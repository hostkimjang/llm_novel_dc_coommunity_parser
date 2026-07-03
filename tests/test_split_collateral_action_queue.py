from __future__ import annotations

import unittest

from tools.split_collateral_action_queue import build_residual_queue


class SplitCollateralActionQueueTest(unittest.TestCase):
    def test_splits_reprocess_and_hold_residual_rows(self) -> None:
        combined_review = {
            "review_id": "unit_combined",
            "gate": "REVIEW-LOCKED",
            "summary": {
                "queue_transition": {
                    "residual_action_queue_rows": 3,
                    "repair_required_rows": 2,
                    "policy_or_native_review_required_rows": 1,
                }
            },
            "rows": [
                {
                    "post_id": 1,
                    "triage_bucket": "safe_loss_resolved_to_null",
                    "review_label": "ACCEPT",
                    "action": ["exclude_from_regression_count_after_gate_wiring"],
                },
                {
                    "post_id": 2,
                    "triage_bucket": "safe_loss_resolved_to_null",
                    "review_label": "REPROCESS",
                    "source_native_verdict": "before_correct_source_native_title_alias",
                    "selected_title": "A",
                    "action": ["repair_safe_loss", "known_alias_runtime_replay_required"],
                    "rationale_ko": "원문은 A를 지지한다.",
                    "evidence_refs": ["unit://2"],
                },
                {
                    "post_id": 3,
                    "triage_bucket": "unsafe_promotion_from_hold",
                    "review_label": "REPROCESS",
                    "source_native_verdict": "after_wrong_hold_preferred",
                    "action": ["repair_unsafe_promotion"],
                    "evidence_refs": ["unit://3"],
                },
                {
                    "post_id": 4,
                    "triage_bucket": "safe_loss_resolved_to_null",
                    "review_label": "HOLD",
                    "source_native_verdict": "image_or_native_evidence_required",
                    "action": ["native_image_or_source_review_required"],
                    "evidence_refs": ["unit://4"],
                },
            ],
        }

        queue = build_residual_queue(combined_review, generated_at="2026-07-03T00:00:00")

        self.assertEqual(queue["gate"], "REVIEW-LOCKED")
        self.assertFalse(queue["full_scan_approval"])
        self.assertEqual(queue["summary"]["residual_action_queue_rows"], 3)
        self.assertEqual(queue["summary"]["label_counts"], {"HOLD": 1, "REPROCESS": 2})
        self.assertEqual(queue["summary"]["action_counts"]["repair_safe_loss"], 1)
        self.assertEqual(queue["summary"]["action_counts"]["known_alias_runtime_replay_required"], 1)
        self.assertEqual(queue["summary"]["action_counts"]["repair_unsafe_promotion"], 1)
        self.assertEqual(queue["summary"]["action_counts"]["native_image_or_source_review_required"], 1)
        repair_safe_loss = next(
            group for group in queue["action_groups"] if group["action"] == "repair_safe_loss"
        )
        self.assertEqual(repair_safe_loss["priority"], "P0")
        self.assertEqual(repair_safe_loss["owner_mode"], "CODE_OR_RUNTIME_REPAIR")
        self.assertEqual(repair_safe_loss["post_ids"], [2])

    def test_validation_issue_when_source_transition_counts_disagree(self) -> None:
        combined_review = {
            "review_id": "unit_combined",
            "summary": {
                "queue_transition": {
                    "residual_action_queue_rows": 9,
                    "repair_required_rows": 8,
                    "policy_or_native_review_required_rows": 7,
                }
            },
            "rows": [
                {"post_id": 1, "review_label": "REPROCESS", "action": ["repair_safe_loss"]},
                {"post_id": 2, "review_label": "HOLD", "action": ["native_image_review_required"]},
            ],
        }

        queue = build_residual_queue(combined_review, generated_at="2026-07-03T00:00:00")

        self.assertEqual(queue["gate"], "NO-GO")
        self.assertEqual(queue["summary"]["validation_issue_count"], 3)
        self.assertEqual(
            {issue["code"] for issue in queue["validation_issues"]},
            {
                "residual_action_queue_count_mismatch",
                "reprocess_count_mismatch",
                "hold_count_mismatch",
            },
        )

    def test_can_exclude_closed_post_ids_from_existing_queue(self) -> None:
        existing_queue = {
            "queue_id": "unit_queue",
            "gate": "REVIEW-LOCKED",
            "summary": {
                "residual_action_queue_rows": 3,
                "label_counts": {"HOLD": 1, "REPROCESS": 2},
            },
            "rows": [
                {
                    "post_id": 10,
                    "triage_bucket": "safe_loss_resolved_to_null",
                    "review_label": "REPROCESS",
                    "actions": ["repair_safe_loss", "known_alias_runtime_replay_required"],
                    "source_native_verdict": "before_correct_known_alias",
                },
                {
                    "post_id": 11,
                    "triage_bucket": "safe_loss_resolved_to_null",
                    "review_label": "REPROCESS",
                    "actions": ["repair_safe_loss"],
                    "source_native_verdict": "before_correct_source_native",
                },
                {
                    "post_id": 12,
                    "triage_bucket": "safe_loss_resolved_to_null",
                    "review_label": "HOLD",
                    "actions": ["native_image_or_source_review_required"],
                    "source_native_verdict": "image_or_native_evidence_required",
                },
            ],
        }

        queue = build_residual_queue(
            existing_queue,
            generated_at="2026-07-03T00:00:00",
            exclude_post_ids={10},
        )

        self.assertEqual(queue["gate"], "REVIEW-LOCKED")
        self.assertEqual(queue["summary"]["residual_action_queue_rows"], 2)
        self.assertEqual(queue["summary"]["label_counts"], {"HOLD": 1, "REPROCESS": 1})
        self.assertEqual(queue["summary"]["closed_post_ids_excluded"], [10])
        self.assertEqual(queue["summary"]["excluded_label_counts"], {"REPROCESS": 1})
        self.assertEqual(queue["summary"]["validation_issue_count"], 0)
        self.assertEqual([row["post_id"] for row in queue["rows"]], [11, 12])
        repair_safe_loss = next(
            group for group in queue["action_groups"] if group["action"] == "repair_safe_loss"
        )
        self.assertEqual(repair_safe_loss["post_ids"], [11])


if __name__ == "__main__":
    unittest.main()
