import unittest

from llm_batch.agentic_pipeline import AgenticPipeline
from llm_batch.experts.orchestrator import ConversationContext
from tools.audit_expert_run_health import _build_search_evidence_gate


class SearchRecoveryContractTest(unittest.TestCase):
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
