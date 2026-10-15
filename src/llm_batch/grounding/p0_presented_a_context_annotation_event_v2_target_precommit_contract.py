"""Presented A-context annotation-event V2의 result-free target precommit 계약.

annotation subject V2의 13개 raw lineage를 검증한 뒤, 판정값ㆍreviewerㆍevent
payload 없이 20개 annotation opportunity target만 결정적으로 고정한다. 결과
taxonomy는 공통 response-schema commitment 한 개로만 precommit에 결박된다.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
import hashlib
import json
import re
from typing import Any, Mapping, Sequence

from llm_batch.grounding import p0_presented_a_context_annotation_subject_v2_precommit_contract as subject_contract


TARGET_SCHEMA = "p0_presented_a_context_annotation_event_v2_target_row_v1"
PRECOMMIT_SCHEMA = "p0_presented_a_context_annotation_event_v2_target_precommit_v1"
TARGET_DOMAIN = "P0_PRESENTED_A_CONTEXT_ANNOTATION_EVENT_V2_TARGET_V1"
JOURNAL_GENESIS_DOMAIN = "P0_PRESENTED_A_CONTEXT_ANNOTATION_EVENT_V2_JOURNAL_GENESIS_V1"
TARGET_PRECOMMIT_ID_DOMAIN = "P0_PRESENTED_A_CONTEXT_ANNOTATION_EVENT_V2_TARGET_PRECOMMIT_ID_V1"
TARGET_ID_PREFIX = "P0:A:ANNOTATION:TARGET:V2:"
TARGET_PRECOMMIT_ID_PREFIX = "P0:A:ANNOTATION:TARGET:PRECOMMIT:V2:"
ORIGIN = "ACTUAL_SCHEMA_CONTRACT_EXAMPLE_ONLY"
OPERATIONAL_EFFECT = "NONE_SHADOW_ONLY"
GATE_STATUS = "A_CONTEXT_EVENT_V2_TARGETS_PRECOMMITTED_NO_ASSIGNMENT_NO_RESULT_ALL_AUTHORITY_NO_GO"
METRIC_STATUS = "METRICS_NOT_ESTIMABLE_TARGET_OPPORTUNITIES_ONLY"
EXPECTED_TARGET_COUNT = 20
MAX_OUTPUT_BYTES = 1_000_000
UPSTREAM_RAW_KEYS = subject_contract.LINEAGE_KEYS
INPUT_RAW_KEYS = (*UPSTREAM_RAW_KEYS, "subject_rows", "subject_precommit")
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
_TARGET_FIELDS = frozenset({
    "schema_version", "record_origin", "target_id", "target_sequence",
    "target_record_type", "opportunity_kind", "initial_state",
    "subject_id", "subject_input_sequence", "annotation_subject_sha256",
    "subject_row_sha256", "subject_rows_raw_sha256", "subject_precommit_raw_sha256",
    "subject_precommit_artifact_sha256",
    "target_commitment_sha256", "journal_genesis_sha256",
    "row_sha256",
})
_PRECOMMIT_FIELDS = frozenset({
    "schema_version", "record_origin", "target_precommit_id",
    "subject_rows_raw_sha256", "subject_precommit_raw_sha256",
    "subject_precommit_artifact_sha256", "target_rows_raw_sha256",
    "bound_input_raw_sha256", "target_count", "annotation_opportunity_count",
    "planned_primary_opportunity_count", "unstarted_target_count", "source_profile_counts",
    "target_set_sha256", "journal_genesis_set_sha256",
    "response_schema_commitment_sha256", "precommitted_at",
    *ZERO_COUNT_FIELDS, "statistical_denominator_contribution", "metric_status",
    "iid_independence_assumed", "future_inferential_cluster_unit",
    *FALSE_FIELDS, "operational_effect", "gate_status", "artifact_sha256",
})


class P0PresentedAContextEventV2TargetPrecommitError(ValueError):
    pass


def canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (RecursionError, UnicodeEncodeError, TypeError, ValueError) as exc:
        raise P0PresentedAContextEventV2TargetPrecommitError("value is not canonical JSON") from exc


def canonical_file_bytes(value: Any) -> bytes:
    return canonical_bytes(value) + b"\n"


def canonical_jsonl_bytes(rows: Sequence[Mapping[str, Any]]) -> bytes:
    return b"".join(canonical_file_bytes(row) for row in rows)


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def raw_sha256(raw: bytes) -> str:
    if type(raw) is not bytes:
        raise P0PresentedAContextEventV2TargetPrecommitError("raw input must be exact bytes")
    return hashlib.sha256(raw).hexdigest()


def with_self_hash(value: Mapping[str, Any], field: str = "artifact_sha256") -> dict[str, Any]:
    material = dict(value)
    material.pop(field, None)
    return {**material, field: canonical_sha256(material)}


RESPONSE_SCHEMA_COMMITMENT_SHA256 = canonical_sha256(RESPONSE_SCHEMA)


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise P0PresentedAContextEventV2TargetPrecommitError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _bad_constant(token: str) -> None:
    raise P0PresentedAContextEventV2TargetPrecommitError(f"non-finite token: {token}")


def _object(raw: bytes, label: str) -> dict[str, Any]:
    if (type(raw) is not bytes or not raw or len(raw) > MAX_OUTPUT_BYTES
            or b"\r" in raw or not raw.endswith(b"\n")):
        raise P0PresentedAContextEventV2TargetPrecommitError(f"{label} framing invalid")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_bad_constant)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValueError) as exc:
        raise P0PresentedAContextEventV2TargetPrecommitError(f"{label} parse failed") from exc
    if type(value) is not dict or raw != canonical_file_bytes(value):
        raise P0PresentedAContextEventV2TargetPrecommitError(f"{label} must be canonical JSON plus LF")
    return value


def _jsonl(raw: bytes, label: str) -> list[dict[str, Any]]:
    if (type(raw) is not bytes or not raw or len(raw) > MAX_OUTPUT_BYTES or b"\r" in raw
            or not raw.endswith(b"\n") or raw.endswith(b"\n\n")):
        raise P0PresentedAContextEventV2TargetPrecommitError(f"{label} framing invalid")
    lines = raw[:-1].split(b"\n")
    if any(len(line) + 1 > MAX_TARGET_ROW_BYTES for line in lines):
        raise P0PresentedAContextEventV2TargetPrecommitError(f"{label} row exceeds line cap")
    rows = [_object(line + b"\n", f"{label} row") for line in lines]
    if raw != canonical_jsonl_bytes(rows):
        raise P0PresentedAContextEventV2TargetPrecommitError(f"{label} noncanonical")
    return rows


def _strict(value: Any, fields: frozenset[str], label: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != fields:
        actual = set(value) if isinstance(value, Mapping) else set()
        raise P0PresentedAContextEventV2TargetPrecommitError(
            f"{label} fields mismatch: missing={sorted(fields-actual)}, extra={sorted(actual-fields)}"
        )
    return dict(value)


def _sha(value: Any, field: str) -> str:
    if type(value) is not str or _SHA.fullmatch(value) is None:
        raise P0PresentedAContextEventV2TargetPrecommitError(f"{field} must be sha256")
    return value


def _identifier(value: Any, field: str) -> str:
    if type(value) is not str or _ID.fullmatch(value) is None:
        raise P0PresentedAContextEventV2TargetPrecommitError(f"{field} must be safe id")
    return value


def _time(value: Any, field: str) -> datetime:
    if type(value) is not str or _RFC3339.fullmatch(value) is None:
        raise P0PresentedAContextEventV2TargetPrecommitError(f"{field} must be strict RFC3339")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise P0PresentedAContextEventV2TargetPrecommitError(f"{field} must be RFC3339") from exc
    if parsed.tzinfo is None:
        raise P0PresentedAContextEventV2TargetPrecommitError(f"{field} needs timezone")
    return parsed


def _predecessor(subject_rows_raw: bytes, subject_precommit_raw: bytes,
                 raws: Mapping[str, bytes]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if set(raws) != set(UPSTREAM_RAW_KEYS):
        raise P0PresentedAContextEventV2TargetPrecommitError("upstream raw inventory mismatch")
    all_inputs = {**raws, "subject_rows": subject_rows_raw,
                  "subject_precommit": subject_precommit_raw}
    for role, raw in all_inputs.items():
        if type(raw) is not bytes or len(raw) > EFFECTIVE_RAW_CAPS[role]:
            raise P0PresentedAContextEventV2TargetPrecommitError(
                f"{role} must be exact bytes within role cap"
            )
    try:
        subjects = subject_contract.validate_subject_rows_bytes(subject_rows_raw, **raws)
        precommit = subject_contract.validate_precommit_bytes(subject_precommit_raw, subject_rows_raw, **raws)
    except (subject_contract.P0PresentedAContextSubjectV2PrecommitError, TypeError, ValueError,
            KeyError, AttributeError, IndexError, RecursionError) as exc:
        raise P0PresentedAContextEventV2TargetPrecommitError("subject V2 predecessor invalid") from exc
    if len(subjects) != EXPECTED_TARGET_COUNT or precommit["subject_count"] != EXPECTED_TARGET_COUNT:
        raise P0PresentedAContextEventV2TargetPrecommitError("predecessor must contain exact 20 subjects")
    return subjects, precommit


def _target_rows(subjects: Sequence[Mapping[str, Any]], subject_precommit: Mapping[str, Any],
                 subject_rows_raw: bytes, subject_precommit_raw: bytes) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for sequence, subject in enumerate(subjects, start=1):
        if type(subject["input_sequence"]) is not int or subject["input_sequence"] != sequence:
            raise P0PresentedAContextEventV2TargetPrecommitError("subject order must be contiguous")
        binding = {
            "domain": TARGET_DOMAIN,
            "target_sequence": sequence,
            "subject_id": subject["subject_id"],
            "annotation_subject_sha256": subject["annotation_subject_sha256"],
            "subject_row_sha256": subject["row_sha256"],
            "subject_rows_raw_sha256": raw_sha256(subject_rows_raw),
            "subject_precommit_raw_sha256": raw_sha256(subject_precommit_raw),
            "subject_precommit_artifact_sha256": subject_precommit["artifact_sha256"],
        }
        target_commitment = canonical_sha256(binding)
        target_id = TARGET_ID_PREFIX + target_commitment
        genesis = canonical_sha256({
            "domain": JOURNAL_GENESIS_DOMAIN,
            "target_id": target_id,
            "target_commitment_sha256": target_commitment,
            "subject_precommit_artifact_sha256": subject_precommit["artifact_sha256"],
        })
        material = {
            "schema_version": TARGET_SCHEMA, "record_origin": ORIGIN,
            "target_id": target_id, "target_sequence": sequence,
            "target_record_type": "A_CONTEXT_ANNOTATION_SUBJECT_V2",
            "opportunity_kind": "PRIMARY_REVIEW", "initial_state": "NO_EVENT_RECORDED",
            "subject_id": subject["subject_id"], "subject_input_sequence": subject["input_sequence"],
            "annotation_subject_sha256": subject["annotation_subject_sha256"],
            "subject_row_sha256": subject["row_sha256"],
            "subject_rows_raw_sha256": raw_sha256(subject_rows_raw),
            "subject_precommit_raw_sha256": raw_sha256(subject_precommit_raw),
            "subject_precommit_artifact_sha256": subject_precommit["artifact_sha256"],
            "target_commitment_sha256": target_commitment,
            "journal_genesis_sha256": genesis,
        }
        result.append(with_self_hash(material, "row_sha256"))
    if (len(result) != EXPECTED_TARGET_COUNT
            or len({row["target_id"] for row in result}) != EXPECTED_TARGET_COUNT
            or len({row["journal_genesis_sha256"] for row in result}) != EXPECTED_TARGET_COUNT):
        raise P0PresentedAContextEventV2TargetPrecommitError("exactly 20 unique targets/genesis commitments required")
    return result


def _validate_target_rows_bytes(target_rows_raw: bytes, subject_rows_raw: bytes,
                                subject_precommit_raw: bytes, raws: Mapping[str, bytes]) -> list[dict[str, Any]]:
    actual = _jsonl(target_rows_raw, "target rows")
    for row in actual:
        _strict(row, _TARGET_FIELDS, "target row")
        forbidden = {
            key for key in row if key != "schema_version"
            and any(fragment in key.lower() for fragment in FORBIDDEN_PER_TARGET_FIELD_FRAGMENTS)
        }
        if forbidden:
            raise P0PresentedAContextEventV2TargetPrecommitError("per-target label/reviewer/result/event field forbidden")
        for field in ("target_sequence", "subject_input_sequence"):
            if type(row[field]) is not int:
                raise P0PresentedAContextEventV2TargetPrecommitError(f"{field} must be exact int")
        for field in (key for key in row if key.endswith("_sha256")):
            _sha(row[field], field)
        for field in ("target_id", "subject_id"):
            _identifier(row[field], field)
    subjects, predecessor = _predecessor(subject_rows_raw, subject_precommit_raw, raws)
    expected = _target_rows(subjects, predecessor, subject_rows_raw, subject_precommit_raw)
    if actual != expected:
        raise P0PresentedAContextEventV2TargetPrecommitError("targets differ from predecessor-derived projection")
    return actual


def validate_target_rows_bytes(target_rows_raw: bytes, subject_rows_raw: bytes,
                               subject_precommit_raw: bytes, **raws: bytes) -> list[dict[str, Any]]:
    try:
        return _validate_target_rows_bytes(target_rows_raw, subject_rows_raw, subject_precommit_raw, raws)
    except P0PresentedAContextEventV2TargetPrecommitError:
        raise
    except (KeyError, TypeError, AttributeError, IndexError, UnicodeEncodeError,
            UnicodeDecodeError, ValueError, ArithmeticError, RecursionError) as exc:
        raise P0PresentedAContextEventV2TargetPrecommitError("malformed target input") from exc


def build_target_rows_bytes(subject_rows_raw: bytes, subject_precommit_raw: bytes, **raws: bytes) -> bytes:
    try:
        subjects, predecessor = _predecessor(subject_rows_raw, subject_precommit_raw, raws)
        raw = canonical_jsonl_bytes(_target_rows(subjects, predecessor, subject_rows_raw, subject_precommit_raw))
        if len(raw) > MAX_OUTPUT_BYTES:
            raise P0PresentedAContextEventV2TargetPrecommitError("target rows exceed output cap")
        _validate_target_rows_bytes(raw, subject_rows_raw, subject_precommit_raw, raws)
        return raw
    except P0PresentedAContextEventV2TargetPrecommitError:
        raise
    except (KeyError, TypeError, AttributeError, IndexError, UnicodeEncodeError,
            UnicodeDecodeError, ValueError, ArithmeticError, RecursionError) as exc:
        raise P0PresentedAContextEventV2TargetPrecommitError("malformed target build input") from exc


def _precommit_value(*, target_rows_raw: bytes, targets: Sequence[Mapping[str, Any]],
                     subject_rows_raw: bytes, subject_precommit_raw: bytes,
                     subjects: Sequence[Mapping[str, Any]], subject_precommit: Mapping[str, Any],
                     raws: Mapping[str, bytes], precommitted_at: str) -> dict[str, Any]:
    bound = {key: raw_sha256(raws[key]) for key in UPSTREAM_RAW_KEYS}
    bound.update({"subject_rows": raw_sha256(subject_rows_raw),
                  "subject_precommit": raw_sha256(subject_precommit_raw)})
    target_precommit_id = TARGET_PRECOMMIT_ID_PREFIX + canonical_sha256({
        "domain": TARGET_PRECOMMIT_ID_DOMAIN, "bound_input_raw_sha256": bound,
        "target_rows_raw_sha256": raw_sha256(target_rows_raw),
        "response_schema_commitment_sha256": RESPONSE_SCHEMA_COMMITMENT_SHA256,
        "precommitted_at": precommitted_at,
    })
    counts = Counter(row["source_profile"] for row in subjects)
    material = {
        "schema_version": PRECOMMIT_SCHEMA, "record_origin": ORIGIN,
        "target_precommit_id": target_precommit_id,
        "subject_rows_raw_sha256": raw_sha256(subject_rows_raw),
        "subject_precommit_raw_sha256": raw_sha256(subject_precommit_raw),
        "subject_precommit_artifact_sha256": subject_precommit["artifact_sha256"],
        "target_rows_raw_sha256": raw_sha256(target_rows_raw),
        "bound_input_raw_sha256": bound,
        "target_count": EXPECTED_TARGET_COUNT,
        "annotation_opportunity_count": EXPECTED_TARGET_COUNT,
        "planned_primary_opportunity_count": EXPECTED_TARGET_COUNT,
        "unstarted_target_count": EXPECTED_TARGET_COUNT,
        "source_profile_counts": {profile: counts[profile] for profile in SOURCE_PROFILES},
        "target_set_sha256": canonical_sha256(list(targets)),
        "journal_genesis_set_sha256": canonical_sha256([row["journal_genesis_sha256"] for row in targets]),
        "response_schema_commitment_sha256": RESPONSE_SCHEMA_COMMITMENT_SHA256,
        "precommitted_at": precommitted_at,
        **{field: 0 for field in ZERO_COUNT_FIELDS},
        "statistical_denominator_contribution": "NONE", "metric_status": METRIC_STATUS,
        "iid_independence_assumed": False,
        "future_inferential_cluster_unit": "UPSTREAM_SOURCE_FRAME_CANDIDATE_ID",
        **{field: False for field in FALSE_FIELDS},
        "operational_effect": OPERATIONAL_EFFECT, "gate_status": GATE_STATUS,
    }
    return with_self_hash(material)


def _validate_precommit_bytes(precommit_raw: bytes, target_rows_raw: bytes,
                              subject_rows_raw: bytes, subject_precommit_raw: bytes,
                              raws: Mapping[str, bytes]) -> dict[str, Any]:
    row = _strict(_object(precommit_raw, "target precommit"), _PRECOMMIT_FIELDS, "target precommit")
    if row["schema_version"] != PRECOMMIT_SCHEMA or row["record_origin"] != ORIGIN:
        raise P0PresentedAContextEventV2TargetPrecommitError("target precommit schema/origin mismatch")
    _identifier(row["target_precommit_id"], "target_precommit_id")
    for field in (key for key in row if key.endswith("_sha256") and key != "bound_input_raw_sha256"):
        _sha(row[field], field)
    for field in FALSE_FIELDS:
        if row[field] is not False:
            raise P0PresentedAContextEventV2TargetPrecommitError(f"target precommit must keep {field}=false")
    if row["iid_independence_assumed"] is not False:
        raise P0PresentedAContextEventV2TargetPrecommitError(
            "target opportunities must not assert iid independence"
        )
    for field in ("target_count", "annotation_opportunity_count", "planned_primary_opportunity_count",
                  "unstarted_target_count", *ZERO_COUNT_FIELDS):
        if type(row[field]) is not int:
            raise P0PresentedAContextEventV2TargetPrecommitError(f"{field} must be exact int")
    if type(row["bound_input_raw_sha256"]) is not dict or set(row["bound_input_raw_sha256"]) != set(INPUT_RAW_KEYS):
        raise P0PresentedAContextEventV2TargetPrecommitError("bound input raw SHA inventory mismatch")
    for key, value in row["bound_input_raw_sha256"].items():
        _sha(value, f"bound_input_raw_sha256.{key}")
    if type(row["source_profile_counts"]) is not dict or set(row["source_profile_counts"]) != set(SOURCE_PROFILES):
        raise P0PresentedAContextEventV2TargetPrecommitError("source profile counts mismatch")
    if any(type(value) is not int for value in row["source_profile_counts"].values()):
        raise P0PresentedAContextEventV2TargetPrecommitError("source profile counts must be exact int")
    targets = _validate_target_rows_bytes(target_rows_raw, subject_rows_raw, subject_precommit_raw, raws)
    subjects, predecessor = _predecessor(subject_rows_raw, subject_precommit_raw, raws)
    if _time(row["precommitted_at"], "precommitted_at") <= _time(predecessor["precommitted_at"], "subject.precommitted_at"):
        raise P0PresentedAContextEventV2TargetPrecommitError("target precommit must strictly follow subject precommit")
    expected = _precommit_value(
        target_rows_raw=target_rows_raw, targets=targets, subject_rows_raw=subject_rows_raw,
        subject_precommit_raw=subject_precommit_raw, subjects=subjects,
        subject_precommit=predecessor, raws=raws, precommitted_at=row["precommitted_at"],
    )
    if row != expected:
        raise P0PresentedAContextEventV2TargetPrecommitError("target precommit differs from deterministic projection")
    return row


def validate_precommit_bytes(precommit_raw: bytes, target_rows_raw: bytes,
                             subject_rows_raw: bytes, subject_precommit_raw: bytes,
                             **raws: bytes) -> dict[str, Any]:
    try:
        return _validate_precommit_bytes(precommit_raw, target_rows_raw, subject_rows_raw,
                                         subject_precommit_raw, raws)
    except P0PresentedAContextEventV2TargetPrecommitError:
        raise
    except (KeyError, TypeError, AttributeError, IndexError, UnicodeEncodeError,
            UnicodeDecodeError, ValueError, ArithmeticError, RecursionError) as exc:
        raise P0PresentedAContextEventV2TargetPrecommitError("malformed target precommit input") from exc


def build_precommit_bytes(target_rows_raw: bytes, subject_rows_raw: bytes,
                          subject_precommit_raw: bytes, *, precommitted_at: str,
                          **raws: bytes) -> bytes:
    try:
        targets = _validate_target_rows_bytes(target_rows_raw, subject_rows_raw, subject_precommit_raw, raws)
        subjects, predecessor = _predecessor(subject_rows_raw, subject_precommit_raw, raws)
        if _time(precommitted_at, "precommitted_at") <= _time(predecessor["precommitted_at"], "subject.precommitted_at"):
            raise P0PresentedAContextEventV2TargetPrecommitError("target precommit must strictly follow subject precommit")
        raw = canonical_file_bytes(_precommit_value(
            target_rows_raw=target_rows_raw, targets=targets, subject_rows_raw=subject_rows_raw,
            subject_precommit_raw=subject_precommit_raw, subjects=subjects,
            subject_precommit=predecessor, raws=raws, precommitted_at=precommitted_at,
        ))
        if len(raw) > MAX_OUTPUT_BYTES:
            raise P0PresentedAContextEventV2TargetPrecommitError("target precommit exceeds output cap")
        _validate_precommit_bytes(raw, target_rows_raw, subject_rows_raw, subject_precommit_raw, raws)
        return raw
    except P0PresentedAContextEventV2TargetPrecommitError:
        raise
    except (KeyError, TypeError, AttributeError, IndexError, UnicodeEncodeError,
            UnicodeDecodeError, ValueError, ArithmeticError, RecursionError) as exc:
        raise P0PresentedAContextEventV2TargetPrecommitError("malformed target precommit build input") from exc


COMPONENT_MANIFEST = {
    "component": "p0_presented_a_context_annotation_event_v2_target_precommit_contract",
    "schemas": [TARGET_SCHEMA, PRECOMMIT_SCHEMA], "input_raw_artifact_count": 13,
    "output_raw_artifact_count": 2, "total_bound_raw_artifact_count": 15,
    "target_count": EXPECTED_TARGET_COUNT, "annotation_opportunity_count": EXPECTED_TARGET_COUNT,
    "max_output_bytes": MAX_OUTPUT_BYTES, "max_target_row_bytes": MAX_TARGET_ROW_BYTES,
    "effective_raw_caps": EFFECTIVE_RAW_CAPS,
    "consumes_packet_v1_labels_or_events": False,
    "per_target_result_values_allowed": False, "authority": "NONE",
    "validation_architecture": "PRODUCER_FREE_COMPOSED_PARENT_DELEGATION",
    "predecessor_parent_module": (
        "llm_batch.grounding."
        "p0_presented_a_context_annotation_subject_v2_precommit_parent_validator"
    ),
    "predecessor_parent_entrypoint": "validate_subject_precommit_against_raw_inputs",
    "predecessor_parent_receipt_schema": (
        "p0_presented_a_context_annotation_subject_v2_parent_receipt_v1"
    ),
    "predecessor_parent_gate_status": (
        "A_CONTEXT_V2_PRECOMMIT_PARENT_REPLAY_PASS_ALL_AUTHORITY_NO_GO"
    ),
    "predecessor_subject_component_manifest_sha256": PREDECESSOR_COMPONENT_MANIFEST_SHA256,
    "response_schema_commitment_sha256": RESPONSE_SCHEMA_COMMITMENT_SHA256,
    "iid_independence_assumed": False,
    "future_inferential_cluster_unit": "UPSTREAM_SOURCE_FRAME_CANDIDATE_ID",
}
COMPONENT_MANIFEST_SHA256 = canonical_sha256(COMPONENT_MANIFEST)


__all__ = [
    "COMPONENT_MANIFEST", "COMPONENT_MANIFEST_SHA256", "EXPECTED_TARGET_COUNT",
    "FALSE_FIELDS", "FORBIDDEN_PER_TARGET_FIELD_FRAGMENTS", "INPUT_RAW_KEYS",
    "MAX_OUTPUT_BYTES", "PRECOMMIT_SCHEMA", "P0PresentedAContextEventV2TargetPrecommitError",
    "PREDECESSOR_COMPONENT_MANIFEST_SHA256",
    "RESPONSE_SCHEMA", "RESPONSE_SCHEMA_COMMITMENT_SHA256",
    "TARGET_SCHEMA", "UPSTREAM_RAW_KEYS", "ZERO_COUNT_FIELDS", "build_precommit_bytes",
    "build_target_rows_bytes", "canonical_file_bytes", "canonical_jsonl_bytes",
    "canonical_sha256", "raw_sha256", "validate_precommit_bytes",
    "validate_target_rows_bytes", "with_self_hash",
]
