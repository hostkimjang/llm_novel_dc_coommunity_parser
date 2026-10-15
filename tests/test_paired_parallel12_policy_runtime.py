"""명시 v4 정책과 실제 세션 클래스의 병렬 행 계약. 합성 자원/health만 사용."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
import os
import socket
import subprocess
import threading

import pytest

from llm_batch.measurement import paired_execution_policy as policy
from llm_batch.measurement import paired_measurement_readback as reader
from llm_batch.runtime import paired_execution as runtime
from llm_batch.runtime import execution_config as resources_module
from tests.paired_parallel12_test_inputs import low12
from tests.test_paired_execution_policy import fixture as legacy_policy_fixture


@pytest.fixture(autouse=True)
def no_external(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("합성 v4 계약 시험의 외부 호출/child 실행 금지")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)


@pytest.mark.parametrize("count", [1, 2, 5, 11, 12, 13, 80])
def test_explicit_v4_projection_bounds_input_without_changing_v3(tmp_path, count):
    low = low12(tmp_path, count=count)
    frozen = policy.validate_low_load_policy(low["policy"])
    assert frozen["schema_version"] == policy.PARALLEL12_POLICY_SCHEMA
    assert frozen["config_projection"]["input_post_count"] == count
    assert frozen["config_projection"]["requested_parallel"] == 12
    assert frozen["config_projection"]["effective_parallel"] == min(12, count)
    assert frozen["config_projection"]["runtime"]["mcp_health_required_ok_count"] == 1
    # 요청12만으로 새 프로토콜을 자동 선택하지 않는다.
    with pytest.raises(ValueError):
        policy.execution_config_projection(low["execution_config"], runtime_fields=low["runtime_fields"])


@pytest.mark.parametrize("mutation", ["count_bool", "count_zero", "effective", "requested", "setting", "projection_version", "policy_version", "health_workers", "health_fail_open"])
def test_resealed_v4_policy_rejects_inconsistent_contract(tmp_path, mutation):
    low = low12(tmp_path, count=2)
    frozen = deepcopy(low["policy"])
    p = frozen["config_projection"]
    if mutation == "count_bool": p["input_post_count"] = True
    elif mutation == "count_zero": p["input_post_count"] = 0
    elif mutation == "effective": p["effective_parallel"] = 12
    elif mutation == "requested": p["requested_parallel"] = 1
    elif mutation == "setting": p["settings"]["requested_parallel"] = 1
    elif mutation == "projection_version": p["schema_version"] = policy.PROJECTION_SCHEMA
    elif mutation == "policy_version": frozen["schema_version"] = policy.POLICY_SCHEMA
    elif mutation == "health_workers": p["runtime"]["mcp_health_workers"] = 12
    else: p["runtime"]["mcp_health_light_mode"] = True
    frozen["config_projection_sha256"] = policy.canonical_sha256(p)
    frozen["policy_sha256"] = policy.canonical_sha256({k: v for k, v in frozen.items() if k != "policy_sha256"})
    with pytest.raises(ValueError): policy.validate_low_load_policy(frozen)


def make_session(tmp_path, monkeypatch, count=13, ids=None):
    low = low12(tmp_path, count=count)
    observed = {**deepcopy(low["policy"]["resources"]), "pid": os.getpid(), "status": "OBSERVED"}
    observed.pop("platform")
    monkeypatch.setattr(resources_module, "observe_process_resources", lambda _: deepcopy(observed))
    health = lambda: {"observed_at": datetime.now(timezone.utc).isoformat(),
        "endpoint_pool_sha256": low["runtime_fields"]["mcp_endpoint_pool_sha256"],
        "ok_count": 1, "checked_count": 1, "failure_count": 0}
    arguments = dict(measurement={"pair_id": "synthetic-pair", "arm": "BEFORE", "execution_policy_binding": low["policy_binding"]},
        run_id="synthetic-run", input_sha256="a" * 64, publication_scope_id="b" * 64,
        execution_config=lambda: deepcopy(low["execution_config"]), runtime_fields=lambda: deepcopy(low["runtime_fields"]),
        health=health, input_post_ids=ids if ids is not None else list(range(101, 101 + count)))
    return runtime.PairedExecutionSession(**arguments), low, arguments, observed


def test_twelve_active_rows_then_finish_out_of_order_and_refill(tmp_path, monkeypatch):
    session, low, args, _ = make_session(tmp_path, monkeypatch)
    session.start()
    for index in range(1, 13):
        session.start_row(input_index=index, post_id=100 + index, attempt_id=f"row-{index}")
    with pytest.raises(ValueError, match="limit"):
        session.start_row(input_index=13, post_id=113, attempt_id="row-13")
    session.finish_row(input_index=7, post_id=107)
    session.start_row(input_index=13, post_id=113, attempt_id="row-13")
    with pytest.raises(ValueError, match="unfinished"): session.finish()
    for index in reversed([i for i in range(1, 14) if i != 7]):
        result = session.finish_row(input_index=index, post_id=100 + index)
        assert result["paired_execution_observation"]["input_index"] == index
        assert result["paired_execution_observation"]["start"]["resources"]["pid"] == os.getpid()
    session.finish()
    assert session.manifest_fields()["paired_execution_observation"]["end"]["phase"] == "END"
    with pytest.raises(ValueError): session.start_row(input_index=1, post_id=101, attempt_id="new-attempt")


@pytest.mark.parametrize("fault", ["index_bool", "index_zero", "index_high", "wrong_type", "wrong_post", "run_attempt", "duplicate_active", "duplicate_attempt", "completed_reuse"])
def test_bound_row_identity_rejected_before_capture(tmp_path, monkeypatch, fault):
    session, _, _, _ = make_session(tmp_path, monkeypatch, count=2)
    session.start()
    kwargs = dict(input_index=1, post_id=101, attempt_id="row-1")
    if fault == "index_bool": kwargs["input_index"] = True
    elif fault == "index_zero": kwargs["input_index"] = 0
    elif fault == "index_high": kwargs["input_index"] = 3
    elif fault == "wrong_type": kwargs["post_id"] = "101"
    elif fault == "wrong_post": kwargs["post_id"] = 102
    elif fault == "run_attempt": kwargs["attempt_id"] = "synthetic-run"
    else:
        session.start_row(**kwargs)
        if fault == "duplicate_attempt": kwargs.update(input_index=2, post_id=102)
        if fault == "completed_reuse":
            session.finish_row(input_index=1, post_id=101)
            kwargs["attempt_id"] = "different-attempt"
    with pytest.raises(ValueError): session.start_row(**kwargs)


@pytest.mark.parametrize("ids", [None, [101], [101, 101], [101, "101"], [True, 102], ["", 102], [-1, 102], [" spaced", 102]])
def test_constructor_requires_unique_typed_full_input(tmp_path, monkeypatch, ids):
    _, _, arguments, _ = make_session(tmp_path, monkeypatch, count=2)
    arguments["input_post_ids"] = ids
    with pytest.raises(ValueError, match="typed input"): runtime.PairedExecutionSession(**arguments)


def test_partial_completed_input_cannot_finish_or_reuse_attempt(tmp_path, monkeypatch):
    session, _, _, _ = make_session(tmp_path, monkeypatch, count=2)
    session.start()
    session.start_row(input_index=1, post_id=101, attempt_id="row-1")
    session.finish_row(input_index=1, post_id=101)
    with pytest.raises(ValueError, match="incomplete"): session.finish()
    with pytest.raises(ValueError, match="attempt"):
        session.start_row(input_index=2, post_id=102, attempt_id="row-1")


def test_small_input_effective_two_and_string_id_is_type_bound(tmp_path, monkeypatch):
    session, _, _, _ = make_session(tmp_path, monkeypatch, count=2, ids=[101, "named-post"])
    session.start()
    session.start_row(input_index=2, post_id="named-post", attempt_id="b")
    session.start_row(input_index=1, post_id=101, attempt_id="a")
    with pytest.raises(ValueError): session.finish_row(input_index=1, post_id="101")
    session.finish_row(input_index=2, post_id="named-post")
    session.finish_row(input_index=1, post_id=101)
    session.finish()


def test_lock_serializes_competing_thirteenth_admission(tmp_path, monkeypatch):
    session, _, _, _ = make_session(tmp_path, monkeypatch)
    session.start()
    barrier = threading.Barrier(13)
    def admit(index):
        barrier.wait(timeout=10)
        try:
            session.start_row(input_index=index, post_id=100 + index, attempt_id=f"row-{index}")
            return index, True
        except ValueError as exc:
            assert "active row limit" in str(exc)
            return index, False
    with ThreadPoolExecutor(max_workers=13) as pool:
        results = list(pool.map(admit, range(1, 14)))
    assert sum(ok for _, ok in results) == 12
    observations = []
    for index, ok in results:
        if ok:
            row = session.finish_row(input_index=index, post_id=100 + index)
            observations.append(row["paired_execution_observation"])
    denied = next(index for index, ok in results if not ok)
    session.start_row(input_index=denied, post_id=100 + denied, attempt_id=f"row-{denied}")
    row = session.finish_row(input_index=denied, post_id=100 + denied)
    observations.append(row["paired_execution_observation"])
    session.finish()
    bundle = session.manifest_fields()["paired_execution_observation"]
    for row in observations:
        assert row["start"]["resources"]["pid"] == row["end"]["resources"]["pid"] == os.getpid()
        assert bundle["start"]["monotonic_ns"] <= row["start"]["monotonic_ns"] < row["end"]["monotonic_ns"] <= bundle["end"]["monotonic_ns"]
    reader._validate_parallel12_row_intervals(observations, input_count=13, effective_parallel=12)


def clock_capture_inputs(tmp_path, monkeypatch, protocol):
    config, fields, frozen, binding = legacy_policy_fixture()
    if protocol == "v4":
        low = low12(tmp_path, count=2)
        config, fields, frozen = low["execution_config"], low["runtime_fields"], low["policy"]
    resources = {**deepcopy(frozen["resources"]), "pid": os.getpid(), "status": "OBSERVED"}
    resources.pop("platform")
    monkeypatch.setattr(resources_module, "observe_process_resources", lambda _: deepcopy(resources))
    health = {"observed_at": datetime.now(timezone.utc).isoformat(),
        "endpoint_pool_sha256": fields["mcp_endpoint_pool_sha256"],
        "ok_count": 1, "checked_count": 1, "failure_count": 0}
    return frozen, config, dict(runtime_fields=fields, binding=binding, health=health)


@pytest.mark.parametrize("protocol", ["v3", "v4"])
def test_capture_uses_raw_high_resolution_clock_without_coarse_clock_or_sleep(tmp_path, monkeypatch, protocol):
    frozen, config, kwargs = clock_capture_inputs(tmp_path, monkeypatch, protocol)
    values = iter((9_000_001, 9_000_003))
    reads = []
    def high_resolution():
        value = next(values)
        reads.append(value)
        return value
    def forbidden(*args, **kwargs):
        raise AssertionError("coarse clock fallback 또는 sleep 금지")
    monkeypatch.setattr(policy.time, "perf_counter_ns", high_resolution)
    monkeypatch.setattr(policy.time, "monotonic_ns", forbidden)
    monkeypatch.setattr(policy.time, "sleep", forbidden)
    start = policy.capture_execution_observation(frozen, config, phase="START", **kwargs)
    end = policy.capture_execution_observation(frozen, config, phase="END", start_observation=start, **kwargs)
    assert reads == [9_000_001, 9_000_003]
    assert [start["monotonic_ns"], end["monotonic_ns"]] == reads
    checked = policy.validate_execution_observation_pair(frozen, start, end, binding=kwargs["binding"])
    assert checked["observed_elapsed_ns"] == 2


@pytest.mark.parametrize("protocol", ["v3", "v4"])
@pytest.mark.parametrize("end_value", [1_000_000, 999_999])
def test_equal_or_backwards_high_resolution_observation_is_not_adjusted(tmp_path, monkeypatch, protocol, end_value):
    frozen, config, kwargs = clock_capture_inputs(tmp_path, monkeypatch, protocol)
    values = iter((1_000_000, end_value))
    observed = []
    def clock():
        value = next(values)
        observed.append(value)
        return value
    monkeypatch.setattr(policy.time, "perf_counter_ns", clock)
    start = policy.capture_execution_observation(frozen, config, phase="START", **kwargs)
    original_start = deepcopy(start)
    with pytest.raises(policy.PairedExecutionPolicyError, match="START_END_CLOCK_NOT_INCREASING"):
        policy.capture_execution_observation(frozen, config, phase="END", start_observation=start, **kwargs)
    assert observed == [1_000_000, end_value]
    assert start == original_start
