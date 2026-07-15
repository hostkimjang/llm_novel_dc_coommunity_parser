from __future__ import annotations

"""Explicit-injection search runtime shadow adapter.

This is deliberately not activated from environment variables or global state.
When enabled by a caller it composes the existing process-local limiter with
the filesystem shared-result singleflight contract.  Runtime adapter failures
fall open to the legacy operation, while the durable measurement gate retains
and fails closed on every incomplete, degraded, denied, or fallback attempt.

Raw prompts and queries are transient inputs only.  Durable records contain
their canonical SHA-256 identities and never their text.
"""

from copy import deepcopy
from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
import re
import threading
import time
from typing import Any, Callable, Mapping, TypeVar
import unicodedata
from urllib.parse import unquote_plus
import uuid

from ..ledger.framed_wal import FramedWAL
from .local_stage_gate import LimiterReceipt, StageLimiterConfig, StageLimiterRegistry
from .shared_result_singleflight import FileSharedResultSingleflight, SharedResultSingleflightReceipt
from .shared_cache_contract import CacheNamespace
from .local_stage_gate import StageSingleflightKey
from .stage_budget import ArtifactRef, StageBudgetBinding, StageBudgetEvent


T = TypeVar("T")
_SHA_RE = re.compile(r"^[0-9a-f]{64}$")
_MAX_BOUNDED_WAIT_MS = 30_000
_RECORD_SCHEMA = "pipeline_search_runtime_shadow_record_v1"
_MEASUREMENT_SCHEMA = "pipeline_search_runtime_shadow_measurement_v1"
_CACHE_VALUE_SCHEMA = "pipeline_search_runtime_shadow_cache_value_v1"


class PipelineStageRuntimeAdapterError(ValueError):
    pass


class PipelineStageRuntimeMeasurementError(PipelineStageRuntimeAdapterError):
    pass


def _canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise PipelineStageRuntimeAdapterError("runtime shadow value must be canonical JSON") from exc


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _require_sha(name: str, value: Any) -> str:
    if not isinstance(value, str) or _SHA_RE.fullmatch(value) is None:
        raise PipelineStageRuntimeMeasurementError(f"invalid {name}")
    return value


def _request_text_forms(value: str) -> tuple[str, str]:
    decoded = unquote_plus(unquote_plus(str(value or "")))
    normalized = unicodedata.normalize("NFKC", decoded).casefold()
    spaced = " ".join(normalized.split())
    compact = "".join(character for character in spaced if character.isalnum())
    return spaced, compact


@dataclass(frozen=True)
class PipelineSearchRuntimeShadowConfig:
    """All active settings must be supplied directly by the caller."""

    enabled: bool = False
    provider: str = ""
    model: str = ""
    limiter: StageLimiterConfig | None = None
    cache_ttl_seconds: float = 0.0
    follower_timeout_ms: int = 0
    lease_timeout_ms: int = 0

    def validate(self) -> None:
        if not isinstance(self.enabled, bool):
            raise PipelineStageRuntimeAdapterError("enabled must be boolean")
        if not self.enabled:
            return
        if not all(isinstance(value, str) and value.strip() for value in (self.provider, self.model)):
            raise PipelineStageRuntimeAdapterError("enabled runtime shadow requires explicit provider and model")
        if self.limiter is None:
            raise PipelineStageRuntimeAdapterError("enabled runtime shadow requires explicit limiter config")
        self.limiter.validate()
        if self.limiter.disabled:
            raise PipelineStageRuntimeAdapterError("enabled runtime shadow cannot use a disabled limiter")
        if (
            isinstance(self.cache_ttl_seconds, bool)
            or not isinstance(self.cache_ttl_seconds, (int, float))
            or not math.isfinite(float(self.cache_ttl_seconds))
            or float(self.cache_ttl_seconds) <= 0
        ):
            raise PipelineStageRuntimeAdapterError("cache TTL must be a finite positive number")
        for name, value, allow_zero in (
            ("follower_timeout_ms", self.follower_timeout_ms, True),
            ("lease_timeout_ms", self.lease_timeout_ms, False),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value < (0 if allow_zero else 1)
                or value > _MAX_BOUNDED_WAIT_MS
            ):
                raise PipelineStageRuntimeAdapterError(f"{name} must be explicitly bounded to {_MAX_BOUNDED_WAIT_MS}ms")
        if self.limiter.max_wait_ms > _MAX_BOUNDED_WAIT_MS:
            raise PipelineStageRuntimeAdapterError(f"limiter max_wait_ms must be bounded to {_MAX_BOUNDED_WAIT_MS}ms")


def _completion_semantics_valid(
    status: str,
    fallback: Any,
    error_class: Any,
    event: StageBudgetEvent,
) -> bool:
    if not isinstance(fallback, bool) or (error_class is not None and not isinstance(error_class, str)):
        return False
    return bool(
        {
            "SHARED_RESULT": (
                not fallback
                and error_class is None
                and event.outcome == "SUCCESS"
                and event.cache_source == "SHARED"
                and event.cache_response_sha256 is not None
                and event.singleflight_role in {"LEADER", "FOLLOWER", "CACHE"}
                and event.limiter_outcome in {"ACQUIRED", "WAITED", "UNLIMITED"}
            ),
            "DEGRADED_EXCLUDED": (
                not fallback
                and event.outcome == "FAILURE"
                and event.cache_source == "DEGRADED_EXCLUDED"
                and event.cache_response_sha256 is None
            ),
            "RAW_QUERY_ECHO_EXCLUDED": (
                not fallback
                and event.outcome == "FAILURE"
                and event.cache_source == "NONE"
                and event.cache_response_sha256 is None
            ),
            "LIMITER_DENIED_FALLBACK": (
                fallback
                and event.outcome == "DENIED"
                and event.limiter_outcome == "DENIED"
                and event.cache_source == "NONE"
            ),
            "ADAPTER_FAILURE_FALLBACK": (
                fallback and event.outcome == "FAILURE" and event.cache_source == "NONE"
            ),
            "LEGACY_OPERATION_ERROR": (
                fallback and event.outcome == "FAILURE" and event.cache_source == "NONE"
            ),
        }.get(status, False)
    )


class _DegradedResult(Exception):
    def __init__(self, public_value: tuple[list[dict[str, Any]], dict[str, Any]]) -> None:
        super().__init__("degraded result is excluded from shared cache")
        self.public_value = public_value


class _PrivacyExcludedResult(Exception):
    def __init__(self, public_value: tuple[list[dict[str, Any]], dict[str, Any]]) -> None:
        super().__init__("shared result echoes raw request text and is excluded from storage")
        self.public_value = public_value


class PipelineSearchRuntimeShadowAdapter:
    """OFF-by-default bridge from AgenticPipeline search to stage controls."""

    def __init__(
        self,
        *,
        config: PipelineSearchRuntimeShadowConfig | None = None,
        binding: StageBudgetBinding | None = None,
        shared_result: FileSharedResultSingleflight | None = None,
        receipt_wal: FramedWAL | Path | str | None = None,
    ) -> None:
        self.config = config or PipelineSearchRuntimeShadowConfig()
        self.config.validate()
        self.enabled = self.config.enabled
        self.binding = binding
        self.shared_result = shared_result
        self._lock = threading.RLock()
        self._measurement_errors: list[str] = []
        self._wal: FramedWAL | None = None
        self._limiter: StageLimiterRegistry | None = None
        self._runtime_id_sha256: str | None = None
        self._limiter_config_sha256: str | None = None
        self._runtime_config_material: dict[str, Any] | None = None
        if not self.enabled:
            return
        if binding is None or shared_result is None or receipt_wal is None:
            raise PipelineStageRuntimeAdapterError(
                "enabled runtime shadow requires explicit binding, shared-result adapter, and receipt WAL"
            )
        binding.validate(verify_bytes=True)
        if not shared_result.enabled or not shared_result.cache.allow_write:
            raise PipelineStageRuntimeAdapterError(
                "enabled runtime shadow requires explicitly enabled shared-result and writable shadow cache"
            )
        limiter_config = self.config.limiter
        assert limiter_config is not None
        self._limiter = StageLimiterRegistry({("search", self.config.provider): limiter_config})
        self._limiter_config_sha256 = _sha(asdict(limiter_config))
        self._runtime_config_material = {
            "provider": self.config.provider,
            "model": self.config.model,
            "limiter": asdict(limiter_config),
            "limiter_config_sha256": self._limiter_config_sha256,
            "cache_ttl_seconds": float(self.config.cache_ttl_seconds),
            "follower_timeout_ms": self.config.follower_timeout_ms,
            "lease_timeout_ms": self.config.lease_timeout_ms,
            "limiter_execution_scope": "PROCESS_LOCAL_THREADS_ONLY",
            "singleflight_execution_scope": "CROSS_PROCESS_FILE_SHARED_RESULT_SHADOW_ONLY",
        }
        self._runtime_id_sha256 = _sha(
            {
                "schema_version": _RECORD_SCHEMA,
                "binding": binding.to_dict(),
                "config": self._runtime_config_material,
            }
        )
        self._wal = receipt_wal if isinstance(receipt_wal, FramedWAL) else FramedWAL(receipt_wal)
        scan = self._wal.initialize(repair_uncommitted_tail=False)
        if scan.trailing_bytes:
            raise PipelineStageRuntimeMeasurementError("runtime shadow receipt WAL has an uncommitted tail")

    @staticmethod
    def _public_value(value: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        if not isinstance(value, (tuple, list)) or len(value) != 2:
            raise PipelineStageRuntimeAdapterError("legacy search result shape mismatch")
        results, meta = value
        if not isinstance(results, list) or not all(isinstance(item, dict) for item in results) or not isinstance(meta, Mapping):
            raise PipelineStageRuntimeAdapterError("legacy search result shape mismatch")
        return deepcopy(results), deepcopy(dict(meta))

    @staticmethod
    def _is_degraded(meta: Mapping[str, Any]) -> bool:
        return bool(
            meta.get("degraded")
            or meta.get("possible_throttle")
            or meta.get("blocked")
            or meta.get("malformed_response")
            or meta.get("upstream_failure")
            or not meta.get("enumeration_finished")
            or str(meta.get("error_status") or "NONE") != "NONE"
        )

    @staticmethod
    def _cache_value(public_value: tuple[list[dict[str, Any]], dict[str, Any]]) -> dict[str, Any]:
        results, meta = public_value
        # Query text and normalized query are reconstructed from the current
        # transient request; they are never written into shared storage.
        cache_meta = {
            key: deepcopy(value)
            for key, value in meta.items()
            if key not in {"query", "query_norm", "purpose", "error"}
        }
        return {"schema_version": _CACHE_VALUE_SCHEMA, "results": deepcopy(results), "meta": cache_meta}

    @staticmethod
    def _contains_raw_request_text(value: Any, request_text: str) -> bool:
        needle_spaced, needle_compact = _request_text_forms(request_text)
        if not needle_spaced:
            return False
        if isinstance(value, str):
            candidate_spaced, candidate_compact = _request_text_forms(value)
            return needle_spaced in candidate_spaced or bool(needle_compact and needle_compact in candidate_compact)
        if isinstance(value, Mapping):
            return any(
                PipelineSearchRuntimeShadowAdapter._contains_raw_request_text(key, request_text)
                or PipelineSearchRuntimeShadowAdapter._contains_raw_request_text(item, request_text)
                for key, item in value.items()
            )
        if isinstance(value, (list, tuple)):
            return any(PipelineSearchRuntimeShadowAdapter._contains_raw_request_text(item, request_text) for item in value)
        return False

    @property
    def measurement_error_classes(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(self._measurement_errors)

    @staticmethod
    def _decode_cache_value(value: Any, *, query: str, purpose: str, cache_hit: bool) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        if not isinstance(value, Mapping) or set(value) != {"schema_version", "results", "meta"} or value.get("schema_version") != _CACHE_VALUE_SCHEMA:
            raise PipelineStageRuntimeAdapterError("shared cache payload shape mismatch")
        results = value.get("results")
        meta = value.get("meta")
        if not isinstance(results, list) or not all(isinstance(item, dict) for item in results) or not isinstance(meta, Mapping):
            raise PipelineStageRuntimeAdapterError("shared cache payload shape mismatch")
        purpose_key = str(purpose or "").strip().lower()
        query_norm = f"{purpose_key}||{query.strip().lower()}" if purpose_key else query.strip().lower()
        restored = deepcopy(dict(meta))
        restored.update({"query": query, "query_norm": query_norm, "purpose": purpose_key})
        if cache_hit:
            restored["from_cache"] = True
        return deepcopy(results), restored

    def _identity(self, *, query: str, purpose: str) -> tuple[CacheNamespace, StageSingleflightKey, dict[str, str]]:
        assert self.binding is not None
        purpose_value = str(purpose or "")
        input_sha = _sha({"query": query, "purpose": purpose_value})
        prompt_sha = _sha(
            {
                "stage": "search",
                "provider": self.config.provider,
                "model": self.config.model,
                "query": query,
                "purpose": purpose_value,
            }
        )
        scope_id = self.binding.publication_scope.sha256
        namespace = CacheNamespace(
            self.binding.run_spec.sha256,
            scope_id,
            input_sha,
            self.config.provider,
            self.config.model,
            prompt_sha,
        )
        key = StageSingleflightKey(
            self.binding.run_spec.sha256,
            scope_id,
            input_sha,
            "search",
            self.config.provider,
            self.config.model,
            prompt_sha,
        )
        logical_call_sha = _sha(
            {
                "schema_version": _RECORD_SCHEMA,
                "run_spec_sha256": self.binding.run_spec.sha256,
                "publication_scope_id": scope_id,
                "attempt_sha256": self.binding.attempt.sha256,
                "decision_ledger_sha256": self.binding.decision_ledger.sha256,
                "input_sha256": input_sha,
                "stage": "search",
                "provider": self.config.provider,
                "model": self.config.model,
                "prompt_sha256": prompt_sha,
            }
        )
        return namespace, key, {
            "input_sha256": input_sha,
            "prompt_sha256": prompt_sha,
            "logical_call_sha256": logical_call_sha,
        }

    def _record(self, record: Mapping[str, Any]) -> None:
        if self._wal is None:
            raise PipelineStageRuntimeMeasurementError("runtime shadow receipt WAL is unavailable")
        self._wal.append(record)

    def _record_failure(self, exc: BaseException) -> None:
        with self._lock:
            self._measurement_errors.append(type(exc).__name__)

    def _event(
        self,
        *,
        identity: Mapping[str, str],
        namespace_sha256: str,
        limiter: LimiterReceipt | None,
        shared: SharedResultSingleflightReceipt | None,
        outcome: str,
        cache_source: str,
        elapsed_ms: int,
        role: str,
        response_sha256: str | None = None,
    ) -> StageBudgetEvent:
        limiter_outcome = "DENIED" if limiter is None else limiter.outcome
        if limiter_outcome not in {"ACQUIRED", "WAITED", "DENIED", "UNLIMITED"}:
            limiter_outcome = "DENIED"
        event = StageBudgetEvent(
            stage="search",
            provider=self.config.provider,
            outcome=outcome,
            retries=0,
            cache_source=cache_source,
            wait_ms=max(0, elapsed_ms),
            inflight_deduped=bool(shared and shared.role == "FOLLOWER"),
            limiter_outcome=limiter_outcome,
            logical_call_sha256=identity["logical_call_sha256"],
            limiter_config_sha256=self._limiter_config_sha256,
            deadline_ms=self.config.follower_timeout_ms,
            cache_namespace_sha256=namespace_sha256,
            cache_response_sha256=response_sha256,
            singleflight_role=role,
            execution_scope="CROSS_PROCESS_FILE_SHARED_RESULT_SHADOW_ONLY",
        )
        event.validate()
        return event

    def execute(
        self,
        *,
        query: str,
        purpose: str,
        operation: Callable[[], tuple[list[dict[str, Any]], dict[str, Any]]],
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Run one search attempt, failing open only around adapter mechanics."""
        if not self.enabled:
            return operation()
        if not isinstance(query, str) or not isinstance(purpose, str) or not callable(operation):
            raise PipelineStageRuntimeAdapterError("runtime shadow search input shape mismatch")
        assert self._limiter is not None and self.shared_result is not None
        invocation_id = uuid.uuid4().hex
        try:
            assert self.binding is not None
            self.binding.validate(verify_bytes=True)
            namespace, key, identity = self._identity(query=query, purpose=purpose)
            namespace_sha = namespace.key()
        except Exception as exc:
            self._record_failure(exc)
            return operation()
        started = time.monotonic()
        start_record = {
            "schema_version": _RECORD_SCHEMA,
            "runtime_id_sha256": self._runtime_id_sha256,
            "invocation_id": invocation_id,
            "phase": "STARTED",
            "logical_call_sha256": identity["logical_call_sha256"],
            "cache_namespace_sha256": namespace_sha,
            "input_sha256": identity["input_sha256"],
            "prompt_sha256": identity["prompt_sha256"],
            "run_spec_sha256": self.binding.run_spec.sha256 if self.binding is not None else None,
            "publication_scope_id": self.binding.publication_scope.sha256 if self.binding is not None else None,
            "attempt_sha256": self.binding.attempt.sha256 if self.binding is not None else None,
            "decision_ledger_sha256": self.binding.decision_ledger.sha256 if self.binding is not None else None,
            "provider": self.config.provider,
            "model": self.config.model,
        }
        try:
            self._record(start_record)
        except Exception as exc:
            self._record_failure(exc)
            return operation()

        operation_called = False
        operation_value: tuple[list[dict[str, Any]], dict[str, Any]] | None = None
        operation_error: BaseException | None = None

        def call_legacy_once() -> tuple[list[dict[str, Any]], dict[str, Any]]:
            nonlocal operation_called, operation_value, operation_error
            if operation_called:
                if operation_error is not None:
                    raise operation_error
                assert operation_value is not None
                return deepcopy(operation_value)
            operation_called = True
            try:
                operation_value = self._public_value(operation())
                return deepcopy(operation_value)
            except BaseException as exc:
                operation_error = exc
                raise

        limiter_receipt: LimiterReceipt | None = None
        shared_receipt: SharedResultSingleflightReceipt | None = None
        event: StageBudgetEvent | None = None
        status = "ADAPTER_FAILURE_FALLBACK"
        fallback = True
        error_class: str | None = None
        result: tuple[list[dict[str, Any]], dict[str, Any]] | None = None
        propagate: BaseException | None = None
        try:
            limiter_receipt = self._limiter.acquire(stage="search", provider=self.config.provider)
            if limiter_receipt.outcome not in {"ACQUIRED", "WAITED", "UNLIMITED"}:
                result = call_legacy_once()
                status = "LIMITER_DENIED_FALLBACK"
                event = self._event(
                    identity=identity,
                    namespace_sha256=namespace_sha,
                    limiter=limiter_receipt,
                    shared=None,
                    outcome="DENIED",
                    cache_source="NONE",
                    elapsed_ms=max(0, int((time.monotonic() - started) * 1000)),
                    role="NONE",
                )
            else:
                def produce_cache_value() -> dict[str, Any]:
                    public_value = call_legacy_once()
                    if self._is_degraded(public_value[1]):
                        raise _DegradedResult(public_value)
                    cache_value = self._cache_value(public_value)
                    if self._contains_raw_request_text(cache_value, query) or self._contains_raw_request_text(cache_value, purpose):
                        raise _PrivacyExcludedResult(public_value)
                    return cache_value

                cache_value, shared_receipt = self.shared_result.run(
                    namespace,
                    key,
                    produce_cache_value,
                    ttl_seconds=float(self.config.cache_ttl_seconds),
                    follower_timeout_ms=self.config.follower_timeout_ms,
                    lease_timeout_ms=self.config.lease_timeout_ms,
                )
                cache_hit = shared_receipt.outcome in {"CACHE_HIT", "FOLLOWER_HIT"}
                if operation_value is not None:
                    result = operation_value
                else:
                    if self._contains_raw_request_text(cache_value, query) or self._contains_raw_request_text(cache_value, purpose):
                        raise PipelineStageRuntimeAdapterError("shared cache payload contains raw request text")
                    result = self._decode_cache_value(
                        cache_value,
                        query=query,
                        purpose=purpose,
                        cache_hit=cache_hit,
                    )
                    if self._is_degraded(result[1]):
                        raise PipelineStageRuntimeAdapterError("degraded shared cache payload is forbidden")
                assert result is not None
                status = "SHARED_RESULT"
                fallback = False
                role = shared_receipt.role if shared_receipt.role in {"LEADER", "FOLLOWER", "CACHE"} else "NONE"
                event = self._event(
                    identity=identity,
                    namespace_sha256=namespace_sha,
                    limiter=limiter_receipt,
                    shared=shared_receipt,
                    outcome="SUCCESS",
                    cache_source="SHARED",
                    elapsed_ms=max(0, int((time.monotonic() - started) * 1000)),
                    role=role,
                    response_sha256=shared_receipt.response_sha256,
                )
        except _DegradedResult as exc:
            result = exc.public_value
            status = "DEGRADED_EXCLUDED"
            fallback = False
            event = self._event(
                identity=identity,
                namespace_sha256=namespace_sha,
                limiter=limiter_receipt,
                shared=None,
                outcome="FAILURE",
                cache_source="DEGRADED_EXCLUDED",
                elapsed_ms=max(0, int((time.monotonic() - started) * 1000)),
                role="LEADER",
            )
        except _PrivacyExcludedResult as exc:
            result = exc.public_value
            status = "RAW_QUERY_ECHO_EXCLUDED"
            fallback = False
            event = self._event(
                identity=identity,
                namespace_sha256=namespace_sha,
                limiter=limiter_receipt,
                shared=None,
                outcome="FAILURE",
                cache_source="NONE",
                elapsed_ms=max(0, int((time.monotonic() - started) * 1000)),
                role="LEADER",
            )
        except BaseException as exc:
            error_class = type(exc).__name__
            if operation_error is exc:
                propagate = exc
                status = "LEGACY_OPERATION_ERROR"
            else:
                try:
                    result = call_legacy_once()
                except BaseException as legacy_exc:
                    propagate = legacy_exc
                    status = "LEGACY_OPERATION_ERROR"
                    error_class = type(legacy_exc).__name__
            event = self._event(
                identity=identity,
                namespace_sha256=namespace_sha,
                limiter=limiter_receipt,
                shared=getattr(exc, "receipt", None),
                outcome="FAILURE",
                cache_source="NONE",
                elapsed_ms=max(0, int((time.monotonic() - started) * 1000)),
                role="NONE",
            )
        finally:
            if event is None:
                event = self._event(
                    identity=identity,
                    namespace_sha256=namespace_sha,
                    limiter=limiter_receipt,
                    shared=shared_receipt,
                    outcome="FAILURE",
                    cache_source="NONE",
                    elapsed_ms=max(0, int((time.monotonic() - started) * 1000)),
                    role="NONE",
                )
            completion = {
                "schema_version": _RECORD_SCHEMA,
                "runtime_id_sha256": self._runtime_id_sha256,
                "invocation_id": invocation_id,
                "phase": "COMPLETED",
                "status": status,
                "fallback_to_legacy": fallback,
                "error_class": error_class,
                "event": asdict(event),
            }
            try:
                self._record(completion)
            except Exception as receipt_exc:
                self._record_failure(receipt_exc)
        if propagate is not None:
            raise propagate
        assert result is not None
        return deepcopy(result)

    def build_measurement_receipt(self) -> dict[str, Any]:
        """Re-read the WAL and derive a fail-closed measurement receipt."""
        if not self.enabled or self.binding is None or self._wal is None:
            raise PipelineStageRuntimeMeasurementError("runtime shadow measurement is OFF")
        self.binding.validate(verify_bytes=True)
        with self._lock:
            in_memory_errors = tuple(self._measurement_errors)
        scan = self._wal.scan(repair_uncommitted_tail=False)
        if scan.trailing_bytes:
            raise PipelineStageRuntimeMeasurementError("runtime shadow WAL has an uncommitted tail")
        starts: dict[str, Mapping[str, Any]] = {}
        completions: dict[str, Mapping[str, Any]] = {}
        for envelope in scan.records:
            record = envelope.get("record")
            if not isinstance(record, Mapping) or record.get("runtime_id_sha256") != self._runtime_id_sha256:
                continue
            if record.get("schema_version") != _RECORD_SCHEMA:
                raise PipelineStageRuntimeMeasurementError("runtime shadow record schema mismatch")
            invocation_id = record.get("invocation_id")
            if not isinstance(invocation_id, str) or not invocation_id:
                raise PipelineStageRuntimeMeasurementError("runtime shadow invocation id mismatch")
            target = starts if record.get("phase") == "STARTED" else completions if record.get("phase") == "COMPLETED" else None
            if target is None or invocation_id in target:
                raise PipelineStageRuntimeMeasurementError("runtime shadow phase pairing mismatch")
            target[invocation_id] = record
        if set(starts) != set(completions) or in_memory_errors:
            raise PipelineStageRuntimeMeasurementError("runtime shadow measurement is incomplete; fail closed")
        events: list[StageBudgetEvent] = []
        statuses: list[str] = []
        completion_summaries: list[dict[str, Any]] = []
        provenance: list[dict[str, str]] = []
        for invocation_id in sorted(starts):
            start = starts[invocation_id]
            completion = completions[invocation_id]
            raw_event = completion.get("event")
            if not isinstance(raw_event, Mapping):
                raise PipelineStageRuntimeMeasurementError("runtime shadow event is missing")
            try:
                event = StageBudgetEvent(**dict(raw_event))
                event.validate()
            except (TypeError, ValueError) as exc:
                raise PipelineStageRuntimeMeasurementError("runtime shadow event is invalid") from exc
            if (
                start.get("logical_call_sha256") != event.logical_call_sha256
                or start.get("cache_namespace_sha256") != event.cache_namespace_sha256
                or start.get("input_sha256") is None
                or start.get("prompt_sha256") is None
            ):
                raise PipelineStageRuntimeMeasurementError("runtime shadow provenance pairing mismatch")
            _require_sha("input_sha256", start.get("input_sha256"))
            _require_sha("prompt_sha256", start.get("prompt_sha256"))
            assert self.binding is not None
            call_provenance = {
                "run_spec_sha256": _require_sha("run_spec_sha256", start.get("run_spec_sha256")),
                "publication_scope_id": _require_sha("publication_scope_id", start.get("publication_scope_id")),
                "attempt_sha256": _require_sha("attempt_sha256", start.get("attempt_sha256")),
                "decision_ledger_sha256": _require_sha("decision_ledger_sha256", start.get("decision_ledger_sha256")),
                "input_sha256": _require_sha("input_sha256", start.get("input_sha256")),
                "provider": str(start.get("provider") or ""),
                "model": str(start.get("model") or ""),
                "prompt_sha256": _require_sha("prompt_sha256", start.get("prompt_sha256")),
            }
            if (
                call_provenance["run_spec_sha256"] != self.binding.run_spec.sha256
                or call_provenance["publication_scope_id"] != self.binding.publication_scope.sha256
                or call_provenance["attempt_sha256"] != self.binding.attempt.sha256
                or call_provenance["decision_ledger_sha256"] != self.binding.decision_ledger.sha256
                or call_provenance["provider"] != self.config.provider
                or call_provenance["model"] != self.config.model
                or CacheNamespace(
                    call_provenance["run_spec_sha256"],
                    call_provenance["publication_scope_id"],
                    call_provenance["input_sha256"],
                    call_provenance["provider"],
                    call_provenance["model"],
                    call_provenance["prompt_sha256"],
                ).key() != event.cache_namespace_sha256
            ):
                raise PipelineStageRuntimeMeasurementError("runtime shadow exact call provenance mismatch")
            events.append(event)
            status = str(completion.get("status") or "")
            fallback = completion.get("fallback_to_legacy")
            error_class = completion.get("error_class")
            if not _completion_semantics_valid(status, fallback, error_class, event):
                raise PipelineStageRuntimeMeasurementError("runtime shadow completion semantics mismatch")
            statuses.append(status)
            completion_summaries.append(
                {"status": status, "fallback_to_legacy": fallback, "error_class": error_class}
            )
            provenance.append(call_provenance)
        gate = "GO_RUNTIME_SHADOW_MEASUREMENT" if statuses and all(status == "SHARED_RESULT" for status in statuses) else "HOLD_RUNTIME_SHADOW_MEASUREMENT"
        material = {
            "schema_version": _MEASUREMENT_SCHEMA,
            "mode": "EXPLICIT_INJECTION_RUNTIME_SHADOW",
            "runtime_id_sha256": self._runtime_id_sha256,
            "binding": self.binding.to_dict(),
            "config": deepcopy(self._runtime_config_material),
            "attempt_count": len(events),
            "statuses": statuses,
            "completions": completion_summaries,
            "provenance": provenance,
            "events": [asdict(event) for event in events],
            "gate": gate,
        }
        return {**material, "measurement_sha256": _sha(material)}

    def require_measurement_go(self) -> dict[str, Any]:
        receipt = self.build_measurement_receipt()
        if receipt["gate"] != "GO_RUNTIME_SHADOW_MEASUREMENT":
            raise PipelineStageRuntimeMeasurementError("runtime shadow measurement gate is HOLD; fail closed")
        return receipt


def read_pipeline_search_runtime_measurement(value: Mapping[str, Any], *, verify_artifacts: bool = True) -> dict[str, Any]:
    """Independent structural and provenance readback for a built receipt."""
    required = {
        "schema_version",
        "mode",
        "runtime_id_sha256",
        "binding",
        "config",
        "attempt_count",
        "statuses",
        "completions",
        "provenance",
        "events",
        "gate",
        "measurement_sha256",
    }
    if not isinstance(value, Mapping) or set(value) != required:
        raise PipelineStageRuntimeMeasurementError("runtime shadow measurement schema mismatch")
    if value.get("schema_version") != _MEASUREMENT_SCHEMA or value.get("mode") != "EXPLICIT_INJECTION_RUNTIME_SHADOW":
        raise PipelineStageRuntimeMeasurementError("runtime shadow measurement schema mismatch")
    _require_sha("runtime_id_sha256", value.get("runtime_id_sha256"))
    binding_value = value.get("binding")
    if not isinstance(binding_value, Mapping) or set(binding_value) != {"run_spec", "publication_scope", "attempt", "decision_ledger"}:
        raise PipelineStageRuntimeMeasurementError("runtime shadow binding mismatch")
    try:
        binding = StageBudgetBinding(
            **{name: ArtifactRef(**dict(binding_value[name])) for name in ("run_spec", "publication_scope", "attempt", "decision_ledger")}
        )
        binding.validate(verify_bytes=verify_artifacts)
    except (TypeError, ValueError) as exc:
        raise PipelineStageRuntimeMeasurementError("runtime shadow binding mismatch") from exc
    config_value = value.get("config")
    config_keys = {"provider", "model", "limiter", "limiter_config_sha256", "cache_ttl_seconds", "follower_timeout_ms", "lease_timeout_ms", "limiter_execution_scope", "singleflight_execution_scope"}
    if not isinstance(config_value, Mapping) or set(config_value) != config_keys or not isinstance(config_value.get("limiter"), Mapping):
        raise PipelineStageRuntimeMeasurementError("runtime shadow config mismatch")
    try:
        limiter_config = StageLimiterConfig(**dict(config_value["limiter"]))
        reconstructed_config = PipelineSearchRuntimeShadowConfig(
            enabled=True,
            provider=str(config_value.get("provider") or ""),
            model=str(config_value.get("model") or ""),
            limiter=limiter_config,
            cache_ttl_seconds=config_value.get("cache_ttl_seconds"),
            follower_timeout_ms=config_value.get("follower_timeout_ms"),
            lease_timeout_ms=config_value.get("lease_timeout_ms"),
        )
        reconstructed_config.validate()
    except (TypeError, ValueError) as exc:
        raise PipelineStageRuntimeMeasurementError("runtime shadow config mismatch") from exc
    if (
        config_value.get("limiter_config_sha256") != _sha(asdict(limiter_config))
        or config_value.get("limiter_execution_scope") != "PROCESS_LOCAL_THREADS_ONLY"
        or config_value.get("singleflight_execution_scope") != "CROSS_PROCESS_FILE_SHARED_RESULT_SHADOW_ONLY"
        or value.get("runtime_id_sha256")
        != _sha({"schema_version": _RECORD_SCHEMA, "binding": binding.to_dict(), "config": dict(config_value)})
    ):
        raise PipelineStageRuntimeMeasurementError("runtime shadow config or runtime id mismatch")
    raw_events = value.get("events")
    statuses = value.get("statuses")
    completions = value.get("completions")
    provenance = value.get("provenance")
    if not isinstance(raw_events, list) or not isinstance(statuses, list) or not isinstance(completions, list) or not isinstance(provenance, list) or value.get("attempt_count") != len(raw_events) or len(statuses) != len(raw_events) or len(completions) != len(raw_events) or len(provenance) != len(raw_events):
        raise PipelineStageRuntimeMeasurementError("runtime shadow measurement count mismatch")
    for raw_event, call_provenance, completion, status in zip(raw_events, provenance, completions, statuses):
        if not isinstance(raw_event, Mapping):
            raise PipelineStageRuntimeMeasurementError("runtime shadow event mismatch")
        try:
            event = StageBudgetEvent(**dict(raw_event))
            event.validate()
        except (TypeError, ValueError) as exc:
            raise PipelineStageRuntimeMeasurementError("runtime shadow event mismatch") from exc
        if (
            not isinstance(completion, Mapping)
            or set(completion) != {"status", "fallback_to_legacy", "error_class"}
            or completion.get("status") != status
            or not _completion_semantics_valid(
                str(status),
                completion.get("fallback_to_legacy"),
                completion.get("error_class"),
                event,
            )
        ):
            raise PipelineStageRuntimeMeasurementError("runtime shadow completion semantics mismatch")
        if not isinstance(call_provenance, Mapping) or set(call_provenance) != {"run_spec_sha256", "publication_scope_id", "attempt_sha256", "decision_ledger_sha256", "input_sha256", "provider", "model", "prompt_sha256"}:
            raise PipelineStageRuntimeMeasurementError("runtime shadow exact call provenance mismatch")
        for name in ("run_spec_sha256", "publication_scope_id", "attempt_sha256", "decision_ledger_sha256", "input_sha256", "prompt_sha256"):
            _require_sha(name, call_provenance.get(name))
        if (
            call_provenance.get("run_spec_sha256") != binding.run_spec.sha256
            or call_provenance.get("publication_scope_id") != binding.publication_scope.sha256
            or call_provenance.get("attempt_sha256") != binding.attempt.sha256
            or call_provenance.get("decision_ledger_sha256") != binding.decision_ledger.sha256
            or call_provenance.get("provider") != event.provider
            or call_provenance.get("provider") != config_value.get("provider")
            or call_provenance.get("model") != config_value.get("model")
            or CacheNamespace(
                str(call_provenance["run_spec_sha256"]),
                str(call_provenance["publication_scope_id"]),
                str(call_provenance["input_sha256"]),
                str(call_provenance["provider"]),
                str(call_provenance["model"]),
                str(call_provenance["prompt_sha256"]),
            ).key() != event.cache_namespace_sha256
        ):
            raise PipelineStageRuntimeMeasurementError("runtime shadow exact call provenance mismatch")
    expected_gate = "GO_RUNTIME_SHADOW_MEASUREMENT" if statuses and all(status == "SHARED_RESULT" for status in statuses) else "HOLD_RUNTIME_SHADOW_MEASUREMENT"
    if value.get("gate") != expected_gate:
        raise PipelineStageRuntimeMeasurementError("runtime shadow measurement gate mismatch")
    material = {key: value[key] for key in required if key != "measurement_sha256"}
    if value.get("measurement_sha256") != _sha(material):
        raise PipelineStageRuntimeMeasurementError("runtime shadow measurement self-hash mismatch")
    return {
        "schema_version": _MEASUREMENT_SCHEMA,
        "attempt_count": len(raw_events),
        "gate": expected_gate,
        "independent_readback": "GO_RUNTIME_SHADOW_RECEIPT_INTEGRITY",
    }
