from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))

from src.llm_batch.ledger.decision_ledger_v2_mirror import read


def main() -> int:
    parser = argparse.ArgumentParser(description="Independently read DecisionLedgerV2 post-run shadow mirror")
    parser.add_argument("--mirror", required=True, type=Path)
    args = parser.parse_args(); print(json.dumps(read(json.loads(args.mirror.read_text(encoding="utf-8"))), ensure_ascii=False)); return 0


if __name__ == "__main__": raise SystemExit(main())
