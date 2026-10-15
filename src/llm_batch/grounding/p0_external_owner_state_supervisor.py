"""Process-local OWNER_STATE handoff for presented asymmetric owner evidence.

The public supervisor accepts only the exact raw pin, signature envelope, and
preauthorization bytes plus a caller-held expected context.  It never accepts
the asymmetric validator's serialized receipt as evidence.  The validator
mints a private object-identity state only after fresh CNG verification; this
module consumes that state exactly once in the same call.

This closes a receipt-reentry/control-flow gap only.  Revalidating the same raw
triplet can mint another state, and the expected context is still caller-held.
External pin provisioning, trusted time, revocation, durable nonce replay
protection, owner authority, P0 exit, and production therefore remain false.
"""

from __future__ import annotations

import hashlib
from typing import Any, Mapping

from . import p0_external_owner_asymmetric_signature as asymmetric


OWNER_STATE_SUPERVISOR_RECEIPT_SCHEMA = (
    "p0_external_owner_state_supervisor_receipt_v1"
)
GATE_STATUS = (
    "PASS_OWNER_STATE_PROCESS_LOCAL_HANDOFF_COMPONENT_ONLY_"
    "ARTIFACT_REPLAY_NO_GO"
)


class P0ExternalOwnerStateSupervisorError(ValueError):
    """The raw-to-private-state supervisor could not fail-closed."""


def execute_presented_external_owner_state_supervisor(
    *,
    public_key_pin_bytes: bytes,
    signature_envelope_bytes: bytes,
    owner_root_preauthorization_bytes: bytes,
    expected_context: Mapping[str, Any],
) -> dict[str, Any]:
    """Freshly validate raw3 and consume its private OWNER_STATE once."""

    try:
        state = (
            asymmetric._validate_presented_external_owner_asymmetric_signature_state(
                public_key_pin_bytes=public_key_pin_bytes,
                signature_envelope_bytes=signature_envelope_bytes,
                owner_root_preauthorization_bytes=(
                    owner_root_preauthorization_bytes
                ),
            )
        )
    except asymmetric.P0ExternalOwnerAsymmetricSignatureError as exc:
        raise P0ExternalOwnerStateSupervisorError(
            "fresh asymmetric raw-triplet validation failed"
        ) from exc
    try:
        consumed = asymmetric._consume_external_owner_asymmetric_signature_state(
            state,
            public_key_pin_bytes=public_key_pin_bytes,
            signature_envelope_bytes=signature_envelope_bytes,
            owner_root_preauthorization_bytes=owner_root_preauthorization_bytes,
            expected_context=expected_context,
        )
    except asymmetric.P0ExternalOwnerAsymmetricSignatureError as exc:
        raise P0ExternalOwnerStateSupervisorError(
            "private OWNER_STATE consumption failed"
        ) from exc
    finally:
        asymmetric._discard_external_owner_asymmetric_signature_state(state)

    child = consumed.public_receipt
    material = {
        "schema_version": OWNER_STATE_SUPERVISOR_RECEIPT_SCHEMA,
        "child_asymmetric_receipt_sha256": child["receipt_sha256"],
        "public_key_pin_bytes_sha256": hashlib.sha256(
            consumed.public_key_pin_bytes
        ).hexdigest(),
        "signature_envelope_bytes_sha256": hashlib.sha256(
            consumed.signature_envelope_bytes
        ).hexdigest(),
        "preauthorization_bytes_sha256": hashlib.sha256(
            consumed.owner_root_preauthorization_bytes
        ).hexdigest(),
        "expected_context_sha256": asymmetric.canonical_sha256(
            asymmetric._owner_state_context_projection(child)
        ),
        "key_id": child["key_id"],
        "key_epoch": child["key_epoch"],
        "trust_domain": child["trust_domain"],
        "project_id": child["project_id"],
        "environment": child["environment"],
        "purpose": child["purpose"],
        "session_id": child["session_id"],
        "run_id": child["run_id"],
        "preauthorization_id": child["preauthorization_id"],
        "parser_run_id": child["parser_run_id"],
        "nonce_commitment_sha256": child["nonce_commitment_sha256"],
        "public_key_fingerprint_sha256": child[
            "public_key_fingerprint_sha256"
        ],
        "owner_principal_sha256": child["owner_principal_sha256"],
        "owner_anchor_sha256": child["owner_anchor_sha256"],
        "asymmetric_signature_math_verified": True,
        "exact_preauthorization_bytes_bound_verified": True,
        "fresh_raw_triplet_validation_observed": True,
        "module_issued_owner_state_consumed_once": True,
        "same_call_raw_triplet_verified": True,
        "exact_object_identity_registry_verified": True,
        "public_receipt_input_absent": True,
        "process_local_cooperative_handoff_only": True,
        "serialized_receipt_consumed": False,
        "serialized_receipt_authoritative": False,
        "execution_trace_transferable_by_receipt": False,
        "signature_artifact_replay_prevented": False,
        "arbitrary_in_process_code_resistance_verified": False,
        "secure_memory_erasure_verified": False,
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
    return {
        **material,
        "receipt_sha256": asymmetric.canonical_sha256(material),
    }


__all__ = [
    "GATE_STATUS",
    "OWNER_STATE_SUPERVISOR_RECEIPT_SCHEMA",
    "P0ExternalOwnerStateSupervisorError",
    "execute_presented_external_owner_state_supervisor",
]
