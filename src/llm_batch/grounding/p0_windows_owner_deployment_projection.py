"""Strict owner-signed Windows verifier deployment projection v2.

The projection is policy material, not live host evidence.  It binds the
native verifier service, WDAC UMCI policy, bootstrap resource, Authenticode
chain pins, and the exact loaded CNG provider modules that a later zero-input
host preflight must observe.  Structural validation never grants authority.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import uuid
from typing import Any, Mapping


DEPLOYMENT_PROJECTION_SCHEMA = "p0_windows_owner_deployment_projection_v2"
RECEIPT_SCHEMA = "p0_windows_owner_deployment_projection_receipt_v1"
GATE_STATUS = (
    "OWNER_DEPLOYMENT_PROJECTION_V2_CONTRACT_PASS_HOST_AND_EXTERNAL_"
    "PROVISIONING_NO_GO"
)
VERIFIER_KIND = "NATIVE_FIXED_PE_SERVICE"
SERVICE_NAME = "llm-novel-dc-p0-owner-verifier-v2"
SERVICE_SID = (
    "S-1-5-80-1513470239-1791686718-1237107998-66343029-3355175470"
)
SERVICE_START_ACCOUNT_SID = "S-1-5-18"
SERVICE_TYPE = "SERVICE_WIN32_OWN_PROCESS"
SERVICE_START_TYPE = "SERVICE_DEMAND_START"
SERVICE_ERROR_CONTROL = "SERVICE_ERROR_NORMAL"
SERVICE_SID_TYPE = "SERVICE_SID_TYPE_RESTRICTED"
SERVICE_BINARY_PATH_ARGV_POLICY = "EXACT_QUOTED_IMAGE_PATH_NO_ARGUMENTS"
BOOTSTRAP_RESOURCE_TYPE = "P0_OWNER_BOOTSTRAP_V2"
BOOTSTRAP_RESOURCE_NAME = "OWNER_POLICY_P256_SPKI"
BOOTSTRAP_RESOURCE_LANGUAGE_ID = 0
VERIFIER_SIGNATURE_TYPE = "EMBEDDED_AUTHENTICODE_WINVERIFYTRUST_V1"
PROVIDER_SIGNATURE_TYPE = "MICROSOFT_CATALOG_WINVERIFYTRUST_V1"
PROVIDER_MODULES = (
    ("BCRYPT", "bcrypt.dll"),
    ("BCRYPT_PRIMITIVES", "bcryptprimitives.dll"),
)

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_FILE_ID = re.compile(r"^[0-9a-f]{32}$")
_SAFE_COMPONENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._ -]{0,127}$")
_RESERVED = frozenset(
    {"con", "prn", "aux", "nul", "clock$"}
    | {f"com{index}" for index in range(1, 10)}
    | {f"lpt{index}" for index in range(1, 10)}
)
_VERIFIER_SUFFIX = (
    "\\Program Files\\llm-novel-dc\\owner-verifier-v2\\"
    "llm-novel-dc-owner-verifier.exe"
)

_PROJECTION_FIELDS = frozenset(
    {
        "projection_schema",
        "verifier_kind",
        "service_name",
        "service_sid",
        "service_start_account_sid",
        "service_type",
        "service_start_type",
        "service_error_control",
        "service_sid_type",
        "service_binary_path_argv_policy",
        "image_final_volume_guid_path",
        "image_volume_serial_decimal",
        "image_file_id_128_hex",
        "image_sha256",
        "bootstrap_resource_sha256",
        "bootstrap_resource_type",
        "bootstrap_resource_name",
        "bootstrap_resource_language_id",
        "bootstrap_resource_exact_count",
        "authenticode_signature_type",
        "signer_leaf_spki_sha256",
        "signer_root_spki_sha256",
        "wdac_policy_id",
        "wdac_base_policy_id",
        "wdac_policy_sha256",
        "user_mode_code_integrity_required",
        "provider_modules",
        "artifact_sha256",
    }
)
_PROVIDER_FIELDS = frozenset(
    {
        "role",
        "module_name",
        "loaded_final_volume_guid_path",
        "volume_serial_decimal",
        "file_id_128_hex",
        "image_sha256",
        "authenticode_signature_type",
        "signer_leaf_spki_sha256",
        "signer_root_spki_sha256",
    }
)


class P0WindowsOwnerDeploymentProjectionError(ValueError):
    """The owner deployment projection failed its strict component contract."""


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def with_artifact_hash(value: Mapping[str, Any]) -> dict[str, Any]:
    material = dict(value)
    material.pop("artifact_sha256", None)
    return {**material, "artifact_sha256": canonical_sha256(material)}


def _exact(value: Any, fields: frozenset[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != fields:
        raise P0WindowsOwnerDeploymentProjectionError(
            f"{label} must use the exact deployment projection fields"
        )
    return value


def _sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise P0WindowsOwnerDeploymentProjectionError(
            f"{label} must be lowercase sha256"
        )
    return value


def _decimal(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value.isascii()
        or not value.isdecimal()
        or (len(value) > 1 and value.startswith("0"))
        or not 0 < int(value) <= 2**64 - 1
    ):
        raise P0WindowsOwnerDeploymentProjectionError(
            f"{label} must be canonical positive uint64 decimal"
        )
    return value


def _file_id(value: Any, label: str) -> str:
    if not isinstance(value, str) or _FILE_ID.fullmatch(value) is None:
        raise P0WindowsOwnerDeploymentProjectionError(
            f"{label} must be a lowercase 128-bit file ID"
        )
    return value


def _uuid(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise P0WindowsOwnerDeploymentProjectionError(
            f"{label} must be a lowercase UUID"
        )
    try:
        parsed = uuid.UUID(value)
    except ValueError as exc:
        raise P0WindowsOwnerDeploymentProjectionError(
            f"{label} must be a lowercase UUID"
        ) from exc
    if parsed.int == 0 or str(parsed) != value:
        raise P0WindowsOwnerDeploymentProjectionError(
            f"{label} must be a non-nil lowercase UUID"
        )
    return value


def _volume_guid_path(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.startswith("\\\\?\\Volume{"):
        raise P0WindowsOwnerDeploymentProjectionError(
            f"{label} must use a volume-GUID path"
        )
    close = value.find("}\\", len("\\\\?\\Volume{"))
    if close < 0 or value.endswith("\\") or "/" in value or "\0" in value:
        raise P0WindowsOwnerDeploymentProjectionError(f"{label} is not canonical")
    guid_text = value[len("\\\\?\\Volume{") : close]
    try:
        parsed = uuid.UUID(guid_text)
    except ValueError as exc:
        raise P0WindowsOwnerDeploymentProjectionError(
            f"{label} has an invalid volume GUID"
        ) from exc
    if parsed.int == 0 or str(parsed) != guid_text:
        raise P0WindowsOwnerDeploymentProjectionError(
            f"{label} volume GUID must be non-nil lowercase canonical text"
        )
    components = value[close + 2 :].split("\\")
    if not components or any(
        not component
        or component in {".", ".."}
        or _SAFE_COMPONENT.fullmatch(component) is None
        or component.endswith((".", " "))
        or component.split(".", 1)[0].lower() in _RESERVED
        for component in components
    ):
        raise P0WindowsOwnerDeploymentProjectionError(
            f"{label} contains an unsafe path component"
        )
    return value


def _validate_projection(value: Any) -> dict[str, Any]:
    row = _exact(value, _PROJECTION_FIELDS, "deployment projection")
    if row["projection_schema"] != DEPLOYMENT_PROJECTION_SCHEMA:
        raise P0WindowsOwnerDeploymentProjectionError(
            "deployment projection schema mismatch"
        )
    if row["verifier_kind"] != VERIFIER_KIND:
        raise P0WindowsOwnerDeploymentProjectionError(
            "deployment verifier must be a fixed native PE service"
        )
    if row["service_name"] != SERVICE_NAME:
        raise P0WindowsOwnerDeploymentProjectionError("service name mismatch")
    if row["service_sid"] != SERVICE_SID:
        raise P0WindowsOwnerDeploymentProjectionError(
            "service_sid must be the deterministic SID for the fixed service name"
        )
    if row["service_start_account_sid"] != SERVICE_START_ACCOUNT_SID:
        raise P0WindowsOwnerDeploymentProjectionError(
            "owner verifier service must start as LocalSystem"
        )
    service_expectations = {
        "service_type": SERVICE_TYPE,
        "service_start_type": SERVICE_START_TYPE,
        "service_error_control": SERVICE_ERROR_CONTROL,
        "service_sid_type": SERVICE_SID_TYPE,
        "service_binary_path_argv_policy": SERVICE_BINARY_PATH_ARGV_POLICY,
    }
    for field, expected in service_expectations.items():
        if row[field] != expected:
            raise P0WindowsOwnerDeploymentProjectionError(
                f"{field} must use the fixed service configuration policy"
            )
    image_path = _volume_guid_path(
        row["image_final_volume_guid_path"], "image_final_volume_guid_path"
    )
    if not image_path.endswith(_VERIFIER_SUFFIX):
        raise P0WindowsOwnerDeploymentProjectionError(
            "native verifier image must use the fixed Program Files path"
        )
    _decimal(row["image_volume_serial_decimal"], "image volume serial")
    _file_id(row["image_file_id_128_hex"], "image file ID")
    for field in (
        "image_sha256",
        "bootstrap_resource_sha256",
        "signer_leaf_spki_sha256",
        "signer_root_spki_sha256",
        "wdac_policy_sha256",
    ):
        _sha(row[field], field)
    if row["bootstrap_resource_type"] != BOOTSTRAP_RESOURCE_TYPE:
        raise P0WindowsOwnerDeploymentProjectionError(
            "bootstrap resource type mismatch"
        )
    if row["bootstrap_resource_name"] != BOOTSTRAP_RESOURCE_NAME:
        raise P0WindowsOwnerDeploymentProjectionError(
            "bootstrap resource name mismatch"
        )
    if (
        type(row["bootstrap_resource_language_id"]) is not int
        or row["bootstrap_resource_language_id"]
        != BOOTSTRAP_RESOURCE_LANGUAGE_ID
    ):
        raise P0WindowsOwnerDeploymentProjectionError(
            "bootstrap resource language mismatch"
        )
    if (
        type(row["bootstrap_resource_exact_count"]) is not int
        or row["bootstrap_resource_exact_count"] != 1
    ):
        raise P0WindowsOwnerDeploymentProjectionError(
            "bootstrap resource must occur exactly once"
        )
    if row["signer_leaf_spki_sha256"] == row["signer_root_spki_sha256"]:
        raise P0WindowsOwnerDeploymentProjectionError(
            "verifier leaf and root SPKI pins must be distinct"
        )
    if row["authenticode_signature_type"] != VERIFIER_SIGNATURE_TYPE:
        raise P0WindowsOwnerDeploymentProjectionError(
            "native verifier requires the fixed embedded Authenticode policy"
        )
    policy_id = _uuid(row["wdac_policy_id"], "wdac_policy_id")
    base_id = _uuid(row["wdac_base_policy_id"], "wdac_base_policy_id")
    if policy_id == base_id:
        raise P0WindowsOwnerDeploymentProjectionError(
            "WDAC policy and base-policy IDs must be distinct"
        )
    if row["user_mode_code_integrity_required"] is not True:
        raise P0WindowsOwnerDeploymentProjectionError(
            "WDAC user-mode code integrity must be required"
        )

    providers = row["provider_modules"]
    if not isinstance(providers, list) or len(providers) != len(PROVIDER_MODULES):
        raise P0WindowsOwnerDeploymentProjectionError(
            "provider_modules must contain exact bcrypt module rows"
        )
    parsed_providers: list[dict[str, Any]] = []
    identities: set[tuple[str, str]] = set()
    for index, (expected_role, expected_name) in enumerate(PROVIDER_MODULES):
        provider = _exact(providers[index], _PROVIDER_FIELDS, f"provider {index}")
        if (
            provider["role"] != expected_role
            or provider["module_name"] != expected_name
        ):
            raise P0WindowsOwnerDeploymentProjectionError(
                "provider module order/name mismatch"
            )
        provider_path = _volume_guid_path(
            provider["loaded_final_volume_guid_path"],
            f"provider {expected_role} loaded path",
        )
        if not provider_path.endswith(f"\\Windows\\System32\\{expected_name}"):
            raise P0WindowsOwnerDeploymentProjectionError(
                "provider must be the loaded System32 module"
            )
        volume = _decimal(provider["volume_serial_decimal"], "provider volume")
        file_id = _file_id(provider["file_id_128_hex"], "provider file ID")
        identity = (volume, file_id)
        if identity in identities:
            raise P0WindowsOwnerDeploymentProjectionError(
                "provider module identities must be distinct"
            )
        identities.add(identity)
        for field in (
            "image_sha256",
            "signer_leaf_spki_sha256",
            "signer_root_spki_sha256",
        ):
            _sha(provider[field], f"provider {expected_role}.{field}")
        if provider["signer_leaf_spki_sha256"] == provider["signer_root_spki_sha256"]:
            raise P0WindowsOwnerDeploymentProjectionError(
                "provider leaf and root SPKI pins must be distinct"
            )
        if provider["authenticode_signature_type"] != PROVIDER_SIGNATURE_TYPE:
            raise P0WindowsOwnerDeploymentProjectionError(
                "CNG providers require the fixed catalog signature policy"
            )
        parsed_providers.append(dict(provider))

    expected_hash = _sha(row["artifact_sha256"], "artifact_sha256")
    actual_hash = canonical_sha256(
        {key: item for key, item in row.items() if key != "artifact_sha256"}
    )
    if not hmac.compare_digest(expected_hash, actual_hash):
        raise P0WindowsOwnerDeploymentProjectionError(
            "deployment projection artifact hash mismatch"
        )
    return {**dict(row), "provider_modules": parsed_providers}


def validate_windows_owner_deployment_projection_contract(
    *, projection: Mapping[str, Any]
) -> dict[str, Any]:
    """Validate presented v2 deployment material without observing the host."""

    parsed = _validate_projection(projection)
    material = {
        "schema_version": RECEIPT_SCHEMA,
        "gate_status": GATE_STATUS,
        "deployment_projection_sha256": parsed["artifact_sha256"],
        "deployment_projection_contract_verified": True,
        "native_fixed_pe_service_required": True,
        "service_name_sid_binding_contract_verified": True,
        "exact_service_configuration_contract_verified": True,
        "embedded_bootstrap_resource_binding_required": True,
        "embedded_bootstrap_resource_selector_contract_verified": True,
        "authenticode_chain_pin_contract_verified": True,
        "wdac_user_mode_code_integrity_required": True,
        "loaded_cng_provider_identity_contract_verified": True,
        "live_host_observation_verified": False,
        "bootstrap_public_key_independently_pinned": False,
        "trusted_verifier_code_identity_verified": False,
        "trusted_cng_provider_provenance_verified": False,
        "external_owner_policy_provisioning_verified": False,
        "owner_authority_verified": False,
        "actual_authority_granted": False,
        "production_approval": False,
        "full_scan_approval": False,
        "p0_phase_exit": False,
        "action_applied": False,
        "operational_effect": "NONE_SHADOW_ONLY",
    }
    return {**material, "receipt_sha256": canonical_sha256(material)}


__all__ = [
    "BOOTSTRAP_RESOURCE_LANGUAGE_ID",
    "BOOTSTRAP_RESOURCE_NAME",
    "BOOTSTRAP_RESOURCE_TYPE",
    "DEPLOYMENT_PROJECTION_SCHEMA",
    "GATE_STATUS",
    "P0WindowsOwnerDeploymentProjectionError",
    "PROVIDER_MODULES",
    "PROVIDER_SIGNATURE_TYPE",
    "RECEIPT_SCHEMA",
    "SERVICE_NAME",
    "SERVICE_BINARY_PATH_ARGV_POLICY",
    "SERVICE_ERROR_CONTROL",
    "SERVICE_SID",
    "SERVICE_SID_TYPE",
    "SERVICE_START_ACCOUNT_SID",
    "SERVICE_START_TYPE",
    "SERVICE_TYPE",
    "VERIFIER_KIND",
    "VERIFIER_SIGNATURE_TYPE",
    "canonical_sha256",
    "validate_windows_owner_deployment_projection_contract",
    "with_artifact_hash",
]
