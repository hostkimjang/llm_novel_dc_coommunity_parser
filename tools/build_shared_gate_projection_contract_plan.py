from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


PUBLISH_RESTORE = "expected_title_restore_contract_case"
NO_PUBLISH = "candidate_scrub_no_publish_contract_case"


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


def _rows(payload: dict[str, Any], *, key: str = "rows") -> list[dict[str, Any]]:
    rows = payload.get(key)
    if not isinstance(rows, list):
        raise ValueError(f"payload must contain {key} list")
    return [row for row in rows if isinstance(row, dict)]


def _post_filter(residual_dispatch: dict[str, Any] | None) -> set[str] | None:
    if residual_dispatch is None:
        return None
    return {_string(row.get("post_id")) for row in _rows(residual_dispatch) if _string(row.get("post_id"))}


def _counter(values: list[str]) -> dict[str, int]:
    counter = Counter(value for value in values if value)
    return {key: counter[key] for key in sorted(counter)}


def _build_plan_row(row: dict[str, Any]) -> dict[str, Any]:
    decision = row.get("promotion_decision") if isinstance(row.get("promotion_decision"), dict) else {}
    publish_allowed = decision.get("publish_allowed") is True
    action = PUBLISH_RESTORE if publish_allowed else NO_PUBLISH
    target_title = _string(decision.get("official_title") if publish_allowed else row.get("selected_title"))
    target_url = _string(decision.get("official_url") if publish_allowed else row.get("selected_url"))
    lane = (
        "SG_shared_gate_publish_release_candidate"
        if publish_allowed
        else "SG_shared_gate_candidate_only_no_publish"
    )
    return {
        "post_id": row.get("post_id"),
        "contract_origin": row.get("projection_id") or "shared_gate_projection",
        "contract_batch_lane": lane,
        "source_projection_id": row.get("projection_id"),
        "triage_bucket": row.get("triage_bucket"),
        "review_label": "REPROCESS" if publish_allowed else "HOLD",
        "source_native_verdict": row.get("source_native_verdict"),
        "evidence_grade": row.get("evidence_grade"),
        "target_title": target_title or None,
        "target_url": target_url or None,
        "current_projection_candidate_title": row.get("selected_title"),
        "current_projection_candidate_url": row.get("selected_url"),
        "actions": row.get("source_actions") or [],
        "contract_action": action,
        "promotion_decision": decision,
        "promotion_gate_state": row.get("promotion_gate_state"),
        "promotion_gate_evidence": row.get("promotion_gate_evidence") or [],
        "release_candidate_not_approval": publish_allowed,
        "runtime_replay_allowed": False,
        "full375_recheck_required": publish_allowed,
        "full_scan_approval": False,
        "rationale_ko": row.get("rationale_ko"),
        "evidence_refs": row.get("evidence_refs") or [],
    }


def build_plan(
    projection: dict[str, Any],
    *,
    residual_dispatch: dict[str, Any] | None = None,
    plan_id: str,
    generated_at: str | None = None,
) -> dict[str, Any]:
    allowed_post_ids = _post_filter(residual_dispatch)
    projection_rows = []
    for row in _rows(projection):
        post_id = _string(row.get("post_id"))
        if allowed_post_ids is not None and post_id not in allowed_post_ids:
            continue
        projection_rows.append({**row, "projection_id": projection.get("projection_id")})

    rows = [_build_plan_row(row) for row in projection_rows]
    validation_issues: list[dict[str, Any]] = []
    for row in rows:
        decision = row.get("promotion_decision") if isinstance(row.get("promotion_decision"), dict) else {}
        action = _string(row.get("contract_action"))
        if decision.get("bypassed_gate"):
            validation_issues.append({"post_id": row.get("post_id"), "issue": "promotion_gate_bypassed"})
        if action == PUBLISH_RESTORE and decision.get("publish_allowed") is not True:
            validation_issues.append({"post_id": row.get("post_id"), "issue": "publish_action_without_publish_decision"})
        if action == PUBLISH_RESTORE and not row.get("target_title"):
            validation_issues.append({"post_id": row.get("post_id"), "issue": "publish_action_missing_target_title"})
        if row.get("runtime_replay_allowed"):
            validation_issues.append({"post_id": row.get("post_id"), "issue": "runtime_replay_allowed_before_full375"})

    action_counts = _counter([_string(row.get("contract_action")) for row in rows])
    status_counts = _counter([
        _string((row.get("promotion_decision") or {}).get("status")) for row in rows
    ])
    lane_counts = _counter([_string(row.get("contract_batch_lane")) for row in rows])
    publish_rows = sum(1 for row in rows if (row.get("promotion_decision") or {}).get("publish_allowed") is True)
    no_publish_rows = len(rows) - publish_rows
    return {
        "report_type": "shared_gate_projection_contract_plan",
        "plan_id": plan_id,
        "generated_at": generated_at or datetime.now().replace(microsecond=0).isoformat(),
        "source_projection_id": projection.get("projection_id"),
        "source_residual_dispatch_id": (residual_dispatch or {}).get("dispatch_id"),
        "gate": "NO-GO" if validation_issues else "REVIEW-LOCKED",
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "summary": {
            "source_projection_rows": len(_rows(projection)),
            "contract_plan_rows": len(rows),
            "filtered_to_residual_dispatch": residual_dispatch is not None,
            "validation_issue_count": len(validation_issues),
            "contract_batch_lane_counts": lane_counts,
            "contract_action_counts": action_counts,
            "promotion_decision_status_counts": status_counts,
            "publish_release_candidate_rows": publish_rows,
            "candidate_only_no_publish_rows": no_publish_rows,
            "runtime_replay_allowed_rows": 0,
            "full375_collateral_gate": "NO-GO",
            "completion_gate": "adjusted full375 collateral GO + full_scan path",
        },
        "validation_issues": validation_issues,
        "rows": rows,
        "approval_boundary": {
            "shared_gate_projection_is_not_runtime_replay": True,
            "publish_rows_are_release_candidates_not_approval": True,
            "candidate_only_rows_do_not_publish": True,
            "full375_collateral_remains_no_go": True,
        },
    }


def write_markdown(path: Path, plan: dict[str, Any]) -> None:
    summary = plan["summary"]
    lines = [
        f"# {plan.get('plan_id')}",
        "",
        "Shared promotion gate projection을 residual 회계가 이해하는 contract plan으로 변환한 산출물이다. "
        "이 산출물은 새 runtime replay가 아니며 full375 collateral approval도 아니다.",
        "",
        "## 요약",
        "",
        f"- source_projection_id: `{plan.get('source_projection_id')}`",
        f"- source_residual_dispatch_id: `{plan.get('source_residual_dispatch_id')}`",
        f"- gate: `{plan.get('gate')}`",
        f"- semantic_quality: `{plan.get('semantic_quality')}`",
        f"- full_scan_approval: `{str(plan.get('full_scan_approval')).lower()}`",
        f"- contract_plan_rows: `{summary.get('contract_plan_rows')}`",
        f"- contract_action_counts: `{summary.get('contract_action_counts')}`",
        f"- promotion_decision_status_counts: `{summary.get('promotion_decision_status_counts')}`",
        f"- publish_release_candidate_rows: `{summary.get('publish_release_candidate_rows')}`",
        f"- candidate_only_no_publish_rows: `{summary.get('candidate_only_no_publish_rows')}`",
        f"- validation_issue_count: `{summary.get('validation_issue_count')}`",
        f"- runtime_replay_allowed_rows: `{summary.get('runtime_replay_allowed_rows')}`",
        f"- full375 collateral: `{summary.get('full375_collateral_gate')}`",
        "",
        "## 행별 계획",
        "",
    ]
    for row in plan.get("rows") or []:
        decision = row.get("promotion_decision") if isinstance(row.get("promotion_decision"), dict) else {}
        lines.append(
            f"- `{row.get('post_id')}` action=`{row.get('contract_action')}` "
            f"decision=`{decision.get('status')}` target=`{row.get('target_title')}` "
            f"url=`{row.get('target_url')}`"
        )
    lines.extend(["", "## Gate 해석", ""])
    lines.append(
        "publish decision 행은 shared `PromotionDecision`을 통과한 release-candidate일 뿐이다. "
        "candidate-only 행은 no-publish contract로 보존하며 public title을 열지 않는다. "
        "따라서 goal은 계속 `ACTIVE / NOT_COMPLETE`이고 완료 기준은 `full375 collateral GO + full_scan 경로 정의`다."
    )
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build contract plan from shared promotion-gate projection rows.")
    parser.add_argument("--projection", required=True, type=Path)
    parser.add_argument("--residual-dispatch", type=Path)
    parser.add_argument("--plan-id", default="shared_gate_projection_contract_plan")
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-md", required=True, type=Path)
    parser.add_argument("--fail-on-validation-issue", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    residual_dispatch = load_json(args.residual_dispatch) if args.residual_dispatch else None
    plan = build_plan(
        load_json(args.projection),
        residual_dispatch=residual_dispatch,
        plan_id=args.plan_id,
    )
    write_json(args.output_json, plan)
    write_markdown(args.output_md, plan)
    print(json.dumps({"gate": plan["gate"], "summary": plan["summary"]}, ensure_ascii=False, indent=2))
    if args.fail_on_validation_issue and plan["validation_issues"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
