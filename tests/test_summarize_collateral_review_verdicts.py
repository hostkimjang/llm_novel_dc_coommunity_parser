import unittest

from tools.summarize_collateral_review_verdicts import build_summary


class SummarizeCollateralReviewVerdictsTest(unittest.TestCase):
    def test_validates_selected_options_and_counts_labels(self):
        batch = {
            "review_rows": [
                {
                    "post_id": 1,
                    "triage_bucket": "wrong_work_title_flip",
                    "collateral_status": "resolved_to_different_title",
                    "blind_judge_options": [{"option_id": "C1"}, {"option_id": "C2"}],
                    "source_native_packet": {"post_title": "post one"},
                    "comparison_private_not_for_blind_judge": {
                        "before_triage_identity": {"official_title": "A"},
                        "after_triage_identity": {"official_title": "B"},
                    },
                }
            ]
        }
        verdicts = {
            "review_id": "unit",
            "rows": [
                {
                    "post_id": 1,
                    "selected_option_id": "C1",
                    "selected_title": "A",
                    "review_label": "REPROCESS",
                    "source_native_verdict": "before_correct_after_wrong",
                    "evidence_grade": "Medium",
                    "action": ["repair_after_wrong_work"],
                    "rationale_ko": "원문은 A를 지지한다.",
                    "evidence_refs": ["unit://source"],
                }
            ],
        }

        summary = build_summary(batch=batch, verdicts=verdicts, generated_at="2026-07-02T00:00:00")

        self.assertEqual(summary["gate"], "REVIEW-LOCKED")
        self.assertEqual(summary["summary"]["batch_review_rows"], 1)
        self.assertEqual(summary["summary"]["reviewed_rows"], 1)
        self.assertEqual(summary["summary"]["unreviewed_batch_rows"], 0)
        self.assertEqual(summary["summary"]["counts_by_bucket"], {"wrong_work_title_flip": 1})
        self.assertEqual(summary["summary"]["label_counts"]["REPROCESS"], 1)
        self.assertEqual(summary["summary"]["action_counts"]["repair_after_wrong_work"], 1)
        self.assertFalse(summary["full_scan_approval"])

    def test_summarizes_non_wrong_work_bucket(self):
        batch = {
            "review_rows": [
                {
                    "post_id": 2,
                    "triage_bucket": "unsafe_promotion_from_hold",
                    "collateral_status": "null_to_resolved",
                    "blind_judge_options": [{"option_id": "C1"}],
                    "source_native_packet": {"post_title": "post two"},
                    "comparison_private_not_for_blind_judge": {
                        "before_triage_identity": {"official_title": None},
                        "after_triage_identity": {"official_title": "C"},
                    },
                }
            ]
        }
        verdicts = {
            "review_id": "unit_unsafe",
            "scope": "Loop unit unsafe promotion review",
            "rows": [
                {
                    "post_id": 2,
                    "selected_option_id": "HOLD",
                    "selected_title": None,
                    "review_label": "REPROCESS",
                    "source_native_verdict": "after_wrong_hold_preferred",
                    "evidence_grade": "Strong",
                    "action": ["repair_unsafe_promotion"],
                    "rationale_ko": "원문만으로 C를 확정할 수 없다.",
                    "evidence_refs": ["unit://source"],
                }
            ],
        }

        summary = build_summary(batch=batch, verdicts=verdicts, generated_at="2026-07-02T00:00:00")

        self.assertEqual(summary["report_type"], "collateral_source_native_review")
        self.assertEqual(summary["scope"], "Loop unit unsafe promotion review")
        self.assertEqual(summary["summary"]["counts_by_bucket"], {"unsafe_promotion_from_hold": 1})
        self.assertEqual(summary["summary"]["action_counts"]["repair_unsafe_promotion"], 1)
        self.assertEqual(summary["gate"], "REVIEW-LOCKED")

    def test_partial_review_reports_unreviewed_rows(self):
        batch = {
            "review_rows": [
                {"post_id": 1, "blind_judge_options": [{"option_id": "C1"}], "source_native_packet": {}},
                {"post_id": 2, "blind_judge_options": [{"option_id": "C1"}], "source_native_packet": {}},
            ]
        }
        verdicts = {
            "review_id": "partial",
            "rows": [
                {
                    "post_id": 1,
                    "selected_option_id": "HOLD",
                    "review_label": "REPROCESS",
                    "source_native_verdict": "after_wrong_hold_preferred",
                    "evidence_refs": ["unit://source"],
                }
            ],
        }

        summary = build_summary(batch=batch, verdicts=verdicts, generated_at="2026-07-02T00:00:00")

        self.assertEqual(summary["summary"]["batch_review_rows"], 2)
        self.assertEqual(summary["summary"]["reviewed_rows"], 1)
        self.assertEqual(summary["summary"]["unreviewed_batch_rows"], 1)

    def test_invalid_selected_option_keeps_no_go(self):
        batch = {
            "review_rows": [
                {
                    "post_id": 1,
                    "blind_judge_options": [{"option_id": "C1"}],
                    "source_native_packet": {},
                    "comparison_private_not_for_blind_judge": {},
                }
            ]
        }
        verdicts = {
            "review_id": "unit",
            "rows": [
                {
                    "post_id": 1,
                    "selected_option_id": "C9",
                    "review_label": "ACCEPT",
                    "source_native_verdict": "after_correct",
                    "evidence_refs": ["unit://source"],
                }
            ],
        }

        summary = build_summary(batch=batch, verdicts=verdicts, generated_at="2026-07-02T00:00:00")

        self.assertEqual(summary["gate"], "NO-GO")
        self.assertEqual(summary["summary"]["validation_issue_count"], 1)
        self.assertEqual(summary["validation_issues"][0]["issues"], ["selected_option_id_not_in_batch_options"])


if __name__ == "__main__":
    unittest.main()
