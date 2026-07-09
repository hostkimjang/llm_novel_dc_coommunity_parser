import tempfile
import unittest
from pathlib import Path

from tools.audit_search_non_ok_split import audit_split, write_markdown


def split_report(rows):
    return {
        "split_id": "unit_split",
        "source_compare_id": "unit_compare",
        "rows": rows,
    }


class AuditSearchNonOkSplitTest(unittest.TestCase):
    def test_splits_hard_replay_from_recovered_observations(self):
        report = audit_split(
            split_report(
                [
                    {"post_id": 1, "search_status": "ok", "primary_action": "ignore"},
                    {
                        "post_id": 2,
                        "search_status": "SEARCH_DEGRADED_RECOVERED",
                        "search_unrecovered_degraded": 0,
                        "primary_action": "hold_for_search_recovery_rerun",
                    },
                    {
                        "post_id": 3,
                        "search_status": "SEARCH_DEGRADED",
                        "search_unrecovered_degraded": 1,
                        "primary_action": "hold_for_search_recovery_rerun",
                    },
                    {
                        "post_id": 4,
                        "search_status": "MISSING",
                        "primary_action": "hold_for_search_health_missing",
                    },
                ]
            ),
            audit_id="unit_non_ok",
        )

        self.assertEqual(report["gate"], "NO-GO")
        self.assertEqual(report["summary"]["non_ok_rows"], 3)
        self.assertEqual(report["summary"]["hard_replay_rows"], 2)
        self.assertEqual(report["summary"]["recovered_observation_rows"], 1)
        self.assertEqual(report["summary"]["hard_post_ids"], [3, 4])
        self.assertEqual(
            report["summary"]["hard_reason_counts"],
            {"search_degraded": 1, "search_health_missing": 1},
        )

    def test_recovered_only_rows_do_not_block_current_search_gate(self):
        report = audit_split(
            split_report(
                [
                    {
                        "post_id": 10,
                        "search_status": "SEARCH_DEGRADED_RECOVERED",
                        "unrecovered_degraded": 0,
                    }
                ]
            ),
            audit_id="unit_non_ok",
        )

        self.assertEqual(report["gate"], "GO")
        self.assertEqual(report["summary"]["hard_replay_rows"], 0)
        self.assertEqual(report["summary"]["recovered_observation_post_ids"], [10])

    def test_markdown_records_approval_boundary(self):
        report = audit_split(
            split_report([{"post_id": 5, "search_status": "MISSING"}]),
            audit_id="unit_non_ok",
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "non_ok.md"
            write_markdown(path, report)
            text = path.read_text(encoding="utf-8")

        self.assertIn("full375 collateral GO나 full_scan approval이 아니다", text)
        self.assertIn("runtime replay 대상", text)


if __name__ == "__main__":
    unittest.main()
