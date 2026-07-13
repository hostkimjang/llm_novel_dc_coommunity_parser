from __future__ import annotations

import json
import hashlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import time
import unittest

from llm_batch.agentic_pipeline import AgenticPipeline
from llm_batch.framed_wal import FramedWAL
from llm_batch.local_stage_gate import FileSingleflightLease, StageLimiterConfig
from llm_batch.pipeline_stage_runtime_adapter import (
    PipelineSearchRuntimeShadowAdapter,
    PipelineSearchRuntimeShadowConfig,
    PipelineStageRuntimeAdapterError,
    PipelineStageRuntimeMeasurementError,
    read_pipeline_search_runtime_measurement,
)
from llm_batch.shared_cache_contract import FileSharedCacheAdapter
from llm_batch.shared_result_singleflight import FileSharedResultSingleflight
from llm_batch.stage_budget import ArtifactRef, StageBudgetBinding


class DummyLLM:
    pass


class CountingMCP:
    def __init__(self, *, degraded: bool = False) -> None:
        self.calls = 0
        self.degraded = degraded

    def search(self, _query: str, purpose: str = "") -> dict:
        self.calls += 1
        if self.degraded:
            return {
                "results": [],
                "total": 0,
                "raw_total": 0,
                "degraded": True,
                "possible_throttle": True,
            }
        return {
            "results": [
                {
                    "title": "고정 작품",
                    "url": "https://example.test/work",
                    "content": "공개 검색 결과",
                }
            ],
            "total": 1,
            "raw_total": 1,
            "retry_count": 0,
        }


class SlowCountingMCP(CountingMCP):
    def search(self, query: str, purpose: str = "") -> dict:
        value = super().search(query, purpose=purpose)
        time.sleep(0.05)
        return value


class EchoCountingMCP(CountingMCP):
    def search(self, query: str, purpose: str = "") -> dict:
        self.calls += 1
        return {
            "results": [{"title": query.casefold().replace(" ", "%20"), "url": "https://example.test/echo", "content": ""}],
            "total": 1,
            "raw_total": 1,
        }


class CallsThenFailsAdapter:
    enabled = True

    def execute(self, *, operation, **_kwargs):
        operation()
        raise RuntimeError("adapter failed after legacy call")


class PipelineStageRuntimeAdapterTests(unittest.TestCase):
    def _binding(self, root: Path, *, suffix: str = "") -> StageBudgetBinding:
        refs = []
        for name in ("run_spec", "publication_scope", "attempt", "decision_ledger"):
            path = root / f"{name}{suffix}.json"
            path.write_text(json.dumps({"name": name, "suffix": suffix}), encoding="utf-8")
            refs.append(ArtifactRef.snapshot(path))
        return StageBudgetBinding(*refs)

    def _adapter(
        self,
        root: Path,
        *,
        rate_per_second: float = 1000.0,
        burst: int = 16,
        max_wait_ms: int = 20,
    ) -> PipelineSearchRuntimeShadowAdapter:
        cache = FileSharedCacheAdapter(root / "cache", allow_write=True)
        shared = FileSharedResultSingleflight(
            cache,
            FileSingleflightLease(root / "leases"),
            enabled=True,
        )
        config = PipelineSearchRuntimeShadowConfig(
            enabled=True,
            provider="mcp",
            model="mcp_search",
            limiter=StageLimiterConfig(
                rate_per_second=rate_per_second,
                burst=burst,
                max_wait_ms=max_wait_ms,
            ),
            cache_ttl_seconds=30.0,
            follower_timeout_ms=100,
            lease_timeout_ms=1000,
        )
        return PipelineSearchRuntimeShadowAdapter(
            config=config,
            binding=self._binding(root),
            shared_result=shared,
            receipt_wal=FramedWAL(root / "runtime_receipts.wal"),
        )

    def test_default_and_explicit_disabled_adapter_are_complete_no_ops(self) -> None:
        baseline_mcp = CountingMCP()
        disabled_mcp = CountingMCP()
        baseline = AgenticPipeline(llm=DummyLLM(), mcp=baseline_mcp, max_iterations=1)
        disabled = AgenticPipeline(
            llm=DummyLLM(),
            mcp=disabled_mcp,
            max_iterations=1,
            search_runtime_shadow=PipelineSearchRuntimeShadowAdapter(),
        )
        self.assertEqual(
            baseline._search_with_meta("동일 질의", "verify"),
            disabled._search_with_meta("동일 질의", "verify"),
        )
        self.assertEqual((baseline_mcp.calls, disabled_mcp.calls), (1, 1))

    def test_explicit_runtime_adapter_reuses_exact_shared_result_and_writes_hash_only_receipts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            adapter = self._adapter(root)
            mcp = CountingMCP()
            first_pipeline = AgenticPipeline(
                llm=DummyLLM(), mcp=mcp, max_iterations=1, search_runtime_shadow=adapter
            )
            second_pipeline = AgenticPipeline(
                llm=DummyLLM(), mcp=mcp, max_iterations=1, search_runtime_shadow=adapter
            )
            first, first_meta = first_pipeline._search_with_meta("민감 원문 질의", "verify")
            second, second_meta = second_pipeline._search_with_meta("민감 원문 질의", "verify")
            self.assertEqual(first, second)
            self.assertFalse(first_meta["from_cache"])
            self.assertTrue(second_meta["from_cache"])
            self.assertEqual(mcp.calls, 1)

            # A fresh adapter instance can reconstruct the gate from the
            # crash-safe WAL without relying on the producer's memory.
            recovered_adapter = self._adapter(root)
            receipt = recovered_adapter.require_measurement_go()
            self.assertEqual(receipt["attempt_count"], 2)
            self.assertEqual(adapter.measurement_error_classes, ())
            self.assertEqual(recovered_adapter.measurement_error_classes, ())
            self.assertEqual(receipt["provenance"][0]["run_spec_sha256"], adapter.binding.run_spec.sha256)
            self.assertEqual(receipt["provenance"][0]["model"], "mcp_search")
            self.assertEqual(
                read_pipeline_search_runtime_measurement(receipt)["independent_readback"],
                "GO_RUNTIME_SHADOW_RECEIPT_INTEGRITY",
            )
            self.assertNotIn("민감 원문 질의", (root / "runtime_receipts.wal").read_bytes().decode("utf-8", errors="ignore"))
            cache_bytes = b"".join(path.read_bytes() for path in (root / "cache").glob("*.json"))
            self.assertNotIn("민감 원문 질의".encode("utf-8"), cache_bytes)

    def test_degraded_result_is_never_cached_and_measurement_gate_holds(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            adapter = self._adapter(root)
            mcp = CountingMCP(degraded=True)
            for _ in range(2):
                pipeline = AgenticPipeline(
                    llm=DummyLLM(), mcp=mcp, max_iterations=1, search_runtime_shadow=adapter
                )
                results, meta = pipeline._search_with_meta("degraded", "verify")
                self.assertEqual(results, [])
                self.assertTrue(meta["degraded"])
            self.assertEqual(mcp.calls, 2)
            receipt = adapter.build_measurement_receipt()
            self.assertEqual(receipt["gate"], "HOLD_RUNTIME_SHADOW_MEASUREMENT")
            self.assertEqual([event["cache_source"] for event in receipt["events"]], ["DEGRADED_EXCLUDED"] * 2)
            with self.assertRaises(PipelineStageRuntimeMeasurementError):
                adapter.require_measurement_go()

    def test_concurrent_pipelines_share_one_inflight_search_with_bounded_follower_wait(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            adapter = self._adapter(root)
            mcp = SlowCountingMCP()
            pipelines = [
                AgenticPipeline(llm=DummyLLM(), mcp=mcp, max_iterations=1, search_runtime_shadow=adapter)
                for _ in range(2)
            ]
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [
                    pool.submit(pipeline._search_with_meta, "동시 질의", "verify")
                    for pipeline in pipelines
                ]
                outputs = [future.result(timeout=2) for future in futures]
            self.assertEqual(outputs[0][0], outputs[1][0])
            self.assertEqual(mcp.calls, 1)
            receipt = adapter.require_measurement_go()
            self.assertEqual(
                {event["singleflight_role"] for event in receipt["events"]},
                {"LEADER", "FOLLOWER"},
            )
            self.assertTrue(any(event["inflight_deduped"] for event in receipt["events"]))

    def test_semantically_degraded_shared_payload_is_rejected_and_legacy_search_runs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            adapter = self._adapter(root)
            namespace, _key, _identity = adapter._identity(query="poison", purpose="verify")
            assert adapter.shared_result is not None
            adapter.shared_result.cache.put(
                namespace,
                value={
                    "schema_version": "pipeline_search_runtime_shadow_cache_value_v1",
                    "results": [{"title": "오염", "url": "https://bad.test", "content": ""}],
                    "meta": {
                        "degraded": True,
                        "possible_throttle": False,
                        "enumeration_finished": True,
                        "error_status": "NONE",
                    },
                },
                ttl_seconds=30,
                degraded=False,
            )
            mcp = CountingMCP()
            pipeline = AgenticPipeline(
                llm=DummyLLM(), mcp=mcp, max_iterations=1, search_runtime_shadow=adapter
            )
            results, _meta = pipeline._search_with_meta("poison", "verify")
            self.assertEqual(results[0]["title"], "고정 작품")
            self.assertEqual(mcp.calls, 1)
            self.assertEqual(adapter.build_measurement_receipt()["gate"], "HOLD_RUNTIME_SHADOW_MEASUREMENT")

    def test_response_echoing_raw_query_is_returned_but_never_persisted_or_reused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            adapter = self._adapter(root)
            mcp = EchoCountingMCP()
            for _ in range(2):
                pipeline = AgenticPipeline(
                    llm=DummyLLM(), mcp=mcp, max_iterations=1, search_runtime_shadow=adapter
                )
                results, _meta = pipeline._search_with_meta("Secret Query", "verify")
                self.assertEqual(results[0]["title"], "secret%20query")
            self.assertEqual(mcp.calls, 2)
            durable = (root / "runtime_receipts.wal").read_bytes() + b"".join(
                path.read_bytes() for path in (root / "cache").glob("*.json")
            )
            self.assertNotIn(b"Secret Query", durable)
            self.assertNotIn(b"secret%20query", durable)
            self.assertEqual(adapter.build_measurement_receipt()["gate"], "HOLD_RUNTIME_SHADOW_MEASUREMENT")

    def test_independent_reader_rejects_rehashed_semantic_or_runtime_config_tamper(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            adapter = self._adapter(root)
            pipeline = AgenticPipeline(
                llm=DummyLLM(), mcp=CountingMCP(), max_iterations=1, search_runtime_shadow=adapter
            )
            pipeline._search_with_meta("clean", "verify")
            receipt = adapter.require_measurement_go()

            def rehash(value: dict) -> None:
                material = {key: value[key] for key in value if key != "measurement_sha256"}
                value["measurement_sha256"] = hashlib.sha256(
                    json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
                ).hexdigest()

            semantic_tamper = json.loads(json.dumps(receipt))
            semantic_tamper["events"][0]["outcome"] = "FAILURE"
            rehash(semantic_tamper)
            with self.assertRaisesRegex(PipelineStageRuntimeMeasurementError, "completion semantics"):
                read_pipeline_search_runtime_measurement(semantic_tamper)

            config_tamper = json.loads(json.dumps(receipt))
            config_tamper["config"]["model"] = "other_model"
            rehash(config_tamper)
            with self.assertRaisesRegex(PipelineStageRuntimeMeasurementError, "runtime id"):
                read_pipeline_search_runtime_measurement(config_tamper)

    def test_limiter_denial_fails_open_to_legacy_but_measurement_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            adapter = self._adapter(root, rate_per_second=0.0, burst=1, max_wait_ms=0)
            mcp = CountingMCP()
            pipeline = AgenticPipeline(
                llm=DummyLLM(), mcp=mcp, max_iterations=1, search_runtime_shadow=adapter
            )
            results, _meta = pipeline._search_with_meta("rate limited", "verify")
            self.assertEqual(results[0]["title"], "고정 작품")
            self.assertEqual(mcp.calls, 1)
            receipt = adapter.build_measurement_receipt()
            self.assertEqual(receipt["events"][0]["limiter_outcome"], "DENIED")
            self.assertEqual(receipt["gate"], "HOLD_RUNTIME_SHADOW_MEASUREMENT")

    def test_completion_receipt_failure_preserves_result_and_leaves_fail_closed_incomplete_start(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            adapter = self._adapter(root)
            assert adapter._wal is not None
            original_append = adapter._wal.append
            calls = 0

            def fail_second_append(record):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("simulated receipt fsync failure")
                return original_append(record)

            adapter._wal.append = fail_second_append  # type: ignore[method-assign]
            mcp = CountingMCP()
            pipeline = AgenticPipeline(
                llm=DummyLLM(), mcp=mcp, max_iterations=1, search_runtime_shadow=adapter
            )
            results, _meta = pipeline._search_with_meta("receipt failure", "verify")
            self.assertEqual(results[0]["title"], "고정 작품")
            self.assertEqual(mcp.calls, 1)
            with self.assertRaisesRegex(PipelineStageRuntimeMeasurementError, "incomplete"):
                adapter.build_measurement_receipt()

    def test_pipeline_adapter_failure_after_legacy_call_does_not_duplicate_search(self) -> None:
        mcp = CountingMCP()
        pipeline = AgenticPipeline(
            llm=DummyLLM(),
            mcp=mcp,
            max_iterations=1,
            search_runtime_shadow=CallsThenFailsAdapter(),  # type: ignore[arg-type]
        )
        results, _meta = pipeline._search_with_meta("one call", "verify")
        self.assertEqual(results[0]["title"], "고정 작품")
        self.assertEqual(mcp.calls, 1)

    def test_active_configuration_requires_explicit_dependencies_and_bounded_waits(self) -> None:
        with self.assertRaises(PipelineStageRuntimeAdapterError):
            PipelineSearchRuntimeShadowAdapter(
                config=PipelineSearchRuntimeShadowConfig(
                    enabled=True,
                    provider="mcp",
                    model="mcp_search",
                    limiter=StageLimiterConfig(rate_per_second=1.0, burst=1, max_wait_ms=30_001),
                    cache_ttl_seconds=1.0,
                    follower_timeout_ms=1,
                    lease_timeout_ms=1,
                )
            )
        with self.assertRaisesRegex(PipelineStageRuntimeAdapterError, "explicit binding"):
            PipelineSearchRuntimeShadowAdapter(
                config=PipelineSearchRuntimeShadowConfig(
                    enabled=True,
                    provider="mcp",
                    model="mcp_search",
                    limiter=StageLimiterConfig(rate_per_second=1.0, burst=1, max_wait_ms=1),
                    cache_ttl_seconds=1.0,
                    follower_timeout_ms=1,
                    lease_timeout_ms=1,
                )
            )


if __name__ == "__main__":
    unittest.main()
