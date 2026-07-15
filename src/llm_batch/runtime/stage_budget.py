from __future__ import annotations

"""Shadow-only, bound stage/provider budget receipts and independent reader."""

from collections import defaultdict
from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping


SCHEMA = "pipeline_stage_budget_snapshot_v2"
_REF_NAMES = ("run_spec", "publication_scope", "attempt", "decision_ledger")


class StageBudgetError(ValueError):
    pass


def _canonical(value: Any) -> Any:
    if isinstance(value, Mapping): return {str(key): _canonical(item) for key, item in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (list, tuple)): return [_canonical(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value): raise StageBudgetError("non-finite value is forbidden")
    if value is None or isinstance(value, (str, int, float, bool)): return value
    raise StageBudgetError(f"unsupported value: {type(value).__name__}")


def _bytes(value: Any) -> bytes:
    return json.dumps(_canonical(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _sha(value: Any) -> str: return hashlib.sha256(_bytes(value)).hexdigest()


@dataclass(frozen=True)
class ArtifactRef:
    path: str
    bytes: int
    sha256: str

    @classmethod
    def snapshot(cls, path: str | Path) -> "ArtifactRef":
        target = Path(path).resolve()
        raw = target.read_bytes()
        return cls(str(target), len(raw), hashlib.sha256(raw).hexdigest())

    def validate(self, *, verify_bytes: bool = True) -> None:
        if not self.path or self.bytes < 0 or len(self.sha256) != 64 or any(ch not in "0123456789abcdef" for ch in self.sha256):
            raise StageBudgetError("artifact reference shape mismatch")
        if verify_bytes:
            current = type(self).snapshot(self.path)
            if current != self: raise StageBudgetError(f"artifact bytes mismatch: {self.path}")


@dataclass(frozen=True)
class StageBudgetBinding:
    run_spec: ArtifactRef
    publication_scope: ArtifactRef
    attempt: ArtifactRef
    decision_ledger: ArtifactRef

    def validate(self, *, verify_bytes: bool = True) -> None:
        for value in self.__dict__.values(): value.validate(verify_bytes=verify_bytes)

    def to_dict(self) -> Dict[str, Any]: return {name: asdict(getattr(self, name)) for name in _REF_NAMES}


@dataclass(frozen=True)
class StageBudgetEvent:
    stage: str
    provider: str
    outcome: str
    retries: int = 0
    cache_source: str = "NONE"
    wait_ms: int = 0
    inflight_deduped: bool = False
    limiter_outcome: str = "NOT_WIRED"
    logical_call_sha256: str | None = None
    limiter_config_sha256: str | None = None
    deadline_ms: int | None = None
    cache_namespace_sha256: str | None = None
    cache_response_sha256: str | None = None
    singleflight_role: str = "NOT_WIRED"
    execution_scope: str = "NOT_WIRED"

    def validate(self) -> None:
        if not self.stage.strip() or not self.provider.strip(): raise StageBudgetError("stage and provider are required")
        if self.outcome not in {"SUCCESS", "FAILURE", "DENIED", "TIMEOUT"}: raise StageBudgetError("invalid stage budget outcome")
        if isinstance(self.retries, bool) or isinstance(self.wait_ms, bool) or not isinstance(self.retries, int) or not isinstance(self.wait_ms, int) or self.retries < 0 or self.wait_ms < 0: raise StageBudgetError("retries and wait_ms must be non-negative integers")
        if self.cache_source not in {"NONE", "LOCAL", "SHARED", "DEGRADED_EXCLUDED"}: raise StageBudgetError("invalid cache_source")
        if self.limiter_outcome not in {"NOT_WIRED", "ACQUIRED", "WAITED", "DENIED", "UNLIMITED"}: raise StageBudgetError("invalid limiter_outcome")
        if self.singleflight_role not in {"NOT_WIRED", "NONE", "LEADER", "FOLLOWER", "CACHE"}: raise StageBudgetError("invalid singleflight_role")
        if self.execution_scope not in {"NOT_WIRED", "OBJECT_LOCAL", "PROCESS_LOCAL_THREADS_ONLY", "CROSS_PROCESS_FILE_SHARED_RESULT_SHADOW_ONLY"}: raise StageBudgetError("invalid execution_scope")
        if self.deadline_ms is not None and (isinstance(self.deadline_ms, bool) or not isinstance(self.deadline_ms, int) or self.deadline_ms < 0): raise StageBudgetError("deadline_ms must be a non-negative integer or null")
        for name in ("logical_call_sha256", "limiter_config_sha256", "cache_namespace_sha256", "cache_response_sha256"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, str) or len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value)):
                raise StageBudgetError(f"invalid {name}")


def validate_canary_event_provenance(rows: Iterable[StageBudgetEvent]) -> None:
    """Dedicated canaries require the full provenance set, unlike legacy schema-only receipts."""
    for event in rows:
        if event.logical_call_sha256 is None or event.limiter_config_sha256 is None or event.deadline_ms is None or event.cache_namespace_sha256 is None:
            raise StageBudgetError("canary event provenance is incomplete")
        if event.singleflight_role == "NOT_WIRED" or event.execution_scope == "NOT_WIRED":
            raise StageBudgetError("canary singleflight/execution scope is incomplete")
        if event.cache_source in {"LOCAL", "SHARED"} and event.cache_response_sha256 is None:
            raise StageBudgetError("cache hit provenance is incomplete")
        if event.cache_source in {"NONE", "DEGRADED_EXCLUDED"} and event.cache_response_sha256 is not None:
            raise StageBudgetError("cache miss/exclusion must not carry response SHA")


def _events(values: Iterable[StageBudgetEvent | Mapping[str, Any]]) -> list[StageBudgetEvent]:
    result = []
    for value in values:
        event = value if isinstance(value, StageBudgetEvent) else StageBudgetEvent(**dict(value))
        event.validate(); result.append(event)
    return result


def _aggregate(rows: Iterable[StageBudgetEvent]) -> list[Dict[str, Any]]:
    groups: dict[tuple[str, str], dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for event in rows:
        bucket = groups[(event.stage, event.provider)]; bucket["calls"] += 1; bucket["retries"] += event.retries; bucket["wait_ms"] += event.wait_ms
        bucket[f"outcome_{event.outcome.lower()}"] += 1; bucket[f"cache_{event.cache_source.lower()}"] += 1; bucket["inflight_deduped"] += int(event.inflight_deduped); bucket[f"limiter_{event.limiter_outcome.lower()}"] += 1
    return [{"stage": stage, "provider": provider, **dict(bucket)} for (stage, provider), bucket in sorted(groups.items())]


def build_shadow_stage_budget_receipt(binding: StageBudgetBinding, events: Iterable[StageBudgetEvent | Mapping[str, Any]], *, verify_artifacts: bool = True) -> Dict[str, Any]:
    """Build a no-write/runtime-free receipt bound to four exact artifacts."""
    binding.validate(verify_bytes=verify_artifacts); rows = _events(events)
    material = {"schema_version": SCHEMA, "mode": "SHADOW_ONLY_NOT_WIRED", "binding": binding.to_dict(), "events": [asdict(item) for item in rows], "event_count": len(rows), "stage_provider": _aggregate(rows), "gate": "GO_BOUND_SCHEMA_ONLY_NO_ACTIVE_PRODUCTION_WIRING"}
    return {**material, "snapshot_sha256": _sha(material)}


def read_stage_budget_receipt(value: Mapping[str, Any], *, verify_artifacts: bool = True) -> Dict[str, Any]:
    """Independently re-read self hash, binding bytes, events and aggregates."""
    if not isinstance(value, Mapping): raise StageBudgetError("receipt must be object")
    required = {"schema_version", "mode", "binding", "events", "event_count", "stage_provider", "gate", "snapshot_sha256"}
    if set(value) != required or value.get("schema_version") != SCHEMA or value.get("mode") != "SHADOW_ONLY_NOT_WIRED": raise StageBudgetError("receipt schema mismatch")
    binding_value = value.get("binding")
    if not isinstance(binding_value, Mapping) or set(binding_value) != set(_REF_NAMES): raise StageBudgetError("binding fields mismatch")
    try: binding = StageBudgetBinding(**{name: ArtifactRef(**dict(binding_value[name])) for name in _REF_NAMES})
    except (TypeError, ValueError) as exc: raise StageBudgetError("invalid artifact binding") from exc
    binding.validate(verify_bytes=verify_artifacts)
    raw_events = value.get("events")
    if not isinstance(raw_events, list): raise StageBudgetError("events must be list")
    rows = _events(raw_events)
    if value.get("event_count") != len(rows) or value.get("stage_provider") != _aggregate(rows): raise StageBudgetError("receipt count or aggregate mismatch")
    material = {key: value[key] for key in required if key != "snapshot_sha256"}
    if value.get("snapshot_sha256") != _sha(material): raise StageBudgetError("receipt self-hash mismatch")
    return {"schema_version": SCHEMA, "mode": value["mode"], "binding": binding.to_dict(), "event_count": len(rows), "stage_provider": _aggregate(rows), "gate": value["gate"], "independent_readback": "GO_BOUND_SCHEMA_ONLY"}


def build_stage_budget_snapshot(events: Iterable[StageBudgetEvent | Mapping[str, Any]]) -> Dict[str, Any]:
    """Legacy unbound helper retained only for existing synthetic consumers."""
    rows = _events(events)
    return {"schema_version": "pipeline_stage_budget_snapshot_v1", "mode": "READ_ONLY_NOT_WIRED", "event_count": len(rows), "stage_provider": _aggregate(rows), "gate": "GO_SCHEMA_ONLY_NO_ACTIVE_PRODUCTION_WIRING"}
