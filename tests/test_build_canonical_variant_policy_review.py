import unittest

from tools.build_canonical_variant_policy_review import build_review


def _variant_plan_row(**overrides):
    row = {
        "post_id": 1,
        "contract_batch_lane": "C2_canonical_variant_policy_contract",
        "canonical_verdict": "RELATED_CANONICAL_VARIANT_CONFIRMED",
        "search_gate": "SEARCH_RECOVERED_CONDITIONAL",
        "evidence_grade": "Medium",
        "target_title": "도굴왕",
        "target_url": "https://page.kakao.com/content/53190884",
        "current_projection_candidate_title": "도굴왕 1 |",
        "current_projection_candidate_url": None,
        "contract_action": "canonical_variant_policy_hold_contract_case",
        "promotion_decision": {
            "status": "candidate_only",
            "publish_allowed": False,
            "reason_codes": [
                "official_title_exists",
                "row_discusses_work_as_work",
                "scope_current_work",
                "canonical_variant_policy_pending",
            ],
            "bypassed_gate": False,
        },
        "runtime_replay_allowed": False,
        "rationale_ko": "같은 작품 계열의 오염 표기 variant다.",
    }
    row.update(overrides)
    return row


class BuildCanonicalVariantPolicyReviewTest(unittest.TestCase):
    def test_variant_policy_keeps_no_publish_and_marks_exclusion_candidate(self):
        review = build_review(
            contract_plan={"plan_id": "unit", "rows": [_variant_plan_row()]},
            contract_queue={
                "queue_id": "queue",
                "rows": [
                    {
                        "post_id": 1,
                        "expected_or_source_native_title": "도굴왕 1 |",
                    }
                ],
            },
            review_id="unit",
        )

        self.assertEqual(review["gate"], "REVIEW-LOCKED")
        self.assertEqual(review["summary"]["policy_review_rows"], 1)
        self.assertEqual(review["summary"]["regression_exclusion_candidate_rows"], 1)
        self.assertEqual(review["summary"]["publish_allowed_rows"], 0)
        self.assertEqual(review["summary"]["runtime_replay_allowed_rows"], 0)
        row = review["rows"][0]
        self.assertEqual(row["policy_decision"], "canonical_variant_quarantine_no_publish")
        self.assertEqual(row["variant_relation"], "partial_or_abbreviation_variant")
        self.assertFalse(row["publish_allowed"])
        self.assertFalse(row["runtime_replay_allowed"])

    def test_search_blind_variant_is_conditional_not_approval(self):
        review = build_review(
            contract_plan={
                "plan_id": "unit",
                "rows": [
                    _variant_plan_row(
                        post_id=2,
                        search_gate="SEARCH_BLIND_BLOCKER",
                        target_title="황제의 딸로 환생했습니다",
                        current_projection_candidate_title="황제의 딸로 환생했습니다",
                    )
                ],
            },
            review_id="unit",
        )

        self.assertEqual(review["summary"]["search_blind_conditional_rows"], 1)
        self.assertEqual(review["summary"]["regression_exclusion_candidate_rows"], 1)
        self.assertTrue(review["rows"][0]["search_blind_conditional"])
        self.assertEqual(review["rows"][0]["variant_relation"], "current_candidate_matches_clean_canonical")
        self.assertFalse(review["full_scan_approval"])

    def test_publish_allowed_before_policy_is_validation_issue(self):
        bad_row = _variant_plan_row(
            promotion_decision={
                "status": "publish",
                "publish_allowed": True,
                "reason_codes": ["official_title_exists", "row_discusses_work_as_work"],
            }
        )
        review = build_review(
            contract_plan={"plan_id": "unit", "rows": [bad_row]},
            review_id="unit",
        )

        self.assertEqual(review["gate"], "NO-GO")
        self.assertEqual(review["summary"]["validation_issue_count"], 1)
        self.assertIn("variant_plan_publish_allowed_before_policy", review["rows"][0]["validation_issues"])
        self.assertIn("variant_plan_not_candidate_only", review["rows"][0]["validation_issues"])
        self.assertIn("variant_policy_pending_reason_missing", review["rows"][0]["validation_issues"])

    def test_missing_canonical_title_is_validation_issue(self):
        review = build_review(
            contract_plan={"plan_id": "unit", "rows": [_variant_plan_row(target_title="")]},
            review_id="unit",
        )

        self.assertEqual(review["gate"], "NO-GO")
        self.assertIn("missing_target_canonical_title", review["rows"][0]["validation_issues"])


if __name__ == "__main__":
    unittest.main()
