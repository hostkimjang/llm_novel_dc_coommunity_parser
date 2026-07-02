import unittest

from tools.evaluate_always_on_regression_gates import evaluate_gates


def _golden(**overrides):
    payload = {
        "row_count": 18,
        "passed_count": 18,
        "failed_count": 0,
        "canary_semantic_gate": "PASS",
        "runtime": {
            "completed_count": 18,
            "pending_count": 0,
            "failed_count": 0,
        },
    }
    payload.update(overrides)
    return payload


def _collateral(**overrides):
    payload = {
        "shared_post_count": 375,
        "changed_post_count": 0,
        "collateral_regression_count": 0,
        "runtime_completed_count": 375,
        "runtime_pending_count": 0,
        "runtime_failed_count": 0,
    }
    payload.update(overrides)
    return payload


def _collateral_review(**overrides):
    payload = {
        "review_id": "unit_collateral_review",
        "gate": "REVIEW-LOCKED",
        "summary": {
            "batch_review_rows": 183,
            "reviewed_rows": 183,
            "unreviewed_batch_rows": 0,
            "validation_issue_count": 0,
            "label_counts": {"ACCEPT": 57, "REPROCESS": 95, "HOLD": 31},
            "action_counts": {
                "exclude_from_regression_count_after_gate_wiring": 57,
                "repair_safe_loss": 76,
            },
            "queue_transition": {
                "exclusion_candidate_rows": 57,
                "residual_action_queue_rows": 126,
            },
        },
    }
    payload.update(overrides)
    return payload


class AlwaysOnRegressionGatesTest(unittest.TestCase):
    def test_gate_go_requires_golden_and_full_collateral(self):
        report = evaluate_gates(golden=_golden(), collateral=_collateral())

        self.assertEqual(report["gate"], "GO")
        self.assertEqual(report["golden"]["gate"], "GO")
        self.assertEqual(report["collateral"]["gate"], "GO")
        self.assertFalse(report["full_scan_approval"])

    def test_golden_pass_alone_does_not_approve_without_375_collateral(self):
        report = evaluate_gates(
            golden=_golden(),
            collateral=_collateral(shared_post_count=16, runtime_completed_count=16),
        )

        self.assertEqual(report["gate"], "NO-GO")
        self.assertIn("collateral:collateral_shared_post_count_mismatch", report["blockers"])

    def test_collateral_regression_count_blocks_gate(self):
        report = evaluate_gates(
            golden=_golden(),
            collateral=_collateral(changed_post_count=223, collateral_regression_count=183),
        )

        self.assertEqual(report["gate"], "NO-GO")
        self.assertEqual(report["collateral"]["gate"], "NO-GO")
        self.assertIn("collateral:collateral_regression_count_nonzero", report["blockers"])

    def test_collateral_review_exclusions_reduce_but_do_not_hide_residual_queue(self):
        report = evaluate_gates(
            golden=_golden(),
            collateral=_collateral(changed_post_count=223, collateral_regression_count=183),
            collateral_review=_collateral_review(),
        )

        self.assertEqual(report["gate"], "NO-GO")
        self.assertEqual(report["collateral"]["collateral_regression_count"], 183)
        self.assertEqual(report["collateral"]["review_adjusted_regression_count"], 126)
        self.assertTrue(report["collateral"]["review_adjustment"]["applied"])
        self.assertEqual(report["collateral"]["review_adjustment"]["exclusion_candidate_rows"], 57)
        self.assertIn(
            "collateral:collateral_review_adjusted_regression_count_nonzero",
            report["blockers"],
        )

    def test_collateral_review_adjustment_requires_clean_full_review_summary(self):
        dirty_review = _collateral_review(
            summary={
                "batch_review_rows": 183,
                "reviewed_rows": 182,
                "unreviewed_batch_rows": 1,
                "validation_issue_count": 1,
                "action_counts": {
                    "exclude_from_regression_count_after_gate_wiring": 57,
                },
                "queue_transition": {"exclusion_candidate_rows": 57},
            }
        )

        report = evaluate_gates(
            golden=_golden(),
            collateral=_collateral(changed_post_count=223, collateral_regression_count=183),
            collateral_review=dirty_review,
        )

        self.assertEqual(report["gate"], "NO-GO")
        self.assertFalse(report["collateral"]["review_adjustment"]["applied"])
        self.assertEqual(report["collateral"]["review_adjusted_regression_count"], 183)
        self.assertIn("collateral:collateral_review_validation_issues_nonzero", report["blockers"])
        self.assertIn("collateral:collateral_review_not_fully_reviewed", report["blockers"])
        self.assertIn("collateral:collateral_review_unreviewed_rows_nonzero", report["blockers"])

    def test_full_review_exclusion_can_clear_collateral_gate_without_granting_full_scan_approval(self):
        review = _collateral_review(
            summary={
                "batch_review_rows": 183,
                "reviewed_rows": 183,
                "unreviewed_batch_rows": 0,
                "validation_issue_count": 0,
                "action_counts": {
                    "exclude_from_regression_count_after_gate_wiring": 183,
                },
                "queue_transition": {
                    "exclusion_candidate_rows": 183,
                    "residual_action_queue_rows": 0,
                },
            }
        )

        report = evaluate_gates(
            golden=_golden(),
            collateral=_collateral(changed_post_count=223, collateral_regression_count=183),
            collateral_review=review,
        )

        self.assertEqual(report["gate"], "GO")
        self.assertEqual(report["collateral"]["gate"], "GO")
        self.assertEqual(report["collateral"]["review_adjusted_regression_count"], 0)
        self.assertFalse(report["full_scan_approval"])

    def test_full_collateral_gate_requires_explicit_runtime_counts(self):
        collateral = _collateral()
        collateral.pop("runtime_completed_count")
        collateral.pop("runtime_pending_count")
        collateral.pop("runtime_failed_count")

        report = evaluate_gates(golden=_golden(), collateral=collateral)

        self.assertEqual(report["gate"], "NO-GO")
        self.assertEqual(report["collateral"]["gate"], "NO-GO")
        self.assertIn("collateral:collateral_runtime_counts_missing", report["blockers"])

    def test_golden_failure_blocks_even_when_collateral_clean(self):
        report = evaluate_gates(
            golden=_golden(passed_count=15, failed_count=1, canary_semantic_gate="NO-GO"),
            collateral=_collateral(),
        )

        self.assertEqual(report["gate"], "NO-GO")
        self.assertIn("golden:golden_expected_answer_failures", report["blockers"])
        self.assertIn("golden:golden_semantic_gate_not_pass", report["blockers"])


if __name__ == "__main__":
    unittest.main()
