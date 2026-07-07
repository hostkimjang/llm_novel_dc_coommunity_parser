from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


RESIDUAL_LABELS = {"REPROCESS", "HOLD", "INFO_MISSING"}
REPAIR_PREFIXES = ("repair_",)
REVIEW_ACTION_MARKERS = (
    "_review_required",
    "_replay_required",
    "_policy_required",
    "_contract_required",
    "_canonicalization_required",
)


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def normalize_actions(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    return [str(value)]


def _counter_to_dict(counter: Counter[str]) -> dict[str, int]:
    return {key: counter[key] for key in sorted(counter)}


def _priority_for_group(action: str, labels: Counter[str]) -> str:
    if labels.get("REPROCESS") and action.startswith(REPAIR_PREFIXES):
        return "P0"
    if labels.get("INFO_MISSING") or action.startswith("p1_"):
        return "P1"
    if labels.get("REPROCESS"):
        return "P1"
    return "P2"


def _priority_for_actions(actions: list[str], label: str) -> str:
    labels = Counter({label: 1})
    priorities = [_priority_for_group(action, labels) for action in actions]
    if "P0" in priorities:
        return "P0"
    if "P1" in priorities:
        return "P1"
    return "P2"


def _owner_mode_for_group(action: str, labels: Counter[str]) -> str:
    if action.startswith(REPAIR_PREFIXES):
        return "CODE_OR_RUNTIME_REPAIR"
    if labels.get("INFO_MISSING"):
        return "SOURCE_NATIVE_OR_BLIND_REVIEW"
    if labels.get("HOLD"):
        return "POLICY_OR_NATIVE_REVIEW"
    return "RUNTIME_REPLAY_OR_REVIEW"


def _owner_mode_for_actions(actions: list[str], label: str) -> str:
    labels = Counter({label: 1})
    if any(action.startswith(REPAIR_PREFIXES) for action in actions):
        return "CODE_OR_RUNTIME_REPAIR"
    if label == "INFO_MISSING":
        return "SOURCE_NATIVE_OR_BLIND_REVIEW"
    if label == "HOLD":
        return "POLICY_OR_NATIVE_REVIEW"
    owner_modes = [_owner_mode_for_group(action, labels) for action in actions]
    if "POLICY_OR_NATIVE_REVIEW" in owner_modes:
        return "POLICY_OR_NATIVE_REVIEW"
    if "SOURCE_NATIVE_OR_BLIND_REVIEW" in owner_modes:
        return "SOURCE_NATIVE_OR_BLIND_REVIEW"
    return "RUNTIME_REPLAY_OR_REVIEW"


def _coerce_post_id(value: Any) -> int | Any:
    try:
        return int(value)
    except (TypeError, ValueError):
        return value


def _unreviewed_regression_entry(row: dict[str, Any], source_review_id: str | None) -> dict[str, Any]:
    bucket = str(row.get("triage_bucket") or "unknown")
    actions = [
        "source_native_or_blind_review_required",
        f"p1_{bucket}_review_required",
    ]
    return {
        "post_id": row.get("post_id"),
        "triage_bucket": bucket,
        "review_label": "INFO_MISSING",
        "source_native_verdict": "unreviewed_regression_row",
        "selected_title": row.get("after_title"),
        "selected_option_id": "UNREVIEWED_P1",
        "evidence_grade": "Missing",
        "actions": actions,
        "rationale_ko": (
            "full375 collateral triage에서는 회귀 후보지만 P0 source-native review 범위 밖이라 "
            "별도 source-native 또는 blind review가 필요하다."
        ),
        "evidence_refs": [],
        "source_review_id": source_review_id,
        "before_title": row.get("before_title"),
        "after_title": row.get("after_title"),
        "before_url": row.get("before_url"),
        "after_url": row.get("after_url"),
        "priority": row.get("priority"),
        "collateral_status": row.get("status"),
    }


def build_residual_queue(
    combined_review: dict[str, Any],
    *,
    generated_at: str | None = None,
    queue_id: str = "collateral_residual_action_queue",
    exclude_post_ids: set[int] | None = None,
    unreviewed_regression_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    rows = combined_review.get("rows") or []
    if not isinstance(rows, list):
        raise ValueError("combined_review.rows must be a list")

    exclude_post_ids = exclude_post_ids or set()
    residual_rows: list[dict[str, Any]] = []
    label_counts: Counter[str] = Counter()
    bucket_counts: Counter[str] = Counter()
    action_counts: Counter[str] = Counter()
    excluded_label_counts: Counter[str] = Counter()
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    excluded_rows: list[dict[str, Any]] = []

    for row in rows:
        if not isinstance(row, dict):
            continue
        raw_post_id = row.get("post_id")
        post_id = _coerce_post_id(raw_post_id)
        label = str(row.get("review_label") or "").strip().upper()
        if label not in RESIDUAL_LABELS:
            continue
        if isinstance(post_id, int) and post_id in exclude_post_ids:
            excluded_label_counts[label] += 1
            excluded_rows.append(
                {
                    "post_id": post_id,
                    "review_label": label,
                    "triage_bucket": row.get("triage_bucket"),
                    "source_native_verdict": row.get("source_native_verdict"),
                }
            )
            continue
        actions = normalize_actions(row.get("action") if row.get("action") is not None else row.get("actions"))
        if not actions:
            actions = ["manual_review_required"]
        bucket = str(row.get("triage_bucket") or "unknown")
        entry = {
            "post_id": raw_post_id,
            "triage_bucket": bucket,
            "priority": _priority_for_actions(actions, label),
            "owner_mode": _owner_mode_for_actions(actions, label),
            "review_label": label,
            "source_native_verdict": row.get("source_native_verdict"),
            "selected_title": row.get("selected_title"),
            "selected_option_id": row.get("selected_option_id"),
            "evidence_grade": row.get("evidence_grade"),
            "actions": actions,
            "rationale_ko": row.get("rationale_ko"),
            "evidence_refs": row.get("evidence_refs") or [],
            "source_review_id": row.get("source_review_id"),
        }
        residual_rows.append(entry)
        label_counts[label] += 1
        bucket_counts[bucket] += 1
        for action in actions:
            action_counts[action] += 1
            groups[action].append(entry)

    seen_post_ids = {_coerce_post_id(row.get("post_id")) for row in rows if isinstance(row, dict)}
    unreviewed_regression_rows = unreviewed_regression_rows or []
    for row in unreviewed_regression_rows:
        if not isinstance(row, dict):
            continue
        post_id = _coerce_post_id(row.get("post_id"))
        if isinstance(post_id, int) and post_id in exclude_post_ids:
            excluded_label_counts["INFO_MISSING"] += 1
            excluded_rows.append(
                {
                    "post_id": post_id,
                    "review_label": "INFO_MISSING",
                    "triage_bucket": row.get("triage_bucket"),
                    "source_native_verdict": "unreviewed_regression_row",
                }
            )
            continue
        if post_id in seen_post_ids:
            continue
        entry = _unreviewed_regression_entry(
            row,
            source_review_id=(
                combined_review.get("review_id")
                or combined_review.get("source_review_id")
                or combined_review.get("queue_id")
            ),
        )
        residual_rows.append(entry)
        label_counts["INFO_MISSING"] += 1
        bucket = str(entry["triage_bucket"])
        bucket_counts[bucket] += 1
        for action in entry["actions"]:
            action_counts[action] += 1
            groups[action].append(entry)

    action_groups: list[dict[str, Any]] = []
    for action in sorted(groups):
        group_rows = groups[action]
        group_label_counts = Counter(str(item["review_label"]) for item in group_rows)
        group_bucket_counts = Counter(str(item["triage_bucket"]) for item in group_rows)
        action_groups.append(
            {
                "action": action,
                "priority": _priority_for_group(action, group_label_counts),
                "owner_mode": _owner_mode_for_group(action, group_label_counts),
                "row_count": len(group_rows),
                "label_counts": _counter_to_dict(group_label_counts),
                "bucket_counts": _counter_to_dict(group_bucket_counts),
                "post_ids": [item["post_id"] for item in group_rows],
                "sample_rows": group_rows[:8],
            }
        )

    summary = combined_review.get("summary") or {}
    transition = summary.get("queue_transition") or {}
    source_expected_residual = transition.get("residual_action_queue_rows", summary.get("residual_action_queue_rows"))
    source_label_counts = summary.get("label_counts") or {}
    source_expected_reprocess = transition.get("repair_required_rows", source_label_counts.get("REPROCESS"))
    source_expected_hold = transition.get("policy_or_native_review_required_rows", source_label_counts.get("HOLD"))

    def _adjust_expected(value: Any, label: str | None = None) -> int | None:
        if value is None:
            return None
        excluded_count = len(excluded_rows) if label is None else excluded_label_counts.get(label, 0)
        return int(value) - excluded_count

    unreviewed_regression_count = len(
        [
            row
            for row in unreviewed_regression_rows
            if isinstance(row, dict)
            and _coerce_post_id(row.get("post_id")) not in seen_post_ids
            and _coerce_post_id(row.get("post_id")) not in exclude_post_ids
        ]
    )
    expected_residual = _adjust_expected(source_expected_residual)
    if expected_residual is not None:
        expected_residual += unreviewed_regression_count
    expected_reprocess = _adjust_expected(source_expected_reprocess, "REPROCESS")
    expected_hold = _adjust_expected(source_expected_hold, "HOLD")
    validation_issues: list[dict[str, Any]] = []
    if expected_residual is not None and int(expected_residual) != len(residual_rows):
        validation_issues.append(
            {
                "code": "residual_action_queue_count_mismatch",
                "expected": expected_residual,
                "actual": len(residual_rows),
            }
        )
    if expected_reprocess is not None and int(expected_reprocess) != label_counts.get("REPROCESS", 0):
        validation_issues.append(
            {
                "code": "reprocess_count_mismatch",
                "expected": expected_reprocess,
                "actual": label_counts.get("REPROCESS", 0),
            }
        )
    if expected_hold is not None and int(expected_hold) != label_counts.get("HOLD", 0):
        validation_issues.append(
            {
                "code": "hold_count_mismatch",
                "expected": expected_hold,
                "actual": label_counts.get("HOLD", 0),
            }
        )

    return {
        "report_type": "collateral_residual_action_queue",
        "queue_id": queue_id,
        "generated_at": generated_at or datetime.now().replace(microsecond=0).isoformat(),
        "source_review_id": (
            combined_review.get("review_id")
            or combined_review.get("source_review_id")
            or combined_review.get("queue_id")
        ),
        "source_gate": combined_review.get("gate"),
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "gate": "NO-GO" if validation_issues else "REVIEW-LOCKED",
        "summary": {
            "source_rows": len(rows),
            "residual_action_queue_rows": len(residual_rows),
            "label_counts": _counter_to_dict(label_counts),
            "bucket_counts": _counter_to_dict(bucket_counts),
            "action_counts": _counter_to_dict(action_counts),
            "action_group_count": len(action_groups),
            "expected_from_source_transition": {
                "residual_action_queue_rows": expected_residual,
                "repair_required_rows": expected_reprocess,
                "policy_or_native_review_required_rows": expected_hold,
                "source_residual_action_queue_rows": source_expected_residual,
                "source_repair_required_rows": source_expected_reprocess,
                "source_policy_or_native_review_required_rows": source_expected_hold,
            },
            "closed_post_ids_excluded": sorted(exclude_post_ids),
            "excluded_residual_action_queue_rows": len(excluded_rows),
            "excluded_label_counts": _counter_to_dict(excluded_label_counts),
            "unreviewed_regression_rows_added": unreviewed_regression_count,
            "validation_issue_count": len(validation_issues),
        },
        "validation_issues": validation_issues,
        "excluded_rows": excluded_rows,
        "action_groups": action_groups,
        "rows": residual_rows,
        "approval_boundary": {
            "launch_or_queue_split_is_not_approval": True,
            "search_recovery_required_before_promotion_unblock": True,
            "promotion_blocked_tag_until_search_recovery": "search-blind conditional",
        },
    }


def write_markdown(queue: dict[str, Any], path: Path) -> None:
    summary = queue["summary"]
    lines = [
        f"# {queue.get('queue_id')}",
        "",
        "## 요약",
        "",
        f"- source_review_id: `{queue.get('source_review_id')}`",
        f"- gate: `{queue.get('gate')}`",
        f"- source_rows: `{summary.get('source_rows')}`",
        f"- residual_action_queue_rows: `{summary.get('residual_action_queue_rows')}`",
        f"- label_counts: `{summary.get('label_counts')}`",
        f"- closed_post_ids_excluded: `{summary.get('closed_post_ids_excluded')}`",
        f"- excluded_residual_action_queue_rows: `{summary.get('excluded_residual_action_queue_rows')}`",
        f"- unreviewed_regression_rows_added: `{summary.get('unreviewed_regression_rows_added')}`",
        f"- action_group_count: `{summary.get('action_group_count')}`",
        f"- validation_issue_count: `{summary.get('validation_issue_count')}`",
        "- approval: `false`",
        "- semantic_quality: `REVIEW-LOCKED`",
        "",
        "## 승인 경계",
        "",
        "- 이 큐 분해는 residual action queue를 실행 가능하게 만든 산출물이며 approval이 아니다.",
        "- search recovery가 `unrecovered_degraded=0`으로 닫히기 전까지 `promotion_blocked`는 `search-blind conditional`이다.",
        "- `REPROCESS`는 코드/계약/runtime replay 후보이고, `HOLD`는 native image/web/source 또는 policy review 후보다.",
        "",
        "## 실행 그룹",
        "",
    ]
    for group in queue.get("action_groups") or []:
        sample = ", ".join(str(post_id) for post_id in group.get("post_ids", [])[:12])
        lines.extend(
            [
                f"### {group.get('priority')} {group.get('action')}",
                "",
                f"- row_count: `{group.get('row_count')}`",
                f"- owner_mode: `{group.get('owner_mode')}`",
                f"- label_counts: `{group.get('label_counts')}`",
                f"- bucket_counts: `{group.get('bucket_counts')}`",
                f"- sample_post_ids: `{sample}`",
                "",
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    while lines and lines[-1] == "":
        lines.pop()
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Split a combined collateral source-native review into residual action groups."
    )
    parser.add_argument("--combined-review", required=True, type=Path)
    parser.add_argument("--queue-id", default="collateral_residual_action_queue")
    parser.add_argument("--collateral-triage", type=Path, default=None)
    parser.add_argument(
        "--include-triage-priorities",
        default="",
        help="쉼표로 구분한 collateral triage priority 목록. 예: P1",
    )
    parser.add_argument(
        "--exclude-post-ids",
        default="",
        help="쉼표로 구분한 post_id 목록. 이미 닫힌 residual row를 current queue에서 제외한다.",
    )
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-md", required=True, type=Path)
    parser.add_argument("--fail-on-validation-issue", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    exclude_post_ids = {
        int(item.strip())
        for item in str(args.exclude_post_ids or "").split(",")
        if item.strip()
    }
    include_priorities = {
        item.strip()
        for item in str(args.include_triage_priorities or "").split(",")
        if item.strip()
    }
    unreviewed_rows: list[dict[str, Any]] = []
    if args.collateral_triage and include_priorities:
        triage = load_json(args.collateral_triage)
        triage_rows = triage.get("rows") if isinstance(triage.get("rows"), list) else []
        unreviewed_rows = [
            row
            for row in triage_rows
            if isinstance(row, dict)
            and row.get("is_regression") is True
            and str(row.get("priority") or "") in include_priorities
        ]
    queue = build_residual_queue(
        load_json(args.combined_review),
        queue_id=args.queue_id,
        exclude_post_ids=exclude_post_ids,
        unreviewed_regression_rows=unreviewed_rows,
    )
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(queue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(queue, args.output_md)
    if args.fail_on_validation_issue and queue["summary"]["validation_issue_count"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
