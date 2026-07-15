from __future__ import annotations

import argparse
import hashlib
import json
import stat
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


ROW_STABLE_SIGNATURE_FIELDS = (
    "model",
    "llm_endpoint",
    "llm_mode",
    "prompt_version",
    "requested_parallel_raw",
    "requested_parallel",
    "effective_parallel",
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
    "mcp_parallel_before_health_filter",
    "mcp_parallel_after_health_filter",
)
ROW_TO_MANIFEST_FIELDS = {
    "model": "llm_model",
    "llm_endpoint": "llm_endpoint",
    "requested_parallel_raw": "requested_parallel_raw",
    "requested_parallel": "requested_parallel",
    "effective_parallel": "effective_parallel",
    "parallel_policy": "parallel_policy",
    "model_parallel_max": "model_parallel_max",
    "model_parallel_cap_applied": "model_parallel_cap_applied",
    "model_parallel_cap_model": "model_parallel_cap_model",
    "mcp_health_include_search": "mcp_health_include_search",
    "mcp_health_light_mode": "mcp_health_light_mode",
    "mcp_health_required_ok_count": "mcp_health_required_ok_count",
    "mcp_health_checked_endpoint_count": "mcp_health_checked_endpoint_count",
    "mcp_health_probe_batch_size": "mcp_health_probe_batch_size",
    "mcp_health_probe_stopped_after_required_ok": "mcp_health_probe_stopped_after_required_ok",
    "mcp_health_workers": "mcp_health_workers",
    "mcp_health_attempts": "mcp_health_attempts",
    "mcp_health_timeout_sec": "mcp_health_timeout_sec",
    "mcp_health_search_max_latency_ms": "mcp_health_search_max_latency_ms",
    "mcp_health_search_min_results": "mcp_health_search_min_results",
    "mcp_health_ok_count": "mcp_health_ok_count",
    "mcp_health_failure_count": "mcp_health_failure_count",
    "mcp_healthy_endpoint_filter": "mcp_healthy_endpoint_filter",
    "mcp_healthy_endpoint_filter_reason": "mcp_healthy_endpoint_filter_reason",
    "mcp_healthy_endpoint_filter_autogen": "mcp_healthy_endpoint_filter_autogen",
    "mcp_healthy_autogen_endpoint_filter": "mcp_healthy_autogen_endpoint_filter",
    "mcp_healthy_autogen_endpoint_filter_reason": "mcp_healthy_autogen_endpoint_filter_reason",
    "mcp_reuse_shards_only_health_filtered": "mcp_reuse_shards_only_health_filtered",
    "mcp_goal_run_health_filtered": "mcp_goal_run_health_filtered",
    "mcp_requested_endpoint_count_before_health_filter": "mcp_requested_endpoint_count_before_health_filter",
    "mcp_healthy_endpoint_count": "mcp_healthy_endpoint_count",
    "mcp_endpoint_count_after_health_filter": "mcp_endpoint_count_after_health_filter",
    "mcp_parallel_before_health_filter": "mcp_parallel_before_health_filter",
    "mcp_parallel_after_health_filter": "mcp_parallel_after_health_filter",
}
MANIFEST_STABLE_SIGNATURE_FIELDS = (
    "llm_model",
    "llm_endpoint",
    "llm_stream_first_token_timeout_seconds",
    "llm_stream_idle_timeout_seconds",
    "llm_stream_signal_idle_timeout_seconds",
    "requested_parallel_raw",
    "requested_parallel",
    "effective_parallel",
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
    "mcp_parallel_before_health_filter",
    "mcp_parallel_after_health_filter",
    "vlm_enabled",
    "ocr_enabled",
    "vlm_ocr_semantic_review_ready",
    "vlm_ocr_semantic_review_required_for_images",
    "dashboard_enabled",
    "dashboard_mode",
    "dashboard_standalone_forwarding",
)
PLAN_REQUIRED_ENV_FIELDS = (
    "MCP_HEALTH_INCLUDE_SEARCH",
    "MCP_HEALTH_LIGHT_MODE",
    "MCP_HEALTH_REQUIRED_OK",
    "MCP_HEALTH_PROBE_BATCH_SIZE",
)
PLAN_RUNTIME_CONTRACT_FIELDS = (
    "requested_parallel",
    "dashboard_required",
    "no_dashboard_forbidden",
    "reuse_shards_only",
    "slang_db",
    "vlm",
    "ocr",
    "require_vlm_ocr_for_images",
)
RAW_CONFIG_HASH_SIZE_DEPENDENT_REASON = (
    "expert_main config_hash includes input_post_count and mcp_run_post_count_for_lifecycle; "
    "component runs with different input sizes must be homogeneous internally but need not share the raw hash"
)
TRUST_ANCHOR_REPORT_TYPE = "interrupted_merge_preflight_trust_anchor"
TRUST_ANCHOR_VERSION = "interrupted-merge-trust-v2"
REPO_ROOT = Path(__file__).resolve().parents[1]
PRODUCTION_PANEL_PATH = (
    REPO_ROOT
    / "out/regression_safe_grounding_20260626_000008_928006_loop01/panel/regression_panel_input.jsonl"
).resolve()
PRODUCTION_BASELINE_PATH = (
    REPO_ROOT
    / "out/regression_safe_grounding_20260626_000008_928006_loop01/baseline/loop638_adjudicated_rebaseline_result.json"
).resolve()
PRODUCTION_GOLDEN_PATH = (
    REPO_ROOT
    / "out/regression_safe_grounding_20260626_000008_928006_loop01/golden/golden_manifest.json"
).resolve()
PRODUCTION_PANEL_SHA256 = "746c89217f8ab7d3dd44b3733ad8ab13801ebe9d995c125cc952806d7aed0cbe"
PRODUCTION_BASELINE_SHA256 = "958b5c547e03df3931d25606b4e8204fcb85a58a6642d70443478adad91c74cb"
PRODUCTION_GOLDEN_SHA256 = "2b9a0d882f22f23de246bfe18bb373ed1d98ade88ef1f10f9cb6952de22f9096"
PRODUCTION_V2_TRUST_ANCHOR_PATH = (
    REPO_ROOT / "docs/devs/loop641_premerge_runtime_trust_anchor_v2.json"
).resolve()
PRODUCTION_V2_TRUST_ANCHOR_SHA256 = (
    "8a7487cff066d162c556678b3f76971436b4a4cba0aad1963b0312af0d2956b8"
)
SUPERSEDED_V1_TRUST_ANCHOR_PATH = (
    REPO_ROOT / "docs/devs/loop641_premerge_runtime_trust_anchor.json"
).resolve()
SUPERSEDED_V1_TRUST_ANCHOR_SHA256 = (
    "332780a30079363747308bad2bd1d3834a3ffce2982d88729f16df5e11023a7a"
)
MERGE_BINDING_RECEIPT_REPORT_TYPE = "interrupted_merge_detached_binding_receipt"
MERGE_BINDING_RECEIPT_SCHEMA_VERSION = "interrupted-merge-binding-receipt-v1"
MERGE_BINDING_RECEIPT_FINALIZATION_MARKER = "MERGE_OUTPUT_SET_FINALIZED"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line_no, line in enumerate(handle, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"expected object at {path}:{line_no}")
            rows.append(row)
    return rows


def _object_rows(payload: Any, label: str) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise ValueError(f"{label} must be a JSON array")
    rows = [row for row in payload if isinstance(row, dict)]
    if len(rows) != len(payload):
        raise ValueError(f"{label} contains non-object rows")
    return rows


def _post_id(row: dict[str, Any]) -> str:
    value = row.get("post_id")
    text = "" if value is None else str(value).strip()
    if not text:
        raise ValueError("row is missing post_id")
    return text


def _checkpoint_post_id(row: dict[str, Any]) -> str:
    result = row.get("result") if isinstance(row.get("result"), dict) else {}
    wrapper_id = _post_id(row)
    result_id = _post_id(result)
    if wrapper_id != result_id:
        raise ValueError(f"checkpoint wrapper/result post_id mismatch: {wrapper_id}/{result_id}")
    return wrapper_id


def _index(rows: list[dict[str, Any]], label: str) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for row in rows:
        post_id = _post_id(row)
        if post_id in index:
            raise ValueError(f"{label} duplicate post_id: {post_id}")
        index[post_id] = row
    return index


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def runtime_code_tree_projection(repo_root: Path) -> dict[str, Any]:
    root = repo_root.resolve()
    candidates = [root / "expert_main.py"]
    src_root = root / "src"
    if src_root.is_dir():
        candidates.extend(path for path in src_root.rglob("*") if path.is_file())
    files: list[dict[str, str]] = []
    for path in sorted(set(candidates), key=lambda item: item.as_posix()):
        relative = path.resolve().relative_to(root).as_posix()
        parts = Path(relative).parts
        if "__pycache__" in parts or ".pytest_cache" in parts:
            continue
        if path.suffix.lower() in {".pyc", ".pyo"}:
            continue
        if not path.is_file():
            raise ValueError(f"runtime code file missing: {relative}")
        files.append({"path": relative, "sha256": _sha256(path)})
    if not files or files[0]["path"] != "expert_main.py":
        raise ValueError("runtime code tree must include expert_main.py")
    return {
        "file_count": len(files),
        "files": files,
        "tree_sha256": _canonical_hash(files),
    }


def _immutable_artifact_projection(path: Path, payload: Any) -> dict[str, Any]:
    return {
        "path": str(path.resolve()),
        "byte_sha256": _sha256(path),
        "canonical_sha256": _canonical_hash(payload),
        "size_bytes": path.stat().st_size,
    }


def _row_artifact_projection(
    path: Path,
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    post_ids = [_post_id(row) for row in rows]
    if len(set(post_ids)) != len(post_ids):
        raise ValueError(f"row artifact duplicate post_id: {path}")
    return {
        **_immutable_artifact_projection(path, rows),
        "row_count": len(rows),
        "post_id_order_sha256": _canonical_hash(post_ids),
        "post_id_set_sha256": _canonical_hash(sorted(post_ids)),
    }


def validate_premerge_trust_anchor(
    *,
    anchor: dict[str, Any],
    anchor_path: Path,
    source_jsonl: Path,
    recovered_result_path: Path,
    source_checkpoint_rows: list[dict[str, Any]],
    source_checkpoint_path: Path,
    recovery_summary_path: Path,
    source_manifest: dict[str, Any],
    source_manifest_path: Path,
    source_plan: dict[str, Any],
    source_plan_path: Path,
    recovered_rows: list[dict[str, Any]],
    recovery_summary: dict[str, Any],
    residual_input_rows: list[dict[str, Any]],
    residual_input_path: Path,
    residual_manifest: dict[str, Any],
    residual_manifest_path: Path,
    residual_plan: dict[str, Any],
    residual_plan_path: Path,
    residual_rows: list[dict[str, Any]],
    expected_source_count: int,
    expected_recovered_count: int,
    expected_residual_count: int,
    repo_root: Path = REPO_ROOT,
    allow_untrusted_test_roots: bool = False,
    expected_trust_anchor_sha256: str | None = None,
) -> dict[str, Any]:
    actual_anchor_sha256 = _sha256(anchor_path)
    expected_anchor_sha256 = str(expected_trust_anchor_sha256 or "").strip().lower()
    if len(expected_anchor_sha256) != 64:
        raise ValueError("expected trust anchor sha256 is required")
    if allow_untrusted_test_roots:
        if actual_anchor_sha256 != expected_anchor_sha256:
            raise ValueError("test trust anchor sha256 mismatch")
    else:
        if anchor_path.resolve() == SUPERSEDED_V1_TRUST_ANCHOR_PATH:
            raise ValueError("v1 trust anchor is SUPERSEDED_NO_APPROVAL")
        if expected_anchor_sha256 == SUPERSEDED_V1_TRUST_ANCHOR_SHA256:
            raise ValueError("v1 trust anchor sha256 is SUPERSEDED_NO_APPROVAL")
        if expected_anchor_sha256 != PRODUCTION_V2_TRUST_ANCHOR_SHA256:
            raise ValueError("caller expected trust anchor sha256 is not the compiled production pin")
        if anchor_path.resolve() != PRODUCTION_V2_TRUST_ANCHOR_PATH:
            raise ValueError("production trust anchor path is not the compiled v2 path")
        if actual_anchor_sha256 != PRODUCTION_V2_TRUST_ANCHOR_SHA256:
            raise ValueError("production v2 trust anchor bytes do not match compiled sha256")
    if anchor.get("report_type") != TRUST_ANCHOR_REPORT_TYPE:
        raise ValueError("trust anchor report_type mismatch")
    if anchor.get("anchor_version") != TRUST_ANCHOR_VERSION:
        raise ValueError("trust anchor version mismatch")
    if anchor.get("gate") != "GO" or anchor.get("generated_before_completion") is not True:
        raise ValueError("trust anchor is not a pre-completion GO anchor")
    if anchor_path.stat().st_mode & stat.S_IWRITE:
        raise ValueError("trust anchor file is not read-only")
    topology = anchor.get("topology") if isinstance(anchor.get("topology"), dict) else {}
    if topology.get("profile") != "interrupted_merge_75_300":
        raise ValueError("merge requires interrupted_merge_75_300 trust profile")
    expected_counts = anchor.get("expected_counts") if isinstance(anchor.get("expected_counts"), dict) else {}
    if expected_counts != {
        "source_rows": expected_source_count,
        "recovered_rows": expected_recovered_count,
        "residual_rows": expected_residual_count,
        "golden_rows": 18 if not allow_untrusted_test_roots else expected_counts.get("golden_rows"),
    }:
        raise ValueError("trust anchor expected counts mismatch")

    supplied_payload_hash = str(anchor.get("anchor_payload_sha256") or "")
    payload_without_hash = dict(anchor)
    payload_without_hash.pop("anchor_payload_sha256", None)
    if supplied_payload_hash != _canonical_hash(payload_without_hash):
        raise ValueError("trust anchor payload digest mismatch")

    source_ids = [_post_id(row) for row in _load_jsonl(source_jsonl)]
    recovered_ids = [_post_id(row) for row in recovered_rows]
    residual_input_ids = [_post_id(row) for row in residual_input_rows]
    expected_residual_ids = [post_id for post_id in source_ids if post_id not in set(recovered_ids)]
    if residual_input_ids != expected_residual_ids:
        raise ValueError("anchored residual input is not the exact source-order complement")
    if len(set(source_ids)) != len(source_ids) or len(set(recovered_ids)) != len(recovered_ids):
        raise ValueError("anchored partition contains duplicate post_id")

    checkpoint_completed = [
        row for row in source_checkpoint_rows if row.get("status") == "completed"
    ]
    if len(checkpoint_completed) != len(source_checkpoint_rows):
        raise ValueError("anchored source checkpoint contains non-completed rows")
    checkpoint_completed_sorted = sorted(
        checkpoint_completed,
        key=lambda row: int(row.get("global_idx") or 0),
    )
    checkpoint_results = [row.get("result") for row in checkpoint_completed_sorted]
    if any(not isinstance(row, dict) for row in checkpoint_results):
        raise ValueError("anchored source checkpoint completed result missing")
    if checkpoint_results != recovered_rows:
        raise ValueError("anchored recovered result/source checkpoint payload mismatch")
    checkpoint_indexes = [row.get("global_idx") for row in checkpoint_completed_sorted]
    if any(
        isinstance(index, bool) or not isinstance(index, int)
        for index in checkpoint_indexes
    ):
        raise ValueError("anchored source checkpoint global_idx invalid")

    immutable = (
        anchor.get("immutable_components")
        if isinstance(anchor.get("immutable_components"), dict)
        else {}
    )
    expected_immutable = {
        "recovered_result": _row_artifact_projection(recovered_result_path, recovered_rows),
        "recovery_summary": _immutable_artifact_projection(
            recovery_summary_path, recovery_summary
        ),
        "source_checkpoint": {
            **_immutable_artifact_projection(source_checkpoint_path, source_checkpoint_rows),
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
            "failed_row_count": 0,
        },
        "residual_input": _row_artifact_projection(
            residual_input_path, residual_input_rows
        ),
        "source_manifest": _immutable_artifact_projection(
            source_manifest_path, source_manifest
        ),
        "source_plan": _immutable_artifact_projection(source_plan_path, source_plan),
        "residual_plan": _immutable_artifact_projection(residual_plan_path, residual_plan),
    }
    if immutable != expected_immutable:
        raise ValueError("trust anchor immutable component binding mismatch")
    partition = anchor.get("partition_integrity")
    if not isinstance(partition, dict) or partition.get("gate") != "GO":
        raise ValueError("trust anchor partition integrity gate is not GO")
    if any(partition.get(field) != [] for field in (
        "overlap_post_ids", "missing_post_ids", "extra_post_ids"
    )):
        raise ValueError("trust anchor partition integrity is non-empty")

    recovered_signature = _uniform_row_signature(recovered_rows, "recovered")
    residual_signature = _uniform_row_signature(residual_rows, "residual")
    if recovered_signature != residual_signature:
        raise ValueError("completed rows no longer match the anchored runtime signature")
    source_manifest_signature = _manifest_signature(source_manifest)
    residual_manifest_signature = _manifest_signature(residual_manifest)
    source_plan_signature = _plan_signature(source_plan, "source")
    residual_plan_signature = _plan_signature(residual_plan, "residual")
    stable_projection = {
        "row": recovered_signature,
        "manifest": source_manifest_signature,
        "plan": source_plan_signature,
    }
    if source_manifest_signature != residual_manifest_signature:
        raise ValueError("completed manifests no longer share the anchored stable projection")
    if source_plan_signature != residual_plan_signature:
        raise ValueError("runtime plans no longer share the anchored stable projection")
    if anchor.get("stable_projection") != stable_projection:
        raise ValueError("trust anchor stable projection mismatch")
    fingerprint = _canonical_hash(stable_projection)
    if anchor.get("stable_runtime_fingerprint_sha256") != fingerprint:
        raise ValueError("trust anchor stable runtime fingerprint mismatch")

    run_ids = anchor.get("run_ids") if isinstance(anchor.get("run_ids"), dict) else {}
    source_run_id = str(source_manifest.get("run_id") or "")
    residual_run_id = str(residual_manifest.get("run_id") or "")
    if run_ids != {"source": source_run_id, "residual": residual_run_id}:
        raise ValueError("trust anchor run id mismatch")
    if recovery_summary.get("run_id") != source_run_id:
        raise ValueError("trust anchor recovery/source run id mismatch")
    if _uniform_row_value(recovered_rows, "recovered", "run_id") != source_run_id:
        raise ValueError("trust anchor recovered row run id mismatch")
    if _uniform_row_value(residual_rows, "residual", "run_id") != residual_run_id:
        raise ValueError("trust anchor residual row run id mismatch")

    code_tree = runtime_code_tree_projection(repo_root)
    if anchor.get("runtime_code_tree_sha256") != code_tree["tree_sha256"]:
        raise ValueError("runtime code tree changed after trust anchor creation")
    if anchor.get("runtime_code_tree") != code_tree:
        raise ValueError("runtime code tree projection mismatch")

    fixed = anchor.get("fixed_artifacts") if isinstance(anchor.get("fixed_artifacts"), dict) else {}
    required_fixed = {"source_panel", "adjudicated_baseline", "golden_manifest"}
    if set(fixed) != required_fixed:
        raise ValueError("trust anchor fixed artifact set mismatch")
    fixed_paths = {name: Path(str(fixed[name].get("path") or "")).resolve() for name in required_fixed}
    fixed_hashes = {name: str(fixed[name].get("sha256") or "") for name in required_fixed}
    if fixed_paths["source_panel"] != source_jsonl.resolve():
        raise ValueError("trust anchor source panel path mismatch")
    if _sha256(source_jsonl) != fixed_hashes["source_panel"]:
        raise ValueError("trust anchor source panel hash mismatch")
    expected_panel_binding = {
        "row_count": len(source_ids),
        "post_id_order_sha256": _canonical_hash(source_ids),
        "post_id_set_sha256": _canonical_hash(sorted(source_ids)),
    }
    for field, expected in expected_panel_binding.items():
        if fixed["source_panel"].get(field) != expected:
            raise ValueError(f"trust anchor source panel {field} mismatch")
    for name in ("adjudicated_baseline", "golden_manifest"):
        if not fixed_paths[name].is_file() or _sha256(fixed_paths[name]) != fixed_hashes[name]:
            raise ValueError(f"trust anchor fixed artifact changed: {name}")
    if not allow_untrusted_test_roots:
        production_paths = {
            "source_panel": PRODUCTION_PANEL_PATH,
            "adjudicated_baseline": PRODUCTION_BASELINE_PATH,
            "golden_manifest": PRODUCTION_GOLDEN_PATH,
        }
        production_hashes = {
            "source_panel": PRODUCTION_PANEL_SHA256,
            "adjudicated_baseline": PRODUCTION_BASELINE_SHA256,
            "golden_manifest": PRODUCTION_GOLDEN_SHA256,
        }
        if fixed_paths != production_paths or fixed_hashes != production_hashes:
            raise ValueError("trust anchor does not match fixed production roots")
    input_hashes = anchor.get("input_hashes") if isinstance(anchor.get("input_hashes"), dict) else {}
    if input_hashes.get("source_panel_sha256") != fixed_hashes["source_panel"]:
        raise ValueError("trust anchor input/source panel hash mismatch")
    if input_hashes.get("adjudicated_baseline_sha256") != fixed_hashes["adjudicated_baseline"]:
        raise ValueError("trust anchor input/baseline hash mismatch")
    if input_hashes.get("golden_manifest_sha256") != fixed_hashes["golden_manifest"]:
        raise ValueError("trust anchor input/golden hash mismatch")

    observation = (
        anchor.get("mutable_runtime_observation")
        if isinstance(anchor.get("mutable_runtime_observation"), dict)
        else {}
    )
    source_observed = observation.get("source_manifest_counts")
    residual_observed = observation.get("residual_manifest_counts")
    if not isinstance(source_observed, dict) or not isinstance(residual_observed, dict):
        raise ValueError("trust anchor pre-completion observations missing")
    if source_observed != {
        "input_post_count": expected_source_count,
        "completed_count": expected_recovered_count,
        "flushed_count": 68 if not allow_untrusted_test_roots else source_observed.get("flushed_count"),
        "pending_count": 7 if not allow_untrusted_test_roots else source_observed.get("pending_count"),
        "failed_count": 0,
        "large_run_complete": False,
    }:
        raise ValueError("trust anchor source interruption observation mismatch")
    observed_completed = residual_observed.get("completed_count")
    observed_flushed = residual_observed.get("flushed_count")
    observed_pending = residual_observed.get("pending_count")
    if any(isinstance(value, bool) or not isinstance(value, int) for value in (
        observed_completed,
        observed_flushed,
        observed_pending,
    )):
        raise ValueError("trust anchor residual pre-completion counts invalid")
    if not (
        residual_observed.get("input_post_count") == expected_residual_count
        and 0 < observed_completed < expected_residual_count
        and 0 < observed_flushed <= observed_completed
        and observed_pending == observed_completed - observed_flushed
        and residual_observed.get("failed_count") == 0
        and residual_observed.get("large_run_complete") is False
    ):
        raise ValueError("trust anchor was not created from an incomplete residual run")

    try:
        generated_at = datetime.fromisoformat(str(anchor.get("generated_at") or ""))
    except ValueError as exc:
        raise ValueError("trust anchor generated_at invalid") from exc
    anchor_mtime = datetime.fromtimestamp(anchor_path.stat().st_mtime)
    final_manifest_mtime = datetime.fromtimestamp(residual_manifest_path.stat().st_mtime)
    if generated_at > anchor_mtime + timedelta(seconds=5):
        raise ValueError("trust anchor generated_at is after its file timestamp")
    if not (generated_at < final_manifest_mtime and anchor_mtime < final_manifest_mtime):
        raise ValueError("trust anchor was not frozen before residual completion")
    final_counts = {
        "input_post_count": expected_residual_count,
        "completed_count": expected_residual_count,
        "flushed_count": expected_residual_count,
        "pending_count": 0,
        "failed_count": 0,
    }
    if any(residual_manifest.get(field) != expected for field, expected in final_counts.items()):
        raise ValueError("residual final manifest counts invalid during trust validation")
    if residual_manifest.get("large_run_complete") is not True:
        raise ValueError("residual final manifest is not complete during trust validation")

    return {
        "gate": "GO",
        "path": str(anchor_path.resolve()),
        "sha256": actual_anchor_sha256,
        "compiled_expected_sha256": expected_anchor_sha256,
        "anchor_version": TRUST_ANCHOR_VERSION,
        "topology_profile": topology["profile"],
        "stable_runtime_fingerprint_sha256": fingerprint,
        "release_fingerprint_sha256": anchor.get("release_fingerprint_sha256"),
        "runtime_code_tree_sha256": code_tree["tree_sha256"],
        "generated_at": anchor.get("generated_at"),
        "anchor_file_mtime": anchor_mtime.isoformat(),
        "residual_final_manifest_mtime": final_manifest_mtime.isoformat(),
    }


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _canonical_hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _uniform_row_signature(rows: list[dict[str, Any]], label: str) -> dict[str, Any]:
    signatures: dict[str, dict[str, Any]] = {}
    for row in rows:
        run_meta = row.get("run_meta")
        if not isinstance(run_meta, dict):
            raise ValueError(f"{label} row {_post_id(row)} is missing run_meta")
        missing = [field for field in ROW_STABLE_SIGNATURE_FIELDS if field not in run_meta]
        if missing:
            raise ValueError(f"{label} row {_post_id(row)} run_meta missing stable fields: {missing}")
        signature = {field: run_meta[field] for field in ROW_STABLE_SIGNATURE_FIELDS}
        signatures[_canonical(signature)] = signature
    if len(signatures) != 1:
        raise ValueError(f"{label} run_meta is not homogeneous: {list(signatures.values())}")
    return next(iter(signatures.values()))


def _uniform_row_value(rows: list[dict[str, Any]], label: str, field: str) -> Any:
    values: dict[str, Any] = {}
    for row in rows:
        run_meta = row.get("run_meta")
        if not isinstance(run_meta, dict) or field not in run_meta:
            raise ValueError(f"{label} row {_post_id(row)} run_meta missing {field}")
        value = run_meta[field]
        values[_canonical(value)] = value
    if len(values) != 1:
        raise ValueError(f"{label} run_meta {field} is not homogeneous: {list(values.values())}")
    return next(iter(values.values()))


def _manifest_signature(manifest: dict[str, Any]) -> dict[str, Any]:
    missing = [field for field in MANIFEST_STABLE_SIGNATURE_FIELDS if field not in manifest]
    if missing:
        raise ValueError(f"manifest missing stable fields: {missing}")
    return {field: manifest[field] for field in MANIFEST_STABLE_SIGNATURE_FIELDS}


def _validate_row_manifest_binding(
    row_signature: dict[str, Any],
    manifest: dict[str, Any],
    label: str,
) -> None:
    mismatches: dict[str, dict[str, Any]] = {}
    for row_field, manifest_field in ROW_TO_MANIFEST_FIELDS.items():
        row_value = row_signature.get(row_field)
        manifest_value = manifest.get(manifest_field)
        if row_value != manifest_value:
            mismatches[row_field] = {
                "row": row_value,
                "manifest_field": manifest_field,
                "manifest": manifest_value,
            }
    if mismatches:
        raise ValueError(f"{label} row/manifest stable field mismatch: {mismatches}")


def _planned_run(plan: dict[str, Any]) -> dict[str, Any]:
    runs = plan.get("planned_runs")
    if not isinstance(runs, list) or not runs or not isinstance(runs[0], dict):
        raise ValueError("runtime plan has no planned_runs[0]")
    return runs[0]


def _normalized_plan_command(plan: dict[str, Any]) -> list[str]:
    argv = list(_planned_run(plan).get("command_argv") or [])
    if len(argv) < 4 or "expert_main.py" not in argv:
        raise ValueError("runtime plan command is not expert_main.py")
    expert_index = argv.index("expert_main.py")
    if expert_index + 1 >= len(argv):
        raise ValueError("runtime plan command is missing input")
    argv[expert_index + 1] = "<INPUT>"
    if "--output" not in argv:
        raise ValueError("runtime plan command is missing --output")
    output_index = argv.index("--output")
    if output_index + 1 >= len(argv):
        raise ValueError("runtime plan command is missing output path")
    argv[output_index + 1] = "<OUTPUT>"
    return argv


def _required_env_signature(plan: dict[str, Any], label: str) -> dict[str, str]:
    runtime_contract = plan.get("runtime_contract")
    if not isinstance(runtime_contract, dict):
        raise ValueError(f"{label} runtime plan has no runtime_contract")
    candidates = {
        "plan.required_env": plan.get("required_env"),
        "runtime_contract.required_env": runtime_contract.get("required_env"),
        "planned_runs[0].required_env": _planned_run(plan).get("required_env"),
    }
    signatures: dict[str, dict[str, str]] = {}
    for source, payload in candidates.items():
        if not isinstance(payload, dict):
            raise ValueError(f"{label} {source} is missing")
        missing = [field for field in PLAN_REQUIRED_ENV_FIELDS if field not in payload]
        if missing:
            raise ValueError(f"{label} {source} missing fields: {missing}")
        signature = {field: str(payload[field]) for field in PLAN_REQUIRED_ENV_FIELDS}
        signatures[_canonical(signature)] = signature
    if len(signatures) != 1:
        raise ValueError(f"{label} required_env sources disagree: {list(signatures.values())}")
    return next(iter(signatures.values()))


def _runtime_contract_signature(plan: dict[str, Any], label: str) -> dict[str, Any]:
    runtime_contract = plan.get("runtime_contract")
    if not isinstance(runtime_contract, dict):
        raise ValueError(f"{label} runtime plan has no runtime_contract")
    missing = [field for field in PLAN_RUNTIME_CONTRACT_FIELDS if field not in runtime_contract]
    if missing:
        raise ValueError(f"{label} runtime_contract missing fields: {missing}")
    return {field: runtime_contract[field] for field in PLAN_RUNTIME_CONTRACT_FIELDS}


def _plan_signature(plan: dict[str, Any], label: str) -> dict[str, Any]:
    return {
        "normalized_command_argv": _normalized_plan_command(plan),
        "required_env": _required_env_signature(plan, label),
        "runtime_contract": _runtime_contract_signature(plan, label),
    }


def _arg_value(argv: list[str], option: str) -> str | None:
    if option not in argv:
        return None
    index = argv.index(option)
    if index + 1 >= len(argv):
        raise ValueError(f"runtime command option {option} has no value")
    return str(argv[index + 1])


def _env_bool(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _validate_plan_manifest_binding(
    plan_signature: dict[str, Any],
    manifest: dict[str, Any],
    label: str,
) -> None:
    argv = plan_signature["normalized_command_argv"]
    runtime_contract = plan_signature["runtime_contract"]
    required_env = plan_signature["required_env"]
    expected_pairs = {
        "llm_model": (_arg_value(argv, "--llm-model"), manifest.get("llm_model")),
        "llm_endpoint": (_arg_value(argv, "--llm-endpoint"), manifest.get("llm_endpoint")),
        "requested_parallel": (
            int(_arg_value(argv, "--parallel") or 0),
            int(manifest.get("requested_parallel") or 0),
        ),
        "vlm_enabled": (_arg_value(argv, "--vlm") == "on", manifest.get("vlm_enabled")),
        "ocr_enabled": (_arg_value(argv, "--ocr") == "on", manifest.get("ocr_enabled")),
        "require_vlm_ocr_for_images": (
            "--require-vlm-ocr-for-images" in argv,
            manifest.get("vlm_ocr_semantic_review_required_for_images"),
        ),
        "dashboard_enabled": (
            bool(runtime_contract["dashboard_required"]) and "--no-dashboard" not in argv,
            manifest.get("dashboard_enabled"),
        ),
        "mcp_health_include_search": (
            _env_bool(required_env["MCP_HEALTH_INCLUDE_SEARCH"]),
            manifest.get("mcp_health_include_search"),
        ),
        "mcp_health_light_mode": (
            _env_bool(required_env["MCP_HEALTH_LIGHT_MODE"]),
            manifest.get("mcp_health_light_mode"),
        ),
        "mcp_health_required_ok_count": (
            int(required_env["MCP_HEALTH_REQUIRED_OK"]),
            int(manifest.get("mcp_health_required_ok_count") or 0),
        ),
        "mcp_health_probe_batch_size": (
            int(required_env["MCP_HEALTH_PROBE_BATCH_SIZE"]),
            int(manifest.get("mcp_health_probe_batch_size") or 0),
        ),
    }
    mismatches = {
        field: {"plan": expected, "manifest": actual}
        for field, (expected, actual) in expected_pairs.items()
        if expected != actual
    }
    command_contract_pairs = {
        "requested_parallel": int(_arg_value(argv, "--parallel") or 0),
        "slang_db": _arg_value(argv, "--slang-db"),
        "vlm": _arg_value(argv, "--vlm"),
        "ocr": _arg_value(argv, "--ocr"),
        "reuse_shards_only": "--reuse-shards-only" in argv,
        "require_vlm_ocr_for_images": "--require-vlm-ocr-for-images" in argv,
    }
    for field, command_value in command_contract_pairs.items():
        if command_value != runtime_contract[field]:
            mismatches[f"runtime_contract.{field}"] = {
                "command": command_value,
                "runtime_contract": runtime_contract[field],
            }
    if runtime_contract["no_dashboard_forbidden"] is not True or "--no-dashboard" in argv:
        mismatches["runtime_contract.no_dashboard_forbidden"] = {
            "command_has_no_dashboard": "--no-dashboard" in argv,
            "runtime_contract": runtime_contract["no_dashboard_forbidden"],
        }
    if manifest.get("dashboard_standalone_forwarding") is not True:
        mismatches["dashboard_standalone_forwarding"] = {
            "plan": True,
            "manifest": manifest.get("dashboard_standalone_forwarding"),
        }
    if runtime_contract["reuse_shards_only"] is not True or manifest.get(
        "mcp_healthy_endpoint_filter_reason"
    ) != "reuse_shards_only":
        mismatches["reuse_shards_only"] = {
            "runtime_contract": runtime_contract["reuse_shards_only"],
            "manifest_reason": manifest.get("mcp_healthy_endpoint_filter_reason"),
        }
    if mismatches:
        raise ValueError(f"{label} plan/manifest contract mismatch: {mismatches}")


def _checkpoint_completed_index(
    rows: list[dict[str, Any]],
    label: str,
    *,
    expected_positions: dict[str, int],
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    completed: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    unsupported: list[dict[str, Any]] = []
    for row in rows:
        if row.get("status") == "completed":
            completed.append(row)
        elif row.get("status") == "failed":
            failed.append(row)
        else:
            unsupported.append(row)
    if failed:
        raise ValueError(f"{label} contains failed rows: {len(failed)}")
    if unsupported:
        raise ValueError(f"{label} contains unsupported status rows: {len(unsupported)}")
    index: dict[str, dict[str, Any]] = {}
    seen_global_indexes: set[int] = set()
    for row in completed:
        post_id = _checkpoint_post_id(row)
        if post_id in index:
            raise ValueError(f"{label} duplicate completed post_id: {post_id}")
        global_idx = row.get("global_idx")
        if isinstance(global_idx, bool) or not isinstance(global_idx, int):
            raise ValueError(f"{label} post_id {post_id} global_idx is not an integer: {global_idx!r}")
        if global_idx in seen_global_indexes:
            raise ValueError(f"{label} duplicate global_idx: {global_idx}")
        seen_global_indexes.add(global_idx)
        expected_global_idx = expected_positions.get(post_id)
        if expected_global_idx is None:
            raise ValueError(f"{label} checkpoint post_id absent from expected positions: {post_id}")
        if global_idx != expected_global_idx:
            raise ValueError(
                f"{label} global_idx mismatch for post_id {post_id}: "
                f"{global_idx} != {expected_global_idx}"
            )
        index[post_id] = row
    if set(index) != set(expected_positions):
        missing = sorted(set(expected_positions) - set(index))
        extra = sorted(set(index) - set(expected_positions))
        raise ValueError(f"{label} checkpoint coverage mismatch missing={missing} extra={extra}")
    return index, completed


def build_merge(
    *,
    source_rows: list[dict[str, Any]],
    recovered_rows: list[dict[str, Any]],
    recovered_checkpoint_rows: list[dict[str, Any]],
    recovery_summary: dict[str, Any],
    source_manifest: dict[str, Any],
    residual_rows: list[dict[str, Any]],
    residual_input_rows: list[dict[str, Any]],
    residual_checkpoint_rows: list[dict[str, Any]],
    residual_pending_rows: list[dict[str, Any]],
    residual_manifest: dict[str, Any],
    source_plan: dict[str, Any],
    residual_plan: dict[str, Any],
    expected_source_count: int = 375,
    expected_recovered_count: int = 75,
    expected_residual_count: int = 300,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    source_by_id = _index(source_rows, "source input")
    recovered_by_id = _index(recovered_rows, "recovered result")
    residual_by_id = _index(residual_rows, "residual result")
    residual_input_by_id = _index(residual_input_rows, "residual input")

    if len(source_rows) != expected_source_count:
        raise ValueError(f"source count mismatch: {len(source_rows)} != {expected_source_count}")
    if len(recovered_rows) != expected_recovered_count:
        raise ValueError(f"recovered count mismatch: {len(recovered_rows)} != {expected_recovered_count}")
    if len(residual_rows) != expected_residual_count:
        raise ValueError(f"residual count mismatch: {len(residual_rows)} != {expected_residual_count}")
    if len(residual_input_rows) != expected_residual_count:
        raise ValueError(
            f"residual input count mismatch: {len(residual_input_rows)} != {expected_residual_count}"
        )

    recovered_ids = set(recovered_by_id)
    residual_ids = set(residual_by_id)
    source_ids = set(source_by_id)
    overlap = sorted(recovered_ids & residual_ids)
    missing = sorted(source_ids - recovered_ids - residual_ids)
    extra = sorted((recovered_ids | residual_ids) - source_ids)
    if overlap or missing or extra:
        raise ValueError(f"partition mismatch overlap={overlap} missing={missing} extra={extra}")

    source_positions = {_post_id(row): index for index, row in enumerate(source_rows, 1)}
    recovered_positions = {post_id: source_positions[post_id] for post_id in recovered_ids}
    expected_residual_ids = [
        _post_id(row) for row in source_rows if _post_id(row) not in recovered_ids
    ]
    actual_residual_input_ids = [_post_id(row) for row in residual_input_rows]
    actual_residual_result_ids = [_post_id(row) for row in residual_rows]
    if actual_residual_input_ids != expected_residual_ids:
        raise ValueError("residual input is not the original-order source complement")
    if actual_residual_result_ids != actual_residual_input_ids:
        raise ValueError("residual result order does not exactly match residual input order")
    residual_positions = {
        post_id: index for index, post_id in enumerate(expected_residual_ids, 1)
    }
    if set(expected_residual_ids) != residual_ids:
        raise ValueError("residual result post_ids do not match original-order residual partition")
    if set(residual_input_by_id) != residual_ids:
        raise ValueError("residual input/result post_id set mismatch")

    recovered_checkpoint_by_id, recovered_completed = _checkpoint_completed_index(
        recovered_checkpoint_rows,
        "recovered source checkpoint",
        expected_positions=recovered_positions,
    )
    residual_checkpoint_by_id, residual_completed = _checkpoint_completed_index(
        residual_checkpoint_rows,
        "residual checkpoint",
        expected_positions=residual_positions,
    )
    residual_checkpoint_source_order = [
        row["result"]
        for row in sorted(residual_completed, key=lambda item: int(item["global_idx"]))
    ]
    if residual_checkpoint_source_order != residual_rows:
        raise ValueError("residual checkpoint does not bind to residual input/result exact order")

    if residual_pending_rows:
        raise ValueError(f"residual pending snapshot is not empty: {len(residual_pending_rows)}")
    if recovery_summary.get("integrity_classification") not in {
        "recoverable_pending_flush_gap",
        "clean_completed_run",
    }:
        raise ValueError("recovery summary is not safe")
    if recovery_summary.get("recovery_safe_to_use_as_completed_subset") is not True:
        raise ValueError("recovery summary does not mark subset safe")
    if int(recovery_summary.get("recovered_rows") or 0) != expected_recovered_count:
        raise ValueError("recovery summary count mismatch")
    if recovery_summary.get("run_id") != source_manifest.get("run_id"):
        raise ValueError("recovery summary/source manifest run_id mismatch")
    if int(recovery_summary.get("checkpoint_completed_rows") or 0) != len(recovered_completed):
        raise ValueError("recovery summary checkpoint completed count mismatch")
    if int(recovery_summary.get("checkpoint_failed_rows") or 0) != 0:
        raise ValueError("recovery summary checkpoint failed count is nonzero")
    recovery_manifest = recovery_summary.get("manifest")
    if not isinstance(recovery_manifest, dict):
        raise ValueError("recovery summary manifest snapshot is missing")
    for field in (
        "input_post_count",
        "completed_count",
        "flushed_count",
        "pending_count",
        "failed_count",
        "next_save_idx",
    ):
        if recovery_manifest.get(field) != source_manifest.get(field):
            raise ValueError(f"recovery summary/source manifest {field} mismatch")

    recovered_checkpoint_payload = {
        post_id: row["result"] for post_id, row in recovered_checkpoint_by_id.items()
    }
    if set(recovered_by_id) != set(recovered_checkpoint_payload):
        raise ValueError("recovered result/checkpoint post_id mismatch")
    if any(recovered_by_id[post_id] != recovered_checkpoint_payload[post_id] for post_id in recovered_by_id):
        raise ValueError("recovered result/checkpoint payload mismatch")
    residual_checkpoint_payload = {
        post_id: row["result"] for post_id, row in residual_checkpoint_by_id.items()
    }
    if set(residual_by_id) != set(residual_checkpoint_payload):
        raise ValueError("residual result/checkpoint post_id mismatch")
    if any(residual_by_id[post_id] != residual_checkpoint_payload[post_id] for post_id in residual_by_id):
        raise ValueError("residual result/checkpoint payload mismatch")

    expected_residual_manifest = {
        "input_post_count": expected_residual_count,
        "completed_count": expected_residual_count,
        "flushed_count": expected_residual_count,
        "pending_count": 0,
        "failed_count": 0,
    }
    for field, expected in expected_residual_manifest.items():
        if int(residual_manifest.get(field) or 0) != expected:
            raise ValueError(f"residual manifest {field} mismatch")
    if residual_manifest.get("large_run_complete") is not True:
        raise ValueError("residual manifest large_run_complete is not true")

    recovered_row_signature = _uniform_row_signature(recovered_rows, "recovered")
    residual_row_signature = _uniform_row_signature(residual_rows, "residual")
    if recovered_row_signature != residual_row_signature:
        raise ValueError(
            f"row runtime signature mismatch: recovered={recovered_row_signature} residual={residual_row_signature}"
        )
    recovered_run_id = _uniform_row_value(recovered_rows, "recovered", "run_id")
    residual_run_id = _uniform_row_value(residual_rows, "residual", "run_id")
    if recovered_run_id != source_manifest.get("run_id"):
        raise ValueError("recovered row/source manifest run_id mismatch")
    if residual_run_id != residual_manifest.get("run_id"):
        raise ValueError("residual row/residual manifest run_id mismatch")
    recovered_raw_config_hash = _uniform_row_value(recovered_rows, "recovered", "config_hash")
    residual_raw_config_hash = _uniform_row_value(residual_rows, "residual", "config_hash")
    if not str(recovered_raw_config_hash or "").strip() or not str(residual_raw_config_hash or "").strip():
        raise ValueError("component raw config_hash is empty")

    source_manifest_signature = _manifest_signature(source_manifest)
    residual_manifest_signature = _manifest_signature(residual_manifest)
    if source_manifest_signature != residual_manifest_signature:
        raise ValueError(
            "manifest runtime signature mismatch: "
            f"source={source_manifest_signature} residual={residual_manifest_signature}"
        )
    _validate_row_manifest_binding(recovered_row_signature, source_manifest, "recovered")
    _validate_row_manifest_binding(residual_row_signature, residual_manifest, "residual")

    source_plan_signature = _plan_signature(source_plan, "source")
    residual_plan_signature = _plan_signature(residual_plan, "residual")
    if source_plan_signature != residual_plan_signature:
        raise ValueError(
            "runtime plan contract mismatch: "
            f"source={source_plan_signature} residual={residual_plan_signature}"
        )
    _validate_plan_manifest_binding(source_plan_signature, source_manifest, "source")
    _validate_plan_manifest_binding(residual_plan_signature, residual_manifest, "residual")

    stable_runtime_signature = {
        "row": recovered_row_signature,
        "manifest": source_manifest_signature,
        "plan": source_plan_signature,
    }
    stable_runtime_fingerprint = _canonical_hash(stable_runtime_signature)

    merged_rows = [
        recovered_by_id.get(_post_id(source)) or residual_by_id[_post_id(source)]
        for source in source_rows
    ]
    merged_checkpoint_rows = [
        {
            "global_idx": index,
            "post_id": row.get("post_id"),
            "status": "completed",
            "result": row,
        }
        for index, row in enumerate(merged_rows, 1)
    ]
    integrity = {
        "report_type": "interrupted_run_original_order_merge_integrity",
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "gate": "GO",
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "counts": {
            "source_rows": len(source_rows),
            "source_unique_post_ids": len(source_ids),
            "recovered_rows": len(recovered_rows),
            "recovered_checkpoint_completed_rows": len(recovered_completed),
            "residual_rows": len(residual_rows),
            "residual_checkpoint_completed_rows": len(residual_completed),
            "residual_pending_rows": len(residual_pending_rows),
            "merged_rows": len(merged_rows),
            "merged_checkpoint_rows": len(merged_checkpoint_rows),
        },
        "post_id_integrity": {
            "overlap_post_ids": overlap,
            "missing_post_ids": missing,
            "extra_post_ids": extra,
            "duplicate_post_ids": [],
            "original_order_preserved": [str(row.get("post_id")) for row in merged_rows]
            == [str(row.get("post_id")) for row in source_rows],
        },
        "runtime_homogeneity": {
            "gate": "GO",
            "stable_runtime_fingerprint_sha256": stable_runtime_fingerprint,
            "stable_row_signature": recovered_row_signature,
            "stable_manifest_signature": source_manifest_signature,
            "stable_plan_signature": source_plan_signature,
            "source_run_id": recovered_run_id,
            "residual_run_id": residual_run_id,
            "component_raw_config_hashes": {
                "source": recovered_raw_config_hash,
                "residual": residual_raw_config_hash,
            },
            "raw_config_hash_cross_run_equality_required": False,
            "raw_config_hash_size_dependent_reason": RAW_CONFIG_HASH_SIZE_DEPENDENT_REASON,
        },
        "recovery": {
            "integrity_classification": recovery_summary.get("integrity_classification"),
            "recovery_safe_to_use_as_completed_subset": recovery_summary.get(
                "recovery_safe_to_use_as_completed_subset"
            ),
        },
        "approval_boundary": {
            "merge_integrity_is_not_semantic_approval": True,
            "component_runtime_homogeneity_required": True,
            "post_run_gates_required": True,
            "production_full_scan_approval": False,
        },
    }
    return merged_rows, merged_checkpoint_rows, integrity


def _write_json_exclusive(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def _write_jsonl_exclusive(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _json_bytes(payload: Any) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _jsonl_bytes(rows: list[dict[str, Any]]) -> bytes:
    return "".join(
        json.dumps(row, ensure_ascii=False) + "\n" for row in rows
    ).encode("utf-8")


def _bytes_sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def finalize_merge_binding_receipt(payload: dict[str, Any]) -> dict[str, Any]:
    receipt = dict(payload)
    receipt["report_type"] = MERGE_BINDING_RECEIPT_REPORT_TYPE
    receipt["schema_version"] = MERGE_BINDING_RECEIPT_SCHEMA_VERSION
    receipt["finalized"] = True
    receipt["finalization"] = {
        "state": "FINALIZED",
        "marker": MERGE_BINDING_RECEIPT_FINALIZATION_MARKER,
        "written_last": True,
        "required_for_downstream": True,
        "self_digest_algorithm": "sha256(canonical_json_without_receipt_payload_sha256)",
    }
    receipt.pop("receipt_payload_sha256", None)
    receipt["receipt_payload_sha256"] = _canonical_hash(receipt)
    return receipt


def validate_finalized_merge_binding_receipt(
    receipt: dict[str, Any],
    *,
    receipt_path: Path | None = None,
    verify_artifact_bytes: bool = False,
) -> dict[str, Any]:
    if receipt.get("report_type") != MERGE_BINDING_RECEIPT_REPORT_TYPE:
        raise ValueError("merge binding receipt report_type mismatch")
    if receipt.get("schema_version") != MERGE_BINDING_RECEIPT_SCHEMA_VERSION:
        raise ValueError("merge binding receipt schema_version mismatch")
    if receipt.get("gate") != "GO" or receipt.get("finalized") is not True:
        raise ValueError("merge binding receipt is not finalized GO")
    finalization = receipt.get("finalization")
    if not isinstance(finalization, dict) or finalization.get("marker") != (
        MERGE_BINDING_RECEIPT_FINALIZATION_MARKER
    ):
        raise ValueError("merge binding receipt finalization marker mismatch")
    supplied_digest = str(receipt.get("receipt_payload_sha256") or "")
    payload_without_digest = dict(receipt)
    payload_without_digest.pop("receipt_payload_sha256", None)
    if supplied_digest != _canonical_hash(payload_without_digest):
        raise ValueError("merge binding receipt self-digest mismatch")
    preflight_paths = receipt.get("preflight_paths")
    if not isinstance(preflight_paths, dict):
        raise ValueError("merge binding receipt preflight paths missing")
    if receipt_path is not None and Path(
        str(preflight_paths.get("binding_receipt") or "")
    ).resolve() != receipt_path.resolve():
        raise ValueError("merge binding receipt self path mismatch")
    if (
        receipt_path is not None
        and receipt_path.exists()
        and receipt_path.stat().st_mode & stat.S_IWRITE
    ):
        raise ValueError("merge binding receipt file is not read-only")
    required_output_fields = {
        "result": (
            "byte_sha256",
            "canonical_sha256",
            "size_bytes",
            "row_count",
            "post_id_order_sha256",
            "post_id_set_sha256",
        ),
        "checkpoint": ("byte_sha256", "canonical_sha256", "size_bytes", "row_count"),
        "pending": ("byte_sha256", "canonical_sha256", "size_bytes", "row_count"),
    }
    output_artifacts = receipt.get("output_artifacts")
    if not isinstance(output_artifacts, dict):
        raise ValueError("merge binding receipt output artifacts missing")
    bindings: list[dict[str, Any]] = []
    for name, required_fields in required_output_fields.items():
        binding = output_artifacts.get(name)
        if not isinstance(binding, dict) or any(
            field not in binding for field in required_fields
        ):
            raise ValueError(f"merge binding receipt {name} binding incomplete")
        bindings.append(binding)
    for name, required_fields in {
        "manifest": ("byte_sha256", "canonical_sha256", "size_bytes"),
        "integrity": ("byte_sha256", "canonical_sha256", "size_bytes"),
        "integrity_markdown": ("byte_sha256", "size_bytes"),
    }.items():
        binding = receipt.get(name)
        if not isinstance(binding, dict) or any(
            field not in binding for field in required_fields
        ):
            raise ValueError(f"merge binding receipt {name} binding incomplete")
        bindings.append(binding)
    trust_anchor = receipt.get("trust_anchor")
    if not isinstance(trust_anchor, dict) or any(
        not str(trust_anchor.get(field) or "").strip()
        for field in (
            "path",
            "sha256",
            "anchor_version",
            "release_fingerprint_sha256",
        )
    ):
        raise ValueError("merge binding receipt trust anchor binding incomplete")
    if verify_artifact_bytes:
        for binding in bindings:
            path = Path(str(binding.get("path") or ""))
            if not path.is_file() or _sha256(path) != binding["byte_sha256"]:
                raise ValueError(f"merge binding receipt artifact byte mismatch: {path}")
            if path.stat().st_size != binding["size_bytes"]:
                raise ValueError(f"merge binding receipt artifact size mismatch: {path}")
            if path.stat().st_mode & stat.S_IWRITE:
                raise ValueError(f"merge binding receipt artifact is not read-only: {path}")
            if "canonical_sha256" in binding:
                parsed = _load_jsonl(path) if path.suffix.lower() == ".jsonl" else _load_json(path)
                if _canonical_hash(parsed) != binding["canonical_sha256"]:
                    raise ValueError(
                        f"merge binding receipt artifact canonical mismatch: {path}"
                    )
        manifest_payload = _load_json(Path(str(receipt["manifest"]["path"])))
        integrity_payload = _load_json(Path(str(receipt["integrity"]["path"])))
        if manifest_payload.get("premerge_trust_anchor") != trust_anchor:
            raise ValueError("merge manifest/receipt trust anchor mismatch")
        if integrity_payload.get("premerge_trust_anchor") != trust_anchor:
            raise ValueError("merge integrity/receipt trust anchor mismatch")
    return {
        "gate": "GO",
        "schema_version": MERGE_BINDING_RECEIPT_SCHEMA_VERSION,
        "receipt_payload_sha256": supplied_digest,
        "trust_anchor_sha256": trust_anchor["sha256"],
    }


def _write_bytes_exclusive(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(payload)
    path.chmod(stat.S_IREAD)


def _integrity_markdown(integrity: dict[str, Any]) -> str:
    lines = [
        "# Loop640 recovered + Loop641 residual original-order 병합 무결성",
        "",
        f"- gate: `{integrity['gate']}`",
        f"- counts: `{integrity['counts']}`",
        f"- post_id_integrity: `{integrity['post_id_integrity']}`",
        f"- runtime_homogeneity: `{integrity['runtime_homogeneity']['gate']}`",
        f"- source/residual run: `{integrity['runtime_homogeneity']['source_run_id']}` / `{integrity['runtime_homogeneity']['residual_run_id']}`",
        "- 이 GO는 병합 무결성과 runtime 동일성만 뜻하며 semantic/full-scan approval이 아니다.",
        "",
    ]
    return "\n".join(lines)


def validate_output_preflight(
    *,
    output_result: Path,
    output_checkpoint: Path,
    output_pending: Path,
    output_manifest: Path,
    output_integrity_json: Path,
    output_integrity_md: Path,
    output_binding_receipt: Path,
    repo_root: Path = REPO_ROOT,
    allow_untrusted_test_roots: bool = False,
) -> dict[str, str]:
    paths = {
        "result": output_result.resolve(),
        "checkpoint": output_checkpoint.resolve(),
        "pending": output_pending.resolve(),
        "manifest": output_manifest.resolve(),
        "integrity_json": output_integrity_json.resolve(),
        "integrity_md": output_integrity_md.resolve(),
        "binding_receipt": output_binding_receipt.resolve(),
    }
    if len(set(paths.values())) != len(paths):
        raise ValueError("merge output paths must be distinct")
    collisions = [str(path) for path in paths.values() if path.exists()]
    if collisions:
        raise FileExistsError(f"merge output preflight collision: {collisions}")

    if allow_untrusted_test_roots:
        allowed_root = repo_root.resolve()
        outside = [
            str(path)
            for path in paths.values()
            if path != allowed_root and allowed_root not in path.parents
        ]
    else:
        merged_root = (PRODUCTION_PANEL_PATH.parents[1] / "merged").resolve()
        docs_root = (REPO_ROOT / "docs/devs").resolve()
        outside = []
        for name in ("result", "checkpoint", "pending"):
            path = paths[name]
            if path != merged_root and merged_root not in path.parents:
                outside.append(str(path))
        for name in ("manifest", "integrity_json", "integrity_md", "binding_receipt"):
            path = paths[name]
            if path != docs_root and docs_root not in path.parents:
                outside.append(str(path))
    if outside:
        raise ValueError(f"merge output path outside confined roots: {outside}")
    return {name: str(path) for name, path in paths.items()}


def validate_residual_manifest_artifact_paths(
    *,
    residual_manifest: dict[str, Any],
    residual_result: Path,
    residual_checkpoint: Path,
    residual_pending: Path,
    repo_root: Path = REPO_ROOT,
) -> None:
    expected = {
        "output_file": residual_result.resolve(),
        "checkpoint_jsonl": residual_checkpoint.resolve(),
        "pending_snapshot": residual_pending.resolve(),
    }
    for field, expected_path in expected.items():
        value = str(residual_manifest.get(field) or "").strip()
        if not value:
            raise ValueError(f"residual manifest {field} is missing")
        actual_path = Path(value)
        if not actual_path.is_absolute():
            actual_path = repo_root / actual_path
        if actual_path.resolve() != expected_path:
            raise ValueError(f"residual manifest {field} path mismatch")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge recovered and residual expert runs in original panel order.")
    parser.add_argument("--source-jsonl", required=True, type=Path)
    parser.add_argument("--recovered-json", required=True, type=Path)
    parser.add_argument("--recovered-checkpoint", required=True, type=Path)
    parser.add_argument("--recovery-summary", required=True, type=Path)
    parser.add_argument("--source-manifest", required=True, type=Path)
    parser.add_argument("--source-plan", required=True, type=Path)
    parser.add_argument("--residual-input", required=True, type=Path)
    parser.add_argument("--residual-json", required=True, type=Path)
    parser.add_argument("--residual-checkpoint", required=True, type=Path)
    parser.add_argument("--residual-pending", required=True, type=Path)
    parser.add_argument("--residual-manifest", required=True, type=Path)
    parser.add_argument("--residual-plan", required=True, type=Path)
    parser.add_argument("--trust-anchor", required=True, type=Path)
    parser.add_argument("--expected-trust-anchor-sha256", required=True)
    parser.add_argument("--expected-source-count", type=int, default=375)
    parser.add_argument("--expected-recovered-count", type=int, default=75)
    parser.add_argument("--expected-residual-count", type=int, default=300)
    parser.add_argument("--output-result", required=True, type=Path)
    parser.add_argument("--output-checkpoint", required=True, type=Path)
    parser.add_argument("--output-pending", required=True, type=Path)
    parser.add_argument("--output-manifest", required=True, type=Path)
    parser.add_argument("--output-integrity-json", required=True, type=Path)
    parser.add_argument("--output-integrity-md", required=True, type=Path)
    parser.add_argument("--output-binding-receipt", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_paths = validate_output_preflight(
        output_result=args.output_result,
        output_checkpoint=args.output_checkpoint,
        output_pending=args.output_pending,
        output_manifest=args.output_manifest,
        output_integrity_json=args.output_integrity_json,
        output_integrity_md=args.output_integrity_md,
        output_binding_receipt=args.output_binding_receipt,
    )
    source_rows = _load_jsonl(args.source_jsonl)
    recovered_rows = _object_rows(_load_json(args.recovered_json), "recovered result")
    source_checkpoint_rows = _load_jsonl(args.recovered_checkpoint)
    recovery_summary = _load_json(args.recovery_summary)
    residual_input_rows = _load_jsonl(args.residual_input)
    residual_rows = _object_rows(_load_json(args.residual_json), "residual result")
    residual_checkpoint_rows = _load_jsonl(args.residual_checkpoint)
    residual_pending_rows = _object_rows(
        _load_json(args.residual_pending), "residual pending"
    )
    source_manifest = _load_json(args.source_manifest)
    residual_manifest = _load_json(args.residual_manifest)
    validate_residual_manifest_artifact_paths(
        residual_manifest=residual_manifest,
        residual_result=args.residual_json,
        residual_checkpoint=args.residual_checkpoint,
        residual_pending=args.residual_pending,
    )
    source_plan = _load_json(args.source_plan)
    residual_plan = _load_json(args.residual_plan)
    trust_anchor = _load_json(args.trust_anchor)
    trust_binding = validate_premerge_trust_anchor(
        anchor=trust_anchor,
        anchor_path=args.trust_anchor,
        source_jsonl=args.source_jsonl,
        recovered_result_path=args.recovered_json,
        source_checkpoint_rows=source_checkpoint_rows,
        source_checkpoint_path=args.recovered_checkpoint,
        recovery_summary_path=args.recovery_summary,
        source_manifest=source_manifest,
        source_manifest_path=args.source_manifest,
        source_plan=source_plan,
        source_plan_path=args.source_plan,
        recovered_rows=recovered_rows,
        recovery_summary=recovery_summary,
        residual_input_rows=residual_input_rows,
        residual_input_path=args.residual_input,
        residual_manifest=residual_manifest,
        residual_manifest_path=args.residual_manifest,
        residual_plan=residual_plan,
        residual_plan_path=args.residual_plan,
        residual_rows=residual_rows,
        expected_source_count=args.expected_source_count,
        expected_recovered_count=args.expected_recovered_count,
        expected_residual_count=args.expected_residual_count,
        expected_trust_anchor_sha256=args.expected_trust_anchor_sha256,
    )
    merged_rows, checkpoint_rows, integrity = build_merge(
        source_rows=source_rows,
        recovered_rows=recovered_rows,
        recovered_checkpoint_rows=source_checkpoint_rows,
        recovery_summary=recovery_summary,
        source_manifest=source_manifest,
        residual_rows=residual_rows,
        residual_input_rows=residual_input_rows,
        residual_checkpoint_rows=residual_checkpoint_rows,
        residual_pending_rows=residual_pending_rows,
        residual_manifest=residual_manifest,
        source_plan=source_plan,
        residual_plan=residual_plan,
        expected_source_count=args.expected_source_count,
        expected_recovered_count=args.expected_recovered_count,
        expected_residual_count=args.expected_residual_count,
    )
    integrity["premerge_trust_anchor"] = trust_binding
    if _sha256(args.trust_anchor) != trust_binding["sha256"]:
        raise ValueError("trust anchor changed before merge output write")

    result_bytes = _json_bytes(merged_rows)
    checkpoint_bytes = _jsonl_bytes(checkpoint_rows)
    pending_bytes = _json_bytes([])
    output_artifact_bindings = {
        "result": {
            "path": output_paths["result"],
            "byte_sha256": _bytes_sha256(result_bytes),
            "canonical_sha256": _canonical_hash(merged_rows),
            "size_bytes": len(result_bytes),
            "row_count": len(merged_rows),
            "post_id_order_sha256": _canonical_hash(
                [_post_id(row) for row in merged_rows]
            ),
            "post_id_set_sha256": _canonical_hash(
                sorted(_post_id(row) for row in merged_rows)
            ),
        },
        "checkpoint": {
            "path": output_paths["checkpoint"],
            "byte_sha256": _bytes_sha256(checkpoint_bytes),
            "canonical_sha256": _canonical_hash(checkpoint_rows),
            "size_bytes": len(checkpoint_bytes),
            "row_count": len(checkpoint_rows),
        },
        "pending": {
            "path": output_paths["pending"],
            "byte_sha256": _bytes_sha256(pending_bytes),
            "canonical_sha256": _canonical_hash([]),
            "size_bytes": len(pending_bytes),
            "row_count": 0,
        },
    }
    residual_artifact_bindings = {
        "input": _row_artifact_projection(args.residual_input, residual_input_rows),
        "result": _row_artifact_projection(args.residual_json, residual_rows),
        "checkpoint": {
            **_immutable_artifact_projection(
                args.residual_checkpoint, residual_checkpoint_rows
            ),
            "row_count": len(residual_checkpoint_rows),
            "completed_post_id_order_sha256": _canonical_hash(
                [
                    _checkpoint_post_id(row)
                    for row in sorted(
                        residual_checkpoint_rows,
                        key=lambda item: int(item.get("global_idx") or 0),
                    )
                ]
            ),
            "completed_post_id_set_sha256": _canonical_hash(
                sorted(_checkpoint_post_id(row) for row in residual_checkpoint_rows)
            ),
        },
        "pending": {
            **_immutable_artifact_projection(args.residual_pending, residual_pending_rows),
            "row_count": len(residual_pending_rows),
        },
        "manifest": _immutable_artifact_projection(
            args.residual_manifest, residual_manifest
        ),
        "anchored_input_order_sha256": _canonical_hash(
            [_post_id(row) for row in residual_input_rows]
        ),
        "anchored_input_set_sha256": _canonical_hash(
            sorted(_post_id(row) for row in residual_input_rows)
        ),
    }

    manifest = {
        "run_id": "loop641_recovered75_plus_residual300_merged375",
        "generated_at": integrity["generated_at"],
        "output_file": str(args.output_result),
        "checkpoint_jsonl": str(args.output_checkpoint),
        "pending_snapshot": str(args.output_pending),
        "input_post_count": len(source_rows),
        "completed_count": len(merged_rows),
        "flushed_count": len(merged_rows),
        "pending_count": 0,
        "failed_count": 0,
        "next_save_idx": len(merged_rows) + 1,
        "partial_flush_gap": False,
        "ordered_flush_blocked": False,
        "large_run_complete": True,
        "result_payload_sha256": _canonical_hash(merged_rows),
        "input_post_id_order_sha256": _canonical_hash(
            [_post_id(row) for row in source_rows]
        ),
        "input_post_id_set_sha256": _canonical_hash(
            sorted(_post_id(row) for row in source_rows)
        ),
        **integrity["runtime_homogeneity"]["stable_manifest_signature"],
        "prompt_version": integrity["runtime_homogeneity"]["stable_row_signature"][
            "prompt_version"
        ],
        "stable_runtime_fingerprint_sha256": integrity["runtime_homogeneity"][
            "stable_runtime_fingerprint_sha256"
        ],
        "premerge_trust_anchor": trust_binding,
        "residual_runtime_artifacts": residual_artifact_bindings,
        "output_artifacts": output_artifact_bindings,
        "component_raw_config_hashes": integrity["runtime_homogeneity"][
            "component_raw_config_hashes"
        ],
        "raw_config_hash_cross_run_equality_required": False,
        "raw_config_hash_size_dependent_reason": RAW_CONFIG_HASH_SIZE_DEPENDENT_REASON,
        "parallel_count": source_manifest.get("parallel_count"),
        "image_post_count": source_manifest.get("image_post_count"),
        "image_posts_present": source_manifest.get("image_posts_present"),
        "image_post_sample_post_ids": source_manifest.get("image_post_sample_post_ids") or [],
        "dashboard_enabled": source_manifest.get("dashboard_enabled"),
        "dashboard_mode": "composite_source_runs",
        "runtime_composition": {
            "source_run_id": source_manifest.get("run_id"),
            "source_completed_rows": len(recovered_rows),
            "residual_run_id": residual_manifest.get("run_id"),
            "residual_completed_rows": len(residual_rows),
            "merge_integrity_gate": integrity["gate"],
        },
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
    }
    manifest_bytes = _json_bytes(manifest)
    integrity["artifacts"] = {
        "source_jsonl": str(args.source_jsonl),
        "source_jsonl_sha256": _sha256(args.source_jsonl),
        "recovered_json": str(args.recovered_json),
        "recovered_json_sha256": _sha256(args.recovered_json),
        "residual_json": str(args.residual_json),
        "residual_json_sha256": _sha256(args.residual_json),
        "residual_input": str(args.residual_input),
        "residual_input_sha256": _sha256(args.residual_input),
        "residual_checkpoint": str(args.residual_checkpoint),
        "residual_checkpoint_sha256": _sha256(args.residual_checkpoint),
        "residual_pending": str(args.residual_pending),
        "residual_pending_sha256": _sha256(args.residual_pending),
        "residual_manifest": str(args.residual_manifest),
        "residual_manifest_sha256": _sha256(args.residual_manifest),
        "output_result": output_paths["result"],
        "output_result_sha256": output_artifact_bindings["result"]["byte_sha256"],
        "output_result_canonical_sha256": output_artifact_bindings["result"][
            "canonical_sha256"
        ],
        "output_checkpoint": output_paths["checkpoint"],
        "output_checkpoint_sha256": output_artifact_bindings["checkpoint"][
            "byte_sha256"
        ],
        "output_checkpoint_canonical_sha256": output_artifact_bindings["checkpoint"][
            "canonical_sha256"
        ],
        "output_pending": output_paths["pending"],
        "output_pending_sha256": output_artifact_bindings["pending"]["byte_sha256"],
        "output_pending_canonical_sha256": output_artifact_bindings["pending"][
            "canonical_sha256"
        ],
        "output_manifest": output_paths["manifest"],
        "output_manifest_sha256": _bytes_sha256(manifest_bytes),
        "output_manifest_canonical_sha256": _canonical_hash(manifest),
        "trust_anchor": str(args.trust_anchor),
        "trust_anchor_sha256": trust_binding["sha256"],
    }
    integrity_bytes = _json_bytes(integrity)
    markdown_bytes = _integrity_markdown(integrity).encode("utf-8")
    binding_receipt = finalize_merge_binding_receipt({
        "generated_at": integrity["generated_at"],
        "gate": "GO",
        "preflight_paths": output_paths,
        "trust_anchor": trust_binding,
        "residual_runtime_artifacts": residual_artifact_bindings,
        "output_artifacts": output_artifact_bindings,
        "manifest": {
            "path": output_paths["manifest"],
            "byte_sha256": _bytes_sha256(manifest_bytes),
            "canonical_sha256": _canonical_hash(manifest),
            "size_bytes": len(manifest_bytes),
        },
        "integrity": {
            "path": output_paths["integrity_json"],
            "byte_sha256": _bytes_sha256(integrity_bytes),
            "canonical_sha256": _canonical_hash(integrity),
            "size_bytes": len(integrity_bytes),
        },
        "integrity_markdown": {
            "path": output_paths["integrity_md"],
            "byte_sha256": _bytes_sha256(markdown_bytes),
            "size_bytes": len(markdown_bytes),
        },
        "approval_boundary": {
            "detached_receipt_is_binding_evidence_not_semantic_approval": True,
            "production_full_scan_approval": False,
        },
    })
    receipt_bytes = _json_bytes(binding_receipt)
    validate_finalized_merge_binding_receipt(
        binding_receipt,
        receipt_path=args.output_binding_receipt,
    )

    # Re-run all collision/confinement checks after serialization and before the
    # first mutation. Partial write failures are intentionally not rolled back.
    validate_output_preflight(
        output_result=args.output_result,
        output_checkpoint=args.output_checkpoint,
        output_pending=args.output_pending,
        output_manifest=args.output_manifest,
        output_integrity_json=args.output_integrity_json,
        output_integrity_md=args.output_integrity_md,
        output_binding_receipt=args.output_binding_receipt,
    )
    if _sha256(args.trust_anchor) != trust_binding["sha256"]:
        raise ValueError("trust anchor changed before merge integrity write")
    _write_bytes_exclusive(args.output_result, result_bytes)
    _write_bytes_exclusive(args.output_checkpoint, checkpoint_bytes)
    _write_bytes_exclusive(args.output_pending, pending_bytes)
    _write_bytes_exclusive(args.output_manifest, manifest_bytes)
    _write_bytes_exclusive(args.output_integrity_json, integrity_bytes)
    _write_bytes_exclusive(args.output_integrity_md, markdown_bytes)
    # Receipt is the commit marker: verify the six staged-final artifacts first,
    # then write the finalized receipt last. Any earlier failure leaves no receipt.
    validate_finalized_merge_binding_receipt(
        binding_receipt,
        receipt_path=args.output_binding_receipt,
        verify_artifact_bytes=True,
    )
    _write_bytes_exclusive(args.output_binding_receipt, receipt_bytes)
    validate_finalized_merge_binding_receipt(
        _load_json(args.output_binding_receipt),
        receipt_path=args.output_binding_receipt,
        verify_artifact_bytes=True,
    )
    print(
        json.dumps(
            {
                "gate": integrity["gate"],
                "counts": integrity["counts"],
                "trust_anchor_sha256": trust_binding["sha256"],
                "binding_receipt_sha256": _bytes_sha256(receipt_bytes),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
