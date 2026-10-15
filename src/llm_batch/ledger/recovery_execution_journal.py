"""별도 로컬 합성 복구 원장: strict replay, 누적 예산, CAS와 durable append.

원본 activation 원장/공개 WAL을 열거나 수리하지 않는다. 읽기 API와 생성자는
파일을 만들지 않으며, 명시적인 transaction/append만 sibling lock을 만든다.
"""
from __future__ import annotations

from contextlib import contextmanager
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import threading
import time
from typing import Any, Mapping

EVENT_SCHEMA = "recovery_execution_event_v1"
STATE_SCHEMA = "recovery_execution_state_v1"
GENESIS_HEAD_SHA256 = "GENESIS"
FINALIZATION_ELAPSED_SCOPE = "THROUGH_ATTEMPT_TERMINAL_DURABLE_READBACK"
MAX_JOURNAL_BYTES = 8 * 1024 * 1024
MAX_EVENT_BYTES = 64 * 1024
MAX_EVENTS = 4096
_ACTION_KINDS = frozenset({"REVALIDATE_SAVED_EVIDENCE", "SIMULATED_TARGETED_SEARCH", "SIMULATED_EXPERT_REVIEW"})
_OUTCOMES = frozenset({"SUCCESS", "TRANSIENT_FAILURE", "PERMANENT_FAILURE", "CANCEL_CONFIRMED", "NO_RESPONSE", "CALLBACK_ERROR", "TIMEOUT", "OUTPUT_LIMIT"})
_TERMINALS = frozenset({"COMPLETED_SIMULATION", "FAILED", "BUDGET_EXHAUSTED", "CANCELLED", "INCOMPLETE"})
_BINDING_KEYS = frozenset({"plan_sha256", "base_sha256", "policy_sha256", "config_sha256", "source_sha256", "fixture_sha256", "publication_scope_id", "input_index", "post_id", "base_attempt_run_id"})
_POLICY_KEYS = frozenset({"max_actions", "max_simulated_dispatches", "max_retries_per_action", "max_elapsed_ms", "per_action_timeout_ms", "cancel_grace_ms", "max_output_bytes", "actual_external_call_budget"})
_INTENT_KEYS = frozenset({"event_type", "recovery_session_id", "recovery_attempt_id", "elapsed_ms", "payload"})
_AUTHORITY = {"execution_mode": "LOCAL_SIMULATION_ONLY", "data_kind": "SYNTHETIC_CONTRACT_ONLY", "actual_external_call_budget": 0, "actual_external_call_count": 0, "public_apply": False, "publication_authority": False, "central_db_write": False}
_EVENT_KEYS = _INTENT_KEYS | _BINDING_KEYS | frozenset(_AUTHORITY) | {"schema_version", "sequence", "prev_event_sha256", "event_sha256"}
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_THREAD_LOCKS: dict[str, threading.Lock] = {}
_THREAD_LOCKS_GUARD = threading.Lock()


class RecoveryExecutionJournalError(ValueError):
    """code는 안정적인 거절 사유이며 원본 수리를 의미하지 않는다."""

    def __init__(self, code: str, detail: str = ""):
        self.code = code
        super().__init__(f"{code}: {detail}" if detail else code)


def _fail(code: str, detail: str = "") -> None:
    raise RecoveryExecutionJournalError(code, detail)


def _json_bytes(value: Any) -> bytes:
    try:
        def check(item):
            if isinstance(item, dict):
                if any(not isinstance(key, str) for key in item):
                    _fail("INVALID_JSON", "non-string object key")
                for child in item.values():
                    check(child)
            elif isinstance(item, list):
                for child in item:
                    check(child)
            elif item is None or type(item) in (str, int, bool):
                return
            elif type(item) is float and math.isfinite(item):
                return
            else:
                _fail("INVALID_JSON", "non-JSON value")
        check(value)
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise RecoveryExecutionJournalError("INVALID_JSON", type(exc).__name__) from exc


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(_json_bytes(value)).hexdigest()


def _keys(value: Any, expected: set | frozenset, label: str) -> dict:
    if not isinstance(value, dict) or set(value) != expected:
        _fail("INVALID_SCHEMA", label)
    return value


def _integer(value: Any, label: str, minimum: int = 0) -> int:
    if type(value) is not int or not minimum <= value <= 2**53 - 1:
        _fail("INVALID_INTEGER", label)
    return value


def _identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip() or len(value) > 128 or any(ord(c) < 32 for c in value):
        _fail("INVALID_IDENTIFIER", label)
    _json_bytes(value)
    return value


def _sha256(value: Any, label: str, nullable: bool = False) -> str | None:
    if nullable and value is None:
        return None
    if not isinstance(value, str) or not _SHA.fullmatch(value):
        _fail("INVALID_SHA256", label)
    return value


def _equal_typed(left: Any, right: Any) -> bool:
    return type(left) is type(right) and left == right


def _configuration(binding: Any, policy: Any, actions: Any) -> tuple[dict, dict, list]:
    binding, policy, actions = copy.deepcopy((binding, policy, actions))
    _keys(binding, _BINDING_KEYS, "binding")
    for key in _BINDING_KEYS:
        if key.endswith("_sha256"):
            _sha256(binding[key], key)
    for key in ("publication_scope_id", "base_attempt_run_id"):
        _identifier(binding[key], key)
    _integer(binding["input_index"], "input_index", 1)
    if type(binding["post_id"]) is int:
        _integer(binding["post_id"], "post_id", 1)
    else:
        _identifier(binding["post_id"], "post_id")
    _keys(policy, _POLICY_KEYS, "policy")
    for key, value in policy.items():
        _integer(value, key)
    if policy["actual_external_call_budget"] != 0:
        _fail("EXTERNAL_EXECUTION_FORBIDDEN")
    if canonical_sha256(policy) != binding["policy_sha256"]:
        _fail("POLICY_SHA256_MISMATCH")
    if not isinstance(actions, list) or not 1 <= len(actions) <= 16:
        _fail("INVALID_ACTIONS")
    seen = set()
    for action in actions:
        _keys(action, {"action_id", "action_kind", "query_sha256"}, "action")
        action_id = _identifier(action["action_id"], "action_id")
        if action_id in seen:
            _fail("DUPLICATE_ACTION_ID")
        seen.add(action_id)
        if not isinstance(action["action_kind"], str) or action["action_kind"] not in _ACTION_KINDS:
            _fail("INVALID_ACTION_KIND")
        _sha256(action["query_sha256"], "query_sha256", action["action_kind"] == "REVALIDATE_SAVED_EVIDENCE")
    _json_bytes([binding, policy, actions])
    return binding, policy, actions


def _empty_state(binding: dict, policy: dict, actions: list) -> dict:
    return {"schema_version": STATE_SCHEMA, "head_sha256": GENESIS_HEAD_SHA256,
            "event_count": 0, "binding": binding, "policy": policy, "actions": actions,
            "events": [], "attempts": {}, "calls": {}, "action_reservations": {},
            "consumed_simulated_dispatches": 0, "consumed_action_count": 0,
            "consumed_elapsed_ms": 0, "open_call_ids": [], "active_attempt_id": None,
            "terminal_attempt_ids": [], "finalized_attempt_ids": [],
            "pending_finalization_attempt_ids": []}


def _output_fields(payload: dict, prefix: str, policy: dict) -> None:
    size = _integer(payload[f"{prefix}_bytes"], f"{prefix}_bytes")
    digest = _sha256(payload[f"{prefix}_sha256"], f"{prefix}_sha256", True)
    if (digest is None) != (size == 0):
        _fail("INVALID_OUTPUT_BINDING", prefix)
    if size > policy["max_output_bytes"]:
        _fail("OUTPUT_LIMIT", prefix)


def _apply_event(state: dict, event: dict) -> None:
    _keys(event, _EVENT_KEYS, "event")
    if len(_json_bytes(event)) > MAX_EVENT_BYTES:
        _fail("EVENT_LIMIT")
    if event["schema_version"] != EVENT_SCHEMA:
        _fail("INVALID_SCHEMA", "event schema")
    if type(event["sequence"]) is not int or event["sequence"] != state["event_count"] + 1:
        _fail("INVALID_SEQUENCE")
    if event["prev_event_sha256"] != state["head_sha256"]:
        _fail("INVALID_HASH_CHAIN")
    for key, expected in state["binding"].items():
        if not _equal_typed(event[key], expected):
            _fail("BINDING_MISMATCH", key)
    for key, expected in _AUTHORITY.items():
        if not _equal_typed(event[key], expected):
            _fail("AUTHORITY_MISMATCH", key)
    _sha256(event["event_sha256"], "event_sha256")
    material = {key: value for key, value in event.items() if key != "event_sha256"}
    if canonical_sha256(material) != event["event_sha256"]:
        _fail("EVENT_SHA256_MISMATCH")
    session_id = _identifier(event["recovery_session_id"], "recovery_session_id")
    attempt_id = _identifier(event["recovery_attempt_id"], "recovery_attempt_id")
    elapsed = _integer(event["elapsed_ms"], "elapsed_ms")
    if attempt_id == state["binding"]["base_attempt_run_id"] or attempt_id == session_id:
        _fail("ATTEMPT_ID_COLLISION")
    event_type, payload = event["event_type"], event["payload"]
    if not isinstance(event_type, str) or not isinstance(payload, dict):
        _fail("INVALID_SCHEMA", "event_type/payload")
    policy = state["policy"]
    attempts = state["attempts"]
    session_ids = {a["recovery_session_id"] for a in attempts.values()}
    if session_id == state["binding"]["base_attempt_run_id"] or session_id in attempts or session_id in state["calls"]:
        _fail("SESSION_ID_COLLISION")
    if event_type == "ATTEMPT_STARTED":
        _keys(payload, set(), event_type)
        if attempt_id in attempts or attempt_id in state["calls"] or attempt_id in session_ids:
            _fail("DUPLICATE_ATTEMPT_ID")
        if state["open_call_ids"] or any(a["finalized"] and a["finalized"]["payload"]["status"] == "INCOMPLETE" for a in attempts.values()):
            _fail("INCOMPLETE_DISPATCH")
        if state["active_attempt_id"] is not None:
            if attempts[state["active_attempt_id"]]["terminal"] is not None:
                _fail("ATTEMPT_NOT_FINALIZED")
            _fail("ATTEMPT_NOT_TERMINAL")
        attempts[attempt_id] = {"recovery_session_id": session_id, "last_elapsed_ms": elapsed,
                                "terminal": None, "finalized": None, "cancel_requested": False, "call_ids": [],
                                "cancel_requested_elapsed_ms": None, "cancel_pending_call_ids": [],
                                "started": copy.deepcopy(event)}
        state["active_attempt_id"] = attempt_id
        state["consumed_elapsed_ms"] += elapsed
    else:
        if attempt_id not in attempts:
            _fail("ATTEMPT_NOT_STARTED")
        attempt = attempts[attempt_id]
        if session_id != attempt["recovery_session_id"]:
            _fail("SESSION_MISMATCH")
        if attempt["finalized"] is not None:
            _fail("ATTEMPT_ALREADY_FINALIZED")
        if attempt["terminal"] is not None and event_type != "ATTEMPT_FINALIZED":
            _fail("ATTEMPT_ALREADY_TERMINAL")
        if event_type == "ATTEMPT_FINALIZED" and attempt["terminal"] is None:
            _fail("ATTEMPT_NOT_TERMINAL")
        if elapsed < attempt["last_elapsed_ms"]:
            _fail("CLOCK_REGRESSION")
        state["consumed_elapsed_ms"] += elapsed - attempt["last_elapsed_ms"]
        attempt["last_elapsed_ms"] = elapsed
        if event_type == "ACTION_RESERVED":
            _keys(payload, {"call_id", "action_id", "action_kind", "query_sha256", "reservation_ordinal", "retry_ordinal", "previous_call_id"}, event_type)
            call_id = _identifier(payload["call_id"], "call_id")
            if call_id in state["calls"] or call_id in attempts or call_id in session_ids or call_id == state["binding"]["base_attempt_run_id"]:
                _fail("DUPLICATE_CALL_ID")
            if state["open_call_ids"]:
                _fail("INCOMPLETE_DISPATCH")
            if attempt["cancel_requested"]:
                _fail("CANCELLATION_REQUESTED")
            if state["consumed_elapsed_ms"] >= policy["max_elapsed_ms"] or policy["per_action_timeout_ms"] == 0:
                _fail("TIME_BUDGET_EXHAUSTED")
            if state["consumed_simulated_dispatches"] >= policy["max_simulated_dispatches"]:
                _fail("DISPATCH_BUDGET_EXHAUSTED")
            action_id = _identifier(payload["action_id"], "action_id")
            action = next((a for a in state["actions"] if a["action_id"] == action_id), None)
            if action is None or any(not _equal_typed(payload[k], action[k]) for k in action):
                _fail("ACTION_BINDING_MISMATCH")
            count = state["action_reservations"].get(action_id, 0)
            if count == 0 and state["consumed_action_count"] >= policy["max_actions"]:
                _fail("ACTION_BUDGET_EXHAUSTED")
            if count >= policy["max_retries_per_action"] + 1:
                _fail("RETRY_BUDGET_EXHAUSTED")
            if _integer(payload["reservation_ordinal"], "reservation_ordinal", 1) != count + 1:
                _fail("INVALID_RESERVATION_ORDINAL")
            action_calls = [c for c in state["calls"].values() if c["action_id"] == action_id]
            if action_calls and action_calls[-1]["terminal"]["payload"]["outcome"] != "TRANSIENT_FAILURE":
                _fail("ACTION_NOT_RETRYABLE")
            local_calls = [c for c in action_calls if c["recovery_attempt_id"] == attempt_id]
            retry = _integer(payload["retry_ordinal"], "retry_ordinal")
            if retry != len(local_calls):
                _fail("INVALID_RETRY_ORDINAL")
            previous = local_calls[-1]["call_id"] if local_calls else None
            if not _equal_typed(payload["previous_call_id"], previous):
                _fail("INVALID_RETRY_LINEAGE")
            state["calls"][call_id] = {**copy.deepcopy(payload), "recovery_attempt_id": attempt_id,
                                       "reserved": copy.deepcopy(event), "terminal": None}
            attempt["call_ids"].append(call_id)
            state["open_call_ids"].append(call_id)
            state["action_reservations"][action_id] = count + 1
            state["consumed_simulated_dispatches"] += 1
            state["consumed_action_count"] += int(count == 0)
        elif event_type == "ACTION_TERMINAL":
            _keys(payload, {"call_id", "outcome", "response_sha256", "response_bytes"}, event_type)
            call_id = _identifier(payload["call_id"], "call_id")
            call = state["calls"].get(call_id)
            if call is None or call["recovery_attempt_id"] != attempt_id:
                _fail("CALL_NOT_RESERVED")
            if call["terminal"] is not None:
                _fail("CALL_ALREADY_TERMINAL")
            outcome = payload["outcome"]
            if not isinstance(outcome, str) or outcome not in _OUTCOMES:
                _fail("INVALID_OUTCOME")
            _output_fields(payload, "response", policy)
            if outcome == "CANCEL_CONFIRMED" and call_id in attempt["cancel_pending_call_ids"]:
                if elapsed > attempt["cancel_requested_elapsed_ms"] + policy["cancel_grace_ms"]:
                    _fail("CANCEL_GRACE_EXCEEDED")
            if outcome == "SUCCESS" and (elapsed - call["reserved"]["elapsed_ms"] > policy["per_action_timeout_ms"] or state["consumed_elapsed_ms"] > policy["max_elapsed_ms"] or attempt["cancel_requested"]):
                _fail("LATE_SUCCESS_FORBIDDEN")
            call["terminal"] = copy.deepcopy(event)
            state["open_call_ids"].remove(call_id)
        elif event_type == "CANCEL_REQUESTED":
            _keys(payload, {"reason_code"}, event_type)
            _identifier(payload["reason_code"], "reason_code")
            if attempt["cancel_requested"]:
                _fail("DUPLICATE_CANCELLATION")
            attempt["cancel_requested"] = True
            attempt["cancel_requested_elapsed_ms"] = elapsed
            attempt["cancel_pending_call_ids"] = list(state["open_call_ids"])
        elif event_type == "ATTEMPT_TERMINAL":
            _keys(payload, {"status", "reason_codes", "output_sha256", "output_bytes"}, event_type)
            status = payload["status"]
            if not isinstance(status, str) or status not in _TERMINALS:
                _fail("INVALID_TERMINAL_STATUS")
            reasons = payload["reason_codes"]
            if not isinstance(reasons, list) or len(reasons) > 32:
                _fail("INVALID_REASON_CODES")
            for reason in reasons:
                _identifier(reason, "reason_code")
            if len(set(reasons)) != len(reasons):
                _fail("INVALID_REASON_CODES")
            _output_fields(payload, "output", policy)
            if status != "COMPLETED_SIMULATION" and payload["output_sha256"] is not None:
                _fail("NONCOMPLETION_OUTPUT_FORBIDDEN")
            if state["open_call_ids"] and status != "INCOMPLETE":
                _fail("INCOMPLETE_DISPATCH")
            uncertain = any(state["calls"][c]["terminal"] and state["calls"][c]["terminal"]["payload"]["outcome"] == "NO_RESPONSE" for c in attempt["call_ids"])
            if uncertain and status != "INCOMPLETE":
                _fail("INCOMPLETE_DISPATCH")
            if status == "CANCELLED" and not attempt["cancel_requested"] and not any(state["calls"][c]["terminal"]["payload"]["outcome"] == "CANCEL_CONFIRMED" for c in attempt["call_ids"]):
                _fail("CANCELLATION_NOT_OBSERVED")
            if status == "CANCELLED":
                for call_id in attempt["cancel_pending_call_ids"]:
                    confirmed = state["calls"][call_id]["terminal"]
                    if confirmed is None or confirmed["payload"]["outcome"] != "CANCEL_CONFIRMED":
                        _fail("CANCELLATION_NOT_CONFIRMED")
                    if confirmed["elapsed_ms"] > attempt["cancel_requested_elapsed_ms"] + policy["cancel_grace_ms"]:
                        _fail("CANCEL_GRACE_EXCEEDED")
            if status == "COMPLETED_SIMULATION":
                succeeded = {c["action_id"] for c in state["calls"].values() if c["terminal"] and c["terminal"]["payload"]["outcome"] == "SUCCESS"}
                if succeeded != {a["action_id"] for a in state["actions"]} or payload["output_sha256"] is None:
                    _fail("COMPLETION_NOT_ESTABLISHED")
                if attempt["cancel_requested"] or state["consumed_elapsed_ms"] > policy["max_elapsed_ms"]:
                    _fail("LATE_SUCCESS_FORBIDDEN")
            attempt["terminal"] = copy.deepcopy(event)
            state["terminal_attempt_ids"].append(attempt_id)
            state["pending_finalization_attempt_ids"].append(attempt_id)
        elif event_type == "ATTEMPT_FINALIZED":
            _keys(payload, {"terminal_event_sha256", "status", "reason_codes", "budget_observation_scope"}, event_type)
            candidate = attempt["terminal"]
            if payload["terminal_event_sha256"] != candidate["event_sha256"]:
                _fail("FINALIZATION_TERMINAL_MISMATCH")
            if payload["budget_observation_scope"] != FINALIZATION_ELAPSED_SCOPE:
                _fail("INVALID_FINALIZATION_SCOPE")
            status, reasons = payload["status"], payload["reason_codes"]
            if not isinstance(status, str) or status not in _TERMINALS:
                _fail("INVALID_TERMINAL_STATUS")
            if not isinstance(reasons, list) or len(reasons) > 32:
                _fail("INVALID_REASON_CODES")
            for reason in reasons:
                _identifier(reason, "reason_code")
            if len(set(reasons)) != len(reasons):
                _fail("INVALID_REASON_CODES")
            original = candidate["payload"]["status"]
            if not set(candidate["payload"]["reason_codes"]).issubset(reasons):
                _fail("FINALIZATION_REASON_MISMATCH")
            if status != original:
                downgrade = (status == "INCOMPLETE" or
                             (status == "BUDGET_EXHAUSTED" and original != "INCOMPLETE"
                              and state["consumed_elapsed_ms"] > policy["max_elapsed_ms"]))
                if not downgrade or not reasons:
                    _fail("INVALID_FINALIZATION_STATUS")
            if status == "COMPLETED_SIMULATION" and state["consumed_elapsed_ms"] > policy["max_elapsed_ms"]:
                _fail("LATE_SUCCESS_FORBIDDEN")
            if state["consumed_elapsed_ms"] > policy["max_elapsed_ms"] and status not in {"BUDGET_EXHAUSTED", "INCOMPLETE"}:
                _fail("FINALIZATION_TIME_BUDGET_EXCEEDED")
            attempt["finalized"] = copy.deepcopy(event)
            state["pending_finalization_attempt_ids"].remove(attempt_id)
            state["finalized_attempt_ids"].append(attempt_id)
            state["active_attempt_id"] = None
        else:
            _fail("INVALID_EVENT_TYPE")
    state["events"].append(copy.deepcopy(event))
    state["head_sha256"] = event["event_sha256"]
    state["event_count"] += 1


def validate_execution_events(events: list, *, binding: Mapping, policy: Mapping, actions: list) -> dict:
    """순수 검산. caller 입력은 바꾸지 않으며 파일/lock/복구 동작이 없다."""
    binding, policy, actions = _configuration(binding, policy, actions)
    if not isinstance(events, list) or len(events) > MAX_EVENTS:
        _fail("EVENT_LIMIT")
    events = copy.deepcopy(events)
    if len(_json_bytes(events)) > MAX_JOURNAL_BYTES:
        _fail("JOURNAL_LIMIT")
    state = _empty_state(binding, policy, actions)
    for event in events:
        _apply_event(state, event)
    return state


def _no_duplicate_keys(pairs: list) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            _fail("DUPLICATE_JSON_KEY", key)
        result[key] = value
    return result


def read_execution_journal(raw_bytes: bytes, *, binding: Mapping, policy: Mapping, actions: list) -> dict:
    """raw JSONL snapshot 검산. 불완전 tail을 삭제/수리하지 않는다."""
    if not isinstance(raw_bytes, bytes):
        _fail("INVALID_JOURNAL_BYTES")
    if len(raw_bytes) > MAX_JOURNAL_BYTES:
        _fail("JOURNAL_LIMIT")
    if raw_bytes and not raw_bytes.endswith(b"\n"):
        _fail("INCOMPLETE_JOURNAL")
    events = []
    for line in raw_bytes.splitlines():
        if not line or len(line) > MAX_EVENT_BYTES:
            _fail("INVALID_EVENT_FRAME")
        try:
            event = json.loads(line.decode("utf-8"), object_pairs_hook=_no_duplicate_keys,
                               parse_constant=lambda _: _fail("INVALID_JSON", "nonfinite"))
        except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
            raise RecoveryExecutionJournalError("INVALID_EVENT_FRAME", type(exc).__name__) from exc
        events.append(event)
        if len(events) > MAX_EVENTS:
            _fail("EVENT_LIMIT")
    return validate_execution_events(events, binding=binding, policy=policy, actions=actions)


def _fsync_directory(path: Path) -> None:
    # Windows CRT는 directory descriptor를 지원하지 않는다. 파일 fsync는 필수다.
    if os.name == "nt":
        return
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _file_identity(info) -> tuple[int, int]:
    return info.st_dev, info.st_ino


def _require_regular(info, label: str) -> None:
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
            or getattr(info, "st_file_attributes", 0) & 0x400):
        _fail("INVALID_" + label + "_PATH")


def _path_info(path: Path, *, label: str, missing_ok: bool = False):
    # lstat은 마지막 파일뿐 아니라 기존 부모의 reparse/symlink도 따라가지 않는다.
    for parent in path.parents:
        try:
            info = parent.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            _fail("INVALID_" + label + "_PATH")
    try:
        info = path.lstat()
    except FileNotFoundError:
        if missing_ok:
            return None
        _fail("FILE_IDENTITY_CHANGED", label)
    _require_regular(info, label)
    return info


def _verify_handle(descriptor: int, path: Path, *, expected, label: str,
                   stable_snapshot: bool = False):
    opened = os.fstat(descriptor)
    _require_regular(opened, label)
    current = _path_info(path, label=label)
    if _file_identity(opened) != _file_identity(current):
        _fail("FILE_IDENTITY_CHANGED", label)
    if expected is not None:
        if _file_identity(opened) != _file_identity(expected):
            _fail("FILE_IDENTITY_CHANGED", label)
        if stable_snapshot and any((info.st_size, info.st_mtime_ns) !=
                                   (expected.st_size, expected.st_mtime_ns)
                                   for info in (opened, current)):
            _fail("FILE_SNAPSHOT_CHANGED", label)
    return opened


def _open_verified(path: Path, flags: int, *, expected, label: str,
                   stable_snapshot: bool = False) -> int:
    flags |= getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    if expected is None:
        # 새 경로의 경쟁 생성은 기존 파일 open으로 전환하지 않는다.
        flags |= os.O_CREAT | os.O_EXCL
    descriptor = os.open(path, flags, 0o600)
    try:
        opened = _verify_handle(descriptor, path, expected=expected, label=label,
                                stable_snapshot=stable_snapshot)
        if expected is None and opened.st_size != 0:
            _fail("FILE_SNAPSHOT_CHANGED", label)
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


@contextmanager
def _exclusive_lock(path: Path):
    key = os.path.normcase(os.path.realpath(path))
    with _THREAD_LOCKS_GUARD:
        thread_lock = _THREAD_LOCKS.setdefault(key, threading.Lock())
    if not thread_lock.acquire(timeout=30):
        _fail("LOCK_TIMEOUT")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = path.with_name(path.name + ".lock")
        # 두 정상 실행자가 최초 lock을 동시에 만들면 새 snapshot으로 재검산한다.
        for retry in range(3):
            previous = _path_info(lock_path, label="LOCK", missing_ok=True)
            try:
                descriptor = _open_verified(lock_path, os.O_RDWR, expected=previous, label="LOCK")
                break
            except FileExistsError:
                if retry == 2:
                    raise
        with os.fdopen(descriptor, "r+b", buffering=0) as handle:
            locked_identity = os.fstat(handle.fileno())
            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                _verify_handle(handle.fileno(), lock_path, expected=locked_identity, label="LOCK")
                handle.seek(0)
                if handle.write(b"\0") != 1:
                    raise OSError("short execution lock initialization")
                handle.flush()
                os.fsync(handle.fileno())
            handle.seek(0)
            deadline = time.monotonic() + 30
            if os.name == "nt":
                import msvcrt
                def acquire():
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                def release():
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                def acquire():
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                def release():
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            while True:
                try:
                    acquire()
                    break
                except OSError as exc:
                    if time.monotonic() >= deadline:
                        raise RecoveryExecutionJournalError("LOCK_TIMEOUT") from exc
                    time.sleep(0.01)
            try:
                _verify_handle(handle.fileno(), lock_path, expected=locked_identity, label="LOCK")
                yield (handle.fileno(), lock_path, locked_identity)
            finally:
                release()
    finally:
        thread_lock.release()


class _JournalTransaction:
    def __init__(self, journal: RecoveryExecutionJournal, lock_binding: tuple):
        self._journal = journal
        self._lock_binding = lock_binding
        self._active = True

    def _require_active(self):
        if not self._active:
            _fail("TRANSACTION_CLOSED")
        descriptor, path, identity = self._lock_binding
        _verify_handle(descriptor, path, expected=identity, label="LOCK")

    def snapshot(self) -> dict:
        self._require_active()
        return self._journal.snapshot()

    def append(self, *, expected_head_sha256: str, event: dict) -> dict:
        self._require_active()
        journal = self._journal
        raw, source_info = journal._read_snapshot()
        state = journal._read(raw)
        if expected_head_sha256 != state["head_sha256"]:
            _fail("JOURNAL_HEAD_CONFLICT")
        event = copy.deepcopy(event)
        _keys(event, _INTENT_KEYS, "event intent")
        material = {**event, **journal._binding, **_AUTHORITY, "schema_version": EVENT_SCHEMA,
                    "sequence": state["event_count"] + 1, "prev_event_sha256": state["head_sha256"]}
        saved = {**material, "event_sha256": canonical_sha256(material)}
        validate_execution_events(state["events"] + [saved], binding=journal._binding, policy=journal._policy, actions=journal._actions)
        frame = _json_bytes(saved) + b"\n"
        if len(raw) + len(frame) > MAX_JOURNAL_BYTES:
            _fail("JOURNAL_LIMIT")
        self._require_active()
        descriptor = _open_verified(journal.path, os.O_WRONLY | os.O_APPEND,
                                    expected=source_info, label="JOURNAL", stable_snapshot=True)
        try:
            opened_identity = os.fstat(descriptor)
            offset = 0
            while offset < len(frame):
                self._require_active()
                current = _verify_handle(descriptor, journal.path, expected=opened_identity,
                                         label="JOURNAL", stable_snapshot=offset == 0)
                if current.st_size != len(raw) + offset:
                    _fail("FILE_SNAPSHOT_CHANGED", "JOURNAL")
                written = os.write(descriptor, frame[offset:])
                if written <= 0:
                    raise OSError("short execution journal write")
                offset += written
            os.fsync(descriptor)
            _verify_handle(descriptor, journal.path, expected=opened_identity, label="JOURNAL")
        finally:
            os.close(descriptor)
        _fsync_directory(journal.path.parent)
        actual = journal._read_bytes()
        if actual != raw + frame:
            _fail("APPEND_READBACK_MISMATCH")
        replay = journal._read(actual)
        if replay["head_sha256"] != saved["event_sha256"]:
            _fail("APPEND_READBACK_MISMATCH")
        return copy.deepcopy(saved)


class RecoveryExecutionJournal:
    """동일 plan의 지정 path. 생성자는 I/O 없이 설정만 고정한다."""

    def __init__(self, path: str | Path, *, binding: Mapping, policy: Mapping, actions: list):
        self.path = Path(os.path.abspath(path))
        self._binding, self._policy, self._actions = _configuration(binding, policy, actions)

    def _read_snapshot(self) -> tuple[bytes, Any]:
        before = _path_info(self.path, label="JOURNAL", missing_ok=True)
        if before is None:
            return b"", None
        descriptor = _open_verified(self.path, os.O_RDONLY, expected=before,
                                    label="JOURNAL", stable_snapshot=True)
        with os.fdopen(descriptor, "rb") as handle:
            raw = handle.read(MAX_JOURNAL_BYTES + 1)
            _verify_handle(handle.fileno(), self.path, expected=before,
                           label="JOURNAL", stable_snapshot=True)
        if len(raw) > MAX_JOURNAL_BYTES:
            _fail("JOURNAL_LIMIT")
        return raw, before

    def _read_bytes(self) -> bytes:
        return self._read_snapshot()[0]

    def _read(self, raw: bytes) -> dict:
        return read_execution_journal(raw, binding=self._binding, policy=self._policy, actions=self._actions)

    def snapshot(self) -> dict:
        return self._read(self._read_bytes())

    @contextmanager
    def transaction(self):
        with _exclusive_lock(self.path) as lock_binding:
            tx = _JournalTransaction(self, lock_binding)
            try:
                yield tx
            finally:
                tx._active = False

    def append(self, *, expected_head_sha256: str, event: dict) -> dict:
        with self.transaction() as tx:
            return tx.append(expected_head_sha256=expected_head_sha256, event=event)
