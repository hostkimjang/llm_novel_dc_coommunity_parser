import unittest

from tools.build_ordinary_residual_dispatch import build_dispatch


class OrdinaryResidualDispatchTests(unittest.TestCase):
    def _accounting(self):
        return {
            "accounting_id": "loop552",
            "summary": {"contract_processed_rows": 1},
            "rows": [
                {
                    "post_id": 1,
                    "triage_bucket": "safe_loss_resolved_to_null",
                    "review_label": "REPROCESS",
                    "ordinary_residual_unprocessed": True,
                    "contract_accounting_state": "ordinary_residual_unprocessed",
                    "contract_accounting_effect": "residual_queue_followup_required",
                },
                {
                    "post_id": 2,
                    "triage_bucket": "wrong_work_title_flip",
                    "review_label": "INFO_MISSING",
                    "ordinary_residual_unprocessed": True,
                    "contract_accounting_state": "ordinary_residual_unprocessed",
                    "contract_accounting_effect": "residual_queue_followup_required",
                },
                {
                    "post_id": 3,
                    "triage_bucket": "safe_loss_resolved_to_null",
                    "review_label": "REPROCESS",
                    "ordinary_residual_unprocessed": False,
                    "contract_accounting_state": "contract_processed_expected_restore_projection_applied",
                },
            ],
        }

    def test_filters_ordinary_rows_and_keeps_no_approval_boundary(self):
        source_queue = {
            "queue_id": "loop546",
            "summary": {"residual_action_queue_rows": 3},
            "rows": [
                {
                    "post_id": 1,
                    "review_label": "REPROCESS",
                    "triage_bucket": "safe_loss_resolved_to_null",
                    "actions": [
                        "repair_safe_loss_restore_supported_title",
                        "shared_promotion_gate_wiring_required",
                    ],
                },
                {
                    "post_id": 2,
                    "review_label": "INFO_MISSING",
                    "triage_bucket": "wrong_work_title_flip",
                    "actions": ["candidate_set_rebuild_required"],
                },
                {
                    "post_id": 3,
                    "review_label": "REPROCESS",
                    "triage_bucket": "safe_loss_resolved_to_null",
                    "actions": ["shared_promotion_gate_wiring_required"],
                },
            ],
        }

        dispatch = build_dispatch(accounting=self._accounting(), source_queue=source_queue, dispatch_id="d1")

        self.assertEqual(dispatch["summary"]["ordinary_residual_rows"], 2)
        self.assertEqual(dispatch["summary"]["contract_processed_rows_held"], 1)
        self.assertEqual(dispatch["summary"]["runtime_replay_allowed_rows"], 0)
        self.assertEqual(dispatch["summary"]["publish_allowed_rows"], 0)
        self.assertFalse(dispatch["full_scan_approval"])
        self.assertTrue(dispatch["approval_boundary"]["dispatch_generation_is_not_approval"])
        self.assertEqual(dispatch["gate"], "REVIEW-LOCKED")
        self.assertEqual(
            dispatch["summary"]["lane_counts"],
            {
                "shared_gate_restore_contract_review": 1,
                "source_native_or_blind_review": 1,
            },
        )

    def test_candidate_and_guard_lanes_are_prioritized_before_runtime(self):
        source_queue = {
            "queue_id": "loop546",
            "rows": [
                {
                    "post_id": 1,
                    "review_label": "REPROCESS",
                    "actions": ["candidate_set_rebuild_required", "native_web_review_required"],
                },
                {
                    "post_id": 2,
                    "review_label": "REPROCESS",
                    "actions": ["repair_unsafe_promotion", "intent_guard_review"],
                },
            ],
        }
        accounting = self._accounting()
        accounting["rows"][1]["review_label"] = "REPROCESS"

        dispatch = build_dispatch(accounting=accounting, source_queue=source_queue, dispatch_id="d2")
        lanes_by_post = {row["post_id"]: row["primary_lane"] for row in dispatch["rows"]}

        self.assertEqual(lanes_by_post[1], "candidate_set_rebuild_review")
        self.assertEqual(lanes_by_post[2], "no_publish_multiwork_guard_review")
        self.assertEqual(dispatch["summary"]["runtime_replay_allowed_rows"], 0)

    def test_missing_source_queue_row_is_validation_issue(self):
        source_queue = {"queue_id": "loop546", "rows": []}

        dispatch = build_dispatch(accounting=self._accounting(), source_queue=source_queue, dispatch_id="d3")

        self.assertEqual(dispatch["gate"], "NO-GO")
        self.assertEqual(dispatch["summary"]["validation_issue_count"], 2)
        self.assertEqual(
            {issue["code"] for issue in dispatch["validation_issues"]},
            {"ordinary_row_missing_source_queue_row"},
        )


if __name__ == "__main__":
    unittest.main()
