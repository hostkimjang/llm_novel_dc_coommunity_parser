from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import ctypes
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import threading
from unittest.mock import patch

import pytest

from src.llm_batch.ledger import recovery_execution_journal as module
from src.llm_batch.ledger.recovery_execution_journal import (
    RecoveryExecutionJournal, RecoveryExecutionJournalError,
    canonical_sha256, read_execution_journal, validate_execution_events,
)


def configuration(**overrides):
    policy = dict(max_actions=2, max_simulated_dispatches=4, max_retries_per_action=2,
                  max_elapsed_ms=100, per_action_timeout_ms=30, cancel_grace_ms=10,
                  max_output_bytes=4096, actual_external_call_budget=0)
    policy.update(overrides)
    binding = dict(plan_sha256="1" * 64, base_sha256="2" * 64,
                   policy_sha256=canonical_sha256(policy), config_sha256="3" * 64,
                   source_sha256="4" * 64, fixture_sha256="5" * 64,
                   publication_scope_id="scope", input_index=1, post_id=101,
                   base_attempt_run_id="base-attempt")
    actions = [dict(action_id="action-1", action_kind="SIMULATED_TARGETED_SEARCH", query_sha256="6" * 64)]
    return dict(binding=binding, policy=policy, actions=actions)


def intent(event_type, payload=None, elapsed=0, attempt="attempt-1", session="session-1"):
    return dict(event_type=event_type, recovery_session_id=session,
                recovery_attempt_id=attempt, elapsed_ms=elapsed, payload=payload or {})


def append(journal, event, *, finalize=True):
    saved = journal.append(expected_head_sha256=journal.snapshot()["head_sha256"], event=event)
    if event["event_type"] == "ATTEMPT_TERMINAL" and finalize:
        final = intent("ATTEMPT_FINALIZED", {
            "terminal_event_sha256": saved["event_sha256"],
            "status": event["payload"]["status"], "reason_codes": event["payload"]["reason_codes"],
            "budget_observation_scope": module.FINALIZATION_ELAPSED_SCOPE,
        }, elapsed=event["elapsed_ms"], attempt=event["recovery_attempt_id"], session=event["recovery_session_id"])
        journal.append(expected_head_sha256=saved["event_sha256"], event=final)
    return saved


def start(journal, **kwargs):
    return append(journal, intent("ATTEMPT_STARTED", **kwargs))


def reservation(call="call-1", ordinal=1, retry=0, previous=None, **kwargs):
    return intent("ACTION_RESERVED", dict(call_id=call, action_id="action-1",
                  action_kind="SIMULATED_TARGETED_SEARCH", query_sha256="6" * 64,
                  reservation_ordinal=ordinal, retry_ordinal=retry, previous_call_id=previous), **kwargs)


def action_terminal(outcome="SUCCESS", call="call-1", **kwargs):
    return intent("ACTION_TERMINAL", dict(call_id=call, outcome=outcome,
                  response_sha256=None, response_bytes=0), **kwargs)


def terminal(status="COMPLETED_SIMULATION", **kwargs):
    return intent("ATTEMPT_TERMINAL", dict(status=status, reason_codes=[],
                  output_sha256="a" * 64 if status == "COMPLETED_SIMULATION" else None,
                  output_bytes=3 if status == "COMPLETED_SIMULATION" else 0), **kwargs)


def finalization(candidate, *, elapsed, status=None, reasons=None):
    return intent("ATTEMPT_FINALIZED", {
        "terminal_event_sha256": candidate["event_sha256"],
        "status": status or candidate["payload"]["status"],
        "reason_codes": candidate["payload"]["reason_codes"] if reasons is None else reasons,
        "budget_observation_scope": module.FINALIZATION_ELAPSED_SCOPE,
    }, elapsed=elapsed, attempt=candidate["recovery_attempt_id"], session=candidate["recovery_session_id"])


def reseal(events):
    previous = "GENESIS"
    for index, event in enumerate(events, 1):
        event["sequence"] = index
        event["prev_event_sha256"] = previous
        event.pop("event_sha256", None)
        event["event_sha256"] = canonical_sha256(event)
        previous = event["event_sha256"]
    return events


def completed(journal):
    start(journal)
    append(journal, reservation(elapsed=1))
    append(journal, action_terminal(elapsed=5))
    append(journal, terminal(elapsed=7))
    return journal.snapshot()


def test_complete_readonly_replay_and_caller_isolation(tmp_path):
    cfg = configuration()
    journal = RecoveryExecutionJournal(tmp_path / "new" / "journal.jsonl", **cfg)
    assert not journal.path.parent.exists()
    assert journal.snapshot()["event_count"] == 0
    assert not journal.path.parent.exists()
    cfg["binding"]["post_id"] = "101"
    state = completed(journal)
    before = journal.path.read_bytes()
    assert state["consumed_simulated_dispatches"] == 1
    assert state["consumed_elapsed_ms"] == 7
    assert state["active_attempt_id"] is None
    assert state["attempts"]["attempt-1"]["terminal"]["payload"]["status"] == "COMPLETED_SIMULATION"
    state["events"][0]["post_id"] = "changed"
    assert journal.snapshot()["events"][0]["post_id"] == 101
    readonly = tmp_path / "readonly.jsonl"
    readonly.write_bytes(before)
    replay = RecoveryExecutionJournal(readonly, **configuration()).snapshot()
    assert replay["event_count"] == 5
    assert not Path(str(readonly) + ".lock").exists()
    assert readonly.read_bytes() == before
    with pytest.raises(RecoveryExecutionJournalError, match="DUPLICATE_ATTEMPT_ID"):
        start(journal)
    assert journal.path.read_bytes() == before


def test_retry_lineage_and_cumulative_budget_survive_new_attempt(tmp_path):
    journal = RecoveryExecutionJournal(tmp_path / "journal.jsonl", **configuration(max_simulated_dispatches=2))
    start(journal)
    append(journal, reservation(elapsed=1))
    append(journal, action_terminal("TRANSIENT_FAILURE", elapsed=3))
    append(journal, terminal("FAILED", elapsed=4))
    start(journal, attempt="attempt-2", elapsed=2)
    append(journal, reservation(call="call-2", ordinal=2, attempt="attempt-2", elapsed=3))
    append(journal, action_terminal("TRANSIENT_FAILURE", call="call-2", attempt="attempt-2", elapsed=4))
    state = journal.snapshot()
    assert state["consumed_simulated_dispatches"] == 2
    assert state["consumed_elapsed_ms"] == 8
    assert state["action_reservations"] == {"action-1": 2}
    with pytest.raises(RecoveryExecutionJournalError, match="DISPATCH_BUDGET_EXHAUSTED"):
        append(journal, reservation(call="call-3", ordinal=3, retry=1, previous="call-2", attempt="attempt-2", elapsed=5))


def test_retry_cap_is_plan_cumulative_not_reset_by_attempt(tmp_path):
    journal = RecoveryExecutionJournal(tmp_path / "journal.jsonl", **configuration(max_retries_per_action=0))
    start(journal)
    append(journal, reservation())
    append(journal, action_terminal("TRANSIENT_FAILURE"))
    append(journal, terminal("FAILED"))
    start(journal, attempt="attempt-2")
    with pytest.raises(RecoveryExecutionJournalError, match="RETRY_BUDGET_EXHAUSTED"):
        append(journal, reservation(call="call-2", ordinal=2, attempt="attempt-2"))


@pytest.mark.parametrize("field,value,code", [
    ("previous_call_id", "different", "INVALID_RETRY_LINEAGE"),
    ("retry_ordinal", 0, "INVALID_RETRY_ORDINAL"),
    ("reservation_ordinal", 1, "INVALID_RESERVATION_ORDINAL"),
    ("query_sha256", "a" * 64, "ACTION_BINDING_MISMATCH"),
    ("call_id", "call-1", "DUPLICATE_CALL_ID"),
])
def test_retry_cannot_rebind_lineage_or_source(tmp_path, field, value, code):
    journal = RecoveryExecutionJournal(tmp_path / "journal.jsonl", **configuration())
    start(journal)
    append(journal, reservation())
    append(journal, action_terminal("TRANSIENT_FAILURE"))
    event = reservation(call="call-2", ordinal=2, retry=1, previous="call-1")
    event["payload"][field] = value
    before = journal.path.read_bytes()
    with pytest.raises(RecoveryExecutionJournalError, match=code):
        append(journal, event)
    assert journal.path.read_bytes() == before


@pytest.mark.parametrize("policy,code", [
    ({"max_actions": 0}, "ACTION_BUDGET_EXHAUSTED"),
    ({"max_simulated_dispatches": 0}, "DISPATCH_BUDGET_EXHAUSTED"),
    ({"max_elapsed_ms": 0}, "TIME_BUDGET_EXHAUSTED"),
    ({"per_action_timeout_ms": 0}, "TIME_BUDGET_EXHAUSTED"),
])
def test_zero_budgets_reserve_nothing(tmp_path, policy, code):
    journal = RecoveryExecutionJournal(tmp_path / "journal.jsonl", **configuration(**policy))
    start(journal)
    with pytest.raises(RecoveryExecutionJournalError, match=code):
        append(journal, reservation())
    assert journal.snapshot()["consumed_simulated_dispatches"] == 0


def test_deadline_exact_boundaries_and_elapsed_across_attempts(tmp_path):
    journal = RecoveryExecutionJournal(tmp_path / "journal.jsonl", **configuration(max_elapsed_ms=10))
    start(journal, elapsed=1)
    append(journal, reservation(elapsed=2))
    append(journal, action_terminal("TRANSIENT_FAILURE", elapsed=7))
    append(journal, terminal("FAILED", elapsed=8))
    start(journal, attempt="attempt-2", elapsed=1)
    with pytest.raises(RecoveryExecutionJournalError, match="TIME_BUDGET_EXHAUSTED"):
        append(journal, reservation(call="call-2", ordinal=2, attempt="attempt-2", elapsed=2))
    assert journal.snapshot()["consumed_elapsed_ms"] == 9
    # 실패한 append의 임시 재생 상태는 기존 파일을 바꾸지 않는다.
    append(journal, terminal("BUDGET_EXHAUSTED", attempt="attempt-2", elapsed=2))
    assert journal.snapshot()["consumed_elapsed_ms"] == 10


@pytest.mark.parametrize("outcome", ["SUCCESS", "PERMANENT_FAILURE", "CANCEL_CONFIRMED", "CALLBACK_ERROR", "TIMEOUT", "OUTPUT_LIMIT"])
def test_only_transient_failure_can_retry(tmp_path, outcome):
    journal = RecoveryExecutionJournal(tmp_path / "journal.jsonl", **configuration())
    start(journal)
    append(journal, reservation())
    append(journal, action_terminal(outcome))
    with pytest.raises(RecoveryExecutionJournalError, match="ACTION_NOT_RETRYABLE"):
        append(journal, reservation(call="call-2", ordinal=2, retry=1, previous="call-1"))


def test_cancel_before_dispatch_and_during_dispatch(tmp_path):
    first = RecoveryExecutionJournal(tmp_path / "first.jsonl", **configuration())
    start(first)
    append(first, intent("CANCEL_REQUESTED", {"reason_code": "USER_CANCEL"}))
    with pytest.raises(RecoveryExecutionJournalError, match="CANCELLATION_REQUESTED"):
        append(first, reservation())
    append(first, terminal("CANCELLED"))
    assert first.snapshot()["consumed_simulated_dispatches"] == 0
    second = RecoveryExecutionJournal(tmp_path / "second.jsonl", **configuration())
    start(second)
    append(second, reservation())
    append(second, intent("CANCEL_REQUESTED", {"reason_code": "USER_CANCEL"}, elapsed=1))
    with pytest.raises(RecoveryExecutionJournalError, match="LATE_SUCCESS_FORBIDDEN"):
        append(second, action_terminal(elapsed=2))
    append(second, action_terminal("CANCEL_CONFIRMED", elapsed=2))
    append(second, terminal("CANCELLED", elapsed=3))
    assert second.snapshot()["consumed_simulated_dispatches"] == 1


def test_crash_reserved_and_unknown_response_never_automatically_resume(tmp_path):
    journal = RecoveryExecutionJournal(tmp_path / "journal.jsonl", **configuration())
    start(journal)
    append(journal, reservation())
    before = journal.path.read_bytes()
    reopened = RecoveryExecutionJournal(journal.path, **configuration())
    assert reopened.snapshot()["open_call_ids"] == ["call-1"]
    with pytest.raises(RecoveryExecutionJournalError, match="INCOMPLETE_DISPATCH"):
        start(reopened, attempt="attempt-2")
    assert journal.path.read_bytes() == before
    with pytest.raises(RecoveryExecutionJournalError, match="INCOMPLETE_DISPATCH"):
        append(reopened, terminal("FAILED"))
    append(reopened, action_terminal("NO_RESPONSE"))
    with pytest.raises(RecoveryExecutionJournalError, match="INCOMPLETE_DISPATCH"):
        append(reopened, terminal("CANCELLED"))
    append(reopened, terminal("INCOMPLETE"))
    with pytest.raises(RecoveryExecutionJournalError, match="INCOMPLETE_DISPATCH"):
        start(reopened, attempt="attempt-2")


@pytest.mark.parametrize("delta,code", [
    ({"post_id": "101"}, "BINDING_MISMATCH"),
    ({"public_apply": 0}, "AUTHORITY_MISMATCH"),
    ({"actual_external_call_count": True}, "AUTHORITY_MISMATCH"),
    ({"publication_authority": True}, "AUTHORITY_MISMATCH"),
    ({"source_sha256": "f" * 64}, "BINDING_MISMATCH"),
    ({"plan_sha256": "f" * 64}, "BINDING_MISMATCH"),
    ({"sequence": True}, "INVALID_SEQUENCE"),
])
def test_resealed_authority_and_binding_contradictions_rejected(tmp_path, delta, code):
    cfg = configuration()
    journal = RecoveryExecutionJournal(tmp_path / "journal.jsonl", **cfg)
    start(journal)
    events = journal.snapshot()["events"]
    events[0].update(delta)
    event = events[0]
    event.pop("event_sha256")
    event["event_sha256"] = canonical_sha256(event)
    with pytest.raises(RecoveryExecutionJournalError, match=code):
        validate_execution_events(events, **cfg)


def test_resealed_duplicate_terminal_and_missing_reservation_rejected(tmp_path):
    cfg = configuration()
    journal = RecoveryExecutionJournal(tmp_path / "journal.jsonl", **cfg)
    events = completed(journal)["events"]
    duplicate = reseal(events[:3] + [deepcopy(events[2])] + events[3:])
    with pytest.raises(RecoveryExecutionJournalError, match="CALL_ALREADY_TERMINAL"):
        validate_execution_events(duplicate, **cfg)
    missing = reseal([events[0], events[2], events[3]])
    with pytest.raises(RecoveryExecutionJournalError, match="CALL_NOT_RESERVED"):
        validate_execution_events(missing, **cfg)


@pytest.mark.parametrize("tail", [b'{"partial":', b'{"partial":true}', b'\xff\n', b'\n'])
def test_bad_tail_is_never_repaired_or_truncated(tmp_path, tail):
    journal = RecoveryExecutionJournal(tmp_path / "journal.jsonl", **configuration())
    start(journal)
    raw = journal.path.read_bytes() + tail
    journal.path.write_bytes(raw)
    with pytest.raises(RecoveryExecutionJournalError):
        journal.snapshot()
    with pytest.raises(RecoveryExecutionJournalError):
        journal.append(expected_head_sha256="GENESIS", event=reservation())
    assert journal.path.read_bytes() == raw


def test_json_duplicate_unknown_keys_nonfinite_and_event_limit(tmp_path):
    journal = RecoveryExecutionJournal(tmp_path / "journal.jsonl", **configuration())
    event = start(journal)
    raw = json.dumps(event).encode()
    duplicate = raw[:-1] + b', "elapsed_ms": 0}\n'
    with pytest.raises(RecoveryExecutionJournalError, match="DUPLICATE_JSON_KEY"):
        read_execution_journal(duplicate, **configuration())
    event["unknown"] = 1
    with pytest.raises(RecoveryExecutionJournalError, match="INVALID_SCHEMA"):
        validate_execution_events([event], **configuration())
    with pytest.raises(RecoveryExecutionJournalError, match="INVALID_JSON"):
        canonical_sha256({"elapsed_ms": float("nan")})
    with patch.object(module, "MAX_EVENTS", 0):
        with pytest.raises(RecoveryExecutionJournalError, match="EVENT_LIMIT"):
            journal.snapshot()


def test_fsync_and_readback_are_required_before_append_returns(tmp_path):
    journal = RecoveryExecutionJournal(tmp_path / "journal.jsonl", **configuration())
    start(journal)
    real_fsync = os.fsync
    with patch.object(module.os, "fsync", wraps=real_fsync) as sync:
        saved = append(journal, reservation())
    assert sync.call_count >= 1
    assert journal.snapshot()["head_sha256"] == saved["event_sha256"]
    assert journal.snapshot()["open_call_ids"] == ["call-1"]


def test_append_failure_keeps_uncertain_reservation_without_retry(tmp_path):
    journal = RecoveryExecutionJournal(tmp_path / "journal.jsonl", **configuration())
    start(journal)
    with patch.object(module.os, "fsync", side_effect=OSError("simulated disk failure")):
        with pytest.raises(OSError):
            append(journal, reservation())
    state = journal.snapshot()
    assert state["consumed_simulated_dispatches"] == 1
    with pytest.raises(RecoveryExecutionJournalError, match="INCOMPLETE_DISPATCH"):
        append(journal, reservation(call="call-2", ordinal=2))


def test_transaction_lifetime_and_stale_cas(tmp_path):
    journal = RecoveryExecutionJournal(tmp_path / "journal.jsonl", **configuration())
    with journal.transaction() as tx:
        before = tx.snapshot()
        saved = tx.append(expected_head_sha256=before["head_sha256"], event=intent("ATTEMPT_STARTED"))
        with pytest.raises(RecoveryExecutionJournalError, match="JOURNAL_HEAD_CONFLICT"):
            tx.append(expected_head_sha256=before["head_sha256"], event=reservation())
        tx.append(expected_head_sha256=saved["event_sha256"], event=reservation())
    with pytest.raises(RecoveryExecutionJournalError, match="TRANSACTION_CLOSED"):
        tx.snapshot()


def test_two_thread_executors_only_one_cas_reservation(tmp_path):
    path = tmp_path / "journal.jsonl"
    journal = RecoveryExecutionJournal(path, **configuration())
    head = start(journal)["event_sha256"]
    barrier = threading.Barrier(2)
    def reserve(index):
        other = RecoveryExecutionJournal(path, **configuration())
        barrier.wait(timeout=5)
        try:
            other.append(expected_head_sha256=head, event=reservation(call=f"call-{index}"))
            return "RESERVED"
        except RecoveryExecutionJournalError as exc:
            return exc.code
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(reserve, [1, 2]))
    assert sorted(results) == ["JOURNAL_HEAD_CONFLICT", "RESERVED"]
    assert journal.snapshot()["consumed_simulated_dispatches"] == 1


def _process_reserve(path, cfg, head, ready, gate, results, index):
    resources = None
    if os.name == "nt":
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetCurrentProcess.restype = ctypes.c_void_p
        kernel.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        kernel.SetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
        kernel.GetPriorityClass.argtypes = [ctypes.c_void_p]
        kernel.GetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t), ctypes.POINTER(ctypes.c_size_t)]
        handle = kernel.GetCurrentProcess()
        assert kernel.SetPriorityClass(handle, 16384)
        assert kernel.SetProcessAffinityMask(handle, 2)
        process, system = ctypes.c_size_t(), ctypes.c_size_t()
        assert kernel.GetProcessAffinityMask(handle, ctypes.byref(process), ctypes.byref(system))
        resources = [kernel.GetPriorityClass(handle), process.value]
    for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
        os.environ[key] = "1"
    journal = RecoveryExecutionJournal(path, **cfg)
    ready.put(index)
    assert gate.wait(10)
    try:
        journal.append(expected_head_sha256=head, event=reservation(call=f"call-{index}"))
        results.put(("RESERVED", resources))
    except RecoveryExecutionJournalError as exc:
        results.put((exc.code, resources))


def test_two_process_executors_only_one_durable_reservation(tmp_path):
    path = tmp_path / "journal.jsonl"
    cfg = configuration()
    journal = RecoveryExecutionJournal(path, **cfg)
    head = start(journal)["event_sha256"]
    ctx = multiprocessing.get_context("spawn")
    ready, results, gate = ctx.Queue(), ctx.Queue(), ctx.Event()
    children = [ctx.Process(target=_process_reserve, args=(str(path), cfg, head, ready, gate, results, index)) for index in [1, 2]]
    try:
        for child in children:
            child.start()
        assert {ready.get(timeout=15), ready.get(timeout=15)} == {1, 2}
        gate.set()
        outcomes = [results.get(timeout=15), results.get(timeout=15)]
        for child in children:
            child.join(15)
            assert child.exitcode == 0
        assert sorted(row[0] for row in outcomes) == ["JOURNAL_HEAD_CONFLICT", "RESERVED"]
        if os.name == "nt":
            assert all(row[1] == [16384, 2] for row in outcomes)
        assert journal.snapshot()["consumed_simulated_dispatches"] == 1
    finally:
        for child in children:
            if child.is_alive():
                child.terminate()
                child.join(5)
        for queue in (ready, results):
            queue.close()
            queue.join_thread()


def test_late_success_clock_regression_and_output_cap(tmp_path):
    journal = RecoveryExecutionJournal(tmp_path / "journal.jsonl", **configuration())
    start(journal, elapsed=2)
    with pytest.raises(RecoveryExecutionJournalError, match="CLOCK_REGRESSION"):
        append(journal, reservation(elapsed=1))
    append(journal, reservation(elapsed=3))
    with pytest.raises(RecoveryExecutionJournalError, match="LATE_SUCCESS_FORBIDDEN"):
        append(journal, action_terminal(elapsed=34))
    bad = action_terminal(elapsed=4)
    bad["payload"].update(response_sha256="a" * 64, response_bytes=4097)
    with pytest.raises(RecoveryExecutionJournalError, match="OUTPUT_LIMIT"):
        append(journal, bad)
    append(journal, action_terminal(elapsed=33))
    append(journal, terminal(elapsed=100))
    assert journal.snapshot()["consumed_elapsed_ms"] == 100


def test_binding_input_types_and_policy_hash_are_strict(tmp_path):
    cfg = configuration()
    cfg["binding"]["post_id"] = True
    with pytest.raises(RecoveryExecutionJournalError):
        RecoveryExecutionJournal(tmp_path / "journal.jsonl", **cfg)
    cfg = configuration()
    cfg["policy"]["max_elapsed_ms"] = 101
    with pytest.raises(RecoveryExecutionJournalError, match="POLICY_SHA256_MISMATCH"):
        RecoveryExecutionJournal(tmp_path / "journal.jsonl", **cfg)
    assert not list(tmp_path.iterdir())


def test_id_namespaces_and_strict_canonical_json(tmp_path):
    journal = RecoveryExecutionJournal(tmp_path / "journal.jsonl", **configuration())
    with pytest.raises(RecoveryExecutionJournalError, match="ATTEMPT_ID_COLLISION"):
        start(journal, attempt="base-attempt")
    with pytest.raises(RecoveryExecutionJournalError, match="SESSION_ID_COLLISION"):
        start(journal, session="base-attempt")
    start(journal)
    with pytest.raises(RecoveryExecutionJournalError, match="DUPLICATE_CALL_ID"):
        append(journal, reservation(call="session-1"))
    for value in ({1: "not-json-key"}, ("not-json-array",), {"score": float("inf")}):
        with pytest.raises(RecoveryExecutionJournalError, match="INVALID_JSON"):
            canonical_sha256(value)


def test_hardlinked_journal_and_lock_are_not_written(tmp_path):
    original = tmp_path / "protected"
    original.write_bytes(b"")
    target = tmp_path / "journal.jsonl"
    try:
        os.link(original, target)
    except OSError:
        pytest.skip("hardlink unavailable on fixture filesystem")
    journal = RecoveryExecutionJournal(target, **configuration())
    with pytest.raises(RecoveryExecutionJournalError, match="INVALID_JOURNAL_PATH"):
        start(journal)
    assert original.read_bytes() == b""
    second = tmp_path / "other.jsonl"
    os.link(original, str(second) + ".lock")
    journal = RecoveryExecutionJournal(second, **configuration())
    with pytest.raises(RecoveryExecutionJournalError, match="INVALID_LOCK_PATH"):
        start(journal)
    assert original.read_bytes() == b""


@pytest.mark.parametrize("confirmed_elapsed", [10, 11])
def test_cancel_confirmation_before_or_at_grace_boundary(tmp_path, confirmed_elapsed):
    journal = RecoveryExecutionJournal(tmp_path / "journal.jsonl", **configuration(cancel_grace_ms=10))
    start(journal)
    append(journal, reservation())
    append(journal, intent("CANCEL_REQUESTED", {"reason_code": "USER_CANCEL"}, elapsed=1))
    attempt = journal.snapshot()["attempts"]["attempt-1"]
    assert attempt["cancel_requested_elapsed_ms"] == 1
    assert attempt["cancel_pending_call_ids"] == ["call-1"]
    append(journal, action_terminal("CANCEL_CONFIRMED", elapsed=confirmed_elapsed))
    # 유예 내 실제 중단 확인 뒤의 bookkeeping 시간은 확인 지연으로 바꾸지 않는다.
    append(journal, terminal("CANCELLED", elapsed=20))
    assert journal.snapshot()["attempts"]["attempt-1"]["terminal"]["payload"]["status"] == "CANCELLED"


def test_late_cancel_confirmation_rejected_and_resealed_replay_rejected(tmp_path):
    cfg = configuration(cancel_grace_ms=10)
    journal = RecoveryExecutionJournal(tmp_path / "journal.jsonl", **cfg)
    start(journal)
    append(journal, reservation())
    append(journal, intent("CANCEL_REQUESTED", {"reason_code": "USER_CANCEL"}, elapsed=1))
    before = journal.path.read_bytes()
    with pytest.raises(RecoveryExecutionJournalError, match="CANCEL_GRACE_EXCEEDED"):
        append(journal, action_terminal("CANCEL_CONFIRMED", elapsed=12))
    assert journal.path.read_bytes() == before
    append(journal, action_terminal("CANCEL_CONFIRMED", elapsed=11))
    append(journal, terminal("CANCELLED", elapsed=13))
    forged = journal.snapshot()["events"]
    next(event for event in forged if event["event_type"] == "ACTION_TERMINAL")["elapsed_ms"] = 12
    with pytest.raises(RecoveryExecutionJournalError, match="CANCEL_GRACE_EXCEEDED"):
        validate_execution_events(reseal(forged), **cfg)


def test_late_unconfirmed_cancel_stays_incomplete(tmp_path):
    journal = RecoveryExecutionJournal(tmp_path / "journal.jsonl", **configuration(cancel_grace_ms=10))
    start(journal)
    append(journal, reservation())
    append(journal, intent("CANCEL_REQUESTED", {"reason_code": "USER_CANCEL"}, elapsed=1))
    append(journal, action_terminal("NO_RESPONSE", elapsed=12))
    with pytest.raises(RecoveryExecutionJournalError, match="INCOMPLETE_DISPATCH"):
        append(journal, terminal("CANCELLED", elapsed=12))
    append(journal, terminal("INCOMPLETE", elapsed=12))
    assert journal.snapshot()["consumed_simulated_dispatches"] == 1


def test_failure_does_not_fabricate_cancel_confirmation(tmp_path):
    journal = RecoveryExecutionJournal(tmp_path / "journal.jsonl", **configuration())
    start(journal)
    append(journal, reservation())
    append(journal, intent("CANCEL_REQUESTED", {"reason_code": "USER_CANCEL"}, elapsed=1))
    append(journal, action_terminal("PERMANENT_FAILURE", elapsed=2))
    with pytest.raises(RecoveryExecutionJournalError, match="CANCELLATION_NOT_CONFIRMED"):
        append(journal, terminal("CANCELLED", elapsed=2))
    append(journal, terminal("INCOMPLETE", elapsed=2))


def test_predispatch_and_spontaneous_cancel_have_no_inflight_grace_claim(tmp_path):
    first = RecoveryExecutionJournal(tmp_path / "first.jsonl", **configuration(cancel_grace_ms=0))
    start(first)
    append(first, intent("CANCEL_REQUESTED", {"reason_code": "USER_CANCEL"}, elapsed=1))
    append(first, terminal("CANCELLED", elapsed=20))
    assert first.snapshot()["attempts"]["attempt-1"]["cancel_pending_call_ids"] == []
    second = RecoveryExecutionJournal(tmp_path / "second.jsonl", **configuration(cancel_grace_ms=0))
    start(second)
    append(second, reservation())
    append(second, action_terminal("CANCEL_CONFIRMED", elapsed=20))
    append(second, terminal("CANCELLED", elapsed=21))
    assert second.snapshot()["attempts"]["attempt-1"]["cancel_requested_elapsed_ms"] is None


@pytest.mark.parametrize("target_kind", ["existing_journal", "new_journal", "existing_lock", "new_lock"])
@pytest.mark.parametrize("link_kind", ["hardlink", "symlink"])
def test_preopen_link_replacement_never_writes_protected_bytes(tmp_path, target_kind, link_kind):
    path = tmp_path / "journal.jsonl"
    journal = RecoveryExecutionJournal(path, **configuration())
    if target_kind == "existing_journal":
        start(journal)
    target = Path(str(path) + ".lock") if "lock" in target_kind else path
    if target_kind == "existing_lock":
        target.write_bytes(b"")
    protected = tmp_path / "protected-original"
    protected_raw = b"" if "lock" in target_kind else b"original result must remain unchanged\n"
    protected.write_bytes(protected_raw)
    if link_kind == "symlink":
        probe = tmp_path / "symlink-capability"
        try:
            probe.symlink_to(protected)
        except OSError:
            pytest.skip("symlink creation unavailable for this account")
        probe.unlink()
    real_open = os.open
    injected = False
    def replaced_open(name, flags, *args, **kwargs):
        nonlocal injected
        if Path(name) == target and flags & (os.O_WRONLY | os.O_RDWR) and not injected:
            injected = True
            if target.exists():
                target.unlink()
            if link_kind == "hardlink":
                os.link(protected, target)
            else:
                target.symlink_to(protected)
        return real_open(name, flags, *args, **kwargs)
    event = reservation() if target_kind == "existing_journal" else intent("ATTEMPT_STARTED")
    head = journal.snapshot()["head_sha256"]
    with patch.object(module.os, "open", side_effect=replaced_open):
        with pytest.raises((RecoveryExecutionJournalError, OSError)):
            journal.append(expected_head_sha256=head, event=event)
    assert injected
    assert protected.read_bytes() == protected_raw
    assert target.read_bytes() == protected_raw


@pytest.mark.parametrize("target_kind", ["journal", "lock"])
def test_opened_wrong_single_link_handle_is_rejected_before_write(tmp_path, target_kind):
    path = tmp_path / "journal.jsonl"
    journal = RecoveryExecutionJournal(path, **configuration())
    if target_kind == "journal":
        start(journal)
    else:
        Path(str(path) + ".lock").write_bytes(b"")
    target = path if target_kind == "journal" else Path(str(path) + ".lock")
    protected = tmp_path / "protected-single-link"
    protected_raw = b"private original\n" if target_kind == "journal" else b""
    protected.write_bytes(protected_raw)
    real_open = os.open
    injected = False
    def wrong_open(name, flags, *args, **kwargs):
        nonlocal injected
        if Path(name) == target and flags & (os.O_WRONLY | os.O_RDWR) and not injected:
            injected = True
            return real_open(protected, os.O_RDWR | getattr(os, "O_BINARY", 0))
        return real_open(name, flags, *args, **kwargs)
    event = reservation() if target_kind == "journal" else intent("ATTEMPT_STARTED")
    head = journal.snapshot()["head_sha256"]
    before = target.read_bytes()
    with patch.object(module.os, "open", side_effect=wrong_open):
        with pytest.raises(RecoveryExecutionJournalError, match="FILE_IDENTITY_CHANGED"):
            journal.append(expected_head_sha256=head, event=event)
    assert injected
    assert target.read_bytes() == before
    assert protected.read_bytes() == protected_raw


@pytest.mark.parametrize("candidate_status", ["COMPLETED_SIMULATION", "FAILED", "CANCELLED"])
def test_terminal_without_finalization_cannot_release_next_attempt(tmp_path, candidate_status):
    journal = RecoveryExecutionJournal(tmp_path / "journal.jsonl", **configuration())
    start(journal)
    if candidate_status == "COMPLETED_SIMULATION":
        append(journal, reservation())
        append(journal, action_terminal())
    elif candidate_status == "CANCELLED":
        append(journal, intent("CANCEL_REQUESTED", {"reason_code": "USER_CANCEL"}))
    candidate = append(journal, terminal(candidate_status, elapsed=5), finalize=False)
    state = journal.snapshot()
    assert state["attempts"]["attempt-1"]["terminal"] == candidate
    assert state["attempts"]["attempt-1"]["finalized"] is None
    assert state["pending_finalization_attempt_ids"] == ["attempt-1"]
    assert state["finalized_attempt_ids"] == []
    assert state["active_attempt_id"] == "attempt-1"
    with pytest.raises(RecoveryExecutionJournalError, match="ATTEMPT_NOT_FINALIZED"):
        start(journal, attempt="attempt-2")
    final = append(journal, finalization(candidate, elapsed=8))
    state = journal.snapshot()
    assert state["attempts"]["attempt-1"]["finalized"] == final
    assert state["pending_finalization_attempt_ids"] == []
    assert state["finalized_attempt_ids"] == ["attempt-1"]
    assert state["consumed_elapsed_ms"] == 8
    start(journal, attempt="attempt-2", elapsed=1)
    assert journal.snapshot()["consumed_elapsed_ms"] == 9


@pytest.mark.parametrize("elapsed", [10, 11])
def test_finalization_includes_terminal_durable_time_in_budget(tmp_path, elapsed):
    journal = RecoveryExecutionJournal(tmp_path / "journal.jsonl", **configuration(max_elapsed_ms=10))
    start(journal)
    append(journal, reservation(elapsed=1))
    append(journal, action_terminal(elapsed=3))
    candidate = append(journal, terminal(elapsed=9), finalize=False)
    if elapsed == 11:
        with pytest.raises(RecoveryExecutionJournalError, match="LATE_SUCCESS_FORBIDDEN"):
            append(journal, finalization(candidate, elapsed=elapsed))
        final = append(journal, finalization(candidate, elapsed=elapsed, status="BUDGET_EXHAUSTED",
                                             reasons=["TERMINAL_DURABLE_TIME_EXCEEDED"]))
    else:
        final = append(journal, finalization(candidate, elapsed=elapsed))
    state = journal.snapshot()
    assert state["consumed_elapsed_ms"] == elapsed
    assert final["payload"]["status"] == ("COMPLETED_SIMULATION" if elapsed == 10 else "BUDGET_EXHAUSTED")
    assert state["attempts"]["attempt-1"]["terminal"]["payload"]["status"] == "COMPLETED_SIMULATION"


@pytest.mark.parametrize("change,code", [
    ({"terminal_event_sha256": "f" * 64}, "FINALIZATION_TERMINAL_MISMATCH"),
    ({"budget_observation_scope": "FUNCTION_RETURN"}, "INVALID_FINALIZATION_SCOPE"),
    ({"status": "COMPLETED_SIMULATION"}, "INVALID_FINALIZATION_STATUS"),
    ({"status": "INCOMPLETE", "reason_codes": []}, "INVALID_FINALIZATION_STATUS"),
])
def test_finalization_binding_status_scope_and_reason_are_strict(tmp_path, change, code):
    journal = RecoveryExecutionJournal(tmp_path / "journal.jsonl", **configuration())
    start(journal)
    candidate = append(journal, terminal("FAILED", elapsed=1), finalize=False)
    event = finalization(candidate, elapsed=2)
    event["payload"].update(change)
    before = journal.path.read_bytes()
    with pytest.raises(RecoveryExecutionJournalError, match=code):
        append(journal, event)
    assert journal.path.read_bytes() == before


def test_finalization_is_once_and_can_only_downgrade_to_uncertainty(tmp_path):
    journal = RecoveryExecutionJournal(tmp_path / "journal.jsonl", **configuration())
    start(journal)
    with pytest.raises(RecoveryExecutionJournalError, match="ATTEMPT_NOT_TERMINAL"):
        append(journal, intent("ATTEMPT_FINALIZED", {}))
    candidate = append(journal, terminal("FAILED", elapsed=1), finalize=False)
    event = finalization(candidate, elapsed=2, status="INCOMPLETE", reasons=["POST_TERMINAL_OBSERVATION_FAILED"])
    append(journal, event)
    with pytest.raises(RecoveryExecutionJournalError, match="ATTEMPT_ALREADY_FINALIZED"):
        append(journal, event)
    with pytest.raises(RecoveryExecutionJournalError, match="INCOMPLETE_DISPATCH"):
        start(journal, attempt="attempt-2")


def test_failure_finalization_preserves_reasons_and_terminal_write_budget(tmp_path):
    journal = RecoveryExecutionJournal(tmp_path / "journal.jsonl", **configuration(max_elapsed_ms=10))
    start(journal)
    event = terminal("FAILED", elapsed=9)
    event["payload"]["reason_codes"] = ["DECLARED_FAILURE"]
    candidate = append(journal, event, finalize=False)
    with pytest.raises(RecoveryExecutionJournalError, match="FINALIZATION_REASON_MISMATCH"):
        append(journal, finalization(candidate, elapsed=10, reasons=[]))
    with pytest.raises(RecoveryExecutionJournalError, match="FINALIZATION_TIME_BUDGET_EXCEEDED"):
        append(journal, finalization(candidate, elapsed=11))
    append(journal, finalization(candidate, elapsed=11, status="BUDGET_EXHAUSTED",
                                 reasons=["DECLARED_FAILURE", "TERMINAL_DURABLE_TIME_EXCEEDED"]))
    start(journal, attempt="attempt-2")
    with pytest.raises(RecoveryExecutionJournalError, match="TIME_BUDGET_EXHAUSTED"):
        append(journal, reservation(attempt="attempt-2"))
