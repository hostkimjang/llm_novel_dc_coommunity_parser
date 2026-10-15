"""Producer-free replay for the live V3 -> embedded V4 transition.

The component proves only byte continuity and detached P-256 signature
mathematics under the public key presented in the V4 bundle.  The presented
key is deliberately not promoted to an externally provisioned trust anchor.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
from typing import Any, Mapping

from . import p0_external_owner_asymmetric_signature as asymmetric
from . import p0_windows_owner_policy_contract as v3
from . import p0_windows_owner_policy_v4_epoch2_fixed_store as v4_fixed
from . import p0_windows_owner_policy_v4_epoch2_fixed_store_parent_validator as v4_parent


RECEIPT_SCHEMA = "p0_windows_owner_policy_v4_transition_parent_receipt_v1"
GATE_STATUS = "NO_GO_V3_V4_TRANSITION_PARENT_COMPONENT_ONLY"
OPERATIONAL_EFFECT = "NONE_PURE_REPLAY"
P256_ORDER = int(
    "FFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551", 16
)
TRANSITION_RAW_ROLES = (
    "live_v3_policy_body",
    "live_v3_policy_signature",
    "live_v3_operational_pin",
    *v4_parent.RAW_ROLES,
)
_TRUE_FIELDS = (
    "nine_member_transition_bundle_exactly_bound",
    "live_v3_contract_validated",
    "live_v3_receipt_independently_reconstructed",
    "live_v3_operational_pin_exactly_bound",
    "live_v3_body_exactly_matches_embedded_predecessor",
    "live_v3_signature_exactly_matches_embedded_predecessor",
    "predecessor_epoch_one_verified",
    "successor_epoch_two_verified",
    "epoch_one_to_two_transition_verified",
    "presented_spki_canonical_p256_verified",
    "predecessor_signature_canonical_low_s_verified",
    "predecessor_signature_mathematics_verified",
    "successor_signature_mathematics_verified",
    "v4_parent_receipt_strictly_replayed",
)
_FALSE_FIELDS = (
    "producer_called_by_parent",
    "filesystem_observed_by_parent",
    "external_root_identity_pin_verified",
    "bootstrap_public_key_independently_pinned",
    "external_public_key_pin_provisioning_verified",
    "external_root_authority_verified",
    "external_code_authority_verified",
    "trusted_time_verified",
    "revocation_high_watermark_verified",
    "durable_nonce_state_verified",
    "os_write_deny_verified",
    "signed_native_runtime_witness_verified",
    "runtime_noninterference_verified",
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
_RECEIPT_FIELDS = (
    "schema_version", "gate_status", "decision", "raw_role_sequence",
    "raw_sha256_by_role", "raw_bundle_projection_sha256", "policy_id",
    "predecessor_policy_epoch", "policy_v4_epoch",
    "predecessor_signature_input_sha256", "predecessor_contract_receipt_sha256",
    "presented_bootstrap_spki_sha256", "v4_parent_declared_sha256",
    "v4_parent_full_canonical_sha256", *_TRUE_FIELDS, *_FALSE_FIELDS,
    "credited_actual_source_claim_count", "credited_actual_a_context_review_count",
    "operational_effect", "receipt_sha256",
)


def _semantic_contract_projection() -> dict[str, Any]:
    return {
        "schema": RECEIPT_SCHEMA, "gate_status": GATE_STATUS,
        "operational_effect": OPERATIONAL_EFFECT,
        "raw_roles": list(TRANSITION_RAW_ROLES),
        "true_fields": list(_TRUE_FIELDS), "false_fields": list(_FALSE_FIELDS),
        "v3_receipt_fields": list(_V3_RECEIPT_FIELDS),
        "v3_receipt_true_fields": list(_V3_RECEIPT_TRUE_FIELDS),
        "v3_receipt_false_fields": list(_V3_RECEIPT_FALSE_FIELDS),
        "receipt_fields": list(_RECEIPT_FIELDS),
        "v4_parent_receipt_fields": list(v4_parent._RECEIPT_FIELDS),
        "public_api": "validate_windows_owner_policy_v4_transition_parent",
    }


SEMANTIC_CONTRACT_SHA256 = "961f7e98c50551c58955510d57b3cc61c794393611760d6f97b8f412a6bee9a5"
EXPECTED_SEMANTIC_CONTRACT_SHA256 = "961f7e98c50551c58955510d57b3cc61c794393611760d6f97b8f412a6bee9a5"
COMPONENT_MANIFEST = {
    "component": "p0_windows_owner_policy_v4_transition_parent_validator",
    "receipt_schema": RECEIPT_SCHEMA,
    "semantic_contract_sha256": SEMANTIC_CONTRACT_SHA256,
    "v4_parent_component_manifest_sha256": v4_parent.EXPECTED_COMPONENT_MANIFEST_SHA256,
    "authority_boundary": GATE_STATUS,
}
COMPONENT_MANIFEST_SHA256 = "467bf7cd295640846c61405d18b7711fa426c45b1b96612cbd3d68951917ba4d"
EXPECTED_COMPONENT_MANIFEST_SHA256 = "467bf7cd295640846c61405d18b7711fa426c45b1b96612cbd3d68951917ba4d"


class P0WindowsOwnerPolicyV4TransitionParentError(ValueError):
    """The transition replay could not fail closed."""


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _stable_code_digest(value: Any) -> str:
    code = getattr(value, "__code__", None)
    if code is None:
        return ""
    projection = (
        code.co_code.hex(), repr(code.co_consts), code.co_names, code.co_varnames,
        code.co_freevars, code.co_cellvars, code.co_argcount,
        code.co_posonlyargcount, code.co_kwonlyargcount, code.co_flags,
    )
    return hashlib.sha256(repr(projection).encode("utf-8")).hexdigest()


def _parse(raw: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise P0WindowsOwnerPolicyV4TransitionParentError(
            f"{label} is not canonical JSON"
        ) from exc
    if type(value) is not dict or v3.json_file_bytes(value) != raw:
        raise P0WindowsOwnerPolicyV4TransitionParentError(
            f"{label} is not canonical JSON-file bytes"
        )
    return value


_V3_RECEIPT_FIELDS = (
    "schema_version", "gate_status", "policy_id", "policy_epoch",
    "policy_body_bytes_sha256", "policy_body_artifact_sha256",
    "policy_signature_bytes_sha256", "policy_signature_artifact_sha256",
    "store_id", "owner_principal_sha256", "owner_anchor_sha256",
    "owner_anchor_scope", "owner_anchor_excludes_pin_transport_hashes_by_design",
    "full_policy_identity_sha256", "acl_template_sha256",
    "operational_key_projection_sha256", "object_identity_projection_sha256",
    "security_template_sha256_by_role", "strict_canonical_policy_body_verified",
    "strict_canonical_detached_signature_envelope_verified",
    "owner_and_verifier_sid_disjoint_contract_verified",
    "fixed_generation_layout_contract_verified",
    "exact_standard_explicit_ace_profile_contract_verified",
    "derived_owner_anchor_cross_binding_verified",
    "detached_signature_body_hash_cross_binding_verified",
    "bootstrap_signature_mathematics_verified", "bootstrap_public_key_independently_pinned",
    "fixed_policy_store_discovery_verified", "live_windows_binary_acl_verified",
    "effective_verifier_token_verified", "linked_elevated_token_absence_verified",
    "independent_owner_policy_state_verified", "external_public_key_pin_provisioning_verified",
    "trusted_time_verified", "revocation_current_verified",
    "rollback_resistant_policy_epoch_verified", "rollback_resistant_key_epoch_verified",
    "durable_nonce_state_verified", "external_code_authority_verified",
    "owner_authority_verified", "actual_authority_granted",
    "actual_semantic_evidence_verified", "production_approval", "full_scan_approval",
    "p0_phase_exit", "action_applied", "policy_schema_version", "policy_domain",
    "signature_schema_version", "signature_domain", "deployment_projection_sha256",
    "native_observer_profile_sha256", "deployment_projection_contract_verified",
    "native_observer_profile_contract_verified",
    "policy_verifier_sid_deployment_service_sid_cross_binding_verified",
    "policy_deployment_native_observer_profile_cross_binding_verified",
    "operational_and_observer_key_role_separation_contract_verified",
    "future_native_observer_authority_requires_v3", "future_authority_policy_version_eligible",
    "positive_native_observer_policy_profile_complete", "receipt_sha256",
)
_V3_RECEIPT_TRUE_FIELDS = (
    "owner_anchor_excludes_pin_transport_hashes_by_design",
    "strict_canonical_policy_body_verified", "strict_canonical_detached_signature_envelope_verified",
    "owner_and_verifier_sid_disjoint_contract_verified", "fixed_generation_layout_contract_verified",
    "exact_standard_explicit_ace_profile_contract_verified",
    "derived_owner_anchor_cross_binding_verified", "detached_signature_body_hash_cross_binding_verified",
    "deployment_projection_contract_verified", "native_observer_profile_contract_verified",
    "policy_verifier_sid_deployment_service_sid_cross_binding_verified",
    "policy_deployment_native_observer_profile_cross_binding_verified",
    "operational_and_observer_key_role_separation_contract_verified",
    "future_native_observer_authority_requires_v3",
)
_V3_RECEIPT_FALSE_FIELDS = (
    "bootstrap_signature_mathematics_verified", "bootstrap_public_key_independently_pinned",
    "fixed_policy_store_discovery_verified", "live_windows_binary_acl_verified",
    "effective_verifier_token_verified", "linked_elevated_token_absence_verified",
    "independent_owner_policy_state_verified", "external_public_key_pin_provisioning_verified",
    "trusted_time_verified", "revocation_current_verified",
    "rollback_resistant_policy_epoch_verified", "rollback_resistant_key_epoch_verified",
    "durable_nonce_state_verified", "external_code_authority_verified",
    "owner_authority_verified", "actual_authority_granted", "actual_semantic_evidence_verified",
    "production_approval", "full_scan_approval", "p0_phase_exit", "action_applied",
    "future_authority_policy_version_eligible", "positive_native_observer_policy_profile_complete",
)


def _independent_v3_receipt(
    *, body: Mapping[str, Any], body_raw: bytes,
    signature: Mapping[str, Any], signature_raw: bytes,
) -> dict[str, Any]:
    security_hashes = {
        row["role"]: canonical_sha256(row["security_template"])
        for row in body["object_policies"]
    }
    object_identity = canonical_sha256([
        {key: row[key] for key in (
            "role", "object_kind", "final_volume_guid_path",
            "volume_serial_decimal", "file_id_128_hex",
        )}
        for row in body["object_policies"]
    ])
    body_sha = hashlib.sha256(body_raw).hexdigest()
    material: dict[str, Any] = {
        "schema_version": "p0_windows_owner_policy_contract_receipt_v3",
        "gate_status": "OWNER_POLICY_CONTRACT_PASS_BOOTSTRAP_AND_PROVISIONING_NO_GO",
        "policy_id": body["policy_id"], "policy_epoch": body["policy_epoch"],
        "policy_body_bytes_sha256": body_sha,
        "policy_body_artifact_sha256": body["artifact_sha256"],
        "policy_signature_bytes_sha256": hashlib.sha256(signature_raw).hexdigest(),
        "policy_signature_artifact_sha256": signature["artifact_sha256"],
        "store_id": body["store_id"], "owner_principal_sha256": body["owner_principal_sha256"],
        "owner_anchor_sha256": body["owner_anchor_sha256"],
        "owner_anchor_scope": "CORE_POLICY_IDENTITY_EXCLUDING_PIN_TRANSPORT_HASHES",
        "owner_anchor_excludes_pin_transport_hashes_by_design": True,
        "full_policy_identity_sha256": body_sha,
        "acl_template_sha256": body["acl_template_sha256"],
        "operational_key_projection_sha256": body["operational_key_projection_sha256"],
        "object_identity_projection_sha256": object_identity,
        "security_template_sha256_by_role": security_hashes,
        "strict_canonical_policy_body_verified": True,
        "strict_canonical_detached_signature_envelope_verified": True,
        "owner_and_verifier_sid_disjoint_contract_verified": True,
        "fixed_generation_layout_contract_verified": True,
        "exact_standard_explicit_ace_profile_contract_verified": True,
        "derived_owner_anchor_cross_binding_verified": True,
        "detached_signature_body_hash_cross_binding_verified": True,
        **{field: False for field in _V3_RECEIPT_FALSE_FIELDS[:21]},
        "policy_schema_version": "p0_windows_external_owner_policy_body_v3",
        "policy_domain": "llm_novel_dc/p0/windows-external-owner-policy/v3",
        "signature_schema_version": "p0_windows_external_owner_policy_signature_v3",
        "signature_domain": "llm_novel_dc/p0/windows-owner-policy-signature/v3",
        "deployment_projection_sha256": body["deployment_projection"]["artifact_sha256"],
        "native_observer_profile_sha256": body["native_observer_profile"]["artifact_sha256"],
        "deployment_projection_contract_verified": True,
        "native_observer_profile_contract_verified": True,
        "policy_verifier_sid_deployment_service_sid_cross_binding_verified": True,
        "policy_deployment_native_observer_profile_cross_binding_verified": True,
        "operational_and_observer_key_role_separation_contract_verified": True,
        "future_native_observer_authority_requires_v3": True,
        "future_authority_policy_version_eligible": False,
        "positive_native_observer_policy_profile_complete": False,
    }
    if tuple(material) + ("receipt_sha256",) != _V3_RECEIPT_FIELDS:
        raise P0WindowsOwnerPolicyV4TransitionParentError(
            "independent V3 receipt literal oracle drift"
        )
    return {**material, "receipt_sha256": canonical_sha256(material)}


def _canonical_p256_key(spki: bytes) -> Any:
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ec

        key = serialization.load_der_public_key(spki)
        if (
            not isinstance(key, ec.EllipticCurvePublicKey)
            or not isinstance(key.curve, ec.SECP256R1)
            or key.public_bytes(
                serialization.Encoding.DER,
                serialization.PublicFormat.SubjectPublicKeyInfo,
            ) != spki
        ):
            raise ValueError("non-canonical key")
        return key
    except (ImportError, TypeError, ValueError) as exc:
        raise P0WindowsOwnerPolicyV4TransitionParentError(
            "presented bootstrap key is not canonical P-256 DER SPKI"
        ) from exc


def _verify_v3_math(
    *, body_raw: bytes, signature_raw: bytes, pin_raw: bytes, spki: bytes
) -> tuple[str, str, str]:
    try:
        contract_receipt = v3.validate_presented_windows_owner_policy_contract(
            policy_body_bytes=body_raw,
            policy_signature_bytes=signature_raw,
        )
    except v3.P0WindowsOwnerPolicyContractError as exc:
        raise P0WindowsOwnerPolicyV4TransitionParentError(
            "live V3 contract failed"
        ) from exc
    body = _parse(body_raw, "live V3 body")
    signature = _parse(signature_raw, "live V3 signature")
    pin = _parse(pin_raw, "live V3 operational pin")
    expected_contract = _independent_v3_receipt(
        body=body, body_raw=body_raw,
        signature=signature, signature_raw=signature_raw,
    )
    contract_declared = contract_receipt.get("receipt_sha256")
    if (
        tuple(contract_receipt) != _V3_RECEIPT_FIELDS
        or any(contract_receipt.get(field) is not True for field in _V3_RECEIPT_TRUE_FIELDS)
        or any(contract_receipt.get(field) is not False for field in _V3_RECEIPT_FALSE_FIELDS)
        or type(contract_declared) is not str
        or not hmac.compare_digest(
            canonical_bytes(contract_receipt), canonical_bytes(expected_contract)
        )
        or contract_receipt.get("schema_version") != v3.CONTRACT_RECEIPT_SCHEMA_V3
        or contract_receipt.get("gate_status") != v3.GATE_STATUS
        or contract_receipt.get("policy_epoch") != 1
        or contract_receipt.get("bootstrap_signature_mathematics_verified") is not False
        or contract_receipt.get("actual_semantic_evidence_verified") is not False
    ):
        raise P0WindowsOwnerPolicyV4TransitionParentError(
            "live V3 contract receipt independent reconstruction mismatch"
        )
    if body.get("policy_epoch") != 1 or signature.get("policy_epoch") != 1:
        raise P0WindowsOwnerPolicyV4TransitionParentError(
            "live predecessor must be epoch 1"
        )
    if body.get("bootstrap_public_key_fingerprint_sha256") != hashlib.sha256(spki).hexdigest():
        raise P0WindowsOwnerPolicyV4TransitionParentError(
            "live V3 bootstrap fingerprint does not bind the presented SPKI"
        )
    operational = body.get("operational_key")
    if type(operational) is not dict:
        raise P0WindowsOwnerPolicyV4TransitionParentError(
            "live V3 operational-key projection is absent"
        )
    try:
        strict_pin, _x, _y = asymmetric._validate_pin(pin)
    except asymmetric.P0ExternalOwnerAsymmetricSignatureError as exc:
        raise P0WindowsOwnerPolicyV4TransitionParentError(
            "live V3 operational pin strict contract failed"
        ) from exc
    pin_declared = pin.get("artifact_sha256")
    pin_cross_binding = {
        "trust_domain": body.get("trust_domain"),
        "project_id": body.get("project_id"),
        "environment": body.get("environment"),
        "key_id": operational.get("key_id"),
        "key_epoch": operational.get("key_epoch"),
        "algorithm": operational.get("algorithm"),
        "public_key_fingerprint_sha256": operational.get(
            "public_key_fingerprint_sha256"
        ),
        "owner_principal_sha256": body.get("owner_principal_sha256"),
        "owner_anchor_sha256": body.get("owner_anchor_sha256"),
        "allowed_signature_domains": operational.get("allowed_signature_domains"),
    }
    if (
        strict_pin != pin
        or type(pin_declared) is not str
        or hashlib.sha256(pin_raw).hexdigest() != operational.get("pin_bytes_sha256")
        or pin_declared != operational.get("pin_artifact_sha256")
        or pin.get("public_key_fingerprint_sha256")
        != operational.get("public_key_fingerprint_sha256")
        or pin.get("key_id") != operational.get("key_id")
        or pin.get("key_epoch") != operational.get("key_epoch")
        or pin.get("owner_principal_sha256") != body.get("owner_principal_sha256")
        or any(pin.get(field) != value for field, value in pin_cross_binding.items())
    ):
        raise P0WindowsOwnerPolicyV4TransitionParentError(
            "live V3 operational pin is not exactly bound"
        )
    encoded = signature.get("signature_rs_base64")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (TypeError, ValueError, binascii.Error) as exc:
        raise P0WindowsOwnerPolicyV4TransitionParentError(
            "live V3 signature is not canonical Base64"
        ) from exc
    if len(raw) != 64 or base64.b64encode(raw).decode("ascii") != encoded:
        raise P0WindowsOwnerPolicyV4TransitionParentError(
            "live V3 signature is not exact P1363"
        )
    r, s = int.from_bytes(raw[:32], "big"), int.from_bytes(raw[32:], "big")
    if not 0 < r < P256_ORDER or not 0 < s <= P256_ORDER // 2:
        raise P0WindowsOwnerPolicyV4TransitionParentError(
            "live V3 signature is not bounded low-S P-256"
        )
    material = canonical_bytes({
        field: signature[field]
        for field in (
            "schema_version", "record_origin", "domain", "policy_id",
            "policy_epoch", "bootstrap_key_id",
            "bootstrap_public_key_fingerprint_sha256",
            "policy_body_bytes_sha256", "algorithm",
        )
    })
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec, utils

        _canonical_p256_key(spki).verify(
            utils.encode_dss_signature(r, s), material,
            ec.ECDSA(hashes.SHA256()),
        )
    except (InvalidSignature, TypeError, ValueError) as exc:
        raise P0WindowsOwnerPolicyV4TransitionParentError(
            "live V3 detached signature mathematics failed"
        ) from exc
    return hashlib.sha256(material).hexdigest(), body["policy_id"], contract_declared


_DEPENDENCY_PINS = {
    "v3_validator": v3.validate_presented_windows_owner_policy_contract,
    "v3_json_file_bytes": v3.json_file_bytes,
    "strict_pin": asymmetric._validate_pin,
    "v4_child_strict": v4_parent._strict_child,
    "v4_parent_replay": v4_parent.validate_v4_epoch2_fixed_store_parent_replay,
    "v4_parent_integrity": v4_parent._assert_parent_integrity,
    "v4_fixed_integrity": v4_fixed._assert_component_and_dependency_integrity,
    "sha256": hashlib.sha256,
    "compare_digest": hmac.compare_digest,
    "json_loads": json.loads,
    "json_dumps": json.dumps,
}
_EXTERNAL_CODE_PINS = tuple(
    (
        label, value,
        _stable_code_digest(value),
        value.__defaults__,
        dict(value.__kwdefaults__) if value.__kwdefaults__ is not None else None,
    )
    for label, value in (
        ("v3_validator", v3.validate_presented_windows_owner_policy_contract),
        ("v3_json_file_bytes", v3.json_file_bytes),
        ("strict_pin", asymmetric._validate_pin),
        ("v4_child_strict", v4_parent._strict_child),
        ("v4_parent_replay", v4_parent.validate_v4_epoch2_fixed_store_parent_replay),
        ("v4_parent_integrity", v4_parent._assert_parent_integrity),
        ("v4_fixed_integrity", v4_fixed._assert_component_and_dependency_integrity),
    )
)
_HASHLIB_SHA256_PIN = hashlib.sha256
_STABLE_CODE_DIGEST_PIN = _stable_code_digest
_STABLE_CODE_OBJECT_PIN = _stable_code_digest.__code__


def _assert_integrity() -> None:
    if (
        hashlib.sha256 is not _HASHLIB_SHA256_PIN
        or _stable_code_digest is not _STABLE_CODE_DIGEST_PIN
        or _stable_code_digest.__code__ is not _STABLE_CODE_OBJECT_PIN
        or SEMANTIC_CONTRACT_SHA256 != EXPECTED_SEMANTIC_CONTRACT_SHA256
        or canonical_sha256(_semantic_contract_projection())
        != EXPECTED_SEMANTIC_CONTRACT_SHA256
        or COMPONENT_MANIFEST_SHA256 != EXPECTED_COMPONENT_MANIFEST_SHA256
        or canonical_sha256(COMPONENT_MANIFEST) != EXPECTED_COMPONENT_MANIFEST_SHA256
        or v3.validate_presented_windows_owner_policy_contract is not _DEPENDENCY_PINS["v3_validator"]
        or v3.json_file_bytes is not _DEPENDENCY_PINS["v3_json_file_bytes"]
        or asymmetric._validate_pin is not _DEPENDENCY_PINS["strict_pin"]
        or v4_parent._strict_child is not _DEPENDENCY_PINS["v4_child_strict"]
        or v4_parent.validate_v4_epoch2_fixed_store_parent_replay
        is not _DEPENDENCY_PINS["v4_parent_replay"]
        or v4_parent._assert_parent_integrity is not _DEPENDENCY_PINS["v4_parent_integrity"]
        or v4_fixed._assert_component_and_dependency_integrity is not _DEPENDENCY_PINS["v4_fixed_integrity"]
        or hashlib.sha256 is not _DEPENDENCY_PINS["sha256"]
        or hmac.compare_digest is not _DEPENDENCY_PINS["compare_digest"]
        or json.loads is not _DEPENDENCY_PINS["json_loads"]
        or json.dumps is not _DEPENDENCY_PINS["json_dumps"]
    ):
        raise P0WindowsOwnerPolicyV4TransitionParentError(
            "transition parent component/dependency integrity drift"
        )
    try:
        v4_parent._assert_parent_integrity()
        v4_fixed._assert_component_and_dependency_integrity()
    except (
        v4_parent.P0WindowsOwnerPolicyV4Epoch2FixedStoreParentError,
        v4_fixed.P0WindowsOwnerPolicyV4Epoch2FixedStoreError,
    ) as exc:
        raise P0WindowsOwnerPolicyV4TransitionParentError(
            "transition parent transitive integrity drift"
        ) from exc
    for label, value, code_sha, defaults, kwdefaults in _EXTERNAL_CODE_PINS:
        if (
            _stable_code_digest(value) != code_sha
            or value.__defaults__ != defaults
            or value.__kwdefaults__ != kwdefaults
        ):
            raise P0WindowsOwnerPolicyV4TransitionParentError(
                f"transition parent external helper drift: {label}"
            )
    pins = globals().get("_SELF_HELPER_PINS")
    if pins is not None:
        for name, expected, code_sha, defaults, kwdefaults in pins:
            live = globals().get(name)
            if (
                live is not expected
                or _callable_code_sha256(live) != code_sha
                or getattr(live, "__defaults__", None) != defaults
                or getattr(live, "__kwdefaults__", None) != kwdefaults
            ):
                raise P0WindowsOwnerPolicyV4TransitionParentError(
                    f"transition parent private helper drift: {name}"
                )


def validate_windows_owner_policy_v4_transition_parent(
    *, raw_bundle: Mapping[str, bytes], v4_child_receipt: Mapping[str, Any],
    v4_parent_receipt: Mapping[str, Any],
) -> dict[str, Any]:
    """Strictly replay one epoch-1/epoch-2 transition without I/O."""

    _assert_integrity()
    if (
        type(raw_bundle) is not dict
        or tuple(raw_bundle) != TRANSITION_RAW_ROLES
        or any(type(raw_bundle[role]) is not bytes for role in TRANSITION_RAW_ROLES)
    ):
        raise P0WindowsOwnerPolicyV4TransitionParentError(
            "transition raw bundle exact inventory mismatch"
        )
    if not hmac.compare_digest(
        raw_bundle["live_v3_policy_body"],
        raw_bundle["predecessor_policy_v3_body"],
    ) or not hmac.compare_digest(
        raw_bundle["live_v3_policy_signature"],
        raw_bundle["predecessor_policy_v3_signature"],
    ):
        raise P0WindowsOwnerPolicyV4TransitionParentError(
            "live V3 bytes do not exactly match the embedded predecessor"
        )
    v4_raws = {role: raw_bundle[role] for role in v4_parent.RAW_ROLES}
    try:
        v4_parent._strict_child(v4_child_receipt)
    except v4_parent.P0WindowsOwnerPolicyV4Epoch2FixedStoreParentError as exc:
        raise P0WindowsOwnerPolicyV4TransitionParentError("V4 child strict replay failed") from exc
    try:
        independently_replayed_v4_parent = (
            v4_parent.validate_v4_epoch2_fixed_store_parent_replay(
                raw_bundle=v4_raws,
                child_receipt=v4_child_receipt,
            )
        )
    except v4_parent.P0WindowsOwnerPolicyV4Epoch2FixedStoreParentError as exc:
        raise P0WindowsOwnerPolicyV4TransitionParentError(
            "V4 parent independent replay failed"
        ) from exc
    parent_material = dict(v4_parent_receipt) if type(v4_parent_receipt) is dict else {}
    parent_declared = parent_material.pop("receipt_sha256", None)
    expected_v4_hashes = {
        role: hashlib.sha256(v4_raws[role]).hexdigest()
        for role in v4_parent.RAW_ROLES
    }
    if (
        type(v4_parent_receipt) is not dict
        or tuple(v4_parent_receipt) != v4_parent._RECEIPT_FIELDS
        or v4_parent_receipt.get("schema_version") != v4_parent.RECEIPT_SCHEMA
        or v4_parent_receipt.get("component_manifest_sha256")
        != v4_parent.EXPECTED_COMPONENT_MANIFEST_SHA256
        or v4_parent_receipt.get("v4_component_manifest_sha256")
        != v4_parent.V4_COMPONENT_MANIFEST_SHA256
        or any(v4_parent_receipt.get(field) is not True for field in v4_parent._TRUE_FIELDS)
        or any(v4_parent_receipt.get(field) is not False for field in v4_parent._FALSE_FIELDS)
        or type(parent_declared) is not str
        or not hmac.compare_digest(parent_declared, canonical_sha256(parent_material))
        or v4_parent_receipt.get("raw_role_sequence") != list(v4_parent.RAW_ROLES)
        or v4_parent_receipt.get("raw_sha256_by_role") != expected_v4_hashes
        or v4_parent_receipt.get("raw_bundle_projection_sha256") != canonical_sha256(expected_v4_hashes)
        or v4_parent_receipt.get("bootstrap_public_key_spki_bytes_sha256")
        != expected_v4_hashes["bootstrap_public_key_spki"]
        or any(
            v4_parent_receipt.get(field) != v4_child_receipt.get(field)
            for field in (
                "policy_id", "project_id", "trust_domain", "environment",
                "policy_purpose", "packet_v2_key_id", "packet_v2_key_epoch",
            )
        )
        or v4_parent_receipt.get("child_receipt_declared_sha256") != v4_child_receipt.get("receipt_sha256")
        or v4_parent_receipt.get("child_receipt_full_canonical_sha256") != canonical_sha256(v4_child_receipt)
        or type(v4_parent_receipt.get("predecessor_policy_epoch")) is not int
        or v4_parent_receipt.get("predecessor_policy_epoch") != 1
        or type(v4_parent_receipt.get("policy_v4_epoch")) is not int
        or v4_parent_receipt.get("policy_v4_epoch") != 2
        or type(v4_parent_receipt.get("packet_v2_key_epoch")) is not int
        or type(v4_parent_receipt.get("credited_actual_source_claim_count")) is not int
        or v4_parent_receipt.get("credited_actual_source_claim_count") != 0
        or type(v4_parent_receipt.get("credited_actual_a_context_review_count")) is not int
        or v4_parent_receipt.get("credited_actual_a_context_review_count") != 0
        or v4_parent_receipt.get("operational_effect") != v4_parent.OPERATIONAL_EFFECT
        or v4_parent_receipt.get("gate_status") != v4_parent.GATE_STATUS
        or not hmac.compare_digest(
            canonical_bytes(v4_parent_receipt),
            canonical_bytes(independently_replayed_v4_parent),
        )
    ):
        raise P0WindowsOwnerPolicyV4TransitionParentError(
            "supplied V4 parent receipt strict replay mismatch"
        )
    v3_input_sha, policy_id, v3_contract_sha = _verify_v3_math(
        body_raw=raw_bundle["live_v3_policy_body"],
        signature_raw=raw_bundle["live_v3_policy_signature"],
        pin_raw=raw_bundle["live_v3_operational_pin"],
        spki=raw_bundle["bootstrap_public_key_spki"],
    )
    if v4_parent_receipt.get("predecessor_policy_epoch") != 1 or v4_parent_receipt.get("policy_v4_epoch") != 2:
        raise P0WindowsOwnerPolicyV4TransitionParentError(
            "transition is not exactly epoch 1 to epoch 2"
        )
    raw_hashes = {
        role: hashlib.sha256(raw_bundle[role]).hexdigest()
        for role in TRANSITION_RAW_ROLES
    }
    material: dict[str, Any] = {
        "schema_version": RECEIPT_SCHEMA,
        "gate_status": GATE_STATUS,
        "decision": "NO_GO",
        "raw_role_sequence": list(TRANSITION_RAW_ROLES),
        "raw_sha256_by_role": raw_hashes,
        "raw_bundle_projection_sha256": canonical_sha256(raw_hashes),
        "policy_id": policy_id,
        "predecessor_policy_epoch": 1,
        "policy_v4_epoch": 2,
        "predecessor_signature_input_sha256": v3_input_sha,
        "predecessor_contract_receipt_sha256": v3_contract_sha,
        "presented_bootstrap_spki_sha256": raw_hashes["bootstrap_public_key_spki"],
        "v4_parent_declared_sha256": v4_parent_receipt["receipt_sha256"],
        "v4_parent_full_canonical_sha256": canonical_sha256(v4_parent_receipt),
        **{field: True for field in _TRUE_FIELDS},
        **{field: False for field in _FALSE_FIELDS},
        "credited_actual_source_claim_count": 0,
        "credited_actual_a_context_review_count": 0,
        "operational_effect": OPERATIONAL_EFFECT,
    }
    receipt = {**material, "receipt_sha256": canonical_sha256(material)}
    if tuple(receipt) != _RECEIPT_FIELDS:
        raise P0WindowsOwnerPolicyV4TransitionParentError(
            "transition parent output field-order drift"
        )
    _assert_integrity()
    return receipt


def _callable_code_sha256(value: Any) -> str:
    return _stable_code_digest(value)


_SELF_HELPER_PINS = tuple(
    (
        name, value, _callable_code_sha256(value), value.__defaults__,
        dict(value.__kwdefaults__) if value.__kwdefaults__ is not None else None,
    )
    for name, value in (
        ("canonical_bytes", canonical_bytes), ("canonical_sha256", canonical_sha256),
        ("_stable_code_digest", _stable_code_digest),
        ("_parse", _parse), ("_independent_v3_receipt", _independent_v3_receipt),
        ("_canonical_p256_key", _canonical_p256_key),
        ("_verify_v3_math", _verify_v3_math), ("_assert_integrity", _assert_integrity),
        ("_callable_code_sha256", _callable_code_sha256),
        ("validate_windows_owner_policy_v4_transition_parent", validate_windows_owner_policy_v4_transition_parent),
    )
)


__all__ = [
    "GATE_STATUS", "OPERATIONAL_EFFECT", "P0WindowsOwnerPolicyV4TransitionParentError",
    "RECEIPT_SCHEMA", "TRANSITION_RAW_ROLES",
    "validate_windows_owner_policy_v4_transition_parent",
]
