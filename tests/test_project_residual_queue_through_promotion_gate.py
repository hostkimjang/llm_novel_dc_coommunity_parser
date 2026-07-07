from __future__ import annotations

import unittest

from tools.project_residual_queue_through_promotion_gate import project_queue


class ProjectResidualQueueThroughPromotionGateTest(unittest.TestCase):
    def test_projects_supported_shared_gate_row_to_publish_decision(self) -> None:
        queue = {
            "batch_id": "unit_p0_batch",
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
        self.assertEqual(projection["source_queue_id"], "unit_p0_batch")
        self.assertFalse(projection["full_scan_approval"])
        self.assertEqual(projection["summary"]["projected_rows"], 1)
        self.assertEqual(projection["summary"]["publish_allowed_rows"], 1)
        row = projection["rows"][0]
        self.assertEqual(row["projected_status"], "safe_resolved")
        self.assertTrue(row["matches_source_native_title"])
        self.assertEqual(row["promotion_decision"]["status"], "publish")
        self.assertFalse(row["promotion_decision"]["bypassed_gate"])
        self.assertEqual(row["publish_contract_trace"]["gate_decision"], row["promotion_decision"])
        self.assertEqual(row["publish_ledger"]["gate_decision"], row["promotion_decision"])
        self.assertEqual(
            row["publish_contract_trace"]["post_gate_identity"]["official_title"],
            "마도서를 줍다 마법사가 되다",
        )
        self.assertEqual(
            row["publish_ledger"]["candidate_preservation"],
            row["publish_contract_trace"]["pre_gate_candidate"],
        )
        self.assertIn("row_discusses_work_as_work", row["projected_reasons"])
        self.assertIn("scope_current_work", row["projected_reasons"])
        self.assertIn("source_native_review_current_work", row["projected_reasons"])

    def test_extracts_mobile_munpia_official_url_for_seed_projection(self) -> None:
        queue = {
            "queue_id": "unit_residual_queue",
            "source_review_id": "unit_review",
            "gate": "REVIEW-LOCKED",
            "rows": [
                {
                    "post_id": 11673102,
                    "triage_bucket": "safe_loss_resolved_to_null",
                    "review_label": "REPROCESS",
                    "source_native_verdict": "supported_safe_title_lost_to_null",
                    "selected_title": "갤질하는 천재 의사",
                    "selected_option_id": "C1",
                    "evidence_grade": "Strong",
                    "actions": [
                        "repair_safe_loss_restore_supported_title",
                        "shared_promotion_gate_wiring_required",
                    ],
                    "rationale_ko": "원문이 작품 설정을 직접 연결한다.",
                    "evidence_refs": [
                        "https://gall.dcinside.com/mgallery/board/view/?id=genrenovel&no=11673102",
                        "https://mm.munpia.com/?menu=novel&action=view&id=556720&entry_id=next&entry_seq=-10860205",
                    ],
                }
            ],
        }

        projection = project_queue(queue, generated_at="2026-07-07T23:30:00")

        row = projection["rows"][0]
        self.assertEqual(
            row["projected_url"],
            "https://mm.munpia.com/?menu=novel&action=view&id=556720&entry_id=next&entry_seq=-10860205",
        )
        self.assertEqual(row["promotion_decision"]["official_url"], row["projected_url"])
        self.assertEqual(projection["summary"]["publish_allowed_rows"], 1)

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
        self.assertEqual(
            projection["rows"][0]["publish_contract_trace"]["post_gate_identity"]["official_title"],
            None,
        )
        self.assertEqual(
            projection["rows"][0]["publish_ledger"]["public_publish"]["candidate_ledger_status"],
            "promotion_blocked",
        )
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
