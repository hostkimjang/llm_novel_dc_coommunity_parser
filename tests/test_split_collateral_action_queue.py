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
                "policy_or_native_review_count_mismatch",
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

    def test_appends_unreviewed_p1_regression_rows_to_residual_queue(self) -> None:
        combined_review = {
            "review_id": "unit_combined_p0",
            "gate": "REVIEW-LOCKED",
            "summary": {
                "queue_transition": {
                    "residual_action_queue_rows": 2,
                    "repair_required_rows": 1,
                    "policy_or_native_review_required_rows": 1,
                }
            },
            "rows": [
                {
                    "post_id": 20,
                    "triage_bucket": "safe_loss_resolved_to_null",
                    "review_label": "REPROCESS",
                    "action": ["repair_safe_loss"],
                },
                {
                    "post_id": 21,
                    "triage_bucket": "unsafe_promotion_from_hold",
                    "review_label": "HOLD",
                    "action": ["native_web_review_required"],
                },
            ],
        }
        p1_rows = [
            {
                "post_id": 22,
                "status": "null_to_resolved",
                "is_regression": True,
                "priority": "P1",
                "triage_bucket": "new_resolution_promotion",
                "before_title": None,
                "after_title": "갤질하는 천재 의사",
                "before_url": None,
                "after_url": "https://novelpia.com/novel/372180",
            }
        ]

        queue = build_residual_queue(
            combined_review,
            generated_at="2026-07-06T00:00:00",
            unreviewed_regression_rows=p1_rows,
        )

        self.assertEqual(queue["gate"], "REVIEW-LOCKED")
        self.assertEqual(queue["summary"]["residual_action_queue_rows"], 3)
        self.assertEqual(queue["summary"]["unreviewed_regression_rows_added"], 1)
        self.assertEqual(
            queue["summary"]["label_counts"],
            {"HOLD": 1, "INFO_MISSING": 1, "REPROCESS": 1},
        )
        self.assertEqual(queue["summary"]["validation_issue_count"], 0)
        p1_group = next(
            group
            for group in queue["action_groups"]
            if group["action"] == "p1_new_resolution_promotion_review_required"
        )
        self.assertEqual(p1_group["priority"], "P1")
        self.assertEqual(p1_group["owner_mode"], "SOURCE_NATIVE_OR_BLIND_REVIEW")
        self.assertEqual(p1_group["post_ids"], [22])

    def test_can_build_triage_only_residual_queue(self) -> None:
        queue = build_residual_queue(
            {
                "review_id": "unit_triage_only",
                "gate": "REVIEW-LOCKED",
                "summary": {},
                "rows": [],
            },
            generated_at="2026-07-08T00:00:00",
            queue_id="unit_triage_only_queue",
            unreviewed_regression_rows=[
                {
                    "post_id": 30,
                    "status": "resolved_to_different_title",
                    "is_regression": True,
                    "priority": "P0",
                    "triage_bucket": "wrong_work_title_flip",
                    "before_title": "Before",
                    "after_title": "After",
                },
                {
                    "post_id": 31,
                    "status": "resolved_to_null",
                    "is_regression": True,
                    "priority": "P0",
                    "triage_bucket": "safe_loss_resolved_to_null",
                    "before_title": "Before Null",
                    "after_title": None,
                },
            ],
        )

        self.assertEqual(queue["gate"], "REVIEW-LOCKED")
        self.assertEqual(queue["summary"]["source_rows"], 0)
        self.assertEqual(queue["summary"]["residual_action_queue_rows"], 2)
        self.assertEqual(queue["summary"]["unreviewed_regression_rows_added"], 2)
        self.assertEqual(queue["summary"]["label_counts"], {"INFO_MISSING": 2})
        self.assertEqual(queue["summary"]["validation_issue_count"], 0)
        self.assertEqual([row["post_id"] for row in queue["rows"]], [30, 31])
        wrong_work_group = next(
            group
            for group in queue["action_groups"]
            if group["action"] == "p0_wrong_work_title_flip_review_required"
        )
        self.assertEqual(wrong_work_group["priority"], "P0")
        self.assertEqual(wrong_work_group["post_ids"], [30])


if __name__ == "__main__":
    unittest.main()
