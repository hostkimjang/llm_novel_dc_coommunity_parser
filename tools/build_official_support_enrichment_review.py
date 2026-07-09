from __future__ import annotations

import argparse
import copy
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from tools.build_ordinary_restore_contract_plan import (
        OFFICIAL_MISSING_ACTION,
        RESTORE_LANE,
    )
    from tools.test_run_dashboard_policy import test_run_execution_contract
except ModuleNotFoundError:  # direct script execution
    from build_ordinary_restore_contract_plan import OFFICIAL_MISSING_ACTION, RESTORE_LANE
    from test_run_dashboard_policy import test_run_execution_contract


EXACT_STATE = "official_detail_exact_title_found"
TITLE_MISMATCH_STATE = "official_detail_found_target_title_mismatch"
EBOOK_OR_CLASSIC_STATE = "ebook_or_classic_policy_review_required"
CANDIDATE_OFFICIAL_MISSING_ACTION = "official_support_missing_candidate_hold_contract_case"
CANDIDATE_SET_LANE = "candidate_set_rebuild_review"
ENRICH_ACTION = "append_official_ref_to_restore_dispatch"
CANONICAL_REWRITE_ACTION = "canonical_title_rewrite_review_required"
CANONICAL_REWRITE_DISPATCH_ACTION = "rewrite_target_to_official_restore_dispatch"
EBOOK_POLICY_HOLD_ACTION = "non_webnovel_ebook_policy_hold"
MISSING_REVIEW_ACTION = "official_support_review_missing"

WEBNOVEL_DETAIL_MARKERS = (
    "novelpia.com/novel/",
    "novel.munpia.com/",
    "mm.munpia.com/novel/detail/",
    "page.kakao.com/content/",
    "ridibooks.com/books/",
    "series.naver.com/novel/detail.series",
)


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


def _compact(value: Any) -> str:
    return "".join(ch for ch in _string(value).lower() if ch.isalnum())


def _same_title(left: Any, right: Any) -> bool:
    return bool(_compact(left) and _compact(left) == _compact(right))


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _string(value).lower() in {"1", "true", "yes", "y", "go"}


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


def _by_post_id(rows: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    indexed: dict[int, dict[str, Any]] = {}
    for row in rows:
        post_id = _post_id(row.get("post_id"))
        if post_id is not None:
            indexed[post_id] = row
    return indexed


def _append_unique(values: Any, *items: str) -> list[str]:
    out = [str(value) for value in (values or []) if str(value).strip()] if isinstance(values, list) else []
    for item in items:
        if item and item not in out:
            out.append(item)
    return out


def _official_detail_url_supported(url: Any) -> bool:
    text = _string(url).lower()
    return bool(text and any(marker in text for marker in WEBNOVEL_DETAIL_MARKERS))


def _review_action(review_row: dict[str, Any] | None, plan_row: dict[str, Any]) -> str:
    if not review_row:
        return MISSING_REVIEW_ACTION
    state = _string(review_row.get("official_support_state"))
    if state == EXACT_STATE:
        return ENRICH_ACTION
    if state == TITLE_MISMATCH_STATE:
        return CANONICAL_REWRITE_ACTION
    if state == EBOOK_OR_CLASSIC_STATE:
        return EBOOK_POLICY_HOLD_ACTION
    return _string(review_row.get("review_action")) or "official_support_review_hold"


def _can_enrich(review_row: dict[str, Any] | None, plan_row: dict[str, Any]) -> bool:
    if not review_row:
        return False
    if _string(review_row.get("official_support_state")) != EXACT_STATE:
        return False
    if review_row.get("accepted_by_shared_official_detail_contract") is not True:
        return False
    if not _official_detail_url_supported(review_row.get("official_url")):
        return False
    return _same_title(review_row.get("official_title"), plan_row.get("target_title"))


def _canonical_rewrite_title(review_row: dict[str, Any]) -> str:
    return _string(
        review_row.get("canonical_rewrite_title")
        or review_row.get("rewritten_title")
        or review_row.get("official_title")
    )


def _can_canonical_rewrite(review_row: dict[str, Any] | None, plan_row: dict[str, Any]) -> bool:
    if not review_row:
        return False
    if _string(review_row.get("official_support_state")) != TITLE_MISMATCH_STATE:
        return False
    if review_row.get("canonical_rewrite_allowed") is not True:
        return False
    if not _official_detail_url_supported(review_row.get("official_url")):
        return False
    official_title = _string(review_row.get("official_title"))
    rewrite_title = _canonical_rewrite_title(review_row)
    target_title = _string(plan_row.get("target_title"))
    if not _same_title(rewrite_title, official_title):
        return False
    if not official_title or _same_title(official_title, target_title):
        return False
    if not any(
        _truthy(review_row.get(key))
        for key in (
            "source_native_rewrite_support",
            "alias_relation_supported",
            "specific_work_target_supported",
        )
    ):
        return False
    return bool(_string(review_row.get("rewrite_reason_ko") or review_row.get("source_evidence_ko")))


def _enriched_dispatch_lane(plan_row: dict[str, Any]) -> str:
    if plan_row.get("contract_action") == CANDIDATE_OFFICIAL_MISSING_ACTION:
        return CANDIDATE_SET_LANE
    return RESTORE_LANE


def _make_enriched_dispatch_row(plan_row: dict[str, Any], review_row: dict[str, Any], review_id: str) -> dict[str, Any]:
    official_url = _string(review_row.get("official_url"))
    official_title = _string(review_row.get("official_title"))
    evidence_refs = _append_unique(
        [official_url],
        *[str(value) for value in plan_row.get("evidence_refs") or []],
        *[str(value) for value in review_row.get("source_urls") or []],
        f"docs/devs/{review_id}.json#post_id={plan_row.get('post_id')}",
    )
    return {
        "post_id": plan_row.get("post_id"),
        "dispatch_lane": _enriched_dispatch_lane(plan_row),
        "triage_bucket": plan_row.get("triage_bucket"),
        "review_label": plan_row.get("review_label"),
        "selected_title": official_title or plan_row.get("target_title"),
        "selected_url": official_url,
        "evidence_grade": plan_row.get("evidence_grade") or "Strong",
        "source_native_verdict": plan_row.get("source_native_verdict"),
        "rationale_ko": (
            f"{plan_row.get('rationale_ko') or ''} "
            f"공식 detail URL 보강: {official_title} / {official_url}"
        ).strip(),
        "actions": _append_unique(
            ["repair_safe_loss_restore_supported_title", "shared_promotion_gate_wiring_required"],
            "official_detail_url_enriched_from_web_review",
        ),
        "evidence_refs": evidence_refs,
        "official_support_review_id": review_id,
        "official_support_state": review_row.get("official_support_state"),
        "official_title": official_title or None,
        "official_url": official_url or None,
        "runtime_replay_allowed": False,
        "full_scan_approval": False,
    }


def _make_canonical_rewrite_dispatch_row(
    plan_row: dict[str, Any], review_row: dict[str, Any], review_id: str
) -> dict[str, Any]:
    official_url = _string(review_row.get("official_url"))
    official_title = _string(review_row.get("official_title"))
    rewrite_title = _canonical_rewrite_title(review_row)
    previous_target = _string(plan_row.get("target_title"))
    evidence_refs = _append_unique(
        [official_url],
        *[str(value) for value in plan_row.get("evidence_refs") or []],
        *[str(value) for value in review_row.get("source_urls") or []],
        f"docs/devs/{review_id}.json#post_id={plan_row.get('post_id')}",
    )
    rewrite_reason = _string(review_row.get("rewrite_reason_ko") or review_row.get("source_evidence_ko"))
    return {
        "post_id": plan_row.get("post_id"),
        "dispatch_lane": _enriched_dispatch_lane(plan_row),
        "triage_bucket": plan_row.get("triage_bucket"),
        "review_label": plan_row.get("review_label"),
        "selected_title": rewrite_title or official_title,
        "selected_url": official_url,
        "evidence_grade": plan_row.get("evidence_grade") or "Strong",
        "source_native_verdict": plan_row.get("source_native_verdict"),
        "rationale_ko": (
            f"{plan_row.get('rationale_ko') or ''} "
            f"공식 title rewrite: `{previous_target}` -> `{rewrite_title or official_title}`. {rewrite_reason}"
        ).strip(),
        "actions": _append_unique(
            ["repair_safe_loss_restore_supported_title", "shared_promotion_gate_wiring_required"],
            "official_detail_url_canonical_title_rewrite",
        ),
        "evidence_refs": evidence_refs,
        "official_support_review_id": review_id,
        "official_support_state": review_row.get("official_support_state"),
        "official_title": official_title or None,
        "official_url": official_url or None,
        "canonical_rewrite_from_target_title": previous_target or None,
        "canonical_rewrite_title": rewrite_title or official_title or None,
        "canonical_rewrite_reason_ko": rewrite_reason or None,
        "runtime_replay_allowed": False,
        "full_scan_approval": False,
    }


def build_review(
    *,
    contract_plan: dict[str, Any],
    reviewed_refs: dict[str, Any],
    review_id: str,
    generated_at: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    missing_actions = {OFFICIAL_MISSING_ACTION, CANDIDATE_OFFICIAL_MISSING_ACTION}
    plan_rows = [row for row in _rows(contract_plan) if row.get("contract_action") in missing_actions]
    review_by_id = _by_post_id(_rows(reviewed_refs))
    validation_issues: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    enriched_rows: list[dict[str, Any]] = []
    canonical_rewrite_rows: list[dict[str, Any]] = []
    state_counts: Counter[str] = Counter()
    action_counts: Counter[str] = Counter()

    for plan_row in plan_rows:
        post_id = _post_id(plan_row.get("post_id"))
        review_row = review_by_id.get(post_id or -1)
        action = _review_action(review_row, plan_row)
        can_enrich = _can_enrich(review_row, plan_row)
        can_canonical_rewrite = _can_canonical_rewrite(review_row, plan_row)
        if can_canonical_rewrite:
            action = CANONICAL_REWRITE_DISPATCH_ACTION
        state = _string((review_row or {}).get("official_support_state")) or "missing_review"
        issues: list[str] = []
        if not review_row:
            issues.append("official_support_review_row_missing")
        elif action == ENRICH_ACTION and not can_enrich:
            issues.append("official_support_exact_review_not_enrichable")
        elif can_enrich and action != ENRICH_ACTION:
            issues.append("enrichable_review_not_marked_for_dispatch")
        elif review_row.get("canonical_rewrite_allowed") is True and not can_canonical_rewrite:
            issues.append("canonical_rewrite_allowed_but_contract_not_satisfied")
        if issues:
            validation_issues.append({"post_id": plan_row.get("post_id"), "issues": issues})

        if can_enrich:
            enriched_rows.append(_make_enriched_dispatch_row(plan_row, review_row or {}, review_id))
        if can_canonical_rewrite:
            canonical_rewrite_rows.append(_make_canonical_rewrite_dispatch_row(plan_row, review_row or {}, review_id))

        state_counts[state] += 1
        action_counts[action] += 1
        dispatch_row = can_enrich or can_canonical_rewrite
        rows.append(
            {
                "post_id": plan_row.get("post_id"),
                "target_title": plan_row.get("target_title"),
                "previous_contract_action": plan_row.get("contract_action"),
                "official_support_state": state,
                "review_action": action,
                "official_title": (review_row or {}).get("official_title"),
                "official_url": (review_row or {}).get("official_url"),
                "accepted_by_shared_official_detail_contract": (review_row or {}).get(
                    "accepted_by_shared_official_detail_contract"
                )
                is True,
                "canonical_rewrite_allowed": (review_row or {}).get("canonical_rewrite_allowed") is True,
                "canonical_rewrite_title": _canonical_rewrite_title(review_row or {}) or None,
                "canonical_rewrite_dispatch_row": can_canonical_rewrite,
                "webnovel_detail_url_supported": _official_detail_url_supported((review_row or {}).get("official_url")),
                "title_matches_target": _same_title((review_row or {}).get("official_title"), plan_row.get("target_title")),
                "enriched_restore_dispatch_row": dispatch_row,
                "runtime_replay_allowed": False,
                "full_scan_approval": False,
                "source_urls": (review_row or {}).get("source_urls") or [],
                "source_evidence_ko": (review_row or {}).get("source_evidence_ko"),
                "hold_reason_ko": (review_row or {}).get("hold_reason_ko"),
                "rewrite_reason_ko": (review_row or {}).get("rewrite_reason_ko"),
                "rationale_ko": plan_row.get("rationale_ko"),
                "validation_issues": issues,
            }
        )

    dispatch_rows = [*enriched_rows, *canonical_rewrite_rows]
    dispatch = {
        "report_type": "official_support_enriched_restore_dispatch",
        "dispatch_id": f"{review_id}_enriched_restore_dispatch",
        "generated_at": generated_at or datetime.now().replace(microsecond=0).isoformat(),
        "source_contract_plan": contract_plan.get("plan_id"),
        "source_review_refs": reviewed_refs.get("review_id") or review_id,
        "gate": "REVIEW-LOCKED",
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "summary": {
            "source_official_missing_hold_rows": len(plan_rows),
            "enriched_restore_dispatch_rows": len(dispatch_rows),
            "exact_official_enriched_dispatch_rows": len(enriched_rows),
            "canonical_rewrite_dispatch_rows": len(canonical_rewrite_rows),
            "runtime_replay_allowed_rows": 0,
            "completion_gate": "adjusted full375 collateral GO + full_scan path",
        },
        "execution_contract": test_run_execution_contract(len(dispatch_rows)),
        "rows": dispatch_rows,
        "approval_boundary": {
            "enriched_dispatch_is_not_runtime_replay": True,
            "official_url_review_is_not_full_scan_approval": True,
            "restore_plan_must_rerun_shared_gate": True,
        },
    }
    report = {
        "report_type": "official_support_enrichment_review",
        "review_id": review_id,
        "generated_at": generated_at or dispatch["generated_at"],
        "source_contract_plan": contract_plan.get("plan_id"),
        "source_review_refs": reviewed_refs.get("review_id") or review_id,
        "gate": "NO-GO" if validation_issues else "REVIEW-LOCKED",
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "summary": {
            "source_official_missing_hold_rows": len(plan_rows),
            "reviewed_rows": len(rows),
            "validation_issue_count": len(validation_issues),
            "state_counts": dict(state_counts),
            "review_action_counts": dict(action_counts),
            "exact_official_detail_rows": state_counts.get(EXACT_STATE, 0),
            "enriched_restore_dispatch_rows": len(dispatch_rows),
            "exact_official_enriched_dispatch_rows": len(enriched_rows),
            "canonical_rewrite_dispatch_rows": len(canonical_rewrite_rows),
            "hold_rows": len(rows) - len(dispatch_rows),
            "runtime_replay_allowed_rows": 0,
            "full375_collateral_gate": "NO-GO",
            "completion_gate": "adjusted full375 collateral GO + full_scan path",
        },
        "validation_issues": validation_issues,
        "rows": rows,
        "enriched_dispatch_id": dispatch["dispatch_id"],
        "approval_boundary": {
            "official_support_review_is_not_runtime_replay": True,
            "enriched_dispatch_must_pass_lane_contract_plan": True,
            "canonical_rewrite_must_be_explicitly_allowed": True,
            "held_rows_remain_ordinary_residual_followup": True,
            "full_scan_approval": False,
        },
    }
    return report, dispatch


def write_markdown(report: dict[str, Any], path: Path) -> None:
    summary = report["summary"]
    source_plan = report.get("source_contract_plan") or "unknown"
    lines = [
        f"# {report.get('review_id')}",
        "",
        f"`{source_plan}`의 official-support missing hold 행을 공식 detail URL 근거로 재분류한 리뷰다. "
        "이 산출물은 새 runtime replay가 아니며, enriched dispatch도 해당 lane의 contract plan을 다시 통과해야 한다.",
        "",
        "## 요약",
        "",
        f"- gate: `{report['gate']}`",
        f"- semantic_quality: `{report['semantic_quality']}`",
        f"- full_scan_approval: `{str(report['full_scan_approval']).lower()}`",
        f"- source_official_missing_hold_rows: `{summary['source_official_missing_hold_rows']}`",
        f"- reviewed_rows: `{summary['reviewed_rows']}`",
        f"- validation_issue_count: `{summary['validation_issue_count']}`",
        f"- state_counts: `{summary['state_counts']}`",
        f"- review_action_counts: `{summary['review_action_counts']}`",
        f"- enriched_restore_dispatch_rows: `{summary['enriched_restore_dispatch_rows']}`",
        f"- exact_official_enriched_dispatch_rows: `{summary['exact_official_enriched_dispatch_rows']}`",
        f"- canonical_rewrite_dispatch_rows: `{summary['canonical_rewrite_dispatch_rows']}`",
        f"- hold_rows: `{summary['hold_rows']}`",
        f"- runtime_replay_allowed_rows: `{summary['runtime_replay_allowed_rows']}`",
        f"- full375 collateral: `{summary['full375_collateral_gate']}`",
        "",
        "## Rows",
        "",
    ]
    for row in report.get("rows") or []:
        lines.append(
            f"- `{row.get('post_id')}` state=`{row.get('official_support_state')}` "
            f"action=`{row.get('review_action')}` target=`{row.get('target_title')}` "
            f"official=`{row.get('official_title')}` url=`{row.get('official_url')}` "
            f"dispatch=`{row.get('enriched_restore_dispatch_row')}`"
        )
    lines.extend(["", "## Gate 해석", ""])
    lines.append(
        f"정확 공식 detail URL 또는 명시적 canonical rewrite 계약이 확인된 "
        f"`{summary['enriched_restore_dispatch_rows']}`건만 enriched dispatch로 넘긴다. "
        f"나머지 `{summary['hold_rows']}`건은 canonical rewrite 또는 eBook/classic 정책 검토가 필요하므로 publish 후보로 세지 않는다. "
        "다음 단계는 enriched dispatch를 해당 lane의 contract plan에 다시 통과시키고 projection-only full375 collateral을 재확인하는 것이다."
    )
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Review official-detail support for restore hold rows.")
    parser.add_argument("--contract-plan", required=True, type=Path)
    parser.add_argument("--reviewed-refs", required=True, type=Path)
    parser.add_argument("--review-id", default="loop585_official_support_enrichment_review")
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-md", required=True, type=Path)
    parser.add_argument("--output-dispatch-json", required=True, type=Path)
    parser.add_argument("--fail-on-validation-issue", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report, dispatch = build_review(
        contract_plan=load_json(args.contract_plan),
        reviewed_refs=load_json(args.reviewed_refs),
        review_id=args.review_id,
    )
    write_json(args.output_json, report)
    write_markdown(report, args.output_md)
    write_json(args.output_dispatch_json, dispatch)
    print(json.dumps({"gate": report["gate"], "summary": report["summary"]}, ensure_ascii=False, indent=2))
    if args.fail_on_validation_issue and report["validation_issues"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
