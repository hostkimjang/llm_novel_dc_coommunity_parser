import json
import tempfile
import unittest
from pathlib import Path

from tools import build_search_only_intent_followup_inputs as followup


class SearchOnlyIntentFollowupInputsTest(unittest.TestCase):
    def test_builds_rerun_input_with_comments_and_image_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            labels_path = root / "labels.jsonl"
            source_path = root / "source.jsonl"
            out_dir = root / "out"

            labels_path.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "review_id": "r1",
                                "post_id": "1",
                                "buckets": ["search_only_resolved_title"],
                                "label": "HOLD",
                                "action": "human_review",
                                "evidence_grade": "Weak",
                                "title": "추천 좀",
                                "resolved_title": "오답",
                                "rationale_ko": "댓글 URL이 있어 확인 필요",
                            },
                            ensure_ascii=False,
                        ),
                        json.dumps(
                            {
                                "review_id": "r2",
                                "post_id": "2",
                                "buckets": ["blocked_intent_resolved_title"],
                                "label": "REJECT",
                                "action": "human_review",
                                "evidence_grade": "Missing",
                                "title": "기억질문",
                                "resolved_title": "네이버",
                                "rationale_ko": "플랫폼 drift",
                            },
                            ensure_ascii=False,
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            source_path.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "post_id": 1,
                                "gallery_id": "genrenovel",
                                "title": "추천 좀",
                                "author": "ㅇㅇ",
                                "url": "https://example.test/1",
                                "content_blocks": [
                                    {"type": "image", "url": "https://dcimg.example/a.jpg"}
                                ],
                            },
                            ensure_ascii=False,
                        ),
                        json.dumps(
                            {
                                "comment_id": "c1",
                                "post_id": 1,
                                "author": "ㅇㅇ",
                                "content": "https://novelpia.com/novel/1",
                            },
                            ensure_ascii=False,
                        ),
                        json.dumps(
                            {
                                "post_id": 2,
                                "gallery_id": "genrenovel",
                                "title": "기억질문",
                                "author": "ㅇㅇ",
                                "url": "https://example.test/2",
                                "content_blocks": [{"type": "text", "text": "무슨 소설이었지"}],
                            },
                            ensure_ascii=False,
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            manifest = followup.build_followup_package(
                labels_path=labels_path,
                source_path=source_path,
                out_dir=out_dir,
                prefix="case",
            )

            self.assertEqual(manifest["target_count"], 2)
            self.assertEqual(manifest["source_post_rows_found"], 2)
            self.assertEqual(manifest["source_comment_rows_found"], 1)
            self.assertEqual(manifest["missing_post_ids"], [])
            self.assertEqual(manifest["browser_target_rows"], 1)
            self.assertEqual(manifest["parallel_policy"]["expected_effective_parallel"], 2)
            self.assertEqual(manifest["recommended_action_counts"]["re_search"], 1)
            self.assertEqual(manifest["recommended_action_counts"]["comment_url_verify"], 1)
            self.assertEqual(manifest["recommended_action_counts"]["re_judge"], 1)

            rerun_rows = followup.load_jsonl(out_dir / "case_rerun_combined_input.jsonl")
            self.assertEqual(len(rerun_rows), 2)
            first = rerun_rows[0]
            self.assertEqual(first["comments"][0]["comment_id"], "c1")
            self.assertEqual(first["image_count"], 1)
            self.assertIn("comment_url_verify", first["_round3_target"]["recommended_actions"])
            second = rerun_rows[1]
            self.assertIn("re_judge", second["_round3_target"]["recommended_actions"])


if __name__ == "__main__":
    unittest.main()
