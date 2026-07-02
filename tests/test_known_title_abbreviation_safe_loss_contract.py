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
            ("암흑가보스<<이거 재밋네", "암흑가 보스요? 제가요?", ""),
            ("기계공주 작가 여초딩임?", "헌터갤러리의 국가권력급 기계공주", ""),
            ("약먹마 요즘 좀 애매함", "약먹는 천재마법사", ""),
            ("악살싶에서는 호평받았었는데", "악당은 살고 싶다", ""),
            ("마도줍 시리즈 왔구나", "마도서를 줍다 마법사가 되다", ""),
            ("즉사무림 최신편도 개개맛있군", "즉사기 들고 무림에 떨어지다", ""),
            ("밀리언클래스 공지보고 웃음", "밀리언 클래스", ""),
            (
                "럽코빙의 원래도 그렇게 대놓고 언급 안했는데",
                "이거 럽코 빙의물인가요",
                "전생 현실 언급 방식이랑 연중 직전 화 얘기",
            ),
            (
                "빚세구 근데 주인공이 은발에 아이돌 출신이란 게 좀 신경쓰이네",
                "빚을 져서라도 세상은 구해야 할 거 아니야",
                "이세계도 감",
            ),
            (
                "마줍 그리즐리 설정 얘기",
                "마도서를 줍다 마법사가 되다",
                "참고로 그리즐리는 마줍에 나오는 투명 우주 흡혈귀임. 작품 설정 얘기",
            ),
            (
                "여신애호) 잉잉이의 정체...",
                "여신이 나만 애호함",
                "그것은 클라우드 링이라는 것이닷",
            ),
            (
                "별품소 웹툰 가끔씩 보는데",
                "별을 품은 소드마스터",
                "별품소가 기사뽕을 잘 채워줬고 결말이 아쉽다",
            ),
            (
                "전독시 영화화는 걱정되긴 함",
                "전지적 독자 시점",
                "웹소설 원작 장면을 영화가 어떻게 각색할지 얘기",
            ),
        ]

        for title, expected, body in cases:
            with self.subTest(title=title):
                ctx = self._ctx(title=title, body=body)

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

    def test_search_dependent_or_ambiguous_aliases_do_not_release_from_registry_alone(self):
        cases = [
            (
                11668288,
                "가챠펑크 오늘 호텔 스트레스 많이 받을거야",
                "아침 모르겠다는 것이야 아무것도 모름 경축 대성공",
                "가챠 중독자의 퓨전펑크 생활",
            ),
            (
                11668300,
                "즉사기 말 많아서 보러간다",
                "재미없다면 고로시 달린다",
                "즉사기 들고 게임 속 으로",
            ),
        ]

        for post_id, title, body, candidate in cases:
            with self.subTest(post_id=post_id):
                ctx = self._ctx(post_id=post_id, title=title, body=body)

                allowed = self.pipeline._known_title_abbreviation_update_question_anchor(ctx, candidate)

                self.assertFalse(allowed)


if __name__ == "__main__":
    unittest.main()
