from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _string(value: Any) -> str:
    return str(value or "").strip()


def _review_rows_by_post_id(batch: dict[str, Any]) -> dict[int, dict[str, Any]]:
    rows = batch.get("review_rows")
    if not isinstance(rows, list):
        raise ValueError("batch JSON must contain review_rows list")
    indexed: dict[int, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        post_id = row.get("post_id")
        if isinstance(post_id, int):
            indexed[post_id] = row
    return indexed


def _option_ids(row: dict[str, Any]) -> set[str]:
    return {
        _string(option.get("option_id"))
        for option in row.get("blind_judge_options") or []
        if isinstance(option, dict) and _string(option.get("option_id"))
    } | {"HOLD"}


def _validate_verdict(row: dict[str, Any], batch_row: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    selected = _string(row.get("selected_option_id"))
    if not selected:
        issues.append("missing_selected_option_id")
    elif selected not in _option_ids(batch_row):
        issues.append("selected_option_id_not_in_batch_options")
    if not _string(row.get("review_label")):
        issues.append("missing_review_label")
    if not _string(row.get("source_native_verdict")):
        issues.append("missing_source_native_verdict")
    if not row.get("evidence_refs"):
        issues.append("missing_evidence_refs")
    return issues


def build_summary(*, batch: dict[str, Any], verdicts: dict[str, Any], generated_at: str | None = None) -> dict[str, Any]:
    indexed = _review_rows_by_post_id(batch)
    rows = verdicts.get("rows")
    if not isinstance(rows, list):
        raise ValueError("verdicts JSON must contain rows list")
    out_rows: list[dict[str, Any]] = []
    validation_issues: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        post_id = row.get("post_id")
        if not isinstance(post_id, int):
            validation_issues.append({"post_id": post_id, "issues": ["invalid_post_id"]})
            continue
        batch_row = indexed.get(post_id)
        if batch_row is None:
            validation_issues.append({"post_id": post_id, "issues": ["post_id_not_in_batch"]})
            continue
        issues = _validate_verdict(row, batch_row)
        if issues:
            validation_issues.append({"post_id": post_id, "issues": issues})
        source = batch_row.get("source_native_packet") or {}
        comparison = batch_row.get("comparison_private_not_for_blind_judge") or {}
        out_rows.append(
            {
                "post_id": post_id,
                "triage_bucket": batch_row.get("triage_bucket"),
                "collateral_status": batch_row.get("collateral_status"),
                "post_title": source.get("post_title"),
                "selected_option_id": row.get("selected_option_id"),
                "selected_title": row.get("selected_title"),
                "selected_url": row.get("selected_url"),
                "review_label": row.get("review_label"),
                "source_native_verdict": row.get("source_native_verdict"),
                "evidence_grade": row.get("evidence_grade"),
                "action": row.get("action") or [],
                "rationale_ko": row.get("rationale_ko"),
                "evidence_refs": row.get("evidence_refs") or [],
                "before_title": (comparison.get("before_triage_identity") or {}).get("official_title"),
                "after_title": (comparison.get("after_triage_identity") or {}).get("official_title"),
            }
        )
    label_counts = Counter(_string(row.get("review_label")) for row in out_rows)
    verdict_counts = Counter(_string(row.get("source_native_verdict")) for row in out_rows)
    bucket_counts = Counter(_string(row.get("triage_bucket")) for row in out_rows)
    action_counts: Counter[str] = Counter()
    for row in out_rows:
        for action in row.get("action") or []:
            action_counts[_string(action)] += 1
    gate = "NO-GO" if validation_issues else "REVIEW-LOCKED"
    return {
        "report_type": "collateral_source_native_review",
        "review_id": verdicts.get("review_id"),
        "scope": verdicts.get("scope"),
        "generated_at": generated_at or datetime.now().replace(microsecond=0).isoformat(),
        "source_batch": verdicts.get("source_batch"),
        "gate": gate,
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "summary": {
            "batch_review_rows": len(indexed),
            "reviewed_rows": len(out_rows),
            "unreviewed_batch_rows": max(len(indexed) - len(out_rows), 0),
            "validation_issue_count": len(validation_issues),
            "counts_by_bucket": dict(bucket_counts),
            "label_counts": dict(label_counts),
            "source_native_verdict_counts": dict(verdict_counts),
            "action_counts": dict(action_counts),
        },
        "validation_issues": validation_issues,
        "rows": out_rows,
        "next_actions": [
            "REPROCESS rows require targeted guard/runtime follow-up before collateral approval.",
            "HOLD rows require native-web or policy review before they can reduce the actionable queue.",
            "ACCEPT rows can be excluded from regression-counting only after the summary is wired into the collateral gate.",
            "Keep semantic_quality=REVIEW-LOCKED and full_scan_approval=false.",
        ],
    }


def write_markdown(path: Path, summary: dict[str, Any]) -> None:
    counts = summary["summary"]
    title = summary.get("scope") or summary.get("review_id") or "collateral source-native 검토"
    lines = [
        f"# {title}",
        "",
        f"- gate: `{summary['gate']}`",
        f"- semantic_quality: `{summary['semantic_quality']}`",
        f"- full_scan_approval: `{str(summary['full_scan_approval']).lower()}`",
        f"- batch review rows: `{counts['batch_review_rows']}`",
        f"- reviewed rows: `{counts['reviewed_rows']}`",
        f"- unreviewed batch rows: `{counts['unreviewed_batch_rows']}`",
        f"- validation issues: `{counts['validation_issue_count']}`",
        "",
        "## Bucket counts",
        "",
    ]
    for bucket, count in sorted(counts["counts_by_bucket"].items()):
        lines.append(f"- `{bucket}`: `{count}`")
    lines.extend(
        [
            "",
        "## Label counts",
        "",
        ]
    )
    for label, count in sorted(counts["label_counts"].items()):
        lines.append(f"- `{label}`: `{count}`")
    lines.extend(["", "## Source-native verdict counts", ""])
    for verdict, count in sorted(counts["source_native_verdict_counts"].items()):
        lines.append(f"- `{verdict}`: `{count}`")
    lines.extend(["", "## Rows", ""])
    for row in summary["rows"]:
        actions = ", ".join(row.get("action") or [])
        lines.append(
            "- "
            f"`{row['post_id']}` `{row['review_label']}` `{row['source_native_verdict']}` "
            f"selected=`{row.get('selected_title')}` action=`{actions}`"
        )
        lines.append(f"  - 근거: {row.get('rationale_ko')}")
    lines.extend(
        [
            "",
            "## Gate 해석",
            "",
            "이 검토는 collateral P0 bucket의 source-native 라벨 산출물이다. "
            "REPROCESS/HOLD 또는 validation issue가 남아 있으면 full collateral approval은 열리지 않는다.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate and summarize collateral source-native review verdicts.")
    parser.add_argument("--batch", required=True, type=Path)
    parser.add_argument("--verdicts", required=True, type=Path)
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-md", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = build_summary(batch=load_json(args.batch), verdicts=load_json(args.verdicts))
    write_json(args.output_json, summary)
    write_markdown(args.output_md, summary)
    print(json.dumps({"gate": summary["gate"], "summary": summary["summary"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
