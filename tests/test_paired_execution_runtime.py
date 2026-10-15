"""합성 policy/health/OS 응답으로 runtime 계약만 확인한다. 모델·네트워크 호출 없음."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import os
from types import SimpleNamespace

import pytest

from llm_batch.measurement import paired_execution_policy as policy
from llm_batch.runtime import execution_config as os_resources
from llm_batch.runtime import paired_execution as runtime
from test_paired_execution_policy import fixture as policy_fixture
from test_paired_execution_policy import observations as policy_observations


@pytest.fixture
def session_fixture(tmp_path, monkeypatch):
    config, fields, frozen, binding = policy_fixture()
    state = {"config": config, "fields": fields, "health_failure": False, "health_calls": 0,
             "resource_calls": 0, "resources": {**deepcopy(frozen["resources"]),
                 "pid": os.getpid(), "status": "OBSERVED"}}
    state["resources"].pop("platform")

    def resources(_):
        state["resource_calls"] += 1
        return deepcopy(state["resources"])

    monkeypatch.setattr(os_resources, "observe_process_resources", resources)

    def health():
        state["health_calls"] += 1
        if state["health_failure"]:
            raise ValueError("synthetic health failure")
        return {"observed_at": datetime.now(timezone.utc).isoformat(), "endpoint_pool_sha256":
            fields["mcp_endpoint_pool_sha256"], "ok_count": 1, "failure_count": 0, "checked_count": 1}

    written = policy.write_execution_policy(frozen, tmp_path / "synthetic-policy.json")
    measurement = {"pair_id": binding["pair_id"], "arm": binding["arm"], "execution_policy_binding":
        {key: written[key] for key in ("path", "file_sha256", "policy_sha256")}}
    arguments = {"measurement": measurement, "run_id": binding["run_id"], "input_sha256": binding["input_sha256"],
        "publication_scope_id": binding["publication_scope_id"], "execution_config": lambda: deepcopy(state["config"]),
        "runtime_fields": lambda: deepcopy(state["fields"]), "health": health}
    return runtime.PairedExecutionSession(**arguments), state, arguments, written


def test_session_lifecycle_and_own_run_row_bindings(session_fixture):
    session, state, arguments, written = session_fixture
    before = session.manifest_fields()["paired_execution_observation"]
    assert before["start"] is None and before["end"] is None
    session.start()
    for index, post, attempt in [(1, 101, "synthetic-row-attempt-1"), (2, "102", "synthetic-row-attempt-2")]:
        session.start_row(input_index=index, post_id=post, attempt_id=attempt)
        result = session.finish_row(input_index=index, post_id=post)
        observation = result["paired_execution_observation"]
        assert observation["input_index"] == index and type(observation["post_id"]) is type(post)
        expected = {"pair_id": arguments["measurement"]["pair_id"], "arm": "BEFORE",
            "run_id": arguments["run_id"], "attempt_id": attempt, "input_sha256": arguments["input_sha256"],
            "publication_scope_id": arguments["publication_scope_id"]}
        assert observation["start"]["binding"] == observation["end"]["binding"] == expected
        assert policy.validate_execution_observation_pair(written["policy"], observation["start"],
            observation["end"], binding=expected)["status"] == "PASS"
    session.finish()
    manifest = session.manifest_fields()
    bundle = manifest["paired_execution_observation"]
    assert bundle["start"]["binding"]["attempt_id"] == arguments["run_id"]
    assert bundle["end"]["start_observation_sha256"] == bundle["start"]["observation_sha256"]
    assert state["health_calls"] == state["resource_calls"] == 6
    bundle["start"]["binding"]["run_id"] = "external-mutation"
    assert session.manifest_fields()["paired_execution_observation"]["start"]["binding"]["run_id"] == arguments["run_id"]
    for action in (session.start, session.finish,
                   lambda: session.start_row(input_index=3, post_id=103, attempt_id="row-3")):
        with pytest.raises(ValueError):
            action()


def test_active_row_sequential_and_post_type_guards(session_fixture):
    session, state, _, _ = session_fixture
    for action in (session.finish, lambda: session.start_row(input_index=1, post_id=101, attempt_id="row-1"),
                   lambda: session.finish_row(input_index=1, post_id=101)):
        with pytest.raises(ValueError):
            action()
    assert state["health_calls"] == 0
    session.start()
    session.start_row(input_index=1, post_id=101, attempt_id="row-1")
    for action in (session.finish, lambda: session.start_row(input_index=2, post_id=102, attempt_id="row-2"),
                   lambda: session.finish_row(input_index=1, post_id="101"),
                   lambda: session.finish_row(input_index=1, post_id=102)):
        with pytest.raises(ValueError):
            action()
    assert state["health_calls"] == 2
    session.finish_row(input_index=1, post_id=101)
    with pytest.raises(ValueError):
        session.start_row(input_index=1, post_id=101, attempt_id="row-1-retry")
    with pytest.raises(ValueError):
        session.finish_row(input_index=1, post_id=101)


@pytest.mark.parametrize("index", [True, 1.0, 0, -1, "1", None])
def test_start_row_rejects_invalid_index_without_capture(session_fixture, index):
    session, state, _, _ = session_fixture
    session.start()
    with pytest.raises(ValueError):
        session.start_row(input_index=index, post_id=101, attempt_id="row-1")
    assert state["health_calls"] == 1


@pytest.mark.parametrize("index", [True, 1.0])
def test_finish_row_rejects_bool_or_float_index_alias(session_fixture, index):
    session, state, _, _ = session_fixture
    session.start()
    session.start_row(input_index=1, post_id=101, attempt_id="row-1")
    with pytest.raises(ValueError):
        session.finish_row(input_index=index, post_id=101)
    assert state["health_calls"] == 2
    assert session.finish_row(input_index=1, post_id=101)["paired_execution_observation"]["input_index"] == 1


def test_completed_row_attempt_cannot_be_reused_for_another_row(session_fixture):
    session, state, _, _ = session_fixture
    session.start()
    session.start_row(input_index=1, post_id=101, attempt_id="same-attempt")
    session.finish_row(input_index=1, post_id=101)
    with pytest.raises(ValueError):
        session.start_row(input_index=2, post_id=102, attempt_id="same-attempt")
    assert state["health_calls"] == 3
    session.start_row(input_index=2, post_id=102, attempt_id="different-attempt")


@pytest.mark.parametrize("attempt", [None, "", True, "synthetic-run"])
def test_invalid_row_attempt_does_not_create_active_row(session_fixture, attempt):
    session, _, _, _ = session_fixture
    session.start()
    with pytest.raises(ValueError):
        session.start_row(input_index=1, post_id=101, attempt_id=attempt)
    session.start_row(input_index=1, post_id=101, attempt_id="valid-attempt")
    session.finish_row(input_index=1, post_id=101)


def test_failed_row_and_run_end_are_not_fabricated_or_consumed(session_fixture):
    session, state, _, _ = session_fixture
    session.start()
    session.start_row(input_index=1, post_id=101, attempt_id="row-1")
    state["health_failure"] = True
    with pytest.raises(ValueError, match="synthetic health failure"):
        session.finish_row(input_index=1, post_id=101)
    assert session.manifest_fields()["paired_execution_observation"]["end"] is None
    with pytest.raises(ValueError, match="rows unfinished"):
        session.finish()
    state["health_failure"] = False
    state["resources"]["affinity_mask"] = 3
    with pytest.raises(ValueError, match="RESOURCE_OBSERVATION_MISMATCH"):
        session.finish_row(input_index=1, post_id=101)
    state["resources"]["affinity_mask"] = 2
    row = session.finish_row(input_index=1, post_id=101)
    assert row["paired_execution_observation"]["end"]["phase"] == "END"
    state["health_failure"] = True
    with pytest.raises(ValueError, match="synthetic health failure"):
        session.finish()
    assert session.manifest_fields()["paired_execution_observation"]["end"] is None
    state["health_failure"] = False
    session.finish()
    assert session.manifest_fields()["paired_execution_observation"]["end"]["phase"] == "END"


def test_run_end_is_committed_only_after_final_pair_validation(session_fixture, monkeypatch):
    session, _, _, _ = session_fixture
    session.start()
    original = runtime.validate_execution_observation_pair

    def reject(*args, **kwargs):
        raise ValueError("synthetic final pair validation failure")

    monkeypatch.setattr(runtime, "validate_execution_observation_pair", reject)
    with pytest.raises(ValueError, match="final pair validation failure"):
        session.finish()
    assert session.manifest_fields()["paired_execution_observation"]["end"] is None
    monkeypatch.setattr(runtime, "validate_execution_observation_pair", original)
    session.finish()
    assert session.manifest_fields()["paired_execution_observation"]["end"]["phase"] == "END"


def test_manifest_runtime_fields_do_not_expose_callback_owned_mapping(session_fixture):
    session, state, _, _ = session_fixture
    session._runtime = lambda: state["fields"]
    result = session.manifest_fields()
    result["paired_execution_runtime_fields"]["llm_model"] = "external-mutation"
    assert state["fields"]["llm_model"] == "synthetic-never-called"
    session.manifest_fields()


@pytest.mark.parametrize("source", ["execution", "generation", "prompt", "pool"])
def test_live_projection_drift_is_rejected_without_end(session_fixture, source):
    session, state, _, _ = session_fixture
    session.start()
    if source == "execution":
        state["config"]["settings"]["ocr"]["value"] = False
    else:
        key = {"generation": "generation_config_sha256", "prompt": "prompt_sha256", "pool": "mcp_endpoint_pool_sha256"}[source]
        state["fields"][key] = "a" * 64
    with pytest.raises(ValueError):
        session.manifest_fields()
    with pytest.raises(ValueError):
        session.finish()
    assert session._end is None


def test_policy_file_rechecked_before_each_capture(session_fixture):
    from pathlib import Path
    session, state, _, written = session_fixture
    target = Path(written["path"])
    original = target.read_bytes()
    session.start()
    target.write_bytes(original + b" ")
    with pytest.raises(ValueError, match="POLICY_FILE_SHA_MISMATCH"):
        session.start_row(input_index=1, post_id=101, attempt_id="row-1")
    assert state["health_calls"] == 1
    target.write_bytes(original)
    session.start_row(input_index=1, post_id=101, attempt_id="row-1")
    session.finish_row(input_index=1, post_id=101)
    target.write_bytes(original + b" ")
    with pytest.raises(ValueError, match="POLICY_FILE_SHA_MISMATCH"):
        session.finish()
    assert session.manifest_fields()["paired_execution_observation"]["end"] is None


def test_constructor_requires_file_and_policy_binding(session_fixture):
    _, _, arguments, _ = session_fixture
    for field in ("file_sha256", "policy_sha256"):
        bad = deepcopy(arguments["measurement"])
        bad["execution_policy_binding"][field] = "a" * 64
        with pytest.raises(ValueError):
            runtime.PairedExecutionSession(**{**arguments, "measurement": bad})
    with pytest.raises(ValueError, match="binding missing"):
        runtime.PairedExecutionSession(**{**arguments, "measurement": {}})


@pytest.fixture
def clock(monkeypatch):
    class Clock(datetime):
        instant = datetime(2026, 10, 10, tzinfo=timezone.utc)

        @classmethod
        def now(cls, tz=None):
            return cls.instant

    monkeypatch.setattr(runtime, "datetime", Clock)
    return Clock


def test_health_freshness_rechecks_same_pool_and_returns_detached_copy(clock):
    endpoints, calls = ["http://127.0.0.1:1/mcp"], []
    probe = runtime.FreshHealthProbe(endpoints=lambda: endpoints, checker=lambda endpoint:
        calls.append(endpoint) or {"ok": True, "search_skipped": False}, max_age_seconds=10)
    first = probe()
    saved = deepcopy(first)
    first["ok_count"] = 999
    clock.instant += timedelta(seconds=4)
    assert probe() == saved and len(calls) == 1
    clock.instant += timedelta(seconds=1)
    refreshed = probe()
    assert len(calls) == 2 and refreshed["observed_at"] != saved["observed_at"]
    assert refreshed["endpoint_pool_sha256"] == saved["endpoint_pool_sha256"]
    endpoints.append("http://127.0.0.1:2/mcp")
    with pytest.raises(ValueError, match="pool changed"):
        probe()
    assert len(calls) == 2


@pytest.mark.parametrize("result", [None, {}, {"ok": False}, {"ok": 1}, {"ok": True, "search_skipped": True}])
def test_health_failure_is_not_cached_as_success(clock, result):
    calls = []
    state = {"result": {"ok": True}}
    def check(endpoint):
        calls.append(endpoint)
        return state["result"]
    probe = runtime.FreshHealthProbe(endpoints=lambda: ["http://127.0.0.1:1/mcp"], checker=check, max_age_seconds=10)
    initial = probe()
    clock.instant += timedelta(seconds=6)
    state["result"] = result
    with pytest.raises(ValueError, match="fresh search health failed"):
        probe()
    assert probe._health == initial
    state["result"] = {"ok": True}
    assert probe()["observed_at"] != initial["observed_at"]
    assert len(calls) == 3


def test_health_future_clock_reprobes_and_fixed_pool_is_order_sensitive(clock):
    endpoints = ["http://127.0.0.1:1/mcp", "http://127.0.0.1:2/mcp"]
    calls = []
    probe = runtime.FreshHealthProbe(endpoints=lambda: endpoints, checker=lambda endpoint:
        calls.append(endpoint) or {"ok": True}, max_age_seconds=300)
    first = probe()
    assert calls == endpoints and first["ok_count"] == first["checked_count"] == 2
    clock.instant -= timedelta(seconds=1)
    assert probe()["observed_at"] != first["observed_at"] and calls == endpoints * 2
    endpoints.reverse()
    with pytest.raises(ValueError, match="pool changed"):
        probe()
    empty = runtime.FreshHealthProbe(endpoints=lambda: [], checker=lambda endpoint: pytest.fail("empty pool checked"), max_age_seconds=300)
    with pytest.raises(ValueError):
        empty()


def test_long_serial_health_probe_keeps_start_timestamp_and_policy_rejects_stale_result(clock):
    endpoints = ["http://127.0.0.1:1/mcp", "http://127.0.0.1:2/mcp"]
    calls = []
    began = clock.instant

    def slow_checker(endpoint):
        calls.append(endpoint)
        clock.instant += timedelta(seconds=6)
        return {"ok": True, "search_skipped": False}

    probe = runtime.FreshHealthProbe(endpoints=lambda: endpoints, checker=slow_checker, max_age_seconds=10)
    observed = probe()
    assert calls == endpoints
    assert observed["observed_at"] == began.isoformat()
    assert clock.instant == began + timedelta(seconds=12)
    _, _, original, binding = policy_fixture()
    projection = deepcopy(original["config_projection"])
    projection["runtime"]["mcp_endpoint_pool_sha256"] = policy.endpoint_pool_fingerprint(endpoints)
    frozen = policy.build_low_load_policy(policy_id="synthetic-slow-health", config_projection=projection,
                                         health_max_age_seconds=10)
    start, _ = policy_observations(frozen, binding)
    start.update(observed_at=clock.instant.isoformat(), health=observed)
    with pytest.raises(ValueError, match="HEALTH_STALE_OR_FUTURE"):
        policy.validate_execution_observation(frozen, policy.seal_execution_observation(start), binding=binding, phase="START")
    assert probe()["observed_at"] == (began + timedelta(seconds=12)).isoformat()
    assert calls == endpoints * 2


def test_generation_fingerprint_tracks_actual_settings_and_ignores_secrets():
    values = {"backend": "openai-compatible", "server_type": "synthetic", "profile": "synthetic",
        "chat_format": "synthetic", "temperature": 0.2, "top_p": 0.9, "min_p": 0.1, "repeat_penalty": 1.0,
        "max_tokens": 64, "json_grammar": False, "think_stream": False, "enable_thinking": False,
        "stream": True, "timeout_s": 10, "max_retries": 1, "retry_base_delay": 0.1}
    client = SimpleNamespace(**values)
    environment = {"API_KEY": "synthetic-secret-a", "LLM_TEMP_SYNTHETIC": "0.4"}
    baseline = runtime.generation_fingerprint(client, environment)
    assert baseline == runtime.generation_fingerprint(client, {**environment, "API_KEY": "synthetic-secret-b", "PID": "999"})
    for key, value in values.items():
        changed = deepcopy(client)
        setattr(changed, key, not value if type(value) is bool else value + 1 if isinstance(value, (int, float)) else value + "-changed")
        assert runtime.generation_fingerprint(changed, environment) != baseline, key
    for key in ("LLM_VLLM_TOP_K", "LLM_VLLM_PRESENCE_PENALTY", "LLM_REASON_REVIEW_MAX_TOKENS",
                "LLM_CONTEXT_LIMIT_TOKENS", "LLM_N_CTX", "LLM_ABORT_AFTER_JSON", "LLM_POST_JSON_PIECE_CAP",
                "LLM_POST_JSON_CHAR_CAP", "LLM_ACC_HARD_CAP", "LLM_TEMP_SYNTHETIC"):
        assert runtime.generation_fingerprint(client, {**environment, key: "12"}) != baseline, key
    assert values == vars(client)
    incomplete = SimpleNamespace(**{k: v for k, v in values.items() if k != "max_tokens"})
    with pytest.raises(AttributeError):
        runtime.generation_fingerprint(incomplete, environment)


def test_prompt_fingerprint_binds_paths_bytes_file_set_but_not_root(tmp_path):
    roots = [tmp_path / "one", tmp_path / "two"]
    for root in roots:
        prompts = root / "src/llm_batch/prompts"
        prompts.mkdir(parents=True)
        (prompts / "b.py").write_bytes(b"SYNTHETIC_B = 'b'\n")
        (prompts / "a.py").write_bytes(b"SYNTHETIC_A = 'a'\n")
    baseline = runtime.prompt_fingerprint(roots[0])
    assert baseline == runtime.prompt_fingerprint(roots[1])
    target = roots[1] / "src/llm_batch/prompts/a.py"
    original = target.read_bytes()
    target.write_bytes(original + b"# changed\n")
    assert runtime.prompt_fingerprint(roots[1]) != baseline
    target.write_bytes(original)
    target.rename(target.with_name("c.py"))
    assert runtime.prompt_fingerprint(roots[1]) != baseline
    extra = roots[0] / "src/llm_batch/prompts/c.py"
    extra.write_bytes(b"SYNTHETIC_NEW = True\n")
    assert runtime.prompt_fingerprint(roots[0]) != baseline
    extra.unlink()
    assert runtime.prompt_fingerprint(roots[0]) == baseline
    with pytest.raises(ValueError, match="source files missing"):
        runtime.prompt_fingerprint(tmp_path / "absent")
