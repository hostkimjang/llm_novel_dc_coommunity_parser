from __future__ import annotations

import unittest

from tools.build_runtime_expected_failure_queue import build_failure_queue


class RuntimeExpectedFailureQueueTest(unittest.TestCase):
    def test_splits_failures_and_projection_still_blocked(self) -> None:
        expected_audit = {
            "run_id": "unit_run",
            "summary": {
                "row_count": 4,
                "exact_safe_resolved_fail": 3,
            },
            "rows": [
                {
                    "post_id": 1,
                    "audit_status": "PASS_EXACT_SAFE_RESOLVED",
                    "expected_title": "A",
                    "actual_title": "A",
                    "safe_resolved": True,
                },
                {
                    "post_id": 2,
                    "audit_status": "FAIL_RUNTIME_PROMOTION_BLOCKED",
                    "expected_title": "B",
                    "actual_title": "B",
                    "candidate_ledger_status": "promotion_blocked",
                    "promotion_status": "candidate_only",
                    "search_status": "SEARCH_DEGRADED",
                    "search_degraded": 5,
                    "search_unrecovered_degraded": 2,
                    "reason_codes": ["official_title_exists", "serialized_public_identity_scrubbed"],
                },
                {
                    "post_id": 3,
                    "audit_status": "FAIL_SAFE_RESOLVED_TITLE_MISMATCH",
                    "expected_title": "C",
                    "actual_title": "C 외전",
                    "safe_resolved": True,
                    "publish_allowed": True,
                    "search_status": "SEARCH_DEGRADED_RECOVERED",
                    "search_degraded": 1,
                    "search_unrecovered_degraded": 0,
                    "reason_codes": ["official_detail_url"],
                },
                {
                    "post_id": 4,
                    "audit_status": "FAIL_VARIANT_COMPACT_MATCH_ONLY",
                    "expected_title": "인간실격",
                    "actual_title": "인간 실격",
                    "search_status": "ok",
                    "reason_codes": ["official_title_exists"],
                },
            ],
        }
        projection = {
            "projection_id": "unit_projection",
            "rows": [
                {
                    "post_id": 5,
                    "projected_status": "promotion_blocked",
                    "selected_title": None,
                    "projected_title": None,
                    "source_actions": ["candidate_set_rebuild_required"],
                    "projected_reasons": ["candidate_set_rebuild_required", "scope_context_only"],
                }
            ],
        }

        queue = build_failure_queue(
            expected_audit,
            projection=projection,
            generated_at="2026-07-06T13:00:00",
            queue_id="unit_queue",
        )

        self.assertEqual(queue["gate"], "REVIEW-LOCKED")
        self.assertFalse(queue["full_scan_approval"])
        self.assertEqual(queue["summary"]["expected_rows"], 4)
        self.assertEqual(queue["summary"]["passed_rows_excluded"], 1)
        self.assertEqual(queue["summary"]["failed_rows"], 3)
        self.assertEqual(queue["summary"]["projection_still_blocked_rows"], 1)
        self.assertEqual(queue["summary"]["action_queue_rows"], 4)
        self.assertEqual(queue["summary"]["source_audit_status_counts"]["PASS_EXACT_SAFE_RESOLVED"], 1)
        self.assertEqual(queue["summary"]["search_unrecovered_degraded_rows"], 1)
        self.assertEqual(queue["summary"]["search_unrecovered_degraded_total"], 2)
        self.assertEqual(queue["summary"]["priority_counts"], {"P0": 2, "P1": 1, "P2": 1})
        self.assertEqual(queue["summary"]["label_counts"], {"HOLD": 3, "REPROCESS": 1})
        self.assertIn("shared_gate_runtime_block_repair_required", queue["summary"]["action_counts"])
        self.assertIn("search_degraded_or_timeout_replay_required", queue["summary"]["action_counts"])
        self.assertIn("candidate_set_rebuild_required", queue["summary"]["action_counts"])

    def test_reports_summary_count_mismatches(self) -> None:
        expected_audit = {
            "summary": {
                "row_count": 2,
                "exact_safe_resolved_fail": 2,
            },
            "rows": [
                {
                    "post_id": 1,
                    "audit_status": "PASS_EXACT_SAFE_RESOLVED",
                    "expected_title": "A",
                    "actual_title": "A",
                    "safe_resolved": True,
                }
            ],
        }

        queue = build_failure_queue(expected_audit)

        self.assertEqual(queue["gate"], "NO-GO")
        self.assertEqual(queue["summary"]["validation_issue_count"], 2)
        self.assertEqual(
            {issue["code"] for issue in queue["validation_issues"]},
            {"expected_audit_row_count_mismatch", "expected_audit_fail_count_mismatch"},
        )


if __name__ == "__main__":
    unittest.main()
