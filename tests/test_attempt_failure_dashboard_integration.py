"""실제 core 실패 producer→MonitorState→ingest/attach/runner 연결. 외부 실행 없음."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import time
from types import SimpleNamespace
import urllib.request

import pytest

from llm_batch.runtime.attempt_failure import record_attempt_failure
from llm_batch.monitor.event_bus import MonitorState
from llm_batch.monitor import server
from tools import attach_manifest_dashboard as attach
from tools import run_independent_plan as runner


def put(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture(autouse=True)
def no_external(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("실패 연결 시험은 API 함수만 직접 호출하며 네트워크/child를 실행하지 않는다")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(urllib.request, "urlopen", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)


@pytest.fixture
def connection(tmp_path, monkeypatch):
    output = tmp_path / "before.json"
    manifest = tmp_path / "before_manifest.json"
    run_id, scope = "20260101_010203_000001", "a" * 64
    start = time.time() - 1
    initial = {"run_id": run_id, "publication_scope_id": scope,
        "output_file": str(output.resolve()), "input_post_count": 3,
        "completed_count": 0, "flushed_count": 0, "pending_count": 0, "failed_count": 0,
        "effective_parallel": 3, "parallel_count": 3,
        "terminal_artifacts_finalized": False, "large_run_complete": False}
    put(manifest, initial)
    remote, producer = MonitorState(), MonitorState()
    monkeypatch.setattr(server, "monitor", remote)
    monkeypatch.setattr(server, "_is_standalone_mode", lambda: True)
    monkeypatch.setattr(server, "_ingest_token_ok", lambda request: True)
    sent, acknowledgements = [], []
    def api(items):
        response = server.api_ingest(SimpleNamespace(headers={}), {"items": items})
        assert response.status_code == 200
        return json.loads(response.body)
    def enqueue(item):
        sent.append(deepcopy(item))
        acknowledgements.append(api([item])["accepted"])
    producer.attach_forwarder(SimpleNamespace(enqueue=enqueue))
    producer.emit("batch_start", {"run_id": run_id, "publication_scope_id": scope,
        "output_file": str(output.resolve()), "total": 3, "parallel_count": 3,
        "started_at_epoch": start})
    producer.emit("post_start", {"post_id": 102, "worker_id": 1, "index": 2,
                                  "title": "진행 중인 합성 행"})
    original = RuntimeError("합성 최초 publication 거절")
    state = {"shutdown_status": "NOT_STARTED", "input_index": 2, "post_id": 102}
    def report(status):
        # 실제 helper가 이벤트/진단/manifest를 모두 만든다. synthetic core_notice를 쓰지 않는다.
        record_attempt_failure(state=state, error=original, manifest_path=manifest,
            output_file=output, run_id=run_id, publication_scope_id=scope,
            input_sha256="b" * 64, total=3, flushed=0, pending=0, failed=1,
            parallel_count=3, started_at_epoch=start, shutdown_status=status,
            attempt_configuration={"config_hash": "synthetic-full-attempt",
                "run_config_payload": {"decision_call_measurement": {"arm": "BEFORE"}}},
            monitor=producer)
    return SimpleNamespace(output=output, manifest=manifest, run_id=run_id, scope=scope,
        start=start, initial=initial, remote=remote, producer=producer, original=original,
        state=state, report=report, sent=sent, acks=acknowledgements, api=api)


def test_actual_core_draining_drained_ingest_preserves_cause_counts_and_unknown_exit(connection):
    c = connection
    assert c.remote.active_posts
    with pytest.raises(RuntimeError) as caught:
        try:
            raise c.original
        except RuntimeError:
            c.report("DRAINING")
            diagnostic = Path(c.state["failure_ref"]["path"])
            first_bytes = diagnostic.read_bytes()
            assert c.remote.batch_failure["shutdown_status"] == "DRAINING"
            assert c.remote.batch_failure["process_exited"] is False
            c.report("DRAINED")
            raise
    assert caught.value is c.original
    assert c.acks == [1, 1, 1, 1]
    assert diagnostic.read_bytes() == first_bytes
    data = json.loads(first_bytes)
    assert data["error_type"] == "RuntimeError" and data["error_message"] == str(c.original)
    assert str(c.original) in data["traceback"]
    assert digest(diagnostic) == c.state["failure_ref"]["sha256"]
    stored = json.loads(c.manifest.read_bytes())
    assert stored["failed_count"] == 1 and stored["completed_count"] == 0
    assert stored["terminal_artifacts_finalized"] is False and stored["large_run_complete"] is False
    assert c.remote.batch_status == "FAILED" and c.remote.batch_running is False
    assert not c.remote.active_posts
    assert c.remote.batch_failure["shutdown_status"] == "DRAINED"
    assert c.remote.batch_failure["exit_code"] is None
    assert c.remote.batch_failure["invocation_exit_code"] is None
    assert c.remote.batch_failure["process_exited"] is False
    assert not c.output.exists() and not list(c.output.parent.glob("*checkpoint*"))


def test_constructor_failure_prepare_replaces_completed_standalone_run(connection):
    c = connection
    # standalone에는 이전 정상 실행이 남고 새 producer는 아직 batch_start 전이다.
    c.remote.ingest_event("batch_start", {"run_id": "old-run", "total": 1,
        "output_file": str(c.output.with_name("old.json")), "parallel_count": 1})
    c.remote.ingest_event("post_start", {"post_id": 50, "index": 1})
    c.remote.ingest_event("post_complete", {"post_id": 50, "is_relevant": False})
    c.remote.ingest_event("batch_complete", {})
    producer = MonitorState()
    producer.attach_forwarder(SimpleNamespace(enqueue=lambda item: c.api([item])))
    producer.emit("batch_prepare", {"run_id": c.run_id,
        "publication_scope_id": c.scope, "output_file": str(c.output.resolve()),
        "total": 3, "parallel_count": 3, "started_at_epoch": c.start})
    assert not producer.batch_running and not c.remote.batch_running
    record_attempt_failure(state={}, error=TypeError("synthetic constructor failure"),
        manifest_path=c.manifest, output_file=c.output, run_id=c.run_id,
        publication_scope_id=c.scope, input_sha256="b" * 64, total=3,
        flushed=0, pending=0, failed=0, parallel_count=3,
        started_at_epoch=c.start, shutdown_status="NOT_STARTED",
        attempt_configuration={}, monitor=producer)
    for monitor in (producer, c.remote):
        status = monitor.get_status()
        assert status["run_id"] == c.run_id
        assert status["batch_status"] == "FAILED" and not status["batch_running"]
        assert status["done_count"] == 0 and status["total_posts"] == 3
        assert status["current_post_id"] is None and not monitor.post_summaries
        assert status["batch_failure"]["shutdown_status"] == "NOT_STARTED"
        assert status["batch_failure"]["exit_code"] is None
    wrong = deepcopy(c.remote.batch_failure)
    wrong["run_id"] = "other"
    assert c.remote.ingest_failure(wrong) is False
    assert not c.output.exists()


def test_prestart_binding_cannot_replace_another_active_run_or_same_run_scope(connection):
    c = connection
    before = c.remote.get_status()
    prepare = {"run_id": "different-run", "publication_scope_id": c.scope,
        "output_file": str(c.output.with_name("different.json").resolve()),
        "total": 3, "parallel_count": 3, "started_at_epoch": c.start}
    assert c.remote.ingest_event("batch_prepare", prepare) is False
    for key, value in (("output_file", str(c.output.with_name("different.json").resolve())),
                       ("publication_scope_id", "b" * 64)):
        prepare.update(run_id=c.run_id, output_file=str(c.output.resolve()), publication_scope_id=c.scope)
        prepare[key] = value
        assert c.remote.ingest_event("batch_prepare", prepare) is False
    after = c.remote.get_status()
    for key in ("run_id", "output_file", "batch_running", "batch_status", "done_count", "active_posts"):
        assert after[key] == before[key]
    # 원래 실행의 후속 이벤트가 failure latch에 막히지 않는다.
    assert c.remote.ingest_event("post_complete", {"post_id": 102, "worker_id": 1,
        "is_relevant": False}) is True
    assert c.remote.batch_running and c.remote.batch_failure is None


def test_actual_failed_manifest_attach_snapshot_restores_failure_and_rejects_late_running(connection, monkeypatch):
    c = connection
    old_running = attach._snapshot(c.initial, started_at=c.start, summary_limit=3)
    c.report("DRAINED")
    before = c.manifest.read_bytes()
    # 실제 helper가 쓴 파일을 attach v2가 읽어 snapshot으로 바꾼다.
    snap = attach._snapshot(json.loads(before), started_at=c.start - 3600, summary_limit=3)
    assert snap["batch_running"] is False and snap["batch_status"] == "FAILED"
    assert snap["batch_start_time"] == c.start
    restored = MonitorState()
    monkeypatch.setattr(server, "monitor", restored)
    assert c.api([{"kind": "status_snapshot", "data": snap}])["accepted"] == 1
    assert restored.batch_status == "FAILED" and not restored.batch_running
    assert restored.batch_failure["manifest_counts"]["failed_count"] == 1
    assert restored.batch_failure["receipt_ref"] == c.state["failure_ref"]
    assert restored.batch_failure["process_exited"] is False
    assert c.api([{"kind": "status_snapshot", "data": old_running}])["accepted"] == 0
    assert restored.batch_status == "FAILED" and not restored.active_posts
    assert c.manifest.read_bytes() == before and not c.output.exists()


def test_real_runner_receipt_helper_complements_core_failure_without_rewriting_it(connection, monkeypatch):
    c = connection
    c.report("DRAINED")
    tmp = c.output.parent
    # 별도 tmp의 합성 child 종료 수령증이다. 실제 프로세스를 실행/종료했다고 주장하지 않는다.
    claim = put(tmp / "claim.json", {"run_id": c.run_id, "output_file": str(c.output.resolve())})
    plan = put(tmp / "plan.json", {"planned_runs": [{
        "output_json": str(c.output.resolve()), "manifest_json": str(c.manifest.resolve()),
        "output_attempt_claim_json": str(claim.resolve()),
        "batch_completion_contract": {"planned_run_id": c.run_id}}]})
    receipt = put(tmp / "execution.receipt.json", {
        "receipt_type": "independent_plan_execution_receipt", "gate": "FAILED", "exit_code": 7,
        "plan": str(plan.resolve()), "plan_sha256": digest(plan), "failed_run_index": 1,
        "completed_at": datetime.now(timezone.utc).isoformat(), "completed_runs": 0})
    pins = {p: p.read_bytes() for p in (c.manifest, receipt, plan, claim,
                                       Path(c.state["failure_ref"]["path"]))}
    deliveries = []
    def deliver(url, items, **kwargs):
        deliveries.extend(deepcopy(items))
        return c.api(items)
    monkeypatch.setattr(attach, "_post_items", deliver)
    observation = runner._notify_dashboard_failure(manifest_path=c.manifest,
        receipt_path=receipt, dashboard_url="http://not-called.invalid", started_at_epoch=c.start)
    assert observation["status"] == "ACKNOWLEDGED"
    assert len(deliveries) == 1 and deliveries[0]["type"] == "batch_failed"
    # server는 실제 receipt/plan/manifest/claim을 재판독한다. 최종 상태를 stub하지 않는다.
    assert server._verified_failed_runner_binding(deliveries[0]["data"]) is True
    status = c.remote.get_status()
    assert status["batch_status"] == "FAILED" and status["batch_running"] is False
    assert status["batch_failure"]["failure_origin"] == "RUNNER_RECEIPT"
    assert status["batch_failure"]["exit_code"] == status["batch_failure"]["invocation_exit_code"] == 7
    assert status["batch_failure"]["process_exited"] is True
    assert status["batch_failure"]["manifest_counts"]["failed_count"] == 1
    late_core = next(item for item in reversed(c.sent) if item["type"] == "batch_failed")
    assert c.api([late_core])["accepted"] == 0
    assert c.remote.batch_failure["exit_code"] == 7
    assert all(path.read_bytes() == raw for path, raw in pins.items())
    assert json.loads(c.manifest.read_bytes())["batch_failure"]["process_exited"] is False
    assert not c.output.exists()


def test_actual_core_event_cannot_change_another_scope_with_same_run_and_output(connection, monkeypatch):
    c = connection
    other = MonitorState()
    other.ingest_event("batch_start", {"run_id": c.run_id, "publication_scope_id": "c" * 64,
        "output_file": str(c.output.resolve()), "total": 3, "parallel_count": 3,
        "started_at_epoch": c.start})
    monkeypatch.setattr(server, "monitor", other)
    c.report("DRAINING")
    assert c.sent[-1]["data"]["publication_scope_id"] == c.scope
    assert c.acks[-1] == 0
    assert other.batch_running and other.batch_failure is None
    assert other.publication_scope_id == "c" * 64
    assert c.producer.batch_failure["shutdown_status"] == "DRAINING"
    assert json.loads(c.manifest.read_bytes())["publication_scope_id"] == c.scope
