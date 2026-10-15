"""Independent raw-byte replay for the presented A-context full frame V1.

This module intentionally imports no producer or project package.  Its positive
claim is limited to a second implementation reproducing the submitted canonical
scope, census, frame, seed, and selected/surplus partition.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from fractions import Fraction
import hashlib
import json
import re
from typing import Any, Callable, Mapping


VALIDATION_RECEIPT_SCHEMA = "p0_presented_a_context_full_frame_v1_parent_receipt_v1"
PARENT_GATE_STATUS = "PRESENTED_A_CONTEXT_FRAME_PARENT_REPLAY_PASS_ALL_AUTHORITY_NO_GO"
SCOPE_SCHEMA = "p0_presented_a_context_full_sampling_scope_v1"
CENSUS_ROW_SCHEMA = "p0_presented_a_context_full_census_row_v1"
FRAME_MANIFEST_SCHEMA = "p0_presented_a_context_full_frame_manifest_v1"
SEED_RECEIPT_SCHEMA = "p0_presented_a_context_sampling_seed_receipt_v1"
SAMPLING_PLAN_SCHEMA = "p0_presented_a_context_stratified_plan_v1"
EXAMPLE_ORIGIN = "ACTUAL_SCHEMA_CONTRACT_EXAMPLE_ONLY"
OPERATIONAL_EFFECT = "NONE_SHADOW_ONLY"
PRODUCER_GATE_STATUS = "PRESENTED_A_CONTEXT_FRAME_CONDITIONAL_DESIGN_ONLY_ALL_AUTHORITY_NO_GO"
METRIC_STATUS = "METRICS_NOT_ESTIMABLE_PRESENTED_FRAME_ONLY"
SOURCE_PROFILES = (
    "OFFICIAL_STRUCTURED", "COMMUNITY_STRUCTURED", "MEDIA_OCR", "GENERIC_FALLBACK",
)
EXPECTED_PER_PROFILE_QUOTA = 5
EXPECTED_TOTAL_QUOTA = 20
SELECTION_ALGORITHM = "SHA256_A_CONTEXT_STRATIFIED_SRSWOR_WITHOUT_REPLACEMENT_V1"
RANK_DOMAIN = "P0_PRESENTED_A_CONTEXT_FULL_FRAME_V1_RANK"
SEED_DERIVATION_DOMAIN = "P0_PRESENTED_A_CONTEXT_FULL_FRAME_V1_DERIVED_SEED"
CONTEXT_UNIT_DOMAIN = "P0_PRESENTED_A_CONTEXT_FULL_FRAME_V1_CONTEXT_UNIT"
CANDIDATE_ID_DOMAIN = "P0_PRESENTED_A_CONTEXT_FULL_FRAME_V1_CANDIDATE_ID"
STRATUM_ID_DOMAIN = "P0_PRESENTED_A_CONTEXT_FULL_FRAME_V1_STRATUM_ID"
MAX_CENSUS_BYTES = 64_000_000
MAX_CENSUS_ROW_BYTES = 64_000
MAX_CENSUS_ROWS = 1_000_000
FALSE_AUTHORITY_FIELDS = (
    "external_context_enumeration_completeness_verified",
    "external_owner_authority_verified", "enumeration_adapter_runtime_verified",
    "rights_factual_authority_verified", "source_capture_authority_verified",
    "seed_authority_verified", "seed_randomness_authority_verified",
    "probability_design_authority_verified", "annotation_not_started_authority_verified",
    "code_identity_verified", "runtime_execution_verified",
    "actual_a_context_evidence_verified", "route_packet_runtime_credit_authority_verified",
    "actual_authority_granted", "p0_phase_exit", "production_approval", "full_scan_approval",
)
EXCLUSION_REASON_ORDER = (
    "RIGHTS_POLICY_NOT_ASSESSED", "COLLECTION_NOT_ALLOWED",
    "TAKEDOWN_NOT_ACTIVE", "SOURCE_BINDING_NOT_VERIFIED",
)
_SHA = re.compile(r"^[0-9a-f]{64}$")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:._-]{0,511}$")


class P0PresentedAContextFrameParentError(ValueError):
    """Independent replay rejected the presented frame."""


def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError, RecursionError) as exc:
        raise P0PresentedAContextFrameParentError("non-canonical JSON value") from exc


def _file(value: Any) -> bytes:
    return _canonical(value) + b"\n"


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _raw_digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise P0PresentedAContextFrameParentError("duplicate JSON key")
        result[key] = value
    return result


def _constant(token: str) -> None:
    raise P0PresentedAContextFrameParentError(f"non-finite number: {token}")


def _object(raw: bytes, label: str, maximum: int = 64_000_000) -> dict[str, Any]:
    if type(raw) is not bytes or not raw or len(raw) > maximum or raw.startswith(b"\xef\xbb\xbf") or b"\r" in raw or not raw.endswith(b"\n"):
        raise P0PresentedAContextFrameParentError(f"{label} framing mismatch")
    try:
        row = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_constant)
    except P0PresentedAContextFrameParentError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError) as exc:
        raise P0PresentedAContextFrameParentError(f"{label} JSON mismatch") from exc
    if type(row) is not dict or _file(row) != raw:
        raise P0PresentedAContextFrameParentError(f"{label} canonical bytes mismatch")
    return row


def _jsonl(
    raw: bytes,
    row_validator: Callable[[dict[str, Any], int], dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    if type(raw) is not bytes or not raw or len(raw) > MAX_CENSUS_BYTES or raw.startswith(b"\xef\xbb\xbf") or b"\r" in raw or not raw.endswith(b"\n"):
        raise P0PresentedAContextFrameParentError("census framing mismatch")
    rows: list[dict[str, Any]] = []
    offset = 0
    index = 1
    while offset < len(raw):
        if index > MAX_CENSUS_ROWS:
            raise P0PresentedAContextFrameParentError("census count mismatch")
        newline = raw.find(b"\n", offset)
        if newline < 0:
            raise P0PresentedAContextFrameParentError("census framing mismatch")
        if newline + 1 - offset > MAX_CENSUS_ROW_BYTES:
            raise P0PresentedAContextFrameParentError(
                f"census row {index} framing mismatch"
            )
        line = raw[offset : newline + 1]
        value = _object(line, f"census row {index}", MAX_CENSUS_ROW_BYTES)
        if set(value) != CENSUS_FIELDS:
            raise P0PresentedAContextFrameParentError(
                f"census row {index} fields mismatch"
            )
        rows.append(value if row_validator is None else row_validator(value, index))
        offset = newline + 1
        index += 1
    if not rows:
        raise P0PresentedAContextFrameParentError("census count mismatch")
    return rows


def _strict(row: Any, fields: set[str] | frozenset[str], label: str) -> dict[str, Any]:
    if type(row) is not dict or set(row) != set(fields):
        raise P0PresentedAContextFrameParentError(f"{label} fields mismatch")
    return dict(row)


def _text(value: Any, field: str, maximum: int = 512) -> str:
    if type(value) is not str or not value or value != value.strip() or len(value) > maximum:
        raise P0PresentedAContextFrameParentError(f"{field} text mismatch")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise P0PresentedAContextFrameParentError(f"{field} Unicode mismatch") from exc
    return value


def _id(value: Any, field: str) -> str:
    value = _text(value, field)
    if _ID.fullmatch(value) is None:
        raise P0PresentedAContextFrameParentError(f"{field} identifier mismatch")
    return value


def _sha(value: Any, field: str) -> str:
    if type(value) is not str or _SHA.fullmatch(value) is None:
        raise P0PresentedAContextFrameParentError(f"{field} SHA mismatch")
    return value


def _int(value: Any, field: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise P0PresentedAContextFrameParentError(f"{field} integer mismatch")
    return value


def _bool(value: Any, field: str) -> bool:
    if type(value) is not bool:
        raise P0PresentedAContextFrameParentError(f"{field} boolean mismatch")
    return value


def _time(value: Any, field: str) -> datetime:
    value = _text(value, field, 64)
    if not value.endswith("Z"):
        raise P0PresentedAContextFrameParentError(f"{field} UTC mismatch")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise P0PresentedAContextFrameParentError(f"{field} time mismatch") from exc
    if parsed.isoformat().replace("+00:00", "Z") != value:
        raise P0PresentedAContextFrameParentError(f"{field} canonical time mismatch")
    return parsed


def _self_hash(row: Mapping[str, Any], field: str, label: str) -> None:
    stored = _sha(row[field], field)
    if stored != _digest({key: value for key, value in row.items() if key != field}):
        raise P0PresentedAContextFrameParentError(f"{label} self hash mismatch")


SCOPE_FIELDS = frozenset({
    "schema_version", "record_origin", "scope_id", "created_at", "frame_cutoff",
    "adapter_profile_map", "strata", "upstream_source_sampling_plan_raw_sha256",
    "upstream_bridge_inventory_raw_sha256", "context_enumeration_policy_sha256",
    "eligibility_policy_sha256", "rights_policy_sha256", "strata_policy_sha256",
    "future_seed_spec_sha256", "expected_per_profile_quota", "expected_total_quota",
    "selection_algorithm", "labels_observed", "semantic_truth_fields_used",
    "annotation_started", "action_applied", "operational_effect", "artifact_sha256",
})
CANDIDATE_FIELDS = frozenset({
    "upstream_frame_candidate_id", "registry_record_id", "adapter_id", "platform_scope",
    "community_scope_commitment_sha256", "content_fingerprint", "payload_sha256",
    "surface_start", "surface_end", "surface_sha256", "context_observed_at",
    "source_published_at", "capture_receipt_sha256", "source_claim_set_sha256",
    "presented_rights_policy_assessed", "presented_collection_allowed",
    "presented_takedown_status", "presented_source_binding_verified",
})
CENSUS_FIELDS = frozenset({
    "schema_version", "record_origin", "enumeration_sequence", "candidate_id",
    "context_unit_sha256", *CANDIDATE_FIELDS, "source_profile", "utc_day",
    "eligibility_status", "exclusion_reason_codes", "action_applied",
    "operational_effect", "row_sha256",
})
FRAME_FIELDS = frozenset({
    "schema_version", "record_origin", "scope_sha256", "frame_sealed_at",
    "census_byte_count", "census_raw_sha256", "census_row_count",
    "eligible_candidate_count", "excluded_candidate_count", "eligible_sampling_units_sha256",
    "excluded_candidates_sha256", "stratum_populations", "presented_census_serialization_verified",
    "presented_serialization_only", *FALSE_AUTHORITY_FIELDS, "gate_status",
    "actual_a_context_review_count", "actual_surplus_review_count",
    "statistical_denominator_contribution", "metric_status",
    "inferential_metrics_allowed", "complete_case_metrics_allowed",
    "action_applied", "operational_effect", "artifact_sha256",
})
SEED_FIELDS = frozenset({
    "schema_version", "record_origin", "seed_receipt_id", "scope_sha256",
    "frame_manifest_sha256", "census_raw_sha256", "future_seed_spec_sha256",
    "revealed_seed_sha256", "frame_owner_precommit_sha256", "frame_owner_precommitted_at",
    "revealed_at", "owner_authority_verified", "seed_authority_verified",
    "action_applied", "operational_effect", "artifact_sha256",
})
ITEM_FIELDS = frozenset({
    "input_sequence", "candidate_id", "context_unit_sha256", "upstream_frame_candidate_id",
    "registry_record_id", "source_profile", "platform_scope", "utc_day", "stratum_id",
    "rank_sha256", "N_h", "n_h", "inclusion_probability_numerator",
    "inclusion_probability_denominator",
})
PLAN_FIELDS = frozenset({
    "schema_version", "record_origin", "scope_sha256", "seed_receipt_sha256",
    "frame_manifest_sha256", "selection_algorithm", "derived_seed_sha256",
    "without_replacement", "spill_allowed", "replacement_allowed", "input_count",
    "per_profile_counts", "selected_contexts", "selected_context_set_sha256",
    "eligible_surplus_count", "eligible_surplus_contexts", "eligible_surplus_set_sha256",
    "eligible_partition_sha256", "selection_sealed_at", "presented_serialization_only",
    *FALSE_AUTHORITY_FIELDS, "gate_status", "action_applied", "operational_effect", "artifact_sha256",
    "actual_a_context_review_count", "actual_surplus_review_count",
    "statistical_denominator_contribution", "metric_status",
    "inferential_metrics_allowed", "complete_case_metrics_allowed",
})


def _scope(raw: bytes) -> dict[str, Any]:
    row = _strict(_object(raw, "scope", 1_000_000), SCOPE_FIELDS, "scope")
    if row["schema_version"] != SCOPE_SCHEMA or row["record_origin"] != EXAMPLE_ORIGIN:
        raise P0PresentedAContextFrameParentError("scope schema/origin mismatch")
    _id(row["scope_id"], "scope_id")
    if _time(row["created_at"], "created_at") > _time(row["frame_cutoff"], "frame_cutoff"):
        raise P0PresentedAContextFrameParentError("scope chronology mismatch")
    for field in (
        "upstream_source_sampling_plan_raw_sha256", "upstream_bridge_inventory_raw_sha256",
        "context_enumeration_policy_sha256", "eligibility_policy_sha256", "rights_policy_sha256",
        "strata_policy_sha256", "future_seed_spec_sha256",
    ):
        _sha(row[field], field)
    adapters = row["adapter_profile_map"]
    if type(adapters) is not list or not adapters:
        raise P0PresentedAContextFrameParentError("adapter map mismatch")
    for item in adapters:
        _strict(item, {"adapter_id", "source_profile"}, "adapter")
        _id(item["adapter_id"], "adapter_id")
        if item["source_profile"] not in SOURCE_PROFILES:
            raise P0PresentedAContextFrameParentError("adapter profile mismatch")
    if adapters != sorted(adapters, key=lambda x: x["adapter_id"]) or len({x["adapter_id"] for x in adapters}) != len(adapters):
        raise P0PresentedAContextFrameParentError("adapter ordering mismatch")
    strata = row["strata"]
    if type(strata) is not list or not strata:
        raise P0PresentedAContextFrameParentError("strata mismatch")
    order = {profile: index for index, profile in enumerate(SOURCE_PROFILES)}
    quotas = Counter()
    keys = []
    for item in strata:
        _strict(item, {"source_profile", "platform_scope", "utc_day", "quota"}, "stratum")
        if item["source_profile"] not in SOURCE_PROFILES:
            raise P0PresentedAContextFrameParentError("stratum profile mismatch")
        _id(item["platform_scope"], "platform_scope")
        if len(_text(item["utc_day"], "utc_day", 10)) != 10:
            raise P0PresentedAContextFrameParentError("stratum day mismatch")
        try:
            datetime.fromisoformat(item["utc_day"])
        except ValueError as exc:
            raise P0PresentedAContextFrameParentError("stratum day mismatch") from exc
        quotas[item["source_profile"]] += _int(item["quota"], "quota", 1)
        keys.append((item["source_profile"], item["platform_scope"], item["utc_day"]))
    if strata != sorted(strata, key=lambda x: (order[x["source_profile"]], x["platform_scope"], x["utc_day"])) or len(set(keys)) != len(keys):
        raise P0PresentedAContextFrameParentError("stratum order mismatch")
    if dict(quotas) != {profile: 5 for profile in SOURCE_PROFILES}:
        raise P0PresentedAContextFrameParentError("profile quota mismatch")
    if (
        _int(row["expected_per_profile_quota"], "expected_per_profile_quota", 1) != 5
        or _int(row["expected_total_quota"], "expected_total_quota", 1) != 20
        or row["selection_algorithm"] != SELECTION_ALGORITHM
    ):
        raise P0PresentedAContextFrameParentError("scope constants mismatch")
    if any(row[field] is not False for field in ("labels_observed", "semantic_truth_fields_used", "annotation_started", "action_applied")) or row["operational_effect"] != OPERATIONAL_EFFECT:
        raise P0PresentedAContextFrameParentError("scope must remain pre-label/no-write")
    _self_hash(row, "artifact_sha256", "scope")
    return row


def _unit(row: Mapping[str, Any]) -> str:
    return _digest({
        "domain": CONTEXT_UNIT_DOMAIN, "registry_record_id": row["registry_record_id"],
        "platform_scope": row["platform_scope"],
        "community_scope_commitment_sha256": row["community_scope_commitment_sha256"],
        "content_fingerprint": row["content_fingerprint"], "surface_start": row["surface_start"],
        "surface_end": row["surface_end"], "surface_sha256": row["surface_sha256"],
    })


def _candidate_id(unit: str) -> str:
    return "P0:A:FRAME:CANDIDATE:" + _digest({"domain": CANDIDATE_ID_DOMAIN, "context_unit_sha256": unit})


def _sid(profile: str, platform: str, day: str) -> str:
    return "P0:A:FRAME:STRATUM:" + _digest({"domain": STRATUM_ID_DOMAIN, "source_profile": profile, "platform_scope": platform, "utc_day": day})


def _census(raw: bytes, scope: Mapping[str, Any]) -> list[dict[str, Any]]:
    adapter_map = {x["adapter_id"]: x["source_profile"] for x in scope["adapter_profile_map"]}
    strata = {(x["source_profile"], x["platform_scope"], x["utc_day"]) for x in scope["strata"]}

    def validate_row(row: dict[str, Any], index: int) -> dict[str, Any]:
        _strict(row, CENSUS_FIELDS, "census row")
        if row["schema_version"] != CENSUS_ROW_SCHEMA or row["record_origin"] != EXAMPLE_ORIGIN or _int(row["enumeration_sequence"], "enumeration_sequence", 1) != index:
            raise P0PresentedAContextFrameParentError("census header mismatch")
        for field in ("upstream_frame_candidate_id", "registry_record_id", "adapter_id", "platform_scope"):
            _id(row[field], field)
        if row["adapter_id"] not in adapter_map:
            raise P0PresentedAContextFrameParentError("census adapter mismatch")
        for field in ("community_scope_commitment_sha256", "content_fingerprint", "payload_sha256", "surface_sha256", "capture_receipt_sha256", "source_claim_set_sha256"):
            _sha(row[field], field)
        if _int(row["surface_start"], "surface_start") >= _int(row["surface_end"], "surface_end", 1):
            raise P0PresentedAContextFrameParentError("surface span mismatch")
        observed = _time(row["context_observed_at"], "context_observed_at")
        published = _time(row["source_published_at"], "source_published_at")
        if published > observed or observed > _time(scope["frame_cutoff"], "frame_cutoff"):
            raise P0PresentedAContextFrameParentError("census chronology mismatch")
        unit = _unit(row)
        profile = adapter_map[row["adapter_id"]]
        day = row["source_published_at"][:10]
        if row["context_unit_sha256"] != unit or row["candidate_id"] != _candidate_id(unit) or row["source_profile"] != profile or row["utc_day"] != day or (profile, row["platform_scope"], day) not in strata:
            raise P0PresentedAContextFrameParentError("census derived binding mismatch")
        reasons = []
        if _bool(row["presented_rights_policy_assessed"], "presented_rights_policy_assessed") is not True:
            reasons.append("RIGHTS_POLICY_NOT_ASSESSED")
        if _bool(row["presented_collection_allowed"], "presented_collection_allowed") is not True:
            reasons.append("COLLECTION_NOT_ALLOWED")
        if row["presented_takedown_status"] not in {"ACTIVE", "PENDING_REMOVAL", "REMOVED"}:
            raise P0PresentedAContextFrameParentError("takedown mismatch")
        if row["presented_takedown_status"] != "ACTIVE":
            reasons.append("TAKEDOWN_NOT_ACTIVE")
        if _bool(row["presented_source_binding_verified"], "presented_source_binding_verified") is not True:
            reasons.append("SOURCE_BINDING_NOT_VERIFIED")
        if row["exclusion_reason_codes"] != reasons or row["eligibility_status"] != ("EXCLUDED" if reasons else "ELIGIBLE"):
            raise P0PresentedAContextFrameParentError("census eligibility mismatch")
        if row["action_applied"] is not False or row["operational_effect"] != OPERATIONAL_EFFECT:
            raise P0PresentedAContextFrameParentError("census effect mismatch")
        _self_hash(row, "row_sha256", "census row")
        return row

    rows = _jsonl(raw, validate_row)
    if rows != sorted(rows, key=lambda x: x["candidate_id"]) or len({x["candidate_id"] for x in rows}) != len(rows) or len({x["context_unit_sha256"] for x in rows}) != len(rows):
        raise P0PresentedAContextFrameParentError("census ordering/uniqueness mismatch")
    return rows


def _false(row: Mapping[str, Any], label: str) -> None:
    if any(row[field] is not False for field in FALSE_AUTHORITY_FIELDS):
        raise P0PresentedAContextFrameParentError(f"{label} authority field must be false")


def _populations(scope: Mapping[str, Any], rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts = Counter((x["source_profile"], x["platform_scope"], x["utc_day"]) for x in rows if x["eligibility_status"] == "ELIGIBLE")
    return [{"source_profile": x["source_profile"], "platform_scope": x["platform_scope"], "utc_day": x["utc_day"], "stratum_id": _sid(x["source_profile"], x["platform_scope"], x["utc_day"]), "N_h": counts[(x["source_profile"], x["platform_scope"], x["utc_day"])], "n_h": x["quota"]} for x in scope["strata"]]


def _frame(raw: bytes, scope: Mapping[str, Any], census_raw: bytes, rows: list[dict[str, Any]]) -> dict[str, Any]:
    row = _strict(_object(raw, "frame", 1_000_000), FRAME_FIELDS, "frame")
    eligible = [x for x in rows if x["eligibility_status"] == "ELIGIBLE"]
    excluded = [x for x in rows if x["eligibility_status"] == "EXCLUDED"]
    expected = {
        "schema_version": FRAME_MANIFEST_SCHEMA, "record_origin": EXAMPLE_ORIGIN,
        "scope_sha256": scope["artifact_sha256"], "census_byte_count": len(census_raw),
        "census_raw_sha256": _raw_digest(census_raw), "census_row_count": len(rows),
        "eligible_candidate_count": len(eligible), "excluded_candidate_count": len(excluded),
        "eligible_sampling_units_sha256": _digest([x["context_unit_sha256"] for x in eligible]),
        "excluded_candidates_sha256": _digest([x["candidate_id"] for x in excluded]),
        "stratum_populations": _populations(scope, rows),
    }
    if any(row[key] != value for key, value in expected.items()):
        raise P0PresentedAContextFrameParentError("frame recomputation mismatch")
    for field in ("census_byte_count", "census_row_count", "eligible_candidate_count", "excluded_candidate_count"):
        _int(row[field], field)
    if type(row["stratum_populations"]) is not list:
        raise P0PresentedAContextFrameParentError("frame population mismatch")
    for item in row["stratum_populations"]:
        _strict(item, {"source_profile", "platform_scope", "utc_day", "stratum_id", "N_h", "n_h"}, "population")
        _int(item["N_h"], "N_h")
        _int(item["n_h"], "n_h", 1)
    if _time(row["frame_sealed_at"], "frame_sealed_at") <= _time(scope["frame_cutoff"], "frame_cutoff") or row["presented_census_serialization_verified"] is not True or row["presented_serialization_only"] is not True:
        raise P0PresentedAContextFrameParentError("frame chronology/scope mismatch")
    _false(row, "frame")
    if row["actual_a_context_review_count"] != 0 or type(row["actual_a_context_review_count"]) is not int or row["actual_surplus_review_count"] != 0 or type(row["actual_surplus_review_count"]) is not int or row["statistical_denominator_contribution"] != "NONE" or row["metric_status"] != METRIC_STATUS or row["inferential_metrics_allowed"] is not False or row["complete_case_metrics_allowed"] is not False:
        raise P0PresentedAContextFrameParentError("frame metric boundary mismatch")
    if row["gate_status"] != PRODUCER_GATE_STATUS or row["action_applied"] is not False or row["operational_effect"] != OPERATIONAL_EFFECT:
        raise P0PresentedAContextFrameParentError("frame gate mismatch")
    _self_hash(row, "artifact_sha256", "frame")
    return row


def _seed(raw: bytes, scope: Mapping[str, Any], frame: Mapping[str, Any], census_raw: bytes) -> dict[str, Any]:
    row = _strict(_object(raw, "seed", 64_000), SEED_FIELDS, "seed")
    if row["schema_version"] != SEED_RECEIPT_SCHEMA or row["record_origin"] != EXAMPLE_ORIGIN or row["scope_sha256"] != scope["artifact_sha256"] or row["frame_manifest_sha256"] != frame["artifact_sha256"] or row["census_raw_sha256"] != _raw_digest(census_raw) or row["future_seed_spec_sha256"] != scope["future_seed_spec_sha256"]:
        raise P0PresentedAContextFrameParentError("seed binding mismatch")
    _id(row["seed_receipt_id"], "seed_receipt_id")
    _sha(row["revealed_seed_sha256"], "revealed_seed_sha256")
    _sha(row["frame_owner_precommit_sha256"], "frame_owner_precommit_sha256")
    pre = _time(row["frame_owner_precommitted_at"], "frame_owner_precommitted_at")
    reveal = _time(row["revealed_at"], "revealed_at")
    if pre <= _time(frame["frame_sealed_at"], "frame_sealed_at") or reveal <= pre:
        raise P0PresentedAContextFrameParentError("seed chronology mismatch")
    if row["owner_authority_verified"] is not False or row["seed_authority_verified"] is not False or row["action_applied"] is not False or row["operational_effect"] != OPERATIONAL_EFFECT:
        raise P0PresentedAContextFrameParentError("seed authority mismatch")
    _self_hash(row, "artifact_sha256", "seed")
    return row


def _rank(seed: str, eligible_sha: str, sid: str, unit: str) -> str:
    return _digest({"domain": RANK_DOMAIN, "derived_seed_sha256": seed, "eligible_sampling_units_sha256": eligible_sha, "stratum_id": sid, "context_unit_sha256": unit})


def _expected_items(scope: Mapping[str, Any], frame: Mapping[str, Any], seed_value: str, rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    selected, surplus = [], []
    sequence = 1
    eligible = [x for x in rows if x["eligibility_status"] == "ELIGIBLE"]
    for spec in scope["strata"]:
        key = (spec["source_profile"], spec["platform_scope"], spec["utc_day"])
        members = [x for x in eligible if (x["source_profile"], x["platform_scope"], x["utc_day"]) == key]
        if len(members) < spec["quota"]:
            raise P0PresentedAContextFrameParentError("stratum underfill")
        sid = _sid(*key)
        ranked = sorted(((_rank(seed_value, frame["eligible_sampling_units_sha256"], sid, x["context_unit_sha256"]), x) for x in members), key=lambda pair: (pair[0], pair[1]["candidate_id"]))
        fraction = Fraction(spec["quota"], len(members))
        for offset, (rank, candidate) in enumerate(ranked):
            item = {"input_sequence": sequence if offset < spec["quota"] else 0, "candidate_id": candidate["candidate_id"], "context_unit_sha256": candidate["context_unit_sha256"], "upstream_frame_candidate_id": candidate["upstream_frame_candidate_id"], "registry_record_id": candidate["registry_record_id"], "source_profile": candidate["source_profile"], "platform_scope": candidate["platform_scope"], "utc_day": candidate["utc_day"], "stratum_id": sid, "rank_sha256": rank, "N_h": len(members), "n_h": spec["quota"], "inclusion_probability_numerator": fraction.numerator, "inclusion_probability_denominator": fraction.denominator}
            (selected if offset < spec["quota"] else surplus).append(item)
            if offset < spec["quota"]:
                sequence += 1
    surplus.sort(key=lambda x: (x["source_profile"], x["platform_scope"], x["utc_day"], x["rank_sha256"], x["candidate_id"]))
    return selected, surplus


def validate_a_context_frame_and_plan_against_raw_inputs(
    frame_raw: bytes, plan_raw: bytes, *, scope_raw: bytes,
    census_raw: bytes, seed_receipt_raw: bytes,
) -> dict[str, Any]:
    scope = _scope(scope_raw)
    rows = _census(census_raw, scope)
    frame = _frame(frame_raw, scope, census_raw, rows)
    seed = _seed(seed_receipt_raw, scope, frame, census_raw)
    plan = _strict(_object(plan_raw, "plan"), PLAN_FIELDS, "plan")
    if plan["schema_version"] != SAMPLING_PLAN_SCHEMA or plan["record_origin"] != EXAMPLE_ORIGIN:
        raise P0PresentedAContextFrameParentError("plan schema/origin mismatch")
    for field in ("without_replacement", "spill_allowed", "replacement_allowed"):
        _bool(plan[field], field)
    _int(plan["input_count"], "input_count")
    _int(plan["eligible_surplus_count"], "eligible_surplus_count")
    if type(plan["per_profile_counts"]) is not dict or set(plan["per_profile_counts"]) != set(SOURCE_PROFILES):
        raise P0PresentedAContextFrameParentError("per-profile counts mismatch")
    for profile, count in plan["per_profile_counts"].items():
        _int(count, f"per_profile_counts.{profile}")
    if type(plan["selected_contexts"]) is not list or type(plan["eligible_surplus_contexts"]) is not list:
        raise P0PresentedAContextFrameParentError("submitted plan inventory mismatch")
    for item in plan["selected_contexts"] + plan["eligible_surplus_contexts"]:
        submitted = _strict(item, ITEM_FIELDS, "submitted plan item")
        for field in (
            "input_sequence", "N_h", "n_h",
            "inclusion_probability_numerator", "inclusion_probability_denominator",
        ):
            _int(submitted[field], field)
        if submitted["N_h"] < 1 or submitted["n_h"] < 1 or submitted["n_h"] > submitted["N_h"] or submitted["inclusion_probability_numerator"] < 1 or submitted["inclusion_probability_denominator"] < 1:
            raise P0PresentedAContextFrameParentError("submitted plan denominator mismatch")
    derived = _digest({"domain": SEED_DERIVATION_DOMAIN, "scope_sha256": scope["artifact_sha256"], "frame_manifest_sha256": frame["artifact_sha256"], "future_seed_spec_sha256": scope["future_seed_spec_sha256"], "revealed_seed_sha256": seed["revealed_seed_sha256"], "frame_owner_precommit_sha256": seed["frame_owner_precommit_sha256"]})
    selected, surplus = _expected_items(scope, frame, derived, rows)
    eligible_ids = sorted(x["candidate_id"] for x in rows if x["eligibility_status"] == "ELIGIBLE")
    expected = {
        "scope_sha256": scope["artifact_sha256"], "seed_receipt_sha256": seed["artifact_sha256"],
        "frame_manifest_sha256": frame["artifact_sha256"], "selection_algorithm": SELECTION_ALGORITHM,
        "derived_seed_sha256": derived, "without_replacement": True, "spill_allowed": False,
        "replacement_allowed": False, "input_count": 20,
        "per_profile_counts": {profile: 5 for profile in SOURCE_PROFILES},
        "selected_contexts": selected, "selected_context_set_sha256": _digest(selected),
        "eligible_surplus_count": len(surplus), "eligible_surplus_contexts": surplus,
        "eligible_surplus_set_sha256": _digest(surplus),
        "eligible_partition_sha256": _digest(eligible_ids),
    }
    if any(plan[key] != value for key, value in expected.items()):
        raise P0PresentedAContextFrameParentError("plan independent recomputation mismatch")
    if sorted(x["candidate_id"] for x in selected + surplus) != eligible_ids or {x["candidate_id"] for x in selected} & {x["candidate_id"] for x in surplus}:
        raise P0PresentedAContextFrameParentError("eligible partition mismatch")
    if _time(plan["selection_sealed_at"], "selection_sealed_at") <= _time(seed["revealed_at"], "revealed_at") or plan["presented_serialization_only"] is not True:
        raise P0PresentedAContextFrameParentError("plan chronology/scope mismatch")
    _false(plan, "plan")
    if plan["actual_a_context_review_count"] != 0 or type(plan["actual_a_context_review_count"]) is not int or plan["actual_surplus_review_count"] != 0 or type(plan["actual_surplus_review_count"]) is not int or plan["statistical_denominator_contribution"] != "NONE" or plan["metric_status"] != METRIC_STATUS or plan["inferential_metrics_allowed"] is not False or plan["complete_case_metrics_allowed"] is not False:
        raise P0PresentedAContextFrameParentError("plan metric boundary mismatch")
    if plan["gate_status"] != PRODUCER_GATE_STATUS or plan["action_applied"] is not False or plan["operational_effect"] != OPERATIONAL_EFFECT:
        raise P0PresentedAContextFrameParentError("plan gate mismatch")
    _self_hash(plan, "artifact_sha256", "plan")
    receipt = {
        "schema_version": VALIDATION_RECEIPT_SCHEMA,
        "scope_raw_sha256": _raw_digest(scope_raw), "census_raw_sha256": _raw_digest(census_raw),
        "frame_raw_sha256": _raw_digest(frame_raw), "seed_receipt_raw_sha256": _raw_digest(seed_receipt_raw),
        "plan_raw_sha256": _raw_digest(plan_raw), "census_row_count": len(rows),
        "eligible_candidate_count": frame["eligible_candidate_count"],
        "selected_context_count": len(selected), "eligible_surplus_count": len(surplus),
        "selected_surplus_exact_partition_verified": True,
        "parent_separate_implementation_frame_replay_verified": True,
        "actual_a_context_review_count": 0, "actual_surplus_review_count": 0,
        "statistical_denominator_contribution": "NONE", "metric_status": METRIC_STATUS,
        "inferential_metrics_allowed": False, "complete_case_metrics_allowed": False,
        "same_process_isolation_verified": False, "producer_code_identity_verified": False,
        "parent_code_identity_verified": False,
        **{field: False for field in FALSE_AUTHORITY_FIELDS},
        "credited_actual_a_context_count": 0, "gate_status": PARENT_GATE_STATUS,
        "action_applied": False, "operational_effect": OPERATIONAL_EFFECT,
    }
    return {**receipt, "receipt_sha256": _digest(receipt)}


__all__ = [
    "P0PresentedAContextFrameParentError", "PARENT_GATE_STATUS",
    "VALIDATION_RECEIPT_SCHEMA", "validate_a_context_frame_and_plan_against_raw_inputs",
]
