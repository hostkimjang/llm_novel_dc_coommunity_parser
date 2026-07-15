from __future__ import annotations

"""Deterministic local limiter and singleflight harness primitives.

No shared cache is implemented here; cache provenance is intentionally a
separate contract in :mod:`shared_cache_contract`.
"""

from dataclasses import dataclass, replace
import hashlib
import json
import os
from pathlib import Path
import threading
import time
from typing import Callable, Dict, TypeVar, Tuple
import math
import uuid

from ..ledger.framed_wal import _exclusive_file_lock


T = TypeVar("T")


class StageGateTimeout(TimeoutError):
    def __init__(self, message: str, *, receipt: "SingleflightReceipt | None" = None) -> None:
        super().__init__(message); self.receipt = receipt


@dataclass(frozen=True)
class LimiterReceipt:
    schema_version: str
    stage: str
    provider: str
    outcome: str
    wait_ms: int
    configured_rate_per_second: float = 0.0
    configured_burst: int = 0
    denial_reason: str | None = None
    configured_max_wait_ms: int = 0
    required_wait_ms: int = 0
    deadline_exhausted: bool = False
    execution_scope: str = "PROCESS_LOCAL_THREADS_ONLY"


@dataclass(frozen=True)
class SingleflightReceipt:
    schema_version: str
    key_sha256: str
    role: str
    outcome: str
    wait_ms: int
    configured_follower_timeout_ms: int
    configured_leader_timeout_ms: int | None
    execution_scope: str = "PROCESS_LOCAL_THREADS_ONLY"
    error_class: str | None = None


@dataclass(frozen=True)
class StageSingleflightKey:
    """Canonical same-process dedupe identity; never stores raw request content."""
    run_spec_sha256: str
    publication_scope_id: str
    input_sha256: str
    stage: str
    provider: str
    model: str
    prompt_sha256: str

    def key(self) -> str:
        for name in ("run_spec_sha256", "input_sha256", "prompt_sha256"):
            value = getattr(self, name)
            if not isinstance(value, str) or len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
                raise ValueError(f"{name} must be exactly 64 lowercase hex")
        if not all(isinstance(value, str) and value.strip() for value in (self.publication_scope_id, self.stage, self.provider, self.model)):
            raise ValueError("complete RunSpec/scope/stage/provider/model key is required")
        material = {name: getattr(self, name) for name in ("run_spec_sha256", "publication_scope_id", "input_sha256", "stage", "provider", "model", "prompt_sha256")}
        return hashlib.sha256(json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class FileLeaseReceipt:
    schema_version: str
    key_sha256: str
    role: str
    status: str
    wait_ms: int
    lease_timeout_ms: int
    execution_scope: str = "CROSS_PROCESS_FILE_LEASE_SHADOW_ONLY"
    owner_token: str | None = None


class FileSingleflightLease:
    """Filesystem-local lease for cross-process cache fill coordination, not result sharing."""
    SCHEMA = "stage_singleflight_file_lease_v1"

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root).resolve(); self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key_sha256: str) -> Path:
        if len(key_sha256) != 64 or any(ch not in "0123456789abcdef" for ch in key_sha256): raise ValueError("canonical key must be sha256")
        return self.root / f"{key_sha256}.lease.json"

    def _lock_path(self, key_sha256: str) -> Path:
        return self.root / f"{key_sha256}.lease.guard"

    @staticmethod
    def _lease_hash(value: dict) -> str:
        return hashlib.sha256(json.dumps({key: item for key, item in value.items() if key != "lease_sha256"}, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    def _read_lease(self, path: Path, key_sha: str, *, self_hash_error: bool = False) -> dict:
        try: current = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc: raise StageGateTimeout("file singleflight lease is malformed; fail closed") from exc
        if not isinstance(current, dict) or current.get("schema_version") != self.SCHEMA or current.get("key_sha256") != key_sha:
            raise StageGateTimeout("file singleflight lease provenance mismatch; fail closed")
        if current.get("lease_sha256") != self._lease_hash(current):
            raise StageGateTimeout("file singleflight lease self-hash mismatch; fail closed" if self_hash_error else "file singleflight lease provenance mismatch; fail closed")
        if not isinstance(current.get("expires_at_epoch"), (int, float)):
            raise StageGateTimeout("file singleflight lease expiry mismatch; fail closed")
        return current

    def _remove_expired_if_observed(self, path: Path, key_sha: str, observed: dict) -> bool:
        """Delete only the exact expired lease observed by this follower.

        The guard is OS-file-locked so a late stale follower can never unlink a
        replacement lease created by another process.
        """
        with _exclusive_file_lock(self._lock_path(key_sha)):
            if not path.is_file(): return False
            current = self._read_lease(path, key_sha)
            if current.get("owner_token") != observed.get("owner_token") or current.get("lease_sha256") != observed.get("lease_sha256") or current["expires_at_epoch"] > time.time(): return False
            path.unlink(); return True

    def acquire(self, key: StageSingleflightKey, *, timeout_ms: int, lease_timeout_ms: int) -> FileLeaseReceipt:
        if isinstance(timeout_ms, bool) or isinstance(lease_timeout_ms, bool) or timeout_ms < 0 or lease_timeout_ms <= 0: raise ValueError("lease timeouts are invalid")
        key_sha = key.key(); path = self._path(key_sha); started = time.monotonic(); deadline = started + timeout_ms / 1000.0; owner = uuid.uuid4().hex
        while True:
            now_epoch = time.time(); lease = {"schema_version": self.SCHEMA, "key_sha256": key_sha, "owner_token": owner, "expires_at_epoch": now_epoch + lease_timeout_ms / 1000.0}
            lease["lease_sha256"] = self._lease_hash(lease)
            try:
                with path.open("x", encoding="utf-8") as handle:
                    handle.write(json.dumps(lease, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"); handle.flush(); os.fsync(handle.fileno())
                return FileLeaseReceipt(self.SCHEMA, key_sha, "LEADER", "ACQUIRED", max(0, int((time.monotonic() - started) * 1000)), lease_timeout_ms, owner_token=owner)
            except FileExistsError:
                current = self._read_lease(path, key_sha)
                if current["expires_at_epoch"] <= time.time():
                    self._remove_expired_if_observed(path, key_sha, current)
                    continue
                if time.monotonic() >= deadline:
                    return FileLeaseReceipt(self.SCHEMA, key_sha, "FOLLOWER", "TIMEOUT", max(0, int((time.monotonic() - started) * 1000)), lease_timeout_ms)
                time.sleep(.01)

    def release(self, receipt: FileLeaseReceipt) -> bool:
        if receipt.schema_version != self.SCHEMA or receipt.role != "LEADER" or not receipt.owner_token: raise ValueError("leader lease receipt is required")
        path = self._path(receipt.key_sha256)
        with _exclusive_file_lock(self._lock_path(receipt.key_sha256)):
            if not path.is_file(): return False
            current = self._read_lease(path, receipt.key_sha256, self_hash_error=True)
            if current.get("owner_token") != receipt.owner_token: return False
            path.unlink(); return True

    def run_while_current_leader(self, receipt: FileLeaseReceipt, operation: Callable[[], T]) -> tuple[bool, T | None]:
        """Run a short publish operation only while this leader still owns its lease.

        The ownership/expiry check and the operation share the lease OS lock.
        A superseded or expired leader therefore cannot publish a late result
        over a replacement leader's result.
        """
        if receipt.schema_version != self.SCHEMA or receipt.role != "LEADER" or not receipt.owner_token:
            raise ValueError("leader lease receipt is required")
        path = self._path(receipt.key_sha256)
        with _exclusive_file_lock(self._lock_path(receipt.key_sha256)):
            if not path.is_file(): return False, None
            current = self._read_lease(path, receipt.key_sha256, self_hash_error=True)
            if current.get("owner_token") != receipt.owner_token or current["expires_at_epoch"] <= time.time():
                return False, None
            return True, operation()


@dataclass(frozen=True)
class StageLimiterConfig:
    rate_per_second: float
    burst: int
    max_wait_ms: int
    disabled: bool = False

    def validate(self) -> None:
        if not math.isfinite(self.rate_per_second) or self.rate_per_second < 0 or isinstance(self.burst, bool) or self.burst < 1 or isinstance(self.max_wait_ms, bool) or self.max_wait_ms < 0:
            raise ValueError("invalid finite limiter configuration")


class LocalTokenBucket:
    def __init__(self, *, rate_per_second: float, burst: int, unlimited: bool = False, clock: Callable[[], float] = time.monotonic) -> None:
        self.rate_per_second = max(0.0, float(rate_per_second))
        self.burst = max(1, int(burst))
        self.unlimited = bool(unlimited)
        self._clock = clock
        self._tokens = float(self.burst)
        self._updated = clock()
        self._lock = threading.Lock()

    def acquire(self, *, stage: str, provider: str, max_wait_ms: int = 0, absolute_deadline: float | None = None) -> LimiterReceipt:
        requested_at = self._clock()
        deadline = absolute_deadline if absolute_deadline is not None else (requested_at + max(0, max_wait_ms) / 1000.0)
        with self._lock:
            now = self._clock()
            self._tokens = min(float(self.burst), self._tokens + max(0.0, now - self._updated) * self.rate_per_second)
            self._updated = now
            if self.rate_per_second <= 0:
                return LimiterReceipt("local_stage_limiter_v2", stage, provider, "UNLIMITED" if self.unlimited else "DENIED", 0, required_wait_ms=0, deadline_exhausted=not self.unlimited)
            if self._tokens >= 1.0:
                self._tokens -= 1.0; return LimiterReceipt("local_stage_limiter_v2", stage, provider, "ACQUIRED", 0)
            wait_ms = max(0, math.ceil(((1.0 - self._tokens) / self.rate_per_second) * 1000))
            remaining_ms = max(0, int((deadline - now) * 1000))
            if max_wait_ms <= 0 or remaining_ms <= 0 or wait_ms > remaining_ms:
                return LimiterReceipt("local_stage_limiter_v2", stage, provider, "DENIED", 0, required_wait_ms=wait_ms, deadline_exhausted=remaining_ms <= 0 or wait_ms > remaining_ms)
        time.sleep(wait_ms / 1000.0)
        followup = self.acquire(stage=stage, provider=provider, max_wait_ms=max_wait_ms, absolute_deadline=deadline)
        if followup.outcome == "ACQUIRED":
            actual_wait_ms = max(0, int((self._clock() - requested_at) * 1000))
            return LimiterReceipt("local_stage_limiter_v2", stage, provider, "WAITED", actual_wait_ms, required_wait_ms=wait_ms, deadline_exhausted=False)
        return LimiterReceipt(followup.schema_version, stage, provider, followup.outcome, max(0, int((self._clock() - requested_at) * 1000)), required_wait_ms=wait_ms + followup.required_wait_ms, deadline_exhausted=followup.deadline_exhausted)


class StageLimiterRegistry:
    """Per-process `(stage, provider)` limiter registry for shadow use only."""
    def __init__(self, configs: Dict[Tuple[str, str], StageLimiterConfig]) -> None:
        self._configs = dict(configs); self._buckets: Dict[Tuple[str, str], LocalTokenBucket] = {}; self._lock = threading.Lock()
        for config in self._configs.values(): config.validate()
    def acquire(self, *, stage: str, provider: str) -> LimiterReceipt:
        key=(str(stage).strip(),str(provider).strip())
        config=self._configs.get(key)
        if config is None: return LimiterReceipt("stage_limiter_registry_v2",key[0],key[1],"DENIED",0,denial_reason="CONFIG_MISSING")
        if config.disabled: return LimiterReceipt("stage_limiter_registry_v2",key[0],key[1],"DISABLED",0,config.rate_per_second,config.burst,"EXPLICIT_DISABLED",0,0,False)
        with self._lock:
            bucket=self._buckets.setdefault(key,LocalTokenBucket(rate_per_second=config.rate_per_second,burst=config.burst))
        deadline=time.monotonic()+config.max_wait_ms/1000.0
        receipt=bucket.acquire(stage=key[0],provider=key[1],max_wait_ms=config.max_wait_ms,absolute_deadline=deadline)
        return LimiterReceipt("stage_limiter_registry_v2",key[0],key[1],receipt.outcome,receipt.wait_ms,config.rate_per_second,config.burst,"MAX_WAIT_EXCEEDED" if receipt.outcome=="DENIED" else None,config.max_wait_ms,receipt.required_wait_ms,receipt.deadline_exhausted)


class _Flight:
    def __init__(self) -> None:
        self.done = threading.Event(); self.value: object | None = None; self.error: BaseException | None = None; self.started_at=time.monotonic()


class LocalSingleflight:
    def __init__(self) -> None:
        self._flights: Dict[str, _Flight] = {}
        self._lock = threading.Lock()

    def run_with_receipt(self, key: str, operation: Callable[[], T], *, timeout_seconds: float, leader_timeout_seconds: float | None = None) -> tuple[T, SingleflightReceipt]:
        if timeout_seconds < 0 or (leader_timeout_seconds is not None and leader_timeout_seconds <= 0): raise ValueError("timeouts must be positive")
        with self._lock:
            flight = self._flights.get(key)
            if flight is not None and leader_timeout_seconds is not None and time.monotonic()-flight.started_at >= leader_timeout_seconds:
                # Late original leader is no longer reusable.  It may finish,
                # but its finally block must not remove a replacement flight.
                self._flights.pop(key, None); flight.error=StageGateTimeout("singleflight leader deadline exceeded; result discarded"); flight.done.set(); flight=None
            if flight is None:
                flight = _Flight(); self._flights[key] = flight; leader = True
            else:
                leader = False
        if not leader:
            started=time.monotonic()
            if not flight.done.wait(max(0.0, timeout_seconds)):
                receipt=SingleflightReceipt("local_singleflight_v2",hashlib.sha256(key.encode()).hexdigest(),"FOLLOWER","TIMEOUT",max(0,int((time.monotonic()-started)*1000)),int(timeout_seconds*1000),int(leader_timeout_seconds*1000) if leader_timeout_seconds is not None else None,error_class="StageGateTimeout")
                raise StageGateTimeout("singleflight follower timed out; no result was reused",receipt=receipt)
            if flight.error is not None: raise flight.error
            return flight.value, SingleflightReceipt("local_singleflight_v2",hashlib.sha256(key.encode()).hexdigest(),"FOLLOWER","SUCCESS",max(0,int((time.monotonic()-started)*1000)),int(timeout_seconds*1000),int(leader_timeout_seconds*1000) if leader_timeout_seconds is not None else None)  # type: ignore[return-value]
        try:
            value = operation(); flight.value = value; return value, SingleflightReceipt("local_singleflight_v2",hashlib.sha256(key.encode()).hexdigest(),"LEADER","SUCCESS",0,int(timeout_seconds*1000),int(leader_timeout_seconds*1000) if leader_timeout_seconds is not None else None)
        except BaseException as exc:
            flight.error = exc; raise
        finally:
            with self._lock:
                if self._flights.get(key) is flight: self._flights.pop(key, None)
                flight.done.set()

    def run(self, key: str, operation: Callable[[], T], *, timeout_seconds: float, leader_timeout_seconds: float | None = None) -> tuple[T, bool]:
        value, receipt=self.run_with_receipt(key,operation,timeout_seconds=timeout_seconds,leader_timeout_seconds=leader_timeout_seconds)
        return value, receipt.role == "FOLLOWER"

    def run_scoped(self, key: StageSingleflightKey, operation: Callable[[], T], *, timeout_seconds: float, leader_timeout_seconds: float | None = None) -> tuple[T, SingleflightReceipt]:
        """Run with a complete RunSpec/scope/provider/model namespace instead of a raw key."""
        canonical_key = key.key()
        try:
            value, receipt = self.run_with_receipt(canonical_key, operation, timeout_seconds=timeout_seconds, leader_timeout_seconds=leader_timeout_seconds)
            return value, replace(receipt, key_sha256=canonical_key)
        except StageGateTimeout as exc:
            if exc.receipt is not None:
                exc.receipt = replace(exc.receipt, key_sha256=canonical_key)
            raise
