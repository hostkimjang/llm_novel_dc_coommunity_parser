from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _iter_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="ignore") as fp:
        for line_no, line in enumerate(fp, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            if isinstance(row, dict):
                row["_line_no"] = line_no
                rows.append(row)
    return rows


def _post_id_from_result(row: dict[str, Any]) -> int | None:
    try:
        return int(row.get("post_id"))
    except Exception:
        return None


def _post_id_from_checkpoint(row: dict[str, Any]) -> int | None:
    result = row.get("result") if isinstance(row.get("result"), dict) else {}
    try:
        return int(row.get("post_id") or result.get("post_id"))
    except Exception:
        return None


def _post_id_from_pending(row: dict[str, Any]) -> int | None:
    result = row.get("result") if isinstance(row.get("result"), dict) else {}
    try:
        return int(row.get("post_id") or result.get("post_id"))
    except Exception:
        return None


def recover(
    *,
    result_path: Path,
    checkpoint_path: Path,
    pending_snapshot_path: Path,
    manifest_path: Path | None,
    recovered_output_path: Path,
    summary_output_path: Path,
) -> dict[str, Any]:
    final_rows = _load_json(result_path) if result_path.exists() else []
    if not isinstance(final_rows, list):
        raise ValueError(f"result JSON must be a list: {result_path}")

    checkpoint_rows = _iter_jsonl(checkpoint_path)
    completed_rows = [row for row in checkpoint_rows if row.get("status") == "completed"]
    failed_rows = [row for row in checkpoint_rows if row.get("status") == "failed"]

    pending_rows: list[dict[str, Any]] = []
    if pending_snapshot_path.exists():
        pending_payload = _load_json(pending_snapshot_path)
        if isinstance(pending_payload, list):
            pending_rows = [row for row in pending_payload if isinstance(row, dict)]

    completed_rows_sorted = sorted(
        completed_rows,
        key=lambda row: (
            int(row.get("global_idx") or 0),
            int(row.get("_line_no") or 0),
        ),
    )
    recovered_rows = [
        row["result"]
        for row in completed_rows_sorted
        if isinstance(row.get("result"), dict)
    ]

    final_ids = {_post_id_from_result(row) for row in final_rows}
    checkpoint_ids = {_post_id_from_checkpoint(row) for row in completed_rows}
    pending_ids = {_post_id_from_pending(row) for row in pending_rows}
    final_ids.discard(None)
    checkpoint_ids.discard(None)
    pending_ids.discard(None)

    missing_from_final = sorted(int(pid) for pid in checkpoint_ids - final_ids)
    pending_not_in_final = sorted(int(pid) for pid in pending_ids - final_ids)
    checkpoint_missing_not_pending = sorted(int(pid) for pid in (checkpoint_ids - final_ids) - pending_ids)
    extra_in_final = sorted(int(pid) for pid in final_ids - checkpoint_ids)
    pending_not_in_checkpoint = sorted(int(pid) for pid in pending_ids - checkpoint_ids)

    manifest = _load_json(manifest_path) if manifest_path and manifest_path.exists() else {}
    recovered_output_path.parent.mkdir(parents=True, exist_ok=True)
    recovered_output_path.write_text(
        json.dumps(recovered_rows, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    summary = {
        "run_id": manifest.get("run_id"),
        "source_result_path": str(result_path),
        "source_checkpoint_path": str(checkpoint_path),
        "source_pending_snapshot_path": str(pending_snapshot_path),
        "recovered_output_path": str(recovered_output_path),
        "final_result_rows": len(final_rows),
        "checkpoint_rows": len(checkpoint_rows),
        "checkpoint_completed_rows": len(completed_rows),
        "checkpoint_failed_rows": len(failed_rows),
        "pending_snapshot_rows": len(pending_rows),
        "recovered_rows": len(recovered_rows),
        "manifest": {
            "input_post_count": manifest.get("input_post_count"),
            "completed_count": manifest.get("completed_count"),
            "flushed_count": manifest.get("flushed_count"),
            "pending_count": manifest.get("pending_count"),
            "failed_count": manifest.get("failed_count"),
            "next_save_idx": manifest.get("next_save_idx"),
        },
        "missing_from_final_post_ids": missing_from_final,
        "pending_not_in_final_post_ids": pending_not_in_final,
        "checkpoint_missing_not_pending_post_ids": checkpoint_missing_not_pending,
        "pending_not_in_checkpoint_post_ids": pending_not_in_checkpoint,
        "extra_in_final_not_checkpoint_post_ids": extra_in_final,
        "integrity_classification": (
            "recoverable_pending_flush_gap"
            if missing_from_final and missing_from_final == pending_not_in_final and not checkpoint_missing_not_pending
            else "requires_manual_review"
        ),
        "recovery_safe_to_use_as_completed_subset": bool(
            recovered_rows
            and not failed_rows
            and not checkpoint_missing_not_pending
            and not pending_not_in_checkpoint
            and not extra_in_final
        ),
        "large_run_complete": bool(
            manifest.get("input_post_count")
            and len(recovered_rows) >= int(manifest.get("input_post_count") or 0)
            and not pending_rows
        ),
    }
    summary_output_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Recover completed expert_main rows from checkpoint JSONL without overwriting the original result.",
    )
    parser.add_argument("--result", required=True, type=Path)
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument("--pending-snapshot", required=True, type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--recovered-output", required=True, type=Path)
    parser.add_argument("--summary-output", required=True, type=Path)
    args = parser.parse_args()

    summary = recover(
        result_path=args.result,
        checkpoint_path=args.checkpoint,
        pending_snapshot_path=args.pending_snapshot,
        manifest_path=args.manifest,
        recovered_output_path=args.recovered_output,
        summary_output_path=args.summary_output,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
