from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List


OUT_DIR = Path("out")
INPUT_JSON = OUT_DIR / "expert_result_20260405_173402_463239.json"
INPUT_CHANGES = OUT_DIR / "expert_result_20260405_173402_463239_final_changes_ko.csv"
OUTPUT_JSONL = OUT_DIR / "golden_regression_cases_ko.jsonl"
OUTPUT_CSV = OUT_DIR / "golden_regression_cases_ko.csv"
OUTPUT_SUMMARY = OUT_DIR / "golden_regression_cases_summary_ko.json"


def _load_changes() -> List[Dict[str, str]]:
    with INPUT_CHANGES.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _load_items() -> Dict[str, Dict[str, Any]]:
    rows = json.loads(INPUT_JSON.read_text(encoding="utf-8"))
    return {str(row["post_id"]): row for row in rows}


def main() -> None:
    changes = _load_changes()
    items = _load_items()

    golden_rows: List[Dict[str, Any]] = []
    for change in changes:
        post_id = change["포스트ID"]
        item = items[post_id]
        golden_rows.append(
            {
                "포스트ID": int(post_id),
                "제목": item.get("title") or "",
                "본문": item.get("content") or [],
                "댓글": item.get("comments") or [],
                "원본_판정상태": change["원본_판정상태"],
                "원본_공식제목": change["원본_공식제목"],
                "최종_판정상태": change["최종_판정상태"],
                "최종_공식제목": change["최종_공식제목"],
                "감사_판정": change["감사_판정"],
                "감사_권장조치": change["감사_권장조치"],
                "최종_정정사유": change["최종_정정사유"],
            }
        )

    with OUTPUT_JSONL.open("w", encoding="utf-8", newline="\n") as f:
        for row in golden_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    with OUTPUT_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "포스트ID",
                "제목",
                "원본_판정상태",
                "원본_공식제목",
                "최종_판정상태",
                "최종_공식제목",
                "감사_판정",
                "감사_권장조치",
                "최종_정정사유",
            ],
        )
        writer.writeheader()
        for row in golden_rows:
            writer.writerow(
                {
                    "포스트ID": row["포스트ID"],
                    "제목": row["제목"],
                    "원본_판정상태": row["원본_판정상태"],
                    "원본_공식제목": row["원본_공식제목"],
                    "최종_판정상태": row["최종_판정상태"],
                    "최종_공식제목": row["최종_공식제목"],
                    "감사_판정": row["감사_판정"],
                    "감사_권장조치": row["감사_권장조치"],
                    "최종_정정사유": row["최종_정정사유"],
                }
            )

    summary = {
        "건수": len(golden_rows),
        "jsonl": str(OUTPUT_JSONL),
        "csv": str(OUTPUT_CSV),
    }
    OUTPUT_SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
