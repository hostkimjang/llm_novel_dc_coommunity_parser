from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

_REPO_ROOT_FOR_IMPORTS = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT_FOR_IMPORTS) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT_FOR_IMPORTS))

from tools.audit_publication_contract_convergence import audit_rows as _audit_publication_contract_rows
from tools.audit_publication_contract_convergence import load_rows as _load_publication_contract_rows


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _optional_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    return text in {"true", "1", "yes", "ready", "go", "pass"}


def result_path_for_manifest(manifest_path: Path) -> Path:
    stem = manifest_path.stem
    if stem.endswith("_manifest"):
        stem = stem[: -len("_manifest")]
    return manifest_path.with_name(stem + ".json")


def count_result_rows(path: Path) -> int | None:
    if not path.exists():
        return None
    try:
        payload = load_json(path)
    except Exception:
        return None
    if isinstance(payload, list):
        return len(payload)
    if isinstance(payload, dict):
        for key in ("results", "rows", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                return len(value)
    return None


def publication_contract_convergence(path: Path, *, evaluate: bool) -> dict[str, Any]:
    if not evaluate:
        return {
            "publication_contract_convergence_gate": "NOT_EVALUATED",
            "publication_contract_ready": False,
            "publication_contract_violation_row_count": None,
            "publication_contract_violation_counts": {},
        }
    if not path.exists():
        return {
            "publication_contract_convergence_gate": "MISSING",
            "publication_contract_ready": False,
            "publication_contract_violation_row_count": None,
            "publication_contract_violation_counts": {},
        }
    try:
        report = _audit_publication_contract_rows(_load_publication_contract_rows(path))
    except Exception as exc:
        return {
            "publication_contract_convergence_gate": "NO-GO",
            "publication_contract_ready": False,
            "publication_contract_violation_row_count": None,
            "publication_contract_violation_counts": {},
            "publication_contract_error": str(exc)[:500],
        }
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    gate = str(report.get("gate") or "").strip() or "NO-GO"
    return {
        "publication_contract_convergence_gate": gate,
        "publication_contract_ready": gate == "GO",
        "publication_contract_violation_row_count": summary.get("violation_row_count"),
        "publication_contract_violation_counts": summary.get("violation_counts") or {},
    }


def summarize_manifest(manifest_path: Path, *, root: Path, random_target: int) -> dict[str, Any] | None:
    try:
        manifest = load_json(manifest_path)
    except Exception:
        return None
    if not isinstance(manifest, dict):
        return None

    result_path = result_path_for_manifest(manifest_path)
    result_rows = count_result_rows(result_path)
    input_count = _optional_int(manifest.get("input_post_count"))
    completed_count = _optional_int(manifest.get("completed_count"))
    flushed_count = _optional_int(manifest.get("flushed_count"))
    pending_count = _optional_int(manifest.get("pending_count"))
    failed_count = _optional_int(manifest.get("failed_count"))
    large_run_complete = _boolish(manifest.get("large_run_complete"))
    vlm_ready = (
        (_boolish(manifest.get("vlm_enabled")) and _boolish(manifest.get("ocr_enabled")))
        or _boolish(manifest.get("vlm_ocr_semantic_review_ready"))
    )
    search_health_included = _boolish(manifest.get("mcp_health_include_search"))
    search_health_light_mode = _boolish(manifest.get("mcp_health_light_mode"))
    search_health_failure_count = _optional_int(manifest.get("mcp_health_failure_count"))
    search_health_ready = bool(
        search_health_included
        and not search_health_light_mode
        and (search_health_failure_count or 0) == 0
    )

    clean_by_counts = bool(
        input_count is not None
        and completed_count is not None
        and completed_count >= input_count
        and (pending_count or 0) == 0
        and (failed_count or 0) == 0
        and (flushed_count is None or flushed_count >= completed_count)
    )
    available_rows = result_rows
    if available_rows is None:
        available_rows = flushed_count if flushed_count is not None else completed_count
    random_feasible = bool(available_rows is not None and available_rows >= random_target)
    candidate_before_publication_contract = bool(
        clean_by_counts
        and vlm_ready
        and search_health_ready
        and result_path.exists()
        and random_feasible
    )
    publication_contract = publication_contract_convergence(
        result_path,
        evaluate=candidate_before_publication_contract,
    )
    approval_candidate = bool(
        candidate_before_publication_contract
        and publication_contract["publication_contract_ready"]
    )

    partial_signals: list[str] = []
    if input_count is None:
        partial_signals.append("input_post_count_missing")
    if completed_count is None:
        partial_signals.append("completed_count_missing")
    if input_count is not None and completed_count is not None and completed_count < input_count:
        partial_signals.append("completed_count_lt_input_post_count")
    if (pending_count or 0) > 0:
        partial_signals.append("pending_count_gt_zero")
    if (failed_count or 0) > 0:
        partial_signals.append("failed_count_gt_zero")
    if flushed_count is not None and completed_count is not None and flushed_count < completed_count:
        partial_signals.append("flushed_count_lt_completed_count")
    if result_rows is None:
        partial_signals.append("result_rows_unknown_or_missing")
    if not search_health_included:
        partial_signals.append("search_health_not_included")
    if search_health_light_mode:
        partial_signals.append("search_health_light_mode")
    if (search_health_failure_count or 0) > 0:
        partial_signals.append("search_health_failure_count_gt_zero")

    return {
        "manifest_path": str(manifest_path.relative_to(root)),
        "result_path": str(result_path.relative_to(root)),
        "result_exists": result_path.exists(),
        "run_id": manifest.get("run_id"),
        "input_post_count": input_count,
        "completed_count": completed_count,
        "flushed_count": flushed_count,
        "pending_count": pending_count,
        "failed_count": failed_count,
        "result_rows": result_rows,
        "available_rows_for_random": available_rows,
        "large_run_complete": large_run_complete,
        "clean_by_counts": clean_by_counts,
        "vlm_ocr_ready": vlm_ready,
        "search_health_included": search_health_included,
        "search_health_light_mode": search_health_light_mode,
        "search_health_failure_count": search_health_failure_count,
        "search_health_ready": search_health_ready,
        **publication_contract,
        "random_target": random_target,
        "random_feasible": random_feasible,
        "approval_source_candidate": approval_candidate,
        "partial_signals": partial_signals,
        "requested_parallel": manifest.get("requested_parallel"),
        "effective_parallel": manifest.get("effective_parallel"),
    }


def _sort_key(item: dict[str, Any]) -> tuple[int, int, int]:
    return (
        int(item.get("available_rows_for_random") or 0),
        int(item.get("completed_count") or 0),
        int(item.get("input_post_count") or 0),
    )


def build_audit(manifest_root: Path, *, random_target: int = 1000, max_candidates: int = 20) -> dict[str, Any]:
    root = Path.cwd().resolve()
    manifest_root = manifest_root.resolve()
    manifest_paths = sorted(manifest_root.rglob("*_manifest.json"))
    candidates: list[dict[str, Any]] = []
    for path in manifest_paths:
        item = summarize_manifest(path, root=root, random_target=random_target)
        if item is not None:
            candidates.append(item)

    approval_candidates = [item for item in candidates if item["approval_source_candidate"]]
    clean_shortfall = [
        item
        for item in candidates
        if item["clean_by_counts"]
        and item["vlm_ocr_ready"]
        and item["search_health_ready"]
        and not item["random_feasible"]
    ]
    clean_search_health_blocked = [
        item
        for item in candidates
        if item["clean_by_counts"]
        and item["vlm_ocr_ready"]
        and item["random_feasible"]
        and not item["search_health_ready"]
    ]
    clean_search_health_not_ready = [
        item
        for item in candidates
        if item["clean_by_counts"]
        and item["vlm_ocr_ready"]
        and not item["search_health_ready"]
    ]
    clean_publication_contract_not_ready = [
        item
        for item in candidates
        if item["clean_by_counts"]
        and item["vlm_ocr_ready"]
        and item["search_health_ready"]
        and item["random_feasible"]
        and item["result_exists"]
        and not item["publication_contract_ready"]
    ]
    partial_population = [
        item
        for item in candidates
        if not item["clean_by_counts"]
        and item["vlm_ocr_ready"]
        and int(item.get("available_rows_for_random") or 0) >= random_target
    ]
    clean_any = [item for item in candidates if item["clean_by_counts"] and item["vlm_ocr_ready"]]

    approval_candidates.sort(key=_sort_key, reverse=True)
    clean_shortfall.sort(key=_sort_key, reverse=True)
    clean_search_health_blocked.sort(key=_sort_key, reverse=True)
    clean_search_health_not_ready.sort(key=_sort_key, reverse=True)
    clean_publication_contract_not_ready.sort(key=_sort_key, reverse=True)
    partial_population.sort(key=_sort_key, reverse=True)
    clean_any.sort(key=_sort_key, reverse=True)

    gate = "REVIEW" if approval_candidates else "REVIEW-LOCKED"
    blockers: list[str] = []
    if not approval_candidates:
        blockers.append("no_completed_vlm_ocr_source_with_random_target_rows")
    if partial_population:
        blockers.append("largest_populations_are_partial_not_approval_sources")
    if clean_shortfall:
        blockers.append("clean_sources_exist_but_random_target_shortfall")
    if clean_search_health_blocked:
        blockers.append("clean_sources_exist_but_search_health_not_ready")
    if clean_publication_contract_not_ready:
        blockers.append("clean_sources_exist_but_publication_contract_not_ready")

    return {
        "report_type": "completed_source_candidate_audit",
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "manifest_root": str(manifest_root.relative_to(root)),
        "random_target": random_target,
        "summary": {
            "manifest_count": len(manifest_paths),
            "parsed_manifest_count": len(candidates),
            "approval_source_candidate_count": len(approval_candidates),
            "clean_vlm_ocr_source_count": len(clean_any),
            "clean_vlm_ocr_random_shortfall_count": len(clean_shortfall),
            "clean_vlm_ocr_search_health_not_ready_count": len(clean_search_health_not_ready),
            "clean_vlm_ocr_search_health_blocked_count": len(clean_search_health_blocked),
            "clean_vlm_ocr_publication_contract_not_ready_count": len(clean_publication_contract_not_ready),
            "partial_vlm_ocr_population_ge_random_target_count": len(partial_population),
            "largest_clean_vlm_ocr_available_rows": (
                clean_any[0].get("available_rows_for_random") if clean_any else None
            ),
            "largest_partial_vlm_ocr_available_rows": (
                partial_population[0].get("available_rows_for_random") if partial_population else None
            ),
        },
        "gate": {
            "overall": gate,
            "semantic_quality": "REVIEW-LOCKED",
            "full_scan_approval": False,
            "blockers": blockers,
            "required_next_actions": (
                ["run_preflight_on_completed_source_candidate"]
                if approval_candidates
                else [
                    "obtain_completed_vlm_ocr_source",
                    "rerun_large_scale_preflight_on_completed_source",
                    "build_random_control_1000_plus_after_completed_source",
                    "build_p0_p1_high_risk_expansion_after_completed_source",
                ]
            ),
        },
        "approval_source_candidates": approval_candidates[:max_candidates],
        "clean_vlm_ocr_random_shortfall_candidates": clean_shortfall[:max_candidates],
        "clean_vlm_ocr_search_health_not_ready_candidates": clean_search_health_not_ready[:max_candidates],
        "clean_vlm_ocr_search_health_blocked_candidates": clean_search_health_blocked[:max_candidates],
        "clean_vlm_ocr_publication_contract_not_ready_candidates": clean_publication_contract_not_ready[:max_candidates],
        "partial_vlm_ocr_population_candidates": partial_population[:max_candidates],
    }


def write_markdown(report: dict[str, Any], path: Path) -> None:
    summary = report["summary"]
    gate = report["gate"]
    lines = [
        "# Completed Source 후보 감사",
        "",
        f"- generated_at: `{report['generated_at']}`",
        f"- manifest_root: `{report['manifest_root']}`",
        f"- random_target: `{report['random_target']}`",
        f"- gate: `{gate['overall']}`",
        f"- semantic_quality: `{gate['semantic_quality']}`",
        f"- full_scan_approval: `{str(gate['full_scan_approval']).lower()}`",
        "",
        "## 요약",
        "",
        f"- manifest_count: `{summary['manifest_count']}`",
        f"- parsed_manifest_count: `{summary['parsed_manifest_count']}`",
        f"- approval_source_candidate_count: `{summary['approval_source_candidate_count']}`",
        f"- clean_vlm_ocr_source_count: `{summary['clean_vlm_ocr_source_count']}`",
        f"- clean_vlm_ocr_random_shortfall_count: `{summary['clean_vlm_ocr_random_shortfall_count']}`",
        f"- clean_vlm_ocr_search_health_not_ready_count: `{summary['clean_vlm_ocr_search_health_not_ready_count']}`",
        f"- clean_vlm_ocr_search_health_blocked_count: `{summary['clean_vlm_ocr_search_health_blocked_count']}`",
        (
            "- clean_vlm_ocr_publication_contract_not_ready_count: "
            f"`{summary['clean_vlm_ocr_publication_contract_not_ready_count']}`"
        ),
        (
            "- partial_vlm_ocr_population_ge_random_target_count: "
            f"`{summary['partial_vlm_ocr_population_ge_random_target_count']}`"
        ),
        f"- largest_clean_vlm_ocr_available_rows: `{summary['largest_clean_vlm_ocr_available_rows']}`",
        f"- largest_partial_vlm_ocr_available_rows: `{summary['largest_partial_vlm_ocr_available_rows']}`",
        "",
        "## Blockers",
        "",
    ]
    if gate["blockers"]:
        lines.extend(f"- `{item}`" for item in gate["blockers"])
    else:
        lines.append("- 없음. 단, 이 감사는 후보 탐색이며 semantic approval이 아니다.")
    lines.extend(["", "## Approval Source Candidates", ""])
    if report["approval_source_candidates"]:
        for item in report["approval_source_candidates"]:
            lines.append(
                f"- `{item['manifest_path']}`: available `{item['available_rows_for_random']}`, "
                f"input/completed/pending/failed `{item['input_post_count']}/{item['completed_count']}/"
                f"{item['pending_count']}/{item['failed_count']}`, "
                f"search_health_ready `{item['search_health_ready']}`, "
                f"publication_contract `{item['publication_contract_convergence_gate']}`"
            )
    else:
        lines.append("- 없음")
    lines.extend(["", "## Clean VLM/OCR Sources Blocked By Search Health", ""])
    for item in report["clean_vlm_ocr_search_health_blocked_candidates"][:10]:
        lines.append(
            f"- `{item['manifest_path']}`: available `{item['available_rows_for_random']}`, "
            f"search_health_included `{item['search_health_included']}`, "
            f"light_mode `{item['search_health_light_mode']}`, "
            f"failure_count `{item['search_health_failure_count']}`"
        )
    if not report["clean_vlm_ocr_search_health_blocked_candidates"]:
        lines.append("- 없음")
    lines.extend(["", "## Clean VLM/OCR Sources Missing Search Health Evidence", ""])
    for item in report["clean_vlm_ocr_search_health_not_ready_candidates"][:10]:
        lines.append(
            f"- `{item['manifest_path']}`: available `{item['available_rows_for_random']}`, "
            f"search_health_included `{item['search_health_included']}`, "
            f"light_mode `{item['search_health_light_mode']}`, "
            f"failure_count `{item['search_health_failure_count']}`"
        )
    if not report["clean_vlm_ocr_search_health_not_ready_candidates"]:
        lines.append("- 없음")
    lines.extend(["", "## Clean VLM/OCR Sources Blocked By Publication Contract", ""])
    for item in report["clean_vlm_ocr_publication_contract_not_ready_candidates"][:10]:
        lines.append(
            f"- `{item['manifest_path']}`: available `{item['available_rows_for_random']}`, "
            f"publication_contract `{item['publication_contract_convergence_gate']}`, "
            f"violations `{item['publication_contract_violation_row_count']}`"
        )
    if not report["clean_vlm_ocr_publication_contract_not_ready_candidates"]:
        lines.append("- 없음")
    lines.extend(["", "## Clean VLM/OCR Sources With Random Shortfall", ""])
    for item in report["clean_vlm_ocr_random_shortfall_candidates"][:10]:
        lines.append(
            f"- `{item['manifest_path']}`: available `{item['available_rows_for_random']}`, "
            f"shortfall `{max(0, int(report['random_target']) - int(item.get('available_rows_for_random') or 0))}`"
        )
    if not report["clean_vlm_ocr_random_shortfall_candidates"]:
        lines.append("- 없음")
    lines.extend(["", "## Partial VLM/OCR Populations", ""])
    for item in report["partial_vlm_ocr_population_candidates"][:10]:
        lines.append(
            f"- `{item['manifest_path']}`: input/completed/flushed/pending/failed "
            f"`{item['input_post_count']}/{item['completed_count']}/{item['flushed_count']}/"
            f"{item['pending_count']}/{item['failed_count']}`, available `{item['available_rows_for_random']}`, "
            f"partial_signals `{', '.join(item.get('partial_signals') or [])}`"
        )
    if not report["partial_vlm_ocr_population_candidates"]:
        lines.append("- 없음")
    lines.extend(["", "## 다음 조치", ""])
    lines.extend(f"- `{item}`" for item in gate["required_next_actions"])
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Find completed VLM/OCR-on source candidates for approval preflight.")
    parser.add_argument("--manifest-root", type=Path, default=Path("out"))
    parser.add_argument("--random-target", type=int, default=1000)
    parser.add_argument("--max-candidates", type=int, default=20)
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-md", required=True, type=Path)
    parser.add_argument("--fail-on-locked", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_audit(
        args.manifest_root,
        random_target=args.random_target,
        max_candidates=args.max_candidates,
    )
    write_json(args.output_json, report)
    write_markdown(report, args.output_md)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.fail_on_locked and report["gate"]["overall"] == "REVIEW-LOCKED":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
