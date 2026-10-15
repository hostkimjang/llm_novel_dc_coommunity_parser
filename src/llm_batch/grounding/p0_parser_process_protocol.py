"""Canonical stdin/stdout protocol for a bounded P0 parser-process probe.

The only supported operation, :data:`CAPTURE_HASH_PROBE`, decodes caller-bound
capture bytes and reports their hashes and accounting.  It deliberately does
not parse semantic claims and cannot grant actual-evidence, owner, runtime,
P0, or production authority.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
from typing import Any, Mapping


REQUEST_SCHEMA = "p0_parser_process_request_v1"
RESPONSE_SCHEMA = "p0_parser_process_response_v2"
CROSS_BINDING_SCHEMA = "p0_parser_process_cross_binding_validation_v2"
RUNTIME_GUARD_ATTESTATION_SCHEMA = "p0_parser_process_runtime_guard_attestation_v2"
OPERATION = "CAPTURE_HASH_PROBE"
OPERATIONAL_EFFECT = "NONE_SHADOW_ONLY"
GATE_STATUS = "NO_GO_CAPTURE_HASH_PROBE_ONLY"

MAX_REQUEST_BYTES = 8 * 1024 * 1024
MAX_RESPONSE_BYTES = 256 * 1024
MAX_CAPTURE_COUNT = 40
MAX_CAPTURE_BYTES = 256 * 1024
MAX_TOTAL_CAPTURE_BYTES = 4 * 1024 * 1024

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")
_REQUEST_FIELDS = frozenset(
    {
        "schema_version",
        "operation",
        "request_id",
        "parser_run_id",
        "launch_sha256",
        "capture_manifest_sha256",
        "input_registry_sha256",
        "parser_manifest_sha256",
        "parser_version",
        "captures",
    }
)
_CAPTURE_FIELDS = frozenset(
    {"capture_id", "payload_base64", "payload_bytes", "payload_sha256"}
)
_OBSERVATION_FIELDS = frozenset(
    {"capture_id", "payload_bytes", "payload_sha256"}
)
_RUNTIME_GUARD_FIELDS = frozenset(
    {
        "schema_version",
        "python_implementation",
        "python_cache_tag",
        "python_version",
        "pycache_prefix_sha256",
        "runtime_flags",
        "guard_meta_path_index",
        "project_specs",
        "guard_finalized",
    }
)
_RUNTIME_GUARD_FLAG_FIELDS = frozenset(
    {
        "dont_write_bytecode",
        "isolated",
        "no_site",
        "ignore_environment",
        "safe_path",
        "optimize",
    }
)
_RUNTIME_GUARD_SPEC_FIELDS = frozenset(
    {
        "module_name",
        "origin_sha256",
        "cached_path_sha256",
        "package_location_sha256s",
        "loader",
        "cached_under_bound_prefix_verified",
    }
)
FALSE_AUTHORITY_FIELDS = frozenset(
    {
        "external_code_authority_verified",
        "supervisor_runtime_trust_verified",
        "trusted_time_verified",
        "external_trust_store_verified",
        "revocation_current_verified",
        "external_owner_trust_verified",
        "owner_authority_verified",
        "external_owner_authority_verified",
        "semantic_quality_verified",
        "external_root_identity_pin_verified",
        "filesystem_handle_binding_verified",
        "filesystem_handle_trust_verified",
        "windows_handle_capture_execution_provenance_verified",
        "handles_held_across_validator_execution",
        "authority_journal_watch_bundle_verified",
        "durable_predecessor_verified",
        "annotation_append_only_verified",
        "actual_semantic_evidence_verified",
        "actual_authority_granted",
        "network_deny_verified",
        "os_write_deny_verified",
        "runtime_noninterference_verified",
        "parser_runtime_execution_verified",
        "p0_phase_exit",
        "production_approval",
        "full_scan_approval",
        "protected_pipeline_state_mutated",
        "action_applied",
    }
)
_RESPONSE_FIELDS = frozenset(
    {
        "schema_version",
        "operation",
        "request_id",
        "parser_run_id",
        "request_sha256",
        "launch_sha256",
        "capture_manifest_sha256",
        "input_registry_sha256",
        "parser_manifest_sha256",
        "parser_version",
        "capture_count",
        "total_payload_bytes",
        "capture_observations",
        "capture_observations_sha256",
        "child_reported_capture_hash_probe_completed",
        "child_reported_capture_payload_accounting_complete",
        "child_reported_runtime_guard_completed",
        "runtime_guard_attestation",
        *FALSE_AUTHORITY_FIELDS,
        "credited_counts",
        "operational_effect",
        "gate_status",
        "receipt_sha256",
    }
)


class P0ParserProcessProtocolError(ValueError):
    """The byte protocol or a protocol value failed closed."""


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_file_bytes(value: Any) -> bytes:
    return canonical_bytes(value) + b"\n"


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _duplicate_rejecting_object(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise P0ParserProcessProtocolError(
                "duplicate JSON key is forbidden"
            )
        result[key] = value
    return result


def _reject_nonfinite(token: str) -> None:
    raise P0ParserProcessProtocolError(
        f"non-finite JSON number is forbidden: {token}"
    )


def _parse_canonical_object(raw: bytes, *, label: str, maximum: int) -> dict[str, Any]:
    if type(raw) is not bytes:
        raise P0ParserProcessProtocolError(f"{label} must be exact bytes")
    if not raw or len(raw) > maximum:
        raise P0ParserProcessProtocolError(
            f"{label} byte length must be within 1..{maximum}"
        )
    if raw.startswith(b"\xef\xbb\xbf"):
        raise P0ParserProcessProtocolError(f"{label} must not contain UTF-8 BOM")
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise P0ParserProcessProtocolError(f"{label} must be strict UTF-8") from exc
    try:
        value = json.loads(
            text,
            object_pairs_hook=_duplicate_rejecting_object,
            parse_constant=_reject_nonfinite,
        )
    except P0ParserProcessProtocolError:
        raise
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise P0ParserProcessProtocolError(f"{label} must contain one JSON object") from exc
    if not isinstance(value, dict):
        raise P0ParserProcessProtocolError(f"{label} must contain one JSON object")
    try:
        expected = canonical_file_bytes(value)
    except (TypeError, ValueError) as exc:
        raise P0ParserProcessProtocolError(
            f"{label} contains a non-canonical JSON value"
        ) from exc
    if raw != expected:
        raise P0ParserProcessProtocolError(
            f"{label} must be canonical JSON with exactly one final LF"
        )
    return value


def _exact_mapping(value: Any, fields: frozenset[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != fields:
        present = set(value) if isinstance(value, Mapping) else set()
        raise P0ParserProcessProtocolError(
            f"{label} fields mismatch: missing={sorted(fields - present)}, "
            f"extra={sorted(present - fields)}"
        )
    return value


def _identifier(value: Any, field: str) -> str:
    if not isinstance(value, str) or _SAFE_ID.fullmatch(value) is None:
        raise P0ParserProcessProtocolError(f"{field} must be a canonical identifier")
    return value


def _sha(value: Any, field: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise P0ParserProcessProtocolError(f"{field} must be lowercase SHA-256")
    return value


def _nonnegative_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise P0ParserProcessProtocolError(f"{field} must be a nonnegative integer")
    return value


def _decode_capture(value: Any, index: int) -> tuple[dict[str, Any], bytes]:
    row = _exact_mapping(value, _CAPTURE_FIELDS, f"captures[{index}]")
    capture_id = _identifier(row["capture_id"], f"captures[{index}].capture_id")
    encoded = row["payload_base64"]
    if not isinstance(encoded, str) or not encoded.isascii():
        raise P0ParserProcessProtocolError(
            f"captures[{index}].payload_base64 must be ASCII base64"
        )
    try:
        payload = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise P0ParserProcessProtocolError(
            f"captures[{index}].payload_base64 is invalid"
        ) from exc
    if base64.b64encode(payload).decode("ascii") != encoded:
        raise P0ParserProcessProtocolError(
            f"captures[{index}].payload_base64 is not canonical"
        )
    expected_bytes = _nonnegative_int(
        row["payload_bytes"], f"captures[{index}].payload_bytes"
    )
    if expected_bytes > MAX_CAPTURE_BYTES:
        raise P0ParserProcessProtocolError(
            f"captures[{index}] exceeds the per-capture byte limit"
        )
    if expected_bytes != len(payload):
        raise P0ParserProcessProtocolError(
            f"captures[{index}] payload byte count mismatch"
        )
    expected_sha = _sha(
        row["payload_sha256"], f"captures[{index}].payload_sha256"
    )
    if not hashlib.sha256(payload).hexdigest() == expected_sha:
        raise P0ParserProcessProtocolError(
            f"captures[{index}] payload SHA-256 mismatch"
        )
    return (
        {
            "capture_id": capture_id,
            "payload_bytes": expected_bytes,
            "payload_sha256": expected_sha,
        },
        payload,
    )


def parse_request_bytes(raw: bytes) -> dict[str, Any]:
    row = _exact_mapping(
        _parse_canonical_object(raw, label="parser request", maximum=MAX_REQUEST_BYTES),
        _REQUEST_FIELDS,
        "parser request",
    )
    if row["schema_version"] != REQUEST_SCHEMA or row["operation"] != OPERATION:
        raise P0ParserProcessProtocolError("parser request schema/operation mismatch")
    _identifier(row["request_id"], "request_id")
    _identifier(row["parser_run_id"], "parser_run_id")
    _sha(row["launch_sha256"], "launch_sha256")
    _sha(row["capture_manifest_sha256"], "capture_manifest_sha256")
    _sha(row["input_registry_sha256"], "input_registry_sha256")
    _sha(row["parser_manifest_sha256"], "parser_manifest_sha256")
    _identifier(row["parser_version"], "parser_version")
    captures = row["captures"]
    if (
        not isinstance(captures, list)
        or not captures
        or len(captures) > MAX_CAPTURE_COUNT
    ):
        raise P0ParserProcessProtocolError(
            f"captures must contain 1..{MAX_CAPTURE_COUNT} rows"
        )
    observations: list[dict[str, Any]] = []
    capture_ids: set[str] = set()
    total = 0
    for index, value in enumerate(captures):
        observation, payload = _decode_capture(value, index)
        capture_id = observation["capture_id"]
        if capture_id in capture_ids:
            raise P0ParserProcessProtocolError("capture_id must be unique")
        capture_ids.add(capture_id)
        observations.append(observation)
        total += len(payload)
        if total > MAX_TOTAL_CAPTURE_BYTES:
            raise P0ParserProcessProtocolError(
                "captures exceed the total decoded byte limit"
            )
    return dict(row)


def execute_request_bytes(
    raw: bytes,
    *,
    runtime_guard_attestation: Mapping[str, Any] | None = None,
) -> bytes:
    row = parse_request_bytes(raw)
    attestation = (
        _validate_runtime_guard_attestation(runtime_guard_attestation)
        if runtime_guard_attestation is not None
        else None
    )
    observations: list[dict[str, Any]] = []
    total = 0
    for index, value in enumerate(row["captures"]):
        observation, payload = _decode_capture(value, index)
        observations.append(observation)
        total += len(payload)
    material = {
        "schema_version": RESPONSE_SCHEMA,
        "operation": OPERATION,
        "request_id": row["request_id"],
        "parser_run_id": row["parser_run_id"],
        "request_sha256": hashlib.sha256(raw).hexdigest(),
        "launch_sha256": row["launch_sha256"],
        "capture_manifest_sha256": row["capture_manifest_sha256"],
        "input_registry_sha256": row["input_registry_sha256"],
        "parser_manifest_sha256": row["parser_manifest_sha256"],
        "parser_version": row["parser_version"],
        "capture_count": len(observations),
        "total_payload_bytes": total,
        "capture_observations": observations,
        "capture_observations_sha256": canonical_sha256(observations),
        "child_reported_capture_hash_probe_completed": True,
        "child_reported_capture_payload_accounting_complete": True,
        "child_reported_runtime_guard_completed": attestation is not None,
        "runtime_guard_attestation": attestation,
        **{field: False for field in FALSE_AUTHORITY_FIELDS},
        "credited_counts": {
            "actual_source_claim_count": 0,
            "actual_a_context_review_count": 0,
        },
        "operational_effect": OPERATIONAL_EFFECT,
        "gate_status": GATE_STATUS,
    }
    response = {**material, "receipt_sha256": canonical_sha256(material)}
    encoded = canonical_file_bytes(response)
    if len(encoded) > MAX_RESPONSE_BYTES:
        raise P0ParserProcessProtocolError("parser response exceeds byte limit")
    return encoded


def _validate_runtime_guard_attestation(value: Any) -> dict[str, Any]:
    row = _exact_mapping(value, _RUNTIME_GUARD_FIELDS, "runtime guard attestation")
    if row["schema_version"] != RUNTIME_GUARD_ATTESTATION_SCHEMA:
        raise P0ParserProcessProtocolError(
            "runtime guard attestation schema mismatch"
        )
    if row["python_implementation"] != "cpython":
        raise P0ParserProcessProtocolError(
            "runtime guard Python implementation mismatch"
        )
    if (
        not isinstance(row["python_cache_tag"], str)
        or not re.fullmatch(r"cpython-[0-9]+", row["python_cache_tag"])
    ):
        raise P0ParserProcessProtocolError("runtime guard cache tag is invalid")
    version = row["python_version"]
    if (
        not isinstance(version, list)
        or len(version) != 3
        or any(type(value) is not int or value < 0 for value in version)
    ):
        raise P0ParserProcessProtocolError("runtime guard Python version is invalid")
    _sha(row["pycache_prefix_sha256"], "pycache_prefix_sha256")
    flags = _exact_mapping(
        row["runtime_flags"], _RUNTIME_GUARD_FLAG_FIELDS, "runtime_flags"
    )
    expected_flags = {
        "dont_write_bytecode": True,
        "isolated": 1,
        "no_site": 1,
        "ignore_environment": 1,
        "safe_path": 1,
        "optimize": 0,
    }
    if flags != expected_flags or row["guard_meta_path_index"] != 0:
        raise P0ParserProcessProtocolError(
            "runtime guard flag/meta-path invariant mismatch"
        )
    specs = row["project_specs"]
    if not isinstance(specs, list) or len(specs) != 3:
        raise P0ParserProcessProtocolError(
            "runtime guard project spec accounting mismatch"
        )
    expected_modules = [
        "llm_batch",
        "llm_batch.grounding",
        "llm_batch.grounding.p0_parser_process_protocol",
    ]
    observed_modules: list[str] = []
    for index, value in enumerate(specs):
        item = _exact_mapping(
            value, _RUNTIME_GUARD_SPEC_FIELDS, f"project_specs[{index}]"
        )
        module_name = item["module_name"]
        if not isinstance(module_name, str):
            raise P0ParserProcessProtocolError("runtime guard module name is invalid")
        observed_modules.append(module_name)
        _sha(item["origin_sha256"], f"project_specs[{index}].origin_sha256")
        _sha(
            item["cached_path_sha256"],
            f"project_specs[{index}].cached_path_sha256",
        )
        locations = item["package_location_sha256s"]
        if not isinstance(locations, list):
            raise P0ParserProcessProtocolError(
                "runtime guard package-location digest list is invalid"
            )
        for location in locations:
            _sha(location, f"project_specs[{index}].package_location_sha256s")
        expected_location_count = 0 if module_name == expected_modules[-1] else 1
        if (
            len(locations) != expected_location_count
            or item["loader"] != "SourceFileLoader"
            or item["cached_under_bound_prefix_verified"] is not True
        ):
            raise P0ParserProcessProtocolError(
                "runtime guard project spec invariant mismatch"
            )
    if observed_modules != expected_modules or row["guard_finalized"] is not True:
        raise P0ParserProcessProtocolError(
            "runtime guard completion/module invariant mismatch"
        )
    return dict(row)


def validate_response_bytes(raw: bytes) -> dict[str, Any]:
    row = _exact_mapping(
        _parse_canonical_object(raw, label="parser response", maximum=MAX_RESPONSE_BYTES),
        _RESPONSE_FIELDS,
        "parser response",
    )
    if row["schema_version"] != RESPONSE_SCHEMA or row["operation"] != OPERATION:
        raise P0ParserProcessProtocolError("parser response schema/operation mismatch")
    _identifier(row["request_id"], "request_id")
    _identifier(row["parser_run_id"], "parser_run_id")
    _identifier(row["parser_version"], "parser_version")
    for field in (
        "request_sha256",
        "launch_sha256",
        "capture_manifest_sha256",
        "input_registry_sha256",
        "parser_manifest_sha256",
        "capture_observations_sha256",
        "receipt_sha256",
    ):
        _sha(row[field], field)
    count = _nonnegative_int(row["capture_count"], "capture_count")
    total = _nonnegative_int(row["total_payload_bytes"], "total_payload_bytes")
    if count < 1 or count > MAX_CAPTURE_COUNT:
        raise P0ParserProcessProtocolError(
            f"response capture_count must be within 1..{MAX_CAPTURE_COUNT}"
        )
    if total > MAX_TOTAL_CAPTURE_BYTES:
        raise P0ParserProcessProtocolError(
            "response total_payload_bytes exceeds the decoded byte limit"
        )
    observations = row["capture_observations"]
    if not isinstance(observations, list) or len(observations) != count:
        raise P0ParserProcessProtocolError("response capture accounting mismatch")
    seen: set[str] = set()
    observed_total = 0
    for index, value in enumerate(observations):
        item = _exact_mapping(
            value, _OBSERVATION_FIELDS, f"capture_observations[{index}]"
        )
        capture_id = _identifier(
            item["capture_id"], f"capture_observations[{index}].capture_id"
        )
        if capture_id in seen:
            raise P0ParserProcessProtocolError("response capture_id must be unique")
        seen.add(capture_id)
        observed_bytes = _nonnegative_int(
            item["payload_bytes"], f"capture_observations[{index}].payload_bytes"
        )
        if observed_bytes > MAX_CAPTURE_BYTES:
            raise P0ParserProcessProtocolError(
                f"capture_observations[{index}] exceeds the per-capture byte limit"
            )
        observed_total += observed_bytes
        _sha(item["payload_sha256"], f"capture_observations[{index}].payload_sha256")
    if total != observed_total or row["capture_observations_sha256"] != canonical_sha256(
        observations
    ):
        raise P0ParserProcessProtocolError("response observation binding mismatch")
    if (
        row["child_reported_capture_hash_probe_completed"] is not True
        or row["child_reported_capture_payload_accounting_complete"] is not True
        or (
            row["runtime_guard_attestation"] is None
            and row["child_reported_runtime_guard_completed"] is not False
        )
        or (
            row["runtime_guard_attestation"] is not None
            and (
                row["child_reported_runtime_guard_completed"] is not True
                or _validate_runtime_guard_attestation(
                    row["runtime_guard_attestation"]
                )
                != row["runtime_guard_attestation"]
            )
        )
        or any(row[field] is not False for field in FALSE_AUTHORITY_FIELDS)
        or row["credited_counts"]
        != {"actual_source_claim_count": 0, "actual_a_context_review_count": 0}
        or row["operational_effect"] != OPERATIONAL_EFFECT
        or row["gate_status"] != GATE_STATUS
    ):
        raise P0ParserProcessProtocolError("response gate/authority invariant mismatch")
    material = {key: value for key, value in row.items() if key != "receipt_sha256"}
    if row["receipt_sha256"] != canonical_sha256(material):
        raise P0ParserProcessProtocolError("response receipt self-hash mismatch")
    return dict(row)


def validate_response_against_request(
    response_raw: bytes, request_raw: bytes
) -> dict[str, Any]:
    """Parent-side exact request/response cross-binding validation.

    The child-reported completion flags remain diagnostics.  This function
    independently reparses the canonical request and recalculates every echo,
    capture observation, count, and hash before issuing a separate local
    cross-binding receipt.  It still grants no process provenance or authority.
    """

    request = parse_request_bytes(request_raw)
    response = validate_response_bytes(response_raw)
    expected_observations: list[dict[str, Any]] = []
    expected_total = 0
    for index, value in enumerate(request["captures"]):
        observation, payload = _decode_capture(value, index)
        expected_observations.append(observation)
        expected_total += len(payload)
    expected_echoes = {
        "request_id": request["request_id"],
        "parser_run_id": request["parser_run_id"],
        "request_sha256": hashlib.sha256(request_raw).hexdigest(),
        "launch_sha256": request["launch_sha256"],
        "capture_manifest_sha256": request["capture_manifest_sha256"],
        "input_registry_sha256": request["input_registry_sha256"],
        "parser_manifest_sha256": request["parser_manifest_sha256"],
        "parser_version": request["parser_version"],
        "capture_count": len(expected_observations),
        "total_payload_bytes": expected_total,
        "capture_observations": expected_observations,
        "capture_observations_sha256": canonical_sha256(expected_observations),
    }
    mismatches = [
        field
        for field, expected in expected_echoes.items()
        if response.get(field) != expected
    ]
    if mismatches:
        raise P0ParserProcessProtocolError(
            "child response/request cross-binding mismatch: "
            + ",".join(sorted(mismatches))
        )
    material = {
        "schema_version": CROSS_BINDING_SCHEMA,
        "request_sha256": expected_echoes["request_sha256"],
        "response_bytes_sha256": hashlib.sha256(response_raw).hexdigest(),
        "child_response_receipt_sha256": response["receipt_sha256"],
        "child_response_exact_cross_binding_verified": True,
        "child_reported_capture_hash_probe_completed": response[
            "child_reported_capture_hash_probe_completed"
        ],
        "child_reported_capture_payload_accounting_complete": response[
            "child_reported_capture_payload_accounting_complete"
        ],
        "child_reported_runtime_guard_completed": response[
            "child_reported_runtime_guard_completed"
        ],
        "runtime_guard_attestation_sha256": (
            canonical_sha256(response["runtime_guard_attestation"])
            if response["runtime_guard_attestation"] is not None
            else None
        ),
        **{field: False for field in FALSE_AUTHORITY_FIELDS},
        "credited_counts": {
            "actual_source_claim_count": 0,
            "actual_a_context_review_count": 0,
        },
        "operational_effect": OPERATIONAL_EFFECT,
        "gate_status": GATE_STATUS,
    }
    return {**material, "receipt_sha256": canonical_sha256(material)}


__all__ = [
    "GATE_STATUS",
    "CROSS_BINDING_SCHEMA",
    "FALSE_AUTHORITY_FIELDS",
    "MAX_CAPTURE_BYTES",
    "MAX_CAPTURE_COUNT",
    "MAX_REQUEST_BYTES",
    "MAX_RESPONSE_BYTES",
    "MAX_TOTAL_CAPTURE_BYTES",
    "OPERATION",
    "OPERATIONAL_EFFECT",
    "P0ParserProcessProtocolError",
    "REQUEST_SCHEMA",
    "RESPONSE_SCHEMA",
    "RUNTIME_GUARD_ATTESTATION_SCHEMA",
    "canonical_bytes",
    "canonical_file_bytes",
    "canonical_sha256",
    "execute_request_bytes",
    "parse_request_bytes",
    "validate_response_bytes",
    "validate_response_against_request",
]
