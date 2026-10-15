"""Presented external-owner ECDSA verification component for actual-P0.

This module verifies one exact canonical owner-root preauthorization byte string
with a separately presented ECDSA P-256 public-key pin artifact.  Verification
uses the Windows CNG primitive provider directly and the public API has no
private-key, signer, callback, or key-generation parameter.

The pin artifact is still supplied by the caller.  Its self-hash and fingerprint
therefore prove only internal consistency, not independent provisioning or
external owner authority.  Trusted time, signed revocation state, durable replay
protection, root authority, P0 exit, and production remain explicitly false.
"""

from __future__ import annotations

import base64
import binascii
import ctypes
from dataclasses import dataclass
import hashlib
import hmac
import json
import os
import re
import secrets
import threading
from types import MappingProxyType
from typing import Any, Mapping

from . import p0_windows_cng_ecdsa_p256 as cng_p256
import weakref

from . import p0_actual_owner_root_preauthorization as preauth


PUBLIC_KEY_PIN_SCHEMA = "p0_external_owner_public_key_pin_v1"
SIGNATURE_ENVELOPE_SCHEMA = "p0_external_owner_asymmetric_signature_envelope_v1"
VALIDATION_RECEIPT_SCHEMA = "p0_external_owner_asymmetric_signature_receipt_v1"
ALGORITHM = "ECDSA_P256_SHA256_CNG_V1"
CURVE = "NIST_P256"
CNG_PROVIDER = "Microsoft Primitive Provider"
COORDINATE_ENCODING = "P256_XY32_BIG_ENDIAN_BASE64_V1"
FINGERPRINT_ENCODING = "RFC5480_DER_SPKI_SHA256_V1"
SIGNATURE_DOMAIN = (
    "llm-novel-dc-community-parser/p0-external-owner-preauthorization-signature/v1"
)
SIGNATURE_PURPOSE = "P0_ACTUAL_SHADOW_PREAUTHORIZATION"
PRESENTED_PIN_ORIGIN = "PRESENTED_EXTERNAL_OWNER_PIN_CANDIDATE"
PRESENTED_SIGNATURE_ORIGIN = "PRESENTED_EXTERNAL_OWNER_SIGNATURE_CANDIDATE"
NONCE_COMMITMENT_DOMAIN = "p0-actual-owner-root-preauthorization-nonce-v1"
GATE_STATUS = "PASS_ASYMMETRIC_SIGNATURE_MATH_COMPONENT_ONLY_EXTERNAL_PROVISIONING_NO_GO"

_OWNER_STATE_CONTEXT_FIELDS = (
    "schema_version",
    "public_key_pin_bytes_sha256",
    "public_key_pin_artifact_sha256",
    "signature_envelope_bytes_sha256",
    "signature_envelope_artifact_sha256",
    "preauthorization_bytes_sha256",
    "preauthorization_artifact_sha256",
    "preauthorization_structure_receipt_sha256",
    "signature_input_sha256",
    "key_id",
    "key_epoch",
    "trust_domain",
    "project_id",
    "environment",
    "purpose",
    "session_id",
    "run_id",
    "preauthorization_id",
    "parser_run_id",
    "nonce_commitment_sha256",
    "launch_sha256",
    "owner_authorization_sha256",
    "packet_root_projection_sha256",
    "protected_root_projection_sha256",
    "category_root_map_sha256",
    "expected_provenance_sha256",
    "watch_requirements_sha256",
    "write_deny_requirements_sha256",
    "public_key_fingerprint_sha256",
    "owner_principal_sha256",
    "owner_anchor_sha256",
)
_OWNER_STATE_ID_FIELDS = frozenset(
    {
        "key_id",
        "trust_domain",
        "project_id",
        "environment",
        "purpose",
        "session_id",
        "run_id",
        "preauthorization_id",
        "parser_run_id",
    }
)
_OWNER_STATE_SHA_FIELDS = frozenset(_OWNER_STATE_CONTEXT_FIELDS).difference(
    _OWNER_STATE_ID_FIELDS,
    {"schema_version", "key_epoch"},
)

_MAX_JSON_BYTES = 1024 * 1024
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")
_P256_ORDER = int(
    "ffffffff00000000ffffffffffffffffbce6faada7179e84f3b9cac2fc632551",
    16,
)
_P256_SPKI_PREFIX = bytes.fromhex(
    "3059301306072a8648ce3d020106082a8648ce3d03010703420004"
)


class P0ExternalOwnerAsymmetricSignatureError(ValueError):
    """The presented asymmetric evidence failed its component contract."""


@dataclass(frozen=True, eq=False)
class _ExternalOwnerAsymmetricSignatureState:
    """Exact module-issued object retained only for an in-process supervisor."""

    public_receipt: Mapping[str, Any]
    _execution_seal: bytes


@dataclass(frozen=True)
class _ConsumedExternalOwnerAsymmetricSignatureState:
    """Validated raw bundle released only after exact-once state consumption."""

    public_key_pin_bytes: bytes
    signature_envelope_bytes: bytes
    owner_root_preauthorization_bytes: bytes
    public_receipt: Mapping[str, Any]


@dataclass
class _IssuedOwnerStateSecret:
    execution_seal: bytearray
    public_key_pin_bytes: bytearray
    signature_envelope_bytes: bytearray
    owner_root_preauthorization_bytes: bytearray
    receipt_sha256: str
    context_projection_sha256: str
    issuer_pid: int


@dataclass(frozen=True)
class _IssuedOwnerStateRecord:
    secret: _IssuedOwnerStateSecret
    state_ref: weakref.ReferenceType[_ExternalOwnerAsymmetricSignatureState]
    finalizer: weakref.finalize


_ISSUED_OWNER_STATES: dict[int, _IssuedOwnerStateRecord] = {}
_ISSUED_OWNER_STATES_LOCK = threading.Lock()


def _freeze_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType(
            {key: _freeze_json(item) for key, item in value.items()}
        )
    if isinstance(value, list):
        return tuple(_freeze_json(item) for item in value)
    return value


def _thaw_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return value


def _burn_owner_state_secret(secret: _IssuedOwnerStateSecret) -> None:
    for buffer in (
        secret.execution_seal,
        secret.public_key_pin_bytes,
        secret.signature_envelope_bytes,
        secret.owner_root_preauthorization_bytes,
    ):
        for index in range(len(buffer)):
            buffer[index] = 0


def _finalize_external_owner_asymmetric_signature_state(
    state_id: int,
    secret: _IssuedOwnerStateSecret,
    registry: dict[int, _IssuedOwnerStateRecord],
    registry_lock: threading.Lock,
) -> None:
    with registry_lock:
        record = registry.get(state_id)
        if record is None or record.secret is not secret:
            return
        registry.pop(state_id, None)
    _burn_owner_state_secret(secret)


def _owner_state_context_projection(
    receipt: Mapping[str, Any],
) -> dict[str, Any]:
    try:
        return {field: receipt[field] for field in _OWNER_STATE_CONTEXT_FIELDS}
    except (KeyError, TypeError) as exc:
        raise P0ExternalOwnerAsymmetricSignatureError(
            "owner state receipt is missing fixed context"
        ) from exc


def _validate_expected_owner_state_context(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise P0ExternalOwnerAsymmetricSignatureError(
            "expected owner state context must be a mapping"
        )
    if set(value) != set(_OWNER_STATE_CONTEXT_FIELDS):
        raise P0ExternalOwnerAsymmetricSignatureError(
            "expected owner state context must have the exact fixed fields"
        )
    row = dict(value)
    if row["schema_version"] != VALIDATION_RECEIPT_SCHEMA:
        raise P0ExternalOwnerAsymmetricSignatureError(
            "expected owner state receipt schema mismatch"
        )
    if type(row["key_epoch"]) is not int or row["key_epoch"] < 1:
        raise P0ExternalOwnerAsymmetricSignatureError(
            "expected owner state key_epoch is invalid"
        )
    for field in _OWNER_STATE_ID_FIELDS:
        _identifier(row[field], f"expected owner state {field}")
    for field in _OWNER_STATE_SHA_FIELDS:
        _sha(row[field], f"expected owner state {field}")
    return row


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


def _reject_duplicate_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise P0ExternalOwnerAsymmetricSignatureError(
                f"duplicate JSON key is forbidden: {key}"
            )
        result[key] = value
    return result


def _reject_nonfinite(token: str) -> None:
    raise P0ExternalOwnerAsymmetricSignatureError(
        f"non-finite JSON constant is forbidden: {token}"
    )


def _parse_canonical_json(raw: bytes, label: str) -> dict[str, Any]:
    if type(raw) is not bytes:
        raise P0ExternalOwnerAsymmetricSignatureError(
            f"{label} must be exact bytes"
        )
    if (
        not raw
        or len(raw) > _MAX_JSON_BYTES
        or raw.startswith(b"\xef\xbb\xbf")
        or b"\r" in raw
        or not raw.endswith(b"\n")
    ):
        raise P0ExternalOwnerAsymmetricSignatureError(
            f"{label} framing is invalid"
        )
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_object,
            parse_constant=_reject_nonfinite,
        )
    except P0ExternalOwnerAsymmetricSignatureError:
        raise
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise P0ExternalOwnerAsymmetricSignatureError(
            f"{label} must be strict UTF-8 JSON"
        ) from exc
    if not isinstance(value, dict) or raw != json_file_bytes(value):
        raise P0ExternalOwnerAsymmetricSignatureError(
            f"{label} must be one canonical JSON object plus one final LF"
        )
    return value


def _strict(value: Any, fields: frozenset[str], label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise P0ExternalOwnerAsymmetricSignatureError(
            f"{label} must be an object"
        )
    keys = frozenset(value)
    if keys != fields:
        raise P0ExternalOwnerAsymmetricSignatureError(
            f"{label} fields mismatch: missing={sorted(fields - keys)}, "
            f"extra={sorted(keys - fields)}"
        )
    return dict(value)


def _sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise P0ExternalOwnerAsymmetricSignatureError(
            f"{label} must be lowercase SHA-256"
        )
    return value


def _identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or _SAFE_ID.fullmatch(value) is None:
        raise P0ExternalOwnerAsymmetricSignatureError(f"{label} is invalid")
    return value


def _decode_base64(value: Any, *, length: int, label: str) -> bytes:
    if (
        not isinstance(value, str)
        or not value
        or any(character.isspace() for character in value)
    ):
        raise P0ExternalOwnerAsymmetricSignatureError(
            f"{label} must be canonical base64"
        )
    try:
        decoded = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise P0ExternalOwnerAsymmetricSignatureError(
            f"{label} must be canonical base64"
        ) from exc
    if len(decoded) != length or base64.b64encode(decoded).decode("ascii") != value:
        raise P0ExternalOwnerAsymmetricSignatureError(
            f"{label} must encode exactly {length} bytes"
        )
    return decoded


def public_key_fingerprint_sha256(
    *, public_key_x_base64: str, public_key_y_base64: str
) -> str:
    x = _decode_base64(
        public_key_x_base64, length=32, label="public_key_x_base64"
    )
    y = _decode_base64(
        public_key_y_base64, length=32, label="public_key_y_base64"
    )
    # RFC 5480 id-ecPublicKey + prime256v1, uncompressed SEC1 point.  Pinning
    # the canonical DER SubjectPublicKeyInfo avoids provider-specific blob
    # fingerprints while CNG still consumes the exact same X/Y coordinates.
    return hashlib.sha256(_P256_SPKI_PREFIX + x + y).hexdigest()


_PIN_FIELDS = frozenset(
    {
        "schema_version",
        "record_origin",
        "trust_domain",
        "project_id",
        "environment",
        "purpose",
        "key_id",
        "key_epoch",
        "algorithm",
        "curve",
        "coordinate_encoding",
        "fingerprint_encoding",
        "public_key_x_base64",
        "public_key_y_base64",
        "public_key_fingerprint_sha256",
        "owner_principal_sha256",
        "owner_anchor_sha256",
        "allowed_signature_domains",
        "artifact_sha256",
    }
)
_ENVELOPE_FIELDS = frozenset(
    {
        "schema_version",
        "record_origin",
        "domain",
        "trust_domain",
        "project_id",
        "environment",
        "purpose",
        "session_id",
        "run_id",
        "preauthorization_id",
        "parser_run_id",
        "nonce_commitment_sha256",
        "key_id",
        "key_epoch",
        "algorithm",
        "public_key_fingerprint_sha256",
        "owner_principal_sha256",
        "owner_anchor_sha256",
        "preauthorization_schema",
        "preauthorization_bytes_sha256",
        "preauthorization_artifact_sha256",
        "signature_rs_base64",
        "artifact_sha256",
    }
)


def _validate_self_hash(row: Mapping[str, Any], label: str) -> str:
    stored = _sha(row.get("artifact_sha256"), f"{label}.artifact_sha256")
    material = {key: value for key, value in row.items() if key != "artifact_sha256"}
    if stored != canonical_sha256(material):
        raise P0ExternalOwnerAsymmetricSignatureError(
            f"{label} self-hash mismatch"
        )
    return stored


def _validate_pin(value: Any) -> tuple[dict[str, Any], bytes, bytes]:
    row = _strict(value, _PIN_FIELDS, "public-key pin")
    if (
        row["schema_version"] != PUBLIC_KEY_PIN_SCHEMA
        or row["record_origin"] != PRESENTED_PIN_ORIGIN
        or row["algorithm"] != ALGORITHM
        or row["curve"] != CURVE
        or row["coordinate_encoding"] != COORDINATE_ENCODING
        or row["fingerprint_encoding"] != FINGERPRINT_ENCODING
        or row["purpose"] != SIGNATURE_PURPOSE
    ):
        raise P0ExternalOwnerAsymmetricSignatureError(
            "public-key pin schema/algorithm/curve mismatch"
        )
    for field in ("trust_domain", "project_id", "environment", "key_id"):
        _identifier(row[field], f"public-key pin.{field}")
    if (
        isinstance(row["key_epoch"], bool)
        or not isinstance(row["key_epoch"], int)
        or row["key_epoch"] < 1
    ):
        raise P0ExternalOwnerAsymmetricSignatureError(
            "public-key pin.key_epoch must be a positive integer"
        )
    if row["allowed_signature_domains"] != [SIGNATURE_DOMAIN]:
        raise P0ExternalOwnerAsymmetricSignatureError(
            "public-key pin allowed signature domains mismatch"
        )
    x = _decode_base64(
        row["public_key_x_base64"],
        length=32,
        label="public-key pin.public_key_x_base64",
    )
    y = _decode_base64(
        row["public_key_y_base64"],
        length=32,
        label="public-key pin.public_key_y_base64",
    )
    expected_fingerprint = public_key_fingerprint_sha256(
        public_key_x_base64=row["public_key_x_base64"],
        public_key_y_base64=row["public_key_y_base64"],
    )
    if _sha(
        row["public_key_fingerprint_sha256"],
        "public-key pin.public_key_fingerprint_sha256",
    ) != expected_fingerprint:
        raise P0ExternalOwnerAsymmetricSignatureError(
            "public-key pin fingerprint mismatch"
        )
    _sha(row["owner_principal_sha256"], "public-key pin.owner_principal_sha256")
    _sha(row["owner_anchor_sha256"], "public-key pin.owner_anchor_sha256")
    _validate_self_hash(row, "public-key pin")
    return row, x, y


def external_owner_signature_material(envelope: Mapping[str, Any]) -> dict[str, Any]:
    """Return the exact domain-separated material an external signer signs."""

    row = _strict(envelope, _ENVELOPE_FIELDS, "signature envelope")
    return {
        key: value
        for key, value in row.items()
        if key not in {"signature_rs_base64", "artifact_sha256"}
    }


def _validate_envelope(value: Any) -> tuple[dict[str, Any], bytes, bytes]:
    row = _strict(value, _ENVELOPE_FIELDS, "signature envelope")
    if (
        row["schema_version"] != SIGNATURE_ENVELOPE_SCHEMA
        or row["record_origin"] != PRESENTED_SIGNATURE_ORIGIN
        or row["domain"] != SIGNATURE_DOMAIN
        or row["algorithm"] != ALGORITHM
        or row["purpose"] != SIGNATURE_PURPOSE
        or row["preauthorization_schema"] != preauth.PREAUTHORIZATION_SCHEMA
    ):
        raise P0ExternalOwnerAsymmetricSignatureError(
            "signature envelope schema/domain/algorithm mismatch"
        )
    for field in (
        "trust_domain",
        "project_id",
        "environment",
        "session_id",
        "run_id",
        "preauthorization_id",
        "parser_run_id",
        "key_id",
    ):
        _identifier(row[field], f"signature envelope.{field}")
    if (
        isinstance(row["key_epoch"], bool)
        or not isinstance(row["key_epoch"], int)
        or row["key_epoch"] < 1
    ):
        raise P0ExternalOwnerAsymmetricSignatureError(
            "signature envelope.key_epoch must be a positive integer"
        )
    for field in (
        "public_key_fingerprint_sha256",
        "owner_principal_sha256",
        "owner_anchor_sha256",
        "preauthorization_bytes_sha256",
        "preauthorization_artifact_sha256",
        "nonce_commitment_sha256",
    ):
        _sha(row[field], f"signature envelope.{field}")
    signature = _decode_base64(
        row["signature_rs_base64"],
        length=64,
        label="signature envelope.signature_rs_base64",
    )
    r = int.from_bytes(signature[:32], "big")
    s = int.from_bytes(signature[32:], "big")
    if not 0 < r < _P256_ORDER or not 0 < s <= _P256_ORDER // 2:
        raise P0ExternalOwnerAsymmetricSignatureError(
            "signature must use canonical nonzero low-S P-256 r||s"
        )
    _validate_self_hash(row, "signature envelope")
    material = external_owner_signature_material(row)
    return row, signature, canonical_bytes(material)


def _cng_verify_p256_sha256(
    *, public_key_x: bytes, public_key_y: bytes, digest: bytes, signature: bytes
) -> None:
    try:
        cng_p256.verify_p256_sha256(
            public_key_x=public_key_x,
            public_key_y=public_key_y,
            digest=digest,
            signature=signature,
        )
    except cng_p256.P0WindowsCngEcdsaP256Error as exc:
        raise P0ExternalOwnerAsymmetricSignatureError(str(exc)) from exc


def _validate_presented_external_owner_asymmetric_signature_core(
    *,
    public_key_pin_bytes: bytes,
    signature_envelope_bytes: bytes,
    owner_root_preauthorization_bytes: bytes,
) -> dict[str, Any]:
    """Verify exact preauthorization bytes under a separately presented pin."""

    pin_value = _parse_canonical_json(public_key_pin_bytes, "public-key pin")
    envelope_value = _parse_canonical_json(
        signature_envelope_bytes, "signature envelope"
    )
    preauthorization = _parse_canonical_json(
        owner_root_preauthorization_bytes, "owner root preauthorization"
    )
    pin_raw_sha = hashlib.sha256(public_key_pin_bytes).hexdigest()
    envelope_raw_sha = hashlib.sha256(signature_envelope_bytes).hexdigest()
    preauthorization_raw_sha = hashlib.sha256(
        owner_root_preauthorization_bytes
    ).hexdigest()
    pin, x, y = _validate_pin(pin_value)
    envelope, signature, signature_input = _validate_envelope(envelope_value)
    try:
        preauth_receipt = preauth.validate_owner_root_preauthorization(
            preauthorization,
            expected_origin=preauth.ACTUAL_ORIGIN,
            key=None,
            expected_owner_anchor_sha256=pin["owner_anchor_sha256"],
        )
    except preauth.P0ActualOwnerRootPreauthorizationError as exc:
        raise P0ExternalOwnerAsymmetricSignatureError(
            "owner root preauthorization structure is invalid"
        ) from exc

    bindings = (
        ("key_id", pin["key_id"], envelope["key_id"]),
        ("key_epoch", pin["key_epoch"], envelope["key_epoch"]),
        ("trust_domain", pin["trust_domain"], envelope["trust_domain"]),
        ("project_id", pin["project_id"], envelope["project_id"]),
        ("environment", pin["environment"], envelope["environment"]),
        ("purpose", pin["purpose"], envelope["purpose"]),
        (
            "public_key_fingerprint_sha256",
            pin["public_key_fingerprint_sha256"],
            envelope["public_key_fingerprint_sha256"],
        ),
        (
            "owner_principal_sha256",
            pin["owner_principal_sha256"],
            envelope["owner_principal_sha256"],
        ),
        (
            "owner_anchor_sha256",
            pin["owner_anchor_sha256"],
            envelope["owner_anchor_sha256"],
        ),
        (
            "preauthorization owner principal",
            pin["owner_principal_sha256"],
            preauthorization.get("owner_principal_sha256"),
        ),
        (
            "preauthorization project",
            pin["project_id"],
            preauthorization.get("project_id"),
        ),
        (
            "preauthorization run",
            envelope["run_id"],
            preauthorization.get("run_id"),
        ),
        (
            "preauthorization id",
            envelope["preauthorization_id"],
            preauthorization.get("preauthorization_id"),
        ),
        (
            "preauthorization parser run",
            envelope["parser_run_id"],
            preauthorization.get("parser_run_id"),
        ),
        (
            "preauthorization nonce commitment",
            envelope["nonce_commitment_sha256"],
            canonical_sha256(
                {
                    "domain": NONCE_COMMITMENT_DOMAIN,
                    "nonce": preauthorization.get("nonce"),
                }
            ),
        ),
        (
            "preauthorization owner anchor",
            pin["owner_anchor_sha256"],
            preauthorization.get("owner_anchor_sha256"),
        ),
        (
            "preauthorization bytes",
            preauthorization_raw_sha,
            envelope["preauthorization_bytes_sha256"],
        ),
        (
            "preauthorization artifact",
            preauthorization.get("artifact_sha256"),
            envelope["preauthorization_artifact_sha256"],
        ),
    )
    for label, expected, observed in bindings:
        if expected != observed:
            raise P0ExternalOwnerAsymmetricSignatureError(
                f"asymmetric evidence binding mismatch: {label}"
            )

    signature_input_sha = hashlib.sha256(signature_input).digest()
    _cng_verify_p256_sha256(
        public_key_x=x,
        public_key_y=y,
        digest=signature_input_sha,
        signature=signature,
    )

    material = {
        "schema_version": VALIDATION_RECEIPT_SCHEMA,
        "public_key_pin_bytes_sha256": pin_raw_sha,
        "public_key_pin_artifact_sha256": pin["artifact_sha256"],
        "signature_envelope_bytes_sha256": envelope_raw_sha,
        "signature_envelope_artifact_sha256": envelope["artifact_sha256"],
        "preauthorization_bytes_sha256": preauthorization_raw_sha,
        "preauthorization_artifact_sha256": preauthorization["artifact_sha256"],
        "preauthorization_structure_receipt_sha256": preauth_receipt[
            "receipt_sha256"
        ],
        "signature_input_sha256": signature_input_sha.hex(),
        "key_id": pin["key_id"],
        "key_epoch": pin["key_epoch"],
        "trust_domain": pin["trust_domain"],
        "project_id": pin["project_id"],
        "environment": pin["environment"],
        "purpose": pin["purpose"],
        "session_id": envelope["session_id"],
        "run_id": envelope["run_id"],
        "preauthorization_id": envelope["preauthorization_id"],
        "parser_run_id": envelope["parser_run_id"],
        "nonce_commitment_sha256": envelope["nonce_commitment_sha256"],
        "launch_sha256": preauthorization["launch_sha256"],
        "owner_authorization_sha256": preauthorization[
            "owner_authorization_sha256"
        ],
        "packet_root_projection_sha256": preauth_receipt[
            "packet_root_projection_sha256"
        ],
        "protected_root_projection_sha256": preauth_receipt[
            "protected_root_projection_sha256"
        ],
        "category_root_map_sha256": preauth_receipt["category_root_map_sha256"],
        "expected_provenance_sha256": preauth_receipt[
            "expected_provenance_sha256"
        ],
        "watch_requirements_sha256": preauth_receipt[
            "watch_requirements_sha256"
        ],
        "write_deny_requirements_sha256": preauth_receipt[
            "write_deny_requirements_sha256"
        ],
        "algorithm": ALGORITHM,
        "curve": CURVE,
        "cng_provider_name": CNG_PROVIDER,
        "public_key_fingerprint_sha256": pin["public_key_fingerprint_sha256"],
        "owner_principal_sha256": pin["owner_principal_sha256"],
        "owner_anchor_sha256": pin["owner_anchor_sha256"],
        "presented_public_key_pin_verified": True,
        "public_key_fingerprint_recomputed_verified": True,
        "cng_public_key_import_verified": True,
        "canonical_low_s_signature_verified": True,
        "asymmetric_signature_math_verified": True,
        "exact_preauthorization_bytes_bound_verified": True,
        "public_api_private_key_parameter_absent": True,
        "fresh_execution_result_observed": True,
        "serialized_receipt_authoritative": False,
        "execution_trace_transferable_by_receipt": False,
        "external_public_key_pin_provisioning_verified": False,
        "independent_readonly_public_key_pin_verified": False,
        "public_key_pin_rollback_protection_verified": False,
        "key_epoch_monotonicity_verified": False,
        "independent_context_policy_verified": False,
        "signature_freshness_verified": False,
        "external_owner_signing_key_verified": False,
        "private_key_outside_verifier_verified": False,
        "trusted_cng_provider_provenance_verified": False,
        "trusted_time_verified": False,
        "revocation_current_verified": False,
        "revocation_rollback_protection_verified": False,
        "durable_cross_process_nonce_verified": False,
        "power_loss_durable_replay_verified": False,
        "single_use_replay_consumed": False,
        "external_trust_store_verified": False,
        "external_owner_trust_verified": False,
        "external_root_identity_pin_verified": False,
        "filesystem_handle_trust_verified": False,
        "runtime_noninterference_verified": False,
        "os_write_deny_verified": False,
        "parser_runtime_execution_verified": False,
        "actual_semantic_evidence_verified": False,
        "owner_authority_verified": False,
        "actual_authority_granted": False,
        "p0_phase_exit": False,
        "production_approval": False,
        "full_scan_approval": False,
        "action_applied": False,
        "protected_pipeline_state_mutated": False,
        "credited_actual_source_claim_count": 0,
        "credited_actual_a_context_review_count": 0,
        "gate_status": GATE_STATUS,
    }
    return {**material, "receipt_sha256": canonical_sha256(material)}


def _owner_state_raw_triplet_binding_sha256(
    *,
    public_key_pin_bytes: bytes,
    signature_envelope_bytes: bytes,
    owner_root_preauthorization_bytes: bytes,
    receipt_sha256: str,
) -> str:
    return canonical_sha256(
        {
            "domain": (
                "llm-novel-dc-community-parser/"
                "p0-external-owner-asymmetric-owner-state/v1"
            ),
            "public_key_pin": {
                "length": len(public_key_pin_bytes),
                "sha256": hashlib.sha256(public_key_pin_bytes).hexdigest(),
            },
            "signature_envelope": {
                "length": len(signature_envelope_bytes),
                "sha256": hashlib.sha256(signature_envelope_bytes).hexdigest(),
            },
            "owner_root_preauthorization": {
                "length": len(owner_root_preauthorization_bytes),
                "sha256": hashlib.sha256(
                    owner_root_preauthorization_bytes
                ).hexdigest(),
            },
            "receipt_sha256": receipt_sha256,
        }
    )


def _validate_presented_external_owner_asymmetric_signature_state(
    *,
    public_key_pin_bytes: bytes,
    signature_envelope_bytes: bytes,
    owner_root_preauthorization_bytes: bytes,
) -> _ExternalOwnerAsymmetricSignatureState:
    """Freshly validate exact raw inputs, then mint one private object identity."""

    receipt = _validate_presented_external_owner_asymmetric_signature_core(
        public_key_pin_bytes=public_key_pin_bytes,
        signature_envelope_bytes=signature_envelope_bytes,
        owner_root_preauthorization_bytes=owner_root_preauthorization_bytes,
    )
    execution_seal = secrets.token_bytes(32)
    state = _ExternalOwnerAsymmetricSignatureState(
        public_receipt=_freeze_json(receipt),
        _execution_seal=execution_seal,
    )
    secret = _IssuedOwnerStateSecret(
        execution_seal=bytearray(execution_seal),
        public_key_pin_bytes=bytearray(public_key_pin_bytes),
        signature_envelope_bytes=bytearray(signature_envelope_bytes),
        owner_root_preauthorization_bytes=bytearray(
            owner_root_preauthorization_bytes
        ),
        receipt_sha256=str(receipt["receipt_sha256"]),
        context_projection_sha256=canonical_sha256(
            _owner_state_context_projection(receipt)
        ),
        issuer_pid=os.getpid(),
    )
    state_id = id(state)
    finalizer = weakref.finalize(
        state,
        _finalize_external_owner_asymmetric_signature_state,
        state_id,
        secret,
        _ISSUED_OWNER_STATES,
        _ISSUED_OWNER_STATES_LOCK,
    )
    finalizer.atexit = False
    record = _IssuedOwnerStateRecord(
        secret=secret,
        state_ref=weakref.ref(state),
        finalizer=finalizer,
    )
    with _ISSUED_OWNER_STATES_LOCK:
        if state_id in _ISSUED_OWNER_STATES:  # pragma: no cover - live id reuse
            finalizer.detach()
            _burn_owner_state_secret(secret)
            raise P0ExternalOwnerAsymmetricSignatureError(
                "owner state object identity collision"
            )
        _ISSUED_OWNER_STATES[state_id] = record
    return state


def _discard_external_owner_asymmetric_signature_state(state: Any) -> None:
    """Idempotently burn one exact object identity without accepting a clone."""

    if type(state) is not _ExternalOwnerAsymmetricSignatureState:
        return
    with _ISSUED_OWNER_STATES_LOCK:
        state_id = id(state)
        record = _ISSUED_OWNER_STATES.get(state_id)
        if record is None or record.state_ref() is not state:
            record = None
        else:
            _ISSUED_OWNER_STATES.pop(state_id, None)
    if record is not None:
        record.finalizer.detach()
        _burn_owner_state_secret(record.secret)


def _consume_external_owner_asymmetric_signature_state(
    state: Any,
    *,
    public_key_pin_bytes: bytes,
    signature_envelope_bytes: bytes,
    owner_root_preauthorization_bytes: bytes,
    expected_context: Mapping[str, Any],
) -> _ConsumedExternalOwnerAsymmetricSignatureState:
    """Atomically consume and cross-bind one freshly validated private state.

    This is a process-local handoff for one validation result.  It does not
    make the signature artifact replay-proof and does not establish external
    pin provisioning or owner authority.
    """

    if type(state) is not _ExternalOwnerAsymmetricSignatureState:
        raise P0ExternalOwnerAsymmetricSignatureError(
            "owner state must be the exact module-issued object"
        )
    with _ISSUED_OWNER_STATES_LOCK:
        state_id = id(state)
        record = _ISSUED_OWNER_STATES.get(state_id)
        if record is None or record.state_ref() is not state:
            record = None
        else:
            _ISSUED_OWNER_STATES.pop(state_id, None)
    if record is None:
        raise P0ExternalOwnerAsymmetricSignatureError(
            "owner state was not issued, was copied, or was already consumed"
        )
    record.finalizer.detach()
    secret = record.secret
    try:
        if (
            type(public_key_pin_bytes) is not bytes
            or type(signature_envelope_bytes) is not bytes
            or type(owner_root_preauthorization_bytes) is not bytes
        ):
            raise P0ExternalOwnerAsymmetricSignatureError(
                "owner state raw triplet must be exact bytes"
            )
        expected = _validate_expected_owner_state_context(expected_context)
        receipt_value = _thaw_json(state.public_receipt)
        if not isinstance(receipt_value, dict):
            raise P0ExternalOwnerAsymmetricSignatureError(
                "owner state receipt must be an object"
            )
        receipt = dict(receipt_value)
        material = dict(receipt)
        declared_receipt_sha = _sha(
            material.pop("receipt_sha256", None),
            "owner state receipt.receipt_sha256",
        )
        context_projection = _owner_state_context_projection(receipt)
        stored_pin = bytes(secret.public_key_pin_bytes)
        stored_envelope = bytes(secret.signature_envelope_bytes)
        stored_preauthorization = bytes(
            secret.owner_root_preauthorization_bytes
        )
        stored_binding = _owner_state_raw_triplet_binding_sha256(
            public_key_pin_bytes=stored_pin,
            signature_envelope_bytes=stored_envelope,
            owner_root_preauthorization_bytes=stored_preauthorization,
            receipt_sha256=secret.receipt_sha256,
        )
        presented_binding = _owner_state_raw_triplet_binding_sha256(
            public_key_pin_bytes=public_key_pin_bytes,
            signature_envelope_bytes=signature_envelope_bytes,
            owner_root_preauthorization_bytes=owner_root_preauthorization_bytes,
            receipt_sha256=declared_receipt_sha,
        )
        state_seal_ok = bool(
            type(state._execution_seal) is bytes
            and len(state._execution_seal) == 32
            and hmac.compare_digest(
                state._execution_seal, bytes(secret.execution_seal)
            )
        )
        checks = (
            secret.issuer_pid == os.getpid(),
            state_seal_ok,
            hmac.compare_digest(declared_receipt_sha, canonical_sha256(material)),
            hmac.compare_digest(declared_receipt_sha, secret.receipt_sha256),
            hmac.compare_digest(
                canonical_sha256(context_projection),
                secret.context_projection_sha256,
            ),
            context_projection == expected,
            hmac.compare_digest(stored_binding, presented_binding),
            hmac.compare_digest(stored_pin, public_key_pin_bytes),
            hmac.compare_digest(stored_envelope, signature_envelope_bytes),
            hmac.compare_digest(
                stored_preauthorization, owner_root_preauthorization_bytes
            ),
            receipt.get("public_key_pin_bytes_sha256")
            == hashlib.sha256(stored_pin).hexdigest(),
            receipt.get("signature_envelope_bytes_sha256")
            == hashlib.sha256(stored_envelope).hexdigest(),
            receipt.get("preauthorization_bytes_sha256")
            == hashlib.sha256(stored_preauthorization).hexdigest(),
        )
        if not all(checks):
            raise P0ExternalOwnerAsymmetricSignatureError(
                "owner state seal/raw/context binding mismatch"
            )
        return _ConsumedExternalOwnerAsymmetricSignatureState(
            public_key_pin_bytes=stored_pin,
            signature_envelope_bytes=stored_envelope,
            owner_root_preauthorization_bytes=stored_preauthorization,
            public_receipt=state.public_receipt,
        )
    except P0ExternalOwnerAsymmetricSignatureError:
        raise
    except Exception as exc:
        raise P0ExternalOwnerAsymmetricSignatureError(
            "owner state seal/raw/context binding mismatch"
        ) from exc
    finally:
        _burn_owner_state_secret(secret)


def validate_presented_external_owner_asymmetric_signature(
    *,
    public_key_pin_bytes: bytes,
    signature_envelope_bytes: bytes,
    owner_root_preauthorization_bytes: bytes,
) -> dict[str, Any]:
    """Return a diagnostic receipt without exposing a transferable state."""

    return _validate_presented_external_owner_asymmetric_signature_core(
        public_key_pin_bytes=public_key_pin_bytes,
        signature_envelope_bytes=signature_envelope_bytes,
        owner_root_preauthorization_bytes=owner_root_preauthorization_bytes,
    )


__all__ = [
    "ALGORITHM",
    "COORDINATE_ENCODING",
    "CNG_PROVIDER",
    "CURVE",
    "FINGERPRINT_ENCODING",
    "GATE_STATUS",
    "NONCE_COMMITMENT_DOMAIN",
    "P0ExternalOwnerAsymmetricSignatureError",
    "PRESENTED_PIN_ORIGIN",
    "PRESENTED_SIGNATURE_ORIGIN",
    "PUBLIC_KEY_PIN_SCHEMA",
    "SIGNATURE_DOMAIN",
    "SIGNATURE_PURPOSE",
    "SIGNATURE_ENVELOPE_SCHEMA",
    "VALIDATION_RECEIPT_SCHEMA",
    "canonical_bytes",
    "canonical_sha256",
    "external_owner_signature_material",
    "json_file_bytes",
    "public_key_fingerprint_sha256",
    "validate_presented_external_owner_asymmetric_signature",
]
