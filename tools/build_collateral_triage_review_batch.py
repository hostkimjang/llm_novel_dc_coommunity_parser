from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


BUCKET_ORDER = {
    "wrong_work_title_flip": 0,
    "unsafe_promotion_from_hold": 1,
    "safe_loss_resolved_to_null": 2,
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_jsonl_index(path: Path) -> dict[int, dict[str, Any]]:
    rows: dict[int, dict[str, Any]] = {}
    with path.open(encoding="utf-8-sig") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            post_id = _int_or_none(row.get("post_id"))
            if post_id is not None:
                rows[post_id] = row
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _int_or_none(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _result_rows_by_post_id(payload: Any) -> dict[int, dict[str, Any]]:
    rows = payload
    if isinstance(payload, dict):
        for key in ("results", "rows", "data", "items"):
            if isinstance(payload.get(key), list):
                rows = payload[key]
                break
    if not isinstance(rows, list):
        raise ValueError("Expected result JSON list or object containing results/rows/data/items")
    indexed: dict[int, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        post_id = _int_or_none(row.get("post_id"))
        if post_id is not None:
            indexed[post_id] = row
    return indexed


def _identity_from_result(row: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(row, dict):
        return {}
    analysis = row.get("analysis_result")
    if not isinstance(analysis, dict):
        result = row.get("result")
        if isinstance(result, dict):
            analysis = result.get("analysis_result")
    if not isinstance(analysis, dict):
        return {}
    identity = analysis.get("identity")
    return identity if isinstance(identity, dict) else {}


def _novel_identity(identity: dict[str, Any]) -> dict[str, Any]:
    novel_identity = identity.get("novel_identity")
    return novel_identity if isinstance(novel_identity, dict) else {}


def _candidate_ledger(identity: dict[str, Any]) -> dict[str, Any]:
    ledger = identity.get("candidate_ledger")
    return ledger if isinstance(ledger, dict) else {}


def _identity_digest(identity: dict[str, Any]) -> dict[str, Any]:
    novel = _novel_identity(identity)
    ledger = _candidate_ledger(identity)
    return {
        "official_title": _string_or_none(novel.get("official_title") or identity.get("official_title")),
        "heretic_url": _string_or_none(novel.get("heretic_url") or identity.get("heretic_url")),
        "confidence": _string_or_none(novel.get("confidence") or identity.get("confidence")),
        "title_resolution_state": _string_or_none(identity.get("title_resolution_state")),
        "candidate_ledger_status": _string_or_none(identity.get("candidate_ledger_status")),
        "work_resolution": _string_or_none(identity.get("work_resolution")),
        "discussion_type": _string_or_none(identity.get("discussion_type")),
        "topicality": _string_or_none(identity.get("topicality")),
        "candidate_count": ledger.get("candidate_count") or 0,
        "title_candidates": [_string_or_none(item) for item in _as_list(ledger.get("title_candidates")) if _string_or_none(item)][:12],
        "blocked_official_title": _string_or_none(ledger.get("blocked_official_title")),
        "blocked_official_title_url": _string_or_none(ledger.get("blocked_official_title_url")),
        "promotion_blocked_reasons": [
            _string_or_none(item)
            for item in _as_list(ledger.get("promotion_blocked_reasons"))
            if _string_or_none(item)
        ][:12],
    }


def _trim_strings(value: Any, *, limit: int, chars: int) -> list[str]:
    out: list[str] = []
    for item in _as_list(value):
        if len(out) >= limit:
            break
        text = _string_or_none(item)
        if text is None:
            continue
        out.append(text[:chars])
    return out


def _source_packet(row: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(row, dict):
        return {"missing_source_row": True}
    return {
        "missing_source_row": False,
        "post_id": row.get("post_id"),
        "gallery_id": row.get("gallery_id"),
        "post_title": row.get("title"),
        "post_url": row.get("url"),
        "created_at": row.get("created_at"),
        "author": row.get("author") or row.get("post_author"),
        "content": _trim_strings(row.get("content"), limit=8, chars=1000),
        "comments": _trim_strings(row.get("comments"), limit=10, chars=1000),
        "comment_dialogue_context_lines": _trim_strings(
            row.get("comment_dialogue_context_lines"),
            limit=10,
            chars=1000,
        ),
        "image_count": row.get("image_count") or len(_as_list(row.get("image_urls"))),
        "image_urls": _trim_strings(row.get("image_urls"), limit=4, chars=1200),
        "panel_roles": _as_list(row.get("_panel_roles")),
        "judge_seed": row.get("_judge_seed") if isinstance(row.get("_judge_seed"), dict) else None,
    }


def _triage_identity(row: dict[str, Any], side: str) -> dict[str, Any]:
    return {
        "official_title": row.get(f"{side}_title"),
        "heretic_url": row.get(f"{side}_url"),
        "candidate_ledger_status": row.get(f"{side}_candidate_ledger_status"),
        "title_resolution_state": row.get(f"{side}_title_resolution_state"),
        "candidate_count": row.get(f"{side}_candidate_count") or 0,
    }


def _blind_candidate_options(row: dict[str, Any]) -> list[dict[str, Any]]:
    seen: set[tuple[str | None, str | None]] = set()
    raw = [_triage_identity(row, "before"), _triage_identity(row, "after")]
    items: list[tuple[str | None, str | None]] = []
    for item in raw:
        title = _string_or_none(item.get("official_title"))
        url = _string_or_none(item.get("heretic_url"))
        if not title and not url:
            continue
        key = (title, url)
        if key in seen:
            continue
        seen.add(key)
        items.append(key)
    items.sort(key=lambda pair: ((pair[0] or ""), (pair[1] or "")))
    return [
        {
            "option_id": f"C{idx}",
            "official_title": title,
            "heretic_url": url,
        }
        for idx, (title, url) in enumerate(items, start=1)
    ]


def _review_question(bucket: str) -> str:
    if bucket == "wrong_work_title_flip":
        return "원문만 보고 후보 C들 중 실제로 논의된 작품이 무엇인지, 둘 다 아니면 hold가 맞는지 판정한다."
    if bucket == "unsafe_promotion_from_hold":
        return "원문과 source-native 근거만 보고 승격 후보가 정당한 작품인지, 아니면 promotion_blocked/hold가 맞는지 판정한다."
    if bucket == "safe_loss_resolved_to_null":
        return "원문과 source-native 근거만 보고 기존 safe title이 정당했는지, 아니면 null/hold로 내린 것이 정당한지 판정한다."
    return "원문과 source-native 근거만 보고 정답 title 또는 hold를 판정한다."


def _selection_key(row: dict[str, Any]) -> tuple[int, int]:
    bucket = str(row.get("triage_bucket") or "")
    post_id = _int_or_none(row.get("post_id")) or 0
    return (BUCKET_ORDER.get(bucket, 99), post_id)


def _p0_rows(
    triage_report: dict[str, Any],
    *,
    per_bucket_limit: int = 0,
    buckets: set[str] | None = None,
    include_post_ids: set[int] | None = None,
    exclude_post_ids: set[int] | None = None,
    include_all_priorities: bool = False,
) -> list[dict[str, Any]]:
    exclude_post_ids = exclude_post_ids or set()
    rows = [
        row
        for row in triage_report.get("rows", [])
        if isinstance(row, dict)
        and row.get("is_regression") is True
        and (include_all_priorities or row.get("priority") == "P0")
    ]
    if buckets:
        rows = [row for row in rows if str(row.get("triage_bucket") or "") in buckets]
    if include_post_ids:
        rows = [
            row
            for row in rows
            if (_int_or_none(row.get("post_id")) or 0) in include_post_ids
        ]
    rows = [
        row
        for row in rows
        if (_int_or_none(row.get("post_id")) or 0) not in exclude_post_ids
    ]
    rows.sort(key=_selection_key)
    if per_bucket_limit <= 0:
        return rows
    selected: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    for row in rows:
        bucket = str(row.get("triage_bucket") or "")
        if counts[bucket] >= per_bucket_limit:
            continue
        selected.append(row)
        counts[bucket] += 1
    return selected


def build_review_batch(
    *,
    triage_report: dict[str, Any],
    panel_rows: dict[int, dict[str, Any]],
    baseline_rows: dict[int, dict[str, Any]],
    after_rows: dict[int, dict[str, Any]],
    per_bucket_limit: int = 0,
    buckets: set[str] | None = None,
    include_post_ids: set[int] | None = None,
    exclude_post_ids: set[int] | None = None,
    include_all_priorities: bool = False,
    scope_label: str = "collateral P0",
    generated_at: str | None = None,
) -> dict[str, Any]:
    exclude_post_ids = exclude_post_ids or set()
    pre_exclusion_p0_rows = _p0_rows(
        triage_report,
        per_bucket_limit=0,
        buckets=buckets,
        include_post_ids=include_post_ids,
        exclude_post_ids=set(),
        include_all_priorities=include_all_priorities,
    )
    excluded_p0_candidate_rows = sum(
        1
        for row in pre_exclusion_p0_rows
        if (_int_or_none(row.get("post_id")) or 0) in exclude_post_ids
    )
    selected = _p0_rows(
        triage_report,
        per_bucket_limit=per_bucket_limit,
        buckets=buckets,
        include_post_ids=include_post_ids,
        exclude_post_ids=exclude_post_ids,
        include_all_priorities=include_all_priorities,
    )
    review_rows: list[dict[str, Any]] = []
    missing = Counter()
    for triage in selected:
        post_id = _int_or_none(triage.get("post_id"))
        source = panel_rows.get(post_id) if post_id is not None else None
        baseline = baseline_rows.get(post_id) if post_id is not None else None
        after = after_rows.get(post_id) if post_id is not None else None
        if source is None:
            missing["source"] += 1
        if baseline is None:
            missing["baseline"] += 1
        if after is None:
            missing["after"] += 1
        bucket = str(triage.get("triage_bucket") or "")
        review_rows.append(
            {
                "post_id": post_id,
                "priority": triage.get("priority"),
                "triage_bucket": bucket,
                "collateral_status": triage.get("status"),
                "review_gate": "REVIEW-LOCKED",
                "search_state_tag": "search-blind conditional until search degraded P0 recovers",
                "blind_judge_question_ko": _review_question(bucket),
                "blind_judge_options": _blind_candidate_options(triage),
                "blind_judge_hold_option": {
                    "option_id": "HOLD",
                    "meaning": "원문만으로 작품 확정 불가, 또는 후보가 모두 부정확함",
                },
                "source_native_packet": _source_packet(source),
                "comparison_private_not_for_blind_judge": {
                    "before_triage_identity": _triage_identity(triage, "before"),
                    "after_triage_identity": _triage_identity(triage, "after"),
                    "baseline_result_identity": _identity_digest(_identity_from_result(baseline)),
                    "after_result_identity": _identity_digest(_identity_from_result(after)),
                },
                "review_decision_schema": {
                    "selected_option_id": None,
                    "resolved_title": None,
                    "resolved_url": None,
                    "decision": "pending",
                    "needs_native_web_check": True,
                    "judge_evidence_note_ko": None,
                },
            }
        )
    counts_by_bucket = Counter(str(row.get("triage_bucket") or "") for row in review_rows)
    counts_by_priority = Counter(str(row.get("priority") or "") for row in review_rows)
    return {
        "report_type": "collateral_p0_blind_source_review_batch",
        "scope_label": scope_label,
        "generated_at": generated_at or datetime.now().replace(microsecond=0).isoformat(),
        "gate": "REVIEW-LOCKED",
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "search_recovery_gate": "P0_OPEN",
        "promotion_blocked_interpretation": "search-blind conditional",
        "summary": {
            "input_triage_rows": len(triage_report.get("rows", [])),
            "selected_review_rows": len(review_rows),
            "counts_by_bucket": dict(counts_by_bucket),
            "counts_by_priority": dict(counts_by_priority),
            "missing_source_rows": missing.get("source", 0),
            "missing_baseline_result_rows": missing.get("baseline", 0),
            "missing_after_result_rows": missing.get("after", 0),
            "per_bucket_limit": per_bucket_limit,
            "bucket_filter": sorted(buckets or []),
            "include_post_ids": sorted(include_post_ids or []),
            "excluded_post_id_rows": len(exclude_post_ids),
            "excluded_p0_candidate_rows": excluded_p0_candidate_rows,
            "include_all_priorities": include_all_priorities,
        },
        "instructions_ko": [
            "blind judge 입력에는 source_native_packet과 blind_judge_options만 제공한다.",
            "comparison_private_not_for_blind_judge는 배치 검수와 전후 diff 설명용이며 blind judge에는 제공하지 않는다.",
            "search degraded 복구 전 promotion_blocked 관련 해석은 search-blind conditional로 태깅한다.",
            "정답 판정 전까지 semantic_quality=REVIEW-LOCKED, full_scan_approval=false를 유지한다.",
        ],
        "review_rows": review_rows,
    }


def write_markdown(path: Path, report: dict[str, Any], *, inputs: dict[str, Path]) -> None:
    summary = report["summary"]
    scope_label = str(report.get("scope_label") or "collateral P0")
    lines = [
        f"# {scope_label} blind/source-native 검토 배치",
        "",
        f"- gate: `{report['gate']}`",
        f"- semantic_quality: `{report['semantic_quality']}`",
        f"- full_scan_approval: `{str(report['full_scan_approval']).lower()}`",
        f"- search recovery gate: `{report['search_recovery_gate']}`",
        f"- promotion_blocked 해석: `{report['promotion_blocked_interpretation']}`",
        f"- selected review rows: `{summary['selected_review_rows']}`",
        f"- excluded post_id rows: `{summary.get('excluded_post_id_rows', 0)}`",
        f"- excluded P0 candidate rows: `{summary.get('excluded_p0_candidate_rows', 0)}`",
        f"- include all priorities: `{str(summary.get('include_all_priorities', False)).lower()}`",
        "",
        "## 입력",
        "",
    ]
    for name, path_value in inputs.items():
        lines.append(f"- {name}: `{path_value.as_posix()}`")
    lines.extend(["", "## Bucket", ""])
    for bucket, count in sorted(summary["counts_by_bucket"].items()):
        lines.append(f"- `{bucket}`: `{count}`")
    if not summary["counts_by_bucket"]:
        lines.append("- 없음")
    lines.extend(["", "## Priority", ""])
    for priority, count in sorted((summary.get("counts_by_priority") or {}).items()):
        lines.append(f"- `{priority}`: `{count}`")
    if not summary.get("counts_by_priority"):
        lines.append("- 없음")
    lines.extend(
        [
            "",
            "## Blind judge 운영 지침",
            "",
            "- judge에는 `source_native_packet`, `blind_judge_options`, `blind_judge_hold_option`만 전달한다.",
            "- `comparison_private_not_for_blind_judge`는 전후 회귀 추적용이므로 judge 입력에서 제외한다.",
            "- native web 확인 전까지 `needs_native_web_check=true`를 유지한다.",
            f"- 이 배치는 {scope_label} 정답성 검토 입력이며 승인 산출물이 아니다.",
            "",
            "## 대표 행",
            "",
        ]
    )
    samples_by_bucket: dict[str, list[dict[str, Any]]] = {}
    for row in report["review_rows"]:
        samples_by_bucket.setdefault(row["triage_bucket"], []).append(row)
    for bucket in sorted(samples_by_bucket, key=lambda item: BUCKET_ORDER.get(item, 99)):
        lines.append(f"### {bucket}")
        for row in samples_by_bucket[bucket][:8]:
            options = ", ".join(
                f"{option['option_id']}={option.get('official_title') or option.get('heretic_url')}"
                for option in row["blind_judge_options"]
            )
            if not options:
                options = "후보 없음"
            post_title = row["source_native_packet"].get("post_title")
            lines.append(f"- `{row['post_id']}` `{row['collateral_status']}` post=`{post_title}` options: {options}")
        lines.append("")
    lines.extend(
        [
            "## Gate 해석",
            "",
            f"이 산출물은 {scope_label}를 blind/source-native 검토 가능한 입력으로 고정한다. "
            "정답 라벨이 채워지기 전까지 full collateral approval은 열리지 않는다.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build blind/source-native review batch for collateral triage rows.")
    parser.add_argument("--triage", required=True, type=Path)
    parser.add_argument("--panel-input", required=True, type=Path)
    parser.add_argument("--baseline-result", required=True, type=Path)
    parser.add_argument("--after-result", required=True, type=Path)
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-jsonl", required=True, type=Path)
    parser.add_argument("--output-md", required=True, type=Path)
    parser.add_argument(
        "--per-bucket-limit",
        type=int,
        default=0,
        help="0 keeps every P0 row; positive values keep this many rows per bucket.",
    )
    parser.add_argument(
        "--bucket",
        action="append",
        default=[],
        help="Restrict the batch to one triage_bucket. Repeat to include multiple buckets.",
    )
    parser.add_argument(
        "--scope-label",
        default="collateral P0",
        help="Reader-facing scope label used in report JSON/Markdown.",
    )
    parser.add_argument(
        "--exclude-post-ids",
        default="",
        help="쉼표로 구분한 post_id 목록. 이미 닫힌 collateral row를 review batch에서 제외한다.",
    )
    parser.add_argument(
        "--include-post-ids",
        default="",
        help="쉼표로 구분한 post_id 목록. 지정하면 해당 P0 collateral row만 review batch에 포함한다.",
    )
    parser.add_argument(
        "--include-all-priorities",
        action="store_true",
        help="P0뿐 아니라 include/bucket 조건에 맞는 모든 regression priority를 batch에 포함한다.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_review_batch(
        triage_report=load_json(args.triage),
        panel_rows=load_jsonl_index(args.panel_input),
        baseline_rows=_result_rows_by_post_id(load_json(args.baseline_result)),
        after_rows=_result_rows_by_post_id(load_json(args.after_result)),
        per_bucket_limit=args.per_bucket_limit,
        buckets={bucket for bucket in args.bucket if bucket},
        include_post_ids={
            int(item.strip())
            for item in str(args.include_post_ids or "").split(",")
            if item.strip()
        } or None,
        exclude_post_ids={
            int(item.strip())
            for item in str(args.exclude_post_ids or "").split(",")
            if item.strip()
        },
        include_all_priorities=args.include_all_priorities,
        scope_label=args.scope_label,
    )
    inputs = {
        "triage": args.triage,
        "panel_input": args.panel_input,
        "baseline_result": args.baseline_result,
        "after_result": args.after_result,
    }
    write_json(args.output_json, {**report, "inputs": {key: value.as_posix() for key, value in inputs.items()}})
    write_jsonl(args.output_jsonl, report["review_rows"])
    write_markdown(args.output_md, report, inputs=inputs)
    print(json.dumps({"gate": report["gate"], "summary": report["summary"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
