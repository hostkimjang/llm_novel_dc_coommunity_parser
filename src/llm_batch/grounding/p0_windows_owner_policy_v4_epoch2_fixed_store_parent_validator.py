"""Producer-free replay for the V4 epoch2 fixed-store raw bundle.

The validator does not call the V4 producer.  It independently parses the six
raw members, binds their hashes and epoch/scope relations to the already
returned V4 receipt, and enforces that every authority field stays false.
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
import marshal
import types
from typing import Any, Mapping

from llm_batch.grounding import p0_windows_owner_policy_contract as owner_v3


RECEIPT_SCHEMA = (
    "p0_windows_owner_policy_v4_epoch2_fixed_store_parent_replay_receipt_v1"
)
GATE_STATUS = "NO_GO_V4_EPOCH2_FIXED_STORE_PRODUCER_FREE_PARENT_REPLAY_ONLY"
OPERATIONAL_EFFECT = "NONE_PURE_REPLAY"
V4_COMPONENT_MANIFEST_SHA256 = (
    "9224e3c69c2748a882b81d5ccd29d02f3a9ad689e29a20ea6de6f100edbb9fc7"
)
V4_RECEIPT_SCHEMA = "p0_windows_owner_policy_v4_packet_v2_profile_receipt_v1"
V4_GATE_STATUS = "NO_GO_SIGNED_OWNER_POLICY_V4_PACKET_V2_PROFILE_ONLY"
V3_BODY_SCHEMA = "p0_windows_external_owner_policy_body_v3"
V3_SIGNATURE_SCHEMA = "p0_windows_external_owner_policy_signature_v3"
V4_BODY_SCHEMA = "p0_windows_external_owner_policy_body_v4"
V4_SIGNATURE_SCHEMA = "p0_windows_external_owner_policy_signature_v4"
PIN_SCHEMA = "p0_actual_owner_root_public_key_pin_v2"
V4_SIGNATURE_ORIGIN = "EXTERNAL_OWNER_POLICY_DETACHED_SIGNATURE_RECORD"
V4_SIGNATURE_DOMAIN = "llm_novel_dc/p0/windows-owner-policy-signature/v4"
V4_SIGNATURE_ALGORITHM = "ECDSA_P256_SHA256_IEEE_P1363_LOW_S"
V4_OPERATIONAL_EFFECT = "NONE_SHADOW_ONLY"
V3_RECEIPT_SCHEMA = "p0_windows_owner_policy_contract_receipt_v3"
V3_GATE_STATUS = "OWNER_POLICY_CONTRACT_PASS_BOOTSTRAP_AND_PROVISIONING_NO_GO"
V3_POLICY_DOMAIN = "llm_novel_dc/p0/windows-external-owner-policy/v3"
V3_SIGNATURE_DOMAIN = "llm_novel_dc/p0/windows-owner-policy-signature/v3"
EXPECTED_PREDECESSOR_EPOCH = 1
EXPECTED_POLICY_EPOCH = 2
_P256_ORDER = int(
    "FFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551",
    16,
)

_V3_VALIDATOR = owner_v3.validate_presented_windows_owner_policy_contract
_V3_GRAPH_MODULES = (
    owner_v3,
    owner_v3.deployment,
    owner_v3.observer_profile,
    owner_v3.observer_profile.deployment,
)


def _graph_constant_eligible(value: Any) -> bool:
    if type(value) in {str, int, bool, bytes, type(None)}:
        return True
    return type(value) in {tuple, frozenset} and all(
        _graph_constant_eligible(item) for item in value
    )


_V3_GRAPH_FUNCTION_SNAPSHOT = tuple(
    (
        module,
        name,
        value,
        value.__code__,
        value.__defaults__,
        value.__kwdefaults__,
        dict(value.__kwdefaults__) if value.__kwdefaults__ is not None else None,
    )
    for module in _V3_GRAPH_MODULES
    for name, value in inspect.getmembers(module, inspect.isfunction)
    if value.__module__ == module.__name__
)
_V3_GRAPH_CONSTANT_SNAPSHOT = tuple(
    (module, name, value, type(value))
    for module in _V3_GRAPH_MODULES
    for name, value in vars(module).items()
    if name.isupper() and _graph_constant_eligible(value)
)
_V3_GRAPH_REGEX_SNAPSHOT = tuple(
    (module, name, value, type(value), value.pattern, value.flags)
    for module in _V3_GRAPH_MODULES
    for name, value in vars(module).items()
    if name.isupper()
    and hasattr(value, "pattern")
    and hasattr(value, "flags")
)


def _identity_bound_reference(value: Any) -> bool:
    return isinstance(value, (types.ModuleType, type)) or callable(value)


def _global_value(function: Any, name: str) -> tuple[str, Any]:
    if name in function.__globals__:
        return "global", function.__globals__[name]
    builtins_value = function.__builtins__
    if isinstance(builtins_value, Mapping):
        return "builtin", builtins_value[name]
    return "builtin", getattr(builtins_value, name)


def _build_v3_reference_graph(
) -> tuple[tuple[Any, ...], tuple[Any, ...], tuple[Any, ...]]:
    globals_seen: set[tuple[int, str, str]] = set()
    attributes_seen: set[tuple[int, int, str]] = set()
    deref_seen: set[tuple[int, str]] = set()
    global_rows: list[tuple[Any, ...]] = []
    attribute_rows: list[tuple[Any, ...]] = []
    deref_rows: list[tuple[Any, ...]] = []
    for module, name, function, *_rest in _V3_GRAPH_FUNCTION_SNAPSHOT:
        function_label = f"{module.__name__}:{name}"
        instructions = tuple(dis.get_instructions(function))
        closure = {
            free_name: cell.cell_contents
            for free_name, cell in zip(
                function.__code__.co_freevars,
                function.__closure__ or (),
                strict=True,
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
    _V3_GRAPH_GLOBAL_REFERENCE_SNAPSHOT,
    _V3_GRAPH_ATTRIBUTE_REFERENCE_SNAPSHOT,
    _V3_GRAPH_DEREF_REFERENCE_SNAPSHOT,
) = _build_v3_reference_graph()


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
    if type(live) is not expected_type:
        return False
    expected_self = getattr(expected, "__self__", None)
    if callable(expected) and expected_self is owner:
        if (
            getattr(live, "__self__", None) is not owner
            or getattr(live, "__name__", None) != getattr(expected, "__name__", None)
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


def _referenced_function_snapshot() -> tuple[tuple[Any, ...], ...]:
    result: list[tuple[Any, ...]] = []
    seen: set[int] = set()
    values = (
        [row[4] for row in _V3_GRAPH_GLOBAL_REFERENCE_SNAPSHOT]
        + [row[4] for row in _V3_GRAPH_ATTRIBUTE_REFERENCE_SNAPSHOT]
        + [row[3] for row in _V3_GRAPH_DEREF_REFERENCE_SNAPSHOT]
    )
    for value in values:
        if not inspect.isfunction(value) or id(value) in seen:
            continue
        seen.add(id(value))
        result.append((
            value,
            value.__code__,
            value.__defaults__,
            value.__kwdefaults__,
            deepcopy(value.__kwdefaults__),
        ))
    return tuple(result)


_V3_GRAPH_REFERENCED_FUNCTION_SNAPSHOT = _referenced_function_snapshot()

RAW_ROLES = (
    "predecessor_policy_v3_body",
    "predecessor_policy_v3_signature",
    "packet_v2_public_key_pin",
    "policy_v4_body",
    "policy_v4_signature",
    "bootstrap_public_key_spki",
)

V4_SIGNATURE_FIELDS = tuple(sorted({
    "schema_version", "record_origin", "domain", "algorithm",
    "policy_body_schema", "policy_body_bytes_sha256",
    "policy_body_artifact_sha256", "policy_id", "policy_epoch",
    "predecessor_policy_v3_bytes_sha256", "predecessor_policy_v3_epoch",
    "predecessor_policy_v3_artifact_sha256",
    "predecessor_policy_v3_signature_bytes_sha256",
    "predecessor_policy_v3_signature_artifact_sha256",
    "predecessor_contract_receipt_sha256", "bootstrap_key_id",
    "bootstrap_public_key_fingerprint_sha256", "profile_artifact_sha256",
    "owner_anchor_sha256", "signature_rs_base64", "artifact_sha256",
}))

_V4_TRUE_FIELDS = (
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
_V4_FALSE_FIELDS = (
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
V4_RECEIPT_FIELDS = (
    "schema_version", "component_manifest_sha256",
    "predecessor_policy_v3_bytes_sha256",
    "predecessor_policy_v3_artifact_sha256",
    "predecessor_policy_v3_signature_bytes_sha256",
    "predecessor_policy_v3_signature_artifact_sha256",
    "predecessor_policy_v3_epoch", "predecessor_contract_receipt_sha256",
    "policy_v4_body_bytes_sha256", "policy_v4_body_artifact_sha256",
    "policy_v4_signature_bytes_sha256",
    "policy_v4_signature_artifact_sha256", "signature_input_sha256",
    "packet_v2_public_key_pin_bytes_sha256",
    "packet_v2_public_key_pin_artifact_sha256",
    "packet_v2_public_key_fingerprint_sha256",
    "packet_v2_owner_principal_sha256", "packet_v2_owner_anchor_sha256",
    "packet_v2_key_id", "packet_v2_key_epoch", "policy_id", "policy_epoch",
    "project_id", "trust_domain", "environment", "policy_purpose",
    "packet_v2_purpose", "profile_artifact_sha256", "owner_anchor_sha256",
    "max_preauthorization_ttl_seconds", "min_revocation_sequence",
    *_V4_TRUE_FIELDS, *_V4_FALSE_FIELDS,
    "credited_actual_source_claim_count", "credited_actual_a_context_review_count",
    "operational_effect", "gate_status", "receipt_sha256",
)

_TRUE_FIELDS = (
    "six_member_raw_bundle_exactly_bound",
    "five_json_members_strict_canonical",
    "json_artifact_self_hashes_verified",
    "predecessor_epoch_one_verified",
    "successor_epoch_two_verified",
    "predecessor_successor_hash_chain_verified",
    "v4_body_signature_cross_binding_verified",
    "packet_pin_profile_cross_binding_verified",
    "bootstrap_spki_fingerprint_cross_binding_verified",
    "scope_owner_and_purpose_cross_binding_verified",
    "child_exact_ordered_receipt_verified",
    "child_receipt_self_hash_verified",
    "child_truth_table_verified",
    "child_raw_hash_binding_independently_replayed",
    "successor_signature_input_independently_reconstructed",
    "successor_signature_mathematics_independently_verified",
    "predecessor_receipt_hash_independently_reconstructed",
)
_FALSE_FIELDS = (
    "producer_called_by_parent",
    "filesystem_observed_by_parent",
    "external_root_identity_pin_verified",
    "external_public_key_pin_provisioning_verified",
    "trusted_time_verified",
    "revocation_high_watermark_verified",
    "durable_nonce_state_verified",
    "external_root_authority_verified",
    "external_code_authority_verified",
    "os_write_deny_verified",
    "runtime_noninterference_verified",
    "actual_semantic_evidence_verified",
    "owner_authority_verified",
    "actual_authority_granted",
    "production_approval",
    "full_scan_approval",
    "p0_phase_exit",
    "action_applied",
)
_RECEIPT_FIELDS = (
    "schema_version", "component_manifest_sha256", "v4_component_manifest_sha256",
    "raw_role_sequence", "raw_sha256_by_role", "raw_bundle_projection_sha256",
    "bootstrap_public_key_spki_bytes_sha256", "predecessor_policy_epoch",
    "policy_v4_epoch", "policy_id", "project_id", "trust_domain",
    "environment", "policy_purpose", "packet_v2_key_id",
    "packet_v2_key_epoch", "child_receipt_declared_sha256",
    "child_receipt_full_canonical_sha256", *_TRUE_FIELDS, *_FALSE_FIELDS,
    "credited_actual_source_claim_count", "credited_actual_a_context_review_count",
    "operational_effect", "gate_status", "receipt_sha256",
)


class P0WindowsOwnerPolicyV4Epoch2FixedStoreParentError(ValueError):
    """The producer-free V4 store replay rejected its inputs."""


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _semantic_contract_projection() -> dict[str, Any]:
    return {
        "schemas": {
            "receipt": RECEIPT_SCHEMA,
            "v4_receipt": V4_RECEIPT_SCHEMA,
            "v3_body": V3_BODY_SCHEMA,
            "v3_signature": V3_SIGNATURE_SCHEMA,
            "v4_body": V4_BODY_SCHEMA,
            "v4_signature": V4_SIGNATURE_SCHEMA,
            "pin": PIN_SCHEMA,
            "v3_receipt": V3_RECEIPT_SCHEMA,
        },
        "gates": {
            "parent": GATE_STATUS,
            "v4": V4_GATE_STATUS,
            "v3": V3_GATE_STATUS,
        },
        "effects": {"parent": OPERATIONAL_EFFECT, "v4": V4_OPERATIONAL_EFFECT},
        "domains": {
            "v4_signature": V4_SIGNATURE_DOMAIN,
            "v3_policy": V3_POLICY_DOMAIN,
            "v3_signature": V3_SIGNATURE_DOMAIN,
        },
        "v4_signature_origin": V4_SIGNATURE_ORIGIN,
        "v4_signature_algorithm": V4_SIGNATURE_ALGORITHM,
        "v4_signature_encoding": "CANONICAL_BASE64_OF_EXACT_64_BYTE_P1363_LOW_S",
        "v4_component_manifest_sha256": V4_COMPONENT_MANIFEST_SHA256,
        "v3_validator_module": owner_v3.__name__,
        "v3_validator_function_count": len(_V3_GRAPH_FUNCTION_SNAPSHOT),
        "v3_validator_constant_count": len(_V3_GRAPH_CONSTANT_SNAPSHOT),
        "v3_validator_regex_count": len(_V3_GRAPH_REGEX_SNAPSHOT),
        "v3_global_reference_count": len(_V3_GRAPH_GLOBAL_REFERENCE_SNAPSHOT),
        "v3_attribute_reference_count": len(_V3_GRAPH_ATTRIBUTE_REFERENCE_SNAPSHOT),
        "v3_deref_reference_count": len(_V3_GRAPH_DEREF_REFERENCE_SNAPSHOT),
        "v3_referenced_function_count": len(
            _V3_GRAPH_REFERENCED_FUNCTION_SNAPSHOT
        ),
        "epochs": [EXPECTED_PREDECESSOR_EPOCH, EXPECTED_POLICY_EPOCH],
        "p256_order_hex": format(_P256_ORDER, "x"),
        "raw_roles": list(RAW_ROLES),
        "v4_signature_fields": list(V4_SIGNATURE_FIELDS),
        "v4_receipt_fields": list(V4_RECEIPT_FIELDS),
        "v4_true_fields": list(_V4_TRUE_FIELDS),
        "v4_false_fields": list(_V4_FALSE_FIELDS),
        "receipt_fields": list(_RECEIPT_FIELDS),
        "true_fields": list(_TRUE_FIELDS),
        "false_fields": list(_FALSE_FIELDS),
    }


SEMANTIC_CONTRACT_SHA256 = canonical_sha256(_semantic_contract_projection())
EXPECTED_SEMANTIC_CONTRACT_SHA256 = (
    "d2f423a1dd5c1f3953f394c3a14aa3a8a11006da144b0b3360e91c06be594575"
)


COMPONENT_MANIFEST = {
    "component": "p0_windows_owner_policy_v4_epoch2_fixed_store_parent_validator",
    "schemas": {"receipt": RECEIPT_SCHEMA, "child_receipt": V4_RECEIPT_SCHEMA},
    "raw_roles": RAW_ROLES,
    "expected_predecessor_epoch": EXPECTED_PREDECESSOR_EPOCH,
    "expected_policy_epoch": EXPECTED_POLICY_EPOCH,
    "v4_component_manifest_sha256": V4_COMPONENT_MANIFEST_SHA256,
    "semantic_contract_sha256": SEMANTIC_CONTRACT_SHA256,
    "architecture": "PRODUCER_FREE_SIX_RAW_MEMBER_AND_CHILD_RECEIPT_REPLAY",
    "public_apis": ("validate_v4_epoch2_fixed_store_parent_replay",),
    "authority_boundary": GATE_STATUS,
}
COMPONENT_MANIFEST_SHA256 = canonical_sha256(COMPONENT_MANIFEST)
EXPECTED_COMPONENT_MANIFEST_SHA256 = (
    "36eec436b81138357b87d5368029754ac846c901db75e640a0889adaadc209e8"
)


def _duplicate_rejecting_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise P0WindowsOwnerPolicyV4Epoch2FixedStoreParentError(
                "duplicate JSON member"
            )
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise P0WindowsOwnerPolicyV4Epoch2FixedStoreParentError(
        f"non-finite JSON constant: {value}"
    )


def _parse_canonical(raw: bytes, label: str) -> dict[str, Any]:
    if type(raw) is not bytes or not raw or len(raw) > 256_000:
        raise P0WindowsOwnerPolicyV4Epoch2FixedStoreParentError(
            f"{label} raw bytes are invalid"
        )
    try:
        text = raw.decode("utf-8", errors="strict")
        value = json.loads(
            text,
            object_pairs_hook=_duplicate_rejecting_object,
            parse_constant=_reject_constant,
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise P0WindowsOwnerPolicyV4Epoch2FixedStoreParentError(
            f"{label} is not strict JSON"
        ) from exc
    if type(value) is not dict or raw != canonical_bytes(value) + b"\n":
        raise P0WindowsOwnerPolicyV4Epoch2FixedStoreParentError(
            f"{label} is not canonical JSON file bytes"
        )
    return value


def _artifact_self_hash(row: Mapping[str, Any], label: str) -> None:
    value = row.get("artifact_sha256")
    material = {key: item for key, item in row.items() if key != "artifact_sha256"}
    if (
        type(value) is not str
        or len(value) != 64
        or not hmac.compare_digest(value, canonical_sha256(material))
    ):
        raise P0WindowsOwnerPolicyV4Epoch2FixedStoreParentError(
            f"{label} artifact self-hash mismatch"
        )


def _lower_sha256(value: Any, label: str) -> str:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise P0WindowsOwnerPolicyV4Epoch2FixedStoreParentError(
            f"{label} must be lowercase SHA-256"
        )
    return value


def _strict_child(receipt: Any) -> dict[str, Any]:
    integer_fields = {
        "predecessor_policy_v3_epoch",
        "packet_v2_key_epoch",
        "policy_epoch",
        "max_preauthorization_ttl_seconds",
        "min_revocation_sequence",
        "credited_actual_source_claim_count",
        "credited_actual_a_context_review_count",
    }
    string_fields = set(V4_RECEIPT_FIELDS) - set(_V4_TRUE_FIELDS) - set(
        _V4_FALSE_FIELDS
    ) - integer_fields
    if (
        type(receipt) is not dict
        or tuple(receipt) != V4_RECEIPT_FIELDS
        or receipt.get("schema_version") != V4_RECEIPT_SCHEMA
        or receipt.get("component_manifest_sha256")
        != V4_COMPONENT_MANIFEST_SHA256
        or receipt.get("gate_status") != V4_GATE_STATUS
        or receipt.get("operational_effect") != V4_OPERATIONAL_EFFECT
        or any(receipt.get(field) is not True for field in _V4_TRUE_FIELDS)
        or any(receipt.get(field) is not False for field in _V4_FALSE_FIELDS)
        or any(type(receipt.get(field)) is not int for field in integer_fields)
        or any(type(receipt.get(field)) is not str for field in string_fields)
        or receipt.get("credited_actual_source_claim_count") != 0
        or receipt.get("credited_actual_a_context_review_count") != 0
    ):
        raise P0WindowsOwnerPolicyV4Epoch2FixedStoreParentError(
            "V4 child receipt exact schema/truth-table mismatch"
        )
    for field in V4_RECEIPT_FIELDS:
        if field.endswith("_sha256"):
            _lower_sha256(receipt[field], f"V4 child {field}")
    material = dict(receipt)
    declared = material.pop("receipt_sha256")
    if (
        type(declared) is not str
        or not hmac.compare_digest(declared, canonical_sha256(material))
    ):
        raise P0WindowsOwnerPolicyV4Epoch2FixedStoreParentError(
            "V4 child receipt self-hash mismatch"
        )
    return receipt


def _expected_predecessor_receipt_sha256(
    *, body: Mapping[str, Any], body_raw: bytes,
    signature: Mapping[str, Any], signature_raw: bytes,
) -> str:
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
    false_fields = (
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
        "action_applied",
    )
    body_sha = hashlib.sha256(body_raw).hexdigest()
    material: dict[str, Any] = {
        "schema_version": V3_RECEIPT_SCHEMA,
        "gate_status": V3_GATE_STATUS,
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
        **{field: False for field in false_fields},
        "policy_schema_version": V3_BODY_SCHEMA,
        "policy_domain": V3_POLICY_DOMAIN,
        "signature_schema_version": V3_SIGNATURE_SCHEMA,
        "signature_domain": V3_SIGNATURE_DOMAIN,
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
    }
    return canonical_sha256(material)


def _verify_v4_signature_math(
    *, signature: Mapping[str, Any], body: Mapping[str, Any], body_raw: bytes,
    bootstrap_public_key_spki_der: bytes,
) -> str:
    if tuple(signature) != V4_SIGNATURE_FIELDS:
        raise P0WindowsOwnerPolicyV4Epoch2FixedStoreParentError(
            "policy V4 signature exact ordered fields mismatch"
        )
    expected = {
        "schema_version": V4_SIGNATURE_SCHEMA,
        "record_origin": V4_SIGNATURE_ORIGIN,
        "domain": V4_SIGNATURE_DOMAIN,
        "algorithm": V4_SIGNATURE_ALGORITHM,
        "policy_body_schema": V4_BODY_SCHEMA,
        "policy_body_bytes_sha256": hashlib.sha256(body_raw).hexdigest(),
        "policy_body_artifact_sha256": body["artifact_sha256"],
        "policy_id": body["policy_id"],
        "policy_epoch": body["policy_epoch"],
        "predecessor_policy_v3_bytes_sha256": body[
            "predecessor_policy_v3_bytes_sha256"
        ],
        "predecessor_policy_v3_epoch": body["predecessor_policy_v3_epoch"],
        "predecessor_policy_v3_artifact_sha256": body[
            "predecessor_policy_v3_artifact_sha256"
        ],
        "predecessor_policy_v3_signature_bytes_sha256": body[
            "predecessor_policy_v3_signature_bytes_sha256"
        ],
        "predecessor_policy_v3_signature_artifact_sha256": body[
            "predecessor_policy_v3_signature_artifact_sha256"
        ],
        "predecessor_contract_receipt_sha256": body[
            "predecessor_contract_receipt_sha256"
        ],
        "bootstrap_key_id": body["bootstrap_key_id"],
        "bootstrap_public_key_fingerprint_sha256": body[
            "bootstrap_public_key_fingerprint_sha256"
        ],
        "profile_artifact_sha256": body["packet_v2_preauthorization_profile"][
            "profile_artifact_sha256"
        ],
        "owner_anchor_sha256": body["owner_anchor_sha256"],
    }
    if any(
        signature.get(field) != value
        or type(signature.get(field)) is not type(value)
        for field, value in expected.items()
    ):
        raise P0WindowsOwnerPolicyV4Epoch2FixedStoreParentError(
            "policy V4 signature/body cross-binding mismatch"
        )
    encoded = signature.get("signature_rs_base64")
    if type(encoded) is not str or not encoded or any(ch.isspace() for ch in encoded):
        raise P0WindowsOwnerPolicyV4Epoch2FixedStoreParentError(
            "policy V4 signature is not canonical Base64"
        )
    try:
        raw_signature = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise P0WindowsOwnerPolicyV4Epoch2FixedStoreParentError(
            "policy V4 signature is not canonical Base64"
        ) from exc
    if (
        len(raw_signature) != 64
        or base64.b64encode(raw_signature).decode("ascii") != encoded
    ):
        raise P0WindowsOwnerPolicyV4Epoch2FixedStoreParentError(
            "policy V4 signature is not exact P1363"
        )
    r = int.from_bytes(raw_signature[:32], "big")
    s = int.from_bytes(raw_signature[32:], "big")
    if not 0 < r < _P256_ORDER or not 0 < s <= _P256_ORDER // 2:
        raise P0WindowsOwnerPolicyV4Epoch2FixedStoreParentError(
            "policy V4 signature scalars are not bounded low-S P-256"
        )
    material = canonical_bytes({
        key: signature[key]
        for key in V4_SIGNATURE_FIELDS
        if key not in {"signature_rs_base64", "artifact_sha256"}
    })
    if (
        type(bootstrap_public_key_spki_der) is not bytes
        or not bootstrap_public_key_spki_der
        or len(bootstrap_public_key_spki_der) > 1024
        or hashlib.sha256(bootstrap_public_key_spki_der).hexdigest()
        != body["bootstrap_public_key_fingerprint_sha256"]
    ):
        raise P0WindowsOwnerPolicyV4Epoch2FixedStoreParentError(
            "bootstrap public key bytes/fingerprint mismatch"
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
            raise P0WindowsOwnerPolicyV4Epoch2FixedStoreParentError(
                "bootstrap public key must be canonical P-256 DER SPKI"
            )
        public_key.verify(
            utils.encode_dss_signature(r, s), material, ec.ECDSA(hashes.SHA256())
        )
    except ImportError as exc:
        raise P0WindowsOwnerPolicyV4Epoch2FixedStoreParentError(
            "cryptography is required for independent V4 verification"
        ) from exc
    except (ValueError, TypeError, InvalidSignature, UnsupportedAlgorithm) as exc:
        raise P0WindowsOwnerPolicyV4Epoch2FixedStoreParentError(
            "independent policy V4 signature mathematics failed"
        ) from exc
    return hashlib.sha256(material).hexdigest()


def _validate(
    *, raw_bundle: Mapping[str, bytes], child_receipt: Mapping[str, Any]
) -> dict[str, Any]:
    if (
        type(raw_bundle) is not dict
        or tuple(raw_bundle) != RAW_ROLES
        or any(type(raw_bundle[role]) is not bytes for role in RAW_ROLES)
    ):
        raise P0WindowsOwnerPolicyV4Epoch2FixedStoreParentError(
            "six-member raw bundle exact inventory mismatch"
        )
    child = _strict_child(child_receipt)
    predecessor = _parse_canonical(
        raw_bundle["predecessor_policy_v3_body"], "predecessor V3 body"
    )
    predecessor_signature = _parse_canonical(
        raw_bundle["predecessor_policy_v3_signature"], "predecessor V3 signature"
    )
    pin = _parse_canonical(raw_bundle["packet_v2_public_key_pin"], "packet V2 pin")
    body = _parse_canonical(raw_bundle["policy_v4_body"], "policy V4 body")
    signature = _parse_canonical(
        raw_bundle["policy_v4_signature"], "policy V4 signature"
    )
    for row, label in (
        (predecessor, "predecessor V3 body"),
        (predecessor_signature, "predecessor V3 signature"),
        (pin, "packet V2 pin"),
        (body, "policy V4 body"),
        (signature, "policy V4 signature"),
    ):
        _artifact_self_hash(row, label)

    raw_hashes = {
        role: hashlib.sha256(raw_bundle[role]).hexdigest() for role in RAW_ROLES
    }
    profile = body.get("packet_v2_preauthorization_profile")
    if type(profile) is not dict:
        raise P0WindowsOwnerPolicyV4Epoch2FixedStoreParentError(
            "V4 packet profile is missing"
        )
    profile_material = {
        key: item for key, item in profile.items() if key != "profile_artifact_sha256"
    }
    if profile.get("profile_artifact_sha256") != canonical_sha256(profile_material):
        raise P0WindowsOwnerPolicyV4Epoch2FixedStoreParentError(
            "V4 packet profile self-hash mismatch"
        )

    try:
        validated_predecessor_receipt = _V3_VALIDATOR(
            policy_body_bytes=raw_bundle["predecessor_policy_v3_body"],
            policy_signature_bytes=raw_bundle["predecessor_policy_v3_signature"],
        )
    except owner_v3.P0WindowsOwnerPolicyContractError as exc:
        raise P0WindowsOwnerPolicyV4Epoch2FixedStoreParentError(
            "independent predecessor V3 structural replay failed"
        ) from exc
    expected_predecessor_receipt_sha256 = _expected_predecessor_receipt_sha256(
        body=predecessor,
        body_raw=raw_bundle["predecessor_policy_v3_body"],
        signature=predecessor_signature,
        signature_raw=raw_bundle["predecessor_policy_v3_signature"],
    )
    if (
        type(validated_predecessor_receipt) is not dict
        or validated_predecessor_receipt.get("receipt_sha256")
        != expected_predecessor_receipt_sha256
    ):
        raise P0WindowsOwnerPolicyV4Epoch2FixedStoreParentError(
            "predecessor V3 receipt independent reconstruction mismatch"
        )
    signature_input_sha256 = _verify_v4_signature_math(
        signature=signature,
        body=body,
        body_raw=raw_bundle["policy_v4_body"],
        bootstrap_public_key_spki_der=raw_bundle["bootstrap_public_key_spki"],
    )

    expected_child = {
        "predecessor_policy_v3_bytes_sha256": raw_hashes[
            "predecessor_policy_v3_body"
        ],
        "predecessor_policy_v3_artifact_sha256": predecessor.get("artifact_sha256"),
        "predecessor_policy_v3_signature_bytes_sha256": raw_hashes[
            "predecessor_policy_v3_signature"
        ],
        "predecessor_policy_v3_signature_artifact_sha256": (
            predecessor_signature.get("artifact_sha256")
        ),
        "predecessor_policy_v3_epoch": EXPECTED_PREDECESSOR_EPOCH,
        "predecessor_contract_receipt_sha256": (
            expected_predecessor_receipt_sha256
        ),
        "policy_v4_body_bytes_sha256": raw_hashes["policy_v4_body"],
        "policy_v4_body_artifact_sha256": body.get("artifact_sha256"),
        "policy_v4_signature_bytes_sha256": raw_hashes["policy_v4_signature"],
        "policy_v4_signature_artifact_sha256": signature.get("artifact_sha256"),
        "signature_input_sha256": signature_input_sha256,
        "packet_v2_public_key_pin_bytes_sha256": raw_hashes[
            "packet_v2_public_key_pin"
        ],
        "packet_v2_public_key_pin_artifact_sha256": pin.get("artifact_sha256"),
        "packet_v2_public_key_fingerprint_sha256": pin.get(
            "public_key_fingerprint_sha256"
        ),
        "packet_v2_owner_principal_sha256": pin.get("owner_principal_sha256"),
        "packet_v2_owner_anchor_sha256": pin.get("owner_anchor_sha256"),
        "packet_v2_key_id": pin.get("key_id"),
        "packet_v2_key_epoch": pin.get("key_epoch"),
        "policy_id": body.get("policy_id"),
        "policy_epoch": EXPECTED_POLICY_EPOCH,
        "project_id": body.get("project_id"),
        "trust_domain": body.get("trust_domain"),
        "environment": body.get("environment"),
        "policy_purpose": body.get("policy_purpose"),
        "packet_v2_purpose": profile.get("packet_v2_purpose"),
        "profile_artifact_sha256": profile.get("profile_artifact_sha256"),
        "owner_anchor_sha256": body.get("owner_anchor_sha256"),
        "max_preauthorization_ttl_seconds": profile.get(
            "max_preauthorization_ttl_seconds"
        ),
        "min_revocation_sequence": profile.get("min_revocation_sequence"),
    }
    if any(child.get(field) != expected for field, expected in expected_child.items()):
        raise P0WindowsOwnerPolicyV4Epoch2FixedStoreParentError(
            "V4 child receipt/raw projection mismatch"
        )

    if (
        predecessor.get("schema_version") != V3_BODY_SCHEMA
        or predecessor_signature.get("schema_version") != V3_SIGNATURE_SCHEMA
        or body.get("schema_version") != V4_BODY_SCHEMA
        or signature.get("schema_version") != V4_SIGNATURE_SCHEMA
        or pin.get("schema_version") != PIN_SCHEMA
        or type(predecessor.get("policy_epoch")) is not int
        or predecessor.get("policy_epoch") != EXPECTED_PREDECESSOR_EPOCH
        or type(body.get("policy_epoch")) is not int
        or body.get("policy_epoch") != EXPECTED_POLICY_EPOCH
        or body.get("predecessor_policy_v3_epoch") != EXPECTED_PREDECESSOR_EPOCH
        or body.get("predecessor_policy_v3_bytes_sha256")
        != raw_hashes["predecessor_policy_v3_body"]
        or body.get("predecessor_policy_v3_signature_bytes_sha256")
        != raw_hashes["predecessor_policy_v3_signature"]
        or signature.get("policy_body_bytes_sha256") != raw_hashes["policy_v4_body"]
        or signature.get("policy_body_artifact_sha256") != body.get("artifact_sha256")
        or body.get("predecessor_contract_receipt_sha256")
        != expected_predecessor_receipt_sha256
        or signature.get("predecessor_contract_receipt_sha256")
        != expected_predecessor_receipt_sha256
        or profile.get("public_key_pin_bytes_sha256")
        != raw_hashes["packet_v2_public_key_pin"]
        or profile.get("public_key_pin_artifact_sha256") != pin.get("artifact_sha256")
        or hashlib.sha256(raw_bundle["bootstrap_public_key_spki"]).hexdigest()
        != body.get("bootstrap_public_key_fingerprint_sha256")
        or body.get("project_id") != pin.get("project_id")
        or body.get("trust_domain") != pin.get("trust_domain")
        or body.get("environment") != pin.get("environment")
        or body.get("owner_principal_sha256") != pin.get("owner_principal_sha256")
        or profile.get("key_id") != pin.get("key_id")
        or profile.get("key_epoch") != pin.get("key_epoch")
        or profile.get("packet_v2_purpose") != pin.get("purpose")
    ):
        raise P0WindowsOwnerPolicyV4Epoch2FixedStoreParentError(
            "V3/V4/pin/SPKI epoch, chain, or scope mismatch"
        )

    material = {
        "schema_version": RECEIPT_SCHEMA,
        "component_manifest_sha256": COMPONENT_MANIFEST_SHA256,
        "v4_component_manifest_sha256": V4_COMPONENT_MANIFEST_SHA256,
        "raw_role_sequence": list(RAW_ROLES),
        "raw_sha256_by_role": raw_hashes,
        "raw_bundle_projection_sha256": canonical_sha256(raw_hashes),
        "bootstrap_public_key_spki_bytes_sha256": raw_hashes[
            "bootstrap_public_key_spki"
        ],
        "predecessor_policy_epoch": EXPECTED_PREDECESSOR_EPOCH,
        "policy_v4_epoch": EXPECTED_POLICY_EPOCH,
        "policy_id": body["policy_id"],
        "project_id": body["project_id"],
        "trust_domain": body["trust_domain"],
        "environment": body["environment"],
        "policy_purpose": body["policy_purpose"],
        "packet_v2_key_id": pin["key_id"],
        "packet_v2_key_epoch": pin["key_epoch"],
        "child_receipt_declared_sha256": child["receipt_sha256"],
        "child_receipt_full_canonical_sha256": canonical_sha256(child),
        **{field: True for field in _TRUE_FIELDS},
        **{field: False for field in _FALSE_FIELDS},
        "credited_actual_source_claim_count": 0,
        "credited_actual_a_context_review_count": 0,
        "operational_effect": OPERATIONAL_EFFECT,
        "gate_status": GATE_STATUS,
    }
    if tuple(material) + ("receipt_sha256",) != _RECEIPT_FIELDS:
        raise P0WindowsOwnerPolicyV4Epoch2FixedStoreParentError(
            "parent replay receipt exact field drift"
        )
    return {**material, "receipt_sha256": canonical_sha256(material)}


def _code_sha256(value: Any) -> str:
    code = getattr(value, "__code__", None)
    if code is None:
        return ""
    return hashlib.sha256(
        marshal.dumps(code)
        + repr(getattr(value, "__defaults__", None)).encode("utf-8")
        + repr(getattr(value, "__kwdefaults__", None)).encode("utf-8")
    ).hexdigest()


_SELF_HELPER_PINS = {
    name: (value, _code_sha256(value))
    for name, value in (
        ("canonical_bytes", canonical_bytes),
        ("canonical_sha256", canonical_sha256),
        ("_graph_constant_eligible", _graph_constant_eligible),
        ("_identity_bound_reference", _identity_bound_reference),
        ("_global_value", _global_value),
        ("_build_v3_reference_graph", _build_v3_reference_graph),
        ("_attribute_reference_matches", _attribute_reference_matches),
        ("_referenced_function_snapshot", _referenced_function_snapshot),
        ("_semantic_contract_projection", _semantic_contract_projection),
        ("_duplicate_rejecting_object", _duplicate_rejecting_object),
        ("_reject_constant", _reject_constant),
        ("_parse_canonical", _parse_canonical),
        ("_artifact_self_hash", _artifact_self_hash),
        ("_lower_sha256", _lower_sha256),
        ("_strict_child", _strict_child),
        ("_expected_predecessor_receipt_sha256", _expected_predecessor_receipt_sha256),
        ("_verify_v4_signature_math", _verify_v4_signature_math),
        ("_validate", _validate),
    )
}
_HASHLIB_MODULE_PIN = hashlib
_HMAC_MODULE_PIN = hmac
_JSON_MODULE_PIN = json
_BASE64_MODULE_PIN = base64
_BINASCII_MODULE_PIN = binascii
_HASHLIB_SHA256_PIN = hashlib.sha256
_HMAC_COMPARE_DIGEST_PIN = hmac.compare_digest
_JSON_LOADS_PIN = json.loads
_JSON_DUMPS_PIN = json.dumps
_BASE64_B64DECODE_PIN = base64.b64decode
_BASE64_B64ENCODE_PIN = base64.b64encode
_OWNER_V3_MODULE_PIN = owner_v3
_OWNER_V3_DEPLOYMENT_MODULE_PIN = owner_v3.deployment
_OWNER_V3_OBSERVER_MODULE_PIN = owner_v3.observer_profile
_OWNER_V3_OBSERVER_DEPLOYMENT_MODULE_PIN = owner_v3.observer_profile.deployment


def _assert_parent_integrity() -> None:
    if (
        hashlib is not _HASHLIB_MODULE_PIN
        or hmac is not _HMAC_MODULE_PIN
        or json is not _JSON_MODULE_PIN
        or base64 is not _BASE64_MODULE_PIN
        or binascii is not _BINASCII_MODULE_PIN
        or hashlib.sha256 is not _HASHLIB_SHA256_PIN
        or hmac.compare_digest is not _HMAC_COMPARE_DIGEST_PIN
        or json.loads is not _JSON_LOADS_PIN
        or json.dumps is not _JSON_DUMPS_PIN
        or base64.b64decode is not _BASE64_B64DECODE_PIN
        or base64.b64encode is not _BASE64_B64ENCODE_PIN
        or owner_v3 is not _OWNER_V3_MODULE_PIN
        or owner_v3.deployment is not _OWNER_V3_DEPLOYMENT_MODULE_PIN
        or owner_v3.observer_profile is not _OWNER_V3_OBSERVER_MODULE_PIN
        or owner_v3.observer_profile.deployment
        is not _OWNER_V3_OBSERVER_DEPLOYMENT_MODULE_PIN
        or owner_v3.validate_presented_windows_owner_policy_contract
        is not _V3_VALIDATOR
        or SEMANTIC_CONTRACT_SHA256 != EXPECTED_SEMANTIC_CONTRACT_SHA256
        or canonical_sha256(_semantic_contract_projection())
        != EXPECTED_SEMANTIC_CONTRACT_SHA256
        or canonical_sha256(COMPONENT_MANIFEST)
        != EXPECTED_COMPONENT_MANIFEST_SHA256
    ):
        raise P0WindowsOwnerPolicyV4Epoch2FixedStoreParentError(
            "parent replay component/module integrity drift"
        )
    for (
        module, name, expected, expected_code, expected_defaults,
        expected_kwdefaults, expected_kwdefaults_value,
    ) in _V3_GRAPH_FUNCTION_SNAPSHOT:
        live = getattr(module, name, None)
        if (
            live is not expected
            or live.__code__ is not expected_code
            or live.__defaults__ is not expected_defaults
            or live.__kwdefaults__ is not expected_kwdefaults
            or live.__kwdefaults__ != expected_kwdefaults_value
        ):
            raise P0WindowsOwnerPolicyV4Epoch2FixedStoreParentError(
                f"predecessor V3 validation graph drift: {module.__name__}.{name}"
            )
    for module, name, expected, expected_type in _V3_GRAPH_CONSTANT_SNAPSHOT:
        live = getattr(module, name, None)
        if type(live) is not expected_type or live != expected:
            raise P0WindowsOwnerPolicyV4Epoch2FixedStoreParentError(
                f"predecessor V3 validation constant drift: {module.__name__}.{name}"
            )
    for (
        module, name, expected, expected_type, expected_pattern, expected_flags,
    ) in _V3_GRAPH_REGEX_SNAPSHOT:
        live = getattr(module, name, None)
        if (
            live is not expected
            or type(live) is not expected_type
            or live.pattern != expected_pattern
            or live.flags != expected_flags
        ):
            raise P0WindowsOwnerPolicyV4Epoch2FixedStoreParentError(
                f"predecessor V3 validation regex drift: {module.__name__}.{name}"
            )
    for (
        function, function_label, source, name, expected,
        expected_type, expected_value,
    ) in _V3_GRAPH_GLOBAL_REFERENCE_SNAPSHOT:
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
            raise P0WindowsOwnerPolicyV4Epoch2FixedStoreParentError(
                f"predecessor V3 referenced global drift: {function_label}:{name}"
            )
    for (
        function_label, path, owner, attribute, expected,
        expected_type, expected_value, expected_static,
        expected_static_type, expected_static_value,
    ) in _V3_GRAPH_ATTRIBUTE_REFERENCE_SNAPSHOT:
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
            raise P0WindowsOwnerPolicyV4Epoch2FixedStoreParentError(
                f"predecessor V3 referenced attribute drift: "
                f"{function_label}:{path}.{attribute}"
            )
    for (
        function, function_label, name, expected, expected_type,
        expected_value,
    ) in _V3_GRAPH_DEREF_REFERENCE_SNAPSHOT:
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
            raise P0WindowsOwnerPolicyV4Epoch2FixedStoreParentError(
                f"predecessor V3 referenced closure drift: {function_label}:{name}"
            )
    for function, code, defaults, kwdefaults, kwdefaults_value in (
        _V3_GRAPH_REFERENCED_FUNCTION_SNAPSHOT
    ):
        if (
            function.__code__ is not code
            or function.__defaults__ is not defaults
            or function.__kwdefaults__ is not kwdefaults
            or function.__kwdefaults__ != kwdefaults_value
        ):
            raise P0WindowsOwnerPolicyV4Epoch2FixedStoreParentError(
                "predecessor V3 referenced function code/default drift"
            )
    namespace = globals()
    for name, (expected, expected_code) in _SELF_HELPER_PINS.items():
        live = namespace.get(name)
        if live is not expected or _code_sha256(live) != expected_code:
            raise P0WindowsOwnerPolicyV4Epoch2FixedStoreParentError(
                f"parent replay helper integrity drift: {name}"
            )


def validate_v4_epoch2_fixed_store_parent_replay(
    *, raw_bundle: Mapping[str, bytes], child_receipt: Mapping[str, Any]
) -> dict[str, Any]:
    """Independently replay a V4 child receipt without calling its producer."""

    _assert_parent_integrity()
    try:
        receipt = _validate(raw_bundle=raw_bundle, child_receipt=child_receipt)
        _assert_parent_integrity()
        return receipt
    except P0WindowsOwnerPolicyV4Epoch2FixedStoreParentError:
        raise
    except (KeyError, TypeError, ValueError, AttributeError, UnicodeError) as exc:
        raise P0WindowsOwnerPolicyV4Epoch2FixedStoreParentError(
            "malformed V4 epoch2 parent replay input"
        ) from exc


__all__ = [
    "COMPONENT_MANIFEST",
    "COMPONENT_MANIFEST_SHA256",
    "EXPECTED_COMPONENT_MANIFEST_SHA256",
    "GATE_STATUS",
    "P0WindowsOwnerPolicyV4Epoch2FixedStoreParentError",
    "RAW_ROLES",
    "RECEIPT_SCHEMA",
    "V4_COMPONENT_MANIFEST_SHA256",
    "validate_v4_epoch2_fixed_store_parent_replay",
]
