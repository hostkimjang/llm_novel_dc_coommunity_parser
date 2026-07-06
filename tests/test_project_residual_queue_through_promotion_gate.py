from __future__ import annotations

import unittest

from tools.project_residual_queue_through_promotion_gate import project_queue


class ProjectResidualQueueThroughPromotionGateTest(unittest.TestCase):
    def test_projects_supported_shared_gate_row_to_publish_decision(self) -> None:
        queue = {
            "queue_id": "unit_residual_queue",
            "source_review_id": "unit_review",
            "gate": "REVIEW-LOCKED",
            "rows": [
                {
                    "post_id": 11660273,
                    "triage_bucket": "safe_loss_resolved_to_null",
                    "review_label": "REPROCESS",
                    "source_native_verdict": "supported_safe_title_lost_to_null",
                    "selected_title": "마도서를 줍다 마법사가 되다",
                    "selected_option_id": "C1",
                    "evidence_grade": "Strong",
                    "actions": [
                        "repair_safe_loss_restore_supported_title",
                        "shared_promotion_gate_wiring_required",
                    ],
                    "rationale_ko": "본문이 마줍 약칭과 작품 설정을 직접 연결한다.",
                    "evidence_refs": ["https://novelpia.com/novel/414963"],
                }
            ],
        }

        projection = project_queue(queue, generated_at="2026-07-06T12:20:00")

        self.assertEqual(projection["gate"], "REVIEW-LOCKED")
        self.assertFalse(projection["full_scan_approval"])
        self.assertEqual(projection["summary"]["projected_rows"], 1)
        self.assertEqual(projection["summary"]["publish_allowed_rows"], 1)
        row = projection["rows"][0]
        self.assertEqual(row["projected_status"], "safe_resolved")
        self.assertTrue(row["matches_source_native_title"])
        self.assertEqual(row["promotion_decision"]["status"], "publish")
        self.assertFalse(row["promotion_decision"]["bypassed_gate"])
        self.assertIn("row_discusses_work_as_work", row["projected_reasons"])
        self.assertIn("scope_current_work", row["projected_reasons"])
        self.assertIn("source_native_review_current_work", row["projected_reasons"])

    def test_candidate_rebuild_rows_stay_blocked_without_validation_issue(self) -> None:
        queue = {
            "queue_id": "unit_residual_queue",
            "source_review_id": "unit_review",
            "gate": "REVIEW-LOCKED",
            "rows": [
                {
                    "post_id": 1,
                    "triage_bucket": "safe_loss_resolved_to_null",
                    "review_label": "HOLD",
                    "source_native_verdict": "alias_current_work_needs_native_confirmation",
                    "selected_title": None,
                    "evidence_grade": "Weak",
                    "actions": [
                        "candidate_set_rebuild_required",
                        "shared_promotion_gate_wiring_required",
                    ],
                }
            ],
        }

        projection = project_queue(queue, generated_at="2026-07-06T12:20:00")

        self.assertEqual(projection["gate"], "REVIEW-LOCKED")
        self.assertEqual(projection["summary"]["validation_issue_count"], 0)
        self.assertEqual(projection["rows"][0]["projected_status"], "promotion_blocked")
        self.assertFalse(projection["rows"][0]["promotion_decision"]["publish_allowed"])
        self.assertIn("candidate_set_rebuild_required", projection["rows"][0]["projected_reasons"])

    def test_ignores_non_shared_gate_actions(self) -> None:
        queue = {
            "queue_id": "unit_residual_queue",
            "source_review_id": "unit_review",
            "gate": "REVIEW-LOCKED",
            "rows": [
                {
                    "post_id": 1,
                    "review_label": "REPROCESS",
                    "selected_title": "A",
                    "actions": ["repair_after_wrong_work"],
                }
            ],
        }

        projection = project_queue(queue)

        self.assertEqual(projection["summary"]["projected_rows"], 0)
        self.assertEqual(projection["rows"], [])


if __name__ == "__main__":
    unittest.main()
