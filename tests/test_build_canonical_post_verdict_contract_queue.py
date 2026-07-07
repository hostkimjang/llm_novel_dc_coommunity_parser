import unittest

from tools.build_canonical_post_verdict_contract_queue import build_contract_queue


class BuildCanonicalPostVerdictContractQueueTest(unittest.TestCase):
    def test_groups_valid_post_verdict_rows_without_runtime_release(self):
        application = {
            "review_id": "unit_application",
            "source_batch": "batch.json",
            "source_verdicts": "verdicts.json",
            "rows": [
                {
                    "post_id": 1,
                    "canonical_verdict": "EXPECTED_SOURCE_NATIVE_TITLE_CONFIRMED",
                    "post_verdict_next_state": "candidate_scrub_or_expected_title_restore_contract_required",
                    "runtime_release_condition": "blocked_until_contract_tests_pass",
                    "runtime_replay_allowed_after_verdict": False,
                    "contract_test_required_before_runtime": True,
                    "search_gate": "SEARCH_OK",
                },
                {
                    "post_id": 2,
                    "canonical_verdict": "RELATED_CANONICAL_VARIANT_CONFIRMED",
                    "post_verdict_next_state": "canonical_variant_policy_contract_required",
                    "runtime_release_condition": "blocked_until_variant_policy_tests_pass",
                    "runtime_replay_allowed_after_verdict": False,
                    "contract_test_required_before_runtime": True,
                    "search_gate": "SEARCH_BLIND_BLOCKER",
                },
            ],
        }

        queue = build_contract_queue(application, queue_id="unit_queue", generated_at="2026-07-07T00:00:00")

        self.assertEqual(queue["gate"], "REVIEW-LOCKED")
        self.assertEqual(queue["summary"]["contract_queue_rows"], 2)
        self.assertEqual(queue["summary"]["runtime_replay_allowed_rows"], 0)
        self.assertEqual(
            queue["summary"]["contract_batch_lane_counts"],
            {
                "C1_expected_restore_or_candidate_scrub_contract": 1,
                "C2_canonical_variant_policy_contract": 1,
            },
        )
        self.assertFalse(queue["full_scan_approval"])
        self.assertEqual(queue["next_batches"][0]["runtime_replay_allowed_rows"], 0)

    def test_runtime_release_or_unknown_state_is_no_go(self):
        application = {
            "review_id": "unit_application",
            "rows": [
                {
                    "post_id": 1,
                    "canonical_verdict": "EXPECTED_SOURCE_NATIVE_TITLE_CONFIRMED",
                    "post_verdict_next_state": "unexpected_next_state",
                    "runtime_replay_allowed_after_verdict": True,
                    "contract_test_required_before_runtime": False,
                }
            ],
        }

        queue = build_contract_queue(application, queue_id="unit_queue", generated_at="2026-07-07T00:00:00")

        self.assertEqual(queue["gate"], "NO-GO")
        self.assertEqual(queue["summary"]["validation_issue_count"], 1)
        self.assertIn("unknown_post_verdict_next_state", queue["validation_issues"][0]["issues"])
        self.assertIn("runtime_replay_already_allowed_after_verdict", queue["validation_issues"][0]["issues"])
        self.assertIn("contract_test_required_before_runtime_not_true", queue["validation_issues"][0]["issues"])


if __name__ == "__main__":
    unittest.main()
