from __future__ import annotations

import unittest

from tools.build_search_recovery_blocker_replay_input import build_blocker_replay_input


class BuildSearchRecoveryBlockerReplayInputTest(unittest.TestCase):
    def test_selects_only_hard_search_blockers(self) -> None:
        rows = [
            {"post_id": 1, "title": "hard"},
            {"post_id": 2, "title": "recovered"},
            {"post_id": 3, "title": "missing"},
        ]
        audit = {
            "audit_id": "loop-test",
            "rows": [
                {
                    "post_id": 1,
                    "search_status": "SEARCH_DEGRADED",
                    "search_blocker_reason": "search_degraded",
                    "queries_issued": 4,
                    "degraded": 2,
                    "degraded_recovered": 0,
                    "unrecovered_degraded": 1,
                },
                {
                    "post_id": 2,
                    "search_status": "SEARCH_DEGRADED_RECOVERED",
                    "recovered_observation": "search_degraded_recovered",
                    "queries_issued": 4,
                    "degraded": 2,
                    "degraded_recovered": 2,
                    "unrecovered_degraded": 0,
                },
                {
                    "post_id": 3,
                    "search_status": "MISSING",
                    "search_blocker_reason": "search_health_missing",
                    "queries_issued": 0,
                    "degraded": 0,
                    "degraded_recovered": 0,
                    "unrecovered_degraded": 0,
                },
            ],
        }

        selected, manifest = build_blocker_replay_input(source_rows=rows, audit=audit, batch_id="loop-test-blockers")

        self.assertEqual([row["post_id"] for row in selected], [1, 3])
        self.assertEqual(manifest["gate"], "GO")
        self.assertEqual(manifest["summary"]["runtime_input_rows"], 2)
        self.assertEqual(
            manifest["summary"]["blocker_reason_counts"],
            {"search_degraded": 1, "search_health_missing": 1},
        )
        self.assertEqual(selected[0]["_search_recovery_blocker_replay"]["source_audit_id"], "loop-test")

    def test_missing_source_row_marks_manifest_no_go(self) -> None:
        audit = {
            "rows": [
                {
                    "post_id": 99,
                    "search_status": "SEARCH_DEGRADED",
                    "search_blocker_reason": "search_degraded",
                }
            ]
        }

        selected, manifest = build_blocker_replay_input(source_rows=[], audit=audit, batch_id="missing")

        self.assertEqual(selected, [])
        self.assertEqual(manifest["gate"], "NO-GO")
        self.assertEqual(manifest["missing_post_ids"], [99])


if __name__ == "__main__":
    unittest.main()
