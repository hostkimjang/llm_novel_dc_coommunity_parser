from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _post_id(row: dict[str, Any]) -> str:
    value = row.get("post_id")
    text = "" if value is None else str(value).strip()
    if not text:
        raise ValueError("row is missing post_id")
    return text


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line_no, line in enumerate(handle, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"expected object at {path}:{line_no}")
            rows.append(row)
    return rows


def _object_rows(payload: Any, *, label: str) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise ValueError(f"{label} must be a JSON array")
    rows: list[dict[str, Any]] = []
    for index, row in enumerate(payload, 1):
        if not isinstance(row, dict):
            raise ValueError(f"{label} row {index} must be an object")
        rows.append(row)
    return rows


def _duplicates(ids: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for post_id in ids:
        if post_id in seen:
            duplicates.add(post_id)
        seen.add(post_id)
    return sorted(duplicates, key=lambda value: (len(value), value))


def build_residual(
    source_rows: list[dict[str, Any]],
    recovered_rows: list[dict[str, Any]],
    *,
    expected_source_count: int | None = None,
    expected_recovered_count: int | None = None,
    expected_residual_count: int | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source_ids = [_post_id(row) for row in source_rows]
    recovered_ids = [_post_id(row) for row in recovered_rows]
    source_duplicates = _duplicates(source_ids)
    recovered_duplicates = _duplicates(recovered_ids)
    if source_duplicates:
        raise ValueError(f"source has duplicate post_id values: {source_duplicates}")
    if recovered_duplicates:
        raise ValueError(f"recovered subset has duplicate post_id values: {recovered_duplicates}")

    source_id_set = set(source_ids)
    recovered_id_set = set(recovered_ids)
    recovered_not_in_source = sorted(
        recovered_id_set - source_id_set,
        key=lambda value: (len(value), value),
    )
    if recovered_not_in_source:
        raise ValueError(f"recovered post_id values are absent from source: {recovered_not_in_source}")

    residual_rows = [row for row in source_rows if _post_id(row) not in recovered_id_set]
    residual_ids = [_post_id(row) for row in residual_rows]
    count_checks = {
        "source": expected_source_count is None or len(source_rows) == expected_source_count,
        "recovered": expected_recovered_count is None or len(recovered_rows) == expected_recovered_count,
        "residual": expected_residual_count is None or len(residual_rows) == expected_residual_count,
        "partition": len(recovered_rows) + len(residual_rows) == len(source_rows),
    }
    if not all(count_checks.values()):
        raise ValueError(
            "count contract failed: "
            + json.dumps(
                {
                    "actual": {
                        "source": len(source_rows),
                        "recovered": len(recovered_rows),
                        "residual": len(residual_rows),
                    },
                    "expected": {
                        "source": expected_source_count,
                        "recovered": expected_recovered_count,
                        "residual": expected_residual_count,
                    },
                    "checks": count_checks,
                },
                ensure_ascii=False,
            )
        )

    source_positions = {post_id: index for index, post_id in enumerate(source_ids, 1)}
    residual_positions = [source_positions[post_id] for post_id in residual_ids]
    order_preserved = residual_positions == sorted(residual_positions)
    if not order_preserved:
        raise ValueError("residual source order is not preserved")

    manifest = {
        "report_type": "interrupted_run_residual_input_manifest",
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "gate": "GO",
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "counts": {
            "source_rows": len(source_rows),
            "source_unique_post_ids": len(source_id_set),
            "recovered_rows": len(recovered_rows),
            "recovered_unique_post_ids": len(recovered_id_set),
            "residual_rows": len(residual_rows),
            "residual_unique_post_ids": len(set(residual_ids)),
        },
        "integrity": {
            "source_duplicate_post_ids": source_duplicates,
            "recovered_duplicate_post_ids": recovered_duplicates,
            "recovered_not_in_source_post_ids": recovered_not_in_source,
            "residual_duplicate_post_ids": _duplicates(residual_ids),
            "recovered_residual_overlap_post_ids": sorted(
                recovered_id_set.intersection(residual_ids),
                key=lambda value: (len(value), value),
            ),
            "partition_missing_post_ids": sorted(
                source_id_set - recovered_id_set - set(residual_ids),
                key=lambda value: (len(value), value),
            ),
            "partition_extra_post_ids": sorted(
                (recovered_id_set | set(residual_ids)) - source_id_set,
                key=lambda value: (len(value), value),
            ),
            "original_order_preserved": order_preserved,
            "count_checks": count_checks,
        },
        "expected_counts": {
            "source_rows": expected_source_count,
            "recovered_rows": expected_recovered_count,
            "residual_rows": expected_residual_count,
        },
        "source_post_ids": source_ids,
        "recovered_post_ids_in_source_order": [
            post_id for post_id in source_ids if post_id in recovered_id_set
        ],
        "residual_post_ids_in_source_order": residual_ids,
        "approval_boundary": {
            "input_generation_is_not_runtime_approval": True,
            "recovered_and_residual_may_merge_only_under_identical_runtime_contract": True,
        },
    }
    return residual_rows, manifest


def _write_jsonl_exclusive(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_json_exclusive(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build an immutable original-order residual input after checkpoint recovery.",
    )
    parser.add_argument("--source-jsonl", required=True, type=Path)
    parser.add_argument("--recovered-json", required=True, type=Path)
    parser.add_argument("--output-jsonl", required=True, type=Path)
    parser.add_argument("--manifest-json", required=True, type=Path)
    parser.add_argument("--reference-plan", type=Path)
    parser.add_argument("--adjudicated-baseline", type=Path)
    parser.add_argument("--expected-source-count", type=int)
    parser.add_argument("--expected-recovered-count", type=int)
    parser.add_argument("--expected-residual-count", type=int)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows, manifest = build_residual(
        _load_jsonl(args.source_jsonl),
        _object_rows(_load_json(args.recovered_json), label="recovered subset"),
        expected_source_count=args.expected_source_count,
        expected_recovered_count=args.expected_recovered_count,
        expected_residual_count=args.expected_residual_count,
    )
    manifest["artifacts"] = {
        "source_jsonl": str(args.source_jsonl),
        "source_jsonl_sha256": _sha256(args.source_jsonl),
        "recovered_json": str(args.recovered_json),
        "recovered_json_sha256": _sha256(args.recovered_json),
        "output_jsonl": str(args.output_jsonl),
        "manifest_json": str(args.manifest_json),
    }
    if args.reference_plan:
        manifest["artifacts"].update(
            {
                "reference_plan": str(args.reference_plan),
                "reference_plan_sha256": _sha256(args.reference_plan),
            }
        )
    if args.adjudicated_baseline:
        manifest["artifacts"].update(
            {
                "adjudicated_baseline": str(args.adjudicated_baseline),
                "adjudicated_baseline_sha256": _sha256(args.adjudicated_baseline),
            }
        )

    _write_jsonl_exclusive(args.output_jsonl, rows)
    manifest["artifacts"]["output_jsonl_sha256"] = _sha256(args.output_jsonl)
    _write_json_exclusive(args.manifest_json, manifest)
    print(f"WROTE {args.output_jsonl} rows={len(rows)} gate={manifest['gate']}")
    print(f"WROTE {args.manifest_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
