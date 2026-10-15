"""Direct, byte-bound execution of the actual-P0 authority validators.

This module accepts only the fixed authority-v2 JSON members and annotation
event bytes.  It parses the JSON members strictly, invokes the foundation and
event-byte validators in-process, and emits a receipt for that local
observation.  The receipt is intentionally not an external execution witness,
an owner trust decision, or an actual-P0 approval.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import re
from types import MappingProxyType
from typing import Any, Mapping

from llm_batch.grounding import p0_actual_authority_contract as authority
from llm_batch.grounding import p0_actual_authority_event_bytes as event_verifier


AUTHORITY_RAW_EXECUTION_SCHEMA = "p0_actual_authority_raw_execution_receipt_v1"
PRESENTED_VALIDATION_SCHEMA = (
    "p0_actual_authority_raw_execution_presented_validation_v1"
)
EXECUTION_SCOPE = "LOCAL_DIRECT_AUTHORITY_VALIDATOR_INVOCATION_OBSERVATION_ONLY"
PRESENTED_SCOPE = "STRUCTURAL_PRESENTED_RECEIPT_ONLY"
GATE_STATUS = "NO_GO_ACTUAL_P0_AUTHORITY_NOT_VERIFIED"

AUTHORITY_FILE_ROLES = tuple(authority.AUTHORITY_EXAMPLE_FILES_V2.items())
AUTHORITY_FILE_COUNT = len(AUTHORITY_FILE_ROLES)

_SHA256 = re.compile(r"^[0-9a-f]{64}$")

_FOUNDATION_RESULT_FIELDS = frozenset(
    {
        "schema_version",
        "record_origin",
        "schema_check_status",
        "gate_status",
        "actual_gate_status",
        "detached_hmac_math_valid",
        "supplied_anchor_key_match",
        "final_attestation_math_valid",
        "final_attestation_sha256",
        "owner_authority_verified",
        "policy_authority_verified",
        "annotation_append_only_verified",
        "terminal_membership_projection_equal",
        "runtime_noninterference_verified",
        "runtime_write_deny_claim_present",
        "actual_source_claim_count",
        "actual_a_context_review_count",
        "expected_actual_source_claim_count",
        "expected_actual_a_context_review_count",
        "metric_status",
        "review_status",
        "authority",
        "public_apply",
        "central_slang_db_write",
        "publication_wal_write",
        "production_approval",
        "full_scan_approval",
        "p0_phase_exit",
        "blockers",
        "manifest_sha256",
        "receipt_sha256",
    }
)

_EVENT_RESULT_FIELDS = frozenset(
    {
        "schema_version",
        "event_file_sha256",
        "event_row_count",
        "predecessor_prefix_rows",
        "predecessor_prefix_bytes",
        "canonical_jsonl_verified",
        "journal_chains_verified",
        "checkpoint_prefixes_verified",
        "head_maps_reconstructed",
        "filesystem_handle_trust_verified",
        "durable_predecessor_verified",
        "owner_authority_verified",
        "runtime_noninterference_verified",
        "gate_status",
        "action_applied",
        "operational_effect",
        "receipt_sha256",
    }
)

_RAW_MEMBER_FIELDS = frozenset({"index", "role", "path", "bytes", "sha256"})
_FOUNDATION_PROJECTION_FIELDS = frozenset(
    {
        "receipt_sha256",
        "manifest_sha256",
        "final_attestation_sha256",
        "schema_check_status",
        "gate_status",
    }
)
_EVENT_PROJECTION_FIELDS = frozenset(
    {
        "receipt_sha256",
        "event_file_sha256",
        "event_row_count",
        "predecessor_prefix_rows",
        "predecessor_prefix_bytes",
        "gate_status",
    }
)

_RECEIPT_FIELDS = frozenset(
    {
        "schema_version",
        "execution_scope",
        "expected_authority_origin",
        "expected_event_origin",
        "foundation_manifest_sha256",
        "foundation_receipt_sha256",
        "expected_external_anchor_sha256",
        "observed_at",
        "authority_raw_member_count",
        "authority_raw_member_projection",
        "authority_raw_member_projection_sha256",
        "annotation_event_bytes_sha256",
        "annotation_event_bytes_count",
        "foundation_result_projection",
        "event_result_projection",
        "foundation_validator_invoked_directly",
        "annotation_event_bytes_validator_invoked_directly",
        "local_direct_validator_invocations_observed",
        "serialized_foundation_receipt_input_accepted",
        "serialized_event_receipt_input_accepted",
        "strict_authority_json_parse_observed",
        "raw_sha_projection_observed",
        "untrusted_local_execution_observation",
        "caller_self_code_measurement_verified",
        "external_code_authority_verified",
        "external_owner_trust_verified",
        "runtime_noninterference_verified",
        "owner_authority_verified",
        "actual_authority_granted",
        "credited_actual_source_claim_count",
        "credited_actual_a_context_review_count",
        "p0_phase_exit",
        "production_approval",
        "full_scan_approval",
        "action_applied",
        "operational_effect",
        "gate_status",
        "receipt_sha256",
    }
)


class P0ActualAuthorityRawExecutionError(ValueError):
    """Raised when raw authority execution cannot remain fail-closed."""


@dataclass(frozen=True)
class _AuthorityRawExecutionState:
    """Private immutable products of one direct validator execution."""

    raw_by_filename: Mapping[str, bytes]
    parsed_rows: Mapping[str, Mapping[str, Any]]
    foundation_result: Mapping[str, Any]
    event_result: Mapping[str, Any]
    public_receipt: Mapping[str, Any]


def _deep_freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType(
            {key: _deep_freeze(item) for key, item in value.items()}
        )
    if isinstance(value, list) or isinstance(value, tuple):
        return tuple(_deep_freeze(item) for item in value)
    return value


def _deep_thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _deep_thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_deep_thaw(item) for item in value]
    return value


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _sha(value: Any, field: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise P0ActualAuthorityRawExecutionError(
            f"{field} must be a lowercase sha256"
        )
    return value


def _optional_timestamp_text(value: Any, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value or value != value.strip():
        raise P0ActualAuthorityRawExecutionError(
            f"{field} must be canonical RFC3339 text or null"
        )
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise P0ActualAuthorityRawExecutionError(
            f"{field} must be canonical RFC3339 text or null"
        ) from exc
    if parsed.tzinfo is None:
        raise P0ActualAuthorityRawExecutionError(
            f"{field} must include a timezone"
        )
    return value


def _exact_mapping(value: Any, fields: frozenset[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise P0ActualAuthorityRawExecutionError(f"{label} must be an object")
    if set(value) != fields:
        raise P0ActualAuthorityRawExecutionError(
            f"{label} fields mismatch: missing={sorted(fields - set(value))}, "
            f"extra={sorted(set(value) - fields)}"
        )
    return value


def _duplicate_rejecting_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    row: dict[str, Any] = {}
    for key, value in pairs:
        if key in row:
            raise P0ActualAuthorityRawExecutionError(
                f"duplicate JSON key in authority member: {key}"
            )
        row[key] = value
    return row


def _reject_nonfinite_constant(token: str) -> None:
    raise P0ActualAuthorityRawExecutionError(
        f"authority JSON must not contain non-finite constant: {token}"
    )


def _parse_strict_json(raw: Any, *, role: str, path: str) -> dict[str, Any]:
    if type(raw) is not bytes:
        raise P0ActualAuthorityRawExecutionError(
            f"authority member {role}/{path} must be exact bytes"
        )
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise P0ActualAuthorityRawExecutionError(
            f"authority member {role}/{path} must be strict UTF-8 JSON"
        ) from exc
    if text.startswith("\ufeff"):
        raise P0ActualAuthorityRawExecutionError(
            f"authority member {role}/{path} must not contain a UTF-8 BOM"
        )
    try:
        value = json.loads(
            text,
            object_pairs_hook=_duplicate_rejecting_object,
            parse_constant=_reject_nonfinite_constant,
        )
    except P0ActualAuthorityRawExecutionError:
        raise
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise P0ActualAuthorityRawExecutionError(
            f"authority member {role}/{path} must be one strict JSON value"
        ) from exc
    if not isinstance(value, dict):
        raise P0ActualAuthorityRawExecutionError(
            f"authority member {role}/{path} must be a JSON object"
        )
    return value


def _self_hash(row: Mapping[str, Any], *, label: str) -> None:
    stored = _sha(row.get("receipt_sha256"), f"{label}.receipt_sha256")
    material = {key: value for key, value in row.items() if key != "receipt_sha256"}
    if stored != _canonical_sha256(material):
        raise P0ActualAuthorityRawExecutionError(f"{label} self-hash mismatch")


def _validate_foundation_result(
    result: Any,
    *,
    rows: Mapping[str, Mapping[str, Any]],
    expected_authority_origin: str,
) -> Mapping[str, Any]:
    row = _exact_mapping(result, _FOUNDATION_RESULT_FIELDS, "foundation validator result")
    _self_hash(row, label="foundation validator result")
    expected_schema_status = (
        "PASS_ACTUAL_AUTHORITY_SCHEMA_EXAMPLE_ONLY"
        if expected_authority_origin == authority.EXAMPLE_ORIGIN
        else "PASS_ACTUAL_AUTHORITY_STRUCTURE_ONLY"
    )
    if row["schema_version"] != authority.RECEIPT_SCHEMA:
        raise P0ActualAuthorityRawExecutionError(
            "foundation validator result schema mismatch"
        )
    if row["record_origin"] != expected_authority_origin:
        raise P0ActualAuthorityRawExecutionError(
            "foundation validator result origin mismatch"
        )
    if row["schema_check_status"] != expected_schema_status:
        raise P0ActualAuthorityRawExecutionError(
            "foundation validator result schema-check projection mismatch"
        )
    if (
        row["gate_status"] != "NO_GO_ACTUAL_P0_NOT_STARTED"
        or row["actual_gate_status"] != "NO_GO_ACTUAL_P0_NOT_STARTED"
        or row["authority"] != "NONE_SCHEMA_FOUNDATION_ONLY"
        or row["metric_status"] != "NOT_ESTIMABLE"
        or row["review_status"] != "REVIEW_LOCKED"
    ):
        raise P0ActualAuthorityRawExecutionError(
            "foundation validator result gate boundary mismatch"
        )
    if row["manifest_sha256"] != rows["manifest"].get("artifact_sha256"):
        raise P0ActualAuthorityRawExecutionError(
            "foundation result/manifest raw input cross-binding mismatch"
        )
    if row["final_attestation_sha256"] != rows["final_attestation"].get(
        "artifact_sha256"
    ):
        raise P0ActualAuthorityRawExecutionError(
            "foundation result/final-attestation raw input cross-binding mismatch"
        )
    for field in (
        "owner_authority_verified",
        "policy_authority_verified",
        "annotation_append_only_verified",
        "runtime_noninterference_verified",
        "runtime_write_deny_claim_present",
        "public_apply",
        "central_slang_db_write",
        "publication_wal_write",
        "production_approval",
        "full_scan_approval",
        "p0_phase_exit",
    ):
        if row[field] is not False:
            raise P0ActualAuthorityRawExecutionError(
                f"foundation validator result overclaims {field}"
            )
    if row["actual_source_claim_count"] != 0 or row["actual_a_context_review_count"] != 0:
        raise P0ActualAuthorityRawExecutionError(
            "foundation validator result must keep actual counts zero"
        )
    if (
        row["expected_actual_source_claim_count"] != 40
        or row["expected_actual_a_context_review_count"] != 20
    ):
        raise P0ActualAuthorityRawExecutionError(
            "foundation validator result 40+20 target mismatch"
        )
    for field in (
        "detached_hmac_math_valid",
        "supplied_anchor_key_match",
        "final_attestation_math_valid",
        "terminal_membership_projection_equal",
    ):
        if not isinstance(row[field], bool):
            raise P0ActualAuthorityRawExecutionError(
                f"foundation validator result {field} must be boolean"
            )
    blockers = row["blockers"]
    if (
        not isinstance(blockers, list)
        or any(not isinstance(item, str) or not item for item in blockers)
        or len(set(blockers)) != len(blockers)
    ):
        raise P0ActualAuthorityRawExecutionError(
            "foundation validator result blockers must be unique text"
        )
    return row


def _validate_event_result(
    result: Any,
    *,
    event_bytes: bytes,
    rows: Mapping[str, Mapping[str, Any]],
) -> Mapping[str, Any]:
    row = _exact_mapping(result, _EVENT_RESULT_FIELDS, "event validator result")
    _self_hash(row, label="event validator result")
    if row["schema_version"] != event_verifier.EVENT_BYTES_RECEIPT_SCHEMA:
        raise P0ActualAuthorityRawExecutionError(
            "event validator result schema mismatch"
        )
    if (
        row["gate_status"] != "NO_GO_ACTUAL_P0_NOT_STARTED"
        or row["operational_effect"] != "NONE_SHADOW_ONLY"
    ):
        raise P0ActualAuthorityRawExecutionError(
            "event validator result gate boundary mismatch"
        )
    for field in (
        "event_row_count",
        "predecessor_prefix_rows",
        "predecessor_prefix_bytes",
    ):
        if isinstance(row[field], bool) or not isinstance(row[field], int) or row[field] < 0:
            raise P0ActualAuthorityRawExecutionError(
                f"event validator result {field} must be a nonnegative integer"
            )
    raw_sha = hashlib.sha256(event_bytes).hexdigest()
    if row["event_file_sha256"] != raw_sha:
        raise P0ActualAuthorityRawExecutionError(
            "event validator result/raw input cross-binding mismatch"
        )
    current = rows["current_checkpoint"]
    predecessor = rows["predecessor_checkpoint"]
    if (
        row["event_file_sha256"] != current.get("event_file_sha256")
        or row["event_row_count"] != current.get("prefix_rows")
        or row["predecessor_prefix_rows"] != predecessor.get("prefix_rows")
        or row["predecessor_prefix_bytes"] != predecessor.get("prefix_bytes")
    ):
        raise P0ActualAuthorityRawExecutionError(
            "event validator result/checkpoint input cross-binding mismatch"
        )
    for field in (
        "filesystem_handle_trust_verified",
        "durable_predecessor_verified",
        "owner_authority_verified",
        "runtime_noninterference_verified",
        "action_applied",
    ):
        if row[field] is not False:
            raise P0ActualAuthorityRawExecutionError(
                f"event validator result overclaims {field}"
            )
    for field in (
        "canonical_jsonl_verified",
        "journal_chains_verified",
        "checkpoint_prefixes_verified",
        "head_maps_reconstructed",
    ):
        if row[field] is not True:
            raise P0ActualAuthorityRawExecutionError(
                f"event validator result does not prove local {field}"
            )
    return row


def _execute_authority_raw_validation_state(
    *,
    authority_raw_by_filename: Mapping[str, bytes],
    annotation_event_bytes: bytes,
    expected_authority_origin: str,
    expected_event_origin: str,
    foundation_manifest_sha256: str,
    foundation_receipt_sha256: str,
    key: bytes | None = None,
    expected_external_anchor_sha256: str | None = None,
    observed_at: str | None = None,
) -> _AuthorityRawExecutionState:
    """Parse fixed raw inputs and directly invoke both authority validators.

    Serialized foundation/event receipts are deliberately not accepted as
    inputs.  The returned private state records only an untrusted local
    invocation and is recursively immutable.
    """

    if not isinstance(authority_raw_by_filename, Mapping):
        raise P0ActualAuthorityRawExecutionError(
            "authority_raw_by_filename must be a filename-to-bytes mapping"
        )
    # Snapshot the caller mapping before any parse or validator call.  Values
    # are required to be immutable ``bytes`` below, so later caller mutation of
    # the source mapping cannot swap a role between validation steps.
    raw_by_filename = dict(authority_raw_by_filename)
    if any(not isinstance(path, str) for path in raw_by_filename):
        raise P0ActualAuthorityRawExecutionError(
            "authority raw inventory keys must be filenames"
        )
    expected_names = {path for _, path in AUTHORITY_FILE_ROLES}
    if set(raw_by_filename) != expected_names:
        raise P0ActualAuthorityRawExecutionError(
            "authority raw filename inventory mismatch: "
            f"missing={sorted(expected_names - set(raw_by_filename))}, "
            f"extra={sorted(set(raw_by_filename) - expected_names)}"
        )
    if type(annotation_event_bytes) is not bytes:
        raise P0ActualAuthorityRawExecutionError(
            "annotation_event_bytes must be exact bytes"
        )
    if not isinstance(expected_authority_origin, str) or not expected_authority_origin:
        raise P0ActualAuthorityRawExecutionError(
            "expected_authority_origin must be non-empty text"
        )
    if not isinstance(expected_event_origin, str) or not expected_event_origin:
        raise P0ActualAuthorityRawExecutionError(
            "expected_event_origin must be non-empty text"
        )
    _sha(foundation_manifest_sha256, "foundation_manifest_sha256")
    _sha(foundation_receipt_sha256, "foundation_receipt_sha256")
    if key is not None and type(key) is not bytes:
        raise P0ActualAuthorityRawExecutionError("key must be exact bytes or null")
    if expected_external_anchor_sha256 is not None:
        _sha(
            expected_external_anchor_sha256,
            "expected_external_anchor_sha256",
        )
    _optional_timestamp_text(observed_at, "observed_at")

    rows: dict[str, dict[str, Any]] = {}
    raw_projection: list[dict[str, Any]] = []
    for index, (role, path) in enumerate(AUTHORITY_FILE_ROLES):
        raw = raw_by_filename[path]
        rows[role] = _parse_strict_json(raw, role=role, path=path)
        raw_projection.append(
            {
                "index": index,
                "role": role,
                "path": path,
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )

    # These are the only calls that produce the two result objects.  Callers
    # cannot supply serialized validator receipts to this API.
    foundation_result = authority.validate_authority_foundation_bundle(
        **rows,
        expected_origin=expected_authority_origin,
        foundation_manifest_sha256=foundation_manifest_sha256,
        foundation_receipt_sha256=foundation_receipt_sha256,
        key=key,
        expected_external_anchor_sha256=expected_external_anchor_sha256,
        observed_at=observed_at,
    )
    foundation = _validate_foundation_result(
        foundation_result,
        rows=rows,
        expected_authority_origin=expected_authority_origin,
    )

    event_result = event_verifier.verify_annotation_event_bytes_from_bytes(
        event_bytes=annotation_event_bytes,
        predecessor_checkpoint=rows["predecessor_checkpoint"],
        predecessor_head_map=rows["predecessor_head_map"],
        current_checkpoint=rows["current_checkpoint"],
        current_head_map=rows["head_map"],
        expected_authority_origin=expected_authority_origin,
        expected_event_origin=expected_event_origin,
    )
    event = _validate_event_result(
        event_result,
        event_bytes=annotation_event_bytes,
        rows=rows,
    )

    material = {
        "schema_version": AUTHORITY_RAW_EXECUTION_SCHEMA,
        "execution_scope": EXECUTION_SCOPE,
        "expected_authority_origin": expected_authority_origin,
        "expected_event_origin": expected_event_origin,
        "foundation_manifest_sha256": foundation_manifest_sha256,
        "foundation_receipt_sha256": foundation_receipt_sha256,
        "expected_external_anchor_sha256": expected_external_anchor_sha256,
        "observed_at": observed_at,
        "authority_raw_member_count": AUTHORITY_FILE_COUNT,
        "authority_raw_member_projection": raw_projection,
        "authority_raw_member_projection_sha256": _canonical_sha256(raw_projection),
        "annotation_event_bytes_sha256": hashlib.sha256(
            annotation_event_bytes
        ).hexdigest(),
        "annotation_event_bytes_count": len(annotation_event_bytes),
        "foundation_result_projection": {
            "receipt_sha256": foundation["receipt_sha256"],
            "manifest_sha256": foundation["manifest_sha256"],
            "final_attestation_sha256": foundation["final_attestation_sha256"],
            "schema_check_status": foundation["schema_check_status"],
            "gate_status": foundation["gate_status"],
        },
        "event_result_projection": {
            "receipt_sha256": event["receipt_sha256"],
            "event_file_sha256": event["event_file_sha256"],
            "event_row_count": event["event_row_count"],
            "predecessor_prefix_rows": event["predecessor_prefix_rows"],
            "predecessor_prefix_bytes": event["predecessor_prefix_bytes"],
            "gate_status": event["gate_status"],
        },
        "foundation_validator_invoked_directly": True,
        "annotation_event_bytes_validator_invoked_directly": True,
        "local_direct_validator_invocations_observed": True,
        "serialized_foundation_receipt_input_accepted": False,
        "serialized_event_receipt_input_accepted": False,
        "strict_authority_json_parse_observed": True,
        "raw_sha_projection_observed": True,
        "untrusted_local_execution_observation": True,
        "caller_self_code_measurement_verified": False,
        "external_code_authority_verified": False,
        "external_owner_trust_verified": False,
        "runtime_noninterference_verified": False,
        "owner_authority_verified": False,
        "actual_authority_granted": False,
        "credited_actual_source_claim_count": 0,
        "credited_actual_a_context_review_count": 0,
        "p0_phase_exit": False,
        "production_approval": False,
        "full_scan_approval": False,
        "action_applied": False,
        "operational_effect": "NONE_SHADOW_ONLY",
        "gate_status": GATE_STATUS,
    }
    public_receipt = {
        **material,
        "receipt_sha256": _canonical_sha256(material),
    }
    return _AuthorityRawExecutionState(
        raw_by_filename=_deep_freeze(raw_by_filename),
        parsed_rows=_deep_freeze(rows),
        foundation_result=_deep_freeze(dict(foundation)),
        event_result=_deep_freeze(dict(event)),
        public_receipt=_deep_freeze(public_receipt),
    )


def execute_authority_raw_validation(
    *,
    authority_raw_by_filename: Mapping[str, bytes],
    annotation_event_bytes: bytes,
    expected_authority_origin: str,
    expected_event_origin: str,
    foundation_manifest_sha256: str,
    foundation_receipt_sha256: str,
    key: bytes | None = None,
    expected_external_anchor_sha256: str | None = None,
    observed_at: str | None = None,
) -> dict[str, Any]:
    """Return only a detached ordinary copy of the private execution receipt."""

    state = _execute_authority_raw_validation_state(
        authority_raw_by_filename=authority_raw_by_filename,
        annotation_event_bytes=annotation_event_bytes,
        expected_authority_origin=expected_authority_origin,
        expected_event_origin=expected_event_origin,
        foundation_manifest_sha256=foundation_manifest_sha256,
        foundation_receipt_sha256=foundation_receipt_sha256,
        key=key,
        expected_external_anchor_sha256=expected_external_anchor_sha256,
        observed_at=observed_at,
    )
    receipt = _deep_thaw(state.public_receipt)
    if not isinstance(receipt, dict):
        raise AssertionError("private authority receipt must thaw to an object")
    return receipt


def _validate_raw_projection(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list) or len(value) != AUTHORITY_FILE_COUNT:
        raise P0ActualAuthorityRawExecutionError(
            "presented authority raw member count mismatch"
        )
    parsed: list[dict[str, Any]] = []
    for index, ((expected_role, expected_path), item) in enumerate(
        zip(AUTHORITY_FILE_ROLES, value, strict=True)
    ):
        row = _exact_mapping(item, _RAW_MEMBER_FIELDS, "presented raw member")
        if row["index"] != index or row["role"] != expected_role or row["path"] != expected_path:
            raise P0ActualAuthorityRawExecutionError(
                "presented authority raw role/path inventory mismatch"
            )
        if isinstance(row["bytes"], bool) or not isinstance(row["bytes"], int) or row["bytes"] < 0:
            raise P0ActualAuthorityRawExecutionError(
                "presented authority raw member bytes must be nonnegative integer"
            )
        _sha(row["sha256"], "presented raw member sha256")
        parsed.append(dict(row))
    return parsed


def validate_presented_authority_raw_execution_receipt(
    value: Any,
) -> dict[str, Any]:
    """Validate a serialized receipt structurally without preserving execution."""

    row = _exact_mapping(value, _RECEIPT_FIELDS, "presented execution receipt")
    _self_hash(row, label="presented execution receipt")
    if row["schema_version"] != AUTHORITY_RAW_EXECUTION_SCHEMA:
        raise P0ActualAuthorityRawExecutionError("presented receipt schema mismatch")
    if row["execution_scope"] != EXECUTION_SCOPE:
        raise P0ActualAuthorityRawExecutionError("presented execution scope mismatch")
    for field in ("expected_authority_origin", "expected_event_origin"):
        if not isinstance(row[field], str) or not row[field]:
            raise P0ActualAuthorityRawExecutionError(
                f"presented {field} must be non-empty text"
            )
    _sha(row["foundation_manifest_sha256"], "foundation_manifest_sha256")
    _sha(row["foundation_receipt_sha256"], "foundation_receipt_sha256")
    if row["expected_external_anchor_sha256"] is not None:
        _sha(
            row["expected_external_anchor_sha256"],
            "expected_external_anchor_sha256",
        )
    _optional_timestamp_text(row["observed_at"], "observed_at")
    projection = _validate_raw_projection(row["authority_raw_member_projection"])
    if row["authority_raw_member_count"] != AUTHORITY_FILE_COUNT:
        raise P0ActualAuthorityRawExecutionError(
            "presented authority raw member count projection mismatch"
        )
    if row["authority_raw_member_projection_sha256"] != _canonical_sha256(projection):
        raise P0ActualAuthorityRawExecutionError(
            "presented authority raw projection hash mismatch"
        )
    _sha(row["annotation_event_bytes_sha256"], "annotation_event_bytes_sha256")
    if (
        isinstance(row["annotation_event_bytes_count"], bool)
        or not isinstance(row["annotation_event_bytes_count"], int)
        or row["annotation_event_bytes_count"] < 0
    ):
        raise P0ActualAuthorityRawExecutionError(
            "annotation_event_bytes_count must be a nonnegative integer"
        )
    foundation = _exact_mapping(
        row["foundation_result_projection"],
        _FOUNDATION_PROJECTION_FIELDS,
        "foundation result projection",
    )
    event = _exact_mapping(
        row["event_result_projection"],
        _EVENT_PROJECTION_FIELDS,
        "event result projection",
    )
    for field in ("receipt_sha256", "manifest_sha256", "final_attestation_sha256"):
        _sha(foundation[field], f"foundation projection {field}")
    for field in ("receipt_sha256", "event_file_sha256"):
        _sha(event[field], f"event projection {field}")
    if event["event_file_sha256"] != row["annotation_event_bytes_sha256"]:
        raise P0ActualAuthorityRawExecutionError(
            "presented event projection/raw SHA mismatch"
        )
    if foundation["gate_status"] != "NO_GO_ACTUAL_P0_NOT_STARTED" or event[
        "gate_status"
    ] != "NO_GO_ACTUAL_P0_NOT_STARTED":
        raise P0ActualAuthorityRawExecutionError("nested gate status overclaim")
    if foundation["schema_check_status"] not in {
        "PASS_ACTUAL_AUTHORITY_SCHEMA_EXAMPLE_ONLY",
        "PASS_ACTUAL_AUTHORITY_STRUCTURE_ONLY",
    }:
        raise P0ActualAuthorityRawExecutionError(
            "foundation schema-check projection is invalid"
        )
    for field in ("event_row_count", "predecessor_prefix_rows", "predecessor_prefix_bytes"):
        if isinstance(event[field], bool) or not isinstance(event[field], int) or event[field] < 0:
            raise P0ActualAuthorityRawExecutionError(
                f"event projection {field} must be a nonnegative integer"
            )
    for field in (
        "foundation_validator_invoked_directly",
        "annotation_event_bytes_validator_invoked_directly",
        "local_direct_validator_invocations_observed",
        "strict_authority_json_parse_observed",
        "raw_sha_projection_observed",
        "untrusted_local_execution_observation",
    ):
        if row[field] is not True:
            raise P0ActualAuthorityRawExecutionError(
                f"presented receipt local observation projection mismatch: {field}"
            )
    for field in (
        "serialized_foundation_receipt_input_accepted",
        "serialized_event_receipt_input_accepted",
        "caller_self_code_measurement_verified",
        "external_code_authority_verified",
        "external_owner_trust_verified",
        "runtime_noninterference_verified",
        "owner_authority_verified",
        "actual_authority_granted",
        "p0_phase_exit",
        "production_approval",
        "full_scan_approval",
        "action_applied",
    ):
        if row[field] is not False:
            raise P0ActualAuthorityRawExecutionError(
                f"presented receipt overclaims {field}"
            )
    if (
        row["credited_actual_source_claim_count"] != 0
        or row["credited_actual_a_context_review_count"] != 0
    ):
        raise P0ActualAuthorityRawExecutionError(
            "presented receipt cannot carry credited actual counts"
        )
    if row["gate_status"] != GATE_STATUS or row["operational_effect"] != "NONE_SHADOW_ONLY":
        raise P0ActualAuthorityRawExecutionError("presented authority boundary mismatch")

    material = {
        "schema_version": PRESENTED_VALIDATION_SCHEMA,
        "validation_scope": PRESENTED_SCOPE,
        "presented_receipt_sha256": row["receipt_sha256"],
        "presented_receipt_structurally_verified": True,
        "local_direct_validator_invocations_observed": False,
        "underlying_validator_execution_verified": False,
        "external_code_authority_verified": False,
        "external_owner_trust_verified": False,
        "runtime_noninterference_verified": False,
        "owner_authority_verified": False,
        "actual_authority_granted": False,
        "credited_actual_source_claim_count": 0,
        "credited_actual_a_context_review_count": 0,
        "p0_phase_exit": False,
        "production_approval": False,
        "full_scan_approval": False,
        "action_applied": False,
        "operational_effect": "NONE_SHADOW_ONLY",
        "gate_status": GATE_STATUS,
    }
    return {**material, "receipt_sha256": _canonical_sha256(material)}


__all__ = [
    "AUTHORITY_FILE_COUNT",
    "AUTHORITY_FILE_ROLES",
    "AUTHORITY_RAW_EXECUTION_SCHEMA",
    "P0ActualAuthorityRawExecutionError",
    "execute_authority_raw_validation",
    "validate_presented_authority_raw_execution_receipt",
]
