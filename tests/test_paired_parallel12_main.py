"""기존 main AST 연결 harness를 v4 policy에 결속한다. 실제 모델 런 시험은 아니다."""
from copy import deepcopy
from types import SimpleNamespace
import socket
import subprocess

import pytest

from llm_batch.measurement import paired_execution_policy as policy
from tests import test_paired_execution_main as original
from tests.test_paired_execution_main import connected, main_ast
from tools import run_independent_plan as runner


@pytest.fixture(autouse=True)
def no_external(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("main v4 연결 시험의 외부 호출/child 실행 금지")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)


def bind12(connected, tmp_path, monkeypatch, count):
    # preflight의 실제 import가 기존 harness의 fingerprint lambda를 대체한다.
    # 따라서 동일한 합성 client에 실제 fingerprint 함수가 읽는 필드를 모두 둔다.
    ns = connected.ns
    client_fields = {
        "model": connected.fields["llm_model"], "endpoint": connected.fields["llm_endpoint"],
        "backend": "openai-compatible", "server_type": "synthetic", "profile": "synthetic",
        "chat_format": "synthetic", "temperature": 0.2, "top_p": 0.9, "min_p": 0.1,
        "repeat_penalty": 1.0, "max_tokens": 64, "json_grammar": False, "think_stream": False,
        "enable_thinking": False, "stream": True, "timeout_s": 10, "max_retries": 1,
        "retry_base_delay": 0.1,
    }
    monkeypatch.setattr(original.LLMClient, "__init__",
        lambda self, *args, **kwargs: self.__dict__.update(deepcopy(client_fields)))
    connected.fields["generation_config_sha256"] = original.paired_execution.generation_fingerprint(
        SimpleNamespace(**client_fields), ns["os"].environ)
    connected.fields["prompt_sha256"] = original.paired_execution.prompt_fingerprint(ns["repo_root"])
    config = connected.config
    config["settings"]["requested_parallel"]["value"] = 12
    config.update(requested_parallel=12, effective_parallel=min(count, 12))
    frozen = policy.build_low_load_policy(policy_id="SYNTHETIC_MAIN_V4",
        config_projection=policy.execution_config_projection(config, runtime_fields=connected.fields,
            projection_schema=policy.PARALLEL12_PROJECTION_SCHEMA, input_post_count=count))
    ref = policy.write_execution_policy(frozen, tmp_path / "main_policy_v4.json")
    connected.reference, connected.policy = ref, frozen
    ns["_decision_call_measurement"]["execution_policy_binding"] = {
        key: ref[key] for key in ("path", "file_sha256", "policy_sha256")}
    ns.update(_paired_policy=frozen, _REQUESTED_PARALLEL_RAW=12, _REQUESTED_PARALLEL=12,
        _PARALLEL=min(count, 12), posts=[SimpleNamespace(post_id=101+i) for i in range(count)])
    return ns


def preflight(connected, main_ast):
    ns = connected.ns
    instrumented_session = ns["PairedExecutionSession"]
    original.execute([original.preflight_block(main_ast)], ns)
    # 실제 import와 policy 검산을 거친 뒤 super()를 호출하는 원형 event spy만 복구한다.
    assert issubclass(instrumented_session, ns["PairedExecutionSession"])
    ns["PairedExecutionSession"] = instrumented_session


@pytest.mark.parametrize("count", [1, 5, 12, 80])
def test_real_main_preflight_accepts_policy_bounded_parallel_and_one_endpoint(connected, main_ast, tmp_path, monkeypatch, count):
    ns = bind12(connected, tmp_path, monkeypatch, count)
    argv = runner._low_load_command_argv(python_path="synthetic-python", input_path="input.jsonl",
        output_path="fresh.json", policy=connected.policy, environment={})
    assert argv[argv.index("--parallel")+1] == "12"
    preflight(connected, main_ast)
    assert connected.events == []
    session = original.start(connected, main_ast)
    assert session.manifest_fields()["paired_execution_observation"]["start"]["config_projection"]["input_post_count"] == count


@pytest.mark.parametrize("early", [False, True])
def test_actual_process_one_keeps_v4_attempt_ledger_and_real_row_end(connected, main_ast, tmp_path, monkeypatch, early):
    bind12(connected, tmp_path, monkeypatch, 1)
    preflight(connected, main_ast)
    # 기존 시험의 실제 _process_one·원장 seal/assertions를 그대로 실행한다.
    original.test_actual_process_one_keeps_row_attempt_and_normal_or_early_end(connected, main_ast, early)
    assert connected.ns["_paired_session"].manifest_fields()["paired_execution_observation"]["end"]["config_projection"]["effective_parallel"] == 1


@pytest.mark.parametrize("field,value", [("_REQUESTED_PARALLEL_RAW", 1), ("_REQUESTED_PARALLEL_RAW", 16), ("_PARALLEL", 1), ("_NO_DASHBOARD", True)])
def test_real_main_rejects_runtime_parallel_or_dashboard_override_before_dispatch(connected, main_ast, tmp_path, monkeypatch, field, value):
    ns = bind12(connected, tmp_path, monkeypatch, 80)
    ns[field] = value
    with pytest.raises(ValueError): original.execute([original.preflight_block(main_ast)], ns)
    assert connected.events == []


def test_main_fixture_uses_real_fingerprint_and_missing_attribute_still_fails(connected, main_ast, tmp_path, monkeypatch):
    ns = bind12(connected, tmp_path, monkeypatch, 1)
    preflight(connected, main_ast)
    client = ns["LLMClient"]()
    assert ns["generation_fingerprint"] is original.paired_execution.generation_fingerprint
    assert ns["generation_fingerprint"](client, ns["os"].environ) == connected.fields["generation_config_sha256"]
    assert ns["prompt_fingerprint"](ns["repo_root"]) == connected.fields["prompt_sha256"]
    del client.backend
    with pytest.raises(AttributeError): ns["generation_fingerprint"](client, ns["os"].environ)
    assert connected.events == []
