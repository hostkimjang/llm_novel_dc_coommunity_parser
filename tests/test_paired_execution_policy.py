"""합성 설정/health로 계약만 검산한다. 마지막 Windows 시험의 자원만 실제 관측한다."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

import pytest

from llm_batch.measurement import paired_execution_policy as policy


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def fixture():
    config = {"schema_version": "expert_execution_config_v1", "profile": "low-load-validation",
        "settings": {key: {"value": value, "source": "SYNTHETIC_FIXTURE"} for key, value in
            {"vlm": True, "ocr": True, "ledger_mode": "REQUIRED", "context_diagnostics": False,
             "requested_parallel": 1}.items()}, "requested_parallel": 1, "effective_parallel": 1,
        "dashboard": {"enabled": True, "url": "http://localhost:9999", "mode": "SYNTHETIC"},
        "compression": {"status": "OFF_NOT_REQUESTED"}, "image_review": {"ready": True},
        "source": {"entry_sha256": "1" * 64, "runtime_source_sha256": "2" * 64,
                   "source_scope": "SELECTED_RUNTIME_FILES", "entry_point": "synthetic.py"},
        "resources": {"pid": 123}, "output_file": "synthetic-output.json"}
    runtime = {"llm_model": "synthetic-never-called", "llm_endpoint": "http://127.0.0.1:1/v1",
        "generation_config_sha256": "3" * 64, "prompt_sha256": "4" * 64,
        "publication_config_sha256": "5" * 64, "publication_decision_environment_sha256": "6" * 64,
        "mcp_endpoint_pool_sha256": policy.endpoint_pool_fingerprint(["http://127.0.0.1:2/mcp"]),
        "mcp_health_workers": 1, "mcp_health_probe_batch_size": 1, "mcp_health_required_ok_count": 1,
        "mcp_health_include_search": True, "mcp_health_light_mode": False, "mcp_reuse_shards_only": True,
        "mcp_auto_up_shards": False, "mcp_auto_recreate_shards": False,
        "mcp_auto_scale_up_missing_shards": False, "mutable_context_mode": "FROZEN_OFF",
        "batch_context_enabled": False, "central_slang_db_write_allowed": False,
        "slang_mode": "OFF", "slang_snapshot_sha256": None, "candidate_retrieval_mode": "OFF",
        "community_knowledge_mode": "OFF", "candidate_reranker_mode": "OFF"}
    projection = policy.execution_config_projection(config, runtime_fields=runtime)
    frozen = policy.build_low_load_policy(policy_id="synthetic-policy", config_projection=projection)
    binding = {"pair_id": "synthetic-pair", "arm": "BEFORE", "run_id": "synthetic-run",
               "attempt_id": "synthetic-attempt", "input_sha256": "7" * 64,
               "publication_scope_id": "8" * 64}
    return config, runtime, frozen, binding


def observations(frozen, binding):
    start = policy.seal_execution_observation({"schema_version": policy.OBSERVATION_SCHEMA,
        "phase": "START", "binding": deepcopy(binding), "policy_sha256": frozen["policy_sha256"],
        "config_projection": deepcopy(frozen["config_projection"]),
        "config_projection_sha256": frozen["config_projection_sha256"],
        "observed_at": "2026-10-10T00:00:00Z", "monotonic_ns": 1000,
        "resources": {**deepcopy(frozen["resources"]), "pid": 123, "status": "OBSERVED"},
        "health": {"observed_at": "2026-10-09T23:59:59Z", "endpoint_pool_sha256":
            frozen["config_projection"]["runtime"]["mcp_endpoint_pool_sha256"],
            "ok_count": 1, "failure_count": 0, "checked_count": 1}, "start_observation_sha256": None})
    end = deepcopy(start)
    end.update(phase="END", observed_at="2026-10-10T00:00:01Z", monotonic_ns=2000,
               start_observation_sha256=start["observation_sha256"])
    return start, policy.seal_execution_observation(end)


def set_path(value, path, replacement):
    parent = value
    for key in path[:-1]:
        parent = parent[key]
    parent[path[-1]] = replacement


def reseal_policy(value):
    value["policy_sha256"] = policy.canonical_sha256({k: v for k, v in value.items() if k != "policy_sha256"})
    return value


def test_projection_stability_and_frozen_copy_without_io(monkeypatch):
    config, runtime, frozen, binding = fixture()
    before = deepcopy((config, runtime, frozen, binding))
    monkeypatch.setattr(Path, "open", lambda *a, **k: pytest.fail("pure validator opened a file"))
    changed = deepcopy(config)
    changed.update(resources={"pid": 999, "observed_at": "later"}, output_file="different-output.json")
    changed["dashboard"].update(url="http://elsewhere", mode="OTHER")
    changed["source"]["entry_point"] = "different-path.py"
    for setting in changed["settings"].values():
        setting["source"] = "OTHER"
    projected = policy.execution_config_projection(changed, runtime_fields={**runtime, "pid": 999})
    assert projected == frozen["config_projection"]
    assert policy.validate_low_load_policy(frozen) == frozen
    assert policy.build_low_load_policy(policy_id="synthetic-policy", config_projection=projected) == frozen
    projected["settings"]["ocr"] = False
    summary = policy.policy_summary(frozen)
    assert summary["publication_authority"] is False
    assert summary["model_immutability_proven"] is False
    assert summary["formal_kpi_status"] == "NOT_ESTIMABLE_POLICY_ONLY"
    assert (config, runtime, frozen, binding) == before


@pytest.mark.parametrize("path,value", [
    (("profile",), "paired-measurement"), (("requested_parallel",), 16),
    (("effective_parallel",), True), (("settings", "requested_parallel"), 1.0),
    (("settings", "ledger_mode"), "SHADOW"), (("settings", "ocr"), None),
    (("dashboard_enabled",), False), (("compression_status",), "ON"), (("image_review_ready",), False),
    (("source", "source_scope"), "ALL_SOURCE"), (("source", "entry_sha256"), "A" * 64),
    (("runtime", "mcp_health_workers"), 2), (("runtime", "mcp_health_probe_batch_size"), True),
    (("runtime", "mcp_health_required_ok_count"), 0), (("runtime", "mcp_health_include_search"), False),
    (("runtime", "mcp_health_light_mode"), True), (("runtime", "mcp_reuse_shards_only"), False),
    (("runtime", "mcp_auto_up_shards"), True), (("runtime", "mcp_auto_recreate_shards"), True),
    (("runtime", "mcp_auto_scale_up_missing_shards"), True), (("runtime", "mutable_context_mode"), "LIVE"),
    (("runtime", "batch_context_enabled"), True), (("runtime", "central_slang_db_write_allowed"), True),
    (("runtime", "slang_mode"), "LEARN"), (("runtime", "slang_snapshot_sha256"), "a" * 64),
    (("runtime", "candidate_retrieval_mode"), "SHADOW"), (("runtime", "community_knowledge_mode"), "READ_ONLY"),
    (("runtime", "candidate_reranker_mode"), "SHADOW"), (("runtime", "generation_config_sha256"), None),
])
def test_resealed_disallowed_projection_is_rejected(path, value):
    _, _, frozen, _ = fixture()
    set_path(frozen["config_projection"], path, value)
    frozen["config_projection_sha256"] = policy.canonical_sha256(frozen["config_projection"])
    with pytest.raises(policy.PairedExecutionPolicyError):
        policy.validate_low_load_policy(reseal_policy(frozen))


def test_missing_configuration_slang_snapshot_and_stable_config_drift():
    config, runtime, frozen, binding = fixture()
    del runtime["prompt_sha256"]
    with pytest.raises(policy.PairedExecutionPolicyError, match="FIELD_MISSING"):
        policy.execution_config_projection(config, runtime_fields=runtime)
    config, runtime, _, _ = fixture()
    runtime.update(slang_mode="READ_ONLY", slang_snapshot_sha256="9" * 64)
    assert policy.execution_config_projection(config, runtime_fields=runtime)["runtime"]["slang_mode"] == "READ_ONLY"
    runtime["slang_snapshot_sha256"] = None
    with pytest.raises(policy.PairedExecutionPolicyError):
        policy.execution_config_projection(config, runtime_fields=runtime)
    start, _ = observations(frozen, binding)
    start["config_projection"]["settings"]["ocr"] = False
    start["config_projection_sha256"] = policy.canonical_sha256(start["config_projection"])
    with pytest.raises(policy.PairedExecutionPolicyError, match="OBSERVATION_CONFIG_MISMATCH"):
        policy.validate_execution_observation(frozen, policy.seal_execution_observation(start), binding=binding, phase="START")


@pytest.mark.parametrize("url", ["https://user:password@host/v1", "http://@host", "http://host/?token=secret",
    "https://host/#fragment", "file:///tmp/x", "http://host:invalid", "http://[bad", ""])
def test_endpoint_credentials_and_invalid_pool_rejected(url):
    with pytest.raises(policy.PairedExecutionPolicyError):
        policy.endpoint_pool_fingerprint([url])


def test_endpoint_pool_order_and_duplicates_are_explicit():
    endpoints = ["http://localhost:1", "http://localhost:2"]
    assert policy.endpoint_pool_fingerprint(endpoints) != policy.endpoint_pool_fingerprint(endpoints[::-1])
    for value in ([], endpoints * 2, "http://localhost:1", ["http://localhost:1"] * 257):
        with pytest.raises(policy.PairedExecutionPolicyError):
            policy.endpoint_pool_fingerprint(value)


@pytest.mark.parametrize("path,value", [
    (("resources", "priority_class"), 32), (("resources", "affinity_mask"), 1),
    (("resources", "logical_cpu_count"), True), (("resources", "numeric_threads", "OMP_NUM_THREADS"), 1),
    (("health", "max_age_seconds"), 0), (("health", "max_age_seconds"), 3601),
    (("health", "future_tolerance_seconds"), 1), (("observation_scope",), "CONTINUOUS"),
])
def test_resealed_policy_cannot_relax_required_rules(path, value):
    _, _, frozen, _ = fixture()
    set_path(frozen, path, value)
    with pytest.raises(policy.PairedExecutionPolicyError):
        policy.validate_low_load_policy(reseal_policy(frozen))


@pytest.mark.parametrize("field,value", [("pair_id", "other"), ("arm", "AFTER"), ("run_id", "other"),
    ("attempt_id", "other"), ("input_sha256", "a" * 64), ("publication_scope_id", "b" * 64)])
def test_every_own_observation_binding_is_checked(field, value):
    _, _, frozen, binding = fixture()
    start, _ = observations(frozen, binding)
    start["binding"][field] = value
    with pytest.raises(policy.PairedExecutionPolicyError, match="BINDING_MISMATCH"):
        policy.validate_execution_observation(frozen, policy.seal_execution_observation(start), binding=binding, phase="START")


@pytest.mark.parametrize("path,value", [
    (("resources", "pid"), True), (("resources", "status"), "NOT_AVAILABLE"),
    (("resources", "priority_class"), 32), (("resources", "affinity_mask"), 3),
    (("resources", "logical_cpu_count"), 2), (("resources", "numeric_threads", "MKL_NUM_THREADS"), None),
    (("health", "endpoint_pool_sha256"), "a" * 64), (("health", "ok_count"), 0),
    (("health", "failure_count"), 1), (("health", "checked_count"), 2),
    (("health", "ok_count"), True), (("health", "observed_at"), "2026-10-09T23:54:59Z"),
    (("health", "observed_at"), "2026-10-10T00:00:01Z"), (("observed_at",), "2026-10-10T00:00:00"),
    (("observed_at",), "2026-10-10T09:00:00+09:00"), (("monotonic_ns",), 0),
    (("policy_sha256",), "a" * 64), (("phase",), "END"), (("start_observation_sha256",), "a" * 64),
])
def test_observation_invalid_resources_health_and_phase(path, value):
    _, _, frozen, binding = fixture()
    start, _ = observations(frozen, binding)
    set_path(start, path, value)
    with pytest.raises(policy.PairedExecutionPolicyError):
        policy.validate_execution_observation(frozen, policy.seal_execution_observation(start), binding=binding, phase="START")


def test_pair_seals_start_link_pid_clock_and_health_freshness():
    _, _, frozen, binding = fixture()
    start, end = observations(frozen, binding)
    result = policy.validate_execution_observation_pair(frozen, start, end, binding=binding)
    assert result["status"] == "PASS" and result["observed_elapsed_ns"] == 1000
    assert result["comparison_eligibility"] == "NOT_DECIDED_POLICY_OBSERVATIONS_ONLY"
    for path, value in [(('start_observation_sha256',), 'a' * 64), (('resources', 'pid'), 124),
                        (('monotonic_ns',), 1000), (('observed_at',), '2026-10-09T23:59:59Z'),
                        (('observed_at',), '2026-10-10T00:05:00Z')]:
        bad = deepcopy(end)
        set_path(bad, path, value)
        with pytest.raises(policy.PairedExecutionPolicyError):
            policy.validate_execution_observation_pair(frozen, start, policy.seal_execution_observation(bad), binding=binding)
    boundary = deepcopy(start)
    boundary["health"]["observed_at"] = "2026-10-09T23:55:00Z"
    policy.validate_execution_observation(frozen, policy.seal_execution_observation(boundary), binding=binding, phase="START")
    for target in (start, end):
        target["observation_sha256"] = "0" * 64
        with pytest.raises(policy.PairedExecutionPolicyError, match="SELF_SHA_MISMATCH"):
            policy.validate_execution_observation(frozen, target, binding=binding, phase=target["phase"])


def test_policy_exclusive_write_raw_sha_and_self_sha_are_distinct(tmp_path):
    _, _, frozen, _ = fixture()
    target = tmp_path / "policy.json"
    written = policy.write_execution_policy(frozen, target)
    original = target.read_bytes()
    assert written["file_sha256"] == sha(original)
    assert policy.read_execution_policy(target, expected_sha256=sha(original), expected_policy_sha256=frozen["policy_sha256"]) == written
    with pytest.raises(policy.PairedExecutionPolicyError, match="OUTPUT_EXISTS"):
        policy.write_execution_policy(frozen, target)
    assert target.read_bytes() == original
    reformatted = json.dumps(frozen, ensure_ascii=False, indent=2).encode()
    target.write_bytes(reformatted)
    with pytest.raises(policy.PairedExecutionPolicyError, match="FILE_SHA_MISMATCH"):
        policy.read_execution_policy(target, expected_sha256=sha(original))
    assert policy.read_execution_policy(target, expected_sha256=sha(reformatted))["policy_sha256"] == frozen["policy_sha256"]
    with pytest.raises(policy.PairedExecutionPolicyError, match="EXPECTED_SELF_SHA_MISMATCH"):
        policy.read_execution_policy(target, expected_sha256=sha(reformatted), expected_policy_sha256="a" * 64)


@pytest.mark.parametrize("raw", [b'{"x":1,"x":2}', b'{"x":NaN}', b'\xff', b'{', b'[]',
    b' ' * (policy.MAX_POLICY_BYTES + 1)], ids=["duplicate-key", "nan", "invalid-utf8", "broken-json", "wrong-schema", "byte-limit"])
def test_strict_file_parse_schema_and_boundaries(tmp_path, raw):
    target = tmp_path / "bad.json"
    target.write_bytes(raw)
    with pytest.raises(policy.PairedExecutionPolicyError):
        policy.read_execution_policy(target, expected_sha256=sha(raw))


def test_self_seal_extra_keys_unknown_values_and_missing_file(tmp_path):
    _, _, frozen, binding = fixture()
    changed = deepcopy(frozen)
    changed["policy_id"] = "tampered"
    with pytest.raises(policy.PairedExecutionPolicyError, match="SELF_SHA_MISMATCH"):
        policy.validate_low_load_policy(changed)
    changed = deepcopy(frozen)
    changed["unknown"] = False
    with pytest.raises(policy.PairedExecutionPolicyError, match="SCHEMA_INVALID"):
        policy.validate_low_load_policy(reseal_policy(changed))
    for value in (float("nan"), object(), {"x": "x" * (policy.MAX_POLICY_BYTES + 1)}):
        with pytest.raises(policy.PairedExecutionPolicyError):
            policy.validate_low_load_policy(value)
    for path in (tmp_path / "absent.json", "//untrusted-server/share/policy.json", "https://example.test/policy.json"):
        with pytest.raises(policy.PairedExecutionPolicyError):
            policy.read_execution_policy(path, expected_sha256="a" * 64)
    start, _ = observations(frozen, binding)
    start["unrecognized"] = True
    with pytest.raises(policy.PairedExecutionPolicyError, match="SCHEMA_INVALID"):
        policy.seal_execution_observation(start)


@pytest.mark.skipif(os.name != "nt", reason="actual resource capture is Windows only")
def test_actual_start_end_resources_and_fresh_second_read(monkeypatch):
    from llm_batch.runtime import execution_config as runtime_module
    config, runtime, frozen, binding = fixture()
    health = {"observed_at": datetime.now(timezone.utc).isoformat(), "endpoint_pool_sha256":
        runtime["mcp_endpoint_pool_sha256"], "ok_count": 1, "failure_count": 0, "checked_count": 1}
    actual = runtime_module.observe_process_resources
    calls = []

    def observe(env):
        value = actual(env)
        calls.append(deepcopy(value))
        return value

    monkeypatch.setattr(runtime_module, "observe_process_resources", observe)
    start = policy.capture_execution_observation(frozen, config, runtime_fields=runtime, binding=binding, phase="START", health=health)
    end = policy.capture_execution_observation(frozen, config, runtime_fields=runtime, binding=binding, phase="END", health=health, start_observation=start)
    assert len(calls) == 2 and start["resources"]["pid"] == end["resources"]["pid"] == os.getpid()
    assert policy.validate_execution_observation_pair(frozen, start, end, binding=binding)["status"] == "PASS"

    def changed_resources(env):
        value = observe(env)
        value["affinity_mask"] = 3
        return value

    monkeypatch.setattr(runtime_module, "observe_process_resources", changed_resources)
    with pytest.raises(policy.PairedExecutionPolicyError, match="RESOURCE_OBSERVATION_MISMATCH"):
        policy.capture_execution_observation(frozen, config, runtime_fields=runtime, binding=binding, phase="END", health=health, start_observation=start)
    assert len(calls) == 3

    def unavailable(_):
        raise OSError("synthetic unavailable API")

    monkeypatch.setattr(runtime_module, "observe_process_resources", unavailable)
    with pytest.raises(policy.PairedExecutionPolicyError, match="RESOURCE_OBSERVATION_FAILED"):
        policy.capture_execution_observation(frozen, config, runtime_fields=runtime, binding=binding, phase="START", health=health)
