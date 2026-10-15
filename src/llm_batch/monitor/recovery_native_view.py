"""native 집계의 배타 발행과 파일·base 결속 판독. GET은 실행기나 키를 쓰지 않는다."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import uuid

from ..measurement.recovery_execution_contract import canonical_sha256
from ..measurement.recovery_execution_readback import read_strict_json
from .recovery_view import _read, _read_ref, _ref, _safe
from .recovery_provider_view import _check_report, bind_recovery_provider_view_row

SCHEMA = "recovery_native_dashboard_aggregate_v1"
SCOPE = "FILE_AND_BASE_BINDING_ONLY"
LIMIT = 32 * 1024 * 1024
SOURCE_LIMIT = 128 * 1024 * 1024
FLAGS = {"public_apply": False, "publication_authority": False, "central_db_write": False,
         "actual_quality_evaluated": False, "formal_kpi_status": "NOT_ESTIMABLE"}
STATES = {"COMPLETED_NATIVE_IO", "PROVIDER_EVIDENCE_STORED", "NOT_EXECUTED", "SKIPPED",
          "INCOMPLETE", "NOT_AVAILABLE", "ERROR"}


def _require(ok):
    if not ok:
        raise ValueError("NATIVE_VIEW_BINDING_INVALID")


def _sha(value):
    return type(value) is str and re.fullmatch(r"[a-f0-9]{64}", value) is not None


def _same(a, b):
    return type(a) is type(b) and a == b


def _identity(value):
    _require(type(value) in (str, int) and (type(value) is int or bool(value)))
    return type(value).__name__, value


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _json(raw):
    return read_strict_json(raw, maximum_bytes=SOURCE_LIMIT)


def _path(output):
    return output.with_name(output.stem + "_recovery_native_view.json")


def _nullable_count(value):
    _require(value is None or type(value) is int and value >= 0)
    return value


def _codes(value):
    _require(type(value) is list and len(value) <= 128 and all(
        type(v) is str and re.fullmatch(r"[A-Z][A-Z0-9_]{0,127}", v) for v in value))
    return value


def _pin_relative(ref, directory, root):
    _require(type(ref) is dict and set(ref) == {"path", "sha256", "bytes"}
             and type(ref["path"]) is str and _sha(ref["sha256"]))
    relative = Path(ref["path"])
    _require(not relative.is_absolute() and relative.parts and ".." not in relative.parts)
    path = _safe(directory / relative, root)
    path.relative_to(directory)
    pinned = {**ref, "path": str(path)}
    raw = _read_ref(pinned, root, LIMIT)
    return pinned, raw


def _check_false(value):
    _require(type(value) is dict and all(_same(value.get(k), v) for k, v in FLAGS.items()))


def _native_summary(receipt, provider, directory, root):
    _require(type(receipt) is dict and receipt.get("schema_version") == "recovery_native_io_receipt_v1")
    _require(type(receipt.get("status")) is str and re.fullmatch(r"[A-Z][A-Z0-9_]{0,127}", receipt["status"])
             and type(receipt.get("native_counts_complete")) is bool
             and receipt.get("time_scope") == "THROUGH_TERMINAL_DURABLE_READBACK"
             and receipt.get("finalization_write_in_time_scope") is False)
    _require(_sha(receipt.get("receipt_sha256")) and receipt["receipt_sha256"] ==
             canonical_sha256({k: v for k, v in receipt.items() if k != "receipt_sha256"}))
    _require(all(receipt.get(k) is False for k in ("public_apply", "publication_authority", "central_db_write")))
    _require(receipt.get("remote_dispatch_count") is None and receipt.get("remote_dispatch_status") == "UNKNOWN")
    binding = receipt.get("binding")
    _require(type(binding) is dict and set(binding) == {
        "source_sha256", "config_sha256", "base_sha256", "context_sha256", "upstream_sha256"}
        and all(_sha(v) for v in binding.values()))
    _require(binding["base_sha256"] == canonical_sha256(provider["base"])
             and binding["upstream_sha256"] == canonical_sha256(provider))
    _require(receipt.get("transport_mode") in {"TEST_DOUBLE", "HTTPX_SINGLE_REQUEST"})
    calls = _nullable_count(receipt.get("total_client_http_invocations"))
    actual = _nullable_count(receipt.get("total_actual_external_calls"))
    _require(actual == 0 if receipt["transport_mode"] == "TEST_DOUBLE" else actual == calls)
    budget, upstream = receipt.get("budget"), receipt.get("upstream_counts")
    _require(type(upstream) is dict and upstream.get("transport_invocations") == provider["client_http_invocations"]
             and upstream.get("actual_external_calls") == provider["actual_external_call_count"])
    if receipt.get("native_counts_complete") is True:
        _require(type(budget) is dict and type(budget.get("transport_invocations")) is int
                 and budget["transport_invocations"] >= 0 and calls == upstream["transport_invocations"] + budget["transport_invocations"])
    else:
        _require(calls is None)
    refs, outcome, scope, result_ref = [], None, None, None
    if receipt.get("status") == "COMPLETED_NATIVE_IO":
        _require(receipt.get("native_counts_complete") is True)
        result = receipt.get("native_result")
        _check_false(result)
        _require(result.get("schema_version") == "recovery_native_result_v1"
                 and result.get("binding") == binding and result.get("base") == provider["base"]
                 and result.get("data_kind") == provider["data_kind"] and _sha(result.get("capture_sha256")))
        _require(canonical_sha256(result.get("config")) == binding["config_sha256"]
                 and canonical_sha256(result.get("source_files_sha256")) == binding["source_sha256"])
        _require(type(result.get("config")) is dict and type(result.get("source_files_sha256")) is dict
                 and result["source_files_sha256"] and all(type(k) is str and _sha(v)
                    for k, v in result["source_files_sha256"].items()))
        result_ref, raw = _pin_relative(receipt["native_result_ref"], directory / "native", root)
        _require(_canonical(_json(raw)) == _canonical(result))
        from ..ledger.publication_commit import (PublicationScopeDescriptor, build_publication_scope_descriptor,
             validate_publication_result_commit, PUBLICATION_COMMIT_EVENT_SCHEMA)
        descriptor = PublicationScopeDescriptor.from_dict(result["publication_scope"])
        expected = build_publication_scope_descriptor(input_file_sha256=provider["base"]["input_raw_sha256"],
             post_ids=[provider["base"]["post_id"]], config_hash=canonical_sha256({"binding": binding,
             "policy": result["config"]["policy"]}), release_fingerprint=binding["source_sha256"])
        _require(descriptor.to_dict() == expected.to_dict()
                 and descriptor.publication_scope_id != provider["base"]["publication_scope_id"])
        row, commit = result["result"], result["publication_commit"]
        _require(type(row) is dict and _same(row.get("post_id"), provider["base"]["post_id"]))
        validate_publication_result_commit(row, commit, expected_scope_id=descriptor.publication_scope_id,
             expected_input_index=1, expected_post_id=provider["base"]["post_id"])
        _require(result.get("guard_status") == commit["outcome"] and commit["outcome"] in {"PUBLISH", "HOLD"})
        file_refs = result.get("publication_files")
        _require(type(file_refs) is list and len(file_refs) == 2 and
                 [Path(r["path"]).as_posix() for r in file_refs] ==
                 ["native/publication_commits.jsonl", "native/publication_commits.jsonl.scope.json"])
        wal_ref, wal_raw = _pin_relative(file_refs[0], directory, root)
        scope_ref, scope_raw = _pin_relative(file_refs[1], directory, root)
        _require(_json(scope_raw) == descriptor.to_dict() and wal_raw.endswith(b"\n") and len(wal_raw.splitlines()) == 1)
        event = _json(wal_raw.strip())
        _require(event.get("schema_version") == PUBLICATION_COMMIT_EVENT_SCHEMA
                 and event.get("result") == row and event.get("receipt") == commit)
        # 원본 native 원장은 실행/수리하지 않는다. 현재 파일의 바이트를 companion에 고정한다.
        refs = [wal_ref, scope_ref]
        for name in ("native_journal.jsonl", "native_journal.jsonl.anchor.json"):
            path = _safe(directory / "native" / name, root)
            refs.append(_ref(path, _read(path, root, LIMIT)))
        outcome, scope = commit["outcome"], descriptor.publication_scope_id
    else:
        _require(receipt.get("native_result") is None)
        if receipt.get("native_result_ref") is not None:
            # terminal 저장 뒤 finalization 실패일 수 있다. 파일은 고정하되 guard는 null이다.
            result_ref, _ = _pin_relative(receipt["native_result_ref"], directory / "native", root)
    return {"status": receipt["status"], "guard_status": outcome, "publication_scope_id": scope,
            "data_kind": provider["data_kind"], "transport_mode": receipt["transport_mode"],
            "client_http_invocations": calls, "actual_external_call_count": actual,
            "remote_dispatch_count": None, "remote_dispatch_status": "UNKNOWN", "price": None,
            "native_counts_complete": receipt.get("native_counts_complete"),
            "receipt_sha256": receipt["receipt_sha256"], "result_ref": result_ref, "protected_refs": refs,
            "time_scope": receipt.get("time_scope"),
            "finalization_write_in_time_scope": receipt.get("finalization_write_in_time_scope"), **FLAGS}


def _base_files(output, manifest_path, root, policy):
    result_raw, manifest_raw = _read(output, root, SOURCE_LIMIT), _read(manifest_path, root, LIMIT)
    items, manifest = _json(result_raw), _json(manifest_raw)
    _require(type(items) is list and 0 < len(items) <= 10000 and all(type(i) is dict for i in items))
    ids = [_identity(i.get("post_id")) for i in items]
    _require(len(ids) == len(set(ids)) and type(manifest) is dict
             and manifest.get("terminal_artifacts_finalized") is True
             and type(manifest.get("run_id")) is str and bool(manifest["run_id"])
             and _sha(manifest.get("publication_scope_id"))
             and _sha(manifest.get("publication_input_snapshot_sha256"))
             and _safe(Path(manifest["output_file"]), root) == output
             and type(manifest.get("input_post_count")) is int and manifest["input_post_count"] == len(items)
             and type(manifest.get("completed_count")) is int and manifest["completed_count"] == len(items)
             and type(manifest.get("flushed_count")) is int and manifest["flushed_count"] == len(items)
             and type(manifest.get("pending_count")) is int and manifest["pending_count"] == 0
             and manifest.get("partial_flush_gap") is False
             and type(policy) is dict and manifest.get("native_recovery_policy") == policy)
    if manifest.get("native_recovery_view_path") is not None:
        _require(_safe(Path(manifest["native_recovery_view_path"]), root) == _safe(_path(output), root))
    return items, manifest, _ref(output, result_raw), _ref(manifest_path, manifest_raw)


def _row(source, item, index, base_run, root):
    _require(type(source) is dict and set(source).issubset({"input_index", "post_id", "capture_status",
        "execution_status", "reason_codes", "provider_report_path", "native_receipt_path", "native_output_dir", "base"}))
    _require(type(source.get("input_index")) is int and source["input_index"] == index
             and _same(source.get("post_id"), item.get("post_id")) and source.get("execution_status") in STATES)
    capture = source.get("capture_status")
    _require(type(capture) is str and re.fullmatch(r"[A-Z][A-Z0-9_]{0,127}", capture))
    row = {"input_index": index, "post_id": item["post_id"], "result_sha256": canonical_sha256(item),
        "capture_status": capture, "execution_status": source["execution_status"],
        "reason_codes": _codes(source.get("reason_codes")), "base": None,
        "provider_report_ref": None, "provider": None, "native_receipt_ref": None,
        "native_output_dir": None, "native": None, **FLAGS}
    if source.get("provider_report_path") is not None:
        path = _safe(Path(source["provider_report_path"]), root)
        raw = _read(path, root, LIMIT); report = _json(raw)
        _require(type(report) is dict and type(report.get("base")) is dict)
        base = report["base"]; _check_report(report, base)
        _require(base.get("export_run_id") == base_run["run_id"]
                 and base.get("publication_scope_id") == base_run["publication_scope_id"]
                 and _same(base.get("input_index"), index) and base.get("input_count") == base_run["input_count"]
                 and base.get("input_order_sha256") == base_run["input_order_sha256"]
                 and base.get("input_raw_sha256") == base_run["input_raw_sha256"])
        _require(bind_recovery_provider_view_row({"binding_status": "BOUND", "report": report}, item)["binding_status"] == "BOUND")
        _require(source.get("base") is None or source["base"] == base)
        row.update(base=base, provider_report_ref=_ref(path, raw), provider={
            "execution_status": report["execution_status"], "guard_status": "GUARD_NOT_EVALUATED",
            "client_http_invocations": report["client_http_invocations"],
            "actual_external_call_count": report["actual_external_call_count"], "data_kind": report["data_kind"],
            "report_sha256": report["report_sha256"]})
        if source.get("native_receipt_path") is not None:
            _require(report["execution_status"] == "PROVIDER_EVIDENCE_STORED")
            directory = _safe(Path(source["native_output_dir"]), root)
            path = _safe(Path(source["native_receipt_path"]), root); path.relative_to(directory)
            native_raw = _read(path, root, LIMIT)
            summary = _native_summary(_json(native_raw), report, directory, root)
            row.update(native_receipt_ref=_ref(path, native_raw), native_output_dir=str(directory), native=summary)
    else:
        _require(source.get("native_receipt_path") is None and source.get("native_output_dir") is None and source.get("base") is None)
    if row["execution_status"] == "COMPLETED_NATIVE_IO":
        _require(row["native"] is not None and row["native"]["status"] == "COMPLETED_NATIVE_IO")
    else:
        _require(row["native"] is None or row["native"]["status"] != "COMPLETED_NATIVE_IO")
    if row["execution_status"] == "PROVIDER_EVIDENCE_STORED":
        _require(row["provider"] is not None and row["provider"]["execution_status"] == "PROVIDER_EVIDENCE_STORED"
                 and row["native"] is None)
    if row["execution_status"] in {"NOT_EXECUTED", "SKIPPED"}:
        _require(row["provider"] is None and row["native"] is None)
    return row


def _counts(rows):
    states = {state: sum(r["execution_status"] == state for r in rows) for state in sorted(STATES)}
    calls, actual = [], []
    for row in rows:
        # native가 진행됐을 수 있는 불완전 행에서 provider만 알려졌다고 전체를 확정하지 않는다.
        record = row["native"] or (row["provider"] if row["execution_status"] == "PROVIDER_EVIDENCE_STORED" else None)
        known_no_call = row["execution_status"] in {"NOT_EXECUTED", "SKIPPED"}
        calls.append(record["client_http_invocations"] if record else 0 if known_no_call else None)
        actual.append(record["actual_external_call_count"] if record else 0 if known_no_call else None)
    return {"input_count": len(rows), "states": states,
        "capture_states": {state: sum(r["capture_status"] == state for r in rows)
                           for state in sorted({r["capture_status"] for r in rows})},
        "provider_report_count": sum(r["provider"] is not None for r in rows),
        "client_http_invocations": None if None in calls else sum(calls),
        "actual_external_call_count": None if None in actual else sum(actual),
        "remote_dispatch_count": None, "remote_dispatch_status": "UNKNOWN"}


def _batch_summary(reference, base, policy, rows, root):
    """행 성공과 별개인 마지막 batch 제어 결과를 원래 raw ref로 고정한다."""
    if reference is None:
        return None
    report = _json(_read_ref(reference, root, LIMIT))
    _require(Path(reference["path"]).name == "batch.json" and type(report) is dict
             and set(report) == {"schema_version", "status", "base_run", "policy", "policy_sha256",
                 "data_kind", "rows", "counts", "budget", "reason_codes", "remote_provider_dispatch_count",
                 "receipt_sha256", *FLAGS})
    _check_false(report)
    _require(report["schema_version"] == "recovery_native_batch_v1"
             and report["status"] in {"COMPLETED", "INCOMPLETE", "NOT_EXECUTED"}
             and report["data_kind"] in {"TEST_SYNTHETIC", "SOURCE_BACKED"}
             and report["remote_provider_dispatch_count"] is None
             and _sha(report["receipt_sha256"]) and report["receipt_sha256"] == canonical_sha256(
                 {k: v for k, v in report.items() if k != "receipt_sha256"}))
    expected_base = {k: v for k, v in base.items() if k != "policy_sha256"}
    _require(_canonical(report["base_run"]) == _canonical(expected_base)
             and _canonical(report["policy"]) == _canonical(policy)
             and report["policy_sha256"] == base["policy_sha256"])
    reasons = _codes(report["reason_codes"])
    _require(not reasons if report["status"] == "COMPLETED" else bool(reasons))
    original_rows = report["rows"]
    _require(type(original_rows) is list and len(original_rows) == len(rows))
    states = ("NOT_EXECUTED", "RUNNING", "COMPLETED_NATIVE_IO", "INCOMPLETE")
    for original, row in zip(original_rows, rows):
        _check_false(original)
        _require(original.get("execution_status") in states and original["execution_status"] != "RUNNING"
                 and original.get("remote_provider_dispatch_count") is None)
        for key in ("input_index", "post_id", "capture_status", "execution_status", "reason_codes", "provider_report_ref"):
            _require(_canonical(original.get(key)) == _canonical(row[key]))
        _nullable_count(original.get("client_http_invocations"))
        _nullable_count(original.get("actual_external_calls"))
        if row["native"] is not None:
            native = row["native"]
            _require(original.get("native_receipt_ref") == row["native_receipt_ref"]
                     and original.get("native_output_dir") == row["native_output_dir"])
            if row["execution_status"] == "COMPLETED_NATIVE_IO":
                _require(_same(original.get("client_http_invocations"), native["client_http_invocations"])
                         and _same(original.get("actual_external_calls"), native["actual_external_call_count"]))
        guard = row["native"]["guard_status"] if row["execution_status"] == "COMPLETED_NATIVE_IO" else None
        _require(original.get("guard_outcome") == guard)
        if row["execution_status"] == "NOT_EXECUTED":
            _require(_same(original.get("client_http_invocations"), 0)
                     and _same(original.get("actual_external_calls"), 0))
    expected_counts = {"input_count": len(rows), **{state: sum(r["execution_status"] == state for r in original_rows)
                       for state in states}}
    for key in ("client_http_invocations", "actual_external_calls"):
        values = [r.get(key) for r in original_rows]
        expected_counts[key] = None if None in values else sum(values)
    _require(_canonical(report["counts"]) == _canonical(expected_counts))
    budget = report["budget"]
    _require(type(budget) is dict and set(budget) == {"reserved_rows", "reserved_calls", "reserved_response_bytes",
             "reserved_elapsed_ms", "refunds", "observed_elapsed_ms", "time_scope",
             "report_publication_io_in_time_scope", "total_ram_bytes"})
    for key, cap in (("reserved_rows", "max_capture_rows"), ("reserved_calls", "max_batch_calls"),
                     ("reserved_response_bytes", "max_batch_response_bytes"), ("reserved_elapsed_ms", "max_batch_elapsed_ms")):
        _require(type(budget[key]) is int and type(policy.get(cap)) is int and 0 <= budget[key] <= policy[cap])
    elapsed = budget["observed_elapsed_ms"]
    _require((elapsed is None or type(elapsed) in (int, float) and math.isfinite(elapsed) and elapsed >= 0)
             and _same(budget["refunds"], 0) and budget["time_scope"] == "THROUGH_FINAL_DRAIN_CONTROL_OBSERVATION"
             and budget["report_publication_io_in_time_scope"] is False and budget["total_ram_bytes"] is None)
    return {"schema_version": "recovery_native_batch_summary_v1", "status": report["status"],
        "reason_codes": reasons, "data_kind": report["data_kind"], "receipt_sha256": report["receipt_sha256"],
        "policy_sha256": report["policy_sha256"], "counts": report["counts"], "budget": budget, **FLAGS}


def _validate(payload, output, root):
    _require(type(payload) is dict and set(payload) == {"schema_version", "base_run", "policy", "rows", "counts",
             "batch_report_ref", "batch", "aggregate_sha256", *FLAGS})
    _check_false(payload)
    _require(payload["schema_version"] == SCHEMA and _sha(payload["aggregate_sha256"])
             and payload["aggregate_sha256"] == canonical_sha256({k: v for k, v in payload.items() if k != "aggregate_sha256"}))
    base = payload["base_run"]
    _require(type(base) is dict and set(base) == {"run_id", "publication_scope_id", "input_count", "input_order_sha256", "input_raw_sha256", "policy_sha256", "result", "manifest"})
    _require(_safe(Path(base["result"]["path"]), root) == output)
    _read_ref(base["result"], root, SOURCE_LIMIT); _read_ref(base["manifest"], root, LIMIT)
    items, manifest, result_ref, manifest_ref = _base_files(output, Path(base["manifest"]["path"]), root, payload["policy"])
    expected = {"run_id": manifest["run_id"], "publication_scope_id": manifest["publication_scope_id"],
        "input_count": len(items), "input_order_sha256": canonical_sha256([i["post_id"] for i in items]),
        "input_raw_sha256": manifest["publication_input_snapshot_sha256"],
        "policy_sha256": canonical_sha256(payload["policy"]), "result": result_ref, "manifest": manifest_ref}
    _require(base == expected and type(payload["rows"]) is list and len(payload["rows"]) == len(items))
    for index, (row, item) in enumerate(zip(payload["rows"], items), 1):
        _require(type(row) is dict)
        source = {k: row[k] for k in ("input_index", "post_id", "capture_status", "execution_status", "reason_codes", "base")}
        for refkey, pathkey in (("provider_report_ref", "provider_report_path"), ("native_receipt_ref", "native_receipt_path")):
            ref = row.get(refkey)
            if ref is not None: _read_ref(ref, root, LIMIT)
            source[pathkey] = ref["path"] if ref is not None else None
        source["native_output_dir"] = row.get("native_output_dir")
        regenerated = _row(source, item, index, base, root)
        _require(row == regenerated)
    _require(payload["counts"] == _counts(payload["rows"]))
    _require(_canonical(payload["batch"]) == _canonical(_batch_summary(
        payload["batch_report_ref"], base, payload["policy"], payload["rows"], root)))
    return payload


def publish_recovery_native_view(output_path, manifest_path, *, root, policy, rows, input_posts=None, batch_report_ref=None):
    """완료 workflow의 저장 보고서를 전체 입력에 결속해 한 번 발행한다."""
    root = Path(root).resolve(); output = _safe(Path(output_path), root)
    manifest_path = _safe(Path(manifest_path), root)
    items, manifest, result_ref, manifest_ref = _base_files(output, manifest_path, root, policy)
    if input_posts is not None:
        _require(type(input_posts) is list and len(input_posts) == len(items)
                 and all(type(p) is dict and _same(p.get("post_id"), i["post_id"]) for p, i in zip(input_posts, items)))
    _require(type(rows) is list and len(rows) == len(items))
    base = {"run_id": manifest["run_id"], "publication_scope_id": manifest["publication_scope_id"],
        "input_count": len(items), "input_order_sha256": canonical_sha256([i["post_id"] for i in items]),
        "input_raw_sha256": manifest["publication_input_snapshot_sha256"],
        "policy_sha256": canonical_sha256(policy), "result": result_ref, "manifest": manifest_ref}
    prepared = [_row(row, item, i, base, root) for i, (row, item) in enumerate(zip(rows, items), 1)]
    payload = {"schema_version": SCHEMA, "base_run": base, "policy": deepcopy(policy), "rows": prepared,
               "counts": _counts(prepared), "batch_report_ref": deepcopy(batch_report_ref),
               "batch": _batch_summary(batch_report_ref, base, policy, prepared, root), **FLAGS}
    payload["aggregate_sha256"] = canonical_sha256(payload)
    _validate(payload, output, root)
    raw = _canonical(payload) + b"\n"; _require(len(raw) <= LIMIT)
    target = _safe(_path(output), root)
    _require(target not in (output, manifest_path))
    if not os.path.lexists(target):
        pending = target.with_name(target.name + "." + uuid.uuid4().hex + ".pending")
        with pending.open("xb") as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        _require(_read(pending, root, LIMIT) == raw)
        try:
            if os.name == "nt": os.rename(pending, target)
            else:
                os.link(pending, target); pending.unlink()
        except FileExistsError:
            pass
    _require(_read(target, root, LIMIT) == raw)
    _validate(_json(_read(target, root, LIMIT)), output, root)
    return _ref(target, raw)


def read_recovery_native_view(output_path, root, *, item=None):
    empty = {"binding_status": "MISSING", "verification_scope": SCOPE, "reason_codes": ["NATIVE_AGGREGATE_NOT_ATTACHED"]}
    try:
        root = Path(root).resolve(); output = _safe(Path(output_path), root); target = _safe(_path(output), root)
        if not os.path.lexists(target): return empty
        raw = _read(target, root, LIMIT); payload = _validate(_json(raw), output, root)
        _require(_read(target, root, LIMIT) == raw)
        view = {"binding_status": "BOUND", "verification_scope": SCOPE, "reason_codes": [], "aggregate": payload}
        return bind_recovery_native_view_row(view, item) if item is not None else view
    except (OSError, ValueError, KeyError, TypeError, RecursionError, AttributeError):
        return {**empty, "binding_status": "INVALID", "reason_codes": ["NATIVE_REFERENCE_OR_BASE_INVALID"]}


def bind_recovery_native_view_row(view, item):
    if view.get("binding_status") != "BOUND": return view
    try:
        rows = view["aggregate"]["rows"]
        selected = [row for row in rows if _same(row["post_id"], item.get("post_id"))]
        _require(len(selected) == 1 and canonical_sha256(item) == selected[0]["result_sha256"])
        return {**view, "row": selected[0]}
    except (ValueError, TypeError, KeyError, AttributeError):
        return {"binding_status": "INVALID", "verification_scope": SCOPE, "reason_codes": ["NATIVE_SELECTED_ROW_INVALID"]}
