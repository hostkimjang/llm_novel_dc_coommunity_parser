from __future__ import annotations

"""Create a dedicated no-runtime StageBudget canary manifest and receipt."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.llm_batch.stage_budget import ArtifactRef, StageBudgetBinding
from src.llm_batch.stage_budget_canary import build_shadow_canary
from tools.build_stage_budget_receipt import _atomic_write


def run(*, output_dir: Path, run_spec: Path, scope: Path, attempt: Path, ledger: Path, events: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    binding = StageBudgetBinding(*(ArtifactRef.snapshot(path) for path in (run_spec, scope, attempt, ledger)))
    manifest = build_shadow_canary(binding=binding, events_path=events, receipt_path=output_dir / "stage_budget_receipt.json", receipt_writer=_atomic_write)
    _atomic_write(output_dir / "stage_budget_shadow_canary.json", manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a no-runtime StageBudget shadow canary")
    for name in ("output-dir", "run-spec", "scope", "attempt", "ledger", "events"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    value = run(output_dir=args.output_dir, run_spec=args.run_spec, scope=args.scope, attempt=args.attempt, ledger=args.ledger, events=args.events)
    print(json.dumps({"gate": value["gate"], "runtime_started": False, "writes_to_production": False, "manifest": str(args.output_dir / "stage_budget_shadow_canary.json")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
