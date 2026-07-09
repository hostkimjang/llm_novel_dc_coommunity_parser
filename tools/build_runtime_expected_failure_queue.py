from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


SCOPE_OR_NONWORK_MARKERS = {
    "context_only",
    "scope_context_only",
    "scope_not_current_work",
    "scope_unknown",
    "row_discussion_missing",
    "nonwork",
    "nonwork_or_noise_context",
    "community_banter",
    "scope_platform_meta_nonwork",
    "non_novel_discourse",
    "exact_alias_candidate_preserved_without_work_discussion",
    "image_ocr_without_title_anchor",
    "unresolved_body_character_work_anchor",
}

SUPPORT_REPAIR_MARKERS = {
    "batch_alias_public_title_bridge",
    "body_verified_character_work_competes_with_resolved_public_title",
    "blocked_candidate_scope_inferred_from_search_evidence",
    "candidate_set_rebuild_required",
    "character_bridge_variance_hold",
    "direct_image_work_surface_bridge",
    "llm_only_sentence_candidate_pruned",
    "ocr_catalog_official_title",
    "official_detail_url_recovered_from_search_evidence",
    "official_detail_url_title_mismatch_publish_blocked",
    "official_title_exists",
    "official_url_recall_candidate_preserved",
    "official_url_recall_candidate_source_preserved",
    "official_url_withheld_by_title_mismatch",
    "serialized_public_identity_scrubbed",
    "title_led_alias_contextual_official_detail_competes",
    "url_title_mismatch",
}


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def _counter_to_dict(counter: Counter[str]) -> dict[str, int]:
    return {key: counter[key] for key in sorted(counter)}


def _reason_set(row: dict[str, Any], key: str = "reason_codes") -> set[str]:
    value = row.get(key) or []
    if not isinstance(value, list):
        value = [value]
    return {str(item or "").strip() for item in value if str(item or "").strip()}


def _action_list(*actions: str) -> list[str]:
    out: list[str] = []
    for action in actions:
        if action and action not in out:
            out.append(action)
    return out


def _add_search_actions(row: dict[str, Any], actions: list[str]) -> tuple[list[str], bool, bool]:
    search_status = row.get("search_status")
    search_status_text = str(search_status) if search_status is not None else "None"
    unrecovered = int(row.get("search_unrecovered_degraded") or 0)
    degraded = int(row.get("search_degraded") or 0)
    has_unrecovered = unrecovered > 0
    missing_search = search_status is None or search_status_text == "None"
    if has_unrecovered or search_status_text == "SEARCH_DEGRADED":
        actions = _action_list(*actions, "search_degraded_or_timeout_replay_required")
    if missing_search and degraded == 0:
        actions = _action_list(*actions, "search_evidence_missing_review_required")
    return actions, has_unrecovered, missing_search


def _raise_priority(current: str, target: str) -> str:
    order = {"P0": 0, "P1": 1, "P2": 2}
    if order.get(target, 99) < order.get(current, 99):
        return target
    return current


def classify_expected_failure(row: dict[str, Any]) -> dict[str, Any]:
    status = str(row.get("audit_status") or "").strip()
    expected_title = row.get("expected_title")
    actual_title = row.get("actual_title")
    reasons = _reason_set(row)
    actions: list[str]

    if status == "FAIL_SAFE_RESOLVED_TITLE_MISMATCH":
        actions = ["canonical_variant_or_wrong_work_review_required"]
        review_label = "HOLD"
        priority = "P0"
        owner_mode = "SOURCE_NATIVE_OR_BLIND_CANONICAL_REVIEW"
        rationale = (
            "Runtime은 safe_resolved/publish까지 갔지만 expected title과 실제 public title이 다르다. "
            "정당 variant인지 wrong-work인지 blind/source-native review로 먼저 확정해야 한다."
        )
        close_condition = "canonical variant 또는 wrong-work 판정 뒤에만 expected gate를 닫는다."
    elif status == "FAIL_VARIANT_COMPACT_MATCH_ONLY":
        actions = ["spacing_or_canonical_variant_policy_review_required"]
        review_label = "HOLD"
        priority = "P1"
        owner_mode = "CANONICAL_VARIANT_POLICY_REVIEW"
        rationale = (
            "공백 제거 compact match만 통과했다. 표기 variant 허용 범위를 정책으로 확정하기 전에는 "
            "exact safe_resolved로 계산하지 않는다."
        )
        close_condition = "spacing/canonical policy가 해당 표기를 정당 variant로 확정해야 한다."
    elif status == "FAIL_RUNTIME_PROMOTION_BLOCKED" and actual_title and actual_title == expected_title:
        actions = [
            "blocked_expected_title_trace_review_required",
            "shared_gate_runtime_block_repair_required",
        ]
        review_label = "REPROCESS"
        priority = "P0"
        owner_mode = "CODE_OR_RUNTIME_PROMOTION_GATE_REPAIR"
        rationale = (
            "실제 title은 expected와 같지만 promotion gate가 candidate_only로 막았다. "
            "publish_contract_trace와 hard-hold reason을 단건이 아니라 shared gate에서 수렴시켜야 한다."
        )
        close_condition = "같은 입력 runtime replay에서 같은 title/url safe_resolved와 publication contract 0 violation을 확인한다."
    elif status == "FAIL_RUNTIME_PROMOTION_BLOCKED" and actual_title and actual_title != expected_title:
        actions = [
            "blocked_title_mismatch_source_native_review_required",
            "canonical_variant_or_wrong_work_review_required",
        ]
        review_label = "HOLD"
        priority = "P0"
        owner_mode = "SOURCE_NATIVE_OR_BLIND_CANONICAL_REVIEW"
        rationale = (
            "promotion은 막혔지만 actual title 후보가 expected와 다르다. gate 완화 전에 "
            "정답 후보와 경쟁 후보의 current-work 근거를 다시 확인해야 한다."
        )
        close_condition = "blind/source-native review가 expected, actual, hold 중 하나를 확정한다."
    elif status == "FAIL_RUNTIME_PROMOTION_BLOCKED" and reasons & SCOPE_OR_NONWORK_MARKERS and not reasons & SUPPORT_REPAIR_MARKERS:
        actions = ["source_native_scope_or_nonwork_hold_review_required"]
        review_label = "HOLD"
        priority = "P2"
        owner_mode = "POLICY_OR_SOURCE_NATIVE_REVIEW"
        rationale = (
            "current-work direct bridge가 닫히지 않았거나 nonwork/context-only 근거가 남았다. "
            "하드홀드 완화가 아니라 source-native/policy review가 먼저다."
        )
        close_condition = "current-work direct bridge가 확인되기 전에는 public publish를 열지 않는다."
    elif status == "FAIL_RUNTIME_PROMOTION_BLOCKED":
        actions = ["shared_gate_runtime_block_repair_required"]
        review_label = "REPROCESS"
        priority = "P1"
        owner_mode = "CODE_OR_RUNTIME_PROMOTION_GATE_REPAIR"
        rationale = (
            "Projection은 safe_resolved였지만 runtime에서는 promotion_blocked로 남았다. "
            "candidate preservation, direct support, hard-hold reason을 shared gate에서 다시 배선한다."
        )
        close_condition = "재실행에서 actionable queue가 줄고 동일 packet safe_resolved가 단조 비감소해야 한다."
    else:
        actions = ["manual_expected_failure_review_required"]
        review_label = "HOLD"
        priority = "P2"
        owner_mode = "MANUAL_REVIEW"
        rationale = "알 수 없는 expected audit failure status다. 수동 review가 필요하다."
        close_condition = "수동 review가 runtime replay, source-native review, policy hold 중 하나로 확정해야 한다."

    actions, has_unrecovered_search, missing_search = _add_search_actions(row, actions)
    if has_unrecovered_search:
        priority = _raise_priority(priority, "P0")
    elif missing_search:
        priority = _raise_priority(priority, "P1")

    return {
        "review_label": review_label,
        "priority": priority,
        "owner_mode": owner_mode,
        "actions": actions,
        "rationale_ko": rationale,
        "close_condition": close_condition,
    }


def _expected_failure_entry(
    row: dict[str, Any],
    classification: dict[str, Any],
    source_expected_audit: str | None,
    queue_id: str,
) -> dict[str, Any]:
    return {
        "post_id": row.get("post_id"),
        "order": row.get("order"),
        "source_kind": "loop489_expected_audit_failure",
        "audit_status": row.get("audit_status"),
        "review_label": classification["review_label"],
        "priority": classification["priority"],
        "owner_mode": classification["owner_mode"],
        "actions": classification["actions"],
        "expected_title": row.get("expected_title"),
        "actual_title": row.get("actual_title"),
        "actual_url": row.get("actual_url"),
        "projected_status": row.get("projected_status"),
        "safe_resolved": row.get("safe_resolved") is True,
        "publish_allowed": row.get("publish_allowed") is True,
        "candidate_ledger_status": row.get("candidate_ledger_status"),
        "promotion_status": row.get("promotion_status"),
        "title_resolution_state": row.get("title_resolution_state"),
        "work_resolution": row.get("work_resolution"),
        "discussion_type": row.get("discussion_type"),
        "search_status": row.get("search_status"),
        "search_degraded": int(row.get("search_degraded") or 0),
        "search_unrecovered_degraded": int(row.get("search_unrecovered_degraded") or 0),
        "exact_title_match": row.get("exact_title_match") is True,
        "compact_title_match": row.get("compact_title_match") is True,
        "reason_codes": sorted(_reason_set(row)),
        "rationale_ko": classification["rationale_ko"],
        "close_condition": classification["close_condition"],
        "evidence_refs": [
            f"{source_expected_audit or queue_id}#post_id={row.get('post_id')}"
        ],
    }


def _projection_still_blocked_entries(
    projection: dict[str, Any] | None,
    *,
    source_projection_path: str | None,
) -> list[dict[str, Any]]:
    if not projection:
        return []
    rows = projection.get("rows") or []
    if not isinstance(rows, list):
        return []
    entries: list[dict[str, Any]] = []
    projection_id = projection.get("projection_id") or source_projection_path or "projection"
    for row in rows:
        if not isinstance(row, dict) or row.get("projected_status") != "promotion_blocked":
            continue
        actions = _action_list(
            *(str(action) for action in (row.get("source_actions") or []) if str(action)),
            "candidate_set_rebuild_required",
            "source_native_scope_or_nonwork_hold_review_required",
        )
        entries.append(
            {
                "post_id": row.get("post_id"),
                "order": None,
                "source_kind": "loop489_projection_still_blocked",
                "audit_status": "PROJECTION_STILL_BLOCKED",
                "review_label": "HOLD",
                "priority": "P2",
                "owner_mode": "CANDIDATE_SET_REBUILD_OR_SOURCE_NATIVE_REVIEW",
                "actions": actions,
                "expected_title": row.get("selected_title"),
                "actual_title": row.get("projected_title"),
                "actual_url": row.get("projected_url"),
                "projected_status": row.get("projected_status"),
                "safe_resolved": False,
                "publish_allowed": False,
                "candidate_ledger_status": "promotion_blocked",
                "promotion_status": "candidate_only",
                "title_resolution_state": None,
                "work_resolution": None,
                "discussion_type": None,
                "search_status": None,
                "search_degraded": 0,
                "search_unrecovered_degraded": 0,
                "exact_title_match": False,
                "compact_title_match": False,
                "reason_codes": sorted(_reason_set(row, key="projected_reasons")),
                "rationale_ko": (
                    row.get("rationale_ko")
                    or "Projection 단계에서도 후보 집합이 닫히지 않아 candidate rebuild와 source-native review가 필요하다."
                ),
                "close_condition": "후보 재구성 뒤 shared gate projection과 runtime replay에서 같은 packet의 수렴을 확인한다.",
                "evidence_refs": [
                    f"{projection_id}#post_id={row.get('post_id')}"
                ]
                + list(row.get("evidence_refs") or []),
            }
        )
    return entries


def build_failure_queue(
    expected_audit: dict[str, Any],
    *,
    projection: dict[str, Any] | None = None,
    generated_at: str | None = None,
    queue_id: str = "runtime_expected_failure_action_queue",
    source_expected_audit: str | None = None,
    source_projection_path: str | None = None,
) -> dict[str, Any]:
    rows = expected_audit.get("rows") or []
    if not isinstance(rows, list):
        raise ValueError("expected_audit.rows must be a list")

    validation_issues: list[dict[str, Any]] = []
    out_rows: list[dict[str, Any]] = []
    passed_rows: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    label_counts: Counter[str] = Counter()
    priority_counts: Counter[str] = Counter()
    owner_counts: Counter[str] = Counter()
    action_counts: Counter[str] = Counter()
    source_kind_counts: Counter[str] = Counter()
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    search_unrecovered_rows = 0
    search_unrecovered_total = 0

    for row in rows:
        if not isinstance(row, dict):
            validation_issues.append({"code": "non_object_expected_audit_row"})
            continue
        status = str(row.get("audit_status") or "").strip()
        status_counts[status] += 1
        if status == "PASS_EXACT_SAFE_RESOLVED":
            passed_rows.append(row)
            continue
        classification = classify_expected_failure(row)
        entry = _expected_failure_entry(row, classification, source_expected_audit, queue_id)
        out_rows.append(entry)
        unrecovered = int(entry.get("search_unrecovered_degraded") or 0)
        if unrecovered:
            search_unrecovered_rows += 1
            search_unrecovered_total += unrecovered

    projection_entries = _projection_still_blocked_entries(
        projection,
        source_projection_path=source_projection_path,
    )
    out_rows.extend(projection_entries)

    for entry in out_rows:
        label_counts[str(entry["review_label"])] += 1
        priority_counts[str(entry["priority"])] += 1
        owner_counts[str(entry["owner_mode"])] += 1
        source_kind_counts[str(entry["source_kind"])] += 1
        for action in entry.get("actions") or []:
            action_counts[str(action)] += 1
            groups[str(action)].append(entry)

    action_groups: list[dict[str, Any]] = []
    for action in sorted(groups):
        group_rows = groups[action]
        action_groups.append(
            {
                "action": action,
                "row_count": len(group_rows),
                "priority_counts": _counter_to_dict(Counter(str(item["priority"]) for item in group_rows)),
                "label_counts": _counter_to_dict(Counter(str(item["review_label"]) for item in group_rows)),
                "audit_status_counts": _counter_to_dict(Counter(str(item["audit_status"]) for item in group_rows)),
                "owner_modes": _counter_to_dict(Counter(str(item["owner_mode"]) for item in group_rows)),
                "post_ids": [item.get("post_id") for item in group_rows],
                "sample_rows": group_rows[:8],
            }
        )

    summary = expected_audit.get("summary") or {}
    expected_row_count = summary.get("row_count")
    if expected_row_count is not None and int(expected_row_count) != len(rows):
        validation_issues.append(
            {
                "code": "expected_audit_row_count_mismatch",
                "expected": expected_row_count,
                "actual": len(rows),
            }
        )
    expected_fail_count = summary.get("exact_safe_resolved_fail")
    actual_fail_count = len(rows) - len(passed_rows)
    if expected_fail_count is not None and int(expected_fail_count) != actual_fail_count:
        validation_issues.append(
            {
                "code": "expected_audit_fail_count_mismatch",
                "expected": expected_fail_count,
                "actual": actual_fail_count,
            }
        )

    return {
        "report_type": "runtime_expected_failure_action_queue",
        "queue_id": queue_id,
        "generated_at": generated_at or datetime.now().replace(microsecond=0).isoformat(),
        "source_expected_audit": source_expected_audit,
        "source_projection_path": source_projection_path,
        "source_run_id": expected_audit.get("run_id"),
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "gate": "NO-GO" if validation_issues else "REVIEW-LOCKED",
        "summary": {
            "expected_rows": len(rows),
            "passed_rows_excluded": len(passed_rows),
            "failed_rows": actual_fail_count,
            "projection_still_blocked_rows": len(projection_entries),
            "action_queue_rows": len(out_rows),
            "source_audit_status_counts": _counter_to_dict(status_counts),
            "source_kind_counts": _counter_to_dict(source_kind_counts),
            "label_counts": _counter_to_dict(label_counts),
            "priority_counts": _counter_to_dict(priority_counts),
            "owner_mode_counts": _counter_to_dict(owner_counts),
            "action_counts": _counter_to_dict(action_counts),
            "action_group_count": len(action_groups),
            "search_unrecovered_degraded_rows": search_unrecovered_rows,
            "search_unrecovered_degraded_total": search_unrecovered_total,
            "validation_issue_count": len(validation_issues),
        },
        "validation_issues": validation_issues,
        "action_groups": action_groups,
        "rows": out_rows,
        "approval_boundary": {
            "queue_is_not_approval": True,
            "loop489_runtime_health_go_is_not_semantic_approval": True,
            "publication_contract_go_is_not_expected_title_approval": True,
            "full375_collateral_remains_no_go_until_replayed": True,
            "completion_gate": "adjusted full375 collateral GO + full_scan path",
        },
    }


def write_markdown(queue: dict[str, Any], path: Path) -> None:
    summary = queue["summary"]
    lines = [
        f"# {queue.get('queue_id')}",
        "",
        "## 요약",
        "",
        f"- gate: `{queue.get('gate')}`",
        f"- expected_rows: `{summary.get('expected_rows')}`",
        f"- passed_rows_excluded: `{summary.get('passed_rows_excluded')}`",
        f"- failed_rows: `{summary.get('failed_rows')}`",
        f"- projection_still_blocked_rows: `{summary.get('projection_still_blocked_rows')}`",
        f"- action_queue_rows: `{summary.get('action_queue_rows')}`",
        f"- source_audit_status_counts: `{summary.get('source_audit_status_counts')}`",
        f"- label_counts: `{summary.get('label_counts')}`",
        f"- priority_counts: `{summary.get('priority_counts')}`",
        f"- owner_mode_counts: `{summary.get('owner_mode_counts')}`",
        f"- search_unrecovered_degraded_rows/total: `{summary.get('search_unrecovered_degraded_rows')}/{summary.get('search_unrecovered_degraded_total')}`",
        f"- validation_issue_count: `{summary.get('validation_issue_count')}`",
        "- approval: `false`",
        "- semantic_quality: `REVIEW-LOCKED`",
        "",
        "## 승인 경계",
        "",
        "- 이 큐는 Loop489 runtime expected-audit 실패를 다음 작업 단위로 나눈 산출물이며 approval이 아니다.",
        "- Runtime completion, publication contract `GO`, expected-audit queue 정리는 full375 collateral 승인이 아니다.",
            "- 완료 기준은 계속 `adjusted full375 collateral GO + full_scan 경로 정의`다.",
        "",
        "## Action groups",
        "",
    ]
    for group in queue.get("action_groups") or []:
        sample = ", ".join(str(post_id) for post_id in group.get("post_ids", [])[:12])
        lines.extend(
            [
                f"### {group.get('action')}",
                "",
                f"- row_count: `{group.get('row_count')}`",
                f"- priority_counts: `{group.get('priority_counts')}`",
                f"- label_counts: `{group.get('label_counts')}`",
                f"- audit_status_counts: `{group.get('audit_status_counts')}`",
                f"- owner_modes: `{group.get('owner_modes')}`",
                f"- sample_post_ids: `{sample}`",
                "",
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    while lines and lines[-1] == "":
        lines.pop()
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an action queue from runtime expected-audit failures.")
    parser.add_argument("--expected-audit", required=True, type=Path)
    parser.add_argument("--projection", type=Path, default=None)
    parser.add_argument("--queue-id", default="runtime_expected_failure_action_queue")
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-md", required=True, type=Path)
    parser.add_argument("--fail-on-validation-issue", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    projection = load_json(args.projection) if args.projection else None
    queue = build_failure_queue(
        load_json(args.expected_audit),
        projection=projection,
        queue_id=args.queue_id,
        source_expected_audit=args.expected_audit.as_posix(),
        source_projection_path=args.projection.as_posix() if args.projection else None,
    )
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(queue, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    write_markdown(queue, args.output_md)
    if args.fail_on_validation_issue and queue["summary"]["validation_issue_count"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
