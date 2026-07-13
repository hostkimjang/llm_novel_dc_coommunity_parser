from __future__ import annotations

"""Independent reader for a StageBudget no-runtime canary manifest."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.llm_batch.stage_budget_canary import read_shadow_canary


def read(path: Path) -> dict:
    return read_shadow_canary(json.loads(path.read_text(encoding="utf-8")))


def main() -> int:
    parser = argparse.ArgumentParser(description="Read a StageBudget shadow canary independently")
    parser.add_argument("--manifest", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(read(args.manifest), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
