"""Zero-input, read-only Windows owner provisioning preflight candidate.

This module can reject an unprovisioned or mismatched host.  It cannot grant
authority: Python is not the future signed native observer, the fixed-store
and host checks do not share one atomic observation interval, and trusted
Authenticode/WDAC/provider/time evidence remains external work.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
import hashlib
import hmac
import os
from typing import Any, Mapping

from . import p0_windows_fixed_directory_identity as fixed
from . import p0_windows_fixed_owner_policy_store_candidate as fixed_store
from . import p0_windows_owner_deployment_projection as deployment
from . import p0_windows_owner_policy_contract as policy


RECEIPT_SCHEMA = "p0_windows_owner_provisioning_preflight_candidate_receipt_v1"
GATE_STATUS = (
    "WINDOWS_OWNER_PROVISIONING_PREFLIGHT_CANDIDATE_EXECUTED_"
    "HOST_AND_EXTERNAL_PROVISIONING_NO_GO"
)

_IS_WINDOWS = os.name == "nt"
_SC_MANAGER_CONNECT = 0x0001
_SERVICE_QUERY_CONFIG = 0x0001
_SERVICE_WIN32_OWN_PROCESS = 0x00000010
_SERVICE_DEMAND_START = 0x00000003
_SERVICE_ERROR_NORMAL = 0x00000001
_SERVICE_CONFIG_SERVICE_SID_INFO = 5
_SERVICE_SID_TYPE_RESTRICTED = 3
_ERROR_INSUFFICIENT_BUFFER = 122
_ERROR_SERVICE_DOES_NOT_EXIST = 1060
_MAX_SERVICE_CONFIG_BYTES = 64 * 1024
_HANDLE_FLAG_INHERIT = 0x00000001

_BLOCKER_ORDER = (
    "FIXED_OWNER_POLICY_STORE_NOT_VERIFIED",
    "OWNER_POLICY_V2_NOT_VERIFIED",
    "SERVICE_CONFIGURATION_NOT_VERIFIED",
    "SERVICE_IMAGE_IDENTITY_NOT_VERIFIED",
    "SERVICE_PROCESS_TOKEN_NOT_VERIFIED",
    "EMBEDDED_BOOTSTRAP_RESOURCE_NOT_VERIFIED",
    "AUTHENTICODE_NOT_VERIFIED",
    "WDAC_UMCI_NOT_VERIFIED",
    "LOADED_CNG_PROVIDER_NOT_VERIFIED",
    "TRUSTED_TIME_REVOCATION_NOT_VERIFIED",
    "SIGNED_NATIVE_OBSERVER_NOT_VERIFIED",
    "SINGLE_INTERVAL_STORE_HOST_BINDING_NOT_VERIFIED",
    "EXTERNAL_OWNER_PROVISIONING_NOT_VERIFIED",
)

_OBSERVATION_FIELDS = (
    "fixed_policy_store_candidate_observed",
    "owner_policy_v2_contract_verified",
    "v1_future_authority_hard_rejected",
    "bootstrap_signature_mathematics_verified",
    "deployment_projection_cross_binding_verified",
    "service_configuration_candidate_verified",
    "service_image_identity_candidate_verified",
)

_ALWAYS_FALSE_FIELDS = (
    "service_process_token_verified",
    "embedded_bootstrap_resource_verified",
    "trusted_verifier_code_identity_verified",
    "wdac_umci_enforced_verified",
    "wdac_policy_identity_hash_verified",
    "loaded_cng_provider_identity_verified",
    "trusted_cng_provider_provenance_verified",
    "trusted_time_verified",
    "revocation_current_verified",
    "signed_native_observer_receipt_verified",
    "single_interval_store_host_cross_binding_verified",
    "serialized_receipt_authoritative",
    "external_owner_policy_provisioning_verified",
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

_CONTRACT_REQUIRED_TRUE_FIELDS = (
    "strict_canonical_policy_body_verified",
    "strict_canonical_detached_signature_envelope_verified",
    "owner_and_verifier_sid_disjoint_contract_verified",
    "fixed_generation_layout_contract_verified",
    "exact_standard_explicit_ace_profile_contract_verified",
    "derived_owner_anchor_cross_binding_verified",
    "detached_signature_body_hash_cross_binding_verified",
    "deployment_projection_contract_verified",
    "policy_verifier_sid_deployment_service_sid_cross_binding_verified",
    "future_authority_policy_requires_v2",
    "future_authority_policy_version_eligible",
)


class P0WindowsOwnerProvisioningPreflightCandidateError(RuntimeError):
    """The preflight itself could not preserve its fail-closed contract."""


class _StageNoGo(RuntimeError):
    def __init__(
        self,
        stage: str,
        blockers: tuple[str, ...],
        *,
        v1_hard_rejected: bool = False,
    ) -> None:
        super().__init__(stage)
        self.stage = stage
        self.blockers = blockers
        self.v1_hard_rejected = v1_hard_rejected


class _QUERY_SERVICE_CONFIGW(ctypes.Structure):
    _fields_ = [
        ("dwServiceType", wintypes.DWORD),
        ("dwStartType", wintypes.DWORD),
        ("dwErrorControl", wintypes.DWORD),
        ("lpBinaryPathName", wintypes.LPWSTR),
        ("lpLoadOrderGroup", wintypes.LPWSTR),
        ("dwTagId", wintypes.DWORD),
        ("lpDependencies", wintypes.LPWSTR),
        ("lpServiceStartName", wintypes.LPWSTR),
        ("lpDisplayName", wintypes.LPWSTR),
    ]


class _SERVICE_SID_INFO(ctypes.Structure):
    _fields_ = [("dwServiceSidType", wintypes.DWORD)]


@dataclass(frozen=True)
class _ServiceConfiguration:
    service_type: int
    start_type: int
    error_control: int
    binary_path: str
    start_account: str
    service_sid_type: int


class _ServiceApi:
    def __init__(self) -> None:
        if not _IS_WINDOWS:
            raise P0WindowsOwnerProvisioningPreflightCandidateError(
                "Windows SCM observation is unavailable"
            )
        advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
        self.OpenSCManagerW = advapi32.OpenSCManagerW
        self.OpenSCManagerW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.LPCWSTR,
            wintypes.DWORD,
        ]
        self.OpenSCManagerW.restype = wintypes.HANDLE
        self.OpenServiceW = advapi32.OpenServiceW
        self.OpenServiceW.argtypes = [
            wintypes.HANDLE,
            wintypes.LPCWSTR,
            wintypes.DWORD,
        ]
        self.OpenServiceW.restype = wintypes.HANDLE
        self.QueryServiceConfigW = advapi32.QueryServiceConfigW
        self.QueryServiceConfigW.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(_QUERY_SERVICE_CONFIGW),
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
        ]
        self.QueryServiceConfigW.restype = wintypes.BOOL
        self.QueryServiceConfig2W = advapi32.QueryServiceConfig2W
        self.QueryServiceConfig2W.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.BYTE),
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
        ]
        self.QueryServiceConfig2W.restype = wintypes.BOOL
        self.CloseServiceHandle = advapi32.CloseServiceHandle
        self.CloseServiceHandle.argtypes = [wintypes.HANDLE]
        self.CloseServiceHandle.restype = wintypes.BOOL


class _OwnedServiceHandle:
    def __init__(self, api: _ServiceApi, value: int, label: str) -> None:
        self.api = api
        self.value = value
        self.label = label

    def __enter__(self) -> "_OwnedServiceHandle":
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        value = self.value
        self.value = None  # type: ignore[assignment]
        if value:
            try:
                closed = self.api.CloseServiceHandle(value)
            except BaseException as cleanup_error:
                if exc_type is None:
                    raise P0WindowsOwnerProvisioningPreflightCandidateError(
                        f"{self.label} cleanup raised"
                    ) from cleanup_error
                return
            if not closed and exc_type is None:
                raise P0WindowsOwnerProvisioningPreflightCandidateError(
                    f"{self.label} cleanup failed"
                )


class _HandleFlagsApi:
    def __init__(self) -> None:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self.GetHandleInformation = kernel32.GetHandleInformation
        self.GetHandleInformation.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(wintypes.DWORD),
        ]
        self.GetHandleInformation.restype = wintypes.BOOL


def _assert_non_inheritable(api: _HandleFlagsApi, handle: int) -> None:
    flags = wintypes.DWORD()
    if not api.GetHandleInformation(handle, ctypes.byref(flags)):
        raise P0WindowsOwnerProvisioningPreflightCandidateError(
            "image handle flags query failed"
        )
    if flags.value & _HANDLE_FLAG_INHERIT:
        raise P0WindowsOwnerProvisioningPreflightCandidateError(
            "image handle must be non-inheritable"
        )


def _self_hash_valid(receipt: Mapping[str, Any]) -> bool:
    declared = receipt.get("receipt_sha256")
    if not isinstance(declared, str):
        return False
    material = dict(receipt)
    material.pop("receipt_sha256", None)
    return hmac.compare_digest(declared, deployment.canonical_sha256(material))


def _validated_projection_from_fixed_outcome(
    receipt: Mapping[str, Any], body: Mapping[str, Any]
) -> dict[str, Any]:
    if (
        type(receipt) is not dict
        or receipt.get("schema_version") != fixed_store.CANDIDATE_RECEIPT_SCHEMA
        or receipt.get("gate_status") != fixed_store.GATE_STATUS
        or receipt.get("candidate_only") is not True
        or receipt.get("fixed_policy_store_discovery_candidate_observed") is not True
        or not _self_hash_valid(receipt)
        or any(
            receipt.get(field) is not True
            for field in _FIXED_STORE_REQUIRED_TRUE_FIELDS
        )
        or any(receipt.get(field) is not False for field in fixed_store._FALSE_FIELDS)
    ):
        raise _StageNoGo(
            "FIXED_STORE",
            ("FIXED_OWNER_POLICY_STORE_NOT_VERIFIED",),
        )
    contract = receipt.get("owner_policy_contract_receipt")
    if type(contract) is not dict or not _self_hash_valid(contract):
        raise _StageNoGo("OWNER_POLICY_V2", ("OWNER_POLICY_V2_NOT_VERIFIED",))
    if (
        contract.get("schema_version") == policy.CONTRACT_RECEIPT_SCHEMA
        and type(body) is dict
        and body.get("schema_version") == policy.POLICY_BODY_SCHEMA
        and body.get("domain") == policy.POLICY_DOMAIN
        and contract.get("full_policy_identity_sha256")
        == hashlib.sha256(policy.json_file_bytes(body)).hexdigest()
        and contract.get("policy_body_bytes_sha256")
        == contract.get("full_policy_identity_sha256")
        and receipt.get("policy_body_bytes_sha256")
        == contract.get("full_policy_identity_sha256")
        and receipt.get("owner_policy_contract_receipt_declared_sha256")
        == contract.get("receipt_sha256")
        and receipt.get("owner_policy_contract_receipt_full_canonical_sha256")
        == deployment.canonical_sha256(contract)
    ):
        raise _StageNoGo(
            "OWNER_POLICY_V2",
            ("OWNER_POLICY_V2_NOT_VERIFIED",),
            v1_hard_rejected=True,
        )
    if (
        contract.get("schema_version") != policy.CONTRACT_RECEIPT_SCHEMA_V2
        or contract.get("gate_status") != policy.GATE_STATUS
        or contract.get("policy_schema_version") != policy.POLICY_BODY_SCHEMA_V2
        or contract.get("policy_domain") != policy.POLICY_DOMAIN_V2
        or contract.get("signature_schema_version")
        != policy.POLICY_SIGNATURE_SCHEMA_V2
        or contract.get("signature_domain") != policy.SIGNATURE_DOMAIN_V2
        or contract.get("deployment_projection_contract_verified") is not True
        or contract.get(
            "policy_verifier_sid_deployment_service_sid_cross_binding_verified"
        )
        is not True
        or contract.get("future_authority_policy_version_eligible") is not True
        or any(
            contract.get(field) is not True
            for field in _CONTRACT_REQUIRED_TRUE_FIELDS
        )
        or any(contract.get(field) is not False for field in policy._ALWAYS_FALSE_FIELDS)
    ):
        raise _StageNoGo("OWNER_POLICY_V2", ("OWNER_POLICY_V2_NOT_VERIFIED",))
    if type(body) is not dict:
        raise _StageNoGo("OWNER_POLICY_V2", ("OWNER_POLICY_V2_NOT_VERIFIED",))
    bootstrap_receipt = receipt.get(
        "bootstrap_policy_signature_candidate_receipt"
    )
    if (
        type(bootstrap_receipt) is not dict
        or not _self_hash_valid(bootstrap_receipt)
        or bootstrap_receipt.get("schema_version")
        != fixed_store.bootstrap.RECEIPT_SCHEMA
        or bootstrap_receipt.get("gate_status") != fixed_store.bootstrap.GATE_STATUS
        or bootstrap_receipt.get("candidate_only") is not True
        or bootstrap_receipt.get("signature_material_contract")
        != fixed_store.bootstrap.SIGNATURE_MATERIAL_CONTRACT
        or bootstrap_receipt.get("compiled_bootstrap_key_candidate_provenance")
        != fixed_store.bootstrap.COMPILED_BOOTSTRAP_KEY_CANDIDATE_PROVENANCE
        or bootstrap_receipt.get("algorithm")
        != policy.BOOTSTRAP_SIGNATURE_ALGORITHM
        or bootstrap_receipt.get("curve") != fixed_store.asymmetric.CURVE
        or bootstrap_receipt.get("cng_provider_name")
        != fixed_store.asymmetric.CNG_PROVIDER
        or any(
            bootstrap_receipt.get(field) is not True
            for field in fixed_store._BOOTSTRAP_RECEIPT_TRUE_FIELDS
        )
        or any(
            bootstrap_receipt.get(field) is not False
            for field in fixed_store._BOOTSTRAP_RECEIPT_FALSE_FIELDS
        )
        or bootstrap_receipt.get("bootstrap_signature_mathematics_verified")
        is not True
        or bootstrap_receipt.get("owner_policy_contract_receipt") != contract
        or bootstrap_receipt.get("owner_policy_contract_receipt_declared_sha256")
        != contract.get("receipt_sha256")
        or bootstrap_receipt.get("compiled_bootstrap_key_id")
        != body.get("bootstrap_key_id")
        or bootstrap_receipt.get(
            "compiled_bootstrap_public_key_fingerprint_sha256"
        )
        != body.get("bootstrap_public_key_fingerprint_sha256")
        or bootstrap_receipt.get("policy_body_bytes_sha256")
        != receipt.get("policy_body_bytes_sha256")
        or bootstrap_receipt.get("policy_signature_bytes_sha256")
        != receipt.get("policy_signature_bytes_sha256")
        or receipt.get(
            "bootstrap_policy_signature_candidate_receipt_declared_sha256"
        )
        != bootstrap_receipt.get("receipt_sha256")
        or receipt.get("bootstrap_signature_input_sha256")
        != bootstrap_receipt.get("signature_material_bytes_sha256")
        or receipt.get("compiled_bootstrap_key_id")
        != bootstrap_receipt.get("compiled_bootstrap_key_id")
        or receipt.get("compiled_bootstrap_public_key_fingerprint_sha256")
        != bootstrap_receipt.get(
            "compiled_bootstrap_public_key_fingerprint_sha256"
        )
        or receipt.get("compiled_bootstrap_key_candidate_selected") is not True
        or receipt.get("bootstrap_signature_mathematics_verified") is not True
    ):
        raise _StageNoGo("OWNER_POLICY_V2", ("OWNER_POLICY_V2_NOT_VERIFIED",))
    if body.get("schema_version") != policy.POLICY_BODY_SCHEMA_V2:
        raise _StageNoGo("OWNER_POLICY_V2", ("OWNER_POLICY_V2_NOT_VERIFIED",))
    body_hash = hashlib.sha256(policy.json_file_bytes(body)).hexdigest()
    if (
        body_hash != receipt.get("policy_body_bytes_sha256")
        or contract.get("full_policy_identity_sha256") != body_hash
        or contract.get("policy_body_artifact_sha256")
        != body.get("artifact_sha256")
        or receipt.get("owner_policy_contract_receipt_declared_sha256")
        != contract.get("receipt_sha256")
        or receipt.get("owner_policy_contract_receipt_full_canonical_sha256")
        != deployment.canonical_sha256(contract)
    ):
        raise _StageNoGo("OWNER_POLICY_V2", ("OWNER_POLICY_V2_NOT_VERIFIED",))
    projection = body.get("deployment_projection")
    if type(projection) is not dict:
        raise _StageNoGo("OWNER_POLICY_V2", ("OWNER_POLICY_V2_NOT_VERIFIED",))
    projection_receipt = (
        deployment.validate_windows_owner_deployment_projection_contract(
            projection=projection
        )
    )
    if projection_receipt["deployment_projection_sha256"] != contract.get(
        "deployment_projection_sha256"
    ):
        raise _StageNoGo("OWNER_POLICY_V2", ("OWNER_POLICY_V2_NOT_VERIFIED",))
    return dict(projection)


def _query_service_configuration_buffer(
    api: _ServiceApi, service: int
) -> tuple[int, int, int, str, str]:
    required = wintypes.DWORD()
    if api.QueryServiceConfigW(service, None, 0, ctypes.byref(required)):
        raise P0WindowsOwnerProvisioningPreflightCandidateError(
            "SCM configuration size probe unexpectedly succeeded"
        )
    if ctypes.get_last_error() != _ERROR_INSUFFICIENT_BUFFER:
        raise P0WindowsOwnerProvisioningPreflightCandidateError(
            "SCM configuration size probe failed"
        )
    if not ctypes.sizeof(_QUERY_SERVICE_CONFIGW) <= required.value <= (
        _MAX_SERVICE_CONFIG_BYTES
    ):
        raise P0WindowsOwnerProvisioningPreflightCandidateError(
            "SCM configuration buffer is outside the strict bound"
        )
    buffer = ctypes.create_string_buffer(required.value)
    pointer = ctypes.cast(buffer, ctypes.POINTER(_QUERY_SERVICE_CONFIGW))
    if not api.QueryServiceConfigW(
        service, pointer, required.value, ctypes.byref(required)
    ):
        raise P0WindowsOwnerProvisioningPreflightCandidateError(
            "SCM configuration query failed"
        )
    config = pointer.contents
    # Copy pointer-backed strings before the bounded query buffer leaves scope.
    return (
        int(config.dwServiceType),
        int(config.dwStartType),
        int(config.dwErrorControl),
        config.lpBinaryPathName or "",
        config.lpServiceStartName or "",
    )


def _query_service_sid_type(api: _ServiceApi, service: int) -> int:
    required = wintypes.DWORD()
    if api.QueryServiceConfig2W(
        service, _SERVICE_CONFIG_SERVICE_SID_INFO, None, 0, ctypes.byref(required)
    ):
        raise P0WindowsOwnerProvisioningPreflightCandidateError(
            "service SID type size probe unexpectedly succeeded"
        )
    if ctypes.get_last_error() != _ERROR_INSUFFICIENT_BUFFER:
        raise P0WindowsOwnerProvisioningPreflightCandidateError(
            "service SID type size probe failed"
        )
    if not ctypes.sizeof(_SERVICE_SID_INFO) <= required.value <= 256:
        raise P0WindowsOwnerProvisioningPreflightCandidateError(
            "service SID type buffer is outside the strict bound"
        )
    buffer = ctypes.create_string_buffer(required.value)
    pointer = ctypes.cast(buffer, ctypes.POINTER(_SERVICE_SID_INFO))
    byte_pointer = ctypes.cast(buffer, ctypes.POINTER(wintypes.BYTE))
    if not api.QueryServiceConfig2W(
        service,
        _SERVICE_CONFIG_SERVICE_SID_INFO,
        byte_pointer,
        required.value,
        ctypes.byref(required),
    ):
        raise P0WindowsOwnerProvisioningPreflightCandidateError(
            "service SID type query failed"
        )
    return int(pointer.contents.dwServiceSidType)


def _observe_fixed_service_configuration_candidate(
) -> _ServiceConfiguration | None:
    api = _ServiceApi()
    manager_value = api.OpenSCManagerW(None, None, _SC_MANAGER_CONNECT)
    if not manager_value:
        raise P0WindowsOwnerProvisioningPreflightCandidateError(
            "OpenSCManagerW failed"
        )
    with _OwnedServiceHandle(api, manager_value, "SCM handle") as manager:
        service_value = api.OpenServiceW(
            manager.value, deployment.SERVICE_NAME, _SERVICE_QUERY_CONFIG
        )
        if not service_value:
            if ctypes.get_last_error() == _ERROR_SERVICE_DOES_NOT_EXIST:
                return None
            raise P0WindowsOwnerProvisioningPreflightCandidateError(
                "OpenServiceW failed"
            )
        with _OwnedServiceHandle(api, service_value, "service handle") as service:
            (
                service_type,
                start_type,
                error_control,
                binary_path,
                start_account,
            ) = _query_service_configuration_buffer(api, service.value)
            return _ServiceConfiguration(
                service_type=service_type,
                start_type=start_type,
                error_control=error_control,
                binary_path=binary_path,
                start_account=start_account,
                service_sid_type=_query_service_sid_type(api, service.value),
            )


def _validate_service_configuration_candidate(
    projection: Mapping[str, Any], observed: _ServiceConfiguration
) -> dict[str, Any]:
    expected_binary_path = f'"{projection["image_final_volume_guid_path"]}"'
    expected = _ServiceConfiguration(
        service_type=_SERVICE_WIN32_OWN_PROCESS,
        start_type=_SERVICE_DEMAND_START,
        error_control=_SERVICE_ERROR_NORMAL,
        binary_path=expected_binary_path,
        start_account="LocalSystem",
        service_sid_type=_SERVICE_SID_TYPE_RESTRICTED,
    )
    if observed != expected:
        raise _StageNoGo(
            "SERVICE_CONFIGURATION",
            ("SERVICE_CONFIGURATION_NOT_VERIFIED",),
        )
    return {
        "service_name": deployment.SERVICE_NAME,
        "service_type": deployment.SERVICE_TYPE,
        "service_start_type": deployment.SERVICE_START_TYPE,
        "service_error_control": deployment.SERVICE_ERROR_CONTROL,
        "service_sid_type": deployment.SERVICE_SID_TYPE,
        "service_start_account_sid": deployment.SERVICE_START_ACCOUNT_SID,
        "service_binary_path_argv_policy": (
            deployment.SERVICE_BINARY_PATH_ARGV_POLICY
        ),
        "raw_binary_path_sha256": hashlib.sha256(
            observed.binary_path.encode("utf-16-le")
        ).hexdigest(),
    }


def _observe_service_image_identity_candidate(
    projection: Mapping[str, Any]
) -> dict[str, Any]:
    api = fixed._Win32()
    flags_api = _HandleFlagsApi()
    image_path = projection["image_final_volume_guid_path"]
    with fixed._open_handle(
        api, image_path, directory=False, read_data=True
    ) as handle:
        _assert_non_inheritable(flags_api, handle.value)
        before = fixed._query_snapshot(api, handle.value, include_streams=True)
        fixed._assert_regular_single_link(before, "owner verifier image")
        if (
            before.final_path != image_path
            or str(before.volume_serial)
            != projection["image_volume_serial_decimal"]
            or before.file_id != projection["image_file_id_128_hex"]
        ):
            raise _StageNoGo(
                "SERVICE_IMAGE",
                ("SERVICE_IMAGE_IDENTITY_NOT_VERIFIED",),
            )
        raw = fixed._read_handle_exact(
            api, handle.value, before.standard[1], "owner verifier image"
        )
        after = fixed._query_snapshot(api, handle.value, include_streams=True)
        if (
            not fixed._snapshot_stable(before, after)
            or not hmac.compare_digest(
                hashlib.sha256(raw).hexdigest(), projection["image_sha256"]
            )
        ):
            raise _StageNoGo(
                "SERVICE_IMAGE",
                ("SERVICE_IMAGE_IDENTITY_NOT_VERIFIED",),
            )
    return {
        "final_volume_guid_path": before.final_path,
        "volume_serial_decimal": str(before.volume_serial),
        "file_id_128_hex": before.file_id,
        "image_sha256": hashlib.sha256(raw).hexdigest(),
        "held_handle_pre_post_stable": True,
        "single_link_non_reparse_unnamed_stream_verified": True,
        "handle_non_inheritable_verified": True,
    }


def _ordered_blockers(*groups: tuple[str, ...]) -> list[str]:
    selected = {item for group in groups for item in group}
    return [item for item in _BLOCKER_ORDER if item in selected]


def _receipt(
    *,
    failure_stage: str,
    observations: Mapping[str, bool],
    blockers: tuple[str, ...],
    service_projection: Mapping[str, Any] | None = None,
    image_projection: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    structural = tuple(
        blocker
        for verified, blocker in (
            (
                observations.get("fixed_policy_store_candidate_observed", False),
                "FIXED_OWNER_POLICY_STORE_NOT_VERIFIED",
            ),
            (
                observations.get("owner_policy_v2_contract_verified", False),
                "OWNER_POLICY_V2_NOT_VERIFIED",
            ),
            (
                observations.get("service_configuration_candidate_verified", False),
                "SERVICE_CONFIGURATION_NOT_VERIFIED",
            ),
            (
                observations.get("service_image_identity_candidate_verified", False),
                "SERVICE_IMAGE_IDENTITY_NOT_VERIFIED",
            ),
        )
        if not verified
    )
    downstream = tuple(
        blocker
        for blocker in _BLOCKER_ORDER
        if blocker
        in {
            "SERVICE_PROCESS_TOKEN_NOT_VERIFIED",
            "EMBEDDED_BOOTSTRAP_RESOURCE_NOT_VERIFIED",
            "AUTHENTICODE_NOT_VERIFIED",
            "WDAC_UMCI_NOT_VERIFIED",
            "LOADED_CNG_PROVIDER_NOT_VERIFIED",
            "TRUSTED_TIME_REVOCATION_NOT_VERIFIED",
            "SIGNED_NATIVE_OBSERVER_NOT_VERIFIED",
            "SINGLE_INTERVAL_STORE_HOST_BINDING_NOT_VERIFIED",
            "EXTERNAL_OWNER_PROVISIONING_NOT_VERIFIED",
        }
    )
    material: dict[str, Any] = {
        "schema_version": RECEIPT_SCHEMA,
        "gate_status": GATE_STATUS,
        "decision": "NO_GO",
        "failure_stage": failure_stage,
        "blocker_codes": _ordered_blockers(blockers, structural, downstream),
        "candidate_only": True,
        "zero_input_public_api_verified": True,
        "caller_supplied_selector_absent": True,
        **{field: bool(observations.get(field, False)) for field in _OBSERVATION_FIELDS},
        "service_configuration_projection": dict(service_projection or {}),
        "service_image_identity_projection": dict(image_projection or {}),
        **{field: False for field in _ALWAYS_FALSE_FIELDS},
        "credited_actual_source_claim_count": 0,
        "credited_actual_a_context_review_count": 0,
        "operational_effect": "NONE_SHADOW_ONLY",
    }
    return {**material, "receipt_sha256": deployment.canonical_sha256(material)}


def _observe_preflight_candidate() -> dict[str, Any]:
    observations = {field: False for field in _OBSERVATION_FIELDS}
    try:
        fixed_receipt, body = (
            fixed_store._observe_fixed_windows_owner_policy_store_candidate_with_body()
        )
    except fixed_store.P0WindowsFixedOwnerPolicyStoreCandidateError:
        return _receipt(
            failure_stage="FIXED_STORE",
            observations=observations,
            blockers=("FIXED_OWNER_POLICY_STORE_NOT_VERIFIED",),
        )
    observations["fixed_policy_store_candidate_observed"] = True
    try:
        projection = _validated_projection_from_fixed_outcome(
            fixed_receipt, body
        )
    except _StageNoGo as exc:
        if exc.stage == "FIXED_STORE":
            observations["fixed_policy_store_candidate_observed"] = False
        elif exc.stage == "OWNER_POLICY_V2":
            observations["v1_future_authority_hard_rejected"] = (
                exc.v1_hard_rejected
            )
        return _receipt(
            failure_stage=exc.stage,
            observations=observations,
            blockers=exc.blockers,
        )
    observations.update(
        {
            "owner_policy_v2_contract_verified": True,
            "v1_future_authority_hard_rejected": True,
            "bootstrap_signature_mathematics_verified": True,
            "deployment_projection_cross_binding_verified": True,
        }
    )
    service_projection: dict[str, Any] | None = None
    try:
        service = _observe_fixed_service_configuration_candidate()
        if service is None:
            raise _StageNoGo(
                "SERVICE_CONFIGURATION",
                ("SERVICE_CONFIGURATION_NOT_VERIFIED",),
            )
        service_projection = _validate_service_configuration_candidate(
            projection, service
        )
        observations["service_configuration_candidate_verified"] = True
        image_projection = _observe_service_image_identity_candidate(projection)
        observations["service_image_identity_candidate_verified"] = True
    except _StageNoGo as exc:
        return _receipt(
            failure_stage=exc.stage,
            observations=observations,
            blockers=exc.blockers,
            service_projection=service_projection,
        )
    except Exception:
        stage = (
            "SERVICE_IMAGE"
            if observations["service_configuration_candidate_verified"]
            else "SERVICE_CONFIGURATION"
        )
        blocker = (
            "SERVICE_IMAGE_IDENTITY_NOT_VERIFIED"
            if stage == "SERVICE_IMAGE"
            else "SERVICE_CONFIGURATION_NOT_VERIFIED"
        )
        return _receipt(
            failure_stage=stage,
            observations=observations,
            blockers=(blocker,),
            service_projection=service_projection,
        )
    return _receipt(
        failure_stage="NATIVE_EXTERNAL_EVIDENCE",
        observations=observations,
        blockers=(),
        service_projection=service_projection,
        image_projection=image_projection,
    )


def observe_fixed_windows_owner_provisioning_preflight_candidate(
) -> dict[str, Any]:
    """Read the compiled store/service/image without caller inputs or mutation."""

    if not _IS_WINDOWS:
        raise P0WindowsOwnerProvisioningPreflightCandidateError(
            "Windows owner provisioning preflight is Windows-only"
        )
    try:
        return _observe_preflight_candidate()
    except P0WindowsOwnerProvisioningPreflightCandidateError:
        raise
    except Exception as exc:
        raise P0WindowsOwnerProvisioningPreflightCandidateError(
            "Windows owner provisioning preflight failed closed"
        ) from exc


__all__ = [
    "GATE_STATUS",
    "P0WindowsOwnerProvisioningPreflightCandidateError",
    "RECEIPT_SCHEMA",
    "observe_fixed_windows_owner_provisioning_preflight_candidate",
]
