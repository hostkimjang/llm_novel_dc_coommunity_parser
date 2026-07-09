from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from llm_batch.promotion_gate import (  # noqa: E402
    EvidenceRecord,
    GroundingState,
    ScopeState,
    can_publish_title,
)


C1 = "C1_expected_restore_or_candidate_scrub_contract"
C2 = "C2_canonical_variant_policy_contract"
C3 = "C3_stronger_evidence_or_native_web_hold"
SG_PUBLISH = "SG_shared_gate_publish_release_candidate"
SG_CANDIDATE_ONLY = "SG_shared_gate_candidate_only_hold"
SEARCH_OK_FOR_CONTRACT_CASE = {"SEARCH_OK", "SEARCH_RECOVERED_CONDITIONAL"}
TITLE_REQUIRED_LANES = {C1, C2, SG_PUBLISH}
CONTRACT_TEST_LANES = {C1, C2, SG_PUBLISH}


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


def _rows(queue: dict[str, Any]) -> list[dict[str, Any]]:
    rows = queue.get("rows")
    if not isinstance(rows, list):
        raise ValueError("contract queue must contain rows list")
    return [row for row in rows if isinstance(row, dict)]


def _grade(value: Any) -> str:
    text = _string(value).lower()
    return text if text in {"strong", "medium", "weak", "missing"} else "medium"


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _is_shared_projection_row(row: dict[str, Any]) -> bool:
    lane = _string(row.get("contract_batch_lane"))
    if lane in {SG_PUBLISH, SG_CANDIDATE_ONLY}:
        return True
    actions = row.get("source_actions")
    action_texts = {str(action or "").strip() for action in actions if str(action or "").strip()} if isinstance(actions, list) else set()
    return bool(
        row.get("projected_status")
        and (
            isinstance(row.get("promotion_decision"), dict)
            or isinstance(row.get("publish_contract_trace"), dict)
            or "shared_promotion_gate_wiring_required" in action_texts
        )
    )


def _projection_decision(row: dict[str, Any]) -> dict[str, Any]:
    decision = _dict(row.get("promotion_decision"))
    if decision:
        return decision
    trace = _dict(row.get("publish_contract_trace"))
    return _dict(trace.get("gate_decision"))


def _normalized_lane(row: dict[str, Any]) -> str:
    lane = _string(row.get("contract_batch_lane"))
    if lane:
        return lane
    if not _is_shared_projection_row(row):
        return ""
    decision = _projection_decision(row)
    if decision.get("publish_allowed") is True or _string(decision.get("status")) == "publish":
        return SG_PUBLISH
    if _string(row.get("projected_status")) == "safe_resolved":
        return SG_PUBLISH
    return SG_CANDIDATE_ONLY


def _contract_blocking_reason(row: dict[str, Any]) -> str:
    lane = _normalized_lane(row)
    search_gate = _string(row.get("search_gate"))
    if lane == C2:
        return "canonical_variant_policy_pending"
    if lane == C3:
        return "stronger_evidence_required"
    if search_gate == "SEARCH_BLIND_BLOCKER":
        return "search_blind_condition"
    if search_gate == "SEARCH_EVIDENCE_MISSING":
        return "search_evidence_missing"
    return ""


def _target_title(row: dict[str, Any]) -> str:
    lane = _normalized_lane(row)
    decision = _projection_decision(row)
    if lane in {SG_PUBLISH, SG_CANDIDATE_ONLY}:
        return _string(
            row.get("projected_title")
            or row.get("selected_title")
            or decision.get("official_title")
            or row.get("canonical_title")
            or row.get("expected_or_source_native_title")
            or row.get("current_projection_candidate_title")
        )
    if lane in {C1, C2}:
        return _string(row.get("canonical_title") or row.get("expected_or_source_native_title"))
    return _string(row.get("canonical_title") or row.get("expected_or_source_native_title") or row.get("current_projection_candidate_title"))


def _target_url(row: dict[str, Any]) -> str:
    lane = _normalized_lane(row)
    decision = _projection_decision(row)
    if lane in {SG_PUBLISH, SG_CANDIDATE_ONLY}:
        return _string(row.get("projected_url") or row.get("selected_url") or decision.get("official_url"))
    if lane in {C1, C2}:
        return _string(row.get("canonical_url"))
    return ""


def _row_discusses_current_work(row: dict[str, Any], blocking_reason: str) -> bool:
    lane = _normalized_lane(row)
    if lane == C3:
        return False
    if lane == C2:
        return True
    if lane == C1:
        return _string(row.get("search_gate")) in SEARCH_OK_FOR_CONTRACT_CASE and _grade(row.get("evidence_grade")) in {"strong", "medium"}
    if lane == SG_PUBLISH:
        decision = _projection_decision(row)
        gate_state = _dict(row.get("promotion_gate_state"))
        return bool(
            not blocking_reason
            and _string(row.get("projected_status")) == "safe_resolved"
            and _grade(row.get("evidence_grade")) in {"strong", "medium"}
            and (
                decision.get("publish_allowed") is True
                or _string(decision.get("status")) == "publish"
                or gate_state.get("row_discusses_work_as_work") is True
            )
        )
    return False


def _contract_action(row: dict[str, Any], decision_status: str, blocking_reason: str) -> str:
    lane = _normalized_lane(row)
    if lane == C1 and decision_status == "publish":
        return "expected_title_restore_contract_case"
    if lane == C1:
        return "candidate_scrub_no_publish_contract_case"
    if lane == SG_PUBLISH and decision_status == "publish":
        return "expected_title_restore_contract_case"
    if lane in {SG_PUBLISH, SG_CANDIDATE_ONLY}:
        return "candidate_scrub_no_publish_contract_case"
    if lane == C2:
        return "canonical_variant_policy_hold_contract_case"
    if lane == C3:
        return "stronger_evidence_hard_hold_contract_case"
    return "unknown_contract_lane_review"


def _build_row(row: dict[str, Any]) -> dict[str, Any]:
    lane = _normalized_lane(row)
    target_title = _target_title(row)
    target_url = _target_url(row)
    blocking_reason = _contract_blocking_reason(row)
    row_discusses_work = _row_discusses_current_work(row, blocking_reason)
    scope_kind = "current_work" if row_discusses_work else "context_only"
    evidence_grade = _grade(row.get("evidence_grade"))
    reason_code = blocking_reason or (
        "shared_gate_projection_current_work" if lane in {SG_PUBLISH, SG_CANDIDATE_ONLY} else "post_verdict_source_native_contract_case"
    )
    direct_bridge_sources = ["canonical_source_native_verdict", lane]
    if lane in {SG_PUBLISH, SG_CANDIDATE_ONLY}:
        direct_bridge_sources = ["source_native_review", "shared_promotion_gate_wiring_required", lane]
    state = GroundingState(
        post_id=row.get("post_id"),
        candidate_title=target_title,
        candidate_url=target_url,
        source="shared_gate_projection_contract_plan" if lane in {SG_PUBLISH, SG_CANDIDATE_ONLY} else "post_verdict_contract_plan",
        official_title_exists=bool(target_title),
        row_discusses_work_as_work=row_discusses_work,
        title_resolution_state="resolved" if row_discusses_work else "context_only",
        work_resolution="resolved" if row_discusses_work else "unresolved",
        discussion_type="review",
        scope=ScopeState(
            scope_kind=scope_kind,
            confidence="high" if evidence_grade == "strong" else "medium",
            direct_bridge_sources=direct_bridge_sources,
            competing_candidates=[_string(row.get("current_projection_candidate_title"))],
            conflict_reason_codes=[blocking_reason] if blocking_reason else [],
        ),
    )
    evidence = [
        EvidenceRecord(
            kind="post_verdict_source_native_contract",
            strength=evidence_grade,
            source_path_or_snippet=_string(row.get("rationale_ko")),
            supports_publish=bool(row_discusses_work and not blocking_reason),
            reason_code=reason_code,
        )
    ]
    decision = can_publish_title(state, evidence)
    action = _contract_action(row, decision.status, blocking_reason)
    return {
        "post_id": row.get("post_id"),
        "contract_batch_lane": lane,
        "canonical_verdict": row.get("canonical_verdict"),
        "search_gate": row.get("search_gate"),
        "evidence_grade": row.get("evidence_grade"),
        "target_title": target_title or None,
        "target_url": target_url or None,
        "current_projection_candidate_title": row.get("current_projection_candidate_title"),
        "current_projection_candidate_url": row.get("current_projection_candidate_url"),
        "source_projected_status": row.get("projected_status"),
        "source_promotion_decision": row.get("promotion_decision"),
        "source_publish_contract_trace": row.get("publish_contract_trace"),
        "contract_blocking_reason": blocking_reason or None,
        "contract_action": action,
        "promotion_decision": decision.to_dict(),
        "promotion_gate_state": state.to_dict(),
        "promotion_gate_evidence": [record.to_dict() for record in evidence],
        "runtime_replay_allowed": False,
        "contract_test_required_before_runtime": lane in CONTRACT_TEST_LANES,
        "stronger_evidence_required_before_runtime": lane == C3,
        "rationale_ko": row.get("rationale_ko"),
        "evidence_refs": row.get("evidence_refs") or [],
    }


def build_plan(
    queue: dict[str, Any],
    *,
    plan_id: str,
    generated_at: str | None = None,
) -> dict[str, Any]:
    rows = [_build_row(row) for row in _rows(queue)]
    validation_issues: list[dict[str, Any]] = []
    for row in rows:
        if not row.get("target_title") and row.get("contract_batch_lane") in TITLE_REQUIRED_LANES:
            validation_issues.append({"post_id": row.get("post_id"), "issue": "missing_target_title"})
        if row["promotion_decision"].get("bypassed_gate"):
            validation_issues.append({"post_id": row.get("post_id"), "issue": "promotion_gate_bypassed"})
        if row.get("runtime_replay_allowed"):
            validation_issues.append({"post_id": row.get("post_id"), "issue": "runtime_replay_allowed_before_contract"})

    action_counts = Counter(_string(row.get("contract_action")) for row in rows)
    status_counts = Counter(_string(row["promotion_decision"].get("status")) for row in rows)
    lane_counts = Counter(_string(row.get("contract_batch_lane")) for row in rows)
    blocking_counts = Counter(_string(row.get("contract_blocking_reason")) for row in rows if row.get("contract_blocking_reason"))
    return {
        "report_type": "post_verdict_promotion_gate_contract_plan",
        "plan_id": plan_id,
        "generated_at": generated_at or datetime.now().replace(microsecond=0).isoformat(),
        "source_contract_queue": queue.get("queue_id"),
        "gate": "NO-GO" if validation_issues else "REVIEW-LOCKED",
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "summary": {
            "source_queue_rows": len(_rows(queue)),
            "contract_plan_rows": len(rows),
            "validation_issue_count": len(validation_issues),
            "contract_batch_lane_counts": dict(lane_counts),
            "contract_action_counts": dict(action_counts),
            "promotion_decision_status_counts": dict(status_counts),
            "contract_blocking_reason_counts": dict(blocking_counts),
            "runtime_replay_allowed_rows": 0,
            "contract_test_required_rows": sum(1 for row in rows if row.get("contract_test_required_before_runtime")),
            "stronger_evidence_required_rows": sum(1 for row in rows if row.get("stronger_evidence_required_before_runtime")),
            "full375_collateral_gate": "NO-GO",
            "completion_gate": "adjusted full375 collateral GO + full_scan path",
        },
        "validation_issues": validation_issues,
        "rows": rows,
        "approval_boundary": {
            "contract_plan_is_not_runtime_replay": True,
            "promotion_decision_publish_is_contract_case_only": True,
            "runtime_replay_before_contract_tests_forbidden": True,
            "full375_collateral_remains_no_go": True,
        },
    }


def write_markdown(path: Path, plan: dict[str, Any]) -> None:
    summary = plan["summary"]
    lines = [
        f"# {plan.get('plan_id')}",
        "",
        "Post-verdict contract queue를 shared `can_publish_title` gate 입력으로 변환한 계약 계획이다. "
        "SG projection과 C1/C2는 contract test 입력이고, C3는 stronger evidence 확인 전까지 release를 열지 않는다. "
        "이 산출물은 runtime replay 허가가 아니다.",
        "",
        "## 요약",
        "",
        f"- gate: `{plan['gate']}`",
        f"- semantic_quality: `{plan['semantic_quality']}`",
        f"- full_scan_approval: `{str(plan['full_scan_approval']).lower()}`",
        f"- contract_plan_rows: `{summary['contract_plan_rows']}`",
        f"- validation_issue_count: `{summary['validation_issue_count']}`",
        f"- contract_action_counts: `{summary['contract_action_counts']}`",
        f"- promotion_decision_status_counts: `{summary['promotion_decision_status_counts']}`",
        f"- runtime_replay_allowed_rows: `{summary['runtime_replay_allowed_rows']}`",
        f"- full375 collateral: `{summary['full375_collateral_gate']}`",
        "",
        "## 계약 액션",
        "",
    ]
    for action, count in sorted((summary.get("contract_action_counts") or {}).items()):
        lines.append(f"- `{action}`: `{count}`")
    lines.extend(["", "## 행별 계획", ""])
    for row in plan.get("rows") or []:
        lines.append(
            f"- `{row.get('post_id')}` lane=`{row.get('contract_batch_lane')}` "
            f"action=`{row.get('contract_action')}` decision=`{row.get('promotion_decision', {}).get('status')}` "
            f"target=`{row.get('target_title')}` block=`{row.get('contract_blocking_reason')}`"
        )
    lines.extend(["", "## Gate 해석", ""])
    lines.append(
        "Post-verdict C1 또는 SG shared-gate projection 일부는 expected title restore contract case로 정리되지만 이는 contract test 입력일 뿐이다. "
        "C2는 canonical variant policy가 닫히기 전까지 candidate-only로 유지하고, "
        "C3는 stronger evidence/native-web 확인 전까지 hard hold로 둔다. "
        "따라서 goal은 `ACTIVE / NOT_COMPLETE`이고 완료 기준은 계속 `adjusted full375 collateral GO + full_scan 경로 정의`다."
    )
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build shared promotion-gate contract plan for post-verdict rows.")
    parser.add_argument("--contract-queue", required=True, type=Path)
    parser.add_argument("--plan-id", default="post_verdict_promotion_gate_contract_plan")
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-md", required=True, type=Path)
    parser.add_argument("--fail-on-validation-issue", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    plan = build_plan(load_json(args.contract_queue), plan_id=args.plan_id)
    write_json(args.output_json, plan)
    write_markdown(args.output_md, plan)
    print(json.dumps({"gate": plan["gate"], "summary": plan["summary"]}, ensure_ascii=False, indent=2))
    if args.fail_on_validation_issue and plan["validation_issues"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
