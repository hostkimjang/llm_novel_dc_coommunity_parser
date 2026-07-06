from __future__ import annotations

from pathlib import Path
import unittest

from tools.build_projection_followup_queue import build_followup_queue, build_runtime_replay_input


class ProjectionFollowupQueueTest(unittest.TestCase):
    def test_splits_projection_followup_lanes(self) -> None:
        projection = {
            "projection_id": "unit_projection",
            "input_rows": 5,
            "rows": [
                {
                    "post_id": 1,
                    "projected_status": "safe_resolved",
                    "matches_source_native_title": True,
                    "selected_title": "A",
                    "projected_title": "A",
                    "projected_reasons": ["scope_current_work"],
                },
                {
                    "post_id": 2,
                    "projected_status": "safe_resolved",
                    "matches_source_native_title": False,
                    "selected_title": "B",
                    "projected_title": "B 단행본",
                    "projected_reasons": ["scope_current_work"],
                },
                {
                    "post_id": 3,
                    "projected_status": "output_consistency_lint",
                    "selected_title": "C",
                    "projected_reasons": ["output_consistency_lint"],
                },
                {
                    "post_id": 4,
                    "projected_status": "promotion_blocked",
                    "selected_title": "D",
                    "projected_reasons": ["scope_not_current_work", "scope_context_only"],
                },
                {
                    "post_id": 5,
                    "projected_status": "promotion_blocked",
                    "selected_title": "E",
                    "projected_reasons": ["verified_alias_title_only_counterevidence_blocked"],
                },
                {
                    "post_id": 6,
                    "projected_status": "promotion_blocked",
                    "selected_title": None,
                    "projected_reasons": ["candidate_set_rebuild_required", "no_candidate_title"],
                },
            ],
        }
        projection["input_rows"] = 6

        queue = build_followup_queue(projection, generated_at="2026-07-06T04:00:00")

        self.assertEqual(queue["gate"], "REVIEW-LOCKED")
        self.assertFalse(queue["full_scan_approval"])
        self.assertEqual(queue["summary"]["followup_action_queue_rows"], 6)
        self.assertEqual(queue["summary"]["runtime_replay_candidate_rows"], 1)
        self.assertEqual(queue["summary"]["variant_review_rows"], 1)
        self.assertEqual(queue["summary"]["lint_followup_rows"], 1)
        self.assertEqual(queue["summary"]["still_blocked_rows"], 3)
        self.assertEqual(queue["summary"]["label_counts"], {"HOLD": 2, "REPROCESS": 4})
        self.assertEqual(queue["summary"]["priority_counts"], {"P0": 2, "P1": 3, "P2": 1})
        self.assertIn(
            "runtime_replay_projected_safe_resolved_exact_required",
            queue["summary"]["action_counts"],
        )
        self.assertIn("scope_or_nonwork_hard_hold_review_required", queue["summary"]["action_counts"])
        self.assertIn("shared_gate_support_gap_repair_required", queue["summary"]["action_counts"])

    def test_reports_projection_input_count_mismatch(self) -> None:
        projection = {
            "projection_id": "unit_projection",
            "input_rows": 2,
            "rows": [
                {
                    "post_id": 1,
                    "projected_status": "safe_resolved",
                    "matches_source_native_title": True,
                    "selected_title": "A",
                    "projected_title": "A",
                }
            ],
        }

        queue = build_followup_queue(projection)

        self.assertEqual(queue["gate"], "NO-GO")
        self.assertEqual(queue["summary"]["validation_issue_count"], 1)
        self.assertEqual(queue["validation_issues"][0]["code"], "projection_input_rows_mismatch")

    def test_builds_runtime_input_for_exact_projected_safe_rows(self) -> None:
        projection = {
            "projection_id": "unit_projection",
            "input_rows": 2,
            "rows": [
                {
                    "post_id": 1,
                    "projected_status": "safe_resolved",
                    "matches_source_native_title": True,
                    "selected_title": "A",
                    "projected_title": "A",
                    "projected_url": "https://example.test/a",
                },
                {
                    "post_id": 2,
                    "projected_status": "safe_resolved",
                    "matches_source_native_title": False,
                    "selected_title": "B",
                    "projected_title": "B 단행본",
                },
            ],
        }
        queue = build_followup_queue(projection, queue_id="unit_queue")
        runtime_rows, manifest = build_runtime_replay_input(
            queue,
            [
                {
                    "post_id": 1,
                    "title": "A 얘기",
                    "content": ["본문"],
                    "comments": [],
                    "analysis_result": {"identity": {"official_title": "stale"}},
                },
                {
                    "post_id": 2,
                    "title": "B 얘기",
                    "content": ["본문"],
                    "comments": [],
                },
            ],
            source_result_path=Path("unit_result.json"),
            output_jsonl=Path("unit_input.jsonl"),
        )

        self.assertEqual(manifest["runtime_replay_candidate_rows"], 1)
        self.assertEqual(manifest["runtime_input_rows"], 1)
        self.assertEqual(manifest["missing_post_ids"], [])
        self.assertEqual(runtime_rows[0]["post_id"], 1)
        self.assertNotIn("analysis_result", runtime_rows[0])
        self.assertEqual(runtime_rows[0]["_loop_projection_followup"]["queue_id"], "unit_queue")
        self.assertEqual(
            runtime_rows[0]["_loop_projection_followup"]["approval_state"],
            "runtime_replay_required_not_approval",
        )


if __name__ == "__main__":
    unittest.main()
