from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from llm_batch.ledger.framed_wal import FramedWAL, FramedWalError, MAGIC, _exclusive_file_lock


class FramedWalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "decisions.fwal"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_reopens_large_sequence_without_rewriting_and_preserves_chain(self) -> None:
        wal = FramedWAL(self.path)
        for index in range(128):
            wal.append({"post_id": index + 1, "outcome": "HOLD"})
        before = self.path.read_bytes()
        reopened = FramedWAL(self.path)
        scan = reopened.initialize()
        self.assertEqual(len(scan.records), 128)
        reopened.append({"post_id": 129, "outcome": "PUBLISH"})
        self.assertTrue(self.path.read_bytes().startswith(before))
        self.assertEqual([item["record"]["post_id"] for item in reopened.iter_records()], list(range(1, 130)))

    def test_repairs_only_incomplete_final_frame(self) -> None:
        wal = FramedWAL(self.path)
        wal.append({"post_id": 1})
        committed_bytes = self.path.read_bytes()
        with self.path.open("ab") as handle:
            handle.write(b"\x00\x00\x00")
        repaired = FramedWAL(self.path).initialize(repair_uncommitted_tail=True)
        self.assertEqual(len(repaired.records), 1)
        self.assertEqual(self.path.read_bytes(), committed_bytes)
        self.assertTrue(list(self.path.with_name(self.path.name + ".tail_repairs").glob("*.json")))

    def test_rejects_complete_corruption(self) -> None:
        wal = FramedWAL(self.path)
        wal.append({"post_id": 1})
        raw = bytearray(self.path.read_bytes())
        raw[len(MAGIC) + 8] ^= 1
        self.path.write_bytes(raw)
        with self.assertRaises(FramedWalError):
            FramedWAL(self.path).initialize(repair_uncommitted_tail=True)

    def test_two_instances_concurrently_append_without_sequence_collision(self) -> None:
        first, second = FramedWAL(self.path), FramedWAL(self.path)
        first.initialize(); second.initialize()
        import threading
        threads = [threading.Thread(target=(first if index % 2 else second).append, args=({"post_id": index + 1},)) for index in range(20)]
        [item.start() for item in threads]; [item.join() for item in threads]
        self.assertEqual([item["sequence"] for item in FramedWAL(self.path).initialize().records], list(range(1, 21)))

    def test_lock_acquire_release_and_reacquire(self) -> None:
        with _exclusive_file_lock(self.path):
            self.assertTrue(True)
        with _exclusive_file_lock(self.path):
            self.assertTrue(True)
