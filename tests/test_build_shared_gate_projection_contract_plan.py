from __future__ import annotations

import unittest

from tools.build_shared_gate_projection_contract_plan import (
    NO_PUBLISH,
    PUBLISH_RESTORE,
    build_plan,
)


class BuildSharedGateProjectionContractPlanTest(unittest.TestCase):
    def test_filters_to_residual_dispatch_and_maps_publish_boundary(self) -> None:
        projection = {
            "projection_id": "unit_projection",
            "rows": [
                {
                    "post_id": 1,
                    "triage_bucket": "safe_loss_resolved_to_null",
                    "selected_title": "Publish Work",
                    "selected_url": "https://novelpia.com/novel/1",
                    "source_native_verdict": "codex_native_web_judge_reprocess_under_resolved",
                    "evidence_grade": "Strong",
                    "source_actions": ["shared_promotion_gate_wiring_required"],
                    "promotion_decision": {
                        "status": "publish",
                        "publish_allowed": True,
                        "official_title": "Publish Work",
                        "official_url": "https://novelpia.com/novel/1",
                        "candidate_preserved": False,
                        "reason_codes": ["row_discusses_work_as_work", "scope_current_work"],
                        "bypassed_gate": False,
                    },
                },
                {
                    "post_id": 2,
                    "triage_bucket": "safe_loss_resolved_to_null",
                    "selected_title": "Blocked Work",
                    "selected_url": "https://novelpia.com/novel/2",
                    "source_native_verdict": "codex_native_web_judge_reprocess_wrong_work",
                    "evidence_grade": "Strong",
                    "source_actions": ["shared_promotion_gate_wiring_required"],
                    "promotion_decision": {
                        "status": "candidate_only",
                        "publish_allowed": False,
                        "official_title": None,
                        "official_url": None,
                        "candidate_preserved": True,
                        "reason_codes": ["row_discussion_missing", "scope_not_current_work"],
                        "bypassed_gate": False,
                    },
                },
                {
                    "post_id": 3,
                    "selected_title": "Already Accounted",
                    "promotion_decision": {
                        "status": "publish",
                        "publish_allowed": True,
                        "official_title": "Already Accounted",
                        "bypassed_gate": False,
                    },
                },
            ],
        }
        residual_dispatch = {"dispatch_id": "remaining", "rows": [{"post_id": 1}, {"post_id": 2}]}

        plan = build_plan(projection, residual_dispatch=residual_dispatch, plan_id="unit_plan")

        self.assertEqual(plan["gate"], "REVIEW-LOCKED")
        self.assertEqual(plan["source_projection_id"], "unit_projection")
        self.assertEqual(plan["summary"]["contract_plan_rows"], 2)
        self.assertEqual(plan["summary"]["publish_release_candidate_rows"], 1)
        self.assertEqual(plan["summary"]["candidate_only_no_publish_rows"], 1)
        self.assertEqual(plan["summary"]["contract_action_counts"][PUBLISH_RESTORE], 1)
        self.assertEqual(plan["summary"]["contract_action_counts"][NO_PUBLISH], 1)
        self.assertFalse(plan["full_scan_approval"])
        publish_row, blocked_row = plan["rows"]
        self.assertEqual(publish_row["contract_action"], PUBLISH_RESTORE)
        self.assertEqual(publish_row["target_title"], "Publish Work")
        self.assertTrue(publish_row["release_candidate_not_approval"])
        self.assertFalse(publish_row["runtime_replay_allowed"])
        self.assertEqual(blocked_row["contract_action"], NO_PUBLISH)
        self.assertEqual(blocked_row["target_title"], "Blocked Work")
        self.assertFalse(blocked_row["release_candidate_not_approval"])

    def test_bypassed_gate_is_validation_issue(self) -> None:
        projection = {
            "projection_id": "unit_projection",
            "rows": [
                {
                    "post_id": 1,
                    "selected_title": "Work",
                    "promotion_decision": {
                        "status": "publish",
                        "publish_allowed": True,
                        "official_title": "Work",
                        "bypassed_gate": True,
                    },
                }
            ],
        }

        plan = build_plan(projection, plan_id="unit_plan")

        self.assertEqual(plan["gate"], "NO-GO")
        self.assertEqual(plan["summary"]["validation_issue_count"], 1)
        self.assertEqual(plan["validation_issues"][0]["issue"], "promotion_gate_bypassed")


if __name__ == "__main__":
    unittest.main()
