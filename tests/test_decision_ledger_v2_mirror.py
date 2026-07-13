from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from src.llm_batch.decision_call_events import DecisionCallLedgerRegistry
from src.llm_batch.decision_ledger_v2_mirror import DecisionLedgerV2MirrorError, mirror, read
from src.llm_batch.publication_commit import build_publication_scope_descriptor


class DecisionLedgerV2MirrorTests(unittest.TestCase):
    def _legacy(self, root: Path) -> tuple[Path, Path, Path, Path, Path]:
        descriptor = build_publication_scope_descriptor(input_file_sha256="1" * 64, post_ids=[101], config_hash="v2-mirror", release_fingerprint="2" * 64)
        legacy_path = root / "legacy"; registry = DecisionCallLedgerRegistry(legacy_path, scope_descriptor=descriptor, create_new=True, enabled=True, run_spec_sha256="3" * 64, pair_id="pair-mirror", arm="BEFORE", fresh_execution_mode=True)
        row = registry.row_attempt(attempt_run_id="run", row_attempt_id="row", input_index=1, post_id=101)
        registry.record_dispatch_intent(row, logical_call_id="logical", call_id="call", retry_ordinal=0, stage="GATEKEEPER", modality="TEXT", requested_model="model", resolved_model=None, endpoint="http://provider", backend="http", started_at="2026-07-12T10:00:00+09:00", monotonic_started_ns=1, request_sha256="a" * 64)
        registry.record_terminal(row, call_id="call", terminal_status="SUCCEEDED", resolved_model="model", response_sha256="b" * 64, usage_provenance="PROVIDER_REPORTED", prompt_tokens=1, completion_tokens=1, total_tokens=2, finished_at="2026-07-12T10:00:01+09:00", monotonic_finished_ns=2)
        registry.seal_row(row, sealed_at="2026-07-12T10:00:01+09:00", monotonic_finished_ns=2); registry.link_publication(row, publication_decision_id="d" * 64, linked_at="2026-07-12T10:00:01+09:00")
        paths = []
        for name in ("run_spec", "publication_scope", "attempt"):
            path = root / f"{name}.json"; path.write_text(json.dumps({"name": name}), encoding="utf-8"); paths.append(path)
        return legacy_path, *paths

    def test_postrun_mirror_is_legacy_read_only_and_independently_replays(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); legacy, run_spec, scope, attempt = self._legacy(root); before = (legacy / "scope.json").read_bytes(); lock = legacy.parent / f".{legacy.name}.lock"; lock.unlink(missing_ok=True)
            value = mirror(legacy_root=legacy, output_root=root / "mirror", run_id="mirror-run", run_spec_path=run_spec, publication_scope_path=scope, attempt_path=attempt, segment_max_frames=2)
            self.assertEqual((value["runtime_started"], value["writes_to_production"], value["legacy_registry_write"]), (False, False, False)); self.assertEqual(read(value)["independent_readback"], "GO_DECISION_LEDGER_V2_POSTRUN_MIRROR")
            self.assertEqual((legacy / "scope.json").read_bytes(), before); self.assertFalse(lock.exists())

    def test_tamper_and_existing_output_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); legacy, run_spec, scope, attempt = self._legacy(root); value = mirror(legacy_root=legacy, output_root=root / "mirror", run_id="mirror-run", run_spec_path=run_spec, publication_scope_path=scope, attempt_path=attempt)
            value["frame_count"] = 99
            with self.assertRaises(DecisionLedgerV2MirrorError): read(value)
            with self.assertRaises(FileExistsError): mirror(legacy_root=legacy, output_root=root / "mirror", run_id="mirror-run", run_spec_path=run_spec, publication_scope_path=scope, attempt_path=attempt)

    def test_malformed_binding_overlap_and_cross_binding_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); legacy, run_spec, scope, attempt = self._legacy(root)
            with self.assertRaisesRegex(DecisionLedgerV2MirrorError, "outside legacy"):
                mirror(legacy_root=legacy, output_root=legacy / "mirror", run_id="mirror-run", run_spec_path=run_spec, publication_scope_path=scope, attempt_path=attempt)
            value = mirror(legacy_root=legacy, output_root=root / "mirror", run_id="mirror-run", run_spec_path=run_spec, publication_scope_path=scope, attempt_path=attempt)
            bad = dict(value); bad["legacy_scope"] = {}; material = {key: item for key, item in bad.items() if key != "mirror_sha256"}; from src.llm_batch.decision_ledger_v2_mirror import _sha; bad["mirror_sha256"] = _sha(material)
            with self.assertRaises(DecisionLedgerV2MirrorError): read(bad)
            bad = dict(value); bad["pair_id"] = "other"; material = {key: item for key, item in bad.items() if key != "mirror_sha256"}; bad["mirror_sha256"] = _sha(material)
            with self.assertRaises(DecisionLedgerV2MirrorError): read(bad)
