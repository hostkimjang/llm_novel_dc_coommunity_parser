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
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from llm_batch.promotion_gate import build_publish_contract_trace, build_publish_ledger  # noqa: E402
from tools.apply_post_verdict_expected_restore_projection_contract import (  # noqa: E402
    CANDIDATE_SET_RESTORE,
    _apply_publish_contract,
)


CANDIDATE_SET_REBUILD_HOLD = "candidate_set_rebuild_required_before_publish"
NO_PUBLISH_INTENT_GUARD = "no_publish_intent_guard_contract_case"
CANDIDATE_SET_ACTIONS = {
    CANDIDATE_SET_RESTORE,
    CANDIDATE_SET_REBUILD_HOLD,
    NO_PUBLISH_INTENT_GUARD,
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _string(value: Any) -> str:
    return str(value or "").strip()


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


def _append_unique(values: Any, *items: str) -> list[str]:
    out = [str(value) for value in (values or []) if str(value).strip()] if isinstance(values, list) else []
    for item in items:
        if item and item not in out:
            out.append(item)
    return out


def _first_title_url(*values: Any) -> dict[str, str | None]:
    for value in values:
        if not isinstance(value, dict):
            continue
        title = _string(
            value.get("official_title")
            or value.get("official_novel_title")
            or value.get("resolved_title")
            or value.get("pipeline_official_title")
            or value.get("blocked_official_title")
            or value.get("title")
        )
        url = _string(
            value.get("heretic_url")
            or value.get("official_url")
            or value.get("resolved_url")
            or value.get("pipeline_url")
            or value.get("blocked_official_title_url")
            or value.get("url")
        )
        if title or url:
            return {"official_title": title or None, "official_url": url or None}
    return {"official_title": None, "official_url": None}


def _candidate_from_projection(row: dict[str, Any]) -> dict[str, Any]:
    identity = _identity(row)
    ledger = identity.get("candidate_ledger") if isinstance(identity.get("candidate_ledger"), dict) else {}
    novel = identity.get("novel_identity") if isinstance(identity.get("novel_identity"), dict) else {}
    trace = identity.get("publish_contract_trace") if isinstance(identity.get("publish_contract_trace"), dict) else {}
    publish_ledger = identity.get("publish_ledger") if isinstance(identity.get("publish_ledger"), dict) else {}
    candidate = _first_title_url(
        novel,
        {
            "official_title": row.get("actual_title"),
            "official_url": row.get("actual_url"),
        },
        identity,
        ledger,
        trace.get("pre_gate_candidate") if isinstance(trace, dict) else {},
        publish_ledger.get("candidate_preservation") if isinstance(publish_ledger, dict) else {},
    )
    if not candidate["official_title"] and not candidate["official_url"]:
        values = identity.get("title_candidates")
        if isinstance(values, list):
            candidate = _first_title_url(*(item for item in values if isinstance(item, dict)))
    candidate["source"] = "current_projection_candidate_or_blocked_identity"
    return candidate


def _enriched_plan_row(plan_row: dict[str, Any], projection_row: dict[str, Any]) -> dict[str, Any]:
    enriched = copy.deepcopy(plan_row)
    candidate = _candidate_from_projection(projection_row)
    if not _string(enriched.get("current_projection_candidate_title")):
        enriched["current_projection_candidate_title"] = candidate.get("official_title")
    if not _string(enriched.get("current_projection_candidate_url")):
        enriched["current_projection_candidate_url"] = candidate.get("official_url")
    return enriched


def _clear_public_identity(row: dict[str, Any], identity: dict[str, Any]) -> None:
    novel = identity.get("novel_identity") if isinstance(identity.get("novel_identity"), dict) else {}
    novel.update({"official_title": None, "heretic_url": None, "confidence": "Hold"})
    identity["novel_identity"] = novel
    for key in (
        "official_title",
        "official_novel_title",
        "resolved_title",
        "heretic_url",
        "official_url",
        "resolved_url",
        "primary_work",
    ):
        identity[key] = None
    row["actual_title"] = None
    row["actual_url"] = None


def _scope_from_plan(plan_row: dict[str, Any], action: str) -> dict[str, Any]:
    state = plan_row.get("promotion_gate_state") if isinstance(plan_row.get("promotion_gate_state"), dict) else {}
    existing = state.get("scope") if isinstance(state.get("scope"), dict) else {}
    if not existing:
        decision = plan_row.get("promotion_decision") if isinstance(plan_row.get("promotion_decision"), dict) else {}
        existing = decision.get("scope") if isinstance(decision.get("scope"), dict) else {}
    scope_kind = "platform_meta_nonwork" if action == NO_PUBLISH_INTENT_GUARD else "unknown"
    conflict = "intent_guard_no_webnovel_promotion" if action == NO_PUBLISH_INTENT_GUARD else "candidate_set_rebuild_required"
    return {
        "scope_kind": _string(existing.get("scope_kind")) or scope_kind,
        "confidence": _string(existing.get("confidence")) or "high",
        "direct_bridge_sources": _append_unique(
            existing.get("direct_bridge_sources"),
            "candidate_set_projection_contract_application",
            action,
        ),
        "competing_candidates": existing.get("competing_candidates", []) if isinstance(existing.get("competing_candidates"), list) else [],
        "conflict_reason_codes": _append_unique(existing.get("conflict_reason_codes"), conflict),
    }


def _hold_reason_codes(plan_row: dict[str, Any], action: str, candidate: dict[str, Any]) -> list[str]:
    decision = plan_row.get("promotion_decision") if isinstance(plan_row.get("promotion_decision"), dict) else {}
    candidate_exists = bool(candidate.get("official_title") or candidate.get("official_url"))
    base = [str(code) for code in (decision.get("reason_codes") or []) if str(code).strip()] if isinstance(decision.get("reason_codes"), list) else []
    if candidate_exists:
        base = [code for code in base if code not in {"no_candidate_title", "hold_without_candidates"}]
    if action == NO_PUBLISH_INTENT_GUARD:
        return _append_unique(
            base,
            "nonwork",
            "scope_platform_meta_nonwork",
            "scope_not_current_work",
            "intent_guard_no_webnovel_promotion",
            "candidate_set_source_native_contract_case",
            "serialized_public_identity_scrubbed" if candidate_exists else "hold_without_candidates",
        )
    return _append_unique(
        base,
        "scope_unknown",
        "scope_not_current_work",
        "candidate_set_rebuild_required",
        "candidate_set_source_native_contract_case",
        "serialized_public_identity_scrubbed" if candidate_exists else "hold_without_candidates",
    )


def _title_resolution_state(action: str, candidate_exists: bool) -> str:
    if action == NO_PUBLISH_INTENT_GUARD:
        return "nonwork"
    if candidate_exists:
        return "unresolved_matchable"
    return "unresolved"


def _work_resolution(action: str) -> str:
    return "nonwork" if action == NO_PUBLISH_INTENT_GUARD else "unresolved"


def _apply_hold_contract(row: dict[str, Any], plan_row: dict[str, Any], action: str) -> dict[str, Any]:
    identity = _identity(row)
    ledger = identity.get("candidate_ledger")
    if not isinstance(ledger, dict):
        ledger = {}
    candidate = _candidate_from_projection(row)
    candidate_title = _string(candidate.get("official_title")) or None
    candidate_url = _string(candidate.get("official_url")) or None
    had_public_identity = bool(
        _string(row.get("actual_title"))
        or _string(row.get("actual_url"))
        or _string((identity.get("novel_identity") or {}).get("official_title") if isinstance(identity.get("novel_identity"), dict) else "")
        or _string((identity.get("novel_identity") or {}).get("heretic_url") if isinstance(identity.get("novel_identity"), dict) else "")
    )
    candidate_exists = bool(candidate_title or candidate_url)
    scope = _scope_from_plan(plan_row, action)
    reason_codes = _hold_reason_codes(plan_row, action, candidate)
    title_state = _title_resolution_state(action, candidate_exists)
    work_state = _work_resolution(action)
    decision = {
        "status": "candidate_only" if candidate_exists else "reject",
        "publish_allowed": False,
        "official_title": None,
        "official_url": None,
        "candidate_preserved": candidate_exists,
        "reason_codes": reason_codes,
        "bypassed_gate": False,
        "scope": scope,
    }
    post_gate_context = {
        "title_resolution_allowed": False,
        "title_resolution_state": title_state,
        "work_resolution": work_state,
        "candidate_ledger_status": "promotion_blocked",
    }
    trace = build_publish_contract_trace(
        decision,
        scope_state=scope,
        pre_gate_candidate={
            "official_title": candidate_title,
            "official_url": candidate_url,
            "source": "current_projection_candidate_preserved_by_candidate_set_contract",
        },
        post_gate_context=post_gate_context,
    )
    decision = trace["gate_decision"]
    publish_ledger = build_publish_ledger(trace)
    gate_state = {
        "post_id": plan_row.get("post_id"),
        "candidate_title": candidate_title or "",
        "candidate_url": candidate_url or "",
        "source": "candidate_set_projection_contract_application",
        "official_title_exists": candidate_exists,
        "row_discusses_work_as_work": False,
        "title_resolution_state": title_state,
        "work_resolution": work_state,
        "discussion_type": "review",
        "scope": scope,
    }

    _clear_public_identity(row, identity)
    identity.update(
        {
            "candidate_ledger_status": "promotion_blocked",
            "title_resolution_allowed": False,
            "title_resolution_state": title_state,
            "work_resolution": work_state,
            "is_resolved_work_discussion": False,
            "promotion_blocked": True,
            "safe_resolved": False,
            "blocked_official_title": candidate_title,
            "blocked_official_title_url": candidate_url,
            "promotion_blocked_reasons": decision["reason_codes"],
            "promotion_decision": decision,
            "promotion_gate_state": gate_state,
            "publish_contract_trace": trace,
            "publish_ledger": publish_ledger,
            "candidate_set_projection_hold_contract": {
                "contract_action": action,
                "source_plan": plan_row.get("post_id"),
                "preserved_candidate": {
                    "official_title": candidate_title,
                    "official_url": candidate_url,
                    "source": candidate.get("source"),
                },
                "rationale_ko": plan_row.get("rationale_ko"),
                "evidence_refs": plan_row.get("evidence_refs") or [],
            },
        }
    )
    if candidate_exists:
        preservation_sources = identity.get("candidate_preservation_sources")
        if not isinstance(preservation_sources, list):
            preservation_sources = []
        preservation_sources.append(
            {
                "official_title": candidate_title,
                "heretic_url": candidate_url,
                "source": "candidate_set_projection_contract_application",
                "promotion_policy": "preserve_without_publication",
            }
        )
        identity["candidate_preservation_sources"] = preservation_sources
    ledger.update(
        {
            "pipeline_official_title": None,
            "candidate_ledger_status": "promotion_blocked",
            "title_resolution_allowed": False,
            "title_resolution_state": title_state,
            "work_resolution": work_state,
            "is_resolved_work_discussion": False,
            "blocked_official_title": candidate_title,
            "blocked_official_title_url": candidate_url,
            "promotion_blocked_reasons": decision["reason_codes"],
            "promotion_decision": decision,
            "promotion_gate_state": gate_state,
            "publish_contract_trace": trace,
            "publish_ledger": publish_ledger,
        }
    )
    identity["candidate_ledger"] = ledger
    return {
        "post_id": plan_row.get("post_id"),
        "contract_action": action,
        "preserved_candidate_title": candidate_title,
        "preserved_candidate_url": candidate_url,
        "status": "scrubbed_public_identity" if had_public_identity else "preserved_no_release",
    }


def apply_candidate_set_projection_contract(
    *,
    contract_plan: dict[str, Any],
    projection_payload: Any,
    projection_id: str,
    generated_at: str | None = None,
) -> tuple[Any, dict[str, Any]]:
    output_payload = copy.deepcopy(projection_payload)
    rows = _rows(output_payload)
    by_post_id = {_string(row.get("post_id")): row for row in rows if _string(row.get("post_id"))}
    applied_rows: list[dict[str, Any]] = []
    validation_issues: list[dict[str, Any]] = []
    skipped_counts: Counter[str] = Counter()

    for plan_row in _plan_rows(contract_plan):
        action = _string(plan_row.get("contract_action"))
        if action not in CANDIDATE_SET_ACTIONS:
            skipped_counts[action or "unknown"] += 1
            continue
        post_id = _string(plan_row.get("post_id"))
        projection_row = by_post_id.get(post_id)
        if projection_row is None:
            validation_issues.append({"post_id": plan_row.get("post_id"), "issue": "projection_row_missing"})
            continue
        enriched_plan = _enriched_plan_row(plan_row, projection_row)
        if action == CANDIDATE_SET_RESTORE:
            if not _string(enriched_plan.get("target_title")):
                validation_issues.append({"post_id": plan_row.get("post_id"), "issue": "missing_target_title"})
                continue
            applied_rows.append(_apply_publish_contract(projection_row, enriched_plan))
        else:
            applied_rows.append(_apply_hold_contract(projection_row, enriched_plan, action))

    status_counts = Counter(_string(row.get("status")) for row in applied_rows)
    action_counts = Counter(_string(row.get("contract_action")) for row in applied_rows)
    summary = {
        "projection_rows": len(rows),
        "contract_plan_rows": len(_plan_rows(contract_plan)),
        "candidate_set_contract_rows": sum(action_counts.values()),
        "applied_restore_rows": action_counts.get(CANDIDATE_SET_RESTORE, 0),
        "applied_hold_rows": action_counts.get(CANDIDATE_SET_REBUILD_HOLD, 0) + action_counts.get(NO_PUBLISH_INTENT_GUARD, 0),
        "applied_candidate_set_rebuild_hold_rows": action_counts.get(CANDIDATE_SET_REBUILD_HOLD, 0),
        "applied_no_publish_intent_guard_rows": action_counts.get(NO_PUBLISH_INTENT_GUARD, 0),
        "scrubbed_public_identity_rows": status_counts.get("scrubbed_public_identity", 0),
        "already_blocked_hold_rows": status_counts.get("preserved_no_release", 0),
        "validation_issue_count": len(validation_issues),
        "skipped_contract_action_counts": dict(skipped_counts),
        "runtime_replay_allowed_rows": 0,
        "requested_parallel_for_future_runtime": 16,
        "dashboard_policy": "WEB_DASHBOARD_REQUIRED_FOR_TEST_RUNS",
        "dashboard_url": "http://127.0.0.1:8080",
        "full375_collateral_gate": "NO-GO",
        "completion_gate": "full375 collateral GO + full_scan path",
    }
    report = {
        "report_type": "candidate_set_projection_contract_application",
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
            "test_runs_require_parallel_16_and_web_dashboard": True,
        },
    }
    return output_payload, report


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    summary = report["summary"]
    lines = [
        f"# {report.get('projection_id')}",
        "",
        "Loop578 candidate-set 계약 계획을 Loop577 full375 projection에 적용한 projection-only 산출물이다. "
        "새 runtime replay가 아니며, release 후보가 생겨도 full375 collateral GO 전에는 approval 근거가 아니다.",
        "",
        "## 요약",
        "",
        f"- gate: `{report['gate']}`",
        f"- semantic_quality: `{report['semantic_quality']}`",
        f"- full_scan_approval: `{str(report['full_scan_approval']).lower()}`",
        f"- projection_rows: `{summary['projection_rows']}`",
        f"- candidate_set_contract_rows: `{summary['candidate_set_contract_rows']}`",
        f"- applied_restore_rows: `{summary['applied_restore_rows']}`",
        f"- applied_hold_rows: `{summary['applied_hold_rows']}`",
        f"- scrubbed_public_identity_rows: `{summary['scrubbed_public_identity_rows']}`",
        f"- already_blocked_hold_rows: `{summary['already_blocked_hold_rows']}`",
        f"- validation_issue_count: `{summary['validation_issue_count']}`",
        f"- runtime_replay_allowed_rows: `{summary['runtime_replay_allowed_rows']}`",
        f"- 다음 runtime/test run 실행 계약: `--parallel {summary['requested_parallel_for_future_runtime']}`, web dashboard `{summary['dashboard_url']}`, `--no-dashboard` 금지",
        f"- full375 collateral: `{summary['full375_collateral_gate']}`",
        f"- 완료 기준: `{summary['completion_gate']}`",
        "",
        "## 적용 행",
        "",
    ]
    for row in report.get("applied_rows") or []:
        if row.get("contract_action") == CANDIDATE_SET_RESTORE:
            lines.append(
                f"- `{row.get('post_id')}` restore target=`{row.get('target_title')}` "
                f"superseded=`{(row.get('superseded_projection_candidate') or {}).get('official_title')}`"
            )
        else:
            lines.append(
                f"- `{row.get('post_id')}` hold action=`{row.get('contract_action')}` "
                f"preserved=`{row.get('preserved_candidate_title')}` status=`{row.get('status')}`"
            )
    lines.extend(["", "## Gate 해석", ""])
    lines.append(
        f"복구 `{summary['applied_restore_rows']}`건은 shared PromotionDecision을 public identity, trace, ledger에 동기화했다. "
        f"hold `{summary['applied_hold_rows']}`건은 serialized public identity를 지우고 후보를 ledger/trace에 보존했다. "
        "이 산출물은 full375 collateral 재평가의 입력일 뿐, runtime 완료나 full_scan approval이 아니다."
    )
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply candidate-set contract plan to a full375 projection result.")
    parser.add_argument("--contract-plan", required=True, type=Path)
    parser.add_argument("--projection-result", required=True, type=Path)
    parser.add_argument("--projection-id", default="candidate_set_projection_contract_application")
    parser.add_argument("--output-result", required=True, type=Path)
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-md", required=True, type=Path)
    parser.add_argument("--fail-on-validation-issue", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_payload, report = apply_candidate_set_projection_contract(
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
