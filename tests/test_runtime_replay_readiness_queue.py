from __future__ import annotations

import unittest

from tools.build_runtime_replay_readiness_queue import build_readiness_queue


class RuntimeReplayReadinessQueueTest(unittest.TestCase):
    def test_splits_runtime_rows_by_search_and_trace_blockers(self) -> None:
        batch = {
            "batch_id": "loop491",
            "summary": {"selected_rows": 2},
            "rows": [
                {
                    "post_id": 1,
                    "review_label": "REPROCESS",
                    "runtime_input_eligible": True,
                    "expected_title": "A",
                    "actions": [
                        "shared_gate_runtime_block_repair_required",
                        "search_degraded_or_timeout_replay_required",
                    ],
                    "search_status": "SEARCH_DEGRADED",
                    "search_unrecovered_degraded": 1,
                },
                {
                    "post_id": 2,
                    "review_label": "REPROCESS",
                    "runtime_input_eligible": True,
                    "expected_title": "B",
                    "actual_title": "B",
                    "actions": [
                        "shared_gate_runtime_block_repair_required",
                        "blocked_expected_title_trace_review_required",
                    ],
                    "search_status": "ok",
                    "search_unrecovered_degraded": 0,
                    "exact_title_match": True,
                },
            ],
        }
        verdict = {"review_id": "loop492", "rows": []}

        queue = build_readiness_queue(batch, verdict, queue_id="unit")

        self.assertEqual(queue["gate"], "REVIEW-LOCKED")
        self.assertEqual(queue["summary"]["loop491_runtime_reprocess_rows"], 2)
        self.assertEqual(queue["summary"]["ready_for_runtime_replay_rows"], 0)
        self.assertEqual(
            queue["summary"]["runtime_lane_counts"],
            {
                "publish_contract_trace_repair_before_replay": 1,
                "search_blind_or_recovered_preflight_before_replay": 1,
            },
        )
        self.assertEqual(queue["rows"][0]["ready_for_runtime_replay"], False)

    def test_maps_loop492_verdict_labels_to_followup_lanes(self) -> None:
        batch = {"batch_id": "loop491", "summary": {"selected_rows": 0}, "rows": []}
        verdict = {
            "review_id": "loop492",
            "rows": [
                {"post_id": 10, "review_label": "ACCEPT", "action": ["variant_policy"]},
                {"post_id": 11, "review_label": "REPROCESS", "action": ["repair"]},
                {"post_id": 12, "review_label": "HOLD", "action": ["hold"]},
            ],
        }

        queue = build_readiness_queue(batch, verdict, queue_id="unit")

        self.assertEqual(queue["summary"]["loop492_verdict_rows"], 3)
        self.assertEqual(
            queue["summary"]["verdict_lane_counts"],
            {
                "canonical_repair_before_runtime_replay": 1,
                "hard_hold_policy_or_native_review": 1,
                "variant_policy_before_regression_exclusion": 1,
            },
        )
        self.assertEqual(queue["summary"]["blocked_before_runtime_replay_rows"], 3)
        self.assertEqual(queue["validation_issues"], [])


if __name__ == "__main__":
    unittest.main()
