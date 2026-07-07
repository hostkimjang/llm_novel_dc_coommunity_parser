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


LABEL_TO_LANE = {
    "ACCEPT": "T1_expected_audit_update_or_blind_acceptance_contract",
    "HOLD": "T2_native_web_disambiguation_hold",
    "REPROCESS": "T3_canonical_cleanup_or_url_correction_contract",
}

LABEL_TO_ACTION = {
    "ACCEPT": "expected_audit_update_exclusion_contract_case",
    "HOLD": "native_web_disambiguation_hold_contract_case",
    "REPROCESS": "canonical_cleanup_or_url_correction_contract_case",
}

LABEL_TO_BLOCKING_REASON = {
    "ACCEPT": "",
    "HOLD": "native_web_disambiguation_required",
    "REPROCESS": "canonical_cleanup_required",
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


def _rows(verdicts: dict[str, Any]) -> list[dict[str, Any]]:
    rows = verdicts.get("rows")
    if not isinstance(rows, list):
        raise ValueError("title mismatch verdict file must contain rows list")
    return [row for row in rows if isinstance(row, dict)]


def _grade(value: Any) -> str:
    text = _string(value).lower()
    return text if text in {"strong", "medium", "weak", "missing"} else "medium"


def _label(row: dict[str, Any]) -> str:
    return _string(row.get("review_label")).upper()


def _target_title(row: dict[str, Any]) -> str:
    label = _label(row)
    if label == "ACCEPT":
        return _string(row.get("selected_title") or row.get("actual_title"))
    if label == "REPROCESS":
        return _string(row.get("expected_title") or row.get("selected_title") or row.get("actual_title"))
    return _string(row.get("expected_title") or row.get("selected_title") or row.get("actual_title"))


def _target_url(row: dict[str, Any]) -> str:
    if _label(row) == "ACCEPT":
        return _string(row.get("selected_url"))
    if _label(row) == "REPROCESS":
        return _string(row.get("selected_url") or row.get("expected_url") or row.get("actual_url"))
    return ""


def _row_discusses_work(row: dict[str, Any], blocking_reason: str) -> bool:
    if blocking_reason:
        return False
    return _label(row) == "ACCEPT" and bool(_target_title(row))


def _validation_issues(row: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    label = _label(row)
    if label not in LABEL_TO_LANE:
        issues.append("unknown_review_label")
    if not _target_title(row):
        issues.append("missing_target_title")
    if label == "ACCEPT" and not _string(row.get("selected_title") or row.get("actual_title")):
        issues.append("accept_without_actual_title")
    if label == "REPROCESS" and not _string(row.get("expected_title")):
        issues.append("reprocess_without_expected_title")
    return issues


def _build_row(row: dict[str, Any]) -> dict[str, Any]:
    label = _label(row)
    lane = LABEL_TO_LANE.get(label, "T0_invalid_title_mismatch_contract_lane")
    action = LABEL_TO_ACTION.get(label, "review_invalid_title_mismatch_verdict")
    blocking_reason = LABEL_TO_BLOCKING_REASON.get(label, "invalid_title_mismatch_verdict")
    target_title = _target_title(row)
    target_url = _target_url(row)
    evidence_grade = _grade(row.get("evidence_grade"))
    row_discusses_work = _row_discusses_work(row, blocking_reason)
    scope_kind = "current_work" if row_discusses_work else "context_only"
    reason_code = blocking_reason or "title_mismatch_expected_update_contract_case"
    state = GroundingState(
        post_id=row.get("post_id"),
        candidate_title=target_title,
        candidate_url=target_url,
        source="title_mismatch_verdict_contract_plan",
        official_title_exists=bool(target_title),
        row_discusses_work_as_work=row_discusses_work,
        title_resolution_state="resolved" if row_discusses_work else "context_only",
        work_resolution="resolved" if row_discusses_work else "unresolved",
        discussion_type="review",
        scope=ScopeState(
            scope_kind=scope_kind,
            confidence="high" if evidence_grade == "strong" else "medium",
            direct_bridge_sources=["title_mismatch_source_native_verdict", lane],
            competing_candidates=[_string(row.get("actual_title")), _string(row.get("expected_title"))],
            conflict_reason_codes=[blocking_reason] if blocking_reason else [],
        ),
    )
    evidence = [
        EvidenceRecord(
            kind="title_mismatch_source_native_verdict",
            strength=evidence_grade,
            source_path_or_snippet=_string(row.get("rationale_ko")),
            supports_publish=bool(row_discusses_work and not blocking_reason),
            reason_code=reason_code,
        )
    ]
    decision = can_publish_title(state, evidence)
    return {
        "post_id": row.get("post_id"),
        "contract_batch_lane": lane,
        "review_label": label,
        "source_native_verdict": row.get("source_native_verdict"),
        "evidence_grade": row.get("evidence_grade"),
        "expected_title": row.get("expected_title"),
        "actual_title": row.get("actual_title"),
        "target_title": target_title or None,
        "target_url": target_url or None,
        "contract_blocking_reason": blocking_reason or None,
        "contract_action": action,
        "promotion_decision": decision.to_dict(),
        "promotion_gate_state": state.to_dict(),
        "promotion_gate_evidence": [record.to_dict() for record in evidence],
        "runtime_replay_allowed": False,
        "contract_test_required_before_runtime": label in {"ACCEPT", "REPROCESS"},
        "stronger_evidence_required_before_runtime": label == "HOLD",
        "rationale_ko": row.get("rationale_ko"),
        "evidence_refs": row.get("evidence_refs") or [],
    }


def build_plan(
    verdicts: dict[str, Any],
    *,
    plan_id: str,
    generated_at: str | None = None,
) -> dict[str, Any]:
    source_rows = _rows(verdicts)
    validation_issues = [
        {"post_id": row.get("post_id"), "issues": issues}
        for row in source_rows
        if (issues := _validation_issues(row))
    ]
    rows = [_build_row(row) for row in source_rows]
    action_counts = Counter(_string(row.get("contract_action")) for row in rows)
    lane_counts = Counter(_string(row.get("contract_batch_lane")) for row in rows)
    label_counts = Counter(_string(row.get("review_label")) for row in rows)
    status_counts = Counter(_string(row["promotion_decision"].get("status")) for row in rows)
    blocking_counts = Counter(_string(row.get("contract_blocking_reason")) for row in rows if row.get("contract_blocking_reason"))
    return {
        "report_type": "title_mismatch_verdict_contract_plan",
        "plan_id": plan_id,
        "generated_at": generated_at or datetime.now().replace(microsecond=0).isoformat(),
        "source_verdicts": verdicts.get("review_id"),
        "source_batch": verdicts.get("source_batch"),
        "source_packet": verdicts.get("source_packet"),
        "gate": "NO-GO" if validation_issues else "REVIEW-LOCKED",
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "summary": {
            "source_verdict_rows": len(source_rows),
            "contract_plan_rows": len(rows),
            "validation_issue_count": len(validation_issues),
            "review_label_counts": dict(label_counts),
            "contract_batch_lane_counts": dict(lane_counts),
            "contract_action_counts": dict(action_counts),
            "promotion_decision_status_counts": dict(status_counts),
            "contract_blocking_reason_counts": dict(blocking_counts),
            "runtime_replay_allowed_rows": 0,
            "contract_test_required_rows": sum(1 for row in rows if row.get("contract_test_required_before_runtime")),
            "stronger_evidence_required_rows": sum(1 for row in rows if row.get("stronger_evidence_required_before_runtime")),
            "full375_collateral_gate": "NO-GO",
            "completion_gate": "full375 collateral GO + full_scan path",
        },
        "validation_issues": validation_issues,
        "rows": rows,
        "approval_boundary": {
            "title_mismatch_plan_is_not_runtime_replay": True,
            "accept_label_is_expected_audit_update_contract_only": True,
            "runtime_replay_before_contract_tests_forbidden": True,
            "full375_collateral_remains_no_go": True,
        },
    }


def write_markdown(path: Path, plan: dict[str, Any]) -> None:
    summary = plan["summary"]
    lines = [
        f"# {plan.get('plan_id')}",
        "",
        "Title mismatch source-native verdict를 shared `can_publish_title` gate 입력으로 변환한 계약 계획이다. "
        "`ACCEPT`도 expected audit update/exclusion 계약일 뿐 runtime approval이 아니다.",
        "",
        "## 요약",
        "",
        f"- gate: `{plan['gate']}`",
        f"- semantic_quality: `{plan['semantic_quality']}`",
        f"- full_scan_approval: `{str(plan['full_scan_approval']).lower()}`",
        f"- contract_plan_rows: `{summary['contract_plan_rows']}`",
        f"- validation_issue_count: `{summary['validation_issue_count']}`",
        f"- review_label_counts: `{summary['review_label_counts']}`",
        f"- contract_action_counts: `{summary['contract_action_counts']}`",
        f"- promotion_decision_status_counts: `{summary['promotion_decision_status_counts']}`",
        f"- runtime_replay_allowed_rows: `{summary['runtime_replay_allowed_rows']}`",
        f"- full375 collateral: `{summary['full375_collateral_gate']}`",
        "",
        "## 행별 계획",
        "",
    ]
    for row in plan.get("rows") or []:
        lines.append(
            f"- `{row.get('post_id')}` label=`{row.get('review_label')}` lane=`{row.get('contract_batch_lane')}` "
            f"action=`{row.get('contract_action')}` decision=`{row.get('promotion_decision', {}).get('status')}` "
            f"target=`{row.get('target_title')}` block=`{row.get('contract_blocking_reason')}`"
        )
    lines.extend(["", "## Gate 해석", ""])
    lines.append(
        "`ACCEPT`는 expected baseline/update 계약으로만 쓰고, `HOLD`는 native-web disambiguation 전까지 hard hold다. "
        "`REPROCESS`는 canonical cleanup 또는 URL correction 계약이 닫히기 전까지 runtime replay를 열지 않는다. "
        "따라서 full375 collateral은 계속 `NO-GO`이고 goal은 `ACTIVE / NOT_COMPLETE`다."
    )
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build shared promotion-gate contract plan for title mismatch verdict rows.")
    parser.add_argument("--verdicts", required=True, type=Path)
    parser.add_argument("--plan-id", default="title_mismatch_verdict_contract_plan")
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-md", required=True, type=Path)
    parser.add_argument("--fail-on-validation-issue", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    plan = build_plan(load_json(args.verdicts), plan_id=args.plan_id)
    write_json(args.output_json, plan)
    write_markdown(args.output_md, plan)
    print(json.dumps({"gate": plan["gate"], "summary": plan["summary"]}, ensure_ascii=False, indent=2))
    if args.fail_on_validation_issue and plan["validation_issues"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
