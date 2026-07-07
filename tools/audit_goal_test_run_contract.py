from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


DEFAULT_PROCESS_PATTERNS = (
    "expert_main",
    "llm_batch",
    "warp_shards",
    "vllm",
    "uvicorn",
)

FORBIDDEN_LOG_PATTERNS: dict[str, str] = {
    "docker_compose": r"\bdocker\s+compose\b",
    "force_recreate": r"force[-_ ]recreate",
    "warp_shards_up": r"warp_shards\.py[^\r\n]*(?:\bup\b|compose\s+up)",
    "warp_shards_recreate": r"warp_shards\.py[^\r\n]*recreate",
    "compose_down": r"(?:\bcompose\s+down\b|\bdocker\s+compose[^\r\n]*\bdown\b)",
}

RUNTIME_EXCEPTION_LOG_PATTERNS: dict[str, str] = {
    "python_traceback": r"Traceback \(most recent call last\):",
    "deliberation_error": r"Deliberation 오류:",
    "python_name_error": r"\bNameError:",
}


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    return data if isinstance(data, dict) else {}


def _first_present(mapping: dict[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        if key in mapping:
            return mapping.get(key)
    return None


def _manifest_value(manifest: dict[str, Any], *keys: str) -> Any:
    direct = _first_present(manifest, keys)
    if direct is not None:
        return direct
    for section_name in ("run_config", "execution_contract", "run_meta"):
        section = manifest.get(section_name)
        if isinstance(section, dict):
            nested = _first_present(section, keys)
            if nested is not None:
                return nested
    return None


def _to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None or value == "":
        return None
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return None


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _short_error(error: Any, *, limit: int = 240) -> str:
    text = " ".join(str(error).split())
    return text[:limit]


def parse_process_patterns(values: Iterable[str] | None) -> list[str]:
    patterns: list[str] = []
    for value in values or ():
        for item in str(value).split(","):
            item = item.strip()
            if item:
                patterns.append(item)
    return patterns or list(DEFAULT_PROCESS_PATTERNS)


def _disabled_process_snapshot(patterns: Iterable[str]) -> dict[str, Any]:
    return {
        "enabled": False,
        "available": False,
        "source": "disabled",
        "patterns": list(patterns),
        "matching_process_count": 0,
        "processes": [],
        "stale_process_candidate_count": 0,
    }


def _unavailable_process_snapshot(patterns: Iterable[str], error: Any) -> dict[str, Any]:
    snapshot = _disabled_process_snapshot(patterns)
    snapshot["enabled"] = True
    snapshot["source"] = "unavailable"
    snapshot["error"] = _short_error(error)
    return snapshot


def _powershell_process_snapshot_command() -> str:
    return r"""
$ErrorActionPreference = 'Stop'
Get-CimInstance Win32_Process |
    Where-Object {
        $_.Name -match 'python' -or
        $_.CommandLine -match 'expert_main|llm_batch|warp_shards|vllm|uvicorn'
    } |
    ForEach-Object {
        [PSCustomObject]@{
            pid = $_.ProcessId
            parent_pid = $_.ParentProcessId
            creation_date = if ($_.CreationDate) { $_.CreationDate.ToString("o") } else { $null }
            command_line = $_.CommandLine
        }
    } |
    ConvertTo-Json -Depth 3
"""


def _coerce_process_records(data: Any) -> list[dict[str, Any]]:
    if data in (None, ""):
        return []
    if isinstance(data, dict):
        for key in ("processes", "records", "items", "data"):
            if key in data:
                data = data.get(key)
                break
    records = data if isinstance(data, list) else [data]
    out: list[dict[str, Any]] = []
    for item in records:
        if not isinstance(item, dict):
            continue
        command_line = item.get("command_line") if "command_line" in item else item.get("CommandLine")
        out.append(
            {
                "pid": _to_int(item.get("pid") if "pid" in item else item.get("ProcessId")),
                "parent_pid": _to_int(
                    item.get("parent_pid") if "parent_pid" in item else item.get("ParentProcessId")
                ),
                "creation_date": item.get("creation_date") if "creation_date" in item else item.get("CreationDate"),
                "command_line": str(command_line or ""),
            }
        )
    return out


def _process_snapshot_from_records(
    patterns: Iterable[str],
    raw_records: Any,
    *,
    source: str,
) -> dict[str, Any]:
    patterns = list(patterns)
    try:
        process_regex = re.compile("|".join(f"(?:{pattern})" for pattern in patterns), flags=re.IGNORECASE)
    except re.error as exc:
        return _unavailable_process_snapshot(patterns, f"invalid process pattern: {exc}")

    current_pid = os.getpid()
    processes = [
        process
        for process in _coerce_process_records(raw_records)
        if process_regex.search(process.get("command_line") or "") and not _is_snapshot_capture_command(process)
    ]
    return {
        "enabled": True,
        "available": True,
        "source": source,
        "patterns": patterns,
        "matching_process_count": len(processes),
        "processes": processes,
        "stale_process_candidate_count": sum(1 for process in processes if process.get("pid") != current_pid),
    }


def load_process_snapshot_json(path: Path, patterns: Iterable[str]) -> dict[str, Any]:
    patterns = list(patterns)
    try:
        raw_records = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:  # noqa: BLE001 - external snapshot input should not crash audit.
        return _unavailable_process_snapshot(patterns, f"invalid process snapshot file {path}: {exc}")
    snapshot = _process_snapshot_from_records(patterns, raw_records, source=str(path))
    snapshot["input_path"] = str(path)
    return snapshot


def _is_snapshot_capture_command(process: dict[str, Any]) -> bool:
    command_line = str(process.get("command_line") or "").lower()
    return "get-ciminstance win32_process" in command_line and "commandline -match" in command_line


def collect_process_snapshot(patterns: Iterable[str], *, timeout_seconds: int = 5) -> dict[str, Any]:
    patterns = list(patterns)
    try:
        completed = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                _powershell_process_snapshot_command(),
            ],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except Exception as exc:  # noqa: BLE001 - snapshot collection must never fail the audit.
        return _unavailable_process_snapshot(patterns, exc)

    if completed.returncode != 0:
        return _unavailable_process_snapshot(patterns, completed.stderr or completed.stdout or completed.returncode)

    stdout = (completed.stdout or "").strip()
    try:
        raw_records = json.loads(stdout) if stdout else []
    except json.JSONDecodeError as exc:
        return _unavailable_process_snapshot(patterns, f"invalid process snapshot JSON: {exc}")

    return _process_snapshot_from_records(patterns, raw_records, source="powershell_get_ciminstance")


def scan_log_text(text: str) -> dict[str, Any]:
    counts: dict[str, int] = {}
    samples: dict[str, list[dict[str, Any]]] = {}
    for name, pattern in {**FORBIDDEN_LOG_PATTERNS, **RUNTIME_EXCEPTION_LOG_PATTERNS}.items():
        matches = list(re.finditer(pattern, text, flags=re.IGNORECASE))
        if not matches:
            continue
        counts[name] = len(matches)
        samples[name] = []
        for match in matches[:3]:
            line_no = text.count("\n", 0, match.start()) + 1
            line_start = text.rfind("\n", 0, match.start()) + 1
            line_end = text.find("\n", match.end())
            if line_end < 0:
                line_end = len(text)
            samples[name].append(
                {
                    "line": line_no,
                    "match": match.group(0),
                    "excerpt": text[line_start:line_end].strip()[:240],
                }
            )
    return {"counts": counts, "samples": samples}


def scan_log_paths(paths: Iterable[Path]) -> dict[str, Any]:
    total_counts: dict[str, int] = {}
    by_file: list[dict[str, Any]] = []
    for path in paths:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        result = scan_log_text(text)
        for key, count in (result.get("counts") or {}).items():
            total_counts[key] = total_counts.get(key, 0) + int(count)
        by_file.append({"path": str(path), **result})
    return {
        "total_counts": dict(sorted(total_counts.items())),
        "files": by_file,
    }


def discover_log_paths(
    manifest: dict[str, Any],
    *,
    log_dir: Path = Path("logs"),
    include_worker_logs: bool = True,
) -> list[Path]:
    run_id = str(_manifest_value(manifest, "run_id") or "").strip()
    if not run_id:
        return []
    candidates = [log_dir / f"expert_run_{run_id}.log"]
    if include_worker_logs:
        candidates.extend(sorted(log_dir.glob(f"expert_run_{run_id}_W*.log")))
    seen: set[str] = set()
    out: list[Path] = []
    for path in candidates:
        key = str(path)
        if key in seen or not path.exists():
            continue
        seen.add(key)
        out.append(path)
    return out


def _issue(code: str, severity: str, evidence: str, action: str) -> dict[str, str]:
    return {
        "code": code,
        "severity": severity,
        "evidence": evidence,
        "action": action,
    }


def _gate_from_issues(issues: list[dict[str, str]]) -> str:
    if any(item.get("severity") == "NO-GO" for item in issues):
        return "NO-GO"
    if issues:
        return "REVIEW"
    return "GO"


def audit_manifest(
    manifest: dict[str, Any],
    *,
    manifest_path: Path | None = None,
    log_paths: Iterable[Path] = (),
    small_run_threshold: int = 36,
    expect_small_goal_run: bool = True,
    allow_lifecycle: bool = False,
    allow_status_audit: bool = False,
    require_log_evidence: bool = False,
    auto_discovered_logs: bool = False,
) -> dict[str, Any]:
    input_count = _to_int(_manifest_value(manifest, "input_post_count", "input_count"))
    requested_parallel_raw = _to_int(
        _manifest_value(manifest, "requested_parallel_raw", "parallel_requested_raw")
    )
    requested_parallel = _to_int(_manifest_value(manifest, "requested_parallel", "parallel_requested"))
    effective_parallel = _to_int(
        _manifest_value(manifest, "effective_parallel", "parallel_count", "parallel")
    )
    model_parallel_max = _to_int(_manifest_value(manifest, "model_parallel_max"))
    model_parallel_cap_applied = _to_bool(_manifest_value(manifest, "model_parallel_cap_applied"))
    llm_model = str(
        _manifest_value(manifest, "llm_model", "model", "model_parallel_cap_model") or ""
    )
    llm_endpoint = str(
        _manifest_value(manifest, "llm_endpoint", "llm_base_url", "base_url") or ""
    ).strip()
    normalized_model = re.sub(r"[^a-z0-9]+", "-", llm_model.lower())
    if model_parallel_max is None and (
        "gemma-4-e4b" in normalized_model
        or "gemma-4-4b" in normalized_model
        or "gemma-4b" in normalized_model
    ):
        model_parallel_max = 36
    completed_count = _to_int(_manifest_value(manifest, "completed_count"))
    flushed_count = _to_int(_manifest_value(manifest, "flushed_count"))
    pending_count = _to_int(_manifest_value(manifest, "pending_count"))
    failed_count = _to_int(_manifest_value(manifest, "failed_count"))
    image_post_count = _to_int(_manifest_value(manifest, "image_post_count"))
    vlm_enabled = _to_bool(_manifest_value(manifest, "vlm_enabled"))
    ocr_enabled = _to_bool(_manifest_value(manifest, "ocr_enabled"))
    vlm_ocr_ready = _to_bool(_manifest_value(manifest, "vlm_ocr_semantic_review_ready"))
    auto_up = _to_bool(_manifest_value(manifest, "mcp_auto_up_shards"))
    auto_recreate = _to_bool(_manifest_value(manifest, "mcp_auto_recreate_shards"))
    local_management = _to_bool(_manifest_value(manifest, "mcp_local_shard_management_enabled"))
    status_audit = _to_bool(
        _manifest_value(
            manifest,
            "mcp_local_shard_status_audit_allowed",
            "mcp_local_shard_status_audit",
        )
    )
    small_blocked = _to_bool(_manifest_value(manifest, "mcp_small_run_shard_lifecycle_blocked"))
    health_include_search = _to_bool(_manifest_value(manifest, "mcp_health_include_search"))
    health_light_mode = _to_bool(_manifest_value(manifest, "mcp_health_light_mode"))
    health_required_ok_count = _to_int(_manifest_value(manifest, "mcp_health_required_ok_count"))
    health_checked_endpoint_count = _to_int(_manifest_value(manifest, "mcp_health_checked_endpoint_count"))
    health_probe_batch_size = _to_int(_manifest_value(manifest, "mcp_health_probe_batch_size"))
    health_probe_stopped_after_required_ok = _to_bool(
        _manifest_value(manifest, "mcp_health_probe_stopped_after_required_ok")
    )
    health_workers = _to_int(_manifest_value(manifest, "mcp_health_workers"))
    health_attempts = _to_int(_manifest_value(manifest, "mcp_health_attempts"))
    health_timeout_sec = _to_float(_manifest_value(manifest, "mcp_health_timeout_sec"))
    health_ok_count = _to_int(_manifest_value(manifest, "mcp_health_ok_count"))
    health_failure_count = _to_int(_manifest_value(manifest, "mcp_health_failure_count"))
    requested_endpoint_count_before_filter = _to_int(
        _manifest_value(manifest, "mcp_requested_endpoint_count_before_health_filter")
    )
    endpoint_count_after_filter = _to_int(
        _manifest_value(manifest, "mcp_endpoint_count_after_health_filter")
    )
    dashboard_enabled = _to_bool(_manifest_value(manifest, "dashboard_enabled"))
    dashboard_mode = str(_manifest_value(manifest, "dashboard_mode") or "").strip()
    dashboard_url = str(_manifest_value(manifest, "dashboard_url") or "").strip()
    dashboard_standalone_forwarding = _to_bool(_manifest_value(manifest, "dashboard_standalone_forwarding"))
    dashboard_start_error = str(_manifest_value(manifest, "dashboard_start_error") or "").strip()

    is_small_run = bool(expect_small_goal_run and input_count is not None and input_count <= small_run_threshold)
    log_paths = list(log_paths)
    log_scan = scan_log_paths(log_paths) if log_paths else {"total_counts": {}, "files": []}
    issues: list[dict[str, str]] = []

    if requested_parallel is None:
        issues.append(
            _issue(
                "requested_parallel_missing",
                "REVIEW",
                "manifest requested_parallel field is missing",
                "manifest_schema_review",
            )
        )
    elif model_parallel_max is not None and requested_parallel > model_parallel_max:
        issues.append(
            _issue(
                "requested_parallel_above_model_parallel_max",
                "NO-GO",
                f"requested_parallel={requested_parallel}, model_parallel_max={model_parallel_max}",
                "rerun_with_model_parallel_max_or_fix_manifest_cap",
            )
        )
    elif model_parallel_max is None and requested_parallel > 36:
        issues.append(
            _issue(
                "requested_parallel_above_legacy_36_without_model_cap",
                "NO-GO",
                f"requested_parallel={requested_parallel}, model_parallel_max=missing",
                "record_model_parallel_max_or_rerun_with_parallel_36_max",
            )
        )

    if effective_parallel is None:
        issues.append(
            _issue(
                "effective_parallel_missing",
                "REVIEW",
                "manifest effective_parallel field is missing",
                "manifest_schema_review",
            )
        )
    elif requested_parallel is not None and effective_parallel > requested_parallel:
        issues.append(
            _issue(
                "effective_parallel_exceeds_requested",
                "NO-GO",
                f"effective_parallel={effective_parallel}, requested_parallel={requested_parallel}",
                "runtime_contract_bug",
            )
        )
    elif input_count is not None and effective_parallel > input_count:
        issues.append(
            _issue(
                "effective_parallel_exceeds_input_post_count",
                "NO-GO",
                f"effective_parallel={effective_parallel}, input_post_count={input_count}",
                "runtime_contract_bug",
            )
        )

    if input_count is None:
        issues.append(
            _issue(
                "input_post_count_missing",
                "REVIEW",
                "manifest input_post_count field is missing",
                "manifest_schema_review",
            )
        )
    else:
        if completed_count is not None and completed_count < input_count:
            issues.append(
                _issue(
                    "completed_count_lt_input_post_count",
                    "NO-GO",
                    f"completed_count={completed_count}, input_post_count={input_count}",
                    "rerun_or_recover_checkpoint",
                )
            )
        if failed_count and failed_count > 0:
            issues.append(
                _issue(
                    "failed_count_gt_zero",
                    "NO-GO",
                    f"failed_count={failed_count}",
                    "inspect_failed_rows",
                )
            )
        if pending_count and pending_count > 0:
            issues.append(
                _issue(
                    "pending_count_gt_zero",
                    "NO-GO",
                    f"pending_count={pending_count}",
                    "recover_or_rerun_pending_rows",
                )
            )
        if completed_count is not None and flushed_count is not None and flushed_count < completed_count:
            issues.append(
                _issue(
                    "flushed_count_lt_completed_count",
                    "NO-GO",
                    f"flushed_count={flushed_count}, completed_count={completed_count}",
                    "use_completed_subset_or_recover_checkpoint",
                )
            )

    if is_small_run and not allow_lifecycle:
        if not llm_endpoint:
            issues.append(
                _issue(
                    "llm_endpoint_missing",
                    "REVIEW",
                    "llm_endpoint field is missing; run target cannot be replayed from manifest",
                    "record_llm_endpoint_in_manifest_or_rerun_with_v491_contract",
                )
            )
        lifecycle_flags = {
            "mcp_auto_up_shards": auto_up,
            "mcp_auto_recreate_shards": auto_recreate,
            "mcp_local_shard_management_enabled": local_management,
        }
        for key, value in lifecycle_flags.items():
            if value is True:
                issues.append(
                    _issue(
                        f"{key}_true_for_small_goal_run",
                        "NO-GO",
                        f"{key}=true, input_post_count={input_count}",
                        "rerun_with_reuse_shards_only_or_without_lifecycle",
                    )
                )
        if status_audit is True and not allow_status_audit:
            issues.append(
                _issue(
                    "mcp_local_shard_status_audit_enabled_for_small_goal_run",
                    "REVIEW",
                    "status audit was enabled on a small goal/test run",
                    "confirm_status_audit_was_explicitly_requested",
                )
            )
        if small_blocked is False:
            issues.append(
                _issue(
                    "small_run_lifecycle_block_not_recorded",
                    "REVIEW",
                    f"mcp_small_run_shard_lifecycle_blocked=false, input_post_count={input_count}",
                    "manifest_contract_review",
                )
            )
        elif small_blocked is None:
            issues.append(
                _issue(
                    "small_run_lifecycle_block_field_missing",
                    "REVIEW",
                    "mcp_small_run_shard_lifecycle_blocked field is missing",
                    "manifest_schema_review",
                )
            )
        if health_include_search is True:
            issues.append(
                _issue(
                    "small_run_health_include_search_true",
                    "REVIEW",
                    "small goal/reuse-only run used search health instead of Bridge readiness only",
                    "rerun_or_override_with_MCP_HEALTH_INCLUDE_SEARCH_0",
                )
            )
        elif health_include_search is None:
            issues.append(
                _issue(
                    "small_run_health_include_search_missing",
                    "REVIEW",
                    "mcp_health_include_search field is missing; log-only health evidence is not enough",
                    "rerun_with_manifest_health_contract_or_fix_manifest_writer",
                )
            )
        if health_light_mode is False:
            issues.append(
                _issue(
                    "small_run_health_light_mode_false",
                    "REVIEW",
                    "small goal/reuse-only run did not record light health mode",
                    "review_expert_main_health_policy_or_rerun_with_v488_contract",
                )
            )
        elif health_light_mode is None:
            issues.append(
                _issue(
                    "small_run_health_light_mode_missing",
                    "REVIEW",
                    "mcp_health_light_mode field is missing; small run light-health contract is not auditable",
                    "rerun_with_manifest_health_contract_or_fix_manifest_writer",
                )
            )
        for _field_name, _value in (
            ("mcp_health_required_ok_count", health_required_ok_count),
            ("mcp_health_checked_endpoint_count", health_checked_endpoint_count),
            ("mcp_health_probe_batch_size", health_probe_batch_size),
            ("mcp_health_workers", health_workers),
            ("mcp_health_attempts", health_attempts),
            ("mcp_health_timeout_sec", health_timeout_sec),
            ("mcp_health_ok_count", health_ok_count),
            ("mcp_health_failure_count", health_failure_count),
        ):
            if _value is None:
                issues.append(
                    _issue(
                        f"{_field_name}_missing",
                        "REVIEW",
                        f"{_field_name} field is missing; health probe evidence cannot be replayed from manifest",
                        "rerun_with_manifest_health_contract_or_fix_manifest_writer",
                    )
                )
        if (
            health_ok_count is not None
            and health_required_ok_count is not None
            and health_ok_count < health_required_ok_count
        ):
            issues.append(
                _issue(
                    "mcp_health_ok_count_lt_required_ok_count",
                    "NO-GO",
                    f"ok={health_ok_count}, required_ok={health_required_ok_count}",
                    "rerun_with_enough_healthy_endpoints_or_fix_health_probe",
                )
            )
        if health_failure_count is not None and health_failure_count > 0:
            issues.append(
                _issue(
                    "mcp_health_failure_count_gt_zero",
                    "NO-GO",
                    f"failure_count={health_failure_count}",
                    "inspect_failed_health_endpoints_before_using_goal_run",
                )
            )
        if (
            health_ok_count is not None
            and health_checked_endpoint_count is not None
            and health_ok_count > health_checked_endpoint_count
        ):
            issues.append(
                _issue(
                    "mcp_health_ok_count_gt_checked_endpoint_count",
                    "NO-GO",
                    f"ok={health_ok_count}, checked={health_checked_endpoint_count}",
                    "inspect_manifest_health_accounting",
                )
            )
        if (
            health_ok_count is not None
            and health_failure_count is not None
            and health_checked_endpoint_count is not None
            and health_ok_count + health_failure_count > health_checked_endpoint_count
        ):
            issues.append(
                _issue(
                    "mcp_health_ok_plus_failure_count_gt_checked_endpoint_count",
                    "NO-GO",
                    (
                        f"ok={health_ok_count}, failure={health_failure_count}, "
                        f"checked={health_checked_endpoint_count}"
                    ),
                    "inspect_manifest_health_accounting",
                )
            )
        if dashboard_enabled is False:
            issues.append(
                _issue(
                    "dashboard_disabled_for_goal_test_run",
                    "NO-GO",
                    "dashboard_enabled=false; test/runtime run progress was not attached to the web dashboard",
                    "rerun_with_dashboard_or_use_run_independent_plan_default_dashboard",
                )
            )
        elif dashboard_enabled is None:
            issues.append(
                _issue(
                    "dashboard_enabled_missing",
                    "REVIEW",
                    "dashboard_enabled field is missing; dashboard attachment cannot be audited",
                    "rerun_with_dashboard_manifest_contract_or_fix_manifest_writer",
                )
            )
        if dashboard_enabled is True:
            if dashboard_mode in {"", "disabled", "unavailable"}:
                issues.append(
                    _issue(
                        "dashboard_mode_not_attached",
                        "REVIEW",
                        f"dashboard_enabled=true but dashboard_mode={dashboard_mode or 'missing'}",
                        "inspect_dashboard_start_error_or_attach_manifest_dashboard",
                    )
                )
            if not dashboard_url:
                issues.append(
                    _issue(
                        "dashboard_url_missing",
                        "REVIEW",
                        "dashboard_enabled=true but dashboard_url is missing",
                        "record_dashboard_url_in_manifest_or_rerun_with_dashboard_contract",
                    )
                )

    log_counts = log_scan.get("total_counts") or {}
    forbidden_counts = {
        key: count
        for key, count in log_counts.items()
        if key in FORBIDDEN_LOG_PATTERNS and int(count) > 0
    }
    runtime_exception_counts = {
        key: count
        for key, count in log_counts.items()
        if key in RUNTIME_EXCEPTION_LOG_PATTERNS and int(count) > 0
    }
    if forbidden_counts:
        issues.append(
            _issue(
                "docker_or_shard_lifecycle_log_hits",
                "NO-GO",
                json.dumps(forbidden_counts, ensure_ascii=False, sort_keys=True),
                "inspect_log_and_rerun_without_lifecycle",
            )
        )
    if runtime_exception_counts:
        issues.append(
            _issue(
                "runtime_log_exception",
                "NO-GO",
                json.dumps(runtime_exception_counts, ensure_ascii=False, sort_keys=True),
                "inspect_traceback_fix_code_and_rerun_targeted_case",
            )
        )
    elif require_log_evidence and not log_paths:
        issues.append(
            _issue(
                "log_evidence_missing",
                "REVIEW",
                "no expert_run log was provided or discovered; forbidden lifecycle log hits cannot be proven absent",
                "provide_log_or_run_auto_log_discovery",
            )
        )

    if image_post_count is None:
        issues.append(
            _issue(
                "image_post_count_missing",
                "REVIEW",
                "manifest image_post_count field is missing",
                "manifest_schema_review",
            )
        )
    elif image_post_count > 0:
        if vlm_enabled is not True or ocr_enabled is not True or vlm_ocr_ready is not True:
            issues.append(
                _issue(
                    "image_posts_without_vlm_ocr_ready",
                    "NO-GO",
                    (
                        f"image_post_count={image_post_count}, "
                        f"vlm_enabled={vlm_enabled}, ocr_enabled={ocr_enabled}, "
                        f"vlm_ocr_semantic_review_ready={vlm_ocr_ready}"
                    ),
                    "rerun_with_vlm_on_ocr_on_or_browser_review",
                )
            )

    if (
        health_checked_endpoint_count is not None
        and requested_endpoint_count_before_filter is not None
        and health_checked_endpoint_count > requested_endpoint_count_before_filter
    ):
        issues.append(
            _issue(
                "mcp_health_checked_endpoint_count_exceeds_requested_endpoint_count",
                "NO-GO",
                (
                    f"checked={health_checked_endpoint_count}, "
                    f"requested_before_filter={requested_endpoint_count_before_filter}"
                ),
                "inspect_manifest_health_accounting",
            )
        )
    if (
        health_checked_endpoint_count is not None
        and endpoint_count_after_filter is not None
        and health_checked_endpoint_count < endpoint_count_after_filter
    ):
        issues.append(
            _issue(
                "mcp_health_checked_endpoint_count_lt_endpoint_count_after_filter",
                "NO-GO",
                (
                    f"checked={health_checked_endpoint_count}, "
                    f"after_filter={endpoint_count_after_filter}"
                ),
                "inspect_manifest_health_accounting",
            )
        )
    if (
        health_required_ok_count is not None
        and endpoint_count_after_filter is not None
        and endpoint_count_after_filter < health_required_ok_count
    ):
        issues.append(
            _issue(
                "mcp_endpoint_count_after_filter_lt_health_required_ok_count",
                "NO-GO",
                (
                    f"after_filter={endpoint_count_after_filter}, "
                    f"required_ok={health_required_ok_count}"
                ),
                "rerun_with_enough_healthy_endpoints_or_fix_health_filter",
            )
        )

    gate = _gate_from_issues(issues)
    return {
        "audit_type": "goal_test_run_contract",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "manifest_path": str(manifest_path or ""),
        "log_paths": [str(path) for path in log_paths],
        "auto_discovered_logs": auto_discovered_logs,
        "log_evidence_present": bool(log_paths),
        "expect_small_goal_run": expect_small_goal_run,
        "small_run_threshold": small_run_threshold,
        "allow_lifecycle": allow_lifecycle,
        "allow_status_audit": allow_status_audit,
        "observed": {
            "run_id": _manifest_value(manifest, "run_id"),
            "llm_model": llm_model,
            "llm_endpoint": llm_endpoint,
            "requested_parallel_raw": requested_parallel_raw,
            "requested_parallel": requested_parallel,
            "effective_parallel": effective_parallel,
            "parallel_policy": _manifest_value(manifest, "parallel_policy"),
            "model_parallel_max": model_parallel_max,
            "model_parallel_cap_applied": model_parallel_cap_applied,
            "input_post_count": input_count,
            "completed_count": completed_count,
            "flushed_count": flushed_count,
            "pending_count": pending_count,
            "failed_count": failed_count,
            "image_post_count": image_post_count,
            "vlm_enabled": vlm_enabled,
            "ocr_enabled": ocr_enabled,
            "vlm_ocr_semantic_review_ready": vlm_ocr_ready,
            "mcp_auto_up_shards": auto_up,
            "mcp_auto_recreate_shards": auto_recreate,
            "mcp_local_shard_management_enabled": local_management,
            "mcp_local_shard_status_audit": status_audit,
            "mcp_small_run_shard_lifecycle_blocked": small_blocked,
            "mcp_healthy_endpoint_filter": _to_bool(_manifest_value(manifest, "mcp_healthy_endpoint_filter")),
            "mcp_requested_endpoint_count_before_health_filter": requested_endpoint_count_before_filter,
            "mcp_endpoint_count_after_health_filter": endpoint_count_after_filter,
            "mcp_health_include_search": health_include_search,
            "mcp_health_light_mode": health_light_mode,
            "mcp_health_required_ok_count": health_required_ok_count,
            "mcp_health_checked_endpoint_count": health_checked_endpoint_count,
            "mcp_health_probe_batch_size": health_probe_batch_size,
            "mcp_health_probe_stopped_after_required_ok": health_probe_stopped_after_required_ok,
            "mcp_health_workers": health_workers,
            "mcp_health_attempts": health_attempts,
            "mcp_health_timeout_sec": health_timeout_sec,
            "mcp_health_ok_count": health_ok_count,
            "mcp_health_failure_count": health_failure_count,
            "dashboard_enabled": dashboard_enabled,
            "dashboard_mode": dashboard_mode,
            "dashboard_url": dashboard_url,
            "dashboard_standalone_forwarding": dashboard_standalone_forwarding,
            "dashboard_start_error": dashboard_start_error,
        },
        "log_scan": log_scan,
        "issues": issues,
        "gate": {
            "runtime_contract": gate,
            "semantic_approval": "not_evaluated_by_runtime_contract_audit",
            "reason": "runtime/log/manifest contract only; semantic decision quality remains separately gated",
        },
    }


def write_markdown(path: Path, audit: dict[str, Any]) -> None:
    observed = audit.get("observed") or {}
    gate = audit.get("gate") or {}
    issues = audit.get("issues") or []
    log_counts = ((audit.get("log_scan") or {}).get("total_counts") or {})
    process_snapshot = audit.get("process_snapshot") or {}
    issue_lines = "\n".join(
        f"- `{item.get('severity')}` `{item.get('code')}`: {item.get('evidence')} -> `{item.get('action')}`"
        for item in issues
    ) or "- 없음"
    process_snapshot_lines = ""
    if process_snapshot.get("enabled"):
        process_snapshot_lines = f"""
## 프로세스 snapshot

- available: `{process_snapshot.get('available')}`
- source: `{process_snapshot.get('source') or ''}`
- patterns: `{', '.join(process_snapshot.get('patterns') or [])}`
- matching_process_count: `{process_snapshot.get('matching_process_count')}`
- stale_process_candidate_count: `{process_snapshot.get('stale_process_candidate_count')}`
- error: `{process_snapshot.get('error') or ''}`
"""
    text = f"""# Goal/Test 런 계약 감사

## 요약

- runtime_contract: `{gate.get('runtime_contract')}`
- semantic_approval: `{gate.get('semantic_approval')}`
- manifest: `{audit.get('manifest_path')}`
- logs: `{', '.join(audit.get('log_paths') or []) or 'none'}`
- auto_discovered_logs: `{audit.get('auto_discovered_logs')}`
- log_evidence_present: `{audit.get('log_evidence_present')}`

## 관측값

- run_id: `{observed.get('run_id')}`
- llm_model: `{observed.get('llm_model')}`
- llm_endpoint: `{observed.get('llm_endpoint')}`
- input_post_count: `{observed.get('input_post_count')}`
- requested_parallel_raw: `{observed.get('requested_parallel_raw')}`
- requested_parallel: `{observed.get('requested_parallel')}`
- effective_parallel: `{observed.get('effective_parallel')}`
- parallel_policy: `{observed.get('parallel_policy')}`
- model_parallel_max: `{observed.get('model_parallel_max')}`
- model_parallel_cap_applied: `{observed.get('model_parallel_cap_applied')}`
- completed/flushed/pending/failed: `{observed.get('completed_count')}/{observed.get('flushed_count')}/{observed.get('pending_count')}/{observed.get('failed_count')}`
- image_post_count: `{observed.get('image_post_count')}`
- VLM/OCR ready: `vlm={observed.get('vlm_enabled')}`, `ocr={observed.get('ocr_enabled')}`, `ready={observed.get('vlm_ocr_semantic_review_ready')}`
- shard lifecycle: `auto_up={observed.get('mcp_auto_up_shards')}`, `auto_recreate={observed.get('mcp_auto_recreate_shards')}`, `local_management={observed.get('mcp_local_shard_management_enabled')}`, `status_audit={observed.get('mcp_local_shard_status_audit')}`
- small_run_lifecycle_blocked: `{observed.get('mcp_small_run_shard_lifecycle_blocked')}`
- healthy_endpoint_filter: `{observed.get('mcp_healthy_endpoint_filter')}`, after_filter=`{observed.get('mcp_endpoint_count_after_health_filter')}`
- health: `include_search={observed.get('mcp_health_include_search')}`, `light_mode={observed.get('mcp_health_light_mode')}`, `required_ok={observed.get('mcp_health_required_ok_count')}`, `checked={observed.get('mcp_health_checked_endpoint_count')}`, `ok={observed.get('mcp_health_ok_count')}`, `failure={observed.get('mcp_health_failure_count')}`, `batch={observed.get('mcp_health_probe_batch_size')}`, `stopped_after_required={observed.get('mcp_health_probe_stopped_after_required_ok')}`
- dashboard: `enabled={observed.get('dashboard_enabled')}`, `mode={observed.get('dashboard_mode')}`, `url={observed.get('dashboard_url')}`, `standalone_forwarding={observed.get('dashboard_standalone_forwarding')}`, `start_error={observed.get('dashboard_start_error')}`

## 로그 금지 패턴

- counts: `{json.dumps(log_counts, ensure_ascii=False, sort_keys=True)}`

## 이슈

{issue_lines}
{process_snapshot_lines}

## 판정

이 도구는 `expert_main.py` 소규모 goal/test run의 런타임 계약만 감사한다. `GO`가 나와도 자연어 판정 품질 승인으로 쓰지 않는다.
이미지 row가 있으면 VLM/OCR ready 또는 Browser visual evidence가 별도 semantic review에 필요하다.
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit post-run expert_main goal/test runtime contract.")
    parser.add_argument("--manifest", required=True, type=Path, help="expert_main result manifest JSON")
    parser.add_argument("--log", action="append", type=Path, default=[], help="expert_main log file; repeatable")
    parser.add_argument("--log-dir", type=Path, default=Path("logs"), help="log directory for run_id based discovery")
    parser.add_argument("--no-auto-log-discovery", action="store_true", help="do not infer expert_run_<run_id>.log")
    parser.add_argument("--skip-worker-logs", action="store_true", help="do not include expert_run_<run_id>_W*.log")
    parser.add_argument("--no-require-log", action="store_true", help="allow GO from manifest-only evidence")
    parser.add_argument("--small-run-threshold", type=int, default=36)
    parser.add_argument("--large-run", action="store_true", help="do not enforce small goal/test lifecycle contract")
    parser.add_argument("--allow-lifecycle", action="store_true", help="allow shard lifecycle for explicit lifecycle tests")
    parser.add_argument("--allow-status-audit", action="store_true", help="allow local shard status audit on small runs")
    parser.add_argument("--output-json", type=Path, default=None)
    parser.add_argument("--output-md", type=Path, default=None)
    parser.add_argument("--fail-on-no-go", action="store_true")
    parser.add_argument(
        "--collect-process-snapshot",
        action="store_true",
        help="collect matching Windows/Python process snapshot and include it in audit JSON",
    )
    parser.add_argument(
        "--process-pattern",
        action="append",
        default=[],
        help="process command-line regex fragment; repeatable or comma-separated",
    )
    parser.add_argument(
        "--process-snapshot-json",
        type=Path,
        default=None,
        help="load process snapshot JSON captured outside this audit process",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = load_json(args.manifest)
    log_paths = list(args.log or [])
    auto_discovered_logs = False
    if not log_paths and not args.no_auto_log_discovery:
        log_paths = discover_log_paths(
            manifest,
            log_dir=args.log_dir,
            include_worker_logs=not args.skip_worker_logs,
        )
        auto_discovered_logs = bool(log_paths)
    audit = audit_manifest(
        manifest,
        manifest_path=args.manifest,
        log_paths=log_paths,
        small_run_threshold=max(0, args.small_run_threshold),
        expect_small_goal_run=not args.large_run,
        allow_lifecycle=args.allow_lifecycle,
        allow_status_audit=args.allow_status_audit,
        require_log_evidence=not args.no_require_log,
        auto_discovered_logs=auto_discovered_logs,
    )
    process_patterns = parse_process_patterns(args.process_pattern)
    if args.process_snapshot_json:
        audit["process_snapshot"] = load_process_snapshot_json(args.process_snapshot_json, process_patterns)
    elif args.collect_process_snapshot:
        audit["process_snapshot"] = collect_process_snapshot(process_patterns)
    else:
        audit["process_snapshot"] = _disabled_process_snapshot(process_patterns)
    payload = json.dumps(audit, ensure_ascii=False, indent=2)
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(payload + "\n", encoding="utf-8")
    if args.output_md:
        write_markdown(args.output_md, audit)
    print(payload)
    if args.fail_on_no_go and (audit.get("gate") or {}).get("runtime_contract") == "NO-GO":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
