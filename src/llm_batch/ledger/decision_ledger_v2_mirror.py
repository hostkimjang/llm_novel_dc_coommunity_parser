from __future__ import annotations

"""Read-only legacy DecisionCallLedger -> isolated V2 shadow mirror.

This module never writes the legacy registry and never participates in its
row/production decisions.  It creates a fresh V2 artifact only after the
legacy ledger has been read back and validated by its own registry code.
"""

import hashlib
import json
from pathlib import Path
import shutil
import tempfile
from typing import Any, Mapping

from .decision_call_events import DecisionCallLedgerRegistry
from .decision_ledger_binding import ArtifactRef, build_shadow_binding, read_shadow_binding
from .decision_ledger_v2 import DecisionCallLedgerV2, DecisionLedgerV2Error, replay_legacy_readback_to_v2


SCHEMA = "decision_ledger_v2_postrun_mirror_v1"


class DecisionLedgerV2MirrorError(ValueError):
    pass


def _bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _sha(value: Any) -> str:
    return hashlib.sha256(_bytes(value)).hexdigest()


def _atomic(path: Path, value: Mapping[str, Any]) -> None:
    from .decision_ledger_binding import _atomic as write
    write(path, value)


def _legacy_config(path: Path) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    source = Path(path).resolve(); scope_path = source / "scope.json"
    try: scope = json.loads(scope_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc: raise DecisionLedgerV2MirrorError("legacy scope sidecar is required") from exc
    if not isinstance(scope, dict) or not isinstance(scope.get("publication_scope_descriptor"), dict) or not isinstance(scope.get("measurement_bindings"), dict):
        raise DecisionLedgerV2MirrorError("legacy scope schema mismatch")
    return source, scope, dict(scope["measurement_bindings"])


def _legacy_readback(path: Path) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    """Validate legacy frames from an isolated clone so source stays read-only."""
    source, scope, measurement = _legacy_config(path)
    with tempfile.TemporaryDirectory(prefix="decision-ledger-v2-mirror-") as sandbox:
        copied = Path(sandbox) / "legacy"; shutil.copytree(source, copied)
        try:
            registry = DecisionCallLedgerRegistry(
                copied, scope_descriptor=scope["publication_scope_descriptor"], create_new=False, enabled=True,
                run_spec_sha256=measurement.get("run_spec_sha256"), pair_id=measurement.get("pair_id"), arm=measurement.get("arm"), fresh_execution_mode=measurement.get("fresh_execution_mode"), stage_allowlist=scope.get("stage_allowlist"),
            )
            return source, scope, registry.readback()
        except Exception as exc: raise DecisionLedgerV2MirrorError(f"legacy registry readback open failed: {type(exc).__name__}") from exc


def _require_disjoint(source: Path, target: Path) -> None:
    if target == source or source in target.parents:
        raise DecisionLedgerV2MirrorError("mirror output root must be outside legacy root")


def mirror(*, legacy_root: Path, output_root: Path, run_id: str, run_spec_path: Path, publication_scope_path: Path, attempt_path: Path, segment_max_frames: int = 256) -> dict[str, Any]:
    if not str(run_id).strip(): raise DecisionLedgerV2MirrorError("run_id is required")
    source = Path(legacy_root).resolve(); target = Path(output_root).resolve(); _require_disjoint(source, target)
    if target.exists(): raise FileExistsError(target)
    source, scope_sidecar, readback = _legacy_readback(source)
    scope = readback.get("scope") if isinstance(readback, dict) else None
    if not isinstance(scope, dict) or not isinstance(scope.get("scope_sha256"), str): raise DecisionLedgerV2MirrorError("legacy readback scope mismatch")
    measurement = scope.get("measurement_bindings")
    if not isinstance(measurement, dict) or measurement.get("arm") not in {"BEFORE", "AFTER"} or not str(measurement.get("pair_id") or "").strip():
        raise DecisionLedgerV2MirrorError("legacy pair/arm binding is required")
    ledger = DecisionCallLedgerV2(target / "ledger_v2", scope_sha256=scope["scope_sha256"], segment_max_frames=segment_max_frames)
    try: replay_receipt = replay_legacy_readback_to_v2(ledger, readback)
    except DecisionLedgerV2Error as exc: raise DecisionLedgerV2MirrorError(str(exc)) from exc
    binding = build_shadow_binding(ledger=ledger, output_path=target / "binding.json", run_id=str(run_id), pair_id=str(measurement["pair_id"]), arm=str(measurement["arm"]), run_spec_path=run_spec_path, publication_scope_path=publication_scope_path, attempt_path=attempt_path)
    material = {
        "schema_version": SCHEMA, "mode": "POSTRUN_SHADOW_MIRROR_NOT_RUNTIME_WIRED",
        "runtime_started": False, "writes_to_production": False, "legacy_registry_write": False,
        "run_id": str(run_id), "pair_id": str(measurement["pair_id"]), "arm": str(measurement["arm"]),
        "legacy_scope": ArtifactRef.snapshot(source / "scope.json").__dict__,
        "legacy_readback_sha256": _sha(readback), "v2_binding": ArtifactRef.snapshot(target / "binding.json").__dict__,
        "replay_receipt": replay_receipt, "frame_count": replay_receipt["frame_count"],
        "gate": "GO_DECISION_LEDGER_V2_POSTRUN_MIRROR_ONLY",
    }
    value = {**material, "mirror_sha256": _sha(material)}; _atomic(target / "mirror.json", value); return value


def read(value: Mapping[str, Any]) -> dict[str, Any]:
    required = {"schema_version", "mode", "runtime_started", "writes_to_production", "legacy_registry_write", "run_id", "pair_id", "arm", "legacy_scope", "legacy_readback_sha256", "v2_binding", "replay_receipt", "frame_count", "gate", "mirror_sha256"}
    if not isinstance(value, Mapping) or set(value) != required or value.get("schema_version") != SCHEMA or value.get("mode") != "POSTRUN_SHADOW_MIRROR_NOT_RUNTIME_WIRED" or value.get("runtime_started") is not False or value.get("writes_to_production") is not False or value.get("legacy_registry_write") is not False or value.get("gate") != "GO_DECISION_LEDGER_V2_POSTRUN_MIRROR_ONLY":
        raise DecisionLedgerV2MirrorError("mirror schema/gate mismatch")
    material = {key: value[key] for key in required if key != "mirror_sha256"}
    if value.get("mirror_sha256") != _sha(material): raise DecisionLedgerV2MirrorError("mirror self-hash mismatch")
    try:
        scope_ref = ArtifactRef(**dict(value["legacy_scope"])); binding_ref = ArtifactRef(**dict(value["v2_binding"])); scope_ref.validate(); binding_ref.validate()
        source, scope_sidecar, readback = _legacy_readback(Path(scope_ref.path).parent)
        binding = json.loads(Path(binding_ref.path).read_text(encoding="utf-8")); binding_readback = read_shadow_binding(binding)
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc: raise DecisionLedgerV2MirrorError(str(exc)) from exc
    receipt = value["replay_receipt"]
    measurement = scope_sidecar.get("measurement_bindings")
    expected_ledger_root = (Path(binding_ref.path).resolve().parent / "ledger_v2").resolve()
    artifacts = binding.get("artifacts") if isinstance(binding, dict) else None
    if not isinstance(receipt, dict) or not isinstance(measurement, dict) or value.get("arm") not in {"BEFORE", "AFTER"} or binding_readback.get("run_id") != value.get("run_id") or binding_readback.get("pair_id") != value.get("pair_id") or binding_readback.get("arm") != value.get("arm") or value.get("pair_id") != measurement.get("pair_id") or value.get("arm") != measurement.get("arm") or not isinstance(artifacts, dict) or Path(str(artifacts.get("ledger_index", {}).get("path") or "")).resolve() != expected_ledger_root / "index.json" or Path(str(artifacts.get("ledger_checkpoint", {}).get("path") or "")).resolve() != expected_ledger_root / "checkpoint.json" or not isinstance(binding.get("ledger_root"), str) or Path(binding["ledger_root"]).resolve() != expected_ledger_root or not isinstance(binding.get("ledger_scope_sha256"), str) or binding.get("ledger_scope_sha256") != readback.get("scope", {}).get("scope_sha256") or receipt.get("equivalent") is not True or receipt.get("legacy_frames_sha256") != receipt.get("v2_replay_sha256") or value.get("legacy_readback_sha256") != _sha(readback) or value.get("frame_count") != len(readback.get("frames", [])) or binding_readback.get("frame_count") != value.get("frame_count"):
        raise DecisionLedgerV2MirrorError("legacy/v2 mirror equivalence mismatch")
    return {"schema_version": SCHEMA, "gate": value["gate"], "frame_count": value["frame_count"], "runtime_started": False, "writes_to_production": False, "independent_readback": "GO_DECISION_LEDGER_V2_POSTRUN_MIRROR"}
