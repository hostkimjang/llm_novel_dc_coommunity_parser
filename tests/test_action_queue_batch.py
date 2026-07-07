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
        self.assertEqual(batch["execution_contract"]["requested_parallel"], 16)
        self.assertEqual(batch["execution_contract"]["expected_effective_parallel"], 2)
        self.assertEqual(
            batch["execution_contract"]["dashboard_contract"]["dashboard_policy"],
            "WEB_DASHBOARD_REQUIRED_FOR_TEST_RUNS",
        )
        self.assertIn("--no-dashboard", batch["execution_contract"]["forbidden_flags"])
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
        self.assertEqual(manifest["execution_contract"]["requested_parallel"], 16)
        self.assertEqual(manifest["execution_contract"]["expected_effective_parallel"], 1)
        self.assertEqual(
            manifest["execution_contract"]["dashboard_contract"]["dashboard_policy"],
            "WEB_DASHBOARD_REQUIRED_FOR_TEST_RUNS",
        )
        self.assertNotIn("--no-dashboard", manifest["execution_contract"]["required_flags"])
        self.assertNotIn("analysis_result", runtime_rows[0])
        self.assertEqual(runtime_rows[0]["_loop_action_batch"]["batch_id"], "unit_batch")
        self.assertEqual(packet["summary"]["review_rows"], 1)
        self.assertEqual(packet["rows"][0]["post_id"], 2)

    def test_info_missing_source_native_action_enters_review_packet(self) -> None:
        queue = {
            "queue_id": "unit_queue",
            "summary": {"action_queue_rows": 1},
            "rows": [
                {
                    "post_id": 42,
                    "triage_bucket": "wrong_work_title_flip",
                    "review_label": "INFO_MISSING",
                    "source_native_verdict": "current_regression_row_without_compatible_prior_verdict",
                    "selected_option_id": "HOLD",
                    "actions": [
                        "source_native_or_blind_review_required",
                        "p0_wrong_work_title_flip_review_required",
                    ],
                }
            ],
        }

        batch = build_action_batch(
            queue,
            batch_id="unit_info_missing",
            actions={"source_native_or_blind_review_required"},
        )
        packet = build_review_packet(batch)

        self.assertEqual(batch["summary"]["selected_rows"], 1)
        self.assertEqual(batch["summary"]["source_native_review_rows"], 1)
        self.assertEqual(batch["summary"]["dispatch_lane_counts"], {"source_native_or_blind_review": 1})
        self.assertTrue(batch["rows"][0]["source_native_review_required"])
        self.assertEqual(packet["summary"]["review_rows"], 1)
        self.assertEqual(packet["rows"][0]["post_id"], 42)

    def test_shared_gate_restore_without_runtime_action_is_not_runtime_dispatch(self) -> None:
        queue = {
            "queue_id": "unit_queue",
            "summary": {"action_queue_rows": 1},
            "rows": [
                {
                    "post_id": 77,
                    "priority": "P0",
                    "review_label": "REPROCESS",
                    "owner_mode": "CODE_OR_RUNTIME_REPAIR",
                    "triage_bucket": "safe_loss_resolved_to_null",
                    "selected_title": "화산파(화산귀환)",
                    "actions": [
                        "repair_safe_loss_restore_supported_title",
                        "shared_promotion_gate_wiring_required",
                    ],
                }
            ],
        }

        batch = build_action_batch(queue, batch_id="unit_shared_gate", priorities={"P0"})

        self.assertEqual(batch["summary"]["selected_rows"], 1)
        self.assertEqual(batch["summary"]["runtime_input_candidate_rows"], 0)
        self.assertEqual(batch["summary"]["source_native_review_rows"], 0)
        self.assertEqual(
            batch["summary"]["dispatch_lane_counts"],
            {"shared_gate_restore_contract_review": 1},
        )
        self.assertFalse(batch["rows"][0]["runtime_input_eligible"])
        self.assertFalse(batch["rows"][0]["source_native_review_required"])
        self.assertEqual(batch["rows"][0]["dispatch_lane"], "shared_gate_restore_contract_review")


if __name__ == "__main__":
    unittest.main()
