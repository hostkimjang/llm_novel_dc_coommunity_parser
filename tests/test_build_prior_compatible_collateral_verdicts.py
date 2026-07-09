from pathlib import Path
import tempfile
import unittest

from tools.build_prior_compatible_collateral_verdicts import (
    build_prior_compatible_verdicts,
    build_unreviewed_batch,
    build_unreviewed_placeholder_verdicts,
    _source_glob_specs,
)


class BuildPriorCompatibleCollateralVerdictsTest(unittest.TestCase):
    def test_source_verdicts_glob_expands_with_bucket(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "b_source_native_verdicts.json").write_text("{}", encoding="utf-8")
            (root / "a_source_native_verdicts.json").write_text("{}", encoding="utf-8")

            specs = _source_glob_specs(str(root / "*_source_native_verdicts.json") + "::*")

        self.assertEqual([bucket for _, bucket in specs], ["*", "*"])
        self.assertEqual([path.name for path, _ in specs], ["a_source_native_verdicts.json", "b_source_native_verdicts.json"])

    def test_remaps_option_id_by_current_title_match(self):
        batch = {
            "review_rows": [
                {
                    "post_id": 1,
                    "triage_bucket": "wrong_work_title_flip",
                    "blind_judge_options": [
                        {"option_id": "C1", "official_title": "new wrong", "heretic_url": "https://example.test/wrong"},
                        {"option_id": "C2", "official_title": "old right", "heretic_url": "https://example.test/right"},
                    ],
                }
            ]
        }
        verdicts = {
            "rows": [
                {
                    "post_id": 1,
                    "selected_option_id": "C1",
                    "selected_title": "old right",
                    "selected_url": "https://example.test/right",
                    "review_label": "ACCEPT",
                    "source_native_verdict": "after_supported",
                    "evidence_refs": ["unit://old"],
                }
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            verdict_path = Path(tmp) / "old.json"
            verdict_path.write_text(__import__("json").dumps(verdicts), encoding="utf-8")

            payload, state = build_prior_compatible_verdicts(
                batch=batch,
                batch_path=Path("batch.json"),
                source_specs=[(verdict_path, "wrong_work_title_flip")],
                review_id="unit",
                scope="unit",
            )

        self.assertEqual(state["summary"]["compatible_rows"], 1)
        self.assertEqual(payload["rows"][0]["selected_option_id"], "C2")
        self.assertEqual(payload["rows"][0]["carry_forward_match_reason"], "title_or_url_match")

    def test_skips_changed_bucket(self):
        batch = {
            "review_rows": [
                {
                    "post_id": 1,
                    "triage_bucket": "safe_loss_resolved_to_null",
                    "blind_judge_options": [
                        {"option_id": "C1", "official_title": "title", "heretic_url": "https://example.test/work"}
                    ],
                }
            ]
        }
        verdicts = {
            "rows": [
                {
                    "post_id": 1,
                    "selected_option_id": "C1",
                    "selected_title": "title",
                    "selected_url": "https://example.test/work",
                    "review_label": "ACCEPT",
                    "source_native_verdict": "after_supported",
                    "evidence_refs": ["unit://old"],
                }
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            verdict_path = Path(tmp) / "old.json"
            verdict_path.write_text(__import__("json").dumps(verdicts), encoding="utf-8")

            payload, state = build_prior_compatible_verdicts(
                batch=batch,
                batch_path=Path("batch.json"),
                source_specs=[(verdict_path, "wrong_work_title_flip")],
                review_id="unit",
                scope="unit",
            )

        self.assertEqual(payload["rows"], [])
        self.assertEqual(state["summary"]["skip_counts"], {"triage_bucket_changed": 1})

    def test_auto_bucket_mode_uses_source_row_bucket(self):
        batch = {
            "review_rows": [
                {
                    "post_id": 1,
                    "triage_bucket": "safe_loss_resolved_to_null",
                    "blind_judge_options": [
                        {"option_id": "C1", "official_title": "title", "heretic_url": "https://example.test/work"}
                    ],
                },
                {
                    "post_id": 2,
                    "triage_bucket": "unsafe_promotion_from_hold",
                    "blind_judge_options": [
                        {"option_id": "C1", "official_title": "other", "heretic_url": "https://example.test/other"}
                    ],
                },
            ]
        }
        verdicts = {
            "rows": [
                {
                    "post_id": 1,
                    "triage_bucket": "safe_loss_resolved_to_null",
                    "selected_option_id": "C9",
                    "selected_title": "title",
                    "selected_url": "https://example.test/work",
                    "review_label": "REPROCESS",
                    "source_native_verdict": "before_supported",
                    "evidence_refs": ["unit://old-1"],
                },
                {
                    "post_id": 2,
                    "triage_bucket": "wrong_work_title_flip",
                    "selected_option_id": "C1",
                    "selected_title": "other",
                    "selected_url": "https://example.test/other",
                    "review_label": "ACCEPT",
                    "source_native_verdict": "after_supported",
                    "evidence_refs": ["unit://old-2"],
                },
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            verdict_path = Path(tmp) / "mixed.json"
            verdict_path.write_text(__import__("json").dumps(verdicts), encoding="utf-8")

            payload, state = build_prior_compatible_verdicts(
                batch=batch,
                batch_path=Path("batch.json"),
                source_specs=[(verdict_path, "*")],
                review_id="unit",
                scope="unit",
            )

        self.assertEqual(state["summary"]["compatible_rows"], 1)
        self.assertEqual(payload["rows"][0]["post_id"], 1)
        self.assertEqual(payload["rows"][0]["selected_option_id"], "C1")
        self.assertEqual(state["summary"]["skip_counts"], {"triage_bucket_changed": 1})

    def test_builds_unreviewed_batch_from_not_covered_rows(self):
        batch = {
            "review_rows": [
                {
                    "post_id": 1,
                    "triage_bucket": "wrong_work_title_flip",
                    "collateral_status": "resolved_to_different_title",
                    "source_native_packet": {"image_count": 0},
                },
                {
                    "post_id": 2,
                    "triage_bucket": "safe_loss_resolved_to_null",
                    "collateral_status": "resolved_to_null",
                    "source_native_packet": {"image_count": 1},
                },
            ]
        }
        compatible_verdicts = {"rows": [{"post_id": 1}]}
        state = {"review_id": "unit", "summary": {"compatible_rows": 1}}

        unreviewed = build_unreviewed_batch(batch, compatible_verdicts, state)

        self.assertEqual(unreviewed["summary"]["source_review_rows"], 2)
        self.assertEqual(unreviewed["summary"]["prior_compatible_rows"], 1)
        self.assertEqual(unreviewed["summary"]["unreviewed_rows"], 1)
        self.assertEqual(unreviewed["summary"]["image_rows"], 1)
        self.assertEqual(unreviewed["summary"]["counts_by_bucket"], {"safe_loss_resolved_to_null": 1})
        self.assertEqual(unreviewed["review_rows"][0]["post_id"], 2)

    def test_unreviewed_batch_honors_additional_covered_verdicts(self):
        batch = {
            "review_rows": [
                {"post_id": 1, "triage_bucket": "wrong_work_title_flip", "source_native_packet": {"image_count": 0}},
                {"post_id": 2, "triage_bucket": "safe_loss_resolved_to_null", "source_native_packet": {"image_count": 0}},
                {"post_id": 3, "triage_bucket": "unsafe_promotion_from_hold", "source_native_packet": {"image_count": 0}},
            ]
        }
        compatible_verdicts = {"rows": [{"post_id": 1}]}
        state = {"review_id": "unit", "summary": {"compatible_rows": 1}}

        unreviewed = build_unreviewed_batch(
            batch,
            compatible_verdicts,
            state,
            additional_covered_verdicts=[{"rows": [{"post_id": 2}]}],
        )

        self.assertEqual(unreviewed["summary"]["prior_compatible_rows"], 1)
        self.assertEqual(unreviewed["summary"]["additional_covered_rows"], 1)
        self.assertEqual(unreviewed["summary"]["covered_post_ids"], 2)
        self.assertEqual(unreviewed["summary"]["unreviewed_rows"], 1)
        self.assertEqual(unreviewed["review_rows"][0]["post_id"], 3)

    def test_builds_info_missing_placeholder_verdicts_for_uncovered_rows(self):
        batch = {
            "review_rows": [
                {
                    "post_id": 1,
                    "triage_bucket": "wrong_work_title_flip",
                    "collateral_status": "resolved_to_different_title",
                },
                {
                    "post_id": 2,
                    "triage_bucket": "safe_loss_resolved_to_null",
                    "collateral_status": "resolved_to_null",
                },
            ]
        }
        compatible_verdicts = {"rows": [{"post_id": 1}]}
        state = {"review_id": "unit_prior", "summary": {"compatible_rows": 1}}

        placeholders = build_unreviewed_placeholder_verdicts(
            batch,
            compatible_verdicts,
            state,
            review_id="unit_unreviewed",
            scope="unit unreviewed",
            batch_path=Path("batch.json"),
        )

        self.assertEqual(placeholders["summary"]["placeholder_rows"], 1)
        self.assertEqual(placeholders["rows"][0]["post_id"], 2)
        self.assertEqual(placeholders["rows"][0]["selected_option_id"], "HOLD")
        self.assertEqual(placeholders["rows"][0]["review_label"], "INFO_MISSING")
        self.assertIn("p0_safe_loss_resolved_to_null_review_required", placeholders["rows"][0]["action"])

    def test_placeholder_generation_honors_additional_covered_verdicts(self):
        batch = {
            "review_rows": [
                {"post_id": 1, "triage_bucket": "wrong_work_title_flip"},
                {"post_id": 2, "triage_bucket": "safe_loss_resolved_to_null"},
                {"post_id": 3, "triage_bucket": "unsafe_promotion_from_hold"},
            ]
        }
        compatible_verdicts = {"rows": [{"post_id": 1}]}
        state = {"review_id": "unit_prior"}

        placeholders = build_unreviewed_placeholder_verdicts(
            batch,
            compatible_verdicts,
            state,
            review_id="unit_unreviewed",
            scope="unit unreviewed",
            batch_path=Path("batch.json"),
            additional_covered_verdicts=[{"rows": [{"post_id": 2}]}],
        )

        self.assertEqual(placeholders["summary"]["prior_compatible_rows"], 1)
        self.assertEqual(placeholders["summary"]["additional_covered_rows"], 1)
        self.assertEqual(placeholders["summary"]["covered_post_ids"], 2)
        self.assertEqual(placeholders["summary"]["placeholder_rows"], 1)
        self.assertEqual(placeholders["rows"][0]["post_id"], 3)


if __name__ == "__main__":
    unittest.main()
