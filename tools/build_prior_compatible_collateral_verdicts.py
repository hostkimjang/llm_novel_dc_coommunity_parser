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
            if current_bucket != expected_bucket:
                skip_counts["triage_bucket_changed"] += 1
                skipped_rows.append(
                    {
                        "post_id": post_id,
                        "reason": "triage_bucket_changed",
                        "source_path": str(verdict_path),
                        "source_bucket": expected_bucket,
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


def write_markdown(path: Path, state: dict[str, Any], *, verdicts_path: Path) -> None:
    summary = state["summary"]
    lines = [
        "# Loop488 P0 이전 호환 source-native verdict 상태",
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
        required=True,
        help="Prior verdict JSON and its expected current triage bucket, formatted as PATH::bucket.",
    )
    parser.add_argument("--review-id", required=True)
    parser.add_argument("--scope", required=True)
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-state-json", required=True, type=Path)
    parser.add_argument("--output-md", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    batch = load_json(args.batch)
    source_specs = [_source_spec(value) for value in args.source_verdicts]
    verdicts, state = build_prior_compatible_verdicts(
        batch=batch,
        batch_path=args.batch,
        source_specs=source_specs,
        review_id=args.review_id,
        scope=args.scope,
    )
    write_json(args.output_json, verdicts)
    write_json(args.output_state_json, state)
    write_markdown(args.output_md, state, verdicts_path=args.output_json)
    print(
        json.dumps(
            {
                "gate": state["gate"],
                "compatible_rows": state["summary"]["compatible_rows"],
                "unreviewed_current_batch_rows": state["summary"]["unreviewed_current_batch_rows"],
                "skip_counts": state["summary"]["skip_counts"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
