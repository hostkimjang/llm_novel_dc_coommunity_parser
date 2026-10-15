"""Fail-closed actual-P0 owner-authority schema foundation.

This module validates the integrity and cross-bindings of a future actual-P0
authority packet.  It deliberately cannot grant actual-P0, production, or
full-scan approval.  A real authority decision additionally requires a pinned
owner trust root outside the repository/run directory, real 40+20 reviewed
artifacts, a sealed journal predecessor, and runtime write-deny evidence.

The module is stdlib-only and intentionally imports no runtime, publication,
ledger, Slang DB, recovery, or retrieval implementation.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import hmac
import json
from pathlib import Path
import re
from types import MappingProxyType
from typing import Any, Mapping, Sequence


ANCHOR_SCHEMA = "p0_actual_external_owner_anchor_v1"
POLICY_REFS_SCHEMA = "p0_actual_policy_refs_v1"
WATCH_SPEC_SCHEMA = "p0_actual_protected_watch_spec_v1"
WATCH_SNAPSHOT_SCHEMA = "p0_actual_protected_watch_snapshot_v1"
HEAD_MAP_SCHEMA = "p0_actual_annotation_head_map_v1"
CHECKPOINT_SCHEMA = "p0_actual_annotation_checkpoint_v2"
LAUNCH_SCHEMA = "p0_actual_pilot_launch_v1"
PARSER_RECEIPT_SCHEMA = "p0_actual_parser_runtime_receipt_v2"
AUTHORIZATION_SCHEMA = "p0_actual_detached_owner_authorization_v1"
MANIFEST_SCHEMA = "p0_actual_authority_manifest_v2"
FINAL_ATTESTATION_SCHEMA = "p0_actual_post_run_owner_attestation_v1"
RECEIPT_SCHEMA = "p0_actual_authority_foundation_receipt_v2"

ACTUAL_ORIGIN = "ACTUAL_AUTHORITY_OBSERVED"
EXAMPLE_ORIGIN = "ACTUAL_AUTHORITY_SCHEMA_EXAMPLE_ONLY"
OPERATIONAL_EFFECT = "NONE_SHADOW_ONLY"
AUTHORIZATION_DOMAIN = "llm-novel-dc-community-parser/p0-actual-owner-authorization/v1"
AUTHORIZATION_DECISION = "AUTHORIZE_P0_ACTUAL_SHADOW_VALIDATION"
FINAL_ATTESTATION_DOMAIN = (
    "llm-novel-dc-community-parser/p0-actual-post-run-owner-attestation/v1"
)
FINAL_ATTESTATION_DECISION = "ATTEST_P0_ACTUAL_SHADOW_RESULT"
AUTHORITY_SCOPE = "P0_ACTUAL_PILOT_SHADOW_ONLY"

AUTHORITY_EXAMPLE_FILES_V2 = MappingProxyType(
    {
        "owner_anchor": "p0_actual_external_owner_anchor_example_v1.json",
        "policy_refs": "p0_actual_policy_refs_example_v1.json",
        "watch_spec": "p0_actual_watch_spec_example_v1.json",
        "watch_pre": "p0_actual_watch_snapshot_pre_example_v1.json",
        "watch_post": "p0_actual_watch_snapshot_post_example_v1.json",
        "predecessor_checkpoint": "p0_annotation_predecessor_checkpoint_example_v2.json",
        "predecessor_head_map": "p0_annotation_predecessor_head_map_example_v1.json",
        "current_checkpoint": "p0_annotation_current_checkpoint_example_v2.json",
        "head_map": "p0_annotation_head_map_example_v1.json",
        "launch": "p0_actual_launch_example_v1.json",
        "parser_receipt": "p0_actual_parser_runtime_receipt_example_v2.json",
        "owner_authorization": "p0_detached_owner_authorization_example_v1.json",
        "manifest": "p0_actual_authority_manifest_example_v2.json",
        "final_attestation": "p0_post_run_owner_attestation_example_v1.json",
    }
)

REQUIRED_POLICY_NAMES = (
    "ANNOTATION_GUIDELINE",
    "CANDIDATE_REGISTRY_POLICY",
    "CAPTURE_POLICY",
    "NOVELTY_REVIEW_POLICY",
    "REVIEWER_ASSIGNMENT_POLICY",
    "RIGHTS_POLICY",
    "SAMPLING_PLAN",
)
REQUIRED_WATCH_CATEGORIES = (
    "CENTRAL_SLANG_DB",
    "CHECKPOINT",
    "DECISION_LEDGER",
    "PUBLICATION_JOURNAL",
    "RECOVERY",
    "RESULT",
)

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")


class P0ActualAuthorityError(ValueError):
    """Raised when an authority schema or cross-binding fails closed."""


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


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def with_artifact_hash(value: Mapping[str, Any]) -> dict[str, Any]:
    material = dict(value)
    material.pop("artifact_sha256", None)
    return {**material, "artifact_sha256": canonical_sha256(material)}


def _strict(value: Any, fields: frozenset[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise P0ActualAuthorityError(f"{label} must be an object")
    if set(value) != fields:
        raise P0ActualAuthorityError(
            f"{label} fields mismatch: missing={sorted(fields - set(value))}, "
            f"extra={sorted(set(value) - fields)}"
        )
    return value


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise P0ActualAuthorityError(f"{field} must be canonical non-empty text")
    return value


def _identifier(value: Any, field: str) -> str:
    text = _text(value, field)
    if _SAFE_ID.fullmatch(text) is None:
        raise P0ActualAuthorityError(f"{field} must be a safe identifier")
    return text


def _sha(value: Any, field: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise P0ActualAuthorityError(f"{field} must be lowercase sha256")
    return value


def _optional_sha(value: Any, field: str) -> str | None:
    return None if value is None else _sha(value, field)


def _timestamp(value: Any, field: str) -> datetime:
    text = _text(value, field)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise P0ActualAuthorityError(f"{field} must be RFC3339") from exc
    if parsed.tzinfo is None:
        raise P0ActualAuthorityError(f"{field} must include timezone")
    return parsed


def _optional_timestamp(value: Any, field: str) -> datetime | None:
    return None if value is None else _timestamp(value, field)


def _nonnegative_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise P0ActualAuthorityError(f"{field} must be a nonnegative integer")
    return value


def _false_capabilities(row: Mapping[str, Any], label: str) -> None:
    for field in (
        "public_apply",
        "central_slang_db_write",
        "publication_wal_write",
        "production_approval",
        "full_scan_approval",
    ):
        if row[field] is not False:
            raise P0ActualAuthorityError(f"{label} must keep {field}=false")


def _origin(row: Mapping[str, Any], expected_origin: str) -> None:
    if expected_origin not in {ACTUAL_ORIGIN, EXAMPLE_ORIGIN}:
        raise P0ActualAuthorityError("unsupported authority origin")
    if row["record_origin"] != expected_origin:
        raise P0ActualAuthorityError("actual/example authority origin mismatch")


def _self_hash(row: Mapping[str, Any], label: str) -> None:
    stored = _sha(row["artifact_sha256"], "artifact_sha256")
    material = {key: value for key, value in row.items() if key != "artifact_sha256"}
    if stored != canonical_sha256(material):
        raise P0ActualAuthorityError(f"{label} artifact hash mismatch")


def _relative_path(value: Any, field: str) -> str:
    text = _text(value, field).replace("\\", "/")
    raw_parts = text.split("/")
    windows_reserved = {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{index}" for index in range(1, 10)),
        *(f"LPT{index}" for index in range(1, 10)),
    }
    if any(
        part in {"", ".", ".."}
        or ":" in part
        or part.rstrip(" .") != part
        or part.split(".", 1)[0].upper() in windows_reserved
        for part in raw_parts
    ):
        raise P0ActualAuthorityError(f"{field} must be a canonical relative path")
    path = Path(*raw_parts)
    if (
        path.is_absolute()
        or not path.parts
        or any(part in {"", ".", ".."} or ":" in part for part in path.parts)
    ):
        raise P0ActualAuthorityError(f"{field} must be a contained relative path")
    if text.startswith("//") or text.startswith("/"):
        raise P0ActualAuthorityError(f"{field} must be a contained relative path")
    return text


_ANCHOR_FIELDS = frozenset(
    {
        "schema_version",
        "record_origin",
        "anchor_id",
        "project_id",
        "owner_principal_sha256",
        "algorithm",
        "key_id",
        "key_fingerprint_sha256",
        "trust_root_location",
        "allowed_scope",
        "valid_from",
        "valid_to",
        "revocation_status",
        "action_applied",
        "operational_effect",
        "artifact_sha256",
    }
)


def validate_owner_anchor(value: Any, expected_origin: str) -> dict[str, Any]:
    row = _strict(value, _ANCHOR_FIELDS, "owner anchor")
    if row["schema_version"] != ANCHOR_SCHEMA:
        raise P0ActualAuthorityError("owner anchor schema mismatch")
    _origin(row, expected_origin)
    for field in ("anchor_id", "project_id", "key_id"):
        _identifier(row[field], field)
    _sha(row["owner_principal_sha256"], "owner_principal_sha256")
    if row["algorithm"] != "HMAC-SHA256":
        raise P0ActualAuthorityError("owner anchor algorithm mismatch")
    fingerprint = _optional_sha(row["key_fingerprint_sha256"], "key_fingerprint_sha256")
    if row["allowed_scope"] != AUTHORITY_SCOPE:
        raise P0ActualAuthorityError("owner anchor scope mismatch")
    start = _timestamp(row["valid_from"], "valid_from")
    end = _timestamp(row["valid_to"], "valid_to")
    if end <= start:
        raise P0ActualAuthorityError("owner anchor validity interval is invalid")
    if row["revocation_status"] not in {"ACTIVE", "REVOKED", "UNKNOWN"}:
        raise P0ActualAuthorityError("owner anchor revocation status is invalid")
    if expected_origin == EXAMPLE_ORIGIN:
        if (
            row["trust_root_location"] != "EXTERNAL_KEY_ABSENT_SCHEMA_EXAMPLE"
            or fingerprint is not None
            or row["revocation_status"] != "UNKNOWN"
        ):
            raise P0ActualAuthorityError("example owner anchor must remain untrusted")
    elif (
        row["trust_root_location"] != "EXTERNAL_PREPROVISIONED"
        or fingerprint is None
        or row["revocation_status"] != "ACTIVE"
    ):
        raise P0ActualAuthorityError(
            "actual owner anchor must be externally provisioned and active"
        )
    if row["action_applied"] is not False or row["operational_effect"] != OPERATIONAL_EFFECT:
        raise P0ActualAuthorityError("owner anchor foundation must be no-write")
    _self_hash(row, "owner anchor")
    return dict(row)


_POLICY_REF_FIELDS = frozenset({"logical_name", "status", "sha256"})
_POLICY_FIELDS = frozenset(
    {
        "schema_version",
        "record_origin",
        "policy_refs",
        "policy_ref_set_sha256",
        "policy_authority_verified",
        "action_applied",
        "operational_effect",
        "artifact_sha256",
    }
)


def validate_policy_refs(value: Any, expected_origin: str) -> dict[str, Any]:
    row = _strict(value, _POLICY_FIELDS, "policy refs")
    if row["schema_version"] != POLICY_REFS_SCHEMA:
        raise P0ActualAuthorityError("policy refs schema mismatch")
    _origin(row, expected_origin)
    refs = row["policy_refs"]
    if not isinstance(refs, list):
        raise P0ActualAuthorityError("policy_refs must be a list")
    parsed = []
    for value_ref in refs:
        ref = _strict(value_ref, _POLICY_REF_FIELDS, "policy ref")
        name = _text(ref["logical_name"], "logical_name")
        if ref["status"] not in {"EXAMPLE_HASH_ONLY", "EXTERNAL_AUTHORITY_VERIFIED", "MISSING"}:
            raise P0ActualAuthorityError("policy ref status is invalid")
        digest = _optional_sha(ref["sha256"], "policy ref sha256")
        if (ref["status"] == "MISSING") != (digest is None):
            raise P0ActualAuthorityError("policy ref status/hash mismatch")
        parsed.append(dict(ref))
    names = [ref["logical_name"] for ref in parsed]
    if names != list(REQUIRED_POLICY_NAMES):
        raise P0ActualAuthorityError("policy refs must contain the fixed ordered policy set")
    if _sha(row["policy_ref_set_sha256"], "policy_ref_set_sha256") != canonical_sha256(parsed):
        raise P0ActualAuthorityError("policy ref set binding mismatch")
    verified = all(ref["status"] == "EXTERNAL_AUTHORITY_VERIFIED" for ref in parsed)
    if row["policy_authority_verified"] is not verified:
        raise P0ActualAuthorityError("policy authority projection mismatch")
    if expected_origin == EXAMPLE_ORIGIN and verified:
        raise P0ActualAuthorityError("example policies cannot be authoritative")
    if row["action_applied"] is not False or row["operational_effect"] != OPERATIONAL_EFFECT:
        raise P0ActualAuthorityError("policy refs foundation must be no-write")
    _self_hash(row, "policy refs")
    return dict(row)


_WATCH_RULE_FIELDS = frozenset(
    {"category", "relative_root", "glob", "recursive", "required_min_count"}
)
_WATCH_SPEC_FIELDS = frozenset(
    {
        "schema_version",
        "record_origin",
        "watch_spec_id",
        "rules",
        "required_categories_sha256",
        "rules_sha256",
        "allowed_write_root",
        "created_at",
        "action_applied",
        "operational_effect",
        "artifact_sha256",
    }
)


def validate_watch_spec(value: Any, expected_origin: str) -> dict[str, Any]:
    row = _strict(value, _WATCH_SPEC_FIELDS, "watch spec")
    if row["schema_version"] != WATCH_SPEC_SCHEMA:
        raise P0ActualAuthorityError("watch spec schema mismatch")
    _origin(row, expected_origin)
    _identifier(row["watch_spec_id"], "watch_spec_id")
    _timestamp(row["created_at"], "created_at")
    _relative_path(row["allowed_write_root"], "allowed_write_root")
    rules = row["rules"]
    if not isinstance(rules, list):
        raise P0ActualAuthorityError("watch rules must be a list")
    parsed = []
    for value_rule in rules:
        rule = _strict(value_rule, _WATCH_RULE_FIELDS, "watch rule")
        category = _text(rule["category"], "category")
        _relative_path(rule["relative_root"], "relative_root")
        if _text(rule["glob"], "glob") != "**/*":
            raise P0ActualAuthorityError(
                "authority foundation watch glob must be the fixed recursive **/* pattern"
            )
        if rule["recursive"] is not True:
            raise P0ActualAuthorityError("authority foundation watch must be recursive")
        if _nonnegative_int(rule["required_min_count"], "required_min_count") < 1:
            raise P0ActualAuthorityError(
                "required_min_count must be positive for every protected category"
            )
        parsed.append(dict(rule))
    categories = [rule["category"] for rule in parsed]
    if categories != list(REQUIRED_WATCH_CATEGORIES):
        raise P0ActualAuthorityError("watch spec must contain the fixed ordered categories")
    if _sha(
        row["required_categories_sha256"], "required_categories_sha256"
    ) != canonical_sha256(list(REQUIRED_WATCH_CATEGORIES)):
        raise P0ActualAuthorityError("required watch category binding mismatch")
    if _sha(row["rules_sha256"], "rules_sha256") != canonical_sha256(parsed):
        raise P0ActualAuthorityError("watch rules binding mismatch")
    roots = [rule["relative_root"].replace("\\", "/").casefold() for rule in parsed]
    if len(set(roots)) != len(roots):
        raise P0ActualAuthorityError("watch rule roots must be canonically unique")
    allowed = row["allowed_write_root"].replace("\\", "/").casefold().rstrip("/")
    if any(
        allowed == root.rstrip("/")
        or allowed.startswith(root.rstrip("/") + "/")
        or root.rstrip("/").startswith(allowed + "/")
        for root in roots
    ):
        raise P0ActualAuthorityError("allowed write root must not overlap protected roots")
    if row["action_applied"] is not False or row["operational_effect"] != OPERATIONAL_EFFECT:
        raise P0ActualAuthorityError("watch spec foundation must be no-write")
    _self_hash(row, "watch spec")
    return dict(row)


_WATCH_MEMBER_FIELDS = frozenset(
    {"category", "relative_path", "entry_type", "bytes", "sha256", "identity_sha256"}
)
_WATCH_SNAPSHOT_FIELDS = frozenset(
    {
        "schema_version",
        "record_origin",
        "snapshot_id",
        "watch_spec_sha256",
        "phase",
        "collected_at",
        "collection_status",
        "members",
        "membership_sha256",
        "required_targets_present",
        "directory_membership_complete",
        "os_write_deny_verified",
        "action_applied",
        "operational_effect",
        "artifact_sha256",
    }
)


def validate_watch_snapshot(value: Any, expected_origin: str) -> dict[str, Any]:
    row = _strict(value, _WATCH_SNAPSHOT_FIELDS, "watch snapshot")
    if row["schema_version"] != WATCH_SNAPSHOT_SCHEMA:
        raise P0ActualAuthorityError("watch snapshot schema mismatch")
    _origin(row, expected_origin)
    _identifier(row["snapshot_id"], "snapshot_id")
    _sha(row["watch_spec_sha256"], "watch_spec_sha256")
    if row["phase"] not in {"PRE", "POST"}:
        raise P0ActualAuthorityError("watch snapshot phase is invalid")
    collected = _optional_timestamp(row["collected_at"], "collected_at")
    if row["collection_status"] not in {"NOT_CAPTURED", "CAPTURED"}:
        raise P0ActualAuthorityError("watch snapshot collection status is invalid")
    members = row["members"]
    if not isinstance(members, list):
        raise P0ActualAuthorityError("watch members must be a list")
    parsed = []
    for value_member in members:
        member = _strict(value_member, _WATCH_MEMBER_FIELDS, "watch member")
        if member["category"] not in REQUIRED_WATCH_CATEGORIES:
            raise P0ActualAuthorityError("watch member category is invalid")
        _relative_path(member["relative_path"], "relative_path")
        if member["entry_type"] not in {"FILE", "DIRECTORY"}:
            raise P0ActualAuthorityError("watch member entry type is invalid")
        _nonnegative_int(member["bytes"], "bytes")
        _sha(member["sha256"], "sha256")
        _sha(member["identity_sha256"], "identity_sha256")
        parsed.append(dict(member))
    if parsed != sorted(parsed, key=lambda item: (item["category"], item["relative_path"])):
        raise P0ActualAuthorityError("watch members must be canonically ordered")
    if len(
        {
            (item["category"], item["relative_path"].replace("\\", "/").casefold())
            for item in parsed
        }
    ) != len(parsed):
        raise P0ActualAuthorityError("watch members must be unique")
    if _sha(row["membership_sha256"], "membership_sha256") != canonical_sha256(parsed):
        raise P0ActualAuthorityError("watch membership binding mismatch")
    for field in (
        "required_targets_present",
        "directory_membership_complete",
        "os_write_deny_verified",
    ):
        if not isinstance(row[field], bool):
            raise P0ActualAuthorityError(f"{field} must be boolean")
    if row["os_write_deny_verified"]:
        raise P0ActualAuthorityError(
            "authority foundation cannot verify a self-declared OS write-deny witness"
        )
    if row["collection_status"] == "NOT_CAPTURED" and (collected is not None or parsed):
        raise P0ActualAuthorityError("uncaptured watch snapshot must be empty")
    if row["collection_status"] == "CAPTURED" and collected is None:
        raise P0ActualAuthorityError("captured watch snapshot requires collected_at")
    if row["required_targets_present"] and not parsed:
        raise P0ActualAuthorityError(
            "required_targets_present cannot be asserted for an empty snapshot"
        )
    if row["action_applied"] is not False or row["operational_effect"] != OPERATIONAL_EFFECT:
        raise P0ActualAuthorityError("watch snapshot foundation must be no-write")
    _self_hash(row, "watch snapshot")
    return dict(row)


_HEAD_FIELDS = frozenset(
    {
        "target_record_type",
        "target_id",
        "target_subject_sha256",
        "journal_id",
        "head_sequence",
        "head_event_id",
        "head_event_sha256",
    }
)
_HEAD_MAP_FIELDS = frozenset(
    {
        "schema_version",
        "record_origin",
        "head_map_id",
        "heads",
        "head_count",
        "head_map_sha256",
        "one_journal_per_target_structurally",
        "action_applied",
        "operational_effect",
        "artifact_sha256",
    }
)


def validate_head_map(value: Any, expected_origin: str) -> dict[str, Any]:
    row = _strict(value, _HEAD_MAP_FIELDS, "annotation head map")
    if row["schema_version"] != HEAD_MAP_SCHEMA:
        raise P0ActualAuthorityError("annotation head map schema mismatch")
    _origin(row, expected_origin)
    _identifier(row["head_map_id"], "head_map_id")
    heads = row["heads"]
    if not isinstance(heads, list):
        raise P0ActualAuthorityError("annotation heads must be a list")
    parsed = []
    for value_head in heads:
        head = _strict(value_head, _HEAD_FIELDS, "annotation head")
        for field in ("target_record_type", "target_id", "journal_id", "head_event_id"):
            _text(head[field], field)
        _sha(head["target_subject_sha256"], "target_subject_sha256")
        _sha(head["head_event_sha256"], "head_event_sha256")
        sequence = _nonnegative_int(head["head_sequence"], "head_sequence")
        if sequence < 1:
            raise P0ActualAuthorityError("head_sequence must be positive")
        parsed.append(dict(head))
    if parsed != sorted(parsed, key=lambda item: (item["target_record_type"], item["target_id"])):
        raise P0ActualAuthorityError("annotation heads must be canonically ordered")
    targets = [(item["target_record_type"], item["target_id"]) for item in parsed]
    if len(set(targets)) != len(targets):
        raise P0ActualAuthorityError("annotation target must have one head")
    if _nonnegative_int(row["head_count"], "head_count") != len(parsed):
        raise P0ActualAuthorityError("annotation head count mismatch")
    if _sha(row["head_map_sha256"], "head_map_sha256") != canonical_sha256(parsed):
        raise P0ActualAuthorityError("annotation head map binding mismatch")
    if row["one_journal_per_target_structurally"] is not True:
        raise P0ActualAuthorityError("annotation head map must prove structural uniqueness")
    if row["action_applied"] is not False or row["operational_effect"] != OPERATIONAL_EFFECT:
        raise P0ActualAuthorityError("annotation head map foundation must be no-write")
    _self_hash(row, "annotation head map")
    return dict(row)


_CHECKPOINT_FIELDS = frozenset(
    {
        "schema_version",
        "record_origin",
        "checkpoint_id",
        "checkpoint_kind",
        "previous_checkpoint_sha256",
        "event_file_sha256",
        "prefix_rows",
        "prefix_bytes",
        "prefix_sha256",
        "prefix_head_set_sha256",
        "head_map_artifact_sha256",
        "owner_sealed",
        "durable_prior_observation",
        "historical_append_only_verified",
        "created_at",
        "action_applied",
        "operational_effect",
        "artifact_sha256",
    }
)


def validate_checkpoint(value: Any, expected_origin: str) -> dict[str, Any]:
    row = _strict(value, _CHECKPOINT_FIELDS, "annotation checkpoint")
    if row["schema_version"] != CHECKPOINT_SCHEMA:
        raise P0ActualAuthorityError("annotation checkpoint schema mismatch")
    _origin(row, expected_origin)
    _identifier(row["checkpoint_id"], "checkpoint_id")
    if row["checkpoint_kind"] not in {
        "SCHEMA_EXAMPLE_RECONSTRUCTED_PREFIX",
        "OWNER_SEALED_GENESIS",
        "OWNER_SEALED_APPEND",
    }:
        raise P0ActualAuthorityError("annotation checkpoint kind is invalid")
    previous = _optional_sha(row["previous_checkpoint_sha256"], "previous_checkpoint_sha256")
    for field in (
        "event_file_sha256",
        "prefix_sha256",
        "prefix_head_set_sha256",
        "head_map_artifact_sha256",
    ):
        _sha(row[field], field)
    if row["event_file_sha256"] != row["prefix_sha256"]:
        raise P0ActualAuthorityError(
            "checkpoint event file must equal the byte-exact sealed prefix"
        )
    rows = _nonnegative_int(row["prefix_rows"], "prefix_rows")
    size = _nonnegative_int(row["prefix_bytes"], "prefix_bytes")
    if rows < 1 or size < 1:
        raise P0ActualAuthorityError("annotation checkpoint prefix must be non-empty")
    for field in ("owner_sealed", "durable_prior_observation", "historical_append_only_verified"):
        if not isinstance(row[field], bool):
            raise P0ActualAuthorityError(f"{field} must be boolean")
    _timestamp(row["created_at"], "created_at")
    if row["checkpoint_kind"] == "SCHEMA_EXAMPLE_RECONSTRUCTED_PREFIX":
        if expected_origin != EXAMPLE_ORIGIN or any(
            row[field]
            for field in ("owner_sealed", "durable_prior_observation", "historical_append_only_verified")
        ):
            raise P0ActualAuthorityError("reconstructed checkpoint cannot assert history")
    else:
        if not row["owner_sealed"] or not row["durable_prior_observation"]:
            raise P0ActualAuthorityError("actual checkpoint requires owner-sealed prior observation")
        if row["checkpoint_kind"] == "OWNER_SEALED_APPEND" and previous is None:
            raise P0ActualAuthorityError("append checkpoint requires predecessor")
    if row["historical_append_only_verified"]:
        raise P0ActualAuthorityError(
            "authority foundation cannot verify append-only history without event bytes"
        )
    if row["action_applied"] is not False or row["operational_effect"] != OPERATIONAL_EFFECT:
        raise P0ActualAuthorityError("annotation checkpoint foundation must be no-write")
    _self_hash(row, "annotation checkpoint")
    return dict(row)


_LAUNCH_FIELDS = frozenset(
    {
        "schema_version",
        "record_origin",
        "launch_id",
        "launch_status",
        "created_at",
        "capture_started_at",
        "foundation_manifest_sha256",
        "foundation_receipt_sha256",
        "owner_anchor_sha256",
        "policy_refs_sha256",
        "watch_spec_sha256",
        "predecessor_checkpoint_sha256",
        "planned_source_claim_set_sha256",
        "planned_a_context_set_sha256",
        "expected_actual_source_claims",
        "expected_actual_a_context_reviews",
        "observed_actual_source_claims",
        "observed_actual_a_context_reviews",
        "authority_scope",
        "owner_authorization_required",
        "public_apply",
        "central_slang_db_write",
        "publication_wal_write",
        "production_approval",
        "full_scan_approval",
        "action_applied",
        "operational_effect",
        "artifact_sha256",
    }
)


def validate_launch(value: Any, expected_origin: str) -> dict[str, Any]:
    row = _strict(value, _LAUNCH_FIELDS, "actual launch")
    if row["schema_version"] != LAUNCH_SCHEMA:
        raise P0ActualAuthorityError("actual launch schema mismatch")
    _origin(row, expected_origin)
    _identifier(row["launch_id"], "launch_id")
    if row["launch_status"] not in {"NOT_LAUNCHED", "SEALED_PRE_CAPTURE"}:
        raise P0ActualAuthorityError("actual launch status is invalid")
    created = _timestamp(row["created_at"], "created_at")
    started = _optional_timestamp(row["capture_started_at"], "capture_started_at")
    if started is not None and started < created:
        raise P0ActualAuthorityError("capture cannot precede launch creation")
    for field in (
        "foundation_manifest_sha256",
        "foundation_receipt_sha256",
        "owner_anchor_sha256",
        "policy_refs_sha256",
        "watch_spec_sha256",
        "predecessor_checkpoint_sha256",
        "planned_source_claim_set_sha256",
        "planned_a_context_set_sha256",
    ):
        _sha(row[field], field)
    if row["expected_actual_source_claims"] != 40 or row["expected_actual_a_context_reviews"] != 20:
        raise P0ActualAuthorityError("actual launch must preserve the fixed 40+20 target")
    for field in ("observed_actual_source_claims", "observed_actual_a_context_reviews"):
        _nonnegative_int(row[field], field)
    if expected_origin == EXAMPLE_ORIGIN and (
        row["launch_status"] != "NOT_LAUNCHED"
        or started is not None
        or row["observed_actual_source_claims"] != 0
        or row["observed_actual_a_context_reviews"] != 0
    ):
        raise P0ActualAuthorityError("authority example launch must remain unstarted")
    if row["authority_scope"] != AUTHORITY_SCOPE or row["owner_authorization_required"] is not True:
        raise P0ActualAuthorityError("actual launch authority boundary mismatch")
    _false_capabilities(row, "actual launch")
    if row["action_applied"] is not False or row["operational_effect"] != OPERATIONAL_EFFECT:
        raise P0ActualAuthorityError("actual launch foundation must be no-write")
    _self_hash(row, "actual launch")
    return dict(row)


_PARSER_FIELDS = frozenset(
    {
        "schema_version",
        "record_origin",
        "parser_run_id",
        "launch_sha256",
        "runtime_status",
        "started_at",
        "completed_at",
        "capture_manifest_sha256",
        "input_registry_sha256",
        "output_claims_sha256",
        "generic_queue_sha256",
        "input_count",
        "processed_count",
        "typed_input_count",
        "claim_row_count",
        "generic_count",
        "error_count",
        "network_deny_verified",
        "run_root_containment_verified",
        "exact_accounting_verified",
        "runtime_noninterference_verified",
        "action_applied",
        "operational_effect",
        "artifact_sha256",
    }
)


def validate_parser_receipt(value: Any, expected_origin: str) -> dict[str, Any]:
    row = _strict(value, _PARSER_FIELDS, "parser runtime receipt")
    if row["schema_version"] != PARSER_RECEIPT_SCHEMA:
        raise P0ActualAuthorityError("parser runtime receipt schema mismatch")
    _origin(row, expected_origin)
    _identifier(row["parser_run_id"], "parser_run_id")
    _sha(row["launch_sha256"], "launch_sha256")
    if row["runtime_status"] not in {"NOT_RUN", "COMPLETE", "FAILED"}:
        raise P0ActualAuthorityError("parser runtime status is invalid")
    started = _optional_timestamp(row["started_at"], "started_at")
    completed = _optional_timestamp(row["completed_at"], "completed_at")
    if row["runtime_status"] == "NOT_RUN":
        if started is not None or completed is not None:
            raise P0ActualAuthorityError("NOT_RUN parser receipt cannot carry runtime times")
    elif started is None or completed is None or completed < started:
        raise P0ActualAuthorityError(
            "terminal parser receipt requires ordered started_at/completed_at"
        )
    for field in (
        "capture_manifest_sha256",
        "input_registry_sha256",
        "output_claims_sha256",
        "generic_queue_sha256",
    ):
        _optional_sha(row[field], field)
    counts = {
        field: _nonnegative_int(row[field], field)
        for field in (
            "input_count",
            "processed_count",
            "typed_input_count",
            "claim_row_count",
            "generic_count",
            "error_count",
        )
    }
    for field in (
        "network_deny_verified",
        "run_root_containment_verified",
        "exact_accounting_verified",
        "runtime_noninterference_verified",
    ):
        if not isinstance(row[field], bool):
            raise P0ActualAuthorityError(f"{field} must be boolean")
    if row["runtime_status"] == "NOT_RUN":
        if any(counts.values()) or any(
            row[field] is not None
            for field in (
                "capture_manifest_sha256",
                "input_registry_sha256",
                "output_claims_sha256",
                "generic_queue_sha256",
            )
        ) or any(
            row[field]
            for field in (
                "network_deny_verified",
                "run_root_containment_verified",
                "exact_accounting_verified",
                "runtime_noninterference_verified",
            )
        ):
            raise P0ActualAuthorityError("NOT_RUN parser receipt must remain empty")
    else:
        if any(
            row[field] is None
            for field in (
                "capture_manifest_sha256",
                "input_registry_sha256",
                "output_claims_sha256",
                "generic_queue_sha256",
            )
        ):
            raise P0ActualAuthorityError(
                "terminal parser receipt requires all artifact hashes"
            )
        if counts["processed_count"] > counts["input_count"] or (
            counts["typed_input_count"]
            + counts["generic_count"]
            + counts["error_count"]
            != counts["processed_count"]
        ):
            raise P0ActualAuthorityError("parser exact accounting mismatch")
        if (
            counts["typed_input_count"] == 0
            and counts["claim_row_count"] != 0
        ) or (
            counts["typed_input_count"] > 0
            and counts["claim_row_count"] < counts["typed_input_count"]
        ):
            raise P0ActualAuthorityError("parser 1:N claim row accounting mismatch")
        if not all(
            row[field]
            for field in (
                "network_deny_verified",
                "run_root_containment_verified",
                "exact_accounting_verified",
            )
        ):
            raise P0ActualAuthorityError("terminal parser receipt lacks runtime witnesses")
        if row["runtime_status"] == "COMPLETE" and (
            counts["processed_count"] != counts["input_count"]
            or counts["error_count"] != 0
        ):
            raise P0ActualAuthorityError("complete parser receipt accounting mismatch")
        if row["runtime_status"] == "FAILED" and not (
            counts["error_count"] > 0
            or counts["processed_count"] < counts["input_count"]
        ):
            raise P0ActualAuthorityError(
                "failed parser receipt must preserve a failure witness"
            )
    if expected_origin == EXAMPLE_ORIGIN and row["runtime_status"] != "NOT_RUN":
        raise P0ActualAuthorityError("authority example parser must remain NOT_RUN")
    if row["action_applied"] is not False or row["operational_effect"] != OPERATIONAL_EFFECT:
        raise P0ActualAuthorityError("parser receipt foundation must be no-write")
    _self_hash(row, "parser runtime receipt")
    return dict(row)


_AUTH_FIELDS = frozenset(
    {
        "schema_version",
        "record_origin",
        "domain",
        "algorithm",
        "key_id",
        "owner_anchor_sha256",
        "launch_sha256",
        "decision",
        "authority_scope",
        "issued_at",
        "not_before",
        "expires_at",
        "nonce",
        "public_apply",
        "central_slang_db_write",
        "publication_wal_write",
        "production_approval",
        "full_scan_approval",
        "authorization_signature_sha256",
        "verification_status",
        "action_applied",
        "operational_effect",
        "artifact_sha256",
    }
)


def authorization_material(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "domain": row["domain"],
        "algorithm": row["algorithm"],
        "key_id": row["key_id"],
        "owner_anchor_sha256": row["owner_anchor_sha256"],
        "launch_sha256": row["launch_sha256"],
        "decision": row["decision"],
        "authority_scope": row["authority_scope"],
        "issued_at": row["issued_at"],
        "not_before": row["not_before"],
        "expires_at": row["expires_at"],
        "nonce": row["nonce"],
        "public_apply": row["public_apply"],
        "central_slang_db_write": row["central_slang_db_write"],
        "publication_wal_write": row["publication_wal_write"],
        "production_approval": row["production_approval"],
        "full_scan_approval": row["full_scan_approval"],
    }


def sign_authorization_material(row: Mapping[str, Any], key: bytes) -> str:
    if not isinstance(key, bytes) or len(key) < 32:
        raise P0ActualAuthorityError("owner HMAC key must be at least 32 bytes")
    return hmac.new(key, canonical_bytes(authorization_material(row)), hashlib.sha256).hexdigest()


def check_supplied_owner_key_binding(
    owner_anchor: Mapping[str, Any],
    *,
    key: bytes,
    expected_external_anchor_sha256: str,
    observed_at: str,
) -> bool:
    """Check key material against caller-supplied, pinned-anchor metadata.

    This proves only that the supplied key matches the pinned anchor metadata;
    it does not establish who provisioned the pin or grant an actual-P0 gate.
    """

    anchor = validate_owner_anchor(owner_anchor, ACTUAL_ORIGIN)
    if not isinstance(key, bytes) or len(key) < 32:
        raise P0ActualAuthorityError("owner HMAC key must be at least 32 bytes")
    if (
        _sha(expected_external_anchor_sha256, "expected_external_anchor_sha256")
        != anchor["artifact_sha256"]
    ):
        raise P0ActualAuthorityError("owner key external anchor mismatch")
    fingerprint = hashlib.sha256(key).hexdigest()
    if not hmac.compare_digest(fingerprint, anchor["key_fingerprint_sha256"]):
        raise P0ActualAuthorityError("owner key fingerprint mismatch")
    observed = _timestamp(observed_at, "observed_at")
    if not (
        _timestamp(anchor["valid_from"], "valid_from")
        <= observed
        < _timestamp(anchor["valid_to"], "valid_to")
    ):
        raise P0ActualAuthorityError("supplied owner anchor is not valid at observation")
    return True


def validate_authorization(
    value: Any,
    expected_origin: str,
    *,
    key: bytes | None = None,
    expected_external_anchor_sha256: str | None = None,
    observed_at: str | None = None,
) -> tuple[dict[str, Any], bool]:
    row = _strict(value, _AUTH_FIELDS, "owner authorization")
    if row["schema_version"] != AUTHORIZATION_SCHEMA:
        raise P0ActualAuthorityError("owner authorization schema mismatch")
    _origin(row, expected_origin)
    if row["domain"] != AUTHORIZATION_DOMAIN or row["algorithm"] != "HMAC-SHA256":
        raise P0ActualAuthorityError("owner authorization domain/algorithm mismatch")
    _identifier(row["key_id"], "key_id")
    anchor_sha = _sha(row["owner_anchor_sha256"], "owner_anchor_sha256")
    _sha(row["launch_sha256"], "launch_sha256")
    if row["decision"] != AUTHORIZATION_DECISION or row["authority_scope"] != AUTHORITY_SCOPE:
        raise P0ActualAuthorityError("owner authorization decision/scope mismatch")
    issued = _timestamp(row["issued_at"], "issued_at")
    not_before = _timestamp(row["not_before"], "not_before")
    expires = _timestamp(row["expires_at"], "expires_at")
    if not (issued <= not_before < expires):
        raise P0ActualAuthorityError("owner authorization validity interval is invalid")
    _identifier(row["nonce"], "nonce")
    _false_capabilities(row, "owner authorization")
    signature = _optional_sha(
        row["authorization_signature_sha256"], "authorization_signature_sha256"
    )
    if row["verification_status"] not in {
        "EXTERNAL_KEY_ABSENT",
        "DETACHED_SIGNATURE_PRESENT_UNVERIFIED",
    }:
        raise P0ActualAuthorityError("owner authorization verification status is invalid")
    if (signature is None) != (row["verification_status"] == "EXTERNAL_KEY_ABSENT"):
        raise P0ActualAuthorityError("owner authorization status/signature mismatch")
    if row["action_applied"] is not False or row["operational_effect"] != OPERATIONAL_EFFECT:
        raise P0ActualAuthorityError("owner authorization foundation must be no-write")
    _self_hash(row, "owner authorization")

    verified = False
    if key is not None or expected_external_anchor_sha256 is not None:
        if key is None or expected_external_anchor_sha256 is None or observed_at is None:
            raise P0ActualAuthorityError(
                "key, expected external anchor, and observed_at must be supplied together"
            )
        if expected_origin != ACTUAL_ORIGIN:
            return dict(row), False
        if _sha(expected_external_anchor_sha256, "expected_external_anchor_sha256") != anchor_sha:
            raise P0ActualAuthorityError("owner authorization external anchor mismatch")
        observed = _timestamp(observed_at, "observed_at")
        if observed < not_before or observed >= expires:
            raise P0ActualAuthorityError("owner authorization is not currently valid")
        if signature is None or not hmac.compare_digest(
            signature, sign_authorization_material(row, key)
        ):
            raise P0ActualAuthorityError("owner authorization signature mismatch")
        verified = True
    return dict(row), verified


_FINAL_ATTESTATION_FIELDS = frozenset(
    {
        "schema_version",
        "record_origin",
        "attestation_id",
        "domain",
        "algorithm",
        "key_id",
        "owner_anchor_sha256",
        "owner_authorization_sha256",
        "foundation_manifest_sha256",
        "foundation_receipt_sha256",
        "launch_sha256",
        "parser_receipt_sha256",
        "predecessor_checkpoint_sha256",
        "predecessor_head_map_sha256",
        "current_checkpoint_sha256",
        "head_map_sha256",
        "watch_spec_sha256",
        "watch_pre_sha256",
        "watch_post_sha256",
        "manifest_sha256",
        "event_file_sha256",
        "actual_source_claim_count",
        "actual_a_context_review_count",
        "decision",
        "authority_scope",
        "issued_at",
        "nonce",
        "public_apply",
        "central_slang_db_write",
        "publication_wal_write",
        "production_approval",
        "full_scan_approval",
        "attestation_signature_sha256",
        "verification_status",
        "action_applied",
        "operational_effect",
        "artifact_sha256",
    }
)


def final_attestation_material(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        field: value
        for field, value in row.items()
        if field not in {"attestation_signature_sha256", "artifact_sha256"}
    }


def sign_final_attestation_material(row: Mapping[str, Any], key: bytes) -> str:
    if not isinstance(key, bytes) or len(key) < 32:
        raise P0ActualAuthorityError("owner HMAC key must be at least 32 bytes")
    return hmac.new(
        key,
        canonical_bytes(final_attestation_material(row)),
        hashlib.sha256,
    ).hexdigest()


def validate_final_attestation(
    value: Any,
    expected_origin: str,
    *,
    key: bytes | None = None,
    expected_external_anchor_sha256: str | None = None,
) -> tuple[dict[str, Any], bool]:
    row = _strict(value, _FINAL_ATTESTATION_FIELDS, "post-run owner attestation")
    if row["schema_version"] != FINAL_ATTESTATION_SCHEMA:
        raise P0ActualAuthorityError("post-run owner attestation schema mismatch")
    _origin(row, expected_origin)
    _identifier(row["attestation_id"], "attestation_id")
    if row["domain"] != FINAL_ATTESTATION_DOMAIN or row["algorithm"] != "HMAC-SHA256":
        raise P0ActualAuthorityError("post-run owner attestation domain/algorithm mismatch")
    _identifier(row["key_id"], "key_id")
    for field in (
        "owner_anchor_sha256",
        "owner_authorization_sha256",
        "foundation_manifest_sha256",
        "foundation_receipt_sha256",
        "launch_sha256",
        "parser_receipt_sha256",
        "predecessor_checkpoint_sha256",
        "predecessor_head_map_sha256",
        "current_checkpoint_sha256",
        "head_map_sha256",
        "watch_spec_sha256",
        "watch_pre_sha256",
        "watch_post_sha256",
        "manifest_sha256",
        "event_file_sha256",
    ):
        _sha(row[field], field)
    for field in ("actual_source_claim_count", "actual_a_context_review_count"):
        _nonnegative_int(row[field], field)
    if (
        row["decision"] != FINAL_ATTESTATION_DECISION
        or row["authority_scope"] != AUTHORITY_SCOPE
    ):
        raise P0ActualAuthorityError("post-run owner attestation decision/scope mismatch")
    _timestamp(row["issued_at"], "issued_at")
    _identifier(row["nonce"], "nonce")
    _false_capabilities(row, "post-run owner attestation")
    signature = _optional_sha(
        row["attestation_signature_sha256"], "attestation_signature_sha256"
    )
    if row["verification_status"] not in {
        "EXTERNAL_KEY_ABSENT",
        "DETACHED_SIGNATURE_PRESENT_UNVERIFIED",
    }:
        raise P0ActualAuthorityError("post-run owner attestation status is invalid")
    if (signature is None) != (row["verification_status"] == "EXTERNAL_KEY_ABSENT"):
        raise P0ActualAuthorityError("post-run owner attestation status/signature mismatch")
    if expected_origin == EXAMPLE_ORIGIN and signature is not None:
        raise P0ActualAuthorityError("example post-run attestation must remain unsigned")
    if expected_origin == ACTUAL_ORIGIN and signature is None:
        raise P0ActualAuthorityError("actual post-run owner attestation requires signature")
    if row["action_applied"] is not False or row["operational_effect"] != OPERATIONAL_EFFECT:
        raise P0ActualAuthorityError("post-run owner attestation foundation must be no-write")
    _self_hash(row, "post-run owner attestation")

    verified = False
    if key is not None or expected_external_anchor_sha256 is not None:
        if key is None or expected_external_anchor_sha256 is None:
            raise P0ActualAuthorityError(
                "post-run key and expected external anchor must be supplied together"
            )
        if expected_origin != ACTUAL_ORIGIN:
            return dict(row), False
        if (
            _sha(expected_external_anchor_sha256, "expected_external_anchor_sha256")
            != row["owner_anchor_sha256"]
        ):
            raise P0ActualAuthorityError("post-run attestation external anchor mismatch")
        if signature is None or not hmac.compare_digest(
            signature, sign_final_attestation_material(row, key)
        ):
            raise P0ActualAuthorityError("post-run owner attestation signature mismatch")
        verified = True
    return dict(row), verified


_MANIFEST_FIELDS = frozenset(
    {
        "schema_version",
        "record_origin",
        "manifest_id",
        "foundation_manifest_sha256",
        "foundation_receipt_sha256",
        "owner_anchor_sha256",
        "policy_refs_sha256",
        "watch_spec_sha256",
        "watch_pre_sha256",
        "watch_post_sha256",
        "predecessor_checkpoint_sha256",
        "predecessor_head_map_sha256",
        "current_checkpoint_sha256",
        "head_map_sha256",
        "launch_sha256",
        "parser_receipt_sha256",
        "owner_authorization_sha256",
        "finalized_at",
        "actual_source_claim_count",
        "actual_a_context_review_count",
        "authority",
        "public_apply",
        "central_slang_db_write",
        "publication_wal_write",
        "production_approval",
        "full_scan_approval",
        "p0_phase_exit",
        "action_applied",
        "operational_effect",
        "artifact_sha256",
    }
)


def validate_manifest(value: Any, expected_origin: str) -> dict[str, Any]:
    row = _strict(value, _MANIFEST_FIELDS, "authority manifest")
    if row["schema_version"] != MANIFEST_SCHEMA:
        raise P0ActualAuthorityError("authority manifest schema mismatch")
    _origin(row, expected_origin)
    _identifier(row["manifest_id"], "manifest_id")
    for field in (
        "foundation_manifest_sha256",
        "foundation_receipt_sha256",
        "owner_anchor_sha256",
        "policy_refs_sha256",
        "watch_spec_sha256",
        "watch_pre_sha256",
        "watch_post_sha256",
        "predecessor_checkpoint_sha256",
        "predecessor_head_map_sha256",
        "current_checkpoint_sha256",
        "head_map_sha256",
        "launch_sha256",
        "parser_receipt_sha256",
        "owner_authorization_sha256",
    ):
        _sha(row[field], field)
    for field in ("actual_source_claim_count", "actual_a_context_review_count"):
        _nonnegative_int(row[field], field)
    finalized = _optional_timestamp(row["finalized_at"], "finalized_at")
    if expected_origin == EXAMPLE_ORIGIN and finalized is not None:
        raise P0ActualAuthorityError("authority example manifest cannot be finalized")
    if expected_origin == ACTUAL_ORIGIN and finalized is None:
        raise P0ActualAuthorityError("actual authority manifest requires finalized_at")
    if row["authority"] != "NONE_SCHEMA_FOUNDATION_ONLY":
        raise P0ActualAuthorityError("authority manifest must not self-declare authority")
    _false_capabilities(row, "authority manifest")
    if row["p0_phase_exit"] is not False:
        raise P0ActualAuthorityError("authority foundation cannot exit actual P0")
    if expected_origin == EXAMPLE_ORIGIN and (
        row["actual_source_claim_count"] != 0
        or row["actual_a_context_review_count"] != 0
    ):
        raise P0ActualAuthorityError("authority example manifest must keep actual counts zero")
    if row["action_applied"] is not False or row["operational_effect"] != OPERATIONAL_EFFECT:
        raise P0ActualAuthorityError("authority manifest foundation must be no-write")
    _self_hash(row, "authority manifest")
    return dict(row)


def validate_authority_foundation_bundle(
    *,
    owner_anchor: Mapping[str, Any],
    policy_refs: Mapping[str, Any],
    watch_spec: Mapping[str, Any],
    watch_pre: Mapping[str, Any],
    watch_post: Mapping[str, Any],
    predecessor_checkpoint: Mapping[str, Any],
    predecessor_head_map: Mapping[str, Any],
    current_checkpoint: Mapping[str, Any],
    head_map: Mapping[str, Any],
    launch: Mapping[str, Any],
    parser_receipt: Mapping[str, Any],
    owner_authorization: Mapping[str, Any],
    manifest: Mapping[str, Any],
    final_attestation: Mapping[str, Any],
    expected_origin: str,
    foundation_manifest_sha256: str,
    foundation_receipt_sha256: str,
    key: bytes | None = None,
    expected_external_anchor_sha256: str | None = None,
    observed_at: str | None = None,
) -> dict[str, Any]:
    """Validate structure/cross-bindings but never grant actual-P0 authority."""

    anchor = validate_owner_anchor(owner_anchor, expected_origin)
    policies = validate_policy_refs(policy_refs, expected_origin)
    watch = validate_watch_spec(watch_spec, expected_origin)
    pre = validate_watch_snapshot(watch_pre, expected_origin)
    post = validate_watch_snapshot(watch_post, expected_origin)
    predecessor = validate_checkpoint(predecessor_checkpoint, expected_origin)
    predecessor_heads = validate_head_map(predecessor_head_map, expected_origin)
    current = validate_checkpoint(current_checkpoint, expected_origin)
    heads = validate_head_map(head_map, expected_origin)
    launch_row = validate_launch(launch, expected_origin)
    parser = validate_parser_receipt(parser_receipt, expected_origin)
    authorization, signature_verified = validate_authorization(
        owner_authorization,
        expected_origin,
        key=key,
        expected_external_anchor_sha256=expected_external_anchor_sha256,
        observed_at=observed_at,
    )
    manifest_row = validate_manifest(manifest, expected_origin)
    attestation, final_signature_verified = validate_final_attestation(
        final_attestation,
        expected_origin,
        key=key,
        expected_external_anchor_sha256=expected_external_anchor_sha256,
    )

    supplied_anchor_key_match = False
    if signature_verified:
        if key is None or expected_external_anchor_sha256 is None:
            raise P0ActualAuthorityError("verified signature lacks owner key binding inputs")
        supplied_anchor_key_match = check_supplied_owner_key_binding(
            anchor,
            key=key,
            expected_external_anchor_sha256=expected_external_anchor_sha256,
            observed_at=observed_at,
        )
        if authorization["key_id"] != anchor["key_id"]:
            raise P0ActualAuthorityError("owner authorization key_id mismatch")
    if final_signature_verified:
        if key is None or expected_external_anchor_sha256 is None:
            raise P0ActualAuthorityError("verified final signature lacks owner key inputs")
        if not check_supplied_owner_key_binding(
            anchor,
            key=key,
            expected_external_anchor_sha256=expected_external_anchor_sha256,
            observed_at=attestation["issued_at"],
        ):
            raise P0ActualAuthorityError("post-run owner anchor binding mismatch")

    foundation_manifest = _sha(foundation_manifest_sha256, "foundation_manifest_sha256")
    foundation_receipt = _sha(foundation_receipt_sha256, "foundation_receipt_sha256")
    bindings = {
        "foundation manifest": launch_row["foundation_manifest_sha256"]
        == foundation_manifest
        == manifest_row["foundation_manifest_sha256"],
        "foundation receipt": launch_row["foundation_receipt_sha256"]
        == foundation_receipt
        == manifest_row["foundation_receipt_sha256"],
        "owner anchor": launch_row["owner_anchor_sha256"]
        == anchor["artifact_sha256"]
        == authorization["owner_anchor_sha256"]
        == manifest_row["owner_anchor_sha256"],
        "policy refs": launch_row["policy_refs_sha256"]
        == policies["artifact_sha256"]
        == manifest_row["policy_refs_sha256"],
        "watch spec": launch_row["watch_spec_sha256"]
        == watch["artifact_sha256"]
        == pre["watch_spec_sha256"]
        == post["watch_spec_sha256"]
        == manifest_row["watch_spec_sha256"],
        "predecessor checkpoint": launch_row["predecessor_checkpoint_sha256"]
        == predecessor["artifact_sha256"]
        == current["previous_checkpoint_sha256"]
        == manifest_row["predecessor_checkpoint_sha256"],
        "predecessor head map artifact": predecessor["head_map_artifact_sha256"]
        == predecessor_heads["artifact_sha256"]
        == manifest_row["predecessor_head_map_sha256"],
        "predecessor head set": predecessor["prefix_head_set_sha256"]
        == predecessor_heads["head_map_sha256"],
        "head map artifact": current["head_map_artifact_sha256"]
        == heads["artifact_sha256"]
        == manifest_row["head_map_sha256"],
        "current head set": current["prefix_head_set_sha256"]
        == heads["head_map_sha256"],
        "launch": launch_row["artifact_sha256"]
        == parser["launch_sha256"]
        == authorization["launch_sha256"]
        == manifest_row["launch_sha256"],
        "watch pre": pre["artifact_sha256"] == manifest_row["watch_pre_sha256"],
        "watch post": post["artifact_sha256"] == manifest_row["watch_post_sha256"],
        "current checkpoint": current["artifact_sha256"]
        == manifest_row["current_checkpoint_sha256"],
        "parser receipt": parser["artifact_sha256"]
        == manifest_row["parser_receipt_sha256"],
        "owner authorization": authorization["artifact_sha256"]
        == manifest_row["owner_authorization_sha256"],
        "final attestation owner anchor": attestation["owner_anchor_sha256"]
        == anchor["artifact_sha256"],
        "final attestation authorization": attestation["owner_authorization_sha256"]
        == authorization["artifact_sha256"],
        "final attestation foundation manifest": attestation[
            "foundation_manifest_sha256"
        ]
        == foundation_manifest,
        "final attestation foundation receipt": attestation[
            "foundation_receipt_sha256"
        ]
        == foundation_receipt,
        "final attestation launch": attestation["launch_sha256"]
        == launch_row["artifact_sha256"],
        "final attestation parser": attestation["parser_receipt_sha256"]
        == parser["artifact_sha256"],
        "final attestation predecessor checkpoint": attestation[
            "predecessor_checkpoint_sha256"
        ]
        == predecessor["artifact_sha256"],
        "final attestation predecessor head map": attestation[
            "predecessor_head_map_sha256"
        ]
        == predecessor_heads["artifact_sha256"],
        "final attestation current checkpoint": attestation[
            "current_checkpoint_sha256"
        ]
        == current["artifact_sha256"],
        "final attestation head map": attestation["head_map_sha256"]
        == heads["artifact_sha256"],
        "final attestation watch spec": attestation["watch_spec_sha256"]
        == watch["artifact_sha256"],
        "final attestation watch PRE": attestation["watch_pre_sha256"]
        == pre["artifact_sha256"],
        "final attestation watch POST": attestation["watch_post_sha256"]
        == post["artifact_sha256"],
        "final attestation manifest": attestation["manifest_sha256"]
        == manifest_row["artifact_sha256"],
        "final attestation event file": attestation["event_file_sha256"]
        == current["event_file_sha256"],
        "final attestation source count": attestation["actual_source_claim_count"]
        == manifest_row["actual_source_claim_count"],
        "final attestation A-context count": attestation[
            "actual_a_context_review_count"
        ]
        == manifest_row["actual_a_context_review_count"],
    }
    failed = [name for name, ok in bindings.items() if not ok]
    if failed:
        raise P0ActualAuthorityError(f"authority bundle binding mismatch: {failed}")
    if pre["phase"] != "PRE" or post["phase"] != "POST":
        raise P0ActualAuthorityError("watch PRE/POST phase binding mismatch")
    if current["prefix_rows"] < predecessor["prefix_rows"] or current["prefix_bytes"] < predecessor["prefix_bytes"]:
        raise P0ActualAuthorityError("annotation checkpoint prefix rollback")
    launch_created = _timestamp(launch_row["created_at"], "created_at")
    predecessor_created = _timestamp(predecessor["created_at"], "created_at")
    if predecessor_created > launch_created:
        raise P0ActualAuthorityError(
            "predecessor checkpoint cannot follow launch creation"
        )
    auth_issued = _timestamp(authorization["issued_at"], "issued_at")
    if auth_issued < launch_created:
        raise P0ActualAuthorityError("owner authorization cannot precede launch")
    capture_started = _optional_timestamp(
        launch_row["capture_started_at"], "capture_started_at"
    )
    if capture_started is not None and _timestamp(
        authorization["not_before"], "not_before"
    ) > capture_started:
        raise P0ActualAuthorityError("owner authorization must precede capture")
    rule_minimums = {
        rule["category"]: rule["required_min_count"] for rule in watch["rules"]
    }
    rule_roots = {
        rule["category"]: rule["relative_root"].replace("\\", "/").casefold()
        for rule in watch["rules"]
    }

    def watch_coverage_complete(snapshot: Mapping[str, Any]) -> bool:
        counts = {category: 0 for category in REQUIRED_WATCH_CATEGORIES}
        for member in snapshot["members"]:
            path = member["relative_path"].replace("\\", "/").casefold()
            root = rule_roots[member["category"]].rstrip("/")
            if not path.startswith(root + "/"):
                raise P0ActualAuthorityError(
                    "watch member must be a descendant of its category rule root"
                )
            counts[member["category"]] += 1
        return all(
            counts[category] >= rule_minimums[category]
            for category in REQUIRED_WATCH_CATEGORIES
        )

    for snapshot in (pre, post):
        coverage = watch_coverage_complete(snapshot)
        if snapshot["required_targets_present"] is not coverage:
            raise P0ActualAuthorityError(
                "watch required-target projection does not match protected membership"
            )
    pre_collected = _optional_timestamp(pre["collected_at"], "collected_at")
    post_collected = _optional_timestamp(post["collected_at"], "collected_at")
    if pre_collected is not None and post_collected is not None:
        if pre_collected > post_collected:
            raise P0ActualAuthorityError("watch PRE must not follow watch POST")
        if launch_created > pre_collected:
            raise P0ActualAuthorityError("watch PRE cannot precede launch creation")
        if auth_issued > pre_collected:
            raise P0ActualAuthorityError("watch PRE cannot precede owner authorization")
    if capture_started is not None:
        if _timestamp(authorization["expires_at"], "expires_at") <= capture_started:
            raise P0ActualAuthorityError("owner authorization must remain valid at capture")
        if pre_collected is None or post_collected is None:
            raise P0ActualAuthorityError(
                "captured launch requires both PRE and POST watch timestamps"
            )
        if not (pre_collected <= capture_started <= post_collected):
            raise P0ActualAuthorityError(
                "capture start must be bounded by PRE and POST watch timestamps"
            )
    if parser["runtime_status"] != "NOT_RUN":
        parser_started = _timestamp(parser["started_at"], "started_at")
        parser_completed = _timestamp(parser["completed_at"], "completed_at")
        if capture_started is None or parser_started < capture_started:
            raise P0ActualAuthorityError("parser cannot start before capture")
        if post_collected is not None and parser_completed > post_collected:
            raise P0ActualAuthorityError("watch POST cannot precede parser completion")
        if _timestamp(authorization["expires_at"], "expires_at") <= parser_completed:
            raise P0ActualAuthorityError(
                "owner authorization must remain valid through parser completion"
            )
        current_created = _timestamp(current["created_at"], "created_at")
        if current_created < parser_completed:
            raise P0ActualAuthorityError(
                "current checkpoint cannot precede parser completion"
            )
        if post_collected is not None and current_created > post_collected:
            raise P0ActualAuthorityError(
                "current checkpoint cannot follow watch POST"
            )
    finalized = _optional_timestamp(manifest_row["finalized_at"], "finalized_at")
    attested = _timestamp(attestation["issued_at"], "issued_at")
    if not (
        _timestamp(authorization["not_before"], "not_before")
        <= attested
        < _timestamp(authorization["expires_at"], "expires_at")
    ):
        raise P0ActualAuthorityError(
            "post-run attestation must be issued within authorization validity"
        )
    if finalized is not None:
        if parser["completed_at"] is None or finalized < _timestamp(
            parser["completed_at"], "completed_at"
        ):
            raise P0ActualAuthorityError("manifest cannot finalize before parser completion")
        if post_collected is None or finalized < post_collected:
            raise P0ActualAuthorityError("manifest cannot finalize before watch POST")
        if attested < finalized:
            raise P0ActualAuthorityError("post-run attestation cannot precede manifest")
    if attestation["key_id"] != anchor["key_id"]:
        raise P0ActualAuthorityError("post-run attestation key_id mismatch")
    terminal_membership_projection_equal = (
        pre["collection_status"] == "CAPTURED"
        and post["collection_status"] == "CAPTURED"
        and pre_collected is not None
        and post_collected is not None
        and watch_coverage_complete(pre)
        and watch_coverage_complete(post)
        and pre["membership_sha256"] == post["membership_sha256"]
        and pre["members"] == post["members"]
    )
    material = {
        "schema_version": RECEIPT_SCHEMA,
        "record_origin": expected_origin,
        "schema_check_status": (
            "PASS_ACTUAL_AUTHORITY_SCHEMA_EXAMPLE_ONLY"
            if expected_origin == EXAMPLE_ORIGIN
            else "PASS_ACTUAL_AUTHORITY_STRUCTURE_ONLY"
        ),
        "gate_status": "NO_GO_ACTUAL_P0_NOT_STARTED",
        "actual_gate_status": "NO_GO_ACTUAL_P0_NOT_STARTED",
        "detached_hmac_math_valid": signature_verified,
        "supplied_anchor_key_match": supplied_anchor_key_match,
        "final_attestation_math_valid": final_signature_verified,
        "final_attestation_sha256": attestation["artifact_sha256"],
        "owner_authority_verified": False,
        "policy_authority_verified": False,
        "annotation_append_only_verified": False,
        "terminal_membership_projection_equal": terminal_membership_projection_equal,
        "runtime_noninterference_verified": False,
        "runtime_write_deny_claim_present": False,
        "actual_source_claim_count": 0,
        "actual_a_context_review_count": 0,
        "expected_actual_source_claim_count": 40,
        "expected_actual_a_context_review_count": 20,
        "metric_status": "NOT_ESTIMABLE",
        "review_status": "REVIEW_LOCKED",
        "authority": "NONE_SCHEMA_FOUNDATION_ONLY",
        "public_apply": False,
        "central_slang_db_write": False,
        "publication_wal_write": False,
        "production_approval": False,
        "full_scan_approval": False,
        "p0_phase_exit": False,
        "blockers": [
            "ACTUAL_A_CONTEXT_REVIEWS_0_OF_20",
            "ACTUAL_ANNOTATION_DURABLE_PREDECESSOR_NOT_VERIFIED",
            "ACTUAL_AUTHORITY_DIRECTORY_VALIDATOR_NOT_IMPLEMENTED",
            "ACTUAL_EVENT_BYTES_RECEIPT_NOT_BOUND",
            "ACTUAL_FINAL_OWNER_ATTESTATION_NOT_VERIFIED",
            "ACTUAL_KEYLESS_PILOT_PACKET_NOT_IMPLEMENTED",
            "ACTUAL_OWNER_EXTERNAL_TRUST_NOT_VERIFIED",
            "ACTUAL_PARSER_RUNTIME_NOT_RUN",
            "ACTUAL_POLICY_AUTHORITY_NOT_VERIFIED",
            "ACTUAL_PROTECTED_STATE_RUNTIME_AUDIT_NOT_COMPLETE",
            "ACTUAL_SEMANTIC_REVIEW_NOT_COMPLETE",
            "ACTUAL_SOURCE_CLAIMS_0_OF_40",
        ],
        "manifest_sha256": manifest_row["artifact_sha256"],
    }
    return {**material, "receipt_sha256": canonical_sha256(material)}


__all__ = [
    "ACTUAL_ORIGIN",
    "AUTHORITY_EXAMPLE_FILES_V2",
    "AUTHORIZATION_DECISION",
    "AUTHORIZATION_DOMAIN",
    "AUTHORITY_SCOPE",
    "EXAMPLE_ORIGIN",
    "FINAL_ATTESTATION_DECISION",
    "FINAL_ATTESTATION_DOMAIN",
    "FINAL_ATTESTATION_SCHEMA",
    "P0ActualAuthorityError",
    "REQUIRED_POLICY_NAMES",
    "REQUIRED_WATCH_CATEGORIES",
    "authorization_material",
    "canonical_sha256",
    "final_attestation_material",
    "sign_authorization_material",
    "sign_final_attestation_material",
    "check_supplied_owner_key_binding",
    "validate_authority_foundation_bundle",
    "validate_authorization",
    "validate_final_attestation",
    "with_artifact_hash",
]
