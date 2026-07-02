from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _identity(row: dict[str, Any], key: str) -> dict[str, Any]:
    value = row.get(key)
    return value if isinstance(value, dict) else {}


def _title(identity: dict[str, Any]) -> str | None:
    value = identity.get("official_title")
    return str(value).strip() if value else None


def _url(identity: dict[str, Any]) -> str | None:
    value = identity.get("heretic_url")
    return str(value).strip() if value else None


def _status(identity: dict[str, Any]) -> str | None:
    value = identity.get("candidate_ledger_status")
    return str(value).strip() if value else None


def _state(identity: dict[str, Any]) -> str | None:
    value = identity.get("title_resolution_state")
    return str(value).strip() if value else None


def _bucket_for(row: dict[str, Any]) -> tuple[str, str]:
    if not bool(row.get("is_regression")):
        return "P2", "non_regression_change"
    status = str(row.get("status") or "").strip()
    before = _identity(row, "before_identity")
    after = _identity(row, "after_identity")
    before_status = _status(before)
    after_status = _status(after)
    if status == "resolved_to_different_title":
        return "P0", "wrong_work_title_flip"
    if status == "resolved_to_null":
        return "P0", "safe_loss_resolved_to_null"
    if status == "null_to_resolved":
        if before_status in {"promotion_blocked", "hold_unresolved"} and after_status == "safe_resolved":
            return "P0", "unsafe_promotion_from_hold"
        return "P1", "new_resolution_promotion"
    return "P1", "other_collateral_regression"


def triage_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        before = _identity(row, "before_identity")
        after = _identity(row, "after_identity")
        priority, bucket = _bucket_for(row)
        out.append(
            {
                "post_id": row.get("post_id"),
                "status": row.get("status"),
                "is_regression": bool(row.get("is_regression")),
                "priority": priority,
                "triage_bucket": bucket,
                "before_title": _title(before),
                "after_title": _title(after),
                "before_url": _url(before),
                "after_url": _url(after),
                "before_candidate_ledger_status": _status(before),
                "after_candidate_ledger_status": _status(after),
                "before_title_resolution_state": _state(before),
                "after_title_resolution_state": _state(after),
                "before_candidate_count": before.get("candidate_count") or 0,
                "after_candidate_count": after.get("candidate_count") or 0,
            }
        )
    return out


def build_report(compare: dict[str, Any], *, sample_limit: int = 12) -> dict[str, Any]:
    rows = [row for row in compare.get("rows", []) if isinstance(row, dict)]
    triaged = triage_rows(rows)
    regression_rows = [row for row in triaged if row["is_regression"]]
    by_bucket = Counter(row["triage_bucket"] for row in triaged)
    by_regression_bucket = Counter(row["triage_bucket"] for row in regression_rows)
    by_priority = Counter(row["priority"] for row in regression_rows)
    by_status = Counter(str(row.get("status") or "") for row in triaged)
    samples: dict[str, list[dict[str, Any]]] = {}
    for bucket in sorted(by_regression_bucket):
        bucket_rows = [row for row in regression_rows if row["triage_bucket"] == bucket]
        samples[bucket] = bucket_rows[:sample_limit]
    return {
        "report_type": "collateral_regression_triage",
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "source": {
            "shared_post_count": compare.get("shared_post_count"),
            "changed_post_count": compare.get("changed_post_count"),
            "collateral_regression_count": compare.get("collateral_regression_count"),
            "status_counts": compare.get("status_counts") or {},
            "regression_status_counts": compare.get("regression_status_counts") or {},
        },
        "gate": "NO-GO" if regression_rows else "GO",
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "summary": {
            "triaged_change_rows": len(triaged),
            "triaged_regression_rows": len(regression_rows),
            "counts_by_status": dict(by_status),
            "counts_by_priority": dict(by_priority),
            "counts_by_bucket": dict(by_bucket),
            "counts_by_regression_bucket": dict(by_regression_bucket),
        },
        "samples_by_regression_bucket": samples,
        "rows": triaged,
        "next_actions": [
            "P0 wrong_work_title_flip/null_to_resolved/resolved_to_null rows must receive blind judge or source-native review before any collateral approval.",
            "Background full375/bounded runs remain monitoring evidence only until their own result and manifest complete.",
            "Keep semantic_quality=REVIEW-LOCKED and full_scan_approval=false.",
        ],
    }


def write_markdown(path: Path, report: dict[str, Any], *, compare_path: Path) -> None:
    summary = report["summary"]
    lines = [
        "# Collateral 183 regression triage",
        "",
        f"- source compare: `{compare_path.as_posix()}`",
        f"- gate: `{report['gate']}`",
        f"- semantic_quality: `{report['semantic_quality']}`",
        f"- full_scan_approval: `{str(report['full_scan_approval']).lower()}`",
        f"- changed rows: `{summary['triaged_change_rows']}`",
        f"- regression rows: `{summary['triaged_regression_rows']}`",
        "",
        "## Regression buckets",
        "",
    ]
    for bucket, count in sorted(summary["counts_by_regression_bucket"].items()):
        lines.append(f"- `{bucket}`: `{count}`")
    if not summary["counts_by_regression_bucket"]:
        lines.append("- 없음")
    lines.extend(["", "## Priority", ""])
    for priority, count in sorted(summary["counts_by_priority"].items()):
        lines.append(f"- `{priority}`: `{count}`")
    if not summary["counts_by_priority"]:
        lines.append("- 없음")
    lines.extend(["", "## 대표 샘플", ""])
    for bucket, rows in report["samples_by_regression_bucket"].items():
        lines.append(f"### {bucket}")
        if not rows:
            lines.append("- 없음")
            continue
        for row in rows:
            lines.append(
                "- "
                f"`{row['post_id']}` `{row['status']}` "
                f"`{row['before_title']}` -> `{row['after_title']}` "
                f"({row['before_candidate_ledger_status']} -> {row['after_candidate_ledger_status']})"
            )
    lines.extend(
        [
            "",
            "## Gate 해석",
            "",
            "이 triage는 full375 collateral diff의 남은 작업을 정렬하는 산출물이다. "
            "regression row가 남아 있으므로 full collateral approval은 열리지 않는다.",
            "",
            "- background full375/bounded run은 완료 감사 전까지 monitoring evidence다.",
            "- P0 bucket은 blind judge 또는 source-native review가 필요하다.",
            "- `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`를 유지한다.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Triage full collateral regression diff rows into review buckets.")
    parser.add_argument("--compare", required=True, type=Path)
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-md", required=True, type=Path)
    parser.add_argument("--sample-limit", type=int, default=12)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report(load_json(args.compare), sample_limit=args.sample_limit)
    write_json(args.output_json, report)
    write_markdown(args.output_md, report, compare_path=args.compare)
    print(json.dumps({"gate": report["gate"], "summary": report["summary"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
