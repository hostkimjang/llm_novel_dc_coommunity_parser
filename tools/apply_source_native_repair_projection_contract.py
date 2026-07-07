from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from expert_main import (  # noqa: E402
    _apply_projection_followup_promotion_seed,
    _canonical_official_detail_url,
    _sync_final_publication_ledger_contract,
)


SAFE_LOSS_ACTION = "repair_safe_loss_restore_supported_title"
SHARED_GATE_ACTION = "shared_promotion_gate_wiring_required"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict) and isinstance(payload.get("rows"), list):
        return [row for row in payload["rows"] if isinstance(row, dict)]
    raise ValueError("projection/result payload must be a JSON array or object with rows")


def _verdict_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict) and isinstance(payload.get("rows"), list):
        return [row for row in payload["rows"] if isinstance(row, dict)]
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    raise ValueError("verdict payload must be a JSON array or object with rows")


def _post_id(value: Any) -> str:
    return str(value or "").strip()


def _string(value: Any) -> str:
    return str(value or "").strip()


def _compact(value: Any) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]+", "", _string(value)).lower()


def _same_title(left: Any, right: Any) -> bool:
    left_key = _compact(left)
    right_key = _compact(right)
    return bool(left_key and left_key == right_key)


def _identity(row: dict[str, Any]) -> dict[str, Any]:
    analysis = row.get("analysis_result")
    if isinstance(analysis, dict) and isinstance(analysis.get("identity"), dict):
        return analysis["identity"]
    if isinstance(row.get("identity"), dict):
        return row["identity"]
    if not isinstance(analysis, dict):
        analysis = {}
        row["analysis_result"] = analysis
    analysis["identity"] = {}
    return analysis["identity"]


def _official_ref_from_evidence_refs(row: dict[str, Any]) -> str:
    for ref in row.get("evidence_refs") or []:
        url = _canonical_official_detail_url(ref)
        if url:
            return url
    return ""


def _candidate_url(row: dict[str, Any]) -> str:
    return _canonical_official_detail_url(row.get("selected_url")) or _official_ref_from_evidence_refs(row)


def _actions(row: dict[str, Any]) -> set[str]:
    return {_string(value) for value in (row.get("action") or row.get("actions") or []) if _string(value)}


def _eligible(row: dict[str, Any]) -> bool:
    actions = _actions(row)
    return bool(
        _string(row.get("review_label")) == "REPROCESS"
        and SAFE_LOSS_ACTION in actions
        and SHARED_GATE_ACTION in actions
        and _string(row.get("selected_title"))
    )


def _build_seed(row: dict[str, Any]) -> dict[str, Any] | None:
    title = _string(row.get("selected_title"))
    url = _candidate_url(row)
    if not title or not url:
        return None
    return {
        "approval_state": "source_native_projection_contract_not_approval",
        "projected_status": "safe_resolved",
        "matches_source_native_title": True,
        "actions": [SAFE_LOSS_ACTION, SHARED_GATE_ACTION],
        "projected_title": title,
        "projected_url": url,
        "selected_title": title,
        "source_native_verdict": row.get("source_native_verdict"),
        "promotion_decision": {
            "status": "publish",
            "publish_allowed": True,
            "official_title": title,
            "official_url": url,
            "reason_codes": [
                "official_title_exists",
                "row_discusses_work_as_work",
                "scope_current_work",
            ],
            "scope": {
                "scope_kind": "current_work",
                "confidence": "high" if _string(row.get("evidence_grade")).lower() == "strong" else "medium",
                "direct_bridge_sources": ["source_native_review_current_work"],
            },
        },
        "promotion_gate_state": {
            "candidate_title": title,
            "candidate_url": url,
            "official_title_exists": True,
            "row_discusses_work_as_work": True,
            "scope": {
                "scope_kind": "current_work",
                "confidence": "high" if _string(row.get("evidence_grade")).lower() == "strong" else "medium",
                "direct_bridge_sources": ["source_native_review_current_work"],
            },
        },
        "promotion_gate_evidence": [
            {
                "kind": "source_native_review",
                "strength": _string(row.get("evidence_grade")).lower() or "medium",
                "source_path_or_snippet": _string(row.get("rationale_ko")),
                "supports_publish": True,
                "reason_code": "source_native_review_current_work",
            }
        ],
    }


def _source_context(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": row.get("title"),
        "content": row.get("content"),
        "comments": row.get("comments"),
        "comment_context_lines": row.get("comment_context_lines"),
        "comment_dialogue_context_lines": row.get("comment_dialogue_context_lines"),
    }


def apply_contract(
    projection_payload: Any,
    verdict_payload: Any,
    *,
    application_id: str,
    generated_at: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    result_rows = copy.deepcopy(_rows(projection_payload))
    verdict_rows = _verdict_rows(verdict_payload)
    verdict_by_id = {_post_id(row.get("post_id")): row for row in verdict_rows if _post_id(row.get("post_id"))}

    application_rows: list[dict[str, Any]] = []
    counters: Counter[str] = Counter()
    eligible_count = 0
    for row in result_rows:
        post_id = _post_id(row.get("post_id"))
        verdict = verdict_by_id.get(post_id)
        if not isinstance(verdict, dict) or not _eligible(verdict):
            continue
        eligible_count += 1
        identity = _identity(row)
        before_status = identity.get("candidate_ledger_status")
        before_title = (identity.get("novel_identity") or {}).get("official_title") if isinstance(identity.get("novel_identity"), dict) else None
        seed = _build_seed(verdict)
        if seed is None:
            outcome = "skipped_missing_official_detail_url"
            counters[outcome] += 1
            application_rows.append(
                {
                    "post_id": int(post_id) if post_id.isdigit() else post_id,
                    "outcome": outcome,
                    "selected_title": verdict.get("selected_title"),
                    "selected_url": verdict.get("selected_url"),
                    "before_status": before_status,
                    "before_title": before_title,
                }
            )
            continue

        changed = _apply_projection_followup_promotion_seed(identity_container := {"identity": identity}, seed)
        if changed:
            sync_payload = dict(identity_container)
            sync_payload.update(_source_context(row))
            _sync_final_publication_ledger_contract(sync_payload, post_title=row.get("title"))

        after_identity = _identity(row)
        novel = after_identity.get("novel_identity") if isinstance(after_identity.get("novel_identity"), dict) else {}
        after_title = novel.get("official_title")
        after_url = novel.get("heretic_url")
        after_status = after_identity.get("candidate_ledger_status")
        if changed and after_status == "safe_resolved" and _same_title(after_title, verdict.get("selected_title")):
            outcome = "applied_shared_gate_publish"
        elif changed:
            outcome = "post_sync_held"
        else:
            outcome = "skipped_by_shared_gate"
        counters[outcome] += 1
        application_rows.append(
            {
                "post_id": int(post_id) if post_id.isdigit() else post_id,
                "outcome": outcome,
                "selected_title": verdict.get("selected_title"),
                "selected_url": seed.get("projected_url"),
                "before_status": before_status,
                "before_title": before_title,
                "after_status": after_status,
                "after_title": after_title,
                "after_url": after_url,
                "source_native_verdict": verdict.get("source_native_verdict"),
                "evidence_grade": verdict.get("evidence_grade"),
                "actions": sorted(_actions(verdict)),
                "gate_reason_codes": (
                    (after_identity.get("promotion_decision") or {}).get("reason_codes")
                    if isinstance(after_identity.get("promotion_decision"), dict)
                    else []
                ),
            }
        )

    application = {
        "application_id": application_id,
        "report_type": "source_native_repair_projection_contract_application",
        "generated_at": generated_at or datetime.now().replace(microsecond=0).isoformat(),
        "gate": "REVIEW-LOCKED",
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "policy": {
            "source_native_seed_is_not_approval": True,
            "uses_shared_promotion_seed_helper": True,
            "uses_final_publication_ledger_sync": True,
            "runtime_replay": "NOT_RUN",
        },
        "summary": {
            "projection_rows": len(result_rows),
            "verdict_rows": len(verdict_rows),
            "eligible_safe_loss_rows": eligible_count,
            "outcome_counts": dict(counters),
            "applied_publish_rows": counters.get("applied_shared_gate_publish", 0),
            "post_sync_held_rows": counters.get("post_sync_held", 0),
            "skipped_rows": counters.get("skipped_missing_official_detail_url", 0)
            + counters.get("skipped_by_shared_gate", 0),
        },
        "rows": application_rows,
    }
    return result_rows, application


def write_markdown(path: Path, application: dict[str, Any], *, result_path: Path) -> None:
    summary = application["summary"]
    lines = [
        f"# {application['application_id']} source-native 수리 projection",
        "",
        f"- 결과 파일: `{result_path.as_posix()}`",
        f"- gate: `{application['gate']}`",
        f"- semantic_quality: `{application['semantic_quality']}`",
        f"- full_scan_approval: `{str(application['full_scan_approval']).lower()}`",
        f"- projection 행 수: `{summary['projection_rows']}`",
        f"- eligible safe-loss 행 수: `{summary['eligible_safe_loss_rows']}`",
        f"- publish 적용 행 수: `{summary['applied_publish_rows']}`",
        f"- post-sync hold 행 수: `{summary['post_sync_held_rows']}`",
        f"- skip 행 수: `{summary['skipped_rows']}`",
        "",
        "## 결과 집계",
        "",
    ]
    for key, value in sorted((summary.get("outcome_counts") or {}).items()):
        lines.append(f"- `{key}`: `{value}`")
    if not summary.get("outcome_counts"):
        lines.append("- 없음")
    lines.extend(["", "## Gate 해석", ""])
    lines.append(
        "이 적용은 source-native verdict를 shared promotion seed helper와 final publication ledger sync에 통과시킨 projection-only 수렴이다. "
        "runtime replay, semantic approval, full_scan approval이 아니다."
    )
    lines.append("")
    lines.append("## 행 요약")
    lines.append("")
    for row in application["rows"][:80]:
        lines.append(
            "- "
            f"`{row['post_id']}` `{row['outcome']}` "
            f"`{row.get('before_title')}` -> `{row.get('after_title')}` "
            f"({row.get('before_status')} -> {row.get('after_status')})"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply source-native safe-loss repair verdicts through shared projection seed contracts.")
    parser.add_argument("--projection-result", required=True, type=Path)
    parser.add_argument("--source-native-verdicts", required=True, type=Path)
    parser.add_argument("--output-result", required=True, type=Path)
    parser.add_argument("--output-application", required=True, type=Path)
    parser.add_argument("--output-md", required=True, type=Path)
    parser.add_argument("--application-id", default="source_native_repair_projection_contract")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result_rows, application = apply_contract(
        load_json(args.projection_result),
        load_json(args.source_native_verdicts),
        application_id=args.application_id,
    )
    write_json(args.output_result, result_rows)
    write_json(args.output_application, application)
    write_markdown(args.output_md, application, result_path=args.output_result)
    print(json.dumps({"gate": application["gate"], "summary": application["summary"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
