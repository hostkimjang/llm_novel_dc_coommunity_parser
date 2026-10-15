"""검색 캐시의 워커 누계·standalone 재접속을 실제 상태 경로로 검산한다."""
from __future__ import annotations

import asyncio
import json
import os
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from llm_batch.monitor.event_bus import MonitorState
from llm_batch.monitor.forwarder import DashboardForwarder
import llm_batch.monitor.server as server


class MonitorSearchStatsTest(unittest.TestCase):
    def make_state(self, output="run/result.json"):
        state = MonitorState()
        state.emit("batch_start", {"total": 12, "parallel_count": 12, "output_file": output})
        return state

    def counts(self, state):
        status = state.get_status()
        return status["search_hits"], status["search_misses"]

    def test_independent_worker_cumulative_totals_are_not_last_worker(self):
        state = self.make_state()
        state.emit("search_stats", {"worker_id": 0, "hits": 4, "misses": 8})
        state.emit("search_stats", {"worker_id": 1, "hits": 1, "misses": 3})
        state.emit("search_stats", {"worker_id": 0, "hits": 7, "misses": 10})
        self.assertEqual(self.counts(state), (8, 13))
        self.assertEqual(state.get_status()["search_stats_workers"], {
            "0": {"hits": 7, "misses": 10}, "1": {"hits": 1, "misses": 3}})

    def test_duplicate_and_late_worker_snapshots_do_not_double_or_roll_back(self):
        state = self.make_state()
        state.ingest_event("search_stats", {"worker_id": 0, "hits": 5, "misses": 8})
        state.ingest_event("search_stats", {"worker_id": "0", "hits": 5, "misses": 8})
        state.ingest_event("search_stats", {"worker_id": 0, "hits": 2, "misses": 4})
        state.ingest_event("search_stats", {"worker_id": 0, "hits": 4, "misses": 9})
        self.assertEqual(self.counts(state), (5, 8))
        self.assertEqual(len(state.get_status()["search_stats_workers"]), 1)

    def test_batch_start_resets_worker_identity_and_counters(self):
        state = self.make_state()
        state.emit("search_stats", {"worker_id": 0, "hits": 9, "misses": 20})
        state.emit("batch_complete")
        self.assertEqual(self.counts(state), (9, 20))
        state.emit("batch_start", {"output_file": "next/result.json"})
        self.assertEqual(self.counts(state), (0, 0))
        state.emit("search_stats", {"worker_id": 0, "hits": 1, "misses": 2})
        self.assertEqual(self.counts(state), (1, 2))

    def test_legacy_events_replace_total_and_are_not_mixed_with_worker_totals(self):
        state = self.make_state()
        state.emit("search_stats", {"hits": 4, "misses": 10})
        state.emit("search_stats", {"hits": 1, "misses": 3})
        self.assertEqual(self.counts(state), (1, 3))
        self.assertIsNone(state.get_status()["search_stats_workers"])
        state.emit("search_stats", {"worker_id": 0, "hits": 2, "misses": 5})
        self.assertEqual(self.counts(state), (2, 5))
        state.emit("search_stats", {"hits": 7, "misses": 12})
        self.assertEqual(self.counts(state), (7, 12))
        self.assertIsNone(state.get_status()["search_stats_workers"])

    def test_json_snapshot_restore_then_backlog_and_increment(self):
        source = self.make_state()
        source.emit("search_stats", {"worker_id": 0, "hits": 7, "misses": 10})
        source.emit("search_stats", {"worker_id": 1, "hits": 1, "misses": 3})
        snapshot = json.loads(json.dumps(source.get_status()))
        target = MonitorState()
        target.load_status_snapshot(snapshot)
        target.ingest_event("search_stats", {"worker_id": 0, "hits": 4, "misses": 8})
        target.ingest_event("search_stats", {"worker_id": 1, "hits": 1, "misses": 3})
        self.assertEqual(self.counts(target), (8, 13))
        target.ingest_event("search_stats", {"worker_id": 1, "hits": 2, "misses": 5})
        self.assertEqual(self.counts(target), (9, 15))
        target.load_status_snapshot(snapshot)
        self.assertEqual(self.counts(target), (9, 15))
        snapshot["search_stats_workers"]["0"]["hits"] = 99
        returned = target.get_status()
        returned["search_stats_workers"]["1"]["hits"] = 88
        self.assertEqual(self.counts(target), (9, 15))

    def test_new_output_snapshot_resets_prior_workers_without_batch_start(self):
        source = self.make_state("new/result.json")
        source.emit("search_stats", {"worker_id": 0, "hits": 1, "misses": 2})
        target = self.make_state("old/result.json")
        target.emit("search_stats", {"worker_id": 9, "hits": 40, "misses": 60})
        target.load_status_snapshot(source.get_status())
        self.assertEqual(self.counts(target), (1, 2))
        self.assertEqual(set(target.get_status()["search_stats_workers"]), {"0"})
        target.load_status_snapshot({"output_file": "third/result.json"})
        self.assertEqual(self.counts(target), (0, 0))

    def test_partial_unrelated_and_legacy_snapshots_preserve_compatibility(self):
        state = self.make_state()
        state.emit("search_stats", {"worker_id": 0, "hits": 4, "misses": 5})
        state.load_status_snapshot({"done_count": 2})
        self.assertEqual(self.counts(state), (4, 5))
        self.assertIn("0", state.get_status()["search_stats_workers"])
        state.load_status_snapshot({"search_hits": 3, "search_misses": 9})
        self.assertEqual(self.counts(state), (3, 9))
        self.assertIsNone(state.get_status()["search_stats_workers"])
        state.load_status_snapshot({"search_hits": 6})
        self.assertEqual(self.counts(state), (6, 9))

    def test_invalid_event_is_not_applied_or_forwarded(self):
        state = self.make_state()
        state.emit("search_stats", {"worker_id": 0, "hits": 2, "misses": 3})
        invalid = [
            {"worker_id": True, "hits": 1, "misses": 1},
            {"worker_id": -1, "hits": 1, "misses": 1},
            {"worker_id": [], "hits": 1, "misses": 1},
            {"worker_id": "", "hits": 1, "misses": 1},
            {"worker_id": 1, "hits": True, "misses": 1},
            {"worker_id": 1, "hits": -1, "misses": 1},
            {"worker_id": 1, "hits": 1.0, "misses": 1},
            {"worker_id": 1, "hits": "1", "misses": 1},
            {"hits": None, "misses": 1},
        ]
        forwarded = []
        state.attach_forwarder(SimpleNamespace(enqueue=forwarded.append))
        with patch.object(state, "_broadcast") as broadcast:
            for event in invalid:
                with self.subTest(event=event):
                    state.emit("search_stats", event)
                    self.assertEqual(self.counts(state), (2, 3))
            broadcast.assert_not_called()
        self.assertEqual(forwarded, [])

    def test_invalid_snapshot_shape_or_total_is_not_accepted(self):
        state = self.make_state()
        state.emit("search_stats", {"worker_id": 0, "hits": 2, "misses": 3})
        invalid = [
            {"search_hits": 100, "search_misses": 3, "search_stats_workers": {"0": {"hits": 2, "misses": 3}}},
            {"search_hits": 1, "search_misses": 2, "search_stats_workers": {"0": {"hits": True, "misses": 2}}},
            {"search_hits": 1, "search_misses": 2, "search_stats_workers": {"0": {"hits": 1, "misses": 2, "extra": 0}}},
            {"search_hits": 1, "search_misses": 2, "search_stats_workers": []},
            {"search_stats_workers": {"0": {"hits": 1, "misses": 2}}},
        ]
        for snapshot in invalid:
            with self.subTest(snapshot=snapshot):
                state.load_status_snapshot(snapshot)
                self.assertEqual(self.counts(state), (2, 3))
                self.assertEqual(state.get_status()["search_stats_workers"], {"0": {"hits": 2, "misses": 3}})

    def test_parallel_worker_updates_are_atomic(self):
        state = self.make_state()
        def update(worker):
            for count in range(1, 6):
                state.emit("search_stats", {"worker_id": worker, "hits": count, "misses": 2 * count})
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(update, range(12)))
        self.assertEqual(self.counts(state), (60, 120))
        self.assertEqual(len(state.get_status()["search_stats_workers"]), 12)

    def test_real_forwarder_ingest_status_roundtrip_matches_all_worker_totals(self):
        # 20/96이라는 관측된 합계를 재현하는 두 워커 합성값이다. 실제 워커 배분은 주장하지 않는다.
        source = self.make_state()
        queued = []
        source.attach_forwarder(SimpleNamespace(enqueue=queued.append))
        source.emit("search_stats", {"worker_id": 0, "hits": 20, "misses": 80})
        source.emit("search_stats", {"worker_id": 5, "hits": 0, "misses": 16})
        self.assertEqual(queued[-1]["data"], {"worker_id": 5, "hits": 0, "misses": 16})
        forwarder = DashboardForwarder("http://not-contacted.invalid", monitor=source)
        snapshot = forwarder._make_snapshot_item()
        self.assertIsNotNone(snapshot)
        target = MonitorState()
        with patch.object(server, "monitor", target), patch.dict(os.environ, {
                "DASHBOARD_STANDALONE": "1", "DASHBOARD_INGEST_TOKEN": ""}):
            # 재접속 스냅샷 뒤 같은 이전 이벤트를 받더라도 합계는 같아야 한다.
            response = server.api_ingest(SimpleNamespace(headers={}),
                {"items": json.loads(json.dumps([snapshot, *queued]))})
            self.assertEqual(response.status_code, 200)
            payload = json.loads(asyncio.run(server.api_status()).body)
        self.assertEqual((payload["search_hits"], payload["search_misses"]), (20, 96))
        self.assertEqual(round(payload["search_hits"] / (payload["search_hits"] + payload["search_misses"]) * 100, 1), 17.2)
        self.assertEqual(payload["output_file"], "run/result.json")
        self.assertIsNone(forwarder._client)
        self.assertIsNone(forwarder._thread)


if __name__ == "__main__":
    unittest.main()
