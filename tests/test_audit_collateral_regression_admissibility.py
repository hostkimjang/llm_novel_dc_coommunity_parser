import tempfile
import unittest
from pathlib import Path

from tools.audit_collateral_regression_admissibility import audit_split_report, write_markdown


def split_report(*, run_gate="REVIEW", degraded=1801, unrecovered=234):
    return {
        "split_id": "unit_split",
        "source_compare_id": "unit_compare",
        "raw_regression_rows": 139,
        "summary": {
            "expected_fp_removal_rows": 42,
            "intended_recovery_blind_judge_rows": 24,
            "intended_recall_miss_rows": 15,
            "intended_wrong_work_rows": 9,
            "search_degraded_or_recovered_overlay_rows": 109,
            "ok_search_non_fp_rows_before_blind_judge": 15,
            "true_triage_ok_search_nonfp_rows": 10,
            "search_health_missing_rows": 9,
        },
        "health_evidence": {
            "run_search_evidence": {
                "gate": run_gate,
                "row_search_health": {
                    "degraded_total": degraded,
                    "unrecovered_degraded_total": unrecovered,
                },
            }
        },
        "derived_sets": {
            "expected_fp_removal_post_ids": [1],
            "intended_recovery_blind_judge_post_ids": [2],
            "search_degraded_or_recovered_post_ids": [3],
            "true_triage_ok_search_nonfp_post_ids": [4, 5],
        },
    }


class AuditCollateralRegressionAdmissibilityTest(unittest.TestCase):
    def test_marks_search_unhealthy_collateral_as_not_admissible(self):
        report = audit_split_report(
            split_report(),
            audit_id="unit",
            expected_counts={
                "raw_regression_rows": 139,
                "expected_fp_removal_rows": 42,
                "intended_recovery_blind_judge_rows": 24,
                "intended_recall_miss_rows": 15,
                "intended_wrong_work_rows": 9,
                "search_degraded_or_recovered_overlay_rows": 109,
                "ok_search_non_fp_rows_before_blind_judge": 15,
                "true_triage_ok_search_nonfp_rows": 10,
                "degraded_query_total": 1801,
                "unrecovered_degraded_total": 234,
            },
        )

        self.assertEqual(report["gate"], "NO-GO")
        self.assertEqual(report["collateral_regression_evidence"], "NOT_ADMISSIBLE")
        self.assertEqual(report["full375_rerun_gate"], "BLOCKED_UNTIL_SEARCH_RECOVERY_FOR_HELD_ROWS")
        self.assertEqual(report["validation"]["issue_count"], 0)
        self.assertEqual(report["blockers"]["count"], 1)
        self.assertEqual(report["post_id_sets"]["true_triage_ok_search_nonfp_post_ids"], [4, 5])

    def test_count_mismatch_is_validation_issue(self):
        report = audit_split_report(
            split_report(),
            audit_id="unit",
            expected_counts={"expected_fp_removal_rows": 41},
        )

        self.assertEqual(report["validation"]["issue_count"], 1)
        self.assertEqual(report["validation"]["issues"][0]["field"], "expected_fp_removal_rows")

    def test_markdown_records_search_evidence_boundary(self):
        report = audit_split_report(split_report(), audit_id="unit")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.md"
            write_markdown(path, report)
            text = path.read_text(encoding="utf-8")

        self.assertIn("회귀 판정 근거로 쓰지 않는다", text)
        self.assertIn("degraded query `1801`", text)
        self.assertIn("true_triage_ok_search_nonfp", text)


if __name__ == "__main__":
    unittest.main()
