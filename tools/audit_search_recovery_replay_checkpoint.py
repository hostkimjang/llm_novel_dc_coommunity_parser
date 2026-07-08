from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line_no, line in enumerate(handle, 1):
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"Expected object at {path}:{line_no}")
            rows.append(payload)
    return rows


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def _post_id(value: Any) -> int | None:
    try:
        return int(value)
    except Exception:
        return None


def _identity(row: dict[str, Any]) -> dict[str, Any]:
    analysis = row.get("analysis_result") if isinstance(row.get("analysis_result"), dict) else {}
    identity = analysis.get("identity") if isinstance(analysis.get("identity"), dict) else {}
    return identity if isinstance(identity, dict) else {}


def _health(row: dict[str, Any]) -> dict[str, Any]:
    identity = _identity(row)
    payload = identity.get("search_health")
    return payload if isinstance(payload, dict) else {}


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except Exception:
        return 0


def _title(row: dict[str, Any]) -> str | None:
    identity = _identity(row)
    novel = identity.get("novel_identity")
    if isinstance(novel, dict):
        title = str(novel.get("official_title") or "").strip()
        if title:
            return title
    title = str(identity.get("official_title") or "").strip()
    return title or None


def _search_blocker_reason(row: dict[str, Any]) -> str | None:
    status = str(row.get("search_status") or "").strip().upper()
    unrecovered = _int(row.get("unrecovered_degraded"))
    degraded_zero = _int(row.get("degraded_zero"))
    recovered = _int(row.get("degraded_recovered"))
    if status == "MISSING":
        return "search_health_missing"
    if status == "SEARCH_DEGRADED":
        return "search_degraded"
    if unrecovered > 0:
        return "unrecovered_degraded"
    if degraded_zero > 0 and recovered <= 0:
        return "degraded_zero_unrecovered"
    return None


def _recovered_observation(row: dict[str, Any]) -> str | None:
    status = str(row.get("search_status") or "").strip().upper()
    degraded = _int(row.get("degraded"))
    unrecovered = _int(row.get("unrecovered_degraded"))
    if status == "SEARCH_DEGRADED_RECOVERED" and unrecovered <= 0:
        return "search_degraded_recovered"
    if status == "OK" and degraded > 0 and unrecovered <= 0:
        return "ok_with_recovered_degradation_counter"
    return None


def audit_replay(
    *,
    recovered_rows: list[dict[str, Any]],
    input_manifest: dict[str, Any] | None = None,
    recovery_summary: dict[str, Any] | None = None,
    audit_id: str = "search_recovery_replay_audit",
) -> dict[str, Any]:
    input_manifest = input_manifest or {}
    recovery_summary = recovery_summary or {}
    expected_count = _int((input_manifest.get("summary") or {}).get("runtime_input_rows")) or _int(
        input_manifest.get("input_post_count")
    )
    completed_count = len(recovered_rows)
    status_counts: Counter[str] = Counter()
    total_queries = 0
    total_degraded = 0
    total_degraded_zero = 0
    total_degraded_recovered = 0
    total_unrecovered = 0
    rows: list[dict[str, Any]] = []

    for row in recovered_rows:
        health = _health(row)
        status = str(health.get("status") or "MISSING").strip() or "MISSING"
        degraded = _int(health.get("degraded") or health.get("degraded_count"))
        degraded_zero = _int(health.get("degraded_zero") or health.get("degraded_zero_count"))
        recovered = _int(health.get("degraded_recovered") or health.get("degraded_recovered_count"))
        unrecovered = _int(health.get("unrecovered_degraded") or health.get("unrecovered_degraded_count"))
        queries = _int(health.get("queries_issued") or health.get("query_count"))
        status_counts[status] += 1
        total_queries += queries
        total_degraded += degraded
        total_degraded_zero += degraded_zero
        total_degraded_recovered += recovered
        total_unrecovered += unrecovered
        audit_row = {
            "post_id": _post_id(row.get("post_id")),
            "title": _title(row),
            "search_status": status,
            "queries_issued": queries,
            "degraded": degraded,
            "degraded_zero": degraded_zero,
            "degraded_recovered": recovered,
            "unrecovered_degraded": unrecovered,
        }
        blocker_reason = _search_blocker_reason(audit_row)
        recovered_reason = _recovered_observation(audit_row)
        audit_row["search_blocker_reason"] = blocker_reason
        audit_row["recovered_observation"] = recovered_reason
        rows.append(audit_row)

    hard_blocker_rows = [row for row in rows if row.get("search_blocker_reason")]
    recovered_observation_rows = [row for row in rows if row.get("recovered_observation")]
    missing_health_rows = [row for row in rows if row.get("search_status") == "MISSING"]
    blockers: list[str] = []
    if expected_count and completed_count < expected_count:
        blockers.append("partial_replay_not_all_deferred_rows_completed")
    if hard_blocker_rows:
        blockers.append("row_search_hard_blocker_observed")
    if missing_health_rows:
        blockers.append("search_health_missing_observed")
    if total_unrecovered > 0:
        blockers.append("unrecovered_degraded_queries_observed")
    if recovery_summary.get("large_run_complete") is False:
        blockers.append("recovered_subset_not_large_run_complete")

    return {
        "report_type": "search_recovery_replay_audit",
        "audit_id": audit_id,
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "gate": "GO" if not blockers else "NO-GO",
        "summary": {
            "expected_replay_rows": expected_count,
            "completed_rows": completed_count,
            "status_counts": dict(sorted(status_counts.items())),
            "total_queries": total_queries,
            "total_degraded": total_degraded,
            "total_degraded_zero": total_degraded_zero,
            "total_degraded_recovered": total_degraded_recovered,
            "total_unrecovered_degraded": total_unrecovered,
            "hard_blocker_row_count": len(hard_blocker_rows),
            "recovered_observation_row_count": len(recovered_observation_rows),
            "missing_search_health_row_count": len(missing_health_rows),
            "non_ok_row_count": len(hard_blocker_rows),
            "blockers": blockers,
        },
        "recovery_summary": {
            "run_id": recovery_summary.get("run_id"),
            "checkpoint_completed_rows": recovery_summary.get("checkpoint_completed_rows"),
            "checkpoint_failed_rows": recovery_summary.get("checkpoint_failed_rows"),
            "recovered_rows": recovery_summary.get("recovered_rows"),
            "large_run_complete": recovery_summary.get("large_run_complete"),
            "integrity_classification": recovery_summary.get("integrity_classification"),
        },
        "rows": rows,
        "approval_boundary": {
            "partial_replay_is_not_search_recovery": True,
            "search_health_ok_required_before_full375_rerun": True,
            "search_degraded_recovered_is_not_hard_blocker_without_unrecovered": True,
            "dashboard_is_progress_only": True,
        },
    }


def write_markdown(report: dict[str, Any], path: Path) -> None:
    summary = report.get("summary") or {}
    recovery = report.get("recovery_summary") or {}
    blockers = summary.get("blockers") or []
    if report.get("gate") == "GO":
        interpretation = [
            "- 동일 deferred replay가 모두 완료됐고 hard search blocker가 남지 않았다.",
            "- `SEARCH_DEGRADED_RECOVERED` 또는 `status=ok`의 recovered-only degraded 카운터는 별도 관측으로 남기되 hard blocker로 세지 않는다.",
            "- 이 감사 범위에서는 검색 복구 gate를 통과했으므로 full375 재실행 선행 차단을 해제할 수 있다.",
            "- 다만 이 산출물은 full375 collateral GO나 full_scan approval이 아니다.",
        ]
    else:
        interpretation = [
            "- 이 산출물은 검색 복구 증명이 아니다.",
            "- 완료 범위, missing search_health, 또는 unrecovered degraded hard blocker가 남아 있으므로 full375 재실행 차단은 유지한다.",
            "- 검색 인프라 복구 후 blocker 행 또는 동일 deferred 행을 다시 실행해야 한다.",
        ]
    lines = [
        f"# {report.get('audit_id')} 검색 복구 재실행 감사",
        "",
        "## 요약",
        "",
        f"- gate: `{report.get('gate')}`",
        f"- expected_replay_rows: `{summary.get('expected_replay_rows')}`",
        f"- completed_rows: `{summary.get('completed_rows')}`",
        f"- status_counts: `{summary.get('status_counts')}`",
        f"- total_degraded: `{summary.get('total_degraded')}`",
        f"- total_degraded_zero: `{summary.get('total_degraded_zero')}`",
        f"- total_degraded_recovered: `{summary.get('total_degraded_recovered')}`",
        f"- total_unrecovered_degraded: `{summary.get('total_unrecovered_degraded')}`",
        f"- hard_blocker_row_count: `{summary.get('hard_blocker_row_count')}`",
        f"- recovered_observation_row_count: `{summary.get('recovered_observation_row_count')}`",
        f"- missing_search_health_row_count: `{summary.get('missing_search_health_row_count')}`",
        f"- blockers: `{blockers}`",
        f"- recovered_subset: run_id `{recovery.get('run_id')}`, integrity `{recovery.get('integrity_classification')}`, large_run_complete `{recovery.get('large_run_complete')}`",
        "- semantic_quality: `REVIEW-LOCKED`",
        "- full_scan_approval: `false`",
        "",
        "## 해석",
        "",
        *interpretation,
        "",
        "## 행 목록",
        "",
    ]
    for row in report.get("rows") or []:
        lines.append(
            "- `{post_id}` status=`{search_status}` degraded=`{degraded}` recovered=`{recovered}` "
            "unrecovered=`{unrecovered}` blocker=`{blocker}` recovered_observation=`{observation}` title=`{title}`".format(
                post_id=row.get("post_id"),
                search_status=row.get("search_status"),
                degraded=row.get("degraded"),
                recovered=row.get("degraded_recovered"),
                unrecovered=row.get("unrecovered_degraded"),
                blocker=row.get("search_blocker_reason"),
                observation=row.get("recovered_observation"),
                title=row.get("title"),
            )
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8", newline="\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit row-level search health for a recovered search replay subset.")
    parser.add_argument("--recovered-result", required=True, type=Path)
    parser.add_argument("--input-manifest", type=Path)
    parser.add_argument("--recovery-summary", type=Path)
    parser.add_argument("--audit-id", default="search_recovery_replay_audit")
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-md", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = audit_replay(
        recovered_rows=_load_json(args.recovered_result),
        input_manifest=_load_json(args.input_manifest) if args.input_manifest else None,
        recovery_summary=_load_json(args.recovery_summary) if args.recovery_summary else None,
        audit_id=args.audit_id,
    )
    _write_json(args.output_json, report)
    write_markdown(report, args.output_md)
    print(
        f"WROTE {args.output_json} gate={report['gate']} "
        f"completed={report['summary']['completed_rows']} blockers={report['summary']['blockers']}"
    )
    print(f"WROTE {args.output_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
