"""Component-only owner preauthorization for the packet V2 Windows reader.

The sole public entry point accepts only caller-presented signed material.  A
successful result proves bounded signature math and one direct Windows packet
observation; it never upgrades the presented key, clock, nonce, root, or packet
to external owner authority.
"""

from __future__ import annotations

import base64
import binascii
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any, Mapping

from llm_batch.grounding import p0_presented_a_context_annotation_packet_v2_windows_fixed_directory as windows_v2
from llm_batch.grounding import p0_windows_cng_ecdsa_p256 as cng_p256


PUBLIC_KEY_PIN_SCHEMA = "p0_actual_owner_root_public_key_pin_v2"
PREAUTHORIZATION_SCHEMA = "p0_actual_owner_root_preauthorization_v2"
SIGNATURE_ENVELOPE_SCHEMA = "p0_actual_owner_root_preauthorization_signature_envelope_v2"
RECEIPT_SCHEMA = "p0_actual_owner_root_preauthorization_receipt_v2"
PREAUTHORIZATION_DOMAIN = (
    "llm-novel-dc-community-parser/owner-root-preauthorization-v2/body/v1"
)
SIGNATURE_DOMAIN = (
    "llm-novel-dc-community-parser/owner-root-preauthorization-v2/signature/v1"
)
MEMBER_COMMITMENT_DOMAIN = (
    "llm-novel-dc-community-parser/owner-root-preauthorization-v2/members/v1"
)
NONCE_CONTEXT_DOMAIN = (
    "llm-novel-dc-community-parser/owner-root-preauthorization-v2/nonce-context/v1"
)
OWNER_ANCHOR_DOMAIN = (
    "llm-novel-dc-community-parser/owner-root-preauthorization-v2/owner-anchor/v1"
)
ROOT_IDENTITY_DOMAIN = (
    "llm-novel-dc-community-parser/owner-root-preauthorization-v2/root-identity/v1"
)
ALGORITHM = "ECDSA_P256_SHA256_CNG_P1363_LOW_S_V2"
CURVE = "NIST_P256"
COORDINATE_ENCODING = "BASE64_RAW_32_BYTE_BIG_ENDIAN_X_AND_Y"
FINGERPRINT_ENCODING = "SHA256_RFC5480_DER_SPKI"
PIN_ORIGIN = "CALLER_PRESENTED_UNTRUSTED_PUBLIC_KEY_PIN"
PREAUTHORIZATION_ORIGIN = "CALLER_PRESENTED_COMPONENT_ONLY_PREAUTHORIZATION"
SIGNATURE_ORIGIN = "CALLER_PRESENTED_DETACHED_SIGNATURE"
PURPOSE = "OWNER_SIGNED_PACKET_V2_WINDOWS_COMPONENT_ONLY_PREFLIGHT"
OPERATIONAL_EFFECT = "NONE_SHADOW_ONLY"
GATE_STATUS = "NO_GO_COMPONENT_ONLY_OWNER_PREAUTHORIZATION_V2"

WINDOWS_COMPONENT_MANIFEST_SHA256 = (
    "4e4e5c76fd3fd210a5e3c381243dccec623f2c0a48afbba6e52667d38afaae02"
)
PACKET_COMPONENT_MANIFEST_SHA256 = (
    "2a4b63518b8d80522469753191c9879af6f85f55828f28318a149911e564d59f"
)
FIXED_MEMBER_CONTRACT_SHA256 = (
    "37f3a34ab17c219065b81d9f2eb3d9a8876c5e32e12e7051ec30f3e5038385fc"
)

_MAX_PIN_BYTES = 64_000
_MAX_PREAUTHORIZATION_BYTES = 1_000_000
_MAX_SIGNATURE_ENVELOPE_BYTES = 64_000
_P256_ORDER = int(
    "FFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551",
    16,
)
_P256_SPKI_PREFIX = bytes.fromhex(
    "3059301306072a8648ce3d020106082a8648ce3d03010703420004"
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,255}$")
_UTC_Z = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")
_FILE_ID = re.compile(r"^[0-9a-f]{32}$")
_ASCII_DECIMAL = re.compile(r"^(?:0|[1-9][0-9]*)$")
_VOLUME_GUID_PATH = re.compile(
    r"^\\\\\?\\Volume\{[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-"
    r"[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}\}(?:\\.*)?$"
)

_FIXED_MEMBER_CONTRACT = (
    ("packet_manifest", "p0_presented_a_context_annotation_packet_v2_manifest.json", "application/json", 1_000_000),
    ("source_scope", "presented_source_scope_v2.json", "application/json", 1_000_000),
    ("source_census", "presented_source_census_v2.jsonl", "application/x-ndjson", 64_000_000),
    ("source_frame", "presented_source_frame_v2.json", "application/json", 1_000_000),
    ("source_seed", "presented_source_seed_v2.json", "application/json", 64_000),
    ("source_plan", "presented_source_plan_v2.json", "application/json", 64_000_000),
    ("bridge_inventory", "presented_registry_capture_bridge_v1.jsonl", "application/x-ndjson", 16_777_216),
    ("a_scope", "presented_a_context_scope_v1.json", "application/json", 1_000_000),
    ("a_census", "presented_a_context_census_v1.jsonl", "application/x-ndjson", 64_000_000),
    ("a_frame", "presented_a_context_frame_v1.json", "application/json", 1_000_000),
    ("a_seed", "presented_a_context_seed_v1.json", "application/json", 64_000),
    ("a_plan", "presented_a_context_plan_v1.json", "application/json", 64_000_000),
    ("subject_rows", "presented_a_context_annotation_subject_v2.jsonl", "application/x-ndjson", 1_000_000),
    ("subject_precommit", "presented_a_context_annotation_subject_v2_precommit.json", "application/json", 1_000_000),
    ("target_rows", "presented_a_context_annotation_event_v2_targets.jsonl", "application/x-ndjson", 1_000_000),
    ("target_precommit", "presented_a_context_annotation_event_v2_target_precommit.json", "application/json", 1_000_000),
)
_MEMBER_ROLES = tuple(row[0] for row in _FIXED_MEMBER_CONTRACT)
_MEMBER_RAW_CAPS = {row[0]: row[3] for row in _FIXED_MEMBER_CONTRACT}
_AGGREGATE_MEMBER_CAP_BYTES = 281_905_216

_PIN_FIELDS = tuple(sorted({
    "schema_version", "record_origin", "trust_domain", "project_id",
    "environment", "purpose", "key_id", "key_epoch", "algorithm", "curve",
    "coordinate_encoding", "fingerprint_encoding", "public_key_x_base64",
    "public_key_y_base64", "public_key_fingerprint_sha256",
    "owner_principal_sha256", "owner_anchor_sha256",
    "allowed_signature_domains", "artifact_sha256",
}))
_MEMBER_FIELDS = tuple(sorted({
    "ordinal", "role", "path", "media_type", "max_bytes", "raw_sha256",
}))

_BODY_FALSE_FIELDS = (
    "external_public_key_pin_provisioning_verified",
    "independent_owner_identity_verified", "trusted_time_verified",
    "revocation_current_verified", "durable_nonce_replay_prevented",
    "single_use_replay_consumed", "external_owner_trust_verified",
    "root_identity_authority_verified", "filesystem_handle_trust_verified",
    "os_write_deny_verified", "runtime_noninterference_verified",
    "write_authority_verified", "descriptive_metrics_allowed",
    "inferential_metrics_allowed", "semantic_metrics_allowed",
    "complete_case_metrics_allowed", "owner_authority_verified",
    "actual_authority_granted", "production_approval", "full_scan_approval",
    "p0_phase_exit", "action_applied", "protected_pipeline_state_mutated",
)
_BODY_FIELDS = tuple(sorted({
    "schema_version", "record_origin", "domain", "algorithm",
    "preauthorization_component_manifest_sha256",
    "windows_component_manifest_sha256", "packet_component_manifest_sha256",
    "fixed_member_contract_sha256", "member_commitment_domain",
    "member_commitment_sha256", "members", "packet_id",
    "packet_manifest_raw_sha256", "packet_manifest_artifact_sha256",
    "trust_domain", "project_id", "environment", "session_id", "run_id",
    "preauthorization_id", "owner_principal_sha256", "owner_anchor_sha256",
    "key_id", "key_epoch", "public_key_fingerprint_sha256",
    "root_final_path", "root_volume_serial", "root_file_id", "issued_at",
    "not_before", "expires_at", "nonce_base64", "nonce_context_domain",
    "nonce_context_commitment_sha256", "single_use", "operational_effect",
    "gate_status", "artifact_sha256", *_BODY_FALSE_FIELDS,
}))
_ENVELOPE_FIELDS = tuple(sorted({
    "schema_version", "record_origin", "domain", "algorithm",
    "preauthorization_schema", "preauthorization_component_manifest_sha256",
    "public_key_pin_bytes_sha256", "public_key_pin_artifact_sha256",
    "preauthorization_bytes_sha256", "preauthorization_artifact_sha256",
    "member_commitment_sha256", "nonce_context_commitment_sha256",
    "trust_domain", "project_id", "environment", "session_id", "run_id",
    "preauthorization_id", "key_id", "key_epoch",
    "public_key_fingerprint_sha256", "owner_principal_sha256",
    "owner_anchor_sha256", "signature_rs_base64", "artifact_sha256",
}))

_WINDOWS_DENIAL_FIELDS = (
    "filesystem_handle_binding_verified", "filesystem_handle_trust_verified",
    "external_root_identity_pin_verified", "root_identity_authority_verified",
    "external_manifest_pin_trust_verified", "upstream_code_identity_verified",
    "same_process_monkeypatch_resistance_verified",
    "external_owner_authority_verified", "authenticity_verified",
    "os_write_deny_verified", "runtime_noninterference_verified",
    "preauthorization_verified", "supervisor_execution_verified",
    "trusted_time_verified", "trusted_revocation_verified",
    "write_authority_verified", "actual_authority_granted",
    "descriptive_metrics_allowed", "inferential_metrics_allowed",
    "semantic_metrics_allowed", "complete_case_metrics_allowed",
    "production_approval", "full_scan_approval", "p0_phase_exit",
    "action_applied",
)
_WINDOWS_DIRECTORY_FIELDS = (
    "schema_version", "validation_mode", "windows_component_manifest_sha256",
    "packet_component_manifest_sha256", "fixed_member_contract_sha256",
    "fixed_member_count", "aggregate_member_cap_bytes",
    "expected_member_raw_sha256", "validated_member_raw_sha256",
    "expected_member_raw_pin_set_sha256", "producer_manifest_validated",
    "producer_parent_validated", "producer_parent_receipt_sha256",
    "producer_parent_receipt_full_sha256",
    "independent_target_parent_receipt_sha256",
    "independent_target_parent_receipt_full_sha256",
    "packet_parent_execution_count", "independent_target_parent_execution_count",
    "total_target_parent_execution_count", "target_parent_single_execution_claimed",
    "byte_inventory_binding_verified", "handles_held_across_packet_validation",
    "local_byte_handle_consistency_verified", *_WINDOWS_DENIAL_FIELDS,
    "operational_effect", "gate_status", "receipt_hash_scope",
    "root_final_path", "root_volume_serial", "root_file_id",
    "ancestor_handle_count", "member_handle_count", "handle_safe_projection",
    "handle_safe_projection_sha256", "receipt_sha256",
)
_WINDOWS_SAFE_FIELDS = (
    "schema_version", "handle_receipt_sha256", "root_final_path",
    "root_volume_serial", "root_file_id", "ancestor_handle_count",
    "member_handle_count", "windows_component_manifest_sha256",
    "packet_component_manifest_sha256", "fixed_member_contract_sha256",
    "member_raw_caps_sha256", "expected_member_raw_pin_set_sha256",
    "member_sequence", "member_sequence_sha256", "total_member_bytes",
    "aggregate_member_cap_bytes", "inventory_before_sha256",
    "inventory_after_sha256", "ancestor_chain_sha256",
    "root_before_projection_sha256", "root_after_projection_sha256",
    "root_reopen_projection_sha256", "member_evidence_sha256",
    "handles_held_across_packet_validation", "local_byte_handle_consistency_verified",
    *_WINDOWS_DENIAL_FIELDS, "receipt_sha256",
)

_RECEIPT_TRUE_FIELDS = (
    "presented_public_key_pin_verified",
    "public_key_fingerprint_recomputed_verified",
    "stable_owner_anchor_recomputed_verified",
    "canonical_low_s_signature_verified", "asymmetric_signature_math_verified",
    "exact_preauthorization_bytes_bound_verified",
    "single_use_declaration_bound_verified",
    "preauthorization_chronology_window_matched",
    "signed_root_identity_bound_verified",
    "signed_fixed_member_commitment_verified",
    "windows_direct_validator_called_once",
    "windows_receipt_strictly_validated",
    "windows_safe_projection_strictly_validated",
    "component_only_bounded_validation_verified",
)
_RECEIPT_FALSE_FIELDS = (
    "serialized_windows_receipt_returned", "serialized_receipt_authoritative",
    "execution_trace_transferable_by_receipt",
    "external_public_key_pin_provisioning_verified",
    "independent_owner_identity_verified", "external_owner_signing_key_verified",
    "private_key_outside_verifier_verified", "trusted_time_verified",
    "signature_freshness_verified", "revocation_current_verified",
    "durable_cross_process_nonce_verified", "power_loss_durable_replay_verified",
    "single_use_replay_consumed", "same_bundle_replay_prevented",
    "external_owner_trust_verified", "external_root_identity_pin_verified",
    "root_identity_authority_verified", "filesystem_handle_trust_verified",
    "same_process_monkeypatch_resistance_verified", "authenticity_verified",
    "packet_id_cross_verified", "packet_manifest_artifact_cross_verified",
    "os_write_deny_verified", "runtime_noninterference_verified",
    "write_authority_verified", "descriptive_metrics_allowed",
    "inferential_metrics_allowed", "semantic_metrics_allowed",
    "complete_case_metrics_allowed", "owner_authority_verified",
    "actual_authority_granted", "production_approval", "full_scan_approval",
    "p0_phase_exit", "action_applied", "protected_pipeline_state_mutated",
)
_RECEIPT_FIELDS = (
    "schema_version", "preauthorization_component_manifest_sha256",
    "windows_component_manifest_sha256", "packet_component_manifest_sha256",
    "fixed_member_contract_sha256", "public_key_pin_bytes_sha256",
    "public_key_pin_artifact_sha256", "preauthorization_bytes_sha256",
    "preauthorization_artifact_sha256", "signature_envelope_bytes_sha256",
    "signature_envelope_artifact_sha256", "signature_input_sha256",
    "public_key_fingerprint_sha256", "owner_anchor_sha256", "key_id",
    "key_epoch", "preauthorization_id", "project_id", "environment",
    "session_id", "run_id", "signed_packet_id",
    "verified_packet_manifest_raw_sha256",
    "signed_packet_manifest_artifact_sha256", "member_commitment_sha256",
    "nonce_context_commitment_sha256", "root_identity_projection_sha256",
    "expected_member_raw_pin_set_sha256", "windows_receipt_declared_sha256",
    "windows_receipt_full_sha256", "windows_safe_projection_declared_sha256",
    "windows_safe_projection_full_sha256", "observed_at",
    *_RECEIPT_TRUE_FIELDS, *_RECEIPT_FALSE_FIELDS,
    "credited_actual_source_claim_count", "credited_actual_a_context_review_count",
    "operational_effect", "gate_status", "receipt_sha256",
)


class P0ActualOwnerRootPreauthorizationV2Error(ValueError):
    """The component-only owner preauthorization failed closed."""


def _canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (RecursionError, UnicodeEncodeError, TypeError, ValueError) as exc:
        raise P0ActualOwnerRootPreauthorizationV2Error(
            "value is not canonical JSON"
        ) from exc


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise P0ActualOwnerRootPreauthorizationV2Error(
                f"duplicate JSON key: {key}"
            )
        result[key] = value
    return result


def _reject_nonfinite(token: str) -> None:
    raise P0ActualOwnerRootPreauthorizationV2Error(
        f"non-finite JSON token: {token}"
    )


def _parse(raw: bytes, *, cap: int, label: str) -> dict[str, Any]:
    if type(raw) is not bytes or not raw or len(raw) > cap:
        raise P0ActualOwnerRootPreauthorizationV2Error(
            f"{label} must be exact bytes within its fixed cap"
        )
    if raw.startswith(b"\xef\xbb\xbf") or b"\r" in raw or not raw.endswith(b"\n"):
        raise P0ActualOwnerRootPreauthorizationV2Error(
            f"{label} BOM/CRLF/final-LF framing mismatch"
        )
    try:
        value = json.loads(
            raw.decode("utf-8"), object_pairs_hook=_pairs,
            parse_constant=_reject_nonfinite,
        )
    except P0ActualOwnerRootPreauthorizationV2Error:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValueError) as exc:
        raise P0ActualOwnerRootPreauthorizationV2Error(
            f"{label} must be strict UTF-8 JSON"
        ) from exc
    if type(value) is not dict or raw != _canonical_bytes(value) + b"\n":
        raise P0ActualOwnerRootPreauthorizationV2Error(
            f"{label} must be one canonical JSON object plus one LF"
        )
    return value


def _strict(row: Any, fields: tuple[str, ...], label: str) -> dict[str, Any]:
    if type(row) is not dict or tuple(row) != fields or any(type(k) is not str for k in row):
        raise P0ActualOwnerRootPreauthorizationV2Error(
            f"{label} exact ordered fields mismatch"
        )
    return dict(row)


def _sha(value: Any, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise P0ActualOwnerRootPreauthorizationV2Error(
            f"{label} must be lowercase SHA-256"
        )
    return value


def _identifier(value: Any, label: str) -> str:
    if type(value) is not str or _SAFE_ID.fullmatch(value) is None:
        raise P0ActualOwnerRootPreauthorizationV2Error(f"{label} is invalid")
    return value


def _decode_base64(value: Any, *, length: int, label: str) -> bytes:
    if type(value) is not str or not value or any(ch.isspace() for ch in value):
        raise P0ActualOwnerRootPreauthorizationV2Error(
            f"{label} must be canonical base64"
        )
    try:
        decoded = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise P0ActualOwnerRootPreauthorizationV2Error(
            f"{label} must be canonical base64"
        ) from exc
    if len(decoded) != length or base64.b64encode(decoded).decode("ascii") != value:
        raise P0ActualOwnerRootPreauthorizationV2Error(
            f"{label} must encode exactly {length} bytes"
        )
    return decoded


def _utc(value: Any, label: str) -> datetime:
    if type(value) is not str or _UTC_Z.fullmatch(value) is None:
        raise P0ActualOwnerRootPreauthorizationV2Error(
            f"{label} must be canonical UTC seconds with Z"
        )
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError as exc:
        raise P0ActualOwnerRootPreauthorizationV2Error(
            f"{label} is not a valid UTC instant"
        ) from exc
    return parsed


def _self_hash(row: Mapping[str, Any], label: str) -> str:
    declared = _sha(row.get("artifact_sha256"), f"{label}.artifact_sha256")
    material = dict(row)
    material.pop("artifact_sha256", None)
    if declared != _canonical_sha256(material):
        raise P0ActualOwnerRootPreauthorizationV2Error(
            f"{label} self-hash mismatch"
        )
    return declared


def _fingerprint(x: bytes, y: bytes) -> str:
    return hashlib.sha256(_P256_SPKI_PREFIX + x + y).hexdigest()


def _owner_anchor(pin: Mapping[str, Any]) -> str:
    return _canonical_sha256({
        "domain": OWNER_ANCHOR_DOMAIN,
        "trust_domain": pin["trust_domain"],
        "project_id": pin["project_id"],
        "environment": pin["environment"],
        "owner_principal_sha256": pin["owner_principal_sha256"],
    })


def _validate_pin(value: Any) -> tuple[dict[str, Any], bytes, bytes]:
    row = _strict(value, _PIN_FIELDS, "public-key pin")
    if (
        row["schema_version"] != PUBLIC_KEY_PIN_SCHEMA
        or row["record_origin"] != PIN_ORIGIN
        or row["purpose"] != PURPOSE
        or row["algorithm"] != ALGORITHM
        or row["curve"] != CURVE
        or row["coordinate_encoding"] != COORDINATE_ENCODING
        or row["fingerprint_encoding"] != FINGERPRINT_ENCODING
        or row["allowed_signature_domains"] != [SIGNATURE_DOMAIN]
    ):
        raise P0ActualOwnerRootPreauthorizationV2Error(
            "public-key pin schema/domain/algorithm mismatch"
        )
    for field in ("trust_domain", "project_id", "environment", "key_id"):
        _identifier(row[field], f"public-key pin.{field}")
    if type(row["key_epoch"]) is not int or row["key_epoch"] < 1:
        raise P0ActualOwnerRootPreauthorizationV2Error(
            "public-key pin.key_epoch must be a positive integer"
        )
    x = _decode_base64(row["public_key_x_base64"], length=32, label="public-key pin X")
    y = _decode_base64(row["public_key_y_base64"], length=32, label="public-key pin Y")
    if _sha(row["public_key_fingerprint_sha256"], "public-key fingerprint") != _fingerprint(x, y):
        raise P0ActualOwnerRootPreauthorizationV2Error(
            "public-key pin RFC5480 SPKI fingerprint mismatch"
        )
    _sha(row["owner_principal_sha256"], "owner principal")
    if _sha(row["owner_anchor_sha256"], "owner anchor") != _owner_anchor(row):
        raise P0ActualOwnerRootPreauthorizationV2Error(
            "public-key pin stable owner anchor mismatch"
        )
    _self_hash(row, "public-key pin")
    return row, x, y


def _member_commitment(members: list[dict[str, Any]]) -> str:
    return _canonical_sha256({
        "domain": MEMBER_COMMITMENT_DOMAIN,
        "packet_component_manifest_sha256": PACKET_COMPONENT_MANIFEST_SHA256,
        "windows_component_manifest_sha256": WINDOWS_COMPONENT_MANIFEST_SHA256,
        "fixed_member_contract_sha256": FIXED_MEMBER_CONTRACT_SHA256,
        "members": members,
    })


def _root_projection(row: Mapping[str, Any]) -> dict[str, str]:
    return {
        "domain": ROOT_IDENTITY_DOMAIN,
        "root_final_path": row["root_final_path"],
        "root_volume_serial": row["root_volume_serial"],
        "root_file_id": row["root_file_id"],
    }


def _nonce_context(row: Mapping[str, Any]) -> str:
    return _canonical_sha256({
        "domain": NONCE_CONTEXT_DOMAIN,
        "trust_domain": row["trust_domain"],
        "project_id": row["project_id"],
        "environment": row["environment"],
        "session_id": row["session_id"],
        "run_id": row["run_id"],
        "preauthorization_id": row["preauthorization_id"],
        "packet_id": row["packet_id"],
        "packet_manifest_raw_sha256": row["packet_manifest_raw_sha256"],
        "packet_manifest_artifact_sha256": row["packet_manifest_artifact_sha256"],
        "member_commitment_sha256": row["member_commitment_sha256"],
        "owner_principal_sha256": row["owner_principal_sha256"],
        "owner_anchor_sha256": row["owner_anchor_sha256"],
        "key_id": row["key_id"],
        "key_epoch": row["key_epoch"],
        "public_key_fingerprint_sha256": row["public_key_fingerprint_sha256"],
        "root_identity": _root_projection(row),
        "nonce_base64": row["nonce_base64"],
    })


def _validate_body(value: Any, observed_at: str) -> tuple[dict[str, Any], dict[str, str]]:
    row = _strict(value, _BODY_FIELDS, "preauthorization")
    if (
        row["schema_version"] != PREAUTHORIZATION_SCHEMA
        or row["record_origin"] != PREAUTHORIZATION_ORIGIN
        or row["domain"] != PREAUTHORIZATION_DOMAIN
        or row["algorithm"] != ALGORITHM
        or row["preauthorization_component_manifest_sha256"] != COMPONENT_MANIFEST_SHA256
        or row["windows_component_manifest_sha256"] != WINDOWS_COMPONENT_MANIFEST_SHA256
        or row["packet_component_manifest_sha256"] != PACKET_COMPONENT_MANIFEST_SHA256
        or row["fixed_member_contract_sha256"] != FIXED_MEMBER_CONTRACT_SHA256
        or row["member_commitment_domain"] != MEMBER_COMMITMENT_DOMAIN
        or row["nonce_context_domain"] != NONCE_CONTEXT_DOMAIN
        or row["operational_effect"] != OPERATIONAL_EFFECT
        or row["gate_status"] != GATE_STATUS
    ):
        raise P0ActualOwnerRootPreauthorizationV2Error(
            "preauthorization schema/domain/component contract mismatch"
        )
    for field in (
        "trust_domain", "project_id", "environment", "session_id", "run_id",
        "preauthorization_id", "packet_id", "key_id",
    ):
        _identifier(row[field], f"preauthorization.{field}")
    if type(row["key_epoch"]) is not int or row["key_epoch"] < 1:
        raise P0ActualOwnerRootPreauthorizationV2Error(
            "preauthorization.key_epoch must be positive int"
        )
    for field in (
        "owner_principal_sha256", "owner_anchor_sha256",
        "public_key_fingerprint_sha256", "packet_manifest_raw_sha256",
        "packet_manifest_artifact_sha256", "member_commitment_sha256",
        "nonce_context_commitment_sha256",
    ):
        _sha(row[field], f"preauthorization.{field}")
    if (
        type(row["root_final_path"]) is not str
        or _VOLUME_GUID_PATH.fullmatch(row["root_final_path"].rstrip("\\")) is None
        or row["root_final_path"].endswith("\\")
        or type(row["root_volume_serial"]) is not str
        or _ASCII_DECIMAL.fullmatch(row["root_volume_serial"]) is None
        or not 0 <= int(row["root_volume_serial"]) < 2**64
        or type(row["root_file_id"]) is not str
        or _FILE_ID.fullmatch(row["root_file_id"]) is None
    ):
        raise P0ActualOwnerRootPreauthorizationV2Error(
            "signed root identity is not a canonical volume-GUID tuple"
        )
    _decode_base64(row["nonce_base64"], length=32, label="preauthorization nonce")
    if type(row["members"]) is not list or len(row["members"]) != 16:
        raise P0ActualOwnerRootPreauthorizationV2Error(
            "preauthorization members must be the exact 16-row list"
        )
    pins: dict[str, str] = {}
    members: list[dict[str, Any]] = []
    for ordinal, (expected, member) in enumerate(zip(_FIXED_MEMBER_CONTRACT, row["members"])):
        role, path, media_type, cap = expected
        item = _strict(member, _MEMBER_FIELDS, f"member[{ordinal}]")
        if (
            type(item["ordinal"]) is not int or item["ordinal"] != ordinal
            or type(item["role"]) is not str or item["role"] != role
            or type(item["path"]) is not str or item["path"] != path
            or type(item["media_type"]) is not str or item["media_type"] != media_type
            or type(item["max_bytes"]) is not int or item["max_bytes"] != cap
        ):
            raise P0ActualOwnerRootPreauthorizationV2Error(
                f"member[{ordinal}] fixed order/role/path/media/cap mismatch"
            )
        pins[role] = _sha(item["raw_sha256"], f"member[{ordinal}].raw_sha256")
        members.append(item)
    if row["member_commitment_sha256"] != _member_commitment(members):
        raise P0ActualOwnerRootPreauthorizationV2Error(
            "signed fixed-member commitment mismatch"
        )
    if row["packet_manifest_raw_sha256"] != pins["packet_manifest"]:
        raise P0ActualOwnerRootPreauthorizationV2Error(
            "packet manifest raw SHA must equal ordered member[0] raw SHA"
        )
    if row["nonce_context_commitment_sha256"] != _nonce_context(row):
        raise P0ActualOwnerRootPreauthorizationV2Error(
            "nonce/context commitment mismatch"
        )
    if type(row["single_use"]) is not bool or row["single_use"] is not True:
        raise P0ActualOwnerRootPreauthorizationV2Error(
            "single_use must be the signed true declaration"
        )
    if any(type(row[field]) is not bool or row[field] is not False for field in _BODY_FALSE_FIELDS):
        raise P0ActualOwnerRootPreauthorizationV2Error(
            "preauthorization authority/mutation/metric fields must remain false"
        )
    issued = _utc(row["issued_at"], "issued_at")
    not_before = _utc(row["not_before"], "not_before")
    expires = _utc(row["expires_at"], "expires_at")
    observed = _utc(observed_at, "observed_at")
    if not (issued <= not_before < expires and not_before <= observed < expires):
        raise P0ActualOwnerRootPreauthorizationV2Error(
            "preauthorization chronology or caller-presented observation window mismatch"
        )
    _self_hash(row, "preauthorization")
    return row, pins


def _signature_material(envelope: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: envelope[key]
        for key in _ENVELOPE_FIELDS
        if key not in {"signature_rs_base64", "artifact_sha256"}
    }


def _validate_envelope(value: Any) -> tuple[dict[str, Any], bytes, bytes]:
    row = _strict(value, _ENVELOPE_FIELDS, "signature envelope")
    if (
        row["schema_version"] != SIGNATURE_ENVELOPE_SCHEMA
        or row["record_origin"] != SIGNATURE_ORIGIN
        or row["domain"] != SIGNATURE_DOMAIN
        or row["algorithm"] != ALGORITHM
        or row["preauthorization_schema"] != PREAUTHORIZATION_SCHEMA
        or row["preauthorization_component_manifest_sha256"] != COMPONENT_MANIFEST_SHA256
    ):
        raise P0ActualOwnerRootPreauthorizationV2Error(
            "signature envelope schema/domain/algorithm mismatch"
        )
    for field in (
        "trust_domain", "project_id", "environment", "session_id", "run_id",
        "preauthorization_id", "key_id",
    ):
        _identifier(row[field], f"signature envelope.{field}")
    if type(row["key_epoch"]) is not int or row["key_epoch"] < 1:
        raise P0ActualOwnerRootPreauthorizationV2Error(
            "signature envelope.key_epoch must be positive int"
        )
    for field in (
        "public_key_pin_bytes_sha256", "public_key_pin_artifact_sha256",
        "preauthorization_bytes_sha256", "preauthorization_artifact_sha256",
        "member_commitment_sha256", "nonce_context_commitment_sha256",
        "public_key_fingerprint_sha256", "owner_principal_sha256",
        "owner_anchor_sha256",
    ):
        _sha(row[field], f"signature envelope.{field}")
    signature = _decode_base64(
        row["signature_rs_base64"], length=64,
        label="signature envelope P1363 signature",
    )
    r = int.from_bytes(signature[:32], "big")
    s = int.from_bytes(signature[32:], "big")
    if not 0 < r < _P256_ORDER or not 0 < s <= _P256_ORDER // 2:
        raise P0ActualOwnerRootPreauthorizationV2Error(
            "signature must be canonical nonzero in-range low-S P-256 P1363 r||s"
        )
    _self_hash(row, "signature envelope")
    material = _canonical_bytes(_signature_material(row))
    return row, signature, material


def _cross_bind(
    pin: Mapping[str, Any], body: Mapping[str, Any], envelope: Mapping[str, Any],
    *, pin_raw_sha: str, body_raw_sha: str,
) -> None:
    comparisons = (
        ("pin bytes", pin_raw_sha, envelope["public_key_pin_bytes_sha256"]),
        ("pin artifact", pin["artifact_sha256"], envelope["public_key_pin_artifact_sha256"]),
        ("preauthorization bytes", body_raw_sha, envelope["preauthorization_bytes_sha256"]),
        ("preauthorization artifact", body["artifact_sha256"], envelope["preauthorization_artifact_sha256"]),
        ("trust_domain pin/body", pin["trust_domain"], body["trust_domain"]),
        ("trust_domain pin/envelope", pin["trust_domain"], envelope["trust_domain"]),
        ("project pin/body", pin["project_id"], body["project_id"]),
        ("project pin/envelope", pin["project_id"], envelope["project_id"]),
        ("environment pin/body", pin["environment"], body["environment"]),
        ("environment pin/envelope", pin["environment"], envelope["environment"]),
        ("purpose", pin["purpose"], PURPOSE),
        ("session", body["session_id"], envelope["session_id"]),
        ("run", body["run_id"], envelope["run_id"]),
        ("preauthorization id", body["preauthorization_id"], envelope["preauthorization_id"]),
        ("key id pin/body", pin["key_id"], body["key_id"]),
        ("key id pin/envelope", pin["key_id"], envelope["key_id"]),
        ("key epoch pin/body", pin["key_epoch"], body["key_epoch"]),
        ("key epoch pin/envelope", pin["key_epoch"], envelope["key_epoch"]),
        ("fingerprint pin/body", pin["public_key_fingerprint_sha256"], body["public_key_fingerprint_sha256"]),
        ("fingerprint pin/envelope", pin["public_key_fingerprint_sha256"], envelope["public_key_fingerprint_sha256"]),
        ("owner principal pin/body", pin["owner_principal_sha256"], body["owner_principal_sha256"]),
        ("owner principal pin/envelope", pin["owner_principal_sha256"], envelope["owner_principal_sha256"]),
        ("owner anchor pin/body", pin["owner_anchor_sha256"], body["owner_anchor_sha256"]),
        ("owner anchor pin/envelope", pin["owner_anchor_sha256"], envelope["owner_anchor_sha256"]),
        ("member commitment", body["member_commitment_sha256"], envelope["member_commitment_sha256"]),
        ("nonce context", body["nonce_context_commitment_sha256"], envelope["nonce_context_commitment_sha256"]),
    )
    for label, expected, actual in comparisons:
        if expected != actual:
            raise P0ActualOwnerRootPreauthorizationV2Error(
                f"pin/body/envelope cross-binding mismatch: {label}"
            )


def _strict_windows_safe(
    value: Any, *, body: Mapping[str, Any], pins: Mapping[str, str],
) -> dict[str, Any]:
    row = _strict(value, _WINDOWS_SAFE_FIELDS, "Windows safe projection")
    string_fields = tuple(
        field for field in _WINDOWS_SAFE_FIELDS
        if field not in {"ancestor_handle_count", "member_handle_count", "total_member_bytes", "aggregate_member_cap_bytes", "member_sequence"}
        and field not in _WINDOWS_DENIAL_FIELDS
        and field not in {"handles_held_across_packet_validation", "local_byte_handle_consistency_verified"}
    )
    if any(type(row[field]) is not str for field in string_fields):
        raise P0ActualOwnerRootPreauthorizationV2Error(
            "Windows safe projection scalar type mismatch"
        )
    for field in ("ancestor_handle_count", "member_handle_count", "total_member_bytes", "aggregate_member_cap_bytes"):
        if type(row[field]) is not int:
            raise P0ActualOwnerRootPreauthorizationV2Error(
                "Windows safe projection integer type mismatch"
            )
    if type(row["member_sequence"]) is not list:
        raise P0ActualOwnerRootPreauthorizationV2Error(
            "Windows safe projection member sequence type mismatch"
        )
    if any(type(item) is not str for item in row["member_sequence"]):
        raise P0ActualOwnerRootPreauthorizationV2Error(
            "Windows safe projection member sequence scalar type mismatch"
        )
    if any(type(row[field]) is not bool or row[field] is not False for field in _WINDOWS_DENIAL_FIELDS):
        raise P0ActualOwnerRootPreauthorizationV2Error(
            "Windows safe projection denial truth table mismatch"
        )
    if any(row[field] is not True for field in ("handles_held_across_packet_validation", "local_byte_handle_consistency_verified")):
        raise P0ActualOwnerRootPreauthorizationV2Error(
            "Windows safe projection bounded truth table mismatch"
        )
    expected_pin_set = _canonical_sha256(dict(pins))
    if (
        row["schema_version"] != windows_v2.SAFE_HANDLE_PROJECTION_SCHEMA
        or row["root_final_path"] != body["root_final_path"]
        or row["root_volume_serial"] != body["root_volume_serial"]
        or row["root_file_id"] != body["root_file_id"]
        or row["ancestor_handle_count"] < 1 or row["member_handle_count"] != 16
        or row["windows_component_manifest_sha256"] != WINDOWS_COMPONENT_MANIFEST_SHA256
        or row["packet_component_manifest_sha256"] != PACKET_COMPONENT_MANIFEST_SHA256
        or row["fixed_member_contract_sha256"] != FIXED_MEMBER_CONTRACT_SHA256
        or row["member_raw_caps_sha256"] != _canonical_sha256(_MEMBER_RAW_CAPS)
        or row["expected_member_raw_pin_set_sha256"] != expected_pin_set
        or row["member_sequence"] != list(_MEMBER_ROLES)
        or row["member_sequence_sha256"] != _canonical_sha256(list(_MEMBER_ROLES))
        or not 0 <= row["total_member_bytes"] <= _AGGREGATE_MEMBER_CAP_BYTES
        or row["aggregate_member_cap_bytes"] != _AGGREGATE_MEMBER_CAP_BYTES
        or row["inventory_before_sha256"] != row["inventory_after_sha256"]
        or row["root_before_projection_sha256"] != row["root_after_projection_sha256"]
        or row["root_before_projection_sha256"] != row["root_reopen_projection_sha256"]
    ):
        raise P0ActualOwnerRootPreauthorizationV2Error(
            "Windows safe projection fixed/root/member semantics mismatch"
        )
    for field in string_fields:
        if field.endswith("_sha256"):
            _sha(row[field], f"Windows safe projection.{field}")
    declared = row["receipt_sha256"]
    material = dict(row)
    material.pop("receipt_sha256")
    if declared != _canonical_sha256(material):
        raise P0ActualOwnerRootPreauthorizationV2Error(
            "Windows safe projection self-hash mismatch"
        )
    return row


def _strict_windows_receipt(
    value: Any, *, body: Mapping[str, Any], pins: Mapping[str, str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    row = _strict(value, _WINDOWS_DIRECTORY_FIELDS, "Windows directory receipt")
    mapping_fields = {"expected_member_raw_sha256", "validated_member_raw_sha256", "handle_safe_projection"}
    integer_fields = {
        "fixed_member_count", "aggregate_member_cap_bytes",
        "packet_parent_execution_count", "independent_target_parent_execution_count",
        "total_target_parent_execution_count", "ancestor_handle_count", "member_handle_count",
    }
    boolean_fields = {
        "producer_manifest_validated", "producer_parent_validated",
        "target_parent_single_execution_claimed", "byte_inventory_binding_verified",
        "handles_held_across_packet_validation", "local_byte_handle_consistency_verified",
        *_WINDOWS_DENIAL_FIELDS,
    }
    for field in _WINDOWS_DIRECTORY_FIELDS:
        if field in mapping_fields:
            if type(row[field]) is not dict:
                raise P0ActualOwnerRootPreauthorizationV2Error(
                    f"Windows directory receipt mapping type mismatch: {field}"
                )
        elif field in integer_fields:
            if type(row[field]) is not int:
                raise P0ActualOwnerRootPreauthorizationV2Error(
                    f"Windows directory receipt integer type mismatch: {field}"
                )
        elif field in boolean_fields:
            if type(row[field]) is not bool:
                raise P0ActualOwnerRootPreauthorizationV2Error(
                    f"Windows directory receipt boolean type mismatch: {field}"
                )
        elif type(row[field]) is not str:
            raise P0ActualOwnerRootPreauthorizationV2Error(
                f"Windows directory receipt string type mismatch: {field}"
            )
    expected_pins = dict(pins)
    if (
        tuple(row["expected_member_raw_sha256"]) != _MEMBER_ROLES
        or tuple(row["validated_member_raw_sha256"]) != _MEMBER_ROLES
        or any(
            type(key) is not str or type(value) is not str
            for mapping in (
                row["expected_member_raw_sha256"],
                row["validated_member_raw_sha256"],
            )
            for key, value in mapping.items()
        )
        or row["expected_member_raw_sha256"] != expected_pins
        or row["validated_member_raw_sha256"] != expected_pins
    ):
        raise P0ActualOwnerRootPreauthorizationV2Error(
            "Windows directory receipt exact member pins mismatch"
        )
    if any(row[field] is not False for field in _WINDOWS_DENIAL_FIELDS):
        raise P0ActualOwnerRootPreauthorizationV2Error(
            "Windows directory receipt denial truth table mismatch"
        )
    required_true = (
        "producer_manifest_validated", "producer_parent_validated",
        "byte_inventory_binding_verified", "handles_held_across_packet_validation",
        "local_byte_handle_consistency_verified",
    )
    if any(row[field] is not True for field in required_true) or row["target_parent_single_execution_claimed"] is not False:
        raise P0ActualOwnerRootPreauthorizationV2Error(
            "Windows directory receipt bounded truth table mismatch"
        )
    expected_pin_set = _canonical_sha256(expected_pins)
    if (
        row["schema_version"] != windows_v2.WINDOWS_DIRECTORY_RECEIPT_SCHEMA
        or row["validation_mode"] != "WINDOWS_FIXED_DIRECTORY_DIRECT"
        or row["windows_component_manifest_sha256"] != WINDOWS_COMPONENT_MANIFEST_SHA256
        or row["packet_component_manifest_sha256"] != PACKET_COMPONENT_MANIFEST_SHA256
        or row["fixed_member_contract_sha256"] != FIXED_MEMBER_CONTRACT_SHA256
        or row["fixed_member_count"] != 16
        or row["aggregate_member_cap_bytes"] != _AGGREGATE_MEMBER_CAP_BYTES
        or row["expected_member_raw_pin_set_sha256"] != expected_pin_set
        or row["packet_parent_execution_count"] != 1
        or row["independent_target_parent_execution_count"] != 1
        or row["total_target_parent_execution_count"] != 2
        or row["operational_effect"] != "NONE_SHADOW_ONLY"
        or row["gate_status"] != "NO_GO_PRESENTED_PACKET_V2_BOUNDED_WINDOWS_HANDLE_BINDING_ONLY"
        or row["receipt_hash_scope"] != "CANONICAL_MATERIAL_EXCLUDING_RECEIPT_SHA256"
        or row["root_final_path"] != body["root_final_path"]
        or row["root_volume_serial"] != body["root_volume_serial"]
        or row["root_file_id"] != body["root_file_id"]
        or row["ancestor_handle_count"] < 1 or row["member_handle_count"] != 16
    ):
        raise P0ActualOwnerRootPreauthorizationV2Error(
            "Windows directory receipt fixed/root semantics mismatch"
        )
    for field, item in row.items():
        if field.endswith("_sha256") and type(item) is str:
            _sha(item, f"Windows directory receipt.{field}")
    safe = _strict_windows_safe(row["handle_safe_projection"], body=body, pins=pins)
    if (
        row["handle_safe_projection_sha256"] != safe["receipt_sha256"]
        or safe["root_final_path"] != row["root_final_path"]
        or safe["root_volume_serial"] != row["root_volume_serial"]
        or safe["root_file_id"] != row["root_file_id"]
        or safe["ancestor_handle_count"] != row["ancestor_handle_count"]
        or safe["member_handle_count"] != row["member_handle_count"]
    ):
        raise P0ActualOwnerRootPreauthorizationV2Error(
            "Windows directory/safe projection cross-binding mismatch"
        )
    declared = row["receipt_sha256"]
    material = dict(row)
    material.pop("receipt_sha256")
    if declared != _canonical_sha256(material):
        raise P0ActualOwnerRootPreauthorizationV2Error(
            "Windows directory receipt self-hash mismatch"
        )
    return row, safe


COMPONENT_MANIFEST = {
    "component": "p0_actual_owner_root_preauthorization_v2",
    "schemas": {
        "public_key_pin": PUBLIC_KEY_PIN_SCHEMA,
        "preauthorization": PREAUTHORIZATION_SCHEMA,
        "signature_envelope": SIGNATURE_ENVELOPE_SCHEMA,
        "receipt": RECEIPT_SCHEMA,
    },
    "domains": {
        "preauthorization": PREAUTHORIZATION_DOMAIN,
        "signature": SIGNATURE_DOMAIN,
        "member_commitment": MEMBER_COMMITMENT_DOMAIN,
        "nonce_context": NONCE_CONTEXT_DOMAIN,
        "owner_anchor": OWNER_ANCHOR_DOMAIN,
        "root_identity": ROOT_IDENTITY_DOMAIN,
    },
    "algorithm": ALGORITHM,
    "windows_component_manifest_sha256": WINDOWS_COMPONENT_MANIFEST_SHA256,
    "packet_component_manifest_sha256": PACKET_COMPONENT_MANIFEST_SHA256,
    "fixed_member_contract_sha256": FIXED_MEMBER_CONTRACT_SHA256,
    "fixed_member_contract": _FIXED_MEMBER_CONTRACT,
    "body_fields": _BODY_FIELDS,
    "pin_fields": _PIN_FIELDS,
    "envelope_fields": _ENVELOPE_FIELDS,
    "receipt_fields": _RECEIPT_FIELDS,
    "public_apis": ("validate_owner_root_preauthorization_v2_windows",),
    "private_key_or_callback_input": False,
    "serialized_receipt_input": False,
    "external_authority": False,
}
COMPONENT_MANIFEST_SHA256 = _canonical_sha256(COMPONENT_MANIFEST)


def _assert_dependency_pins() -> None:
    if (
        windows_v2.COMPONENT_MANIFEST_SHA256 != WINDOWS_COMPONENT_MANIFEST_SHA256
        or windows_v2.PACKET_COMPONENT_MANIFEST_SHA256 != PACKET_COMPONENT_MANIFEST_SHA256
        or windows_v2.FIXED_MEMBER_CONTRACT_SHA256 != FIXED_MEMBER_CONTRACT_SHA256
        or tuple(windows_v2.FIXED_MEMBER_CONTRACT) != _FIXED_MEMBER_CONTRACT
        or tuple(windows_v2.MEMBER_ROLES) != _MEMBER_ROLES
        or windows_v2.WINDOWS_DIRECTORY_RECEIPT_FIELDS != _WINDOWS_DIRECTORY_FIELDS
    ):
        raise P0ActualOwnerRootPreauthorizationV2Error(
            "final Windows V2 dependency drift pin mismatch"
        )


def validate_owner_root_preauthorization_v2_windows(
    packet_dir: Path | str,
    *,
    public_key_pin_bytes: bytes,
    preauthorization_bytes: bytes,
    signature_envelope_bytes: bytes,
    observed_at: str,
) -> dict[str, Any]:
    """Verify signed V2 component inputs, then invoke the direct Windows reader once."""

    if not isinstance(packet_dir, (str, Path)) or isinstance(packet_dir, bytes):
        raise P0ActualOwnerRootPreauthorizationV2Error(
            "packet_dir must be a path without pre-observation filesystem access"
        )
    if isinstance(packet_dir, str) and (not packet_dir or "\x00" in packet_dir):
        raise P0ActualOwnerRootPreauthorizationV2Error("packet_dir is invalid")

    # All caps, types, canonical JSON, component pins, commitments, chronology,
    # and signature math are checked before the first filesystem-capable call.
    pin_value = _parse(public_key_pin_bytes, cap=_MAX_PIN_BYTES, label="public-key pin")
    body_value = _parse(
        preauthorization_bytes, cap=_MAX_PREAUTHORIZATION_BYTES,
        label="preauthorization",
    )
    envelope_value = _parse(
        signature_envelope_bytes, cap=_MAX_SIGNATURE_ENVELOPE_BYTES,
        label="signature envelope",
    )
    _assert_dependency_pins()
    pin_raw_sha = hashlib.sha256(public_key_pin_bytes).hexdigest()
    body_raw_sha = hashlib.sha256(preauthorization_bytes).hexdigest()
    envelope_raw_sha = hashlib.sha256(signature_envelope_bytes).hexdigest()
    pin, x, y = _validate_pin(pin_value)
    body, member_pins = _validate_body(body_value, observed_at)
    envelope, signature, signature_input = _validate_envelope(envelope_value)
    _cross_bind(
        pin, body, envelope, pin_raw_sha=pin_raw_sha, body_raw_sha=body_raw_sha,
    )
    digest = hashlib.sha256(signature_input).digest()
    try:
        cng_p256.verify_p256_sha256(
            public_key_x=x, public_key_y=y, digest=digest, signature=signature,
        )
    except cng_p256.P0WindowsCngEcdsaP256Error as exc:
        raise P0ActualOwnerRootPreauthorizationV2Error(str(exc)) from exc

    # A test-controlled CNG verifier can reach this explicit boundary on a
    # non-Windows host, but no portable/pathlib fallback is ever attempted.
    if os.name != "nt":
        raise P0ActualOwnerRootPreauthorizationV2Error(
            "Windows direct fixed-directory validation is required"
        )

    try:
        windows_receipt_value = (
            windows_v2.validate_presented_a_context_annotation_packet_v2_windows_directory(
                packet_dir,
                expected_root_final_path=body["root_final_path"],
                expected_root_volume_serial=int(body["root_volume_serial"]),
                expected_root_file_id=body["root_file_id"],
                expected_member_raw_sha256=member_pins,
            )
        )
    except windows_v2.P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError as exc:
        raise P0ActualOwnerRootPreauthorizationV2Error(
            "final Windows V2 direct validation failed"
        ) from exc
    windows_receipt, safe = _strict_windows_receipt(
        windows_receipt_value, body=body, pins=member_pins,
    )

    material = {
        "schema_version": RECEIPT_SCHEMA,
        "preauthorization_component_manifest_sha256": COMPONENT_MANIFEST_SHA256,
        "windows_component_manifest_sha256": WINDOWS_COMPONENT_MANIFEST_SHA256,
        "packet_component_manifest_sha256": PACKET_COMPONENT_MANIFEST_SHA256,
        "fixed_member_contract_sha256": FIXED_MEMBER_CONTRACT_SHA256,
        "public_key_pin_bytes_sha256": pin_raw_sha,
        "public_key_pin_artifact_sha256": pin["artifact_sha256"],
        "preauthorization_bytes_sha256": body_raw_sha,
        "preauthorization_artifact_sha256": body["artifact_sha256"],
        "signature_envelope_bytes_sha256": envelope_raw_sha,
        "signature_envelope_artifact_sha256": envelope["artifact_sha256"],
        "signature_input_sha256": digest.hex(),
        "public_key_fingerprint_sha256": pin["public_key_fingerprint_sha256"],
        "owner_anchor_sha256": pin["owner_anchor_sha256"],
        "key_id": pin["key_id"],
        "key_epoch": pin["key_epoch"],
        "preauthorization_id": body["preauthorization_id"],
        "project_id": body["project_id"],
        "environment": body["environment"],
        "session_id": body["session_id"],
        "run_id": body["run_id"],
        "signed_packet_id": body["packet_id"],
        "verified_packet_manifest_raw_sha256": body["packet_manifest_raw_sha256"],
        "signed_packet_manifest_artifact_sha256": body["packet_manifest_artifact_sha256"],
        "member_commitment_sha256": body["member_commitment_sha256"],
        "nonce_context_commitment_sha256": body["nonce_context_commitment_sha256"],
        "root_identity_projection_sha256": _canonical_sha256(_root_projection(body)),
        "expected_member_raw_pin_set_sha256": _canonical_sha256(member_pins),
        "windows_receipt_declared_sha256": windows_receipt["receipt_sha256"],
        "windows_receipt_full_sha256": _canonical_sha256(windows_receipt),
        "windows_safe_projection_declared_sha256": safe["receipt_sha256"],
        "windows_safe_projection_full_sha256": _canonical_sha256(safe),
        "observed_at": observed_at,
        **{field: True for field in _RECEIPT_TRUE_FIELDS},
        **{field: False for field in _RECEIPT_FALSE_FIELDS},
        "credited_actual_source_claim_count": 0,
        "credited_actual_a_context_review_count": 0,
        "operational_effect": OPERATIONAL_EFFECT,
        "gate_status": GATE_STATUS,
    }
    if tuple(material) + ("receipt_sha256",) != _RECEIPT_FIELDS:
        raise P0ActualOwnerRootPreauthorizationV2Error(
            "internal public receipt exact field drift"
        )
    return {**material, "receipt_sha256": _canonical_sha256(material)}


__all__ = ["validate_owner_root_preauthorization_v2_windows"]
