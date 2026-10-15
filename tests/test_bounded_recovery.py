"""R6 선언형 fixture·상태기계의 로컬 합성 계약 시험. 실제 외부 실행은 없다."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import threading

import pytest

from src.llm_batch.runtime import bounded_recovery as runtime
from src.llm_batch.ledger import recovery_execution_journal as ledger
from src.llm_batch.measurement.recovery_execution_contract import execution_journal_arguments
from recovery_execution_fixtures import make_recovery_fixture


def fixture_responses(*responses, action_id="synthetic-action-1"):
    if not responses:
        responses = ({"outcome": "SUCCESS", "delay_ms": 0, "retry_delay_ms": 0,
                      "response": {"text": "합성 계약 응답", "public_apply": False}},)
    return {"schema_version": "recovery_simulation_fixture_v1",
            "data_kind": "SYNTHETIC_CONTRACT_ONLY",
            "actions": [{"action_id": action_id, "responses": list(deepcopy(responses))}]}


class Clock:
    def __init__(self, start=1000):
        self.value = start
        self.sleeps = []

    def monotonic_ms(self):
        return self.value

    def sleep_ms(self, duration_ms):
        self.sleeps.append(duration_ms)
        self.value += duration_ms


class Cancellation:
    def __init__(self, requested=False):
        self.value = requested

    def requested(self):
        return self.value


def test_fixture_is_frozen_json_with_stable_semantics_and_no_input_mutation():
    value = fixture_responses()
    original = deepcopy(value)
    frozen, digest = runtime._fixture_snapshot(value)
    expected = hashlib.sha256(json.dumps(original, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    assert digest == expected and value == original
    value["actions"][0]["responses"][0]["response"]["text"] = "외부 변경"
    assert frozen == original


@pytest.mark.parametrize("invalid", [lambda: None, object(), {"backend": lambda: None}])
def test_callable_or_backend_registration_cannot_be_a_fixture(invalid):
    with pytest.raises(runtime.BoundedRecoveryError):
        runtime._fixture_snapshot(invalid)


@pytest.mark.parametrize("field,value", [
    ("delay_ms", True), ("delay_ms", 1.0), ("delay_ms", -1),
    ("retry_delay_ms", None), ("retry_delay_ms", runtime.MAX_FIXTURE_DELAY_MS + 1),
    ("outcome", "ACTUAL_MODEL"), ("response", float("nan")),
    ("response", {"bad": float("inf")}), ("response", {"callback": lambda: None}),
], ids=("bool-delay", "float-delay", "negative-delay", "null-retry", "large-retry",
        "unknown-outcome", "nan", "infinity", "nested-callable"))
def test_fixture_rejects_non_declarative_or_ambiguous_response(field, value):
    fixture = fixture_responses()
    fixture["actions"][0]["responses"][0][field] = value
    with pytest.raises(runtime.BoundedRecoveryError):
        runtime._fixture_snapshot(fixture)


def test_fixture_rejects_unknown_fields_duplicate_actions_failure_payload_and_bounds():
    cases = []
    extra = fixture_responses()
    extra["shell"] = "synthetic forbidden command"
    cases.append(extra)
    duplicate = fixture_responses()
    duplicate["actions"].append(deepcopy(duplicate["actions"][0]))
    cases.append(duplicate)
    failure = fixture_responses()
    failure["actions"][0]["responses"][0]["outcome"] = "PERMANENT_FAILURE"
    cases.append(failure)
    large = fixture_responses()
    large["actions"][0]["responses"][0]["response"]["text"] = "가" * runtime.MAX_FIXTURE_BYTES
    cases.append(large)
    responses = fixture_responses()
    responses["actions"][0]["responses"] *= runtime.MAX_RESPONSES_PER_ACTION + 1
    cases.append(responses)
    for fixture in cases:
        with pytest.raises(runtime.BoundedRecoveryError):
            runtime._fixture_snapshot(fixture)


def response(outcome="SUCCESS", *, delay=0, retry_delay=0, text="합성 응답"):
    return {"outcome": outcome, "delay_ms": delay, "retry_delay_ms": retry_delay,
            "response": {"text": text} if outcome == "SUCCESS" else None}


def case(root, **kwargs):
    value = make_recovery_fixture(root, **kwargs)
    value["journal"] = ledger.RecoveryExecutionJournal(value["bound"].journal_path,
        **execution_journal_arguments(value["plan"]))
    return value


def execute(value, *, attempt="recovery-attempt-1", session="recovery-session-1", clock=None,
            cancellation=None, fixture=None, journal=None):
    return runtime.execute_recovery_simulation(value["bound"],
        fixture=value["fixture"] if fixture is None else fixture,
        journal=value["journal"] if journal is None else journal, attempt_id=attempt, session_id=session,
        clock=Clock() if clock is None else clock, cancellation=cancellation)


def protected_raw(value):
    return {name: Path(ref["path"]).read_bytes() for name, ref in value["artifact_refs"].items()}


def append(value, kind, payload, *, elapsed=0, attempt="old-attempt", session="old-session"):
    journal = value["journal"]
    return journal.append(expected_head_sha256=journal.snapshot()["head_sha256"], event={
        "event_type": kind, "recovery_session_id": session, "recovery_attempt_id": attempt,
        "elapsed_ms": elapsed, "payload": payload})


def reserve_old(value, *, terminal=True, elapsed=7):
    append(value, "ATTEMPT_STARTED", {})
    action = execution_journal_arguments(value["plan"])["actions"][0]
    append(value, "ACTION_RESERVED", {**action, "call_id": "old-call", "reservation_ordinal": 1,
        "retry_ordinal": 0, "previous_call_id": None})
    if terminal:
        append(value, "ACTION_TERMINAL", {"call_id": "old-call", "outcome": "TRANSIENT_FAILURE",
            "response_sha256": None, "response_bytes": 0}, elapsed=elapsed)
        candidate = append(value, "ATTEMPT_TERMINAL", {"status": "FAILED", "reason_codes": ["SYNTHETIC_FAILURE"],
            "output_sha256": None, "output_bytes": 0}, elapsed=elapsed)
        append(value, "ATTEMPT_FINALIZED", {"terminal_event_sha256": candidate["event_sha256"],
            "status": "FAILED", "reason_codes": ["SYNTHETIC_FAILURE"],
            "budget_observation_scope": runtime.BUDGET_OBSERVATION_SCOPE}, elapsed=elapsed)


def test_completed_output_is_candidate_until_finalization_and_replay_dispatches_zero(tmp_path):
    value = case(tmp_path)
    before = protected_raw(value)
    result = execute(value, attempt="attempt/한글")
    assert result["status"] == "COMPLETED_SIMULATION" and result["dispatches_this_invocation"] == 1
    assert result["actual_external_call_count"] == 0 and result["public_apply"] is False
    assert result["tokens"] is result["price"] is None and result["formal_kpi_status"] == "NOT_ESTIMABLE"
    path = Path(result["output"]["path"])
    assert path.name == hashlib.sha256("attempt/한글".encode()).hexdigest() + ".json"
    raw = path.read_bytes()
    output = json.loads(raw)
    assert output["status"] == "SIMULATION_OUTPUT_CANDIDATE"
    assert raw == runtime._canonical_bytes(output) + b"\n"
    assert output["receipt_sha256"] == hashlib.sha256(runtime._canonical_bytes({
        k: v for k, v in output.items() if k != "receipt_sha256"})).hexdigest()
    attempt = value["journal"].snapshot()["attempts"]["attempt/한글"]
    assert attempt["finalized"]["payload"]["terminal_event_sha256"] == attempt["terminal"]["event_sha256"]
    assert attempt["finalized"]["payload"]["budget_observation_scope"] == runtime.BUDGET_OBSERVATION_SCOPE
    journal_raw = value["journal"].path.read_bytes()
    replay = execute(value, attempt="attempt/한글")
    assert replay["status"] == "COMPLETED_SIMULATION" and replay["replayed"] is True
    assert replay["dispatches_this_invocation"] == 0 and replay["output"] == result["output"]
    assert value["journal"].path.read_bytes() == journal_raw and protected_raw(value) == before


def test_transient_retry_has_new_call_lineage_and_includes_backoff_time(tmp_path):
    value = case(tmp_path, responses=[response("TRANSIENT_FAILURE", delay=2, retry_delay=7), response(delay=3)])
    result = execute(value)
    state = value["journal"].snapshot()
    calls = list(state["calls"].values())
    assert result["status"] == "COMPLETED_SIMULATION" and result["dispatches_this_invocation"] == 2
    assert state["consumed_simulated_dispatches"] == 2 and state["consumed_elapsed_ms"] == 12
    assert calls[0]["call_id"] != calls[1]["call_id"]
    assert calls[1]["previous_call_id"] == calls[0]["call_id"]
    assert [c["retry_ordinal"] for c in calls] == [0, 1]
    assert [c["reservation_ordinal"] for c in calls] == [1, 2]


@pytest.mark.parametrize("policy,reason", [
    ({"max_simulated_dispatches": 0}, "DISPATCH_BUDGET_EXHAUSTED"),
    ({"max_elapsed_ms": 0, "per_action_timeout_ms": 0, "cancel_grace_ms": 0}, "TIME_BUDGET_EXHAUSTED"),
    ({"per_action_timeout_ms": 0}, "ACTION_TIME_BUDGET_EXHAUSTED"),
])
def test_zero_budget_is_checked_before_reservation(tmp_path, policy, reason):
    value = case(tmp_path, policy_overrides=policy)
    result = execute(value)
    assert result["status"] == "BUDGET_EXHAUSTED" and reason in result["reason_codes"]
    assert result["dispatches_this_invocation"] == result["consumed_simulated_dispatches"] == 0
    assert value["journal"].snapshot()["calls"] == {} and result["output"] is None


@pytest.mark.parametrize("policy,reason", [
    ({"max_simulated_dispatches": 1}, "DISPATCH_BUDGET_EXHAUSTED"),
    ({"max_retries_per_action": 0}, "RETRY_BUDGET_EXHAUSTED"),
    ({"max_elapsed_ms": 7, "per_action_timeout_ms": 7, "cancel_grace_ms": 7}, "TIME_BUDGET_EXHAUSTED"),
])
def test_new_attempt_does_not_reset_plan_budget(tmp_path, policy, reason):
    value = case(tmp_path, responses=[response("TRANSIENT_FAILURE"), response()], policy_overrides=policy)
    reserve_old(value)
    result = execute(value)
    assert result["status"] == "BUDGET_EXHAUSTED" and reason in result["reason_codes"]
    assert result["dispatches_this_invocation"] == 0 and result["consumed_simulated_dispatches"] == 1
    assert result["consumed_elapsed_ms"] == 7


def test_new_attempt_uses_global_fixture_ordinal_and_prior_elapsed(tmp_path):
    value = case(tmp_path, responses=[response("TRANSIENT_FAILURE"), response(delay=3, text="두 번째 고정 응답")])
    reserve_old(value)
    result = execute(value)
    state = value["journal"].snapshot()
    assert result["status"] == "COMPLETED_SIMULATION" and result["dispatches_this_invocation"] == 1
    assert state["consumed_simulated_dispatches"] == 2 and state["consumed_elapsed_ms"] == 10
    call = list(state["calls"].values())[-1]
    assert call["reservation_ordinal"] == 2 and call["retry_ordinal"] == 0 and call["previous_call_id"] is None
    assert json.loads(Path(result["output"]["path"]).read_bytes())["actions"][0]["response"]["text"] == "두 번째 고정 응답"


@pytest.mark.parametrize("declared,forged", [("PERMANENT_FAILURE", "TRANSIENT_FAILURE"),
    ("SUCCESS", "TRANSIENT_FAILURE"), ("TRANSIENT_FAILURE", "TIMEOUT"), ("SUCCESS", "NO_RESPONSE"),
    ("SUCCESS", "CANCEL_CONFIRMED")])
def test_resealed_failure_cannot_create_a_retry_or_fake_timeout(tmp_path, declared, forged):
    value = case(tmp_path, responses=[response(declared), response()])
    reserve_old(value, terminal=False)
    if forged == "CANCEL_CONFIRMED":
        append(value, "CANCEL_REQUESTED", {"reason_code": "SYNTHETIC_CANCEL_REQUEST"})
    append(value, "ACTION_TERMINAL", {"call_id": "old-call", "outcome": forged,
        "response_sha256": None, "response_bytes": 0})
    append(value, "ATTEMPT_TERMINAL", {"status": "INCOMPLETE" if forged == "NO_RESPONSE" else "FAILED",
        "reason_codes": ["RESEALED_SYNTHETIC_CONTRADICTION"], "output_sha256": None, "output_bytes": 0})
    before = value["journal"].path.read_bytes()
    with pytest.raises(runtime.BoundedRecoveryError):
        execute(value)
    assert value["journal"].path.read_bytes() == before
    assert value["journal"].snapshot()["consumed_simulated_dispatches"] == 1


@pytest.mark.parametrize("same_attempt", [False, True])
def test_reserved_crash_is_incomplete_without_any_new_dispatch_or_write(tmp_path, same_attempt):
    value = case(tmp_path)
    reserve_old(value, terminal=False)
    before = value["journal"].path.read_bytes()
    result = execute(value, attempt="old-attempt" if same_attempt else "new-attempt",
                     session="old-session" if same_attempt else "new-session")
    assert result["status"] == "INCOMPLETE" and result["dispatches_this_invocation"] == 0
    assert "INCOMPLETE_DISPATCH" in result["reason_codes"]
    assert value["journal"].path.read_bytes() == before


def test_cancellation_before_reservation_records_request_without_dispatch(tmp_path):
    value = case(tmp_path)
    result = execute(value, cancellation=Cancellation(True))
    assert result["status"] == "CANCELLED" and result["dispatches_this_invocation"] == 0
    state = value["journal"].snapshot()
    assert state["consumed_simulated_dispatches"] == 0
    assert [event["event_type"] for event in state["events"]] == [
        "ATTEMPT_STARTED", "CANCEL_REQUESTED", "ATTEMPT_TERMINAL", "ATTEMPT_FINALIZED"]


@pytest.mark.parametrize("outcome,expected", [("CANCEL_CONFIRMED", "CANCELLED"), ("SUCCESS", "INCOMPLETE")])
def test_cancellation_request_is_not_a_stop_confirmation(tmp_path, outcome, expected):
    value = case(tmp_path, responses=[response(outcome, delay=20)], policy_overrides={"cancel_grace_ms": 20})
    clock = Clock()
    class DuringCall:
        def requested(self):
            return clock.value >= 1010
    result = execute(value, clock=clock, cancellation=DuringCall())
    assert result["status"] == expected and result["dispatches_this_invocation"] == 1
    assert result["consumed_simulated_dispatches"] == 1 and result["output"] is None
    if expected == "INCOMPLETE":
        assert "CANCEL_NOT_CONFIRMED" in result["reason_codes"]


@pytest.mark.parametrize("extra_ms,expected", [(0, "CANCELLED"), (1, "INCOMPLETE")])
def test_cancel_grace_is_rechecked_after_source_verification_before_terminal(tmp_path, monkeypatch, extra_ms, expected):
    value = case(tmp_path, responses=[response("CANCEL_CONFIRMED", delay=20)], policy_overrides={"cancel_grace_ms": 10})
    clock = Clock()
    class DuringCall:
        def requested(self):
            return clock.value >= 1010
    original = runtime.BoundRecoveryPlan.verify_protected_sources
    def delayed_verification(self):
        result = original(self)
        if clock.value == 1020 and value["journal"].snapshot()["open_call_ids"]:
            clock.value += extra_ms
        return result
    monkeypatch.setattr(runtime.BoundRecoveryPlan, "verify_protected_sources", delayed_verification)
    result = execute(value, clock=clock, cancellation=DuringCall())
    assert result["status"] == expected and result["dispatches_this_invocation"] == 1
    outcome = list(value["journal"].snapshot()["calls"].values())[0]["terminal"]["payload"]["outcome"]
    assert outcome == ("CANCEL_CONFIRMED" if extra_ms == 0 else "NO_RESPONSE")


def test_backoff_cancellation_does_not_reserve_retry(tmp_path):
    value = case(tmp_path, responses=[response("TRANSIENT_FAILURE", retry_delay=20), response()])
    clock = Clock()
    class BackoffCancel:
        def requested(self):
            return clock.value >= 1010
    result = execute(value, clock=clock, cancellation=BackoffCancel())
    assert result["status"] == "CANCELLED" and result["dispatches_this_invocation"] == 1
    assert result["consumed_simulated_dispatches"] == 1


@pytest.mark.parametrize("outcome,expected", [("PERMANENT_FAILURE", "FAILED"), ("CALLBACK_ERROR", "FAILED"), ("NO_RESPONSE", "INCOMPLETE")])
def test_failed_and_uncertain_responses_are_counted_without_retry(tmp_path, outcome, expected):
    value = case(tmp_path, responses=[response(outcome), response()])
    result = execute(value)
    assert result["status"] == expected and result["dispatches_this_invocation"] == 1
    assert result["consumed_simulated_dispatches"] == 1 and result["output"] is None


@pytest.mark.parametrize("delay,expected", [(5, "COMPLETED_SIMULATION"), (6, "BUDGET_EXHAUSTED")])
def test_exact_timeout_boundary_and_late_response(tmp_path, delay, expected):
    value = case(tmp_path, responses=[response(delay=delay)], policy_overrides={"per_action_timeout_ms": 5})
    result = execute(value)
    assert result["status"] == expected and result["dispatches_this_invocation"] == 1
    if delay == 6:
        assert "LATE_RESPONSE" in result["reason_codes"] and result["output"] is None


def test_clock_error_after_reservation_is_not_fabricated_end_or_dispatch(tmp_path):
    value = case(tmp_path)
    class BadClock(Clock):
        def monotonic_ms(self):
            if value["journal"].snapshot()["open_call_ids"]:
                raise ValueError("synthetic clock failure")
            return self.value
    result = execute(value, clock=BadClock())
    assert result["status"] == "INCOMPLETE" and result["dispatches_this_invocation"] == 0
    state = value["journal"].snapshot()
    assert len(state["open_call_ids"]) == 1 and state["attempts"]["recovery-attempt-1"]["terminal"] is None


@pytest.mark.parametrize("value", [None, 1, "false"])
def test_non_boolean_cancellation_is_not_a_safe_false(tmp_path, value):
    fixture = case(tmp_path)
    result = execute(fixture, cancellation=Cancellation(value))
    assert result["status"] == "INCOMPLETE" and result["dispatches_this_invocation"] == 0
    assert "CANCELLATION_VALUE_INVALID" in result["reason_codes"]


def test_source_drift_after_dispatch_is_incomplete_and_never_retried(tmp_path):
    value = case(tmp_path, responses=[response(delay=1)])
    path = Path(value["artifact_refs"]["input"]["path"])
    class DriftingClock(Clock):
        def sleep_ms(self, duration_ms):
            super().sleep_ms(duration_ms)
            path.write_bytes(path.read_bytes() + b" ")
    result = execute(value, clock=DriftingClock())
    assert result["status"] == "INCOMPLETE" and result["dispatches_this_invocation"] == 1
    assert result["output"] is None
    assert len(value["journal"].snapshot()["open_call_ids"]) == 1


@pytest.mark.parametrize("failed_kind,dispatches", [("ACTION_RESERVED", 0), ("ACTION_TERMINAL", 1),
    ("ATTEMPT_TERMINAL", 1), ("ATTEMPT_FINALIZED", 1)])
def test_journal_append_failure_never_becomes_completion(tmp_path, monkeypatch, failed_kind, dispatches):
    value = case(tmp_path)
    original = ledger._JournalTransaction.append
    def fail(self, *, expected_head_sha256, event):
        if event["event_type"] == failed_kind:
            raise OSError("synthetic durable append failure")
        return original(self, expected_head_sha256=expected_head_sha256, event=event)
    monkeypatch.setattr(ledger._JournalTransaction, "append", fail)
    result = execute(value)
    assert result["status"] == "INCOMPLETE" and result["dispatches_this_invocation"] == dispatches
    attempt = value["journal"].snapshot()["attempts"]["recovery-attempt-1"]
    assert attempt["finalized"] is None or attempt["finalized"]["payload"]["status"] != "COMPLETED_SIMULATION"
    if failed_kind == "ATTEMPT_FINALIZED":
        assert attempt["terminal"]["payload"]["status"] == "COMPLETED_SIMULATION"


def test_output_exclusive_collision_preserves_existing_bytes(tmp_path):
    value = case(tmp_path)
    path = runtime.simulation_output_path(value["bound"], "recovery-attempt-1")
    path.parent.mkdir(parents=True)
    path.write_bytes(b"existing unrelated synthetic output")
    result = execute(value)
    assert result["status"] == "INCOMPLETE" and result["output"] is None
    assert path.read_bytes() == b"existing unrelated synthetic output"


def test_output_fsync_time_is_included_before_completion_and_orphan_is_not_success(tmp_path, monkeypatch):
    value = case(tmp_path)
    clock = Clock()
    path = runtime.simulation_output_path(value["bound"], "recovery-attempt-1")
    original = runtime.os.fsync
    def fsync(fd):
        original(fd)
        if path.exists() and runtime.os.fstat(fd).st_ino == path.stat().st_ino:
            clock.value += value["plan"]["policy"]["max_elapsed_ms"] + 1
    monkeypatch.setattr(runtime.os, "fsync", fsync)
    result = execute(value, clock=clock)
    assert result["status"] == "BUDGET_EXHAUSTED" and result["output"] is None
    assert path.exists() and json.loads(path.read_bytes())["status"] == "SIMULATION_OUTPUT_CANDIDATE"
    terminal = value["journal"].snapshot()["attempts"]["recovery-attempt-1"]["terminal"]
    assert terminal["payload"]["output_sha256"] is None and terminal["payload"]["output_bytes"] == 0


@pytest.mark.parametrize("guard_delay,expected,dispatches", [
    (5, "COMPLETED_SIMULATION", 1), (6, "INCOMPLETE", 0)])
def test_fresh_guard_after_reservation_rechecks_action_time_before_dispatch(
        tmp_path, monkeypatch, guard_delay, expected, dispatches):
    value = case(tmp_path, policy_overrides={"per_action_timeout_ms": 5})
    clock, injected = Clock(), []
    original = type(value["bound"]).verify_protected_sources
    def verify(bound):
        result = original(bound)
        if not injected and value["journal"].snapshot()["open_call_ids"]:
            clock.value += guard_delay
            injected.append(True)
        return result
    monkeypatch.setattr(type(value["bound"]), "verify_protected_sources", verify)
    result = execute(value, clock=clock)
    state = value["journal"].snapshot()
    assert injected and result["status"] == expected
    assert result["dispatches_this_invocation"] == dispatches
    assert result["consumed_simulated_dispatches"] == 1
    if dispatches == 0:
        assert result["output"] is None and len(state["open_call_ids"]) == 1
        assert "ACTION_TIME_BUDGET_EXHAUSTED_BEFORE_DISPATCH" in result["reason_codes"]
        assert not any(event["event_type"] == "ACTION_TERMINAL" for event in state["events"])


def advance_during_event_fsync(monkeypatch, clock, event_kind, duration):
    """실제 append/fsync를 보존하며 지정 사건의 fsync 뒤 합성 시간을 한 번 더한다."""
    original_append, original_fsync = ledger._JournalTransaction.append, ledger.os.fsync
    active, hits = [], []
    def append_with_kind(tx, *, expected_head_sha256, event):
        active.append(event["event_type"])
        try:
            return original_append(tx, expected_head_sha256=expected_head_sha256, event=event)
        finally:
            active.pop()
    def fsync(fd):
        original_fsync(fd)
        if active and active[-1] == event_kind and not hits:
            clock.value += duration
            hits.append(event_kind)
    monkeypatch.setattr(ledger._JournalTransaction, "append", append_with_kind)
    monkeypatch.setattr(ledger.os, "fsync", fsync)
    return hits


@pytest.mark.parametrize("duration,expected", [(1000, "COMPLETED_SIMULATION"), (1001, "BUDGET_EXHAUSTED")])
def test_terminal_fsync_time_is_finalized_and_late_candidate_cannot_replay_as_success(
        tmp_path, monkeypatch, duration, expected):
    value, clock = case(tmp_path), Clock()
    hits = advance_during_event_fsync(monkeypatch, clock, "ATTEMPT_TERMINAL", duration)
    result = execute(value, clock=clock)
    state = value["journal"].snapshot()
    attempt = state["attempts"]["recovery-attempt-1"]
    assert hits == ["ATTEMPT_TERMINAL"] and result["status"] == expected
    assert attempt["terminal"]["elapsed_ms"] == 0
    assert attempt["terminal"]["payload"]["status"] == "COMPLETED_SIMULATION"
    assert attempt["finalized"]["elapsed_ms"] == result["consumed_elapsed_ms"] == duration
    assert attempt["finalized"]["payload"]["terminal_event_sha256"] == attempt["terminal"]["event_sha256"]
    assert attempt["finalized"]["payload"]["budget_observation_scope"] == runtime.BUDGET_OBSERVATION_SCOPE
    path = runtime.simulation_output_path(value["bound"], "recovery-attempt-1")
    assert json.loads(path.read_bytes())["status"] == "SIMULATION_OUTPUT_CANDIDATE"
    if expected == "BUDGET_EXHAUSTED":
        assert result["output"] is None
        assert "TERMINAL_DURABILITY_TIME_BUDGET_EXHAUSTED" in result["reason_codes"]
    before = value["journal"].path.read_bytes()
    replay = execute(value)
    assert replay["status"] == expected and replay["dispatches_this_invocation"] == 0
    assert replay["output"] == result["output"] and value["journal"].path.read_bytes() == before


def test_failure_terminal_storage_elapsed_carries_into_next_attempt(tmp_path, monkeypatch):
    value, clock = case(tmp_path, responses=[response("PERMANENT_FAILURE")]), Clock()
    original = ledger._JournalTransaction.append
    def append_with_readback_delay(tx, *, expected_head_sha256, event):
        saved = original(tx, expected_head_sha256=expected_head_sha256, event=event)
        if event["event_type"] == "ATTEMPT_TERMINAL":
            clock.value += 17 if event["recovery_attempt_id"] == "recovery-attempt-1" else 13
        return saved
    monkeypatch.setattr(ledger._JournalTransaction, "append", append_with_readback_delay)
    first = execute(value, clock=clock)
    assert first["status"] == "FAILED" and first["consumed_elapsed_ms"] == 17
    second = execute(value, clock=clock, attempt="second-attempt", session="second-session")
    state = value["journal"].snapshot()
    assert second["status"] == "FAILED" and second["dispatches_this_invocation"] == 0
    assert "ACTION_NOT_RETRYABLE" in second["reason_codes"]
    assert second["consumed_elapsed_ms"] == 30 and second["consumed_simulated_dispatches"] == 1
    assert [a["finalized"]["elapsed_ms"] for a in state["attempts"].values()] == [17, 13]


@pytest.mark.parametrize("failure", ["append", "clock"])
def test_missing_finalization_blocks_completed_replay_and_new_attempt(tmp_path, monkeypatch, failure):
    value = case(tmp_path)
    original = ledger._JournalTransaction.append
    candidate_stored = []
    def fail_finalization(tx, *, expected_head_sha256, event):
        if failure == "append" and event["event_type"] == "ATTEMPT_FINALIZED":
            raise OSError("synthetic finalization append failure")
        saved = original(tx, expected_head_sha256=expected_head_sha256, event=event)
        if event["event_type"] == "ATTEMPT_TERMINAL":
            candidate_stored.append(True)
        return saved
    class FinalClock(Clock):
        def monotonic_ms(self):
            if failure == "clock" and candidate_stored:
                raise ValueError("synthetic post-durable observation failure")
            return self.value
    monkeypatch.setattr(ledger._JournalTransaction, "append", fail_finalization)
    first = execute(value, clock=FinalClock())
    attempt = value["journal"].snapshot()["attempts"]["recovery-attempt-1"]
    assert first["status"] == "INCOMPLETE" and first["output"] is None
    assert attempt["terminal"]["payload"]["status"] == "COMPLETED_SIMULATION" and attempt["finalized"] is None
    before = value["journal"].path.read_bytes()
    replay = execute(value)
    new_attempt = execute(value, attempt="second-attempt", session="second-session")
    assert replay["status"] == new_attempt["status"] == "INCOMPLETE"
    assert "FINALIZATION_MISSING" in replay["reason_codes"]
    assert replay["dispatches_this_invocation"] == new_attempt["dispatches_this_invocation"] == 0
    assert value["journal"].path.read_bytes() == before


@pytest.mark.parametrize("observation", ["source", "cancel", "cancel-error"])
def test_post_terminal_observation_error_downgrades_candidate(tmp_path, monkeypatch, observation):
    value, candidate_stored = case(tmp_path), []
    original = ledger._JournalTransaction.append
    source = Path(value["artifact_refs"]["input"]["path"])
    def terminal_observation(tx, *, expected_head_sha256, event):
        saved = original(tx, expected_head_sha256=expected_head_sha256, event=event)
        if event["event_type"] == "ATTEMPT_TERMINAL":
            candidate_stored.append(True)
            if observation == "source":
                source.write_bytes(source.read_bytes() + b" ")
        return saved
    class FinalCancellation:
        def requested(self):
            if candidate_stored and observation == "cancel-error":
                raise ValueError("synthetic post-terminal cancellation observation error")
            return bool(candidate_stored and observation == "cancel")
    monkeypatch.setattr(ledger._JournalTransaction, "append", terminal_observation)
    result = execute(value, cancellation=FinalCancellation())
    attempt = value["journal"].snapshot()["attempts"]["recovery-attempt-1"]
    assert result["status"] == "INCOMPLETE" and result["output"] is None
    assert attempt["terminal"]["payload"]["status"] == "COMPLETED_SIMULATION"
    assert attempt["finalized"]["payload"]["status"] == "INCOMPLETE"


def test_final_observation_receipt_storage_is_explicitly_outside_budget_scope(tmp_path, monkeypatch):
    value, clock = case(tmp_path), Clock()
    hits = advance_during_event_fsync(monkeypatch, clock, "ATTEMPT_FINALIZED", 1001)
    result = execute(value, clock=clock)
    attempt = value["journal"].snapshot()["attempts"]["recovery-attempt-1"]
    assert hits == ["ATTEMPT_FINALIZED"] and clock.value == 2001
    assert result["status"] == "COMPLETED_SIMULATION" and result["consumed_elapsed_ms"] == 0
    assert attempt["finalized"]["elapsed_ms"] == 0
    assert attempt["finalized"]["payload"]["budget_observation_scope"] == "THROUGH_ATTEMPT_TERMINAL_DURABLE_READBACK"


def test_candidate_output_limit_is_not_silently_truncated(tmp_path):
    value = case(tmp_path, policy_overrides={"max_output_bytes": 100})
    result = execute(value)
    assert result["status"] == "FAILED" and result["reason_codes"] == ["OUTPUT_LIMIT"]
    assert result["output"] is None and not (value["bound"].output_dir / "attempts").exists()


def test_wrong_fixture_or_journal_namespace_is_rejected_before_output_creation(tmp_path):
    value = case(tmp_path)
    wrong = deepcopy(value["fixture"])
    wrong["actions"][0]["responses"][0]["response"]["text"] = "계획에 없는 응답"
    with pytest.raises(runtime.BoundedRecoveryError, match="FIXTURE_BINDING_MISMATCH"):
        execute(value, fixture=wrong)
    wrong_journal = ledger.RecoveryExecutionJournal(tmp_path / "other.jsonl", **execution_journal_arguments(value["plan"]))
    with pytest.raises(runtime.BoundedRecoveryError, match="JOURNAL_PATH_MISMATCH"):
        execute(value, journal=wrong_journal)
    assert not value["bound"].output_dir.exists() and not wrong_journal.path.exists()


def test_corrupt_journal_is_not_repaired_or_dispatched(tmp_path):
    value = case(tmp_path)
    value["journal"].path.parent.mkdir()
    value["journal"].path.write_bytes(b'{"partial":')
    with pytest.raises(ledger.RecoveryExecutionJournalError, match="INCOMPLETE_JOURNAL"):
        execute(value)
    assert value["journal"].path.read_bytes() == b'{"partial":'
    assert not value["journal"].path.with_name("recovery_execution.jsonl.lock").exists()


def test_completed_replay_rejects_changed_output_without_new_dispatch(tmp_path):
    value = case(tmp_path)
    completed = execute(value)
    path = Path(completed["output"]["path"])
    path.write_bytes(path.read_bytes() + b" ")
    before = value["journal"].path.read_bytes()
    result = execute(value)
    assert result["status"] == "INCOMPLETE" and result["dispatches_this_invocation"] == 0
    assert value["journal"].path.read_bytes() == before


def test_concurrent_attempt_cannot_dispatch_while_first_has_reserved_call(tmp_path):
    value = case(tmp_path, responses=[response(delay=1)])
    entered, release = threading.Event(), threading.Event()
    class PausingClock(Clock):
        def sleep_ms(self, duration_ms):
            entered.set()
            assert release.wait(5)
            super().sleep_ms(duration_ms)
    results = []
    thread = threading.Thread(target=lambda: results.append(execute(value, clock=PausingClock())))
    thread.start()
    try:
        assert entered.wait(5)
        second = execute(value, attempt="second-attempt", session="second-session")
        assert second["status"] == "INCOMPLETE" and second["dispatches_this_invocation"] == 0
    finally:
        release.set()
        thread.join(5)
    assert not thread.is_alive() and results[0]["status"] == "COMPLETED_SIMULATION"
    assert value["journal"].snapshot()["consumed_simulated_dispatches"] == 1
