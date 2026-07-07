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

from llm_batch.promotion_gate import EvidenceRecord, GroundingState, ScopeState, can_publish_title  # noqa: E402


PUBLISH_RESTORE = "expected_title_restore_contract_case"
NO_PUBLISH = "candidate_scrub_no_publish_contract_case"


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
    rows = payload.get(key) if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise ValueError(f"payload must contain {key} list")
    return [row for row in rows if isinstance(row, dict)]


def _actions(row: dict[str, Any]) -> set[str]:
    values = row.get("actions")
    if values is None:
        values = row.get("action")
    if not isinstance(values, list):
        return set()
    return {_string(value) for value in values if _string(value)}


def _analysis(row: dict[str, Any]) -> dict[str, Any]:
    value = row.get("analysis_result")
    return value if isinstance(value, dict) else {}


def _identity(row: dict[str, Any]) -> dict[str, Any]:
    ident = _analysis(row).get("identity")
    return ident if isinstance(ident, dict) else {}


def _novel_identity(row: dict[str, Any]) -> dict[str, Any]:
    novel = _identity(row).get("novel_identity")
    return novel if isinstance(novel, dict) else {}


def _analysis_payload(row: dict[str, Any]) -> dict[str, Any]:
    value = _analysis(row).get("analysis")
    return value if isinstance(value, dict) else {}


def _image_catalog(row: dict[str, Any]) -> list[dict[str, Any]]:
    ident = _identity(row)
    analysis = _analysis_payload(row)
    for value in (ident.get("image_evidence_catalog"), analysis.get("image_evidence_catalog")):
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def _detected_titles(row: dict[str, Any]) -> list[dict[str, Any]]:
    value = _analysis_payload(row).get("detected_titles")
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _compact(value: Any) -> str:
    return "".join(ch for ch in _string(value).lower() if ch.isalnum())


def _matching_title(left: Any, right: Any) -> bool:
    left_compact = _compact(left)
    return bool(left_compact and left_compact == _compact(right))


def _eligible_image_title(result_row: dict[str, Any]) -> dict[str, Any] | None:
    for item in _image_catalog(result_row):
        title = _string(item.get("explicit_work_title"))
        if (
            title
            and item.get("promotion_eligible") is True
            and _string(item.get("title_role")) == "work_title"
        ):
            return item
    return None


def _official_detail_for_title(result_row: dict[str, Any], title: str) -> dict[str, Any] | None:
    for item in _detected_titles(result_row):
        if _string(item.get("source_tier")) != "official_detail":
            continue
        if not _matching_title(item.get("official_title"), title):
            continue
        return item
    return None


def _primary_official_detail(result_row: dict[str, Any]) -> dict[str, Any] | None:
    for item in _detected_titles(result_row):
        if _string(item.get("source_tier")) == "official_detail" and _string(item.get("reference_role")) == "primary":
            return item
    return None


def _official_url_for(result_row: dict[str, Any], title: str) -> str:
    novel = _novel_identity(result_row)
    if _matching_title(novel.get("official_title"), title):
        return _string(novel.get("heretic_url"))
    detail = _official_detail_for_title(result_row, title) or _primary_official_detail(result_row)
    return _string((detail or {}).get("heretic_url"))


def _source_ref(result_path: Path, post_id: Any) -> str:
    return f"{result_path.as_posix()}#post_id={post_id}"


def _publish_candidate(dispatch_row: dict[str, Any], result_row: dict[str, Any]) -> dict[str, Any] | None:
    actions = _actions(dispatch_row)
    if "title_surface_specificity_review_required" in actions:
        return None
    ident = _identity(result_row)
    novel = _novel_identity(result_row)
    is_resolved_work = ident.get("is_resolved_work_discussion") is True
    title_allowed = ident.get("title_resolution_allowed") is True

    image = _eligible_image_title(result_row)
    if image and (is_resolved_work or title_allowed):
        title = _string(image.get("explicit_work_title"))
        return {
            "title": title,
            "url": _official_url_for(result_row, title),
            "lane": "NE_direct_image_work_title_publish_candidate",
            "evidence_kind": "direct_image_work_surface",
            "evidence_strength": "strong",
            "reason_code": "direct_image_work_surface_bridge",
            "rationale_ko": (
                "현재 full375 결과의 image evidence catalog에 promotion_eligible=true인 직접 작품 제목이 있고, "
                "row가 작품 논의로 판정되어 shared gate publish 후보로만 반영한다."
            ),
        }

    official_title = _string(novel.get("official_title"))
    official_url = _string(novel.get("heretic_url"))
    if is_resolved_work and title_allowed and official_title and official_url:
        return {
            "title": official_title,
            "url": official_url,
            "lane": "NE_official_detail_alias_publish_candidate",
            "evidence_kind": "official_detail_url",
            "evidence_strength": "strong",
            "reason_code": "official_detail_url",
            "rationale_ko": (
                "현재 full375 결과가 공식 상세 URL과 작품 논의 상태를 함께 보존하므로 shared gate publish 후보로만 반영한다."
            ),
        }
    return None


def _is_no_publish_contract(dispatch_row: dict[str, Any], result_row: dict[str, Any]) -> tuple[bool, str]:
    ident = _identity(result_row)
    image = _eligible_image_title(result_row)
    if image:
        return False, ""
    if ident.get("is_relevant") is False and ident.get("is_resolved_work_discussion") is not True:
        return True, "current_result_nonwork_or_noise_no_publish"
    if _string(ident.get("discussion_type")) == "community_banter" and ident.get("title_resolution_allowed") is not True:
        return True, "community_banter_or_cross_media_no_publish"
    return False, ""


def _decision_for(
    *,
    post_id: Any,
    title: str,
    url: str,
    lane: str,
    evidence_kind: str,
    evidence_strength: str,
    reason_code: str,
    supports_publish: bool,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    scope_kind = "current_work" if supports_publish else "context_only"
    state = GroundingState(
        post_id=post_id,
        candidate_title=title,
        candidate_url=url,
        source="remaining_native_evidence_contract_plan",
        official_title_exists=bool(title),
        row_discusses_work_as_work=supports_publish,
        title_resolution_state="resolved" if supports_publish else "context_only",
        work_resolution="resolved" if supports_publish else "unresolved",
        discussion_type="review",
        scope=ScopeState(
            scope_kind=scope_kind,
            confidence="high" if evidence_strength == "strong" else "medium",
            direct_bridge_sources=[lane, evidence_kind],
            conflict_reason_codes=[] if supports_publish else [reason_code],
        ),
    )
    evidence = [
        EvidenceRecord(
            kind=evidence_kind,
            strength=evidence_strength,
            source_path_or_snippet=lane,
            supports_publish=supports_publish,
            reason_code=reason_code,
        )
    ]
    decision = can_publish_title(state, evidence)
    payload = decision.to_dict()
    if state.scope:
        payload["scope"] = state.scope.to_dict()
    return payload, state.to_dict(), [record.to_dict() for record in evidence]


def build_plan(
    *,
    residual_dispatch: dict[str, Any],
    result_rows: list[dict[str, Any]],
    result_path: Path,
    plan_id: str,
    generated_at: str | None = None,
) -> dict[str, Any]:
    result_by_id = {_string(row.get("post_id")): row for row in result_rows if _string(row.get("post_id"))}
    rows: list[dict[str, Any]] = []
    review_rows: list[dict[str, Any]] = []
    validation_issues: list[dict[str, Any]] = []

    for dispatch_row in _rows(residual_dispatch):
        post_id = dispatch_row.get("post_id")
        key = _string(post_id)
        result_row = result_by_id.get(key)
        if result_row is None:
            validation_issues.append({"post_id": post_id, "issue": "result_row_missing"})
            review_rows.append(
                {
                    "post_id": post_id,
                    "review_label": "INFO_MISSING",
                    "contract_disposition": "hold",
                    "rationale_ko": "current full375 result에서 해당 post_id를 찾지 못해 계약 처리하지 않는다.",
                }
            )
            continue

        publish = _publish_candidate(dispatch_row, result_row)
        if publish:
            decision, gate_state, evidence = _decision_for(
                post_id=post_id,
                title=publish["title"],
                url=publish["url"],
                lane=publish["lane"],
                evidence_kind=publish["evidence_kind"],
                evidence_strength=publish["evidence_strength"],
                reason_code=publish["reason_code"],
                supports_publish=True,
            )
            contract_row = {
                "post_id": post_id,
                "contract_origin": plan_id,
                "contract_batch_lane": publish["lane"],
                "triage_bucket": dispatch_row.get("triage_bucket"),
                "review_label": "REPROCESS",
                "source_native_verdict": dispatch_row.get("source_native_verdict"),
                "evidence_grade": "Strong" if publish["evidence_strength"] == "strong" else "Medium",
                "target_title": publish["title"],
                "target_url": publish["url"] or None,
                "current_projection_candidate_title": dispatch_row.get("selected_title"),
                "current_projection_candidate_url": dispatch_row.get("selected_url"),
                "actions": sorted(_actions(dispatch_row)),
                "contract_action": PUBLISH_RESTORE,
                "promotion_decision": decision,
                "promotion_gate_state": gate_state,
                "promotion_gate_evidence": evidence,
                "release_candidate_not_approval": True,
                "runtime_replay_allowed": False,
                "full375_recheck_required": True,
                "full_scan_approval": False,
                "rationale_ko": publish["rationale_ko"],
                "evidence_refs": [
                    _source_ref(result_path, post_id),
                    *[str(ref) for ref in dispatch_row.get("evidence_refs") or []][:3],
                ],
            }
            rows.append(contract_row)
            review_rows.append({**contract_row, "contract_disposition": "release_candidate_not_approval"})
            continue

        no_publish, no_publish_reason = _is_no_publish_contract(dispatch_row, result_row)
        if no_publish:
            decision, gate_state, evidence = _decision_for(
                post_id=post_id,
                title="",
                url="",
                lane="NE_current_result_no_publish_contract",
                evidence_kind="current_result_nonwork_or_policy_hold",
                evidence_strength="strong",
                reason_code=no_publish_reason,
                supports_publish=False,
            )
            contract_row = {
                "post_id": post_id,
                "contract_origin": plan_id,
                "contract_batch_lane": "NE_current_result_no_publish_contract",
                "triage_bucket": dispatch_row.get("triage_bucket"),
                "review_label": "HOLD",
                "source_native_verdict": dispatch_row.get("source_native_verdict"),
                "evidence_grade": "Strong",
                "target_title": None,
                "target_url": None,
                "current_projection_candidate_title": dispatch_row.get("selected_title"),
                "current_projection_candidate_url": dispatch_row.get("selected_url"),
                "actions": sorted(_actions(dispatch_row)),
                "contract_action": NO_PUBLISH,
                "promotion_decision": decision,
                "promotion_gate_state": gate_state,
                "promotion_gate_evidence": evidence,
                "release_candidate_not_approval": False,
                "runtime_replay_allowed": False,
                "full375_recheck_required": True,
                "full_scan_approval": False,
                "rationale_ko": "현재 full375 결과가 작품 publish를 허용하지 않는 nonwork/noise/cross-media 경계를 보존하므로 no-publish contract로만 처리한다.",
                "evidence_refs": [
                    _source_ref(result_path, post_id),
                    *[str(ref) for ref in dispatch_row.get("evidence_refs") or []][:3],
                ],
            }
            rows.append(contract_row)
            review_rows.append({**contract_row, "contract_disposition": "no_publish_not_approval"})
            continue

        ident = _identity(result_row)
        review_rows.append(
            {
                "post_id": post_id,
                "triage_bucket": dispatch_row.get("triage_bucket"),
                "review_label": "HOLD",
                "source_native_verdict": dispatch_row.get("source_native_verdict"),
                "contract_disposition": "hold_for_native_web_or_image_review",
                "title_resolution_state": ident.get("title_resolution_state"),
                "discussion_type": ident.get("discussion_type"),
                "rationale_ko": "현재 result evidence만으로 shared gate publish/no-publish 계약을 닫지 않는다.",
                "evidence_refs": [
                    _source_ref(result_path, post_id),
                    *[str(ref) for ref in dispatch_row.get("evidence_refs") or []][:3],
                ],
            }
        )

    action_counts = Counter(_string(row.get("contract_action")) for row in rows)
    lane_counts = Counter(_string(row.get("contract_batch_lane")) for row in rows)
    decision_counts = Counter(_string((row.get("promotion_decision") or {}).get("status")) for row in rows)
    disposition_counts = Counter(_string(row.get("contract_disposition")) for row in review_rows)
    return {
        "report_type": "remaining_native_evidence_contract_plan",
        "plan_id": plan_id,
        "generated_at": generated_at or datetime.now().replace(microsecond=0).isoformat(),
        "source_dispatch_id": residual_dispatch.get("dispatch_id"),
        "source_result_path": str(result_path),
        "gate": "NO-GO" if validation_issues else "REVIEW-LOCKED",
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "summary": {
            "source_dispatch_rows": len(_rows(residual_dispatch)),
            "result_matched_rows": len([row for row in review_rows if row.get("review_label") != "INFO_MISSING"]),
            "contract_plan_rows": len(rows),
            "release_candidate_not_approval_rows": sum(1 for row in rows if row.get("release_candidate_not_approval")),
            "no_publish_contract_rows": sum(1 for row in rows if row.get("contract_action") == NO_PUBLISH),
            "hold_rows": disposition_counts.get("hold_for_native_web_or_image_review", 0),
            "validation_issue_count": len(validation_issues),
            "contract_batch_lane_counts": dict(lane_counts),
            "contract_action_counts": dict(action_counts),
            "promotion_decision_status_counts": dict(decision_counts),
            "review_disposition_counts": dict(disposition_counts),
            "runtime_replay_allowed_rows": 0,
            "full375_collateral_gate": "NO-GO",
            "completion_gate": "full375 collateral GO + full_scan path",
        },
        "validation_issues": validation_issues,
        "rows": rows,
        "review_rows": review_rows,
        "approval_boundary": {
            "current_result_evidence_is_not_runtime_replay": True,
            "release_candidate_is_not_approval": True,
            "no_publish_contract_is_not_full_scan_approval": True,
            "full375_collateral_remains_no_go": True,
        },
    }


def write_markdown(path: Path, plan: dict[str, Any]) -> None:
    summary = plan["summary"]
    lines = [
        f"# {plan.get('plan_id')}",
        "",
        "Remaining native-web/image evidence를 shared promotion gate contract plan으로 변환한 산출물이다. "
        "새 runtime replay가 아니며 full375 approval도 아니다.",
        "",
        "## 요약",
        "",
        f"- source_dispatch_id: `{plan.get('source_dispatch_id')}`",
        f"- source_dispatch_rows: `{summary.get('source_dispatch_rows')}`",
        f"- contract_plan_rows: `{summary.get('contract_plan_rows')}`",
        f"- release_candidate_not_approval_rows: `{summary.get('release_candidate_not_approval_rows')}`",
        f"- no_publish_contract_rows: `{summary.get('no_publish_contract_rows')}`",
        f"- hold_rows: `{summary.get('hold_rows')}`",
        f"- contract_action_counts: `{summary.get('contract_action_counts')}`",
        f"- promotion_decision_status_counts: `{summary.get('promotion_decision_status_counts')}`",
        f"- validation_issue_count: `{summary.get('validation_issue_count')}`",
        "- runtime_replay_allowed_rows: `0`",
        "- full375 collateral: `NO-GO`",
        "- semantic_quality: `REVIEW-LOCKED`",
        "- full_scan_approval: `false`",
        "",
        "## 계약 행",
        "",
    ]
    for row in plan.get("rows") or []:
        decision = row.get("promotion_decision") if isinstance(row.get("promotion_decision"), dict) else {}
        lines.append(
            f"- `{row.get('post_id')}` action=`{row.get('contract_action')}` "
            f"decision=`{decision.get('status')}` target=`{row.get('target_title')}` "
            f"url=`{row.get('target_url')}` lane=`{row.get('contract_batch_lane')}`"
        )
    hold_rows = [row for row in plan.get("review_rows") or [] if row.get("contract_disposition") == "hold_for_native_web_or_image_review"]
    if hold_rows:
        lines.extend(["", "## Hold 행", ""])
        for row in hold_rows:
            lines.append(
                f"- `{row.get('post_id')}` state=`{row.get('title_resolution_state')}` "
                f"type=`{row.get('discussion_type')}` reason=`{row.get('source_native_verdict')}`"
            )
    lines.extend(["", "## Gate 해석", ""])
    lines.append(
        "publish 행은 release candidate일 뿐이고 no-publish 행도 full_scan approval이 아니다. "
        "남은 hold 행은 native-web/image evidence review가 필요하다. 완료 기준은 계속 `full375 collateral GO + full_scan path`다."
    )
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build native-evidence contract plan for remaining residual rows.")
    parser.add_argument("--dispatch", required=True, type=Path)
    parser.add_argument("--result", required=True, type=Path)
    parser.add_argument("--plan-id", required=True)
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-md", required=True, type=Path)
    parser.add_argument("--fail-on-validation-issue", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    plan = build_plan(
        residual_dispatch=load_json(args.dispatch),
        result_rows=_rows(load_json(args.result)),
        result_path=args.result,
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
