"""Durable typed ledger for physical model-call attempts.

The ledger is deliberately independent from result rows and the publication
decision WAL.  Every committed object is an immutable, self-hashed JSON frame
published with an exclusive atomic link.  Prompt and response bodies are never
accepted by this API; callers provide only their SHA-256 digests.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import threading
import time
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence, Tuple


LEDGER_SCOPE_SCHEMA = "decision_call_ledger_scope_v1"
ROW_ATTEMPT_SCHEMA = "decision_call_row_attempt_v1"
FRAME_SCHEMA = "decision_call_immutable_frame_v1"
SUMMARY_SCHEMA = "decision_call_ledger_summary_v1"
READBACK_SCHEMA = "decision_call_ledger_readback_v1"

FRAME_DISPATCH = "DISPATCH_INTENT"
FRAME_TERMINAL = "TERMINAL"
FRAME_ROW_SEAL = "ROW_SEAL"
FRAME_ROW_ABORT = "ROW_ABORT"
FRAME_PUBLICATION_LINK = "PUBLICATION_LINK"
FRAME_KINDS = frozenset(
    {
        FRAME_DISPATCH,
        FRAME_TERMINAL,
        FRAME_ROW_SEAL,
        FRAME_ROW_ABORT,
        FRAME_PUBLICATION_LINK,
    }
)

TERMINAL_STATUSES = frozenset({"SUCCEEDED", "FAILED", "CANCELLED", "UNKNOWN"})
USAGE_PROVENANCE_VALUES = frozenset(
    {"PROVIDER_REPORTED", "ESTIMATED", "UNAVAILABLE"}
)
MODALITIES = frozenset({"TEXT", "VLM"})
ARMS = frozenset({"BEFORE", "AFTER"})

DEFAULT_STAGE_ALLOWLIST: Tuple[str, ...] = (
    "ARBITER",
    "CRITIC",
    "DECODER",
    "DELIBERATION",
    "DISCOURSE",
    "FINAL_SEMANTIC_REREAD",
    "GATEKEEPER",
    "PAGE_ALIVE_CHECK",
    "PAGE_ANALYZER",
    "REASON_REVIEW",
    "SNIPPET_ANALYZER",
    "SYNTHESIZER",
    "VERIFIER",
    "VLM_OCR",
)

_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_LOCK_TIMEOUT_SECONDS = 30.0


class DecisionCallLedgerError(ValueError):
    """Base error for malformed, incomplete, or unsafe call ledgers."""


class DecisionCallLedgerConflict(DecisionCallLedgerError):
    """Raised when one immutable identity is reused with another payload."""


class DecisionCallLedgerIncomplete(DecisionCallLedgerError):
    """Raised when a row cannot be sealed because call evidence is incomplete."""


class DecisionCallLedgerDisabled(DecisionCallLedgerError):
    """Raised when a write is attempted while instrumentation is disabled."""


def _canonical_payload(value: Any) -> Any:
    if isinstance(value, Mapping):
        normalized: Dict[str, Any] = {}
        for key, item in value.items():
            text_key = str(key)
            if text_key in normalized:
                raise DecisionCallLedgerError(
                    f"canonical mapping key collision after string coercion: {text_key!r}"
                )
            normalized[text_key] = _canonical_payload(item)
        return {key: normalized[key] for key in sorted(normalized)}
    if isinstance(value, (list, tuple)):
        return [_canonical_payload(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise DecisionCallLedgerError(f"unsupported canonical value: {type(value).__name__}")


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        _canonical_payload(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _require_exact_keys(value: Mapping[str, Any], expected: Iterable[str], label: str) -> None:
    actual = set(value)
    required = set(expected)
    if actual != required:
        raise DecisionCallLedgerError(
            f"{label} fields mismatch: missing={sorted(required - actual)}, "
            f"extra={sorted(actual - required)}"
        )


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DecisionCallLedgerError(f"{field} must be a non-empty string")
    return value.strip()


def _optional_text(value: Any, field: str) -> Optional[str]:
    if value is None:
        return None
    return _text(value, field)


def _hex64(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _HEX64.fullmatch(value):
        raise DecisionCallLedgerError(f"{field} must be a lowercase sha256")
    return value


def _nonnegative_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise DecisionCallLedgerError(f"{field} must be a nonnegative int")
    return value


def _positive_int(value: Any, field: str) -> int:
    number = _nonnegative_int(value, field)
    if number == 0:
        raise DecisionCallLedgerError(f"{field} must be positive")
    return number


def _optional_nonnegative_int(value: Any, field: str) -> Optional[int]:
    if value is None:
        return None
    return _nonnegative_int(value, field)


def _strict_bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise DecisionCallLedgerError(f"{field} must be bool")
    return value


def _post_id(value: Any) -> int | str:
    if isinstance(value, bool) or value in (None, ""):
        raise DecisionCallLedgerError("post_id must be non-empty")
    if isinstance(value, int):
        if value <= 0:
            raise DecisionCallLedgerError("post_id must be positive")
        return value
    text = str(value).strip()
    if not text:
        raise DecisionCallLedgerError("post_id must be non-empty")
    try:
        number = int(text)
    except ValueError:
        return text
    if number <= 0:
        raise DecisionCallLedgerError("post_id must be positive")
    return number


def _iso_timestamp(value: Any, field: str) -> str:
    text = _text(value, field)
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise DecisionCallLedgerError(f"{field} must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise DecisionCallLedgerError(f"{field} must include timezone")
    return text


def _utc_now() -> str:
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


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


def _atomic_replace(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(
        f".{path.name}.{os.getpid()}.{threading.get_ident()}.{time.time_ns()}.tmp"
    )
    try:
        with temporary.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def _exclusive_publish(path: Path, payload: bytes) -> bool:
    """Atomically publish a fully fsynced immutable frame without replacement."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(
        f".{path.name}.{os.getpid()}.{threading.get_ident()}.{time.time_ns()}.tmp"
    )
    try:
        with temporary.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            return False
        except OSError as exc:
            raise DecisionCallLedgerError(
                f"atomic exclusive frame publish failed: {path}: {exc}"
            ) from exc
        _fsync_directory(path.parent)
        return True
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


@contextmanager
def _exclusive_file_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
            os.fsync(handle.fileno())
        handle.seek(0)
        deadline = time.monotonic() + _LOCK_TIMEOUT_SECONDS
        if os.name == "nt":
            import msvcrt

            while True:
                try:
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError as exc:
                    if time.monotonic() >= deadline:
                        raise DecisionCallLedgerError(f"ledger lock timeout: {path}") from exc
                    time.sleep(0.01)
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            while True:
                try:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError as exc:
                    if time.monotonic() >= deadline:
                        raise DecisionCallLedgerError(f"ledger lock timeout: {path}") from exc
                    time.sleep(0.01)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _normalize_scope_descriptor(value: Any) -> Dict[str, Any]:
    if hasattr(value, "validate") and callable(value.validate):
        value.validate()
    if hasattr(value, "to_dict") and callable(value.to_dict):
        value = value.to_dict()
    if not isinstance(value, Mapping):
        raise DecisionCallLedgerError("scope_descriptor must be PublicationScopeDescriptor-like")
    expected = {
        "schema_version",
        "publication_scope_id",
        "input_file_sha256",
        "post_ids",
        "config_hash",
        "release_fingerprint",
        "descriptor_sha256",
    }
    _require_exact_keys(value, expected, "publication scope descriptor")
    if value.get("schema_version") != "publication_scope_descriptor_v1":
        raise DecisionCallLedgerError("publication scope descriptor schema mismatch")
    input_hash = _hex64(value.get("input_file_sha256"), "input_file_sha256")
    raw_post_ids = value.get("post_ids")
    if not isinstance(raw_post_ids, (list, tuple)):
        raise DecisionCallLedgerError("scope post_ids must be a list")
    post_ids = tuple(_post_id(item) for item in raw_post_ids)
    if not post_ids or len(post_ids) != len(set(post_ids)):
        raise DecisionCallLedgerError("scope post_ids must be non-empty and unique")
    config_hash = _text(value.get("config_hash"), "config_hash")
    release = _optional_text(value.get("release_fingerprint"), "release_fingerprint")
    scope_id = _sha256(
        {
            "schema_version": "publication_scope_v1",
            "input_file_sha256": input_hash,
            "post_id_order": list(post_ids),
            "config_hash": config_hash,
            "release_fingerprint": release,
        }
    )
    if _hex64(value.get("publication_scope_id"), "publication_scope_id") != scope_id:
        raise DecisionCallLedgerError("publication scope descriptor scope mismatch")
    material = {
        "schema_version": "publication_scope_descriptor_v1",
        "publication_scope_id": scope_id,
        "input_file_sha256": input_hash,
        "post_ids": list(post_ids),
        "config_hash": config_hash,
        "release_fingerprint": release,
    }
    descriptor_sha = _hex64(value.get("descriptor_sha256"), "descriptor_sha256")
    if descriptor_sha != _sha256(material):
        raise DecisionCallLedgerError("publication scope descriptor hash mismatch")
    return {**material, "descriptor_sha256": descriptor_sha}


@dataclass(frozen=True, slots=True)
class RowAttemptScope:
    publication_scope_id: str
    attempt_run_id: str
    row_attempt_id: str
    input_index: int
    post_id: int | str
    schema_version: str = ROW_ATTEMPT_SCHEMA

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "publication_scope_id", _hex64(self.publication_scope_id, "publication_scope_id")
        )
        object.__setattr__(self, "attempt_run_id", _text(self.attempt_run_id, "attempt_run_id"))
        object.__setattr__(self, "row_attempt_id", _text(self.row_attempt_id, "row_attempt_id"))
        object.__setattr__(self, "input_index", _positive_int(self.input_index, "input_index"))
        object.__setattr__(self, "post_id", _post_id(self.post_id))
        if self.schema_version != ROW_ATTEMPT_SCHEMA:
            raise DecisionCallLedgerError("row attempt schema mismatch")

    @classmethod
    def from_dict(cls, value: Any) -> "RowAttemptScope":
        if not isinstance(value, Mapping):
            raise DecisionCallLedgerError("row attempt scope must be an object")
        _require_exact_keys(value, cls.__dataclass_fields__, "row attempt scope")
        return cls(**dict(value))

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DecisionCallLedgerRegistry:
    """Immutable-frame CAS registry for physical model-call evidence."""

    def __init__(
        self,
        path: str | Path | None = None,
        *,
        scope_descriptor: Any = None,
        create_new: bool = False,
        enabled: bool = False,
        run_spec_sha256: Optional[str] = None,
        pair_id: Optional[str] = None,
        arm: Optional[str] = None,
        fresh_execution_mode: Optional[bool] = None,
        stage_allowlist: Optional[Sequence[str]] = None,
    ) -> None:
        self.enabled = _strict_bool(enabled, "enabled")
        self._lock = threading.RLock()
        self.path = Path(path).resolve() if path is not None else None
        self.frames_dir = self.path / "frames" if self.path is not None else None
        self.scope_path = self.path / "scope.json" if self.path is not None else None
        self.lock_path = (
            self.path.parent / f".{self.path.name}.lock" if self.path is not None else None
        )
        self.scope_descriptor: Optional[Dict[str, Any]] = None
        self.publication_scope_id: Optional[str] = None
        self.measurement_bindings: Dict[str, Any] = {
            "run_spec_sha256": None,
            "pair_id": None,
            "arm": None,
            "fresh_execution_mode": None,
        }
        self.stage_allowlist: Tuple[str, ...] = tuple(DEFAULT_STAGE_ALLOWLIST)
        self._frames: Dict[str, Dict[str, Any]] = {}
        self._dispatch_by_call: Dict[str, Dict[str, Any]] = {}
        self._terminal_by_call: Dict[str, Dict[str, Any]] = {}
        self._seal_by_row: Dict[Tuple[Any, ...], Dict[str, Any]] = {}
        self._abort_by_row: Dict[Tuple[Any, ...], Dict[str, Any]] = {}
        self._link_by_row: Dict[Tuple[Any, ...], Dict[str, Any]] = {}
        if not self.enabled:
            return
        if self.path is None or scope_descriptor is None:
            raise DecisionCallLedgerError("enabled ledger requires path and scope_descriptor")
        descriptor = _normalize_scope_descriptor(scope_descriptor)
        supplied_measurement = self._normalize_measurement_bindings(
            run_spec_sha256=run_spec_sha256,
            pair_id=pair_id,
            arm=arm,
            fresh_execution_mode=fresh_execution_mode,
        )
        supplied_stages = self._normalize_stage_allowlist(stage_allowlist)
        assert self.scope_path is not None and self.frames_dir is not None and self.lock_path is not None
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with _exclusive_file_lock(self.lock_path):
            if create_new:
                if self.path.exists():
                    raise FileExistsError(self.path)
                self.frames_dir.mkdir(parents=True)
                sidecar = self._build_scope_sidecar(
                    descriptor, supplied_measurement, supplied_stages
                )
                _atomic_replace(self.scope_path, _canonical_bytes(sidecar) + b"\n")
                _fsync_directory(self.path)
            elif not self.path.is_dir():
                raise DecisionCallLedgerError(f"decision call ledger missing: {self.path}")
            stored = self._read_scope_sidecar()
            if stored["publication_scope_descriptor"] != descriptor:
                raise DecisionCallLedgerError("ledger scope descriptor mismatch")
            if any(
                value is not None
                for value in (run_spec_sha256, pair_id, arm, fresh_execution_mode)
            ) and stored["measurement_bindings"] != supplied_measurement:
                raise DecisionCallLedgerError("ledger measurement binding mismatch")
            if stage_allowlist is not None and tuple(stored["stage_allowlist"]) != supplied_stages:
                raise DecisionCallLedgerError("ledger stage allowlist mismatch")
            self.scope_descriptor = descriptor
            self.publication_scope_id = descriptor["publication_scope_id"]
            self.measurement_bindings = dict(stored["measurement_bindings"])
            self.stage_allowlist = tuple(stored["stage_allowlist"])
            self._reload_frames()

    @staticmethod
    def _normalize_measurement_bindings(
        *,
        run_spec_sha256: Optional[str],
        pair_id: Optional[str],
        arm: Optional[str],
        fresh_execution_mode: Optional[bool],
    ) -> Dict[str, Any]:
        run_hash = None if run_spec_sha256 is None else _hex64(run_spec_sha256, "run_spec_sha256")
        pair = _optional_text(pair_id, "pair_id")
        normalized_arm = None if arm is None else _text(arm, "arm").upper()
        if normalized_arm is not None and normalized_arm not in ARMS:
            raise DecisionCallLedgerError("arm must be BEFORE or AFTER")
        fresh = (
            None
            if fresh_execution_mode is None
            else _strict_bool(fresh_execution_mode, "fresh_execution_mode")
        )
        return {
            "run_spec_sha256": run_hash,
            "pair_id": pair,
            "arm": normalized_arm,
            "fresh_execution_mode": fresh,
        }

    @staticmethod
    def _normalize_stage_allowlist(values: Optional[Sequence[str]]) -> Tuple[str, ...]:
        source = DEFAULT_STAGE_ALLOWLIST if values is None else values
        if isinstance(source, (str, bytes)):
            raise DecisionCallLedgerError("stage_allowlist must be a sequence")
        stages = tuple(sorted({_text(value, "stage").upper() for value in source}))
        if not stages:
            raise DecisionCallLedgerError("stage_allowlist must be non-empty")
        return stages

    @staticmethod
    def _build_scope_sidecar(
        descriptor: Mapping[str, Any],
        measurement: Mapping[str, Any],
        stages: Sequence[str],
    ) -> Dict[str, Any]:
        material = {
            "schema_version": LEDGER_SCOPE_SCHEMA,
            "publication_scope_id": descriptor["publication_scope_id"],
            "publication_scope_descriptor": dict(descriptor),
            "measurement_bindings": dict(measurement),
            "stage_allowlist": list(stages),
        }
        return {**material, "scope_sha256": _sha256(material)}

    def _read_scope_sidecar(self) -> Dict[str, Any]:
        assert self.scope_path is not None
        try:
            value = json.loads(self.scope_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise DecisionCallLedgerError(f"invalid ledger scope sidecar: {exc}") from exc
        if not isinstance(value, Mapping):
            raise DecisionCallLedgerError("ledger scope sidecar must be an object")
        _require_exact_keys(
            value,
            {
                "schema_version",
                "publication_scope_id",
                "publication_scope_descriptor",
                "measurement_bindings",
                "stage_allowlist",
                "scope_sha256",
            },
            "ledger scope sidecar",
        )
        if value.get("schema_version") != LEDGER_SCOPE_SCHEMA:
            raise DecisionCallLedgerError("ledger scope sidecar schema mismatch")
        descriptor = _normalize_scope_descriptor(value.get("publication_scope_descriptor"))
        if _hex64(value.get("publication_scope_id"), "publication_scope_id") != descriptor["publication_scope_id"]:
            raise DecisionCallLedgerError("ledger sidecar publication scope mismatch")
        measurement = value.get("measurement_bindings")
        if not isinstance(measurement, Mapping):
            raise DecisionCallLedgerError("measurement_bindings must be an object")
        _require_exact_keys(
            measurement,
            {"run_spec_sha256", "pair_id", "arm", "fresh_execution_mode"},
            "measurement bindings",
        )
        normalized_measurement = self._normalize_measurement_bindings(
            run_spec_sha256=measurement.get("run_spec_sha256"),
            pair_id=measurement.get("pair_id"),
            arm=measurement.get("arm"),
            fresh_execution_mode=measurement.get("fresh_execution_mode"),
        )
        stages = self._normalize_stage_allowlist(value.get("stage_allowlist"))
        material = {
            "schema_version": LEDGER_SCOPE_SCHEMA,
            "publication_scope_id": descriptor["publication_scope_id"],
            "publication_scope_descriptor": descriptor,
            "measurement_bindings": normalized_measurement,
            "stage_allowlist": list(stages),
        }
        if _hex64(value.get("scope_sha256"), "scope_sha256") != _sha256(material):
            raise DecisionCallLedgerError("ledger scope sidecar hash mismatch")
        return {**material, "scope_sha256": value["scope_sha256"]}

    def _require_enabled(self) -> None:
        if not self.enabled:
            raise DecisionCallLedgerDisabled("decision call ledger is disabled")

    def row_attempt(
        self,
        *,
        attempt_run_id: str,
        row_attempt_id: str,
        input_index: int,
        post_id: Any,
    ) -> RowAttemptScope:
        self._require_enabled()
        assert self.publication_scope_id is not None
        row = RowAttemptScope(
            publication_scope_id=self.publication_scope_id,
            attempt_run_id=attempt_run_id,
            row_attempt_id=row_attempt_id,
            input_index=input_index,
            post_id=post_id,
        )
        self._validate_row(row)
        return row

    def _validate_row(self, row: RowAttemptScope) -> None:
        if not isinstance(row, RowAttemptScope):
            raise DecisionCallLedgerError("row must be RowAttemptScope")
        if row.publication_scope_id != self.publication_scope_id:
            raise DecisionCallLedgerError("row publication scope mismatch")
        assert self.scope_descriptor is not None
        post_ids = self.scope_descriptor["post_ids"]
        if row.input_index > len(post_ids):
            raise DecisionCallLedgerError("row input_index is outside publication scope")
        if post_ids[row.input_index - 1] != row.post_id:
            raise DecisionCallLedgerError("row input_index/post_id binding mismatch")

    @staticmethod
    def _row_key(row: RowAttemptScope) -> Tuple[Any, ...]:
        return (
            row.attempt_run_id,
            row.row_attempt_id,
            row.input_index,
            row.post_id,
        )

    def _make_frame(
        self,
        frame_kind: str,
        row: RowAttemptScope,
        payload: Mapping[str, Any],
    ) -> Dict[str, Any]:
        identity_material: Dict[str, Any] = {
            "frame_kind": frame_kind,
            "row": row.to_dict(),
        }
        if frame_kind in {FRAME_DISPATCH, FRAME_TERMINAL}:
            identity_material["call_id"] = payload.get("call_id")
        identity_sha = _sha256(identity_material)
        material = {
            "schema_version": FRAME_SCHEMA,
            "frame_kind": frame_kind,
            "row": row.to_dict(),
            "identity_sha256": identity_sha,
            "payload": _canonical_payload(payload),
        }
        return {**material, "frame_sha256": _sha256(material)}

    @staticmethod
    def _frame_filename(frame: Mapping[str, Any]) -> str:
        return f"{str(frame['frame_kind']).lower()}_{frame['identity_sha256']}.json"

    def _validate_frame(self, value: Any) -> Dict[str, Any]:
        if not isinstance(value, Mapping):
            raise DecisionCallLedgerError("ledger frame must be an object")
        _require_exact_keys(
            value,
            {"schema_version", "frame_kind", "row", "identity_sha256", "payload", "frame_sha256"},
            "ledger frame",
        )
        if value.get("schema_version") != FRAME_SCHEMA:
            raise DecisionCallLedgerError("ledger frame schema mismatch")
        kind = _text(value.get("frame_kind"), "frame_kind")
        if kind not in FRAME_KINDS:
            raise DecisionCallLedgerError("unsupported ledger frame kind")
        row = RowAttemptScope.from_dict(value.get("row"))
        self._validate_row(row)
        payload = value.get("payload")
        if not isinstance(payload, Mapping):
            raise DecisionCallLedgerError("ledger frame payload must be an object")
        normalized_payload = self._validate_payload(kind, payload)
        rebuilt = self._make_frame(kind, row, normalized_payload)
        if value.get("identity_sha256") != rebuilt["identity_sha256"]:
            raise DecisionCallLedgerError("ledger frame identity mismatch")
        if value.get("frame_sha256") != rebuilt["frame_sha256"]:
            raise DecisionCallLedgerError("ledger frame self hash mismatch")
        return rebuilt

    def _validate_payload(self, kind: str, payload: Mapping[str, Any]) -> Dict[str, Any]:
        if kind == FRAME_DISPATCH:
            expected = {
                "logical_call_id", "call_id", "retry_ordinal", "retry_of_call_id",
                "stage", "modality", "requested_model", "resolved_model", "endpoint",
                "backend", "started_at", "monotonic_started_ns", "request_sha256",
            }
            _require_exact_keys(payload, expected, "dispatch payload")
            stage = _text(payload.get("stage"), "stage").upper()
            if stage not in self.stage_allowlist:
                raise DecisionCallLedgerError(f"stage is not allowlisted: {stage}")
            modality = _text(payload.get("modality"), "modality").upper()
            if modality not in MODALITIES:
                raise DecisionCallLedgerError("unsupported modality")
            ordinal = _nonnegative_int(payload.get("retry_ordinal"), "retry_ordinal")
            retry_of = _optional_text(payload.get("retry_of_call_id"), "retry_of_call_id")
            if (ordinal == 0 and retry_of is not None) or (ordinal > 0 and retry_of is None):
                raise DecisionCallLedgerError("retry parent/ordinal mismatch")
            return {
                "logical_call_id": _text(payload.get("logical_call_id"), "logical_call_id"),
                "call_id": _text(payload.get("call_id"), "call_id"),
                "retry_ordinal": ordinal,
                "retry_of_call_id": retry_of,
                "stage": stage,
                "modality": modality,
                "requested_model": _text(payload.get("requested_model"), "requested_model"),
                "resolved_model": _optional_text(payload.get("resolved_model"), "resolved_model"),
                "endpoint": _text(payload.get("endpoint"), "endpoint"),
                "backend": _text(payload.get("backend"), "backend"),
                "started_at": _iso_timestamp(payload.get("started_at"), "started_at"),
                "monotonic_started_ns": _nonnegative_int(
                    payload.get("monotonic_started_ns"), "monotonic_started_ns"
                ),
                "request_sha256": _hex64(payload.get("request_sha256"), "request_sha256"),
            }
        if kind == FRAME_TERMINAL:
            expected = {
                "logical_call_id", "call_id", "retry_ordinal", "retry_of_call_id",
                "stage", "modality", "requested_model", "resolved_model", "endpoint",
                "backend", "started_at", "monotonic_started_ns", "request_sha256",
                "terminal_status", "finished_at", "monotonic_finished_ns", "wall_ms",
                "response_sha256", "usage_provenance", "prompt_tokens",
                "completion_tokens", "total_tokens", "error_type", "error_message_sha256",
            }
            _require_exact_keys(payload, expected, "terminal payload")
            base = self._validate_payload(
                FRAME_DISPATCH,
                {key: payload.get(key) for key in {
                    "logical_call_id", "call_id", "retry_ordinal", "retry_of_call_id",
                    "stage", "modality", "requested_model", "resolved_model", "endpoint",
                    "backend", "started_at", "monotonic_started_ns", "request_sha256",
                }},
            )
            status = _text(payload.get("terminal_status"), "terminal_status").upper()
            if status not in TERMINAL_STATUSES:
                raise DecisionCallLedgerError("unsupported terminal status")
            finished_at = _iso_timestamp(payload.get("finished_at"), "finished_at")
            if datetime.fromisoformat(finished_at) < datetime.fromisoformat(base["started_at"]):
                raise DecisionCallLedgerError("terminal finished_at precedes started_at")
            finished_ns = _nonnegative_int(
                payload.get("monotonic_finished_ns"), "monotonic_finished_ns"
            )
            if finished_ns < base["monotonic_started_ns"]:
                raise DecisionCallLedgerError("terminal monotonic time precedes dispatch")
            wall_ms = (finished_ns - base["monotonic_started_ns"]) // 1_000_000
            if _nonnegative_int(payload.get("wall_ms"), "wall_ms") != wall_ms:
                raise DecisionCallLedgerError("terminal wall_ms mismatch")
            provenance = _text(payload.get("usage_provenance"), "usage_provenance").upper()
            if provenance not in USAGE_PROVENANCE_VALUES:
                raise DecisionCallLedgerError("unsupported usage provenance")
            tokens = tuple(
                _optional_nonnegative_int(payload.get(name), name)
                for name in ("prompt_tokens", "completion_tokens", "total_tokens")
            )
            if provenance == "UNAVAILABLE":
                if any(item is not None for item in tokens):
                    raise DecisionCallLedgerError("unavailable usage must keep tokens null")
            else:
                if any(item is None for item in tokens):
                    raise DecisionCallLedgerError("available usage requires all token fields")
                if tokens[2] != tokens[0] + tokens[1]:
                    raise DecisionCallLedgerError("total_tokens arithmetic mismatch")
            response_sha = (
                None
                if payload.get("response_sha256") is None
                else _hex64(payload.get("response_sha256"), "response_sha256")
            )
            error_type = _optional_text(payload.get("error_type"), "error_type")
            error_sha = (
                None
                if payload.get("error_message_sha256") is None
                else _hex64(payload.get("error_message_sha256"), "error_message_sha256")
            )
            if status == "SUCCEEDED":
                if response_sha is None or error_type is not None or error_sha is not None:
                    raise DecisionCallLedgerError("successful terminal response/error mismatch")
            elif error_type is None:
                raise DecisionCallLedgerError("non-success terminal requires error_type")
            return {
                **base,
                "terminal_status": status,
                "finished_at": finished_at,
                "monotonic_finished_ns": finished_ns,
                "wall_ms": wall_ms,
                "response_sha256": response_sha,
                "usage_provenance": provenance,
                "prompt_tokens": tokens[0],
                "completion_tokens": tokens[1],
                "total_tokens": tokens[2],
                "error_type": error_type,
                "error_message_sha256": error_sha,
            }
        if kind == FRAME_ROW_SEAL:
            expected = {
                "event_root_sha256", "event_frame_count", "expert_calls", "text_calls",
                "vlm_calls", "retry_count", "terminal_counts", "usage_status",
                "prompt_tokens", "completion_tokens", "total_tokens", "sealed_at",
                "monotonic_finished_ns",
            }
            _require_exact_keys(payload, expected, "row seal payload")
            terminal_counts = payload.get("terminal_counts")
            if not isinstance(terminal_counts, Mapping):
                raise DecisionCallLedgerError("terminal_counts must be an object")
            _require_exact_keys(terminal_counts, TERMINAL_STATUSES, "terminal_counts")
            normalized_counts = {
                key: _nonnegative_int(terminal_counts.get(key), f"terminal_counts.{key}")
                for key in sorted(TERMINAL_STATUSES)
            }
            usage_status = _text(payload.get("usage_status"), "usage_status")
            if usage_status not in {
                "NO_CALLS", "COMPLETE_PROVIDER_REPORTED", "COMPLETE_WITH_ESTIMATES", "UNAVAILABLE"
            }:
                raise DecisionCallLedgerError("unsupported usage_status")
            tokens = tuple(
                _optional_nonnegative_int(payload.get(name), name)
                for name in ("prompt_tokens", "completion_tokens", "total_tokens")
            )
            if usage_status == "UNAVAILABLE" and any(item is not None for item in tokens):
                raise DecisionCallLedgerError("unavailable seal usage must keep tokens null")
            if usage_status != "UNAVAILABLE" and any(item is None for item in tokens):
                raise DecisionCallLedgerError("complete seal usage requires token totals")
            if tokens[2] is not None and tokens[2] != tokens[0] + tokens[1]:
                raise DecisionCallLedgerError("seal token arithmetic mismatch")
            return {
                "event_root_sha256": _hex64(payload.get("event_root_sha256"), "event_root_sha256"),
                "event_frame_count": _nonnegative_int(payload.get("event_frame_count"), "event_frame_count"),
                "expert_calls": _nonnegative_int(payload.get("expert_calls"), "expert_calls"),
                "text_calls": _nonnegative_int(payload.get("text_calls"), "text_calls"),
                "vlm_calls": _nonnegative_int(payload.get("vlm_calls"), "vlm_calls"),
                "retry_count": _nonnegative_int(payload.get("retry_count"), "retry_count"),
                "terminal_counts": normalized_counts,
                "usage_status": usage_status,
                "prompt_tokens": tokens[0], "completion_tokens": tokens[1], "total_tokens": tokens[2],
                "sealed_at": _iso_timestamp(payload.get("sealed_at"), "sealed_at"),
                "monotonic_finished_ns": _nonnegative_int(
                    payload.get("monotonic_finished_ns"), "monotonic_finished_ns"
                ),
            }
        if kind == FRAME_ROW_ABORT:
            expected = {
                "reason_code", "event_root_sha256", "event_frame_count", "expert_calls",
                "open_call_count", "aborted_at", "monotonic_finished_ns",
            }
            _require_exact_keys(payload, expected, "row abort payload")
            return {
                "reason_code": _text(payload.get("reason_code"), "reason_code"),
                "event_root_sha256": _hex64(payload.get("event_root_sha256"), "event_root_sha256"),
                "event_frame_count": _nonnegative_int(payload.get("event_frame_count"), "event_frame_count"),
                "expert_calls": _nonnegative_int(payload.get("expert_calls"), "expert_calls"),
                "open_call_count": _nonnegative_int(payload.get("open_call_count"), "open_call_count"),
                "aborted_at": _iso_timestamp(payload.get("aborted_at"), "aborted_at"),
                "monotonic_finished_ns": _nonnegative_int(
                    payload.get("monotonic_finished_ns"), "monotonic_finished_ns"
                ),
            }
        expected = {
            "publication_decision_id", "event_root_sha256", "seal_frame_sha256", "linked_at"
        }
        _require_exact_keys(payload, expected, "publication link payload")
        return {
            "publication_decision_id": _hex64(
                payload.get("publication_decision_id"), "publication_decision_id"
            ),
            "event_root_sha256": _hex64(payload.get("event_root_sha256"), "event_root_sha256"),
            "seal_frame_sha256": _hex64(payload.get("seal_frame_sha256"), "seal_frame_sha256"),
            "linked_at": _iso_timestamp(payload.get("linked_at"), "linked_at"),
        }

    def _reload_frames(self) -> None:
        self._frames = {}
        assert self.frames_dir is not None
        for path in sorted(self.frames_dir.iterdir()):
            if path.name.startswith(".") and path.name.endswith(".tmp"):
                continue
            if not path.is_file() or path.suffix != ".json":
                raise DecisionCallLedgerError(f"unexpected ledger frame entry: {path.name}")
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise DecisionCallLedgerError(f"invalid ledger frame {path}: {exc}") from exc
            frame = self._validate_frame(value)
            if path.name != self._frame_filename(frame):
                raise DecisionCallLedgerError("ledger frame filename/identity mismatch")
            identity = frame["identity_sha256"]
            if identity in self._frames:
                raise DecisionCallLedgerConflict("duplicate ledger frame identity")
            self._frames[identity] = frame
        self._rebuild_indexes()

    def _rebuild_indexes(self) -> None:
        self._dispatch_by_call = {}
        self._terminal_by_call = {}
        self._seal_by_row = {}
        self._abort_by_row = {}
        self._link_by_row = {}
        logical_ordinals: Dict[Tuple[Any, ...], str] = {}
        for frame in self._frames.values():
            row = RowAttemptScope.from_dict(frame["row"])
            key = self._row_key(row)
            payload = frame["payload"]
            kind = frame["frame_kind"]
            if kind == FRAME_DISPATCH:
                call_id = payload["call_id"]
                if call_id in self._dispatch_by_call:
                    raise DecisionCallLedgerConflict("physical call_id reused")
                ordinal_key = key + (payload["logical_call_id"], payload["retry_ordinal"])
                if ordinal_key in logical_ordinals and logical_ordinals[ordinal_key] != call_id:
                    raise DecisionCallLedgerConflict("logical retry ordinal reused")
                logical_ordinals[ordinal_key] = call_id
                self._dispatch_by_call[call_id] = frame
            elif kind == FRAME_TERMINAL:
                call_id = payload["call_id"]
                if call_id in self._terminal_by_call:
                    raise DecisionCallLedgerConflict("double terminal for physical call")
                self._terminal_by_call[call_id] = frame
            elif kind == FRAME_ROW_SEAL:
                if key in self._seal_by_row:
                    raise DecisionCallLedgerConflict("duplicate row seal")
                self._seal_by_row[key] = frame
            elif kind == FRAME_ROW_ABORT:
                if key in self._abort_by_row:
                    raise DecisionCallLedgerConflict("duplicate row abort")
                self._abort_by_row[key] = frame
            else:
                if key in self._link_by_row:
                    raise DecisionCallLedgerConflict("duplicate publication link")
                self._link_by_row[key] = frame
        for call_id, terminal in self._terminal_by_call.items():
            dispatch = self._dispatch_by_call.get(call_id)
            if dispatch is None:
                raise DecisionCallLedgerError("orphan terminal without dispatch intent")
            if terminal["row"] != dispatch["row"]:
                raise DecisionCallLedgerError("terminal row binding mismatch")
            for field in (
                "logical_call_id", "call_id", "retry_ordinal", "retry_of_call_id", "stage",
                "modality", "requested_model", "endpoint", "backend", "started_at",
                "monotonic_started_ns", "request_sha256",
            ):
                if terminal["payload"][field] != dispatch["payload"][field]:
                    raise DecisionCallLedgerError(f"terminal/dispatch binding mismatch: {field}")
            expected_model = dispatch["payload"]["resolved_model"]
            if expected_model is not None and terminal["payload"]["resolved_model"] != expected_model:
                raise DecisionCallLedgerError("terminal resolved_model mismatch")
        for call_id, dispatch in self._dispatch_by_call.items():
            payload = dispatch["payload"]
            if payload["retry_ordinal"] == 0:
                continue
            parent_id = payload["retry_of_call_id"]
            parent = self._dispatch_by_call.get(parent_id)
            parent_terminal = self._terminal_by_call.get(parent_id)
            if parent is None or parent_terminal is None:
                raise DecisionCallLedgerError("retry lineage gap")
            if parent["row"] != dispatch["row"]:
                raise DecisionCallLedgerError("retry parent row mismatch")
            if parent["payload"]["logical_call_id"] != payload["logical_call_id"]:
                raise DecisionCallLedgerError("retry parent logical call mismatch")
            if parent["payload"]["retry_ordinal"] != payload["retry_ordinal"] - 1:
                raise DecisionCallLedgerError("retry ordinal is not contiguous")
            if parent_terminal["payload"]["terminal_status"] == "SUCCEEDED":
                raise DecisionCallLedgerError("successful call cannot be retried")
        row_keys = set(self._seal_by_row) | set(self._abort_by_row) | set(self._link_by_row)
        row_keys.update(self._row_key(RowAttemptScope.from_dict(item["row"])) for item in self._dispatch_by_call.values())
        for key in row_keys:
            if key in self._seal_by_row and key in self._abort_by_row:
                raise DecisionCallLedgerConflict("row cannot be sealed and aborted")
            row = self._row_from_key(key)
            evidence = self._derive_row_evidence(row)
            seal = self._seal_by_row.get(key)
            abort = self._abort_by_row.get(key)
            link = self._link_by_row.get(key)
            if seal is not None and seal["payload"] != self._seal_payload(
                row,
                sealed_at=seal["payload"]["sealed_at"],
                monotonic_finished_ns=seal["payload"]["monotonic_finished_ns"],
            ):
                raise DecisionCallLedgerError("row seal no longer matches call events")
            if abort is not None:
                expected_abort = {
                    "reason_code": abort["payload"]["reason_code"],
                    "event_root_sha256": evidence["event_root_sha256"],
                    "event_frame_count": evidence["event_frame_count"],
                    "expert_calls": evidence["expert_calls"],
                    "open_call_count": evidence["open_call_count"],
                    "aborted_at": abort["payload"]["aborted_at"],
                    "monotonic_finished_ns": abort["payload"]["monotonic_finished_ns"],
                }
                if abort["payload"] != expected_abort:
                    raise DecisionCallLedgerError("row abort no longer matches call events")
            if link is not None:
                if seal is None:
                    raise DecisionCallLedgerError("publication link requires a sealed row")
                if (
                    link["payload"]["event_root_sha256"] != seal["payload"]["event_root_sha256"]
                    or link["payload"]["seal_frame_sha256"] != seal["frame_sha256"]
                ):
                    raise DecisionCallLedgerError("publication link/seal mismatch")

    def _row_from_key(self, key: Tuple[Any, ...]) -> RowAttemptScope:
        assert self.publication_scope_id is not None
        return RowAttemptScope(
            publication_scope_id=self.publication_scope_id,
            attempt_run_id=key[0], row_attempt_id=key[1], input_index=key[2], post_id=key[3]
        )

    def _row_call_frames(self, row: RowAttemptScope) -> list[Dict[str, Any]]:
        key = self._row_key(row)
        frames = [
            frame for frame in self._frames.values()
            if frame["frame_kind"] in {FRAME_DISPATCH, FRAME_TERMINAL}
            and self._row_key(RowAttemptScope.from_dict(frame["row"])) == key
        ]
        return sorted(
            frames,
            key=lambda item: (
                item["payload"]["monotonic_started_ns"],
                item["payload"]["call_id"],
                0 if item["frame_kind"] == FRAME_DISPATCH else 1,
            ),
        )

    def _derive_row_evidence(self, row: RowAttemptScope) -> Dict[str, Any]:
        frames = self._row_call_frames(row)
        dispatches = [item for item in frames if item["frame_kind"] == FRAME_DISPATCH]
        terminals = [item for item in frames if item["frame_kind"] == FRAME_TERMINAL]
        terminal_by_call = {item["payload"]["call_id"]: item for item in terminals}
        open_count = sum(item["payload"]["call_id"] not in terminal_by_call for item in dispatches)
        terminal_counts = {
            status: sum(item["payload"]["terminal_status"] == status for item in terminals)
            for status in sorted(TERMINAL_STATUSES)
        }
        provenance = [item["payload"]["usage_provenance"] for item in terminals]
        if not dispatches:
            usage_status = "NO_CALLS"
            prompt = completion = total = 0
        elif open_count or any(item == "UNAVAILABLE" for item in provenance):
            usage_status = "UNAVAILABLE"
            prompt = completion = total = None
        else:
            usage_status = (
                "COMPLETE_WITH_ESTIMATES"
                if any(item == "ESTIMATED" for item in provenance)
                else "COMPLETE_PROVIDER_REPORTED"
            )
            prompt = sum(int(item["payload"]["prompt_tokens"]) for item in terminals)
            completion = sum(int(item["payload"]["completion_tokens"]) for item in terminals)
            total = prompt + completion
        return {
            "event_root_sha256": _sha256([item["frame_sha256"] for item in frames]),
            "event_frame_count": len(frames),
            "expert_calls": len(dispatches),
            "text_calls": sum(item["payload"]["modality"] == "TEXT" for item in dispatches),
            "vlm_calls": sum(item["payload"]["modality"] == "VLM" for item in dispatches),
            "retry_count": sum(item["payload"]["retry_ordinal"] > 0 for item in dispatches),
            "terminal_counts": terminal_counts,
            "usage_status": usage_status,
            "prompt_tokens": prompt,
            "completion_tokens": completion,
            "total_tokens": total,
            "open_call_count": open_count,
        }

    def _seal_payload(
        self, row: RowAttemptScope, *, sealed_at: str, monotonic_finished_ns: int
    ) -> Dict[str, Any]:
        evidence = self._derive_row_evidence(row)
        if evidence["open_call_count"]:
            raise DecisionCallLedgerIncomplete("row has dispatch intents without terminal frames")
        # A row containing physical calls is publishable only when at least one
        # call has a real successful terminal.  FAILED-only and fallback-only
        # observations must remain abort/non-estimable; otherwise an empty
        # provider fallback could masquerade as a measured row.
        if evidence["expert_calls"] and not evidence["terminal_counts"]["SUCCEEDED"]:
            raise DecisionCallLedgerIncomplete(
                "row has no successful terminal call; seal is not estimable"
            )
        return {
            key: evidence[key]
            for key in (
                "event_root_sha256", "event_frame_count", "expert_calls", "text_calls",
                "vlm_calls", "retry_count", "terminal_counts", "usage_status",
                "prompt_tokens", "completion_tokens", "total_tokens",
            )
        } | {
            "sealed_at": _iso_timestamp(sealed_at, "sealed_at"),
            "monotonic_finished_ns": _nonnegative_int(
                monotonic_finished_ns, "monotonic_finished_ns"
            ),
        }

    def _record_frame_locked(self, frame: Mapping[str, Any]) -> Tuple[Dict[str, Any], bool]:
        """Append one frame while the registry/process lock is already held.

        Callers that decide whether a row is open must keep that decision and
        the exclusive publish in this same critical section.  Re-checking the
        closure index here is intentional: it prevents a prepared dispatch or
        terminal frame from being published after a concurrent seal/abort.
        """
        self._require_enabled()
        assert self.lock_path is not None and self.frames_dir is not None
        normalized = self._validate_frame(frame)
        self._reload_frames()
        row_key = self._row_key(RowAttemptScope.from_dict(normalized["row"]))
        if normalized["frame_kind"] == FRAME_DISPATCH and (
            row_key in self._seal_by_row or row_key in self._abort_by_row
        ):
            raise DecisionCallLedgerConflict("late dispatch after row closure")
        if normalized["frame_kind"] == FRAME_TERMINAL and (
            row_key in self._seal_by_row or row_key in self._abort_by_row
        ):
            raise DecisionCallLedgerConflict("late terminal after row closure")
        identity = normalized["identity_sha256"]
        existing = self._frames.get(identity)
        if existing is not None:
            if existing == normalized:
                return json.loads(json.dumps(existing)), False
            raise DecisionCallLedgerConflict("immutable frame identity conflict")
        path = self.frames_dir / self._frame_filename(normalized)
        created = _exclusive_publish(path, _canonical_bytes(normalized) + b"\n")
        if not created:
            self._reload_frames()
            existing = self._frames.get(identity)
            if existing == normalized:
                return json.loads(json.dumps(existing)), False
            raise DecisionCallLedgerConflict("concurrent immutable frame conflict")
        self._reload_frames()
        return json.loads(json.dumps(self._frames[identity])), True

    def _record_frame(self, frame: Mapping[str, Any]) -> Tuple[Dict[str, Any], bool]:
        self._require_enabled()
        assert self.lock_path is not None
        with self._lock:
            with _exclusive_file_lock(self.lock_path):
                return self._record_frame_locked(frame)

    def record_dispatch_intent(
        self,
        row: RowAttemptScope,
        *,
        logical_call_id: str,
        call_id: str,
        retry_ordinal: int,
        retry_of_call_id: Optional[str] = None,
        stage: str,
        modality: str,
        requested_model: str,
        resolved_model: Optional[str],
        endpoint: str,
        backend: str,
        started_at: Optional[str] = None,
        monotonic_started_ns: Optional[int] = None,
        request_sha256: str,
    ) -> Tuple[Dict[str, Any], bool]:
        self._require_enabled()
        self._validate_row(row)
        with self._lock:
            assert self.lock_path is not None
            with _exclusive_file_lock(self.lock_path):
                self._reload_frames()
                key = self._row_key(row)
                if key in self._seal_by_row or key in self._abort_by_row:
                    raise DecisionCallLedgerConflict("late dispatch after row closure")
                payload = self._validate_payload(FRAME_DISPATCH, {
                    "logical_call_id": logical_call_id,
                    "call_id": call_id,
                    "retry_ordinal": retry_ordinal,
                    "retry_of_call_id": retry_of_call_id,
                    "stage": stage,
                    "modality": modality,
                    "requested_model": requested_model,
                    "resolved_model": resolved_model,
                    "endpoint": endpoint,
                    "backend": backend,
                    "started_at": started_at or _utc_now(),
                    "monotonic_started_ns": (
                        time.monotonic_ns() if monotonic_started_ns is None else monotonic_started_ns
                    ),
                    "request_sha256": request_sha256,
                })
                if call_id in self._dispatch_by_call:
                    frame = self._make_frame(FRAME_DISPATCH, row, payload)
                    existing = self._dispatch_by_call[call_id]
                    if existing == frame:
                        return json.loads(json.dumps(existing)), False
                    raise DecisionCallLedgerConflict("physical call_id reused")
                ordinal_key = key + (payload["logical_call_id"], payload["retry_ordinal"])
                for existing in self._dispatch_by_call.values():
                    erow = RowAttemptScope.from_dict(existing["row"])
                    ep = existing["payload"]
                    if self._row_key(erow) + (ep["logical_call_id"], ep["retry_ordinal"]) == ordinal_key:
                        raise DecisionCallLedgerConflict("logical retry ordinal reused")
                if payload["retry_ordinal"] > 0:
                    parent = self._dispatch_by_call.get(str(payload["retry_of_call_id"]))
                    terminal = self._terminal_by_call.get(str(payload["retry_of_call_id"]))
                    if parent is None or terminal is None:
                        raise DecisionCallLedgerError("retry lineage gap")
                    if parent["row"] != row.to_dict():
                        raise DecisionCallLedgerError("retry parent row mismatch")
                    if parent["payload"]["logical_call_id"] != payload["logical_call_id"]:
                        raise DecisionCallLedgerError("retry parent logical call mismatch")
                    if parent["payload"]["retry_ordinal"] != payload["retry_ordinal"] - 1:
                        raise DecisionCallLedgerError("retry ordinal is not contiguous")
                    if terminal["payload"]["terminal_status"] == "SUCCEEDED":
                        raise DecisionCallLedgerError("successful call cannot be retried")
                frame = self._make_frame(FRAME_DISPATCH, row, payload)
                return self._record_frame_locked(frame)

    def record_terminal(
        self,
        row: RowAttemptScope,
        *,
        call_id: str,
        terminal_status: str,
        resolved_model: Optional[str],
        response_sha256: Optional[str],
        usage_provenance: str,
        prompt_tokens: Optional[int],
        completion_tokens: Optional[int],
        total_tokens: Optional[int],
        error_type: Optional[str] = None,
        error_message_sha256: Optional[str] = None,
        finished_at: Optional[str] = None,
        monotonic_finished_ns: Optional[int] = None,
    ) -> Tuple[Dict[str, Any], bool]:
        self._require_enabled()
        self._validate_row(row)
        with self._lock:
            assert self.lock_path is not None
            with _exclusive_file_lock(self.lock_path):
                self._reload_frames()
                key = self._row_key(row)
                if key in self._seal_by_row or key in self._abort_by_row:
                    raise DecisionCallLedgerConflict("late terminal after row closure")
                dispatch = self._dispatch_by_call.get(call_id)
                if dispatch is None:
                    raise DecisionCallLedgerError("terminal requires a dispatch intent")
                if dispatch["row"] != row.to_dict():
                    raise DecisionCallLedgerError("terminal cross-row binding mismatch")
                base = dict(dispatch["payload"])
                finished_ns = time.monotonic_ns() if monotonic_finished_ns is None else monotonic_finished_ns
                payload = {
                    **base,
                    "resolved_model": (
                        base["resolved_model"] if resolved_model is None else resolved_model
                    ),
                    "terminal_status": terminal_status,
                    "finished_at": finished_at or _utc_now(),
                    "monotonic_finished_ns": finished_ns,
                    "wall_ms": (finished_ns - base["monotonic_started_ns"]) // 1_000_000,
                    "response_sha256": response_sha256,
                    "usage_provenance": usage_provenance,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                    "error_type": error_type,
                    "error_message_sha256": error_message_sha256,
                }
                payload = self._validate_payload(FRAME_TERMINAL, payload)
                frame = self._make_frame(FRAME_TERMINAL, row, payload)
                existing = self._terminal_by_call.get(call_id)
                if existing is not None:
                    if existing == frame:
                        return json.loads(json.dumps(existing)), False
                    raise DecisionCallLedgerConflict("double terminal conflict")
                return self._record_frame_locked(frame)

    def seal_row(
        self,
        row: RowAttemptScope,
        *,
        sealed_at: Optional[str] = None,
        monotonic_finished_ns: Optional[int] = None,
    ) -> Tuple[Dict[str, Any], bool]:
        self._require_enabled()
        self._validate_row(row)
        with self._lock:
            assert self.lock_path is not None
            with _exclusive_file_lock(self.lock_path):
                self._reload_frames()
                key = self._row_key(row)
                if key in self._abort_by_row:
                    raise DecisionCallLedgerConflict("aborted row cannot be sealed")
                payload = self._seal_payload(
                    row,
                    sealed_at=sealed_at or _utc_now(),
                    monotonic_finished_ns=(
                        time.monotonic_ns()
                        if monotonic_finished_ns is None
                        else monotonic_finished_ns
                    ),
                )
                frame = self._make_frame(FRAME_ROW_SEAL, row, payload)
                existing = self._seal_by_row.get(key)
                if existing is not None:
                    if existing == frame:
                        return json.loads(json.dumps(existing)), False
                    raise DecisionCallLedgerConflict("row already sealed with another payload")
                return self._record_frame_locked(frame)

    def abort_row(
        self,
        row: RowAttemptScope,
        *,
        reason_code: str,
        aborted_at: Optional[str] = None,
        monotonic_finished_ns: Optional[int] = None,
    ) -> Tuple[Dict[str, Any], bool]:
        self._require_enabled()
        self._validate_row(row)
        with self._lock:
            assert self.lock_path is not None
            with _exclusive_file_lock(self.lock_path):
                self._reload_frames()
                key = self._row_key(row)
                if key in self._seal_by_row:
                    raise DecisionCallLedgerConflict("sealed row cannot be aborted")
                evidence = self._derive_row_evidence(row)
                payload = {
                    "reason_code": _text(reason_code, "reason_code"),
                    "event_root_sha256": evidence["event_root_sha256"],
                    "event_frame_count": evidence["event_frame_count"],
                    "expert_calls": evidence["expert_calls"],
                    "open_call_count": evidence["open_call_count"],
                    "aborted_at": aborted_at or _utc_now(),
                    "monotonic_finished_ns": (
                        time.monotonic_ns()
                        if monotonic_finished_ns is None
                        else monotonic_finished_ns
                    ),
                }
                payload = self._validate_payload(FRAME_ROW_ABORT, payload)
                frame = self._make_frame(FRAME_ROW_ABORT, row, payload)
                existing = self._abort_by_row.get(key)
                if existing is not None:
                    if existing == frame:
                        return json.loads(json.dumps(existing)), False
                    raise DecisionCallLedgerConflict("row already aborted with another payload")
                return self._record_frame_locked(frame)

    def link_publication(
        self,
        row: RowAttemptScope,
        *,
        publication_decision_id: str,
        linked_at: Optional[str] = None,
    ) -> Tuple[Dict[str, Any], bool]:
        self._require_enabled()
        self._validate_row(row)
        with self._lock:
            assert self.lock_path is not None
            with _exclusive_file_lock(self.lock_path):
                self._reload_frames()
                key = self._row_key(row)
                seal = self._seal_by_row.get(key)
                if seal is None:
                    raise DecisionCallLedgerIncomplete("publication link requires a sealed row")
                payload = self._validate_payload(FRAME_PUBLICATION_LINK, {
                    "publication_decision_id": publication_decision_id,
                    "event_root_sha256": seal["payload"]["event_root_sha256"],
                    "seal_frame_sha256": seal["frame_sha256"],
                    "linked_at": linked_at or _utc_now(),
                })
                frame = self._make_frame(FRAME_PUBLICATION_LINK, row, payload)
                existing = self._link_by_row.get(key)
                if existing is not None:
                    if existing == frame:
                        return json.loads(json.dumps(existing)), False
                    raise DecisionCallLedgerConflict("row already linked to another publication payload")
                return self._record_frame_locked(frame)

    def _measurement_status(self) -> str:
        values = self.measurement_bindings
        if any(values.get(key) is None for key in ("run_spec_sha256", "pair_id", "arm", "fresh_execution_mode")):
            return "UNBOUND_PARTIAL"
        if values.get("fresh_execution_mode") is not True:
            return "BOUND_NONFRESH_PARTIAL"
        return "BOUND_FRESH_EXECUTION"

    def summary(self) -> Dict[str, Any]:
        if not self.enabled:
            return {
                "schema_version": SUMMARY_SCHEMA,
                "instrumentation_status": "DISABLED",
                "publication_scope_id": None,
                "measurement_binding_status": "UNBOUND_PARTIAL",
                "ledger_status": "UNMEASURED",
                "actual_kpi_status": "NOT_ESTIMABLE",
                "actual_metrics": {
                    "expert_calls": None, "prompt_tokens": None,
                    "completion_tokens": None, "total_tokens": None,
                },
                "derived_observation": {
                    "expert_calls": None, "prompt_tokens": None,
                    "completion_tokens": None, "total_tokens": None,
                },
                "reason_codes": ["INSTRUMENTATION_DISABLED"],
                "row_attempt_count": 0, "sealed_row_attempt_count": 0,
                "aborted_row_attempt_count": 0, "linked_row_attempt_count": 0,
                "open_call_count": 0,
            }
        assert self.lock_path is not None
        with self._lock:
            with _exclusive_file_lock(self.lock_path):
                self._read_scope_sidecar()
                self._reload_frames()
                row_keys = {
                    self._row_key(RowAttemptScope.from_dict(frame["row"]))
                    for frame in self._frames.values()
                }
                rows = [self._derive_row_evidence(self._row_from_key(key)) for key in sorted(row_keys, key=str)]
                reasons: list[str] = []
                measurement_status = self._measurement_status()
                if measurement_status != "BOUND_FRESH_EXECUTION":
                    reasons.append(measurement_status)
                if not row_keys:
                    reasons.append("NO_ROW_ATTEMPTS")
                if any(key not in self._seal_by_row for key in row_keys):
                    reasons.append("UNSEALED_ROW_ATTEMPT")
                if any(key in self._abort_by_row for key in row_keys):
                    reasons.append("ABORTED_ROW_ATTEMPT")
                if any(key not in self._link_by_row for key in self._seal_by_row):
                    reasons.append("UNLINKED_ROW_ATTEMPT")
                if any(row["open_call_count"] for row in rows):
                    reasons.append("OPEN_CALL_INTENT")
                if any(row["usage_status"] == "UNAVAILABLE" for row in rows):
                    reasons.append("USAGE_UNAVAILABLE")
                if any(row["usage_status"] == "COMPLETE_WITH_ESTIMATES" for row in rows):
                    reasons.append("USAGE_ESTIMATED")
                terminal_models = [
                    item["payload"]["resolved_model"] for item in self._terminal_by_call.values()
                ]
                if any(model is None for model in terminal_models):
                    reasons.append("RESOLVED_MODEL_UNAVAILABLE")
                by_run: Dict[str, list[Tuple[Any, ...]]] = {}
                for key in row_keys:
                    by_run.setdefault(str(key[0]), []).append(key)
                if len(by_run) > 1:
                    reasons.append("AMBIGUOUS_MULTIPLE_ATTEMPT_RUNS")
                assert self.scope_descriptor is not None
                expected = {
                    (index, post_id)
                    for index, post_id in enumerate(self.scope_descriptor["post_ids"], 1)
                }
                for keys in by_run.values():
                    actual = [(key[2], key[3]) for key in keys]
                    if len(actual) != len(set(actual)) or set(actual) != expected:
                        reasons.append("RUN_ROW_COVERAGE_INCOMPLETE")
                        break
                reasons = sorted(set(reasons))
                writer_complete = not reasons
                derived_calls = sum(row["expert_calls"] for row in rows)
                derived_prompt = (
                    sum(int(row["prompt_tokens"]) for row in rows)
                    if rows and all(row["prompt_tokens"] is not None for row in rows)
                    else None
                )
                derived_completion = (
                    sum(int(row["completion_tokens"]) for row in rows)
                    if rows and all(row["completion_tokens"] is not None for row in rows)
                    else None
                )
                derived_total = (
                    derived_prompt + derived_completion
                    if derived_prompt is not None and derived_completion is not None
                    else None
                )
                return {
                    "schema_version": SUMMARY_SCHEMA,
                    "instrumentation_status": "ENABLED",
                    "publication_scope_id": self.publication_scope_id,
                    "measurement_binding_status": measurement_status,
                    "ledger_status": "COMPLETE" if writer_complete else "PARTIAL",
                    "structured_observation_status": (
                        "COMPLETE_PENDING_INDEPENDENT_READBACK"
                        if writer_complete
                        else "PARTIAL"
                    ),
                    "actual_kpi_status": (
                        "PENDING_INDEPENDENT_READBACK"
                        if writer_complete
                        else "NOT_ESTIMABLE"
                    ),
                    "actual_metrics": {
                        "expert_calls": None,
                        "prompt_tokens": None,
                        "completion_tokens": None,
                        "total_tokens": None,
                    },
                    "derived_observation": {
                        "expert_calls": derived_calls,
                        "prompt_tokens": derived_prompt,
                        "completion_tokens": derived_completion,
                        "total_tokens": derived_total,
                    },
                    "reason_codes": reasons,
                    "row_attempt_count": len(row_keys),
                    "sealed_row_attempt_count": len(self._seal_by_row),
                    "aborted_row_attempt_count": len(self._abort_by_row),
                    "linked_row_attempt_count": len(self._link_by_row),
                    "open_call_count": sum(row["open_call_count"] for row in rows),
                }

    def readback(self) -> Dict[str, Any]:
        summary = self.summary()
        if not self.enabled:
            return {
                "schema_version": READBACK_SCHEMA,
                "scope": None,
                "frames": [],
                "summary": summary,
            }
        assert self.lock_path is not None
        with self._lock:
            with _exclusive_file_lock(self.lock_path):
                scope = self._read_scope_sidecar()
                self._reload_frames()
                frames = sorted(
                    (json.loads(json.dumps(item)) for item in self._frames.values()),
                    key=lambda item: (item["frame_kind"], item["identity_sha256"]),
                )
        return {
            "schema_version": READBACK_SCHEMA,
            "scope": scope,
            "frames": frames,
            "summary": summary,
        }


__all__ = [
    "DEFAULT_STAGE_ALLOWLIST",
    "DecisionCallLedgerConflict",
    "DecisionCallLedgerDisabled",
    "DecisionCallLedgerError",
    "DecisionCallLedgerIncomplete",
    "DecisionCallLedgerRegistry",
    "RowAttemptScope",
]
