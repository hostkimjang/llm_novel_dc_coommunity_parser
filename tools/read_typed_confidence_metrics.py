"""No-write operator reader for typed confidence-report JSONL."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from llm_batch.grounding.confidence_report import read_jsonl_rows, read_policy_independent_metrics


def main() -> int:
    parser = argparse.ArgumentParser(description="Typed confidence metrics reader (no-write)")
    parser.add_argument("--input", required=True, help="evaluation JSONL; never modified")
    parser.add_argument("--artifact-root", help="required root for FROZEN_ACTUAL artifact verification")
    parser.add_argument("--ece-bins", type=int, default=10)
    args = parser.parse_args()
    try:
        path = Path(args.input)
        if not path.is_file():
            raise ValueError("input must be a regular file")
        result = read_policy_independent_metrics(
            read_jsonl_rows(str(path)),
            ece_bins=args.ece_bins,
            artifact_root=args.artifact_root,
        )
        result["runtime_started"] = False
        result["writes_performed"] = False
        result["public_result_interference"] = False
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, allow_nan=False))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "NO_GO_TYPED_CONFIDENCE_READBACK", "error": str(exc), "runtime_started": False, "writes_performed": False, "public_result_interference": False}, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
