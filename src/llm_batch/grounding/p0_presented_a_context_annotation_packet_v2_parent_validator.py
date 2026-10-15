"""Packet V2의 producer-free composed parent 검증기.

유일한 component dependency인 target parent를 직접 한 번 실행하고, 패킷
manifest projection은 producer 모듈을 import하지 않은 literal로 독립 재생한다.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
import re
from typing import Any, Mapping

from llm_batch.grounding import p0_presented_a_context_annotation_event_v2_target_precommit_parent_validator as target_parent


MANIFEST_SCHEMA = "p0_presented_a_context_annotation_packet_v2_manifest_v1"
PACKET_MANIFEST_FILENAME = "p0_presented_a_context_annotation_packet_v2_manifest.json"
PACKET_ID_PREFIX = "P0:A:ANNOTATION:PACKET:V2:"
PACKET_ID_DOMAIN = "P0_PRESENTED_A_CONTEXT_ANNOTATION_PACKET_V2_ID_V1"
ORIGIN = "ACTUAL_SCHEMA_CONTRACT_EXAMPLE_ONLY"
OPERATIONAL_EFFECT = "NONE_SHADOW_ONLY"
GATE_STATUS = "NO_GO_PRESENTED_A_CONTEXT_ANNOTATION_PACKET_V2_ENVELOPE_ONLY"
PARENT_GATE_STATUS = "PRESENTED_A_CONTEXT_ANNOTATION_PACKET_V2_COMPOSED_PARENT_PASS_ALL_AUTHORITY_NO_GO"
METRIC_STATUS = "METRICS_NOT_ESTIMABLE_PRE_RESULT_PACKET_ONLY"
SUBJECT_COMPONENT_MANIFEST_SHA256 = "4f8e70e08f153886576fad2dbaa2a35e298a1e7438e58a047bdf00105a8f01b6"
TARGET_COMPONENT_MANIFEST_SHA256 = "ac99ac5544bbfa5d5e264eb93bc2086eb9eed2271e18534c173df1be0dc86ecd"
RESPONSE_SCHEMA_COMMITMENT_SHA256 = "3728334be85d5b53fd1b8f403c8471bad78817735271a301bab07590c063dd41"
MAX_MANIFEST_BYTES = 1_000_000
EFFECTIVE_RAW_CAPS = {
    "source_scope": 1_000_000, "source_census": 64_000_000,
    "source_frame": 1_000_000, "source_seed": 64_000,
    "source_plan": 64_000_000, "bridge_inventory": 16_777_216,
    "a_scope": 1_000_000, "a_census": 64_000_000,
    "a_frame": 1_000_000, "a_seed": 64_000, "a_plan": 64_000_000,
    "subject_rows": 1_000_000, "subject_precommit": 1_000_000,
    "target_rows": 1_000_000, "target_precommit": 1_000_000,
}
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
FIXED_MEMBER_CONTRACT = (("packet_manifest", PACKET_MANIFEST_FILENAME, "application/json", MAX_MANIFEST_BYTES), *CHILD_FILES)
CHILD_ROLES = tuple(role for role, _, _, _ in CHILD_FILES)
MEMBER_ROLES = tuple(role for role, _, _, _ in FIXED_MEMBER_CONTRACT)
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
SOURCE_PROFILES = ("OFFICIAL_STRUCTURED", "COMMUNITY_STRUCTURED", "MEDIA_OCR", "GENERIC_FALLBACK")
FIXED_COUNTS = {
    "source_selected_count": 40, "bridge_count": 40, "a_selected_count": 20,
    "subject_count": 20, "target_count": 20, "annotation_opportunity_count": 20,
    "planned_primary_opportunity_count": 20, "unstarted_target_count": 20,
    "journal_genesis_commitment_count": 20,
}
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
    "response_schema_commitment_sha256", *FIXED_COUNTS, "source_profile_counts",
    "input_raw_artifact_count", "output_raw_artifact_count",
    "total_bound_raw_artifact_count", "fixed_child_count", "fixed_member_count",
    "generic_subject_count", "generic_target_count", *ZERO_COUNT_FIELDS,
    "terminal_status_counts", "statistical_denominator_contribution", "metric_status",
    "iid_independence_assumed", "future_inferential_cluster_unit", *FALSE_FIELDS,
    "operational_effect", "gate_status", "artifact_sha256",
})
_TARGET_RECEIPT_FIELDS = frozenset({
    "schema_version", "expected_component_manifest_sha256", "component_manifest_parity_verified",
    "validation_architecture", "producer_free_composed_parent_verified", "predecessor_parent_module",
    "predecessor_subject_component_manifest_sha256", "predecessor_subject_parent_executed",
    "predecessor_subject_parent_receipt_sha256", "validated_raw_sha256",
    "validated_raw_pin_set_sha256", "predecessor_subject_replay_delegated",
    "predecessor_subject_replay_locally_verified", "predecessor_subject_replay_locally_duplicated",
    "current_target_projection_independently_replayed", "current_precommit_projection_independently_replayed",
    "generic_fallback_target_count", "input_raw_artifact_count", "output_raw_artifact_count",
    "total_bound_raw_artifact_count", "target_count", "annotation_opportunity_count",
    "planned_primary_opportunity_count", "unstarted_target_count", "actual_a_context_review_count",
    "review_assignment_count", "journal_head_count", "annotation_event_count",
    "annotation_result_count", "actual_a_context_credit_count",
    "statistical_denominator_contribution", "metric_status", "iid_independence_assumed",
    "future_inferential_cluster_unit", "upstream_code_identity_verified",
    "same_process_monkeypatch_resistance_verified", "producer_code_imported",
    "actual_authority_granted", "target_wiring_applied", "journal_wiring_applied",
    "response_schema_wiring_verified", "inferential_metrics_allowed", "complete_case_metrics_allowed",
    "production_approval", "full_scan_approval", "p0_phase_exit", "gate_status",
    "operational_effect", "receipt_sha256",
})


class P0PresentedAContextAnnotationPacketV2ParentError(ValueError):
    pass


def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (RecursionError, UnicodeEncodeError, TypeError, ValueError) as exc:
        raise P0PresentedAContextAnnotationPacketV2ParentError("value is not canonical JSON") from exc


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


FIXED_MEMBER_CONTRACT_SHA256 = _digest(FIXED_MEMBER_CONTRACT)


def _raw(raw: bytes) -> str:
    if type(raw) is not bytes:
        raise P0PresentedAContextAnnotationPacketV2ParentError("raw input must be exact bytes")
    return hashlib.sha256(raw).hexdigest()


def _file(value: Any) -> bytes:
    return _canonical(value) + b"\n"


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise P0PresentedAContextAnnotationPacketV2ParentError(f"duplicate JSON key: {key}")
        out[key] = value
    return out


def _object(raw: bytes, label: str, cap: int) -> dict[str, Any]:
    if type(raw) is not bytes or not raw or len(raw) > cap or b"\r" in raw or not raw.endswith(b"\n"):
        raise P0PresentedAContextAnnotationPacketV2ParentError(f"{label} framing invalid")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                           parse_constant=lambda token: (_ for _ in ()).throw(
                               P0PresentedAContextAnnotationPacketV2ParentError(f"non-finite token: {token}")))
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValueError) as exc:
        raise P0PresentedAContextAnnotationPacketV2ParentError(f"{label} parse failed") from exc
    if type(value) is not dict or raw != _file(value):
        raise P0PresentedAContextAnnotationPacketV2ParentError(f"{label} noncanonical")
    return value


def _time(value: Any, label: str) -> datetime:
    if type(value) is not str or _RFC3339.fullmatch(value) is None:
        raise P0PresentedAContextAnnotationPacketV2ParentError(f"{label} must be strict RFC3339")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise P0PresentedAContextAnnotationPacketV2ParentError(f"{label} must be RFC3339") from exc
    if result.tzinfo is None:
        raise P0PresentedAContextAnnotationPacketV2ParentError(f"{label} needs timezone")
    return result


def _sha(value: Any, label: str) -> str:
    if type(value) is not str or _SHA.fullmatch(value) is None:
        raise P0PresentedAContextAnnotationPacketV2ParentError(f"{label} must be sha256")
    return value


def _self(row: Mapping[str, Any], field: str, label: str) -> None:
    submitted = _sha(row[field], f"{label}.{field}")
    material = dict(row)
    material.pop(field)
    if submitted != _digest(material):
        raise P0PresentedAContextAnnotationPacketV2ParentError(f"{label} self hash mismatch")


def _target_receipt(value: Any, expected_child_pins: Mapping[str, str]) -> dict[str, Any]:
    if type(value) is not dict or set(value) != _TARGET_RECEIPT_FIELDS:
        raise P0PresentedAContextAnnotationPacketV2ParentError("target parent receipt exact fields mismatch")
    row = dict(value)
    _self(row, "receipt_sha256", "target parent receipt")
    if row["schema_version"] != "p0_presented_a_context_annotation_event_v2_target_parent_receipt_v1":
        raise P0PresentedAContextAnnotationPacketV2ParentError("target parent receipt schema mismatch")
    required = {
        "expected_component_manifest_sha256": TARGET_COMPONENT_MANIFEST_SHA256,
        "component_manifest_parity_verified": True,
        "validation_architecture": "PRODUCER_FREE_COMPOSED_PARENT",
        "producer_free_composed_parent_verified": True,
        "predecessor_parent_module": (
            "llm_batch.grounding."
            "p0_presented_a_context_annotation_subject_v2_precommit_parent_validator"
        ),
        "predecessor_subject_component_manifest_sha256": SUBJECT_COMPONENT_MANIFEST_SHA256,
        "predecessor_subject_parent_executed": True,
        "predecessor_subject_replay_delegated": True,
        "predecessor_subject_replay_locally_verified": False,
        "predecessor_subject_replay_locally_duplicated": False,
        "current_target_projection_independently_replayed": True,
        "current_precommit_projection_independently_replayed": True,
        "generic_fallback_target_count": 5, "input_raw_artifact_count": 13,
        "output_raw_artifact_count": 2, "total_bound_raw_artifact_count": 15,
        "target_count": 20, "annotation_opportunity_count": 20,
        "planned_primary_opportunity_count": 20, "unstarted_target_count": 20,
        "actual_a_context_review_count": 0, "review_assignment_count": 0,
        "journal_head_count": 0, "annotation_event_count": 0,
        "annotation_result_count": 0, "actual_a_context_credit_count": 0,
        "statistical_denominator_contribution": "NONE",
        "metric_status": "METRICS_NOT_ESTIMABLE_TARGET_OPPORTUNITIES_ONLY",
        "iid_independence_assumed": False,
        "future_inferential_cluster_unit": "UPSTREAM_SOURCE_FRAME_CANDIDATE_ID",
        "upstream_code_identity_verified": False,
        "same_process_monkeypatch_resistance_verified": False,
        "producer_code_imported": False, "actual_authority_granted": False,
        "target_wiring_applied": False, "journal_wiring_applied": False,
        "response_schema_wiring_verified": False, "inferential_metrics_allowed": False,
        "complete_case_metrics_allowed": False, "production_approval": False,
        "full_scan_approval": False, "p0_phase_exit": False,
        "gate_status": target_parent.PARENT_GATE_STATUS, "operational_effect": OPERATIONAL_EFFECT,
    }
    if any(type(row[key]) is not type(expected) or row[key] != expected
           for key, expected in required.items()):
        raise P0PresentedAContextAnnotationPacketV2ParentError("target parent receipt semantic mismatch")
    validated_raw_sha256 = row["validated_raw_sha256"]
    if (type(validated_raw_sha256) is not dict
            or tuple(validated_raw_sha256) != CHILD_ROLES):
        raise P0PresentedAContextAnnotationPacketV2ParentError(
            "target parent receipt raw map exact ordered inventory mismatch"
        )
    for role in CHILD_ROLES:
        submitted = _sha(
            validated_raw_sha256[role],
            f"target parent receipt validated_raw_sha256.{role}",
        )
        if submitted != expected_child_pins[role]:
            raise P0PresentedAContextAnnotationPacketV2ParentError(
                "target parent receipt raw map mismatch"
            )
    if type(row["validated_raw_pin_set_sha256"]) is not str:
        raise P0PresentedAContextAnnotationPacketV2ParentError(
            "target parent receipt pin set must be exact string"
        )
    if _sha(
        row["validated_raw_pin_set_sha256"],
        "target parent receipt validated_raw_pin_set_sha256",
    ) != _digest(dict(expected_child_pins)):
        raise P0PresentedAContextAnnotationPacketV2ParentError("target parent receipt raw map mismatch")
    _sha(row["predecessor_subject_parent_receipt_sha256"], "subject parent receipt SHA")
    return row


def _expected_manifest(raws: Mapping[str, bytes], pins: Mapping[str, str], row: Mapping[str, Any],
                       target_precommit: Mapping[str, Any]) -> dict[str, Any]:
    files = [{"role": role, "path": path, "media_type": media, "max_bytes": cap,
              "rows": raws[role].count(b"\n") if media == "application/x-ndjson" else 1,
              "bytes": len(raws[role]), "sha256": pins[role]}
             for role, path, media, cap in CHILD_FILES]
    profile_counts = dict(target_precommit["source_profile_counts"])
    packet_id = PACKET_ID_PREFIX + _digest({
        "domain": PACKET_ID_DOMAIN, "created_at": row["created_at"],
        "fixed_member_contract_sha256": FIXED_MEMBER_CONTRACT_SHA256,
        "child_raw_sha256": dict(pins),
        "subject_component_manifest_sha256": SUBJECT_COMPONENT_MANIFEST_SHA256,
        "target_component_manifest_sha256": TARGET_COMPONENT_MANIFEST_SHA256,
        "response_schema_commitment_sha256": RESPONSE_SCHEMA_COMMITMENT_SHA256,
        "input_raw_artifact_count": 13, "output_raw_artifact_count": 2,
        "total_bound_raw_artifact_count": 15, "fixed_child_count": 15,
        "fixed_member_count": 16,
    })
    material = {
        "schema_version": MANIFEST_SCHEMA, "record_origin": ORIGIN, "packet_id": packet_id,
        "created_at": row["created_at"], "files": files,
        "fixed_member_contract_sha256": FIXED_MEMBER_CONTRACT_SHA256,
        "child_raw_pin_set_sha256": _digest(dict(pins)),
        "subject_component_manifest_sha256": SUBJECT_COMPONENT_MANIFEST_SHA256,
        "target_component_manifest_sha256": TARGET_COMPONENT_MANIFEST_SHA256,
        "response_schema_commitment_sha256": RESPONSE_SCHEMA_COMMITMENT_SHA256,
        "input_raw_artifact_count": 13, "output_raw_artifact_count": 2,
        "total_bound_raw_artifact_count": 15, "fixed_child_count": 15,
        "fixed_member_count": 16,
        **FIXED_COUNTS, "source_profile_counts": profile_counts,
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
    return {**material, "artifact_sha256": _digest(material)}


EXPECTED_COMPONENT_MANIFEST = {
    "component": "p0_presented_a_context_annotation_packet_v2_contract",
    "schema": MANIFEST_SCHEMA, "input_raw_artifact_count": 13,
    "output_raw_artifact_count": 2, "total_bound_raw_artifact_count": 15,
    "fixed_child_count": 15, "fixed_member_count": 16,
    "fixed_member_contract": FIXED_MEMBER_CONTRACT,
    "fixed_member_contract_sha256": FIXED_MEMBER_CONTRACT_SHA256,
    "member_raw_caps": MEMBER_RAW_CAPS,
    "subject_component_manifest_sha256": SUBJECT_COMPONENT_MANIFEST_SHA256,
    "target_component_manifest_sha256": TARGET_COMPONENT_MANIFEST_SHA256,
    "response_schema_commitment_sha256": RESPONSE_SCHEMA_COMMITMENT_SHA256,
    "memory_only": True, "authority": "NONE", "event_or_result_child_allowed": False,
    "iid_independence_assumed": False,
    "future_inferential_cluster_unit": "UPSTREAM_SOURCE_FRAME_CANDIDATE_ID",
}
EXPECTED_COMPONENT_MANIFEST_SHA256 = _digest(EXPECTED_COMPONENT_MANIFEST)


def _validate(*, manifest_raw: bytes, expected_member_raw_sha256: Mapping[str, str],
              raws: Mapping[str, bytes]) -> dict[str, Any]:
    if type(raws) is not dict or tuple(raws) != CHILD_ROLES:
        raise P0PresentedAContextAnnotationPacketV2ParentError("child raw exact ordered inventory mismatch")
    if type(expected_member_raw_sha256) is not dict or tuple(expected_member_raw_sha256) != MEMBER_ROLES:
        raise P0PresentedAContextAnnotationPacketV2ParentError("caller expected member SHA exact ordered 16-role inventory mismatch")
    all_raws = {"packet_manifest": manifest_raw, **raws}
    for role in MEMBER_ROLES:
        raw = all_raws[role]
        if type(raw) is not bytes or len(raw) > MEMBER_RAW_CAPS[role]:
            raise P0PresentedAContextAnnotationPacketV2ParentError(f"{role} must be exact bytes within role cap")
    for role in MEMBER_ROLES:
        submitted = _sha(expected_member_raw_sha256[role], f"expected_member_raw_sha256.{role}")
        if _raw(all_raws[role]) != submitted:
            raise P0PresentedAContextAnnotationPacketV2ParentError(f"caller-pinned {role} raw SHA mismatch")
    child_pins = {role: expected_member_raw_sha256[role] for role in CHILD_ROLES}
    try:
        target_receipt_value = target_parent.validate_target_precommit_against_raw_inputs(
            target_rows_raw=raws["target_rows"], target_precommit_raw=raws["target_precommit"],
            subject_rows_raw=raws["subject_rows"], subject_precommit_raw=raws["subject_precommit"],
            expected_raw_sha256=child_pins,
            **{role: raws[role] for role in CHILD_ROLES[:11]},
        )
    except (target_parent.P0PresentedAContextEventV2TargetParentError, RuntimeError, TypeError,
            ValueError, KeyError, AttributeError, IndexError, RecursionError) as exc:
        raise P0PresentedAContextAnnotationPacketV2ParentError("target parent execution failed") from exc
    target_receipt_value = _target_receipt(target_receipt_value, child_pins)
    target_precommit = _object(raws["target_precommit"], "target precommit", EFFECTIVE_RAW_CAPS["target_precommit"])
    manifest = _object(manifest_raw, "packet manifest", MAX_MANIFEST_BYTES)
    if set(manifest) != _MANIFEST_FIELDS:
        raise P0PresentedAContextAnnotationPacketV2ParentError("packet manifest exact fields mismatch")
    if type(manifest["files"]) is not list or len(manifest["files"]) != 15:
        raise P0PresentedAContextAnnotationPacketV2ParentError("manifest file inventory mismatch")
    if any(type(ref) is not dict or set(ref) != _REF_FIELDS for ref in manifest["files"]):
        raise P0PresentedAContextAnnotationPacketV2ParentError("manifest file ref exact fields mismatch")
    expected_manifest = _expected_manifest(raws, child_pins, manifest, target_precommit)
    if _canonical(manifest) != _canonical(expected_manifest):
        raise P0PresentedAContextAnnotationPacketV2ParentError("manifest independent replay mismatch")
    if _time(manifest["created_at"], "manifest.created_at") <= _time(target_precommit["precommitted_at"], "target.precommitted_at"):
        raise P0PresentedAContextAnnotationPacketV2ParentError("target precommit must strictly precede manifest")
    receipt = {
        "schema_version": "p0_presented_a_context_annotation_packet_v2_parent_receipt_v1",
        "expected_component_manifest_sha256": EXPECTED_COMPONENT_MANIFEST_SHA256,
        "component_manifest_parity_verified": True,
        "validation_architecture": "PRODUCER_FREE_COMPOSED_PARENT",
        "producer_free_composed_parent_verified": True,
        "target_parent_module": "llm_batch.grounding.p0_presented_a_context_annotation_event_v2_target_precommit_parent_validator",
        "target_component_manifest_sha256": TARGET_COMPONENT_MANIFEST_SHA256,
        "target_parent_executed": True,
        "target_parent_receipt_sha256": target_receipt_value["receipt_sha256"],
        "target_parent_receipt_full_sha256": _digest(target_receipt_value),
        "target_replay_delegated": True, "target_replay_locally_verified": False,
        "packet_envelope_independently_replayed": True,
        "validated_member_raw_sha256": dict(expected_member_raw_sha256),
        "validated_member_raw_pin_set_sha256": _digest(dict(expected_member_raw_sha256)),
        "fixed_member_contract_sha256": FIXED_MEMBER_CONTRACT_SHA256,
        "packet_id": manifest["packet_id"],
        "packet_manifest_artifact_sha256": manifest["artifact_sha256"],
        "packet_manifest_raw_sha256": expected_member_raw_sha256["packet_manifest"],
        "response_schema_commitment_sha256": RESPONSE_SCHEMA_COMMITMENT_SHA256,
        "input_raw_artifact_count": 13, "output_raw_artifact_count": 2,
        "total_bound_raw_artifact_count": 15, "fixed_child_count": 15,
        "fixed_member_count": 16, **FIXED_COUNTS,
        "source_profile_counts": {profile: 5 for profile in SOURCE_PROFILES},
        "generic_subject_count": 5, "generic_target_count": 5,
        **{field: 0 for field in ZERO_COUNT_FIELDS},
        "terminal_status_counts": {"JUDGED": 0, "UNJUDGED": 0, "UNAVAILABLE": 0},
        "statistical_denominator_contribution": "NONE", "metric_status": METRIC_STATUS,
        "iid_independence_assumed": False,
        "future_inferential_cluster_unit": "UPSTREAM_SOURCE_FRAME_CANDIDATE_ID",
        "target_precommitted_at": target_precommit["precommitted_at"],
        "packet_created_at": manifest["created_at"],
        "target_precommit_strictly_precedes_packet_manifest_verified": True,
        "event_or_result_child_allowed": False,
        **{field: False for field in FALSE_FIELDS},
        "upstream_code_identity_verified": False,
        "same_process_monkeypatch_resistance_verified": False,
        "producer_code_imported": False,
        "predecessor_subject_parent_receipt_value_independently_verified": False,
        "operational_effect": OPERATIONAL_EFFECT,
        "gate_status": PARENT_GATE_STATUS,
    }
    return {**receipt, "receipt_sha256": _digest(receipt)}


def validate_packet_manifest_against_raw_inputs(*, manifest_raw: bytes,
                                                expected_member_raw_sha256: Mapping[str, str],
                                                **raws: bytes) -> dict[str, Any]:
    try:
        return _validate(manifest_raw=manifest_raw,
                         expected_member_raw_sha256=expected_member_raw_sha256, raws=raws)
    except P0PresentedAContextAnnotationPacketV2ParentError:
        raise
    except (KeyError, TypeError, AttributeError, IndexError, UnicodeEncodeError,
            UnicodeDecodeError, ValueError, ArithmeticError, RecursionError) as exc:
        raise P0PresentedAContextAnnotationPacketV2ParentError("malformed packet V2 parent input") from exc


__all__ = [
    "EXPECTED_COMPONENT_MANIFEST", "EXPECTED_COMPONENT_MANIFEST_SHA256",
    "FIXED_MEMBER_CONTRACT", "FIXED_MEMBER_CONTRACT_SHA256", "PARENT_GATE_STATUS",
    "P0PresentedAContextAnnotationPacketV2ParentError",
    "validate_packet_manifest_against_raw_inputs",
]
