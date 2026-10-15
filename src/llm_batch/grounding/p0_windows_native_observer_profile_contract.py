"""Strict presented contract for a future Windows native observer profile.

This module validates an exact owner-policy-v3 nested profile and one
presented request/ticket/native-receipt/signature transcript.  The two P-256
signatures are checked with Windows CNG and every byte-bearing artifact uses
canonical JSON plus one final LF.

The profile is still caller-presented here.  No service is contacted, no
external owner state is discovered, and no nonce is durably consumed.  A
successful receipt therefore proves component structure and signature
mathematics only.  It never grants owner authority, actual-P0 credit,
production approval, or full-scan approval.
"""

from __future__ import annotations

import base64
import binascii
from datetime import datetime, timezone
import hashlib
import hmac
import json
import re
import uuid
from typing import Any, Mapping

from . import p0_windows_cng_ecdsa_p256 as cng_p256
from . import p0_windows_owner_deployment_projection as deployment


PROFILE_SCHEMA = "p0_windows_native_observer_profile_v1"
PROFILE_ORIGIN = "EXTERNAL_OWNER_POLICY_NATIVE_OBSERVER_PROFILE"
PROFILE_DOMAIN = "llm_novel_dc/p0/windows-native-observer-profile/v1"
REQUEST_SCHEMA = "p0_windows_native_observer_request_v1"
REQUEST_ORIGIN = "ZERO_INPUT_NATIVE_OBSERVER_CLIENT_REQUEST"
REQUEST_DOMAIN = "llm_novel_dc/p0/windows-native-observer-request/v1"
OWNER_STATE_TICKET_SCHEMA = "p0_windows_owner_state_ticket_v1"
OWNER_STATE_TICKET_ORIGIN = "EXTERNAL_OWNER_STATE_AUTHORITY_TICKET"
OWNER_STATE_TICKET_DOMAIN = "llm_novel_dc/p0/windows-owner-state-ticket/v1"
RECEIPT_BODY_SCHEMA = "p0_windows_native_observer_receipt_body_v1"
RECEIPT_BODY_ORIGIN = "NATIVE_FIXED_PE_SERVICE_OBSERVATION"
RECEIPT_BODY_DOMAIN = "llm_novel_dc/p0/windows-native-observer-receipt-body/v1"
RECEIPT_SIGNATURE_SCHEMA = "p0_windows_native_observer_receipt_signature_v1"
RECEIPT_SIGNATURE_ORIGIN = "NATIVE_OBSERVER_TPM_KEY_SIGNATURE"
RECEIPT_SIGNATURE_DOMAIN = (
    "llm_novel_dc/p0/windows-native-observer-receipt-signature/v1"
)
VALIDATION_RECEIPT_SCHEMA = (
    "p0_windows_native_observer_profile_component_receipt_v1"
)
GATE_STATUS = (
    "NATIVE_OBSERVER_PROFILE_AND_PRESENTED_SIGNATURE_MATH_PASS_"
    "EXTERNAL_PROVISIONING_NO_GO"
)
OPERATIONAL_EFFECT = "NONE_PRESENTED_COMPONENT_ONLY"

FIXED_PIPE_NAME = (
    r"\\.\pipe\llm-novel-dc-p0-owner-verifier-v2-observe-v1"
)
OBSERVER_KEY_ROLE = "NATIVE_OBSERVER_RECEIPT_SIGNING_ONLY"
OWNER_STATE_KEY_ROLE = "OWNER_STATE_TICKET_SIGNING_ONLY"
OBSERVER_KEY_ALGORITHM = "ECDSA_P256_SHA256_CNG_IEEE_P1363_LOW_S_V1"
OWNER_STATE_KEY_ALGORITHM = "ECDSA_P256_SHA256_CNG_IEEE_P1363_LOW_S_V1"
OBSERVER_KEY_STORAGE_PROVIDER = "Microsoft Platform Crypto Provider"
OBSERVER_KEY_ATTESTATION_FORMAT = "TPM_KEY_ATTESTATION_CNG_V1"
TRUSTED_TIME_MODEL = "REMOTE_OWNER_BROKER_SIGNED_UTC_QPC_BOUND_V1"
NONCE_STATE_MODEL = "REMOTE_OWNER_BROKER_EXACTLY_ONCE_V1"
TICKET_DECISION = "AUTHORIZE_ONE_NATIVE_OBSERVATION"
CHALLENGE_SIZE_BYTES = 32
MAX_REQUEST_BYTES = 64 * 1024
MAX_RESPONSE_BYTES = 1024 * 1024

_MAX_JSON_BYTES = 1024 * 1024
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_FILE_ID = re.compile(r"^[0-9a-f]{32}$")
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,255}$")
_SID = re.compile(
    r"^S-(?:0|[1-9][0-9]*)-(?:0|[1-9][0-9]*)(?:-(?:0|[1-9][0-9]*)){1,15}$"
)
_UTC = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")
_P256_ORDER = int(
    "ffffffff00000000ffffffffffffffffbce6faada7179e84f3b9cac2fc632551",
    16,
)
_P256_SPKI_PREFIX = bytes.fromhex(
    "3059301306072a8648ce3d020106082a8648ce3d03010703420004"
)

_PROFILE_FIELDS = frozenset(
    {
        "schema_version",
        "record_origin",
        "domain",
        "deployment_projection_sha256",
        "service_name",
        "service_sid",
        "fixed_pipe_name",
        "request_schema_version",
        "request_domain",
        "receipt_body_schema_version",
        "receipt_body_domain",
        "receipt_signature_schema_version",
        "receipt_signature_domain",
        "challenge_size_bytes",
        "max_request_bytes",
        "max_response_bytes",
        "observer_key_id",
        "observer_key_epoch",
        "observer_key_role",
        "observer_key_algorithm",
        "observer_public_key_spki_der_base64",
        "observer_public_key_fingerprint_sha256",
        "observer_key_storage_provider",
        "observer_key_unique_name_sha256",
        "observer_key_allowed_signature_domains",
        "observer_key_hardware_backed_required",
        "observer_key_non_exportable_required",
        "observer_key_attestation_format",
        "observer_key_attestation_sha256",
        "observer_key_security_template_sha256",
        "owner_state_ticket_schema_version",
        "owner_state_ticket_domain",
        "owner_state_authority_key_id",
        "owner_state_authority_key_epoch",
        "owner_state_authority_key_role",
        "owner_state_authority_algorithm",
        "owner_state_authority_public_key_spki_der_base64",
        "owner_state_authority_spki_sha256",
        "owner_state_authority_allowed_signature_domains",
        "trusted_time_model",
        "nonce_state_model",
        "max_ticket_lifetime_seconds",
        "min_revocation_sequence",
        "min_observer_counter",
        "artifact_sha256",
    }
)
_REQUEST_FIELDS = frozenset(
    {
        "schema_version",
        "record_origin",
        "domain",
        "request_id",
        "challenge_base64",
        "challenge_sha256",
        "policy_id",
        "policy_epoch",
        "policy_body_bytes_sha256",
        "deployment_projection_sha256",
        "native_observer_profile_sha256",
        "artifact_sha256",
    }
)
_TICKET_FIELDS = frozenset(
    {
        "schema_version",
        "record_origin",
        "domain",
        "ticket_id",
        "decision",
        "request_id",
        "request_artifact_sha256",
        "challenge_sha256",
        "policy_id",
        "policy_epoch",
        "policy_body_bytes_sha256",
        "deployment_projection_sha256",
        "native_observer_profile_sha256",
        "observer_key_id",
        "observer_key_epoch",
        "revocation_sequence",
        "observer_counter",
        "issued_at_utc",
        "not_before_utc",
        "expires_at_utc",
        "owner_state_authority_key_id",
        "owner_state_authority_key_epoch",
        "owner_state_authority_key_role",
        "algorithm",
        "signature_rs_base64",
        "artifact_sha256",
    }
)
_RECEIPT_BODY_FIELDS = frozenset(
    {
        "schema_version",
        "record_origin",
        "domain",
        "receipt_id",
        "request_id",
        "request_artifact_sha256",
        "challenge_sha256",
        "owner_state_ticket_artifact_sha256",
        "policy_id",
        "policy_epoch",
        "policy_body_bytes_sha256",
        "policy_signature_bytes_sha256",
        "owner_anchor_sha256",
        "deployment_projection_sha256",
        "native_observer_profile_sha256",
        "observer_key_id",
        "observer_key_epoch",
        "qpc_frequency",
        "observation_started_qpc",
        "observation_finished_qpc",
        "system_boot_id_sha256",
        "policy_store_evidence",
        "service_evidence",
        "image_evidence",
        "bootstrap_resource_evidence",
        "authenticode_evidence",
        "wdac_evidence",
        "provider_evidence",
        "observer_key_evidence",
        "owner_state_evidence",
        "diagnostics",
        "artifact_sha256",
    }
)
_RECEIPT_SIGNATURE_FIELDS = frozenset(
    {
        "schema_version",
        "record_origin",
        "domain",
        "receipt_body_bytes_sha256",
        "observer_key_id",
        "observer_key_epoch",
        "observer_key_role",
        "public_key_fingerprint_sha256",
        "algorithm",
        "signature_rs_base64",
        "artifact_sha256",
    }
)

_POLICY_STORE_FIELDS = frozenset(
    {
        "policy_body_bytes_sha256",
        "policy_signature_bytes_sha256",
        "owner_anchor_sha256",
        "all_required_handles_held",
        "pre_post_stable",
        "projection_sha256",
    }
)
_SERVICE_FIELDS = frozenset(
    {
        "service_name",
        "service_sid",
        "service_status",
        "service_pid",
        "process_creation_time_100ns",
        "token_user_sid",
        "service_sid_enabled",
        "service_sid_restricted",
        "token_is_restricted",
        "linked_token_absent",
        "projection_sha256",
    }
)
_IMAGE_FIELDS = frozenset(
    {
        "final_volume_guid_path",
        "volume_serial_decimal",
        "file_id_128_hex",
        "image_sha256",
        "handle_held",
        "projection_sha256",
    }
)
_RESOURCE_FIELDS = frozenset(
    {
        "resource_type",
        "resource_name",
        "language_id",
        "exact_count",
        "resource_sha256",
        "projection_sha256",
    }
)
_AUTHENTICODE_FIELDS = frozenset(
    {
        "signature_type",
        "signer_leaf_spki_sha256",
        "signer_root_spki_sha256",
        "winverifytrust_status",
        "chain_status",
        "revocation_status",
        "projection_sha256",
    }
)
_WDAC_FIELDS = frozenset(
    {
        "policy_id",
        "base_policy_id",
        "policy_sha256",
        "umci_enforcement_status",
        "projection_sha256",
    }
)
_PROVIDER_CONTAINER_FIELDS = frozenset({"modules", "projection_sha256"})
_PROVIDER_FIELDS = frozenset(
    {
        "role",
        "module_name",
        "final_volume_guid_path",
        "volume_serial_decimal",
        "file_id_128_hex",
        "image_sha256",
        "signature_type",
        "signer_leaf_spki_sha256",
        "signer_root_spki_sha256",
        "catalog_status",
        "handle_held",
        "projection_sha256",
    }
)
_OBSERVER_KEY_EVIDENCE_FIELDS = frozenset(
    {
        "key_id",
        "key_epoch",
        "storage_provider",
        "key_unique_name_sha256",
        "public_key_fingerprint_sha256",
        "hardware_backed_observed",
        "non_exportable_observed",
        "attestation_sha256",
        "security_template_sha256",
        "projection_sha256",
    }
)
_OWNER_STATE_EVIDENCE_FIELDS = frozenset(
    {
        "ticket_id",
        "ticket_artifact_sha256",
        "revocation_sequence",
        "observer_counter",
        "ticket_window_structure_observed",
        "nonce_consumption_observed",
        "trusted_time_ticket_observed",
        "projection_sha256",
    }
)

_ALWAYS_FALSE_FIELDS = (
    "profile_independently_provisioned_verified",
    "native_service_execution_verified",
    "live_host_observation_verified",
    "observer_key_hardware_backing_verified",
    "observer_key_non_exportability_verified",
    "owner_state_authority_independently_pinned",
    "trusted_time_verified",
    "revocation_current_verified",
    "durable_cross_process_nonce_verified",
    "single_use_replay_consumed",
    "signature_freshness_verified",
    "external_owner_policy_provisioning_verified",
    "external_owner_trust_verified",
    "single_interval_store_host_cross_binding_verified",
    "runtime_noninterference_verified",
    "actual_authority_granted",
    "actual_semantic_evidence_verified",
    "p0_phase_exit",
    "production_approval",
    "full_scan_approval",
    "action_applied",
    "protected_pipeline_state_mutated",
)


class P0WindowsNativeObserverProfileContractError(ValueError):
    """The presented native-observer component transcript is invalid."""


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


def with_artifact_hash(value: Mapping[str, Any]) -> dict[str, Any]:
    material = dict(value)
    material.pop("artifact_sha256", None)
    return {**material, "artifact_sha256": canonical_sha256(material)}


def with_projection_hash(value: Mapping[str, Any]) -> dict[str, Any]:
    material = dict(value)
    material.pop("projection_sha256", None)
    return {**material, "projection_sha256": canonical_sha256(material)}


def _duplicate_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise P0WindowsNativeObserverProfileContractError(
                f"duplicate JSON key is forbidden: {key}"
            )
        result[key] = value
    return result


def _reject_nonfinite(token: str) -> None:
    raise P0WindowsNativeObserverProfileContractError(
        f"non-finite JSON constant is forbidden: {token}"
    )


def _parse_canonical(raw: bytes, label: str) -> dict[str, Any]:
    if (
        type(raw) is not bytes
        or not raw
        or len(raw) > _MAX_JSON_BYTES
        or raw.startswith(b"\xef\xbb\xbf")
        or b"\r" in raw
        or not raw.endswith(b"\n")
    ):
        raise P0WindowsNativeObserverProfileContractError(
            f"{label} framing is invalid"
        )
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_duplicate_object,
            parse_constant=_reject_nonfinite,
        )
    except P0WindowsNativeObserverProfileContractError:
        raise
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise P0WindowsNativeObserverProfileContractError(
            f"{label} must be strict UTF-8 JSON"
        ) from exc
    if type(value) is not dict or raw != json_file_bytes(value):
        raise P0WindowsNativeObserverProfileContractError(
            f"{label} must be one canonical JSON object plus one LF"
        )
    return value


def _strict(value: Any, fields: frozenset[str], label: str) -> dict[str, Any]:
    if type(value) is not dict or frozenset(value) != fields:
        actual = frozenset(value) if isinstance(value, Mapping) else frozenset()
        raise P0WindowsNativeObserverProfileContractError(
            f"{label} fields mismatch: missing={sorted(fields - actual)}, "
            f"extra={sorted(actual - fields)}"
        )
    return dict(value)


def _sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise P0WindowsNativeObserverProfileContractError(
            f"{label} must be lowercase SHA-256"
        )
    return value


def _identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or _SAFE_ID.fullmatch(value) is None:
        raise P0WindowsNativeObserverProfileContractError(f"{label} is invalid")
    return value


def _positive_int(value: Any, label: str, maximum: int = 2**63 - 1) -> int:
    if type(value) is not int or not 0 < value <= maximum:
        raise P0WindowsNativeObserverProfileContractError(
            f"{label} must be a positive bounded integer"
        )
    return value


def _canonical_decimal(value: Any, label: str, maximum: int = 2**64 - 1) -> str:
    if (
        not isinstance(value, str)
        or not value.isascii()
        or not value.isdecimal()
        or (len(value) > 1 and value.startswith("0"))
        or not 0 < int(value) <= maximum
    ):
        raise P0WindowsNativeObserverProfileContractError(
            f"{label} must be canonical positive decimal"
        )
    return value


def _uuid(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise P0WindowsNativeObserverProfileContractError(
            f"{label} must be a lowercase non-nil UUID"
        )
    try:
        parsed = uuid.UUID(value)
    except ValueError as exc:
        raise P0WindowsNativeObserverProfileContractError(
            f"{label} must be a lowercase non-nil UUID"
        ) from exc
    if parsed.int == 0 or str(parsed) != value:
        raise P0WindowsNativeObserverProfileContractError(
            f"{label} must be a lowercase non-nil UUID"
        )
    return value


def _timestamp(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or _UTC.fullmatch(value) is None:
        raise P0WindowsNativeObserverProfileContractError(
            f"{label} must be second-precision canonical UTC"
        )
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError as exc:
        raise P0WindowsNativeObserverProfileContractError(
            f"{label} is not a valid UTC timestamp"
        ) from exc
    return parsed


def _canonical_base64(value: Any, label: str, length: int | None = None) -> bytes:
    if (
        not isinstance(value, str)
        or not value
        or any(character.isspace() for character in value)
    ):
        raise P0WindowsNativeObserverProfileContractError(
            f"{label} must be canonical base64"
        )
    try:
        decoded = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise P0WindowsNativeObserverProfileContractError(
            f"{label} must be canonical base64"
        ) from exc
    if (
        (length is not None and len(decoded) != length)
        or base64.b64encode(decoded).decode("ascii") != value
    ):
        raise P0WindowsNativeObserverProfileContractError(
            f"{label} has an invalid canonical width"
        )
    return decoded


def _spki(value: Any, fingerprint: Any, label: str) -> tuple[bytes, bytes]:
    encoded = _canonical_base64(value, f"{label}.spki", len(_P256_SPKI_PREFIX) + 64)
    if not encoded.startswith(_P256_SPKI_PREFIX):
        raise P0WindowsNativeObserverProfileContractError(
            f"{label} must be canonical RFC5480 P-256 SPKI"
        )
    expected = hashlib.sha256(encoded).hexdigest()
    if not hmac.compare_digest(_sha(fingerprint, f"{label}.fingerprint"), expected):
        raise P0WindowsNativeObserverProfileContractError(
            f"{label} SPKI fingerprint mismatch"
        )
    point = encoded[len(_P256_SPKI_PREFIX) :]
    return point[:32], point[32:]


def _artifact_hash(row: Mapping[str, Any], label: str) -> str:
    declared = _sha(row.get("artifact_sha256"), f"{label}.artifact_sha256")
    material = {key: value for key, value in row.items() if key != "artifact_sha256"}
    if not hmac.compare_digest(declared, canonical_sha256(material)):
        raise P0WindowsNativeObserverProfileContractError(
            f"{label} artifact hash mismatch"
        )
    return declared


def _projection_hash(row: Mapping[str, Any], label: str) -> str:
    declared = _sha(row.get("projection_sha256"), f"{label}.projection_sha256")
    material = {key: value for key, value in row.items() if key != "projection_sha256"}
    if not hmac.compare_digest(declared, canonical_sha256(material)):
        raise P0WindowsNativeObserverProfileContractError(
            f"{label} projection hash mismatch"
        )
    return declared


def _signature(value: Any, label: str) -> bytes:
    raw = _canonical_base64(value, label, 64)
    r = int.from_bytes(raw[:32], "big")
    s = int.from_bytes(raw[32:], "big")
    if not 0 < r < _P256_ORDER or not 0 < s <= _P256_ORDER // 2:
        raise P0WindowsNativeObserverProfileContractError(
            f"{label} must contain bounded low-S P-256 r||s"
        )
    return raw


def _verify_signature(
    *, x: bytes, y: bytes, material: Mapping[str, Any], signature: bytes, label: str
) -> None:
    try:
        cng_p256.verify_p256_sha256(
            public_key_x=x,
            public_key_y=y,
            digest=hashlib.sha256(canonical_bytes(material)).digest(),
            signature=signature,
        )
    except cng_p256.P0WindowsCngEcdsaP256Error as exc:
        raise P0WindowsNativeObserverProfileContractError(
            f"{label} signature mismatch"
        ) from exc


def _validate_native_observer_profile(value: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the exact nested profile for a future policy-v3 branch."""

    if not isinstance(value, Mapping):
        raise P0WindowsNativeObserverProfileContractError(
            "native observer profile must be an object"
        )
    row = _strict(dict(value), _PROFILE_FIELDS, "native observer profile")
    fixed = {
        "schema_version": PROFILE_SCHEMA,
        "record_origin": PROFILE_ORIGIN,
        "domain": PROFILE_DOMAIN,
        "service_name": deployment.SERVICE_NAME,
        "service_sid": deployment.SERVICE_SID,
        "fixed_pipe_name": FIXED_PIPE_NAME,
        "request_schema_version": REQUEST_SCHEMA,
        "request_domain": REQUEST_DOMAIN,
        "receipt_body_schema_version": RECEIPT_BODY_SCHEMA,
        "receipt_body_domain": RECEIPT_BODY_DOMAIN,
        "receipt_signature_schema_version": RECEIPT_SIGNATURE_SCHEMA,
        "receipt_signature_domain": RECEIPT_SIGNATURE_DOMAIN,
        "challenge_size_bytes": CHALLENGE_SIZE_BYTES,
        "max_request_bytes": MAX_REQUEST_BYTES,
        "max_response_bytes": MAX_RESPONSE_BYTES,
        "observer_key_role": OBSERVER_KEY_ROLE,
        "observer_key_algorithm": OBSERVER_KEY_ALGORITHM,
        "observer_key_storage_provider": OBSERVER_KEY_STORAGE_PROVIDER,
        "observer_key_attestation_format": OBSERVER_KEY_ATTESTATION_FORMAT,
        "owner_state_ticket_schema_version": OWNER_STATE_TICKET_SCHEMA,
        "owner_state_ticket_domain": OWNER_STATE_TICKET_DOMAIN,
        "owner_state_authority_key_role": OWNER_STATE_KEY_ROLE,
        "owner_state_authority_algorithm": OWNER_STATE_KEY_ALGORITHM,
        "trusted_time_model": TRUSTED_TIME_MODEL,
        "nonce_state_model": NONCE_STATE_MODEL,
    }
    if any(row[field] != expected for field, expected in fixed.items()):
        raise P0WindowsNativeObserverProfileContractError(
            "native observer profile fixed contract mismatch"
        )
    _sha(row["deployment_projection_sha256"], "profile deployment projection")
    for field in ("observer_key_id", "owner_state_authority_key_id"):
        _identifier(row[field], f"profile.{field}")
    for field in (
        "observer_key_epoch",
        "owner_state_authority_key_epoch",
        "max_ticket_lifetime_seconds",
        "min_revocation_sequence",
        "min_observer_counter",
    ):
        _positive_int(row[field], f"profile.{field}")
    if not 1 <= row["max_ticket_lifetime_seconds"] <= 3600:
        raise P0WindowsNativeObserverProfileContractError(
            "profile ticket lifetime must not exceed one hour"
        )
    if row["observer_key_hardware_backed_required"] is not True or row[
        "observer_key_non_exportable_required"
    ] is not True:
        raise P0WindowsNativeObserverProfileContractError(
            "observer key must require hardware backing and non-exportability"
        )
    if row["observer_key_allowed_signature_domains"] != [
        RECEIPT_SIGNATURE_DOMAIN
    ]:
        raise P0WindowsNativeObserverProfileContractError(
            "observer key signature domain mismatch"
        )
    if row["owner_state_authority_allowed_signature_domains"] != [
        OWNER_STATE_TICKET_DOMAIN
    ]:
        raise P0WindowsNativeObserverProfileContractError(
            "owner-state key signature domain mismatch"
        )
    observer_xy = _spki(
        row["observer_public_key_spki_der_base64"],
        row["observer_public_key_fingerprint_sha256"],
        "observer key",
    )
    state_xy = _spki(
        row["owner_state_authority_public_key_spki_der_base64"],
        row["owner_state_authority_spki_sha256"],
        "owner-state key",
    )
    if (
        row["observer_key_id"] == row["owner_state_authority_key_id"]
        or row["observer_public_key_fingerprint_sha256"]
        == row["owner_state_authority_spki_sha256"]
        or observer_xy == state_xy
    ):
        raise P0WindowsNativeObserverProfileContractError(
            "observer and owner-state keys must be distinct"
        )
    for field in (
        "observer_key_unique_name_sha256",
        "observer_key_attestation_sha256",
        "observer_key_security_template_sha256",
    ):
        _sha(row[field], f"profile.{field}")
    _artifact_hash(row, "native observer profile")
    return row


def _validate_request(raw: bytes, profile: Mapping[str, Any]) -> dict[str, Any]:
    row = _strict(_parse_canonical(raw, "observer request"), _REQUEST_FIELDS, "observer request")
    if (
        row["schema_version"] != REQUEST_SCHEMA
        or row["record_origin"] != REQUEST_ORIGIN
        or row["domain"] != REQUEST_DOMAIN
    ):
        raise P0WindowsNativeObserverProfileContractError(
            "observer request schema/domain mismatch"
        )
    _uuid(row["request_id"], "request_id")
    challenge = _canonical_base64(
        row["challenge_base64"], "request.challenge_base64", CHALLENGE_SIZE_BYTES
    )
    if not hmac.compare_digest(
        _sha(row["challenge_sha256"], "request.challenge_sha256"),
        hashlib.sha256(challenge).hexdigest(),
    ):
        raise P0WindowsNativeObserverProfileContractError(
            "request challenge hash mismatch"
        )
    _identifier(row["policy_id"], "request.policy_id")
    _positive_int(row["policy_epoch"], "request.policy_epoch")
    for field in (
        "policy_body_bytes_sha256",
        "deployment_projection_sha256",
        "native_observer_profile_sha256",
    ):
        _sha(row[field], f"request.{field}")
    if row["deployment_projection_sha256"] != profile[
        "deployment_projection_sha256"
    ] or row["native_observer_profile_sha256"] != profile["artifact_sha256"]:
        raise P0WindowsNativeObserverProfileContractError(
            "request profile/deployment cross-binding mismatch"
        )
    _artifact_hash(row, "observer request")
    return row


def _validate_ticket(
    raw: bytes,
    *,
    profile: Mapping[str, Any],
    request: Mapping[str, Any],
) -> dict[str, Any]:
    row = _strict(_parse_canonical(raw, "owner-state ticket"), _TICKET_FIELDS, "owner-state ticket")
    if (
        row["schema_version"] != OWNER_STATE_TICKET_SCHEMA
        or row["record_origin"] != OWNER_STATE_TICKET_ORIGIN
        or row["domain"] != OWNER_STATE_TICKET_DOMAIN
        or row["decision"] != TICKET_DECISION
        or row["owner_state_authority_key_role"] != OWNER_STATE_KEY_ROLE
        or row["algorithm"] != OWNER_STATE_KEY_ALGORITHM
    ):
        raise P0WindowsNativeObserverProfileContractError(
            "owner-state ticket schema/domain/key role mismatch"
        )
    _uuid(row["ticket_id"], "ticket_id")
    if row["ticket_id"] == request["request_id"]:
        raise P0WindowsNativeObserverProfileContractError(
            "ticket and request identifiers must be distinct"
        )
    exact = {
        "request_id": request["request_id"],
        "request_artifact_sha256": request["artifact_sha256"],
        "challenge_sha256": request["challenge_sha256"],
        "policy_id": request["policy_id"],
        "policy_epoch": request["policy_epoch"],
        "policy_body_bytes_sha256": request["policy_body_bytes_sha256"],
        "deployment_projection_sha256": request["deployment_projection_sha256"],
        "native_observer_profile_sha256": profile["artifact_sha256"],
        "observer_key_id": profile["observer_key_id"],
        "observer_key_epoch": profile["observer_key_epoch"],
        "owner_state_authority_key_id": profile["owner_state_authority_key_id"],
        "owner_state_authority_key_epoch": profile[
            "owner_state_authority_key_epoch"
        ],
    }
    if any(row[field] != expected for field, expected in exact.items()):
        raise P0WindowsNativeObserverProfileContractError(
            "owner-state ticket request/profile cross-binding mismatch"
        )
    revocation = _positive_int(row["revocation_sequence"], "ticket.revocation_sequence")
    counter = _positive_int(row["observer_counter"], "ticket.observer_counter")
    if revocation < profile["min_revocation_sequence"] or counter < profile[
        "min_observer_counter"
    ]:
        raise P0WindowsNativeObserverProfileContractError(
            "owner-state ticket is below the signed high-water floor"
        )
    issued = _timestamp(row["issued_at_utc"], "ticket.issued_at_utc")
    not_before = _timestamp(row["not_before_utc"], "ticket.not_before_utc")
    expires = _timestamp(row["expires_at_utc"], "ticket.expires_at_utc")
    if not issued <= not_before < expires or (
        expires - not_before
    ).total_seconds() > profile["max_ticket_lifetime_seconds"]:
        raise P0WindowsNativeObserverProfileContractError(
            "owner-state ticket time window structure is invalid"
        )
    signature = _signature(row["signature_rs_base64"], "ticket signature")
    _artifact_hash(row, "owner-state ticket")
    material = {
        key: value
        for key, value in row.items()
        if key not in {"signature_rs_base64", "artifact_sha256"}
    }
    state_x, state_y = _spki(
        profile["owner_state_authority_public_key_spki_der_base64"],
        profile["owner_state_authority_spki_sha256"],
        "owner-state key",
    )
    _verify_signature(
        x=state_x,
        y=state_y,
        material=material,
        signature=signature,
        label="owner-state ticket",
    )
    return row


def _validate_projection_row(
    value: Any, fields: frozenset[str], label: str
) -> dict[str, Any]:
    row = _strict(value, fields, label)
    _projection_hash(row, label)
    return row


def _validate_body_evidence(
    row: Mapping[str, Any],
    *,
    profile: Mapping[str, Any],
    request: Mapping[str, Any],
    ticket: Mapping[str, Any],
) -> None:
    policy_store = _validate_projection_row(
        row["policy_store_evidence"], _POLICY_STORE_FIELDS, "policy-store evidence"
    )
    if (
        policy_store["policy_body_bytes_sha256"] != row["policy_body_bytes_sha256"]
        or policy_store["policy_signature_bytes_sha256"]
        != row["policy_signature_bytes_sha256"]
        or policy_store["owner_anchor_sha256"] != row["owner_anchor_sha256"]
    ):
        raise P0WindowsNativeObserverProfileContractError(
            "policy-store evidence binding mismatch"
        )
    for field in ("all_required_handles_held", "pre_post_stable"):
        if type(policy_store[field]) is not bool:
            raise P0WindowsNativeObserverProfileContractError(
                "policy-store evidence booleans are invalid"
            )

    service = _validate_projection_row(
        row["service_evidence"], _SERVICE_FIELDS, "service evidence"
    )
    if (
        service["service_name"] != deployment.SERVICE_NAME
        or service["service_sid"] != deployment.SERVICE_SID
        or service["service_status"] not in {"RUNNING", "NOT_RUNNING"}
        or type(service["service_pid"]) is not int
        or service["service_pid"] < 0
        or type(service["process_creation_time_100ns"]) is not int
        or service["process_creation_time_100ns"] < 0
        or not isinstance(service["token_user_sid"], str)
        or _SID.fullmatch(service["token_user_sid"]) is None
        or any(
            type(service[field]) is not bool
            for field in (
                "service_sid_enabled",
                "service_sid_restricted",
                "token_is_restricted",
                "linked_token_absent",
            )
        )
    ):
        raise P0WindowsNativeObserverProfileContractError(
            "service evidence shape/binding mismatch"
        )
    running = service["service_status"] == "RUNNING"
    if (
        (service["service_pid"] > 0) is not running
        or (service["process_creation_time_100ns"] > 0) is not running
        or (
            not running
            and any(
                service[field]
                for field in (
                    "service_sid_enabled",
                    "service_sid_restricted",
                    "token_is_restricted",
                    "linked_token_absent",
                )
            )
        )
    ):
        raise P0WindowsNativeObserverProfileContractError(
            "service status/PID/token truth table mismatch"
        )

    image = _validate_projection_row(row["image_evidence"], _IMAGE_FIELDS, "image evidence")
    if (
        not isinstance(image["final_volume_guid_path"], str)
        or not image["final_volume_guid_path"].startswith("\\\\?\\Volume{")
        or _FILE_ID.fullmatch(image["file_id_128_hex"]) is None
        or type(image["handle_held"]) is not bool
    ):
        raise P0WindowsNativeObserverProfileContractError("image evidence is invalid")
    _canonical_decimal(image["volume_serial_decimal"], "image volume serial")
    _sha(image["image_sha256"], "image sha256")

    resource = _validate_projection_row(
        row["bootstrap_resource_evidence"], _RESOURCE_FIELDS, "resource evidence"
    )
    if (
        resource["resource_type"] != deployment.BOOTSTRAP_RESOURCE_TYPE
        or resource["resource_name"] != deployment.BOOTSTRAP_RESOURCE_NAME
        or type(resource["language_id"]) is not int
        or resource["language_id"] != deployment.BOOTSTRAP_RESOURCE_LANGUAGE_ID
        or type(resource["exact_count"]) is not int
        or resource["exact_count"] != 1
    ):
        raise P0WindowsNativeObserverProfileContractError(
            "bootstrap resource selector mismatch"
        )
    _sha(resource["resource_sha256"], "resource sha256")

    authenticode = _validate_projection_row(
        row["authenticode_evidence"], _AUTHENTICODE_FIELDS, "Authenticode evidence"
    )
    if authenticode["signature_type"] != deployment.VERIFIER_SIGNATURE_TYPE:
        raise P0WindowsNativeObserverProfileContractError(
            "Authenticode signature type mismatch"
        )
    for field in ("signer_leaf_spki_sha256", "signer_root_spki_sha256"):
        _sha(authenticode[field], f"Authenticode.{field}")
    if (
        authenticode["signer_leaf_spki_sha256"]
        == authenticode["signer_root_spki_sha256"]
        or authenticode["winverifytrust_status"]
        not in {"VERIFIED", "FAILED", "NOT_OBSERVED"}
        or authenticode["chain_status"]
        not in {"VERIFIED", "FAILED", "NOT_OBSERVED"}
        or authenticode["revocation_status"]
        not in {"CURRENT", "STALE", "UNKNOWN", "NOT_OBSERVED"}
    ):
        raise P0WindowsNativeObserverProfileContractError(
            "Authenticode status/signer truth table mismatch"
        )

    wdac = _validate_projection_row(row["wdac_evidence"], _WDAC_FIELDS, "WDAC evidence")
    for field in ("policy_id", "base_policy_id"):
        _uuid(wdac[field], f"WDAC.{field}")
    _sha(wdac["policy_sha256"], "WDAC policy sha256")
    if (
        wdac["policy_id"] == wdac["base_policy_id"]
        or wdac["umci_enforcement_status"]
        not in {"ENFORCED", "NOT_ENFORCED", "NOT_OBSERVED"}
    ):
        raise P0WindowsNativeObserverProfileContractError(
            "WDAC policy/UMCI status mismatch"
        )

    providers = _strict(row["provider_evidence"], _PROVIDER_CONTAINER_FIELDS, "provider evidence")
    modules = providers["modules"]
    if type(modules) is not list or len(modules) != len(deployment.PROVIDER_MODULES):
        raise P0WindowsNativeObserverProfileContractError(
            "provider evidence must contain the exact module set"
        )
    for index, (expected_role, expected_name) in enumerate(deployment.PROVIDER_MODULES):
        provider = _validate_projection_row(
            modules[index], _PROVIDER_FIELDS, f"provider evidence {index}"
        )
        if (
            provider["role"] != expected_role
            or provider["module_name"] != expected_name
            or provider["signature_type"] != deployment.PROVIDER_SIGNATURE_TYPE
            or type(provider["handle_held"]) is not bool
            or _FILE_ID.fullmatch(provider["file_id_128_hex"]) is None
            or not isinstance(provider["final_volume_guid_path"], str)
            or not provider["final_volume_guid_path"].startswith("\\\\?\\Volume{")
            or not provider["final_volume_guid_path"].endswith(
                f"\\Windows\\System32\\{expected_name}"
            )
        ):
            raise P0WindowsNativeObserverProfileContractError(
                "provider evidence identity mismatch"
            )
        _canonical_decimal(provider["volume_serial_decimal"], "provider volume")
        for field in (
            "image_sha256",
            "signer_leaf_spki_sha256",
            "signer_root_spki_sha256",
        ):
            _sha(provider[field], f"provider.{field}")
        if (
            provider["signer_leaf_spki_sha256"]
            == provider["signer_root_spki_sha256"]
            or provider["catalog_status"]
            not in {"VERIFIED", "FAILED", "NOT_OBSERVED"}
        ):
            raise P0WindowsNativeObserverProfileContractError(
                "provider catalog/signer truth table mismatch"
            )
    if not hmac.compare_digest(
        _sha(providers["projection_sha256"], "providers projection"),
        canonical_sha256(modules),
    ):
        raise P0WindowsNativeObserverProfileContractError(
            "provider container projection mismatch"
        )

    key_evidence = _validate_projection_row(
        row["observer_key_evidence"],
        _OBSERVER_KEY_EVIDENCE_FIELDS,
        "observer key evidence",
    )
    key_exact = {
        "key_id": profile["observer_key_id"],
        "key_epoch": profile["observer_key_epoch"],
        "storage_provider": profile["observer_key_storage_provider"],
        "key_unique_name_sha256": profile["observer_key_unique_name_sha256"],
        "public_key_fingerprint_sha256": profile[
            "observer_public_key_fingerprint_sha256"
        ],
        "attestation_sha256": profile["observer_key_attestation_sha256"],
        "security_template_sha256": profile[
            "observer_key_security_template_sha256"
        ],
    }
    if any(key_evidence[field] != expected for field, expected in key_exact.items()) or any(
        type(key_evidence[field]) is not bool
        for field in ("hardware_backed_observed", "non_exportable_observed")
    ):
        raise P0WindowsNativeObserverProfileContractError(
            "observer key evidence binding mismatch"
        )

    owner_state = _validate_projection_row(
        row["owner_state_evidence"],
        _OWNER_STATE_EVIDENCE_FIELDS,
        "owner-state evidence",
    )
    owner_exact = {
        "ticket_id": ticket["ticket_id"],
        "ticket_artifact_sha256": ticket["artifact_sha256"],
        "revocation_sequence": ticket["revocation_sequence"],
        "observer_counter": ticket["observer_counter"],
    }
    if any(owner_state[field] != expected for field, expected in owner_exact.items()) or any(
        type(owner_state[field]) is not bool
        for field in (
            "ticket_window_structure_observed",
            "nonce_consumption_observed",
            "trusted_time_ticket_observed",
        )
    ):
        raise P0WindowsNativeObserverProfileContractError(
            "owner-state evidence binding mismatch"
        )


def _validate_receipt_body(
    raw: bytes,
    *,
    profile: Mapping[str, Any],
    request: Mapping[str, Any],
    ticket: Mapping[str, Any],
) -> dict[str, Any]:
    row = _strict(_parse_canonical(raw, "native receipt body"), _RECEIPT_BODY_FIELDS, "native receipt body")
    if (
        row["schema_version"] != RECEIPT_BODY_SCHEMA
        or row["record_origin"] != RECEIPT_BODY_ORIGIN
        or row["domain"] != RECEIPT_BODY_DOMAIN
    ):
        raise P0WindowsNativeObserverProfileContractError(
            "native receipt body schema/domain mismatch"
        )
    _uuid(row["receipt_id"], "receipt_id")
    if row["receipt_id"] in {request["request_id"], ticket["ticket_id"]}:
        raise P0WindowsNativeObserverProfileContractError(
            "receipt/request/ticket identifiers must be distinct"
        )
    exact = {
        "request_id": request["request_id"],
        "request_artifact_sha256": request["artifact_sha256"],
        "challenge_sha256": request["challenge_sha256"],
        "owner_state_ticket_artifact_sha256": ticket["artifact_sha256"],
        "policy_id": request["policy_id"],
        "policy_epoch": request["policy_epoch"],
        "policy_body_bytes_sha256": request["policy_body_bytes_sha256"],
        "deployment_projection_sha256": profile["deployment_projection_sha256"],
        "native_observer_profile_sha256": profile["artifact_sha256"],
        "observer_key_id": profile["observer_key_id"],
        "observer_key_epoch": profile["observer_key_epoch"],
    }
    if any(row[field] != expected for field, expected in exact.items()):
        raise P0WindowsNativeObserverProfileContractError(
            "native receipt request/ticket/profile binding mismatch"
        )
    for field in (
        "policy_signature_bytes_sha256",
        "owner_anchor_sha256",
        "system_boot_id_sha256",
    ):
        _sha(row[field], f"receipt.{field}")
    frequency = _positive_int(row["qpc_frequency"], "receipt.qpc_frequency")
    start = _positive_int(row["observation_started_qpc"], "receipt.observation_started_qpc")
    finish = _positive_int(row["observation_finished_qpc"], "receipt.observation_finished_qpc")
    if finish <= start or finish - start > frequency * 300:
        raise P0WindowsNativeObserverProfileContractError(
            "native receipt observation interval is invalid"
        )
    if type(row["diagnostics"]) is not list or any(
        not isinstance(item, str) or len(item) > 1024 for item in row["diagnostics"]
    ):
        raise P0WindowsNativeObserverProfileContractError(
            "native receipt diagnostics are invalid"
        )
    _validate_body_evidence(
        row, profile=profile, request=request, ticket=ticket
    )
    _artifact_hash(row, "native receipt body")
    return row


def _validate_receipt_signature(
    raw: bytes,
    *,
    body_raw: bytes,
    profile: Mapping[str, Any],
) -> dict[str, Any]:
    row = _strict(_parse_canonical(raw, "native receipt signature"), _RECEIPT_SIGNATURE_FIELDS, "native receipt signature")
    fixed = {
        "schema_version": RECEIPT_SIGNATURE_SCHEMA,
        "record_origin": RECEIPT_SIGNATURE_ORIGIN,
        "domain": RECEIPT_SIGNATURE_DOMAIN,
        "receipt_body_bytes_sha256": hashlib.sha256(body_raw).hexdigest(),
        "observer_key_id": profile["observer_key_id"],
        "observer_key_epoch": profile["observer_key_epoch"],
        "observer_key_role": OBSERVER_KEY_ROLE,
        "public_key_fingerprint_sha256": profile[
            "observer_public_key_fingerprint_sha256"
        ],
        "algorithm": OBSERVER_KEY_ALGORITHM,
    }
    if any(row[field] != expected for field, expected in fixed.items()):
        raise P0WindowsNativeObserverProfileContractError(
            "native receipt signature domain/key/body binding mismatch"
        )
    signature = _signature(row["signature_rs_base64"], "observer signature")
    _artifact_hash(row, "native receipt signature")
    material = {
        key: value
        for key, value in row.items()
        if key not in {"signature_rs_base64", "artifact_sha256"}
    }
    observer_x, observer_y = _spki(
        profile["observer_public_key_spki_der_base64"],
        profile["observer_public_key_fingerprint_sha256"],
        "observer key",
    )
    _verify_signature(
        x=observer_x,
        y=observer_y,
        material=material,
        signature=signature,
        label="native receipt",
    )
    return row


def validate_presented_windows_native_observer_profile_component(
    *,
    native_observer_profile: Mapping[str, Any],
    request_bytes: bytes,
    owner_state_ticket_bytes: bytes,
    raw_receipt_body_bytes: bytes,
    detached_observer_signature_bytes: bytes,
) -> dict[str, Any]:
    """Validate one presented transcript without granting external authority."""

    profile = _validate_native_observer_profile(native_observer_profile)
    request = _validate_request(request_bytes, profile)
    ticket = _validate_ticket(
        owner_state_ticket_bytes, profile=profile, request=request
    )
    body = _validate_receipt_body(
        raw_receipt_body_bytes,
        profile=profile,
        request=request,
        ticket=ticket,
    )
    signature = _validate_receipt_signature(
        detached_observer_signature_bytes,
        body_raw=raw_receipt_body_bytes,
        profile=profile,
    )
    material: dict[str, Any] = {
        "schema_version": VALIDATION_RECEIPT_SCHEMA,
        "gate_status": GATE_STATUS,
        "scope": "PRESENTED_NATIVE_OBSERVER_PROFILE_COMPONENT_ONLY",
        "decision": "NO_GO",
        "profile_schema_version": profile["schema_version"],
        "profile_artifact_sha256": profile["artifact_sha256"],
        "deployment_projection_sha256": profile[
            "deployment_projection_sha256"
        ],
        "service_name": profile["service_name"],
        "service_sid": profile["service_sid"],
        "request_bytes_sha256": hashlib.sha256(request_bytes).hexdigest(),
        "request_artifact_sha256": request["artifact_sha256"],
        "request_id": request["request_id"],
        "challenge_sha256": request["challenge_sha256"],
        "owner_state_ticket_bytes_sha256": hashlib.sha256(
            owner_state_ticket_bytes
        ).hexdigest(),
        "owner_state_ticket_artifact_sha256": ticket["artifact_sha256"],
        "ticket_id": ticket["ticket_id"],
        "receipt_body_bytes_sha256": hashlib.sha256(
            raw_receipt_body_bytes
        ).hexdigest(),
        "receipt_body_artifact_sha256": body["artifact_sha256"],
        "receipt_id": body["receipt_id"],
        "detached_signature_bytes_sha256": hashlib.sha256(
            detached_observer_signature_bytes
        ).hexdigest(),
        "detached_signature_artifact_sha256": signature["artifact_sha256"],
        "strict_profile_contract_verified": True,
        "strict_canonical_transcript_verified": True,
        "request_ticket_receipt_cross_binding_verified": True,
        "observer_and_owner_state_key_roles_disjoint_verified": True,
        "owner_state_ticket_signature_math_verified": True,
        "observer_receipt_signature_math_verified": True,
        "owner_state_ticket_time_window_structure_verified": True,
        "signed_revocation_and_counter_floor_structure_verified": True,
        "presented_profile_only": True,
        "serialized_receipt_authoritative": False,
        "credited_actual_source_claim_count": 0,
        "credited_actual_a_context_review_count": 0,
        **{field: False for field in _ALWAYS_FALSE_FIELDS},
        "operational_effect": OPERATIONAL_EFFECT,
    }
    return {**material, "receipt_sha256": canonical_sha256(material)}


__all__ = [
    "CHALLENGE_SIZE_BYTES",
    "FIXED_PIPE_NAME",
    "GATE_STATUS",
    "MAX_REQUEST_BYTES",
    "MAX_RESPONSE_BYTES",
    "NONCE_STATE_MODEL",
    "OBSERVER_KEY_ALGORITHM",
    "OBSERVER_KEY_ROLE",
    "OWNER_STATE_KEY_ALGORITHM",
    "OWNER_STATE_KEY_ROLE",
    "OWNER_STATE_TICKET_DOMAIN",
    "OWNER_STATE_TICKET_SCHEMA",
    "P0WindowsNativeObserverProfileContractError",
    "PROFILE_DOMAIN",
    "PROFILE_ORIGIN",
    "PROFILE_SCHEMA",
    "RECEIPT_BODY_DOMAIN",
    "RECEIPT_BODY_ORIGIN",
    "RECEIPT_BODY_SCHEMA",
    "RECEIPT_SIGNATURE_DOMAIN",
    "RECEIPT_SIGNATURE_ORIGIN",
    "RECEIPT_SIGNATURE_SCHEMA",
    "REQUEST_DOMAIN",
    "REQUEST_ORIGIN",
    "REQUEST_SCHEMA",
    "TRUSTED_TIME_MODEL",
    "VALIDATION_RECEIPT_SCHEMA",
    "_validate_native_observer_profile",
    "canonical_bytes",
    "canonical_sha256",
    "json_file_bytes",
    "validate_presented_windows_native_observer_profile_component",
    "with_artifact_hash",
    "with_projection_hash",
]
