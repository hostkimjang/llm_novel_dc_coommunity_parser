import json
import tempfile
import threading
import time
import unittest
from pathlib import Path

from tools.attach_manifest_dashboard import _load_json_when_ready, _snapshot, _started_at_from_manifest


class AttachManifestDashboardTest(unittest.TestCase):
    def test_started_at_from_manifest_uses_run_id(self):
        started_at = _started_at_from_manifest({"run_id": "20260706_151001_584579"})
        self.assertGreater(started_at, 0)
        self.assertEqual(
            time.strftime("%Y%m%d_%H%M%S", time.localtime(started_at)),
            "20260706_151001",
        )

    def test_snapshot_maps_manifest_progress(self):
        snap = _snapshot(
            {
                "run_id": "r",
                "input_post_count": 375,
                "completed_count": 150,
                "flushed_count": 149,
                "pending_count": 1,
                "failed_count": 0,
                "large_run_complete": False,
                "parallel_count": 16,
                "mcp_health_ok_count": 16,
                "mcp_health_failure_count": 0,
            },
            started_at=123.0,
            summary_limit=5,
        )
        self.assertTrue(snap["batch_running"])
        self.assertEqual(snap["total_posts"], 375)
        self.assertEqual(snap["done_count"], 150)
        self.assertEqual(snap["parallel_count"], 16)
        self.assertEqual(snap["search_hits"], 16)
        self.assertEqual(snap["attach_manifest"]["pending_count"], 1)

    def test_load_json_when_ready_waits_for_manifest_creation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "run_manifest.json"

            def write_later() -> None:
                time.sleep(0.1)
                path.write_text(json.dumps({"large_run_complete": True}), encoding="utf-8")

            thread = threading.Thread(target=write_later)
            thread.start()
            try:
                payload = _load_json_when_ready(path, wait_sec=2.0, retry_sec=0.05)
            finally:
                thread.join(timeout=2.0)

        self.assertEqual(payload["large_run_complete"], True)


if __name__ == "__main__":
    unittest.main()
