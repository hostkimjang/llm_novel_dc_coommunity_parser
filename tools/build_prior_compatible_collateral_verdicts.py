from __future__ import annotations

import argparse
import glob
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
    out: dict[int, dict[str, Any]] = {}
    for row in rows:
        if isinstance(row, dict) and isinstance(row.get("post_id"), int):
            out[row["post_id"]] = row
    return out


def _option_signature(option: dict[str, Any]) -> tuple[str, str]:
    return (_string(option.get("official_title")), _string(option.get("heretic_url")))


def _matching_current_option(
    verdict_row: dict[str, Any], batch_row: dict[str, Any]
) -> tuple[dict[str, Any] | None, str]:
    selected = _string(verdict_row.get("selected_option_id"))
    if selected == "HOLD":
        return {"option_id": "HOLD", "official_title": None, "heretic_url": None}, "hold"
    title = _string(verdict_row.get("selected_title"))
    url = _string(verdict_row.get("selected_url"))
    if not title and not url:
        return None, "missing_selected_title_or_url"
    matches: list[dict[str, Any]] = []
    for option in batch_row.get("blind_judge_options") or []:
        if not isinstance(option, dict):
            continue
        option_title, option_url = _option_signature(option)
        if (title and title == option_title) or (url and url == option_url):
            matches.append(option)
    if len(matches) == 1:
        return matches[0], "title_or_url_match"
    if not matches:
        return None, "selected_title_or_url_not_in_current_options"
    return None, "ambiguous_current_option_match"


def _source_spec(value: str) -> tuple[Path, str]:
    if "::" not in value:
        raise ValueError("--source-verdicts entries must use PATH::triage_bucket")
    path_text, bucket = value.rsplit("::", 1)
    path = Path(path_text)
    bucket = _string(bucket)
    if not bucket:
        raise ValueError("--source-verdicts bucket cannot be empty")
    return path, bucket


def _source_glob_specs(value: str) -> list[tuple[Path, str]]:
    if "::" not in value:
        raise ValueError("--source-verdicts-glob entries must use GLOB::triage_bucket")
    pattern, bucket = value.rsplit("::", 1)
    bucket = _string(bucket)
    if not bucket:
        raise ValueError("--source-verdicts-glob bucket cannot be empty")
    return [(Path(path), bucket) for path in sorted(glob.glob(pattern))]


def _expected_bucket_for_row(old_row: dict[str, Any], source_bucket: str) -> tuple[str, str | None]:
    if source_bucket != "*":
        return source_bucket, None
    expected_bucket = _string(old_row.get("triage_bucket"))
    if not expected_bucket:
        return "", "missing_source_triage_bucket_for_auto_bucket"
    return expected_bucket, None


def _copy_refs(refs: Any, *, verdict_path: Path, batch_path: Path, post_id: int) -> list[Any]:
    out: list[Any] = []
    if isinstance(refs, list):
        out.extend(refs)
    elif refs:
        out.append(refs)
    out.append(f"{verdict_path.as_posix()}#post_id={post_id}")
    out.append(f"{batch_path.as_posix()}#post_id={post_id}")
    return out


def build_prior_compatible_verdicts(
    *,
    batch: dict[str, Any],
    batch_path: Path,
    source_specs: list[tuple[Path, str]],
    review_id: str,
    scope: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    current_by_post_id = _review_rows_by_post_id(batch)
    compatible_rows: list[dict[str, Any]] = []
    skipped_rows: list[dict[str, Any]] = []
    seen_post_ids: set[int] = set()
    input_counts: Counter[str] = Counter()
    skip_counts: Counter[str] = Counter()

    for verdict_path, expected_bucket in source_specs:
        verdicts = load_json(verdict_path)
        verdict_rows = verdicts.get("rows")
        if not isinstance(verdict_rows, list):
            raise ValueError(f"{verdict_path} must contain rows list")
        input_counts["source_verdict_rows"] += len(verdict_rows)
        for old_row in verdict_rows:
            if not isinstance(old_row, dict):
                continue
            post_id = old_row.get("post_id")
            if not isinstance(post_id, int):
                skip_counts["invalid_post_id"] += 1
                skipped_rows.append({"post_id": post_id, "reason": "invalid_post_id", "source_path": str(verdict_path)})
                continue
            current = current_by_post_id.get(post_id)
            if current is None:
                skip_counts["post_id_not_in_current_batch"] += 1
                skipped_rows.append({"post_id": post_id, "reason": "post_id_not_in_current_batch", "source_path": str(verdict_path)})
                continue
            input_counts["overlap_rows"] += 1
            current_bucket = _string(current.get("triage_bucket"))
            expected_bucket_for_row, auto_bucket_skip_reason = _expected_bucket_for_row(old_row, expected_bucket)
            if auto_bucket_skip_reason:
                skip_counts[auto_bucket_skip_reason] += 1
                skipped_rows.append(
                    {
                        "post_id": post_id,
                        "reason": auto_bucket_skip_reason,
                        "source_path": str(verdict_path),
                        "current_bucket": current_bucket,
                    }
                )
                continue
            if current_bucket != expected_bucket_for_row:
                skip_counts["triage_bucket_changed"] += 1
                skipped_rows.append(
                    {
                        "post_id": post_id,
                        "reason": "triage_bucket_changed",
                        "source_path": str(verdict_path),
                        "source_bucket": expected_bucket_for_row,
                        "current_bucket": current_bucket,
                    }
                )
                continue
            if post_id in seen_post_ids:
                skip_counts["duplicate_compatible_post_id"] += 1
                skipped_rows.append({"post_id": post_id, "reason": "duplicate_compatible_post_id", "source_path": str(verdict_path)})
                continue
            option, match_reason = _matching_current_option(old_row, current)
            if option is None:
                skip_counts[match_reason] += 1
                skipped_rows.append(
                    {
                        "post_id": post_id,
                        "reason": match_reason,
                        "source_path": str(verdict_path),
                        "source_bucket": expected_bucket,
                        "current_bucket": current_bucket,
                        "selected_option_id": old_row.get("selected_option_id"),
                        "selected_title": old_row.get("selected_title"),
                        "selected_url": old_row.get("selected_url"),
                    }
                )
                continue
            copied = dict(old_row)
            copied["triage_bucket"] = current_bucket
            copied["selected_option_id"] = option["option_id"]
            if option["option_id"] == "HOLD":
                copied["selected_title"] = None
                copied["selected_url"] = None
            else:
                copied["selected_title"] = option.get("official_title")
                copied["selected_url"] = option.get("heretic_url")
            copied["carry_forward_kind"] = "prior_source_native_verdict_compatible"
            copied["carry_forward_match_reason"] = match_reason
            copied["carry_forward_source_path"] = str(verdict_path)
            copied["evidence_refs"] = _copy_refs(
                old_row.get("evidence_refs"),
                verdict_path=verdict_path,
                batch_path=batch_path,
                post_id=post_id,
            )
            compatible_rows.append(copied)
            seen_post_ids.add(post_id)
            input_counts["compatible_rows"] += 1

    payload = {
        "review_id": review_id,
        "scope": scope,
        "source_batch": str(batch_path),
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "compatibility_policy": {
            "requires_same_post_id": True,
            "requires_same_triage_bucket": True,
            "requires_current_option_title_or_url_match": True,
            "allows_option_id_remap": True,
            "hold_is_compatible_without_title_url": True,
        },
        "summary": {
            "current_batch_rows": len(current_by_post_id),
            "source_verdict_rows": input_counts["source_verdict_rows"],
            "overlap_rows": input_counts["overlap_rows"],
            "compatible_rows": input_counts["compatible_rows"],
            "unreviewed_current_batch_rows": max(len(current_by_post_id) - input_counts["compatible_rows"], 0),
            "skip_counts": dict(skip_counts),
        },
        "rows": compatible_rows,
    }
    state = {
        "report_type": "prior_compatible_collateral_verdicts_state",
        "review_id": review_id,
        "scope": scope,
        "generated_at": payload["generated_at"],
        "gate": "REVIEW-LOCKED",
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "summary": payload["summary"],
        "source_verdicts": [
            {"path": str(path), "expected_triage_bucket": bucket}
            for path, bucket in source_specs
        ],
        "skipped_rows": skipped_rows,
    }
    return payload, state


def _covered_post_ids(
    compatible_verdicts: dict[str, Any],
    additional_covered_verdicts: list[dict[str, Any]] | None = None,
) -> tuple[set[int], int]:
    covered_post_ids = {
        row.get("post_id")
        for row in compatible_verdicts.get("rows") or []
        if isinstance(row, dict) and isinstance(row.get("post_id"), int)
    }
    additional_covered_rows = 0
    for verdicts in additional_covered_verdicts or []:
        for row in verdicts.get("rows") or []:
            if isinstance(row, dict) and isinstance(row.get("post_id"), int):
                additional_covered_rows += 1
                covered_post_ids.add(row["post_id"])
    return covered_post_ids, additional_covered_rows


def build_unreviewed_batch(
    batch: dict[str, Any],
    compatible_verdicts: dict[str, Any],
    state: dict[str, Any],
    additional_covered_verdicts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    covered_post_ids, additional_covered_rows = _covered_post_ids(
        compatible_verdicts,
        additional_covered_verdicts,
    )
    review_rows = [
        row
        for row in batch.get("review_rows") or []
        if isinstance(row, dict) and isinstance(row.get("post_id"), int) and row["post_id"] not in covered_post_ids
    ]
    bucket_counts = Counter(_string(row.get("triage_bucket")) for row in review_rows)
    status_counts = Counter(_string(row.get("collateral_status")) for row in review_rows)
    image_rows = sum(
        1
        for row in review_rows
        if isinstance(row.get("source_native_packet"), dict)
        and int(row["source_native_packet"].get("image_count") or 0) > 0
    )
    out = {
        "report_type": "collateral_p0_unreviewed_source_review_batch",
        "source_report_type": batch.get("report_type"),
        "scope_label": "full375 P0 prior-incompatible residual",
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "gate": "REVIEW-LOCKED",
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "source_batch": state.get("source_batch") or batch.get("scope_label"),
        "prior_compatible_review_id": state.get("review_id"),
        "prior_compatible_summary": state.get("summary"),
        "summary": {
            "source_review_rows": len(batch.get("review_rows") or []),
            "prior_compatible_rows": len(compatible_verdicts.get("rows") or []),
            "additional_covered_rows": additional_covered_rows,
            "covered_post_ids": len(covered_post_ids),
            "unreviewed_rows": len(review_rows),
            "counts_by_bucket": dict(bucket_counts),
            "counts_by_collateral_status": dict(status_counts),
            "image_rows": image_rows,
            "text_only_rows": len(review_rows) - image_rows,
        },
        "instructions_ko": [
            "이 배치는 과거 source-native verdict와 title/url 기준으로 호환되지 않은 현재 P0 행만 포함한다.",
            "blind judge 입력에는 source_native_packet과 blind_judge_options만 제공한다.",
            "comparison_private_not_for_blind_judge는 전후 diff 검수용이며 blind judge에는 제공하지 않는다.",
            "이미지 행은 VLM/OCR 또는 native/browser 확인 없이 텍스트만으로 Strong evidence로 올리지 않는다.",
            "정답 판정 전까지 semantic_quality=REVIEW-LOCKED, full_scan_approval=false를 유지한다.",
        ],
        "review_rows": review_rows,
    }
    return out


def build_unreviewed_placeholder_verdicts(
    batch: dict[str, Any],
    compatible_verdicts: dict[str, Any],
    state: dict[str, Any],
    *,
    review_id: str,
    scope: str,
    batch_path: Path,
    additional_covered_verdicts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    covered_post_ids, additional_covered_rows = _covered_post_ids(
        compatible_verdicts,
        additional_covered_verdicts,
    )
    rows: list[dict[str, Any]] = []
    for row in batch.get("review_rows") or []:
        if not isinstance(row, dict):
            continue
        post_id = row.get("post_id")
        if not isinstance(post_id, int) or post_id in covered_post_ids:
            continue
        bucket = _string(row.get("triage_bucket")) or "unknown"
        rows.append(
            {
                "post_id": post_id,
                "triage_bucket": bucket,
                "selected_option_id": "HOLD",
                "selected_title": None,
                "selected_url": None,
                "review_label": "INFO_MISSING",
                "source_native_verdict": "current_regression_row_without_compatible_prior_verdict",
                "evidence_grade": "Missing",
                "action": [
                    "source_native_or_blind_review_required",
                    f"p0_{bucket}_review_required",
                ],
                "rationale_ko": (
                    "현재 full375 collateral P0 회귀 행이지만 prior source-native verdict가 "
                    "동일 post_id, 동일 triage_bucket, 현재 후보 title/url 조건을 통과하지 못했다. "
                    "정답성 확정 전까지 별도 blind/source-native 검토가 필요하다."
                ),
                "evidence_refs": [
                    f"{batch_path.as_posix()}#post_id={post_id}",
                    f"{state.get('review_id')}#unreviewed_current_batch_row",
                ],
            }
        )
    return {
        "review_id": review_id,
        "scope": scope,
        "source_batch": str(batch_path),
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "gate": "REVIEW-LOCKED",
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "summary": {
            "source_review_rows": len(batch.get("review_rows") or []),
            "prior_compatible_rows": len(
                {
                    row.get("post_id")
                    for row in compatible_verdicts.get("rows") or []
                    if isinstance(row, dict) and isinstance(row.get("post_id"), int)
                }
            ),
            "additional_covered_rows": additional_covered_rows,
            "covered_post_ids": len(covered_post_ids),
            "placeholder_rows": len(rows),
            "counts_by_bucket": dict(Counter(row["triage_bucket"] for row in rows)),
        },
        "rows": rows,
    }


def write_unreviewed_markdown(path: Path, batch: dict[str, Any]) -> None:
    summary = batch["summary"]
    lines = [
        "# full375 P0 이전 비호환 잔여 검토 배치",
        "",
        f"- gate: `{batch['gate']}`",
        f"- semantic_quality: `{batch['semantic_quality']}`",
        f"- full_scan_approval: `{str(batch['full_scan_approval']).lower()}`",
        f"- source review rows: `{summary['source_review_rows']}`",
        f"- prior-compatible rows: `{summary['prior_compatible_rows']}`",
        f"- additional covered rows: `{summary.get('additional_covered_rows', 0)}`",
        f"- covered post ids: `{summary.get('covered_post_ids', summary['prior_compatible_rows'])}`",
        f"- unreviewed rows: `{summary['unreviewed_rows']}`",
        f"- image rows: `{summary['image_rows']}`",
        f"- text-only rows: `{summary['text_only_rows']}`",
        "",
        "## 버킷",
        "",
    ]
    for bucket, count in sorted((summary.get("counts_by_bucket") or {}).items()):
        lines.append(f"- {bucket}: `{count}`")
    lines.extend(["", "## 행 목록", ""])
    for row in batch.get("review_rows") or []:
        source = row.get("source_native_packet") or {}
        options = ", ".join(
            f"{option.get('option_id')}={option.get('official_title')}"
            for option in row.get("blind_judge_options") or []
            if isinstance(option, dict)
        )
        lines.append(
            f"- `{row.get('post_id')}` / `{row.get('triage_bucket')}` / image `{source.get('image_count', 0)}` / {source.get('post_title')} / options: {options}"
        )
    lines.extend(
        [
            "",
            "## 해석",
            "",
            "이 배치는 잔여 검토 입력이며 approval이 아니다.",
            f"잔여 `{summary['unreviewed_rows']}`건 verdict가 채워지고 full375 collateral gate에 반영되기 전까지 full375 collateral은 `NO-GO`다.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_markdown(path: Path, state: dict[str, Any], *, verdicts_path: Path) -> None:
    summary = state["summary"]
    lines = [
        "# full375 P0 이전 호환 source-native verdict 상태",
        "",
        f"- gate: `{state['gate']}`",
        f"- semantic_quality: `{state['semantic_quality']}`",
        f"- full_scan_approval: `{str(state['full_scan_approval']).lower()}`",
        f"- current batch rows: `{summary['current_batch_rows']}`",
        f"- compatible rows: `{summary['compatible_rows']}`",
        f"- unreviewed current batch rows: `{summary['unreviewed_current_batch_rows']}`",
        f"- compatible verdicts: `{verdicts_path.as_posix()}`",
        "",
        "## 제외 사유 집계",
        "",
    ]
    for reason, count in sorted((summary.get("skip_counts") or {}).items()):
        lines.append(f"- {reason}: `{count}`")
    unreviewed = state.get("unreviewed_batch")
    if isinstance(unreviewed, dict):
        unreviewed_summary = unreviewed.get("summary") or {}
        artifacts = unreviewed.get("artifacts") or {}
        lines.extend(
            [
                "",
                "## 잔여 배치",
                "",
                f"- gate: `{unreviewed.get('gate')}`",
                f"- unreviewed rows: `{unreviewed_summary.get('unreviewed_rows')}`",
                f"- image rows: `{unreviewed_summary.get('image_rows')}`",
                f"- text-only rows: `{unreviewed_summary.get('text_only_rows')}`",
                f"- json: `{artifacts.get('json')}`",
                f"- jsonl: `{artifacts.get('jsonl')}`",
                f"- markdown: `{artifacts.get('markdown')}`",
            ]
        )
    placeholders = state.get("unreviewed_placeholder_verdicts")
    if isinstance(placeholders, dict):
        placeholder_summary = placeholders.get("summary") or {}
        lines.extend(
            [
                "",
                "## 미검토 placeholder verdict",
                "",
                f"- gate: `{placeholders.get('gate')}`",
                f"- placeholder rows: `{placeholder_summary.get('placeholder_rows')}`",
                f"- json: `{placeholders.get('artifact')}`",
            ]
        )
    lines.extend(
        [
            "",
            "## 해석",
            "",
            "이 산출물은 과거 source-native verdict를 현재 P0 배치에 그대로 승인한 것이 아니다.",
            "동일 post_id, 동일 triage_bucket, 현재 후보의 title/url 일치를 만족한 행만 재사용 후보로 분리했다.",
            "남은 행은 신규 blind/source-native 검토가 필요하며 full375 collateral gate는 계속 NO-GO다.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", required=True, type=Path)
    parser.add_argument(
        "--source-verdicts",
        action="append",
        default=[],
        help="Prior verdict JSON and its expected current triage bucket, formatted as PATH::bucket.",
    )
    parser.add_argument(
        "--source-verdicts-glob",
        action="append",
        default=[],
        help="Prior verdict JSON glob and expected current triage bucket, formatted as GLOB::bucket.",
    )
    parser.add_argument("--review-id", required=True)
    parser.add_argument("--scope", required=True)
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-state-json", required=True, type=Path)
    parser.add_argument("--output-md", required=True, type=Path)
    parser.add_argument("--output-unreviewed-batch-json", type=Path)
    parser.add_argument("--output-unreviewed-batch-jsonl", type=Path)
    parser.add_argument("--output-unreviewed-batch-md", type=Path)
    parser.add_argument("--output-unreviewed-verdicts-json", type=Path)
    parser.add_argument("--additional-covered-verdicts-json", nargs="*", type=Path, default=[])
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    batch = load_json(args.batch)
    source_specs = [_source_spec(value) for value in args.source_verdicts]
    for value in args.source_verdicts_glob:
        source_specs.extend(_source_glob_specs(value))
    if not source_specs:
        raise ValueError("At least one --source-verdicts or --source-verdicts-glob entry is required")
    verdicts, state = build_prior_compatible_verdicts(
        batch=batch,
        batch_path=args.batch,
        source_specs=source_specs,
        review_id=args.review_id,
        scope=args.scope,
    )
    write_json(args.output_json, verdicts)
    additional_covered_verdicts = [load_json(path) for path in args.additional_covered_verdicts_json]
    if args.output_unreviewed_batch_json or args.output_unreviewed_batch_jsonl or args.output_unreviewed_batch_md:
        unreviewed_batch = build_unreviewed_batch(
            batch,
            verdicts,
            state,
            additional_covered_verdicts,
        )
        state["unreviewed_batch"] = {
            "gate": unreviewed_batch["gate"],
            "summary": unreviewed_batch["summary"],
            "artifacts": {
                "json": str(args.output_unreviewed_batch_json) if args.output_unreviewed_batch_json else None,
                "jsonl": str(args.output_unreviewed_batch_jsonl) if args.output_unreviewed_batch_jsonl else None,
                "markdown": str(args.output_unreviewed_batch_md) if args.output_unreviewed_batch_md else None,
            },
        }
        if args.output_unreviewed_batch_json:
            write_json(args.output_unreviewed_batch_json, unreviewed_batch)
        if args.output_unreviewed_batch_jsonl:
            write_jsonl(args.output_unreviewed_batch_jsonl, unreviewed_batch["review_rows"])
        if args.output_unreviewed_batch_md:
            write_unreviewed_markdown(args.output_unreviewed_batch_md, unreviewed_batch)
    if args.output_unreviewed_verdicts_json:
        unreviewed_verdicts = build_unreviewed_placeholder_verdicts(
            batch,
            verdicts,
            state,
            review_id=f"{args.review_id}_unreviewed_placeholders",
            scope=f"{args.scope} unreviewed placeholders",
            batch_path=args.batch,
            additional_covered_verdicts=additional_covered_verdicts,
        )
        state["unreviewed_placeholder_verdicts"] = {
            "gate": unreviewed_verdicts["gate"],
            "summary": unreviewed_verdicts["summary"],
            "artifact": str(args.output_unreviewed_verdicts_json),
        }
        write_json(args.output_unreviewed_verdicts_json, unreviewed_verdicts)
    write_json(args.output_state_json, state)
    write_markdown(args.output_md, state, verdicts_path=args.output_json)
    print(
        json.dumps(
            {
                "gate": state["gate"],
                "compatible_rows": state["summary"]["compatible_rows"],
                "unreviewed_current_batch_rows": state["summary"]["unreviewed_current_batch_rows"],
                "skip_counts": state["summary"]["skip_counts"],
                "unreviewed_batch_written": bool(
                    args.output_unreviewed_batch_json
                    or args.output_unreviewed_batch_jsonl
                    or args.output_unreviewed_batch_md
                ),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
