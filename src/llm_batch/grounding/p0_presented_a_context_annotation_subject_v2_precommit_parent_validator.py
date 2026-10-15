"""Annotation subject V2 precommit의 독립 부모 검증기.

producer/``llm_batch`` 모듈을 import하지 않는다. source/A upstream의 raw chain,
inventory, self-hash와 bridge/20 subject lineage를 제한 범위로 재계산한다.
"""

from __future__ import annotations

import base64
from collections import Counter
from datetime import datetime
from fractions import Fraction
import hashlib
import json
import math
import re
import unicodedata
from typing import Any, Mapping, Sequence

SUBJECT_SCHEMA = "p0_presented_a_context_annotation_subject_v2_prelabel_row_v1"
PRECOMMIT_SCHEMA = "p0_presented_a_context_annotation_subject_v2_precommit_v1"
SUBJECT_DOMAIN = "P0_PRESENTED_A_CONTEXT_ANNOTATION_SUBJECT_V2_PRECOMMIT_V1"
ORIGIN = "ACTUAL_SCHEMA_CONTRACT_EXAMPLE_ONLY"
OPERATIONAL_EFFECT = "NONE_SHADOW_ONLY"
GATE_STATUS = "A_CONTEXT_V2_SUBJECTS_PRECOMMITTED_ANNOTATION_NOT_STARTED_ALL_AUTHORITY_NO_GO"
PARENT_GATE_STATUS = "A_CONTEXT_V2_PRECOMMIT_PARENT_REPLAY_PASS_ALL_AUTHORITY_NO_GO"
METRIC_STATUS = "METRICS_NOT_ESTIMABLE_PREANNOTATION_ONLY"
PROFILES = ("OFFICIAL_STRUCTURED", "COMMUNITY_STRUCTURED", "MEDIA_OCR", "GENERIC_FALLBACK")
SOURCE_EXCLUSION_REASON_ORDER = (
    "RIGHTS_POLICY_NOT_ASSESSED", "COLLECTION_NOT_ALLOWED", "TAKEDOWN_NOT_ACTIVE",
    "ADAPTER_CONTRACT_NOT_VERIFIED", "LINEAGE_DERIVATIVE", "LINEAGE_UNKNOWN",
    "LINEAGE_GROUP_HAS_NO_ROOT",
)
A_EXCLUSION_REASON_ORDER = (
    "RIGHTS_POLICY_NOT_ASSESSED", "COLLECTION_NOT_ALLOWED", "TAKEDOWN_NOT_ACTIVE",
    "SOURCE_BINDING_NOT_VERIFIED",
)
LINEAGE_KEYS = (
    "source_scope", "source_census", "source_frame", "source_seed", "source_plan",
    "bridge_inventory", "a_scope", "a_census", "a_frame", "a_seed", "a_plan",
)
FALSE_FIELDS = (
    "labels_observed", "semantic_truth_fields_used", "annotation_started",
    "actual_a_context_evidence_verified", "actual_authority_granted",
    "inferential_metrics_allowed", "complete_case_metrics_allowed",
    "production_approval", "full_scan_approval", "p0_phase_exit",
    "runtime_noninterference_verified", "write_authority_verified", "action_applied",
)
SOURCE_FALSE = (
    "bounded_scope_completeness_verified", "external_owner_authority_verified",
    "enumeration_adapter_runtime_verified", "eligibility_factual_authority_verified",
    "lineage_factual_authority_verified", "seed_authority_verified",
    "seed_randomness_authority_verified", "probability_design_authority_verified",
    "capture_not_started_authority_verified", "code_identity_verified",
    "runtime_execution_verified", "actual_source_evidence_verified",
    "route_packet_runtime_credit_authority_verified", "actual_authority_granted",
    "production_approval", "full_scan_approval",
)
A_FALSE = (
    "external_context_enumeration_completeness_verified", "external_owner_authority_verified",
    "enumeration_adapter_runtime_verified", "rights_factual_authority_verified",
    "source_capture_authority_verified", "seed_authority_verified",
    "seed_randomness_authority_verified", "probability_design_authority_verified",
    "annotation_not_started_authority_verified", "code_identity_verified",
    "runtime_execution_verified", "actual_a_context_evidence_verified",
    "route_packet_runtime_credit_authority_verified", "actual_authority_granted",
    "p0_phase_exit", "production_approval", "full_scan_approval",
)
FORBIDDEN = frozenset({
    "truth_work_id", "truth_kind", "annotation_status", "reviewer_id", "decision_work_id",
    "target_work_id", "target_sense_id", "gold_label", "candidate_work_ids",
    "latest_annotation_event_id",
})
UPSTREAM_FORBIDDEN = FORBIDDEN | frozenset({
    "gold_label", "truth_label", "truth_work_id", "truth_kind", "nil_label",
    "annotation_status", "annotation_event", "annotation_events", "reviewer_id",
    "reviewer_identity", "decision_work_id", "decision_payload_sha256",
    "target_work_id", "target_sense_id", "candidate_labels", "predicted_work_id",
    "inference_result", "model_result",
})
SOURCE_SCOPE_FIELDS = frozenset("action_applied adapter_profile_map artifact_sha256 created_at eligibility_policy_sha256 enumeration_policy_sha256 expected_per_profile_quota expected_total_quota frame_cutoff future_seed_spec_sha256 labels_observed lineage_policy operational_effect record_origin rights_policy_sha256 schema_version scope_id selection_algorithm semantic_fields_used strata strata_policy_sha256".split())
SOURCE_CENSUS_FIELDS = frozenset("action_applied adapter_id candidate_id eligibility_status enumeration_sequence exclusion_reason_codes lineage_group_id lineage_role lineage_root_locator_commitment_sha256 locator_commitment_sha256 observed_at operational_effect platform presented_adapter_contract_verified presented_collection_allowed presented_rights_policy_assessed presented_takedown_status published_at record_origin row_sha256 schema_version utc_day".split())
SOURCE_FRAME_FIELDS = frozenset("action_applied actual_authority_granted actual_source_evidence_verified artifact_sha256 bounded_scope_completeness_verified capture_not_started_authority_verified census_byte_count census_raw_sha256 census_row_count code_identity_verified derived_candidate_inventory_sha256 eligibility_factual_authority_verified eligible_candidate_count eligible_lineage_unit_count eligible_sampling_units_sha256 enumeration_adapter_runtime_verified excluded_candidate_count excluded_candidates_sha256 exclusion_reason_counts external_owner_authority_verified frame_sealed_at full_scan_approval gate_status lineage_factual_authority_verified operational_effect presented_census_serialization_verified presented_serialization_only probability_design_authority_verified production_approval record_origin route_packet_runtime_credit_authority_verified runtime_execution_verified schema_version scope_sha256 seed_authority_verified seed_randomness_authority_verified stratum_populations".split())
SOURCE_SEED_FIELDS = frozenset("action_applied artifact_sha256 frame_manifest_sha256 frame_owner_precommit_sha256 frame_owner_precommitted_at future_seed_spec_sha256 operational_effect owner_authority_verified record_origin revealed_at revealed_seed_sha256 schema_version scope_sha256 seed_authority_verified seed_receipt_id".split())
SOURCE_PLAN_FIELDS = frozenset("action_applied actual_authority_granted actual_source_evidence_verified artifact_sha256 bounded_scope_completeness_verified capture_not_started_authority_verified code_identity_verified derived_seed_sha256 eligibility_factual_authority_verified eligible_surplus_count eligible_surplus_sha256 enumeration_adapter_runtime_verified external_owner_authority_verified frame_manifest_sha256 full_scan_approval gate_status input_count lineage_factual_authority_verified operational_effect per_profile_counts presented_serialization_only probability_design_authority_verified production_approval record_origin replacement_allowed route_packet_runtime_credit_authority_verified runtime_execution_verified schema_version scope_sha256 seed_authority_verified seed_randomness_authority_verified seed_receipt_sha256 selected_input_set_sha256 selected_inputs selection_algorithm selection_sealed_at spill_allowed without_replacement".split())
A_SCOPE_FIELDS = frozenset("action_applied adapter_profile_map annotation_started artifact_sha256 context_enumeration_policy_sha256 created_at eligibility_policy_sha256 expected_per_profile_quota expected_total_quota frame_cutoff future_seed_spec_sha256 labels_observed operational_effect record_origin rights_policy_sha256 schema_version scope_id selection_algorithm semantic_truth_fields_used strata strata_policy_sha256 upstream_bridge_inventory_raw_sha256 upstream_source_sampling_plan_raw_sha256".split())
A_CENSUS_FIELDS = frozenset("action_applied adapter_id candidate_id capture_receipt_sha256 community_scope_commitment_sha256 content_fingerprint context_observed_at context_unit_sha256 eligibility_status enumeration_sequence exclusion_reason_codes operational_effect payload_sha256 platform_scope presented_collection_allowed presented_rights_policy_assessed presented_source_binding_verified presented_takedown_status record_origin registry_record_id row_sha256 schema_version source_claim_set_sha256 source_profile source_published_at surface_end surface_sha256 surface_start upstream_frame_candidate_id utc_day".split())
A_FRAME_FIELDS = frozenset("action_applied actual_a_context_evidence_verified actual_a_context_review_count actual_authority_granted actual_surplus_review_count annotation_not_started_authority_verified artifact_sha256 census_byte_count census_raw_sha256 census_row_count code_identity_verified complete_case_metrics_allowed eligible_candidate_count eligible_sampling_units_sha256 enumeration_adapter_runtime_verified excluded_candidate_count excluded_candidates_sha256 external_context_enumeration_completeness_verified external_owner_authority_verified frame_sealed_at full_scan_approval gate_status inferential_metrics_allowed metric_status operational_effect p0_phase_exit presented_census_serialization_verified presented_serialization_only probability_design_authority_verified production_approval record_origin rights_factual_authority_verified route_packet_runtime_credit_authority_verified runtime_execution_verified schema_version scope_sha256 seed_authority_verified seed_randomness_authority_verified source_capture_authority_verified statistical_denominator_contribution stratum_populations".split())
A_SEED_FIELDS = frozenset("action_applied artifact_sha256 census_raw_sha256 frame_manifest_sha256 frame_owner_precommit_sha256 frame_owner_precommitted_at future_seed_spec_sha256 operational_effect owner_authority_verified record_origin revealed_at revealed_seed_sha256 schema_version scope_sha256 seed_authority_verified seed_receipt_id".split())
A_PLAN_FIELDS = frozenset("action_applied actual_a_context_evidence_verified actual_a_context_review_count actual_authority_granted actual_surplus_review_count annotation_not_started_authority_verified artifact_sha256 code_identity_verified complete_case_metrics_allowed derived_seed_sha256 eligible_partition_sha256 eligible_surplus_contexts eligible_surplus_count eligible_surplus_set_sha256 enumeration_adapter_runtime_verified external_context_enumeration_completeness_verified external_owner_authority_verified frame_manifest_sha256 full_scan_approval gate_status inferential_metrics_allowed input_count metric_status operational_effect p0_phase_exit per_profile_counts presented_serialization_only probability_design_authority_verified production_approval record_origin replacement_allowed rights_factual_authority_verified route_packet_runtime_credit_authority_verified runtime_execution_verified schema_version scope_sha256 seed_authority_verified seed_randomness_authority_verified seed_receipt_sha256 selected_context_set_sha256 selected_contexts selection_algorithm selection_sealed_at source_capture_authority_verified spill_allowed statistical_denominator_contribution without_replacement".split())
ADAPTER_FIELDS = frozenset({"adapter_id", "source_profile"})
SOURCE_STRATUM_FIELDS = frozenset({"source_profile", "platform", "utc_day", "quota"})
A_STRATUM_FIELDS = frozenset({"source_profile", "platform_scope", "utc_day", "quota"})
SOURCE_POP_FIELDS = frozenset({"source_profile", "platform", "utc_day", "stratum_id", "N_h", "n_h"})
A_POP_FIELDS = frozenset({"source_profile", "platform_scope", "utc_day", "stratum_id", "N_h", "n_h"})
REASON_COUNT_FIELDS = frozenset({"reason_code", "count"})
SOURCE_SELECTED_FIELDS = frozenset("input_sequence candidate_id locator_commitment_sha256 lineage_group_id lineage_unit_sha256 adapter_id source_profile platform utc_day stratum_id rank_sha256 N_h n_h inclusion_probability_numerator inclusion_probability_denominator".split())
SOURCE_SURPLUS_FIELDS = frozenset({"candidate_id", "lineage_unit_sha256", "stratum_id", "rank_sha256"})
A_ITEM_FIELDS = frozenset("input_sequence candidate_id context_unit_sha256 upstream_frame_candidate_id registry_record_id source_profile platform_scope utc_day stratum_id rank_sha256 N_h n_h inclusion_probability_numerator inclusion_probability_denominator".split())
_SUBJECT_FIELDS = frozenset({
    "schema_version", "record_origin", "subject_id", "input_sequence",
    "source_input_sequence", "source_frame_candidate_id", "source_selected_input_sha256",
    "source_lineage_unit_sha256", "a_frame_candidate_id", "a_context_unit_sha256",
    "a_selected_context_sha256", "source_profile", "platform_scope",
    "registry_record_id", "registry_record_commitment_sha256", "bridge_row_sha256",
    "community_scope_commitment_sha256", "capture_receipt_sha256", "source_claim_set_sha256",
    "payload_bytes", "payload_sha256", "surface_span_unit", "surface_start", "surface_end",
    "surface_sha256", "surface_text_sha256", "evidence_disposition", "lineage_raw_sha256",
    "evidence_unit_sha256", "annotation_subject_sha256", "row_sha256",
})
_PRECOMMIT_FIELDS = frozenset({
    "schema_version", "record_origin", "precommit_id", "lineage_raw_sha256",
    "source_sampling_frame_sha256", "source_sampling_plan_artifact_sha256",
    "source_selected_input_set_sha256", "bridge_inventory_sha256",
    "a_context_sampling_frame_sha256", "a_sampling_plan_artifact_sha256",
    "a_selected_context_set_sha256", "frame_domains_separated", "subject_rows_raw_sha256",
    "subject_count", "source_profile_counts", "subject_set_sha256", "precommitted_at",
    "v2_annotation_event_count", "actual_a_context_review_count", "actual_a_context_credit_count",
    "statistical_denominator_contribution", "metric_status", *FALSE_FIELDS,
    "operational_effect", "gate_status", "artifact_sha256",
})
_BRIDGE_FIELDS = frozenset({
    "schema_version", "input_sequence", "candidate_id", "locator_commitment_sha256",
    "lineage_group_id", "lineage_unit_sha256", "adapter_id", "source_profile", "platform",
    "utc_day", "stratum_id", "selected_input_sha256", "registry_record_id",
    "registry_record_commitment_sha256", "content_type", "capture_version",
    "normalization_version", "payload_base64", "payload_bytes", "payload_sha256",
    "bridge_row_sha256",
})
_SHA = re.compile(r"^[0-9a-f]{64}$")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")
_A_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,511}$")
_PLATFORM = re.compile(r"^[a-z0-9][a-z0-9._:-]{0,127}$")
_DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_FORBIDDEN_TEXT_CATEGORIES = frozenset(("Cc", "Cf", "Cs", "Zl", "Zp"))
MAX_OUTPUT_BYTES = 1_000_000
EXPECTED_COMPONENT_MANIFEST = {
    "component": "p0_presented_a_context_annotation_subject_v2_precommit_contract",
    "schemas": [SUBJECT_SCHEMA, PRECOMMIT_SCHEMA], "input_raw_artifact_count": 11,
    "output_raw_artifact_count": 2, "total_bound_raw_artifact_count": 13,
    "max_output_bytes": MAX_OUTPUT_BYTES,
    "consumes_packet_v1_labels_or_events": False, "authority": "NONE",
}
EXPECTED_COMPONENT_MANIFEST_SHA256 = ""


class P0PresentedAContextSubjectV2ParentError(ValueError):
    pass


def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (RecursionError, UnicodeEncodeError, TypeError, ValueError) as exc:
        raise P0PresentedAContextSubjectV2ParentError("value is not canonical JSON") from exc


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _raw(raw: bytes) -> str:
    if type(raw) is not bytes:
        raise P0PresentedAContextSubjectV2ParentError("raw input must be exact bytes")
    return hashlib.sha256(raw).hexdigest()


def _file(value: Any) -> bytes:
    return _canonical(value) + b"\n"


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise P0PresentedAContextSubjectV2ParentError("duplicate key")
        out[key] = value
    return out


def _obj(raw: bytes, label: str) -> dict[str, Any]:
    if type(raw) is not bytes or not raw or len(raw) > 64_000_000 or b"\r" in raw or not raw.endswith(b"\n"):
        raise P0PresentedAContextSubjectV2ParentError(f"{label} framing invalid")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValueError) as exc:
        raise P0PresentedAContextSubjectV2ParentError(f"{label} parse invalid") from exc
    if type(value) is not dict or raw != _file(value):
        raise P0PresentedAContextSubjectV2ParentError(f"{label} noncanonical")
    return value


def _rows(raw: bytes, label: str) -> list[dict[str, Any]]:
    if (type(raw) is not bytes or not raw or len(raw) > 64_000_000
            or raw.startswith(b"\xef\xbb\xbf") or b"\r" in raw
            or not raw.endswith(b"\n") or raw.endswith(b"\n\n")):
        raise P0PresentedAContextSubjectV2ParentError(f"{label} framing invalid")
    rows = [_obj(line + b"\n", label) for line in raw[:-1].split(b"\n")]
    if raw != b"".join(_file(row) for row in rows):
        raise P0PresentedAContextSubjectV2ParentError(f"{label} noncanonical")
    return rows


def _strict(row: Any, fields: frozenset[str], label: str) -> dict[str, Any]:
    if type(row) is not dict or set(row) != fields:
        raise P0PresentedAContextSubjectV2ParentError(f"{label} fields mismatch")
    return row


def _self(row: Mapping[str, Any], field: str, label: str) -> None:
    if type(row[field]) is not str or _SHA.fullmatch(row[field]) is None or row[field] != _digest({k: v for k, v in row.items() if k != field}):
        raise P0PresentedAContextSubjectV2ParentError(f"{label} self hash mismatch")


def _time(value: Any) -> datetime:
    if type(value) is not str or _UTC.fullmatch(value) is None:
        raise P0PresentedAContextSubjectV2ParentError("timestamp invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise P0PresentedAContextSubjectV2ParentError("timestamp invalid") from exc
    if parsed.tzinfo is None:
        raise P0PresentedAContextSubjectV2ParentError("timestamp timezone missing")
    return parsed


def _a_time(value: Any) -> datetime:
    """Mirror the A-frame predecessor's canonical UTC-Z parser (fraction allowed)."""
    if type(value) is not str or not value.endswith("Z"):
        raise P0PresentedAContextSubjectV2ParentError("A timestamp invalid")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise P0PresentedAContextSubjectV2ParentError("A timestamp invalid") from exc
    if parsed.isoformat().replace("+00:00", "Z") != value:
        raise P0PresentedAContextSubjectV2ParentError("A timestamp noncanonical")
    return parsed


def _precommit_time(value: Any) -> datetime:
    """Mirror the successor producer's timezone-aware ISO parser."""
    if type(value) is not str:
        raise P0PresentedAContextSubjectV2ParentError("precommit timestamp invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise P0PresentedAContextSubjectV2ParentError("precommit timestamp invalid") from exc
    if parsed.tzinfo is None:
        raise P0PresentedAContextSubjectV2ParentError("precommit timestamp timezone missing")
    return parsed


def _sha_value(value: Any, label: str) -> str:
    if type(value) is not str or _SHA.fullmatch(value) is None:
        raise P0PresentedAContextSubjectV2ParentError(f"{label} must be lowercase SHA-256")
    return value


def _id_value(value: Any, label: str) -> str:
    if type(value) is not str or _ID.fullmatch(value) is None:
        raise P0PresentedAContextSubjectV2ParentError(f"{label} invalid")
    return value


def _a_id_value(value: Any, label: str) -> str:
    if type(value) is not str or _A_ID.fullmatch(value) is None:
        raise P0PresentedAContextSubjectV2ParentError(f"{label} invalid")
    return value


def _day_value(value: Any, label: str) -> str:
    if type(value) is not str or _DAY.fullmatch(value) is None:
        raise P0PresentedAContextSubjectV2ParentError(f"{label} invalid")
    return value


def _platform_value(value: Any, label: str) -> str:
    if type(value) is not str or _PLATFORM.fullmatch(value) is None:
        raise P0PresentedAContextSubjectV2ParentError(f"{label} invalid")
    return value


def _metadata_value(value: Any, label: str) -> str:
    if (type(value) is not str or not value or len(value) > 512 or value != value.strip()
            or unicodedata.normalize("NFC", value) != value
            or any(unicodedata.category(char) in _FORBIDDEN_TEXT_CATEGORIES for char in value)):
        raise P0PresentedAContextSubjectV2ParentError(f"{label} invalid")
    return value


def _int_value(value: Any, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise P0PresentedAContextSubjectV2ParentError(f"{label} integer invalid")
    return value


def _lineage(raws: Mapping[str, bytes]) -> dict[str, str]:
    if set(raws) != set(LINEAGE_KEYS):
        raise P0PresentedAContextSubjectV2ParentError("raw inventory mismatch")
    if any(type(raws[key]) is not bytes or len(raws[key]) > 64_000_000 for key in LINEAGE_KEYS):
        raise P0PresentedAContextSubjectV2ParentError("raw input type/size invalid")
    return {key: _raw(raws[key]) for key in LINEAGE_KEYS}


def _reject_forbidden_recursive(value: Any, label: str) -> None:
    if type(value) is dict:
        overlap = UPSTREAM_FORBIDDEN.intersection(value)
        if overlap:
            raise P0PresentedAContextSubjectV2ParentError(
                f"{label} contains forbidden pre-label keys: {sorted(overlap)}")
        for child in value.values():
            _reject_forbidden_recursive(child, label)
    elif type(value) is list:
        for child in value:
            _reject_forbidden_recursive(child, label)


def _header(row: Mapping[str, Any], schema: str, label: str, *, origin_required: bool = True) -> None:
    if row.get("schema_version") != schema:
        raise P0PresentedAContextSubjectV2ParentError(f"{label} schema mismatch")
    if origin_required and row.get("record_origin") != ORIGIN:
        raise P0PresentedAContextSubjectV2ParentError(f"{label} origin mismatch")


def _strict_nested(source_scope: Mapping[str, Any], source_frame_value: Mapping[str, Any],
                   source_plan: Mapping[str, Any], a_scope: Mapping[str, Any],
                   a_frame_value: Mapping[str, Any], a_plan: Mapping[str, Any]) -> None:
    inventories = (
        (source_scope["adapter_profile_map"], ADAPTER_FIELDS, "source adapter"),
        (source_scope["strata"], SOURCE_STRATUM_FIELDS, "source stratum"),
        (source_frame_value["stratum_populations"], SOURCE_POP_FIELDS, "source population"),
        (source_frame_value["exclusion_reason_counts"], REASON_COUNT_FIELDS, "source reason count"),
        (source_plan["selected_inputs"], SOURCE_SELECTED_FIELDS, "source selected item"),
        (a_scope["adapter_profile_map"], ADAPTER_FIELDS, "A adapter"),
        (a_scope["strata"], A_STRATUM_FIELDS, "A stratum"),
        (a_frame_value["stratum_populations"], A_POP_FIELDS, "A population"),
        (a_plan["selected_contexts"], A_ITEM_FIELDS, "A selected item"),
        (a_plan["eligible_surplus_contexts"], A_ITEM_FIELDS, "A surplus item"),
    )
    for values, fields, label in inventories:
        if type(values) is not list:
            raise P0PresentedAContextSubjectV2ParentError(f"{label} inventory must be list")
        for value in values:
            _strict(value, fields, label)
    for scope, platform_field, label in (
        (source_scope, "platform", "source stratum"),
        (a_scope, "platform_scope", "A stratum"),
    ):
        for value in scope["strata"]:
            if (type(value["quota"]) is not int or value["quota"] < 1
                    or type(value[platform_field]) is not str or not value[platform_field]):
                raise P0PresentedAContextSubjectV2ParentError(f"{label} value invalid")
    for frame, fields, label in (
        (source_frame_value,
         ("census_byte_count", "census_row_count", "eligible_candidate_count", "excluded_candidate_count",
          "eligible_lineage_unit_count"), "source frame"),
        (a_frame_value,
         ("census_byte_count", "census_row_count", "eligible_candidate_count", "excluded_candidate_count",
          "actual_a_context_review_count", "actual_surplus_review_count"), "A frame"),
    ):
        for field in fields:
            _int_value(frame[field], f"{label} {field}")
    for plan, fields, label in (
        (source_plan, ("input_count", "eligible_surplus_count"), "source plan"),
        (a_plan, ("input_count", "eligible_surplus_count", "actual_a_context_review_count",
                  "actual_surplus_review_count"), "A plan"),
    ):
        for field in fields:
            _int_value(plan[field], f"{label} {field}")
    for population in source_frame_value["stratum_populations"]:
        _int_value(population["N_h"], "source population N_h")
        _int_value(population["n_h"], "source population n_h", 1)
    for population in a_frame_value["stratum_populations"]:
        _int_value(population["N_h"], "A population N_h")
        _int_value(population["n_h"], "A population n_h", 1)
    for reason_count in source_frame_value["exclusion_reason_counts"]:
        _int_value(reason_count["count"], "source reason count")
    for item in source_plan["selected_inputs"]:
        for field in ("input_sequence", "N_h", "n_h", "inclusion_probability_numerator",
                      "inclusion_probability_denominator"):
            _int_value(item[field], f"source selected {field}", 1)
    for item in a_plan["selected_contexts"] + a_plan["eligible_surplus_contexts"]:
        _int_value(item["input_sequence"], "A item input_sequence")
        for field in ("N_h", "n_h", "inclusion_probability_numerator", "inclusion_probability_denominator"):
            _int_value(item[field], f"A item {field}", 1)
    surplus = source_plan.get("eligible_surplus")
    if surplus is not None:
        if type(surplus) is not list:
            raise P0PresentedAContextSubjectV2ParentError("source surplus must be list")
        for value in surplus:
            _strict(value, SOURCE_SURPLUS_FIELDS, "source surplus item")


def _validate_scope_seed_scalars(source_scope: Mapping[str, Any], source_seed: Mapping[str, Any],
                                 a_scope: Mapping[str, Any], a_seed: Mapping[str, Any]) -> None:
    _id_value(source_scope["scope_id"], "source scope_id")
    _a_id_value(a_scope["scope_id"], "A scope_id")
    for field in ("enumeration_policy_sha256", "eligibility_policy_sha256", "rights_policy_sha256",
                  "strata_policy_sha256", "future_seed_spec_sha256"):
        _sha_value(source_scope[field], f"source {field}")
    for field in ("context_enumeration_policy_sha256", "eligibility_policy_sha256", "rights_policy_sha256",
                  "strata_policy_sha256", "future_seed_spec_sha256",
                  "upstream_source_sampling_plan_raw_sha256", "upstream_bridge_inventory_raw_sha256"):
        _sha_value(a_scope[field], f"A {field}")
    for scope, platform_field, label in ((source_scope, "platform", "source"),
                                         (a_scope, "platform_scope", "A")):
        for adapter in scope["adapter_profile_map"]:
            _id_value(adapter["adapter_id"], f"{label} adapter_id")
            if adapter["source_profile"] not in PROFILES:
                raise P0PresentedAContextSubjectV2ParentError(f"{label} adapter profile invalid")
        for stratum in scope["strata"]:
            if stratum["source_profile"] not in PROFILES or type(stratum["quota"]) is not int or stratum["quota"] < 1:
                raise P0PresentedAContextSubjectV2ParentError(f"{label} stratum scalar invalid")
            _platform_value(stratum[platform_field], f"{label} stratum platform")
            _day_value(stratum["utc_day"], f"{label} stratum day")
    for seed, label in ((source_seed, "source seed"),):
        _id_value(seed["seed_receipt_id"], f"{label} receipt id")
        for field in ("scope_sha256", "frame_manifest_sha256", "future_seed_spec_sha256",
                      "revealed_seed_sha256", "frame_owner_precommit_sha256", "artifact_sha256"):
            _sha_value(seed[field], f"{label} {field}")
        _time(seed["frame_owner_precommitted_at"])
        _time(seed["revealed_at"])
    _a_id_value(a_seed["seed_receipt_id"], "A seed receipt id")
    for field in ("scope_sha256", "frame_manifest_sha256", "future_seed_spec_sha256",
                  "revealed_seed_sha256", "frame_owner_precommit_sha256", "artifact_sha256"):
        _sha_value(a_seed[field], f"A seed {field}")
    _a_time(a_seed["frame_owner_precommitted_at"])
    _a_time(a_seed["revealed_at"])
    _sha_value(a_seed["census_raw_sha256"], "A seed census_raw_sha256")


def _validate_census_derivations(source_scope: Mapping[str, Any], source_census: Sequence[Mapping[str, Any]],
                                 a_scope: Mapping[str, Any], a_census: Sequence[Mapping[str, Any]]) -> None:
    source_adapters = {row["adapter_id"]: row["source_profile"] for row in source_scope["adapter_profile_map"]}
    source_strata = {(row["source_profile"], row["platform"], row["utc_day"]) for row in source_scope["strata"]}
    source_groups: dict[str, list[Mapping[str, Any]]] = {}
    for row in source_census:
        source_groups.setdefault(row["lineage_group_id"], []).append(row)
    group_roots: dict[str, Mapping[str, Any] | None] = {}
    for group_id, members in source_groups.items():
        profiles = {source_adapters.get(row["adapter_id"]) for row in members}
        lineage_strata = {(source_adapters.get(row["adapter_id"]), row["platform"], row["utc_day"])
                          for row in members}
        roots = [row for row in members if row["lineage_role"] == "ROOT"]
        if len(profiles) != 1 or None in profiles or len(lineage_strata) != 1 or len(roots) > 1:
            raise P0PresentedAContextSubjectV2ParentError("source lineage group invariant mismatch")
        root = roots[0] if roots else None
        if root is None:
            if any(row["lineage_role"] != "UNKNOWN" for row in members):
                raise P0PresentedAContextSubjectV2ParentError("source rootless lineage mismatch")
        else:
            minimum = min(members, key=lambda row: (row["locator_commitment_sha256"], row["candidate_id"]))
            if root is not minimum or root["locator_commitment_sha256"] != root["lineage_root_locator_commitment_sha256"]:
                raise P0PresentedAContextSubjectV2ParentError("source canonical root mismatch")
        declared_root = members[0]["lineage_root_locator_commitment_sha256"]
        if any(row["lineage_root_locator_commitment_sha256"] != declared_root for row in members):
            raise P0PresentedAContextSubjectV2ParentError("source lineage root commitment mismatch")
        group_roots[group_id] = root
    for index, row in enumerate(source_census, start=1):
        for field in ("locator_commitment_sha256", "lineage_root_locator_commitment_sha256", "row_sha256"):
            _sha_value(row[field], f"source census {field}")
        _id_value(row["adapter_id"], "source census adapter_id")
        _platform_value(row["platform"], "source census platform")
        _day_value(row["utc_day"], "source census day")
        if (type(row["enumeration_sequence"]) is not int
                or any(type(row[field]) is not bool for field in (
                    "presented_rights_policy_assessed", "presented_collection_allowed",
                    "presented_adapter_contract_verified"))
                or row["presented_takedown_status"] not in ("ACTIVE", "PENDING_REMOVAL", "REMOVED")
                or row["eligibility_status"] not in ("ELIGIBLE", "EXCLUDED")):
            raise P0PresentedAContextSubjectV2ParentError("source census enum/type mismatch")
        expected_candidate = "P0:FRAME:CANDIDATE:" + _digest({"domain": "P0_FULL_ELIGIBLE_FRAME_V2_CANDIDATE_ID",
                                                               "locator_commitment_sha256": row["locator_commitment_sha256"]})
        expected_group = "P0:FRAME:LINEAGE:" + _digest({"domain": "P0_FULL_ELIGIBLE_FRAME_V2_LINEAGE_GROUP",
                                                          "root_locator_commitment_sha256": row["lineage_root_locator_commitment_sha256"]})
        profile = source_adapters.get(row["adapter_id"])
        if (row["enumeration_sequence"] != index or row["candidate_id"] != expected_candidate
                or row["lineage_group_id"] != expected_group or row["utc_day"] != row["published_at"][:10]
                or (profile, row["platform"], row["utc_day"]) not in source_strata):
            raise P0PresentedAContextSubjectV2ParentError("source census derived identity mismatch")
        if (row["lineage_role"] not in ("ROOT", "DERIVATIVE", "UNKNOWN")
                or _time(row["published_at"]) > _time(row["observed_at"])
                or _time(row["observed_at"]) > _time(source_scope["frame_cutoff"])):
            raise P0PresentedAContextSubjectV2ParentError("source census base semantics mismatch")
        reasons: list[str] = []
        if row["presented_rights_policy_assessed"] is not True: reasons.append("RIGHTS_POLICY_NOT_ASSESSED")
        if row["presented_collection_allowed"] is not True: reasons.append("COLLECTION_NOT_ALLOWED")
        if row["presented_takedown_status"] != "ACTIVE": reasons.append("TAKEDOWN_NOT_ACTIVE")
        if row["presented_adapter_contract_verified"] is not True: reasons.append("ADAPTER_CONTRACT_NOT_VERIFIED")
        if row["lineage_role"] == "DERIVATIVE": reasons.append("LINEAGE_DERIVATIVE")
        elif row["lineage_role"] == "UNKNOWN": reasons.append("LINEAGE_UNKNOWN")
        if group_roots[row["lineage_group_id"]] is None: reasons.append("LINEAGE_GROUP_HAS_NO_ROOT")
        reasons = [reason for reason in SOURCE_EXCLUSION_REASON_ORDER if reason in reasons]
        if row["exclusion_reason_codes"] != reasons or row["eligibility_status"] != ("EXCLUDED" if reasons else "ELIGIBLE"):
            raise P0PresentedAContextSubjectV2ParentError("source census eligibility mismatch")
    eligible_groups = [row["lineage_group_id"] for row in source_census if row["eligibility_status"] == "ELIGIBLE"]
    if (list(source_census) != sorted(source_census, key=lambda row: row["candidate_id"])
            or len({row["candidate_id"] for row in source_census}) != len(source_census)
            or len({row["locator_commitment_sha256"] for row in source_census}) != len(source_census)
            or len(set(eligible_groups)) != len(eligible_groups)):
        raise P0PresentedAContextSubjectV2ParentError("source census order/uniqueness mismatch")

    a_adapters = {row["adapter_id"]: row["source_profile"] for row in a_scope["adapter_profile_map"]}
    a_strata = {(row["source_profile"], row["platform_scope"], row["utc_day"]) for row in a_scope["strata"]}
    for index, row in enumerate(a_census, start=1):
        for field in ("community_scope_commitment_sha256", "content_fingerprint", "payload_sha256",
                      "surface_sha256", "capture_receipt_sha256", "source_claim_set_sha256",
                      "context_unit_sha256", "row_sha256"):
            _sha_value(row[field], f"A census {field}")
        for field in ("upstream_frame_candidate_id", "registry_record_id", "adapter_id"):
            _id_value(row[field], f"A census {field}")
        _platform_value(row["platform_scope"], "A census platform")
        _day_value(row["utc_day"], "A census day")
        if (type(row["enumeration_sequence"]) is not int
                or any(type(row[field]) is not bool for field in (
                    "presented_rights_policy_assessed", "presented_collection_allowed",
                    "presented_source_binding_verified"))
                or row["presented_takedown_status"] not in ("ACTIVE", "PENDING_REMOVAL", "REMOVED")
                or row["eligibility_status"] not in ("ELIGIBLE", "EXCLUDED")):
            raise P0PresentedAContextSubjectV2ParentError("A census enum/type mismatch")
        unit = _digest({"domain": "P0_PRESENTED_A_CONTEXT_FULL_FRAME_V1_CONTEXT_UNIT",
                        "registry_record_id": row["registry_record_id"], "platform_scope": row["platform_scope"],
                        "community_scope_commitment_sha256": row["community_scope_commitment_sha256"],
                        "content_fingerprint": row["content_fingerprint"], "surface_start": row["surface_start"],
                        "surface_end": row["surface_end"], "surface_sha256": row["surface_sha256"]})
        candidate = "P0:A:FRAME:CANDIDATE:" + _digest({"domain": "P0_PRESENTED_A_CONTEXT_FULL_FRAME_V1_CANDIDATE_ID",
                                                         "context_unit_sha256": unit})
        profile = a_adapters.get(row["adapter_id"])
        day = row["source_published_at"][:10]
        if (_a_time(row["source_published_at"]) > _a_time(row["context_observed_at"])
                or _a_time(row["context_observed_at"]) > _a_time(a_scope["frame_cutoff"])):
            raise P0PresentedAContextSubjectV2ParentError("A census chronology mismatch")
        reasons: list[str] = []
        if row["presented_rights_policy_assessed"] is not True: reasons.append("RIGHTS_POLICY_NOT_ASSESSED")
        if row["presented_collection_allowed"] is not True: reasons.append("COLLECTION_NOT_ALLOWED")
        if row["presented_takedown_status"] != "ACTIVE": reasons.append("TAKEDOWN_NOT_ACTIVE")
        if row["presented_source_binding_verified"] is not True: reasons.append("SOURCE_BINDING_NOT_VERIFIED")
        reasons = [reason for reason in A_EXCLUSION_REASON_ORDER if reason in reasons]
        if (row["enumeration_sequence"] != index or row["context_unit_sha256"] != unit
                or row["candidate_id"] != candidate or row["source_profile"] != profile or row["utc_day"] != day
                or (profile, row["platform_scope"], day) not in a_strata
                or row["exclusion_reason_codes"] != reasons
                or row["eligibility_status"] != ("EXCLUDED" if reasons else "ELIGIBLE")):
            raise P0PresentedAContextSubjectV2ParentError("A census derived identity/eligibility mismatch")
    if (list(a_census) != sorted(a_census, key=lambda row: row["candidate_id"])
            or len({row["candidate_id"] for row in a_census}) != len(a_census)
            or len({row["context_unit_sha256"] for row in a_census}) != len(a_census)):
        raise P0PresentedAContextSubjectV2ParentError("A census order/uniqueness mismatch")


def _validate_frame_plan_constants(source_scope: Mapping[str, Any], source_census: Sequence[Mapping[str, Any]],
                                   source_frame_value: Mapping[str, Any], source_plan: Mapping[str, Any],
                                   a_scope: Mapping[str, Any], a_census: Sequence[Mapping[str, Any]],
                                   a_frame_value: Mapping[str, Any], a_plan: Mapping[str, Any]) -> None:
    source_adapter_rows = source_scope["adapter_profile_map"]
    source_strata = source_scope["strata"]
    source_profile_order = {profile: index for index, profile in enumerate(PROFILES)}
    if (not source_adapter_rows or source_adapter_rows != sorted(source_adapter_rows, key=lambda row: row["adapter_id"])
            or len({row["adapter_id"] for row in source_adapter_rows}) != len(source_adapter_rows)
            or any(row["source_profile"] not in PROFILES for row in source_adapter_rows)
            or not source_strata
            or source_strata != sorted(source_strata, key=lambda row: (source_profile_order.get(row["source_profile"], 99), row["platform"], row["utc_day"]))
            or len({(row["source_profile"], row["platform"], row["utc_day"]) for row in source_strata}) != len(source_strata)
            or {profile: sum(row["quota"] for row in source_strata if row["source_profile"] == profile) for profile in PROFILES}
               != {profile: 10 for profile in PROFILES}):
        raise P0PresentedAContextSubjectV2ParentError("source scope nested accounting mismatch")
    if (source_scope["selection_algorithm"] != "SHA256_STRATIFIED_SRSWOR_WITHOUT_REPLACEMENT_V2"
            or source_scope["lineage_policy"] != "CANONICAL_MIN_ROOT_ONE_UNIT_PER_GROUP_V2"
            or source_scope["expected_per_profile_quota"] != 10 or source_scope["expected_total_quota"] != 40
            or source_plan["selection_algorithm"] != source_scope["selection_algorithm"]
            or source_plan["input_count"] != 40 or source_plan["presented_serialization_only"] is not True
            or source_plan["gate_status"] != "NO_GO_DETERMINISTIC_EXAMPLE_PLAN_ONLY"
            or source_frame_value["presented_census_serialization_verified"] is not True
            or source_frame_value["presented_serialization_only"] is not True
            or source_frame_value["gate_status"] != "NO_GO_PRESENTED_SERIALIZATION_ONLY"):
        raise P0PresentedAContextSubjectV2ParentError("source structural constants mismatch")
    source_eligible = [row for row in source_census if row["eligibility_status"] == "ELIGIBLE"]
    source_excluded = [row for row in source_census if row["eligibility_status"] == "EXCLUDED"]
    source_adapters = {row["adapter_id"]: row["source_profile"] for row in source_adapter_rows}
    projections = []
    eligible_units = []
    for row in source_census:
        unit = _digest({"domain": "P0_FULL_ELIGIBLE_FRAME_V2_LINEAGE_UNIT",
                        "lineage_group_id": row["lineage_group_id"], "candidate_id": row["candidate_id"],
                        "locator_commitment_sha256": row["locator_commitment_sha256"]})
        projection = {"candidate_id": row["candidate_id"], "locator_commitment_sha256": row["locator_commitment_sha256"],
                      "lineage_group_id": row["lineage_group_id"], "lineage_unit_sha256": unit,
                      "adapter_id": row["adapter_id"], "source_profile": source_adapters[row["adapter_id"]],
                      "platform": row["platform"], "utc_day": row["utc_day"],
                      "eligibility_status": row["eligibility_status"],
                      "exclusion_reason_codes": row["exclusion_reason_codes"], "row_sha256": row["row_sha256"]}
        projections.append(projection)
        if row["eligibility_status"] == "ELIGIBLE":
            eligible_units.append({key: projection[key] for key in (
                "candidate_id", "locator_commitment_sha256", "lineage_group_id", "lineage_unit_sha256",
                "adapter_id", "source_profile", "platform", "utc_day")})
    source_counts = Counter((row["source_profile"], row["platform"], row["utc_day"]) for row in eligible_units)
    source_populations = [{"source_profile": spec["source_profile"], "platform": spec["platform"],
                           "utc_day": spec["utc_day"],
                           "stratum_id": "P0:FRAME:STRATUM:" + _digest({
                               "domain": "P0_FULL_ELIGIBLE_FRAME_V2_STRATUM_ID",
                               "source_profile": spec["source_profile"], "platform": spec["platform"],
                               "utc_day": spec["utc_day"]}),
                           "N_h": source_counts[(spec["source_profile"], spec["platform"], spec["utc_day"])],
                           "n_h": spec["quota"]} for spec in source_strata]
    source_reason_counts = Counter(reason for row in source_excluded for reason in row["exclusion_reason_codes"])
    expected_reason_counts = [{"reason_code": reason, "count": source_reason_counts[reason]}
                              for reason in SOURCE_EXCLUSION_REASON_ORDER]
    if (source_frame_value["eligible_candidate_count"] != len(source_eligible)
            or source_frame_value["excluded_candidate_count"] != len(source_excluded)
            or source_frame_value["eligible_lineage_unit_count"] != len(source_eligible)
            or source_frame_value["derived_candidate_inventory_sha256"] != _digest(projections)
            or source_frame_value["eligible_sampling_units_sha256"] != _digest(eligible_units)
            or source_frame_value["excluded_candidates_sha256"] != _digest([projection for projection in projections if projection["eligibility_status"] == "EXCLUDED"])
            or source_frame_value["exclusion_reason_counts"] != expected_reason_counts
            or source_frame_value["stratum_populations"] != source_populations):
        raise P0PresentedAContextSubjectV2ParentError("source frame accounting mismatch")

    a_adapter_rows = a_scope["adapter_profile_map"]
    a_strata = a_scope["strata"]
    if (not a_adapter_rows or a_adapter_rows != sorted(a_adapter_rows, key=lambda row: row["adapter_id"])
            or len({row["adapter_id"] for row in a_adapter_rows}) != len(a_adapter_rows)
            or any(row["source_profile"] not in PROFILES for row in a_adapter_rows)
            or not a_strata
            or a_strata != sorted(a_strata, key=lambda row: (source_profile_order.get(row["source_profile"], 99), row["platform_scope"], row["utc_day"]))
            or len({(row["source_profile"], row["platform_scope"], row["utc_day"]) for row in a_strata}) != len(a_strata)
            or {profile: sum(row["quota"] for row in a_strata if row["source_profile"] == profile) for profile in PROFILES}
               != {profile: 5 for profile in PROFILES}):
        raise P0PresentedAContextSubjectV2ParentError("A scope nested accounting mismatch")
    if (a_scope["selection_algorithm"] != "SHA256_A_CONTEXT_STRATIFIED_SRSWOR_WITHOUT_REPLACEMENT_V1"
            or a_scope["expected_per_profile_quota"] != 5 or a_scope["expected_total_quota"] != 20
            or a_plan["selection_algorithm"] != a_scope["selection_algorithm"] or a_plan["input_count"] != 20
            or a_plan["presented_serialization_only"] is not True
            or a_plan["metric_status"] != "METRICS_NOT_ESTIMABLE_PRESENTED_FRAME_ONLY"
            or a_plan["gate_status"] != "PRESENTED_A_CONTEXT_FRAME_CONDITIONAL_DESIGN_ONLY_ALL_AUTHORITY_NO_GO"
            or a_frame_value["presented_census_serialization_verified"] is not True
            or a_frame_value["presented_serialization_only"] is not True
            or a_frame_value["metric_status"] != "METRICS_NOT_ESTIMABLE_PRESENTED_FRAME_ONLY"
            or a_frame_value["gate_status"] != "PRESENTED_A_CONTEXT_FRAME_CONDITIONAL_DESIGN_ONLY_ALL_AUTHORITY_NO_GO"):
        raise P0PresentedAContextSubjectV2ParentError("A structural constants mismatch")
    a_eligible = [row for row in a_census if row["eligibility_status"] == "ELIGIBLE"]
    a_excluded = [row for row in a_census if row["eligibility_status"] == "EXCLUDED"]
    a_counts = Counter((row["source_profile"], row["platform_scope"], row["utc_day"]) for row in a_eligible)
    a_populations = [{"source_profile": spec["source_profile"], "platform_scope": spec["platform_scope"],
                      "utc_day": spec["utc_day"],
                      "stratum_id": "P0:A:FRAME:STRATUM:" + _digest({
                          "domain": "P0_PRESENTED_A_CONTEXT_FULL_FRAME_V1_STRATUM_ID",
                          "source_profile": spec["source_profile"], "platform_scope": spec["platform_scope"],
                          "utc_day": spec["utc_day"]}),
                      "N_h": a_counts[(spec["source_profile"], spec["platform_scope"], spec["utc_day"])],
                      "n_h": spec["quota"]} for spec in a_strata]
    expected_partition = _digest(sorted(row["candidate_id"] for row in a_eligible))
    if (a_frame_value["eligible_candidate_count"] != len(a_eligible)
            or a_frame_value["excluded_candidate_count"] != len(a_excluded)
            or a_frame_value["eligible_sampling_units_sha256"] != _digest([row["context_unit_sha256"] for row in a_eligible])
            or a_frame_value["excluded_candidates_sha256"] != _digest([row["candidate_id"] for row in a_excluded])
            or a_frame_value["stratum_populations"] != a_populations
            or a_plan["eligible_partition_sha256"] != expected_partition):
        raise P0PresentedAContextSubjectV2ParentError("A frame/partition accounting mismatch")


def _source_expected_selection(scope: Mapping[str, Any], census: Sequence[Mapping[str, Any]],
                               frame: Mapping[str, Any], seed: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str]:
    adapters = {row["adapter_id"]: row["source_profile"] for row in scope["adapter_profile_map"]}
    eligible: list[dict[str, Any]] = []
    for row in census:
        if row["eligibility_status"] != "ELIGIBLE":
            continue
        unit = _digest({"domain": "P0_FULL_ELIGIBLE_FRAME_V2_LINEAGE_UNIT",
                        "lineage_group_id": row["lineage_group_id"], "candidate_id": row["candidate_id"],
                        "locator_commitment_sha256": row["locator_commitment_sha256"]})
        eligible.append({"candidate_id": row["candidate_id"], "locator_commitment_sha256": row["locator_commitment_sha256"],
                         "lineage_group_id": row["lineage_group_id"], "lineage_unit_sha256": unit,
                         "adapter_id": row["adapter_id"], "source_profile": adapters[row["adapter_id"]],
                         "platform": row["platform"], "utc_day": row["utc_day"]})
    eligible_sha = _digest(eligible)
    if frame["eligible_sampling_units_sha256"] != eligible_sha:
        raise P0PresentedAContextSubjectV2ParentError("source eligible inventory hash mismatch")
    derived = _digest({"domain": "P0_FULL_ELIGIBLE_FRAME_V2_DERIVED_SEED",
                       "scope_sha256": scope["artifact_sha256"],
                       "future_seed_spec_sha256": scope["future_seed_spec_sha256"],
                       "revealed_seed_sha256": seed["revealed_seed_sha256"]})
    selected: list[dict[str, Any]] = []
    surplus: list[dict[str, Any]] = []
    for spec in scope["strata"]:
        key = (spec["source_profile"], spec["platform"], spec["utc_day"])
        members = [row for row in eligible if (row["source_profile"], row["platform"], row["utc_day"]) == key]
        if len(members) < spec["quota"]:
            raise P0PresentedAContextSubjectV2ParentError("source stratum underfill")
        sid = "P0:FRAME:STRATUM:" + _digest({"domain": "P0_FULL_ELIGIBLE_FRAME_V2_STRATUM_ID",
                                              "source_profile": key[0], "platform": key[1], "utc_day": key[2]})
        ranked = sorted(((_digest({"domain": "P0_FULL_ELIGIBLE_FRAME_V2_RANK",
                                    "derived_seed_sha256": derived, "eligible_sampling_units_sha256": eligible_sha,
                                    "stratum_id": sid, "lineage_unit_sha256": row["lineage_unit_sha256"]}), row)
                         for row in members), key=lambda pair: (pair[0], pair[1]["candidate_id"]))
        gcd = math.gcd(spec["quota"], len(members))
        for rank, row in ranked[:spec["quota"]]:
            selected.append({"input_sequence": len(selected) + 1, **row, "stratum_id": sid,
                             "rank_sha256": rank, "N_h": len(members), "n_h": spec["quota"],
                             "inclusion_probability_numerator": spec["quota"] // gcd,
                             "inclusion_probability_denominator": len(members) // gcd})
        surplus.extend({"candidate_id": row["candidate_id"], "lineage_unit_sha256": row["lineage_unit_sha256"],
                        "stratum_id": sid, "rank_sha256": rank} for rank, row in ranked[spec["quota"]:])
    return selected, surplus, derived


def _a_expected_selection(scope: Mapping[str, Any], census: Sequence[Mapping[str, Any]],
                          frame: Mapping[str, Any], seed: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str]:
    eligible = [row for row in census if row["eligibility_status"] == "ELIGIBLE"]
    eligible_sha = _digest([row["context_unit_sha256"] for row in eligible])
    if frame["eligible_sampling_units_sha256"] != eligible_sha:
        raise P0PresentedAContextSubjectV2ParentError("A eligible inventory hash mismatch")
    derived = _digest({"domain": "P0_PRESENTED_A_CONTEXT_FULL_FRAME_V1_DERIVED_SEED",
                       "scope_sha256": scope["artifact_sha256"], "frame_manifest_sha256": frame["artifact_sha256"],
                       "future_seed_spec_sha256": scope["future_seed_spec_sha256"],
                       "revealed_seed_sha256": seed["revealed_seed_sha256"],
                       "frame_owner_precommit_sha256": seed["frame_owner_precommit_sha256"]})
    selected: list[dict[str, Any]] = []
    surplus: list[dict[str, Any]] = []
    sequence = 1
    for spec in scope["strata"]:
        key = (spec["source_profile"], spec["platform_scope"], spec["utc_day"])
        members = [row for row in eligible if (row["source_profile"], row["platform_scope"], row["utc_day"]) == key]
        if len(members) < spec["quota"]:
            raise P0PresentedAContextSubjectV2ParentError("A stratum underfill")
        sid = "P0:A:FRAME:STRATUM:" + _digest({"domain": "P0_PRESENTED_A_CONTEXT_FULL_FRAME_V1_STRATUM_ID",
                                                "source_profile": key[0], "platform_scope": key[1], "utc_day": key[2]})
        ranked = sorted(((_digest({"domain": "P0_PRESENTED_A_CONTEXT_FULL_FRAME_V1_RANK",
                                    "derived_seed_sha256": derived, "eligible_sampling_units_sha256": eligible_sha,
                                    "stratum_id": sid, "context_unit_sha256": row["context_unit_sha256"]}), row)
                         for row in members), key=lambda pair: (pair[0], pair[1]["candidate_id"]))
        fraction = Fraction(spec["quota"], len(members))
        for offset, (rank, row) in enumerate(ranked):
            item = {"input_sequence": sequence if offset < spec["quota"] else 0,
                    "candidate_id": row["candidate_id"], "context_unit_sha256": row["context_unit_sha256"],
                    "upstream_frame_candidate_id": row["upstream_frame_candidate_id"],
                    "registry_record_id": row["registry_record_id"], "source_profile": row["source_profile"],
                    "platform_scope": row["platform_scope"], "utc_day": row["utc_day"], "stratum_id": sid,
                    "rank_sha256": rank, "N_h": len(members), "n_h": spec["quota"],
                    "inclusion_probability_numerator": fraction.numerator,
                    "inclusion_probability_denominator": fraction.denominator}
            (selected if offset < spec["quota"] else surplus).append(item)
            if offset < spec["quota"]:
                sequence += 1
    surplus.sort(key=lambda row: (row["source_profile"], row["platform_scope"], row["utc_day"], row["rank_sha256"], row["candidate_id"]))
    return selected, surplus, derived


def _bridge(raw: bytes, selected: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows = _rows(raw, "bridge")
    if len(rows) != 40 or len(selected) != 40:
        raise P0PresentedAContextSubjectV2ParentError("bridge/source selected count mismatch")
    seen: set[str] = set()
    total_payload_bytes = 0
    identity = ("input_sequence", "candidate_id", "locator_commitment_sha256", "lineage_group_id",
                "lineage_unit_sha256", "adapter_id", "source_profile", "platform", "utc_day", "stratum_id")
    for index, (row, source) in enumerate(zip(rows, selected), start=1):
        _strict(row, _BRIDGE_FIELDS, "bridge row")
        if row["schema_version"] != "p0_presented_registry_capture_bridge_row_v1" or type(row["input_sequence"]) is not int or row["input_sequence"] != index:
            raise P0PresentedAContextSubjectV2ParentError("bridge schema/order mismatch")
        if any(row[field] != source[field] for field in identity) or row["selected_input_sha256"] != _digest(source):
            raise P0PresentedAContextSubjectV2ParentError("bridge/source selected identity mismatch")
        _sha_value(row["selected_input_sha256"], "bridge selected input SHA")
        _id_value(row["registry_record_id"], "bridge registry_record_id")
        if row["registry_record_id"] == source["candidate_id"]:
            raise P0PresentedAContextSubjectV2ParentError("bridge registry/candidate domains collide")
        if row["registry_record_id"] in seen:
            raise P0PresentedAContextSubjectV2ParentError("duplicate bridge registry")
        seen.add(row["registry_record_id"])
        _sha_value(row["registry_record_commitment_sha256"], "bridge registry commitment")
        _sha_value(row["payload_sha256"], "bridge payload SHA")
        _sha_value(row["bridge_row_sha256"], "bridge row SHA")
        for field in ("content_type", "capture_version", "normalization_version"):
            _metadata_value(row[field], f"bridge {field}")
        if type(row["payload_base64"]) is not str:
            raise P0PresentedAContextSubjectV2ParentError("bridge payload_base64 must be text")
        try:
            payload = base64.b64decode(row["payload_base64"].encode("ascii"), validate=True)
        except (ValueError, UnicodeEncodeError) as exc:
            raise P0PresentedAContextSubjectV2ParentError("bridge payload invalid") from exc
        if (len(payload) > 256 * 1024
                or base64.b64encode(payload).decode("ascii") != row["payload_base64"]
                or type(row["payload_bytes"]) is not int or row["payload_bytes"] != len(payload)
                or row["payload_sha256"] != hashlib.sha256(payload).hexdigest()):
            raise P0PresentedAContextSubjectV2ParentError("bridge payload binding mismatch")
        total_payload_bytes += len(payload)
        if total_payload_bytes > 40 * 256 * 1024:
            raise P0PresentedAContextSubjectV2ParentError("bridge total payload bound exceeded")
        _self(row, "bridge_row_sha256", "bridge row")
    return rows


def _derive_subjects(raws: Mapping[str, bytes]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    _lineage(raws)
    # This parent performs bounded structural/raw-lineage replay plus both
    # deterministic selection/partition algorithms. It does not claim full
    # upstream census eligibility/frame semantic parity.
    source_scope = _obj(raws["source_scope"], "source scope")
    source_plan = _obj(raws["source_plan"], "source plan")
    source_frame_value = _obj(raws["source_frame"], "source frame")
    source_seed = _obj(raws["source_seed"], "source seed")
    source_census = _rows(raws["source_census"], "source census")
    _strict(source_scope, SOURCE_SCOPE_FIELDS, "source scope")
    _strict(source_frame_value, SOURCE_FRAME_FIELDS, "source frame")
    _strict(source_seed, SOURCE_SEED_FIELDS, "source seed")
    _strict(source_plan, SOURCE_PLAN_FIELDS, "source plan")
    for row in source_census:
        _strict(row, SOURCE_CENSUS_FIELDS, "source census row")
    _header(source_scope, "p0_full_eligible_sampling_scope_v2", "source scope")
    _header(source_frame_value, "p0_full_eligible_frame_manifest_v2", "source frame")
    _header(source_seed, "p0_sampling_seed_receipt_v2", "source seed")
    _header(source_plan, "p0_deterministic_stratified_srswor_plan_v2", "source plan")
    for row in source_census:
        _header(row, "p0_full_eligible_census_row_v2", "source census row")
    if not (
        _time(source_scope["created_at"]) <= _time(source_scope["frame_cutoff"])
        < _time(source_frame_value["frame_sealed_at"])
        < _time(source_seed["frame_owner_precommitted_at"])
        < _time(source_seed["revealed_at"])
        < _time(source_plan["selection_sealed_at"])
    ):
        raise P0PresentedAContextSubjectV2ParentError("source full chronology mismatch")
    for value, field, label in ((source_scope, "artifact_sha256", "source scope"),
                                (source_frame_value, "artifact_sha256", "source frame"),
                                (source_seed, "artifact_sha256", "source seed"),
                                (source_plan, "artifact_sha256", "source plan")):
        _self(value, field, label)
    for row in source_census:
        _self(row, "row_sha256", "source census row")
        if row["action_applied"] is not False or row["operational_effect"] != OPERATIONAL_EFFECT:
            raise P0PresentedAContextSubjectV2ParentError("source census authority mismatch")
    if (source_scope["labels_observed"] is not False or source_scope["semantic_fields_used"] is not False
            or source_scope["action_applied"] is not False or source_scope["operational_effect"] != OPERATIONAL_EFFECT):
        raise P0PresentedAContextSubjectV2ParentError("source scope authority mismatch")
    if (any(source_frame_value[field] is not False for field in SOURCE_FALSE)
            or source_frame_value["action_applied"] is not False
            or source_frame_value["operational_effect"] != OPERATIONAL_EFFECT):
        raise P0PresentedAContextSubjectV2ParentError("source frame authority mismatch")
    if (source_seed["owner_authority_verified"] is not False or source_seed["seed_authority_verified"] is not False
            or source_seed["action_applied"] is not False or source_seed["operational_effect"] != OPERATIONAL_EFFECT):
        raise P0PresentedAContextSubjectV2ParentError("source seed authority mismatch")
    if (any(source_plan[field] is not False for field in SOURCE_FALSE)
            or source_plan["action_applied"] is not False or source_plan["operational_effect"] != OPERATIONAL_EFFECT
            or source_plan["without_replacement"] is not True or source_plan["spill_allowed"] is not False
            or source_plan["replacement_allowed"] is not False):
        raise P0PresentedAContextSubjectV2ParentError("source plan authority/design mismatch")
    if (source_frame_value["scope_sha256"] != source_scope["artifact_sha256"]
            or source_frame_value["census_raw_sha256"] != _raw(raws["source_census"])
            or source_frame_value["census_byte_count"] != len(raws["source_census"])
            or source_frame_value["census_row_count"] != len(source_census)
            or source_seed["scope_sha256"] != source_scope["artifact_sha256"]
            or source_seed["frame_manifest_sha256"] != source_frame_value["artifact_sha256"]
            or source_seed["future_seed_spec_sha256"] != source_scope["future_seed_spec_sha256"]
            or source_plan["scope_sha256"] != source_scope["artifact_sha256"]
            or source_plan["frame_manifest_sha256"] != source_frame_value["artifact_sha256"]
            or source_plan["seed_receipt_sha256"] != source_seed["artifact_sha256"]):
        raise P0PresentedAContextSubjectV2ParentError("source raw chain mismatch")
    selected_source = source_plan.get("selected_inputs")
    if type(selected_source) is not list or len(selected_source) != 40:
        raise P0PresentedAContextSubjectV2ParentError("source selected40 missing")
    if [row.get("input_sequence") for row in selected_source] != list(range(1, 41)):
        raise P0PresentedAContextSubjectV2ParentError("source selected order mismatch")
    if source_plan["selected_input_set_sha256"] != _digest(selected_source):
        raise P0PresentedAContextSubjectV2ParentError("source selected set hash mismatch")
    expected_source_selected, expected_source_surplus, expected_source_seed = _source_expected_selection(
        source_scope, source_census, source_frame_value, source_seed)
    source_counts = Counter(row["source_profile"] for row in selected_source)
    if (type(source_plan["per_profile_counts"]) is not dict
            or set(source_plan["per_profile_counts"]) != set(PROFILES)
            or any(type(value) is not int for value in source_plan["per_profile_counts"].values())
            or source_plan["per_profile_counts"] != {profile: source_counts[profile] for profile in PROFILES}
            or source_plan["per_profile_counts"] != {profile: 10 for profile in PROFILES}):
        raise P0PresentedAContextSubjectV2ParentError("source per-profile accounting mismatch")
    if (selected_source != expected_source_selected
            or source_plan["derived_seed_sha256"] != expected_source_seed
            or source_plan["eligible_surplus_count"] != len(expected_source_surplus)
            or source_plan["eligible_surplus_sha256"] != _digest(expected_source_surplus)):
        raise P0PresentedAContextSubjectV2ParentError("source deterministic selection/partition mismatch")
    census_ids = {row["candidate_id"] for row in source_census}
    if len({row["candidate_id"] for row in selected_source}) != 40 or not {row["candidate_id"] for row in selected_source}.issubset(census_ids):
        raise P0PresentedAContextSubjectV2ParentError("source selected/census mismatch")
    source_census_by_id = {row["candidate_id"]: row for row in source_census}
    source_identity = ("candidate_id", "locator_commitment_sha256", "lineage_group_id",
                       "adapter_id", "platform", "utc_day")
    adapter_profiles = {row["adapter_id"]: row["source_profile"] for row in source_scope["adapter_profile_map"]}
    for selected in selected_source:
        candidate = source_census_by_id[selected["candidate_id"]]
        if (any(selected[field] != candidate[field] for field in source_identity)
                or selected["source_profile"] != adapter_profiles.get(candidate["adapter_id"])):
            raise P0PresentedAContextSubjectV2ParentError("source selected projection drift")
    bridge_rows = _bridge(raws["bridge_inventory"], source_plan["selected_inputs"])
    a_scope = _obj(raws["a_scope"], "A scope")
    a_frame_value = _obj(raws["a_frame"], "A frame")
    a_seed = _obj(raws["a_seed"], "A seed")
    a_plan = _obj(raws["a_plan"], "A plan")
    a_census = _rows(raws["a_census"], "A census")
    _strict(a_scope, A_SCOPE_FIELDS, "A scope")
    _strict(a_frame_value, A_FRAME_FIELDS, "A frame")
    _strict(a_seed, A_SEED_FIELDS, "A seed")
    _strict(a_plan, A_PLAN_FIELDS, "A plan")
    for row in a_census:
        _strict(row, A_CENSUS_FIELDS, "A census row")
    _strict_nested(source_scope, source_frame_value, source_plan, a_scope, a_frame_value, a_plan)
    _validate_scope_seed_scalars(source_scope, source_seed, a_scope, a_seed)
    _validate_census_derivations(source_scope, source_census, a_scope, a_census)
    _validate_frame_plan_constants(source_scope, source_census, source_frame_value, source_plan,
                                   a_scope, a_census, a_frame_value, a_plan)
    _header(a_scope, "p0_presented_a_context_full_sampling_scope_v1", "A scope")
    _header(a_frame_value, "p0_presented_a_context_full_frame_manifest_v1", "A frame")
    _header(a_seed, "p0_presented_a_context_sampling_seed_receipt_v1", "A seed")
    _header(a_plan, "p0_presented_a_context_stratified_plan_v1", "A plan")
    for row in a_census:
        _header(row, "p0_presented_a_context_full_census_row_v1", "A census row")
    if not (
        _a_time(a_scope["created_at"]) <= _a_time(a_scope["frame_cutoff"])
        < _a_time(a_frame_value["frame_sealed_at"])
        < _a_time(a_seed["frame_owner_precommitted_at"])
        < _a_time(a_seed["revealed_at"])
        < _a_time(a_plan["selection_sealed_at"])
    ):
        raise P0PresentedAContextSubjectV2ParentError("A full chronology mismatch")
    for label, value in (
        ("source scope", source_scope), ("source census", source_census),
        ("source frame", source_frame_value), ("source seed", source_seed),
        ("source plan", source_plan), ("bridge", bridge_rows), ("A scope", a_scope),
        ("A census", a_census), ("A frame", a_frame_value), ("A seed", a_seed),
        ("A plan", a_plan),
    ):
        _reject_forbidden_recursive(value, label)
    for value, label in ((a_scope, "A scope"), (a_frame_value, "A frame"),
                         (a_seed, "A seed"), (a_plan, "A plan")):
        _self(value, "artifact_sha256", label)
    for row in a_census:
        _self(row, "row_sha256", "A census row")
        if row["action_applied"] is not False or row["operational_effect"] != OPERATIONAL_EFFECT:
            raise P0PresentedAContextSubjectV2ParentError("A census authority mismatch")
    if (a_scope["labels_observed"] is not False or a_scope["semantic_truth_fields_used"] is not False
            or a_scope["annotation_started"] is not False or a_scope["action_applied"] is not False
            or a_scope["operational_effect"] != OPERATIONAL_EFFECT):
        raise P0PresentedAContextSubjectV2ParentError("A scope authority mismatch")
    if (any(a_frame_value[field] is not False for field in A_FALSE)
            or a_frame_value["action_applied"] is not False or a_frame_value["operational_effect"] != OPERATIONAL_EFFECT
            or a_frame_value["actual_a_context_review_count"] != 0
            or a_frame_value["actual_surplus_review_count"] != 0):
        raise P0PresentedAContextSubjectV2ParentError("A frame authority/metric mismatch")
    if (a_seed["owner_authority_verified"] is not False or a_seed["seed_authority_verified"] is not False
            or a_seed["action_applied"] is not False or a_seed["operational_effect"] != OPERATIONAL_EFFECT):
        raise P0PresentedAContextSubjectV2ParentError("A seed authority mismatch")
    if (any(a_plan[field] is not False for field in A_FALSE)
            or a_plan["action_applied"] is not False or a_plan["operational_effect"] != OPERATIONAL_EFFECT
            or a_plan["without_replacement"] is not True or a_plan["spill_allowed"] is not False
            or a_plan["replacement_allowed"] is not False
            or a_plan["actual_a_context_review_count"] != 0 or a_plan["actual_surplus_review_count"] != 0
            or a_plan["inferential_metrics_allowed"] is not False
            or a_plan["complete_case_metrics_allowed"] is not False
            or a_plan["statistical_denominator_contribution"] != "NONE"):
        raise P0PresentedAContextSubjectV2ParentError("A plan authority/metric mismatch")
    if a_scope["upstream_source_sampling_plan_raw_sha256"] != _raw(raws["source_plan"]) or a_scope["upstream_bridge_inventory_raw_sha256"] != _raw(raws["bridge_inventory"]):
        raise P0PresentedAContextSubjectV2ParentError("A scope predecessor raw binding mismatch")
    if (_time(source_plan["selection_sealed_at"]) >= _a_time(a_scope["created_at"])
            or a_frame_value["scope_sha256"] != a_scope["artifact_sha256"]
            or a_frame_value["census_raw_sha256"] != _raw(raws["a_census"])
            or a_frame_value["census_byte_count"] != len(raws["a_census"])
            or a_frame_value["census_row_count"] != len(a_census)
            or a_seed["scope_sha256"] != a_scope["artifact_sha256"]
            or a_seed["frame_manifest_sha256"] != a_frame_value["artifact_sha256"]
            or a_seed["census_raw_sha256"] != _raw(raws["a_census"])
            or a_seed["future_seed_spec_sha256"] != a_scope["future_seed_spec_sha256"]
            or a_plan["scope_sha256"] != a_scope["artifact_sha256"]
            or a_plan["frame_manifest_sha256"] != a_frame_value["artifact_sha256"]
            or a_plan["seed_receipt_sha256"] != a_seed["artifact_sha256"]):
        raise P0PresentedAContextSubjectV2ParentError("A raw chain/chronology mismatch")
    selected_a_rows = a_plan.get("selected_contexts")
    if type(selected_a_rows) is not list or len(selected_a_rows) != 20 or [row.get("input_sequence") for row in selected_a_rows] != list(range(1, 21)):
        raise P0PresentedAContextSubjectV2ParentError("A selected20/order mismatch")
    if a_plan["selected_context_set_sha256"] != _digest(selected_a_rows):
        raise P0PresentedAContextSubjectV2ParentError("A selected set hash mismatch")
    expected_a_selected, expected_a_surplus, expected_a_seed = _a_expected_selection(
        a_scope, a_census, a_frame_value, a_seed)
    a_counts = Counter(row["source_profile"] for row in selected_a_rows)
    if (type(a_plan["per_profile_counts"]) is not dict
            or set(a_plan["per_profile_counts"]) != set(PROFILES)
            or any(type(value) is not int for value in a_plan["per_profile_counts"].values())
            or a_plan["per_profile_counts"] != {profile: a_counts[profile] for profile in PROFILES}
            or a_plan["per_profile_counts"] != {profile: 5 for profile in PROFILES}):
        raise P0PresentedAContextSubjectV2ParentError("A per-profile accounting mismatch")
    if (selected_a_rows != expected_a_selected
            or a_plan["derived_seed_sha256"] != expected_a_seed
            or a_plan["eligible_surplus_contexts"] != expected_a_surplus
            or a_plan["eligible_surplus_count"] != len(expected_a_surplus)
            or a_plan["eligible_surplus_set_sha256"] != _digest(expected_a_surplus)):
        raise P0PresentedAContextSubjectV2ParentError("A deterministic selection/partition mismatch")
    a_census_by_candidate = {row["candidate_id"]: row for row in a_census}
    a_identity = ("candidate_id", "context_unit_sha256", "upstream_frame_candidate_id",
                  "registry_record_id", "source_profile", "platform_scope", "utc_day")
    for selected in selected_a_rows:
        candidate = a_census_by_candidate.get(selected["candidate_id"])
        if candidate is None or any(selected[field] != candidate[field] for field in a_identity):
            raise P0PresentedAContextSubjectV2ParentError("A selected projection drift")
    if raws["source_frame"] == raws["a_frame"] or source_frame_value["artifact_sha256"] == a_frame_value["artifact_sha256"]:
        raise P0PresentedAContextSubjectV2ParentError("frame domains not distinct")
    lineage = _lineage(raws)
    source_census_by_id = {row["candidate_id"]: row for row in source_census}
    source_by_id = {row["candidate_id"]: row for row in source_plan["selected_inputs"]}
    bridge_by_id = {row["candidate_id"]: row for row in bridge_rows}
    a_census_by_id = {row["candidate_id"]: row for row in a_census}
    subjects: list[dict[str, Any]] = []
    # Every A census row, including surplus/excluded rows, must replay a real
    # source-selected/bridge context. Multiple surface opportunities per source are allowed.
    for candidate in a_census:
        source = source_by_id.get(candidate.get("upstream_frame_candidate_id"))
        bridge = bridge_by_id.get(candidate.get("upstream_frame_candidate_id"))
        source_candidate = source_census_by_id.get(candidate.get("upstream_frame_candidate_id"))
        if source is None or bridge is None or source_candidate is None:
            raise P0PresentedAContextSubjectV2ParentError("A census predecessor missing")
        try:
            text = base64.b64decode(bridge["payload_base64"].encode("ascii"), validate=True).decode("utf-8")
        except (ValueError, UnicodeDecodeError, UnicodeEncodeError) as exc:
            raise P0PresentedAContextSubjectV2ParentError("A context payload must be strict UTF-8") from exc
        start, end = candidate["surface_start"], candidate["surface_end"]
        if type(start) is not int or type(end) is not int or start < 0 or end <= start or end > len(text):
            raise P0PresentedAContextSubjectV2ParentError("A character span invalid")
        expected = {
            "registry_record_id": bridge["registry_record_id"], "adapter_id": bridge["adapter_id"],
            "source_profile": bridge["source_profile"], "platform_scope": bridge["platform"],
            "content_fingerprint": _digest(text), "payload_sha256": bridge["payload_sha256"],
            "surface_sha256": _digest(text[start:end]), "context_observed_at": source_candidate["observed_at"],
            "source_published_at": source_candidate["published_at"],
        }
        if any(candidate[key] != value for key, value in expected.items()):
            raise P0PresentedAContextSubjectV2ParentError("A census/bridge evidence mismatch")
    for sequence, selected_a in enumerate(selected_a_rows, start=1):
        candidate = a_census_by_id.get(selected_a["candidate_id"])
        source = source_by_id.get(candidate["upstream_frame_candidate_id"] if candidate else None)
        bridge = bridge_by_id.get(candidate["upstream_frame_candidate_id"] if candidate else None)
        source_candidate = source_census_by_id.get(candidate["upstream_frame_candidate_id"] if candidate else None)
        if candidate is None or source is None or bridge is None or source_candidate is None or selected_a["input_sequence"] != sequence:
            raise P0PresentedAContextSubjectV2ParentError("A selected mapping mismatch")
        text = base64.b64decode(bridge["payload_base64"].encode("ascii"), validate=True).decode("utf-8")
        start, end = candidate["surface_start"], candidate["surface_end"]
        surface = text[start:end]
        expected_candidate = {
            "registry_record_id": bridge["registry_record_id"], "adapter_id": bridge["adapter_id"],
            "source_profile": bridge["source_profile"], "platform_scope": bridge["platform"],
            "content_fingerprint": _digest(text), "payload_sha256": bridge["payload_sha256"],
            "surface_sha256": _digest(surface),
            "context_observed_at": source_candidate["observed_at"], "source_published_at": source_candidate["published_at"],
        }
        if any(candidate[key] != value for key, value in expected_candidate.items()):
            raise P0PresentedAContextSubjectV2ParentError("A candidate/evidence mismatch")
        source_sha, a_sha = _digest(source), _digest(selected_a)
        evidence = _digest({"source_selected_input_sha256": source_sha, "bridge_row_sha256": bridge["bridge_row_sha256"],
                            "a_selected_context_sha256": a_sha, "a_context_unit_sha256": candidate["context_unit_sha256"],
                            "payload_sha256": bridge["payload_sha256"],
                            "community_scope_commitment_sha256": candidate["community_scope_commitment_sha256"],
                            "capture_receipt_sha256": candidate["capture_receipt_sha256"],
                            "source_claim_set_sha256": candidate["source_claim_set_sha256"]})
        subject_sha = _digest({"domain": SUBJECT_DOMAIN, "lineage_raw_sha256": lineage,
                               "source_selected_input_sha256": source_sha, "a_selected_context_sha256": a_sha,
                               "evidence_unit_sha256": evidence})
        material = {
            "schema_version": SUBJECT_SCHEMA, "record_origin": ORIGIN,
            "subject_id": "P0:A:SUBJECT:V2:" + subject_sha, "input_sequence": sequence,
            "source_input_sequence": source["input_sequence"], "source_frame_candidate_id": source["candidate_id"],
            "source_selected_input_sha256": source_sha, "source_lineage_unit_sha256": source["lineage_unit_sha256"],
            "a_frame_candidate_id": selected_a["candidate_id"], "a_context_unit_sha256": selected_a["context_unit_sha256"],
            "a_selected_context_sha256": a_sha, "source_profile": bridge["source_profile"],
            "platform_scope": bridge["platform"], "registry_record_id": bridge["registry_record_id"],
            "registry_record_commitment_sha256": bridge["registry_record_commitment_sha256"],
            "bridge_row_sha256": bridge["bridge_row_sha256"], "payload_bytes": bridge["payload_bytes"],
            "community_scope_commitment_sha256": candidate["community_scope_commitment_sha256"],
            "capture_receipt_sha256": candidate["capture_receipt_sha256"],
            "source_claim_set_sha256": candidate["source_claim_set_sha256"],
            "payload_sha256": bridge["payload_sha256"], "surface_span_unit": "UNICODE_CODEPOINT",
            "surface_start": start, "surface_end": end, "surface_sha256": _digest(surface),
            "surface_text_sha256": _digest(surface),
            "evidence_disposition": "UNRESOLVED_PREANNOTATION_EVIDENCE" if bridge["source_profile"] == "GENERIC_FALLBACK" else "PRESENTED_CONTEXT_UNJUDGED",
            "lineage_raw_sha256": lineage, "evidence_unit_sha256": evidence,
            "annotation_subject_sha256": subject_sha,
        }
        subjects.append({**material, "row_sha256": _digest(material)})
    if len(subjects) != 20 or len({row["subject_id"] for row in subjects}) != 20:
        raise P0PresentedAContextSubjectV2ParentError("subject count/uniqueness mismatch")
    state = {"source_plan": source_plan, "source_frame": source_frame_value, "bridge": bridge_rows,
             "a_frame": a_frame_value, "a_plan": a_plan}
    return subjects, state


def _validate_subject_precommit_against_raw_inputs(*, subject_rows_raw: bytes,
                                                  expected_subject_rows_raw_sha256: str,
                                                  precommit_raw: bytes,
                                                  expected_precommit_raw_sha256: str,
                                                  **raws: bytes) -> dict[str, Any]:
    if (type(subject_rows_raw) is not bytes or type(precommit_raw) is not bytes
            or len(subject_rows_raw) > MAX_OUTPUT_BYTES or len(precommit_raw) > MAX_OUTPUT_BYTES):
        raise P0PresentedAContextSubjectV2ParentError("parent output input exceeds 1 MiB cap")
    if (type(expected_subject_rows_raw_sha256) is not str or _SHA.fullmatch(expected_subject_rows_raw_sha256) is None
            or expected_subject_rows_raw_sha256 != _raw(subject_rows_raw)):
        raise P0PresentedAContextSubjectV2ParentError("caller-pinned subjects raw SHA mismatch")
    if (type(expected_precommit_raw_sha256) is not str or _SHA.fullmatch(expected_precommit_raw_sha256) is None
            or expected_precommit_raw_sha256 != _raw(precommit_raw)):
        raise P0PresentedAContextSubjectV2ParentError("caller-pinned precommit raw SHA mismatch")
    expected_subjects, state = _derive_subjects(raws)
    subjects = _rows(subject_rows_raw, "subjects")
    for row in subjects:
        _strict(row, _SUBJECT_FIELDS, "subject")
        if FORBIDDEN.intersection(row):
            raise P0PresentedAContextSubjectV2ParentError("label/reviewer field forbidden")
        _self(row, "row_sha256", "subject")
        for field in ("input_sequence", "source_input_sequence", "payload_bytes", "surface_start", "surface_end"):
            if type(row[field]) is not int:
                raise P0PresentedAContextSubjectV2ParentError("subject integer type mismatch")
        for field in ("subject_id", "source_frame_candidate_id", "a_frame_candidate_id", "registry_record_id"):
            _id_value(row[field], f"subject {field}")
        for field in (key for key in row if key.endswith("_sha256")):
            if field != "lineage_raw_sha256":
                _sha_value(row[field], f"subject {field}")
        if type(row["lineage_raw_sha256"]) is not dict or set(row["lineage_raw_sha256"]) != set(LINEAGE_KEYS):
            raise P0PresentedAContextSubjectV2ParentError("subject lineage hash inventory mismatch")
        for value in row["lineage_raw_sha256"].values():
            _sha_value(value, "subject lineage raw SHA")
        if row["surface_span_unit"] != "UNICODE_CODEPOINT":
            raise P0PresentedAContextSubjectV2ParentError("subject span unit mismatch")
    if subjects != expected_subjects:
        raise P0PresentedAContextSubjectV2ParentError("subject independent replay mismatch")
    row = _strict(_obj(precommit_raw, "precommit"), _PRECOMMIT_FIELDS, "precommit")
    if row["schema_version"] != PRECOMMIT_SCHEMA or row["record_origin"] != ORIGIN:
        raise P0PresentedAContextSubjectV2ParentError("precommit schema/origin mismatch")
    if type(row["precommit_id"]) is not str or _ID.fullmatch(row["precommit_id"]) is None:
        raise P0PresentedAContextSubjectV2ParentError("precommit id invalid")
    for field in (key for key in row if key.endswith("_sha256")):
        if field != "lineage_raw_sha256":
            _sha_value(row[field], f"precommit {field}")
    if type(row["lineage_raw_sha256"]) is not dict or set(row["lineage_raw_sha256"]) != set(LINEAGE_KEYS):
        raise P0PresentedAContextSubjectV2ParentError("precommit lineage hash inventory mismatch")
    _self(row, "artifact_sha256", "precommit")
    for field in FALSE_FIELDS:
        if row[field] is not False:
            raise P0PresentedAContextSubjectV2ParentError("precommit false-boundary mismatch")
    if row["frame_domains_separated"] is not True:
        raise P0PresentedAContextSubjectV2ParentError("frame separation flag mismatch")
    for field in ("subject_count", "v2_annotation_event_count", "actual_a_context_review_count", "actual_a_context_credit_count"):
        if type(row[field]) is not int:
            raise P0PresentedAContextSubjectV2ParentError("precommit count type mismatch")
    if type(row["source_profile_counts"]) is not dict or set(row["source_profile_counts"]) != set(PROFILES):
        raise P0PresentedAContextSubjectV2ParentError("profile count fields mismatch")
    if any(type(value) is not int for value in row["source_profile_counts"].values()):
        raise P0PresentedAContextSubjectV2ParentError("profile counts must be exact int")
    counts = Counter(item["source_profile"] for item in subjects)
    expected = {
        "lineage_raw_sha256": _lineage(raws), "source_sampling_frame_sha256": state["source_frame"]["artifact_sha256"],
        "source_sampling_plan_artifact_sha256": state["source_plan"]["artifact_sha256"],
        "source_selected_input_set_sha256": state["source_plan"]["selected_input_set_sha256"],
        "bridge_inventory_sha256": _digest(state["bridge"]), "a_context_sampling_frame_sha256": state["a_frame"]["artifact_sha256"],
        "a_sampling_plan_artifact_sha256": state["a_plan"]["artifact_sha256"],
        "a_selected_context_set_sha256": state["a_plan"]["selected_context_set_sha256"],
        "frame_domains_separated": True, "subject_rows_raw_sha256": _raw(subject_rows_raw), "subject_count": 20,
        "source_profile_counts": {profile: counts[profile] for profile in PROFILES}, "subject_set_sha256": _digest(subjects),
        "v2_annotation_event_count": 0, "actual_a_context_review_count": 0, "actual_a_context_credit_count": 0,
        "statistical_denominator_contribution": "NONE", "metric_status": METRIC_STATUS,
        **{field: False for field in FALSE_FIELDS}, "operational_effect": OPERATIONAL_EFFECT, "gate_status": GATE_STATUS,
    }
    if any(row[field] != value for field, value in expected.items()):
        raise P0PresentedAContextSubjectV2ParentError("precommit projection mismatch")
    if _precommit_time(row["precommitted_at"]) <= _a_time(state["a_plan"]["selection_sealed_at"]):
        raise P0PresentedAContextSubjectV2ParentError("precommit chronology mismatch")
    receipt = {
        "schema_version": "p0_presented_a_context_annotation_subject_v2_parent_receipt_v1",
        "expected_component_manifest_sha256": EXPECTED_COMPONENT_MANIFEST_SHA256,
        "component_manifest_parity_verified": True,
        "source_parent_full_frame_replay_verified": False, "a_parent_full_frame_replay_verified": False,
        "upstream_raw_chain_structural_replay_verified": True,
        "source_deterministic_selection_partition_replayed": True,
        "a_deterministic_selection_partition_replayed": True,
        "bridge40_selected40_replayed": True, "subject20_selected20_replayed": True,
        "input_raw_artifact_count": 11, "output_raw_artifact_count": 2,
        "total_bound_raw_artifact_count": 13, "v2_annotation_event_count": 0,
        "actual_a_context_review_count": 0, "actual_a_context_credit_count": 0,
        "producer_code_imported": False, "actual_authority_granted": False,
        "production_approval": False, "full_scan_approval": False, "p0_phase_exit": False,
        "gate_status": PARENT_GATE_STATUS, "operational_effect": OPERATIONAL_EFFECT,
    }
    return {**receipt, "receipt_sha256": _digest(receipt)}


EXPECTED_COMPONENT_MANIFEST_SHA256 = _digest(EXPECTED_COMPONENT_MANIFEST)


def validate_subject_precommit_against_raw_inputs(**kwargs: Any) -> dict[str, Any]:
    """Public fail-closed wrapper: malformed nested input never leaks builtin errors."""
    try:
        return _validate_subject_precommit_against_raw_inputs(**kwargs)
    except P0PresentedAContextSubjectV2ParentError:
        raise
    except (KeyError, TypeError, AttributeError, IndexError, UnicodeEncodeError,
            UnicodeDecodeError, ValueError, ArithmeticError, RecursionError) as exc:
        raise P0PresentedAContextSubjectV2ParentError("malformed parent input") from exc


__all__ = ["EXPECTED_COMPONENT_MANIFEST", "EXPECTED_COMPONENT_MANIFEST_SHA256",
           "P0PresentedAContextSubjectV2ParentError", "validate_subject_precommit_against_raw_inputs"]
