import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from llm_batch.agentic_pipeline import AgenticPipeline  # noqa: E402
from llm_batch.experts.orchestrator import ConversationContext, ExpertType  # noqa: E402


class DummyLLM:
    pass


class DummyMCP:
    pass


class KnownTitleAbbreviationSafeLossContractTest(unittest.TestCase):
    def setUp(self):
        self.pipeline = AgenticPipeline(llm=DummyLLM(), mcp=DummyMCP(), max_iterations=1)

    def _ctx(self, *, post_id=1, title, body="", comments=(), intent="express_opinion"):
        content_blocks = []
        if body:
            content_blocks.append({"type": "text", "text": body})
        ctx = ConversationContext(
            post_id=post_id,
            post_data={"post_id": post_id, "title": title, "content_blocks": content_blocks},
            comments=list(comments),
        )
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": intent,
                    "target_kind": "work",
                    "primary_domain": "novel_literature",
                }
            },
        )
        return ctx

    def test_loop301_direct_alias_review_surfaces_release_known_title_abbreviation(self):
        cases = [
            ("암흑가보스<<이거 재밋네", "암흑가 보스요? 제가요?"),
            ("기계공주 작가 여초딩임?", "헌터갤러리의 국가권력급 기계공주"),
            ("약먹마 요즘 좀 애매함", "약먹는 천재마법사"),
            ("악살싶에서는 호평받았었는데", "악당도 살고 싶다"),
            ("마도줍 시리즈 왔구나", "마도서를 줍다 마법사가 되다"),
            ("즉사무림 최신편도 개개맛있군", "즉사기 들고 무림에 떨어지다"),
            ("밀리언클래스 공지보고 웃음", "밀리언 클래스"),
        ]

        for title, expected in cases:
            with self.subTest(title=title):
                ctx = self._ctx(title=title)

                allowed = self.pipeline._known_title_abbreviation_update_question_anchor(ctx, expected)

                self.assertTrue(allowed)
                self.assertEqual(ctx._known_title_abbreviation_official_detail_anchor_title, expected)

    def test_comparison_only_adjacent_alias_does_not_release_known_title_abbreviation(self):
        ctx = self._ctx(
            post_id=11660232,
            title="괴담텔 이번 전개는 괴담동이 살짝 생각나네",
            body="현재 전개 비교 얘기",
        )

        allowed = self.pipeline._known_title_abbreviation_update_question_anchor(ctx, "괴담 동아리")

        self.assertFalse(allowed)


if __name__ == "__main__":
    unittest.main()
