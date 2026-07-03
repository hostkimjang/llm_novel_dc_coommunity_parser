import unittest
from unittest.mock import patch

from llm_batch.search.client import MCPClient
from tools import warp_shards


class SearchBudgetContractTest(unittest.TestCase):
    def test_mcp_client_does_not_retry_same_endpoint_by_default(self):
        with patch.dict("os.environ", {}, clear=True):
            client = MCPClient()

        self.assertEqual(client.search_max_retries, 0)
        self.assertTrue(client.search_retry_on_degraded_empty)

    def test_warp_shard_compose_defaults_keep_search_budget_bounded(self):
        block = warp_shards._render_service_block(1, 3333, 28081)

        self.assertIn("MCP_SEARCH_MAX_RETRIES=${MCP_SEARCH_MAX_RETRIES:-1}", block)
        self.assertIn("MCP_SEARCH_MAX_PAGES=${MCP_SEARCH_MAX_PAGES:-2}", block)
        self.assertIn("MCP_SEARCH_ENGINES=${MCP_SEARCH_ENGINES:-google,bing,webcrawler,naver}", block)
        self.assertIn(
            "MCP_SEARCH_FALLBACK_ENGINES=${MCP_SEARCH_FALLBACK_ENGINES:-webcrawler,google,bing,naver}",
            block,
        )


if __name__ == "__main__":
    unittest.main()
