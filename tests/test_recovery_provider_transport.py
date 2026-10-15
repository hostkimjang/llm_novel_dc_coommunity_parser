"""실제 파일 원장 + 단일 HTTP mock. 모델·네트워크 호출은 없다."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import httpx
import pytest

from src.llm_batch.runtime import recovery_provider_transport as provider
from src.llm_batch.ledger import recovery_provider_journal as journal
from test_recovery_provider_journal import configuration_case


class Clock:
    def __init__(self): self.value = 1000
    def __call__(self): return self.value


class Body(httpx.SyncByteStream):
    def __init__(self, raw, before=None): self.raw, self.before = raw, before
    def __iter__(self):
        if self.before: self.before()
        yield self.raw


def response(raw=b'{ "results" : [ { "title": "synthetic" } ] }', status=200, before=None):
    return httpx.Response(status, stream=Body(raw, before))


def case(tmp_path, handler=None, config=None, state=None, clock=None):
    config, payloads, endpoint = configuration_case() if config is None else config
    clock = clock or Clock()
    state = state if state is not None else {"sent": [], "source": True, "cancelled": False}
    path = tmp_path / "provider.jsonl"
    def handle(request):
        # 실제 전송 전에 파일 예약을 재판독할 수 있어야 한다.
        snap = journal.RecoveryProviderJournal(path, **config).snapshot()
        assert snap["open_request_id"] is not None
        state["sent"].append(request)
        return handler(request, state, clock) if handler else response()
    runner = provider.RecoveryProviderRunner(**config, journal_path=path,
        endpoints={"MCP_SEARCH": endpoint}, source_check=lambda: state["source"],
        cancelled=lambda: state["cancelled"], test_transport=httpx.MockTransport(handle), clock_ms=clock)
    return runner, payloads, state, clock


def call(runner, payloads, index=0):
    return runner.request("MCP_SEARCH", payloads[index], request_id=f"request-{index}")


def test_success_stores_exact_raw_and_terminal_then_new_runner_replays_zero_requests(tmp_path):
    runner, payloads, state, clock = case(tmp_path)
    result = call(runner, payloads)
    assert result["status"] == "SUCCESS" and result["payload"]["results"][0]["title"] == "synthetic"
    assert result["actual_external_calls"] == 0 and result["transport_invocations_this_invocation"] == 1
    assert result["remote_dispatch_count"] is None and result["remote_dispatch_status"] == "UNKNOWN"
    assert not any(result[k] for k in journal.FLAGS)
    raw = (tmp_path / result["response_ref"]["path"]).read_bytes()
    assert raw.startswith(b'{ "results"')  # 정규화 JSON으로 원시 bytes를 대체하지 않는다.
    assert hashlib.sha256(raw).hexdigest() == result["response_ref"]["sha256"]
    assert result["transport_receipt_sha256"] == result["transport_receipt"]["receipt_sha256"]
    assert [e["event_type"] for e in runner.journal.snapshot()["events"]] == ["JOB_STARTED", "REQUEST_RESERVED", "REQUEST_TERMINAL", "REQUEST_FINALIZED"]
    before = {str(p):p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    clock.value += 100000
    restarted, _, _, _ = case(tmp_path, state=state, clock=clock)
    replay = call(restarted, payloads)
    assert replay["status"] == "SUCCESS" and replay["replayed"] is True
    assert replay["transport_invocations"] == replay["actual_external_calls"] == 0
    assert replay["response_ref"] == result["response_ref"] and len(state["sent"]) == 1
    assert {str(p):p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()} == before


def test_explicit_readback_never_turns_unstarted_work_into_dispatch(tmp_path):
    runner, payloads, state, _ = case(tmp_path)
    assert runner.readback(request_id="request-0")["status"] == "NOT_STARTED"
    assert state["sent"] == [] and list(tmp_path.iterdir()) == []
    assert call(runner, payloads)["status"] == "SUCCESS"
    before = {str(p):p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    assert runner.readback(request_id="request-0")["status"] == "SUCCESS"
    assert runner.readback(request_id="request-1")["status"] == "NOT_STARTED"
    assert len(state["sent"]) == 1
    assert {str(p):p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()} == before


def test_sequential_requests_use_cumulative_reserved_bytes_not_observed_small_body(tmp_path):
    runner, payloads, state, _ = case(tmp_path)
    first = call(runner, payloads); second = call(runner, payloads, 1)
    assert first["status"] == second["status"] == "SUCCESS"
    assert second["budget"]["reserved_response_bytes"] == 8192
    assert second["budget"]["observed_response_bytes"] < 8192
    assert second["budget"]["transport_invocations"] == len(state["sent"]) == 2


def test_restart_never_assigns_a_new_deadline_to_unstarted_request(tmp_path):
    runner, payloads, state, clock = case(tmp_path)
    assert call(runner, payloads)["status"] == "SUCCESS"
    restarted, _, _, _ = case(tmp_path, state=state, clock=clock)
    result = call(restarted, payloads, 1)
    assert result["status"] == "NOT_AVAILABLE" and result["reason_codes"] == ["RESTART_TIME_UNVERIFIED"]
    assert len(state["sent"]) == 1


@pytest.mark.parametrize("failure", ["response_write", "transport_write", "terminal", "finalized"])
def test_storage_crash_does_not_publish_success_or_retry_on_restart(tmp_path, monkeypatch, failure):
    runner, payloads, state, clock = case(tmp_path)
    original_write, original_append = provider._write_new, journal._Transaction.append
    def write(path, raw):
        if failure == "response_write" and path.suffix == ".bin":
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as stream: stream.write(raw[:2])
            raise OSError("PRIVATE_DISK_PATH")
        if failure == "transport_write" and path.parent.name == "responses" and path.suffix == ".json":
            raise OSError("PRIVATE_DISK_PATH")
        return original_write(path, raw)
    def append(self, *, expected_head_sha256, event):
        if (failure == "terminal" and event["event_type"] == "REQUEST_TERMINAL") or (failure == "finalized" and event["event_type"] == "REQUEST_FINALIZED"):
            raise OSError("PRIVATE_DISK_PATH")
        return original_append(self, expected_head_sha256=expected_head_sha256, event=event)
    monkeypatch.setattr(provider, "_write_new", write)
    monkeypatch.setattr(journal._Transaction, "append", append)
    result = call(runner, payloads)
    assert result["status"] != "SUCCESS" and result["payload"] is None
    assert "PRIVATE_DISK_PATH" not in json.dumps(result)
    monkeypatch.setattr(provider, "_write_new", original_write)
    monkeypatch.setattr(journal._Transaction, "append", original_append)
    restarted, _, _, _ = case(tmp_path, state=state, clock=clock)
    replay = call(restarted, payloads)
    assert replay["status"] != "SUCCESS" and len(state["sent"]) == 1
    assert replay["transport_invocations_this_invocation"] == 0


def test_reservation_fsync_failure_never_reaches_http_and_is_not_refunded(tmp_path, monkeypatch):
    runner, payloads, state, clock = case(tmp_path)
    original = journal._Transaction.append
    def append(self, *, expected_head_sha256, event):
        result = original(self, expected_head_sha256=expected_head_sha256, event=event)
        if event["event_type"] == "REQUEST_RESERVED": raise OSError("failed reservation readback")
        return result
    monkeypatch.setattr(journal._Transaction, "append", append)
    result = call(runner, payloads)
    assert result["status"] != "SUCCESS" and state["sent"] == []
    assert result["budget"]["reservations_consumed"] == 1
    restarted, _, _, _ = case(tmp_path, state=state, clock=clock)
    assert call(restarted, payloads)["status"] != "SUCCESS" and state["sent"] == []


@pytest.mark.parametrize("field", ["source", "cancelled"])
def test_fresh_guard_after_durable_reservation_prevents_send(tmp_path, monkeypatch, field):
    runner, payloads, state, _ = case(tmp_path)
    original = journal._Transaction.append
    def append(self, *, expected_head_sha256, event):
        result = original(self, expected_head_sha256=expected_head_sha256, event=event)
        if event["event_type"] == "REQUEST_RESERVED": state[field] = field == "cancelled"
        return result
    monkeypatch.setattr(journal._Transaction, "append", append)
    result = call(runner, payloads)
    assert result["status"] != "SUCCESS" and result["payload"] is None
    assert state["sent"] == [] and result["budget"]["reservations_consumed"] == 1


@pytest.mark.parametrize("failure", ["timeout", "connection", "http", "invalid_json", "oversize"])
def test_failure_is_one_local_attempt_and_never_a_confirmed_remote_outcome(tmp_path, failure):
    def handle(req, state, clock):
        if failure == "timeout": raise httpx.ReadTimeout("PRIVATE_URI")
        if failure == "connection": raise httpx.ConnectError("PRIVATE_URI")
        if failure == "http": return response(status=503)
        if failure == "invalid_json": return response(b'{"dup":1,"dup":2}')
        return response(b"x" * 5000)
    runner, payloads, state, clock = case(tmp_path, handle)
    result = call(runner, payloads)
    assert result["status"] != "SUCCESS" and result["payload"] is None
    assert result["remote_dispatch_count"] is None and result["remote_cancel_confirmed"] is None
    assert result["actual_external_calls"] == 0 and result["transport_invocations"] == 1
    restarted, _, _, _ = case(tmp_path, state=state, clock=clock)
    assert call(restarted, payloads)["status"] != "SUCCESS" and len(state["sent"]) == 1
    assert "PRIVATE_URI" not in json.dumps(result)


@pytest.mark.parametrize("fault", ["raw", "receipt", "source", "body", "delete_journal"])
def test_replay_requires_original_raw_receipt_source_and_exact_request(tmp_path, fault):
    runner, payloads, state, clock = case(tmp_path)
    result = call(runner, payloads)
    assert result["status"] == "SUCCESS"
    if fault == "raw": (tmp_path / result["response_ref"]["path"]).write_bytes(b"different")
    elif fault == "receipt": (tmp_path / result["transport_ref"]["path"]).write_bytes(b"{}")
    elif fault == "source": state["source"] = False
    elif fault == "body": payloads = deepcopy(payloads); payloads[0]["query"] += " 변경"
    else: runner.journal.path.unlink()
    restarted, _, _, _ = case(tmp_path, state=state, clock=clock)
    replay = call(restarted, payloads)
    assert replay["status"] != "SUCCESS" and replay["payload"] is None
    assert len(state["sent"]) == 1


@pytest.mark.parametrize("zero", ["max_calls", "max_total_response_bytes"])
def test_zero_budget_does_not_create_lock_anchor_or_journal(tmp_path, zero):
    runner, payloads, state, _ = case(tmp_path, config=configuration_case(**{zero: 0}))
    result = call(runner, payloads)
    assert result["status"] == "NOT_AVAILABLE" and state["sent"] == []
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("boundary", ["cancel", "source", "clock", "private_exception"])
def test_fresh_pre_send_callback_failure_has_no_request_or_error_message_leak(tmp_path, boundary):
    runner, payloads, state, clock = case(tmp_path)
    if boundary == "cancel": state["cancelled"] = True
    elif boundary == "source": state["source"] = False
    elif boundary == "clock": clock.value = 0
    else: runner._source_check = lambda: (_ for _ in ()).throw(OSError("PRIVATE_DISK_PATH"))
    result = call(runner, payloads)
    assert result["status"] == "NOT_AVAILABLE" and state["sent"] == []
    assert result["payload"] is None and "PRIVATE_DISK_PATH" not in json.dumps(result)


def test_terminal_storage_time_can_only_downgrade_success(tmp_path, monkeypatch):
    runner, payloads, state, clock = case(tmp_path)
    original = journal._Transaction.append
    def append(self, *, expected_head_sha256, event):
        result = original(self, expected_head_sha256=expected_head_sha256, event=event)
        if event["event_type"] == "REQUEST_TERMINAL": clock.value += 10000
        return result
    monkeypatch.setattr(journal._Transaction, "append", append)
    result = call(runner, payloads)
    assert result["status"] == "TIME_BUDGET_EXHAUSTED" and result["payload"] is None
    assert result["time_scope"] == "THROUGH_REQUEST_TERMINAL_DURABLE_READBACK"
    assert result["finalization_write_in_time_scope"] is False
    assert len(state["sent"]) == 1


@pytest.mark.parametrize("delay_stage", ["transport_write", "terminal_readback", "raw_readback"])
def test_initial_request_deadline_covers_reservation_storage_and_readback_on_restart(tmp_path, monkeypatch, delay_stage):
    config = configuration_case(max_elapsed_ms=1000, request_timeout_ms=100)
    def handle(req, state, clock):
        clock.value += 10
        return response()
    runner, payloads, state, clock = case(tmp_path, handle, config=config)
    original_reserve = runner._gate._reserve
    def delayed_reserve(proposal):
        clock.value += 80
        return original_reserve(proposal)
    monkeypatch.setattr(runner._gate, "_reserve", delayed_reserve)
    original_write, original_append, original_read = provider._write_new, journal._Transaction.append, runner._read_ref
    def write(path, raw):
        result = original_write(path, raw)
        if delay_stage == "transport_write" and path.parent.name == "responses" and path.suffix == ".json":
            clock.value += 50
        return result
    def append(self, *, expected_head_sha256, event):
        result = original_append(self, expected_head_sha256=expected_head_sha256, event=event)
        if delay_stage == "terminal_readback" and event["event_type"] == "REQUEST_TERMINAL":
            clock.value += 50
        return result
    def read(ref, maximum):
        result = original_read(ref, maximum)
        if delay_stage == "raw_readback" and ref["path"].endswith(".bin"):
            clock.value += 50
        return result
    monkeypatch.setattr(provider, "_write_new", write)
    monkeypatch.setattr(journal._Transaction, "append", append)
    monkeypatch.setattr(runner, "_read_ref", read)
    result = call(runner, payloads)
    assert clock.value == 1140  # job 예산 1000ms는 남지만 요청 제한 100ms는 지났다.
    assert result["status"] in {"INCOMPLETE", "TIME_BUDGET_EXHAUSTED"}
    assert result["reason_codes"] == ["TIME_BUDGET_EXHAUSTED"] and result["payload"] is None
    assert result["actual_external_calls"] == 0 and result["transport_invocations_this_invocation"] == 1
    reserved = runner.journal.snapshot()["calls"]["request-0"]["reserved"]
    assert reserved["elapsed_ms"] == 80
    assert reserved["payload"]["request_started_elapsed_ms"] == 0
    assert reserved["payload"]["request_deadline_elapsed_ms"] == 100
    original_files = {str(p):p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    restarted, _, _, _ = case(tmp_path, config=config, state=state, clock=clock)
    for replay in (restarted.readback(request_id="request-0"), call(restarted, payloads)):
        assert replay["status"] != "SUCCESS" and replay["payload"] is None
        assert replay["transport_invocations_this_invocation"] == 0
    assert len(state["sent"]) == 1
    assert {str(p):p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()} == original_files


def test_initial_fresh_source_check_does_not_restart_request_timeout(tmp_path):
    runner, payloads, state, clock = case(tmp_path,
        config=configuration_case(max_elapsed_ms=1000, request_timeout_ms=100))
    def slow_source():
        clock.value += 100
        return True
    runner._source_check = slow_source
    result = call(runner, payloads)
    assert result["status"] == "NOT_AVAILABLE" and result["reason_codes"] == ["TIME_BUDGET_EXHAUSTED"]
    assert result["payload"] is None and state["sent"] == []
    assert list(tmp_path.iterdir()) == []


def test_reentrant_sender_is_rejected_before_second_reservation(tmp_path):
    holder = {}
    def handle(req, state, clock):
        with pytest.raises(journal.RecoveryProviderJournalError, match="CONCURRENT_REQUEST_NOT_SUPPORTED"):
            call(holder["runner"], holder["payloads"], 1)
        return response()
    runner, payloads, state, _ = case(tmp_path, handle)
    holder.update(runner=runner, payloads=payloads)
    assert call(runner, payloads)["status"] == "SUCCESS"
    assert len(state["sent"]) == 1 and runner.journal.snapshot()["budget"]["reservations_consumed"] == 1


def test_different_runner_cannot_send_while_reserved_request_is_active(tmp_path):
    def handle(req, state, clock):
        contender, payloads, _, _ = case(tmp_path, state=state, clock=clock)
        denied = call(contender, payloads, 1)
        assert denied["status"] == "INCOMPLETE" and denied["reason_codes"] == ["INCOMPLETE_DISPATCH"]
        return response()
    runner, payloads, state, _ = case(tmp_path, handle)
    assert call(runner, payloads)["status"] == "SUCCESS"
    assert len(state["sent"]) == 1
