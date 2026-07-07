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

    def test_prior_runtime_promotion_block_failure_requires_repair_before_replay(self) -> None:
        projection = {
            "projection_id": "unit_projection",
            "input_rows": 1,
            "rows": [
                {
                    "post_id": 11660271,
                    "projected_status": "safe_resolved",
                    "matches_source_native_title": True,
                    "selected_title": "월야의 여인들",
                    "projected_title": "월야의 여인들",
                    "projected_url": None,
                    "projected_reasons": ["scope_current_work"],
                }
            ],
        }
        prior_audit = {
            "rows": [
                {
                    "post_id": 11660271,
                    "expected_title": "월야의 여인들",
                    "actual_title": None,
                    "audit_status": "FAIL_RUNTIME_PROMOTION_BLOCKED",
                    "reason_codes": ["llm_only_sentence_candidate_pruned"],
                    "search_status": "SEARCH_DEGRADED_RECOVERED",
                }
            ]
        }

        queue = build_followup_queue(
            projection,
            prior_runtime_expected_audit=prior_audit,
        )

        self.assertEqual(queue["gate"], "REVIEW-LOCKED")
        self.assertEqual(queue["summary"]["runtime_replay_candidate_rows"], 0)
        self.assertEqual(
            queue["summary"]["prior_runtime_audit_status_counts"],
            {"FAIL_RUNTIME_PROMOTION_BLOCKED": 1},
        )
        self.assertIn(
            "prior_runtime_promotion_block_repair_required",
            queue["summary"]["action_counts"],
        )
        self.assertIn(
            "projection_followup_official_url_repair_required",
            queue["summary"]["action_counts"],
        )
        self.assertEqual(queue["rows"][0]["priority"], "P0")
        self.assertEqual(queue["rows"][0]["prior_runtime_reason_codes"], ["llm_only_sentence_candidate_pruned"])

    def test_prior_runtime_promotion_block_with_projection_url_becomes_seeded_replay_candidate(self) -> None:
        projection = {
            "projection_id": "unit_projection",
            "input_rows": 1,
            "rows": [
                {
                    "post_id": 11660273,
                    "projected_status": "safe_resolved",
                    "matches_source_native_title": True,
                    "selected_title": "마도서를 줍다 마법사가 되다",
                    "projected_title": "마도서를 줍다 마법사가 되다",
                    "projected_url": "https://novelpia.com/novel/414963",
                    "promotion_decision": {
                        "status": "publish",
                        "publish_allowed": True,
                        "official_title": "마도서를 줍다 마법사가 되다",
                        "official_url": "https://novelpia.com/novel/414963",
                        "reason_codes": ["scope_current_work"],
                    },
                    "promotion_gate_state": {
                        "candidate_title": "마도서를 줍다 마법사가 되다",
                        "candidate_url": "https://novelpia.com/novel/414963",
                        "official_title_exists": True,
                        "row_discusses_work_as_work": True,
                        "scope": {"scope_kind": "current_work", "confidence": "high"},
                    },
                    "promotion_gate_evidence": [
                        {"kind": "source_native_review", "supports_publish": True}
                    ],
                }
            ],
        }
        prior_audit = {
            "rows": [
                {
                    "post_id": 11660273,
                    "audit_status": "FAIL_RUNTIME_PROMOTION_BLOCKED",
                    "actual_title": None,
                    "reason_codes": ["serialized_public_identity_scrubbed"],
                }
            ]
        }

        queue = build_followup_queue(projection, prior_runtime_expected_audit=prior_audit)

        self.assertEqual(queue["summary"]["runtime_seed_replay_candidate_rows"], 1)
        self.assertNotIn("prior_runtime_promotion_block_repair_required", queue["summary"]["action_counts"])
        self.assertIn("runtime_replay_with_projection_followup_seed_required", queue["rows"][0]["actions"])
        self.assertEqual(queue["rows"][0]["owner_mode"], "RUNTIME_REPLAY_WITH_SHARED_GATE_SEED")
        self.assertEqual(queue["rows"][0]["promotion_gate_state"]["scope"]["scope_kind"], "current_work")

    def test_prior_runtime_exact_pass_still_requires_replay_recheck(self) -> None:
        projection = {
            "projection_id": "unit_projection",
            "input_rows": 1,
            "rows": [
                {
                    "post_id": 11660273,
                    "projected_status": "safe_resolved",
                    "matches_source_native_title": True,
                    "selected_title": "마도서를 줍다 마법사가 되다",
                    "projected_title": "마도서를 줍다 마법사가 되다",
                }
            ],
        }
        prior_audit = {
            "rows": [
                {
                    "post_id": 11660273,
                    "audit_status": "PASS_EXACT_SAFE_RESOLVED",
                    "actual_title": "마도서를 줍다 마법사가 되다",
                }
            ]
        }

        queue = build_followup_queue(
            projection,
            prior_runtime_expected_audit=prior_audit,
        )

        self.assertEqual(queue["summary"]["runtime_replay_candidate_rows"], 1)
        self.assertEqual(queue["rows"][0]["priority"], "P1")
        self.assertIn(
            "runtime_replay_projected_safe_resolved_exact_required",
            queue["rows"][0]["actions"],
        )

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
            runtime_manifest_json=Path("unit_manifest.json"),
        )

        self.assertEqual(manifest["runtime_replay_candidate_rows"], 1)
        self.assertEqual(manifest["runtime_input_rows"], 1)
        self.assertEqual(manifest["runtime_input_manifest_path"], "unit_manifest.json")
        self.assertEqual(manifest["requested_parallel"], 16)
        self.assertEqual(manifest["expected_effective_parallel"], 1)
        self.assertEqual(
            manifest["dashboard_contract"]["dashboard_policy"],
            "WEB_DASHBOARD_REQUIRED_FOR_TEST_RUNS",
        )
        self.assertEqual(manifest["dashboard_contract"]["dashboard_url"], "http://127.0.0.1:8080")
        self.assertIn("--no-dashboard", manifest["dashboard_contract"]["forbidden_flags"])
        self.assertNotIn("attach_manifest_command", manifest["dashboard_contract"])
        self.assertIn("expert_main result manifest", manifest["dashboard_attach_boundary"])
        self.assertEqual(manifest["missing_post_ids"], [])
        self.assertEqual(runtime_rows[0]["post_id"], 1)
        self.assertNotIn("analysis_result", runtime_rows[0])
        self.assertEqual(runtime_rows[0]["_loop_projection_followup"]["queue_id"], "unit_queue")
        self.assertEqual(
            runtime_rows[0]["_loop_projection_followup"]["approval_state"],
            "runtime_replay_required_not_approval",
        )

    def test_builds_runtime_input_for_seeded_prior_block_rows(self) -> None:
        projection = {
            "projection_id": "unit_projection",
            "input_rows": 1,
            "rows": [
                {
                    "post_id": 1,
                    "projected_status": "safe_resolved",
                    "matches_source_native_title": True,
                    "selected_title": "A",
                    "projected_title": "A",
                    "projected_url": "https://novelpia.com/novel/1",
                    "promotion_decision": {
                        "publish_allowed": True,
                        "official_title": "A",
                        "official_url": "https://novelpia.com/novel/1",
                    },
                    "promotion_gate_state": {
                        "candidate_title": "A",
                        "candidate_url": "https://novelpia.com/novel/1",
                        "official_title_exists": True,
                        "row_discusses_work_as_work": True,
                        "scope": {"scope_kind": "current_work"},
                    },
                }
            ],
        }
        prior_audit = {"rows": [{"post_id": 1, "audit_status": "FAIL_RUNTIME_PROMOTION_BLOCKED"}]}
        queue = build_followup_queue(projection, queue_id="unit_queue", prior_runtime_expected_audit=prior_audit)
        runtime_rows, manifest = build_runtime_replay_input(
            queue,
            [{"post_id": 1, "title": "A", "content": [], "comments": []}],
            source_result_path=Path("unit_result.json"),
        )

        self.assertEqual(manifest["runtime_replay_candidate_rows"], 1)
        self.assertEqual(manifest["requested_parallel"], 16)
        self.assertEqual(manifest["expected_effective_parallel"], 1)
        self.assertEqual(
            manifest["dashboard_contract"]["dashboard_policy"],
            "WEB_DASHBOARD_REQUIRED_FOR_TEST_RUNS",
        )
        self.assertNotIn("attach_manifest_command", manifest["dashboard_contract"])
        self.assertEqual(runtime_rows[0]["_loop_projection_followup"]["promotion_decision"]["official_title"], "A")
        self.assertTrue(runtime_rows[0]["_loop_projection_followup"]["matches_source_native_title"])


if __name__ == "__main__":
    unittest.main()
