"""Fail-closed bridge between the key-less P0 packet and authority v2.

The authority-v2 examples are intentionally immutable.  This module adds a
one-way, post-v2 bridge instead of extending any v2 artifact.  It verifies
parser provenance and terminal cross-bindings, but it never grants authority,
credits observations, exits P0, or enables a production/full scan.

Inputs named ``*_receipt`` are expected to be receipts recomputed by their
own validators.  The bridge verifies their self hashes (where defined) and
the projections needed for the join; it does not accept caller-provided
"trusted" booleans as authority.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import hmac
import json
import re
from typing import Any, Mapping

from . import p0_actual_a_event_bytes as a_event_bytes_contract
from . import p0_actual_authority_contract as authority_contract
from . import p0_actual_authority_event_bytes as event_bytes_contract
from . import p0_actual_packet_contract as packet_contract
from . import p0_actual_route_contract as route_contract
from . import p0_windows_fixed_directory_identity as windows_contract


PARSER_PROVENANCE_AUTHORIZATION_SCHEMA = (
    "p0_actual_owner_parser_provenance_authorization_v1"
)
TERMINAL_BRIDGE_ATTESTATION_SCHEMA = (
    "p0_actual_terminal_authority_bridge_attestation_v1"
)
BRIDGE_RECEIPT_SCHEMA = "p0_actual_authority_bridge_receipt_v1"

PARSER_PROVENANCE_DOMAIN = (
    "llm-novel-dc-community-parser/p0-actual-parser-provenance-authorization/v1"
)
TERMINAL_BRIDGE_DOMAIN = (
    "llm-novel-dc-community-parser/p0-actual-terminal-authority-bridge/v1"
)
PARSER_PROVENANCE_DECISION = "AUTHORIZE_EXPECTED_P0_PARSER_PROVENANCE"
TERMINAL_BRIDGE_DECISION = "ATTEST_P0_ACTUAL_AUTHORITY_BRIDGE"
AUTHORITY_SCOPE = authority_contract.AUTHORITY_SCOPE
OPERATIONAL_EFFECT = authority_contract.OPERATIONAL_EFFECT

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")
_WINDOWS_FILE_ID = re.compile(r"^[0-9a-f]{32}$")
_WINDOWS_VOLUME_GUID_PATH = re.compile(
    r"^\\\\\?\\Volume\{[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-"
    r"[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}\}(?:\\.*)?$"
)

_PROVENANCE_FIELDS = frozenset(
    {
        "schema_version",
        "record_origin",
        "provenance_authorization_id",
        "domain",
        "algorithm",
        "key_id",
        "owner_anchor_sha256",
        "owner_authorization_sha256",
        "launch_sha256",
        "expected_parser_receipt_schema",
        "expected_parser_manifest_sha256",
        "expected_parser_version",
        "expected_capture_manifest_sha256",
        "expected_input_registry_sha256",
        "authority_scope",
        "decision",
        "issued_at",
        "not_before",
        "expires_at",
        "nonce",
        "provenance_signature_sha256",
        "verification_status",
        "action_applied",
        "operational_effect",
        "artifact_sha256",
    }
)

_TERMINAL_FIELDS = frozenset(
    {
        "schema_version",
        "record_origin",
        "bridge_attestation_id",
        "domain",
        "algorithm",
        "key_id",
        "owner_anchor_sha256",
        "owner_authorization_sha256",
        "parser_provenance_authorization_sha256",
        "launch_sha256",
        "keyless_manifest_file_sha256",
        "keyless_manifest_artifact_sha256",
        "packet_receipt_sha256",
        "route_receipt_sha256",
        "parser_receipt_sha256",
        "authority_manifest_sha256",
        "authority_final_attestation_sha256",
        "authority_foundation_receipt_sha256",
        "event_bytes_receipt_sha256",
        "event_file_sha256",
        "a_event_bytes_receipt_sha256",
        "a_context_file_sha256",
        "a_event_file_sha256",
        "a_subject_selection_seal_sha256",
        "windows_packet_validation_receipt_sha256",
        "windows_expected_manifest_sha256",
        "windows_root_final_path",
        "windows_root_volume_serial",
        "windows_root_file_id",
        "actual_source_claim_count",
        "actual_a_context_review_count",
        "issued_at",
        "nonce",
        "decision",
        "authority_scope",
        "bridge_signature_sha256",
        "verification_status",
        "action_applied",
        "operational_effect",
        "artifact_sha256",
    }
)

_A_EVENT_BYTES_RECEIPT_FIELDS = frozenset(
    {
        "schema_version",
        "record_origin",
        "source_claim_file_sha256",
        "source_claim_row_count",
        "a_context_file_sha256",
        "a_context_row_count",
        "a_event_file_sha256",
        "a_event_row_count",
        "a_subject_selection_seal_file_sha256",
        "a_subject_selection_seal_row_count",
        "a_subject_selection_seal_sha256",
        "a_context_receipt",
        "a_context_receipt_sha256",
        "head_count",
        "head_projection_sha256",
        "canonical_input_bytes_verified",
        "a_event_hash_chains_verified",
        "latest_event_projection_verified",
        "a_subject_selection_seal_verified",
        "filesystem_handle_trust_verified",
        "durable_predecessor_verified",
        "annotation_append_only_verified",
        "owner_authority_verified",
        "runtime_noninterference_verified",
        "credited_actual_a_context_review_count",
        "actual_authority_granted",
        "production_approval",
        "full_scan_approval",
        "p0_phase_exit",
        "action_applied",
        "operational_effect",
        "gate_status",
        "receipt_sha256",
    }
)

_WINDOWS_COMPOSITE_RECEIPT_FIELDS = frozenset(
    {
        "schema_version",
        "expected_manifest_sha256",
        "windows_handle_receipt",
        "windows_handle_receipt_declared_receipt_sha256",
        "windows_handle_receipt_full_canonical_sha256",
        "packet_receipt",
        "packet_receipt_declared_receipt_sha256",
        "packet_receipt_full_canonical_sha256",
        "handle_member_inventory_projection",
        "handle_member_inventory_sha256",
        "packet_manifest_fixed_file_inventory_projection",
        "packet_manifest_fixed_file_inventory_sha256",
        "handle_manifest_fixed_file_inventory_exact_match",
        "byte_inventory_binding_verified",
        "filesystem_handle_binding_verified",
        "filesystem_handle_trust_verified",
        "external_root_identity_pin_verified",
        "os_write_deny_verified",
        "runtime_noninterference_verified",
        "external_owner_authority_verified",
        "actual_authority_granted",
        "production_approval",
        "full_scan_approval",
        "p0_phase_exit",
        "action_applied",
        "operational_effect",
        "gate_status",
        "receipt_hash_scope",
        "receipt_sha256",
    }
)


class P0ActualAuthorityBridgeError(ValueError):
    """Raised when a bridge artifact or cross-binding fails closed."""


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


def _strict(value: Any, fields: frozenset[str], label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise P0ActualAuthorityBridgeError(f"{label} must be an object")
    keys = frozenset(value)
    if keys != fields:
        missing = sorted(fields - keys)
        extra = sorted(keys - fields)
        raise P0ActualAuthorityBridgeError(
            f"{label} fields mismatch: missing={missing}, extra={extra}"
        )
    return dict(value)


def _required(value: Mapping[str, Any], fields: tuple[str, ...], label: str) -> None:
    missing = [field for field in fields if field not in value]
    if missing:
        raise P0ActualAuthorityBridgeError(f"{label} missing fields: {missing}")


def _sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise P0ActualAuthorityBridgeError(f"{label} must be lowercase sha256")
    return value


def _optional_sha(value: Any, label: str) -> str | None:
    if value is None:
        return None
    return _sha(value, label)


def _identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or _SAFE_ID.fullmatch(value) is None:
        raise P0ActualAuthorityBridgeError(f"{label} is invalid")
    return value


def _text(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 256
        or any(ord(char) < 32 for char in value)
    ):
        raise P0ActualAuthorityBridgeError(f"{label} must be nonempty text")
    return value


def _timestamp(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise P0ActualAuthorityBridgeError(f"{label} must be RFC3339 UTC")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise P0ActualAuthorityBridgeError(f"{label} must be RFC3339 UTC") from exc
    if parsed.isoformat().replace("+00:00", "Z") != value:
        raise P0ActualAuthorityBridgeError(f"{label} must be canonical RFC3339 UTC")
    return parsed


def _self_hash(row: Mapping[str, Any], label: str) -> None:
    stored = _sha(row.get("artifact_sha256"), f"{label}.artifact_sha256")
    material = {key: item for key, item in row.items() if key != "artifact_sha256"}
    if stored != canonical_sha256(material):
        raise P0ActualAuthorityBridgeError(f"{label} self hash mismatch")


def _receipt_hash(row: Mapping[str, Any], label: str) -> None:
    stored = _sha(row.get("receipt_sha256"), f"{label}.receipt_sha256")
    material = {key: item for key, item in row.items() if key != "receipt_sha256"}
    if stored != canonical_sha256(material):
        raise P0ActualAuthorityBridgeError(f"{label} receipt hash mismatch")


def _signature_material(row: Mapping[str, Any], signature_field: str) -> dict[str, Any]:
    return {
        key: item
        for key, item in row.items()
        if key not in {signature_field, "artifact_sha256"}
    }


def _sign(row: Mapping[str, Any], key: bytes, signature_field: str) -> str:
    if not isinstance(key, bytes) or len(key) < 32:
        raise P0ActualAuthorityBridgeError("owner HMAC key must be at least 32 bytes")
    return hmac.new(
        key,
        canonical_bytes(_signature_material(row, signature_field)),
        hashlib.sha256,
    ).hexdigest()


def sign_parser_provenance_authorization(
    row: Mapping[str, Any], key: bytes
) -> str:
    return _sign(row, key, "provenance_signature_sha256")


def sign_terminal_bridge_attestation(row: Mapping[str, Any], key: bytes) -> str:
    return _sign(row, key, "bridge_signature_sha256")


def _validate_signature_state(
    row: Mapping[str, Any],
    *,
    signature_field: str,
    expected_origin: str,
    key: bytes | None,
    expected_external_anchor_sha256: str | None,
    signer: Any,
    label: str,
) -> bool:
    signature = _optional_sha(row[signature_field], signature_field)
    status = row["verification_status"]
    if status not in {
        "EXTERNAL_KEY_ABSENT",
        "DETACHED_SIGNATURE_PRESENT_UNVERIFIED",
    }:
        raise P0ActualAuthorityBridgeError(f"{label} verification status is invalid")
    if (signature is None) != (status == "EXTERNAL_KEY_ABSENT"):
        raise P0ActualAuthorityBridgeError(f"{label} signature/status mismatch")
    if expected_origin == authority_contract.EXAMPLE_ORIGIN:
        if signature is not None:
            raise P0ActualAuthorityBridgeError(f"example {label} must be unsigned")
    elif expected_origin == authority_contract.ACTUAL_ORIGIN:
        if signature is None:
            raise P0ActualAuthorityBridgeError(f"actual {label} requires signature")
    else:
        raise P0ActualAuthorityBridgeError("unsupported authority origin")
    if key is None and expected_external_anchor_sha256 is None:
        return False
    if key is None or expected_external_anchor_sha256 is None:
        raise P0ActualAuthorityBridgeError(
            "key and expected external anchor must be supplied together"
        )
    if expected_origin != authority_contract.ACTUAL_ORIGIN:
        return False
    if (
        _sha(expected_external_anchor_sha256, "expected_external_anchor_sha256")
        != row["owner_anchor_sha256"]
    ):
        raise P0ActualAuthorityBridgeError(f"{label} external anchor mismatch")
    if signature is None or not hmac.compare_digest(signature, signer(row, key)):
        raise P0ActualAuthorityBridgeError(f"{label} signature mismatch")
    return True


def validate_parser_provenance_authorization(
    value: Any,
    expected_origin: str,
    *,
    key: bytes | None = None,
    expected_external_anchor_sha256: str | None = None,
) -> tuple[dict[str, Any], bool]:
    row = _strict(value, _PROVENANCE_FIELDS, "parser provenance authorization")
    if row["schema_version"] != PARSER_PROVENANCE_AUTHORIZATION_SCHEMA:
        raise P0ActualAuthorityBridgeError("parser provenance schema mismatch")
    if row["record_origin"] != expected_origin:
        raise P0ActualAuthorityBridgeError("parser provenance origin mismatch")
    _identifier(row["provenance_authorization_id"], "provenance_authorization_id")
    if row["domain"] != PARSER_PROVENANCE_DOMAIN or row["algorithm"] != "HMAC-SHA256":
        raise P0ActualAuthorityBridgeError("parser provenance domain/algorithm mismatch")
    _identifier(row["key_id"], "key_id")
    for field in (
        "owner_anchor_sha256",
        "owner_authorization_sha256",
        "launch_sha256",
        "expected_parser_manifest_sha256",
    ):
        _sha(row[field], field)
    _optional_sha(row["expected_capture_manifest_sha256"], "expected_capture_manifest_sha256")
    _optional_sha(row["expected_input_registry_sha256"], "expected_input_registry_sha256")
    if row["expected_parser_receipt_schema"] != authority_contract.PARSER_RECEIPT_SCHEMA:
        raise P0ActualAuthorityBridgeError("expected parser receipt schema mismatch")
    _text(row["expected_parser_version"], "expected_parser_version")
    if row["authority_scope"] != AUTHORITY_SCOPE or row["decision"] != PARSER_PROVENANCE_DECISION:
        raise P0ActualAuthorityBridgeError("parser provenance decision/scope mismatch")
    issued = _timestamp(row["issued_at"], "issued_at")
    not_before = _timestamp(row["not_before"], "not_before")
    expires = _timestamp(row["expires_at"], "expires_at")
    if not (issued <= not_before < expires):
        raise P0ActualAuthorityBridgeError("parser provenance validity interval is invalid")
    _identifier(row["nonce"], "nonce")
    if row["action_applied"] is not False or row["operational_effect"] != OPERATIONAL_EFFECT:
        raise P0ActualAuthorityBridgeError("parser provenance must remain no-write")
    verified = _validate_signature_state(
        row,
        signature_field="provenance_signature_sha256",
        expected_origin=expected_origin,
        key=key,
        expected_external_anchor_sha256=expected_external_anchor_sha256,
        signer=sign_parser_provenance_authorization,
        label="parser provenance authorization",
    )
    _self_hash(row, "parser provenance authorization")
    return row, verified


def validate_terminal_bridge_attestation(
    value: Any,
    expected_origin: str,
    *,
    key: bytes | None = None,
    expected_external_anchor_sha256: str | None = None,
) -> tuple[dict[str, Any], bool]:
    row = _strict(value, _TERMINAL_FIELDS, "terminal bridge attestation")
    if row["schema_version"] != TERMINAL_BRIDGE_ATTESTATION_SCHEMA:
        raise P0ActualAuthorityBridgeError("terminal bridge schema mismatch")
    if row["record_origin"] != expected_origin:
        raise P0ActualAuthorityBridgeError("terminal bridge origin mismatch")
    _identifier(row["bridge_attestation_id"], "bridge_attestation_id")
    if row["domain"] != TERMINAL_BRIDGE_DOMAIN or row["algorithm"] != "HMAC-SHA256":
        raise P0ActualAuthorityBridgeError("terminal bridge domain/algorithm mismatch")
    _identifier(row["key_id"], "key_id")
    for field in (
        "owner_anchor_sha256",
        "owner_authorization_sha256",
        "parser_provenance_authorization_sha256",
        "launch_sha256",
        "keyless_manifest_file_sha256",
        "keyless_manifest_artifact_sha256",
        "packet_receipt_sha256",
        "route_receipt_sha256",
        "parser_receipt_sha256",
        "authority_manifest_sha256",
        "authority_final_attestation_sha256",
        "authority_foundation_receipt_sha256",
        "event_bytes_receipt_sha256",
        "event_file_sha256",
        "a_event_bytes_receipt_sha256",
        "a_context_file_sha256",
        "a_event_file_sha256",
        "a_subject_selection_seal_sha256",
        "windows_packet_validation_receipt_sha256",
        "windows_expected_manifest_sha256",
    ):
        _sha(row[field], field)
    if (
        not isinstance(row["windows_root_final_path"], str)
        or _WINDOWS_VOLUME_GUID_PATH.fullmatch(row["windows_root_final_path"]) is None
    ):
        raise P0ActualAuthorityBridgeError("Windows root final path is invalid")
    volume_serial = row["windows_root_volume_serial"]
    if (
        not isinstance(volume_serial, str)
        or not volume_serial.isdecimal()
        or not 0 <= int(volume_serial) < 2**64
    ):
        raise P0ActualAuthorityBridgeError("Windows root volume serial is invalid")
    if (
        not isinstance(row["windows_root_file_id"], str)
        or _WINDOWS_FILE_ID.fullmatch(row["windows_root_file_id"]) is None
    ):
        raise P0ActualAuthorityBridgeError("Windows root file id is invalid")
    if row["actual_source_claim_count"] != 40 or row["actual_a_context_review_count"] != 20:
        raise P0ActualAuthorityBridgeError("terminal bridge requires observed 40+20")
    _timestamp(row["issued_at"], "issued_at")
    _identifier(row["nonce"], "nonce")
    if row["decision"] != TERMINAL_BRIDGE_DECISION or row["authority_scope"] != AUTHORITY_SCOPE:
        raise P0ActualAuthorityBridgeError("terminal bridge decision/scope mismatch")
    if row["action_applied"] is not False or row["operational_effect"] != OPERATIONAL_EFFECT:
        raise P0ActualAuthorityBridgeError("terminal bridge must remain no-write")
    verified = _validate_signature_state(
        row,
        signature_field="bridge_signature_sha256",
        expected_origin=expected_origin,
        key=key,
        expected_external_anchor_sha256=expected_external_anchor_sha256,
        signer=sign_terminal_bridge_attestation,
        label="terminal bridge attestation",
    )
    _self_hash(row, "terminal bridge attestation")
    return row, verified


def _must_equal(bindings: Mapping[str, bool]) -> None:
    failed = [name for name, valid in bindings.items() if not valid]
    if failed:
        raise P0ActualAuthorityBridgeError(f"authority bridge binding mismatch: {failed}")


def _input_authority_flags_must_be_false(*rows: Mapping[str, Any]) -> None:
    fields = (
        "external_owner_authority_verified",
        "owner_authority_verified",
        "actual_authority_granted",
        "production_approval",
        "full_scan_approval",
        "p0_phase_exit",
        "action_applied",
    )
    for row in rows:
        for field in fields:
            if field in row and row[field] is not False:
                raise P0ActualAuthorityBridgeError(
                    f"caller authority projection must remain false: {field}"
                )


def validate_authority_bridge_bundle(
    *,
    parser_provenance_authorization: Mapping[str, Any],
    terminal_bridge_attestation: Mapping[str, Any],
    owner_anchor: Mapping[str, Any],
    owner_authorization: Mapping[str, Any],
    launch: Mapping[str, Any],
    parser_receipt: Mapping[str, Any],
    route_receipt: Mapping[str, Any],
    keyless_manifest: Mapping[str, Any],
    packet_receipt: Mapping[str, Any],
    authority_manifest: Mapping[str, Any],
    authority_final_attestation: Mapping[str, Any],
    authority_foundation_receipt: Mapping[str, Any],
    event_bytes_receipt: Mapping[str, Any],
    a_event_bytes_receipt: Mapping[str, Any],
    windows_packet_validation_receipt: Mapping[str, Any],
    expected_authority_origin: str,
    expected_packet_origin: str,
    key: bytes | None = None,
    expected_external_anchor_sha256: str | None = None,
) -> dict[str, Any]:
    """Cross-bind recomputed terminal artifacts without granting authority."""

    expected_pair = {
        authority_contract.ACTUAL_ORIGIN: packet_contract.ACTUAL_ORIGIN,
        authority_contract.EXAMPLE_ORIGIN: packet_contract.EXAMPLE_ORIGIN,
    }
    if expected_pair.get(expected_authority_origin) != expected_packet_origin:
        raise P0ActualAuthorityBridgeError("authority/packet origin pair mismatch")

    provenance, provenance_math_valid = validate_parser_provenance_authorization(
        parser_provenance_authorization,
        expected_authority_origin,
        key=key,
        expected_external_anchor_sha256=expected_external_anchor_sha256,
    )
    terminal, terminal_math_valid = validate_terminal_bridge_attestation(
        terminal_bridge_attestation,
        expected_authority_origin,
        key=key,
        expected_external_anchor_sha256=expected_external_anchor_sha256,
    )

    for row, label in (
        (owner_anchor, "owner anchor"),
        (owner_authorization, "owner authorization"),
        (launch, "launch"),
        (parser_receipt, "parser receipt"),
        (keyless_manifest, "keyless manifest"),
        (authority_manifest, "authority manifest"),
        (authority_final_attestation, "authority final attestation"),
    ):
        _self_hash(row, label)
    _receipt_hash(authority_foundation_receipt, "authority foundation receipt")
    _receipt_hash(event_bytes_receipt, "event bytes receipt")
    a_event_receipt = _strict(
        a_event_bytes_receipt,
        _A_EVENT_BYTES_RECEIPT_FIELDS,
        "A event bytes receipt",
    )
    _receipt_hash(a_event_receipt, "A event bytes receipt")
    windows_receipt = _strict(
        windows_packet_validation_receipt,
        _WINDOWS_COMPOSITE_RECEIPT_FIELDS,
        "Windows packet validation receipt",
    )
    _receipt_hash(windows_receipt, "Windows packet validation receipt")

    _required(owner_anchor, ("record_origin", "key_id", "artifact_sha256"), "owner anchor")
    _required(
        owner_authorization,
        (
            "record_origin",
            "key_id",
            "owner_anchor_sha256",
            "launch_sha256",
            "issued_at",
            "not_before",
            "expires_at",
            "artifact_sha256",
        ),
        "owner authorization",
    )
    _required(launch, ("record_origin", "created_at", "capture_started_at", "artifact_sha256"), "launch")
    _required(
        parser_receipt,
        (
            "schema_version",
            "record_origin",
            "launch_sha256",
            "runtime_status",
            "completed_at",
            "capture_manifest_sha256",
            "input_registry_sha256",
            "artifact_sha256",
        ),
        "parser receipt",
    )
    _required(
        route_receipt,
        (
            "schema_version",
            "record_origin",
            "source_input_plan_sha256",
            "sampling_frame_sha256",
            "parser_manifest_sha256",
            "parser_version",
            "parser_launch_sha256",
            "parser_capture_manifest_sha256",
            "captured_source_registry_sha256",
            "route_accounting_packet_complete",
            "actual_authority_granted",
        ),
        "route receipt",
    )
    _required(
        keyless_manifest,
        (
            "record_origin",
            "created_at",
            "files",
            "route_receipt_sha256",
            "parser_receipt_sha256",
            "a_context_receipt_sha256",
            "a_subject_selection_seal_sha256",
            "observed_counts",
            "credited_counts",
            "artifact_sha256",
        ),
        "keyless manifest",
    )
    _required(
        packet_receipt,
        (
            "schema_version",
            "record_origin",
            "manifest_file_sha256",
            "manifest_artifact_sha256",
            "route_receipt_sha256",
            "parser_receipt_sha256",
            "a_context_receipt_sha256",
            "a_subject_selection_seal_sha256",
            "source_input_plan_sha256",
            "sampling_frame_sha256",
            "route_parser_manifest_sha256",
            "route_parser_version",
            "route_parser_launch_sha256",
            "route_parser_capture_manifest_sha256",
            "route_accounting_packet_complete",
            "observed_counts",
            "credited_counts",
        ),
        "packet receipt",
    )
    _required(
        authority_manifest,
        (
            "record_origin",
            "parser_receipt_sha256",
            "finalized_at",
            "actual_source_claim_count",
            "actual_a_context_review_count",
            "artifact_sha256",
        ),
        "authority manifest",
    )
    _required(
        authority_final_attestation,
        (
            "record_origin",
            "owner_anchor_sha256",
            "owner_authorization_sha256",
            "launch_sha256",
            "parser_receipt_sha256",
            "manifest_sha256",
            "event_file_sha256",
            "actual_source_claim_count",
            "actual_a_context_review_count",
            "issued_at",
            "artifact_sha256",
        ),
        "authority final attestation",
    )
    _required(
        authority_foundation_receipt,
        (
            "schema_version",
            "record_origin",
            "manifest_sha256",
            "final_attestation_sha256",
            "owner_authority_verified",
            "actual_source_claim_count",
            "actual_a_context_review_count",
            "receipt_sha256",
        ),
        "authority foundation receipt",
    )
    _required(
        event_bytes_receipt,
        ("schema_version", "event_file_sha256", "receipt_sha256"),
        "event bytes receipt",
    )
    _required(
        a_event_receipt,
        tuple(sorted(_A_EVENT_BYTES_RECEIPT_FIELDS)),
        "A event bytes receipt",
    )

    if owner_anchor["record_origin"] != expected_authority_origin or any(
        row["record_origin"] != expected_authority_origin
        for row in (
            owner_authorization,
            launch,
            parser_receipt,
            authority_manifest,
            authority_final_attestation,
            authority_foundation_receipt,
        )
    ):
        raise P0ActualAuthorityBridgeError("authority artifact origin mismatch")
    if route_receipt["record_origin"] != expected_packet_origin or any(
        row["record_origin"] != expected_packet_origin
        for row in (keyless_manifest, packet_receipt, a_event_receipt)
    ):
        raise P0ActualAuthorityBridgeError("packet artifact origin mismatch")
    if parser_receipt["schema_version"] != authority_contract.PARSER_RECEIPT_SCHEMA:
        raise P0ActualAuthorityBridgeError("parser receipt schema mismatch")
    if route_receipt["schema_version"] != route_contract.ROUTE_RECEIPT_SCHEMA:
        raise P0ActualAuthorityBridgeError("route receipt schema mismatch")
    if packet_receipt["schema_version"] != packet_contract.PACKET_RECEIPT_SCHEMA:
        raise P0ActualAuthorityBridgeError("packet receipt schema mismatch")
    _receipt_hash(packet_receipt, "packet receipt")
    if authority_foundation_receipt["schema_version"] != authority_contract.RECEIPT_SCHEMA:
        raise P0ActualAuthorityBridgeError("authority receipt schema mismatch")
    if event_bytes_receipt["schema_version"] != event_bytes_contract.EVENT_BYTES_RECEIPT_SCHEMA:
        raise P0ActualAuthorityBridgeError("event receipt schema mismatch")
    if a_event_receipt["schema_version"] != a_event_bytes_contract.A_EVENT_BYTES_RECEIPT_SCHEMA:
        raise P0ActualAuthorityBridgeError("A event bytes receipt schema mismatch")
    if (
        windows_receipt["schema_version"]
        != windows_contract.WINDOWS_PACKET_VALIDATION_RECEIPT_SCHEMA
    ):
        raise P0ActualAuthorityBridgeError("Windows packet receipt schema mismatch")
    nested_handle_receipt = windows_receipt["windows_handle_receipt"]
    if not isinstance(nested_handle_receipt, Mapping):
        raise P0ActualAuthorityBridgeError("Windows handle receipt must be an object")
    _required(
        nested_handle_receipt,
        (
            "schema_version",
            "root_final_path",
            "root_volume_serial",
            "root_file_id",
            "external_root_identity_pin_verified",
            "filesystem_handle_binding_verified",
            "filesystem_handle_trust_verified",
            "os_write_deny_verified",
            "runtime_noninterference_verified",
            "authority_journal_watch_bundle_verified",
            "external_owner_authority_verified",
            "actual_authority_granted",
            "production_approval",
            "full_scan_approval",
            "p0_phase_exit",
            "action_applied",
            "operational_effect",
            "receipt_sha256",
        ),
        "Windows handle receipt",
    )
    if nested_handle_receipt["schema_version"] != windows_contract.WINDOWS_HANDLE_RECEIPT_SCHEMA:
        raise P0ActualAuthorityBridgeError("Windows handle receipt schema mismatch")
    _receipt_hash(nested_handle_receipt, "Windows handle receipt")

    route_sha = canonical_sha256(route_receipt)
    packet_file_sha = _sha(packet_receipt["manifest_file_sha256"], "manifest_file_sha256")
    packet_artifact_sha = _sha(keyless_manifest["artifact_sha256"], "keyless manifest hash")
    recomputed_packet_file_sha = hashlib.sha256(
        canonical_bytes(keyless_manifest) + b"\n"
    ).hexdigest()
    if packet_file_sha != recomputed_packet_file_sha:
        raise P0ActualAuthorityBridgeError(
            "keyless manifest file hash does not match canonical bytes"
        )
    parser_sha = _sha(parser_receipt["artifact_sha256"], "parser receipt hash")
    authority_manifest_sha = _sha(authority_manifest["artifact_sha256"], "authority manifest hash")
    authority_final_sha = _sha(authority_final_attestation["artifact_sha256"], "authority final hash")
    authority_receipt_sha = _sha(authority_foundation_receipt["receipt_sha256"], "authority receipt hash")
    event_receipt_sha = _sha(event_bytes_receipt["receipt_sha256"], "event receipt hash")
    packet_receipt_sha = _sha(packet_receipt["receipt_sha256"], "packet receipt hash")
    a_event_receipt_sha = _sha(a_event_receipt["receipt_sha256"], "A event receipt hash")
    windows_receipt_sha = _sha(
        windows_receipt["receipt_sha256"], "Windows packet receipt hash"
    )

    root_final_path = nested_handle_receipt["root_final_path"]
    root_volume_serial = nested_handle_receipt["root_volume_serial"]
    root_file_id = nested_handle_receipt["root_file_id"]
    if (
        not isinstance(root_final_path, str)
        or _WINDOWS_VOLUME_GUID_PATH.fullmatch(root_final_path) is None
    ):
        raise P0ActualAuthorityBridgeError("Windows handle root final path is invalid")
    if (
        not isinstance(root_volume_serial, str)
        or not root_volume_serial.isdecimal()
        or not 0 <= int(root_volume_serial) < 2**64
    ):
        raise P0ActualAuthorityBridgeError("Windows handle root volume serial is invalid")
    if not isinstance(root_file_id, str) or _WINDOWS_FILE_ID.fullmatch(root_file_id) is None:
        raise P0ActualAuthorityBridgeError("Windows handle root file id is invalid")

    handle_projection = windows_receipt["handle_member_inventory_projection"]
    packet_projection = windows_receipt[
        "packet_manifest_fixed_file_inventory_projection"
    ]
    if not isinstance(handle_projection, list) or not isinstance(packet_projection, list):
        raise P0ActualAuthorityBridgeError("Windows inventory projections must be lists")
    windows_bindings = {
        "nested handle declared hash": windows_receipt[
            "windows_handle_receipt_declared_receipt_sha256"
        ]
        == nested_handle_receipt["receipt_sha256"],
        "nested handle full hash": windows_receipt[
            "windows_handle_receipt_full_canonical_sha256"
        ]
        == canonical_sha256(nested_handle_receipt),
        "nested packet": windows_receipt["packet_receipt"] == packet_receipt,
        "nested packet declared hash": windows_receipt[
            "packet_receipt_declared_receipt_sha256"
        ]
        == packet_receipt_sha,
        "nested packet full hash": windows_receipt[
            "packet_receipt_full_canonical_sha256"
        ]
        == canonical_sha256(packet_receipt),
        "expected manifest": windows_receipt["expected_manifest_sha256"]
        == packet_file_sha,
        "handle inventory hash": windows_receipt[
            "handle_member_inventory_sha256"
        ]
        == canonical_sha256(handle_projection),
        "packet inventory hash": windows_receipt[
            "packet_manifest_fixed_file_inventory_sha256"
        ]
        == canonical_sha256(packet_projection),
        "inventory equality": handle_projection == packet_projection,
    }
    _must_equal({f"Windows {name}": valid for name, valid in windows_bindings.items()})
    for field in (
        "handle_manifest_fixed_file_inventory_exact_match",
        "byte_inventory_binding_verified",
        "filesystem_handle_binding_verified",
    ):
        if windows_receipt[field] is not True:
            raise P0ActualAuthorityBridgeError(
                f"Windows composite binding projection must be true: {field}"
            )
    if nested_handle_receipt["filesystem_handle_binding_verified"] is not True:
        raise P0ActualAuthorityBridgeError("Windows handle binding must be verified")
    for row, label in (
        (windows_receipt, "Windows composite"),
        (nested_handle_receipt, "Windows handle"),
    ):
        for field in (
            "filesystem_handle_trust_verified",
            "external_root_identity_pin_verified",
        ):
            if row[field] is not False:
                raise P0ActualAuthorityBridgeError(
                    f"{label} external trust projection must remain false: {field}"
                )
    for field in (
        "os_write_deny_verified",
        "runtime_noninterference_verified",
        "authority_journal_watch_bundle_verified",
        "external_owner_authority_verified",
        "actual_authority_granted",
        "production_approval",
        "full_scan_approval",
        "p0_phase_exit",
        "action_applied",
    ):
        if nested_handle_receipt[field] is not False:
            raise P0ActualAuthorityBridgeError(
                f"Windows handle authority projection must remain false: {field}"
            )
    if nested_handle_receipt["operational_effect"] != OPERATIONAL_EFFECT:
        raise P0ActualAuthorityBridgeError("Windows handle must remain no-write")
    for field in (
        "os_write_deny_verified",
        "runtime_noninterference_verified",
        "external_owner_authority_verified",
        "actual_authority_granted",
        "production_approval",
        "full_scan_approval",
        "p0_phase_exit",
        "action_applied",
    ):
        if windows_receipt[field] is not False:
            raise P0ActualAuthorityBridgeError(
                f"Windows composite authority projection must remain false: {field}"
            )
    if windows_receipt["operational_effect"] != OPERATIONAL_EFFECT:
        raise P0ActualAuthorityBridgeError("Windows composite must remain no-write")

    files = keyless_manifest["files"]
    if not isinstance(files, list):
        raise P0ActualAuthorityBridgeError("keyless manifest files must be a list")
    child_by_role: dict[str, Mapping[str, Any]] = {}
    for child in files:
        if not isinstance(child, Mapping) or not isinstance(child.get("role"), str):
            raise P0ActualAuthorityBridgeError("keyless manifest child reference is invalid")
        role = child["role"]
        if role in child_by_role:
            raise P0ActualAuthorityBridgeError("keyless manifest child roles must be unique")
        child_by_role[role] = child
    expected_child_paths = {
        "a_contexts": "a_contexts.jsonl",
        "a_annotation_events": "a_annotation_events.jsonl",
        "a_subject_selection_seal": "a_subject_selection_seal.json",
    }
    for role, path in expected_child_paths.items():
        child = child_by_role.get(role)
        if child is None or child.get("path") != path:
            raise P0ActualAuthorityBridgeError(
                f"keyless manifest fixed child missing or misplaced: {role}"
            )
        _sha(child.get("sha256"), f"keyless manifest {role} child sha256")

    observed = packet_receipt["observed_counts"]
    credited = packet_receipt["credited_counts"]
    if not isinstance(observed, Mapping) or not isinstance(credited, Mapping):
        raise P0ActualAuthorityBridgeError("packet count projections must be objects")
    source_count = observed.get("selected_source_claim_count")
    a_count = observed.get("a_context_review_count")
    if source_count != 40 or a_count != 20:
        raise P0ActualAuthorityBridgeError("bridge requires observed packet 40+20")
    if credited != {
        "actual_source_claim_count": 0,
        "actual_a_context_review_count": 0,
    } or keyless_manifest["credited_counts"] != credited:
        raise P0ActualAuthorityBridgeError("bridge input credited counts must remain zero")
    if keyless_manifest["observed_counts"] != observed:
        raise P0ActualAuthorityBridgeError("packet observed projection mismatch")
    if (
        a_event_receipt["a_context_row_count"] != 20
        or a_event_receipt["a_event_row_count"] < 20
        or a_event_receipt["head_count"] != 20
        or a_event_receipt["credited_actual_a_context_review_count"] != 0
    ):
        raise P0ActualAuthorityBridgeError(
            "A event receipt must preserve observed 20 and credited zero"
        )
    for field in (
        "canonical_input_bytes_verified",
        "a_event_hash_chains_verified",
        "latest_event_projection_verified",
        "a_subject_selection_seal_verified",
    ):
        if a_event_receipt[field] is not True:
            raise P0ActualAuthorityBridgeError(
                f"A event receipt structural projection must be true: {field}"
            )
    for field in (
        "filesystem_handle_trust_verified",
        "durable_predecessor_verified",
        "annotation_append_only_verified",
        "owner_authority_verified",
        "runtime_noninterference_verified",
        "actual_authority_granted",
        "production_approval",
        "full_scan_approval",
        "p0_phase_exit",
        "action_applied",
    ):
        if a_event_receipt[field] is not False:
            raise P0ActualAuthorityBridgeError(
                f"A event receipt authority projection must remain false: {field}"
            )
    if a_event_receipt["operational_effect"] != OPERATIONAL_EFFECT:
        raise P0ActualAuthorityBridgeError("A event receipt must remain no-write")
    nested_a_context_receipt = a_event_receipt["a_context_receipt"]
    if not isinstance(nested_a_context_receipt, Mapping):
        raise P0ActualAuthorityBridgeError("A context receipt must be an object")
    _receipt_hash(nested_a_context_receipt, "A context receipt")
    if (
        nested_a_context_receipt["receipt_sha256"]
        != a_event_receipt["a_context_receipt_sha256"]
    ):
        raise P0ActualAuthorityBridgeError("A context receipt projection mismatch")
    packet_a_context_receipt_digest = canonical_sha256(nested_a_context_receipt)

    bindings = {
        "owner key": provenance["key_id"] == terminal["key_id"] == owner_anchor["key_id"] == owner_authorization["key_id"],
        "owner anchor": provenance["owner_anchor_sha256"] == terminal["owner_anchor_sha256"] == owner_anchor["artifact_sha256"] == owner_authorization["owner_anchor_sha256"] == authority_final_attestation["owner_anchor_sha256"],
        "owner authorization": provenance["owner_authorization_sha256"] == terminal["owner_authorization_sha256"] == owner_authorization["artifact_sha256"] == authority_final_attestation["owner_authorization_sha256"],
        "launch": provenance["launch_sha256"] == terminal["launch_sha256"] == launch["artifact_sha256"] == owner_authorization["launch_sha256"] == parser_receipt["launch_sha256"] == route_receipt["parser_launch_sha256"] == authority_final_attestation["launch_sha256"],
        "parser manifest": provenance["expected_parser_manifest_sha256"] == route_receipt["parser_manifest_sha256"],
        "parser version": provenance["expected_parser_version"] == route_receipt["parser_version"],
        "parser receipt": terminal["parser_receipt_sha256"] == parser_sha == keyless_manifest["parser_receipt_sha256"] == authority_manifest["parser_receipt_sha256"] == authority_final_attestation["parser_receipt_sha256"],
        "parser capture": route_receipt["parser_capture_manifest_sha256"] == parser_receipt["capture_manifest_sha256"],
        "packet route": keyless_manifest["route_receipt_sha256"] == route_sha,
        "packet receipt": packet_receipt["manifest_artifact_sha256"] == packet_artifact_sha and packet_receipt["route_receipt_sha256"] == route_sha and packet_receipt["parser_receipt_sha256"] == parser_sha,
        "packet provenance": packet_receipt["source_input_plan_sha256"] == route_receipt["source_input_plan_sha256"] and packet_receipt["sampling_frame_sha256"] == route_receipt["sampling_frame_sha256"] and packet_receipt["route_parser_manifest_sha256"] == route_receipt["parser_manifest_sha256"] == provenance["expected_parser_manifest_sha256"] and packet_receipt["route_parser_version"] == route_receipt["parser_version"] == provenance["expected_parser_version"] and packet_receipt["route_parser_launch_sha256"] == route_receipt["parser_launch_sha256"] and packet_receipt["route_parser_capture_manifest_sha256"] == route_receipt["parser_capture_manifest_sha256"],
        "packet terminal": terminal["keyless_manifest_file_sha256"] == packet_file_sha and terminal["keyless_manifest_artifact_sha256"] == packet_artifact_sha and terminal["packet_receipt_sha256"] == packet_receipt_sha and terminal["route_receipt_sha256"] == route_sha,
        "A context receipt": keyless_manifest["a_context_receipt_sha256"] == packet_receipt["a_context_receipt_sha256"] == packet_a_context_receipt_digest and a_event_receipt["a_context_receipt_sha256"] == nested_a_context_receipt["receipt_sha256"],
        "A subject seal": keyless_manifest["a_subject_selection_seal_sha256"] == packet_receipt["a_subject_selection_seal_sha256"] == a_event_receipt["a_subject_selection_seal_sha256"] == terminal["a_subject_selection_seal_sha256"],
        "A fixed child bytes": child_by_role["a_contexts"]["sha256"] == a_event_receipt["a_context_file_sha256"] == terminal["a_context_file_sha256"] and child_by_role["a_annotation_events"]["sha256"] == a_event_receipt["a_event_file_sha256"] == terminal["a_event_file_sha256"] and child_by_role["a_subject_selection_seal"]["sha256"] == a_event_receipt["a_subject_selection_seal_file_sha256"],
        "A event receipt": terminal["a_event_bytes_receipt_sha256"] == a_event_receipt_sha,
        "Windows composite": terminal["windows_packet_validation_receipt_sha256"] == windows_receipt_sha and terminal["windows_expected_manifest_sha256"] == packet_file_sha and terminal["windows_root_final_path"] == root_final_path and terminal["windows_root_volume_serial"] == root_volume_serial and terminal["windows_root_file_id"] == root_file_id,
        "authority manifest": authority_final_attestation["manifest_sha256"] == authority_manifest_sha == authority_foundation_receipt["manifest_sha256"] == terminal["authority_manifest_sha256"],
        "authority final": authority_foundation_receipt["final_attestation_sha256"] == authority_final_sha == terminal["authority_final_attestation_sha256"],
        "authority receipt": terminal["authority_foundation_receipt_sha256"] == authority_receipt_sha,
        "event file": event_bytes_receipt["event_file_sha256"] == authority_final_attestation["event_file_sha256"] == terminal["event_file_sha256"],
        "event receipt": terminal["event_bytes_receipt_sha256"] == event_receipt_sha,
        "provenance": terminal["parser_provenance_authorization_sha256"] == provenance["artifact_sha256"],
        "counts": terminal["actual_source_claim_count"] == source_count and terminal["actual_a_context_review_count"] == a_count,
    }
    expected_capture = provenance["expected_capture_manifest_sha256"]
    if expected_capture is not None:
        bindings["expected capture manifest"] = expected_capture == parser_receipt["capture_manifest_sha256"]
    expected_registry = provenance["expected_input_registry_sha256"]
    if expected_registry is not None:
        bindings["expected input registry"] = expected_registry == parser_receipt["input_registry_sha256"] == route_receipt["captured_source_registry_sha256"]
    _must_equal(bindings)

    if expected_authority_origin == authority_contract.ACTUAL_ORIGIN:
        if parser_receipt["runtime_status"] != "COMPLETE" or route_receipt["route_accounting_packet_complete"] is not True or packet_receipt["route_accounting_packet_complete"] is not True:
            raise P0ActualAuthorityBridgeError("actual bridge requires complete parser route")
        if (
            authority_manifest["actual_source_claim_count"],
            authority_manifest["actual_a_context_review_count"],
            authority_final_attestation["actual_source_claim_count"],
            authority_final_attestation["actual_a_context_review_count"],
        ) != (40, 20, 40, 20):
            raise P0ActualAuthorityBridgeError("actual authority artifacts must project observed 40+20")
    else:
        if (
            authority_manifest["actual_source_claim_count"],
            authority_manifest["actual_a_context_review_count"],
            authority_final_attestation["actual_source_claim_count"],
            authority_final_attestation["actual_a_context_review_count"],
        ) != (0, 0, 0, 0):
            raise P0ActualAuthorityBridgeError("example authority artifacts must keep counts zero")

    _input_authority_flags_must_be_false(
        route_receipt,
        keyless_manifest,
        packet_receipt,
        authority_manifest,
        authority_foundation_receipt,
        event_bytes_receipt,
    )
    if authority_foundation_receipt["actual_source_claim_count"] != 0 or authority_foundation_receipt["actual_a_context_review_count"] != 0:
        raise P0ActualAuthorityBridgeError("foundation receipt cannot credit actual counts")

    launch_created = _timestamp(launch["created_at"], "launch.created_at")
    auth_issued = _timestamp(owner_authorization["issued_at"], "owner_authorization.issued_at")
    auth_not_before = _timestamp(owner_authorization["not_before"], "owner_authorization.not_before")
    auth_expires = _timestamp(owner_authorization["expires_at"], "owner_authorization.expires_at")
    provenance_issued = _timestamp(provenance["issued_at"], "provenance.issued_at")
    provenance_not_before = _timestamp(provenance["not_before"], "provenance.not_before")
    provenance_expires = _timestamp(provenance["expires_at"], "provenance.expires_at")
    final_issued = _timestamp(authority_final_attestation["issued_at"], "final_attestation.issued_at")
    terminal_issued = _timestamp(terminal["issued_at"], "terminal.issued_at")
    if not (
        launch_created <= auth_issued <= provenance_issued <= provenance_not_before
        and auth_not_before <= provenance_not_before
        and provenance_expires <= auth_expires
        and final_issued <= terminal_issued < provenance_expires
    ):
        raise P0ActualAuthorityBridgeError("authority bridge chronology/expiry mismatch")
    capture_started = launch["capture_started_at"]
    if capture_started is not None:
        capture_time = _timestamp(capture_started, "launch.capture_started_at")
        if not (provenance_not_before <= capture_time < provenance_expires):
            raise P0ActualAuthorityBridgeError("capture is outside provenance window")
    if parser_receipt["runtime_status"] != "NOT_RUN":
        completed = _timestamp(parser_receipt["completed_at"], "parser.completed_at")
        packet_created = _timestamp(keyless_manifest["created_at"], "keyless_manifest.created_at")
        if completed >= packet_created:
            raise P0ActualAuthorityBridgeError("packet manifest must follow parser completion")
        finalized_at = authority_manifest["finalized_at"]
        if finalized_at is None:
            raise P0ActualAuthorityBridgeError("terminal authority manifest requires finalized_at")
        finalized = _timestamp(finalized_at, "authority_manifest.finalized_at")
        if packet_created > finalized or finalized > final_issued:
            raise P0ActualAuthorityBridgeError("packet/authority finalization chronology mismatch")

    material = {
        "schema_version": BRIDGE_RECEIPT_SCHEMA,
        "record_origin": expected_authority_origin,
        "parser_provenance_authorization_sha256": provenance["artifact_sha256"],
        "terminal_bridge_attestation_sha256": terminal["artifact_sha256"],
        "keyless_manifest_file_sha256": packet_file_sha,
        "keyless_manifest_artifact_sha256": packet_artifact_sha,
        "packet_receipt_sha256": packet_receipt_sha,
        "route_receipt_sha256": route_sha,
        "parser_receipt_sha256": parser_sha,
        "authority_manifest_sha256": authority_manifest_sha,
        "authority_final_attestation_sha256": authority_final_sha,
        "authority_foundation_receipt_sha256": authority_receipt_sha,
        "event_bytes_receipt_sha256": event_receipt_sha,
        "event_file_sha256": event_bytes_receipt["event_file_sha256"],
        "a_event_bytes_receipt_sha256": a_event_receipt_sha,
        "a_context_file_sha256": a_event_receipt["a_context_file_sha256"],
        "a_event_file_sha256": a_event_receipt["a_event_file_sha256"],
        "a_subject_selection_seal_sha256": a_event_receipt[
            "a_subject_selection_seal_sha256"
        ],
        "a_context_receipt_sha256": a_event_receipt["a_context_receipt_sha256"],
        "packet_a_context_receipt_digest_sha256": packet_a_context_receipt_digest,
        "windows_packet_validation_receipt_sha256": windows_receipt_sha,
        "windows_expected_manifest_sha256": packet_file_sha,
        "windows_root_final_path": root_final_path,
        "windows_root_volume_serial": root_volume_serial,
        "windows_root_file_id": root_file_id,
        "filesystem_handle_binding_verified": False,
        "presented_filesystem_handle_binding_consistent": True,
        "route_parser_manifest_sha256": route_receipt["parser_manifest_sha256"],
        "route_parser_version": route_receipt["parser_version"],
        "parser_provenance_signature_math_valid": provenance_math_valid,
        "terminal_bridge_signature_math_valid": terminal_math_valid,
        "binding_scope": "STRUCTURAL_PRESENTED_RECEIPT_BINDINGS_ONLY",
        "presented_receipt_cross_bindings_verified": True,
        "underlying_validator_execution_verified": False,
        "untrusted_observation": True,
        "observed_counts": {
            "actual_source_claim_count": 40,
            "actual_a_context_review_count": 20,
        },
        "credited_counts": {
            "actual_source_claim_count": 0,
            "actual_a_context_review_count": 0,
        },
        "external_anchor_trust_verified": False,
        "external_root_identity_pin_verified": False,
        "filesystem_handle_trust_verified": False,
        "os_write_deny_verified": False,
        "runtime_noninterference_verified": False,
        "owner_authority_verified": False,
        "actual_authority_granted": False,
        "production_approval": False,
        "full_scan_approval": False,
        "p0_phase_exit": False,
        "action_applied": False,
        "operational_effect": OPERATIONAL_EFFECT,
        "gate_status": "NO_GO_ACTUAL_P0_AUTHORITY_NOT_VERIFIED",
    }
    return {**material, "receipt_sha256": canonical_sha256(material)}


__all__ = [
    "AUTHORITY_SCOPE",
    "BRIDGE_RECEIPT_SCHEMA",
    "PARSER_PROVENANCE_AUTHORIZATION_SCHEMA",
    "PARSER_PROVENANCE_DECISION",
    "PARSER_PROVENANCE_DOMAIN",
    "P0ActualAuthorityBridgeError",
    "TERMINAL_BRIDGE_ATTESTATION_SCHEMA",
    "TERMINAL_BRIDGE_DECISION",
    "TERMINAL_BRIDGE_DOMAIN",
    "canonical_bytes",
    "canonical_sha256",
    "sign_parser_provenance_authorization",
    "sign_terminal_bridge_attestation",
    "validate_authority_bridge_bundle",
    "validate_parser_provenance_authorization",
    "validate_terminal_bridge_attestation",
    "with_artifact_hash",
]
