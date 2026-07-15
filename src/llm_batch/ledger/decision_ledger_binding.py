from __future__ import annotations

"""Cross-run/arm/scope binding sidecar for a shadow DecisionCallLedgerV2."""

from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping
import uuid

from .decision_ledger_v2 import DecisionCallLedgerV2, DecisionLedgerV2Error


SCHEMA = "decision_ledger_v2_shadow_binding_v1"


class DecisionLedgerBindingError(ValueError):
    pass


def _bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _sha(value: Any) -> str:
    return hashlib.sha256(_bytes(value)).hexdigest()


@dataclass(frozen=True)
class ArtifactRef:
    path: str
    bytes: int
    sha256: str

    @classmethod
    def snapshot(cls, path: Path) -> "ArtifactRef":
        path = path.resolve(); raw = path.read_bytes()
        return cls(str(path), len(raw), hashlib.sha256(raw).hexdigest())

    def validate(self) -> None:
        if not self.path or self.bytes < 0 or len(self.sha256) != 64 or any(ch not in "0123456789abcdef" for ch in self.sha256):
            raise DecisionLedgerBindingError("artifact reference shape mismatch")
        if type(self).snapshot(Path(self.path)) != self:
            raise DecisionLedgerBindingError(f"artifact bytes mismatch: {self.path}")


def _atomic(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True); temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(_bytes(value) + b"\n"); handle.flush(); os.fsync(handle.fileno())
        os.replace(temporary, path)
        descriptor = None
        try: descriptor = os.open(str(path.parent), os.O_RDONLY); os.fsync(descriptor)
        except OSError: pass
        finally:
            if descriptor is not None: os.close(descriptor)
    finally: temporary.unlink(missing_ok=True)


def build_shadow_binding(*, ledger: DecisionCallLedgerV2, output_path: Path, run_id: str, pair_id: str, arm: str, run_spec_path: Path, publication_scope_path: Path, attempt_path: Path) -> dict[str, Any]:
    if not isinstance(ledger, DecisionCallLedgerV2): raise DecisionLedgerBindingError("ledger must be DecisionCallLedgerV2")
    if arm not in {"BEFORE", "AFTER"} or not str(run_id).strip() or not str(pair_id).strip():
        raise DecisionLedgerBindingError("run_id, pair_id and BEFORE/AFTER arm are required")
    state = ledger.initialize(); checkpoint = ledger.checkpoint(); frames = ledger.replay()
    refs = {"run_spec": asdict(ArtifactRef.snapshot(run_spec_path)), "publication_scope": asdict(ArtifactRef.snapshot(publication_scope_path)), "attempt": asdict(ArtifactRef.snapshot(attempt_path)), "ledger_index": asdict(ArtifactRef.snapshot(ledger.index_path)), "ledger_checkpoint": asdict(ArtifactRef.snapshot(ledger.checkpoint_path))}
    material = {"schema_version": SCHEMA, "mode": "SHADOW_ONLY_NOT_RUNTIME_WIRED", "run_id": str(run_id), "pair_id": str(pair_id), "arm": arm, "ledger_root": str(ledger.root.resolve()), "ledger_scope_sha256": ledger.scope_sha256, "artifacts": refs, "index_sha256": state["index_sha256"], "checkpoint_sha256": checkpoint["checkpoint_sha256"], "frame_count": len(frames), "replay_sha256": _sha(frames), "gate": "GO_DECISION_LEDGER_V2_SHADOW_BINDING_ONLY"}
    value = {**material, "binding_sha256": _sha(material)}; _atomic(output_path, value); return value


def read_shadow_binding(value: Mapping[str, Any]) -> dict[str, Any]:
    required = {"schema_version", "mode", "run_id", "pair_id", "arm", "ledger_root", "ledger_scope_sha256", "artifacts", "index_sha256", "checkpoint_sha256", "frame_count", "replay_sha256", "gate", "binding_sha256"}
    if not isinstance(value, Mapping) or set(value) != required or value.get("schema_version") != SCHEMA or value.get("mode") != "SHADOW_ONLY_NOT_RUNTIME_WIRED" or value.get("gate") != "GO_DECISION_LEDGER_V2_SHADOW_BINDING_ONLY":
        raise DecisionLedgerBindingError("binding schema/mode/gate mismatch")
    if value.get("arm") not in {"BEFORE", "AFTER"} or not str(value.get("run_id") or "").strip() or not str(value.get("pair_id") or "").strip():
        raise DecisionLedgerBindingError("binding run/pair/arm mismatch")
    material = {key: value[key] for key in required if key != "binding_sha256"}
    if value.get("binding_sha256") != _sha(material): raise DecisionLedgerBindingError("binding self-hash mismatch")
    try:
        refs = {name: ArtifactRef(**dict(value["artifacts"][name])) for name in ("run_spec", "publication_scope", "attempt", "ledger_index", "ledger_checkpoint")}
    except (TypeError, KeyError, ValueError) as exc: raise DecisionLedgerBindingError("binding artifact shape mismatch") from exc
    for ref in refs.values(): ref.validate()
    try:
        ledger = DecisionCallLedgerV2(Path(str(value["ledger_root"])), scope_sha256=str(value["ledger_scope_sha256"])); state = ledger.initialize(); frames = ledger.replay()
    except (DecisionLedgerV2Error, OSError) as exc: raise DecisionLedgerBindingError(str(exc)) from exc
    if state["index_sha256"] != value["index_sha256"] or len(frames) != value["frame_count"] or _sha(frames) != value["replay_sha256"]:
        raise DecisionLedgerBindingError("ledger index/replay binding mismatch")
    try:
        checkpoint = json.loads(ledger.checkpoint_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc: raise DecisionLedgerBindingError("durable checkpoint missing") from exc
    if checkpoint.get("checkpoint_sha256") != value["checkpoint_sha256"]:
        raise DecisionLedgerBindingError("checkpoint binding mismatch")
    return {"schema_version": SCHEMA, "run_id": value["run_id"], "pair_id": value["pair_id"], "arm": value["arm"], "frame_count": len(frames), "gate": value["gate"], "independent_readback": "GO_DECISION_LEDGER_V2_SHADOW_BINDING"}
