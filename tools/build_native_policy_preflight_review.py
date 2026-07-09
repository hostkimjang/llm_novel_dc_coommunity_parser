from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from tools.build_ordinary_restore_contract_plan import RESTORE_LANE
    from tools.test_run_dashboard_policy import test_run_execution_contract
except ModuleNotFoundError:  # direct script execution
    from build_ordinary_restore_contract_plan import RESTORE_LANE
    from test_run_dashboard_policy import test_run_execution_contract


NATIVE_WEB_LANE = "native_web_image_evidence_review"
NO_PUBLISH_GUARD_LANE = "no_publish_guard_review"
ACCEPTED_STATES = {
    "official_detail_and_store_context_confirmed",
    "native_policy_exact_official_detail_confirmed",
}
RESTORE_DISPATCH_ACTION = "native_policy_restore_dispatch"
HOLD_ACTION = "native_policy_hold_no_dispatch"
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


def _post_id(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    if not isinstance(rows, list):
        raise ValueError("payload must contain rows list")
    return [row for row in rows if isinstance(row, dict)]


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


def _has_lane(row: dict[str, Any], lane: str) -> bool:
    if _string(row.get("dispatch_lane")) == lane:
        return True
    lanes = row.get("batch_lanes")
    return isinstance(lanes, list) and lane in lanes


def _is_preflight_row(row: dict[str, Any]) -> bool:
    return _string(row.get("dispatch_lane")) in {NATIVE_WEB_LANE, NO_PUBLISH_GUARD_LANE}


def _webnovel_detail_url_supported(url: Any) -> bool:
    text = _string(url).lower()
    return bool(text and any(marker in text for marker in WEBNOVEL_DETAIL_MARKERS))


def _is_accepted_review(review_row: dict[str, Any] | None) -> bool:
    if not review_row:
        return False
    return review_row.get("accepted_by_native_policy_contract") is True and (
        _string(review_row.get("native_policy_state")) in ACCEPTED_STATES
    )


def _review_action(review_row: dict[str, Any] | None) -> str:
    if not review_row:
        return "native_policy_review_missing"
    if _is_accepted_review(review_row):
        return RESTORE_DISPATCH_ACTION
    return _string(review_row.get("review_action")) or HOLD_ACTION


def _needs_store_context(plan_row: dict[str, Any]) -> bool:
    actions = plan_row.get("actions")
    return isinstance(actions, list) and "merchandise_or_emoticon_work_context_guard" in actions


def _can_dispatch(plan_row: dict[str, Any], review_row: dict[str, Any] | None) -> bool:
    if not _is_accepted_review(review_row):
        return False
    if not _webnovel_detail_url_supported(review_row.get("official_url")):
        return False
    official_title = _string(review_row.get("official_title"))
    target_title = _string(plan_row.get("target_title"))
    if not _same_title(official_title, target_title):
        return False
    if _needs_store_context(plan_row) and review_row.get("store_context_confirmed") is not True:
        return False
    return True


def _make_dispatch_row(plan_row: dict[str, Any], review_row: dict[str, Any], review_id: str) -> dict[str, Any]:
    official_title = _string(review_row.get("official_title"))
    official_url = _string(review_row.get("official_url"))
    source_evidence = _string(review_row.get("source_evidence_ko"))
    evidence_refs = _append_unique(
        [official_url],
        *[str(value) for value in plan_row.get("evidence_refs") or []],
        *[str(value) for value in review_row.get("source_urls") or []],
        f"docs/devs/{review_id}.json#post_id={plan_row.get('post_id')}",
    )
    actions = _append_unique(
        plan_row.get("actions") or [],
        "native_policy_preflight_confirmed",
        "official_detail_url_enriched_from_native_policy_review",
    )
    if review_row.get("store_context_confirmed") is True:
        actions = _append_unique(actions, "work_specific_store_context_confirmed")
    return {
        "post_id": plan_row.get("post_id"),
        "dispatch_lane": RESTORE_LANE,
        "triage_bucket": plan_row.get("triage_bucket"),
        "review_label": plan_row.get("review_label"),
        "selected_title": official_title,
        "selected_url": official_url,
        "evidence_grade": plan_row.get("evidence_grade") or "Strong",
        "source_native_verdict": plan_row.get("source_native_verdict"),
        "rationale_ko": (
            f"{plan_row.get('rationale_ko') or ''} "
            f"Native/policy preflight 확인: {source_evidence or official_url}"
        ).strip(),
        "actions": actions,
        "evidence_refs": evidence_refs,
        "native_policy_review_id": review_id,
        "native_policy_state": review_row.get("native_policy_state"),
        "official_title": official_title or None,
        "official_url": official_url or None,
        "store_url": _string(review_row.get("store_url")) or None,
        "store_context_confirmed": review_row.get("store_context_confirmed") is True,
        "runtime_replay_allowed": False,
        "full_scan_approval": False,
    }


def build_review(
    *,
    contract_queue: dict[str, Any],
    reviewed_refs: dict[str, Any],
    review_id: str,
    generated_at: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    source_rows = [row for row in _rows(contract_queue) if _is_preflight_row(row)]
    review_by_id = _by_post_id(_rows(reviewed_refs))
    validation_issues: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    dispatch_rows: list[dict[str, Any]] = []
    state_counts: Counter[str] = Counter()
    action_counts: Counter[str] = Counter()
    lane_counts: Counter[str] = Counter()

    generated = generated_at or datetime.now().replace(microsecond=0).isoformat()
    for plan_row in source_rows:
        post_id = _post_id(plan_row.get("post_id"))
        review_row = review_by_id.get(post_id or -1)
        action = _review_action(review_row)
        state = _string((review_row or {}).get("native_policy_state")) or "missing_review"
        can_dispatch = _can_dispatch(plan_row, review_row)
        issues: list[str] = []
        if not review_row:
            issues.append("native_policy_review_row_missing")
        elif action == RESTORE_DISPATCH_ACTION and not can_dispatch:
            issues.append("native_policy_dispatch_contract_not_satisfied")
        elif can_dispatch and action != RESTORE_DISPATCH_ACTION:
            issues.append("dispatchable_review_not_marked_for_restore")
        if issues:
            validation_issues.append({"post_id": plan_row.get("post_id"), "issues": issues})
        if can_dispatch:
            dispatch_rows.append(_make_dispatch_row(plan_row, review_row or {}, review_id))

        if _has_lane(plan_row, NATIVE_WEB_LANE):
            lane_counts[NATIVE_WEB_LANE] += 1
        if _has_lane(plan_row, NO_PUBLISH_GUARD_LANE):
            lane_counts[NO_PUBLISH_GUARD_LANE] += 1
        state_counts[state] += 1
        action_counts[action] += 1
        rows.append(
            {
                "post_id": plan_row.get("post_id"),
                "target_title": plan_row.get("target_title"),
                "dispatch_lane": plan_row.get("dispatch_lane"),
                "batch_lanes": plan_row.get("batch_lanes") or [],
                "native_policy_state": state,
                "review_action": action,
                "official_title": (review_row or {}).get("official_title"),
                "official_url": (review_row or {}).get("official_url"),
                "store_url": (review_row or {}).get("store_url"),
                "accepted_by_native_policy_contract": (review_row or {}).get(
                    "accepted_by_native_policy_contract"
                )
                is True,
                "webnovel_detail_url_supported": _webnovel_detail_url_supported(
                    (review_row or {}).get("official_url")
                ),
                "title_matches_target": _same_title((review_row or {}).get("official_title"), plan_row.get("target_title")),
                "store_context_required": _needs_store_context(plan_row),
                "store_context_confirmed": (review_row or {}).get("store_context_confirmed") is True,
                "restore_dispatch_row": can_dispatch,
                "runtime_replay_allowed": False,
                "full_scan_approval": False,
                "source_urls": (review_row or {}).get("source_urls") or [],
                "source_evidence_ko": (review_row or {}).get("source_evidence_ko"),
                "hold_reason_ko": (review_row or {}).get("hold_reason_ko"),
                "rationale_ko": plan_row.get("rationale_ko"),
                "validation_issues": issues,
            }
        )

    dispatch = {
        "report_type": "native_policy_preflight_restore_dispatch",
        "dispatch_id": f"{review_id}_restore_dispatch",
        "generated_at": generated,
        "source_contract_queue": contract_queue.get("queue_id") or contract_queue.get("dispatch_id"),
        "source_review_refs": reviewed_refs.get("review_id") or review_id,
        "gate": "REVIEW-LOCKED",
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "summary": {
            "source_preflight_rows": len(source_rows),
            "restore_dispatch_rows": len(dispatch_rows),
            "native_web_hold_rows": sum(1 for row in rows if row.get("review_action") != RESTORE_DISPATCH_ACTION),
            "runtime_replay_allowed_rows": 0,
            "completion_gate": "adjusted full375 collateral GO + full_scan path",
        },
        "execution_contract": test_run_execution_contract(len(dispatch_rows)),
        "rows": dispatch_rows,
        "approval_boundary": {
            "native_policy_dispatch_is_not_runtime_replay": True,
            "restore_dispatch_must_pass_shared_promotion_gate": True,
            "held_rows_remain_ordinary_residual_followup": True,
            "full_scan_approval": False,
        },
    }
    report = {
        "report_type": "native_policy_preflight_review",
        "review_id": review_id,
        "generated_at": generated,
        "source_contract_queue": contract_queue.get("queue_id") or contract_queue.get("dispatch_id"),
        "source_review_refs": reviewed_refs.get("review_id") or review_id,
        "gate": "NO-GO" if validation_issues else "REVIEW-LOCKED",
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "summary": {
            "source_preflight_rows": len(source_rows),
            "reviewed_rows": len(rows),
            "validation_issue_count": len(validation_issues),
            "lane_counts": dict(lane_counts),
            "state_counts": dict(state_counts),
            "review_action_counts": dict(action_counts),
            "restore_dispatch_rows": len(dispatch_rows),
            "hold_rows": len(rows) - len(dispatch_rows),
            "runtime_replay_allowed_rows": 0,
            "full375_collateral_gate": "NO-GO",
            "completion_gate": "adjusted full375 collateral GO + full_scan path",
        },
        "validation_issues": validation_issues,
        "rows": rows,
        "restore_dispatch_id": dispatch["dispatch_id"],
        "approval_boundary": {
            "native_policy_review_is_not_runtime_replay": True,
            "accepted_rows_must_pass_shared_restore_plan": True,
            "native_web_context_only_rows_do_not_publish": True,
            "held_rows_remain_ordinary_residual_followup": True,
            "full_scan_approval": False,
        },
    }
    return report, dispatch


def write_markdown(report: dict[str, Any], path: Path) -> None:
    summary = report["summary"]
    lines = [
        f"# {report.get('review_id')}",
        "",
        "Loop582/587의 native-web/image 및 no-publish guard 사전 검토 행을 공식/native 근거로 재분류한 리뷰다. "
        "이 산출물은 새 runtime replay가 아니며, restore dispatch도 shared promotion gate를 다시 통과해야 한다.",
        "",
        "## 요약",
        "",
        f"- gate: `{report['gate']}`",
        f"- semantic_quality: `{report['semantic_quality']}`",
        f"- full_scan_approval: `{str(report['full_scan_approval']).lower()}`",
        f"- source_preflight_rows: `{summary['source_preflight_rows']}`",
        f"- reviewed_rows: `{summary['reviewed_rows']}`",
        f"- validation_issue_count: `{summary['validation_issue_count']}`",
        f"- lane_counts: `{summary['lane_counts']}`",
        f"- state_counts: `{summary['state_counts']}`",
        f"- review_action_counts: `{summary['review_action_counts']}`",
        f"- restore_dispatch_rows: `{summary['restore_dispatch_rows']}`",
        f"- hold_rows: `{summary['hold_rows']}`",
        f"- runtime_replay_allowed_rows: `{summary['runtime_replay_allowed_rows']}`",
        f"- full375 collateral: `{summary['full375_collateral_gate']}`",
        "",
        "## Rows",
        "",
    ]
    for row in report.get("rows") or []:
        lines.append(
            f"- `{row.get('post_id')}` state=`{row.get('native_policy_state')}` "
            f"action=`{row.get('review_action')}` target=`{row.get('target_title')}` "
            f"official=`{row.get('official_title')}` url=`{row.get('official_url')}` "
            f"dispatch=`{row.get('restore_dispatch_row')}`"
        )
    lines.extend(["", "## Gate 해석", ""])
    lines.append(
        f"공식 detail과 작품별 상품/이모티콘 맥락이 함께 확인된 `{summary['restore_dispatch_rows']}`건만 restore dispatch로 넘긴다. "
        f"나머지 `{summary['hold_rows']}`건은 exact official title 또는 native-web disambiguation이 부족하므로 publish 후보로 세지 않는다. "
        "다음 단계는 dispatch를 shared restore contract plan에 통과시키고 projection-only full375 collateral을 재확인하는 것이다."
    )
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Review native/policy preflight rows before restore dispatch.")
    parser.add_argument("--contract-queue", required=True, type=Path)
    parser.add_argument("--reviewed-refs", required=True, type=Path)
    parser.add_argument("--review-id", default="loop588_native_policy_preflight_review")
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-md", required=True, type=Path)
    parser.add_argument("--output-dispatch-json", required=True, type=Path)
    parser.add_argument("--fail-on-validation-issue", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report, dispatch = build_review(
        contract_queue=load_json(args.contract_queue),
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
