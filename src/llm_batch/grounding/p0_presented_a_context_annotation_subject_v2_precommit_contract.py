"""Presented A-context annotation subject V2의 label-free precommit 계약.

source full-frame V2의 selected 40, registry/capture bridge 40, 별도 A-context
full-frame selected 20을 raw SHA lineage로 묶는다. 기존 packet V1의 label,
``a_contexts`` 및 annotation event는 입력으로 받지 않는다.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
import base64
import hashlib
import json
import re
from typing import Any, Mapping, Sequence

from llm_batch.grounding import p0_full_eligible_sampling_frame_v2_contract as source_frame
from llm_batch.grounding import p0_presented_a_context_full_frame_v1_contract as a_frame
from llm_batch.grounding import p0_presented_batch_exact_accounting_v1_contract as bridge_contract


SUBJECT_SCHEMA = "p0_presented_a_context_annotation_subject_v2_prelabel_row_v1"
PRECOMMIT_SCHEMA = "p0_presented_a_context_annotation_subject_v2_precommit_v1"
SUBJECT_DOMAIN = "P0_PRESENTED_A_CONTEXT_ANNOTATION_SUBJECT_V2_PRECOMMIT_V1"
SUBJECT_ID_PREFIX = "P0:A:SUBJECT:V2:"
GATE_STATUS = "A_CONTEXT_V2_SUBJECTS_PRECOMMITTED_ANNOTATION_NOT_STARTED_ALL_AUTHORITY_NO_GO"
METRIC_STATUS = "METRICS_NOT_ESTIMABLE_PREANNOTATION_ONLY"
ORIGIN = source_frame.EXAMPLE_ORIGIN
OPERATIONAL_EFFECT = source_frame.OPERATIONAL_EFFECT
EXPECTED_SUBJECT_COUNT = 20
EXPECTED_SOURCE_COUNT = 40
MAX_OUTPUT_BYTES = 1_000_000
SURFACE_SPAN_UNIT = "UNICODE_CODEPOINT"

FALSE_FIELDS = (
    "labels_observed", "semantic_truth_fields_used", "annotation_started",
    "actual_a_context_evidence_verified", "actual_authority_granted",
    "inferential_metrics_allowed", "complete_case_metrics_allowed",
    "production_approval", "full_scan_approval", "p0_phase_exit",
    "runtime_noninterference_verified", "write_authority_verified", "action_applied",
)
FORBIDDEN_LABEL_FIELDS = frozenset({
    "truth_work_id", "truth_kind", "annotation_status", "reviewer_id",
    "decision_work_id", "target_work_id", "target_sense_id", "gold_label",
    "candidate_work_ids", "latest_annotation_event_id",
})
LINEAGE_KEYS = (
    "source_scope", "source_census", "source_frame", "source_seed", "source_plan",
    "bridge_inventory", "a_scope", "a_census", "a_frame", "a_seed", "a_plan",
)
_SHA = re.compile(r"^[0-9a-f]{64}$")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")
_LINEAGE_FIELDS = frozenset(LINEAGE_KEYS)
_SUBJECT_FIELDS = frozenset({
    "schema_version", "record_origin", "subject_id", "input_sequence",
    "source_input_sequence", "source_frame_candidate_id", "source_selected_input_sha256",
    "source_lineage_unit_sha256", "a_frame_candidate_id", "a_context_unit_sha256",
    "a_selected_context_sha256", "source_profile", "platform_scope",
    "registry_record_id", "registry_record_commitment_sha256", "bridge_row_sha256",
    "community_scope_commitment_sha256", "capture_receipt_sha256", "source_claim_set_sha256",
    "payload_bytes", "payload_sha256", "surface_span_unit", "surface_start", "surface_end",
    "surface_sha256", "surface_text_sha256", "evidence_disposition",
    "lineage_raw_sha256", "evidence_unit_sha256", "annotation_subject_sha256",
    "row_sha256",
})
_PRECOMMIT_FIELDS = frozenset({
    "schema_version", "record_origin", "precommit_id", "lineage_raw_sha256",
    "source_sampling_frame_sha256", "source_sampling_plan_artifact_sha256",
    "source_selected_input_set_sha256", "bridge_inventory_sha256",
    "a_context_sampling_frame_sha256", "a_sampling_plan_artifact_sha256",
    "a_selected_context_set_sha256", "frame_domains_separated",
    "subject_rows_raw_sha256", "subject_count", "source_profile_counts",
    "subject_set_sha256", "precommitted_at", "v2_annotation_event_count",
    "actual_a_context_review_count", "actual_a_context_credit_count",
    "statistical_denominator_contribution", "metric_status", *FALSE_FIELDS,
    "operational_effect", "gate_status", "artifact_sha256",
})


class P0PresentedAContextSubjectV2PrecommitError(ValueError):
    pass


def canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (RecursionError, UnicodeEncodeError, TypeError, ValueError) as exc:
        raise P0PresentedAContextSubjectV2PrecommitError("value is not canonical JSON") from exc


def canonical_file_bytes(value: Any) -> bytes:
    return canonical_bytes(value) + b"\n"


def canonical_jsonl_bytes(rows: Sequence[Mapping[str, Any]]) -> bytes:
    return b"".join(canonical_file_bytes(row) for row in rows)


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def raw_sha256(raw: bytes) -> str:
    if type(raw) is not bytes:
        raise P0PresentedAContextSubjectV2PrecommitError("raw input must be exact bytes")
    return hashlib.sha256(raw).hexdigest()


def with_self_hash(value: Mapping[str, Any], field: str = "artifact_sha256") -> dict[str, Any]:
    material = dict(value)
    material.pop(field, None)
    return {**material, field: canonical_sha256(material)}


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise P0PresentedAContextSubjectV2PrecommitError(f"duplicate JSON key: {key}")
        out[key] = value
    return out


def _bad_constant(token: str) -> None:
    raise P0PresentedAContextSubjectV2PrecommitError(f"non-finite token: {token}")


def _object(raw: bytes, label: str) -> dict[str, Any]:
    if type(raw) is not bytes or not raw or len(raw) > 64_000_000 or b"\r" in raw or not raw.endswith(b"\n"):
        raise P0PresentedAContextSubjectV2PrecommitError(f"{label} framing invalid")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_bad_constant)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValueError) as exc:
        raise P0PresentedAContextSubjectV2PrecommitError(f"{label} parse failed") from exc
    if type(value) is not dict or raw != canonical_file_bytes(value):
        raise P0PresentedAContextSubjectV2PrecommitError(f"{label} must be canonical JSON plus LF")
    return value


def _jsonl(raw: bytes, label: str) -> list[dict[str, Any]]:
    if type(raw) is not bytes or not raw or len(raw) > 64_000_000 or b"\r" in raw or not raw.endswith(b"\n") or raw.endswith(b"\n\n"):
        raise P0PresentedAContextSubjectV2PrecommitError(f"{label} framing invalid")
    rows = [_object(line + b"\n", f"{label} row") for line in raw[:-1].split(b"\n")]
    if raw != canonical_jsonl_bytes(rows):
        raise P0PresentedAContextSubjectV2PrecommitError(f"{label} noncanonical")
    return rows


def _strict(value: Any, fields: frozenset[str], label: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != fields:
        actual = set(value) if isinstance(value, Mapping) else set()
        raise P0PresentedAContextSubjectV2PrecommitError(
            f"{label} fields mismatch: missing={sorted(fields-actual)}, extra={sorted(actual-fields)}"
        )
    return dict(value)


def _sha(value: Any, field: str) -> str:
    if type(value) is not str or _SHA.fullmatch(value) is None:
        raise P0PresentedAContextSubjectV2PrecommitError(f"{field} must be sha256")
    return value


def _identifier(value: Any, field: str) -> str:
    if type(value) is not str or _ID.fullmatch(value) is None:
        raise P0PresentedAContextSubjectV2PrecommitError(f"{field} must be safe id")
    return value


def _time(value: Any, field: str) -> datetime:
    if type(value) is not str:
        raise P0PresentedAContextSubjectV2PrecommitError(f"{field} must be timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise P0PresentedAContextSubjectV2PrecommitError(f"{field} must be RFC3339") from exc
    if parsed.tzinfo is None:
        raise P0PresentedAContextSubjectV2PrecommitError(f"{field} needs timezone")
    return parsed


def _lineage(raws: Mapping[str, bytes]) -> dict[str, str]:
    if set(raws) != set(LINEAGE_KEYS):
        raise P0PresentedAContextSubjectV2PrecommitError("lineage raw inventory mismatch")
    if any(type(raws[key]) is not bytes or len(raws[key]) > 64_000_000 for key in LINEAGE_KEYS):
        raise P0PresentedAContextSubjectV2PrecommitError("lineage raw type/size invalid")
    return {key: raw_sha256(raws[key]) for key in LINEAGE_KEYS}


def _validated(raws: Mapping[str, bytes]) -> dict[str, Any]:
    _lineage(raws)
    try:
        source_scope = source_frame.validate_scope_bytes(raws["source_scope"])
        source_census = source_frame.validate_census_bytes(raws["source_census"], raws["source_scope"])
        source_frame_value = source_frame.validate_frame_manifest_bytes(
            raws["source_frame"], raws["source_scope"], raws["source_census"])
        source_seed = source_frame.validate_seed_receipt_bytes(
            raws["source_seed"], raws["source_scope"], raws["source_frame"], raws["source_census"])
        source_plan = source_frame.validate_sampling_plan_bytes(
            raws["source_plan"], raws["source_scope"], raws["source_census"],
            raws["source_seed"], raws["source_frame"])
        bridge_rows, _, _ = bridge_contract._validate_bridge_rows(raws["bridge_inventory"], source_plan)
        a_scope = a_frame.validate_scope_bytes(raws["a_scope"])
        a_census = a_frame.validate_census_bytes(raws["a_census"], raws["a_scope"])
        a_frame_value = a_frame.validate_frame_manifest_bytes(
            raws["a_frame"], raws["a_scope"], raws["a_census"])
        a_seed = a_frame.validate_seed_receipt_bytes(
            raws["a_seed"], raws["a_scope"], raws["a_frame"], raws["a_census"])
        a_plan = a_frame.validate_sampling_plan_bytes(
            raws["a_plan"], raws["a_scope"], raws["a_census"], raws["a_seed"], raws["a_frame"])
    except (source_frame.P0FullEligibleFrameV2Error, bridge_contract.P0PresentedBatchAccountingError,
            a_frame.P0PresentedAContextFrameError) as exc:
        raise P0PresentedAContextSubjectV2PrecommitError(f"upstream component invalid: {exc}") from exc
    if a_scope["upstream_source_sampling_plan_raw_sha256"] != raw_sha256(raws["source_plan"]):
        raise P0PresentedAContextSubjectV2PrecommitError("A scope/source plan raw binding mismatch")
    if a_scope["upstream_bridge_inventory_raw_sha256"] != raw_sha256(raws["bridge_inventory"]):
        raise P0PresentedAContextSubjectV2PrecommitError("A scope/bridge raw binding mismatch")
    if len(source_plan["selected_inputs"]) != EXPECTED_SOURCE_COUNT or len(bridge_rows) != EXPECTED_SOURCE_COUNT:
        raise P0PresentedAContextSubjectV2PrecommitError("source plan and bridge must each contain exact 40")
    source_ids = [row["candidate_id"] for row in source_plan["selected_inputs"]]
    if [row["candidate_id"] for row in bridge_rows] != source_ids or len(set(source_ids)) != EXPECTED_SOURCE_COUNT:
        raise P0PresentedAContextSubjectV2PrecommitError("bridge/source selected order mismatch")
    if raws["source_frame"] == raws["a_frame"] or source_frame_value["artifact_sha256"] == a_frame_value["artifact_sha256"]:
        raise P0PresentedAContextSubjectV2PrecommitError("source and A frame domains must be distinct")
    if _time(source_plan["selection_sealed_at"], "source.selection_sealed_at") >= _time(a_scope["created_at"], "a_scope.created_at"):
        raise P0PresentedAContextSubjectV2PrecommitError("source selection must strictly precede A scope")
    source_census_by_id = {row["candidate_id"]: row for row in source_census}
    source_selected_by_id = {row["candidate_id"]: row for row in source_plan["selected_inputs"]}
    bridge_by_id = {row["candidate_id"]: row for row in bridge_rows}
    if len(a_census) < EXPECTED_SUBJECT_COUNT:
        raise P0PresentedAContextSubjectV2PrecommitError("A census cannot underfill selected20")
    for candidate in a_census:
        source_selected = source_selected_by_id.get(candidate["upstream_frame_candidate_id"])
        bridge = bridge_by_id.get(candidate["upstream_frame_candidate_id"])
        source_candidate = source_census_by_id.get(candidate["upstream_frame_candidate_id"])
        if source_selected is None or bridge is None or source_candidate is None:
            raise P0PresentedAContextSubjectV2PrecommitError("A census predecessor missing")
        try:
            payload_text = base64.b64decode(bridge["payload_base64"].encode("ascii"), validate=True).decode("utf-8")
        except (UnicodeDecodeError, UnicodeEncodeError, ValueError) as exc:
            raise P0PresentedAContextSubjectV2PrecommitError("A census requires strict UTF-8 bridge payload") from exc
        start, end = candidate["surface_start"], candidate["surface_end"]
        if type(start) is not int or type(end) is not int or start < 0 or end <= start or end > len(payload_text):
            raise P0PresentedAContextSubjectV2PrecommitError("A census character span invalid")
        surface_text = payload_text[start:end]
        expected_candidate = {
            "registry_record_id": bridge["registry_record_id"], "adapter_id": bridge["adapter_id"],
            "source_profile": bridge["source_profile"], "platform_scope": bridge["platform"],
            "content_fingerprint": canonical_sha256(payload_text), "payload_sha256": bridge["payload_sha256"],
            "surface_sha256": canonical_sha256(surface_text), "context_observed_at": source_candidate["observed_at"],
            "source_published_at": source_candidate["published_at"],
        }
        if candidate["upstream_frame_candidate_id"] != source_selected["candidate_id"] or any(candidate[key] != value for key, value in expected_candidate.items()):
            raise P0PresentedAContextSubjectV2PrecommitError("A census candidate/predecessor mismatch")
    return {
        "source_scope": source_scope, "source_census": source_census,
        "source_frame": source_frame_value, "source_seed": source_seed,
        "source_plan": source_plan, "bridge_rows": bridge_rows,
        "a_scope": a_scope, "a_census": a_census, "a_frame": a_frame_value,
        "a_seed": a_seed, "a_plan": a_plan,
    }


def _subjects(raws: Mapping[str, bytes], values: Mapping[str, Any]) -> list[dict[str, Any]]:
    lineage = _lineage(raws)
    source_census_by_id = {row["candidate_id"]: row for row in values["source_census"]}
    source_plan_by_id = {row["candidate_id"]: row for row in values["source_plan"]["selected_inputs"]}
    bridge_by_source_id = {row["candidate_id"]: row for row in values["bridge_rows"]}
    a_census_by_id = {row["candidate_id"]: row for row in values["a_census"]}
    result: list[dict[str, Any]] = []
    for sequence, selected_a in enumerate(values["a_plan"]["selected_contexts"], start=1):
        if selected_a["input_sequence"] != sequence:
            raise P0PresentedAContextSubjectV2PrecommitError("A selected order must be contiguous")
        candidate = a_census_by_id.get(selected_a["candidate_id"])
        if candidate is None or candidate["context_unit_sha256"] != selected_a["context_unit_sha256"]:
            raise P0PresentedAContextSubjectV2PrecommitError("A plan/census binding mismatch")
        source_selected = source_plan_by_id.get(candidate["upstream_frame_candidate_id"])
        bridge = bridge_by_source_id.get(candidate["upstream_frame_candidate_id"])
        source_candidate = source_census_by_id.get(candidate["upstream_frame_candidate_id"])
        if source_selected is None or bridge is None or source_candidate is None:
            raise P0PresentedAContextSubjectV2PrecommitError("A candidate is outside selected source/bridge 40")
        try:
            payload_text = base64.b64decode(bridge["payload_base64"].encode("ascii"), validate=True).decode("utf-8")
        except (UnicodeDecodeError, UnicodeEncodeError, ValueError) as exc:
            raise P0PresentedAContextSubjectV2PrecommitError("selected bridge payload must be strict UTF-8") from exc
        start, end = candidate["surface_start"], candidate["surface_end"]
        surface_text = payload_text[start:end]
        expected = {
            "registry_record_id": bridge["registry_record_id"], "adapter_id": bridge["adapter_id"],
            "source_profile": bridge["source_profile"], "platform_scope": bridge["platform"],
            "content_fingerprint": canonical_sha256(payload_text), "payload_sha256": bridge["payload_sha256"],
            "surface_start": start, "surface_end": end, "surface_sha256": canonical_sha256(surface_text),
            "context_observed_at": source_candidate["observed_at"], "source_published_at": source_candidate["published_at"],
        }
        if any(candidate[key] != expected_value for key, expected_value in expected.items()):
            raise P0PresentedAContextSubjectV2PrecommitError("A candidate/bridge/source evidence mismatch")
        source_selected_sha = canonical_sha256(source_selected)
        a_selected_sha = canonical_sha256(selected_a)
        evidence_unit = canonical_sha256({
            "source_selected_input_sha256": source_selected_sha,
            "bridge_row_sha256": bridge["bridge_row_sha256"],
            "a_selected_context_sha256": a_selected_sha,
            "a_context_unit_sha256": candidate["context_unit_sha256"],
            "payload_sha256": bridge["payload_sha256"],
            "community_scope_commitment_sha256": candidate["community_scope_commitment_sha256"],
            "capture_receipt_sha256": candidate["capture_receipt_sha256"],
            "source_claim_set_sha256": candidate["source_claim_set_sha256"],
        })
        disposition = (
            "UNRESOLVED_PREANNOTATION_EVIDENCE"
            if bridge["source_profile"] == "GENERIC_FALLBACK"
            else "PRESENTED_CONTEXT_UNJUDGED"
        )
        subject_material = {
            "domain": SUBJECT_DOMAIN, "lineage_raw_sha256": lineage,
            "source_selected_input_sha256": source_selected_sha,
            "a_selected_context_sha256": a_selected_sha,
            "evidence_unit_sha256": evidence_unit,
        }
        subject_sha = canonical_sha256(subject_material)
        row = {
            "schema_version": SUBJECT_SCHEMA, "record_origin": ORIGIN,
            "subject_id": SUBJECT_ID_PREFIX + subject_sha, "input_sequence": sequence,
            "source_input_sequence": source_selected["input_sequence"],
            "source_frame_candidate_id": source_selected["candidate_id"],
            "source_selected_input_sha256": source_selected_sha,
            "source_lineage_unit_sha256": source_selected["lineage_unit_sha256"],
            "a_frame_candidate_id": selected_a["candidate_id"],
            "a_context_unit_sha256": selected_a["context_unit_sha256"],
            "a_selected_context_sha256": a_selected_sha,
            "source_profile": bridge["source_profile"], "platform_scope": bridge["platform"],
            "registry_record_id": bridge["registry_record_id"],
            "registry_record_commitment_sha256": bridge["registry_record_commitment_sha256"],
            "bridge_row_sha256": bridge["bridge_row_sha256"], "payload_bytes": bridge["payload_bytes"],
            "community_scope_commitment_sha256": candidate["community_scope_commitment_sha256"],
            "capture_receipt_sha256": candidate["capture_receipt_sha256"],
            "source_claim_set_sha256": candidate["source_claim_set_sha256"],
            "payload_sha256": bridge["payload_sha256"], "surface_span_unit": SURFACE_SPAN_UNIT,
            "surface_start": start, "surface_end": end,
            "surface_sha256": canonical_sha256(surface_text), "surface_text_sha256": canonical_sha256(surface_text),
            "evidence_disposition": disposition, "lineage_raw_sha256": lineage,
            "evidence_unit_sha256": evidence_unit,
            "annotation_subject_sha256": subject_sha,
        }
        result.append(with_self_hash(row, "row_sha256"))
    if len(result) != EXPECTED_SUBJECT_COUNT or len({row["subject_id"] for row in result}) != EXPECTED_SUBJECT_COUNT:
        raise P0PresentedAContextSubjectV2PrecommitError("exactly 20 unique subjects required")
    return result


def build_subject_rows_bytes(**raws: bytes) -> bytes:
    values = _validated(raws)
    raw = canonical_jsonl_bytes(_subjects(raws, values))
    if len(raw) > MAX_OUTPUT_BYTES:
        raise P0PresentedAContextSubjectV2PrecommitError("subject rows exceed output cap")
    validate_subject_rows_bytes(raw, **raws)
    return raw


def validate_subject_rows_bytes(subject_rows_raw: bytes, **raws: bytes) -> list[dict[str, Any]]:
    if type(subject_rows_raw) is not bytes or len(subject_rows_raw) > MAX_OUTPUT_BYTES:
        raise P0PresentedAContextSubjectV2PrecommitError("subject rows exceed output cap")
    actual = _jsonl(subject_rows_raw, "subject rows")
    for row in actual:
        _strict(row, _SUBJECT_FIELDS, "subject row")
        if FORBIDDEN_LABEL_FIELDS.intersection(row):
            raise P0PresentedAContextSubjectV2PrecommitError("label/reviewer field forbidden")
        lineage = _strict(row["lineage_raw_sha256"], _LINEAGE_FIELDS, "subject lineage")
        for key in LINEAGE_KEYS:
            _sha(lineage[key], f"lineage.{key}")
        for field in ("input_sequence", "source_input_sequence", "payload_bytes", "surface_start", "surface_end"):
            if type(row[field]) is not int:
                raise P0PresentedAContextSubjectV2PrecommitError(f"{field} must be exact int")
        if row["surface_span_unit"] != SURFACE_SPAN_UNIT:
            raise P0PresentedAContextSubjectV2PrecommitError("surface span unit mismatch")
    expected = _subjects(raws, _validated(raws))
    if actual != expected:
        raise P0PresentedAContextSubjectV2PrecommitError("subjects differ from raw-derived projection")
    return actual


def _precommit_value(*, raws: Mapping[str, bytes], values: Mapping[str, Any], subjects_raw: bytes,
                     subjects: Sequence[Mapping[str, Any]], precommit_id: str, precommitted_at: str) -> dict[str, Any]:
    counts = Counter(row["source_profile"] for row in subjects)
    material = {
        "schema_version": PRECOMMIT_SCHEMA, "record_origin": ORIGIN, "precommit_id": precommit_id,
        "lineage_raw_sha256": _lineage(raws),
        "source_sampling_frame_sha256": values["source_frame"]["artifact_sha256"],
        "source_sampling_plan_artifact_sha256": values["source_plan"]["artifact_sha256"],
        "source_selected_input_set_sha256": values["source_plan"]["selected_input_set_sha256"],
        "bridge_inventory_sha256": canonical_sha256(values["bridge_rows"]),
        "a_context_sampling_frame_sha256": values["a_frame"]["artifact_sha256"],
        "a_sampling_plan_artifact_sha256": values["a_plan"]["artifact_sha256"],
        "a_selected_context_set_sha256": values["a_plan"]["selected_context_set_sha256"],
        "frame_domains_separated": True, "subject_rows_raw_sha256": raw_sha256(subjects_raw),
        "subject_count": EXPECTED_SUBJECT_COUNT,
        "source_profile_counts": {profile: counts[profile] for profile in source_frame.SOURCE_PROFILES},
        "subject_set_sha256": canonical_sha256(list(subjects)), "precommitted_at": precommitted_at,
        "v2_annotation_event_count": 0, "actual_a_context_review_count": 0,
        "actual_a_context_credit_count": 0, "statistical_denominator_contribution": "NONE",
        "metric_status": METRIC_STATUS, **{field: False for field in FALSE_FIELDS},
        "operational_effect": OPERATIONAL_EFFECT, "gate_status": GATE_STATUS,
    }
    return with_self_hash(material)


def build_precommit_bytes(subject_rows_raw: bytes, *, precommit_id: str, precommitted_at: str, **raws: bytes) -> bytes:
    _identifier(precommit_id, "precommit_id")
    values = _validated(raws)
    subjects = validate_subject_rows_bytes(subject_rows_raw, **raws)
    if _time(precommitted_at, "precommitted_at") <= _time(values["a_plan"]["selection_sealed_at"], "selection_sealed_at"):
        raise P0PresentedAContextSubjectV2PrecommitError("precommit chronology must be strictly after A selection")
    raw = canonical_file_bytes(_precommit_value(raws=raws, values=values, subjects_raw=subject_rows_raw,
                                                subjects=subjects, precommit_id=precommit_id,
                                                precommitted_at=precommitted_at))
    if len(raw) > MAX_OUTPUT_BYTES:
        raise P0PresentedAContextSubjectV2PrecommitError("precommit exceeds output cap")
    validate_precommit_bytes(raw, subject_rows_raw, **raws)
    return raw


def validate_precommit_bytes(precommit_raw: bytes, subject_rows_raw: bytes, **raws: bytes) -> dict[str, Any]:
    if type(precommit_raw) is not bytes or type(subject_rows_raw) is not bytes or len(precommit_raw) > MAX_OUTPUT_BYTES:
        raise P0PresentedAContextSubjectV2PrecommitError("precommit exceeds output cap")
    row = _strict(_object(precommit_raw, "precommit"), _PRECOMMIT_FIELDS, "precommit")
    if row["schema_version"] != PRECOMMIT_SCHEMA or row["record_origin"] != ORIGIN:
        raise P0PresentedAContextSubjectV2PrecommitError("precommit schema/origin mismatch")
    for field in FALSE_FIELDS:
        if row[field] is not False:
            raise P0PresentedAContextSubjectV2PrecommitError(f"precommit must keep {field}=false")
    for field in ("subject_count", "v2_annotation_event_count", "actual_a_context_review_count", "actual_a_context_credit_count"):
        if type(row[field]) is not int:
            raise P0PresentedAContextSubjectV2PrecommitError(f"{field} must be exact int")
    if row["frame_domains_separated"] is not True:
        raise P0PresentedAContextSubjectV2PrecommitError("frame_domains_separated must be true")
    precommit_id = _identifier(row["precommit_id"], "precommit_id")
    values = _validated(raws)
    subjects = validate_subject_rows_bytes(subject_rows_raw, **raws)
    if _time(row["precommitted_at"], "precommitted_at") <= _time(values["a_plan"]["selection_sealed_at"], "selection_sealed_at"):
        raise P0PresentedAContextSubjectV2PrecommitError("precommit chronology must be strictly after A selection")
    expected = _precommit_value(raws=raws, values=values, subjects_raw=subject_rows_raw,
                                subjects=subjects, precommit_id=precommit_id,
                                precommitted_at=row["precommitted_at"])
    if row != expected:
        raise P0PresentedAContextSubjectV2PrecommitError("precommit differs from raw-derived projection")
    return row


COMPONENT_MANIFEST = {
    "component": "p0_presented_a_context_annotation_subject_v2_precommit_contract",
    "schemas": [SUBJECT_SCHEMA, PRECOMMIT_SCHEMA], "input_raw_artifact_count": 11,
    "output_raw_artifact_count": 2, "total_bound_raw_artifact_count": 13,
    "max_output_bytes": MAX_OUTPUT_BYTES,
    "consumes_packet_v1_labels_or_events": False, "authority": "NONE",
}
COMPONENT_MANIFEST_SHA256 = canonical_sha256(COMPONENT_MANIFEST)
