from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import json
from unittest.mock import patch

import pytest

from llm_batch import agentic_pipeline as pipeline_module
from llm_batch.agentic_pipeline import AgenticPipeline
from llm_batch.domain.models import ContentBlock, PostInput
from llm_batch.experts.decoder import DecoderExpert
from llm_batch.experts.orchestrator import ExpertType, ConversationContext
from llm_batch.promotion_gate import GroundingState, ScopeState, SemanticPublicationState, EvidenceRecord, evaluate_publish_contract


def _sha(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


TITLE = "합성 은빛 기록 연대기"
URL = "https://novel.munpia.com/999911"


class FakeLLM:
    last_usage = None
    max_tokens = 1024

    def __init__(self):
        self.calls = []

    def _stream_chat_http(self, *, messages, tag, **kwargs):
        self.calls.append((tag, deepcopy(messages)))
        if tag == "decoder":
            # 독립 검색 없이 후보를 High/공식 URL로 주장하는 모델도 제품 guard가 거절해야 한다.
            return json.dumps({"decoded_terms": [{"original": "은기록", "best_match": {"title": TITLE, "url": URL, "confidence": "high"},
                "candidates": [{"official_title": TITLE, "url": URL, "confidence": "high", "is_verified": True}],
                "grounding": {"is_grounded": True, "anchor_type": "title_alias"}}], "overall_confidence": "high"}, ensure_ascii=False)
        return "{}"


class FakeMCP:
    def __init__(self, rows=None):
        self.calls = []
        self.rows = rows or []

    def search(self, query, purpose="", **kwargs):
        self.calls.append((query, purpose))
        return {"results": deepcopy(self.rows), "total": len(self.rows), "raw_total": len(self.rows), "retry_count": 0}

    def fetch(self, url, **kwargs):
        self.calls.append(("fetch", url))
        return {"success": False, "content": "", "error": "synthetic_no_page"}


class ExpertStub:
    def __init__(self, llm, role, no_terms=False):
        self.llm, self.role, self.no_terms = llm, role, no_terms

    def analyze(self, *args, **kwargs):
        if self.role == "gatekeeper":
            return {"is_noise": False, "post_type": "work_discussion", "key_terms": [] if self.no_terms else ["은기록"],
                "detected_entities": {}, "context_clues": {}, "search_requests": []}
        if self.role == "discourse":
            return {"discourse_analysis": {"primary_domain": "novel_literature", "domain_confidence": "high", "intent": "discuss_work"}}
        if self.role == "verifier":
            return {"is_verified": False, "is_relevant": False, "overall_confidence": "low", "novel_identity": {"official_title": None}, "verification_search": []}
        if self.role == "arbiter":
            return {"is_relevant": False, "official_title": None, "confidence": "low", "discussion_type": "undecodable_reference", "reason": "합성 시험: 독립 작품 근거 없음"}
        return {}


class SnapshotStub:
    def __init__(self, behavior="ok"):
        self.views = []
        self.behavior = behavior

    def summary(self):
        return {"snapshot_sha256": "a"*64, "config_sha256": "b"*64, "data_kind": "SYNTHETIC_FIXTURE"}

    def query(self, view):
        self.views.append(deepcopy(view))
        if self.behavior == "raise":
            raise RuntimeError("SECRET_MUST_NOT_LEAK")
        receipt = {"schema_version": "community_knowledge_readback_v1", "mode": "READ_ONLY", "post_id": view["post_id"],
            "status": "AMBIGUOUS", "reason_codes": [], "query_sha256": _sha(view), "snapshot_sha256": "a"*64,
            "config_sha256": "b"*64, "public_authority": False, "public_apply": False, "central_db_write": False,
            "candidates": [{"candidate_id": "synthetic:alias", "surface": "은기록", "sense_id": "work-sense", "definition": TITLE,
                "source_refs": [{"source_ref": "fixture://source", "payload_byte_sha256": "c"*64}],
                "work_alias_entries": [{"canonical_title": TITLE, "work_id": "synthetic-work"}]},
                {"candidate_id": "synthetic:general", "surface": "은기록", "sense_id": "general-sense", "definition": "은색으로 적은 개인 기록", "source_refs": []}],
            "consumption": {"status": "QUERY_ONLY"}, "receipt_digest_scope": "CANONICAL_EXCLUDING_ELAPSED_SELF_AND_STORAGE_BINDING"}
        if self.behavior == "wrong_hash":
            receipt["query_sha256"] = "0"*64
        if self.behavior == "authority":
            receipt["public_authority"] = True
        if self.behavior == "oversize":
            receipt["candidates"][0]["definition"] = "한"*20000
        if self.behavior == "prompt_limit":
            receipt["candidates"][0]["definition"] = "한"*3500
        if self.behavior == "wrong_snapshot":
            receipt["snapshot_sha256"] = "0"*64
        if self.behavior == "wrong_config":
            receipt["config_sha256"] = "0"*64
        if self.behavior in {"UNAVAILABLE", "INVALID_INPUT", "LIMIT_EXCEEDED", "NO_MATCH"}:
            receipt.update(status=self.behavior, candidates=[], reason_codes=["SYNTHETIC_"+self.behavior])
        receipt["receipt_sha256"] = _sha(receipt)
        if self.behavior == "bad_digest":
            receipt["receipt_sha256"] = "0"*64
        if self.behavior == "invalid_json":
            receipt["invalid"] = object()
        return receipt


@pytest.fixture(autouse=True)
def environment(monkeypatch):
    for key in ("LLM_VLM_ENABLED", "PIPELINE_REASON_LLM_REVIEW", "PIPELINE_HERETIC_LIVE_FETCH", "PIPELINE_ACTIVE_LEARNING_QUEUE", "LLM_CONTEXT_COMPACT"):
        monkeypatch.setenv(key, "0")
    monkeypatch.setenv("PIPELINE_POSTPROCESS_TRACE", "0")
    monkeypatch.setenv("PIPELINE_CONTEXT_TO_OUTPUT_DUMP_AFTER", "0")
    monkeypatch.setenv("DELIBERATION_ENABLED", "0")
    monkeypatch.setattr("socket.create_connection", lambda *a, **kw: pytest.fail("network forbidden"))


def _pipeline(tmp_path, snapshot=None, no_terms=False):
    llm, mcp = FakeLLM(), FakeMCP()
    with patch.object(pipeline_module, "GatekeeperExpert", lambda client: ExpertStub(client, "gatekeeper")), patch("llm_batch.experts.decoder.get_kiwi", return_value=None):
        pipeline = AgenticPipeline(llm=llm, mcp=mcp, output_dir=tmp_path, max_iterations=2, community_knowledge=snapshot)
    pipeline.experts.update({kind: ExpertStub(llm, kind.value, no_terms) for kind in ExpertType if kind != ExpertType.DECODER})
    pipeline.orchestrator.experts = pipeline.experts
    pipeline.orchestrator._try_fast_path = lambda *a, **kw: None
    return pipeline, llm, mcp


def _post(post_id=991):
    return PostInput(post_id=post_id, gallery_id="synthetic-community", created_at="2026-10-08T00:00:00Z",
        title="은기록 에 관한 긴 후기", content_blocks=[ContentBlock(type="text", text="은기록 이라는 말은 여러 의미라서 문맥을 확인해야 한다.")],
        comments=[{"content": "은기록 의 다른 뜻도 있다"}], judge_seed={"official_title": "REFERENCE_NOT_QUERY"})


def _public(output):
    assert not (output.identity.reason or "").startswith("처리 오류:"), output.identity.reason
    value = output.model_dump(mode="json")
    assert "_community_knowledge_readback" not in value
    return value


def test_actual_process_orchestrator_decoder_prompt_and_private_consumption(tmp_path):
    store = SnapshotStub()
    pipeline, llm, _ = _pipeline(tmp_path, store)
    session_before = deepcopy(pipeline.session_knowledge)
    before = _post().model_dump()
    output = pipeline.process_post(_post())
    _public(output)
    assert len(store.views) == 1 and _post().model_dump() == before
    decoder_calls = [messages for tag, messages in llm.calls if tag == "decoder"]
    assert decoder_calls
    prompt = decoder_calls[0][1]["content"]
    assert "COMMUNITY KNOWLEDGE CANDIDATES" in prompt and "synthetic:alias" in prompt and "synthetic:general" in prompt
    assert "fixture://source" in prompt
    assert "REFERENCE_NOT_QUERY" not in json.dumps(store.views)
    receipt = output.__dict__["_community_knowledge_readback"]
    assert receipt["consumption"]["prompt_included_calls"] == len(decoder_calls)
    assert 0 < receipt["consumption"]["prompt_bytes"] <= 8192
    assert receipt["consumption"]["candidate_ids"] == ["synthetic:alias", "synthetic:general"]
    assert len(receipt["store_receipt_sha256"]) == 64 and receipt["store_receipt_sha256"] != receipt["receipt_sha256"]
    assert receipt["receipt_sha256"] == _sha({key: value for key, value in receipt.items() if key not in {"receipt_sha256", "latency_ms", "elapsed_ms", "binding"}})
    assert output.identity.novel_identity is None or output.identity.novel_identity.official_title is None
    assert output.identity.title_resolution_allowed is not True
    assert output.batch_context_learning_envelope is None and pipeline.session_knowledge == session_before


@pytest.mark.parametrize("behavior,code", [("raise", "QUERY_EXCEPTION"), ("wrong_hash", "QUERY_FINGERPRINT_MISMATCH"), ("authority", "INVALID_RECEIPT"), ("oversize", "RECEIPT_LIMIT_EXCEEDED"), ("invalid_json", "INVALID_RECEIPT"), ("wrong_snapshot", "INVALID_RECEIPT"), ("wrong_config", "INVALID_RECEIPT"), ("bad_digest", "RECEIPT_DIGEST_MISMATCH")])
def test_query_failures_keep_existing_decoder_prompt_without_secret(tmp_path, behavior, code):
    off, off_llm, _ = _pipeline(tmp_path/"off")
    on, on_llm, _ = _pipeline(tmp_path/"on", SnapshotStub(behavior))
    baseline = off.process_post(_post())
    output = on.process_post(_post())
    _public(baseline); _public(output)
    assert off_llm.calls == on_llm.calls
    receipt = output.__dict__["_community_knowledge_readback"]
    assert receipt["status"] == "ERROR" and receipt["reason_codes"] == [code]
    assert "SECRET" not in json.dumps(receipt)
    assert receipt["snapshot_sha256"] == "a"*64
    assert receipt["consumption"]["prompt_included_calls"] == 0
    assert receipt["consumption"]["status"] == "NOT_CONSUMED_ERROR"


def test_original_paths_explicit_scope_and_unknown_timezone(tmp_path):
    snapshot = SnapshotStub()
    pipeline, _, _ = _pipeline(tmp_path, snapshot)
    post = _post()
    post.created_at = "2026-10-08 03:00:00"
    post.gallery_id = "test"
    post.comments.extend(["문자열", {"text": "다른 댓글"}])
    pipeline.process_post(post)
    view = snapshot.views[0]
    assert view["community"] == {"value": None, "source_path": "/gallery_id", "status": "UNKNOWN"}
    assert view["as_of"]["status"] == "UNKNOWN" and view["as_of"]["value"] is None
    assert {row["raw_path"] for row in view["fragments"]} == {"/title", "/content_blocks/0/text", "/comments/0/content", "/comments/1", "/comments/2/text"}


def test_prompt_limit_is_explicit_and_off_reuse_removes_private_receipt(tmp_path):
    pipeline, llm, _ = _pipeline(tmp_path, SnapshotStub("prompt_limit"))
    output = pipeline.process_post(_post())
    _public(output)
    assert output.__dict__["_community_knowledge_readback"]["consumption"]["status"] == "NOT_CONSUMED_PROMPT_LIMIT"
    assert all("COMMUNITY KNOWLEDGE CANDIDATES" not in messages[1]["content"] for tag, messages in llm.calls if tag == "decoder")
    pipeline._community_knowledge = None
    with patch.object(pipeline, "_context_to_output", return_value=output):
        result = pipeline.process_post(_post())
    assert result is output and "_community_knowledge_readback" not in output.__dict__


def test_actual_fast_path_records_no_decoder_consumption(tmp_path):
    snapshot = SnapshotStub()
    pipeline, llm, _ = _pipeline(tmp_path, snapshot)
    del pipeline.orchestrator._try_fast_path
    output = pipeline.process_post(PostInput(post_id=995, title=""))
    _public(output)
    assert len(snapshot.views) == 1 and not llm.calls
    assert output.__dict__["_community_knowledge_readback"]["consumption"]["status"] == "NOT_CONSUMED_FAST_PATH"


def test_publication_gate_blocks_forged_high_evidence_but_keeps_independent_source(tmp_path):
    pipeline, _, _ = _pipeline(tmp_path)
    ctx = ConversationContext(post_id=991, post_data={"title": "은기록", "content_blocks": []}, comments=[])
    ctx._community_knowledge_readback = {"consumption": {"prompt_included_calls": 1}}
    state = GroundingState(post_id=991, candidate_title=TITLE, candidate_url=URL, official_title_exists=True,
        row_discusses_work_as_work=True, title_resolution_state="resolved", work_resolution="resolved",
        scope=ScopeState(scope_kind="current_work", confidence="high", direct_bridge_sources=("forged_model_alias",)),
        semantic_publication=SemanticPublicationState(evidence_status="sufficient", media_domain_class="novel_work", primary_work_status="unique"))
    evidence = [EvidenceRecord(kind="official_title", strength="high", supports_publish=True, candidate_title=TITLE, candidate_url=URL, title_url_match=True)]
    contract = evaluate_publish_contract(state, evidence, post_gate_context={})
    guarded = pipeline._community_knowledge_guard_contract(ctx, contract, {})
    assert guarded.decision.publish_allowed is False and guarded.decision.official_title is None and guarded.decision.official_url is None
    assert guarded.state.semantic_publication.evidence_status == "insufficient"
    assert guarded.state.semantic_publication.media_domain_class == "novel_work"
    assert guarded.state.semantic_publication.primary_work_status == "unique"
    ctx.search_results = [{"title": TITLE, "url": URL, "content": "독립적인 합성 공식 상세 검색 결과"}]
    assert pipeline._community_knowledge_guard_contract(ctx, contract, {}) is contract


def test_shared_snapshot_isolated_across_actual_workers(tmp_path):
    snapshot = SnapshotStub()
    workers = [_pipeline(tmp_path/str(i), snapshot)[0] for i in range(2)]
    with ThreadPoolExecutor(max_workers=2) as pool:
        outputs = list(pool.map(lambda p: p[0].process_post(_post(p[1])), zip(workers, [996, 997])))
    for output in outputs:
        _public(output)
        receipt = output.__dict__["_community_knowledge_readback"]
        view = next(item for item in snapshot.views if item["post_id"] == output.post_id)
        assert receipt["query_sha256"] == _sha(view) and receipt["post_id"] == output.post_id
        assert receipt["consumption"]["candidate_ids"]


def _real_store(tmp_path):
    from llm_batch.grounding import p0_source_profile_raw_parser_core as parser
    from llm_batch.grounding.community_knowledge_builder import build_snapshot, CAPTURE_SCHEMA
    from llm_batch.grounding.community_knowledge import load_snapshot
    capture = tmp_path/"capture"
    capture.mkdir()
    payload = (f"'은기록'은 {TITLE}를 뜻한다.\n'은기록'은 은색으로 적은 개인 기록을 뜻한다.\n").encode()
    rights = b"SYNTHETIC_FIXTURE; newly authored test text; no real source rights assertion"
    (capture/"payload.txt").write_bytes(payload)
    (capture/"rights.txt").write_bytes(rights)
    source = {"source_id": "synthetic-capture", "source_ref": "fixture://r3-source", "payload_ref": "payload.txt",
        "payload_byte_sha256": hashlib.sha256(payload).hexdigest(), "capture_profile": parser.SUPPORTED_PROFILE,
        "capture_version": parser.SUPPORTED_CAPTURE_VERSION, "normalization_version": parser.SUPPORTED_NORMALIZATION_VERSION,
        "source_published_at": "2026-10-01T00:00:00Z", "source_modified_at": None, "captured_at": "2026-10-02T00:00:00Z",
        "available_at": "2026-10-02T00:00:00Z", "time_unknown_reason": None, "community_scope": ["synthetic-community"],
        "lineage_root_id": "fixture-root", "parent_id": None, "derivation_kind": "ORIGINAL", "lineage_status": "DECLARED",
        "rights": {"status": "SYNTHETIC_FIXTURE", "basis_ref": "rights.txt", "basis_sha256": hashlib.sha256(rights).hexdigest(),
                   "collection": True, "retention": True, "derived_index": True, "quotation": True,
                   "reviewed_at": "2026-10-02T00:00:00Z", "takedown_status": "ACTIVE"}}
    spec = {"schema_version": CAPTURE_SCHEMA, "snapshot_id": "synthetic-pipeline-corpus", "data_kind": "SYNTHETIC_FIXTURE",
        "built_at": "2026-10-10T00:00:00Z", "freeze_cutoff": "2026-10-09T00:00:00Z",
        "captures": [{"source": source, "content_type": parser.SUPPORTED_CONTENT_TYPE,
            "temporal_scope": {"valid_from": "2026-10-01T00:00:00Z", "valid_to": None, "time_unknown_reason": None}, "reviews": []}]}
    (capture/"capture.json").write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    build = build_snapshot(capture/"capture.json", tmp_path/"snapshot", capture_root=capture, output_root=tmp_path)
    return load_snapshot(tmp_path/"snapshot/manifest.json", expected_sha256=build["snapshot_sha256"])


def test_real_local_builder_store_pipeline_decoder_and_runtime_export(tmp_path):
    from llm_batch.runtime.community_knowledge import export_community_knowledge_fields
    from llm_batch.ledger.publication_commit import _stable_result_payload
    real = _real_store(tmp_path)
    class Counted:
        calls = 0
        summary = real.summary
        def query(self, view):
            self.calls += 1
            return real.query(view)
    store = Counted()
    pipeline, llm, _ = _pipeline(tmp_path/"runtime", store)
    output = pipeline.process_post(_post())
    public = _public(output)
    readback = output.__dict__["_community_knowledge_readback"]
    assert store.calls == 1 and readback["status"] == "AMBIGUOUS"
    assert len(readback["candidates"]) == 2 and readback["consumption"]["prompt_included_calls"] > 0
    assert readback["candidates"][0]["source_refs"][0]["source_ref"] == "fixture://r3-source"
    prompt = next(messages[1]["content"] for tag, messages in llm.calls if tag == "decoder")
    assert all(item["candidate_id"] in prompt for item in readback["candidates"])
    binding = {"run_id": "synthetic-r3", "input_index": 1, "post_id": 991, "attempt_id": "attempt", "publication_scope_id": "scope"}
    exported = export_community_knowledge_fields(output, real, binding=binding)
    stored = exported["community_knowledge_readback"]
    assert stored["status"] == "AMBIGUOUS" and stored["receipt_sha256"] == readback["receipt_sha256"]
    assert stored["binding"]["scope"] == "ATTEMPT_LOCAL_CONSUMPTION"
    # 모델 실행 설정은 동일한 채 receipt만 더한 경우의 저장 지문을 비교한다.
    row = {"post_id": 991, "analysis_result": public, "run_meta": {"run_id": "synthetic-r3"}}
    with_receipt = deepcopy(row)
    with_receipt["run_meta"].update(exported)
    assert _stable_result_payload(row) == _stable_result_payload(with_receipt)


def test_off_keeps_original_orchestrator_call_and_no_snapshot_import(tmp_path):
    import builtins
    pipeline, _, _ = _pipeline(tmp_path)
    original_import = builtins.__import__
    def guarded_import(name, *args, **kwargs):
        assert "community_knowledge" not in name
        return original_import(name, *args, **kwargs)
    with patch.object(pipeline.orchestrator, "process", wraps=pipeline.orchestrator.process) as process, patch("builtins.__import__", side_effect=guarded_import):
        output = pipeline.process_post(_post())
    _public(output)
    assert set(process.call_args.kwargs) == {"post_data", "comments", "rules_config"}
    assert "_community_knowledge_readback" not in output.__dict__


def test_no_key_terms_and_post_conversion_do_not_create_candidate_authority(tmp_path):
    pipeline, llm, _ = _pipeline(tmp_path, SnapshotStub())
    receipt = pipeline._query_community_knowledge(_post())
    ctx = ConversationContext(post_id=991, post_data={"title": TITLE}, comments=[])
    ctx._final_source_original_inputs = [{"origin": "post_title", "raw_text": "은기록", "caller_disposition": "passed_to_source"}]
    ctx._community_knowledge_readback = receipt
    result = pipeline.experts[ExpertType.DECODER].analyze({"key_terms": []}, [], {}, ctx=ctx, community_knowledge_context=receipt)
    assert not llm.calls and result["decoded_terms"] == []
    assert receipt["consumption"]["status"] == "NOT_CONSUMED_NO_KEY_TERMS"
    assert not DecoderExpert.community_knowledge_independent_title_support(ctx, TITLE)


def test_late_pipeline_error_preserves_actual_prompt_consumption(tmp_path):
    pipeline, llm, _ = _pipeline(tmp_path, SnapshotStub())
    original = pipeline.orchestrator.process
    def run_then_fail(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("synthetic late failure")
    with patch.object(pipeline.orchestrator, "process", side_effect=run_then_fail):
        output = pipeline.process_post(_post())
    assert output.identity.reason.startswith("처리 오류:")
    receipt = output.__dict__["_community_knowledge_readback"]
    assert receipt["consumption"]["prompt_included_calls"] == sum(tag == "decoder" for tag, _ in llm.calls) > 0


def test_final_receipt_size_limit_is_explicit_after_actual_consumption(tmp_path):
    pipeline, _, _ = _pipeline(tmp_path, SnapshotStub())
    original = pipeline.orchestrator.process
    def with_large_diagnostic(*args, **kwargs):
        ctx = original(*args, **kwargs)
        ctx._community_knowledge_readback["consumption"]["oversize_diagnostic"] = "한"*17000
        return ctx
    with patch.object(pipeline.orchestrator, "process", side_effect=with_large_diagnostic):
        output = pipeline.process_post(_post())
    _public(output)
    receipt = output.__dict__["_community_knowledge_readback"]
    assert receipt["reason_codes"] == ["FINAL_RECEIPT_LIMIT_EXCEEDED"]
    assert receipt["consumption"] == {"status": "CONSUMPTION_RECEIPT_LIMIT", "details_available": False}
    assert len(json.dumps(receipt, ensure_ascii=False).encode()) < 48*1024


def test_independent_full_title_particle_boundary_preserves_publish_contract(tmp_path):
    pipeline, _, _ = _pipeline(tmp_path)
    state = GroundingState(post_id=991, candidate_title=TITLE, candidate_url=URL, official_title_exists=True,
        row_discusses_work_as_work=True, title_resolution_state="resolved", work_resolution="resolved",
        scope=ScopeState(scope_kind="current_work", confidence="high", direct_bridge_sources=("original_full_title",)),
        semantic_publication=SemanticPublicationState(evidence_status="sufficient", media_domain_class="novel_work", primary_work_status="unique"))
    evidence = [EvidenceRecord(kind="official_title", strength="high", supports_publish=True, candidate_title=TITLE, candidate_url=URL, title_url_match=True)]
    baseline = evaluate_publish_contract(state, evidence, post_gate_context={})
    assert baseline.decision.publish_allowed is True
    cases = [(TITLE+"를 읽었다.", True), (TITLE+"는 재미있다.", True), (TITLE+"에서 나온 대사", True),
             (TITLE+"만 읽었다.", True), ("《"+TITLE+"》를 읽었다.", True),
             (TITLE+"외전을 읽었다.", False), (TITLE+"의귀환을 읽었다.", False),
             (TITLE+"가짜를 읽었다.", False), (TITLE+"2를 읽었다.", False),
             (TITLE+"_다른작품", False), ("신"+TITLE, False), (TITLE+"으로써진다", False)]
    for text, expected in cases:
        ctx = ConversationContext(post_id=991, post_data={"title": "은기록", "content_blocks": []}, comments=[])
        ctx._final_source_original_inputs = [{"origin": "body_line", "raw_text": text, "caller_disposition": "passed_to_source"}]
        ctx._community_knowledge_readback = {"consumption": {"prompt_included_calls": 1}}
        assert DecoderExpert.community_knowledge_independent_title_support(ctx, TITLE) is expected, text
        guarded = pipeline._community_knowledge_guard_contract(ctx, baseline, {})
        assert guarded.decision.publish_allowed is expected, text
        if expected:
            assert guarded is baseline
    # 원문 조사의 제한적 허용을 공식 검색 제목의 긴 작품명에 적용하지 않는다.
    ctx._final_source_original_inputs = []
    ctx.search_results = [{"title": TITLE+"는 영원하다", "url": URL}]
    assert not DecoderExpert.community_knowledge_independent_title_support(ctx, TITLE)


@pytest.mark.parametrize("query_status,consumption_status", [("UNAVAILABLE", "NOT_CONSUMED_UNAVAILABLE"),
    ("INVALID_INPUT", "NOT_CONSUMED_INVALID_INPUT"), ("LIMIT_EXCEEDED", "NOT_CONSUMED_QUERY_LIMIT"),
    ("NO_MATCH", "NOT_CONSUMED_NO_ELIGIBLE_CANDIDATES")])
def test_query_failure_consumption_remains_distinct_from_empty_result(tmp_path, query_status, consumption_status):
    pipeline, llm, _ = _pipeline(tmp_path, SnapshotStub(query_status))
    output = pipeline.process_post(_post())
    _public(output)
    receipt = output.__dict__["_community_knowledge_readback"]
    assert receipt["status"] == query_status and receipt["reason_codes"] == ["SYNTHETIC_"+query_status]
    assert receipt["consumption"]["status"] == consumption_status
    assert receipt["consumption"]["prompt_included_calls"] == 0
    assert all("COMMUNITY KNOWLEDGE CANDIDATES" not in messages[1]["content"] for tag, messages in llm.calls if tag == "decoder")


def test_query_exception_reason_survives_fast_path(tmp_path):
    pipeline, _, _ = _pipeline(tmp_path, SnapshotStub("raise"))
    del pipeline.orchestrator._try_fast_path
    output = pipeline.process_post(PostInput(post_id=999, title=""))
    receipt = output.__dict__["_community_knowledge_readback"]
    assert receipt["status"] == "ERROR" and receipt["consumption"]["status"] == "NOT_CONSUMED_ERROR"
    assert receipt["consumption"]["route"] == "FAST_PATH"
