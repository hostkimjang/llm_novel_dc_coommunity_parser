from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _post_id(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _batch_post_ids(batch: dict[str, Any]) -> set[int]:
    rows = batch.get("review_rows")
    if not isinstance(rows, list):
        raise ValueError("batch JSON must contain review_rows list")
    out: set[int] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        post_id = _post_id(row.get("post_id"))
        if post_id is not None:
            out.add(post_id)
    return out


def filter_verdicts_to_batch(
    *,
    batch: dict[str, Any],
    verdicts_list: list[dict[str, Any]],
    source_paths: list[Path],
    review_id: str,
    scope: str,
) -> dict[str, Any]:
    allowed = _batch_post_ids(batch)
    kept_rows: list[dict[str, Any]] = []
    dropped_rows: list[dict[str, Any]] = []
    duplicate_post_ids: list[int] = []
    seen: set[int] = set()
    source_summaries: list[dict[str, Any]] = []

    for verdicts, source_path in zip(verdicts_list, source_paths, strict=True):
        rows = verdicts.get("rows")
        if not isinstance(rows, list):
            raise ValueError(f"verdicts JSON must contain rows list: {source_path}")
        kept = 0
        dropped = 0
        for row in rows:
            if not isinstance(row, dict):
                continue
            post_id = _post_id(row.get("post_id"))
            if post_id is None:
                dropped += 1
                dropped_rows.append(
                    {
                        "post_id": row.get("post_id"),
                        "drop_reason": "invalid_post_id",
                        "source_path": source_path.as_posix(),
                    }
                )
                continue
            if post_id not in allowed:
                dropped += 1
                dropped_rows.append(
                    {
                        "post_id": post_id,
                        "drop_reason": "post_id_not_in_current_batch",
                        "source_path": source_path.as_posix(),
                    }
                )
                continue
            if post_id in seen:
                duplicate_post_ids.append(post_id)
                dropped += 1
                dropped_rows.append(
                    {
                        "post_id": post_id,
                        "drop_reason": "duplicate_post_id_after_filter",
                        "source_path": source_path.as_posix(),
                    }
                )
                continue
            copied = dict(row)
            copied.setdefault("evidence_refs", [])
            copied["evidence_refs"] = [
                *(copied.get("evidence_refs") or []),
                f"{source_path.as_posix()}#post_id={post_id}",
            ]
            kept_rows.append(copied)
            seen.add(post_id)
            kept += 1
        source_summaries.append(
            {
                "source_path": source_path.as_posix(),
                "source_review_id": verdicts.get("review_id"),
                "source_rows": len(rows),
                "kept_rows": kept,
                "dropped_rows": dropped,
            }
        )

    missing_post_ids = sorted(allowed - seen)
    validation_issues: list[dict[str, Any]] = []
    if duplicate_post_ids:
        validation_issues.append(
            {
                "code": "duplicate_post_id_after_filter",
                "post_ids": sorted(set(duplicate_post_ids)),
            }
        )

    return {
        "review_id": review_id,
        "scope": scope,
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "source_batch": batch.get("inputs", {}).get("triage") or batch.get("scope_label"),
        "filter_policy": "keep_only_verdict_rows_whose_post_id_exists_in_current_batch",
        "gate": "NO-GO" if validation_issues else "REVIEW-LOCKED",
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "summary": {
            "batch_post_ids": len(allowed),
            "kept_rows": len(kept_rows),
            "dropped_rows": len(dropped_rows),
            "missing_batch_post_ids": len(missing_post_ids),
            "validation_issue_count": len(validation_issues),
        },
        "source_verdicts": source_summaries,
        "dropped_rows": dropped_rows,
        "missing_post_ids": missing_post_ids,
        "validation_issues": validation_issues,
        "rows": kept_rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Filter carried-forward collateral source-native verdicts to the current review batch."
    )
    parser.add_argument("--batch", required=True, type=Path)
    parser.add_argument("--verdicts", required=True, type=Path, nargs="+")
    parser.add_argument("--review-id", required=True)
    parser.add_argument("--scope", required=True)
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--fail-on-validation-issue", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    verdicts_list = [load_json(path) for path in args.verdicts]
    report = filter_verdicts_to_batch(
        batch=load_json(args.batch),
        verdicts_list=verdicts_list,
        source_paths=list(args.verdicts),
        review_id=args.review_id,
        scope=args.scope,
    )
    write_json(args.output_json, report)
    print(json.dumps({"gate": report["gate"], "summary": report["summary"]}, ensure_ascii=False, indent=2))
    if args.fail_on_validation_issue and report["summary"]["validation_issue_count"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
