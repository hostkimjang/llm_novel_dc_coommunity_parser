from __future__ import annotations

"""Shadow-only framed WAL v2 adapter for DecisionCallLedger frames.

Unlike the current ``DecisionCallLedgerRegistry`` frame-directory writer, this
adapter keeps a bounded segment index and does not reload every historic frame
on append.  It is not wired into ``expert_main`` yet; use it only in a
dedicated canary after replay-equivalence verification.
"""

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import threading
import time
from typing import Any, Dict, Iterable, Mapping

from .framed_wal import FramedWAL, FramedWalError


SCHEMA = "decision_call_ledger_framed_v2"
LEGACY_READBACK_SCHEMA = "decision_call_ledger_readback_v1"
LEGACY_SCOPE_SCHEMA = "decision_call_ledger_scope_v1"
LEGACY_FRAME_SCHEMA = "decision_call_immutable_frame_v1"
LEGACY_REPLAY_RECEIPT_SCHEMA = "decision_call_ledger_legacy_replay_equivalence_v1"
CHECKPOINT_SCHEMA = "decision_call_ledger_v2_checkpoint_v1"
COMPACTION_RECEIPT_SCHEMA = "decision_call_ledger_v2_compaction_receipt_v1"


class DecisionLedgerV2Error(ValueError):
    pass


def _hex_sha256(value: Any, field: str) -> str:
    text = str(value)
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise DecisionLedgerV2Error(f"{field} must be lowercase sha256")
    return text


def _legacy_replay_source(readback: Mapping[str, Any]) -> tuple[str, list[Dict[str, Any]]]:
    """Validate and deterministically order a legacy registry readback.

    This intentionally validates only the immutable transport envelope.  The
    source ``DecisionCallLedgerRegistry.readback()`` remains responsible for
    semantic frame validation (retry lineage, row seals, and publication
    links); the adapter does not become a second production ledger runtime.
    """
    if not isinstance(readback, Mapping) or readback.get("schema_version") != LEGACY_READBACK_SCHEMA:
        raise DecisionLedgerV2Error("legacy readback schema mismatch")
    scope = readback.get("scope")
    if not isinstance(scope, Mapping) or scope.get("schema_version") != LEGACY_SCOPE_SCHEMA:
        raise DecisionLedgerV2Error("legacy scope schema mismatch")
    scope_sha256 = _hex_sha256(scope.get("scope_sha256"), "legacy scope_sha256")
    scope_material = dict(scope)
    scope_material.pop("scope_sha256", None)
    if _sha(scope_material) != scope_sha256:
        raise DecisionLedgerV2Error("legacy scope self-hash mismatch")

    source = readback.get("frames")
    if not isinstance(source, list):
        raise DecisionLedgerV2Error("legacy frames must be a list")
    frames: list[Dict[str, Any]] = []
    identities: set[str] = set()
    for value in source:
        if not isinstance(value, Mapping) or value.get("schema_version") != LEGACY_FRAME_SCHEMA:
            raise DecisionLedgerV2Error("legacy frame schema mismatch")
        frame = dict(value)
        DecisionCallLedgerV2._reject_raw_fields(frame)
        identity = _hex_sha256(frame.get("identity_sha256"), "legacy identity_sha256")
        if identity in identities:
            raise DecisionLedgerV2Error("duplicate legacy frame identity")
        identities.add(identity)
        frame_sha256 = _hex_sha256(frame.get("frame_sha256"), "legacy frame_sha256")
        material = dict(frame)
        material.pop("frame_sha256", None)
        if _sha(material) != frame_sha256:
            raise DecisionLedgerV2Error("legacy frame self-hash mismatch")
        frames.append(json.loads(json.dumps(frame)))
    frames.sort(key=lambda item: (str(item.get("frame_kind")), item["identity_sha256"]))
    return scope_sha256, frames


def replay_legacy_readback_to_v2(
    ledger: "DecisionCallLedgerV2", readback: Mapping[str, Any]
) -> Dict[str, Any]:
    """Replay one validated legacy readback into an empty shadow v2 ledger.

    The destination must be empty so an equivalence receipt can never hide
    pre-existing or cross-run frames.  Production wiring is deliberately out
    of scope; callers opt into this adapter from tests or a dedicated canary.
    """
    if not isinstance(ledger, DecisionCallLedgerV2):
        raise DecisionLedgerV2Error("ledger must be DecisionCallLedgerV2")
    scope_sha256, frames = _legacy_replay_source(readback)
    if scope_sha256 != ledger.scope_sha256:
        raise DecisionLedgerV2Error("legacy/v2 scope mismatch")
    state = ledger.initialize()
    if state["frame_count"] != 0:
        raise DecisionLedgerV2Error("legacy replay requires an empty v2 ledger")
    ledger.append_many(frames)
    replayed = ledger.replay()
    if _bytes(replayed) != _bytes(frames):
        raise DecisionLedgerV2Error("legacy/v2 replay mismatch")
    replay_sha256 = _sha(frames)
    material = {
        "schema_version": LEGACY_REPLAY_RECEIPT_SCHEMA,
        "scope_sha256": scope_sha256,
        "frame_count": len(frames),
        "legacy_frames_sha256": replay_sha256,
        "v2_replay_sha256": replay_sha256,
        "equivalent": True,
        "status": "SHADOW_ONLY_REPLAY_EQUIVALENT",
    }
    return {**material, "receipt_sha256": _sha(material)}


def _bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _sha(value: Any) -> str:
    return hashlib.sha256(_bytes(value)).hexdigest()


def _atomic(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.{time.time_ns()}.tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(_bytes(value) + b"\n"); handle.flush(); os.fsync(handle.fileno())
        os.replace(temporary, path)
        descriptor = None
        try:
            descriptor = os.open(str(path.parent), os.O_RDONLY); os.fsync(descriptor)
        except OSError:
            pass
        finally:
            if descriptor is not None: os.close(descriptor)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def _lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0"); handle.flush(); os.fsync(handle.fileno())
        handle.seek(0, os.SEEK_SET)
        deadline = time.monotonic() + 30
        if os.name == "nt":
            import msvcrt
            while True:
                try:
                    handle.seek(0, os.SEEK_SET); msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1); break
                except OSError:
                    if time.monotonic() >= deadline: raise DecisionLedgerV2Error("v2 ledger lock timeout")
                    time.sleep(.01)
            try: yield
            finally: handle.seek(0, os.SEEK_SET); msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try: yield
            finally: fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


class DecisionCallLedgerV2:
    def __init__(self, root: Path | str, *, scope_sha256: str, segment_max_frames: int = 256) -> None:
        self.root = Path(root); self.scope_sha256 = str(scope_sha256); self.segment_max_frames = max(1, int(segment_max_frames))
        if len(self.scope_sha256) != 64: raise DecisionLedgerV2Error("scope_sha256 must be sha256")
        self.index_path = self.root / "index.json"; self.checkpoint_path = self.root / "checkpoint.json"; self.lock_path = self.root / ".ledger-v2.lock"
        self._state: Dict[str, Any] | None = None; self._wals: Dict[str, FramedWAL] = {}
        self._validated_index_sha256: str | None = None

    def initialize(self, *, recover_torn_tail: bool = False) -> Dict[str, Any]:
        with _lock(self.lock_path):
            return self._initialize_locked(recover_torn_tail=recover_torn_tail)

    def _initialize_locked(self, *, recover_torn_tail: bool) -> Dict[str, Any]:
        if not self.index_path.exists():
            self.root.mkdir(parents=True, exist_ok=True)
            self._state = self._seal({"schema_version": SCHEMA, "scope_sha256": self.scope_sha256, "segment_max_frames": self.segment_max_frames, "segments": [], "frame_count": 0, "status": "SHADOW_ONLY_NOT_WIRED"})
            _atomic(self.index_path, self._state)
        else:
            self._state = self._read_index()
        if recover_torn_tail:
            self._recover_locked()
        else:
            self._verify_index_evidence_locked(self._state, repair_torn_tail=False)
            self._validated_index_sha256 = self._state["index_sha256"]
        return dict(self._state)

    def append(self, frame: Mapping[str, Any]) -> Dict[str, Any]:
        return self.append_many([frame])[0]

    def append_many(self, frames: Iterable[Mapping[str, Any]]) -> list[Dict[str, Any]]:
        items=list(frames)
        if not items: return []
        for frame in items:
            if not isinstance(frame, Mapping): raise DecisionLedgerV2Error("frame must be object")
            self._reject_raw_fields(frame)
        receipts=[]
        with _lock(self.lock_path):
            state=self._read_index() if self.index_path.exists() else self._initialize_locked(recover_torn_tail=False)
            self._verify_append_evidence_locked(state)
            segments=list(state["segments"])
            cursor=0
            while cursor<len(items):
                if not segments or segments[-1]["frame_count"]>=state["segment_max_frames"]:
                    segments.append({"path":f"segments/{len(segments):06d}.fwal","frame_count":0,"last_frame_sha256":"0"*64})
                segment=segments[-1]; take=min(state["segment_max_frames"]-segment["frame_count"],len(items)-cursor); wal=self._wals.get(segment["path"])
                if wal is None:
                    wal=FramedWAL(self.root/segment["path"]); wal.initialize(repair_uncommitted_tail=False); self._wals[segment["path"]]=wal
                envelopes=wal.append_many_cached_under_external_lock({"scope_sha256":self.scope_sha256,"frame":dict(item)} for item in items[cursor:cursor+take])
                segment["frame_count"]+=len(envelopes); segment["last_frame_sha256"]=_sha(envelopes[-1]); cursor+=take
            state=self._seal({**{k:v for k,v in state.items() if k!="index_sha256"},"segments":segments,"frame_count":int(state["frame_count"])+len(items)})
            _atomic(self.index_path,state); self._state=state; self._validated_index_sha256 = state["index_sha256"]
            return [{"schema_version":SCHEMA,"status":"APPENDED","frame_count":state["frame_count"],"index_sha256":state["index_sha256"]} for _ in items]

    def _append_legacy_single(self, frame: Mapping[str, Any]) -> Dict[str, Any]:
        if not isinstance(frame, Mapping): raise DecisionLedgerV2Error("frame must be object")
        self._reject_raw_fields(frame)
        with _lock(self.lock_path):
            state = self._read_index() if self.index_path.exists() else self._initialize_locked(recover_torn_tail=False)
            segments = list(state["segments"])
            if not segments or segments[-1]["frame_count"] >= state["segment_max_frames"]:
                name = f"segments/{len(segments):06d}.fwal"; segments.append({"path": name, "frame_count": 0, "last_frame_sha256": "0" * 64})
            segment = segments[-1]; wal = self._wals.get(segment["path"])
            if wal is None:
                wal = FramedWAL(self.root / segment["path"]); wal.initialize(repair_uncommitted_tail=False); self._wals[segment["path"]] = wal
            envelope = wal.append_cached_under_external_lock({"scope_sha256": self.scope_sha256, "frame": dict(frame)})
            segment["frame_count"] += 1; segment["last_frame_sha256"] = _sha(envelope)
            state = self._seal({**{key: value for key, value in state.items() if key != "index_sha256"}, "segments": segments, "frame_count": int(state["frame_count"]) + 1})
            _atomic(self.index_path, state); self._state = state
            return {"schema_version": SCHEMA, "status": "APPENDED", "segment": segment["path"], "frame_count": state["frame_count"], "index_sha256": state["index_sha256"]}

    def replay(self) -> list[Dict[str, Any]]:
        with _lock(self.lock_path):
            return self._replay_locked()

    def _replay_locked(self) -> list[Dict[str, Any]]:
        state = self._read_index(); scans = self._verify_index_evidence_locked(state, repair_torn_tail=False); result: list[Dict[str, Any]] = []
        for segment, scan in zip(state["segments"], scans):
            for item in scan.records:
                record = item["record"]
                if record.get("scope_sha256") != self.scope_sha256 or not isinstance(record.get("frame"), dict): raise DecisionLedgerV2Error("frame scope/schema mismatch")
                result.append(dict(record["frame"]))
        if len(result) != state["frame_count"]: raise DecisionLedgerV2Error("index total mismatch")
        return result

    def checkpoint(self) -> Dict[str, Any]:
        with _lock(self.lock_path):
            state = self._read_index(); self._verify_index_evidence_locked(state, repair_torn_tail=False)
            receipt = self._seal({"schema_version": CHECKPOINT_SCHEMA, "scope_sha256": self.scope_sha256, "index_sha256": state["index_sha256"], "frame_count": state["frame_count"], "status": "SHADOW_ONLY_CHECKPOINT"}, key="checkpoint_sha256")
            _atomic(self.checkpoint_path, receipt); return receipt

    def compact(self, checkpoint: Mapping[str, Any]) -> Dict[str, Any]:
        """Compact immutable segments only after a durable matching checkpoint.

        The receipt is persisted before the index swap and before any source
        segment is removed.  A crash between those steps therefore leaves an
        orphan that is fail-closed until :meth:`reconcile_compaction` is
        explicitly invoked.
        """
        with _lock(self.lock_path):
            state = self._read_index()
            source_scans = self._verify_index_evidence_locked(state, repair_torn_tail=False)
            durable_checkpoint = self._read_checkpoint_locked()
            if dict(checkpoint) != durable_checkpoint:
                raise DecisionLedgerV2Error("compaction requires the persisted checkpoint receipt")
            if (durable_checkpoint["index_sha256"] != state["index_sha256"] or
                    durable_checkpoint["frame_count"] != state["frame_count"]):
                raise DecisionLedgerV2Error("checkpoint does not cover current index")

            source_segments = [segment["path"] for segment in state["segments"]]
            if len(source_segments) <= 1:
                return {"schema_version": COMPACTION_RECEIPT_SCHEMA, "status": "SHADOW_ONLY_COMPACTION_NOT_NEEDED", "index_sha256": state["index_sha256"], "frame_count": state["frame_count"]}
            compacted_path = f"segments/compact-{state['index_sha256'][:16]}.fwal"
            compacted_wal = FramedWAL(self.root / compacted_path)
            scan = compacted_wal.initialize(repair_uncommitted_tail=False)
            if scan.records:
                raise DecisionLedgerV2Error("compaction target already contains evidence")
            records = [item["record"] for source_scan in source_scans for item in source_scan.records]
            envelopes = compacted_wal.append_many_cached_under_external_lock(records)
            compacted_segment = {"path": compacted_path, "frame_count": len(envelopes), "last_frame_sha256": _sha(envelopes[-1])}
            compacted_state = self._seal({
                **{key: value for key, value in state.items() if key not in {"index_sha256", "segments", "status", "compaction"}},
                "segments": [compacted_segment],
                "status": "SHADOW_ONLY_COMPACTION_PENDING_CLEANUP",
                "compaction": {"source_index_sha256": state["index_sha256"], "checkpoint_sha256": durable_checkpoint["checkpoint_sha256"]},
            })
            receipt_material = {
                "schema_version": COMPACTION_RECEIPT_SCHEMA,
                "scope_sha256": self.scope_sha256,
                "checkpoint_sha256": durable_checkpoint["checkpoint_sha256"],
                "source_index_sha256": state["index_sha256"],
                "compacted_index_sha256": compacted_state["index_sha256"],
                "source_segment_paths": source_segments,
                "compacted_segment_path": compacted_path,
                "frame_count": state["frame_count"],
                "status": "SHADOW_ONLY_COMPACTION_ACCEPTED",
            }
            receipt = self._seal(receipt_material, key="receipt_sha256")
            receipt_path = self._compaction_receipt_path(receipt)
            _atomic(receipt_path, receipt)
            _atomic(self.index_path, compacted_state)
            self._state = compacted_state; self._validated_index_sha256 = compacted_state["index_sha256"]
            self._delete_segments_locked(source_segments)
            return receipt

    def recover(self) -> Dict[str, Any]:
        """Repair torn tails only; never implicitly rebuild or absorb evidence."""
        with _lock(self.lock_path):
            return self._recover_locked()

    def _recover_locked(self) -> Dict[str, Any]:
        state = self._read_index()
        self._verify_index_evidence_locked(state, repair_torn_tail=True)
        self._state = state; self._validated_index_sha256 = state["index_sha256"]
        return dict(state)

    def reconcile_compaction(self) -> Dict[str, Any]:
        """Explicitly remove only receipt-authorized compaction orphans."""
        with _lock(self.lock_path):
            state = self._read_index()
            indexed_paths = {segment["path"] for segment in state["segments"]}
            physical_paths = self._physical_segment_paths_locked()
            orphan_paths = physical_paths - indexed_paths
            if not orphan_paths:
                self._verify_index_evidence_locked(state, repair_torn_tail=False)
                return {"schema_version": COMPACTION_RECEIPT_SCHEMA, "status": "SHADOW_ONLY_RECONCILIATION_NOT_NEEDED", "index_sha256": state["index_sha256"]}
            receipt = self._find_compaction_receipt_locked(state, orphan_paths)
            source_paths = set(receipt["source_segment_paths"])
            compacted_path = receipt["compacted_segment_path"]
            if state["index_sha256"] == receipt["source_index_sha256"]:
                allowed = {compacted_path}
                status = "SHADOW_ONLY_COMPACTION_ROLLBACK_RECONCILED"
            elif state["index_sha256"] == receipt["compacted_index_sha256"]:
                allowed = source_paths
                status = "SHADOW_ONLY_COMPACTION_RECONCILED"
            else:
                raise DecisionLedgerV2Error("compaction receipt/index mismatch")
            if not orphan_paths <= allowed:
                raise DecisionLedgerV2Error("orphan segment requires explicit reconciliation receipt")
            self._delete_segments_locked(sorted(orphan_paths))
            self._verify_index_evidence_locked(state, repair_torn_tail=False)
            return {"schema_version": COMPACTION_RECEIPT_SCHEMA, "status": status, "index_sha256": state["index_sha256"], "reconciled_segments": sorted(orphan_paths)}

    def _read_checkpoint_locked(self) -> Dict[str, Any]:
        try:
            value = json.loads(self.checkpoint_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise DecisionLedgerV2Error("compaction requires a durable checkpoint receipt") from exc
        if (not isinstance(value, dict) or value.get("schema_version") != CHECKPOINT_SCHEMA or
                value.get("scope_sha256") != self.scope_sha256):
            raise DecisionLedgerV2Error("checkpoint schema/scope mismatch")
        expected = self._seal(value, key="checkpoint_sha256")
        if value.get("checkpoint_sha256") != expected["checkpoint_sha256"]:
            raise DecisionLedgerV2Error("checkpoint self-hash mismatch")
        return value

    def _compaction_receipt_path(self, receipt: Mapping[str, Any]) -> Path:
        return self.root / "compaction_receipts" / f"{receipt['compacted_index_sha256']}.json"

    def _find_compaction_receipt_locked(self, state: Mapping[str, Any], orphan_paths: set[str]) -> Dict[str, Any]:
        receipt_dir = self.root / "compaction_receipts"
        if not receipt_dir.exists():
            raise DecisionLedgerV2Error("orphan segment requires explicit reconciliation receipt")
        matches: list[Dict[str, Any]] = []
        for path in receipt_dir.glob("*.json"):
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise DecisionLedgerV2Error("compaction receipt is invalid") from exc
            if not isinstance(value, dict) or value.get("schema_version") != COMPACTION_RECEIPT_SCHEMA:
                continue
            expected = self._seal(value, key="receipt_sha256")
            if value.get("receipt_sha256") != expected["receipt_sha256"]:
                raise DecisionLedgerV2Error("compaction receipt self-hash mismatch")
            if value.get("scope_sha256") != self.scope_sha256:
                continue
            if state["index_sha256"] == value.get("source_index_sha256"):
                allowed = {value.get("compacted_segment_path")}
            elif state["index_sha256"] == value.get("compacted_index_sha256"):
                allowed = set(value.get("source_segment_paths", []))
            else:
                continue
            if orphan_paths <= allowed:
                matches.append(value)
        if len(matches) != 1:
            raise DecisionLedgerV2Error("orphan segment requires one explicit reconciliation receipt")
        return matches[0]

    def _physical_segment_paths_locked(self) -> set[str]:
        segments_dir = self.root / "segments"
        if not segments_dir.exists():
            return set()
        return {path.relative_to(self.root).as_posix() for path in segments_dir.glob("*.fwal")}

    def _delete_segments_locked(self, paths: Iterable[str]) -> None:
        for relative in paths:
            target = self.root / relative
            if target.exists():
                target.unlink()
        segments_dir = self.root / "segments"
        if segments_dir.exists():
            descriptor = None
            try:
                descriptor = os.open(str(segments_dir), os.O_RDONLY); os.fsync(descriptor)
            except OSError:
                pass
            finally:
                if descriptor is not None: os.close(descriptor)

    def _verify_index_evidence_locked(self, state: Mapping[str, Any], *, repair_torn_tail: bool) -> list[Any]:
        self._validate_index_shape(state)
        indexed_paths = {segment["path"] for segment in state["segments"]}
        physical_paths = self._physical_segment_paths_locked()
        missing = indexed_paths - physical_paths
        if missing:
            raise DecisionLedgerV2Error("indexed segment is missing")
        orphaned = physical_paths - indexed_paths
        if orphaned:
            raise DecisionLedgerV2Error("orphan segment requires explicit reconciliation")
        scans = []
        for segment in state["segments"]:
            scan = FramedWAL(self.root / segment["path"]).initialize(repair_uncommitted_tail=repair_torn_tail)
            if len(scan.records) != segment["frame_count"]:
                raise DecisionLedgerV2Error("segment/index frame count mismatch")
            if scan.last_frame_sha256 != segment["last_frame_sha256"]:
                raise DecisionLedgerV2Error("segment/index last-frame mismatch")
            for record in scan.records:
                if record["record"].get("scope_sha256") != self.scope_sha256:
                    raise DecisionLedgerV2Error("foreign scope segment")
            scans.append(scan)
        if sum(len(scan.records) for scan in scans) != state["frame_count"]:
            raise DecisionLedgerV2Error("index total mismatch")
        return scans

    def _verify_append_evidence_locked(self, state: Mapping[str, Any]) -> None:
        """Keep steady-state append bounded while retaining crash fail-closed checks."""
        self._validate_index_shape(state)
        indexed_paths = {segment["path"] for segment in state["segments"]}
        physical_paths = self._physical_segment_paths_locked()
        if indexed_paths - physical_paths:
            raise DecisionLedgerV2Error("indexed segment is missing")
        if physical_paths - indexed_paths:
            raise DecisionLedgerV2Error("orphan segment requires explicit reconciliation")
        if self._validated_index_sha256 != state["index_sha256"]:
            self._verify_index_evidence_locked(state, repair_torn_tail=False)
            self._validated_index_sha256 = state["index_sha256"]
            return
        if state["segments"] and state["segments"][-1]["frame_count"] < state["segment_max_frames"]:
            segment = state["segments"][-1]
            scan = FramedWAL(self.root / segment["path"]).initialize(repair_uncommitted_tail=False)
            if len(scan.records) != segment["frame_count"]:
                raise DecisionLedgerV2Error("segment/index frame count mismatch")
            if scan.last_frame_sha256 != segment["last_frame_sha256"]:
                raise DecisionLedgerV2Error("segment/index last-frame mismatch")
            if any(record["record"].get("scope_sha256") != self.scope_sha256 for record in scan.records):
                raise DecisionLedgerV2Error("foreign scope segment")

    def _validate_index_shape(self, state: Mapping[str, Any]) -> None:
        segments = state.get("segments")
        if not isinstance(segments, list) or not isinstance(state.get("frame_count"), int) or state["frame_count"] < 0:
            raise DecisionLedgerV2Error("index segment schema mismatch")
        paths: set[str] = set(); counted = 0
        for segment in segments:
            if not isinstance(segment, dict) or set(segment) != {"path", "frame_count", "last_frame_sha256"}:
                raise DecisionLedgerV2Error("index segment schema mismatch")
            path = segment["path"]
            if not isinstance(path, str) or not path.startswith("segments/") or "/" in path[len("segments/"):]:
                raise DecisionLedgerV2Error("index segment path mismatch")
            if not path.endswith(".fwal") or path in paths:
                raise DecisionLedgerV2Error("index segment path mismatch")
            count = segment["frame_count"]
            if not isinstance(count, int) or isinstance(count, bool) or count <= 0:
                raise DecisionLedgerV2Error("index segment frame count mismatch")
            if count > state["segment_max_frames"] and not Path(path).name.startswith("compact-"):
                raise DecisionLedgerV2Error("index segment exceeds configured bound")
            _hex_sha256(segment["last_frame_sha256"], "index last_frame_sha256")
            paths.add(path); counted += count
        if counted != state["frame_count"]:
            raise DecisionLedgerV2Error("index total mismatch")

    @staticmethod
    def _reject_raw_fields(value: Any) -> None:
        if isinstance(value, Mapping):
            for key, item in value.items():
                lowered = str(key).lower()
                if "raw_prompt" in lowered or "raw_response" in lowered:
                    raise DecisionLedgerV2Error("raw prompt/response is forbidden")
                DecisionCallLedgerV2._reject_raw_fields(item)
        elif isinstance(value, (list, tuple)):
            for item in value: DecisionCallLedgerV2._reject_raw_fields(item)

    @staticmethod
    def _seal(value: Mapping[str, Any], *, key: str = "index_sha256") -> Dict[str, Any]:
        material = dict(value); material.pop(key, None); return {**material, key: _sha(material)}

    def _read_index(self) -> Dict[str, Any]:
        try: value = json.loads(self.index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc: raise DecisionLedgerV2Error("index missing or invalid") from exc
        if not isinstance(value, dict) or value.get("schema_version") != SCHEMA or value.get("scope_sha256") != self.scope_sha256: raise DecisionLedgerV2Error("index schema/scope mismatch")
        expected = self._seal(value)
        if value.get("index_sha256") != expected["index_sha256"]: raise DecisionLedgerV2Error("index self-hash mismatch")
        return value
