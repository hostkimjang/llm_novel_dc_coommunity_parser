from __future__ import annotations

"""Dedicated, no-runtime StageBudget shadow-canary manifest and reader."""

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping

from .stage_budget import ArtifactRef, StageBudgetBinding, StageBudgetError, _events, build_shadow_stage_budget_receipt, read_stage_budget_receipt, validate_canary_event_provenance


SCHEMA = "stage_budget_shadow_canary_v1"


class StageBudgetCanaryError(ValueError):
    pass


def _canonical(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _canonical(item) for key, item in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        raise StageBudgetCanaryError("non-finite value is forbidden")
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise StageBudgetCanaryError(f"unsupported value: {type(value).__name__}")


def _bytes(value: Any) -> bytes:
    return json.dumps(_canonical(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _sha(value: Any) -> str:
    return hashlib.sha256(_bytes(value)).hexdigest()


def _ref(value: Mapping[str, Any]) -> ArtifactRef:
    try:
        return ArtifactRef(**dict(value))
    except (TypeError, ValueError) as exc:
        raise StageBudgetCanaryError("invalid artifact reference") from exc


def build_shadow_canary(*, binding: StageBudgetBinding, events_path: Path, receipt_path: Path, receipt_writer: callable) -> dict[str, Any]:
    """Build receipt through the supplied atomic writer, then bind it in a canary manifest."""
    try:
        events = json.loads(events_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StageBudgetCanaryError("events JSON list is required") from exc
    if not isinstance(events, list):
        raise StageBudgetCanaryError("events JSON list is required")
    try:
        validate_canary_event_provenance(_events(events))
    except StageBudgetError as exc:
        raise StageBudgetCanaryError(str(exc)) from exc
    binding.validate(verify_bytes=True)
    receipt = build_shadow_stage_budget_receipt(binding, events, verify_artifacts=True)
    receipt_writer(receipt_path, receipt)
    receipt_ref = ArtifactRef.snapshot(receipt_path)
    events_ref = ArtifactRef.snapshot(events_path)
    material = {
        "schema_version": SCHEMA,
        "mode": "SHADOW_ONLY_DEDICATED_CANARY_NO_RUNTIME",
        "runtime_started": False,
        "writes_to_production": False,
        "active_production_interaction": "NONE",
        "binding": binding.to_dict(),
        "events": {"artifact": events_ref.__dict__, "count": len(events)},
        "receipt": receipt_ref.__dict__,
        "gate": "GO_STAGE_BUDGET_SHADOW_CANARY_ONLY",
    }
    return {**material, "canary_sha256": _sha(material)}


def read_shadow_canary(value: Mapping[str, Any], *, verify_artifacts: bool = True) -> dict[str, Any]:
    required = {"schema_version", "mode", "runtime_started", "writes_to_production", "active_production_interaction", "binding", "events", "receipt", "gate", "canary_sha256"}
    if not isinstance(value, Mapping) or set(value) != required:
        raise StageBudgetCanaryError("canary schema fields mismatch")
    if value.get("schema_version") != SCHEMA or value.get("mode") != "SHADOW_ONLY_DEDICATED_CANARY_NO_RUNTIME" or value.get("runtime_started") is not False or value.get("writes_to_production") is not False or value.get("active_production_interaction") != "NONE" or value.get("gate") != "GO_STAGE_BUDGET_SHADOW_CANARY_ONLY":
        raise StageBudgetCanaryError("canary mode/gate mismatch")
    material = {key: value[key] for key in required if key != "canary_sha256"}
    if value.get("canary_sha256") != _sha(material):
        raise StageBudgetCanaryError("canary self-hash mismatch")
    try:
        binding = StageBudgetBinding(**{name: _ref(value["binding"][name]) for name in ("run_spec", "publication_scope", "attempt", "decision_ledger")})
        events_ref = _ref(value["events"]["artifact"])
        receipt_ref = _ref(value["receipt"])
    except (KeyError, TypeError) as exc:
        raise StageBudgetCanaryError("canary binding shape mismatch") from exc
    if not isinstance(value["events"].get("count"), int) or value["events"]["count"] < 0:
        raise StageBudgetCanaryError("canary event count mismatch")
    try:
        binding.validate(verify_bytes=verify_artifacts); events_ref.validate(verify_bytes=verify_artifacts); receipt_ref.validate(verify_bytes=verify_artifacts)
        events = json.loads(Path(events_ref.path).read_text(encoding="utf-8"))
        receipt = json.loads(Path(receipt_ref.path).read_text(encoding="utf-8"))
        receipt_readback = read_stage_budget_receipt(receipt, verify_artifacts=verify_artifacts)
    except (OSError, json.JSONDecodeError, StageBudgetError) as exc:
        raise StageBudgetCanaryError(str(exc)) from exc
    expected_receipt = build_shadow_stage_budget_receipt(binding, events, verify_artifacts=verify_artifacts)
    if not isinstance(events, list) or len(events) != value["events"]["count"] or receipt != expected_receipt or receipt_readback.get("binding") != binding.to_dict():
        raise StageBudgetCanaryError("canary receipt/event binding mismatch")
    return {"schema_version": SCHEMA, "gate": value["gate"], "runtime_started": False, "writes_to_production": False, "event_count": len(events), "independent_readback": "GO_STAGE_BUDGET_SHADOW_CANARY"}
