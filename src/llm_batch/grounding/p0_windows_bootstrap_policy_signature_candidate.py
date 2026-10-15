"""Windows CNG bootstrap-signature mathematics for owner-policy bytes.

The verifier accepts exact policy body/signature bytes but no key, path,
provider, algorithm, receipt, state, callback, or expected identity input.  It
selects one source-compiled public-key *candidate*, validates the strict owner
policy contract, and verifies the detached envelope's domain-separated
canonical material with Windows CNG ECDSA P-256/SHA-256.

Source-level constants are not an independently provisioned trust root.  A
successful result proves signature mathematics under the compiled candidate,
not immutable verifier-code identity, external provisioning, owner authority,
rollback resistance, P0 exit, or production approval.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import hmac
import os
from typing import Any, Mapping

from . import p0_external_owner_asymmetric_signature as asymmetric
from . import p0_windows_owner_policy_contract as policy
from . import p0_windows_cng_ecdsa_p256 as cng_p256


RECEIPT_SCHEMA = "p0_windows_bootstrap_policy_signature_candidate_receipt_v1"
GATE_STATUS = (
    "BOOTSTRAP_POLICY_SIGNATURE_MATH_CANDIDATE_PASS_CODE_AUTHORITY_NO_GO"
)
COMPILED_BOOTSTRAP_KEY_ID = "compiled-bootstrap-candidate-20260902-001"
COMPILED_BOOTSTRAP_PUBLIC_KEY_X_BASE64 = (
    "TIw6HZPdOa3D9h/pqowso8XSYHvphpRxyRPdAQHxJMA="
)
COMPILED_BOOTSTRAP_PUBLIC_KEY_Y_BASE64 = (
    "c+Dtj4y2Ej62Rp2Y+r9HWCLLtbE3Vilp7sjO5BH+Nug="
)
COMPILED_BOOTSTRAP_PUBLIC_KEY_FINGERPRINT_SHA256 = (
    "5693c09f1b6a59b26a9c97d7c93c07549b39b0ec43eb6e5952769711bc726234"
)
COMPILED_BOOTSTRAP_KEY_CANDIDATE_PROVENANCE = (
    "PUBLIC_ONLY_NONAUTHORITY_CANDIDATE_PRIVATE_KEY_NOT_AVAILABLE"
)
SIGNATURE_MATERIAL_CONTRACT = (
    "CANONICAL_STRICT_DETACHED_ENVELOPE_EXCLUDING_SIGNATURE_AND_ARTIFACT"
)

_SIGNATURE_MATERIAL_FIELDS = (
    "schema_version",
    "record_origin",
    "domain",
    "policy_id",
    "policy_epoch",
    "bootstrap_key_id",
    "bootstrap_public_key_fingerprint_sha256",
    "policy_body_bytes_sha256",
    "algorithm",
)

_FALSE_FIELDS = (
    "bootstrap_public_key_independently_pinned",
    "trusted_verifier_code_identity_verified",
    "trusted_cng_provider_provenance_verified",
    "external_owner_policy_provisioning_verified",
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
    "protected_pipeline_state_mutated",
)


class P0WindowsBootstrapPolicySignatureCandidateError(ValueError):
    """Bootstrap policy signature mathematics could not fail closed."""


@dataclass(frozen=True)
class _CompiledBootstrapKeyCandidate:
    key_id: str
    public_key_x: bytes
    public_key_y: bytes
    public_key_fingerprint_sha256: str


def canonical_bytes(value: Any) -> bytes:
    return policy.canonical_bytes(value)


def canonical_sha256(value: Any) -> str:
    return policy.canonical_sha256(value)


def _strict_coordinate(value: str, label: str) -> bytes:
    try:
        raw = base64.b64decode(value, validate=True)
    except (ValueError, base64.binascii.Error) as exc:
        raise P0WindowsBootstrapPolicySignatureCandidateError(
            f"{label} is not canonical Base64"
        ) from exc
    if len(raw) != 32 or base64.b64encode(raw).decode("ascii") != value:
        raise P0WindowsBootstrapPolicySignatureCandidateError(
            f"{label} must be one canonical 32-byte coordinate"
        )
    return raw


def _compiled_bootstrap_key_candidate() -> _CompiledBootstrapKeyCandidate:
    x = _strict_coordinate(
        COMPILED_BOOTSTRAP_PUBLIC_KEY_X_BASE64,
        "compiled bootstrap public-key X",
    )
    y = _strict_coordinate(
        COMPILED_BOOTSTRAP_PUBLIC_KEY_Y_BASE64,
        "compiled bootstrap public-key Y",
    )
    fingerprint = asymmetric.public_key_fingerprint_sha256(
        public_key_x_base64=COMPILED_BOOTSTRAP_PUBLIC_KEY_X_BASE64,
        public_key_y_base64=COMPILED_BOOTSTRAP_PUBLIC_KEY_Y_BASE64,
    )
    if not hmac.compare_digest(
        fingerprint, COMPILED_BOOTSTRAP_PUBLIC_KEY_FINGERPRINT_SHA256
    ):
        raise P0WindowsBootstrapPolicySignatureCandidateError(
            "compiled bootstrap public-key fingerprint constant mismatch"
        )
    return _CompiledBootstrapKeyCandidate(
        key_id=COMPILED_BOOTSTRAP_KEY_ID,
        public_key_x=x,
        public_key_y=y,
        public_key_fingerprint_sha256=fingerprint,
    )


def _signature_material(signature: Mapping[str, Any]) -> dict[str, Any]:
    return {field: signature[field] for field in _SIGNATURE_MATERIAL_FIELDS}


def verify_presented_windows_owner_policy_bootstrap_signature_candidate(
    *, policy_body_bytes: bytes, policy_signature_bytes: bytes
) -> dict[str, Any]:
    """Verify strict detached-policy signature math under the compiled key."""

    if os.name != "nt":
        raise P0WindowsBootstrapPolicySignatureCandidateError(
            "Windows CNG bootstrap policy verification is required"
        )
    try:
        contract_receipt = (
            policy.validate_presented_windows_owner_policy_contract(
                policy_body_bytes=policy_body_bytes,
                policy_signature_bytes=policy_signature_bytes,
            )
        )
        body = policy._validate_policy_body(policy_body_bytes)
        signature = policy._validate_signature(
            policy_signature_bytes, body, policy_body_bytes
        )
        key = _compiled_bootstrap_key_candidate()
    except P0WindowsBootstrapPolicySignatureCandidateError:
        raise
    except (
        policy.P0WindowsOwnerPolicyContractError,
        asymmetric.P0ExternalOwnerAsymmetricSignatureError,
    ) as exc:
        raise P0WindowsBootstrapPolicySignatureCandidateError(
            "strict owner-policy contract failed before bootstrap CNG"
        ) from exc
    except BaseException as exc:
        raise P0WindowsBootstrapPolicySignatureCandidateError(
            "bootstrap policy structure/key selection failed closed"
        ) from exc

    if (
        body["bootstrap_key_id"] != key.key_id
        or signature["bootstrap_key_id"] != key.key_id
    ):
        raise P0WindowsBootstrapPolicySignatureCandidateError(
            "policy bootstrap key ID does not match compiled candidate"
        )
    if (
        body["bootstrap_public_key_fingerprint_sha256"]
        != key.public_key_fingerprint_sha256
        or signature["bootstrap_public_key_fingerprint_sha256"]
        != key.public_key_fingerprint_sha256
    ):
        raise P0WindowsBootstrapPolicySignatureCandidateError(
            "policy bootstrap fingerprint does not match compiled candidate"
        )

    encoded = signature["signature_rs_base64"]
    try:
        signature_rs = base64.b64decode(encoded, validate=True)
    except (ValueError, base64.binascii.Error) as exc:
        raise P0WindowsBootstrapPolicySignatureCandidateError(
            "policy bootstrap signature is not canonical Base64"
        ) from exc
    material = _signature_material(signature)
    material_bytes = canonical_bytes(material)
    digest = hashlib.sha256(material_bytes).digest()
    try:
        cng_p256.verify_p256_sha256(
            public_key_x=key.public_key_x,
            public_key_y=key.public_key_y,
            digest=digest,
            signature=signature_rs,
        )
    except cng_p256.P0WindowsCngEcdsaP256Error as exc:
        raise P0WindowsBootstrapPolicySignatureCandidateError(
            "compiled-candidate bootstrap signature mathematics failed"
        ) from exc
    except Exception as exc:
        raise P0WindowsBootstrapPolicySignatureCandidateError(
            "bootstrap CNG verification failed closed"
        ) from exc

    material_receipt: dict[str, Any] = {
        "schema_version": RECEIPT_SCHEMA,
        "gate_status": GATE_STATUS,
        "candidate_only": True,
        "policy_body_bytes_sha256": hashlib.sha256(
            policy_body_bytes
        ).hexdigest(),
        "policy_signature_bytes_sha256": hashlib.sha256(
            policy_signature_bytes
        ).hexdigest(),
        "policy_signature_artifact_sha256": signature["artifact_sha256"],
        "signature_material_contract": SIGNATURE_MATERIAL_CONTRACT,
        "signature_material_bytes_sha256": digest.hex(),
        "signature_material_envelope_field_names": list(
            _SIGNATURE_MATERIAL_FIELDS
        ),
        "compiled_bootstrap_key_id": key.key_id,
        "compiled_bootstrap_public_key_fingerprint_sha256": (
            key.public_key_fingerprint_sha256
        ),
        "compiled_bootstrap_key_candidate_provenance": (
            COMPILED_BOOTSTRAP_KEY_CANDIDATE_PROVENANCE
        ),
        "algorithm": policy.BOOTSTRAP_SIGNATURE_ALGORITHM,
        "curve": asymmetric.CURVE,
        "cng_provider_name": asymmetric.CNG_PROVIDER,
        "owner_policy_contract_receipt": contract_receipt,
        "owner_policy_contract_receipt_declared_sha256": contract_receipt[
            "receipt_sha256"
        ],
        "compiled_bootstrap_key_candidate_selected": True,
        "signature_bootstrap_identity_matches_compiled_candidate": True,
        "strict_policy_contract_revalidated": True,
        "signature_domain_separation_material_verified": True,
        "exact_policy_body_bytes_hash_bound_verified": True,
        "canonical_low_s_signature_verified": True,
        "cng_public_key_import_verified": True,
        "bootstrap_signature_mathematics_verified": True,
        "public_api_key_parameter_absent": True,
        "public_api_provider_parameter_absent": True,
        "serialized_receipt_authoritative": False,
        "execution_trace_transferable_by_receipt": False,
        **{field: False for field in _FALSE_FIELDS},
        "credited_actual_source_claim_count": 0,
        "credited_actual_a_context_review_count": 0,
        "operational_effect": "NONE_SHADOW_ONLY",
    }
    return {
        **material_receipt,
        "receipt_sha256": canonical_sha256(material_receipt),
    }


__all__ = [
    "COMPILED_BOOTSTRAP_KEY_ID",
    "COMPILED_BOOTSTRAP_KEY_CANDIDATE_PROVENANCE",
    "COMPILED_BOOTSTRAP_PUBLIC_KEY_FINGERPRINT_SHA256",
    "GATE_STATUS",
    "P0WindowsBootstrapPolicySignatureCandidateError",
    "RECEIPT_SCHEMA",
    "SIGNATURE_MATERIAL_CONTRACT",
    "verify_presented_windows_owner_policy_bootstrap_signature_candidate",
]
