"""A-event V2 target precommit의 producer-free composed parent 검증기.

검증된 subject V2 parent를 유일한 predecessor dependency로 직접 실행하고,
현재 target 및 target-precommit projection만 producer와 독립된 literal로 재생한다.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
import re
from typing import Any, Mapping, Sequence

from llm_batch.grounding import p0_presented_a_context_annotation_subject_v2_precommit_parent_validator as subject_parent


TARGET_SCHEMA = "p0_presented_a_context_annotation_event_v2_target_row_v1"
PRECOMMIT_SCHEMA = "p0_presented_a_context_annotation_event_v2_target_precommit_v1"
SUBJECT_SCHEMA = "p0_presented_a_context_annotation_subject_v2_prelabel_row_v1"
SUBJECT_PRECOMMIT_SCHEMA = "p0_presented_a_context_annotation_subject_v2_precommit_v1"
TARGET_DOMAIN = "P0_PRESENTED_A_CONTEXT_ANNOTATION_EVENT_V2_TARGET_V1"
JOURNAL_GENESIS_DOMAIN = "P0_PRESENTED_A_CONTEXT_ANNOTATION_EVENT_V2_JOURNAL_GENESIS_V1"
TARGET_PRECOMMIT_ID_DOMAIN = "P0_PRESENTED_A_CONTEXT_ANNOTATION_EVENT_V2_TARGET_PRECOMMIT_ID_V1"
TARGET_ID_PREFIX = "P0:A:ANNOTATION:TARGET:V2:"
TARGET_PRECOMMIT_ID_PREFIX = "P0:A:ANNOTATION:TARGET:PRECOMMIT:V2:"
ORIGIN = "ACTUAL_SCHEMA_CONTRACT_EXAMPLE_ONLY"
OPERATIONAL_EFFECT = "NONE_SHADOW_ONLY"
GATE_STATUS = "A_CONTEXT_EVENT_V2_TARGETS_PRECOMMITTED_NO_ASSIGNMENT_NO_RESULT_ALL_AUTHORITY_NO_GO"
PARENT_GATE_STATUS = "A_CONTEXT_EVENT_V2_TARGET_PRECOMMIT_COMPOSED_PARENT_PASS_ALL_AUTHORITY_NO_GO"
SUBJECT_PARENT_GATE_STATUS = "A_CONTEXT_V2_PRECOMMIT_PARENT_REPLAY_PASS_ALL_AUTHORITY_NO_GO"
METRIC_STATUS = "METRICS_NOT_ESTIMABLE_TARGET_OPPORTUNITIES_ONLY"
EXPECTED_TARGET_COUNT = 20
MAX_OUTPUT_BYTES = 1_000_000
UPSTREAM_RAW_KEYS = (
    "source_scope", "source_census", "source_frame", "source_seed", "source_plan",
    "bridge_inventory", "a_scope", "a_census", "a_frame", "a_seed", "a_plan",
)
PREDECESSOR_PARENT_MODULE = (
    "llm_batch.grounding."
    "p0_presented_a_context_annotation_subject_v2_precommit_parent_validator"
)
PREDECESSOR_COMPONENT_MANIFEST_SHA256 = "4f8e70e08f153886576fad2dbaa2a35e298a1e7438e58a047bdf00105a8f01b6"
SOURCE_PROFILES = ("OFFICIAL_STRUCTURED", "COMMUNITY_STRUCTURED", "MEDIA_OCR", "GENERIC_FALLBACK")
RESPONSE_SCHEMA = {
    "schema_version": "p0_presented_a_context_annotation_event_v2_response_taxonomy_v1",
    "initial_state": "NO_EVENT_RECORDED",
    "initial_state_payload_rule": "NO_RESULT_OBJECT_EXISTS",
    "per_target_values_assigned": False,
    "required_result_fields": [
        "annotation_status", "decision_kind", "decision_work_id",
        "decision_nil_reason", "status_reason_code",
    ],
    "annotation_status_values": ["JUDGED", "UNJUDGED", "UNAVAILABLE"],
    "decision_kind_values": ["WORK_ID", "NIL", "UNRESOLVED"],
    "status_decision_matrix": {
        "JUDGED": ["WORK_ID", "NIL"],
        "UNJUDGED": ["UNRESOLVED"],
        "UNAVAILABLE": ["UNRESOLVED"],
    },
    "field_rules": {
        "decision_work_id": "REQUIRED_NONEMPTY_ID_IFF_DECISION_KIND_WORK_ID_ELSE_NULL",
        "decision_nil_reason": "REQUIRED_IFF_DECISION_KIND_NIL_ELSE_NULL",
        "status_reason_code": "REQUIRED_EXACTLY_ONE_FROM_MATCHING_STATUS_FAMILY",
    },
    "nil_reason_values": [
        "NIL_NON_WORK", "NIL_OUT_OF_UNIVERSE", "NIL_NO_VALID_CANDIDATE",
    ],
    "status_reason_code_values": {
        "JUDGED": ["annotation_human_review_completed"],
        "UNJUDGED": [
            "annotation_alias_sense_unresolved",
            "annotation_multiwork_primary_unresolved",
            "annotation_conflicting_evidence",
            "annotation_insufficient_context",
        ],
        "UNAVAILABLE": [
            "evidence_unavailable", "evidence_access_restricted", "evidence_deleted",
        ],
    },
    "work_id_rule": "MUST_BIND_FUTURE_SEALED_CANDIDATE_AND_EVIDENCE_AT_EVENT_CUTOFF",
    "nil_rule": "JUDGED_SEMANTIC_NEGATIVE_REQUIRES_COMPLETE_FUTURE_CANDIDATE_ENUMERATION",
    "unresolved_rule": "NONJUDGED_MISSINGNESS_OR_AMBIGUITY_NOT_NIL_NOT_NEGATIVE_NOT_GOLD",
    "unavailable_rule": "EVIDENCE_ACCESS_FAILURE_NOT_NIL_NOT_NEGATIVE_NOT_GOLD",
    "unknown_result_fields_policy": "REJECT",
}
FALSE_FIELDS = (
    "target_wiring_applied", "journal_wiring_applied", "response_schema_wiring_verified",
    "annotation_started", "responses_observed", "labels_observed",
    "semantic_truth_fields_used", "actual_a_context_evidence_verified",
    "actual_authority_granted", "inferential_metrics_allowed",
    "complete_case_metrics_allowed", "runtime_noninterference_verified",
    "write_authority_verified", "production_approval", "full_scan_approval",
    "p0_phase_exit", "action_applied",
)
ZERO_COUNT_FIELDS = (
    "actual_a_context_review_count", "review_assignment_count", "journal_head_count",
    "annotation_event_count", "annotation_result_count", "actual_a_context_credit_count",
)
FORBIDDEN_PER_TARGET_FIELD_FRAGMENTS = (
    "label", "reviewer", "result", "event", "response_schema", "taxonomy",
)
_SHA = re.compile(r"^[0-9a-f]{64}$")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")
_RFC3339 = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(?:\.[0-9]+)?(?:Z|[+-][0-9]{2}:[0-9]{2})$"
)
MAX_TARGET_ROW_BYTES = 65_536
EFFECTIVE_RAW_CAPS = {
    "source_scope": 1_000_000, "source_census": 64_000_000,
    "source_frame": 1_000_000, "source_seed": 64_000,
    "source_plan": 64_000_000, "bridge_inventory": 16_777_216,
    "a_scope": 1_000_000, "a_census": 64_000_000,
    "a_frame": 1_000_000, "a_seed": 64_000, "a_plan": 64_000_000,
    "subject_rows": 1_000_000, "subject_precommit": 1_000_000,
    "target_rows": 1_000_000, "target_precommit": 1_000_000,
}
_SUBJECT_FIELDS = frozenset({
    "schema_version", "record_origin", "subject_id", "input_sequence",
    "source_input_sequence", "source_frame_candidate_id", "source_selected_input_sha256",
    "source_lineage_unit_sha256", "a_frame_candidate_id", "a_context_unit_sha256",
    "a_selected_context_sha256", "source_profile", "platform_scope",
    "registry_record_id", "registry_record_commitment_sha256", "bridge_row_sha256",
    "community_scope_commitment_sha256", "capture_receipt_sha256", "source_claim_set_sha256",
    "payload_bytes", "payload_sha256", "surface_span_unit", "surface_start", "surface_end",
    "surface_sha256", "surface_text_sha256", "evidence_disposition",
    "lineage_raw_sha256", "evidence_unit_sha256", "annotation_subject_sha256", "row_sha256",
})
_SUBJECT_PRECOMMIT_FIELDS = frozenset({
    "schema_version", "record_origin", "precommit_id", "lineage_raw_sha256",
    "source_sampling_frame_sha256", "source_sampling_plan_artifact_sha256",
    "source_selected_input_set_sha256", "bridge_inventory_sha256",
    "a_context_sampling_frame_sha256", "a_sampling_plan_artifact_sha256",
    "a_selected_context_set_sha256", "frame_domains_separated",
    "subject_rows_raw_sha256", "subject_count", "source_profile_counts",
    "subject_set_sha256", "precommitted_at", "v2_annotation_event_count",
    "actual_a_context_review_count", "actual_a_context_credit_count",
    "statistical_denominator_contribution", "metric_status", "labels_observed",
    "semantic_truth_fields_used", "annotation_started", "actual_a_context_evidence_verified",
    "actual_authority_granted", "inferential_metrics_allowed", "complete_case_metrics_allowed",
    "production_approval", "full_scan_approval", "p0_phase_exit",
    "runtime_noninterference_verified", "write_authority_verified", "action_applied",
    "operational_effect", "gate_status", "artifact_sha256",
})
_TARGET_FIELDS = frozenset({
    "schema_version", "record_origin", "target_id", "target_sequence",
    "target_record_type", "opportunity_kind", "initial_state",
    "subject_id", "subject_input_sequence", "annotation_subject_sha256",
    "subject_row_sha256", "subject_rows_raw_sha256", "subject_precommit_raw_sha256",
    "subject_precommit_artifact_sha256",
    "target_commitment_sha256", "journal_genesis_sha256", "row_sha256",
})
_PRECOMMIT_FIELDS = frozenset({
    "schema_version", "record_origin", "target_precommit_id",
    "subject_rows_raw_sha256", "subject_precommit_raw_sha256",
    "subject_precommit_artifact_sha256", "target_rows_raw_sha256",
    "bound_input_raw_sha256", "target_count", "annotation_opportunity_count",
    "planned_primary_opportunity_count", "unstarted_target_count", "source_profile_counts",
    "target_set_sha256",
    "journal_genesis_set_sha256", "response_schema_commitment_sha256",
    "precommitted_at", *ZERO_COUNT_FIELDS, "statistical_denominator_contribution",
    "metric_status", "iid_independence_assumed", "future_inferential_cluster_unit",
    *FALSE_FIELDS,
    "operational_effect", "gate_status", "artifact_sha256",
})
_SUBJECT_RECEIPT_FIELDS = frozenset({
    "schema_version", "expected_component_manifest_sha256",
    "component_manifest_parity_verified", "source_parent_full_frame_replay_verified",
    "a_parent_full_frame_replay_verified", "upstream_raw_chain_structural_replay_verified",
    "source_deterministic_selection_partition_replayed",
    "a_deterministic_selection_partition_replayed", "bridge40_selected40_replayed",
    "subject20_selected20_replayed", "input_raw_artifact_count",
    "output_raw_artifact_count", "total_bound_raw_artifact_count",
    "v2_annotation_event_count", "actual_a_context_review_count",
    "actual_a_context_credit_count", "producer_code_imported", "actual_authority_granted",
    "production_approval", "full_scan_approval", "p0_phase_exit", "gate_status",
    "operational_effect", "receipt_sha256",
})


class P0PresentedAContextEventV2TargetParentError(ValueError):
    pass


def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (RecursionError, UnicodeEncodeError, TypeError, ValueError) as exc:
        raise P0PresentedAContextEventV2TargetParentError("value is not canonical JSON") from exc


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


RESPONSE_SCHEMA_COMMITMENT_SHA256 = _digest(RESPONSE_SCHEMA)


def _raw(raw: bytes) -> str:
    if type(raw) is not bytes:
        raise P0PresentedAContextEventV2TargetParentError("raw input must be exact bytes")
    return hashlib.sha256(raw).hexdigest()


def _file(value: Any) -> bytes:
    return _canonical(value) + b"\n"


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise P0PresentedAContextEventV2TargetParentError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _bad_constant(token: str) -> None:
    raise P0PresentedAContextEventV2TargetParentError(f"non-finite token: {token}")


def _obj(raw: bytes, label: str) -> dict[str, Any]:
    if (type(raw) is not bytes or not raw or len(raw) > MAX_OUTPUT_BYTES
            or b"\r" in raw or not raw.endswith(b"\n")):
        raise P0PresentedAContextEventV2TargetParentError(f"{label} framing invalid")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_bad_constant)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValueError) as exc:
        raise P0PresentedAContextEventV2TargetParentError(f"{label} parse failed") from exc
    if type(value) is not dict or raw != _file(value):
        raise P0PresentedAContextEventV2TargetParentError(f"{label} noncanonical")
    return value


def _rows(raw: bytes, label: str, *, max_line_bytes: int | None = None) -> list[dict[str, Any]]:
    if (type(raw) is not bytes or not raw or len(raw) > MAX_OUTPUT_BYTES or b"\r" in raw
            or not raw.endswith(b"\n") or raw.endswith(b"\n\n")):
        raise P0PresentedAContextEventV2TargetParentError(f"{label} framing invalid")
    lines = raw[:-1].split(b"\n")
    if max_line_bytes is not None and any(len(line) + 1 > max_line_bytes for line in lines):
        raise P0PresentedAContextEventV2TargetParentError(f"{label} row exceeds line cap")
    rows = [_obj(line + b"\n", f"{label} row") for line in lines]
    if raw != b"".join(_file(row) for row in rows):
        raise P0PresentedAContextEventV2TargetParentError(f"{label} noncanonical")
    return rows


def _strict(value: Any, fields: frozenset[str], label: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != fields:
        raise P0PresentedAContextEventV2TargetParentError(f"{label} exact fields mismatch")
    return dict(value)


def _sha(value: Any, label: str) -> str:
    if type(value) is not str or _SHA.fullmatch(value) is None:
        raise P0PresentedAContextEventV2TargetParentError(f"{label} must be sha256")
    return value


def _id(value: Any, label: str) -> str:
    if type(value) is not str or _ID.fullmatch(value) is None:
        raise P0PresentedAContextEventV2TargetParentError(f"{label} must be safe id")
    return value


def _time(value: Any, label: str) -> datetime:
    if type(value) is not str or _RFC3339.fullmatch(value) is None:
        raise P0PresentedAContextEventV2TargetParentError(f"{label} must be strict RFC3339")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise P0PresentedAContextEventV2TargetParentError(f"{label} must be RFC3339") from exc
    if result.tzinfo is None:
        raise P0PresentedAContextEventV2TargetParentError(f"{label} needs timezone")
    return result


def _self(row: Mapping[str, Any], field: str, label: str) -> None:
    _sha(row[field], f"{label}.{field}")
    material = dict(row)
    submitted = material.pop(field)
    if submitted != _digest(material):
        raise P0PresentedAContextEventV2TargetParentError(f"{label} self hash mismatch")


def _pin(raw: bytes, submitted: str, label: str) -> None:
    if _sha(submitted, label) != _raw(raw):
        raise P0PresentedAContextEventV2TargetParentError(f"caller-pinned {label} mismatch")


def _validate_predecessor_receipt(receipt: Any) -> dict[str, Any]:
    row = _strict(receipt, _SUBJECT_RECEIPT_FIELDS, "predecessor subject parent receipt")
    _self(row, "receipt_sha256", "predecessor subject parent receipt")
    if row["schema_version"] != "p0_presented_a_context_annotation_subject_v2_parent_receipt_v1":
        raise P0PresentedAContextEventV2TargetParentError("predecessor receipt schema mismatch")
    if (row["expected_component_manifest_sha256"] != PREDECESSOR_COMPONENT_MANIFEST_SHA256
            or row["component_manifest_parity_verified"] is not True):
        raise P0PresentedAContextEventV2TargetParentError("predecessor manifest pin mismatch")
    expected_true = (
        "upstream_raw_chain_structural_replay_verified",
        "source_deterministic_selection_partition_replayed",
        "a_deterministic_selection_partition_replayed", "bridge40_selected40_replayed",
        "subject20_selected20_replayed",
    )
    if any(row[field] is not True for field in expected_true):
        raise P0PresentedAContextEventV2TargetParentError("predecessor replay claim mismatch")
    expected_false = (
        "source_parent_full_frame_replay_verified", "a_parent_full_frame_replay_verified",
        "producer_code_imported", "actual_authority_granted", "production_approval",
        "full_scan_approval", "p0_phase_exit",
    )
    if any(row[field] is not False for field in expected_false):
        raise P0PresentedAContextEventV2TargetParentError("predecessor authority/implementation claim mismatch")
    expected_counts = {
        "input_raw_artifact_count": 11, "output_raw_artifact_count": 2,
        "total_bound_raw_artifact_count": 13, "v2_annotation_event_count": 0,
        "actual_a_context_review_count": 0, "actual_a_context_credit_count": 0,
    }
    if any(type(row[field]) is not int or row[field] != value for field, value in expected_counts.items()):
        raise P0PresentedAContextEventV2TargetParentError("predecessor receipt count mismatch")
    if row["gate_status"] != SUBJECT_PARENT_GATE_STATUS or row["operational_effect"] != OPERATIONAL_EFFECT:
        raise P0PresentedAContextEventV2TargetParentError("predecessor receipt gate mismatch")
    return row


def _subjects(raw: bytes) -> list[dict[str, Any]]:
    rows = _rows(raw, "subject rows")
    for sequence, row in enumerate(rows, start=1):
        _strict(row, _SUBJECT_FIELDS, "subject row")
        if row["schema_version"] != SUBJECT_SCHEMA or row["record_origin"] != ORIGIN:
            raise P0PresentedAContextEventV2TargetParentError("subject schema/origin mismatch")
        if type(row["input_sequence"]) is not int or row["input_sequence"] != sequence:
            raise P0PresentedAContextEventV2TargetParentError("subject sequence mismatch")
        _id(row["subject_id"], "subject_id")
        _sha(row["annotation_subject_sha256"], "annotation_subject_sha256")
        _self(row, "row_sha256", "subject row")
    if len(rows) != EXPECTED_TARGET_COUNT or len({row["subject_id"] for row in rows}) != EXPECTED_TARGET_COUNT:
        raise P0PresentedAContextEventV2TargetParentError("subject inventory mismatch")
    return rows


def _subject_precommit(raw: bytes, subject_rows_raw: bytes) -> dict[str, Any]:
    row = _strict(_obj(raw, "subject precommit"), _SUBJECT_PRECOMMIT_FIELDS, "subject precommit")
    if row["schema_version"] != SUBJECT_PRECOMMIT_SCHEMA or row["record_origin"] != ORIGIN:
        raise P0PresentedAContextEventV2TargetParentError("subject precommit schema/origin mismatch")
    _self(row, "artifact_sha256", "subject precommit")
    if row["subject_rows_raw_sha256"] != _raw(subject_rows_raw):
        raise P0PresentedAContextEventV2TargetParentError("subject precommit/raw binding mismatch")
    return row


def _expected_targets(subjects: Sequence[Mapping[str, Any]], subject_precommit: Mapping[str, Any],
                      subject_rows_raw: bytes, subject_precommit_raw: bytes) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for sequence, subject in enumerate(subjects, start=1):
        binding = {
            "domain": TARGET_DOMAIN, "target_sequence": sequence,
            "subject_id": subject["subject_id"],
            "annotation_subject_sha256": subject["annotation_subject_sha256"],
            "subject_row_sha256": subject["row_sha256"],
            "subject_rows_raw_sha256": _raw(subject_rows_raw),
            "subject_precommit_raw_sha256": _raw(subject_precommit_raw),
            "subject_precommit_artifact_sha256": subject_precommit["artifact_sha256"],
        }
        target_commitment = _digest(binding)
        target_id = TARGET_ID_PREFIX + target_commitment
        material = {
            "schema_version": TARGET_SCHEMA, "record_origin": ORIGIN,
            "target_id": target_id, "target_sequence": sequence,
            "target_record_type": "A_CONTEXT_ANNOTATION_SUBJECT_V2",
            "opportunity_kind": "PRIMARY_REVIEW", "initial_state": "NO_EVENT_RECORDED",
            "subject_id": subject["subject_id"], "subject_input_sequence": subject["input_sequence"],
            "annotation_subject_sha256": subject["annotation_subject_sha256"],
            "subject_row_sha256": subject["row_sha256"],
            "subject_rows_raw_sha256": _raw(subject_rows_raw),
            "subject_precommit_raw_sha256": _raw(subject_precommit_raw),
            "subject_precommit_artifact_sha256": subject_precommit["artifact_sha256"],
            "target_commitment_sha256": target_commitment,
            "journal_genesis_sha256": _digest({
                "domain": JOURNAL_GENESIS_DOMAIN, "target_id": target_id,
                "target_commitment_sha256": target_commitment,
                "subject_precommit_artifact_sha256": subject_precommit["artifact_sha256"],
            }),
        }
        result.append({**material, "row_sha256": _digest(material)})
    return result


def _target_rows(raw: bytes, subjects: Sequence[Mapping[str, Any]],
                 subject_precommit: Mapping[str, Any], subject_rows_raw: bytes,
                 subject_precommit_raw: bytes) -> list[dict[str, Any]]:
    rows = _rows(raw, "target rows", max_line_bytes=MAX_TARGET_ROW_BYTES)
    for row in rows:
        _strict(row, _TARGET_FIELDS, "target row")
        if row["schema_version"] != TARGET_SCHEMA or row["record_origin"] != ORIGIN:
            raise P0PresentedAContextEventV2TargetParentError("target schema/origin mismatch")
        forbidden = {key for key in row if key != "schema_version" and any(
            fragment in key.lower() for fragment in FORBIDDEN_PER_TARGET_FIELD_FRAGMENTS)}
        if forbidden:
            raise P0PresentedAContextEventV2TargetParentError("per-target result/reviewer/event field forbidden")
        for field in ("target_sequence", "subject_input_sequence"):
            if type(row[field]) is not int:
                raise P0PresentedAContextEventV2TargetParentError("target count must be exact integer")
        _id(row["target_id"], "target_id")
        _id(row["subject_id"], "subject_id")
        for field in (key for key in row if key.endswith("_sha256")):
            _sha(row[field], field)
        _self(row, "row_sha256", "target row")
    expected = _expected_targets(subjects, subject_precommit, subject_rows_raw, subject_precommit_raw)
    if rows != expected:
        raise P0PresentedAContextEventV2TargetParentError("current target projection independent replay mismatch")
    return rows


def _target_precommit(raw: bytes, *, target_rows_raw: bytes,
                      subject_rows_raw: bytes, subject_precommit_raw: bytes,
                      targets: Sequence[Mapping[str, Any]], subjects: Sequence[Mapping[str, Any]],
                      subject_precommit: Mapping[str, Any], raws: Mapping[str, bytes]) -> dict[str, Any]:
    row = _strict(_obj(raw, "target precommit"), _PRECOMMIT_FIELDS, "target precommit")
    if row["schema_version"] != PRECOMMIT_SCHEMA or row["record_origin"] != ORIGIN:
        raise P0PresentedAContextEventV2TargetParentError("target precommit schema/origin mismatch")
    _id(row["target_precommit_id"], "target_precommit_id")
    for field in (key for key in row if key.endswith("_sha256") and key != "bound_input_raw_sha256"):
        _sha(row[field], field)
    _self(row, "artifact_sha256", "target precommit")
    for field in FALSE_FIELDS:
        if row[field] is not False:
            raise P0PresentedAContextEventV2TargetParentError("target authority/wiring/metric flag mismatch")
    expected_counts = {"target_count": 20, "annotation_opportunity_count": 20,
                       "planned_primary_opportunity_count": 20, "unstarted_target_count": 20,
                       **{field: 0 for field in ZERO_COUNT_FIELDS}}
    if any(type(row[field]) is not int or row[field] != value for field, value in expected_counts.items()):
        raise P0PresentedAContextEventV2TargetParentError("target precommit count/bool confusion")
    bound = {key: _raw(raws[key]) for key in UPSTREAM_RAW_KEYS}
    bound.update({"subject_rows": _raw(subject_rows_raw),
                  "subject_precommit": _raw(subject_precommit_raw)})
    if type(row["bound_input_raw_sha256"]) is not dict or set(row["bound_input_raw_sha256"]) != set(bound):
        raise P0PresentedAContextEventV2TargetParentError("bound input raw SHA exact inventory mismatch")
    for key, value in row["bound_input_raw_sha256"].items():
        _sha(value, f"bound_input_raw_sha256.{key}")
    counts = {profile: sum(item["source_profile"] == profile for item in subjects)
              for profile in SOURCE_PROFILES}
    if type(row["source_profile_counts"]) is not dict or set(row["source_profile_counts"]) != set(SOURCE_PROFILES):
        raise P0PresentedAContextEventV2TargetParentError("source profile count inventory mismatch")
    if any(type(value) is not int for value in row["source_profile_counts"].values()):
        raise P0PresentedAContextEventV2TargetParentError("source profile count bool confusion")
    target_precommit_id = TARGET_PRECOMMIT_ID_PREFIX + _digest({
        "domain": TARGET_PRECOMMIT_ID_DOMAIN, "bound_input_raw_sha256": bound,
        "target_rows_raw_sha256": _raw(target_rows_raw),
        "response_schema_commitment_sha256": RESPONSE_SCHEMA_COMMITMENT_SHA256,
        "precommitted_at": row["precommitted_at"],
    })
    expected = {
        "target_precommit_id": target_precommit_id,
        "subject_rows_raw_sha256": _raw(subject_rows_raw),
        "subject_precommit_raw_sha256": _raw(subject_precommit_raw),
        "subject_precommit_artifact_sha256": subject_precommit["artifact_sha256"],
        "target_rows_raw_sha256": _raw(target_rows_raw),
        "bound_input_raw_sha256": bound,
        "target_count": 20, "annotation_opportunity_count": 20,
        "planned_primary_opportunity_count": 20, "unstarted_target_count": 20,
        "source_profile_counts": counts,
        "target_set_sha256": _digest(list(targets)),
        "journal_genesis_set_sha256": _digest([item["journal_genesis_sha256"] for item in targets]),
        "response_schema_commitment_sha256": RESPONSE_SCHEMA_COMMITMENT_SHA256,
        **{field: 0 for field in ZERO_COUNT_FIELDS},
        "statistical_denominator_contribution": "NONE", "metric_status": METRIC_STATUS,
        "iid_independence_assumed": False,
        "future_inferential_cluster_unit": "UPSTREAM_SOURCE_FRAME_CANDIDATE_ID",
        **{field: False for field in FALSE_FIELDS},
        "operational_effect": OPERATIONAL_EFFECT, "gate_status": GATE_STATUS,
    }
    if row["iid_independence_assumed"] is not False:
        raise P0PresentedAContextEventV2TargetParentError(
            "target opportunities must not assert iid independence"
        )
    if any(row[field] != value for field, value in expected.items()):
        raise P0PresentedAContextEventV2TargetParentError("current target precommit independent replay mismatch")
    if _time(row["precommitted_at"], "target.precommitted_at") <= _time(subject_precommit["precommitted_at"], "subject.precommitted_at"):
        raise P0PresentedAContextEventV2TargetParentError("subject precommit must strictly precede target precommit")
    return row


EXPECTED_COMPONENT_MANIFEST = {
    "component": "p0_presented_a_context_annotation_event_v2_target_precommit_contract",
    "schemas": [TARGET_SCHEMA, PRECOMMIT_SCHEMA], "input_raw_artifact_count": 13,
    "output_raw_artifact_count": 2, "total_bound_raw_artifact_count": 15,
    "target_count": EXPECTED_TARGET_COUNT, "annotation_opportunity_count": EXPECTED_TARGET_COUNT,
    "max_output_bytes": MAX_OUTPUT_BYTES, "max_target_row_bytes": MAX_TARGET_ROW_BYTES,
    "effective_raw_caps": EFFECTIVE_RAW_CAPS,
    "consumes_packet_v1_labels_or_events": False,
    "per_target_result_values_allowed": False, "authority": "NONE",
    "validation_architecture": "PRODUCER_FREE_COMPOSED_PARENT_DELEGATION",
    "predecessor_parent_module": PREDECESSOR_PARENT_MODULE,
    "predecessor_parent_entrypoint": "validate_subject_precommit_against_raw_inputs",
    "predecessor_parent_receipt_schema": (
        "p0_presented_a_context_annotation_subject_v2_parent_receipt_v1"
    ),
    "predecessor_parent_gate_status": SUBJECT_PARENT_GATE_STATUS,
    "predecessor_subject_component_manifest_sha256": PREDECESSOR_COMPONENT_MANIFEST_SHA256,
    "response_schema_commitment_sha256": RESPONSE_SCHEMA_COMMITMENT_SHA256,
    "iid_independence_assumed": False,
    "future_inferential_cluster_unit": "UPSTREAM_SOURCE_FRAME_CANDIDATE_ID",
}
EXPECTED_COMPONENT_MANIFEST_SHA256 = _digest(EXPECTED_COMPONENT_MANIFEST)


def _validate_target_precommit_against_raw_inputs(*, target_rows_raw: bytes,
                                                  target_precommit_raw: bytes,
                                                  subject_rows_raw: bytes,
                                                  subject_precommit_raw: bytes,
                                                  expected_raw_sha256: Mapping[str, str],
                                                  **raws: bytes) -> dict[str, Any]:
    if set(raws) != set(UPSTREAM_RAW_KEYS):
        raise P0PresentedAContextEventV2TargetParentError("upstream raw inventory mismatch")
    all_raws = {**raws, "subject_rows": subject_rows_raw, "subject_precommit": subject_precommit_raw,
                "target_rows": target_rows_raw, "target_precommit": target_precommit_raw}
    if type(expected_raw_sha256) is not dict or set(expected_raw_sha256) != set(all_raws):
        raise P0PresentedAContextEventV2TargetParentError("caller expected raw SHA exact 15-role inventory mismatch")
    for key, raw in all_raws.items():
        if type(raw) is not bytes or len(raw) > EFFECTIVE_RAW_CAPS[key]:
            raise P0PresentedAContextEventV2TargetParentError(
                f"{key} must be exact bytes within role cap"
            )
        _pin(raw, expected_raw_sha256[key], f"{key} raw SHA")
    try:
        predecessor_receipt = subject_parent.validate_subject_precommit_against_raw_inputs(
            subject_rows_raw=subject_rows_raw,
            expected_subject_rows_raw_sha256=expected_raw_sha256["subject_rows"],
            precommit_raw=subject_precommit_raw,
            expected_precommit_raw_sha256=expected_raw_sha256["subject_precommit"],
            **raws,
        )
    except (subject_parent.P0PresentedAContextSubjectV2ParentError, RuntimeError, TypeError,
            ValueError, KeyError, AttributeError, IndexError, RecursionError) as exc:
        raise P0PresentedAContextEventV2TargetParentError("predecessor subject parent execution failed") from exc
    predecessor_receipt = _validate_predecessor_receipt(predecessor_receipt)
    subjects = _subjects(subject_rows_raw)
    predecessor = _subject_precommit(subject_precommit_raw, subject_rows_raw)
    targets = _target_rows(target_rows_raw, subjects, predecessor, subject_rows_raw, subject_precommit_raw)
    _target_precommit(
        target_precommit_raw, target_rows_raw=target_rows_raw,
        subject_rows_raw=subject_rows_raw, subject_precommit_raw=subject_precommit_raw,
        targets=targets, subjects=subjects, subject_precommit=predecessor, raws=raws,
    )
    generic_ids = {item["subject_id"] for item in subjects if item["source_profile"] == "GENERIC_FALLBACK"}
    target_subject_ids = {item["subject_id"] for item in targets}
    if not generic_ids or not generic_ids <= target_subject_ids:
        raise P0PresentedAContextEventV2TargetParentError("generic fallback subjects must remain target opportunities")
    receipt = {
        "schema_version": "p0_presented_a_context_annotation_event_v2_target_parent_receipt_v1",
        "expected_component_manifest_sha256": EXPECTED_COMPONENT_MANIFEST_SHA256,
        "component_manifest_parity_verified": True,
        "validation_architecture": "PRODUCER_FREE_COMPOSED_PARENT",
        "producer_free_composed_parent_verified": True,
        "predecessor_parent_module": PREDECESSOR_PARENT_MODULE,
        "predecessor_subject_component_manifest_sha256": PREDECESSOR_COMPONENT_MANIFEST_SHA256,
        "predecessor_subject_parent_executed": True,
        "predecessor_subject_parent_receipt_sha256": predecessor_receipt["receipt_sha256"],
        "validated_raw_sha256": dict(expected_raw_sha256),
        "validated_raw_pin_set_sha256": _digest(expected_raw_sha256),
        "predecessor_subject_replay_delegated": True,
        "predecessor_subject_replay_locally_verified": False,
        "predecessor_subject_replay_locally_duplicated": False,
        "current_target_projection_independently_replayed": True,
        "current_precommit_projection_independently_replayed": True,
        "generic_fallback_target_count": len(generic_ids),
        "input_raw_artifact_count": 13, "output_raw_artifact_count": 2,
        "total_bound_raw_artifact_count": 15, "target_count": 20,
        "annotation_opportunity_count": 20, "planned_primary_opportunity_count": 20,
        "unstarted_target_count": 20, **{field: 0 for field in ZERO_COUNT_FIELDS},
        "statistical_denominator_contribution": "NONE", "metric_status": METRIC_STATUS,
        "iid_independence_assumed": False,
        "future_inferential_cluster_unit": "UPSTREAM_SOURCE_FRAME_CANDIDATE_ID",
        "upstream_code_identity_verified": False,
        "same_process_monkeypatch_resistance_verified": False,
        "producer_code_imported": False, "actual_authority_granted": False,
        "target_wiring_applied": False, "journal_wiring_applied": False,
        "response_schema_wiring_verified": False, "inferential_metrics_allowed": False,
        "complete_case_metrics_allowed": False, "production_approval": False,
        "full_scan_approval": False, "p0_phase_exit": False,
        "gate_status": PARENT_GATE_STATUS, "operational_effect": OPERATIONAL_EFFECT,
    }
    return {**receipt, "receipt_sha256": _digest(receipt)}


def validate_target_precommit_against_raw_inputs(**kwargs: Any) -> dict[str, Any]:
    """Public fail-closed wrapper: malformed input과 dependency 실패를 한 오류로 정규화한다."""
    try:
        return _validate_target_precommit_against_raw_inputs(**kwargs)
    except P0PresentedAContextEventV2TargetParentError:
        raise
    except (KeyError, TypeError, AttributeError, IndexError, UnicodeEncodeError,
            UnicodeDecodeError, ValueError, ArithmeticError, RecursionError) as exc:
        raise P0PresentedAContextEventV2TargetParentError("malformed composed-parent input") from exc


__all__ = [
    "EXPECTED_COMPONENT_MANIFEST", "EXPECTED_COMPONENT_MANIFEST_SHA256",
    "P0PresentedAContextEventV2TargetParentError", "PARENT_GATE_STATUS",
    "PREDECESSOR_COMPONENT_MANIFEST_SHA256", "PREDECESSOR_PARENT_MODULE",
    "validate_target_precommit_against_raw_inputs",
]
