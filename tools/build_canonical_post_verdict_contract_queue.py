from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


NEXT_STATE_TO_BATCH = {
    "candidate_scrub_or_expected_title_restore_contract_required": "C1_expected_restore_or_candidate_scrub_contract",
    "canonical_variant_policy_contract_required": "C2_canonical_variant_policy_contract",
    "hard_hold_or_native_web_review_required": "C3_stronger_evidence_or_native_web_hold",
    "source_native_expectation_update_or_blind_acceptance_required": "C4_expected_update_or_blind_acceptance_contract",
    "current_projection_candidate_scrub_required": "C5_current_candidate_scrub_contract",
}

NEXT_STATE_TO_ACTIONS = {
    "candidate_scrub_or_expected_title_restore_contract_required": [
        "write_expected_restore_or_candidate_scrub_contract_test",
        "keep_runtime_replay_blocked_until_contract_passes",
    ],
    "canonical_variant_policy_contract_required": [
        "write_canonical_variant_policy_contract_test",
        "preserve_variant_alias_without_unverified_publish",
        "keep_runtime_replay_blocked_until_contract_passes",
    ],
    "hard_hold_or_native_web_review_required": [
        "collect_stronger_source_or_native_web_evidence",
        "keep_hard_hold_until_evidence_strength_improves",
    ],
    "source_native_expectation_update_or_blind_acceptance_required": [
        "update_expected_or_blind_acceptance_contract",
        "keep_runtime_replay_blocked_until_expected_contract_updates",
    ],
    "current_projection_candidate_scrub_required": [
        "write_current_candidate_scrub_contract_test",
        "keep_runtime_replay_blocked_until_candidate_scrub_passes",
    ],
}


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


def _rows(application: dict[str, Any]) -> list[dict[str, Any]]:
    rows = application.get("rows")
    if not isinstance(rows, list):
        raise ValueError("application state must contain rows list")
    return [row for row in rows if isinstance(row, dict)]


def _validation_issues(row: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    if row.get("row_validation_issues"):
        issues.append("source_application_row_has_validation_issues")
    next_state = _string(row.get("post_verdict_next_state"))
    if not next_state:
        issues.append("missing_post_verdict_next_state")
    elif next_state not in NEXT_STATE_TO_BATCH:
        issues.append("unknown_post_verdict_next_state")
    if row.get("runtime_replay_allowed_after_verdict") is True:
        issues.append("runtime_replay_already_allowed_after_verdict")
    if row.get("contract_test_required_before_runtime") is not True:
        issues.append("contract_test_required_before_runtime_not_true")
    return issues


def _queue_row(row: dict[str, Any]) -> dict[str, Any]:
    next_state = _string(row.get("post_verdict_next_state"))
    batch_lane = NEXT_STATE_TO_BATCH.get(next_state, "C0_invalid_or_unknown_contract_lane")
    return {
        "post_id": row.get("post_id"),
        "contract_batch_lane": batch_lane,
        "post_verdict_next_state": next_state,
        "canonical_verdict": row.get("canonical_verdict"),
        "evidence_grade": row.get("evidence_grade"),
        "canonical_title": row.get("canonical_title"),
        "canonical_url": row.get("canonical_url"),
        "expected_or_source_native_title": row.get("expected_or_source_native_title"),
        "current_projection_candidate_title": row.get("current_projection_candidate_title"),
        "current_projection_candidate_url": row.get("current_projection_candidate_url"),
        "review_lane": row.get("review_lane"),
        "candidate_support_state": row.get("candidate_support_state"),
        "search_gate": row.get("search_gate"),
        "primary_repair_lane": row.get("primary_repair_lane"),
        "runtime_release_condition": row.get("runtime_release_condition"),
        "runtime_replay_allowed": False,
        "contract_test_required_before_runtime": True,
        "actions": NEXT_STATE_TO_ACTIONS.get(next_state, ["review_invalid_post_verdict_next_state"]),
        "rationale_ko": row.get("rationale_ko"),
        "evidence_refs": row.get("evidence_refs") or [],
    }


def build_contract_queue(
    application: dict[str, Any],
    *,
    queue_id: str,
    generated_at: str | None = None,
) -> dict[str, Any]:
    rows = _rows(application)
    queue_rows: list[dict[str, Any]] = []
    validation_issues: list[dict[str, Any]] = []
    for row in rows:
        issues = _validation_issues(row)
        if issues:
            validation_issues.append({"post_id": row.get("post_id"), "issues": issues})
        queue_rows.append(_queue_row(row))

    lane_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in queue_rows:
        lane_groups[_string(row.get("contract_batch_lane"))].append(row)

    next_batches = []
    for lane in sorted(lane_groups):
        lane_rows = lane_groups[lane]
        next_batches.append(
            {
                "contract_batch_lane": lane,
                "row_count": len(lane_rows),
                "post_ids": [row.get("post_id") for row in lane_rows],
                "canonical_verdict_counts": dict(
                    Counter(_string(row.get("canonical_verdict")) for row in lane_rows)
                ),
                "search_gate_counts": dict(Counter(_string(row.get("search_gate")) for row in lane_rows)),
                "runtime_replay_allowed_rows": 0,
            }
        )

    return {
        "report_type": "canonical_post_verdict_contract_queue",
        "queue_id": queue_id,
        "generated_at": generated_at or datetime.now().replace(microsecond=0).isoformat(),
        "source_application": application.get("review_id"),
        "source_batch": application.get("source_batch"),
        "source_verdicts": application.get("source_verdicts"),
        "gate": "NO-GO" if validation_issues else "REVIEW-LOCKED",
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "summary": {
            "source_application_rows": len(rows),
            "contract_queue_rows": len(queue_rows),
            "validation_issue_count": len(validation_issues),
            "contract_batch_lane_counts": dict(
                Counter(_string(row.get("contract_batch_lane")) for row in queue_rows)
            ),
            "post_verdict_next_state_counts": dict(
                Counter(_string(row.get("post_verdict_next_state")) for row in queue_rows)
            ),
            "canonical_verdict_counts": dict(
                Counter(_string(row.get("canonical_verdict")) for row in queue_rows)
            ),
            "runtime_replay_allowed_rows": 0,
            "contract_test_required_rows": len(queue_rows),
            "full375_collateral_gate": "NO-GO",
            "completion_gate": "adjusted full375 collateral GO + full_scan path",
        },
        "validation_issues": validation_issues,
        "next_batches": next_batches,
        "rows": queue_rows,
        "approval_boundary": {
            "post_verdict_queue_is_not_runtime_release": True,
            "runtime_replay_before_contract_tests_forbidden": True,
            "full375_collateral_remains_no_go": True,
        },
    }


def write_markdown(path: Path, queue: dict[str, Any]) -> None:
    summary = queue["summary"]
    lines = [
        f"# {queue.get('queue_id')}",
        "",
        "이 큐는 canonical verdict 적용 뒤의 contract 작업 배치다. "
        "아직 runtime replay 허가가 아니며, contract test와 필요한 native-web/강한 근거 확인 전에는 full_scan approval을 열지 않는다.",
        "",
        "## 요약",
        "",
        f"- gate: `{queue['gate']}`",
        f"- semantic_quality: `{queue['semantic_quality']}`",
        f"- full_scan_approval: `{str(queue['full_scan_approval']).lower()}`",
        f"- source_application_rows: `{summary['source_application_rows']}`",
        f"- contract_queue_rows: `{summary['contract_queue_rows']}`",
        f"- validation issues: `{summary['validation_issue_count']}`",
        f"- runtime_replay_allowed_rows: `{summary['runtime_replay_allowed_rows']}`",
        f"- contract_test_required_rows: `{summary['contract_test_required_rows']}`",
        f"- full375 collateral: `{summary['full375_collateral_gate']}`",
        f"- completion gate: `{summary['completion_gate']}`",
        "",
        "## Contract batch lanes",
        "",
    ]
    for lane, count in sorted((summary.get("contract_batch_lane_counts") or {}).items()):
        lines.append(f"- `{lane}`: `{count}`")
    lines.extend(["", "## Next batches", ""])
    for batch in queue.get("next_batches") or []:
        post_ids = ", ".join(f"`{post_id}`" for post_id in batch.get("post_ids") or [])
        lines.append(
            f"- `{batch['contract_batch_lane']}` rows=`{batch['row_count']}` "
            f"runtime_replay_allowed=`{batch['runtime_replay_allowed_rows']}`"
        )
        lines.append(f"  - post_ids: {post_ids}")
    lines.extend(["", "## Gate 해석", ""])
    lines.append(
        f"Canonical verdict는 `{summary['contract_queue_rows']}/{summary['source_application_rows']}` 적용됐지만 "
        "이 큐는 replay release가 아니다. C1/C2는 contract test가 먼저 필요하고, "
        "C3는 stronger evidence 또는 native-web 검증 전까지 hard hold다."
    )
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build post-verdict contract batches from canonical verdict application state.")
    parser.add_argument("--application", required=True, type=Path)
    parser.add_argument("--queue-id", default="canonical_post_verdict_contract_queue")
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-md", required=True, type=Path)
    parser.add_argument("--fail-on-validation-issue", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    queue = build_contract_queue(
        load_json(args.application),
        queue_id=args.queue_id,
    )
    write_json(args.output_json, queue)
    write_markdown(args.output_md, queue)
    print(json.dumps({"gate": queue["gate"], "summary": queue["summary"]}, ensure_ascii=False, indent=2))
    if args.fail_on_validation_issue and queue["validation_issues"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
