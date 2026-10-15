"""외부 owner trust store를 실제 파일시스템에서 실행하는 P0 보조 컴포넌트.

이 모듈은 caller가 넘긴 key를 받지 않는다. 고정 이름의 canonical trust anchor와
revocation snapshot을 run/packet/protected root 밖에서 읽고, 그 anchor 안의 key로
기존 owner-root preauthorization HMAC을 검증한 뒤 nonce를 ``O_EXCL`` 파일로 한 번만
소비한다. nonce 파일은 완전히 기록되기 전에 장애가 나더라도 남겨 두어 재시도를
fail-close 한다.

다만 trust store 경로와 시스템 wall clock은 caller/로컬 환경이 선택한 값이다.
따라서 실제 파일 읽기, store-key 서명 검증, nonce 소비 사실만 증명하며 외부 trust,
독립 revocation-current, trusted time, owner authority, P0 exit 또는 production 승인을
부여하지 않는다.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import base64
import binascii
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import re
import secrets
import stat
import threading
from types import MappingProxyType
from typing import Any, Iterator, Mapping, Sequence
import weakref


TRUST_ANCHOR_FILENAME = "p0_external_owner_trust_anchor_v1.json"
REVOCATION_SNAPSHOT_FILENAME = "p0_external_owner_revocation_snapshot_v1.json"
NONCE_LEDGER_DIRECTORY = "p0_external_owner_consumed_nonces_v1"

TRUST_ANCHOR_SCHEMA = "p0_external_owner_trust_anchor_v1"
REVOCATION_SNAPSHOT_SCHEMA = "p0_external_owner_revocation_snapshot_v1"
NONCE_RECORD_SCHEMA = "p0_external_owner_nonce_consumption_v1"
EXECUTION_RECEIPT_SCHEMA = "p0_external_owner_trust_execution_receipt_v1"

PREAUTHORIZATION_SCHEMA = "p0_actual_owner_capture_root_preauthorization_v1"
PREAUTHORIZATION_DOMAIN = (
    "llm-novel-dc-community-parser/"
    "p0-actual-owner-capture-root-preauthorization/v1"
)
NONCE_COMMITMENT_DOMAIN = "p0-actual-owner-root-preauthorization-nonce-v1"
ACTUAL_ORIGIN = "ACTUAL_AUTHORITY_OBSERVED"
ALGORITHM = "HMAC-SHA256"
PARSER_RECEIPT_SCHEMA = "p0_actual_parser_runtime_receipt_v2"
PACKET_MANIFEST_SCHEMA = "p0_actual_keyless_pilot_manifest_v1"
PACKET_FIXED_MEMBER_CONTRACT_SHA256 = (
    "72189ac02f34f100c5d07e62f1acccb3a86f79756f3381e57dba637341012256"
)
AUTHORITY_SCOPE = "P0_ACTUAL_PILOT_SHADOW_ONLY"
PREAUTHORIZATION_DECISION = "AUTHORIZE_FIXED_ROOT_P0_ACTUAL_SHADOW_CAPTURE"
PREAUTHORIZATION_OPERATIONAL_EFFECT = "NONE_SHADOW_ONLY"
REQUIRED_WATCH_CATEGORIES = (
    "CENTRAL_SLANG_DB",
    "CHECKPOINT",
    "DECISION_LEDGER",
    "PUBLICATION_JOURNAL",
    "RECOVERY",
    "RESULT",
)

_MAX_JSON_BYTES = 1024 * 1024
_MIN_KEY_BYTES = 32
_MAX_KEY_BYTES = 128
_FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_FILE_ID_128 = re.compile(r"^[0-9a-f]{32}$")
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")
_NONCE_FILENAME = re.compile(r"^[0-9a-f]{64}\.json$")
_ASCII_DECIMAL = re.compile(r"^(?:0|[1-9][0-9]*)$")
_VOLUME_GUID_PATH = re.compile(
    r"^\\\\\?\\Volume\{[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-"
    r"[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}\}\\[^/]+(?:\\[^/]+)*$"
)


class P0ExternalOwnerTrustExecutionError(ValueError):
    """외부 trust 실행이 안전하게 완료되지 못했을 때 발생한다."""


@dataclass(frozen=True, eq=False)
class _ExternalOwnerTrustExecutionState:
    """동일 프로세스 supervisor만 사용하는 exact object-identity seal."""

    public_receipt: Mapping[str, Any]
    _execution_seal: bytes


@dataclass
class _IssuedStateSecret:
    key: bytearray
    execution_seal: bytearray
    receipt_sha256: str
    context_projection_sha256: str
    nonce_commitment_sha256: str
    key_id: str
    key_fingerprint_sha256: str
    issuer_pid: int


@dataclass(frozen=True)
class _IssuedStateRecord:
    secret: _IssuedStateSecret
    state_ref: weakref.ReferenceType[_ExternalOwnerTrustExecutionState]
    finalizer: weakref.finalize


_ISSUED_STATE_LOCK = threading.Lock()
_ISSUED_STATE_RECORDS: dict[int, _IssuedStateRecord] = {}

_TRUST_STATE_CONTEXT_FIELDS = (
    "schema_version",
    "store_id",
    "session_id",
    "run_id",
    "preauthorization_id",
    "preauthorization_artifact_sha256",
    "preauthorization_bytes_sha256",
    "key_id",
    "key_fingerprint_sha256",
    "owner_principal_sha256",
    "owner_anchor_sha256",
    "nonce_commitment_sha256",
    "packet_root_tuple_sha256",
    "parser_provenance_sha256",
    "revocation_snapshot_id",
    "revocation_sequence",
    "trust_anchor_redacted_projection_sha256",
    "revocation_snapshot_artifact_sha256",
    "revocation_snapshot_bytes_sha256",
    "nonce_record_artifact_sha256",
    "nonce_record_bytes_sha256",
)


def _freeze_state_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType(
            {key: _freeze_state_json(item) for key, item in value.items()}
        )
    if isinstance(value, list):
        return tuple(_freeze_state_json(item) for item in value)
    return value


def _thaw_state_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw_state_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_state_json(item) for item in value]
    return value


def _trust_state_context_projection(receipt: Mapping[str, Any]) -> dict[str, Any]:
    try:
        return {field: receipt[field] for field in _TRUST_STATE_CONTEXT_FIELDS}
    except (KeyError, TypeError) as exc:
        raise P0ExternalOwnerTrustExecutionError(
            "external trust state receipt is missing fixed context"
        ) from exc


def _issue_external_owner_trust_state(
    receipt: Mapping[str, Any], key: bytes
) -> _ExternalOwnerTrustExecutionState:
    detached_receipt = _plain_json(receipt, "issued external trust receipt")
    if not isinstance(detached_receipt, dict):
        raise P0ExternalOwnerTrustExecutionError(
            "issued external trust receipt must be an object"
        )
    execution_seal = secrets.token_bytes(32)
    state = _ExternalOwnerTrustExecutionState(
        _freeze_state_json(detached_receipt),
        execution_seal,
    )
    secret = _IssuedStateSecret(
        key=bytearray(key),
        execution_seal=bytearray(execution_seal),
        receipt_sha256=str(receipt["receipt_sha256"]),
        context_projection_sha256=canonical_sha256(
            _trust_state_context_projection(detached_receipt)
        ),
        nonce_commitment_sha256=str(receipt["nonce_commitment_sha256"]),
        key_id=str(receipt["key_id"]),
        key_fingerprint_sha256=str(receipt["key_fingerprint_sha256"]),
        issuer_pid=os.getpid(),
    )
    state_id = id(state)
    finalizer = weakref.finalize(
        state,
        _finalize_external_owner_trust_state,
        state_id,
        secret,
        _ISSUED_STATE_RECORDS,
        _ISSUED_STATE_LOCK,
    )
    finalizer.atexit = False
    record = _IssuedStateRecord(
        secret=secret,
        state_ref=weakref.ref(state),
        finalizer=finalizer,
    )
    with _ISSUED_STATE_LOCK:
        if state_id in _ISSUED_STATE_RECORDS:  # pragma: no cover - live id reuse
            finalizer.detach()
            _burn_secret(secret)
            raise P0ExternalOwnerTrustExecutionError(
                "external trust state object identity collision"
            )
        _ISSUED_STATE_RECORDS[state_id] = record
    return state


def _burn_secret(secret: _IssuedStateSecret) -> None:
    for buffer in (secret.key, secret.execution_seal):
        for index in range(len(buffer)):
            buffer[index] = 0


def _finalize_external_owner_trust_state(
    state_id: int,
    secret: _IssuedStateSecret,
    registry: dict[int, _IssuedStateRecord],
    registry_lock: threading.Lock,
) -> None:
    with registry_lock:
        record = registry.get(state_id)
        if record is None or record.secret is not secret:
            return
        registry.pop(state_id, None)
    _burn_secret(secret)


def _discard_external_owner_trust_state(state: Any) -> None:
    if type(state) is not _ExternalOwnerTrustExecutionState:
        return
    with _ISSUED_STATE_LOCK:
        state_id = id(state)
        record = _ISSUED_STATE_RECORDS.get(state_id)
        if record is None or record.state_ref() is not state:
            record = None
        else:
            _ISSUED_STATE_RECORDS.pop(state_id, None)
    if record is not None:
        record.finalizer.detach()
        _burn_secret(record.secret)


def _consume_external_owner_trust_state(
    state: Any,
    *,
    expected_receipt_sha256: str,
    expected_nonce_commitment_sha256: str,
) -> bytes:
    """Consume one exact module-issued seal and return its key exactly once."""

    if type(state) is not _ExternalOwnerTrustExecutionState:
        raise P0ExternalOwnerTrustExecutionError(
            "external trust state must be the exact module-issued type"
        )
    with _ISSUED_STATE_LOCK:
        state_id = id(state)
        record = _ISSUED_STATE_RECORDS.get(state_id)
        if record is None or record.state_ref() is not state:
            record = None
        else:
            _ISSUED_STATE_RECORDS.pop(state_id, None)
    if record is None:
        raise P0ExternalOwnerTrustExecutionError(
            "external trust state was not issued, was copied, or was already consumed"
        )
    record.finalizer.detach()
    secret = record.secret
    try:
        expected_receipt = _sha(
            expected_receipt_sha256, "expected_receipt_sha256"
        )
        expected_nonce = _sha(
            expected_nonce_commitment_sha256,
            "expected_nonce_commitment_sha256",
        )
        receipt = _thaw_state_json(state.public_receipt)
        if not isinstance(receipt, dict):
            raise P0ExternalOwnerTrustExecutionError(
                "external trust state receipt must be an object"
            )
        material = dict(receipt)
        declared_receipt = _sha(
            material.pop("receipt_sha256", None), "state receipt.receipt_sha256"
        )
        context_projection = _trust_state_context_projection(receipt)
        state_seal_ok = bool(
            type(state._execution_seal) is bytes
            and len(state._execution_seal) == 32
            and hmac.compare_digest(
                state._execution_seal,
                bytes(secret.execution_seal),
            )
        )
        if (
            secret.issuer_pid != os.getpid()
            or not state_seal_ok
            or declared_receipt != canonical_sha256(material)
            or not hmac.compare_digest(declared_receipt, secret.receipt_sha256)
            or not hmac.compare_digest(declared_receipt, expected_receipt)
            or not hmac.compare_digest(
                canonical_sha256(context_projection),
                secret.context_projection_sha256,
            )
            or receipt.get("nonce_commitment_sha256") != secret.nonce_commitment_sha256
            or not hmac.compare_digest(secret.nonce_commitment_sha256, expected_nonce)
            or receipt.get("key_id") != secret.key_id
            or receipt.get("key_fingerprint_sha256")
            != secret.key_fingerprint_sha256
            or not hmac.compare_digest(
                hashlib.sha256(secret.key).hexdigest(),
                secret.key_fingerprint_sha256,
            )
        ):
            raise P0ExternalOwnerTrustExecutionError(
                "external trust state receipt/key/nonce seal binding mismatch"
            )
        return bytes(secret.key)
    except P0ExternalOwnerTrustExecutionError:
        raise
    except Exception as exc:
        raise P0ExternalOwnerTrustExecutionError(
            "external trust state receipt/key/nonce seal binding mismatch"
        ) from exc
    finally:
        _burn_secret(secret)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def json_file_bytes(value: Any) -> bytes:
    return canonical_bytes(value) + b"\n"


def nonce_commitment_sha256(nonce: str) -> str:
    nonce_value = _identifier(nonce, "nonce")
    return canonical_sha256(
        {"domain": NONCE_COMMITMENT_DOMAIN, "nonce": nonce_value}
    )


def _identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or _SAFE_ID.fullmatch(value) is None:
        raise P0ExternalOwnerTrustExecutionError(f"{label} is invalid")
    return value


def _sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise P0ExternalOwnerTrustExecutionError(
            f"{label} must be lowercase SHA-256"
        )
    return value


def _text(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or len(value) > 256
        or any(ord(char) < 32 for char in value)
    ):
        raise P0ExternalOwnerTrustExecutionError(
            f"{label} must be canonical nonempty text"
        )
    return value


def _strict_object(
    value: Any, fields: frozenset[str], label: str
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise P0ExternalOwnerTrustExecutionError(f"{label} must be an object")
    keys = frozenset(value)
    if keys != fields:
        raise P0ExternalOwnerTrustExecutionError(
            f"{label} fields mismatch: missing={sorted(fields - keys)}, "
            f"extra={sorted(keys - fields)}"
        )
    return dict(value)


def _reject_duplicate_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise P0ExternalOwnerTrustExecutionError(
                f"duplicate JSON key is forbidden: {key}"
            )
        result[key] = value
    return result


def _reject_nonfinite(token: str) -> None:
    raise P0ExternalOwnerTrustExecutionError(
        f"non-finite JSON constant is forbidden: {token}"
    )


def _parse_canonical_json(raw: bytes, label: str) -> dict[str, Any]:
    if type(raw) is not bytes:
        raise P0ExternalOwnerTrustExecutionError(f"{label} must be exact bytes")
    if (
        not raw
        or len(raw) > _MAX_JSON_BYTES
        or raw.startswith(b"\xef\xbb\xbf")
        or b"\r" in raw
        or not raw.endswith(b"\n")
    ):
        raise P0ExternalOwnerTrustExecutionError(f"{label} framing is invalid")
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_object,
            parse_constant=_reject_nonfinite,
        )
    except P0ExternalOwnerTrustExecutionError:
        raise
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise P0ExternalOwnerTrustExecutionError(
            f"{label} must be strict UTF-8 JSON"
        ) from exc
    if not isinstance(value, dict):
        raise P0ExternalOwnerTrustExecutionError(f"{label} must be an object")
    try:
        expected = json_file_bytes(value)
    except (TypeError, ValueError) as exc:
        raise P0ExternalOwnerTrustExecutionError(
            f"{label} cannot be canonicalized"
        ) from exc
    if raw != expected:
        raise P0ExternalOwnerTrustExecutionError(
            f"{label} must use exact canonical JSON plus one final LF"
        )
    return value


def _timestamp(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise P0ExternalOwnerTrustExecutionError(
            f"{label} must be canonical RFC3339 UTC"
        )
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise P0ExternalOwnerTrustExecutionError(
            f"{label} must be canonical RFC3339 UTC"
        ) from exc
    if parsed.isoformat().replace("+00:00", "Z") != value:
        raise P0ExternalOwnerTrustExecutionError(
            f"{label} must be canonical RFC3339 UTC"
        )
    return parsed


def _format_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _plain_json(value: Any, label: str) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise P0ExternalOwnerTrustExecutionError(
                f"{label} contains a non-finite number"
            )
        return value
    if isinstance(value, list):
        return [_plain_json(item, label) for item in value]
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str) or key in result:
                raise P0ExternalOwnerTrustExecutionError(
                    f"{label} contains an invalid object key"
                )
            result[key] = _plain_json(item, label)
        return result
    raise P0ExternalOwnerTrustExecutionError(
        f"{label} contains a non-JSON value"
    )


def _is_reparse(info: os.stat_result) -> bool:
    attributes = getattr(info, "st_file_attributes", 0)
    return bool(attributes & _FILE_ATTRIBUTE_REPARSE_POINT)


def _assert_no_alias_chain(path: Path, label: str) -> None:
    absolute = Path(os.path.abspath(os.fspath(path)))
    parts = absolute.parts
    if not parts:
        raise P0ExternalOwnerTrustExecutionError(f"{label} path is invalid")
    current = Path(parts[0])
    start = 1
    if len(parts) > 1 and parts[0] == os.sep:
        current = Path(os.sep)
    for part in parts[start:]:
        current = current / part
        try:
            info = os.lstat(current)
        except OSError as exc:
            raise P0ExternalOwnerTrustExecutionError(
                f"{label} path component cannot be inspected: {current}"
            ) from exc
        if stat.S_ISLNK(info.st_mode) or _is_reparse(info):
            raise P0ExternalOwnerTrustExecutionError(
                f"{label} path contains a symlink/reparse component: {current}"
            )


def _path_identity(path: Path) -> tuple[int, int]:
    info = os.stat(path, follow_symlinks=False)
    return (info.st_dev, info.st_ino)


def _same_or_nested(left: Path, right: Path) -> bool:
    left_text = os.path.normcase(os.fspath(left))
    right_text = os.path.normcase(os.fspath(right))
    try:
        return os.path.commonpath((left_text, right_text)) == right_text
    except ValueError:
        return False


def _ancestor_identities(path: Path) -> set[tuple[int, int]]:
    return {_path_identity(candidate) for candidate in (path, *path.parents)}


def _validate_store_location(
    trust_store_dir: Path | str,
    *,
    run_root: Path | str,
    packet_root: Path | str,
    protected_roots: Sequence[Path | str],
) -> Path:
    if isinstance(protected_roots, (str, bytes)) or not isinstance(
        protected_roots, Sequence
    ):
        raise P0ExternalOwnerTrustExecutionError(
            "protected_roots must be a sequence of filesystem paths"
        )
    supplied = [run_root, packet_root, *protected_roots]
    if not protected_roots:
        raise P0ExternalOwnerTrustExecutionError(
            "at least one protected root is required"
        )
    try:
        store = Path(trust_store_dir).resolve(strict=True)
    except (OSError, TypeError, ValueError) as exc:
        raise P0ExternalOwnerTrustExecutionError(
            "trust_store_dir must be an existing directory"
        ) from exc
    _assert_no_alias_chain(Path(trust_store_dir), "trust store")
    if not store.is_dir():
        raise P0ExternalOwnerTrustExecutionError(
            "trust_store_dir must be a directory"
        )
    resolved_roots: list[Path] = []
    for index, value in enumerate(supplied):
        try:
            root = Path(value).resolve(strict=True)
        except (OSError, TypeError, ValueError) as exc:
            raise P0ExternalOwnerTrustExecutionError(
                f"supplied root {index} must exist and resolve exactly"
            ) from exc
        _assert_no_alias_chain(Path(value), f"supplied root {index}")
        if not root.is_dir():
            raise P0ExternalOwnerTrustExecutionError(
                f"supplied root {index} must be a directory"
            )
        resolved_roots.append(root)
    for root in resolved_roots:
        store_ancestors = _ancestor_identities(store)
        root_ancestors = _ancestor_identities(root)
        if (
            _path_identity(store) == _path_identity(root)
            or _same_or_nested(store, root)
            or _same_or_nested(root, store)
            or _path_identity(root) in store_ancestors
            or _path_identity(store) in root_ancestors
        ):
            raise P0ExternalOwnerTrustExecutionError(
                "trust store must be outside run, packet, and protected roots"
            )
    return store


def _stable_regular_file_bytes(path: Path, label: str) -> bytes:
    try:
        before = os.lstat(path)
    except OSError as exc:
        raise P0ExternalOwnerTrustExecutionError(f"{label} is missing") from exc
    if (
        not stat.S_ISREG(before.st_mode)
        or stat.S_ISLNK(before.st_mode)
        or _is_reparse(before)
        or before.st_nlink != 1
        or not 0 < before.st_size <= _MAX_JSON_BYTES
    ):
        raise P0ExternalOwnerTrustExecutionError(
            f"{label} must be a bounded single-link regular non-reparse file"
        )
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise P0ExternalOwnerTrustExecutionError(f"{label} cannot be opened") from exc
    try:
        opened = os.fstat(descriptor)
        if (
            (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino)
            or opened.st_nlink != 1
            or not stat.S_ISREG(opened.st_mode)
        ):
            raise P0ExternalOwnerTrustExecutionError(
                f"{label} identity changed before read"
            )
        chunks: list[bytes] = []
        remaining = before.st_size
        while remaining:
            chunk = os.read(descriptor, min(remaining, 65536))
            if not chunk:
                raise P0ExternalOwnerTrustExecutionError(
                    f"{label} was truncated while reading"
                )
            chunks.append(chunk)
            remaining -= len(chunk)
        if os.read(descriptor, 1):
            raise P0ExternalOwnerTrustExecutionError(
                f"{label} grew while reading"
            )
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    if (
        (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
        != (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        or after.st_nlink != 1
    ):
        raise P0ExternalOwnerTrustExecutionError(
            f"{label} identity or metadata changed while reading"
        )
    final = os.lstat(path)
    if (
        (final.st_dev, final.st_ino, final.st_size, final.st_mtime_ns)
        != (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        or final.st_nlink != 1
        or stat.S_ISLNK(final.st_mode)
        or _is_reparse(final)
    ):
        raise P0ExternalOwnerTrustExecutionError(
            f"{label} namespace changed while reading"
        )
    return b"".join(chunks)


_ANCHOR_FIELDS = frozenset(
    {
        "schema_version",
        "store_id",
        "key_id",
        "algorithm",
        "key_fingerprint_sha256",
        "key_material_base64",
        "owner_principal_sha256",
        "owner_anchor_sha256",
        "nonce_ledger_device_decimal",
        "nonce_ledger_inode_decimal",
        "valid_from",
        "valid_to",
        "artifact_sha256",
    }
)
_REVOCATION_FIELDS = frozenset(
    {
        "schema_version",
        "store_id",
        "snapshot_id",
        "sequence",
        "issued_at",
        "valid_from",
        "valid_to",
        "revoked_key_ids",
        "revoked_owner_anchor_sha256",
        "artifact_sha256",
    }
)


def _validate_self_hash(row: Mapping[str, Any], label: str) -> str:
    stored = _sha(row.get("artifact_sha256"), f"{label}.artifact_sha256")
    material = {key: value for key, value in row.items() if key != "artifact_sha256"}
    if stored != canonical_sha256(material):
        raise P0ExternalOwnerTrustExecutionError(f"{label} self-hash mismatch")
    return stored


def _validate_anchor(value: Any, observed: datetime) -> tuple[dict[str, Any], bytes]:
    row = _strict_object(value, _ANCHOR_FIELDS, "trust anchor")
    if row["schema_version"] != TRUST_ANCHOR_SCHEMA:
        raise P0ExternalOwnerTrustExecutionError("trust anchor schema mismatch")
    _identifier(row["store_id"], "trust anchor.store_id")
    _identifier(row["key_id"], "trust anchor.key_id")
    if row["algorithm"] != ALGORITHM:
        raise P0ExternalOwnerTrustExecutionError("trust anchor algorithm mismatch")
    fingerprint = _sha(
        row["key_fingerprint_sha256"], "trust anchor.key_fingerprint_sha256"
    )
    _sha(row["owner_principal_sha256"], "trust anchor.owner_principal_sha256")
    _sha(row["owner_anchor_sha256"], "trust anchor.owner_anchor_sha256")
    for field in ("nonce_ledger_device_decimal", "nonce_ledger_inode_decimal"):
        value = row[field]
        if not isinstance(value, str) or _ASCII_DECIMAL.fullmatch(value) is None:
            raise P0ExternalOwnerTrustExecutionError(
                f"trust anchor.{field} must be canonical ASCII decimal"
            )
    valid_from = _timestamp(row["valid_from"], "trust anchor.valid_from")
    valid_to = _timestamp(row["valid_to"], "trust anchor.valid_to")
    if not valid_from < valid_to or not valid_from <= observed < valid_to:
        raise P0ExternalOwnerTrustExecutionError(
            "trust anchor is outside its local wall-clock validity window"
        )
    encoded = row["key_material_base64"]
    if not isinstance(encoded, str) or not encoded or any(char.isspace() for char in encoded):
        raise P0ExternalOwnerTrustExecutionError(
            "trust anchor key_material_base64 is invalid"
        )
    try:
        key = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise P0ExternalOwnerTrustExecutionError(
            "trust anchor key_material_base64 is invalid"
        ) from exc
    if not _MIN_KEY_BYTES <= len(key) <= _MAX_KEY_BYTES:
        raise P0ExternalOwnerTrustExecutionError(
            "trust anchor HMAC key length is invalid"
        )
    if not hmac.compare_digest(hashlib.sha256(key).hexdigest(), fingerprint):
        raise P0ExternalOwnerTrustExecutionError(
            "trust anchor key fingerprint mismatch"
        )
    _validate_self_hash(row, "trust anchor")
    return row, key


def _validate_sorted_unique_ids(value: Any, label: str) -> list[str]:
    if not isinstance(value, list):
        raise P0ExternalOwnerTrustExecutionError(f"{label} must be a list")
    result = [_identifier(item, label) for item in value]
    if result != sorted(result) or len(result) != len(set(result)):
        raise P0ExternalOwnerTrustExecutionError(
            f"{label} must be sorted and unique"
        )
    return result


def _validate_sorted_unique_shas(value: Any, label: str) -> list[str]:
    if not isinstance(value, list):
        raise P0ExternalOwnerTrustExecutionError(f"{label} must be a list")
    result = [_sha(item, label) for item in value]
    if result != sorted(result) or len(result) != len(set(result)):
        raise P0ExternalOwnerTrustExecutionError(
            f"{label} must be sorted and unique"
        )
    return result


def _validate_revocation(
    value: Any, *, anchor: Mapping[str, Any], observed: datetime
) -> dict[str, Any]:
    row = _strict_object(value, _REVOCATION_FIELDS, "revocation snapshot")
    if row["schema_version"] != REVOCATION_SNAPSHOT_SCHEMA:
        raise P0ExternalOwnerTrustExecutionError("revocation snapshot schema mismatch")
    if row["store_id"] != anchor["store_id"]:
        raise P0ExternalOwnerTrustExecutionError(
            "revocation snapshot store_id mismatch"
        )
    _identifier(row["snapshot_id"], "revocation snapshot.snapshot_id")
    sequence = row["sequence"]
    if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 1:
        raise P0ExternalOwnerTrustExecutionError(
            "revocation snapshot.sequence must be a positive integer"
        )
    issued = _timestamp(row["issued_at"], "revocation snapshot.issued_at")
    valid_from = _timestamp(row["valid_from"], "revocation snapshot.valid_from")
    valid_to = _timestamp(row["valid_to"], "revocation snapshot.valid_to")
    if not issued <= valid_from < valid_to or not valid_from <= observed < valid_to:
        raise P0ExternalOwnerTrustExecutionError(
            "revocation snapshot is outside its local wall-clock window"
        )
    revoked_keys = _validate_sorted_unique_ids(
        row["revoked_key_ids"], "revocation snapshot.revoked_key_ids"
    )
    revoked_anchors = _validate_sorted_unique_shas(
        row["revoked_owner_anchor_sha256"],
        "revocation snapshot.revoked_owner_anchor_sha256",
    )
    if anchor["key_id"] in revoked_keys or anchor["owner_anchor_sha256"] in revoked_anchors:
        raise P0ExternalOwnerTrustExecutionError(
            "owner key or anchor is revoked by the presented snapshot"
        )
    _validate_self_hash(row, "revocation snapshot")
    return row


_PREAUTHORIZATION_FIELDS = frozenset(
    {
        "schema_version",
        "record_origin",
        "preauthorization_id",
        "project_id",
        "run_id",
        "parser_run_id",
        "domain",
        "algorithm",
        "key_id",
        "owner_principal_sha256",
        "owner_anchor_sha256",
        "foundation_manifest_sha256",
        "launch_sha256",
        "owner_authorization_sha256",
        "watch_spec_sha256",
        "expected_provenance",
        "allowed_packet_root",
        "protected_roots",
        "category_root_map",
        "watch_requirements",
        "write_deny_requirements",
        "issued_at",
        "not_before",
        "expires_at",
        "nonce",
        "single_use",
        "authority_scope",
        "decision",
        "public_apply",
        "central_slang_db_write",
        "publication_wal_write",
        "production_approval",
        "full_scan_approval",
        "preauthorization_signature_sha256",
        "verification_status",
        "action_applied",
        "operational_effect",
        "artifact_sha256",
    }
)
_ROOT_FIELDS = frozenset(
    {
        "root_id",
        "final_volume_guid_path",
        "volume_serial_decimal",
        "file_id_128_hex",
        "access_intent",
    }
)
_PROVENANCE_FIELDS = frozenset(
    {
        "parser_receipt_schema",
        "parser_manifest_sha256",
        "parser_version",
        "capture_manifest_sha256",
        "input_registry_sha256",
        "source_input_plan_sha256",
        "sampling_frame_sha256",
        "packet_manifest_schema",
        "packet_fixed_member_contract_sha256",
    }
)
_CATEGORY_FIELDS = frozenset(
    {"category", "root_id", "relative_root", "required_min_count"}
)
_WATCH_REQUIREMENT_FIELDS = frozenset(
    {
        "pre_post_required",
        "recursive_exact_membership_required",
        "identity_per_member_required",
        "continuous_journal_or_equivalent_required",
        "overflow_or_gap_fail_closed",
        "independent_observer_required",
        "required_evidence_schema",
    }
)
_WRITE_DENY_REQUIREMENT_FIELDS = frozenset(
    {
        "os_enforcement_required",
        "protected_root_ids",
        "parser_principal_must_be_denied",
        "independent_verifier_required",
        "must_preexist_before_watch_pre",
        "must_remain_through_terminal_attestation",
        "required_evidence_schema",
    }
)


def _validated_root(value: Any, *, packet: bool, label: str) -> dict[str, Any]:
    row = _strict_object(value, _ROOT_FIELDS, label)
    _identifier(row["root_id"], f"{label}.root_id")
    final_path = row["final_volume_guid_path"]
    serial = row["volume_serial_decimal"]
    file_id = row["file_id_128_hex"]
    if (
        not isinstance(final_path, str)
        or _VOLUME_GUID_PATH.fullmatch(final_path) is None
        or any(
            component in {"", ".", ".."}
            or ":" in component
            or component.rstrip(" .") != component
            for component in final_path.split("\\")[4:]
        )
    ):
        raise P0ExternalOwnerTrustExecutionError(f"{label} final path is invalid")
    if (
        not isinstance(serial, str)
        or _ASCII_DECIMAL.fullmatch(serial) is None
        or not 0 <= int(serial) < 2**64
    ):
        raise P0ExternalOwnerTrustExecutionError(f"{label} volume serial is invalid")
    if not isinstance(file_id, str) or _FILE_ID_128.fullmatch(file_id) is None:
        raise P0ExternalOwnerTrustExecutionError(f"{label} file ID is invalid")
    expected_intent = "WRITE_RUN_OUTPUT_ONLY" if packet else "READ_ONLY_PROTECTED"
    if row["access_intent"] != expected_intent:
        raise P0ExternalOwnerTrustExecutionError(
            f"{label} access intent must be {expected_intent}"
        )
    return {
        **row,
        "_normalized_path": final_path.casefold().rstrip("\\"),
        "_identity": (str(int(serial)), file_id),
    }


def _paths_overlap(left: str, right: str) -> bool:
    return (
        left == right
        or left.startswith(right + "\\")
        or right.startswith(left + "\\")
    )


def _relative_root(value: Any, label: str) -> str:
    text = _text(value, label).replace("\\", "/")
    if any(
        part in {"", ".", ".."}
        or ":" in part
        or part.rstrip(" .") != part
        for part in text.split("/")
    ):
        raise P0ExternalOwnerTrustExecutionError(
            f"{label} must be a canonical contained relative path"
        )
    return text


def _validate_preauthorization(
    raw: bytes,
    *,
    anchor: Mapping[str, Any],
    key: bytes,
    observed: datetime,
    run_id: str,
    nonce_commitment: str,
    expected_packet_root_final_path: str,
    expected_packet_root_volume_serial: int,
    expected_packet_root_file_id: str,
    expected_parser_provenance: Mapping[str, Any],
) -> tuple[dict[str, Any], str, str]:
    row = _strict_object(
        _parse_canonical_json(raw, "owner root preauthorization"),
        _PREAUTHORIZATION_FIELDS,
        "owner root preauthorization",
    )
    if row["schema_version"] != PREAUTHORIZATION_SCHEMA:
        raise P0ExternalOwnerTrustExecutionError("preauthorization schema mismatch")
    if row["record_origin"] != ACTUAL_ORIGIN:
        raise P0ExternalOwnerTrustExecutionError(
            "external trust execution requires ACTUAL preauthorization"
        )
    for field in ("preauthorization_id", "project_id", "run_id", "parser_run_id", "nonce"):
        _identifier(row[field], f"preauthorization.{field}")
    if row["run_id"] != run_id:
        raise P0ExternalOwnerTrustExecutionError("preauthorization run_id mismatch")
    if row["domain"] != PREAUTHORIZATION_DOMAIN or row["algorithm"] != ALGORITHM:
        raise P0ExternalOwnerTrustExecutionError(
            "preauthorization domain/algorithm mismatch"
        )
    if (
        row["key_id"] != anchor["key_id"]
        or row["owner_principal_sha256"] != anchor["owner_principal_sha256"]
        or row["owner_anchor_sha256"] != anchor["owner_anchor_sha256"]
    ):
        raise P0ExternalOwnerTrustExecutionError(
            "preauthorization owner anchor/key/principal binding mismatch"
        )
    for field in (
        "owner_principal_sha256",
        "owner_anchor_sha256",
        "foundation_manifest_sha256",
        "launch_sha256",
        "owner_authorization_sha256",
        "watch_spec_sha256",
    ):
        _sha(row[field], f"preauthorization.{field}")
    supplied_provenance = _plain_json(
        expected_parser_provenance, "expected_parser_provenance"
    )
    if not isinstance(supplied_provenance, dict):
        raise P0ExternalOwnerTrustExecutionError(
            "expected_parser_provenance must be an object"
        )
    supplied_provenance = _strict_object(
        supplied_provenance, _PROVENANCE_FIELDS, "expected_parser_provenance"
    )
    if (
        supplied_provenance["parser_receipt_schema"] != PARSER_RECEIPT_SCHEMA
        or supplied_provenance["packet_manifest_schema"] != PACKET_MANIFEST_SCHEMA
        or supplied_provenance["packet_fixed_member_contract_sha256"]
        != PACKET_FIXED_MEMBER_CONTRACT_SHA256
    ):
        raise P0ExternalOwnerTrustExecutionError(
            "expected_parser_provenance schema/fixed-contract mismatch"
        )
    _text(supplied_provenance["parser_version"], "expected_parser_provenance.parser_version")
    for field in (
        "parser_manifest_sha256",
        "capture_manifest_sha256",
        "input_registry_sha256",
        "source_input_plan_sha256",
        "sampling_frame_sha256",
        "packet_fixed_member_contract_sha256",
    ):
        _sha(supplied_provenance[field], f"expected_parser_provenance.{field}")
    if row["expected_provenance"] != supplied_provenance:
        raise P0ExternalOwnerTrustExecutionError(
            "preauthorization parser provenance binding mismatch"
        )
    packet_root = _validated_root(
        row["allowed_packet_root"],
        packet=True,
        label="preauthorization.allowed_packet_root",
    )
    protected_values = row["protected_roots"]
    if not isinstance(protected_values, list) or not protected_values:
        raise P0ExternalOwnerTrustExecutionError(
            "preauthorization.protected_roots must be a nonempty list"
        )
    protected = [
        _validated_root(
            value, packet=False, label=f"preauthorization.protected_roots[{index}]"
        )
        for index, value in enumerate(protected_values)
    ]
    protected_ids = [value["root_id"] for value in protected]
    if protected_ids != sorted(protected_ids) or len(protected_ids) != len(
        set(protected_ids)
    ):
        raise P0ExternalOwnerTrustExecutionError(
            "protected roots must have sorted unique root IDs"
        )
    if packet_root["root_id"] in set(protected_ids):
        raise P0ExternalOwnerTrustExecutionError(
            "packet and protected root IDs must differ"
        )
    all_roots = [packet_root, *protected]
    for index, left in enumerate(all_roots):
        for right in all_roots[index + 1 :]:
            if left["_identity"] == right["_identity"] or _paths_overlap(
                left["_normalized_path"], right["_normalized_path"]
            ):
                raise P0ExternalOwnerTrustExecutionError(
                    "packet/protected root identities and paths must not overlap"
                )

    category_values = row["category_root_map"]
    if not isinstance(category_values, list):
        raise P0ExternalOwnerTrustExecutionError(
            "preauthorization.category_root_map must be a list"
        )
    categories: list[dict[str, Any]] = []
    for index, value in enumerate(category_values):
        category = _strict_object(
            value, _CATEGORY_FIELDS, f"preauthorization.category_root_map[{index}]"
        )
        _text(category["category"], f"category_root_map[{index}].category")
        _identifier(category["root_id"], f"category_root_map[{index}].root_id")
        category["relative_root"] = _relative_root(
            category["relative_root"], f"category_root_map[{index}].relative_root"
        )
        count = category["required_min_count"]
        if isinstance(count, bool) or not isinstance(count, int) or count < 1:
            raise P0ExternalOwnerTrustExecutionError(
                "category required_min_count must be a positive integer"
            )
        if category["root_id"] not in set(protected_ids):
            raise P0ExternalOwnerTrustExecutionError(
                "category mapping references an unknown protected root"
            )
        categories.append(category)
    if [value["category"] for value in categories] != list(
        REQUIRED_WATCH_CATEGORIES
    ):
        raise P0ExternalOwnerTrustExecutionError(
            "category map must contain the exact ordered protected category set"
        )
    effective_paths = [
        next(
            root["_normalized_path"]
            for root in protected
            if root["root_id"] == category["root_id"]
        )
        + "\\"
        + category["relative_root"].replace("/", "\\").casefold()
        for category in categories
    ]
    for index, left in enumerate(effective_paths):
        if any(_paths_overlap(left, right) for right in effective_paths[index + 1 :]):
            raise P0ExternalOwnerTrustExecutionError(
                "category effective roots must be unique and non-overlapping"
            )

    watch = _strict_object(
        row["watch_requirements"],
        _WATCH_REQUIREMENT_FIELDS,
        "preauthorization.watch_requirements",
    )
    for field in (
        "pre_post_required",
        "recursive_exact_membership_required",
        "identity_per_member_required",
        "continuous_journal_or_equivalent_required",
        "overflow_or_gap_fail_closed",
        "independent_observer_required",
    ):
        if watch[field] is not True:
            raise P0ExternalOwnerTrustExecutionError(
                f"preauthorization.watch_requirements.{field} must be true"
            )
    _identifier(
        watch["required_evidence_schema"],
        "preauthorization.watch_requirements.required_evidence_schema",
    )
    write_deny = _strict_object(
        row["write_deny_requirements"],
        _WRITE_DENY_REQUIREMENT_FIELDS,
        "preauthorization.write_deny_requirements",
    )
    for field in (
        "os_enforcement_required",
        "parser_principal_must_be_denied",
        "independent_verifier_required",
        "must_preexist_before_watch_pre",
        "must_remain_through_terminal_attestation",
    ):
        if write_deny[field] is not True:
            raise P0ExternalOwnerTrustExecutionError(
                f"preauthorization.write_deny_requirements.{field} must be true"
            )
    if write_deny["protected_root_ids"] != protected_ids:
        raise P0ExternalOwnerTrustExecutionError(
            "write-deny protected root IDs must exactly match protected roots"
        )
    _identifier(
        write_deny["required_evidence_schema"],
        "preauthorization.write_deny_requirements.required_evidence_schema",
    )

    packet_final_path = packet_root["final_volume_guid_path"]
    packet_serial = packet_root["volume_serial_decimal"]
    packet_file_id = packet_root["file_id_128_hex"]
    if (
        not isinstance(packet_final_path, str)
        or _VOLUME_GUID_PATH.fullmatch(packet_final_path) is None
        or any(
            component in {"", ".", ".."}
            or ":" in component
            or component.rstrip(" .") != component
            for component in packet_final_path.split("\\")[4:]
        )
        or not isinstance(expected_packet_root_final_path, str)
        or _VOLUME_GUID_PATH.fullmatch(expected_packet_root_final_path) is None
        or packet_final_path.casefold()
        != expected_packet_root_final_path.casefold()
        or not isinstance(packet_serial, str)
        or _ASCII_DECIMAL.fullmatch(packet_serial) is None
        or not 0 <= int(packet_serial) < 2**64
        or isinstance(expected_packet_root_volume_serial, bool)
        or not isinstance(expected_packet_root_volume_serial, int)
        or not 0 <= expected_packet_root_volume_serial < 2**64
        or packet_serial != str(expected_packet_root_volume_serial)
        or not isinstance(packet_file_id, str)
        or _FILE_ID_128.fullmatch(packet_file_id) is None
        or not isinstance(expected_packet_root_file_id, str)
        or _FILE_ID_128.fullmatch(expected_packet_root_file_id) is None
        or packet_file_id != expected_packet_root_file_id
    ):
        raise P0ExternalOwnerTrustExecutionError(
            "preauthorization packet root tuple mismatch"
        )
    issued = _timestamp(row["issued_at"], "preauthorization.issued_at")
    not_before = _timestamp(row["not_before"], "preauthorization.not_before")
    expires = _timestamp(row["expires_at"], "preauthorization.expires_at")
    if not issued <= not_before < expires or not not_before <= observed < expires:
        raise P0ExternalOwnerTrustExecutionError(
            "preauthorization is outside its local wall-clock validity window"
        )
    if row["single_use"] is not True:
        raise P0ExternalOwnerTrustExecutionError("preauthorization must be single-use")
    if (
        row["authority_scope"] != AUTHORITY_SCOPE
        or row["decision"] != PREAUTHORIZATION_DECISION
        or row["operational_effect"] != PREAUTHORIZATION_OPERATIONAL_EFFECT
    ):
        raise P0ExternalOwnerTrustExecutionError(
            "preauthorization decision/scope/operational effect mismatch"
        )
    for field in (
        "public_apply",
        "central_slang_db_write",
        "publication_wal_write",
        "production_approval",
        "full_scan_approval",
        "action_applied",
    ):
        if row[field] is not False:
            raise P0ExternalOwnerTrustExecutionError(
                f"preauthorization capability must remain false: {field}"
            )
    if row["verification_status"] != "DETACHED_SIGNATURE_PRESENT_UNVERIFIED":
        raise P0ExternalOwnerTrustExecutionError(
            "preauthorization verification_status mismatch"
        )
    signature = _sha(
        row["preauthorization_signature_sha256"],
        "preauthorization.preauthorization_signature_sha256",
    )
    stored_artifact_sha = _validate_self_hash(row, "preauthorization")
    signature_material = {
        name: item
        for name, item in row.items()
        if name not in {"preauthorization_signature_sha256", "artifact_sha256"}
    }
    expected_signature = hmac.new(
        key, canonical_bytes(signature_material), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(signature, expected_signature):
        raise P0ExternalOwnerTrustExecutionError(
            "preauthorization signature mismatch for store key"
        )
    actual_nonce_commitment = nonce_commitment_sha256(row["nonce"])
    if not hmac.compare_digest(actual_nonce_commitment, nonce_commitment):
        raise P0ExternalOwnerTrustExecutionError(
            "preauthorization nonce commitment mismatch"
        )
    return row, stored_artifact_sha, hashlib.sha256(raw).hexdigest()


def _validate_nonce_inventory(nonce_dir: Path) -> None:
    _assert_no_alias_chain(nonce_dir, "nonce ledger")
    info = os.lstat(nonce_dir)
    if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode) or _is_reparse(info):
        raise P0ExternalOwnerTrustExecutionError(
            "nonce ledger must be a non-reparse directory"
        )
    with os.scandir(nonce_dir) as entries:
        for entry in entries:
            if _NONCE_FILENAME.fullmatch(entry.name) is None:
                raise P0ExternalOwnerTrustExecutionError(
                    "nonce ledger contains a noncanonical entry name"
                )
            # Windows ``DirEntry.stat`` can report ``st_nlink=0`` even though
            # ``os.lstat`` returns the kernel-observed link count correctly.
            entry_info = os.lstat(entry.path)
            if (
                not entry.is_file(follow_symlinks=False)
                or stat.S_ISLNK(entry_info.st_mode)
                or _is_reparse(entry_info)
                or entry_info.st_nlink != 1
            ):
                raise P0ExternalOwnerTrustExecutionError(
                    "nonce ledger contains an alias/reparse/hardlink entry"
                )


def _write_all(descriptor: int, raw: bytes) -> None:
    offset = 0
    while offset < len(raw):
        written = os.write(descriptor, raw[offset:])
        if written <= 0:
            raise OSError("short nonce ledger write")
        offset += written


@contextmanager
def _hold_nonce_directory(nonce_dir: Path) -> Iterator[int | None]:
    """Hold the ledger namespace stable, or retain a relative-open dir fd."""

    if os.name == "nt":
        import ctypes

        create_file = ctypes.WinDLL("kernel32", use_last_error=True).CreateFileW
        create_file.argtypes = [
            ctypes.c_wchar_p,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_void_p,
        ]
        create_file.restype = ctypes.c_void_p
        close_handle = ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle
        close_handle.argtypes = [ctypes.c_void_p]
        close_handle.restype = ctypes.c_int
        # Deliberately omit FILE_SHARE_DELETE. While this handle is live,
        # rename/delete replacement of the pinned ledger directory is denied.
        handle = create_file(
            os.fspath(nonce_dir),
            0x0080,  # FILE_READ_ATTRIBUTES
            0x00000001 | 0x00000002,  # FILE_SHARE_READ | FILE_SHARE_WRITE
            None,
            3,  # OPEN_EXISTING
            0x02000000 | 0x00200000,  # BACKUP_SEMANTICS | OPEN_REPARSE_POINT
            None,
        )
        if handle in (None, ctypes.c_void_p(-1).value):
            raise P0ExternalOwnerTrustExecutionError(
                "nonce ledger directory guard could not be acquired"
            )
        try:
            yield None
        finally:
            close_handle(handle)
        return

    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(nonce_dir, flags)
    except OSError as exc:
        raise P0ExternalOwnerTrustExecutionError(
            "nonce ledger directory guard could not be acquired"
        ) from exc
    try:
        yield descriptor
    finally:
        os.close(descriptor)


def _consume_nonce(
    nonce_dir: Path,
    *,
    directory_descriptor: int | None,
    nonce_commitment: str,
    record_material: Mapping[str, Any],
) -> tuple[dict[str, Any], str]:
    material = dict(record_material)
    material["schema_version"] = NONCE_RECORD_SCHEMA
    record = {**material, "artifact_sha256": canonical_sha256(material)}
    raw = json_file_bytes(record)
    target = nonce_dir / f"{nonce_commitment}.json"
    before_dir_identity = (
        (os.fstat(directory_descriptor).st_dev, os.fstat(directory_descriptor).st_ino)
        if directory_descriptor is not None
        else _path_identity(nonce_dir)
    )
    flags = (
        os.O_CREAT
        | os.O_EXCL
        | os.O_RDWR
        | getattr(os, "O_BINARY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        if directory_descriptor is None:
            descriptor = os.open(target, flags, 0o600)
        else:
            descriptor = os.open(
                target.name, flags, 0o600, dir_fd=directory_descriptor
            )
    except FileExistsError as exc:
        raise P0ExternalOwnerTrustExecutionError(
            "single-use nonce was already consumed or reserved"
        ) from exc
    except OSError as exc:
        raise P0ExternalOwnerTrustExecutionError(
            "single-use nonce could not be reserved atomically"
        ) from exc
    # 생성 뒤의 모든 오류에서 파일을 지우지 않는다. 부분 파일도 영구 replay 거부다.
    try:
        created = os.fstat(descriptor)
        if not stat.S_ISREG(created.st_mode) or created.st_nlink != 1:
            raise P0ExternalOwnerTrustExecutionError(
                "created nonce record is not a single-link regular file"
            )
        _write_all(descriptor, raw)
        os.fsync(descriptor)
        os.lseek(descriptor, 0, os.SEEK_SET)
        read_back = bytearray()
        while len(read_back) < len(raw):
            chunk = os.read(descriptor, len(raw) - len(read_back))
            if not chunk:
                break
            read_back.extend(chunk)
        final_open = os.fstat(descriptor)
        if bytes(read_back) != raw or final_open.st_nlink != 1:
            raise P0ExternalOwnerTrustExecutionError(
                "nonce record durable read-back mismatch"
            )
    except P0ExternalOwnerTrustExecutionError:
        raise
    except OSError as exc:
        raise P0ExternalOwnerTrustExecutionError(
            "nonce record durable write failed closed"
        ) from exc
    finally:
        os.close(descriptor)
    try:
        final_path = os.lstat(target)
    except OSError as exc:
        raise P0ExternalOwnerTrustExecutionError(
            "nonce record disappeared after durable write"
        ) from exc
    if (
        (final_path.st_dev, final_path.st_ino) != (created.st_dev, created.st_ino)
        or final_path.st_nlink != 1
        or not stat.S_ISREG(final_path.st_mode)
        or stat.S_ISLNK(final_path.st_mode)
        or _is_reparse(final_path)
        or _path_identity(nonce_dir) != before_dir_identity
    ):
        raise P0ExternalOwnerTrustExecutionError(
            "nonce ledger namespace changed during atomic consumption"
        )
    # POSIX에서는 directory entry 자체도 가능한 범위에서 flush한다.
    if os.name != "nt":
        try:
            if directory_descriptor is None:  # pragma: no cover - held on POSIX
                raise OSError("missing held nonce directory descriptor")
            os.fsync(directory_descriptor)
        except OSError as exc:
            raise P0ExternalOwnerTrustExecutionError(
                "nonce ledger directory flush failed closed"
            ) from exc
    return record, hashlib.sha256(raw).hexdigest()


def _execute_external_owner_trust_state(
    *,
    trust_store_dir: Path | str,
    run_root: Path | str,
    packet_root: Path | str,
    protected_roots: Sequence[Path | str],
    owner_root_preauthorization_bytes: bytes,
    session_id: str,
    run_id: str,
    nonce_commitment_sha256: str,
    expected_packet_root_final_path: str,
    expected_packet_root_volume_serial: int,
    expected_packet_root_file_id: str,
    expected_parser_provenance: Mapping[str, Any],
) -> _ExternalOwnerTrustExecutionState:
    """파일시스템 trust 실행과 key-bearing private state를 함께 반환한다."""

    session = _identifier(session_id, "session_id")
    run = _identifier(run_id, "run_id")
    nonce_commitment = _sha(nonce_commitment_sha256, "nonce_commitment_sha256")
    if type(owner_root_preauthorization_bytes) is not bytes:
        raise P0ExternalOwnerTrustExecutionError(
            "owner_root_preauthorization_bytes must be exact bytes"
        )
    store = _validate_store_location(
        trust_store_dir,
        run_root=run_root,
        packet_root=packet_root,
        protected_roots=protected_roots,
    )
    expected_names = {
        TRUST_ANCHOR_FILENAME,
        REVOCATION_SNAPSHOT_FILENAME,
        NONCE_LEDGER_DIRECTORY,
    }
    with os.scandir(store) as entries:
        actual_names = {entry.name for entry in entries}
    if actual_names != expected_names:
        raise P0ExternalOwnerTrustExecutionError(
            "trust store must contain the exact canonical inventory"
        )
    nonce_dir = store / NONCE_LEDGER_DIRECTORY
    _validate_nonce_inventory(nonce_dir)
    store_identity = _path_identity(store)
    anchor_raw = _stable_regular_file_bytes(
        store / TRUST_ANCHOR_FILENAME, "trust anchor"
    )
    revocation_raw = _stable_regular_file_bytes(
        store / REVOCATION_SNAPSHOT_FILENAME, "revocation snapshot"
    )
    if _path_identity(store) != store_identity:
        raise P0ExternalOwnerTrustExecutionError(
            "trust store identity changed while reading"
        )
    observed = datetime.now(timezone.utc)
    anchor, key = _validate_anchor(
        _parse_canonical_json(anchor_raw, "trust anchor"), observed
    )
    nonce_ledger_info = os.stat(nonce_dir, follow_symlinks=False)
    if (
        anchor["nonce_ledger_device_decimal"] != str(nonce_ledger_info.st_dev)
        or anchor["nonce_ledger_inode_decimal"] != str(nonce_ledger_info.st_ino)
    ):
        raise P0ExternalOwnerTrustExecutionError(
            "nonce ledger filesystem identity does not match trust anchor pin"
        )
    revocation = _validate_revocation(
        _parse_canonical_json(revocation_raw, "revocation snapshot"),
        anchor=anchor,
        observed=observed,
    )
    wall_clock_observed_at = _format_timestamp(observed)
    trust_anchor_redacted_projection = {
        name: item
        for name, item in anchor.items()
        if name not in {"key_material_base64", "artifact_sha256"}
    }
    trust_anchor_artifact_sha = anchor["artifact_sha256"]
    trust_anchor_bytes_sha = hashlib.sha256(anchor_raw).hexdigest()
    revocation_artifact_sha = revocation["artifact_sha256"]
    revocation_bytes_sha = hashlib.sha256(revocation_raw).hexdigest()
    provenance = _plain_json(expected_parser_provenance, "expected_parser_provenance")
    if not isinstance(provenance, dict):
        raise P0ExternalOwnerTrustExecutionError(
            "expected_parser_provenance must be an object"
        )
    preauth, preauth_artifact_sha, preauth_bytes_sha = _validate_preauthorization(
        owner_root_preauthorization_bytes,
        anchor=anchor,
        key=key,
        observed=observed,
        run_id=run,
        nonce_commitment=nonce_commitment,
        expected_packet_root_final_path=expected_packet_root_final_path,
        expected_packet_root_volume_serial=expected_packet_root_volume_serial,
        expected_packet_root_file_id=expected_packet_root_file_id,
        expected_parser_provenance=provenance,
    )
    packet_root_tuple = {
        "final_volume_guid_path": preauth["allowed_packet_root"][
            "final_volume_guid_path"
        ],
        "volume_serial_decimal": preauth["allowed_packet_root"][
            "volume_serial_decimal"
        ],
        "file_id_128_hex": preauth["allowed_packet_root"]["file_id_128_hex"],
    }
    consumed_at = _format_timestamp(datetime.now(timezone.utc))
    with _hold_nonce_directory(nonce_dir) as nonce_directory_descriptor:
        held_nonce_info = os.stat(nonce_dir, follow_symlinks=False)
        if (
            anchor["nonce_ledger_device_decimal"] != str(held_nonce_info.st_dev)
            or anchor["nonce_ledger_inode_decimal"] != str(held_nonce_info.st_ino)
        ):
            raise P0ExternalOwnerTrustExecutionError(
                "held nonce ledger identity does not match trust anchor pin"
            )
        nonce_record, nonce_record_bytes_sha = _consume_nonce(
            nonce_dir,
            directory_descriptor=nonce_directory_descriptor,
            nonce_commitment=nonce_commitment,
            record_material={
                "store_id": anchor["store_id"],
                "session_id": session,
                "run_id": run,
                "preauthorization_id": preauth["preauthorization_id"],
                "preauthorization_artifact_sha256": preauth_artifact_sha,
                "preauthorization_bytes_sha256": preauth_bytes_sha,
                "key_id": anchor["key_id"],
                "owner_principal_sha256": anchor["owner_principal_sha256"],
                "owner_anchor_sha256": anchor["owner_anchor_sha256"],
                "nonce_commitment_sha256": nonce_commitment,
                "packet_root_tuple": packet_root_tuple,
                "parser_provenance_sha256": canonical_sha256(provenance),
                "revocation_snapshot_id": revocation["snapshot_id"],
                "revocation_sequence": revocation["sequence"],
                "trust_anchor_artifact_sha256": trust_anchor_artifact_sha,
                "trust_anchor_bytes_sha256": trust_anchor_bytes_sha,
                "revocation_snapshot_artifact_sha256": revocation_artifact_sha,
                "revocation_snapshot_bytes_sha256": revocation_bytes_sha,
                "wall_clock_observed_at": wall_clock_observed_at,
                "consumed_at": consumed_at,
            },
        )
    receipt_material = {
        "schema_version": EXECUTION_RECEIPT_SCHEMA,
        "store_id": anchor["store_id"],
        "session_id": session,
        "run_id": run,
        "preauthorization_id": preauth["preauthorization_id"],
        "preauthorization_artifact_sha256": preauth_artifact_sha,
        "preauthorization_bytes_sha256": preauth_bytes_sha,
        "key_id": anchor["key_id"],
        "key_fingerprint_sha256": anchor["key_fingerprint_sha256"],
        "owner_principal_sha256": anchor["owner_principal_sha256"],
        "owner_anchor_sha256": anchor["owner_anchor_sha256"],
        "nonce_commitment_sha256": nonce_commitment,
        "packet_root_tuple": packet_root_tuple,
        "packet_root_tuple_sha256": canonical_sha256(packet_root_tuple),
        "parser_provenance_sha256": canonical_sha256(provenance),
        "revocation_snapshot_id": revocation["snapshot_id"],
        "revocation_sequence": revocation["sequence"],
        "trust_anchor_redacted_projection_sha256": canonical_sha256(
            trust_anchor_redacted_projection
        ),
        "trust_anchor_full_hash_withheld_from_public_receipt": True,
        "revocation_snapshot_artifact_sha256": revocation_artifact_sha,
        "revocation_snapshot_bytes_sha256": revocation_bytes_sha,
        "wall_clock_observed_at": wall_clock_observed_at,
        "nonce_record_artifact_sha256": nonce_record["artifact_sha256"],
        "nonce_record_bytes_sha256": nonce_record_bytes_sha,
        "trust_store_filesystem_execution_observed": True,
        "trust_store_exact_inventory_verified": True,
        "trust_store_alias_guards_checked": True,
        "filesystem_namespace_alias_resolution_verified": False,
        "signature_verified_with_store_key": True,
        "anchor_local_wall_clock_window_match": True,
        "revocation_snapshot_local_wall_clock_window_match": True,
        "revocation_snapshot_no_match_for_key_or_anchor": True,
        "single_use_replay_consumed": True,
        "single_use_scope": "CURRENT_PINNED_PRESENTED_STORE_FILESYSTEM_EXECUTION",
        "nonce_atomic_create_exclusive_verified": True,
        "nonce_ledger_identity_pin_matched": True,
        "nonce_ledger_identity_pin_source": "CALLER_SELECTED_SELF_HASHED_TRUST_ANCHOR",
        "nonce_directory_namespace_guard_verified": True,
        "nonce_creation_relative_to_held_directory_verified": os.name != "nt",
        "nonce_directory_rename_delete_guard_verified": os.name == "nt",
        "cross_process_immutable_nonce_ledger_verified": False,
        "nonce_record_file_flush_verified": True,
        "nonce_directory_entry_flush_verified": os.name != "nt",
        "power_loss_durable_replay_verified": False,
        "nonce_ledger_action_applied": True,
        "security_control_state_mutated": True,
        "external_trust_store_verified": False,
        "revocation_current_verified": False,
        "trusted_time_verified": False,
        "external_owner_trust_verified": False,
        "external_root_identity_pin_verified": False,
        "filesystem_handle_trust_verified": False,
        "owner_authority_verified": False,
        "actual_authority_granted": False,
        "credited_actual_source_claim_count": 0,
        "credited_actual_a_context_review_count": 0,
        "production_approval": False,
        "full_scan_approval": False,
        "p0_phase_exit": False,
        "action_applied": False,
        "protected_pipeline_action_applied": False,
        "operational_effect": "NONCE_LEDGER_SECURITY_CONTROL_ONLY_NO_PIPELINE_EFFECT",
        "gate_status": "EXTERNAL_STORE_EXECUTED_ACTUAL_P0_AUTHORITY_NO_GO",
        "receipt_hash_scope": "CANONICAL_MATERIAL_EXCLUDING_RECEIPT_SHA256",
    }
    receipt = {
        **receipt_material,
        "receipt_sha256": canonical_sha256(receipt_material),
    }
    return _issue_external_owner_trust_state(receipt, key)


def execute_external_owner_trust(
    *,
    trust_store_dir: Path | str,
    run_root: Path | str,
    packet_root: Path | str,
    protected_roots: Sequence[Path | str],
    owner_root_preauthorization_bytes: bytes,
    session_id: str,
    run_id: str,
    nonce_commitment_sha256: str,
    expected_packet_root_final_path: str,
    expected_packet_root_volume_serial: int,
    expected_packet_root_file_id: str,
    expected_parser_provenance: Mapping[str, Any],
) -> dict[str, Any]:
    """실제 trust-store 실행 receipt만 반환하며 key는 공개하지 않는다."""

    state = _execute_external_owner_trust_state(
        trust_store_dir=trust_store_dir,
        run_root=run_root,
        packet_root=packet_root,
        protected_roots=protected_roots,
        owner_root_preauthorization_bytes=owner_root_preauthorization_bytes,
        session_id=session_id,
        run_id=run_id,
        nonce_commitment_sha256=nonce_commitment_sha256,
        expected_packet_root_final_path=expected_packet_root_final_path,
        expected_packet_root_volume_serial=expected_packet_root_volume_serial,
        expected_packet_root_file_id=expected_packet_root_file_id,
        expected_parser_provenance=expected_parser_provenance,
    )
    try:
        receipt = _thaw_state_json(state.public_receipt)
        if not isinstance(receipt, dict):
            raise P0ExternalOwnerTrustExecutionError(
                "external trust public receipt must be an object"
            )
        return receipt
    finally:
        _discard_external_owner_trust_state(state)


__all__ = [
    "EXECUTION_RECEIPT_SCHEMA",
    "NONCE_COMMITMENT_DOMAIN",
    "NONCE_LEDGER_DIRECTORY",
    "NONCE_RECORD_SCHEMA",
    "P0ExternalOwnerTrustExecutionError",
    "REVOCATION_SNAPSHOT_FILENAME",
    "REVOCATION_SNAPSHOT_SCHEMA",
    "TRUST_ANCHOR_FILENAME",
    "TRUST_ANCHOR_SCHEMA",
    "canonical_bytes",
    "canonical_sha256",
    "execute_external_owner_trust",
    "json_file_bytes",
    "nonce_commitment_sha256",
]
