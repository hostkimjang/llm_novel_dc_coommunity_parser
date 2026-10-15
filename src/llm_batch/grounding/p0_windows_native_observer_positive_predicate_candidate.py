"""Fail-closed classifier for presented native-observer component transcripts.

This is deliberately not a positive authority gate.  It runs the strict
presented-component validator in the same call, distinguishes explicitly
negative runtime projections from an all-green presented projection, and
rejects both.  Current profile v1 receipts do not prove that the native
service was contacted, that the keys were independently provisioned, that
time/revocation are current, or that a nonce was durably consumed.
"""

from __future__ import annotations

import hmac
from typing import Any, Mapping

from . import p0_windows_native_observer_profile_contract as component
from . import p0_windows_owner_deployment_projection as deployment


RECEIPT_SCHEMA = (
    "p0_windows_native_observer_positive_predicate_rejection_receipt_v1"
)
GATE_STATUS = "PRESENTED_NATIVE_OBSERVER_POSITIVE_CANDIDATE_REJECTED"
OPERATIONAL_EFFECT = "NONE_POSITIVE_REJECTION_ONLY"

_COMPONENT_TRUE_FIELDS = (
    "strict_profile_contract_verified",
    "strict_canonical_transcript_verified",
    "request_ticket_receipt_cross_binding_verified",
    "observer_and_owner_state_key_roles_disjoint_verified",
    "owner_state_ticket_signature_math_verified",
    "observer_receipt_signature_math_verified",
    "owner_state_ticket_time_window_structure_verified",
    "signed_revocation_and_counter_floor_structure_verified",
    "presented_profile_only",
)

_COMPONENT_RECEIPT_FIELDS = frozenset(
    {
        "schema_version",
        "gate_status",
        "scope",
        "decision",
        "profile_schema_version",
        "profile_artifact_sha256",
        "deployment_projection_sha256",
        "service_name",
        "service_sid",
        "request_bytes_sha256",
        "request_artifact_sha256",
        "request_id",
        "challenge_sha256",
        "owner_state_ticket_bytes_sha256",
        "owner_state_ticket_artifact_sha256",
        "ticket_id",
        "receipt_body_bytes_sha256",
        "receipt_body_artifact_sha256",
        "receipt_id",
        "detached_signature_bytes_sha256",
        "detached_signature_artifact_sha256",
        *_COMPONENT_TRUE_FIELDS,
        "serialized_receipt_authoritative",
        "credited_actual_source_claim_count",
        "credited_actual_a_context_review_count",
        *component._ALWAYS_FALSE_FIELDS,
        "operational_effect",
        "receipt_sha256",
    }
)

_ALWAYS_FALSE_FIELDS = (
    "positive_native_observer_schema_available",
    "positive_native_observer_evidence_verified",
    "serialized_component_receipt_authoritative",
    "native_service_ipc_independently_established",
    "external_owner_provisioning_verified",
    "trusted_current_time_verified",
    "revocation_current_verified",
    "durable_nonce_consumption_verified",
    "single_use_replay_rejection_verified",
    "run_session_host_source_plan_binding_verified",
    "actual_authority_granted",
    "actual_semantic_evidence_verified",
    "p0_phase_exit",
    "production_approval",
    "full_scan_approval",
    "action_applied",
    "protected_pipeline_state_mutated",
)

_BASE_BLOCKERS = (
    "PRESENTED_COMPONENT_RECEIPT_NOT_AUTHORITY",
    "POSITIVE_NATIVE_OBSERVER_SCHEMA_NOT_AVAILABLE",
    "NATIVE_SERVICE_IPC_NOT_INDEPENDENTLY_ESTABLISHED",
    "EXTERNAL_OWNER_PROVISIONING_NOT_VERIFIED",
    "TRUSTED_TIME_REVOCATION_NONCE_NOT_VERIFIED",
    "RUN_SESSION_HOST_SOURCE_PLAN_BINDING_NOT_VERIFIED",
)


class P0WindowsNativeObserverPositivePredicateCandidateError(ValueError):
    """The rejection classifier could not preserve its exact contract."""


def _component_receipt_exact(receipt: Any) -> bool:
    if type(receipt) is not dict or set(receipt) != _COMPONENT_RECEIPT_FIELDS:
        return False
    declared = receipt.get("receipt_sha256")
    material = dict(receipt)
    material.pop("receipt_sha256", None)
    return (
        type(declared) is str
        and len(declared) == 64
        and hmac.compare_digest(declared, component.canonical_sha256(material))
        and receipt.get("schema_version") == component.VALIDATION_RECEIPT_SCHEMA
        and receipt.get("gate_status") == component.GATE_STATUS
        and receipt.get("scope")
        == "PRESENTED_NATIVE_OBSERVER_PROFILE_COMPONENT_ONLY"
        and receipt.get("decision") == "NO_GO"
        and receipt.get("profile_schema_version") == component.PROFILE_SCHEMA
        and receipt.get("serialized_receipt_authoritative") is False
        and receipt.get("credited_actual_source_claim_count") == 0
        and type(receipt.get("credited_actual_source_claim_count")) is int
        and receipt.get("credited_actual_a_context_review_count") == 0
        and type(receipt.get("credited_actual_a_context_review_count")) is int
        and all(receipt.get(field) is True for field in _COMPONENT_TRUE_FIELDS)
        and all(
            receipt.get(field) is False
            for field in component._ALWAYS_FALSE_FIELDS
        )
        and receipt.get("operational_effect") == component.OPERATIONAL_EFFECT
    )


def _presented_runtime_projection_has_no_explicit_negative_flags(
    body: Mapping[str, Any]
) -> bool:
    policy_store = body["policy_store_evidence"]
    service = body["service_evidence"]
    image = body["image_evidence"]
    authenticode = body["authenticode_evidence"]
    wdac = body["wdac_evidence"]
    providers = body["provider_evidence"]["modules"]
    key = body["observer_key_evidence"]
    state = body["owner_state_evidence"]
    return (
        policy_store["all_required_handles_held"] is True
        and policy_store["pre_post_stable"] is True
        and service["service_status"] == "RUNNING"
        and type(service["service_pid"]) is int
        and service["service_pid"] > 0
        and type(service["process_creation_time_100ns"]) is int
        and service["process_creation_time_100ns"] > 0
        and service["token_user_sid"]
        == deployment.SERVICE_START_ACCOUNT_SID
        and all(
            service[field] is True
            for field in (
                "service_sid_enabled",
                "service_sid_restricted",
                "token_is_restricted",
                "linked_token_absent",
            )
        )
        and image["handle_held"] is True
        and authenticode["winverifytrust_status"] == "VERIFIED"
        and authenticode["chain_status"] == "VERIFIED"
        and authenticode["revocation_status"] == "CURRENT"
        and wdac["umci_enforcement_status"] == "ENFORCED"
        and all(
            row["catalog_status"] == "VERIFIED"
            and row["handle_held"] is True
            for row in providers
        )
        and key["hardware_backed_observed"] is True
        and key["non_exportable_observed"] is True
        and state["ticket_window_structure_observed"] is True
        and state["nonce_consumption_observed"] is True
        and state["trusted_time_ticket_observed"] is True
        and body["diagnostics"] == []
    )


def reject_presented_windows_native_observer_component_candidate(
    *,
    native_observer_profile: Mapping[str, Any],
    request_bytes: bytes,
    owner_state_ticket_bytes: bytes,
    raw_receipt_body_bytes: bytes,
    detached_observer_signature_bytes: bytes,
) -> dict[str, Any]:
    """Validate one component transcript, then reject it as positive evidence."""

    try:
        component_receipt = (
            component.validate_presented_windows_native_observer_profile_component(
                native_observer_profile=native_observer_profile,
                request_bytes=request_bytes,
                owner_state_ticket_bytes=owner_state_ticket_bytes,
                raw_receipt_body_bytes=raw_receipt_body_bytes,
                detached_observer_signature_bytes=(
                    detached_observer_signature_bytes
                ),
            )
        )
        if not _component_receipt_exact(component_receipt):
            raise P0WindowsNativeObserverPositivePredicateCandidateError(
                "component receipt exact truth table mismatch"
            )
        body = component._parse_canonical(
            raw_receipt_body_bytes, "positive-rejection native receipt body"
        )
        if not isinstance(body, Mapping):
            raise P0WindowsNativeObserverPositivePredicateCandidateError(
                "validated native receipt body is not an object"
            )
        no_explicit_negative = (
            _presented_runtime_projection_has_no_explicit_negative_flags(body)
        )
    except P0WindowsNativeObserverPositivePredicateCandidateError:
        raise
    except component.P0WindowsNativeObserverProfileContractError:
        raise
    except BaseException as exc:
        raise P0WindowsNativeObserverPositivePredicateCandidateError(
            "positive-rejection classification failed closed"
        ) from exc

    blockers = list(_BASE_BLOCKERS)
    if not no_explicit_negative:
        blockers.insert(0, "PRESENTED_NEGATIVE_RUNTIME_PROJECTION_DETECTED")
    material: dict[str, Any] = {
        "schema_version": RECEIPT_SCHEMA,
        "gate_status": GATE_STATUS,
        "decision": "POSITIVE_REJECTED",
        "failure_stage": (
            "PRESENTED_NEGATIVE_RUNTIME_EVIDENCE"
            if not no_explicit_negative
            else "PRESENTED_COMPONENT_ONLY"
        ),
        "blocker_codes": blockers,
        "candidate_only": True,
        "component_validator_executed_same_call": True,
        "presented_component_receipt_exact_revalidated": True,
        "component_receipt_sha256": component_receipt["receipt_sha256"],
        "presented_negative_runtime_projection_detected": (
            not no_explicit_negative
        ),
        "presented_negative_runtime_projection_hard_rejected": (
            not no_explicit_negative
        ),
        "selected_presented_runtime_flags_no_explicit_negative_but_rejected": (
            no_explicit_negative
        ),
        "positive_candidate_hard_rejected": True,
        **{field: False for field in _ALWAYS_FALSE_FIELDS},
        "credited_actual_source_claim_count": 0,
        "credited_actual_a_context_review_count": 0,
        "operational_effect": OPERATIONAL_EFFECT,
    }
    return {**material, "receipt_sha256": component.canonical_sha256(material)}


__all__ = [
    "GATE_STATUS",
    "P0WindowsNativeObserverPositivePredicateCandidateError",
    "RECEIPT_SCHEMA",
    "reject_presented_windows_native_observer_component_candidate",
]
