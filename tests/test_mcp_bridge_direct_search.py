import unittest
from unittest.mock import patch

from llm_batch.mcp_bridge import server


class McpBridgeDirectSearchTest(unittest.TestCase):
    def test_direct_search_parser_keeps_platform_result(self):
        html = """
        <html><body>
          <a href="https://search.naver.com/search.naver?query=x">ignore search</a>
          <a href="https://novel.munpia.com/530500">판초우의의 마법사 - 문피아</a>
          <a href="https://series.naver.com/novel/detail.series?productNo=14207846">판초우의의 마법사</a>
        </body></html>
        """

        items = server._normalize_direct_search_items(
            html=html,
            provider="naver",
            base_url="https://search.naver.com/search.naver?query=x",
            query="판초우의의 마법사",
            purpose="official_title_verify",
            limit=5,
        )

        self.assertEqual([item["url"] for item in items], [
            "https://novel.munpia.com/530500",
            "https://series.naver.com/novel/detail.series?productNo=14207846",
        ])
        self.assertTrue(all(item["engine"] == "direct_naver" for item in items))

    def test_bing_redirect_url_is_decoded(self):
        encoded = "a1aHR0cHM6Ly9ub3ZlbC5tdW5waWEuY29tLzUzMDUwMA"
        url = f"https://www.bing.com/ck/a?!&&u={encoded}&ntb=1"

        self.assertEqual(
            server._clean_direct_search_url(url),
            "https://novel.munpia.com/530500",
        )

    def test_breadcrumb_title_is_recovered_from_namu_url(self):
        html = """
        <html><body>
          <a href="https://namu.wiki/w/%ED%83%90%EC%8B%9D%EC%9D%98%20%EC%9E%AC%EB%A6%BC">나무위키 namu.wiki ›</a>
          <a href="https://www.naver.com">NAVER</a>
          <a href="https://ader.naver.com/v1/ad-click">탐식의재림 광고</a>
        </body></html>
        """

        items = server._normalize_direct_search_items(
            html=html,
            provider="naver",
            base_url="https://search.naver.com/search.naver?query=x",
            query="탐식의 재림",
            purpose="official_title_verify",
            limit=5,
        )

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "탐식의 재림")
        self.assertEqual(items[0]["url"], "https://namu.wiki/w/탐식의 재림")

    def test_direct_fallback_reason_only_for_empty_or_degraded_low(self):
        self.assertEqual(
            server._direct_search_fallback_reason(
                filtered_items=[],
                degraded=False,
                possible_throttle=False,
                num_results=8,
            ),
            "empty_results",
        )
        self.assertEqual(
            server._direct_search_fallback_reason(
                filtered_items=[{"title": "x", "url": "https://example.com"}],
                degraded=True,
                possible_throttle=False,
                num_results=8,
            ),
            "degraded_low_accepted",
        )
        self.assertEqual(
            server._direct_search_fallback_reason(
                filtered_items=[
                    {"title": "a", "url": "https://example.com/a"},
                    {"title": "b", "url": "https://example.com/b"},
                    {"title": "c", "url": "https://example.com/c"},
                ],
                degraded=True,
                possible_throttle=False,
                num_results=8,
            ),
            "",
        )

    def test_direct_fallback_reason_detects_bridge_filter_collapse(self):
        raw_items = [
            {"title": f"Noise {idx}", "url": f"https://example.com/{idx}", "content": "Online timer"}
            for idx in range(10)
        ]
        filtered_out = [
            {**item, "filter_reason": "no_hangul:other"}
            for item in raw_items
        ]

        self.assertEqual(
            server._direct_search_fallback_reason(
                filtered_items=[],
                raw_items=raw_items,
                filtered_out_items=filtered_out,
                filter_reason_counts={"no_hangul": 10},
                degraded=False,
                possible_throttle=False,
                num_results=10,
            ),
            "low_bridge_after_filter",
        )

    def test_direct_fallback_readyz_requires_explicit_canary_gate(self):
        with patch.dict("os.environ", {}, clear=False):
            self.assertFalse(server._direct_search_fallback_readyz_ok())

        with patch.dict(
            "os.environ",
            {
                "MCP_DIRECT_SEARCH_FALLBACK_READYZ_OK": "1",
                "MCP_DIRECT_SEARCH_FALLBACK": "1",
                "MCP_DIRECT_SEARCH_PROVIDERS": "naver,bing",
            },
            clear=False,
        ):
            self.assertTrue(server._direct_search_fallback_readyz_ok())

        with patch.dict(
            "os.environ",
            {
                "MCP_DIRECT_SEARCH_FALLBACK_READYZ_OK": "1",
                "MCP_DIRECT_SEARCH_FALLBACK": "0",
                "MCP_DIRECT_SEARCH_PROVIDERS": "naver,bing",
            },
            clear=False,
        ):
            self.assertFalse(server._direct_search_fallback_readyz_ok())

    def test_direct_search_ranking_prefers_official_detail_over_reference_or_community(self):
        items = [
            {
                "title": "즉사기 들고 무림에 떨어지다",
                "url": "https://namu.wiki/w/%EC%A6%89%EC%82%AC%EA%B8%B0",
                "content": "즉사기 들고 무림에 떨어지다",
            },
            {
                "title": "즉사기 들고 무림에 떨어지다",
                "url": "https://gall.dcinside.com/mgallery/board/view/?id=genrenovel&no=1",
                "content": "즉사기 들고 무림에 떨어지다",
            },
            {
                "title": "즉사기 들고 무림에 떨어지다",
                "url": "https://novelpia.com/novel/102155",
                "content": "즉사기 들고 무림에 떨어지다",
            },
        ]

        ranked = server._rank_direct_search_items(items, "즉사기 들고 무림에 떨어지다")

        self.assertEqual(ranked[0]["url"], "https://novelpia.com/novel/102155")

    def test_series_product_number_detail_query_is_preserved(self):
        html = """
        <html><body>
          <a href="https://series.naver.com/novel/detail.series?productNo=14041321">작품 상세</a>
          <a href="https://series.naver.com/search/search.series?t=novel&fs=novel&q=x">검색</a>
        </body></html>
        """

        items = server._normalize_direct_search_items(
            html=html,
            provider="bing",
            base_url="https://www.bing.com/search?q=x",
            query="작품 상세",
            purpose="official_title_verify",
            limit=5,
        )
        ranked = server._rank_direct_search_items(items, "작품 상세")

        self.assertEqual(ranked[0]["url"], "https://series.naver.com/novel/detail.series?productNo=14041321")


if __name__ == "__main__":
    unittest.main()
