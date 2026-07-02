import unittest

from tools.triage_collateral_regressions import build_report


def _row(status, before_title, after_title, before_status="safe_resolved", after_status="safe_resolved"):
    return {
        "post_id": 1,
        "status": status,
        "is_regression": status != "same_title_url_changed",
        "before_identity": {
            "official_title": before_title,
            "heretic_url": "https://before",
            "title_resolution_state": "resolved" if before_title else "unresolved_matchable",
            "candidate_ledger_status": before_status,
            "candidate_count": 1,
        },
        "after_identity": {
            "official_title": after_title,
            "heretic_url": "https://after",
            "title_resolution_state": "resolved" if after_title else "unresolved_matchable",
            "candidate_ledger_status": after_status,
            "candidate_count": 2,
        },
    }


class CollateralRegressionTriageTest(unittest.TestCase):
    def test_triage_groups_collateral_regression_buckets(self):
        report = build_report(
            {
                "shared_post_count": 4,
                "changed_post_count": 4,
                "collateral_regression_count": 3,
                "rows": [
                    _row("null_to_resolved", None, "A", "promotion_blocked", "safe_resolved"),
                    _row("resolved_to_null", "B", None),
                    _row("resolved_to_different_title", "C", "D"),
                    _row("same_title_url_changed", "E", "E"),
                ],
            }
        )

        self.assertEqual(report["gate"], "NO-GO")
        self.assertEqual(report["summary"]["triaged_regression_rows"], 3)
        self.assertEqual(report["summary"]["counts_by_regression_bucket"]["unsafe_promotion_from_hold"], 1)
        self.assertEqual(report["summary"]["counts_by_regression_bucket"]["safe_loss_resolved_to_null"], 1)
        self.assertEqual(report["summary"]["counts_by_regression_bucket"]["wrong_work_title_flip"], 1)
        self.assertEqual(report["summary"]["counts_by_priority"]["P0"], 3)
        self.assertFalse(report["full_scan_approval"])


if __name__ == "__main__":
    unittest.main()
