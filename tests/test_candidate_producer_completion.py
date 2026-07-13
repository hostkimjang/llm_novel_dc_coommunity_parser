from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from src.llm_batch.agentic_pipeline import AgenticPipeline
from src.llm_batch.candidate_generation import (
    build_candidate_generation_proof,
    build_candidate_producer_plan,
    build_candidate_producer_receipt,
    candidate_generation_proof_from_dict,
    candidate_producer_plans_from_payload,
    candidate_producer_receipt_from_dict,
    candidate_producer_receipts_from_payload,
)
from src.llm_batch.experts.orchestrator import ConversationContext, Orchestrator
from src.llm_batch.search.client import MCPClient


def _search_plan(*, finished: bool = True):
    return build_candidate_producer_plan(
        [{"query": 'site:example.com "작품 A"', "purpose": "official_title_verify"}],
        producer="search",
        occurrence=1,
        enumeration_finished=finished,
    )


def _search_receipt(plan, *, meta=None, results=None, occurrence: int = 1):
    return build_candidate_producer_receipt(
        results
        if results is not None
        else [{"title": "작품 A", "url": "https://example.com/work/1"}],
        meta
        if meta is not None
        else {
            "attempts": 1,
            "raw_total": 1,
            "enumeration_finished": True,
        },
        producer="search",
        operation_input='site:example.com "작품 A"',
        purpose="official_title_verify",
        plan_fingerprint=plan.plan_fingerprint,
        occurrence=occurrence,
    )


def _fetch_plan(*, finished: bool = True):
    return build_candidate_producer_plan(
        [{"url": "https://example.com/work/1", "purpose": "official_detail_fetch"}],
        producer="fetch",
        occurrence=1,
        enumeration_finished=finished,
    )


def _fetch_receipt(plan):
    return build_candidate_producer_receipt(
        [
            {
                "url": "https://example.com/work/1",
                "structured_info": {"page_title": "작품 A"},
            }
        ],
        {
            "attempted_count": 1,
            "raw_count": 1,
            "enumeration_finished": True,
        },
        producer="fetch",
        operation_input="https://example.com/work/1",
        purpose="official_detail_fetch",
        plan_fingerprint=plan.plan_fingerprint,
        occurrence=1,
    )


class CandidateProducerCompletionContractTest(unittest.TestCase):
    def test_clean_search_and_fetch_plan_can_prove_bounded_complete(self) -> None:
        search_plan = _search_plan()
        fetch_plan = _fetch_plan()
        proof = build_candidate_generation_proof(
            [search_plan, fetch_plan],
            [_search_receipt(search_plan), _fetch_receipt(fetch_plan)],
            local_snapshots=["UNKNOWN", "UNKNOWN"],
        )

        self.assertEqual(proof.status, "COMPLETE")
        self.assertEqual(proof.upstream_completeness, "COMPLETE")
        self.assertEqual(proof.missing_receipt_count, 0)
        self.assertEqual(proof.extra_receipt_count, 0)
        self.assertEqual(
            candidate_generation_proof_from_dict(proof.to_ledger_dict()),
            proof,
        )

    def test_empty_required_producer_plan_cannot_manufacture_complete(self) -> None:
        search_plan = _search_plan()
        empty_fetch_plan = build_candidate_producer_plan(
            [],
            producer="fetch",
            occurrence=1,
            enumeration_finished=True,
        )

        proof = build_candidate_generation_proof(
            [search_plan, empty_fetch_plan],
            [_search_receipt(search_plan)],
            local_snapshots=["UNKNOWN", "UNKNOWN"],
        )

        self.assertEqual("UNKNOWN", proof.status)
        self.assertNotIn("fetch", proof.observed_producers)
        self.assertIn("required_producer_missing", proof.reason_codes)

    def test_required_producer_set_cannot_be_narrowed_to_search_only(self) -> None:
        search_plan = _search_plan()

        with self.assertRaisesRegex(ValueError, r"canonical search\+fetch"):
            build_candidate_generation_proof(
                [search_plan],
                [_search_receipt(search_plan)],
                local_snapshots=["UNKNOWN", "UNKNOWN"],
                required_producers=("search",),
            )

    def test_raw_query_and_result_identity_are_not_serialized(self) -> None:
        plan = _search_plan()
        receipt = _search_receipt(plan)
        serialized = json.dumps(
            {
                "plan": plan.to_ledger_dict(),
                "receipt": receipt.to_ledger_dict(),
            },
            ensure_ascii=False,
        )

        self.assertNotIn("작품 A", serialized)
        self.assertNotIn("example.com", serialized)
        self.assertIn("input_fingerprint", serialized)
        self.assertIn("output_fingerprint", serialized)

    def test_degraded_or_throttled_cache_replay_remains_unknown(self) -> None:
        plan = _search_plan()
        receipt = _search_receipt(
            plan,
            meta={
                "attempts": 2,
                "raw_total": 0,
                "enumeration_finished": True,
                "from_cache": True,
                "degraded": True,
                "possible_throttle": True,
            },
            results=[],
        )

        self.assertEqual(receipt.status, "UNKNOWN")
        self.assertIn("cache_replay", receipt.reason_codes)
        self.assertIn("producer_degraded", receipt.reason_codes)
        self.assertIn("producer_possible_throttle", receipt.reason_codes)

    def test_clean_cache_replay_without_origin_proof_remains_unknown(self) -> None:
        plan = _search_plan()
        receipt = _search_receipt(
            plan,
            meta={
                "attempts": 1,
                "raw_total": 1,
                "enumeration_finished": True,
                "from_cache": True,
            },
        )

        self.assertEqual("UNKNOWN", receipt.status)
        self.assertIn("cache_replay", receipt.reason_codes)
        self.assertIn("cache_origin_proof_missing", receipt.reason_codes)

    def test_missing_explicit_completion_signal_remains_unknown(self) -> None:
        plan = _search_plan()
        receipt = _search_receipt(
            plan,
            meta={
                "attempts": 1,
                "raw_total": 1,
            },
        )

        self.assertEqual("UNKNOWN", receipt.status)
        self.assertFalse(receipt.enumeration_finished)

    def test_top_k_or_filter_loss_is_truncated(self) -> None:
        plan = _search_plan()
        receipt = _search_receipt(
            plan,
            meta={
                "attempts": 1,
                "raw_total": 11,
                "enumeration_finished": True,
            },
            results=[
                {"title": f"작품 {idx}", "url": f"https://example.com/work/{idx}"}
                for idx in range(10)
            ],
        )

        self.assertEqual(receipt.status, "TRUNCATED")
        self.assertIn("producer_output_truncated", receipt.reason_codes)

    def test_underreported_raw_count_fails_closed(self) -> None:
        plan = _search_plan()
        receipt = _search_receipt(
            plan,
            meta={
                "attempts": 1,
                "raw_total": 0,
                "enumeration_finished": True,
            },
            results=[
                {"title": "작품 A", "url": "https://example.com/work/1"}
            ],
        )

        self.assertEqual("UNKNOWN", receipt.status)
        self.assertEqual("MISSING_META", receipt.error_status)
        self.assertIn("producer_meta_missing", receipt.reason_codes)

    def test_missing_receipt_or_unfinished_plan_fails_closed(self) -> None:
        search_plan = _search_plan(finished=False)
        fetch_plan = _fetch_plan()
        proof = build_candidate_generation_proof(
            [search_plan, fetch_plan],
            [_fetch_receipt(fetch_plan)],
            local_snapshots=["UNKNOWN", "UNKNOWN"],
        )

        self.assertEqual(proof.status, "UNKNOWN")
        self.assertEqual(proof.unfinished_plan_count, 1)
        self.assertEqual(proof.missing_receipt_count, 1)
        self.assertIn("bounded_plan_unfinished", proof.reason_codes)
        self.assertIn("planned_operation_receipt_missing", proof.reason_codes)

    def test_local_or_producer_loss_dominates_as_truncated(self) -> None:
        plan = _search_plan()
        fetch_plan = _fetch_plan()
        truncated_receipt = _search_receipt(
            plan,
            meta={
                "attempts": 1,
                "raw_total": 2,
                "enumeration_finished": True,
            },
            results=[{"title": "작품 A"}],
        )
        proof = build_candidate_generation_proof(
            [plan, fetch_plan],
            [truncated_receipt, _fetch_receipt(fetch_plan)],
            local_snapshots=["TRUNCATED", "UNKNOWN"],
        )

        self.assertEqual(proof.status, "TRUNCATED")
        self.assertEqual(proof.truncated_receipt_count, 1)
        self.assertEqual(proof.local_truncated_count, 1)

    def test_stage_only_or_missing_required_producer_never_completes(self) -> None:
        plan = _search_plan()
        proof = build_candidate_generation_proof(
            [plan],
            [_search_receipt(plan)],
            local_snapshots=["UNKNOWN", "UNKNOWN"],
        )

        self.assertEqual(proof.status, "UNKNOWN")
        self.assertIn("required_producer_missing", proof.reason_codes)

    def test_tamper_and_duplicate_receipts_fail_closed(self) -> None:
        plan = _search_plan()
        receipt = _search_receipt(plan)
        tampered = copy.deepcopy(receipt.to_ledger_dict())
        tampered["accepted_count"] = 0
        with self.assertRaises(ValueError):
            candidate_producer_receipt_from_dict(tampered)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            candidate_producer_receipts_from_payload(
                [receipt.to_ledger_dict(), receipt.to_ledger_dict()]
            )

    def test_context_search_outcome_records_one_redacted_receipt(self) -> None:
        ctx = ConversationContext(post_id=10, post_data={}, comments=[])
        plan = _search_plan()
        ctx.record_candidate_producer_plan(plan)
        query = 'site:example.com "작품 A"'
        results = [{"title": "작품 A", "url": "https://example.com/work/1"}]
        meta = {
            "attempts": 1,
            "raw_total": 1,
            "enumeration_finished": True,
        }

        ctx.record_search_outcome(
            1,
            raw_count=1,
            purpose="official_title_verify",
            producer_query=query,
            producer_results=results,
            producer_meta=meta,
            producer_plan_fingerprint=plan.plan_fingerprint,
        )

        receipts = candidate_producer_receipts_from_payload(
            ctx._candidate_producer_receipts
        )
        self.assertEqual(1, len(receipts))
        self.assertEqual("COMPLETE", receipts[0].status)
        serialized = json.dumps(ctx._candidate_producer_receipts, ensure_ascii=False)
        self.assertNotIn("작품 A", serialized)
        self.assertNotIn("example.com", serialized)

    def test_pipeline_direct_search_recorder_binds_plan_and_receipt(self) -> None:
        pipeline = AgenticPipeline.__new__(AgenticPipeline)
        ctx = ConversationContext(post_id=11, post_data={}, comments=[])
        query = 'site:example.com "작품 A"'
        results = [{"title": "작품 A", "url": "https://example.com/work/1"}]
        meta = {
            "attempts": 1,
            "raw_total": 1,
            "enumeration_finished": True,
        }

        pipeline._record_context_search_outcome_from_meta(
            ctx,
            query,
            "official_title_verify",
            results,
            meta,
        )

        plans = candidate_producer_plans_from_payload(ctx._candidate_producer_plans)
        receipts = candidate_producer_receipts_from_payload(
            ctx._candidate_producer_receipts
        )
        self.assertEqual(1, len(plans))
        self.assertEqual(1, len(receipts))
        self.assertEqual(plans[0].plan_fingerprint, receipts[0].plan_fingerprint)
        self.assertFalse(plans[0].enumeration_finished)
        self.assertEqual("COMPLETE", receipts[0].status)
        self.assertEqual([], ctx._candidate_producer_integrity_errors)
        serialized = json.dumps(
            {
                "plans": ctx._candidate_producer_plans,
                "receipts": ctx._candidate_producer_receipts,
            },
            ensure_ascii=False,
        )
        self.assertNotIn("작품 A", serialized)
        self.assertNotIn("example.com", serialized)

    def test_orchestrator_fetch_plan_is_predeclared_before_receipt(self) -> None:
        class FetchOwner:
            def fetch(self, url: str):
                return self._fetch_with_meta(url)[0]

            def _fetch_with_meta(self, url: str):
                return (
                    {
                        "url": url,
                        "structured_info": {"page_title": "작품 A"},
                    },
                    {
                        "attempted_count": 1,
                        "raw_count": 1,
                        "enumeration_finished": True,
                        "error_status": "NONE",
                    },
                )

        owner = FetchOwner()
        orchestrator = Orchestrator({}, fetch_fn=owner.fetch)
        ctx = ConversationContext(post_id=12, post_data={}, comments=[])

        result = orchestrator._fetch_with_context_receipt(
            ctx,
            "https://example.com/work/1",
            purpose="official_detail_fetch",
        )

        self.assertIsInstance(result, dict)
        plans = candidate_producer_plans_from_payload(ctx._candidate_producer_plans)
        receipts = candidate_producer_receipts_from_payload(
            ctx._candidate_producer_receipts
        )
        self.assertEqual(1, len(plans))
        self.assertEqual(1, len(receipts))
        self.assertTrue(plans[0].enumeration_finished)
        self.assertEqual("COMPLETE", receipts[0].status)
        self.assertEqual(plans[0].plan_fingerprint, receipts[0].plan_fingerprint)

    def test_search_meta_emits_explicit_completion_and_cache_fails_closed(self) -> None:
        class SearchMCP:
            def __init__(self) -> None:
                self.calls = 0

            def search(self, query: str, purpose: str = ""):
                self.calls += 1
                return {
                    "results": [
                        {
                            "title": "작품 A",
                            "url": "https://example.com/work/1",
                            "content": "작품 상세",
                        }
                    ],
                    "raw_total": 1,
                    "total": 1,
                }

        pipeline = AgenticPipeline.__new__(AgenticPipeline)
        pipeline.mcp = SearchMCP()
        pipeline._search_cache = {}
        pipeline._search_cache_lock = threading.Lock()
        pipeline._search_cache_hits = 0
        pipeline._search_cache_misses = 0
        pipeline._search_degraded_zero_suppression = {}
        pipeline._search_degraded_zero_suppression_hits = 0
        pipeline._consecutive_degraded = 0
        pipeline._last_search_meta = {}

        query = 'site:example.com "작품 A"'
        first, first_meta = pipeline._search_with_meta(
            query,
            "official_title_verify",
        )
        second, second_meta = pipeline._search_with_meta(
            query,
            "official_title_verify",
        )

        self.assertEqual(1, pipeline.mcp.calls)
        self.assertTrue(first_meta["enumeration_finished"])
        self.assertTrue(second_meta["enumeration_finished"])
        self.assertTrue(second_meta["from_cache"])
        plan = _search_plan()
        replay_receipt = _search_receipt(
            plan,
            meta=second_meta,
            results=second,
        )
        self.assertEqual("UNKNOWN", replay_receipt.status)
        self.assertIn("cache_origin_proof_missing", replay_receipt.reason_codes)

    def test_partial_engine_failure_cannot_produce_complete_receipt(self) -> None:
        class PartialSearchMCP:
            def search(self, query: str, purpose: str = ""):
                return {
                    "results": [
                        {
                            "title": "작품 A",
                            "url": "https://example.com/work/1",
                            "content": "작품 상세",
                        }
                    ],
                    "raw_total": 1,
                    "total": 1,
                    "degraded": False,
                    "possible_throttle": False,
                    "engine_errors": ["one configured engine failed"],
                }

        pipeline = AgenticPipeline.__new__(AgenticPipeline)
        pipeline.mcp = PartialSearchMCP()
        pipeline._search_cache = {}
        pipeline._search_cache_lock = threading.Lock()
        pipeline._search_cache_hits = 0
        pipeline._search_cache_misses = 0
        pipeline._search_degraded_zero_suppression = {}
        pipeline._search_degraded_zero_suppression_hits = 0
        pipeline._consecutive_degraded = 0
        pipeline._last_search_meta = {}

        results, meta = pipeline._search_with_meta(
            'site:example.com "작품 A"',
            "official_title_verify",
        )
        plan = _search_plan()
        receipt = _search_receipt(plan, meta=meta, results=results)

        self.assertFalse(meta["enumeration_finished"])
        self.assertTrue(meta["degraded"])
        self.assertEqual("UNKNOWN", receipt.status)
        self.assertIn("producer_degraded", receipt.reason_codes)

    def test_generic_search_error_or_block_cannot_produce_complete(self) -> None:
        class BlockedSearchMCP:
            def search(self, query: str, purpose: str = ""):
                return {
                    "results": [],
                    "raw_total": 0,
                    "total": 0,
                    "error": "upstream failed",
                    "blocked": True,
                }

        pipeline = AgenticPipeline.__new__(AgenticPipeline)
        pipeline.mcp = BlockedSearchMCP()
        pipeline._search_cache = {}
        pipeline._search_cache_lock = threading.Lock()
        pipeline._search_cache_hits = 0
        pipeline._search_cache_misses = 0
        pipeline._search_degraded_zero_suppression = {}
        pipeline._search_degraded_zero_suppression_hits = 0
        pipeline._consecutive_degraded = 0
        pipeline._last_search_meta = {}

        results, meta = pipeline._search_with_meta(
            'site:example.com "작품 A"',
            "official_title_verify",
        )
        plan = _search_plan()
        receipt = _search_receipt(plan, meta=meta, results=results)

        self.assertFalse(meta["enumeration_finished"])
        self.assertEqual("ERROR", meta["error_status"])
        self.assertTrue(meta["degraded"])
        self.assertEqual("UNKNOWN", receipt.status)

    def test_mcp_client_marks_non_object_search_response_malformed(self) -> None:
        class FakeResponse:
            def raise_for_status(self) -> None:
                return None

            def json(self):
                return ["not", "an", "object"]

        client = MCPClient(endpoint="http://127.0.0.1:3333")
        client.endpoint_failover = False
        with patch(
            "src.llm_batch.search.client.httpx.post",
            return_value=FakeResponse(),
        ):
            payload = client.search('site:example.com "작품 A"')

        self.assertTrue(payload["malformed_response"])
        self.assertEqual("non_object_search_response", payload["error"])
        self.assertEqual([], payload["results"])

    def test_fetch_meta_preserves_success_cache_and_error_provenance(self) -> None:
        class FakeMCP:
            def __init__(self) -> None:
                self.calls = 0
                self.fail = False

            def fetch(self, url: str):
                self.calls += 1
                if self.fail:
                    raise RuntimeError("secret upstream detail")
                return {
                    "url": url,
                    "structured_info": {"page_title": "작품 A"},
                }

        def make_pipeline(tmp_path: Path, mcp: FakeMCP) -> AgenticPipeline:
            pipeline = AgenticPipeline.__new__(AgenticPipeline)
            pipeline.mcp = mcp
            pipeline.enable_url_fetch_disk_cache = False
            pipeline.url_fetch_cache_dir = tmp_path
            pipeline._url_fetch_cache = {}
            pipeline._url_fetch_cache_meta = {}
            pipeline._url_fetch_cache_hits = 0
            pipeline._url_fetch_cache_misses = 0
            pipeline._url_fetch_cache_lock = threading.Lock()
            pipeline._url_fetch_inflight = {}
            return pipeline

        with tempfile.TemporaryDirectory() as tmp:
            mcp = FakeMCP()
            pipeline = make_pipeline(Path(tmp), mcp)
            url = "https://example.com/work/1"
            first, first_meta = pipeline._fetch_with_meta(url)
            second, second_meta = pipeline._fetch_with_meta(url)

            self.assertEqual(first, second)
            self.assertEqual(1, mcp.calls)
            self.assertTrue(first_meta["enumeration_finished"])
            self.assertEqual("NONE", first_meta["error_status"])
            self.assertTrue(second_meta["from_cache"])
            self.assertEqual("memory", second_meta["cache_source"])

            failed_mcp = FakeMCP()
            failed_mcp.fail = True
            failed_pipeline = make_pipeline(Path(tmp), failed_mcp)
            failed, failed_meta = failed_pipeline._fetch_with_meta(
                "https://example.com/work/2"
            )
            self.assertIsNone(failed)
            self.assertFalse(failed_meta["enumeration_finished"])
            self.assertEqual("ERROR", failed_meta["error_status"])
            self.assertNotIn("secret upstream detail", json.dumps(failed_meta))

    def test_fetch_snippet_fallback_cannot_produce_complete_receipt(self) -> None:
        class FallbackMCP:
            def fetch(self, url: str):
                return {
                    "url": url,
                    "fallback": True,
                    "restricted_domain": True,
                    "direct_fetch_error": "secret direct fetch failure",
                    "structured_info": {
                        "page_title": "검색 snippet 제목",
                        "fallback_source": "searxng_site_search",
                    },
                }

        pipeline = AgenticPipeline.__new__(AgenticPipeline)
        pipeline.mcp = FallbackMCP()
        pipeline.enable_url_fetch_disk_cache = False
        pipeline.url_fetch_cache_dir = Path("tmp/test_candidate_fetch_fallback")
        pipeline._url_fetch_cache = {}
        pipeline._url_fetch_cache_meta = {}
        pipeline._url_fetch_cache_hits = 0
        pipeline._url_fetch_cache_misses = 0
        pipeline._url_fetch_cache_lock = threading.Lock()
        pipeline._url_fetch_inflight = {}

        url = "https://example.com/work/fallback"
        result, meta = pipeline._fetch_with_meta(url)
        plan = build_candidate_producer_plan(
            [{"url": url, "purpose": "official_detail_fetch"}],
            producer="fetch",
            occurrence=1,
            enumeration_finished=True,
        )
        receipt = build_candidate_producer_receipt(
            [result],
            meta,
            producer="fetch",
            operation_input=url,
            purpose="official_detail_fetch",
            plan_fingerprint=plan.plan_fingerprint,
            occurrence=1,
        )

        self.assertFalse(meta["enumeration_finished"])
        self.assertTrue(meta["degraded"])
        self.assertEqual("ERROR", meta["error_status"])
        self.assertEqual("UNKNOWN", receipt.status)
        self.assertNotIn(
            "secret direct fetch failure",
            json.dumps(receipt.to_ledger_dict(), ensure_ascii=False),
        )


if __name__ == "__main__":
    unittest.main()
