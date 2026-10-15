"""별도 provider 원장의 실제 파일 CAS/재생 시험. 총괄 묶음에서만 실행한다."""
from copy import deepcopy
import hashlib
import os
from concurrent.futures import ThreadPoolExecutor

import pytest

from src.llm_batch.ledger import recovery_provider_journal as journal
from src.llm_batch.runtime import recovery_transport as transport


def configuration_case(count=2, **overrides):
    policy = {"max_calls": 2, "max_elapsed_ms": 10000, "request_timeout_ms": 5000,
              "max_response_bytes": 4096, "max_total_response_bytes": 8192, **overrides}
    binding = {"plan_sha256": "a" * 64, "base_sha256": "b" * 64, "source_sha256": "c" * 64,
        "config_sha256": "d" * 64, "policy_sha256": journal.canonical_sha256(policy),
        "publication_scope_id": "scope-provider", "input_index": 1, "post_id": 345,
        "base_attempt_run_id": "original-attempt"}
    endpoint = "http://fixture.invalid/search"
    payloads = [{"query": f"원문 검색 {i}", "purpose": "source-bound-recovery", "num_results": 2} for i in range(count)]
    requests = [{"request_id": f"request-{i}", "kind": "MCP_SEARCH",
                 "body_sha256": hashlib.sha256(transport._payload("MCP_SEARCH", payload)).hexdigest(),
                 "endpoint_sha256": hashlib.sha256(transport._endpoint(endpoint).encode()).hexdigest()}
                for i,payload in enumerate(payloads)]
    return {"binding": binding, "policy": policy, "requests": requests}, payloads, endpoint


def new_journal(tmp_path, **overrides):
    config, _, _ = configuration_case(**overrides)
    return journal.RecoveryProviderJournal(tmp_path / "provider.jsonl", **config)


def emit(value, kind, payload, elapsed=0):
    return value.append(expected_head_sha256=value.snapshot()["head_sha256"],
                        event={"event_type": kind, "elapsed_ms": elapsed, "payload": payload})


def start(value):
    return emit(value, "JOB_STARTED", {"owner_epoch": "owner-1", "transport_mode": "TEST_DOUBLE"})


def reserve(value, index=0, elapsed=1, *, request_started=None):
    config = value.snapshot()
    request = config["requests"][index]
    request_started = elapsed if request_started is None else request_started
    return emit(value, "REQUEST_RESERVED", {"request_id": request["request_id"],
        "request_sha256": journal.request_identity(config["binding"], config["policy"], request)["request_sha256"],
        "reservation_id": f"reservation-{index}", "ordinal": index + 1,
        "response_bytes_reserved": config["policy"]["max_response_bytes"],
        "request_started_elapsed_ms": request_started,
        "request_deadline_elapsed_ms": min(config["policy"]["max_elapsed_ms"],
            request_started + config["policy"]["request_timeout_ms"])}, elapsed)


def terminal(value, index=0, status="SUCCESS", elapsed=2):
    return emit(value, "REQUEST_TERMINAL", {"request_id": f"request-{index}", "status": status,
        "response_ref": {"path": "responses/" + "e"*64 + ".bin", "sha256": "f"*64, "bytes": 2} if status == "SUCCESS" else None,
        "transport_ref": {"path": "responses/" + "e"*64 + ".json", "sha256": "f"*64, "bytes": 100},
        "transport_receipt_sha256": "f"*64, "observed_response_bytes": 2,
        "transport_invocations": 1, "actual_external_calls": 0}, elapsed)


def finalize(value, end, elapsed=3):
    status = end["payload"]["status"]
    return emit(value, "REQUEST_FINALIZED", {"request_id": end["payload"]["request_id"],
        "terminal_sha256": end["event_sha256"], "status": status,
        "reason_codes": [] if status == "SUCCESS" else [status]}, elapsed)


def test_constructor_and_empty_read_do_not_create_any_file(tmp_path):
    value = new_journal(tmp_path)
    assert value.snapshot()["head_sha256"] == journal.GENESIS
    assert list(tmp_path.iterdir()) == []


def test_file_replay_keeps_reserved_budget_and_isolates_caller_mutation(tmp_path):
    value = new_journal(tmp_path); start(value); reserve(value)
    end = terminal(value); finalize(value, end)
    before = value.path.read_bytes()
    state = value.snapshot()
    assert state["budget"] == {"reservations_consumed": 1, "reserved_response_bytes": 4096,
        "observed_response_bytes": 2, "transport_invocations": 1, "actual_external_calls": 0}
    state["budget"]["reservations_consumed"] = 0
    reopened = new_journal(tmp_path)
    assert reopened.snapshot()["budget"]["reservations_consumed"] == 1
    reserve(reopened, 1, 4); finalize(reopened, terminal(reopened, 1, elapsed=5), 6)
    assert reopened.snapshot()["budget"]["reserved_response_bytes"] == 8192
    assert reopened.path.read_bytes().startswith(before)


def test_reserved_or_terminal_without_finalization_blocks_every_other_request(tmp_path):
    value = new_journal(tmp_path); start(value); reserve(value)
    with pytest.raises(journal.RecoveryProviderJournalError, match="INCOMPLETE_DISPATCH"):
        reserve(new_journal(tmp_path), 1)
    terminal(value)
    with pytest.raises(journal.RecoveryProviderJournalError, match="INCOMPLETE_DISPATCH"):
        reserve(new_journal(tmp_path), 1, 3)


@pytest.mark.parametrize("change", ["post_type", "source", "path", "request"])
def test_reopening_cannot_rebind_a_saved_plan_or_journal_path(tmp_path, change):
    value = new_journal(tmp_path); start(value)
    config, _, _ = configuration_case()
    path = value.path
    if change == "post_type": config["binding"]["post_id"] = "345"
    elif change == "source": config["binding"]["source_sha256"] = "f"*64
    elif change == "request": config["requests"][0]["body_sha256"] = "f"*64
    else:
        path = tmp_path / "copied.jsonl"; path.write_bytes(value.path.read_bytes())
    with pytest.raises(journal.RecoveryProviderJournalError, match="EVENT_BINDING_MISMATCH"):
        journal.RecoveryProviderJournal(path, **config).snapshot()


@pytest.mark.parametrize("limit", ["max_calls", "max_total_response_bytes"])
def test_zero_budget_cannot_reserve(tmp_path, limit):
    value = new_journal(tmp_path, **{limit: 0}); start(value)
    before = value.path.read_bytes()
    with pytest.raises(journal.RecoveryProviderJournalError, match="BUDGET_EXHAUSTED"):
        reserve(value)
    assert value.path.read_bytes() == before


def test_terminal_failure_keeps_slot_and_blocks_retry_or_next_request(tmp_path):
    value = new_journal(tmp_path); start(value); reserve(value)
    finalize(value, terminal(value, status="TIMEOUT_UNCONFIRMED"))
    state = value.snapshot()
    assert state["budget"]["reservations_consumed"] == 1
    assert state["budget"]["reserved_response_bytes"] == 4096
    with pytest.raises(journal.RecoveryProviderJournalError, match="INCOMPLETE_DISPATCH"):
        reserve(value, 1, 4)


def test_partial_tail_is_preserved_and_never_repaired(tmp_path):
    value = new_journal(tmp_path); start(value)
    with value.path.open("ab") as stream: stream.write(b'{"partial":')
    raw = value.path.read_bytes()
    with pytest.raises(journal.RecoveryProviderJournalError, match="INCOMPLETE_JOURNAL"):
        value.snapshot()
    assert value.path.read_bytes() == raw


def test_fsync_failure_never_returns_an_ack_but_consumed_reservation_remains(tmp_path, monkeypatch):
    value = new_journal(tmp_path); start(value)
    monkeypatch.setattr(journal.os, "fsync", lambda fd: (_ for _ in ()).throw(OSError("private path")))
    with pytest.raises(OSError): reserve(value)
    state = value.snapshot()
    assert state["open_request_id"] == "request-0"
    assert state["budget"]["reservations_consumed"] == 1


def test_stale_cas_and_closed_transaction_cannot_append(tmp_path):
    value = new_journal(tmp_path)
    with value.transaction() as tx:
        tx.append(expected_head_sha256=journal.GENESIS, event={"event_type": "JOB_STARTED", "elapsed_ms": 0,
            "payload": {"owner_epoch": "one", "transport_mode": "TEST_DOUBLE"}})
        with pytest.raises(journal.RecoveryProviderJournalError, match="JOURNAL_HEAD_CONFLICT"):
            tx.append(expected_head_sha256=journal.GENESIS, event={})
    with pytest.raises(journal.RecoveryProviderJournalError, match="TRANSACTION_CLOSED"):
        tx.snapshot()


def test_two_threads_only_one_same_head_start_is_durable(tmp_path):
    value = new_journal(tmp_path)
    def append(owner):
        try:
            return value.append(expected_head_sha256=journal.GENESIS, event={"event_type": "JOB_STARTED", "elapsed_ms": 0,
                "payload": {"owner_epoch": owner, "transport_mode": "TEST_DOUBLE"}})["event_type"]
        except journal.RecoveryProviderJournalError as exc:
            return exc.code
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(append, ["one", "two"]))
    assert sorted(outcomes) == ["JOB_STARTED", "JOURNAL_HEAD_CONFLICT"]
    assert len(value.snapshot()["events"]) == 1


def test_late_success_and_fake_mock_actual_count_are_rejected(tmp_path):
    value = new_journal(tmp_path, max_elapsed_ms=5); start(value); reserve(value)
    with pytest.raises(journal.RecoveryProviderJournalError, match="LATE_SUCCESS"):
        terminal(value, elapsed=5)
    end = terminal(value)
    state = value.snapshot()
    events = deepcopy(state["events"])
    events[-1]["payload"]["actual_external_calls"] = 1
    events[-1]["event_sha256"] = journal.canonical_sha256({k:v for k,v in events[-1].items() if k != "event_sha256"})
    raw = b"".join(journal.canonical_bytes(e)+b"\n" for e in events)
    with pytest.raises(journal.RecoveryProviderJournalError, match="ACTUAL_CALL_SCOPE_INVALID"):
        journal.read_provider_journal(raw, binding=value.binding, policy=value.policy,
            requests=value.requests, journal_path=value.path)
    finalize(value, end)


@pytest.mark.parametrize("late_stage", ["terminal", "finalized"])
def test_resealed_late_success_uses_request_start_not_reservation_time(tmp_path, late_stage):
    value = new_journal(tmp_path, max_elapsed_ms=1000, request_timeout_ms=100)
    start(value); reserve(value, elapsed=80, request_started=0)
    end = terminal(value, elapsed=90); finalize(value, end, elapsed=91)
    original = value.path.read_bytes()
    events = deepcopy(value.snapshot()["events"])
    target = "REQUEST_TERMINAL" if late_stage == "terminal" else "REQUEST_FINALIZED"
    for event in events:
        if event["event_type"] == target:
            event["elapsed_ms"] = 140
    if late_stage == "terminal":
        events[-1]["elapsed_ms"] = 141
    # 외부 checksum만 고친 반례가 아니라 hash chain/terminal link까지 다시 봉인한다.
    previous = journal.GENESIS
    terminal_sha = None
    for event in events:
        event["prev_event_sha256"] = previous
        if event["event_type"] == "REQUEST_FINALIZED":
            event["payload"]["terminal_sha256"] = terminal_sha
        event["event_sha256"] = journal.canonical_sha256({k:v for k,v in event.items() if k != "event_sha256"})
        if event["event_type"] == "REQUEST_TERMINAL":
            terminal_sha = event["event_sha256"]
        previous = event["event_sha256"]
    raw = b"".join(journal.canonical_bytes(e) + b"\n" for e in events)
    with pytest.raises(journal.RecoveryProviderJournalError, match="LATE_SUCCESS"):
        journal.read_provider_journal(raw, binding=value.binding, policy=value.policy,
            requests=value.requests, journal_path=value.path)
    assert value.path.read_bytes() == original
    assert new_journal(tmp_path, max_elapsed_ms=1000, request_timeout_ms=100).snapshot()["calls"]["request-0"]["finalized"]["payload"]["status"] == "SUCCESS"


@pytest.mark.parametrize("fault", ["late_reservation", "extended_deadline", "start_after_reservation"])
def test_reservation_deadline_is_exact_and_cannot_reset_elapsed_budget(tmp_path, fault):
    value = new_journal(tmp_path, max_elapsed_ms=1000, request_timeout_ms=100)
    start(value)
    if fault == "late_reservation":
        before = value.path.read_bytes()
        with pytest.raises(journal.RecoveryProviderJournalError, match="TIME_BUDGET_EXHAUSTED"):
            reserve(value, elapsed=100, request_started=0)
        assert value.path.read_bytes() == before
        return
    saved = reserve(value, elapsed=80, request_started=0)
    events = deepcopy(value.snapshot()["events"])
    if fault == "extended_deadline":
        events[-1]["payload"]["request_deadline_elapsed_ms"] = 180
    else:
        events[-1]["payload"]["request_started_elapsed_ms"] = 81
        events[-1]["payload"]["request_deadline_elapsed_ms"] = 181
    events[-1]["event_sha256"] = journal.canonical_sha256({k:v for k,v in events[-1].items() if k != "event_sha256"})
    raw = b"".join(journal.canonical_bytes(e) + b"\n" for e in events)
    with pytest.raises(journal.RecoveryProviderJournalError, match="REQUEST_DEADLINE_INVALID"):
        journal.read_provider_journal(raw, binding=value.binding, policy=value.policy,
            requests=value.requests, journal_path=value.path)
    assert value.snapshot()["calls"]["request-0"]["reserved"] == saved


def test_response_path_cannot_escape_or_hardlink_journal(tmp_path):
    value = new_journal(tmp_path); start(value)
    linked = tmp_path / "linked.jsonl"
    os.link(value.path, linked)
    with pytest.raises(ValueError): value.snapshot()
    assert linked.read_bytes() == value.path.read_bytes()
    with pytest.raises(journal.RecoveryProviderJournalError, match="RESPONSE_PATH_INVALID"):
        journal._ref({"path": "../source.json", "sha256": "a"*64, "bytes": 5})
