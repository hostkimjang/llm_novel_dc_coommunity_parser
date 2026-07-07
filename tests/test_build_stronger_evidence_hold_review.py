import unittest

from tools.build_stronger_evidence_hold_review import build_review


def _c3_plan_row(**overrides):
    row = {
        "post_id": 1,
        "contract_batch_lane": "C3_stronger_evidence_or_native_web_hold",
        "canonical_verdict": "INSUFFICIENT_EVIDENCE_HOLD",
        "search_gate": "SEARCH_BLIND_BLOCKER",
        "evidence_grade": "Medium",
        "target_title": "퍼펙트 메이지",
        "target_url": None,
        "current_projection_candidate_title": "죽었다 깨어도 수선",
        "current_projection_candidate_url": "https://novelpia.com/novel/233173",
        "contract_action": "stronger_evidence_hard_hold_contract_case",
        "promotion_decision": {
            "status": "candidate_only",
            "publish_allowed": False,
            "reason_codes": [
                "official_title_exists",
                "row_discussion_missing",
                "context_only",
                "scope_not_current_work",
                "stronger_evidence_required",
            ],
            "bypassed_gate": False,
        },
        "runtime_replay_allowed": False,
        "stronger_evidence_required_before_runtime": True,
        "rationale_ko": "이미지/캐릭터 장면은 가능성을 주지만 native-web/시각 근거 강화 전 hard-hold로 둔다.",
    }
    row.update(overrides)
    return row


class BuildStrongerEvidenceHoldReviewTest(unittest.TestCase):
    def test_c3_hold_keeps_no_publish_even_with_prior_reprocess(self):
        review = build_review(
            contract_plan={"plan_id": "unit", "rows": [_c3_plan_row()]},
            contract_queue={
                "queue_id": "queue",
                "rows": [
                    {
                        "post_id": 1,
                        "expected_or_source_native_title": "퍼펙트 메이지",
                        "search_gate": "SEARCH_BLIND_BLOCKER",
                    }
                ],
            },
            prior_verdicts=[
                {
                    "review_id": "prior",
                    "rows": [
                        {
                            "post_id": 1,
                            "source_native_verdict": "title_parenthetical_and_character_scene_support_safe_title",
                            "review_label": "REPROCESS",
                            "action": ["repair_safe_loss_restore_supported_title"],
                        }
                    ],
                }
            ],
            review_id="unit",
        )

        self.assertEqual(review["gate"], "REVIEW-LOCKED")
        self.assertEqual(review["summary"]["hard_hold_review_rows"], 1)
        self.assertEqual(review["summary"]["prior_restore_conflict_rows"], 1)
        self.assertEqual(review["summary"]["publish_allowed_rows"], 0)
        self.assertEqual(review["summary"]["runtime_replay_allowed_rows"], 0)
        row = review["rows"][0]
        self.assertEqual(row["policy_decision"], "stronger_evidence_native_web_hard_hold")
        self.assertEqual(row["hold_reason"], "competing_candidate_image_or_character_bridge_required")
        self.assertTrue(row["prior_restore_conflict"])
        self.assertFalse(row["prior_restore_is_release_authority"])
        self.assertTrue(row["native_web_or_blind_judge_required"])
        self.assertFalse(row["publish_allowed"])

    def test_generic_system_trope_requires_direct_title_evidence(self):
        review = build_review(
            contract_plan={
                "plan_id": "unit",
                "rows": [
                    _c3_plan_row(
                        post_id=2,
                        search_gate="SEARCH_EVIDENCE_MISSING",
                        target_title="설정값 딸깍으로 판타지 시스템 정상화",
                        current_projection_candidate_title="시스템",
                        current_projection_candidate_url=None,
                        rationale_ko="시스템 딸깍, 상태창, 파이어볼 같은 장르/클리셰 비평이다.",
                    )
                ],
            },
            review_id="unit",
        )

        self.assertEqual(review["summary"]["search_recovery_required_rows"], 1)
        self.assertEqual(review["rows"][0]["hold_reason"], "generic_system_trope_direct_title_missing")
        self.assertFalse(review["full_scan_approval"])

    def test_publish_allowed_before_stronger_evidence_is_validation_issue(self):
        bad_row = _c3_plan_row(
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
        self.assertIn("hard_hold_plan_publish_allowed", review["rows"][0]["validation_issues"])
        self.assertIn("hard_hold_plan_not_candidate_only", review["rows"][0]["validation_issues"])
        self.assertIn("stronger_evidence_required_reason_missing", review["rows"][0]["validation_issues"])

    def test_wrong_lane_with_c3_action_is_validation_issue(self):
        review = build_review(
            contract_plan={"plan_id": "unit", "rows": [_c3_plan_row(contract_batch_lane="C2_canonical_variant_policy_contract")]},
            review_id="unit",
        )

        self.assertEqual(review["gate"], "NO-GO")
        self.assertEqual(review["summary"]["source_c3_rows"], 1)
        self.assertIn("not_stronger_evidence_hold_lane", review["rows"][0]["validation_issues"])


if __name__ == "__main__":
    unittest.main()
