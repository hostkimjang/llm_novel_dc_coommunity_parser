from __future__ import annotations

import argparse
import copy
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
    build_publish_contract_trace,
    build_publish_ledger,
    can_publish_title,
)


NATIVE_WEB_HOLD = "native_web_disambiguation_hold_contract_case"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _string(value: Any) -> str:
    return str(value or "").strip()


def _rows(payload: Any, *, key: str = "rows") -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict) and isinstance(payload.get(key), list):
        return [row for row in payload[key] if isinstance(row, dict)]
    raise ValueError(f"payload must contain {key} list")


def _analysis(row: dict[str, Any]) -> dict[str, Any]:
    value = row.get("analysis_result")
    return value if isinstance(value, dict) else {}


def _identity(row: dict[str, Any]) -> dict[str, Any]:
    ident = _analysis(row).get("identity")
    return ident if isinstance(ident, dict) else {}


def _novel_identity(row: dict[str, Any]) -> dict[str, Any]:
    novel = _identity(row).get("novel_identity")
    return novel if isinstance(novel, dict) else {}


def _actions(row: dict[str, Any]) -> list[str]:
    raw = row.get("actions") or row.get("action") or []
    return sorted({_string(value) for value in raw if _string(value)}) if isinstance(raw, list) else []


def _image_catalog(row: dict[str, Any]) -> list[dict[str, Any]]:
    ident = _identity(row)
    analysis = _analysis(row).get("analysis")
    for value in (
        ident.get("image_evidence_catalog"),
        analysis.get("image_evidence_catalog") if isinstance(analysis, dict) else None,
    ):
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def _detected_titles(row: dict[str, Any]) -> list[dict[str, Any]]:
    analysis = _analysis(row).get("analysis")
    value = analysis.get("detected_titles") if isinstance(analysis, dict) else None
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _compact(value: Any) -> str:
    return "".join(ch for ch in _string(value).lower() if ch.isalnum())


def _matching_title(left: Any, right: Any) -> bool:
    return bool(_compact(left) and _compact(left) == _compact(right))


def _pre_gate_candidate(row: dict[str, Any]) -> dict[str, Any]:
    ident = _identity(row)
    trace = ident.get("publish_contract_trace")
    pre_gate = trace.get("pre_gate_candidate") if isinstance(trace, dict) else {}
    return pre_gate if isinstance(pre_gate, dict) else {}


def _first_candidate_title_url(dispatch_row: dict[str, Any], result_row: dict[str, Any]) -> tuple[str, str, str]:
    pre_gate = _pre_gate_candidate(result_row)
    if "image_native_review_required" in set(_actions(dispatch_row)):
        for image in _image_catalog(result_row):
            image_title = _string(image.get("explicit_work_title"))
            if image_title:
                pre_gate_url = _string(pre_gate.get("official_url")) if _matching_title(pre_gate.get("official_title"), image_title) else ""
                return image_title, pre_gate_url, "image_evidence_catalog.explicit_work_title"

    if _string(pre_gate.get("official_title")):
        return (
            _string(pre_gate.get("official_title")),
            _string(pre_gate.get("official_url")),
            "publish_contract_trace.pre_gate_candidate",
        )

    novel = _novel_identity(result_row)
    if _string(novel.get("official_title")):
        return _string(novel.get("official_title")), _string(novel.get("heretic_url")), "novel_identity"

    for item in _detected_titles(result_row):
        if _string(item.get("official_title")):
            return _string(item.get("official_title")), _string(item.get("heretic_url")), "analysis.detected_titles"

    if _string(dispatch_row.get("selected_title")):
        return _string(dispatch_row.get("selected_title")), _string(dispatch_row.get("selected_url")), "dispatch.selected_title"
    return "", "", "missing_candidate"


def _hold_scope_and_reason(dispatch_row: dict[str, Any], result_row: dict[str, Any]) -> tuple[str, str, str]:
    actions = set(_actions(dispatch_row))
    ident = _identity(result_row)
    source_verdict = _string(dispatch_row.get("source_native_verdict"))
    if "image_native_review_required" in actions:
        return (
            "image_ocr_derived_work",
            "image_ocr_or_platform_visual_requires_native_review",
            "이미지/OCR에서 작품 표면은 보이지만 현재 gate에서 public title publish 조건을 충족하지 못해 native-web/image 확인 전 no-release hold로 둔다.",
        )
    if "title_surface_specificity_review_required" in actions:
        return (
            "unknown",
            "title_surface_specificity_requires_native_confirmation",
            "짧거나 일반명사/작가명처럼 읽히는 표면이므로 native 확인 전 public title을 열지 않는다.",
        )
    if "character_bridge_review_required" in actions or "character" in source_verdict:
        return (
            "unknown",
            "character_bridge_requires_verified_work_link",
            "캐릭터/설정 표면과 후보 작품 사이의 직접 relation이 부족해 native 확인 전 public title을 열지 않는다.",
        )
    if _string(ident.get("title_resolution_state")) in {"unresolved_matchable", "ocr_explicit_title_unresolved"}:
        return (
            "unknown",
            "unresolved_matchable_requires_native_review",
            "현재 result가 unresolved 계열이라 native 확인 전 public title을 열지 않는다.",
        )
    return "unknown", "native_web_disambiguation_required", "native-web disambiguation 전 public title을 열지 않는다."


def _decision_for(
    *,
    post_id: Any,
    title: str,
    url: str,
    scope_kind: str,
    reason_code: str,
    source: str,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    scope = ScopeState(
        scope_kind=scope_kind,
        confidence="high" if title else "medium",
        direct_bridge_sources=[source],
        conflict_reason_codes=[reason_code],
    )
    state = GroundingState(
        post_id=post_id,
        candidate_title=title,
        candidate_url=url,
        source="remaining_native_hold_contract_plan",
        official_title_exists=bool(title),
        row_discusses_work_as_work=bool(title),
        title_resolution_state="unresolved_matchable",
        work_resolution="unresolved",
        discussion_type="review",
        scope=scope,
    )
    evidence = [
        EvidenceRecord(
            kind="native_web_hold_boundary",
            strength="medium",
            source_path_or_snippet=source,
            supports_publish=False,
            reason_code=reason_code,
        )
    ]
    decision = can_publish_title(state, evidence)
    decision_payload = decision.to_dict()
    decision_payload["scope"] = scope.to_dict()
    return decision_payload, state.to_dict(), [record.to_dict() for record in evidence], scope.to_dict()


def build_plan(
    *,
    dispatch: dict[str, Any],
    result_rows: list[dict[str, Any]],
    plan_id: str,
    result_path: Path,
    generated_at: str | None = None,
) -> dict[str, Any]:
    result_by_id = {_string(row.get("post_id")): row for row in result_rows if _string(row.get("post_id"))}
    rows: list[dict[str, Any]] = []
    validation_issues: list[dict[str, Any]] = []

    for dispatch_row in _rows(dispatch):
        post_id = dispatch_row.get("post_id")
        result_row = result_by_id.get(_string(post_id))
        if result_row is None:
            validation_issues.append({"post_id": post_id, "issue": "result_row_missing"})
            continue
        candidate_title, candidate_url, source = _first_candidate_title_url(dispatch_row, result_row)
        scope_kind, reason_code, rationale_ko = _hold_scope_and_reason(dispatch_row, result_row)
        decision, gate_state, evidence, scope_state = _decision_for(
            post_id=post_id,
            title=candidate_title,
            url=candidate_url,
            scope_kind=scope_kind,
            reason_code=reason_code,
            source=source,
        )
        if decision.get("publish_allowed"):
            validation_issues.append({"post_id": post_id, "issue": "hold_contract_decision_published"})
        rows.append(
            {
                "post_id": post_id,
                "contract_origin": plan_id,
                "contract_batch_lane": "remaining_native_web_image_hold",
                "contract_action": NATIVE_WEB_HOLD,
                "triage_bucket": dispatch_row.get("triage_bucket"),
                "review_label": "HOLD",
                "source_native_verdict": dispatch_row.get("source_native_verdict"),
                "evidence_grade": dispatch_row.get("evidence_grade") or "Weak",
                "target_title": None,
                "target_url": None,
                "current_projection_candidate_title": candidate_title or None,
                "current_projection_candidate_url": candidate_url or None,
                "candidate_source": source,
                "actions": _actions(dispatch_row),
                "promotion_decision": decision,
                "promotion_gate_state": gate_state,
                "promotion_gate_evidence": evidence,
                "scope_state": scope_state,
                "release_candidate_not_approval": False,
                "runtime_replay_allowed": False,
                "full375_recheck_required": True,
                "full_scan_approval": False,
                "rationale_ko": rationale_ko,
                "evidence_refs": [
                    f"{result_path.as_posix()}#post_id={post_id}",
                    *[str(ref) for ref in (dispatch_row.get("evidence_refs") or [])[:4]],
                ],
            }
        )

    action_counts = Counter(_string(row.get("contract_action")) for row in rows)
    decision_counts = Counter(_string((row.get("promotion_decision") or {}).get("status")) for row in rows)
    return {
        "report_type": "remaining_native_hold_contract_plan",
        "plan_id": plan_id,
        "generated_at": generated_at or datetime.now().replace(microsecond=0).isoformat(),
        "source_dispatch_id": dispatch.get("dispatch_id"),
        "source_result_path": str(result_path),
        "gate": "NO-GO" if validation_issues else "REVIEW-LOCKED",
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "summary": {
            "source_dispatch_rows": len(_rows(dispatch)),
            "contract_plan_rows": len(rows),
            "native_web_hold_contract_rows": len(rows),
            "release_candidate_not_approval_rows": 0,
            "no_publish_contract_rows": 0,
            "validation_issue_count": len(validation_issues),
            "contract_action_counts": dict(action_counts),
            "promotion_decision_status_counts": dict(decision_counts),
            "runtime_replay_allowed_rows": 0,
            "full375_collateral_gate": "NO-GO",
            "completion_gate": "adjusted full375 collateral GO + full_scan path",
        },
        "validation_issues": validation_issues,
        "rows": rows,
        "approval_boundary": {
            "native_web_hold_is_not_approval": True,
            "projection_scrub_required_for_leaked_public_identity": True,
            "runtime_replay_allowed_rows": 0,
            "full_scan_approval": False,
        },
    }


def _ensure_identity(row: dict[str, Any]) -> dict[str, Any]:
    analysis = row.setdefault("analysis_result", {})
    if not isinstance(analysis, dict):
        row["analysis_result"] = {}
        analysis = row["analysis_result"]
    ident = analysis.setdefault("identity", {})
    if not isinstance(ident, dict):
        analysis["identity"] = {}
        ident = analysis["identity"]
    return ident


def _append_unique(values: Any, *items: str) -> list[str]:
    out = [str(value) for value in values if str(value).strip()] if isinstance(values, list) else []
    for item in items:
        if item and item not in out:
            out.append(item)
    return out


def _candidate_payload(plan_row: dict[str, Any]) -> dict[str, Any]:
    return {
        "official_title": plan_row.get("current_projection_candidate_title"),
        "official_url": plan_row.get("current_projection_candidate_url"),
        "source": "remaining_native_hold_contract_candidate",
    }


def _scrub_row(row: dict[str, Any], plan_row: dict[str, Any]) -> tuple[dict[str, Any], str]:
    updated = copy.deepcopy(row)
    ident = _ensure_identity(updated)
    candidate = _candidate_payload(plan_row)
    decision = copy.deepcopy(plan_row.get("promotion_decision") or {})
    scope_state = plan_row.get("scope_state") if isinstance(plan_row.get("scope_state"), dict) else {}
    reason_codes = _append_unique(decision.get("reason_codes"), "serialized_public_identity_scrubbed")
    decision.update(
        {
            "status": "candidate_only",
            "publish_allowed": False,
            "official_title": None,
            "official_url": None,
            "candidate_preserved": True,
            "reason_codes": reason_codes,
            "bypassed_gate": False,
            "scope": scope_state,
        }
    )
    trace = build_publish_contract_trace(
        decision,
        scope_state=scope_state,
        pre_gate_candidate=candidate,
        post_gate_context={
            "contract_action": plan_row.get("contract_action"),
            "contract_origin": plan_row.get("contract_origin"),
            "rationale_ko": plan_row.get("rationale_ko"),
        },
    )
    publish_ledger = build_publish_ledger(trace)
    publish_ledger["status"] = decision["status"]
    publish_ledger["candidate_preserved"] = True
    candidate_ledger = {
        "status": decision["status"],
        "candidate_preserved": True,
        "promotion_decision": decision,
        "publish_contract_trace": trace,
        "publish_ledger": publish_ledger,
        "candidate_preservation": publish_ledger.get("candidate_preservation"),
    }

    old_novel = ident.get("novel_identity") if isinstance(ident.get("novel_identity"), dict) else {}
    ident["blocked_official_title"] = old_novel.get("official_title") or candidate.get("official_title")
    ident["blocked_official_title_url"] = old_novel.get("heretic_url") or candidate.get("official_url")
    ident["novel_identity"] = {"official_title": None, "heretic_url": None, "confidence": "Hold"}
    for public_key in (
        "official_title",
        "official_novel_title",
        "resolved_title",
        "heretic_url",
        "official_url",
        "resolved_url",
    ):
        ident[public_key] = None
    ident["primary_work"] = None
    ident["candidate_ledger"] = candidate_ledger
    ident["candidate_ledger_status"] = "promotion_blocked"
    ident["promotion_decision"] = decision
    ident["publish_contract_trace"] = trace
    ident["publish_ledger"] = publish_ledger
    ident["publish_allowed"] = False
    ident["promotion_blocked"] = True
    ident["safe_resolved"] = False
    ident["title_resolution_allowed"] = False
    ident["title_resolution_state"] = "unresolved_matchable"
    ident["work_resolution"] = "unresolved"
    ident["is_resolved_work_discussion"] = False
    ident["serialized_public_identity"] = None
    ident["public_identity"] = None
    ident["consistency_flags"] = _append_unique(
        ident.get("consistency_flags"),
        "remaining_native_hold_contract_applied",
        "serialized_public_identity_scrubbed",
    )
    updated["actual_title"] = None
    updated["actual_url"] = None
    updated["publish_allowed"] = False
    return updated, "scrubbed_public_identity"


def apply_hold_contracts(
    *,
    projection_rows: list[dict[str, Any]],
    plan: dict[str, Any],
    projection_id: str,
    generated_at: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    plan_by_id = {_string(row.get("post_id")): row for row in _rows(plan) if _string(row.get("post_id"))}
    updated_rows: list[dict[str, Any]] = []
    applied_rows: list[dict[str, Any]] = []
    skipped_counts: Counter[str] = Counter()
    for row in projection_rows:
        plan_row = plan_by_id.get(_string(row.get("post_id")))
        if not plan_row:
            updated_rows.append(row)
            continue
        new_row, status = _scrub_row(row, plan_row)
        updated_rows.append(new_row)
        applied_rows.append(
            {
                "post_id": row.get("post_id"),
                "status": status,
                "contract_action": plan_row.get("contract_action"),
                "current_projection_candidate_title": plan_row.get("current_projection_candidate_title"),
                "current_projection_candidate_url": plan_row.get("current_projection_candidate_url"),
                "target_title": None,
                "target_url": None,
                "runtime_replay_allowed": False,
            }
        )
    for row in _rows(plan):
        if _string(row.get("post_id")) not in {_string(item.get("post_id")) for item in applied_rows}:
            skipped_counts[_string(row.get("contract_action"))] += 1
    application = {
        "report_type": "remaining_native_hold_projection_application",
        "projection_id": projection_id,
        "generated_at": generated_at or datetime.now().replace(microsecond=0).isoformat(),
        "source_contract_plan": plan.get("plan_id"),
        "gate": "REVIEW-LOCKED",
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "summary": {
            "projection_rows": len(projection_rows),
            "contract_plan_rows": len(_rows(plan)),
            "applied_hold_contract_rows": len(applied_rows),
            "applied_scrubbed_public_identity_rows": sum(1 for row in applied_rows if row.get("status") == "scrubbed_public_identity"),
            "validation_issue_count": 0,
            "skipped_contract_action_counts": dict(skipped_counts),
            "runtime_replay_allowed_rows": 0,
            "full375_collateral_gate": "NO-GO",
            "completion_gate": "adjusted full375 collateral GO + full_scan path",
        },
        "validation_issues": [],
        "applied_rows": applied_rows,
        "approval_boundary": {
            "projection_application_is_not_runtime_replay": True,
            "hold_contract_is_not_approval": True,
            "full_scan_approval": False,
        },
    }
    return updated_rows, application


def write_plan_markdown(path: Path, plan: dict[str, Any]) -> None:
    summary = plan["summary"]
    lines = [
        f"# {plan.get('plan_id')}",
        "",
        "Remaining native-web/image review 행을 no-release hold contract로 닫는 산출물이다. 새 runtime replay가 아니며 approval도 아니다.",
        "",
        "## 요약",
        "",
        f"- source_dispatch_id: `{plan.get('source_dispatch_id')}`",
        f"- contract_plan_rows: `{summary['contract_plan_rows']}`",
        f"- native_web_hold_contract_rows: `{summary['native_web_hold_contract_rows']}`",
        f"- promotion_decision_status_counts: `{summary['promotion_decision_status_counts']}`",
        "- runtime_replay_allowed_rows: `0`",
        "- full375 collateral: `NO-GO`",
        "- semantic_quality: `REVIEW-LOCKED`",
        "- full_scan_approval: `false`",
        "",
        "## Hold contract rows",
        "",
    ]
    for row in plan.get("rows") or []:
        decision = row.get("promotion_decision") if isinstance(row.get("promotion_decision"), dict) else {}
        lines.append(
            f"- `{row.get('post_id')}` candidate=`{row.get('current_projection_candidate_title')}` "
            f"decision=`{decision.get('status')}` reason=`{row.get('source_native_verdict')}`"
        )
    lines.extend(["", "## Gate 해석", ""])
    lines.append(
        "모든 행은 candidate 보존 또는 public identity scrub 대상이며, full375 collateral GO 전 publish/release 근거가 아니다."
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def write_application_markdown(path: Path, application: dict[str, Any]) -> None:
    summary = application["summary"]
    lines = [
        f"# {application.get('projection_id')}",
        "",
        "Remaining native hold contract를 current projection result에 projection-only로 적용한 산출물이다.",
        "",
        "## 요약",
        "",
        f"- projection_rows: `{summary['projection_rows']}`",
        f"- contract_plan_rows: `{summary['contract_plan_rows']}`",
        f"- applied_hold_contract_rows: `{summary['applied_hold_contract_rows']}`",
        f"- applied_scrubbed_public_identity_rows: `{summary['applied_scrubbed_public_identity_rows']}`",
        "- runtime_replay_allowed_rows: `0`",
        "- full375 collateral: `NO-GO`",
        "- semantic_quality: `REVIEW-LOCKED`",
        "- full_scan_approval: `false`",
        "",
        "## Applied rows",
        "",
    ]
    for row in application.get("applied_rows") or []:
        lines.append(
            f"- `{row.get('post_id')}` status=`{row.get('status')}` "
            f"candidate=`{row.get('current_projection_candidate_title')}`"
        )
    lines.extend(["", "## Gate 해석", ""])
    lines.append("이 적용은 public identity 제거와 후보 보존만 수행하며, 새 runtime replay나 full_scan approval이 아니다.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build/apply hold contracts for remaining native-web/image residual rows.")
    parser.add_argument("--dispatch", required=True, type=Path)
    parser.add_argument("--result", required=True, type=Path)
    parser.add_argument("--projection-result", required=True, type=Path)
    parser.add_argument("--plan-id", required=True)
    parser.add_argument("--projection-id", required=True)
    parser.add_argument("--output-plan-json", required=True, type=Path)
    parser.add_argument("--output-plan-md", required=True, type=Path)
    parser.add_argument("--output-result", required=True, type=Path)
    parser.add_argument("--output-application-json", required=True, type=Path)
    parser.add_argument("--output-application-md", required=True, type=Path)
    parser.add_argument("--fail-on-validation-issue", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    plan = build_plan(
        dispatch=load_json(args.dispatch),
        result_rows=_rows(load_json(args.result)),
        plan_id=args.plan_id,
        result_path=args.result,
    )
    projection_rows = _rows(load_json(args.projection_result))
    updated_rows, application = apply_hold_contracts(
        projection_rows=projection_rows,
        plan=plan,
        projection_id=args.projection_id,
    )
    write_json(args.output_plan_json, plan)
    write_plan_markdown(args.output_plan_md, plan)
    write_json(args.output_result, updated_rows)
    write_json(args.output_application_json, application)
    write_application_markdown(args.output_application_md, application)
    print(json.dumps({"gate": plan["gate"], "summary": plan["summary"], "application": application["summary"]}, ensure_ascii=False, indent=2))
    if args.fail_on_validation_issue and (plan.get("validation_issues") or application.get("validation_issues")):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
