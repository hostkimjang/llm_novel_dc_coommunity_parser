from __future__ import annotations

"""Explicitly injected, no-write stage-budget observer for AgenticPipeline.

The observer is intentionally separate from limiter/cache/singleflight control:
it only captures hash-only search-stage evidence after the existing pipeline
path completes.  No environment variable creates it and observer failures are
handled by the caller as non-interfering diagnostics.
"""

from dataclasses import asdict
import hashlib
import json
import time
from typing import Any, Mapping

from .stage_budget import StageBudgetBinding, StageBudgetEvent, build_shadow_stage_budget_receipt


class PipelineStageShadowError(ValueError):
    pass


def _sha(value: Any) -> str:
    try:
        raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise PipelineStageShadowError("stage shadow value must be canonical JSON") from exc
    return hashlib.sha256(raw).hexdigest()


class PipelineSearchStageShadow:
    """In-memory, artifact-bound search observer; it never controls search."""

    SCHEMA = "pipeline_search_stage_shadow_v1"

    def __init__(self, binding: StageBudgetBinding) -> None:
        binding.validate(verify_bytes=True)
        self.binding = binding
        # Keep the stage namespace cryptographically tied to the exact scope
        # artifact.  Raw scope labels are deliberately not accepted here.
        self.publication_scope_id = binding.publication_scope.sha256
        self._events: list[StageBudgetEvent] = []
        self._limiter_config_sha256 = _sha({"mode": "OBSERVE_ONLY", "limiter": "NOT_WIRED", "singleflight": "NOT_WIRED"})

    @property
    def events(self) -> tuple[StageBudgetEvent, ...]:
        return tuple(self._events)

    def observe_search(self, *, query: str, purpose: str, results: list[dict[str, Any]], search_meta: Mapping[str, Any], elapsed_ms: int) -> None:
        if not isinstance(query, str) or not isinstance(purpose, str) or not isinstance(results, list) or not isinstance(search_meta, Mapping):
            raise PipelineStageShadowError("search stage shadow input shape mismatch")
        if isinstance(elapsed_ms, bool) or not isinstance(elapsed_ms, int) or elapsed_ms < 0:
            raise PipelineStageShadowError("search stage elapsed_ms must be non-negative integer")
        input_sha = _sha({"query": query, "purpose": purpose})
        namespace_sha = _sha({"run_spec_sha256": self.binding.run_spec.sha256, "publication_scope_id": self.publication_scope_id, "input_sha256": input_sha, "provider": "mcp", "model": "mcp_search", "prompt_sha256": input_sha})
        from_cache = bool(search_meta.get("from_cache"))
        error_status = str(search_meta.get("error_status") or "NONE")
        outcome = "FAILURE" if error_status == "ERROR" else ("TIMEOUT" if error_status == "SKIPPED" else "SUCCESS")
        response_sha = _sha(results) if from_cache else None
        logical_call_sha = _sha({"schema_version": self.SCHEMA, "run_spec_artifact_sha256": self.binding.run_spec.sha256, "attempt_artifact_sha256": self.binding.attempt.sha256, "decision_ledger_artifact_sha256": self.binding.decision_ledger.sha256, "publication_scope_id": self.publication_scope_id, "input_sha256": input_sha, "stage": "search", "provider": "mcp"})
        event = StageBudgetEvent(
            stage="search", provider="mcp", outcome=outcome,
            retries=max(0, int(search_meta.get("retry_count") or 0)),
            cache_source="LOCAL" if from_cache else "NONE", wait_ms=elapsed_ms,
            inflight_deduped=from_cache, limiter_outcome="NOT_WIRED",
            logical_call_sha256=logical_call_sha, limiter_config_sha256=self._limiter_config_sha256,
            deadline_ms=0, cache_namespace_sha256=namespace_sha,
            cache_response_sha256=response_sha, singleflight_role="NONE", execution_scope="OBJECT_LOCAL",
        )
        event.validate(); self._events.append(event)

    def build_receipt(self) -> dict[str, Any]:
        """Build a caller-owned no-write receipt from current observed events."""
        return build_shadow_stage_budget_receipt(self.binding, self._events, verify_artifacts=True)

    def summary(self) -> dict[str, Any]:
        return {"schema_version": self.SCHEMA, "mode": "OBSERVE_ONLY_NOT_RUNTIME_CONTROL", "event_count": len(self._events), "events": [asdict(event) for event in self._events]}
