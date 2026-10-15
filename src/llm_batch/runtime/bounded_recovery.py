"""선언형 fixture만 소비하는 R6 로컬 복구 시뮬레이션. 외부 실행 권한은 없다."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import time
from typing import Any

from ..measurement.recovery_execution_contract import (
    BoundRecoveryPlan, execution_journal_arguments, validate_plan,
)
from ..ledger.recovery_execution_journal import RecoveryExecutionJournal


MAX_FIXTURE_BYTES = 64 * 1024
MAX_FIXTURE_ACTIONS = 16
MAX_RESPONSES_PER_ACTION = 16
MAX_FIXTURE_DELAY_MS = 3_600_000
FIXTURE_SCHEMA = "recovery_simulation_fixture_v1"
BUDGET_OBSERVATION_SCOPE = "THROUGH_ATTEMPT_TERMINAL_DURABLE_READBACK"
OUTCOMES = frozenset(("SUCCESS", "TRANSIENT_FAILURE", "PERMANENT_FAILURE",
                     "CANCEL_CONFIRMED", "NO_RESPONSE", "CALLBACK_ERROR"))


class BoundedRecoveryError(ValueError):
    """검산/저장 오류이며 공개 성공이나 외부 실행을 허용하지 않는다."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise BoundedRecoveryError(code)


def _json_value(value: Any, depth: int = 0) -> None:
    _require(depth <= 24, "FIXTURE_JSON_DEPTH")
    kind = type(value)
    if value is None or kind in (str, bool, int):
        return
    if kind is float:
        _require(math.isfinite(value), "FIXTURE_NONFINITE_NUMBER")
        return
    if kind is list:
        for item in value:
            _json_value(item, depth + 1)
        return
    _require(kind is dict, "FIXTURE_JSON_TYPE")
    for key, item in value.items():
        _require(type(key) is str, "FIXTURE_JSON_KEY")
        _json_value(item, depth + 1)


def _canonical_bytes(value: Any) -> bytes:
    _json_value(value)
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (ValueError, UnicodeError, OverflowError) as exc:
        raise BoundedRecoveryError("FIXTURE_JSON_ENCODING") from exc


def _fixture_snapshot(fixture: Any) -> tuple[dict, str]:
    """검산 후 별도 JSON 사본을 만든다. 임의 callback을 fixture로 받지 않는다."""
    _require(type(fixture) is dict, "FIXTURE_OBJECT_REQUIRED")
    raw = _canonical_bytes(fixture)
    _require(len(raw) <= MAX_FIXTURE_BYTES, "FIXTURE_BYTE_LIMIT")
    value = json.loads(raw)
    _require(set(value) == {"schema_version", "data_kind", "actions"}, "FIXTURE_SCHEMA_KEYS")
    _require(value["schema_version"] == FIXTURE_SCHEMA
             and value["data_kind"] == "SYNTHETIC_CONTRACT_ONLY", "FIXTURE_SCHEMA_VERSION")
    actions = value["actions"]
    _require(type(actions) is list and 1 <= len(actions) <= MAX_FIXTURE_ACTIONS,
             "FIXTURE_ACTION_LIMIT")
    seen = set()
    for action in actions:
        _require(type(action) is dict and set(action) == {"action_id", "responses"},
                 "FIXTURE_ACTION_SCHEMA")
        action_id = action["action_id"]
        _require(type(action_id) is str and 0 < len(action_id) <= 128
                 and action_id.strip() == action_id and action_id not in seen,
                 "FIXTURE_ACTION_ID")
        seen.add(action_id)
        responses = action["responses"]
        _require(type(responses) is list and 1 <= len(responses) <= MAX_RESPONSES_PER_ACTION,
                 "FIXTURE_RESPONSE_LIMIT")
        for response in responses:
            _require(type(response) is dict and set(response) == {
                "outcome", "delay_ms", "retry_delay_ms", "response"}, "FIXTURE_RESPONSE_SCHEMA")
            _require(type(response["outcome"]) is str and response["outcome"] in OUTCOMES,
                     "FIXTURE_OUTCOME")
            for field in ("delay_ms", "retry_delay_ms"):
                _require(type(response[field]) is int and 0 <= response[field] <= MAX_FIXTURE_DELAY_MS,
                         "FIXTURE_DELAY")
            _require(response["response"] is None or type(response["response"]) is dict,
                     "FIXTURE_RESPONSE_VALUE")
            _require(response["outcome"] == "SUCCESS" or response["response"] is None,
                     "FIXTURE_FAILURE_HAS_RESPONSE")
    return value, hashlib.sha256(raw).hexdigest()


class _SystemClock:
    def monotonic_ms(self) -> int:
        return time.monotonic_ns() // 1_000_000

    def sleep_ms(self, duration_ms: int) -> None:
        time.sleep(duration_ms / 1000)


class _NeverCancelled:
    def requested(self) -> bool:
        return False


class _Observation:
    """clock/cancellation 반환값과 예외를 관측하며 누락을 성공으로 채우지 않는다."""

    def __init__(self, clock, cancellation):
        self.clock = _SystemClock() if clock is None else clock
        self.cancellation = _NeverCancelled() if cancellation is None else cancellation
        self.last_ms = None
        self.started_ms = self.now()

    def now(self) -> int:
        try:
            value = self.clock.monotonic_ms()
        except Exception as exc:
            raise BoundedRecoveryError("CLOCK_CALLBACK_ERROR") from exc
        _require(type(value) is int and value >= 0, "CLOCK_VALUE_INVALID")
        _require(self.last_ms is None or value >= self.last_ms, "CLOCK_REVERSED")
        self.last_ms = value
        return value

    def cancelled(self) -> bool:
        try:
            value = self.cancellation.requested()
        except Exception as exc:
            raise BoundedRecoveryError("CANCELLATION_CALLBACK_ERROR") from exc
        _require(type(value) is bool, "CANCELLATION_VALUE_INVALID")
        return value

    def sleep(self, duration_ms: int) -> None:
        try:
            self.clock.sleep_ms(duration_ms)
        except Exception as exc:
            raise BoundedRecoveryError("CLOCK_SLEEP_CALLBACK_ERROR") from exc


_AUTHORITY = {"execution_mode": "LOCAL_SIMULATION_ONLY", "data_kind": "SYNTHETIC_CONTRACT_ONLY",
              "actual_external_call_count": 0, "public_apply": False,
              "publication_authority": False, "central_db_write": False,
              "tokens": None, "price": None, "formal_kpi_status": "NOT_ESTIMABLE"}
_OUTPUT_KEYS = set(_AUTHORITY) | {"schema_version", "status", "binding", "recovery_session_id",
    "recovery_attempt_id", "actions", "protected_sources_start", "protected_sources_before_output",
    "elapsed_ms_before_output_write", "receipt_sha256"}


def _seal(value: dict) -> dict:
    return {**value, "receipt_sha256": hashlib.sha256(_canonical_bytes(value)).hexdigest()}


def simulation_output_path(bound_plan: BoundRecoveryPlan, attempt_id: str) -> Path:
    _require(type(bound_plan) is BoundRecoveryPlan, "BOUND_PLAN_REQUIRED")
    _identifier(attempt_id)
    basename = hashlib.sha256(attempt_id.encode("utf-8")).hexdigest() + ".json"
    return bound_plan.assert_output_path(bound_plan.output_dir / "attempts" / basename)


def _identifier(value: Any) -> None:
    _require(type(value) is str and 1 <= len(value) <= 128 and value.strip() == value
             and not any(ord(c) < 32 for c in value), "RECOVERY_IDENTIFIER_INVALID")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise BoundedRecoveryError("RECOVERY_IDENTIFIER_INVALID") from exc


class _Stop(Exception):
    def __init__(self, status: str, reason: str):
        self.status, self.reason = status, reason


class _Execution:
    def __init__(self, bound_plan, fixture, journal, attempt_id, session_id, clock, cancellation):
        # 준비 검산·원본 읽기·lock 대기까지 현재 attempt 시간에 포함한다.
        self.observation = _Observation(clock, cancellation)
        _require(type(bound_plan) is BoundRecoveryPlan, "BOUND_PLAN_REQUIRED")
        _require(type(journal) is RecoveryExecutionJournal, "JOURNAL_REQUIRED")
        _identifier(attempt_id)
        _identifier(session_id)
        self.bound = bound_plan
        self.plan = validate_plan(bound_plan.plan)
        self.fixture, fixture_sha = _fixture_snapshot(fixture)
        _require(fixture_sha == self.plan["fixture_sha256"]
                 and _canonical_bytes(self.fixture) == _canonical_bytes(bound_plan.fixture), "FIXTURE_BINDING_MISMATCH")
        _require([a["action_id"] for a in self.fixture["actions"]]
                 == [a["action_id"] for a in self.plan["actions"]], "FIXTURE_ACTION_BINDING_MISMATCH")
        self.arguments = execution_journal_arguments(self.plan)
        self.binding, self.policy = self.arguments["binding"], self.arguments["policy"]
        self.journal = journal
        self.attempt, self.session = attempt_id, session_id
        _require(attempt_id not in (session_id, self.binding["base_attempt_run_id"]), "RECOVERY_ATTEMPT_COLLISION")
        self.dispatched = 0
        self.state = None
        self._paths()
        self.protected_start = self.bound.verify_protected_sources()
        self._snapshot()

    def _paths(self):
        expected = self.bound.assert_output_path(self.bound.journal_path)
        _require(self.journal.path == expected, "JOURNAL_PATH_MISMATCH")
        self.bound.assert_output_path(expected.with_name(expected.name + ".lock"))
        return simulation_output_path(self.bound, self.attempt)

    def _snapshot(self, tx=None):
        state = self.journal.snapshot() if tx is None else tx.snapshot()
        for key in ("binding", "policy", "actions"):
            _require(_canonical_bytes(state[key]) == _canonical_bytes(self.arguments[key]), "JOURNAL_CONFIGURATION_MISMATCH")
        self._fixture_events(state)
        self.state = state
        return state

    def _fixture_events(self, state):
        """과거 실패도 고정 응답과 대조하여 재봉인한 retry 가능성을 받아들이지 않는다."""
        fixtures = {a["action_id"]: a["responses"] for a in self.fixture["actions"]}
        elapsed_by_attempt, cancelled = {}, {}
        for event in state["events"]:
            attempt = event["recovery_attempt_id"]
            elapsed_by_attempt[attempt] = event["elapsed_ms"]
            kind, payload = event["event_type"], event["payload"]
            if kind == "CANCEL_REQUESTED":
                cancelled[attempt] = event["elapsed_ms"]
            if kind not in ("ACTION_RESERVED", "ACTION_TERMINAL"):
                continue
            call = state["calls"][payload["call_id"]]
            responses = fixtures[call["action_id"]]
            ordinal = call["reservation_ordinal"]
            _require(1 <= ordinal <= len(responses), "FIXTURE_RESERVATION_ORDINAL_MISMATCH")
            if kind == "ACTION_RESERVED":
                continue
            expected = responses[ordinal - 1]
            outcome = payload["outcome"]
            observed_delay = event["elapsed_ms"] - call["reserved"]["elapsed_ms"]
            if outcome in {"SUCCESS", "TRANSIENT_FAILURE", "PERMANENT_FAILURE", "CALLBACK_ERROR", "CANCEL_CONFIRMED"}:
                _require(outcome == expected["outcome"] and observed_delay >= expected["delay_ms"],
                         "FIXTURE_TERMINAL_OUTCOME_MISMATCH")
                if outcome == "CANCEL_CONFIRMED" and attempt in cancelled:
                    _require(event["elapsed_ms"] - cancelled[attempt] <= self.policy["cancel_grace_ms"],
                             "CANCEL_CONFIRMATION_AFTER_GRACE")
            if outcome == "SUCCESS":
                _require(type(expected["response"]) is dict, "SUCCESS_RESPONSE_NOT_BOUND")
                raw = _canonical_bytes(expected["response"])
                _require(payload["response_sha256"] == hashlib.sha256(raw).hexdigest()
                         and payload["response_bytes"] == len(raw), "FIXTURE_RESPONSE_HASH_MISMATCH")
            else:
                _require(payload["response_sha256"] is None and payload["response_bytes"] == 0,
                         "FAILURE_RESPONSE_BINDING_MISMATCH")
                if outcome == "TIMEOUT":
                    _require(observed_delay > self.policy["per_action_timeout_ms"]
                             or sum(elapsed_by_attempt.values()) > self.policy["max_elapsed_ms"],
                             "TIMEOUT_WITHOUT_OBSERVED_TIME")
                elif outcome == "NO_RESPONSE":
                    declared_missing = expected["outcome"] == "NO_RESPONSE" or (
                        expected["outcome"] == "SUCCESS" and expected["response"] is None)
                    _require(attempt in cancelled or (declared_missing and observed_delay >= expected["delay_ms"]),
                             "NO_RESPONSE_WITHOUT_EVIDENCE")
                elif outcome == "OUTPUT_LIMIT":
                    _require(expected["outcome"] == "SUCCESS" and type(expected["response"]) is dict
                             and observed_delay >= expected["delay_ms"]
                             and len(_canonical_bytes(expected["response"])) > self.policy["max_output_bytes"],
                             "OUTPUT_LIMIT_WITHOUT_EVIDENCE")

    def _elapsed(self):
        return self.observation.now() - self.observation.started_ms

    def _total_elapsed(self, elapsed):
        prior = self.state["attempts"].get(self.attempt, {}).get("last_elapsed_ms", 0)
        return self.state["consumed_elapsed_ms"] - prior + elapsed

    def _protected(self):
        self._paths()
        try:
            current = self.bound.verify_protected_sources()
        except Exception as exc:
            raise BoundedRecoveryError("PROTECTED_SOURCE_DRIFT") from exc
        _require(current == self.protected_start, "PROTECTED_SOURCE_DRIFT")
        return current

    def _emit(self, tx, kind, payload, *, elapsed_ms=None):
        event = {"event_type": kind, "recovery_session_id": self.session,
                 "recovery_attempt_id": self.attempt,
                 "elapsed_ms": self._elapsed() if elapsed_ms is None else elapsed_ms, "payload": payload}
        result = tx.append(expected_head_sha256=self.state["head_sha256"], event=event)
        self._snapshot(tx)
        return result

    def _cancel(self, tx, reason="CANCELLATION_REQUESTED"):
        if not self.state["attempts"][self.attempt]["cancel_requested"]:
            self._emit(tx, "CANCEL_REQUESTED", {"reason_code": reason})

    def _guard(self, tx, *, before_reservation=False):
        self._snapshot(tx)
        self._protected()
        if self.observation.cancelled() or self.state["attempts"][self.attempt]["cancel_requested"]:
            self._cancel(tx)
            raise _Stop("CANCELLED", "CANCELLATION_REQUESTED")
        total = self._total_elapsed(self._elapsed())
        limit = self.policy["max_elapsed_ms"]
        if total > limit or (before_reservation and total == limit):
            raise _Stop("BUDGET_EXHAUSTED", "TIME_BUDGET_EXHAUSTED")

    def _result(self, status, reasons, *, replayed=False, output=None):
        return _seal({"schema_version": "recovery_execution_result_v1", **_AUTHORITY,
            "status": status, "reason_codes": list(dict.fromkeys(reasons)), "binding": self.binding,
            "recovery_session_id": self.session, "recovery_attempt_id": self.attempt,
            "output": output, "replayed": replayed, "dispatches_this_invocation": self.dispatched,
            "consumed_simulated_dispatches": self.state["consumed_simulated_dispatches"],
            "consumed_elapsed_ms": self.state["consumed_elapsed_ms"],
            "journal_head_sha256": self.state["head_sha256"]})

    def _successful_actions(self):
        result = []
        for action in self.arguments["actions"]:
            calls = [call for call in self.state["calls"].values() if call["action_id"] == action["action_id"]
                     and call["terminal"] and call["terminal"]["payload"]["outcome"] == "SUCCESS"]
            _require(len(calls) == 1, "SUCCESSFUL_ACTION_NOT_BOUND")
            call = calls[0]
            fixture = next(a for a in self.fixture["actions"] if a["action_id"] == action["action_id"])
            ordinal = call["reservation_ordinal"]
            _require(ordinal <= len(fixture["responses"]), "FIXTURE_RESPONSE_MISSING")
            response = fixture["responses"][ordinal - 1]
            _require(response["outcome"] == "SUCCESS" and type(response["response"]) is dict,
                     "SUCCESS_RESPONSE_NOT_BOUND")
            raw = _canonical_bytes(response["response"])
            payload = call["terminal"]["payload"]
            _require(payload["response_sha256"] == hashlib.sha256(raw).hexdigest()
                     and payload["response_bytes"] == len(raw), "SUCCESS_RESPONSE_HASH_MISMATCH")
            result.append({**action, "call_id": call["call_id"], "reservation_ordinal": ordinal,
                           "response": response["response"], "response_sha256": payload["response_sha256"],
                           "response_bytes": payload["response_bytes"]})
        return result

    def _replay(self, attempt):
        _require(attempt["recovery_session_id"] == self.session, "SESSION_MISMATCH")
        terminal = attempt["terminal"]
        if terminal is None:
            return self._result("INCOMPLETE", ["INCOMPLETE_DISPATCH"], replayed=True)
        finalized = attempt.get("finalized")
        if finalized is None:
            return self._result("INCOMPLETE", ["FINALIZATION_MISSING"], replayed=True)
        _require(finalized["payload"]["terminal_event_sha256"] == terminal["event_sha256"]
                 and finalized["payload"]["budget_observation_scope"] == BUDGET_OBSERVATION_SCOPE,
                 "FINALIZATION_BINDING_MISMATCH")
        payload = terminal["payload"]
        final = finalized["payload"]
        output = None
        self._protected()
        if final["status"] == "COMPLETED_SIMULATION":
            _require(payload["status"] == "COMPLETED_SIMULATION", "FINALIZATION_STATUS_PROMOTION")
            path = self._paths()
            with path.open("rb") as stream:
                raw = stream.read(self.policy["max_output_bytes"] + 1)
            _require(path.stat().st_nlink == 1 and len(raw) == payload["output_bytes"]
                     and hashlib.sha256(raw).hexdigest() == payload["output_sha256"], "OUTPUT_READBACK_MISMATCH")
            value = json.loads(raw)
            _require(type(value) is dict and set(value) == _OUTPUT_KEYS
                     and raw == _canonical_bytes(value) + b"\n", "OUTPUT_SCHEMA_OR_SERIALIZATION_MISMATCH")
            digest = value.pop("receipt_sha256", None)
            _require(digest == hashlib.sha256(_canonical_bytes(value)).hexdigest(), "OUTPUT_RECEIPT_SHA_MISMATCH")
            prior_elapsed = max((e["elapsed_ms"] for e in self.state["events"]
                if e["recovery_attempt_id"] == self.attempt and e["sequence"] < terminal["sequence"]), default=0)
            elapsed = value["elapsed_ms_before_output_write"]
            _require(type(elapsed) is int and prior_elapsed <= elapsed <= terminal["elapsed_ms"],
                     "OUTPUT_ELAPSED_MISMATCH")
            _require(value["schema_version"] == "recovery_simulation_output_v1"
                     and value["status"] == "SIMULATION_OUTPUT_CANDIDATE"
                     and value["binding"] == self.binding and value["recovery_attempt_id"] == self.attempt
                     and value["recovery_session_id"] == self.session
                     and value["actions"] == self._successful_actions()
                     and value["protected_sources_start"] == value["protected_sources_before_output"] == self.protected_start
                     and all(type(value[k]) is type(v) and value[k] == v for k, v in _AUTHORITY.items()),
                     "OUTPUT_BINDING_MISMATCH")
            self._protected()
            output = {"path": str(path), "sha256": payload["output_sha256"], "bytes": len(raw)}
        return self._result(final["status"], final["reason_codes"], replayed=True, output=output)

    def _finalize(self, tx, terminal):
        """후보 terminal의 durable readback 이후를 관측한다. 이 관측의 저장은 report I/O다."""
        self._snapshot(tx)
        attempt = self.state["attempts"][self.attempt]
        _require(attempt["terminal"]["event_sha256"] == terminal["event_sha256"]
                 and attempt.get("finalized") is None, "FINALIZATION_NOT_CURRENT")
        candidate = terminal["payload"]
        status, reasons = candidate["status"], list(candidate["reason_codes"])
        observation_errors = []
        try:
            self._protected()
        except Exception:
            observation_errors.append("PROTECTED_SOURCE_DRIFT_AFTER_TERMINAL")
        try:
            cancelled = self.observation.cancelled()
        except Exception:
            cancelled = False
            observation_errors.append("CANCELLATION_OBSERVATION_FAILED_AFTER_TERMINAL")
        # 유효한 시간 관측이 없으면 FINALIZED를 만들지 않는다.
        elapsed = self._elapsed()
        if status == "INCOMPLETE" or self.state["open_call_ids"] or observation_errors:
            status = "INCOMPLETE"
            reasons.extend(observation_errors)
            if self.state["open_call_ids"] and "INCOMPLETE_DISPATCH" not in reasons:
                reasons.append("INCOMPLETE_DISPATCH")
        elif self._total_elapsed(elapsed) > self.policy["max_elapsed_ms"]:
            status = "BUDGET_EXHAUSTED"
            reasons.append("TERMINAL_DURABILITY_TIME_BUDGET_EXHAUSTED")
        elif cancelled and status == "COMPLETED_SIMULATION":
            status = "INCOMPLETE"
            reasons.append("CANCELLATION_DURING_TERMINAL_PERSISTENCE")
        final = self._emit(tx, "ATTEMPT_FINALIZED", {
            "terminal_event_sha256": terminal["event_sha256"], "status": status,
            "reason_codes": list(dict.fromkeys(reasons)), "budget_observation_scope": BUDGET_OBSERVATION_SCOPE},
            elapsed_ms=elapsed)
        return final["payload"]

    def _finish_failure(self, status, reason):
        try:
            with self.journal.transaction() as tx:
                self._snapshot(tx)
                attempt = self.state["attempts"].get(self.attempt)
                if attempt is None or attempt["terminal"] is not None:
                    return self._result("INCOMPLETE", [reason, "FINALIZATION_NOT_ESTABLISHED"])
                # 관측/저장 실패로 열린 예약을 timeout·중단 확인으로 추정하지 않는다.
                if self.state["open_call_ids"]:
                    status = "INCOMPLETE"
                terminal = self._emit(tx, "ATTEMPT_TERMINAL", {"status": status, "reason_codes": [reason],
                                      "output_sha256": None, "output_bytes": 0})
                final = self._finalize(tx, terminal)
            return self._result(final["status"], final["reason_codes"])
        except Exception:
            # 실패한 END/append의 재시각·재봉인으로 완료를 꾸미지 않는다.
            return self._result("INCOMPLETE", [reason, "FAILURE_TERMINAL_NOT_STORED"])

    def _reserve(self, action):
        with self.journal.transaction() as tx:
            self._guard(tx, before_reservation=True)
            state = self.state
            count = state["action_reservations"].get(action["action_id"], 0)
            if state["consumed_simulated_dispatches"] >= self.policy["max_simulated_dispatches"]:
                raise _Stop("BUDGET_EXHAUSTED", "DISPATCH_BUDGET_EXHAUSTED")
            if count == 0 and state["consumed_action_count"] >= self.policy["max_actions"]:
                raise _Stop("BUDGET_EXHAUSTED", "ACTION_BUDGET_EXHAUSTED")
            if count >= self.policy["max_retries_per_action"] + 1:
                raise _Stop("BUDGET_EXHAUSTED", "RETRY_BUDGET_EXHAUSTED")
            if self.policy["per_action_timeout_ms"] == 0:
                raise _Stop("BUDGET_EXHAUSTED", "ACTION_TIME_BUDGET_EXHAUSTED")
            all_calls = [c for c in state["calls"].values() if c["action_id"] == action["action_id"]]
            if all_calls and (all_calls[-1]["terminal"] is None
                             or all_calls[-1]["terminal"]["payload"]["outcome"] != "TRANSIENT_FAILURE"):
                raise _Stop("FAILED", "ACTION_NOT_RETRYABLE")
            fixture = next(a for a in self.fixture["actions"] if a["action_id"] == action["action_id"])
            if count >= len(fixture["responses"]):
                raise _Stop("FAILED", "FIXTURE_RESPONSE_MISSING")
            local = [c for c in all_calls if c["recovery_attempt_id"] == self.attempt]
            call_id = "simulation-call-" + hashlib.sha256(_canonical_bytes({
                "plan_sha256": self.binding["plan_sha256"], "attempt": self.attempt,
                "action_id": action["action_id"], "ordinal": count + 1})).hexdigest()
            saved = self._emit(tx, "ACTION_RESERVED", {**action, "call_id": call_id,
                "reservation_ordinal": count + 1, "retry_ordinal": len(local),
                "previous_call_id": local[-1]["call_id"] if local else None})
        return saved, fixture["responses"][count]

    def _wait_response(self, reserved, response):
        call_id = reserved["payload"]["call_id"]
        with self.journal.transaction() as tx:
            self._guard(tx, before_reservation=True)
            _require(self.state["open_call_ids"] == [call_id], "RESERVATION_NOT_CURRENT")
            if self._elapsed() - reserved["elapsed_ms"] > self.policy["per_action_timeout_ms"]:
                raise _Stop("BUDGET_EXHAUSTED", "ACTION_TIME_BUDGET_EXHAUSTED_BEFORE_DISPATCH")
            # 이 점 이전의 durable append/재검산 실패에서는 fixture dispatch도 0이다.
            self.dispatched += 1
        target = self.observation.now() + response["delay_ms"]
        cancel_started = None
        while True:
            now = self.observation.now()
            elapsed = now - self.observation.started_ms
            if self.observation.cancelled() or self.state["attempts"][self.attempt]["cancel_requested"]:
                if cancel_started is None:
                    cancel_started = now
                    with self.journal.transaction() as tx:
                        self._snapshot(tx)
                        self._cancel(tx)
                if now - cancel_started > self.policy["cancel_grace_ms"]:
                    return "NO_RESPONSE", "CANCEL_NOT_CONFIRMED"
            if self._total_elapsed(elapsed) > self.policy["max_elapsed_ms"] or elapsed - reserved["elapsed_ms"] > self.policy["per_action_timeout_ms"]:
                return "TIMEOUT", "LATE_RESPONSE"
            if now >= target:
                if cancel_started is not None and response["outcome"] != "CANCEL_CONFIRMED":
                    return "NO_RESPONSE", "CANCEL_NOT_CONFIRMED"
                outcome = response["outcome"]
                if outcome == "SUCCESS" and response["response"] is None:
                    return "NO_RESPONSE", "RESPONSE_MISSING"
                return outcome, outcome
            sleep = min(10, target - now)
            self.observation.sleep(sleep)
            _require(self.observation.now() > now, "CLOCK_NOT_ADVANCING")

    def _call(self, action):
        reserved, response = self._reserve(action)
        outcome, reason = self._wait_response(reserved, response)
        with self.journal.transaction() as tx:
            self._snapshot(tx)
            self._protected()
            if self.observation.cancelled() and not self.state["attempts"][self.attempt]["cancel_requested"]:
                self._cancel(tx)
            elapsed = self._elapsed()
            if outcome == "CANCEL_CONFIRMED":
                cancellations = [e for e in self.state["events"] if e["event_type"] == "CANCEL_REQUESTED"
                                 and e["recovery_attempt_id"] == self.attempt]
                if cancellations and elapsed - cancellations[-1]["elapsed_ms"] > self.policy["cancel_grace_ms"]:
                    outcome, reason = "NO_RESPONSE", "CANCEL_NOT_CONFIRMED"
            if outcome == "SUCCESS" and self.state["attempts"][self.attempt]["cancel_requested"]:
                outcome, reason = "NO_RESPONSE", "CANCEL_NOT_CONFIRMED"
            if outcome == "SUCCESS" and (self._total_elapsed(elapsed) > self.policy["max_elapsed_ms"]
                                          or elapsed - reserved["elapsed_ms"] > self.policy["per_action_timeout_ms"]):
                outcome, reason = "TIMEOUT", "LATE_RESPONSE"
            raw = _canonical_bytes(response["response"]) if outcome == "SUCCESS" else None
            if raw is not None and len(raw) > self.policy["max_output_bytes"]:
                outcome, reason, raw = "OUTPUT_LIMIT", "OUTPUT_LIMIT", None
            self._emit(tx, "ACTION_TERMINAL", {"call_id": reserved["payload"]["call_id"], "outcome": outcome,
                "response_sha256": hashlib.sha256(raw).hexdigest() if raw is not None else None,
                "response_bytes": len(raw) if raw is not None else 0})
        if outcome == "SUCCESS":
            return
        if outcome == "TRANSIENT_FAILURE":
            target = self.observation.now() + response["retry_delay_ms"]
            while self.observation.now() < target:
                with self.journal.transaction() as tx:
                    self._guard(tx, before_reservation=True)
                now = self.observation.now()
                if now >= target:
                    break
                self.observation.sleep(min(10, target - now))
                _require(self.observation.now() > now, "CLOCK_NOT_ADVANCING")
            return self._call(action)
        status = {"CANCEL_CONFIRMED": "CANCELLED", "NO_RESPONSE": "INCOMPLETE",
                  "TIMEOUT": "BUDGET_EXHAUSTED"}.get(outcome, "FAILED")
        raise _Stop(status, reason)

    def _complete(self):
        with self.journal.transaction() as tx:
            self._guard(tx)
            path = self._paths()
            payload = _seal({"schema_version": "recovery_simulation_output_v1", **_AUTHORITY,
                "status": "SIMULATION_OUTPUT_CANDIDATE", "binding": self.binding,
                "recovery_session_id": self.session, "recovery_attempt_id": self.attempt,
                "actions": self._successful_actions(), "protected_sources_start": self.protected_start,
                "protected_sources_before_output": self._protected(), "elapsed_ms_before_output_write": self._elapsed()})
            raw = _canonical_bytes(payload) + b"\n"
            if len(raw) > self.policy["max_output_bytes"]:
                raise _Stop("FAILED", "OUTPUT_LIMIT")
            path.parent.mkdir(parents=True, exist_ok=True)
            self._paths()
            with path.open("xb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            self._paths()
            with path.open("rb") as stream:
                stored = stream.read(self.policy["max_output_bytes"] + 1)
            _require(path.stat().st_nlink == 1 and stored == raw, "OUTPUT_READBACK_MISMATCH")
            # 출력 fsync/재판독 시간과 protected END를 성공 terminal 전에 포함한다.
            self._guard(tx)
            output = {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
            terminal = self._emit(tx, "ATTEMPT_TERMINAL", {"status": "COMPLETED_SIMULATION", "reason_codes": [],
                                  "output_sha256": output["sha256"], "output_bytes": output["bytes"]})
            final = self._finalize(tx, terminal)
        return self._result(final["status"], final["reason_codes"],
                            output=output if final["status"] == "COMPLETED_SIMULATION" else None)

    def run(self):
        try:
            with self.journal.transaction() as tx:
                self._snapshot(tx)
                if self.attempt in self.state["attempts"]:
                    return self._replay(self.state["attempts"][self.attempt])
                if self.state["active_attempt_id"] or self.state["open_call_ids"] or any(
                    a.get("finalized") is None or a["finalized"]["payload"]["status"] == "INCOMPLETE"
                    for a in self.state["attempts"].values()):
                    return self._result("INCOMPLETE", ["INCOMPLETE_DISPATCH"])
                self._protected()
                self._emit(tx, "ATTEMPT_STARTED", {})
                self._guard(tx, before_reservation=True)
            for action in self.arguments["actions"]:
                succeeded = any(c["action_id"] == action["action_id"] and c["terminal"]
                    and c["terminal"]["payload"]["outcome"] == "SUCCESS" for c in self.state["calls"].values())
                if not succeeded:
                    self._call(action)
            return self._complete()
        except _Stop as stop:
            return self._finish_failure(stop.status, stop.reason)
        except Exception as exc:
            code = getattr(exc, "code", "EXECUTION_OBSERVATION_OR_STORAGE_ERROR")
            # 검산/저장 오류를 retry하지 않는다. raw 예외 문자열을 출력하지 않는다.
            return self._finish_failure("INCOMPLETE", code if type(code) is str else "EXECUTION_ERROR")


def execute_recovery_simulation(bound_plan, *, fixture, journal, attempt_id, session_id,
                                clock=None, cancellation=None) -> dict:
    """고정 합성 응답만 실행한다. 잘못된 사전 결속은 예약 전에 예외로 거절한다."""
    return _Execution(bound_plan, fixture, journal, attempt_id, session_id, clock, cancellation).run()
