from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


RESTORE = "expected_title_restore_contract_case"
SCRUB = "candidate_scrub_no_publish_contract_case"
VARIANT_HOLD = "canonical_variant_policy_hold_contract_case"
STRONGER_HOLD = "stronger_evidence_hard_hold_contract_case"
MISMATCH_REVIEW = "restore_target_runtime_mismatch_review_required"
EXPECTED_AUDIT_UPDATE = "expected_audit_update_exclusion_contract_case"
NATIVE_WEB_HOLD = "native_web_disambiguation_hold_contract_case"
CANONICAL_CLEANUP = "canonical_cleanup_or_url_correction_contract_case"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _string(value: Any) -> str:
    return str(value or "").strip()


def _compact(value: Any) -> str:
    return "".join(ch for ch in _string(value).lower() if ch.isalnum())


def _matches_title(left: Any, right: Any) -> bool:
    return bool(_compact(left) and _compact(left) == _compact(right))


def _matches_url(left: Any, right: Any) -> bool:
    return bool(_string(left) and _string(left) == _string(right))


def _plan_rows(plan: dict[str, Any]) -> list[dict[str, Any]]:
    rows = plan.get("rows")
    if not isinstance(rows, list):
        raise ValueError("contract plan must contain rows list")
    return [row for row in rows if isinstance(row, dict)]


def _projection_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict) and isinstance(payload.get("rows"), list):
        return [row for row in payload["rows"] if isinstance(row, dict)]
    raise ValueError("projection result must be a JSON array or object with rows list")


def _identity(row: dict[str, Any]) -> dict[str, Any]:
    analysis = row.get("analysis_result")
    if isinstance(analysis, dict):
        ident = analysis.get("identity")
        return ident if isinstance(ident, dict) else {}
    ident = row.get("identity")
    return ident if isinstance(ident, dict) else {}


def _novel_identity(row: dict[str, Any]) -> dict[str, Any]:
    ident = _identity(row)
    novel = ident.get("novel_identity")
    return novel if isinstance(novel, dict) else {}


def _candidate_status(row: dict[str, Any]) -> str:
    ident = _identity(row)
    if _string(ident.get("candidate_ledger_status")):
        return _string(ident.get("candidate_ledger_status"))
    ledger = ident.get("candidate_ledger")
    if isinstance(ledger, dict):
        return _string(ledger.get("status"))
    return _string(row.get("candidate_ledger_status"))


def _publish_allowed(row: dict[str, Any]) -> bool:
    ident = _identity(row)
    if isinstance(ident.get("publish_allowed"), bool):
        return bool(ident["publish_allowed"])
    decision = ident.get("promotion_decision")
    if isinstance(decision, dict) and isinstance(decision.get("publish_allowed"), bool):
        return bool(decision["publish_allowed"])
    trace = ident.get("publish_contract_trace")
    if isinstance(trace, dict) and isinstance(trace.get("publish_allowed"), bool):
        return bool(trace["publish_allowed"])
    if isinstance(row.get("publish_allowed"), bool):
        return bool(row["publish_allowed"])
    return False


def _public_title(row: dict[str, Any]) -> str:
    return _string(_novel_identity(row).get("official_title") or row.get("actual_title"))


def _public_url(row: dict[str, Any]) -> str:
    return _string(_novel_identity(row).get("heretic_url") or row.get("actual_url"))


def _projection_by_post_id(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {_string(row.get("post_id")): row for row in rows if _string(row.get("post_id"))}


def _audit_row(plan_row: dict[str, Any], projection_row: dict[str, Any] | None) -> dict[str, Any]:
    post_id = plan_row.get("post_id")
    action = _string(plan_row.get("contract_action"))
    lane = _string(plan_row.get("contract_batch_lane"))
    target_title = _string(plan_row.get("target_title"))
    target_url = _string(plan_row.get("target_url"))
    action = _string(plan_row.get("contract_action"))
    candidate_title = _string(plan_row.get("current_projection_candidate_title"))
    candidate_url = _string(plan_row.get("current_projection_candidate_url"))
    if not candidate_title:
        if action == EXPECTED_AUDIT_UPDATE:
            candidate_title = _string(plan_row.get("expected_title"))
        elif action == CANONICAL_CLEANUP:
            candidate_title = _string(plan_row.get("actual_title"))
    if projection_row is None:
        return {
            "post_id": post_id,
            "contract_batch_lane": lane,
            "contract_action": action,
            "release_gate_state": "projection_row_missing",
            "violation": True,
            "violation_code": "projection_row_missing",
            "runtime_replay_allowed": False,
            "release_candidate_after_contract": False,
        }

    public_title = _public_title(projection_row)
    public_url = _public_url(projection_row)
    publish_allowed = _publish_allowed(projection_row)
    status = _candidate_status(projection_row)
    has_public_identity = bool(public_title or public_url or publish_allowed)
    target_published = _matches_title(public_title, target_title) or _matches_url(public_url, target_url)
    candidate_title_leaked = _matches_title(public_title, candidate_title) and not _matches_title(
        candidate_title, target_title
    )
    candidate_url_leaked = _matches_url(public_url, candidate_url) and not _matches_url(candidate_url, target_url)
    candidate_leaked = candidate_title_leaked or candidate_url_leaked

    release_gate_state = "unknown_contract_action"
    violation_code = ""
    violation = False
    pending_contract = False
    satisfied_no_release = False
    release_candidate = False

    if action == RESTORE:
        if candidate_leaked:
            release_gate_state = "expected_restore_current_candidate_leak_violation"
            violation = True
            violation_code = "current_candidate_leaked_after_expected_restore_plan"
        elif target_published:
            release_gate_state = "expected_restore_contract_satisfied_release_candidate"
            release_candidate = True
        elif not has_public_identity and status == "promotion_blocked":
            release_gate_state = "expected_restore_contract_pending_projection_not_restored"
            pending_contract = True
        elif has_public_identity:
            release_gate_state = "expected_restore_unexpected_public_identity_violation"
            violation = True
            violation_code = "unexpected_public_identity_after_expected_restore_plan"
        else:
            release_gate_state = "expected_restore_contract_pending_unknown_projection_state"
            pending_contract = True
    elif action == SCRUB:
        if candidate_leaked:
            release_gate_state = "scrub_current_candidate_leak_violation"
            violation = True
            violation_code = "current_candidate_leaked_after_scrub_plan"
        elif has_public_identity:
            release_gate_state = "scrub_unexpected_public_identity_violation"
            violation = True
            violation_code = "unexpected_public_identity_after_scrub_plan"
        else:
            release_gate_state = "scrub_contract_satisfied_no_release"
            satisfied_no_release = True
    elif action == VARIANT_HOLD:
        if has_public_identity:
            release_gate_state = "variant_policy_hold_public_identity_violation"
            violation = True
            violation_code = "variant_published_before_policy_contract"
        else:
            release_gate_state = "variant_policy_hold_satisfied_no_release"
            satisfied_no_release = True
    elif action == STRONGER_HOLD:
        if has_public_identity:
            release_gate_state = "stronger_evidence_hold_public_identity_violation"
            violation = True
            violation_code = "hard_hold_published_before_stronger_evidence"
        else:
            release_gate_state = "stronger_evidence_hold_preserved_no_release"
            satisfied_no_release = True
    elif action == MISMATCH_REVIEW:
        if has_public_identity:
            release_gate_state = "restore_target_mismatch_public_identity_violation"
            violation = True
            violation_code = "mismatch_review_published_before_source_native_verdict"
        else:
            release_gate_state = "restore_target_mismatch_preserved_no_release"
            satisfied_no_release = True
    elif action == EXPECTED_AUDIT_UPDATE:
        if candidate_leaked:
            release_gate_state = "expected_audit_update_old_expected_leak_violation"
            violation = True
            violation_code = "old_expected_title_leaked_after_expected_audit_update_plan"
        elif target_published:
            release_gate_state = "expected_audit_update_contract_satisfied_release_candidate"
            release_candidate = True
        elif not has_public_identity and status == "promotion_blocked":
            release_gate_state = "expected_audit_update_contract_pending_projection_not_restored"
            pending_contract = True
        elif has_public_identity:
            release_gate_state = "expected_audit_update_unexpected_public_identity_violation"
            violation = True
            violation_code = "unexpected_public_identity_after_expected_audit_update_plan"
        else:
            release_gate_state = "expected_audit_update_contract_pending_unknown_projection_state"
            pending_contract = True
    elif action == NATIVE_WEB_HOLD:
        if has_public_identity:
            release_gate_state = "native_web_disambiguation_hold_public_identity_violation"
            violation = True
            violation_code = "native_web_hold_published_before_disambiguation"
        else:
            release_gate_state = "native_web_disambiguation_hold_preserved_no_release"
            satisfied_no_release = True
    elif action == CANONICAL_CLEANUP:
        if candidate_leaked:
            release_gate_state = "canonical_cleanup_contaminated_candidate_leak_violation"
            violation = True
            violation_code = "contaminated_candidate_leaked_before_canonical_cleanup"
        elif target_published:
            release_gate_state = "canonical_cleanup_contract_satisfied_release_candidate"
            release_candidate = True
        elif not has_public_identity and status == "promotion_blocked":
            release_gate_state = "canonical_cleanup_contract_pending_projection_not_restored"
            pending_contract = True
        elif has_public_identity:
            release_gate_state = "canonical_cleanup_unexpected_public_identity_violation"
            violation = True
            violation_code = "unexpected_public_identity_before_canonical_cleanup"
        else:
            release_gate_state = "canonical_cleanup_contract_pending_unknown_projection_state"
            pending_contract = True

    return {
        "post_id": post_id,
        "contract_batch_lane": lane,
        "contract_action": action,
        "target_title": target_title or None,
        "target_url": target_url or None,
        "current_projection_candidate_title": candidate_title or None,
        "current_projection_candidate_url": candidate_url or None,
        "public_title": public_title or None,
        "public_url": public_url or None,
        "candidate_ledger_status": status or None,
        "publish_allowed": publish_allowed,
        "release_gate_state": release_gate_state,
        "pending_contract": pending_contract,
        "satisfied_no_release": satisfied_no_release,
        "release_candidate_after_contract": release_candidate,
        "violation": violation,
        "violation_code": violation_code or None,
        "runtime_replay_allowed": False,
    }


def build_audit(
    *,
    contract_plan: dict[str, Any],
    projection_rows: list[dict[str, Any]],
    audit_id: str,
    generated_at: str | None = None,
) -> dict[str, Any]:
    by_post_id = _projection_by_post_id(projection_rows)
    rows = [_audit_row(row, by_post_id.get(_string(row.get("post_id")))) for row in _plan_rows(contract_plan)]
    state_counts = Counter(_string(row.get("release_gate_state")) for row in rows)
    action_counts = Counter(_string(row.get("contract_action")) for row in rows)
    violation_counts = Counter(_string(row.get("violation_code")) for row in rows if row.get("violation"))
    pending_rows = [row for row in rows if row.get("pending_contract")]
    satisfied_no_release_rows = [row for row in rows if row.get("satisfied_no_release")]
    release_candidate_rows = [row for row in rows if row.get("release_candidate_after_contract")]
    violation_rows = [row for row in rows if row.get("violation")]
    validation_issues = []
    if contract_plan.get("gate") == "NO-GO":
        validation_issues.append({"issue": "source_contract_plan_no_go"})
    if contract_plan.get("full_scan_approval") is not False:
        validation_issues.append({"issue": "source_contract_plan_full_scan_approval_not_false"})
    return {
        "report_type": "post_verdict_promotion_gate_release_contract_audit",
        "audit_id": audit_id,
        "generated_at": generated_at or datetime.now().replace(microsecond=0).isoformat(),
        "source_contract_plan": contract_plan.get("plan_id"),
        "gate": "NO-GO" if violation_rows or validation_issues else "REVIEW-LOCKED",
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "summary": {
            "contract_plan_rows": len(rows),
            "projection_rows": len(projection_rows),
            "validation_issue_count": len(validation_issues),
            "violation_row_count": len(violation_rows),
            "pending_contract_rows": len(pending_rows),
            "satisfied_no_release_rows": len(satisfied_no_release_rows),
            "release_candidate_after_contract_rows": len(release_candidate_rows),
            "runtime_replay_allowed_rows": 0,
            "contract_action_counts": dict(action_counts),
            "release_gate_state_counts": dict(state_counts),
            "violation_counts": dict(violation_counts),
            "full375_collateral_gate": "NO-GO",
            "completion_gate": "full375 collateral GO + full_scan path",
        },
        "validation_issues": validation_issues,
        "violation_rows": violation_rows,
        "pending_rows": pending_rows,
        "satisfied_no_release_rows": satisfied_no_release_rows,
        "release_candidate_rows": release_candidate_rows,
        "rows": rows,
        "approval_boundary": {
            "release_contract_audit_is_not_runtime_replay": True,
            "release_candidate_is_not_full_scan_approval": True,
            "runtime_replay_before_full375_collateral_forbidden": True,
            "full375_collateral_remains_no_go": True,
        },
    }


def write_markdown(path: Path, audit: dict[str, Any]) -> None:
    summary = audit["summary"]
    pending_contract_rows = summary["pending_contract_rows"]
    release_candidate_rows = summary["release_candidate_after_contract_rows"]
    satisfied_no_release_rows = summary["satisfied_no_release_rows"]
    runtime_replay_allowed_rows = summary["runtime_replay_allowed_rows"]
    lines = [
        f"# {audit.get('audit_id')}",
        "",
        "Post-verdict promotion-gate contract plan을 current projection 결과에 대조한 release gate 감사다. "
        "이 감사는 새 runtime replay가 아니며, release candidate가 있더라도 full375 collateral GO 전에는 approval이나 full_scan 경로로 보지 않는다.",
        "",
        "## 요약",
        "",
        f"- gate: `{audit['gate']}`",
        f"- semantic_quality: `{audit['semantic_quality']}`",
        f"- full_scan_approval: `{str(audit['full_scan_approval']).lower()}`",
        f"- contract_plan_rows: `{summary['contract_plan_rows']}`",
        f"- projection_rows: `{summary['projection_rows']}`",
        f"- validation_issue_count: `{summary['validation_issue_count']}`",
        f"- violation_row_count: `{summary['violation_row_count']}`",
        f"- pending_contract_rows: `{summary['pending_contract_rows']}`",
        f"- satisfied_no_release_rows: `{summary['satisfied_no_release_rows']}`",
        f"- release_candidate_after_contract_rows: `{summary['release_candidate_after_contract_rows']}`",
        f"- runtime_replay_allowed_rows: `{summary['runtime_replay_allowed_rows']}`",
        f"- full375 collateral: `{summary['full375_collateral_gate']}`",
        "",
        "## Release gate states",
        "",
    ]
    for state, count in sorted((summary.get("release_gate_state_counts") or {}).items()):
        lines.append(f"- `{state}`: `{count}`")
    if audit.get("pending_rows"):
        lines.extend(["", "## Pending contract rows", ""])
        for row in audit["pending_rows"]:
            lines.append(f"- `{row['post_id']}` action=`{row['contract_action']}` state=`{row['release_gate_state']}` target=`{row.get('target_title')}`")
    if audit.get("satisfied_no_release_rows"):
        lines.extend(["", "## Satisfied no-release rows", ""])
        for row in audit["satisfied_no_release_rows"]:
            lines.append(f"- `{row['post_id']}` action=`{row['contract_action']}` state=`{row['release_gate_state']}`")
    if audit.get("release_candidate_rows"):
        lines.extend(["", "## Release candidates", ""])
        for row in audit["release_candidate_rows"]:
            lines.append(f"- `{row['post_id']}` action=`{row['contract_action']}` title=`{row.get('public_title')}`")
    if audit.get("violation_rows"):
        lines.extend(["", "## Violations", ""])
        for row in audit["violation_rows"]:
            lines.append(f"- `{row['post_id']}` `{row['violation_code']}` public=`{row.get('public_title')}`")
    lines.extend(["", "## Gate 해석", ""])
    if pending_contract_rows:
        release_sentence = (
            f"현재 projection 기준 pending contract는 `{pending_contract_rows}`건이고 "
            f"release candidate는 `{release_candidate_rows}`건이다."
        )
    else:
        release_sentence = (
            f"현재 projection 기준 pending contract는 `0`건이며 "
            f"release candidate는 `{release_candidate_rows}`건이다."
        )
    lines.append(
        f"{release_sentence} "
        f"no-release 유지 행은 `{satisfied_no_release_rows}`건이며, "
        f"runtime replay allowed는 `{runtime_replay_allowed_rows}`건이다. "
        f"full375 collateral은 `{summary['full375_collateral_gate']}`, goal은 `ACTIVE / NOT_COMPLETE`다."
    )
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit post-verdict promotion-gate plan against current projection release state.")
    parser.add_argument("--contract-plan", required=True, type=Path)
    parser.add_argument("--projection-result", required=True, type=Path)
    parser.add_argument("--audit-id", default="post_verdict_promotion_gate_release_contract_audit")
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-md", required=True, type=Path)
    parser.add_argument("--fail-on-violation", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    audit = build_audit(
        contract_plan=load_json(args.contract_plan),
        projection_rows=_projection_rows(load_json(args.projection_result)),
        audit_id=args.audit_id,
    )
    write_json(args.output_json, audit)
    write_markdown(args.output_md, audit)
    print(json.dumps({"gate": audit["gate"], "summary": audit["summary"]}, ensure_ascii=False, indent=2))
    if args.fail_on_violation and (audit["violation_rows"] or audit["validation_issues"]):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
