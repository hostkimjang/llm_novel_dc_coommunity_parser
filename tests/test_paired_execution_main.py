"""실제 main 연결부를 AST로 실행하는 합성 계약 시험. 모델·서비스 실행 없음.

행 처리 함수는 본문 전체를 실행한다. 최종 manifest 시험은 관계없는 공개
메타데이터를 제외한 실제 paired 필드 표현식과 실제 종료/저장 분기를 실행한다.
전체 CLI main이나 실제 provider 실행을 검증했다고 주장하지 않는다.
"""
from __future__ import annotations

import ast
from collections.abc import Mapping
import copy
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
from types import SimpleNamespace

import pytest
import httpx

import expert_main
from llm_batch.ledger.decision_call_events import DecisionCallLedgerRegistry
from llm_batch.ledger.decision_tracing_llm import DecisionTracingLLMClient
from llm_batch.llm.client import LLMClient
from llm_batch.measurement import paired_execution_policy as policy
from llm_batch.runtime import execution_config, paired_execution
from tests import test_paired_measurement_low_load as low_fixture
from tests import test_paired_measurement_readback as legacy_fixture
from tests.test_expert_main_early_route_measurement import _post, _required_env
from tests.test_paired_execution_policy import fixture as policy_fixture
from tests.test_publication_decision_commit import _valid_result
from tools import run_independent_plan as runner


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "expert_main.py"


@pytest.fixture(autouse=True)
def no_external_execution(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("main 연결 시험에서 외부 호출/child 실행 금지")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)


@pytest.fixture(scope="module")
def main_ast():
    return next(node for node in ast.parse(SOURCE.read_text(encoding="utf-8")).body
                if isinstance(node, ast.FunctionDef) and node.name == "main")


def function(tree, name):
    found = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == name]
    assert len(found) == 1, f"실제 main 함수 경계 변경: {name}"
    return found[0]


def execute(nodes, namespace):
    module = ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")],
                                            level=0), *copy.deepcopy(nodes)], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), str(SOURCE), "exec"), namespace)


def direct_call(node, object_name, method):
    return (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Attribute)
            and isinstance(node.value.func.value, ast.Name)
            and node.value.func.value.id == object_name and node.value.func.attr == method)


def setup_block(tree):
    found = [node for node in ast.walk(tree) if isinstance(node, ast.If)
             and any(direct_call(child, "_paired_session", "start") for child in node.body)]
    assert len(found) == 1
    return found[0]


def preflight_block(tree):
    found = [node for node in tree.body if isinstance(node, ast.If)
             and any(isinstance(child, ast.ImportFrom) and child.module == "llm_batch.runtime.paired_execution"
                     for child in node.body)]
    assert len(found) == 1
    return found[0]


def required_for_spec(spec_path, arm="BEFORE"):
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    return {**_required_env(arm=arm),
            "PIPELINE_MEASUREMENT_RUN_SPEC_PATH": str(spec_path),
            "PIPELINE_MEASUREMENT_RUN_SPEC_FILE_SHA256": hashlib.sha256(spec_path.read_bytes()).hexdigest(),
            "PIPELINE_MEASUREMENT_RUN_SPEC_SHA256": spec["run_spec_sha256"],
            "PIPELINE_MEASUREMENT_PAIR_ID": spec["pair_id"]}


@pytest.mark.parametrize("arm", ["BEFORE", "AFTER"])
def test_v3_real_measurement_config_keeps_policy_and_file_bindings(tmp_path, arm):
    _, _, _, spec_path, low = low_fixture.PairedMeasurementLowLoadTests()._fixture(tmp_path)
    config = expert_main._decision_call_measurement_config(required_for_spec(spec_path, arm))
    assert config["execution_policy_binding"] == low["policy_binding"]
    assert config["run_spec_file_binding"]["arm"] == arm
    assert config["run_spec_file_binding"]["file_sha256"] == hashlib.sha256(spec_path.read_bytes()).hexdigest()
    assert config["early_route_enabled"] is (arm == "AFTER")
    assert config["central_slang_db_write_allowed"] is False
    assert "execution_policy" not in config


@pytest.mark.parametrize("target", ["policy_bytes", "spec_bytes", "pair", "self_sha", "file_sha"])
def test_v3_prebound_tamper_rejected_before_provider(tmp_path, target):
    _, _, _, spec_path, low = low_fixture.PairedMeasurementLowLoadTests()._fixture(tmp_path)
    environment = required_for_spec(spec_path)
    if target in {"policy_bytes", "spec_bytes"}:
        path = Path(low["policy_binding"]["path"]) if target == "policy_bytes" else spec_path
        path.write_bytes(path.read_bytes() + b" ")
    else:
        key, value = {"pair": ("PAIR_ID", "wrong-pair"), "self_sha": ("RUN_SPEC_SHA256", "0" * 64),
                      "file_sha": ("RUN_SPEC_FILE_SHA256", "0" * 64)}[target]
        environment["PIPELINE_MEASUREMENT_" + key] = value
    with pytest.raises(ValueError):
        expert_main._decision_call_measurement_config(environment)


def test_v2_prebound_and_v1_hash_only_keep_legacy_behavior(tmp_path):
    before, _, _, spec_path = legacy_fixture.PairedMeasurementReadbackTests()._fixture(tmp_path)
    config = expert_main._decision_call_measurement_config(required_for_spec(spec_path))
    assert "execution_policy_binding" not in config
    assert config["run_spec_file_binding"]["arm"] == "BEFORE"
    source = json.loads(before.read_text(encoding="utf-8"))
    source["publication_slang_db_input_sha256"] = legacy_fixture.SLANG_INPUT_SHA
    source.pop("publication_slang_db_input_binding")
    before.write_text(json.dumps(source), encoding="utf-8")
    reader = low_fixture.reader
    legacy = reader.build_paired_measurement_run_spec(input_path=legacy_fixture._claimed_input_path(before),
        source_manifest_path=before, pair_id=legacy_fixture.PAIR_ID,
        run_spec_schema_version=reader.LEGACY_RUN_SPEC_SCHEMA_VERSION)
    legacy_path = tmp_path / "legacy-v1.json"
    legacy_path.write_text(json.dumps(legacy), encoding="utf-8")
    environment = required_for_spec(legacy_path)
    with pytest.raises(ValueError):
        expert_main._decision_call_measurement_config(environment)
    environment.pop("PIPELINE_MEASUREMENT_RUN_SPEC_PATH")
    environment.pop("PIPELINE_MEASUREMENT_RUN_SPEC_FILE_SHA256")
    config = expert_main._decision_call_measurement_config(environment)
    assert config["run_spec_sha256"] == legacy["run_spec_sha256"]
    assert "execution_policy_binding" not in config and "run_spec_file_binding" not in config


@pytest.fixture
def connected(tmp_path, monkeypatch, main_ast, request):
    config, fields, frozen, binding = policy_fixture()
    scope = expert_main.build_publication_scope_descriptor(input_file_sha256=binding["input_sha256"],
        post_ids=[101], config_hash="synthetic-main-contract", release_fingerprint="a" * 64)
    reference = policy.write_execution_policy(frozen, tmp_path / "policy.json")
    arm = "AFTER" if getattr(request.node, "callspec", SimpleNamespace(params={})).params.get("early") else "BEFORE"
    measurement = expert_main._decision_call_measurement_config(_required_env(arm=arm))
    measurement.update(pair_id=binding["pair_id"], execution_policy_binding={key: reference[key]
                       for key in ("path", "file_sha256", "policy_sha256")})
    events, closures = [], []
    resources = {**frozen["resources"], "pid": os.getpid(), "status": "OBSERVED"}
    resources.pop("platform")
    monkeypatch.setattr(execution_config, "observe_process_resources", lambda _: copy.deepcopy(resources))
    monkeypatch.setattr(LLMClient, "__init__", lambda self, *args, **kwargs:
                        self.__dict__.update(model=fields["llm_model"], endpoint=fields["llm_endpoint"]))
    ledger = DecisionCallLedgerRegistry(tmp_path / "ledger", scope_descriptor=scope, create_new=True,
        enabled=True, run_spec_sha256=measurement["run_spec_sha256"], pair_id=measurement["pair_id"],
        arm=arm, fresh_execution_mode=True)

    class Session(paired_execution.PairedExecutionSession):
        def start(self):
            result = super().start()
            events.append("RUN_START")
            return result

        def start_row(self, **kwargs):
            result = super().start_row(**kwargs)
            events.append("ROW_START")
            return result

        def finish_row(self, **kwargs):
            result = super().finish_row(**kwargs)
            events.append("ROW_END")
            return result

    class Trace(DecisionTracingLLMClient):
        def begin_row_attempt(self, *args):
            events.append("LEDGER_BEGIN")
            return super().begin_row_attempt(*args)

        def seal_row_attempt(self):
            result = super().seal_row_attempt()
            events.append("LEDGER_SEAL")
            return result

    class MCP:
        endpoint_failover = False

        def __init__(self, **kwargs):
            pass

        def health_check(self, **kwargs):
            events.append("SYNTHETIC_HEALTH")
            assert kwargs["include_search"] is True
            return {"ok": True, "search_skipped": False}

    class Pipeline:
        def __init__(self, **kwargs):
            assert "RUN_START" in events
            events.append("WORKER_CREATED")
            self.llm = kwargs["llm"]
            self.orchestrator = SimpleNamespace(_last_ctx=None)

        def process_post(self, post):
            assert events.index("ROW_START") < events.index("LEDGER_BEGIN")
            assert self.llm._active_row.input_index == 1
            assert self.llm._active_row.post_id == post.post_id
            events.append("SYNTHETIC_PROCESS")
            return SimpleNamespace(
                model_dump=lambda: {"analysis": {}},
                _final_source_context_receipt={"trace_observation": lambda observation: None})

        def verify_final_source_context_serialization(self, *args, **kwargs):
            return {}

        def _trace_final_source_observation(self, *args):
            pass

    namespace = dict(vars(expert_main))
    namespace.update(os=SimpleNamespace(environ={}, getenv=lambda key, default=None: default), sys=sys,
        time=time, datetime=datetime, threading=threading, copy=copy, Mapping=Mapping,
        _paired_policy=frozen, _paired_session=None, _paired_clients=[], _paired_mcp_clients=[],
        _native_recovery_options=None, _native_recovery_batch=None,
        _decision_call_measurement=measurement, _execution_config_snapshot=lambda: copy.deepcopy(config),
        _publication_config_hash=fields["publication_config_sha256"],
        early_route_canonical_hash=lambda _: fields["publication_decision_environment_sha256"],
        _publication_decision_environment=lambda _: {}, generation_fingerprint=lambda *args: fields["generation_config_sha256"],
        prompt_fingerprint=lambda _: fields["prompt_sha256"], endpoint_pool_fingerprint=policy.endpoint_pool_fingerprint,
        _get_mcp_endpoint_pool=lambda: ["http://127.0.0.1:2/mcp"],
        _env_bool_runtime=lambda key, default=False: key == "MCP_HEALTH_INCLUDE_SEARCH",
        _mcp_goal_run_light_health_mode=lambda: False, _default_mcp_health_include_search=lambda: True,
        _mcp_health_required_ok_count=lambda pool: 1, _mcp_health_probe_batch_size=lambda *args, **kwargs: 1,
        _allow_local_shard_auto_up=lambda: False, _allow_local_shard_recreate=lambda: False,
        _allow_missing_shard_auto_scale_up=lambda: False,
        _CLI_ARGS=SimpleNamespace(reuse_shards_only=True, candidate_retrieval="OFF", candidate_corpus=None),
        _batch_context=SimpleNamespace(enabled=False), _slang_db_enabled=False, _scope_slang_db_sha256=None,
        _community_knowledge_settings={"mode": "OFF"}, _candidate_reranker_settings={"mode": "OFF"},
        _candidate_retrieval_observer=None, _candidate_reranker=None, _community_knowledge_snapshot=None,
        _candidate_calibration=None, _candidate_inference=None, _candidate_semantics=None,
        _candidate_calibration_settings={"mode": "OFF"}, _candidate_inference_settings={"mode": "OFF"},
        _candidate_semantics_settings={"mode": "OFF"},
        _candidate_calibration_policy_fields=lambda: {}, _candidate_inference_policy_fields=lambda: {},
        _candidate_semantics_policy_fields=lambda: {},
        candidate_calibration_policy_fields=lambda *args: {}, candidate_inference_policy_fields=lambda *args: {},
        candidate_semantics_policy_fields=lambda *args: {},
        _input_snapshot_sha256=scope.input_file_sha256, publication_scope_id=scope.publication_scope_id,
        ts=binding["run_id"], repo_root=ROOT, _PARALLEL=1, _REQUESTED_PARALLEL_RAW=1, _REQUESTED_PARALLEL=1,
        _NO_DASHBOARD=False, _execution_settings={"profile": "low-load-validation"},
        _health_workers=1, _health_probe_batch_size=1, _health_required_ok=1, _health_include_search=True,
        _health_light_mode=False, _health_timeout=1, _health_checked_endpoint_count=1, _health_attempts=1,
        _health_probe_stopped_after_required_ok=True, _health_ok=[{}], _health_failures=[],
        PairedExecutionSession=Session, FreshHealthProbe=paired_execution.FreshHealthProbe,
        LLMClient=LLMClient, DecisionTracingLLMClient=Trace, MCPClient=MCP, AgenticPipeline=Pipeline,
        decision_call_ledger_registry=ledger, _mcp_endpoint_pool=["http://127.0.0.1:2/mcp"],
        OUT_DIR=tmp_path, LOG_DIR=tmp_path, log_path=tmp_path / "not-created.log",
        _recent_post_index=None, _negative_detail_retry_coordinator=object(),
        _print_lock=threading.Lock(), _monitor=None, _context_diagnostics_enabled=False,
        export_source_context_diagnostics=lambda *args, **kwargs: {"status": "OFF"},
        _publication_reference_by_index={}, _record_early_route_execution=lambda **kwargs: None,
        _record_decision_call_closure=lambda **kwargs: closures.append(kwargs),
        _candidate_retrieval_row_fields=lambda *args: {}, _candidate_reranker_row_fields=lambda *args: {},
        _candidate_calibration_row_fields=lambda *args: {}, _candidate_inference_row_fields=lambda *args: {},
        _candidate_semantics_row_fields=lambda *args: {},
        _community_knowledge_row_fields=lambda *args: {}, _early_route_run_meta_fields=lambda *args: {},
        _decision_call_run_meta_fields=lambda *args: {}, _runtime_binding_echo_fields=lambda: {},
        LLM_MODE="remote", _prompt_version="synthetic", _config_hash="synthetic", _MODEL_PARALLEL_MAX=1,
        _MODEL_PARALLEL_CAP_APPLIED=False, _PARALLEL_POLICY_MODEL=fields["llm_model"],
        _parallel_policy_text=lambda: "synthetic", _run_config_payload={}, _reuse_health_filter_meta={})
    execute([function(main_ast, name) for name in ("_create_pipeline", "_decision_call_row_attempt_id", "_process_one")], namespace)
    return SimpleNamespace(ns=namespace, events=events, closures=closures, config=config, fields=fields,
                           policy=frozen, reference=reference, resources=resources, mcp=MCP, ledger=ledger)


def start(connected, main_ast):
    execute([setup_block(main_ast)], connected.ns)
    return connected.ns["_paired_session"]


@pytest.mark.parametrize("early", [False, True])
def test_actual_process_one_keeps_row_attempt_and_normal_or_early_end(connected, main_ast, early):
    ns = connected.ns
    if early:
        source = _valid_result(post_id=101)
        source.setdefault("run_meta", {}).update(paired_execution_observation={"old": True},
                                                paired_execution_runtime_fields={"old": True})
        ns["_fresh_execution_authoritative_reference_for_row"] = lambda *args, **kwargs: (copy.deepcopy(source), None)
    session = start(connected, main_ast)
    pipeline = ns["_create_pipeline"]()
    post = _post(author="합성", url="https://example.invalid/101", created_at="2026-10-10")
    result = ns["_process_one"](post, 1, 1, pipeline, 0)
    row = connected.closures[0]["row"]
    bundle = result["run_meta"]["paired_execution_observation"]
    assert bundle["input_index"] == row.input_index == 1
    assert bundle["post_id"] == row.post_id == 101
    assert bundle["start"]["binding"]["attempt_id"] == bundle["end"]["binding"]["attempt_id"] == row.row_attempt_id
    assert bundle["start"]["binding"]["run_id"] == row.attempt_run_id == ns["ts"]
    assert bundle["start"]["binding"]["publication_scope_id"] == row.publication_scope_id
    assert connected.events.index("RUN_START") < connected.events.index("WORKER_CREATED")
    assert connected.events.index("ROW_START") < connected.events.index("LEDGER_BEGIN")
    assert connected.events.index("LEDGER_SEAL") < connected.events.index("ROW_END")
    assert ("SYNTHETIC_PROCESS" in connected.events) is not early
    assert "old" not in bundle
    assert result["run_meta"]["paired_execution_runtime_fields"] == connected.fields
    session.finish()
    assert session.manifest_fields()["paired_execution_observation"]["end"]["phase"] == "END"


def test_row_exception_aborts_ledger_and_cannot_fabricate_run_end(connected, main_ast):
    session = start(connected, main_ast)
    pipeline = connected.ns["_create_pipeline"]()
    pipeline.process_post = lambda post: (_ for _ in ()).throw(RuntimeError("synthetic row failure"))
    with pytest.raises(RuntimeError, match="synthetic row failure"):
        connected.ns["_process_one"](_post(author="합성", url="", created_at=""), 1, 1, pipeline, 0)
    assert len(connected.closures) == 1
    assert "ROW_END" not in connected.events and "LEDGER_SEAL" not in connected.events
    with pytest.raises(ValueError, match="rows unfinished"):
        session.finish()
    assert session.manifest_fields()["paired_execution_observation"]["end"] is None


@pytest.mark.parametrize("boundary", ["preflight", "health_client", "worker_client", "runtime_environment"])
def test_actual_main_failover_boundaries_reject_before_dispatch(connected, main_ast, boundary):
    ns = connected.ns
    if boundary == "preflight":
        ns["_env_bool_runtime"] = lambda *args, **kwargs: True
        with pytest.raises(ValueError, match="정책 불일치"):
            execute([preflight_block(main_ast)], ns)
        assert connected.events == []
        return
    if boundary == "health_client":
        connected.mcp.endpoint_failover = True
        with pytest.raises(ValueError, match="failover"):
            start(connected, main_ast)
        assert "SYNTHETIC_HEALTH" not in connected.events and "RUN_START" not in connected.events
        return
    start(connected, main_ast)
    if boundary == "worker_client":
        connected.mcp.endpoint_failover = True
        with pytest.raises(ValueError, match="failover"):
            ns["_create_pipeline"]()
        assert "WORKER_CREATED" not in connected.events
    else:
        ns["_env_bool_runtime"] = lambda *args, **kwargs: True
        with pytest.raises(ValueError, match="failover"):
            ns["_paired_runtime_fields"]()


def test_generated_argv_matches_actual_main_reuse_only_gate(connected, main_ast):
    ns = connected.ns
    argv = runner._low_load_command_argv(python_path=sys.executable, input_path="synthetic.jsonl",
        output_path="new-output.json", policy=connected.policy, environment={})
    ns["_CLI_ARGS"] = expert_main._build_arg_parser(add_help=False).parse_args(argv[3:])
    assert ns["_CLI_ARGS"].reuse_shards_only is True
    execute([preflight_block(main_ast)], ns)
    assert ns["_paired_policy"] == connected.policy
    assert connected.events == []


@pytest.mark.parametrize("monitor,mode", [(None, "embedded"), (object(), "unavailable"), (object(), "disabled")])
def test_actual_execution_snapshot_rejects_unavailable_dashboard(connected, main_ast, monitor, mode):
    ns = connected.ns
    ns.update(_monitor=monitor, _dashboard_mode=mode)
    execute([function(main_ast, "_execution_config_snapshot")], ns)
    with pytest.raises(ValueError, match="대시보드"):
        ns["_execution_config_snapshot"]()
    assert connected.events == []


def test_actual_execution_snapshot_refreshes_paired_settings_and_source(connected, main_ast, tmp_path):
    ns = connected.ns
    reads, dashboard_checks = [], []
    ns["_CLI_ARGS"].__dict__.update(execution_profile="low-load-validation", parallel=1,
        parallel_explicit=True, decision_call_ledger="REQUIRED", vlm="on", ocr="on", context_diagnostics="off")
    ns.update(_monitor=object(), _dashboard_mode="embedded", _dashboard_url="http://localhost:9999",
        _require_paired_dashboard_ready=lambda url, mode: dashboard_checks.append((url, mode)),
        build_execution_config=execution_config.build_execution_config,
        resolve_execution_settings=execution_config.resolve_execution_settings,
        source_snapshot=lambda path: reads.append(path) or copy.deepcopy(connected.config["source"]),
        _execution_resources=connected.resources, out_result_path=tmp_path / "never-written.json",
        image_post_count=0, vlm_ocr_semantic_review_ready=True, vlm_ocr_semantic_review_skip_reason_codes=[],
        candidate_retrieval_policy_fields=lambda *args, **kwargs: {},
        candidate_reranker_policy_fields=lambda *args: {}, community_knowledge_policy_fields=lambda *args: {})
    execute([function(main_ast, "_execution_config_snapshot")], ns)
    first = ns["_execution_config_snapshot"]()
    assert first["dashboard"]["enabled"] is True and first["dashboard"]["mode"] == "embedded"
    assert first["settings"]["ocr"]["value"] is True
    ns["_CLI_ARGS"].ocr = "off"
    second = ns["_execution_config_snapshot"]()
    assert second["settings"]["ocr"]["value"] is False and len(reads) == 2
    assert dashboard_checks == [("http://localhost:9999", "embedded")] * 2
    assert all(path == SOURCE for path in reads)


@pytest.mark.parametrize("mode", ["embedded", "standalone_forward"])
def test_dashboard_ready_accepts_only_bound_health_and_forward_ack(monkeypatch, mode):
    calls = []
    payload = {"service": "expert-pipeline-monitor", "ok": True,
               "standalone": mode == "standalone_forward", "pid": os.getpid()}
    monkeypatch.setenv("DASHBOARD_INGEST_TOKEN", "synthetic-token")

    def get(url, **kwargs):
        calls.append(("GET", url, kwargs))
        return httpx.Response(200, json=payload, request=httpx.Request("GET", url))

    def post(url, **kwargs):
        calls.append(("POST", url, kwargs))
        assert kwargs["json"] == {"items": []}
        assert kwargs["headers"] == {"X-Ingest-Token": "synthetic-token"}
        return httpx.Response(200, json={"ok": True, "accepted": 0}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "get", get)
    monkeypatch.setattr(httpx, "post", post)
    monkeypatch.setattr(expert_main.time, "sleep", lambda _: pytest.fail("정상 준비 상태가 재시도됨"))
    expert_main._require_paired_dashboard_ready("http://127.0.0.1:9999", mode)
    assert [call[0] for call in calls] == (["GET"] if mode == "embedded" else ["GET", "POST"])
    assert all(call[2]["timeout"].connect <= .2 and call[2]["timeout"].read <= .5 for call in calls)


@pytest.mark.parametrize("failure", ["dead_listener", "wrong_pid", "wrong_service", "wrong_standalone",
                                     "forward_403", "forward_bad_ack", "forward_bool_ack"])
def test_dashboard_ready_rejects_unreachable_or_unbound_server_with_bounded_retry(monkeypatch, failure):
    calls, sleeps = [], []
    forward = failure.startswith("forward")
    mode = "standalone_forward" if forward else "embedded"
    payload = {"service": "expert-pipeline-monitor", "ok": True, "standalone": forward, "pid": os.getpid()}
    if failure == "wrong_pid":
        payload["pid"] += 1
    elif failure == "wrong_service":
        payload["service"] = "unrelated-local-service"
    elif failure == "wrong_standalone":
        payload["standalone"] = True

    def get(url, **kwargs):
        calls.append("GET")
        if failure == "dead_listener":
            raise httpx.ConnectError("synthetic dead listener")
        return httpx.Response(200, json=payload, request=httpx.Request("GET", url))

    def post(url, **kwargs):
        calls.append("POST")
        return httpx.Response(403 if failure == "forward_403" else 200,
            json={"ok": True, "accepted": False if failure == "forward_bool_ack" else 1},
            request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "get", get)
    monkeypatch.setattr(httpx, "post", post)
    monkeypatch.setattr(expert_main.time, "sleep", sleeps.append)
    with pytest.raises(ValueError, match="handshake failed"):
        expert_main._require_paired_dashboard_ready("http://127.0.0.1:9999", mode)
    assert calls.count("GET") == 5 and calls.count("POST") == (5 if forward else 0)
    assert sleeps == [.1] * 4


@pytest.mark.parametrize("url", ["https://localhost:9999", "http://example.invalid:9999"])
def test_dashboard_ready_rejects_nonlocal_or_wrong_protocol_before_http(monkeypatch, url):
    monkeypatch.setattr(httpx, "get", lambda *args, **kwargs: pytest.fail("HTTP 호출 전 거절해야 함"))
    with pytest.raises(ValueError, match="local monitor"):
        expert_main._require_paired_dashboard_ready(url, "embedded")


@pytest.mark.parametrize("bad_end", [False, True])
def test_actual_terminal_branch_stores_run_end_before_finalized_manifest(connected, main_ast, bad_end):
    ns = connected.ns
    session = start(connected, main_ast)
    manifest_function = function(main_ast, "_parallel_manifest_fields")
    returned = next(node.value for node in manifest_function.body if isinstance(node, ast.Return))
    fields = [(key, value) for key, value in zip(returned.keys, returned.values)
              if (isinstance(key, ast.Constant) and key.value == "execution_config")
              or (key is None and any(isinstance(child, ast.Name) and child.id == "_paired_session"
                                      for child in ast.walk(value)))]
    assert len(fields) == 2
    expression = ast.Expression(body=ast.Dict(keys=[key for key, _ in fields], values=[value for _, value in fields]))
    compiled = compile(ast.fix_missing_locations(expression), str(SOURCE), "eval")
    ns["_parallel_manifest_fields"] = lambda: eval(compiled, ns)
    terminal = [node for node in ast.walk(main_ast) if isinstance(node, ast.If)
                and any(direct_call(child, "_paired_session", "finish") for child in node.body)]
    assert len(terminal) == 1
    sibling_groups = [value for node in ast.walk(main_ast) for _, value in ast.iter_fields(node)
                      if isinstance(value, list) and terminal[0] in value]
    assert len(sibling_groups) == 1
    siblings = sibling_groups[0]
    index = siblings.index(terminal[0])
    segment = siblings[index:index + 3]
    assert isinstance(segment[1], ast.Assign) and segment[1].targets[0].id == "_terminal_artifacts_finalized"
    writes = []
    ns.update(_terminal_artifacts_finalized=False, result_manifest_path=Path("synthetic_manifest.json"),
              out_result_path=Path("synthetic.json"), checkpoint_jsonl_path=Path("synthetic_checkpoint.jsonl"),
              pending_snapshot_path=Path("synthetic_pending.json"), results=[], _sequential_failed_count=0,
              _completion_manifest_gate_fields=lambda **kwargs: {"terminal_artifacts_finalized": ns["_terminal_artifacts_finalized"]},
              _atomic_write_json=lambda path, value: writes.append(copy.deepcopy(value)))
    if bad_end:
        connected.resources["affinity_mask"] = 3
        with pytest.raises(ValueError):
            execute(segment, ns)
        assert not writes and ns["_terminal_artifacts_finalized"] is False
        assert session.manifest_fields()["paired_execution_observation"]["end"] is None
    else:
        execute(segment, ns)
        assert len(writes) == 1 and writes[0]["terminal_artifacts_finalized"] is True
        bundle = writes[0]["paired_execution_observation"]
        assert bundle["start"]["phase"] == "START" and bundle["end"]["phase"] == "END"
        assert bundle["start"]["binding"]["attempt_id"] == ns["ts"]
        assert bundle["end"]["start_observation_sha256"] == bundle["start"]["observation_sha256"]
        assert writes[0]["paired_execution_runtime_fields"] == connected.fields
