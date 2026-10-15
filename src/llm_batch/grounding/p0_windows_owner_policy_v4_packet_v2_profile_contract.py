"""Signed owner-policy V4 profile for the packet V2 preauthorization lane.

This additive contract closes the wire-format mismatch between owner policy V3
and the packet V2 preauthorization components.  It validates a presented V3
predecessor through the existing parent contract, an exact packet V2 public-key
pin, and a bootstrap-key signature over the V4 successor profile.  It does not
discover a policy store, establish an external trust anchor, consume a nonce,
observe trusted time/revocation state, touch the filesystem, or grant authority.
"""

from __future__ import annotations

import base64
import binascii
from copy import deepcopy
import dis
import hashlib
import hmac
import inspect
import json
import re
import types
from typing import Any, Mapping

from llm_batch.grounding import p0_actual_owner_root_preauthorization_v2 as preauth_v2
from llm_batch.grounding import (
    p0_actual_owner_root_preauthorization_v2_supervisor as supervisor_v2,
)
from llm_batch.grounding import (
    p0_presented_a_context_annotation_packet_v2_contract as packet_v2,
)
from llm_batch.grounding import (
    p0_presented_a_context_annotation_packet_v2_windows_fixed_directory as windows_v2,
)
from llm_batch.grounding import p0_windows_owner_policy_contract as owner_policy


# Capture the full V3 structural replay functions before any caller-controlled
# test/runtime mutation.  Their module globals are independently pinned below.
_OWNER_POLICY_PARENT_VALIDATOR = (
    owner_policy.validate_presented_windows_owner_policy_contract
)
_OWNER_POLICY_BODY_REPLAY = owner_policy._validate_policy_body
_OWNER_POLICY_SIGNATURE_REPLAY = owner_policy._validate_signature
_OWNER_DEPLOYMENT_MODULE = owner_policy.deployment
_OWNER_OBSERVER_MODULE = owner_policy.observer_profile
_OWNER_OBSERVER_DEPLOYMENT_MODULE = owner_policy.observer_profile.deployment

_OWNER_GRAPH_MODULES = (
    owner_policy,
    owner_policy.deployment,
    owner_policy.observer_profile,
)


def _critical_constant_name(name: str) -> bool:
    return name.isupper() or (
        name.startswith("_")
        and any(
            token in name
            for token in ("FIELDS", "KEYS", "MASK", "ORDER", "ROLES", "SIDS")
        )
    )


_OWNER_GRAPH_CALLABLE_SNAPSHOT = tuple(
    (
        module,
        name,
        value,
        value.__code__,
        value.__defaults__,
        value.__kwdefaults__,
        deepcopy(value.__kwdefaults__),
    )
    for module in _OWNER_GRAPH_MODULES
    for name, value in vars(module).items()
    if inspect.isfunction(value) and value.__module__ == module.__name__
)
_OWNER_GRAPH_CONSTANT_SNAPSHOT = tuple(
    (module, name, type(value), deepcopy(value))
    for module in _OWNER_GRAPH_MODULES
    for name, value in vars(module).items()
    if _critical_constant_name(name) and not inspect.isroutine(value)
)
_OWNER_GRAPH_CALLABLE_NAMES = tuple(
    f"{module.__name__}:{name}"
    for module, name, *_rest in _OWNER_GRAPH_CALLABLE_SNAPSHOT
)
_OWNER_GRAPH_CONSTANT_NAMES = tuple(
    f"{module.__name__}:{name}"
    for module, name, *_rest in _OWNER_GRAPH_CONSTANT_SNAPSHOT
)


def _identity_bound_reference(value: Any) -> bool:
    return isinstance(value, (types.ModuleType, type)) or callable(value)


def _reference_target_label(value: Any) -> str:
    if isinstance(value, types.ModuleType):
        return f"module:{value.__name__}"
    bound_self = getattr(value, "__self__", None)
    bound_name = getattr(value, "__name__", None)
    if bound_self is not None and isinstance(bound_name, str):
        owner_type = bound_self if isinstance(bound_self, type) else type(bound_self)
        return (
            f"bound:{owner_type.__module__}:{owner_type.__qualname__}:"
            f"{bound_name}"
        )
    module = getattr(value, "__module__", None)
    qualname = getattr(value, "__qualname__", None)
    if isinstance(module, str) and isinstance(qualname, str):
        return f"object:{module}:{qualname}"
    if isinstance(value, (str, int, float, bool, type(None), bytes)):
        return f"value:{type(value).__name__}:{value!r}"
    return f"value:{type(value).__module__}:{type(value).__qualname__}"


def _global_value(function: Any, name: str) -> tuple[str, Any]:
    if name in function.__globals__:
        return "global", function.__globals__[name]
    builtins_value = function.__builtins__
    if isinstance(builtins_value, Mapping):
        return "builtin", builtins_value[name]
    return "builtin", getattr(builtins_value, name)


def _build_reference_graph() -> tuple[tuple[Any, ...], tuple[Any, ...], tuple[Any, ...]]:
    globals_seen: set[tuple[int, str, str]] = set()
    attributes_seen: set[tuple[int, int, str]] = set()
    deref_seen: set[tuple[int, str]] = set()
    global_rows: list[tuple[Any, ...]] = []
    attribute_rows: list[tuple[Any, ...]] = []
    deref_rows: list[tuple[Any, ...]] = []
    for module, name, function, *_rest in _OWNER_GRAPH_CALLABLE_SNAPSHOT:
        function_label = f"{module.__name__}:{name}"
        instructions = tuple(dis.get_instructions(function))
        closure = {
            free_name: cell.cell_contents
            for free_name, cell in zip(
                function.__code__.co_freevars, function.__closure__ or (), strict=True
            )
        }
        for index, instruction in enumerate(instructions):
            if instruction.opname == "LOAD_GLOBAL":
                source, value = _global_value(function, instruction.argval)
                key = (id(function), source, instruction.argval)
                if key not in globals_seen:
                    globals_seen.add(key)
                    global_rows.append((
                        function, function_label, source, instruction.argval,
                        value, type(value),
                        None if _identity_bound_reference(value) else deepcopy(value),
                    ))
            elif instruction.opname == "LOAD_DEREF":
                if instruction.argval not in closure:
                    continue
                value = closure[instruction.argval]
                key = (id(function), instruction.argval)
                if key not in deref_seen:
                    deref_seen.add(key)
                    deref_rows.append((
                        function, function_label, instruction.argval, value,
                        type(value),
                        None if _identity_bound_reference(value) else deepcopy(value),
                    ))
            else:
                continue
            current = value
            current_path = instruction.argval
            cursor = index + 1
            while cursor < len(instructions) and instructions[cursor].opname in {
                "LOAD_ATTR", "LOAD_METHOD",
            }:
                attribute = instructions[cursor].argval
                target = getattr(current, attribute)
                key = (id(function), id(current), attribute)
                if key not in attributes_seen:
                    attributes_seen.add(key)
                    static_target = inspect.getattr_static(current, attribute)
                    attribute_rows.append((
                        function_label, current_path, current, attribute,
                        target, type(target),
                        None if _identity_bound_reference(target) else deepcopy(target),
                        static_target, type(static_target),
                        None
                        if _identity_bound_reference(static_target)
                        else deepcopy(static_target),
                    ))
                current = target
                current_path = f"{current_path}.{attribute}"
                cursor += 1
    return tuple(global_rows), tuple(attribute_rows), tuple(deref_rows)


(
    _OWNER_GRAPH_GLOBAL_REFERENCE_SNAPSHOT,
    _OWNER_GRAPH_ATTRIBUTE_REFERENCE_SNAPSHOT,
    _OWNER_GRAPH_DEREF_REFERENCE_SNAPSHOT,
) = _build_reference_graph()

_OWNER_GRAPH_REFERENCE_DESCRIPTOR = {
    "globals": tuple(
        f"{function_label}:{source}:{name}->{_reference_target_label(value)}"
        for _function, function_label, source, name, value, *_rest
        in _OWNER_GRAPH_GLOBAL_REFERENCE_SNAPSHOT
    ),
    "attributes": tuple(
        f"{function_label}:{path}.{attribute}->{_reference_target_label(target)}"
        for function_label, path, _owner, attribute, target, *_rest
        in _OWNER_GRAPH_ATTRIBUTE_REFERENCE_SNAPSHOT
    ),
    "derefs": tuple(
        f"{function_label}:{name}->{_reference_target_label(value)}"
        for _function, function_label, name, value, *_rest
        in _OWNER_GRAPH_DEREF_REFERENCE_SNAPSHOT
    ),
}
_OWNER_GRAPH_REFERENCE_DESCRIPTOR_SHA256 = hashlib.sha256(
    json.dumps(
        _OWNER_GRAPH_REFERENCE_DESCRIPTOR,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
).hexdigest()

def _referenced_function_snapshot() -> tuple[tuple[Any, ...], ...]:
    result: list[tuple[Any, ...]] = []
    seen: set[int] = set()
    values = (
        [row[4] for row in _OWNER_GRAPH_GLOBAL_REFERENCE_SNAPSHOT]
        + [row[4] for row in _OWNER_GRAPH_ATTRIBUTE_REFERENCE_SNAPSHOT]
        + [row[3] for row in _OWNER_GRAPH_DEREF_REFERENCE_SNAPSHOT]
    )
    for value in values:
        if not inspect.isfunction(value) or id(value) in seen:
            continue
        seen.add(id(value))
        result.append((
            value, value.__code__, value.__defaults__, value.__kwdefaults__,
            deepcopy(value.__kwdefaults__),
        ))
    return tuple(result)


_OWNER_GRAPH_REFERENCED_FUNCTION_SNAPSHOT = _referenced_function_snapshot()


def _attribute_reference_matches(
    owner: Any,
    attribute: str,
    live: Any,
    expected: Any,
    expected_type: type,
    expected_value: Any,
    expected_static: Any,
    expected_static_type: type,
    expected_static_value: Any,
) -> bool:
    """Compare an attribute without rejecting fresh bound-method wrappers."""

    if type(live) is not expected_type:
        return False
    expected_self = getattr(expected, "__self__", None)
    if callable(expected) and expected_self is owner:
        if (
            getattr(live, "__self__", None) is not owner
            or getattr(live, "__name__", None)
            != getattr(expected, "__name__", None)
            or getattr(live, "__qualname__", None)
            != getattr(expected, "__qualname__", None)
        ):
            return False
        expected_function = getattr(expected, "__func__", None)
        if expected_function is not None and (
            getattr(live, "__func__", None) is not expected_function
        ):
            return False
        live_static = inspect.getattr_static(owner, attribute)
        if type(live_static) is not expected_static_type:
            return False
        return (
            live_static is expected_static
            if _identity_bound_reference(expected_static)
            else live_static == expected_static_value
        )
    return (
        live is expected
        if _identity_bound_reference(expected)
        else live == expected_value
    )


POLICY_BODY_SCHEMA = "p0_windows_external_owner_policy_body_v4"
PROFILE_SCHEMA = "p0_windows_owner_policy_v4_packet_v2_preauthorization_profile_v1"
POLICY_SIGNATURE_SCHEMA = "p0_windows_external_owner_policy_signature_v4"
RECEIPT_SCHEMA = "p0_windows_owner_policy_v4_packet_v2_profile_receipt_v1"
POLICY_DOMAIN = "llm_novel_dc/p0/windows-external-owner-policy/v4"
POLICY_ORIGIN = "EXTERNAL_OWNER_POLICY_RECORD"
SIGNATURE_ORIGIN = "EXTERNAL_OWNER_POLICY_DETACHED_SIGNATURE_RECORD"
PROFILE_DOMAIN = (
    "llm-novel-dc-community-parser/owner-policy-v4/"
    "packet-v2-preauthorization-profile/v1"
)
SIGNATURE_DOMAIN = "llm_novel_dc/p0/windows-owner-policy-signature/v4"
OWNER_ANCHOR_DOMAIN_V4 = (
    "llm-novel-dc-community-parser/owner-policy-v4/owner-anchor/v1"
)
SIGNATURE_ALGORITHM = "ECDSA_P256_SHA256_IEEE_P1363_LOW_S"
PACKET_PUBLIC_KEY_PIN_SCHEMA = "p0_actual_owner_root_public_key_pin_v2"
PACKET_PREAUTHORIZATION_ALGORITHM = "ECDSA_P256_SHA256_CNG_P1363_LOW_S_V2"
PACKET_PREAUTHORIZATION_SIGNATURE_DOMAIN = (
    "llm-novel-dc-community-parser/owner-root-preauthorization-v2/signature/v1"
)
PACKET_PREAUTHORIZATION_PURPOSE = (
    "OWNER_SIGNED_PACKET_V2_WINDOWS_COMPONENT_ONLY_PREFLIGHT"
)
PACKET_PIN_ORIGIN = "CALLER_PRESENTED_UNTRUSTED_PUBLIC_KEY_PIN"
PACKET_CURVE = "NIST_P256"
PACKET_COORDINATE_ENCODING = "BASE64_RAW_32_BYTE_BIG_ENDIAN_X_AND_Y"
PACKET_FINGERPRINT_ENCODING = "SHA256_RFC5480_DER_SPKI"
PACKET_OWNER_ANCHOR_DOMAIN = (
    "llm-novel-dc-community-parser/owner-root-preauthorization-v2/owner-anchor/v1"
)
OPERATIONAL_EFFECT = "NONE_SHADOW_ONLY"
GATE_STATUS = "NO_GO_SIGNED_OWNER_POLICY_V4_PACKET_V2_PROFILE_ONLY"
PREDECESSOR_GATE_STATUS = (
    "OWNER_POLICY_CONTRACT_PASS_BOOTSTRAP_AND_PROVISIONING_NO_GO"
)
PREDECESSOR_POLICY_BODY_SCHEMA = "p0_windows_external_owner_policy_body_v3"
PREDECESSOR_POLICY_SIGNATURE_SCHEMA = (
    "p0_windows_external_owner_policy_signature_v3"
)
PREDECESSOR_RECEIPT_SCHEMA = "p0_windows_owner_policy_contract_receipt_v3"
PREDECESSOR_POLICY_DOMAIN = "llm_novel_dc/p0/windows-external-owner-policy/v3"
PREDECESSOR_SIGNATURE_DOMAIN = "llm_novel_dc/p0/windows-owner-policy-signature/v3"

PACKET_COMPONENT_MANIFEST_SHA256 = (
    "2a4b63518b8d80522469753191c9879af6f85f55828f28318a149911e564d59f"
)
WINDOWS_COMPONENT_MANIFEST_SHA256 = (
    "4e4e5c76fd3fd210a5e3c381243dccec623f2c0a48afbba6e52667d38afaae02"
)
PREAUTHORIZATION_COMPONENT_MANIFEST_SHA256 = (
    "07ae0af427112978ba3cb5f5a0ae8713a25837cbb9ae65ac0b7993da7d44876e"
)
SUPERVISOR_COMPONENT_MANIFEST_SHA256 = (
    "239b595763bf1bef0d5ab925d51f864f1c1c3090123f6ca540a225e4f9c4fddf"
)
FIXED_MEMBER_CONTRACT_SHA256 = (
    "37f3a34ab17c219065b81d9f2eb3d9a8876c5e32e12e7051ec30f3e5038385fc"
)

MAX_PREAUTHORIZATION_TTL_SECONDS = 300
_MAX_POLICY_BYTES = 256_000
_MAX_SIGNATURE_BYTES = 64_000
_MAX_PIN_BYTES = 64_000
_P256_ORDER = int(
    "FFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551",
    16,
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,255}$")

_PIN_FIELDS = tuple(sorted({
    "schema_version", "record_origin", "trust_domain", "project_id",
    "environment", "purpose", "key_id", "key_epoch", "algorithm", "curve",
    "coordinate_encoding", "fingerprint_encoding", "public_key_x_base64",
    "public_key_y_base64", "public_key_fingerprint_sha256",
    "owner_principal_sha256", "owner_anchor_sha256",
    "allowed_signature_domains", "artifact_sha256",
}))

_REQUIRED_CAPABILITY_FIELDS = (
    "trusted_time_required",
    "revocation_high_watermark_required",
    "durable_nonce_required",
    "external_root_authority_required",
    "external_code_authority_required",
    "os_write_deny_required",
    "actual_semantic_evidence_required",
)
_PROFILE_FALSE_FIELDS = (
    "external_public_key_pin_provisioning_verified",
    "zero_input_policy_store_observed",
    "positive_provisioning_complete",
    "owner_authority_verified",
    "actual_authority_granted",
    "public_apply_allowed",
    "wal_write_allowed",
    "central_slang_db_write_allowed",
    "production_approval",
    "full_scan_approval",
    "p0_phase_exit",
    "action_applied",
)
_PROFILE_FIELDS = tuple(sorted({
    "schema_version",
    "domain",
    "public_key_pin_schema",
    "public_key_pin_bytes_sha256",
    "public_key_pin_artifact_sha256",
    "public_key_fingerprint_sha256",
    "key_id",
    "key_epoch",
    "preauthorization_algorithm",
    "preauthorization_signature_domain",
    "packet_component_manifest_sha256",
    "windows_component_manifest_sha256",
    "preauthorization_component_manifest_sha256",
    "supervisor_component_manifest_sha256",
    "fixed_member_contract_sha256",
    "max_preauthorization_ttl_seconds",
    "min_revocation_sequence",
    "packet_v2_purpose",
    "owner_principal_sha256",
    "public_key_pin_owner_anchor_sha256",
    *_REQUIRED_CAPABILITY_FIELDS,
    *_PROFILE_FALSE_FIELDS,
    "profile_artifact_sha256",
}))
_BODY_FIELDS = tuple(sorted({
    "schema_version",
    "record_origin",
    "domain",
    "policy_id",
    "policy_epoch",
    "predecessor_policy_v3_bytes_sha256",
    "predecessor_policy_v3_epoch",
    "predecessor_policy_v3_artifact_sha256",
    "predecessor_policy_v3_signature_bytes_sha256",
    "predecessor_policy_v3_signature_artifact_sha256",
    "predecessor_contract_receipt_sha256",
    "project_id",
    "trust_domain",
    "environment",
    "policy_purpose",
    "bootstrap_key_id",
    "bootstrap_public_key_fingerprint_sha256",
    "owner_principal_sha256",
    "packet_v2_owner_anchor_sha256",
    "owner_anchor_sha256",
    "packet_v2_preauthorization_profile",
    "operational_effect",
    "gate_status",
    "artifact_sha256",
}))
_SIGNATURE_FIELDS = tuple(sorted({
    "schema_version",
    "record_origin",
    "domain",
    "algorithm",
    "policy_body_schema",
    "policy_body_bytes_sha256",
    "policy_body_artifact_sha256",
    "policy_id",
    "policy_epoch",
    "predecessor_policy_v3_bytes_sha256",
    "predecessor_policy_v3_epoch",
    "predecessor_policy_v3_artifact_sha256",
    "predecessor_policy_v3_signature_bytes_sha256",
    "predecessor_policy_v3_signature_artifact_sha256",
    "predecessor_contract_receipt_sha256",
    "bootstrap_key_id",
    "bootstrap_public_key_fingerprint_sha256",
    "profile_artifact_sha256",
    "owner_anchor_sha256",
    "signature_rs_base64",
    "artifact_sha256",
}))
_RECEIPT_FALSE_FIELDS = (
    "predecessor_bootstrap_signature_mathematics_verified",
    "bootstrap_public_key_independently_pinned",
    "external_public_key_pin_provisioning_verified",
    "zero_input_policy_store_observed",
    "positive_provisioning_complete",
    "trusted_time_verified",
    "revocation_high_watermark_verified",
    "durable_nonce_state_verified",
    "external_root_authority_verified",
    "external_code_authority_verified",
    "os_write_deny_verified",
    "actual_semantic_evidence_verified",
    "owner_authority_verified",
    "actual_authority_granted",
    "public_apply_allowed",
    "wal_write_allowed",
    "central_slang_db_write_allowed",
    "production_approval",
    "full_scan_approval",
    "p0_phase_exit",
    "action_applied",
    "protected_pipeline_state_mutated",
)
_RECEIPT_TRUE_FIELDS = (
    "predecessor_v3_parent_contract_validated",
    "predecessor_v3_parent_receipt_exactly_validated",
    "predecessor_v3_full_structural_replay_verified",
    "predecessor_v3_receipt_independently_reconstructed",
    "predecessor_body_signature_receipt_bound",
    "packet_v2_public_key_pin_contract_validated",
    "packet_v2_public_key_curve_point_verified",
    "packet_v2_owner_principal_cross_binding_verified",
    "packet_v2_owner_anchor_cross_binding_verified",
    "packet_key_four_role_separation_verified",
    "bounded_monotonic_epoch_profile_verified",
    "profile_artifact_self_hash_verified",
    "owner_anchor_v4_recomputed_verified",
    "exact_v2_algorithm_and_signature_domain_bound",
    "exact_component_pin_set_bound",
    "dependency_declared_recomputed_live_pins_verified",
    "scope_and_purpose_cross_binding_verified",
    "canonical_low_s_signature_verified",
    "successor_bootstrap_signature_mathematics_verified",
    "downstream_requirement_truth_table_bound",
)
_RECEIPT_PREFIX_FIELDS = (
    "schema_version", "component_manifest_sha256",
    "predecessor_policy_v3_bytes_sha256",
    "predecessor_policy_v3_artifact_sha256",
    "predecessor_policy_v3_signature_bytes_sha256",
    "predecessor_policy_v3_signature_artifact_sha256",
    "predecessor_policy_v3_epoch", "predecessor_contract_receipt_sha256",
    "policy_v4_body_bytes_sha256", "policy_v4_body_artifact_sha256",
    "policy_v4_signature_bytes_sha256", "policy_v4_signature_artifact_sha256",
    "signature_input_sha256", "packet_v2_public_key_pin_bytes_sha256",
    "packet_v2_public_key_pin_artifact_sha256",
    "packet_v2_public_key_fingerprint_sha256",
    "packet_v2_owner_principal_sha256", "packet_v2_owner_anchor_sha256",
    "packet_v2_key_id", "packet_v2_key_epoch", "policy_id", "policy_epoch",
    "project_id", "trust_domain", "environment", "policy_purpose",
    "packet_v2_purpose", "profile_artifact_sha256", "owner_anchor_sha256",
    "max_preauthorization_ttl_seconds", "min_revocation_sequence",
)
_RECEIPT_FIELDS = (
    *_RECEIPT_PREFIX_FIELDS, *_RECEIPT_TRUE_FIELDS, *_RECEIPT_FALSE_FIELDS,
    "credited_actual_source_claim_count", "credited_actual_a_context_review_count",
    "operational_effect", "gate_status", "receipt_sha256",
)

_PREDECESSOR_RECEIPT_FIELDS = (
    "schema_version", "gate_status", "policy_id", "policy_epoch",
    "policy_body_bytes_sha256", "policy_body_artifact_sha256",
    "policy_signature_bytes_sha256", "policy_signature_artifact_sha256",
    "store_id", "owner_principal_sha256", "owner_anchor_sha256",
    "owner_anchor_scope", "owner_anchor_excludes_pin_transport_hashes_by_design",
    "full_policy_identity_sha256", "acl_template_sha256",
    "operational_key_projection_sha256", "object_identity_projection_sha256",
    "security_template_sha256_by_role",
    "strict_canonical_policy_body_verified",
    "strict_canonical_detached_signature_envelope_verified",
    "owner_and_verifier_sid_disjoint_contract_verified",
    "fixed_generation_layout_contract_verified",
    "exact_standard_explicit_ace_profile_contract_verified",
    "derived_owner_anchor_cross_binding_verified",
    "detached_signature_body_hash_cross_binding_verified",
    "bootstrap_signature_mathematics_verified",
    "bootstrap_public_key_independently_pinned",
    "fixed_policy_store_discovery_verified", "live_windows_binary_acl_verified",
    "effective_verifier_token_verified", "linked_elevated_token_absence_verified",
    "independent_owner_policy_state_verified",
    "external_public_key_pin_provisioning_verified", "trusted_time_verified",
    "revocation_current_verified", "rollback_resistant_policy_epoch_verified",
    "rollback_resistant_key_epoch_verified", "durable_nonce_state_verified",
    "external_code_authority_verified", "owner_authority_verified",
    "actual_authority_granted", "actual_semantic_evidence_verified",
    "production_approval", "full_scan_approval", "p0_phase_exit",
    "action_applied", "policy_schema_version", "policy_domain",
    "signature_schema_version", "signature_domain",
    "deployment_projection_sha256", "native_observer_profile_sha256",
    "deployment_projection_contract_verified",
    "native_observer_profile_contract_verified",
    "policy_verifier_sid_deployment_service_sid_cross_binding_verified",
    "policy_deployment_native_observer_profile_cross_binding_verified",
    "operational_and_observer_key_role_separation_contract_verified",
    "future_native_observer_authority_requires_v3",
    "future_authority_policy_version_eligible",
    "positive_native_observer_policy_profile_complete", "receipt_sha256",
)
_PREDECESSOR_RECEIPT_TRUE_FIELDS = (
    "owner_anchor_excludes_pin_transport_hashes_by_design",
    "strict_canonical_policy_body_verified",
    "strict_canonical_detached_signature_envelope_verified",
    "owner_and_verifier_sid_disjoint_contract_verified",
    "fixed_generation_layout_contract_verified",
    "exact_standard_explicit_ace_profile_contract_verified",
    "derived_owner_anchor_cross_binding_verified",
    "detached_signature_body_hash_cross_binding_verified",
    "deployment_projection_contract_verified",
    "native_observer_profile_contract_verified",
    "policy_verifier_sid_deployment_service_sid_cross_binding_verified",
    "policy_deployment_native_observer_profile_cross_binding_verified",
    "operational_and_observer_key_role_separation_contract_verified",
    "future_native_observer_authority_requires_v3",
)
_PREDECESSOR_RECEIPT_FALSE_FIELDS = (
    "bootstrap_signature_mathematics_verified",
    "bootstrap_public_key_independently_pinned",
    "fixed_policy_store_discovery_verified",
    "live_windows_binary_acl_verified",
    "effective_verifier_token_verified",
    "linked_elevated_token_absence_verified",
    "independent_owner_policy_state_verified",
    "external_public_key_pin_provisioning_verified",
    "trusted_time_verified",
    "revocation_current_verified",
    "rollback_resistant_policy_epoch_verified",
    "rollback_resistant_key_epoch_verified",
    "durable_nonce_state_verified",
    "external_code_authority_verified",
    "owner_authority_verified",
    "actual_authority_granted",
    "actual_semantic_evidence_verified",
    "production_approval",
    "full_scan_approval",
    "p0_phase_exit",
    "action_applied",
    "future_authority_policy_version_eligible",
    "positive_native_observer_policy_profile_complete",
)


class P0WindowsOwnerPolicyV4PacketV2ProfileError(ValueError):
    """The presented V4 successor profile could not fail closed."""


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    return value


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        _plain(value), ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def json_file_bytes(value: Mapping[str, Any]) -> bytes:
    return canonical_bytes(value) + b"\n"


def with_artifact_hash(value: Mapping[str, Any]) -> dict[str, Any]:
    material = {key: _plain(item) for key, item in value.items() if key != "artifact_sha256"}
    return {**material, "artifact_sha256": canonical_sha256(material)}


def _duplicate_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise P0WindowsOwnerPolicyV4PacketV2ProfileError(
                f"duplicate JSON key: {key}"
            )
        result[key] = value
    return result


def _reject_nonfinite(token: str) -> None:
    raise P0WindowsOwnerPolicyV4PacketV2ProfileError(
        f"non-finite JSON constant is forbidden: {token}"
    )


def _parse(raw: Any, *, cap: int, label: str) -> dict[str, Any]:
    if (
        type(raw) is not bytes or not raw or len(raw) > cap
        or raw.startswith(b"\xef\xbb\xbf")
    ):
        raise P0WindowsOwnerPolicyV4PacketV2ProfileError(
            f"{label} must be bounded exact UTF-8 bytes without BOM"
        )
    try:
        value = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=_duplicate_object,
            parse_constant=_reject_nonfinite,
        )
    except (UnicodeError, ValueError, TypeError, RecursionError) as exc:
        raise P0WindowsOwnerPolicyV4PacketV2ProfileError(
            f"{label} is not strict JSON"
        ) from exc
    if type(value) is not dict or json_file_bytes(value) != raw:
        raise P0WindowsOwnerPolicyV4PacketV2ProfileError(
            f"{label} must be one canonical JSON object plus LF"
        )
    return value


def _strict(row: Any, fields: tuple[str, ...], label: str) -> dict[str, Any]:
    if type(row) is not dict or tuple(row) != fields or any(type(key) is not str for key in row):
        raise P0WindowsOwnerPolicyV4PacketV2ProfileError(
            f"{label} exact ordered fields mismatch"
        )
    return dict(row)


def _sha(value: Any, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise P0WindowsOwnerPolicyV4PacketV2ProfileError(
            f"{label} must be lowercase SHA-256"
        )
    return value


def _identifier(value: Any, label: str) -> str:
    if type(value) is not str or _IDENTIFIER.fullmatch(value) is None:
        raise P0WindowsOwnerPolicyV4PacketV2ProfileError(f"{label} is invalid")
    return value


def _positive_bounded_int(value: Any, label: str) -> int:
    if type(value) is not int or not 1 <= value <= 2**63 - 1:
        raise P0WindowsOwnerPolicyV4PacketV2ProfileError(
            f"{label} must be exact int in 1..2^63-1"
        )
    return value


def _self_hash(row: Mapping[str, Any], label: str) -> str:
    declared = _sha(row.get("artifact_sha256"), f"{label}.artifact_sha256")
    material = dict(row)
    material.pop("artifact_sha256", None)
    if not hmac.compare_digest(declared, canonical_sha256(material)):
        raise P0WindowsOwnerPolicyV4PacketV2ProfileError(
            f"{label}.artifact_sha256 mismatch"
        )
    return declared


def _profile_self_hash(row: Mapping[str, Any]) -> str:
    declared = _sha(
        row.get("profile_artifact_sha256"),
        "packet_v2_preauthorization_profile.profile_artifact_sha256",
    )
    material = dict(row)
    material.pop("profile_artifact_sha256", None)
    if not hmac.compare_digest(declared, canonical_sha256(material)):
        raise P0WindowsOwnerPolicyV4PacketV2ProfileError(
            "packet V2 profile artifact SHA mismatch"
        )
    return declared


def _decode_signature(value: Any) -> bytes:
    if type(value) is not str or not value or any(ch.isspace() for ch in value):
        raise P0WindowsOwnerPolicyV4PacketV2ProfileError(
            "signature_rs_base64 must be canonical Base64"
        )
    try:
        raw = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise P0WindowsOwnerPolicyV4PacketV2ProfileError(
            "signature_rs_base64 must be canonical Base64"
        ) from exc
    if len(raw) != 64 or base64.b64encode(raw).decode("ascii") != value:
        raise P0WindowsOwnerPolicyV4PacketV2ProfileError(
            "signature must be an exact 64-byte P1363 value"
        )
    r = int.from_bytes(raw[:32], "big")
    s = int.from_bytes(raw[32:], "big")
    if not 0 < r < _P256_ORDER or not 0 < s <= _P256_ORDER // 2:
        raise P0WindowsOwnerPolicyV4PacketV2ProfileError(
            "signature must contain bounded low-S P-256 scalars"
        )
    return raw


def _assert_owner_graph_integrity() -> None:
    """Detect runtime mutation across the complete V3 validation graph."""

    try:
        if (
            owner_policy.validate_presented_windows_owner_policy_contract
            is not _OWNER_POLICY_PARENT_VALIDATOR
            or owner_policy._validate_policy_body is not _OWNER_POLICY_BODY_REPLAY
            or owner_policy._validate_signature is not _OWNER_POLICY_SIGNATURE_REPLAY
            or owner_policy.deployment is not _OWNER_DEPLOYMENT_MODULE
            or owner_policy.observer_profile is not _OWNER_OBSERVER_MODULE
            or owner_policy.observer_profile.deployment
            is not _OWNER_OBSERVER_DEPLOYMENT_MODULE
        ):
            raise P0WindowsOwnerPolicyV4PacketV2ProfileError(
                "predecessor validator public/private callable identity drift"
            )
        for (
            module, name, original, code, defaults, kwdefaults,
            kwdefaults_value,
        ) in _OWNER_GRAPH_CALLABLE_SNAPSHOT:
            live = getattr(module, name)
            if (
                live is not original
                or live.__code__ is not code
                or live.__defaults__ is not defaults
                or live.__kwdefaults__ is not kwdefaults
                or live.__kwdefaults__ != kwdefaults_value
            ):
                raise P0WindowsOwnerPolicyV4PacketV2ProfileError(
                    f"predecessor validator graph callable drift: {module.__name__}:{name}"
                )
        for module, name, expected_type, expected_value in (
            _OWNER_GRAPH_CONSTANT_SNAPSHOT
        ):
            live = getattr(module, name)
            if type(live) is not expected_type or live != expected_value:
                raise P0WindowsOwnerPolicyV4PacketV2ProfileError(
                    f"predecessor validator graph constant drift: {module.__name__}:{name}"
                )
        for (
            function, function_label, source, name, expected,
            expected_type, expected_value,
        ) in _OWNER_GRAPH_GLOBAL_REFERENCE_SNAPSHOT:
            live_source, live = _global_value(function, name)
            if (
                live_source != source
                or type(live) is not expected_type
                or (
                    live is not expected
                    if _identity_bound_reference(expected)
                    else live != expected_value
                )
            ):
                raise P0WindowsOwnerPolicyV4PacketV2ProfileError(
                    f"predecessor validator referenced global drift: {function_label}:{name}"
                )
        for (
            function_label, path, owner, attribute, expected,
            expected_type, expected_value, expected_static,
            expected_static_type, expected_static_value,
        ) in _OWNER_GRAPH_ATTRIBUTE_REFERENCE_SNAPSHOT:
            live = getattr(owner, attribute)
            if not _attribute_reference_matches(
                owner,
                attribute,
                live,
                expected,
                expected_type,
                expected_value,
                expected_static,
                expected_static_type,
                expected_static_value,
            ):
                raise P0WindowsOwnerPolicyV4PacketV2ProfileError(
                    f"predecessor validator referenced attribute drift: {function_label}:{path}.{attribute}"
                )
        for (
            function, function_label, name, expected, expected_type,
            expected_value,
        ) in _OWNER_GRAPH_DEREF_REFERENCE_SNAPSHOT:
            closure = dict(zip(
                function.__code__.co_freevars,
                function.__closure__ or (),
                strict=True,
            ))
            live = closure[name].cell_contents
            if (
                type(live) is not expected_type
                or (
                    live is not expected
                    if _identity_bound_reference(expected)
                    else live != expected_value
                )
            ):
                raise P0WindowsOwnerPolicyV4PacketV2ProfileError(
                    f"predecessor validator referenced closure drift: {function_label}:{name}"
                )
        for function, code, defaults, kwdefaults, kwdefaults_value in (
            _OWNER_GRAPH_REFERENCED_FUNCTION_SNAPSHOT
        ):
            if (
                function.__code__ is not code
                or function.__defaults__ is not defaults
                or function.__kwdefaults__ is not kwdefaults
                or function.__kwdefaults__ != kwdefaults_value
            ):
                raise P0WindowsOwnerPolicyV4PacketV2ProfileError(
                    "predecessor validator referenced function code/default drift"
                )
    except P0WindowsOwnerPolicyV4PacketV2ProfileError:
        raise
    except (KeyError, TypeError, AttributeError, ValueError) as exc:
        raise P0WindowsOwnerPolicyV4PacketV2ProfileError(
            "predecessor validator graph integrity check failed"
        ) from exc


def _assert_dependency_pins() -> None:
    """Check local declarations, dependency declarations, and live manifests."""

    try:
        _assert_owner_graph_integrity()
        if (
            canonical_sha256(COMPONENT_MANIFEST) != COMPONENT_MANIFEST_SHA256
            or COMPONENT_MANIFEST_SHA256 != EXPECTED_COMPONENT_MANIFEST_SHA256
        ):
            raise P0WindowsOwnerPolicyV4PacketV2ProfileError(
                "V4 component manifest integrity mismatch"
            )
        own_expected = {
            ("schemas", "policy_body"): POLICY_BODY_SCHEMA,
            ("schemas", "profile"): PROFILE_SCHEMA,
            ("schemas", "policy_signature"): POLICY_SIGNATURE_SCHEMA,
            ("schemas", "receipt"): RECEIPT_SCHEMA,
            ("origins", "policy"): POLICY_ORIGIN,
            ("origins", "signature"): SIGNATURE_ORIGIN,
            ("domains", "policy"): POLICY_DOMAIN,
            ("domains", "profile"): PROFILE_DOMAIN,
            ("domains", "signature"): SIGNATURE_DOMAIN,
            ("domains", "owner_anchor_v4"): OWNER_ANCHOR_DOMAIN_V4,
            ("domains", "packet_v2_signature"): PACKET_PREAUTHORIZATION_SIGNATURE_DOMAIN,
            ("algorithms", "bootstrap_signature"): SIGNATURE_ALGORITHM,
            ("algorithms", "packet_v2_preauthorization"): PACKET_PREAUTHORIZATION_ALGORITHM,
            ("predecessor_contract", "policy_body_schema"): PREDECESSOR_POLICY_BODY_SCHEMA,
            ("predecessor_contract", "policy_signature_schema"): PREDECESSOR_POLICY_SIGNATURE_SCHEMA,
            ("predecessor_contract", "receipt_schema"): PREDECESSOR_RECEIPT_SCHEMA,
            ("predecessor_contract", "policy_domain"): PREDECESSOR_POLICY_DOMAIN,
            ("predecessor_contract", "signature_domain"): PREDECESSOR_SIGNATURE_DOMAIN,
            ("predecessor_contract", "gate_status"): PREDECESSOR_GATE_STATUS,
        }
        if any(
            COMPONENT_MANIFEST[group][field] != expected
            for (group, field), expected in own_expected.items()
        ) or (
            COMPONENT_MANIFEST["packet_v2_public_key_pin_schema"]
            != PACKET_PUBLIC_KEY_PIN_SCHEMA
            or COMPONENT_MANIFEST["packet_v2_purpose"]
            != PACKET_PREAUTHORIZATION_PURPOSE
            or COMPONENT_MANIFEST["packet_v2_pin_semantics"]["record_origin"]
            != PACKET_PIN_ORIGIN
            or COMPONENT_MANIFEST["packet_v2_pin_semantics"]["curve"]
            != PACKET_CURVE
            or COMPONENT_MANIFEST["packet_v2_pin_semantics"]["coordinate_encoding"]
            != PACKET_COORDINATE_ENCODING
            or COMPONENT_MANIFEST["packet_v2_pin_semantics"]["fingerprint_encoding"]
            != PACKET_FINGERPRINT_ENCODING
            or COMPONENT_MANIFEST["packet_v2_pin_semantics"]["owner_anchor_domain"]
            != PACKET_OWNER_ANCHOR_DOMAIN
            or tuple(COMPONENT_MANIFEST["packet_v2_pin_semantics"]["fields"])
            != _PIN_FIELDS
            or COMPONENT_MANIFEST["max_preauthorization_ttl_seconds"]
            != MAX_PREAUTHORIZATION_TTL_SECONDS
            or COMPONENT_MANIFEST["operational_effect"] != OPERATIONAL_EFFECT
            or COMPONENT_MANIFEST["gate_status"] != GATE_STATUS
            or tuple(COMPONENT_MANIFEST["body_fields"]) != _BODY_FIELDS
            or tuple(COMPONENT_MANIFEST["profile_fields"]) != _PROFILE_FIELDS
            or tuple(COMPONENT_MANIFEST["signature_fields"]) != _SIGNATURE_FIELDS
            or tuple(COMPONENT_MANIFEST["required_capability_fields"])
            != _REQUIRED_CAPABILITY_FIELDS
            or tuple(COMPONENT_MANIFEST["profile_false_fields"])
            != _PROFILE_FALSE_FIELDS
            or tuple(COMPONENT_MANIFEST["receipt_fields"])
            != _RECEIPT_FIELDS
            or tuple(COMPONENT_MANIFEST["receipt_true_fields"])
            != _RECEIPT_TRUE_FIELDS
            or tuple(COMPONENT_MANIFEST["receipt_false_fields"])
            != _RECEIPT_FALSE_FIELDS
            or tuple(COMPONENT_MANIFEST["predecessor_receipt_fields"])
            != _PREDECESSOR_RECEIPT_FIELDS
            or tuple(COMPONENT_MANIFEST["predecessor_receipt_true_fields"])
            != _PREDECESSOR_RECEIPT_TRUE_FIELDS
            or tuple(COMPONENT_MANIFEST["predecessor_receipt_false_fields"])
            != _PREDECESSOR_RECEIPT_FALSE_FIELDS
            or tuple(COMPONENT_MANIFEST["predecessor_contract"][
                "validator_graph_callable_names"
            ]) != _OWNER_GRAPH_CALLABLE_NAMES
            or tuple(COMPONENT_MANIFEST["predecessor_contract"][
                "validator_graph_constant_names"
            ]) != _OWNER_GRAPH_CONSTANT_NAMES
            or tuple(COMPONENT_MANIFEST["predecessor_contract"][
                "validator_graph_global_references"
            ]) != _OWNER_GRAPH_REFERENCE_DESCRIPTOR["globals"]
            or tuple(COMPONENT_MANIFEST["predecessor_contract"][
                "validator_graph_attribute_references"
            ]) != _OWNER_GRAPH_REFERENCE_DESCRIPTOR["attributes"]
            or tuple(COMPONENT_MANIFEST["predecessor_contract"][
                "validator_graph_deref_references"
            ]) != _OWNER_GRAPH_REFERENCE_DESCRIPTOR["derefs"]
            or COMPONENT_MANIFEST["predecessor_contract"][
                "validator_graph_reference_descriptor_sha256"
            ] != _OWNER_GRAPH_REFERENCE_DESCRIPTOR_SHA256
            or hashlib.sha256(json.dumps(
                _OWNER_GRAPH_REFERENCE_DESCRIPTOR,
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")).hexdigest()
            != _OWNER_GRAPH_REFERENCE_DESCRIPTOR_SHA256
        ):
            raise P0WindowsOwnerPolicyV4PacketV2ProfileError(
                "V4 semantic constants do not match the sealed component manifest"
            )
        if (
            owner_policy.POLICY_BODY_SCHEMA_V3 != PREDECESSOR_POLICY_BODY_SCHEMA
            or owner_policy.POLICY_SIGNATURE_SCHEMA_V3
            != PREDECESSOR_POLICY_SIGNATURE_SCHEMA
            or owner_policy.CONTRACT_RECEIPT_SCHEMA_V3 != PREDECESSOR_RECEIPT_SCHEMA
            or owner_policy.POLICY_DOMAIN_V3 != PREDECESSOR_POLICY_DOMAIN
            or owner_policy.SIGNATURE_DOMAIN_V3 != PREDECESSOR_SIGNATURE_DOMAIN
            or owner_policy.POLICY_ORIGIN != POLICY_ORIGIN
            or owner_policy.SIGNATURE_ORIGIN != SIGNATURE_ORIGIN
            or owner_policy.BOOTSTRAP_SIGNATURE_ALGORITHM != SIGNATURE_ALGORITHM
            or owner_policy.GATE_STATUS != PREDECESSOR_GATE_STATUS
            or owner_policy._validate_policy_body is not _OWNER_POLICY_BODY_REPLAY
            or owner_policy._validate_signature is not _OWNER_POLICY_SIGNATURE_REPLAY
        ):
            raise P0WindowsOwnerPolicyV4PacketV2ProfileError(
                "predecessor V3 replay identity or semantic literal drift"
            )
        preauth_manifest = preauth_v2.COMPONENT_MANIFEST
        if (
            preauth_v2.PUBLIC_KEY_PIN_SCHEMA != PACKET_PUBLIC_KEY_PIN_SCHEMA
            or preauth_v2.ALGORITHM != PACKET_PREAUTHORIZATION_ALGORITHM
            or preauth_v2.SIGNATURE_DOMAIN
            != PACKET_PREAUTHORIZATION_SIGNATURE_DOMAIN
            or preauth_v2.PURPOSE != PACKET_PREAUTHORIZATION_PURPOSE
            or preauth_v2.PIN_ORIGIN != PACKET_PIN_ORIGIN
            or preauth_v2.CURVE != PACKET_CURVE
            or preauth_v2.COORDINATE_ENCODING != PACKET_COORDINATE_ENCODING
            or preauth_v2.FINGERPRINT_ENCODING != PACKET_FINGERPRINT_ENCODING
            or preauth_v2.OWNER_ANCHOR_DOMAIN != PACKET_OWNER_ANCHOR_DOMAIN
            or tuple(preauth_v2._PIN_FIELDS) != _PIN_FIELDS
            or preauth_manifest["schemas"]["public_key_pin"]
            != PACKET_PUBLIC_KEY_PIN_SCHEMA
            or preauth_manifest["domains"]["signature"]
            != PACKET_PREAUTHORIZATION_SIGNATURE_DOMAIN
            or preauth_manifest["algorithm"]
            != PACKET_PREAUTHORIZATION_ALGORITHM
        ):
            raise P0WindowsOwnerPolicyV4PacketV2ProfileError(
                "upstream packet V2 semantic literal/manifest drift"
            )
        dependencies = (
            (
                "packet", PACKET_COMPONENT_MANIFEST_SHA256,
                packet_v2.COMPONENT_MANIFEST_SHA256,
                canonical_sha256(packet_v2.COMPONENT_MANIFEST),
            ),
            (
                "windows", WINDOWS_COMPONENT_MANIFEST_SHA256,
                windows_v2.COMPONENT_MANIFEST_SHA256,
                canonical_sha256(windows_v2.COMPONENT_MANIFEST),
            ),
            (
                "preauthorization", PREAUTHORIZATION_COMPONENT_MANIFEST_SHA256,
                preauth_v2.COMPONENT_MANIFEST_SHA256,
                canonical_sha256(preauth_v2.COMPONENT_MANIFEST),
            ),
            (
                "supervisor", SUPERVISOR_COMPONENT_MANIFEST_SHA256,
                supervisor_v2.COMPONENT_MANIFEST_SHA256,
                canonical_sha256(supervisor_v2.COMPONENT_MANIFEST),
            ),
            (
                "fixed_member_contract", FIXED_MEMBER_CONTRACT_SHA256,
                packet_v2.FIXED_MEMBER_CONTRACT_SHA256,
                canonical_sha256(packet_v2.FIXED_MEMBER_CONTRACT),
            ),
        )
        declared = COMPONENT_MANIFEST["dependency_pins"]
        for name, pinned, live_declared, live_recomputed in dependencies:
            if (
                declared.get(name) != pinned
                or live_declared != pinned
                or live_recomputed != pinned
            ):
                raise P0WindowsOwnerPolicyV4PacketV2ProfileError(
                    f"{name} declared/recomputed/live dependency pin drift"
                )
        if (
            preauth_v2.PACKET_COMPONENT_MANIFEST_SHA256
            != PACKET_COMPONENT_MANIFEST_SHA256
            or preauth_v2.WINDOWS_COMPONENT_MANIFEST_SHA256
            != WINDOWS_COMPONENT_MANIFEST_SHA256
            or preauth_v2.FIXED_MEMBER_CONTRACT_SHA256
            != FIXED_MEMBER_CONTRACT_SHA256
            or supervisor_v2.PACKET_COMPONENT_MANIFEST_SHA256
            != PACKET_COMPONENT_MANIFEST_SHA256
            or supervisor_v2.WINDOWS_COMPONENT_MANIFEST_SHA256
            != WINDOWS_COMPONENT_MANIFEST_SHA256
            or supervisor_v2.PREAUTHORIZATION_COMPONENT_MANIFEST_SHA256
            != PREAUTHORIZATION_COMPONENT_MANIFEST_SHA256
            or supervisor_v2.FIXED_MEMBER_CONTRACT_SHA256
            != FIXED_MEMBER_CONTRACT_SHA256
        ):
            raise P0WindowsOwnerPolicyV4PacketV2ProfileError(
                "transitive packet V2 dependency pin drift"
            )
    except P0WindowsOwnerPolicyV4PacketV2ProfileError:
        raise
    except (KeyError, TypeError, AttributeError, ValueError, RecursionError) as exc:
        raise P0WindowsOwnerPolicyV4PacketV2ProfileError(
            "dependency manifest integrity validation failed"
        ) from exc


def _expected_predecessor_receipt(
    *, body: Mapping[str, Any], body_raw: bytes,
    signature: Mapping[str, Any], signature_raw: bytes,
) -> dict[str, Any]:
    """Independently reconstruct the exact 61-field V3 parent receipt."""

    security_template_hashes = {
        row["role"]: canonical_sha256(row["security_template"])
        for row in body["object_policies"]
    }
    object_identity = canonical_sha256([
        {
            key: row[key]
            for key in (
                "role", "object_kind", "final_volume_guid_path",
                "volume_serial_decimal", "file_id_128_hex",
            )
        }
        for row in body["object_policies"]
    ])
    body_sha = hashlib.sha256(body_raw).hexdigest()
    material: dict[str, Any] = {
        "schema_version": PREDECESSOR_RECEIPT_SCHEMA,
        "gate_status": PREDECESSOR_GATE_STATUS,
        "policy_id": body["policy_id"],
        "policy_epoch": body["policy_epoch"],
        "policy_body_bytes_sha256": body_sha,
        "policy_body_artifact_sha256": body["artifact_sha256"],
        "policy_signature_bytes_sha256": hashlib.sha256(signature_raw).hexdigest(),
        "policy_signature_artifact_sha256": signature["artifact_sha256"],
        "store_id": body["store_id"],
        "owner_principal_sha256": body["owner_principal_sha256"],
        "owner_anchor_sha256": body["owner_anchor_sha256"],
        "owner_anchor_scope": "CORE_POLICY_IDENTITY_EXCLUDING_PIN_TRANSPORT_HASHES",
        "owner_anchor_excludes_pin_transport_hashes_by_design": True,
        "full_policy_identity_sha256": body_sha,
        "acl_template_sha256": body["acl_template_sha256"],
        "operational_key_projection_sha256": body[
            "operational_key_projection_sha256"
        ],
        "object_identity_projection_sha256": object_identity,
        "security_template_sha256_by_role": security_template_hashes,
        "strict_canonical_policy_body_verified": True,
        "strict_canonical_detached_signature_envelope_verified": True,
        "owner_and_verifier_sid_disjoint_contract_verified": True,
        "fixed_generation_layout_contract_verified": True,
        "exact_standard_explicit_ace_profile_contract_verified": True,
        "derived_owner_anchor_cross_binding_verified": True,
        "detached_signature_body_hash_cross_binding_verified": True,
        **{
            field: False
            for field in _PREDECESSOR_RECEIPT_FALSE_FIELDS[:21]
        },
    }
    material.update({
        "policy_schema_version": PREDECESSOR_POLICY_BODY_SCHEMA,
        "policy_domain": PREDECESSOR_POLICY_DOMAIN,
        "signature_schema_version": PREDECESSOR_POLICY_SIGNATURE_SCHEMA,
        "signature_domain": PREDECESSOR_SIGNATURE_DOMAIN,
        "deployment_projection_sha256": body["deployment_projection"][
            "artifact_sha256"
        ],
        "native_observer_profile_sha256": body["native_observer_profile"][
            "artifact_sha256"
        ],
        "deployment_projection_contract_verified": True,
        "native_observer_profile_contract_verified": True,
        "policy_verifier_sid_deployment_service_sid_cross_binding_verified": True,
        "policy_deployment_native_observer_profile_cross_binding_verified": True,
        "operational_and_observer_key_role_separation_contract_verified": True,
        "future_native_observer_authority_requires_v3": True,
        "future_authority_policy_version_eligible": False,
        "positive_native_observer_policy_profile_complete": False,
    })
    expected = {**material, "receipt_sha256": canonical_sha256(material)}
    if tuple(expected) != _PREDECESSOR_RECEIPT_FIELDS:
        raise P0WindowsOwnerPolicyV4PacketV2ProfileError(
            "internal predecessor V3 receipt reconstruction field drift"
        )
    return expected


def _validate_predecessor_receipt(
    receipt: Any, *, body: Mapping[str, Any], body_raw: bytes,
    signature: Mapping[str, Any], signature_raw: bytes,
) -> dict[str, Any]:
    row = _strict(receipt, _PREDECESSOR_RECEIPT_FIELDS, "predecessor V3 receipt")
    material = dict(row)
    declared = _sha(material.pop("receipt_sha256"), "predecessor V3 receipt SHA")
    if not hmac.compare_digest(declared, canonical_sha256(material)):
        raise P0WindowsOwnerPolicyV4PacketV2ProfileError(
            "predecessor V3 receipt self-hash mismatch"
        )
    expected = {
        "schema_version": PREDECESSOR_RECEIPT_SCHEMA,
        "gate_status": PREDECESSOR_GATE_STATUS,
        "policy_id": body["policy_id"],
        "policy_epoch": body["policy_epoch"],
        "policy_body_bytes_sha256": hashlib.sha256(body_raw).hexdigest(),
        "policy_body_artifact_sha256": body["artifact_sha256"],
        "policy_signature_bytes_sha256": hashlib.sha256(signature_raw).hexdigest(),
        "policy_signature_artifact_sha256": signature["artifact_sha256"],
        "owner_principal_sha256": body["owner_principal_sha256"],
        "policy_schema_version": PREDECESSOR_POLICY_BODY_SCHEMA,
        "policy_domain": PREDECESSOR_POLICY_DOMAIN,
        "signature_schema_version": PREDECESSOR_POLICY_SIGNATURE_SCHEMA,
        "signature_domain": PREDECESSOR_SIGNATURE_DOMAIN,
        "owner_anchor_scope": "CORE_POLICY_IDENTITY_EXCLUDING_PIN_TRANSPORT_HASHES",
    }
    if any(
        row.get(field) != value or type(row.get(field)) is not type(value)
        for field, value in expected.items()
    ):
        raise P0WindowsOwnerPolicyV4PacketV2ProfileError(
            "predecessor V3 receipt exact binding mismatch"
        )
    if any(type(row.get(field)) is not bool or row[field] is not True for field in _PREDECESSOR_RECEIPT_TRUE_FIELDS):
        raise P0WindowsOwnerPolicyV4PacketV2ProfileError(
            "predecessor V3 receipt required truth mismatch"
        )
    if any(
        type(row.get(field)) is not bool or row[field] is not False
        for field in _PREDECESSOR_RECEIPT_FALSE_FIELDS
    ):
        raise P0WindowsOwnerPolicyV4PacketV2ProfileError(
            "predecessor V3 receipt denial truth mismatch"
        )
    expected_receipt = _expected_predecessor_receipt(
        body=body, body_raw=body_raw,
        signature=signature, signature_raw=signature_raw,
    )
    if row != expected_receipt or canonical_bytes(row) != canonical_bytes(expected_receipt):
        raise P0WindowsOwnerPolicyV4PacketV2ProfileError(
            "predecessor V3 parent receipt differs from independent reconstruction"
        )
    return row


def _validate_predecessor(
    body_raw: bytes, signature_raw: bytes,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    try:
        receipt = _OWNER_POLICY_PARENT_VALIDATOR(
            policy_body_bytes=body_raw,
            policy_signature_bytes=signature_raw,
        )
        _assert_owner_graph_integrity()
        body = _parse(
            body_raw, cap=1024 * 1024, label="predecessor_policy_v3"
        )
        signature = _parse(
            signature_raw, cap=_MAX_SIGNATURE_BYTES,
            label="predecessor_policy_v3_signature",
        )
        replayed_body = _OWNER_POLICY_BODY_REPLAY(body_raw)
        replayed_signature = _OWNER_POLICY_SIGNATURE_REPLAY(
            signature_raw, replayed_body, body_raw
        )
        _assert_owner_graph_integrity()
    except owner_policy.P0WindowsOwnerPolicyContractError as exc:
        raise P0WindowsOwnerPolicyV4PacketV2ProfileError(
            "predecessor owner policy V3 parent validation failed"
        ) from exc
    if (
        body.get("schema_version") != PREDECESSOR_POLICY_BODY_SCHEMA
        or body.get("domain") != PREDECESSOR_POLICY_DOMAIN
        or signature.get("schema_version") != PREDECESSOR_POLICY_SIGNATURE_SCHEMA
        or signature.get("domain") != PREDECESSOR_SIGNATURE_DOMAIN
        or body != replayed_body
        or signature != replayed_signature
    ):
        raise P0WindowsOwnerPolicyV4PacketV2ProfileError(
            "predecessor must be the exact validated V3 contract"
        )
    validated_receipt = _validate_predecessor_receipt(
        receipt, body=body, body_raw=body_raw,
        signature=signature, signature_raw=signature_raw,
    )
    return body, signature, validated_receipt


def _validate_pin(pin_raw: bytes) -> dict[str, Any]:
    try:
        pin = _strict(
            _parse(
                pin_raw, cap=_MAX_PIN_BYTES, label="packet V2 public-key pin"
            ),
            _PIN_FIELDS,
            "packet V2 public-key pin",
        )
        fixed = {
            "schema_version": PACKET_PUBLIC_KEY_PIN_SCHEMA,
            "record_origin": PACKET_PIN_ORIGIN,
            "purpose": PACKET_PREAUTHORIZATION_PURPOSE,
            "algorithm": PACKET_PREAUTHORIZATION_ALGORITHM,
            "curve": PACKET_CURVE,
            "coordinate_encoding": PACKET_COORDINATE_ENCODING,
            "fingerprint_encoding": PACKET_FINGERPRINT_ENCODING,
            "allowed_signature_domains": [
                PACKET_PREAUTHORIZATION_SIGNATURE_DOMAIN
            ],
        }
        if any(
            pin.get(field) != expected
            or type(pin.get(field)) is not type(expected)
            for field, expected in fixed.items()
        ):
            raise P0WindowsOwnerPolicyV4PacketV2ProfileError(
                "packet V2 pin fixed V4 semantics mismatch"
            )
        for field in ("trust_domain", "project_id", "environment", "key_id"):
            _identifier(pin[field], f"packet V2 pin.{field}")
        _positive_bounded_int(pin["key_epoch"], "packet V2 pin.key_epoch")

        def coordinate(field: str) -> bytes:
            value = pin[field]
            if type(value) is not str or not value or any(
                char.isspace() for char in value
            ):
                raise P0WindowsOwnerPolicyV4PacketV2ProfileError(
                    f"packet V2 pin.{field} must be canonical Base64"
                )
            try:
                decoded = base64.b64decode(value, validate=True)
            except (ValueError, binascii.Error) as exc:
                raise P0WindowsOwnerPolicyV4PacketV2ProfileError(
                    f"packet V2 pin.{field} must be canonical Base64"
                ) from exc
            if (
                len(decoded) != 32
                or base64.b64encode(decoded).decode("ascii") != value
            ):
                raise P0WindowsOwnerPolicyV4PacketV2ProfileError(
                    f"packet V2 pin.{field} must encode exactly 32 bytes"
                )
            return decoded

        x = coordinate("public_key_x_base64")
        y = coordinate("public_key_y_base64")
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ec

        public_key = ec.EllipticCurvePublicNumbers(
            int.from_bytes(x, "big"), int.from_bytes(y, "big"), ec.SECP256R1()
        ).public_key()
        canonical_spki = public_key.public_bytes(
            serialization.Encoding.DER,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        expected_spki = bytes.fromhex(
            "3059301306072a8648ce3d020106082a8648ce3d03010703420004"
        ) + x + y
        fingerprint = _sha(
            pin["public_key_fingerprint_sha256"],
            "packet V2 pin public-key fingerprint",
        )
        owner_principal = _sha(
            pin["owner_principal_sha256"], "packet V2 pin owner principal"
        )
        expected_owner_anchor = canonical_sha256({
            "domain": PACKET_OWNER_ANCHOR_DOMAIN,
            "trust_domain": pin["trust_domain"],
            "project_id": pin["project_id"],
            "environment": pin["environment"],
            "owner_principal_sha256": owner_principal,
        })
        if (
            canonical_spki != expected_spki
            or hashlib.sha256(expected_spki).hexdigest()
            != fingerprint
            or _sha(pin["owner_anchor_sha256"], "packet V2 pin owner anchor")
            != expected_owner_anchor
        ):
            raise P0WindowsOwnerPolicyV4PacketV2ProfileError(
                "packet V2 pin point, fingerprint, or owner anchor mismatch"
            )
        _self_hash(pin, "packet V2 public-key pin")
    except ImportError as exc:
        raise P0WindowsOwnerPolicyV4PacketV2ProfileError(
            "cryptography is required for packet V2 point validation"
        ) from exc
    except P0WindowsOwnerPolicyV4PacketV2ProfileError:
        raise
    except (ValueError, TypeError, KeyError) as exc:
        raise P0WindowsOwnerPolicyV4PacketV2ProfileError(
            "packet V2 public-key pin validation failed"
        ) from exc
    return pin


def _validate_profile(
    value: Any, *, pin: Mapping[str, Any], pin_raw: bytes,
) -> dict[str, Any]:
    row = _strict(value, _PROFILE_FIELDS, "packet_v2_preauthorization_profile")
    expected = {
        "schema_version": PROFILE_SCHEMA,
        "domain": PROFILE_DOMAIN,
        "public_key_pin_schema": PACKET_PUBLIC_KEY_PIN_SCHEMA,
        "public_key_pin_bytes_sha256": hashlib.sha256(pin_raw).hexdigest(),
        "public_key_pin_artifact_sha256": pin["artifact_sha256"],
        "public_key_fingerprint_sha256": pin["public_key_fingerprint_sha256"],
        "key_id": pin["key_id"],
        "key_epoch": pin["key_epoch"],
        "preauthorization_algorithm": PACKET_PREAUTHORIZATION_ALGORITHM,
        "preauthorization_signature_domain": PACKET_PREAUTHORIZATION_SIGNATURE_DOMAIN,
        "packet_component_manifest_sha256": PACKET_COMPONENT_MANIFEST_SHA256,
        "windows_component_manifest_sha256": WINDOWS_COMPONENT_MANIFEST_SHA256,
        "preauthorization_component_manifest_sha256": PREAUTHORIZATION_COMPONENT_MANIFEST_SHA256,
        "supervisor_component_manifest_sha256": SUPERVISOR_COMPONENT_MANIFEST_SHA256,
        "fixed_member_contract_sha256": FIXED_MEMBER_CONTRACT_SHA256,
        "max_preauthorization_ttl_seconds": MAX_PREAUTHORIZATION_TTL_SECONDS,
        "packet_v2_purpose": PACKET_PREAUTHORIZATION_PURPOSE,
        "owner_principal_sha256": pin["owner_principal_sha256"],
        "public_key_pin_owner_anchor_sha256": pin["owner_anchor_sha256"],
    }
    for field, expected_value in expected.items():
        if row.get(field) != expected_value or type(row.get(field)) is not type(expected_value):
            raise P0WindowsOwnerPolicyV4PacketV2ProfileError(
                f"packet V2 profile {field} mismatch"
            )
    if type(row.get("min_revocation_sequence")) is not int or row["min_revocation_sequence"] < 1:
        raise P0WindowsOwnerPolicyV4PacketV2ProfileError(
            "packet V2 profile min_revocation_sequence must be positive int"
        )
    if any(type(row.get(field)) is not bool or row[field] is not True for field in _REQUIRED_CAPABILITY_FIELDS):
        raise P0WindowsOwnerPolicyV4PacketV2ProfileError(
            "packet V2 profile downstream requirements must be exact true"
        )
    if any(type(row.get(field)) is not bool or row[field] is not False for field in _PROFILE_FALSE_FIELDS):
        raise P0WindowsOwnerPolicyV4PacketV2ProfileError(
            "packet V2 profile authority/mutation truth table must remain false"
        )
    _profile_self_hash(row)
    return row


def _derive_owner_anchor(
    row: Mapping[str, Any], profile: Mapping[str, Any],
) -> str:
    return canonical_sha256({
        "domain": OWNER_ANCHOR_DOMAIN_V4,
        "policy_id": row["policy_id"],
        "policy_epoch": row["policy_epoch"],
        "predecessor_policy_v3_bytes_sha256": row["predecessor_policy_v3_bytes_sha256"],
        "predecessor_policy_v3_artifact_sha256": row["predecessor_policy_v3_artifact_sha256"],
        "predecessor_policy_v3_signature_bytes_sha256": row["predecessor_policy_v3_signature_bytes_sha256"],
        "predecessor_policy_v3_signature_artifact_sha256": row["predecessor_policy_v3_signature_artifact_sha256"],
        "predecessor_contract_receipt_sha256": row["predecessor_contract_receipt_sha256"],
        "predecessor_policy_v3_epoch": row["predecessor_policy_v3_epoch"],
        "project_id": row["project_id"],
        "trust_domain": row["trust_domain"],
        "environment": row["environment"],
        "policy_purpose": row["policy_purpose"],
        "bootstrap_key_id": row["bootstrap_key_id"],
        "bootstrap_public_key_fingerprint_sha256": row["bootstrap_public_key_fingerprint_sha256"],
        "owner_principal_sha256": row["owner_principal_sha256"],
        "packet_v2_owner_anchor_sha256": row["packet_v2_owner_anchor_sha256"],
        "profile_artifact_sha256": profile["profile_artifact_sha256"],
        "public_key_pin_bytes_sha256": profile["public_key_pin_bytes_sha256"],
        "public_key_pin_artifact_sha256": profile["public_key_pin_artifact_sha256"],
        "public_key_fingerprint_sha256": profile["public_key_fingerprint_sha256"],
        "packet_v2_key_id": profile["key_id"],
        "packet_v2_key_epoch": profile["key_epoch"],
        "min_revocation_sequence": profile["min_revocation_sequence"],
        "component_pins": {
            "packet": profile["packet_component_manifest_sha256"],
            "windows": profile["windows_component_manifest_sha256"],
            "preauthorization": profile["preauthorization_component_manifest_sha256"],
            "supervisor": profile["supervisor_component_manifest_sha256"],
            "fixed_member_contract": profile["fixed_member_contract_sha256"],
        },
    })


def _validate_body(
    raw: bytes, *, predecessor: Mapping[str, Any], predecessor_raw: bytes,
    predecessor_signature: Mapping[str, Any], predecessor_signature_raw: bytes,
    predecessor_receipt: Mapping[str, Any], pin: Mapping[str, Any], pin_raw: bytes,
) -> tuple[dict[str, Any], dict[str, Any]]:
    row = _strict(_parse(raw, cap=_MAX_POLICY_BYTES, label="policy V4 body"), _BODY_FIELDS, "policy V4 body")
    profile = _validate_profile(
        row["packet_v2_preauthorization_profile"], pin=pin, pin_raw=pin_raw,
    )
    predecessor_sha = hashlib.sha256(predecessor_raw).hexdigest()
    predecessor_signature_sha = hashlib.sha256(predecessor_signature_raw).hexdigest()
    predecessor_epoch = _positive_bounded_int(
        predecessor["policy_epoch"], "predecessor.policy_epoch"
    )
    if predecessor_epoch == 2**63 - 1:
        raise P0WindowsOwnerPolicyV4PacketV2ProfileError(
            "predecessor policy epoch has no bounded V4 successor"
        )
    expected = {
        "schema_version": POLICY_BODY_SCHEMA,
        "record_origin": POLICY_ORIGIN,
        "domain": POLICY_DOMAIN,
        "policy_id": predecessor["policy_id"],
        "policy_epoch": predecessor_epoch + 1,
        "predecessor_policy_v3_bytes_sha256": predecessor_sha,
        "predecessor_policy_v3_epoch": predecessor["policy_epoch"],
        "predecessor_policy_v3_artifact_sha256": predecessor["artifact_sha256"],
        "predecessor_policy_v3_signature_bytes_sha256": predecessor_signature_sha,
        "predecessor_policy_v3_signature_artifact_sha256": predecessor_signature["artifact_sha256"],
        "predecessor_contract_receipt_sha256": predecessor_receipt["receipt_sha256"],
        "project_id": predecessor["project_id"],
        "trust_domain": predecessor["trust_domain"],
        "environment": predecessor["environment"],
        "policy_purpose": predecessor["purpose"],
        "bootstrap_key_id": predecessor["bootstrap_key_id"],
        "bootstrap_public_key_fingerprint_sha256": predecessor["bootstrap_public_key_fingerprint_sha256"],
        "owner_principal_sha256": predecessor["owner_principal_sha256"],
        "packet_v2_owner_anchor_sha256": pin["owner_anchor_sha256"],
        "operational_effect": OPERATIONAL_EFFECT,
        "gate_status": GATE_STATUS,
    }
    for field, expected_value in expected.items():
        if row.get(field) != expected_value or type(row.get(field)) is not type(expected_value):
            raise P0WindowsOwnerPolicyV4PacketV2ProfileError(
                f"policy V4 body {field} mismatch"
            )
    for field in (
        "policy_id", "project_id", "trust_domain", "environment", "policy_purpose",
        "bootstrap_key_id",
    ):
        _identifier(row[field], f"policy V4 body.{field}")
    _sha(row["bootstrap_public_key_fingerprint_sha256"], "policy V4 bootstrap fingerprint")
    _positive_bounded_int(row["policy_epoch"], "policy V4 policy_epoch")
    _positive_bounded_int(row["predecessor_policy_v3_epoch"], "policy V4 predecessor epoch")
    packet_epoch = _positive_bounded_int(profile["key_epoch"], "packet V2 key_epoch")
    revocation = _positive_bounded_int(
        profile["min_revocation_sequence"], "packet V2 min_revocation_sequence"
    )
    operational = predecessor["operational_key"]
    native = predecessor["native_observer_profile"]
    predecessor_key_epochs = (
        predecessor_epoch,
        _positive_bounded_int(operational["key_epoch"], "predecessor operational key_epoch"),
        _positive_bounded_int(native["observer_key_epoch"], "predecessor observer key_epoch"),
        _positive_bounded_int(native["owner_state_authority_key_epoch"], "predecessor owner-state key_epoch"),
    )
    predecessor_key_ids = (
        predecessor["bootstrap_key_id"], operational["key_id"],
        native["observer_key_id"], native["owner_state_authority_key_id"],
    )
    predecessor_fingerprints = (
        predecessor["bootstrap_public_key_fingerprint_sha256"],
        operational["public_key_fingerprint_sha256"],
        native["observer_public_key_fingerprint_sha256"],
        native["owner_state_authority_spki_sha256"],
    )
    if (
        row["project_id"] != pin["project_id"]
        or row["trust_domain"] != pin["trust_domain"]
        or row["environment"] != pin["environment"]
        or profile["packet_v2_purpose"] != pin["purpose"]
        or pin["owner_principal_sha256"] != predecessor["owner_principal_sha256"]
        or profile["owner_principal_sha256"] != predecessor["owner_principal_sha256"]
        or profile["public_key_pin_owner_anchor_sha256"] != pin["owner_anchor_sha256"]
        or revocation < _positive_bounded_int(
            predecessor["min_revocation_sequence"], "predecessor min_revocation_sequence"
        )
        or packet_epoch <= max(predecessor_key_epochs)
        or pin["key_id"] in predecessor_key_ids
        or pin["public_key_fingerprint_sha256"] in predecessor_fingerprints
    ):
        raise P0WindowsOwnerPolicyV4PacketV2ProfileError(
            "V3/V4/pin scope, owner, key-role, epoch, or revocation cross-binding mismatch"
        )
    expected_anchor = _derive_owner_anchor(row, profile)
    if (
        _sha(row["owner_anchor_sha256"], "policy V4 owner anchor")
        != expected_anchor
    ):
        raise P0WindowsOwnerPolicyV4PacketV2ProfileError(
            "policy V4 owner anchor mismatch"
        )
    _self_hash(row, "policy V4 body")
    return row, profile


def _signature_material(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: row[key]
        for key in _SIGNATURE_FIELDS
        if key not in {"signature_rs_base64", "artifact_sha256"}
    }


def _validate_signature(
    raw: bytes, *, body: Mapping[str, Any], body_raw: bytes,
) -> tuple[dict[str, Any], bytes, bytes]:
    row = _strict(_parse(raw, cap=_MAX_SIGNATURE_BYTES, label="policy V4 signature"), _SIGNATURE_FIELDS, "policy V4 signature")
    expected = {
        "schema_version": POLICY_SIGNATURE_SCHEMA,
        "record_origin": SIGNATURE_ORIGIN,
        "domain": SIGNATURE_DOMAIN,
        "algorithm": SIGNATURE_ALGORITHM,
        "policy_body_schema": POLICY_BODY_SCHEMA,
        "policy_body_bytes_sha256": hashlib.sha256(body_raw).hexdigest(),
        "policy_body_artifact_sha256": body["artifact_sha256"],
        "policy_id": body["policy_id"],
        "policy_epoch": body["policy_epoch"],
        "predecessor_policy_v3_bytes_sha256": body["predecessor_policy_v3_bytes_sha256"],
        "predecessor_policy_v3_epoch": body["predecessor_policy_v3_epoch"],
        "predecessor_policy_v3_artifact_sha256": body["predecessor_policy_v3_artifact_sha256"],
        "predecessor_policy_v3_signature_bytes_sha256": body["predecessor_policy_v3_signature_bytes_sha256"],
        "predecessor_policy_v3_signature_artifact_sha256": body["predecessor_policy_v3_signature_artifact_sha256"],
        "predecessor_contract_receipt_sha256": body["predecessor_contract_receipt_sha256"],
        "bootstrap_key_id": body["bootstrap_key_id"],
        "bootstrap_public_key_fingerprint_sha256": body["bootstrap_public_key_fingerprint_sha256"],
        "profile_artifact_sha256": body["packet_v2_preauthorization_profile"]["profile_artifact_sha256"],
        "owner_anchor_sha256": body["owner_anchor_sha256"],
    }
    for field, expected_value in expected.items():
        if row.get(field) != expected_value or type(row.get(field)) is not type(expected_value):
            raise P0WindowsOwnerPolicyV4PacketV2ProfileError(
                f"policy V4 signature {field} mismatch"
            )
    signature = _decode_signature(row["signature_rs_base64"])
    _self_hash(row, "policy V4 signature")
    material = canonical_bytes(_signature_material(row))
    return row, signature, material


def _verify_signature_math(
    *, bootstrap_public_key_spki_der: bytes, expected_fingerprint: str,
    signature: bytes, material: bytes,
) -> None:
    if type(bootstrap_public_key_spki_der) is not bytes or not bootstrap_public_key_spki_der or len(bootstrap_public_key_spki_der) > 1024:
        raise P0WindowsOwnerPolicyV4PacketV2ProfileError(
            "bootstrap public key must be bounded DER SPKI bytes"
        )
    if hashlib.sha256(bootstrap_public_key_spki_der).hexdigest() != expected_fingerprint:
        raise P0WindowsOwnerPolicyV4PacketV2ProfileError(
            "bootstrap public key fingerprint mismatch"
        )
    try:
        from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec, utils

        public_key = serialization.load_der_public_key(bootstrap_public_key_spki_der)
        if (
            not isinstance(public_key, ec.EllipticCurvePublicKey)
            or not isinstance(public_key.curve, ec.SECP256R1)
            or public_key.public_bytes(
                serialization.Encoding.DER,
                serialization.PublicFormat.SubjectPublicKeyInfo,
            ) != bootstrap_public_key_spki_der
        ):
            raise P0WindowsOwnerPolicyV4PacketV2ProfileError(
                "bootstrap public key must be canonical P-256 DER SPKI"
            )
        r = int.from_bytes(signature[:32], "big")
        s = int.from_bytes(signature[32:], "big")
        public_key.verify(
            utils.encode_dss_signature(r, s), material, ec.ECDSA(hashes.SHA256())
        )
    except ImportError as exc:
        raise P0WindowsOwnerPolicyV4PacketV2ProfileError(
            "cryptography is required for V4 signature verification"
        ) from exc
    except (ValueError, TypeError, InvalidSignature, UnsupportedAlgorithm) as exc:
        raise P0WindowsOwnerPolicyV4PacketV2ProfileError(
            "policy V4 bootstrap signature mathematics failed"
        ) from exc


COMPONENT_MANIFEST = {
    "component": "p0_windows_owner_policy_v4_packet_v2_profile_contract",
    "schemas": {
        "policy_body": POLICY_BODY_SCHEMA,
        "profile": PROFILE_SCHEMA,
        "policy_signature": POLICY_SIGNATURE_SCHEMA,
        "receipt": RECEIPT_SCHEMA,
    },
    "origins": {
        "policy": POLICY_ORIGIN,
        "signature": SIGNATURE_ORIGIN,
    },
    "domains": {
        "policy": POLICY_DOMAIN,
        "profile": PROFILE_DOMAIN,
        "signature": SIGNATURE_DOMAIN,
        "owner_anchor_v4": OWNER_ANCHOR_DOMAIN_V4,
        "packet_v2_signature": PACKET_PREAUTHORIZATION_SIGNATURE_DOMAIN,
    },
    "algorithms": {
        "bootstrap_signature": SIGNATURE_ALGORITHM,
        "packet_v2_preauthorization": PACKET_PREAUTHORIZATION_ALGORITHM,
    },
    "packet_v2_public_key_pin_schema": PACKET_PUBLIC_KEY_PIN_SCHEMA,
    "packet_v2_purpose": PACKET_PREAUTHORIZATION_PURPOSE,
    "packet_v2_pin_semantics": {
        "record_origin": PACKET_PIN_ORIGIN,
        "curve": PACKET_CURVE,
        "coordinate_encoding": PACKET_COORDINATE_ENCODING,
        "fingerprint_encoding": PACKET_FINGERPRINT_ENCODING,
        "owner_anchor_domain": PACKET_OWNER_ANCHOR_DOMAIN,
        "fields": _PIN_FIELDS,
    },
    "predecessor_contract": {
        "policy_body_schema": PREDECESSOR_POLICY_BODY_SCHEMA,
        "policy_signature_schema": PREDECESSOR_POLICY_SIGNATURE_SCHEMA,
        "receipt_schema": PREDECESSOR_RECEIPT_SCHEMA,
        "policy_domain": PREDECESSOR_POLICY_DOMAIN,
        "signature_domain": PREDECESSOR_SIGNATURE_DOMAIN,
        "gate_status": PREDECESSOR_GATE_STATUS,
        "validator_graph_callable_names": _OWNER_GRAPH_CALLABLE_NAMES,
        "validator_graph_constant_names": _OWNER_GRAPH_CONSTANT_NAMES,
        "validator_graph_global_references": (
            _OWNER_GRAPH_REFERENCE_DESCRIPTOR["globals"]
        ),
        "validator_graph_attribute_references": (
            _OWNER_GRAPH_REFERENCE_DESCRIPTOR["attributes"]
        ),
        "validator_graph_deref_references": (
            _OWNER_GRAPH_REFERENCE_DESCRIPTOR["derefs"]
        ),
        "validator_graph_reference_descriptor_sha256": (
            _OWNER_GRAPH_REFERENCE_DESCRIPTOR_SHA256
        ),
    },
    "dependency_pins": {
        "packet": PACKET_COMPONENT_MANIFEST_SHA256,
        "windows": WINDOWS_COMPONENT_MANIFEST_SHA256,
        "preauthorization": PREAUTHORIZATION_COMPONENT_MANIFEST_SHA256,
        "supervisor": SUPERVISOR_COMPONENT_MANIFEST_SHA256,
        "fixed_member_contract": FIXED_MEMBER_CONTRACT_SHA256,
    },
    "max_preauthorization_ttl_seconds": MAX_PREAUTHORIZATION_TTL_SECONDS,
    "operational_effect": OPERATIONAL_EFFECT,
    "gate_status": GATE_STATUS,
    "required_capability_fields": _REQUIRED_CAPABILITY_FIELDS,
    "profile_false_fields": _PROFILE_FALSE_FIELDS,
    "receipt_fields": _RECEIPT_FIELDS,
    "receipt_true_fields": _RECEIPT_TRUE_FIELDS,
    "receipt_false_fields": _RECEIPT_FALSE_FIELDS,
    "predecessor_receipt_fields": _PREDECESSOR_RECEIPT_FIELDS,
    "predecessor_receipt_true_fields": _PREDECESSOR_RECEIPT_TRUE_FIELDS,
    "predecessor_receipt_false_fields": _PREDECESSOR_RECEIPT_FALSE_FIELDS,
    "body_fields": _BODY_FIELDS,
    "profile_fields": _PROFILE_FIELDS,
    "signature_fields": _SIGNATURE_FIELDS,
    "public_apis": ("validate_presented_windows_owner_policy_v4_packet_v2_profile",),
    "filesystem_access": False,
    "network_access": False,
    "external_authority": False,
}
COMPONENT_MANIFEST_SHA256 = canonical_sha256(COMPONENT_MANIFEST)
# Replaced after every intentional manifest change.  Runtime recomputation must
# match both this literal and the public manifest SHA at entry and exit.
EXPECTED_COMPONENT_MANIFEST_SHA256 = (
    "9224e3c69c2748a882b81d5ccd29d02f3a9ad689e29a20ea6de6f100edbb9fc7"
)


def _validate_presented_windows_owner_policy_v4_packet_v2_profile(
    *,
    predecessor_policy_v3_body_bytes: bytes,
    predecessor_policy_v3_signature_bytes: bytes,
    packet_v2_public_key_pin_bytes: bytes,
    policy_v4_body_bytes: bytes,
    policy_v4_signature_bytes: bytes,
    bootstrap_public_key_spki_der: bytes,
) -> dict[str, Any]:
    """Validate the signed V4 profile without provisioning or applying it."""

    _assert_dependency_pins()
    predecessor, predecessor_signature, predecessor_receipt = _validate_predecessor(
        predecessor_policy_v3_body_bytes, predecessor_policy_v3_signature_bytes,
    )
    pin = _validate_pin(packet_v2_public_key_pin_bytes)
    body, profile = _validate_body(
        policy_v4_body_bytes,
        predecessor=predecessor,
        predecessor_raw=predecessor_policy_v3_body_bytes,
        predecessor_signature=predecessor_signature,
        predecessor_signature_raw=predecessor_policy_v3_signature_bytes,
        predecessor_receipt=predecessor_receipt,
        pin=pin,
        pin_raw=packet_v2_public_key_pin_bytes,
    )
    signature_row, signature, signature_material = _validate_signature(
        policy_v4_signature_bytes, body=body, body_raw=policy_v4_body_bytes,
    )
    _verify_signature_math(
        bootstrap_public_key_spki_der=bootstrap_public_key_spki_der,
        expected_fingerprint=body["bootstrap_public_key_fingerprint_sha256"],
        signature=signature,
        material=signature_material,
    )
    receipt_material: dict[str, Any] = {
        "schema_version": RECEIPT_SCHEMA,
        "component_manifest_sha256": COMPONENT_MANIFEST_SHA256,
        "predecessor_policy_v3_bytes_sha256": hashlib.sha256(predecessor_policy_v3_body_bytes).hexdigest(),
        "predecessor_policy_v3_artifact_sha256": predecessor["artifact_sha256"],
        "predecessor_policy_v3_signature_bytes_sha256": hashlib.sha256(predecessor_policy_v3_signature_bytes).hexdigest(),
        "predecessor_policy_v3_signature_artifact_sha256": predecessor_signature["artifact_sha256"],
        "predecessor_policy_v3_epoch": predecessor["policy_epoch"],
        "predecessor_contract_receipt_sha256": predecessor_receipt["receipt_sha256"],
        "policy_v4_body_bytes_sha256": hashlib.sha256(policy_v4_body_bytes).hexdigest(),
        "policy_v4_body_artifact_sha256": body["artifact_sha256"],
        "policy_v4_signature_bytes_sha256": hashlib.sha256(policy_v4_signature_bytes).hexdigest(),
        "policy_v4_signature_artifact_sha256": signature_row["artifact_sha256"],
        "signature_input_sha256": hashlib.sha256(signature_material).hexdigest(),
        "packet_v2_public_key_pin_bytes_sha256": hashlib.sha256(packet_v2_public_key_pin_bytes).hexdigest(),
        "packet_v2_public_key_pin_artifact_sha256": pin["artifact_sha256"],
        "packet_v2_public_key_fingerprint_sha256": pin["public_key_fingerprint_sha256"],
        "packet_v2_owner_principal_sha256": pin["owner_principal_sha256"],
        "packet_v2_owner_anchor_sha256": pin["owner_anchor_sha256"],
        "packet_v2_key_id": pin["key_id"],
        "packet_v2_key_epoch": pin["key_epoch"],
        "policy_id": body["policy_id"],
        "policy_epoch": body["policy_epoch"],
        "project_id": body["project_id"],
        "trust_domain": body["trust_domain"],
        "environment": body["environment"],
        "policy_purpose": body["policy_purpose"],
        "packet_v2_purpose": profile["packet_v2_purpose"],
        "profile_artifact_sha256": profile["profile_artifact_sha256"],
        "owner_anchor_sha256": body["owner_anchor_sha256"],
        "max_preauthorization_ttl_seconds": profile["max_preauthorization_ttl_seconds"],
        "min_revocation_sequence": profile["min_revocation_sequence"],
        "predecessor_v3_parent_contract_validated": True,
        "predecessor_v3_parent_receipt_exactly_validated": True,
        "predecessor_v3_full_structural_replay_verified": True,
        "predecessor_v3_receipt_independently_reconstructed": True,
        "predecessor_body_signature_receipt_bound": True,
        "packet_v2_public_key_pin_contract_validated": True,
        "packet_v2_public_key_curve_point_verified": True,
        "packet_v2_owner_principal_cross_binding_verified": True,
        "packet_v2_owner_anchor_cross_binding_verified": True,
        "packet_key_four_role_separation_verified": True,
        "bounded_monotonic_epoch_profile_verified": True,
        "profile_artifact_self_hash_verified": True,
        "owner_anchor_v4_recomputed_verified": True,
        "exact_v2_algorithm_and_signature_domain_bound": True,
        "exact_component_pin_set_bound": True,
        "dependency_declared_recomputed_live_pins_verified": True,
        "scope_and_purpose_cross_binding_verified": True,
        "canonical_low_s_signature_verified": True,
        "successor_bootstrap_signature_mathematics_verified": True,
        "downstream_requirement_truth_table_bound": True,
        **{field: False for field in _RECEIPT_FALSE_FIELDS},
        "credited_actual_source_claim_count": 0,
        "credited_actual_a_context_review_count": 0,
        "operational_effect": OPERATIONAL_EFFECT,
        "gate_status": GATE_STATUS,
    }
    _assert_dependency_pins()
    if tuple(receipt_material) + ("receipt_sha256",) != _RECEIPT_FIELDS:
        raise P0WindowsOwnerPolicyV4PacketV2ProfileError(
            "internal V4 receipt exact field drift"
        )
    return {**receipt_material, "receipt_sha256": canonical_sha256(receipt_material)}


def validate_presented_windows_owner_policy_v4_packet_v2_profile(
    *,
    predecessor_policy_v3_body_bytes: bytes,
    predecessor_policy_v3_signature_bytes: bytes,
    packet_v2_public_key_pin_bytes: bytes,
    policy_v4_body_bytes: bytes,
    policy_v4_signature_bytes: bytes,
    bootstrap_public_key_spki_der: bytes,
) -> dict[str, Any]:
    """Fail-closed public boundary for presented, non-authoritative bytes."""

    try:
        return _validate_presented_windows_owner_policy_v4_packet_v2_profile(
            predecessor_policy_v3_body_bytes=predecessor_policy_v3_body_bytes,
            predecessor_policy_v3_signature_bytes=predecessor_policy_v3_signature_bytes,
            packet_v2_public_key_pin_bytes=packet_v2_public_key_pin_bytes,
            policy_v4_body_bytes=policy_v4_body_bytes,
            policy_v4_signature_bytes=policy_v4_signature_bytes,
            bootstrap_public_key_spki_der=bootstrap_public_key_spki_der,
        )
    except P0WindowsOwnerPolicyV4PacketV2ProfileError:
        raise
    except (
        KeyError, TypeError, AttributeError, IndexError, UnicodeError,
        ValueError, ArithmeticError, RecursionError,
    ) as exc:
        raise P0WindowsOwnerPolicyV4PacketV2ProfileError(
            "malformed owner policy V4 packet V2 profile input"
        ) from exc


__all__ = [
    "COMPONENT_MANIFEST_SHA256",
    "GATE_STATUS",
    "P0WindowsOwnerPolicyV4PacketV2ProfileError",
    "validate_presented_windows_owner_policy_v4_packet_v2_profile",
]
