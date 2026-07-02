from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Dict, List


OUT_DIR = Path("out")
GOLDEN = OUT_DIR / "golden_regression_cases_ko.csv"
CURRENT = OUT_DIR / "expert_result_20260405_173402_463239_final_corrected_ko.csv"
REPORT_JSON = OUT_DIR / "golden_regression_compare_summary_ko.json"
REPORT_CSV = OUT_DIR / "golden_regression_compare_details_ko.csv"


def _load_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def main() -> None:
    golden_rows = _load_csv(GOLDEN)
    current_rows = _load_csv(CURRENT)
    current_by_id = {row["포스트ID"]: row for row in current_rows}

    details: List[Dict[str, str]] = []
    matched = 0

    for gold in golden_rows:
        pid = gold["포스트ID"]
        cur = current_by_id.get(pid)
        if cur is None:
            details.append(
                {
                    "포스트ID": pid,
                    "비교결과": "누락",
                    "기대_판정상태": gold["최종_판정상태"],
                    "현재_판정상태": "",
                    "기대_공식제목": gold["최종_공식제목"],
                    "현재_공식제목": "",
                }
            )
            continue

        same_state = gold["최종_판정상태"] == cur["최종_판정상태"]
        same_title = gold["최종_공식제목"] == cur["최종_공식제목"]
        result = "일치" if (same_state and same_title) else "불일치"
        if result == "일치":
            matched += 1

        details.append(
            {
                "포스트ID": pid,
                "비교결과": result,
                "기대_판정상태": gold["최종_판정상태"],
                "현재_판정상태": cur["최종_판정상태"],
                "기대_공식제목": gold["최종_공식제목"],
                "현재_공식제목": cur["최종_공식제목"],
            }
        )

    with REPORT_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(details[0].keys()))
        writer.writeheader()
        writer.writerows(details)

    summary = {
        "골든셋건수": len(golden_rows),
        "비교대상건수": len(current_rows),
        "일치건수": matched,
        "불일치건수": sum(1 for row in details if row["비교결과"] == "불일치"),
        "누락건수": sum(1 for row in details if row["비교결과"] == "누락"),
        "상세CSV": str(REPORT_CSV),
    }
    REPORT_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
