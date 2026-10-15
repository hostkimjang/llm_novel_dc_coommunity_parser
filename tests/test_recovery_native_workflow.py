"""합성 HTTP만 대체하고 실제 전문가→native guard→새 publication WAL을 잇는다."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import httpx
import pytest

from src.llm_batch.agentic_pipeline import AgenticPipeline
from src.llm_batch.experts.orchestrator import ExpertType
from src.llm_batch.ledger.publication_commit import (
    PublicationCommitRegistry, build_publication_scope_descriptor,
    commit_publication_result, validate_publication_result_commit,
)
from src.llm_batch.ledger.recovery_provider_journal import canonical_sha256
from src.llm_batch.runtime.recovery_native_io import NativeRecoveryIO, NativeLLMFacade, NativeMCPFacade
from tests.recovery_native_fixtures import (
    DETAIL_URL, ENDPOINTS, TITLE, NativeHTTPFixture, build_native_base_fixture,
    build_native_capture, source_bytes, store_native_provider_evidence,
)


@pytest.fixture(autouse=True)
def isolated_native_registry(tmp_path, monkeypatch):
    # 저장 위치만 격리한다. 원장/예산/guard의 동작은 바꾸지 않는다.
    from src.llm_batch.runtime import recovery_native_io
    from tools import run_recovery_provider
    monkeypatch.setattr(recovery_native_io, "NATIVE_JOB_REGISTRY_ROOT", tmp_path / "native_registry")
    monkeypatch.setattr(run_recovery_provider, "ROOT", tmp_path)


def _prepare(tmp_path, *, case="positive", max_calls=32, cancelled=None, existing_capture=None):
    bundle = build_native_base_fixture(tmp_path / "base", case=case)
    handler = NativeHTTPFixture(bundle["native_case"])
    provider = store_native_provider_evidence(bundle, handler)
    if existing_capture is None:
        # capture 생성에만 쓰는 정상 pipeline. 전문가/최종화는 실행하지 않는다.
        initial_pipeline = AgenticPipeline(llm=object(), mcp=object(),
            output_dir=tmp_path / "capture_only", native_recovery=True)
        captured = build_native_capture(initial_pipeline, bundle)
    else:
        assert existing_capture.source_snapshot == provider["evidence"].input_post
        captured = {"post": existing_capture.post, "context": existing_capture.clone_context(),
                    "capture": existing_capture}
    capture, evidence = captured["capture"], provider["evidence"]
    source_paths = [Path(AgenticPipeline.__module__.replace(".", "/") + ".py")]
    repo = Path(__file__).resolve().parents[1]
    source_hashes = {str(path): hashlib.sha256((repo / path).read_bytes()).hexdigest()
                     for path in source_paths}
    config = {"model": "synthetic-native-model", "max_tokens": 32768,
              "temperature": 0, "top_p": 1, "endpoints": ENDPOINTS}
    binding = {"source_sha256": canonical_sha256(source_hashes),
        "config_sha256": canonical_sha256(config), "base_sha256": canonical_sha256(bundle["bound"].base),
        "context_sha256": capture.context_sha256, "upstream_sha256": canonical_sha256(evidence.report)}
    policy = {"max_calls": max_calls, "max_elapsed_ms": 180000, "request_timeout_ms": 30000,
              "max_response_bytes": 2 * 1024 * 1024, "max_total_response_bytes": 64 * 1024 * 1024}
    def source_check():
        return (bundle["bound"].verify_protected_sources() and evidence.verify_current()
                and capture.verify_current())
    io_args = {"binding": binding, "policy": policy, "endpoints": ENDPOINTS,
        "journal_path": tmp_path / "native" / "native_journal.jsonl", "upstream_receipt": evidence.report,
        "source_check": source_check, "cancelled": cancelled or (lambda: False),
        "test_transport": httpx.MockTransport(handler), "clock_ms": lambda: 2000}
    io = NativeRecoveryIO(**io_args)
    io.llm = NativeLLMFacade(io, **{key: config[key] for key in ("model", "max_tokens", "temperature", "top_p")})
    io.mcp = NativeMCPFacade(io)
    pipeline = AgenticPipeline(llm=io.llm, mcp=io.mcp, output_dir=tmp_path / "pipeline",
                              native_recovery=True, max_iterations=2)
    return {"bundle": bundle, "handler": handler, "provider": provider,
            "capture": capture, "captured": captured, "evidence": evidence,
            "io": io, "io_args": io_args, "pipeline": pipeline, "config": config}


def _commit_native(tmp_path, prepared, outcome):
    """guard 출력에 손대지 않고 실제 main wrapper와 실제 임시 registry를 사용한다."""
    from expert_main import _FinalSourceContextResult

    pipeline, bundle, output = prepared["pipeline"], prepared["bundle"], outcome.output
    payload = output.model_dump(mode="json")
    model_observation = pipeline.verify_final_source_context_serialization(output, payload, stage="model_dump")
    original_post = prepared["capture"].post
    row = deepcopy(bundle["result"])
    row["analysis_result"] = payload
    row["run_meta"] = {"run_id": "native-attempt", "execution_mode": "TEST_SYNTHETIC_NATIVE"}
    wrapped = _FinalSourceContextResult(row, output=output,
        verifier=pipeline.verify_final_source_context_serialization)
    descriptor = build_publication_scope_descriptor(
        input_file_sha256=bundle["source_refs"]["input"]["sha256"], post_ids=[original_post.post_id],
        config_hash=canonical_sha256({"native": prepared["config"], "base_decision_id": bundle["receipt"].decision_id}),
        release_fingerprint="TEST_SYNTHETIC_NATIVE_CONTINUATION")
    assert descriptor.publication_scope_id != bundle["scope"].publication_scope_id
    wal_path = tmp_path / "new_publication" / "publication_commits.jsonl"
    wal_path.parent.mkdir(parents=True, exist_ok=False)
    registry = PublicationCommitRegistry(wal_path, scope_descriptor=descriptor, create_new=True)
    receipt, created = commit_publication_result(wrapped, registry=registry,
        attempt_run_id="native-attempt", input_index=1, post_id=original_post.post_id)
    assert created
    registry = PublicationCommitRegistry(wal_path, scope_descriptor=descriptor, create_new=False)
    stored = registry.result(original_post.post_id)
    stored_observation = wrapped.verify_stored_payload(stored, stage="canonical_stored_payload")
    validate_publication_result_commit(stored, receipt,
        expected_scope_id=descriptor.publication_scope_id, expected_input_index=1, expected_post_id=original_post.post_id)
    return {"row": stored, "receipt": receipt, "registry": registry, "wal_path": wal_path,
            "wrapper": wrapped, "model_observation": model_observation,
            "stored_observation": stored_observation}


@pytest.mark.parametrize("case", ["positive", "hold", "previous", "comparison"])
def test_actual_experts_native_guard_serialization_and_publication_commit(tmp_path, case):
    prepared = _prepare(tmp_path, case=case)
    bundle, handler = prepared["bundle"], prepared["handler"]
    before = source_bytes(bundle)
    old_context = prepared["capture"].clone_context()
    outcome = prepared["pipeline"].continue_native_recovery(
        prepared["capture"], prepared["evidence"], prepared["io"])
    assert outcome.receipt["status"] == "NATIVE_GUARD_EVALUATED"
    assert outcome.output.__dict__["_final_source_context_owner"] is outcome.context
    assert outcome.output.__dict__["_final_source_context_native"] is outcome.context._final_source_projection_native
    assert outcome.receipt["capture_sha256"] == prepared["capture"].capture_sha256
    assert not handler.unexpected
    # 기존 전문가 메서드는 실제 실행됐고 대체 지점은 HTTP뿐이다.
    sequence = outcome.receipt["expert_sequence"]
    assert sequence and len(sequence) == len(set(sequence))
    if case == "hold":
        # 원문에 해독할 key_terms가 없으면 실제 Decoder 메서드는 빈 결과를
        # 반환하고 HTTP를 생략한다. 전문가 단계 자체를 생략한 것과 구별한다.
        assert sequence == ["decoder", "verifier", "synthesizer", "arbiter"]
        assert outcome.context.get_expert_output(ExpertType.GATEKEEPER)["key_terms"] == []
        decoded = outcome.context.get_expert_output(ExpertType.DECODER)
        assert decoded["decoded_terms"] == []
        assert decoded["overall_confidence"] == "none"
        assert handler.tags.count("decoder") == 0
        assert {"verifier", "synthesizer", "arbiter"}.issubset(set(handler.tags))
    else:
        assert {"decoder", "verifier", "synthesizer"}.issubset(set(handler.tags))
    for expert in (ExpertType.DECODER, ExpertType.VERIFIER, ExpertType.SYNTHESIZER, ExpertType.ARBITER):
        value = outcome.context.get_expert_output(expert)
        assert value and "error" not in value
    assert "STALE_PRE_RECOVERY" not in json.dumps(outcome.context.get_expert_output(ExpertType.VERIFIER))
    assert "STALE_PRE_RECOVERY" in json.dumps(old_context.get_expert_output(ExpertType.VERIFIER))
    committed = _commit_native(tmp_path, prepared, outcome)
    assert committed["receipt"].outcome == bundle["native_case"]["expected_outcome"]
    identity = committed["row"]["analysis_result"]["identity"]
    decision = identity["promotion_decision"]
    if case == "positive":
        assert decision["publish_allowed"] is True
        assert identity["novel_identity"]["official_title"] == TITLE
        assert identity["novel_identity"]["heretic_url"] == DETAIL_URL
        assert outcome.output.__dict__["_final_source_context_receipt"]["native_return"] is True
    else:
        assert decision["publish_allowed"] is False
        novel = identity.get("novel_identity") or {}
        assert novel.get("official_title") is None and novel.get("heretic_url") is None
    if case in {"previous", "comparison"}:
        # non-core 공개 후보 목록은 비워질 수 있으므로 실제 canonical WAL의
        # 보존 원장을 검산한다. candidate를 previous/comparison으로 승격하지 않는다.
        candidates = identity["candidate_ledger"]["title_candidate_generation_retained_sources"]
        assert any(row.get("official_title") == TITLE
                   and row.get("heretic_url") == DETAIL_URL
                   and row.get("preservation_role") == "ranked_title_candidate"
                   for row in candidates), candidates
        assert TITLE in prepared["capture"].post.content_blocks[0].text
        assert ("전작이다" if case == "previous" else "처럼") in prepared["capture"].post.content_blocks[0].text
        assert decision.get("official_title") is None
    for flag in ("public_apply", "publication_authority", "central_db_write"):
        assert outcome.receipt[flag] is False
    assert outcome.receipt["actual_quality_evaluated"] is False
    assert outcome.receipt["formal_kpi_status"] == "NOT_ESTIMABLE"
    count = len(handler.requests)
    finalized = prepared["io"].finish({"row": committed["row"], "guard": outcome.receipt,
        "publication_commit": committed["receipt"].to_dict(), "data_kind": "TEST_SYNTHETIC"})
    assert finalized["status"] == "COMPLETED_NATIVE_IO", finalized
    replay = NativeRecoveryIO(**prepared["io_args"]).readback()
    assert replay["status"] == "COMPLETED_NATIVE_IO" and replay["replayed"] is True
    assert replay["native_result"] == finalized["native_result"]
    assert len(handler.requests) == count
    assert source_bytes(bundle) == before
    assert prepared["capture"].verify_current() is True
    # 같은 output에 대한 사후 공개 표시 변조는 새 SHA로 성공시킬 수 없다.
    changed = deepcopy(committed["row"])
    changed["analysis_result"]["identity"]["reason"] += " 원문에 없는 사후 표시"
    with pytest.raises(ValueError):
        committed["wrapper"].verify_stored_payload(changed, stage="tampered_saved_payload")
    assert len(handler.requests) == count
    with pytest.raises(ValueError, match="NATIVE_PIPELINE_ALREADY_CONSUMED"):
        prepared["pipeline"].continue_native_recovery(prepared["capture"], prepared["evidence"], prepared["io"])


@pytest.mark.parametrize("failure", ["cancel", "zero_calls", "changed_provider_raw"])
def test_native_preflight_failure_does_not_become_guard_success(tmp_path, failure):
    prepared = _prepare(tmp_path, case="hold", max_calls=0 if failure == "zero_calls" else 32,
                        cancelled=(lambda: True) if failure == "cancel" else None)
    handler, bundle = prepared["handler"], prepared["bundle"]
    if failure == "changed_provider_raw":
        ref = prepared["evidence"].report["request_receipts"][0]["response_ref"]
        (bundle["bound"].output_dir / ref["path"]).write_bytes(b"{}")
    before, calls = source_bytes(bundle), len(handler.requests)
    with pytest.raises(ValueError):
        prepared["pipeline"].continue_native_recovery(prepared["capture"], prepared["evidence"], prepared["io"])
    assert len(handler.requests) == calls
    assert prepared["io"].readback()["status"] != "COMPLETED_NATIVE_IO"
    assert not list(tmp_path.glob("new_publication/**/*"))
    assert source_bytes(bundle) == before


def test_same_call_process_capture_reaches_actual_native_guard_and_new_commit(tmp_path):
    """전문가 실행 전 capture를 심는 네 사례와 달리 실제 process hook을 소비한다."""
    initial = _prepare(tmp_path / "initial_analysis", case="positive", max_calls=64)
    initial_io, initial_handler = initial["io"], initial["handler"]
    original_post = initial["capture"].post
    initial_binding = initial_io.binding
    initial_sources = source_bytes(initial["bundle"])
    initial_output, capture = initial["pipeline"].process_post_with_recovery_context(original_post)
    initial_io.check()  # process_post가 I/O 오류를 삼켜도 성공으로 보지 않는다.
    assert capture is not None
    assert capture.source_snapshot == initial["evidence"].input_post
    assert capture.verify_current() is True
    assert "_final_source_context_owner" in initial_output.__dict__
    owner = initial_output.__dict__["_final_source_context_owner"]
    assert owner.post_id == original_post.post_id
    assert capture.clone_context() is not owner
    captured_experts = capture.clone_context()
    assert captured_experts.get_expert_output(ExpertType.GATEKEEPER)
    assert "STALE_PRE_RECOVERY" not in json.dumps(captured_experts.expert_outputs, default=str)
    initial_calls = len(initial_handler.requests)
    assert initial_calls > 1 and not initial_handler.unexpected
    initial_public = initial_output.model_dump(mode="json")
    baseline = initial_io.finish({"scope": "INITIAL_ANALYSIS_ONLY", "data_kind": "TEST_SYNTHETIC",
        "capture_sha256": capture.capture_sha256, "output_sha256": canonical_sha256(initial_public)})
    assert baseline["status"] == "COMPLETED_NATIVE_IO"
    assert baseline["total_client_http_invocations"] == initial_calls
    assert initial_io.binding == initial_binding
    # 같은 합성 원문을 별도 고정 provider 계약으로 준비한다. 그 후 새 capture로
    # 처음부터 결속된 I/O/전용 pipeline을 만든다. 이전 binding을 갱신하지 않는다.
    prepared = _prepare(tmp_path / "recovery", case="positive", existing_capture=capture)
    io, handler = prepared["io"], prepared["handler"]
    source_before = source_bytes(prepared["bundle"])
    assert prepared["bundle"]["source_bytes"]["input"] == initial["bundle"]["source_bytes"]["input"]
    assert io.binding["context_sha256"] == capture.context_sha256
    assert io.binding["base_sha256"] == canonical_sha256(prepared["evidence"].base)
    assert io.binding["upstream_sha256"] == canonical_sha256(prepared["evidence"].report)
    assert io is not initial_io and prepared["pipeline"] is not initial["pipeline"]
    before_native_calls = len(handler.requests)
    outcome = prepared["pipeline"].continue_native_recovery(capture, prepared["evidence"], io)
    assert outcome.receipt["capture_sha256"] == capture.capture_sha256
    assert outcome.context is not owner
    assert initial_output.model_dump(mode="json") == initial_public
    assert len(handler.requests) > before_native_calls and not handler.unexpected
    committed = _commit_native(tmp_path, prepared, outcome)
    assert committed["receipt"].outcome == "PUBLISH"
    result = io.finish({"row": committed["row"], "guard": outcome.receipt,
        "publication_commit": committed["receipt"].to_dict(), "data_kind": "TEST_SYNTHETIC",
        "initial_analysis_baseline": {"scope": "EXCLUDED_FROM_RECOVERY_BUDGET",
            "receipt": baseline, "client_http_invocations": initial_calls}})
    assert result["status"] == "COMPLETED_NATIVE_IO"
    assert result["total_actual_external_calls"] == 0
    assert result["total_client_http_invocations"] == len(handler.requests)
    assert baseline["total_client_http_invocations"] + result["total_client_http_invocations"] == (
        len(initial_handler.requests) + len(handler.requests))
    assert initial_io.binding == initial_binding
    assert source_bytes(initial["bundle"]) == initial_sources
    assert source_bytes(prepared["bundle"]) == source_before
    assert capture.verify_current() is True
