from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


C1 = "C1_expected_restore_or_candidate_scrub_contract"
C2 = "C2_canonical_variant_policy_contract"
C3 = "C3_stronger_evidence_or_native_web_hold"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _string(value: Any) -> str:
    return str(value or "").strip()


def _compact(value: Any) -> str:
    return "".join(ch for ch in _string(value).lower() if ch.isalnum())


def _projection_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict) and isinstance(payload.get("rows"), list):
        return [row for row in payload["rows"] if isinstance(row, dict)]
    raise ValueError("projection result must be a JSON array or object with rows list")


def _queue_rows(queue: dict[str, Any]) -> list[dict[str, Any]]:
    rows = queue.get("rows")
    if not isinstance(rows, list):
        raise ValueError("contract queue must contain rows list")
    return [row for row in rows if isinstance(row, dict)]


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
        return bool(ident.get("publish_allowed"))
    trace = ident.get("publish_contract_trace")
    if isinstance(trace, dict) and isinstance(trace.get("publish_allowed"), bool):
        return bool(trace.get("publish_allowed"))
    if isinstance(row.get("publish_allowed"), bool):
        return bool(row.get("publish_allowed"))
    return False


def _public_title(row: dict[str, Any]) -> str:
    return _string(_novel_identity(row).get("official_title") or row.get("actual_title"))


def _public_url(row: dict[str, Any]) -> str:
    return _string(_novel_identity(row).get("heretic_url") or row.get("actual_url"))


def _matches_title(left: Any, right: Any) -> bool:
    return bool(_compact(left) and _compact(left) == _compact(right))


def _matches_url(left: Any, right: Any) -> bool:
    return bool(_string(left) and _string(left) == _string(right))


def _audit_row(queue_row: dict[str, Any], projection_row: dict[str, Any] | None) -> dict[str, Any]:
    post_id = queue_row.get("post_id")
    lane = _string(queue_row.get("contract_batch_lane"))
    if projection_row is None:
        return {
            "post_id": post_id,
            "contract_batch_lane": lane,
            "outcome": "projection_row_missing",
            "violation": True,
            "violation_code": "projection_row_missing",
        }

    public_title = _public_title(projection_row)
    public_url = _public_url(projection_row)
    candidate_title = queue_row.get("current_projection_candidate_title")
    candidate_url = queue_row.get("current_projection_candidate_url")
    canonical_title = queue_row.get("canonical_title") or queue_row.get("expected_or_source_native_title")
    candidate_leaked = _matches_title(public_title, candidate_title) or _matches_url(public_url, candidate_url)
    canonical_published = _matches_title(public_title, canonical_title)
    has_public_identity = bool(public_title or public_url or _publish_allowed(projection_row))
    status = _candidate_status(projection_row)

    outcome = "unclassified_contract_lane"
    violation_code = ""
    violation = False

    if lane == C1:
        if candidate_leaked:
            outcome = "current_candidate_leak_violation"
            violation = True
            violation_code = "current_candidate_leaked_after_expected_verdict"
        elif canonical_published:
            outcome = "expected_title_restored"
        elif not has_public_identity and status == "promotion_blocked":
            outcome = "candidate_scrub_satisfied_expected_restore_pending"
        elif has_public_identity:
            outcome = "unexpected_public_title_after_expected_verdict"
            violation = True
            violation_code = "unexpected_public_title_after_expected_verdict"
        else:
            outcome = "expected_contract_pending_unknown_projection_state"
    elif lane == C2:
        if has_public_identity:
            outcome = "variant_published_before_policy_contract"
            violation = True
            violation_code = "variant_published_before_policy_contract"
        elif status == "promotion_blocked":
            outcome = "variant_policy_pending_no_publish"
        else:
            outcome = "variant_policy_pending_unknown_projection_state"
    elif lane == C3:
        if has_public_identity:
            outcome = "hard_hold_release_violation"
            violation = True
            violation_code = "hard_hold_published_before_stronger_evidence"
        elif status == "promotion_blocked":
            outcome = "hard_hold_preserved"
        else:
            outcome = "hard_hold_pending_unknown_projection_state"

    return {
        "post_id": post_id,
        "contract_batch_lane": lane,
        "canonical_verdict": queue_row.get("canonical_verdict"),
        "canonical_title": canonical_title,
        "current_projection_candidate_title": candidate_title,
        "public_title": public_title or None,
        "public_url": public_url or None,
        "candidate_ledger_status": status or None,
        "publish_allowed": _publish_allowed(projection_row),
        "outcome": outcome,
        "violation": violation,
        "violation_code": violation_code or None,
        "runtime_replay_allowed": False,
    }


def build_audit(
    *,
    contract_queue: dict[str, Any],
    projection_rows: list[dict[str, Any]],
    audit_id: str,
    generated_at: str | None = None,
) -> dict[str, Any]:
    projection_by_post_id = {
        row.get("post_id"): row
        for row in projection_rows
        if isinstance(row.get("post_id"), int)
    }
    rows = [_audit_row(row, projection_by_post_id.get(row.get("post_id"))) for row in _queue_rows(contract_queue)]
    outcome_counts = Counter(_string(row.get("outcome")) for row in rows)
    lane_counts = Counter(_string(row.get("contract_batch_lane")) for row in rows)
    violation_counts = Counter(_string(row.get("violation_code")) for row in rows if row.get("violation"))
    violation_rows = [row for row in rows if row.get("violation")]
    pending_rows = [
        row
        for row in rows
        if not row.get("violation")
        and row.get("outcome") in {
            "candidate_scrub_satisfied_expected_restore_pending",
            "variant_policy_pending_no_publish",
            "expected_contract_pending_unknown_projection_state",
            "variant_policy_pending_unknown_projection_state",
            "hard_hold_pending_unknown_projection_state",
        }
    ]
    satisfied_rows = [
        row
        for row in rows
        if not row.get("violation")
        and row.get("outcome") in {"expected_title_restored", "hard_hold_preserved"}
    ]
    gate = "NO-GO" if violation_rows else "REVIEW-LOCKED"
    return {
        "report_type": "canonical_post_verdict_projection_contract_audit",
        "audit_id": audit_id,
        "generated_at": generated_at or datetime.now().replace(microsecond=0).isoformat(),
        "source_contract_queue": contract_queue.get("queue_id"),
        "gate": gate,
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "summary": {
            "contract_queue_rows": len(rows),
            "projection_rows": len(projection_rows),
            "violation_row_count": len(violation_rows),
            "pending_contract_rows": len(pending_rows),
            "satisfied_contract_rows": len(satisfied_rows),
            "runtime_replay_allowed_rows": 0,
            "lane_counts": dict(lane_counts),
            "outcome_counts": dict(outcome_counts),
            "violation_counts": dict(violation_counts),
            "full375_collateral_gate": "NO-GO",
            "completion_gate": "adjusted full375 collateral GO + full_scan path",
        },
        "violation_rows": violation_rows,
        "pending_rows": pending_rows,
        "satisfied_rows": satisfied_rows,
        "rows": rows,
        "approval_boundary": {
            "projection_contract_audit_is_not_runtime_release": True,
            "runtime_replay_before_contract_tests_forbidden": True,
            "full375_collateral_remains_no_go": True,
        },
    }


def write_markdown(path: Path, audit: dict[str, Any]) -> None:
    summary = audit["summary"]
    lines = [
        f"# {audit.get('audit_id')}",
        "",
        "이 감사는 Loop530 post-verdict contract queue를 current projection 결과에 대조한다. "
        "위반이 없어도 contract test나 stronger evidence가 닫힌 것은 아니므로 runtime replay는 계속 금지한다.",
        "",
        "## 요약",
        "",
        f"- gate: `{audit['gate']}`",
        f"- semantic_quality: `{audit['semantic_quality']}`",
        f"- full_scan_approval: `{str(audit['full_scan_approval']).lower()}`",
        f"- contract_queue_rows: `{summary['contract_queue_rows']}`",
        f"- violation_row_count: `{summary['violation_row_count']}`",
        f"- pending_contract_rows: `{summary['pending_contract_rows']}`",
        f"- satisfied_contract_rows: `{summary['satisfied_contract_rows']}`",
        f"- runtime_replay_allowed_rows: `{summary['runtime_replay_allowed_rows']}`",
        f"- full375 collateral: `{summary['full375_collateral_gate']}`",
        "",
        "## Outcome counts",
        "",
    ]
    for outcome, count in sorted((summary.get("outcome_counts") or {}).items()):
        lines.append(f"- `{outcome}`: `{count}`")
    if audit.get("violation_rows"):
        lines.extend(["", "## Violations", ""])
        for row in audit["violation_rows"]:
            lines.append(f"- `{row['post_id']}` `{row['violation_code']}` public=`{row.get('public_title')}`")
    if audit.get("pending_rows"):
        lines.extend(["", "## Pending", ""])
        for row in audit["pending_rows"]:
            lines.append(f"- `{row['post_id']}` `{row['contract_batch_lane']}` outcome=`{row['outcome']}`")
    lines.extend(["", "## Gate 해석", ""])
    lines.append(
        "현재 projection은 current candidate 누출과 C3 hard-hold release 위반은 보이지 않지만, "
        "C1 expected restore와 C2 variant policy는 별도 contract test 전까지 pending이다. "
        "따라서 full375 collateral은 `NO-GO`, goal은 `ACTIVE / NOT_COMPLETE`다."
    )
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit projection rows against canonical post-verdict contract queue.")
    parser.add_argument("--contract-queue", required=True, type=Path)
    parser.add_argument("--projection-result", required=True, type=Path)
    parser.add_argument("--audit-id", default="canonical_post_verdict_projection_contract_audit")
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-md", required=True, type=Path)
    parser.add_argument("--fail-on-violation", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    audit = build_audit(
        contract_queue=load_json(args.contract_queue),
        projection_rows=_projection_rows(load_json(args.projection_result)),
        audit_id=args.audit_id,
    )
    write_json(args.output_json, audit)
    write_markdown(args.output_md, audit)
    print(json.dumps({"gate": audit["gate"], "summary": audit["summary"]}, ensure_ascii=False, indent=2))
    if args.fail_on_violation and audit["violation_rows"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
