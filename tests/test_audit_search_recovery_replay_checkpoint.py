from __future__ import annotations

import unittest

from tools.audit_search_recovery_replay_checkpoint import audit_replay


def _row(post_id: int, status: str, *, degraded: int = 0, unrecovered: int = 0) -> dict:
    return {
        "post_id": post_id,
        "analysis_result": {
            "identity": {
                "novel_identity": {"official_title": f"title {post_id}"},
                "search_health": {
                    "status": status,
                    "queries_issued": 3,
                    "degraded": degraded,
                    "degraded_recovered": max(degraded - unrecovered, 0),
                    "unrecovered_degraded": unrecovered,
                },
            }
        },
    }


class AuditSearchRecoveryReplayCheckpointTest(unittest.TestCase):
    def test_partial_degraded_subset_is_no_go(self) -> None:
        report = audit_replay(
            recovered_rows=[
                _row(1, "SEARCH_DEGRADED", degraded=2, unrecovered=1),
                _row(2, "SEARCH_DEGRADED_RECOVERED", degraded=1, unrecovered=0),
            ],
            input_manifest={"summary": {"runtime_input_rows": 3}},
            recovery_summary={"large_run_complete": False, "checkpoint_completed_rows": 2},
            audit_id="test",
        )

        self.assertEqual(report["gate"], "NO-GO")
        self.assertEqual(report["summary"]["completed_rows"], 2)
        self.assertEqual(report["summary"]["status_counts"]["SEARCH_DEGRADED"], 1)
        self.assertIn("partial_replay_not_all_deferred_rows_completed", report["summary"]["blockers"])
        self.assertIn("row_search_health_not_ok", report["summary"]["blockers"])
        self.assertIn("unrecovered_degraded_queries_observed", report["summary"]["blockers"])

    def test_complete_all_ok_subset_is_go(self) -> None:
        report = audit_replay(
            recovered_rows=[_row(1, "ok"), _row(2, "ok")],
            input_manifest={"summary": {"runtime_input_rows": 2}},
            recovery_summary={"large_run_complete": True, "checkpoint_completed_rows": 2},
            audit_id="test",
        )

        self.assertEqual(report["gate"], "GO")
        self.assertEqual(report["summary"]["non_ok_row_count"], 0)
        self.assertEqual(report["summary"]["blockers"], [])


if __name__ == "__main__":
    unittest.main()
