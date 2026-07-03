from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from llm_batch.agentic_pipeline import AgenticPipeline  # noqa: E402
from llm_batch.experts.orchestrator import ConversationContext  # noqa: E402


class DummyLLM:
    pass


class DummyMCP:
    def __init__(self):
        self.calls = 0

    def search(self, query: str, purpose: str = ""):
        self.calls += 1
        return {
            "results": [],
            "degraded": True,
            "possible_throttle": True,
            "attempts": 5,
            "retry_count": 4,
            "total": 0,
            "raw_total": 0,
            "lang_filtered": 0,
            "provider_url": "http://127.0.0.1:8889/search",
            "engines": "google,bing",
        }


def _build_pipeline(mcp: DummyMCP) -> AgenticPipeline:
    tmpdir = tempfile.TemporaryDirectory()
    pipeline = AgenticPipeline(llm=DummyLLM(), mcp=mcp, output_dir=Path(tmpdir.name), max_iterations=1)
    pipeline._test_tmpdir = tmpdir
    return pipeline


class SearchDegradedZeroSuppressionTest(unittest.TestCase):
    def test_repeated_degraded_zero_query_is_suppressed_without_cache_poisoning(self):
        mcp = DummyMCP()
        pipeline = _build_pipeline(mcp)
        env = {"PIPELINE_SEARCH_DEGRADED_ZERO_SUPPRESS_TTL_SECONDS": "600"}

        with patch.dict(os.environ, env, clear=False):
            first_results, first_meta = pipeline._search_with_meta(
                'site:novelpia.com/novel "아생갤"',
                "title_anchor_official_probe",
            )
            second_results, second_meta = pipeline._search_with_meta(
                'site:novelpia.com/novel "아생갤"',
                "title_anchor_official_probe",
            )

        self.assertEqual(first_results, [])
        self.assertEqual(second_results, [])
        self.assertEqual(mcp.calls, 1)
        self.assertFalse(first_meta.get("from_cache"))
        self.assertFalse(first_meta.get("suppressed_degraded_zero"))
        self.assertFalse(second_meta.get("from_cache"))
        self.assertTrue(second_meta.get("suppressed_degraded_zero"))
        self.assertTrue(second_meta.get("degraded"))
        self.assertNotIn(
            'title_anchor_official_probe||site:novelpia.com/novel "아생갤"',
            pipeline._search_cache,
        )

    def test_ttl_zero_disables_degraded_zero_suppression(self):
        mcp = DummyMCP()
        pipeline = _build_pipeline(mcp)
        env = {"PIPELINE_SEARCH_DEGRADED_ZERO_SUPPRESS_TTL_SECONDS": "0"}

        with patch.dict(os.environ, env, clear=False):
            pipeline._search_with_meta("same degraded zero", "title_anchor_official_probe")
            _, second_meta = pipeline._search_with_meta("same degraded zero", "title_anchor_official_probe")

        self.assertEqual(mcp.calls, 2)
        self.assertFalse(second_meta.get("suppressed_degraded_zero"))

    def test_suppressed_degraded_zero_has_separate_stats_counter(self):
        ctx = ConversationContext(post_id=1, post_data={}, comments=[])

        ctx.record_search_outcome(
            0,
            raw_count=0,
            degraded=True,
            attempts=1,
            retries=0,
            degraded_zero_suppressed=True,
            purpose="title_anchor_official_probe",
        )

        stats = ctx.search_query_stats
        self.assertEqual(stats["degraded_total"], 1)
        self.assertEqual(stats["degraded_zero"], 1)
        self.assertEqual(stats["unrecovered_degraded_total"], 1)
        self.assertEqual(stats["degraded_zero_suppressed_total"], 1)
        self.assertEqual(stats["cache_hit_total"], 0)


if __name__ == "__main__":
    unittest.main()
