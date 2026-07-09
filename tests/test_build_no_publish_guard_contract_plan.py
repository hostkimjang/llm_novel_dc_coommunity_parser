import unittest

from tools.build_no_publish_guard_contract_plan import build_plan


class BuildNoPublishGuardContractPlanTest(unittest.TestCase):
    def test_builds_no_publish_contracts_from_guard_lane(self):
        batch = {
            "dispatch_id": "unit_residual15",
            "rows": [
                {
                    "post_id": 1,
                    "primary_lane": "no_publish_multiwork_guard_review",
                    "triage_bucket": "safe_loss_resolved_to_null",
                    "review_label": "HOLD",
                    "source_native_verdict": "non_webnovel_classic_policy_hold",
                    "selected_title": "인간실격",
                    "evidence_grade": "Medium",
                    "actions": [
                        "wrong_work_or_cross_media_policy_hold_required",
                        "blind_or_policy_judge_required",
                    ],
                    "rationale_ko": "고전 문학 표면이라 웹소설 publish 범위 밖이다.",
                },
                {
                    "post_id": 2,
                    "primary_lane": "no_publish_multiwork_guard_review",
                    "triage_bucket": "safe_loss_resolved_to_null",
                    "review_label": "REJECT",
                    "source_native_verdict": "codex_native_web_judge_reject_wrong_work",
                    "selected_title": "너의 이름은.",
                    "evidence_grade": "Strong",
                    "actions": ["wrong_work_or_cross_media_policy_hold_required"],
                    "rationale_ko": "교차매체 wrong-work 오매칭이다.",
                },
                {
                    "post_id": 3,
                    "primary_lane": "native_web_image_evidence_review",
                    "selected_title": "Ignored",
                },
            ],
        }

        plan = build_plan(batch, plan_id="unit")

        self.assertEqual(plan["gate"], "REVIEW-LOCKED")
        self.assertEqual(plan["summary"]["no_publish_contract_plan_rows"], 2)
        self.assertEqual(
            plan["summary"]["contract_action_counts"],
            {"no_publish_intent_guard_contract_case": 2},
        )
        self.assertEqual(plan["summary"]["promotion_decision_status_counts"], {"candidate_only": 2})
        self.assertEqual(plan["summary"]["label_counts"], {"HOLD": 1, "REJECT": 1})
        self.assertEqual(
            plan["summary"]["completion_gate"],
            "adjusted full375 collateral GO + full_scan path",
        )
        for row in plan["rows"]:
            self.assertEqual(row["contract_action"], "no_publish_intent_guard_contract_case")
            self.assertFalse(row["promotion_decision"]["publish_allowed"])
            self.assertFalse(row["runtime_replay_allowed"])
            self.assertIn("scope_platform_meta_nonwork", row["promotion_decision"]["reason_codes"])

    def test_ordinary_dispatch_primary_lane_is_required(self):
        batch = {
            "dispatch_id": "unit",
            "rows": [
                {
                    "post_id": 1,
                    "primary_lane": "canonical_policy_cleanup_review",
                    "selected_title": "Not selected",
                }
            ],
        }

        plan = build_plan(batch, plan_id="unit")

        self.assertEqual(plan["summary"]["no_publish_contract_plan_rows"], 0)
        self.assertEqual(plan["rows"], [])


if __name__ == "__main__":
    unittest.main()
