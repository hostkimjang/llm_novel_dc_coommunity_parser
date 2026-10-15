"""Pre-capture owner/root supplement for the actual-P0 shadow pilot.

This module is a one-way supplement.  It binds an owner signature to the
existing authority-v2 launch/authorization hashes, fixed Windows root
identities, parser provenance, and protection requirements without modifying
or upgrading any authority-v2 artifact.

Successful validation proves only schema integrity and (when a key is
supplied) detached HMAC mathematics.  A caller-supplied key is never evidence
that the key came from an external owner trust store.  Consequently every
receipt remains zero-credit and NO-GO until separately implemented external
trust, revocation, replay, root-handle, watch, and OS write-deny verifiers are
bound at runtime.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import hmac
import json
import re
from typing import Any, Mapping

from . import p0_actual_authority_contract as authority_contract
from . import p0_actual_packet_contract as packet_contract


PREAUTHORIZATION_SCHEMA = "p0_actual_owner_capture_root_preauthorization_v1"
PREAUTHORIZATION_RECEIPT_SCHEMA = (
    "p0_actual_owner_capture_root_preauthorization_receipt_v1"
)
PREAUTHORIZATION_DOMAIN = (
    "llm-novel-dc-community-parser/"
    "p0-actual-owner-capture-root-preauthorization/v1"
)
PREAUTHORIZATION_DECISION = "AUTHORIZE_FIXED_ROOT_P0_ACTUAL_SHADOW_CAPTURE"

ACTUAL_ORIGIN = authority_contract.ACTUAL_ORIGIN
EXAMPLE_ORIGIN = authority_contract.EXAMPLE_ORIGIN
AUTHORITY_SCOPE = authority_contract.AUTHORITY_SCOPE
OPERATIONAL_EFFECT = authority_contract.OPERATIONAL_EFFECT
REQUIRED_WATCH_CATEGORIES = authority_contract.REQUIRED_WATCH_CATEGORIES

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_FILE_ID_128 = re.compile(r"^[0-9a-f]{32}$")
_ASCII_DECIMAL = re.compile(r"^(?:0|[1-9][0-9]*)$")
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")
_VOLUME_GUID_PATH = re.compile(
    r"^(\\\\\?\\Volume\{[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-"
    r"[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}\})(\\.*)$"
)

FIXED_MEMBER_CONTRACT = (
    {
        "role": "packet_manifest",
        "path": packet_contract.PACKET_MANIFEST_FILENAME,
        "media_type": "application/json",
    },
    *(
        {"role": role, "path": path, "media_type": media_type}
        for role, path, media_type in packet_contract.CHILD_FILES
    ),
)
if len(FIXED_MEMBER_CONTRACT) != 14:  # manifest 1 + packet child 13
    raise RuntimeError("P0 packet v1 fixed member contract must contain 14 members")


class P0ActualOwnerRootPreauthorizationError(ValueError):
    """Raised when the one-way preauthorization supplement fails closed."""


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


FIXED_MEMBER_CONTRACT_SHA256 = canonical_sha256(FIXED_MEMBER_CONTRACT)


def with_artifact_hash(value: Mapping[str, Any]) -> dict[str, Any]:
    material = dict(value)
    material.pop("artifact_sha256", None)
    return {**material, "artifact_sha256": canonical_sha256(material)}


def _strict(value: Any, fields: frozenset[str], label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise P0ActualOwnerRootPreauthorizationError(f"{label} must be an object")
    keys = frozenset(value)
    if keys != fields:
        raise P0ActualOwnerRootPreauthorizationError(
            f"{label} fields mismatch: missing={sorted(fields - keys)}, "
            f"extra={sorted(keys - fields)}"
        )
    return dict(value)


def _identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or _SAFE_ID.fullmatch(value) is None:
        raise P0ActualOwnerRootPreauthorizationError(f"{label} is invalid")
    return value


def _text(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or len(value) > 256
        or any(ord(char) < 32 for char in value)
    ):
        raise P0ActualOwnerRootPreauthorizationError(
            f"{label} must be canonical nonempty text"
        )
    return value


def _sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise P0ActualOwnerRootPreauthorizationError(
            f"{label} must be lowercase sha256"
        )
    return value


def _timestamp(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise P0ActualOwnerRootPreauthorizationError(
            f"{label} must be canonical RFC3339 UTC"
        )
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise P0ActualOwnerRootPreauthorizationError(
            f"{label} must be canonical RFC3339 UTC"
        ) from exc
    if parsed.isoformat().replace("+00:00", "Z") != value:
        raise P0ActualOwnerRootPreauthorizationError(
            f"{label} must be canonical RFC3339 UTC"
        )
    return parsed


def _positive_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise P0ActualOwnerRootPreauthorizationError(
            f"{label} must be a positive integer"
        )
    return value


def _relative_root(value: Any, label: str) -> str:
    text = _text(value, label).replace("\\", "/")
    parts = text.split("/")
    if any(
        part in {"", ".", ".."}
        or ":" in part
        or part.rstrip(" .") != part
        for part in parts
    ):
        raise P0ActualOwnerRootPreauthorizationError(
            f"{label} must be a canonical contained relative path"
        )
    return text


def _canonical_volume_path(value: Any, label: str) -> str:
    text = _text(value, label)
    if "/" in text:
        raise P0ActualOwnerRootPreauthorizationError(
            f"{label} must use Windows volume-GUID separators"
        )
    match = _VOLUME_GUID_PATH.fullmatch(text)
    if match is None:
        raise P0ActualOwnerRootPreauthorizationError(
            f"{label} must be a final volume-GUID descendant path"
        )
    tail = match.group(2)
    parts = tail[1:].split("\\")
    if any(
        part in {"", ".", ".."}
        or ":" in part
        or part.rstrip(" .") != part
        for part in parts
    ):
        raise P0ActualOwnerRootPreauthorizationError(
            f"{label} contains a noncanonical path component"
        )
    return text.casefold()


_ROOT_FIELDS = frozenset(
    {
        "root_id",
        "final_volume_guid_path",
        "volume_serial_decimal",
        "file_id_128_hex",
        "access_intent",
    }
)


def _validate_root(value: Any, *, packet: bool, label: str) -> dict[str, Any]:
    row = _strict(value, _ROOT_FIELDS, label)
    _identifier(row["root_id"], f"{label}.root_id")
    normalized_path = _canonical_volume_path(
        row["final_volume_guid_path"], f"{label}.final_volume_guid_path"
    )
    serial = row["volume_serial_decimal"]
    if (
        not isinstance(serial, str)
        or _ASCII_DECIMAL.fullmatch(serial) is None
        or not 0 <= int(serial) < 2**64
    ):
        raise P0ActualOwnerRootPreauthorizationError(
            f"{label}.volume_serial_decimal is invalid"
        )
    file_id = row["file_id_128_hex"]
    if not isinstance(file_id, str) or _FILE_ID_128.fullmatch(file_id) is None:
        raise P0ActualOwnerRootPreauthorizationError(
            f"{label}.file_id_128_hex is invalid"
        )
    expected_intent = "WRITE_RUN_OUTPUT_ONLY" if packet else "READ_ONLY_PROTECTED"
    if row["access_intent"] != expected_intent:
        raise P0ActualOwnerRootPreauthorizationError(
            f"{label}.access_intent must be {expected_intent}"
        )
    return {
        **row,
        "_normalized_path": normalized_path,
        "_identity": (str(int(serial)), file_id),
    }


def _paths_overlap(left: str, right: str) -> bool:
    left = left.rstrip("\\")
    right = right.rstrip("\\")
    return left == right or left.startswith(right + "\\") or right.startswith(
        left + "\\"
    )


_PROVENANCE_FIELDS = frozenset(
    {
        "parser_receipt_schema",
        "parser_manifest_sha256",
        "parser_version",
        "capture_manifest_sha256",
        "input_registry_sha256",
        "source_input_plan_sha256",
        "sampling_frame_sha256",
        "packet_manifest_schema",
        "packet_fixed_member_contract_sha256",
    }
)


def _validate_provenance(value: Any) -> dict[str, Any]:
    row = _strict(value, _PROVENANCE_FIELDS, "expected provenance")
    if row["parser_receipt_schema"] != authority_contract.PARSER_RECEIPT_SCHEMA:
        raise P0ActualOwnerRootPreauthorizationError(
            "expected parser receipt schema mismatch"
        )
    if row["packet_manifest_schema"] != packet_contract.PACKET_MANIFEST_SCHEMA:
        raise P0ActualOwnerRootPreauthorizationError(
            "expected packet manifest schema mismatch"
        )
    for field in (
        "parser_manifest_sha256",
        "capture_manifest_sha256",
        "input_registry_sha256",
        "source_input_plan_sha256",
        "sampling_frame_sha256",
        "packet_fixed_member_contract_sha256",
    ):
        _sha(row[field], f"expected_provenance.{field}")
    _text(row["parser_version"], "expected_provenance.parser_version")
    if row["packet_fixed_member_contract_sha256"] != FIXED_MEMBER_CONTRACT_SHA256:
        raise P0ActualOwnerRootPreauthorizationError(
            "fixed packet member contract mismatch"
        )
    return row


_CATEGORY_FIELDS = frozenset(
    {"category", "root_id", "relative_root", "required_min_count"}
)


_WATCH_REQUIREMENT_FIELDS = frozenset(
    {
        "pre_post_required",
        "recursive_exact_membership_required",
        "identity_per_member_required",
        "continuous_journal_or_equivalent_required",
        "overflow_or_gap_fail_closed",
        "independent_observer_required",
        "required_evidence_schema",
    }
)


_WRITE_DENY_REQUIREMENT_FIELDS = frozenset(
    {
        "os_enforcement_required",
        "protected_root_ids",
        "parser_principal_must_be_denied",
        "independent_verifier_required",
        "must_preexist_before_watch_pre",
        "must_remain_through_terminal_attestation",
        "required_evidence_schema",
    }
)


_PREAUTHORIZATION_FIELDS = frozenset(
    {
        "schema_version",
        "record_origin",
        "preauthorization_id",
        "project_id",
        "run_id",
        "parser_run_id",
        "domain",
        "algorithm",
        "key_id",
        "owner_principal_sha256",
        "owner_anchor_sha256",
        "foundation_manifest_sha256",
        "launch_sha256",
        "owner_authorization_sha256",
        "watch_spec_sha256",
        "expected_provenance",
        "allowed_packet_root",
        "protected_roots",
        "category_root_map",
        "watch_requirements",
        "write_deny_requirements",
        "issued_at",
        "not_before",
        "expires_at",
        "nonce",
        "single_use",
        "authority_scope",
        "decision",
        "public_apply",
        "central_slang_db_write",
        "publication_wal_write",
        "production_approval",
        "full_scan_approval",
        "preauthorization_signature_sha256",
        "verification_status",
        "action_applied",
        "operational_effect",
        "artifact_sha256",
    }
)


def preauthorization_signature_material(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in row.items()
        if key not in {"preauthorization_signature_sha256", "artifact_sha256"}
    }


def sign_preauthorization(row: Mapping[str, Any], key: bytes) -> str:
    if not isinstance(key, bytes) or len(key) < 32:
        raise P0ActualOwnerRootPreauthorizationError(
            "owner HMAC key must be at least 32 bytes"
        )
    return hmac.new(
        key,
        canonical_bytes(preauthorization_signature_material(row)),
        hashlib.sha256,
    ).hexdigest()


def _all_true_requirements(row: Mapping[str, Any], fields: tuple[str, ...], label: str) -> None:
    for field in fields:
        if row[field] is not True:
            raise P0ActualOwnerRootPreauthorizationError(
                f"{label}.{field} must be true"
            )


def validate_owner_root_preauthorization(
    value: Any,
    expected_origin: str,
    *,
    key: bytes | None = None,
    expected_owner_anchor_sha256: str | None = None,
    observed_at: str | None = None,
) -> dict[str, Any]:
    """Validate signed structure/HMAC math and return a permanent NO-GO receipt.

    ``key`` and ``expected_owner_anchor_sha256`` are caller-presented values.
    Matching them cannot establish an external trust-store, revocation, or
    replay decision and therefore cannot grant authority or credit.
    """

    row = _strict(value, _PREAUTHORIZATION_FIELDS, "owner root preauthorization")
    if row["schema_version"] != PREAUTHORIZATION_SCHEMA:
        raise P0ActualOwnerRootPreauthorizationError("preauthorization schema mismatch")
    if expected_origin not in {ACTUAL_ORIGIN, EXAMPLE_ORIGIN}:
        raise P0ActualOwnerRootPreauthorizationError("unsupported record origin")
    if row["record_origin"] != expected_origin:
        raise P0ActualOwnerRootPreauthorizationError("record origin mismatch")
    for field in (
        "preauthorization_id",
        "project_id",
        "run_id",
        "parser_run_id",
        "key_id",
        "nonce",
    ):
        _identifier(row[field], field)
    if row["domain"] != PREAUTHORIZATION_DOMAIN or row["algorithm"] != "HMAC-SHA256":
        raise P0ActualOwnerRootPreauthorizationError(
            "preauthorization domain/algorithm mismatch"
        )
    for field in (
        "owner_principal_sha256",
        "owner_anchor_sha256",
        "foundation_manifest_sha256",
        "launch_sha256",
        "owner_authorization_sha256",
        "watch_spec_sha256",
    ):
        _sha(row[field], field)
    provenance = _validate_provenance(row["expected_provenance"])

    packet_root = _validate_root(
        row["allowed_packet_root"], packet=True, label="allowed packet root"
    )
    protected_values = row["protected_roots"]
    if not isinstance(protected_values, list) or not protected_values:
        raise P0ActualOwnerRootPreauthorizationError(
            "protected_roots must be a nonempty list"
        )
    protected = [
        _validate_root(value, packet=False, label=f"protected root {index}")
        for index, value in enumerate(protected_values)
    ]
    root_ids = [value["root_id"] for value in protected]
    if root_ids != sorted(root_ids) or len(set(root_ids)) != len(root_ids):
        raise P0ActualOwnerRootPreauthorizationError(
            "protected roots must have unique canonically ordered root IDs"
        )
    if packet_root["root_id"] in set(root_ids):
        raise P0ActualOwnerRootPreauthorizationError(
            "packet root ID must differ from protected root IDs"
        )
    all_roots = [packet_root, *protected]
    for index, left in enumerate(all_roots):
        for right in all_roots[index + 1 :]:
            if left["_identity"] == right["_identity"]:
                raise P0ActualOwnerRootPreauthorizationError(
                    "packet/protected root identities must be unique"
                )
            if _paths_overlap(left["_normalized_path"], right["_normalized_path"]):
                raise P0ActualOwnerRootPreauthorizationError(
                    "packet/protected root paths must not overlap"
                )

    category_values = row["category_root_map"]
    if not isinstance(category_values, list):
        raise P0ActualOwnerRootPreauthorizationError(
            "category_root_map must be a list"
        )
    categories: list[dict[str, Any]] = []
    for value in category_values:
        category = _strict(value, _CATEGORY_FIELDS, "category root mapping")
        _text(category["category"], "category")
        _identifier(category["root_id"], "category.root_id")
        _relative_root(category["relative_root"], "category.relative_root")
        _positive_int(category["required_min_count"], "required_min_count")
        if category["root_id"] not in set(root_ids):
            raise P0ActualOwnerRootPreauthorizationError(
                "category mapping references an unknown protected root"
            )
        categories.append(category)
    if [value["category"] for value in categories] != list(
        REQUIRED_WATCH_CATEGORIES
    ):
        raise P0ActualOwnerRootPreauthorizationError(
            "category map must contain the exact ordered protected category set"
        )
    effective_roots = [
        "\\".join(
            (
                next(
                    root["_normalized_path"].rstrip("\\")
                    for root in protected
                    if root["root_id"] == category["root_id"]
                ),
                category["relative_root"].replace("/", "\\").casefold(),
            )
        )
        for category in categories
    ]
    for index, left in enumerate(effective_roots):
        if any(_paths_overlap(left, right) for right in effective_roots[index + 1 :]):
            raise P0ActualOwnerRootPreauthorizationError(
                "category effective roots must be unique and non-overlapping"
            )

    watch = _strict(
        row["watch_requirements"],
        _WATCH_REQUIREMENT_FIELDS,
        "watch requirements",
    )
    _all_true_requirements(
        watch,
        (
            "pre_post_required",
            "recursive_exact_membership_required",
            "identity_per_member_required",
            "continuous_journal_or_equivalent_required",
            "overflow_or_gap_fail_closed",
            "independent_observer_required",
        ),
        "watch_requirements",
    )
    _identifier(watch["required_evidence_schema"], "watch required evidence schema")

    write_deny = _strict(
        row["write_deny_requirements"],
        _WRITE_DENY_REQUIREMENT_FIELDS,
        "write-deny requirements",
    )
    _all_true_requirements(
        write_deny,
        (
            "os_enforcement_required",
            "parser_principal_must_be_denied",
            "independent_verifier_required",
            "must_preexist_before_watch_pre",
            "must_remain_through_terminal_attestation",
        ),
        "write_deny_requirements",
    )
    if write_deny["protected_root_ids"] != root_ids:
        raise P0ActualOwnerRootPreauthorizationError(
            "write-deny protected root IDs must exactly match protected roots"
        )
    _identifier(
        write_deny["required_evidence_schema"],
        "write-deny required evidence schema",
    )

    issued = _timestamp(row["issued_at"], "issued_at")
    not_before = _timestamp(row["not_before"], "not_before")
    expires = _timestamp(row["expires_at"], "expires_at")
    if not (issued <= not_before < expires):
        raise P0ActualOwnerRootPreauthorizationError(
            "preauthorization validity interval is invalid"
        )
    if observed_at is not None:
        observed = _timestamp(observed_at, "observed_at")
        if not (not_before <= observed < expires):
            raise P0ActualOwnerRootPreauthorizationError(
                "preauthorization is outside its presented observation window"
            )
    if row["single_use"] is not True:
        raise P0ActualOwnerRootPreauthorizationError(
            "preauthorization must be single-use"
        )
    if row["authority_scope"] != AUTHORITY_SCOPE or row["decision"] != PREAUTHORIZATION_DECISION:
        raise P0ActualOwnerRootPreauthorizationError(
            "preauthorization decision/scope mismatch"
        )
    for field in (
        "public_apply",
        "central_slang_db_write",
        "publication_wal_write",
        "production_approval",
        "full_scan_approval",
        "action_applied",
    ):
        if row[field] is not False:
            raise P0ActualOwnerRootPreauthorizationError(
                f"preauthorization capability must remain false: {field}"
            )
    if row["operational_effect"] != OPERATIONAL_EFFECT:
        raise P0ActualOwnerRootPreauthorizationError(
            "preauthorization must remain shadow-only"
        )

    signature = row["preauthorization_signature_sha256"]
    if signature is not None:
        _sha(signature, "preauthorization_signature_sha256")
    status = row["verification_status"]
    if expected_origin == ACTUAL_ORIGIN:
        if signature is None or status != "DETACHED_SIGNATURE_PRESENT_UNVERIFIED":
            raise P0ActualOwnerRootPreauthorizationError(
                "actual preauthorization requires a detached untrusted signature"
            )
    elif signature is not None or status != "EXTERNAL_KEY_ABSENT":
        raise P0ActualOwnerRootPreauthorizationError(
            "example preauthorization must remain unsigned"
        )

    stored_hash = _sha(row["artifact_sha256"], "artifact_sha256")
    material = {key_name: item for key_name, item in row.items() if key_name != "artifact_sha256"}
    if stored_hash != canonical_sha256(material):
        raise P0ActualOwnerRootPreauthorizationError(
            "preauthorization artifact hash mismatch"
        )

    signature_math_valid = False
    if key is not None:
        if expected_origin == ACTUAL_ORIGIN:
            if signature is None or not hmac.compare_digest(
                signature, sign_preauthorization(row, key)
            ):
                raise P0ActualOwnerRootPreauthorizationError(
                    "preauthorization signature mismatch"
                )
            signature_math_valid = True
        elif not isinstance(key, bytes) or len(key) < 32:
            raise P0ActualOwnerRootPreauthorizationError(
                "owner HMAC key must be at least 32 bytes"
            )

    presented_anchor_match = False
    if expected_owner_anchor_sha256 is not None:
        presented_anchor_match = (
            _sha(expected_owner_anchor_sha256, "expected_owner_anchor_sha256")
            == row["owner_anchor_sha256"]
        )
        if not presented_anchor_match:
            raise P0ActualOwnerRootPreauthorizationError(
                "presented owner anchor mismatch"
            )

    public_packet_root = {
        key_name: item
        for key_name, item in packet_root.items()
        if not key_name.startswith("_")
    }
    public_protected = [
        {
            key_name: item
            for key_name, item in root.items()
            if not key_name.startswith("_")
        }
        for root in protected
    ]
    receipt_material = {
        "schema_version": PREAUTHORIZATION_RECEIPT_SCHEMA,
        "record_origin": expected_origin,
        "preauthorization_sha256": stored_hash,
        "owner_anchor_sha256": row["owner_anchor_sha256"],
        "launch_sha256": row["launch_sha256"],
        "owner_authorization_sha256": row["owner_authorization_sha256"],
        "run_id": row["run_id"],
        "parser_run_id": row["parser_run_id"],
        "nonce": row["nonce"],
        "packet_root_projection_sha256": canonical_sha256(public_packet_root),
        "protected_root_projection_sha256": canonical_sha256(public_protected),
        "category_root_map_sha256": canonical_sha256(categories),
        "expected_provenance_sha256": canonical_sha256(provenance),
        "watch_requirements_sha256": canonical_sha256(watch),
        "write_deny_requirements_sha256": canonical_sha256(write_deny),
        "signature_math_valid": signature_math_valid,
        "presented_owner_anchor_match": presented_anchor_match,
        "presented_internal_structure_verified": True,
        "presented_observation_window_checked": observed_at is not None,
        "presented_observation_window_match": observed_at is not None,
        "filesystem_namespace_alias_resolution_verified": False,
        "category_effective_root_overlap_rejected": True,
        "external_trust_store_verified": False,
        "revocation_current_verified": False,
        "single_use_replay_consumed": False,
        "external_root_identity_pin_verified": False,
        "filesystem_handle_trust_verified": False,
        "continuous_watch_verified": False,
        "os_write_deny_verified": False,
        "runtime_noninterference_verified": False,
        "owner_authority_verified": False,
        "credited_actual_source_claim_count": 0,
        "credited_actual_a_context_review_count": 0,
        "actual_authority_granted": False,
        "production_approval": False,
        "full_scan_approval": False,
        "p0_phase_exit": False,
        "action_applied": False,
        "operational_effect": OPERATIONAL_EFFECT,
        "gate_status": "NO_GO_ACTUAL_P0_AUTHORITY_NOT_VERIFIED",
    }
    return {
        **receipt_material,
        "receipt_sha256": canonical_sha256(receipt_material),
    }


__all__ = [
    "ACTUAL_ORIGIN",
    "AUTHORITY_SCOPE",
    "EXAMPLE_ORIGIN",
    "FIXED_MEMBER_CONTRACT",
    "FIXED_MEMBER_CONTRACT_SHA256",
    "PREAUTHORIZATION_DECISION",
    "PREAUTHORIZATION_DOMAIN",
    "PREAUTHORIZATION_RECEIPT_SCHEMA",
    "PREAUTHORIZATION_SCHEMA",
    "P0ActualOwnerRootPreauthorizationError",
    "canonical_bytes",
    "canonical_sha256",
    "preauthorization_signature_material",
    "sign_preauthorization",
    "validate_owner_root_preauthorization",
    "with_artifact_hash",
]
