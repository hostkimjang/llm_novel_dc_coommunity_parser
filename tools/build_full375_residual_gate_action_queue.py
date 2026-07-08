from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


EXCLUSION_ACTION = "exclude_from_regression_count_after_gate_wiring"


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _string(value: Any) -> str:
    return str(value or "").strip()


def _identity_title(identity: Any) -> Any:
    return identity.get("official_title") if isinstance(identity, dict) else None


def _identity_status(identity: Any) -> Any:
    return identity.get("candidate_ledger_status") if isinstance(identity, dict) else None


def _review_rows_by_post_id(review_summary: dict[str, Any]) -> dict[int, dict[str, Any]]:
    rows = review_summary.get("rows")
    if not isinstance(rows, list):
        return {}
    indexed: dict[int, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        post_id = row.get("post_id")
        if isinstance(post_id, int):
            indexed[post_id] = row
    return indexed


def _lane_for(*, status: str, review: dict[str, Any] | None) -> str:
    if review is None:
        if status == "resolved_to_different_title":
            return "unreviewed_variant_or_canonical_contract_review"
        if status == "null_to_resolved":
            return "unreviewed_unsafe_promotion_native_review"
        if status == "resolved_to_null":
            return "unreviewed_safe_loss_native_or_contract_review"
        return "unreviewed_regression_review"
    actions = set(review.get("action") or [])
    if "shared_promotion_gate_wiring_required" in actions:
        return "shared_promotion_gate_contract_repair"
    if "candidate_set_rebuild_required" in actions:
        return "candidate_set_rebuild_contract"
    if "native_web_or_image_evidence_required" in actions:
        return "native_web_or_image_evidence_batch"
    if "native_web_judge_reprocess_required" in actions:
        return "native_web_judge_reprocess_contract"
    if "wrong_work_or_cross_media_policy_hold_required" in actions or "blind_or_policy_judge_required" in actions:
        return "policy_or_cross_media_hold_review"
    if "native_web_or_image_human_review_required" in actions:
        return "native_web_or_image_human_review"
    if "native_web_or_alias_relation_review_required" in actions:
        return "alias_relation_native_web_review"
    if "image_native_review_required" in actions:
        return "image_native_review"
    if "character_bridge_native_web_review_required" in actions:
        return "character_bridge_native_web_review"
    return "source_native_followup_required"


def _reason_for_row(row: dict[str, Any]) -> str:
    if row["review_coverage"] == "unreviewed_raw_regression":
        return "full375 raw regression이지만 병합 source-native review rows에 post_id가 없다."
    label = row.get("review_label")
    if label == "INFO_MISSING":
        return "source-native/native-web 근거가 누락되어 raw regression을 제외할 수 없다."
    if label == "REPROCESS":
        return "source-native 판정이 수리 또는 shared gate 계약 처리를 요구한다."
    if label == "REJECT":
        return "wrong-work 또는 cross-media policy hold 검토가 필요하다."
    if label == "HOLD":
        return "native-web, image, alias, character bridge 검토 전 hard-hold를 유지한다."
    return "regression count 제외 후보가 아니므로 후속 검토가 필요하다."


def build_queue(*, collateral_compare: dict[str, Any], review_summary: dict[str, Any], queue_id: str) -> dict[str, Any]:
    review_by_post_id = _review_rows_by_post_id(review_summary)
    raw_rows = [
        row
        for row in collateral_compare.get("rows") or []
        if isinstance(row, dict) and row.get("is_regression")
    ]
    residual_rows: list[dict[str, Any]] = []
    exclusion_candidate_rows = 0
    reviewed_raw_regression_rows = 0
    reviewed_non_regression_rows = 0
    raw_post_ids = {row.get("post_id") for row in raw_rows if isinstance(row.get("post_id"), int)}
    for review in review_by_post_id.values():
        post_id = review.get("post_id")
        if isinstance(post_id, int) and post_id not in raw_post_ids:
            reviewed_non_regression_rows += 1
    for raw in raw_rows:
        post_id = raw.get("post_id")
        if not isinstance(post_id, int):
            continue
        review = review_by_post_id.get(post_id)
        actions = review.get("action") or [] if review else []
        if review is not None:
            reviewed_raw_regression_rows += 1
        if EXCLUSION_ACTION in actions:
            exclusion_candidate_rows += 1
            continue
        status = _string(raw.get("status"))
        before = raw.get("before_identity") or {}
        after = raw.get("after_identity") or {}
        out_row = {
            "post_id": post_id,
            "status": status,
            "triage_bucket": review.get("triage_bucket") if review else status,
            "review_coverage": "reviewed_raw_regression" if review else "unreviewed_raw_regression",
            "queue_lane": _lane_for(status=status, review=review),
            "before_title": _identity_title(before),
            "before_candidate_ledger_status": _identity_status(before),
            "after_title": _identity_title(after),
            "after_candidate_ledger_status": _identity_status(after),
            "review_label": review.get("review_label") if review else "INFO_MISSING",
            "source_native_verdict": review.get("source_native_verdict") if review else "raw_regression_not_in_review_summary",
            "evidence_grade": review.get("evidence_grade") if review else "Missing",
            "selected_option_id": review.get("selected_option_id") if review else None,
            "selected_title": review.get("selected_title") if review else None,
            "selected_url": review.get("selected_url") if review else None,
            "action": actions if review else ["source_native_or_blind_review_required"],
            "source_review_id": review.get("source_review_id") if review else None,
            "rationale_ko": review.get("rationale_ko") if review else None,
            "evidence_refs": review.get("evidence_refs") if review else [],
        }
        out_row["reason_ko"] = _reason_for_row(out_row)
        residual_rows.append(out_row)
    lane_counts = Counter(row["queue_lane"] for row in residual_rows)
    status_counts = Counter(row["status"] for row in residual_rows)
    label_counts = Counter(row["review_label"] for row in residual_rows)
    coverage_counts = Counter(row["review_coverage"] for row in residual_rows)
    bucket_counts = Counter(_string(row.get("triage_bucket")) for row in residual_rows)
    return {
        "report_type": "full375_residual_gate_action_queue",
        "queue_id": queue_id,
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "source_collateral_compare": collateral_compare.get("compare_id"),
        "source_review_summary": review_summary.get("review_id"),
        "gate": "REVIEW-LOCKED",
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "summary": {
            "raw_regression_rows": len(raw_rows),
            "reviewed_raw_regression_rows": reviewed_raw_regression_rows,
            "reviewed_non_regression_rows": reviewed_non_regression_rows,
            "exclusion_candidate_rows": exclusion_candidate_rows,
            "residual_action_queue_rows": len(residual_rows),
            "reviewed_raw_residual_rows": coverage_counts.get("reviewed_raw_regression", 0),
            "unreviewed_raw_residual_rows": coverage_counts.get("unreviewed_raw_regression", 0),
            "validation_issue_count": 0,
            "counts_by_lane": dict(lane_counts),
            "counts_by_status": dict(status_counts),
            "counts_by_review_label": dict(label_counts),
            "counts_by_coverage": dict(coverage_counts),
            "counts_by_bucket": dict(bucket_counts),
        },
        "rows": residual_rows,
        "next_actions": [
            "unreviewed raw regression rows must be source-native or native-web reviewed before approval.",
            "reviewed residual rows must go through the lane-specific contract or native evidence path.",
            "Do not dispatch a runtime test run unless a lane explicitly produces runtime input candidates.",
            "Keep semantic_quality=REVIEW-LOCKED and full_scan_approval=false.",
        ],
    }


def write_markdown(path: Path, queue: dict[str, Any]) -> None:
    summary = queue["summary"]
    lines = [
        "# Full375 residual gate action queue",
        "",
        f"- gate: `{queue['gate']}`",
        f"- semantic_quality: `{queue['semantic_quality']}`",
        f"- full_scan_approval: `{str(queue['full_scan_approval']).lower()}`",
        f"- raw regression rows: `{summary['raw_regression_rows']}`",
        f"- reviewed raw regression rows: `{summary['reviewed_raw_regression_rows']}`",
        f"- reviewed non-regression rows: `{summary['reviewed_non_regression_rows']}`",
        f"- exclusion candidate rows: `{summary['exclusion_candidate_rows']}`",
        f"- residual action queue rows: `{summary['residual_action_queue_rows']}`",
        f"- reviewed raw residual rows: `{summary['reviewed_raw_residual_rows']}`",
        f"- unreviewed raw residual rows: `{summary['unreviewed_raw_residual_rows']}`",
        "",
        "## Lane Counts",
        "",
    ]
    for lane, count in sorted(summary["counts_by_lane"].items()):
        lines.append(f"- `{lane}`: `{count}`")
    lines.extend(["", "## Rows", ""])
    for row in queue["rows"]:
        lines.append(
            "- "
            f"`{row['post_id']}` lane=`{row['queue_lane']}` status=`{row['status']}` "
            f"coverage=`{row['review_coverage']}` label=`{row['review_label']}` "
            f"before=`{row.get('before_title')}` after=`{row.get('after_title')}`"
        )
        lines.append(f"  - 근거: {row['reason_ko']}")
    lines.extend(
        [
            "",
            "## Gate 해석",
            "",
            "이 큐는 corrected full375 gate 기준의 남은 raw regression action queue다. "
            "큐가 0이 되고 full375 runtime counts가 확인되기 전까지 full_scan approval은 열리지 않는다.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build full375 residual action queue from collateral and review overlap.")
    parser.add_argument("--collateral-compare", required=True, type=Path)
    parser.add_argument("--review-summary", required=True, type=Path)
    parser.add_argument("--queue-id", required=True)
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-md", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    queue = build_queue(
        collateral_compare=load_json(args.collateral_compare),
        review_summary=load_json(args.review_summary),
        queue_id=args.queue_id,
    )
    write_json(args.output_json, queue)
    write_markdown(args.output_md, queue)
    print(json.dumps({"gate": queue["gate"], "summary": queue["summary"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
