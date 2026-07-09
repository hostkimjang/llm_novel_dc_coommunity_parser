from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
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


def _verdict_rows_with_sources(verdicts_list: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    for verdicts in verdicts_list:
        verdict_rows = verdicts.get("rows")
        if not isinstance(verdict_rows, list):
            raise ValueError("verdicts JSON must contain rows list")
        source = {
            "review_id": verdicts.get("review_id"),
            "scope": verdicts.get("scope"),
            "source_batch": verdicts.get("source_batch"),
            "source_path": verdicts.get("_source_path"),
            "row_count": len(verdict_rows),
        }
        sources.append(source)
        for row in verdict_rows:
            if isinstance(row, dict):
                copied = dict(row)
                copied["_source_review_id"] = verdicts.get("review_id")
                rows.append(copied)
    return rows, sources


def _queue_transition(
    *,
    batch_row_count: int,
    rows: list[dict[str, Any]],
    validation_issues: list[dict[str, Any]],
) -> dict[str, Any]:
    label_counts = Counter(_string(row.get("review_label")) for row in rows)
    info_missing_rows = label_counts.get("INFO_MISSING", 0)
    decision_rows = max(len(rows) - info_missing_rows, 0)
    exclusion_candidates = sum(
        1
        for row in rows
        if "exclude_from_regression_count_after_gate_wiring" in (row.get("action") or [])
    )
    repair_required = label_counts.get("REPROCESS", 0)
    policy_or_review_required = label_counts.get("HOLD", 0)
    return {
        "original_batch_rows": batch_row_count,
        "original_p0_rows": batch_row_count,
        "source_native_reviewed_rows": len(rows),
        "source_native_decision_rows": decision_rows,
        "info_missing_rows": info_missing_rows,
        "exclusion_candidate_rows": exclusion_candidates,
        "repair_required_rows": repair_required,
        "policy_or_native_review_required_rows": policy_or_review_required,
        "residual_action_queue_rows": max(batch_row_count - exclusion_candidates, 0),
        "validation_issue_count": len(validation_issues),
        "full_collateral_approval_open": False,
        "exclusion_requires_gate_wiring": exclusion_candidates > 0,
    }


def _queue_by_bucket(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[_string(row.get("triage_bucket"))].append(row)
    out: dict[str, dict[str, Any]] = {}
    for bucket, bucket_rows in sorted(grouped.items()):
        label_counts = Counter(_string(row.get("review_label")) for row in bucket_rows)
        info_missing_rows = label_counts.get("INFO_MISSING", 0)
        action_counts: Counter[str] = Counter()
        for row in bucket_rows:
            for action in row.get("action") or []:
                action_counts[_string(action)] += 1
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


def build_summary(*, batch: dict[str, Any], verdicts: dict[str, Any], generated_at: str | None = None) -> dict[str, Any]:
    return build_combined_summary(
        batch=batch,
        verdicts_list=[verdicts],
        generated_at=generated_at,
        review_id=verdicts.get("review_id"),
        scope=verdicts.get("scope"),
        source_batch=verdicts.get("source_batch"),
    )


def build_combined_summary(
    *,
    batch: dict[str, Any],
    verdicts_list: list[dict[str, Any]],
    generated_at: str | None = None,
    review_id: str | None = None,
    scope: str | None = None,
    source_batch: str | None = None,
) -> dict[str, Any]:
    indexed = _review_rows_by_post_id(batch)
    rows, source_verdicts = _verdict_rows_with_sources(verdicts_list)
    out_rows: list[dict[str, Any]] = []
    validation_issues: list[dict[str, Any]] = []
    seen_post_ids: set[int] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        post_id = row.get("post_id")
        if not isinstance(post_id, int):
            validation_issues.append({"post_id": post_id, "issues": ["invalid_post_id"]})
            continue
        if post_id in seen_post_ids:
            validation_issues.append({"post_id": post_id, "issues": ["duplicate_verdict_post_id"]})
            continue
        seen_post_ids.add(post_id)
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
                "source_review_id": row.get("_source_review_id"),
            }
        )
    label_counts = Counter(_string(row.get("review_label")) for row in out_rows)
    info_missing_rows = label_counts.get("INFO_MISSING", 0)
    source_native_decision_rows = max(len(out_rows) - info_missing_rows, 0)
    verdict_counts = Counter(_string(row.get("source_native_verdict")) for row in out_rows)
    bucket_counts = Counter(_string(row.get("triage_bucket")) for row in out_rows)
    action_counts: Counter[str] = Counter()
    for row in out_rows:
        for action in row.get("action") or []:
            action_counts[_string(action)] += 1
    gate = "NO-GO" if validation_issues else "REVIEW-LOCKED"
    return {
        "report_type": "collateral_source_native_review",
        "review_id": review_id or "combined_collateral_source_native_review",
        "scope": scope,
        "generated_at": generated_at or datetime.now().replace(microsecond=0).isoformat(),
        "source_batch": source_batch,
        "source_verdicts": source_verdicts,
        "gate": gate,
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "summary": {
            "batch_review_rows": len(indexed),
            "reviewed_rows": len(out_rows),
            "source_native_decision_rows": source_native_decision_rows,
            "info_missing_rows": info_missing_rows,
            "unreviewed_batch_rows": max(len(indexed) - len(out_rows), 0),
            "unreviewed_or_info_missing_batch_rows": max(len(indexed) - source_native_decision_rows, 0),
            "validation_issue_count": len(validation_issues),
            "counts_by_bucket": dict(bucket_counts),
            "label_counts": dict(label_counts),
            "source_native_verdict_counts": dict(verdict_counts),
            "action_counts": dict(action_counts),
            "queue_transition": _queue_transition(
                batch_row_count=len(indexed),
                rows=out_rows,
                validation_issues=validation_issues,
            ),
            "queue_by_bucket": _queue_by_bucket(out_rows),
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
        f"- source-native decision rows: `{counts.get('source_native_decision_rows', counts['reviewed_rows'])}`",
        f"- info missing rows: `{counts.get('info_missing_rows', 0)}`",
        f"- unreviewed batch rows: `{counts['unreviewed_batch_rows']}`",
        f"- unreviewed or info-missing rows: `{counts.get('unreviewed_or_info_missing_batch_rows', counts['unreviewed_batch_rows'])}`",
        f"- validation issues: `{counts['validation_issue_count']}`",
        "",
        "## 버킷 집계",
        "",
    ]
    for bucket, count in sorted(counts["counts_by_bucket"].items()):
        lines.append(f"- `{bucket}`: `{count}`")
    lines.extend(
        [
            "",
        "## 라벨 집계",
        "",
        ]
    )
    for label, count in sorted(counts["label_counts"].items()):
        lines.append(f"- `{label}`: `{count}`")
    transition = counts.get("queue_transition") or {}
    lines.extend(["", "## Action queue 전환", ""])
    lines.extend(
        [
            f"- 원 batch 행: `{transition.get('original_batch_rows', transition.get('original_p0_rows', 0))}`",
            f"- source-native 검토 완료: `{transition.get('source_native_reviewed_rows', 0)}`",
            f"- source-native decision rows: `{transition.get('source_native_decision_rows', transition.get('source_native_reviewed_rows', 0))}`",
            f"- info missing rows: `{transition.get('info_missing_rows', 0)}`",
            f"- gate wiring 뒤 regression count 제외 후보: `{transition.get('exclusion_candidate_rows', 0)}`",
            f"- REPROCESS 수리 큐: `{transition.get('repair_required_rows', 0)}`",
            f"- HOLD 정책/native 추가 검토 큐: `{transition.get('policy_or_native_review_required_rows', 0)}`",
            f"- 잔여 action queue: `{transition.get('residual_action_queue_rows', 0)}`",
            f"- full collateral approval open: `{str(transition.get('full_collateral_approval_open', False)).lower()}`",
        ]
    )
    queue_by_bucket = counts.get("queue_by_bucket") or {}
    if queue_by_bucket:
        lines.extend(["", "## 버킷별 action queue", ""])
        for bucket, bucket_counts in sorted(queue_by_bucket.items()):
            lines.append(
                "- "
                f"`{bucket}` rows=`{bucket_counts.get('rows', 0)}` "
                f"decision=`{bucket_counts.get('source_native_decision_rows', bucket_counts.get('rows', 0))}` "
                f"info_missing=`{bucket_counts.get('info_missing_rows', 0)}` "
                f"exclude_candidates=`{bucket_counts.get('exclusion_candidate_rows', 0)}` "
                f"residual=`{bucket_counts.get('residual_action_queue_rows', 0)}`"
            )
    lines.extend(["", "## Source-native verdict 집계", ""])
    for verdict, count in sorted(counts["source_native_verdict_counts"].items()):
        lines.append(f"- `{verdict}`: `{count}`")
    lines.extend(["", "## 행별 판정", ""])
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
    parser.add_argument("--verdicts", required=True, type=Path, nargs="+")
    parser.add_argument("--review-id", default="", help="Override review_id for combined verdict inputs.")
    parser.add_argument("--scope", default="", help="Override scope/title for combined verdict inputs.")
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-md", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    verdicts_list = []
    for path in args.verdicts:
        verdicts = load_json(path)
        if isinstance(verdicts, dict):
            verdicts["_source_path"] = str(path)
        verdicts_list.append(verdicts)
    if len(verdicts_list) == 1 and not args.review_id and not args.scope:
        summary = build_summary(batch=load_json(args.batch), verdicts=verdicts_list[0])
    else:
        summary = build_combined_summary(
            batch=load_json(args.batch),
            verdicts_list=verdicts_list,
            review_id=args.review_id or "combined_collateral_source_native_review",
            scope=args.scope or "combined collateral source-native review",
            source_batch=str(args.batch),
        )
    write_json(args.output_json, summary)
    write_markdown(args.output_md, summary)
    print(json.dumps({"gate": summary["gate"], "summary": summary["summary"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
