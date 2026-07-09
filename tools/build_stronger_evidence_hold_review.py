from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


C3_ACTION = "stronger_evidence_hard_hold_contract_case"
C3_LANE = "C3_stronger_evidence_or_native_web_hold"
C3_VERDICT = "INSUFFICIENT_EVIDENCE_HOLD"
SEARCH_BLOCKER_GATES = {"SEARCH_BLIND_BLOCKER", "SEARCH_EVIDENCE_MISSING"}


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


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    if not isinstance(rows, list):
        raise ValueError("payload must contain rows list")
    return [row for row in rows if isinstance(row, dict)]


def _by_post_id(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {_string(row.get("post_id")): row for row in rows if _string(row.get("post_id"))}


def _prior_by_post_id(prior_verdicts: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for payload in prior_verdicts:
        for row in _rows(payload):
            post_id = _string(row.get("post_id"))
            if post_id:
                merged[post_id] = row
    return merged


def _issue_list(row: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    if _string(row.get("contract_action")) != C3_ACTION:
        issues.append("not_stronger_evidence_hold_action")
    if _string(row.get("contract_batch_lane")) != C3_LANE:
        issues.append("not_stronger_evidence_hold_lane")
    if _string(row.get("canonical_verdict")) != C3_VERDICT:
        issues.append("canonical_verdict_not_insufficient_evidence_hold")
    decision = row.get("promotion_decision") if isinstance(row.get("promotion_decision"), dict) else {}
    if decision.get("publish_allowed") is True:
        issues.append("hard_hold_plan_publish_allowed")
    if _string(decision.get("status")) != "candidate_only":
        issues.append("hard_hold_plan_not_candidate_only")
    reason_codes = decision.get("reason_codes") if isinstance(decision.get("reason_codes"), list) else []
    if "stronger_evidence_required" not in {str(code) for code in reason_codes}:
        issues.append("stronger_evidence_required_reason_missing")
    if row.get("runtime_replay_allowed") is True:
        issues.append("runtime_replay_allowed_before_stronger_evidence")
    if row.get("stronger_evidence_required_before_runtime") is False:
        issues.append("stronger_evidence_required_before_runtime_false")
    return issues


def _hold_reason(row: dict[str, Any], queue_row: dict[str, Any] | None) -> str:
    target = _string(row.get("target_title") or (queue_row or {}).get("expected_or_source_native_title"))
    current = _string(row.get("current_projection_candidate_title"))
    rationale = _string(row.get("rationale_ko") or (queue_row or {}).get("rationale_ko"))
    haystack = " ".join([target, current, rationale]).lower()
    if "유희왕" in haystack or "프랜차이즈" in rationale or "패러디" in rationale:
        return "franchise_or_fanfic_native_web_required"
    if "시스템" in haystack or "상태창" in rationale or "클리셰" in rationale:
        return "generic_system_trope_direct_title_missing"
    if "이미지" in rationale or "캐릭터" in rationale or current:
        return "competing_candidate_image_or_character_bridge_required"
    return "stronger_evidence_required"


def _source_snapshot(source_row: dict[str, Any] | None) -> dict[str, Any]:
    context = (source_row or {}).get("source_context")
    if not isinstance(context, dict):
        return {}
    keys = [
        "post_title",
        "post_url",
        "content_preview",
        "comment_preview",
        "comment_dialogue_context_preview",
        "image_count",
        "image_urls",
    ]
    return {key: context.get(key) for key in keys if key in context}


def _build_review_row(
    row: dict[str, Any],
    *,
    queue_row: dict[str, Any] | None,
    prior_row: dict[str, Any] | None,
    source_row: dict[str, Any] | None,
) -> dict[str, Any]:
    issues = _issue_list(row)
    search_gate = _string(row.get("search_gate") or (queue_row or {}).get("search_gate"))
    prior_label = _string((prior_row or {}).get("review_label"))
    prior_actions = (prior_row or {}).get("action")
    if not isinstance(prior_actions, list):
        prior_actions = []
    prior_restore_conflict = prior_label == "REPROCESS" and "repair_safe_loss_restore_supported_title" in {
        str(action) for action in prior_actions
    }
    return {
        "post_id": row.get("post_id"),
        "policy_decision": "stronger_evidence_native_web_hard_hold" if not issues else "policy_validation_issue",
        "hold_reason": _hold_reason(row, queue_row),
        "expected_or_source_native_title": (queue_row or {}).get("expected_or_source_native_title"),
        "target_title": row.get("target_title"),
        "target_url": row.get("target_url"),
        "current_projection_candidate_title": row.get("current_projection_candidate_title"),
        "current_projection_candidate_url": row.get("current_projection_candidate_url"),
        "search_gate": search_gate or None,
        "search_recovery_required": search_gate in SEARCH_BLOCKER_GATES,
        "native_web_or_blind_judge_required": True,
        "prior_source_native_verdict": (prior_row or {}).get("source_native_verdict"),
        "prior_review_label": prior_label or None,
        "prior_restore_conflict": prior_restore_conflict,
        "prior_restore_is_release_authority": False,
        "publish_allowed": False,
        "runtime_replay_allowed": False,
        "full_scan_approval": False,
        "validation_issues": issues,
        "rationale_ko": row.get("rationale_ko") or (queue_row or {}).get("rationale_ko"),
        "source_snapshot": _source_snapshot(source_row),
        "evidence_refs": row.get("evidence_refs") or (queue_row or {}).get("evidence_refs") or [],
    }


def build_review(
    *,
    contract_plan: dict[str, Any],
    contract_queue: dict[str, Any] | None = None,
    prior_verdicts: list[dict[str, Any]] | None = None,
    source_batch: dict[str, Any] | None = None,
    review_id: str,
    generated_at: str | None = None,
) -> dict[str, Any]:
    queue_by_id = _by_post_id(_rows(contract_queue)) if contract_queue else {}
    prior_by_id = _prior_by_post_id(prior_verdicts or [])
    source_by_id = _by_post_id(_rows(source_batch)) if source_batch else {}
    source_rows = [
        row
        for row in _rows(contract_plan)
        if _string(row.get("contract_action")) == C3_ACTION
        or _string(row.get("contract_batch_lane")) == C3_LANE
    ]
    rows = [
        _build_review_row(
            row,
            queue_row=queue_by_id.get(_string(row.get("post_id"))),
            prior_row=prior_by_id.get(_string(row.get("post_id"))),
            source_row=source_by_id.get(_string(row.get("post_id"))),
        )
        for row in source_rows
    ]
    validation_issues = [
        {"post_id": row.get("post_id"), "issues": row.get("validation_issues")}
        for row in rows
        if row.get("validation_issues")
    ]
    decision_counts = Counter(_string(row.get("policy_decision")) for row in rows)
    hold_reason_counts = Counter(_string(row.get("hold_reason")) for row in rows)
    search_counts = Counter(_string(row.get("search_gate")) for row in rows)
    prior_counts = Counter(_string(row.get("prior_review_label")) for row in rows)
    return {
        "report_type": "stronger_evidence_hold_review",
        "review_id": review_id,
        "generated_at": generated_at or datetime.now().replace(microsecond=0).isoformat(),
        "source_contract_plan": contract_plan.get("plan_id"),
        "source_contract_queue": (contract_queue or {}).get("queue_id"),
        "source_batch": (source_batch or {}).get("batch_id") or (source_batch or {}).get("review_id"),
        "gate": "NO-GO" if validation_issues else "REVIEW-LOCKED",
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "summary": {
            "source_c3_rows": len(source_rows),
            "hard_hold_review_rows": len(rows),
            "validation_issue_count": len(validation_issues),
            "policy_decision_counts": dict(decision_counts),
            "hold_reason_counts": dict(hold_reason_counts),
            "search_gate_counts": dict(search_counts),
            "prior_review_label_counts": dict(prior_counts),
            "prior_restore_conflict_rows": sum(1 for row in rows if row.get("prior_restore_conflict")),
            "search_recovery_required_rows": sum(1 for row in rows if row.get("search_recovery_required")),
            "native_web_or_blind_judge_required_rows": sum(
                1 for row in rows if row.get("native_web_or_blind_judge_required")
            ),
            "publish_allowed_rows": 0,
            "runtime_replay_allowed_rows": 0,
            "full375_collateral_gate": "NO-GO",
            "completion_gate": "adjusted full375 collateral GO + full_scan path",
        },
        "validation_issues": validation_issues,
        "rows": rows,
        "approval_boundary": {
            "c3_review_is_not_runtime_replay": True,
            "prior_reprocess_verdict_is_not_release_authority": True,
            "native_web_or_blind_judge_required_before_release": True,
            "search_recovery_required_before_promotion_if_blind_or_missing": True,
            "full375_collateral_remains_no_go": True,
        },
    }


def write_markdown(path: Path, review: dict[str, Any]) -> None:
    summary = review["summary"]
    lines = [
        f"# {review.get('review_id')}",
        "",
        "Loop548/550 뒤 남은 C3 stronger evidence/native-web hold 행을 shared promotion gate 계약 기준으로 검토한 산출물이다. "
        "이 리뷰는 prior `REPROCESS` verdict를 무효화하는 것이 아니라, 최신 hard-hold 계약을 통과하기 전에는 public publish와 runtime replay를 열 수 없음을 고정한다.",
        "",
        "## 요약",
        "",
        f"- gate: `{review['gate']}`",
        f"- semantic_quality: `{review['semantic_quality']}`",
        f"- full_scan_approval: `{str(review['full_scan_approval']).lower()}`",
        f"- hard_hold_review_rows: `{summary['hard_hold_review_rows']}`",
        f"- validation_issue_count: `{summary['validation_issue_count']}`",
        f"- prior_restore_conflict_rows: `{summary['prior_restore_conflict_rows']}`",
        f"- search_recovery_required_rows: `{summary['search_recovery_required_rows']}`",
        f"- native_web_or_blind_judge_required_rows: `{summary['native_web_or_blind_judge_required_rows']}`",
        f"- publish_allowed_rows: `{summary['publish_allowed_rows']}`",
        f"- runtime_replay_allowed_rows: `{summary['runtime_replay_allowed_rows']}`",
        f"- full375 collateral: `{summary['full375_collateral_gate']}`",
        "",
        "## Hold 사유",
        "",
    ]
    for reason, count in sorted((summary.get("hold_reason_counts") or {}).items()):
        lines.append(f"- `{reason}`: `{count}`")
    lines.extend(["", "## 행별 정책", ""])
    for row in review.get("rows") or []:
        lines.append(
            f"- `{row.get('post_id')}` decision=`{row.get('policy_decision')}` "
            f"hold_reason=`{row.get('hold_reason')}` target=`{row.get('target_title')}` "
            f"candidate=`{row.get('current_projection_candidate_title')}` search=`{row.get('search_gate')}` "
            f"prior_restore_conflict=`{row.get('prior_restore_conflict')}`"
        )
    lines.extend(["", "## Gate 해석", ""])
    lines.append(
        "C3 3건은 native-web, blind judge, 직접 시각/캐릭터 bridge 같은 stronger evidence가 닫히기 전까지 hard-hold다. "
        "과거 source-native `REPROCESS` verdict가 있어도 최신 shared gate의 `stronger_evidence_required`를 우회할 수 없다. "
        "따라서 이번 리뷰 후에도 runtime replay allowed rows는 `0`이고, goal은 `ACTIVE / NOT_COMPLETE`, "
        "`semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`다."
    )
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build C3 stronger evidence hard-hold review from a contract plan.")
    parser.add_argument("--contract-plan", required=True, type=Path)
    parser.add_argument("--contract-queue", type=Path)
    parser.add_argument("--prior-verdicts", action="append", type=Path, default=[])
    parser.add_argument("--source-batch", type=Path)
    parser.add_argument("--review-id", default="stronger_evidence_hold_review")
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-md", required=True, type=Path)
    parser.add_argument("--fail-on-validation-issue", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    review = build_review(
        contract_plan=load_json(args.contract_plan),
        contract_queue=load_json(args.contract_queue) if args.contract_queue else None,
        prior_verdicts=[load_json(path) for path in args.prior_verdicts],
        source_batch=load_json(args.source_batch) if args.source_batch else None,
        review_id=args.review_id,
    )
    write_json(args.output_json, review)
    write_markdown(args.output_md, review)
    print(json.dumps({"gate": review["gate"], "summary": review["summary"]}, ensure_ascii=False, indent=2))
    if args.fail_on_validation_issue and review["validation_issues"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
