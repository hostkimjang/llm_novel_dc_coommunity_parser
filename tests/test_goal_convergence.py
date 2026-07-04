import json
import tempfile
import unittest
from pathlib import Path

from tools.evaluate_goal_convergence import (
    actionable_count,
    evaluate_convergence,
    load_rows,
    packet_summary,
)


def _row(post_id, status):
    return {
        "post_id": post_id,
        "analysis_result": {
            "identity": {
                "candidate_ledger_status": status,
            }
        },
    }


class GoalConvergenceTest(unittest.TestCase):
    def test_actionable_count_prefers_explicit_next_queue(self):
        payload = {
            "summary": {"next_actionable_queue": 130, "total_actions": 999},
            "actions": [{"status": "ready"}],
        }

        count, source = actionable_count(payload)

        self.assertEqual(count, 130)
        self.assertEqual(source, "summary.next_actionable_queue")

    def test_actionable_count_reads_residual_queue_summary_artifact(self):
        payload = {
            "report_type": "collateral_residual_action_queue",
            "summary": {"residual_action_queue_rows": 101},
        }

        count, source = actionable_count(payload)

        self.assertEqual(count, 101)
        self.assertEqual(source, "summary.residual_action_queue_rows")

    def test_packet_summary_counts_safe_resolved_rows(self):
        summary = packet_summary(
            [
                _row(11660237, "safe_resolved"),
                _row(11674712, "promotion_blocked"),
                _row(11698880, "safe_resolved"),
            ]
        )

        self.assertEqual(summary["row_count"], 3)
        self.assertEqual(summary["safe_resolved_count"], 2)
        self.assertEqual(summary["safe_resolved_post_ids"], ["11660237", "11698880"])

    def test_convergence_gate_go_requires_queue_decrease_and_safe_monotonic_packet(self):
        report = evaluate_convergence(
            {"summary": {"next_actionable_queue": 131}},
            {"summary": {"next_actionable_queue": 130}},
            [
                _row(11660237, "safe_resolved"),
                _row(11674712, "promotion_blocked"),
                _row(11698880, "promotion_blocked"),
            ],
            [
                _row(11660237, "safe_resolved"),
                _row(11674712, "safe_resolved"),
                _row(11698880, "promotion_blocked"),
            ],
        )

        self.assertEqual(report["gate"], "GO")
        self.assertTrue(report["actionable_queue"]["decreased"])
        self.assertTrue(report["packet"]["same_packet"])
        self.assertTrue(report["packet"]["safe_resolved_monotonic_nondecrease"])
        self.assertEqual(report["packet"]["safe_gain_post_ids"], ["11674712"])

    def test_convergence_gate_blocks_loop_count_without_actionable_decrease(self):
        report = evaluate_convergence(
            {"summary": {"next_actionable_queue": 131}},
            {"summary": {"next_actionable_queue": 131}},
            [_row(1, "safe_resolved"), _row(2, "promotion_blocked")],
            [_row(1, "safe_resolved"), _row(2, "safe_resolved")],
        )

        self.assertEqual(report["gate"], "NO-GO")
        self.assertIn("actionable_queue_not_decreased", {item["code"] for item in report["blockers"]})

    def test_convergence_gate_blocks_safe_loss_on_same_packet(self):
        report = evaluate_convergence(
            {"summary": {"next_actionable_queue": 131}},
            {"summary": {"next_actionable_queue": 130}},
            [
                _row(11660237, "safe_resolved"),
                _row(11674712, "safe_resolved"),
                _row(11698880, "promotion_blocked"),
            ],
            [
                _row(11660237, "promotion_blocked"),
                _row(11674712, "safe_resolved"),
                _row(11698880, "safe_resolved"),
            ],
        )

        self.assertEqual(report["gate"], "NO-GO")
        self.assertFalse(report["packet"]["safe_resolved_monotonic_nondecrease"])
        self.assertEqual(report["packet"]["safe_loss_post_ids"], ["11660237"])
        self.assertTrue(report["packet"]["safe_delta_evaluated"])

    def test_convergence_gate_does_not_report_safe_loss_when_packet_changes(self):
        report = evaluate_convergence(
            {"summary": {"next_actionable_queue": 2}},
            {"summary": {"next_actionable_queue": 1}},
            [
                _row(11660237, "safe_resolved"),
                _row(11674712, "safe_resolved"),
            ],
            [
                _row(11660237, "safe_resolved"),
            ],
        )

        self.assertEqual(report["gate"], "NO-GO")
        self.assertFalse(report["packet"]["same_packet"])
        self.assertFalse(report["packet"]["safe_delta_evaluated"])
        self.assertEqual(report["packet"]["safe_loss_post_ids"], [])
        self.assertEqual(report["packet"]["safe_gain_post_ids"], [])
        self.assertIn("packet_identity_changed", {item["code"] for item in report["blockers"]})

    def test_load_rows_accepts_jsonl(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rows.jsonl"
            path.write_text(
                "\n".join(json.dumps(_row(post_id, "safe_resolved")) for post_id in (1, 2)) + "\n",
                encoding="utf-8",
            )

            rows = load_rows(path)

            self.assertEqual([row["post_id"] for row in rows], [1, 2])


if __name__ == "__main__":
    unittest.main()
