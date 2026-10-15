"""Zero-input v3 owner-policy successor preflight with positive path closed.

The existing v2 provisioning preflight remains unchanged.  This successor
observes the fixed store once, requires the exact v3 policy/profile/bootstrap
bindings, and then stops before SCM or native IPC because current v3 explicitly
declares its positive observer profile incomplete.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import os
from typing import Any, Mapping

from . import p0_windows_fixed_owner_policy_store_candidate as fixed_store
from . import p0_windows_native_observer_profile_contract as observer
from . import p0_windows_owner_deployment_projection as deployment
from . import p0_windows_owner_policy_contract as policy


RECEIPT_SCHEMA = "p0_windows_owner_policy_v3_preflight_candidate_receipt_v2"
GATE_STATUS = "WINDOWS_OWNER_POLICY_V3_PREFLIGHT_EXECUTED_POSITIVE_NO_GO"
OPERATIONAL_EFFECT = "NONE_V3_PREFLIGHT_REJECTION_ONLY"

_IS_WINDOWS = os.name == "nt"

_BLOCKER_ORDER = (
    "FIXED_OWNER_POLICY_STORE_NOT_VERIFIED",
    "OWNER_POLICY_V3_NOT_VERIFIED",
    "BOOTSTRAP_CNG_REEXECUTION_NOT_VERIFIED",
    "BOOTSTRAP_CNG_REEXECUTION_RECEIPT_MISMATCH",
    "POSITIVE_NATIVE_OBSERVER_POLICY_PROFILE_NOT_VERIFIED",
    "POSITIVE_NATIVE_OBSERVER_POLICY_PROFILE_INCOMPLETE",
    "PRESENTED_TRANSCRIPT_COMPONENT_NOT_AUTHORITY",
    "NATIVE_OBSERVER_IPC_NOT_ATTEMPTED",
    "SCM_SERVICE_HOST_NOT_OBSERVED",
    "AUTHENTICODE_CATALOG_NOT_VERIFIED",
    "WDAC_UMCI_POLICY_IDENTITY_NOT_VERIFIED",
    "TPM_KSP_ATTESTATION_NOT_VERIFIED",
    "TRUSTED_TIME_REVOCATION_NONCE_NOT_VERIFIED",
    "SINGLE_INTERVAL_STORE_HOST_BINDING_NOT_VERIFIED",
    "EXTERNAL_OWNER_PROVISIONING_NOT_VERIFIED",
)

_OBSERVATION_FIELDS = (
    "fixed_policy_store_candidate_observed",
    "owner_policy_v3_contract_verified",
    "non_v3_policy_version_input_hard_rejected",
    "producer_bootstrap_receipt_exact_validated",
    "producer_bootstrap_signature_math_result_observed",
    "successor_bootstrap_cng_same_process_reexecution_attempted",
    "successor_bootstrap_cng_same_process_reexecution_succeeded",
    "successor_reexecution_receipt_contract_validated",
    "successor_reexecution_receipt_exact_match_verified",
    "same_snapshot_policy_bytes_used_for_cng_reexecution",
    "bootstrap_signature_math_two_execution_consistency_verified",
    "bootstrap_signature_mathematics_verified",
    "deployment_projection_cross_binding_verified",
    "native_observer_profile_component_contract_verified",
    "policy_deployment_native_profile_cross_binding_verified",
    "four_key_role_separation_contract_verified",
    "current_v3_positive_profile_incomplete_verified",
)

_FIXED_STORE_REQUIRED_TRUE_FIELDS = (
    "known_folder_api_succeeded",
    "known_folder_free_call_completed_observed",
    "program_data_held_identity_verified",
    "program_data_no_reparse_verified",
    "compiled_genesis_inventory_verified",
    "policy_epoch_directory_exact_match_observed",
    "fixed_generation_layout_handle_binding_observed",
    "policy_object_identity_live_handle_exact_match_observed",
    "pin_bytes_operational_key_cross_binding_observed",
    "held_role_acl_projection_matches_presented_template_observed",
    "all_lexical_ancestor_handles_held",
    "ancestor_namespace_pre_post_and_reopen_stable",
    "all_role_handles_held_across_validation",
    "all_handles_non_inheritable_observed",
    "single_link_non_reparse_unnamed_stream_observed",
    "same_volume_role_set_observed",
    "role_pre_post_identity_inventory_acl_stable",
    "path_reopen_identity_stable",
    "bounded_directory_change_interval_observed",
    "fixed_policy_store_discovery_candidate_observed",
    "caller_supplied_path_absent",
    "caller_supplied_environment_absent",
    "caller_supplied_epoch_absent",
    "caller_supplied_key_absent",
    "caller_supplied_sid_absent",
    "caller_supplied_expected_identity_absent",
    "caller_supplied_receipt_state_callback_absent",
)

_V3_CONTRACT_REQUIRED_TRUE_FIELDS = (
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

_FIXED_STORE_RECEIPT_FIELDS = frozenset(
    {
        "schema_version",
        "gate_status",
        "candidate_only",
        "known_folder_id",
        "known_folder_flags",
        "known_folder_token_is_null",
        "known_folder_api_succeeded",
        "known_folder_free_call_completed_observed",
        "program_data_held_identity",
        "program_data_held_identity_verified",
        "program_data_no_reparse_verified",
        "fixed_relative_store_components",
        "selected_generation_component",
        "selected_policy_epoch",
        "compiled_genesis_inventory_verified",
        "lexical_ancestor_handle_count",
        "lexical_ancestor_identity_projection",
        "lexical_ancestor_identity_projection_sha256",
        "role_handle_count",
        "role_identity_projection_by_role",
        "role_identity_projection_sha256",
        "inventory_projection_by_directory",
        "inventory_projection_sha256",
        "policy_body_bytes_length",
        "policy_body_bytes_sha256",
        "policy_signature_bytes_length",
        "policy_signature_bytes_sha256",
        "public_key_pin_bytes_length",
        "public_key_pin_bytes_sha256",
        "public_key_pin_artifact_sha256",
        "public_key_fingerprint_sha256",
        "public_key_id",
        "public_key_epoch",
        "owner_policy_contract_receipt",
        "owner_policy_contract_receipt_declared_sha256",
        "owner_policy_contract_receipt_full_canonical_sha256",
        "bootstrap_policy_signature_candidate_receipt",
        "bootstrap_policy_signature_candidate_receipt_declared_sha256",
        "bootstrap_signature_input_sha256",
        "compiled_bootstrap_key_id",
        "compiled_bootstrap_public_key_fingerprint_sha256",
        "compiled_bootstrap_key_candidate_selected",
        "bootstrap_signature_mathematics_verified",
        "acl_projection_sha256_by_role",
        "directory_change_watches",
        *_FIXED_STORE_REQUIRED_TRUE_FIELDS,
        *fixed_store._FALSE_FIELDS,
        "credited_actual_source_claim_count",
        "credited_actual_a_context_review_count",
        "operational_effect",
        "receipt_sha256",
    }
)

_BOOTSTRAP_RECEIPT_FIELDS = frozenset(
    {
        "schema_version",
        "gate_status",
        "candidate_only",
        "policy_body_bytes_sha256",
        "policy_signature_bytes_sha256",
        "policy_signature_artifact_sha256",
        "signature_material_contract",
        "signature_material_bytes_sha256",
        "signature_material_envelope_field_names",
        "compiled_bootstrap_key_id",
        "compiled_bootstrap_public_key_fingerprint_sha256",
        "compiled_bootstrap_key_candidate_provenance",
        "algorithm",
        "curve",
        "cng_provider_name",
        "owner_policy_contract_receipt",
        "owner_policy_contract_receipt_declared_sha256",
        *fixed_store._BOOTSTRAP_RECEIPT_TRUE_FIELDS,
        *fixed_store._BOOTSTRAP_RECEIPT_FALSE_FIELDS,
        "public_api_key_parameter_absent",
        "public_api_provider_parameter_absent",
        "credited_actual_source_claim_count",
        "credited_actual_a_context_review_count",
        "operational_effect",
        "receipt_sha256",
    }
)

_V3_CONTRACT_RECEIPT_FIELDS = frozenset(
    {
        "schema_version",
        "gate_status",
        "policy_body_bytes_sha256",
        "policy_signature_bytes_sha256",
        "policy_id",
        "policy_epoch",
        "policy_body_artifact_sha256",
        "policy_signature_artifact_sha256",
        "store_id",
        "owner_principal_sha256",
        "owner_anchor_sha256",
        "owner_anchor_scope",
        "owner_anchor_excludes_pin_transport_hashes_by_design",
        "full_policy_identity_sha256",
        "acl_template_sha256",
        "operational_key_projection_sha256",
        "object_identity_projection_sha256",
        "security_template_sha256_by_role",
        *_V3_CONTRACT_REQUIRED_TRUE_FIELDS,
        *policy._ALWAYS_FALSE_FIELDS,
        "policy_schema_version",
        "policy_domain",
        "signature_schema_version",
        "signature_domain",
        "deployment_projection_sha256",
        "native_observer_profile_sha256",
        "future_authority_policy_version_eligible",
        "positive_native_observer_policy_profile_complete",
        "receipt_sha256",
    }
)

_ALWAYS_FALSE_FIELDS = (
    "positive_native_observer_policy_profile_complete",
    "native_observer_transcript_evaluated",
    "native_observer_ipc_attempted",
    "service_configuration_observation_attempted",
    "actual_launch_attempted",
    "serialized_receipt_authoritative",
    "external_owner_policy_provisioning_verified",
    "native_service_execution_verified",
    "live_host_observation_verified",
    "observer_key_hardware_backing_verified",
    "observer_key_non_exportability_verified",
    "trusted_time_verified",
    "revocation_current_verified",
    "durable_cross_process_nonce_verified",
    "single_use_replay_consumed",
    "single_interval_store_host_cross_binding_verified",
    "actual_authority_granted",
    "actual_semantic_evidence_verified",
    "p0_phase_exit",
    "production_approval",
    "full_scan_approval",
    "action_applied",
    "protected_pipeline_state_mutated",
)


class P0WindowsOwnerPolicyV3PreflightCandidateError(RuntimeError):
    """The v3 successor preflight could not preserve fail-closed meaning."""


@dataclass(frozen=True)
class _ValidatedV3Snapshot:
    policy_body_bytes: bytes
    policy_signature_bytes: bytes
    producer_bootstrap_receipt_canonical_bytes: bytes


class _StageNoGo(RuntimeError):
    def __init__(
        self,
        stage: str,
        blocker: str,
        *,
        non_v3_hard_rejected: bool = False,
        cng_reexecution_receipt_contract_validated: bool = False,
    ) -> None:
        super().__init__(stage)
        self.stage = stage
        self.blocker = blocker
        self.non_v3_hard_rejected = non_v3_hard_rejected
        self.cng_reexecution_receipt_contract_validated = (
            cng_reexecution_receipt_contract_validated
        )


def _is_sha256(value: Any) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _fixed_watch_projection_valid(value: Any) -> bool:
    fields = {
        "requested_path",
        "identity",
        "watch_subtree",
        "notify_filter",
        "completion_status",
        "pending_request_until_interval_end_observed",
        "completion_drained_observed",
        "watch_handles_non_inheritable_verified",
        "watch_handles_closed_observed",
        "directory_change_notification_delivered_observed",
        "overflow_observed",
        "observation_gap_observed",
        "bounded_watch_observation_verified",
    }
    if type(value) is not dict or set(value) != fields:
        return False
    identity = value.get("identity")
    return (
        type(value.get("requested_path")) is str
        and bool(value["requested_path"])
        and type(identity) is dict
        and set(identity) == {"final_path", "volume_serial", "file_id"}
        and type(identity.get("final_path")) is str
        and type(identity.get("volume_serial")) is str
        and identity["volume_serial"].isdigit()
        and type(identity.get("file_id")) is str
        and len(identity["file_id"]) == 32
        and value.get("watch_subtree") is True
        and type(value.get("notify_filter")) is int
        and value.get("notify_filter") == fixed_store._WATCH_FILTER
        and type(value.get("completion_status")) is str
        and value.get("pending_request_until_interval_end_observed") is True
        and value.get("completion_drained_observed") is True
        and value.get("watch_handles_non_inheritable_verified") is True
        and value.get("watch_handles_closed_observed") is True
        and value.get("directory_change_notification_delivered_observed")
        is False
        and value.get("overflow_observed") is False
        and value.get("observation_gap_observed") is False
        and value.get("bounded_watch_observation_verified") is True
    )


def _fixed_outer_semantics_valid(
    receipt: Mapping[str, Any], body: Mapping[str, Any]
) -> bool:
    operational = body.get("operational_key")
    watches = receipt.get("directory_change_watches")
    acl_hashes = receipt.get("acl_projection_sha256_by_role")
    body_bytes = policy.json_file_bytes(body)
    return (
        type(operational) is dict
        and receipt.get("known_folder_id") == fixed_store.KNOWN_FOLDER_ID
        and type(receipt.get("known_folder_flags")) is int
        and receipt.get("known_folder_flags") == fixed_store.KNOWN_FOLDER_FLAGS
        and receipt.get("known_folder_token_is_null") is True
        and receipt.get("fixed_relative_store_components")
        == list(policy.FIXED_POLICY_STORE_SUFFIX)
        and receipt.get("selected_generation_component")
        == fixed_store.GENERATION_COMPONENT
        and type(receipt.get("selected_policy_epoch")) is int
        and receipt.get("selected_policy_epoch")
        == fixed_store.COMPILED_POLICY_EPOCH
        and type(receipt.get("role_handle_count")) is int
        and receipt.get("role_handle_count") == len(policy.OBJECT_ROLES)
        and type(receipt.get("lexical_ancestor_handle_count")) is int
        and receipt.get("lexical_ancestor_handle_count") > 0
        and type(receipt.get("policy_body_bytes_length")) is int
        and receipt.get("policy_body_bytes_length") == len(body_bytes)
        and type(receipt.get("policy_signature_bytes_length")) is int
        and 0 < receipt.get("policy_signature_bytes_length") <= 1024 * 1024
        and type(receipt.get("public_key_pin_bytes_length")) is int
        and 0 < receipt.get("public_key_pin_bytes_length") <= 1024 * 1024
        and receipt.get("public_key_id") == operational.get("key_id")
        and type(receipt.get("public_key_epoch")) is int
        and receipt.get("public_key_epoch") == operational.get("key_epoch")
        and receipt.get("public_key_fingerprint_sha256")
        == operational.get("public_key_fingerprint_sha256")
        and receipt.get("public_key_pin_bytes_sha256")
        == operational.get("pin_bytes_sha256")
        and receipt.get("public_key_pin_artifact_sha256")
        == operational.get("pin_artifact_sha256")
        and type(acl_hashes) is dict
        and set(acl_hashes) == set(policy.OBJECT_ROLES)
        and all(_is_sha256(value) for value in acl_hashes.values())
        and type(watches) is list
        and len(watches) == 2
        and all(_fixed_watch_projection_valid(row) for row in watches)
    )


def _self_hash_valid(receipt: Mapping[str, Any]) -> bool:
    declared = receipt.get("receipt_sha256")
    material = dict(receipt)
    material.pop("receipt_sha256", None)
    return (
        type(declared) is str
        and len(declared) == 64
        and hmac.compare_digest(declared, deployment.canonical_sha256(material))
    )


def _validate_bootstrap_binding(
    *,
    fixed_receipt: Mapping[str, Any],
    contract: Mapping[str, Any],
    body: Mapping[str, Any],
) -> None:
    receipt = fixed_receipt.get("bootstrap_policy_signature_candidate_receipt")
    expected_signature_material = {
        "schema_version": policy.POLICY_SIGNATURE_SCHEMA_V3,
        "record_origin": policy.SIGNATURE_ORIGIN,
        "domain": policy.SIGNATURE_DOMAIN_V3,
        "policy_id": body.get("policy_id"),
        "policy_epoch": body.get("policy_epoch"),
        "bootstrap_key_id": body.get("bootstrap_key_id"),
        "bootstrap_public_key_fingerprint_sha256": body.get(
            "bootstrap_public_key_fingerprint_sha256"
        ),
        "policy_body_bytes_sha256": fixed_receipt.get(
            "policy_body_bytes_sha256"
        ),
        "algorithm": policy.BOOTSTRAP_SIGNATURE_ALGORITHM,
    }
    if (
        type(receipt) is not dict
        or set(receipt) != _BOOTSTRAP_RECEIPT_FIELDS
        or not _self_hash_valid(receipt)
        or receipt.get("schema_version") != fixed_store.bootstrap.RECEIPT_SCHEMA
        or receipt.get("gate_status") != fixed_store.bootstrap.GATE_STATUS
        or receipt.get("candidate_only") is not True
        or receipt.get("signature_material_contract")
        != fixed_store.bootstrap.SIGNATURE_MATERIAL_CONTRACT
        or receipt.get("compiled_bootstrap_key_candidate_provenance")
        != fixed_store.bootstrap.COMPILED_BOOTSTRAP_KEY_CANDIDATE_PROVENANCE
        or receipt.get("compiled_bootstrap_key_id")
        != fixed_store.bootstrap.COMPILED_BOOTSTRAP_KEY_ID
        or receipt.get("compiled_bootstrap_public_key_fingerprint_sha256")
        != fixed_store.bootstrap.COMPILED_BOOTSTRAP_PUBLIC_KEY_FINGERPRINT_SHA256
        or receipt.get("algorithm") != policy.BOOTSTRAP_SIGNATURE_ALGORITHM
        or receipt.get("curve") != fixed_store.asymmetric.CURVE
        or receipt.get("cng_provider_name")
        != fixed_store.asymmetric.CNG_PROVIDER
        or any(
            receipt.get(field) is not True
            for field in fixed_store._BOOTSTRAP_RECEIPT_TRUE_FIELDS
        )
        or any(
            receipt.get(field) is not False
            for field in fixed_store._BOOTSTRAP_RECEIPT_FALSE_FIELDS
        )
        or receipt.get("owner_policy_contract_receipt") != contract
        or receipt.get("owner_policy_contract_receipt_declared_sha256")
        != contract.get("receipt_sha256")
        or receipt.get("policy_body_bytes_sha256")
        != fixed_receipt.get("policy_body_bytes_sha256")
        or receipt.get("policy_signature_bytes_sha256")
        != fixed_receipt.get("policy_signature_bytes_sha256")
        or receipt.get("policy_signature_artifact_sha256")
        != contract.get("policy_signature_artifact_sha256")
        or receipt.get("signature_material_envelope_field_names")
        != list(fixed_store.bootstrap._SIGNATURE_MATERIAL_FIELDS)
        or receipt.get("signature_material_bytes_sha256")
        != fixed_store.bootstrap.canonical_sha256(expected_signature_material)
        or receipt.get("compiled_bootstrap_key_id")
        != body.get("bootstrap_key_id")
        or receipt.get("compiled_bootstrap_public_key_fingerprint_sha256")
        != body.get("bootstrap_public_key_fingerprint_sha256")
        or fixed_receipt.get(
            "bootstrap_policy_signature_candidate_receipt_declared_sha256"
        )
        != receipt.get("receipt_sha256")
        or fixed_receipt.get("bootstrap_signature_input_sha256")
        != receipt.get("signature_material_bytes_sha256")
        or fixed_receipt.get("compiled_bootstrap_key_id")
        != receipt.get("compiled_bootstrap_key_id")
        or fixed_receipt.get(
            "compiled_bootstrap_public_key_fingerprint_sha256"
        )
        != receipt.get("compiled_bootstrap_public_key_fingerprint_sha256")
        or fixed_receipt.get("compiled_bootstrap_key_candidate_selected")
        is not True
        or fixed_receipt.get("bootstrap_signature_mathematics_verified")
        is not True
        or receipt.get("public_api_key_parameter_absent") is not True
        or receipt.get("public_api_provider_parameter_absent") is not True
        or type(receipt.get("credited_actual_source_claim_count")) is not int
        or receipt.get("credited_actual_source_claim_count") != 0
        or type(receipt.get("credited_actual_a_context_review_count")) is not int
        or receipt.get("credited_actual_a_context_review_count") != 0
        or receipt.get("operational_effect") != "NONE_SHADOW_ONLY"
    ):
        raise _StageNoGo(
            "OWNER_POLICY_V3", "OWNER_POLICY_V3_NOT_VERIFIED"
        )


def _validate_v3_fixed_outcome(
    fixed_receipt: Mapping[str, Any],
    body: Mapping[str, Any],
    policy_signature_bytes: bytes,
) -> _ValidatedV3Snapshot:
    if (
        type(fixed_receipt) is not dict
        or set(fixed_receipt) != _FIXED_STORE_RECEIPT_FIELDS
        or fixed_receipt.get("schema_version")
        != fixed_store.CANDIDATE_RECEIPT_SCHEMA
        or fixed_receipt.get("gate_status") != fixed_store.GATE_STATUS
        or fixed_receipt.get("candidate_only") is not True
        or not _self_hash_valid(fixed_receipt)
        or any(
            fixed_receipt.get(field) is not True
            for field in _FIXED_STORE_REQUIRED_TRUE_FIELDS
        )
        or any(
            fixed_receipt.get(field) is not False
            for field in fixed_store._FALSE_FIELDS
        )
        or type(fixed_receipt.get("credited_actual_source_claim_count")) is not int
        or fixed_receipt.get("credited_actual_source_claim_count") != 0
        or type(fixed_receipt.get("credited_actual_a_context_review_count"))
        is not int
        or fixed_receipt.get("credited_actual_a_context_review_count") != 0
        or fixed_receipt.get("operational_effect") != "NONE_SHADOW_ONLY"
    ):
        raise _StageNoGo(
            "FIXED_STORE", "FIXED_OWNER_POLICY_STORE_NOT_VERIFIED"
        )
    contract = fixed_receipt.get("owner_policy_contract_receipt")
    if type(contract) is not dict or not _self_hash_valid(contract):
        raise _StageNoGo(
            "OWNER_POLICY_V3", "OWNER_POLICY_V3_NOT_VERIFIED"
        )
    if type(body) is not dict:
        raise _StageNoGo(
            "OWNER_POLICY_V3", "OWNER_POLICY_V3_NOT_VERIFIED"
        )
    if type(policy_signature_bytes) is not bytes:
        raise _StageNoGo(
            "OWNER_POLICY_V3", "OWNER_POLICY_V3_NOT_VERIFIED"
        )
    if not _fixed_outer_semantics_valid(fixed_receipt, body):
        raise _StageNoGo(
            "FIXED_STORE", "FIXED_OWNER_POLICY_STORE_NOT_VERIFIED"
        )
    is_non_v3 = (
        contract.get("schema_version")
        in {policy.CONTRACT_RECEIPT_SCHEMA, policy.CONTRACT_RECEIPT_SCHEMA_V2}
        or body.get("schema_version")
        in {policy.POLICY_BODY_SCHEMA, policy.POLICY_BODY_SCHEMA_V2}
    )
    if is_non_v3:
        raise _StageNoGo(
            "OWNER_POLICY_V3",
            "OWNER_POLICY_V3_NOT_VERIFIED",
            non_v3_hard_rejected=True,
        )
    if set(contract) != _V3_CONTRACT_RECEIPT_FIELDS:
        raise _StageNoGo(
            "OWNER_POLICY_V3", "OWNER_POLICY_V3_NOT_VERIFIED"
        )
    if (
        contract.get("schema_version") != policy.CONTRACT_RECEIPT_SCHEMA_V3
        or contract.get("gate_status") != policy.GATE_STATUS
        or contract.get("policy_schema_version") != policy.POLICY_BODY_SCHEMA_V3
        or contract.get("policy_domain") != policy.POLICY_DOMAIN_V3
        or contract.get("signature_schema_version")
        != policy.POLICY_SIGNATURE_SCHEMA_V3
        or contract.get("signature_domain") != policy.SIGNATURE_DOMAIN_V3
        or any(
            contract.get(field) is not True
            for field in _V3_CONTRACT_REQUIRED_TRUE_FIELDS
        )
        or contract.get("future_authority_policy_version_eligible") is not False
        or contract.get("positive_native_observer_policy_profile_complete")
        is not False
        or any(
            contract.get(field) is not False
            for field in policy._ALWAYS_FALSE_FIELDS
        )
    ):
        raise _StageNoGo(
            "OWNER_POLICY_V3", "OWNER_POLICY_V3_NOT_VERIFIED"
        )
    if type(body) is not dict or body.get("schema_version") != policy.POLICY_BODY_SCHEMA_V3:
        raise _StageNoGo(
            "OWNER_POLICY_V3", "OWNER_POLICY_V3_NOT_VERIFIED"
        )
    try:
        body_bytes = policy.json_file_bytes(body)
        validated_body = policy._validate_policy_body(body_bytes)
        validated_signature = policy._validate_signature(
            policy_signature_bytes, validated_body, body_bytes
        )
        projection = deployment._validate_projection(
            validated_body["deployment_projection"]
        )
        profile = observer._validate_native_observer_profile(
            validated_body["native_observer_profile"]
        )
    except (
        policy.P0WindowsOwnerPolicyContractError,
        deployment.P0WindowsOwnerDeploymentProjectionError,
        observer.P0WindowsNativeObserverProfileContractError,
    ) as exc:
        raise _StageNoGo(
            "OWNER_POLICY_V3", "OWNER_POLICY_V3_NOT_VERIFIED"
        ) from exc
    body_hash = hashlib.sha256(body_bytes).hexdigest()
    object_identity_projection_sha256 = deployment.canonical_sha256(
        [
            {
                key: row[key]
                for key in (
                    "role",
                    "object_kind",
                    "final_volume_guid_path",
                    "volume_serial_decimal",
                    "file_id_128_hex",
                )
            }
            for row in validated_body["object_policies"]
        ]
    )
    security_template_sha256_by_role = {
        row["role"]: deployment.canonical_sha256(row["security_template"])
        for row in validated_body["object_policies"]
    }
    if (
        validated_body != body
        or body_hash != fixed_receipt.get("policy_body_bytes_sha256")
        or body_hash != contract.get("policy_body_bytes_sha256")
        or body_hash != contract.get("full_policy_identity_sha256")
        or len(policy_signature_bytes)
        != fixed_receipt.get("policy_signature_bytes_length")
        or hashlib.sha256(policy_signature_bytes).hexdigest()
        != fixed_receipt.get("policy_signature_bytes_sha256")
        or contract.get("policy_signature_bytes_sha256")
        != fixed_receipt.get("policy_signature_bytes_sha256")
        or validated_signature.get("artifact_sha256")
        != contract.get("policy_signature_artifact_sha256")
        or type(contract.get("policy_epoch")) is not int
        or contract.get("policy_id") != body.get("policy_id")
        or contract.get("policy_epoch") != body.get("policy_epoch")
        or contract.get("store_id") != body.get("store_id")
        or contract.get("owner_principal_sha256")
        != body.get("owner_principal_sha256")
        or contract.get("owner_anchor_sha256")
        != body.get("owner_anchor_sha256")
        or contract.get("acl_template_sha256")
        != body.get("acl_template_sha256")
        or contract.get("operational_key_projection_sha256")
        != body.get("operational_key_projection_sha256")
        or contract.get("object_identity_projection_sha256")
        != object_identity_projection_sha256
        or contract.get("security_template_sha256_by_role")
        != security_template_sha256_by_role
        or contract.get("owner_anchor_scope")
        != "CORE_POLICY_IDENTITY_EXCLUDING_PIN_TRANSPORT_HASHES"
        or contract.get("owner_anchor_excludes_pin_transport_hashes_by_design")
        is not True
        or contract.get("policy_body_artifact_sha256")
        != body.get("artifact_sha256")
        or fixed_receipt.get("owner_policy_contract_receipt_declared_sha256")
        != contract.get("receipt_sha256")
        or fixed_receipt.get("owner_policy_contract_receipt_full_canonical_sha256")
        != deployment.canonical_sha256(contract)
        or contract.get("deployment_projection_sha256")
        != projection.get("artifact_sha256")
        or contract.get("native_observer_profile_sha256")
        != profile.get("artifact_sha256")
        or profile.get("deployment_projection_sha256")
        != projection.get("artifact_sha256")
        or profile.get("service_name") != projection.get("service_name")
        or profile.get("service_sid") != projection.get("service_sid")
    ):
        raise _StageNoGo(
            "OWNER_POLICY_V3", "OWNER_POLICY_V3_NOT_VERIFIED"
        )
    operational = body.get("operational_key")
    if type(operational) is not dict:
        raise _StageNoGo(
            "OWNER_POLICY_V3", "OWNER_POLICY_V3_NOT_VERIFIED"
        )
    key_ids = {
        body.get("bootstrap_key_id"),
        operational.get("key_id"),
        profile.get("observer_key_id"),
        profile.get("owner_state_authority_key_id"),
    }
    fingerprints = {
        body.get("bootstrap_public_key_fingerprint_sha256"),
        operational.get("public_key_fingerprint_sha256"),
        profile.get("observer_public_key_fingerprint_sha256"),
        profile.get("owner_state_authority_spki_sha256"),
    }
    if len(key_ids) != 4 or len(fingerprints) != 4:
        raise _StageNoGo(
            "OWNER_POLICY_V3", "OWNER_POLICY_V3_NOT_VERIFIED"
        )
    _validate_bootstrap_binding(
        fixed_receipt=fixed_receipt, contract=contract, body=body
    )
    producer_bootstrap_receipt = fixed_receipt.get(
        "bootstrap_policy_signature_candidate_receipt"
    )
    assert type(producer_bootstrap_receipt) is dict
    return _ValidatedV3Snapshot(
        policy_body_bytes=body_bytes,
        policy_signature_bytes=policy_signature_bytes,
        producer_bootstrap_receipt_canonical_bytes=policy.canonical_bytes(
            producer_bootstrap_receipt
        ),
    )


def _reexecute_bootstrap_cng_for_same_snapshot(
    snapshot: _ValidatedV3Snapshot,
) -> None:
    """Re-run fixed CNG verification over the validated snapshot bytes.

    This is a same-process consistency check.  It does not establish an
    independent verifier, trusted code/provider provenance, or owner trust.
    """

    try:
        receipt = (
            fixed_store.bootstrap.verify_presented_windows_owner_policy_bootstrap_signature_candidate(
                policy_body_bytes=snapshot.policy_body_bytes,
                policy_signature_bytes=snapshot.policy_signature_bytes,
            )
        )
    except Exception as exc:
        raise _StageNoGo(
            "BOOTSTRAP_CNG_REEXECUTION",
            "BOOTSTRAP_CNG_REEXECUTION_NOT_VERIFIED",
        ) from exc
    if (
        type(receipt) is not dict
        or set(receipt) != _BOOTSTRAP_RECEIPT_FIELDS
        or not _self_hash_valid(receipt)
        or receipt.get("schema_version") != fixed_store.bootstrap.RECEIPT_SCHEMA
        or receipt.get("gate_status") != fixed_store.bootstrap.GATE_STATUS
        or receipt.get("candidate_only") is not True
        or receipt.get("signature_material_contract")
        != fixed_store.bootstrap.SIGNATURE_MATERIAL_CONTRACT
        or receipt.get("compiled_bootstrap_key_candidate_provenance")
        != fixed_store.bootstrap.COMPILED_BOOTSTRAP_KEY_CANDIDATE_PROVENANCE
        or receipt.get("algorithm") != policy.BOOTSTRAP_SIGNATURE_ALGORITHM
        or receipt.get("curve") != fixed_store.asymmetric.CURVE
        or receipt.get("cng_provider_name")
        != fixed_store.asymmetric.CNG_PROVIDER
        or any(
            receipt.get(field) is not True
            for field in fixed_store._BOOTSTRAP_RECEIPT_TRUE_FIELDS
        )
        or any(
            receipt.get(field) is not False
            for field in fixed_store._BOOTSTRAP_RECEIPT_FALSE_FIELDS
        )
        or receipt.get("public_api_key_parameter_absent") is not True
        or receipt.get("public_api_provider_parameter_absent") is not True
        or type(receipt.get("credited_actual_source_claim_count")) is not int
        or receipt.get("credited_actual_source_claim_count") != 0
        or type(receipt.get("credited_actual_a_context_review_count")) is not int
        or receipt.get("credited_actual_a_context_review_count") != 0
        or receipt.get("operational_effect") != "NONE_SHADOW_ONLY"
    ):
        raise _StageNoGo(
            "BOOTSTRAP_CNG_REEXECUTION",
            "BOOTSTRAP_CNG_REEXECUTION_NOT_VERIFIED",
        )
    if not hmac.compare_digest(
        policy.canonical_bytes(receipt),
        snapshot.producer_bootstrap_receipt_canonical_bytes,
    ):
        raise _StageNoGo(
            "BOOTSTRAP_CNG_REEXECUTION",
            "BOOTSTRAP_CNG_REEXECUTION_RECEIPT_MISMATCH",
            cng_reexecution_receipt_contract_validated=True,
        )


def _receipt(
    *,
    failure_stage: str,
    observations: Mapping[str, bool],
    primary_blocker: str,
) -> dict[str, Any]:
    selected = {primary_blocker, *_BLOCKER_ORDER[6:]}
    if not observations.get("fixed_policy_store_candidate_observed", False):
        selected.add("FIXED_OWNER_POLICY_STORE_NOT_VERIFIED")
    if not observations.get("owner_policy_v3_contract_verified", False):
        selected.add("OWNER_POLICY_V3_NOT_VERIFIED")
        selected.add("POSITIVE_NATIVE_OBSERVER_POLICY_PROFILE_NOT_VERIFIED")
    else:
        selected.add("POSITIVE_NATIVE_OBSERVER_POLICY_PROFILE_INCOMPLETE")
    blockers = [code for code in _BLOCKER_ORDER if code in selected]
    material: dict[str, Any] = {
        "schema_version": RECEIPT_SCHEMA,
        "gate_status": GATE_STATUS,
        "decision": "NO_GO",
        "failure_stage": failure_stage,
        "blocker_codes": blockers,
        "candidate_only": True,
        "zero_input_public_api_verified": True,
        "caller_supplied_selector_absent": True,
        **{
            field: bool(observations.get(field, False))
            for field in _OBSERVATION_FIELDS
        },
        "non_v3_policy_versions_ineligible_by_contract": True,
        "current_transcript_schema_positive_path_closed_by_contract": True,
        "positive_native_observer_hard_rejected": True,
        **{field: False for field in _ALWAYS_FALSE_FIELDS},
        "credited_actual_source_claim_count": 0,
        "credited_actual_a_context_review_count": 0,
        "operational_effect": OPERATIONAL_EFFECT,
    }
    return {**material, "receipt_sha256": deployment.canonical_sha256(material)}


def _observe_v3_preflight_candidate() -> dict[str, Any]:
    observations = {field: False for field in _OBSERVATION_FIELDS}
    try:
        fixed_receipt, body, policy_signature_bytes = (
            fixed_store._observe_fixed_windows_owner_policy_store_candidate_with_body_and_signature_bytes()
        )
    except fixed_store.P0WindowsFixedOwnerPolicyStoreCandidateError:
        return _receipt(
            failure_stage="FIXED_STORE",
            observations=observations,
            primary_blocker="FIXED_OWNER_POLICY_STORE_NOT_VERIFIED",
        )
    observations["fixed_policy_store_candidate_observed"] = True
    try:
        snapshot = _validate_v3_fixed_outcome(
            fixed_receipt, body, policy_signature_bytes
        )
    except _StageNoGo as exc:
        if exc.stage == "FIXED_STORE":
            observations["fixed_policy_store_candidate_observed"] = False
        observations["non_v3_policy_version_input_hard_rejected"] = (
            exc.non_v3_hard_rejected
        )
        return _receipt(
            failure_stage=exc.stage,
            observations=observations,
            primary_blocker=exc.blocker,
        )
    observations.update(
        {
            "owner_policy_v3_contract_verified": True,
            "producer_bootstrap_receipt_exact_validated": True,
            "producer_bootstrap_signature_math_result_observed": True,
            "deployment_projection_cross_binding_verified": True,
            "native_observer_profile_component_contract_verified": True,
            "policy_deployment_native_profile_cross_binding_verified": True,
            "four_key_role_separation_contract_verified": True,
            "current_v3_positive_profile_incomplete_verified": True,
        }
    )
    observations[
        "successor_bootstrap_cng_same_process_reexecution_attempted"
    ] = True
    observations[
        "same_snapshot_policy_bytes_used_for_cng_reexecution"
    ] = True
    try:
        _reexecute_bootstrap_cng_for_same_snapshot(snapshot)
    except _StageNoGo as exc:
        observations[
            "successor_reexecution_receipt_contract_validated"
        ] = exc.cng_reexecution_receipt_contract_validated
        return _receipt(
            failure_stage=exc.stage,
            observations=observations,
            primary_blocker=exc.blocker,
        )
    observations.update(
        {
            "successor_bootstrap_cng_same_process_reexecution_succeeded": True,
            "successor_reexecution_receipt_contract_validated": True,
            "successor_reexecution_receipt_exact_match_verified": True,
            "bootstrap_signature_math_two_execution_consistency_verified": True,
            "bootstrap_signature_mathematics_verified": True,
        }
    )
    return _receipt(
        failure_stage="POSITIVE_PROFILE",
        observations=observations,
        primary_blocker="POSITIVE_NATIVE_OBSERVER_POLICY_PROFILE_INCOMPLETE",
    )


def observe_fixed_windows_owner_policy_v3_preflight_candidate() -> dict[str, Any]:
    """Observe the fixed v3 component and stop before SCM/native IPC."""

    if not _IS_WINDOWS:
        raise P0WindowsOwnerPolicyV3PreflightCandidateError(
            "Windows owner-policy v3 preflight is Windows-only"
        )
    try:
        return _observe_v3_preflight_candidate()
    except P0WindowsOwnerPolicyV3PreflightCandidateError:
        raise
    except BaseException as exc:
        raise P0WindowsOwnerPolicyV3PreflightCandidateError(
            "Windows owner-policy v3 preflight failed closed"
        ) from exc


__all__ = [
    "GATE_STATUS",
    "P0WindowsOwnerPolicyV3PreflightCandidateError",
    "RECEIPT_SCHEMA",
    "observe_fixed_windows_owner_policy_v3_preflight_candidate",
]
