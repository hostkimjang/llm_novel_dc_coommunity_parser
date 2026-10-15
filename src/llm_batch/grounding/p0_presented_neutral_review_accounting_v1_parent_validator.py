"""Standalone replay for presented neutral-review accounting v1.

This module intentionally imports only the standard library.  It independently
reconstructs the forty input-review units from presented bridge/result/
unreviewed artifacts, checks roster, assignment, precommit, terminal review
rows, span arithmetic, and the receipt.  It does not claim to replay the full
upstream sampling/batch execution or establish reviewer/human authority.
"""

from __future__ import annotations

import base64
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
import re
import unicodedata
from typing import Any, Mapping, Sequence


REVIEWER_ROW_SCHEMA = "p0_presented_neutral_reviewer_row_v1"
REVIEW_UNIT_ROW_SCHEMA = "p0_presented_neutral_input_review_unit_v1"
ASSIGNMENT_ROW_SCHEMA = "p0_presented_neutral_review_assignment_v1"
REVIEW_PRECOMMIT_SCHEMA = "p0_presented_neutral_review_precommit_v1"
GOLD_SPAN_SCHEMA = "p0_presented_neutral_gold_span_v1"
OBSERVATION_ADJUDICATION_SCHEMA = "p0_presented_neutral_observation_adjudication_v1"
REVIEW_RESULT_ROW_SCHEMA = "p0_presented_neutral_input_review_result_v1"
REVIEW_RECEIPT_SCHEMA = "p0_presented_neutral_review_accounting_receipt_v1"
COMPONENT_MANIFEST_SCHEMA = "p0_presented_neutral_review_component_manifest_v1"
PARENT_RECEIPT_SCHEMA = "p0_presented_neutral_review_parent_receipt_v1"

COMPONENT_VERSION = "presented-neutral-review-accounting-v1"
RECORD_ORIGIN = "ACTUAL_SCHEMA_CONTRACT_EXAMPLE_ONLY"
OPERATIONAL_EFFECT = "NONE_SHADOW_ONLY"
UPSTREAM_COMPONENT_MANIFEST_SHA256 = "c7beb367d62a4af025643d42caddf20caccb4938cd5a68dac8b649ee49b165c1"
EXPECTED_INPUT_COUNT = 40
MAX_REVIEWERS = 16
MAX_GOLD_SPANS_PER_INPUT = 5041
MAX_DOCUMENT_CHARS = 64 * 1024
MIN_RELATION_LINE_CHARS = 12
MAX_METADATA_CHARS = 512
MAX_SURFACE_CHARS = 512
MAX_DEFINITION_CHARS = 4096
MAX_JSON_BYTES = 32 * 1024 * 1024
MAX_JSONL_BYTES = 32 * 1024 * 1024
ANNOTATION_STATUSES = ("JUDGED", "UNAVAILABLE", "UNJUDGED")
OBSERVATION_VERDICTS = ("CONFIRMED", "SPURIOUS")
RELATION_KIND = "PRESENTED_EXPLICIT_DEFINITION_STATEMENT"
SAMPLING_UNIT = "SELECTED_INPUT_LINEAGE"
METRIC_STATUS = "NOT_ESTIMABLE_PRESENTED_REVIEW_ONLY"
GATE_STATUS = "NO_GO_PRESENTED_REVIEW_ACCOUNTING_ONLY"
PARENT_GATE_STATUS = "NO_GO_STANDALONE_PRESENTED_REVIEW_REPLAY_ONLY"
UPSTREAM_BRIDGE_SCHEMA = "p0_presented_registry_capture_bridge_row_v1"
UPSTREAM_RESULT_SCHEMA = "p0_presented_neutral_batch_result_row_v1"
UPSTREAM_UNREVIEWED_SCHEMA = "p0_presented_neutral_batch_unreviewed_inventory_v1"
UPSTREAM_COMPONENT_VERSION = "presented-neutral-batch-exact-accounting-v1"
UPSTREAM_PLAN_SCHEMA = "p0_deterministic_stratified_srswor_plan_v2"
UPSTREAM_BATCH_PRECOMMIT_SCHEMA = "p0_presented_neutral_batch_precommit_v1"
UPSTREAM_BATCH_RECEIPT_SCHEMA = "p0_presented_neutral_batch_itt_receipt_v1"
UPSTREAM_SELECTION_ALGORITHM = "SHA256_STRATIFIED_SRSWOR_WITHOUT_REPLACEMENT_V2"
UPSTREAM_NEUTRAL_CORE_VERSION = "raw-captured-utf8-neutral-observation-core-v1"
UPSTREAM_NEUTRAL_CORE_MANIFEST_SHA256 = "7d57b8be8a126b6421bfe65f8c1b4402478071426385647c4b714848a1a31eac"
SOURCE_PROFILES = ("OFFICIAL_STRUCTURED", "COMMUNITY_STRUCTURED", "MEDIA_OCR", "GENERIC_FALLBACK")
TERMINAL_DISPOSITIONS = ("MATCHED", "NO_MATCH", "UNSUPPORTED_PROFILE", "INVALID_CAPTURE", "CORE_ERROR")

_STATUS_REASON = {
    "JUDGED": "PRESENTED_FULL_PAYLOAD_REVIEW_RECORDED",
    "UNAVAILABLE": "PRESENTED_REVIEW_UNAVAILABLE",
    "UNJUDGED": "PRESENTED_REVIEW_NOT_COMPLETED",
}
_SHA_RE = re.compile(r"^[0-9a-f]{64}$")
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")
_TIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_PLATFORM_RE = re.compile(r"^[a-z0-9][a-z0-9._:-]{0,127}$")
_UTC_DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_RELATION_RE = re.compile(
    r"^'(?P<surface>[^'\n]{1,512})'(?:은|는) "
    r"(?P<presented_definition>.+?)(?:을|를) 뜻한다\.$"
)
_FORBIDDEN_CATEGORIES = frozenset(("Cc", "Cf", "Cs", "Zl", "Zp"))
_FORBIDDEN_SEMANTIC_FIELDS = frozenset(
    {
        "target_work_id", "target_sense_id", "alias_relation", "truth_label",
        "work_id", "sense_id", "retrieval_query", "route_class",
        "publication_decision", "credit_count", "free_form_note",
        "reviewer_name", "reviewer_email",
    }
)
_FALSE_AUTHORITY_FIELDS = (
    "reviewer_identity_authority_verified",
    "reviewer_assignment_factuality_verified",
    "reviewer_independence_verified",
    "reviewer_blinding_verified",
    "human_judgment_factuality_verified",
    "gold_span_semantic_factuality_verified",
    "gold_span_completeness_factuality_verified",
    "trusted_time_verified",
    "code_identity_verified",
    "dependency_closure_verified",
    "process_isolation_verified",
    "runtime_execution_authority_verified",
    "route_packet_ledger_credit_verified",
    "actual_source_evidence_verified",
    "actual_authority_granted",
    "exhaustive_human_review_verified",
    "p0_phase_exit",
    "production_approval",
    "full_scan_approval",
)
_UPSTREAM_FALSE_FIELDS = (
    "external_population_completeness_verified", "external_owner_authority_verified",
    "external_registry_authority_verified", "external_capture_authority_verified",
    "trusted_time_verified", "hidden_retry_absence_verified", "core_error_factuality_verified",
    "code_identity_verified", "dependency_closure_verified", "process_isolation_verified",
    "runtime_execution_authority_verified", "route_packet_ledger_credit_verified",
    "actual_source_evidence_verified", "actual_authority_granted", "p0_phase_exit",
    "production_approval", "full_scan_approval",
)
_UPSTREAM_PLAN_FALSE_FIELDS = (
    "bounded_scope_completeness_verified", "external_owner_authority_verified",
    "enumeration_adapter_runtime_verified", "eligibility_factual_authority_verified",
    "lineage_factual_authority_verified", "seed_authority_verified",
    "seed_randomness_authority_verified", "probability_design_authority_verified",
    "capture_not_started_authority_verified", "code_identity_verified",
    "runtime_execution_verified", "actual_source_evidence_verified",
    "route_packet_runtime_credit_authority_verified", "actual_authority_granted",
    "production_approval", "full_scan_approval",
)

_SELECTED_IDENTITY_FIELDS = (
    "input_sequence", "candidate_id", "locator_commitment_sha256", "lineage_group_id",
    "lineage_unit_sha256", "adapter_id", "source_profile", "platform", "utc_day", "stratum_id",
)
_SELECTED_FIELDS = frozenset(
    {*_SELECTED_IDENTITY_FIELDS, "rank_sha256", "N_h", "n_h",
     "inclusion_probability_numerator", "inclusion_probability_denominator"}
)
_PLAN_FIELDS = frozenset(
    {
        "schema_version", "record_origin", "scope_sha256", "seed_receipt_sha256",
        "frame_manifest_sha256", "selection_algorithm", "derived_seed_sha256",
        "without_replacement", "spill_allowed", "replacement_allowed", "input_count",
        "per_profile_counts", "selected_inputs", "selected_input_set_sha256",
        "eligible_surplus_count", "eligible_surplus_sha256", "selection_sealed_at",
        "presented_serialization_only", *_UPSTREAM_PLAN_FALSE_FIELDS, "gate_status",
        "action_applied", "operational_effect", "artifact_sha256",
    }
)
_UPSTREAM_PRECOMMIT_FIELDS = frozenset(
    {
        "schema_version", "record_origin", "component_version", "upstream_sampling_plan_schema",
        "upstream_sampling_plan_raw_sha256", "upstream_sampling_plan_artifact_sha256",
        "upstream_selected_input_set_sha256", "bridge_inventory_raw_sha256",
        "bridge_inventory_row_count", "bridge_inventory_sha256", "total_payload_bytes",
        "per_profile_input_counts", "neutral_core_version", "neutral_core_manifest_sha256",
        "expected_input_count", "attempts_per_input", "retry_allowed", "replacement_allowed",
        "backfill_allowed", "spill_allowed", "precommitted_at",
        "presented_registry_capture_bridge_verified", "presented_precommit_only",
        *_UPSTREAM_FALSE_FIELDS, "action_applied", "operational_effect", "artifact_sha256",
    }
)
_UPSTREAM_RECEIPT_FIELDS = frozenset(
    {
        "schema_version", "record_origin", "component_version", "batch_precommit_raw_sha256",
        "batch_precommit_artifact_sha256", "bridge_inventory_raw_sha256", "results_raw_sha256",
        "results_row_count", "results_inventory_sha256", "batch_started_at", "batch_completed_at",
        "results_sealed_at", "itt_denominator", "itt_accounted_input_count", "core_result_count",
        "core_error_count", "total_observation_count", "per_profile_terminal_counts",
        "terminal_disposition_counts", "missing_input_count", "duplicate_result_count",
        "extra_result_count", "reordered_result_count", "replacement_result_count",
        "backfill_result_count", "retry_result_count", "all_selected_inputs_accounted_once",
        "core_error_included_in_itt", "without_replacement_preserved",
        "presented_batch_accounting_verified", "actual_source_credit_count",
        "actual_context_credit_count", "exhaustive_human_review_verified", "metric_status",
        "inferential_metrics_allowed", "complete_case_metrics_allowed",
        "observation_rows_are_sampling_units", "sampling_unit", *_UPSTREAM_FALSE_FIELDS,
        "gate_status", "action_applied", "operational_effect", "artifact_sha256",
    }
)

_BRIDGE_FIELDS = frozenset(
    {
        "schema_version", "input_sequence", "candidate_id", "locator_commitment_sha256",
        "lineage_group_id", "lineage_unit_sha256", "adapter_id", "source_profile",
        "platform", "utc_day", "stratum_id", "selected_input_sha256",
        "registry_record_id", "registry_record_commitment_sha256", "content_type",
        "capture_version", "normalization_version", "payload_base64", "payload_bytes",
        "payload_sha256", "bridge_row_sha256",
    }
)
_CORE_OBSERVATION_FIELDS = frozenset(
    {
        "schema_version", "observation_sequence", "line_number", "relation_kind",
        "character_span_start", "character_span_end", "utf8_byte_span_start",
        "utf8_byte_span_end", "evidence_text", "evidence_utf8_sha256", "surface_text",
        "surface_utf8_sha256", "presented_definition_text",
        "presented_definition_utf8_sha256", "observation_sha256",
    }
)
_CORE_RESULT_FIELDS = frozenset(
    {
        "schema_version", "core_version", "core_manifest_sha256", "source_profile",
        "content_type", "capture_version", "normalization_version", "payload_bytes",
        "payload_sha256", "disposition", "reason_code", "line_count",
        "nonempty_line_count", "observation_count", "observations",
        "observations_sha256", "result_sha256",
    }
)
_BATCH_RESULT_FIELDS = frozenset(
    {
        "schema_version", "input_sequence", "frame_candidate_id", "registry_record_id",
        "registry_record_commitment_sha256", "source_profile", "selected_input_sha256",
        "bridge_row_sha256", "payload_sha256", "attempt_count", "retry_performed",
        "replacement_performed", "terminal_disposition", "core_result",
        "core_result_sha256", "core_observations_sha256", "observation_count",
        "core_error_stage", "core_error_code", "core_error_presented_only",
        "result_row_sha256",
    }
)
_CONTEXT_FIELDS = frozenset(
    {
        "review_unit_sequence", "input_sequence", "frame_candidate_id",
        "registry_record_id", "selected_input_sha256", "bridge_row_sha256",
        "payload_sha256", "core_result_sha256", "observation_sequence",
        "observation_sha256", "contextual_observation_unit_sha256",
    }
)
_MISSED_FIELDS = frozenset(
    {
        "input_sequence", "frame_candidate_id", "registry_record_id",
        "selected_input_sha256", "bridge_row_sha256", "payload_sha256",
        "result_row_sha256", "terminal_disposition",
        "full_payload_missed_span_unit_sha256",
    }
)
_UNREVIEWED_FIELDS = frozenset(
    {
        "schema_version", "record_origin", "component_version", "batch_receipt_raw_sha256",
        "batch_receipt_artifact_sha256", "results_raw_sha256",
        "contextual_observation_review_units", "contextual_observation_review_units_sha256",
        "contextual_observation_count", "full_payload_missed_span_review_units",
        "full_payload_missed_span_review_units_sha256", "full_payload_missed_span_input_count",
        "human_reviewed_contextual_observation_count", "human_reviewed_full_payload_input_count",
        "unreviewed_contextual_observation_count", "unreviewed_full_payload_input_count",
        "review_inventory_sealed_at", "exhaustive_human_review_verified",
        *_UPSTREAM_FALSE_FIELDS, "gate_status", "action_applied", "operational_effect",
        "artifact_sha256",
    }
)
_REVIEWER_FIELDS = frozenset(
    {"schema_version", "reviewer_sequence", "reviewer_id", "identity_commitment_sha256", "independence_group_id", "reviewer_row_sha256"}
)
_EMITTED_SUBJECT_FIELDS = frozenset(
    {"contextual_observation_unit_sha256", *_CORE_OBSERVATION_FIELDS}
)
_UNIT_FIELDS = frozenset(
    {
        "schema_version", "review_unit_sequence", "input_sequence", "frame_candidate_id",
        "registry_record_id", "selected_input_sha256", "bridge_row_sha256",
        "payload_base64", "payload_bytes", "payload_sha256", "result_row_sha256",
        "parser_terminal_disposition", "full_payload_missed_span_unit_sha256",
        "emitted_observation_subjects", "emitted_observation_subjects_sha256",
        "emitted_observation_count", "input_review_unit_sha256",
    }
)
_ASSIGNMENT_FIELDS = frozenset(
    {
        "schema_version", "assignment_sequence", "input_review_unit_sha256",
        "input_sequence", "reviewer_id", "reviewer_identity_commitment_sha256",
        "independence_group_id", "semantic_target_blind_required", "assignment_row_sha256",
    }
)
_PRECOMMIT_FIELDS = frozenset(
    {
        "schema_version", "record_origin", "component_version", "upstream_component_manifest_sha256",
        "upstream_sampling_plan_raw_sha256", "upstream_bridge_inventory_raw_sha256",
        "upstream_batch_precommit_raw_sha256", "upstream_results_raw_sha256",
        "upstream_batch_receipt_raw_sha256", "upstream_unreviewed_inventory_raw_sha256",
        "upstream_unreviewed_inventory_artifact_sha256", "review_guideline_sha256",
        "reviewer_roster_raw_sha256", "reviewer_roster_row_count",
        "review_unit_inventory_raw_sha256", "review_unit_inventory_row_count",
        "review_unit_inventory_sha256", "assignment_inventory_raw_sha256",
        "assignment_inventory_row_count", "assignment_inventory_sha256",
        "annotation_statuses", "observation_verdicts", "expected_input_count",
        "max_gold_spans_per_input", "assignment_sealed_at", "review_precommitted_at",
        "presented_policy_only", *_FALSE_AUTHORITY_FIELDS, "action_applied",
        "operational_effect", "artifact_sha256",
    }
)
_GOLD_FIELDS = frozenset(
    {
        "schema_version", "gold_span_sequence", "line_number", "relation_kind",
        "character_span_start", "character_span_end", "utf8_byte_span_start",
        "utf8_byte_span_end", "evidence_text", "evidence_utf8_sha256", "surface_text",
        "surface_utf8_sha256", "presented_definition_text",
        "presented_definition_utf8_sha256", "payload_sha256", "gold_span_sha256",
    }
)
_ADJUDICATION_FIELDS = frozenset(
    {
        "schema_version", "adjudication_sequence", "contextual_observation_unit_sha256",
        "observation_sha256", "verdict", "matched_gold_span_sha256", "adjudication_sha256",
    }
)
_RESULT_FIELDS = frozenset(
    {
        "schema_version", "result_sequence", "input_review_unit_sha256", "input_sequence",
        "frame_candidate_id", "registry_record_id", "payload_sha256", "result_row_sha256",
        "full_payload_missed_span_unit_sha256", "assignment_row_sha256",
        "assigned_reviewer_id", "assigned_reviewer_identity_commitment_sha256",
        "annotation_status", "terminal_reason_code", "reviewed_at",
        "full_payload_review_complete_presented", "observation_adjudications",
        "observation_adjudications_sha256", "presented_gold_spans",
        "presented_gold_spans_sha256", "gold_span_count", "confirmed_emitted_count",
        "spurious_emitted_count", "missed_gold_span_count", "review_result_row_sha256",
    }
)
_RECEIPT_FIELDS = frozenset(
    {
        "schema_version", "record_origin", "component_version", "review_precommit_raw_sha256",
        "review_precommit_artifact_sha256", "review_unit_inventory_raw_sha256",
        "assignment_inventory_raw_sha256", "review_results_raw_sha256",
        "review_results_row_count", "review_results_inventory_sha256",
        "review_results_sealed_at", "receipt_sealed_at", "selected_input_itt_denominator",
        "presented_terminal_input_count", "presented_missing_terminal_count",
        "presented_duplicate_terminal_count", "presented_extra_terminal_count",
        "presented_reordered_terminal_count", "annotation_status_counts",
        "presented_unjudged_input_count", "presented_unavailable_input_count", "presented_judged_input_count",
        "presented_terminal_review_accounting_exhaustive", "presented_all_full_payload_inputs_judged",
        "judged_subset_presented_gold_span_set_accounting_verified", "contextual_review_denominator",
        "full_payload_review_denominator", "judged_subset_emitted_observation_denominator",
        "judged_subset_gold_span_denominator", "all_input_emitted_observation_denominator",
        "all_input_gold_span_denominator", "judged_subset_presented_gold_span_count",
        "judged_subset_confirmed_emitted_count", "judged_subset_spurious_emitted_count",
        "judged_subset_missed_gold_span_count", "all_input_gold_span_count",
        "all_input_confirmed_emitted_count", "all_input_spurious_emitted_count",
        "all_input_missed_gold_span_count", "actual_human_review_count",
        "actual_human_unreviewed_input_count", "actual_source_credit_count",
        "actual_context_credit_count", "metric_status", "descriptive_quality_metrics_allowed",
        "inferential_metrics_allowed", "complete_case_metrics_allowed", "semantic_metrics_allowed",
        "observation_rows_are_sampling_units", "sampling_unit", *_FALSE_AUTHORITY_FIELDS,
        "gate_status", "action_applied", "operational_effect", "artifact_sha256",
    }
)


class P0PresentedNeutralReviewParentError(ValueError):
    """Standalone parent rejected the presented review bundle."""


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _file(value: Any) -> bytes:
    return _canonical(value) + b"\n"


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _raw_digest(value: bytes) -> str:
    if type(value) is not bytes:
        raise P0PresentedNeutralReviewParentError("raw value must be exact bytes")
    return hashlib.sha256(value).hexdigest()


def _with_hash(value: Mapping[str, Any], field: str = "artifact_sha256") -> dict[str, Any]:
    material = dict(value)
    material.pop(field, None)
    return {**material, field: _digest(material)}


def _constant(value: str) -> None:
    raise P0PresentedNeutralReviewParentError(f"non-finite JSON number forbidden: {value}")


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise P0PresentedNeutralReviewParentError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _object(raw: bytes, label: str) -> dict[str, Any]:
    if type(raw) is not bytes or not raw or len(raw) > MAX_JSON_BYTES:
        raise P0PresentedNeutralReviewParentError(f"{label} byte length invalid")
    if raw.startswith(b"\xef\xbb\xbf") or b"\r" in raw:
        raise P0PresentedNeutralReviewParentError(f"{label} BOM/CR forbidden")
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise P0PresentedNeutralReviewParentError(f"{label} UTF-8 invalid") from exc
    if unicodedata.normalize("NFC", text) != text:
        raise P0PresentedNeutralReviewParentError(f"{label} NFC invalid")
    try:
        value = json.loads(text, object_pairs_hook=_pairs, parse_constant=_constant)
    except (json.JSONDecodeError, RecursionError, TypeError, ValueError) as exc:
        raise P0PresentedNeutralReviewParentError(f"{label} JSON invalid") from exc
    if type(value) is not dict:
        raise P0PresentedNeutralReviewParentError(f"{label} must be object")
    try:
        expected = _file(value)
    except (RecursionError, UnicodeEncodeError, TypeError, ValueError) as exc:
        raise P0PresentedNeutralReviewParentError(f"{label} noncanonical") from exc
    if raw != expected:
        raise P0PresentedNeutralReviewParentError(f"{label} canonical bytes mismatch")
    return value


def _jsonl(raw: bytes, label: str) -> list[dict[str, Any]]:
    if type(raw) is not bytes or not raw or len(raw) > MAX_JSONL_BYTES:
        raise P0PresentedNeutralReviewParentError(f"{label} byte length invalid")
    if raw.startswith(b"\xef\xbb\xbf") or b"\r" in raw or not raw.endswith(b"\n") or raw.endswith(b"\n\n"):
        raise P0PresentedNeutralReviewParentError(f"{label} framing invalid")
    rows: list[dict[str, Any]] = []
    for index, line in enumerate(raw[:-1].split(b"\n"), start=1):
        if not line:
            raise P0PresentedNeutralReviewParentError(f"{label} blank row {index}")
        rows.append(_object(line + b"\n", f"{label} row {index}"))
    return rows


def _strict(value: Any, fields: frozenset[str], label: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != fields:
        raise P0PresentedNeutralReviewParentError(f"{label} exact fields mismatch")
    if _FORBIDDEN_SEMANTIC_FIELDS.intersection(value):
        raise P0PresentedNeutralReviewParentError(f"{label} semantic/PII field forbidden")
    return value


def _integer(value: Any, field: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise P0PresentedNeutralReviewParentError(f"{field} exact integer invalid")
    return value


def _bool(value: Any, field: str) -> bool:
    if type(value) is not bool:
        raise P0PresentedNeutralReviewParentError(f"{field} exact boolean invalid")
    return value


def _sha(value: Any, field: str) -> str:
    if type(value) is not str or _SHA_RE.fullmatch(value) is None:
        raise P0PresentedNeutralReviewParentError(f"{field} SHA invalid")
    return value


def _id(value: Any, field: str) -> str:
    if type(value) is not str or _ID_RE.fullmatch(value) is None:
        raise P0PresentedNeutralReviewParentError(f"{field} ID invalid")
    return value


def _text(value: Any, field: str, *, maximum: int = MAX_METADATA_CHARS) -> str:
    if type(value) is not str or not value or len(value) > maximum or value != value.strip() or unicodedata.normalize("NFC", value) != value or any(unicodedata.category(char) in _FORBIDDEN_CATEGORIES for char in value):
        raise P0PresentedNeutralReviewParentError(f"{field} text invalid")
    return value


def _time(value: Any, field: str) -> datetime:
    if type(value) is not str or _TIME_RE.fullmatch(value) is None:
        raise P0PresentedNeutralReviewParentError(f"{field} time invalid")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise P0PresentedNeutralReviewParentError(f"{field} time invalid") from exc


def _self(row: Mapping[str, Any], field: str, label: str) -> None:
    material = dict(row)
    presented = material.pop(field, None)
    if _sha(presented, field) != _digest(material):
        raise P0PresentedNeutralReviewParentError(f"{label} self-hash mismatch")


def _false(row: Mapping[str, Any], fields: Sequence[str], label: str) -> None:
    for field in fields:
        if _bool(row[field], field) is not False:
            raise P0PresentedNeutralReviewParentError(f"{label} cannot assert {field}")


def _upstream_plan(raw: bytes, expected_raw_sha256: str) -> dict[str, Any]:
    if _raw_digest(raw) != _sha(expected_raw_sha256, "expected_sampling_plan_raw_sha256"):
        raise P0PresentedNeutralReviewParentError("presented sampling plan pin mismatch")
    row = _strict(_object(raw, "sampling plan"), _PLAN_FIELDS, "sampling plan")
    if (
        row["schema_version"] != UPSTREAM_PLAN_SCHEMA
        or row["record_origin"] != RECORD_ORIGIN
        or row["selection_algorithm"] != UPSTREAM_SELECTION_ALGORITHM
        or row["gate_status"] != "NO_GO_DETERMINISTIC_EXAMPLE_PLAN_ONLY"
        or row["operational_effect"] != OPERATIONAL_EFFECT
        or _bool(row["without_replacement"], "without_replacement") is not True
        or _bool(row["spill_allowed"], "spill_allowed") is not False
        or _bool(row["replacement_allowed"], "replacement_allowed") is not False
        or _bool(row["presented_serialization_only"], "presented_serialization_only") is not True
        or _bool(row["action_applied"], "action_applied") is not False
        or _integer(row["input_count"], "input_count", 1) != EXPECTED_INPUT_COUNT
    ):
        raise P0PresentedNeutralReviewParentError("sampling plan contract mismatch")
    _false(row, _UPSTREAM_PLAN_FALSE_FIELDS, "sampling plan")
    for field in ("scope_sha256", "seed_receipt_sha256", "frame_manifest_sha256", "derived_seed_sha256", "selected_input_set_sha256", "eligible_surplus_sha256"):
        _sha(row[field], field)
    _integer(row["eligible_surplus_count"], "eligible_surplus_count")
    selected = row["selected_inputs"]
    if type(selected) is not list or len(selected) != EXPECTED_INPUT_COUNT:
        raise P0PresentedNeutralReviewParentError("sampling plan selected inventory mismatch")
    candidates: set[str] = set()
    lineages: set[str] = set()
    profile_counts: Counter[str] = Counter()
    stratum_shapes: dict[str, tuple[str, str, str, int, int]] = {}
    for index, value in enumerate(selected, start=1):
        item = _strict(value, _SELECTED_FIELDS, f"selected input {index}")
        if _integer(item["input_sequence"], "input_sequence", 1) != index:
            raise P0PresentedNeutralReviewParentError("selected input physical order mismatch")
        for field in ("candidate_id", "lineage_group_id", "adapter_id", "stratum_id"):
            _id(item[field], field)
        for field in ("locator_commitment_sha256", "lineage_unit_sha256", "rank_sha256"):
            _sha(item[field], field)
        if item["source_profile"] not in SOURCE_PROFILES or type(item["platform"]) is not str or _PLATFORM_RE.fullmatch(item["platform"]) is None or type(item["utc_day"]) is not str or _UTC_DAY_RE.fullmatch(item["utc_day"]) is None:
            raise P0PresentedNeutralReviewParentError("selected input profile/day invalid")
        for field in ("N_h", "n_h", "inclusion_probability_numerator", "inclusion_probability_denominator"):
            _integer(item[field], field, 1)
        divisor = math.gcd(item["n_h"], item["N_h"])
        if (
            item["n_h"] > item["N_h"]
            or item["inclusion_probability_numerator"] != item["n_h"] // divisor
            or item["inclusion_probability_denominator"] != item["N_h"] // divisor
            or item["candidate_id"] in candidates
            or item["lineage_group_id"] in lineages
        ):
            raise P0PresentedNeutralReviewParentError("selected input replacement/fraction invalid")
        shape = (item["source_profile"], item["platform"], item["utc_day"], item["N_h"], item["n_h"])
        if stratum_shapes.setdefault(item["stratum_id"], shape) != shape:
            raise P0PresentedNeutralReviewParentError("selected stratum shape mismatch")
        candidates.add(item["candidate_id"])
        lineages.add(item["lineage_group_id"])
        profile_counts[item["source_profile"]] += 1
    expected_profile_counts = {profile: 10 for profile in SOURCE_PROFILES}
    if row["per_profile_counts"] != expected_profile_counts or dict(profile_counts) != expected_profile_counts:
        raise P0PresentedNeutralReviewParentError("sampling plan profile counts mismatch")
    if row["selected_input_set_sha256"] != _digest(selected):
        raise P0PresentedNeutralReviewParentError("selected input set hash mismatch")
    _time(row["selection_sealed_at"], "selection_sealed_at")
    _self(row, "artifact_sha256", "sampling plan")
    return row


def _upstream_precommit(
    raw: bytes,
    *,
    expected_raw_sha256: str,
    plan_raw: bytes,
    plan: Mapping[str, Any],
    bridge_raw: bytes,
    bridges: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    if _raw_digest(raw) != _sha(expected_raw_sha256, "expected_batch_precommit_raw_sha256"):
        raise P0PresentedNeutralReviewParentError("presented batch precommit pin mismatch")
    row = _strict(_object(raw, "batch precommit"), _UPSTREAM_PRECOMMIT_FIELDS, "batch precommit")
    if row["schema_version"] != UPSTREAM_BATCH_PRECOMMIT_SCHEMA or row["record_origin"] != RECORD_ORIGIN or row["component_version"] != UPSTREAM_COMPONENT_VERSION or row["upstream_sampling_plan_schema"] != UPSTREAM_PLAN_SCHEMA or row["neutral_core_version"] != UPSTREAM_NEUTRAL_CORE_VERSION or row["neutral_core_manifest_sha256"] != UPSTREAM_NEUTRAL_CORE_MANIFEST_SHA256:
        raise P0PresentedNeutralReviewParentError("batch precommit contract mismatch")
    expected = {
        "upstream_sampling_plan_raw_sha256": _raw_digest(plan_raw),
        "upstream_sampling_plan_artifact_sha256": plan["artifact_sha256"],
        "upstream_selected_input_set_sha256": plan["selected_input_set_sha256"],
        "bridge_inventory_raw_sha256": _raw_digest(bridge_raw),
        "bridge_inventory_row_count": EXPECTED_INPUT_COUNT,
        "bridge_inventory_sha256": _digest(bridges),
        "total_payload_bytes": sum(_integer(item["payload_bytes"], "payload_bytes") for item in bridges),
        "expected_input_count": EXPECTED_INPUT_COUNT,
        "attempts_per_input": 1,
        "per_profile_input_counts": {profile: sum(item["source_profile"] == profile for item in bridges) for profile in SOURCE_PROFILES},
    }
    if any(row[field] != value for field, value in expected.items()):
        raise P0PresentedNeutralReviewParentError("batch precommit lineage mismatch")
    for field in ("retry_allowed", "replacement_allowed", "backfill_allowed", "spill_allowed"):
        if _bool(row[field], field) is not False:
            raise P0PresentedNeutralReviewParentError("batch precommit retry policy mismatch")
    for field in ("presented_registry_capture_bridge_verified", "presented_precommit_only"):
        if _bool(row[field], field) is not True:
            raise P0PresentedNeutralReviewParentError("batch precommit presented boundary mismatch")
    _false(row, _UPSTREAM_FALSE_FIELDS, "batch precommit")
    if _bool(row["action_applied"], "action_applied") is not False or row["operational_effect"] != OPERATIONAL_EFFECT or _time(row["precommitted_at"], "precommitted_at") <= _time(plan["selection_sealed_at"], "selection_sealed_at"):
        raise P0PresentedNeutralReviewParentError("batch precommit effect/chronology mismatch")
    _self(row, "artifact_sha256", "batch precommit")
    return row


def _upstream_receipt(
    raw: bytes,
    *,
    precommit_raw: bytes,
    precommit: Mapping[str, Any],
    bridge_raw: bytes,
    results_raw: bytes,
    results: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    row = _strict(_object(raw, "batch receipt"), _UPSTREAM_RECEIPT_FIELDS, "batch receipt")
    if row["schema_version"] != UPSTREAM_BATCH_RECEIPT_SCHEMA or row["record_origin"] != RECORD_ORIGIN or row["component_version"] != UPSTREAM_COMPONENT_VERSION:
        raise P0PresentedNeutralReviewParentError("batch receipt contract mismatch")
    terminal_counts = Counter(result["terminal_disposition"] for result in results)
    profile_counts = Counter(result["source_profile"] for result in results)
    expected = {
        "batch_precommit_raw_sha256": _raw_digest(precommit_raw),
        "batch_precommit_artifact_sha256": precommit["artifact_sha256"],
        "bridge_inventory_raw_sha256": _raw_digest(bridge_raw),
        "results_raw_sha256": _raw_digest(results_raw),
        "results_row_count": EXPECTED_INPUT_COUNT,
        "results_inventory_sha256": _digest(results),
        "itt_denominator": EXPECTED_INPUT_COUNT,
        "itt_accounted_input_count": EXPECTED_INPUT_COUNT,
        "core_result_count": EXPECTED_INPUT_COUNT - terminal_counts["CORE_ERROR"],
        "core_error_count": terminal_counts["CORE_ERROR"],
        "total_observation_count": sum(_integer(result["observation_count"], "observation_count") for result in results),
        "per_profile_terminal_counts": {profile: profile_counts[profile] for profile in SOURCE_PROFILES},
        "terminal_disposition_counts": {status: terminal_counts[status] for status in TERMINAL_DISPOSITIONS},
    }
    if any(row[field] != value for field, value in expected.items()):
        raise P0PresentedNeutralReviewParentError("batch receipt accounting mismatch")
    for field in ("missing_input_count", "duplicate_result_count", "extra_result_count", "reordered_result_count", "replacement_result_count", "backfill_result_count", "retry_result_count", "actual_source_credit_count", "actual_context_credit_count"):
        if _integer(row[field], field) != 0:
            raise P0PresentedNeutralReviewParentError("batch receipt zero boundary mismatch")
    for field in ("all_selected_inputs_accounted_once", "core_error_included_in_itt", "without_replacement_preserved", "presented_batch_accounting_verified"):
        if _bool(row[field], field) is not True:
            raise P0PresentedNeutralReviewParentError("batch receipt presented accounting mismatch")
    if row["metric_status"] != "NOT_ESTIMABLE_PRESENTED_ACCOUNTING_ONLY" or row["sampling_unit"] != SAMPLING_UNIT or row["gate_status"] != "NO_GO_PRESENTED_BATCH_ACCOUNTING_ONLY":
        raise P0PresentedNeutralReviewParentError("batch receipt metric/gate mismatch")
    for field in ("inferential_metrics_allowed", "complete_case_metrics_allowed", "observation_rows_are_sampling_units", "exhaustive_human_review_verified"):
        if _bool(row[field], field) is not False:
            raise P0PresentedNeutralReviewParentError("batch receipt metric boundary mismatch")
    _false(row, _UPSTREAM_FALSE_FIELDS, "batch receipt")
    if _bool(row["action_applied"], "action_applied") is not False or row["operational_effect"] != OPERATIONAL_EFFECT:
        raise P0PresentedNeutralReviewParentError("batch receipt effect mismatch")
    started = _time(row["batch_started_at"], "batch_started_at")
    completed = _time(row["batch_completed_at"], "batch_completed_at")
    sealed = _time(row["results_sealed_at"], "results_sealed_at")
    if started <= _time(precommit["precommitted_at"], "precommitted_at") or completed <= started or sealed <= completed:
        raise P0PresentedNeutralReviewParentError("batch receipt chronology mismatch")
    _self(row, "artifact_sha256", "batch receipt")
    return row


def _upstream(
    *,
    sampling_plan_raw: bytes,
    expected_sampling_plan_raw_sha256: str,
    bridge_raw: bytes,
    batch_precommit_raw: bytes,
    expected_batch_precommit_raw_sha256: str,
    results_raw: bytes,
    batch_receipt_raw: bytes,
    unreviewed_raw: bytes,
    expected_unreviewed_raw_sha256: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    plan = _upstream_plan(sampling_plan_raw, expected_sampling_plan_raw_sha256)
    if _raw_digest(unreviewed_raw) != _sha(expected_unreviewed_raw_sha256, "expected_unreviewed_inventory_raw_sha256"):
        raise P0PresentedNeutralReviewParentError("presented unreviewed pin mismatch")
    bridges = _jsonl(bridge_raw, "upstream bridge")
    results = _jsonl(results_raw, "upstream results")
    if len(bridges) != EXPECTED_INPUT_COUNT or len(results) != EXPECTED_INPUT_COUNT:
        raise P0PresentedNeutralReviewParentError("upstream row count mismatch")
    for index, (bridge_value, result_value, selected) in enumerate(zip(bridges, results, plan["selected_inputs"]), start=1):
        bridge = _strict(bridge_value, _BRIDGE_FIELDS, f"bridge {index}")
        result = _strict(result_value, _BATCH_RESULT_FIELDS, f"batch result {index}")
        if (
            bridge["schema_version"] != UPSTREAM_BRIDGE_SCHEMA
            or result["schema_version"] != UPSTREAM_RESULT_SCHEMA
            or
            _integer(bridge["input_sequence"], "input_sequence", 1) != index
            or _integer(result["input_sequence"], "input_sequence", 1) != index
        ):
            raise P0PresentedNeutralReviewParentError("upstream physical order mismatch")
        if bridge["source_profile"] not in SOURCE_PROFILES or result["terminal_disposition"] not in TERMINAL_DISPOSITIONS:
            raise P0PresentedNeutralReviewParentError("upstream profile/disposition invalid")
        _id(bridge["candidate_id"], "candidate_id")
        _id(bridge["registry_record_id"], "registry_record_id")
        if bridge["candidate_id"] == bridge["registry_record_id"]:
            raise P0PresentedNeutralReviewParentError("candidate/registry ID collision")
        if any(bridge[field] != selected[field] for field in _SELECTED_IDENTITY_FIELDS) or bridge["selected_input_sha256"] != _digest(selected):
            raise P0PresentedNeutralReviewParentError("bridge/sampling plan lineage mismatch")
        try:
            payload = base64.b64decode(bridge["payload_base64"], validate=True)
        except Exception as exc:
            raise P0PresentedNeutralReviewParentError("bridge payload invalid") from exc
        if len(payload) != _integer(bridge["payload_bytes"], "payload_bytes") or hashlib.sha256(payload).hexdigest() != bridge["payload_sha256"]:
            raise P0PresentedNeutralReviewParentError("bridge payload binding mismatch")
        _self(bridge, "bridge_row_sha256", f"bridge {index}")
        exact = {
            "frame_candidate_id": bridge["candidate_id"], "registry_record_id": bridge["registry_record_id"],
            "registry_record_commitment_sha256": bridge["registry_record_commitment_sha256"],
            "source_profile": bridge["source_profile"], "selected_input_sha256": bridge["selected_input_sha256"],
            "bridge_row_sha256": bridge["bridge_row_sha256"], "payload_sha256": bridge["payload_sha256"],
        }
        if any(result[field] != expected for field, expected in exact.items()):
            raise P0PresentedNeutralReviewParentError("batch result/bridge mismatch")
        if _integer(result["attempt_count"], "attempt_count", 1) != 1 or result["retry_performed"] is not False or result["replacement_performed"] is not False:
            raise P0PresentedNeutralReviewParentError("batch result attempt surface invalid")
        core = result["core_result"]
        if core is None:
            if (
                result["terminal_disposition"] != "CORE_ERROR"
                or _integer(result["observation_count"], "observation_count") != 0
                or result["core_result_sha256"] is not None
                or result["core_observations_sha256"] is not None
                or result["core_error_stage"] != "CORE_EXECUTION"
                or result["core_error_code"] != "UNEXPECTED_CORE_EXCEPTION"
                or result["core_error_presented_only"] is not True
            ):
                raise P0PresentedNeutralReviewParentError("batch CORE_ERROR shape invalid")
        else:
            core = _strict(core, _CORE_RESULT_FIELDS, f"core result {index}")
            observations = core["observations"]
            if type(observations) is not list or len(observations) != _integer(core["observation_count"], "observation_count") or len(observations) != _integer(result["observation_count"], "observation_count"):
                raise P0PresentedNeutralReviewParentError("core observation count mismatch")
            if core["payload_sha256"] != bridge["payload_sha256"] or _integer(core["payload_bytes"], "payload_bytes") != bridge["payload_bytes"] or core["disposition"] != result["terminal_disposition"]:
                raise P0PresentedNeutralReviewParentError("core result projection mismatch")
            if result["core_error_stage"] is not None or result["core_error_code"] is not None or result["core_error_presented_only"] is not False:
                raise P0PresentedNeutralReviewParentError("non-error batch row error fields invalid")
            for observation_index, observation_value in enumerate(observations, start=1):
                observation = _strict(observation_value, _CORE_OBSERVATION_FIELDS, f"observation {index}:{observation_index}")
                if _integer(observation["observation_sequence"], "observation_sequence", 1) != observation_index:
                    raise P0PresentedNeutralReviewParentError("observation order mismatch")
                _self(observation, "observation_sha256", f"observation {index}:{observation_index}")
            if _digest(observations) != core["observations_sha256"]:
                raise P0PresentedNeutralReviewParentError("core observation inventory mismatch")
            _self(core, "result_sha256", f"core result {index}")
            if result["core_result_sha256"] != core["result_sha256"] or result["core_observations_sha256"] != core["observations_sha256"]:
                raise P0PresentedNeutralReviewParentError("batch core hash projection mismatch")
        _self(result, "result_row_sha256", f"batch result {index}")
    batch_precommit = _upstream_precommit(
        batch_precommit_raw,
        expected_raw_sha256=expected_batch_precommit_raw_sha256,
        plan_raw=sampling_plan_raw,
        plan=plan,
        bridge_raw=bridge_raw,
        bridges=bridges,
    )
    batch_receipt = _upstream_receipt(
        batch_receipt_raw,
        precommit_raw=batch_precommit_raw,
        precommit=batch_precommit,
        bridge_raw=bridge_raw,
        results_raw=results_raw,
        results=results,
    )
    inventory = _strict(_object(unreviewed_raw, "upstream unreviewed"), _UNREVIEWED_FIELDS, "upstream unreviewed")
    if (
        inventory["schema_version"] != UPSTREAM_UNREVIEWED_SCHEMA
        or inventory["record_origin"] != RECORD_ORIGIN
        or inventory["component_version"] != UPSTREAM_COMPONENT_VERSION
        or inventory["gate_status"] != "NO_GO_UNREVIEWED_INVENTORY_ONLY"
        or inventory["action_applied"] is not False
        or inventory["operational_effect"] != OPERATIONAL_EFFECT
    ):
        raise P0PresentedNeutralReviewParentError("upstream unreviewed contract mismatch")
    if inventory["results_raw_sha256"] != _raw_digest(results_raw) or inventory["batch_receipt_raw_sha256"] != _raw_digest(batch_receipt_raw) or inventory["batch_receipt_artifact_sha256"] != batch_receipt["artifact_sha256"]:
        raise P0PresentedNeutralReviewParentError("unreviewed upstream raw binding mismatch")
    if (
        _integer(inventory["human_reviewed_contextual_observation_count"], "human_reviewed_contextual_observation_count") != 0
        or _integer(inventory["human_reviewed_full_payload_input_count"], "human_reviewed_full_payload_input_count") != 0
        or _integer(inventory["unreviewed_full_payload_input_count"], "unreviewed_full_payload_input_count") != EXPECTED_INPUT_COUNT
        or inventory["exhaustive_human_review_verified"] is not False
    ):
        raise P0PresentedNeutralReviewParentError("upstream unreviewed state invalid")
    _false(inventory, _UPSTREAM_FALSE_FIELDS, "upstream unreviewed")
    _self(inventory, "artifact_sha256", "upstream unreviewed")
    contextual_expected: list[dict[str, Any]] = []
    missed_expected: list[dict[str, Any]] = []
    for bridge, result in zip(bridges, results):
        core = result["core_result"]
        if core is not None:
            for observation in core["observations"]:
                material = {
                    "review_unit_sequence": len(contextual_expected) + 1,
                    "input_sequence": bridge["input_sequence"],
                    "frame_candidate_id": bridge["candidate_id"],
                    "registry_record_id": bridge["registry_record_id"],
                    "selected_input_sha256": bridge["selected_input_sha256"],
                    "bridge_row_sha256": bridge["bridge_row_sha256"],
                    "payload_sha256": bridge["payload_sha256"],
                    "core_result_sha256": core["result_sha256"],
                    "observation_sequence": observation["observation_sequence"],
                    "observation_sha256": observation["observation_sha256"],
                }
                contextual_expected.append({**material, "contextual_observation_unit_sha256": _digest({"domain": "P0_BATCH_CONTEXTUAL_OBSERVATION_REVIEW_UNIT_V1", **material})})
        missed_material = {
            "input_sequence": bridge["input_sequence"], "frame_candidate_id": bridge["candidate_id"],
            "registry_record_id": bridge["registry_record_id"], "selected_input_sha256": bridge["selected_input_sha256"],
            "bridge_row_sha256": bridge["bridge_row_sha256"], "payload_sha256": bridge["payload_sha256"],
            "result_row_sha256": result["result_row_sha256"], "terminal_disposition": result["terminal_disposition"],
        }
        missed_expected.append({**missed_material, "full_payload_missed_span_unit_sha256": _digest({"domain": "P0_BATCH_FULL_PAYLOAD_MISSED_SPAN_REVIEW_UNIT_V1", **missed_material})})
    if _canonical(inventory["contextual_observation_review_units"]) != _canonical(contextual_expected) or _canonical(inventory["full_payload_missed_span_review_units"]) != _canonical(missed_expected):
        raise P0PresentedNeutralReviewParentError("upstream review universe mismatch")
    if _integer(inventory["contextual_observation_count"], "contextual_observation_count") != len(contextual_expected) or _integer(inventory["unreviewed_contextual_observation_count"], "unreviewed_contextual_observation_count") != len(contextual_expected) or _integer(inventory["full_payload_missed_span_input_count"], "full_payload_missed_span_input_count") != EXPECTED_INPUT_COUNT:
        raise P0PresentedNeutralReviewParentError("upstream review counts mismatch")
    if inventory["contextual_observation_review_units_sha256"] != _digest(contextual_expected) or inventory["full_payload_missed_span_review_units_sha256"] != _digest(missed_expected):
        raise P0PresentedNeutralReviewParentError("upstream review universe hash mismatch")
    return bridges, results, inventory


def _derive_units(bridges: Sequence[Mapping[str, Any]], results: Sequence[Mapping[str, Any]], inventory: Mapping[str, Any]) -> list[dict[str, Any]]:
    contextual_by_input: dict[int, list[Mapping[str, Any]]] = defaultdict(list)
    for item in inventory["contextual_observation_review_units"]:
        contextual_by_input[item["input_sequence"]].append(item)
    missed_by_input = {item["input_sequence"]: item for item in inventory["full_payload_missed_span_review_units"]}
    units: list[dict[str, Any]] = []
    for index, (bridge, result) in enumerate(zip(bridges, results), start=1):
        observations = [] if result["core_result"] is None else result["core_result"]["observations"]
        contextual = contextual_by_input.get(index, [])
        if len(contextual) != len(observations):
            raise P0PresentedNeutralReviewParentError("review-unit observation count mismatch")
        subjects = []
        for unit, observation in zip(contextual, observations):
            subject = {"contextual_observation_unit_sha256": unit["contextual_observation_unit_sha256"], **observation}
            _strict(subject, _EMITTED_SUBJECT_FIELDS, "emitted subject")
            subjects.append(subject)
        material = {
            "schema_version": REVIEW_UNIT_ROW_SCHEMA, "review_unit_sequence": index,
            "input_sequence": index, "frame_candidate_id": bridge["candidate_id"],
            "registry_record_id": bridge["registry_record_id"], "selected_input_sha256": bridge["selected_input_sha256"],
            "bridge_row_sha256": bridge["bridge_row_sha256"], "payload_base64": bridge["payload_base64"],
            "payload_bytes": bridge["payload_bytes"], "payload_sha256": bridge["payload_sha256"],
            "result_row_sha256": result["result_row_sha256"], "parser_terminal_disposition": result["terminal_disposition"],
            "full_payload_missed_span_unit_sha256": missed_by_input[index]["full_payload_missed_span_unit_sha256"],
            "emitted_observation_subjects": subjects, "emitted_observation_subjects_sha256": _digest(subjects),
            "emitted_observation_count": len(subjects),
        }
        units.append({**material, "input_review_unit_sha256": _digest({"domain": "P0_PRESENTED_NEUTRAL_INPUT_REVIEW_UNIT_V1", **material})})
    return units


def _roster(raw: bytes) -> list[dict[str, Any]]:
    rows = _jsonl(raw, "reviewer roster")
    if not 1 <= len(rows) <= MAX_REVIEWERS:
        raise P0PresentedNeutralReviewParentError("reviewer count invalid")
    ids: set[str] = set()
    commitments: set[str] = set()
    for index, value in enumerate(rows, start=1):
        row = _strict(value, _REVIEWER_FIELDS, f"reviewer {index}")
        if row["schema_version"] != REVIEWER_ROW_SCHEMA or _integer(row["reviewer_sequence"], "reviewer_sequence", 1) != index:
            raise P0PresentedNeutralReviewParentError("reviewer order invalid")
        rid = _id(row["reviewer_id"], "reviewer_id")
        commitment = _sha(row["identity_commitment_sha256"], "identity_commitment_sha256")
        _id(row["independence_group_id"], "independence_group_id")
        if rid in ids or commitment in commitments:
            raise P0PresentedNeutralReviewParentError("reviewer duplicate")
        ids.add(rid); commitments.add(commitment)
        _self(row, "reviewer_row_sha256", f"reviewer {index}")
    return rows


def _units(raw: bytes, expected: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows = _jsonl(raw, "review units")
    if _canonical(rows) != _canonical(list(expected)):
        raise P0PresentedNeutralReviewParentError("review units differ from upstream replay")
    return rows


def _assignments(raw: bytes, units: Sequence[Mapping[str, Any]], roster: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows = _jsonl(raw, "assignments")
    if len(rows) != EXPECTED_INPUT_COUNT:
        raise P0PresentedNeutralReviewParentError("assignment count invalid")
    by_id = {row["reviewer_id"]: row for row in roster}
    for index, (value, unit) in enumerate(zip(rows, units), start=1):
        row = _strict(value, _ASSIGNMENT_FIELDS, f"assignment {index}")
        reviewer_id = _id(row["reviewer_id"], "reviewer_id")
        reviewer = by_id.get(reviewer_id)
        if row["schema_version"] != ASSIGNMENT_ROW_SCHEMA or _integer(row["assignment_sequence"], "assignment_sequence", 1) != index or _integer(row["input_sequence"], "input_sequence", 1) != index or row["input_review_unit_sha256"] != unit["input_review_unit_sha256"] or reviewer is None:
            raise P0PresentedNeutralReviewParentError("assignment identity invalid")
        if row["reviewer_identity_commitment_sha256"] != reviewer["identity_commitment_sha256"] or row["independence_group_id"] != reviewer["independence_group_id"] or row["semantic_target_blind_required"] is not True:
            raise P0PresentedNeutralReviewParentError("assignment reviewer projection invalid")
        _self(row, "assignment_row_sha256", f"assignment {index}")
    return rows


def _precommit(
    raw: bytes,
    *,
    expected_raw_sha256: str,
    sampling_plan_raw: bytes,
    bridge_raw: bytes,
    batch_precommit_raw: bytes,
    results_raw: bytes,
    batch_receipt_raw: bytes,
    unreviewed_raw: bytes,
    inventory: Mapping[str, Any],
    roster_raw: bytes,
    roster: Sequence[Mapping[str, Any]],
    units_raw: bytes,
    units: Sequence[Mapping[str, Any]],
    assignments_raw: bytes,
    assignments: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    if _raw_digest(raw) != _sha(expected_raw_sha256, "expected_review_precommit_raw_sha256"):
        raise P0PresentedNeutralReviewParentError("presented precommit pin mismatch")
    row = _strict(_object(raw, "review precommit"), _PRECOMMIT_FIELDS, "review precommit")
    if row["schema_version"] != REVIEW_PRECOMMIT_SCHEMA or row["record_origin"] != RECORD_ORIGIN or row["component_version"] != COMPONENT_VERSION or row["upstream_component_manifest_sha256"] != UPSTREAM_COMPONENT_MANIFEST_SHA256:
        raise P0PresentedNeutralReviewParentError("review precommit contract mismatch")
    expected_hashes = {
        "upstream_sampling_plan_raw_sha256": _raw_digest(sampling_plan_raw),
        "upstream_bridge_inventory_raw_sha256": _raw_digest(bridge_raw),
        "upstream_batch_precommit_raw_sha256": _raw_digest(batch_precommit_raw),
        "upstream_results_raw_sha256": _raw_digest(results_raw),
        "upstream_batch_receipt_raw_sha256": _raw_digest(batch_receipt_raw),
        "upstream_unreviewed_inventory_raw_sha256": _raw_digest(unreviewed_raw),
        "upstream_unreviewed_inventory_artifact_sha256": inventory["artifact_sha256"],
        "reviewer_roster_raw_sha256": _raw_digest(roster_raw),
        "review_unit_inventory_raw_sha256": _raw_digest(units_raw),
        "review_unit_inventory_sha256": _digest(units),
        "assignment_inventory_raw_sha256": _raw_digest(assignments_raw),
        "assignment_inventory_sha256": _digest(assignments),
    }
    if any(row[field] != expected for field, expected in expected_hashes.items()):
        raise P0PresentedNeutralReviewParentError("review precommit raw binding mismatch")
    if _integer(row["reviewer_roster_row_count"], "reviewer_roster_row_count", 1) != len(roster) or _integer(row["review_unit_inventory_row_count"], "review_unit_inventory_row_count", 1) != EXPECTED_INPUT_COUNT or _integer(row["assignment_inventory_row_count"], "assignment_inventory_row_count", 1) != EXPECTED_INPUT_COUNT or row["annotation_statuses"] != list(ANNOTATION_STATUSES) or row["observation_verdicts"] != list(OBSERVATION_VERDICTS) or _integer(row["expected_input_count"], "expected_input_count", 1) != EXPECTED_INPUT_COUNT or _integer(row["max_gold_spans_per_input"], "max_gold_spans_per_input", 1) != MAX_GOLD_SPANS_PER_INPUT or row["presented_policy_only"] is not True:
        raise P0PresentedNeutralReviewParentError("review precommit policy mismatch")
    _sha(row["review_guideline_sha256"], "review_guideline_sha256")
    if _time(row["assignment_sealed_at"], "assignment_sealed_at") <= _time(inventory["review_inventory_sealed_at"], "review_inventory_sealed_at") or _time(row["review_precommitted_at"], "review_precommitted_at") <= _time(row["assignment_sealed_at"], "assignment_sealed_at"):
        raise P0PresentedNeutralReviewParentError("review precommit chronology mismatch")
    _false(row, _FALSE_AUTHORITY_FIELDS, "review precommit")
    if row["action_applied"] is not False or row["operational_effect"] != OPERATIONAL_EFFECT:
        raise P0PresentedNeutralReviewParentError("review precommit effect mismatch")
    _self(row, "artifact_sha256", "review precommit")
    return row


def _line_bounds(document: str) -> dict[int, tuple[int, int]]:
    bounds: dict[int, tuple[int, int]] = {}
    start = 0
    for number, line in enumerate(document.split("\n"), start=1):
        end = start + len(line)
        if line:
            bounds[number] = (start, end)
        start = end + 1
    return bounds


def _span_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return (row["line_number"], row["character_span_start"], row["character_span_end"], row["utf8_byte_span_start"], row["utf8_byte_span_end"], row["evidence_text"], row["surface_text"], row["presented_definition_text"], row["relation_kind"])


def _gold(value: Any, unit: Mapping[str, Any]) -> list[dict[str, Any]]:
    if type(value) is not list or len(value) > MAX_GOLD_SPANS_PER_INPUT:
        raise P0PresentedNeutralReviewParentError("gold span inventory invalid")
    try:
        payload = base64.b64decode(unit["payload_base64"], validate=True)
        document = payload.decode("utf-8", errors="strict")
    except (UnicodeDecodeError, ValueError) as exc:
        raise P0PresentedNeutralReviewParentError("JUDGED payload UTF-8 invalid") from exc
    if document.startswith("\ufeff") or "\x00" in document or "\r" in document or unicodedata.normalize("NFC", document) != document:
        raise P0PresentedNeutralReviewParentError("JUDGED payload canonical text invalid")
    if len(document) > MAX_DOCUMENT_CHARS:
        raise P0PresentedNeutralReviewParentError("JUDGED payload exceeds review-document domain")
    bounds = _line_bounds(document)
    rows: list[dict[str, Any]] = []
    previous_end = -1
    for index, raw in enumerate(value, start=1):
        row = _strict(raw, _GOLD_FIELDS, f"gold span {index}")
        line = _integer(row["line_number"], "line_number", 1)
        start = _integer(row["character_span_start"], "character_span_start")
        end = _integer(row["character_span_end"], "character_span_end", 1)
        if row["schema_version"] != GOLD_SPAN_SCHEMA or _integer(row["gold_span_sequence"], "gold_span_sequence", 1) != index or line not in bounds or bounds[line] != (start, end) or start < previous_end or document[start:end] != row["evidence_text"]:
            raise P0PresentedNeutralReviewParentError("gold whole-line binding invalid")
        byte_start = len(document[:start].encode("utf-8")); byte_end = len(document[:end].encode("utf-8"))
        if _integer(row["utf8_byte_span_start"], "utf8_byte_span_start") != byte_start or _integer(row["utf8_byte_span_end"], "utf8_byte_span_end", 1) != byte_end or row["relation_kind"] != RELATION_KIND or row["payload_sha256"] != unit["payload_sha256"]:
            raise P0PresentedNeutralReviewParentError("gold byte/payload binding invalid")
        evidence = row["evidence_text"]; surface = _text(row["surface_text"], "surface_text", maximum=MAX_SURFACE_CHARS); definition = _text(row["presented_definition_text"], "presented_definition_text", maximum=MAX_DEFINITION_CHARS)
        relation = _RELATION_RE.fullmatch(evidence)
        if relation is None or relation.group("surface") != surface or relation.group("presented_definition") != definition or row["evidence_utf8_sha256"] != hashlib.sha256(evidence.encode("utf-8")).hexdigest() or row["surface_utf8_sha256"] != hashlib.sha256(surface.encode("utf-8")).hexdigest() or row["presented_definition_utf8_sha256"] != hashlib.sha256(definition.encode("utf-8")).hexdigest():
            raise P0PresentedNeutralReviewParentError("gold text/hash binding invalid")
        material = dict(row); presented = material.pop("gold_span_sha256")
        expected = _digest({"domain": "P0_PRESENTED_NEUTRAL_GOLD_SPAN_V1", "input_review_unit_sha256": unit["input_review_unit_sha256"], **material})
        if presented != expected:
            raise P0PresentedNeutralReviewParentError("gold span self-hash mismatch")
        rows.append(row); previous_end = end
    if len({_span_key(row) for row in rows}) != len(rows):
        raise P0PresentedNeutralReviewParentError("duplicate gold span")
    return rows


def _review_results(raw: bytes, units: Sequence[Mapping[str, Any]], assignments: Sequence[Mapping[str, Any]], precommit: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = _jsonl(raw, "review results")
    if len(rows) != EXPECTED_INPUT_COUNT:
        raise P0PresentedNeutralReviewParentError("review result count invalid")
    for index, (value, unit, assignment) in enumerate(zip(rows, units, assignments), start=1):
        row = _strict(value, _RESULT_FIELDS, f"review result {index}")
        exact = {
            "input_review_unit_sha256": unit["input_review_unit_sha256"], "input_sequence": index,
            "frame_candidate_id": unit["frame_candidate_id"], "registry_record_id": unit["registry_record_id"],
            "payload_sha256": unit["payload_sha256"], "result_row_sha256": unit["result_row_sha256"],
            "full_payload_missed_span_unit_sha256": unit["full_payload_missed_span_unit_sha256"],
            "assignment_row_sha256": assignment["assignment_row_sha256"], "assigned_reviewer_id": assignment["reviewer_id"],
            "assigned_reviewer_identity_commitment_sha256": assignment["reviewer_identity_commitment_sha256"],
        }
        if row["schema_version"] != REVIEW_RESULT_ROW_SCHEMA or _integer(row["result_sequence"], "result_sequence", 1) != index or _integer(row["input_sequence"], "input_sequence", 1) != index or any(row[field] != expected for field, expected in exact.items()):
            raise P0PresentedNeutralReviewParentError("review result identity/order mismatch")
        status = row["annotation_status"]
        if status not in ANNOTATION_STATUSES or row["terminal_reason_code"] != _STATUS_REASON[status]:
            raise P0PresentedNeutralReviewParentError("review result status/reason mismatch")
        null_fields = ("observation_adjudications", "observation_adjudications_sha256", "presented_gold_spans", "presented_gold_spans_sha256", "gold_span_count", "confirmed_emitted_count", "spurious_emitted_count", "missed_gold_span_count")
        if status == "UNJUDGED":
            if row["reviewed_at"] is not None or row["full_payload_review_complete_presented"] is not False or any(row[field] is not None for field in null_fields):
                raise P0PresentedNeutralReviewParentError("UNJUDGED nullability mismatch")
        elif status == "UNAVAILABLE":
            if _time(row["reviewed_at"], "reviewed_at") <= _time(precommit["review_precommitted_at"], "review_precommitted_at") or row["full_payload_review_complete_presented"] is not False or any(row[field] is not None for field in null_fields):
                raise P0PresentedNeutralReviewParentError("UNAVAILABLE nullability mismatch")
        else:
            if _time(row["reviewed_at"], "reviewed_at") <= _time(precommit["review_precommitted_at"], "review_precommitted_at") or row["full_payload_review_complete_presented"] is not True:
                raise P0PresentedNeutralReviewParentError("JUDGED completion mismatch")
            gold = _gold(row["presented_gold_spans"], unit)
            if row["presented_gold_spans_sha256"] != _digest(gold) or _integer(row["gold_span_count"], "gold_span_count") != len(gold):
                raise P0PresentedNeutralReviewParentError("gold inventory aggregate mismatch")
            gold_by_key = {_span_key(span): span for span in gold}
            emitted = unit["emitted_observation_subjects"]
            adjudications = row["observation_adjudications"]
            if type(adjudications) is not list or len(adjudications) != len(emitted):
                raise P0PresentedNeutralReviewParentError("adjudication count mismatch")
            confirmed = 0
            for subject_index, (adjudication_value, subject) in enumerate(zip(adjudications, emitted), start=1):
                adjudication = _strict(adjudication_value, _ADJUDICATION_FIELDS, f"adjudication {index}:{subject_index}")
                matched = gold_by_key.get(_span_key(subject)); verdict = "CONFIRMED" if matched is not None else "SPURIOUS"
                material = {
                    "schema_version": OBSERVATION_ADJUDICATION_SCHEMA, "adjudication_sequence": subject_index,
                    "contextual_observation_unit_sha256": subject["contextual_observation_unit_sha256"],
                    "observation_sha256": subject["observation_sha256"], "verdict": verdict,
                    "matched_gold_span_sha256": None if matched is None else matched["gold_span_sha256"],
                }
                expected_adj = {**material, "adjudication_sha256": _digest(material)}
                _integer(adjudication["adjudication_sequence"], "adjudication_sequence", 1)
                if adjudication != expected_adj:
                    raise P0PresentedNeutralReviewParentError("adjudication exact arithmetic mismatch")
                confirmed += int(matched is not None)
            if row["observation_adjudications_sha256"] != _digest(adjudications) or _integer(row["confirmed_emitted_count"], "confirmed_emitted_count") != confirmed or _integer(row["spurious_emitted_count"], "spurious_emitted_count") != len(emitted) - confirmed or _integer(row["missed_gold_span_count"], "missed_gold_span_count") != len(set(gold_by_key) - {_span_key(subject) for subject in emitted}):
                raise P0PresentedNeutralReviewParentError("review span arithmetic mismatch")
        _self(row, "review_result_row_sha256", f"review result {index}")
    return rows


def _receipt(raw: bytes, *, precommit_raw: bytes, precommit: Mapping[str, Any], units_raw: bytes, units: Sequence[Mapping[str, Any]], assignments_raw: bytes, results_raw: bytes, results: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    row = _strict(_object(raw, "review receipt"), _RECEIPT_FIELDS, "review receipt")
    if row["schema_version"] != REVIEW_RECEIPT_SCHEMA or row["record_origin"] != RECORD_ORIGIN or row["component_version"] != COMPONENT_VERSION:
        raise P0PresentedNeutralReviewParentError("review receipt contract mismatch")
    sealed = _time(row["review_results_sealed_at"], "review_results_sealed_at")
    if sealed <= _time(precommit["review_precommitted_at"], "review_precommitted_at") or any(_time(result["reviewed_at"], "reviewed_at") >= sealed for result in results if result["reviewed_at"] is not None) or _time(row["receipt_sealed_at"], "receipt_sealed_at") <= sealed:
        raise P0PresentedNeutralReviewParentError("review receipt chronology mismatch")
    counts = Counter(result["annotation_status"] for result in results)
    judged = [result for result in results if result["annotation_status"] == "JUDGED"]
    judged_sequences = {result["input_sequence"] for result in judged}
    contextual_denominator = sum(_integer(unit["emitted_observation_count"], "emitted_observation_count") for unit in units)
    judged_emitted_denominator = sum(
        _integer(unit["emitted_observation_count"], "emitted_observation_count")
        for unit in units
        if unit["input_sequence"] in judged_sequences
    )
    totals = {
        "gold": sum(result["gold_span_count"] for result in judged),
        "confirmed": sum(result["confirmed_emitted_count"] for result in judged),
        "spurious": sum(result["spurious_emitted_count"] for result in judged),
        "missed": sum(result["missed_gold_span_count"] for result in judged),
    }
    all_judged = counts["JUDGED"] == EXPECTED_INPUT_COUNT
    expected = _with_hash(
        {
            "schema_version": REVIEW_RECEIPT_SCHEMA, "record_origin": RECORD_ORIGIN, "component_version": COMPONENT_VERSION,
            "review_precommit_raw_sha256": _raw_digest(precommit_raw), "review_precommit_artifact_sha256": precommit["artifact_sha256"],
            "review_unit_inventory_raw_sha256": _raw_digest(units_raw), "assignment_inventory_raw_sha256": _raw_digest(assignments_raw),
            "review_results_raw_sha256": _raw_digest(results_raw), "review_results_row_count": EXPECTED_INPUT_COUNT,
            "review_results_inventory_sha256": _digest(results), "review_results_sealed_at": row["review_results_sealed_at"],
            "receipt_sealed_at": row["receipt_sealed_at"], "selected_input_itt_denominator": EXPECTED_INPUT_COUNT,
            "presented_terminal_input_count": EXPECTED_INPUT_COUNT, "presented_missing_terminal_count": 0,
            "presented_duplicate_terminal_count": 0, "presented_extra_terminal_count": 0,
            "presented_reordered_terminal_count": 0, "annotation_status_counts": {status: counts[status] for status in ANNOTATION_STATUSES},
            "presented_unjudged_input_count": counts["UNJUDGED"], "presented_unavailable_input_count": counts["UNAVAILABLE"],
            "presented_judged_input_count": counts["JUDGED"], "presented_terminal_review_accounting_exhaustive": counts["UNJUDGED"] == 0,
            "presented_all_full_payload_inputs_judged": all_judged,
            "judged_subset_presented_gold_span_set_accounting_verified": bool(judged),
            "contextual_review_denominator": contextual_denominator,
            "full_payload_review_denominator": EXPECTED_INPUT_COUNT,
            "judged_subset_emitted_observation_denominator": judged_emitted_denominator,
            "judged_subset_gold_span_denominator": totals["gold"],
            "all_input_emitted_observation_denominator": contextual_denominator if all_judged else None,
            "all_input_gold_span_denominator": totals["gold"] if all_judged else None,
            "judged_subset_presented_gold_span_count": totals["gold"], "judged_subset_confirmed_emitted_count": totals["confirmed"],
            "judged_subset_spurious_emitted_count": totals["spurious"], "judged_subset_missed_gold_span_count": totals["missed"],
            "all_input_gold_span_count": totals["gold"] if all_judged else None,
            "all_input_confirmed_emitted_count": totals["confirmed"] if all_judged else None,
            "all_input_spurious_emitted_count": totals["spurious"] if all_judged else None,
            "all_input_missed_gold_span_count": totals["missed"] if all_judged else None,
            "actual_human_review_count": 0, "actual_human_unreviewed_input_count": EXPECTED_INPUT_COUNT,
            "actual_source_credit_count": 0, "actual_context_credit_count": 0, "metric_status": METRIC_STATUS,
            "descriptive_quality_metrics_allowed": False, "inferential_metrics_allowed": False,
            "complete_case_metrics_allowed": False, "semantic_metrics_allowed": False,
            "observation_rows_are_sampling_units": False, "sampling_unit": SAMPLING_UNIT,
            **{field: False for field in _FALSE_AUTHORITY_FIELDS}, "gate_status": GATE_STATUS,
            "action_applied": False, "operational_effect": OPERATIONAL_EFFECT,
        }
    )
    if raw != _file(expected):
        raise P0PresentedNeutralReviewParentError("review receipt exact replay mismatch")
    return row


ARTIFACT_FIELDS = {
    "reviewer_row": sorted(_REVIEWER_FIELDS), "emitted_observation_subject": sorted(_EMITTED_SUBJECT_FIELDS), "review_unit_row": sorted(_UNIT_FIELDS),
    "assignment_row": sorted(_ASSIGNMENT_FIELDS), "review_precommit": sorted(_PRECOMMIT_FIELDS),
    "gold_span": sorted(_GOLD_FIELDS), "observation_adjudication": sorted(_ADJUDICATION_FIELDS),
    "review_result_row": sorted(_RESULT_FIELDS), "review_receipt": sorted(_RECEIPT_FIELDS),
}
EXPECTED_COMPONENT_MANIFEST = {
    "schema_version": COMPONENT_MANIFEST_SCHEMA,
    "component": "p0_presented_neutral_review_accounting_v1_contract",
    "component_version": COMPONENT_VERSION,
    "record_origin": RECORD_ORIGIN,
    "upstream_component_manifest_sha256": UPSTREAM_COMPONENT_MANIFEST_SHA256,
    "reviewer_row_schema": REVIEWER_ROW_SCHEMA,
    "review_unit_row_schema": REVIEW_UNIT_ROW_SCHEMA,
    "assignment_row_schema": ASSIGNMENT_ROW_SCHEMA,
    "review_precommit_schema": REVIEW_PRECOMMIT_SCHEMA,
    "gold_span_schema": GOLD_SPAN_SCHEMA,
    "observation_adjudication_schema": OBSERVATION_ADJUDICATION_SCHEMA,
    "review_result_row_schema": REVIEW_RESULT_ROW_SCHEMA,
    "review_receipt_schema": REVIEW_RECEIPT_SCHEMA,
    "expected_input_count": EXPECTED_INPUT_COUNT,
    "annotation_statuses": list(ANNOTATION_STATUSES),
    "status_reason_codes": dict(_STATUS_REASON),
    "observation_verdicts": list(OBSERVATION_VERDICTS),
    "relation_kind": RELATION_KIND,
    "input_terminal_exactly_once": True,
    "unavailable_gold_and_arithmetic_are_null": True,
    "unjudged_gold_and_arithmetic_are_null": True,
    "judged_empty_gold_allowed": True,
    "core_error_input_retained": True,
    "physical_jsonl_order_required": True,
    "gold_span_capacity_policy": {
        "basis": "FULL_BOUNDED_REVIEW_DOCUMENT_MINIMUM_CANONICAL_RELATION_LINE",
        "max_document_chars": MAX_DOCUMENT_CHARS,
        "minimum_relation_line_chars": MIN_RELATION_LINE_CHARS,
        "max_gold_spans_per_input": MAX_GOLD_SPANS_PER_INPUT,
        "independent_of_parser_emission_limit": True,
        "overlong_strict_utf8_payload_terminal": "UNAVAILABLE_REQUIRED",
    },
    "forbidden_semantic_fields": sorted(_FORBIDDEN_SEMANTIC_FIELDS),
    "artifact_fields": ARTIFACT_FIELDS,
    "limits": {"max_reviewers": MAX_REVIEWERS, "max_gold_spans_per_input": MAX_GOLD_SPANS_PER_INPUT, "max_surface_chars": MAX_SURFACE_CHARS, "max_definition_chars": MAX_DEFINITION_CHARS, "max_json_bytes": MAX_JSON_BYTES, "max_jsonl_bytes": MAX_JSONL_BYTES},
    "chronology": ["upstream_unreviewed_inventory_seal", "reviewer_roster_and_assignment_seal", "review_precommit", "presented_terminal_review_results", "review_accounting_receipt"],
    "direct_io_capabilities": [],
    "actual_human_review_count": 0,
    "actual_human_unreviewed_input_count": EXPECTED_INPUT_COUNT,
    "actual_source_credit_count": 0,
    "actual_context_credit_count": 0,
    "metric_status": METRIC_STATUS,
    "descriptive_quality_metrics_allowed": False,
    "inferential_metrics_allowed": False,
    "complete_case_metrics_allowed": False,
    "semantic_metrics_allowed": False,
    "observation_rows_are_sampling_units": False,
    "sampling_unit": SAMPLING_UNIT,
    "denominator_policy": {
        "selected_input_itt_denominator": EXPECTED_INPUT_COUNT,
        "contextual_review_denominator": "ALL_SEALED_EMITTED_OBSERVATION_SUBJECTS",
        "full_payload_review_denominator": EXPECTED_INPUT_COUNT,
        "judged_subset_denominators": "EXACT_JUDGED_INPUT_SUBSET_DIAGNOSTIC_ONLY",
        "all_input_denominators": "INTEGER_ONLY_WHEN_ALL_40_PRESENTED_JUDGED_ELSE_NULL",
    },
    **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    "action_applied": False,
    "operational_effect": OPERATIONAL_EFFECT,
}
EXPECTED_COMPONENT_MANIFEST_SHA256 = _digest(EXPECTED_COMPONENT_MANIFEST)


def validate_review_bundle_against_raw_inputs(
    *,
    sampling_plan_raw: bytes,
    expected_sampling_plan_raw_sha256: str,
    bridge_inventory_raw: bytes,
    batch_precommit_raw: bytes,
    expected_batch_precommit_raw_sha256: str,
    results_raw: bytes,
    batch_receipt_raw: bytes,
    unreviewed_inventory_raw: bytes,
    expected_unreviewed_inventory_raw_sha256: str,
    reviewer_roster_raw: bytes,
    review_unit_inventory_raw: bytes,
    assignment_inventory_raw: bytes,
    review_precommit_raw: bytes,
    expected_review_precommit_raw_sha256: str,
    review_results_raw: bytes,
    review_receipt_raw: bytes,
) -> dict[str, Any]:
    bridges, batch_results, inventory = _upstream(
        sampling_plan_raw=sampling_plan_raw,
        expected_sampling_plan_raw_sha256=expected_sampling_plan_raw_sha256,
        bridge_raw=bridge_inventory_raw,
        batch_precommit_raw=batch_precommit_raw,
        expected_batch_precommit_raw_sha256=expected_batch_precommit_raw_sha256,
        results_raw=results_raw,
        batch_receipt_raw=batch_receipt_raw,
        unreviewed_raw=unreviewed_inventory_raw,
        expected_unreviewed_raw_sha256=expected_unreviewed_inventory_raw_sha256,
    )
    units = _units(review_unit_inventory_raw, _derive_units(bridges, batch_results, inventory))
    roster = _roster(reviewer_roster_raw)
    assignments = _assignments(assignment_inventory_raw, units, roster)
    precommit = _precommit(
        review_precommit_raw,
        expected_raw_sha256=expected_review_precommit_raw_sha256,
        sampling_plan_raw=sampling_plan_raw,
        bridge_raw=bridge_inventory_raw,
        batch_precommit_raw=batch_precommit_raw,
        results_raw=results_raw,
        batch_receipt_raw=batch_receipt_raw,
        unreviewed_raw=unreviewed_inventory_raw,
        inventory=inventory,
        roster_raw=reviewer_roster_raw,
        roster=roster,
        units_raw=review_unit_inventory_raw,
        units=units,
        assignments_raw=assignment_inventory_raw,
        assignments=assignments,
    )
    review_results = _review_results(review_results_raw, units, assignments, precommit)
    receipt = _receipt(
        review_receipt_raw,
        precommit_raw=review_precommit_raw,
        precommit=precommit,
        units_raw=review_unit_inventory_raw,
        units=units,
        assignments_raw=assignment_inventory_raw,
        results_raw=review_results_raw,
        results=review_results,
    )
    material = {
        "schema_version": PARENT_RECEIPT_SCHEMA,
        "expected_component_manifest_sha256": EXPECTED_COMPONENT_MANIFEST_SHA256,
        "presented_expected_unreviewed_inventory_match_verified": True,
        "presented_expected_review_precommit_match_verified": True,
        "upstream_plan_bridge_binding_verified": True,
        "upstream_batch_precommit_binding_verified": True,
        "upstream_batch_receipt_binding_verified": True,
        "parent_separate_implementation_review_replay_verified": True,
        "presented_terminal_review_accounting_exhaustive": receipt["presented_terminal_review_accounting_exhaustive"],
        "presented_all_full_payload_inputs_judged": receipt["presented_all_full_payload_inputs_judged"],
        "selected_input_itt_denominator": EXPECTED_INPUT_COUNT,
        "presented_terminal_input_count": EXPECTED_INPUT_COUNT,
        "contextual_review_denominator": receipt["contextual_review_denominator"],
        "full_payload_review_denominator": receipt["full_payload_review_denominator"],
        "judged_subset_emitted_observation_denominator": receipt["judged_subset_emitted_observation_denominator"],
        "judged_subset_gold_span_denominator": receipt["judged_subset_gold_span_denominator"],
        "all_input_emitted_observation_denominator": receipt["all_input_emitted_observation_denominator"],
        "all_input_gold_span_denominator": receipt["all_input_gold_span_denominator"],
        "actual_human_review_count": 0,
        "actual_human_unreviewed_input_count": EXPECTED_INPUT_COUNT,
        "upstream_batch_replay_verified": False,
        "reviewer_identity_authority_verified": False,
        "reviewer_assignment_factuality_verified": False,
        "reviewer_independence_verified": False,
        "reviewer_blinding_verified": False,
        "human_judgment_factuality_verified": False,
        "gold_span_semantic_factuality_verified": False,
        "gold_span_completeness_factuality_verified": False,
        "actual_source_credit_count": 0,
        "actual_context_credit_count": 0,
        "metric_status": METRIC_STATUS,
        "descriptive_quality_metrics_allowed": False,
        "inferential_metrics_allowed": False,
        "complete_case_metrics_allowed": False,
        "semantic_metrics_allowed": False,
        "observation_rows_are_sampling_units": False,
        "sampling_unit": SAMPLING_UNIT,
        "actual_authority_granted": False,
        "exhaustive_human_review_verified": False,
        "p0_phase_exit": False,
        "production_approval": False,
        "full_scan_approval": False,
        "gate_status": PARENT_GATE_STATUS,
    }
    return {**material, "receipt_sha256": _digest(material)}


__all__ = [
    "EXPECTED_COMPONENT_MANIFEST", "EXPECTED_COMPONENT_MANIFEST_SHA256",
    "P0PresentedNeutralReviewParentError", "PARENT_GATE_STATUS",
    "PARENT_RECEIPT_SCHEMA", "validate_review_bundle_against_raw_inputs",
]
