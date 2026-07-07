import unittest

from tools.build_residual_p0_contract_queue import build_contract_queue


class BuildResidualP0ContractQueueTest(unittest.TestCase):
    def _batch(self):
        return {
            "batch_id": "unit_p0_action_batch",
            "rows": [
                {
                    "post_id": 1,
                    "priority": "P0",
                    "review_label": "REPROCESS",
                    "dispatch_lane": "shared_gate_restore_contract_review",
                    "batch_lanes": ["shared_gate_restore_contract_review"],
                    "selected_title": "Official Work",
                    "actions": [
                        "repair_safe_loss_restore_supported_title",
                        "shared_promotion_gate_wiring_required",
                    ],
                    "evidence_refs": ["https://novelpia.com/novel/123"],
                },
                {
                    "post_id": 2,
                    "priority": "P0",
                    "review_label": "REPROCESS",
                    "dispatch_lane": "shared_gate_restore_contract_review",
                    "batch_lanes": ["shared_gate_restore_contract_review"],
                    "selected_title": "Needs URL",
                    "actions": [
                        "repair_safe_loss_restore_supported_title",
                        "shared_promotion_gate_wiring_required",
                    ],
                    "evidence_refs": ["docs/devs/source_native.json#post_id=2"],
                },
                {
                    "post_id": 3,
                    "priority": "P0",
                    "review_label": "REPROCESS",
                    "dispatch_lane": "native_web_image_evidence_review",
                    "batch_lanes": [
                        "shared_gate_restore_contract_review",
                        "native_web_image_evidence_review",
                    ],
                    "selected_title": "Needs Native",
                    "actions": [
                        "repair_safe_loss_restore_supported_title",
                        "shared_promotion_gate_wiring_required",
                        "native_web_review_required",
                    ],
                },
                {
                    "post_id": 4,
                    "priority": "P0",
                    "review_label": "REPROCESS",
                    "dispatch_lane": "no_publish_guard_review",
                    "batch_lanes": [
                        "shared_gate_restore_contract_review",
                        "no_publish_guard_review",
                    ],
                    "selected_title": "Guarded Work",
                    "actions": [
                        "repair_safe_loss_restore_supported_title",
                        "shared_promotion_gate_wiring_required",
                        "merchandise_or_emoticon_work_context_guard",
                    ],
                },
                {
                    "post_id": 5,
                    "priority": "P0",
                    "review_label": "REPROCESS",
                    "dispatch_lane": "candidate_set_rebuild_review",
                    "batch_lanes": ["candidate_set_rebuild_review"],
                    "selected_title": None,
                    "actions": ["candidate_set_rebuild_required", "repair_after_wrong_work"],
                },
                {
                    "post_id": 6,
                    "priority": "P0",
                    "review_label": "INFO_MISSING",
                    "dispatch_lane": "source_native_or_blind_review",
                    "batch_lanes": ["source_native_or_blind_review"],
                    "actions": ["source_native_or_blind_review_required"],
                },
            ],
        }

    def test_builds_contract_buckets_without_runtime_replay(self):
        queue = build_contract_queue(self._batch(), queue_id="unit")

        self.assertEqual(queue["gate"], "REVIEW-LOCKED")
        self.assertEqual(queue["summary"]["contract_queue_rows"], 6)
        self.assertEqual(queue["summary"]["runtime_replay_allowed_rows"], 0)
        self.assertEqual(queue["summary"]["shared_gate_restore_clean_lane_rows"], 2)
        self.assertEqual(queue["summary"]["shared_gate_restore_ready_with_official_url_rows"], 1)
        self.assertEqual(queue["summary"]["shared_gate_restore_official_url_enrichment_rows"], 1)
        self.assertEqual(queue["summary"]["shared_gate_restore_precondition_review_rows"], 2)
        self.assertEqual(queue["summary"]["candidate_set_rebuild_required_rows"], 1)
        self.assertEqual(queue["summary"]["source_native_or_blind_info_missing_rows"], 1)
        self.assertEqual(
            queue["summary"]["contract_bucket_counts"],
            {
                "candidate_set_rebuild_required_before_publish": 1,
                "shared_gate_restore_contract_ready_with_official_url": 1,
                "shared_gate_restore_requires_native_web_review": 1,
                "shared_gate_restore_requires_no_publish_guard": 1,
                "shared_gate_restore_requires_official_url_enrichment": 1,
                "source_native_or_blind_info_missing_review": 1,
            },
        )

    def test_execution_contract_uses_parallel_16_and_dashboard(self):
        queue = build_contract_queue(self._batch(), queue_id="unit")

        self.assertEqual(queue["execution_contract"]["requested_parallel"], 16)
        self.assertEqual(queue["execution_contract"]["expected_effective_parallel"], 6)
        self.assertIn("--no-dashboard", queue["execution_contract"]["forbidden_flags"])
        self.assertEqual(
            queue["execution_contract"]["dashboard_contract"]["dashboard_policy"],
            "WEB_DASHBOARD_REQUIRED_FOR_TEST_RUNS",
        )
        self.assertFalse(any(row["runtime_replay_allowed"] for row in queue["rows"]))
        self.assertFalse(any(row["promotion_hard_hold_relaxation_allowed"] for row in queue["rows"]))


if __name__ == "__main__":
    unittest.main()
