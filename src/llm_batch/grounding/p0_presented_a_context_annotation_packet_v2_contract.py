"""Presented A-context annotation packet V2의 memory-only shadow envelope.

15개 선행 raw를 고정된 순서ㆍ경로ㆍmedia type으로 봉인한다. 이 계층은
event/result/reviewer/gold 또는 파일시스템ㆍ실행 권한을 만들지 않는다.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
import re
from typing import Any, Mapping

from llm_batch.grounding import p0_presented_a_context_annotation_event_v2_target_precommit_contract as target_contract


MANIFEST_SCHEMA = "p0_presented_a_context_annotation_packet_v2_manifest_v1"
PACKET_MANIFEST_FILENAME = "p0_presented_a_context_annotation_packet_v2_manifest.json"
PACKET_ID_PREFIX = "P0:A:ANNOTATION:PACKET:V2:"
PACKET_ID_DOMAIN = "P0_PRESENTED_A_CONTEXT_ANNOTATION_PACKET_V2_ID_V1"
ORIGIN = "ACTUAL_SCHEMA_CONTRACT_EXAMPLE_ONLY"
OPERATIONAL_EFFECT = "NONE_SHADOW_ONLY"
GATE_STATUS = "NO_GO_PRESENTED_A_CONTEXT_ANNOTATION_PACKET_V2_ENVELOPE_ONLY"
METRIC_STATUS = "METRICS_NOT_ESTIMABLE_PRE_RESULT_PACKET_ONLY"
SUBJECT_COMPONENT_MANIFEST_SHA256 = "4f8e70e08f153886576fad2dbaa2a35e298a1e7438e58a047bdf00105a8f01b6"
TARGET_COMPONENT_MANIFEST_SHA256 = "ac99ac5544bbfa5d5e264eb93bc2086eb9eed2271e18534c173df1be0dc86ecd"
MAX_MANIFEST_BYTES = 1_000_000

EFFECTIVE_RAW_CAPS = dict(target_contract.COMPONENT_MANIFEST["effective_raw_caps"])
MEMBER_RAW_CAPS = {"packet_manifest": MAX_MANIFEST_BYTES, **EFFECTIVE_RAW_CAPS}
CHILD_FILES = (
    ("source_scope", "presented_source_scope_v2.json", "application/json", EFFECTIVE_RAW_CAPS["source_scope"]),
    ("source_census", "presented_source_census_v2.jsonl", "application/x-ndjson", EFFECTIVE_RAW_CAPS["source_census"]),
    ("source_frame", "presented_source_frame_v2.json", "application/json", EFFECTIVE_RAW_CAPS["source_frame"]),
    ("source_seed", "presented_source_seed_v2.json", "application/json", EFFECTIVE_RAW_CAPS["source_seed"]),
    ("source_plan", "presented_source_plan_v2.json", "application/json", EFFECTIVE_RAW_CAPS["source_plan"]),
    ("bridge_inventory", "presented_registry_capture_bridge_v1.jsonl", "application/x-ndjson", EFFECTIVE_RAW_CAPS["bridge_inventory"]),
    ("a_scope", "presented_a_context_scope_v1.json", "application/json", EFFECTIVE_RAW_CAPS["a_scope"]),
    ("a_census", "presented_a_context_census_v1.jsonl", "application/x-ndjson", EFFECTIVE_RAW_CAPS["a_census"]),
    ("a_frame", "presented_a_context_frame_v1.json", "application/json", EFFECTIVE_RAW_CAPS["a_frame"]),
    ("a_seed", "presented_a_context_seed_v1.json", "application/json", EFFECTIVE_RAW_CAPS["a_seed"]),
    ("a_plan", "presented_a_context_plan_v1.json", "application/json", EFFECTIVE_RAW_CAPS["a_plan"]),
    ("subject_rows", "presented_a_context_annotation_subject_v2.jsonl", "application/x-ndjson", EFFECTIVE_RAW_CAPS["subject_rows"]),
    ("subject_precommit", "presented_a_context_annotation_subject_v2_precommit.json", "application/json", EFFECTIVE_RAW_CAPS["subject_precommit"]),
    ("target_rows", "presented_a_context_annotation_event_v2_targets.jsonl", "application/x-ndjson", EFFECTIVE_RAW_CAPS["target_rows"]),
    ("target_precommit", "presented_a_context_annotation_event_v2_target_precommit.json", "application/json", EFFECTIVE_RAW_CAPS["target_precommit"]),
)
FIXED_MEMBER_CONTRACT = (
    ("packet_manifest", PACKET_MANIFEST_FILENAME, "application/json", MAX_MANIFEST_BYTES), *CHILD_FILES,
)
CHILD_ROLES = tuple(role for role, _, _, _ in CHILD_FILES)
MEMBER_ROLES = tuple(role for role, _, _, _ in FIXED_MEMBER_CONTRACT)
FIXED_MEMBER_CONTRACT_SHA256: str

ZERO_COUNT_FIELDS = (
    "review_assignment_count", "reviewer_count", "annotation_event_count",
    "primary_annotation_event_count", "recheck_annotation_event_count",
    "journal_head_count", "annotation_result_count", "actual_human_review_count",
    "actual_source_credit_count", "actual_a_context_review_count",
    "actual_a_context_credit_count", "gold_count", "metric_eligible_target_count",
)
FALSE_FIELDS = (
    "labels_observed", "responses_observed", "semantic_truth_fields_used",
    "annotation_started", "target_wiring_applied", "journal_wiring_applied",
    "event_wiring_applied", "result_wiring_applied", "reviewer_identity_bound",
    "reviewer_assignment_bound", "guideline_authority_verified",
    "actual_source_evidence_verified", "actual_a_context_evidence_verified",
    "actual_authority_granted", "trusted_time_verified", "trusted_revocation_verified",
    "durable_predecessor_verified", "append_only_journal_verified",
    "filesystem_handle_binding_verified", "portable_directory_binding_verified",
    "preauthorization_verified", "supervisor_execution_verified",
    "os_write_deny_verified", "runtime_noninterference_verified",
    "write_authority_verified", "descriptive_metrics_allowed",
    "inferential_metrics_allowed", "semantic_metrics_allowed",
    "complete_case_metrics_allowed", "production_approval", "full_scan_approval",
    "p0_phase_exit", "action_applied",
)
SOURCE_PROFILES = target_contract.SOURCE_PROFILES
_SHA = re.compile(r"^[0-9a-f]{64}$")
_RFC3339 = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(?:\.[0-9]+)?(?:Z|[+-][0-9]{2}:[0-9]{2})$"
)
_REF_FIELDS = frozenset({"role", "path", "media_type", "max_bytes", "rows", "bytes", "sha256"})
_MANIFEST_FIELDS = frozenset({
    "schema_version", "record_origin", "packet_id", "created_at", "files",
    "fixed_member_contract_sha256", "child_raw_pin_set_sha256",
    "subject_component_manifest_sha256", "target_component_manifest_sha256",
    "response_schema_commitment_sha256", "source_selected_count", "bridge_count",
    "input_raw_artifact_count", "output_raw_artifact_count",
    "total_bound_raw_artifact_count", "fixed_child_count", "fixed_member_count",
    "a_selected_count", "subject_count", "target_count", "annotation_opportunity_count",
    "planned_primary_opportunity_count", "unstarted_target_count",
    "journal_genesis_commitment_count", "source_profile_counts",
    "generic_subject_count", "generic_target_count", *ZERO_COUNT_FIELDS,
    "terminal_status_counts", "statistical_denominator_contribution", "metric_status",
    "iid_independence_assumed", "future_inferential_cluster_unit", *FALSE_FIELDS,
    "operational_effect", "gate_status", "artifact_sha256",
})


class P0PresentedAContextAnnotationPacketV2Error(ValueError):
    pass


def canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (RecursionError, UnicodeEncodeError, TypeError, ValueError) as exc:
        raise P0PresentedAContextAnnotationPacketV2Error("value is not canonical JSON") from exc


def canonical_file_bytes(value: Any) -> bytes:
    return canonical_bytes(value) + b"\n"


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def raw_sha256(raw: bytes) -> str:
    if type(raw) is not bytes:
        raise P0PresentedAContextAnnotationPacketV2Error("raw input must be exact bytes")
    return hashlib.sha256(raw).hexdigest()


FIXED_MEMBER_CONTRACT_SHA256 = canonical_sha256(FIXED_MEMBER_CONTRACT)


def with_self_hash(value: Mapping[str, Any], field: str = "artifact_sha256") -> dict[str, Any]:
    material = dict(value)
    material.pop(field, None)
    return {**material, field: canonical_sha256(material)}


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise P0PresentedAContextAnnotationPacketV2Error(f"duplicate JSON key: {key}")
        out[key] = value
    return out


def _bad_constant(token: str) -> None:
    raise P0PresentedAContextAnnotationPacketV2Error(f"non-finite token: {token}")


def _object(raw: bytes, label: str) -> dict[str, Any]:
    if type(raw) is not bytes or not raw or len(raw) > MAX_MANIFEST_BYTES or b"\r" in raw or not raw.endswith(b"\n"):
        raise P0PresentedAContextAnnotationPacketV2Error(f"{label} framing invalid")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_bad_constant)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValueError) as exc:
        raise P0PresentedAContextAnnotationPacketV2Error(f"{label} parse failed") from exc
    if type(value) is not dict or raw != canonical_file_bytes(value):
        raise P0PresentedAContextAnnotationPacketV2Error(f"{label} must be canonical JSON plus LF")
    return value


def _time(value: Any, field: str) -> datetime:
    if type(value) is not str or _RFC3339.fullmatch(value) is None:
        raise P0PresentedAContextAnnotationPacketV2Error(f"{field} must be strict RFC3339")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise P0PresentedAContextAnnotationPacketV2Error(f"{field} must be RFC3339") from exc
    if parsed.tzinfo is None:
        raise P0PresentedAContextAnnotationPacketV2Error(f"{field} needs timezone")
    return parsed


def _prepared(raws: Mapping[str, bytes]) -> tuple[dict[str, bytes], dict[str, str]]:
    if type(raws) is not dict or tuple(raws) != CHILD_ROLES:
        raise P0PresentedAContextAnnotationPacketV2Error("child raw exact ordered inventory mismatch")
    copied = dict(raws)
    for role in CHILD_ROLES:
        raw = copied[role]
        if type(raw) is not bytes or len(raw) > EFFECTIVE_RAW_CAPS[role]:
            raise P0PresentedAContextAnnotationPacketV2Error(f"{role} must be exact bytes within role cap")
    return copied, {role: raw_sha256(copied[role]) for role in CHILD_ROLES}


def _validated_target(raws: Mapping[str, bytes]) -> dict[str, Any]:
    if (target_contract.COMPONENT_MANIFEST_SHA256 != TARGET_COMPONENT_MANIFEST_SHA256
            or target_contract.PREDECESSOR_COMPONENT_MANIFEST_SHA256
            != SUBJECT_COMPONENT_MANIFEST_SHA256):
        raise P0PresentedAContextAnnotationPacketV2Error("target dependency component manifest pin mismatch")
    upstream = {key: raws[key] for key in target_contract.UPSTREAM_RAW_KEYS}
    try:
        target_contract.validate_target_rows_bytes(
            raws["target_rows"], raws["subject_rows"], raws["subject_precommit"], **upstream)
        return target_contract.validate_precommit_bytes(
            raws["target_precommit"], raws["target_rows"], raws["subject_rows"],
            raws["subject_precommit"], **upstream)
    except (target_contract.P0PresentedAContextEventV2TargetPrecommitError, TypeError,
            ValueError, KeyError, AttributeError, IndexError, RecursionError) as exc:
        raise P0PresentedAContextAnnotationPacketV2Error("target component invalid") from exc


def _row_count(raw: bytes, media_type: str) -> int:
    return raw.count(b"\n") if media_type == "application/x-ndjson" else 1


def _manifest_value(raws: Mapping[str, bytes], pins: Mapping[str, str], *, created_at: str,
                    target_precommit: Mapping[str, Any]) -> dict[str, Any]:
    profile_counts = dict(target_precommit["source_profile_counts"])
    files = [
        {"role": role, "path": path, "media_type": media, "max_bytes": cap,
         "rows": _row_count(raws[role], media),
         "bytes": len(raws[role]), "sha256": pins[role]}
        for role, path, media, cap in CHILD_FILES
    ]
    packet_id = PACKET_ID_PREFIX + canonical_sha256({
        "domain": PACKET_ID_DOMAIN, "created_at": created_at,
        "fixed_member_contract_sha256": FIXED_MEMBER_CONTRACT_SHA256,
        "child_raw_sha256": dict(pins),
        "subject_component_manifest_sha256": SUBJECT_COMPONENT_MANIFEST_SHA256,
        "target_component_manifest_sha256": TARGET_COMPONENT_MANIFEST_SHA256,
        "response_schema_commitment_sha256": target_contract.RESPONSE_SCHEMA_COMMITMENT_SHA256,
        "input_raw_artifact_count": 13, "output_raw_artifact_count": 2,
        "total_bound_raw_artifact_count": 15, "fixed_child_count": 15,
        "fixed_member_count": 16,
    })
    material = {
        "schema_version": MANIFEST_SCHEMA, "record_origin": ORIGIN,
        "packet_id": packet_id, "created_at": created_at, "files": files,
        "fixed_member_contract_sha256": FIXED_MEMBER_CONTRACT_SHA256,
        "child_raw_pin_set_sha256": canonical_sha256(dict(pins)),
        "subject_component_manifest_sha256": SUBJECT_COMPONENT_MANIFEST_SHA256,
        "target_component_manifest_sha256": TARGET_COMPONENT_MANIFEST_SHA256,
        "response_schema_commitment_sha256": target_contract.RESPONSE_SCHEMA_COMMITMENT_SHA256,
        "input_raw_artifact_count": 13, "output_raw_artifact_count": 2,
        "total_bound_raw_artifact_count": 15, "fixed_child_count": 15,
        "fixed_member_count": 16,
        "source_selected_count": 40, "bridge_count": 40, "a_selected_count": 20,
        "subject_count": 20, "target_count": 20, "annotation_opportunity_count": 20,
        "planned_primary_opportunity_count": 20, "unstarted_target_count": 20,
        "journal_genesis_commitment_count": 20, "source_profile_counts": profile_counts,
        "generic_subject_count": profile_counts["GENERIC_FALLBACK"],
        "generic_target_count": profile_counts["GENERIC_FALLBACK"],
        **{field: 0 for field in ZERO_COUNT_FIELDS},
        "terminal_status_counts": {"JUDGED": 0, "UNJUDGED": 0, "UNAVAILABLE": 0},
        "statistical_denominator_contribution": "NONE", "metric_status": METRIC_STATUS,
        "iid_independence_assumed": False,
        "future_inferential_cluster_unit": "UPSTREAM_SOURCE_FRAME_CANDIDATE_ID",
        **{field: False for field in FALSE_FIELDS},
        "operational_effect": OPERATIONAL_EFFECT, "gate_status": GATE_STATUS,
    }
    return with_self_hash(material)


def _validate_manifest_bytes(manifest_raw: bytes, raws: Mapping[str, bytes]) -> dict[str, Any]:
    # The envelope is attacker-presented too.  Reject its type/size before
    # hashing or decoding any (potentially very large) child artifact.
    if type(manifest_raw) is not bytes or len(manifest_raw) > MAX_MANIFEST_BYTES:
        raise P0PresentedAContextAnnotationPacketV2Error(
            "packet manifest must be exact bytes within output cap"
        )
    copied, pins = _prepared(raws)
    target_precommit = _validated_target(copied)
    row = _object(manifest_raw, "packet manifest")
    if set(row) != _MANIFEST_FIELDS:
        raise P0PresentedAContextAnnotationPacketV2Error("packet manifest exact fields mismatch")
    if type(row["files"]) is not list or len(row["files"]) != len(CHILD_FILES):
        raise P0PresentedAContextAnnotationPacketV2Error("manifest file inventory mismatch")
    for ref in row["files"]:
        if type(ref) is not dict or set(ref) != _REF_FIELDS:
            raise P0PresentedAContextAnnotationPacketV2Error("manifest file ref exact fields mismatch")
    expected = _manifest_value(copied, pins, created_at=row["created_at"], target_precommit=target_precommit)
    if canonical_bytes(row) != canonical_bytes(expected):
        raise P0PresentedAContextAnnotationPacketV2Error("manifest differs from deterministic envelope projection")
    if _time(row["created_at"], "manifest.created_at") <= _time(target_precommit["precommitted_at"], "target.precommitted_at"):
        raise P0PresentedAContextAnnotationPacketV2Error("target precommit must strictly precede manifest")
    return row


def validate_manifest_bytes(manifest_raw: bytes, child_raw_by_role: Mapping[str, bytes]) -> dict[str, Any]:
    try:
        return _validate_manifest_bytes(manifest_raw, child_raw_by_role)
    except P0PresentedAContextAnnotationPacketV2Error:
        raise
    except (KeyError, TypeError, AttributeError, IndexError, UnicodeEncodeError,
            UnicodeDecodeError, ValueError, ArithmeticError, RecursionError) as exc:
        raise P0PresentedAContextAnnotationPacketV2Error("malformed packet V2 input") from exc


def build_manifest_bytes(child_raw_by_role: Mapping[str, bytes], *, created_at: str) -> bytes:
    try:
        copied, pins = _prepared(child_raw_by_role)
        target_precommit = _validated_target(copied)
        if _time(created_at, "manifest.created_at") <= _time(target_precommit["precommitted_at"], "target.precommitted_at"):
            raise P0PresentedAContextAnnotationPacketV2Error("target precommit must strictly precede manifest")
        raw = canonical_file_bytes(_manifest_value(copied, pins, created_at=created_at,
                                                   target_precommit=target_precommit))
        if len(raw) > MAX_MANIFEST_BYTES:
            raise P0PresentedAContextAnnotationPacketV2Error("packet manifest exceeds output cap")
        _validate_manifest_bytes(raw, copied)
        return raw
    except P0PresentedAContextAnnotationPacketV2Error:
        raise
    except (KeyError, TypeError, AttributeError, IndexError, UnicodeEncodeError,
            UnicodeDecodeError, ValueError, ArithmeticError, RecursionError) as exc:
        raise P0PresentedAContextAnnotationPacketV2Error("malformed packet V2 build input") from exc


COMPONENT_MANIFEST = {
    "component": "p0_presented_a_context_annotation_packet_v2_contract",
    "schema": MANIFEST_SCHEMA, "input_raw_artifact_count": 13,
    "output_raw_artifact_count": 2, "total_bound_raw_artifact_count": 15,
    "fixed_child_count": 15, "fixed_member_count": 16,
    "fixed_member_contract": FIXED_MEMBER_CONTRACT,
    "fixed_member_contract_sha256": FIXED_MEMBER_CONTRACT_SHA256,
    "member_raw_caps": MEMBER_RAW_CAPS,
    "subject_component_manifest_sha256": SUBJECT_COMPONENT_MANIFEST_SHA256,
    "target_component_manifest_sha256": TARGET_COMPONENT_MANIFEST_SHA256,
    "response_schema_commitment_sha256": target_contract.RESPONSE_SCHEMA_COMMITMENT_SHA256,
    "memory_only": True, "authority": "NONE", "event_or_result_child_allowed": False,
    "iid_independence_assumed": False,
    "future_inferential_cluster_unit": "UPSTREAM_SOURCE_FRAME_CANDIDATE_ID",
}
COMPONENT_MANIFEST_SHA256 = canonical_sha256(COMPONENT_MANIFEST)


__all__ = [
    "CHILD_FILES", "CHILD_ROLES", "COMPONENT_MANIFEST", "COMPONENT_MANIFEST_SHA256",
    "EFFECTIVE_RAW_CAPS", "FALSE_FIELDS", "FIXED_MEMBER_CONTRACT",
    "FIXED_MEMBER_CONTRACT_SHA256", "GATE_STATUS", "MANIFEST_SCHEMA",
    "MAX_MANIFEST_BYTES", "MEMBER_RAW_CAPS", "MEMBER_ROLES", "METRIC_STATUS",
    "OPERATIONAL_EFFECT", "PACKET_MANIFEST_FILENAME",
    "P0PresentedAContextAnnotationPacketV2Error", "SUBJECT_COMPONENT_MANIFEST_SHA256",
    "TARGET_COMPONENT_MANIFEST_SHA256", "ZERO_COUNT_FIELDS", "build_manifest_bytes",
    "canonical_bytes", "canonical_file_bytes", "canonical_sha256", "raw_sha256",
    "validate_manifest_bytes", "with_self_hash",
]
