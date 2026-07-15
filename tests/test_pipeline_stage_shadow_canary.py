from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

from src.llm_batch.runtime.pipeline_stage_shadow_canary import PipelineStageShadowCanaryError, read
from tools.read_pipeline_stage_shadow_canary import read as independent_read
from tools.run_pipeline_stage_shadow_canary import run


class PipelineStageShadowCanaryTests(unittest.TestCase):
    def _inputs(self, root: Path) -> tuple[Path, Path, Path, Path, Path]:
        paths = []
        for name in ("run_spec", "scope", "attempt", "ledger"):
            path = root / f"{name}.json"; path.write_text(json.dumps({"name": name}), encoding="utf-8"); paths.append(path)
        replay = root / "replay.json"; replay.write_text(json.dumps({"schema_version": "pipeline_stage_shadow_replay_input_v1", "queries": [{"query": "title search", "purpose": "verify", "response": {"results": [{"title": "work", "url": "https://example.test/work", "content": "evidence"}], "total": 1, "raw_total": 1}}]}), encoding="utf-8")
        return (*paths, replay)

    def test_replay_pipeline_canary_and_independent_reader(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); inputs = self._inputs(root)
            manifest = run(output_dir=root / "canary", run_spec=inputs[0], scope=inputs[1], attempt=inputs[2], ledger=inputs[3], replay_input=inputs[4])
            self.assertEqual((manifest["runtime_started"], manifest["writes_to_production"], manifest["pipeline_invoked"]), (False, False, True))
            self.assertEqual(independent_read(root / "canary" / "pipeline_stage_shadow_canary.json")["independent_readback"], "GO_PIPELINE_STAGE_SHADOW_REPLAY")
            self.assertNotIn("title search", json.dumps(manifest, ensure_ascii=False))

    def test_canary_never_creates_cwd_out_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); inputs = self._inputs(root); before = Path.cwd()
            try:
                os.chdir(root)
                run(output_dir=root / "canary", run_spec=inputs[0], scope=inputs[1], attempt=inputs[2], ledger=inputs[3], replay_input=inputs[4])
                self.assertFalse((root / "out").exists())
            finally:
                os.chdir(before)

    def test_reader_rejects_rehashed_event_replay_mismatch_and_duplicate_input(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); inputs = self._inputs(root); run(output_dir=root / "canary", run_spec=inputs[0], scope=inputs[1], attempt=inputs[2], ledger=inputs[3], replay_input=inputs[4])
            manifest_path = root / "canary" / "pipeline_stage_shadow_canary.json"; manifest = json.loads(manifest_path.read_text(encoding="utf-8")); stage_path = Path(manifest["stage_budget_canary"]["path"]); stage = json.loads(stage_path.read_text(encoding="utf-8")); events_path = Path(stage["events"]["artifact"]["path"])
            events = json.loads(events_path.read_text(encoding="utf-8")); events[0]["wait_ms"] = 999; events_path.write_text(json.dumps(events), encoding="utf-8")
            stage["events"]["artifact"] = {"path": str(events_path.resolve()), "bytes": len(events_path.read_bytes()), "sha256": hashlib.sha256(events_path.read_bytes()).hexdigest()}; material = {key: value for key, value in stage.items() if key != "canary_sha256"}; stage["canary_sha256"] = hashlib.sha256(json.dumps(material, ensure_ascii=False,sort_keys=True,separators=(",", ":")).encode()).hexdigest(); stage_path.write_text(json.dumps(stage), encoding="utf-8")
            manifest["stage_budget_canary"] = {"path": str(stage_path.resolve()), "bytes": len(stage_path.read_bytes()), "sha256": hashlib.sha256(stage_path.read_bytes()).hexdigest()}; material = {key: value for key, value in manifest.items() if key != "canary_sha256"}; manifest["canary_sha256"] = hashlib.sha256(json.dumps(material, ensure_ascii=False,sort_keys=True,separators=(",", ":")).encode()).hexdigest()
            with self.assertRaises(PipelineStageShadowCanaryError): read(manifest)
            replay = json.loads(inputs[4].read_text(encoding="utf-8")); replay["queries"].append(replay["queries"][0]); inputs[4].write_text(json.dumps(replay), encoding="utf-8")
            with self.assertRaises(PipelineStageShadowCanaryError): run(output_dir=root / "duplicate", run_spec=inputs[0], scope=inputs[1], attempt=inputs[2], ledger=inputs[3], replay_input=inputs[4])
