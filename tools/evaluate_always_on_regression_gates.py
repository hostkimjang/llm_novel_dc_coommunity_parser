from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _safe_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _raw_regression_post_ids(collateral: dict[str, Any]) -> set[int] | None:
    rows = collateral.get("rows")
    if not isinstance(rows, list):
        return None
    post_ids: set[int] = set()
    saw_regression_row = False
    for row in rows:
        if not isinstance(row, dict) or not row.get("is_regression"):
            continue
        saw_regression_row = True
        post_id = row.get("post_id")
        if isinstance(post_id, int):
            post_ids.add(post_id)
    return post_ids if saw_regression_row else None


def _review_post_ids(collateral_review: dict[str, Any]) -> set[int] | None:
    rows = collateral_review.get("rows")
    if not isinstance(rows, list):
        return None
    post_ids = {row.get("post_id") for row in rows if isinstance(row, dict)}
    return {post_id for post_id in post_ids if isinstance(post_id, int)}


def _exclusion_post_ids(collateral_review: dict[str, Any]) -> set[int] | None:
    rows = collateral_review.get("rows")
    if not isinstance(rows, list):
        return None
    post_ids: set[int] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        if "exclude_from_regression_count_after_gate_wiring" not in (row.get("action") or []):
            continue
        post_id = row.get("post_id")
        if isinstance(post_id, int):
            post_ids.add(post_id)
    return post_ids


def golden_gate(golden: dict[str, Any], expected_rows: int) -> dict[str, Any]:
    row_count = _safe_int(golden.get("row_count"))
    passed_count = _safe_int(golden.get("passed_count"))
    failed_count = _safe_int(golden.get("failed_count"))
    semantic_gate = str(golden.get("canary_semantic_gate") or "").strip()
    runtime = golden.get("runtime") if isinstance(golden.get("runtime"), dict) else {}
    runtime_completed = _safe_int(runtime.get("completed_count"))
    runtime_complete = (
        runtime_completed is not None
        and runtime_completed >= expected_rows
        and (_safe_int(runtime.get("pending_count")) or 0) == 0
        and (_safe_int(runtime.get("failed_count")) or 0) == 0
    )
    passed = (
        row_count == expected_rows
        and passed_count == expected_rows
        and (failed_count or 0) == 0
        and semantic_gate in {"PASS", "GO"}
        and runtime_complete
    )
    blockers: list[str] = []
    if row_count != expected_rows:
        blockers.append("golden_row_count_mismatch")
    if passed_count != expected_rows or (failed_count or 0) != 0:
        blockers.append("golden_expected_answer_failures")
    if semantic_gate not in {"PASS", "GO"}:
        blockers.append("golden_semantic_gate_not_pass")
    if not runtime_complete:
        blockers.append("golden_runtime_not_complete")
    return {
        "gate": "GO" if passed else "NO-GO",
        "expected_rows": expected_rows,
        "row_count": row_count,
        "passed_count": passed_count,
        "failed_count": failed_count,
        "canary_semantic_gate": semantic_gate,
        "runtime_complete": runtime_complete,
        "blockers": blockers,
    }


def _collateral_review_adjustment(
    *,
    collateral_review: dict[str, Any] | None,
    raw_regression_count: int | None,
    raw_regression_post_ids: set[int] | None = None,
) -> dict[str, Any]:
    if not collateral_review:
        return {
            "provided": False,
            "applied": False,
            "exclusion_candidate_rows": 0,
            "review_adjusted_regression_count": raw_regression_count,
            "blockers": [],
        }

    summary = collateral_review.get("summary") if isinstance(collateral_review.get("summary"), dict) else {}
    transition = (
        summary.get("queue_transition")
        if isinstance(summary.get("queue_transition"), dict)
        else {}
    )
    action_counts = summary.get("action_counts") if isinstance(summary.get("action_counts"), dict) else {}
    review_gate = str(collateral_review.get("gate") or "").strip()
    batch_review_rows = _safe_int(summary.get("batch_review_rows"))
    reviewed_rows = _safe_int(summary.get("reviewed_rows"))
    source_native_decision_rows = _safe_int(summary.get("source_native_decision_rows"))
    info_missing_rows = _safe_int(summary.get("info_missing_rows"))
    unreviewed_batch_rows = _safe_int(summary.get("unreviewed_batch_rows"))
    unreviewed_or_info_missing_batch_rows = _safe_int(summary.get("unreviewed_or_info_missing_batch_rows"))
    validation_issue_count = _safe_int(summary.get("validation_issue_count"))
    exclusion_candidate_rows = _safe_int(transition.get("exclusion_candidate_rows"))
    if exclusion_candidate_rows is None:
        exclusion_candidate_rows = _safe_int(
            action_counts.get("exclude_from_regression_count_after_gate_wiring")
        )
    if exclusion_candidate_rows is None:
        exclusion_candidate_rows = 0
    reviewed_raw_regression_rows: int | None = None
    reviewed_non_regression_rows: int | None = None
    unreviewed_regression_post_ids: list[int] | None = None
    review_post_ids = _review_post_ids(collateral_review)
    exclusion_post_ids = _exclusion_post_ids(collateral_review)
    if raw_regression_post_ids is not None and review_post_ids is not None:
        reviewed_raw_regression_rows = len(raw_regression_post_ids & review_post_ids)
        reviewed_non_regression_rows = len(review_post_ids - raw_regression_post_ids)
        unreviewed_regression_post_ids = sorted(raw_regression_post_ids - review_post_ids)
        if exclusion_post_ids is not None:
            exclusion_candidate_rows = len(exclusion_post_ids & raw_regression_post_ids)

    blockers: list[str] = []
    if review_gate != "REVIEW-LOCKED":
        blockers.append("collateral_review_gate_not_review_locked")
    if validation_issue_count != 0:
        blockers.append("collateral_review_validation_issues_nonzero")
    if batch_review_rows is None or reviewed_rows is None:
        blockers.append("collateral_review_counts_missing")
    elif reviewed_rows != batch_review_rows:
        blockers.append("collateral_review_not_fully_reviewed")
    if (unreviewed_batch_rows or 0) != 0:
        blockers.append("collateral_review_unreviewed_rows_nonzero")
    full_review_by_post_id = False
    if (
        raw_regression_post_ids is not None
        and review_post_ids is not None
        and raw_regression_count is not None
    ):
        full_review_by_post_id = raw_regression_post_ids.issubset(review_post_ids)

    if raw_regression_count is None:
        blockers.append("collateral_raw_regression_count_missing")
    else:
        scoped_rows = _safe_int(transition.get("original_p0_rows"))
        full_review = batch_review_rows == raw_regression_count
        scoped_p0_review = (
            batch_review_rows is not None
            and batch_review_rows < raw_regression_count
            and scoped_rows == batch_review_rows
        )
        if not (full_review or full_review_by_post_id or scoped_p0_review):
            blockers.append("collateral_review_batch_count_mismatch")
    if raw_regression_count is not None and exclusion_candidate_rows > raw_regression_count:
        blockers.append("collateral_review_exclusion_exceeds_regression_count")
    if batch_review_rows is not None and exclusion_candidate_rows > batch_review_rows:
        blockers.append("collateral_review_exclusion_exceeds_batch_count")

    applied = not blockers
    adjusted = (
        max(raw_regression_count - exclusion_candidate_rows, 0)
        if applied and raw_regression_count is not None
        else raw_regression_count
    )
    if raw_regression_count is not None and reviewed_raw_regression_rows is not None:
        unreviewed_regression_rows = max(raw_regression_count - reviewed_raw_regression_rows, 0)
    elif raw_regression_count is not None and batch_review_rows is not None:
        unreviewed_regression_rows = max(raw_regression_count - batch_review_rows, 0)
    else:
        unreviewed_regression_rows = None
    return {
        "provided": True,
        "applied": applied,
        "review_id": collateral_review.get("review_id"),
        "review_gate": review_gate,
        "review_scope": (
            "full_regression"
            if raw_regression_count is not None and batch_review_rows == raw_regression_count
            else "full_regression_post_id_overlap"
            if full_review_by_post_id
            else "p0_scoped"
            if applied and (unreviewed_regression_rows or 0) > 0
            else "unknown"
        ),
        "batch_review_rows": batch_review_rows,
        "reviewed_rows": reviewed_rows,
        "source_native_decision_rows": source_native_decision_rows,
        "info_missing_rows": info_missing_rows,
        "unreviewed_batch_rows": unreviewed_batch_rows,
        "unreviewed_or_info_missing_batch_rows": unreviewed_or_info_missing_batch_rows,
        "unreviewed_regression_rows": unreviewed_regression_rows,
        "reviewed_raw_regression_rows": reviewed_raw_regression_rows,
        "reviewed_non_regression_rows": reviewed_non_regression_rows,
        "unreviewed_regression_post_ids": unreviewed_regression_post_ids,
        "validation_issue_count": validation_issue_count,
        "exclusion_candidate_rows": exclusion_candidate_rows,
        "label_counts": summary.get("label_counts") or {},
        "action_counts": action_counts,
        "review_adjusted_regression_count": adjusted,
        "blockers": blockers,
    }


def collateral_gate(
    collateral: dict[str, Any],
    expected_shared_posts: int,
    collateral_review: dict[str, Any] | None = None,
) -> dict[str, Any]:
    shared = _safe_int(collateral.get("shared_post_count"))
    changed = _safe_int(collateral.get("changed_post_count"))
    regression_count = _safe_int(collateral.get("collateral_regression_count"))
    runtime_completed = _safe_int(collateral.get("runtime_completed_count"))
    runtime_pending = _safe_int(collateral.get("runtime_pending_count"))
    runtime_failed = _safe_int(collateral.get("runtime_failed_count"))
    runtime_complete = (
        runtime_completed == expected_shared_posts
        and (runtime_pending or 0) == 0
        and (runtime_failed or 0) == 0
    )
    review_adjustment = _collateral_review_adjustment(
        collateral_review=collateral_review,
        raw_regression_count=regression_count,
        raw_regression_post_ids=_raw_regression_post_ids(collateral),
    )
    adjusted_regression_count = review_adjustment.get("review_adjusted_regression_count")
    passed = (
        shared == expected_shared_posts
        and (adjusted_regression_count or 0) == 0
        and not review_adjustment.get("blockers")
        and runtime_complete
    )
    blockers: list[str] = []
    if shared != expected_shared_posts:
        blockers.append("collateral_shared_post_count_mismatch")
    blockers.extend(review_adjustment.get("blockers") or [])
    if (adjusted_regression_count or 0) != 0:
        blockers.append(
            "collateral_review_adjusted_regression_count_nonzero"
            if review_adjustment.get("applied")
            else "collateral_regression_count_nonzero"
        )
    if (
        review_adjustment.get("applied")
        and (review_adjustment.get("unreviewed_regression_rows") or 0) != 0
    ):
        blockers.append("collateral_review_unreviewed_regression_rows_nonzero")
    if runtime_completed is None:
        blockers.append("collateral_runtime_counts_missing")
    elif not runtime_complete:
        blockers.append("collateral_runtime_not_complete")
    return {
        "gate": "GO" if passed else "NO-GO",
        "expected_shared_posts": expected_shared_posts,
        "shared_post_count": shared,
        "changed_post_count": changed,
        "collateral_regression_count": regression_count,
        "review_adjusted_regression_count": adjusted_regression_count,
        "review_adjustment": review_adjustment,
        "runtime_complete": runtime_complete,
        "blockers": blockers,
    }


def evaluate_gates(
    *,
    golden: dict[str, Any],
    collateral: dict[str, Any],
    collateral_review: dict[str, Any] | None = None,
    expected_golden_rows: int = 18,
    expected_collateral_shared_posts: int = 375,
) -> dict[str, Any]:
    golden_result = golden_gate(golden, expected_golden_rows)
    collateral_result = collateral_gate(
        collateral,
        expected_collateral_shared_posts,
        collateral_review=collateral_review,
    )
    gate = "GO" if golden_result["gate"] == "GO" and collateral_result["gate"] == "GO" else "NO-GO"
    return {
        "report_type": "always_on_regression_gates",
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "gate": gate,
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "policy": {
            "golden_expected_rows": expected_golden_rows,
            "full_375_collateral_required": True,
            "golden_pass_alone_is_not_approval": True,
            "collateral_runtime_pass_alone_is_not_approval": True,
            "collateral_source_native_exclusion_requires_clean_review_summary": True,
        },
        "golden": golden_result,
        "collateral": collateral_result,
        "blockers": [
            *[f"golden:{code}" for code in golden_result["blockers"]],
            *[f"collateral:{code}" for code in collateral_result["blockers"]],
        ],
    }


def write_markdown(report: dict[str, Any], path: Path) -> None:
    def display(value: Any) -> str:
        return "null" if value is None else str(value)

    lines = [
        "# 상시 회귀 게이트",
        "",
        f"- gate: `{report['gate']}`",
        f"- semantic_quality: `{report['semantic_quality']}`",
        f"- full_scan_approval: `{str(report['full_scan_approval']).lower()}`",
        f"- 정책: golden-{report['golden']['expected_rows']}과 full 375 collateral diff를 항상 함께 요구한다.",
        "",
        "## Golden 게이트",
        "",
        f"- gate: `{report['golden']['gate']}`",
        f"- rows: `{report['golden']['row_count']}/{report['golden']['expected_rows']}`",
        f"- passed: `{display(report['golden']['passed_count'])}`",
        f"- failed: `{display(report['golden']['failed_count'])}`",
        f"- runtime_complete: `{report['golden']['runtime_complete']}`",
        "",
        "## Collateral 게이트",
        "",
        f"- gate: `{report['collateral']['gate']}`",
        (
            "- shared posts: "
            f"`{report['collateral']['shared_post_count']}/{report['collateral']['expected_shared_posts']}`"
        ),
        f"- changed posts: `{report['collateral']['changed_post_count']}`",
        f"- raw collateral_regression_count: `{report['collateral']['collateral_regression_count']}`",
        (
            "- review exclusion candidates: "
            f"`{report['collateral']['review_adjustment'].get('exclusion_candidate_rows')}`"
        ),
        (
            "- review adjustment applied: "
            f"`{report['collateral']['review_adjustment'].get('applied')}`"
        ),
        (
            "- review scope: "
            f"`{report['collateral']['review_adjustment'].get('review_scope')}`"
        ),
        (
            "- source-native decision rows: "
            f"`{display(report['collateral']['review_adjustment'].get('source_native_decision_rows'))}`"
        ),
        (
            "- info missing rows: "
            f"`{display(report['collateral']['review_adjustment'].get('info_missing_rows'))}`"
        ),
        (
            "- unreviewed or info-missing rows: "
            f"`{display(report['collateral']['review_adjustment'].get('unreviewed_or_info_missing_batch_rows'))}`"
        ),
        (
            "- unreviewed regression rows: "
            f"`{report['collateral']['review_adjustment'].get('unreviewed_regression_rows')}`"
        ),
        (
            "- reviewed raw regression rows: "
            f"`{display(report['collateral']['review_adjustment'].get('reviewed_raw_regression_rows'))}`"
        ),
        (
            "- reviewed non-regression rows: "
            f"`{display(report['collateral']['review_adjustment'].get('reviewed_non_regression_rows'))}`"
        ),
        (
            "- review_adjusted_regression_count: "
            f"`{report['collateral']['review_adjusted_regression_count']}`"
        ),
        f"- runtime_complete: `{report['collateral']['runtime_complete']}`",
        "",
        "## 차단 항목",
        "",
    ]
    if report["blockers"]:
        for blocker in report["blockers"]:
            lines.append(f"- `{blocker}`")
    else:
        lines.append("- 없음")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate golden plus full 375 collateral as always-on gates.")
    parser.add_argument("--golden-audit", required=True, type=Path)
    parser.add_argument("--collateral-compare", required=True, type=Path)
    parser.add_argument("--collateral-review-summary", type=Path, default=None)
    parser.add_argument("--expected-golden-rows", type=int, default=18)
    parser.add_argument("--expected-collateral-shared-posts", type=int, default=375)
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-md", required=True, type=Path)
    parser.add_argument("--fail-on-no-go", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = evaluate_gates(
        golden=load_json(args.golden_audit),
        collateral=load_json(args.collateral_compare),
        collateral_review=(
            load_json(args.collateral_review_summary)
            if args.collateral_review_summary
            else None
        ),
        expected_golden_rows=args.expected_golden_rows,
        expected_collateral_shared_posts=args.expected_collateral_shared_posts,
    )
    write_json(args.output_json, report)
    write_markdown(report, args.output_md)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.fail_on_no_go and report["gate"] != "GO":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
