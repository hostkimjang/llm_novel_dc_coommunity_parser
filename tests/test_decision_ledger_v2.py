from __future__ import annotations

from pathlib import Path
import tempfile
import threading
import unittest

from llm_batch.ledger.decision_ledger_v2 import DecisionCallLedgerV2, DecisionLedgerV2Error
from llm_batch.ledger.framed_wal import FramedWAL, FramedWalError


class DecisionLedgerV2Tests(unittest.TestCase):
    def setUp(self): self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name) / "v2"; self.scope = "a" * 64
    def tearDown(self): self.tmp.cleanup()
    def test_segment_index_checkpoint_and_replay_equivalence(self):
        ledger = DecisionCallLedgerV2(self.root, scope_sha256=self.scope, segment_max_frames=2)
        source = [{"frame_kind": "DISPATCH_INTENT", "call_id": str(n)} for n in range(5)]
        for frame in source: ledger.append(frame)
        self.assertEqual(ledger.replay(), source)
        self.assertEqual(ledger.checkpoint()["frame_count"], 5)
        self.assertEqual(len(ledger.initialize()["segments"]), 3)

    def test_first_append_initialize_recovery_and_nested_raw_rejection(self):
        ledger = DecisionCallLedgerV2(self.root, scope_sha256=self.scope)
        self.assertEqual(ledger.append({"frame_kind": "X"})["frame_count"], 1)
        self.assertEqual(ledger.initialize(recover_torn_tail=True)["frame_count"], 1)
        with self.assertRaisesRegex(DecisionLedgerV2Error, "raw prompt"):
            ledger.append({"payload": {"raw_prompt": "secret"}})
    def test_torn_tail_recovers_but_complete_corruption_fails(self):
        ledger = DecisionCallLedgerV2(self.root, scope_sha256=self.scope); ledger.append({"frame_kind": "X"})
        segment = next((self.root / "segments").glob("*.fwal")); committed = segment.read_bytes()
        with segment.open("ab") as handle: handle.write(b"\0\0")
        self.assertEqual(ledger.recover()["frame_count"], 1); self.assertEqual(segment.read_bytes(), committed)
        raw = bytearray(segment.read_bytes()); raw[-1] ^= 1; segment.write_bytes(raw)
        with self.assertRaises((FramedWalError, DecisionLedgerV2Error)): ledger.recover()
    def test_concurrent_append_has_one_indexed_frame_each(self):
        ledger = DecisionCallLedgerV2(self.root, scope_sha256=self.scope); errors=[]
        def append(n):
            try: ledger.append({"frame_kind": "TERMINAL", "call_id": str(n)})
            except Exception as exc: errors.append(exc)
        workers=[threading.Thread(target=append,args=(n,)) for n in range(16)]
        [item.start() for item in workers]; [item.join() for item in workers]
        self.assertEqual(errors, []); self.assertEqual(len(ledger.replay()), 16)

    def test_bounded_segment_scale_does_not_reopen_each_append(self):
        ledger = DecisionCallLedgerV2(self.root, scope_sha256=self.scope, segment_max_frames=64)
        for n in range(256): ledger.append({"frame_kind": "DISPATCH_INTENT", "call_id": str(n)})
        self.assertEqual(len(ledger.initialize()["segments"]), 4)
        self.assertEqual(len(ledger.replay()), 256)

    def test_104502_frame_scale_acceptance(self):
        ledger = DecisionCallLedgerV2(self.root, scope_sha256=self.scope, segment_max_frames=256)
        ledger.append_many({"frame_kind": "SCALE", "call_id": str(n)} for n in range(104_502))
        state = ledger.initialize()
        self.assertEqual((state["frame_count"], len(state["segments"]), len(ledger.replay())), (104_502, 409, 104_502))

    def test_compaction_requires_persisted_checkpoint_before_deleting_segments(self):
        ledger = DecisionCallLedgerV2(self.root, scope_sha256=self.scope, segment_max_frames=2)
        source = [{"frame_kind": "X", "call_id": str(n)} for n in range(5)]
        ledger.append_many(source)
        before = {path.name: path.read_bytes() for path in (self.root / "segments").glob("*.fwal")}
        with self.assertRaisesRegex(DecisionLedgerV2Error, "durable checkpoint"):
            ledger.compact({})
        self.assertEqual({path.name: path.read_bytes() for path in (self.root / "segments").glob("*.fwal")}, before)

        checkpoint = ledger.checkpoint()
        receipt = ledger.compact(checkpoint)
        self.assertEqual(receipt["status"], "SHADOW_ONLY_COMPACTION_ACCEPTED")
        self.assertTrue((self.root / "compaction_receipts" / f"{receipt['compacted_index_sha256']}.json").exists())
        self.assertEqual(ledger.replay(), source)
        self.assertEqual(len(list((self.root / "segments").glob("*.fwal"))), 1)

    def test_compaction_orphan_is_fail_closed_until_explicit_receipt_reconciliation(self):
        ledger = DecisionCallLedgerV2(self.root, scope_sha256=self.scope, segment_max_frames=2)
        source = [{"frame_kind": "X", "call_id": str(n)} for n in range(5)]
        ledger.append_many(source)
        source_bytes = {path.name: path.read_bytes() for path in (self.root / "segments").glob("*.fwal")}
        receipt = ledger.compact(ledger.checkpoint())
        # Simulate a crash after the durable receipt/index swap but before all
        # old source files were removed.
        restored = self.root / "segments" / next(iter(source_bytes))
        restored.write_bytes(source_bytes[restored.name])

        restarted = DecisionCallLedgerV2(self.root, scope_sha256=self.scope, segment_max_frames=2)
        with self.assertRaisesRegex(DecisionLedgerV2Error, "orphan segment"):
            restarted.initialize()
        reconciliation = restarted.reconcile_compaction()
        self.assertEqual(reconciliation["status"], "SHADOW_ONLY_COMPACTION_RECONCILED")
        self.assertEqual(reconciliation["reconciled_segments"], [f"segments/{restored.name}"])
        self.assertEqual(restarted.replay(), source)
        self.assertEqual(restarted.initialize()["index_sha256"], receipt["compacted_index_sha256"])

    def test_unknown_orphan_and_complete_index_mismatch_fail_closed(self):
        ledger = DecisionCallLedgerV2(self.root, scope_sha256=self.scope)
        ledger.append({"frame_kind": "X"})
        orphan = FramedWAL(self.root / "segments" / "orphan.fwal")
        orphan.initialize()
        orphan.append({"scope_sha256": self.scope, "frame": {"frame_kind": "ORPHAN"}})
        restarted = DecisionCallLedgerV2(self.root, scope_sha256=self.scope)
        with self.assertRaisesRegex(DecisionLedgerV2Error, "orphan segment"):
            restarted.recover()

        orphan.path.unlink()
        indexed = next((self.root / "segments").glob("*.fwal"))
        extra = FramedWAL(indexed)
        extra.append({"scope_sha256": self.scope, "frame": {"frame_kind": "EXTRA"}})
        with self.assertRaisesRegex(DecisionLedgerV2Error, "frame count mismatch"):
            restarted.recover()
