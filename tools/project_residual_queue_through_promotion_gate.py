from __future__ import annotations

import argparse
import json
import re
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
    build_publish_contract_trace,
    build_publish_ledger,
    can_publish_title,
)


OFFICIAL_URL_MARKERS = (
    "novelpia.com/novel",
    "novel.munpia.com",
    "m.munpia.com/novel",
    "series.naver.com/novel",
    "page.kakao.com/content",
    "ridibooks.com/books",
)


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _counter_to_dict(counter: Counter[str]) -> dict[str, int]:
    return {key: counter[key] for key in sorted(counter)}


def _normalize_title(value: Any) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]+", "", str(value or "")).lower()


def _normalize_grade(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"strong", "medium", "weak", "missing"}:
        return text
    return "medium"


def _official_url_from_refs(refs: Any) -> str:
    if not isinstance(refs, list):
        return ""
    for ref in refs:
        text = str(ref or "").strip()
        lower = text.lower()
        if any(marker in lower for marker in OFFICIAL_URL_MARKERS):
            return text
    return ""


def _actions(row: dict[str, Any]) -> set[str]:
    raw = row.get("actions")
    if raw is None:
        raw = row.get("action")
    if isinstance(raw, str):
        values = [raw]
    elif isinstance(raw, list):
        values = raw
    else:
        values = []
    return {str(value or "").strip() for value in values if str(value or "").strip()}


def _row_is_shared_gate_candidate(row: dict[str, Any], action: str) -> bool:
    return action in _actions(row)


def _row_supports_current_work(row: dict[str, Any]) -> bool:
    label = str(row.get("review_label") or "").strip().upper()
    selected_title = str(row.get("selected_title") or "").strip()
    grade = _normalize_grade(row.get("evidence_grade"))
    verdict = str(row.get("source_native_verdict") or "").lower()
    if label != "REPROCESS" or not selected_title:
        return False
    if grade not in {"strong", "medium"}:
        return False
    uncertain_markers = (
        "needs_confirmation",
        "review_required",
        "image_required",
        "not_supported",
        "wrong",
        "generic",
    )
    return not any(marker in verdict for marker in uncertain_markers)


def project_queue(
    queue: dict[str, Any],
    *,
    projection_id: str = "residual_queue_shared_gate_projection",
    action: str = "shared_promotion_gate_wiring_required",
    generated_at: str | None = None,
) -> dict[str, Any]:
    rows = queue.get("rows") or []
    if not isinstance(rows, list):
        raise ValueError("queue.rows must be a list")

    projected_rows: list[dict[str, Any]] = []
    validation_issues: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    label_counts: Counter[str] = Counter()
    bucket_counts: Counter[str] = Counter()
    publish_allowed_count = 0
    exact_title_match_count = 0

    for row in rows:
        if not isinstance(row, dict):
            validation_issues.append({"code": "non_object_queue_row"})
            continue
        if not _row_is_shared_gate_candidate(row, action):
            continue

        selected_title = str(row.get("selected_title") or "").strip()
        selected_url = _official_url_from_refs(row.get("evidence_refs"))
        supports_current_work = _row_supports_current_work(row)
        action_set = _actions(row)
        candidate_rebuild_required = "candidate_set_rebuild_required" in action_set
        if not selected_title and not candidate_rebuild_required:
            validation_issues.append(
                {"code": "shared_gate_row_missing_selected_title", "post_id": row.get("post_id")}
            )

        grade = _normalize_grade(row.get("evidence_grade"))
        scope_kind = "current_work" if supports_current_work else "context_only"
        conflict_reason_codes = [] if supports_current_work else ["source_native_support_not_sufficient"]
        if candidate_rebuild_required:
            conflict_reason_codes.append("candidate_set_rebuild_required")
        state = GroundingState(
            post_id=row.get("post_id"),
            candidate_title=selected_title,
            candidate_url=selected_url,
            source="source_native_residual_queue_shared_gate_projection",
            official_title_exists=bool(selected_title),
            row_discusses_work_as_work=supports_current_work,
            title_resolution_state="resolved" if supports_current_work else "context_only",
            work_resolution="resolved" if supports_current_work else "unresolved",
            discussion_type="review",
            scope=ScopeState(
                scope_kind=scope_kind,
                confidence="high" if grade == "strong" else "medium",
                direct_bridge_sources=["source_native_review", action],
                competing_candidates=[],
                conflict_reason_codes=conflict_reason_codes,
            ),
        )
        evidence = [
            EvidenceRecord(
                kind="source_native_review",
                strength=grade,
                source_path_or_snippet=str(row.get("rationale_ko") or ""),
                supports_publish=supports_current_work,
                reason_code="source_native_review_current_work"
                if supports_current_work
                else "candidate_set_rebuild_required"
                if candidate_rebuild_required
                else "source_native_support_not_sufficient",
            )
        ]
        if selected_url:
            evidence.append(
                EvidenceRecord(
                    kind="official_detail_url",
                    strength="strong",
                    source_path_or_snippet=selected_url,
                    supports_publish=False,
                    reason_code="official_detail_url",
                )
            )
        decision = can_publish_title(state, evidence)
        decision_payload = decision.to_dict()
        if isinstance(state.scope, ScopeState):
            decision_payload["scope"] = state.scope.to_dict()
        projected_status = "safe_resolved" if decision.publish_allowed else "promotion_blocked"
        projected_title = decision.official_title
        projected_url = decision.official_url
        post_gate_context = {
            "title_resolution_allowed": decision.publish_allowed,
            "title_resolution_state": "resolved" if decision.publish_allowed else state.title_resolution_state,
            "work_resolution": "resolved" if decision.publish_allowed else state.work_resolution,
            "candidate_ledger_status": projected_status,
        }
        trace = build_publish_contract_trace(
            decision_payload,
            scope_state=state.scope,
            pre_gate_candidate={
                "official_title": selected_title or None,
                "official_url": selected_url or None,
                "source": "source_native_residual_queue_shared_gate_projection",
            },
            post_gate_context=post_gate_context,
        )
        decision_payload = trace["gate_decision"]
        publish_ledger = build_publish_ledger(trace)
        matches_title = (
            bool(selected_title)
            and bool(projected_title)
            and _normalize_title(selected_title) == _normalize_title(projected_title)
        )
        if decision.publish_allowed:
            publish_allowed_count += 1
        if matches_title:
            exact_title_match_count += 1

        status_counts[projected_status] += 1
        label_counts[str(row.get("review_label") or "").strip().upper()] += 1
        bucket_counts[str(row.get("triage_bucket") or "unknown")] += 1
        projected_rows.append(
            {
                "post_id": row.get("post_id"),
                "triage_bucket": row.get("triage_bucket"),
                "selected_title": selected_title or None,
                "selected_url": selected_url or None,
                "selected_option_id": row.get("selected_option_id"),
                "source_native_verdict": row.get("source_native_verdict"),
                "source_review_id": row.get("source_review_id"),
                "evidence_grade": row.get("evidence_grade"),
                "source_actions": sorted(action_set),
                "projected_status": projected_status,
                "projected_title": projected_title,
                "projected_url": projected_url,
                "matches_source_native_title": matches_title,
                "promotion_decision": decision_payload,
                "publish_contract_trace": trace,
                "publish_ledger": publish_ledger,
                "projected_reasons": decision_payload.get("reason_codes") or [],
                "promotion_gate_state": state.to_dict(),
                "promotion_gate_evidence": [record.to_dict() for record in evidence],
                "rationale_ko": row.get("rationale_ko"),
                "evidence_refs": row.get("evidence_refs") or [],
            }
        )

    return {
        "report_type": "residual_queue_shared_promotion_gate_projection",
        "projection_id": projection_id,
        "generated_at": generated_at or datetime.now().replace(microsecond=0).isoformat(),
        "source_queue_id": queue.get("queue_id"),
        "source_review_id": queue.get("source_review_id"),
        "source_gate": queue.get("gate"),
        "action_filter": action,
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "gate": "NO-GO" if validation_issues else "REVIEW-LOCKED",
        "input_rows": len(projected_rows),
        "summary": {
            "source_queue_rows": len(rows),
            "projected_rows": len(projected_rows),
            "projected_status_counts": _counter_to_dict(status_counts),
            "source_label_counts": _counter_to_dict(label_counts),
            "source_bucket_counts": _counter_to_dict(bucket_counts),
            "publish_allowed_rows": publish_allowed_count,
            "matches_source_native_title_rows": exact_title_match_count,
            "validation_issue_count": len(validation_issues),
        },
        "validation_issues": validation_issues,
        "rows": projected_rows,
        "approval_boundary": {
            "projection_is_not_runtime_replay": True,
            "projection_is_not_full375_approval": True,
            "requires_runtime_replay_and_full375_collateral_go": True,
        },
    }


def write_markdown(report: dict[str, Any], path: Path) -> None:
    summary = report["summary"]
    lines = [
        f"# {report.get('projection_id')}",
        "",
        "## 요약",
        "",
        f"- source_queue_id: `{report.get('source_queue_id')}`",
        f"- source_review_id: `{report.get('source_review_id')}`",
        f"- gate: `{report.get('gate')}`",
        f"- action_filter: `{report.get('action_filter')}`",
        f"- projected_rows: `{summary.get('projected_rows')}`",
        f"- projected_status_counts: `{summary.get('projected_status_counts')}`",
        f"- publish_allowed_rows: `{summary.get('publish_allowed_rows')}`",
        f"- matches_source_native_title_rows: `{summary.get('matches_source_native_title_rows')}`",
        f"- validation_issue_count: `{summary.get('validation_issue_count')}`",
        "- semantic_quality: `REVIEW-LOCKED`",
        "- full_scan_approval: `false`",
        "",
        "## 경계",
        "",
        "- 이 projection은 source-native residual queue를 shared `can_publish_title` 계약으로 투영한 산출물이다.",
        "- Runtime replay, full375 collateral GO, full_scan approval을 대체하지 않는다.",
        "- `safe_resolved` projection 행은 후속 runtime replay 후보이며, replay 후 publication contract와 collateral gate를 다시 봐야 한다.",
        "",
        "## 샘플",
        "",
    ]
    for row in (report.get("rows") or [])[:12]:
        lines.append(
            "- "
            f"`{row.get('post_id')}` "
            f"`{row.get('projected_status')}` "
            f"`{row.get('selected_title')}` -> `{row.get('projected_title')}`"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Project residual queue source-native rows through the shared promotion gate."
    )
    parser.add_argument("--queue", required=True, type=Path)
    parser.add_argument("--projection-id", default="residual_queue_shared_gate_projection")
    parser.add_argument("--action", default="shared_promotion_gate_wiring_required")
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-md", required=True, type=Path)
    parser.add_argument("--fail-on-validation-issue", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = project_queue(
        load_json(args.queue),
        projection_id=args.projection_id,
        action=args.action,
    )
    write_json(args.output_json, report)
    write_markdown(report, args.output_md)
    if args.fail_on_validation_issue and report["summary"]["validation_issue_count"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
