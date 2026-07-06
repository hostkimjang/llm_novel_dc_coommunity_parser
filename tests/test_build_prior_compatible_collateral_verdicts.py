from pathlib import Path
import tempfile
import unittest

from tools.build_prior_compatible_collateral_verdicts import build_prior_compatible_verdicts, build_unreviewed_batch


class BuildPriorCompatibleCollateralVerdictsTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
