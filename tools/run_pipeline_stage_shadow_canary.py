from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))

from src.llm_batch.pipeline_stage_shadow_canary import build
from tools.build_stage_budget_receipt import _atomic_write


def run(*, output_dir: Path, run_spec: Path, scope: Path, attempt: Path, ledger: Path, replay_input: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = build(output_dir=output_dir, run_spec=run_spec, scope=scope, attempt=attempt, ledger=ledger, replay_input=replay_input, receipt_writer=_atomic_write)
    _atomic_write(output_dir / "pipeline_stage_shadow_canary.json", manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Run replay-only AgenticPipeline stage-shadow canary")
    for name in ("output-dir", "run-spec", "scope", "attempt", "ledger", "replay-input"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args(); value = run(output_dir=args.output_dir, run_spec=args.run_spec, scope=args.scope, attempt=args.attempt, ledger=args.ledger, replay_input=args.replay_input)
    print(json.dumps({"gate": value["gate"], "runtime_started": False, "writes_to_production": False, "manifest": str(args.output_dir / "pipeline_stage_shadow_canary.json")}, ensure_ascii=False)); return 0


if __name__ == "__main__": raise SystemExit(main())
