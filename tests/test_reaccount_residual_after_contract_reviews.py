import unittest

from tools.reaccount_residual_after_contract_reviews import build_accounting


def _residual_row(post_id, **overrides):
    row = {
        "post_id": post_id,
        "triage_bucket": "safe_loss_resolved_to_null",
        "review_label": "REPROCESS",
        "source_native_verdict": "supported_safe_title_lost_to_null",
        "selected_title": "작품",
        "selected_option_id": "C1",
        "actions": ["repair_safe_loss_restore_supported_title", "shared_promotion_gate_wiring_required"],
        "loop546_transition": "runtime_expected_title_failure_remaining",
    }
    row.update(overrides)
    return row


def _plan_row(post_id, action, **overrides):
    row = {
        "post_id": post_id,
        "contract_action": action,
        "contract_batch_lane": "lane",
        "target_title": "작품",
        "current_projection_candidate_title": "후보",
    }
    row.update(overrides)
    return row


class ReaccountResidualAfterContractReviewsTest(unittest.TestCase):
    def test_contract_reviews_split_processed_and_ordinary_residual(self):
        accounting = build_accounting(
            residual_queue={
                "queue_id": "residual",
                "summary": {"residual_action_queue_rows": 5},
                "rows": [
                    _residual_row(1),
                    _residual_row(2),
                    _residual_row(3),
                    _residual_row(4),
                    _residual_row(5),
                ],
            },
            contract_plan={
                "plan_id": "plan",
                "rows": [
                    _plan_row(1, "expected_title_restore_contract_case"),
                    _plan_row(2, "candidate_scrub_no_publish_contract_case"),
                    _plan_row(3, "canonical_variant_policy_hold_contract_case"),
                    _plan_row(4, "stronger_evidence_hard_hold_contract_case"),
                ],
            },
            expected_restore_application={
                "projection_id": "restore",
                "applied_rows": [{"post_id": 1, "status": "applied"}],
            },
            variant_review={
                "review_id": "variant",
                "rows": [{"post_id": 3, "policy_decision": "canonical_variant_quarantine_no_publish"}],
            },
            c3_review={
                "review_id": "c3",
                "rows": [{"post_id": 4, "policy_decision": "stronger_evidence_native_web_hard_hold"}],
            },
            accounting_id="unit",
        )

        self.assertEqual(accounting["gate"], "REVIEW-LOCKED")
        self.assertEqual(accounting["summary"]["contract_processed_rows"], 4)
        self.assertEqual(accounting["summary"]["ordinary_residual_unprocessed_rows"], 1)
        self.assertEqual(accounting["summary"]["release_candidate_not_approval_rows"], 1)
        self.assertEqual(accounting["summary"]["no_publish_or_hold_contract_rows"], 3)
        self.assertEqual(accounting["summary"]["publish_allowed_rows"], 0)
        self.assertEqual(accounting["summary"]["runtime_replay_allowed_rows"], 0)
        self.assertFalse(accounting["full_scan_approval"])

    def test_missing_variant_review_is_validation_issue(self):
        accounting = build_accounting(
            residual_queue={"queue_id": "residual", "rows": [_residual_row(10)]},
            contract_plan={
                "plan_id": "plan",
                "rows": [_plan_row(10, "canonical_variant_policy_hold_contract_case")],
            },
            accounting_id="unit",
        )

        self.assertEqual(accounting["gate"], "NO-GO")
        self.assertEqual(accounting["summary"]["validation_issue_count"], 1)
        self.assertIn("canonical_variant_policy_review_missing", accounting["rows"][0]["validation_issues"])

    def test_expected_restore_without_application_is_not_closed(self):
        accounting = build_accounting(
            residual_queue={"queue_id": "residual", "rows": [_residual_row(20)]},
            contract_plan={
                "plan_id": "plan",
                "rows": [_plan_row(20, "expected_title_restore_contract_case")],
            },
            accounting_id="unit",
        )

        self.assertEqual(accounting["gate"], "NO-GO")
        self.assertFalse(accounting["rows"][0]["contract_processed"])
        self.assertIn("expected_restore_application_missing", accounting["rows"][0]["validation_issues"])

    def test_restore_target_runtime_mismatch_returns_to_source_native_review(self):
        accounting = build_accounting(
            residual_queue={"queue_id": "residual", "rows": [_residual_row(25)]},
            contract_plan={
                "plan_id": "plan",
                "rows": [_plan_row(25, "restore_target_runtime_mismatch_review_required")],
            },
            accounting_id="unit",
        )

        row = accounting["rows"][0]
        self.assertEqual(accounting["gate"], "REVIEW-LOCKED")
        self.assertFalse(row["contract_processed"])
        self.assertTrue(row["ordinary_residual_unprocessed"])
        self.assertEqual(row["contract_accounting_effect"], "restore_target_mismatch_source_native_review_required")
        self.assertIn("source_native_or_blind_review_required", row["actions"])
        self.assertEqual(accounting["summary"]["restore_target_mismatch_review_rows"], 1)

    def test_dispatch_source_and_application_ref_are_preserved(self):
        accounting = build_accounting(
            residual_queue={"dispatch_id": "ordinary_dispatch", "rows": [_residual_row(30)]},
            contract_plan={
                "plan_id": "ordinary_restore_plan",
                "rows": [_plan_row(30, "expected_title_restore_contract_case")],
            },
            expected_restore_application={
                "projection_id": "ordinary_restore_application",
                "applied_rows": [{"post_id": 30, "status": "applied"}],
            },
            accounting_id="unit",
        )

        self.assertEqual(accounting["source_residual_queue"], "ordinary_dispatch")
        self.assertEqual(accounting["rows"][0]["policy_review_ref"], "ordinary_restore_application")
        self.assertEqual(accounting["summary"]["contract_processed_rows"], 1)
        self.assertEqual(accounting["summary"]["ordinary_residual_unprocessed_rows"], 0)

    def test_official_support_missing_restore_hold_stays_unprocessed_followup(self):
        accounting = build_accounting(
            residual_queue={
                "queue_id": "residual",
                "summary": {"residual_action_queue_rows": 1},
                "rows": [_residual_row(40, actions=["repair_safe_loss_restore_supported_title"])],
            },
            contract_plan={
                "plan_id": "plan",
                "rows": [
                    _plan_row(
                        40,
                        "official_support_missing_restore_hold_contract_case",
                        target_title="Expected Work",
                    )
                ],
            },
            accounting_id="unit",
        )

        row = accounting["rows"][0]
        self.assertEqual(accounting["gate"], "REVIEW-LOCKED")
        self.assertEqual(accounting["summary"]["validation_issue_count"], 0)
        self.assertEqual(accounting["summary"]["contract_processed_rows"], 0)
        self.assertEqual(accounting["summary"]["ordinary_residual_unprocessed_rows"], 1)
        self.assertEqual(accounting["summary"]["official_support_missing_restore_followup_rows"], 1)
        self.assertFalse(row["contract_processed"])
        self.assertTrue(row["ordinary_residual_unprocessed"])
        self.assertEqual(row["contract_accounting_effect"], "official_support_missing_restore_followup_required")
        self.assertIn("official_detail_url_enrichment_required", row["actions"])

    def test_candidate_set_rebuild_hold_with_application_is_processed_no_publish(self):
        accounting = build_accounting(
            residual_queue={
                "queue_id": "residual",
                "summary": {"residual_action_queue_rows": 1},
                "rows": [_residual_row(50, actions=["candidate_set_rebuild_required"])],
            },
            contract_plan={
                "plan_id": "candidate_set_plan",
                "rows": [
                    _plan_row(
                        50,
                        "candidate_set_rebuild_required_before_publish",
                        target_title=None,
                    )
                ],
            },
            expected_restore_application={
                "projection_id": "candidate_set_application",
                "applied_rows": [{"post_id": 50, "status": "scrubbed_public_identity"}],
            },
            accounting_id="unit",
        )

        row = accounting["rows"][0]
        self.assertEqual(accounting["gate"], "REVIEW-LOCKED")
        self.assertEqual(accounting["summary"]["contract_processed_rows"], 1)
        self.assertEqual(accounting["summary"]["ordinary_residual_unprocessed_rows"], 0)
        self.assertEqual(accounting["summary"]["candidate_set_rebuild_hold_rows"], 1)
        self.assertEqual(accounting["summary"]["no_publish_or_hold_contract_rows"], 1)
        self.assertTrue(row["contract_processed"])
        self.assertFalse(row["ordinary_residual_unprocessed"])
        self.assertEqual(row["contract_accounting_effect"], "candidate_set_rebuild_hold_not_approval")
        self.assertEqual(row["policy_review_ref"], "candidate_set_application")


if __name__ == "__main__":
    unittest.main()
