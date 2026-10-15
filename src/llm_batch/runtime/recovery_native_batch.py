"""현재 호출의 capture만 보관하고 원본 확정 뒤 별도 복구를 직렬 소비한다.

first-N 배정과 최대치 슬롯 예약은 실제 행별 durable 원장을 대체하지 않는다.
완료 batch의 같은 객체 재호출 외에는 재개하지 않으며 과거 JSON을 복원하지 않는다.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
import hashlib
import math
import os
from pathlib import Path
import re
import threading
import time

from ..ledger.publication_commit import (
    PublicationDecisionCommit, PublicationScopeDescriptor, validate_publication_result_commit,
)
from ..ledger.recovery_activation import extract_direct_ocr_review_proposals
from ..measurement import recovery_execution_contract as files
from ..measurement.recovery_input_projection import validate_main_input_projection
from ..measurement.recovery_provider_contract import (
    SOURCE_SCHEMA, build_recovery_provider_plan, bind_recovery_provider_plan,
)
from ..measurement.recovery_provider_readback import build_provider_report
from ..monitor.recovery_view import _read, _read_ref, _ref, _safe
from .recovery_native_context import NativeRecoveryCapture
from .recovery_transport import RecoveryTransportPolicy, _endpoint

SCHEMA = "recovery_native_batch_v1"
POLICY_SCHEMA = "recovery_native_batch_policy_v1"
MAX_CAPTURE_ROWS = 64
MAX_INPUT_ROWS = 10000
_POLICY_KEYS = {"schema_version", "max_capture_rows", "max_batch_calls", "max_batch_elapsed_ms",
    "max_batch_response_bytes", "provider_policy", "native_policy", "provider_endpoint", "native_config"}
_WIRE_KEYS = {"model", "max_tokens", "temperature", "top_p", "server_type", "min_p",
              "repeat_penalty", "enable_thinking", "temperature_by_tag", "vllm_top_k", "vllm_presence_penalty"}
_FLAGS = {"publication_authority": False, "public_apply": False, "central_db_write": False,
          "actual_quality_evaluated": False, "formal_kpi_status": "NOT_ESTIMABLE"}
_sha = files.canonical_sha256
_bytes = files._canonical_bytes


class NativeRecoveryBatchError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _require(condition, code):
    if not condition:
        raise NativeRecoveryBatchError(code)


def _code(exc):
    value = getattr(exc, "code", None)
    return value if type(value) is str and re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", value) else "BATCH_OPERATION_FAILED"


def _same(left, right, code):
    _require(_bytes(left) == _bytes(right), code)


def validate_native_batch_policy(value):
    """명시 JSON 정책만 검산한다. 파일·capture·원장·네트워크를 만들지 않는다."""
    _require(type(value) is dict and set(value) == _POLICY_KEYS, "BATCH_POLICY_FIELDS")
    _require(value["schema_version"] == POLICY_SCHEMA, "BATCH_POLICY_SCHEMA")
    for key in ("max_capture_rows", "max_batch_calls", "max_batch_elapsed_ms", "max_batch_response_bytes"):
        _require(type(value[key]) is int and 0 <= value[key] <= 2**53 - 1, "BATCH_POLICY_INTEGER")
    _require(value["max_capture_rows"] <= MAX_CAPTURE_ROWS, "BATCH_CAPTURE_LIMIT")
    _require(value["max_batch_elapsed_ms"] <= 86400000, "BATCH_TIME_LIMIT")
    for key in ("provider_policy", "native_policy"):
        policy = value[key]
        _require(type(policy) is dict and set(policy) == set(RecoveryTransportPolicy.__dataclass_fields__),
                 "BATCH_TRANSPORT_POLICY_FIELDS")
        checked = RecoveryTransportPolicy(**policy)
        _require(checked.request_timeout_ms <= checked.max_elapsed_ms, "BATCH_REQUEST_DEADLINE")
        _same(asdict(checked), policy, "BATCH_TRANSPORT_POLICY_CHANGED")
    _require(value["provider_policy"]["max_calls"] == 1, "BATCH_SINGLE_PROVIDER_REQUEST")
    _require(value["native_policy"]["max_calls"] <= 128, "BATCH_NATIVE_CALL_LIMIT")
    config = value["native_config"]
    _require(type(config) is dict and set(config) == _WIRE_KEYS | {"endpoints"}, "BATCH_NATIVE_CONFIG_FIELDS")
    endpoints = config["endpoints"]
    _require(type(endpoints) is dict and set(endpoints) == {"OPENAI_CHAT", "MCP_SEARCH", "MCP_FETCH"},
             "BATCH_ENDPOINT_FIELDS")
    for endpoint in (value["provider_endpoint"], *endpoints.values()):
        _require(_endpoint(endpoint) == endpoint, "BATCH_ENDPOINT_NOT_CANONICAL")
    _same(value["provider_endpoint"], endpoints["MCP_SEARCH"], "BATCH_SEARCH_ENDPOINT_MISMATCH")
    from .recovery_native_io import validate_native_wire_config
    normalized = validate_native_wire_config(**{key: config[key] for key in _WIRE_KEYS})
    _same(normalized, {key: config[key] for key in _WIRE_KEYS}, "BATCH_WIRE_SETTINGS_MUST_BE_EXPLICIT")
    _bytes(value)
    return deepcopy(value)


def _row(index, post_id, admitted):
    return {"input_index": index, "post_id": post_id,
        "capture_status": "AWAITING_CAPTURE" if admitted else "NOT_ADMITTED",
        "execution_status": "NOT_EXECUTED", "reason_codes": [] if admitted else ["CAPTURE_ADMISSION_LIMIT"],
        "base": None, "provider_plan_ref": None, "provider_report_ref": None,
        "native_result_ref": None, "native_journal_ref": None, "native_receipt_ref": None,
        "native_output_dir": None, "guard_outcome": None,
        "client_http_invocations": 0, "actual_external_calls": 0,
        "remote_provider_dispatch_count": None, **_FLAGS}


class NativeRecoveryBatchCoordinator:
    def __init__(self, *, policy, input_post_ids, input_snapshot_bytes, input_path,
                 output_dir, root, hmac_key_path, dashboard_url, data_kind="SOURCE_BACKED",
                 event_bus=None, cancelled=None, clock_ms=None, test_transport=None,
                 run_id=None, publication_scope_id=None):
        self._policy = validate_native_batch_policy(policy)
        _require(type(input_post_ids) is list and 0 < len(input_post_ids) <= MAX_INPUT_ROWS, "BATCH_INPUT_IDS")
        for value in input_post_ids:
            _require(type(value) in (int, str) and (type(value) is int or bool(value.strip())), "BATCH_TYPED_ID")
        _require(len({_bytes(x) for x in input_post_ids}) == len(input_post_ids), "BATCH_DUPLICATE_ID")
        _require(type(input_snapshot_bytes) is bytes and 0 < len(input_snapshot_bytes) <= files.MAX_FILE_BYTES,
                 "BATCH_INPUT_SNAPSHOT")
        posts, _ = files._input_snapshot(input_snapshot_bytes, "JSONL_POST_COMMENT_V1")
        _same([p["post_id"] for p in posts], input_post_ids, "BATCH_INPUT_ID_ORDER")
        _require(data_kind in {"SOURCE_BACKED", "TEST_SYNTHETIC"}, "BATCH_DATA_KIND")
        _require(data_kind != "TEST_SYNTHETIC" or test_transport is not None, "BATCH_SYNTHETIC_REQUIRES_MOCK")
        self._root = Path(root).resolve()
        self._directory = _safe(files._absolute_path(str(output_dir)), self._root)
        self._input_path = files._safe_path(files._absolute_path(str(input_path)))
        self._key_path = files._safe_path(files._absolute_path(str(hmac_key_path)))
        for path in (self._input_path, self._key_path):
            _require(path != self._directory and self._directory not in path.parents, "BATCH_OUTPUT_SOURCE_OVERLAP")
        self._input = input_snapshot_bytes
        self._ids, self._posts = deepcopy(input_post_ids), posts
        self._data_kind, self._dashboard = data_kind, dashboard_url
        self._bus, self._cancelled = event_bus, cancelled or (lambda: False)
        self._clock, self._transport = clock_ms or (lambda: time.monotonic() * 1000), test_transport
        self._rows = [_row(i, pid, i <= policy["max_capture_rows"]) for i, pid in enumerate(input_post_ids, 1)]
        self._captures, self._receipts = {}, {}
        self._accepted = set()
        self._lock = threading.RLock()
        self._state, self._reasons, self._base, self._refs = "COLLECTING", [], None, {}
        self._reserved_calls = self._reserved_bytes = self._reserved_rows = self._reserved_time = 0
        self._started = self._last_clock = None
        self._finished = None
        self._key_raw = self._anchor_ref = None
        self._source_failure_code = None
        self._audit_missing_path = self._current_index = None
        self._progress_binding = None
        if run_id is not None or publication_scope_id is not None:
            _require(type(run_id) is str and 0 < len(run_id) <= 200 and type(publication_scope_id) is str
                and re.fullmatch(r"[0-9a-f]{64}", publication_scope_id) is not None, "BATCH_PROGRESS_BINDING")
            self._progress_binding = {"run_id": run_id, "publication_scope_id": publication_scope_id}
        self._sequence, self._processed = 0, set()

    def admitted(self, input_index, post_id):
        _require(type(input_index) is int and 1 <= input_index <= len(self._ids), "BATCH_INPUT_INDEX")
        _same(post_id, self._ids[input_index - 1], "BATCH_TYPED_ROW_MISMATCH")
        return input_index <= self._policy["max_capture_rows"]

    def accept_committed(self, input_index, post_id, capture, *, result, receipt, created=True):
        """commit 완료 행만 소유한다. 전달 객체를 JSON에서 재생성하지 않는다."""
        with self._lock:
            _require(self._state == "COLLECTING", "BATCH_ADMISSION_CLOSED")
            if not self.admitted(input_index, post_id):
                return False
            _require(input_index not in self._accepted, "BATCH_CAPTURE_ALREADY_RECEIVED")
            self._accepted.add(input_index)
            row = self._rows[input_index - 1]
            try:
                _require(created is True, "BASE_PUBLICATION_REPLAY_NO_CAPTURE")
                _require(type(capture) is NativeRecoveryCapture, "CAPTURE_UNAVAILABLE")
                capture.verify_current()
                _same(capture.post.post_id, post_id, "BATCH_CAPTURE_POST_MISMATCH")
                rec = receipt if type(receipt) is PublicationDecisionCommit else PublicationDecisionCommit.from_dict(receipt)
                _same(rec.post_id, post_id, "BATCH_COMMIT_POST_TYPE")
                _require(rec.input_index == input_index, "BATCH_COMMIT_INDEX")
                validate_publication_result_commit(result, rec)
                self._captures[input_index] = capture
                self._receipts[input_index] = rec.to_dict()
                row["capture_status"] = "CAPTURED"
                row["base"] = {"publication_scope_id": rec.publication_scope_id, "input_index": input_index,
                    "post_id": post_id, "publication_decision_id": rec.decision_id,
                    "base_attempt_run_id": rec.attempt_run_id, "result_sha256": rec.result_sha256}
                return True
            except Exception as exc:
                row.update(capture_status="UNAVAILABLE", reason_codes=[_code(exc)])
                return False

    def _now(self):
        value = self._clock()
        _require(type(value) in (int, float) and math.isfinite(value), "BATCH_CLOCK_INVALID")
        _require(self._last_clock is None or value >= self._last_clock, "BATCH_CLOCK_REGRESSED")
        self._last_clock = value
        return value

    def _check_control(self):
        elapsed = self._now() - self._started
        cancelled = self._cancelled()
        _require(type(cancelled) is bool, "BATCH_CANCELLATION_INVALID")
        _require(not cancelled, "BATCH_CANCELLED")
        _require(elapsed < self._policy["max_batch_elapsed_ms"], "BATCH_TIME_EXHAUSTED")

    def _check_sources(self):
        # A stopped controller must not hide a simultaneous protected-source failure.
        # This check is also used immediately before publishing and on completed replay.
        if self._source_failure_code is not None:
            raise NativeRecoveryBatchError(self._source_failure_code)
        try:
            return self._verify_protected_sources()
        except Exception as exc:
            code = _code(exc)
            self._source_failure_code = code if code != "BATCH_OPERATION_FAILED" else "BATCH_PROTECTED_SOURCE_CHANGED"
            raise NativeRecoveryBatchError(self._source_failure_code) from exc

    def _verify_protected_sources(self):
        for ref in self._refs.values():
            try:
                files._read_protected(ref)
            except Exception as exc:
                raise NativeRecoveryBatchError("BATCH_PROTECTED_SOURCE_CHANGED") from exc
        if self._audit_missing_path is not None:
            _require(not os.path.lexists(self._audit_missing_path), "BATCH_ACTIVATION_JOURNAL_DRIFT")
        _require(self._read_original(self._input_path) == self._input, "BATCH_INPUT_DRIFT")
        if self._key_raw is not None:
            _require(self._read_original(self._key_path, 4096) == self._key_raw, "BATCH_KEY_DRIFT")
        if self._anchor_ref is not None:
            try:
                _read_ref(self._anchor_ref, self._root, 65536)
            except Exception as exc:
                raise NativeRecoveryBatchError("BATCH_ANCHOR_CHANGED") from exc
        if self._current_index in self._captures:
            self._captures[self._current_index].verify_current()
        return True

    def _check(self):
        self._check_sources()
        self._check_control()
        return True

    def _cancel_control(self):
        self._check()
        return False

    @staticmethod
    def _read_original(path, limit=files.MAX_FILE_BYTES):
        path = files._safe_path(path, file_required=True)
        _require(path.stat().st_size <= limit, "BATCH_SOURCE_BYTE_LIMIT")
        raw = path.read_bytes()
        _require(len(raw) <= limit, "BATCH_SOURCE_BYTE_LIMIT")
        files._read_protected(_ref(path, raw))
        return raw

    def _save(self, path, raw):
        path = _safe(path, self._root)
        _require(self._directory in path.parents, "BATCH_OUTPUT_OUTSIDE_NAMESPACE")
        _require(len(raw) <= files.MAX_FILE_BYTES, "BATCH_OUTPUT_BYTE_LIMIT")
        path.parent.mkdir(parents=True, exist_ok=True)
        _safe(path, self._root)
        with path.open("xb") as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        ref = _ref(path, raw)
        _read_ref(ref, self._root, files.MAX_FILE_BYTES)
        return ref

    def _emit(self, complete=False):
        if self._bus is not None and self._progress_binding is not None:
            self._sequence += 1
            rows = self._rows if complete else [r for r in self._rows if r["input_index"] in self._processed]
            reference = self._finished.get("dashboard_reference") if self._finished else None
            status = ("COMPLETED" if self._state == "COMPLETED" and reference else "INCOMPLETE") if complete else "RUNNING"
            value = {"schema_version": "native_recovery_progress_v1", **self._progress_binding,
                "policy_sha256": _sha(self._policy), "sequence": self._sequence, "status": status,
                "total": len(self._ids), "processed": len(rows),
                "completed": sum(r["execution_status"] == "COMPLETED_NATIVE_IO" for r in rows),
                "not_executed": sum(r["execution_status"] == "NOT_EXECUTED" for r in rows),
                "incomplete": sum(r["execution_status"] == "INCOMPLETE" for r in rows),
                "aggregate_ref": deepcopy(reference)}
            self._bus.emit("native_recovery_complete" if complete else "native_recovery_progress", value)

    def _preflight(self, paths):
        _require(self._read_original(self._input_path) == self._input, "BATCH_INPUT_DRIFT")
        paths = dict(paths)
        audit_path = files._safe_path(files._absolute_path(str(paths["activation_journal"])))
        if not os.path.lexists(audit_path):
            self._audit_missing_path = audit_path
            del paths["activation_journal"]
        raw = {role: self._read_original(files._absolute_path(str(path))) for role, path in paths.items()}
        self._refs = {role: _ref(files._absolute_path(str(paths[role])), value) for role, value in raw.items()}
        _require(sum(len(x) for x in raw.values()) + len(self._input) <= files.MAX_TOTAL_BYTES, "BATCH_SOURCE_TOTAL_LIMIT")
        for ref in self._refs.values():
            source = Path(ref["path"])
            _require(source != self._directory and self._directory not in source.parents, "BATCH_OUTPUT_SOURCE_OVERLAP")
        manifest, results = files._load_json(raw["manifest"]), files._load_json(raw["result"])
        if type(manifest) is dict:
            observed = {"run_id": manifest.get("run_id"), "publication_scope_id": manifest.get("publication_scope_id")}
            if self._progress_binding is not None:
                _same(observed, self._progress_binding, "BATCH_MANIFEST_RUN_SCOPE_MISMATCH")
            elif type(observed["run_id"]) is str and type(observed["publication_scope_id"]) is str:
                self._progress_binding = observed
        _require(type(manifest) is dict and manifest.get("terminal_artifacts_finalized") is True, "FINALIZED_MANIFEST_REQUIRED")
        _same(manifest.get("native_recovery_policy"), self._policy, "BATCH_MANIFEST_POLICY_MISMATCH")
        for key in ("completed_count", "flushed_count"):
            _require(type(manifest.get(key)) is int and manifest[key] == len(self._ids), "INCOMPLETE_MANIFEST")
        _require(type(manifest.get("pending_count")) is int and manifest["pending_count"] == 0
            and manifest.get("partial_flush_gap") is False, "INCOMPLETE_MANIFEST")
        if "data_kind" in manifest:
            _same(manifest["data_kind"], self._data_kind, "BATCH_DATA_KIND_MISMATCH")
        _same(manifest.get("publication_input_snapshot_sha256"), hashlib.sha256(self._input).hexdigest(), "MANIFEST_INPUT_SNAPSHOT_MISMATCH")
        _same(str(files._absolute_path(manifest.get("output_file"))), self._refs["result"]["path"], "MANIFEST_OUTPUT_MISMATCH")
        descriptor = PublicationScopeDescriptor.from_dict(files._load_json(raw["scope_descriptor"]))
        _same(descriptor.publication_scope_id, manifest.get("publication_scope_id"), "MANIFEST_SCOPE_MISMATCH")
        _same(descriptor.descriptor_sha256, manifest.get("publication_scope_descriptor_sha256"), "MANIFEST_SCOPE_DESCRIPTOR_MISMATCH")
        _same(descriptor.input_file_sha256, hashlib.sha256(self._input).hexdigest(), "SCOPE_INPUT_SHA_MISMATCH")
        _same(list(descriptor.post_ids), self._ids, "SCOPE_TYPED_INPUT_ORDER_MISMATCH")
        _require(type(results) is list and len(results) == len(self._ids), "FINAL_RESULT_FULL_INPUT_REQUIRED")
        _same([r.get("post_id") for r in results], self._ids, "FINAL_RESULT_TYPED_INPUT_ORDER")
        events = files._json_lines(raw["publication_wal"], "publication WAL")
        _require(len(events) == len(results), "FINAL_WAL_FULL_INPUT_REQUIRED")
        files._publication_event(raw["publication_wal"], events[0]["receipt"]["decision_id"], self._posts)
        by_index = {e["receipt"]["input_index"]: e for e in events}
        _, inputs = files._input_snapshot(self._input, "JSONL_POST_COMMENT_V1")
        from expert_main import load_jsonl_posts
        loaded = load_jsonl_posts(self._input_path, snapshot_bytes=self._input)
        _require(len(loaded) == len(results), "NATIVE_LOADER_INPUT_COUNT")
        for index, (post, result) in enumerate(zip(self._posts, results), 1):
            event = by_index[index]
            _same(result, event["result"], "FINAL_RESULT_WAL_ROW_MISMATCH")
            _same(event["receipt"]["publication_scope_id"], descriptor.publication_scope_id, "WAL_SCOPE_MISMATCH")
            # The raw JSONL may contain only content_blocks. Main stores its
            # loader projection as text, public blocks and image URLs separately.
            validate_main_input_projection(post, result)
            _same(result.get("comments"), inputs["post_bindings"][index-1]["result_comments"], "ORIGINAL_COMMENTS_MISMATCH")
            if index in self._captures:
                _same(event["receipt"], self._receipts[index], "BATCH_CAPTURE_COMMIT_MISMATCH")
                self._captures[index].verify_current()
                loaded_post = loaded[index-1]
                _same(self._captures[index].source_snapshot, {"payload": loaded_post.model_dump(mode="json"),
                    "input_truncated": getattr(loaded_post, "_input_truncated", None),
                    "parse_errors": list(getattr(loaded_post, "_parse_errors", ()))}, "BATCH_CAPTURE_SOURCE_MISMATCH")
        self._key_raw = self._read_original(self._key_path, 4096)
        _require(re.fullmatch(rb"[0-9a-fA-F]{64}\s*", self._key_raw) is not None, "BATCH_KEY_FORMAT")
        key = bytes.fromhex(self._key_raw.decode("ascii").strip())
        audits = (files.read_recovery_activation_snapshot(raw["activation_journal"],
            expected_sha256=self._refs["activation_journal"]["sha256"], hmac_key=key,
            expected_scope_id=descriptor.publication_scope_id) if "activation_journal" in raw else ())
        self._base = {"run_id": manifest["run_id"], "publication_scope_id": descriptor.publication_scope_id,
            "input_count": len(results), "input_order_sha256": _sha(self._ids),
            "input_raw_sha256": hashlib.sha256(self._input).hexdigest(),
            "result": self._refs["result"], "manifest": self._refs["manifest"]}
        return raw, results, by_index, audits, key

    def _claim(self):
        _require(not os.path.lexists(self._directory), "BATCH_OUTPUT_EXISTS_NO_RESTART")
        value = {"schema_version": SCHEMA, "base_run": self._base, "policy_sha256": _sha(self._policy),
                 "output_dir": str(self._directory), "restart_policy": "NO_CAPTURE_RESTORE"}
        # Policy/output changes do not create a new batch for the same original scope.
        directory = _safe(self._root / ".recovery_native_batches", self._root)
        directory.mkdir(parents=True, exist_ok=True)
        path = _safe(directory / (self._base["publication_scope_id"] + ".json"), self._root)
        _require(not os.path.lexists(path), "BATCH_ALREADY_CLAIMED_NO_RESTART")
        raw = _bytes(value) + b"\n"
        with path.open("xb") as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        self._anchor_ref = _ref(path, raw)
        _read_ref(self._anchor_ref, self._root, 65536)
        self._directory.mkdir(parents=True, exist_ok=False)
        return self._save(self._directory / "sources/input.jsonl", self._input)

    def _plan(self, index, result, event, audits, raw, input_ref, key):
        proposals = extract_direct_ocr_review_proposals(result)
        _require(len(proposals) == 1, "AMBIGUOUS_SUPPORTED_PROPOSAL" if proposals else "NO_SUPPORTED_PROPOSAL")
        proposal = proposals[0].to_dict()
        candidates = [e for e in audits if e["base_decision_id"] == event["receipt"]["decision_id"]
            and _bytes(e["proposal"]) == _bytes(proposal)]
        _require(len(candidates) == 1, "ACTIVATION_JOURNAL_MISSING" if self._audit_missing_path else "ACTIVATION_NOT_FOUND")
        chosen = candidates[0]
        catalog = result["analysis_result"]["identity"].get("image_evidence_catalog", [])
        items = [x for x in catalog if _sha(x) == proposal["source_payload_sha256"]]
        _require(len(items) == 1, "SOURCE_ITEM_NOT_UNIQUE_IN_RESULT")
        item, query = items[0], proposal["raw_candidate_title"]
        field = item.get("ocr_text")
        _require(type(field) is str and field.count(query) == 1, "SOURCE_SPAN_NOT_UNIQUE")
        start = len(field[:field.index(query)].encode("utf-8"))
        source = {"source_locator": proposal["source_locator"], "source_item_sha256": _sha(item),
            "field_pointer": "/ocr_text", "span_start": start, "span_end": start + len(query.encode("utf-8")),
            "span_unit": "UTF8_FIELD_VALUE", "query": query, "query_sha256": hashlib.sha256(query.encode()).hexdigest(),
            "relation_role": proposal["relation_role"]}
        meta = result.get("run_meta", {})
        router, recovery = meta.get("semantic_review_router_receipt"), meta.get("semantic_recovery_plan_receipt")
        _require(type(router) is dict and type(recovery) is dict, "REVIEW_RECEIPT_MISSING")
        capture = {"schema_version": SOURCE_SCHEMA, "data_kind": self._data_kind,
            "input_raw_sha256": input_ref["sha256"], "input_index": index, "post_id": self._ids[index-1],
            "source_locator": proposal["source_locator"], "item": item}
        rowdir = self._directory / "sources" / str(index)
        additions = {"router": router, "recovery_plan": recovery, "source_capture": capture}
        refs = {**self._refs, "input": input_ref}
        source_bytes = {**raw, "input": self._input}
        for role, value in additions.items():
            payload = _bytes(value) + b"\n"
            refs[role] = self._save(rowdir / (role + ".json"), payload)
            source_bytes[role] = payload
        purpose = recovery.get("plan", {}).get("query_plan", {}).get("purposes", [])
        _require(type(purpose) is list and bool(purpose), "SEMANTIC_QUERY_NOT_ALLOWED")
        plan = build_recovery_provider_plan(source_refs=refs, source_bytes=source_bytes,
            input_format="JSONL_POST_COMMENT_V1", result_pointer=f"/{index-1}", router_pointer="", recovery_plan_pointer="",
            publication_decision_id=event["receipt"]["decision_id"], activation_event_sha256=chosen["event_sha256"],
            source_binding=source, endpoint=self._policy["provider_endpoint"],
            payload={"query": query, "num_results": 10, "purpose": purpose[0]},
            policy=self._policy["provider_policy"], output_dir=str(self._directory / "attempts" / str(index)), hmac_key=key)
        bound = bind_recovery_provider_plan(plan, hmac_key=key)
        reference = self._save(rowdir / "provider_plan.json", _bytes(plan) + b"\n")
        return plan, bound, reference

    def _reserve(self):
        calls = self._policy["provider_policy"]["max_calls"] + self._policy["native_policy"]["max_calls"]
        size = self._policy["provider_policy"]["max_total_response_bytes"] + self._policy["native_policy"]["max_total_response_bytes"]
        duration = self._policy["provider_policy"]["max_elapsed_ms"] + self._policy["native_policy"]["max_elapsed_ms"]
        _require(self._reserved_calls + calls <= self._policy["max_batch_calls"], "BATCH_CALL_BUDGET_EXHAUSTED")
        _require(self._reserved_bytes + size <= self._policy["max_batch_response_bytes"], "BATCH_RESPONSE_BUDGET_EXHAUSTED")
        _require(self._reserved_time + duration <= self._policy["max_batch_elapsed_ms"], "BATCH_TIME_SLOT_EXHAUSTED")
        self._check()
        # Exclusive durable slot before either provider; failures never refund it.
        ordinal = self._reserved_rows + 1
        self._reserved_rows += 1; self._reserved_calls += calls; self._reserved_bytes += size
        self._reserved_time += duration
        self._save(self._directory / "reservations" / f"{ordinal}.json", _bytes({
            "ordinal": ordinal, "calls": calls, "response_bytes": size, "max_elapsed_ms": duration,
            "elapsed_ms": self._last_clock-self._started, "policy_sha256": _sha(self._policy)}) + b"\n")
        self._check()

    def _execute(self, index, bound, plan_ref, key):
        from tools.run_recovery_provider import run_recovery_provider
        from .recovery_native_workflow import run_native_recovery
        row = self._rows[index-1]
        self._reserve()
        row.update(execution_status="RUNNING", client_http_invocations=None, actual_external_calls=None)
        self._emit()
        self._check()
        token = bound.job_id[:40]
        run_recovery_provider(plan_path=Path(plan_ref["path"]), plan_sha256=plan_ref["sha256"],
            hmac_key_path=self._key_path, attempt_id="batch-provider-"+token, session_id="batch-session-"+token,
            root=self._root, dashboard_url=self._dashboard, publish_view=False,
            test_transport=self._transport, cancellation=self._cancel_control, clock=self._clock)
        # Only JSON/files crossed into tools' src namespace; bind again in this namespace.
        bound = bind_recovery_provider_plan(files._load_json(_read_ref(plan_ref, self._root, 65536)), hmac_key=key)
        self._check()
        report = build_provider_report(bound)
        report_path = bound.output_dir / "reports/provider_readback.json"
        report_raw = _read(report_path, self._root, 2*1024*1024)
        _same(files._load_json(report_raw), report, "PROVIDER_STORED_REPORT_MISMATCH")
        row["provider_report_ref"] = _ref(report_path, report_raw)
        _require(report["execution_status"] == "PROVIDER_EVIDENCE_STORED", "PROVIDER_NOT_COMPLETE")
        native = run_native_recovery(bound, self._captures[index], policy=self._policy["native_policy"],
            **deepcopy(self._policy["native_config"]), cancelled=self._cancel_control,
            test_transport=self._transport, clock_ms=self._clock)
        _require(type(native) is dict, "NATIVE_NOT_COMPLETE")
        row["native_output_dir"] = str(bound.output_dir)
        row["native_receipt_ref"] = self._save(bound.output_dir / "reports/native_receipt.json", _bytes(native) + b"\n")
        self._check()
        _require(native.get("status") == "COMPLETED_NATIVE_IO", "NATIVE_NOT_COMPLETE")
        result = native["native_result"]
        _require(result["guard_status"] in {"PUBLISH", "HOLD"}, "NATIVE_GUARD_NOT_EVALUATED")
        ref = native["native_result_ref"]
        native_root = bound.output_dir / "native"
        result_path = native_root / ref["path"]
        native_raw = _read(result_path, self._root, self._policy["native_policy"]["max_response_bytes"])
        _require(hashlib.sha256(native_raw).hexdigest() == ref["sha256"] and len(native_raw) == ref["bytes"], "NATIVE_RESULT_REF_MISMATCH")
        _same(files._load_json(native_raw), result, "NATIVE_STORED_RESULT_MISMATCH")
        journal = native_root / "native_journal.jsonl"
        row.update(execution_status="COMPLETED_NATIVE_IO", guard_outcome=result["guard_status"], reason_codes=[],
            native_result_ref=_ref(result_path, native_raw), native_journal_ref=_ref(journal, _read(journal,self._root,8*1024*1024)),
            client_http_invocations=native["total_client_http_invocations"], actual_external_calls=native["total_actual_external_calls"])

    def summary(self):
        with self._lock:
            rows = deepcopy(self._rows)
            counts = {state: sum(r["execution_status"] == state for r in rows)
                      for state in ("NOT_EXECUTED", "RUNNING", "COMPLETED_NATIVE_IO", "INCOMPLETE")}
            totals = {key: sum(r[key] for r in rows) if all(type(r[key]) is int for r in rows) else None
                      for key in ("client_http_invocations", "actual_external_calls")}
            value = {"schema_version": SCHEMA, "status": self._state, "base_run": deepcopy(self._base),
                "policy": deepcopy(self._policy), "policy_sha256": _sha(self._policy), "data_kind": self._data_kind,
                "rows": rows, "counts": {"input_count": len(rows), **counts, **totals},
                "budget": {"reserved_rows": self._reserved_rows, "reserved_calls": self._reserved_calls,
                    "reserved_response_bytes": self._reserved_bytes, "reserved_elapsed_ms": self._reserved_time, "refunds": 0,
                    "observed_elapsed_ms": (self._last_clock - self._started
                        if self._last_clock is not None and self._started is not None else None),
                    "time_scope": "THROUGH_FINAL_DRAIN_CONTROL_OBSERVATION",
                    "report_publication_io_in_time_scope": False, "total_ram_bytes": None},
                "reason_codes": list(self._reasons), "remote_provider_dispatch_count": None, **_FLAGS}
            value["receipt_sha256"] = _sha(value)
            return value

    def drain(self, *, result_path, manifest_path, publication_wal_path, scope_descriptor_path, activation_journal_path):
        with self._lock:
            if self._finished is not None:
                self._check_sources()
                for name in ("report_ref", "dashboard_reference"):
                    if name in self._finished:
                        _read_ref(self._finished[name], self._root, files.MAX_FILE_BYTES)
                if self._finished.get("dashboard_reference"):
                    from ..monitor.recovery_native_view import read_recovery_native_view
                    _require(read_recovery_native_view(result_path, self._root).get("binding_status") == "BOUND",
                             "BATCH_SAVED_VIEW_CHANGED")
                return deepcopy(self._finished)
            _require(self._state == "COLLECTING", "BATCH_DRAIN_ALREADY_STARTED")
            self._state = "DRAINING"
            try:
                self._started = self._now()
                self._check()
                raw, results, events, audits, key = self._preflight({"result": result_path, "manifest": manifest_path,
                    "publication_wal": publication_wal_path, "scope_descriptor": scope_descriptor_path,
                    "activation_journal": activation_journal_path})
                self._check()
                input_ref = self._claim()
                blocked = None
                for index, row in enumerate(self._rows, 1):
                    try:
                        if index not in self._captures:
                            if row["capture_status"] == "AWAITING_CAPTURE":
                                row.update(capture_status="UNAVAILABLE", reason_codes=["CAPTURE_UNAVAILABLE"])
                            continue
                        if blocked:
                            row["reason_codes"] = [blocked]
                            continue
                        self._check()
                        self._current_index = index
                        plan, bound, ref = self._plan(index, results[index-1], events[index], audits, raw, input_ref, key)
                        row.update(base=plan["base"], provider_plan_ref=ref)
                        self._execute(index, bound, ref, key)
                    except Exception as exc:
                        code = _code(exc)
                        dispatched = row["execution_status"] == "RUNNING"
                        row.update(execution_status="INCOMPLETE" if dispatched else "NOT_EXECUTED",
                                   guard_outcome=None, reason_codes=[code])
                        if dispatched or code.startswith("BATCH_"):
                            blocked = code
                            self._reasons.append(code)
                    finally:
                        self._captures.pop(index, None)
                        self._receipts.pop(index, None)
                        self._current_index = None
                        self._processed.add(index)
                    self._emit()
                try:
                    self._check()
                except NativeRecoveryBatchError as exc:
                    if exc.code not in {"BATCH_CANCELLED", "BATCH_TIME_EXHAUSTED"}:
                        raise
                    # Preserve completed row guards/counts; the batch control outcome
                    # is separate and must survive live/history readback.
                    self._reasons.append(exc.code)
                self._state = "INCOMPLETE" if self._reasons else "COMPLETED"
                report = self.summary()
                report_ref = self._save(self._directory / "batch.json", _bytes(report) + b"\n")
                from ..monitor.recovery_native_view import publish_recovery_native_view
                view_rows = []
                for row in self._rows:
                    view = {k: row[k] for k in ("input_index", "post_id", "capture_status", "execution_status", "reason_codes")}
                    ref = row["provider_report_ref"]
                    native_ref = row["native_receipt_ref"]
                    # A timed-out observation cannot present an earlier completed receipt as success.
                    if row["execution_status"] != "COMPLETED_NATIVE_IO" and native_ref is not None:
                        saved = files._load_json(_read_ref(native_ref, self._root, files.MAX_FILE_BYTES))
                        if saved.get("status") == "COMPLETED_NATIVE_IO":
                            native_ref = None
                    view.update(provider_report_path=ref["path"] if ref else None,
                        native_receipt_path=native_ref["path"] if native_ref else None,
                        native_output_dir=row["native_output_dir"] if native_ref else None,
                        base=row["base"] if ref else None)
                    view_rows.append(view)
                self._check_sources()
                reference = publish_recovery_native_view(result_path, manifest_path, root=self._root,
                    policy=self._policy, rows=view_rows, input_posts=self._posts, batch_report_ref=report_ref)
                self._finished = {**report, "report_ref": report_ref, "dashboard_reference": reference}
                self._finished["receipt_sha256"] = _sha({k: v for k, v in self._finished.items() if k != "receipt_sha256"})
                self._emit(complete=True)
                return deepcopy(self._finished)
            except Exception as exc:
                code = _code(exc)
                self._state = "INCOMPLETE" if self._reserved_rows else "NOT_EXECUTED"
                self._reasons = sorted(set([*self._reasons, code]))
                for row in self._rows:
                    if row["execution_status"] == "RUNNING":
                        row.update(execution_status="INCOMPLETE", guard_outcome=None, reason_codes=[code])
                    elif row["capture_status"] in {"CAPTURED", "AWAITING_CAPTURE"} and row["execution_status"] == "NOT_EXECUTED":
                        row["reason_codes"] = [code]
                self._finished = self.summary()
                try:
                    self._emit(complete=True)
                except Exception:
                    self._reasons = sorted(set([*self._reasons, "BATCH_EVENT_DELIVERY_FAILED"]))
                    self._finished = self.summary()
                return deepcopy(self._finished)
            finally:
                self._captures.clear(); self._receipts.clear()
