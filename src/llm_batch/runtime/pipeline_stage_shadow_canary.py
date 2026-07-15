from __future__ import annotations

"""Replay-only, no-write canary proving AgenticPipeline shadow observation.

The input is a local MCP response replay, never a live endpoint.  The reader
replays the same input in memory and compares hash-only stage events with the
bound StageBudget canary, so an event file alone cannot claim pipeline wiring.
"""

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import tempfile
from typing import Any, Mapping

from ..agentic_pipeline import AgenticPipeline
from .pipeline_stage_shadow import PipelineSearchStageShadow
from .stage_budget import ArtifactRef, StageBudgetBinding
from .stage_budget_canary import StageBudgetCanaryError, build_shadow_canary, read_shadow_canary


SCHEMA = "pipeline_stage_shadow_canary_v1"
INPUT_SCHEMA = "pipeline_stage_shadow_replay_input_v1"


class PipelineStageShadowCanaryError(ValueError):
    pass


def _bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _sha(value: Any) -> str:
    return hashlib.sha256(_bytes(value)).hexdigest()


def _ref(value: Mapping[str, Any]) -> ArtifactRef:
    try: return ArtifactRef(**dict(value))
    except (TypeError, ValueError) as exc: raise PipelineStageShadowCanaryError("invalid artifact reference") from exc


def _binding(value: Mapping[str, Any]) -> StageBudgetBinding:
    try: return StageBudgetBinding(**{name: _ref(value[name]) for name in ("run_spec", "publication_scope", "attempt", "decision_ledger")})
    except (KeyError, TypeError) as exc: raise PipelineStageShadowCanaryError("invalid stage binding") from exc


def _input(path: Path) -> list[dict[str, Any]]:
    try: value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc: raise PipelineStageShadowCanaryError("replay input JSON is required") from exc
    if not isinstance(value, dict) or set(value) != {"schema_version", "queries"} or value.get("schema_version") != INPUT_SCHEMA or not isinstance(value.get("queries"), list):
        raise PipelineStageShadowCanaryError("replay input schema mismatch")
    rows: list[dict[str, Any]] = []; seen: set[tuple[str, str]] = set()
    for item in value["queries"]:
        if not isinstance(item, dict) or set(item) != {"query", "purpose", "response"} or not isinstance(item["query"], str) or not item["query"].strip() or not isinstance(item["purpose"], str) or not isinstance(item["response"], dict):
            raise PipelineStageShadowCanaryError("replay query schema mismatch")
        key = (item["query"], item["purpose"])
        if key in seen: raise PipelineStageShadowCanaryError("replay query keys must be unique")
        seen.add(key); _bytes(item["response"]); rows.append(dict(item))
    if not rows: raise PipelineStageShadowCanaryError("replay input requires at least one query")
    return rows


class _ReplayMCP:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._responses = {(item["query"], item["purpose"]): item["response"] for item in rows}
        self.calls = 0

    def search(self, query: str, purpose: str = "") -> dict[str, Any]:
        try: value = self._responses[(query, purpose)]
        except KeyError as exc: raise PipelineStageShadowCanaryError("pipeline requested an unregistered replay query") from exc
        self.calls += 1
        return json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))


class _NoopLLM:
    pass


def _events(binding: StageBudgetBinding, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    shadow = PipelineSearchStageShadow(binding)
    # AgenticPipeline creates its output directory in __init__.  Keep that
    # unavoidable constructor side effect in an OS temporary sandbox, never
    # in CWD/out or the supplied canonical artifact directory.
    with tempfile.TemporaryDirectory(prefix="pipeline-stage-shadow-") as sandbox:
        pipeline = AgenticPipeline(llm=_NoopLLM(), mcp=_ReplayMCP(rows), output_dir=Path(sandbox), max_iterations=1, search_stage_shadow=shadow)
        for item in rows:
            pipeline._search_with_meta(item["query"], item["purpose"])
    return [asdict(event) for event in shadow.events]


def build(*, output_dir: Path, run_spec: Path, scope: Path, attempt: Path, ledger: Path, replay_input: Path, receipt_writer: callable) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    binding = StageBudgetBinding(*(ArtifactRef.snapshot(path) for path in (run_spec, scope, attempt, ledger)))
    rows = _input(replay_input); events = _events(binding, rows)
    events_path = output_dir / "pipeline_stage_shadow_events.json"; receipt_writer(events_path, events)
    stage_manifest = build_shadow_canary(binding=binding, events_path=events_path, receipt_path=output_dir / "stage_budget_receipt.json", receipt_writer=receipt_writer)
    stage_manifest_path = output_dir / "stage_budget_shadow_canary.json"; receipt_writer(stage_manifest_path, stage_manifest)
    material = {
        "schema_version": SCHEMA,
        "mode": "REPLAY_ONLY_PIPELINE_SHADOW_NO_RUNTIME",
        "runtime_started": False,
        "writes_to_production": False,
        "active_production_interaction": "NONE",
        "pipeline_invoked": True,
        "replay_input": ArtifactRef.snapshot(replay_input).__dict__,
        "stage_budget_canary": ArtifactRef.snapshot(stage_manifest_path).__dict__,
        "event_count": len(events),
        "gate": "GO_PIPELINE_STAGE_SHADOW_REPLAY_ONLY",
    }
    return {**material, "canary_sha256": _sha(material)}


def read(value: Mapping[str, Any], *, verify_artifacts: bool = True) -> dict[str, Any]:
    required = {"schema_version", "mode", "runtime_started", "writes_to_production", "active_production_interaction", "pipeline_invoked", "replay_input", "stage_budget_canary", "event_count", "gate", "canary_sha256"}
    if not isinstance(value, Mapping) or set(value) != required or value.get("schema_version") != SCHEMA or value.get("mode") != "REPLAY_ONLY_PIPELINE_SHADOW_NO_RUNTIME" or value.get("runtime_started") is not False or value.get("writes_to_production") is not False or value.get("active_production_interaction") != "NONE" or value.get("pipeline_invoked") is not True or value.get("gate") != "GO_PIPELINE_STAGE_SHADOW_REPLAY_ONLY":
        raise PipelineStageShadowCanaryError("pipeline canary schema/gate mismatch")
    material = {key: value[key] for key in required if key != "canary_sha256"}
    if value.get("canary_sha256") != _sha(material): raise PipelineStageShadowCanaryError("pipeline canary self-hash mismatch")
    replay_ref = _ref(value["replay_input"]); stage_ref = _ref(value["stage_budget_canary"])
    try:
        replay_ref.validate(verify_bytes=verify_artifacts); stage_ref.validate(verify_bytes=verify_artifacts)
        rows = _input(Path(replay_ref.path)); stage_value = json.loads(Path(stage_ref.path).read_text(encoding="utf-8")); stage_readback = read_shadow_canary(stage_value, verify_artifacts=verify_artifacts)
        binding = _binding(stage_value["binding"]); expected_events = _events(binding, rows)
        events_ref = _ref(stage_value["events"]["artifact"]); events_ref.validate(verify_bytes=verify_artifacts)
        events = json.loads(Path(events_ref.path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, StageBudgetCanaryError) as exc:
        raise PipelineStageShadowCanaryError(str(exc)) from exc
    if not isinstance(value["event_count"], int) or value["event_count"] != len(rows) or events != expected_events or stage_readback.get("event_count") != len(expected_events):
        raise PipelineStageShadowCanaryError("pipeline replay/event binding mismatch")
    return {"schema_version": SCHEMA, "gate": value["gate"], "runtime_started": False, "writes_to_production": False, "event_count": len(expected_events), "independent_readback": "GO_PIPELINE_STAGE_SHADOW_REPLAY"}
