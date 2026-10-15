"""자동 배치의 실제 파일/계약/guard 경계. 외부 HTTP 응답만 합성으로 대체한다."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path

import httpx
import pytest

from src.llm_batch.agentic_pipeline import AgenticPipeline
from src.llm_batch.ledger.private_file import create_private_file
from src.llm_batch.ledger.publication_commit import (
    PUBLICATION_COMMIT_EVENT_SCHEMA, build_publication_scope_descriptor, compute_publication_decision_commit,
)
from src.llm_batch.ledger.recovery_activation import _create_event, extract_direct_ocr_review_proposals
from src.llm_batch.measurement.semantic_review_router import build_semantic_review_router_receipt
from src.llm_batch.measurement.semantic_recovery_plan import build_semantic_recovery_plan_receipt
from src.llm_batch.monitor.recovery_native_view import read_recovery_native_view
from src.llm_batch.runtime import recovery_native_batch as batch_module
from src.llm_batch.runtime.recovery_native_batch import (
    NativeRecoveryBatchCoordinator, NativeRecoveryBatchError, POLICY_SCHEMA, validate_native_batch_policy,
)
from tests.recovery_execution_fixtures import _hold_result, json_bytes
from tests.recovery_native_fixtures import (
    ENDPOINTS, NativeHTTPFixture, build_native_base_fixture, build_native_capture,
)
from tests.recovery_provider_fixtures import build_recovery_provider_fixture


def batch_policy(*, captures=1, calls=33, native_calls=32):
    return {"schema_version": POLICY_SCHEMA, "max_capture_rows": captures, "max_batch_calls": calls,
        "max_batch_elapsed_ms": 1000000, "max_batch_response_bytes": 100 * 1024 * 1024,
        "provider_policy": {"max_calls": 1, "max_elapsed_ms": 10000, "request_timeout_ms": 5000,
            "max_response_bytes": 32768, "max_total_response_bytes": 32768},
        "native_policy": {"max_calls": native_calls, "max_elapsed_ms": 180000, "request_timeout_ms": 30000,
            "max_response_bytes": 2 * 1024 * 1024, "max_total_response_bytes": 64 * 1024 * 1024},
        "provider_endpoint": ENDPOINTS["MCP_SEARCH"], "native_config": {
            "endpoints": deepcopy(ENDPOINTS), "model": "synthetic-native-model", "max_tokens": 32768,
            "temperature": 0, "top_p": 1, "server_type": "openai", "min_p": None, "repeat_penalty": None,
            "enable_thinking": False, "temperature_by_tag": {}, "vllm_top_k": None, "vllm_presence_penalty": None}}


@pytest.fixture(autouse=True)
def isolated_io(tmp_path, monkeypatch):
    from src.llm_batch.runtime import recovery_native_io
    from tools import run_recovery_provider
    monkeypatch.setattr(recovery_native_io, "NATIVE_JOB_REGISTRY_ROOT", tmp_path / "native_registry")
    # 대시보드 health I/O 응답만 대체한다. source/원장/guard/resource 검사는 실제 코드다.
    monkeypatch.setattr(run_recovery_provider, "_dashboard_health", lambda url: {
        "url": url, "pid": 42, "service": "expert-pipeline-monitor", "standalone": True})
    for key in list(os.environ):
        if key.startswith(("PIPELINE_MEASUREMENT_", "PIPELINE_PAIRED_EXECUTION_")):
            monkeypatch.delenv(key)
    monkeypatch.delenv("EXPERT_EXECUTION_PROFILE", raising=False)


def prepare_batch(tmp_path, *, policy=None, two=False, capture=None, case="positive", cancelled=None, clock=None):
    """수동 HOLD는 원래 publication 결속 fixture다. 이후 native guard는 실제 실행한다."""
    policy = batch_policy() if policy is None else deepcopy(policy)
    bundle = (build_recovery_provider_fixture(tmp_path / "base") if two else
              build_native_base_fixture(tmp_path / "base", case=case))
    # 두 builder의 기존 합성 key와 별개로 CLI의 32-byte/64-hex 계약을 따른다.
    # 아래서 새로 쓰는 AUDIT event와 audit.hex에 같은 키를 사용한다.
    bundle["hmac_key"] = hashlib.sha256(b"r6-auto-batch-synthetic-key-only").digest()
    assert len(bundle["hmac_key"]) == 32 and len(bundle["hmac_key"].hex()) == 64
    # main처럼 검토 metadata를 부착한 후 최종 commit을 새로 계산한다.
    # fixture 준비 단계이며, 실행에 넘긴 원본은 이후 한 바이트도 수정하지 않는다.
    results, receipts, events = [], [], []
    for index, original in enumerate(bundle["results"], 1):
        row = deepcopy(original)
        base = bundle["receipts"][index-1]
        router = build_semantic_review_router_receipt(row, base, attempt_run_id=base.attempt_run_id)
        recovery = build_semantic_recovery_plan_receipt(row, base, attempt_run_id=base.attempt_run_id)
        row.setdefault("run_meta", {}).update(semantic_review_router_receipt=router, semantic_recovery_plan_receipt=recovery)
        receipt = compute_publication_decision_commit(row, publication_scope_id=base.publication_scope_id,
            attempt_run_id=base.attempt_run_id, input_index=index, post_id=row["post_id"])
        results.append(row); receipts.append(receipt)
        proposal = extract_direct_ocr_review_proposals(row)[0]
        events.append(_create_event(receipt=receipt, proposal=proposal, raw_capability="synthetic-batch-audit-only",
            hmac_key=bundle["hmac_key"], sequence=index,
            prev_event_sha256=events[-1].event_sha256 if events else "GENESIS"))
    manifest = {**bundle["manifest"], "input_post_count": len(results), "native_recovery_policy": policy}
    newraw = {"result": json_bytes(results), "manifest": json_bytes(manifest),
        "publication_wal": b"".join(json_bytes({"schema_version": PUBLICATION_COMMIT_EVENT_SCHEMA,
            "receipt": receipt.to_dict(), "result": row}) + b"\n" for receipt, row in zip(receipts, results)),
        "activation_journal": b"".join(json_bytes(event.to_dict()) + b"\n" for event in events)}
    for role, raw in newraw.items():
        Path(bundle["source_refs"][role]["path"]).write_bytes(raw)
        bundle["source_bytes"][role] = raw
        bundle["source_refs"][role].update(sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))
    key_path = tmp_path / "audit.hex"
    with os.fdopen(create_private_file(key_path), "wb") as stream:
        stream.write((bundle["hmac_key"].hex() + "\n").encode())
    handler = NativeHTTPFixture(bundle["native_case"]) if not two else None
    transport = httpx.MockTransport(handler or (lambda req: (_ for _ in ()).throw(AssertionError("dispatch forbidden"))))
    kwargs = dict(policy=policy, input_post_ids=[r["post_id"] for r in results],
        input_snapshot_bytes=bundle["source_bytes"]["input"], input_path=Path(bundle["source_refs"]["input"]["path"]),
        output_dir=tmp_path / "batch", root=tmp_path, hmac_key_path=key_path,
        dashboard_url="http://127.0.0.1:8080", data_kind="TEST_SYNTHETIC",
        test_transport=transport, clock_ms=clock or (lambda: 2000), cancelled=cancelled,
        run_id=manifest["run_id"], publication_scope_id=manifest["publication_scope_id"])
    coordinator = NativeRecoveryBatchCoordinator(**kwargs)
    if capture is None and not two:
        pipeline = AgenticPipeline(llm=object(), mcp=object(), output_dir=tmp_path / "capture", native_recovery=True)
        capture = build_native_capture(pipeline, bundle)["capture"]
    return {"bundle": bundle, "batch": coordinator, "capture": capture, "results": results,
        "receipts": receipts, "kwargs": kwargs, "handler": handler,
        "drain": {name + "_path": Path(bundle["source_refs"][name]["path"])
                  for name in ("result", "manifest", "publication_wal", "scope_descriptor", "activation_journal")}}


def accept(prepared):
    return prepared["batch"].accept_committed(1, prepared["results"][0]["post_id"], prepared["capture"],
        result=prepared["results"][0], receipt=prepared["receipts"][0], created=True)


def protected(prepared):
    return {role: Path(ref["path"]).read_bytes() for role, ref in prepared["bundle"]["source_refs"].items()}


def prepare_block_projection_batch(tmp_path, fault, *, omit_comments=False, separate_comments=()):
    """content 없는 원문을 실제 loader/main helper로 투영한 새 합성 확정 원본."""
    from expert_main import load_jsonl_posts, _public_content_blocks, _public_image_urls

    source_dir = tmp_path / "projection_source"
    source_dir.mkdir()
    post = {"gallery_id": "synthetic_r6", "post_id": 101, "title": "합성 복구 계약",
        "content_blocks": [
            {"type": "image", "url": "https://example.invalid/original-source.png"},
            {"type": "text", "text": "  합성 자료의 첫 번째 원문.  "},
            {"type": "text", "text": "이미지는 원문 블록의 순서와 URL로 검산한다."}], "comments": []}
    if fault == "alias":
        post["content"] = ["서로 다른 원문을 같은 content alias라고 선언할 수 없다."]
    if omit_comments:
        post.pop("comments")
    raw_input = json_bytes(post) + b"\n" + b"".join(json_bytes(c) + b"\n" for c in separate_comments)
    input_path = source_dir / "input.jsonl"
    with input_path.open("xb") as stream:
        stream.write(raw_input)
    loaded = load_jsonl_posts(input_path, snapshot_bytes=raw_input)
    assert len(loaded) == 1
    if fault != "alias":
        assert not getattr(loaded[0], "_input_truncated", None)
        assert not getattr(loaded[0], "_parse_errors", ())
    result = _hold_result(101, "primary")
    result["comments"] = [c["content"] for c in loaded[0].comments]
    # main의 공개 필드 생성 경로를 사용하며 새 projection validator로 기대값을 만들지 않는다.
    result.update(content=[block.text for block in loaded[0].content_blocks if block.text],
        content_blocks=_public_content_blocks(loaded[0].content_blocks),
        image_urls=_public_image_urls(loaded[0].content_blocks))
    result["image_count"] = len(result["image_urls"])
    if fault == "text":
        result["content"][0] = "원문에서 온 것이 아닌 텍스트"
    elif fault == "blocks":
        result["content_blocks"] = result["content_blocks"][1:]
    elif fault == "image_urls":
        result["image_urls"] = ["https://example.invalid/other-source.png"]
    elif fault == "image_count":
        result["image_count"] = True
    scope = build_publication_scope_descriptor(input_file_sha256=hashlib.sha256(raw_input).hexdigest(),
        post_ids=[101], config_hash="synthetic-projection-batch", release_fingerprint="TEST_SYNTHETIC")
    receipt = compute_publication_decision_commit(result, publication_scope_id=scope.publication_scope_id,
        attempt_run_id="synthetic-projection-owner", input_index=1, post_id=101)
    policy = batch_policy()
    manifest = {"run_id": "synthetic-projection-export", "output_file": str(source_dir / "result.json"),
        "publication_scope_id": scope.publication_scope_id,
        "publication_input_snapshot_sha256": hashlib.sha256(raw_input).hexdigest(),
        "publication_scope_descriptor_sha256": scope.descriptor_sha256,
        "terminal_artifacts_finalized": True, "completed_count": 1, "flushed_count": 1,
        "pending_count": 0, "partial_flush_gap": False, "data_kind": "TEST_SYNTHETIC",
        "native_recovery_policy": policy, "input_post_count": 1}
    payloads = {"result": json_bytes([result]), "manifest": json_bytes(manifest),
        "scope_descriptor": json_bytes(scope.to_dict()),
        "publication_wal": json_bytes({"schema_version": PUBLICATION_COMMIT_EVENT_SCHEMA,
            "receipt": receipt.to_dict(), "result": result}) + b"\n"}
    paths = {role: source_dir / (role + (".jsonl" if role == "publication_wal" else ".json"))
             for role in payloads}
    for role, raw in payloads.items():
        with paths[role].open("xb") as stream:
            stream.write(raw)
    key_path = tmp_path / "projection-audit.hex"
    with os.fdopen(create_private_file(key_path), "wb") as stream:
        stream.write(("61" * 32 + "\n").encode())
    calls = []
    def forbid_http(request):
        calls.append(request)
        raise AssertionError("projection preflight must not dispatch HTTP")
    coordinator = NativeRecoveryBatchCoordinator(policy=policy, input_post_ids=[101],
        input_snapshot_bytes=raw_input, input_path=input_path, output_dir=tmp_path / "projection_batch",
        root=tmp_path, hmac_key_path=key_path, dashboard_url="http://127.0.0.1:8080",
        data_kind="TEST_SYNTHETIC", clock_ms=lambda: 2000, test_transport=httpx.MockTransport(forbid_http),
        run_id=manifest["run_id"], publication_scope_id=scope.publication_scope_id)
    drain = {role + "_path": path for role, path in paths.items()}
    drain["activation_journal_path"] = source_dir / "absent-audit.jsonl"
    return coordinator, post, result, drain, calls, [input_path, key_path, *paths.values()]


@pytest.mark.parametrize("fault,reason", [(None, None),
    ("text", "ORIGINAL_CONTENT_PROJECTION_MISMATCH"),
    ("blocks", "ORIGINAL_CONTENT_BLOCKS_PROJECTION_MISMATCH"),
    ("image_urls", "ORIGINAL_IMAGE_URLS_PROJECTION_MISMATCH"),
    ("image_count", "ORIGINAL_IMAGE_COUNT_PROJECTION_MISMATCH"),
    ("alias", "ORIGINAL_CONTENT_ALIAS_CONFLICT")])
def test_structured_image_original_binds_to_main_projection_before_dispatch(tmp_path, fault, reason):
    coordinator, post, result, drain, calls, paths = prepare_block_projection_batch(tmp_path, fault)
    before = {str(path): path.read_bytes() for path in paths}
    report = coordinator.drain(**drain)
    assert not calls and report["budget"]["reserved_rows"] == 0
    assert report["counts"]["input_count"] == 1
    assert {str(path): path.read_bytes() for path in paths} == before
    if reason is not None:
        assert report["status"] == "NOT_EXECUTED" and reason in report["reason_codes"], report
        assert "dashboard_reference" not in report
    else:
        assert "content" not in post and result["content"] != post["content_blocks"]
        assert result["image_count"] == 1 and result["content"][0].startswith("  ")
        assert report["status"] == "COMPLETED", report
        view = read_recovery_native_view(drain["result_path"], tmp_path)
        assert view["binding_status"] == "BOUND", view
        assert view["aggregate"]["counts"]["input_count"] == 1
    assert not drain["activation_journal_path"].exists()


@pytest.mark.parametrize("comments", [[], [{"post_id": 101, "comment_id": "comment-1", "content": "원래 댓글을 보존한다"}]])
def test_native_batch_accepts_main_jsonl_without_embedded_comments_and_keeps_separate_records(tmp_path, comments):
    coordinator, post, result, drain, calls, paths = prepare_block_projection_batch(
        tmp_path, None, omit_comments=True, separate_comments=comments)
    original = {str(path): path.read_bytes() for path in paths}
    assert "comments" not in post
    assert result["comments"] == [c["content"] for c in comments]
    report = coordinator.drain(**drain)
    assert report["status"] == "COMPLETED" and not calls
    assert report["counts"]["NOT_EXECUTED"] == 1
    assert report["rows"][0]["reason_codes"] == ["CAPTURE_UNAVAILABLE"]
    assert {str(path): path.read_bytes() for path in paths} == original
    assert read_recovery_native_view(drain["result_path"], tmp_path)["binding_status"] == "BOUND"


@pytest.mark.parametrize("field,value", [("max_capture_rows", True), ("max_capture_rows", 65),
    ("max_batch_calls", -1), ("max_batch_elapsed_ms", float("inf")), ("max_batch_response_bytes", None)])
def test_policy_requires_finite_explicit_budgets(field, value):
    policy = batch_policy(); policy[field] = value
    with pytest.raises(ValueError): validate_native_batch_policy(policy)


def test_policy_exact_wire_and_copy():
    policy = batch_policy()
    checked = validate_native_batch_policy(policy)
    checked["native_config"]["model"] = "other"
    assert policy["native_config"]["model"] == "synthetic-native-model"
    policy["native_config"]["server_type"] = "vllm"
    with pytest.raises(ValueError, match="MUST_BE_EXPLICIT"): validate_native_batch_policy(policy)
    policy["native_config"].update(vllm_top_k=20, vllm_presence_penalty=1.5)
    assert validate_native_batch_policy(policy) == policy
    policy["native_config"]["headers"] = {"secret": "forbidden"}
    with pytest.raises(ValueError): validate_native_batch_policy(policy)


def test_fixed_first_n_typed_denominator_and_no_capture_replacement(tmp_path):
    p = prepare_batch(tmp_path, two=True)
    c = p["batch"]
    assert c.admitted(1, 101) and not c.admitted(2, 202)
    with pytest.raises(ValueError, match="TYPED_ROW"): c.admitted(1, "101")
    with pytest.raises(ValueError, match="INPUT_INDEX"): c.admitted(True, 101)
    assert not c.accept_committed(1, 101, None, result=p["results"][0], receipt=p["receipts"][0])
    assert not c.admitted(2, 202)
    with pytest.raises(ValueError, match="ALREADY_RECEIVED"):
        c.accept_committed(1, 101, None, result=p["results"][0], receipt=p["receipts"][0])
    before = protected(p)
    report = c.drain(**p["drain"])
    assert report["status"] == "COMPLETED", report
    assert report["counts"]["input_count"] == 2 and report["counts"]["NOT_EXECUTED"] == 2
    assert report["rows"][1]["reason_codes"] == ["CAPTURE_ADMISSION_LIMIT"]
    assert report["counts"]["client_http_invocations"] == 0
    assert not c._captures and protected(p) == before


@pytest.mark.parametrize("condition", ["manifest", "input", "wal", "scope", "audit"])
def test_full_finalized_source_gate_prevents_every_dispatch(tmp_path, condition):
    p = prepare_batch(tmp_path)
    assert accept(p)
    refs = p["bundle"]["source_refs"]
    if condition == "manifest":
        path = Path(refs["manifest"]["path"]); value = json.loads(path.read_bytes())
        value["terminal_artifacts_finalized"] = False; path.write_bytes(json_bytes(value))
    elif condition == "input":
        Path(refs["input"]["path"]).write_bytes(p["bundle"]["source_bytes"]["input"] + b"\n")
    elif condition == "wal":
        Path(refs["publication_wal"]["path"]).write_bytes(b"")
    elif condition == "scope":
        Path(refs["scope_descriptor"]["path"]).write_bytes(b"{}")
    else:
        path = Path(refs["activation_journal"]["path"]); value = json.loads(path.read_bytes())
        value["capability_hmac_sha256"] = "0" * 64; path.write_bytes(json_bytes(value)+b"\n")
    before = protected(p)
    report = p["batch"].drain(**p["drain"])
    assert report["status"] == "NOT_EXECUTED", report
    assert not p["handler"].requests and report["budget"]["reserved_rows"] == 0
    assert not p["batch"]._captures and protected(p) == before


def test_committed_capture_is_not_accepted_for_replay_or_foreign_row(tmp_path):
    p = prepare_batch(tmp_path)
    assert not p["batch"].accept_committed(1, 101, p["capture"], result=p["results"][0],
        receipt=p["receipts"][0], created=False)
    assert p["batch"].summary()["rows"][0]["reason_codes"] == ["BASE_PUBLICATION_REPLAY_NO_CAPTURE"]
    assert not p["batch"]._captures


@pytest.mark.parametrize("field", ["max_batch_calls", "max_batch_response_bytes", "max_batch_elapsed_ms"])
def test_zero_batch_budget_never_dispatches_or_invents_usage(tmp_path, field):
    policy = batch_policy(); policy[field] = 0
    p = prepare_batch(tmp_path, policy=policy); assert accept(p)
    report = p["batch"].drain(**p["drain"])
    assert not p["handler"].requests and report["counts"]["client_http_invocations"] == 0
    assert report["counts"]["input_count"] == 1 and not p["batch"]._captures
    assert report["remote_provider_dispatch_count"] is None


def test_cancel_before_finalization_is_zero_dispatch(tmp_path):
    p = prepare_batch(tmp_path, cancelled=lambda: True); assert accept(p)
    report = p["batch"].drain(**p["drain"])
    assert report["status"] == "NOT_EXECUTED" and report["reason_codes"] == ["BATCH_CANCELLED"]
    assert not p["handler"].requests and not p["batch"]._captures


def test_missing_audit_file_preserves_all_rows_and_terminal_event(tmp_path):
    p = prepare_batch(tmp_path, two=True)
    Path(p["bundle"]["source_refs"]["activation_journal"]["path"]).unlink()
    events = []
    class Bus:
        def emit(self, kind, data):
            from src.llm_batch.monitor.event_bus import _native_progress
            assert _native_progress(data) == data
            events.append((kind, deepcopy(data)))
    p["batch"]._bus = Bus()
    report = p["batch"].drain(**p["drain"])
    assert report["status"] == "COMPLETED", report
    assert report["counts"]["input_count"] == report["counts"]["NOT_EXECUTED"] == 2
    assert events[-1][0] == "native_recovery_complete"
    view = read_recovery_native_view(p["drain"]["result_path"], tmp_path)
    assert view["binding_status"] == "BOUND", view
    assert not Path(p["bundle"]["source_refs"]["activation_journal"]["path"]).exists()


def test_partial_manifest_emits_terminal_phase_without_dispatch(tmp_path):
    p = prepare_batch(tmp_path); assert accept(p)
    events = []
    class Bus:
        def emit(self, kind, data):
            from src.llm_batch.monitor.event_bus import _native_progress
            assert _native_progress(data) == data
            events.append((kind, deepcopy(data)))
    p["batch"]._bus = Bus()
    path = p["drain"]["manifest_path"]
    value = json.loads(path.read_bytes()); value["terminal_artifacts_finalized"] = False
    path.write_bytes(json_bytes(value))
    report = p["batch"].drain(**p["drain"])
    assert events[-1][0] == "native_recovery_complete" and events[-1][1]["status"] == "INCOMPLETE"
    assert report["counts"]["input_count"] == 1 and not p["handler"].requests


@pytest.mark.parametrize("stop", ["cancel", "deadline"])
def test_post_reservation_control_consumes_slot_but_sends_zero(tmp_path, stop):
    reservation = tmp_path / "batch/reservations/1.json"
    clock = lambda: 2000000 if stop == "deadline" and reservation.exists() else 2000
    cancelled = lambda: stop == "cancel" and reservation.exists()
    p = prepare_batch(tmp_path, cancelled=cancelled, clock=clock); assert accept(p)
    report = p["batch"].drain(**p["drain"])
    assert reservation.exists() and report["budget"]["reserved_rows"] == 1, report
    assert report["budget"]["refunds"] == 0 and not p["handler"].requests
    assert report["rows"][0]["guard_outcome"] is None


def test_same_id_foreign_capture_source_fails_before_provider(tmp_path):
    p = prepare_batch(tmp_path / "main")
    other = prepare_batch(tmp_path / "other", case="hold")
    p["capture"] = other["capture"]
    assert accept(p)  # typed ID만으로 내용이 같다고 판정하지 않는다.
    report = p["batch"].drain(**p["drain"])
    assert report["status"] == "NOT_EXECUTED" and report["reason_codes"] == ["BATCH_CAPTURE_SOURCE_MISMATCH"]
    assert not p["handler"].requests


def test_failed_native_has_consumed_slot_no_refund_and_no_restart(tmp_path):
    p = prepare_batch(tmp_path, policy=batch_policy(native_calls=0)); assert accept(p)
    before = protected(p)
    report = p["batch"].drain(**p["drain"])
    assert report["status"] == "INCOMPLETE", report
    assert report["rows"][0]["execution_status"] == "INCOMPLETE"
    assert report["rows"][0]["guard_outcome"] is None
    assert report["budget"]["reserved_rows"] == 1 and report["budget"]["refunds"] == 0
    assert report["budget"]["reserved_calls"] == 1 and len(p["handler"].requests) == 1
    count = len(p["handler"].requests)
    assert p["batch"].drain(**p["drain"]) == report and len(p["handler"].requests) == count
    relocated = NativeRecoveryBatchCoordinator(**{**p["kwargs"], "output_dir": tmp_path / "moved"})
    assert relocated.accept_committed(1, 101, p["capture"], result=p["results"][0], receipt=p["receipts"][0])
    refused = relocated.drain(**p["drain"])
    assert refused["status"] == "NOT_EXECUTED" and "BATCH_ALREADY_CLAIMED_NO_RESTART" in refused["reason_codes"]
    assert len(p["handler"].requests) == count and protected(p) == before


def test_actual_main_same_call_capture_batch_provider_native_guard_and_view(tmp_path):
    # 실제 process hook을 호출한 baseline은 추가 복구 예산 밖의 별도 I/O다.
    from tests.test_recovery_native_workflow import _prepare
    from expert_main import _process_post_with_optional_native_capture
    initial = _prepare(tmp_path / "initial", case="positive", max_calls=64)
    p = prepare_batch(tmp_path / "recovery")
    output, capture = _process_post_with_optional_native_capture(initial["pipeline"], initial["capture"].post,
        input_index=1, batch=p["batch"])
    initial["io"].check()
    assert capture is not None and not initial["handler"].unexpected
    public_before = output.model_dump(mode="json")
    baseline = initial["io"].finish({"scope": "INITIAL_ANALYSIS_ONLY", "data_kind": "TEST_SYNTHETIC",
        "capture_sha256": capture.capture_sha256})
    assert baseline["status"] == "COMPLETED_NATIVE_IO"
    initial_calls = len(initial["handler"].requests)
    p["capture"] = capture
    assert accept(p)
    before = protected(p)
    report = p["batch"].drain(**p["drain"])
    assert report["status"] == "COMPLETED", report
    row = report["rows"][0]
    assert row["execution_status"] == "COMPLETED_NATIVE_IO" and row["guard_outcome"] == "PUBLISH", row
    assert row["actual_external_calls"] == 0 and row["client_http_invocations"] == len(p["handler"].requests)
    assert row["client_http_invocations"] > 1 and not p["handler"].unexpected
    view = read_recovery_native_view(p["drain"]["result_path"], p["kwargs"]["root"])
    assert view["binding_status"] == "BOUND", view
    native = view["aggregate"]["rows"][0]["native"]
    assert native["guard_status"] == "PUBLISH" and view["aggregate"]["public_apply"] is False
    assert protected(p) == before and output.model_dump(mode="json") == public_before
    assert len(initial["handler"].requests) == initial_calls
    count = len(p["handler"].requests)
    assert p["batch"].drain(**p["drain"]) == report and len(p["handler"].requests) == count
    assert not p["batch"]._captures


@pytest.mark.parametrize("target", ["result", "input", "key", "anchor"])
def test_final_control_to_publication_drift_cannot_rebind_new_source(tmp_path, target):
    state = {"batch": None, "path": None, "before": None, "changed": False}

    def inspect_control():
        coordinator = state["batch"]
        if coordinator is not None and len(coordinator._processed) == 1 and not state["changed"]:
            path = (Path(coordinator._anchor_ref["path"]) if target == "anchor" else
                    coordinator._key_path if target == "key" else
                    Path(p["bundle"]["source_refs"][target]["path"]))
            state.update(path=path, before=path.read_bytes(), changed=True)
            # Same JSON meaning, different protected raw bytes. This happens after
            # the final controller's source read, so the publication check is needed.
            path.write_bytes(state["before"] + b" ")
        return False

    p = prepare_batch(tmp_path, cancelled=inspect_control)
    state["batch"] = p["batch"]
    report = p["batch"].drain(**p["drain"])
    assert state["changed"] and not p["handler"].requests
    expected = {"result": "BATCH_PROTECTED_SOURCE_CHANGED", "input": "BATCH_INPUT_DRIFT",
                "key": "BATCH_KEY_DRIFT", "anchor": "BATCH_ANCHOR_CHANGED"}[target]
    assert expected in report["reason_codes"] and "dashboard_reference" not in report, report
    companion = p["drain"]["result_path"].with_name(p["drain"]["result_path"].stem + "_recovery_native_view.json")
    assert not companion.exists()
    # Restoring the bytes cannot erase a detected failure or enable a same-object retry.
    state["path"].write_bytes(state["before"])
    with pytest.raises(NativeRecoveryBatchError, match=expected):
        p["batch"].drain(**p["drain"])
    assert not p["handler"].requests


@pytest.mark.parametrize("fault", ["result_drift", "cancel", "deadline"])
def test_completed_native_row_preserved_but_final_batch_failure_is_not_lost(tmp_path, fault):
    state = {"armed": False}
    clock = lambda: 2000000 if state["armed"] and fault == "deadline" else 2000
    cancelled = lambda: state["armed"] and fault == "cancel"
    p = prepare_batch(tmp_path, clock=clock, cancelled=cancelled)
    before = protected(p)
    assert accept(p)
    events = []

    class FinalBoundary:
        def emit(self, kind, payload):
            events.append((kind, deepcopy(payload)))
            if kind == "native_recovery_progress" and payload["completed"] == payload["total"] == 1:
                state["armed"] = True
                if fault == "result_drift":
                    path = p["drain"]["result_path"]
                    path.write_bytes(before["result"] + b" ")

    p["batch"]._bus = FinalBoundary()
    report = p["batch"].drain(**p["drain"])
    assert state["armed"] and report["status"] == "INCOMPLETE", report
    row = report["rows"][0]
    assert row["execution_status"] == "COMPLETED_NATIVE_IO" and row["guard_outcome"] == "PUBLISH", row
    assert row["client_http_invocations"] == len(p["handler"].requests) > 1
    assert row["actual_external_calls"] == 0 and not p["handler"].unexpected
    assert events[-1][0] == "native_recovery_complete" and events[-1][1]["status"] == "INCOMPLETE"
    assert report["budget"]["refunds"] == 0 and not p["batch"]._captures
    if fault == "result_drift":
        assert "BATCH_PROTECTED_SOURCE_CHANGED" in report["reason_codes"]
        assert "dashboard_reference" not in report
        assert read_recovery_native_view(p["drain"]["result_path"], tmp_path)["binding_status"] == "MISSING"
        return
    reason = "BATCH_CANCELLED" if fault == "cancel" else "BATCH_TIME_EXHAUSTED"
    assert reason in report["reason_codes"] and protected(p) == before
    stored = json.loads(Path(report["report_ref"]["path"]).read_bytes())
    assert stored["status"] == "INCOMPLETE" and reason in stored["reason_codes"]
    assert stored["budget"]["time_scope"] == "THROUGH_FINAL_DRAIN_CONTROL_OBSERVATION"
    assert stored["budget"]["report_publication_io_in_time_scope"] is False
    if fault == "deadline":
        assert stored["budget"]["observed_elapsed_ms"] > p["kwargs"]["policy"]["max_batch_elapsed_ms"]
    view = read_recovery_native_view(p["drain"]["result_path"], tmp_path)
    assert view["binding_status"] == "BOUND", view
    aggregate = view["aggregate"]
    assert aggregate["batch_report_ref"] == report["report_ref"]
    assert aggregate["batch"]["status"] == "INCOMPLETE" and reason in aggregate["batch"]["reason_codes"]
    assert aggregate["batch"]["budget"] == stored["budget"]
    assert aggregate["rows"][0]["native"]["guard_status"] == "PUBLISH"
    assert aggregate["counts"]["client_http_invocations"] == row["client_http_invocations"]
    calls = len(p["handler"].requests)
    assert p["batch"].drain(**p["drain"]) == report and len(p["handler"].requests) == calls
