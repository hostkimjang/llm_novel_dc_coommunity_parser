from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
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


def _string(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    try:
        if value is None or value == "":
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _merge_counter(target: Counter[str], values: dict[str, Any] | None) -> None:
    if not isinstance(values, dict):
        return
    for key, value in values.items():
        target[_string(key)] += _int(value)


def _queue_by_bucket(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[_string(row.get("triage_bucket"))].append(row)
    out: dict[str, dict[str, Any]] = {}
    for bucket, bucket_rows in sorted(grouped.items()):
        label_counts = Counter(_string(row.get("review_label")) for row in bucket_rows)
        action_counts: Counter[str] = Counter()
        for row in bucket_rows:
            for action in row.get("action") or []:
                action_counts[_string(action)] += 1
        info_missing_rows = label_counts.get("INFO_MISSING", 0)
        exclusion_candidates = action_counts.get("exclude_from_regression_count_after_gate_wiring", 0)
        out[bucket] = {
            "rows": len(bucket_rows),
            "source_native_decision_rows": max(len(bucket_rows) - info_missing_rows, 0),
            "info_missing_rows": info_missing_rows,
            "label_counts": dict(label_counts),
            "action_counts": dict(action_counts),
            "exclusion_candidate_rows": exclusion_candidates,
            "residual_action_queue_rows": max(len(bucket_rows) - exclusion_candidates, 0),
        }
    return out


def build_merged_summary(
    *,
    summaries: list[dict[str, Any]],
    review_id: str,
    scope: str,
    generated_at: str | None = None,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    source_summaries: list[dict[str, Any]] = []
    validation_issues: list[dict[str, Any]] = []
    seen_post_ids: set[int] = set()
    counts_by_bucket: Counter[str] = Counter()
    label_counts: Counter[str] = Counter()
    verdict_counts: Counter[str] = Counter()
    action_counts: Counter[str] = Counter()

    batch_review_rows = 0
    reviewed_rows = 0
    source_native_decision_rows = 0
    info_missing_rows = 0
    unreviewed_batch_rows = 0
    unreviewed_or_info_missing_batch_rows = 0
    original_p0_rows = 0
    exclusion_candidate_rows = 0
    repair_required_rows = 0
    policy_or_native_review_required_rows = 0
    residual_action_queue_rows = 0

    for index, summary_doc in enumerate(summaries, start=1):
        summary = summary_doc.get("summary") if isinstance(summary_doc.get("summary"), dict) else {}
        transition = summary.get("queue_transition") if isinstance(summary.get("queue_transition"), dict) else {}
        source_id = _string(summary_doc.get("review_id")) or f"summary_{index}"
        source_summaries.append(
            {
                "review_id": source_id,
                "scope": summary_doc.get("scope"),
                "source_path": summary_doc.get("_source_path"),
                "gate": summary_doc.get("gate"),
                "batch_review_rows": summary.get("batch_review_rows"),
                "reviewed_rows": summary.get("reviewed_rows"),
                "exclusion_candidate_rows": transition.get("exclusion_candidate_rows"),
                "residual_action_queue_rows": transition.get("residual_action_queue_rows"),
            }
        )

        if _string(summary_doc.get("gate")) != "REVIEW-LOCKED":
            validation_issues.append({"source_review_id": source_id, "issues": ["source_gate_not_review_locked"]})
        if _int(summary.get("validation_issue_count")) != 0:
            validation_issues.append({"source_review_id": source_id, "issues": ["source_validation_issues_nonzero"]})

        batch_review_rows += _int(summary.get("batch_review_rows"))
        reviewed_rows += _int(summary.get("reviewed_rows"))
        source_native_decision_rows += _int(summary.get("source_native_decision_rows"))
        info_missing_rows += _int(summary.get("info_missing_rows"))
        unreviewed_batch_rows += _int(summary.get("unreviewed_batch_rows"))
        unreviewed_or_info_missing_batch_rows += _int(summary.get("unreviewed_or_info_missing_batch_rows"))

        _merge_counter(counts_by_bucket, summary.get("counts_by_bucket"))
        _merge_counter(label_counts, summary.get("label_counts"))
        _merge_counter(verdict_counts, summary.get("source_native_verdict_counts"))
        _merge_counter(action_counts, summary.get("action_counts"))

        original_p0_rows += _int(transition.get("original_p0_rows"), _int(summary.get("batch_review_rows")))
        exclusion_candidate_rows += _int(transition.get("exclusion_candidate_rows"))
        repair_required_rows += _int(transition.get("repair_required_rows"))
        policy_or_native_review_required_rows += _int(transition.get("policy_or_native_review_required_rows"))
        residual_action_queue_rows += _int(transition.get("residual_action_queue_rows"))

        for row in summary_doc.get("rows") or []:
            if not isinstance(row, dict):
                continue
            post_id = row.get("post_id")
            if not isinstance(post_id, int):
                validation_issues.append(
                    {"source_review_id": source_id, "post_id": post_id, "issues": ["invalid_post_id"]}
                )
                continue
            if post_id in seen_post_ids:
                validation_issues.append(
                    {"source_review_id": source_id, "post_id": post_id, "issues": ["duplicate_post_id"]}
                )
                continue
            seen_post_ids.add(post_id)
            copied = dict(row)
            copied["source_review_id"] = row.get("source_review_id") or source_id
            rows.append(copied)

    if reviewed_rows != len(rows):
        validation_issues.append(
            {
                "issues": ["merged_row_count_mismatch"],
                "reviewed_rows_from_summaries": reviewed_rows,
                "merged_rows": len(rows),
            }
        )

    gate = "NO-GO" if validation_issues else "REVIEW-LOCKED"
    return {
        "report_type": "merged_collateral_source_native_review",
        "review_id": review_id,
        "scope": scope,
        "generated_at": generated_at or datetime.now().replace(microsecond=0).isoformat(),
        "source_summaries": source_summaries,
        "gate": gate,
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "summary": {
            "batch_review_rows": batch_review_rows,
            "reviewed_rows": reviewed_rows,
            "source_native_decision_rows": source_native_decision_rows,
            "info_missing_rows": info_missing_rows,
            "unreviewed_batch_rows": unreviewed_batch_rows,
            "unreviewed_or_info_missing_batch_rows": unreviewed_or_info_missing_batch_rows,
            "validation_issue_count": len(validation_issues),
            "counts_by_bucket": dict(counts_by_bucket),
            "label_counts": dict(label_counts),
            "source_native_verdict_counts": dict(verdict_counts),
            "action_counts": dict(action_counts),
            "queue_transition": {
                "original_p0_rows": original_p0_rows,
                "source_native_reviewed_rows": reviewed_rows,
                "source_native_decision_rows": source_native_decision_rows,
                "info_missing_rows": info_missing_rows,
                "exclusion_candidate_rows": exclusion_candidate_rows,
                "repair_required_rows": repair_required_rows,
                "policy_or_native_review_required_rows": policy_or_native_review_required_rows,
                "residual_action_queue_rows": residual_action_queue_rows,
                "validation_issue_count": len(validation_issues),
                "full_collateral_approval_open": False,
                "exclusion_requires_gate_wiring": exclusion_candidate_rows > 0,
            },
            "queue_by_bucket": _queue_by_bucket(rows),
        },
        "validation_issues": validation_issues,
        "rows": rows,
        "next_actions": [
            "항상 full375 collateral gate에 이 병합 요약을 함께 넣어 raw regression과 review-adjusted regression을 같이 본다.",
            "HOLD/REPROCESS/INFO_MISSING 행은 approval이 아니라 후속 native-web, image, alias, contract repair 큐다.",
            "semantic_quality=REVIEW-LOCKED와 full_scan_approval=false를 유지한다.",
        ],
    }


def write_markdown(path: Path, summary: dict[str, Any]) -> None:
    counts = summary["summary"]
    transition = counts["queue_transition"]
    lines = [
        f"# {summary['scope']}",
        "",
        f"- gate: `{summary['gate']}`",
        f"- semantic_quality: `{summary['semantic_quality']}`",
        f"- full_scan_approval: `{str(summary['full_scan_approval']).lower()}`",
        f"- source summaries: `{len(summary['source_summaries'])}`",
        f"- batch review rows: `{counts['batch_review_rows']}`",
        f"- reviewed rows: `{counts['reviewed_rows']}`",
        f"- source-native decision rows: `{counts['source_native_decision_rows']}`",
        f"- info missing rows: `{counts['info_missing_rows']}`",
        f"- validation issues: `{counts['validation_issue_count']}`",
        "",
        "## Source Summaries",
        "",
    ]
    for source in summary["source_summaries"]:
        lines.append(
            "- "
            f"`{source.get('review_id')}` rows=`{source.get('reviewed_rows')}` "
            f"exclude=`{source.get('exclusion_candidate_rows')}` "
            f"residual=`{source.get('residual_action_queue_rows')}` "
            f"path=`{source.get('source_path')}`"
        )
    lines.extend(["", "## Action queue 전환", ""])
    lines.extend(
        [
            f"- 원 P0 행: `{transition['original_p0_rows']}`",
            f"- source-native 검토 완료: `{transition['source_native_reviewed_rows']}`",
            f"- source-native decision rows: `{transition['source_native_decision_rows']}`",
            f"- info missing rows: `{transition['info_missing_rows']}`",
            f"- gate wiring 뒤 regression count 제외 후보: `{transition['exclusion_candidate_rows']}`",
            f"- REPROCESS 수리 큐: `{transition['repair_required_rows']}`",
            f"- HOLD 정책/native 추가 검토 큐: `{transition['policy_or_native_review_required_rows']}`",
            f"- 잔여 action queue: `{transition['residual_action_queue_rows']}`",
            f"- full collateral approval open: `{str(transition['full_collateral_approval_open']).lower()}`",
            "",
            "## 라벨 집계",
            "",
        ]
    )
    for label, count in sorted(counts["label_counts"].items()):
        lines.append(f"- `{label}`: `{count}`")
    lines.extend(["", "## 버킷 집계", ""])
    for bucket, count in sorted(counts["counts_by_bucket"].items()):
        lines.append(f"- `{bucket}`: `{count}`")
    lines.extend(["", "## Gate 해석", ""])
    lines.append(
        "이 병합 요약은 full375 collateral regression을 source-native 검토로 재회계하기 위한 입력이다. "
        "검토 제외 후보가 있어도 raw/full375 gate가 조용해지기 전까지 승인으로 보지 않는다."
    )
    if summary["validation_issues"]:
        lines.extend(["", "## Validation Issues", ""])
        for issue in summary["validation_issues"]:
            lines.append(f"- `{issue}`")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge clean collateral source-native review summaries.")
    parser.add_argument("--summary", required=True, type=Path, nargs="+")
    parser.add_argument("--review-id", required=True)
    parser.add_argument("--scope", required=True)
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-md", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summaries: list[dict[str, Any]] = []
    for path in args.summary:
        summary = load_json(path)
        summary["_source_path"] = str(path)
        summaries.append(summary)
    merged = build_merged_summary(summaries=summaries, review_id=args.review_id, scope=args.scope)
    write_json(args.output_json, merged)
    write_markdown(args.output_md, merged)
    print(json.dumps({"gate": merged["gate"], "summary": merged["summary"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
