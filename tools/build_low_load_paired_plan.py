"""고정 RunSpec v3를 검산하여 새 폴더에 실행 계획만 저장한다. 실행 기능 없음."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = ROOT / "out"
for entry in (ROOT, ROOT / "src"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from llm_batch.measurement.paired_execution_policy import endpoint_pool_fingerprint
from llm_batch.measurement.paired_measurement_readback import read_prebound_execution_measurement
from tools import run_independent_plan as runner


def _path(value: str | Path, *, existing: bool = True) -> Path:
    path = Path(value).absolute()
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise ValueError("plan-only paths must not contain symlinks")
    path = path.resolve()
    if existing and not path.is_file():
        raise ValueError(f"plan-only source file missing: {path}")
    return path


def _reference(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return {"path": str(path), "sha256": runner._sha256_bytes(raw), "bytes": len(raw)}


def _environment(extra: Mapping[str, str] | None) -> dict[str, str]:
    result = dict(extra or {})
    if any(not isinstance(key, str) or not key or not isinstance(value, str) or
           any(secret in key.upper() for secret in ("API_KEY", "SECRET", "PASSWORD", "INGEST_TOKEN", "ACCESS_TOKEN"))
           for key, value in result.items()):
        raise ValueError("plan-only environment must contain explicit nonsecret string bindings")
    return result


def build_low_load_paired_plan(
    *, run_spec_path: str | Path, source_manifest_path: str | Path, input_path: str | Path,
    python_path: str | Path, output_root: str | Path, mcp_endpoints: Sequence[str],
    dashboard_url: str = runner.DEFAULT_DASHBOARD_URL,
    extra_environment: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """계획 파일만 exclusive 생성한다. health/서버/child/model 호출은 하지 않는다.

    실패 시 새 폴더의 부분 출력은 보존하며 기존 파일을 덮거나 자동 재시도하지 않는다.
    계획 검산 PASS는 실제 서비스 준비·모델 측정·실행 승인을 의미하지 않는다.
    """
    spec_path, source_path = _path(run_spec_path), _path(source_manifest_path)
    input_file, interpreter = _path(input_path), _path(python_path)
    destination = _path(output_root, existing=False)
    if destination == OUTPUT_ROOT.resolve() or not destination.is_relative_to(OUTPUT_ROOT.resolve()):
        raise ValueError("plan-only output must be a new namespace below the repository out directory")
    if os.path.lexists(destination):
        raise FileExistsError(f"plan-only output already exists: {destination}")
    spec = runner._load_json(spec_path)
    if spec.get("schema_version") not in (runner.LOW_LOAD_RUN_SPEC_SCHEMA, runner.PARALLEL12_RUN_SPEC_SCHEMA):
        raise ValueError("plan-only generator requires explicit RunSpec v3/v4")
    spec_ref = _reference(spec_path)
    bound = read_prebound_execution_measurement(run_spec_path=spec_path,
        file_sha256=spec_ref["sha256"], self_sha256=spec["run_spec_sha256"], pair_id=spec["pair_id"], arm="BEFORE")
    policy = bound["execution_policy"]
    runtime = policy["config_projection"]["runtime"]
    if runtime["slang_mode"] != "OFF":
        raise ValueError("plan-only expert_main v3/v4 currently requires Slang OFF")
    endpoints = list(mcp_endpoints)
    if endpoint_pool_fingerprint(endpoints) != runtime["mcp_endpoint_pool_sha256"]:
        raise ValueError("plan-only MCP endpoint pool differs from frozen policy")
    dashboard_url = dashboard_url.rstrip("/")
    dashboard = urlsplit(dashboard_url)
    if dashboard.scheme != "http" or dashboard.hostname not in {"127.0.0.1", "localhost", "::1"} or dashboard.username or dashboard.password or dashboard.query or dashboard.fragment or dashboard.path:
        raise ValueError("plan-only dashboard must use an explicit local HTTP origin")
    source = runner._load_json(source_path)
    wal_path = Path(str(source.get("publication_commit_journal", "")))
    wal_path = _path(wal_path if wal_path.is_absolute() else source_path.parent / wal_path)
    source_binding = {"schema_version": runner.LOW_LOAD_SOURCE_BINDING_SCHEMA,
        "input": _reference(input_file), "source_manifest": _reference(source_path),
        "publication_wal": _reference(wal_path)}
    fixed = {
        "EXPERT_DASHBOARD_FORWARD": "1", "DASHBOARD_URL": dashboard_url,
        "DASHBOARD_PORT": str(dashboard.port or 80), "PYTHONDONTWRITEBYTECODE": "1",
        "PIPELINE_DECISION_CALL_LEDGER_MODE": "REQUIRED",
        "PIPELINE_MEASUREMENT_RUN_SPEC_PATH": str(spec_path),
        "PIPELINE_MEASUREMENT_RUN_SPEC_FILE_SHA256": spec_ref["sha256"],
        "PIPELINE_MEASUREMENT_RUN_SPEC_SHA256": spec["run_spec_sha256"],
        "PIPELINE_MEASUREMENT_PAIR_ID": spec["pair_id"],
        "PIPELINE_MEASUREMENT_EXECUTION_MODE": "FRESH_EXECUTION_REQUIRED",
        "PIPELINE_MEASUREMENT_MUTABLE_CONTEXT_MODE": "FROZEN_OFF",
        "PIPELINE_MEASUREMENT_EARLY_ROUTE_MODE": "SOURCE_ONLY_V1",
        "PIPELINE_SLANG_DB": "0",
        "MCP_ENDPOINTS": ",".join(endpoints), "MCP_ENDPOINTS_AUTOGEN": "0",
        "MCP_AUTO_UP_SHARDS": "0", "MCP_AUTO_RECREATE_SHARDS": "0",
        "MCP_AUTO_SCALE_UP_MISSING_SHARDS": "0", "MCP_CLIENT_ENDPOINT_FAILOVER": "0",
        "MCP_HEALTH_INCLUDE_SEARCH": "1", "MCP_HEALTH_LIGHT_MODE": "0",
        "MCP_HEALTH_REQUIRED_OK": "1", "MCP_HEALTH_PROBE_BATCH_SIZE": "1", "MCP_HEALTH_WORKERS": "1",
        "LLM_ENDPOINT": runtime["llm_endpoint"], "LLM_MODEL": runtime["llm_model"],
        "RECOVERY_ACTIVATION_MODE": "OFF", **{key: "1" for key in runner._NUMERIC_THREAD_KEYS},
    }
    shared_env = _environment(extra_environment)
    if any(key in shared_env and shared_env[key] != value for key, value in fixed.items()) or any(
            key in shared_env for key in ("EXPERT_RUN_ID", "PIPELINE_MEASUREMENT_ARM")):
        raise ValueError("plan-only extra environment overrides a frozen policy/arm binding")
    shared_env.update(fixed)
    shared_env.setdefault("LLM_SERVER_TYPE", "vllm")
    if shared_env["LLM_SERVER_TYPE"] not in {"llama", "vllm"}:
        raise ValueError("plan-only server type must be llama or vllm")
    parallel12 = spec["schema_version"] == runner.PARALLEL12_RUN_SPEC_SCHEMA
    now = datetime.now(timezone.utc)
    runs = []
    for offset, arm in enumerate(("BEFORE", "AFTER")):
        run_id = (now + timedelta(microseconds=offset)).strftime("%Y%m%d_%H%M%S_%f")
        output = destination / (arm.lower() + ".json")
        env = {**shared_env, "EXPERT_RUN_ID": run_id, "PIPELINE_MEASUREMENT_ARM": arm}
        run = {"input_jsonl": str(input_file), "input_sha256": source_binding["input"]["sha256"],
            "output_json": str(output), "checkpoint_jsonl": str(output.with_name(output.stem + "_checkpoint.jsonl")),
            "manifest_json": str(output.with_name(output.stem + "_manifest.json")),
            "output_attempt_claim_json": str(output.with_name(output.stem + "_attempt_claim.json")),
            "decision_call_ledger_dir": str(output.with_name(output.stem + "_decision_call_ledger")),
            "required_env": env,
            "batch_completion_contract": {"schema_version": runner.PARALLEL12_BATCH_COMPLETION_SCHEMA if parallel12 else runner.LOW_LOAD_BATCH_COMPLETION_SCHEMA,
                "batch_id": "low-load:" + spec["pair_id"], "pair_id": spec["pair_id"], "arm": arm,
                "planned_run_id": run_id, "input_post_count": spec["input_post_count"],
                "ordered_post_ids": spec["ordered_post_ids"]}}
        run["command_argv"] = runner._low_load_command_argv(python_path=str(interpreter), input_path=str(input_file),
            output_path=str(output), policy=policy, environment=env)
        run["batch_execution_envelope"] = {"schema_version": runner.PARALLEL12_BATCH_ENVELOPE_SCHEMA if parallel12 else runner.LOW_LOAD_BATCH_ENVELOPE_SCHEMA,
            "effective_argv_sha256": runner._canonical_sha256(run["command_argv"]),
            "environment_binding": dict(env), "environment_sha256": runner._canonical_sha256(env),
            "execution_policy_binding": dict(bound["execution_policy_binding"]), "source_binding": source_binding}
        runs.append(run)
    plan = {"manifest_type": "low-load-paired-plan-only-v1", "execution_mode": "PLAN_ONLY",
            "actual_model_runs_started": 0, "service_health_checked": False,
            "planned_runs": runs, "approval_boundary": {"model_execution_approval": "NOT_PROVIDED_BY_PLAN",
                "production_enable_allowed": False, "full_scan_approval": False, "formal_kpi": "NOT_ESTIMABLE"}}
    plan["plan_self_binding"] = {"version": "independent-explicit-batch-plan-self-binding-v2",
        "algorithm": "sha256", "canonicalization": "json-sort-keys-compact-utf8",
        "excluded_field": "plan_self_binding", "canonical_sha256": runner._canonical_sha256(plan)}
    runner._validate_plan_self_binding(plan)
    runner._validate_batch_plan(plan, runs)
    runner._planned_runtime_path_entries(runs)
    if _reference(spec_path) != spec_ref:
        raise ValueError("RunSpec changed during plan-only generation")
    destination.mkdir(parents=True, exist_ok=False)
    plan_path = destination / "plan.json"
    runner._write_json_exclusive(plan_path, plan)
    readback = runner._load_json(plan_path)
    if readback != plan:
        raise ValueError("exclusive plan JSON readback mismatch")
    runner._validate_plan_self_binding(readback)
    runner._validate_batch_plan(readback, readback["planned_runs"])
    encoded = (json.dumps(plan, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if plan_path.read_bytes() != encoded:
        raise ValueError("exclusive plan byte readback mismatch")
    return {"status": "PLAN_ONLY_VERIFIED", "plan_path": str(plan_path),
            "plan_sha256": runner._file_sha256(plan_path), "plan": plan,
            "model_calls": 0, "child_processes_started": 0, "service_health_checked": False}


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="RunSpec v3/v4의 저부하 paired 계획 파일만 생성합니다. 실행하지 않습니다.")
    for name in ("run-spec", "source-manifest", "input", "python", "output-root"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--mcp-endpoint", action="append", required=True)
    parser.add_argument("--dashboard-url", default=runner.DEFAULT_DASHBOARD_URL)
    parser.add_argument("--environment-json", type=Path, help="비밀값 없는 명시 환경 JSON 객체")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    result = build_low_load_paired_plan(run_spec_path=args.run_spec, source_manifest_path=args.source_manifest,
        input_path=args.input, python_path=args.python, output_root=args.output_root, mcp_endpoints=args.mcp_endpoint,
        dashboard_url=args.dashboard_url,
        extra_environment=runner._load_json(args.environment_json) if args.environment_json else None)
    print(json.dumps({key: value for key, value in result.items() if key != "plan"}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
