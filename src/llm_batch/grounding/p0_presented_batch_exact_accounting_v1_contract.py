"""Presented P0 neutral-observation batch accounting contract.

This pure component binds the exact 40 selected rows of the presented V2
sampling plan to an ordered registry/capture bridge, seals that inventory before
execution, records exactly one terminal result per input, and emits an
unreviewed observation/missed-span inventory.  It does not perform file or
network I/O and does not connect to the existing actual route, packet, ledger,
publication, or Slang DB paths.

The bridge, timestamps, CORE_ERROR rows, and execution are caller-presented.
They are not external registry/capture authority, trusted time, code identity,
or actual semantic evidence.  Every selected input remains in the fixed ITT
denominator, including unsupported, invalid, no-match, and CORE_ERROR rows.
"""

from __future__ import annotations

import base64
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import re
import unicodedata
from typing import Any, Mapping, Sequence

from . import p0_full_eligible_sampling_frame_v2_contract as frame_contract
from . import p0_source_profile_raw_parser_core as neutral_core


BRIDGE_ROW_SCHEMA = "p0_presented_registry_capture_bridge_row_v1"
BATCH_PRECOMMIT_SCHEMA = "p0_presented_neutral_batch_precommit_v1"
BATCH_RESULT_ROW_SCHEMA = "p0_presented_neutral_batch_result_row_v1"
BATCH_RECEIPT_SCHEMA = "p0_presented_neutral_batch_itt_receipt_v1"
UNREVIEWED_INVENTORY_SCHEMA = "p0_presented_neutral_batch_unreviewed_inventory_v1"
COMPONENT_MANIFEST_SCHEMA = "p0_presented_neutral_batch_component_manifest_v1"

COMPONENT_VERSION = "presented-neutral-batch-exact-accounting-v1"
RECORD_ORIGIN = "ACTUAL_SCHEMA_CONTRACT_EXAMPLE_ONLY"
OPERATIONAL_EFFECT = "NONE_SHADOW_ONLY"
EXPECTED_INPUT_COUNT = 40
EXPECTED_PER_PROFILE = 10
SOURCE_PROFILES = (
    "OFFICIAL_STRUCTURED",
    "COMMUNITY_STRUCTURED",
    "MEDIA_OCR",
    "GENERIC_FALLBACK",
)
TERMINAL_DISPOSITIONS = (
    "MATCHED",
    "NO_MATCH",
    "UNSUPPORTED_PROFILE",
    "INVALID_CAPTURE",
    "CORE_ERROR",
)
CORE_ERROR_CODE = "UNEXPECTED_CORE_EXCEPTION"
CORE_ERROR_STAGE = "CORE_EXECUTION"
GATE_STATUS = "NO_GO_PRESENTED_BATCH_ACCOUNTING_ONLY"
METRIC_STATUS = "NOT_ESTIMABLE_PRESENTED_ACCOUNTING_ONLY"
SAMPLING_UNIT = "SELECTED_INPUT_LINEAGE"

MAX_METADATA_CHARS = 512
MAX_PAYLOAD_BYTES_PER_INPUT = neutral_core.MAX_PAYLOAD_BYTES
MAX_TOTAL_PAYLOAD_BYTES = EXPECTED_INPUT_COUNT * MAX_PAYLOAD_BYTES_PER_INPUT
MAX_BRIDGE_JSONL_BYTES = 16 * 1024 * 1024
MAX_RESULTS_JSONL_BYTES = 32 * 1024 * 1024
MAX_ARTIFACT_BYTES = 32 * 1024 * 1024

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")
_UTC_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_FORBIDDEN_CATEGORIES = frozenset(("Cc", "Cf", "Cs", "Zl", "Zp"))

_FALSE_AUTHORITY_FIELDS = (
    "external_population_completeness_verified",
    "external_owner_authority_verified",
    "external_registry_authority_verified",
    "external_capture_authority_verified",
    "trusted_time_verified",
    "hidden_retry_absence_verified",
    "core_error_factuality_verified",
    "code_identity_verified",
    "dependency_closure_verified",
    "process_isolation_verified",
    "runtime_execution_authority_verified",
    "route_packet_ledger_credit_verified",
    "actual_source_evidence_verified",
    "actual_authority_granted",
    "p0_phase_exit",
    "production_approval",
    "full_scan_approval",
)

_SELECTED_IDENTITY_FIELDS = (
    "input_sequence",
    "candidate_id",
    "locator_commitment_sha256",
    "lineage_group_id",
    "lineage_unit_sha256",
    "adapter_id",
    "source_profile",
    "platform",
    "utc_day",
    "stratum_id",
)
_CALLER_INPUT_FIELDS = frozenset(
    {
        *_SELECTED_IDENTITY_FIELDS,
        "registry_record_id",
        "registry_record_commitment_sha256",
        "content_type",
        "capture_version",
        "normalization_version",
        "payload",
    }
)
_BRIDGE_ROW_FIELDS = frozenset(
    {
        "schema_version",
        *_SELECTED_IDENTITY_FIELDS,
        "selected_input_sha256",
        "registry_record_id",
        "registry_record_commitment_sha256",
        "content_type",
        "capture_version",
        "normalization_version",
        "payload_base64",
        "payload_bytes",
        "payload_sha256",
        "bridge_row_sha256",
    }
)
_PRECOMMIT_FIELDS = frozenset(
    {
        "schema_version",
        "record_origin",
        "component_version",
        "upstream_sampling_plan_schema",
        "upstream_sampling_plan_raw_sha256",
        "upstream_sampling_plan_artifact_sha256",
        "upstream_selected_input_set_sha256",
        "bridge_inventory_raw_sha256",
        "bridge_inventory_row_count",
        "bridge_inventory_sha256",
        "total_payload_bytes",
        "per_profile_input_counts",
        "neutral_core_version",
        "neutral_core_manifest_sha256",
        "expected_input_count",
        "attempts_per_input",
        "retry_allowed",
        "replacement_allowed",
        "backfill_allowed",
        "spill_allowed",
        "precommitted_at",
        "presented_registry_capture_bridge_verified",
        "presented_precommit_only",
        *_FALSE_AUTHORITY_FIELDS,
        "action_applied",
        "operational_effect",
        "artifact_sha256",
    }
)
_CORE_RESULT_FIELDS = frozenset(
    {
        "schema_version",
        "core_version",
        "core_manifest_sha256",
        "source_profile",
        "content_type",
        "capture_version",
        "normalization_version",
        "payload_bytes",
        "payload_sha256",
        "disposition",
        "reason_code",
        "line_count",
        "nonempty_line_count",
        "observation_count",
        "observations",
        "observations_sha256",
        "result_sha256",
    }
)
_CORE_OBSERVATION_FIELDS = frozenset(
    {
        "schema_version",
        "observation_sequence",
        "line_number",
        "relation_kind",
        "character_span_start",
        "character_span_end",
        "utf8_byte_span_start",
        "utf8_byte_span_end",
        "evidence_text",
        "evidence_utf8_sha256",
        "surface_text",
        "surface_utf8_sha256",
        "presented_definition_text",
        "presented_definition_utf8_sha256",
        "observation_sha256",
    }
)
_RESULT_ROW_FIELDS = frozenset(
    {
        "schema_version",
        "input_sequence",
        "frame_candidate_id",
        "registry_record_id",
        "registry_record_commitment_sha256",
        "source_profile",
        "selected_input_sha256",
        "bridge_row_sha256",
        "payload_sha256",
        "attempt_count",
        "retry_performed",
        "replacement_performed",
        "terminal_disposition",
        "core_result",
        "core_result_sha256",
        "core_observations_sha256",
        "observation_count",
        "core_error_stage",
        "core_error_code",
        "core_error_presented_only",
        "result_row_sha256",
    }
)
_RECEIPT_FIELDS = frozenset(
    {
        "schema_version",
        "record_origin",
        "component_version",
        "batch_precommit_raw_sha256",
        "batch_precommit_artifact_sha256",
        "bridge_inventory_raw_sha256",
        "results_raw_sha256",
        "results_row_count",
        "results_inventory_sha256",
        "batch_started_at",
        "batch_completed_at",
        "results_sealed_at",
        "itt_denominator",
        "itt_accounted_input_count",
        "core_result_count",
        "core_error_count",
        "total_observation_count",
        "per_profile_terminal_counts",
        "terminal_disposition_counts",
        "missing_input_count",
        "duplicate_result_count",
        "extra_result_count",
        "reordered_result_count",
        "replacement_result_count",
        "backfill_result_count",
        "retry_result_count",
        "all_selected_inputs_accounted_once",
        "core_error_included_in_itt",
        "without_replacement_preserved",
        "presented_batch_accounting_verified",
        "actual_source_credit_count",
        "actual_context_credit_count",
        "exhaustive_human_review_verified",
        "metric_status",
        "inferential_metrics_allowed",
        "complete_case_metrics_allowed",
        "observation_rows_are_sampling_units",
        "sampling_unit",
        *_FALSE_AUTHORITY_FIELDS,
        "gate_status",
        "action_applied",
        "operational_effect",
        "artifact_sha256",
    }
)
_CONTEXT_REVIEW_FIELDS = frozenset(
    {
        "review_unit_sequence",
        "input_sequence",
        "frame_candidate_id",
        "registry_record_id",
        "selected_input_sha256",
        "bridge_row_sha256",
        "payload_sha256",
        "core_result_sha256",
        "observation_sequence",
        "observation_sha256",
        "contextual_observation_unit_sha256",
    }
)
_MISSED_SPAN_REVIEW_FIELDS = frozenset(
    {
        "input_sequence",
        "frame_candidate_id",
        "registry_record_id",
        "selected_input_sha256",
        "bridge_row_sha256",
        "payload_sha256",
        "result_row_sha256",
        "terminal_disposition",
        "full_payload_missed_span_unit_sha256",
    }
)
_UNREVIEWED_FIELDS = frozenset(
    {
        "schema_version",
        "record_origin",
        "component_version",
        "batch_receipt_raw_sha256",
        "batch_receipt_artifact_sha256",
        "results_raw_sha256",
        "contextual_observation_review_units",
        "contextual_observation_review_units_sha256",
        "contextual_observation_count",
        "full_payload_missed_span_review_units",
        "full_payload_missed_span_review_units_sha256",
        "full_payload_missed_span_input_count",
        "human_reviewed_contextual_observation_count",
        "human_reviewed_full_payload_input_count",
        "unreviewed_contextual_observation_count",
        "unreviewed_full_payload_input_count",
        "review_inventory_sealed_at",
        "exhaustive_human_review_verified",
        *_FALSE_AUTHORITY_FIELDS,
        "gate_status",
        "action_applied",
        "operational_effect",
        "artifact_sha256",
    }
)


class P0PresentedBatchAccountingError(ValueError):
    """The presented batch accounting contract rejected an input."""


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


def raw_sha256(value: bytes) -> str:
    if type(value) is not bytes:
        raise P0PresentedBatchAccountingError("raw value must be exact bytes")
    return hashlib.sha256(value).hexdigest()


def with_self_hash(value: Mapping[str, Any], field: str = "artifact_sha256") -> dict[str, Any]:
    material = dict(value)
    material.pop(field, None)
    return {**material, field: canonical_sha256(material)}


def _reject_constant(value: str) -> None:
    raise P0PresentedBatchAccountingError(f"non-finite JSON number is forbidden: {value}")


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise P0PresentedBatchAccountingError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _decode_object(raw: bytes, label: str, maximum: int = MAX_ARTIFACT_BYTES) -> dict[str, Any]:
    if type(raw) is not bytes or not raw or len(raw) > maximum:
        raise P0PresentedBatchAccountingError(f"{label} byte length is invalid")
    if raw.startswith(b"\xef\xbb\xbf") or b"\r" in raw:
        raise P0PresentedBatchAccountingError(f"{label} BOM/CR is forbidden")
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise P0PresentedBatchAccountingError(f"{label} must be strict UTF-8") from exc
    if unicodedata.normalize("NFC", text) != text:
        raise P0PresentedBatchAccountingError(f"{label} must be NFC")
    try:
        value = json.loads(text, object_pairs_hook=_pairs, parse_constant=_reject_constant)
    except (json.JSONDecodeError, RecursionError, TypeError, ValueError) as exc:
        raise P0PresentedBatchAccountingError(f"{label} is invalid JSON") from exc
    if type(value) is not dict:
        raise P0PresentedBatchAccountingError(f"{label} must be an object")
    try:
        expected = canonical_file_bytes(value)
    except (RecursionError, UnicodeEncodeError, TypeError, ValueError) as exc:
        raise P0PresentedBatchAccountingError(f"{label} is noncanonical") from exc
    if raw != expected:
        raise P0PresentedBatchAccountingError(f"{label} must be canonical JSON plus LF")
    return value


def _decode_jsonl(raw: bytes, label: str, maximum: int) -> list[dict[str, Any]]:
    if type(raw) is not bytes or not raw or len(raw) > maximum:
        raise P0PresentedBatchAccountingError(f"{label} byte length is invalid")
    if raw.startswith(b"\xef\xbb\xbf") or b"\r" in raw:
        raise P0PresentedBatchAccountingError(f"{label} BOM/CR is forbidden")
    if not raw.endswith(b"\n") or raw.endswith(b"\n\n"):
        raise P0PresentedBatchAccountingError(f"{label} must end in exactly one LF")
    rows: list[dict[str, Any]] = []
    for index, line in enumerate(raw[:-1].split(b"\n"), start=1):
        if not line:
            raise P0PresentedBatchAccountingError(f"{label} blank row is forbidden")
        row = _decode_object(line + b"\n", f"{label} row {index}", maximum)
        rows.append(row)
    if len(rows) != EXPECTED_INPUT_COUNT:
        raise P0PresentedBatchAccountingError(
            f"{label} must contain exactly {EXPECTED_INPUT_COUNT} physical rows"
        )
    return rows


def _strict(value: Any, fields: frozenset[str], label: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != fields:
        raise P0PresentedBatchAccountingError(f"{label} field set mismatch")
    return value


def _sha(value: Any, field: str) -> str:
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        raise P0PresentedBatchAccountingError(f"{field} must be lowercase SHA-256")
    return value


def _identifier(value: Any, field: str) -> str:
    if type(value) is not str or _SAFE_ID_RE.fullmatch(value) is None:
        raise P0PresentedBatchAccountingError(f"{field} is invalid")
    return value


def _metadata(value: Any, field: str) -> str:
    if (
        type(value) is not str
        or not value
        or len(value) > MAX_METADATA_CHARS
        or value != value.strip()
        or unicodedata.normalize("NFC", value) != value
        or any(unicodedata.category(char) in _FORBIDDEN_CATEGORIES for char in value)
    ):
        raise P0PresentedBatchAccountingError(f"{field} must be canonical text")
    return value


def _integer(value: Any, field: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise P0PresentedBatchAccountingError(f"{field} must be an integer >= {minimum}")
    return value


def _boolean(value: Any, field: str) -> bool:
    if type(value) is not bool:
        raise P0PresentedBatchAccountingError(f"{field} must be boolean")
    return value


def _timestamp(value: Any, field: str) -> datetime:
    if type(value) is not str or _UTC_TIMESTAMP_RE.fullmatch(value) is None:
        raise P0PresentedBatchAccountingError(f"{field} must be strict UTC seconds")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError as exc:
        raise P0PresentedBatchAccountingError(f"{field} is not a real UTC timestamp") from exc
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
        raise P0PresentedBatchAccountingError(f"{field} is not canonical")
    return parsed


def _self_hash(row: Mapping[str, Any], field: str, label: str) -> None:
    digest = _sha(row[field], field)
    material = {key: value for key, value in row.items() if key != field}
    if digest != canonical_sha256(material):
        raise P0PresentedBatchAccountingError(f"{label} self-hash mismatch")


def _truth_false(row: Mapping[str, Any], label: str) -> None:
    for field in _FALSE_AUTHORITY_FIELDS:
        if _boolean(row[field], field) is not False:
            raise P0PresentedBatchAccountingError(f"{label} cannot claim {field}")
    if _boolean(row["action_applied"], "action_applied") is not False:
        raise P0PresentedBatchAccountingError(f"{label} must be shadow-only")
    if row["operational_effect"] != OPERATIONAL_EFFECT:
        raise P0PresentedBatchAccountingError(f"{label} operational effect mismatch")


def _validated_plan(
    *,
    scope_raw: bytes,
    census_raw: bytes,
    frame_manifest_raw: bytes,
    seed_receipt_raw: bytes,
    sampling_plan_raw: bytes,
) -> dict[str, Any]:
    return frame_contract.validate_sampling_plan_bytes(
        sampling_plan_raw,
        scope_raw,
        census_raw,
        seed_receipt_raw,
        frame_manifest_raw,
    )


def _validate_inputs(
    plan: Mapping[str, Any], batch_inputs: Sequence[Mapping[str, Any]]
) -> tuple[list[dict[str, Any]], int]:
    if not isinstance(batch_inputs, Sequence) or isinstance(batch_inputs, (str, bytes)):
        raise P0PresentedBatchAccountingError("batch inputs must be a sequence")
    if len(batch_inputs) != EXPECTED_INPUT_COUNT:
        raise P0PresentedBatchAccountingError("batch inputs must be exact selected 40")
    selected = plan["selected_inputs"]
    if len(selected) != EXPECTED_INPUT_COUNT:
        raise P0PresentedBatchAccountingError("upstream plan input count mismatch")
    rows: list[dict[str, Any]] = []
    total_payload = 0
    registry_ids: set[str] = set()
    for physical_index, (selected_row, value) in enumerate(
        zip(selected, batch_inputs), start=1
    ):
        row = _strict(value, _CALLER_INPUT_FIELDS, f"batch input {physical_index}")
        if _integer(row["input_sequence"], "input_sequence", 1) != physical_index:
            raise P0PresentedBatchAccountingError("batch input physical order mismatch")
        for field in _SELECTED_IDENTITY_FIELDS:
            if row[field] != selected_row[field]:
                raise P0PresentedBatchAccountingError(
                    f"batch input/selected plan identity mismatch: {field}"
                )
        registry_id = _identifier(row["registry_record_id"], "registry_record_id")
        if registry_id == selected_row["candidate_id"]:
            raise P0PresentedBatchAccountingError(
                "frame candidate and registry record identities must remain distinct"
            )
        if registry_id in registry_ids:
            raise P0PresentedBatchAccountingError("registry_record_id must be unique")
        registry_ids.add(registry_id)
        _sha(row["registry_record_commitment_sha256"], "registry_record_commitment_sha256")
        content_type = _metadata(row["content_type"], "content_type")
        capture_version = _metadata(row["capture_version"], "capture_version")
        normalization_version = _metadata(
            row["normalization_version"], "normalization_version"
        )
        payload = row["payload"]
        if type(payload) is not bytes or len(payload) > MAX_PAYLOAD_BYTES_PER_INPUT:
            raise P0PresentedBatchAccountingError("payload bytes exceed per-input bound")
        total_payload += len(payload)
        if total_payload > MAX_TOTAL_PAYLOAD_BYTES:
            raise P0PresentedBatchAccountingError("batch payload bytes exceed total bound")
        material = {
            "schema_version": BRIDGE_ROW_SCHEMA,
            **{field: selected_row[field] for field in _SELECTED_IDENTITY_FIELDS},
            "selected_input_sha256": canonical_sha256(selected_row),
            "registry_record_id": registry_id,
            "registry_record_commitment_sha256": row[
                "registry_record_commitment_sha256"
            ],
            "content_type": content_type,
            "capture_version": capture_version,
            "normalization_version": normalization_version,
            "payload_base64": base64.b64encode(payload).decode("ascii"),
            "payload_bytes": len(payload),
            "payload_sha256": raw_sha256(payload),
        }
        rows.append({**material, "bridge_row_sha256": canonical_sha256(material)})
    return rows, total_payload


def build_bridge_inventory_bytes(
    *,
    scope_raw: bytes,
    census_raw: bytes,
    frame_manifest_raw: bytes,
    seed_receipt_raw: bytes,
    sampling_plan_raw: bytes,
    batch_inputs: Sequence[Mapping[str, Any]],
) -> bytes:
    """Build exact 40-row presented registry/capture bridge JSONL."""

    plan = _validated_plan(
        scope_raw=scope_raw,
        census_raw=census_raw,
        frame_manifest_raw=frame_manifest_raw,
        seed_receipt_raw=seed_receipt_raw,
        sampling_plan_raw=sampling_plan_raw,
    )
    rows, _ = _validate_inputs(plan, batch_inputs)
    raw = b"".join(canonical_file_bytes(row) for row in rows)
    if len(raw) > MAX_BRIDGE_JSONL_BYTES:
        raise P0PresentedBatchAccountingError("bridge inventory byte bound exceeded")
    return raw


def _validate_bridge_rows(
    raw: bytes, plan: Mapping[str, Any]
) -> tuple[list[dict[str, Any]], list[bytes], int]:
    rows = _decode_jsonl(raw, "bridge inventory", MAX_BRIDGE_JSONL_BYTES)
    payloads: list[bytes] = []
    total = 0
    registry_ids: set[str] = set()
    for index, (value, selected) in enumerate(zip(rows, plan["selected_inputs"]), start=1):
        row = _strict(value, _BRIDGE_ROW_FIELDS, f"bridge row {index}")
        if (
            row["schema_version"] != BRIDGE_ROW_SCHEMA
            or _integer(row["input_sequence"], "input_sequence", 1) != index
        ):
            raise P0PresentedBatchAccountingError("bridge row schema/order mismatch")
        for field in _SELECTED_IDENTITY_FIELDS:
            if row[field] != selected[field]:
                raise P0PresentedBatchAccountingError(
                    f"bridge/selected plan identity mismatch: {field}"
                )
        if row["selected_input_sha256"] != canonical_sha256(selected):
            raise P0PresentedBatchAccountingError("selected input binding mismatch")
        registry_id = _identifier(row["registry_record_id"], "registry_record_id")
        if registry_id == selected["candidate_id"]:
            raise P0PresentedBatchAccountingError(
                "frame candidate and registry record identities must remain distinct"
            )
        if registry_id in registry_ids:
            raise P0PresentedBatchAccountingError("duplicate registry bridge row")
        registry_ids.add(registry_id)
        _sha(row["registry_record_commitment_sha256"], "registry_record_commitment_sha256")
        for field in ("content_type", "capture_version", "normalization_version"):
            _metadata(row[field], field)
        encoded = row["payload_base64"]
        if type(encoded) is not str:
            raise P0PresentedBatchAccountingError("payload_base64 must be text")
        try:
            payload = base64.b64decode(encoded.encode("ascii"), validate=True)
        except (UnicodeEncodeError, ValueError) as exc:
            raise P0PresentedBatchAccountingError("payload_base64 is invalid") from exc
        if base64.b64encode(payload).decode("ascii") != encoded:
            raise P0PresentedBatchAccountingError("payload_base64 is noncanonical")
        if len(payload) > MAX_PAYLOAD_BYTES_PER_INPUT:
            raise P0PresentedBatchAccountingError("decoded payload exceeds bound")
        if (
            _integer(row["payload_bytes"], "payload_bytes") != len(payload)
            or row["payload_sha256"] != raw_sha256(payload)
        ):
            raise P0PresentedBatchAccountingError("bridge payload binding mismatch")
        total += len(payload)
        if total > MAX_TOTAL_PAYLOAD_BYTES:
            raise P0PresentedBatchAccountingError("decoded batch payload exceeds bound")
        _self_hash(row, "bridge_row_sha256", f"bridge row {index}")
        payloads.append(payload)
    return rows, payloads, total


def build_batch_precommit_bytes(
    *,
    scope_raw: bytes,
    census_raw: bytes,
    frame_manifest_raw: bytes,
    seed_receipt_raw: bytes,
    sampling_plan_raw: bytes,
    bridge_inventory_raw: bytes,
    precommitted_at: str,
) -> bytes:
    plan = _validated_plan(
        scope_raw=scope_raw,
        census_raw=census_raw,
        frame_manifest_raw=frame_manifest_raw,
        seed_receipt_raw=seed_receipt_raw,
        sampling_plan_raw=sampling_plan_raw,
    )
    rows, _, total = _validate_bridge_rows(bridge_inventory_raw, plan)
    if _timestamp(precommitted_at, "precommitted_at") <= _timestamp(
        plan["selection_sealed_at"], "selection_sealed_at"
    ):
        raise P0PresentedBatchAccountingError("batch precommit must follow selection seal")
    counts = Counter(row["source_profile"] for row in rows)
    expected_counts = {profile: EXPECTED_PER_PROFILE for profile in SOURCE_PROFILES}
    if dict(counts) != expected_counts:
        raise P0PresentedBatchAccountingError("bridge profile counts must be exact 10x4")
    material = {
        "schema_version": BATCH_PRECOMMIT_SCHEMA,
        "record_origin": RECORD_ORIGIN,
        "component_version": COMPONENT_VERSION,
        "upstream_sampling_plan_schema": frame_contract.SAMPLING_PLAN_SCHEMA,
        "upstream_sampling_plan_raw_sha256": raw_sha256(sampling_plan_raw),
        "upstream_sampling_plan_artifact_sha256": plan["artifact_sha256"],
        "upstream_selected_input_set_sha256": plan["selected_input_set_sha256"],
        "bridge_inventory_raw_sha256": raw_sha256(bridge_inventory_raw),
        "bridge_inventory_row_count": len(rows),
        "bridge_inventory_sha256": canonical_sha256(rows),
        "total_payload_bytes": total,
        "per_profile_input_counts": expected_counts,
        "neutral_core_version": neutral_core.CORE_VERSION,
        "neutral_core_manifest_sha256": neutral_core.CORE_MANIFEST_SHA256,
        "expected_input_count": EXPECTED_INPUT_COUNT,
        "attempts_per_input": 1,
        "retry_allowed": False,
        "replacement_allowed": False,
        "backfill_allowed": False,
        "spill_allowed": False,
        "precommitted_at": precommitted_at,
        "presented_registry_capture_bridge_verified": True,
        "presented_precommit_only": True,
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
        "action_applied": False,
        "operational_effect": OPERATIONAL_EFFECT,
    }
    return canonical_file_bytes(with_self_hash(material))


def validate_batch_precommit_bytes(
    raw: bytes,
    *,
    scope_raw: bytes,
    census_raw: bytes,
    frame_manifest_raw: bytes,
    seed_receipt_raw: bytes,
    sampling_plan_raw: bytes,
    bridge_inventory_raw: bytes,
) -> dict[str, Any]:
    row = _strict(_decode_object(raw, "batch precommit"), _PRECOMMIT_FIELDS, "batch precommit")
    if row["schema_version"] != BATCH_PRECOMMIT_SCHEMA or row["record_origin"] != RECORD_ORIGIN:
        raise P0PresentedBatchAccountingError("batch precommit schema/origin mismatch")
    if row["component_version"] != COMPONENT_VERSION:
        raise P0PresentedBatchAccountingError("batch component version mismatch")
    if _boolean(row["presented_registry_capture_bridge_verified"], "presented_registry_capture_bridge_verified") is not True:
        raise P0PresentedBatchAccountingError("presented bridge flag must be true")
    if _boolean(row["presented_precommit_only"], "presented_precommit_only") is not True:
        raise P0PresentedBatchAccountingError("precommit must remain presented-only")
    for field in ("retry_allowed", "replacement_allowed", "backfill_allowed", "spill_allowed"):
        if _boolean(row[field], field) is not False:
            raise P0PresentedBatchAccountingError(f"{field} must be false")
    _truth_false(row, "batch precommit")
    _self_hash(row, "artifact_sha256", "batch precommit")
    expected = build_batch_precommit_bytes(
        scope_raw=scope_raw,
        census_raw=census_raw,
        frame_manifest_raw=frame_manifest_raw,
        seed_receipt_raw=seed_receipt_raw,
        sampling_plan_raw=sampling_plan_raw,
        bridge_inventory_raw=bridge_inventory_raw,
        precommitted_at=row["precommitted_at"],
    )
    if raw != expected:
        raise P0PresentedBatchAccountingError("batch precommit differs from exact recomputation")
    return dict(row)


def _validate_core_result(result: Any, bridge: Mapping[str, Any]) -> dict[str, Any]:
    row = _strict(result, _CORE_RESULT_FIELDS, "core result")
    if row["core_version"] != neutral_core.CORE_VERSION or row["core_manifest_sha256"] != neutral_core.CORE_MANIFEST_SHA256:
        raise P0PresentedBatchAccountingError("core result version/manifest mismatch")
    for field in ("source_profile", "content_type", "capture_version", "normalization_version"):
        if row[field] != bridge[field]:
            raise P0PresentedBatchAccountingError(f"core result input binding mismatch: {field}")
    if row["payload_bytes"] != bridge["payload_bytes"] or row["payload_sha256"] != bridge["payload_sha256"]:
        raise P0PresentedBatchAccountingError("core result payload binding mismatch")
    if row["disposition"] not in neutral_core.DISPOSITIONS:
        raise P0PresentedBatchAccountingError("core disposition mismatch")
    for field in ("payload_bytes", "line_count", "nonempty_line_count", "observation_count"):
        _integer(row[field], field)
    observations = row["observations"]
    if type(observations) is not list or len(observations) != row["observation_count"]:
        raise P0PresentedBatchAccountingError("core observation count mismatch")
    for index, observation in enumerate(observations, start=1):
        item = _strict(observation, _CORE_OBSERVATION_FIELDS, f"core observation {index}")
        if item["observation_sequence"] != index:
            raise P0PresentedBatchAccountingError("core observation order mismatch")
        _self_hash(item, "observation_sha256", f"core observation {index}")
    if row["observations_sha256"] != canonical_sha256(observations):
        raise P0PresentedBatchAccountingError("core observation inventory mismatch")
    _self_hash(row, "result_sha256", "core result")
    if row["disposition"] == "MATCHED" and not observations:
        raise P0PresentedBatchAccountingError("MATCHED must preserve observations")
    if row["disposition"] != "MATCHED" and observations:
        raise P0PresentedBatchAccountingError("non-MATCHED result cannot carry observations")
    return row


def _execute_rows(
    bridge_rows: Sequence[Mapping[str, Any]], payloads: Sequence[bytes]
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for bridge, payload in zip(bridge_rows, payloads):
        core_result: dict[str, Any] | None = None
        error = False
        try:
            candidate = neutral_core.parse_capture(
                source_profile=bridge["source_profile"],
                content_type=bridge["content_type"],
                capture_version=bridge["capture_version"],
                normalization_version=bridge["normalization_version"],
                payload=payload,
            )
            core_result = _validate_core_result(candidate, bridge)
        except Exception:
            error = True
            core_result = None
        disposition = CORE_ERROR_CODE if error else core_result["disposition"]
        terminal = "CORE_ERROR" if error else disposition
        material = {
            "schema_version": BATCH_RESULT_ROW_SCHEMA,
            "input_sequence": bridge["input_sequence"],
            "frame_candidate_id": bridge["candidate_id"],
            "registry_record_id": bridge["registry_record_id"],
            "registry_record_commitment_sha256": bridge[
                "registry_record_commitment_sha256"
            ],
            "source_profile": bridge["source_profile"],
            "selected_input_sha256": bridge["selected_input_sha256"],
            "bridge_row_sha256": bridge["bridge_row_sha256"],
            "payload_sha256": bridge["payload_sha256"],
            "attempt_count": 1,
            "retry_performed": False,
            "replacement_performed": False,
            "terminal_disposition": terminal,
            "core_result": core_result,
            "core_result_sha256": None if error else core_result["result_sha256"],
            "core_observations_sha256": None if error else core_result["observations_sha256"],
            "observation_count": 0 if error else core_result["observation_count"],
            "core_error_stage": CORE_ERROR_STAGE if error else None,
            "core_error_code": CORE_ERROR_CODE if error else None,
            "core_error_presented_only": error,
        }
        results.append({**material, "result_row_sha256": canonical_sha256(material)})
    return results


def _count_rows(rows: Sequence[Mapping[str, Any]]) -> tuple[dict[str, int], dict[str, int], int, int]:
    disposition = Counter(row["terminal_disposition"] for row in rows)
    profiles = Counter(row["source_profile"] for row in rows)
    disposition_counts = {name: disposition.get(name, 0) for name in TERMINAL_DISPOSITIONS}
    profile_counts = {name: profiles.get(name, 0) for name in SOURCE_PROFILES}
    errors = disposition_counts["CORE_ERROR"]
    observations = sum(row["observation_count"] for row in rows)
    return disposition_counts, profile_counts, errors, observations


def _build_receipt_value(
    *,
    precommit: Mapping[str, Any],
    bridge_inventory_raw: bytes,
    batch_precommit_raw: bytes,
    results_raw: bytes,
    result_rows: Sequence[Mapping[str, Any]],
    batch_started_at: str,
    batch_completed_at: str,
    results_sealed_at: str,
) -> dict[str, Any]:
    started = _timestamp(batch_started_at, "batch_started_at")
    completed = _timestamp(batch_completed_at, "batch_completed_at")
    sealed = _timestamp(results_sealed_at, "results_sealed_at")
    if started <= _timestamp(precommit["precommitted_at"], "precommitted_at"):
        raise P0PresentedBatchAccountingError("batch start must follow precommit")
    if completed <= started or sealed <= completed:
        raise P0PresentedBatchAccountingError("batch completion/results chronology invalid")
    disposition_counts, profile_counts, errors, observations = _count_rows(result_rows)
    if sum(disposition_counts.values()) != EXPECTED_INPUT_COUNT:
        raise P0PresentedBatchAccountingError("terminal disposition accounting mismatch")
    if profile_counts != {profile: EXPECTED_PER_PROFILE for profile in SOURCE_PROFILES}:
        raise P0PresentedBatchAccountingError("terminal profile accounting mismatch")
    return with_self_hash(
        {
            "schema_version": BATCH_RECEIPT_SCHEMA,
            "record_origin": RECORD_ORIGIN,
            "component_version": COMPONENT_VERSION,
            "batch_precommit_raw_sha256": raw_sha256(batch_precommit_raw),
            "batch_precommit_artifact_sha256": precommit["artifact_sha256"],
            "bridge_inventory_raw_sha256": raw_sha256(bridge_inventory_raw),
            "results_raw_sha256": raw_sha256(results_raw),
            "results_row_count": len(result_rows),
            "results_inventory_sha256": canonical_sha256(result_rows),
            "batch_started_at": batch_started_at,
            "batch_completed_at": batch_completed_at,
            "results_sealed_at": results_sealed_at,
            "itt_denominator": EXPECTED_INPUT_COUNT,
            "itt_accounted_input_count": EXPECTED_INPUT_COUNT,
            "core_result_count": EXPECTED_INPUT_COUNT - errors,
            "core_error_count": errors,
            "total_observation_count": observations,
            "per_profile_terminal_counts": profile_counts,
            "terminal_disposition_counts": disposition_counts,
            "missing_input_count": 0,
            "duplicate_result_count": 0,
            "extra_result_count": 0,
            "reordered_result_count": 0,
            "replacement_result_count": 0,
            "backfill_result_count": 0,
            "retry_result_count": 0,
            "all_selected_inputs_accounted_once": True,
            "core_error_included_in_itt": True,
            "without_replacement_preserved": True,
            "presented_batch_accounting_verified": True,
            "actual_source_credit_count": 0,
            "actual_context_credit_count": 0,
            "exhaustive_human_review_verified": False,
            "metric_status": METRIC_STATUS,
            "inferential_metrics_allowed": False,
            "complete_case_metrics_allowed": False,
            "observation_rows_are_sampling_units": False,
            "sampling_unit": SAMPLING_UNIT,
            **{field: False for field in _FALSE_AUTHORITY_FIELDS},
            "gate_status": GATE_STATUS,
            "action_applied": False,
            "operational_effect": OPERATIONAL_EFFECT,
        }
    )


def execute_presented_batch(
    *,
    scope_raw: bytes,
    census_raw: bytes,
    frame_manifest_raw: bytes,
    seed_receipt_raw: bytes,
    sampling_plan_raw: bytes,
    bridge_inventory_raw: bytes,
    batch_precommit_raw: bytes,
    batch_started_at: str,
    batch_completed_at: str,
    results_sealed_at: str,
) -> tuple[bytes, bytes]:
    """Execute exactly one in-process neutral-core attempt per presented input."""

    plan = _validated_plan(
        scope_raw=scope_raw,
        census_raw=census_raw,
        frame_manifest_raw=frame_manifest_raw,
        seed_receipt_raw=seed_receipt_raw,
        sampling_plan_raw=sampling_plan_raw,
    )
    bridge_rows, payloads, _ = _validate_bridge_rows(bridge_inventory_raw, plan)
    precommit = validate_batch_precommit_bytes(
        batch_precommit_raw,
        scope_raw=scope_raw,
        census_raw=census_raw,
        frame_manifest_raw=frame_manifest_raw,
        seed_receipt_raw=seed_receipt_raw,
        sampling_plan_raw=sampling_plan_raw,
        bridge_inventory_raw=bridge_inventory_raw,
    )
    result_rows = _execute_rows(bridge_rows, payloads)
    results_raw = b"".join(canonical_file_bytes(row) for row in result_rows)
    if len(results_raw) > MAX_RESULTS_JSONL_BYTES:
        raise P0PresentedBatchAccountingError("results JSONL byte bound exceeded")
    receipt = _build_receipt_value(
        precommit=precommit,
        bridge_inventory_raw=bridge_inventory_raw,
        batch_precommit_raw=batch_precommit_raw,
        results_raw=results_raw,
        result_rows=result_rows,
        batch_started_at=batch_started_at,
        batch_completed_at=batch_completed_at,
        results_sealed_at=results_sealed_at,
    )
    return results_raw, canonical_file_bytes(receipt)


def _validate_result_rows(
    raw: bytes, bridge_rows: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    rows = _decode_jsonl(raw, "batch results", MAX_RESULTS_JSONL_BYTES)
    for index, (value, bridge) in enumerate(zip(rows, bridge_rows), start=1):
        row = _strict(value, _RESULT_ROW_FIELDS, f"result row {index}")
        if (
            row["schema_version"] != BATCH_RESULT_ROW_SCHEMA
            or _integer(row["input_sequence"], "input_sequence", 1) != index
        ):
            raise P0PresentedBatchAccountingError("result physical order mismatch")
        exact = {
            "frame_candidate_id": bridge["candidate_id"],
            "registry_record_id": bridge["registry_record_id"],
            "registry_record_commitment_sha256": bridge["registry_record_commitment_sha256"],
            "source_profile": bridge["source_profile"],
            "selected_input_sha256": bridge["selected_input_sha256"],
            "bridge_row_sha256": bridge["bridge_row_sha256"],
            "payload_sha256": bridge["payload_sha256"],
        }
        if any(row[field] != expected for field, expected in exact.items()):
            raise P0PresentedBatchAccountingError("result/bridge identity mismatch")
        if _integer(row["attempt_count"], "attempt_count", 1) != 1:
            raise P0PresentedBatchAccountingError("exactly one core attempt is required")
        if _boolean(row["retry_performed"], "retry_performed") is not False or _boolean(row["replacement_performed"], "replacement_performed") is not False:
            raise P0PresentedBatchAccountingError("retry/replacement is forbidden")
        terminal = row["terminal_disposition"]
        if terminal not in TERMINAL_DISPOSITIONS:
            raise P0PresentedBatchAccountingError("terminal disposition is invalid")
        observation_count = _integer(row["observation_count"], "observation_count")
        if terminal == "CORE_ERROR":
            if (
                row["core_result"] is not None
                or row["core_result_sha256"] is not None
                or row["core_observations_sha256"] is not None
                or observation_count != 0
                or row["core_error_stage"] != CORE_ERROR_STAGE
                or row["core_error_code"] != CORE_ERROR_CODE
                or row["core_error_presented_only"] is not True
            ):
                raise P0PresentedBatchAccountingError("CORE_ERROR row shape mismatch")
        else:
            core_result = _validate_core_result(row["core_result"], bridge)
            if (
                terminal != core_result["disposition"]
                or row["core_result_sha256"] != core_result["result_sha256"]
                or row["core_observations_sha256"] != core_result["observations_sha256"]
                or observation_count != core_result["observation_count"]
                or row["core_error_stage"] is not None
                or row["core_error_code"] is not None
                or row["core_error_presented_only"] is not False
            ):
                raise P0PresentedBatchAccountingError("core result row projection mismatch")
        _self_hash(row, "result_row_sha256", f"result row {index}")
    return rows


def validate_batch_receipt_bytes(
    receipt_raw: bytes,
    *,
    scope_raw: bytes,
    census_raw: bytes,
    frame_manifest_raw: bytes,
    seed_receipt_raw: bytes,
    sampling_plan_raw: bytes,
    bridge_inventory_raw: bytes,
    batch_precommit_raw: bytes,
    results_raw: bytes,
) -> dict[str, Any]:
    plan = _validated_plan(
        scope_raw=scope_raw,
        census_raw=census_raw,
        frame_manifest_raw=frame_manifest_raw,
        seed_receipt_raw=seed_receipt_raw,
        sampling_plan_raw=sampling_plan_raw,
    )
    bridge_rows, _, _ = _validate_bridge_rows(bridge_inventory_raw, plan)
    result_rows = _validate_result_rows(results_raw, bridge_rows)
    row = _strict(_decode_object(receipt_raw, "batch receipt"), _RECEIPT_FIELDS, "batch receipt")
    if row["schema_version"] != BATCH_RECEIPT_SCHEMA or row["record_origin"] != RECORD_ORIGIN:
        raise P0PresentedBatchAccountingError("batch receipt schema/origin mismatch")
    for field in (
        "all_selected_inputs_accounted_once",
        "core_error_included_in_itt",
        "without_replacement_preserved",
        "presented_batch_accounting_verified",
    ):
        if _boolean(row[field], field) is not True:
            raise P0PresentedBatchAccountingError(f"{field} must be true")
    if _boolean(row["exhaustive_human_review_verified"], "exhaustive_human_review_verified") is not False:
        raise P0PresentedBatchAccountingError("batch receipt cannot claim human review")
    if (
        row["metric_status"] != METRIC_STATUS
        or _boolean(row["inferential_metrics_allowed"], "inferential_metrics_allowed") is not False
        or _boolean(row["complete_case_metrics_allowed"], "complete_case_metrics_allowed") is not False
        or _boolean(row["observation_rows_are_sampling_units"], "observation_rows_are_sampling_units") is not False
        or row["sampling_unit"] != SAMPLING_UNIT
    ):
        raise P0PresentedBatchAccountingError("batch metric boundary mismatch")
    _truth_false(row, "batch receipt")
    _self_hash(row, "artifact_sha256", "batch receipt")
    precommit = validate_batch_precommit_bytes(
        batch_precommit_raw,
        scope_raw=scope_raw,
        census_raw=census_raw,
        frame_manifest_raw=frame_manifest_raw,
        seed_receipt_raw=seed_receipt_raw,
        sampling_plan_raw=sampling_plan_raw,
        bridge_inventory_raw=bridge_inventory_raw,
    )
    expected = _build_receipt_value(
        precommit=precommit,
        bridge_inventory_raw=bridge_inventory_raw,
        batch_precommit_raw=batch_precommit_raw,
        results_raw=results_raw,
        result_rows=result_rows,
        batch_started_at=row["batch_started_at"],
        batch_completed_at=row["batch_completed_at"],
        results_sealed_at=row["results_sealed_at"],
    )
    if receipt_raw != canonical_file_bytes(expected):
        raise P0PresentedBatchAccountingError("batch receipt exact recomputation mismatch")
    return dict(row)


def build_unreviewed_inventory_bytes(
    receipt_raw: bytes,
    *,
    scope_raw: bytes,
    census_raw: bytes,
    frame_manifest_raw: bytes,
    seed_receipt_raw: bytes,
    sampling_plan_raw: bytes,
    bridge_inventory_raw: bytes,
    batch_precommit_raw: bytes,
    results_raw: bytes,
    review_inventory_sealed_at: str,
) -> bytes:
    receipt = validate_batch_receipt_bytes(
        receipt_raw,
        scope_raw=scope_raw,
        census_raw=census_raw,
        frame_manifest_raw=frame_manifest_raw,
        seed_receipt_raw=seed_receipt_raw,
        sampling_plan_raw=sampling_plan_raw,
        bridge_inventory_raw=bridge_inventory_raw,
        batch_precommit_raw=batch_precommit_raw,
        results_raw=results_raw,
    )
    sealed = _timestamp(review_inventory_sealed_at, "review_inventory_sealed_at")
    if sealed <= _timestamp(receipt["results_sealed_at"], "results_sealed_at"):
        raise P0PresentedBatchAccountingError("review inventory must follow results seal")
    plan = _validated_plan(
        scope_raw=scope_raw,
        census_raw=census_raw,
        frame_manifest_raw=frame_manifest_raw,
        seed_receipt_raw=seed_receipt_raw,
        sampling_plan_raw=sampling_plan_raw,
    )
    bridge_rows, _, _ = _validate_bridge_rows(bridge_inventory_raw, plan)
    result_rows = _validate_result_rows(results_raw, bridge_rows)
    contextual: list[dict[str, Any]] = []
    missed: list[dict[str, Any]] = []
    for bridge, result in zip(bridge_rows, result_rows):
        core_result = result["core_result"]
        if core_result is not None:
            for observation in core_result["observations"]:
                material = {
                    "review_unit_sequence": len(contextual) + 1,
                    "input_sequence": bridge["input_sequence"],
                    "frame_candidate_id": bridge["candidate_id"],
                    "registry_record_id": bridge["registry_record_id"],
                    "selected_input_sha256": bridge["selected_input_sha256"],
                    "bridge_row_sha256": bridge["bridge_row_sha256"],
                    "payload_sha256": bridge["payload_sha256"],
                    "core_result_sha256": core_result["result_sha256"],
                    "observation_sequence": observation["observation_sequence"],
                    "observation_sha256": observation["observation_sha256"],
                }
                contextual.append(
                    {
                        **material,
                        "contextual_observation_unit_sha256": canonical_sha256(
                            {
                                "domain": "P0_BATCH_CONTEXTUAL_OBSERVATION_REVIEW_UNIT_V1",
                                **material,
                            }
                        ),
                    }
                )
        missed_material = {
            "input_sequence": bridge["input_sequence"],
            "frame_candidate_id": bridge["candidate_id"],
            "registry_record_id": bridge["registry_record_id"],
            "selected_input_sha256": bridge["selected_input_sha256"],
            "bridge_row_sha256": bridge["bridge_row_sha256"],
            "payload_sha256": bridge["payload_sha256"],
            "result_row_sha256": result["result_row_sha256"],
            "terminal_disposition": result["terminal_disposition"],
        }
        missed.append(
            {
                **missed_material,
                "full_payload_missed_span_unit_sha256": canonical_sha256(
                    {
                        "domain": "P0_BATCH_FULL_PAYLOAD_MISSED_SPAN_REVIEW_UNIT_V1",
                        **missed_material,
                    }
                ),
            }
        )
    material = {
        "schema_version": UNREVIEWED_INVENTORY_SCHEMA,
        "record_origin": RECORD_ORIGIN,
        "component_version": COMPONENT_VERSION,
        "batch_receipt_raw_sha256": raw_sha256(receipt_raw),
        "batch_receipt_artifact_sha256": receipt["artifact_sha256"],
        "results_raw_sha256": raw_sha256(results_raw),
        "contextual_observation_review_units": contextual,
        "contextual_observation_review_units_sha256": canonical_sha256(contextual),
        "contextual_observation_count": len(contextual),
        "full_payload_missed_span_review_units": missed,
        "full_payload_missed_span_review_units_sha256": canonical_sha256(missed),
        "full_payload_missed_span_input_count": len(missed),
        "human_reviewed_contextual_observation_count": 0,
        "human_reviewed_full_payload_input_count": 0,
        "unreviewed_contextual_observation_count": len(contextual),
        "unreviewed_full_payload_input_count": len(missed),
        "review_inventory_sealed_at": review_inventory_sealed_at,
        "exhaustive_human_review_verified": False,
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
        "gate_status": "NO_GO_UNREVIEWED_INVENTORY_ONLY",
        "action_applied": False,
        "operational_effect": OPERATIONAL_EFFECT,
    }
    return canonical_file_bytes(with_self_hash(material))


def validate_unreviewed_inventory_bytes(
    raw: bytes,
    *,
    receipt_raw: bytes,
    scope_raw: bytes,
    census_raw: bytes,
    frame_manifest_raw: bytes,
    seed_receipt_raw: bytes,
    sampling_plan_raw: bytes,
    bridge_inventory_raw: bytes,
    batch_precommit_raw: bytes,
    results_raw: bytes,
) -> dict[str, Any]:
    row = _strict(_decode_object(raw, "unreviewed inventory"), _UNREVIEWED_FIELDS, "unreviewed inventory")
    if row["schema_version"] != UNREVIEWED_INVENTORY_SCHEMA or row["record_origin"] != RECORD_ORIGIN:
        raise P0PresentedBatchAccountingError("unreviewed inventory schema/origin mismatch")
    if row["exhaustive_human_review_verified"] is not False:
        raise P0PresentedBatchAccountingError("unreviewed inventory cannot claim review completion")
    contextual = row["contextual_observation_review_units"]
    missed = row["full_payload_missed_span_review_units"]
    if type(contextual) is not list or type(missed) is not list:
        raise P0PresentedBatchAccountingError("review inventories must be lists")
    for index, item in enumerate(contextual, start=1):
        unit = _strict(item, _CONTEXT_REVIEW_FIELDS, f"context review unit {index}")
        if unit["review_unit_sequence"] != index:
            raise P0PresentedBatchAccountingError("context review unit order mismatch")
    for index, item in enumerate(missed, start=1):
        unit = _strict(item, _MISSED_SPAN_REVIEW_FIELDS, f"missed-span unit {index}")
        if unit["input_sequence"] != index:
            raise P0PresentedBatchAccountingError("missed-span input order mismatch")
    _truth_false(row, "unreviewed inventory")
    _self_hash(row, "artifact_sha256", "unreviewed inventory")
    expected = build_unreviewed_inventory_bytes(
        receipt_raw,
        scope_raw=scope_raw,
        census_raw=census_raw,
        frame_manifest_raw=frame_manifest_raw,
        seed_receipt_raw=seed_receipt_raw,
        sampling_plan_raw=sampling_plan_raw,
        bridge_inventory_raw=bridge_inventory_raw,
        batch_precommit_raw=batch_precommit_raw,
        results_raw=results_raw,
        review_inventory_sealed_at=row["review_inventory_sealed_at"],
    )
    if raw != expected:
        raise P0PresentedBatchAccountingError("unreviewed inventory differs from recomputation")
    return dict(row)


ARTIFACT_FIELDS = {
    "bridge_row": sorted(_BRIDGE_ROW_FIELDS),
    "batch_precommit": sorted(_PRECOMMIT_FIELDS),
    "batch_result_row": sorted(_RESULT_ROW_FIELDS),
    "batch_receipt": sorted(_RECEIPT_FIELDS),
    "contextual_review_unit": sorted(_CONTEXT_REVIEW_FIELDS),
    "missed_span_review_unit": sorted(_MISSED_SPAN_REVIEW_FIELDS),
    "unreviewed_inventory": sorted(_UNREVIEWED_FIELDS),
}

COMPONENT_MANIFEST = {
    "schema_version": COMPONENT_MANIFEST_SCHEMA,
    "component": "p0_presented_batch_exact_accounting_v1_contract",
    "component_version": COMPONENT_VERSION,
    "record_origin": RECORD_ORIGIN,
    "bridge_row_schema": BRIDGE_ROW_SCHEMA,
    "batch_precommit_schema": BATCH_PRECOMMIT_SCHEMA,
    "batch_result_row_schema": BATCH_RESULT_ROW_SCHEMA,
    "batch_receipt_schema": BATCH_RECEIPT_SCHEMA,
    "unreviewed_inventory_schema": UNREVIEWED_INVENTORY_SCHEMA,
    "upstream_sampling_plan_schema": frame_contract.SAMPLING_PLAN_SCHEMA,
    "upstream_frame_component_manifest_sha256": frame_contract.COMPONENT_MANIFEST_SHA256,
    "neutral_core_version": neutral_core.CORE_VERSION,
    "neutral_core_manifest_sha256": neutral_core.CORE_MANIFEST_SHA256,
    "expected_input_count": EXPECTED_INPUT_COUNT,
    "expected_per_profile": EXPECTED_PER_PROFILE,
    "source_profiles": list(SOURCE_PROFILES),
    "terminal_dispositions": list(TERMINAL_DISPOSITIONS),
    "core_error_stage": CORE_ERROR_STAGE,
    "core_error_code": CORE_ERROR_CODE,
    "attempts_per_input": 1,
    "retry_allowed": False,
    "replacement_allowed": False,
    "backfill_allowed": False,
    "spill_allowed": False,
    "physical_jsonl_order_required": True,
    "core_error_in_itt_denominator": True,
    "frame_candidate_and_registry_id_distinct": True,
    "contextual_observation_domain": "P0_BATCH_CONTEXTUAL_OBSERVATION_REVIEW_UNIT_V1",
    "full_payload_missed_span_domain": "P0_BATCH_FULL_PAYLOAD_MISSED_SPAN_REVIEW_UNIT_V1",
    "artifact_fields": ARTIFACT_FIELDS,
    "limits": {
        "max_payload_bytes_per_input": MAX_PAYLOAD_BYTES_PER_INPUT,
        "max_total_payload_bytes": MAX_TOTAL_PAYLOAD_BYTES,
        "max_bridge_jsonl_bytes": MAX_BRIDGE_JSONL_BYTES,
        "max_results_jsonl_bytes": MAX_RESULTS_JSONL_BYTES,
        "max_observations_per_input": neutral_core.MAX_OBSERVATIONS,
    },
    "chronology": [
        "upstream_selection_seal",
        "presented_registry_capture_bridge",
        "batch_precommit",
        "one_core_attempt_per_input",
        "physical_result_jsonl_seal",
        "unreviewed_observation_and_missed_span_inventory_seal",
    ],
    "direct_io_capabilities": [],
    "semantic_target_fields_used": False,
    "actual_source_credit_count": 0,
    "actual_context_credit_count": 0,
    "metric_status": METRIC_STATUS,
    "inferential_metrics_allowed": False,
    "complete_case_metrics_allowed": False,
    "observation_rows_are_sampling_units": False,
    "sampling_unit": SAMPLING_UNIT,
    **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    "exhaustive_human_review_verified": False,
    "action_applied": False,
    "operational_effect": OPERATIONAL_EFFECT,
}
COMPONENT_MANIFEST_SHA256 = canonical_sha256(COMPONENT_MANIFEST)


__all__ = [
    "ARTIFACT_FIELDS",
    "BATCH_PRECOMMIT_SCHEMA",
    "BATCH_RECEIPT_SCHEMA",
    "BATCH_RESULT_ROW_SCHEMA",
    "BRIDGE_ROW_SCHEMA",
    "COMPONENT_MANIFEST",
    "COMPONENT_MANIFEST_SCHEMA",
    "COMPONENT_MANIFEST_SHA256",
    "COMPONENT_VERSION",
    "CORE_ERROR_CODE",
    "CORE_ERROR_STAGE",
    "EXPECTED_INPUT_COUNT",
    "EXPECTED_PER_PROFILE",
    "GATE_STATUS",
    "MAX_BRIDGE_JSONL_BYTES",
    "MAX_PAYLOAD_BYTES_PER_INPUT",
    "MAX_RESULTS_JSONL_BYTES",
    "MAX_TOTAL_PAYLOAD_BYTES",
    "METRIC_STATUS",
    "OPERATIONAL_EFFECT",
    "P0PresentedBatchAccountingError",
    "RECORD_ORIGIN",
    "SAMPLING_UNIT",
    "SOURCE_PROFILES",
    "TERMINAL_DISPOSITIONS",
    "UNREVIEWED_INVENTORY_SCHEMA",
    "build_batch_precommit_bytes",
    "build_bridge_inventory_bytes",
    "build_unreviewed_inventory_bytes",
    "canonical_bytes",
    "canonical_file_bytes",
    "canonical_sha256",
    "execute_presented_batch",
    "raw_sha256",
    "validate_batch_precommit_bytes",
    "validate_batch_receipt_bytes",
    "validate_unreviewed_inventory_bytes",
    "with_self_hash",
]
