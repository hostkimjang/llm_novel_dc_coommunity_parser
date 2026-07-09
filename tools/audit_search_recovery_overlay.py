from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def _to_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _post_id(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _held_post_ids(split_report: Mapping[str, Any]) -> list[int]:
    derived = split_report.get("derived_sets")
    if not isinstance(derived, Mapping):
        raise ValueError("split report has no derived_sets")
    raw_values = derived.get("search_degraded_or_recovered_post_ids")
    if not isinstance(raw_values, list):
        raise ValueError("split report has no search_degraded_or_recovered_post_ids")
    out: list[int] = []
    for value in raw_values:
        pid = _post_id(value)
        if pid is not None:
            out.append(pid)
    return out


def _is_hard_blocker(row: Mapping[str, Any]) -> bool:
    if row.get("search_blocker_reason"):
        return True
    if str(row.get("search_status") or "").upper() == "MISSING":
        return True
    return _to_int(row.get("unrecovered_degraded")) > 0


def _source_descriptor(path: Path, audit: Mapping[str, Any]) -> dict[str, Any]:
    summary = audit.get("summary") if isinstance(audit.get("summary"), Mapping) else {}
    recovery = audit.get("recovery_summary") if isinstance(audit.get("recovery_summary"), Mapping) else {}
    return {
        "path": path.as_posix(),
        "audit_id": audit.get("audit_id"),
        "gate": audit.get("gate"),
        "generated_at": audit.get("generated_at"),
        "expected_replay_rows": summary.get("expected_replay_rows"),
        "completed_rows": summary.get("completed_rows"),
        "hard_blocker_row_count": summary.get("hard_blocker_row_count"),
        "total_unrecovered_degraded": summary.get("total_unrecovered_degraded"),
        "run_id": recovery.get("run_id"),
        "large_run_complete": recovery.get("large_run_complete"),
        "integrity_classification": recovery.get("integrity_classification"),
    }


def audit_overlay(
    *,
    split_report: Mapping[str, Any],
    audit_payloads: list[tuple[Path, Mapping[str, Any]]],
    audit_id: str,
    generated_at: str | None = None,
) -> dict[str, Any]:
    held_ids = _held_post_ids(split_report)
    held_set = set(held_ids)
    latest_by_post: dict[int, dict[str, Any]] = {}
    seen_by_post: dict[int, list[dict[str, Any]]] = {pid: [] for pid in held_ids}
    sources: list[dict[str, Any]] = []

    for index, (path, audit) in enumerate(audit_payloads):
        sources.append(_source_descriptor(path, audit))
        for row in audit.get("rows") or []:
            if not isinstance(row, Mapping):
                continue
            pid = _post_id(row.get("post_id"))
            if pid is None or pid not in held_set:
                continue
            source = {
                "overlay_index": index,
                "source_path": path.as_posix(),
                "source_audit_id": audit.get("audit_id"),
                "source_gate": audit.get("gate"),
                "source_run_id": (audit.get("recovery_summary") or {}).get("run_id")
                if isinstance(audit.get("recovery_summary"), Mapping)
                else None,
            }
            row_payload = dict(row)
            row_payload["_overlay_source"] = source
            latest_by_post[pid] = row_payload
            seen_by_post.setdefault(pid, []).append(source)

    final_rows: list[dict[str, Any]] = []
    missing_post_ids: list[int] = []
    status_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    hard_blocker_rows: list[dict[str, Any]] = []
    recovered_observation_rows: list[dict[str, Any]] = []
    total_unrecovered = 0
    total_degraded = 0
    total_recovered = 0

    for pid in held_ids:
        row = latest_by_post.get(pid)
        if row is None:
            missing_post_ids.append(pid)
            continue
        source = row.get("_overlay_source") if isinstance(row.get("_overlay_source"), Mapping) else {}
        status = str(row.get("search_status") or "MISSING")
        unrecovered = _to_int(row.get("unrecovered_degraded"))
        degraded = _to_int(row.get("degraded"))
        recovered = _to_int(row.get("degraded_recovered"))
        total_unrecovered += unrecovered
        total_degraded += degraded
        total_recovered += recovered
        status_counts[status] += 1
        source_counts[str(source.get("source_audit_id") or source.get("source_path") or "unknown")] += 1
        final = {
            "post_id": pid,
            "title": row.get("title"),
            "search_status": status,
            "queries_issued": _to_int(row.get("queries_issued")),
            "degraded": degraded,
            "degraded_recovered": recovered,
            "unrecovered_degraded": unrecovered,
            "search_blocker_reason": row.get("search_blocker_reason"),
            "recovered_observation": row.get("recovered_observation"),
            "source_audit_id": source.get("source_audit_id"),
            "source_path": source.get("source_path"),
            "source_run_id": source.get("source_run_id"),
            "seen_source_count": len(seen_by_post.get(pid) or []),
        }
        if _is_hard_blocker(final):
            hard_blocker_rows.append(final)
        if final.get("recovered_observation"):
            recovered_observation_rows.append(final)
        final_rows.append(final)

    blockers: list[str] = []
    if missing_post_ids:
        blockers.append("held_rows_missing_from_overlay")
    if hard_blocker_rows:
        blockers.append("row_search_hard_blocker_observed")
    if total_unrecovered > 0:
        blockers.append("unrecovered_degraded_queries_observed")

    gate = "GO" if not blockers else "NO-GO"
    return {
        "report_type": "search_recovery_overlay_audit",
        "audit_id": audit_id,
        "generated_at": generated_at or datetime.now().replace(microsecond=0).isoformat(),
        "source_split_id": split_report.get("split_id"),
        "source_compare_id": split_report.get("source_compare_id"),
        "gate": gate,
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "search_recovery_scope": "loop609_search_degraded_or_recovered_held_rows",
        "summary": {
            "held_rows": len(held_ids),
            "covered_rows": len(final_rows),
            "missing_rows": len(missing_post_ids),
            "status_counts": dict(sorted(status_counts.items())),
            "source_counts": dict(sorted(source_counts.items())),
            "hard_blocker_row_count": len(hard_blocker_rows),
            "recovered_observation_row_count": len(recovered_observation_rows),
            "total_degraded": total_degraded,
            "total_degraded_recovered": total_recovered,
            "total_unrecovered_degraded": total_unrecovered,
            "blockers": blockers,
        },
        "approval_boundary": {
            "overlay_search_recovery_is_not_collateral_go": True,
            "overlay_search_recovery_is_not_full_scan_approval": True,
            "search_degraded_recovered_without_unrecovered_is_not_hard_blocker": True,
            "full375_rerun_still_requires_fresh_runtime_contract_and_dashboard": True,
        },
        "sources": sources,
        "missing_post_ids": missing_post_ids,
        "hard_blocker_rows": hard_blocker_rows,
        "rows": final_rows,
    }


def write_markdown(path: Path, report: Mapping[str, Any]) -> None:
    summary = report["summary"]
    interpretation = (
        [
            "- Loop609 search-degraded/recovered 보류 `109`행은 overlay 기준 모두 최신 재실행 증거로 덮였다.",
            "- 최신 row-level hard search blocker와 unrecovered degraded query가 `0`이므로 이 범위의 search recovery gate는 `GO`다.",
            "- 이는 Loop609 raw139의 검색 선결을 닫는 증거이지 full375 collateral GO나 full_scan approval이 아니다.",
        ]
        if report.get("gate") == "GO"
        else [
            "- Loop609 search-degraded/recovered 보류행 중 최신 재실행 증거가 없거나 hard blocker가 남아 있다.",
            "- full375 재실행 차단은 유지한다.",
        ]
    )
    lines = [
        f"# {report['audit_id']} 검색 복구 overlay 감사",
        "",
        "## 결론",
        "",
        f"- gate: `{report['gate']}`",
        f"- held_rows: `{summary['held_rows']}`",
        f"- covered_rows: `{summary['covered_rows']}`",
        f"- missing_rows: `{summary['missing_rows']}`",
        f"- status_counts: `{json.dumps(summary['status_counts'], ensure_ascii=False, sort_keys=True)}`",
        f"- source_counts: `{json.dumps(summary['source_counts'], ensure_ascii=False, sort_keys=True)}`",
        f"- hard_blocker_row_count: `{summary['hard_blocker_row_count']}`",
        f"- recovered_observation_row_count: `{summary['recovered_observation_row_count']}`",
        f"- total_degraded: `{summary['total_degraded']}`",
        f"- total_degraded_recovered: `{summary['total_degraded_recovered']}`",
        f"- total_unrecovered_degraded: `{summary['total_unrecovered_degraded']}`",
        f"- blockers: `{summary['blockers']}`",
        "- semantic_quality: `REVIEW-LOCKED`",
        "- full_scan_approval: `false`",
        "",
        "## 해석",
        "",
        *interpretation,
        "",
        "## 입력 감사",
        "",
    ]
    for source in report.get("sources") or []:
        lines.append(
            "- `{audit_id}` path=`{path}` gate=`{gate}` run=`{run}` completed=`{completed}` "
            "hard_blockers=`{hard}` unrecovered=`{unrecovered}`".format(
                audit_id=source.get("audit_id"),
                path=source.get("path"),
                gate=source.get("gate"),
                run=source.get("run_id"),
                completed=source.get("completed_rows"),
                hard=source.get("hard_blocker_row_count"),
                unrecovered=source.get("total_unrecovered_degraded"),
            )
        )
    lines.extend(["", "## 최신 행 목록", ""])
    for row in report.get("rows") or []:
        lines.append(
        "- `{post_id}` status=`{status}` unrecovered=`{unrecovered}` source=`{source}` title=`{title}`".format(
                post_id=row.get("post_id"),
                status=row.get("search_status"),
                unrecovered=row.get("unrecovered_degraded"),
                source=row.get("source_audit_id"),
                title=row.get("title") if row.get("title") is not None else "null",
            )
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8", newline="\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Overlay multiple search-recovery audits for held post_ids.")
    parser.add_argument("--split-report", required=True, type=Path)
    parser.add_argument("--audit-json", required=True, action="append", type=Path)
    parser.add_argument("--audit-id", required=True)
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-md", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = audit_overlay(
        split_report=load_json(args.split_report),
        audit_payloads=[(path, load_json(path)) for path in args.audit_json],
        audit_id=args.audit_id,
    )
    write_json(args.output_json, report)
    write_markdown(args.output_md, report)
    print(
        json.dumps(
            {
                "gate": report["gate"],
                "held_rows": report["summary"]["held_rows"],
                "covered_rows": report["summary"]["covered_rows"],
                "hard_blocker_row_count": report["summary"]["hard_blocker_row_count"],
                "total_unrecovered_degraded": report["summary"]["total_unrecovered_degraded"],
                "blockers": report["summary"]["blockers"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
