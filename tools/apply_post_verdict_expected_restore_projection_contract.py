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
    build_publish_contract_trace,
    build_publish_ledger,
)


RESTORE = "expected_title_restore_contract_case"
EXPECTED_AUDIT_UPDATE = "expected_audit_update_exclusion_contract_case"
CANONICAL_CLEANUP = "canonical_cleanup_or_url_correction_contract_case"
CANDIDATE_SET_RESTORE = "candidate_set_expected_restore_contract_case"
PUBLISH_CONTRACT_ACTIONS = {RESTORE, EXPECTED_AUDIT_UPDATE, CANONICAL_CLEANUP, CANDIDATE_SET_RESTORE}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _string(value: Any) -> str:
    return str(value or "").strip()


def _compact(value: Any) -> str:
    return "".join(ch for ch in _string(value).lower() if ch.isalnum())


def _rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict) and isinstance(payload.get("rows"), list):
        return [row for row in payload["rows"] if isinstance(row, dict)]
    raise ValueError("projection result must be a JSON array or object with rows list")


def _plan_rows(plan: dict[str, Any]) -> list[dict[str, Any]]:
    rows = plan.get("rows")
    if not isinstance(rows, list):
        raise ValueError("contract plan must contain rows list")
    return [row for row in rows if isinstance(row, dict)]


def _identity(row: dict[str, Any]) -> dict[str, Any]:
    analysis = row.get("analysis_result")
    if isinstance(analysis, dict):
        ident = analysis.get("identity")
        if isinstance(ident, dict):
            return ident
    ident = row.get("identity")
    if isinstance(ident, dict):
        return ident
    if isinstance(analysis, dict):
        analysis["identity"] = {}
        return analysis["identity"]
    row["analysis_result"] = {"identity": {}}
    return row["analysis_result"]["identity"]


def _candidate_title_url(plan_row: dict[str, Any]) -> dict[str, Any]:
    action = _string(plan_row.get("contract_action"))
    title = _string(plan_row.get("current_projection_candidate_title"))
    url = _string(plan_row.get("current_projection_candidate_url"))
    if not title:
        if action == EXPECTED_AUDIT_UPDATE:
            title = _string(plan_row.get("expected_title"))
        elif action == CANONICAL_CLEANUP:
            title = _string(plan_row.get("actual_title"))
    return {
        "official_title": title or None,
        "official_url": url or None,
        "source": f"{action or 'unknown'}_superseded_projection_candidate",
    }


def _append_unique(values: Any, *items: str) -> list[str]:
    out = [str(value) for value in (values or []) if str(value).strip()] if isinstance(values, list) else []
    for item in items:
        if item and item not in out:
            out.append(item)
    return out


def _matching_title(left: Any, right: Any) -> bool:
    return bool(_compact(left) and _compact(left) == _compact(right))


def _contract_source(action: str) -> str:
    return {
        RESTORE: "post_verdict_expected_restore_contract",
        EXPECTED_AUDIT_UPDATE: "post_verdict_expected_audit_update_contract",
        CANONICAL_CLEANUP: "post_verdict_canonical_cleanup_contract",
        CANDIDATE_SET_RESTORE: "candidate_set_expected_restore_contract",
    }.get(action, "post_verdict_projection_publish_contract")


def _contract_metadata_key(action: str) -> str:
    return {
        RESTORE: "post_verdict_expected_restore_contract",
        EXPECTED_AUDIT_UPDATE: "post_verdict_expected_audit_update_contract",
        CANONICAL_CLEANUP: "post_verdict_canonical_cleanup_contract",
        CANDIDATE_SET_RESTORE: "candidate_set_expected_restore_contract",
    }.get(action, "post_verdict_projection_publish_contract")


def _contract_applied_reason(action: str) -> str:
    return {
        RESTORE: "post_verdict_expected_restore_contract_applied",
        EXPECTED_AUDIT_UPDATE: "post_verdict_expected_audit_update_contract_applied",
        CANONICAL_CLEANUP: "post_verdict_canonical_cleanup_contract_applied",
        CANDIDATE_SET_RESTORE: "candidate_set_expected_restore_contract_applied",
    }.get(action, "post_verdict_projection_publish_contract_applied")


def _publish_scope_state(plan_row: dict[str, Any], action: str) -> dict[str, Any]:
    state = plan_row.get("promotion_gate_state") if isinstance(plan_row.get("promotion_gate_state"), dict) else {}
    existing = state.get("scope") if isinstance(state.get("scope"), dict) else {}
    decision = plan_row.get("promotion_decision") if isinstance(plan_row.get("promotion_decision"), dict) else {}
    if not existing and isinstance(decision.get("scope"), dict):
        existing = decision["scope"]
    direct_sources = _append_unique(
        existing.get("direct_bridge_sources") if isinstance(existing, dict) else [],
        _contract_source(action),
    )
    return {
        "scope_kind": "current_work",
        "confidence": _string(existing.get("confidence") if isinstance(existing, dict) else "") or "high",
        "direct_bridge_sources": direct_sources,
        "competing_candidates": existing.get("competing_candidates", []) if isinstance(existing, dict) else [],
        "conflict_reason_codes": [],
    }


def _publish_reason_codes(plan_row: dict[str, Any], action: str) -> list[str]:
    decision = plan_row.get("promotion_decision") if isinstance(plan_row.get("promotion_decision"), dict) else {}
    if action == CANONICAL_CLEANUP:
        return _append_unique(
            [],
            "official_title_exists",
            "row_discusses_work_as_work",
            "scope_current_work",
            "canonical_cleanup_contract_applied",
            "serialized_public_identity_shared_gate_restored",
        )
    return _append_unique(
        decision.get("reason_codes"),
        _contract_applied_reason(action),
        "serialized_public_identity_shared_gate_restored",
    )


def _ensure_candidate_list_has_target(identity: dict[str, Any], target_title: str, target_url: str | None) -> None:
    values = identity.get("title_candidates")
    if not isinstance(values, list):
        values = []
    if not any(_matching_title(item.get("official_title") if isinstance(item, dict) else item, target_title) for item in values):
        values.insert(
            0,
            {
                "official_title": target_title,
                "heretic_url": target_url,
                "confidence": "High",
                "source_tier": "post_verdict_source_native_contract",
                "page_type": "source_native_contract",
                "reference_role": "primary",
            },
        )
    identity["title_candidates"] = values


def _mark_superseded_candidates(identity: dict[str, Any], candidate: dict[str, Any]) -> None:
    candidate_title = candidate.get("official_title")
    if not candidate_title:
        return
    for values in (
        identity.get("title_candidates"),
        identity.get("candidate_preservation_sources"),
        identity.get("mentioned_works"),
        identity.get("secondary_reference_works"),
    ):
        if not isinstance(values, list):
            continue
        for item in values:
            if not isinstance(item, dict):
                continue
            title = item.get("official_title") or item.get("official_novel_title") or item.get("title")
            if not _matching_title(title, candidate_title):
                continue
            item["reference_role"] = "superseded_candidate"
            item["promotion_policy"] = "preserve_without_publication"
            item["blocked_by_candidate_audit"] = True
            item["negative_evidence"] = _append_unique(
                item.get("negative_evidence"),
                "post_verdict_expected_restore_superseded_candidate",
            )


def _apply_publish_contract(row: dict[str, Any], plan_row: dict[str, Any]) -> dict[str, Any]:
    identity = _identity(row)
    ledger = identity.get("candidate_ledger")
    if not isinstance(ledger, dict):
        ledger = {}

    action = _string(plan_row.get("contract_action"))
    target_title = _string(plan_row.get("target_title"))
    target_url = _string(plan_row.get("target_url")) or None
    decision = copy.deepcopy(plan_row.get("promotion_decision") or {})
    scope_state = _publish_scope_state(plan_row, action)
    reason_codes = _publish_reason_codes(plan_row, action)
    decision.update(
        {
            "status": "publish",
            "publish_allowed": True,
            "official_title": target_title,
            "official_url": target_url,
            "candidate_preserved": False,
            "reason_codes": reason_codes,
            "bypassed_gate": False,
            "scope": scope_state,
        }
    )

    for key, value in (
        ("candidate_ledger_status", "safe_resolved"),
        ("title_resolution_allowed", True),
        ("title_resolution_state", "resolved"),
        ("work_resolution", "resolved"),
        ("is_resolved_work_discussion", True),
        ("promotion_blocked", False),
        ("safe_resolved", True),
        ("discussion_type", "review"),
    ):
        identity[key] = value
    identity["promotion_blocked_reasons"] = []
    identity["blocked_official_title"] = None
    identity["blocked_official_title_url"] = None

    novel = identity.get("novel_identity")
    if not isinstance(novel, dict):
        novel = {}
    novel.update({"official_title": target_title, "heretic_url": target_url, "confidence": "High"})
    identity["novel_identity"] = novel
    identity["primary_work"] = {
        "official_title": target_title,
        "heretic_url": target_url,
        "confidence": "High",
        "source_tier": "post_verdict_source_native_contract",
        "page_type": "source_native_contract",
        "reference_role": "primary",
    }
    _ensure_candidate_list_has_target(identity, target_title, target_url)

    superseded = _candidate_title_url(plan_row)
    _mark_superseded_candidates(identity, superseded)
    metadata = {
        "contract_action": action,
        "source_plan": plan_row.get("post_id"),
        "target_title": target_title,
        "target_url": target_url,
        "superseded_projection_candidate": superseded,
        "rationale_ko": plan_row.get("rationale_ko"),
        "evidence_refs": plan_row.get("evidence_refs") or [],
    }
    identity["post_verdict_projection_publish_contract"] = metadata
    identity[_contract_metadata_key(action)] = metadata

    gate_state = {
        "post_id": plan_row.get("post_id"),
        "candidate_title": target_title,
        "candidate_url": target_url or "",
        "source": _contract_source(action),
        "official_title_exists": True,
        "row_discusses_work_as_work": True,
        "title_resolution_state": "resolved",
        "work_resolution": "resolved",
        "discussion_type": "review",
        "scope": scope_state,
    }
    post_gate_context = {
        "title_resolution_allowed": True,
        "title_resolution_state": "resolved",
        "work_resolution": "resolved",
        "candidate_ledger_status": "safe_resolved",
    }
    trace = build_publish_contract_trace(
        decision,
        scope_state=scope_state,
        pre_gate_candidate={
            "official_title": target_title,
            "official_url": target_url,
            "source": _contract_source(action),
        },
        post_gate_context=post_gate_context,
    )
    trace["superseded_projection_candidate"] = superseded
    publish_ledger = build_publish_ledger(trace)
    publish_ledger["superseded_projection_candidate"] = superseded

    identity["promotion_decision"] = decision
    identity["promotion_gate_state"] = gate_state
    identity["publish_contract_trace"] = trace
    identity["publish_ledger"] = publish_ledger

    ledger.update(
        {
            "pipeline_official_title": target_title,
            "candidate_ledger_status": "safe_resolved",
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "is_resolved_work_discussion": True,
            "blocked_official_title": None,
            "blocked_official_title_url": None,
            "promotion_blocked_reasons": [],
            "promotion_decision": decision,
            "promotion_gate_state": gate_state,
            "publish_contract_trace": trace,
            "publish_ledger": publish_ledger,
            "superseded_projection_candidate": superseded,
        }
    )
    identity["candidate_ledger"] = ledger
    row["actual_title"] = target_title
    row["actual_url"] = target_url
    return {
        "post_id": plan_row.get("post_id"),
        "contract_action": action,
        "target_title": target_title,
        "target_url": target_url,
        "superseded_projection_candidate": superseded,
        "status": "applied",
    }


def apply_expected_restore_contract(
    *,
    contract_plan: dict[str, Any],
    projection_payload: Any,
    projection_id: str,
    generated_at: str | None = None,
) -> tuple[Any, dict[str, Any]]:
    output_payload = copy.deepcopy(projection_payload)
    rows = _rows(output_payload)
    by_post_id = {_string(row.get("post_id")): row for row in rows if _string(row.get("post_id"))}
    validation_issues: list[dict[str, Any]] = []
    applied_rows: list[dict[str, Any]] = []
    skipped_counts: Counter[str] = Counter()

    for plan_row in _plan_rows(contract_plan):
        action = _string(plan_row.get("contract_action"))
        if action not in PUBLISH_CONTRACT_ACTIONS:
            skipped_counts[action or "unknown"] += 1
            continue
        post_id = _string(plan_row.get("post_id"))
        target_title = _string(plan_row.get("target_title"))
        decision = plan_row.get("promotion_decision") if isinstance(plan_row.get("promotion_decision"), dict) else {}
        if not target_title:
            validation_issues.append({"post_id": plan_row.get("post_id"), "issue": "missing_target_title"})
            continue
        if action in {RESTORE, EXPECTED_AUDIT_UPDATE} and decision.get("publish_allowed") is not True:
            validation_issues.append({"post_id": plan_row.get("post_id"), "issue": "publish_contract_plan_decision_not_publish", "contract_action": action})
            continue
        projection_row = by_post_id.get(post_id)
        if projection_row is None:
            validation_issues.append({"post_id": plan_row.get("post_id"), "issue": "projection_row_missing"})
            continue
        applied = _apply_publish_contract(projection_row, plan_row)
        identity = _identity(projection_row)
        novel = identity.get("novel_identity") if isinstance(identity.get("novel_identity"), dict) else {}
        if not _matching_title(novel.get("official_title"), target_title):
            validation_issues.append({"post_id": plan_row.get("post_id"), "issue": "target_title_not_serialized_after_apply"})
        applied_rows.append(applied)

    summary = {
        "projection_rows": len(rows),
        "contract_plan_rows": len(_plan_rows(contract_plan)),
        "publish_contract_plan_rows": len(applied_rows) + sum(1 for issue in validation_issues if issue.get("issue") != "projection_row_missing"),
        "applied_publish_contract_rows": len(applied_rows),
        "restore_plan_rows": sum(1 for row in applied_rows if row.get("contract_action") == RESTORE),
        "applied_restore_rows": sum(1 for row in applied_rows if row.get("contract_action") == RESTORE),
        "applied_expected_audit_update_rows": sum(1 for row in applied_rows if row.get("contract_action") == EXPECTED_AUDIT_UPDATE),
        "applied_canonical_cleanup_rows": sum(1 for row in applied_rows if row.get("contract_action") == CANONICAL_CLEANUP),
        "applied_candidate_set_restore_rows": sum(1 for row in applied_rows if row.get("contract_action") == CANDIDATE_SET_RESTORE),
        "validation_issue_count": len(validation_issues),
        "skipped_contract_action_counts": dict(skipped_counts),
        "runtime_replay_allowed_rows": 0,
        "full375_collateral_gate": "NO-GO",
        "completion_gate": "adjusted full375 collateral GO + full_scan path",
    }
    report = {
        "report_type": "post_verdict_projection_publish_contract_application",
        "projection_id": projection_id,
        "generated_at": generated_at or datetime.now().replace(microsecond=0).isoformat(),
        "source_contract_plan": contract_plan.get("plan_id"),
        "gate": "NO-GO" if validation_issues else "REVIEW-LOCKED",
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "summary": summary,
        "validation_issues": validation_issues,
        "applied_rows": applied_rows,
        "approval_boundary": {
            "projection_application_is_not_runtime_replay": True,
            "release_candidate_is_not_full_scan_approval": True,
            "runtime_replay_before_full375_collateral_forbidden": True,
            "full375_collateral_remains_no_go": True,
        },
    }
    return output_payload, report


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    summary = report["summary"]
    lines = [
        f"# {report.get('projection_id')}",
        "",
        "Post-verdict publish-class contract를 current projection row에 적용한 projection-only 산출물이다. "
        "새 runtime replay가 아니며, release candidate가 생겨도 full375 collateral GO 전에는 approval 근거가 아니다.",
        "",
        "## 요약",
        "",
        f"- gate: `{report['gate']}`",
        f"- semantic_quality: `{report['semantic_quality']}`",
        f"- full_scan_approval: `{str(report['full_scan_approval']).lower()}`",
        f"- projection_rows: `{summary['projection_rows']}`",
        f"- applied_publish_contract_rows: `{summary['applied_publish_contract_rows']}`",
        f"- applied_restore_rows: `{summary['applied_restore_rows']}`",
        f"- applied_expected_audit_update_rows: `{summary['applied_expected_audit_update_rows']}`",
        f"- applied_canonical_cleanup_rows: `{summary['applied_canonical_cleanup_rows']}`",
        f"- validation_issue_count: `{summary['validation_issue_count']}`",
        f"- runtime_replay_allowed_rows: `{summary['runtime_replay_allowed_rows']}`",
        f"- full375 collateral: `{summary['full375_collateral_gate']}`",
        "",
        "## 적용 행",
        "",
    ]
    for row in report.get("applied_rows") or []:
        superseded = row.get("superseded_projection_candidate") or {}
        lines.append(
            f"- `{row.get('post_id')}` action=`{row.get('contract_action')}` target=`{row.get('target_title')}` "
            f"superseded=`{superseded.get('official_title')}`"
        )
    lines.extend(["", "## Gate 해석", ""])
    lines.append(
        f"publish-class contract 적용 행 `{summary['applied_publish_contract_rows']}`건은 shared PromotionDecision을 projection identity, "
        "publish_contract_trace, publish_ledger에 동기화했다. 이 결과는 release gate contract를 닫는 "
        "projection 증거이며 runtime replay 또는 full_scan approval이 아니다."
    )
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply expected-restore post-verdict contract to a projection result.")
    parser.add_argument("--contract-plan", required=True, type=Path)
    parser.add_argument("--projection-result", required=True, type=Path)
    parser.add_argument("--projection-id", default="post_verdict_expected_restore_projection_contract")
    parser.add_argument("--output-result", required=True, type=Path)
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-md", required=True, type=Path)
    parser.add_argument("--fail-on-validation-issue", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_payload, report = apply_expected_restore_contract(
        contract_plan=load_json(args.contract_plan),
        projection_payload=load_json(args.projection_result),
        projection_id=args.projection_id,
    )
    write_json(args.output_result, output_payload)
    write_json(args.output_json, report)
    write_markdown(args.output_md, report)
    print(json.dumps({"gate": report["gate"], "summary": report["summary"]}, ensure_ascii=False, indent=2))
    if args.fail_on_validation_issue and report["validation_issues"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
