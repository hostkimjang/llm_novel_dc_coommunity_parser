"""native aggregate의 저장→실제 API 결속과 실패/분모 보존. 외부 전송은 HTTP mock만 쓴다."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from src.llm_batch.monitor import recovery_native_view as view


def raw(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw(value))
    return path


def simple(tmp_path):
    items = [{"post_id": 11, "title": "원래 행"}, {"post_id": "11", "title": "문자열 ID"},
             {"post_id": 12, "title": "불완전 행"}]
    policy = {"mode": "ON", "max_capture_rows": 1}
    output = put(tmp_path / "result.json", items)
    manifest = put(tmp_path / "result_manifest.json", {"run_id": "run-current", "publication_scope_id": "a" * 64,
        "output_file": str(output), "terminal_artifacts_finalized": True, "input_post_count": 3,
        "completed_count": 3, "flushed_count": 3, "pending_count": 0, "partial_flush_gap": False,
        "publication_input_snapshot_sha256": "b" * 64, "native_recovery_policy": policy})
    rows = [{"input_index": i, "post_id": item["post_id"], "capture_status": "NOT_ADMITTED",
        "execution_status": state, "reason_codes": ["CAPTURE_UNAVAILABLE"],
        "provider_report_path": None, "native_receipt_path": None, "native_output_dir": None}
        for i, (item, state) in enumerate(zip(items, ["NOT_EXECUTED", "SKIPPED", "INCOMPLETE"]), 1)]
    return output, manifest, items, policy, rows


def stored_batch(tmp_path, output, manifest_path, policy, records, *, reason="BATCH_CANCELLED", reserved=0):
    """현재 batch wire 형식으로 마지막 제어 결과를 독립 저장한다. 실행기를 부르지 않는다."""
    manifest = json.loads(manifest_path.read_bytes())
    records = [{**row, "remote_provider_dispatch_count": None, **view.FLAGS} for row in records]
    counts = {state: sum(r["execution_status"] == state for r in records)
              for state in ("NOT_EXECUTED", "RUNNING", "COMPLETED_NATIVE_IO", "INCOMPLETE")}
    for key in ("client_http_invocations", "actual_external_calls"):
        counts[key] = None if any(r[key] is None for r in records) else sum(r[key] for r in records)
    reference = lambda path: {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                              "bytes": len(path.read_bytes())}
    report = {"schema_version": "recovery_native_batch_v1", "status": "INCOMPLETE",
        "base_run": {"run_id": manifest["run_id"], "publication_scope_id": manifest["publication_scope_id"],
            "input_count": len(records), "input_order_sha256": view.canonical_sha256([r["post_id"] for r in records]),
            "input_raw_sha256": manifest["publication_input_snapshot_sha256"],
            "result": reference(output), "manifest": reference(manifest_path)},
        "policy": policy, "policy_sha256": view.canonical_sha256(policy), "data_kind": "TEST_SYNTHETIC",
        "rows": records, "counts": {"input_count": len(records), **counts},
        "budget": {"reserved_rows": reserved, "reserved_calls": reserved * 32,
            "reserved_response_bytes": reserved * 4096, "reserved_elapsed_ms": reserved * 100,
            "observed_elapsed_ms": 101, "refunds": 0,
            "time_scope": "THROUGH_FINAL_DRAIN_CONTROL_OBSERVATION",
            "report_publication_io_in_time_scope": False, "total_ram_bytes": None},
        "reason_codes": [reason], "remote_provider_dispatch_count": None, **view.FLAGS}
    report["receipt_sha256"] = view.canonical_sha256(report)
    path = put(tmp_path / "batch.json", report)
    return reference(path)


@pytest.mark.parametrize("fault", ["none", "raw_change", "typed_row", "run", "counts", "budget", "policy"])
def test_batch_report_ref_binds_final_control_and_rejects_resealed_mismatch(tmp_path, fault):
    output, manifest, items, policy, rows = simple(tmp_path)
    policy.update(max_batch_calls=32, max_batch_response_bytes=4096, max_batch_elapsed_ms=100)
    manifest_value = json.loads(manifest.read_bytes()); manifest_value["native_recovery_policy"] = policy
    put(manifest, manifest_value)
    for row in rows: row["execution_status"] = "NOT_EXECUTED"
    records = [{**row, "provider_report_ref": None, "native_receipt_ref": None, "guard_outcome": None,
                "client_http_invocations": 0, "actual_external_calls": 0} for row in rows]
    reference = stored_batch(tmp_path, output, manifest, policy, records)
    path = Path(reference["path"])
    if fault != "none":
        report = json.loads(path.read_bytes())
        if fault == "typed_row": report["rows"][0]["post_id"] = "11"
        elif fault == "run": report["base_run"]["run_id"] = "foreign"
        elif fault == "counts": report["counts"]["NOT_EXECUTED"] = 2
        elif fault == "budget": report["budget"]["reserved_calls"] = 33
        elif fault == "policy": report["policy_sha256"] = "c" * 64
        report["receipt_sha256"] = view.canonical_sha256({k:v for k,v in report.items() if k != "receipt_sha256"})
        payload = raw(report) + (b" " if fault == "raw_change" else b"")
        path.write_bytes(payload)
        if fault != "raw_change": reference.update(sha256=hashlib.sha256(payload).hexdigest(), bytes=len(payload))
        with pytest.raises(ValueError):
            view.publish_recovery_native_view(output, manifest, root=tmp_path, policy=policy, rows=rows, batch_report_ref=reference)
        assert view.read_recovery_native_view(output, tmp_path)["binding_status"] == "MISSING"
        return
    source_before = (output.read_bytes(), manifest.read_bytes(), path.read_bytes())
    view.publish_recovery_native_view(output, manifest, root=tmp_path, policy=policy, rows=rows, batch_report_ref=reference)
    attached = view.read_recovery_native_view(output, tmp_path)
    assert attached["binding_status"] == "BOUND"
    assert attached["aggregate"]["batch"]["status"] == "INCOMPLETE"
    assert attached["aggregate"]["batch"]["reason_codes"] == ["BATCH_CANCELLED"]
    assert attached["aggregate"]["batch"]["budget"]["observed_elapsed_ms"] == 101
    assert attached["aggregate"]["counts"]["states"]["NOT_EXECUTED"] == 3
    assert (output.read_bytes(), manifest.read_bytes(), path.read_bytes()) == source_before
    path.write_bytes(path.read_bytes() + b" ")
    assert view.read_recovery_native_view(output, tmp_path)["binding_status"] == "INVALID"


def test_whole_typed_denominator_unknown_and_readonly_api(tmp_path, monkeypatch):
    output, manifest, items, policy, rows = simple(tmp_path)
    before = (output.read_bytes(), manifest.read_bytes())
    reference = view.publish_recovery_native_view(output, manifest, root=tmp_path, policy=policy, rows=rows, input_posts=items)
    attached = view.read_recovery_native_view(output, tmp_path)
    assert attached["binding_status"] == "BOUND"
    assert [r["post_id"] for r in attached["aggregate"]["rows"]] == [11, "11", 12]
    assert attached["aggregate"]["counts"]["input_count"] == 3
    assert attached["aggregate"]["counts"]["client_http_invocations"] is None
    assert attached["aggregate"]["counts"]["actual_external_call_count"] is None
    assert view.bind_recovery_native_view_row(attached, items[1])["row"]["input_index"] == 2
    assert view.bind_recovery_native_view_row(attached, {**items[0], "post_id": True})["binding_status"] == "INVALID"
    from src.llm_batch.monitor import server
    monkeypatch.setattr(server, "_OUT_DIR", tmp_path)
    from src.llm_batch.runtime import recovery_native_workflow
    monkeypatch.setattr(recovery_native_workflow, "run_native_recovery", lambda *a, **k: pytest.fail("GET must not execute"))
    live = server._to_live_detail(items[0], output_path=output)
    history = server._history_item(items[0], SimpleNamespace(path=output, manifest=manifest))
    assert live["recovery_native_execution"] == history["recovery_native_execution"]
    assert history["recovery_native_execution"]["row"]["execution_status"] == "NOT_EXECUTED"
    assert view.publish_recovery_native_view(output, manifest, root=tmp_path, policy=policy, rows=rows) == reference
    assert (output.read_bytes(), manifest.read_bytes()) == before
    with pytest.raises(ValueError):
        view.publish_recovery_native_view(output, manifest, root=tmp_path, policy=policy, rows=rows[:-1])
    swapped = [rows[1], rows[0], rows[2]]
    with pytest.raises(ValueError):
        view.publish_recovery_native_view(output, manifest, root=tmp_path, policy=policy, rows=swapped)


def test_replayed_owner_and_new_row_keep_manifest_mismatch_but_bind_current_native_export(tmp_path, monkeypatch):
    from src.llm_batch.monitor import server
    from src.llm_batch.ledger.publication_commit import compute_publication_decision_commit, PUBLICATION_COMMIT_EVENT_SCHEMA
    from tests.recovery_provider_fixtures import build_recovery_provider_fixture
    bundle = build_recovery_provider_fixture(tmp_path / "base")
    items = deepcopy(bundle["results"])
    assert len(items) == 2
    scope = bundle["manifest"]["publication_scope_id"]
    items[0].setdefault("run_meta", {}).update(run_id="prior-wal-owner", publication_scope_id=scope)
    items[1].setdefault("run_meta", {}).update(run_id="current-export", publication_scope_id=scope)
    events = []
    for index, row in enumerate(items, 1):
        commit = compute_publication_decision_commit(row, publication_scope_id=scope,
            attempt_run_id=row["run_meta"]["run_id"], input_index=index, post_id=row["post_id"])
        events.append({"schema_version": PUBLICATION_COMMIT_EVENT_SCHEMA, "receipt": commit.to_dict(), "result": row})
    output = Path(bundle["source_refs"]["result"]["path"])
    manifest_path = output.with_name(output.stem + "_manifest.json")
    wal = Path(bundle["source_refs"]["publication_wal"]["path"])
    policy = {"mode": "ON", "max_capture_rows": 1}
    put(output, items)
    put(manifest_path, {**bundle["manifest"], "run_id": "current-export", "output_file": str(output),
        "input_post_count": 2, "native_recovery_policy": policy})
    wal.write_bytes(b"".join(raw(event) + b"\n" for event in events))
    original = {p: p.read_bytes() for p in (output, manifest_path, wal)}
    rows = [{"input_index": index, "post_id": item["post_id"], "capture_status": "UNAVAILABLE",
        "execution_status": "NOT_EXECUTED", "reason_codes": [reason], "provider_report_path": None,
        "native_receipt_path": None, "native_output_dir": None}
        for index, (item, reason) in enumerate(zip(items,
            ["BASE_PUBLICATION_REPLAY_NO_CAPTURE", "CAPTURE_UNAVAILABLE"]), 1)]
    view.publish_recovery_native_view(output, manifest_path, root=tmp_path, policy=policy, rows=rows)
    record = SimpleNamespace(path=output, manifest=manifest_path,
        public={"filename": output.name, "run_id": "current-export"})
    monkeypatch.setattr(server, "_OUT_DIR", tmp_path)
    monkeypatch.setattr(server, "_LOG_DIR", tmp_path)
    monkeypatch.setattr(server, "_history_record", lambda key: (record, None))
    summary = json.loads(server._history_detail("current", 0, 20, True).body)
    assert summary["run_manifest"]["binding_status"] == "MISMATCH"
    assert summary["run_manifest"]["reason_codes"] == ["RUN_ID_MISMATCH"]
    assert summary["recovery_native_export_manifest"]["binding_status"] == "BOUND"
    assert summary["recovery_native_execution"]["aggregate"]["counts"]["input_count"] == 2
    for index, item in enumerate(items):
        live = server._to_live_detail(item, output_path=output)
        history = server._history_item(item, record)
        assert live["run_manifest"]["binding_status"] == ("MISMATCH" if index == 0 else "BOUND")
        assert live["recovery_native_execution"] == history["recovery_native_execution"]
        assert live["recovery_native_export_manifest"] == history["recovery_native_export_manifest"]
        assert live["recovery_native_export_manifest"]["summary"]["run_id"] == "current-export"
        assert live["run_meta"]["run_id"] == item["run_meta"]["run_id"]
    assert all(path.read_bytes() == content for path, content in original.items())


@pytest.mark.parametrize("fault", ["run", "scope", "id_type", "row", "count", "authority", "escape", "self_sha"])
def test_resealed_or_foreign_aggregate_cannot_show_success(tmp_path, fault):
    output, manifest, items, policy, rows = simple(tmp_path)
    ref = view.publish_recovery_native_view(output, manifest, root=tmp_path, policy=policy, rows=rows)
    target = Path(ref["path"]); value = json.loads(target.read_bytes())
    if fault == "run": value["base_run"]["run_id"] = "other-run"
    elif fault == "scope": value["base_run"]["publication_scope_id"] = "c" * 64
    elif fault == "id_type": value["rows"][0]["post_id"] = "11"
    elif fault == "row": value["rows"][0]["result_sha256"] = "c" * 64
    elif fault == "count": value["counts"]["client_http_invocations"] = 0
    elif fault == "authority": value["public_apply"] = True
    elif fault == "escape": value["base_run"]["result"]["path"] = str(tmp_path / ".." / "result.json")
    if fault != "self_sha": value["aggregate_sha256"] = view.canonical_sha256({k:v for k,v in value.items() if k != "aggregate_sha256"})
    else: value["aggregate_sha256"] = "0" * 64
    put(target, value)
    assert view.read_recovery_native_view(output, tmp_path)["binding_status"] == "INVALID"


def test_atomic_publish_failure_does_not_expose_partial_companion(tmp_path, monkeypatch):
    output, manifest, items, policy, rows = simple(tmp_path)
    original = view._read
    def failed(path, root, limit):
        if str(path).endswith(".pending"): raise OSError("LOCAL_READBACK_FAILURE")
        return original(path, root, limit)
    monkeypatch.setattr(view, "_read", failed)
    with pytest.raises(OSError): view.publish_recovery_native_view(output, manifest, root=tmp_path, policy=policy, rows=rows)
    assert not output.with_name(output.stem + "_recovery_native_view.json").exists()
    assert output.read_bytes() == raw(items)


@pytest.mark.parametrize("field,value", [("completed_count", 2), ("flushed_count", 2),
    ("pending_count", 1), ("partial_flush_gap", True), ("input_post_count", True)])
def test_terminal_title_does_not_override_incomplete_base_manifest(tmp_path, field, value):
    output, manifest, items, policy, rows = simple(tmp_path)
    payload = json.loads(manifest.read_bytes()); payload[field] = value; put(manifest, payload)
    with pytest.raises(ValueError):
        view.publish_recovery_native_view(output, manifest, root=tmp_path, policy=policy, rows=rows)
    assert view.read_recovery_native_view(output, tmp_path)["binding_status"] == "MISSING"


def test_real_http_fixture_native_guard_saved_result_and_api_tamper_boundary(tmp_path, monkeypatch):
    from src.llm_batch.agentic_pipeline import AgenticPipeline
    from src.llm_batch.measurement.recovery_provider_contract import build_recovery_provider_plan, bind_recovery_provider_plan
    from src.llm_batch.measurement.recovery_provider_readback import build_provider_report
    from src.llm_batch.runtime import recovery_native_io
    from src.llm_batch.runtime.recovery_native_workflow import run_native_recovery
    from tests.recovery_native_fixtures import (build_native_base_fixture, build_native_capture,
        NativeHTTPFixture, store_native_provider_evidence, source_bytes, ENDPOINTS)
    monkeypatch.setattr(recovery_native_io, "NATIVE_JOB_REGISTRY_ROOT", tmp_path / "registry")
    bundle = build_native_base_fixture(tmp_path / "base")
    policy = {"mode": "ON", "max_capture_rows": 1, "max_batch_calls": 32,
              "max_batch_response_bytes": 4096, "max_batch_elapsed_ms": 100}
    # 신규 fixture의 final manifest를 dispatch 전에 확정하고 기존 정식 binder로 다시 결속한다.
    manifest = {**bundle["manifest"], "input_post_count": 1, "native_recovery_policy": policy}
    manifest_path = Path(bundle["source_refs"]["result"]["path"]).with_name("result_manifest.json")
    payload = raw(manifest); manifest_path.write_bytes(payload)
    bundle["source_bytes"]["manifest"] = payload
    bundle["source_refs"]["manifest"] = {"path": str(manifest_path), "sha256": hashlib.sha256(payload).hexdigest(), "bytes": len(payload)}
    args = {**bundle["build_kwargs"], "source_refs": bundle["source_refs"], "source_bytes": bundle["source_bytes"]}
    bundle["plan"] = build_recovery_provider_plan(**args)
    bundle["bound"] = bind_recovery_provider_plan(bundle["plan"], hmac_key=bundle["hmac_key"])
    handler = NativeHTTPFixture(bundle["native_case"])
    store_native_provider_evidence(bundle, handler)
    pipeline = AgenticPipeline(llm=object(), mcp=object(), output_dir=tmp_path / "capture", native_recovery=True)
    capture = build_native_capture(pipeline, bundle)["capture"]
    protected = source_bytes(bundle)
    receipt = run_native_recovery(bundle["bound"], capture,
        policy={"max_calls": 32, "max_elapsed_ms": 180000, "request_timeout_ms": 30000,
                "max_response_bytes": 2 * 1024 * 1024, "max_total_response_bytes": 64 * 1024 * 1024},
        endpoints=ENDPOINTS, model="synthetic-native-model", max_tokens=32768,
        test_transport=httpx.MockTransport(handler), clock_ms=lambda: 2000)
    assert receipt["status"] == "COMPLETED_NATIVE_IO", receipt
    provider = build_provider_report(bundle["bound"])
    directory = bundle["bound"].output_dir
    provider_path = put(directory / "reports/provider.json", provider)
    native_path = put(directory / "reports/native.json", receipt)
    output = Path(bundle["source_refs"]["result"]["path"])
    rows = [{"input_index": 1, "post_id": 101, "capture_status": "CAPTURED", "execution_status": "COMPLETED_NATIVE_IO",
        "reason_codes": [], "provider_report_path": str(provider_path), "native_receipt_path": str(native_path),
        "native_output_dir": str(directory)}]
    reference = lambda path: {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                              "bytes": len(path.read_bytes())}
    batch_ref = stored_batch(tmp_path, output, manifest_path, policy, [{**rows[0],
        "provider_report_ref": reference(provider_path), "native_receipt_ref": reference(native_path),
        "guard_outcome": receipt["native_result"]["guard_status"],
        "client_http_invocations": receipt["total_client_http_invocations"],
        "actual_external_calls": receipt["total_actual_external_calls"]}], reason="BATCH_TIME_EXHAUSTED", reserved=1)
    ref = view.publish_recovery_native_view(output, manifest_path, root=tmp_path, policy=policy, rows=rows, batch_report_ref=batch_ref)
    from src.llm_batch.monitor import server
    monkeypatch.setattr(server, "_OUT_DIR", tmp_path)
    live = server._to_live_detail(bundle["result"], output_path=output)
    history = server._history_item(bundle["result"], SimpleNamespace(path=output, manifest=manifest_path))
    assert live["recovery_native_execution"] == history["recovery_native_execution"]
    bound_view = history["recovery_native_execution"]
    assert bound_view["binding_status"] == "BOUND"
    row = bound_view["row"]
    assert row["native"]["guard_status"] == bundle["native_case"]["expected_outcome"]
    assert row["provider"]["guard_status"] == "GUARD_NOT_EVALUATED"
    assert row["native"]["actual_external_call_count"] == 0
    assert row["native"]["client_http_invocations"] == len(handler.requests)
    assert bound_view["aggregate"]["counts"]["client_http_invocations"] == len(handler.requests)
    assert bound_view["aggregate"]["batch"]["status"] == "INCOMPLETE"
    assert bound_view["aggregate"]["batch"]["reason_codes"] == ["BATCH_TIME_EXHAUSTED"]
    assert bound_view["aggregate"]["batch"]["counts"]["COMPLETED_NATIVE_IO"] == 1
    # 실제 native 호출이 여러 번 발생한 뒤 그 receipt를 잃었다고 가정한다.
    # 알려진 provider 1회로 전체를 축소해서는 안 된다.
    unknown = {**row, "execution_status": "INCOMPLETE", "native": None, "native_receipt_ref": None}
    assert unknown["provider"]["client_http_invocations"] == 1
    missing_native = view._counts([unknown])
    assert missing_native["client_http_invocations"] is None
    assert missing_native["actual_external_call_count"] is None
    provider_only = {**unknown, "execution_status": "PROVIDER_EVIDENCE_STORED"}
    assert view._counts([provider_only])["client_http_invocations"] == 1
    assert source_bytes(bundle) == protected
    # Node는 이 실제 API 응답을 그대로 소비할 수 있다. root의 새 증거 경로에서만 배타 저장한다.
    if os.environ.get("NATIVE_UI_READBACK"):
        with Path(os.environ["NATIVE_UI_READBACK"]).open("xb") as stream:
            stream.write(raw({"live": live, "history": history}))
    before_calls = len(handler.requests)
    for selected in (native_path, provider_path, Path(batch_ref["path"]), *(Path(r["path"]) for r in row["native"]["protected_refs"])):
        saved = selected.read_bytes()
        try:
            selected.write_bytes(saved + b" ")
            assert view.read_recovery_native_view(output, tmp_path)["binding_status"] == "INVALID"
        finally: selected.write_bytes(saved)
    assert len(handler.requests) == before_calls and Path(ref["path"]).is_file()
