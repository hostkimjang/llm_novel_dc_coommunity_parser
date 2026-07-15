from __future__ import annotations

"""RunSpec-bound, OFF-by-default cache adapter contract.

It is a local deterministic reference adapter, not production wiring.  Entries
are accepted only with exact namespace/provenance hashes and never when an
upstream response is degraded.
"""

from dataclasses import dataclass
from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import threading
import time
from typing import Any, Dict
import uuid

from ..ledger.framed_wal import _exclusive_file_lock


class SharedCacheContractError(ValueError):
    pass


_LOWER_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _sha(value: Any) -> str:
    try:
        canonical = json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise SharedCacheContractError(
            "cache payload must be canonical JSON without NaN or infinity"
        ) from exc
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _require_sha256(name: str, value: Any) -> str:
    if not isinstance(value, str) or _LOWER_SHA256_RE.fullmatch(value) is None:
        raise SharedCacheContractError(f"{name} must be exactly 64 lowercase hex characters")
    return value


def _require_positive_finite_ttl(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SharedCacheContractError("TTL must be a finite positive number")
    ttl = float(value)
    if not math.isfinite(ttl) or ttl <= 0:
        raise SharedCacheContractError("TTL must be a finite positive number")
    return ttl


@dataclass(frozen=True)
class CacheNamespace:
    run_spec_sha256: str
    publication_scope_id: str
    input_sha256: str
    provider: str
    model: str
    prompt_sha256: str

    def key(self) -> str:
        _require_sha256("run_spec_sha256", self.run_spec_sha256)
        _require_sha256("input_sha256", self.input_sha256)
        _require_sha256("prompt_sha256", self.prompt_sha256)
        if not all(
            isinstance(item, str) and bool(item.strip())
            for item in (self.publication_scope_id, self.provider, self.model)
        ):
            raise SharedCacheContractError("complete RunSpec/scope/input/provider/model/prompt namespace is required")
        return _sha(self.__dict__)


class ReadOnlySharedCacheAdapter:
    def __init__(self, *, allow_write: bool = False) -> None:
        self.allow_write = bool(allow_write)
        self._entries: Dict[str, tuple[float, str, Any]] = {}
        self._lock = threading.RLock()

    def _receipt(self, status: str, namespace_sha256: str, **details: Any) -> Dict[str, Any]:
        receipt: Dict[str, Any] = {
            "status": status,
            "namespace_sha256": namespace_sha256,
            "adapter_scope": "OBJECT_LOCAL",
            "contract_mode": "SHADOW_ONLY_NOT_RUNTIME_WIRED",
            "allow_write": self.allow_write,
        }
        receipt.update(details)
        return receipt

    def get(self, namespace: CacheNamespace, *, response_sha256: str | None = None) -> Dict[str, Any]:
        key = namespace.key()
        if response_sha256 is not None:
            _require_sha256("response_sha256", response_sha256)
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return self._receipt("MISS", key, cache_source="NONE", expired_entry_deleted=False)
            expires_monotonic, actual_sha, value = entry
            if expires_monotonic <= time.monotonic():
                del self._entries[key]
                return self._receipt("MISS", key, cache_source="NONE", expired_entry_deleted=True)
            if _sha(value) != actual_sha:
                raise SharedCacheContractError("cache storage digest mismatch; fail closed")
            if response_sha256 is not None and response_sha256 != actual_sha:
                raise SharedCacheContractError("cache poison or provenance mismatch; fail closed")
            return self._receipt(
                "HIT",
                key,
                cache_source="OBJECT_LOCAL",
                response_sha256=actual_sha,
                expires_monotonic=expires_monotonic,
                value=deepcopy(value),
            )

    def put(self, namespace: CacheNamespace, *, value: Any, ttl_seconds: float, degraded: bool) -> Dict[str, Any]:
        key = namespace.key()
        ttl = _require_positive_finite_ttl(ttl_seconds)
        stored = deepcopy(value)
        payload_sha = _sha(stored)
        if degraded:
            return self._receipt(
                "EXCLUDED_DEGRADED",
                key,
                cache_source="DEGRADED_EXCLUDED",
                response_sha256=payload_sha,
                ttl_seconds=ttl,
                degraded=True,
            )
        if not self.allow_write:
            return self._receipt(
                "READ_ONLY",
                key,
                cache_source="NONE",
                response_sha256=payload_sha,
                ttl_seconds=ttl,
                degraded=False,
            )
        expires_monotonic = time.monotonic() + ttl
        with self._lock:
            self._entries[key] = (expires_monotonic, payload_sha, stored)
        return self._receipt(
            "STORED",
            key,
            cache_source="OBJECT_LOCAL",
            response_sha256=payload_sha,
            ttl_seconds=ttl,
            expires_monotonic=expires_monotonic,
            degraded=False,
        )


class ProcessSharedCacheAdapter(ReadOnlySharedCacheAdapter):
    """Same-process thread-shared shadow cache; not a cross-process backend."""
    _shared_entries: Dict[str, tuple[float, str, Any]] = {}
    _shared_lock = threading.RLock()
    def __init__(self, *, allow_write: bool = False) -> None:
        super().__init__(allow_write=allow_write); self._entries=type(self)._shared_entries; self._lock=type(self)._shared_lock
    @classmethod
    def reset_for_tests(cls) -> None:
        with cls._shared_lock: cls._shared_entries.clear()
    def _receipt(self, status: str, namespace_sha256: str, **details: Any) -> Dict[str, Any]:
        receipt=super()._receipt(status,namespace_sha256,**details); receipt["adapter_scope"]="PROCESS_SHARED_THREADS_ONLY"; return receipt


class FileSharedCacheAdapter(ReadOnlySharedCacheAdapter):
    """Filesystem-local, cross-process shadow cache; never production runtime wiring."""
    SCHEMA = "file_shared_cache_entry_v1"

    def __init__(self, root: Path, *, allow_write: bool = False) -> None:
        super().__init__(allow_write=allow_write); self.root = Path(root).resolve(); self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        _require_sha256("namespace_sha256", key); return self.root / f"{key}.json"

    def _lock_path(self, key: str) -> Path:
        _require_sha256("namespace_sha256", key); return self.root / f"{key}.entry.guard"

    def _receipt(self, status: str, namespace_sha256: str, **details: Any) -> Dict[str, Any]:
        receipt = super()._receipt(status, namespace_sha256, **details)
        receipt["adapter_scope"] = "CROSS_PROCESS_FILE_SHADOW_ONLY"
        receipt["storage_root"] = str(self.root)
        return receipt

    @staticmethod
    def _entry_hash(value: Dict[str, Any]) -> str:
        return _sha({key: item for key, item in value.items() if key != "entry_sha256"})

    def _atomic_entry(self, path: Path, entry: Dict[str, Any]) -> None:
        raw = json.dumps(entry, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8") + b"\n"
        tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        try:
            with tmp.open("xb") as handle:
                handle.write(raw); handle.flush(); os.fsync(handle.fileno())
            os.replace(tmp, path)
            descriptor = None
            try:
                descriptor = os.open(str(path.parent), os.O_RDONLY); os.fsync(descriptor)
            except OSError:
                pass
            finally:
                if descriptor is not None: os.close(descriptor)
        finally:
            tmp.unlink(missing_ok=True)

    def _read_entry(self, path: Path, key: str) -> Dict[str, Any]:
        try:
            entry = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SharedCacheContractError("file shared cache entry is malformed; fail closed") from exc
        if not isinstance(entry, dict) or set(entry) != {"schema_version", "namespace_sha256", "response_sha256", "expires_at_epoch", "value", "entry_sha256"} or entry.get("schema_version") != self.SCHEMA or entry.get("entry_sha256") != self._entry_hash(entry):
            raise SharedCacheContractError("file shared cache entry self-hash mismatch; fail closed")
        if entry.get("namespace_sha256") != key or _sha(entry.get("value")) != entry.get("response_sha256"):
            raise SharedCacheContractError("file shared cache provenance mismatch; fail closed")
        if not isinstance(entry.get("expires_at_epoch"), (int, float)) or not math.isfinite(entry["expires_at_epoch"]):
            raise SharedCacheContractError("file shared cache expiry mismatch; fail closed")
        return entry

    def _delete_if_same_expired(self, path: Path, key: str, observed: Dict[str, Any]) -> bool:
        """Evict only the exact expired entry observed before the OS-file lock."""
        with _exclusive_file_lock(self._lock_path(key)):
            if not path.is_file(): return False
            current = self._read_entry(path, key)
            if current["entry_sha256"] != observed["entry_sha256"] or current["expires_at_epoch"] > time.time(): return False
            path.unlink(); return True

    def get(self, namespace: CacheNamespace, *, response_sha256: str | None = None) -> Dict[str, Any]:
        key = namespace.key(); path = self._path(key)
        if response_sha256 is not None: _require_sha256("response_sha256", response_sha256)
        if not path.is_file(): return self._receipt("MISS", key, cache_source="NONE", expired_entry_deleted=False)
        entry = self._read_entry(path, key)
        if entry["expires_at_epoch"] <= time.time():
            return self._receipt("MISS", key, cache_source="NONE", expired_entry_deleted=self._delete_if_same_expired(path, key, entry))
        if response_sha256 is not None and entry["response_sha256"] != response_sha256:
            raise SharedCacheContractError("cache poison or provenance mismatch; fail closed")
        return self._receipt("HIT", key, cache_source="CROSS_PROCESS_FILE_SHADOW", response_sha256=entry["response_sha256"], expires_at_epoch=entry["expires_at_epoch"], value=deepcopy(entry["value"]))

    def put(self, namespace: CacheNamespace, *, value: Any, ttl_seconds: float, degraded: bool) -> Dict[str, Any]:
        key = namespace.key(); ttl = _require_positive_finite_ttl(ttl_seconds); stored = deepcopy(value); payload_sha = _sha(stored)
        if degraded:
            return self._receipt("EXCLUDED_DEGRADED", key, cache_source="DEGRADED_EXCLUDED", response_sha256=payload_sha, ttl_seconds=ttl, degraded=True)
        if not self.allow_write:
            return self._receipt("READ_ONLY", key, cache_source="NONE", response_sha256=payload_sha, ttl_seconds=ttl, degraded=False)
        entry = {"schema_version": self.SCHEMA, "namespace_sha256": key, "response_sha256": payload_sha, "expires_at_epoch": time.time() + ttl, "value": stored}
        entry["entry_sha256"] = self._entry_hash(entry)
        with _exclusive_file_lock(self._lock_path(key)):
            self._atomic_entry(self._path(key), entry)
        return self._receipt("STORED", key, cache_source="CROSS_PROCESS_FILE_SHADOW", response_sha256=payload_sha, ttl_seconds=ttl, expires_at_epoch=entry["expires_at_epoch"], degraded=False)
