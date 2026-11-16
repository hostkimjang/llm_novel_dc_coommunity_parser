from __future__ import annotations

import asyncio
import json
import sys
import time
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from llm_batch.monitor.event_bus import MonitorState  # noqa: E402
from llm_batch.monitor.server import api_llm_resume  # noqa: E402


class MonitorSuspendStateTest(unittest.TestCase):
    def test_llm_suspend_and_resume_are_reflected_in_status(self):
        monitor = MonitorState()
        monitor.emit(
            "batch_start",
            {
                "total": 10,
                "input_file": "input.jsonl",
                "output_file": "output.json",
                "parallel_count": 4,
            },
        )

        monitor.emit(
            "llm_suspend",
            {
                "failure_count": 3,
                "threshold": 3,
                "last_error": "OSError: vllm hung",
                "started_at": "2026-04-16T12:00:00",
                "message": "llm서버측의 응답이 이상합니다 확인해주세요",
            },
        )
        suspended = monitor.get_status()
        self.assertTrue(suspended["llm_suspended"])
        self.assertEqual(suspended["llm_suspend_failure_count"], 3)
        self.assertEqual(suspended["llm_suspend_threshold"], 3)
        self.assertEqual(suspended["llm_suspend_error"], "OSError: vllm hung")
        self.assertEqual(
            suspended["llm_suspend_message"],
            "llm서버측의 응답이 이상합니다 확인해주세요",
        )

        monitor.emit(
            "llm_resume",
            {
                "failure_count": 3,
                "threshold": 3,
                "last_error": "OSError: vllm hung",
                "started_at": "2026-04-16T12:00:00",
                "resumed_at": "2026-04-16T12:01:00",
                "message": "사용자 확인 후 처리 재개",
            },
        )
        resumed = monitor.get_status()
        self.assertFalse(resumed["llm_suspended"])
        self.assertEqual(resumed["llm_suspend_resumed_at"], "2026-04-16T12:01:00")


class MonitorResumeApiTest(unittest.TestCase):
    def test_api_llm_resume_forwards_source(self):
        with patch("llm_batch.llm.client.request_llm_server_resume", return_value=True) as fake_resume:
            response = asyncio.run(api_llm_resume(source="web_keyboard"))

        payload = json.loads(response.body.decode("utf-8"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["source"], "web_keyboard")
        fake_resume.assert_called_once_with(source="web_keyboard")

    def test_api_llm_resume_returns_conflict_when_not_paused(self):
        with patch("llm_batch.llm.client.request_llm_server_resume", return_value=False):
            response = asyncio.run(api_llm_resume(source="web_dashboard"))

        payload = json.loads(response.body.decode("utf-8"))
        self.assertEqual(response.status_code, 409)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["source"], "web_dashboard")


class NativeRecoveryProgressTest(unittest.TestCase):
    def event(self, sequence=0, status="RUNNING", **updates):
        return {"schema_version": "native_recovery_progress_v1", "run_id": "native-base",
            "publication_scope_id": "a" * 64, "policy_sha256": "b" * 64, "sequence": sequence,
            "status": status, "total": 3, "processed": 1, "completed": 0, "not_executed": 1,
            "incomplete": 0, "aggregate_ref": None, **updates}

    def test_native_snapshot_reconnect_duplicate_order_and_base_counters(self):
        m = MonitorState()
        m.emit("batch_start", {"total": 3, "run_id": "native-base", "publication_scope_id": "a" * 64})
        m.emit("post_complete", {"post_id": 1, "token_usage": {"total_tokens": 17}})
        before = m.get_status()
        first = self.event()
        m.emit("native_recovery_progress", first)
        first["processed"] = 3  # caller 변경이 snapshot을 오염시키지 않음
        self.assertEqual(m.get_status()["native_recovery"]["processed"], 1)
        m.emit("native_recovery_progress", self.event(sequence=0, processed=2))
        m.emit("native_recovery_progress", self.event(sequence=1, run_id="foreign"))
        complete = self.event(sequence=2, status="COMPLETED", processed=3, completed=1,
            not_executed=1, incomplete=1, aggregate_ref={"path": "result_recovery_native_view.json", "sha256": "c" * 64, "bytes": 100})
        m.emit("native_recovery_complete", complete)
        m.emit("native_recovery_progress", self.event(sequence=3, processed=3))
        self.assertEqual(m.get_status()["native_recovery"], complete)
        after = m.get_status()
        for key in ("done_count", "relevant_count", "noise_count", "token_usage"):
            self.assertEqual(before[key], after[key])
        restored = MonitorState(); restored.load_status_snapshot(after)
        self.assertEqual(restored.get_status()["native_recovery"], complete)
        restored.load_status_snapshot({**after, "native_recovery": self.event(sequence=1)})
        self.assertEqual(restored.get_status()["native_recovery"], complete)
        returned = restored.get_status(); returned["native_recovery"]["completed"] = 99
        self.assertEqual(restored.get_status()["native_recovery"]["completed"], 1)
        restored.output_file = "old.json"
        new = self.event(run_id="next-run")
        restored.load_status_snapshot({"output_file": "new.json", "native_recovery": new})
        self.assertEqual(restored.get_status()["native_recovery"], new)

    def test_native_invalid_event_is_not_forwarded_and_batch_start_resets(self):
        m = MonitorState()
        with patch.object(m, "_broadcast") as send:
            m.emit("native_recovery_complete", self.event(status="COMPLETED", processed=3))
            m.ingest_event("native_recovery_progress", self.event(sequence=True))
            m.emit("native_recovery_progress", self.event(policy_sha256="not-sha"))
            m.emit("native_recovery_progress", self.event(status={"invalid": True}))
            send.assert_not_called()
        m.emit("native_recovery_progress", self.event())
        m.emit("batch_start", {"total": 1, "run_id": "another"})
        self.assertIsNone(m.get_status()["native_recovery"])
        m.emit("native_recovery_progress", self.event(sequence=1))
        self.assertIsNone(m.get_status()["native_recovery"])


class MonitorLlmThroughputTest(unittest.TestCase):
    def _monitor(self) -> MonitorState:
        monitor = MonitorState()
        monitor.emit("batch_start", {"total": 4, "input_file": "in.jsonl", "output_file": "out.json",
                                     "parallel_count": 2})
        return monitor

    def test_llm_stream_without_worker_id_uses_logging_thread_worker(self):
        monitor = self._monitor()
        seen = {}

        def worker() -> None:
            monitor.add_log("[12:00:00.000|W1] 🚀 Agentic Pipeline start", worker_id=1)
            monitor.emit("llm_stream", {"phase": "start", "tag": "decoder"})
            seen["sessions"] = monitor.get_status()["llm_throughput"]["sessions"]

        thread = threading.Thread(target=worker)
        thread.start()
        thread.join()
        self.assertEqual(seen["sessions"]["1"]["phase"], "streaming")
        self.assertEqual(seen["sessions"]["1"]["tag"], "decoder")

    def test_progress_then_end_counts_provider_usage_once(self):
        monitor = self._monitor()
        now = time.time()
        base = {"tag": "gatekeeper", "worker_id": 0}
        monitor.emit("llm_stream", {**base, "phase": "start", "at": now - 20})
        monitor.emit("llm_stream", {**base, "phase": "progress", "tokens": 200, "elapsed_s": 6.0,
                                    "ttft_s": 2.0, "at": now - 14})
        monitor.emit("llm_stream", {**base, "phase": "end", "tokens": 300, "elapsed_s": 12.0, "ttft_s": 2.0,
                                    "prompt_tokens": 1000, "completion_tokens": 400, "at": now - 8})
        throughput = monitor.get_status()["llm_throughput"]
        self.assertEqual(throughput["source"], "llm_stream")
        self.assertEqual((throughput["calls"], throughput["prompt_tokens"], throughput["completion_tokens"]),
                         (1, 1000, 400))
        # 진행 이벤트 200 + 끝 보정 200 = 출력 400. 첫 표본(14초 전)부터 나눈다.
        self.assertAlmostEqual(throughput["output_tps"], 400 / 14, delta=0.5)
        self.assertAlmostEqual(throughput["processed_tps"], 1400 / 14, delta=1.0)
        session = throughput["sessions"]["0"]
        self.assertEqual(session["phase"], "idle")
        self.assertEqual(session["last_call"]["tps"], 40.0)
        self.assertNotIn("_counted", session)

    def test_post_complete_tokens_give_approximate_rate_without_llm_stream(self):
        monitor = self._monitor()
        empty = monitor.get_status()["llm_throughput"]
        self.assertEqual(empty["source"], "none")
        self.assertIsNone(empty["output_tps"])
        monitor.emit("post_complete", {"post_id": 7, "title": "t", "is_relevant": True, "worker_id": 0,
                                       "token_usage": {"prompt_tokens": 3000, "completion_tokens": 600,
                                                       "total_tokens": 3600}})
        throughput = monitor.get_status()["llm_throughput"]
        self.assertEqual(throughput["source"], "post_complete")
        self.assertGreater(throughput["output_tps"], 0)
        self.assertGreater(throughput["processed_tps"], throughput["output_tps"])

    def test_batch_start_clears_llm_sessions(self):
        monitor = self._monitor()
        monitor.emit("llm_stream", {"phase": "queued", "tag": "verifier", "worker_id": 1})
        self.assertIn("1", monitor.get_status()["llm_throughput"]["sessions"])
        monitor.emit("batch_start", {"total": 1, "input_file": "in.jsonl", "output_file": "out2.json",
                                     "parallel_count": 2})
        self.assertEqual(monitor.get_status()["llm_throughput"]["sessions"], {})

    def test_unknown_llm_stream_phase_is_not_broadcast(self):
        monitor = self._monitor()
        sent = []
        with patch.object(monitor, "_broadcast", side_effect=sent.append):
            monitor.emit("llm_stream", {"phase": "bogus", "worker_id": 0})
        self.assertEqual(sent, [])
        self.assertEqual(monitor.get_status()["llm_throughput"]["sessions"], {})

    def test_progress_lines_are_throttled_per_worker(self):
        monitor = self._monitor()
        sent = []
        with patch.object(monitor, "_broadcast", side_effect=sent.append):
            for worker_id in (0, 1, 2):
                monitor.add_log(f"[12:00:00.000|W{worker_id}] ✅ Gatekeeper 완료", worker_id=worker_id)
            # 진행 줄은 워커가 다르면 같은 순간에 와도 모두 보낸다.
            self.assertEqual(len(sent), 3)
            monitor.add_log("[12:00:00.010|W0] 🔍 검색 시작", worker_id=0)
            self.assertEqual(len(sent), 3)
            # LLM 응답 JSON 조각은 워커와 상관없이 전체 간격을 따른다.
            monitor.add_log('    "query": "a",', worker_id=1)
            monitor.add_log('    "query": "b",', worker_id=2)
            self.assertEqual(len(sent), 4)

if __name__ == "__main__":
    unittest.main()
