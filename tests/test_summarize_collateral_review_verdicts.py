import unittest

from tools.summarize_collateral_review_verdicts import build_combined_summary, build_summary


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
        self.assertEqual(summary["summary"]["queue_transition"]["original_p0_rows"], 2)
        self.assertEqual(summary["summary"]["queue_transition"]["residual_action_queue_rows"], 2)

    def test_info_missing_is_not_counted_as_source_native_decision(self):
        batch = {
            "review_rows": [
                {"post_id": 1, "blind_judge_options": [{"option_id": "C1"}], "source_native_packet": {}},
                {"post_id": 2, "blind_judge_options": [{"option_id": "C1"}], "source_native_packet": {}},
            ]
        }
        verdicts = {
            "review_id": "info_missing",
            "rows": [
                {
                    "post_id": 1,
                    "selected_option_id": "C1",
                    "review_label": "ACCEPT",
                    "source_native_verdict": "after_correct",
                    "action": ["exclude_from_regression_count_after_gate_wiring"],
                    "evidence_refs": ["unit://source"],
                },
                {
                    "post_id": 2,
                    "selected_option_id": "HOLD",
                    "review_label": "INFO_MISSING",
                    "source_native_verdict": "current_regression_row_without_compatible_prior_verdict",
                    "action": ["source_native_or_blind_review_required"],
                    "evidence_refs": ["unit://source"],
                },
            ],
        }

        summary = build_summary(batch=batch, verdicts=verdicts, generated_at="2026-07-02T00:00:00")

        counts = summary["summary"]
        transition = counts["queue_transition"]
        self.assertEqual(counts["reviewed_rows"], 2)
        self.assertEqual(counts["source_native_decision_rows"], 1)
        self.assertEqual(counts["info_missing_rows"], 1)
        self.assertEqual(counts["unreviewed_or_info_missing_batch_rows"], 1)
        self.assertEqual(transition["source_native_reviewed_rows"], 2)
        self.assertEqual(transition["source_native_decision_rows"], 1)
        self.assertEqual(transition["info_missing_rows"], 1)
        self.assertEqual(counts["queue_by_bucket"][""]["info_missing_rows"], 1)

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

    def test_combined_verdicts_report_residual_action_queue(self):
        batch = {
            "review_rows": [
                {
                    "post_id": 1,
                    "triage_bucket": "wrong_work_title_flip",
                    "collateral_status": "resolved_to_different_title",
                    "blind_judge_options": [{"option_id": "C1"}],
                    "source_native_packet": {},
                    "comparison_private_not_for_blind_judge": {},
                },
                {
                    "post_id": 2,
                    "triage_bucket": "safe_loss_resolved_to_null",
                    "collateral_status": "resolved_to_null",
                    "blind_judge_options": [{"option_id": "C1"}],
                    "source_native_packet": {},
                    "comparison_private_not_for_blind_judge": {},
                },
            ]
        }
        verdicts_list = [
            {
                "review_id": "wrong_work",
                "rows": [
                    {
                        "post_id": 1,
                        "selected_option_id": "C1",
                        "review_label": "REPROCESS",
                        "source_native_verdict": "before_correct_after_wrong",
                        "action": ["repair_after_wrong_work"],
                        "evidence_refs": ["unit://source"],
                    }
                ],
            },
            {
                "review_id": "safe_loss",
                "rows": [
                    {
                        "post_id": 2,
                        "selected_option_id": "HOLD",
                        "review_label": "ACCEPT",
                        "source_native_verdict": "after_hold_preferred_wrong_before_title",
                        "action": ["exclude_from_regression_count_after_gate_wiring"],
                        "evidence_refs": ["unit://source"],
                    }
                ],
            },
        ]

        summary = build_combined_summary(
            batch=batch,
            verdicts_list=verdicts_list,
            generated_at="2026-07-03T00:00:00",
            review_id="combined",
            scope="combined collateral review",
            source_batch="unit_batch.json",
        )

        transition = summary["summary"]["queue_transition"]
        self.assertEqual(summary["gate"], "REVIEW-LOCKED")
        self.assertEqual(summary["summary"]["batch_review_rows"], 2)
        self.assertEqual(summary["summary"]["reviewed_rows"], 2)
        self.assertEqual(transition["exclusion_candidate_rows"], 1)
        self.assertEqual(transition["repair_required_rows"], 1)
        self.assertEqual(transition["residual_action_queue_rows"], 1)
        self.assertEqual(summary["summary"]["queue_by_bucket"]["safe_loss_resolved_to_null"]["residual_action_queue_rows"], 0)

    def test_duplicate_post_id_in_combined_verdicts_keeps_no_go(self):
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
        verdicts_list = [
            {
                "review_id": "first",
                "rows": [
                    {
                        "post_id": 1,
                        "selected_option_id": "C1",
                        "review_label": "ACCEPT",
                        "source_native_verdict": "after_correct",
                        "evidence_refs": ["unit://source"],
                    }
                ],
            },
            {
                "review_id": "second",
                "rows": [
                    {
                        "post_id": 1,
                        "selected_option_id": "C1",
                        "review_label": "ACCEPT",
                        "source_native_verdict": "after_correct",
                        "evidence_refs": ["unit://source"],
                    }
                ],
            },
        ]

        summary = build_combined_summary(batch=batch, verdicts_list=verdicts_list)

        self.assertEqual(summary["gate"], "NO-GO")
        self.assertEqual(summary["validation_issues"][0]["issues"], ["duplicate_verdict_post_id"])


if __name__ == "__main__":
    unittest.main()
