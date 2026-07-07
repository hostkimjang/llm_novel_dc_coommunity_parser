from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _rows(payload: dict[str, Any], key: str) -> list[dict[str, Any]]:
    rows = payload.get(key)
    if not isinstance(rows, list):
        raise ValueError(f"payload must contain {key} list")
    return [row for row in rows if isinstance(row, dict)]


def _counter(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    values = Counter(str(row.get(field) or "") for row in rows if str(row.get(field) or ""))
    return {key: values[key] for key in sorted(values)}


def _decision_counter(rows: list[dict[str, Any]]) -> dict[str, int]:
    values = Counter(
        str((row.get("promotion_decision") or {}).get("status") or "")
        for row in rows
        if isinstance(row.get("promotion_decision"), dict)
    )
    return {key: values[key] for key in sorted(values) if key}


def merge_plan(
    base: dict[str, Any],
    addition: dict[str, Any],
    *,
    plan_id: str,
    generated_at: str | None = None,
) -> dict[str, Any]:
    base_rows = _rows(base, "rows")
    addition_rows = _rows(addition, "rows")
    rows = [*base_rows, *addition_rows]
    validation_issues = [
        *(base.get("validation_issues") or []),
        *(addition.get("validation_issues") or []),
    ]
    summary = dict(base.get("summary") or {})
    summary.update(
        {
            "contract_plan_rows": len(rows),
            "validation_issue_count": len(validation_issues),
            "contract_action_counts": _counter(rows, "contract_action"),
            "contract_batch_lane_counts": _counter(rows, "contract_batch_lane"),
            "promotion_decision_status_counts": _decision_counter(rows),
            "addition_plan_id": addition.get("plan_id"),
            "addition_plan_rows": len(addition_rows),
            "addition_publish_release_candidate_rows": (
                (addition.get("summary") or {}).get("publish_release_candidate_rows")
                if (addition.get("summary") or {}).get("publish_release_candidate_rows") is not None
                else (addition.get("summary") or {}).get("release_candidate_not_approval_rows")
            ),
            "addition_candidate_only_no_publish_rows": (
                (addition.get("summary") or {}).get("candidate_only_no_publish_rows")
                if (addition.get("summary") or {}).get("candidate_only_no_publish_rows") is not None
                else (addition.get("summary") or {}).get("no_publish_contract_rows")
            ),
            "runtime_replay_allowed_rows": 0,
            "full375_collateral_gate": "NO-GO",
            "completion_gate": "full375 collateral GO + full_scan path",
        }
    )
    return {
        **base,
        "plan_id": plan_id,
        "generated_at": generated_at or datetime.now().replace(microsecond=0).isoformat(),
        "source_contract_plans": [base.get("plan_id"), addition.get("plan_id")],
        "gate": "NO-GO" if validation_issues else "REVIEW-LOCKED",
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "summary": summary,
        "rows": rows,
        "validation_issues": validation_issues,
    }


def merge_application(
    base: dict[str, Any],
    addition: dict[str, Any],
    *,
    projection_id: str,
    source_contract_plan: str,
    generated_at: str | None = None,
) -> dict[str, Any]:
    base_rows = _rows(base, "applied_rows")
    addition_rows = _rows(addition, "applied_rows")
    rows = [*base_rows, *addition_rows]
    validation_issues = [
        *(base.get("validation_issues") or []),
        *(addition.get("validation_issues") or []),
    ]
    skipped = Counter(base.get("summary", {}).get("skipped_contract_action_counts") or {})
    skipped.update(addition.get("summary", {}).get("skipped_contract_action_counts") or {})
    summary = dict(base.get("summary") or {})
    summary.update(
        {
            "contract_plan_rows": (base.get("summary") or {}).get("contract_plan_rows", 0)
            + (addition.get("summary") or {}).get("contract_plan_rows", 0),
            "publish_contract_plan_rows": len(rows),
            "applied_publish_contract_rows": len(rows),
            "restore_plan_rows": sum(
                1 for row in rows if row.get("contract_action") == "expected_title_restore_contract_case"
            ),
            "applied_restore_rows": sum(
                1 for row in rows if row.get("contract_action") == "expected_title_restore_contract_case"
            ),
            "applied_expected_audit_update_rows": sum(
                1 for row in rows if row.get("contract_action") == "expected_audit_update_exclusion_contract_case"
            ),
            "applied_canonical_cleanup_rows": sum(
                1 for row in rows if row.get("contract_action") == "canonical_cleanup_or_url_correction_contract_case"
            ),
            "applied_candidate_set_restore_rows": sum(
                1 for row in rows if row.get("contract_action") == "candidate_set_expected_restore_contract_case"
            ),
            "validation_issue_count": len(validation_issues),
            "skipped_contract_action_counts": dict(skipped),
            "addition_projection_id": addition.get("projection_id"),
            "addition_applied_rows": len(addition_rows),
            "runtime_replay_allowed_rows": 0,
            "full375_collateral_gate": "NO-GO",
            "completion_gate": "full375 collateral GO + full_scan path",
        }
    )
    return {
        **base,
        "projection_id": projection_id,
        "generated_at": generated_at or datetime.now().replace(microsecond=0).isoformat(),
        "source_contract_plan": source_contract_plan,
        "gate": "NO-GO" if validation_issues else "REVIEW-LOCKED",
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "summary": summary,
        "validation_issues": validation_issues,
        "applied_rows": rows,
    }


def write_plan_markdown(path: Path, plan: dict[str, Any], addition: dict[str, Any]) -> None:
    summary = plan["summary"]
    lines = [
        f"# {plan.get('plan_id')}",
        "",
        "기존 contract plan에 추가 shared-gate contract plan을 병합한 projection-only 산출물이다.",
        "",
        "## 요약",
        "",
        f"- contract_plan_rows: `{summary.get('contract_plan_rows')}`",
        f"- contract_action_counts: `{summary.get('contract_action_counts')}`",
        f"- promotion_decision_status_counts: `{summary.get('promotion_decision_status_counts')}`",
        f"- addition_plan_id: `{summary.get('addition_plan_id')}`",
        f"- addition_plan_rows: `{summary.get('addition_plan_rows')}`",
        f"- addition_publish_release_candidate_rows: `{summary.get('addition_publish_release_candidate_rows')}`",
        f"- addition_candidate_only_no_publish_rows: `{summary.get('addition_candidate_only_no_publish_rows')}`",
        "- runtime_replay_allowed_rows: `0`",
        "- full375 collateral: `NO-GO`",
        "- semantic_quality: `REVIEW-LOCKED`",
        "- full_scan_approval: `false`",
        "",
        "## 추가 행",
        "",
    ]
    for row in addition.get("rows") or []:
        decision = row.get("promotion_decision") if isinstance(row.get("promotion_decision"), dict) else {}
        lines.append(
            f"- `{row.get('post_id')}` action=`{row.get('contract_action')}` "
            f"decision=`{decision.get('status')}` target=`{row.get('target_title')}`"
        )
    lines.extend(["", "## Gate 해석", ""])
    lines.append(
        "추가 publish 행은 release candidate이며 approval이 아니다. candidate-only 행은 no-publish contract로 보존한다. "
        "완료 기준은 계속 `full375 collateral GO + full_scan path`다."
    )
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def write_application_markdown(path: Path, application: dict[str, Any], addition: dict[str, Any]) -> None:
    summary = application["summary"]
    lines = [
        f"# {application.get('projection_id')}",
        "",
        "기존 projection application에 추가 shared-gate publish-class 적용 행을 병합한 projection-only 산출물이다.",
        "",
        "## 요약",
        "",
        f"- applied_publish_contract_rows: `{summary.get('applied_publish_contract_rows')}`",
        f"- addition_projection_id: `{summary.get('addition_projection_id')}`",
        f"- addition_applied_rows: `{summary.get('addition_applied_rows')}`",
        f"- applied_restore_rows: `{summary.get('applied_restore_rows')}`",
        f"- applied_canonical_cleanup_rows: `{summary.get('applied_canonical_cleanup_rows')}`",
        f"- skipped_contract_action_counts: `{summary.get('skipped_contract_action_counts')}`",
        "- runtime_replay_allowed_rows: `0`",
        "- full375 collateral: `NO-GO`",
        "- semantic_quality: `REVIEW-LOCKED`",
        "- full_scan_approval: `false`",
        "",
        "## 추가 적용 행",
        "",
    ]
    for row in addition.get("applied_rows") or []:
        lines.append(
            f"- `{row.get('post_id')}` action=`{row.get('contract_action')}` "
            f"target=`{row.get('target_title')}` url=`{row.get('target_url')}`"
        )
    lines.extend(["", "## Gate 해석", ""])
    lines.append(
        "적용 행은 shared `PromotionDecision`/`publish_contract_trace`/`publish_ledger` 동기화 증거다. "
        "새 runtime replay나 full_scan approval이 아니다."
    )
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge a contract plan/application pair with an additional pair.")
    parser.add_argument("--base-plan", required=True, type=Path)
    parser.add_argument("--addition-plan", required=True, type=Path)
    parser.add_argument("--base-application", required=True, type=Path)
    parser.add_argument("--addition-application", required=True, type=Path)
    parser.add_argument("--plan-id", required=True)
    parser.add_argument("--projection-id", required=True)
    parser.add_argument("--output-plan-json", required=True, type=Path)
    parser.add_argument("--output-plan-md", required=True, type=Path)
    parser.add_argument("--output-application-json", required=True, type=Path)
    parser.add_argument("--output-application-md", required=True, type=Path)
    parser.add_argument("--fail-on-validation-issue", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    base_plan = load_json(args.base_plan)
    addition_plan = load_json(args.addition_plan)
    base_application = load_json(args.base_application)
    addition_application = load_json(args.addition_application)
    plan = merge_plan(base_plan, addition_plan, plan_id=args.plan_id)
    application = merge_application(
        base_application,
        addition_application,
        projection_id=args.projection_id,
        source_contract_plan=args.plan_id,
    )
    write_json(args.output_plan_json, plan)
    write_json(args.output_application_json, application)
    write_plan_markdown(args.output_plan_md, plan, addition_plan)
    write_application_markdown(args.output_application_md, application, addition_application)
    summary = {
        "plan_gate": plan["gate"],
        "application_gate": application["gate"],
        "plan_summary": plan["summary"],
        "application_summary": application["summary"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.fail_on_validation_issue and (plan["validation_issues"] or application["validation_issues"]):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
