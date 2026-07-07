import unittest

from tools.merge_collateral_review_summaries import build_merged_summary


def _summary(review_id, rows, *, gate="REVIEW-LOCKED"):
    exclusion_count = sum(
        1
        for row in rows
        if "exclude_from_regression_count_after_gate_wiring" in (row.get("action") or [])
    )
    repair_count = sum(1 for row in rows if row.get("review_label") == "REPROCESS")
    hold_count = sum(1 for row in rows if row.get("review_label") == "HOLD")
    info_missing_count = sum(1 for row in rows if row.get("review_label") == "INFO_MISSING")
    label_counts = {}
    bucket_counts = {}
    action_counts = {}
    verdict_counts = {}
    for row in rows:
        label_counts[row.get("review_label", "")] = label_counts.get(row.get("review_label", ""), 0) + 1
        bucket_counts[row.get("triage_bucket", "")] = bucket_counts.get(row.get("triage_bucket", ""), 0) + 1
        verdict_counts[row.get("source_native_verdict", "")] = verdict_counts.get(
            row.get("source_native_verdict", ""), 0
        ) + 1
        for action in row.get("action") or []:
            action_counts[action] = action_counts.get(action, 0) + 1
    return {
        "review_id": review_id,
        "gate": gate,
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "summary": {
            "batch_review_rows": len(rows),
            "reviewed_rows": len(rows),
            "source_native_decision_rows": len(rows) - info_missing_count,
            "info_missing_rows": info_missing_count,
            "unreviewed_batch_rows": 0,
            "unreviewed_or_info_missing_batch_rows": info_missing_count,
            "validation_issue_count": 0,
            "counts_by_bucket": bucket_counts,
            "label_counts": label_counts,
            "source_native_verdict_counts": verdict_counts,
            "action_counts": action_counts,
            "queue_transition": {
                "original_p0_rows": len(rows),
                "source_native_reviewed_rows": len(rows),
                "source_native_decision_rows": len(rows) - info_missing_count,
                "info_missing_rows": info_missing_count,
                "exclusion_candidate_rows": exclusion_count,
                "repair_required_rows": repair_count,
                "policy_or_native_review_required_rows": hold_count,
                "residual_action_queue_rows": len(rows) - exclusion_count,
                "validation_issue_count": 0,
                "full_collateral_approval_open": False,
            },
        },
        "rows": rows,
    }


class MergeCollateralReviewSummariesTest(unittest.TestCase):
    def test_merges_clean_summaries_and_preserves_queue_accounting(self):
        first = _summary(
            "first",
            [
                {
                    "post_id": 1,
                    "triage_bucket": "wrong_work_title_flip",
                    "review_label": "ACCEPT",
                    "source_native_verdict": "after_correct",
                    "action": ["exclude_from_regression_count_after_gate_wiring"],
                },
                {
                    "post_id": 2,
                    "triage_bucket": "safe_loss_resolved_to_null",
                    "review_label": "INFO_MISSING",
                    "source_native_verdict": "needs_review",
                    "action": ["native_web_or_image_evidence_required"],
                },
            ],
        )
        second = _summary(
            "second",
            [
                {
                    "post_id": 3,
                    "triage_bucket": "unsafe_promotion_from_hold",
                    "review_label": "HOLD",
                    "source_native_verdict": "alias_bridge_unverified_hold",
                    "action": ["native_web_or_alias_relation_review_required"],
                }
            ],
        )

        merged = build_merged_summary(summaries=[first, second], review_id="merged", scope="unit merge")

        transition = merged["summary"]["queue_transition"]
        self.assertEqual(merged["gate"], "REVIEW-LOCKED")
        self.assertEqual(merged["summary"]["batch_review_rows"], 3)
        self.assertEqual(merged["summary"]["reviewed_rows"], 3)
        self.assertEqual(merged["summary"]["source_native_decision_rows"], 2)
        self.assertEqual(merged["summary"]["info_missing_rows"], 1)
        self.assertEqual(transition["exclusion_candidate_rows"], 1)
        self.assertEqual(transition["policy_or_native_review_required_rows"], 1)
        self.assertEqual(transition["residual_action_queue_rows"], 2)
        self.assertEqual(merged["summary"]["label_counts"]["ACCEPT"], 1)
        self.assertEqual(merged["summary"]["counts_by_bucket"]["unsafe_promotion_from_hold"], 1)

    def test_duplicate_post_id_keeps_no_go(self):
        first = _summary(
            "first",
            [{"post_id": 1, "review_label": "ACCEPT", "source_native_verdict": "after_correct", "action": []}],
        )
        second = _summary(
            "second",
            [{"post_id": 1, "review_label": "ACCEPT", "source_native_verdict": "after_correct", "action": []}],
        )

        merged = build_merged_summary(summaries=[first, second], review_id="merged", scope="unit merge")

        self.assertEqual(merged["gate"], "NO-GO")
        self.assertEqual(merged["summary"]["validation_issue_count"], 2)
        self.assertIn("duplicate_post_id", merged["validation_issues"][0]["issues"])

    def test_source_gate_issue_keeps_no_go(self):
        summary = _summary(
            "bad",
            [{"post_id": 1, "review_label": "ACCEPT", "source_native_verdict": "after_correct", "action": []}],
            gate="NO-GO",
        )

        merged = build_merged_summary(summaries=[summary], review_id="merged", scope="unit merge")

        self.assertEqual(merged["gate"], "NO-GO")
        self.assertEqual(merged["summary"]["validation_issue_count"], 1)


if __name__ == "__main__":
    unittest.main()
