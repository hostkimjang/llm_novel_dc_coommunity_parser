import tempfile
import unittest
from pathlib import Path

from tools.audit_search_recovery_overlay import audit_overlay, write_markdown


def split_report():
    return {
        "split_id": "unit_split",
        "source_compare_id": "unit_compare",
        "derived_sets": {"search_degraded_or_recovered_post_ids": [1, 2, 3]},
    }


def audit(path_name, audit_id, rows, gate="NO-GO"):
    return (
        Path(path_name),
        {
            "audit_id": audit_id,
            "gate": gate,
            "generated_at": "2026-07-09T00:00:00",
            "summary": {
                "expected_replay_rows": len(rows),
                "completed_rows": len(rows),
                "hard_blocker_row_count": sum(1 for row in rows if row.get("search_blocker_reason")),
                "total_unrecovered_degraded": sum(int(row.get("unrecovered_degraded") or 0) for row in rows),
            },
            "recovery_summary": {
                "run_id": audit_id,
                "large_run_complete": True,
                "integrity_classification": "clean_completed_run",
            },
            "rows": rows,
        },
    )


class AuditSearchRecoveryOverlayTest(unittest.TestCase):
    def test_later_audits_replace_hard_blockers(self):
        report = audit_overlay(
            split_report=split_report(),
            audit_payloads=[
                audit(
                    "base.json",
                    "base",
                    [
                        {
                            "post_id": 1,
                            "title": "one",
                            "search_status": "SEARCH_DEGRADED",
                            "unrecovered_degraded": 1,
                            "search_blocker_reason": "search_degraded",
                        },
                        {
                            "post_id": 2,
                            "title": "two",
                            "search_status": "SEARCH_DEGRADED_RECOVERED",
                            "unrecovered_degraded": 0,
                            "recovered_observation": "search_degraded_recovered",
                        },
                        {
                            "post_id": 3,
                            "title": "three",
                            "search_status": "MISSING",
                            "search_blocker_reason": "search_health_missing",
                        },
                    ],
                ),
                audit(
                    "fix.json",
                    "fix",
                    [
                        {"post_id": 1, "title": "one", "search_status": "ok", "unrecovered_degraded": 0},
                        {"post_id": 3, "title": "three", "search_status": "ok", "unrecovered_degraded": 0},
                    ],
                    gate="GO",
                ),
            ],
            audit_id="unit_overlay",
        )

        self.assertEqual(report["gate"], "GO")
        self.assertEqual(report["summary"]["held_rows"], 3)
        self.assertEqual(report["summary"]["covered_rows"], 3)
        self.assertEqual(report["summary"]["hard_blocker_row_count"], 0)
        self.assertEqual(report["summary"]["total_unrecovered_degraded"], 0)
        self.assertEqual(report["summary"]["source_counts"], {"base": 1, "fix": 2})

    def test_missing_held_row_blocks(self):
        report = audit_overlay(
            split_report=split_report(),
            audit_payloads=[audit("base.json", "base", [{"post_id": 1, "search_status": "ok"}])],
            audit_id="unit_overlay",
        )

        self.assertEqual(report["gate"], "NO-GO")
        self.assertEqual(report["missing_post_ids"], [2, 3])
        self.assertIn("held_rows_missing_from_overlay", report["summary"]["blockers"])

    def test_markdown_records_approval_boundary(self):
        report = audit_overlay(
            split_report={"derived_sets": {"search_degraded_or_recovered_post_ids": [1]}},
            audit_payloads=[audit("base.json", "base", [{"post_id": 1, "search_status": "ok"}], gate="GO")],
            audit_id="unit_overlay",
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "overlay.md"
            write_markdown(path, report)
            text = path.read_text(encoding="utf-8")

        self.assertIn("검색 복구 overlay 감사", text)
        self.assertIn("full375 collateral GO나 full_scan approval이 아니다", text)


if __name__ == "__main__":
    unittest.main()
