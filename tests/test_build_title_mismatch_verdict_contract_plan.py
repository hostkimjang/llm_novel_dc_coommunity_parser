import unittest

from tools.build_title_mismatch_verdict_contract_plan import build_plan


class BuildTitleMismatchVerdictContractPlanTest(unittest.TestCase):
    def test_accept_is_expected_audit_update_contract_case(self):
        verdicts = {
            "review_id": "unit_title_mismatch",
            "rows": [
                {
                    "post_id": 1,
                    "review_label": "ACCEPT",
                    "expected_title": "Expected Question Surface",
                    "actual_title": "Actual Work",
                    "selected_title": "Actual Work",
                    "selected_url": "https://novelpia.com/novel/1",
                    "source_native_verdict": "actual_title_correct",
                    "evidence_grade": "Strong",
                    "rationale_ko": "이미지 OCR이 실제 작품명을 직접 지지한다.",
                }
            ],
        }

        plan = build_plan(verdicts, plan_id="unit")
        row = plan["rows"][0]

        self.assertEqual(plan["gate"], "REVIEW-LOCKED")
        self.assertEqual(row["contract_action"], "expected_audit_update_exclusion_contract_case")
        self.assertEqual(row["promotion_decision"]["status"], "publish")
        self.assertTrue(row["promotion_decision"]["publish_allowed"])
        self.assertFalse(row["runtime_replay_allowed"])
        self.assertEqual(plan["summary"]["runtime_replay_allowed_rows"], 0)

    def test_hold_requires_native_web_disambiguation(self):
        verdicts = {
            "review_id": "unit_title_mismatch",
            "rows": [
                {
                    "post_id": 2,
                    "review_label": "HOLD",
                    "expected_title": "Expected Work",
                    "actual_title": "Competing Work",
                    "source_native_verdict": "alias_competition",
                    "evidence_grade": "Medium",
                }
            ],
        }

        plan = build_plan(verdicts, plan_id="unit")
        row = plan["rows"][0]

        self.assertEqual(row["contract_action"], "native_web_disambiguation_hold_contract_case")
        self.assertEqual(row["contract_blocking_reason"], "native_web_disambiguation_required")
        self.assertEqual(row["promotion_decision"]["status"], "candidate_only")
        self.assertFalse(row["promotion_decision"]["publish_allowed"])
        self.assertTrue(row["stronger_evidence_required_before_runtime"])

    def test_reprocess_requires_cleanup_before_runtime(self):
        verdicts = {
            "review_id": "unit_title_mismatch",
            "rows": [
                {
                    "post_id": 3,
                    "review_label": "REPROCESS",
                    "expected_title": "Clean Canonical",
                    "actual_title": "Contaminated Candidate",
                    "source_native_verdict": "candidate_url_contaminated",
                    "evidence_grade": "Strong",
                }
            ],
        }

        plan = build_plan(verdicts, plan_id="unit")
        row = plan["rows"][0]

        self.assertEqual(row["contract_action"], "canonical_cleanup_or_url_correction_contract_case")
        self.assertEqual(row["target_title"], "Clean Canonical")
        self.assertEqual(row["contract_blocking_reason"], "canonical_cleanup_required")
        self.assertEqual(row["promotion_decision"]["status"], "candidate_only")
        self.assertTrue(row["contract_test_required_before_runtime"])
        self.assertFalse(row["runtime_replay_allowed"])

    def test_unknown_label_is_no_go(self):
        verdicts = {
            "review_id": "unit_title_mismatch",
            "rows": [
                {
                    "post_id": 4,
                    "review_label": "MAYBE",
                    "expected_title": "",
                    "actual_title": "",
                }
            ],
        }

        plan = build_plan(verdicts, plan_id="unit")

        self.assertEqual(plan["gate"], "NO-GO")
        self.assertEqual(plan["summary"]["validation_issue_count"], 1)
        self.assertIn("unknown_review_label", plan["validation_issues"][0]["issues"])
        self.assertIn("missing_target_title", plan["validation_issues"][0]["issues"])


if __name__ == "__main__":
    unittest.main()
