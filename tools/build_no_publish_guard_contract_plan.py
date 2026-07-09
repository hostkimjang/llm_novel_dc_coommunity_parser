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


NO_PUBLISH_LANE = "no_publish_multiwork_guard_review"
NO_PUBLISH_ACTION = "no_publish_intent_guard_contract_case"


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


def _row_lane(row: dict[str, Any]) -> str:
    return _string(row.get("dispatch_lane") or row.get("primary_lane"))


def _actions(row: dict[str, Any]) -> list[str]:
    raw = row.get("actions")
    if raw is None:
        raw = row.get("action")
    if isinstance(raw, str):
        return [raw] if raw.strip() else []
    if isinstance(raw, list):
        return [_string(item) for item in raw if _string(item)]
    return []


def _counter_to_dict(counter: Counter[str]) -> dict[str, int]:
    return {key: counter[key] for key in sorted(counter)}


def _scope_conflict_codes(row: dict[str, Any]) -> list[str]:
    codes = ["no_publish_policy_guard", "public_identity_scrubbed_before_policy_contract"]
    for action in _actions(row):
        if action == "wrong_work_or_cross_media_policy_hold_required":
            codes.append("wrong_work_or_cross_media_policy_hold_required")
        elif action == "blind_or_policy_judge_required":
            codes.append("blind_or_policy_judge_required")
    verdict = _string(row.get("source_native_verdict")).lower()
    rationale = _string(row.get("rationale_ko")).lower()
    if "classic" in verdict or "non_webnovel" in verdict or "고전" in rationale:
        codes.append("non_webnovel_or_classic_policy_hold")
    if "wrong_work" in verdict or "cross_media" in verdict or "교차매체" in rationale:
        codes.append("cross_media_wrong_work_policy_hold")
    out: list[str] = []
    for code in codes:
        if code not in out:
            out.append(code)
    return out


def _build_plan_row(row: dict[str, Any]) -> dict[str, Any]:
    target_title = _string(row.get("selected_title"))
    target_url = _string(row.get("selected_url"))
    evidence_grade = _grade(row.get("evidence_grade"))
    confidence = "high" if evidence_grade == "strong" else "medium"
    conflict_codes = _scope_conflict_codes(row)
    scope = ScopeState(
        scope_kind="platform_meta_nonwork",
        confidence=confidence,
        direct_bridge_sources=["ordinary_residual_dispatch", NO_PUBLISH_LANE, NO_PUBLISH_ACTION],
        competing_candidates=[],
        conflict_reason_codes=conflict_codes,
    )
    state = GroundingState(
        post_id=_post_id(row.get("post_id")),
        candidate_title=target_title,
        candidate_url=target_url,
        source="no_publish_guard_contract_plan",
        official_title_exists=bool(target_title and target_url),
        row_discusses_work_as_work=False,
        title_resolution_state="nonwork",
        work_resolution="nonwork",
        discussion_type="review",
        scope=scope,
    )
    evidence = [
        EvidenceRecord(
            kind="no_publish_source_native_contract",
            strength=evidence_grade,
            source_path_or_snippet=_string(row.get("rationale_ko")),
            supports_publish=False,
            reason_code="no_publish_guard_source_native_contract_case",
        )
    ]
    decision = can_publish_title(state, evidence)
    return {
        "post_id": _post_id(row.get("post_id")),
        "contract_origin": "ordinary_residual_no_publish_guard_dispatch",
        "contract_batch_lane": "NP_no_publish_guard_contract",
        "source_dispatch_lane": _row_lane(row),
        "triage_bucket": row.get("triage_bucket"),
        "review_label": row.get("review_label"),
        "source_native_verdict": row.get("source_native_verdict"),
        "evidence_grade": row.get("evidence_grade"),
        "target_title": target_title or None,
        "target_url": target_url or None,
        "official_support_refs": [],
        "official_support_ref_count": 0,
        "actions": _actions(row),
        "contract_action": NO_PUBLISH_ACTION,
        "promotion_decision": decision.to_dict(),
        "promotion_gate_state": state.to_dict(),
        "promotion_gate_evidence": [item.to_dict() for item in evidence],
        "release_candidate_not_approval": False,
        "no_publish_contract_required_before_publish": True,
        "runtime_replay_allowed": False,
        "contract_application_required_before_runtime": True,
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
    selected = [row for row in _rows(batch) if _row_lane(row) == NO_PUBLISH_LANE]
    rows = [_build_plan_row(row) for row in selected]
    validation_issues: list[dict[str, Any]] = []
    for row in rows:
        if not row.get("post_id"):
            validation_issues.append({"issue": "missing_post_id", "row": row})
        decision = row.get("promotion_decision") if isinstance(row.get("promotion_decision"), dict) else {}
        if decision.get("bypassed_gate"):
            validation_issues.append({"issue": "promotion_gate_bypassed", "post_id": row.get("post_id")})
        if decision.get("publish_allowed"):
            validation_issues.append({"issue": "no_publish_guard_publish_allowed", "post_id": row.get("post_id")})
        if row.get("runtime_replay_allowed"):
            validation_issues.append({"issue": "runtime_replay_allowed_before_contract", "post_id": row.get("post_id")})

    action_counts = Counter(_string(row.get("contract_action")) for row in rows)
    decision_counts = Counter(_string(row["promotion_decision"].get("status")) for row in rows)
    label_counts = Counter(_string(row.get("review_label")) for row in rows)
    triage_counts = Counter(_string(row.get("triage_bucket")) for row in rows)
    return {
        "report_type": "no_publish_guard_contract_plan",
        "plan_id": plan_id,
        "generated_at": generated_at or datetime.now().replace(microsecond=0).isoformat(),
        "source_batch": batch.get("dispatch_id") or batch.get("batch_id") or batch.get("queue_id"),
        "gate": "NO-GO" if validation_issues else "REVIEW-LOCKED",
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "summary": {
            "source_batch_rows": len(_rows(batch)),
            "no_publish_contract_plan_rows": len(rows),
            "validation_issue_count": len(validation_issues),
            "contract_action_counts": _counter_to_dict(action_counts),
            "promotion_decision_status_counts": _counter_to_dict(decision_counts),
            "label_counts": _counter_to_dict(label_counts),
            "triage_bucket_counts": _counter_to_dict(triage_counts),
            "no_publish_contract_rows": len(rows),
            "release_candidate_not_approval_rows": 0,
            "publish_allowed_rows": 0,
            "runtime_replay_allowed_rows": 0,
            "full375_collateral_gate": "NO-GO",
            "completion_gate": "adjusted full375 collateral GO + full_scan path",
        },
        "execution_contract": {
            "runtime_replay_allowed": False,
            "requested_parallel": 16,
            "dashboard_contract": {
                "dashboard_policy": "WEB_DASHBOARD_REQUIRED_FOR_TEST_RUNS",
                "dashboard_url": "http://127.0.0.1:8080",
                "forbidden_flags": ["--no-dashboard"],
            },
        },
        "validation_issues": validation_issues,
        "rows": rows,
        "approval_boundary": {
            "no_publish_contract_plan_is_not_approval": True,
            "no_publish_rows_hold_public_identity": True,
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
        f"`{plan.get('source_batch')}`의 `no_publish_multiwork_guard_review` 행을 shared promotion gate no-publish 계약으로 분리한 산출물이다. "
        "이 문서는 runtime replay 허가나 full_scan approval이 아니다.",
        "",
        "## 요약",
        "",
        f"- gate: `{plan.get('gate')}`",
        "- semantic_quality: `REVIEW-LOCKED`",
        "- full_scan_approval: `false`",
        f"- no_publish_contract_plan_rows: `{summary.get('no_publish_contract_plan_rows')}`",
        f"- validation_issue_count: `{summary.get('validation_issue_count')}`",
        f"- contract_action_counts: `{summary.get('contract_action_counts')}`",
        f"- promotion_decision_status_counts: `{summary.get('promotion_decision_status_counts')}`",
        f"- label_counts: `{summary.get('label_counts')}`",
        f"- release_candidate_not_approval_rows: `{summary.get('release_candidate_not_approval_rows')}`",
        f"- runtime_replay_allowed_rows: `{summary.get('runtime_replay_allowed_rows')}`",
        f"- full375 collateral: `{summary.get('full375_collateral_gate')}`",
        "",
        "## 실행 계약",
        "",
        "- 이 산출물만으로 runtime replay를 시작하지 않는다.",
        "- 다음 test/runtime run은 `--parallel 16`을 사용한다.",
        f"- 웹 대시보드: `{dashboard.get('dashboard_url')}`",
        "- `--no-dashboard`는 금지한다.",
        "",
        "## 행별 계획",
        "",
    ]
    for row in plan.get("rows") or []:
        decision = row.get("promotion_decision") if isinstance(row.get("promotion_decision"), dict) else {}
        target = row.get("target_title") or "-"
        lines.append(
            f"- `{row.get('post_id')}` action=`{row.get('contract_action')}` "
            f"decision=`{decision.get('status')}` target=`{target}` label=`{row.get('review_label')}`"
        )
    lines.extend(
        [
            "",
            "## Gate 해석",
            "",
            "- `no_publish_intent_guard_contract_case`는 고전/비웹소설/교차매체 wrong-work 표면이 웹소설 public identity로 승격되는 것을 막는다.",
            "- 이 plan의 모든 행은 release candidate가 아니며 projection application에서 public identity를 scrub 또는 no-release 상태로 보존해야 한다.",
            "- 완료 기준은 계속 `adjusted full375 collateral GO + full_scan 경로 정의`다.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build no-publish guard shared promotion gate contract plan.")
    parser.add_argument("--batch", required=True, type=Path)
    parser.add_argument("--plan-id", default="no_publish_guard_contract_plan")
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-md", required=True, type=Path)
    parser.add_argument("--fail-on-validation-issue", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    plan = build_plan(load_json(args.batch), plan_id=args.plan_id)
    write_json(args.output_json, plan)
    write_markdown(plan, args.output_md)
    print(json.dumps({"gate": plan["gate"], "summary": plan["summary"]}, ensure_ascii=False, indent=2))
    if args.fail_on_validation_issue and plan.get("validation_issues"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
