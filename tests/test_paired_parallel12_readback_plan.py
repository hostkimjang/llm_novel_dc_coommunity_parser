"""v4 RunSpec→원장 재생→plan 봉투를 실제 함수로 검사하는 합성 자료 시험."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path
import socket
import subprocess
import sys

import pytest

from llm_batch.measurement import paired_execution_policy as policy
from llm_batch.measurement import paired_measurement_readback as reader
from tests.paired_parallel12_test_inputs import paired12, load, save, reseal_bundle
from tests import test_paired_measurement_readback as legacy
from tools import build_low_load_paired_plan as builder
from tools import run_independent_plan as runner
from tools.run_paired_measurement_readback import _parser, _exclusive_write_run_spec, render_korean_report


@pytest.fixture(autouse=True)
def no_external(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("v4 합성 계획·readback에서 외부/child 호출 금지")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(runner, "_ensure_dashboard", forbidden)


def test_full_v4_readback_accepts_overlapping_rows_and_preserves_cost_scope(tmp_path):
    before, after, wal, spec, low = paired12(tmp_path)
    original_wal = wal.read_bytes()
    result = reader.build_paired_measurement_readback(run_spec_path=spec,
        before_manifest_path=before, after_manifest_path=after)
    reader.validate_paired_measurement_readback(result, run_spec_path=spec,
        before_manifest_path=before, after_manifest_path=after)
    protocol = result["execution_protocol"]
    assert result["schema_version"] == reader.PARALLEL12_SCHEMA_VERSION
    assert protocol["schema_version"] == "paired_measurement_parallel12_readback_v1"
    assert "명시적 v4 병렬12" in render_korean_report(result)
    assert protocol["run_spec_schema_version"] == reader.PARALLEL12_RUN_SPEC_SCHEMA_VERSION
    assert protocol["requested_parallel"] == 12 and protocol["effective_parallel"] == 2
    assert protocol["observed_row_count_per_arm"] == 2
    assert result["counterfactual_reference_copy_cost"]["row_count"] == 1
    assert result["production_inference_comparable_row_count"] == 1
    assert result["zero_physical_call_coverage"]["denominator"] == 2
    assert result["counterfactual_reference_copy_cost"]["production_savings_kpi_eligible"] is False
    assert result["non_cost_metrics"]["frozen_actual_accuracy"]["value"] is None
    assert result["non_cost_metrics"]["money_cost"]["value"] is None
    assert result["gates"]["production_enable_allowed"] is False
    assert result["gates"]["full_scan_approval"] is False
    assert original_wal == wal.read_bytes()


@pytest.mark.parametrize("fault", ["policy_v3", "input_count", "parallel", "health_zero", "health_failure", "release", "scope", "row_pid", "row_outside", "typed_post", "attempt_reuse"])
def test_v4_resealed_bad_bindings_never_become_cost_go(tmp_path, fault):
    before, after, wal, spec_path, low = paired12(tmp_path)
    wal_bytes = wal.read_bytes()
    if fault in {"policy_v3", "input_count", "parallel", "health_zero", "health_failure"}:
        spec = load(spec_path)
        fields = spec["frozen_conditions"]["runtime_manifest_fields"]
        if fault == "policy_v3": spec["schema_version"] = reader.LOW_LOAD_RUN_SPEC_SCHEMA_VERSION
        elif fault == "input_count":
            frozen = load(low["policy_binding"]["path"])
            frozen["config_projection"]["input_post_count"] = 3
            frozen["config_projection"]["effective_parallel"] = 3
            frozen["config_projection_sha256"] = policy.canonical_sha256(frozen["config_projection"])
            frozen["policy_sha256"] = policy.canonical_sha256({k:v for k,v in frozen.items() if k != "policy_sha256"})
            new_ref = policy.write_execution_policy(frozen, tmp_path / "count3_policy.json")
            new_binding = {"schema_version": reader.EXECUTION_POLICY_BINDING_SCHEMA_VERSION,
                **{key:new_ref[key] for key in ("path", "file_sha256", "policy_sha256")}}
            spec["execution_policy"] = new_binding
            spec["frozen_conditions"]["shared_measurement_fields"]["execution_policy_binding"] = deepcopy(new_binding)
        elif fault == "parallel": fields["requested_parallel"] = 1
        elif fault == "health_zero": fields["mcp_health_ok_count"] = 0
        else: fields["mcp_health_failure_count"] = 1
        spec["run_spec_sha256"] = reader._sha256({k:v for k,v in spec.items() if k != "run_spec_sha256"})
        save(spec_path, spec)
    elif fault in {"release", "scope"}:
        manifest = load(before)
        manifest["publication_release_fingerprint" if fault == "release" else "publication_scope_id"] = "0" * 64
        save(before, manifest)
    else:
        output = Path(load(before)["output_file"])
        rows = load(output)
        bundle = rows[1]["run_meta"]["paired_execution_observation"]
        if fault == "row_pid":
            for phase in ("start", "end"): bundle[phase]["resources"]["pid"] = 1235
        elif fault == "row_outside": bundle["end"]["monotonic_ns"] = 1001
        elif fault == "typed_post": bundle["post_id"] = str(bundle["post_id"])
        else:
            for phase in ("start", "end"):
                bundle[phase]["binding"]["attempt_id"] = rows[0]["run_meta"]["paired_execution_observation"][phase]["binding"]["attempt_id"]
        reseal_bundle(bundle)
        save(output, rows)
    with pytest.raises(ValueError):
        reader.build_paired_measurement_readback(run_spec_path=spec_path,
            before_manifest_path=before, after_manifest_path=after)
    assert wal.read_bytes() == wal_bytes


def intervals(count, *, concurrent):
    origin = datetime(2026, 1, 1, tzinfo=timezone.utc)
    values = []
    for i in range(count):
        start, end = (1, 100) if concurrent else (1 + 100*i, 101 + 100*i)
        values.append({"start": {"monotonic_ns": start, "observed_at": (origin+timedelta(microseconds=start)).isoformat()},
                       "end": {"monotonic_ns": end, "observed_at": (origin+timedelta(microseconds=end)).isoformat()}})
    return values


@pytest.mark.parametrize("count", [1, 2, 11, 12, 13, 80])
def test_interval_sweep_accepts_serial_and_at_most_twelve(tmp_path, count):
    reader._validate_parallel12_row_intervals(intervals(count, concurrent=False),
        input_count=count, effective_parallel=min(count, 12))
    if count <= 12:
        reader._validate_parallel12_row_intervals(intervals(count, concurrent=True),
            input_count=count, effective_parallel=min(count, 12))
    else:
        with pytest.raises(ValueError, match="concurrency"):
            reader._validate_parallel12_row_intervals(intervals(count, concurrent=True),
                input_count=count, effective_parallel=12)


@pytest.mark.parametrize("clock", ["monotonic_ns", "observed_at"])
def test_only_one_clock_exceeding_twelve_still_rejected(clock):
    values = intervals(13, concurrent=False)
    overlap = intervals(13, concurrent=True)
    for row, bad in zip(values, overlap):
        for phase in ("start", "end"): row[phase][clock] = bad[phase][clock]
    with pytest.raises(ValueError, match="concurrency"):
        reader._validate_parallel12_row_intervals(values, input_count=13, effective_parallel=12)


def test_utc_coarse_equal_boundary_keeps_monotonic_check():
    values = intervals(12, concurrent=True)
    for row in values: row["end"]["observed_at"] = row["start"]["observed_at"]
    reader._validate_parallel12_row_intervals(values, input_count=12, effective_parallel=12)


def plan_fixture(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    before, after, wal, _, low = paired12(source)
    input_path = legacy._claimed_input_path(before)
    spec = reader.build_paired_measurement_run_spec(input_path=input_path, source_manifest_path=before,
        pair_id="synthetic-v4-plan", run_spec_schema_version=reader.PARALLEL12_RUN_SPEC_SCHEMA_VERSION,
        execution_policy_path=low["policy_binding"]["path"])
    spec_path = source / "fresh_spec.json"
    _exclusive_write_run_spec(spec_path, spec)
    monkeypatch.setattr(builder, "OUTPUT_ROOT", tmp_path / "out")
    args = dict(run_spec_path=spec_path, source_manifest_path=before, input_path=input_path,
        python_path=sys.executable, output_root=tmp_path / "out/new-plan", mcp_endpoints=["http://synthetic-search"],
        dashboard_url="http://127.0.0.1:18866", extra_environment={"LLM_HTTP_CONCURRENCY":"4",
            "PIPELINE_URL_FETCH_DISK_CACHE":"0", "PIPELINE_PAGE_ANALYZER_CACHE":"0"})
    return args, low


def test_v4_freeze_prebound_and_plan_actual_argv_without_execution(tmp_path, monkeypatch):
    args, low = plan_fixture(tmp_path, monkeypatch)
    spec = load(args["run_spec_path"])
    bound = reader.read_prebound_execution_measurement(run_spec_path=args["run_spec_path"],
        file_sha256=hashlib.sha256(args["run_spec_path"].read_bytes()).hexdigest(),
        self_sha256=spec["run_spec_sha256"], pair_id=spec["pair_id"], arm="BEFORE")
    assert bound["execution_policy"]["schema_version"] == policy.PARALLEL12_POLICY_SCHEMA
    built = builder.build_low_load_paired_plan(**args)
    plan = load(built["plan_path"])
    runner._validate_plan_self_binding(plan)
    runner._validate_batch_plan(plan, plan["planned_runs"])
    assert built["model_calls"] == built["child_processes_started"] == 0
    assert built["service_health_checked"] is False
    assert len(plan["planned_runs"]) == 2
    assert {run["batch_completion_contract"]["arm"] for run in plan["planned_runs"]} == {"BEFORE", "AFTER"}
    for run in plan["planned_runs"]:
        argv = run["command_argv"]
        assert argv[argv.index("--parallel")+1] == "12"
        assert argv[argv.index("--decision-call-ledger")+1] == "REQUIRED"
        assert "--no-dashboard" not in argv
        assert run["batch_completion_contract"]["schema_version"] == runner.PARALLEL12_BATCH_COMPLETION_SCHEMA
        assert run["batch_execution_envelope"]["schema_version"] == runner.PARALLEL12_BATCH_ENVELOPE_SCHEMA
        env = run["batch_execution_envelope"]["environment_binding"]
        assert env["MCP_HEALTH_REQUIRED_OK"] == env["MCP_HEALTH_WORKERS"] == "1"
        assert env["LLM_HTTP_CONCURRENCY"] == "4"
        assert env["PIPELINE_URL_FETCH_DISK_CACHE"] == env["PIPELINE_PAGE_ANALYZER_CACHE"] == "0"
        assert env["PIPELINE_MEASUREMENT_MUTABLE_CONTEXT_MODE"] == "FROZEN_OFF"
    with pytest.raises(FileExistsError): builder.build_low_load_paired_plan(**args)
    args_cli = _parser().parse_args(["--run-spec-schema", reader.PARALLEL12_RUN_SPEC_SCHEMA_VERSION])
    assert args_cli.run_spec_schema == reader.PARALLEL12_RUN_SPEC_SCHEMA_VERSION


@pytest.mark.parametrize("fault", ["batch_v2", "envelope_v2", "argv1", "argv16", "append_parallel", "dashboard", "health12", "source_bytes"])
def test_v4_resealed_plan_cannot_cross_revision_or_override_policy(tmp_path, monkeypatch, fault):
    args, low = plan_fixture(tmp_path, monkeypatch)
    plan = builder.build_low_load_paired_plan(**args)["plan"]
    run = plan["planned_runs"][0]
    envelope = run["batch_execution_envelope"]
    if fault == "batch_v2": run["batch_completion_contract"]["schema_version"] = runner.LOW_LOAD_BATCH_COMPLETION_SCHEMA
    elif fault == "envelope_v2": envelope["schema_version"] = runner.LOW_LOAD_BATCH_ENVELOPE_SCHEMA
    elif fault in {"argv1", "argv16"}: run["command_argv"][run["command_argv"].index("--parallel")+1] = "1" if fault == "argv1" else "16"
    elif fault == "append_parallel": run["command_argv"].append("--parallel=1")
    elif fault == "dashboard": run["command_argv"].append("--no-dashboard")
    elif fault == "health12": envelope["environment_binding"]["MCP_HEALTH_REQUIRED_OK"] = "12"
    else: Path(args["source_manifest_path"]).write_bytes(Path(args["source_manifest_path"]).read_bytes()+b"\n")
    envelope["effective_argv_sha256"] = runner._canonical_sha256(run["command_argv"])
    envelope["environment_sha256"] = runner._canonical_sha256(envelope["environment_binding"])
    with pytest.raises(ValueError): runner._validate_batch_plan(plan, plan["planned_runs"])
