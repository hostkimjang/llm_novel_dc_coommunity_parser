from __future__ import annotations

"""Crash-tolerant framed WAL v2 for *new* shadow/fresh artifacts.

This is deliberately separate from the existing P2 JSONL journal.  Migration
is an explicit launch decision; opening a v2 WAL never rewrites legacy
publication evidence.  A frame is committed only after its complete payload
and checksum are fsync'd.  Recovery may remove an incomplete final frame, but
never a complete invalid/corrupt frame.
"""

from dataclasses import dataclass
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import struct
import threading
import time
from typing import Any, Dict, Iterable, Mapping



MAGIC = b"LLM-FRAMED-WAL-V2\n"
SCHEMA = "llm_framed_wal_v2"
_LEN = struct.Struct(">Q")
_DIGEST_BYTES = 32


class FramedWalError(ValueError):
    pass


def _canonical(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _canonical(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return str(value)


def _bytes(value: Any) -> bytes:
    return json.dumps(_canonical(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _fsync_directory(path: Path) -> None:
    try:
        descriptor = os.open(str(path), os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


@contextmanager
def _exclusive_file_lock(path: Path):
    lock_path = path.with_name(path.name + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as handle:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0"); handle.flush(); os.fsync(handle.fileno())
        # Windows msvcrt locks from the current file offset.  Both acquire and
        # release must therefore operate on sentinel byte 0, never byte 1.
        handle.seek(0, os.SEEK_SET)
        deadline = time.monotonic() + 30
        if os.name == "nt":
            import msvcrt
            while True:
                handle.seek(0, os.SEEK_SET)
                try: msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1); break
                except OSError:
                    if time.monotonic() >= deadline: raise FramedWalError("framed WAL lock timeout")
                    time.sleep(.01)
            try: yield
            finally:
                handle.seek(0, os.SEEK_SET); msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try: yield
            finally: fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@dataclass(frozen=True)
class FramedWalScan:
    records: tuple[Dict[str, Any], ...]
    retained_bytes: int
    trailing_bytes: int
    last_frame_sha256: str


class FramedWAL:
    """Append-only framed WAL with O(1) steady-state append per instance."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self._lock = threading.RLock()
        self._sequence = 0
        self._last_frame_sha256 = "0" * 64
        self._initialized = False

    def initialize(self, *, repair_uncommitted_tail: bool = False) -> FramedWalScan:
        with self._lock:
            with _exclusive_file_lock(self.path):
                return self._initialize_locked(repair_uncommitted_tail=repair_uncommitted_tail)

    def _initialize_locked(self, *, repair_uncommitted_tail: bool) -> FramedWalScan:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            with self.path.open("xb") as handle:
                handle.write(MAGIC); handle.flush(); os.fsync(handle.fileno())
            _fsync_directory(self.path.parent)
        scan = self._scan_locked(repair_uncommitted_tail=repair_uncommitted_tail)
        self._sequence = len(scan.records); self._last_frame_sha256 = scan.last_frame_sha256; self._initialized = True
        return scan

    def append(self, record: Mapping[str, Any]) -> Dict[str, Any]:
        if not isinstance(record, Mapping):
            raise FramedWalError("framed WAL record must be an object")
        with self._lock:
            with _exclusive_file_lock(self.path):
                # Re-read inside the OS lock: a second registry instance or
                # process may have appended since this instance last wrote.
                self._initialize_locked(repair_uncommitted_tail=False)
                envelope = {"schema_version": SCHEMA, "sequence": self._sequence + 1, "previous_frame_sha256": self._last_frame_sha256, "record": _canonical(dict(record))}
                payload = _bytes(envelope)
                if not payload: raise FramedWalError("framed WAL payload is empty")
                frame_digest = hashlib.sha256(payload).digest()
                with self.path.open("ab") as handle:
                    handle.write(_LEN.pack(len(payload))); handle.write(payload); handle.write(frame_digest); handle.flush(); os.fsync(handle.fileno())
                _fsync_directory(self.path.parent)
                self._sequence += 1; self._last_frame_sha256 = frame_digest.hex()
                return dict(envelope)

    def append_cached_under_external_lock(self, record: Mapping[str, Any]) -> Dict[str, Any]:
        """Append without a rescan when caller owns a stronger ledger lock.

        Only DecisionLedgerV2 may use this after ``initialize``; its per-ledger
        OS lock prevents another adapter from changing this segment meanwhile.
        """
        if not isinstance(record, Mapping): raise FramedWalError("framed WAL record must be an object")
        with self._lock:
            if not self._initialized: raise FramedWalError("cached append requires initialized WAL")
            envelope = {"schema_version": SCHEMA, "sequence": self._sequence + 1, "previous_frame_sha256": self._last_frame_sha256, "record": _canonical(dict(record))}
            payload = _bytes(envelope); digest = hashlib.sha256(payload).digest()
            with self.path.open("ab") as handle:
                handle.write(_LEN.pack(len(payload))); handle.write(payload); handle.write(digest); handle.flush(); os.fsync(handle.fileno())
            _fsync_directory(self.path.parent); self._sequence += 1; self._last_frame_sha256 = digest.hex()
            return dict(envelope)

    def append_many_cached_under_external_lock(self, records: Iterable[Mapping[str, Any]]) -> list[Dict[str, Any]]:
        """Durably append one bounded segment batch with one file fsync."""
        prepared = list(records)
        with self._lock:
            if not self._initialized: raise FramedWalError("cached append requires initialized WAL")
            envelopes=[]
            with self.path.open("ab") as handle:
                for record in prepared:
                    if not isinstance(record, Mapping): raise FramedWalError("framed WAL record must be an object")
                    envelope={"schema_version":SCHEMA,"sequence":self._sequence+1,"previous_frame_sha256":self._last_frame_sha256,"record":_canonical(dict(record))}
                    payload=_bytes(envelope); digest=hashlib.sha256(payload).digest()
                    handle.write(_LEN.pack(len(payload))); handle.write(payload); handle.write(digest)
                    self._sequence+=1; self._last_frame_sha256=digest.hex(); envelopes.append(envelope)
                handle.flush(); os.fsync(handle.fileno())
            _fsync_directory(self.path.parent); return envelopes

    def scan(self, *, repair_uncommitted_tail: bool = False) -> FramedWalScan:
        with self._lock:
            with _exclusive_file_lock(self.path):
                return self._scan_locked(repair_uncommitted_tail=repair_uncommitted_tail)

    def _scan_locked(self, *, repair_uncommitted_tail: bool = False) -> FramedWalScan:
        raw = self.path.read_bytes() if self.path.exists() else b""
        if not raw.startswith(MAGIC):
            raise FramedWalError("framed WAL magic is missing or mismatched")
        offset = len(MAGIC)
        records: list[Dict[str, Any]] = []
        previous = "0" * 64
        incomplete_at: int | None = None
        while offset < len(raw):
            frame_start = offset
            if len(raw) - offset < _LEN.size:
                incomplete_at = frame_start; break
            length = _LEN.unpack(raw[offset:offset + _LEN.size])[0]
            offset += _LEN.size
            if length <= 0 or length > 64 * 1024 * 1024:
                raise FramedWalError("framed WAL frame length is invalid")
            needed = int(length) + _DIGEST_BYTES
            if len(raw) - offset < needed:
                incomplete_at = frame_start; break
            payload = raw[offset:offset + int(length)]
            digest = raw[offset + int(length):offset + needed]
            offset += needed
            if hashlib.sha256(payload).digest() != digest:
                raise FramedWalError("framed WAL complete frame checksum mismatch")
            try:
                envelope = json.loads(payload.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise FramedWalError("framed WAL complete frame JSON is invalid") from exc
            if not isinstance(envelope, dict) or set(envelope) != {"schema_version", "sequence", "previous_frame_sha256", "record"}:
                raise FramedWalError("framed WAL frame schema mismatch")
            if envelope.get("schema_version") != SCHEMA or envelope.get("sequence") != len(records) + 1:
                raise FramedWalError("framed WAL frame sequence mismatch")
            if envelope.get("previous_frame_sha256") != previous or not isinstance(envelope.get("record"), dict):
                raise FramedWalError("framed WAL frame chain mismatch")
            previous = digest.hex()
            records.append(dict(envelope))
        retained = incomplete_at if incomplete_at is not None else offset
        trailing = len(raw) - retained
        if trailing and repair_uncommitted_tail:
            with self.path.open("r+b") as handle:
                handle.truncate(retained); handle.flush(); os.fsync(handle.fileno())
            _fsync_directory(self.path.parent)
            self._write_repair_record(raw[retained:])
        return FramedWalScan(tuple(records), retained, trailing, previous)

    def _write_repair_record(self, discarded: bytes) -> None:
        repair_dir = self.path.with_name(self.path.name + ".tail_repairs")
        repair_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": "llm_framed_wal_v2_tail_repair_v1",
            "wal_name": self.path.name,
            "discarded_tail_bytes": len(discarded),
            "discarded_tail_sha256": _sha(discarded),
            "commit_point_policy": "complete_length_payload_checksum_frame",
            "repaired_at_unix_ns": time.time_ns(),
        }
        target = repair_dir / f"repair_{payload['repaired_at_unix_ns']}_{payload['discarded_tail_sha256'][:12]}.json"
        payload["repair_sha256"] = _sha(_bytes(payload))
        temporary = target.with_name(f".{target.name}.tmp")
        with temporary.open("xb") as handle:
            handle.write(_bytes(payload) + b"\n"); handle.flush(); os.fsync(handle.fileno())
        os.replace(temporary, target); _fsync_directory(repair_dir)

    def iter_records(self, *, repair_uncommitted_tail: bool = False) -> Iterable[Dict[str, Any]]:
        yield from self.scan(repair_uncommitted_tail=repair_uncommitted_tail).records
