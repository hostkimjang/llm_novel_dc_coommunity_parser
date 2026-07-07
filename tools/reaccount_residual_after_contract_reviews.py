from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


EXPECTED_RESTORE = "expected_title_restore_contract_case"
CANDIDATE_SCRUB = "candidate_scrub_no_publish_contract_case"
VARIANT_HOLD = "canonical_variant_policy_hold_contract_case"
STRONGER_HOLD = "stronger_evidence_hard_hold_contract_case"


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


def _applied_by_post_id(application: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    rows = (application or {}).get("applied_rows") or []
    if not isinstance(rows, list):
        return {}
    return {_string(row.get("post_id")): row for row in rows if isinstance(row, dict) and _string(row.get("post_id"))}


def _classification_for(
    residual_row: dict[str, Any],
    *,
    plan_row: dict[str, Any] | None,
    applied_row: dict[str, Any] | None,
    variant_row: dict[str, Any] | None,
    c3_row: dict[str, Any] | None,
) -> tuple[str, str, list[str]]:
    if not plan_row:
        return "ordinary_residual_unprocessed", "residual_queue_followup_required", []

    issues: list[str] = []
    action = _string(plan_row.get("contract_action"))
    if action == EXPECTED_RESTORE:
        if not applied_row or _string(applied_row.get("status")) != "applied":
            issues.append("expected_restore_application_missing")
            return "contract_processing_validation_issue", "expected_restore_application_missing", issues
        return (
            "contract_processed_expected_restore_projection_applied",
            "release_candidate_not_approval_full375_recheck_required",
            issues,
        )
    if action == CANDIDATE_SCRUB:
        return (
            "contract_processed_candidate_scrub_no_publish",
            "candidate_scrub_no_publish_not_approval",
            issues,
        )
    if action == VARIANT_HOLD:
        if not variant_row or _string(variant_row.get("policy_decision")) != "canonical_variant_quarantine_no_publish":
            issues.append("canonical_variant_policy_review_missing")
            return "contract_processing_validation_issue", "variant_policy_review_missing", issues
        return (
            "contract_processed_variant_quarantine_no_publish",
            "variant_quarantine_exclusion_candidate_not_approval",
            issues,
        )
    if action == STRONGER_HOLD:
        if not c3_row or _string(c3_row.get("policy_decision")) != "stronger_evidence_native_web_hard_hold":
            issues.append("stronger_evidence_hold_review_missing")
            return "contract_processing_validation_issue", "stronger_evidence_hold_review_missing", issues
        return (
            "contract_processed_stronger_evidence_hard_hold",
            "native_web_or_blind_judge_required_not_approval",
            issues,
        )
    issues.append("unknown_contract_action")
    return "contract_processing_validation_issue", "unknown_contract_action", issues


def build_accounting(
    *,
    residual_queue: dict[str, Any],
    contract_plan: dict[str, Any],
    expected_restore_application: dict[str, Any] | None = None,
    variant_review: dict[str, Any] | None = None,
    c3_review: dict[str, Any] | None = None,
    accounting_id: str,
    generated_at: str | None = None,
) -> dict[str, Any]:
    residual_rows = _rows(residual_queue)
    plan_by_id = _by_post_id(_rows(contract_plan))
    applied_by_id = _applied_by_post_id(expected_restore_application)
    variant_by_id = _by_post_id(_rows(variant_review)) if variant_review else {}
    c3_by_id = _by_post_id(_rows(c3_review)) if c3_review else {}

    rows: list[dict[str, Any]] = []
    validation_issues: list[dict[str, Any]] = []
    state_counts: Counter[str] = Counter()
    effect_counts: Counter[str] = Counter()
    label_counts: Counter[str] = Counter()
    bucket_counts: Counter[str] = Counter()
    transition_counts: Counter[str] = Counter()
    action_counts: Counter[str] = Counter()

    for residual_row in residual_rows:
        post_id = _string(residual_row.get("post_id"))
        plan_row = plan_by_id.get(post_id)
        variant_row = variant_by_id.get(post_id)
        c3_row = c3_by_id.get(post_id)
        applied_row = applied_by_id.get(post_id)
        state, effect, issues = _classification_for(
            residual_row,
            plan_row=plan_row,
            applied_row=applied_row,
            variant_row=variant_row,
            c3_row=c3_row,
        )
        if issues:
            validation_issues.append({"post_id": residual_row.get("post_id"), "issues": issues})
        actions = residual_row.get("actions") if isinstance(residual_row.get("actions"), list) else []
        for action in actions:
            action_counts[str(action)] += 1
        label_counts[_string(residual_row.get("review_label"))] += 1
        bucket_counts[_string(residual_row.get("triage_bucket"))] += 1
        transition_counts[_string(residual_row.get("loop546_transition"))] += 1
        state_counts[state] += 1
        effect_counts[effect] += 1
        rows.append(
            {
                "post_id": residual_row.get("post_id"),
                "triage_bucket": residual_row.get("triage_bucket"),
                "review_label": residual_row.get("review_label"),
                "source_native_verdict": residual_row.get("source_native_verdict"),
                "selected_title": residual_row.get("selected_title"),
                "selected_option_id": residual_row.get("selected_option_id"),
                "loop546_transition": residual_row.get("loop546_transition"),
                "contract_action": (plan_row or {}).get("contract_action"),
                "contract_batch_lane": (plan_row or {}).get("contract_batch_lane"),
                "contract_accounting_state": state,
                "contract_accounting_effect": effect,
                "contract_processed": state.startswith("contract_processed_"),
                "ordinary_residual_unprocessed": state == "ordinary_residual_unprocessed",
                "publish_allowed": False,
                "runtime_replay_allowed": False,
                "full_scan_approval": False,
                "validation_issues": issues,
                "target_title": (plan_row or {}).get("target_title"),
                "current_projection_candidate_title": (plan_row or {}).get("current_projection_candidate_title"),
                "policy_review_ref": _policy_ref_for(action=(plan_row or {}).get("contract_action")),
                "rationale_ko": residual_row.get("rationale_ko"),
                "evidence_refs": residual_row.get("evidence_refs") or [],
            }
        )

    source_summary = residual_queue.get("summary") or {}
    contract_processed_rows = sum(1 for row in rows if row.get("contract_processed"))
    ordinary_unprocessed_rows = sum(1 for row in rows if row.get("ordinary_residual_unprocessed"))
    return {
        "report_type": "residual_contract_review_accounting",
        "accounting_id": accounting_id,
        "generated_at": generated_at or datetime.now().replace(microsecond=0).isoformat(),
        "source_residual_queue": residual_queue.get("queue_id"),
        "source_contract_plan": contract_plan.get("plan_id"),
        "source_expected_restore_application": (expected_restore_application or {}).get("projection_id"),
        "source_variant_review": (variant_review or {}).get("review_id"),
        "source_c3_review": (c3_review or {}).get("review_id"),
        "gate": "NO-GO" if validation_issues else "REVIEW-LOCKED",
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "summary": {
            "source_residual_rows": len(residual_rows),
            "source_residual_action_queue_rows": source_summary.get("residual_action_queue_rows"),
            "contract_plan_overlap_rows": sum(1 for row in rows if row.get("contract_action")),
            "contract_processed_rows": contract_processed_rows,
            "ordinary_residual_unprocessed_rows": ordinary_unprocessed_rows,
            "validation_issue_count": len(validation_issues),
            "contract_accounting_state_counts": dict(state_counts),
            "contract_accounting_effect_counts": dict(effect_counts),
            "label_counts": dict(label_counts),
            "bucket_counts": dict(bucket_counts),
            "transition_counts": dict(transition_counts),
            "source_action_counts": dict(action_counts),
            "release_candidate_not_approval_rows": effect_counts.get(
                "release_candidate_not_approval_full375_recheck_required", 0
            ),
            "no_publish_or_hold_contract_rows": contract_processed_rows
            - effect_counts.get("release_candidate_not_approval_full375_recheck_required", 0),
            "publish_allowed_rows": 0,
            "runtime_replay_allowed_rows": 0,
            "full375_collateral_gate": "NO-GO",
            "completion_gate": "full375 collateral GO + full_scan path",
        },
        "validation_issues": validation_issues,
        "rows": rows,
        "unprocessed_rows": [row for row in rows if row.get("ordinary_residual_unprocessed")],
        "contract_processed_rows": [row for row in rows if row.get("contract_processed")],
        "approval_boundary": {
            "contract_accounting_is_not_full375_go": True,
            "contract_processed_rows_are_not_full_scan_approval": True,
            "release_candidates_require_full375_recheck": True,
            "runtime_replay_allowed_rows_remain_zero": True,
            "semantic_quality_remains_review_locked": True,
        },
    }


def _policy_ref_for(*, action: Any) -> str | None:
    action_text = _string(action)
    if action == EXPECTED_RESTORE:
        return "docs/devs/loop549_b1_expected_restore_projection_contract_application.json"
    if action_text in {CANDIDATE_SCRUB, EXPECTED_RESTORE}:
        return "docs/devs/loop548_b1_post_verdict_promotion_gate_contract_plan.json"
    if action_text == VARIANT_HOLD:
        return "docs/devs/loop550_c2_canonical_variant_policy_review.json"
    if action_text == STRONGER_HOLD:
        return "docs/devs/loop551_c3_stronger_evidence_hold_review.json"
    return None


def write_markdown(path: Path, accounting: dict[str, Any]) -> None:
    summary = accounting["summary"]
    lines = [
        f"# {accounting.get('accounting_id')}",
        "",
        "Loop546 residual78에 Loop548/549/550/551 post-verdict contract 결과를 결합한 회계 산출물이다. "
        "이 산출물은 새 runtime replay나 full375 GO가 아니며, contract 처리 상태와 아직 남은 ordinary residual을 분리한다.",
        "",
        "## 요약",
        "",
        f"- gate: `{accounting['gate']}`",
        f"- semantic_quality: `{accounting['semantic_quality']}`",
        f"- full_scan_approval: `{str(accounting['full_scan_approval']).lower()}`",
        f"- source_residual_rows: `{summary['source_residual_rows']}`",
        f"- contract_plan_overlap_rows: `{summary['contract_plan_overlap_rows']}`",
        f"- contract_processed_rows: `{summary['contract_processed_rows']}`",
        f"- ordinary_residual_unprocessed_rows: `{summary['ordinary_residual_unprocessed_rows']}`",
        f"- validation_issue_count: `{summary['validation_issue_count']}`",
        f"- release_candidate_not_approval_rows: `{summary['release_candidate_not_approval_rows']}`",
        f"- no_publish_or_hold_contract_rows: `{summary['no_publish_or_hold_contract_rows']}`",
        f"- publish_allowed_rows: `{summary['publish_allowed_rows']}`",
        f"- runtime_replay_allowed_rows: `{summary['runtime_replay_allowed_rows']}`",
        f"- full375 collateral: `{summary['full375_collateral_gate']}`",
        "",
        "## Contract 회계 상태",
        "",
    ]
    for state, count in sorted((summary.get("contract_accounting_state_counts") or {}).items()):
        lines.append(f"- `{state}`: `{count}`")
    lines.extend(["", "## Gate 해석", ""])
    lines.append(
        "Loop548 post-verdict 14건은 최신 shared gate 산출물로 contract-processed 상태가 됐다. "
        "하지만 release candidate `3`건은 approval이 아니고, no-publish/quarantine/hard-hold `11`건은 public publish를 열지 않는다. "
        "ordinary residual `64`건과 full375 collateral 재확인이 남아 있으므로 goal은 `ACTIVE / NOT_COMPLETE`, "
        "`semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`다."
    )
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reaccount residual queue after post-verdict contract reviews.")
    parser.add_argument("--residual-queue", required=True, type=Path)
    parser.add_argument("--contract-plan", required=True, type=Path)
    parser.add_argument("--expected-restore-application", type=Path)
    parser.add_argument("--variant-review", type=Path)
    parser.add_argument("--c3-review", type=Path)
    parser.add_argument("--accounting-id", default="residual_contract_review_accounting")
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-md", required=True, type=Path)
    parser.add_argument("--fail-on-validation-issue", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    accounting = build_accounting(
        residual_queue=load_json(args.residual_queue),
        contract_plan=load_json(args.contract_plan),
        expected_restore_application=load_json(args.expected_restore_application)
        if args.expected_restore_application
        else None,
        variant_review=load_json(args.variant_review) if args.variant_review else None,
        c3_review=load_json(args.c3_review) if args.c3_review else None,
        accounting_id=args.accounting_id,
    )
    write_json(args.output_json, accounting)
    write_markdown(args.output_md, accounting)
    print(json.dumps({"gate": accounting["gate"], "summary": accounting["summary"]}, ensure_ascii=False, indent=2))
    if args.fail_on_validation_issue and accounting["validation_issues"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
