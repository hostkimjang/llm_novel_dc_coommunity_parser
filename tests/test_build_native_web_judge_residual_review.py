import json
import tempfile
import unittest
from pathlib import Path

from tools.build_native_web_judge_residual_review import SOURCE_NATIVE_EXCLUDE, build_review


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class NativeWebJudgeResidualReviewTest(unittest.TestCase):
    def test_maps_codex_native_verdicts_and_missing_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            judge_root = root / "judge"
            _write_json(
                judge_root / "verdicts" / "verdict_001.json",
                {
                    "verdicts": [
                        {
                            "post_id": 1,
                            "resolution_label": "ACCEPT",
                            "disagreement_type": "none",
                            "likely_correct": "pipeline",
                            "search_evidence_grade": "Strong",
                            "recommended_action": "no_action",
                            "independent_official_title": "A",
                            "independent_url": "https://example.com/a",
                            "pipeline_official_title": "A",
                            "pipeline_url": "https://example.com/a",
                            "source_urls": ["https://example.com/a"],
                            "korean_reason": "공식 상세가 일치한다.",
                        },
                        {
                            "post_id": 2,
                            "resolution_label": "REPROCESS",
                            "disagreement_type": "under_resolved",
                            "likely_correct": "codex",
                            "search_evidence_grade": "Strong",
                            "recommended_action": "re_search",
                            "independent_official_title": "B",
                            "independent_url": "https://example.com/b",
                            "pipeline_official_title": None,
                            "pipeline_url": None,
                            "source_urls": ["https://example.com/b"],
                            "korean_reason": "파이프라인이 과소해결했다.",
                        },
                    ]
                },
            )
            dispatch = {
                "dispatch_id": "unit_dispatch",
                "rows": [
                    {"post_id": 1, "triage_bucket": "safe_loss", "evidence_refs": ["dispatch#1"]},
                    {"post_id": 2, "triage_bucket": "safe_loss", "evidence_refs": ["dispatch#2"]},
                    {"post_id": 3, "triage_bucket": "safe_loss", "evidence_refs": ["dispatch#3"]},
                ],
            }
            carry = {
                "review_id": "carry_review",
                "rows": [
                    {
                        "post_id": 10,
                        "triage_bucket": "wrong_work",
                        "review_label": "ACCEPT",
                        "source_native_verdict": "carried",
                        "action": [SOURCE_NATIVE_EXCLUDE],
                        "rationale_ko": "carry",
                    }
                ],
            }

            review = build_review(
                dispatch=dispatch,
                judge_root=judge_root,
                carry_reviews=[carry],
                review_id="unit_review",
            )

        self.assertEqual(review["gate"], "REVIEW-LOCKED")
        self.assertEqual(review["summary"]["dispatch_rows"], 3)
        self.assertEqual(review["summary"]["carried_rows"], 1)
        self.assertEqual(review["summary"]["codex_native_web_found_rows"], 2)
        self.assertEqual(review["summary"]["codex_native_web_missing_rows"], 1)
        self.assertEqual(review["summary"]["label_counts"]["ACCEPT"], 2)
        self.assertEqual(review["summary"]["label_counts"]["REPROCESS"], 1)
        self.assertEqual(review["summary"]["label_counts"]["INFO_MISSING"], 1)
        self.assertEqual(review["summary"]["action_counts"][SOURCE_NATIVE_EXCLUDE], 2)
        by_post = {row["post_id"]: row for row in review["rows"]}
        self.assertIn("shared_promotion_gate_wiring_required", by_post[2]["action"])
        self.assertEqual(by_post[3]["review_label"], "INFO_MISSING")


if __name__ == "__main__":
    unittest.main()
