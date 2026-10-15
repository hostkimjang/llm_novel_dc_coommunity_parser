"""Provider 원장과 저장 응답을 독립 판독한다. 공개 판정이나 원격 내부 호출을 추정하지 않는다."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import os
from pathlib import Path
import re

from ..ledger.recovery_provider_journal import (
    RecoveryProviderJournal, canonical_bytes, canonical_sha256, request_identity,
)
from .recovery_execution_readback import read_strict_json

SCHEMA = "recovery_provider_report_v1"
FIXED = {"guard_status": "GUARD_NOT_EVALUATED", "public_apply": False,
         "publication_authority": False, "central_db_write": False,
         "formal_kpi_status": "NOT_ESTIMABLE", "remote_provider_dispatch_count": None,
         "remote_provider_dispatch_status": "UNKNOWN"}
SHA = re.compile(r"[0-9a-f]{64}\Z")


def _require(condition, code):
    if not condition:
        raise ValueError(code)


def _equal(left, right):
    return canonical_bytes(left) == canonical_bytes(right)


def _saved(bound, ref, limit):
    from ..runtime.recovery_provider_transport import _read
    _require(type(ref) is dict and set(ref) == {"path", "sha256", "bytes"}, "PROVIDER_REF_INVALID")
    _require(type(ref["path"]) is str and re.fullmatch(r"responses/[0-9a-f]{64}\.(?:bin|json)", ref["path"]), "PROVIDER_REF_PATH")
    _require(type(ref["bytes"]) is int and 0 <= ref["bytes"] <= limit, "PROVIDER_REF_BYTES")
    path = bound.assert_output_path(bound.output_dir / ref["path"])
    raw = _read(path, limit)
    _require(len(raw) == ref["bytes"] and hashlib.sha256(raw).hexdigest() == ref["sha256"], "PROVIDER_REF_SHA")
    return raw


def build_provider_report(bound_plan, *, execution=None):
    """현재 고정 원본·원장·실제 저장 bytes로 다시 만든 보고서. execution은 권위가 아니다."""
    from .recovery_provider_contract import BoundRecoveryProviderPlan, provider_journal_arguments
    _require(type(bound_plan) is BoundRecoveryProviderPlan, "BOUND_PROVIDER_PLAN_REQUIRED")
    bound_plan.verify_protected_sources()
    plan = bound_plan.plan
    args = provider_journal_arguments(plan)
    state = RecoveryProviderJournal(bound_plan.journal_path, **args).snapshot()
    anchor_path = bound_plan.journal_path.with_name(bound_plan.journal_path.name + ".anchor.json")
    _require(state["started"] is not None or not os.path.lexists(anchor_path), "JOURNAL_MISSING_AFTER_ANCHOR")
    if state["started"]:
        from ..runtime.recovery_provider_transport import _read
        anchor = bound_plan.assert_output_path(bound_plan.journal_path.with_name(bound_plan.journal_path.name + ".anchor.json"))
        expected_anchor = {"configuration_sha256": state["configuration_sha256"],
                           "journal_path_sha256": state["journal_path_sha256"],
                           "owner_epoch": state["started"]["payload"]["owner_epoch"]}
        _require(_read(anchor, 4096) == canonical_bytes(expected_anchor), "PROVIDER_ANCHOR_BINDING")
    summaries = []
    mode = state["started"]["payload"]["transport_mode"] if state["started"] else "NOT_STARTED"
    for rid, call in state["calls"].items():
        reservation = call["reserved"]["payload"]
        row = {"request_id": rid, "request_sha256": reservation["request_sha256"],
               "reservation_id": reservation["reservation_id"], "status": "INCOMPLETE_DISPATCH",
               "response_ref": None, "transport_ref": None, "transport_receipt_sha256": None,
               "client_http_invocations": None, "actual_external_call_count": None,
               "observed_response_bytes": None, "finalization_recorded": False}
        terminal = call["terminal"]
        if terminal is not None:
            value = terminal["payload"]
            raw = _saved(bound_plan, value["transport_ref"], 24 * 1024 * 1024)
            transport = read_strict_json(raw, maximum_bytes=24 * 1024 * 1024)
            _require(type(transport) is dict and transport.get("schema_version") == "recovery_transport_receipt_v1", "TRANSPORT_RECEIPT_SCHEMA")
            digest = canonical_sha256({k:v for k,v in transport.items() if k != "receipt_sha256"})
            _require(digest == transport.get("receipt_sha256") == value["transport_receipt_sha256"], "TRANSPORT_RECEIPT_SHA")
            request = next(r for r in args["requests"] if r["request_id"] == rid)
            identity = request_identity(args["binding"], args["policy"], request)
            _require(value["transport_ref"]["path"] == "responses/" + identity["request_sha256"] + ".json", "TRANSPORT_REF_REQUEST")
            _require(all(_equal(transport.get(k), v) for k,v in identity.items()), "TRANSPORT_REQUEST_BINDING")
            _require(transport.get("status") == value["status"] and transport.get("reservation_id") == reservation["reservation_id"]
                     and transport.get("reservation_consumed") is True, "TRANSPORT_STATUS_BINDING")
            _require(transport.get("transport_mode") == mode, "TRANSPORT_MODE_BINDING")
            for k in ("observed_response_bytes", "transport_invocations"):
                _require(_equal(transport.get(k), value[k]), "TRANSPORT_COUNT_BINDING")
            for k in ("public_apply", "publication_authority", "central_db_write"):
                _require(transport.get(k) is False, "TRANSPORT_AUTHORITY")
            response = value["response_ref"]
            if response is not None:
                _require(response["path"] == "responses/" + identity["request_sha256"] + ".bin", "RESPONSE_REF_REQUEST")
                response_raw = _saved(bound_plan, response, args["policy"]["max_response_bytes"])
                _require(transport.get("response_complete") is True and hashlib.sha256(response_raw).hexdigest() == transport.get("response_sha256"), "RESPONSE_RAW_BINDING")
                _require(transport.get("observed_response_sha256") == (response["sha256"] if response_raw else None), "RESPONSE_OBSERVED_SHA")
                _require(len(response_raw) == transport["observed_response_bytes"], "RESPONSE_SIZE_BINDING")
                if transport["status"] == "SUCCESS":
                    _require(_equal(read_strict_json(response_raw, maximum_bytes=args["policy"]["max_response_bytes"]), transport.get("payload")), "RESPONSE_PAYLOAD_BINDING")
            _require(transport["status"] != "SUCCESS" or response is not None, "SUCCESS_RESPONSE_MISSING")
            row.update(response_ref=response, transport_ref=value["transport_ref"],
                       transport_receipt_sha256=value["transport_receipt_sha256"],
                       client_http_invocations=value["transport_invocations"],
                       actual_external_call_count=value["actual_external_calls"],
                       observed_response_bytes=value["observed_response_bytes"])
        if call["finalized"] is not None:
            row.update(status=call["finalized"]["payload"]["status"], finalization_recorded=True)
        summaries.append(row)
    incomplete = any(not row["finalization_recorded"] for row in summaries)
    if incomplete:
        status = "INCOMPLETE_DISPATCH"
    elif not summaries:
        status = "NOT_STARTED"
    elif len(summaries) == len(args["requests"]) and all(row["status"] == "SUCCESS" for row in summaries):
        status = "PROVIDER_EVIDENCE_STORED"
    else:
        status = "PROVIDER_REQUEST_FAILED"
    uncertain = any(row["client_http_invocations"] is None for row in summaries)
    base = deepcopy(plan["base"])
    rows = []
    for index, post in enumerate(bound_plan.input_rows, 1):
        row = {"input_index": index, "post_id": post["post_id"]}
        selected = row["input_index"] == base["input_index"] and _equal(row["post_id"], base["post_id"])
        rows.append({**row, "state": status if selected else "NO_PLAN_PROVIDED"})
    report = {"schema_version": SCHEMA, **FIXED, "base": base,
              "plan_sha256": plan["plan_sha256"], "data_kind": plan["data_kind"],
              "execution_status": status, "transport_mode": mode,
              "verification_scope": "SOURCE_JOURNAL_AND_RESPONSE_READBACK",
              "journal_head_sha256": state["head_sha256"],
              "budget": deepcopy(state["budget"]), "request_receipts": summaries,
              "client_http_invocations": None if uncertain else sum(r["client_http_invocations"] for r in summaries),
              "actual_external_call_count": None if uncertain and mode != "TEST_DOUBLE" else sum((r["actual_external_call_count"] or 0) for r in summaries),
              "input_count": len(rows), "input_rows": rows}
    report["report_sha256"] = canonical_sha256(report)
    validate_provider_report(report)
    bound_plan.verify_protected_sources()
    return report


def validate_provider_report(report):
    _require(type(report) is dict and report.get("schema_version") == SCHEMA, "PROVIDER_REPORT_SCHEMA")
    _require(report.get("report_sha256") == canonical_sha256({k:v for k,v in report.items() if k != "report_sha256"}), "PROVIDER_REPORT_SHA")
    for k,v in FIXED.items():
        _require(type(report.get(k)) is type(v) and report.get(k) == v, "PROVIDER_REPORT_AUTHORITY")
    _require(report.get("data_kind") in {"SOURCE_BACKED", "TEST_SYNTHETIC", "UNKNOWN"}, "PROVIDER_REPORT_DATA_KIND")
    _require(report.get("transport_mode") in {"HTTPX_SINGLE_REQUEST", "TEST_DOUBLE", "NOT_STARTED"}, "PROVIDER_REPORT_TRANSPORT_MODE")
    _require(report.get("verification_scope") == "SOURCE_JOURNAL_AND_RESPONSE_READBACK", "PROVIDER_REPORT_SCOPE")
    _require(report.get("execution_status") in {"PROVIDER_EVIDENCE_STORED", "INCOMPLETE_DISPATCH", "PROVIDER_REQUEST_FAILED", "NOT_STARTED"}, "PROVIDER_REPORT_STATUS")
    _require(type(report.get("plan_sha256")) is str and SHA.fullmatch(report["plan_sha256"]), "PROVIDER_REPORT_PLAN_SHA")
    for key in ("client_http_invocations", "actual_external_call_count"):
        value = report.get(key)
        _require(value is None or (type(value) is int and value >= 0), "PROVIDER_REPORT_COUNT")
    if report["transport_mode"] in {"TEST_DOUBLE", "NOT_STARTED"}:
        _require(report["actual_external_call_count"] == 0, "PROVIDER_REPORT_TEST_ACTUAL_COUNT")
    rows, receipts, base = report.get("input_rows"), report.get("request_receipts"), report.get("base")
    _require(type(base) is dict and type(rows) is list and type(receipts) is list, "PROVIDER_REPORT_ROWS")
    _require(type(report.get("input_count")) is int and len(rows) == report["input_count"] > 0, "PROVIDER_REPORT_DENOMINATOR")
    _require(base.get("input_count") == report["input_count"] and type(base.get("input_index")) is int, "PROVIDER_REPORT_BASE_DENOMINATOR")
    _require(len(receipts) <= 1, "PROVIDER_REPORT_REQUESTS")
    for row in receipts:
        _require(type(row) is dict and type(row.get("finalization_recorded")) is bool, "PROVIDER_REPORT_REQUEST_SCHEMA")
        for key in ("request_sha256",):
            _require(type(row.get(key)) is str and SHA.fullmatch(row[key]), "PROVIDER_REPORT_REQUEST_SHA")
        for key in ("request_id", "reservation_id", "status"):
            _require(type(row.get(key)) is str and 0 < len(row[key]) <= 128, "PROVIDER_REPORT_REQUEST_ID")
        for key in ("client_http_invocations", "actual_external_call_count", "observed_response_bytes"):
            value = row.get(key)
            _require(value is None or type(value) is int and value >= 0, "PROVIDER_REPORT_REQUEST_COUNT")
        _require(row["client_http_invocations"] is None or row["client_http_invocations"] <= 1, "PROVIDER_REPORT_RETRY")
        expected_row_actual = (None if row["client_http_invocations"] is None else
                               0 if report["transport_mode"] == "TEST_DOUBLE" else row["client_http_invocations"])
        _require(_equal(row["actual_external_call_count"], expected_row_actual), "PROVIDER_REPORT_REQUEST_ACTUAL_COUNT")
        if row["finalization_recorded"]:
            _require(row["client_http_invocations"] is not None and row.get("transport_ref") is not None, "PROVIDER_REPORT_TERMINAL_MISSING")
        else:
            _require(row["status"] == "INCOMPLETE_DISPATCH", "PROVIDER_REPORT_INCOMPLETE_STATUS")
        for key, suffix in (("response_ref", ".bin"), ("transport_ref", ".json")):
            ref = row.get(key)
            if ref is not None:
                _require(type(ref) is dict and set(ref) == {"path", "sha256", "bytes"}
                         and ref["path"] == "responses/" + row["request_sha256"] + suffix
                         and type(ref["sha256"]) is str and SHA.fullmatch(ref["sha256"])
                         and type(ref["bytes"]) is int and ref["bytes"] >= 0, "PROVIDER_REPORT_RESPONSE_REF")
        if row.get("transport_ref") is not None:
            _require(type(row.get("transport_receipt_sha256")) is str and SHA.fullmatch(row["transport_receipt_sha256"]),
                     "PROVIDER_REPORT_TRANSPORT_SHA")
        if row["status"] == "SUCCESS":
            _require(row["client_http_invocations"] == 1 and row.get("transport_ref") is not None
                     and row.get("response_ref") is not None
                     and _equal(row["observed_response_bytes"], row["response_ref"]["bytes"]),
                     "PROVIDER_REPORT_SUCCESS_COUNTS")
    _require(report["transport_mode"] != "NOT_STARTED" or not receipts, "PROVIDER_REPORT_NOT_STARTED_REQUESTS")
    uncertain = any(row["client_http_invocations"] is None for row in receipts)
    expected_calls = None if uncertain else sum(row["client_http_invocations"] for row in receipts)
    expected_actual = 0 if report["transport_mode"] in {"TEST_DOUBLE", "NOT_STARTED"} else expected_calls
    _require(_equal(report["client_http_invocations"], expected_calls)
             and _equal(report["actual_external_call_count"], expected_actual), "PROVIDER_REPORT_COUNT_TOTAL")
    derived_status = ("INCOMPLETE_DISPATCH" if any(not r["finalization_recorded"] for r in receipts)
                      else "NOT_STARTED" if not receipts else "PROVIDER_EVIDENCE_STORED" if all(r["status"] == "SUCCESS" for r in receipts)
                      else "PROVIDER_REQUEST_FAILED")
    _require(report["execution_status"] == derived_status, "PROVIDER_REPORT_STATUS_CONTRADICTION")
    selected_count = 0
    for index, row in enumerate(rows, 1):
        _require(type(row) is dict and row.get("input_index") == index, "PROVIDER_REPORT_INPUT_ORDER")
        selected = index == base.get("input_index") and _equal(row.get("post_id"), base.get("post_id"))
        selected_count += int(selected)
        _require(row.get("state") == (report["execution_status"] if selected else "NO_PLAN_PROVIDED"), "PROVIDER_REPORT_INPUT_STATE")
    _require(selected_count == 1, "PROVIDER_REPORT_BASE_ROW")
    if report["execution_status"] == "PROVIDER_EVIDENCE_STORED":
        _require(bool(receipts) and all(r.get("status") == "SUCCESS" and r.get("finalization_recorded") is True and r.get("response_ref") is not None for r in receipts), "PROVIDER_REPORT_SUCCESS_MISSING")
    return deepcopy(report)
