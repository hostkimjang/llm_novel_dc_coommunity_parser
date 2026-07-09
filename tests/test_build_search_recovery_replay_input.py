from __future__ import annotations

import unittest

from tools.build_search_recovery_replay_input import build_replay_input


class BuildSearchRecoveryReplayInputTest(unittest.TestCase):
    def test_builds_runtime_rows_from_source_result(self) -> None:
        source = [
            {
                "post_id": 1,
                "title": "one",
                "content": ["body"],
                "comments": ["comment"],
                "analysis_result": {"identity": {"search_health": {"status": "SEARCH_DEGRADED"}}},
                "run_meta": {"worker": 0},
            }
        ]
        deferred = [
            {
                "post_id": 1,
                "primary_action": "hold_for_search_recovery_rerun",
                "status": "null_to_resolved",
                "search_status": "SEARCH_DEGRADED",
                "search_queries": 4,
                "search_degraded": 2,
                "search_degraded_recovered": 0,
                "search_unrecovered_degraded": 1,
                "after_title": "after",
            }
        ]

        rows, manifest = build_replay_input(source, deferred, batch_id="loop_test")

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["post_id"], 1)
        self.assertNotIn("analysis_result", rows[0])
        self.assertNotIn("run_meta", rows[0])
        meta = rows[0]["_search_recovery_replay"]
        self.assertEqual(meta["batch_id"], "loop_test")
        self.assertEqual(meta["loop609_search_status"], "SEARCH_DEGRADED")
        self.assertEqual(meta["approval_state"], "search_recovery_replay_required_not_approval")
        self.assertEqual(manifest["gate"], "GO")
        self.assertEqual(manifest["summary"]["runtime_input_rows"], 1)
        self.assertEqual(manifest["summary"]["deferred_search_status_counts"], {"SEARCH_DEGRADED": 1})
        self.assertEqual(
            manifest["summary"]["deferred_primary_action_counts"],
            {"hold_for_search_recovery_rerun": 1},
        )
        self.assertEqual(manifest["summary"]["loop609_search_status_counts"], {"SEARCH_DEGRADED": 1})
        self.assertTrue(manifest["execution_contract"]["dashboard_required"])

    def test_skips_non_deferred_duplicate_and_reports_missing(self) -> None:
        source = [{"post_id": "1", "title": "one"}]
        deferred = [
            {"post_id": 1, "search_status": "ok"},
            {"post_id": 1, "search_status": "SEARCH_DEGRADED_RECOVERED"},
            {"post_id": 1, "search_status": "SEARCH_DEGRADED_RECOVERED"},
            {"post_id": 2, "search_status": "SEARCH_DEGRADED"},
        ]

        rows, manifest = build_replay_input(source, deferred, batch_id="loop_test")

        self.assertEqual([row["post_id"] for row in rows], ["1"])
        self.assertEqual(manifest["gate"], "NO-GO")
        self.assertEqual(manifest["missing_post_ids"], [2])
        reasons = [row["reason"] for row in manifest["skipped"]]
        self.assertIn("search_status_not_deferred", reasons)
        self.assertIn("duplicate_post_id", reasons)


if __name__ == "__main__":
    unittest.main()
