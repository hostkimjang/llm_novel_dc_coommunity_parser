from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any, Dict, Iterable, List


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8", errors="ignore"))


def _artifact_prefix_from_manifest(manifest: Path) -> str:
    name = manifest.name
    prefix = "expert_result_"
    suffix = "_manifest.json"
    if name.startswith(prefix) and name.endswith(suffix):
        return name[len(prefix) : -len(suffix)]
    return ""


def _resolve_cli_path(value: str | None, *, repo: Path) -> Path | None:
    if not value:
        return None
    path = Path(value)
    if path.is_absolute():
        return path
    return repo / path


def _resolve_run_artifacts(
    run_id: str,
    *,
    repo: Path,
    artifact_prefix: str | None = None,
    manifest_path: str | None = None,
    checkpoint_path: str | None = None,
    result_json_path: str | None = None,
    pending_snapshot_path: str | None = None,
    log_glob: str | None = None,
) -> Dict[str, Any]:
    """Resolve launcher-output artifacts even when internal run_id differs."""
    out_dir = repo / "out"
    logs_dir = repo / "logs"

    explicit_overrides: List[str] = []
    explicit_manifest = _resolve_cli_path(manifest_path, repo=repo)
    if artifact_prefix:
        explicit_overrides.append("artifact_prefix")
    resolved_prefix = str(artifact_prefix or run_id)
    direct_manifest = out_dir / f"expert_result_{resolved_prefix}_manifest.json"
    manifest = direct_manifest
    manifest_run_id = run_id
    resolution = "direct_prefix"

    if explicit_manifest is not None:
        manifest = explicit_manifest
        explicit_overrides.append("manifest")
        inferred_prefix = _artifact_prefix_from_manifest(manifest)
        if inferred_prefix and not artifact_prefix:
            resolved_prefix = inferred_prefix
        try:
            payload = _load_json(manifest)
            if isinstance(payload, dict):
                manifest_run_id = str(payload.get("run_id") or run_id)
        except Exception:
            manifest_run_id = run_id
        resolution = "explicit_paths"

    if explicit_manifest is None and not manifest.exists():
        for candidate in sorted(out_dir.glob("expert_result_*_manifest.json")):
            try:
                payload = _load_json(candidate)
            except Exception:
                continue
            if not isinstance(payload, dict):
                continue
            if str(payload.get("run_id") or "").strip() != run_id:
                continue
            resolved_prefix = _artifact_prefix_from_manifest(candidate)
            if not resolved_prefix:
                continue
            manifest = candidate
            manifest_run_id = str(payload.get("run_id") or "")
            resolution = "manifest_run_id_lookup"
            break

    checkpoint = out_dir / f"expert_result_{resolved_prefix}_checkpoint.jsonl"
    explicit_checkpoint = _resolve_cli_path(checkpoint_path, repo=repo)
    if explicit_checkpoint is not None:
        checkpoint = explicit_checkpoint
        explicit_overrides.append("checkpoint")

    result_json = out_dir / f"expert_result_{resolved_prefix}.json"
    explicit_result_json = _resolve_cli_path(result_json_path, repo=repo)
    if explicit_result_json is not None:
        result_json = explicit_result_json
        explicit_overrides.append("result_json")

    pending = out_dir / f"expert_result_{resolved_prefix}_pending_snapshot.json"
    explicit_pending = _resolve_cli_path(pending_snapshot_path, repo=repo)
    if explicit_pending is not None:
        pending = explicit_pending
        explicit_overrides.append("pending_snapshot")

    explicit_log_glob = _resolve_cli_path(log_glob, repo=repo)
    if explicit_log_glob is not None:
        log_files = sorted(explicit_log_glob.parent.glob(explicit_log_glob.name))
        explicit_overrides.append("log_glob")
    else:
        log_files = sorted(logs_dir.glob(f"expert_run_{run_id}_W*.log"))
        if resolved_prefix != run_id:
            extra_logs = sorted(logs_dir.glob(f"expert_run_{resolved_prefix}_W*.log"))
            seen = {path.resolve() for path in log_files}
            log_files.extend(path for path in extra_logs if path.resolve() not in seen)

    if explicit_overrides:
        resolution = "explicit_paths"

    return {
        "requested_run_id": run_id,
        "manifest_run_id": manifest_run_id,
        "artifact_prefix": resolved_prefix,
        "resolution": resolution,
        "explicit_overrides": explicit_overrides,
        "manifest": manifest,
        "checkpoint": checkpoint,
        "result_json": result_json,
        "pending": pending,
        "log_files": log_files,
    }


def _count_result_rows(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {
            "path": str(path),
            "exists": False,
            "shape": "missing",
            "row_count": None,
            "load_error": "missing",
        }
    try:
        payload = _load_json(path)
    except Exception as exc:
        return {
            "path": str(path),
            "exists": True,
            "shape": "unreadable",
            "row_count": None,
            "load_error": f"{type(exc).__name__}: {exc}",
        }
    if isinstance(payload, list):
        return {
            "path": str(path),
            "exists": True,
            "shape": "list",
            "row_count": len(payload),
            "load_error": None,
        }
    if isinstance(payload, dict):
        for key in ("results", "rows", "data", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                return {
                    "path": str(path),
                    "exists": True,
                    "shape": f"dict.{key}",
                    "row_count": len(value),
                    "load_error": None,
                }
        return {
            "path": str(path),
            "exists": True,
            "shape": "dict",
            "row_count": None,
            "load_error": "no_supported_row_list",
        }
    return {
        "path": str(path),
        "exists": True,
        "shape": type(payload).__name__,
        "row_count": None,
        "load_error": "unsupported_json_shape",
    }


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    try:
        return int(value)
    except Exception:
        return None


def _summarize_pending_row(row: Dict[str, Any]) -> Dict[str, Any]:
    result = row.get("result") if isinstance(row.get("result"), dict) else {}
    return {
        "global_idx": row.get("global_idx"),
        "post_id": row.get("post_id") or result.get("post_id"),
        "title": row.get("title") or result.get("title"),
    }


def _build_flush_frontier(
    *,
    manifest_data: Dict[str, Any],
    checkpoint_completed_indexes: List[int],
    pending_global_indexes: List[int],
) -> Dict[str, Any]:
    next_save_idx = _as_int(manifest_data.get("next_save_idx"))
    completed = sorted(set(checkpoint_completed_indexes))
    pending = sorted(set(pending_global_indexes))

    frontier_in_checkpoint = next_save_idx in completed if next_save_idx is not None else None
    frontier_in_pending = next_save_idx in pending if next_save_idx is not None else None
    first_pending_at_or_after = (
        next((idx for idx in pending if idx >= next_save_idx), None)
        if next_save_idx is not None
        else None
    )
    first_completed_at_or_after = (
        next((idx for idx in completed if idx >= next_save_idx), None)
        if next_save_idx is not None
        else None
    )

    if next_save_idx is None:
        status = "unknown"
        reason = "next_save_idx_missing"
    elif frontier_in_checkpoint:
        status = "ready_to_flush_or_flush_lag"
        reason = "frontier_completed_in_checkpoint"
    elif frontier_in_pending:
        status = "pending_completed_not_flushed"
        reason = "frontier_present_in_pending_snapshot"
    else:
        status = "in_flight_or_missing"
        reason = "frontier_missing_from_checkpoint_and_pending"

    return {
        "next_save_idx": next_save_idx,
        "status": status,
        "reason": reason,
        "frontier_in_checkpoint_completed": frontier_in_checkpoint,
        "frontier_in_pending_snapshot": frontier_in_pending,
        "completed_index_min": completed[0] if completed else None,
        "completed_index_max": completed[-1] if completed else None,
        "pending_index_min": pending[0] if pending else None,
        "pending_index_max": pending[-1] if pending else None,
        "first_pending_at_or_after_frontier": first_pending_at_or_after,
        "first_completed_at_or_after_frontier": first_completed_at_or_after,
        "frontier_gap_global_idx": (
            next_save_idx
            if next_save_idx is not None and not frontier_in_checkpoint and not frontier_in_pending
            else None
        ),
    }


def _build_flush_integrity(
    *,
    manifest_data: Dict[str, Any],
    status_counts: Dict[str, int],
    result_audit: Dict[str, Any],
    pending_count_actual: int | None,
    pending_samples: List[Dict[str, Any]],
    checkpoint_completed_indexes: List[int] | None = None,
    pending_global_indexes: List[int] | None = None,
) -> Dict[str, Any]:
    input_count = _as_int(manifest_data.get("input_post_count"))
    completed_count = _as_int(manifest_data.get("completed_count"))
    flushed_count = _as_int(manifest_data.get("flushed_count"))
    pending_count = _as_int(manifest_data.get("pending_count"))
    failed_count = _as_int(manifest_data.get("failed_count"))
    checkpoint_completed = _as_int(status_counts.get("completed")) or 0
    checkpoint_failed = _as_int(status_counts.get("failed")) or 0
    result_rows = _as_int(result_audit.get("row_count"))
    completed_minus_flushed = (
        completed_count - flushed_count
        if completed_count is not None and flushed_count is not None
        else None
    )

    required_counts = {
        "input_post_count": input_count,
        "completed_count": completed_count,
        "flushed_count": flushed_count,
        "pending_count": pending_count,
        "failed_count": failed_count,
        "result_rows": result_rows,
        "pending_count_actual": pending_count_actual,
    }
    blockers: List[str] = [f"{name}_missing" for name, value in required_counts.items() if value is None]

    if input_count is not None and completed_count is not None and completed_count < input_count:
        blockers.append("completed_count_lt_input_post_count")
    if pending_count is not None and pending_count > 0:
        blockers.append("pending_count_gt_zero")
    if failed_count is not None and failed_count > 0:
        blockers.append("failed_count_gt_zero")
    if completed_count is not None and flushed_count is not None and flushed_count < completed_count:
        blockers.append("flushed_count_lt_completed_count")
    if completed_count is not None and result_rows is not None and result_rows < completed_count:
        blockers.append("result_rows_lt_completed_count")
    if manifest_data.get("large_run_complete") is not True:
        blockers.append("large_run_completion_not_proven")
    if manifest_data.get("ordered_flush_blocked") is True:
        blockers.append("ordered_flush_blocked")
    if manifest_data.get("partial_flush_gap") is True:
        blockers.append("partial_flush_gap")

    consistency = {
        "result_rows_eq_flushed_count": (
            result_rows is not None and flushed_count is not None and result_rows == flushed_count
        ),
        "checkpoint_completed_eq_manifest_completed": (
            completed_count is not None and checkpoint_completed == completed_count
        ),
        "checkpoint_failed_eq_manifest_failed": (
            failed_count is not None and checkpoint_failed == failed_count
        ),
        "pending_snapshot_rows_eq_manifest_pending": (
            pending_count_actual is not None and pending_count is not None and pending_count_actual == pending_count
        ),
        "pending_snapshot_rows_eq_completed_minus_flushed": (
            pending_count_actual is not None
            and completed_minus_flushed is not None
            and pending_count_actual == completed_minus_flushed
        ),
    }
    frontier = _build_flush_frontier(
        manifest_data=manifest_data,
        checkpoint_completed_indexes=checkpoint_completed_indexes or [],
        pending_global_indexes=pending_global_indexes or [],
    )
    if result_rows is not None and flushed_count is not None and result_rows != flushed_count:
        blockers.append("result_rows_ne_flushed_count")
    if completed_count is not None and checkpoint_completed != completed_count:
        blockers.append("checkpoint_completed_ne_manifest_completed")
    if failed_count is not None and checkpoint_failed != failed_count:
        blockers.append("checkpoint_failed_ne_manifest_failed")
    if pending_count_actual is not None and pending_count is not None and pending_count_actual != pending_count:
        blockers.append("pending_snapshot_rows_ne_manifest_pending")
    if (
        pending_count_actual is not None
        and completed_minus_flushed is not None
        and pending_count_actual != completed_minus_flushed
    ):
        blockers.append("pending_snapshot_rows_ne_completed_minus_flushed")

    artifact_mismatch = any(
        not value
        for key, value in consistency.items()
        if key
        in {
            "result_rows_eq_flushed_count",
            "checkpoint_completed_eq_manifest_completed",
            "checkpoint_failed_eq_manifest_failed",
            "pending_snapshot_rows_eq_manifest_pending",
            "pending_snapshot_rows_eq_completed_minus_flushed",
        }
    )
    clean_completion = (
        not blockers
        and input_count is not None
        and completed_count == input_count
        and flushed_count == completed_count
        and result_rows == flushed_count
        and pending_count == 0
        and pending_count_actual == 0
        and failed_count == 0
        and manifest_data.get("large_run_complete") is True
        and manifest_data.get("ordered_flush_blocked") is not True
        and manifest_data.get("partial_flush_gap") is not True
    )

    if clean_completion:
        gate = "GO"
        classification = "clean_completed_source"
    elif artifact_mismatch:
        gate = "NO-GO"
        classification = "artifact_count_mismatch"
    elif failed_count is not None and failed_count > 0:
        gate = "NO-GO"
        classification = "failed_rows_present"
    elif (
        (pending_count is not None and pending_count > 0)
        or (flushed_count is not None and completed_count is not None and flushed_count < completed_count)
        or manifest_data.get("ordered_flush_blocked") is True
        or manifest_data.get("partial_flush_gap") is True
    ):
        gate = "IN_PROGRESS"
        classification = "ordered_flush_gap_in_progress"
    elif input_count is not None and completed_count is not None and completed_count < input_count:
        gate = "IN_PROGRESS"
        classification = "incomplete_run_in_progress"
    else:
        gate = "IN_PROGRESS"
        classification = "incomplete_or_unclassified"

    return {
        "run_integrity_gate": gate,
        "classification": classification,
        "completion_ready": clean_completion,
        "approval_ready": clean_completion,
        "blockers": blockers,
        "counts": {
            "manifest_input_post_count": input_count,
            "manifest_completed_count": completed_count,
            "manifest_flushed_count": flushed_count,
            "manifest_pending_count": pending_count,
            "manifest_failed_count": failed_count,
            "checkpoint_completed_count": checkpoint_completed,
            "checkpoint_failed_count": checkpoint_failed,
            "result_rows": result_rows,
            "pending_snapshot_rows": pending_count_actual,
            "completed_minus_flushed": completed_minus_flushed,
        },
        "consistency": consistency,
        "frontier": frontier,
        "pending_blocker_samples": pending_samples,
    }


def _iter_checkpoint(path: Path) -> Iterable[Dict[str, Any]]:
    with path.open(encoding="utf-8", errors="ignore") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if isinstance(row, dict):
                yield row


def _identity_from_row(row: Dict[str, Any]) -> Dict[str, Any]:
    result = row.get("result") or {}
    analysis_result = result.get("analysis_result") or {}
    identity = analysis_result.get("identity") or {}
    return identity if isinstance(identity, dict) else {}


def _result_from_row(row: Dict[str, Any]) -> Dict[str, Any]:
    result = row.get("result") or {}
    return result if isinstance(result, dict) else {}


def _extract_int(pattern: str, text: str) -> int | None:
    match = re.search(pattern, text)
    if not match:
        return None
    try:
        return int(match.group(1))
    except Exception:
        return None


def _percent(part: int, whole: int) -> float:
    if whole <= 0:
        return 0.0
    return round((part / whole) * 100.0, 2)


def _audit_slang(
    rows: List[Dict[str, Any]],
    *,
    repo: Path,
) -> Dict[str, Any]:
    import sys

    sys.path.insert(0, str(repo / "src"))
    from llm_batch.agentic_pipeline import AgenticPipeline  # noqa: WPS433
    from llm_batch.slang_db import _is_exact_title_alias, _looks_sentence_like_term  # noqa: WPS433

    pipe = object.__new__(AgenticPipeline)
    slang_all: List[Dict[str, Any]] = []
    old_store: List[Dict[str, Any]] = []
    new_store: List[Dict[str, Any]] = []
    blocked: List[Dict[str, Any]] = []

    for row in rows:
        identity = _identity_from_row(row)
        slang = identity.get("slang_insight")
        if not isinstance(slang, dict):
            continue
        novel_identity = identity.get("novel_identity")
        if not isinstance(novel_identity, dict):
            novel_identity = {}
        result = _result_from_row(row)
        contract = pipe._infer_slang_alias_contract(
            official_title=novel_identity.get("official_title"),
            vf_slang=slang,
            entity_mentions=identity.get("entity_mentions") or [],
            discussion_type=identity.get("discussion_type"),
            topicality=identity.get("topicality"),
            subtype=identity.get("subtype"),
            work_resolution=identity.get("work_resolution"),
        )
        item = {
            "post_id": row.get("post_id"),
            "post_title": result.get("title"),
            "detected_term": slang.get("detected_term"),
            "decoded_term": slang.get("decoded_term"),
            "old_store_in_slang_db": slang.get("store_in_slang_db"),
            "old_store_reason": slang.get("store_reason"),
            "old_alias_scope": slang.get("alias_scope"),
            "new_store_in_slang_db": contract.get("store_in_slang_db"),
            "new_store_reason": contract.get("store_reason"),
            "new_alias_scope": contract.get("alias_scope"),
            "new_canonical_work_alias": contract.get("canonical_work_alias"),
            "official_title": novel_identity.get("official_title"),
            "discussion_type": identity.get("discussion_type"),
            "topicality": identity.get("topicality"),
            "work_resolution": identity.get("work_resolution"),
        }
        slang_all.append(item)
        if slang.get("store_in_slang_db") is True:
            old_store.append(item)
        if contract.get("store_in_slang_db") is True:
            new_store.append(item)
        if slang.get("store_in_slang_db") is True and contract.get("store_in_slang_db") is not True:
            blocked.append(item)

    slang_db_path = repo / "slang_db" / "slang_db.json"
    db_bad: List[Dict[str, Any]] = []
    db_term_count = 0
    db_title_count = 0
    if slang_db_path.exists():
        data = _load_json(slang_db_path)
        titles = data.get("titles") if isinstance(data, dict) else {}
        if isinstance(titles, dict):
            db_title_count = len(titles)
            for title, entry in titles.items():
                if not isinstance(entry, dict):
                    continue
                for slang_row in entry.get("slang") or []:
                    if not isinstance(slang_row, dict):
                        continue
                    db_term_count += 1
                    term = str(slang_row.get("term") or "")
                    if _looks_sentence_like_term(term) or _is_exact_title_alias(term, str(title)):
                        db_bad.append(
                            {
                                "title": title,
                                "term": term,
                                "sources": slang_row.get("sources"),
                                "count": slang_row.get("count"),
                            }
                        )

    return {
        "slang_insight_count": len(slang_all),
        "old_store_true_count": len(old_store),
        "new_store_true_after_patch_count": len(new_store),
        "old_store_true_blocked_by_patch_count": len(blocked),
        "blocked_reason_counts": dict(Counter(x["new_store_reason"] for x in blocked).most_common()),
        "blocked_samples": blocked[:80],
        "kept_samples": new_store[:80],
        "slang_db": {
            "title_count": db_title_count,
            "slang_term_count": db_term_count,
            "sentence_or_exact_bad_remaining": len(db_bad),
            "bad_remaining_samples": db_bad[:80],
        },
    }


def _audit_logs(log_files: List[Path]) -> Dict[str, Any]:
    counts: Counter[str] = Counter()
    worker_counts: Dict[str, Counter[str]] = {}
    headless_engines: Counter[str] = Counter()
    processing_samples: List[str] = []
    starts = 0
    completes = 0

    for path in log_files:
        worker_match = re.search(r"_W(\d+)\.log$", path.name)
        worker_key = f"W{worker_match.group(1)}" if worker_match else path.name
        wc = worker_counts.setdefault(worker_key, Counter())
        try:
            f = path.open(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        with f:
            for lineno, line in enumerate(f, 1):
                if "Agentic Pipeline 시작" in line:
                    starts += 1
                    wc["post_start"] += 1
                if "✅ Post " in line and "완료" in line:
                    completes += 1
                    wc["post_complete"] += 1
                if "processing error" in line or "처리 오류:" in line or "Traceback" in line:
                    counts["fatal_or_trace_line"] += 1
                    wc["fatal_or_trace_line"] += 1
                    if len(processing_samples) < 30:
                        processing_samples.append(f"{path.name}:{lineno}:{line[:300]}")
                if "Connection refused" in line or "WinError 10061" in line:
                    counts["llm_connection_refused"] += 1
                    wc["llm_connection_refused"] += 1
                if "LLM snippet 분석 실패" in line and "NoneType" in line:
                    counts["snippet_none_fallback"] += 1
                    wc["snippet_none_fallback"] += 1
                if "search results [upstream무결과]" in line:
                    counts["search_upstream_zero"] += 1
                    wc["search_upstream_zero"] += 1
                if "search results [bridge필터후0]" in line:
                    counts["search_bridge_after_filter_zero"] += 1
                    wc["search_bridge_after_filter_zero"] += 1
                if "검색 오류: timed out" in line:
                    counts["search_timeout"] += 1
                    wc["search_timeout"] += 1
                if "검색 품질 저하 감지" in line:
                    counts["search_degraded_detected"] += 1
                    wc["search_degraded_detected"] += 1
                if "headless_" in line:
                    counts["headless_lines"] += 1
                    wc["headless_lines"] += 1
                    for match in re.finditer(r"\[(headless_[^\]]+)\]", line):
                        headless_engines[match.group(1)] += 1
                if "headless(" in line:
                    counts["headless_meta_lines"] += 1
                    wc["headless_meta_lines"] += 1
                if "title_anchor_exact_probe" in line:
                    counts["title_anchor_exact_probe_lines"] += 1
                    wc["title_anchor_exact_probe_lines"] += 1

    return {
        "worker_log_count": len(log_files),
        "post_start_count_in_worker_logs": starts,
        "post_complete_count_in_worker_logs": completes,
        "counts": dict(counts),
        "worker_counts_top": {
            key: dict(value.most_common())
            for key, value in sorted(
                worker_counts.items(),
                key=lambda kv: (
                    -kv[1].get("search_degraded_detected", 0),
                    -kv[1].get("search_upstream_zero", 0),
                    kv[0],
                ),
            )[:20]
        },
        "headless_engine_counts": dict(headless_engines.most_common()),
        "processing_error_samples": processing_samples,
    }


def build_audit(
    run_id: str,
    *,
    repo: Path,
    artifact_prefix: str | None = None,
    manifest_path: str | None = None,
    checkpoint_path: str | None = None,
    result_json_path: str | None = None,
    pending_snapshot_path: str | None = None,
    log_glob: str | None = None,
) -> Dict[str, Any]:
    artifacts = _resolve_run_artifacts(
        run_id,
        repo=repo,
        artifact_prefix=artifact_prefix,
        manifest_path=manifest_path,
        checkpoint_path=checkpoint_path,
        result_json_path=result_json_path,
        pending_snapshot_path=pending_snapshot_path,
        log_glob=log_glob,
    )
    checkpoint = artifacts["checkpoint"]
    result_json = artifacts["result_json"]
    manifest = artifacts["manifest"]
    pending = artifacts["pending"]
    log_files = artifacts["log_files"]

    rows = list(_iter_checkpoint(checkpoint))
    status_counts = Counter(row.get("status") for row in rows)
    checkpoint_completed_indexes = [
        idx
        for idx in (_as_int(row.get("global_idx")) for row in rows if row.get("status") == "completed")
        if idx is not None
    ]
    discussion_counts: Counter[str] = Counter()
    topicality_counts: Counter[str] = Counter()
    work_resolution_counts: Counter[str] = Counter()
    identity_state_counts: Counter[str] = Counter()
    confidence_counts: Counter[str] = Counter()
    flag_counts: Counter[str] = Counter()
    reason_errors: List[Dict[str, Any]] = []
    executed_queries: List[int] = []
    degraded_queries: List[int] = []

    for row in rows:
        result = _result_from_row(row)
        identity = _identity_from_row(row)
        reason = str(identity.get("reason") or "")
        if any(
            marker in reason
            for marker in (
                "처리 오류",
                "Traceback",
                "cannot access local variable",
                "object has no attribute",
                "not supported between instances",
            )
        ):
            reason_errors.append(
                {
                    "post_id": row.get("post_id"),
                    "title": result.get("title"),
                    "reason": reason[:600],
                }
            )
        discussion_counts[str(identity.get("discussion_type") or "")] += 1
        topicality_counts[str(identity.get("topicality") or "")] += 1
        work_resolution_counts[str(identity.get("work_resolution") or "")] += 1
        identity_state_counts[str(identity.get("identity_state") or "")] += 1
        novel_identity = identity.get("novel_identity")
        if not isinstance(novel_identity, dict):
            novel_identity = {}
        confidence_counts[str(novel_identity.get("confidence") or "")] += 1
        for flag in identity.get("consistency_flags") or []:
            flag_counts[str(flag)] += 1
        q_count = _extract_int(r"executed_queries:\s*(\d+)", reason)
        if q_count is not None:
            executed_queries.append(q_count)
        d_count = _extract_int(r"degraded_queries:\s*(\d+)", reason)
        if d_count is not None:
            degraded_queries.append(d_count)

    pending_count_actual: int | None = None
    pending_samples: List[Dict[str, Any]] = []
    pending_global_indexes: List[int] = []
    if pending.exists():
        payload = _load_json(pending)
        pending_items: List[Any] = []
        if isinstance(payload, list):
            pending_items = payload
        elif isinstance(payload, dict):
            for key in ("pending", "items", "posts", "data"):
                if isinstance(payload.get(key), list):
                    pending_items = payload[key]
                    break
        pending_count_actual = len(pending_items)
        pending_rows = [row for row in pending_items if isinstance(row, dict)]
        pending_global_indexes = [
            idx for idx in (_as_int(row.get("global_idx")) for row in pending_rows) if idx is not None
        ]
        pending_samples = [_summarize_pending_row(row) for row in pending_rows[:10]]

    manifest_data = _load_json(manifest) if manifest.exists() else {}
    result_audit = _count_result_rows(result_json)
    flush_integrity = _build_flush_integrity(
        manifest_data=manifest_data if isinstance(manifest_data, dict) else {},
        status_counts=dict(status_counts),
        result_audit=result_audit,
        pending_count_actual=pending_count_actual,
        pending_samples=pending_samples,
        checkpoint_completed_indexes=checkpoint_completed_indexes,
        pending_global_indexes=pending_global_indexes,
    )
    log_audit = _audit_logs(log_files)
    slang_audit = _audit_slang(rows, repo=repo)

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "run_id": run_id,
        "artifact_resolution": {
            "resolution": artifacts["resolution"],
            "artifact_prefix": artifacts["artifact_prefix"],
            "explicit_overrides": artifacts["explicit_overrides"],
            "manifest_run_id": artifacts["manifest_run_id"],
            "manifest": str(manifest),
            "checkpoint": str(checkpoint),
            "result_json": str(result_json),
            "pending_snapshot": str(pending),
            "worker_log_count": len(log_files),
        },
        "manifest": manifest_data,
        "result_json": result_audit,
        "result_rows": result_audit["row_count"],
        "checkpoint_rows": len(rows),
        "pending_count_actual": pending_count_actual,
        "flush_integrity": flush_integrity,
        "status_counts": dict(status_counts),
        "identity_state_counts": dict(identity_state_counts.most_common(30)),
        "discussion_type_counts_top": dict(discussion_counts.most_common(40)),
        "topicality_counts": dict(topicality_counts.most_common(20)),
        "work_resolution_counts": dict(work_resolution_counts.most_common(20)),
        "novel_confidence_counts": dict(confidence_counts.most_common(20)),
        "consistency_flag_counts_top": dict(flag_counts.most_common(50)),
        "reason_error_count": len(reason_errors),
        "reason_error_samples": reason_errors[:30],
        "query_stats": {
            "parsed_count": len(executed_queries),
            "avg_executed_queries": round(mean(executed_queries), 2) if executed_queries else None,
            "p95_executed_queries": (
                sorted(executed_queries)[int(len(executed_queries) * 0.95)]
                if executed_queries
                else None
            ),
            "max_executed_queries": max(executed_queries) if executed_queries else None,
            "avg_degraded_queries": round(mean(degraded_queries), 2) if degraded_queries else None,
            "max_degraded_queries": max(degraded_queries) if degraded_queries else None,
        },
        "slang": slang_audit,
        "logs": log_audit,
        "rates": {
            "reason_error_rate_pct": _percent(len(reason_errors), len(rows)),
            "resolved_title_rate_pct": _percent(identity_state_counts.get("resolved_title", 0), len(rows)),
            "unresolved_title_rate_pct": _percent(identity_state_counts.get("unresolved_title", 0), len(rows)),
            "headless_line_per_completed_pct": _percent(
                int(log_audit["counts"].get("headless_lines", 0)),
                max(1, len(rows)),
            ),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit expert run health: logs, search, processing errors, slang candidates.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--artifact-prefix", help="Output artifact prefix when it differs from run id.")
    parser.add_argument("--manifest", help="Explicit manifest path for sampling or custom output locations.")
    parser.add_argument("--checkpoint", help="Explicit checkpoint JSONL path for sampling or custom output locations.")
    parser.add_argument("--result-json", help="Explicit final result JSON path for sampling or custom output locations.")
    parser.add_argument("--pending-snapshot", help="Explicit pending snapshot path for sampling or custom output locations.")
    parser.add_argument("--log-glob", help="Explicit worker log glob, e.g. logs/expert_run_<id>_W*.log")
    parser.add_argument("--output", help="Output JSON path. Defaults to out/run_audit_<run-id>.json")
    args = parser.parse_args()

    repo = _repo_root()
    audit = build_audit(
        args.run_id,
        repo=repo,
        artifact_prefix=args.artifact_prefix,
        manifest_path=args.manifest,
        checkpoint_path=args.checkpoint,
        result_json_path=args.result_json,
        pending_snapshot_path=args.pending_snapshot,
        log_glob=args.log_glob,
    )
    output = Path(args.output) if args.output else repo / "out" / f"run_audit_{args.run_id}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"WROTE {output}")
    print(f"result_rows={audit['result_rows']} result_shape={audit['result_json']['shape']}")
    print(
        "flush_integrity="
        f"{audit['flush_integrity']['run_integrity_gate']}/"
        f"{audit['flush_integrity']['classification']}"
    )
    print(f"checkpoint_rows={audit['checkpoint_rows']} status_counts={audit['status_counts']}")
    print(f"reason_errors={audit['reason_error_count']}")
    print(
        "slang old/new/blocked="
        f"{audit['slang']['old_store_true_count']}/"
        f"{audit['slang']['new_store_true_after_patch_count']}/"
        f"{audit['slang']['old_store_true_blocked_by_patch_count']}"
    )
    print(f"slang_db_bad_remaining={audit['slang']['slang_db']['sentence_or_exact_bad_remaining']}")
    print(f"log_counts={audit['logs']['counts']}")
    print(f"headless={audit['logs']['headless_engine_counts']}")


if __name__ == "__main__":
    main()
