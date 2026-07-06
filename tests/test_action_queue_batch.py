from __future__ import annotations

from pathlib import Path
import unittest

from tools.build_action_queue_batch import (
    build_action_batch,
    build_review_packet,
    build_runtime_input,
)


class ActionQueueBatchTest(unittest.TestCase):
    def test_filters_p0_and_splits_runtime_and_hold_lanes(self) -> None:
        queue = {
            "queue_id": "unit_queue",
            "summary": {"action_queue_rows": 4},
            "rows": [
                {
                    "post_id": 1,
                    "priority": "P0",
                    "review_label": "REPROCESS",
                    "owner_mode": "CODE_OR_RUNTIME_PROMOTION_GATE_REPAIR",
                    "audit_status": "FAIL_RUNTIME_PROMOTION_BLOCKED",
                    "expected_title": "A",
                    "actual_title": "A",
                    "actions": [
                        "shared_gate_runtime_block_repair_required",
                        "search_degraded_or_timeout_replay_required",
                    ],
                },
                {
                    "post_id": 2,
                    "priority": "P0",
                    "review_label": "HOLD",
                    "owner_mode": "SOURCE_NATIVE_OR_BLIND_CANONICAL_REVIEW",
                    "audit_status": "FAIL_SAFE_RESOLVED_TITLE_MISMATCH",
                    "expected_title": "B",
                    "actual_title": "B 외전",
                    "actions": ["canonical_variant_or_wrong_work_review_required"],
                },
                {
                    "post_id": 3,
                    "priority": "P1",
                    "review_label": "REPROCESS",
                    "owner_mode": "CODE_OR_RUNTIME_PROMOTION_GATE_REPAIR",
                    "audit_status": "FAIL_RUNTIME_PROMOTION_BLOCKED",
                    "actions": ["shared_gate_runtime_block_repair_required"],
                },
            ],
        }

        batch = build_action_batch(queue, batch_id="unit_batch", priorities={"P0"})

        self.assertEqual(batch["gate"], "REVIEW-LOCKED")
        self.assertEqual(batch["summary"]["selected_rows"], 2)
        self.assertEqual(batch["summary"]["runtime_input_candidate_rows"], 1)
        self.assertEqual(batch["summary"]["source_native_review_rows"], 1)
        self.assertEqual(batch["summary"]["search_replay_required_rows"], 1)
        self.assertEqual(batch["summary"]["label_counts"], {"HOLD": 1, "REPROCESS": 1})
        self.assertEqual(
            batch["summary"]["dispatch_lane_counts"],
            {"runtime_repair_with_search_replay": 1, "source_native_or_blind_review": 1},
        )
        self.assertTrue(batch["rows"][0]["runtime_input_eligible"])
        self.assertTrue(batch["rows"][1]["source_native_review_required"])

    def test_builds_runtime_input_and_review_packet(self) -> None:
        queue = {
            "queue_id": "unit_queue",
            "summary": {"action_queue_rows": 2},
            "rows": [
                {
                    "post_id": 1,
                    "priority": "P0",
                    "review_label": "REPROCESS",
                    "owner_mode": "CODE_OR_RUNTIME_PROMOTION_GATE_REPAIR",
                    "audit_status": "FAIL_RUNTIME_PROMOTION_BLOCKED",
                    "expected_title": "A",
                    "actual_title": None,
                    "actions": ["shared_gate_runtime_block_repair_required"],
                    "close_condition": "runtime replay",
                },
                {
                    "post_id": 2,
                    "priority": "P0",
                    "review_label": "HOLD",
                    "owner_mode": "CANONICAL_VARIANT_POLICY_REVIEW",
                    "audit_status": "FAIL_VARIANT_COMPACT_MATCH_ONLY",
                    "expected_title": "인간실격",
                    "actual_title": "인간 실격",
                    "actions": ["spacing_or_canonical_variant_policy_review_required"],
                },
            ],
        }
        batch = build_action_batch(queue, batch_id="unit_batch", priorities={"P0"})

        runtime_rows, manifest = build_runtime_input(
            batch,
            [
                {
                    "post_id": 1,
                    "title": "A 얘기",
                    "content": ["본문"],
                    "analysis_result": {"stale": True},
                }
            ],
            source_jsonl=Path("source.jsonl"),
            output_jsonl=Path("runtime.jsonl"),
        )
        packet = build_review_packet(batch)

        self.assertEqual(manifest["runtime_input_candidate_rows"], 1)
        self.assertEqual(manifest["runtime_input_rows"], 1)
        self.assertEqual(manifest["missing_post_ids"], [])
        self.assertNotIn("analysis_result", runtime_rows[0])
        self.assertEqual(runtime_rows[0]["_loop_action_batch"]["batch_id"], "unit_batch")
        self.assertEqual(packet["summary"]["review_rows"], 1)
        self.assertEqual(packet["rows"][0]["post_id"], 2)


if __name__ == "__main__":
    unittest.main()
