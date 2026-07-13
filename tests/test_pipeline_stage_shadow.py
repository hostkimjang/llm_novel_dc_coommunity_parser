from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from llm_batch.agentic_pipeline import AgenticPipeline
from llm_batch.pipeline_stage_shadow import PipelineSearchStageShadow
from llm_batch.stage_budget import ArtifactRef, StageBudgetBinding, read_stage_budget_receipt


class DummyLLM:
    pass


class FakeMCP:
    def __init__(self) -> None:
        self.calls = 0

    def search(self, query: str, purpose: str = "") -> dict:
        self.calls += 1
        return {"results": [{"title": query, "url": "https://example.test/work", "content": purpose}], "total": 1, "raw_total": 1, "retry_count": 0}


class ErrorMCP:
    def search(self, _query: str, purpose: str = "") -> dict:
        raise RuntimeError(f"mcp error: {purpose}")


class FailingObserver:
    def observe_search(self, **_kwargs) -> None:
        raise RuntimeError("observer failure")


class MutatingObserver:
    def observe_search(self, *, results, search_meta, **_kwargs) -> None:
        results.clear(); search_meta.clear()


class PipelineStageShadowTests(unittest.TestCase):
    def _binding(self, root: Path) -> StageBudgetBinding:
        refs = []
        for name in ("run_spec", "scope", "attempt", "ledger"):
            path = root / f"{name}.json"; path.write_text(json.dumps({"name": name}), encoding="utf-8"); refs.append(ArtifactRef.snapshot(path))
        return StageBudgetBinding(*refs)

    def test_explicit_observer_preserves_search_output_and_builds_bound_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); mcp = FakeMCP(); shadow = PipelineSearchStageShadow(self._binding(root))
            pipeline = AgenticPipeline(llm=DummyLLM(), mcp=mcp, max_iterations=1, search_stage_shadow=shadow)
            first, first_meta = pipeline._search_with_meta("query one", "verify")
            second, second_meta = pipeline._search_with_meta("query one", "verify")
            self.assertEqual((first, first_meta["from_cache"], second, second_meta["from_cache"], mcp.calls), (second, False, first, True, 1))
            self.assertEqual(len(shadow.events), 2); self.assertEqual((shadow.events[0].cache_source, shadow.events[1].cache_source), ("NONE", "LOCAL"))
            receipt = shadow.build_receipt(); self.assertEqual(read_stage_budget_receipt(receipt)["event_count"], 2)
            self.assertNotIn("query one", json.dumps(shadow.summary(), ensure_ascii=False))

    def test_no_observer_and_observer_failure_do_not_change_legacy_search_result(self) -> None:
        baseline = AgenticPipeline(llm=DummyLLM(), mcp=FakeMCP(), max_iterations=1)
        failed = AgenticPipeline(llm=DummyLLM(), mcp=FakeMCP(), max_iterations=1, search_stage_shadow=FailingObserver())
        self.assertEqual(baseline._search_with_meta("same", "purpose"), failed._search_with_meta("same", "purpose"))

    def test_non_throwing_observer_cannot_mutate_returned_or_cached_search_state(self) -> None:
        pipeline = AgenticPipeline(llm=DummyLLM(), mcp=FakeMCP(), max_iterations=1, search_stage_shadow=MutatingObserver())
        first, first_meta = pipeline._search_with_meta("same", "purpose")
        second, second_meta = pipeline._search_with_meta("same", "purpose")
        self.assertEqual((first[0]["title"], first_meta["from_cache"], second[0]["title"], second_meta["from_cache"]), ("same", False, "same", True))

    def test_observer_failure_does_not_change_mcp_error_fail_close_result(self) -> None:
        baseline = AgenticPipeline(llm=DummyLLM(), mcp=ErrorMCP(), max_iterations=1)
        failed = AgenticPipeline(llm=DummyLLM(), mcp=ErrorMCP(), max_iterations=1, search_stage_shadow=FailingObserver())
        self.assertEqual(baseline._search_with_meta("same", "purpose"), failed._search_with_meta("same", "purpose"))

    def test_scope_namespace_is_derived_from_exact_scope_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            binding = self._binding(Path(directory)); shadow = PipelineSearchStageShadow(binding)
            self.assertEqual(shadow.publication_scope_id, binding.publication_scope.sha256)
            Path(binding.publication_scope.path).write_text("changed", encoding="utf-8")
            with self.assertRaises(Exception):
                shadow.build_receipt()


if __name__ == "__main__":
    unittest.main()
