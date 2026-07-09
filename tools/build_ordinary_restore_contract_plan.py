from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from tools.test_run_dashboard_policy import test_run_execution_contract
except ModuleNotFoundError:  # direct script execution: python tools/build_ordinary_restore_contract_plan.py
    from test_run_dashboard_policy import test_run_execution_contract

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


RESTORE_LANE = "shared_gate_restore_contract_review"
RESTORE_ACTION = "expected_title_restore_contract_case"
MISMATCH_REVIEW_ACTION = "restore_target_runtime_mismatch_review_required"
OFFICIAL_MISSING_ACTION = "official_support_missing_restore_hold_contract_case"
OFFICIAL_REF_MARKERS = (
    "novelpia.com",
    "novel.munpia.com",
    "mm.munpia.com",
    "page.kakao.com",
    "ridibooks.com",
    "series.naver.com",
)


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


def _string(value: Any) -> str:
    return str(value or "").strip()


def _compact(value: Any) -> str:
    return "".join(ch for ch in _string(value).lower() if ch.isalnum())


def _same_title(left: Any, right: Any) -> bool:
    return bool(_compact(left) and _compact(left) == _compact(right))


def _counter_to_dict(counter: Counter[str]) -> dict[str, int]:
    return {key: counter[key] for key in sorted(counter)}


def _post_id(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _grade(value: Any) -> str:
    text = _string(value).lower()
    return text if text in {"strong", "medium", "weak", "missing"} else "medium"


def _official_refs(row: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    for item in _as_list(row.get("evidence_refs")):
        text = _string(item)
        if text and any(marker in text for marker in OFFICIAL_REF_MARKERS):
            refs.append(text)
    return refs


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    if not isinstance(rows, list):
        raise ValueError("payload must contain rows list")
    return [row for row in rows if isinstance(row, dict)]


def _index_runtime_audit(payload: dict[str, Any] | None) -> dict[int, dict[str, Any]]:
    if not payload:
        return {}
    indexed: dict[int, dict[str, Any]] = {}
    for row in _as_list(payload.get("rows")):
        if not isinstance(row, dict):
            continue
        post_id = _post_id(row.get("post_id"))
        if post_id is not None:
            indexed[post_id] = row
    return indexed


def _search_condition(runtime_row: dict[str, Any] | None) -> str:
    if not runtime_row:
        return "runtime_expected_audit_missing"
    status = _string(runtime_row.get("search_status"))
    if status == "SEARCH_DEGRADED":
        return "search_degraded_condition"
    if status == "SEARCH_DEGRADED_RECOVERED":
        return "search_recovered_condition"
    if status:
        return status.lower()
    return "search_status_missing"


def _append_unique(values: Any, *items: str) -> list[str]:
    out = [str(value) for value in (values or []) if str(value).strip()] if isinstance(values, list) else []
    for item in items:
        if item and item not in out:
            out.append(item)
    return out


def _runtime_target_mismatch(selected_title: str, runtime_row: dict[str, Any] | None) -> bool:
    if not runtime_row:
        return False
    if _string(runtime_row.get("audit_status")) != "FAIL_SAFE_RESOLVED_TITLE_MISMATCH":
        return False
    actual_title = _string(runtime_row.get("actual_title"))
    return bool(selected_title and actual_title and not _same_title(selected_title, actual_title))


def _is_restore_lane(row: dict[str, Any]) -> bool:
    return row.get("primary_lane") == RESTORE_LANE or row.get("dispatch_lane") == RESTORE_LANE


def _build_plan_row(row: dict[str, Any], runtime_row: dict[str, Any] | None) -> dict[str, Any]:
    post_id = _post_id(row.get("post_id"))
    selected_title = _string(row.get("selected_title"))
    refs = _official_refs(row)
    target_url = refs[0] if refs else ""
    evidence_grade = _grade(row.get("evidence_grade"))
    confidence = "high" if evidence_grade == "strong" else "medium"
    direct_sources = [
        "ordinary_residual_source_native_verdict",
        RESTORE_LANE,
    ]
    if refs:
        direct_sources.append("official_support_ref")

    state = GroundingState(
        post_id=post_id,
        candidate_title=selected_title,
        candidate_url=target_url,
        source="ordinary_residual_restore_contract_plan",
        official_title_exists=bool(selected_title and refs),
        row_discusses_work_as_work=bool(selected_title),
        title_resolution_state="resolved" if selected_title else "unresolved",
        work_resolution="resolved" if selected_title else "unresolved",
        discussion_type="review",
        scope=ScopeState(
            scope_kind="current_work" if selected_title else "unknown",
            confidence=confidence,
            direct_bridge_sources=direct_sources,
            competing_candidates=[_string(runtime_row.get("actual_title"))] if runtime_row else [],
            conflict_reason_codes=[],
        ),
    )
    evidence = [
        EvidenceRecord(
            kind="ordinary_residual_source_native_restore_contract",
            strength=evidence_grade,
            source_path_or_snippet=_string(row.get("rationale_ko")),
            supports_publish=evidence_grade in {"strong", "medium"} and bool(selected_title and refs),
            reason_code="ordinary_residual_supported_restore_contract_case",
        )
    ]
    if refs:
        evidence.append(
            EvidenceRecord(
                kind="official_support_ref",
                strength="strong",
                source_path_or_snippet=refs[0],
                supports_publish=True,
                reason_code="official_support_ref_present",
            )
        )
    decision = can_publish_title(state, evidence)
    runtime_audit_status = _string(runtime_row.get("audit_status")) if runtime_row else ""
    search_condition = _search_condition(runtime_row)
    mismatch_review_required = _runtime_target_mismatch(selected_title, runtime_row)
    decision_dict = decision.to_dict()
    state_dict = state.to_dict()
    evidence_dicts = [item.to_dict() for item in evidence]
    if mismatch_review_required:
        actual_title = _string(runtime_row.get("actual_title"))
        actual_url = _string(runtime_row.get("actual_url"))
        decision_dict.update(
            {
                "status": "candidate_only",
                "publish_allowed": False,
                "official_title": None,
                "official_url": None,
                "candidate_preserved": True,
                "reason_codes": _append_unique(
                    decision_dict.get("reason_codes"),
                    "restore_target_runtime_mismatch_review_required",
                    "runtime_safe_resolved_title_conflicts_with_restore_target",
                ),
                "bypassed_gate": False,
            }
        )
        scope = state_dict.get("scope") if isinstance(state_dict.get("scope"), dict) else {}
        scope["conflict_reason_codes"] = _append_unique(
            scope.get("conflict_reason_codes"),
            "runtime_safe_resolved_title_conflicts_with_restore_target",
        )
        scope["competing_candidates"] = _append_unique(scope.get("competing_candidates"), actual_title)
        state_dict["scope"] = scope
        evidence_dicts.append(
            {
                "kind": "runtime_expected_title_mismatch",
                "strength": "strong",
                "source_path_or_snippet": (
                    f"runtime actual title `{actual_title}` conflicts with restore target `{selected_title}`"
                ),
                "supports_publish": False,
                "reason_code": "runtime_safe_resolved_title_conflicts_with_restore_target",
                "actual_title": actual_title or None,
                "actual_url": actual_url or None,
            }
        )
    contract_action = RESTORE_ACTION if decision.status == "publish" else "candidate_scrub_no_publish_contract_case"
    if selected_title and not refs and not mismatch_review_required:
        contract_action = OFFICIAL_MISSING_ACTION
    if mismatch_review_required:
        contract_action = MISMATCH_REVIEW_ACTION
    return {
        "post_id": post_id,
        "contract_origin": "ordinary_residual_shared_gate_restore",
        "contract_batch_lane": "O1_shared_gate_restore_contract",
        "source_dispatch_lane": row.get("primary_lane") or row.get("dispatch_lane"),
        "triage_bucket": row.get("triage_bucket"),
        "review_label": row.get("review_label"),
        "source_native_verdict": row.get("source_native_verdict"),
        "evidence_grade": row.get("evidence_grade"),
        "target_title": selected_title or None,
        "target_url": target_url or None,
        "official_support_refs": refs,
        "official_support_ref_count": len(refs),
        "current_projection_candidate_title": _string(runtime_row.get("actual_title")) or None if runtime_row else None,
        "current_projection_candidate_url": _string(runtime_row.get("actual_url")) or None if runtime_row else None,
        "runtime_expected_audit_status": runtime_audit_status or None,
        "runtime_search_status": _string(runtime_row.get("search_status")) or None if runtime_row else None,
        "search_condition_tag": search_condition,
        "contract_action": contract_action,
        "promotion_decision": decision_dict,
        "promotion_gate_state": state_dict,
        "promotion_gate_evidence": evidence_dicts,
        "release_candidate_not_approval": contract_action == RESTORE_ACTION and decision_dict.get("status") == "publish",
        "official_support_missing_before_publish": contract_action == OFFICIAL_MISSING_ACTION,
        "restore_target_mismatch_review_required": mismatch_review_required,
        "search_review_required_before_approval": search_condition in {
            "search_degraded_condition",
            "search_status_missing",
            "runtime_expected_audit_missing",
        },
        "runtime_replay_allowed": False,
        "contract_application_required_before_runtime": True,
        "full375_recheck_required": True,
        "full_scan_approval": False,
        "rationale_ko": row.get("rationale_ko"),
        "evidence_refs": row.get("evidence_refs") or [],
    }


def build_plan(
    *,
    dispatch: dict[str, Any],
    runtime_expected_audit: dict[str, Any] | None = None,
    plan_id: str,
    generated_at: str | None = None,
) -> dict[str, Any]:
    runtime_by_post_id = _index_runtime_audit(runtime_expected_audit)
    selected = [row for row in _rows(dispatch) if _is_restore_lane(row)]
    rows = [_build_plan_row(row, runtime_by_post_id.get(_post_id(row.get("post_id")) or -1)) for row in selected]
    validation_issues: list[dict[str, Any]] = []
    for row in rows:
        if not row.get("post_id"):
            validation_issues.append({"issue": "missing_post_id", "row": row})
        if not row.get("target_title"):
            validation_issues.append({"issue": "missing_target_title", "post_id": row.get("post_id")})
        if row["promotion_decision"].get("bypassed_gate"):
            validation_issues.append({"issue": "promotion_gate_bypassed", "post_id": row.get("post_id")})
        if row.get("runtime_replay_allowed"):
            validation_issues.append({"issue": "runtime_replay_allowed_before_contract", "post_id": row.get("post_id")})

    action_counts = Counter(_string(row.get("contract_action")) for row in rows)
    decision_counts = Counter(_string(row["promotion_decision"].get("status")) for row in rows)
    grade_counts = Counter(_string(row.get("evidence_grade")) for row in rows)
    runtime_audit_counts = Counter(_string(row.get("runtime_expected_audit_status")) or "missing" for row in rows)
    search_counts = Counter(_string(row.get("search_condition_tag")) for row in rows)
    return {
        "report_type": "ordinary_residual_restore_contract_plan",
        "plan_id": plan_id,
        "generated_at": generated_at or datetime.now().replace(microsecond=0).isoformat(),
        "source_dispatch": dispatch.get("dispatch_id") or dispatch.get("batch_id"),
        "gate": "NO-GO" if validation_issues else "REVIEW-LOCKED",
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "summary": {
            "source_dispatch_rows": len(_rows(dispatch)),
            "restore_contract_plan_rows": len(rows),
            "validation_issue_count": len(validation_issues),
            "contract_action_counts": _counter_to_dict(action_counts),
            "promotion_decision_status_counts": _counter_to_dict(decision_counts),
            "evidence_grade_counts": _counter_to_dict(grade_counts),
            "runtime_expected_audit_status_counts": _counter_to_dict(runtime_audit_counts),
            "search_condition_counts": _counter_to_dict(search_counts),
            "official_support_ref_missing_rows": sum(1 for row in rows if not row.get("official_support_refs")),
            "official_support_missing_hold_rows": sum(
                1 for row in rows if row.get("official_support_missing_before_publish")
            ),
            "search_review_required_before_approval_rows": sum(
                1 for row in rows if row.get("search_review_required_before_approval")
            ),
            "release_candidate_not_approval_rows": sum(1 for row in rows if row.get("release_candidate_not_approval")),
            "publish_allowed_rows": 0,
            "runtime_replay_allowed_rows": 0,
            "full375_collateral_gate": "NO-GO",
            "completion_gate": "adjusted full375 collateral GO + full_scan path",
        },
        "execution_contract": test_run_execution_contract(len(rows)),
        "validation_issues": validation_issues,
        "rows": rows,
        "approval_boundary": {
            "restore_contract_plan_is_not_approval": True,
            "promotion_decision_publish_is_contract_case_only": True,
            "contract_application_required_before_runtime": True,
            "runtime_replay_allowed": False,
            "full375_collateral_remains_no_go": True,
            "full_scan_approval": False,
        },
    }


def write_markdown(plan: dict[str, Any], path: Path) -> None:
    summary = plan["summary"]
    execution_contract = plan.get("execution_contract") or {}
    dashboard_contract = execution_contract.get("dashboard_contract") or {}
    lines = [
        f"# {plan.get('plan_id')}",
        "",
        f"`{plan.get('source_dispatch')}` shared-gate restore lane을 shared `can_publish_title` gate로 통과시킨 계약 계획이다. "
        "이 산출물은 runtime replay 허가나 full_scan approval이 아니다.",
        "",
        "## 요약",
        "",
        f"- source_dispatch: `{plan.get('source_dispatch')}`",
        f"- gate: `{plan.get('gate')}`",
        f"- restore_contract_plan_rows: `{summary.get('restore_contract_plan_rows')}`",
        f"- validation_issue_count: `{summary.get('validation_issue_count')}`",
        f"- contract_action_counts: `{summary.get('contract_action_counts')}`",
        f"- promotion_decision_status_counts: `{summary.get('promotion_decision_status_counts')}`",
        f"- evidence_grade_counts: `{summary.get('evidence_grade_counts')}`",
        f"- search_condition_counts: `{summary.get('search_condition_counts')}`",
        f"- official_support_ref_missing_rows: `{summary.get('official_support_ref_missing_rows')}`",
        f"- official_support_missing_hold_rows: `{summary.get('official_support_missing_hold_rows')}`",
        f"- search_review_required_before_approval_rows: `{summary.get('search_review_required_before_approval_rows')}`",
        f"- release_candidate_not_approval_rows: `{summary.get('release_candidate_not_approval_rows')}`",
        f"- publish_allowed_rows: `{summary.get('publish_allowed_rows')}`",
        f"- runtime_replay_allowed_rows: `{summary.get('runtime_replay_allowed_rows')}`",
        "- semantic_quality: `REVIEW-LOCKED`",
        "- full_scan_approval: `false`",
        "",
        "## 테스트런 실행 계약",
        "",
        f"- policy: `{execution_contract.get('policy')}`",
        f"- requested_parallel: `{execution_contract.get('requested_parallel')}`",
        f"- expected_effective_parallel: `{execution_contract.get('expected_effective_parallel')}`",
        f"- forbidden_flags: `{execution_contract.get('forbidden_flags')}`",
        f"- dashboard_policy: `{dashboard_contract.get('dashboard_policy')}`",
        f"- dashboard_url: `{dashboard_contract.get('dashboard_url')}`",
        f"- dashboard_gate: `{execution_contract.get('dashboard_gate')}`",
        "- Dashboard는 진행 확인 도구이며 semantic/full_scan approval 근거가 아니다.",
        "",
        "## 승인 경계",
        "",
        "- `promotion_decision=publish`는 contract case일 뿐 approval이 아니다.",
        "- 공식 detail URL이 없는 restore 후보는 `official_support_missing_restore_hold_contract_case`로 보존하고 publish하지 않는다.",
        "- Projection 적용, lane별 검증, full375 collateral 재확인 전 runtime replay를 열지 않는다.",
        "- Search degraded/status missing 조건은 full_scan approval 전에 별도 확인해야 한다.",
            "- 완료 기준은 계속 `adjusted full375 collateral GO + full_scan 경로 정의`다.",
        "",
        "## Rows",
        "",
    ]
    for row in plan.get("rows") or []:
        lines.append(
            f"- `{row.get('post_id')}` action=`{row.get('contract_action')}` "
            f"decision=`{row.get('promotion_decision', {}).get('status')}` target=`{row.get('target_title')}` "
            f"runtime_audit=`{row.get('runtime_expected_audit_status')}` search=`{row.get('search_condition_tag')}` "
            f"official_refs=`{row.get('official_support_ref_count')}`"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build shared-gate restore contract plan for ordinary residual rows.")
    parser.add_argument("--dispatch", required=True, type=Path)
    parser.add_argument("--runtime-expected-audit", type=Path, default=None)
    parser.add_argument("--plan-id", default="loop554_ordinary_restore_shared_gate_contract_plan")
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-md", required=True, type=Path)
    parser.add_argument("--fail-on-validation-issue", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    audit = load_json(args.runtime_expected_audit) if args.runtime_expected_audit else None
    plan = build_plan(dispatch=load_json(args.dispatch), runtime_expected_audit=audit, plan_id=args.plan_id)
    write_json(args.output_json, plan)
    write_markdown(plan, args.output_md)
    print(json.dumps({"gate": plan["gate"], "summary": plan["summary"]}, ensure_ascii=False, indent=2))
    if args.fail_on_validation_issue and plan["validation_issues"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
