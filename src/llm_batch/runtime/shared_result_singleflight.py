from __future__ import annotations

"""OFF-by-default filesystem-local shared-result singleflight shadow contract.

This deliberately composes the cache and lease contracts without wiring any
runtime caller.  The cache namespace and lease key must describe the same
RunSpec/scope/input/provider/model/prompt.  A leader may publish only while it
still owns an unexpired lease; followers poll the cache and never reuse a raw
leader result directly.
"""

from dataclasses import dataclass
import time
from typing import Any, Callable

from .local_stage_gate import FileLeaseReceipt, FileSingleflightLease, StageGateTimeout, StageSingleflightKey
from .shared_cache_contract import CacheNamespace, FileSharedCacheAdapter


@dataclass(frozen=True)
class SharedResultSingleflightReceipt:
    schema_version: str
    namespace_sha256: str
    role: str
    outcome: str
    wait_ms: int
    cache_source: str
    response_sha256: str | None
    enabled: bool
    execution_scope: str = "CROSS_PROCESS_FILE_SHARED_RESULT_SHADOW_ONLY"


class FileSharedResultSingleflight:
    """Filesystem-local result reuse with explicit no-op and bounded fail-close modes."""

    SCHEMA = "file_shared_result_singleflight_v1"

    def __init__(self, cache: FileSharedCacheAdapter, leases: FileSingleflightLease, *, enabled: bool = False) -> None:
        if not isinstance(cache, FileSharedCacheAdapter) or not isinstance(leases, FileSingleflightLease):
            raise TypeError("file cache and file lease contracts are required")
        self.cache = cache; self.leases = leases; self.enabled = bool(enabled)

    @staticmethod
    def _validate_binding(namespace: CacheNamespace, key: StageSingleflightKey) -> str:
        namespace_sha = namespace.key(); key_sha = key.key()
        if (namespace.run_spec_sha256, namespace.publication_scope_id, namespace.input_sha256, namespace.provider, namespace.model, namespace.prompt_sha256) != (key.run_spec_sha256, key.publication_scope_id, key.input_sha256, key.provider, key.model, key.prompt_sha256):
            raise ValueError("cache namespace and singleflight key must have exact RunSpec/scope/input/provider/model/prompt binding")
        return namespace_sha

    def _receipt(self, namespace_sha: str, role: str, outcome: str, started: float, *, cache_source: str, response_sha256: str | None = None) -> SharedResultSingleflightReceipt:
        return SharedResultSingleflightReceipt(self.SCHEMA, namespace_sha, role, outcome, max(0, int((time.monotonic() - started) * 1000)), cache_source, response_sha256, self.enabled)

    @staticmethod
    def _timeout(message: str, receipt: SharedResultSingleflightReceipt) -> StageGateTimeout:
        error = StageGateTimeout(message); error.receipt = receipt; return error

    def run(self, namespace: CacheNamespace, key: StageSingleflightKey, operation: Callable[[], Any], *, ttl_seconds: float, follower_timeout_ms: int, lease_timeout_ms: int) -> tuple[Any, SharedResultSingleflightReceipt]:
        if isinstance(follower_timeout_ms, bool) or isinstance(lease_timeout_ms, bool) or follower_timeout_ms < 0 or lease_timeout_ms <= 0:
            raise ValueError("singleflight timeouts are invalid")
        namespace_sha = self._validate_binding(namespace, key); started = time.monotonic()
        if not self.enabled:
            return operation(), self._receipt(namespace_sha, "NONE", "DISABLED_NO_OP", started, cache_source="NONE")
        if not self.cache.allow_write:
            raise ValueError("enabled shared-result singleflight requires a writable shadow cache")
        deadline = started + follower_timeout_ms / 1000.0
        follower_waited = False
        while True:
            cached = self.cache.get(namespace)
            if cached["status"] == "HIT":
                role, outcome = ("FOLLOWER", "FOLLOWER_HIT") if follower_waited else ("CACHE", "CACHE_HIT")
                return cached["value"], self._receipt(namespace_sha, role, outcome, started, cache_source=cached["cache_source"], response_sha256=cached["response_sha256"])
            lease = self.leases.acquire(key, timeout_ms=0, lease_timeout_ms=lease_timeout_ms)
            if lease.role == "LEADER":
                try:
                    produced = operation()
                    published, stored = self.leases.run_while_current_leader(lease, lambda: self.cache.put(namespace, value=produced, ttl_seconds=ttl_seconds, degraded=False))
                    if not published:
                        raise self._timeout("shared-result leader lease expired before cache publish; result discarded", self._receipt(namespace_sha, "LEADER", "LEASE_EXPIRED", started, cache_source="NONE"))
                    assert isinstance(stored, dict)
                    if stored["status"] != "STORED":
                        raise self._timeout("shared-result leader cache publish failed closed", self._receipt(namespace_sha, "LEADER", "PUBLISH_REJECTED", started, cache_source=stored.get("cache_source", "NONE")))
                    return produced, self._receipt(namespace_sha, "LEADER", "PRODUCED", started, cache_source=stored["cache_source"], response_sha256=stored["response_sha256"])
                finally:
                    self.leases.release(lease)
            if time.monotonic() >= deadline:
                final = self.cache.get(namespace)
                if final["status"] == "HIT":
                    return final["value"], self._receipt(namespace_sha, "FOLLOWER", "FOLLOWER_HIT", started, cache_source=final["cache_source"], response_sha256=final["response_sha256"])
                raise self._timeout("shared-result follower timed out without a cache result", self._receipt(namespace_sha, "FOLLOWER", "TIMEOUT", started, cache_source="NONE"))
            follower_waited = True
            time.sleep(.01)
