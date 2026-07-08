from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


SOURCE_NATIVE_ACTIONS = {
    "source_native_or_blind_review_required",
    "p0_wrong_work_title_flip_review_required",
}
CANDIDATE_SET_ACTIONS = {
    "candidate_set_rebuild_required",
    "repair_after_wrong_work",
}
NO_PUBLISH_GUARD_ACTIONS = {
    "repair_unsafe_promotion",
    "intent_guard_review",
    "multi_work_guard_required",
    "nonwork_game_context_publish_block_required",
    "search_title_similarity_hard_hold_required",
    "alias_collision_guard_required",
    "canonical_alias_competition_guard_required",
    "wrong_work_or_cross_media_policy_hold_required",
    "blind_or_policy_judge_required",
}
NATIVE_WEB_IMAGE_ACTIONS = {
    "native_web_review_required",
    "image_native_review_required",
    "image_listing_multi_work_guard_required",
    "image_multi_panel_review_required",
    "image_platform_url_preference",
    "native_web_or_image_evidence_required",
    "native_web_or_image_human_review_required",
}
CANONICAL_POLICY_ACTIONS = {
    "policy_or_canonical_title_review_required",
    "canonical_title_cleanup_required",
    "title_url_or_variant_trace_repair",
    "title_surface_specificity_review_required",
    "alias_relation_review_required",
    "character_bridge_review_required",
    "native_web_or_alias_relation_review_required",
    "character_bridge_native_web_review_required",
    "official_detail_url_enrichment_required",
}
SHARED_GATE_RESTORE_ACTIONS = {
    "repair_safe_loss_restore_supported_title",
    "shared_promotion_gate_wiring_required",
}


LANE_DESCRIPTIONS = {
    "source_native_or_blind_review": "prior-compatible verdict가 없거나 INFO_MISSING이라 source-native/blind 판정을 먼저 닫는다.",
    "candidate_set_rebuild_review": "현재 후보셋이 정답 후보를 빠뜨렸거나 wrong-work 후보를 보존했으므로 candidate ledger를 재구성한다.",
    "no_publish_multiwork_guard_review": "unsafe promotion, intent guard, multi-work guard를 먼저 닫고 publish hard-hold를 유지한다.",
    "native_web_image_evidence_review": "native web, 이미지, OCR, 플랫폼 evidence를 직접 확인해야 한다.",
    "canonical_policy_cleanup_review": "canonical title, URL, variant, alias relation 정책을 정리한다.",
    "shared_gate_restore_contract_review": "source-native supported title을 shared promotion gate contract로 복원 후보화한다.",
    "manual_review": "기계 분류가 부족하므로 수동 검토로 남긴다.",
}


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _counter_to_dict(counter: Counter[str]) -> dict[str, int]:
    return {key: counter[key] for key in sorted(counter)}


def _post_id(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _index_rows(rows: list[Any]) -> dict[int, dict[str, Any]]:
    indexed: dict[int, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        post_id = _post_id(row.get("post_id"))
        if post_id is None:
            continue
        indexed[post_id] = row
    return indexed


def _source_id(payload: dict[str, Any], *, fallback: str) -> str:
    for key in ("queue_id", "dispatch_id", "accounting_id", "plan_id"):
        value = str(payload.get(key) or "").strip()
        if value:
            return value
    return fallback


def _actions(row: dict[str, Any]) -> list[str]:
    return [str(item) for item in _as_list(row.get("actions")) if str(item)]


def _merge_actions(*values: list[str]) -> list[str]:
    out: list[str] = []
    for items in values:
        for item in items:
            if item and item not in out:
                out.append(item)
    return out


def _primary_lane(row: dict[str, Any]) -> str:
    actions = set(_actions(row))
    label = str(row.get("review_label") or "")
    if actions & SOURCE_NATIVE_ACTIONS or label == "INFO_MISSING":
        return "source_native_or_blind_review"
    if actions & CANDIDATE_SET_ACTIONS:
        return "candidate_set_rebuild_review"
    if actions & NO_PUBLISH_GUARD_ACTIONS:
        return "no_publish_multiwork_guard_review"
    if actions & NATIVE_WEB_IMAGE_ACTIONS:
        return "native_web_image_evidence_review"
    if actions & CANONICAL_POLICY_ACTIONS:
        return "canonical_policy_cleanup_review"
    if actions & SHARED_GATE_RESTORE_ACTIONS:
        return "shared_gate_restore_contract_review"
    return "manual_review"


def _lane_gate(lane: str) -> str:
    if lane == "shared_gate_restore_contract_review":
        return "BLOCKED_UNTIL_SHARED_GATE_CONTRACT_APPLICATION_AND_FULL375_RECHECK"
    if lane == "native_web_image_evidence_review":
        return "BLOCKED_UNTIL_NATIVE_WEB_OR_IMAGE_EVIDENCE_REVIEW"
    if lane == "source_native_or_blind_review":
        return "BLOCKED_UNTIL_SOURCE_NATIVE_OR_BLIND_VERDICT"
    if lane == "candidate_set_rebuild_review":
        return "BLOCKED_UNTIL_CANDIDATE_SET_REBUILT_AND_CONTRACT_TESTED"
    if lane == "no_publish_multiwork_guard_review":
        return "HARD_HOLD_UNTIL_NO_PUBLISH_GUARD_REVIEW"
    if lane == "canonical_policy_cleanup_review":
        return "BLOCKED_UNTIL_CANONICAL_POLICY_CLEANUP"
    return "MANUAL_REVIEW_REQUIRED"


def build_dispatch(
    *,
    accounting: dict[str, Any],
    source_queue: dict[str, Any],
    dispatch_id: str,
    generated_at: str | None = None,
) -> dict[str, Any]:
    accounting_rows = _as_list(accounting.get("rows"))
    source_rows = _as_list(source_queue.get("rows"))
    source_by_post_id = _index_rows(source_rows)

    validation_issues: list[dict[str, Any]] = []
    ordinary_rows: list[dict[str, Any]] = []
    for row in accounting_rows:
        if not isinstance(row, dict) or not row.get("ordinary_residual_unprocessed"):
            continue
        post_id = _post_id(row.get("post_id"))
        if post_id is None:
            validation_issues.append({"code": "ordinary_row_without_post_id", "row": row})
            continue
        source = source_by_post_id.get(post_id)
        if not source:
            validation_issues.append({"code": "ordinary_row_missing_source_queue_row", "post_id": post_id})
            source = {}
        actions = _merge_actions(_actions(source), _actions(row))
        lane_input = dict(source or row)
        lane_input["actions"] = actions
        lane_input["review_label"] = row.get("review_label") or source.get("review_label")
        merged = {
            "post_id": post_id,
            "triage_bucket": row.get("triage_bucket") or source.get("triage_bucket"),
            "review_label": row.get("review_label") or source.get("review_label"),
            "source_native_verdict": row.get("source_native_verdict") or source.get("source_native_verdict"),
            "selected_title": row.get("selected_title") or source.get("selected_title"),
            "selected_option_id": row.get("selected_option_id") or source.get("selected_option_id"),
            "evidence_grade": source.get("evidence_grade"),
            "loop546_transition": row.get("loop546_transition") or source.get("loop546_transition"),
            "actions": actions,
            "primary_lane": _primary_lane(source or row),
            "lane_gate": "",
            "publish_allowed": False,
            "runtime_replay_allowed": False,
            "full_scan_approval": False,
            "contract_accounting_state": row.get("contract_accounting_state"),
            "contract_accounting_effect": row.get("contract_accounting_effect"),
            "rationale_ko": row.get("rationale_ko") or source.get("rationale_ko"),
            "evidence_refs": source.get("evidence_refs") or row.get("evidence_refs") or [],
        }
        merged["primary_lane"] = _primary_lane(lane_input)
        merged["lane_gate"] = _lane_gate(str(merged["primary_lane"]))
        ordinary_rows.append(merged)

    ordinary_rows.sort(key=lambda item: (str(item.get("primary_lane")), str(item.get("triage_bucket")), int(item["post_id"])))

    label_counts: Counter[str] = Counter()
    bucket_counts: Counter[str] = Counter()
    transition_counts: Counter[str] = Counter()
    action_counts: Counter[str] = Counter()
    lane_counts: Counter[str] = Counter()
    lane_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in ordinary_rows:
        label_counts[str(row.get("review_label"))] += 1
        bucket_counts[str(row.get("triage_bucket"))] += 1
        transition_counts[str(row.get("loop546_transition"))] += 1
        lane_counts[str(row.get("primary_lane"))] += 1
        lane_groups[str(row.get("primary_lane"))].append(row)
        for action in row.get("actions") or []:
            action_counts[str(action)] += 1

    groups: list[dict[str, Any]] = []
    for lane in sorted(lane_groups):
        rows = lane_groups[lane]
        groups.append(
            {
                "lane": lane,
                "description_ko": LANE_DESCRIPTIONS.get(lane, ""),
                "lane_gate": _lane_gate(lane),
                "row_count": len(rows),
                "label_counts": _counter_to_dict(Counter(str(row.get("review_label")) for row in rows)),
                "bucket_counts": _counter_to_dict(Counter(str(row.get("triage_bucket")) for row in rows)),
                "post_ids": [row.get("post_id") for row in rows],
                "sample_rows": rows[:8],
            }
        )

    source_summary = source_queue.get("summary") if isinstance(source_queue.get("summary"), dict) else {}
    accounting_summary = accounting.get("summary") if isinstance(accounting.get("summary"), dict) else {}
    return {
        "report_type": "ordinary_residual_dispatch",
        "dispatch_id": dispatch_id,
        "generated_at": generated_at or datetime.now().replace(microsecond=0).isoformat(),
        "source_accounting_id": accounting.get("accounting_id"),
        "source_queue_id": _source_id(source_queue, fallback="source_queue"),
        "gate": "NO-GO" if validation_issues else "REVIEW-LOCKED",
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "summary": {
            "source_accounting_rows": len(accounting_rows),
            "source_queue_rows": source_summary.get("residual_action_queue_rows", len(source_rows)),
            "ordinary_residual_rows": len(ordinary_rows),
            "contract_processed_rows_held": accounting_summary.get("contract_processed_rows"),
            "validation_issue_count": len(validation_issues),
            "lane_counts": _counter_to_dict(lane_counts),
            "label_counts": _counter_to_dict(label_counts),
            "bucket_counts": _counter_to_dict(bucket_counts),
            "transition_counts": _counter_to_dict(transition_counts),
            "action_counts": _counter_to_dict(action_counts),
            "publish_allowed_rows": 0,
            "runtime_replay_allowed_rows": 0,
            "full375_collateral_gate": "NO-GO",
            "completion_gate": "full375 collateral GO + full_scan path",
        },
        "validation_issues": validation_issues,
        "lane_groups": groups,
        "rows": ordinary_rows,
        "approval_boundary": {
            "dispatch_generation_is_not_approval": True,
            "runtime_replay_allowed": False,
            "publish_allowed": False,
            "full375_collateral_go_required_before_completion": True,
            "full_scan_approval": False,
        },
    }


def write_markdown(dispatch: dict[str, Any], path: Path) -> None:
    summary = dispatch["summary"]
    lines = [
        f"# {dispatch.get('dispatch_id')}",
        "",
        "이 회차는 남은 ordinary residual을 단건이 아니라 배치 lane으로 재분해한 산출물이다. "
        "새 runtime replay, bounded run, full375 대형 런은 실행하지 않았다.",
        "",
        "## 요약",
        "",
        f"- source_accounting_id: `{dispatch.get('source_accounting_id')}`",
        f"- source_queue_id: `{dispatch.get('source_queue_id')}`",
        f"- ordinary_residual_rows: `{summary.get('ordinary_residual_rows')}`",
        f"- contract_processed_rows_held: `{summary.get('contract_processed_rows_held')}`",
        f"- lane_counts: `{summary.get('lane_counts')}`",
        f"- label_counts: `{summary.get('label_counts')}`",
        f"- bucket_counts: `{summary.get('bucket_counts')}`",
        f"- validation_issue_count: `{summary.get('validation_issue_count')}`",
        f"- publish_allowed_rows: `{summary.get('publish_allowed_rows')}`",
        f"- runtime_replay_allowed_rows: `{summary.get('runtime_replay_allowed_rows')}`",
        "- approval: `false`",
        "- semantic_quality: `REVIEW-LOCKED`",
        "- full_scan_approval: `false`",
        "",
        "## 승인 경계",
        "",
        "- 이 dispatch는 residual 처리 순서를 정한 산출물이며 approval이 아니다.",
        "- 모든 lane은 review/contract/full375 재확인 전까지 `publish_allowed=false`, `runtime_replay_allowed=false`다.",
        "- Dashboard는 다음 runtime 진행 관측 도구일 뿐 semantic/full_scan approval 근거가 아니다.",
        "- 완료 기준은 계속 `full375 collateral GO + full_scan 경로 정의`다.",
        "",
        "## Lanes",
        "",
    ]
    for group in dispatch.get("lane_groups") or []:
        sample = ", ".join(str(post_id) for post_id in group.get("post_ids", [])[:14])
        lines.extend(
            [
                f"### {group.get('lane')}",
                "",
                f"- 의미: {group.get('description_ko')}",
                f"- lane_gate: `{group.get('lane_gate')}`",
                f"- row_count: `{group.get('row_count')}`",
                f"- label_counts: `{group.get('label_counts')}`",
                f"- bucket_counts: `{group.get('bucket_counts')}`",
                f"- sample_post_ids: `{sample}`",
                "",
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    while lines and lines[-1] == "":
        lines.pop()
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a lane dispatch for Loop552 ordinary residual rows.")
    parser.add_argument("--accounting", required=True, type=Path)
    parser.add_argument("--source-queue", required=True, type=Path)
    parser.add_argument("--dispatch-id", default="loop553_ordinary_residual64_dispatch")
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-md", required=True, type=Path)
    parser.add_argument("--fail-on-validation-issue", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    dispatch = build_dispatch(
        accounting=load_json(args.accounting),
        source_queue=load_json(args.source_queue),
        dispatch_id=args.dispatch_id,
    )
    write_json(args.output_json, dispatch)
    write_markdown(dispatch, args.output_md)
    if args.fail_on_validation_issue and dispatch["summary"]["validation_issue_count"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
