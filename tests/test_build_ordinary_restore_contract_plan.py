import unittest

from tools.build_ordinary_restore_contract_plan import build_plan


class BuildOrdinaryRestoreContractPlanTest(unittest.TestCase):
    def _dispatch(self):
        return {
            "dispatch_id": "loop553",
            "rows": [
                {
                    "post_id": 1,
                    "primary_lane": "shared_gate_restore_contract_review",
                    "triage_bucket": "safe_loss_resolved_to_null",
                    "review_label": "REPROCESS",
                    "selected_title": "Expected Work",
                    "evidence_grade": "Strong",
                    "source_native_verdict": "supported_safe_title_lost_to_null",
                    "rationale_ko": "원문이 Expected Work를 직접 지지한다.",
                    "evidence_refs": ["https://novelpia.com/novel/123"],
                },
                {
                    "post_id": 2,
                    "primary_lane": "candidate_set_rebuild_review",
                    "selected_title": "Other Work",
                    "evidence_grade": "Strong",
                    "evidence_refs": ["https://novelpia.com/novel/456"],
                },
            ],
        }

    def test_builds_restore_contract_case_without_runtime_approval(self):
        audit = {
            "rows": [
                {
                    "post_id": 1,
                    "audit_status": "FAIL_RUNTIME_PROMOTION_BLOCKED",
                    "actual_title": None,
                    "search_status": "SEARCH_DEGRADED",
                }
            ]
        }

        plan = build_plan(dispatch=self._dispatch(), runtime_expected_audit=audit, plan_id="unit")
        row = plan["rows"][0]

        self.assertEqual(plan["gate"], "REVIEW-LOCKED")
        self.assertEqual(plan["summary"]["restore_contract_plan_rows"], 1)
        self.assertEqual(row["contract_action"], "expected_title_restore_contract_case")
        self.assertEqual(row["promotion_decision"]["status"], "publish")
        self.assertTrue(row["release_candidate_not_approval"])
        self.assertFalse(row["runtime_replay_allowed"])
        self.assertFalse(plan["full_scan_approval"])
        self.assertEqual(plan["summary"]["publish_allowed_rows"], 0)
        self.assertEqual(plan["summary"]["runtime_replay_allowed_rows"], 0)
        self.assertEqual(plan["summary"]["search_review_required_before_approval_rows"], 1)

    def test_missing_title_is_validation_issue(self):
        dispatch = self._dispatch()
        dispatch["rows"][0]["selected_title"] = ""

        plan = build_plan(dispatch=dispatch, plan_id="unit")

        self.assertEqual(plan["gate"], "NO-GO")
        self.assertEqual(plan["summary"]["validation_issue_count"], 1)
        self.assertEqual(plan["validation_issues"][0]["issue"], "missing_target_title")

    def test_non_restore_lanes_are_ignored(self):
        dispatch = {"dispatch_id": "loop553", "rows": [self._dispatch()["rows"][1]]}

        plan = build_plan(dispatch=dispatch, plan_id="unit")

        self.assertEqual(plan["summary"]["restore_contract_plan_rows"], 0)
        self.assertEqual(plan["summary"]["validation_issue_count"], 0)
        self.assertEqual(plan["summary"]["runtime_replay_allowed_rows"], 0)


if __name__ == "__main__":
    unittest.main()
