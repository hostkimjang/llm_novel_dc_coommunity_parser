"""Presented-only full eligible frame for the P0 A-context sample.

The component seals a caller-presented pre-label context census and deterministically
partitions every eligible unit into selected (5 x 4 profiles = 20) and surplus
sets.  It does not prove external enumeration, capture, rights, owner, beacon,
runtime, reviewer, or annotation authority and cannot grant actual credit.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from fractions import Fraction
import hashlib
import json
import math
import re
from typing import Any, Callable, Mapping, Sequence


SCOPE_SCHEMA = "p0_presented_a_context_full_sampling_scope_v1"
CENSUS_ROW_SCHEMA = "p0_presented_a_context_full_census_row_v1"
FRAME_MANIFEST_SCHEMA = "p0_presented_a_context_full_frame_manifest_v1"
SEED_RECEIPT_SCHEMA = "p0_presented_a_context_sampling_seed_receipt_v1"
SAMPLING_PLAN_SCHEMA = "p0_presented_a_context_stratified_plan_v1"
EXAMPLE_ORIGIN = "ACTUAL_SCHEMA_CONTRACT_EXAMPLE_ONLY"
OPERATIONAL_EFFECT = "NONE_SHADOW_ONLY"
GATE_STATUS = "PRESENTED_A_CONTEXT_FRAME_CONDITIONAL_DESIGN_ONLY_ALL_AUTHORITY_NO_GO"
METRIC_STATUS = "METRICS_NOT_ESTIMABLE_PRESENTED_FRAME_ONLY"

SOURCE_PROFILES = (
    "OFFICIAL_STRUCTURED",
    "COMMUNITY_STRUCTURED",
    "MEDIA_OCR",
    "GENERIC_FALLBACK",
)
EXPECTED_PER_PROFILE_QUOTA = 5
EXPECTED_TOTAL_QUOTA = 20
SELECTION_ALGORITHM = "SHA256_A_CONTEXT_STRATIFIED_SRSWOR_WITHOUT_REPLACEMENT_V1"
RANK_DOMAIN = "P0_PRESENTED_A_CONTEXT_FULL_FRAME_V1_RANK"
SEED_DERIVATION_DOMAIN = "P0_PRESENTED_A_CONTEXT_FULL_FRAME_V1_DERIVED_SEED"
CONTEXT_UNIT_DOMAIN = "P0_PRESENTED_A_CONTEXT_FULL_FRAME_V1_CONTEXT_UNIT"
CANDIDATE_ID_DOMAIN = "P0_PRESENTED_A_CONTEXT_FULL_FRAME_V1_CANDIDATE_ID"
STRATUM_ID_DOMAIN = "P0_PRESENTED_A_CONTEXT_FULL_FRAME_V1_STRATUM_ID"

MAX_SCOPE_BYTES = 1_000_000
MAX_SEED_BYTES = 64_000
MAX_CENSUS_BYTES = 64_000_000
MAX_CENSUS_ROW_BYTES = 64_000
MAX_CENSUS_ROWS = 1_000_000
TAKEDOWN_STATUSES = ("ACTIVE", "PENDING_REMOVAL", "REMOVED")
EXCLUSION_REASON_ORDER = (
    "RIGHTS_POLICY_NOT_ASSESSED",
    "COLLECTION_NOT_ALLOWED",
    "TAKEDOWN_NOT_ACTIVE",
    "SOURCE_BINDING_NOT_VERIFIED",
)

FALSE_AUTHORITY_FIELDS = (
    "external_context_enumeration_completeness_verified",
    "external_owner_authority_verified",
    "enumeration_adapter_runtime_verified",
    "rights_factual_authority_verified",
    "source_capture_authority_verified",
    "seed_authority_verified",
    "seed_randomness_authority_verified",
    "probability_design_authority_verified",
    "annotation_not_started_authority_verified",
    "code_identity_verified",
    "runtime_execution_verified",
    "actual_a_context_evidence_verified",
    "route_packet_runtime_credit_authority_verified",
    "actual_authority_granted",
    "p0_phase_exit",
    "production_approval",
    "full_scan_approval",
)

_SHA = re.compile(r"^[0-9a-f]{64}$")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:._-]{0,511}$")


class P0PresentedAContextFrameError(ValueError):
    """The presented A-context frame is malformed or internally inconsistent."""


def canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError, RecursionError) as exc:
        raise P0PresentedAContextFrameError("value is not canonical JSON") from exc


def canonical_file_bytes(value: Any) -> bytes:
    return canonical_bytes(value) + b"\n"


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def raw_sha256(value: bytes) -> str:
    if type(value) is not bytes:
        raise P0PresentedAContextFrameError("raw value must be bytes")
    return hashlib.sha256(value).hexdigest()


def with_self_hash(value: Mapping[str, Any], field: str = "artifact_sha256") -> dict[str, Any]:
    row = dict(value)
    row.pop(field, None)
    return {**row, field: canonical_sha256(row)}


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    row: dict[str, Any] = {}
    for key, value in pairs:
        if key in row:
            raise P0PresentedAContextFrameError("duplicate JSON object key")
        row[key] = value
    return row


def _constant(token: str) -> None:
    raise P0PresentedAContextFrameError(f"non-finite JSON number forbidden: {token}")


def _object(raw: bytes, label: str, maximum: int) -> dict[str, Any]:
    if type(raw) is not bytes or not raw or len(raw) > maximum:
        raise P0PresentedAContextFrameError(f"{label} byte size is invalid")
    if raw.startswith(b"\xef\xbb\xbf") or b"\r" in raw or not raw.endswith(b"\n"):
        raise P0PresentedAContextFrameError(f"{label} must be canonical UTF-8 JSON plus LF")
    try:
        value = json.loads(
            raw.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_constant
        )
    except P0PresentedAContextFrameError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError) as exc:
        raise P0PresentedAContextFrameError(f"{label} is invalid JSON") from exc
    if type(value) is not dict or canonical_file_bytes(value) != raw:
        raise P0PresentedAContextFrameError(f"{label} is not canonical")
    return value


def _jsonl(
    raw: bytes,
    row_validator: Callable[[dict[str, Any], int], dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    if type(raw) is not bytes or not raw or len(raw) > MAX_CENSUS_BYTES:
        raise P0PresentedAContextFrameError("census byte size is invalid")
    if raw.startswith(b"\xef\xbb\xbf") or b"\r" in raw or not raw.endswith(b"\n"):
        raise P0PresentedAContextFrameError("census must be canonical JSONL")
    values: list[dict[str, Any]] = []
    offset = 0
    index = 1
    while offset < len(raw):
        if index > MAX_CENSUS_ROWS:
            raise P0PresentedAContextFrameError("census row count is invalid")
        newline = raw.find(b"\n", offset)
        if newline < 0:
            raise P0PresentedAContextFrameError("census must be canonical JSONL")
        if newline + 1 - offset > MAX_CENSUS_ROW_BYTES:
            raise P0PresentedAContextFrameError(
                f"census row {index} byte size is invalid"
            )
        line = raw[offset : newline + 1]
        value = _object(line, f"census row {index}", MAX_CENSUS_ROW_BYTES)
        if set(value) != _CENSUS_FIELDS:
            raise P0PresentedAContextFrameError(
                f"census row {index} fields mismatch"
            )
        values.append(
            value if row_validator is None else row_validator(value, index)
        )
        offset = newline + 1
        index += 1
    if not values:
        raise P0PresentedAContextFrameError("census row count is invalid")
    return values


def _strict(value: Any, fields: frozenset[str], label: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != fields:
        raise P0PresentedAContextFrameError(f"{label} fields mismatch")
    return dict(value)


def _text(value: Any, field: str, maximum: int = 512) -> str:
    if type(value) is not str or not value or value != value.strip() or len(value) > maximum:
        raise P0PresentedAContextFrameError(f"{field} must be canonical nonempty text")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise P0PresentedAContextFrameError(f"{field} must be valid Unicode") from exc
    return value


def _identifier(value: Any, field: str) -> str:
    value = _text(value, field)
    if _ID.fullmatch(value) is None:
        raise P0PresentedAContextFrameError(f"{field} is invalid")
    return value


def _sha(value: Any, field: str) -> str:
    if type(value) is not str or _SHA.fullmatch(value) is None:
        raise P0PresentedAContextFrameError(f"{field} must be lowercase SHA-256")
    return value


def _boolean(value: Any, field: str) -> bool:
    if type(value) is not bool:
        raise P0PresentedAContextFrameError(f"{field} must be boolean")
    return value


def _integer(value: Any, field: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise P0PresentedAContextFrameError(f"{field} must be an integer >= {minimum}")
    return value


def _timestamp(value: Any, field: str) -> datetime:
    value = _text(value, field, 64)
    if not value.endswith("Z"):
        raise P0PresentedAContextFrameError(f"{field} must be UTC Z time")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise P0PresentedAContextFrameError(f"{field} is invalid") from exc
    if parsed.isoformat().replace("+00:00", "Z") != value:
        raise P0PresentedAContextFrameError(f"{field} must be canonical RFC3339")
    return parsed


def _day(value: Any, field: str = "utc_day") -> str:
    value = _text(value, field, 10)
    try:
        datetime.fromisoformat(value)
    except ValueError as exc:
        raise P0PresentedAContextFrameError(f"{field} is invalid") from exc
    if len(value) != 10:
        raise P0PresentedAContextFrameError(f"{field} is invalid")
    return value


def _self_hash(row: Mapping[str, Any], field: str, label: str) -> None:
    stored = _sha(row[field], field)
    material = {key: item for key, item in row.items() if key != field}
    if canonical_sha256(material) != stored:
        raise P0PresentedAContextFrameError(f"{label} self hash mismatch")


def _false_fields(row: Mapping[str, Any], label: str) -> None:
    for field in FALSE_AUTHORITY_FIELDS:
        if _boolean(row[field], field) is not False:
            raise P0PresentedAContextFrameError(f"{label} must keep {field}=false")


_ADAPTER_FIELDS = frozenset({"adapter_id", "source_profile"})
_STRATUM_FIELDS = frozenset({"source_profile", "platform_scope", "utc_day", "quota"})
_SCOPE_FIELDS = frozenset({
    "schema_version", "record_origin", "scope_id", "created_at", "frame_cutoff",
    "adapter_profile_map", "strata", "upstream_source_sampling_plan_raw_sha256",
    "upstream_bridge_inventory_raw_sha256", "context_enumeration_policy_sha256",
    "eligibility_policy_sha256", "rights_policy_sha256", "strata_policy_sha256",
    "future_seed_spec_sha256", "expected_per_profile_quota", "expected_total_quota",
    "selection_algorithm", "labels_observed", "semantic_truth_fields_used",
    "annotation_started", "action_applied", "operational_effect", "artifact_sha256",
})


def _validate_scope(value: Any) -> dict[str, Any]:
    row = _strict(value, _SCOPE_FIELDS, "scope")
    if row["schema_version"] != SCOPE_SCHEMA or row["record_origin"] != EXAMPLE_ORIGIN:
        raise P0PresentedAContextFrameError("scope schema/origin mismatch")
    _identifier(row["scope_id"], "scope_id")
    if _timestamp(row["created_at"], "created_at") > _timestamp(row["frame_cutoff"], "frame_cutoff"):
        raise P0PresentedAContextFrameError("scope created_at follows cutoff")
    for field in (
        "upstream_source_sampling_plan_raw_sha256", "upstream_bridge_inventory_raw_sha256",
        "context_enumeration_policy_sha256", "eligibility_policy_sha256",
        "rights_policy_sha256", "strata_policy_sha256", "future_seed_spec_sha256",
    ):
        _sha(row[field], field)
    if type(row["adapter_profile_map"]) is not list or not row["adapter_profile_map"]:
        raise P0PresentedAContextFrameError("adapter map must be nonempty")
    adapters = [_strict(item, _ADAPTER_FIELDS, "adapter mapping") for item in row["adapter_profile_map"]]
    for item in adapters:
        _identifier(item["adapter_id"], "adapter_id")
        if item["source_profile"] not in SOURCE_PROFILES:
            raise P0PresentedAContextFrameError("adapter profile is invalid")
    if adapters != sorted(adapters, key=lambda item: item["adapter_id"]) or len({x["adapter_id"] for x in adapters}) != len(adapters):
        raise P0PresentedAContextFrameError("adapter map order/uniqueness mismatch")
    if type(row["strata"]) is not list or not row["strata"]:
        raise P0PresentedAContextFrameError("strata must be nonempty")
    strata = [_strict(item, _STRATUM_FIELDS, "stratum") for item in row["strata"]]
    order = {profile: index for index, profile in enumerate(SOURCE_PROFILES)}
    for item in strata:
        if item["source_profile"] not in SOURCE_PROFILES:
            raise P0PresentedAContextFrameError("stratum profile is invalid")
        _identifier(item["platform_scope"], "platform_scope")
        _day(item["utc_day"])
        _integer(item["quota"], "quota", 1)
    key = lambda item: (order[item["source_profile"]], item["platform_scope"], item["utc_day"])
    keys = [(x["source_profile"], x["platform_scope"], x["utc_day"]) for x in strata]
    if strata != sorted(strata, key=key) or len(set(keys)) != len(keys):
        raise P0PresentedAContextFrameError("stratum order/uniqueness mismatch")
    quotas = Counter()
    for item in strata:
        quotas[item["source_profile"]] += item["quota"]
    if dict(quotas) != {profile: EXPECTED_PER_PROFILE_QUOTA for profile in SOURCE_PROFILES}:
        raise P0PresentedAContextFrameError("strata must total quota 5 per profile")
    if _integer(row["expected_per_profile_quota"], "expected_per_profile_quota", 1) != EXPECTED_PER_PROFILE_QUOTA or _integer(row["expected_total_quota"], "expected_total_quota", 1) != EXPECTED_TOTAL_QUOTA:
        raise P0PresentedAContextFrameError("scope quota constants mismatch")
    if row["selection_algorithm"] != SELECTION_ALGORITHM:
        raise P0PresentedAContextFrameError("selection algorithm mismatch")
    for field in ("labels_observed", "semantic_truth_fields_used", "annotation_started", "action_applied"):
        if _boolean(row[field], field) is not False:
            raise P0PresentedAContextFrameError(f"scope must keep {field}=false")
    if row["operational_effect"] != OPERATIONAL_EFFECT:
        raise P0PresentedAContextFrameError("scope must be shadow-only")
    _self_hash(row, "artifact_sha256", "scope")
    return row


def validate_scope_bytes(raw: bytes) -> dict[str, Any]:
    return _validate_scope(_object(raw, "scope", MAX_SCOPE_BYTES))


def build_scope_bytes(material: Mapping[str, Any]) -> bytes:
    raw = canonical_file_bytes(with_self_hash(material))
    validate_scope_bytes(raw)
    return raw


_CANDIDATE_FIELDS = frozenset({
    "upstream_frame_candidate_id", "registry_record_id", "adapter_id", "platform_scope",
    "community_scope_commitment_sha256", "content_fingerprint", "payload_sha256",
    "surface_start", "surface_end", "surface_sha256", "context_observed_at",
    "source_published_at", "capture_receipt_sha256", "source_claim_set_sha256",
    "presented_rights_policy_assessed", "presented_collection_allowed",
    "presented_takedown_status", "presented_source_binding_verified",
})
_CENSUS_FIELDS = frozenset({
    "schema_version", "record_origin", "enumeration_sequence", "candidate_id",
    "context_unit_sha256", *_CANDIDATE_FIELDS, "source_profile", "utc_day",
    "eligibility_status", "exclusion_reason_codes", "action_applied",
    "operational_effect", "row_sha256",
})


def context_unit_sha256(row: Mapping[str, Any]) -> str:
    return canonical_sha256({
        "domain": CONTEXT_UNIT_DOMAIN,
        "registry_record_id": row["registry_record_id"],
        "platform_scope": row["platform_scope"],
        "community_scope_commitment_sha256": row["community_scope_commitment_sha256"],
        "content_fingerprint": row["content_fingerprint"],
        "surface_start": row["surface_start"],
        "surface_end": row["surface_end"],
        "surface_sha256": row["surface_sha256"],
    })


def candidate_id_from_context_unit(unit_sha256: str) -> str:
    unit = _sha(unit_sha256, "context_unit_sha256")
    return "P0:A:FRAME:CANDIDATE:" + canonical_sha256({"domain": CANDIDATE_ID_DOMAIN, "context_unit_sha256": unit})


def stratum_id(source_profile: str, platform_scope: str, utc_day: str) -> str:
    if source_profile not in SOURCE_PROFILES:
        raise P0PresentedAContextFrameError("source profile is invalid")
    platform_scope = _identifier(platform_scope, "platform_scope")
    utc_day = _day(utc_day)
    return "P0:A:FRAME:STRATUM:" + canonical_sha256({
        "domain": STRATUM_ID_DOMAIN, "source_profile": source_profile,
        "platform_scope": platform_scope, "utc_day": utc_day,
    })


def _adapter_map(scope: Mapping[str, Any]) -> dict[str, str]:
    return {row["adapter_id"]: row["source_profile"] for row in scope["adapter_profile_map"]}


def _base_candidate(value: Any, scope: Mapping[str, Any], label: str) -> dict[str, Any]:
    row = _strict(value, _CANDIDATE_FIELDS, label)
    for field in ("upstream_frame_candidate_id", "registry_record_id", "adapter_id", "platform_scope"):
        _identifier(row[field], field)
    if row["adapter_id"] not in _adapter_map(scope):
        raise P0PresentedAContextFrameError("candidate adapter is outside sealed map")
    for field in (
        "community_scope_commitment_sha256", "content_fingerprint", "payload_sha256",
        "surface_sha256", "capture_receipt_sha256", "source_claim_set_sha256",
    ):
        _sha(row[field], field)
    start = _integer(row["surface_start"], "surface_start")
    end = _integer(row["surface_end"], "surface_end", 1)
    if start >= end:
        raise P0PresentedAContextFrameError("surface span must be nonempty")
    observed = _timestamp(row["context_observed_at"], "context_observed_at")
    published = _timestamp(row["source_published_at"], "source_published_at")
    if published > observed or observed > _timestamp(scope["frame_cutoff"], "frame_cutoff"):
        raise P0PresentedAContextFrameError("candidate chronology mismatch")
    for field in (
        "presented_rights_policy_assessed", "presented_collection_allowed",
        "presented_source_binding_verified",
    ):
        _boolean(row[field], field)
    if row["presented_takedown_status"] not in TAKEDOWN_STATUSES:
        raise P0PresentedAContextFrameError("takedown status is invalid")
    return row


def _reasons(row: Mapping[str, Any]) -> list[str]:
    result: list[str] = []
    if row["presented_rights_policy_assessed"] is not True:
        result.append("RIGHTS_POLICY_NOT_ASSESSED")
    if row["presented_collection_allowed"] is not True:
        result.append("COLLECTION_NOT_ALLOWED")
    if row["presented_takedown_status"] != "ACTIVE":
        result.append("TAKEDOWN_NOT_ACTIVE")
    if row["presented_source_binding_verified"] is not True:
        result.append("SOURCE_BINDING_NOT_VERIFIED")
    return result


def _census_row(item: Mapping[str, Any], sequence: int) -> dict[str, Any]:
    reasons = _reasons(item)
    return with_self_hash({
        "schema_version": CENSUS_ROW_SCHEMA, "record_origin": EXAMPLE_ORIGIN,
        "enumeration_sequence": sequence, "candidate_id": item["candidate_id"],
        "context_unit_sha256": item["context_unit_sha256"],
        **{field: item[field] for field in _CANDIDATE_FIELDS},
        "source_profile": item["source_profile"], "utc_day": item["utc_day"],
        "eligibility_status": "EXCLUDED" if reasons else "ELIGIBLE",
        "exclusion_reason_codes": reasons, "action_applied": False,
        "operational_effect": OPERATIONAL_EFFECT,
    }, "row_sha256")


def build_census_bytes(scope_raw: bytes, candidate_rows: Sequence[Mapping[str, Any]]) -> bytes:
    scope = validate_scope_bytes(scope_raw)
    if isinstance(candidate_rows, (str, bytes, bytearray)) or not isinstance(candidate_rows, Sequence) or not candidate_rows or len(candidate_rows) > MAX_CENSUS_ROWS:
        raise P0PresentedAContextFrameError("candidate_rows must be a bounded nonempty sequence")
    prepared: list[dict[str, Any]] = []
    seen_units: set[str] = set()
    conservative_census_bytes = 0
    for index, value in enumerate(candidate_rows, start=1):
        if index > MAX_CENSUS_ROWS:
            raise P0PresentedAContextFrameError(
                "candidate_rows exceeds the row budget"
            )
        base = _base_candidate(value, scope, f"candidate {index}")
        unit = context_unit_sha256(base)
        if unit in seen_units:
            raise P0PresentedAContextFrameError(
                "duplicate logical A-context unit is forbidden"
            )
        seen_units.add(unit)
        profile = _adapter_map(scope)[base["adapter_id"]]
        item = {**base, "context_unit_sha256": unit, "candidate_id": candidate_id_from_context_unit(unit), "source_profile": profile, "utc_day": base["source_published_at"][:10]}
        # Sequence 1 is a byte-length lower bound for every positive canonical
        # enumeration sequence.  This lets clearly oversized input fail before
        # retaining and sorting the entire candidate population; the exact
        # post-sort check below remains authoritative at the boundary.
        conservative_row_bytes = len(canonical_file_bytes(_census_row(item, 1)))
        if conservative_row_bytes > MAX_CENSUS_ROW_BYTES:
            raise P0PresentedAContextFrameError(
                "census row byte budget exceeded"
            )
        if conservative_row_bytes > MAX_CENSUS_BYTES - conservative_census_bytes:
            raise P0PresentedAContextFrameError(
                "census conservative cumulative byte budget exceeded"
            )
        conservative_census_bytes += conservative_row_bytes
        prepared.append(item)
    prepared.sort(key=lambda row: row["candidate_id"])
    output = bytearray()
    for sequence, item in enumerate(prepared, start=1):
        row = _census_row(item, sequence)
        encoded = canonical_file_bytes(row)
        if len(encoded) > MAX_CENSUS_ROW_BYTES:
            raise P0PresentedAContextFrameError(
                "census row byte budget exceeded"
            )
        if len(encoded) > MAX_CENSUS_BYTES - len(output):
            raise P0PresentedAContextFrameError(
                "census cumulative byte budget exceeded"
            )
        output.extend(encoded)
    raw = bytes(output)
    del output
    del prepared
    validate_census_bytes(raw, scope_raw)
    return raw


def validate_census_bytes(raw: bytes, scope_raw: bytes) -> list[dict[str, Any]]:
    scope = validate_scope_bytes(scope_raw)
    fixed_strata = {(x["source_profile"], x["platform_scope"], x["utc_day"]) for x in scope["strata"]}

    def validate_row(value: dict[str, Any], index: int) -> dict[str, Any]:
        row = _strict(value, _CENSUS_FIELDS, f"census row {index}")
        if row["schema_version"] != CENSUS_ROW_SCHEMA or row["record_origin"] != EXAMPLE_ORIGIN or _integer(row["enumeration_sequence"], "enumeration_sequence", 1) != index:
            raise P0PresentedAContextFrameError("census schema/origin/sequence mismatch")
        base = _base_candidate({field: row[field] for field in _CANDIDATE_FIELDS}, scope, f"census row {index} base")
        unit = context_unit_sha256(base)
        profile = _adapter_map(scope)[base["adapter_id"]]
        day = base["source_published_at"][:10]
        if row["context_unit_sha256"] != unit or row["candidate_id"] != candidate_id_from_context_unit(unit) or row["source_profile"] != profile or row["utc_day"] != day:
            raise P0PresentedAContextFrameError("census derived binding mismatch")
        if (profile, base["platform_scope"], day) not in fixed_strata:
            raise P0PresentedAContextFrameError("candidate is outside fixed strata")
        reasons = _reasons(base)
        if row["exclusion_reason_codes"] != reasons or row["eligibility_status"] != ("EXCLUDED" if reasons else "ELIGIBLE"):
            raise P0PresentedAContextFrameError("eligibility must be recomputed")
        if row["action_applied"] is not False or row["operational_effect"] != OPERATIONAL_EFFECT:
            raise P0PresentedAContextFrameError("census must remain shadow-only")
        _self_hash(row, "row_sha256", "census row")
        return row

    rows = _jsonl(raw, validate_row)
    if rows != sorted(rows, key=lambda row: row["candidate_id"]):
        raise P0PresentedAContextFrameError("census order mismatch")
    if len({row["candidate_id"] for row in rows}) != len(rows) or len({row["context_unit_sha256"] for row in rows}) != len(rows):
        raise P0PresentedAContextFrameError("duplicate A-context candidate/unit")
    return rows


_POP_FIELDS = frozenset({"source_profile", "platform_scope", "utc_day", "stratum_id", "N_h", "n_h"})
_FRAME_FIELDS = frozenset({
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


def _population(scope: Mapping[str, Any], rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    counts = Counter((row["source_profile"], row["platform_scope"], row["utc_day"]) for row in rows if row["eligibility_status"] == "ELIGIBLE")
    return [{
        "source_profile": item["source_profile"], "platform_scope": item["platform_scope"],
        "utc_day": item["utc_day"], "stratum_id": stratum_id(item["source_profile"], item["platform_scope"], item["utc_day"]),
        "N_h": counts[(item["source_profile"], item["platform_scope"], item["utc_day"])], "n_h": item["quota"],
    } for item in scope["strata"]]


def build_frame_manifest_bytes(scope_raw: bytes, census_raw: bytes, *, frame_sealed_at: str) -> bytes:
    scope = validate_scope_bytes(scope_raw)
    rows = validate_census_bytes(census_raw, scope_raw)
    sealed = _timestamp(frame_sealed_at, "frame_sealed_at")
    if sealed <= _timestamp(scope["frame_cutoff"], "frame_cutoff"):
        raise P0PresentedAContextFrameError("frame seal must follow cutoff")
    eligible = [row for row in rows if row["eligibility_status"] == "ELIGIBLE"]
    excluded = [row for row in rows if row["eligibility_status"] == "EXCLUDED"]
    material: dict[str, Any] = {
        "schema_version": FRAME_MANIFEST_SCHEMA, "record_origin": EXAMPLE_ORIGIN,
        "scope_sha256": scope["artifact_sha256"], "frame_sealed_at": frame_sealed_at,
        "census_byte_count": len(census_raw), "census_raw_sha256": raw_sha256(census_raw),
        "census_row_count": len(rows), "eligible_candidate_count": len(eligible),
        "excluded_candidate_count": len(excluded),
        "eligible_sampling_units_sha256": canonical_sha256([row["context_unit_sha256"] for row in eligible]),
        "excluded_candidates_sha256": canonical_sha256([row["candidate_id"] for row in excluded]),
        "stratum_populations": _population(scope, rows),
        "presented_census_serialization_verified": True, "presented_serialization_only": True,
        **{field: False for field in FALSE_AUTHORITY_FIELDS}, "gate_status": GATE_STATUS,
        "actual_a_context_review_count": 0, "actual_surplus_review_count": 0,
        "statistical_denominator_contribution": "NONE", "metric_status": METRIC_STATUS,
        "inferential_metrics_allowed": False, "complete_case_metrics_allowed": False,
        "action_applied": False, "operational_effect": OPERATIONAL_EFFECT,
    }
    raw = canonical_file_bytes(with_self_hash(material))
    validate_frame_manifest_bytes(raw, scope_raw, census_raw)
    return raw


def validate_frame_manifest_bytes(frame_raw: bytes, scope_raw: bytes, census_raw: bytes) -> dict[str, Any]:
    scope = validate_scope_bytes(scope_raw)
    rows = validate_census_bytes(census_raw, scope_raw)
    row = _strict(_object(frame_raw, "frame manifest", MAX_SCOPE_BYTES), _FRAME_FIELDS, "frame manifest")
    if row["schema_version"] != FRAME_MANIFEST_SCHEMA or row["record_origin"] != EXAMPLE_ORIGIN or row["scope_sha256"] != scope["artifact_sha256"]:
        raise P0PresentedAContextFrameError("frame schema/origin/scope mismatch")
    eligible = [x for x in rows if x["eligibility_status"] == "ELIGIBLE"]
    excluded = [x for x in rows if x["eligibility_status"] == "EXCLUDED"]
    expected = {
        "census_byte_count": len(census_raw), "census_raw_sha256": raw_sha256(census_raw),
        "census_row_count": len(rows), "eligible_candidate_count": len(eligible),
        "excluded_candidate_count": len(excluded),
        "eligible_sampling_units_sha256": canonical_sha256([x["context_unit_sha256"] for x in eligible]),
        "excluded_candidates_sha256": canonical_sha256([x["candidate_id"] for x in excluded]),
        "stratum_populations": _population(scope, rows),
    }
    if any(row[key] != value for key, value in expected.items()):
        raise P0PresentedAContextFrameError("frame census accounting mismatch")
    for field in ("census_byte_count", "census_row_count", "eligible_candidate_count", "excluded_candidate_count"):
        _integer(row[field], field)
    if type(row["stratum_populations"]) is not list:
        raise P0PresentedAContextFrameError("frame populations must be a list")
    for item in row["stratum_populations"]:
        pop = _strict(item, _POP_FIELDS, "stratum population")
        _integer(pop["N_h"], "N_h")
        _integer(pop["n_h"], "n_h", 1)
    if _timestamp(row["frame_sealed_at"], "frame_sealed_at") <= _timestamp(scope["frame_cutoff"], "frame_cutoff"):
        raise P0PresentedAContextFrameError("frame chronology mismatch")
    if row["presented_census_serialization_verified"] is not True or row["presented_serialization_only"] is not True:
        raise P0PresentedAContextFrameError("frame presented scope mismatch")
    _false_fields(row, "frame")
    if (
        _integer(row["actual_a_context_review_count"], "actual_a_context_review_count") != 0
        or _integer(row["actual_surplus_review_count"], "actual_surplus_review_count") != 0
        or row["statistical_denominator_contribution"] != "NONE"
        or row["metric_status"] != METRIC_STATUS
        or row["inferential_metrics_allowed"] is not False
        or row["complete_case_metrics_allowed"] is not False
    ):
        raise P0PresentedAContextFrameError("frame must contribute no reviews or metrics")
    if row["gate_status"] != GATE_STATUS or row["action_applied"] is not False or row["operational_effect"] != OPERATIONAL_EFFECT:
        raise P0PresentedAContextFrameError("frame gate/effect mismatch")
    _self_hash(row, "artifact_sha256", "frame")
    return row


_SEED_FIELDS = frozenset({
    "schema_version", "record_origin", "seed_receipt_id", "scope_sha256",
    "frame_manifest_sha256", "census_raw_sha256", "future_seed_spec_sha256",
    "revealed_seed_sha256", "frame_owner_precommit_sha256", "frame_owner_precommitted_at",
    "revealed_at", "owner_authority_verified", "seed_authority_verified",
    "action_applied", "operational_effect", "artifact_sha256",
})


def build_seed_receipt_bytes(material: Mapping[str, Any], scope_raw: bytes, frame_raw: bytes, census_raw: bytes) -> bytes:
    raw = canonical_file_bytes(with_self_hash(material))
    validate_seed_receipt_bytes(raw, scope_raw, frame_raw, census_raw)
    return raw


def validate_seed_receipt_bytes(seed_raw: bytes, scope_raw: bytes, frame_raw: bytes, census_raw: bytes) -> dict[str, Any]:
    scope = validate_scope_bytes(scope_raw)
    frame = validate_frame_manifest_bytes(frame_raw, scope_raw, census_raw)
    row = _strict(_object(seed_raw, "seed receipt", MAX_SEED_BYTES), _SEED_FIELDS, "seed receipt")
    if row["schema_version"] != SEED_RECEIPT_SCHEMA or row["record_origin"] != EXAMPLE_ORIGIN:
        raise P0PresentedAContextFrameError("seed schema/origin mismatch")
    _identifier(row["seed_receipt_id"], "seed_receipt_id")
    expected = {
        "scope_sha256": scope["artifact_sha256"], "frame_manifest_sha256": frame["artifact_sha256"],
        "census_raw_sha256": raw_sha256(census_raw), "future_seed_spec_sha256": scope["future_seed_spec_sha256"],
    }
    if any(row[key] != value for key, value in expected.items()):
        raise P0PresentedAContextFrameError("seed predecessor binding mismatch")
    _sha(row["revealed_seed_sha256"], "revealed_seed_sha256")
    _sha(row["frame_owner_precommit_sha256"], "frame_owner_precommit_sha256")
    pre = _timestamp(row["frame_owner_precommitted_at"], "frame_owner_precommitted_at")
    reveal = _timestamp(row["revealed_at"], "revealed_at")
    if pre <= _timestamp(frame["frame_sealed_at"], "frame_sealed_at") or reveal <= pre:
        raise P0PresentedAContextFrameError("seed chronology mismatch")
    if row["owner_authority_verified"] is not False or row["seed_authority_verified"] is not False or row["action_applied"] is not False or row["operational_effect"] != OPERATIONAL_EFFECT:
        raise P0PresentedAContextFrameError("seed authority/effect must remain false")
    _self_hash(row, "artifact_sha256", "seed receipt")
    return row


_ITEM_FIELDS = frozenset({
    "input_sequence", "candidate_id", "context_unit_sha256", "upstream_frame_candidate_id",
    "registry_record_id", "source_profile", "platform_scope", "utc_day", "stratum_id",
    "rank_sha256", "N_h", "n_h", "inclusion_probability_numerator",
    "inclusion_probability_denominator",
})
_PLAN_FIELDS = frozenset({
    "schema_version", "record_origin", "scope_sha256", "seed_receipt_sha256",
    "frame_manifest_sha256", "selection_algorithm", "derived_seed_sha256",
    "without_replacement", "spill_allowed", "replacement_allowed", "input_count",
    "per_profile_counts", "selected_contexts", "selected_context_set_sha256",
    "eligible_surplus_count", "eligible_surplus_contexts", "eligible_surplus_set_sha256",
    "eligible_partition_sha256", "selection_sealed_at", "presented_serialization_only",
    *FALSE_AUTHORITY_FIELDS, "gate_status", "action_applied", "operational_effect",
    "actual_a_context_review_count", "actual_surplus_review_count",
    "statistical_denominator_contribution", "metric_status",
    "inferential_metrics_allowed", "complete_case_metrics_allowed",
    "artifact_sha256",
})


def _rank(seed: str, eligible_sha: str, sid: str, unit: str) -> str:
    return canonical_sha256({"domain": RANK_DOMAIN, "derived_seed_sha256": seed, "eligible_sampling_units_sha256": eligible_sha, "stratum_id": sid, "context_unit_sha256": unit})


def _derive_seed(scope: Mapping[str, Any], frame: Mapping[str, Any], seed: Mapping[str, Any]) -> str:
    return canonical_sha256({
        "domain": SEED_DERIVATION_DOMAIN, "scope_sha256": scope["artifact_sha256"],
        "frame_manifest_sha256": frame["artifact_sha256"],
        "future_seed_spec_sha256": scope["future_seed_spec_sha256"],
        "revealed_seed_sha256": seed["revealed_seed_sha256"],
        "frame_owner_precommit_sha256": seed["frame_owner_precommit_sha256"],
    })


def _plan_items(scope: Mapping[str, Any], rows: Sequence[Mapping[str, Any]], seed_value: str, eligible_sha: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    selected: list[dict[str, Any]] = []
    surplus: list[dict[str, Any]] = []
    strata = {(x["source_profile"], x["platform_scope"], x["utc_day"]): x for x in scope["strata"]}
    eligible = [row for row in rows if row["eligibility_status"] == "ELIGIBLE"]
    sequence = 1
    for key, spec in strata.items():
        members = [row for row in eligible if (row["source_profile"], row["platform_scope"], row["utc_day"]) == key]
        if len(members) < spec["quota"]:
            raise P0PresentedAContextFrameError("A-context stratum underfill; spill is forbidden")
        sid = stratum_id(*key)
        ranked = sorted((( _rank(seed_value, eligible_sha, sid, row["context_unit_sha256"]), row) for row in members), key=lambda pair: (pair[0], pair[1]["candidate_id"]))
        fraction = Fraction(spec["quota"], len(members))
        for offset, (rank, row) in enumerate(ranked):
            item = {
                "input_sequence": sequence if offset < spec["quota"] else 0,
                "candidate_id": row["candidate_id"], "context_unit_sha256": row["context_unit_sha256"],
                "upstream_frame_candidate_id": row["upstream_frame_candidate_id"],
                "registry_record_id": row["registry_record_id"], "source_profile": row["source_profile"],
                "platform_scope": row["platform_scope"], "utc_day": row["utc_day"], "stratum_id": sid,
                "rank_sha256": rank, "N_h": len(members), "n_h": spec["quota"],
                "inclusion_probability_numerator": fraction.numerator,
                "inclusion_probability_denominator": fraction.denominator,
            }
            if offset < spec["quota"]:
                selected.append(item)
                sequence += 1
            else:
                surplus.append(item)
    surplus.sort(key=lambda item: (item["source_profile"], item["platform_scope"], item["utc_day"], item["rank_sha256"], item["candidate_id"]))
    return selected, surplus


def build_sampling_plan_bytes(scope_raw: bytes, census_raw: bytes, frame_raw: bytes, seed_raw: bytes, *, selection_sealed_at: str) -> bytes:
    scope = validate_scope_bytes(scope_raw)
    rows = validate_census_bytes(census_raw, scope_raw)
    frame = validate_frame_manifest_bytes(frame_raw, scope_raw, census_raw)
    seed = validate_seed_receipt_bytes(seed_raw, scope_raw, frame_raw, census_raw)
    if _timestamp(selection_sealed_at, "selection_sealed_at") <= _timestamp(seed["revealed_at"], "revealed_at"):
        raise P0PresentedAContextFrameError("selection must follow seed reveal")
    derived = _derive_seed(scope, frame, seed)
    selected, surplus = _plan_items(scope, rows, derived, frame["eligible_sampling_units_sha256"])
    profile_counts = {profile: sum(x["source_profile"] == profile for x in selected) for profile in SOURCE_PROFILES}
    partition = sorted([x["candidate_id"] for x in selected + surplus])
    material: dict[str, Any] = {
        "schema_version": SAMPLING_PLAN_SCHEMA, "record_origin": EXAMPLE_ORIGIN,
        "scope_sha256": scope["artifact_sha256"], "seed_receipt_sha256": seed["artifact_sha256"],
        "frame_manifest_sha256": frame["artifact_sha256"], "selection_algorithm": SELECTION_ALGORITHM,
        "derived_seed_sha256": derived, "without_replacement": True, "spill_allowed": False,
        "replacement_allowed": False, "input_count": len(selected), "per_profile_counts": profile_counts,
        "selected_contexts": selected, "selected_context_set_sha256": canonical_sha256(selected),
        "eligible_surplus_count": len(surplus), "eligible_surplus_contexts": surplus,
        "eligible_surplus_set_sha256": canonical_sha256(surplus),
        "eligible_partition_sha256": canonical_sha256(partition),
        "selection_sealed_at": selection_sealed_at, "presented_serialization_only": True,
        **{field: False for field in FALSE_AUTHORITY_FIELDS}, "gate_status": GATE_STATUS,
        "actual_a_context_review_count": 0, "actual_surplus_review_count": 0,
        "statistical_denominator_contribution": "NONE", "metric_status": METRIC_STATUS,
        "inferential_metrics_allowed": False, "complete_case_metrics_allowed": False,
        "action_applied": False, "operational_effect": OPERATIONAL_EFFECT,
    }
    raw = canonical_file_bytes(with_self_hash(material))
    validate_sampling_plan_bytes(raw, scope_raw, census_raw, seed_raw, frame_raw)
    return raw


def validate_sampling_plan_bytes(plan_raw: bytes, scope_raw: bytes, census_raw: bytes, seed_raw: bytes, frame_raw: bytes) -> dict[str, Any]:
    scope = validate_scope_bytes(scope_raw)
    rows = validate_census_bytes(census_raw, scope_raw)
    frame = validate_frame_manifest_bytes(frame_raw, scope_raw, census_raw)
    seed = validate_seed_receipt_bytes(seed_raw, scope_raw, frame_raw, census_raw)
    row = _strict(_object(plan_raw, "sampling plan", MAX_CENSUS_BYTES), _PLAN_FIELDS, "sampling plan")
    if row["schema_version"] != SAMPLING_PLAN_SCHEMA or row["record_origin"] != EXAMPLE_ORIGIN:
        raise P0PresentedAContextFrameError("plan schema/origin mismatch")
    for field in ("without_replacement", "spill_allowed", "replacement_allowed"):
        _boolean(row[field], field)
    _integer(row["input_count"], "input_count")
    _integer(row["eligible_surplus_count"], "eligible_surplus_count")
    if type(row["per_profile_counts"]) is not dict or set(row["per_profile_counts"]) != set(SOURCE_PROFILES):
        raise P0PresentedAContextFrameError("per-profile count fields mismatch")
    for profile, count in row["per_profile_counts"].items():
        _integer(count, f"per_profile_counts.{profile}")
    if type(row["selected_contexts"]) is not list or type(row["eligible_surplus_contexts"]) is not list:
        raise P0PresentedAContextFrameError("plan item inventories must be lists")
    for item in row["selected_contexts"] + row["eligible_surplus_contexts"]:
        submitted = _strict(item, _ITEM_FIELDS, "submitted plan item")
        for field in (
            "input_sequence", "N_h", "n_h", "inclusion_probability_numerator",
            "inclusion_probability_denominator",
        ):
            _integer(submitted[field], field)
        for field in ("candidate_id", "upstream_frame_candidate_id", "registry_record_id", "source_profile", "platform_scope", "utc_day", "stratum_id"):
            _identifier(submitted[field], field)
        for field in ("context_unit_sha256", "rank_sha256"):
            _sha(submitted[field], field)
        if submitted["N_h"] < 1 or submitted["n_h"] < 1 or submitted["n_h"] > submitted["N_h"]:
            raise P0PresentedAContextFrameError("submitted plan denominator mismatch")
        if submitted["inclusion_probability_numerator"] < 1 or submitted["inclusion_probability_denominator"] < 1:
            raise P0PresentedAContextFrameError("submitted inclusion probability mismatch")
    derived = _derive_seed(scope, frame, seed)
    selected, surplus = _plan_items(scope, rows, derived, frame["eligible_sampling_units_sha256"])
    expected_profiles = {profile: EXPECTED_PER_PROFILE_QUOTA for profile in SOURCE_PROFILES}
    eligible_ids = sorted(x["candidate_id"] for x in rows if x["eligibility_status"] == "ELIGIBLE")
    expected = {
        "scope_sha256": scope["artifact_sha256"], "seed_receipt_sha256": seed["artifact_sha256"],
        "frame_manifest_sha256": frame["artifact_sha256"], "selection_algorithm": SELECTION_ALGORITHM,
        "derived_seed_sha256": derived, "without_replacement": True, "spill_allowed": False,
        "replacement_allowed": False, "input_count": EXPECTED_TOTAL_QUOTA,
        "per_profile_counts": expected_profiles, "selected_contexts": selected,
        "selected_context_set_sha256": canonical_sha256(selected),
        "eligible_surplus_count": len(surplus), "eligible_surplus_contexts": surplus,
        "eligible_surplus_set_sha256": canonical_sha256(surplus),
        "eligible_partition_sha256": canonical_sha256(eligible_ids),
    }
    if any(row[key] != value for key, value in expected.items()):
        raise P0PresentedAContextFrameError("sampling plan recomputation mismatch")
    for item in row["selected_contexts"] + row["eligible_surplus_contexts"]:
        if math.gcd(item["inclusion_probability_numerator"], item["inclusion_probability_denominator"]) != 1:
            raise P0PresentedAContextFrameError("inclusion probability must be reduced")
    if {x["candidate_id"] for x in selected} & {x["candidate_id"] for x in surplus} or sorted(x["candidate_id"] for x in selected + surplus) != eligible_ids:
        raise P0PresentedAContextFrameError("selected/surplus is not exact eligible partition")
    if _timestamp(row["selection_sealed_at"], "selection_sealed_at") <= _timestamp(seed["revealed_at"], "revealed_at"):
        raise P0PresentedAContextFrameError("selection chronology mismatch")
    if row["presented_serialization_only"] is not True:
        raise P0PresentedAContextFrameError("plan scope mismatch")
    _false_fields(row, "plan")
    if (
        _integer(row["actual_a_context_review_count"], "actual_a_context_review_count") != 0
        or _integer(row["actual_surplus_review_count"], "actual_surplus_review_count") != 0
        or row["statistical_denominator_contribution"] != "NONE"
        or row["metric_status"] != METRIC_STATUS
        or row["inferential_metrics_allowed"] is not False
        or row["complete_case_metrics_allowed"] is not False
    ):
        raise P0PresentedAContextFrameError("plan must contribute no reviews or metrics")
    if row["gate_status"] != GATE_STATUS or row["action_applied"] is not False or row["operational_effect"] != OPERATIONAL_EFFECT:
        raise P0PresentedAContextFrameError("plan gate/effect mismatch")
    _self_hash(row, "artifact_sha256", "plan")
    return row


COMPONENT_MANIFEST = {
    "component": "p0_presented_a_context_full_frame_v1_contract",
    "schemas": [SCOPE_SCHEMA, CENSUS_ROW_SCHEMA, FRAME_MANIFEST_SCHEMA, SEED_RECEIPT_SCHEMA, SAMPLING_PLAN_SCHEMA],
    "source_profiles": list(SOURCE_PROFILES), "expected_per_profile_quota": EXPECTED_PER_PROFILE_QUOTA,
    "expected_total_quota": EXPECTED_TOTAL_QUOTA, "selection_algorithm": SELECTION_ALGORITHM,
    "selected_surplus_exact_partition": True, "truth_or_annotation_fields_allowed": False,
    "false_authority_fields": list(FALSE_AUTHORITY_FIELDS), "gate_status": GATE_STATUS,
    "operational_effect": OPERATIONAL_EFFECT,
}
COMPONENT_MANIFEST_SHA256 = canonical_sha256(COMPONENT_MANIFEST)


__all__ = [
    "CANDIDATE_ID_DOMAIN", "CENSUS_ROW_SCHEMA", "COMPONENT_MANIFEST",
    "COMPONENT_MANIFEST_SHA256", "CONTEXT_UNIT_DOMAIN", "EXAMPLE_ORIGIN",
    "EXPECTED_PER_PROFILE_QUOTA", "EXPECTED_TOTAL_QUOTA", "FALSE_AUTHORITY_FIELDS",
    "FRAME_MANIFEST_SCHEMA", "GATE_STATUS", "METRIC_STATUS", "OPERATIONAL_EFFECT",
    "P0PresentedAContextFrameError", "RANK_DOMAIN", "SAMPLING_PLAN_SCHEMA",
    "SCOPE_SCHEMA", "SEED_DERIVATION_DOMAIN", "SEED_RECEIPT_SCHEMA",
    "SELECTION_ALGORITHM", "SOURCE_PROFILES", "build_census_bytes",
    "build_frame_manifest_bytes", "build_sampling_plan_bytes", "build_scope_bytes",
    "build_seed_receipt_bytes", "candidate_id_from_context_unit", "canonical_bytes",
    "canonical_file_bytes", "canonical_sha256", "context_unit_sha256", "raw_sha256",
    "stratum_id", "validate_census_bytes", "validate_frame_manifest_bytes",
    "validate_sampling_plan_bytes", "validate_scope_bytes", "validate_seed_receipt_bytes",
    "with_self_hash",
]
