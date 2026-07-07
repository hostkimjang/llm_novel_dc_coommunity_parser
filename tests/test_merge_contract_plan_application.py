from __future__ import annotations

import unittest

from tools.merge_contract_plan_application import merge_application, merge_plan


class MergeContractPlanApplicationTest(unittest.TestCase):
    def test_merges_plan_and_application_counts(self) -> None:
        base_plan = {
            "plan_id": "base",
            "summary": {"contract_plan_rows": 1},
            "validation_issues": [],
            "rows": [
                {
                    "post_id": 1,
                    "contract_action": "expected_title_restore_contract_case",
                    "contract_batch_lane": "base_lane",
                    "promotion_decision": {"status": "publish"},
                }
            ],
        }
        addition_plan = {
            "plan_id": "addition",
            "summary": {
                "release_candidate_not_approval_rows": 1,
                "no_publish_contract_rows": 1,
            },
            "validation_issues": [],
            "rows": [
                {
                    "post_id": 2,
                    "contract_action": "expected_title_restore_contract_case",
                    "contract_batch_lane": "add_publish",
                    "promotion_decision": {"status": "publish"},
                },
                {
                    "post_id": 3,
                    "contract_action": "candidate_scrub_no_publish_contract_case",
                    "contract_batch_lane": "add_block",
                    "promotion_decision": {"status": "candidate_only"},
                },
            ],
        }

        merged = merge_plan(base_plan, addition_plan, plan_id="merged")

        self.assertEqual(merged["gate"], "REVIEW-LOCKED")
        self.assertEqual(merged["summary"]["contract_plan_rows"], 3)
        self.assertEqual(merged["summary"]["addition_plan_rows"], 2)
        self.assertEqual(merged["summary"]["addition_publish_release_candidate_rows"], 1)
        self.assertEqual(merged["summary"]["addition_candidate_only_no_publish_rows"], 1)
        self.assertEqual(merged["summary"]["release_candidate_not_approval_rows"], 0)
        self.assertEqual(merged["summary"]["no_release_hold_rows"], 1)
        self.assertEqual(
            merged["summary"]["contract_action_counts"]["expected_title_restore_contract_case"],
            2,
        )
        self.assertEqual(
            merged["summary"]["contract_action_counts"]["candidate_scrub_no_publish_contract_case"],
            1,
        )

        base_application = {
            "projection_id": "base_app",
            "summary": {
                "contract_plan_rows": 1,
                "skipped_contract_action_counts": {"candidate_set_rebuild_required_before_publish": 1},
            },
            "validation_issues": [],
            "applied_rows": [
                {"post_id": 1, "contract_action": "expected_title_restore_contract_case"}
            ],
        }
        addition_application = {
            "projection_id": "addition_app",
            "summary": {
                "contract_plan_rows": 2,
                "skipped_contract_action_counts": {"candidate_scrub_no_publish_contract_case": 1},
            },
            "validation_issues": [],
            "applied_rows": [
                {"post_id": 2, "contract_action": "expected_title_restore_contract_case"},
                {"post_id": 3, "contract_action": "native_web_disambiguation_hold_contract_case"},
            ],
        }

        merged_application = merge_application(
            base_application,
            addition_application,
            projection_id="merged_app",
            source_contract_plan="merged",
        )

        self.assertEqual(merged_application["gate"], "REVIEW-LOCKED")
        self.assertEqual(merged_application["summary"]["applied_publish_contract_rows"], 2)
        self.assertEqual(merged_application["summary"]["applied_hold_contract_rows"], 1)
        self.assertEqual(merged_application["summary"]["addition_applied_rows"], 2)
        self.assertEqual(merged_application["summary"]["applied_restore_rows"], 2)
        self.assertEqual(
            merged_application["summary"]["skipped_contract_action_counts"][
                "candidate_scrub_no_publish_contract_case"
            ],
            1,
        )


if __name__ == "__main__":
    unittest.main()
