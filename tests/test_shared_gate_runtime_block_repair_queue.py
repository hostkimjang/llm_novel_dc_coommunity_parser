import unittest

from tools.build_shared_gate_runtime_block_repair_queue import build_repair_queue


class SharedGateRuntimeBlockRepairQueueTest(unittest.TestCase):
    def test_candidate_pruning_rows_are_not_runtime_replay_ready(self):
        queue = {
            "queue_id": "unit_followup",
            "rows": [
                {
                    "post_id": 11660271,
                    "selected_title": "월야의 여인들",
                    "projected_title": "월야의 여인들",
                    "prior_runtime_audit_status": "FAIL_RUNTIME_PROMOTION_BLOCKED",
                    "prior_runtime_search_status": "SEARCH_DEGRADED_RECOVERED",
                    "prior_runtime_reason_codes": [
                        "llm_only_sentence_candidate_pruned",
                        "serialized_public_identity_scrubbed",
                    ],
                    "actions": [
                        "prior_runtime_promotion_block_repair_required",
                        "shared_gate_runtime_block_repair_required",
                    ],
                }
            ],
        }

        repair = build_repair_queue(queue, queue_id="unit_repair")

        self.assertEqual(repair["gate"], "REVIEW-LOCKED")
        self.assertEqual(repair["summary"]["repair_rows"], 1)
        self.assertEqual(repair["summary"]["runtime_replay_allowed_rows"], 0)
        self.assertEqual(
            repair["rows"][0]["primary_repair_lane"],
            "candidate_preservation_or_scrub_repair",
        )
        self.assertFalse(repair["rows"][0]["runtime_replay_allowed"])
        self.assertIn("candidate_preservation_or_scrub", repair["rows"][0]["repair_facets"])
        self.assertIn("search_recovered_conditional_tag_required", repair["rows"][0]["actions"])

    def test_scope_and_search_blind_rows_stay_hard_hold_repair(self):
        queue = {
            "queue_id": "unit_followup",
            "rows": [
                {
                    "post_id": 11663521,
                    "selected_title": "초전자포] 시스터즈가 되었다",
                    "projected_title": "초전자포] 시스터즈가 되었다",
                    "prior_runtime_audit_status": "FAIL_RUNTIME_PROMOTION_BLOCKED",
                    "prior_runtime_search_status": "SEARCH_DEGRADED",
                    "prior_runtime_reason_codes": [
                        "scope_context_only",
                        "scope_not_current_work",
                        "exact_alias_candidate_preserved_without_work_discussion",
                        "image_ocr_without_title_anchor",
                        "serialized_public_identity_scrubbed",
                    ],
                    "projected_reasons": [
                        "source_native_review_current_work",
                        "row_discusses_work_as_work",
                        "scope_current_work",
                    ],
                    "actions": ["shared_gate_runtime_block_repair_required"],
                }
            ],
        }

        repair = build_repair_queue(queue, queue_id="unit_repair")

        self.assertEqual(
            repair["rows"][0]["primary_repair_lane"],
            "scope_or_nonwork_monotonicity_repair",
        )
        self.assertEqual(repair["rows"][0]["search_gate"], "SEARCH_BLIND_BLOCKER")
        self.assertIn("search_blind_preflight_required", repair["rows"][0]["actions"])
        self.assertTrue(repair["rows"][0]["projection_runtime_scope_conflict"])
        self.assertEqual(
            repair["rows"][0]["projected_scope_claim"],
            "PROJECTED_CURRENT_WORK",
        )
        self.assertEqual(
            repair["rows"][0]["runtime_scope_claim"],
            "RUNTIME_NONCURRENT_OR_CONTEXT_ONLY",
        )
        self.assertIn("projection_runtime_scope_conflict", repair["rows"][0]["repair_facets"])
        self.assertEqual(repair["rows"][0]["projection_runtime_scope_conflict_kind"], "hard_noncurrent")
        self.assertIn("projection_runtime_scope_reconciliation_required", repair["rows"][0]["actions"])
        self.assertEqual(
            repair["summary"]["projection_runtime_scope_conflict_counts"],
            {"conflict": 1},
        )
        self.assertEqual(
            repair["summary"]["projection_runtime_scope_conflict_kind_counts"],
            {"hard_noncurrent": 1},
        )
        self.assertIn("_post_discusses_work_as_work", "\n".join(repair["rows"][0]["required_contract_tests"]))

    def test_mixed_runtime_scope_trace_is_separate_from_hard_noncurrent_conflict(self):
        queue = {
            "queue_id": "unit_followup",
            "rows": [
                {
                    "post_id": 11679547,
                    "selected_title": "도굴왕",
                    "projected_title": "도굴왕",
                    "prior_runtime_audit_status": "FAIL_RUNTIME_PROMOTION_BLOCKED",
                    "prior_runtime_search_status": "SEARCH_DEGRADED_RECOVERED",
                    "prior_runtime_reason_codes": [
                        "context_only",
                        "row_discusses_work_as_work",
                        "scope_current_work",
                        "alias_bridge",
                        "serialized_public_identity_scrubbed",
                    ],
                    "projected_reasons": [
                        "source_native_review_current_work",
                        "scope_current_work",
                    ],
                    "actions": ["shared_gate_runtime_block_repair_required"],
                }
            ],
        }

        repair = build_repair_queue(queue, queue_id="unit_repair")

        self.assertTrue(repair["rows"][0]["projection_runtime_scope_conflict"])
        self.assertEqual(repair["rows"][0]["projection_runtime_scope_conflict_kind"], "mixed_trace")
        self.assertEqual(
            repair["rows"][0]["runtime_scope_claim"],
            "RUNTIME_MIXED_CURRENT_AND_NONCURRENT",
        )
        self.assertIn("projection_runtime_scope_mixed_trace", repair["rows"][0]["repair_facets"])
        self.assertIn("projection_runtime_scope_trace_normalization_required", repair["rows"][0]["actions"])
        self.assertNotIn("projection_runtime_scope_reconciliation_required", repair["rows"][0]["actions"])
        self.assertEqual(
            repair["summary"]["projection_runtime_scope_conflict_kind_counts"],
            {"mixed_trace": 1},
        )

    def test_runtime_current_work_does_not_count_as_projection_scope_conflict(self):
        queue = {
            "queue_id": "unit_followup",
            "rows": [
                {
                    "post_id": 11702094,
                    "selected_title": "#더블오",
                    "projected_title": "#더블오",
                    "prior_runtime_audit_status": "FAIL_RUNTIME_PROMOTION_BLOCKED",
                    "prior_runtime_search_status": "SEARCH_DEGRADED_RECOVERED",
                    "prior_runtime_reason_codes": [
                        "row_discusses_work_as_work",
                        "scope_current_work",
                        "title_led_consumption_bridge",
                        "serialized_public_identity_scrubbed",
                    ],
                    "projected_reasons": [
                        "source_native_review_current_work",
                        "scope_current_work",
                    ],
                    "actions": ["shared_gate_runtime_block_repair_required"],
                }
            ],
        }

        repair = build_repair_queue(queue, queue_id="unit_repair")

        self.assertFalse(repair["rows"][0]["projection_runtime_scope_conflict"])
        self.assertEqual(repair["rows"][0]["runtime_scope_claim"], "RUNTIME_CURRENT_WORK")
        self.assertNotIn("projection_runtime_scope_reconciliation_required", repair["rows"][0]["actions"])
        self.assertEqual(
            repair["summary"]["projection_runtime_scope_conflict_counts"],
            {"no_conflict": 1},
        )
        self.assertEqual(
            repair["summary"]["projection_runtime_scope_conflict_kind_counts"],
            {"none": 1},
        )

    def test_title_url_markers_take_priority_over_scope_markers(self):
        queue = {
            "queue_id": "unit_followup",
            "rows": [
                {
                    "post_id": 11694019,
                    "selected_title": "혼후 순결",
                    "projected_title": "혼후 순결",
                    "prior_runtime_audit_status": "FAIL_RUNTIME_PROMOTION_BLOCKED",
                    "prior_runtime_search_status": "ok",
                    "prior_runtime_reason_codes": [
                        "row_discusses_work_as_work",
                        "scope_context_only",
                        "scope_not_current_work",
                        "url_title_mismatch",
                        "official_detail_url_title_mismatch_publish_blocked",
                        "serialized_public_identity_scrubbed",
                    ],
                    "actions": ["shared_gate_runtime_block_repair_required"],
                }
            ],
        }

        repair = build_repair_queue(queue, queue_id="unit_repair")

        self.assertEqual(
            repair["rows"][0]["primary_repair_lane"],
            "title_url_or_variant_trace_repair",
        )
        self.assertEqual(repair["rows"][0]["search_gate"], "SEARCH_OK")
        self.assertIn("title_url_or_variant_trace", repair["rows"][0]["repair_facets"])
        self.assertIn("scope_or_nonwork_monotonicity", repair["rows"][0]["repair_facets"])

    def test_invalid_prior_status_is_validation_issue(self):
        queue = {
            "queue_id": "unit_followup",
            "rows": [
                {
                    "post_id": 1,
                    "prior_runtime_audit_status": "PASS_EXACT_SAFE_RESOLVED",
                    "prior_runtime_reason_codes": ["serialized_public_identity_scrubbed"],
                    "actions": ["shared_gate_runtime_block_repair_required"],
                }
            ],
        }

        repair = build_repair_queue(queue, queue_id="unit_repair")

        self.assertEqual(repair["gate"], "NO-GO")
        self.assertEqual(repair["summary"]["validation_issue_count"], 1)


if __name__ == "__main__":
    unittest.main()
