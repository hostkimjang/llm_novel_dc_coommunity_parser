"""로컬 합성 source만 사용한다. 계획 생성 중 model/서버/child 실행은 금지한다."""
from copy import deepcopy
import json
from pathlib import Path
import sys
from unittest.mock import patch

import pytest

from llm_batch.measurement import paired_measurement_readback as reader
from tests import test_paired_measurement_low_load as low_fixture
from tests import test_paired_measurement_readback as legacy_fixture
from tests import test_run_independent_plan as runner_fixture
from tools import build_low_load_paired_plan as builder
from tools import run_independent_plan as runner


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def reseal_envelope(run):
    envelope = run["batch_execution_envelope"]
    envelope["effective_argv_sha256"] = runner._canonical_sha256(run["command_argv"])
    envelope["environment_sha256"] = runner._canonical_sha256(envelope["environment_binding"])


def fixture(tmp_path, monkeypatch):
    source_root = tmp_path / "source"
    source_root.mkdir()
    before, after, wal, _, low = low_fixture.PairedMeasurementLowLoadTests()._fixture(source_root)
    input_path = legacy_fixture._claimed_input_path(before)
    spec = reader.build_paired_measurement_run_spec(input_path=input_path, source_manifest_path=before,
        pair_id="runner-SYNTHETIC_CONTRACT_ONLY", run_spec_schema_version=reader.LOW_LOAD_RUN_SPEC_SCHEMA_VERSION,
        execution_policy_path=low["policy_binding"]["path"])
    spec_path = source_root / "fresh_plan_spec.json"
    save(spec_path, spec)
    monkeypatch.setattr(builder, "OUTPUT_ROOT", tmp_path / "out")
    args = dict(run_spec_path=spec_path, source_manifest_path=before, input_path=input_path,
                python_path=sys.executable, output_root=tmp_path / "out" / "new-plan",
                mcp_endpoints=["http://synthetic-search"])
    return args, low, (before, after, wal, spec_path)


def test_plan_only_exclusive_readback_has_no_process_or_service_calls(tmp_path, monkeypatch):
    args, low, source_paths = fixture(tmp_path, monkeypatch)
    frozen = {path: path.read_bytes() for path in (*source_paths, Path(low["policy_binding"]["path"]), args["input_path"])}
    with patch("subprocess.Popen", side_effect=AssertionError("child forbidden")), \
            patch("subprocess.run", side_effect=AssertionError("process forbidden")), \
            patch("socket.socket.connect", side_effect=AssertionError("network forbidden")), \
            patch.object(runner, "_ensure_dashboard", side_effect=AssertionError("server forbidden")):
        receipt = builder.build_low_load_paired_plan(**args)
    assert receipt["status"] == "PLAN_ONLY_VERIFIED"
    assert receipt["model_calls"] == receipt["child_processes_started"] == 0
    assert receipt["service_health_checked"] is False
    assert list(args["output_root"].iterdir()) == [Path(receipt["plan_path"])]
    plan = load(receipt["plan_path"])
    runner._validate_plan_self_binding(plan)
    runner._validate_batch_plan(plan, plan["planned_runs"])
    assert {row["batch_completion_contract"]["arm"] for row in plan["planned_runs"]} == {"BEFORE", "AFTER"}
    assert len({row["batch_completion_contract"]["planned_run_id"] for row in plan["planned_runs"]}) == 2
    for run in plan["planned_runs"]:
        argv = run["command_argv"]
        assert argv[argv.index("--parallel") + 1] == "1"
        assert argv[argv.index("--decision-call-ledger") + 1] == "REQUIRED"
        assert "--no-dashboard" not in argv
        assert run["batch_execution_envelope"]["execution_policy_binding"] == low["policy_binding"]
    assert all(path.read_bytes() == raw for path, raw in frozen.items())
    with pytest.raises(FileExistsError):
        builder.build_low_load_paired_plan(**args)


@pytest.mark.parametrize("mutation", ["parallel", "profile", "ledger", "alias_override", "no_dashboard", "expert_entry"])
def test_resealed_v2_argv_cannot_override_frozen_execution(tmp_path, monkeypatch, mutation):
    args, _, _ = fixture(tmp_path, monkeypatch)
    run = builder.build_low_load_paired_plan(**args)["plan"]["planned_runs"][0]
    argv = run["command_argv"]
    if mutation in {"parallel", "profile", "ledger"}:
        flag, bad = {"parallel": ("--parallel", "16"), "profile": ("--execution-profile", "general"),
                     "ledger": ("--decision-call-ledger", "SHADOW")}[mutation]
        argv[argv.index(flag) + 1] = bad
    elif mutation == "alias_override":
        argv.extend(["--parallel=16"])
    elif mutation == "no_dashboard":
        argv.append("--no-dashboard")
    else:
        argv[2] = str(tmp_path / "unrelated.py")
    reseal_envelope(run)
    with pytest.raises(ValueError):
        runner._validate_batch_child_envelope(run, index=1, argv=argv,
                                              environment=run["batch_execution_envelope"]["environment_binding"])


@pytest.mark.parametrize("key,value", [("MCP_HEALTH_WORKERS", "16"), ("MCP_HEALTH_REQUIRED_OK", "16"),
    ("MCP_AUTO_UP_SHARDS", "1"), ("PIPELINE_MEASUREMENT_MUTABLE_CONTEXT_MODE", "NORMAL"),
    ("PIPELINE_DECISION_CALL_LEDGER_MODE", "SHADOW"), ("OMP_NUM_THREADS", "4"),
    ("LLM_MODEL", "different"), ("PIPELINE_SLANG_DB", "1"), ("MCP_ENDPOINTS", "http://other-search")])
def test_resealed_environment_drift_is_rejected(tmp_path, monkeypatch, key, value):
    args, _, _ = fixture(tmp_path, monkeypatch)
    run = builder.build_low_load_paired_plan(**args)["plan"]["planned_runs"][0]
    run["batch_execution_envelope"]["environment_binding"][key] = value
    reseal_envelope(run)
    with pytest.raises(ValueError):
        runner._validate_batch_child_envelope(run, index=1, argv=run["command_argv"],
                                              environment=run["batch_execution_envelope"]["environment_binding"])


@pytest.mark.parametrize("role", ["input", "source_manifest", "publication_wal", "policy", "run_spec"])
def test_changed_source_bytes_fail_before_new_directory(tmp_path, monkeypatch, role):
    args, low, sources = fixture(tmp_path, monkeypatch)
    if role in {"input", "source_manifest", "publication_wal"}:
        receipt = builder.build_low_load_paired_plan(**args)
        run = receipt["plan"]["planned_runs"][0]
        target = Path(run["batch_execution_envelope"]["source_binding"][role]["path"])
        target.write_bytes(target.read_bytes() + b" ")
        with pytest.raises(ValueError):
            runner._validate_batch_run_spec(run, index=1, batch=run["batch_completion_contract"])
    elif role == "policy":
        target = Path(low["policy_binding"]["path"])
        target.write_bytes(target.read_bytes() + b" ")
        with pytest.raises(ValueError):
            builder.build_low_load_paired_plan(**args)
        assert not args["output_root"].exists()
    else:
        spec = load(args["run_spec_path"])
        spec["input_post_count"] = 999
        save(args["run_spec_path"], spec)
        with pytest.raises(ValueError):
            builder.build_low_load_paired_plan(**args)
        assert not args["output_root"].exists()


def test_source_binding_cannot_be_rehashed_to_launder_changed_runtime(tmp_path, monkeypatch):
    args, _, _ = fixture(tmp_path, monkeypatch)
    run = builder.build_low_load_paired_plan(**args)["plan"]["planned_runs"][0]
    ref = run["batch_execution_envelope"]["source_binding"]["source_manifest"]
    source = load(ref["path"])
    source["llm_model"] = "different-model"
    save(ref["path"], source)
    ref.update(builder._reference(Path(ref["path"])))
    with pytest.raises(ValueError):
        runner._validate_batch_run_spec(run, index=1, batch=run["batch_completion_contract"])


def test_plan_only_rejects_read_only_slang_before_creating_output(tmp_path, monkeypatch):
    args, low, _ = fixture(tmp_path, monkeypatch)
    # 공통 reader는 READ_ONLY를 지원한다. 계획 생성기의 더 좁은 실행 지원
    # 경계를 고립해 검사하며, 이 stub을 실제 파일 검산 성공으로 해석하지 않는다.
    bound = deepcopy(reader.read_prebound_execution_measurement(
        run_spec_path=args["run_spec_path"],
        file_sha256=runner._file_sha256(args["run_spec_path"]),
        self_sha256=load(args["run_spec_path"])["run_spec_sha256"],
        pair_id=load(args["run_spec_path"])["pair_id"], arm="BEFORE"))
    bound["execution_policy"]["config_projection"]["runtime"].update(
        slang_mode="READ_ONLY", slang_snapshot_sha256="a" * 64)
    monkeypatch.setattr(builder, "read_prebound_execution_measurement", lambda **kwargs: bound)
    with pytest.raises(ValueError, match="requires Slang OFF"):
        builder.build_low_load_paired_plan(**args)
    assert not args["output_root"].exists()


def test_v1_v2_batch_versions_cannot_cross_runspec_revision(tmp_path, monkeypatch):
    args, _, _ = fixture(tmp_path, monkeypatch)
    run = builder.build_low_load_paired_plan(**args)["plan"]["planned_runs"][0]
    run["batch_completion_contract"]["schema_version"] = runner.BATCH_COMPLETION_SCHEMA
    env = run["batch_execution_envelope"]
    env["schema_version"] = runner.BATCH_ENVELOPE_SCHEMA
    env.pop("execution_policy_binding")
    env.pop("source_binding")
    with pytest.raises(ValueError, match="self/revision"):
        runner._validate_batch_run_spec(run, index=1, batch=run["batch_completion_contract"])


@pytest.mark.parametrize("extra", [{"OPENAI_API_KEY": "synthetic-secret"}, {"MCP_HEALTH_WORKERS": "16"},
                                  {"EXPERT_RUN_ID": "spoof"}])
def test_extra_environment_cannot_store_secrets_or_override_policy(tmp_path, monkeypatch, extra):
    args, _, _ = fixture(tmp_path, monkeypatch)
    with pytest.raises(ValueError):
        builder.build_low_load_paired_plan(**args, extra_environment=extra)
    assert not args["output_root"].exists()


def test_write_boundary_and_legacy_spec_are_explicit(tmp_path, monkeypatch):
    args, _, _ = fixture(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="namespace"):
        builder.build_low_load_paired_plan(**{**args, "output_root": tmp_path / "source" / "new"})
    spec = load(args["run_spec_path"])
    spec["schema_version"] = reader.RUN_SPEC_SCHEMA_VERSION
    save(args["run_spec_path"], spec)
    with pytest.raises(ValueError, match="explicit RunSpec v3"):
        builder.build_low_load_paired_plan(**args)


def test_cli_has_no_execute_switch_and_help_does_not_call_builder(monkeypatch, capsys):
    with patch.object(builder, "build_low_load_paired_plan", side_effect=AssertionError("builder invoked")):
        with pytest.raises(SystemExit) as done:
            builder.parse_args(["--help"])
    assert done.value.code == 0
    assert "실행하지 않습니다" in capsys.readouterr().out


def test_new_batch_indeterminate_attempt_is_not_reexecuted(tmp_path, monkeypatch):
    args, _, _ = fixture(tmp_path, monkeypatch)
    receipt = builder.build_low_load_paired_plan(**args)
    plan_path = Path(receipt["plan_path"])
    runner_fixture._materialize_indeterminate_started_attempt(plan_path)
    with patch("subprocess.Popen", side_effect=AssertionError("child forbidden")), \
            patch.object(runner, "_ensure_dashboard", side_effect=AssertionError("dashboard forbidden")), \
            pytest.raises(ValueError, match="INDETERMINATE"):
        runner.run_plan(plan_path=plan_path, log_dir=args["output_root"] / "logs",
            env_updates={}, skip_existing=True, limit=None, dashboard=True)


def test_missing_start_end_observation_cannot_be_adopted_as_complete(tmp_path, monkeypatch):
    args, _, _ = fixture(tmp_path, monkeypatch)
    run = builder.build_low_load_paired_plan(**args)["plan"]["planned_runs"][0]
    batch = run["batch_completion_contract"]
    env = run["required_env"]
    spec = load(args["run_spec_path"])
    bound = reader.read_prebound_execution_measurement(run_spec_path=args["run_spec_path"],
        file_sha256=env["PIPELINE_MEASUREMENT_RUN_SPEC_FILE_SHA256"], self_sha256=spec["run_spec_sha256"],
        pair_id=spec["pair_id"], arm="BEFORE")
    measurement = {**bound["expected_measurement_fields"], "pair_id": spec["pair_id"], "arm": "BEFORE",
        "run_spec_sha256": spec["run_spec_sha256"], "run_spec_file_binding": bound["run_spec_file_binding"]}
    source = load(args["source_manifest_path"])
    rows = load(source["output_file"])
    for row in rows:
        row["run_meta"].update(run_id=batch["planned_run_id"], decision_call_measurement=measurement)
    save(run["output_json"], rows)
    Path(run["checkpoint_jsonl"]).write_text("".join(json.dumps({"global_idx": index,
        "post_id": row["post_id"], "status": "completed", "result": row}) + "\n"
        for index, row in enumerate(rows, 1)), encoding="utf-8")
    claim = {"schema_version": "expert_output_attempt_claim_v1", "run_id": batch["planned_run_id"],
             "input_file": run["input_jsonl"], "output_file": run["output_json"],
             "decision_call_ledger_mode": "REQUIRED", "decision_call_ledger_path": run["decision_call_ledger_dir"],
             "decision_call_measurement": measurement, "pid": 1234}
    save(run["output_attempt_claim_json"], claim)
    source.update(run_id=batch["planned_run_id"], output_file=run["output_json"], checkpoint_jsonl=run["checkpoint_jsonl"],
        dashboard_standalone_forwarding=True, decision_call_measurement=measurement,
        decision_call_ledger_path=run["decision_call_ledger_dir"], output_attempt_claim=run["output_attempt_claim_json"],
        output_attempt_claim_sha256=runner._file_sha256(Path(run["output_attempt_claim_json"])))
    source.pop("paired_execution_observation")
    save(run["manifest_json"], source)
    with pytest.raises(ValueError, match="observation"):
        runner._validate_complete_batch_artifacts(run, index=1,
            paths=runner._run_artifact_paths(run, index=1), batch=batch)
