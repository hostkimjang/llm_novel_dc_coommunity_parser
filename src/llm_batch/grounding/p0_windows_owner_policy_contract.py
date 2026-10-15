"""Strict component contract for a Windows external-owner policy.

This module validates the bytes and exact security-template semantics of a
presented owner-policy body and its detached signature envelope.  It does not
select the policy store, pin a bootstrap public key, verify signature
mathematics, inspect a live Windows security descriptor, or provide durable
rollback state.  Consequently a successful receipt is component evidence only
and every authority, provisioning, P0-exit, and production field stays false.

The deliberately narrow ACL profile permits exactly two explicit
standard ACCESS_ALLOWED ACEs per object: the external owner receives concrete
FILE_ALL_ACCESS and the verifier receives a concrete read-only mask.  Generic,
inherited, callback, conditional, object, resource, scoped, and unknown ACEs
cannot be represented by this contract.  The v1 policy meaning is preserved;
v2 adds an owner-signed native-verifier deployment projection and uses separate
body, signature, and owner-anchor domains so a v1 envelope cannot be upgraded.
The v3 branch preserves the v1/v2 exact contracts while adding an independently
keyed native-observer profile.  Structural validation never proves signature
mathematics, TPM provenance, active WDAC/UMCI state, or external provisioning.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import uuid
from typing import Any, Mapping, Sequence

from . import p0_windows_native_observer_profile_contract as observer_profile
from . import p0_windows_owner_deployment_projection as deployment


POLICY_BODY_SCHEMA = "p0_windows_external_owner_policy_body_v1"
POLICY_SIGNATURE_SCHEMA = "p0_windows_external_owner_policy_signature_v1"
POLICY_BODY_SCHEMA_V2 = "p0_windows_external_owner_policy_body_v2"
POLICY_SIGNATURE_SCHEMA_V2 = "p0_windows_external_owner_policy_signature_v2"
POLICY_BODY_SCHEMA_V3 = "p0_windows_external_owner_policy_body_v3"
POLICY_SIGNATURE_SCHEMA_V3 = "p0_windows_external_owner_policy_signature_v3"
CONTRACT_RECEIPT_SCHEMA = "p0_windows_owner_policy_contract_receipt_v1"
CONTRACT_RECEIPT_SCHEMA_V2 = "p0_windows_owner_policy_contract_receipt_v2"
CONTRACT_RECEIPT_SCHEMA_V3 = "p0_windows_owner_policy_contract_receipt_v3"
POLICY_DOMAIN = "llm_novel_dc/p0/windows-external-owner-policy/v1"
SIGNATURE_DOMAIN = "llm_novel_dc/p0/windows-owner-policy-signature/v1"
POLICY_DOMAIN_V2 = "llm_novel_dc/p0/windows-external-owner-policy/v2"
SIGNATURE_DOMAIN_V2 = "llm_novel_dc/p0/windows-owner-policy-signature/v2"
POLICY_DOMAIN_V3 = "llm_novel_dc/p0/windows-external-owner-policy/v3"
SIGNATURE_DOMAIN_V3 = "llm_novel_dc/p0/windows-owner-policy-signature/v3"
OWNER_PRINCIPAL_DOMAIN = "llm_novel_dc/p0/owner-principal/v1"
OWNER_ANCHOR_DOMAIN = "llm_novel_dc/p0/owner-anchor/v1"
OWNER_ANCHOR_DOMAIN_V2 = "llm_novel_dc/p0/owner-anchor/v2"
OWNER_ANCHOR_DOMAIN_V3 = "llm_novel_dc/p0/owner-anchor/v3"
ACL_TEMPLATE_DOMAIN = "llm_novel_dc/p0/windows-acl-template/v1"
OPERATIONAL_KEY_DOMAIN = "llm_novel_dc/p0/operational-owner-key/v1"
POLICY_ORIGIN = "EXTERNAL_OWNER_POLICY_RECORD"
SIGNATURE_ORIGIN = "EXTERNAL_OWNER_POLICY_DETACHED_SIGNATURE_RECORD"
BOOTSTRAP_SIGNATURE_ALGORITHM = "ECDSA_P256_SHA256_IEEE_P1363_LOW_S"
OPERATIONAL_KEY_ALGORITHM = "ECDSA_P256_SHA256_CNG_V1"
OPERATIONAL_SIGNATURE_DOMAIN = (
    "llm-novel-dc-community-parser/"
    "p0-external-owner-preauthorization-signature/v1"
)
GATE_STATUS = "OWNER_POLICY_CONTRACT_PASS_BOOTSTRAP_AND_PROVISIONING_NO_GO"

ACCESS_ALLOWED_ACE_TYPE = 0
ACE_FLAGS_NONE = 0
FILE_ALL_ACCESS = 0x001F01FF
FILE_READER_MASK = 0x00120089
DIRECTORY_READER_MASK = 0x001200A9
GENERIC_RIGHTS_MASK = 0xF0000000
MAXIMUM_ALLOWED = 0x02000000

OBJECT_ROLES = (
    "policy_store",
    "generations_directory",
    "generation_directory",
    "policy_directory",
    "pin_directory",
    "policy_body_file",
    "policy_signature_file",
    "public_key_pin_file",
)
FIXED_POLICY_STORE_SUFFIX = ("llm-novel-dc", "p0-owner-policy-v1")
_DIRECTORY_ROLES = frozenset(OBJECT_ROLES[:5])
_FILE_ROLES = frozenset(OBJECT_ROLES[5:])

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_FILE_ID = re.compile(r"^[0-9a-f]{32}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,255}$")
_SID = re.compile(r"^S-(?:0|[1-9][0-9]*)-(?:0|[1-9][0-9]*)(?:-(?:0|[1-9][0-9]*)){1,15}$")
_SAFE_PATH_COMPONENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_RESERVED_DOS_BASENAMES = frozenset(
    {"con", "prn", "aux", "nul", "clock$"}
    | {f"com{index}" for index in range(1, 10)}
    | {f"lpt{index}" for index in range(1, 10)}
)

_BROAD_OR_PRIVILEGED_GROUP_SIDS = frozenset(
    {
        "S-1-1-0",  # Everyone
        "S-1-5-11",  # Authenticated Users
        "S-1-5-32-544",  # Builtin Administrators
        "S-1-5-32-545",  # Builtin Users
    }
)
_FORBIDDEN_VERIFIER_SIDS = _BROAD_OR_PRIVILEGED_GROUP_SIDS | {
    "S-1-5-18",  # LocalSystem
}

# Order of the NIST P-256 curve.  Detached signatures must be structurally
# canonical (including low-S) even though this component does not verify the
# signature against a bootstrap key.
_P256_ORDER = int(
    "FFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551",
    16,
)

_BODY_KEYS = frozenset(
    {
        "schema_version",
        "record_origin",
        "domain",
        "policy_id",
        "policy_epoch",
        "predecessor_policy_bytes_sha256",
        "store_id",
        "project_id",
        "trust_domain",
        "environment",
        "purpose",
        "bootstrap_key_id",
        "bootstrap_public_key_fingerprint_sha256",
        "owner_sid",
        "verifier_sid",
        "object_policies",
        "operational_key",
        "min_revocation_sequence",
        "lifecycle_status",
        "owner_principal_sha256",
        "acl_template_sha256",
        "operational_key_projection_sha256",
        "owner_anchor_sha256",
        "artifact_sha256",
    }
)
_BODY_KEYS_V2 = _BODY_KEYS | {"deployment_projection"}
_BODY_KEYS_V3 = _BODY_KEYS | {
    "deployment_projection",
    "native_observer_profile",
}
_SIGNATURE_KEYS = frozenset(
    {
        "schema_version",
        "record_origin",
        "domain",
        "policy_id",
        "policy_epoch",
        "bootstrap_key_id",
        "bootstrap_public_key_fingerprint_sha256",
        "policy_body_bytes_sha256",
        "algorithm",
        "signature_rs_base64",
        "artifact_sha256",
    }
)
_OBJECT_KEYS = frozenset(
    {
        "role",
        "object_kind",
        "final_volume_guid_path",
        "volume_serial_decimal",
        "file_id_128_hex",
        "security_template",
    }
)
_SECURITY_KEYS = frozenset(
    {
        "owner_sid",
        "group_sid",
        "dacl_present",
        "dacl_null",
        "dacl_protected",
        "dacl_defaulted",
        "dacl_auto_inherited",
        "dacl_auto_inherit_req",
        "ordered_aces",
    }
)
_ACE_KEYS = frozenset(
    {"ace_type", "ace_flags", "access_mask_decimal", "sid"}
)
_OPERATIONAL_KEY_KEYS = frozenset(
    {
        "key_id",
        "key_epoch",
        "algorithm",
        "public_key_fingerprint_sha256",
        "pin_bytes_sha256",
        "pin_artifact_sha256",
        "allowed_signature_domains",
    }
)
_OPERATIONAL_KEY_ANCHOR_FIELDS = (
    "key_id",
    "key_epoch",
    "algorithm",
    "public_key_fingerprint_sha256",
    "allowed_signature_domains",
)

_ALWAYS_FALSE_FIELDS = (
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
)


class P0WindowsOwnerPolicyContractError(ValueError):
    """The presented owner-policy contract could not fail closed."""


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    return value


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        _plain(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def json_file_bytes(value: Mapping[str, Any]) -> bytes:
    return canonical_bytes(value) + b"\n"


def _duplicate_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise P0WindowsOwnerPolicyContractError(
                f"duplicate JSON key: {key}"
            )
        result[key] = value
    return result


def _reject_nonfinite(token: str) -> None:
    raise P0WindowsOwnerPolicyContractError(
        f"non-finite JSON constant is forbidden: {token}"
    )


def _parse_canonical_object(raw: Any, label: str) -> dict[str, Any]:
    if (
        type(raw) is not bytes
        or not raw
        or len(raw) > 1024 * 1024
        or raw.startswith(b"\xef\xbb\xbf")
    ):
        raise P0WindowsOwnerPolicyContractError(
            f"{label} must be bounded exact UTF-8 bytes without BOM"
        )
    try:
        value = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=_duplicate_object,
            parse_constant=_reject_nonfinite,
        )
        canonical = json_file_bytes(value) if isinstance(value, dict) else None
    except (
        UnicodeDecodeError,
        UnicodeEncodeError,
        ValueError,
        RecursionError,
        TypeError,
    ) as exc:
        raise P0WindowsOwnerPolicyContractError(
            f"{label} is not strict JSON"
        ) from exc
    if not isinstance(value, dict) or canonical != raw:
        raise P0WindowsOwnerPolicyContractError(
            f"{label} must be one canonical JSON object plus LF"
        )
    return value


def _exact_keys(value: Mapping[str, Any], expected: frozenset[str], label: str) -> None:
    actual = frozenset(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise P0WindowsOwnerPolicyContractError(
            f"{label} keys mismatch: missing={missing}, extra={extra}"
        )


def _identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        raise P0WindowsOwnerPolicyContractError(f"{label} is invalid")
    return value


def _sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise P0WindowsOwnerPolicyContractError(
            f"{label} must be lowercase sha256"
        )
    return value


def _positive_int(value: Any, label: str) -> int:
    if type(value) is not int or value <= 0 or value > 2**63 - 1:
        raise P0WindowsOwnerPolicyContractError(
            f"{label} must be a positive bounded integer"
        )
    return value


def _decimal(value: Any, label: str, *, maximum: int = 2**64 - 1) -> str:
    if (
        not isinstance(value, str)
        or not value.isascii()
        or not value.isdecimal()
        or (len(value) > 1 and value.startswith("0"))
    ):
        raise P0WindowsOwnerPolicyContractError(
            f"{label} must be canonical unsigned decimal"
        )
    parsed = int(value)
    if parsed <= 0 or parsed > maximum:
        raise P0WindowsOwnerPolicyContractError(f"{label} is out of range")
    return value


def _sid(value: Any, label: str) -> str:
    if not isinstance(value, str) or _SID.fullmatch(value) is None:
        raise P0WindowsOwnerPolicyContractError(
            f"{label} must be a canonical numeric SID"
        )
    parts = [int(item) for item in value[2:].split("-")]
    if parts[0] != 1 or parts[1] > 2**48 - 1 or any(
        item > 2**32 - 1 for item in parts[2:]
    ):
        raise P0WindowsOwnerPolicyContractError(f"{label} is out of range")
    return value


def _forbidden_builtin_alias(value: str) -> bool:
    return value.startswith("S-1-5-32-")


def _permitted_owner_sid_profile(value: str) -> bool:
    return (
        value == "S-1-5-18"
        or _account_sid_profile(value)
        or _service_sid_profile(value)
    )


def _permitted_verifier_sid_profile(value: str) -> bool:
    return _account_sid_profile(value) or _service_sid_profile(value)


def _account_sid_profile(value: str) -> bool:
    parts = value.split("-")
    return (
        len(parts) == 8
        and parts[:4] == ["S", "1", "5", "21"]
        and int(parts[-1]) >= 1000
    )


def _service_sid_profile(value: str) -> bool:
    parts = value.split("-")
    return len(parts) == 9 and parts[:4] == ["S", "1", "5", "80"]


def _volume_guid_path(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.startswith("\\\\?\\Volume{"):
        raise P0WindowsOwnerPolicyContractError(
            f"{label} must use the Windows volume-GUID namespace"
        )
    close = value.find("}\\", len("\\\\?\\Volume{"))
    if close < 0 or value.endswith("\\") or "/" in value or "\0" in value:
        raise P0WindowsOwnerPolicyContractError(f"{label} is not canonical")
    try:
        parsed_guid = uuid.UUID(value[len("\\\\?\\Volume{") : close])
    except ValueError as exc:
        raise P0WindowsOwnerPolicyContractError(
            f"{label} has an invalid volume GUID"
        ) from exc
    guid_text = value[len("\\\\?\\Volume{") : close]
    if guid_text != guid_text.lower() or str(parsed_guid) != guid_text:
        raise P0WindowsOwnerPolicyContractError(
            f"{label} volume GUID must be lowercase canonical text"
        )
    components = value[close + 2 :].split("\\")
    if not components or any(
        not component
        or component in {".", ".."}
        or _SAFE_PATH_COMPONENT.fullmatch(component) is None
        or component.endswith((".", " "))
        or component.split(".", 1)[0].lower() in _RESERVED_DOS_BASENAMES
        for component in components
    ):
        raise P0WindowsOwnerPolicyContractError(
            f"{label} has an invalid path component"
        )
    return value


def _artifact_hash(value: Mapping[str, Any], label: str) -> str:
    expected = _sha(value.get("artifact_sha256"), f"{label}.artifact_sha256")
    material = {key: item for key, item in value.items() if key != "artifact_sha256"}
    actual = canonical_sha256(material)
    if not hmac.compare_digest(expected, actual):
        raise P0WindowsOwnerPolicyContractError(
            f"{label}.artifact_sha256 mismatch"
        )
    return expected


def derive_owner_principal_sha256(owner_sid: str) -> str:
    return canonical_sha256(
        {"domain": OWNER_PRINCIPAL_DOMAIN, "owner_sid": owner_sid}
    )


def derive_operational_key_projection_sha256(
    operational_key: Mapping[str, Any],
) -> str:
    """Hash the stable key identity without creating a pin/anchor cycle.

    The signed policy body separately binds the exact pin byte and artifact
    hashes.  Excluding those two transport hashes here permits the pin to bind
    the resulting owner anchor and then be hashed into that signed body.
    """

    projection = {
        field: operational_key[field]
        for field in _OPERATIONAL_KEY_ANCHOR_FIELDS
    }
    return canonical_sha256(
        {"domain": OPERATIONAL_KEY_DOMAIN, "operational_key": projection}
    )


def _reader_mask(role: str) -> int:
    return DIRECTORY_READER_MASK if role in _DIRECTORY_ROLES else FILE_READER_MASK


def _validate_security_template(
    value: Any,
    *,
    role: str,
    owner_sid: str,
    verifier_sid: str,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise P0WindowsOwnerPolicyContractError(
            f"{role}.security_template must be an object"
        )
    _exact_keys(value, _SECURITY_KEYS, f"{role}.security_template")
    observed_owner = _sid(value.get("owner_sid"), f"{role}.owner_sid")
    group_sid = _sid(value.get("group_sid"), f"{role}.group_sid")
    if observed_owner != owner_sid:
        raise P0WindowsOwnerPolicyContractError(f"{role} owner SID mismatch")
    expected_controls = {
        "dacl_present": True,
        "dacl_null": False,
        "dacl_protected": True,
        "dacl_defaulted": False,
        "dacl_auto_inherited": False,
        "dacl_auto_inherit_req": False,
    }
    for field, expected in expected_controls.items():
        if type(value.get(field)) is not bool or value[field] is not expected:
            raise P0WindowsOwnerPolicyContractError(
                f"{role}.{field} must be {expected}"
            )
    aces = value.get("ordered_aces")
    if not isinstance(aces, list) or len(aces) != 2:
        raise P0WindowsOwnerPolicyContractError(
            f"{role}.ordered_aces must contain exactly owner and verifier ACEs"
        )
    expected_aces = ((owner_sid, FILE_ALL_ACCESS), (verifier_sid, _reader_mask(role)))
    projected: list[dict[str, Any]] = []
    seen_sids: set[str] = set()
    for index, (raw_ace, (expected_sid, expected_mask)) in enumerate(
        zip(aces, expected_aces, strict=True)
    ):
        if not isinstance(raw_ace, Mapping):
            raise P0WindowsOwnerPolicyContractError(
                f"{role}.ordered_aces[{index}] must be an object"
            )
        _exact_keys(raw_ace, _ACE_KEYS, f"{role}.ordered_aces[{index}]")
        if (
            type(raw_ace.get("ace_type")) is not int
            or raw_ace.get("ace_type") != ACCESS_ALLOWED_ACE_TYPE
        ):
            raise P0WindowsOwnerPolicyContractError(
                f"{role}.ordered_aces[{index}] must be standard ACCESS_ALLOWED"
            )
        if (
            type(raw_ace.get("ace_flags")) is not int
            or raw_ace.get("ace_flags") != ACE_FLAGS_NONE
        ):
            raise P0WindowsOwnerPolicyContractError(
                f"{role}.ordered_aces[{index}] must be explicit and non-inheriting"
            )
        sid = _sid(raw_ace.get("sid"), f"{role}.ordered_aces[{index}].sid")
        if sid in seen_sids:
            raise P0WindowsOwnerPolicyContractError(
                f"{role}.ordered_aces contains duplicate SID"
            )
        seen_sids.add(sid)
        mask_text = _decimal(
            raw_ace.get("access_mask_decimal"),
            f"{role}.ordered_aces[{index}].access_mask_decimal",
            maximum=2**32 - 1,
        )
        mask = int(mask_text)
        if mask & (GENERIC_RIGHTS_MASK | MAXIMUM_ALLOWED):
            raise P0WindowsOwnerPolicyContractError(
                f"{role}.ordered_aces[{index}] contains generic/MAXIMUM_ALLOWED rights"
            )
        if sid != expected_sid or mask != expected_mask:
            raise P0WindowsOwnerPolicyContractError(
                f"{role}.ordered_aces[{index}] does not match the exact policy profile"
            )
        projected.append(dict(raw_ace))
    return {
        "owner_sid": observed_owner,
        "group_sid": group_sid,
        **expected_controls,
        "ordered_aces": projected,
    }


def _validate_object_policies(
    value: Any, *, owner_sid: str, verifier_sid: str, policy_epoch: int
) -> list[dict[str, Any]]:
    if not isinstance(value, list) or len(value) != len(OBJECT_ROLES):
        raise P0WindowsOwnerPolicyContractError(
            "object_policies must contain the exact ordered role set"
        )
    result: list[dict[str, Any]] = []
    identities: set[tuple[str, str]] = set()
    paths: dict[str, str] = {}
    for index, expected_role in enumerate(OBJECT_ROLES):
        row = value[index]
        if not isinstance(row, Mapping):
            raise P0WindowsOwnerPolicyContractError(
                f"object_policies[{index}] must be an object"
            )
        _exact_keys(row, _OBJECT_KEYS, f"object_policies[{index}]")
        if row.get("role") != expected_role:
            raise P0WindowsOwnerPolicyContractError(
                "object_policies must use the exact ordered role set"
            )
        expected_kind = "DIRECTORY" if expected_role in _DIRECTORY_ROLES else "FILE"
        if row.get("object_kind") != expected_kind:
            raise P0WindowsOwnerPolicyContractError(
                f"{expected_role}.object_kind must be {expected_kind}"
            )
        path = _volume_guid_path(
            row.get("final_volume_guid_path"),
            f"{expected_role}.final_volume_guid_path",
        )
        serial = _decimal(
            row.get("volume_serial_decimal"),
            f"{expected_role}.volume_serial_decimal",
        )
        file_id = row.get("file_id_128_hex")
        if not isinstance(file_id, str) or _FILE_ID.fullmatch(file_id) is None:
            raise P0WindowsOwnerPolicyContractError(
                f"{expected_role}.file_id_128_hex must be lowercase 128-bit hex"
            )
        identity = (serial, file_id)
        if identity in identities or path in set(paths.values()):
            raise P0WindowsOwnerPolicyContractError(
                "owner-policy object identities and paths must be distinct"
            )
        identities.add(identity)
        paths[expected_role] = path
        security = _validate_security_template(
            row.get("security_template"),
            role=expected_role,
            owner_sid=owner_sid,
            verifier_sid=verifier_sid,
        )
        result.append(
            {
                "role": expected_role,
                "object_kind": expected_kind,
                "final_volume_guid_path": path,
                "volume_serial_decimal": serial,
                "file_id_128_hex": file_id,
                "security_template": security,
            }
        )

    store = paths["policy_store"]
    store_components = store.split("\\")
    if tuple(store_components[-len(FIXED_POLICY_STORE_SUFFIX) :]) != (
        FIXED_POLICY_STORE_SUFFIX
    ):
        raise P0WindowsOwnerPolicyContractError(
            "policy_store must use the exact fixed lowercase suffix"
        )
    generations = f"{store}\\generations"
    generation = paths["generation_directory"]
    expected_generation = f"{generations}\\{policy_epoch:020d}"
    policy_directory = f"{expected_generation}\\policy"
    pin_directory = f"{expected_generation}\\pin"
    expected_paths = {
        "generations_directory": generations,
        "generation_directory": expected_generation,
        "policy_directory": policy_directory,
        "pin_directory": pin_directory,
        "policy_body_file": f"{policy_directory}\\body.json",
        "policy_signature_file": f"{policy_directory}\\signature.json",
        "public_key_pin_file": (
            f"{pin_directory}\\p0_external_owner_public_key_pin_v1.json"
        ),
    }
    for role, expected in expected_paths.items():
        if paths[role] != expected:
            raise P0WindowsOwnerPolicyContractError(
                f"{role} must use the fixed generation layout"
            )
    if len({row["volume_serial_decimal"] for row in result}) != 1:
        raise P0WindowsOwnerPolicyContractError(
            "all fixed-generation objects must share one volume serial"
        )
    return result


def _validate_operational_key(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise P0WindowsOwnerPolicyContractError(
            "operational_key must be an object"
        )
    _exact_keys(value, _OPERATIONAL_KEY_KEYS, "operational_key")
    result = {
        "key_id": _identifier(value.get("key_id"), "operational_key.key_id"),
        "key_epoch": _positive_int(
            value.get("key_epoch"), "operational_key.key_epoch"
        ),
        "algorithm": value.get("algorithm"),
        "public_key_fingerprint_sha256": _sha(
            value.get("public_key_fingerprint_sha256"),
            "operational_key.public_key_fingerprint_sha256",
        ),
        "pin_bytes_sha256": _sha(
            value.get("pin_bytes_sha256"), "operational_key.pin_bytes_sha256"
        ),
        "pin_artifact_sha256": _sha(
            value.get("pin_artifact_sha256"),
            "operational_key.pin_artifact_sha256",
        ),
    }
    if result["algorithm"] != OPERATIONAL_KEY_ALGORITHM:
        raise P0WindowsOwnerPolicyContractError(
            "operational_key.algorithm mismatch"
        )
    domains = value.get("allowed_signature_domains")
    if (
        not isinstance(domains, list)
        or domains != [OPERATIONAL_SIGNATURE_DOMAIN]
    ):
        raise P0WindowsOwnerPolicyContractError(
            "operational_key.allowed_signature_domains mismatch"
        )
    result["allowed_signature_domains"] = list(domains)
    return result


def _validate_policy_body(raw: bytes) -> dict[str, Any]:
    body = _parse_canonical_object(raw, "policy_body")
    schema_version = body.get("schema_version")
    native_observer_profile = None
    if schema_version == POLICY_BODY_SCHEMA:
        _exact_keys(body, _BODY_KEYS, "policy_body")
        expected_domain = POLICY_DOMAIN
        anchor_domain = OWNER_ANCHOR_DOMAIN
        deployment_projection = None
    elif schema_version == POLICY_BODY_SCHEMA_V2:
        _exact_keys(body, _BODY_KEYS_V2, "policy_body")
        expected_domain = POLICY_DOMAIN_V2
        anchor_domain = OWNER_ANCHOR_DOMAIN_V2
        try:
            deployment_projection = deployment._validate_projection(
                body.get("deployment_projection")
            )
        except deployment.P0WindowsOwnerDeploymentProjectionError as exc:
            raise P0WindowsOwnerPolicyContractError(
                "policy deployment projection v2 is invalid"
            ) from exc
    elif schema_version == POLICY_BODY_SCHEMA_V3:
        _exact_keys(body, _BODY_KEYS_V3, "policy_body")
        expected_domain = POLICY_DOMAIN_V3
        anchor_domain = OWNER_ANCHOR_DOMAIN_V3
        try:
            deployment_projection = deployment._validate_projection(
                body.get("deployment_projection")
            )
        except deployment.P0WindowsOwnerDeploymentProjectionError as exc:
            raise P0WindowsOwnerPolicyContractError(
                "policy deployment projection v3 nested v2 contract is invalid"
            ) from exc
        try:
            native_observer_profile = (
                observer_profile._validate_native_observer_profile(
                    body.get("native_observer_profile")
                )
            )
        except observer_profile.P0WindowsNativeObserverProfileContractError as exc:
            raise P0WindowsOwnerPolicyContractError(
                "policy native observer profile v1 is invalid"
            ) from exc
    else:
        raise P0WindowsOwnerPolicyContractError("policy body schema mismatch")
    if body.get("record_origin") != POLICY_ORIGIN:
        raise P0WindowsOwnerPolicyContractError("policy body origin mismatch")
    if body.get("domain") != expected_domain:
        raise P0WindowsOwnerPolicyContractError("policy body domain mismatch")
    policy_id = _identifier(body.get("policy_id"), "policy_id")
    policy_epoch = _positive_int(body.get("policy_epoch"), "policy_epoch")
    predecessor = body.get("predecessor_policy_bytes_sha256")
    if policy_epoch == 1:
        if predecessor is not None:
            raise P0WindowsOwnerPolicyContractError(
                "genesis policy must have null predecessor"
            )
    else:
        _sha(predecessor, "predecessor_policy_bytes_sha256")
    scope = {
        field: _identifier(body.get(field), field)
        for field in (
            "store_id",
            "project_id",
            "trust_domain",
            "environment",
            "purpose",
            "bootstrap_key_id",
        )
    }
    bootstrap_fingerprint = _sha(
        body.get("bootstrap_public_key_fingerprint_sha256"),
        "bootstrap_public_key_fingerprint_sha256",
    )
    owner_sid = _sid(body.get("owner_sid"), "owner_sid")
    verifier_sid = _sid(body.get("verifier_sid"), "verifier_sid")
    if owner_sid == verifier_sid:
        raise P0WindowsOwnerPolicyContractError(
            "owner_sid and verifier_sid must be distinct"
        )
    if (
        owner_sid in _BROAD_OR_PRIVILEGED_GROUP_SIDS
        or _forbidden_builtin_alias(owner_sid)
        or not _permitted_owner_sid_profile(owner_sid)
    ):
        raise P0WindowsOwnerPolicyContractError(
            "owner_sid is outside the permitted structural owner profile"
        )
    if (
        verifier_sid in _FORBIDDEN_VERIFIER_SIDS
        or _forbidden_builtin_alias(verifier_sid)
        or not _permitted_verifier_sid_profile(verifier_sid)
    ):
        raise P0WindowsOwnerPolicyContractError(
            "verifier_sid is outside the permitted structural verifier profile"
        )
    if (
        deployment_projection is not None
        and verifier_sid != deployment_projection["service_sid"]
    ):
        raise P0WindowsOwnerPolicyContractError(
            "v2/v3 verifier_sid must match the fixed deployment service SID"
        )
    if native_observer_profile is not None:
        expected_profile_bindings = {
            "deployment_projection_sha256": deployment_projection[
                "artifact_sha256"
            ],
            "service_name": deployment_projection["service_name"],
            "service_sid": deployment_projection["service_sid"],
        }
        for field, expected in expected_profile_bindings.items():
            if native_observer_profile.get(field) != expected:
                raise P0WindowsOwnerPolicyContractError(
                    f"v3 native observer profile {field} cross-binding mismatch"
                )
    object_policies = _validate_object_policies(
        body.get("object_policies"),
        owner_sid=owner_sid,
        verifier_sid=verifier_sid,
        policy_epoch=policy_epoch,
    )
    operational_key = _validate_operational_key(body.get("operational_key"))
    if native_observer_profile is not None:
        role_key_ids = (
            scope["bootstrap_key_id"],
            operational_key["key_id"],
            native_observer_profile["observer_key_id"],
            native_observer_profile["owner_state_authority_key_id"],
        )
        role_fingerprints = (
            bootstrap_fingerprint,
            operational_key["public_key_fingerprint_sha256"],
            native_observer_profile[
                "observer_public_key_fingerprint_sha256"
            ],
            native_observer_profile["owner_state_authority_spki_sha256"],
        )
        if len(set(role_key_ids)) != len(role_key_ids):
            raise P0WindowsOwnerPolicyContractError(
                "v3 bootstrap/operational/observer/owner-state key IDs must be distinct"
            )
        if len(set(role_fingerprints)) != len(role_fingerprints):
            raise P0WindowsOwnerPolicyContractError(
                "v3 bootstrap/operational/observer/owner-state key fingerprints must be distinct"
            )
    min_revocation_sequence = _positive_int(
        body.get("min_revocation_sequence"), "min_revocation_sequence"
    )
    if body.get("lifecycle_status") != "ACTIVE":
        raise P0WindowsOwnerPolicyContractError(
            "first-version policy lifecycle_status must be ACTIVE"
        )

    owner_principal = derive_owner_principal_sha256(owner_sid)
    acl_projection = [
        {
            "role": row["role"],
            "object_kind": row["object_kind"],
            "security_template": row["security_template"],
        }
        for row in object_policies
    ]
    acl_hash = canonical_sha256(
        {"domain": ACL_TEMPLATE_DOMAIN, "objects": acl_projection}
    )
    operational_key_hash = derive_operational_key_projection_sha256(
        operational_key
    )
    object_identity_hash = canonical_sha256(
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
            for row in object_policies
        ]
    )
    anchor_material = {
        "domain": anchor_domain,
        "policy_id": policy_id,
        "policy_epoch": policy_epoch,
        "predecessor_policy_bytes_sha256": predecessor,
        **scope,
        "bootstrap_public_key_fingerprint_sha256": bootstrap_fingerprint,
        "owner_principal_sha256": owner_principal,
        "verifier_sid": verifier_sid,
        "object_identity_projection_sha256": object_identity_hash,
        "acl_template_sha256": acl_hash,
        "operational_key_projection_sha256": operational_key_hash,
        "min_revocation_sequence": min_revocation_sequence,
        "lifecycle_status": "ACTIVE",
    }
    if deployment_projection is not None:
        anchor_material["deployment_projection_sha256"] = (
            deployment_projection["artifact_sha256"]
        )
    if native_observer_profile is not None:
        anchor_material["native_observer_profile_sha256"] = (
            native_observer_profile["artifact_sha256"]
        )
    anchor = canonical_sha256(anchor_material)
    derived = {
        "owner_principal_sha256": owner_principal,
        "acl_template_sha256": acl_hash,
        "operational_key_projection_sha256": operational_key_hash,
        "owner_anchor_sha256": anchor,
    }
    for field, expected in derived.items():
        actual = _sha(body.get(field), field)
        if not hmac.compare_digest(actual, expected):
            raise P0WindowsOwnerPolicyContractError(f"{field} mismatch")
    _artifact_hash(body, "policy_body")
    return dict(body)


def _validate_signature(raw: bytes, body: Mapping[str, Any], body_raw: bytes) -> dict[str, Any]:
    signature = _parse_canonical_object(raw, "policy_signature")
    _exact_keys(signature, _SIGNATURE_KEYS, "policy_signature")
    if type(signature.get("policy_epoch")) is not int:
        raise P0WindowsOwnerPolicyContractError(
            "policy_signature.policy_epoch must be an integer"
        )
    body_is_v2 = body["schema_version"] == POLICY_BODY_SCHEMA_V2
    body_is_v3 = body["schema_version"] == POLICY_BODY_SCHEMA_V3
    expected_values = {
        "schema_version": (
            POLICY_SIGNATURE_SCHEMA_V3
            if body_is_v3
            else POLICY_SIGNATURE_SCHEMA_V2
            if body_is_v2
            else POLICY_SIGNATURE_SCHEMA
        ),
        "record_origin": SIGNATURE_ORIGIN,
        "domain": (
            SIGNATURE_DOMAIN_V3
            if body_is_v3
            else SIGNATURE_DOMAIN_V2
            if body_is_v2
            else SIGNATURE_DOMAIN
        ),
        "policy_id": body["policy_id"],
        "policy_epoch": body["policy_epoch"],
        "bootstrap_key_id": body["bootstrap_key_id"],
        "bootstrap_public_key_fingerprint_sha256": body[
            "bootstrap_public_key_fingerprint_sha256"
        ],
        "policy_body_bytes_sha256": hashlib.sha256(body_raw).hexdigest(),
        "algorithm": BOOTSTRAP_SIGNATURE_ALGORITHM,
    }
    for field, expected in expected_values.items():
        if signature.get(field) != expected:
            raise P0WindowsOwnerPolicyContractError(
                f"policy_signature.{field} mismatch"
            )
    encoded = signature.get("signature_rs_base64")
    if not isinstance(encoded, str):
        raise P0WindowsOwnerPolicyContractError(
            "policy_signature.signature_rs_base64 is invalid"
        )
    try:
        raw_signature = base64.b64decode(encoded, validate=True)
    except (ValueError, base64.binascii.Error) as exc:
        raise P0WindowsOwnerPolicyContractError(
            "policy_signature.signature_rs_base64 is invalid"
        ) from exc
    if len(raw_signature) != 64:
        raise P0WindowsOwnerPolicyContractError(
            "policy signature must be a 64-byte IEEE P1363 value"
        )
    if base64.b64encode(raw_signature).decode("ascii") != encoded:
        raise P0WindowsOwnerPolicyContractError(
            "policy signature Base64 must use canonical pad bits"
        )
    r = int.from_bytes(raw_signature[:32], "big")
    s = int.from_bytes(raw_signature[32:], "big")
    if not 1 <= r < _P256_ORDER or not 1 <= s <= _P256_ORDER // 2:
        raise P0WindowsOwnerPolicyContractError(
            "policy signature must contain bounded low-S P-256 scalars"
        )
    _artifact_hash(signature, "policy_signature")
    return dict(signature)


def validate_presented_windows_owner_policy_contract(
    *, policy_body_bytes: bytes, policy_signature_bytes: bytes
) -> dict[str, Any]:
    """Validate strict presented bytes without upgrading them to authority."""

    body = _validate_policy_body(policy_body_bytes)
    signature = _validate_signature(
        policy_signature_bytes, body, policy_body_bytes
    )
    security_template_hashes = {
        row["role"]: canonical_sha256(row["security_template"])
        for row in body["object_policies"]
    }
    body_is_v2 = body["schema_version"] == POLICY_BODY_SCHEMA_V2
    body_is_v3 = body["schema_version"] == POLICY_BODY_SCHEMA_V3
    material: dict[str, Any] = {
        "schema_version": (
            CONTRACT_RECEIPT_SCHEMA_V3
            if body_is_v3
            else CONTRACT_RECEIPT_SCHEMA_V2
            if body_is_v2
            else CONTRACT_RECEIPT_SCHEMA
        ),
        "gate_status": GATE_STATUS,
        "policy_id": body["policy_id"],
        "policy_epoch": body["policy_epoch"],
        "policy_body_bytes_sha256": hashlib.sha256(policy_body_bytes).hexdigest(),
        "policy_body_artifact_sha256": body["artifact_sha256"],
        "policy_signature_bytes_sha256": hashlib.sha256(
            policy_signature_bytes
        ).hexdigest(),
        "policy_signature_artifact_sha256": signature["artifact_sha256"],
        "store_id": body["store_id"],
        "owner_principal_sha256": body["owner_principal_sha256"],
        "owner_anchor_sha256": body["owner_anchor_sha256"],
        "owner_anchor_scope": (
            "CORE_POLICY_IDENTITY_EXCLUDING_PIN_TRANSPORT_HASHES"
        ),
        "owner_anchor_excludes_pin_transport_hashes_by_design": True,
        "full_policy_identity_sha256": hashlib.sha256(
            policy_body_bytes
        ).hexdigest(),
        "acl_template_sha256": body["acl_template_sha256"],
        "operational_key_projection_sha256": body[
            "operational_key_projection_sha256"
        ],
        "object_identity_projection_sha256": canonical_sha256(
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
                for row in body["object_policies"]
            ]
        ),
        "security_template_sha256_by_role": security_template_hashes,
        "strict_canonical_policy_body_verified": True,
        "strict_canonical_detached_signature_envelope_verified": True,
        "owner_and_verifier_sid_disjoint_contract_verified": True,
        "fixed_generation_layout_contract_verified": True,
        "exact_standard_explicit_ace_profile_contract_verified": True,
        "derived_owner_anchor_cross_binding_verified": True,
        "detached_signature_body_hash_cross_binding_verified": True,
        **{field: False for field in _ALWAYS_FALSE_FIELDS},
    }
    if body_is_v2:
        material.update(
            {
                "policy_schema_version": body["schema_version"],
                "policy_domain": body["domain"],
                "signature_schema_version": signature["schema_version"],
                "signature_domain": signature["domain"],
                "deployment_projection_sha256": body[
                    "deployment_projection"
                ]["artifact_sha256"],
                "deployment_projection_contract_verified": True,
                "policy_verifier_sid_deployment_service_sid_cross_binding_verified": True,
                "future_authority_policy_requires_v2": True,
                "future_authority_policy_version_eligible": True,
            }
        )
    elif body_is_v3:
        material.update(
            {
                "policy_schema_version": body["schema_version"],
                "policy_domain": body["domain"],
                "signature_schema_version": signature["schema_version"],
                "signature_domain": signature["domain"],
                "deployment_projection_sha256": body[
                    "deployment_projection"
                ]["artifact_sha256"],
                "native_observer_profile_sha256": body[
                    "native_observer_profile"
                ]["artifact_sha256"],
                "deployment_projection_contract_verified": True,
                "native_observer_profile_contract_verified": True,
                "policy_verifier_sid_deployment_service_sid_cross_binding_verified": True,
                "policy_deployment_native_observer_profile_cross_binding_verified": True,
                "operational_and_observer_key_role_separation_contract_verified": True,
                "future_native_observer_authority_requires_v3": True,
                "future_authority_policy_version_eligible": False,
                "positive_native_observer_policy_profile_complete": False,
            }
        )
    return {**material, "receipt_sha256": canonical_sha256(material)}


def compare_exact_security_projection(
    *,
    validated_policy_body_bytes: bytes,
    role: str,
    observed_security_projection: Mapping[str, Any],
) -> dict[str, Any]:
    """Compare a binary-reader projection to the signed template exactly.

    The projection remains caller-presented at this layer.  The function is a
    reusable exact comparator for a future held-handle Windows reader, not live
    OS evidence and not independent policy evidence.
    """

    body = _validate_policy_body(validated_policy_body_bytes)
    if role not in OBJECT_ROLES:
        raise P0WindowsOwnerPolicyContractError("unknown object policy role")
    if not isinstance(observed_security_projection, Mapping):
        raise P0WindowsOwnerPolicyContractError(
            "observed_security_projection must be an object"
        )
    expected = next(
        row["security_template"]
        for row in body["object_policies"]
        if row["role"] == role
    )
    observed = _validate_security_template(
        observed_security_projection,
        role=role,
        owner_sid=body["owner_sid"],
        verifier_sid=body["verifier_sid"],
    )
    if canonical_bytes(observed) != canonical_bytes(expected):
        raise P0WindowsOwnerPolicyContractError(
            "observed security projection does not exactly match policy"
        )
    material = {
        "schema_version": "p0_windows_owner_policy_security_comparison_v1",
        "role": role,
        "policy_body_bytes_sha256": hashlib.sha256(
            validated_policy_body_bytes
        ).hexdigest(),
        "expected_security_template_sha256": canonical_sha256(expected),
        "observed_security_projection_sha256": canonical_sha256(observed),
        "presented_projection_exact_match_verified": True,
        "live_windows_binary_acl_verified": False,
        "independent_owner_policy_state_verified": False,
        "owner_authority_verified": False,
        "production_approval": False,
        "full_scan_approval": False,
        "p0_phase_exit": False,
        "action_applied": False,
    }
    return {**material, "receipt_sha256": canonical_sha256(material)}


__all__ = [
    "ACCESS_ALLOWED_ACE_TYPE",
    "BOOTSTRAP_SIGNATURE_ALGORITHM",
    "CONTRACT_RECEIPT_SCHEMA",
    "CONTRACT_RECEIPT_SCHEMA_V2",
    "CONTRACT_RECEIPT_SCHEMA_V3",
    "DIRECTORY_READER_MASK",
    "FILE_ALL_ACCESS",
    "FILE_READER_MASK",
    "FIXED_POLICY_STORE_SUFFIX",
    "GATE_STATUS",
    "OBJECT_ROLES",
    "OPERATIONAL_KEY_ALGORITHM",
    "OPERATIONAL_SIGNATURE_DOMAIN",
    "OWNER_ANCHOR_DOMAIN",
    "OWNER_ANCHOR_DOMAIN_V2",
    "OWNER_ANCHOR_DOMAIN_V3",
    "POLICY_BODY_SCHEMA",
    "POLICY_BODY_SCHEMA_V2",
    "POLICY_BODY_SCHEMA_V3",
    "POLICY_DOMAIN",
    "POLICY_DOMAIN_V2",
    "POLICY_DOMAIN_V3",
    "POLICY_SIGNATURE_SCHEMA",
    "POLICY_SIGNATURE_SCHEMA_V2",
    "POLICY_SIGNATURE_SCHEMA_V3",
    "P0WindowsOwnerPolicyContractError",
    "SIGNATURE_DOMAIN",
    "SIGNATURE_DOMAIN_V2",
    "SIGNATURE_DOMAIN_V3",
    "canonical_bytes",
    "canonical_sha256",
    "compare_exact_security_projection",
    "derive_operational_key_projection_sha256",
    "derive_owner_principal_sha256",
    "json_file_bytes",
    "validate_presented_windows_owner_policy_contract",
]
