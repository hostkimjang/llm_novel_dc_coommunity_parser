import time
import unittest

from tools.attach_manifest_dashboard import _snapshot, _started_at_from_manifest


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


if __name__ == "__main__":
    unittest.main()
