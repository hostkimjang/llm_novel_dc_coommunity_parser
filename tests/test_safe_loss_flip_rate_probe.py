import json
import tempfile
import unittest
from pathlib import Path

from tools.safe_loss_flip_rate_probe import (
    analyze_flip_rate,
    build_probe_input,
    load_rows,
    write_probe_input,
)


def _input_row(post_id):
    return {"post_id": post_id, "title": f"title-{post_id}", "content": ["same"]}


def _result_row(post_id, status, title="작품", url="https://novelpia.com/novel/1"):
    return {
        "post_id": post_id,
        "analysis_result": {
            "identity": {
                "candidate_ledger_status": status,
                "novel_identity": {
                    "official_title": title if status == "safe_resolved" else None,
                    "heretic_url": url if status == "safe_resolved" else None,
                },
                "blocked_official_title": title if status != "safe_resolved" else None,
                "blocked_official_title_url": url if status != "safe_resolved" else None,
            }
        },
    }


class SafeLossFlipRateProbeTest(unittest.TestCase):
    def test_build_probe_input_duplicates_rows_without_metadata(self):
        rows, missing = build_probe_input(
            source_rows=[_input_row(11674712), _input_row(11660237)],
            post_ids=["11674712", "11660237"],
            repeats=3,
        )

        self.assertEqual(missing, [])
        self.assertEqual(len(rows), 6)
        self.assertEqual([row["post_id"] for row in rows], [11674712, 11660237] * 3)
        self.assertNotIn("_flip_probe", rows[0])

    def test_analyze_flip_rate_marks_oscillation_as_unresolved_nondeterminism(self):
        report = analyze_flip_rate(
            result_rows=[
                _result_row(11660237, "safe_resolved", "테라포밍"),
                _result_row(11660237, "promotion_blocked", "테라포밍"),
                _result_row(11660237, "safe_resolved", "테라포밍"),
            ],
            post_ids=["11660237"],
            repeats=3,
        )

        self.assertEqual(report["gate"], "NO-GO")
        self.assertTrue(report["summary"]["any_flip"])
        self.assertEqual(report["rows"][0]["classification"], "nondeterminism_unresolved")
        self.assertAlmostEqual(report["rows"][0]["flip_rate"], 1 / 3)
        self.assertFalse(report["hard_hold_relaxation_allowed"])

    def test_analyze_flip_rate_requires_blind_judge_before_hard_hold_relaxation(self):
        report = analyze_flip_rate(
            result_rows=[
                _result_row(11698880, "safe_resolved", "가챠 중독자의 퓨전펑크 생활"),
                _result_row(11698880, "safe_resolved", "가챠 중독자의 퓨전펑크 생활"),
            ],
            post_ids=["11698880"],
            repeats=2,
        )

        self.assertEqual(report["gate"], "REVIEW")
        self.assertEqual(report["rows"][0]["classification"], "stable_blind_judge_required")
        self.assertFalse(report["hard_hold_relaxation_allowed"])

    def test_analyze_flip_rate_allows_hard_hold_relaxation_only_after_blind_judge_match(self):
        report = analyze_flip_rate(
            result_rows=[
                _result_row(11698880, "safe_resolved", "가챠 중독자의 퓨전펑크 생활"),
                _result_row(11698880, "safe_resolved", "가챠 중독자의 퓨전펑크 생활"),
            ],
            post_ids=["11698880"],
            repeats=2,
            blind_judge={
                "11698880": {
                    "expected_status": "safe_resolved",
                    "expected_title": "가챠 중독자의 퓨전펑크 생활",
                    "expected_url": "https://novelpia.com/novel/1",
                }
            },
        )

        self.assertEqual(report["gate"], "GO")
        self.assertEqual(report["rows"][0]["classification"], "stable_blind_judge_confirmed")
        self.assertTrue(report["hard_hold_relaxation_allowed"])

    def test_load_rows_accepts_json_array(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "result.json"
            path.write_text(json.dumps([_result_row(1, "safe_resolved")]), encoding="utf-8")

            rows = load_rows(path)

            self.assertEqual(rows[0]["post_id"], 1)

    def test_write_probe_input_outputs_jsonl(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "probe.jsonl"
            write_probe_input([_input_row(1), _input_row(2)], path)

            lines = path.read_text(encoding="utf-8").splitlines()

            self.assertEqual(len(lines), 2)
            self.assertEqual(json.loads(lines[0])["post_id"], 1)


if __name__ == "__main__":
    unittest.main()
