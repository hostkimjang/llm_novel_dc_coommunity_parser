from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))

from src.llm_batch.pipeline_stage_shadow_canary import read as _read


def read(path: Path) -> dict:
    return _read(json.loads(path.read_text(encoding="utf-8")))


def main() -> int:
    parser = argparse.ArgumentParser(description="Independently read a replay-only pipeline stage-shadow canary")
    parser.add_argument("--manifest", required=True, type=Path)
    args = parser.parse_args(); print(json.dumps(read(args.manifest), ensure_ascii=False)); return 0


if __name__ == "__main__": raise SystemExit(main())
