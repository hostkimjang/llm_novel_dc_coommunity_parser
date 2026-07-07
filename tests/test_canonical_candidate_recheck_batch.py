import unittest

from tools.build_canonical_candidate_recheck_batch import build_canonical_recheck_batch


class CanonicalCandidateRecheckBatchTest(unittest.TestCase):
    def test_b1_rows_enter_canonical_recheck_without_runtime_release(self) -> None:
        queue = {
            "queue_id": "unit_repair_queue",
            "gate": "REVIEW-LOCKED",
            "summary": {"repair_rows": 2},
            "rows": [
                {
                    "post_id": 11665124,
                    "selected_title": "화산파(화산귀환)",
                    "projected_title": "화산파(화산귀환)",
                    "repair_batch_lane": "B1_different_candidate_alignment_review",
                    "runtime_release_gate": "BLOCKED_UNTIL_CANONICAL_CANDIDATE_RECHECK",
                    "runtime_replay_allowed": False,
                    "current_projection_candidate_alignment_state": "different_title_candidate_review",
                    "current_projection_candidate_alignment_requires_review": True,
                    "candidate_support_state": "official_url_candidate_support",
                    "search_gate": "SEARCH_BLIND_BLOCKER",
                    "primary_repair_lane": "candidate_preservation_or_scrub_repair",
                    "current_projection_candidate": {
                        "official_title": "뿔 달고 귀환했다",
                        "official_url": "https://novelpia.com/novel/320490",
                        "candidate_source_tiers": ["official_detail"],
                        "candidate_source_roles": ["candidate"],
                    },
                    "actions": ["current_projection_candidate_recheck_required"],
                },
                {
                    "post_id": 11710049,
                    "selected_title": "빙의자를 위한 특혜",
                    "repair_batch_lane": "B2_same_title_search_blind_preflight",
                    "runtime_release_gate": "BLOCKED_UNTIL_SEARCH_PREFLIGHT_GO",
                    "runtime_replay_allowed": False,
                    "current_projection_candidate_alignment_state": "same_title_surface",
                    "current_projection_candidate_alignment_requires_review": False,
                    "current_projection_candidate": {"official_title": "빙의자를 위한 특혜"},
                    "actions": ["same_title_surface_search_preflight_required"],
                },
            ],
        }

        batch = build_canonical_recheck_batch(queue, batch_id="unit_b1")

        self.assertEqual(batch["gate"], "REVIEW-LOCKED")
        self.assertEqual(batch["summary"]["selected_rows"], 1)
        self.assertEqual(batch["summary"]["runtime_replay_allowed_rows"], 0)
        self.assertEqual(
            batch["summary"]["review_lane_counts"],
            {"B1_different_candidate_alignment_review": 1},
        )
        self.assertEqual(batch["summary"]["validation_issue_count"], 0)
        row = batch["rows"][0]
        self.assertEqual(row["post_id"], 11665124)
        self.assertEqual(row["canonical_review_state"], "NEEDS_SOURCE_NATIVE_OR_BLIND_CANONICAL_RECHECK")
        self.assertIn("EXPECTED_SOURCE_NATIVE_TITLE_CONFIRMED", row["allowed_verdicts"])
        self.assertTrue(row["approval_boundary"]["packet_generation_is_not_verdict"])

    def test_related_b1_rows_are_grouped_separately(self) -> None:
        queue = {
            "queue_id": "unit_repair_queue",
            "summary": {"repair_rows": 1},
            "rows": [
                {
                    "post_id": 11698859,
                    "selected_title": "귤부인 대롱대롱",
                    "repair_batch_lane": "B1_related_candidate_alignment_review",
                    "runtime_release_gate": "BLOCKED_UNTIL_CANONICAL_CANDIDATE_RECHECK",
                    "runtime_replay_allowed": False,
                    "current_projection_candidate_alignment_state": "related_title_surface_review",
                    "current_projection_candidate_alignment_requires_review": True,
                    "candidate_support_state": "non_official_candidate_preservation_only",
                    "search_gate": "SEARCH_BLIND_BLOCKER",
                    "primary_repair_lane": "scope_or_nonwork_monotonicity_repair",
                    "current_projection_candidate": {
                        "official_title": "귤부인",
                        "candidate_source_tiers": ["post_title_surface"],
                    },
                    "actions": ["current_projection_candidate_recheck_required"],
                }
            ],
        }

        batch = build_canonical_recheck_batch(queue, batch_id="unit_related")

        self.assertEqual(batch["summary"]["selected_rows"], 1)
        self.assertEqual(
            batch["summary"]["alignment_state_counts"],
            {"related_title_surface_review": 1},
        )
        self.assertEqual(batch["review_groups"][0]["review_lane"], "B1_related_candidate_alignment_review")
        self.assertEqual(batch["review_groups"][0]["post_ids"], [11698859])

    def test_missing_candidate_b1_rows_are_valid_rebuild_packets(self) -> None:
        queue = {
            "queue_id": "unit_missing_candidate_queue",
            "summary": {"repair_rows": 1},
            "rows": [
                {
                    "post_id": 11669933,
                    "selected_title": "회귀수선전",
                    "repair_batch_lane": "B1_missing_candidate_alignment_review",
                    "runtime_release_gate": "BLOCKED_UNTIL_CANONICAL_CANDIDATE_RECHECK",
                    "runtime_replay_allowed": False,
                    "current_projection_candidate_alignment_state": "missing_current_projection_candidate",
                    "current_projection_candidate_alignment_requires_review": True,
                    "candidate_support_state": "missing_current_projection_candidate_support",
                    "search_gate": "SEARCH_RECOVERED_CONDITIONAL",
                    "primary_repair_lane": "title_url_or_variant_trace_repair",
                    "actions": ["current_projection_candidate_recheck_required"],
                }
            ],
        }

        batch = build_canonical_recheck_batch(queue, batch_id="unit_missing")

        self.assertEqual(batch["gate"], "REVIEW-LOCKED")
        self.assertEqual(batch["summary"]["selected_rows"], 1)
        self.assertEqual(batch["summary"]["validation_issue_count"], 0)
        row = batch["rows"][0]
        self.assertIsNone(row["current_projection_candidate_title"])
        self.assertTrue(row["current_projection_candidate_missing"])
        self.assertIn("expected/source-native title 자체", row["review_questions"][0])
        self.assertEqual(
            row["allowed_verdicts"],
            ["EXPECTED_SOURCE_NATIVE_TITLE_CONFIRMED", "INSUFFICIENT_EVIDENCE_HOLD"],
        )

    def test_validation_issue_when_runtime_replay_is_already_open(self) -> None:
        queue = {
            "queue_id": "unit_repair_queue",
            "rows": [
                {
                    "post_id": 1,
                    "selected_title": "A",
                    "repair_batch_lane": "B1_different_candidate_alignment_review",
                    "runtime_release_gate": "BLOCKED_UNTIL_CANONICAL_CANDIDATE_RECHECK",
                    "runtime_replay_allowed": True,
                    "current_projection_candidate_alignment_state": "different_title_candidate_review",
                    "current_projection_candidate_alignment_requires_review": True,
                    "current_projection_candidate": {"official_title": "B"},
                    "actions": ["current_projection_candidate_recheck_required"],
                }
            ],
        }

        batch = build_canonical_recheck_batch(queue, batch_id="unit_invalid")

        self.assertEqual(batch["gate"], "NO-GO")
        self.assertEqual(batch["summary"]["validation_issue_count"], 1)
        self.assertEqual(
            batch["validation_issues"][0]["code"],
            "canonical_batch_row_runtime_replay_already_allowed",
        )


if __name__ == "__main__":
    unittest.main()
