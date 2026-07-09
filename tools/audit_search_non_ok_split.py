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


def write_jsonl(path: Path, rows: list[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _to_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _row_unrecovered(row: Mapping[str, Any]) -> int:
    return _to_int(row.get("search_unrecovered_degraded") or row.get("unrecovered_degraded"))


def _is_hard(row: Mapping[str, Any]) -> bool:
    status = str(row.get("search_status") or "").strip().upper()
    return status in {"MISSING", "SEARCH_DEGRADED"} or _row_unrecovered(row) > 0


def _is_recovered_observation(row: Mapping[str, Any]) -> bool:
    status = str(row.get("search_status") or "").strip().upper()
    return status == "SEARCH_DEGRADED_RECOVERED" and _row_unrecovered(row) == 0


def _classify_reason(row: Mapping[str, Any]) -> str:
    status = str(row.get("search_status") or "").strip().upper()
    if status == "MISSING":
        return "search_health_missing"
    if status == "SEARCH_DEGRADED":
        return "search_degraded"
    if _row_unrecovered(row) > 0:
        return "unrecovered_degraded"
    if _is_recovered_observation(row):
        return "search_degraded_recovered_observation"
    return "other_non_ok_search_status"


def audit_split(
    split_report: Mapping[str, Any],
    *,
    audit_id: str,
    generated_at: str | None = None,
) -> dict[str, Any]:
    rows = split_report.get("rows")
    if not isinstance(rows, list):
        raise ValueError("split report has no rows list")

    non_ok_rows: list[dict[str, Any]] = []
    hard_rows: list[dict[str, Any]] = []
    recovered_rows: list[dict[str, Any]] = []

    for row in rows:
        if not isinstance(row, Mapping):
            continue
        status = str(row.get("search_status") or "").strip()
        if status == "ok":
            continue
        payload = dict(row)
        payload["search_gate_reason"] = _classify_reason(payload)
        payload["search_replay_required"] = _is_hard(payload)
        payload["recovered_observation"] = _is_recovered_observation(payload)
        non_ok_rows.append(payload)
        if payload["search_replay_required"]:
            hard_rows.append(payload)
        elif payload["recovered_observation"]:
            recovered_rows.append(payload)

    status_counts = Counter(str(row.get("search_status") or "MISSING") for row in non_ok_rows)
    action_counts = Counter(str(row.get("primary_action") or "") for row in non_ok_rows)
    hard_reason_counts = Counter(str(row.get("search_gate_reason") or "") for row in hard_rows)
    gate = "GO" if not hard_rows else "NO-GO"
    return {
        "report_type": "search_non_ok_split_audit",
        "audit_id": audit_id,
        "generated_at": generated_at or datetime.now().replace(microsecond=0).isoformat(),
        "source_split_id": split_report.get("split_id"),
        "source_compare_id": split_report.get("source_compare_id"),
        "gate": gate,
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "summary": {
            "source_rows": len(rows),
            "non_ok_rows": len(non_ok_rows),
            "hard_replay_rows": len(hard_rows),
            "recovered_observation_rows": len(recovered_rows),
            "status_counts": dict(sorted(status_counts.items())),
            "primary_action_counts": dict(sorted(action_counts.items())),
            "hard_reason_counts": dict(sorted(hard_reason_counts.items())),
            "hard_post_ids": [row.get("post_id") for row in hard_rows],
            "recovered_observation_post_ids": [row.get("post_id") for row in recovered_rows],
        },
        "approval_boundary": {
            "current_search_gate_is_not_full375_collateral_go": True,
            "current_search_gate_is_not_full_scan_approval": True,
            "recovered_only_rows_are_observations_not_hard_blockers": True,
            "hard_rows_need_runtime_replay_with_parallel16_dashboard": True,
        },
        "hard_rows": hard_rows,
        "recovered_observation_rows": recovered_rows,
        "rows": non_ok_rows,
    }


def write_markdown(path: Path, report: Mapping[str, Any]) -> None:
    summary = report["summary"]
    lines = [
        f"# {report['audit_id']} current search non-ok gate",
        "",
        "## 결론",
        "",
        f"- gate: `{report['gate']}`",
        f"- source_rows: `{summary['source_rows']}`",
        f"- non_ok_rows: `{summary['non_ok_rows']}`",
        f"- hard_replay_rows: `{summary['hard_replay_rows']}`",
        f"- recovered_observation_rows: `{summary['recovered_observation_rows']}`",
        f"- status_counts: `{json.dumps(summary['status_counts'], ensure_ascii=False, sort_keys=True)}`",
        f"- hard_reason_counts: `{json.dumps(summary['hard_reason_counts'], ensure_ascii=False, sort_keys=True)}`",
        f"- hard_post_ids: `{summary['hard_post_ids']}`",
        "- semantic_quality: `REVIEW-LOCKED`",
        "- full_scan_approval: `false`",
        "",
        "## 해석",
        "",
        "- `SEARCH_DEGRADED_RECOVERED`이고 unrecovered degraded가 `0`인 행은 recovered-only 관측으로 분리한다.",
        "- `MISSING`, `SEARCH_DEGRADED`, unrecovered degraded가 남은 행은 runtime replay 대상이다.",
        "- 이 current search gate는 full375 collateral GO나 full_scan approval이 아니다.",
        "",
        "## Hard replay rows",
        "",
    ]
    for row in report.get("hard_rows") or []:
        lines.append(
            "- `{post_id}` status=`{status}` reason=`{reason}` primary_action=`{action}` "
            "before=`{before}` after=`{after}` post=`{post}`".format(
                post_id=row.get("post_id"),
                status=row.get("search_status"),
                reason=row.get("search_gate_reason"),
                action=row.get("primary_action"),
                before=row.get("before_title"),
                after=row.get("after_title"),
                post=row.get("post_title"),
            )
        )
    lines.extend(["", "## Recovered-only observations", ""])
    for row in report.get("recovered_observation_rows") or []:
        lines.append(
            "- `{post_id}` status=`{status}` primary_action=`{action}` unrecovered=`{unrecovered}`".format(
                post_id=row.get("post_id"),
                status=row.get("search_status"),
                action=row.get("primary_action"),
                unrecovered=_row_unrecovered(row),
            )
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8", newline="\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit non-ok search rows in a collateral split report.")
    parser.add_argument("--split-report", required=True, type=Path)
    parser.add_argument("--audit-id", required=True)
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-md", required=True, type=Path)
    parser.add_argument("--hard-jsonl", type=Path)
    parser.add_argument("--recovered-jsonl", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = audit_split(load_json(args.split_report), audit_id=args.audit_id)
    write_json(args.output_json, report)
    write_markdown(args.output_md, report)
    if args.hard_jsonl:
        write_jsonl(args.hard_jsonl, report["hard_rows"])
    if args.recovered_jsonl:
        write_jsonl(args.recovered_jsonl, report["recovered_observation_rows"])
    print(
        json.dumps(
            {
                "gate": report["gate"],
                "non_ok_rows": report["summary"]["non_ok_rows"],
                "hard_replay_rows": report["summary"]["hard_replay_rows"],
                "recovered_observation_rows": report["summary"]["recovered_observation_rows"],
                "hard_post_ids": report["summary"]["hard_post_ids"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
