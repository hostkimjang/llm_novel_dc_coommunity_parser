from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from src.llm_batch.runtime.stage_budget_canary import StageBudgetCanaryError, read_shadow_canary
from tools.read_stage_budget_shadow_canary import read
from tools.run_stage_budget_shadow_canary import run


class StageBudgetShadowCanaryTests(unittest.TestCase):
    def _inputs(self, root: Path) -> tuple[Path, Path, Path, Path, Path]:
        paths = []
        for name in ("run_spec", "scope", "attempt", "ledger"):
            path = root / f"{name}.json"
            path.write_text(json.dumps({"name": name}), encoding="utf-8")
            paths.append(path)
        events = root / "events.json"
        events.write_text(json.dumps([{"stage": "search", "provider": "mcp", "outcome": "SUCCESS", "wait_ms": 3, "logical_call_sha256": "1" * 64, "limiter_config_sha256": "2" * 64, "deadline_ms": 50, "cache_namespace_sha256": "3" * 64, "singleflight_role": "LEADER", "execution_scope": "PROCESS_LOCAL_THREADS_ONLY"}, {"stage": "search", "provider": "mcp", "outcome": "DENIED", "limiter_outcome": "DENIED", "logical_call_sha256": "4" * 64, "limiter_config_sha256": "5" * 64, "deadline_ms": 0, "cache_namespace_sha256": "6" * 64, "singleflight_role": "FOLLOWER", "execution_scope": "PROCESS_LOCAL_THREADS_ONLY"}]), encoding="utf-8")
        return (*paths, events)

    def test_dedicated_no_runtime_canary_and_independent_reader(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); inputs = self._inputs(root)
            manifest = run(output_dir=root / "canary", run_spec=inputs[0], scope=inputs[1], attempt=inputs[2], ledger=inputs[3], events=inputs[4])
            self.assertFalse(manifest["runtime_started"]); self.assertFalse(manifest["writes_to_production"])
            self.assertEqual(read(root / "canary" / "stage_budget_shadow_canary.json")["independent_readback"], "GO_STAGE_BUDGET_SHADOW_CANARY")

    def test_reader_rejects_event_or_receipt_tamper(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); inputs = self._inputs(root)
            run(output_dir=root / "canary", run_spec=inputs[0], scope=inputs[1], attempt=inputs[2], ledger=inputs[3], events=inputs[4])
            manifest_path = root / "canary" / "stage_budget_shadow_canary.json"
            events = json.loads(inputs[4].read_text(encoding="utf-8")); events[0]["wait_ms"] = 99; inputs[4].write_text(json.dumps(events), encoding="utf-8")
            with self.assertRaises(StageBudgetCanaryError):
                read(manifest_path)
            # Restoring the event bytes cannot repair a receipt whose self-hash is changed.
            inputs[4].write_text(json.dumps([{"stage": "search", "provider": "mcp", "outcome": "SUCCESS", "wait_ms": 3, "logical_call_sha256": "1" * 64, "limiter_config_sha256": "2" * 64, "deadline_ms": 50, "cache_namespace_sha256": "3" * 64, "singleflight_role": "LEADER", "execution_scope": "PROCESS_LOCAL_THREADS_ONLY"}, {"stage": "search", "provider": "mcp", "outcome": "DENIED", "limiter_outcome": "DENIED", "logical_call_sha256": "4" * 64, "limiter_config_sha256": "5" * 64, "deadline_ms": 0, "cache_namespace_sha256": "6" * 64, "singleflight_role": "FOLLOWER", "execution_scope": "PROCESS_LOCAL_THREADS_ONLY"}]), encoding="utf-8")
            value = json.loads(manifest_path.read_text(encoding="utf-8")); value["canary_sha256"] = "0" * 64
            with self.assertRaises(StageBudgetCanaryError):
                read_shadow_canary(value)

    def test_reader_rejects_mixed_binding_even_with_rehashed_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            first_root, second_root = Path(first), Path(second); inputs = self._inputs(first_root); other = self._inputs(second_root)
            manifest = run(output_dir=first_root / "canary", run_spec=inputs[0], scope=inputs[1], attempt=inputs[2], ledger=inputs[3], events=inputs[4])
            manifest["binding"]["attempt"] = {"path": str(other[2].resolve()), "bytes": len(other[2].read_bytes()), "sha256": __import__("hashlib").sha256(other[2].read_bytes()).hexdigest()}
            material = {key: value for key, value in manifest.items() if key != "canary_sha256"}
            manifest["canary_sha256"] = __import__("hashlib").sha256(json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            with self.assertRaises(StageBudgetCanaryError):
                read_shadow_canary(manifest)

    def test_canary_rejects_incomplete_stage_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); inputs = self._inputs(root)
            events = json.loads(inputs[4].read_text(encoding="utf-8")); events[0].pop("logical_call_sha256"); inputs[4].write_text(json.dumps(events), encoding="utf-8")
            with self.assertRaisesRegex(StageBudgetCanaryError, "provenance is incomplete"):
                run(output_dir=root / "canary", run_spec=inputs[0], scope=inputs[1], attempt=inputs[2], ledger=inputs[3], events=inputs[4])
