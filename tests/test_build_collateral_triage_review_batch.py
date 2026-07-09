import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tools.build_collateral_triage_review_batch import build_review_batch, write_markdown


def _triage_row(post_id, bucket, status, before_title, after_title):
    return {
        "post_id": post_id,
        "priority": "P0",
        "triage_bucket": bucket,
        "status": status,
        "is_regression": True,
        "before_title": before_title,
        "after_title": after_title,
        "before_url": "https://before.example" if before_title else None,
        "after_url": "https://after.example" if after_title else None,
        "before_candidate_ledger_status": "promotion_blocked" if before_title is None else "safe_resolved",
        "after_candidate_ledger_status": "promotion_blocked" if after_title is None else "safe_resolved",
        "before_title_resolution_state": "unresolved_matchable" if before_title is None else "resolved",
        "after_title_resolution_state": "unresolved_matchable" if after_title is None else "resolved",
        "before_candidate_count": 1,
        "after_candidate_count": 2,
    }


def _result(post_id, title):
    return {
        "post_id": post_id,
        "analysis_result": {
            "identity": {
                "reason_lines": ["judge input must not include this"],
                "novel_identity": {"official_title": title, "heretic_url": "https://work.example" if title else None},
                "title_resolution_state": "resolved" if title else "unresolved_matchable",
                "candidate_ledger_status": "safe_resolved" if title else "promotion_blocked",
                "candidate_ledger": {
                    "candidate_count": 1,
                    "title_candidates": [title] if title else [],
                    "promotion_blocked_reasons": ["search degraded"],
                },
            }
        },
    }


class BuildCollateralTriageReviewBatchTest(unittest.TestCase):
    def test_builds_blind_source_native_rows_without_reason_lines(self):
        report = build_review_batch(
            triage_report={
                "rows": [
                    _triage_row(10, "wrong_work_title_flip", "resolved_to_different_title", "A", "B"),
                    _triage_row(11, "unsafe_promotion_from_hold", "null_to_resolved", None, "C"),
                    _triage_row(12, "safe_loss_resolved_to_null", "resolved_to_null", "D", None),
                    {**_triage_row(13, "non_regression_change", "same_title_url_changed", "E", "E"), "priority": "P2"},
                ]
            },
            panel_rows={
                10: {"post_id": 10, "title": "post A", "content": ["body"], "comments": ["comment"], "url": "https://post/10"},
                11: {"post_id": 11, "title": "post C", "content": [], "comments": []},
                12: {"post_id": 12, "title": "post D", "content": [], "comments": []},
            },
            baseline_rows={10: _result(10, "A"), 11: _result(11, None), 12: _result(12, "D")},
            after_rows={10: _result(10, "B"), 11: _result(11, "C"), 12: _result(12, None)},
            generated_at="2026-07-02T00:00:00",
        )

        self.assertEqual(report["gate"], "REVIEW-LOCKED")
        self.assertEqual(report["summary"]["selected_review_rows"], 3)
        self.assertEqual(report["summary"]["counts_by_bucket"]["wrong_work_title_flip"], 1)
        self.assertFalse(report["full_scan_approval"])
        first = report["review_rows"][0]
        self.assertEqual(first["post_id"], 10)
        self.assertEqual([item["option_id"] for item in first["blind_judge_options"]], ["C1", "C2"])
        self.assertNotIn("reason_lines", str(first["source_native_packet"]))
        self.assertNotIn("reason_lines", str(first["blind_judge_options"]))
        self.assertIn("comparison_private_not_for_blind_judge", first)

    def test_per_bucket_limit_is_deterministic(self):
        report = build_review_batch(
            triage_report={
                "rows": [
                    _triage_row(20, "safe_loss_resolved_to_null", "resolved_to_null", "A", None),
                    _triage_row(19, "safe_loss_resolved_to_null", "resolved_to_null", "B", None),
                    _triage_row(18, "unsafe_promotion_from_hold", "null_to_resolved", None, "C"),
                    _triage_row(17, "wrong_work_title_flip", "resolved_to_different_title", "D", "E"),
                ]
            },
            panel_rows={post_id: {"post_id": post_id, "title": f"post {post_id}"} for post_id in range(17, 21)},
            baseline_rows={},
            after_rows={},
            per_bucket_limit=1,
            generated_at="2026-07-02T00:00:00",
        )

        self.assertEqual([row["post_id"] for row in report["review_rows"]], [17, 18, 19])
        self.assertEqual(report["summary"]["selected_review_rows"], 3)

    def test_bucket_filter_selects_only_requested_bucket(self):
        report = build_review_batch(
            triage_report={
                "rows": [
                    _triage_row(20, "safe_loss_resolved_to_null", "resolved_to_null", "A", None),
                    _triage_row(18, "unsafe_promotion_from_hold", "null_to_resolved", None, "C"),
                    _triage_row(17, "wrong_work_title_flip", "resolved_to_different_title", "D", "E"),
                ]
            },
            panel_rows={post_id: {"post_id": post_id, "title": f"post {post_id}"} for post_id in (17, 18, 20)},
            baseline_rows={},
            after_rows={},
            buckets={"unsafe_promotion_from_hold"},
            generated_at="2026-07-02T00:00:00",
        )

        self.assertEqual([row["post_id"] for row in report["review_rows"]], [18])
        self.assertEqual(report["summary"]["counts_by_bucket"], {"unsafe_promotion_from_hold": 1})
        self.assertEqual(report["summary"]["bucket_filter"], ["unsafe_promotion_from_hold"])

    def test_exclude_post_ids_removes_closed_rows_before_batch_selection(self):
        report = build_review_batch(
            triage_report={
                "rows": [
                    _triage_row(20, "safe_loss_resolved_to_null", "resolved_to_null", "A", None),
                    _triage_row(18, "unsafe_promotion_from_hold", "null_to_resolved", None, "C"),
                    _triage_row(17, "wrong_work_title_flip", "resolved_to_different_title", "D", "E"),
                ]
            },
            panel_rows={post_id: {"post_id": post_id, "title": f"post {post_id}"} for post_id in (17, 18, 20)},
            baseline_rows={},
            after_rows={},
            exclude_post_ids={18},
            generated_at="2026-07-08T00:00:00",
        )

        self.assertEqual([row["post_id"] for row in report["review_rows"]], [17, 20])
        self.assertEqual(report["summary"]["selected_review_rows"], 2)
        self.assertEqual(report["summary"]["excluded_post_id_rows"], 1)
        self.assertEqual(report["summary"]["excluded_p0_candidate_rows"], 1)
        self.assertEqual(
            report["summary"]["counts_by_bucket"],
            {"safe_loss_resolved_to_null": 1, "wrong_work_title_flip": 1},
        )

    def test_include_post_ids_selects_specific_p0_rows(self):
        report = build_review_batch(
            triage_report={
                "rows": [
                    _triage_row(20, "safe_loss_resolved_to_null", "resolved_to_null", "A", None),
                    _triage_row(18, "unsafe_promotion_from_hold", "null_to_resolved", None, "C"),
                    _triage_row(17, "wrong_work_title_flip", "resolved_to_different_title", "D", "E"),
                ]
            },
            panel_rows={post_id: {"post_id": post_id, "title": f"post {post_id}"} for post_id in (17, 18, 20)},
            baseline_rows={},
            after_rows={},
            include_post_ids={18, 20},
            generated_at="2026-07-08T00:00:00",
        )

        self.assertEqual([row["post_id"] for row in report["review_rows"]], [18, 20])
        self.assertEqual(report["summary"]["include_post_ids"], [18, 20])
        self.assertEqual(report["summary"]["selected_review_rows"], 2)

    def test_include_all_priorities_keeps_explicit_non_p0_regression_rows(self):
        p1_row = {**_triage_row(21, "new_resolution_promotion", "null_to_resolved", None, "F"), "priority": "P1"}
        report = build_review_batch(
            triage_report={
                "rows": [
                    _triage_row(20, "safe_loss_resolved_to_null", "resolved_to_null", "A", None),
                    p1_row,
                ]
            },
            panel_rows={post_id: {"post_id": post_id, "title": f"post {post_id}"} for post_id in (20, 21)},
            baseline_rows={},
            after_rows={},
            include_post_ids={20, 21},
            include_all_priorities=True,
            generated_at="2026-07-09T00:00:00",
        )

        self.assertEqual([row["post_id"] for row in report["review_rows"]], [20, 21])
        self.assertEqual(report["summary"]["counts_by_priority"], {"P0": 1, "P1": 1})
        self.assertTrue(report["summary"]["include_all_priorities"])

    def test_scope_label_is_configurable(self):
        report = build_review_batch(
            triage_report={
                "rows": [
                    _triage_row(20, "safe_loss_resolved_to_null", "resolved_to_null", "A", None),
                ]
            },
            panel_rows={20: {"post_id": 20, "title": "post 20"}},
            baseline_rows={},
            after_rows={},
            scope_label="Loop477 full375 P0 collateral",
            generated_at="2026-07-06T00:00:00",
        )

        self.assertEqual(report["report_type"], "collateral_p0_blind_source_review_batch")
        self.assertEqual(report["scope_label"], "Loop477 full375 P0 collateral")

        with TemporaryDirectory() as tmp:
            output = Path(tmp) / "batch.md"
            write_markdown(output, report, inputs={"triage": Path("triage.json")})
            text = output.read_text(encoding="utf-8")

        self.assertIn("# Loop477 full375 P0 collateral blind/source-native 검토 배치", text)
        self.assertIn("Loop477 full375 P0 collateral 정답성 검토 입력", text)
        self.assertNotIn("collateral183", text)


if __name__ == "__main__":
    unittest.main()
