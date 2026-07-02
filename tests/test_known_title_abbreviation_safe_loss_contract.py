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
            (
                "괴담출근정도는 돼야 독창성 운운할수 있는거다",
                "괴담에 떨어져도 출근을 해야 하는구나",
                "모든 괴담물 = 괴담출근의 표절작",
            ),
            (
                "절꺾않 웹툰 존나 잘뽑히긴했노 ㅋㅋㅋㅋㅋ",
                "절대 꺾이지 않을거야!",
                "스토리 치트키에 그림 치트키 합해져서 재밌는 웹툰화 얘기",
            ),
            (
                "무마 웹툰 보는데",
                "무한의 마법사",
                "시로네 장면과 웹툰 각색 얘기",
            ),
            (
                "아카엄창 엄마랑 섹스함?",
                "아카데미 패드립 면역",
                "하면 보러감",
            ),
            (
                "성좌안무서움 이거 도시락 사장은 정체 뭐임?",
                "나만 성좌들이 안 무서움",
                "외신한테 도시락 팔고 그러는 설정 얘기",
            ),
            (
                "빌환 표지변경됨",
                "빌어먹을 환생",
                "시엘 세냐 아니스티나 매르 표지 구성 얘기",
            ),
            (
                "지구온라인 재밌다며 장붕아",
                "지구온라인에서 쌀먹합니다",
                "주인공 보고 외모찬양 주접독백 쓰는 장면 얘기",
            ),
        ]

        for title, expected, body in cases:
            with self.subTest(title=title):
                ctx = self._ctx(title=title, body=body)

                allowed = self.pipeline._known_title_abbreviation_update_question_anchor(ctx, expected)

                self.assertTrue(allowed)
                self.assertEqual(ctx._known_title_abbreviation_official_detail_anchor_title, expected)

    def test_loop321_negated_recommendation_does_not_release_even_with_registered_alias(self):
        ctx = self._ctx(
            post_id=11714892,
            title="재밌는 소설 없나",
            body="기계공주는 ㄴㄴ ts는 안 봄",
            intent="recommendation_request",
        )

        allowed = self.pipeline._known_title_abbreviation_update_question_anchor(
            ctx,
            "헌터갤러리의 국가권력급 기계공주",
        )

        self.assertFalse(allowed)

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

    def test_known_alias_work_bridge_routes_through_shared_predicate_under_webtoon_discourse(self):
        ctx = self._ctx(
            post_id=11708470,
            title="절꺾않 웹툰 존나 잘뽑히긴했노 ㅋㅋㅋㅋㅋ",
            body="스토리 치트키에 그림 치트키 합해져서 재밌는 웹툰화 얘기",
            comments=["소설은 어떰", "소설 개재밌음 ㅇㅇ 취향맞으면"],
        )
        ctx.discourse_warning = "non_novel(manga_comics,high)"
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "intent": "discuss_work",
                    "target_kind": "work",
                    "primary_domain": "manga_comics",
                    "secondary_domains": ["novel_literature"],
                }
            },
        )

        self.assertTrue(
            self.pipeline._known_title_abbreviation_post_work_bridge(
                ctx,
                "절대 꺾이지 않을거야!",
                "절꺾않",
            )
        )
        self.assertTrue(
            self.pipeline._post_discusses_work_as_work(
                ctx,
                "절대 꺾이지 않을거야!",
                source="official_url_recall_gate",
            )
        )
        self.assertTrue(
            self.pipeline._has_specific_work_non_novel_media_exemption(
                ctx,
                "절대 꺾이지 않을거야!",
                {},
            )
        )

    def test_known_alias_semantic_no_work_gate_can_publish_with_official_detail(self):
        title = "지구온라인에서 쌀먹합니다"
        url = "https://novelpia.com/novel/395678"
        ctx = self._ctx(
            post_id=11718110,
            title="지구온라인 재밌다며 장붕아",
            body="주인공 보고 외모찬양 주접독백 쓰는 장면 얘기",
            comments=["그걸 믿음?"],
        )
        ctx.search_results = [
            {
                "title": title,
                "url": url,
                "content": "노벨피아 웹소설 작품 상세",
            }
        ]
        final_decision = {
            "title_resolution_allowed": False,
            "title_resolution_state": "unresolved_matchable",
            "work_resolution": "unresolved",
            "discussion_type": "general",
        }

        old_official = self.pipeline._has_official_title_evidence
        old_detail_urls = self.pipeline._official_detail_exact_title_urls_for_no_work_anchor
        old_find_url = self.pipeline._find_title_matched_official_url
        self.pipeline._has_official_title_evidence = lambda *_args, **_kwargs: True
        self.pipeline._official_detail_exact_title_urls_for_no_work_anchor = lambda *_args, **_kwargs: [url]
        self.pipeline._find_title_matched_official_url = lambda *_args, **_kwargs: url
        try:
            allowed = self.pipeline._can_promote_title_after_semantic_no_work(
                ctx,
                title,
                source="title_surface_primary_candidate_rescued",
                final_decision=final_decision,
                verification_result={},
                title_candidates=[],
            )
        finally:
            self.pipeline._has_official_title_evidence = old_official
            self.pipeline._official_detail_exact_title_urls_for_no_work_anchor = old_detail_urls
            self.pipeline._find_title_matched_official_url = old_find_url

        self.assertTrue(allowed)
        decision = final_decision["_promotion_gate_decision"]
        self.assertEqual(decision["status"], "publish")
        self.assertTrue(decision["publish_allowed"])
        self.assertIn("row_discusses_work_as_work", decision["reason_codes"])
        self.assertEqual(final_decision["_promotion_gate_state"]["scope"]["scope_kind"], "current_work")

    def test_known_alias_release_meta_does_not_force_platform_meta_block(self):
        ctx = self._ctx(
            post_id=11718099,
            title="빌환 표지변경됨",
            body="시엘 세냐 아니스티나 매르 표지 구성 얘기",
        )

        blocked, reason = self.pipeline._should_block_title_promotion_for_meta_primary_subject(
            ctx=ctx,
            vf_result={},
            final_decision={},
        )

        self.assertFalse(blocked)
        self.assertEqual(reason, "")


if __name__ == "__main__":
    unittest.main()
