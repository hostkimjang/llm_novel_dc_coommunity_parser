from __future__ import annotations

"""Create a synthetic-only legacy fixture then an isolated V2 mirror artifact."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))

from src.llm_batch.decision_call_events import DecisionCallLedgerRegistry
from src.llm_batch.decision_ledger_v2_mirror import mirror
from src.llm_batch.publication_commit import build_publication_scope_descriptor
from tools.build_stage_budget_receipt import _atomic_write


def run(*, output_root: Path) -> dict:
    root = Path(output_root).resolve()
    if root.exists(): raise FileExistsError(root)
    root.mkdir(parents=True)
    descriptor = build_publication_scope_descriptor(input_file_sha256="1" * 64, post_ids=[101], config_hash="decision-ledger-v2-mirror-canary", release_fingerprint="2" * 64)
    legacy = DecisionCallLedgerRegistry(root / "legacy", scope_descriptor=descriptor, create_new=True, enabled=True, run_spec_sha256="3" * 64, pair_id="mirror-canary-pair", arm="BEFORE", fresh_execution_mode=True)
    row = legacy.row_attempt(attempt_run_id="mirror-canary-run", row_attempt_id="row-1", input_index=1, post_id=101)
    legacy.record_dispatch_intent(row, logical_call_id="logical-1", call_id="call-1", retry_ordinal=0, stage="GATEKEEPER", modality="TEXT", requested_model="synthetic-model", resolved_model=None, endpoint="http://synthetic.invalid", backend="synthetic", started_at="2026-07-12T00:00:00+09:00", monotonic_started_ns=1, request_sha256="a" * 64)
    legacy.record_terminal(row, call_id="call-1", terminal_status="SUCCEEDED", resolved_model="synthetic-model", response_sha256="b" * 64, usage_provenance="PROVIDER_REPORTED", prompt_tokens=1, completion_tokens=1, total_tokens=2, finished_at="2026-07-12T00:00:01+09:00", monotonic_finished_ns=2)
    legacy.seal_row(row, sealed_at="2026-07-12T00:00:01+09:00", monotonic_finished_ns=2); legacy.link_publication(row, publication_decision_id="d" * 64, linked_at="2026-07-12T00:00:01+09:00")
    inputs = root / "inputs"; inputs.mkdir()
    paths = []
    for name in ("run_spec", "publication_scope", "attempt"):
        path = inputs / f"{name}.json"; _atomic_write(path, {"schema_version": "decision_ledger_v2_mirror_canary_input_v1", "synthetic": True, "name": name, "runtime_started": False}); paths.append(path)
    value = mirror(legacy_root=root / "legacy", output_root=root / "mirror", run_id="mirror-canary-run", run_spec_path=paths[0], publication_scope_path=paths[1], attempt_path=paths[2], segment_max_frames=2)
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description="Create synthetic-only DecisionLedgerV2 post-run mirror canary")
    parser.add_argument("--output-root", required=True, type=Path)
    args = parser.parse_args(); value = run(output_root=args.output_root)
    print(json.dumps({"gate": value["gate"], "runtime_started": False, "writes_to_production": False, "mirror": str(Path(args.output_root) / "mirror" / "mirror.json")}, ensure_ascii=False)); return 0


if __name__ == "__main__": raise SystemExit(main())
