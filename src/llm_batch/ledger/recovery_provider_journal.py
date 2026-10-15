"""실제 HTTP 경계의 별도 영속 원장. 합성 실행 원장의 권한/상태는 바꾸지 않는다."""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re

from . import recovery_execution_journal as files

SCHEMA = "recovery_provider_event_v1"
STATE_SCHEMA = "recovery_provider_state_v1"
MAX_JOURNAL_BYTES = 8 * 1024 * 1024
MAX_EVENT_BYTES = 64 * 1024
MAX_EVENTS = 128
GENESIS = "GENESIS"
BINDING_KEYS = {"plan_sha256", "base_sha256", "source_sha256", "config_sha256", "policy_sha256",
                "publication_scope_id", "input_index", "post_id", "base_attempt_run_id"}
POLICY_KEYS = {"max_calls", "max_elapsed_ms", "request_timeout_ms", "max_response_bytes", "max_total_response_bytes"}
REQUEST_KEYS = {"request_id", "kind", "body_sha256", "endpoint_sha256"}
FLAGS = {"publication_authority": False, "public_apply": False, "central_db_write": False}
SHA = re.compile(r"[0-9a-f]{64}\Z")


class RecoveryProviderJournalError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def require(value, code):
    if not value:
        raise RecoveryProviderJournalError(code)


def canonical_bytes(value):
    return files._json_bytes(value)


def canonical_sha256(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _keys(value, keys):
    require(type(value) is dict and set(value) == set(keys), "SCHEMA_INVALID")


def _integer(value, minimum=0, maximum=2**53-1):
    require(type(value) is int and minimum <= value <= maximum, "INTEGER_INVALID")


def _id(value):
    require(type(value) is str and 0 < len(value) <= 128 and value.strip() == value
            and all(ord(c) >= 32 for c in value), "IDENTIFIER_INVALID")


def _sha(value):
    require(type(value) is str and SHA.fullmatch(value) is not None, "SHA_INVALID")


def configuration(binding, policy, requests):
    binding, policy, requests = deepcopy((binding, policy, requests))
    _keys(binding, BINDING_KEYS)
    for key in BINDING_KEYS:
        if key.endswith("_sha256"):
            _sha(binding[key])
    for key in ("publication_scope_id", "base_attempt_run_id"):
        _id(binding[key])
    _integer(binding["input_index"], 1)
    if type(binding["post_id"]) is int:
        _integer(binding["post_id"])
    else:
        _id(binding["post_id"])
    _keys(policy, POLICY_KEYS)
    for key, value in policy.items():
        _integer(value, 0 if key in {"max_calls", "max_total_response_bytes"} else 1)
    require(policy["max_response_bytes"] <= 16 * 1024 * 1024, "RESPONSE_HARD_LIMIT")
    require(canonical_sha256(policy) == binding["policy_sha256"], "POLICY_SHA_MISMATCH")
    require(type(requests) is list and 1 <= len(requests) <= 16, "REQUESTS_INVALID")
    seen = set()
    for request in requests:
        _keys(request, REQUEST_KEYS)
        _id(request["request_id"])
        require(request["request_id"] not in seen, "REQUEST_ID_DUPLICATE")
        seen.add(request["request_id"])
        require(request["kind"] in ("MCP_SEARCH", "OPENAI_CHAT"), "REQUEST_KIND_INVALID")
        _sha(request["body_sha256"]); _sha(request["endpoint_sha256"])
    canonical_bytes([binding, policy, requests])
    return binding, policy, requests


def request_identity(binding, policy, request):
    value = {"job_id": binding["plan_sha256"], **request, "policy_sha256": canonical_sha256(policy)}
    value["request_sha256"] = canonical_sha256(value)
    return value


def _ref(value):
    _keys(value, {"path", "sha256", "bytes"})
    require(type(value["path"]) is str and re.fullmatch(r"responses/[0-9a-f]{64}\.(?:bin|json)", value["path"]), "RESPONSE_PATH_INVALID")
    _sha(value["sha256"]); _integer(value["bytes"])


def _state(binding, policy, requests, journal_path):
    return {"schema_version": STATE_SCHEMA, "binding": binding, "policy": policy, "requests": requests,
            "journal_path_sha256": hashlib.sha256(os.path.normcase(os.path.abspath(journal_path)).encode("utf-8")).hexdigest(),
            "configuration_sha256": canonical_sha256({"binding": binding, "policy": policy, "requests": requests}),
            "head_sha256": GENESIS, "events": [], "started": None, "last_elapsed_ms": 0,
            "calls": {}, "open_request_id": None, "blocked_reason": None,
            "budget": {"reservations_consumed": 0, "reserved_response_bytes": 0,
                       "observed_response_bytes": 0, "transport_invocations": 0, "actual_external_calls": 0}}


def _apply(state, event):
    _keys(event, {"schema_version", "sequence", "prev_event_sha256", "configuration_sha256", "journal_path_sha256",
                  "event_type", "elapsed_ms", "payload", "event_sha256"})
    require(event["schema_version"] == SCHEMA, "EVENT_SCHEMA_INVALID")
    require(type(event["sequence"]) is int and event["sequence"] == len(state["events"]) + 1, "EVENT_SEQUENCE_INVALID")
    require(event["prev_event_sha256"] == state["head_sha256"], "EVENT_CHAIN_INVALID")
    for key in ("configuration_sha256", "journal_path_sha256"):
        require(event[key] == state[key], "EVENT_BINDING_MISMATCH")
    require(event["event_sha256"] == canonical_sha256({k:v for k,v in event.items() if k != "event_sha256"}), "EVENT_SHA_MISMATCH")
    elapsed, kind, payload = event["elapsed_ms"], event["event_type"], event["payload"]
    _integer(elapsed)
    require(elapsed >= state["last_elapsed_ms"], "CLOCK_REGRESSED")
    require(type(payload) is dict, "EVENT_PAYLOAD_INVALID")
    policy, budget = state["policy"], state["budget"]
    if kind == "JOB_STARTED":
        _keys(payload, {"owner_epoch", "transport_mode"})
        _id(payload["owner_epoch"])
        require(payload["transport_mode"] in {"TEST_DOUBLE", "HTTPX_SINGLE_REQUEST"}, "TRANSPORT_MODE_INVALID")
        require(state["started"] is None and not state["events"], "JOB_ALREADY_STARTED")
        state["started"] = event
    else:
        require(state["started"] is not None, "JOB_NOT_STARTED")
        if kind == "REQUEST_RESERVED":
            _keys(payload, {"request_id", "request_sha256", "reservation_id", "ordinal", "response_bytes_reserved",
                            "request_started_elapsed_ms", "request_deadline_elapsed_ms"})
            require(state["open_request_id"] is None and state["blocked_reason"] is None, "INCOMPLETE_DISPATCH")
            rid = payload["request_id"]
            require(type(rid) is str and rid not in state["calls"], "REQUEST_ALREADY_RESERVED")
            expected = next((r for r in state["requests"] if r["request_id"] == rid), None)
            require(expected is not None, "REQUEST_NOT_PLANNED")
            require(payload["request_sha256"] == request_identity(state["binding"], policy, expected)["request_sha256"], "REQUEST_SHA_MISMATCH")
            _id(payload["reservation_id"])
            require(all(c["reserved"]["payload"]["reservation_id"] != payload["reservation_id"] for c in state["calls"].values()), "RESERVATION_ID_REUSED")
            _integer(payload["ordinal"], 1)
            require(payload["ordinal"] == budget["reservations_consumed"] + 1, "RESERVATION_ORDINAL_INVALID")
            require(budget["reservations_consumed"] < policy["max_calls"], "CALL_BUDGET_EXHAUSTED")
            remaining = policy["max_total_response_bytes"] - budget["reserved_response_bytes"]
            expected_bytes = policy["max_response_bytes"]
            require(remaining >= expected_bytes and payload["response_bytes_reserved"] == expected_bytes
                    and type(payload["response_bytes_reserved"]) is int, "OUTPUT_BUDGET_EXHAUSTED")
            started, deadline = payload["request_started_elapsed_ms"], payload["request_deadline_elapsed_ms"]
            _integer(started); _integer(deadline)
            require(started <= elapsed and deadline == min(policy["max_elapsed_ms"], started + policy["request_timeout_ms"]),
                    "REQUEST_DEADLINE_INVALID")
            require(elapsed < deadline, "TIME_BUDGET_EXHAUSTED")
            budget["reservations_consumed"] += 1
            budget["reserved_response_bytes"] += expected_bytes
            state["calls"][rid] = {"reserved": event, "terminal": None, "finalized": None}
            state["open_request_id"] = rid
        elif kind == "REQUEST_TERMINAL":
            _keys(payload, {"request_id", "status", "response_ref", "transport_ref", "transport_receipt_sha256",
                            "observed_response_bytes", "transport_invocations", "actual_external_calls"})
            rid = payload["request_id"]
            require(type(rid) is str and rid == state["open_request_id"], "REQUEST_NOT_RESERVED")
            call = state["calls"][rid]
            require(call["terminal"] is None, "TERMINAL_ALREADY_RECORDED")
            _id(payload["status"]); _sha(payload["transport_receipt_sha256"]); _ref(payload["transport_ref"])
            if payload["response_ref"] is not None:
                _ref(payload["response_ref"])
            for key in ("observed_response_bytes", "transport_invocations", "actual_external_calls"):
                _integer(payload[key])
            require(payload["transport_invocations"] <= 1, "RETRY_FORBIDDEN")
            expected_actual = payload["transport_invocations"] if state["started"]["payload"]["transport_mode"] == "HTTPX_SINGLE_REQUEST" else 0
            require(payload["actual_external_calls"] == expected_actual, "ACTUAL_CALL_SCOPE_INVALID")
            # iter_raw may expose one bounded over-limit chunk. This is observed, never stored as success.
            allowance = call["reserved"]["payload"]["response_bytes_reserved"]
            require(payload["observed_response_bytes"] <= allowance + 16384, "OBSERVED_BYTES_UNBOUNDED")
            if payload["status"] == "SUCCESS":
                require(payload["response_ref"] is not None and payload["transport_invocations"] == 1
                        and payload["response_ref"]["bytes"] == payload["observed_response_bytes"] <= allowance,
                        "SUCCESS_RESPONSE_MISSING")
                require(elapsed < call["reserved"]["payload"]["request_deadline_elapsed_ms"], "LATE_SUCCESS")
            for key in ("observed_response_bytes", "transport_invocations", "actual_external_calls"):
                budget[key] += payload[key]
            call["terminal"] = event
        elif kind == "REQUEST_FINALIZED":
            _keys(payload, {"request_id", "terminal_sha256", "status", "reason_codes"})
            rid = payload["request_id"]
            require(type(rid) is str and rid == state["open_request_id"], "REQUEST_NOT_RESERVED")
            call = state["calls"][rid]
            require(call["terminal"] is not None and call["finalized"] is None, "TERMINAL_NOT_READY")
            require(payload["terminal_sha256"] == call["terminal"]["event_sha256"], "TERMINAL_SHA_MISMATCH")
            _id(payload["status"])
            require(type(payload["reason_codes"]) is list and len(payload["reason_codes"]) <= 8, "REASONS_INVALID")
            for reason in payload["reason_codes"]:
                _id(reason)
            terminal_status = call["terminal"]["payload"]["status"]
            if payload["status"] == "SUCCESS":
                require(terminal_status == "SUCCESS" and not payload["reason_codes"], "SUCCESS_PROMOTION")
                require(elapsed < call["reserved"]["payload"]["request_deadline_elapsed_ms"], "LATE_SUCCESS")
            else:
                require(bool(payload["reason_codes"]), "FAILURE_REASON_MISSING")
                if terminal_status != "SUCCESS":
                    require(payload["status"] == terminal_status, "TERMINAL_STATUS_CHANGED")
                state["blocked_reason"] = payload["status"]
            call["finalized"] = event
            state["open_request_id"] = None
        else:
            require(False, "EVENT_TYPE_INVALID")
    state["events"].append(event)
    state["head_sha256"] = event["event_sha256"]
    state["last_elapsed_ms"] = elapsed


def read_provider_journal(raw, *, binding, policy, requests, journal_path):
    """순수 읽기. 손상/미완성 tail을 지우거나 응답을 추정하지 않는다."""
    binding, policy, requests = configuration(binding, policy, requests)
    require(type(raw) is bytes and len(raw) <= MAX_JOURNAL_BYTES, "JOURNAL_BYTE_LIMIT")
    state = _state(binding, policy, requests, journal_path)
    if not raw:
        return state
    require(raw.endswith(b"\n"), "INCOMPLETE_JOURNAL")
    lines = raw.splitlines()
    require(len(lines) <= MAX_EVENTS, "EVENT_COUNT_LIMIT")
    for line in lines:
        require(0 < len(line) <= MAX_EVENT_BYTES, "EVENT_BYTE_LIMIT")
        try:
            value = json.loads(line.decode("utf-8"), object_pairs_hook=files._no_duplicate_keys,
                               parse_constant=lambda _: require(False, "NONFINITE_JSON"))
        except (UnicodeError, ValueError, RecursionError) as exc:
            raise RecoveryProviderJournalError("JOURNAL_JSON_INVALID") from exc
        require(canonical_bytes(value) == line, "EVENT_CANONICAL_MISMATCH")
        _apply(state, value)
    return state


class _Transaction:
    def __init__(self, journal, lock):
        self.journal, self.lock, self.active = journal, lock, True

    def _guard(self):
        require(self.active, "TRANSACTION_CLOSED")
        fd, path, expected = self.lock
        files._verify_handle(fd, path, expected=expected, label="LOCK")

    def snapshot(self):
        self._guard()
        return self.journal.snapshot()

    def append(self, *, expected_head_sha256, event):
        self._guard()
        raw, info = self.journal._raw()
        state = self.journal._parse(raw)
        require(expected_head_sha256 == state["head_sha256"], "JOURNAL_HEAD_CONFLICT")
        _keys(event, {"event_type", "elapsed_ms", "payload"})
        saved = {**deepcopy(event), "schema_version": SCHEMA, "sequence": len(state["events"]) + 1,
                 "prev_event_sha256": state["head_sha256"], "configuration_sha256": state["configuration_sha256"],
                 "journal_path_sha256": state["journal_path_sha256"]}
        saved["event_sha256"] = canonical_sha256(saved)
        frame = canonical_bytes(saved) + b"\n"
        self.journal._parse(raw + frame)
        self._guard()
        fd = files._open_verified(self.journal.path, os.O_WRONLY | os.O_APPEND,
                                  expected=info, label="PROVIDER_JOURNAL", stable_snapshot=True)
        try:
            opened = os.fstat(fd)
            offset = 0
            while offset < len(frame):
                self._guard()
                current = files._verify_handle(fd, self.journal.path, expected=opened,
                                               label="PROVIDER_JOURNAL", stable_snapshot=offset == 0)
                require(current.st_size == len(raw) + offset, "JOURNAL_SIZE_CHANGED")
                n = os.write(fd, frame[offset:]); require(n > 0, "JOURNAL_SHORT_WRITE")
                offset += n
            os.fsync(fd)
            files._verify_handle(fd, self.journal.path, expected=opened, label="PROVIDER_JOURNAL")
        finally:
            os.close(fd)
        files._fsync_directory(self.journal.path.parent)
        actual, _ = self.journal._raw()
        require(actual == raw + frame, "APPEND_READBACK_MISMATCH")
        require(self.journal._parse(actual)["head_sha256"] == saved["event_sha256"], "APPEND_READBACK_MISMATCH")
        return deepcopy(saved)


class RecoveryProviderJournal:
    """생성자는 쓰지 않는다. 원장 경로까지 event에 결속한다."""
    def __init__(self, path, *, binding, policy, requests):
        self.path = Path(os.path.abspath(path))
        self.binding, self.policy, self.requests = configuration(binding, policy, requests)

    def _raw(self):
        info = files._path_info(self.path, label="PROVIDER_JOURNAL", missing_ok=True)
        if info is None:
            return b"", None
        fd = files._open_verified(self.path, os.O_RDONLY, expected=info, label="PROVIDER_JOURNAL", stable_snapshot=True)
        with os.fdopen(fd, "rb") as stream:
            raw = stream.read(MAX_JOURNAL_BYTES + 1)
            files._verify_handle(stream.fileno(), self.path, expected=info, label="PROVIDER_JOURNAL", stable_snapshot=True)
        require(len(raw) <= MAX_JOURNAL_BYTES, "JOURNAL_BYTE_LIMIT")
        return raw, info

    def _parse(self, raw):
        return read_provider_journal(raw, binding=self.binding, policy=self.policy,
                                     requests=self.requests, journal_path=self.path)

    def snapshot(self):
        return self._parse(self._raw()[0])

    @contextmanager
    def transaction(self):
        files._path_info(self.path, label="PROVIDER_JOURNAL", missing_ok=True)
        with files._exclusive_lock(self.path) as lock:
            tx = _Transaction(self, lock)
            try:
                yield tx
            finally:
                tx.active = False

    def append(self, *, expected_head_sha256, event):
        with self.transaction() as tx:
            return tx.append(expected_head_sha256=expected_head_sha256, event=event)
