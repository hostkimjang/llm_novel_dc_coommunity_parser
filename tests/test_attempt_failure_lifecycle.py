"""실제 collector/finally AST와 pure 실패 저장 경로를 함께 검증한다."""
import ast
from concurrent.futures import Future
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
from queue import Queue
import socket
import subprocess
import sys
import threading
import time
from types import SimpleNamespace

import pytest
import expert_main as main
from llm_batch.runtime import attempt_failure as failure
from tests import test_paired_execution_main as harness
from tests.test_paired_execution_main import main_ast
from tests.test_publication_decision_commit import _valid_result, _scope_id


@pytest.fixture(autouse=True)
def no_external(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("실패 lifecycle 시험의 외부 호출/child 금지")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)


def preview(row, reference=None):
    return main._preview_publication_decision(row, publication_scope_id=_scope_id(),
        attempt_run_id="fresh", input_index=1, post_id=101, reference_receipt=reference)


def environment(tmp_path, main_ast, *, fresh=True):
    ref = _valid_result(publish=False)
    reference_receipt = preview(ref)
    out = tmp_path / "before.json"
    monitor_events = []
    state = {"shutdown_status": "NOT_STARTED"}
    ns = dict(vars(main), _attempt_failure_state=state, out_result_path=out,
        result_manifest_path=tmp_path / "before_manifest.json", ts="fresh",
        publication_scope_id=_scope_id(), _input_snapshot_sha256="a" * 64,
        _publication_reference_by_index={1: (ref, reference_receipt)},
        _decision_call_measurement={"fresh_execution_required": fresh},
        _worker_pool=Queue(), _pending_results={}, _pending_commit_receipts={},
        _slang_db_manager=SimpleNamespace(record_result=lambda row: records.append(row)),
        _append_checkpoint=lambda **kwargs: checkpoints.append(kwargs),
        _write_pending_snapshot=lambda: writes.append("pending"),
        _flush_ordered=lambda: writes.append("flush"),
        _shutdown_event=threading.Event(), _config_hash="attempt-local",
        _run_config_payload={"decision_call_measurement": {"arm": "BEFORE"}},
        posts=[SimpleNamespace(post_id=101), SimpleNamespace(post_id=102)], _PARALLEL=2,
        _attempt_started_at_epoch=time.time(), results=[],
        _monitor=SimpleNamespace(emit=lambda name, data: monitor_events.append((name, deepcopy(data)))))
    records, checkpoints, writes, commits = [], [], [], []
    def commit(row, **kwargs):
        commits.append(row)
        return preview(row, reference_receipt if fresh else None), False, row
    ns["_commit_final_result"] = commit
    harness.execute([harness.function(main_ast, "_record_fresh_rejection"),
                     harness.function(main_ast, "_report_attempt_failure")], ns)
    factory = ast.parse("def bind():\n    _failed_count = 0\n    return None").body[0]
    factory.body[-1:] = [deepcopy(harness.function(main_ast, "_collect_done")),
                         ast.parse("return _collect_done, lambda: _failed_count").body[0]]
    harness.execute([factory], ns)
    collect, count = ns["bind"]()
    return SimpleNamespace(ns=ns, collect=collect, count=count, state=state, ref=ref,
        rc=reference_receipt, commits=commits, records=records, checkpoints=checkpoints,
        writes=writes, monitor=monitor_events)


def completed(value=None, error=None):
    f = Future()
    f.set_exception(error) if error is not None else f.set_result(value)
    return f


def changed_row(env):
    row = deepcopy(env.ref)
    row["analysis_result"]["identity"]["reason"] = "원래 reference와 다른 실제 판정"
    return row


def test_fresh_reject_keeps_exact_row_once_and_does_not_accept_later_done(tmp_path, main_ast):
    env = environment(tmp_path, main_ast)
    row = changed_row(env)
    original = deepcopy(row)
    first, later = completed(row), completed(deepcopy(env.ref))
    futures = {first: (1, 101, 0), later: (2, 102, 1)}
    with pytest.raises(main.PublicationCommitError):
        env.collect(futures)
    assert env.count() == 1 and env.ns["_worker_pool"].get_nowait() == 0
    assert list(futures) == [later] and len(env.commits) == 1
    assert not env.records and not env.checkpoints and not env.writes
    assert env.ns["_pending_results"] == {} and row == original
    ref = env.state["rejected_row_ref"]
    raw = Path(ref["path"]).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == ref["sha256"]
    data = json.loads(raw)
    assert data["fresh_result"] == original and data["reference_result"] == env.ref
    assert data["reference_receipt"] == env.rc.to_dict()
    assert data["current_preview"]["decision_id"] != env.rc.decision_id
    assert "stable_result_sha256" in data["receipt_differing_fields"]
    assert data["accepted"] is False and data["post_id"] == 101 and type(data["post_id"]) is int
    canonical = json.dumps(original, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    assert data["fresh_result_canonical_sha256"] == hashlib.sha256(canonical).hexdigest()
    assert not env.ns["out_result_path"].exists()


def test_fresh_worker_exception_is_not_fabricated_error_hold(tmp_path, main_ast):
    env = environment(tmp_path, main_ast)
    original = RuntimeError("provider 원래 실패")
    with pytest.raises(RuntimeError) as caught:
        env.collect({completed(error=original): (1, 101, 0)})
    assert caught.value is original and env.count() == 1
    assert not env.commits and not env.checkpoints and not env.records
    assert env.ns["_worker_pool"].qsize() == 1


@pytest.mark.parametrize("kind", ["worker", "publication"])
def test_normal_error_hold_fallback_is_preserved(tmp_path, main_ast, kind):
    env = environment(tmp_path, main_ast, fresh=False)
    if kind == "publication":
        def reject_once(row, **kwargs):
            env.commits.append(row)
            if len(env.commits) == 1:
                raise main.PublicationCommitError("정상 모드 첫 거절")
            return preview(row), False, row
        env.ns["_commit_final_result"] = reject_once
    f = completed(error=RuntimeError("처리 오류")) if kind == "worker" else completed(deepcopy(env.ref))
    env.collect({f: (1, 101, 0)})
    assert env.count() == 1 and len(env.commits) == (1 if kind == "worker" else 2)
    assert env.checkpoints[0]["publication_commit"].outcome == "ERROR_HOLD"
    assert env.checkpoints[0]["status"] == "failed" and len(env.records) == 1
    assert env.writes == ["pending", "flush"]


def test_rejection_preservation_failure_keeps_exception_and_never_overwrites(tmp_path, main_ast):
    env = environment(tmp_path, main_ast)
    folder = tmp_path / "before_rejected_rows"
    folder.mkdir()
    preserved = folder / "row_000001.json"
    preserved.write_bytes(b"old evidence")
    row = changed_row(env)
    with pytest.raises(main.PublicationCommitError) as caught:
        env.collect({completed(row): (1, 101, 0)})
    assert "no longer matches" in str(caught.value)
    assert any("FileExistsError" in note for note in caught.value.__notes__)
    assert preserved.read_bytes() == b"old evidence" and len(env.commits) == 1


def test_invalid_reference_diagnostic_context_cannot_mask_original_rejection(tmp_path, main_ast):
    env = environment(tmp_path, main_ast)
    env.ns["_publication_reference_by_index"] = {1: {"invalid": "reference"}}
    original = main.PublicationCommitError("invalid reference first")
    env.ns["_record_fresh_rejection"](original, changed_row(env), 1, 101)
    assert any("rejected_row_context" in note for note in original.__notes__)
    assert env.state["post_id"] == 101 and not env.ns["out_result_path"].exists()


def main_failure_blocks(main_ast):
    outer = next(node for node in ast.walk(main_ast) if isinstance(node, ast.Try)
        and any(isinstance(child, ast.Assign) and any(isinstance(target, ast.Attribute)
            and isinstance(target.value, ast.Name) and target.value.id == "sys"
            and target.attr == "stdout" for target in child.targets) for child in node.finalbody))
    inner = next(node for node in ast.walk(main_ast) if isinstance(node, ast.Try)
        and any(isinstance(child, ast.Assign) and any(isinstance(target, ast.Name)
            and target.id == "_parallel_error" for target in child.targets) for child in node.finalbody))
    return outer, inner


@pytest.mark.parametrize("drain_error", [False, True])
def test_actual_fatal_finally_drains_before_close_preserves_original_and_failed_state(
        tmp_path, main_ast, drain_error):
    env = environment(tmp_path, main_ast)
    order = []
    log = io.StringIO()
    original = main.PublicationCommitError("최초 거절")
    class Executor:
        def shutdown(self, *, wait, cancel_futures):
            order.append("drain")
            assert wait is True and cancel_futures is True and not log.closed
            assert env.ns["_shutdown_event"].is_set()
            manifest = json.loads(env.ns["result_manifest_path"].read_text())
            assert manifest["batch_failure"]["shutdown_status"] == "DRAINING"
            if drain_error:
                raise RuntimeError("drain 보조 오류")
    queued = Future()
    env.ns.update(_executor_ref=Executor(), futures={queued: (2, 102, 1)},
        _worker_log_files=[log], _parallel_mode=True, original=original,
        _orig_out=sys.stdout, _orig_err=sys.stderr,
        _dashboard_forwarder=SimpleNamespace(flush_and_stop=lambda **kwargs: order.append("forward_flush")))
    outer, inner = main_failure_blocks(main_ast)
    injected = ast.Try(body=ast.parse("raise original").body, handlers=[], orelse=[],
                       finalbody=deepcopy(inner.finalbody))
    wrapper = ast.Try(body=[injected], handlers=deepcopy(outer.handlers), orelse=[],
                      finalbody=deepcopy(outer.finalbody))
    with pytest.raises(main.PublicationCommitError) as caught:
        harness.execute([wrapper], env.ns)
    assert caught.value is original and queued.cancelled()
    assert log.closed is (not drain_error)
    assert order == ["drain", "forward_flush"]
    assert sys.stdout is env.ns["_orig_out"] and sys.stderr is env.ns["_orig_err"]
    data = json.loads(env.ns["result_manifest_path"].read_text())
    assert data["terminal_status"] == "FAILED" and data["large_run_complete"] is False
    assert data["terminal_artifacts_finalized"] is False and data["completed_count"] == 0
    assert data["batch_failure"]["exit_code"] is None and data["batch_failure"]["process_exited"] is False
    assert data["batch_failure"]["shutdown_status"] == ("CLEANUP_ERROR" if drain_error else "DRAINED")
    assert [name for name, _ in env.monitor] == ["batch_failed", "batch_failed"]
    assert not env.commits and not env.records and not env.checkpoints
    assert not env.ns["out_result_path"].exists()
    if drain_error:
        assert any("drain 보조 오류" in note for note in original.__notes__)
        log.close()


@pytest.mark.parametrize("failure_target", ["manifest", "diagnostic", "monitor"])
def test_secondary_failure_does_not_replace_first_cause(tmp_path, main_ast, failure_target):
    env = environment(tmp_path, main_ast)
    error = RuntimeError("first")
    if failure_target == "manifest":
        env.ns["result_manifest_path"].write_bytes(b"preserved invalid manifest")
    elif failure_target == "diagnostic":
        (tmp_path / "before_failure.json").write_bytes(b"preserved diagnostic")
    else:
        env.ns["_monitor"] = SimpleNamespace(emit=lambda *args: (_ for _ in ()).throw(OSError("monitor")))
    try:
        raise error
    except RuntimeError:
        env.ns["_report_attempt_failure"](error, "NOT_STARTED", env.ns)
    assert env.state["secondary_errors"] and error.__notes__
    if failure_target == "manifest":
        assert env.ns["result_manifest_path"].read_bytes() == b"preserved invalid manifest"
    if failure_target == "diagnostic":
        assert (tmp_path / "before_failure.json").read_bytes() == b"preserved diagnostic"


@pytest.mark.parametrize("field,value", [("run_id", "other"), ("output_file", "other.json"),
                                        ("publication_scope_id", "f" * 64)])
def test_failure_cannot_rewrite_different_run_manifest(tmp_path, main_ast, field, value):
    env = environment(tmp_path, main_ast)
    manifest = {"run_id": "fresh", "publication_scope_id": _scope_id(),
                "output_file": str(env.ns["out_result_path"].resolve())}
    manifest[field] = value
    raw = json.dumps(manifest).encode()
    env.ns["result_manifest_path"].write_bytes(raw)
    env.ns["_report_attempt_failure"](RuntimeError("first"), "NOT_STARTED", env.ns)
    assert env.ns["result_manifest_path"].read_bytes() == raw
    assert any("different run/output/scope" in item for item in env.state["secondary_errors"])


def test_actual_sequential_fresh_commit_handler_preserves_rejected_row(tmp_path, main_ast):
    env = environment(tmp_path, main_ast)
    handlers = [node for node in ast.walk(main_ast) if isinstance(node, ast.ExceptHandler)
        and node.name == "error" and any(isinstance(x, ast.Call) and isinstance(x.func, ast.Name)
            and x.func.id == "_record_fresh_rejection" for x in ast.walk(node))]
    assert len(handlers) == 1
    error = main.PublicationCommitError("sequential rejected")
    env.ns.update(original=error, full_result=changed_row(env), i=1,
                  post=SimpleNamespace(post_id=101), _sequential_failed_count=0)
    wrapper = ast.Try(body=ast.parse("raise original").body, handlers=deepcopy(handlers),
                      orelse=[], finalbody=[])
    with pytest.raises(main.PublicationCommitError) as caught:
        harness.execute([wrapper], env.ns)
    assert caught.value is error and env.ns["_sequential_failed_count"] == 1
    data = json.loads(Path(env.state["rejected_row_ref"]["path"]).read_text())
    assert data["current_preview"] is None and data["fresh_result"] == env.ns["full_result"]


def test_actual_keyboardinterrupt_branch_retains_cancel_collect_order(main_ast):
    _, inner = main_failure_blocks(main_ast)
    handler = next(node for node in inner.handlers if isinstance(node.type, ast.Name)
                   and node.type.id == "KeyboardInterrupt")
    events = []
    ns = dict(vars(main), _cli_progress=lambda _: None, _shutdown_event=threading.Event(),
        futures={SimpleNamespace: None},
        _collect_done=lambda futures: events.append("collect"),
        executor=SimpleNamespace(shutdown=lambda **kw: events.append(("shutdown", kw))))
    # 고정 future 인터페이스, 실제 thread/child/모델은 생성하지 않는다.
    f = type("Queued", (), {"cancel": lambda self: events.append("cancel")})()
    ns["futures"] = {f: None}
    harness.execute(handler.body, ns)
    assert ns["_shutdown_event"].is_set()
    assert events == ["cancel", "collect", ("shutdown", {"wait": True, "cancel_futures": True})]


@pytest.mark.parametrize("exception_type", [KeyboardInterrupt, SystemExit])
@pytest.mark.parametrize("drain_interrupted", [False, True])
def test_second_interrupt_does_not_close_live_worker_logs(tmp_path, main_ast,
                                                         exception_type, drain_interrupted):
    env = environment(tmp_path, main_ast)
    original = exception_type("두 번째 종료 신호")
    log = io.StringIO()
    calls = []
    def shutdown(**kwargs):
        calls.append(kwargs)
        assert not log.closed
        if drain_interrupted:
            raise KeyboardInterrupt("drain 중 재중단")
    queued = Future()
    env.ns.update(original=original, _executor_ref=SimpleNamespace(shutdown=shutdown),
        futures={queued: None}, _worker_log_files=[log], _parallel_mode=True)
    _, inner = main_failure_blocks(main_ast)
    wrapper = ast.Try(body=ast.parse("raise original").body, handlers=[], orelse=[],
                      finalbody=deepcopy(inner.finalbody))
    with pytest.raises(exception_type) as caught:
        harness.execute([wrapper], env.ns)
    assert caught.value is original and queued.cancelled()
    assert calls == [{"wait": True, "cancel_futures": True}]
    assert log.closed is (not drain_interrupted)
    assert env.state["shutdown_status"] == ("CLEANUP_ERROR" if drain_interrupted else "DRAINED")
    assert not env.monitor and not env.commits  # Ctrl+C를 새 publication/실패 결과로 합성하지 않는다.
    if drain_interrupted:
        assert original.__notes__ and not log.closed
        log.close()


def test_failed_manifest_preserves_accepted_counts_without_promoting_finished_workers(tmp_path, main_ast):
    env = environment(tmp_path, main_ast)
    env.ns["posts"].append(SimpleNamespace(post_id=103))
    env.ns.update(results=[deepcopy(env.ref)], _pending_results={2: deepcopy(env.ref)}, _failed_count=1)
    env.ns["_report_attempt_failure"](RuntimeError("third row fatal"), "DRAINED", env.ns)
    manifest = json.loads(env.ns["result_manifest_path"].read_text())
    assert manifest["batch_failure"]["manifest_counts"] == {
        "input_post_count": 3, "completed_count": 2, "flushed_count": 1,
        "pending_count": 1, "failed_count": 1}
    assert manifest["runtime_completion_gate"]["completed_count"] == 1
    assert manifest["runtime_completion_gate"]["terminal_artifacts_finalized"] is False
    assert manifest["runtime_completion_gate"]["status"] == manifest["measurement_gate"]["status"] == "NO_GO"
    assert not env.commits and not env.records and not env.checkpoints


def test_fatal_before_scope_and_executor_does_not_invent_binding(tmp_path, main_ast):
    env = environment(tmp_path, main_ast)
    env.ns.pop("publication_scope_id")
    env.ns["_report_attempt_failure"](RuntimeError("setup failed"), "NOT_STARTED", env.ns)
    manifest = json.loads(env.ns["result_manifest_path"].read_text())
    assert manifest["publication_scope_id"] is None
    assert manifest["batch_failure"]["exit_code"] is None
    assert manifest["batch_failure"]["shutdown_status"] == "NOT_STARTED"
    assert not env.ns["out_result_path"].exists()
