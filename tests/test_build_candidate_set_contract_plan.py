import unittest

from tools.build_candidate_set_contract_plan import build_plan


class BuildCandidateSetContractPlanTest(unittest.TestCase):
    def _batch(self):
        return {
            "dispatch_id": "unit",
            "rows": [
                {
                    "post_id": 1,
                    "dispatch_lane": "candidate_set_rebuild_review",
                    "triage_bucket": "wrong_work_title_flip",
                    "source_native_verdict": "source_supports_before_title",
                    "selected_title": "Expected Work",
                    "evidence_grade": "Strong",
                    "actions": ["repair_after_wrong_work", "canonical_title_cleanup_required"],
                    "evidence_refs": ["https://novelpia.com/novel/123"],
                    "rationale_ko": "원문이 Expected Work를 직접 지지한다.",
                },
                {
                    "post_id": 2,
                    "dispatch_lane": "candidate_set_rebuild_review",
                    "triage_bucket": "safe_loss_resolved_to_null",
                    "source_native_verdict": "candidate_set_incomplete",
                    "selected_title": None,
                    "evidence_grade": "Strong",
                    "actions": ["candidate_set_rebuild_required"],
                    "evidence_refs": ["https://novelpia.com/novel/456"],
                    "rationale_ko": "현재 후보셋에 정답 title이 없다.",
                },
                {
                    "post_id": 3,
                    "dispatch_lane": "candidate_set_rebuild_review",
                    "triage_bucket": "wrong_work_title_flip",
                    "source_native_verdict": "classic_japanese_novel_context_blocks_same_surface_webnovel_promotion",
                    "selected_title": "인간실격",
                    "evidence_grade": "Strong",
                    "actions": ["repair_after_wrong_work", "intent_guard_review"],
                    "evidence_refs": [],
                    "rationale_ko": "다자이 오사무의 고전 인간실격을 묻는다.",
                },
                {
                    "post_id": 4,
                    "dispatch_lane": "shared_gate_restore_contract_review",
                    "selected_title": "Ignored",
                },
            ],
        }

    def test_selected_title_with_official_ref_becomes_restore_contract_case(self):
        plan = build_plan(self._batch(), plan_id="unit")
        row = plan["rows"][0]

        self.assertEqual(plan["gate"], "REVIEW-LOCKED")
        self.assertEqual(row["contract_action"], "candidate_set_expected_restore_contract_case")
        self.assertEqual(row["promotion_decision"]["status"], "publish")
        self.assertTrue(row["release_candidate_not_approval"])
        self.assertFalse(row["runtime_replay_allowed"])
        self.assertEqual(plan["summary"]["publish_allowed_rows"], 0)
        self.assertEqual(plan["summary"]["runtime_replay_allowed_rows"], 0)

    def test_missing_selected_title_stays_candidate_set_rebuild_hold(self):
        plan = build_plan(self._batch(), plan_id="unit")
        row = plan["rows"][1]

        self.assertEqual(row["contract_action"], "candidate_set_rebuild_required_before_publish")
        self.assertTrue(row["candidate_set_rebuild_required_before_publish"])
        self.assertEqual(row["promotion_decision"]["status"], "reject")
        self.assertFalse(row["promotion_decision"]["publish_allowed"])
        self.assertFalse(row["runtime_replay_allowed"])

    def test_intent_guard_blocks_same_surface_webnovel_publish(self):
        plan = build_plan(self._batch(), plan_id="unit")
        row = plan["rows"][2]

        self.assertEqual(row["contract_action"], "no_publish_intent_guard_contract_case")
        self.assertTrue(row["intent_guard_hold_before_publish"])
        self.assertEqual(row["promotion_decision"]["status"], "candidate_only")
        self.assertFalse(row["promotion_decision"]["publish_allowed"])
        self.assertIn("scope_platform_meta_nonwork", row["promotion_decision"]["reason_codes"])

    def test_execution_contract_requires_dashboard_and_parallel_16(self):
        plan = build_plan(self._batch(), plan_id="unit")

        self.assertEqual(plan["summary"]["candidate_set_contract_plan_rows"], 3)
        self.assertEqual(plan["execution_contract"]["requested_parallel"], 16)
        self.assertEqual(
            plan["execution_contract"]["dashboard_contract"]["dashboard_policy"],
            "WEB_DASHBOARD_REQUIRED_FOR_TEST_RUNS",
        )
        self.assertIn("--no-dashboard", plan["execution_contract"]["dashboard_contract"]["forbidden_flags"])

    def test_accepts_ordinary_residual_dispatch_primary_lane(self):
        batch = {
            "dispatch_id": "ordinary_residual_dispatch",
            "rows": [
                {
                    "post_id": 5,
                    "primary_lane": "candidate_set_rebuild_review",
                    "triage_bucket": "safe_loss_resolved_to_null",
                    "source_native_verdict": "candidate_set_incomplete",
                    "selected_title": None,
                    "evidence_grade": "Strong",
                    "actions": ["candidate_set_rebuild_required"],
                    "rationale_ko": "ordinary residual dispatch가 primary_lane으로 lane을 기록한다.",
                }
            ],
        }

        plan = build_plan(batch, plan_id="unit_primary_lane")

        self.assertEqual(plan["summary"]["candidate_set_contract_plan_rows"], 1)
        self.assertEqual(plan["rows"][0]["source_dispatch_lane"], "candidate_set_rebuild_review")
        self.assertEqual(
            plan["rows"][0]["contract_action"],
            "candidate_set_rebuild_required_before_publish",
        )


if __name__ == "__main__":
    unittest.main()
