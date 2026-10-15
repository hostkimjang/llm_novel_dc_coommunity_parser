"""main 연결 계약 시험. 실제 전문가 동작은 별도 HTTP 통합 시험에서 검증한다."""
from __future__ import annotations

import ast
import builtins
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import threading
from types import SimpleNamespace

import pytest

import expert_main as main
from tests.test_paired_execution_main import main_ast, execute, function, direct_call
from tests.test_recovery_native_batch import batch_policy
from tests.test_publication_decision_commit import _valid_result


def options(**kwargs):
    return SimpleNamespace(native_recovery=None, **kwargs)


def test_off_does_not_read_policy_or_import_native(monkeypatch):
    original_import = builtins.__import__
    def guarded_import(name, *args, **kwargs):
        assert "recovery_native" not in name
        return original_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", guarded_import)
    monkeypatch.setattr(Path, "read_bytes", lambda *args: pytest.fail("OFF 정책 읽기"))
    assert main._resolve_native_recovery_options(options(), {
        "EXPERT_NATIVE_RECOVERY_POLICY": "missing.json", "EXPERT_NATIVE_RECOVERY_POLICY_SHA256": "wrong"}) is None
    assert main._resolve_native_recovery_options(SimpleNamespace(native_recovery="OFF"), {
        "EXPERT_NATIVE_RECOVERY": "ON"}) is None
    assert main._native_recovery_manifest_fields(None, "result.json") == {}


@pytest.mark.parametrize("argument,environment,code", [
    ({"native_recovery_extra_arguments": ("--native-recovery-typo",)}, {}, "MODE_OR_OPTION"),
    ({"recovery_requested": True}, {}, "ONLY_COMMAND_CONFLICT"),
    ({"no_dashboard": True}, {}, "DASHBOARD_REQUIRED"),
    ({}, {main._MEASUREMENT_EXECUTION_MODE_ENV: "FRESH"}, "MEASUREMENT_CONFLICT"),
    ({}, {main._MEASUREMENT_EARLY_ROUTE_MODE_ENV: "ON"}, "MEASUREMENT_CONFLICT"),
    ({"execution_profile": "paired-measurement"}, {}, "MEASUREMENT_CONFLICT"),
    ({}, {"PIPELINE_MEASUREMENT_PAIR_ID": "old-pair"}, "MEASUREMENT_CONFLICT"),
    ({}, {main._RECOVERY_ACTIVATION_MODE_ENV: "OFF"}, "AUDIT_ONLY_REQUIRED"),
    ({"slang_db": "on"}, {}, "MUTABLE_SLANG_FORBIDDEN"),
    ({}, {"PIPELINE_SLANG_DB": "1"}, "MUTABLE_SLANG_FORBIDDEN"),
])
def test_on_rejects_conflicts_before_policy_read(monkeypatch, argument, environment, code):
    monkeypatch.setattr(Path, "read_bytes", lambda *args: pytest.fail("충돌 이후 정책 읽기"))
    env = {"EXPERT_NATIVE_RECOVERY": "ON", main._RECOVERY_ACTIVATION_MODE_ENV: "AUDIT_ONLY", **environment}
    with pytest.raises(ValueError, match=code):
        main._resolve_native_recovery_options(options(**argument), env)


def test_pinned_policy_and_manifest_independent_copy(tmp_path):
    path = tmp_path / "policy.json"
    policy = batch_policy()
    path.write_text(json.dumps(policy), encoding="utf-8")
    env = {"EXPERT_NATIVE_RECOVERY": "ON", main._RECOVERY_ACTIVATION_MODE_ENV: "AUDIT_ONLY",
        "EXPERT_NATIVE_RECOVERY_POLICY": str(path),
        "EXPERT_NATIVE_RECOVERY_POLICY_SHA256": hashlib.sha256(path.read_bytes()).hexdigest()}
    resolved = main._resolve_native_recovery_options(options(), env)
    metadata = main._native_recovery_manifest_fields(resolved, tmp_path / "result.json")
    assert metadata["native_recovery_policy"] == policy
    assert metadata["native_recovery_application_mode"] == "SEPARATE_RESULT_ONLY"
    metadata["native_recovery_policy"]["native_config"]["model"] = "changed"
    assert resolved["policy"] == policy
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError, match="POLICY_SHA_MISMATCH"):
        main._resolve_native_recovery_options(options(), env)


def test_on_freezes_mutable_measurement_binding():
    frozen = main._decision_call_measurement_config({}, native_recovery_frozen=True)
    assert frozen["mutable_context_mode"] == "FROZEN_OFF"
    assert frozen["central_slang_db_write_allowed"] is False


def test_actual_batch_start_prebinds_current_run_before_recovery_events(tmp_path, main_ast):
    from llm_batch.monitor.event_bus import MonitorState
    node = next(node for node in ast.walk(main_ast) if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "_monitor" and node.func.attr == "emit"
        and node.args and isinstance(node.args[0], ast.Constant) and node.args[0].value == "batch_start")
    monitor = MonitorState()
    policy = batch_policy()
    ns = dict(vars(main))
    ns.update(_monitor=monitor, posts=[object()], INPUT_PATH=tmp_path / "input.jsonl",
        out_result_path=tmp_path / "result.json", _PARALLEL=1, ts="new-run", publication_scope_id="a" * 64,
        _execution_config_snapshot=lambda: {}, _native_recovery_options={"policy": policy},
        _attempt_started_at_epoch=1770000000.0)
    execute([ast.Expr(value=deepcopy(node))], ns)
    event = {"schema_version": "native_recovery_progress_v1", "run_id": "old-run",
        "publication_scope_id": "a" * 64, "policy_sha256": main.early_route_canonical_hash(policy),
        "sequence": 0, "status": "RUNNING", "total": 1, "processed": 0, "completed": 0,
        "not_executed": 0, "incomplete": 0, "aggregate_ref": None}
    monitor.emit("native_recovery_progress", event)
    assert monitor.get_status()["native_recovery"] is None
    monitor.emit("native_recovery_progress", {**event, "run_id": "new-run"})
    assert monitor.get_status()["native_recovery"]["run_id"] == "new-run"


def test_two_workers_reverse_completion_keep_own_capture():
    first_started, second_done = threading.Event(), threading.Event()
    class Pipeline:
        def process_post_with_recovery_context(self, post):
            if post.post_id == 101:
                first_started.set()
                assert second_done.wait(5)
            else:
                assert first_started.wait(5)
                second_done.set()
            return {"post_id": post.post_id}, ("capture", post.post_id)
        def process_post(self, post):
            return {"post_id": post.post_id}
    batch = SimpleNamespace(admitted=lambda index, pid: index <= 2)
    pipeline = Pipeline()
    def process(index):
        return main._process_post_with_optional_native_capture(pipeline,
            SimpleNamespace(post_id=100 + index), input_index=index, batch=batch)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(process, index) for index in (1, 2)]
        assert [future.result() for future in futures] == [
            ({"post_id": 101}, ("capture", 101)), ({"post_id": 102}, ("capture", 102))]
    assert process(3) == ({"post_id": 103}, None)
    assert main._process_post_with_optional_native_capture(pipeline,
        SimpleNamespace(post_id=104), input_index=4, batch=None) == ({"post_id": 104}, None)


def commit_namespace(tmp_path, tree, *, post_ids, input_bytes=b"synthetic-main-contract", batch=None):
    """실제 main commit/AUDIT closure. 사용하지 않는 측정·학습 observer만 OFF다."""
    scope = main.build_publication_scope_descriptor(input_file_sha256=hashlib.sha256(input_bytes).hexdigest(),
        post_ids=post_ids, config_hash="native-main-contract", release_fingerprint="a" * 64)
    registry = main.PublicationCommitRegistry(tmp_path / "publication.jsonl", scope_descriptor=scope, create_new=True)
    key, activation, status, mode = main._initialize_recovery_activation_runtime(
        journal_path=tmp_path / "activation.jsonl", hmac_key_path=tmp_path / "activation.hex",
        publication_scope_id=scope.publication_scope_id, requested_mode="AUDIT_ONLY", fresh_execution_required=False)
    assert status == "READY" and mode == "AUDIT_ONLY"
    namespace = dict(vars(main))
    namespace.update(publication_scope_id=scope.publication_scope_id, publication_commit_registry=registry,
        ts="native-main-synthetic", _publication_reference_by_index={},
        _decision_call_measurement=main._decision_call_measurement_config({}, native_recovery_frozen=True),
        decision_call_ledger_registry=SimpleNamespace(enabled=False),
        _early_route_decision_for_index=lambda index: None,
        _link_decision_call_attempt=lambda **kwargs: None,
        _queue_batch_context_publication_learning=lambda **kwargs: None,
        _native_recovery_batch=batch, recovery_activation_registry=activation,
        _recovery_activation_stats_lock=threading.Lock(),
        _recovery_activation_stats={key: 0 for key in ("append_errors", "proposals_observed", "events_created", "events_replayed")},
        _recovery_activation_errors=[])
    # nonlocal을 유지한 실제 두 closure를 작은 enclosing scope에 묶는다.
    factory = ast.parse('def bind():\n    _recovery_activation_status = "READY"\n    return None').body[0]
    factory.body[-1:] = [deepcopy(function(tree, "_ensure_review_recovery_sidecar")),
                         deepcopy(function(tree, "_commit_final_result")),
                         ast.Return(value=ast.Name(id="_commit_final_result", ctx=ast.Load()))]
    execute([factory], namespace)
    namespace["commit"] = namespace["bind"]()
    return namespace


def process_namespace(namespace, tree, tmp_path):
    """일반 process_one 본문 전체를 연결한다. 사용하지 않는 관측 기능은 OFF다."""
    from llm_batch.ledger.decision_tracing_llm import DecisionTracingLLMClient
    from llm_batch.grounding.source_context_diagnostics import export_source_context_diagnostics
    namespace.update(DecisionTracingLLMClient=DecisionTracingLLMClient,
                     export_source_context_diagnostics=export_source_context_diagnostics)
    execute([node for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
             and node.module == "llm_batch.grounding.candidate_audit"], namespace)
    namespace.update(_paired_session=None, _PARALLEL=1, _print_lock=threading.Lock(), _monitor=None,
        _context_diagnostics_enabled=False, _execution_config_snapshot=lambda: {"profile": "low-load-validation"},
        _decision_call_row_attempt_id=lambda *args: "unused-tracing-off",
        _early_route_run_meta_fields=lambda *args: {}, _decision_call_run_meta_fields=lambda *args: {},
        _runtime_binding_echo_fields=lambda: {}, _record_early_route_execution=lambda **kwargs: None,
        _record_decision_call_closure=lambda **kwargs: None, _reuse_health_filter_meta={}, _run_config_payload={},
        _prompt_version="synthetic", _config_hash="native-main-contract", _parallel_policy_text=lambda: "parallel1",
        _MODEL_PARALLEL_MAX=1, _MODEL_PARALLEL_CAP_APPLIED=False, _PARALLEL_POLICY_MODEL="synthetic-native-model",
        _REQUESTED_PARALLEL=1, _REQUESTED_PARALLEL_RAW=1, LLM_MODE="remote", LOG_DIR=tmp_path,
        log_path=tmp_path / "main.log", _health_attempts=1, _health_checked_endpoint_count=1,
        _health_failures=[], _health_include_search=False, _health_light_mode=True, _health_ok=[{}],
        _health_probe_batch_size=1, _health_probe_stopped_after_required_ok=True, _health_required_ok=1,
        _health_timeout=1, _health_workers=1)
    for name in ("retrieval", "reranker", "calibration", "inference", "semantics"):
        namespace["_candidate_" + name + "_row_fields"] = lambda *args: {}
    namespace["_community_knowledge_row_fields"] = lambda *args: {}
    execute([function(tree, "_process_one")], namespace)
    return namespace


def test_actual_main_commit_reads_canonical_before_capture_and_replay(tmp_path, main_ast):
    accepted, observations = [], []
    def accepted_after_read(index, post_id, capture, **kwargs):
        main.validate_publication_result_commit(kwargs["result"], kwargs["receipt"])
        assert ns["publication_commit_registry"].result(post_id) == kwargs["result"]
        assert observations[-1]["canonical_publication_read"] == "ACTUAL_REGISTRY_RESULT"
        accepted.append((index, post_id, capture, kwargs["created"]))
    batch = SimpleNamespace(accept_committed=accepted_after_read)
    ns = commit_namespace(tmp_path, main_ast, post_ids=[101, 102], batch=batch)
    wrappers = []
    for pid in (101, 102):
        output = SimpleNamespace(_final_source_context_receipt={"trace_observation": observations.append})
        wrappers.append(main._FinalSourceContextResult(_valid_result(post_id=pid), output=output,
            verifier=lambda *args, **kwargs: {"stage": kwargs["stage"]}, native_capture=("capture", pid)))
    receipts = {}
    for index in (2, 1):
        receipt, created, canonical = ns["commit"](wrappers[index-1], global_idx=index, post_id=100 + index)
        receipts[index] = (canonical, receipt)
        assert created and canonical["run_meta"]["semantic_review_router_receipt"]
        assert wrappers[index-1].take_native_capture() is None
    assert accepted == [(2, 102, ("capture", 102), True), (1, 101, ("capture", 101), True)]
    # 실제 main은 재생 행을 commit 함수에 다시 넣지 않고 constructor 직후 직접 알린다.
    replay = next(node for node in ast.walk(main_ast) if isinstance(node, ast.For)
        and isinstance(node.target, ast.Tuple) and any(isinstance(child, ast.Name)
            and child.id == "_native_replay_index" for child in ast.walk(node.target)))
    ns["_publication_replay_by_index"] = {1: receipts[1]}
    execute([replay], ns)
    assert accepted[-1] == (1, 101, None, False)


def terminal_segment(tree):
    target = [node for node in ast.walk(tree) if isinstance(node, ast.If)
        and any(direct_call(child, "_paired_session", "finish") for child in node.body)]
    assert len(target) == 1
    siblings = next(value for node in ast.walk(tree) for _, value in ast.iter_fields(node)
        if isinstance(value, list) and target[0] in value)
    index = siblings.index(target[0])
    segment = siblings[index:index + 4]
    assert any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
        and n.func.attr == "drain" for n in ast.walk(segment[-1]))
    return segment


@pytest.mark.parametrize("parallel", [1, 2])
def test_actual_terminal_manifest_precedes_drain_and_preserves_bytes(tmp_path, main_ast, parallel):
    output, manifest, wal, scope, audit = [tmp_path / name for name in
        ("result.json", "manifest.json", "publication.jsonl", "scope.json", "activation.jsonl")]
    for path in (output, wal, scope, audit): path.write_bytes(b"[]")
    protected = {path: path.read_bytes() for path in (output, wal, scope, audit)}
    seen = []
    ns = dict(vars(main))
    def write(path, value):
        assert ns["_terminal_artifacts_finalized"]
        path.write_text(json.dumps(value), encoding="utf-8")
        seen.append("manifest")
    def drain(**kwargs):
        assert seen == ["manifest"] and json.loads(manifest.read_bytes())["terminal_artifacts_finalized"]
        assert all(path.read_bytes() == data for path, data in protected.items())
        seen.append("drain")
        return {"status": "COMPLETED"}
    ns.update(ts="native-terminal-synthetic", _paired_session=None, _terminal_artifacts_finalized=False, _PARALLEL=parallel,
        result_manifest_path=manifest, out_result_path=output,
        checkpoint_jsonl_path=tmp_path / "checkpoint.jsonl", pending_snapshot_path=tmp_path / "pending.json",
        results=[], _sequential_failed_count=0, _parallel_manifest_fields=lambda: {},
        _completion_manifest_gate_fields=lambda **kwargs: {"terminal_artifacts_finalized": True},
        _atomic_write_json=write, _write_manifest=lambda: write(manifest, {"terminal_artifacts_finalized": True}),
        _native_recovery_batch=SimpleNamespace(drain=drain), publication_commit_journal_path=wal,
        publication_commit_registry=SimpleNamespace(scope_descriptor_path=scope), recovery_activation_journal_path=audit)
    execute(terminal_segment(main_ast), ns)
    assert seen == ["manifest", "drain"]
