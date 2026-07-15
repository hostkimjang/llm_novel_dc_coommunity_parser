from __future__ import annotations

"""Build a fail-closed search-recovery gate without merging semantic results.

The original Golden18 result remains the only semantic result.  Replay outputs are
used only as search-recovery evidence for the exact rows selected by the original
prepare gate and the two-review terminal consensus report.
"""

import argparse
import hashlib
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.audit_publication_contract_convergence import audit_rows as audit_publication_rows
from tools.audit_regression_safe_golden import build_audit as build_golden_audit
from tools.build_full375_search_adjudication_gate import (
    _public_state,
    _search_health,
    _search_health_issues,
    _search_issue,
    _sha256_file,
    _terminal_issues,
)
from tools.compare_completed779_improvement import load_json_or_jsonl


BUILDER_VERSION = "search-recovery-composite-gate-v1"
EXPECTED_ORIGINAL_ROWS = 18
EXPECTED_HARD_ROWS = 6
EXPECTED_UNREVIEWED_ROWS = 4
EXPECTED_CONSENSUS_SAFE_ROWS = 2
EXPECTED_BLIND_BLOCKER_NULL_ROWS = 2
EXPECTED_SEARCH_SHARDS = 16
MAX_PREFLIGHT_LEAD = timedelta(hours=2)

ROW_CONTRACT_FIELDS = (
    "model",
    "llm_mode",
    "llm_endpoint",
    "prompt_version",
    "runtime_release_fingerprint_sha256",
    "requested_parallel_raw",
    "requested_parallel",
    "parallel_policy",
    "model_parallel_max",
    "model_parallel_cap_applied",
    "model_parallel_cap_model",
    "mcp_health_include_search",
    "mcp_health_light_mode",
    "mcp_health_required_ok_count",
    "mcp_health_checked_endpoint_count",
    "mcp_health_probe_batch_size",
    "mcp_health_probe_stopped_after_required_ok",
    "mcp_health_workers",
    "mcp_health_attempts",
    "mcp_health_timeout_sec",
    "mcp_health_search_max_latency_ms",
    "mcp_health_search_min_results",
    "mcp_health_ok_count",
    "mcp_health_failure_count",
    "mcp_healthy_endpoint_filter",
    "mcp_healthy_endpoint_filter_reason",
    "mcp_healthy_endpoint_filter_autogen",
    "mcp_healthy_autogen_endpoint_filter",
    "mcp_healthy_autogen_endpoint_filter_reason",
    "mcp_reuse_shards_only_health_filtered",
    "mcp_goal_run_health_filtered",
    "mcp_requested_endpoint_count_before_health_filter",
    "mcp_healthy_endpoint_count",
    "mcp_endpoint_count_after_health_filter",
)

MANIFEST_CONTRACT_FIELDS = (
    "llm_model",
    "llm_endpoint",
    "llm_stream_first_token_timeout_seconds",
    "llm_stream_idle_timeout_seconds",
    "llm_stream_signal_idle_timeout_seconds",
    "requested_parallel_raw",
    "requested_parallel",
    "parallel_policy",
    "model_parallel_max",
    "model_parallel_cap_applied",
    "model_parallel_cap_model",
    "mcp_endpoints",
    "mcp_health_include_search",
    "mcp_health_light_mode",
    "mcp_health_required_ok_count",
    "mcp_health_checked_endpoint_count",
    "mcp_health_probe_batch_size",
    "mcp_health_probe_stopped_after_required_ok",
    "mcp_health_workers",
    "mcp_health_attempts",
    "mcp_health_timeout_sec",
    "mcp_health_search_max_latency_ms",
    "mcp_health_search_min_results",
    "mcp_health_ok_count",
    "mcp_health_failure_count",
    "mcp_healthy_endpoint_filter",
    "mcp_healthy_endpoint_filter_reason",
    "mcp_healthy_endpoint_filter_autogen",
    "mcp_healthy_autogen_endpoint_filter",
    "mcp_healthy_autogen_endpoint_filter_reason",
    "mcp_reuse_shards_only_health_filtered",
    "mcp_goal_run_health_filtered",
    "mcp_requested_endpoint_count_before_health_filter",
    "mcp_healthy_endpoint_count",
    "mcp_endpoint_count_after_health_filter",
    "vlm_enabled",
    "ocr_enabled",
    "vlm_ocr_semantic_review_ready",
    "vlm_ocr_semantic_review_required_for_images",
    "dashboard_enabled",
    "dashboard_mode",
    "dashboard_standalone_forwarding",
)

CONFIG_PAYLOAD_MANIFEST_FIELDS = (
    "requested_parallel_raw",
    "requested_parallel",
    "effective_parallel",
    "parallel_policy",
    "model_parallel_max",
    "model_parallel_cap_applied",
    "model_parallel_cap_model",
    "input_post_count",
    "mcp_endpoints",
    "mcp_auto_up_shards",
    "mcp_auto_recreate_shards",
    "mcp_auto_scale_up_missing_shards",
    "mcp_local_shard_management_enabled",
    "mcp_local_shard_status_audit",
    "mcp_local_shard_status_audit_requested",
    "mcp_local_shard_status_audit_allowed",
    "mcp_shard_lifecycle_policy",
    "mcp_allow_goal_shard_lifecycle",
    "mcp_command_shard_lifecycle_allowed",
    "mcp_interactive_codex_run",
    "mcp_env_shard_lifecycle_requested",
    "mcp_env_shard_lifecycle_global_opt_in",
    "mcp_env_shard_lifecycle_allowed",
    "mcp_env_shard_lifecycle_blocked_by_context",
    "mcp_shard_lifecycle_block_threshold",
    "mcp_run_post_count_for_lifecycle",
    "mcp_small_targeted_run",
    "mcp_small_run_shard_lifecycle_blocked",
    "mcp_health_include_search",
    "mcp_health_light_mode",
    "mcp_health_required_ok_count",
    "mcp_health_checked_endpoint_count",
    "mcp_health_probe_batch_size",
    "mcp_health_probe_stopped_after_required_ok",
    "mcp_health_workers",
    "mcp_health_attempts",
    "mcp_health_timeout_sec",
    "mcp_health_search_max_latency_ms",
    "mcp_health_search_min_results",
    "mcp_missing_shard_scale_up_allowed",
    "mcp_missing_shard_scale_up_triggered",
    "mcp_missing_shard_scale_up_shards",
    "mcp_missing_shard_scale_up_recovered_endpoints",
    "mcp_missing_shard_scale_up_error",
    "mcp_healthy_endpoint_filter",
    "mcp_healthy_endpoint_filter_reason",
    "mcp_healthy_endpoint_filter_autogen",
    "mcp_healthy_autogen_endpoint_filter",
    "mcp_healthy_autogen_endpoint_filter_reason",
    "mcp_reuse_shards_only_health_filtered",
    "mcp_goal_run_health_filtered",
    "mcp_requested_endpoint_count_before_health_filter",
    "mcp_healthy_endpoint_count",
    "mcp_endpoint_count_after_health_filter",
    "mcp_parallel_before_health_filter",
    "mcp_parallel_after_health_filter",
)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be object: {path}")
    return value


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line_no, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"JSONL row must be object: {path}:{line_no}")
            rows.append(value)
    return rows


def _post_id(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("post_id")
    text = str(value or "").strip()
    if not text:
        raise ValueError("post_id is required")
    return text


def _ids_with_duplicates(rows: Iterable[dict[str, Any]]) -> tuple[list[str], list[str]]:
    ids: list[str] = []
    duplicates: list[str] = []
    seen: set[str] = set()
    for row in rows:
        post_id = _post_id(row)
        ids.append(post_id)
        if post_id in seen and post_id not in duplicates:
            duplicates.append(post_id)
        seen.add(post_id)
    return ids, duplicates


def _resolve(path_text: Any) -> Path:
    candidate = Path(str(path_text or ""))
    return (ROOT / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()


def _same_path(path_text: Any, expected: Path) -> bool:
    return bool(str(path_text or "").strip()) and _resolve(path_text) == expected.resolve()


def _artifact(path: Path, *, row_count: int | None = None) -> dict[str, Any]:
    item: dict[str, Any] = {
        "path": str(path),
        "sha256": file_sha256(path),
        "size_bytes": path.stat().st_size,
    }
    if row_count is not None:
        item["row_count"] = row_count
    return item


def _uniform_row_contract(rows: list[dict[str, Any]]) -> tuple[dict[str, Any], list[str]]:
    issues: list[str] = []
    if not rows:
        return {}, ["runtime_result_empty"]
    signatures: list[dict[str, Any]] = []
    config_hashes: set[str] = set()
    run_ids: set[str] = set()
    for row in rows:
        meta = row.get("run_meta") if isinstance(row.get("run_meta"), dict) else {}
        signature = {field: meta.get(field) for field in ROW_CONTRACT_FIELDS}
        signatures.append(signature)
        config_hashes.add(str(meta.get("config_hash") or "").strip())
        run_ids.add(str(meta.get("run_id") or "").strip())
    if any(signature != signatures[0] for signature in signatures[1:]):
        issues.append("row_runtime_contract_not_uniform")
    if len(config_hashes) != 1 or "" in config_hashes:
        issues.append("row_config_hash_not_uniform_nonempty")
    if len(run_ids) != 1 or "" in run_ids:
        issues.append("row_run_id_not_uniform_nonempty")
    return {
        "stable": signatures[0],
        "config_hash": next(iter(config_hashes)) if len(config_hashes) == 1 else None,
        "run_id": next(iter(run_ids)) if len(run_ids) == 1 else None,
    }, issues


def _manifest_contract(manifest: dict[str, Any]) -> dict[str, Any]:
    return {field: manifest.get(field) for field in MANIFEST_CONTRACT_FIELDS}


def runtime_config_payload(
    manifest: dict[str, Any],
    row_contract: dict[str, Any],
    *,
    slang_db: str = "0",
    reason_full_mode: str = "1",
    server_type: str = "vllm",
) -> dict[str, Any]:
    """Reconstruct expert_main's hashed runtime config from persisted evidence."""

    stable = row_contract.get("stable") if isinstance(row_contract.get("stable"), dict) else {}
    payload = {
        "llm_mode": stable.get("llm_mode"),
        "server_type": server_type,
        "llm_endpoint": manifest.get("llm_endpoint"),
        "llm_model": manifest.get("llm_model"),
        "parallel": manifest.get("effective_parallel"),
    }
    payload.update({field: manifest.get(field) for field in CONFIG_PAYLOAD_MANIFEST_FIELDS})
    payload.update(
        {
            "slang_db": slang_db,
            "reason_full_mode": reason_full_mode,
            "prompt_version": stable.get("prompt_version"),
        }
    )
    return payload


def expected_runtime_config_hash(
    manifest: dict[str, Any], row_contract: dict[str, Any], *, slang_db: str = "0"
) -> str:
    return hashlib.sha256(
        json.dumps(
            runtime_config_payload(manifest, row_contract, slang_db=slang_db),
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()[:12]


def _runtime_issues(
    *,
    rows: list[dict[str, Any]],
    result_path: Path,
    manifest: dict[str, Any],
    original_row_contract: dict[str, Any] | None,
    original_manifest_contract: dict[str, Any] | None,
    label: str,
) -> tuple[dict[str, Any], list[str]]:
    issues: list[str] = []
    ids, duplicates = _ids_with_duplicates(rows)
    if duplicates:
        issues.append(f"{label}_duplicate_post_ids")
    expected_count = len(rows)
    for field, expected in {
        "input_post_count": expected_count,
        "completed_count": expected_count,
        "flushed_count": expected_count,
        "pending_count": 0,
        "failed_count": 0,
    }.items():
        if manifest.get(field) != expected:
            issues.append(f"{label}_manifest_{field}_mismatch")
    for field, expected in {
        "large_run_complete": True,
        "partial_flush_gap": False,
        "ordered_flush_blocked": False,
    }.items():
        if manifest.get(field) is not expected:
            issues.append(f"{label}_manifest_{field}_mismatch")
    if not _same_path(manifest.get("output_file"), result_path):
        issues.append(f"{label}_manifest_output_file_mismatch")

    row_contract, row_issues = _uniform_row_contract(rows)
    issues.extend(f"{label}_{issue}" for issue in row_issues)
    manifest_contract = _manifest_contract(manifest)
    if row_contract.get("run_id") != str(manifest.get("run_id") or "").strip():
        issues.append(f"{label}_row_manifest_run_id_mismatch")
    stable = row_contract.get("stable") if isinstance(row_contract.get("stable"), dict) else {}
    row_manifest_pairs = {
        "model": "llm_model",
        "llm_endpoint": "llm_endpoint",
        "requested_parallel_raw": "requested_parallel_raw",
        "requested_parallel": "requested_parallel",
        "parallel_policy": "parallel_policy",
        "mcp_health_include_search": "mcp_health_include_search",
        "mcp_health_light_mode": "mcp_health_light_mode",
        "mcp_health_required_ok_count": "mcp_health_required_ok_count",
        "mcp_health_checked_endpoint_count": "mcp_health_checked_endpoint_count",
        "mcp_health_ok_count": "mcp_health_ok_count",
        "mcp_health_failure_count": "mcp_health_failure_count",
    }
    for row_field, manifest_field in row_manifest_pairs.items():
        if stable.get(row_field) != manifest.get(manifest_field):
            issues.append(f"{label}_row_manifest_{row_field}_mismatch")

    config_hash = row_contract.get("config_hash")
    if config_hash and config_hash != expected_runtime_config_hash(manifest, row_contract, slang_db="0"):
        issues.append(f"{label}_config_hash_not_slang_db_off_contract")

    endpoints = [item for item in str(manifest.get("mcp_endpoints") or "").split(",") if item]
    search_contract = {
        "include_search": manifest.get("mcp_health_include_search") is True,
        "non_light": manifest.get("mcp_health_light_mode") is False,
        "shard_count": len(endpoints),
        "required_ok": manifest.get("mcp_health_required_ok_count"),
        "checked": manifest.get("mcp_health_checked_endpoint_count"),
        "ok": manifest.get("mcp_health_ok_count"),
        "failure": manifest.get("mcp_health_failure_count"),
        "reuse_shards_only_reason": manifest.get("mcp_healthy_endpoint_filter_reason"),
    }
    if not (
        search_contract["include_search"]
        and search_contract["non_light"]
        and search_contract["shard_count"] == EXPECTED_SEARCH_SHARDS
        and search_contract["required_ok"] == EXPECTED_SEARCH_SHARDS
        and search_contract["checked"] == EXPECTED_SEARCH_SHARDS
        and search_contract["ok"] == EXPECTED_SEARCH_SHARDS
        and search_contract["failure"] == 0
        and search_contract["reuse_shards_only_reason"] == "reuse_shards_only"
    ):
        issues.append(f"{label}_search_runtime_contract_mismatch")
    if not (
        manifest.get("vlm_enabled") is True
        and manifest.get("ocr_enabled") is True
        and manifest.get("vlm_ocr_semantic_review_ready") is True
        and manifest.get("vlm_ocr_semantic_review_required_for_images") is True
        and manifest.get("vlm_ocr_semantic_review_blocker") is False
    ):
        issues.append(f"{label}_vlm_ocr_contract_mismatch")
    if not (
        manifest.get("dashboard_enabled") is True
        and manifest.get("dashboard_standalone_forwarding") is True
    ):
        issues.append(f"{label}_dashboard_contract_mismatch")

    if original_row_contract is not None:
        original_stable = original_row_contract.get("stable") or {}
        if stable != original_stable:
            issues.append(f"{label}_row_runtime_contract_drift")
    if original_manifest_contract is not None and manifest_contract != original_manifest_contract:
        issues.append(f"{label}_manifest_runtime_contract_drift")

    return {
        "post_ids": ids,
        "row_contract": row_contract,
        "manifest_contract": manifest_contract,
        "search_contract": search_contract,
        "slang_db_off_config_hash_verified": bool(config_hash) and not any(
            issue.endswith("config_hash_not_slang_db_off_contract") for issue in issues
        ),
    }, issues


def _parse_time(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def _run_time(manifest: dict[str, Any]) -> datetime | None:
    try:
        return datetime.strptime(str(manifest.get("run_id") or ""), "%Y%m%d_%H%M%S_%f")
    except ValueError:
        return None


def _probe_scope(audit: dict[str, Any]) -> tuple[str, set[str]]:
    purposes: set[str] = set()
    for shard in audit.get("shards") or []:
        if isinstance(shard, dict) and isinstance(shard.get("search_probe"), dict):
            purpose = str(shard["search_probe"].get("purpose") or "").strip().lower()
            if purpose:
                purposes.add(purpose)
    normalized = {
        value.replace("preflight", "{phase}").replace("postflight", "{phase}")
        for value in purposes
    }
    return (next(iter(normalized)) if len(normalized) == 1 else ""), purposes


def _query_audit_issues(
    preflight: dict[str, Any], postflight: dict[str, Any], manifest: dict[str, Any], label: str
) -> list[str]:
    issues: list[str] = []
    pre_scope, pre_purposes = _probe_scope(preflight)
    post_scope, post_purposes = _probe_scope(postflight)
    pre_summary = preflight.get("search_probe_summary") if isinstance(preflight.get("search_probe_summary"), dict) else {}
    post_summary = postflight.get("search_probe_summary") if isinstance(postflight.get("search_probe_summary"), dict) else {}
    for phase, audit, summary, purposes in (
        ("preflight", preflight, pre_summary, pre_purposes),
        ("postflight", postflight, post_summary, post_purposes),
    ):
        if audit.get("count") != EXPECTED_SEARCH_SHARDS or audit.get("ok_count") != EXPECTED_SEARCH_SHARDS:
            issues.append(f"{label}_{phase}_shard_count_not_healthy16")
        if audit.get("bad_count") != 0:
            issues.append(f"{label}_{phase}_bad_shards_nonzero")
        if not (
            summary.get("enabled") is True
            and summary.get("ok_count") == EXPECTED_SEARCH_SHARDS
            and summary.get("bad_count") == 0
            and summary.get("degraded_count") == 0
            and summary.get("forbidden_engine_count") == 0
        ):
            issues.append(f"{label}_{phase}_query_probe_not_healthy16")
        shards = audit.get("shards") if isinstance(audit.get("shards"), list) else []
        shard_ids = sorted(
            item.get("shard") for item in shards if isinstance(item, dict) and isinstance(item.get("shard"), int)
        )
        if shard_ids != list(range(1, EXPECTED_SEARCH_SHARDS + 1)):
            issues.append(f"{label}_{phase}_shard_ids_mismatch")
        if not purposes or any(phase not in value for value in purposes):
            issues.append(f"{label}_{phase}_probe_purpose_mismatch")
        for item in shards:
            if not isinstance(item, dict):
                issues.append(f"{label}_{phase}_shard_nonobject")
                continue
            healthz = item.get("healthz") if isinstance(item.get("healthz"), dict) else {}
            readyz = item.get("readyz") if isinstance(item.get("readyz"), dict) else {}
            probe = item.get("search_probe") if isinstance(item.get("search_probe"), dict) else {}
            docker = item.get("docker") if isinstance(item.get("docker"), dict) else {}
            if item.get("ok") is not True or healthz.get("ok") is not True or readyz.get("ok") is not True:
                issues.append(f"{label}_{phase}_shard_detail_not_ready")
            if probe.get("ok") is not True or probe.get("degraded") is not False:
                issues.append(f"{label}_{phase}_shard_probe_dirty")
            for component in ("warp", "searchxng", "mcp_bridge", "browser_search"):
                state = docker.get(component) if isinstance(docker.get(component), dict) else {}
                if state.get("ok") is not True:
                    issues.append(f"{label}_{phase}_docker_{component}_not_ok")
    if not pre_scope or pre_scope != post_scope:
        issues.append(f"{label}_pre_post_probe_scope_mismatch")
    if str(pre_summary.get("query") or "").strip() != str(post_summary.get("query") or "").strip():
        issues.append(f"{label}_pre_post_query_mismatch")
    pre_at = _parse_time(preflight.get("generated_at"))
    post_at = _parse_time(postflight.get("generated_at"))
    run_at = _run_time(manifest)
    if pre_at is None or post_at is None or run_at is None:
        issues.append(f"{label}_temporal_binding_timestamp_missing")
    else:
        if not (pre_at < run_at < post_at):
            issues.append(f"{label}_pre_run_post_temporal_order_mismatch")
        if run_at - pre_at > MAX_PREFLIGHT_LEAD:
            issues.append(f"{label}_preflight_stale")
    return sorted(set(issues))


def _publication_issues(
    audit: dict[str, Any], rows: list[dict[str, Any]], result_path: Path, label: str
) -> list[str]:
    issues: list[str] = []
    recomputed = audit_publication_rows(rows)
    if audit.get("gate") != "GO" or recomputed.get("gate") != "GO":
        issues.append(f"{label}_publication_gate_not_go")
    if audit.get("summary") != recomputed.get("summary") or audit.get("violations") != recomputed.get("violations"):
        issues.append(f"{label}_publication_audit_not_deterministic_recompute")
    bindings = audit.get("result_artifacts") if isinstance(audit.get("result_artifacts"), list) else []
    if len(bindings) != 1:
        issues.append(f"{label}_publication_result_binding_count_mismatch")
    else:
        binding = bindings[0] if isinstance(bindings[0], dict) else {}
        if not _same_path(binding.get("path"), result_path):
            issues.append(f"{label}_publication_result_path_mismatch")
        if binding.get("sha256") != file_sha256(result_path):
            issues.append(f"{label}_publication_result_sha256_mismatch")
        if binding.get("size_bytes") != result_path.stat().st_size:
            issues.append(f"{label}_publication_result_size_mismatch")
        if binding.get("row_count") != len(rows):
            issues.append(f"{label}_publication_result_row_count_mismatch")
    return issues


def _golden_issues(
    audit: dict[str, Any],
    rows: list[dict[str, Any]],
    manifest: dict[str, Any],
    result_path: Path,
    manifest_path: Path,
    golden_path: Path,
    golden_rows: list[dict[str, Any]],
    label: str,
) -> list[str]:
    issues: list[str] = []
    expected_bindings = {
        "after_result_sha256": file_sha256(result_path),
        "merged_manifest_sha256": file_sha256(manifest_path),
        "golden_manifest_sha256": file_sha256(golden_path),
    }
    for field, expected in expected_bindings.items():
        if audit.get(field) != expected:
            issues.append(f"{label}_golden_{field}_mismatch")
    for field, expected_path in {
        "after_result_path": result_path,
        "merged_manifest_path": manifest_path,
        "golden_manifest_path": golden_path,
    }.items():
        if not _same_path(audit.get(field), expected_path):
            issues.append(f"{label}_golden_{field}_mismatch")
    audit_rows_value = audit.get("rows") if isinstance(audit.get("rows"), list) else []
    try:
        audit_ids, duplicates = _ids_with_duplicates(audit_rows_value)
    except ValueError:
        audit_ids, duplicates = [], []
        issues.append(f"{label}_golden_rows_invalid")
    if duplicates:
        issues.append(f"{label}_golden_duplicate_post_ids")
    audit_by_id = {
        _post_id(row): row for row in audit_rows_value if isinstance(row, dict) and row.get("post_id") is not None
    }
    replay_ids = [_post_id(row) for row in rows]
    if any(post_id not in audit_by_id for post_id in replay_ids):
        issues.append(f"{label}_golden_replay_rows_missing")
    if any(audit_by_id.get(post_id, {}).get("passed") is not True for post_id in replay_ids):
        issues.append(f"{label}_golden_replay_semantic_not_pass")
    recomputed = build_golden_audit(
        canary_rows=rows,
        golden_rows=golden_rows,
        run_manifest=manifest,
        canary_result=result_path,
        canary_manifest=manifest_path,
        golden_manifest=golden_path,
    )
    recomputed_by_id = {_post_id(row): row for row in recomputed.get("rows") or []}
    for post_id in replay_ids:
        if audit_by_id.get(post_id) != recomputed_by_id.get(post_id):
            issues.append(f"{label}_golden_row_not_deterministic_recompute:{post_id}")
    return sorted(set(issues))


def _prepare_gate_ids(
    prepare: dict[str, Any], original_rows: list[dict[str, Any]], golden_rows: list[dict[str, Any]]
) -> tuple[list[str], list[str], list[str]]:
    issues: list[str] = []
    hard_details = prepare.get("required_search_hard_blocker_rows")
    unreviewed_details = prepare.get("unreviewed_search_row_details")
    if not isinstance(hard_details, list) or not isinstance(unreviewed_details, list):
        return [], [], ["prepare_gate_issue_rows_missing"]
    hard_ids, hard_duplicates = _ids_with_duplicates(hard_details)
    unreviewed_ids, unreviewed_duplicates = _ids_with_duplicates(unreviewed_details)
    if hard_duplicates or unreviewed_duplicates or set(hard_ids) & set(unreviewed_ids):
        issues.append("prepare_gate_issue_post_ids_not_unique_disjoint")
    if prepare.get("required_search_hard_blocker") != EXPECTED_HARD_ROWS or len(hard_ids) != EXPECTED_HARD_ROWS:
        issues.append("prepare_gate_required_hard_count_not_6")
    if prepare.get("unreviewed_search_rows") != EXPECTED_UNREVIEWED_ROWS or len(unreviewed_ids) != EXPECTED_UNREVIEWED_ROWS:
        issues.append("prepare_gate_unreviewed_count_not_4")

    golden_by_id = {_post_id(row): row for row in golden_rows}
    derived_hard: list[str] = []
    derived_unreviewed: list[str] = []
    for row in original_rows:
        health = _search_health(row)
        search_issue, _ = _search_issue(health)
        if not search_issue:
            continue
        post_id = _post_id(row)
        public = _public_state(row)
        golden = golden_by_id.get(post_id) or {}
        publish_dependency = bool(
            public.get("official_title")
            or public.get("official_url")
            or public.get("publish_allowed") is True
            or (golden and golden.get("expected_no_public_title") is False)
        )
        (derived_hard if publish_dependency else derived_unreviewed).append(post_id)
    if hard_ids != derived_hard:
        issues.append("prepare_gate_required_hard_ids_not_exact_recompute")
    if unreviewed_ids != derived_unreviewed:
        issues.append("prepare_gate_unreviewed_ids_not_exact_recompute")
    return hard_ids, unreviewed_ids, issues


def build_composite_gate(
    *,
    original_result: Path,
    original_manifest: Path,
    original_search_prepare_gate: Path,
    golden_manifest: Path,
    replay_results: list[Path],
    replay_manifests: list[Path],
    replay_preflights: list[Path],
    replay_postflights: list[Path],
    replay_publication_audits: list[Path],
    replay_golden_audits: list[Path],
    terminal_ledger: Path,
    terminal_consensus_report: Path,
) -> dict[str, Any]:
    # The upstream terminal validator caches artifact hashes for large full375
    # audits.  A composite gate may be invoked repeatedly in one test/process
    # after a mutation, so start from live bytes every time.
    _sha256_file.cache_clear()
    blockers: list[str] = []
    paths_by_kind = {
        "replay_result": replay_results,
        "replay_manifest": replay_manifests,
        "replay_preflight": replay_preflights,
        "replay_postflight": replay_postflights,
        "replay_publication_audit": replay_publication_audits,
        "replay_golden_audit": replay_golden_audits,
    }
    replay_count = len(replay_results)
    if replay_count == 0 or any(len(paths) != replay_count for paths in paths_by_kind.values()):
        blockers.append("replay_artifact_group_count_mismatch")

    original_rows = load_json_or_jsonl(original_result)
    original_manifest_payload = _load_json(original_manifest)
    prepare = _load_json(original_search_prepare_gate)
    golden_payload = _load_json(golden_manifest)
    golden_rows = golden_payload.get("rows") if isinstance(golden_payload.get("rows"), list) else []
    terminal_rows = _load_jsonl(terminal_ledger)
    consensus = _load_json(terminal_consensus_report)

    original_ids, original_duplicates = _ids_with_duplicates(original_rows)
    golden_ids, golden_duplicates = _ids_with_duplicates(golden_rows)
    if len(original_rows) != EXPECTED_ORIGINAL_ROWS or original_duplicates:
        blockers.append("original_result_not_unique18")
    if len(golden_rows) != EXPECTED_ORIGINAL_ROWS or golden_duplicates:
        blockers.append("golden_manifest_not_unique18")
    if original_ids != golden_ids:
        blockers.append("original_result_order_not_golden18_order")

    provenance = prepare.get("artifact_provenance") if isinstance(prepare.get("artifact_provenance"), dict) else {}
    for label, path in {
        "result": original_result,
        "manifest": original_manifest,
        "golden_manifest": golden_manifest,
    }.items():
        ref = provenance.get(label) if isinstance(provenance.get(label), dict) else {}
        if not _same_path(ref.get("path"), path):
            blockers.append(f"prepare_{label}_path_mismatch")
        if ref.get("sha256") != file_sha256(path):
            blockers.append(f"prepare_{label}_sha256_mismatch")

    hard_ids, unreviewed_ids, prepare_issues = _prepare_gate_ids(prepare, original_rows, golden_rows)
    blockers.extend(prepare_issues)

    original_runtime, original_runtime_issues = _runtime_issues(
        rows=original_rows,
        result_path=original_result,
        manifest=original_manifest_payload,
        original_row_contract=None,
        original_manifest_contract=None,
        label="original",
    )
    blockers.extend(original_runtime_issues)

    terminal_ids, terminal_duplicates = _ids_with_duplicates(terminal_rows)
    consensus_ids = [_post_id(value) for value in consensus.get("consensus_post_ids") or []]
    excluded_values = consensus.get("excluded_rows")
    if not isinstance(excluded_values, list):
        excluded_values = consensus.get("excluded_disagreements")
    excluded_values = excluded_values if isinstance(excluded_values, list) else []
    excluded_ids, excluded_duplicates = _ids_with_duplicates(excluded_values)
    if terminal_duplicates or excluded_duplicates or len(set(consensus_ids)) != len(consensus_ids):
        blockers.append("terminal_consensus_post_ids_not_unique")
    if consensus.get("builder_gate") not in (None, "GO"):
        blockers.append("terminal_consensus_builder_gate_not_go")
    if terminal_ids != consensus_ids:
        blockers.append("terminal_ledger_ids_not_consensus_ids")
    safe_expected = [post_id for post_id in unreviewed_ids if post_id in set(consensus_ids)]
    if terminal_ids != safe_expected or len(terminal_ids) != EXPECTED_CONSENSUS_SAFE_ROWS:
        blockers.append("terminal_consensus_safe_ids_not_exact_unreviewed2")
    null_blocker_ids = [post_id for post_id in unreviewed_ids if post_id in set(excluded_ids)]
    if len(null_blocker_ids) != EXPECTED_BLIND_BLOCKER_NULL_ROWS:
        blockers.append("blind_blocker_null_ids_not_exact2")
    if set(unreviewed_ids) != set(terminal_ids) | set(null_blocker_ids):
        blockers.append("unreviewed_ids_not_partitioned_by_terminal_and_replay")
    issue_scope = set(hard_ids) | set(unreviewed_ids)
    if not set(excluded_ids).issubset(issue_scope):
        blockers.append("terminal_consensus_excluded_ids_outside_original_issue_scope")
    for item in excluded_values:
        if _post_id(item) not in null_blocker_ids:
            continue
        blind = item.get("blind") if isinstance(item.get("blind"), dict) else {}
        if blind.get("classification") != "blocker" or blind.get("terminal_safe") is not False:
            blockers.append("blind_blocker_null_consensus_provenance_invalid")

    output_artifacts = consensus.get("output_artifacts") if isinstance(consensus.get("output_artifacts"), dict) else {}
    ledger_ref = output_artifacts.get("ledger") if isinstance(output_artifacts.get("ledger"), dict) else {}
    if not ledger_ref and isinstance(consensus.get("output_ledger"), dict):
        ledger_ref = consensus["output_ledger"]
    if not _same_path(ledger_ref.get("path"), terminal_ledger):
        blockers.append("terminal_consensus_ledger_path_mismatch")
    if ledger_ref.get("sha256") != file_sha256(terminal_ledger):
        blockers.append("terminal_consensus_ledger_sha256_mismatch")
    if ledger_ref.get("row_count") != len(terminal_rows):
        blockers.append("terminal_consensus_ledger_row_count_mismatch")
    consensus_result_ref = (consensus.get("input_artifacts") or {}).get("result") or {}
    if not _same_path(consensus_result_ref.get("path"), original_result) or consensus_result_ref.get("sha256") != file_sha256(original_result):
        blockers.append("terminal_consensus_original_result_binding_mismatch")

    original_by_id = {_post_id(row): row for row in original_rows}
    terminal_validation: list[dict[str, Any]] = []
    for ledger in terminal_rows:
        post_id = _post_id(ledger)
        row = original_by_id.get(post_id)
        issues = ["terminal_post_id_not_in_original"] if row is None else _terminal_issues(ledger, row, _public_state(row))
        if issues:
            blockers.extend(f"terminal_{post_id}:{issue}" for issue in issues)
        terminal_validation.append({"post_id": post_id, "issues": issues})

    # Replay batches are intentionally lane-separated: exact hard6 first, then
    # the two blind-blocker null rows.  Preserve source order inside each batch;
    # do not require an artificial cross-batch Golden18 interleave.
    expected_replay_ids = [*hard_ids, *null_blocker_ids]
    replay_reports: list[dict[str, Any]] = []
    replay_union: list[str] = []
    replay_seen: set[str] = set()
    if not blockers or replay_count:
        for index in range(min(len(paths) for paths in paths_by_kind.values()) if paths_by_kind else 0):
            label = f"replay_{index + 1}"
            result_path = replay_results[index]
            manifest_path = replay_manifests[index]
            preflight_path = replay_preflights[index]
            postflight_path = replay_postflights[index]
            publication_path = replay_publication_audits[index]
            golden_audit_path = replay_golden_audits[index]
            rows = load_json_or_jsonl(result_path)
            manifest_payload = _load_json(manifest_path)
            preflight_payload = _load_json(preflight_path)
            postflight_payload = _load_json(postflight_path)
            publication_payload = _load_json(publication_path)
            golden_audit_payload = _load_json(golden_audit_path)
            ids, duplicates = _ids_with_duplicates(rows)
            replay_issues: list[str] = []
            if duplicates:
                replay_issues.append(f"{label}_duplicate_post_ids")
            overlap = sorted(set(ids) & replay_seen)
            if overlap:
                replay_issues.append(f"{label}_coverage_overlap")
            extras = sorted(set(ids) - set(expected_replay_ids))
            if extras:
                replay_issues.append(f"{label}_coverage_extra_post_ids")
            expected_group_order = [post_id for post_id in golden_ids if post_id in set(ids)]
            if ids != expected_group_order:
                replay_issues.append(f"{label}_result_order_not_golden_source_order")
            if result_path.resolve() == original_result.resolve():
                replay_issues.append(f"{label}_best_of_merge_or_original_reuse_forbidden")

            runtime_report, runtime_issues = _runtime_issues(
                rows=rows,
                result_path=result_path,
                manifest=manifest_payload,
                original_row_contract=original_runtime.get("row_contract"),
                original_manifest_contract=original_runtime.get("manifest_contract"),
                label=label,
            )
            replay_issues.extend(runtime_issues)
            for row in rows:
                health = _search_health(row)
                status = str(health.get("status") or "").strip()
                if status not in {"ok", "SEARCH_DEGRADED_RECOVERED"}:
                    replay_issues.append(f"{label}_row_search_status_not_clean:{_post_id(row)}")
                if int(health.get("unrecovered_degraded") or 0) != 0 or _search_health_issues(health):
                    replay_issues.append(f"{label}_row_search_health_dirty:{_post_id(row)}")
            replay_issues.extend(_query_audit_issues(preflight_payload, postflight_payload, manifest_payload, label))
            replay_issues.extend(_publication_issues(publication_payload, rows, result_path, label))
            replay_issues.extend(
                _golden_issues(
                    golden_audit_payload,
                    rows,
                    manifest_payload,
                    result_path,
                    manifest_path,
                    golden_manifest,
                    golden_rows,
                    label,
                )
            )
            blockers.extend(replay_issues)
            replay_union.extend(ids)
            replay_seen.update(ids)
            replay_reports.append(
                {
                    "label": label,
                    "post_ids": ids,
                    "gate": "GO" if not replay_issues else "NO-GO",
                    "issues": sorted(set(replay_issues)),
                    "runtime": runtime_report,
                    "artifacts": {
                        "result": _artifact(result_path, row_count=len(rows)),
                        "manifest": _artifact(manifest_path),
                        "preflight": _artifact(preflight_path),
                        "postflight": _artifact(postflight_path),
                        "publication_audit": _artifact(publication_path),
                        "golden_audit": _artifact(golden_audit_path),
                    },
                }
            )

    if replay_union != expected_replay_ids:
        blockers.append("replay_union_missing_extra_duplicate_or_order_mismatch")
    if len(replay_union) != len(set(replay_union)):
        blockers.append("replay_union_duplicate_post_ids")
    if set(replay_union) & set(terminal_ids):
        blockers.append("replay_terminal_coverage_overlap")
    if set(replay_union) | set(terminal_ids) != set(hard_ids) | set(unreviewed_ids):
        blockers.append("original_search_issue_scope_not_fully_accounted")

    blockers = sorted(set(blockers))
    gate = "GO" if not blockers else "NO-GO"
    return {
        "report_type": "search_recovery_composite_gate",
        "builder_version": BUILDER_VERSION,
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "gate": gate,
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "required_search_hard_blocker": 0 if gate == "GO" else len(hard_ids),
        "unreviewed_search_rows": 0 if gate == "GO" else len(unreviewed_ids),
        "original_issue_accounting": {
            "required_hard_post_ids": hard_ids,
            "unreviewed_post_ids": unreviewed_ids,
            "expected_replay_post_ids": expected_replay_ids,
            "terminal_consensus_safe_post_ids": terminal_ids,
            "blind_blocker_null_replay_post_ids": null_blocker_ids,
            "replay_union_post_ids": replay_union,
        },
        "terminal_validation": terminal_validation,
        "replays": replay_reports,
        "blockers": blockers,
        "semantic_result_policy": {
            "authoritative_result": str(original_result),
            "authoritative_result_sha256": file_sha256(original_result),
            "replay_rows_merged_into_original": False,
            "best_of_semantic_merge_performed": False,
            "replay_role": "search_recovery_evidence_only",
        },
        "artifact_provenance": {
            "original_result": _artifact(original_result, row_count=len(original_rows)),
            "original_manifest": _artifact(original_manifest),
            "original_search_prepare_gate": _artifact(original_search_prepare_gate),
            "golden_manifest": _artifact(golden_manifest, row_count=len(golden_rows)),
            "terminal_ledger": _artifact(terminal_ledger, row_count=len(terminal_rows)),
            "terminal_consensus_report": _artifact(terminal_consensus_report),
        },
        "approval_boundary": {
            "dashboard_is_not_approval": True,
            "golden18_search_recovery_is_not_full375_approval": True,
            "fresh375_post_run_gates_still_required": True,
            "production_full_scan_approval": False,
        },
    }


def write_markdown(report: dict[str, Any], path: Path) -> None:
    accounting = report["original_issue_accounting"]
    lines = [
        "# Golden18 search 복구 composite gate",
        "",
        f"- gate: `{report['gate']}`",
        f"- required_search_hard_blocker: `{report['required_search_hard_blocker']}`",
        f"- unreviewed_search_rows: `{report['unreviewed_search_rows']}`",
        f"- 원본 hard IDs: `{accounting['required_hard_post_ids']}`",
        f"- 원본 unreviewed IDs: `{accounting['unreviewed_post_ids']}`",
        f"- replay 회계 IDs: `{accounting['replay_union_post_ids']}`",
        f"- consensus safe terminal IDs: `{accounting['terminal_consensus_safe_post_ids']}`",
        "- Replay 결과는 원본 Golden18 semantic result에 병합하지 않았고 search 복구 증거로만 사용했다.",
        "- 이 gate는 Golden18 search 복구 경계이며 fresh375/full scan 승인이 아니다.",
        "",
        "## Replay",
        "",
    ]
    for replay in report["replays"]:
        lines.append(
            f"- `{replay['label']}`: gate=`{replay['gate']}`, post_ids=`{replay['post_ids']}`, issues=`{replay['issues']}`"
        )
    lines.extend(["", "## Blocker", "", f"- `{report['blockers']}`", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the deterministic Golden18 search recovery composite gate.")
    parser.add_argument("--original-result", required=True, type=Path)
    parser.add_argument("--original-manifest", required=True, type=Path)
    parser.add_argument("--original-search-prepare-gate", required=True, type=Path)
    parser.add_argument("--golden-manifest", required=True, type=Path)
    parser.add_argument("--replay-result", required=True, action="append", type=Path)
    parser.add_argument("--replay-manifest", required=True, action="append", type=Path)
    parser.add_argument("--replay-preflight", required=True, action="append", type=Path)
    parser.add_argument("--replay-postflight", required=True, action="append", type=Path)
    parser.add_argument("--replay-publication-audit", required=True, action="append", type=Path)
    parser.add_argument("--replay-golden-audit", required=True, action="append", type=Path)
    parser.add_argument("--terminal-ledger", required=True, type=Path)
    parser.add_argument("--terminal-consensus-report", required=True, type=Path)
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-md", required=True, type=Path)
    parser.add_argument("--fail-on-no-go", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_composite_gate(
        original_result=args.original_result,
        original_manifest=args.original_manifest,
        original_search_prepare_gate=args.original_search_prepare_gate,
        golden_manifest=args.golden_manifest,
        replay_results=args.replay_result,
        replay_manifests=args.replay_manifest,
        replay_preflights=args.replay_preflight,
        replay_postflights=args.replay_postflight,
        replay_publication_audits=args.replay_publication_audit,
        replay_golden_audits=args.replay_golden_audit,
        terminal_ledger=args.terminal_ledger,
        terminal_consensus_report=args.terminal_consensus_report,
    )
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    with args.output_json.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    write_markdown(report, args.output_md)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 2 if args.fail_on_no_go and report["gate"] != "GO" else 0


if __name__ == "__main__":
    raise SystemExit(main())
