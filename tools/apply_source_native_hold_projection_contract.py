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

from expert_main import _scrub_promotion_blocked_result_contract  # noqa: E402


UNSAFE_PROMOTION_ACTION = "repair_unsafe_promotion"


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


def _reason_code(value: Any) -> str:
    text = re.sub(r"[^0-9A-Za-z_가-힣]+", "_", _string(value)).strip("_").lower()
    return text or "source_native_hold"


def _actions(row: dict[str, Any]) -> set[str]:
    return {_string(value) for value in (row.get("action") or row.get("actions") or []) if _string(value)}


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


def _ledger(identity: dict[str, Any]) -> dict[str, Any]:
    ledger = identity.get("candidate_ledger")
    if not isinstance(ledger, dict):
        ledger = {}
        identity["candidate_ledger"] = ledger
    return ledger


def _public_candidate(identity: dict[str, Any]) -> tuple[str, str]:
    novel = identity.get("novel_identity")
    sources = [identity]
    if isinstance(novel, dict):
        sources.insert(0, novel)
    for source in sources:
        title = _string(
            source.get("official_title")
            or source.get("official_novel_title")
            or source.get("resolved_title")
        )
        url = _string(source.get("heretic_url") or source.get("official_url") or source.get("resolved_url") or source.get("url"))
        if title:
            return title, url
    return "", ""


def _eligible(row: dict[str, Any]) -> bool:
    actions = _actions(row)
    selected_option = _string(row.get("selected_option_id")).upper()
    return bool(
        _string(row.get("review_label")) == "REPROCESS"
        and UNSAFE_PROMOTION_ACTION in actions
        and (selected_option == "HOLD" or not _string(row.get("selected_title")))
    )


def _confidence(row: dict[str, Any]) -> str:
    grade = _string(row.get("evidence_grade")).lower()
    if grade == "strong":
        return "high"
    if grade == "weak":
        return "low"
    return "medium"


def _scope_kind(row: dict[str, Any]) -> str:
    actions = _actions(row)
    verdict = _string(row.get("source_native_verdict")).lower()
    if "nonwork_game_context_publish_block_required" in actions or "nonwork" in verdict:
        return "nonwork"
    if "intent_guard_review" in actions or "generic" in verdict or "context" in verdict:
        return "context_only"
    return "unknown"


def _reason_codes(row: dict[str, Any]) -> list[str]:
    codes = [
        "source_native_hold_projection_contract",
        "source_native_review_hold",
        "serialized_public_identity_scrubbed",
        "scope_not_current_work",
    ]
    verdict = _reason_code(row.get("source_native_verdict"))
    if verdict not in codes:
        codes.append(verdict)
    for action in sorted(_actions(row)):
        code = _reason_code(action)
        if code not in codes:
            codes.append(code)
    return codes


def _append_candidate_preservation(ledger: dict[str, Any], title: str, url: str, row: dict[str, Any]) -> None:
    if not title:
        return
    values = ledger.get("candidate_preservation_sources")
    if not isinstance(values, list):
        values = []
    key = (re.sub(r"[^0-9A-Za-z가-힣]+", "", title).lower(), url)
    for item in values:
        if not isinstance(item, dict):
            continue
        item_key = (
            re.sub(
                r"[^0-9A-Za-z가-힣]+",
                "",
                _string(item.get("official_title") or item.get("title") or item.get("blocked_official_title")),
            ).lower(),
            _string(item.get("heretic_url") or item.get("official_url") or item.get("blocked_official_title_url")),
        )
        if item_key == key:
            item["promotion_policy"] = "hold_without_promotion"
            item["blocked_by_source_native_hold"] = True
            ledger["candidate_preservation_sources"] = values
            return
    payload: dict[str, Any] = {
        "official_title": title,
        "source": "source_native_hold_projection_contract",
        "source_native_verdict": row.get("source_native_verdict"),
        "reference_role": "candidate",
        "promotion_policy": "hold_without_promotion",
        "blocked_by_source_native_hold": True,
    }
    if url:
        payload["heretic_url"] = url
    values.append(payload)
    ledger["candidate_preservation_sources"] = values


def _source_context(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": row.get("title"),
        "content": row.get("content"),
        "comments": row.get("comments"),
        "comment_context_lines": row.get("comment_context_lines"),
        "comment_dialogue_context_lines": row.get("comment_dialogue_context_lines"),
    }


def _apply_hold(row: dict[str, Any], verdict: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    identity = _identity(row)
    ledger = _ledger(identity)
    before_title, before_url = _public_candidate(identity)
    before_status = identity.get("candidate_ledger_status")
    if not before_title and before_status != "safe_resolved":
        return False, {
            "outcome": "skipped_no_public_candidate",
            "before_status": before_status,
            "before_title": before_title or None,
            "before_url": before_url or None,
        }

    reason_codes = _reason_codes(verdict)
    scope = {
        "scope_kind": _scope_kind(verdict),
        "confidence": _confidence(verdict),
        "conflict_reason_codes": reason_codes,
    }
    gate_decision = {
        "status": "candidate_only",
        "publish_allowed": False,
        "official_title": None,
        "official_url": None,
        "candidate_preserved": bool(before_title or before_url),
        "reason_codes": reason_codes,
        "bypassed_gate": False,
        "scope": scope,
    }
    gate_state = {
        "candidate_title": before_title or None,
        "candidate_url": before_url or None,
        "scope": scope,
        "source_native_review": {
            "selected_option_id": verdict.get("selected_option_id"),
            "source_native_verdict": verdict.get("source_native_verdict"),
            "evidence_grade": verdict.get("evidence_grade"),
        },
    }

    _append_candidate_preservation(ledger, before_title, before_url, verdict)
    for key, value in (
        ("candidate_ledger_status", "promotion_blocked"),
        ("title_resolution_allowed", False),
        ("is_resolved_work_discussion", False),
        ("promotion_blocked", True),
        ("safe_resolved", False),
        ("blocked_official_title", before_title or None),
        ("blocked_official_title_url", before_url or None),
        ("promotion_decision", gate_decision),
        ("promotion_gate_state", gate_state),
    ):
        identity[key] = value
        ledger[key] = value
    blocked_reasons = [str(value) for value in identity.get("promotion_blocked_reasons") or [] if str(value).strip()]
    for code in reason_codes:
        if code not in blocked_reasons:
            blocked_reasons.append(code)
    identity["promotion_blocked_reasons"] = blocked_reasons
    ledger["promotion_blocked_reasons"] = blocked_reasons
    identity["candidate_ledger"] = ledger

    sync_payload = {"identity": identity, **_source_context(row)}
    changed = _scrub_promotion_blocked_result_contract(sync_payload, post_title=row.get("title"))

    after_identity = _identity(row)
    after_novel = after_identity.get("novel_identity") if isinstance(after_identity.get("novel_identity"), dict) else {}
    after_title = after_novel.get("official_title") if isinstance(after_novel, dict) else None
    after_url = after_novel.get("heretic_url") if isinstance(after_novel, dict) else None
    after_status = after_identity.get("candidate_ledger_status")
    applied = bool(
        (changed or before_status != after_status)
        and after_status == "promotion_blocked"
        and after_identity.get("title_resolution_allowed") is False
        and not after_title
    )
    return applied, {
        "outcome": "applied_source_native_hold" if applied else "skipped_by_shared_hold_gate",
        "before_status": before_status,
        "before_title": before_title or None,
        "before_url": before_url or None,
        "after_status": after_status,
        "after_title": after_title,
        "after_url": after_url,
        "reason_codes": (
            (after_identity.get("promotion_decision") or {}).get("reason_codes")
            if isinstance(after_identity.get("promotion_decision"), dict)
            else []
        ),
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
        applied, details = _apply_hold(row, verdict)
        outcome = details.get("outcome") or ("applied_source_native_hold" if applied else "skipped_by_shared_hold_gate")
        counters[str(outcome)] += 1
        application_rows.append(
            {
                "post_id": int(post_id) if post_id.isdigit() else post_id,
                "outcome": outcome,
                "selected_option_id": verdict.get("selected_option_id"),
                "source_native_verdict": verdict.get("source_native_verdict"),
                "evidence_grade": verdict.get("evidence_grade"),
                "actions": sorted(_actions(verdict)),
                **details,
            }
        )

    application = {
        "application_id": application_id,
        "report_type": "source_native_hold_projection_contract_application",
        "generated_at": generated_at or datetime.now().replace(microsecond=0).isoformat(),
        "gate": "REVIEW-LOCKED",
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "policy": {
            "source_native_hold_is_not_approval": True,
            "uses_shared_promotion_block_contract": True,
            "runtime_replay": "NOT_RUN",
        },
        "summary": {
            "projection_rows": len(result_rows),
            "verdict_rows": len(verdict_rows),
            "eligible_unsafe_promotion_rows": eligible_count,
            "outcome_counts": dict(counters),
            "applied_hold_rows": counters.get("applied_source_native_hold", 0),
            "skipped_rows": eligible_count - counters.get("applied_source_native_hold", 0),
        },
        "rows": application_rows,
    }
    return result_rows, application


def _write_md(path: Path, application: dict[str, Any]) -> None:
    summary = application["summary"]
    lines = [
        "# Source-native HOLD projection contract 적용",
        "",
        f"- application_id: `{application['application_id']}`",
        f"- gate: `{application['gate']}`",
        f"- semantic_quality: `{application['semantic_quality']}`",
        f"- full_scan_approval: `{str(application['full_scan_approval']).lower()}`",
        f"- projection_rows: `{summary['projection_rows']}`",
        f"- verdict_rows: `{summary['verdict_rows']}`",
        f"- eligible_unsafe_promotion_rows: `{summary['eligible_unsafe_promotion_rows']}`",
        f"- outcome_counts: `{summary['outcome_counts']}`",
        f"- applied_hold_rows: `{summary['applied_hold_rows']}`",
        f"- skipped_rows: `{summary['skipped_rows']}`",
        "",
        "## 적용 행",
        "",
    ]
    for row in application.get("rows", []):
        lines.append(
            f"- `{row.get('post_id')}` `{row.get('outcome')}` "
            f"before=`{row.get('before_title')}` after_status=`{row.get('after_status')}` "
            f"verdict=`{row.get('source_native_verdict')}`"
        )
    lines.extend(
        [
            "",
            "## 승인 경계",
            "",
            "- Source-native HOLD 적용은 projection/static 계약 수렴이며 full_scan approval이 아니다.",
            "- Public title은 제거하고 candidate ledger/trace에 보존한다.",
            "- 완료 기준은 계속 `adjusted full375 collateral GO + full_scan 경로 정의`다.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply source-native HOLD verdicts to projection rows through the shared block contract.")
    parser.add_argument("--projection-result", required=True, type=Path)
    parser.add_argument("--source-native-verdicts", required=True, type=Path)
    parser.add_argument("--output-result", required=True, type=Path)
    parser.add_argument("--output-application", required=True, type=Path)
    parser.add_argument("--output-md", required=True, type=Path)
    parser.add_argument("--application-id", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result_rows, application = apply_contract(
        load_json(args.projection_result),
        load_json(args.source_native_verdicts),
        application_id=args.application_id,
    )
    write_json(args.output_result, result_rows)
    write_json(args.output_application, application)
    _write_md(args.output_md, application)
    print(json.dumps(application["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
