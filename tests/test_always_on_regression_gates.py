import unittest

from tools.evaluate_always_on_regression_gates import evaluate_gates


def _golden(**overrides):
    payload = {
        "row_count": 16,
        "passed_count": 16,
        "failed_count": 0,
        "canary_semantic_gate": "PASS",
        "runtime": {
            "completed_count": 16,
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
