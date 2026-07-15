from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from llm_batch.agentic_pipeline import AgenticPipeline  # noqa: E402
from llm_batch.experts.orchestrator import ConversationContext  # noqa: E402


class DummyLLM:
    pass


class DummyMCP:
    pass


class DummyContext(SimpleNamespace):
    def get_expert_output(self, *_args, **_kwargs):
        return {}


class AgenticPipelineSearchEvidenceTest(unittest.TestCase):
    def test_build_search_evidence_catalog_keeps_eid_query_url_and_snippet(self) -> None:
        pipeline = AgenticPipeline(llm=DummyLLM(), mcp=DummyMCP(), max_iterations=1)
        ctx = SimpleNamespace(
            search_results=[
                {
                    "_evidence_id": "E0001",
                    "_query": "성녀 속마음 노벨피아",
                    "_purpose": "official_title_verify",
                    "title": "성녀의 속마음이 들린다",
                    "url": "https://novelpia.com/novel/314965",
                    "content": "성녀의 속마음이 들린다 작품 상세 페이지",
                    "engine": "test",
                    "degraded": False,
                },
                {
                    "_evidence_id": "E0002",
                    "_query": "성녀 속마음 노벨피아",
                    "_purpose": "official_title_verify",
                    "title": "성녀의 속마음이 들린다",
                    "url": "https://novelpia.com/novel/314965",
                    "content": "성녀의 속마음이 들린다 작품 상세 페이지",
                },
                {
                    "title": "강철의 연금술사",
                    "url": "https://namu.wiki/w/강철의%20연금술사",
                    "snippet": "만화/애니메이션 작품 설명",
                    "query": "강연금",
                },
                {
                    "title": "강철의 연금술사 완전판 [단행본] - 웹툰 - 카카오페이지",
                    "url": "https://page.kakao.com/content/50565497",
                    "snippet": "연금술로 엄마를 되살리려던 형제의 모험. cHiromu Arakawa/SQUARE ENIX CO., LTD.",
                    "query": "강연금",
                },
            ]
        )

        catalog = pipeline._build_search_evidence_catalog(ctx)

        self.assertEqual(len(catalog), 3)
        self.assertEqual(catalog[0]["eid"], "E0001")
        self.assertEqual(catalog[0]["query"], "성녀 속마음 노벨피아")
        self.assertEqual(catalog[0]["purpose"], "official_title_verify")
        self.assertEqual(catalog[0]["source_tier"], "novel_platform")
        self.assertEqual(catalog[0]["domain"], "novelpia.com")
        self.assertIn("작품 상세 페이지", catalog[0]["snippet"])
        self.assertEqual(catalog[1]["source_tier"], "wiki")
        self.assertEqual(catalog[2]["source_tier"], "non_novel_media_platform")

    def test_search_evidence_catalog_keeps_novelpia_detail_despite_wallet_ui_webtoon_marker(self) -> None:
        pipeline = AgenticPipeline(llm=DummyLLM(), mcp=DummyMCP(), max_iterations=1)
        ctx = SimpleNamespace(
            search_results=[
                {
                    "_evidence_id": "E0001",
                    "_query": "성녀의 속마음이 들린다 노벨피아",
                    "_purpose": "official_title_verify",
                    "title": "성녀의 속마음이 들린다",
                    "url": "https://novelpia.com/novel/314965",
                    "content": "페이지로딩 닫기 보유재화 코인 웹툰코인 북캐시 멤버십코인",
                }
            ]
        )

        catalog = pipeline._build_search_evidence_catalog(ctx)

        self.assertEqual(len(catalog), 1)
        self.assertEqual(catalog[0]["source_tier"], "novel_platform")

    def test_direct_recall_search_outcome_populates_public_search_health(self) -> None:
        pipeline = AgenticPipeline(llm=DummyLLM(), mcp=DummyMCP(), max_iterations=1)
        ctx = ConversationContext(post_id=11700483, post_data={}, comments=[])
        results = [
            {
                "title": "니들 생각 다 들린다 - 나무위키",
                "url": "https://namu.wiki/w/니들%20생각%20다%20들린다",
                "content": "니생들 표지와 노벨피아 연재처 정보",
            }
        ]

        pipeline._record_context_search_outcome_from_meta(
            ctx,
            "니생들 노벨피아",
            "title_alias_platform_recall",
            results,
            {"raw_total": 1, "degraded": False, "attempts": 1},
        )

        health = pipeline._build_search_health_public_fields(ctx)
        self.assertIsNotNone(health)
        self.assertEqual(health["queries_issued"], 1)
        self.assertEqual(health["accepted"], 1)
        self.assertEqual(health["status"], "ok")
        self.assertEqual(ctx.executed_queries, ["니생들 노벨피아"])

    def test_validate_heretic_url_fast_exact_official_stops_after_exact_url(self) -> None:
        pipeline = AgenticPipeline(llm=DummyLLM(), mcp=DummyMCP(), max_iterations=1)
        title = "괴담에 떨어져도 출근을 해야 하는구나"
        official_url = "https://page.kakao.com/content/65171279"
        stale_url = "https://novelpia.com/novel/374287"
        ctx = DummyContext(
            search_results=[
                {
                    "title": "괴담에 떨어져도 출근을 해야 하는구나 - 카카오페이지",
                    "url": official_url,
                    "content": "괴담에 떨어져도 출근을 해야 하는구나 웹소설 작품 상세 페이지",
                    "rank": 1,
                },
                {
                    "title": "[괴담출근 패러디] 괴담에 떨어져도 노 페인 노 게인",
                    "url": stale_url,
                    "content": "패러디 작품 상세 페이지",
                    "rank": 2,
                },
                {
                    "title": "SCP 재단 Bangja 시리즈",
                    "url": "https://novelpia.com/novel/37455",
                    "content": "SCP 재단 패러디 상세 페이지",
                    "rank": 3,
                },
            ]
        )
        fetched_urls: list[str] = []

        def fake_fetch(ctx_arg, fetch_url):
            fetched_urls.append(fetch_url)
            return {
                "url": fetch_url,
                "structured_info": {
                    "title": title if fetch_url == official_url else "다른 작품",
                    "page_title": title if fetch_url == official_url else "다른 작품",
                    "content_status": "active",
                },
                "text_preview": title if fetch_url == official_url else "다른 작품",
            }

        pipeline._fetch_and_attach_page_info = fake_fetch

        self.assertEqual(
            pipeline._validate_heretic_url(stale_url, ctx, identified_title=title),
            official_url,
        )
        self.assertEqual(fetched_urls, [official_url])

    def test_validate_heretic_url_candidate_cap_limits_live_fetches(self) -> None:
        pipeline = AgenticPipeline(llm=DummyLLM(), mcp=DummyMCP(), max_iterations=1)
        pipeline.heretic_url_fast_exact_official = False
        pipeline.heretic_url_eval_max = 2
        expert_urls = [
            f"https://novelpia.com/novel/{300000 + idx}"
            for idx in range(5)
        ]
        input_url = "https://novelpia.com/novel/299999"
        # 현재 구현은 선택 작품과 연결되는 검색 근거가 있어야만 실제 페이지를 fetch한다.
        # 이 테스트는 prefetch 게이트가 아니라 URL 평가 cap을 검증하므로 후보별 제목 근거를 제공한다.
        selected_title = "괴담에 떨어져도 출근을 해야 하는구나"
        ctx = DummyContext(
            search_results=[
                {
                    "url": candidate_url,
                    "title": selected_title,
                    "content": f"{selected_title} 작품 상세",
                }
                for candidate_url in [input_url, *expert_urls]
            ]
        )

        # 실제 구현이 제목 범위를 전달해도 URL cap 계약만 검증하도록 받는다.
        def fake_collect(_ctx, **_kwargs):
            return expert_urls

        fetched_urls: list[str] = []

        def fake_fetch(ctx_arg, fetch_url):
            fetched_urls.append(fetch_url)
            return {
                "url": fetch_url,
                "structured_info": {
                    "title": "다른 작품",
                    "page_title": "다른 작품",
                    # 평가 cap 뒤에도 최종 URL은 채택되지 않도록 명시적인 삭제 상태를 사용한다.
                    "content_status": "deleted",
                },
                "text_preview": "다른 작품",
            }

        pipeline._collect_expert_urls = fake_collect
        pipeline._fetch_and_attach_page_info = fake_fetch

        self.assertIsNone(
            pipeline._validate_heretic_url(
                input_url,
                ctx,
                identified_title=selected_title,
            )
        )
        self.assertEqual(len(fetched_urls), 2)


if __name__ == "__main__":
    unittest.main()
