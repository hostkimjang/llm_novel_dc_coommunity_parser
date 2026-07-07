from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

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


CANDIDATE_SET_LANE = "candidate_set_rebuild_review"
RESTORE_ACTION = "candidate_set_expected_restore_contract_case"
REBUILD_ACTION = "candidate_set_rebuild_required_before_publish"
INTENT_HOLD_ACTION = "no_publish_intent_guard_contract_case"
OFFICIAL_MISSING_ACTION = "official_support_missing_candidate_hold_contract_case"


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def _string(value: Any) -> str:
    return str(value or "").strip()


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    if not isinstance(rows, list):
        raise ValueError("payload must contain rows list")
    return [row for row in rows if isinstance(row, dict)]


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


def _counter_to_dict(counter: Counter[str]) -> dict[str, int]:
    return {key: counter[key] for key in sorted(counter)}


def _canonical_official_detail_url(value: Any) -> str:
    url = _string(value)
    if not url:
        return ""
    lowered = url.lower()
    if "novelpia.com/novel/" in lowered:
        return url
    if "series.naver.com/novel/detail.series" in lowered:
        return url
    if "page.kakao.com/content/" in lowered:
        return url
    if "novel.munpia.com/" in lowered:
        return url
    if "ridibooks.com/books/" in lowered:
        return url

    parts = urlsplit(url)
    host = parts.netloc.lower()
    path = parts.path.strip("/")
    if host in {"mm.munpia.com", "m.munpia.com"}:
        match = re.search(r"(?:^|/)novel/detail/(\d+)(?:/|$)", path, flags=re.IGNORECASE)
        if match:
            return f"https://novel.munpia.com/{match.group(1)}"
        params = parse_qs(parts.query)
        menu = (params.get("menu") or [""])[0].strip().lower()
        novel_id = (params.get("id") or [""])[0].strip()
        if menu == "novel" and novel_id.isdigit():
            return f"https://novel.munpia.com/{novel_id}"
    return ""


def _official_refs(row: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    seen: set[str] = set()
    for item in _as_list(row.get("evidence_refs")):
        ref = _canonical_official_detail_url(item)
        if ref and ref not in seen:
            seen.add(ref)
            refs.append(ref)
    return refs


def _actions(row: dict[str, Any]) -> set[str]:
    return {_string(item) for item in _as_list(row.get("actions")) if _string(item)}


def _is_intent_guard(row: dict[str, Any]) -> bool:
    actions = _actions(row)
    verdict = _string(row.get("source_native_verdict")).lower()
    rationale = _string(row.get("rationale_ko")).lower()
    return (
        "intent_guard_review" in actions
        or "classic" in verdict
        or "nonwebnovel" in verdict
        or "same_surface_webnovel_promotion" in verdict
        or "고전" in rationale
        or "다자이" in rationale
    )


def _contract_action(row: dict[str, Any], selected_title: str, official_refs: list[str]) -> str:
    if _is_intent_guard(row):
        return INTENT_HOLD_ACTION
    if not selected_title:
        return REBUILD_ACTION
    if official_refs:
        return RESTORE_ACTION
    return OFFICIAL_MISSING_ACTION


def _build_state_and_evidence(
    row: dict[str, Any],
    *,
    selected_title: str,
    official_refs: list[str],
    action: str,
) -> tuple[GroundingState, list[EvidenceRecord]]:
    evidence_grade = _grade(row.get("evidence_grade"))
    confidence = "high" if evidence_grade == "strong" else "medium"
    current_work = action == RESTORE_ACTION
    candidate_url = official_refs[0] if official_refs else ""
    conflict_reason_codes: list[str] = []
    scope_kind = "current_work" if current_work else "unknown"
    title_resolution_state = "resolved" if current_work else "unresolved"
    work_resolution = "resolved" if current_work else "unresolved"
    discussion_type = "review"
    if action == INTENT_HOLD_ACTION:
        scope_kind = "platform_meta_nonwork"
        title_resolution_state = "nonwork"
        work_resolution = "nonwork"
        discussion_type = "review"
        conflict_reason_codes.append("intent_guard_no_webnovel_promotion")
    elif action == REBUILD_ACTION:
        conflict_reason_codes.append("candidate_set_rebuild_required")
    elif action == OFFICIAL_MISSING_ACTION:
        conflict_reason_codes.append("official_support_missing")

    state = GroundingState(
        post_id=_post_id(row.get("post_id")),
        candidate_title=selected_title,
        candidate_url=candidate_url,
        source="candidate_set_contract_plan",
        official_title_exists=bool(selected_title and official_refs),
        row_discusses_work_as_work=current_work,
        title_resolution_state=title_resolution_state,
        work_resolution=work_resolution,
        discussion_type=discussion_type,
        scope=ScopeState(
            scope_kind=scope_kind,
            confidence=confidence,
            direct_bridge_sources=[
                "refined_p0_candidate_set_dispatch",
                CANDIDATE_SET_LANE,
                action,
            ],
            competing_candidates=[],
            conflict_reason_codes=conflict_reason_codes,
        ),
    )
    evidence = [
        EvidenceRecord(
            kind="candidate_set_source_native_contract",
            strength=evidence_grade,
            source_path_or_snippet=_string(row.get("rationale_ko")),
            supports_publish=action == RESTORE_ACTION and evidence_grade in {"strong", "medium"},
            reason_code="candidate_set_source_native_contract_case",
        )
    ]
    if official_refs:
        evidence.append(
            EvidenceRecord(
                kind="official_support_ref",
                strength="strong",
                source_path_or_snippet=official_refs[0],
                supports_publish=action == RESTORE_ACTION,
                reason_code="official_support_ref_present",
            )
        )
    return state, evidence


def _build_plan_row(row: dict[str, Any]) -> dict[str, Any]:
    selected_title = _string(row.get("selected_title"))
    official_refs = _official_refs(row)
    action = _contract_action(row, selected_title, official_refs)
    state, evidence = _build_state_and_evidence(
        row,
        selected_title=selected_title,
        official_refs=official_refs,
        action=action,
    )
    decision = can_publish_title(state, evidence)
    return {
        "post_id": _post_id(row.get("post_id")),
        "contract_origin": "refined_p0_candidate_set_dispatch",
        "contract_batch_lane": "CS_candidate_set_contract",
        "source_dispatch_lane": row.get("dispatch_lane"),
        "triage_bucket": row.get("triage_bucket"),
        "review_label": row.get("review_label"),
        "source_native_verdict": row.get("source_native_verdict"),
        "evidence_grade": row.get("evidence_grade"),
        "target_title": selected_title or None,
        "target_url": official_refs[0] if official_refs else None,
        "official_support_refs": official_refs,
        "official_support_ref_count": len(official_refs),
        "actions": row.get("actions") or [],
        "contract_action": action,
        "promotion_decision": decision.to_dict(),
        "promotion_gate_state": state.to_dict(),
        "promotion_gate_evidence": [item.to_dict() for item in evidence],
        "release_candidate_not_approval": action == RESTORE_ACTION and decision.status == "publish",
        "candidate_set_rebuild_required_before_publish": action == REBUILD_ACTION,
        "intent_guard_hold_before_publish": action == INTENT_HOLD_ACTION,
        "official_support_missing_before_publish": action == OFFICIAL_MISSING_ACTION,
        "runtime_replay_allowed": False,
        "contract_application_required_before_runtime": action == RESTORE_ACTION,
        "candidate_set_rebuild_required_before_runtime": action in {REBUILD_ACTION, OFFICIAL_MISSING_ACTION},
        "full375_recheck_required": True,
        "full_scan_approval": False,
        "rationale_ko": row.get("rationale_ko"),
        "evidence_refs": row.get("evidence_refs") or [],
    }


def build_plan(
    batch: dict[str, Any],
    *,
    plan_id: str,
    generated_at: str | None = None,
) -> dict[str, Any]:
    selected = [row for row in _rows(batch) if row.get("dispatch_lane") == CANDIDATE_SET_LANE]
    rows = [_build_plan_row(row) for row in selected]
    validation_issues: list[dict[str, Any]] = []
    for row in rows:
        if not row.get("post_id"):
            validation_issues.append({"issue": "missing_post_id", "row": row})
        if row["promotion_decision"].get("bypassed_gate"):
            validation_issues.append({"issue": "promotion_gate_bypassed", "post_id": row.get("post_id")})
        if row.get("runtime_replay_allowed"):
            validation_issues.append({"issue": "runtime_replay_allowed_before_contract", "post_id": row.get("post_id")})
        if row.get("contract_action") == RESTORE_ACTION and row["promotion_decision"].get("status") != "publish":
            validation_issues.append({"issue": "restore_contract_not_publish_decision", "post_id": row.get("post_id")})
        if row.get("contract_action") == INTENT_HOLD_ACTION and row["promotion_decision"].get("publish_allowed"):
            validation_issues.append({"issue": "intent_guard_publish_allowed", "post_id": row.get("post_id")})

    action_counts = Counter(_string(row.get("contract_action")) for row in rows)
    decision_counts = Counter(_string(row["promotion_decision"].get("status")) for row in rows)
    grade_counts = Counter(_string(row.get("evidence_grade")) for row in rows)
    triage_counts = Counter(_string(row.get("triage_bucket")) for row in rows)
    return {
        "report_type": "candidate_set_contract_plan",
        "plan_id": plan_id,
        "generated_at": generated_at or datetime.now().replace(microsecond=0).isoformat(),
        "source_batch": batch.get("dispatch_id") or batch.get("queue_id") or batch.get("plan_id"),
        "gate": "NO-GO" if validation_issues else "REVIEW-LOCKED",
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "summary": {
            "source_batch_rows": len(_rows(batch)),
            "candidate_set_contract_plan_rows": len(rows),
            "validation_issue_count": len(validation_issues),
            "contract_action_counts": _counter_to_dict(action_counts),
            "promotion_decision_status_counts": _counter_to_dict(decision_counts),
            "evidence_grade_counts": _counter_to_dict(grade_counts),
            "triage_bucket_counts": _counter_to_dict(triage_counts),
            "official_support_ref_missing_rows": sum(1 for row in rows if not row.get("official_support_refs")),
            "release_candidate_not_approval_rows": sum(1 for row in rows if row.get("release_candidate_not_approval")),
            "candidate_set_rebuild_hold_rows": sum(
                1 for row in rows if row.get("candidate_set_rebuild_required_before_publish")
            ),
            "intent_guard_hold_rows": sum(1 for row in rows if row.get("intent_guard_hold_before_publish")),
            "publish_allowed_rows": 0,
            "runtime_replay_allowed_rows": 0,
            "full375_collateral_gate": "NO-GO",
            "completion_gate": "full375 collateral GO + full_scan path",
        },
        "execution_contract": {
            "runtime_replay_allowed": False,
            "requested_parallel": 16,
            "dashboard_contract": {
                "dashboard_policy": "WEB_DASHBOARD_REQUIRED_FOR_TEST_RUNS",
                "dashboard_url": "http://127.0.0.1:8080",
                "forbidden_flags": ["--no-dashboard"],
                "attach_manifest_command": (
                    "python tools/attach_manifest_dashboard.py --manifest <result_manifest.json> "
                    "--dashboard-url http://127.0.0.1:8080"
                ),
            },
        },
        "validation_issues": validation_issues,
        "rows": rows,
        "approval_boundary": {
            "candidate_set_contract_plan_is_not_approval": True,
            "promotion_decision_publish_is_contract_case_only": True,
            "candidate_set_rebuild_holds_publish": True,
            "runtime_replay_allowed": False,
            "full375_collateral_remains_no_go": True,
            "full_scan_approval": False,
        },
    }


def write_markdown(plan: dict[str, Any], path: Path) -> None:
    summary = plan["summary"]
    dashboard = plan["execution_contract"]["dashboard_contract"]
    lines = [
        f"# {plan.get('plan_id')}",
        "",
        "Loop577 refined P0 dispatch의 `candidate_set_rebuild_review` 10건을 shared promotion gate 계약 계획으로 분리한 산출물이다. "
        "이 문서는 runtime replay 허가나 full_scan approval이 아니다.",
        "",
        "## 요약",
        "",
        f"- gate: `{plan.get('gate')}`",
        "- semantic_quality: `REVIEW-LOCKED`",
        "- full_scan_approval: `false`",
        f"- candidate_set_contract_plan_rows: `{summary.get('candidate_set_contract_plan_rows')}`",
        f"- validation_issue_count: `{summary.get('validation_issue_count')}`",
        f"- contract_action_counts: `{summary.get('contract_action_counts')}`",
        f"- promotion_decision_status_counts: `{summary.get('promotion_decision_status_counts')}`",
        f"- release_candidate_not_approval_rows: `{summary.get('release_candidate_not_approval_rows')}`",
        f"- candidate_set_rebuild_hold_rows: `{summary.get('candidate_set_rebuild_hold_rows')}`",
        f"- intent_guard_hold_rows: `{summary.get('intent_guard_hold_rows')}`",
        f"- runtime_replay_allowed_rows: `{summary.get('runtime_replay_allowed_rows')}`",
        f"- full375 collateral: `{summary.get('full375_collateral_gate')}`",
        "",
        "## 실행 계약",
        "",
        "- 이 산출물만으로 runtime replay를 시작하지 않는다.",
        "- 다음 test/runtime run은 `--parallel 16`을 사용한다.",
        f"- 웹 대시보드: `{dashboard.get('dashboard_url')}`",
        "- `--no-dashboard`는 금지한다.",
        "- 이미 dashboard 없이 시작한 런만 manifest 사후 부착 명령을 사용한다.",
        "",
        "## 행별 계획",
        "",
    ]
    for row in plan.get("rows") or []:
        target = row.get("target_title") or "-"
        lines.append(
            f"- `{row.get('post_id')}` action=`{row.get('contract_action')}` "
            f"decision=`{row.get('promotion_decision', {}).get('status')}` "
            f"target=`{target}` official_refs=`{row.get('official_support_ref_count')}` "
            f"release_candidate_not_approval=`{str(row.get('release_candidate_not_approval')).lower()}`"
        )
    lines.extend(
        [
            "",
            "## Gate 해석",
            "",
            "- `candidate_set_expected_restore_contract_case` 4건은 source-native 근거와 공식 detail URL을 갖춘 contract case다. 이는 release 후보 표시일 뿐 승인 완료가 아니다.",
            "- `candidate_set_rebuild_required_before_publish` 5건은 현재 후보셋이 source-supported title을 담지 못하므로 publish 금지 상태로 둔다.",
            "- `no_publish_intent_guard_contract_case` 1건은 고전 작품 intent guard로 같은 표면 웹소설 promotion을 막는다.",
            "- 완료 기준은 계속 `full375 collateral GO + full_scan 경로 정의`다.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build candidate-set shared promotion gate contract plan.")
    parser.add_argument("--batch", required=True, type=Path)
    parser.add_argument("--plan-id", default="loop578_candidate_set_contract_plan")
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-md", required=True, type=Path)
    parser.add_argument("--fail-on-validation-issue", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    plan = build_plan(load_json(args.batch), plan_id=args.plan_id)
    write_json(args.output_json, plan)
    write_markdown(plan, args.output_md)
    if args.fail_on_validation_issue and plan.get("validation_issues"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
