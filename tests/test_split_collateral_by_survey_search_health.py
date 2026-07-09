import json
import tempfile
import unittest
from pathlib import Path

from tools.split_collateral_by_survey_search_health import classify_rows, write_markdown


def result_row(post_id, status):
    health = None if status is None else {"status": status, "queries": 1, "degraded": 0, "degraded_recovered": 0, "unrecovered_degraded": 0}
    return {
        "post_id": post_id,
        "title": f"post {post_id}",
        "analysis_result": {"identity": {"search_health": health}},
    }


def compare_row(post_id, status, before="A", after=None):
    return {
        "post_id": post_id,
        "status": status,
        "is_regression": True,
        "before_identity": {"official_title": before},
        "after_identity": {"official_title": after},
    }


class SplitCollateralBySurveySearchHealthTest(unittest.TestCase):
    def test_splits_expected_fp_intended_search_and_true_triage(self):
        collateral = {
            "compare_id": "unit",
            "rows": [
                compare_row(1, "resolved_to_null", before="wrong", after=None),
                compare_row(2, "null_to_resolved", before=None, after="right"),
                compare_row(3, "resolved_to_different_title", before="wrong", after="right"),
                compare_row(4, "resolved_to_null", before="maybe", after=None),
                compare_row(5, "resolved_to_null", before="maybe", after=None),
            ],
        }
        survey = {
            1: {"post_id": 1, "disagreement_type": "over_resolved", "failure_class": "over_resolved_nonwork"},
            2: {"post_id": 2, "disagreement_type": "under_resolved_false_negative", "failure_class": "recall_miss"},
            3: {"post_id": 3, "disagreement_type": "wrong_work", "failure_class": "wrong_work_among_aliases"},
        }
        report = classify_rows(
            collateral_compare=collateral,
            survey_errors=survey,
            after_rows=[
                result_row(1, "SEARCH_DEGRADED"),
                result_row(2, "ok"),
                result_row(3, "SEARCH_DEGRADED_RECOVERED"),
                result_row(4, "ok"),
                result_row(5, None),
            ],
            split_id="unit",
        )

        self.assertEqual(report["summary"]["expected_fp_removal_rows"], 1)
        self.assertEqual(report["summary"]["intended_recovery_blind_judge_rows"], 2)
        self.assertEqual(report["summary"]["search_degraded_or_recovered_overlay_rows"], 2)
        self.assertEqual(report["summary"]["true_triage_ok_search_nonfp_rows"], 1)
        self.assertEqual(report["summary"]["search_health_missing_rows"], 1)
        actions = {row["post_id"]: row["primary_action"] for row in report["rows"]}
        self.assertEqual(actions[1], "expected_fp_removal_exempt")
        self.assertEqual(actions[2], "blind_judge_title_correctness")
        self.assertEqual(actions[3], "blind_judge_title_correctness")
        self.assertEqual(actions[4], "true_triage_ok_search_nonfp")
        self.assertEqual(actions[5], "hold_for_search_health_missing")

    def test_markdown_records_search_gate_boundary(self):
        report = {
            "split_id": "unit",
            "source_compare_id": "unit_compare",
            "raw_regression_rows": 1,
            "summary": {
                "expected_fp_removal_rows": 0,
                "intended_recovery_blind_judge_rows": 0,
                "intended_recall_miss_rows": 0,
                "intended_wrong_work_rows": 0,
                "search_degraded_or_recovered_overlay_rows": 1,
                "ok_search_non_fp_rows_before_blind_judge": 0,
                "true_triage_ok_search_nonfp_rows": 0,
                "search_health_missing_rows": 0,
            },
            "derived_sets": {
                "expected_fp_removal_post_ids": [],
                "intended_recovery_blind_judge_post_ids": [],
                "true_triage_ok_search_nonfp_post_ids": [],
            },
            "health_evidence": {
                "run_search_evidence": {
                    "row_search_health": {
                        "degraded_total": 7,
                        "unrecovered_degraded_total": 2,
                    }
                }
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "report.md"
            write_markdown(path, report)
            text = path.read_text(encoding="utf-8")
        self.assertIn("검색 선결", text)
        self.assertIn("unit_compare", text)
        self.assertIn("degraded query `7`", text)
        self.assertNotIn("Loop609 health audit", text)
        self.assertIn("회귀 판정 근거로 쓰지 않는다", text)


if __name__ == "__main__":
    unittest.main()
