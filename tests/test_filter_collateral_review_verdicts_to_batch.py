import unittest
from pathlib import Path

from tools.filter_collateral_review_verdicts_to_batch import filter_verdicts_to_batch


class FilterCollateralReviewVerdictsToBatchTest(unittest.TestCase):
    def test_filters_verdict_rows_to_current_batch_post_ids(self) -> None:
        batch = {
            "review_rows": [
                {"post_id": 10},
                {"post_id": 20},
            ]
        }
        verdicts = {
            "review_id": "prior_review",
            "rows": [
                {
                    "post_id": 10,
                    "selected_option_id": "C1",
                    "review_label": "REPROCESS",
                    "source_native_verdict": "needs_repair",
                    "evidence_refs": ["old#post_id=10"],
                },
                {
                    "post_id": 30,
                    "selected_option_id": "C1",
                    "review_label": "ACCEPT",
                    "source_native_verdict": "closed_old_row",
                },
            ],
        }

        report = filter_verdicts_to_batch(
            batch=batch,
            verdicts_list=[verdicts],
            source_paths=[Path("prior_verdicts.json")],
            review_id="current_review",
            scope="current batch",
        )

        self.assertEqual(report["gate"], "REVIEW-LOCKED")
        self.assertEqual(report["summary"]["kept_rows"], 1)
        self.assertEqual(report["summary"]["dropped_rows"], 1)
        self.assertEqual(report["summary"]["missing_batch_post_ids"], 1)
        self.assertEqual([row["post_id"] for row in report["rows"]], [10])
        self.assertEqual(report["dropped_rows"][0]["post_id"], 30)
        self.assertEqual(report["missing_post_ids"], [20])


if __name__ == "__main__":
    unittest.main()
