from __future__ import annotations

import copy
from pathlib import Path
import tempfile
import unittest

from src.llm_batch.ledger.decision_call_events import DecisionCallLedgerRegistry
from src.llm_batch.ledger.decision_ledger_v2 import (
    DecisionCallLedgerV2,
    DecisionLedgerV2Error,
    replay_legacy_readback_to_v2,
)
from src.llm_batch.ledger.publication_commit import build_publication_scope_descriptor


class DecisionLedgerV2LegacyReplayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.scope = build_publication_scope_descriptor(
            input_file_sha256="1" * 64,
            post_ids=[101],
            config_hash="legacy-v2-equivalence",
            release_fingerprint="2" * 64,
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _legacy_readback(self):
        registry = DecisionCallLedgerRegistry(
            self.root / "legacy",
            scope_descriptor=self.scope,
            create_new=True,
            enabled=True,
            run_spec_sha256="e" * 64,
            pair_id="pair-legacy-v2",
            arm="BEFORE",
            fresh_execution_mode=True,
        )
        row = registry.row_attempt(
            attempt_run_id="run-a", row_attempt_id="row-a", input_index=1, post_id=101
        )
        registry.record_dispatch_intent(
            row,
            logical_call_id="logical-0",
            call_id="call-0",
            retry_ordinal=0,
            stage="GATEKEEPER",
            modality="TEXT",
            requested_model="requested-model",
            resolved_model=None,
            endpoint="http://127.0.0.1:8000/v1",
            backend="http",
            started_at="2026-07-12T10:00:00+09:00",
            monotonic_started_ns=1_000_000_000,
            request_sha256="a" * 64,
        )
        registry.record_terminal(
            row,
            call_id="call-0",
            terminal_status="SUCCEEDED",
            resolved_model="resolved-model",
            response_sha256="b" * 64,
            usage_provenance="PROVIDER_REPORTED",
            prompt_tokens=10,
            completion_tokens=2,
            total_tokens=12,
            finished_at="2026-07-12T10:00:01+09:00",
            monotonic_finished_ns=1_100_000_000,
        )
        registry.seal_row(
            row,
            sealed_at="2026-07-12T10:00:01+09:00",
            monotonic_finished_ns=1_100_000_000,
        )
        registry.link_publication(
            row, publication_decision_id="d" * 64, linked_at="2026-07-12T10:00:01+09:00"
        )
        return registry.readback()

    def test_real_legacy_frames_replay_exactly_and_deterministically(self) -> None:
        readback = self._legacy_readback()
        reversed_readback = copy.deepcopy(readback)
        reversed_readback["frames"].reverse()

        first = DecisionCallLedgerV2(
            self.root / "v2-first", scope_sha256=readback["scope"]["scope_sha256"], segment_max_frames=2
        )
        second = DecisionCallLedgerV2(
            self.root / "v2-second", scope_sha256=readback["scope"]["scope_sha256"], segment_max_frames=3
        )
        first_receipt = replay_legacy_readback_to_v2(first, reversed_readback)
        second_receipt = replay_legacy_readback_to_v2(second, readback)

        self.assertEqual(first_receipt, second_receipt)
        self.assertTrue(first_receipt["equivalent"])
        self.assertEqual(first_receipt["frame_count"], 4)
        self.assertEqual(first.replay(), readback["frames"])
        self.assertEqual(second.replay(), readback["frames"])

    def test_scope_tamper_and_nonempty_destination_fail_closed(self) -> None:
        readback = self._legacy_readback()
        wrong_scope = DecisionCallLedgerV2(self.root / "wrong", scope_sha256="f" * 64)
        with self.assertRaisesRegex(DecisionLedgerV2Error, "scope mismatch"):
            replay_legacy_readback_to_v2(wrong_scope, readback)

        tampered = copy.deepcopy(readback)
        tampered["frames"][0]["payload"] = {"tampered": True}
        target = DecisionCallLedgerV2(
            self.root / "tampered", scope_sha256=readback["scope"]["scope_sha256"]
        )
        with self.assertRaisesRegex(DecisionLedgerV2Error, "frame self-hash"):
            replay_legacy_readback_to_v2(target, tampered)

        nonempty = DecisionCallLedgerV2(
            self.root / "nonempty", scope_sha256=readback["scope"]["scope_sha256"]
        )
        nonempty.append({"frame_kind": "EXISTING"})
        with self.assertRaisesRegex(DecisionLedgerV2Error, "empty v2 ledger"):
            replay_legacy_readback_to_v2(nonempty, readback)


if __name__ == "__main__":
    unittest.main()
