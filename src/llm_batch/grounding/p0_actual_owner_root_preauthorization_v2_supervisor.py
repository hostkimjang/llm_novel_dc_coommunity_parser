"""One-step, component-only supervisor for owner preauthorization V2.

This wrapper adds no filesystem or owner authority.  It prechecks the exact
caller-presented byte inputs, invokes the V2 preauthorization component once,
strictly revalidates its fixed public receipt, and returns only a bounded safe
projection plus hashes.  The child is the sole filesystem-capable boundary.
"""

from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path
import re
from typing import Any, Mapping

from llm_batch.grounding import p0_actual_owner_root_preauthorization_v2 as preauth_v2


RECEIPT_SCHEMA = "p0_actual_owner_root_preauthorization_v2_supervisor_receipt_v1"
SAFE_PROJECTION_SCHEMA = (
    "p0_actual_owner_root_preauthorization_v2_supervisor_child_safe_projection_v1"
)
STEP_RECEIPT_SCHEMA = (
    "p0_actual_owner_root_preauthorization_v2_supervisor_step_receipt_v1"
)
RAW_INPUT_BINDING_DOMAIN = (
    "llm-novel-dc-community-parser/owner-root-preauthorization-v2-supervisor/"
    "raw-input-binding/v1"
)
TRUTH_TABLE_BINDING_DOMAIN = (
    "llm-novel-dc-community-parser/owner-root-preauthorization-v2-supervisor/"
    "child-truth-table/v1"
)
STEP_RECEIPT_DOMAIN = (
    "llm-novel-dc-community-parser/owner-root-preauthorization-v2-supervisor/"
    "step-receipt/v1"
)
OPERATIONAL_EFFECT = "NONE_SHADOW_ONLY"
GATE_STATUS = "NO_GO_COMPONENT_ONLY_OWNER_PREAUTHORIZATION_V2_SUPERVISOR"
EXECUTION_STEP = "PREAUTHORIZATION_V2_VALIDATE_ONCE"

PREAUTHORIZATION_COMPONENT_MANIFEST_SHA256 = (
    "07ae0af427112978ba3cb5f5a0ae8713a25837cbb9ae65ac0b7993da7d44876e"
)
WINDOWS_COMPONENT_MANIFEST_SHA256 = (
    "4e4e5c76fd3fd210a5e3c381243dccec623f2c0a48afbba6e52667d38afaae02"
)
PACKET_COMPONENT_MANIFEST_SHA256 = (
    "2a4b63518b8d80522469753191c9879af6f85f55828f28318a149911e564d59f"
)
FIXED_MEMBER_CONTRACT_SHA256 = (
    "37f3a34ab17c219065b81d9f2eb3d9a8876c5e32e12e7051ec30f3e5038385fc"
)
PREAUTHORIZATION_PUBLIC_API = "validate_owner_root_preauthorization_v2_windows"
PREAUTHORIZATION_RECEIPT_SCHEMA = "p0_actual_owner_root_preauthorization_receipt_v2"
PREAUTHORIZATION_OPERATIONAL_EFFECT = "NONE_SHADOW_ONLY"
PREAUTHORIZATION_GATE_STATUS = "NO_GO_COMPONENT_ONLY_OWNER_PREAUTHORIZATION_V2"

_MAX_PIN_BYTES = 64_000
_MAX_PREAUTHORIZATION_BYTES = 1_000_000
_MAX_SIGNATURE_ENVELOPE_BYTES = 64_000
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_UTC_Z = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")

_CHILD_TRUE_FIELDS = (
    "presented_public_key_pin_verified",
    "public_key_fingerprint_recomputed_verified",
    "stable_owner_anchor_recomputed_verified",
    "canonical_low_s_signature_verified",
    "asymmetric_signature_math_verified",
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
_CHILD_FALSE_FIELDS = (
    "serialized_windows_receipt_returned",
    "serialized_receipt_authoritative",
    "execution_trace_transferable_by_receipt",
    "external_public_key_pin_provisioning_verified",
    "independent_owner_identity_verified",
    "external_owner_signing_key_verified",
    "private_key_outside_verifier_verified",
    "trusted_time_verified",
    "signature_freshness_verified",
    "revocation_current_verified",
    "durable_cross_process_nonce_verified",
    "power_loss_durable_replay_verified",
    "single_use_replay_consumed",
    "same_bundle_replay_prevented",
    "external_owner_trust_verified",
    "external_root_identity_pin_verified",
    "root_identity_authority_verified",
    "filesystem_handle_trust_verified",
    "same_process_monkeypatch_resistance_verified",
    "authenticity_verified",
    "packet_id_cross_verified",
    "packet_manifest_artifact_cross_verified",
    "os_write_deny_verified",
    "runtime_noninterference_verified",
    "write_authority_verified",
    "descriptive_metrics_allowed",
    "inferential_metrics_allowed",
    "semantic_metrics_allowed",
    "complete_case_metrics_allowed",
    "owner_authority_verified",
    "actual_authority_granted",
    "production_approval",
    "full_scan_approval",
    "p0_phase_exit",
    "action_applied",
    "protected_pipeline_state_mutated",
)
_CHILD_RECEIPT_FIELDS = (
    "schema_version",
    "preauthorization_component_manifest_sha256",
    "windows_component_manifest_sha256",
    "packet_component_manifest_sha256",
    "fixed_member_contract_sha256",
    "public_key_pin_bytes_sha256",
    "public_key_pin_artifact_sha256",
    "preauthorization_bytes_sha256",
    "preauthorization_artifact_sha256",
    "signature_envelope_bytes_sha256",
    "signature_envelope_artifact_sha256",
    "signature_input_sha256",
    "public_key_fingerprint_sha256",
    "owner_anchor_sha256",
    "key_id",
    "key_epoch",
    "preauthorization_id",
    "project_id",
    "environment",
    "session_id",
    "run_id",
    "signed_packet_id",
    "verified_packet_manifest_raw_sha256",
    "signed_packet_manifest_artifact_sha256",
    "member_commitment_sha256",
    "nonce_context_commitment_sha256",
    "root_identity_projection_sha256",
    "expected_member_raw_pin_set_sha256",
    "windows_receipt_declared_sha256",
    "windows_receipt_full_sha256",
    "windows_safe_projection_declared_sha256",
    "windows_safe_projection_full_sha256",
    "observed_at",
    *_CHILD_TRUE_FIELDS,
    *_CHILD_FALSE_FIELDS,
    "credited_actual_source_claim_count",
    "credited_actual_a_context_review_count",
    "operational_effect",
    "gate_status",
    "receipt_sha256",
)

_CHILD_SAFE_SOURCE_FIELDS = (
    "preauthorization_component_manifest_sha256",
    "windows_component_manifest_sha256",
    "packet_component_manifest_sha256",
    "fixed_member_contract_sha256",
    "public_key_pin_bytes_sha256",
    "preauthorization_bytes_sha256",
    "signature_envelope_bytes_sha256",
    "signature_input_sha256",
    "public_key_fingerprint_sha256",
    "owner_anchor_sha256",
    "preauthorization_id",
    "project_id",
    "environment",
    "session_id",
    "run_id",
    "signed_packet_id",
    "verified_packet_manifest_raw_sha256",
    "signed_packet_manifest_artifact_sha256",
    "member_commitment_sha256",
    "nonce_context_commitment_sha256",
    "root_identity_projection_sha256",
    "expected_member_raw_pin_set_sha256",
    "windows_receipt_declared_sha256",
    "windows_receipt_full_sha256",
    "windows_safe_projection_declared_sha256",
    "windows_safe_projection_full_sha256",
    "observed_at",
)
_CHILD_SAFE_FIELDS = (
    "schema_version",
    *_CHILD_SAFE_SOURCE_FIELDS,
    "child_true_field_count",
    "child_false_field_count",
    "child_truth_table_projection_sha256",
    "child_receipt_sha256",
    "receipt_sha256",
)

_STEP_RECEIPT_FIELDS = (
    "schema_version",
    "domain",
    "ordinal",
    "operation",
    "raw_input_binding_sha256",
    "child_receipt_declared_sha256",
    "child_receipt_full_sha256",
    "child_safe_projection_sha256",
    "child_truth_table_projection_sha256",
    "preauthorization_execution_count",
    "direct_windows_execution_count",
    "receipt_sha256",
)

_SUPERVISOR_TRUE_FIELDS = (
    "exact_input_bytes_prechecked",
    "preauthorization_public_api_identity_pinned",
    "preauthorization_validator_called_once",
    "child_receipt_exactly_validated",
    "child_receipt_self_hash_verified",
    "raw_input_binding_verified",
    "child_truth_table_exactly_validated",
    "child_windows_direct_validator_called_once_bound",
    "component_only_supervisor_validation_verified",
)
_SUPERVISOR_FALSE_FIELDS = (
    "serialized_child_receipt_returned",
    "child_receipt_authoritative",
    "execution_trace_transferable_by_receipt",
    "supervisor_independent_windows_observation_verified",
    "direct_windows_validator_called_by_supervisor",
    "external_public_key_pin_provisioning_verified",
    "independent_owner_identity_verified",
    "external_owner_signing_key_verified",
    "private_key_outside_verifier_verified",
    "trusted_time_verified",
    "signature_freshness_verified",
    "revocation_current_verified",
    "durable_cross_process_nonce_verified",
    "power_loss_durable_replay_verified",
    "single_use_replay_consumed",
    "same_bundle_replay_prevented",
    "external_owner_trust_verified",
    "external_root_identity_pin_verified",
    "root_identity_authority_verified",
    "filesystem_handle_trust_verified",
    "same_process_monkeypatch_resistance_verified",
    "upstream_code_identity_verified",
    "authenticity_verified",
    "os_write_deny_verified",
    "runtime_noninterference_verified",
    "write_authority_verified",
    "descriptive_metrics_allowed",
    "inferential_metrics_allowed",
    "semantic_metrics_allowed",
    "complete_case_metrics_allowed",
    "owner_authority_verified",
    "actual_authority_granted",
    "production_approval",
    "full_scan_approval",
    "p0_phase_exit",
    "action_applied",
    "protected_pipeline_state_mutated",
)
_RECEIPT_FIELDS = (
    "schema_version",
    "supervisor_component_manifest_sha256",
    "preauthorization_component_manifest_sha256",
    "windows_component_manifest_sha256",
    "packet_component_manifest_sha256",
    "fixed_member_contract_sha256",
    "preauthorization_public_api",
    "packet_dir_input_kind",
    "packet_dir_lexical_utf8_sha256",
    "public_key_pin_bytes_sha256",
    "preauthorization_bytes_sha256",
    "signature_envelope_bytes_sha256",
    "raw_input_binding_sha256",
    "observed_at",
    "child_receipt_declared_sha256",
    "child_receipt_full_sha256",
    "child_safe_projection",
    "child_safe_projection_sha256",
    "child_truth_table_projection_sha256",
    "execution_step",
    "execution_step_count",
    "preauthorization_execution_count",
    "direct_windows_execution_count",
    "execution_step_receipt",
    "execution_step_receipt_declared_sha256",
    "execution_step_receipt_full_sha256",
    *_SUPERVISOR_TRUE_FIELDS,
    *_SUPERVISOR_FALSE_FIELDS,
    "credited_actual_source_claim_count",
    "credited_actual_a_context_review_count",
    "operational_effect",
    "gate_status",
    "receipt_sha256",
)


class P0ActualOwnerRootPreauthorizationV2SupervisorError(ValueError):
    """The memory-only V2 supervisor failed closed."""


def _canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (RecursionError, TypeError, UnicodeEncodeError, ValueError) as exc:
        raise P0ActualOwnerRootPreauthorizationV2SupervisorError(
            "value is not canonical JSON"
        ) from exc


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _sha(value: Any, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise P0ActualOwnerRootPreauthorizationV2SupervisorError(
            f"{label} must be lowercase SHA-256"
        )
    return value


def _precheck_bytes(value: Any, *, cap: int, label: str) -> bytes:
    if type(value) is not bytes or not value or len(value) > cap:
        raise P0ActualOwnerRootPreauthorizationV2SupervisorError(
            f"{label} must be exact non-empty bytes within its fixed cap"
        )
    return value


def _assert_dependency_contract() -> Any:
    expected_parameters = (
        "packet_dir",
        "public_key_pin_bytes",
        "preauthorization_bytes",
        "signature_envelope_bytes",
        "observed_at",
    )
    api = getattr(preauth_v2, PREAUTHORIZATION_PUBLIC_API, None)
    try:
        signature = inspect.signature(api)
    except (TypeError, ValueError) as exc:
        raise P0ActualOwnerRootPreauthorizationV2SupervisorError(
            "preauthorization V2 public API identity drift"
        ) from exc
    parameters = tuple(signature.parameters.values())
    manifest = preauth_v2.COMPONENT_MANIFEST
    if (
        preauth_v2.COMPONENT_MANIFEST_SHA256
        != PREAUTHORIZATION_COMPONENT_MANIFEST_SHA256
        or _canonical_sha256(manifest)
        != PREAUTHORIZATION_COMPONENT_MANIFEST_SHA256
        or type(manifest) is not dict
        or manifest.get("receipt_fields") != _CHILD_RECEIPT_FIELDS
        or manifest.get("public_apis") != (PREAUTHORIZATION_PUBLIC_API,)
        or manifest.get("windows_component_manifest_sha256")
        != WINDOWS_COMPONENT_MANIFEST_SHA256
        or manifest.get("packet_component_manifest_sha256")
        != PACKET_COMPONENT_MANIFEST_SHA256
        or manifest.get("fixed_member_contract_sha256")
        != FIXED_MEMBER_CONTRACT_SHA256
        or getattr(preauth_v2, "__all__", None) != [PREAUTHORIZATION_PUBLIC_API]
        or not callable(api)
        or getattr(api, "__name__", None) != PREAUTHORIZATION_PUBLIC_API
        or getattr(api, "__module__", None) != preauth_v2.__name__
        or tuple(signature.parameters) != expected_parameters
        or len(parameters) != 5
        or parameters[0].kind
        not in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
        or any(item.kind is not inspect.Parameter.KEYWORD_ONLY for item in parameters[1:])
    ):
        raise P0ActualOwnerRootPreauthorizationV2SupervisorError(
            "preauthorization V2 dependency contract drift"
        )
    return api


def _packet_dir_lexical_binding(packet_dir: Any) -> tuple[str, str, int]:
    if type(packet_dir) is str:
        input_kind = "STR"
        lexical = packet_dir
    elif type(packet_dir) is type(Path()):
        input_kind = "PATH"
        lexical = str(packet_dir)
    else:
        raise P0ActualOwnerRootPreauthorizationV2SupervisorError(
            "packet_dir must be an exact str or concrete Path"
        )
    if not lexical or "\x00" in lexical:
        raise P0ActualOwnerRootPreauthorizationV2SupervisorError(
            "packet_dir lexical input is invalid"
        )
    try:
        lexical_bytes = lexical.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise P0ActualOwnerRootPreauthorizationV2SupervisorError(
            "packet_dir lexical input must encode as UTF-8"
        ) from exc
    return input_kind, hashlib.sha256(lexical_bytes).hexdigest(), len(lexical_bytes)


def _strict_child_receipt(
    value: Any,
    *,
    pin_raw_sha: str,
    preauthorization_raw_sha: str,
    envelope_raw_sha: str,
    observed_at: str,
) -> tuple[dict[str, Any], dict[str, Any], str]:
    if (
        type(value) is not dict
        or tuple(value) != _CHILD_RECEIPT_FIELDS
        or any(type(key) is not str for key in value)
    ):
        raise P0ActualOwnerRootPreauthorizationV2SupervisorError(
            "child receipt exact ordered fields mismatch"
        )
    row = dict(value)
    integer_fields = {
        "key_epoch",
        "credited_actual_source_claim_count",
        "credited_actual_a_context_review_count",
    }
    boolean_fields = {*_CHILD_TRUE_FIELDS, *_CHILD_FALSE_FIELDS}
    for field in _CHILD_RECEIPT_FIELDS:
        if field in integer_fields:
            if type(row[field]) is not int:
                raise P0ActualOwnerRootPreauthorizationV2SupervisorError(
                    f"child receipt integer type mismatch: {field}"
                )
        elif field in boolean_fields:
            if type(row[field]) is not bool:
                raise P0ActualOwnerRootPreauthorizationV2SupervisorError(
                    f"child receipt boolean type mismatch: {field}"
                )
        elif type(row[field]) is not str:
            raise P0ActualOwnerRootPreauthorizationV2SupervisorError(
                f"child receipt string type mismatch: {field}"
            )
    for field, item in row.items():
        if field.endswith("_sha256"):
            _sha(item, f"child receipt.{field}")
    if any(row[field] is not True for field in _CHILD_TRUE_FIELDS):
        raise P0ActualOwnerRootPreauthorizationV2SupervisorError(
            "child receipt bounded truth table mismatch"
        )
    if any(row[field] is not False for field in _CHILD_FALSE_FIELDS):
        raise P0ActualOwnerRootPreauthorizationV2SupervisorError(
            "child receipt denial truth table mismatch"
        )
    if (
        row["schema_version"] != PREAUTHORIZATION_RECEIPT_SCHEMA
        or row["preauthorization_component_manifest_sha256"]
        != PREAUTHORIZATION_COMPONENT_MANIFEST_SHA256
        or row["windows_component_manifest_sha256"]
        != WINDOWS_COMPONENT_MANIFEST_SHA256
        or row["packet_component_manifest_sha256"]
        != PACKET_COMPONENT_MANIFEST_SHA256
        or row["fixed_member_contract_sha256"]
        != FIXED_MEMBER_CONTRACT_SHA256
        or row["public_key_pin_bytes_sha256"] != pin_raw_sha
        or row["preauthorization_bytes_sha256"] != preauthorization_raw_sha
        or row["signature_envelope_bytes_sha256"] != envelope_raw_sha
        or row["observed_at"] != observed_at
        or row["credited_actual_source_claim_count"] != 0
        or row["credited_actual_a_context_review_count"] != 0
        or row["operational_effect"] != PREAUTHORIZATION_OPERATIONAL_EFFECT
        or row["gate_status"] != PREAUTHORIZATION_GATE_STATUS
    ):
        raise P0ActualOwnerRootPreauthorizationV2SupervisorError(
            "child receipt fixed/input/gate semantics mismatch"
        )
    declared = row["receipt_sha256"]
    material = dict(row)
    material.pop("receipt_sha256")
    if declared != _canonical_sha256(material):
        raise P0ActualOwnerRootPreauthorizationV2SupervisorError(
            "child receipt self-hash mismatch"
        )
    truth_projection = {
        "domain": TRUTH_TABLE_BINDING_DOMAIN,
        "required_true": {field: row[field] for field in _CHILD_TRUE_FIELDS},
        "required_false": {field: row[field] for field in _CHILD_FALSE_FIELDS},
        "credited_actual_source_claim_count": row["credited_actual_source_claim_count"],
        "credited_actual_a_context_review_count": row[
            "credited_actual_a_context_review_count"
        ],
        "operational_effect": row["operational_effect"],
        "gate_status": row["gate_status"],
    }
    truth_sha = _canonical_sha256(truth_projection)
    safe_material = {
        "schema_version": SAFE_PROJECTION_SCHEMA,
        **{field: row[field] for field in _CHILD_SAFE_SOURCE_FIELDS},
        "child_true_field_count": len(_CHILD_TRUE_FIELDS),
        "child_false_field_count": len(_CHILD_FALSE_FIELDS),
        "child_truth_table_projection_sha256": truth_sha,
        "child_receipt_sha256": declared,
    }
    if tuple(safe_material) + ("receipt_sha256",) != _CHILD_SAFE_FIELDS:
        raise P0ActualOwnerRootPreauthorizationV2SupervisorError(
            "internal child safe projection field drift"
        )
    safe = {**safe_material, "receipt_sha256": _canonical_sha256(safe_material)}
    return row, safe, truth_sha


def _strict_step_receipt(
    value: Any,
    *,
    raw_input_binding_sha256: str,
    child_receipt_declared_sha256: str,
    child_receipt_full_sha256: str,
    child_safe_projection_sha256: str,
    child_truth_table_projection_sha256: str,
) -> dict[str, Any]:
    if (
        type(value) is not dict
        or tuple(value) != _STEP_RECEIPT_FIELDS
        or any(type(key) is not str for key in value)
    ):
        raise P0ActualOwnerRootPreauthorizationV2SupervisorError(
            "execution step receipt exact ordered fields mismatch"
        )
    row = dict(value)
    integer_fields = {
        "ordinal",
        "preauthorization_execution_count",
        "direct_windows_execution_count",
    }
    for field in _STEP_RECEIPT_FIELDS:
        if field in integer_fields:
            if type(row[field]) is not int:
                raise P0ActualOwnerRootPreauthorizationV2SupervisorError(
                    f"execution step receipt integer type mismatch: {field}"
                )
        elif type(row[field]) is not str:
            raise P0ActualOwnerRootPreauthorizationV2SupervisorError(
                f"execution step receipt string type mismatch: {field}"
            )
    for field, item in row.items():
        if field.endswith("_sha256"):
            _sha(item, f"execution step receipt.{field}")
    if (
        row["schema_version"] != STEP_RECEIPT_SCHEMA
        or row["domain"] != STEP_RECEIPT_DOMAIN
        or row["ordinal"] != 0
        or row["operation"] != EXECUTION_STEP
        or row["raw_input_binding_sha256"] != raw_input_binding_sha256
        or row["child_receipt_declared_sha256"]
        != child_receipt_declared_sha256
        or row["child_receipt_full_sha256"] != child_receipt_full_sha256
        or row["child_safe_projection_sha256"]
        != child_safe_projection_sha256
        or row["child_truth_table_projection_sha256"]
        != child_truth_table_projection_sha256
        or row["preauthorization_execution_count"] != 1
        or row["direct_windows_execution_count"] != 0
    ):
        raise P0ActualOwnerRootPreauthorizationV2SupervisorError(
            "execution step receipt fixed input/output semantics mismatch"
        )
    material = dict(row)
    declared = material.pop("receipt_sha256")
    if declared != _canonical_sha256(material):
        raise P0ActualOwnerRootPreauthorizationV2SupervisorError(
            "execution step receipt self-hash mismatch"
        )
    return row


COMPONENT_MANIFEST = {
    "component": "p0_actual_owner_root_preauthorization_v2_supervisor",
    "receipt_schema": RECEIPT_SCHEMA,
    "safe_projection_schema": SAFE_PROJECTION_SCHEMA,
    "raw_input_binding_domain": RAW_INPUT_BINDING_DOMAIN,
    "truth_table_binding_domain": TRUTH_TABLE_BINDING_DOMAIN,
    "step_receipt_schema": STEP_RECEIPT_SCHEMA,
    "step_receipt_domain": STEP_RECEIPT_DOMAIN,
    "preauthorization_component_manifest_sha256": (
        PREAUTHORIZATION_COMPONENT_MANIFEST_SHA256
    ),
    "windows_component_manifest_sha256": WINDOWS_COMPONENT_MANIFEST_SHA256,
    "packet_component_manifest_sha256": PACKET_COMPONENT_MANIFEST_SHA256,
    "fixed_member_contract_sha256": FIXED_MEMBER_CONTRACT_SHA256,
    "preauthorization_public_api": PREAUTHORIZATION_PUBLIC_API,
    "preauthorization_receipt_fields": _CHILD_RECEIPT_FIELDS,
    "child_safe_fields": _CHILD_SAFE_FIELDS,
    "step_receipt_fields": _STEP_RECEIPT_FIELDS,
    "receipt_fields": _RECEIPT_FIELDS,
    "execution_step": EXECUTION_STEP,
    "execution_step_count": 1,
    "preauthorization_execution_count": 1,
    "direct_windows_execution_count": 0,
    "serialized_child_receipt_returned": False,
    "external_authority": False,
    "public_apis": ("execute_owner_root_preauthorization_v2_supervisor_windows",),
}
COMPONENT_MANIFEST_SHA256 = _canonical_sha256(COMPONENT_MANIFEST)


def execute_owner_root_preauthorization_v2_supervisor_windows(
    packet_dir: Path | str,
    *,
    public_key_pin_bytes: bytes,
    preauthorization_bytes: bytes,
    signature_envelope_bytes: bytes,
    observed_at: str,
) -> dict[str, Any]:
    """Execute exactly one preauthorization V2 validation and fail closed."""

    packet_dir_input_kind, packet_dir_lexical_sha, packet_dir_lexical_length = (
        _packet_dir_lexical_binding(packet_dir)
    )
    pin_bytes = _precheck_bytes(
        public_key_pin_bytes, cap=_MAX_PIN_BYTES, label="public_key_pin_bytes"
    )
    body_bytes = _precheck_bytes(
        preauthorization_bytes,
        cap=_MAX_PREAUTHORIZATION_BYTES,
        label="preauthorization_bytes",
    )
    envelope_bytes = _precheck_bytes(
        signature_envelope_bytes,
        cap=_MAX_SIGNATURE_ENVELOPE_BYTES,
        label="signature_envelope_bytes",
    )
    if type(observed_at) is not str or _UTC_Z.fullmatch(observed_at) is None:
        raise P0ActualOwnerRootPreauthorizationV2SupervisorError(
            "observed_at must be canonical UTC seconds with Z"
        )
    child_api = _assert_dependency_contract()

    pin_raw_sha = hashlib.sha256(pin_bytes).hexdigest()
    body_raw_sha = hashlib.sha256(body_bytes).hexdigest()
    envelope_raw_sha = hashlib.sha256(envelope_bytes).hexdigest()
    raw_input_binding = {
        "domain": RAW_INPUT_BINDING_DOMAIN,
        "packet_dir_input_kind": packet_dir_input_kind,
        "packet_dir_lexical_utf8_length": packet_dir_lexical_length,
        "packet_dir_lexical_utf8_sha256": packet_dir_lexical_sha,
        "public_key_pin_bytes_length": len(pin_bytes),
        "public_key_pin_bytes_sha256": pin_raw_sha,
        "preauthorization_bytes_length": len(body_bytes),
        "preauthorization_bytes_sha256": body_raw_sha,
        "signature_envelope_bytes_length": len(envelope_bytes),
        "signature_envelope_bytes_sha256": envelope_raw_sha,
        "observed_at": observed_at,
    }
    raw_input_binding_sha = _canonical_sha256(raw_input_binding)

    try:
        child_value = child_api(
            packet_dir,
            public_key_pin_bytes=pin_bytes,
            preauthorization_bytes=body_bytes,
            signature_envelope_bytes=envelope_bytes,
            observed_at=observed_at,
        )
    except Exception as exc:
        raise P0ActualOwnerRootPreauthorizationV2SupervisorError(
            "preauthorization V2 child validation failed"
        ) from exc

    child, safe, truth_sha = _strict_child_receipt(
        child_value,
        pin_raw_sha=pin_raw_sha,
        preauthorization_raw_sha=body_raw_sha,
        envelope_raw_sha=envelope_raw_sha,
        observed_at=observed_at,
    )
    child_full_sha = _canonical_sha256(child)
    step_material = {
        "schema_version": STEP_RECEIPT_SCHEMA,
        "domain": STEP_RECEIPT_DOMAIN,
        "ordinal": 0,
        "operation": EXECUTION_STEP,
        "raw_input_binding_sha256": raw_input_binding_sha,
        "child_receipt_declared_sha256": child["receipt_sha256"],
        "child_receipt_full_sha256": child_full_sha,
        "child_safe_projection_sha256": safe["receipt_sha256"],
        "child_truth_table_projection_sha256": truth_sha,
        "preauthorization_execution_count": 1,
        "direct_windows_execution_count": 0,
    }
    step_candidate = {
        **step_material,
        "receipt_sha256": _canonical_sha256(step_material),
    }
    step = _strict_step_receipt(
        step_candidate,
        raw_input_binding_sha256=raw_input_binding_sha,
        child_receipt_declared_sha256=child["receipt_sha256"],
        child_receipt_full_sha256=child_full_sha,
        child_safe_projection_sha256=safe["receipt_sha256"],
        child_truth_table_projection_sha256=truth_sha,
    )
    material = {
        "schema_version": RECEIPT_SCHEMA,
        "supervisor_component_manifest_sha256": COMPONENT_MANIFEST_SHA256,
        "preauthorization_component_manifest_sha256": (
            PREAUTHORIZATION_COMPONENT_MANIFEST_SHA256
        ),
        "windows_component_manifest_sha256": WINDOWS_COMPONENT_MANIFEST_SHA256,
        "packet_component_manifest_sha256": PACKET_COMPONENT_MANIFEST_SHA256,
        "fixed_member_contract_sha256": FIXED_MEMBER_CONTRACT_SHA256,
        "preauthorization_public_api": PREAUTHORIZATION_PUBLIC_API,
        "packet_dir_input_kind": packet_dir_input_kind,
        "packet_dir_lexical_utf8_sha256": packet_dir_lexical_sha,
        "public_key_pin_bytes_sha256": pin_raw_sha,
        "preauthorization_bytes_sha256": body_raw_sha,
        "signature_envelope_bytes_sha256": envelope_raw_sha,
        "raw_input_binding_sha256": raw_input_binding_sha,
        "observed_at": observed_at,
        "child_receipt_declared_sha256": child["receipt_sha256"],
        "child_receipt_full_sha256": child_full_sha,
        "child_safe_projection": safe,
        "child_safe_projection_sha256": safe["receipt_sha256"],
        "child_truth_table_projection_sha256": truth_sha,
        "execution_step": EXECUTION_STEP,
        "execution_step_count": 1,
        "preauthorization_execution_count": 1,
        "direct_windows_execution_count": 0,
        "execution_step_receipt": step,
        "execution_step_receipt_declared_sha256": step["receipt_sha256"],
        "execution_step_receipt_full_sha256": _canonical_sha256(step),
        **{field: True for field in _SUPERVISOR_TRUE_FIELDS},
        **{field: False for field in _SUPERVISOR_FALSE_FIELDS},
        "credited_actual_source_claim_count": 0,
        "credited_actual_a_context_review_count": 0,
        "operational_effect": OPERATIONAL_EFFECT,
        "gate_status": GATE_STATUS,
    }
    if tuple(material) + ("receipt_sha256",) != _RECEIPT_FIELDS:
        raise P0ActualOwnerRootPreauthorizationV2SupervisorError(
            "internal supervisor receipt field drift"
        )
    return {**material, "receipt_sha256": _canonical_sha256(material)}


__all__ = ["execute_owner_root_preauthorization_v2_supervisor_windows"]
