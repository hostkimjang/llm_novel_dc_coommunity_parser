"""OFF-by-default legacy-first DecisionLedgerV2 shadow dual writer.

The existing :class:`DecisionCallLedgerRegistry` remains authoritative.  This
adapter calls it first and returns its exact result.  A V2 failure can disable
only the shadow path; it must never alter a provider result, row closure, or
publication link.  Explicit disable is a rollback: legacy evidence is kept and
the V2 directory is preserved for audit instead of being deleted.
"""

from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import threading
import time
from typing import Any, Callable, Mapping

from .decision_call_events import DecisionCallLedgerRegistry
from .decision_ledger_v2 import DecisionCallLedgerV2
from .framed_wal import FramedWAL


SCHEMA = "decision_ledger_v2_dual_write_control_v1"
RECEIPT_SCHEMA = "decision_ledger_v2_dual_write_receipt_v1"
ROLLBACK_LATCH_SCHEMA = "decision_ledger_v2_rollback_latch_v1"
EVIDENCE_LATCH_SCHEMA = "decision_ledger_v2_evidence_incomplete_latch_v1"
_WRITE_METHODS = frozenset(
    {"record_dispatch_intent", "record_terminal", "seal_row", "abort_row", "link_publication"}
)


class _CoordinationLockError(RuntimeError):
    pass


@contextmanager
def _coordination_lock(path: Path):
    """Serialize legacy commit+mirror and reconcile across adapter instances."""

    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        handle = path.open("a+b")
    except OSError as exc:
        raise _CoordinationLockError("dual-write coordination lock open failed") from exc
    with handle:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
            os.fsync(handle.fileno())
        handle.seek(0, os.SEEK_SET)
        deadline = time.monotonic() + 30.0
        if os.name == "nt":
            import msvcrt

            while True:
                try:
                    handle.seek(0, os.SEEK_SET)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError as exc:
                    if time.monotonic() >= deadline:
                        raise _CoordinationLockError("dual-write coordination lock timeout") from exc
                    time.sleep(0.01)
            try:
                yield
            finally:
                handle.seek(0, os.SEEK_SET)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            while True:
                try:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError as exc:
                    if time.monotonic() >= deadline:
                        raise _CoordinationLockError("dual-write coordination lock timeout") from exc
                    time.sleep(0.01)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _atomic(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(
        f".{path.name}.{os.getpid()}.{threading.get_ident()}.{time.time_ns()}.tmp"
    )
    try:
        with temporary.open("xb") as handle:
            handle.write(_canonical_bytes(dict(value)) + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        descriptor = None
        try:
            descriptor = os.open(str(path.parent), os.O_RDONLY)
            os.fsync(descriptor)
        except OSError:
            pass
        finally:
            if descriptor is not None:
                os.close(descriptor)
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_create_once(path: Path, value: Mapping[str, Any]) -> None:
    """Create one immutable marker and never replace an existing marker."""

    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(_canonical_bytes(dict(value)) + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        descriptor = None
        try:
            descriptor = os.open(str(path.parent), os.O_RDONLY)
            os.fsync(descriptor)
        except OSError:
            pass
        finally:
            if descriptor is not None:
                os.close(descriptor)
    except FileExistsError:
        return


def _sealed_marker(schema: str, reason_code: str, binding: Mapping[str, Any]) -> dict[str, Any]:
    material = {
        "schema_version": schema,
        "reason_code": str(reason_code),
        "binding": dict(binding),
    }
    return {**material, "marker_sha256": _sha(material)}


def _read_marker(path: Path, schema: str, binding: Mapping[str, Any]) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    required = {"schema_version", "reason_code", "binding", "marker_sha256"}
    if not isinstance(value, Mapping) or set(value) != required:
        raise ValueError("dual-write marker schema mismatch")
    material = {key: value[key] for key in required if key != "marker_sha256"}
    if value.get("schema_version") != schema or value.get("marker_sha256") != _sha(material):
        raise ValueError("dual-write marker self-hash mismatch")
    if value.get("binding") != dict(binding):
        raise ValueError("dual-write marker binding mismatch")
    if not str(value.get("reason_code") or "").strip():
        raise ValueError("dual-write marker reason is missing")
    return dict(value)


class DecisionLedgerV2DualWriteAdapter:
    """Proxy a legacy ledger and optionally mirror newly created frames to V2."""

    def __init__(
        self,
        legacy: DecisionCallLedgerRegistry,
        *,
        v2_root: str | Path | None = None,
        shadow_enabled: bool = False,
        reconcile_on_start: bool = True,
        attempt_run_id: str | None = None,
        output_attempt_sha256: str | None = None,
    ) -> None:
        if not isinstance(legacy, DecisionCallLedgerRegistry):
            raise TypeError("legacy must be DecisionCallLedgerRegistry")
        self.legacy = legacy
        self._lock = threading.RLock()
        self._v2: DecisionCallLedgerV2 | None = None
        self._receipt_wal: FramedWAL | None = None
        self._shadow_active = False
        self._shadow_reason = "OFF_BY_DEFAULT"
        self._control_path: Path | None = None
        self._coordination_lock_path: Path | None = None
        self._rollback_latch_path: Path | None = None
        self._evidence_latch_path: Path | None = None
        self._binding: dict[str, Any] | None = None
        self._rollback_persisted: bool | None = None
        self._control_persisted: bool | None = None
        self._rollback_persist_error: str | None = None
        self._control_persist_error: str | None = None
        self._shadow_evidence_complete = True
        self._shadow_evidence_reason: str | None = None
        if not shadow_enabled:
            return
        if not legacy.enabled or legacy.path is None:
            self._shadow_reason = "LEGACY_LEDGER_NOT_ENABLED"
            return
        if v2_root is None:
            self._shadow_reason = "V2_ROOT_REQUIRED"
            return
        try:
            root = Path(v2_root).resolve()
            legacy_root = legacy.path.resolve()
            if root == legacy_root or root in legacy_root.parents or legacy_root in root.parents:
                raise ValueError("V2 root must not overlap the authoritative legacy ledger")
            readback = legacy.readback()
            scope = readback.get("scope")
            if not isinstance(scope, Mapping):
                raise ValueError("legacy scope is unavailable")
            scope_sha256 = str(scope.get("scope_sha256") or "")
            measurement = dict(scope.get("measurement_bindings") or {})
            binding = {
                "legacy_scope_sha256": scope_sha256,
                "run_spec_sha256": measurement.get("run_spec_sha256"),
                "pair_id": measurement.get("pair_id"),
                "arm": measurement.get("arm"),
                "fresh_execution_mode": measurement.get("fresh_execution_mode"),
                "attempt_run_id": self._optional_identity(
                    attempt_run_id, "attempt_run_id"
                ),
                "output_attempt_sha256": self._optional_sha256(
                    output_attempt_sha256, "output_attempt_sha256"
                ),
            }
            control_path = root / "dual_write_control.json"
            self._coordination_lock_path = root / ".dual-write-coordination.lock"
            self._rollback_latch_path = root / "dual_write_disabled.latch.json"
            self._evidence_latch_path = root / "dual_write_evidence_incomplete.latch.json"
            self._control_path = control_path
            self._binding = binding
            if self._rollback_latch_path.exists():
                marker = _read_marker(
                    self._rollback_latch_path, ROLLBACK_LATCH_SCHEMA, binding
                )
                self._shadow_reason = str(marker["reason_code"])
                self._rollback_persisted = True
                self._control_persisted = control_path.exists()
                return
            if self._evidence_latch_path.exists():
                marker = _read_marker(
                    self._evidence_latch_path, EVIDENCE_LATCH_SCHEMA, binding
                )
                self._shadow_evidence_complete = False
                self._shadow_evidence_reason = str(marker["reason_code"])
            v2 = DecisionCallLedgerV2(root, scope_sha256=scope_sha256)
            v2.initialize(recover_torn_tail=False)
            receipt_wal = FramedWAL(root / "dual_write_receipts.fwal")
            receipt_wal.initialize(repair_uncommitted_tail=False)
            expected_control = self._sealed_control("ENABLED", "EXPLICIT_SHADOW_ENABLE", binding)
            if control_path.exists():
                stored = json.loads(control_path.read_text(encoding="utf-8"))
                self._validate_control(stored, binding)
                if stored["status"] == "DISABLED":
                    self._v2 = v2
                    self._receipt_wal = receipt_wal
                    self._shadow_reason = str(stored["reason_code"])
                    self._persist_rollback_latch(self._shadow_reason)
                    self._control_persisted = True
                    return
            else:
                _atomic(control_path, expected_control)
            self._v2 = v2
            self._receipt_wal = receipt_wal
            self._shadow_active = True
            self._shadow_reason = "ENABLED_EXPLICIT_SHADOW_ONLY"
            self._rollback_persisted = False
            self._control_persisted = True
            if reconcile_on_start:
                self.reconcile_from_legacy()
        except Exception as exc:  # shadow setup never invalidates the legacy writer
            self._shadow_active = False
            self._shadow_reason = f"SETUP_FAILED_{type(exc).__name__.upper()}"
            if self._rollback_latch_path is not None and self._binding is not None:
                self._persist_rollback_latch(self._shadow_reason)

    @staticmethod
    def _optional_identity(value: Any, field: str) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            raise ValueError(f"{field} must be non-empty when supplied")
        return text

    @staticmethod
    def _optional_sha256(value: Any, field: str) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
            raise ValueError(f"{field} must be a lowercase sha256 when supplied")
        return text

    @property
    def enabled(self) -> bool:
        """Preserve the legacy registry's public enabled contract."""

        return self.legacy.enabled

    @property
    def path(self) -> Path | None:
        return self.legacy.path

    @property
    def shadow_enabled(self) -> bool:
        return self._shadow_active

    @staticmethod
    def _sealed_control(status: str, reason_code: str, binding: Mapping[str, Any]) -> dict[str, Any]:
        material = {
            "schema_version": SCHEMA,
            "status": status,
            "reason_code": reason_code,
            "binding": dict(binding),
            "legacy_authoritative": True,
            "public_result_interference": False,
        }
        return {**material, "control_sha256": _sha(material)}

    @classmethod
    def _validate_control(cls, value: Any, binding: Mapping[str, Any]) -> None:
        required = {
            "schema_version", "status", "reason_code", "binding", "legacy_authoritative",
            "public_result_interference", "control_sha256",
        }
        if not isinstance(value, Mapping) or set(value) != required:
            raise ValueError("dual-write control schema mismatch")
        material = {key: value[key] for key in required if key != "control_sha256"}
        if value.get("schema_version") != SCHEMA or value.get("control_sha256") != _sha(material):
            raise ValueError("dual-write control self-hash mismatch")
        if value.get("status") not in {"ENABLED", "DISABLED"} or value.get("binding") != dict(binding):
            raise ValueError("dual-write control binding mismatch")
        if value.get("legacy_authoritative") is not True or value.get("public_result_interference") is not False:
            raise ValueError("dual-write control safety mismatch")

    def _append_receipt(
        self,
        *,
        event: str,
        status: str,
        frame: Mapping[str, Any] | None = None,
        identities: list[str] | None = None,
    ) -> None:
        if self._receipt_wal is None:
            return
        covered = list(identities or ())
        if frame is not None and frame.get("identity_sha256") is not None:
            covered.append(str(frame.get("identity_sha256")))
        covered = sorted(set(covered))
        record = {
            "schema_version": RECEIPT_SCHEMA,
            "event": event,
            "status": status,
            "legacy_authoritative": True,
            "public_result_interference": False,
            "frame_kind": None if frame is None else frame.get("frame_kind"),
            "identity_sha256": None if frame is None else frame.get("identity_sha256"),
            "identity_sha256s": covered,
            "identity_count": len(covered),
            "identity_set_sha256": _sha(covered),
            "binding_sha256": None if self._binding is None else _sha(self._binding),
        }
        try:
            self._receipt_wal.append(record)
        except Exception as exc:
            # Receipt failure is itself shadow-only.  The durable control file
            # is the rollback authority and legacy evidence has already won.
            self._mark_evidence_incomplete(
                f"RECEIPT_APPEND_FAILED_{type(exc).__name__.upper()}"
            )

    def _audit_receipt_coverage(self, legacy_frames: list[Mapping[str, Any]]) -> None:
        if self._receipt_wal is None or self._binding is None:
            self._mark_evidence_incomplete("RECEIPT_AUDIT_UNAVAILABLE")
            return
        try:
            scan = self._receipt_wal.initialize(repair_uncommitted_tail=False)
            covered: set[str] = set()
            expected_binding = _sha(self._binding)
            for envelope in scan.records:
                record = envelope.get("record")
                if not isinstance(record, Mapping) or record.get("schema_version") != RECEIPT_SCHEMA:
                    raise ValueError("receipt schema mismatch")
                identities = record.get("identity_sha256s")
                if not isinstance(identities, list) or identities != sorted(set(identities)):
                    raise ValueError("receipt identity list mismatch")
                if record.get("identity_count") != len(identities):
                    raise ValueError("receipt identity count mismatch")
                if record.get("identity_set_sha256") != _sha(identities):
                    raise ValueError("receipt identity set hash mismatch")
                if record.get("binding_sha256") != expected_binding:
                    raise ValueError("receipt binding mismatch")
                if record.get("event") in {"FRAME_MIRROR", "RECONCILE"}:
                    covered.update(str(identity) for identity in identities)
            expected = {str(frame["identity_sha256"]) for frame in legacy_frames}
            if covered != expected:
                raise ValueError("receipt coverage mismatch")
        except Exception as exc:
            self._mark_evidence_incomplete(
                f"RECEIPT_COVERAGE_FAILED_{type(exc).__name__.upper()}"
            )

    def _mark_evidence_incomplete(self, reason_code: str) -> None:
        self._shadow_evidence_complete = False
        self._shadow_evidence_reason = reason_code
        if self._evidence_latch_path is None or self._binding is None:
            return
        try:
            _atomic_create_once(
                self._evidence_latch_path,
                _sealed_marker(EVIDENCE_LATCH_SCHEMA, reason_code, self._binding),
            )
            marker = _read_marker(
                self._evidence_latch_path, EVIDENCE_LATCH_SCHEMA, self._binding
            )
            self._shadow_evidence_reason = str(marker["reason_code"])
        except Exception as exc:
            self._shadow_evidence_reason = (
                f"{reason_code}_MARKER_PERSIST_FAILED_{type(exc).__name__.upper()}"
            )

    def _persist_rollback_latch(self, reason_code: str) -> bool:
        if self._rollback_latch_path is None or self._binding is None:
            self._rollback_persisted = False
            self._rollback_persist_error = "ROLLBACK_LATCH_UNAVAILABLE"
            return False
        try:
            _atomic_create_once(
                self._rollback_latch_path,
                _sealed_marker(ROLLBACK_LATCH_SCHEMA, reason_code, self._binding),
            )
            marker = _read_marker(
                self._rollback_latch_path, ROLLBACK_LATCH_SCHEMA, self._binding
            )
            self._rollback_persisted = True
            self._rollback_persist_error = None
            self._shadow_reason = str(marker["reason_code"])
            return True
        except Exception as exc:
            self._rollback_persisted = False
            self._rollback_persist_error = (
                f"ROLLBACK_LATCH_PERSIST_FAILED_{type(exc).__name__.upper()}"
            )
            return False

    def _disable(self, reason_code: str) -> None:
        self._shadow_active = False
        self._shadow_reason = reason_code
        latch_persisted = self._persist_rollback_latch(reason_code)
        if self._control_path is not None and self._binding is not None:
            try:
                _atomic(
                    self._control_path,
                    self._sealed_control("DISABLED", reason_code, self._binding),
                )
                self._control_persisted = True
                self._control_persist_error = None
            except Exception as exc:
                self._control_persisted = False
                control_error = f"CONTROL_PERSIST_FAILED_{type(exc).__name__.upper()}"
                self._control_persist_error = control_error
                if not latch_persisted:
                    self._shadow_reason = (
                        f"{reason_code}_{self._rollback_persist_error}_{control_error}"
                    )
        if not latch_persisted and self._shadow_reason == reason_code:
            self._shadow_reason = f"{reason_code}_{self._rollback_persist_error}"
        self._append_receipt(event="SHADOW_DISABLE", status=reason_code)

    def _refresh_control_under_coordination_lock(self) -> bool:
        """Re-read cross-adapter rollback state while the root lock is held."""

        if self._control_path is None or self._binding is None:
            raise ValueError("dual-write control is unavailable")
        if self._rollback_latch_path is not None and self._rollback_latch_path.exists():
            marker = _read_marker(
                self._rollback_latch_path, ROLLBACK_LATCH_SCHEMA, self._binding
            )
            self._shadow_active = False
            self._shadow_reason = str(marker["reason_code"])
            self._rollback_persisted = True
            return False
        stored = json.loads(self._control_path.read_text(encoding="utf-8"))
        self._validate_control(stored, self._binding)
        if stored["status"] == "DISABLED":
            self._shadow_active = False
            self._shadow_reason = str(stored["reason_code"])
            return False
        return True

    def disable_shadow(self, reason_code: str = "OPERATOR_ROLLBACK") -> dict[str, Any]:
        with self._lock:
            normalized = str(reason_code or "OPERATOR_ROLLBACK").strip().upper()
            if self._coordination_lock_path is not None:
                try:
                    with _coordination_lock(self._coordination_lock_path):
                        self._disable(normalized)
                except _CoordinationLockError:
                    self._disable("COORDINATION_LOCK_FAILED_DURING_ROLLBACK")
            else:
                self._disable(normalized)
            return self.shadow_status()

    def _mirror_created_frame(self, frame: Mapping[str, Any]) -> None:
        if not self._shadow_active or self._v2 is None:
            return
        try:
            self._v2.append(frame)
            self._append_receipt(event="FRAME_MIRROR", status="V2_APPENDED", frame=frame)
        except Exception as exc:
            self._disable(f"V2_APPEND_FAILED_{type(exc).__name__.upper()}")

    def _wrapped_write(self, name: str, target: Callable[..., Any]) -> Callable[..., Any]:
        def call(*args: Any, **kwargs: Any) -> Any:
            # Serialize the authoritative legacy commit and its shadow mirror
            # with restart reconciliation.  Without this outer lock,
            # reconciliation can observe a newly committed legacy frame before
            # its mirror, append it, and race the original writer into a
            # duplicate V2 identity.
            def commit_and_mirror() -> Any:
                result = target(*args, **kwargs)
                try:
                    frame, created = result
                except (TypeError, ValueError):
                    self._disable("LEGACY_WRITE_RESULT_SCHEMA_MISMATCH")
                    return result
                if created and isinstance(frame, Mapping):
                    self._mirror_created_frame(frame)
                return result

            with self._lock:
                if not self._shadow_active or self._coordination_lock_path is None:
                    return target(*args, **kwargs)
                try:
                    with _coordination_lock(self._coordination_lock_path):
                        try:
                            if not self._refresh_control_under_coordination_lock():
                                return target(*args, **kwargs)
                        except Exception as exc:
                            self._disable(
                                f"CONTROL_REVALIDATION_FAILED_{type(exc).__name__.upper()}"
                            )
                            return target(*args, **kwargs)
                        return commit_and_mirror()
                except _CoordinationLockError:
                    # Acquisition failed before the legacy commit.  Disable
                    # only the shadow and execute the authoritative write once.
                    self._disable("COORDINATION_LOCK_FAILED")
                    return target(*args, **kwargs)

        return call

    def __getattr__(self, name: str) -> Any:
        target = getattr(self.legacy, name)
        if name in _WRITE_METHODS and callable(target):
            return self._wrapped_write(name, target)
        return target

    def readback(self) -> dict[str, Any]:
        """Keep existing consumers on the authoritative legacy readback."""

        return self.legacy.readback()

    def reconcile_from_legacy(self) -> dict[str, Any]:
        """Append only missing legacy frames after a clean V2 replay.

        Extra, changed, torn, or corrupt V2 evidence disables the shadow path.
        It is never automatically deleted or rewritten.
        """

        with self._lock:
            if not self._shadow_active or self._v2 is None:
                return self.shadow_status()
            try:
                if self._coordination_lock_path is None:
                    raise _CoordinationLockError("coordination lock unavailable")
                with _coordination_lock(self._coordination_lock_path):
                    if not self._refresh_control_under_coordination_lock():
                        return self.shadow_status()
                    legacy_frames = list(self.legacy.readback()["frames"])
                    v2_frames = self._v2.replay()
                    legacy_by_id = {str(frame["identity_sha256"]): frame for frame in legacy_frames}
                    v2_by_id = {str(frame["identity_sha256"]): frame for frame in v2_frames}
                    if len(legacy_by_id) != len(legacy_frames) or len(v2_by_id) != len(v2_frames):
                        raise ValueError("duplicate frame identity")
                    for identity, frame in v2_by_id.items():
                        if legacy_by_id.get(identity) != frame:
                            raise ValueError("V2 contains extra or changed evidence")
                    missing = [
                        frame
                        for frame in legacy_frames
                        if str(frame["identity_sha256"]) not in v2_by_id
                    ]
                    if missing:
                        self._v2.append_many(missing)
                    replayed = self._v2.replay()
                    if sorted(replayed, key=lambda item: (item["frame_kind"], item["identity_sha256"])) != legacy_frames:
                        raise ValueError("legacy/V2 replay mismatch")
                    self._append_receipt(
                        event="RECONCILE",
                        status="EQUIVALENT",
                        identities=[str(frame["identity_sha256"]) for frame in missing],
                    )
                    self._audit_receipt_coverage(legacy_frames)
                    return self.shadow_status()
            except Exception as exc:
                self._disable(f"V2_RECONCILE_FAILED_{type(exc).__name__.upper()}")
                return self.shadow_status()

    def shadow_status(self) -> dict[str, Any]:
        if (
            self._rollback_latch_path is not None
            and self._binding is not None
            and self._rollback_latch_path.exists()
        ):
            try:
                marker = _read_marker(
                    self._rollback_latch_path, ROLLBACK_LATCH_SCHEMA, self._binding
                )
                self._shadow_active = False
                self._shadow_reason = str(marker["reason_code"])
                self._rollback_persisted = True
            except Exception as exc:
                self._shadow_active = False
                self._shadow_reason = (
                    f"ROLLBACK_LATCH_INVALID_{type(exc).__name__.upper()}"
                )
                self._rollback_persisted = False
                self._rollback_persist_error = self._shadow_reason
        if (
            self._evidence_latch_path is not None
            and self._binding is not None
            and self._evidence_latch_path.exists()
        ):
            try:
                marker = _read_marker(
                    self._evidence_latch_path, EVIDENCE_LATCH_SCHEMA, self._binding
                )
                self._shadow_evidence_complete = False
                self._shadow_evidence_reason = str(marker["reason_code"])
            except Exception as exc:
                self._shadow_evidence_complete = False
                self._shadow_evidence_reason = (
                    f"EVIDENCE_LATCH_INVALID_{type(exc).__name__.upper()}"
                )
        frame_count = None
        index_sha256 = None
        if self._v2 is not None:
            try:
                state = self._v2.initialize(recover_torn_tail=False)
                frame_count = state["frame_count"]
                index_sha256 = state["index_sha256"]
            except Exception:
                pass
        attempt_bound = bool(
            self._binding is not None
            and self._binding.get("attempt_run_id")
            and self._binding.get("output_attempt_sha256")
        )
        return {
            "schema_version": "decision_ledger_v2_dual_write_status_v1",
            "shadow_enabled": self._shadow_active,
            "status": "SHADOW_ACTIVE" if self._shadow_active else "SHADOW_DISABLED",
            "reason_code": self._shadow_reason,
            "legacy_authoritative": True,
            "public_result_interference": False,
            "v2_frame_count": frame_count,
            "v2_index_sha256": index_sha256,
            "actual_metrics": None,
            "actual_metrics_eligible": False,
            "rollback_latched": bool(
                self._rollback_latch_path is not None
                and self._rollback_latch_path.exists()
            ),
            "rollback_persisted": self._rollback_persisted,
            "control_persisted": self._control_persisted,
            "rollback_persist_error": self._rollback_persist_error,
            "control_persist_error": self._control_persist_error,
            "shadow_evidence_complete": self._shadow_evidence_complete,
            "shadow_evidence_reason": self._shadow_evidence_reason,
            "attempt_binding_status": (
                "BOUND" if attempt_bound else "EXPLICIT_NULL_LIMITED"
            ),
        }


__all__ = ["DecisionLedgerV2DualWriteAdapter"]
