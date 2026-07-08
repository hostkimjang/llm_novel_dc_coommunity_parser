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

    def test_policy_holds_reduce_ordinary_residual_without_approval(self):
        residual_queue = {
            "queue_id": "unit_residual",
            "rows": [
                {
                    "post_id": 11698859,
                    "triage_bucket": "safe_loss_resolved_to_null",
                    "review_label": "REPROCESS",
                    "actions": ["native_web_review_required"],
                },
                {
                    "post_id": 11698870,
                    "triage_bucket": "safe_loss_resolved_to_null",
                    "review_label": "REPROCESS",
                    "actions": ["official_detail_url_enrichment_required"],
                },
            ],
        }
        contract_plan = {
            "plan_id": "unit_plan",
            "rows": [
                {
                    "post_id": 11698859,
                    "contract_action": "native_web_disambiguation_hold_contract_case",
                    "target_title": "귤부인 대롱대롱",
                },
                {
                    "post_id": 11698870,
                    "contract_action": "non_webnovel_ebook_policy_hold_contract_case",
                    "target_title": "인간실격",
                },
            ],
        }

        accounting = build_accounting(
            residual_queue=residual_queue,
            contract_plan=contract_plan,
            accounting_id="unit",
        )

        summary = accounting["summary"]
        self.assertEqual(summary["contract_processed_rows"], 2)
        self.assertEqual(summary["ordinary_residual_unprocessed_rows"], 0)
        self.assertEqual(summary["native_web_disambiguation_hold_rows"], 1)
        self.assertEqual(summary["non_webnovel_ebook_policy_hold_rows"], 1)
        self.assertEqual(summary["release_candidate_not_approval_rows"], 0)
        self.assertEqual(summary["publish_allowed_rows"], 0)
        self.assertFalse(accounting["full_scan_approval"])
        self.assertEqual(
            accounting["rows"][0]["contract_accounting_state"],
            "contract_processed_native_web_disambiguation_hold_no_publish",
        )
        self.assertEqual(
            accounting["rows"][1]["contract_accounting_state"],
            "contract_processed_non_webnovel_ebook_policy_hold_no_publish",
        )

    def test_action_field_is_counted_when_actions_field_is_absent(self):
        residual_queue = {
            "queue_id": "unit_residual",
            "rows": [
                {
                    "post_id": 11694041,
                    "triage_bucket": "safe_loss_resolved_to_null",
                    "review_label": "REPROCESS",
                    "action": [
                        "shared_promotion_gate_wiring_required",
                        "official_detail_url_enrichment_required",
                    ],
                }
            ],
        }
        contract_plan = {
            "plan_id": "unit_plan",
            "rows": [
                {
                    "post_id": 11694041,
                    "contract_action": "expected_title_restore_contract_case",
                    "target_title": "격투 소설 엑스트라가 타격 천재임",
                    "target_url": "https://novelpia.com/novel/380507",
                }
            ],
        }
        application = {
            "projection_id": "unit_application",
            "applied_rows": [
                {
                    "post_id": 11694041,
                    "status": "applied",
                    "contract_action": "expected_title_restore_contract_case",
                }
            ],
        }

        accounting = build_accounting(
            residual_queue=residual_queue,
            contract_plan=contract_plan,
            expected_restore_application=application,
            accounting_id="unit",
        )

        action_counts = accounting["summary"]["source_action_counts"]
        self.assertEqual(action_counts["shared_promotion_gate_wiring_required"], 1)
        self.assertEqual(action_counts["official_detail_url_enrichment_required"], 1)
        self.assertEqual(
            accounting["rows"][0]["actions"],
            [
                "shared_promotion_gate_wiring_required",
                "official_detail_url_enrichment_required",
            ],
        )

    def test_release_audit_can_satisfy_candidate_set_hold_accounting(self):
        residual_queue = {
            "queue_id": "unit_residual",
            "rows": [
                {
                    "post_id": 11694035,
                    "triage_bucket": "safe_loss_resolved_to_null",
                    "review_label": "HOLD",
                    "actions": ["candidate_set_rebuild_required"],
                }
            ],
        }
        contract_plan = {
            "plan_id": "unit_plan",
            "rows": [
                {
                    "post_id": 11694035,
                    "contract_action": "candidate_set_rebuild_required_before_publish",
                    "target_title": None,
                }
            ],
        }
        release_gate_audit = {
            "audit_id": "unit_release_gate",
            "satisfied_no_release_rows": [
                {
                    "post_id": 11694035,
                    "release_gate_state": "candidate_set_rebuild_preserved_no_release",
                    "satisfied_no_release": True,
                    "violation": False,
                }
            ],
        }

        accounting = build_accounting(
            residual_queue=residual_queue,
            contract_plan=contract_plan,
            release_gate_audit=release_gate_audit,
            accounting_id="unit",
        )

        summary = accounting["summary"]
        self.assertEqual(summary["contract_processed_rows"], 1)
        self.assertEqual(summary["candidate_set_rebuild_hold_rows"], 1)
        self.assertEqual(summary["ordinary_residual_unprocessed_rows"], 0)
        self.assertEqual(summary["validation_issue_count"], 0)
        self.assertEqual(accounting["rows"][0]["policy_review_ref"], "unit_release_gate")

    def test_canonical_cleanup_counts_as_release_candidate_after_application(self):
        residual_queue = {
            "queue_id": "unit_residual",
            "rows": [
                {
                    "post_id": 11669907,
                    "triage_bucket": "safe_loss_resolved_to_null",
                    "review_label": "REPROCESS",
                    "actions": ["canonical_title_cleanup_required"],
                }
            ],
        }
        contract_plan = {
            "plan_id": "unit_plan",
            "rows": [
                {
                    "post_id": 11669907,
                    "contract_action": "canonical_cleanup_or_url_correction_contract_case",
                    "target_title": "마법 좋아좋아좋아",
                    "target_url": "https://novelpia.com/novel/326040",
                }
            ],
        }
        application = {
            "projection_id": "unit_application",
            "applied_rows": [
                {
                    "post_id": 11669907,
                    "contract_action": "canonical_cleanup_or_url_correction_contract_case",
                    "status": "applied",
                }
            ],
        }

        accounting = build_accounting(
            residual_queue=residual_queue,
            contract_plan=contract_plan,
            expected_restore_application=application,
            accounting_id="unit",
        )

        summary = accounting["summary"]
        self.assertEqual(summary["contract_processed_rows"], 1)
        self.assertEqual(summary["release_candidate_not_approval_rows"], 1)
        self.assertEqual(summary["canonical_cleanup_release_candidate_rows"], 1)
        self.assertEqual(summary["ordinary_residual_unprocessed_rows"], 0)
        self.assertEqual(summary["validation_issue_count"], 0)
        self.assertFalse(accounting["rows"][0]["publish_allowed"])


if __name__ == "__main__":
    unittest.main()
