"""Standalone parent replay for presented neutral batch accounting.

The module imports only Python standard-library modules.  It independently
parses the presented V2 plan structure, bridge/precommit/result/receipt bytes,
replays every non-error neutral-core result from payload bytes, and rebuilds the
unreviewed observation/missed-span inventory.  It intentionally does not claim
full-frame, external owner, runtime, error-factuality, or actual-evidence
authority.
"""

from __future__ import annotations

import base64
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
import re
import unicodedata
from typing import Any, Mapping, Sequence


BRIDGE_ROW_SCHEMA = "p0_presented_registry_capture_bridge_row_v1"
BATCH_PRECOMMIT_SCHEMA = "p0_presented_neutral_batch_precommit_v1"
BATCH_RESULT_ROW_SCHEMA = "p0_presented_neutral_batch_result_row_v1"
BATCH_RECEIPT_SCHEMA = "p0_presented_neutral_batch_itt_receipt_v1"
UNREVIEWED_INVENTORY_SCHEMA = "p0_presented_neutral_batch_unreviewed_inventory_v1"
COMPONENT_MANIFEST_SCHEMA = "p0_presented_neutral_batch_component_manifest_v1"
PARENT_RECEIPT_SCHEMA = "p0_presented_neutral_batch_parent_validation_receipt_v1"

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
PARENT_GATE_STATUS = "PARENT_PRESENTED_BATCH_REPLAY_PASS_ACTUAL_AUTHORITY_NO_GO"
METRIC_STATUS = "NOT_ESTIMABLE_PRESENTED_ACCOUNTING_ONLY"
SAMPLING_UNIT = "SELECTED_INPUT_LINEAGE"

UPSTREAM_PLAN_SCHEMA = "p0_deterministic_stratified_srswor_plan_v2"
UPSTREAM_SELECTION_ALGORITHM = "SHA256_STRATIFIED_SRSWOR_WITHOUT_REPLACEMENT_V2"
UPSTREAM_FRAME_COMPONENT_MANIFEST_SHA256 = "efed07649c14cc2af0b0916ef6e6a04b39ad0c9147b97daec74428521287111b"
NEUTRAL_CORE_VERSION = "raw-captured-utf8-neutral-observation-core-v1"
NEUTRAL_CORE_MANIFEST_SHA256 = "7d57b8be8a126b6421bfe65f8c1b4402478071426385647c4b714848a1a31eac"
NEUTRAL_RESULT_SCHEMA = "p0_raw_capture_neutral_observation_result_v1"
NEUTRAL_OBSERVATION_SCHEMA = "p0_raw_capture_neutral_observation_v1"

MAX_METADATA_CHARS = 512
MAX_PAYLOAD_BYTES_PER_INPUT = 256 * 1024
MAX_TOTAL_PAYLOAD_BYTES = EXPECTED_INPUT_COUNT * MAX_PAYLOAD_BYTES_PER_INPUT
MAX_BRIDGE_JSONL_BYTES = 16 * 1024 * 1024
MAX_RESULTS_JSONL_BYTES = 32 * 1024 * 1024
MAX_ARTIFACT_BYTES = 32 * 1024 * 1024
MAX_DOCUMENT_CHARS = 64 * 1024
MAX_OBSERVATIONS = 64
MAX_SURFACE_CHARS = 512
MAX_DEFINITION_CHARS = 4096

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")
_PLATFORM_RE = re.compile(r"^[a-z0-9][a-z0-9._:-]{0,127}$")
_UTC_DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_UTC_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_FORBIDDEN_CATEGORIES = frozenset(("Cc", "Cf", "Cs", "Zl", "Zp"))
_FORBIDDEN_DOCUMENT_FORMAT = frozenset(("\u200b", "\u200c", "\u200d", "\ufeff"))
_FORBIDDEN_RELATION_CHARACTERS = frozenset(("'", '"', "\\", ".", "?", "!", "。", "！", "？", "…"))
_RELATIONS = (
    re.compile(
        r"^'(?P<surface>[^'\n]{1,512})'(?:은|는) "
        r"(?P<presented_definition>.+?)(?:을|를) 뜻한다\.$"
    ),
)

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
_UPSTREAM_FALSE_FIELDS = (
    "bounded_scope_completeness_verified",
    "external_owner_authority_verified",
    "enumeration_adapter_runtime_verified",
    "eligibility_factual_authority_verified",
    "lineage_factual_authority_verified",
    "seed_authority_verified",
    "seed_randomness_authority_verified",
    "probability_design_authority_verified",
    "capture_not_started_authority_verified",
    "code_identity_verified",
    "runtime_execution_verified",
    "actual_source_evidence_verified",
    "route_packet_runtime_credit_authority_verified",
    "actual_authority_granted",
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
_SELECTED_FIELDS = frozenset(
    {
        *_SELECTED_IDENTITY_FIELDS,
        "rank_sha256",
        "N_h",
        "n_h",
        "inclusion_probability_numerator",
        "inclusion_probability_denominator",
    }
)
_PLAN_FIELDS = frozenset(
    {
        "schema_version",
        "record_origin",
        "scope_sha256",
        "seed_receipt_sha256",
        "frame_manifest_sha256",
        "selection_algorithm",
        "derived_seed_sha256",
        "without_replacement",
        "spill_allowed",
        "replacement_allowed",
        "input_count",
        "per_profile_counts",
        "selected_inputs",
        "selected_input_set_sha256",
        "eligible_surplus_count",
        "eligible_surplus_sha256",
        "selection_sealed_at",
        "presented_serialization_only",
        *_UPSTREAM_FALSE_FIELDS,
        "gate_status",
        "action_applied",
        "operational_effect",
        "artifact_sha256",
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


class P0PresentedBatchParentValidationError(ValueError):
    """Standalone parent replay rejected the presented batch."""


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _file(value: Any) -> bytes:
    return _canonical(value) + b"\n"


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _raw_digest(value: bytes) -> str:
    if type(value) is not bytes:
        raise P0PresentedBatchParentValidationError("raw value must be exact bytes")
    return hashlib.sha256(value).hexdigest()


def _with_hash(value: Mapping[str, Any], field: str = "artifact_sha256") -> dict[str, Any]:
    material = dict(value)
    material.pop(field, None)
    return {**material, field: _digest(material)}


def _constant(value: str) -> None:
    raise P0PresentedBatchParentValidationError(f"non-finite number forbidden: {value}")


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise P0PresentedBatchParentValidationError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _object(raw: bytes, label: str, maximum: int = MAX_ARTIFACT_BYTES) -> dict[str, Any]:
    if type(raw) is not bytes or not raw or len(raw) > maximum:
        raise P0PresentedBatchParentValidationError(f"{label} byte length invalid")
    if raw.startswith(b"\xef\xbb\xbf") or b"\r" in raw:
        raise P0PresentedBatchParentValidationError(f"{label} BOM/CR forbidden")
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise P0PresentedBatchParentValidationError(f"{label} UTF-8 invalid") from exc
    if unicodedata.normalize("NFC", text) != text:
        raise P0PresentedBatchParentValidationError(f"{label} must be NFC")
    try:
        value = json.loads(text, object_pairs_hook=_pairs, parse_constant=_constant)
    except (json.JSONDecodeError, RecursionError, TypeError, ValueError) as exc:
        raise P0PresentedBatchParentValidationError(f"{label} JSON invalid") from exc
    if type(value) is not dict:
        raise P0PresentedBatchParentValidationError(f"{label} must be object")
    try:
        expected = _file(value)
    except (RecursionError, UnicodeEncodeError, TypeError, ValueError) as exc:
        raise P0PresentedBatchParentValidationError(f"{label} noncanonical") from exc
    if raw != expected:
        raise P0PresentedBatchParentValidationError(f"{label} canonical bytes mismatch")
    return value


def _jsonl(raw: bytes, label: str, maximum: int) -> list[dict[str, Any]]:
    if type(raw) is not bytes or not raw or len(raw) > maximum:
        raise P0PresentedBatchParentValidationError(f"{label} byte length invalid")
    if raw.startswith(b"\xef\xbb\xbf") or b"\r" in raw:
        raise P0PresentedBatchParentValidationError(f"{label} BOM/CR forbidden")
    if not raw.endswith(b"\n") or raw.endswith(b"\n\n"):
        raise P0PresentedBatchParentValidationError(f"{label} terminal LF invalid")
    rows: list[dict[str, Any]] = []
    for index, line in enumerate(raw[:-1].split(b"\n"), start=1):
        if not line:
            raise P0PresentedBatchParentValidationError(f"{label} blank row")
        rows.append(_object(line + b"\n", f"{label} row {index}", maximum))
    if len(rows) != EXPECTED_INPUT_COUNT:
        raise P0PresentedBatchParentValidationError(f"{label} must have exact 40 rows")
    return rows


def _strict(value: Any, fields: frozenset[str], label: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != fields:
        raise P0PresentedBatchParentValidationError(f"{label} field set mismatch")
    return value


def _sha(value: Any, field: str) -> str:
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        raise P0PresentedBatchParentValidationError(f"{field} invalid SHA-256")
    return value


def _id(value: Any, field: str) -> str:
    if type(value) is not str or _SAFE_ID_RE.fullmatch(value) is None:
        raise P0PresentedBatchParentValidationError(f"{field} invalid")
    return value


def _text(value: Any, field: str) -> str:
    if (
        type(value) is not str
        or not value
        or len(value) > MAX_METADATA_CHARS
        or value != value.strip()
        or unicodedata.normalize("NFC", value) != value
        or any(unicodedata.category(char) in _FORBIDDEN_CATEGORIES for char in value)
    ):
        raise P0PresentedBatchParentValidationError(f"{field} invalid text")
    return value


def _integer(value: Any, field: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise P0PresentedBatchParentValidationError(f"{field} invalid integer")
    return value


def _bool(value: Any, field: str) -> bool:
    if type(value) is not bool:
        raise P0PresentedBatchParentValidationError(f"{field} invalid boolean")
    return value


def _time(value: Any, field: str) -> datetime:
    if type(value) is not str or _UTC_TIMESTAMP_RE.fullmatch(value) is None:
        raise P0PresentedBatchParentValidationError(f"{field} invalid timestamp")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError as exc:
        raise P0PresentedBatchParentValidationError(
            f"{field} is not a real UTC timestamp"
        ) from exc
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
        raise P0PresentedBatchParentValidationError(f"{field} noncanonical timestamp")
    return parsed


def _self(row: Mapping[str, Any], field: str, label: str) -> None:
    stored = _sha(row[field], field)
    material = {key: value for key, value in row.items() if key != field}
    if stored != _digest(material):
        raise P0PresentedBatchParentValidationError(f"{label} self-hash mismatch")


def _false_authority(row: Mapping[str, Any], label: str) -> None:
    for field in _FALSE_AUTHORITY_FIELDS:
        if _bool(row[field], field) is not False:
            raise P0PresentedBatchParentValidationError(f"{label} overclaims {field}")
    if _bool(row["action_applied"], "action_applied") is not False:
        raise P0PresentedBatchParentValidationError(f"{label} action must be false")
    if row["operational_effect"] != OPERATIONAL_EFFECT:
        raise P0PresentedBatchParentValidationError(f"{label} effect mismatch")


def _plan(raw: bytes, expected_raw_sha256: str) -> dict[str, Any]:
    expected_pin = _sha(expected_raw_sha256, "expected_sampling_plan_raw_sha256")
    if _raw_digest(raw) != expected_pin:
        raise P0PresentedBatchParentValidationError("presented sampling plan pin mismatch")
    row = _strict(_object(raw, "sampling plan"), _PLAN_FIELDS, "sampling plan")
    if (
        row["schema_version"] != UPSTREAM_PLAN_SCHEMA
        or row["record_origin"] != RECORD_ORIGIN
        or row["selection_algorithm"] != UPSTREAM_SELECTION_ALGORITHM
        or row["operational_effect"] != OPERATIONAL_EFFECT
    ):
        raise P0PresentedBatchParentValidationError("sampling plan contract mismatch")
    for field in (
        "scope_sha256",
        "seed_receipt_sha256",
        "frame_manifest_sha256",
        "derived_seed_sha256",
        "selected_input_set_sha256",
        "eligible_surplus_sha256",
    ):
        _sha(row[field], field)
    if _bool(row["without_replacement"], "without_replacement") is not True:
        raise P0PresentedBatchParentValidationError("sampling plan replacement policy mismatch")
    for field in ("spill_allowed", "replacement_allowed"):
        if _bool(row[field], field) is not False:
            raise P0PresentedBatchParentValidationError(f"sampling plan {field} must be false")
    if _bool(row["presented_serialization_only"], "presented_serialization_only") is not True:
        raise P0PresentedBatchParentValidationError("sampling plan truth mismatch")
    for field in _UPSTREAM_FALSE_FIELDS:
        if _bool(row[field], field) is not False:
            raise P0PresentedBatchParentValidationError(f"sampling plan overclaims {field}")
    if _bool(row["action_applied"], "action_applied") is not False:
        raise P0PresentedBatchParentValidationError("sampling plan action must be false")
    if _integer(row["input_count"], "input_count", 1) != EXPECTED_INPUT_COUNT:
        raise P0PresentedBatchParentValidationError("sampling plan input count mismatch")
    expected_counts = {profile: EXPECTED_PER_PROFILE for profile in SOURCE_PROFILES}
    if row["per_profile_counts"] != expected_counts:
        raise P0PresentedBatchParentValidationError("sampling plan profile count mismatch")
    selected = row["selected_inputs"]
    if type(selected) is not list or len(selected) != EXPECTED_INPUT_COUNT:
        raise P0PresentedBatchParentValidationError("sampling plan selected inventory mismatch")
    candidates: set[str] = set()
    lineages: set[str] = set()
    profile_counts: Counter[str] = Counter()
    stratum_shapes: dict[str, tuple[str, str, str, int, int]] = {}
    for index, value in enumerate(selected, start=1):
        item = _strict(value, _SELECTED_FIELDS, f"selected input {index}")
        if _integer(item["input_sequence"], "input_sequence", 1) != index:
            raise P0PresentedBatchParentValidationError("selected input physical order mismatch")
        for field in (
            "candidate_id",
            "lineage_group_id",
            "adapter_id",
        ):
            _id(item[field], field)
        for field in (
            "locator_commitment_sha256",
            "lineage_unit_sha256",
            "rank_sha256",
        ):
            _sha(item[field], field)
        _id(item["stratum_id"], "stratum_id")
        if item["source_profile"] not in SOURCE_PROFILES:
            raise P0PresentedBatchParentValidationError("selected profile invalid")
        if type(item["platform"]) is not str or _PLATFORM_RE.fullmatch(item["platform"]) is None:
            raise P0PresentedBatchParentValidationError("selected platform invalid")
        if type(item["utc_day"]) is not str or _UTC_DAY_RE.fullmatch(item["utc_day"]) is None:
            raise P0PresentedBatchParentValidationError("selected UTC day invalid")
        for field in ("N_h", "n_h", "inclusion_probability_numerator", "inclusion_probability_denominator"):
            _integer(item[field], field, 1)
        if item["n_h"] > item["N_h"]:
            raise P0PresentedBatchParentValidationError("selected stratum fraction invalid")
        divisor = math.gcd(item["n_h"], item["N_h"])
        if (
            item["inclusion_probability_numerator"] != item["n_h"] // divisor
            or item["inclusion_probability_denominator"] != item["N_h"] // divisor
        ):
            raise P0PresentedBatchParentValidationError("selected nominal fraction mismatch")
        shape = (
            item["source_profile"],
            item["platform"],
            item["utc_day"],
            item["N_h"],
            item["n_h"],
        )
        prior_shape = stratum_shapes.setdefault(item["stratum_id"], shape)
        if prior_shape != shape:
            raise P0PresentedBatchParentValidationError("selected stratum shape mismatch")
        if item["candidate_id"] in candidates or item["lineage_group_id"] in lineages:
            raise P0PresentedBatchParentValidationError("selected replacement/lineage duplicate")
        candidates.add(item["candidate_id"])
        lineages.add(item["lineage_group_id"])
        profile_counts[item["source_profile"]] += 1
    if dict(profile_counts) != expected_counts:
        raise P0PresentedBatchParentValidationError("selected profile inventory mismatch")
    if row["selected_input_set_sha256"] != _digest(selected):
        raise P0PresentedBatchParentValidationError("selected input set hash mismatch")
    if _integer(row["eligible_surplus_count"], "eligible_surplus_count") < 0:
        raise P0PresentedBatchParentValidationError("eligible surplus count invalid")
    if row["gate_status"] != "NO_GO_DETERMINISTIC_EXAMPLE_PLAN_ONLY":
        raise P0PresentedBatchParentValidationError("sampling plan gate status mismatch")
    _time(row["selection_sealed_at"], "selection_sealed_at")
    _self(row, "artifact_sha256", "sampling plan")
    return row


def _bridge(raw: bytes, plan: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[bytes], int]:
    rows = _jsonl(raw, "bridge inventory", MAX_BRIDGE_JSONL_BYTES)
    payloads: list[bytes] = []
    total = 0
    registry_ids: set[str] = set()
    for index, (value, selected) in enumerate(zip(rows, plan["selected_inputs"]), start=1):
        row = _strict(value, _BRIDGE_ROW_FIELDS, f"bridge row {index}")
        if (
            row["schema_version"] != BRIDGE_ROW_SCHEMA
            or _integer(row["input_sequence"], "input_sequence", 1) != index
        ):
            raise P0PresentedBatchParentValidationError("bridge schema/order mismatch")
        for field in _SELECTED_IDENTITY_FIELDS:
            if row[field] != selected[field]:
                raise P0PresentedBatchParentValidationError(f"bridge selected mismatch: {field}")
        if row["selected_input_sha256"] != _digest(selected):
            raise P0PresentedBatchParentValidationError("bridge selected hash mismatch")
        registry_id = _id(row["registry_record_id"], "registry_record_id")
        if registry_id == selected["candidate_id"]:
            raise P0PresentedBatchParentValidationError(
                "frame candidate and registry record identities must remain distinct"
            )
        if registry_id in registry_ids:
            raise P0PresentedBatchParentValidationError("bridge registry duplicate")
        registry_ids.add(registry_id)
        _sha(row["registry_record_commitment_sha256"], "registry_record_commitment_sha256")
        for field in ("content_type", "capture_version", "normalization_version"):
            _text(row[field], field)
        encoded = row["payload_base64"]
        if type(encoded) is not str:
            raise P0PresentedBatchParentValidationError("payload_base64 invalid")
        try:
            payload = base64.b64decode(encoded.encode("ascii"), validate=True)
        except (UnicodeEncodeError, ValueError) as exc:
            raise P0PresentedBatchParentValidationError("payload_base64 invalid") from exc
        if base64.b64encode(payload).decode("ascii") != encoded:
            raise P0PresentedBatchParentValidationError("payload_base64 noncanonical")
        if len(payload) > MAX_PAYLOAD_BYTES_PER_INPUT:
            raise P0PresentedBatchParentValidationError("payload bound exceeded")
        if (
            _integer(row["payload_bytes"], "payload_bytes") != len(payload)
            or row["payload_sha256"] != _raw_digest(payload)
        ):
            raise P0PresentedBatchParentValidationError("payload binding mismatch")
        total += len(payload)
        if total > MAX_TOTAL_PAYLOAD_BYTES:
            raise P0PresentedBatchParentValidationError("total payload bound exceeded")
        _self(row, "bridge_row_sha256", f"bridge row {index}")
        payloads.append(payload)
    return rows, payloads, total


def _precommit(
    raw: bytes,
    *,
    plan_raw: bytes,
    plan: Mapping[str, Any],
    bridge_raw: bytes,
    bridge_rows: Sequence[Mapping[str, Any]],
    total_payload: int,
    expected_raw_sha256: str,
) -> dict[str, Any]:
    expected_pin = _sha(expected_raw_sha256, "expected_precommit_raw_sha256")
    if _raw_digest(raw) != expected_pin:
        raise P0PresentedBatchParentValidationError("presented precommit pin mismatch")
    row = _strict(_object(raw, "batch precommit"), _PRECOMMIT_FIELDS, "batch precommit")
    if (
        row["schema_version"] != BATCH_PRECOMMIT_SCHEMA
        or row["record_origin"] != RECORD_ORIGIN
        or row["component_version"] != COMPONENT_VERSION
        or row["upstream_sampling_plan_schema"] != UPSTREAM_PLAN_SCHEMA
        or row["neutral_core_version"] != NEUTRAL_CORE_VERSION
        or row["neutral_core_manifest_sha256"] != NEUTRAL_CORE_MANIFEST_SHA256
    ):
        raise P0PresentedBatchParentValidationError("precommit contract mismatch")
    expected_counts = {profile: EXPECTED_PER_PROFILE for profile in SOURCE_PROFILES}
    expected_values = {
        "upstream_sampling_plan_raw_sha256": _raw_digest(plan_raw),
        "upstream_sampling_plan_artifact_sha256": plan["artifact_sha256"],
        "upstream_selected_input_set_sha256": plan["selected_input_set_sha256"],
        "bridge_inventory_raw_sha256": _raw_digest(bridge_raw),
        "bridge_inventory_row_count": EXPECTED_INPUT_COUNT,
        "bridge_inventory_sha256": _digest(list(bridge_rows)),
        "total_payload_bytes": total_payload,
        "per_profile_input_counts": expected_counts,
        "expected_input_count": EXPECTED_INPUT_COUNT,
        "attempts_per_input": 1,
    }
    if any(row[field] != expected for field, expected in expected_values.items()):
        raise P0PresentedBatchParentValidationError("precommit exact binding mismatch")
    for field in ("retry_allowed", "replacement_allowed", "backfill_allowed", "spill_allowed"):
        if _bool(row[field], field) is not False:
            raise P0PresentedBatchParentValidationError(f"precommit {field} must be false")
    for field in ("presented_registry_capture_bridge_verified", "presented_precommit_only"):
        if _bool(row[field], field) is not True:
            raise P0PresentedBatchParentValidationError(f"precommit {field} must be true")
    _false_authority(row, "precommit")
    if _time(row["precommitted_at"], "precommitted_at") <= _time(plan["selection_sealed_at"], "selection_sealed_at"):
        raise P0PresentedBatchParentValidationError("precommit chronology mismatch")
    _self(row, "artifact_sha256", "precommit")
    return row


def _core_text_ok(value: str, maximum: int) -> bool:
    return (
        bool(value)
        and len(value) <= maximum
        and value == value.strip()
        and unicodedata.normalize("NFC", value) == value
        and not any(
            char in _FORBIDDEN_RELATION_CHARACTERS
            or char in _FORBIDDEN_DOCUMENT_FORMAT
            or unicodedata.category(char) in _FORBIDDEN_CATEGORIES
            for char in value
        )
    )


def _core_observation(
    sequence: int,
    line_number: int,
    document: str,
    start: int,
    end: int,
    surface: str,
    definition: str,
) -> dict[str, Any]:
    evidence = document[start:end]
    material = {
        "schema_version": NEUTRAL_OBSERVATION_SCHEMA,
        "observation_sequence": sequence,
        "line_number": line_number,
        "relation_kind": "PRESENTED_EXPLICIT_DEFINITION_STATEMENT",
        "character_span_start": start,
        "character_span_end": end,
        "utf8_byte_span_start": len(document[:start].encode("utf-8")),
        "utf8_byte_span_end": len(document[:end].encode("utf-8")),
        "evidence_text": evidence,
        "evidence_utf8_sha256": hashlib.sha256(evidence.encode("utf-8")).hexdigest(),
        "surface_text": surface,
        "surface_utf8_sha256": hashlib.sha256(surface.encode("utf-8")).hexdigest(),
        "presented_definition_text": definition,
        "presented_definition_utf8_sha256": hashlib.sha256(definition.encode("utf-8")).hexdigest(),
    }
    return {**material, "observation_sha256": _digest(material)}


def _core_result(
    bridge: Mapping[str, Any],
    payload: bytes,
    disposition: str,
    reason: str,
    line_count: int,
    nonempty_count: int,
    observations: list[dict[str, Any]],
) -> dict[str, Any]:
    material = {
        "schema_version": NEUTRAL_RESULT_SCHEMA,
        "core_version": NEUTRAL_CORE_VERSION,
        "core_manifest_sha256": NEUTRAL_CORE_MANIFEST_SHA256,
        "source_profile": bridge["source_profile"],
        "content_type": bridge["content_type"],
        "capture_version": bridge["capture_version"],
        "normalization_version": bridge["normalization_version"],
        "payload_bytes": len(payload),
        "payload_sha256": _raw_digest(payload),
        "disposition": disposition,
        "reason_code": reason,
        "line_count": line_count,
        "nonempty_line_count": nonempty_count,
        "observation_count": len(observations),
        "observations": observations,
        "observations_sha256": _digest(observations),
    }
    return {**material, "result_sha256": _digest(material)}


def _derive_core(bridge: Mapping[str, Any], payload: bytes) -> dict[str, Any]:
    profile = bridge["source_profile"]
    if not payload:
        return _core_result(bridge, payload, "INVALID_CAPTURE", "empty_payload", 0, 0, [])
    unsupported = {
        "OFFICIAL_STRUCTURED": "official_capture_adapter_not_bound",
        "MEDIA_OCR": "ocr_media_engine_transcript_provenance_not_bound",
        "GENERIC_FALLBACK": "generic_profile_requires_manual_lane",
    }.get(profile)
    if unsupported is not None:
        return _core_result(bridge, payload, "UNSUPPORTED_PROFILE", unsupported, 0, 0, [])
    if profile != "COMMUNITY_STRUCTURED":
        return _core_result(bridge, payload, "UNSUPPORTED_PROFILE", "unknown_source_profile", 0, 0, [])
    if (
        bridge["content_type"] != "text/plain; charset=utf-8"
        or bridge["capture_version"] != "normalized-community-explicit-statement-lines-v1"
        or bridge["normalization_version"] != "utf8_identity_v1"
    ):
        return _core_result(bridge, payload, "UNSUPPORTED_PROFILE", "community_capture_contract_mismatch", 0, 0, [])
    try:
        document = payload.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return _core_result(bridge, payload, "INVALID_CAPTURE", "invalid_utf8", 0, 0, [])
    invalid = None
    if document.startswith("\ufeff"):
        invalid = "utf8_bom_forbidden"
    elif "\x00" in document:
        invalid = "nul_forbidden"
    elif "\r" in document:
        invalid = "non_lf_line_ending"
    elif len(document) > MAX_DOCUMENT_CHARS:
        invalid = "document_character_limit_exceeded"
    elif unicodedata.normalize("NFC", document) != document:
        invalid = "document_not_nfc"
    elif any(char in _FORBIDDEN_DOCUMENT_FORMAT for char in document):
        invalid = "invisible_format_character_forbidden"
    if invalid is not None:
        return _core_result(bridge, payload, "INVALID_CAPTURE", invalid, 0, 0, [])
    lines = document.split("\n")
    if document.endswith("\n"):
        lines = lines[:-1]
    nonempty = [(index, line) for index, line in enumerate(lines, start=1) if line]
    matched: list[tuple[int, str, str, str]] = []
    for line_number, line in nonempty:
        relation = next((pattern.fullmatch(line) for pattern in _RELATIONS if pattern.fullmatch(line) is not None), None)
        if relation is None:
            continue
        surface = relation.group("surface")
        definition = relation.group("presented_definition")
        if _core_text_ok(surface, MAX_SURFACE_CHARS) and _core_text_ok(definition, MAX_DEFINITION_CHARS):
            matched.append((line_number, line, surface, definition))
    if not nonempty or len(matched) != len(nonempty):
        reason = "no_nonempty_statement" if not nonempty else "mixed_or_nonmatching_context_fail_closed"
        return _core_result(bridge, payload, "NO_MATCH", reason, len(lines), len(nonempty), [])
    if len(matched) > MAX_OBSERVATIONS:
        return _core_result(bridge, payload, "INVALID_CAPTURE", "observation_limit_exceeded", 0, 0, [])
    offsets: list[int] = []
    cursor = 0
    for line in lines:
        offsets.append(cursor)
        cursor += len(line) + 1
    observations = [
        _core_observation(
            sequence,
            line_number,
            document,
            offsets[line_number - 1],
            offsets[line_number - 1] + len(line),
            surface,
            definition,
        )
        for sequence, (line_number, line, surface, definition) in enumerate(matched, start=1)
    ]
    return _core_result(
        bridge,
        payload,
        "MATCHED",
        "all_nonempty_lines_are_explicit_definition_observations",
        len(lines),
        len(nonempty),
        observations,
    )


def _results(
    raw: bytes,
    bridge_rows: Sequence[Mapping[str, Any]],
    payloads: Sequence[bytes],
) -> tuple[list[dict[str, Any]], int]:
    rows = _jsonl(raw, "batch results", MAX_RESULTS_JSONL_BYTES)
    replayed = 0
    for index, (value, bridge, payload) in enumerate(zip(rows, bridge_rows, payloads), start=1):
        row = _strict(value, _RESULT_ROW_FIELDS, f"result row {index}")
        if (
            row["schema_version"] != BATCH_RESULT_ROW_SCHEMA
            or _integer(row["input_sequence"], "input_sequence", 1) != index
        ):
            raise P0PresentedBatchParentValidationError("result schema/order mismatch")
        bindings = {
            "frame_candidate_id": bridge["candidate_id"],
            "registry_record_id": bridge["registry_record_id"],
            "registry_record_commitment_sha256": bridge["registry_record_commitment_sha256"],
            "source_profile": bridge["source_profile"],
            "selected_input_sha256": bridge["selected_input_sha256"],
            "bridge_row_sha256": bridge["bridge_row_sha256"],
            "payload_sha256": bridge["payload_sha256"],
        }
        if any(row[field] != expected for field, expected in bindings.items()):
            raise P0PresentedBatchParentValidationError("result bridge binding mismatch")
        if (
            _integer(row["attempt_count"], "attempt_count", 1) != 1
            or _bool(row["retry_performed"], "retry_performed") is not False
            or _bool(row["replacement_performed"], "replacement_performed") is not False
        ):
            raise P0PresentedBatchParentValidationError("result retry/replacement mismatch")
        terminal = row["terminal_disposition"]
        if terminal not in TERMINAL_DISPOSITIONS:
            raise P0PresentedBatchParentValidationError("terminal disposition invalid")
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
                raise P0PresentedBatchParentValidationError("CORE_ERROR shape mismatch")
        else:
            expected_core = _derive_core(bridge, payload)
            presented_core = _strict(row["core_result"], _CORE_RESULT_FIELDS, "core result")
            observations = presented_core["observations"]
            if type(observations) is not list:
                raise P0PresentedBatchParentValidationError("core observations invalid")
            for obs_index, observation in enumerate(observations, start=1):
                item = _strict(observation, _CORE_OBSERVATION_FIELDS, f"core observation {obs_index}")
                if item["observation_sequence"] != obs_index:
                    raise P0PresentedBatchParentValidationError("core observation order mismatch")
            if _canonical(presented_core) != _canonical(expected_core):
                raise P0PresentedBatchParentValidationError("core result differs from independent replay")
            if (
                terminal != expected_core["disposition"]
                or row["core_result_sha256"] != expected_core["result_sha256"]
                or row["core_observations_sha256"] != expected_core["observations_sha256"]
                or observation_count != expected_core["observation_count"]
                or row["core_error_stage"] is not None
                or row["core_error_code"] is not None
                or row["core_error_presented_only"] is not False
            ):
                raise P0PresentedBatchParentValidationError("core result projection mismatch")
            replayed += 1
        _self(row, "result_row_sha256", f"result row {index}")
    return rows, replayed


def _receipt(
    raw: bytes,
    *,
    bridge_raw: bytes,
    precommit_raw: bytes,
    precommit: Mapping[str, Any],
    results_raw: bytes,
    result_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    row = _strict(_object(raw, "batch receipt"), _RECEIPT_FIELDS, "batch receipt")
    if row["schema_version"] != BATCH_RECEIPT_SCHEMA or row["record_origin"] != RECORD_ORIGIN or row["component_version"] != COMPONENT_VERSION:
        raise P0PresentedBatchParentValidationError("batch receipt contract mismatch")
    started = _time(row["batch_started_at"], "batch_started_at")
    completed = _time(row["batch_completed_at"], "batch_completed_at")
    sealed = _time(row["results_sealed_at"], "results_sealed_at")
    if started <= _time(precommit["precommitted_at"], "precommitted_at") or completed <= started or sealed <= completed:
        raise P0PresentedBatchParentValidationError("batch chronology mismatch")
    disposition = Counter(item["terminal_disposition"] for item in result_rows)
    profiles = Counter(item["source_profile"] for item in result_rows)
    disposition_counts = {name: disposition.get(name, 0) for name in TERMINAL_DISPOSITIONS}
    profile_counts = {name: profiles.get(name, 0) for name in SOURCE_PROFILES}
    errors = disposition_counts["CORE_ERROR"]
    observations = sum(item["observation_count"] for item in result_rows)
    expected = _with_hash(
        {
            "schema_version": BATCH_RECEIPT_SCHEMA,
            "record_origin": RECORD_ORIGIN,
            "component_version": COMPONENT_VERSION,
            "batch_precommit_raw_sha256": _raw_digest(precommit_raw),
            "batch_precommit_artifact_sha256": precommit["artifact_sha256"],
            "bridge_inventory_raw_sha256": _raw_digest(bridge_raw),
            "results_raw_sha256": _raw_digest(results_raw),
            "results_row_count": EXPECTED_INPUT_COUNT,
            "results_inventory_sha256": _digest(list(result_rows)),
            "batch_started_at": row["batch_started_at"],
            "batch_completed_at": row["batch_completed_at"],
            "results_sealed_at": row["results_sealed_at"],
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
    if raw != _file(expected):
        raise P0PresentedBatchParentValidationError("batch receipt differs from independent accounting")
    return row


def _unreviewed(
    raw: bytes,
    *,
    receipt_raw: bytes,
    receipt: Mapping[str, Any],
    results_raw: bytes,
    bridge_rows: Sequence[Mapping[str, Any]],
    result_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    row = _strict(_object(raw, "unreviewed inventory"), _UNREVIEWED_FIELDS, "unreviewed inventory")
    if row["schema_version"] != UNREVIEWED_INVENTORY_SCHEMA or row["record_origin"] != RECORD_ORIGIN or row["component_version"] != COMPONENT_VERSION:
        raise P0PresentedBatchParentValidationError("unreviewed inventory contract mismatch")
    if _time(row["review_inventory_sealed_at"], "review_inventory_sealed_at") <= _time(receipt["results_sealed_at"], "results_sealed_at"):
        raise P0PresentedBatchParentValidationError("unreviewed inventory chronology mismatch")
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
                        "contextual_observation_unit_sha256": _digest(
                            {"domain": "P0_BATCH_CONTEXTUAL_OBSERVATION_REVIEW_UNIT_V1", **material}
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
                "full_payload_missed_span_unit_sha256": _digest(
                    {"domain": "P0_BATCH_FULL_PAYLOAD_MISSED_SPAN_REVIEW_UNIT_V1", **missed_material}
                ),
            }
        )
    expected = _with_hash(
        {
            "schema_version": UNREVIEWED_INVENTORY_SCHEMA,
            "record_origin": RECORD_ORIGIN,
            "component_version": COMPONENT_VERSION,
            "batch_receipt_raw_sha256": _raw_digest(receipt_raw),
            "batch_receipt_artifact_sha256": receipt["artifact_sha256"],
            "results_raw_sha256": _raw_digest(results_raw),
            "contextual_observation_review_units": contextual,
            "contextual_observation_review_units_sha256": _digest(contextual),
            "contextual_observation_count": len(contextual),
            "full_payload_missed_span_review_units": missed,
            "full_payload_missed_span_review_units_sha256": _digest(missed),
            "full_payload_missed_span_input_count": EXPECTED_INPUT_COUNT,
            "human_reviewed_contextual_observation_count": 0,
            "human_reviewed_full_payload_input_count": 0,
            "unreviewed_contextual_observation_count": len(contextual),
            "unreviewed_full_payload_input_count": EXPECTED_INPUT_COUNT,
            "review_inventory_sealed_at": row["review_inventory_sealed_at"],
            "exhaustive_human_review_verified": False,
            **{field: False for field in _FALSE_AUTHORITY_FIELDS},
            "gate_status": "NO_GO_UNREVIEWED_INVENTORY_ONLY",
            "action_applied": False,
            "operational_effect": OPERATIONAL_EFFECT,
        }
    )
    if raw != _file(expected):
        raise P0PresentedBatchParentValidationError("unreviewed inventory differs from independent replay")
    return row


ARTIFACT_FIELDS = {
    "bridge_row": sorted(_BRIDGE_ROW_FIELDS),
    "batch_precommit": sorted(_PRECOMMIT_FIELDS),
    "batch_result_row": sorted(_RESULT_ROW_FIELDS),
    "batch_receipt": sorted(_RECEIPT_FIELDS),
    "contextual_review_unit": sorted(_CONTEXT_REVIEW_FIELDS),
    "missed_span_review_unit": sorted(_MISSED_SPAN_REVIEW_FIELDS),
    "unreviewed_inventory": sorted(_UNREVIEWED_FIELDS),
}
EXPECTED_COMPONENT_MANIFEST = {
    "schema_version": COMPONENT_MANIFEST_SCHEMA,
    "component": "p0_presented_batch_exact_accounting_v1_contract",
    "component_version": COMPONENT_VERSION,
    "record_origin": RECORD_ORIGIN,
    "bridge_row_schema": BRIDGE_ROW_SCHEMA,
    "batch_precommit_schema": BATCH_PRECOMMIT_SCHEMA,
    "batch_result_row_schema": BATCH_RESULT_ROW_SCHEMA,
    "batch_receipt_schema": BATCH_RECEIPT_SCHEMA,
    "unreviewed_inventory_schema": UNREVIEWED_INVENTORY_SCHEMA,
    "upstream_sampling_plan_schema": UPSTREAM_PLAN_SCHEMA,
    "upstream_frame_component_manifest_sha256": UPSTREAM_FRAME_COMPONENT_MANIFEST_SHA256,
    "neutral_core_version": NEUTRAL_CORE_VERSION,
    "neutral_core_manifest_sha256": NEUTRAL_CORE_MANIFEST_SHA256,
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
        "max_observations_per_input": MAX_OBSERVATIONS,
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
EXPECTED_COMPONENT_MANIFEST_SHA256 = _digest(EXPECTED_COMPONENT_MANIFEST)


def validate_batch_bundle_against_raw_inputs(
    *,
    sampling_plan_raw: bytes,
    expected_sampling_plan_raw_sha256: str,
    bridge_inventory_raw: bytes,
    batch_precommit_raw: bytes,
    expected_precommit_raw_sha256: str,
    results_raw: bytes,
    batch_receipt_raw: bytes,
    unreviewed_inventory_raw: bytes,
) -> dict[str, Any]:
    """Independently replay the presented batch from exact raw bytes."""

    plan = _plan(sampling_plan_raw, expected_sampling_plan_raw_sha256)
    bridges, payloads, total = _bridge(bridge_inventory_raw, plan)
    precommit = _precommit(
        batch_precommit_raw,
        plan_raw=sampling_plan_raw,
        plan=plan,
        bridge_raw=bridge_inventory_raw,
        bridge_rows=bridges,
        total_payload=total,
        expected_raw_sha256=expected_precommit_raw_sha256,
    )
    results, replayed = _results(results_raw, bridges, payloads)
    receipt = _receipt(
        batch_receipt_raw,
        bridge_raw=bridge_inventory_raw,
        precommit_raw=batch_precommit_raw,
        precommit=precommit,
        results_raw=results_raw,
        result_rows=results,
    )
    inventory = _unreviewed(
        unreviewed_inventory_raw,
        receipt_raw=batch_receipt_raw,
        receipt=receipt,
        results_raw=results_raw,
        bridge_rows=bridges,
        result_rows=results,
    )
    error_count = sum(row["terminal_disposition"] == "CORE_ERROR" for row in results)
    material = {
        "schema_version": PARENT_RECEIPT_SCHEMA,
        "expected_component_manifest_sha256": EXPECTED_COMPONENT_MANIFEST_SHA256,
        "sampling_plan_raw_sha256": _raw_digest(sampling_plan_raw),
        "bridge_inventory_raw_sha256": _raw_digest(bridge_inventory_raw),
        "batch_precommit_raw_sha256": _raw_digest(batch_precommit_raw),
        "results_raw_sha256": _raw_digest(results_raw),
        "batch_receipt_raw_sha256": _raw_digest(batch_receipt_raw),
        "unreviewed_inventory_raw_sha256": _raw_digest(unreviewed_inventory_raw),
        "presented_expected_sampling_plan_match_verified": True,
        "presented_expected_precommit_match_verified": True,
        "presented_plan_structure_verified": True,
        "parent_separate_implementation_batch_accounting_verified": True,
        "independent_non_error_core_replay_count": replayed,
        "presented_core_error_accounting_count": error_count,
        "itt_denominator": EXPECTED_INPUT_COUNT,
        "itt_accounted_input_count": EXPECTED_INPUT_COUNT,
        "contextual_observation_count": inventory["contextual_observation_count"],
        "full_payload_missed_span_input_count": EXPECTED_INPUT_COUNT,
        "unreviewed_contextual_observation_count": inventory[
            "unreviewed_contextual_observation_count"
        ],
        "unreviewed_full_payload_input_count": EXPECTED_INPUT_COUNT,
        "upstream_full_frame_replay_verified": False,
        "same_process_isolation_verified": False,
        "core_code_identity_verified": False,
        "parent_code_identity_verified": False,
        "external_owner_authority_verified": False,
        "external_registry_authority_verified": False,
        "external_capture_authority_verified": False,
        "trusted_time_verified": False,
        "hidden_retry_absence_verified": False,
        "core_error_factuality_verified": False,
        "runtime_execution_authority_verified": False,
        "route_packet_ledger_credit_verified": False,
        "actual_source_evidence_verified": False,
        "actual_source_credit_count": 0,
        "actual_context_credit_count": 0,
        "exhaustive_human_review_verified": False,
        "metric_status": METRIC_STATUS,
        "inferential_metrics_allowed": False,
        "complete_case_metrics_allowed": False,
        "observation_rows_are_sampling_units": False,
        "sampling_unit": SAMPLING_UNIT,
        "actual_authority_granted": False,
        "p0_phase_exit": False,
        "production_approval": False,
        "full_scan_approval": False,
        "gate_status": PARENT_GATE_STATUS,
    }
    return {**material, "receipt_sha256": _digest(material)}


__all__ = [
    "EXPECTED_COMPONENT_MANIFEST",
    "EXPECTED_COMPONENT_MANIFEST_SHA256",
    "P0PresentedBatchParentValidationError",
    "PARENT_GATE_STATUS",
    "PARENT_RECEIPT_SCHEMA",
    "validate_batch_bundle_against_raw_inputs",
]
