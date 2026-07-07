from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


VARIANT_ACTION = "canonical_variant_policy_hold_contract_case"
VARIANT_LANE = "C2_canonical_variant_policy_contract"
SEARCH_CONDITIONAL_GATES = {"SEARCH_BLIND_BLOCKER", "SEARCH_EVIDENCE_MISSING"}


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


def _compact(value: Any) -> str:
    return "".join(ch for ch in _string(value).lower() if ch.isalnum())


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    if not isinstance(rows, list):
        raise ValueError("payload must contain rows list")
    return [row for row in rows if isinstance(row, dict)]


def _by_post_id(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {_string(row.get("post_id")): row for row in rows if _string(row.get("post_id"))}


def _variant_relation(row: dict[str, Any], queue_row: dict[str, Any] | None) -> str:
    target = _string(row.get("target_title"))
    current = _string(row.get("current_projection_candidate_title"))
    expected = _string((queue_row or {}).get("expected_or_source_native_title"))
    target_key = _compact(target)
    current_key = _compact(current)
    expected_key = _compact(expected)
    if target_key and current_key and target_key == current_key:
        return "current_candidate_matches_clean_canonical"
    if target_key and expected_key and target_key == expected_key:
        return "expected_matches_clean_canonical"
    if target_key and current_key and (target_key in current_key or current_key in target_key):
        return "partial_or_abbreviation_variant"
    if target_key and expected_key and (target_key in expected_key or expected_key in target_key):
        return "expected_contaminated_or_volume_variant"
    return "related_variant_requires_human_policy_note"


def _issue_list(row: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    if _string(row.get("contract_action")) != VARIANT_ACTION:
        issues.append("not_canonical_variant_policy_action")
    if _string(row.get("contract_batch_lane")) != VARIANT_LANE:
        issues.append("not_canonical_variant_policy_lane")
    if _string(row.get("canonical_verdict")) != "RELATED_CANONICAL_VARIANT_CONFIRMED":
        issues.append("canonical_verdict_not_related_variant")
    if not _string(row.get("target_title")):
        issues.append("missing_target_canonical_title")
    decision = row.get("promotion_decision") if isinstance(row.get("promotion_decision"), dict) else {}
    if decision.get("publish_allowed") is True:
        issues.append("variant_plan_publish_allowed_before_policy")
    if _string(decision.get("status")) != "candidate_only":
        issues.append("variant_plan_not_candidate_only")
    reason_codes = decision.get("reason_codes") if isinstance(decision.get("reason_codes"), list) else []
    if "canonical_variant_policy_pending" not in {str(code) for code in reason_codes}:
        issues.append("variant_policy_pending_reason_missing")
    if row.get("runtime_replay_allowed") is True:
        issues.append("runtime_replay_allowed_before_variant_policy")
    return issues


def _build_review_row(row: dict[str, Any], queue_row: dict[str, Any] | None) -> dict[str, Any]:
    issues = _issue_list(row)
    search_gate = _string(row.get("search_gate") or (queue_row or {}).get("search_gate"))
    evidence_grade = _string(row.get("evidence_grade") or (queue_row or {}).get("evidence_grade"))
    relation = _variant_relation(row, queue_row)
    search_conditional = search_gate in SEARCH_CONDITIONAL_GATES
    exclusion_candidate = not issues and evidence_grade.lower() in {"strong", "medium"}
    return {
        "post_id": row.get("post_id"),
        "policy_decision": "canonical_variant_quarantine_no_publish" if not issues else "policy_validation_issue",
        "variant_relation": relation,
        "expected_or_source_native_title": (queue_row or {}).get("expected_or_source_native_title"),
        "canonical_title": row.get("target_title"),
        "canonical_url": row.get("target_url"),
        "current_projection_candidate_title": row.get("current_projection_candidate_title"),
        "current_projection_candidate_url": row.get("current_projection_candidate_url"),
        "search_gate": search_gate or None,
        "search_blind_conditional": search_conditional,
        "evidence_grade": evidence_grade or None,
        "regression_exclusion_candidate_after_gate_wiring": exclusion_candidate,
        "publish_allowed": False,
        "runtime_replay_allowed": False,
        "full_scan_approval": False,
        "validation_issues": issues,
        "rationale_ko": row.get("rationale_ko") or (queue_row or {}).get("rationale_ko"),
        "evidence_refs": row.get("evidence_refs") or (queue_row or {}).get("evidence_refs") or [],
    }


def build_review(
    *,
    contract_plan: dict[str, Any],
    contract_queue: dict[str, Any] | None = None,
    review_id: str,
    generated_at: str | None = None,
) -> dict[str, Any]:
    queue_by_id = _by_post_id(_rows(contract_queue)) if contract_queue else {}
    source_rows = [
        row
        for row in _rows(contract_plan)
        if _string(row.get("contract_action")) == VARIANT_ACTION
        or _string(row.get("contract_batch_lane")) == VARIANT_LANE
    ]
    rows = [_build_review_row(row, queue_by_id.get(_string(row.get("post_id")))) for row in source_rows]
    validation_issues = [
        {"post_id": row.get("post_id"), "issues": row.get("validation_issues")}
        for row in rows
        if row.get("validation_issues")
    ]
    relation_counts = Counter(_string(row.get("variant_relation")) for row in rows)
    search_counts = Counter(_string(row.get("search_gate")) for row in rows)
    decision_counts = Counter(_string(row.get("policy_decision")) for row in rows)
    return {
        "report_type": "canonical_variant_policy_review",
        "review_id": review_id,
        "generated_at": generated_at or datetime.now().replace(microsecond=0).isoformat(),
        "source_contract_plan": contract_plan.get("plan_id"),
        "source_contract_queue": (contract_queue or {}).get("queue_id"),
        "gate": "NO-GO" if validation_issues else "REVIEW-LOCKED",
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "summary": {
            "source_variant_rows": len(source_rows),
            "policy_review_rows": len(rows),
            "validation_issue_count": len(validation_issues),
            "policy_decision_counts": dict(decision_counts),
            "variant_relation_counts": dict(relation_counts),
            "search_gate_counts": dict(search_counts),
            "search_blind_conditional_rows": sum(1 for row in rows if row.get("search_blind_conditional")),
            "regression_exclusion_candidate_rows": sum(
                1 for row in rows if row.get("regression_exclusion_candidate_after_gate_wiring")
            ),
            "publish_allowed_rows": 0,
            "runtime_replay_allowed_rows": 0,
            "full375_collateral_gate": "NO-GO",
            "completion_gate": "full375 collateral GO + full_scan path",
        },
        "validation_issues": validation_issues,
        "rows": rows,
        "approval_boundary": {
            "variant_policy_review_is_not_runtime_replay": True,
            "variant_quarantine_is_not_full_scan_approval": True,
            "search_blind_conditional_rows_require_search_recovery_before_promotion": True,
            "full375_collateral_remains_no_go": True,
        },
    }


def write_markdown(path: Path, review: dict[str, Any]) -> None:
    summary = review["summary"]
    lines = [
        f"# {review.get('review_id')}",
        "",
        "Loop548/549 뒤에 남은 C2 canonical variant policy 행을 shared promotion gate 계약 기준으로 검토한 산출물이다. "
        "이 리뷰는 public publish, runtime replay, full_scan approval이 아니며, variant를 no-publish quarantine/exclusion 후보로만 분리한다.",
        "",
        "## 요약",
        "",
        f"- gate: `{review['gate']}`",
        f"- semantic_quality: `{review['semantic_quality']}`",
        f"- full_scan_approval: `{str(review['full_scan_approval']).lower()}`",
        f"- policy_review_rows: `{summary['policy_review_rows']}`",
        f"- validation_issue_count: `{summary['validation_issue_count']}`",
        f"- regression_exclusion_candidate_rows: `{summary['regression_exclusion_candidate_rows']}`",
        f"- search_blind_conditional_rows: `{summary['search_blind_conditional_rows']}`",
        f"- publish_allowed_rows: `{summary['publish_allowed_rows']}`",
        f"- runtime_replay_allowed_rows: `{summary['runtime_replay_allowed_rows']}`",
        f"- full375 collateral: `{summary['full375_collateral_gate']}`",
        "",
        "## Variant 관계",
        "",
    ]
    for relation, count in sorted((summary.get("variant_relation_counts") or {}).items()):
        lines.append(f"- `{relation}`: `{count}`")
    lines.extend(["", "## 행별 정책", ""])
    for row in review.get("rows") or []:
        lines.append(
            f"- `{row.get('post_id')}` decision=`{row.get('policy_decision')}` "
            f"relation=`{row.get('variant_relation')}` canonical=`{row.get('canonical_title')}` "
            f"candidate=`{row.get('current_projection_candidate_title')}` "
            f"search=`{row.get('search_gate')}` exclusion_candidate=`{row.get('regression_exclusion_candidate_after_gate_wiring')}`"
        )
    lines.extend(["", "## Gate 해석", ""])
    lines.append(
        "C2 5건은 모두 no-publish quarantine으로 유지한다. "
        "regression exclusion 후보로 표시된 행도 queue 회계 후보일 뿐 approval이 아니며, "
        "search blind/missing 행은 search 복구 전 promotion approval 근거로 쓰지 않는다. "
        "따라서 goal은 `ACTIVE / NOT_COMPLETE`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`다."
    )
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build canonical variant policy review from a post-verdict contract plan.")
    parser.add_argument("--contract-plan", required=True, type=Path)
    parser.add_argument("--contract-queue", type=Path)
    parser.add_argument("--review-id", default="canonical_variant_policy_review")
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-md", required=True, type=Path)
    parser.add_argument("--fail-on-validation-issue", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    review = build_review(
        contract_plan=load_json(args.contract_plan),
        contract_queue=load_json(args.contract_queue) if args.contract_queue else None,
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
