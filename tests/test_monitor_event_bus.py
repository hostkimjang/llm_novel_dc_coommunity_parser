from __future__ import annotations

import asyncio
import json
import sys
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


if __name__ == "__main__":
    unittest.main()
