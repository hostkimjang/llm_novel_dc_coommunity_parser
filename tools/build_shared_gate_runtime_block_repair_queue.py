from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


REPAIR_ACTIONS = {
    "prior_runtime_promotion_block_repair_required",
    "shared_gate_runtime_block_repair_required",
}

SCOPE_OR_NONWORK_MARKERS = {
    "context_only",
    "scope_context_only",
    "scope_not_current_work",
    "scope_unknown",
    "scope_unclassified",
    "row_discussion_missing",
    "nonwork",
    "nonwork_or_noise_context",
    "community_banter",
    "scope_platform_meta_nonwork",
    "non_novel_discourse",
    "exact_alias_candidate_preserved_without_work_discussion",
    "image_ocr_without_title_anchor",
    "unresolved_body_character_work_anchor",
    "missing_body_work_bridge",
}

CANDIDATE_PRESERVATION_MARKERS = {
    "blocked_candidate_scope_inferred_from_final_contract",
    "blocked_candidate_scope_inferred_from_search_evidence",
    "llm_only_sentence_candidate_pruned",
    "missing_direct_candidate_title",
    "official_url_recall_candidate_preserved",
    "official_url_recall_candidate_source_preserved",
    "serialized_public_identity_scrubbed",
    "serialized_public_identity_shared_gate_restored",
}

IMAGE_OR_ALIAS_MARKERS = {
    "alias_bridge",
    "batch_alias_public_title_bridge",
    "direct_image_work_surface_bridge",
    "ocr_catalog_official_title",
    "title_acceptance_accept",
    "title_led_consumption_bridge",
    "unverified_promoted_image_work_title_without_official_support",
    "verified_alias_title_only_publication",
}

TITLE_URL_OR_VARIANT_MARKERS = {
    "body_verified_character_work_competes_with_resolved_public_title",
    "character_bridge_variance_hold",
    "character_title_collision",
    "competing_candidate_present",
    "official_detail_url_title_mismatch_publish_blocked",
    "official_url_withheld_by_title_mismatch",
    "promoted_image_work_title_conflicts_with_public_title",
    "title_led_alias_contextual_official_detail_competes",
    "url_title_mismatch",
}

OFFICIAL_SUPPORT_MARKERS = {
    "official_detail_url",
    "official_detail_url_recovered_from_search_evidence",
    "official_title_exists",
}

PROJECTED_CURRENT_WORK_MARKERS = {
    "source_native_review_current_work",
    "scope_current_work",
    "row_discusses_work_as_work",
}

RUNTIME_CURRENT_WORK_MARKERS = {
    "scope_current_work",
    "row_discusses_work_as_work",
}

RUNTIME_NONCURRENT_MARKERS = {
    "context_only",
    "scope_context_only",
    "scope_not_current_work",
    "scope_unknown",
    "scope_unclassified",
    "row_discussion_missing",
    "nonwork",
    "nonwork_or_noise_context",
    "community_banter",
    "scope_platform_meta_nonwork",
    "non_novel_discourse",
}


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def _counter_to_dict(counter: Counter[str]) -> dict[str, int]:
    return {key: counter[key] for key in sorted(counter)}


def _actions(row: dict[str, Any]) -> list[str]:
    value = row.get("actions") or []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    return []


def _reason_set(row: dict[str, Any]) -> set[str]:
    value = row.get("prior_runtime_reason_codes") or row.get("reason_codes") or []
    if not isinstance(value, list):
        value = [value]
    return {str(item or "").strip() for item in value if str(item or "").strip()}


def _projected_reason_set(row: dict[str, Any]) -> set[str]:
    value = row.get("projected_reasons") or []
    if not isinstance(value, list):
        value = [value]
    return {str(item or "").strip() for item in value if str(item or "").strip()}


def _repair_rows(queue: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows = queue.get("rows") or []
    if not isinstance(rows, list):
        raise ValueError("queue.rows must be a list")
    selected: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            issues.append({"code": "non_object_queue_row", "index": idx})
            continue
        action_set = set(_actions(row))
        if not action_set.intersection(REPAIR_ACTIONS):
            continue
        if str(row.get("prior_runtime_audit_status") or "") != "FAIL_RUNTIME_PROMOTION_BLOCKED":
            issues.append(
                {
                    "code": "repair_action_without_prior_promotion_block",
                    "post_id": row.get("post_id"),
                    "prior_runtime_audit_status": row.get("prior_runtime_audit_status"),
                }
            )
        selected.append(row)
    return selected, issues


def _search_gate(row: dict[str, Any]) -> str:
    status = row.get("prior_runtime_search_status")
    text = str(status) if status is not None else "None"
    if text == "ok":
        return "SEARCH_OK"
    if text == "SEARCH_DEGRADED_RECOVERED":
        return "SEARCH_RECOVERED_CONDITIONAL"
    if text == "SEARCH_DEGRADED":
        return "SEARCH_BLIND_BLOCKER"
    return "SEARCH_EVIDENCE_MISSING"


def _facets_for(reasons: set[str], search_gate: str) -> list[str]:
    facets: list[str] = ["public_identity_serialization_trace"]
    if reasons & SCOPE_OR_NONWORK_MARKERS:
        facets.append("scope_or_nonwork_monotonicity")
    if reasons & CANDIDATE_PRESERVATION_MARKERS:
        facets.append("candidate_preservation_or_scrub")
    if reasons & IMAGE_OR_ALIAS_MARKERS:
        facets.append("image_or_alias_anchor_contract")
    if reasons & TITLE_URL_OR_VARIANT_MARKERS:
        facets.append("title_url_or_variant_trace")
    if reasons & OFFICIAL_SUPPORT_MARKERS:
        facets.append("official_support_reconciliation")
    if search_gate != "SEARCH_OK":
        facets.append("search_blind_or_missing_preflight")
    return facets


def _scope_claim(reasons: set[str], *, projected: bool = False) -> str:
    if projected:
        if reasons & PROJECTED_CURRENT_WORK_MARKERS:
            return "PROJECTED_CURRENT_WORK"
        return "PROJECTED_SCOPE_UNSPECIFIED"
    if reasons & RUNTIME_NONCURRENT_MARKERS:
        return "RUNTIME_NONCURRENT_OR_CONTEXT_ONLY"
    if reasons & RUNTIME_CURRENT_WORK_MARKERS:
        return "RUNTIME_CURRENT_WORK"
    return "RUNTIME_SCOPE_UNSPECIFIED"


def _has_projection_runtime_scope_conflict(projected_reasons: set[str], runtime_reasons: set[str]) -> bool:
    return bool(projected_reasons & PROJECTED_CURRENT_WORK_MARKERS) and bool(
        runtime_reasons & RUNTIME_NONCURRENT_MARKERS
    )


def _primary_lane(reasons: set[str]) -> str:
    if reasons & TITLE_URL_OR_VARIANT_MARKERS:
        return "title_url_or_variant_trace_repair"
    if reasons & IMAGE_OR_ALIAS_MARKERS:
        return "image_or_alias_anchor_contract_repair"
    if reasons & SCOPE_OR_NONWORK_MARKERS:
        return "scope_or_nonwork_monotonicity_repair"
    if reasons & CANDIDATE_PRESERVATION_MARKERS:
        return "candidate_preservation_or_scrub_repair"
    if "promotion_blocked" in reasons:
        return "promotion_trace_introspection_required"
    return "manual_shared_gate_repair_review"


def _lane_action(lane: str) -> str:
    return f"{lane}_required" if not lane.endswith("_required") else lane


def _close_condition(lane: str) -> str:
    if lane == "title_url_or_variant_trace_repair":
        return "title/url mismatch, competing candidate, variant reason이 publish_contract_trace와 can_publish_title에서 같은 결정으로 수렴해야 한다."
    if lane == "image_or_alias_anchor_contract_repair":
        return "이미지/OCR/별칭 앵커가 direct work anchor인지 검증하고, 미검증 앵커는 candidate_only로 보존해야 한다."
    if lane == "scope_or_nonwork_monotonicity_repair":
        return "current-work 직접 브리지가 확인되기 전에는 hard-hold를 완화하지 않고, 확인된 경우 _post_discusses_work_as_work 경유로만 publish를 연다."
    if lane == "candidate_preservation_or_scrub_repair":
        return "supported candidate가 serialized public identity에서 사라지지 않고 candidate ledger와 publish trace에 보존되어야 한다."
    if lane == "promotion_trace_introspection_required":
        return "promotion_blocked reason이 publish_contract_trace에 충분히 노출되어 다음 repair lane으로 재분류되어야 한다."
    return "수동 review가 publish, candidate_only, repair 중 하나를 확정해야 한다."


def _contract_tests(lane: str) -> list[str]:
    common = [
        "runtime replay는 수리 전 금지한다.",
        "수리 후 같은 packet safe_resolved는 단조 비감소해야 한다.",
        "full375 collateral 재확인 전 approval을 열지 않는다.",
    ]
    lane_tests = {
        "title_url_or_variant_trace_repair": [
            "publish_contract_trace와 can_publish_title이 title/url mismatch를 같은 reason code로 노출한다.",
            "공식 URL과 public title이 불일치하면 safe_resolved가 아니라 candidate_only로 보존한다.",
        ],
        "image_or_alias_anchor_contract_repair": [
            "검증된 이미지/OCR/별칭 앵커만 _post_discusses_work_as_work 경유로 current-work bridge를 연다.",
            "image_ocr_without_title_anchor 계열은 직접 제목 앵커 없이는 publish를 열지 않는다.",
        ],
        "scope_or_nonwork_monotonicity_repair": [
            "_has_verified_contextual_alias_work_bridge는 _post_discusses_work_as_work를 경유한다.",
            "scope_not_current_work/context_only/nonwork reason은 direct work bridge 없이는 monotonic hard-hold를 유지한다.",
        ],
        "candidate_preservation_or_scrub_repair": [
            "llm-only sentence pruning 뒤에도 source-native supported candidate는 candidate ledger에 보존된다.",
            "serialized_public_identity_scrubbed reason은 public identity와 candidate ledger의 불일치로 audit 가능해야 한다.",
        ],
        "promotion_trace_introspection_required": [
            "promotion_blocked 단독 reason은 다음 repair lane으로 재분류할 수 있을 만큼 trace detail을 남긴다.",
        ],
    }
    return lane_tests.get(lane, ["manual review packet이 next action을 확정한다."]) + common


def classify_repair_row(row: dict[str, Any]) -> dict[str, Any]:
    reasons = _reason_set(row)
    projected_reasons = _projected_reason_set(row)
    search_gate = _search_gate(row)
    lane = _primary_lane(reasons)
    facets = _facets_for(reasons, search_gate)
    scope_conflict = _has_projection_runtime_scope_conflict(projected_reasons, reasons)
    if scope_conflict:
        facets.append("projection_runtime_scope_conflict")
    actions = [
        _lane_action(lane),
        "publish_contract_trace_contract_test_required",
        "runtime_replay_after_contract_repair",
        "full375_collateral_recheck_after_repair",
    ]
    if scope_conflict:
        actions.insert(1, "projection_runtime_scope_reconciliation_required")
    if search_gate in {"SEARCH_BLIND_BLOCKER", "SEARCH_EVIDENCE_MISSING"}:
        actions.insert(1, "search_blind_preflight_required")
    elif search_gate == "SEARCH_RECOVERED_CONDITIONAL":
        actions.insert(1, "search_recovered_conditional_tag_required")

    return {
        "post_id": row.get("post_id"),
        "selected_title": row.get("selected_title"),
        "projected_title": row.get("projected_title"),
        "source_native_verdict": row.get("source_native_verdict"),
        "prior_runtime_audit_status": row.get("prior_runtime_audit_status"),
        "prior_runtime_search_status": row.get("prior_runtime_search_status"),
        "search_gate": search_gate,
        "projected_scope_claim": _scope_claim(projected_reasons, projected=True),
        "runtime_scope_claim": _scope_claim(reasons),
        "projection_runtime_scope_conflict": scope_conflict,
        "primary_repair_lane": lane,
        "repair_facets": facets,
        "reason_codes": sorted(reasons),
        "projected_reasons": sorted(projected_reasons),
        "runtime_replay_allowed": False,
        "runtime_replay_blocker": "contract_repair_required_before_replay",
        "actions": actions,
        "close_condition": _close_condition(lane),
        "required_contract_tests": _contract_tests(lane),
        "evidence_refs": list(row.get("evidence_refs") or [])
        + [f"prior_runtime_expected_audit#post_id={row.get('post_id')}"],
    }


def build_repair_queue(
    source_queue: dict[str, Any],
    *,
    queue_id: str,
    generated_at: str | None = None,
) -> dict[str, Any]:
    rows, validation_issues = _repair_rows(source_queue)
    out_rows = [classify_repair_row(row) for row in rows]
    primary_counts = Counter(str(row["primary_repair_lane"]) for row in out_rows)
    facet_counts: Counter[str] = Counter()
    reason_counts: Counter[str] = Counter()
    search_counts = Counter(str(row["search_gate"]) for row in out_rows)
    action_counts: Counter[str] = Counter()
    scope_conflict_counts = Counter(
        "conflict" if row.get("projection_runtime_scope_conflict") else "no_conflict" for row in out_rows
    )
    lane_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in out_rows:
        lane_groups[str(row["primary_repair_lane"])].append(row)
        for facet in row["repair_facets"]:
            facet_counts[str(facet)] += 1
        for reason in row["reason_codes"]:
            reason_counts[str(reason)] += 1
        for action in row["actions"]:
            action_counts[str(action)] += 1

    action_groups: list[dict[str, Any]] = []
    for lane in sorted(lane_groups):
        group_rows = lane_groups[lane]
        action_groups.append(
            {
                "primary_repair_lane": lane,
                "row_count": len(group_rows),
                "search_gate_counts": _counter_to_dict(Counter(str(row["search_gate"]) for row in group_rows)),
                "facet_counts": _counter_to_dict(
                    Counter(facet for row in group_rows for facet in row["repair_facets"])
                ),
                "projection_runtime_scope_conflict_rows": sum(
                    1 for row in group_rows if row.get("projection_runtime_scope_conflict")
                ),
                "post_ids": [row.get("post_id") for row in group_rows],
                "sample_rows": group_rows[:8],
            }
        )

    return {
        "report_type": "shared_gate_runtime_block_repair_queue",
        "queue_id": queue_id,
        "generated_at": generated_at or datetime.now().replace(microsecond=0).isoformat(),
        "source_queue_id": source_queue.get("queue_id"),
        "source_queue_path": source_queue.get("source_projection_path") or "",
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "gate": "NO-GO" if validation_issues else "REVIEW-LOCKED",
        "summary": {
            "source_queue_rows": len(source_queue.get("rows") or []),
            "repair_rows": len(out_rows),
            "runtime_replay_allowed_rows": sum(1 for row in out_rows if row.get("runtime_replay_allowed") is True),
            "primary_repair_lane_counts": _counter_to_dict(primary_counts),
            "repair_facet_counts": _counter_to_dict(facet_counts),
            "search_gate_counts": _counter_to_dict(search_counts),
            "reason_counts": _counter_to_dict(reason_counts),
            "action_counts": _counter_to_dict(action_counts),
            "projection_runtime_scope_conflict_counts": _counter_to_dict(scope_conflict_counts),
            "validation_issue_count": len(validation_issues),
        },
        "stop_condition": {
            "actionable_queue_must_decrease": True,
            "same_packet_safe_resolved_must_be_monotonic_non_decreasing": True,
            "round_count_is_not_a_stop_condition": True,
        },
        "approval_boundary": {
            "repair_queue_is_not_approval": True,
            "runtime_replay_before_contract_repair_forbidden": True,
            "full375_collateral_remains_no_go": True,
            "completion_gate": "full375 collateral GO + full_scan path",
        },
        "validation_issues": validation_issues,
        "action_groups": action_groups,
        "rows": out_rows,
    }


def write_markdown(queue: dict[str, Any], path: Path) -> None:
    summary = queue["summary"]
    lines = [
        f"# {queue['queue_id']}",
        "",
        "## 요약",
        "",
        f"- source_queue_id: `{queue.get('source_queue_id')}`",
        f"- gate: `{queue.get('gate')}`",
        f"- repair_rows: `{summary.get('repair_rows')}`",
        f"- runtime_replay_allowed_rows: `{summary.get('runtime_replay_allowed_rows')}`",
        f"- primary_repair_lane_counts: `{summary.get('primary_repair_lane_counts')}`",
        f"- repair_facet_counts: `{summary.get('repair_facet_counts')}`",
        f"- search_gate_counts: `{summary.get('search_gate_counts')}`",
        f"- projection_runtime_scope_conflict_counts: `{summary.get('projection_runtime_scope_conflict_counts')}`",
        f"- validation_issue_count: `{summary.get('validation_issue_count')}`",
        "- approval: `false`",
        "- semantic_quality: `REVIEW-LOCKED`",
        "",
        "## 승인 경계",
        "",
        "- 이 repair queue는 runtime replay 입력이 아니다.",
        "- 수리 전 동일 packet 반복 실행을 금지한다.",
        "- search degraded 또는 missing 행은 `search-blind 조건부`를 보존한다.",
        "- 완료 기준은 계속 `full375 collateral GO + full_scan 경로 정의`다.",
        "",
        "## Repair lanes",
        "",
    ]
    for group in queue.get("action_groups") or []:
        sample = ", ".join(str(post_id) for post_id in group.get("post_ids", [])[:12])
        lines.extend(
            [
                f"### {group.get('primary_repair_lane')}",
                "",
                f"- row_count: `{group.get('row_count')}`",
                f"- search_gate_counts: `{group.get('search_gate_counts')}`",
                f"- facet_counts: `{group.get('facet_counts')}`",
                f"- projection_runtime_scope_conflict_rows: `{group.get('projection_runtime_scope_conflict_rows')}`",
                f"- sample_post_ids: `{sample}`",
                "",
            ]
        )
    lines.extend(["## 다음 조건", "", "- contract repair 뒤에만 runtime replay 후보로 되돌린다.", "- replay 뒤에는 full375 collateral을 다시 확인한다."])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8", newline="\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a repair queue for shared gate runtime promotion-block rows.")
    parser.add_argument("--queue", required=True, type=Path)
    parser.add_argument("--queue-id", default="shared_gate_runtime_block_repair_queue")
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-md", required=True, type=Path)
    parser.add_argument("--fail-on-validation-issue", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    queue = build_repair_queue(load_json(args.queue), queue_id=args.queue_id)
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
