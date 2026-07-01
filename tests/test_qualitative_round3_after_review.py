import json
import tempfile
import unittest
from pathlib import Path

from tools import build_qualitative_round3_after_review as after_review


class QualitativeRound3AfterReviewTest(unittest.TestCase):
    def test_positive_alias_candidate_overblock_is_not_auto_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result_path = root / "result.json"
            target_path = root / "target.jsonl"

            result_path.write_text(
                json.dumps(
                    [
                        {
                            "post_id": 11718098,
                            "title": "마좋좋좋 결말이 왜이러냐..",
                            "content": ["ts난교 뭐다이.."],
                            "comments": ["그것이 [사랑]"],
                            "analysis_result": {
                                "identity": {
                                    "is_relevant": False,
                                    "is_novel_related": True,
                                    "discussion_type": "noise",
                                    "work_resolution": "none",
                                    "title_resolution_state": "context_only",
                                    "title_resolution_allowed": False,
                                    "reason": "판정: 비관련; 공식 제목: 미확정; 검색 결과는 커뮤니티 위주다.",
                                }
                            },
                        }
                    ],
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            target_path.write_text(
                json.dumps(
                    {
                        "post_id": 11718098,
                        "title": "마좋좋좋 결말이 왜이러냐..",
                        "_round3_target": {
                            "label": "HOLD",
                            "action": "re_judge",
                            "primary_pattern": "blocked_intent_resolved_title",
                            "resolved_title": "스포)마법 좋아좋아좋아",
                            "evidence_grade": "Medium",
                            "rationale_ko": (
                                "마좋좋좋 alias와 official detail URL은 같은 작품을 지지할 수 있다. "
                                "canonical title 정정 전까지 HOLD다."
                            ),
                        },
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            _packets, labels, manifest = after_review.build_after_review(result_path, target_path)

        self.assertEqual(labels[0]["label"], "REJECT")
        self.assertEqual(labels[0]["action"], "re_judge")
        self.assertEqual(labels[0]["followup_guard"], "positive_alias_candidate_overblocked")
        self.assertIn("positive_alias_overblock_after_followup", labels[0]["boundary_risk"])
        self.assertEqual(manifest["label_counts"], {"REJECT": 1})
        self.assertEqual(manifest["followup_guard_counts"], {"positive_alias_candidate_overblocked": 1})

    def test_human_followup_target_is_not_auto_accepted_without_closure_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result_path = root / "result.json"
            target_path = root / "target.jsonl"

            result_path.write_text(
                json.dumps(
                    [
                        {
                            "post_id": 11718049,
                            "title": "후타 암타물을 보고싶구나..",
                            "content": ["추천 좀"],
                            "comments": ["https://novelpia.com/novel/50764"],
                            "analysis_result": {
                                "identity": {
                                    "is_relevant": False,
                                    "is_novel_related": True,
                                    "discussion_type": "noise",
                                    "work_resolution": "none",
                                    "title_resolution_state": "context_only",
                                    "title_resolution_allowed": False,
                                    "reason": "판정: 비관련; 공식 제목: 미확정; 댓글 URL은 별도 확인 필요.",
                                }
                            },
                        }
                    ],
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            target_path.write_text(
                json.dumps(
                    {
                        "post_id": 11718049,
                        "title": "후타 암타물을 보고싶구나..",
                        "_round3_target": {
                            "label": "HOLD",
                            "action": "human_review",
                            "primary_pattern": "search_only_resolved_title",
                            "resolved_title": "깨어나 보니 여자가 되어 있었다. 그런데 달려 있는.",
                            "evidence_grade": "Weak",
                            "rationale_ko": (
                                "댓글에 Novelpia URL이 있어 작품 추천/답변일 가능성은 있으나, "
                                "comment metadata와 browser/direct evidence가 부족하다."
                            ),
                        },
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            _packets, labels, manifest = after_review.build_after_review(result_path, target_path)

        self.assertEqual(labels[0]["label"], "HOLD")
        self.assertEqual(labels[0]["action"], "comment_url_verify")
        self.assertEqual(labels[0]["followup_guard"], "human_followup_not_closed")
        self.assertIn("human_followup_not_closed_after_rerun", labels[0]["boundary_risk"])
        self.assertEqual(manifest["label_counts"], {"HOLD": 1})


if __name__ == "__main__":
    unittest.main()
