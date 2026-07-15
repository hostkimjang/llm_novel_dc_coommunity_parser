from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import stat
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.merge_interrupted_run_results import (
    PRODUCTION_BASELINE_PATH,
    PRODUCTION_BASELINE_SHA256,
    PRODUCTION_GOLDEN_PATH,
    PRODUCTION_GOLDEN_SHA256,
    PRODUCTION_PANEL_PATH,
    PRODUCTION_PANEL_SHA256,
    TRUST_ANCHOR_REPORT_TYPE,
    TRUST_ANCHOR_VERSION,
    _arg_value,
    _canonical_hash,
    _index,
    _load_json,
    _load_jsonl,
    _manifest_signature,
    _object_rows,
    _plan_signature,
    _post_id,
    _sha256,
    _uniform_row_signature,
    _uniform_row_value,
    _validate_plan_manifest_binding,
    _validate_row_manifest_binding,
    runtime_code_tree_projection,
)


def _require_sha256(value: str, label: str) -> str:
    text = str(value or "").strip().lower()
    if len(text) != 64 or any(char not in "0123456789abcdef" for char in text):
        raise ValueError(f"{label} must be a sha256")
    return text


def _rows_from_json_or_jsonl(path: Path, label: str) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".jsonl":
        return _load_jsonl(path)
    return _object_rows(_load_json(path), label)


def _fixed_artifact(
    *,
    path: Path,
    rows: list[dict[str, Any]] | None,
    expected_sha256: str,
) -> dict[str, Any]:
    actual_sha256 = _sha256(path)
    if actual_sha256 != _require_sha256(expected_sha256, str(path)):
        raise ValueError(f"fixed artifact sha256 mismatch: {path}")
    payload: dict[str, Any] = {
        "path": str(path.resolve()),
        "sha256": actual_sha256,
    }
    if rows is not None:
        post_ids = [_post_id(row) for row in rows]
        if len(set(post_ids)) != len(post_ids):
            raise ValueError(f"fixed artifact duplicate post_id: {path}")
        payload.update(
            {
                "row_count": len(rows),
                "post_id_order_sha256": _canonical_hash(post_ids),
                "post_id_set_sha256": _canonical_hash(sorted(post_ids)),
            }
        )
    return payload


def _immutable_json_artifact(
    *,
    path: Path,
    payload: Any,
) -> dict[str, Any]:
    """Bind both the exact file bytes and the parsed canonical payload."""
    return {
        "path": str(path.resolve()),
        "byte_sha256": _sha256(path),
        "canonical_sha256": _canonical_hash(payload),
        "size_bytes": path.stat().st_size,
    }


def _row_artifact(
    *,
    path: Path,
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    post_ids = [_post_id(row) for row in rows]
    if len(set(post_ids)) != len(post_ids):
        raise ValueError(f"row artifact duplicate post_id: {path}")
    return {
        **_immutable_json_artifact(path=path, payload=rows),
        "row_count": len(rows),
        "post_id_order_sha256": _canonical_hash(post_ids),
        "post_id_set_sha256": _canonical_hash(sorted(post_ids)),
    }


FRESH375_RUN_START_SCHEMA_VERSION = "fresh375-run-start-binding-v2"
FRESH375_START_EVENT_SCHEMA_VERSION = "fresh375-supervisor-start-event-v2"
FRESH375_SNAPSHOT_SCHEMA_VERSION = "fresh375-first-durable-snapshot-v2"
FRESH375_FINAL_CONTINUITY_SCHEMA_VERSION = "fresh375-final-continuity-v2"
FRESH375_BINDING_TOKEN_ENV = "FRESH375_RUN_BINDING_TOKEN"
FRESH375_BINDING_TOKEN_MANIFEST_FIELD = "fresh375_run_binding_token"
FRESH375_BINDING_TOKEN_ROW_FIELD = "fresh375_run_binding_token"
WINDOWS_CREATE_SUSPENDED = 0x00000004
WINDOWS_CREATE_NO_WINDOW = 0x08000000
# expert_main serializes the supervisor token into every row run_meta and every
# manifest write. The supervisor still verifies the exact echo before resume
# artifacts can become trusted evidence.
FRESH375_RUNTIME_BINDING_ECHO_IMPLEMENTED = True
FRESH375_WINDOWS_OS_ENV_ALLOWLIST = (
    "ALLUSERSPROFILE",
    "APPDATA",
    "COMSPEC",
    "HOMEDRIVE",
    "HOMEPATH",
    "LOCALAPPDATA",
    "NUMBER_OF_PROCESSORS",
    "OS",
    "PATH",
    "PATHEXT",
    "PROCESSOR_ARCHITECTURE",
    "PROGRAMDATA",
    "SYSTEMDRIVE",
    "SYSTEMROOT",
    "TEMP",
    "TMP",
    "USERPROFILE",
    "WINDIR",
)


def _clean_mapping(raw: Any, label: str) -> dict[str, str]:
    if raw in (None, ""):
        return {}
    if not isinstance(raw, dict):
        raise ValueError(f"{label} must be an object")
    output: dict[str, str] = {}
    for key, value in raw.items():
        text = str(key or "").strip()
        if not text:
            raise ValueError(f"{label} contains an empty key")
        output[text] = str(value)
    return output


def _resolve_from_root(path_value: str | Path, root: Path) -> Path:
    path = Path(path_value)
    if not path.is_absolute():
        path = root / path
    return path.resolve()


def _manifest_path_for_output(output: Path) -> Path:
    return output.with_name(f"{output.stem}_manifest.json")


def _checkpoint_path_for_output(output: Path) -> Path:
    return output.with_name(f"{output.stem}_checkpoint.jsonl")


def _pending_path_for_output(output: Path) -> Path:
    return output.with_name(f"{output.stem}_pending_snapshot.json")


def _binding_token_commitment(token: str) -> str:
    text = str(token or "").strip()
    if len(text) != 64 or any(char not in "0123456789abcdef" for char in text.lower()):
        raise ValueError("fresh375 binding token must be 32 random bytes in hex")
    return _canonical_hash(
        {"name": FRESH375_BINDING_TOKEN_ENV, "value": text.lower()}
    )


def _environment_binding(values: dict[str, str]) -> dict[str, Any]:
    normalized = {str(key).upper(): str(value) for key, value in values.items()}
    ordered = {key: normalized[key] for key in sorted(normalized)}
    return {
        "names": list(ordered),
        "value_sha256": {
            key: _canonical_hash({"name": key, "value": value})
            for key, value in ordered.items()
        },
        "block_sha256": _canonical_hash(ordered),
        "variable_count": len(ordered),
        "values_redacted": True,
    }


def build_fresh375_child_environment(
    *,
    anchored_runtime_env: dict[str, str],
    source_environment: dict[str, str] | None = None,
    binding_token: str | None = None,
) -> tuple[dict[str, str], dict[str, Any]]:
    """Build a minimal exact Windows child env; never inherit os.environ wholesale."""
    raw_source = dict(os.environ if source_environment is None else source_environment)
    source_by_upper = {str(key).upper(): str(value) for key, value in raw_source.items()}
    child = {
        name: source_by_upper[name]
        for name in FRESH375_WINDOWS_OS_ENV_ALLOWLIST
        if name in source_by_upper
    }
    runtime = {str(key).upper(): str(value) for key, value in anchored_runtime_env.items()}
    if FRESH375_BINDING_TOKEN_ENV in runtime:
        raise ValueError("fresh375 plan cannot predefine the dynamic binding token")
    child.update(runtime)
    if binding_token is not None:
        _binding_token_commitment(binding_token)
        child[FRESH375_BINDING_TOKEN_ENV] = binding_token.lower()
    return child, _environment_binding(child)


def _validate_fresh375_binding_token_echo(
    *,
    rows: list[dict[str, Any]],
    manifest: dict[str, Any],
    expected_commitment: str,
    label: str,
) -> str:
    manifest_token = str(
        manifest.get(FRESH375_BINDING_TOKEN_MANIFEST_FIELD) or ""
    ).strip().lower()
    if not manifest_token:
        raise ValueError(f"{label} manifest binding-token echo missing")
    if _binding_token_commitment(manifest_token) != expected_commitment:
        raise ValueError(f"{label} manifest binding-token echo mismatch")
    for index, row in enumerate(rows, start=1):
        run_meta = row.get("run_meta")
        row_token = str(
            run_meta.get(FRESH375_BINDING_TOKEN_ROW_FIELD)
            if isinstance(run_meta, dict)
            else ""
        ).strip().lower()
        if row_token != manifest_token:
            raise ValueError(f"{label} row {index} binding-token echo mismatch")
    return manifest_token


def _validate_fresh375_final_checkpoint(
    *,
    checkpoint_rows: list[dict[str, Any]],
    final_rows: list[dict[str, Any]],
    source_rows: list[dict[str, Any]],
) -> None:
    expected_count = len(source_rows)
    if len(checkpoint_rows) != expected_count:
        raise ValueError("fresh375 final checkpoint row count mismatch")
    by_index: dict[int, dict[str, Any]] = {}
    for entry in checkpoint_rows:
        global_idx = entry.get("global_idx")
        if (
            isinstance(global_idx, bool)
            or not isinstance(global_idx, int)
            or global_idx in by_index
        ):
            raise ValueError("fresh375 final checkpoint index is invalid or duplicate")
        by_index[global_idx] = entry
    if sorted(by_index) != list(range(1, expected_count + 1)):
        raise ValueError("fresh375 final checkpoint coverage is incomplete")
    for global_idx in range(1, expected_count + 1):
        entry = by_index[global_idx]
        expected_post_id = _post_id(source_rows[global_idx - 1])
        if (
            entry.get("status") != "completed"
            or _post_id(entry) != expected_post_id
            or entry.get("result") != final_rows[global_idx - 1]
        ):
            raise ValueError("fresh375 final checkpoint/result/source binding mismatch")


def _resolve_planned_executable(
    value: str,
    *,
    runtime_root: Path,
    child_environment: dict[str, str],
) -> Path:
    candidate = Path(value)
    if candidate.is_absolute():
        resolved = candidate.resolve()
    elif candidate.parent != Path("."):
        resolved = (runtime_root / candidate).resolve()
    else:
        found = shutil.which(value, path=child_environment.get("PATH"))
        if not found:
            raise ValueError(f"fresh375 planned executable cannot be resolved: {value}")
        resolved = Path(found).resolve()
    if not resolved.is_file():
        raise ValueError(f"fresh375 planned executable is not a file: {resolved}")
    return resolved


def validate_fresh375_supervisor_output_preflight(
    *,
    immutable_input_paths: list[Path],
    execution_contract: dict[str, Any],
    live_result_path: Path,
    live_manifest_path: Path,
    live_checkpoint_path: Path,
    live_pending_path: Path,
    supervisor_start_event_path: Path,
    snapshot_result_path: Path,
    snapshot_manifest_path: Path,
    receipt_path: Path,
    final_verification_path: Path,
    stdout_log_path: Path,
    stderr_log_path: Path,
) -> list[Path]:
    output_paths = [
        supervisor_start_event_path,
        live_result_path,
        live_manifest_path,
        live_checkpoint_path,
        live_pending_path,
        snapshot_result_path,
        snapshot_manifest_path,
        receipt_path,
        final_verification_path,
        stdout_log_path,
        stderr_log_path,
    ]
    resolved_outputs = [path.resolve() for path in output_paths]
    if len(set(resolved_outputs)) != len(resolved_outputs):
        raise ValueError("fresh375 supervisor output/log canonical paths collide")
    resolved_inputs = {path.resolve() for path in immutable_input_paths}
    if resolved_inputs.intersection(resolved_outputs):
        raise ValueError("fresh375 supervisor output/log path aliases an immutable input")
    expected_live = {
        live_result_path.resolve(): Path(execution_contract["output_path"]).resolve(),
        live_manifest_path.resolve(): Path(execution_contract["manifest_path"]).resolve(),
        live_checkpoint_path.resolve(): Path(
            execution_contract["checkpoint_path"]
        ).resolve(),
        live_pending_path.resolve(): Path(execution_contract["pending_path"]).resolve(),
    }
    if any(actual != expected for actual, expected in expected_live.items()):
        raise ValueError("fresh375 supervisor live paths differ from anchored plan")
    collisions = [path for path in output_paths if path.exists()]
    if collisions:
        raise FileExistsError(
            f"fresh375 supervisor pre-dispatch output collision: "
            f"{[str(path) for path in collisions]}"
        )
    return resolved_outputs


def fresh375_plan_execution_contract(
    *,
    fresh_plan: dict[str, Any],
    fresh_plan_path: Path,
    source_jsonl: Path,
    runtime_root: Path,
    dashboard_url: str = "http://127.0.0.1:8080",
    source_environment: dict[str, str] | None = None,
) -> dict[str, Any]:
    plan_payload = {key: value for key, value in fresh_plan.items() if key != "plan_path"}
    if _load_json(fresh_plan_path) != plan_payload:
        raise ValueError("fresh375 plan parsed payload/path mismatch")
    runs = plan_payload.get("planned_runs")
    if not isinstance(runs, list) or len(runs) != 1 or not isinstance(runs[0], dict):
        raise ValueError("fresh375 plan must contain exactly one planned run")
    run = runs[0]
    argv = run.get("command_argv")
    if not isinstance(argv, list) or not argv or not all(isinstance(item, str) for item in argv):
        raise ValueError("fresh375 plan command_argv is invalid")
    if "--no-dashboard" in argv:
        raise ValueError("fresh375 plan cannot disable dashboard")
    expert_indexes = [
        index for index, value in enumerate(argv) if Path(value).name == "expert_main.py"
    ]
    if len(expert_indexes) != 1 or expert_indexes[0] + 1 >= len(argv):
        raise ValueError("fresh375 plan must invoke expert_main.py with one input")
    input_path = _resolve_from_root(argv[expert_indexes[0] + 1], runtime_root)
    if input_path != source_jsonl.resolve():
        raise ValueError("fresh375 plan input path does not match source panel")
    output_value = _arg_value(argv, "--output")
    if not output_value:
        raise ValueError("fresh375 plan command is missing --output")
    output_path = _resolve_from_root(output_value, runtime_root)
    declared_output = str(run.get("output_json") or "").strip()
    if not declared_output or _resolve_from_root(declared_output, runtime_root) != output_path:
        raise ValueError("fresh375 plan output_json/command output mismatch")
    expected_manifest_path = _manifest_path_for_output(output_path)
    declared_manifest = str(run.get("manifest_json") or "").strip()
    if declared_manifest and _resolve_from_root(declared_manifest, runtime_root) != expected_manifest_path:
        raise ValueError("fresh375 plan manifest_json/output mismatch")

    plan_required = _clean_mapping(plan_payload.get("required_env"), "required_env")
    plan_overrides = _clean_mapping(plan_payload.get("env_overrides"), "env_overrides")
    runtime_contract = plan_payload.get("runtime_contract")
    if not isinstance(runtime_contract, dict):
        raise ValueError("fresh375 plan runtime_contract missing")
    runtime_required = _clean_mapping(
        runtime_contract.get("required_env"), "runtime_contract.required_env"
    )
    run_required = _clean_mapping(run.get("required_env"), "planned_run.required_env")
    run_overrides = _clean_mapping(run.get("env_overrides"), "planned_run.env_overrides")
    if plan_required != runtime_required or plan_required != run_required:
        raise ValueError("fresh375 required_env sources disagree")
    effective_env: dict[str, str] = {}
    for mapping in (
        plan_required,
        plan_overrides,
        runtime_required,
        run_required,
        run_overrides,
    ):
        effective_env.update(mapping)
    effective_env.setdefault("PYTHONIOENCODING", "utf-8")
    effective_env.setdefault("LLM_SUSPEND_ON_SERVER_ANOMALY", "0")
    effective_env.setdefault("LLM_SUSPEND_FAILURE_THRESHOLD", "0")
    effective_env.setdefault("LLM_STREAM_FIRST_TOKEN_TIMEOUT_SECONDS", "45")
    effective_env.setdefault("LLM_STREAM_IDLE_TIMEOUT_SECONDS", "45")
    effective_env["DASHBOARD_URL"] = dashboard_url.rstrip("/")
    effective_env["DASHBOARD_PORT"] = str(
        int(dashboard_url.rstrip("/").rsplit(":", 1)[-1])
    )
    effective_env["EXPERT_DASHBOARD_FORWARD"] = "1"
    required_echo_contract = {
        "required": True,
        "environment_name": FRESH375_BINDING_TOKEN_ENV,
        "manifest_field": FRESH375_BINDING_TOKEN_MANIFEST_FIELD,
        "row_run_meta_field": FRESH375_BINDING_TOKEN_ROW_FIELD,
        "echo_scope": "manifest_and_every_result_row",
    }
    if runtime_contract.get("fresh375_binding_echo") != required_echo_contract:
        raise ValueError(
            "fresh375 plan runtime_contract lacks the required binding-token echo contract"
        )
    child_environment, child_environment_binding = build_fresh375_child_environment(
        anchored_runtime_env=effective_env,
        source_environment=source_environment,
    )
    executable = _resolve_planned_executable(
        argv[0],
        runtime_root=runtime_root,
        child_environment=child_environment,
    )
    resolved_command = [str(executable), *argv[1:]]
    return {
        "plan_signature": _plan_signature(fresh_plan, "fresh375"),
        "command_argv": list(argv),
        "command_argv_sha256": _canonical_hash(argv),
        "resolved_command_argv": resolved_command,
        "resolved_command_argv_sha256": _canonical_hash(resolved_command),
        "executable": {
            "path": str(executable),
            "byte_sha256": _sha256(executable),
            "size_bytes": executable.stat().st_size,
        },
        "cwd": str(runtime_root.resolve()),
        "input_path": str(input_path),
        "output_path": str(output_path),
        "manifest_path": str(expected_manifest_path),
        "checkpoint_path": str(_checkpoint_path_for_output(output_path)),
        "pending_path": str(_pending_path_for_output(output_path)),
        "required_env": plan_required,
        "env_overrides": {
            "plan": plan_overrides,
            "run": run_overrides,
        },
        "effective_env": effective_env,
        "effective_env_sha256": _canonical_hash(effective_env),
        "child_environment_without_binding_token": child_environment_binding,
        "child_environment_policy": {
            "os_allowlist": list(FRESH375_WINDOWS_OS_ENV_ALLOWLIST),
            "wholesale_environment_inheritance_forbidden": True,
            "unplanned_semantic_environment_removed": True,
            "dynamic_binding_token_added_only_by_supervisor": True,
        },
        "binding_echo_contract": required_echo_contract,
        "runtime_contract": runtime_contract,
    }


def _validate_production_roots(
    *,
    source_jsonl: Path,
    baseline_result: Path,
    golden_manifest: Path,
    expected_source_count: int,
    expected_golden_count: int,
    expected_panel_sha256: str,
    expected_baseline_sha256: str,
    expected_golden_sha256: str,
    allow_untrusted_test_roots: bool,
) -> None:
    if allow_untrusted_test_roots:
        return
    if expected_source_count != 375 or expected_golden_count != 18:
        raise ValueError("production trust anchor scope must be 375/18")
    expected_paths = {
        source_jsonl.resolve(): PRODUCTION_PANEL_PATH,
        baseline_result.resolve(): PRODUCTION_BASELINE_PATH,
        golden_manifest.resolve(): PRODUCTION_GOLDEN_PATH,
    }
    if any(actual != expected for actual, expected in expected_paths.items()):
        raise ValueError("production trust anchor canonical artifact path mismatch")
    expected_hashes = {
        _require_sha256(expected_panel_sha256, "panel"): PRODUCTION_PANEL_SHA256,
        _require_sha256(expected_baseline_sha256, "baseline"): PRODUCTION_BASELINE_SHA256,
        _require_sha256(expected_golden_sha256, "golden"): PRODUCTION_GOLDEN_SHA256,
    }
    if any(actual != expected for actual, expected in expected_hashes.items()):
        raise ValueError("production trust anchor fixed sha256 mismatch")


def build_trust_anchor(
    *,
    source_rows: list[dict[str, Any]],
    baseline_rows: list[dict[str, Any]],
    golden_rows: list[dict[str, Any]],
    recovered_rows: list[dict[str, Any]],
    source_checkpoint_rows: list[dict[str, Any]],
    recovery_summary: dict[str, Any],
    source_manifest: dict[str, Any],
    source_plan: dict[str, Any],
    residual_partial_rows: list[dict[str, Any]],
    residual_input_rows: list[dict[str, Any]],
    residual_manifest: dict[str, Any],
    residual_plan: dict[str, Any],
    source_jsonl: Path,
    recovered_result_path: Path,
    recovery_summary_path: Path,
    source_checkpoint_path: Path,
    source_manifest_path: Path,
    source_plan_path: Path,
    residual_input_path: Path,
    residual_plan_path: Path,
    baseline_result: Path,
    golden_manifest: Path,
    runtime_root: Path,
    expected_source_run_id: str,
    expected_residual_run_id: str,
    expected_source_count: int,
    expected_recovered_count: int,
    expected_residual_count: int,
    expected_source_flushed_count: int,
    expected_source_pending_count: int,
    expected_golden_count: int,
    expected_panel_sha256: str,
    expected_baseline_sha256: str,
    expected_golden_sha256: str,
    generated_at: str | None = None,
    allow_untrusted_test_roots: bool = False,
) -> dict[str, Any]:
    _validate_production_roots(
        source_jsonl=source_jsonl,
        baseline_result=baseline_result,
        golden_manifest=golden_manifest,
        expected_source_count=expected_source_count,
        expected_golden_count=expected_golden_count,
        expected_panel_sha256=expected_panel_sha256,
        expected_baseline_sha256=expected_baseline_sha256,
        expected_golden_sha256=expected_golden_sha256,
        allow_untrusted_test_roots=allow_untrusted_test_roots,
    )
    if len(source_rows) != expected_source_count:
        raise ValueError("source row count mismatch")
    if len(baseline_rows) != expected_source_count:
        raise ValueError("baseline row count mismatch")
    if len(recovered_rows) != expected_recovered_count:
        raise ValueError("recovered row count mismatch")
    if len(golden_rows) != expected_golden_count:
        raise ValueError("golden row count mismatch")
    if not residual_partial_rows:
        raise ValueError("residual partial result must contain at least one completed row")
    if len(residual_partial_rows) > expected_residual_count:
        raise ValueError("residual partial result exceeds expected residual count")

    source_ids = [_post_id(row) for row in source_rows]
    baseline_ids = [_post_id(row) for row in baseline_rows]
    if source_ids != baseline_ids:
        raise ValueError("source/baseline post_id order mismatch")
    source_id_set = set(source_ids)
    recovered_by_id = _index(recovered_rows, "recovered result")
    residual_partial_by_id = _index(residual_partial_rows, "residual partial result")
    if not set(recovered_by_id).issubset(source_id_set):
        raise ValueError("recovered rows are outside source panel")
    if not set(residual_partial_by_id).issubset(source_id_set - set(recovered_by_id)):
        raise ValueError("residual partial rows are outside residual partition")

    checkpoint_completed = [
        row for row in source_checkpoint_rows if row.get("status") == "completed"
    ]
    checkpoint_failed = [
        row for row in source_checkpoint_rows if row.get("status") == "failed"
    ]
    if len(checkpoint_completed) != expected_recovered_count or checkpoint_failed:
        raise ValueError("source checkpoint completed/failed count mismatch")
    if len(checkpoint_completed) != len(source_checkpoint_rows):
        raise ValueError("source checkpoint contains an unsupported status")
    checkpoint_completed_sorted = sorted(
        checkpoint_completed,
        key=lambda row: int(row.get("global_idx") or 0),
    )
    checkpoint_results: list[dict[str, Any]] = []
    checkpoint_indexes: list[int] = []
    for checkpoint_row in checkpoint_completed_sorted:
        result = checkpoint_row.get("result")
        if not isinstance(result, dict):
            raise ValueError("source checkpoint completed row is missing result")
        global_idx = checkpoint_row.get("global_idx")
        if isinstance(global_idx, bool) or not isinstance(global_idx, int):
            raise ValueError("source checkpoint global_idx must be an integer")
        checkpoint_post_id = _post_id(checkpoint_row)
        if _post_id(result) != checkpoint_post_id:
            raise ValueError("source checkpoint wrapper/result post_id mismatch")
        if global_idx < 1 or global_idx > len(source_rows):
            raise ValueError("source checkpoint global_idx is outside source panel")
        if _post_id(source_rows[global_idx - 1]) != checkpoint_post_id:
            raise ValueError("source checkpoint global_idx/source panel mismatch")
        checkpoint_indexes.append(global_idx)
        checkpoint_results.append(result)
    if len(set(checkpoint_indexes)) != len(checkpoint_indexes):
        raise ValueError("source checkpoint duplicate global_idx")
    if checkpoint_results != recovered_rows:
        raise ValueError("recovered result is not the canonical source-order checkpoint subset")

    expected_residual_ids = [
        post_id for post_id in source_ids if post_id not in recovered_by_id
    ]
    residual_input_ids = [_post_id(row) for row in residual_input_rows]
    if len(residual_input_rows) != expected_residual_count:
        raise ValueError("residual input row count mismatch")
    if residual_input_ids != expected_residual_ids:
        raise ValueError("residual input is not the exact original-order complement")
    overlap_ids = sorted(set(recovered_by_id) & set(residual_input_ids))
    missing_ids = sorted(source_id_set - set(recovered_by_id) - set(residual_input_ids))
    extra_ids = sorted((set(recovered_by_id) | set(residual_input_ids)) - source_id_set)
    if overlap_ids or missing_ids or extra_ids:
        raise ValueError(
            f"partition mismatch overlap={overlap_ids} missing={missing_ids} extra={extra_ids}"
        )
    golden_ids = [_post_id(row) for row in golden_rows]
    if len(set(golden_ids)) != len(golden_ids) or not set(golden_ids).issubset(source_id_set):
        raise ValueError("golden rows are not a unique source-panel subset")

    if source_manifest.get("run_id") != expected_source_run_id:
        raise ValueError("source manifest run_id mismatch")
    if residual_manifest.get("run_id") != expected_residual_run_id:
        raise ValueError("residual manifest run_id mismatch")
    if recovery_summary.get("run_id") != expected_source_run_id:
        raise ValueError("recovery summary run_id mismatch")
    if recovery_summary.get("recovery_safe_to_use_as_completed_subset") is not True:
        raise ValueError("recovery summary does not mark the subset safe")
    if int(recovery_summary.get("recovered_rows") or 0) != expected_recovered_count:
        raise ValueError("recovery summary recovered count mismatch")
    source_expected_counts = {
        "input_post_count": expected_source_count,
        "completed_count": expected_recovered_count,
        "flushed_count": expected_source_flushed_count,
        "pending_count": expected_source_pending_count,
        "failed_count": 0,
    }
    for field, expected in source_expected_counts.items():
        if source_manifest.get(field) != expected:
            raise ValueError(f"source interrupted manifest {field} mismatch")
    if expected_source_flushed_count + expected_source_pending_count != expected_recovered_count:
        raise ValueError("source interrupted flushed+pending does not equal recovered count")
    if source_manifest.get("large_run_complete") is not False:
        raise ValueError("source interrupted manifest must be incomplete")
    recovery_manifest = recovery_summary.get("manifest")
    if not isinstance(recovery_manifest, dict):
        raise ValueError("recovery summary manifest snapshot missing")
    for field, expected in source_expected_counts.items():
        if recovery_manifest.get(field) != expected:
            raise ValueError(f"recovery summary manifest {field} mismatch")

    residual_completed = residual_manifest.get("completed_count")
    residual_flushed = residual_manifest.get("flushed_count")
    residual_pending = residual_manifest.get("pending_count")
    residual_failed = residual_manifest.get("failed_count")
    if residual_manifest.get("input_post_count") != expected_residual_count:
        raise ValueError("residual partial input count mismatch")
    if any(isinstance(value, bool) or not isinstance(value, int) for value in (
        residual_completed,
        residual_flushed,
        residual_pending,
        residual_failed,
    )):
        raise ValueError("residual partial counts must be integers")
    if not (0 < residual_completed < expected_residual_count):
        raise ValueError("residual manifest is not a pre-completion partial run")
    if residual_flushed <= 0 or residual_flushed > residual_completed:
        raise ValueError("residual partial flushed count invalid")
    if residual_pending != residual_completed - residual_flushed or residual_failed != 0:
        raise ValueError("residual partial pending/failed count invalid")
    if residual_manifest.get("large_run_complete") is not False:
        raise ValueError("residual manifest must be incomplete when anchor is created")
    if len(residual_partial_rows) != residual_flushed:
        raise ValueError("residual partial result rows must equal flushed count")

    recovered_row_signature = _uniform_row_signature(recovered_rows, "recovered")
    residual_row_signature = _uniform_row_signature(residual_partial_rows, "residual partial")
    if recovered_row_signature != residual_row_signature:
        raise ValueError("recovered/residual partial row runtime signature mismatch")
    if _uniform_row_value(recovered_rows, "recovered", "run_id") != expected_source_run_id:
        raise ValueError("recovered row run_id mismatch")
    if (
        _uniform_row_value(residual_partial_rows, "residual partial", "run_id")
        != expected_residual_run_id
    ):
        raise ValueError("residual partial row run_id mismatch")

    source_manifest_signature = _manifest_signature(source_manifest)
    residual_manifest_signature = _manifest_signature(residual_manifest)
    if source_manifest_signature != residual_manifest_signature:
        raise ValueError("source/residual stable manifest projection mismatch")
    _validate_row_manifest_binding(recovered_row_signature, source_manifest, "recovered")
    _validate_row_manifest_binding(residual_row_signature, residual_manifest, "residual partial")

    source_plan_signature = _plan_signature(source_plan, "source")
    residual_plan_signature = _plan_signature(residual_plan, "residual")
    if source_plan_signature != residual_plan_signature:
        raise ValueError("source/residual stable plan projection mismatch")
    _validate_plan_manifest_binding(source_plan_signature, source_manifest, "source")
    _validate_plan_manifest_binding(residual_plan_signature, residual_manifest, "residual")

    stable_projection = {
        "row": recovered_row_signature,
        "manifest": source_manifest_signature,
        "plan": source_plan_signature,
    }
    stable_fingerprint = _canonical_hash(stable_projection)
    code_tree = runtime_code_tree_projection(runtime_root)
    fixed_artifacts = {
        "source_panel": _fixed_artifact(
            path=source_jsonl,
            rows=source_rows,
            expected_sha256=expected_panel_sha256,
        ),
        "adjudicated_baseline": _fixed_artifact(
            path=baseline_result,
            rows=baseline_rows,
            expected_sha256=expected_baseline_sha256,
        ),
        "golden_manifest": _fixed_artifact(
            path=golden_manifest,
            rows=golden_rows,
            expected_sha256=expected_golden_sha256,
        ),
    }
    immutable_components = {
        "recovered_result": _row_artifact(
            path=recovered_result_path,
            rows=recovered_rows,
        ),
        "recovery_summary": _immutable_json_artifact(
            path=recovery_summary_path,
            payload=recovery_summary,
        ),
        "source_checkpoint": {
            **_immutable_json_artifact(
                path=source_checkpoint_path,
                payload=source_checkpoint_rows,
            ),
            "checkpoint_row_count": len(source_checkpoint_rows),
            "completed_row_count": len(checkpoint_results),
            "completed_canonical_sha256": _canonical_hash(checkpoint_results),
            "completed_post_id_order_sha256": _canonical_hash(
                [_post_id(row) for row in checkpoint_results]
            ),
            "completed_post_id_set_sha256": _canonical_hash(
                sorted(_post_id(row) for row in checkpoint_results)
            ),
            "completed_global_idx_order_sha256": _canonical_hash(checkpoint_indexes),
            "failed_row_count": len(checkpoint_failed),
        },
        "residual_input": _row_artifact(
            path=residual_input_path,
            rows=residual_input_rows,
        ),
        "source_manifest": _immutable_json_artifact(
            path=source_manifest_path,
            payload=source_manifest,
        ),
        "source_plan": _immutable_json_artifact(
            path=source_plan_path,
            payload={key: value for key, value in source_plan.items() if key != "plan_path"},
        ),
        "residual_plan": _immutable_json_artifact(
            path=residual_plan_path,
            payload={key: value for key, value in residual_plan.items() if key != "plan_path"},
        ),
    }
    runtime_contract = source_plan_signature["runtime_contract"]
    required_env = source_plan_signature["required_env"]
    contract = {
        "model": source_manifest_signature["llm_model"],
        "endpoint": source_manifest_signature["llm_endpoint"],
        "prompt_version": recovered_row_signature["prompt_version"],
        "parallel": {
            "requested": source_manifest_signature["requested_parallel"],
            "effective": source_manifest_signature["effective_parallel"],
            "policy": source_manifest_signature["parallel_policy"],
        },
        "search": {
            "included": source_manifest_signature["mcp_health_include_search"],
            "light_mode": source_manifest_signature["mcp_health_light_mode"],
            "required_ok": source_manifest_signature["mcp_health_required_ok_count"],
            "healthy_ok": source_manifest_signature["mcp_health_ok_count"],
            "failure_count": source_manifest_signature["mcp_health_failure_count"],
            "reuse_shards_only": runtime_contract["reuse_shards_only"],
            "required_env": required_env,
        },
        "vlm_ocr": {
            "vlm": runtime_contract["vlm"],
            "ocr": runtime_contract["ocr"],
            "require_for_images": runtime_contract["require_vlm_ocr_for_images"],
            "semantic_review_ready": source_manifest_signature[
                "vlm_ocr_semantic_review_ready"
            ],
        },
        "slang_db": runtime_contract["slang_db"],
        "dashboard_required": runtime_contract["dashboard_required"],
    }
    payload: dict[str, Any] = {
        "report_type": TRUST_ANCHOR_REPORT_TYPE,
        "anchor_version": TRUST_ANCHOR_VERSION,
        "generated_at": generated_at or datetime.now().replace(microsecond=0).isoformat(),
        "gate": "GO",
        "topology": {
            "profile": "interrupted_merge_75_300",
            "components": ["recovered_source", "residual"],
            "source_rows": expected_source_count,
            "recovered_rows": expected_recovered_count,
            "residual_rows": expected_residual_count,
        },
        "generated_before_completion": True,
        "stable_runtime_fingerprint_sha256": stable_fingerprint,
        "release_fingerprint_sha256": _canonical_hash(
            {
                "stable_runtime_fingerprint_sha256": stable_fingerprint,
                "runtime_code_tree_sha256": code_tree["tree_sha256"],
                "source_panel_sha256": fixed_artifacts["source_panel"]["sha256"],
                "prompt_version": recovered_row_signature["prompt_version"],
            }
        ),
        "runtime_code_tree_sha256": code_tree["tree_sha256"],
        "runtime_code_tree": code_tree,
        "expected_counts": {
            "source_rows": expected_source_count,
            "recovered_rows": expected_recovered_count,
            "residual_rows": expected_residual_count,
            "golden_rows": expected_golden_count,
        },
        "run_ids": {
            "source": expected_source_run_id,
            "residual": expected_residual_run_id,
        },
        "stable_projection": stable_projection,
        "prompt_version_binding": {
            "expected": recovered_row_signature["prompt_version"],
            "recovered": recovered_row_signature["prompt_version"],
            "residual_partial": residual_row_signature["prompt_version"],
            "gate": "GO",
        },
        "configuration_hashes": {
            "row_signature_sha256": _canonical_hash(recovered_row_signature),
            "manifest_signature_sha256": _canonical_hash(source_manifest_signature),
            "plan_signature_sha256": _canonical_hash(source_plan_signature),
            "stable_runtime_fingerprint_sha256": stable_fingerprint,
            "runtime_code_tree_sha256": code_tree["tree_sha256"],
        },
        "input_hashes": {
            "source_panel_sha256": fixed_artifacts["source_panel"]["sha256"],
            "adjudicated_baseline_sha256": fixed_artifacts["adjudicated_baseline"][
                "sha256"
            ],
            "golden_manifest_sha256": fixed_artifacts["golden_manifest"]["sha256"],
            "source_post_id_order_sha256": fixed_artifacts["source_panel"][
                "post_id_order_sha256"
            ],
        },
        "fixed_artifacts": fixed_artifacts,
        "immutable_components": immutable_components,
        "partition_integrity": {
            "gate": "GO",
            "source_rows": len(source_rows),
            "recovered_rows": len(recovered_rows),
            "residual_input_rows": len(residual_input_rows),
            "recovered_is_source_order_checkpoint_subset": True,
            "residual_is_exact_original_order_complement": True,
            "overlap_post_ids": overlap_ids,
            "missing_post_ids": missing_ids,
            "extra_post_ids": extra_ids,
            "overlap_count": len(overlap_ids),
            "missing_count": len(missing_ids),
            "extra_count": len(extra_ids),
        },
        "contract": contract,
        "component_paths": {
            "source_plan": str(source_plan_path.resolve()),
            "residual_plan": str(residual_plan_path.resolve()),
            "source_manifest": str(source_manifest_path.resolve()),
            "source_checkpoint": str(source_checkpoint_path.resolve()),
            "recovered_result": str(recovered_result_path.resolve()),
            "recovery_summary": str(recovery_summary_path.resolve()),
            "residual_input": str(residual_input_path.resolve()),
        },
        "mutable_runtime_observation": {
            "residual_partial_row_count": len(residual_partial_rows),
            "source_manifest_counts": {
                field: source_manifest.get(field)
                for field in (
                    "input_post_count",
                    "completed_count",
                    "flushed_count",
                    "pending_count",
                    "failed_count",
                    "large_run_complete",
                )
            },
            "residual_manifest_counts": {
                field: residual_manifest.get(field)
                for field in (
                    "input_post_count",
                    "completed_count",
                    "flushed_count",
                    "pending_count",
                    "failed_count",
                    "large_run_complete",
                )
            },
            "counts_and_mutable_manifest_bytes_are_not_trust_root": True,
        },
        "approval_boundary": {
            "anchor_is_premerge_runtime_identity_not_semantic_approval": True,
            "immutable_partition_files_are_byte_and_canonical_bound": True,
            "mutable_residual_manifest_byte_hash_excluded": True,
            "mutable_residual_counts_excluded_from_stable_fingerprint": True,
            "merge_must_revalidate_anchor_against_completed_residual": True,
            "production_full_scan_approval": False,
        },
    }
    payload["anchor_payload_sha256"] = _canonical_hash(payload)
    return payload


def build_fresh375_trust_anchor(
    *,
    source_rows: list[dict[str, Any]],
    baseline_rows: list[dict[str, Any]],
    golden_rows: list[dict[str, Any]],
    fresh_plan: dict[str, Any],
    fresh_plan_path: Path,
    source_jsonl: Path,
    baseline_result: Path,
    golden_manifest: Path,
    runtime_root: Path,
    expected_prompt_version: str,
    expected_fresh_run_id: str | None,
    expected_source_count: int,
    expected_golden_count: int,
    expected_panel_sha256: str,
    expected_baseline_sha256: str,
    expected_golden_sha256: str,
    generated_at: str | None = None,
    allow_untrusted_test_roots: bool = False,
) -> dict[str, Any]:
    _validate_production_roots(
        source_jsonl=source_jsonl,
        baseline_result=baseline_result,
        golden_manifest=golden_manifest,
        expected_source_count=expected_source_count,
        expected_golden_count=expected_golden_count,
        expected_panel_sha256=expected_panel_sha256,
        expected_baseline_sha256=expected_baseline_sha256,
        expected_golden_sha256=expected_golden_sha256,
        allow_untrusted_test_roots=allow_untrusted_test_roots,
    )
    if len(source_rows) != expected_source_count or len(baseline_rows) != expected_source_count:
        raise ValueError("fresh375 source/baseline row count mismatch")
    source_ids = [_post_id(row) for row in source_rows]
    baseline_ids = [_post_id(row) for row in baseline_rows]
    if source_ids != baseline_ids or len(set(source_ids)) != len(source_ids):
        raise ValueError("fresh375 source/baseline order is not a unique match")
    if len(golden_rows) != expected_golden_count:
        raise ValueError("fresh375 golden row count mismatch")
    golden_ids = [_post_id(row) for row in golden_rows]
    if len(set(golden_ids)) != len(golden_ids) or not set(golden_ids).issubset(set(source_ids)):
        raise ValueError("fresh375 golden rows are not a unique panel subset")
    if not str(expected_prompt_version or "").strip():
        raise ValueError("fresh375 expected prompt version is required")

    plan_signature = _plan_signature(fresh_plan, "fresh375")
    execution_contract = fresh375_plan_execution_contract(
        fresh_plan=fresh_plan,
        fresh_plan_path=fresh_plan_path,
        source_jsonl=source_jsonl,
        runtime_root=runtime_root,
    )
    plan_payload = {key: value for key, value in fresh_plan.items() if key != "plan_path"}
    plan_artifact = _immutable_json_artifact(
        path=fresh_plan_path,
        payload=plan_payload,
    )
    argv = plan_signature["normalized_command_argv"]
    runtime_contract = plan_signature["runtime_contract"]
    required_env = plan_signature["required_env"]
    fixed_artifacts = {
        "source_panel": _fixed_artifact(
            path=source_jsonl,
            rows=source_rows,
            expected_sha256=expected_panel_sha256,
        ),
        "adjudicated_baseline": _fixed_artifact(
            path=baseline_result,
            rows=baseline_rows,
            expected_sha256=expected_baseline_sha256,
        ),
        "golden_manifest": _fixed_artifact(
            path=golden_manifest,
            rows=golden_rows,
            expected_sha256=expected_golden_sha256,
        ),
    }
    code_tree = runtime_code_tree_projection(runtime_root)
    stable_projection = {
        "plan": plan_signature,
        "fresh_plan_artifact": plan_artifact,
        "execution_contract_sha256": _canonical_hash(execution_contract),
        "expected_prompt_version": expected_prompt_version,
        "source_panel_sha256": fixed_artifacts["source_panel"]["sha256"],
        "source_post_id_order_sha256": fixed_artifacts["source_panel"][
            "post_id_order_sha256"
        ],
        "runtime_code_tree_sha256": code_tree["tree_sha256"],
    }
    release_fingerprint = _canonical_hash(stable_projection)
    contract = {
        "model": _arg_value(argv, "--llm-model"),
        "endpoint": _arg_value(argv, "--llm-endpoint"),
        "prompt_version": expected_prompt_version,
        "parallel": {
            "requested": int(_arg_value(argv, "--parallel") or 0),
            "policy": "effective_parallel=min(requested_parallel,input_post_count)",
        },
        "search": {
            "included": required_env["MCP_HEALTH_INCLUDE_SEARCH"] == "1",
            "light_mode": required_env["MCP_HEALTH_LIGHT_MODE"] == "1",
            "required_ok": int(required_env["MCP_HEALTH_REQUIRED_OK"]),
            "reuse_shards_only": runtime_contract["reuse_shards_only"],
            "required_env": required_env,
        },
        "vlm_ocr": {
            "vlm": runtime_contract["vlm"],
            "ocr": runtime_contract["ocr"],
            "require_for_images": runtime_contract["require_vlm_ocr_for_images"],
        },
        "slang_db": runtime_contract["slang_db"],
        "dashboard_required": runtime_contract["dashboard_required"],
    }
    payload: dict[str, Any] = {
        "report_type": TRUST_ANCHOR_REPORT_TYPE,
        "anchor_version": TRUST_ANCHOR_VERSION,
        "generated_at": generated_at or datetime.now().replace(microsecond=0).isoformat(),
        "gate": "GO",
        "topology": {
            "profile": "fresh375",
            "components": ["fresh375"],
            "source_rows": expected_source_count,
        },
        "binding_phase": "pre_run_release_anchor",
        "generated_before_completion": True,
        "stable_runtime_fingerprint_sha256": release_fingerprint,
        "release_fingerprint_sha256": release_fingerprint,
        "runtime_code_tree_sha256": code_tree["tree_sha256"],
        "runtime_code_tree": code_tree,
        "expected_counts": {
            "source_rows": expected_source_count,
            "fresh_rows": expected_source_count,
            "golden_rows": expected_golden_count,
        },
        "run_ids": {"fresh": expected_fresh_run_id},
        "stable_projection": stable_projection,
        "prompt_version_binding": {
            "expected": expected_prompt_version,
            "source": "explicit_pre_run_contract",
            "actual_run_start": None,
            "gate": "PENDING_RUN_START_RECEIPT",
        },
        "configuration_hashes": {
            "plan_signature_sha256": _canonical_hash(plan_signature),
            "fresh_plan_byte_sha256": plan_artifact["byte_sha256"],
            "fresh_plan_canonical_sha256": plan_artifact["canonical_sha256"],
            "execution_contract_sha256": _canonical_hash(execution_contract),
            "release_fingerprint_sha256": release_fingerprint,
            "runtime_code_tree_sha256": code_tree["tree_sha256"],
        },
        "input_hashes": {
            "source_panel_sha256": fixed_artifacts["source_panel"]["sha256"],
            "adjudicated_baseline_sha256": fixed_artifacts["adjudicated_baseline"][
                "sha256"
            ],
            "golden_manifest_sha256": fixed_artifacts["golden_manifest"]["sha256"],
            "source_post_id_order_sha256": fixed_artifacts["source_panel"][
                "post_id_order_sha256"
            ],
        },
        "fixed_artifacts": fixed_artifacts,
        "immutable_components": {
            "fresh_plan": plan_artifact,
        },
        "contract": contract,
        "execution_contract": execution_contract,
        "component_paths": {
            "fresh_plan": str(fresh_plan_path.resolve()),
        },
        "mutable_runtime_observation": {
            "run_not_required_to_exist_when_anchor_is_created": True,
            "mutable_manifest_byte_hash_excluded": True,
            "mutable_runtime_counts_excluded": True,
        },
        "approval_boundary": {
            "anchor_is_prerun_release_identity_not_semantic_approval": True,
            "pre_run_anchor_is_not_actual_run_start_binding": True,
            "separate_actual_run_start_binding_receipt_required": True,
            "runtime_must_bind_completed_rows_and_manifest_to_this_anchor": True,
            "production_full_scan_approval": False,
        },
    }
    payload["anchor_payload_sha256"] = _canonical_hash(payload)
    return payload


def _legacy_build_fresh375_run_start_binding_receipt_v1(
    *,
    pre_run_anchor: dict[str, Any],
    pre_run_anchor_path: Path,
    expected_anchor_sha256: str,
    run_manifest: dict[str, Any],
    run_manifest_path: Path,
    partial_rows: list[dict[str, Any]],
    partial_result_path: Path,
    source_rows: list[dict[str, Any]],
    source_jsonl: Path,
    runtime_root: Path,
    generated_at: str | None = None,
    allow_untrusted_test_roots: bool = False,
) -> dict[str, Any]:
    """Bind an actual fresh375 run start without mutating the pre-run anchor."""
    if _load_json(pre_run_anchor_path) != pre_run_anchor:
        raise ValueError("fresh375 pre-run anchor parsed payload mismatch")
    if _load_json(run_manifest_path) != run_manifest:
        raise ValueError("fresh375 run manifest parsed payload mismatch")
    if _rows_from_json_or_jsonl(partial_result_path, "fresh375 partial result") != partial_rows:
        raise ValueError("fresh375 partial result parsed payload mismatch")
    if _load_jsonl(source_jsonl) != source_rows:
        raise ValueError("fresh375 source input parsed payload mismatch")
    if pre_run_anchor_path.stat().st_mode & stat.S_IWRITE:
        raise ValueError("fresh375 pre-run anchor must be read-only")
    actual_anchor_sha256 = _sha256(pre_run_anchor_path)
    if actual_anchor_sha256 != _require_sha256(
        expected_anchor_sha256, "fresh375 pre-run anchor"
    ):
        raise ValueError("fresh375 pre-run anchor sha256 mismatch")
    if pre_run_anchor.get("topology", {}).get("profile") != "fresh375":
        raise ValueError("fresh375 run-start receipt requires fresh375 profile")
    if pre_run_anchor.get("binding_phase") != "pre_run_release_anchor":
        raise ValueError("fresh375 pre-run anchor phase mismatch")
    if pre_run_anchor.get("anchor_version") != TRUST_ANCHOR_VERSION:
        raise ValueError("fresh375 pre-run anchor version mismatch")
    supplied_payload_hash = pre_run_anchor.get("anchor_payload_sha256")
    payload_without_hash = dict(pre_run_anchor)
    payload_without_hash.pop("anchor_payload_sha256", None)
    if supplied_payload_hash != _canonical_hash(payload_without_hash):
        raise ValueError("fresh375 pre-run anchor payload digest mismatch")
    stable_projection = pre_run_anchor.get("stable_projection")
    if not isinstance(stable_projection, dict):
        raise ValueError("fresh375 pre-run stable projection missing")
    release_fingerprint = _canonical_hash(stable_projection)
    if (
        pre_run_anchor.get("release_fingerprint_sha256") != release_fingerprint
        or pre_run_anchor.get("stable_runtime_fingerprint_sha256") != release_fingerprint
    ):
        raise ValueError("fresh375 pre-run release fingerprint mismatch")
    code_tree = runtime_code_tree_projection(runtime_root)
    if (
        pre_run_anchor.get("runtime_code_tree_sha256") != code_tree["tree_sha256"]
        or pre_run_anchor.get("runtime_code_tree") != code_tree
        or stable_projection.get("runtime_code_tree_sha256") != code_tree["tree_sha256"]
    ):
        raise ValueError("fresh375 runtime code tree changed after pre-run anchor")

    source_ids = [_post_id(row) for row in source_rows]
    if len(set(source_ids)) != len(source_ids):
        raise ValueError("fresh375 source input has duplicate post_id")
    source_binding = pre_run_anchor.get("fixed_artifacts", {}).get("source_panel")
    if not isinstance(source_binding, dict):
        raise ValueError("fresh375 source panel anchor binding missing")
    if (
        Path(str(source_binding.get("path") or "")).resolve() != source_jsonl.resolve()
        or source_binding.get("sha256") != _sha256(source_jsonl)
        or source_binding.get("row_count") != len(source_rows)
        or source_binding.get("post_id_order_sha256") != _canonical_hash(source_ids)
        or source_binding.get("post_id_set_sha256") != _canonical_hash(sorted(source_ids))
    ):
        raise ValueError("fresh375 source input does not match pre-run anchor")
    if not allow_untrusted_test_roots:
        if source_jsonl.resolve() != PRODUCTION_PANEL_PATH:
            raise ValueError("fresh375 production source input path mismatch")
        if _sha256(source_jsonl) != PRODUCTION_PANEL_SHA256:
            raise ValueError("fresh375 production source input sha256 mismatch")
        docs_root = (ROOT / "docs/devs").resolve()
        if docs_root not in pre_run_anchor_path.resolve().parents:
            raise ValueError("fresh375 production pre-run anchor is outside docs/devs")
    expected_rows = int(pre_run_anchor.get("expected_counts", {}).get("fresh_rows") or 0)
    if len(source_rows) != expected_rows:
        raise ValueError("fresh375 source row count does not match pre-run anchor")
    manifest_run_id = str(run_manifest.get("run_id") or "").strip()
    if not manifest_run_id:
        raise ValueError("fresh375 run manifest run_id is empty")
    anchored_run_id = pre_run_anchor.get("run_ids", {}).get("fresh")
    if anchored_run_id not in (None, "") and str(anchored_run_id) != manifest_run_id:
        raise ValueError("fresh375 run id does not match pre-run anchor")
    completed = run_manifest.get("completed_count")
    flushed = run_manifest.get("flushed_count")
    pending = run_manifest.get("pending_count")
    failed = run_manifest.get("failed_count")
    if any(
        isinstance(value, bool) or not isinstance(value, int)
        for value in (completed, flushed, pending, failed)
    ):
        raise ValueError("fresh375 run-start counts must be integers")
    if not (
        run_manifest.get("input_post_count") == expected_rows
        and 0 < completed < expected_rows
        and 0 < flushed <= completed
        and pending == completed - flushed
        and failed == 0
        and run_manifest.get("large_run_complete") is False
        and len(partial_rows) == flushed
    ):
        raise ValueError("fresh375 receipt must observe an incomplete started run")
    manifest_output_file = str(run_manifest.get("output_file") or "").strip()
    if not manifest_output_file:
        raise ValueError("fresh375 run manifest output_file is missing")
    manifest_output_path = Path(manifest_output_file)
    if not manifest_output_path.is_absolute():
        manifest_output_path = ROOT / manifest_output_path
    if manifest_output_path.resolve() != partial_result_path.resolve():
        raise ValueError("fresh375 manifest/result path mismatch")
    partial_ids = [_post_id(row) for row in partial_rows]
    if partial_ids != source_ids[:flushed]:
        raise ValueError("fresh375 partial result is not the ordered input prefix")
    row_signature = _uniform_row_signature(partial_rows, "fresh375 run start")
    row_run_id = _uniform_row_value(partial_rows, "fresh375 run start", "run_id")
    if row_run_id != manifest_run_id:
        raise ValueError("fresh375 partial row run_id does not match manifest")
    actual_config_hash = str(
        _uniform_row_value(partial_rows, "fresh375 run start", "config_hash") or ""
    ).strip()
    if not actual_config_hash:
        raise ValueError("fresh375 partial row config_hash is empty")
    manifest_signature = _manifest_signature(run_manifest)
    _validate_row_manifest_binding(row_signature, run_manifest, "fresh375 run start")
    plan_signature = stable_projection.get("plan")
    if not isinstance(plan_signature, dict):
        raise ValueError("fresh375 pre-run plan signature missing")
    _validate_plan_manifest_binding(plan_signature, run_manifest, "fresh375 run start")
    expected_prompt = pre_run_anchor.get("prompt_version_binding", {}).get("expected")
    actual_prompt = row_signature.get("prompt_version")
    if actual_prompt != expected_prompt:
        raise ValueError("fresh375 run-start prompt version mismatch")
    contract = pre_run_anchor.get("contract", {})
    if (
        run_manifest.get("llm_model") != contract.get("model")
        or run_manifest.get("llm_endpoint") != contract.get("endpoint")
    ):
        raise ValueError("fresh375 run-start model/endpoint mismatch")
    anchor_generated_at = datetime.fromisoformat(
        str(pre_run_anchor.get("generated_at") or "")
    ).timestamp()
    anchor_mtime = pre_run_anchor_path.stat().st_mtime
    manifest_mtime = run_manifest_path.stat().st_mtime
    partial_mtime = partial_result_path.stat().st_mtime
    observed_at = generated_at or datetime.now().astimezone().replace(microsecond=0).isoformat()
    observed_timestamp = datetime.fromisoformat(observed_at).timestamp()
    if anchor_generated_at > anchor_mtime + 5:
        raise ValueError("fresh375 pre-run anchor generated_at is after anchor mtime")
    if not (anchor_mtime < manifest_mtime and anchor_mtime < partial_mtime):
        raise ValueError("fresh375 run artifacts were not created after pre-run anchor")
    if observed_timestamp + 5 < max(manifest_mtime, partial_mtime):
        raise ValueError("fresh375 run-start receipt timestamp predates observed artifacts")
    receipt: dict[str, Any] = {
        "report_type": "fresh375_actual_run_start_binding_receipt",
        "schema_version": "fresh375-run-start-binding-v1",
        "binding_phase": "actual_run_start",
        "generated_at": observed_at,
        "gate": "GO",
        "finalized": True,
        "pre_run_anchor": {
            "path": str(pre_run_anchor_path.resolve()),
            "sha256": actual_anchor_sha256,
            "anchor_version": pre_run_anchor["anchor_version"],
            "release_fingerprint_sha256": pre_run_anchor[
                "release_fingerprint_sha256"
            ],
        },
        "run_id": manifest_run_id,
        "release_fingerprint_sha256": release_fingerprint,
        "runtime_code_tree_sha256": code_tree["tree_sha256"],
        "source_input": _row_artifact(path=source_jsonl, rows=source_rows),
        "observed_counts": {
            "input_post_count": run_manifest.get("input_post_count"),
            "completed_count": completed,
            "flushed_count": flushed,
            "pending_count": pending,
            "failed_count": failed,
            "large_run_complete": run_manifest.get("large_run_complete"),
        },
        "prompt_version_binding": {
            "expected": expected_prompt,
            "actual": actual_prompt,
            "gate": "GO",
        },
        "row_signature": row_signature,
        "manifest_signature": manifest_signature,
        "plan_signature_sha256": _canonical_hash(plan_signature),
        "config_binding": {
            "uniform_row_config_hash": actual_config_hash,
            "gate": "GO",
        },
        "partial_result": _row_artifact(
            path=partial_result_path,
            rows=partial_rows,
        ),
        "run_manifest": _immutable_json_artifact(
            path=run_manifest_path,
            payload=run_manifest,
        ),
        "temporal_binding": {
            "pre_run_anchor_generated_at": pre_run_anchor.get("generated_at"),
            "pre_run_anchor_mtime": datetime.fromtimestamp(anchor_mtime).astimezone().isoformat(),
            "partial_result_mtime": datetime.fromtimestamp(partial_mtime).astimezone().isoformat(),
            "run_manifest_mtime": datetime.fromtimestamp(manifest_mtime).astimezone().isoformat(),
            "anchor_precedes_run_artifacts": True,
            "receipt_observes_incomplete_run": True,
        },
        "finalization": {
            "state": "FINALIZED",
            "marker": "FRESH375_RUN_START_BOUND",
            "self_digest_algorithm": "sha256(canonical_json_without_receipt_payload_sha256)",
        },
        "approval_boundary": {
            "run_start_binding_is_not_completion_or_semantic_approval": True,
            "production_full_scan_approval": False,
        },
    }
    receipt["receipt_payload_sha256"] = _canonical_hash(receipt)
    return receipt


def _legacy_validate_fresh375_run_start_binding_receipt_v1(
    receipt: dict[str, Any],
    *,
    receipt_path: Path | None = None,
    verify_artifact_bytes: bool = False,
) -> dict[str, Any]:
    if receipt.get("report_type") != "fresh375_actual_run_start_binding_receipt":
        raise ValueError("fresh375 receipt report_type mismatch")
    if receipt.get("schema_version") != "fresh375-run-start-binding-v1":
        raise ValueError("fresh375 receipt schema_version mismatch")
    if receipt.get("gate") != "GO" or receipt.get("finalized") is not True:
        raise ValueError("fresh375 receipt is not finalized GO")
    if receipt.get("finalization", {}).get("marker") != "FRESH375_RUN_START_BOUND":
        raise ValueError("fresh375 receipt finalization marker mismatch")
    supplied_digest = str(receipt.get("receipt_payload_sha256") or "")
    payload_without_digest = dict(receipt)
    payload_without_digest.pop("receipt_payload_sha256", None)
    if supplied_digest != _canonical_hash(payload_without_digest):
        raise ValueError("fresh375 receipt self-digest mismatch")
    if not str(receipt.get("run_id") or "").strip():
        raise ValueError("fresh375 receipt run_id is empty")
    if receipt_path is not None and receipt_path.stat().st_mode & stat.S_IWRITE:
        raise ValueError("fresh375 receipt file is not read-only")
    if verify_artifact_bytes:
        for name in ("pre_run_anchor", "source_input", "partial_result", "run_manifest"):
            binding = receipt.get(name)
            if not isinstance(binding, dict):
                raise ValueError(f"fresh375 receipt {name} binding missing")
            path = Path(str(binding.get("path") or ""))
            expected_hash = binding.get("byte_sha256") or binding.get("sha256")
            if not path.is_file() or _sha256(path) != expected_hash:
                raise ValueError(f"fresh375 receipt {name} byte mismatch")
    return {
        "gate": "GO",
        "run_id": receipt["run_id"],
        "receipt_payload_sha256": supplied_digest,
        "release_fingerprint_sha256": receipt["release_fingerprint_sha256"],
    }


def create_fresh375_run_start_snapshots_and_receipt(
    *,
    pre_run_anchor: dict[str, Any],
    pre_run_anchor_path: Path,
    expected_anchor_sha256: str,
    supervisor_start_event: dict[str, Any],
    supervisor_start_event_path: Path,
    live_result_path: Path,
    live_manifest_path: Path,
    live_checkpoint_path: Path,
    live_pending_path: Path,
    snapshot_result_path: Path,
    snapshot_manifest_path: Path,
    receipt_path: Path,
    source_rows: list[dict[str, Any]],
    source_jsonl: Path,
    fresh_plan: dict[str, Any],
    fresh_plan_path: Path,
    runtime_root: Path,
    process_state_provider: Callable[[int], dict[str, Any]] | None = None,
    dashboard_url: str = "http://127.0.0.1:8080",
    allow_untrusted_test_roots: bool = False,
) -> dict[str, Any]:
    process_state_provider = process_state_provider or _process_state_windows
    if (
        not allow_untrusted_test_roots
        and not isinstance(process_state_provider, _BoundPopenStateProvider)
    ):
        raise ValueError(
            "fresh375 production snapshot requires the supervisor-owned Popen capability"
        )
    start = validate_fresh375_supervisor_start_event(
        supervisor_start_event,
        event_path=supervisor_start_event_path,
    )
    anchor_binding, plan_artifact, execution_contract = _fresh_anchor_plan_binding(
        pre_run_anchor=pre_run_anchor,
        pre_run_anchor_path=pre_run_anchor_path,
        expected_anchor_sha256=expected_anchor_sha256,
        fresh_plan=fresh_plan,
        fresh_plan_path=fresh_plan_path,
        source_rows=source_rows,
        source_jsonl=source_jsonl,
        runtime_root=runtime_root,
        dashboard_url=dashboard_url,
        allow_untrusted_test_roots=allow_untrusted_test_roots,
    )
    if supervisor_start_event.get("pre_run_anchor") != anchor_binding:
        raise ValueError("fresh375 start event/pre-run anchor binding mismatch")
    if supervisor_start_event.get("fresh_plan") != plan_artifact:
        raise ValueError("fresh375 start event/plan binding mismatch")
    _validate_fresh375_start_execution_binding(
        event=supervisor_start_event,
        execution_contract=execution_contract,
        binding_token_commitment=start["binding_token_commitment"],
    )
    event_paths = supervisor_start_event.get("artifact_paths", {})
    expected_paths = {
        "live_result": live_result_path.resolve(),
        "live_manifest": live_manifest_path.resolve(),
        "live_checkpoint": live_checkpoint_path.resolve(),
        "live_pending": live_pending_path.resolve(),
        "snapshot_result": snapshot_result_path.resolve(),
        "snapshot_manifest": snapshot_manifest_path.resolve(),
        "run_start_receipt": receipt_path.resolve(),
    }
    if any(
        Path(str(event_paths.get(name) or "")).resolve() != expected
        for name, expected in expected_paths.items()
    ):
        raise ValueError("fresh375 supervisor artifact path binding mismatch")
    if len(set(expected_paths.values())) != len(expected_paths):
        raise ValueError("fresh375 live/snapshot/receipt paths collide")
    collisions = [
        str(path)
        for path in (snapshot_result_path, snapshot_manifest_path, receipt_path)
        if path.exists()
    ]
    if collisions:
        raise FileExistsError(f"fresh375 run-start immutable output collision: {collisions}")
    state = process_state_provider(start["pid"])
    _validate_fresh375_bound_process_state(
        state=state,
        start_binding=start,
        allow_untrusted_test_roots=allow_untrusted_test_roots,
    )
    # The supervisor reads live payloads only to copy the first durable flush.
    # No live byte/canonical hash is recorded in the receipt.
    live_manifest = _load_json(live_manifest_path)
    live_rows = _rows_from_json_or_jsonl(live_result_path, "fresh375 live durable result")
    if (
        live_manifest.get("large_run_complete") is not False
        or int(live_manifest.get("completed_count") or 0) <= 0
        or int(live_manifest.get("flushed_count") or 0) <= 0
        or len(live_rows) != int(live_manifest.get("flushed_count") or 0)
    ):
        raise ValueError("fresh375 live files are complete or not a durable flush")
    _validate_fresh375_binding_token_echo(
        rows=live_rows,
        manifest=live_manifest,
        expected_commitment=start["binding_token_commitment"],
        label="fresh375 live durable flush",
    )
    _write_json_exclusive(snapshot_result_path, live_rows)  # type: ignore[arg-type]
    _write_json_exclusive(snapshot_manifest_path, live_manifest)
    receipt = build_fresh375_run_start_binding_receipt(
        pre_run_anchor=pre_run_anchor,
        pre_run_anchor_path=pre_run_anchor_path,
        expected_anchor_sha256=expected_anchor_sha256,
        supervisor_start_event=supervisor_start_event,
        supervisor_start_event_path=supervisor_start_event_path,
        snapshot_manifest=live_manifest,
        snapshot_manifest_path=snapshot_manifest_path,
        snapshot_rows=live_rows,
        snapshot_result_path=snapshot_result_path,
        source_rows=source_rows,
        source_jsonl=source_jsonl,
        fresh_plan=fresh_plan,
        fresh_plan_path=fresh_plan_path,
        runtime_root=runtime_root,
        process_state_provider=process_state_provider,
        dashboard_url=dashboard_url,
        allow_untrusted_test_roots=allow_untrusted_test_roots,
    )
    _write_json_exclusive(receipt_path, receipt)
    validate_fresh375_run_start_binding_receipt(
        _load_json(receipt_path),
        receipt_path=receipt_path,
        verify_artifact_bytes=True,
    )
    return receipt


def build_fresh375_final_continuity_verification(
    *,
    receipt: dict[str, Any],
    receipt_path: Path,
    final_rows: list[dict[str, Any]],
    final_result_path: Path,
    final_manifest: dict[str, Any],
    final_manifest_path: Path,
    final_checkpoint_rows: list[dict[str, Any]],
    final_checkpoint_path: Path,
    final_pending: Any,
    final_pending_path: Path,
    source_rows: list[dict[str, Any]],
    process_exit_code: int,
    generated_at: str | None = None,
) -> dict[str, Any]:
    receipt_validation = validate_fresh375_run_start_binding_receipt(
        receipt,
        receipt_path=receipt_path,
        verify_artifact_bytes=True,
    )
    live = receipt["live_artifact_diagnostics"]
    if (
        final_result_path.resolve() != Path(str(live["result_path"])).resolve()
        or final_manifest_path.resolve() != Path(str(live["manifest_path"])).resolve()
    ):
        raise ValueError("fresh375 final live paths differ from supervised paths")
    start_event = _load_json(
        Path(str(receipt.get("supervisor_start_event", {}).get("path") or ""))
    )
    event_paths = start_event.get("artifact_paths", {})
    if (
        final_checkpoint_path.resolve()
        != Path(str(event_paths.get("live_checkpoint") or "")).resolve()
        or final_pending_path.resolve()
        != Path(str(event_paths.get("live_pending") or "")).resolve()
    ):
        raise ValueError("fresh375 final checkpoint/pending paths differ from start event")
    if _rows_from_json_or_jsonl(final_result_path, "fresh375 final result") != final_rows:
        raise ValueError("fresh375 final result file/payload mismatch")
    if _load_json(final_manifest_path) != final_manifest:
        raise ValueError("fresh375 final manifest file/payload mismatch")
    if _load_jsonl(final_checkpoint_path) != final_checkpoint_rows:
        raise ValueError("fresh375 final checkpoint file/payload mismatch")
    if _load_json(final_pending_path) != final_pending:
        raise ValueError("fresh375 final pending file/payload mismatch")
    final_paths = (
        final_result_path,
        final_manifest_path,
        final_checkpoint_path,
        final_pending_path,
    )
    if any(path.stat().st_mode & stat.S_IWRITE for path in final_paths):
        raise ValueError("fresh375 final artifact set must be read-only before continuity")
    expected_rows = len(source_rows)
    required_counts = {
        "input_post_count": expected_rows,
        "completed_count": expected_rows,
        "flushed_count": expected_rows,
        "pending_count": 0,
        "failed_count": 0,
    }
    if (
        process_exit_code != 0
        or len(final_rows) != expected_rows
        or final_manifest.get("large_run_complete") is not True
        or any(final_manifest.get(key) != value for key, value in required_counts.items())
    ):
        raise ValueError("fresh375 final runtime is not complete and successful")
    if [_post_id(row) for row in final_rows] != [_post_id(row) for row in source_rows]:
        raise ValueError("fresh375 final result order differs from source input")
    _validate_fresh375_final_checkpoint(
        checkpoint_rows=final_checkpoint_rows,
        final_rows=final_rows,
        source_rows=source_rows,
    )
    if final_pending != []:
        raise ValueError("fresh375 final pending snapshot is not empty")
    run_id = receipt_validation["run_id"]
    if (
        str(final_manifest.get("run_id") or "") != run_id
        or any(str((row.get("run_meta") or {}).get("run_id") or "") != run_id for row in final_rows)
    ):
        raise ValueError("fresh375 final run_id continuity mismatch")
    snapshot_path = Path(str(receipt["snapshot_result"]["path"]))
    snapshot_rows = _rows_from_json_or_jsonl(snapshot_path, "fresh375 immutable snapshot")
    if final_rows[: len(snapshot_rows)] != snapshot_rows:
        raise ValueError("fresh375 final result does not preserve immutable snapshot prefix")
    final_signature = _uniform_row_signature(final_rows, "fresh375 final")
    if final_signature != receipt.get("row_signature"):
        raise ValueError("fresh375 snapshot/final row runtime signature mismatch")
    final_config_hash = str(
        _uniform_row_value(final_rows, "fresh375 final", "config_hash") or ""
    ).strip()
    if final_config_hash != receipt.get("config_binding", {}).get("uniform_row_config_hash"):
        raise ValueError("fresh375 snapshot/final config hash mismatch")
    _validate_fresh375_binding_token_echo(
        rows=final_rows,
        manifest=final_manifest,
        expected_commitment=receipt.get("process_continuity", {}).get(
            "binding_token_commitment"
        ),
        label="fresh375 final artifact set",
    )
    final_artifacts = {
        "result": _row_artifact(path=final_result_path, rows=final_rows),
        "manifest": _immutable_json_artifact(
            path=final_manifest_path,
            payload=final_manifest,
        ),
        "checkpoint": _row_artifact(
            path=final_checkpoint_path,
            rows=final_checkpoint_rows,
        ),
        "pending": _immutable_json_artifact(
            path=final_pending_path,
            payload=final_pending,
        ),
    }
    report: dict[str, Any] = {
        "report_type": "fresh375_final_prefix_continuity_verification",
        "schema_version": FRESH375_FINAL_CONTINUITY_SCHEMA_VERSION,
        "generated_at": generated_at or datetime.now().astimezone().isoformat(),
        "gate": "GO",
        "run_id": run_id,
        "release_fingerprint_sha256": receipt_validation[
            "release_fingerprint_sha256"
        ],
        "run_start_receipt": {
            "path": str(receipt_path.resolve()),
            "sha256": _sha256(receipt_path),
            "payload_sha256": receipt_validation["receipt_payload_sha256"],
        },
        "immutable_snapshot": receipt["snapshot_result"],
        "immutable_snapshot_schema_version": FRESH375_SNAPSHOT_SCHEMA_VERSION,
        "final_artifacts": final_artifacts,
        "continuity": {
            "snapshot_rows": len(snapshot_rows),
            "final_rows": len(final_rows),
            "exact_prefix_preserved": True,
            "same_run_id": True,
            "same_runtime_signature": True,
            "same_config_hash": True,
            "process_exit_code": process_exit_code,
            "final_result_manifest_checkpoint_pending_read_only": True,
        },
        "finalization": {
            "state": "FINALIZED",
            "marker": "FRESH375_FINAL_ARTIFACT_SET_COMMITTED_LAST",
            "continuity_written_after_final_artifact_freeze": True,
        },
        "approval_boundary": {
            "runtime_continuity_is_not_semantic_or_production_approval": True,
            "production_full_scan_approval": False,
        },
    }
    report["verification_payload_sha256"] = _canonical_hash(report)
    return report


def validate_fresh375_final_continuity_verification(
    *,
    verification: dict[str, Any],
    verification_path: Path,
    source_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    if (
        verification.get("report_type")
        != "fresh375_final_prefix_continuity_verification"
        or verification.get("schema_version") != FRESH375_FINAL_CONTINUITY_SCHEMA_VERSION
        or verification.get("immutable_snapshot_schema_version")
        != FRESH375_SNAPSHOT_SCHEMA_VERSION
        or verification.get("gate") != "GO"
        or verification.get("finalization", {}).get("marker")
        != "FRESH375_FINAL_ARTIFACT_SET_COMMITTED_LAST"
    ):
        raise ValueError("fresh375 final continuity type/version/finalization invalid")
    supplied = str(verification.get("verification_payload_sha256") or "")
    without_digest = dict(verification)
    without_digest.pop("verification_payload_sha256", None)
    if supplied != _canonical_hash(without_digest):
        raise ValueError("fresh375 final continuity self-digest mismatch")
    if (
        not verification_path.is_file()
        or verification_path.stat().st_mode & stat.S_IWRITE
        or _load_json(verification_path) != verification
    ):
        raise ValueError("fresh375 final continuity artifact is missing, writable, or changed")
    receipt_binding = verification.get("run_start_receipt")
    final_artifacts = verification.get("final_artifacts")
    if not isinstance(receipt_binding, dict) or not isinstance(final_artifacts, dict):
        raise ValueError("fresh375 final continuity bindings missing")
    receipt_path = Path(str(receipt_binding.get("path") or ""))
    receipt = _load_json(receipt_path)
    if (
        _sha256(receipt_path) != receipt_binding.get("sha256")
        or receipt.get("receipt_payload_sha256")
        != receipt_binding.get("payload_sha256")
    ):
        raise ValueError("fresh375 final continuity receipt binding mismatch")
    required_artifacts = {"result", "manifest", "checkpoint", "pending"}
    if set(final_artifacts) != required_artifacts:
        raise ValueError("fresh375 final continuity four-artifact set missing")
    loaded: dict[str, Any] = {}
    for name in sorted(required_artifacts):
        binding = final_artifacts[name]
        if not isinstance(binding, dict):
            raise ValueError(f"fresh375 final {name} binding invalid")
        path = Path(str(binding.get("path") or ""))
        if (
            not path.is_file()
            or path.stat().st_mode & stat.S_IWRITE
            or _sha256(path) != binding.get("byte_sha256")
        ):
            raise ValueError(f"fresh375 final {name} byte/read-only binding mismatch")
        payload = _load_jsonl(path) if name == "checkpoint" else _load_json(path)
        if _canonical_hash(payload) != binding.get("canonical_sha256"):
            raise ValueError(f"fresh375 final {name} canonical binding mismatch")
        loaded[name] = payload
    rebuilt = build_fresh375_final_continuity_verification(
        receipt=receipt,
        receipt_path=receipt_path,
        final_rows=loaded["result"],
        final_result_path=Path(final_artifacts["result"]["path"]),
        final_manifest=loaded["manifest"],
        final_manifest_path=Path(final_artifacts["manifest"]["path"]),
        final_checkpoint_rows=loaded["checkpoint"],
        final_checkpoint_path=Path(final_artifacts["checkpoint"]["path"]),
        final_pending=loaded["pending"],
        final_pending_path=Path(final_artifacts["pending"]["path"]),
        source_rows=source_rows,
        process_exit_code=int(verification.get("continuity", {}).get("process_exit_code")),
        generated_at=str(verification.get("generated_at") or ""),
    )
    if rebuilt != verification:
        raise ValueError("fresh375 final continuity source recomputation mismatch")
    return {
        "gate": "GO",
        "run_id": verification["run_id"],
        "release_fingerprint_sha256": verification[
            "release_fingerprint_sha256"
        ],
        "verification_payload_sha256": supplied,
        "final_artifacts": final_artifacts,
    }


def validate_fresh375_consumer_trust_bundle(
    *,
    pre_run_anchor_path: Path,
    compiled_anchor_path: Path,
    compiled_anchor_sha256: str,
    supervisor_start_event_path: Path,
    run_start_receipt_path: Path,
    final_continuity_path: Path,
    source_jsonl: Path,
) -> dict[str, Any]:
    """Fail-closed consumer entrypoint; callers must supply a compiled path/SHA pin."""
    if pre_run_anchor_path.resolve() != compiled_anchor_path.resolve():
        raise ValueError("fresh375 compiled pre-run anchor path pin mismatch")
    expected_anchor_sha = _require_sha256(
        compiled_anchor_sha256, "fresh375 compiled pre-run anchor"
    )
    if _sha256(pre_run_anchor_path) != expected_anchor_sha:
        raise ValueError("fresh375 compiled pre-run anchor sha256 pin mismatch")
    anchor = _load_json(pre_run_anchor_path)
    event = _load_json(supervisor_start_event_path)
    start = validate_fresh375_supervisor_start_event(
        event,
        event_path=supervisor_start_event_path,
    )
    receipt = _load_json(run_start_receipt_path)
    receipt_validation = validate_fresh375_run_start_binding_receipt(
        receipt,
        receipt_path=run_start_receipt_path,
        verify_artifact_bytes=True,
    )
    source_rows = _load_jsonl(source_jsonl)
    final = _load_json(final_continuity_path)
    final_validation = validate_fresh375_final_continuity_verification(
        verification=final,
        verification_path=final_continuity_path,
        source_rows=source_rows,
    )
    anchor_binding = receipt.get("pre_run_anchor", {})
    if (
        anchor_binding.get("path") != str(pre_run_anchor_path.resolve())
        or anchor_binding.get("sha256") != expected_anchor_sha
        or event.get("pre_run_anchor") != anchor_binding
        or receipt_validation["run_id"] != final_validation["run_id"]
        or receipt_validation["release_fingerprint_sha256"]
        != final_validation["release_fingerprint_sha256"]
        or start["binding_token_commitment"]
        != receipt.get("process_continuity", {}).get("binding_token_commitment")
    ):
        raise ValueError("fresh375 consumer trust-chain cross binding mismatch")
    return {
        "gate": "GO",
        "schema": "fresh375-consumer-trust-bundle-v2",
        "run_id": final_validation["run_id"],
        "compiled_pre_run_anchor": {
            "path": str(pre_run_anchor_path.resolve()),
            "sha256": expected_anchor_sha,
        },
        "supervisor_start_event_sha256": _sha256(supervisor_start_event_path),
        "run_start_receipt_sha256": _sha256(run_start_receipt_path),
        "final_continuity_sha256": _sha256(final_continuity_path),
        "final_artifacts": final_validation["final_artifacts"],
        "production_full_scan_approval": False,
    }


def _resume_suspended_windows_process(process: subprocess.Popen[Any]) -> None:
    if os.name != "nt":
        raise RuntimeError("fresh375 production supervisor requires Windows suspended launch")
    import ctypes
    from ctypes import wintypes

    ntdll = ctypes.WinDLL("ntdll")
    ntdll.NtResumeProcess.argtypes = [wintypes.HANDLE]
    ntdll.NtResumeProcess.restype = ctypes.c_long
    process_handle = wintypes.HANDLE(int(process._handle))  # type: ignore[attr-defined]
    status = ntdll.NtResumeProcess(process_handle)
    if status != 0:
        raise OSError(status, "NtResumeProcess failed")


def supervise_fresh375_run(
    *,
    pre_run_anchor_path: Path,
    expected_anchor_sha256: str,
    fresh_plan_path: Path,
    source_jsonl: Path,
    runtime_root: Path,
    live_result_path: Path,
    live_manifest_path: Path,
    live_checkpoint_path: Path,
    live_pending_path: Path,
    supervisor_start_event_path: Path,
    snapshot_result_path: Path,
    snapshot_manifest_path: Path,
    receipt_path: Path,
    final_verification_path: Path,
    log_dir: Path,
    dashboard_url: str = "http://127.0.0.1:8080",
    poll_interval_seconds: float = 1.0,
    timeout_seconds: float = 14_400.0,
) -> dict[str, Any]:
    if os.name != "nt":
        raise RuntimeError("fresh375 production supervisor is Windows-only")
    if poll_interval_seconds <= 0 or timeout_seconds <= 0:
        raise ValueError("fresh375 supervisor poll/timeout must be positive")
    if FRESH375_RUNTIME_BINDING_ECHO_IMPLEMENTED is not True:
        raise RuntimeError(
            "fresh375 dispatch forbidden: expert_main manifest/row binding-token echo "
            "wiring is not implemented in the frozen Loop641 runtime"
        )
    pre_run_anchor = _load_json(pre_run_anchor_path)
    fresh_plan = _load_json(fresh_plan_path)
    fresh_plan["plan_path"] = str(fresh_plan_path)
    source_rows = _load_jsonl(source_jsonl)
    anchor_binding, plan_artifact, execution_contract = _fresh_anchor_plan_binding(
        pre_run_anchor=pre_run_anchor,
        pre_run_anchor_path=pre_run_anchor_path,
        expected_anchor_sha256=expected_anchor_sha256,
        fresh_plan=fresh_plan,
        fresh_plan_path=fresh_plan_path,
        source_rows=source_rows,
        source_jsonl=source_jsonl,
        runtime_root=runtime_root,
        dashboard_url=dashboard_url,
        allow_untrusted_test_roots=False,
    )
    docs_root = (ROOT / "docs/devs").resolve()
    run_root = PRODUCTION_PANEL_PATH.parents[1]
    review_root = (run_root / "review").resolve()
    for path in (supervisor_start_event_path, receipt_path, final_verification_path):
        if docs_root not in path.resolve().parents:
            raise ValueError("fresh375 supervisor report path is outside docs/devs")
    for path in (snapshot_result_path, snapshot_manifest_path):
        if review_root not in path.resolve().parents:
            raise ValueError("fresh375 snapshot path is outside run review root")
    stdout_path = log_dir / "fresh375_supervisor.stdout.log"
    stderr_path = log_dir / "fresh375_supervisor.stderr.log"
    validate_fresh375_supervisor_output_preflight(
        immutable_input_paths=[pre_run_anchor_path, fresh_plan_path, source_jsonl],
        execution_contract=execution_contract,
        live_result_path=live_result_path,
        live_manifest_path=live_manifest_path,
        live_checkpoint_path=live_checkpoint_path,
        live_pending_path=live_pending_path,
        supervisor_start_event_path=supervisor_start_event_path,
        snapshot_result_path=snapshot_result_path,
        snapshot_manifest_path=snapshot_manifest_path,
        receipt_path=receipt_path,
        final_verification_path=final_verification_path,
        stdout_log_path=stdout_path,
        stderr_log_path=stderr_path,
    )
    binding_token = secrets.token_hex(32)
    binding_token_commitment = _binding_token_commitment(binding_token)
    anchored_env, anchored_env_binding = build_fresh375_child_environment(
        anchored_runtime_env=execution_contract["effective_env"],
    )
    if (
        anchored_env_binding
        != execution_contract["child_environment_without_binding_token"]
    ):
        raise ValueError("fresh375 OS/runtime environment drifted after pre-run anchor")
    env, child_environment_binding = build_fresh375_child_environment(
        anchored_runtime_env=execution_contract["effective_env"],
        binding_token=binding_token,
    )
    command = list(execution_contract["resolved_command_argv"])
    executable = Path(execution_contract["executable"]["path"])
    if (
        not executable.is_file()
        or _sha256(executable) != execution_contract["executable"]["byte_sha256"]
        or str(runtime_root.resolve()) != execution_contract["cwd"]
    ):
        raise ValueError("fresh375 executable bytes or cwd drifted after pre-run anchor")
    log_dir.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    process: subprocess.Popen[Any] | None = None
    resumed = False
    with stdout_path.open("xb") as stdout_handle, stderr_path.open("xb") as stderr_handle:
        try:
            creation_flags = WINDOWS_CREATE_NO_WINDOW | WINDOWS_CREATE_SUSPENDED
            process = subprocess.Popen(
                command,
                cwd=runtime_root,
                env=env,
                stdout=stdout_handle,
                stderr=stderr_handle,
                stdin=subprocess.DEVNULL,
                creationflags=creation_flags,
                close_fds=True,
                shell=False,
            )
            process_handle_value = int(process._handle)  # type: ignore[attr-defined]
            state = _process_state_windows(
                process.pid,
                process_handle=process_handle_value,
            )
            if state.get("alive") is not True or state.get("creation_time_unix") is None:
                raise ValueError("fresh375 suspended child process binding unavailable")
            if (
                state.get("handle_source") != "Popen._handle"
                or state.get("handle_value") != process_handle_value
            ):
                raise ValueError("fresh375 suspended child did not use the Popen handle")
            event = build_fresh375_supervisor_start_event(
                pre_run_anchor_binding=anchor_binding,
                plan_artifact=plan_artifact,
                execution_contract=execution_contract,
                binding_token_commitment=binding_token_commitment,
                child_environment_binding=child_environment_binding,
                process_id=process.pid,
                process_creation_time_unix=float(state["creation_time_unix"]),
                process_handle_value=process_handle_value,
                supervisor_process_id=os.getpid(),
                live_result_path=live_result_path,
                live_manifest_path=live_manifest_path,
                live_checkpoint_path=live_checkpoint_path,
                live_pending_path=live_pending_path,
                snapshot_result_path=snapshot_result_path,
                snapshot_manifest_path=snapshot_manifest_path,
                receipt_path=receipt_path,
                final_verification_path=final_verification_path,
                stdout_log_path=stdout_path,
                stderr_log_path=stderr_path,
            )
            _write_json_exclusive(supervisor_start_event_path, event)
            validate_fresh375_supervisor_start_event(
                _load_json(supervisor_start_event_path),
                event_path=supervisor_start_event_path,
            )
            _resume_suspended_windows_process(process)
            resumed = True
            bound_process_state = _BoundPopenStateProvider(process)

            receipt: dict[str, Any] | None = None
            while receipt is None:
                if time.monotonic() - started > timeout_seconds:
                    raise TimeoutError("fresh375 supervisor timed out before durable snapshot")
                if live_manifest_path.is_file() and live_result_path.is_file():
                    try:
                        live_manifest = _load_json(live_manifest_path)
                        if (
                            live_manifest.get("large_run_complete") is True
                            or int(live_manifest.get("completed_count") or 0) >= len(source_rows)
                        ):
                            raise ValueError(
                                "fresh375 completed before supervised run-start snapshot"
                            )
                        if int(live_manifest.get("flushed_count") or 0) > 0:
                            receipt = create_fresh375_run_start_snapshots_and_receipt(
                                pre_run_anchor=pre_run_anchor,
                                pre_run_anchor_path=pre_run_anchor_path,
                                expected_anchor_sha256=expected_anchor_sha256,
                                supervisor_start_event=event,
                                supervisor_start_event_path=supervisor_start_event_path,
                                live_result_path=live_result_path,
                                live_manifest_path=live_manifest_path,
                                live_checkpoint_path=live_checkpoint_path,
                                live_pending_path=live_pending_path,
                                snapshot_result_path=snapshot_result_path,
                                snapshot_manifest_path=snapshot_manifest_path,
                                receipt_path=receipt_path,
                                source_rows=source_rows,
                                source_jsonl=source_jsonl,
                                fresh_plan=fresh_plan,
                                fresh_plan_path=fresh_plan_path,
                                runtime_root=runtime_root,
                                process_state_provider=bound_process_state,
                                dashboard_url=dashboard_url,
                            )
                    except (json.JSONDecodeError, FileNotFoundError):
                        pass
                if receipt is None and process.poll() is not None:
                    raise ValueError("fresh375 child exited before durable run-start snapshot")
                if receipt is None:
                    time.sleep(min(poll_interval_seconds, 5.0))

            remaining = max(0.1, timeout_seconds - (time.monotonic() - started))
            exit_code = process.wait(timeout=remaining)
            final_rows = _rows_from_json_or_jsonl(live_result_path, "fresh375 final result")
            final_manifest = _load_json(live_manifest_path)
            final_checkpoint_rows = _load_jsonl(live_checkpoint_path)
            final_pending = _load_json(live_pending_path)
            for path in (
                live_result_path,
                live_manifest_path,
                live_checkpoint_path,
                live_pending_path,
            ):
                path.chmod(stat.S_IREAD)
            verification = build_fresh375_final_continuity_verification(
                receipt=receipt,
                receipt_path=receipt_path,
                final_rows=final_rows,
                final_result_path=live_result_path,
                final_manifest=final_manifest,
                final_manifest_path=live_manifest_path,
                final_checkpoint_rows=final_checkpoint_rows,
                final_checkpoint_path=live_checkpoint_path,
                final_pending=final_pending,
                final_pending_path=live_pending_path,
                source_rows=source_rows,
                process_exit_code=exit_code,
            )
            _write_json_exclusive(final_verification_path, verification)
            return {
                "gate": "GO",
                "run_id": verification["run_id"],
                "process_id": process.pid,
                "start_event": str(supervisor_start_event_path),
                "run_start_receipt": str(receipt_path),
                "final_continuity": str(final_verification_path),
            }
        except Exception:
            if process is not None and process.poll() is None:
                if not resumed:
                    try:
                        _resume_suspended_windows_process(process)
                    except Exception:
                        pass
                process.kill()
                process.wait(timeout=30)
            raise


def _write_json_exclusive(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    path.chmod(stat.S_IREAD)
    return {
        "report_type": "interrupted_merge_trust_anchor_write_receipt",
        "path": str(path.resolve()),
        "sha256": _sha256(path),
        "size_bytes": path.stat().st_size,
        "read_only": not bool(path.stat().st_mode & stat.S_IWRITE),
    }


def _fresh_anchor_plan_binding(
    *,
    pre_run_anchor: dict[str, Any],
    pre_run_anchor_path: Path,
    expected_anchor_sha256: str,
    fresh_plan: dict[str, Any],
    fresh_plan_path: Path,
    source_rows: list[dict[str, Any]],
    source_jsonl: Path,
    runtime_root: Path,
    dashboard_url: str,
    allow_untrusted_test_roots: bool,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    if _load_json(pre_run_anchor_path) != pre_run_anchor:
        raise ValueError("fresh375 pre-run anchor parsed payload mismatch")
    if pre_run_anchor_path.stat().st_mode & stat.S_IWRITE:
        raise ValueError("fresh375 pre-run anchor must be read-only")
    actual_anchor_sha256 = _sha256(pre_run_anchor_path)
    if actual_anchor_sha256 != _require_sha256(
        expected_anchor_sha256, "fresh375 pre-run anchor"
    ):
        raise ValueError("fresh375 pre-run anchor sha256 mismatch")
    if (
        pre_run_anchor.get("topology", {}).get("profile") != "fresh375"
        or pre_run_anchor.get("binding_phase") != "pre_run_release_anchor"
        or pre_run_anchor.get("anchor_version") != TRUST_ANCHOR_VERSION
    ):
        raise ValueError("fresh375 pre-run anchor profile/phase/version mismatch")
    payload_without_hash = dict(pre_run_anchor)
    supplied_payload_hash = payload_without_hash.pop("anchor_payload_sha256", None)
    if supplied_payload_hash != _canonical_hash(payload_without_hash):
        raise ValueError("fresh375 pre-run anchor payload digest mismatch")

    plan_payload = {key: value for key, value in fresh_plan.items() if key != "plan_path"}
    if _load_json(fresh_plan_path) != plan_payload:
        raise ValueError("fresh375 plan parsed payload mismatch")
    plan_artifact = _immutable_json_artifact(path=fresh_plan_path, payload=plan_payload)
    anchored_plan = pre_run_anchor.get("immutable_components", {}).get("fresh_plan")
    if anchored_plan != plan_artifact:
        raise ValueError("fresh375 plan bytes/canonical payload changed after pre-run anchor")
    execution_contract = fresh375_plan_execution_contract(
        fresh_plan=fresh_plan,
        fresh_plan_path=fresh_plan_path,
        source_jsonl=source_jsonl,
        runtime_root=runtime_root,
        dashboard_url=dashboard_url,
    )
    if pre_run_anchor.get("execution_contract") != execution_contract:
        raise ValueError("fresh375 plan execution contract changed after pre-run anchor")
    stable_projection = pre_run_anchor.get("stable_projection")
    if not isinstance(stable_projection, dict):
        raise ValueError("fresh375 pre-run stable projection missing")
    release_fingerprint = _canonical_hash(stable_projection)
    if (
        pre_run_anchor.get("release_fingerprint_sha256") != release_fingerprint
        or pre_run_anchor.get("stable_runtime_fingerprint_sha256") != release_fingerprint
        or stable_projection.get("fresh_plan_artifact") != plan_artifact
        or stable_projection.get("execution_contract_sha256")
        != _canonical_hash(execution_contract)
    ):
        raise ValueError("fresh375 release fingerprint/plan binding mismatch")
    code_tree = runtime_code_tree_projection(runtime_root)
    if (
        pre_run_anchor.get("runtime_code_tree") != code_tree
        or pre_run_anchor.get("runtime_code_tree_sha256") != code_tree["tree_sha256"]
    ):
        raise ValueError("fresh375 runtime code tree changed after pre-run anchor")
    source_ids = [_post_id(row) for row in source_rows]
    source_binding = pre_run_anchor.get("fixed_artifacts", {}).get("source_panel")
    if (
        len(set(source_ids)) != len(source_ids)
        or not isinstance(source_binding, dict)
        or Path(str(source_binding.get("path") or "")).resolve() != source_jsonl.resolve()
        or source_binding.get("sha256") != _sha256(source_jsonl)
        or source_binding.get("row_count") != len(source_rows)
        or source_binding.get("post_id_order_sha256") != _canonical_hash(source_ids)
        or source_binding.get("post_id_set_sha256") != _canonical_hash(sorted(source_ids))
    ):
        raise ValueError("fresh375 source input does not match pre-run anchor")
    if not allow_untrusted_test_roots and (
        source_jsonl.resolve() != PRODUCTION_PANEL_PATH
        or _sha256(source_jsonl) != PRODUCTION_PANEL_SHA256
    ):
        raise ValueError("fresh375 production source input root mismatch")
    return (
        {
            "path": str(pre_run_anchor_path.resolve()),
            "sha256": actual_anchor_sha256,
            "anchor_version": pre_run_anchor["anchor_version"],
            "release_fingerprint_sha256": release_fingerprint,
        },
        plan_artifact,
        execution_contract,
    )


def _validate_hex_nonce(value: str) -> str:
    text = str(value or "").strip().lower()
    if len(text) != 64 or any(char not in "0123456789abcdef" for char in text):
        raise ValueError("fresh375 supervisor nonce must be 32 random bytes")
    return text


def _process_state_windows(
    pid: int,
    *,
    process_handle: int | None = None,
) -> dict[str, Any]:
    if os.name != "nt":
        raise RuntimeError("fresh375 production supervisor process binding requires Windows")
    import ctypes
    from ctypes import wintypes

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    STILL_ACTIVE = 259
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.GetProcessTimes.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
    ]
    kernel32.GetProcessTimes.restype = wintypes.BOOL
    kernel32.GetExitCodeProcess.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.DWORD),
    ]
    kernel32.GetExitCodeProcess.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    owns_handle = process_handle is None
    handle = (
        kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
        if owns_handle
        else wintypes.HANDLE(int(process_handle))
    )
    if not handle:
        return {
            "alive": False,
            "pid": int(pid),
            "creation_time_unix": None,
            "handle_source": "OpenProcess" if owns_handle else "Popen._handle",
        }
    try:
        creation = wintypes.FILETIME()
        exit_time = wintypes.FILETIME()
        kernel = wintypes.FILETIME()
        user = wintypes.FILETIME()
        if not kernel32.GetProcessTimes(
            handle,
            ctypes.byref(creation),
            ctypes.byref(exit_time),
            ctypes.byref(kernel),
            ctypes.byref(user),
        ):
            raise OSError(ctypes.get_last_error(), "GetProcessTimes failed")
        exit_code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            raise OSError(ctypes.get_last_error(), "GetExitCodeProcess failed")
        ticks = (creation.dwHighDateTime << 32) | creation.dwLowDateTime
        creation_unix = ticks / 10_000_000 - 11_644_473_600
        return {
            "alive": exit_code.value == STILL_ACTIVE,
            "pid": int(pid),
            "creation_time_unix": creation_unix,
            "handle_value": int(
                handle if isinstance(handle, int) else (handle.value or 0)
            ),
            "handle_source": "OpenProcess" if owns_handle else "Popen._handle",
        }
    finally:
        if owns_handle and not kernel32.CloseHandle(handle):
            raise OSError(ctypes.get_last_error(), "CloseHandle failed")


class _BoundPopenStateProvider:
    """Production-only process-state capability tied to one live Popen handle."""

    def __init__(self, process: subprocess.Popen[Any]) -> None:
        self._process = process
        self._pid = int(process.pid)
        self._handle = int(process._handle)  # type: ignore[attr-defined]

    def __call__(self, pid: int) -> dict[str, Any]:
        if int(pid) != self._pid:
            return {"alive": False, "pid": int(pid)}
        return _process_state_windows(
            self._pid,
            process_handle=self._handle,
        )


def build_fresh375_supervisor_start_event(
    *,
    pre_run_anchor_binding: dict[str, Any],
    plan_artifact: dict[str, Any],
    execution_contract: dict[str, Any],
    binding_token_commitment: str,
    child_environment_binding: dict[str, Any],
    process_id: int,
    process_creation_time_unix: float,
    process_handle_value: int,
    supervisor_process_id: int,
    live_result_path: Path,
    live_manifest_path: Path,
    live_checkpoint_path: Path,
    live_pending_path: Path,
    snapshot_result_path: Path,
    snapshot_manifest_path: Path,
    receipt_path: Path,
    final_verification_path: Path,
    stdout_log_path: Path,
    stderr_log_path: Path,
    generated_at: str | None = None,
) -> dict[str, Any]:
    binding_token_commitment = _require_sha256(
        binding_token_commitment, "fresh375 binding token commitment"
    )
    if (
        not isinstance(child_environment_binding, dict)
        or child_environment_binding.get("value_sha256", {}).get(
            FRESH375_BINDING_TOKEN_ENV
        )
        != binding_token_commitment
        or FRESH375_BINDING_TOKEN_ENV
        not in child_environment_binding.get("names", [])
    ):
        raise ValueError("fresh375 child environment does not bind the token commitment")
    expected_output = Path(execution_contract["output_path"]).resolve()
    expected_manifest = Path(execution_contract["manifest_path"]).resolve()
    expected_checkpoint = Path(execution_contract["checkpoint_path"]).resolve()
    expected_pending = Path(execution_contract["pending_path"]).resolve()
    if (
        live_result_path.resolve() != expected_output
        or live_manifest_path.resolve() != expected_manifest
        or live_checkpoint_path.resolve() != expected_checkpoint
        or live_pending_path.resolve() != expected_pending
    ):
        raise ValueError("fresh375 live artifact paths differ from anchored plan")
    all_paths = [
        live_result_path.resolve(),
        live_manifest_path.resolve(),
        live_checkpoint_path.resolve(),
        live_pending_path.resolve(),
        snapshot_result_path.resolve(),
        snapshot_manifest_path.resolve(),
        receipt_path.resolve(),
        final_verification_path.resolve(),
        stdout_log_path.resolve(),
        stderr_log_path.resolve(),
    ]
    if len(set(all_paths)) != len(all_paths):
        raise ValueError("fresh375 live/snapshot/receipt/final/log paths must be distinct")
    payload: dict[str, Any] = {
        "report_type": "fresh375_supervisor_start_event",
        "schema_version": FRESH375_START_EVENT_SCHEMA_VERSION,
        "generated_at": generated_at or datetime.now().astimezone().isoformat(),
        "gate": "GO",
        "finalized": True,
        "pre_dispatch_binding_token_commitment": binding_token_commitment,
        "pre_run_anchor": pre_run_anchor_binding,
        "fresh_plan": plan_artifact,
        "execution_binding": {
            "command_argv": execution_contract["command_argv"],
            "command_argv_sha256": execution_contract["command_argv_sha256"],
            "resolved_command_argv": execution_contract["resolved_command_argv"],
            "resolved_command_argv_sha256": execution_contract[
                "resolved_command_argv_sha256"
            ],
            "executable": execution_contract["executable"],
            "cwd": execution_contract["cwd"],
            "input_path": execution_contract["input_path"],
            "output_path": execution_contract["output_path"],
            "manifest_path": execution_contract["manifest_path"],
            "checkpoint_path": execution_contract["checkpoint_path"],
            "pending_path": execution_contract["pending_path"],
            "required_env": execution_contract["required_env"],
            "env_overrides": execution_contract["env_overrides"],
            "child_environment": child_environment_binding,
            "child_environment_policy": execution_contract[
                "child_environment_policy"
            ],
            "binding_echo_contract": execution_contract["binding_echo_contract"],
            "runtime_contract": execution_contract["runtime_contract"],
        },
        "process_binding": {
            "pid": int(process_id),
            "creation_time_unix": float(process_creation_time_unix),
            "popen_process_handle_value": int(process_handle_value),
            "state_and_resume_use_same_popen_handle": True,
            "supervisor_pid": int(supervisor_process_id),
            "create_suspended_flag": WINDOWS_CREATE_SUSPENDED,
            "create_no_window_flag": WINDOWS_CREATE_NO_WINDOW,
            "handle_inheritance": {
                "close_fds": True,
                "only_explicit_stdio_handles": True,
                "shell": False,
                "log_files_created_exclusive": True,
            },
            "created_suspended_before_start_event": True,
            "resumed_only_after_start_event_write": True,
        },
        "artifact_paths": {
            "live_result": str(live_result_path.resolve()),
            "live_manifest": str(live_manifest_path.resolve()),
            "live_checkpoint": str(live_checkpoint_path.resolve()),
            "live_pending": str(live_pending_path.resolve()),
            "snapshot_result": str(snapshot_result_path.resolve()),
            "snapshot_manifest": str(snapshot_manifest_path.resolve()),
            "run_start_receipt": str(receipt_path.resolve()),
            "final_continuity": str(final_verification_path.resolve()),
            "stdout_log": str(stdout_log_path.resolve()),
            "stderr_log": str(stderr_log_path.resolve()),
        },
        "approval_boundary": {
            "mtime_and_generated_at_are_diagnostic_only": True,
            "live_partial_bytes_are_not_receipt_trust_roots": True,
            "production_full_scan_approval": False,
        },
    }
    payload["start_event_payload_sha256"] = _canonical_hash(payload)
    return payload


def validate_fresh375_supervisor_start_event(
    event: dict[str, Any],
    *,
    event_path: Path | None = None,
) -> dict[str, Any]:
    if (
        event.get("report_type") != "fresh375_supervisor_start_event"
        or event.get("schema_version") != FRESH375_START_EVENT_SCHEMA_VERSION
        or event.get("gate") != "GO"
        or event.get("finalized") is not True
    ):
        raise ValueError("fresh375 supervisor start event type/version/gate invalid")
    supplied = str(event.get("start_event_payload_sha256") or "")
    without_digest = dict(event)
    without_digest.pop("start_event_payload_sha256", None)
    if supplied != _canonical_hash(without_digest):
        raise ValueError("fresh375 supervisor start event self-digest mismatch")
    commitment = _require_sha256(
        str(event.get("pre_dispatch_binding_token_commitment") or ""),
        "fresh375 binding token commitment",
    )
    if "pre_dispatch_nonce" in event:
        raise ValueError("fresh375 start event leaks a raw nonce")
    execution = event.get("execution_binding")
    if (
        not isinstance(execution, dict)
        or execution.get("child_environment", {}).get("value_sha256", {}).get(
            FRESH375_BINDING_TOKEN_ENV
        )
        != commitment
        or execution.get("child_environment", {}).get("values_redacted") is not True
    ):
        raise ValueError("fresh375 start event child environment commitment invalid")
    process = event.get("process_binding")
    if (
        not isinstance(process, dict)
        or not isinstance(process.get("pid"), int)
        or not isinstance(process.get("creation_time_unix"), (int, float))
        or not isinstance(process.get("popen_process_handle_value"), int)
        or process.get("state_and_resume_use_same_popen_handle") is not True
        or process.get("create_suspended_flag") != WINDOWS_CREATE_SUSPENDED
        or process.get("create_no_window_flag") != WINDOWS_CREATE_NO_WINDOW
        or process.get("handle_inheritance")
        != {
            "close_fds": True,
            "only_explicit_stdio_handles": True,
            "shell": False,
            "log_files_created_exclusive": True,
        }
        or process.get("created_suspended_before_start_event") is not True
        or process.get("resumed_only_after_start_event_write") is not True
    ):
        raise ValueError("fresh375 supervisor process binding invalid")
    if event_path is not None:
        if not event_path.is_file() or event_path.stat().st_mode & stat.S_IWRITE:
            raise ValueError("fresh375 supervisor start event is missing or writable")
        if _load_json(event_path) != event:
            raise ValueError("fresh375 supervisor start event file payload mismatch")
    return {
        "gate": "GO",
        "payload_sha256": supplied,
        "pid": process["pid"],
        "creation_time_unix": process["creation_time_unix"],
        "process_handle_value": process["popen_process_handle_value"],
        "supervisor_pid": process["supervisor_pid"],
        "binding_token_commitment": commitment,
    }


def _validate_fresh375_start_execution_binding(
    *,
    event: dict[str, Any],
    execution_contract: dict[str, Any],
    binding_token_commitment: str,
) -> dict[str, Any]:
    execution = event.get("execution_binding")
    if not isinstance(execution, dict):
        raise ValueError("fresh375 start event execution binding missing")
    expected = {
        key: execution_contract[key]
        for key in (
            "command_argv",
            "command_argv_sha256",
            "resolved_command_argv",
            "resolved_command_argv_sha256",
            "executable",
            "cwd",
            "input_path",
            "output_path",
            "manifest_path",
            "checkpoint_path",
            "pending_path",
            "required_env",
            "env_overrides",
            "child_environment_policy",
            "binding_echo_contract",
            "runtime_contract",
        )
    }
    if any(execution.get(key) != value for key, value in expected.items()):
        raise ValueError("fresh375 start event command/input/output/env/runtime drift")
    child = execution.get("child_environment")
    anchored = execution_contract["child_environment_without_binding_token"]
    if not isinstance(child, dict):
        raise ValueError("fresh375 child environment binding missing")
    expected_names = sorted(
        [*anchored["names"], FRESH375_BINDING_TOKEN_ENV]
    )
    if child.get("names") != expected_names or child.get("values_redacted") is not True:
        raise ValueError("fresh375 child environment names drift")
    actual_value_digests = child.get("value_sha256")
    if not isinstance(actual_value_digests, dict):
        raise ValueError("fresh375 child environment value digests missing")
    for name, digest in anchored["value_sha256"].items():
        if actual_value_digests.get(name) != digest:
            raise ValueError("fresh375 child environment anchored value drift")
    if actual_value_digests.get(FRESH375_BINDING_TOKEN_ENV) != binding_token_commitment:
        raise ValueError("fresh375 child environment binding token commitment mismatch")
    if child.get("variable_count") != len(expected_names) or not child.get("block_sha256"):
        raise ValueError("fresh375 child environment block digest invalid")
    return child


def _validate_fresh375_bound_process_state(
    *,
    state: dict[str, Any],
    start_binding: dict[str, Any],
    allow_untrusted_test_roots: bool,
) -> None:
    if (
        not isinstance(state, dict)
        or state.get("alive") is not True
        or state.get("pid") != start_binding["pid"]
        or abs(
            float(state.get("creation_time_unix") or 0)
            - float(start_binding["creation_time_unix"])
        )
        > 0.001
        or state.get("handle_value") != start_binding["process_handle_value"]
        or state.get("handle_source") != "Popen._handle"
    ):
        raise ValueError("fresh375 supervisor process is not the bound live Popen handle")
    if (
        not allow_untrusted_test_roots
        and start_binding["supervisor_pid"] != os.getpid()
    ):
        raise ValueError("fresh375 start event was not created by this live supervisor")


def build_fresh375_run_start_binding_receipt(
    *,
    pre_run_anchor: dict[str, Any],
    pre_run_anchor_path: Path,
    expected_anchor_sha256: str,
    supervisor_start_event: dict[str, Any],
    supervisor_start_event_path: Path,
    snapshot_manifest: dict[str, Any],
    snapshot_manifest_path: Path,
    snapshot_rows: list[dict[str, Any]],
    snapshot_result_path: Path,
    source_rows: list[dict[str, Any]],
    source_jsonl: Path,
    fresh_plan: dict[str, Any],
    fresh_plan_path: Path,
    runtime_root: Path,
    process_state_provider: Callable[[int], dict[str, Any]] = _process_state_windows,
    dashboard_url: str = "http://127.0.0.1:8080",
    generated_at: str | None = None,
    allow_untrusted_test_roots: bool = False,
) -> dict[str, Any]:
    if (
        not allow_untrusted_test_roots
        and not isinstance(process_state_provider, _BoundPopenStateProvider)
    ):
        raise ValueError(
            "fresh375 production receipt requires the supervisor-owned Popen capability"
        )
    anchor_binding, plan_artifact, execution_contract = _fresh_anchor_plan_binding(
        pre_run_anchor=pre_run_anchor,
        pre_run_anchor_path=pre_run_anchor_path,
        expected_anchor_sha256=expected_anchor_sha256,
        fresh_plan=fresh_plan,
        fresh_plan_path=fresh_plan_path,
        source_rows=source_rows,
        source_jsonl=source_jsonl,
        runtime_root=runtime_root,
        dashboard_url=dashboard_url,
        allow_untrusted_test_roots=allow_untrusted_test_roots,
    )
    start_binding = validate_fresh375_supervisor_start_event(
        supervisor_start_event,
        event_path=supervisor_start_event_path,
    )
    if supervisor_start_event.get("pre_run_anchor") != anchor_binding:
        raise ValueError("fresh375 start event/pre-run anchor binding mismatch")
    if supervisor_start_event.get("fresh_plan") != plan_artifact:
        raise ValueError("fresh375 start event/plan binding mismatch")
    _validate_fresh375_start_execution_binding(
        event=supervisor_start_event,
        execution_contract=execution_contract,
        binding_token_commitment=start_binding["binding_token_commitment"],
    )
    process_state = process_state_provider(start_binding["pid"])
    _validate_fresh375_bound_process_state(
        state=process_state,
        start_binding=start_binding,
        allow_untrusted_test_roots=allow_untrusted_test_roots,
    )

    paths = supervisor_start_event.get("artifact_paths")
    if not isinstance(paths, dict):
        raise ValueError("fresh375 start event artifact paths missing")
    live_result = Path(str(paths.get("live_result") or "")).resolve()
    live_manifest = Path(str(paths.get("live_manifest") or "")).resolve()
    if (
        snapshot_result_path.resolve()
        != Path(str(paths.get("snapshot_result") or "")).resolve()
        or snapshot_manifest_path.resolve()
        != Path(str(paths.get("snapshot_manifest") or "")).resolve()
        or snapshot_result_path.resolve() in {live_result, live_manifest}
        or snapshot_manifest_path.resolve() in {live_result, live_manifest}
        or snapshot_result_path.resolve() == snapshot_manifest_path.resolve()
    ):
        raise ValueError("fresh375 snapshot paths are not distinct from live paths")
    if _rows_from_json_or_jsonl(snapshot_result_path, "fresh375 result snapshot") != snapshot_rows:
        raise ValueError("fresh375 result snapshot file/payload mismatch")
    if _load_json(snapshot_manifest_path) != snapshot_manifest:
        raise ValueError("fresh375 manifest snapshot file/payload mismatch")
    if (
        snapshot_result_path.stat().st_mode & stat.S_IWRITE
        or snapshot_manifest_path.stat().st_mode & stat.S_IWRITE
    ):
        raise ValueError("fresh375 run-start snapshots must be read-only")
    expected_rows = int(pre_run_anchor.get("expected_counts", {}).get("fresh_rows") or 0)
    completed = snapshot_manifest.get("completed_count")
    flushed = snapshot_manifest.get("flushed_count")
    pending = snapshot_manifest.get("pending_count")
    failed = snapshot_manifest.get("failed_count")
    if (
        any(
            isinstance(value, bool) or not isinstance(value, int)
            for value in (completed, flushed, pending, failed)
        )
        or snapshot_manifest.get("input_post_count") != expected_rows
        or not (0 < completed < expected_rows)
        or not (0 < flushed <= completed)
        or pending != completed - flushed
        or failed != 0
        or snapshot_manifest.get("large_run_complete") is not False
        or len(snapshot_rows) != flushed
    ):
        raise ValueError("fresh375 snapshots do not prove an incomplete durable flush")
    manifest_run_id = str(snapshot_manifest.get("run_id") or "").strip()
    if not manifest_run_id:
        raise ValueError("fresh375 snapshot manifest run_id is empty")
    anchored_run_id = pre_run_anchor.get("run_ids", {}).get("fresh")
    if anchored_run_id not in (None, "") and str(anchored_run_id) != manifest_run_id:
        raise ValueError("fresh375 snapshot run_id differs from pre-run anchor")
    if [_post_id(row) for row in snapshot_rows] != [
        _post_id(row) for row in source_rows[:flushed]
    ]:
        raise ValueError("fresh375 result snapshot is not the ordered source prefix")
    _validate_fresh375_binding_token_echo(
        rows=snapshot_rows,
        manifest=snapshot_manifest,
        expected_commitment=start_binding["binding_token_commitment"],
        label="fresh375 immutable snapshot",
    )
    row_signature = _uniform_row_signature(snapshot_rows, "fresh375 result snapshot")
    if _uniform_row_value(snapshot_rows, "fresh375 result snapshot", "run_id") != manifest_run_id:
        raise ValueError("fresh375 snapshot row/manifest run_id mismatch")
    config_hash = str(
        _uniform_row_value(snapshot_rows, "fresh375 result snapshot", "config_hash") or ""
    ).strip()
    if not config_hash:
        raise ValueError("fresh375 result snapshot config_hash is empty")
    _validate_row_manifest_binding(row_signature, snapshot_manifest, "fresh375 snapshot")
    _validate_plan_manifest_binding(
        execution_contract["plan_signature"],
        snapshot_manifest,
        "fresh375 snapshot",
    )
    expected_prompt = pre_run_anchor.get("prompt_version_binding", {}).get("expected")
    if row_signature.get("prompt_version") != expected_prompt:
        raise ValueError("fresh375 snapshot prompt version mismatch")
    receipt: dict[str, Any] = {
        "report_type": "fresh375_actual_run_start_binding_receipt",
        "schema_version": FRESH375_RUN_START_SCHEMA_VERSION,
        "binding_phase": "supervised_immutable_first_durable_flush",
        "generated_at": generated_at or datetime.now().astimezone().isoformat(),
        "gate": "GO",
        "finalized": True,
        "run_id": manifest_run_id,
        "pre_run_anchor": anchor_binding,
        "release_fingerprint_sha256": anchor_binding["release_fingerprint_sha256"],
        "runtime_code_tree_sha256": pre_run_anchor["runtime_code_tree_sha256"],
        "fresh_plan": plan_artifact,
        "supervisor_start_event": _immutable_json_artifact(
            path=supervisor_start_event_path,
            payload=supervisor_start_event,
        ),
        "process_continuity": {
            "pid": start_binding["pid"],
            "creation_time_unix": start_binding["creation_time_unix"],
            "popen_process_handle_value": start_binding["process_handle_value"],
            "alive_at_snapshot": True,
            "binding_token_commitment": start_binding[
                "binding_token_commitment"
            ],
            "start_event_payload_sha256": start_binding["payload_sha256"],
        },
        "source_input": _row_artifact(path=source_jsonl, rows=source_rows),
        "snapshot_schema_version": FRESH375_SNAPSHOT_SCHEMA_VERSION,
        "snapshot_result": _row_artifact(
            path=snapshot_result_path,
            rows=snapshot_rows,
        ),
        "snapshot_manifest": _immutable_json_artifact(
            path=snapshot_manifest_path,
            payload=snapshot_manifest,
        ),
        "observed_counts": {
            "input_post_count": expected_rows,
            "completed_count": completed,
            "flushed_count": flushed,
            "pending_count": pending,
            "failed_count": failed,
            "large_run_complete": False,
        },
        "prompt_version_binding": {
            "expected": expected_prompt,
            "actual": row_signature["prompt_version"],
            "gate": "GO",
        },
        "row_signature": row_signature,
        "manifest_signature": _manifest_signature(snapshot_manifest),
        "plan_signature_sha256": _canonical_hash(execution_contract["plan_signature"]),
        "config_binding": {
            "uniform_row_config_hash": config_hash,
            "gate": "GO",
        },
        "live_artifact_diagnostics": {
            "result_path": str(live_result),
            "manifest_path": str(live_manifest),
            "live_partial_bytes_hashed_or_bound": False,
            "mtime_is_gate": False,
        },
        "finalization": {
            "state": "FINALIZED",
            "marker": "FRESH375_SUPERVISED_SNAPSHOT_BOUND",
            "self_digest_algorithm": "sha256(canonical_json_without_receipt_payload_sha256)",
        },
        "approval_boundary": {
            "run_start_binding_is_not_completion_or_semantic_approval": True,
            "dedicated_immutable_snapshots_are_only_partial_runtime_trust_roots": True,
            "final_prefix_continuity_verification_required": True,
            "production_full_scan_approval": False,
        },
    }
    receipt["receipt_payload_sha256"] = _canonical_hash(receipt)
    return receipt


def validate_fresh375_run_start_binding_receipt(
    receipt: dict[str, Any],
    *,
    receipt_path: Path | None = None,
    verify_artifact_bytes: bool = False,
) -> dict[str, Any]:
    if (
        receipt.get("report_type") != "fresh375_actual_run_start_binding_receipt"
        or receipt.get("schema_version") != FRESH375_RUN_START_SCHEMA_VERSION
        or receipt.get("binding_phase")
        != "supervised_immutable_first_durable_flush"
        or receipt.get("snapshot_schema_version")
        != FRESH375_SNAPSHOT_SCHEMA_VERSION
        or receipt.get("gate") != "GO"
        or receipt.get("finalized") is not True
        or receipt.get("finalization", {}).get("marker")
        != "FRESH375_SUPERVISED_SNAPSHOT_BOUND"
    ):
        raise ValueError("fresh375 supervised receipt type/version/finalization invalid")
    supplied = str(receipt.get("receipt_payload_sha256") or "")
    without_digest = dict(receipt)
    without_digest.pop("receipt_payload_sha256", None)
    if supplied != _canonical_hash(without_digest):
        raise ValueError("fresh375 receipt self-digest mismatch")
    if not str(receipt.get("run_id") or "").strip():
        raise ValueError("fresh375 receipt run_id is empty")
    if receipt_path is not None:
        expected_path = Path(
            str(
                _load_json(
                    Path(str(receipt["supervisor_start_event"]["path"]))
                ).get("artifact_paths", {}).get("run_start_receipt")
                or ""
            )
        ).resolve()
        if receipt_path.resolve() != expected_path:
            raise ValueError("fresh375 receipt self path/start-event mismatch")
        if receipt_path.is_file() and receipt_path.stat().st_mode & stat.S_IWRITE:
            raise ValueError("fresh375 receipt file is writable")
    live = receipt.get("live_artifact_diagnostics")
    snapshot_result = receipt.get("snapshot_result")
    snapshot_manifest = receipt.get("snapshot_manifest")
    if not all(isinstance(value, dict) for value in (live, snapshot_result, snapshot_manifest)):
        raise ValueError("fresh375 receipt snapshot/live bindings missing")
    live_paths = {
        Path(str(live.get("result_path") or "")).resolve(),
        Path(str(live.get("manifest_path") or "")).resolve(),
    }
    if (
        live.get("live_partial_bytes_hashed_or_bound") is not False
        or live.get("mtime_is_gate") is not False
        or Path(str(snapshot_result.get("path") or "")).resolve() in live_paths
        or Path(str(snapshot_manifest.get("path") or "")).resolve() in live_paths
    ):
        raise ValueError("fresh375 receipt trusts live partial files or aliases snapshots")
    if verify_artifact_bytes:
        bindings = {
            "pre_run_anchor": receipt["pre_run_anchor"],
            "fresh_plan": receipt["fresh_plan"],
            "supervisor_start_event": receipt["supervisor_start_event"],
            "source_input": receipt["source_input"],
            "snapshot_result": snapshot_result,
            "snapshot_manifest": snapshot_manifest,
        }
        for name, binding in bindings.items():
            path = Path(str(binding.get("path") or ""))
            expected_hash = binding.get("byte_sha256") or binding.get("sha256")
            if (
                not path.is_file()
                or _sha256(path) != expected_hash
                or path.stat().st_mode & stat.S_IWRITE
            ):
                raise ValueError(f"fresh375 receipt immutable artifact mismatch: {name}")
            if "canonical_sha256" in binding:
                payload = (
                    _load_jsonl(path)
                    if path.suffix.lower() == ".jsonl"
                    else _load_json(path)
                )
                if _canonical_hash(payload) != binding["canonical_sha256"]:
                    raise ValueError(f"fresh375 receipt canonical artifact mismatch: {name}")
    return {
        "gate": "GO",
        "run_id": receipt["run_id"],
        "receipt_payload_sha256": supplied,
        "release_fingerprint_sha256": receipt["release_fingerprint_sha256"],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Freeze a pre-merge trust anchor from stable interrupted-run projections."
    )
    parser.add_argument(
        "--profile",
        choices=(
            "interrupted_merge_75_300",
            "fresh375",
            "fresh375_supervisor",
            "fresh375_run_start",
        ),
        default="interrupted_merge_75_300",
    )
    parser.add_argument("--source-jsonl", required=True, type=Path)
    parser.add_argument("--baseline-result", type=Path)
    parser.add_argument("--golden-manifest", type=Path)
    parser.add_argument("--recovered-json", type=Path)
    parser.add_argument("--recovery-summary", type=Path)
    parser.add_argument("--source-checkpoint", type=Path)
    parser.add_argument("--source-manifest", type=Path)
    parser.add_argument("--source-plan", type=Path)
    parser.add_argument("--residual-json", type=Path)
    parser.add_argument("--residual-input", type=Path)
    parser.add_argument("--residual-manifest", type=Path)
    parser.add_argument("--residual-plan", type=Path)
    parser.add_argument("--fresh-plan", type=Path)
    parser.add_argument("--fresh-pre-run-anchor", type=Path)
    parser.add_argument("--fresh-run-manifest", type=Path)
    parser.add_argument("--fresh-partial-result", type=Path)
    parser.add_argument("--fresh-live-result", type=Path)
    parser.add_argument("--fresh-live-manifest", type=Path)
    parser.add_argument("--fresh-live-checkpoint", type=Path)
    parser.add_argument("--fresh-live-pending", type=Path)
    parser.add_argument("--fresh-snapshot-result", type=Path)
    parser.add_argument("--fresh-snapshot-manifest", type=Path)
    parser.add_argument("--fresh-supervisor-start-event", type=Path)
    parser.add_argument("--fresh-final-verification", type=Path)
    parser.add_argument("--fresh-log-dir", type=Path)
    parser.add_argument("--dashboard-url", default="http://127.0.0.1:8080")
    parser.add_argument("--poll-interval-seconds", type=float, default=1.0)
    parser.add_argument("--timeout-seconds", type=float, default=14400.0)
    parser.add_argument("--runtime-root", type=Path, default=ROOT)
    parser.add_argument("--expected-source-run-id")
    parser.add_argument("--expected-residual-run-id")
    parser.add_argument("--expected-fresh-run-id")
    parser.add_argument("--expected-prompt-version")
    parser.add_argument("--expected-anchor-sha256")
    parser.add_argument("--expected-source-count", type=int, default=375)
    parser.add_argument("--expected-recovered-count", type=int, default=75)
    parser.add_argument("--expected-residual-count", type=int, default=300)
    parser.add_argument("--expected-source-flushed-count", type=int, default=68)
    parser.add_argument("--expected-source-pending-count", type=int, default=7)
    parser.add_argument("--expected-golden-count", type=int, default=18)
    parser.add_argument("--expected-panel-sha256")
    parser.add_argument("--expected-baseline-sha256")
    parser.add_argument("--expected-golden-sha256")
    parser.add_argument("--output-json", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.profile == "fresh375_run_start":
        raise SystemExit(
            "fresh375_run_start is disabled: use fresh375_supervisor so a suspended "
            "child, immutable start-event, one-shot snapshots, and final prefix continuity "
            "are bound by one supervisor"
        )
    if args.profile == "fresh375_supervisor":
        required = (
            "fresh_pre_run_anchor",
            "fresh_plan",
            "fresh_live_result",
            "fresh_live_manifest",
            "fresh_live_checkpoint",
            "fresh_live_pending",
            "fresh_snapshot_result",
            "fresh_snapshot_manifest",
            "fresh_supervisor_start_event",
            "fresh_final_verification",
            "fresh_log_dir",
            "expected_anchor_sha256",
        )
        missing = [name for name in required if getattr(args, name) in (None, "")]
        if missing:
            raise SystemExit(f"fresh375_supervisor missing required arguments: {missing}")
        result = supervise_fresh375_run(
            pre_run_anchor_path=args.fresh_pre_run_anchor,
            expected_anchor_sha256=args.expected_anchor_sha256,
            fresh_plan_path=args.fresh_plan,
            source_jsonl=args.source_jsonl,
            runtime_root=args.runtime_root,
            live_result_path=args.fresh_live_result,
            live_manifest_path=args.fresh_live_manifest,
            live_checkpoint_path=args.fresh_live_checkpoint,
            live_pending_path=args.fresh_live_pending,
            supervisor_start_event_path=args.fresh_supervisor_start_event,
            snapshot_result_path=args.fresh_snapshot_result,
            snapshot_manifest_path=args.fresh_snapshot_manifest,
            receipt_path=args.output_json,
            final_verification_path=args.fresh_final_verification,
            log_dir=args.fresh_log_dir,
            dashboard_url=args.dashboard_url,
            poll_interval_seconds=args.poll_interval_seconds,
            timeout_seconds=args.timeout_seconds,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    required_fixed = (
        "baseline_result",
        "golden_manifest",
        "expected_panel_sha256",
        "expected_baseline_sha256",
        "expected_golden_sha256",
    )
    missing_fixed = [name for name in required_fixed if getattr(args, name) in (None, "")]
    if missing_fixed:
        raise SystemExit(f"{args.profile} missing fixed-root arguments: {missing_fixed}")
    golden_payload = _load_json(args.golden_manifest)
    golden_rows = golden_payload.get("rows") if isinstance(golden_payload, dict) else None
    if not isinstance(golden_rows, list) or any(not isinstance(row, dict) for row in golden_rows):
        raise ValueError("golden manifest rows must be a list of objects")
    common = {
        "source_rows": _load_jsonl(args.source_jsonl),
        "baseline_rows": _rows_from_json_or_jsonl(args.baseline_result, "baseline result"),
        "golden_rows": golden_rows,
        "source_jsonl": args.source_jsonl,
        "baseline_result": args.baseline_result,
        "golden_manifest": args.golden_manifest,
        "runtime_root": args.runtime_root,
        "expected_source_count": args.expected_source_count,
        "expected_golden_count": args.expected_golden_count,
        "expected_panel_sha256": args.expected_panel_sha256,
        "expected_baseline_sha256": args.expected_baseline_sha256,
        "expected_golden_sha256": args.expected_golden_sha256,
    }
    if args.profile == "fresh375":
        if args.fresh_plan is None or not args.expected_prompt_version:
            raise SystemExit("fresh375 requires --fresh-plan and --expected-prompt-version")
        fresh_plan = _load_json(args.fresh_plan)
        fresh_plan["plan_path"] = str(args.fresh_plan)
        anchor = build_fresh375_trust_anchor(
            **common,
            fresh_plan=fresh_plan,
            fresh_plan_path=args.fresh_plan,
            expected_prompt_version=args.expected_prompt_version,
            expected_fresh_run_id=args.expected_fresh_run_id,
        )
    else:
        required = (
            "recovered_json",
            "recovery_summary",
            "source_checkpoint",
            "source_manifest",
            "source_plan",
            "residual_json",
            "residual_input",
            "residual_manifest",
            "residual_plan",
            "expected_source_run_id",
            "expected_residual_run_id",
        )
        missing = [name for name in required if getattr(args, name) in (None, "")]
        if missing:
            raise SystemExit(f"interrupted profile missing required arguments: {missing}")
        source_plan = _load_json(args.source_plan)
        residual_plan = _load_json(args.residual_plan)
        source_plan["plan_path"] = str(args.source_plan)
        residual_plan["plan_path"] = str(args.residual_plan)
        anchor = build_trust_anchor(
            **common,
            recovered_rows=_rows_from_json_or_jsonl(args.recovered_json, "recovered result"),
            source_checkpoint_rows=_load_jsonl(args.source_checkpoint),
            recovery_summary=_load_json(args.recovery_summary),
            source_manifest=_load_json(args.source_manifest),
            source_plan=source_plan,
            residual_partial_rows=_rows_from_json_or_jsonl(
                args.residual_json,
                "residual partial result",
            ),
            residual_input_rows=_load_jsonl(args.residual_input),
            residual_manifest=_load_json(args.residual_manifest),
            residual_plan=residual_plan,
            recovered_result_path=args.recovered_json,
            recovery_summary_path=args.recovery_summary,
            source_checkpoint_path=args.source_checkpoint,
            source_manifest_path=args.source_manifest,
            source_plan_path=args.source_plan,
            residual_input_path=args.residual_input,
            residual_plan_path=args.residual_plan,
            expected_source_run_id=args.expected_source_run_id,
            expected_residual_run_id=args.expected_residual_run_id,
            expected_recovered_count=args.expected_recovered_count,
            expected_residual_count=args.expected_residual_count,
            expected_source_flushed_count=args.expected_source_flushed_count,
            expected_source_pending_count=args.expected_source_pending_count,
        )
    write_receipt = _write_json_exclusive(args.output_json, anchor)
    print(
        json.dumps(
            {
                "gate": anchor["gate"],
                "stable_runtime_fingerprint_sha256": anchor[
                    "stable_runtime_fingerprint_sha256"
                ],
                "runtime_code_tree_sha256": anchor["runtime_code_tree_sha256"],
                "output_json": str(args.output_json),
                "write_receipt": write_receipt,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
