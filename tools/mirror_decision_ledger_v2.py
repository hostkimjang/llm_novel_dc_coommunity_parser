from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))

from src.llm_batch.decision_ledger_v2_mirror import mirror


def main() -> int:
    parser = argparse.ArgumentParser(description="Create isolated post-run DecisionLedgerV2 shadow mirror")
    for name in ("legacy-root", "output-root", "run-id", "run-spec", "publication-scope", "attempt"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--segment-max-frames", type=int, default=256)
    args = parser.parse_args(); value = mirror(legacy_root=Path(args.legacy_root), output_root=Path(args.output_root), run_id=args.run_id, run_spec_path=Path(args.run_spec), publication_scope_path=Path(args.publication_scope), attempt_path=Path(args.attempt), segment_max_frames=args.segment_max_frames)
    print(json.dumps({"gate": value["gate"], "runtime_started": False, "writes_to_production": False, "mirror": str(Path(args.output_root) / "mirror.json")}, ensure_ascii=False)); return 0


if __name__ == "__main__": raise SystemExit(main())
