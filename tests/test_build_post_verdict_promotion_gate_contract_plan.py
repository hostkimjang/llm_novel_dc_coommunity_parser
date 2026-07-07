import unittest

from tools.build_post_verdict_promotion_gate_contract_plan import build_plan


class BuildPostVerdictPromotionGateContractPlanTest(unittest.TestCase):
    def test_c1_recovered_expected_title_becomes_restore_contract_case(self):
        queue = {
            "queue_id": "unit",
            "rows": [
                {
                    "post_id": 1,
                    "contract_batch_lane": "C1_expected_restore_or_candidate_scrub_contract",
                    "canonical_verdict": "EXPECTED_SOURCE_NATIVE_TITLE_CONFIRMED",
                    "evidence_grade": "Strong",
                    "canonical_title": "Expected Work",
                    "current_projection_candidate_title": "Wrong Candidate",
                    "search_gate": "SEARCH_RECOVERED_CONDITIONAL",
                    "rationale_ko": "원문이 expected 작품을 직접 지지한다.",
                }
            ],
        }

        plan = build_plan(queue, plan_id="unit")
        row = plan["rows"][0]

        self.assertEqual(plan["gate"], "REVIEW-LOCKED")
        self.assertEqual(row["contract_action"], "expected_title_restore_contract_case")
        self.assertEqual(row["promotion_decision"]["status"], "publish")
        self.assertTrue(row["promotion_decision"]["publish_allowed"])
        self.assertFalse(row["runtime_replay_allowed"])
        self.assertEqual(plan["summary"]["runtime_replay_allowed_rows"], 0)

    def test_c1_search_blind_expected_title_stays_scrub_contract_case(self):
        queue = {
            "queue_id": "unit",
            "rows": [
                {
                    "post_id": 2,
                    "contract_batch_lane": "C1_expected_restore_or_candidate_scrub_contract",
                    "canonical_verdict": "EXPECTED_SOURCE_NATIVE_TITLE_CONFIRMED",
                    "evidence_grade": "Strong",
                    "canonical_title": "Expected Work",
                    "current_projection_candidate_title": "Wrong Candidate",
                    "search_gate": "SEARCH_BLIND_BLOCKER",
                }
            ],
        }

        plan = build_plan(queue, plan_id="unit")
        row = plan["rows"][0]

        self.assertEqual(row["contract_action"], "candidate_scrub_no_publish_contract_case")
        self.assertEqual(row["contract_blocking_reason"], "search_blind_condition")
        self.assertEqual(row["promotion_decision"]["status"], "candidate_only")
        self.assertFalse(row["promotion_decision"]["publish_allowed"])
        self.assertIn("search_blind_condition", row["promotion_decision"]["reason_codes"])

    def test_c2_variant_policy_blocks_publish_even_for_current_work(self):
        queue = {
            "queue_id": "unit",
            "rows": [
                {
                    "post_id": 3,
                    "contract_batch_lane": "C2_canonical_variant_policy_contract",
                    "canonical_verdict": "RELATED_CANONICAL_VARIANT_CONFIRMED",
                    "evidence_grade": "Medium",
                    "canonical_title": "Canonical Work",
                    "current_projection_candidate_title": "Variant",
                    "search_gate": "SEARCH_RECOVERED_CONDITIONAL",
                }
            ],
        }

        plan = build_plan(queue, plan_id="unit")
        row = plan["rows"][0]

        self.assertEqual(row["contract_action"], "canonical_variant_policy_hold_contract_case")
        self.assertEqual(row["contract_blocking_reason"], "canonical_variant_policy_pending")
        self.assertEqual(row["promotion_decision"]["status"], "candidate_only")
        self.assertFalse(row["promotion_decision"]["publish_allowed"])
        self.assertIn("canonical_variant_policy_pending", row["promotion_decision"]["reason_codes"])

    def test_c3_stronger_evidence_hold_stays_candidate_only(self):
        queue = {
            "queue_id": "unit",
            "rows": [
                {
                    "post_id": 4,
                    "contract_batch_lane": "C3_stronger_evidence_or_native_web_hold",
                    "canonical_verdict": "INSUFFICIENT_EVIDENCE_HOLD",
                    "evidence_grade": "Weak",
                    "expected_or_source_native_title": "Unproven Candidate",
                    "current_projection_candidate_title": "Other Candidate",
                    "search_gate": "SEARCH_OK",
                }
            ],
        }

        plan = build_plan(queue, plan_id="unit")
        row = plan["rows"][0]

        self.assertEqual(row["contract_action"], "stronger_evidence_hard_hold_contract_case")
        self.assertEqual(row["contract_blocking_reason"], "stronger_evidence_required")
        self.assertFalse(row["contract_test_required_before_runtime"])
        self.assertTrue(row["stronger_evidence_required_before_runtime"])
        self.assertEqual(row["promotion_decision"]["status"], "candidate_only")
        self.assertFalse(row["promotion_decision"]["publish_allowed"])


if __name__ == "__main__":
    unittest.main()
