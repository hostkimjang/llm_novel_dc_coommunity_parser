import unittest

from llm_batch.agentic_pipeline import AgenticPipeline
from llm_batch.experts.orchestrator import ConversationContext, Orchestrator
from tools.audit_expert_run_health import _build_search_evidence_gate


class SearchRecoveryContractTest(unittest.TestCase):
    def test_author_bridge_title_builds_narrow_official_probe(self):
        orchestrator = Orchestrator.__new__(Orchestrator)
        ctx = ConversationContext(post_id=11694019, post_data={}, comments=[])
        hints = {
            "title_hints": [
                {
                    "title": "이세계에서 사이비로 살아남기",
                    "source": "author_bridge",
                    "author_anchor": "미츄리",
                    "url": "https://arca.live/b/novelchannel/77980889",
                }
            ],
            "author_hints": [
                {
                    "name": "미츄리",
                    "source": "author_bridge",
                    "url": "https://arca.live/b/novelchannel/77980889",
                }
            ],
        }

        queries = orchestrator._build_author_bridge_official_url_queries(
            ctx,
            hints,
            "이세계에서 사이비로 살아남기",
        )

        self.assertEqual(
            queries,
            [
                {
                    "query": "미츄리 이세계에서 사이비로 살아남기",
                    "purpose": "adaptive_author_bridge_official_url",
                    "priority": -1,
                }
            ],
        )

    def test_author_bridge_title_keeps_gap_when_only_wrong_official_details_exist(self):
        orchestrator = Orchestrator.__new__(Orchestrator)
        ctx = ConversationContext(post_id=11694019, post_data={}, comments=[])
        ctx.search_results = [
            {
                "title": "혼후순결 - 웹소설",
                "url": "https://page.kakao.com/content/60742024",
                "content": "혼후순결 카카오페이지",
            },
            {
                "title": "감옥학원에서 나만 힐링할거다",
                "url": "https://novelpia.com/novel/75754",
                "content": "작가 미츄리",
            },
        ]
        hints = {
            "title_hints": [
                {
                    "title": "이세계에서 사이비로 살아남기",
                    "source": "author_bridge",
                    "author_anchor": "미츄리",
                }
            ],
            "author_hints": [{"name": "미츄리", "source": "author_bridge"}],
        }

        gaps = orchestrator._identify_evidence_gaps(ctx, hints, ["미츄리", "혼후순결"])

        self.assertIn(
            {
                "type": "no_official_url",
                "term": "이세계에서 사이비로 살아남기",
                "description": "'이세계에서 사이비로 살아남기'의 author_bridge 공식 detail 미확정",
            },
            gaps,
        )

    def test_author_bridge_title_gap_closes_with_exact_official_detail(self):
        orchestrator = Orchestrator.__new__(Orchestrator)
        ctx = ConversationContext(post_id=11694019, post_data={}, comments=[])
        ctx.search_results = [
            {
                "title": "이세계에서 사이비로 살아남기 - 노벨피아",
                "url": "https://novelpia.com/novel/181771",
                "content": "작가 미츄리",
            }
        ]
        hints = {
            "title_hints": [
                {
                    "title": "이세계에서 사이비로 살아남기",
                    "source": "author_bridge",
                    "author_anchor": "미츄리",
                }
            ],
            "author_hints": [{"name": "미츄리", "source": "author_bridge"}],
        }

        gaps = orchestrator._identify_evidence_gaps(ctx, hints, ["미츄리", "혼후순결"])

        self.assertNotIn(
            "'이세계에서 사이비로 살아남기'의 author_bridge 공식 detail 미확정",
            [gap.get("description") for gap in gaps],
        )

    def test_context_records_degraded_fallback_recovery(self):
        ctx = ConversationContext(post_id=1, post_data={}, comments=[])

        ctx.record_search_outcome(
            2,
            raw_count=10,
            filtered_count=8,
            degraded=True,
            attempts=2,
            retries=1,
            fallback_recovered=True,
            degraded_recovered=True,
            direct_search_used=True,
            direct_search_reason="low_bridge_after_filter",
            direct_search_count=2,
            direct_search_providers=["bing"],
        )

        stats = ctx.search_query_stats
        self.assertEqual(stats["degraded_total"], 1)
        self.assertEqual(stats["degraded_nonzero"], 1)
        self.assertEqual(stats["degraded_zero"], 0)
        self.assertEqual(stats["degraded_recovered_total"], 1)
        self.assertEqual(stats["unrecovered_degraded_total"], 0)
        self.assertEqual(stats["direct_search_used_total"], 1)
        self.assertEqual(stats["direct_search_result_total"], 2)

        health = AgenticPipeline._build_search_health_public_fields(
            AgenticPipeline.__new__(AgenticPipeline),
            ctx,
        )
        self.assertEqual(health["status"], "SEARCH_DEGRADED_RECOVERED")
        self.assertEqual(health["degraded_recovered"], 1)
        self.assertEqual(health["unrecovered_degraded"], 0)

    def test_audit_does_not_block_recovered_degraded_health(self):
        audit = _build_search_evidence_gate(
            manifest_data={
                "mcp_health_include_search": True,
                "mcp_health_light_mode": False,
                "mcp_health_ok_count": 1,
                "mcp_health_failure_count": 0,
            },
            rows=[
                {
                    "result": {
                        "analysis_result": {
                            "identity": {
                                "search_health": {
                                    "queries_issued": 1,
                                    "degraded": 1,
                                    "degraded_zero": 0,
                                    "degraded_recovered": 1,
                                    "unrecovered_degraded": 0,
                                    "status": "SEARCH_DEGRADED_RECOVERED",
                                }
                            }
                        }
                    }
                }
            ],
            log_audit={"counts": {}},
        )

        self.assertEqual(audit["gate"], "GO")
        self.assertEqual(audit["row_search_health"]["degraded_recovered_total"], 1)
        self.assertEqual(audit["row_search_health"]["unrecovered_degraded_total"], 0)
        self.assertNotIn("search_degraded_observed", audit["blockers"])


if __name__ == "__main__":
    unittest.main()
