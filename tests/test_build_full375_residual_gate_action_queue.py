import unittest

from tools.build_full375_residual_gate_action_queue import build_queue


class BuildFull375ResidualGateActionQueueTest(unittest.TestCase):
    def test_builds_queue_from_raw_regression_post_id_overlap(self):
        collateral = {
            "compare_id": "unit_compare",
            "rows": [
                {
                    "post_id": 1,
                    "is_regression": True,
                    "status": "resolved_to_null",
                    "before_identity": {"official_title": "A", "candidate_ledger_status": "safe_resolved"},
                    "after_identity": {"official_title": None, "candidate_ledger_status": "promotion_blocked"},
                },
                {
                    "post_id": 2,
                    "is_regression": True,
                    "status": "null_to_resolved",
                    "before_identity": {"official_title": None, "candidate_ledger_status": "promotion_blocked"},
                    "after_identity": {"official_title": "B", "candidate_ledger_status": "safe_resolved"},
                },
                {"post_id": 3, "is_regression": True, "status": "resolved_to_different_title"},
                {"post_id": 9, "is_regression": False, "status": "same_title_url_changed"},
            ],
        }
        review = {
            "review_id": "unit_review",
            "rows": [
                {
                    "post_id": 1,
                    "triage_bucket": "safe_loss_resolved_to_null",
                    "review_label": "ACCEPT",
                    "source_native_verdict": "after_null_correct",
                    "action": ["exclude_from_regression_count_after_gate_wiring"],
                },
                {
                    "post_id": 2,
                    "triage_bucket": "unsafe_promotion_from_hold",
                    "review_label": "HOLD",
                    "source_native_verdict": "alias_bridge_unverified_hold",
                    "action": ["native_web_or_alias_relation_review_required"],
                },
                {
                    "post_id": 9,
                    "triage_bucket": "wrong_work_title_flip",
                    "review_label": "REPROCESS",
                    "source_native_verdict": "non_raw_repair",
                    "action": ["shared_promotion_gate_wiring_required"],
                },
            ],
        }

        queue = build_queue(collateral_compare=collateral, review_summary=review, queue_id="unit_queue")

        summary = queue["summary"]
        self.assertEqual(summary["raw_regression_rows"], 3)
        self.assertEqual(summary["reviewed_raw_regression_rows"], 2)
        self.assertEqual(summary["reviewed_non_regression_rows"], 1)
        self.assertEqual(summary["exclusion_candidate_rows"], 1)
        self.assertEqual(summary["residual_action_queue_rows"], 2)
        self.assertEqual(summary["reviewed_raw_residual_rows"], 1)
        self.assertEqual(summary["unreviewed_raw_residual_rows"], 1)
        self.assertEqual(queue["rows"][0]["post_id"], 2)
        self.assertEqual(queue["rows"][0]["queue_lane"], "alias_relation_native_web_review")
        self.assertEqual(queue["rows"][1]["post_id"], 3)
        self.assertEqual(queue["rows"][1]["review_coverage"], "unreviewed_raw_regression")


if __name__ == "__main__":
    unittest.main()
