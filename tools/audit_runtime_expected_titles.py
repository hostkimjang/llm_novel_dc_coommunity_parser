from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


PUBLIC_TITLE_KEYS = ("official_title", "official_novel_title", "resolved_title")
PUBLIC_URL_KEYS = ("heretic_url", "official_url", "resolved_url")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, raw_line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        if not raw_line.strip():
            continue
        payload = json.loads(raw_line)
        if not isinstance(payload, dict):
            raise ValueError(f"Expected JSON object at {path}:{line_no}")
        rows.append(payload)
    return rows


def load_rows(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".jsonl":
        return load_jsonl(path)
    payload = load_json(path)
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("results", "rows", "items", "data"):
            rows = payload.get(key)
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, dict)]
    raise ValueError(f"Unsupported result row payload: {path}")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def unwrap_result_row(row: dict[str, Any]) -> dict[str, Any]:
    nested = row.get("result")
    return nested if isinstance(nested, dict) else row


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _post_key(value: Any) -> str:
    return str(value or "").strip()


def _title_key(value: Any) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]+", "", str(value or "")).lower()


def compact_title_match(left: Any, right: Any) -> bool:
    left_key = _title_key(left)
    right_key = _title_key(right)
    return bool(left_key and right_key and left_key == right_key)


def row_analysis(row: dict[str, Any]) -> dict[str, Any]:
    row = unwrap_result_row(row)
    return _dict(row.get("analysis_result"))


def row_identity(row: dict[str, Any]) -> dict[str, Any]:
    analysis = row_analysis(row)
    identity = analysis.get("identity")
    if isinstance(identity, dict):
        return identity
    row = unwrap_result_row(row)
    return _dict(row.get("identity"))


def row_post_id(row: dict[str, Any]) -> str:
    row = unwrap_result_row(row)
    analysis = row_analysis(row)
    identity = row_identity(row)
    for source in (row, analysis, identity):
        if isinstance(source, dict) and source.get("post_id") not in (None, ""):
            return _post_key(source.get("post_id"))
    return ""


def _first_public_value(identity: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    novel = _dict(identity.get("novel_identity"))
    for source in (novel, identity):
        for key in keys:
            value = _text(source.get(key))
            if value:
                return value
    return None


def _promotion_decision(row: dict[str, Any], identity: dict[str, Any]) -> dict[str, Any]:
    analysis = row_analysis(row)
    ledger = _dict(identity.get("candidate_ledger"))
    for source in (identity, analysis, ledger):
        decision = _dict(source.get("promotion_decision"))
        if decision:
            return decision
    return {}


def _publish_ledger_public(row: dict[str, Any], identity: dict[str, Any]) -> dict[str, Any]:
    analysis = row_analysis(row)
    ledger = _dict(identity.get("candidate_ledger"))
    for source in (identity, analysis, ledger):
        publish_ledger = _dict(source.get("publish_ledger"))
        public = _dict(publish_ledger.get("public_publish"))
        if public:
            return public
    return {}


def _actual_title(row: dict[str, Any], identity: dict[str, Any]) -> str | None:
    decision = _promotion_decision(row, identity)
    public = _publish_ledger_public(row, identity)
    ledger = _dict(identity.get("candidate_ledger"))
    for value in (
        _first_public_value(identity, PUBLIC_TITLE_KEYS),
        _text(decision.get("official_title")),
        _text(public.get("official_title")),
        _text(ledger.get("pipeline_official_title")),
    ):
        if value:
            return value
    return None


def _actual_url(row: dict[str, Any], identity: dict[str, Any]) -> str | None:
    decision = _promotion_decision(row, identity)
    public = _publish_ledger_public(row, identity)
    ledger = _dict(identity.get("candidate_ledger"))
    for value in (
        _first_public_value(identity, PUBLIC_URL_KEYS),
        _text(decision.get("official_url")),
        _text(public.get("official_url")),
        _text(ledger.get("pipeline_official_title_url")),
    ):
        if value:
            return value
    return None


def _candidate_ledger_status(row: dict[str, Any], identity: dict[str, Any]) -> str | None:
    analysis = row_analysis(row)
    public = _publish_ledger_public(row, identity)
    for source in (analysis, identity, public):
        value = _text(_dict(source).get("candidate_ledger_status"))
        if value:
            return value
    decision = _promotion_decision(row, identity)
    status = _text(decision.get("status"))
    if status == "publish":
        return "safe_resolved"
    if status == "candidate_only":
        return "promotion_blocked"
    return status


def _bool_from_sources(key: str, row: dict[str, Any], identity: dict[str, Any]) -> bool:
    analysis = row_analysis(row)
    for source in (analysis, identity):
        if isinstance(source, dict) and source.get(key) is True:
            return True
    return False


def _reason_codes(row: dict[str, Any], identity: dict[str, Any]) -> list[str]:
    analysis = row_analysis(row)
    decision = _promotion_decision(row, identity)
    trace = _dict(identity.get("publish_contract_trace"))
    codes: list[str] = []
    for value in (
        decision.get("reason_codes"),
        trace.get("reason_codes"),
        analysis.get("reason_codes"),
        identity.get("reason_codes"),
    ):
        if isinstance(value, list):
            codes.extend(str(item or "").strip() for item in value if str(item or "").strip())
    return list(dict.fromkeys(codes))


def _search_status(row: dict[str, Any], identity: dict[str, Any]) -> tuple[str | None, int | None, int | None]:
    analysis = row_analysis(row)
    row = unwrap_result_row(row)
    for source in (identity.get("search_health"), analysis.get("search_health"), row.get("search_health")):
        payload = _dict(source)
        if payload:
            status = _text(payload.get("status") or payload.get("overall_status"))
            degraded = payload.get("degraded_count", payload.get("search_degraded"))
            unrecovered = payload.get("unrecovered_degraded_count", payload.get("search_unrecovered_degraded"))
            return status, _int_or_none(degraded), _int_or_none(unrecovered)
    catalog = _dict(identity.get("search_evidence_catalog"))
    status = _text(catalog.get("status"))
    return status, _int_or_none(catalog.get("degraded_count")), _int_or_none(catalog.get("unrecovered_degraded_count"))


def _int_or_none(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _runtime_meta(runtime_manifest: dict[str, Any] | None) -> dict[str, Any]:
    payload = runtime_manifest if isinstance(runtime_manifest, dict) else {}
    return {
        "run_id": payload.get("run_id"),
        "completed_count": payload.get("completed_count"),
        "flushed_count": payload.get("flushed_count"),
        "pending_count": payload.get("pending_count"),
        "failed_count": payload.get("failed_count"),
        "large_run_complete": payload.get("large_run_complete"),
        "include_search": payload.get("mcp_health_include_search"),
        "light_mode": payload.get("mcp_health_light_mode"),
        "health_ok": payload.get("mcp_health_ok_count"),
        "health_failure": payload.get("mcp_health_failure_count"),
        "vlm_ocr_ready": payload.get("vlm_ocr_ready"),
        "image_post_count": payload.get("image_post_count"),
    }


def _projection_rows(projection: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    rows = _dict(projection).get("rows") or []
    if not isinstance(rows, list):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        post_id = _post_key(row.get("post_id"))
        if post_id:
            out[post_id] = row
    return out


def expected_pairs(input_manifest: dict[str, Any]) -> list[tuple[str, str]]:
    post_ids = input_manifest.get("post_ids")
    titles = input_manifest.get("expected_titles")
    if not isinstance(post_ids, list) or not isinstance(titles, list):
        raise ValueError("input manifest must contain post_ids and expected_titles arrays")
    if len(post_ids) != len(titles):
        raise ValueError("input manifest post_ids and expected_titles length mismatch")
    return [(_post_key(post_id), str(title or "").strip()) for post_id, title in zip(post_ids, titles)]


def audit_runtime_expected_titles(
    *,
    input_manifest: dict[str, Any],
    result_rows: list[dict[str, Any]],
    runtime_manifest: dict[str, Any] | None = None,
    projection: dict[str, Any] | None = None,
    generated_at: str | None = None,
    report_type: str = "runtime_expected_title_audit",
    inputs: dict[str, str] | None = None,
) -> dict[str, Any]:
    by_post_id = {row_post_id(row): row for row in result_rows if row_post_id(row)}
    projections = _projection_rows(projection)
    rows: list[dict[str, Any]] = []

    for order, (post_id, expected_title) in enumerate(expected_pairs(input_manifest), start=1):
        row = by_post_id.get(post_id)
        projection_row = projections.get(post_id, {})
        if row is None:
            rows.append(
                {
                    "order": order,
                    "post_id": int(post_id) if post_id.isdigit() else post_id,
                    "expected_title": expected_title,
                    "projected_status": projection_row.get("projected_status", "safe_resolved"),
                    "actual_title": None,
                    "actual_url": None,
                    "safe_resolved": False,
                    "is_relevant": None,
                    "candidate_ledger_status": None,
                    "promotion_status": None,
                    "publish_allowed": False,
                    "title_resolution_state": None,
                    "work_resolution": None,
                    "discussion_type": None,
                    "search_status": None,
                    "search_unrecovered_degraded": None,
                    "search_degraded": None,
                    "exact_title_match": False,
                    "compact_title_match": False,
                    "audit_status": "FAIL_MISSING_RUNTIME_ROW",
                    "reason_codes": [],
                }
            )
            continue

        identity = row_identity(row)
        analysis = row_analysis(row)
        decision = _promotion_decision(row, identity)
        actual_title = _actual_title(row, identity)
        actual_url = _actual_url(row, identity)
        candidate_status = _candidate_ledger_status(row, identity)
        publish_allowed = decision.get("publish_allowed") is True
        promotion_status = _text(decision.get("status"))
        safe_resolved = (
            _bool_from_sources("safe_resolved", row, identity)
            or candidate_status == "safe_resolved"
            or (publish_allowed and promotion_status == "publish")
        )
        exact_match = bool(actual_title and actual_title == expected_title)
        compact_match = compact_title_match(actual_title, expected_title)

        if safe_resolved and exact_match:
            audit_status = "PASS_EXACT_SAFE_RESOLVED"
        elif not safe_resolved or candidate_status == "promotion_blocked" or publish_allowed is False:
            audit_status = "FAIL_RUNTIME_PROMOTION_BLOCKED"
        elif compact_match:
            audit_status = "FAIL_VARIANT_COMPACT_MATCH_ONLY"
        else:
            audit_status = "FAIL_SAFE_RESOLVED_TITLE_MISMATCH"

        search_status, search_degraded, search_unrecovered = _search_status(row, identity)
        rows.append(
            {
                "order": order,
                "post_id": int(post_id) if post_id.isdigit() else post_id,
                "expected_title": expected_title,
                "projected_status": projection_row.get("projected_status", "safe_resolved"),
                "actual_title": actual_title,
                "actual_url": actual_url,
                "safe_resolved": safe_resolved,
                "is_relevant": analysis.get("is_relevant", identity.get("is_relevant")),
                "candidate_ledger_status": candidate_status,
                "promotion_status": promotion_status,
                "publish_allowed": publish_allowed,
                "title_resolution_state": identity.get("title_resolution_state"),
                "work_resolution": identity.get("work_resolution"),
                "discussion_type": identity.get("discussion_type"),
                "search_status": search_status,
                "search_unrecovered_degraded": search_unrecovered,
                "search_degraded": search_degraded,
                "exact_title_match": exact_match,
                "compact_title_match": compact_match,
                "audit_status": audit_status,
                "reason_codes": _reason_codes(row, identity),
            }
        )

    status_counts = Counter(str(row["audit_status"]) for row in rows)
    ledger_counts = Counter(str(row.get("candidate_ledger_status")) for row in rows)
    search_counts = Counter(str(row.get("search_status")) for row in rows)
    exact_pass = status_counts.get("PASS_EXACT_SAFE_RESOLVED", 0)
    gate = "GO" if rows and exact_pass == len(rows) else "NO-GO"
    runtime = _runtime_meta(runtime_manifest)
    degraded_total = sum(row.get("search_degraded") or 0 for row in rows)
    unrecovered_total = sum(row.get("search_unrecovered_degraded") or 0 for row in rows)

    return {
        "report_type": report_type,
        "generated_at": generated_at or datetime.now().astimezone().isoformat(timespec="seconds"),
        "gate": gate,
        "gate_reason": (
            "all runtime rows reproduced exact safe_resolved titles"
            if gate == "GO"
            else "runtime rows did not all reproduce expected exact safe_resolved titles"
        ),
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "approval_boundary": "runtime expected-title audit does not imply semantic/full_scan approval",
        "inputs": inputs or {},
        "runtime": runtime,
        "summary": {
            "row_count": len(rows),
            "exact_safe_resolved_pass": exact_pass,
            "exact_safe_resolved_fail": len(rows) - exact_pass,
            "runtime_safe_resolved_count": sum(1 for row in rows if row.get("safe_resolved") is True),
            "runtime_publish_allowed_count": sum(1 for row in rows if row.get("publish_allowed") is True),
            "runtime_promotion_blocked_count": sum(
                1 for row in rows if row.get("candidate_ledger_status") == "promotion_blocked"
            ),
            "status_counts": dict(sorted(status_counts.items())),
            "candidate_ledger_status_counts": dict(sorted(ledger_counts.items())),
            "search_status_counts": dict(sorted(search_counts.items())),
            "search_degraded_total": degraded_total,
            "search_unrecovered_degraded_total": unrecovered_total,
        },
        "rows": rows,
    }


def render_markdown(audit: dict[str, Any]) -> str:
    summary = _dict(audit.get("summary"))
    runtime = _dict(audit.get("runtime"))
    lines = [
        f"# {audit.get('report_type')}",
        "",
        "## 요약",
        "",
        (
            f"runtime expected-title 재현 게이트는 `{audit.get('gate')}`다. "
            f"정확 safe_resolved 재현은 `{summary.get('exact_safe_resolved_pass')}/{summary.get('row_count')}`이며, "
            "이 결과는 runtime 재현성만 다루고 full_scan 승인을 의미하지 않는다."
        ),
        "",
        "## 런타임 상태",
        "",
        f"- run_id: `{runtime.get('run_id')}`",
        (
            "- completed/flushed/pending/failed: "
            f"`{runtime.get('completed_count')}/{runtime.get('flushed_count')}/"
            f"{runtime.get('pending_count')}/{runtime.get('failed_count')}`"
        ),
        f"- large_run_complete: `{runtime.get('large_run_complete')}`",
        (
            "- search health: "
            f"include_search=`{runtime.get('include_search')}`, "
            f"light_mode=`{runtime.get('light_mode')}`, "
            f"ok/failure=`{runtime.get('health_ok')}/{runtime.get('health_failure')}`"
        ),
        f"- VLM/OCR: ready=`{runtime.get('vlm_ocr_ready')}`, image_post_count=`{runtime.get('image_post_count')}`",
        "",
        "## 집계",
        "",
        f"- exact safe_resolved PASS: `{summary.get('exact_safe_resolved_pass')}/{summary.get('row_count')}`",
        f"- runtime safe_resolved: `{summary.get('runtime_safe_resolved_count')}/{summary.get('row_count')}`",
        f"- runtime promotion_blocked: `{summary.get('runtime_promotion_blocked_count')}/{summary.get('row_count')}`",
        f"- audit_status_counts: `{summary.get('status_counts')}`",
        f"- search_status_counts: `{summary.get('search_status_counts')}`",
        (
            "- search degraded/unrecovered total: "
            f"`{summary.get('search_degraded_total')}/{summary.get('search_unrecovered_degraded_total')}`"
        ),
        "",
        "## 행별 결과",
        "",
        "| post_id | audit | expected | actual | ledger | decision | search |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in audit.get("rows") or []:
        lines.append(
            "| "
            f"`{row.get('post_id')}` | "
            f"`{row.get('audit_status')}` | "
            f"`{row.get('expected_title') or ''}` | "
            f"`{row.get('actual_title') or ''}` | "
            f"`{row.get('candidate_ledger_status') or ''}` | "
            f"`{row.get('promotion_status') or ''}` | "
            f"`{row.get('search_status')}` / unrecovered `{row.get('search_unrecovered_degraded')}` |"
        )
    lines.extend(
        [
            "",
            "## Gate",
            "",
            (
                "- projection expected-title: "
                f"`{audit.get('gate')} / {summary.get('exact_safe_resolved_pass')} of {summary.get('row_count')}`"
            ),
            "- search evidence: `REVIEW / degraded 또는 timeout은 별도 검색 복구 P0에서 닫는다`",
            "- full375 collateral: `NO-GO / 별도 전수 collateral GO 전까지 유지`",
            "- completion gate: `NO-GO / full375 collateral GO + full_scan 경로 정의 필요`",
            f"- semantic_quality: `{audit.get('semantic_quality')}`",
            f"- full_scan_approval: `{str(audit.get('full_scan_approval')).lower()}`",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit runtime rows against expected projected safe titles.")
    parser.add_argument("--input-manifest", required=True, type=Path)
    parser.add_argument("--result", required=True, type=Path)
    parser.add_argument("--runtime-manifest", type=Path)
    parser.add_argument("--projection", type=Path)
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-md", required=True, type=Path)
    parser.add_argument("--report-type", default="runtime_expected_title_audit")
    parser.add_argument("--fail-on-no-go", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_manifest = load_json(args.input_manifest)
    runtime_manifest = load_json(args.runtime_manifest) if args.runtime_manifest else None
    projection = load_json(args.projection) if args.projection else None
    audit = audit_runtime_expected_titles(
        input_manifest=input_manifest,
        result_rows=load_rows(args.result),
        runtime_manifest=runtime_manifest,
        projection=projection,
        report_type=args.report_type,
        inputs={
            "input_manifest": str(args.input_manifest),
            "runtime_result": str(args.result),
            "runtime_manifest": str(args.runtime_manifest) if args.runtime_manifest else "",
            "projection": str(args.projection) if args.projection else "",
        },
    )
    write_json(args.output_json, audit)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.write_text(render_markdown(audit), encoding="utf-8")
    if args.fail_on_no_go and audit.get("gate") != "GO":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
