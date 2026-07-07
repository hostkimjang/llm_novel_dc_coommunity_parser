import unittest

from tools.reaccount_residual_after_contract_reviews import build_accounting


class ReaccountResidualAfterContractReviewsTest(unittest.TestCase):
    def test_source_native_accept_exclusion_reduces_ordinary_residual_without_approval(self):
        residual_queue = {
            "queue_id": "unit_residual",
            "rows": [
                {
                    "post_id": 1,
                    "triage_bucket": "wrong_work_title_flip",
                    "review_label": "INFO_MISSING",
                    "actions": ["source_native_or_blind_review_required"],
                },
                {
                    "post_id": 2,
                    "triage_bucket": "wrong_work_title_flip",
                    "review_label": "REPROCESS",
                    "actions": ["repair_after_wrong_work"],
                },
            ],
        }
        contract_plan = {
            "plan_id": "unit_plan",
            "rows": [
                {
                    "post_id": 2,
                    "contract_action": "expected_title_restore_contract_case",
                    "target_title": "마도서를 줍다 마법사가 되다",
                    "target_url": "https://novelpia.com/novel/414963",
                }
            ],
        }
        application = {
            "projection_id": "unit_application",
            "applied_rows": [
                {
                    "post_id": 2,
                    "status": "applied",
                    "contract_action": "expected_title_restore_contract_case",
                }
            ],
        }
        source_native_review = {
            "review_id": "unit_source_native",
            "rows": [
                {
                    "post_id": 1,
                    "review_label": "ACCEPT",
                    "action": ["exclude_from_regression_count_after_gate_wiring"],
                }
            ],
        }

        accounting = build_accounting(
            residual_queue=residual_queue,
            contract_plan=contract_plan,
            expected_restore_application=application,
            source_native_review=source_native_review,
            accounting_id="unit",
        )

        summary = accounting["summary"]
        self.assertEqual(summary["contract_processed_rows"], 1)
        self.assertEqual(summary["source_native_processed_rows"], 1)
        self.assertEqual(summary["processed_or_excluded_rows"], 2)
        self.assertEqual(summary["ordinary_residual_unprocessed_rows"], 0)
        self.assertEqual(summary["source_native_exclusion_candidate_rows"], 1)
        self.assertFalse(accounting["full_scan_approval"])
        self.assertEqual(accounting["rows"][0]["contract_accounting_state"], "source_native_reviewed_exclusion_candidate")
        self.assertFalse(accounting["rows"][0]["publish_allowed"])


if __name__ == "__main__":
    unittest.main()
