"""Independent parent replay for full-eligible sampling-frame V2 artifacts.

No producer or ``llm_batch`` module is imported.  The public schemas, limits,
manifest and deterministic behavior are pinned as literals, then exact raw
scope/census/seed bytes are replayed.  A pass proves presented serialization
replay only; every authority, runtime, isolation and code-identity claim stays
false.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
import re
import unicodedata
from typing import Any, Mapping, Sequence


VALIDATION_RECEIPT_SCHEMA = "p0_full_eligible_frame_v2_parent_receipt_v1"
GATE_STATUS = "PRESENTED_FRAME_PARENT_REPLAY_PASS_ALL_AUTHORITY_NO_GO"
SCOPE_SCHEMA = "p0_full_eligible_sampling_scope_v2"
SEED_RECEIPT_SCHEMA = "p0_sampling_seed_receipt_v2"
CENSUS_ROW_SCHEMA = "p0_full_eligible_census_row_v2"
FRAME_MANIFEST_SCHEMA = "p0_full_eligible_frame_manifest_v2"
SAMPLING_PLAN_SCHEMA = "p0_deterministic_stratified_srswor_plan_v2"
EXAMPLE_ORIGIN = "ACTUAL_SCHEMA_CONTRACT_EXAMPLE_ONLY"
OPERATIONAL_EFFECT = "NONE_SHADOW_ONLY"
SOURCE_PROFILES = (
    "OFFICIAL_STRUCTURED",
    "COMMUNITY_STRUCTURED",
    "MEDIA_OCR",
    "GENERIC_FALLBACK",
)
EXPECTED_PER_PROFILE_QUOTA = 10
EXPECTED_TOTAL_QUOTA = 40
SELECTION_ALGORITHM = "SHA256_STRATIFIED_SRSWOR_WITHOUT_REPLACEMENT_V2"
LINEAGE_POLICY = "CANONICAL_MIN_ROOT_ONE_UNIT_PER_GROUP_V2"
RANK_DOMAIN = "P0_FULL_ELIGIBLE_FRAME_V2_RANK"
SEED_DERIVATION_DOMAIN = "P0_FULL_ELIGIBLE_FRAME_V2_DERIVED_SEED"
CANDIDATE_ID_DOMAIN = "P0_FULL_ELIGIBLE_FRAME_V2_CANDIDATE_ID"
LINEAGE_UNIT_DOMAIN = "P0_FULL_ELIGIBLE_FRAME_V2_LINEAGE_UNIT"
LINEAGE_GROUP_DOMAIN = "P0_FULL_ELIGIBLE_FRAME_V2_LINEAGE_GROUP"
STRATUM_ID_DOMAIN = "P0_FULL_ELIGIBLE_FRAME_V2_STRATUM_ID"
MAX_SCOPE_BYTES = 1_000_000
MAX_SEED_RECEIPT_BYTES = 64_000
MAX_CENSUS_BYTES = 64_000_000
MAX_CENSUS_ROWS = 1_000_000
LINEAGE_ROLES = ("ROOT", "DERIVATIVE", "UNKNOWN")
TAKEDOWN_STATUSES = ("ACTIVE", "PENDING_REMOVAL", "REMOVED")
ELIGIBILITY_STATUSES = ("ELIGIBLE", "EXCLUDED")
EXCLUSION_REASON_ORDER = (
    "RIGHTS_POLICY_NOT_ASSESSED",
    "COLLECTION_NOT_ALLOWED",
    "TAKEDOWN_NOT_ACTIVE",
    "ADAPTER_CONTRACT_NOT_VERIFIED",
    "LINEAGE_DERIVATIVE",
    "LINEAGE_UNKNOWN",
    "LINEAGE_GROUP_HAS_NO_ROOT",
)
POLICY_COMMITMENT_FIELDS = (
    "enumeration_policy_sha256",
    "eligibility_policy_sha256",
    "rights_policy_sha256",
    "strata_policy_sha256",
    "future_seed_spec_sha256",
)
SELECTION_RANK_INPUT_FIELDS = (
    "domain",
    "derived_seed_sha256",
    "eligible_sampling_units_sha256",
    "stratum_id",
    "lineage_unit_sha256",
)
FALSE_AUTHORITY_FIELDS = (
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

_HEX = re.compile(r"^[0-9a-f]{64}$")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")
_PLATFORM = re.compile(r"^[a-z0-9][a-z0-9._:-]{0,127}$")
_STAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class P0FullEligibleSamplingFrameV2ParentValidationError(ValueError):
    """Independent replay rejected a presented artifact."""


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
    return hashlib.sha256(value).hexdigest()


def _with_hash(value: Mapping[str, Any], field: str = "artifact_sha256") -> dict[str, Any]:
    body = dict(value)
    body.pop(field, None)
    return {**body, field: _digest(body)}


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise P0FullEligibleSamplingFrameV2ParentValidationError(
                f"duplicate JSON key: {key}"
            )
        result[key] = value
    return result


def _constant(value: str) -> None:
    raise P0FullEligibleSamplingFrameV2ParentValidationError(
        f"non-finite number: {value}"
    )


def _object(raw: bytes, label: str, maximum: int) -> dict[str, Any]:
    if type(raw) is not bytes or not raw or len(raw) > maximum:
        raise P0FullEligibleSamplingFrameV2ParentValidationError(
            f"{label} must be bounded exact bytes"
        )
    if raw.startswith(b"\xef\xbb\xbf") or b"\r" in raw:
        raise P0FullEligibleSamplingFrameV2ParentValidationError(
            f"{label} BOM/CR forbidden"
        )
    try:
        text = raw.decode("utf-8", errors="strict")
        if unicodedata.normalize("NFC", text) != text:
            raise P0FullEligibleSamplingFrameV2ParentValidationError(
                f"{label} must be NFC"
            )
        value = json.loads(
            text, object_pairs_hook=_pairs, parse_constant=_constant
        )
    except P0FullEligibleSamplingFrameV2ParentValidationError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise P0FullEligibleSamplingFrameV2ParentValidationError(
            f"{label} invalid JSON"
        ) from exc
    if type(value) is not dict:
        raise P0FullEligibleSamplingFrameV2ParentValidationError(
            f"{label} must be canonical JSON with one LF"
        )
    try:
        expected_raw = _file(value)
    except (UnicodeEncodeError, TypeError, ValueError) as exc:
        raise P0FullEligibleSamplingFrameV2ParentValidationError(
            f"{label} contains a noncanonical JSON value"
        ) from exc
    if raw != expected_raw:
        raise P0FullEligibleSamplingFrameV2ParentValidationError(
            f"{label} must be canonical JSON with one LF"
        )
    return value


def _jsonl(raw: bytes) -> list[dict[str, Any]]:
    if type(raw) is not bytes or not raw or len(raw) > MAX_CENSUS_BYTES:
        raise P0FullEligibleSamplingFrameV2ParentValidationError(
            "census must be bounded exact bytes"
        )
    if raw.startswith(b"\xef\xbb\xbf") or b"\r" in raw:
        raise P0FullEligibleSamplingFrameV2ParentValidationError(
            "census BOM/CR forbidden"
        )
    if not raw.endswith(b"\n") or raw.endswith(b"\n\n"):
        raise P0FullEligibleSamplingFrameV2ParentValidationError(
            "census LF framing invalid"
        )
    lines = raw[:-1].split(b"\n")
    if not lines or len(lines) > MAX_CENSUS_ROWS or any(not line for line in lines):
        raise P0FullEligibleSamplingFrameV2ParentValidationError(
            "census row count invalid"
        )
    rows = [
        _object(line + b"\n", f"census row {index}", MAX_CENSUS_BYTES)
        for index, line in enumerate(lines, start=1)
    ]
    if raw != b"".join(_file(row) for row in rows):
        raise P0FullEligibleSamplingFrameV2ParentValidationError(
            "census not canonical JSONL"
        )
    return rows


def _strict(value: Any, fields: frozenset[str], label: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != fields:
        raise P0FullEligibleSamplingFrameV2ParentValidationError(
            f"{label} field set mismatch"
        )
    return value


def _text(value: Any, field: str) -> str:
    if (
        type(value) is not str
        or not value
        or value != value.strip()
        or unicodedata.normalize("NFC", value) != value
    ):
        raise P0FullEligibleSamplingFrameV2ParentValidationError(
            f"{field} invalid text"
        )
    return value


def _identifier(value: Any, field: str) -> str:
    text = _text(value, field)
    if _ID.fullmatch(text) is None:
        raise P0FullEligibleSamplingFrameV2ParentValidationError(
            f"{field} invalid identifier"
        )
    return text


def _platform(value: Any) -> str:
    text = _text(value, "platform")
    if _PLATFORM.fullmatch(text) is None:
        raise P0FullEligibleSamplingFrameV2ParentValidationError(
            "platform invalid"
        )
    return text


def _sha(value: Any, field: str) -> str:
    if type(value) is not str or _HEX.fullmatch(value) is None:
        raise P0FullEligibleSamplingFrameV2ParentValidationError(
            f"{field} invalid sha256"
        )
    return value


def _bool(value: Any, field: str) -> bool:
    if type(value) is not bool:
        raise P0FullEligibleSamplingFrameV2ParentValidationError(
            f"{field} must be exact bool"
        )
    return value


def _int(value: Any, field: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise P0FullEligibleSamplingFrameV2ParentValidationError(
            f"{field} must be exact int >= {minimum}"
        )
    return value


def _timestamp(value: Any, field: str) -> datetime:
    text = _text(value, field)
    if _STAMP.fullmatch(text) is None:
        raise P0FullEligibleSamplingFrameV2ParentValidationError(
            f"{field} invalid timestamp"
        )
    try:
        return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError as exc:
        raise P0FullEligibleSamplingFrameV2ParentValidationError(
            f"{field} invalid timestamp"
        ) from exc


def _day(value: Any) -> str:
    text = _text(value, "utc_day")
    if _DAY.fullmatch(text) is None:
        raise P0FullEligibleSamplingFrameV2ParentValidationError(
            "utc_day invalid"
        )
    try:
        datetime.strptime(text, "%Y-%m-%d")
    except ValueError as exc:
        raise P0FullEligibleSamplingFrameV2ParentValidationError(
            "utc_day invalid"
        ) from exc
    return text


def _self_hash(row: Mapping[str, Any], field: str, label: str) -> None:
    expected = _digest({key: value for key, value in row.items() if key != field})
    if _sha(row[field], field) != expected:
        raise P0FullEligibleSamplingFrameV2ParentValidationError(
            f"{label} self hash mismatch"
        )


_ADAPTER_FIELDS = frozenset({"adapter_id", "source_profile"})
_STRATUM_FIELDS = frozenset({"source_profile", "platform", "utc_day", "quota"})
_SCOPE_FIELDS = frozenset(
    {
        "schema_version", "record_origin", "scope_id", "created_at",
        "frame_cutoff", "adapter_profile_map", "strata",
        *POLICY_COMMITMENT_FIELDS, "expected_per_profile_quota",
        "expected_total_quota", "selection_algorithm", "lineage_policy",
        "labels_observed", "semantic_fields_used", "action_applied",
        "operational_effect", "artifact_sha256",
    }
)
_SEED_FIELDS = frozenset(
    {
        "schema_version", "record_origin", "seed_receipt_id", "scope_sha256",
        "frame_manifest_sha256", "future_seed_spec_sha256",
        "revealed_seed_sha256", "frame_owner_precommit_sha256",
        "frame_owner_precommitted_at", "revealed_at",
        "owner_authority_verified", "seed_authority_verified", "action_applied",
        "operational_effect", "artifact_sha256",
    }
)
_CENSUS_BASE_FIELDS = frozenset(
    {
        "locator_commitment_sha256", "adapter_id", "platform", "observed_at",
        "published_at", "lineage_root_locator_commitment_sha256", "lineage_role",
        "presented_rights_policy_assessed", "presented_collection_allowed",
        "presented_takedown_status", "presented_adapter_contract_verified",
    }
)
_CENSUS_FIELDS = frozenset(
    {
        "schema_version", "record_origin", "enumeration_sequence", "candidate_id",
        *_CENSUS_BASE_FIELDS, "lineage_group_id", "utc_day",
        "eligibility_status", "exclusion_reason_codes", "action_applied",
        "operational_effect", "row_sha256",
    }
)
_FRAME_FIELDS = frozenset(
    {
        "schema_version", "record_origin", "scope_sha256", "frame_sealed_at",
        "census_byte_count", "census_raw_sha256", "census_row_count",
        "derived_candidate_inventory_sha256", "eligible_candidate_count",
        "excluded_candidate_count", "eligible_lineage_unit_count",
        "eligible_sampling_units_sha256", "excluded_candidates_sha256",
        "exclusion_reason_counts", "stratum_populations",
        "presented_census_serialization_verified", "presented_serialization_only",
        *FALSE_AUTHORITY_FIELDS,
        "gate_status", "action_applied", "operational_effect", "artifact_sha256",
    }
)
_SELECTED_FIELDS = frozenset(
    {
        "input_sequence", "candidate_id", "locator_commitment_sha256",
        "lineage_group_id", "lineage_unit_sha256", "adapter_id",
        "source_profile", "platform", "utc_day", "stratum_id", "rank_sha256",
        "N_h", "n_h", "inclusion_probability_numerator",
        "inclusion_probability_denominator",
    }
)
_PLAN_FIELDS = frozenset(
    {
        "schema_version", "record_origin", "scope_sha256", "seed_receipt_sha256",
        "frame_manifest_sha256", "selection_algorithm", "derived_seed_sha256",
        "without_replacement", "spill_allowed", "replacement_allowed",
        "input_count", "per_profile_counts", "selected_inputs",
        "selected_input_set_sha256", "eligible_surplus_count",
        "eligible_surplus_sha256", "selection_sealed_at",
        "presented_serialization_only", *FALSE_AUTHORITY_FIELDS, "gate_status",
        "action_applied", "operational_effect", "artifact_sha256",
    }
)

ARTIFACT_FIELDS = {
    "scope": sorted(_SCOPE_FIELDS),
    "seed_receipt": sorted(_SEED_FIELDS),
    "census_row": sorted(_CENSUS_FIELDS),
    "frame_manifest": sorted(_FRAME_FIELDS),
    "sampling_plan": sorted(_PLAN_FIELDS),
    "selected_input": sorted(_SELECTED_FIELDS),
}
EXPECTED_COMPONENT_MANIFEST: dict[str, Any] = {
    "component": "p0_full_eligible_sampling_frame_v2_contract",
    "record_origin": EXAMPLE_ORIGIN,
    "scope_schema": SCOPE_SCHEMA,
    "seed_receipt_schema": SEED_RECEIPT_SCHEMA,
    "census_row_schema": CENSUS_ROW_SCHEMA,
    "frame_manifest_schema": FRAME_MANIFEST_SCHEMA,
    "sampling_plan_schema": SAMPLING_PLAN_SCHEMA,
    "source_profiles": list(SOURCE_PROFILES),
    "expected_per_profile_quota": EXPECTED_PER_PROFILE_QUOTA,
    "expected_total_quota": EXPECTED_TOTAL_QUOTA,
    "selection_algorithm": SELECTION_ALGORITHM,
    "lineage_policy": LINEAGE_POLICY,
    "rank_domain": RANK_DOMAIN,
    "selection_rank_input_fields": list(SELECTION_RANK_INPUT_FIELDS),
    "policy_commitment_fields": list(POLICY_COMMITMENT_FIELDS),
    "artifact_fields": ARTIFACT_FIELDS,
    "lineage_group_domain": LINEAGE_GROUP_DOMAIN,
    "raw_inputs": [
        "canonical_json_scope", "canonical_jsonl_census",
        "canonical_json_seed_receipt",
    ],
    "chronology": [
        "scope_and_future_event_spec", "enumeration_and_frame_cutoff",
        "frame_seal", "presented_owner_precommit", "future_seed_reveal",
        "selection_seal",
    ],
    "semantic_fields_used": False,
    **{field: False for field in FALSE_AUTHORITY_FIELDS},
    "action_applied": False,
    "operational_effect": OPERATIONAL_EFFECT,
}
EXPECTED_COMPONENT_MANIFEST_SHA256 = _digest(EXPECTED_COMPONENT_MANIFEST)


def _scope(raw: bytes) -> dict[str, Any]:
    row = _strict(_object(raw, "scope", MAX_SCOPE_BYTES), _SCOPE_FIELDS, "scope")
    if row["schema_version"] != SCOPE_SCHEMA or row["record_origin"] != EXAMPLE_ORIGIN:
        raise P0FullEligibleSamplingFrameV2ParentValidationError(
            "scope schema/origin mismatch"
        )
    _identifier(row["scope_id"], "scope_id")
    created = _timestamp(row["created_at"], "created_at")
    cutoff = _timestamp(row["frame_cutoff"], "frame_cutoff")
    if created > cutoff:
        raise P0FullEligibleSamplingFrameV2ParentValidationError(
            "scope chronology mismatch"
        )
    for field in POLICY_COMMITMENT_FIELDS:
        _sha(row[field], field)
    mappings = row["adapter_profile_map"]
    if type(mappings) is not list or not mappings:
        raise P0FullEligibleSamplingFrameV2ParentValidationError(
            "adapter mapping missing"
        )
    normalized = []
    for item in mappings:
        item = _strict(item, _ADAPTER_FIELDS, "adapter mapping")
        adapter = _identifier(item["adapter_id"], "adapter_id")
        profile = _text(item["source_profile"], "source_profile")
        if profile not in SOURCE_PROFILES:
            raise P0FullEligibleSamplingFrameV2ParentValidationError(
                "adapter profile invalid"
            )
        normalized.append({"adapter_id": adapter, "source_profile": profile})
    if normalized != sorted(normalized, key=lambda item: item["adapter_id"]):
        raise P0FullEligibleSamplingFrameV2ParentValidationError(
            "adapter order invalid"
        )
    if len({item["adapter_id"] for item in normalized}) != len(normalized):
        raise P0FullEligibleSamplingFrameV2ParentValidationError(
            "adapter duplicate"
        )
    strata = row["strata"]
    if type(strata) is not list or not strata:
        raise P0FullEligibleSamplingFrameV2ParentValidationError("strata missing")
    order = {profile: index for index, profile in enumerate(SOURCE_PROFILES)}
    normalized_strata = []
    for item in strata:
        item = _strict(item, _STRATUM_FIELDS, "stratum")
        profile = _text(item["source_profile"], "source_profile")
        if profile not in SOURCE_PROFILES:
            raise P0FullEligibleSamplingFrameV2ParentValidationError(
                "stratum profile invalid"
            )
        normalized_strata.append(
            {
                "source_profile": profile,
                "platform": _platform(item["platform"]),
                "utc_day": _day(item["utc_day"]),
                "quota": _int(item["quota"], "quota", 1),
            }
        )
    key = lambda item: (
        order[item["source_profile"]], item["platform"], item["utc_day"]
    )
    if normalized_strata != sorted(normalized_strata, key=key):
        raise P0FullEligibleSamplingFrameV2ParentValidationError(
            "strata order invalid"
        )
    keys = [(x["source_profile"], x["platform"], x["utc_day"]) for x in normalized_strata]
    if len(set(keys)) != len(keys):
        raise P0FullEligibleSamplingFrameV2ParentValidationError(
            "stratum duplicate"
        )
    quotas: Counter[str] = Counter()
    for item in normalized_strata:
        quotas[item["source_profile"]] += item["quota"]
    if dict(quotas) != {profile: 10 for profile in SOURCE_PROFILES}:
        raise P0FullEligibleSamplingFrameV2ParentValidationError(
            "profile quotas invalid"
        )
    if (
        _int(row["expected_per_profile_quota"], "expected_per_profile_quota", 1)
        != 10
        or _int(row["expected_total_quota"], "expected_total_quota", 1) != 40
        or row["selection_algorithm"] != SELECTION_ALGORITHM
        or row["lineage_policy"] != LINEAGE_POLICY
    ):
        raise P0FullEligibleSamplingFrameV2ParentValidationError(
            "scope design mismatch"
        )
    for field in ("labels_observed", "semantic_fields_used", "action_applied"):
        if _bool(row[field], field) is not False:
            raise P0FullEligibleSamplingFrameV2ParentValidationError(
                f"scope {field} must be false"
            )
    if row["operational_effect"] != OPERATIONAL_EFFECT:
        raise P0FullEligibleSamplingFrameV2ParentValidationError(
            "scope operational effect mismatch"
        )
    _self_hash(row, "artifact_sha256", "scope")
    return row


def _candidate_id(locator: str) -> str:
    return "P0:FRAME:CANDIDATE:" + _digest(
        {"domain": CANDIDATE_ID_DOMAIN, "locator_commitment_sha256": locator}
    )


def _lineage_group(root_locator: str) -> str:
    return "P0:FRAME:LINEAGE:" + _digest(
        {
            "domain": LINEAGE_GROUP_DOMAIN,
            "root_locator_commitment_sha256": root_locator,
        }
    )


def _stratum_id(profile: str, platform: str, day: str) -> str:
    return "P0:FRAME:STRATUM:" + _digest(
        {
            "domain": STRATUM_ID_DOMAIN,
            "source_profile": profile,
            "platform": platform,
            "utc_day": day,
        }
    )


def _reason_map(
    rows: Sequence[Mapping[str, Any]], adapter_map: Mapping[str, str]
) -> dict[str, list[str]]:
    groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[row["lineage_group_id"]].append(row)
    result = {}
    for group, members in groups.items():
        if len({adapter_map[item["adapter_id"]] for item in members}) != 1:
            raise P0FullEligibleSamplingFrameV2ParentValidationError(
                f"lineage group crosses profiles: {group}"
            )
        lineage_strata = {
            (
                adapter_map[item["adapter_id"]],
                item["platform"],
                item["utc_day"],
            )
            for item in members
        }
        if len(lineage_strata) != 1:
            raise P0FullEligibleSamplingFrameV2ParentValidationError(
                f"lineage group crosses fixed platform/UTC-day strata: {group}"
            )
        roots = [item for item in members if item["lineage_role"] == "ROOT"]
        if len(roots) > 1:
            raise P0FullEligibleSamplingFrameV2ParentValidationError(
                f"lineage group ROOT count invalid: {group}"
            )
        root = roots[0] if roots else None
        if root is None:
            if any(item["lineage_role"] != "UNKNOWN" for item in members):
                raise P0FullEligibleSamplingFrameV2ParentValidationError(
                    "rootless lineage group contains non-UNKNOWN member"
                )
        else:
            if root is not min(
                members,
                key=lambda item: (
                    item["locator_commitment_sha256"], item["candidate_id"]
                ),
            ):
                raise P0FullEligibleSamplingFrameV2ParentValidationError(
                    "ROOT is not canonical minimum"
                )
            if root["locator_commitment_sha256"] != root["lineage_root_locator_commitment_sha256"]:
                raise P0FullEligibleSamplingFrameV2ParentValidationError(
                    "ROOT commitment mismatch"
                )
        declared_root = members[0]["lineage_root_locator_commitment_sha256"]
        if any(
            item["lineage_root_locator_commitment_sha256"]
            != declared_root
            for item in members
        ):
            raise P0FullEligibleSamplingFrameV2ParentValidationError(
                "lineage root commitments differ"
            )
        for item in members:
            reasons = []
            if item["presented_rights_policy_assessed"] is not True:
                reasons.append("RIGHTS_POLICY_NOT_ASSESSED")
            if item["presented_collection_allowed"] is not True:
                reasons.append("COLLECTION_NOT_ALLOWED")
            if item["presented_takedown_status"] != "ACTIVE":
                reasons.append("TAKEDOWN_NOT_ACTIVE")
            if item["presented_adapter_contract_verified"] is not True:
                reasons.append("ADAPTER_CONTRACT_NOT_VERIFIED")
            if item["lineage_role"] == "DERIVATIVE":
                reasons.append("LINEAGE_DERIVATIVE")
            elif item["lineage_role"] == "UNKNOWN":
                reasons.append("LINEAGE_UNKNOWN")
            if root is None:
                reasons.append("LINEAGE_GROUP_HAS_NO_ROOT")
            result[item["candidate_id"]] = [
                reason for reason in EXCLUSION_REASON_ORDER if reason in reasons
            ]
    return result


def _census(raw: bytes, scope: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = _jsonl(raw)
    adapters = {
        item["adapter_id"]: item["source_profile"]
        for item in scope["adapter_profile_map"]
    }
    strata = {
        (item["source_profile"], item["platform"], item["utc_day"])
        for item in scope["strata"]
    }
    cutoff = _timestamp(scope["frame_cutoff"], "frame_cutoff")
    for index, row in enumerate(rows, start=1):
        _strict(row, _CENSUS_FIELDS, f"census row {index}")
        if row["schema_version"] != CENSUS_ROW_SCHEMA or row["record_origin"] != EXAMPLE_ORIGIN:
            raise P0FullEligibleSamplingFrameV2ParentValidationError(
                "census schema/origin mismatch"
            )
        if _int(row["enumeration_sequence"], "enumeration_sequence", 1) != index:
            raise P0FullEligibleSamplingFrameV2ParentValidationError(
                "enumeration sequence invalid"
            )
        locator = _sha(row["locator_commitment_sha256"], "locator_commitment_sha256")
        if _identifier(row["candidate_id"], "candidate_id") != _candidate_id(locator):
            raise P0FullEligibleSamplingFrameV2ParentValidationError(
                "candidate id mismatch"
            )
        adapter = _identifier(row["adapter_id"], "adapter_id")
        if adapter not in adapters:
            raise P0FullEligibleSamplingFrameV2ParentValidationError(
                "adapter outside scope"
            )
        platform = _platform(row["platform"])
        observed = _timestamp(row["observed_at"], "observed_at")
        published = _timestamp(row["published_at"], "published_at")
        if published > observed or observed > cutoff:
            raise P0FullEligibleSamplingFrameV2ParentValidationError(
                "candidate chronology invalid"
            )
        root_locator = _sha(
            row["lineage_root_locator_commitment_sha256"],
            "lineage_root_locator_commitment_sha256",
        )
        if _identifier(row["lineage_group_id"], "lineage_group_id") != _lineage_group(root_locator):
            raise P0FullEligibleSamplingFrameV2ParentValidationError(
                "lineage group mismatch"
            )
        role = _text(row["lineage_role"], "lineage_role")
        if role not in LINEAGE_ROLES:
            raise P0FullEligibleSamplingFrameV2ParentValidationError(
                "lineage role invalid"
            )
        takedown = _text(row["presented_takedown_status"], "presented_takedown_status")
        if takedown not in TAKEDOWN_STATUSES:
            raise P0FullEligibleSamplingFrameV2ParentValidationError(
                "takedown status invalid"
            )
        for field in (
            "presented_rights_policy_assessed", "presented_collection_allowed",
            "presented_adapter_contract_verified", "action_applied",
        ):
            _bool(row[field], field)
        day = _day(row["utc_day"])
        if day != row["published_at"][:10] or (adapters[adapter], platform, day) not in strata:
            raise P0FullEligibleSamplingFrameV2ParentValidationError(
                "candidate stratum mismatch"
            )
        status = _text(row["eligibility_status"], "eligibility_status")
        if status not in ELIGIBILITY_STATUSES:
            raise P0FullEligibleSamplingFrameV2ParentValidationError(
                "eligibility invalid"
            )
        reasons = row["exclusion_reason_codes"]
        if type(reasons) is not list or any(type(reason) is not str for reason in reasons):
            raise P0FullEligibleSamplingFrameV2ParentValidationError(
                "exclusion reasons invalid"
            )
        if reasons != [reason for reason in EXCLUSION_REASON_ORDER if reason in reasons]:
            raise P0FullEligibleSamplingFrameV2ParentValidationError(
                "exclusion reason order invalid"
            )
        if any(reason not in EXCLUSION_REASON_ORDER for reason in reasons):
            raise P0FullEligibleSamplingFrameV2ParentValidationError(
                "unknown exclusion reason"
            )
        if row["action_applied"] is not False or row["operational_effect"] != OPERATIONAL_EFFECT:
            raise P0FullEligibleSamplingFrameV2ParentValidationError(
                "census action/effect invalid"
            )
        _self_hash(row, "row_sha256", "census row")
    if rows != sorted(rows, key=lambda item: item["candidate_id"]):
        raise P0FullEligibleSamplingFrameV2ParentValidationError(
            "candidate order invalid"
        )
    if len({row["candidate_id"] for row in rows}) != len(rows) or len(
        {row["locator_commitment_sha256"] for row in rows}
    ) != len(rows):
        raise P0FullEligibleSamplingFrameV2ParentValidationError(
            "duplicate census candidate"
        )
    expected = _reason_map(rows, adapters)
    eligible_groups: set[str] = set()
    for row in rows:
        reasons = expected[row["candidate_id"]]
        status = "EXCLUDED" if reasons else "ELIGIBLE"
        if row["exclusion_reason_codes"] != reasons or row["eligibility_status"] != status:
            raise P0FullEligibleSamplingFrameV2ParentValidationError(
                "eligibility derivation mismatch"
            )
        if status == "ELIGIBLE":
            if row["lineage_group_id"] in eligible_groups:
                raise P0FullEligibleSamplingFrameV2ParentValidationError(
                    "eligible lineage duplicate"
                )
            eligible_groups.add(row["lineage_group_id"])
    return rows


def _state(
    scope: Mapping[str, Any], census_raw: bytes, rows: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    adapters = {
        item["adapter_id"]: item["source_profile"]
        for item in scope["adapter_profile_map"]
    }
    projections = []
    eligible = []
    excluded = []
    reason_counts: Counter[str] = Counter()
    by_stratum: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        profile = adapters[row["adapter_id"]]
        unit = _digest(
            {
                "domain": LINEAGE_UNIT_DOMAIN,
                "lineage_group_id": row["lineage_group_id"],
                "candidate_id": row["candidate_id"],
                "locator_commitment_sha256": row["locator_commitment_sha256"],
            }
        )
        projection = {
            "candidate_id": row["candidate_id"],
            "locator_commitment_sha256": row["locator_commitment_sha256"],
            "lineage_group_id": row["lineage_group_id"],
            "lineage_unit_sha256": unit,
            "adapter_id": row["adapter_id"],
            "source_profile": profile,
            "platform": row["platform"],
            "utc_day": row["utc_day"],
            "eligibility_status": row["eligibility_status"],
            "exclusion_reason_codes": row["exclusion_reason_codes"],
            "row_sha256": row["row_sha256"],
        }
        projections.append(projection)
        if row["eligibility_status"] == "ELIGIBLE":
            eligible_unit = {
                key: projection[key]
                for key in (
                    "candidate_id",
                    "locator_commitment_sha256",
                    "lineage_group_id",
                    "lineage_unit_sha256",
                    "adapter_id",
                    "source_profile",
                    "platform",
                    "utc_day",
                )
            }
            eligible.append(eligible_unit)
            by_stratum[(profile, row["platform"], row["utc_day"])].append(
                eligible_unit
            )
        else:
            excluded.append(projection)
            reason_counts.update(row["exclusion_reason_codes"])
    populations = []
    for item in scope["strata"]:
        key = (item["source_profile"], item["platform"], item["utc_day"])
        population = len(by_stratum.get(key, []))
        quota = item["quota"]
        if population < quota:
            raise P0FullEligibleSamplingFrameV2ParentValidationError(
                "fixed stratum underfill"
            )
        populations.append(
            {
                "source_profile": key[0], "platform": key[1], "utc_day": key[2],
                "stratum_id": _stratum_id(*key), "N_h": population, "n_h": quota,
            }
        )
    return {
        "projections": projections, "eligible": eligible, "excluded": excluded,
        "reason_counts": reason_counts, "by_stratum": by_stratum,
        "populations": populations, "census_raw": census_raw,
    }


def _frame(
    scope: Mapping[str, Any], state: Mapping[str, Any], frame_sealed_at: str
) -> dict[str, Any]:
    if _timestamp(frame_sealed_at, "frame_sealed_at") <= _timestamp(
        scope["frame_cutoff"], "frame_cutoff"
    ):
        raise P0FullEligibleSamplingFrameV2ParentValidationError(
            "frame seal must follow cutoff"
        )
    material = {
        "schema_version": FRAME_MANIFEST_SCHEMA,
        "record_origin": EXAMPLE_ORIGIN,
        "scope_sha256": scope["artifact_sha256"],
        "frame_sealed_at": frame_sealed_at,
        "census_byte_count": len(state["census_raw"]),
        "census_raw_sha256": _raw_digest(state["census_raw"]),
        "census_row_count": len(state["projections"]),
        "derived_candidate_inventory_sha256": _digest(state["projections"]),
        "eligible_candidate_count": len(state["eligible"]),
        "excluded_candidate_count": len(state["excluded"]),
        "eligible_lineage_unit_count": len(state["eligible"]),
        "eligible_sampling_units_sha256": _digest(state["eligible"]),
        "excluded_candidates_sha256": _digest(state["excluded"]),
        "exclusion_reason_counts": [
            {"reason_code": reason, "count": state["reason_counts"].get(reason, 0)}
            for reason in EXCLUSION_REASON_ORDER
        ],
        "stratum_populations": state["populations"],
        "presented_census_serialization_verified": True,
        "presented_serialization_only": True,
        **{field: False for field in FALSE_AUTHORITY_FIELDS},
        "gate_status": "NO_GO_PRESENTED_SERIALIZATION_ONLY",
        "action_applied": False,
        "operational_effect": OPERATIONAL_EFFECT,
    }
    return _with_hash(material)


def _seed(
    raw: bytes, scope: Mapping[str, Any], frame: Mapping[str, Any]
) -> dict[str, Any]:
    row = _strict(
        _object(raw, "seed receipt", MAX_SEED_RECEIPT_BYTES),
        _SEED_FIELDS,
        "seed receipt",
    )
    if row["schema_version"] != SEED_RECEIPT_SCHEMA or row["record_origin"] != EXAMPLE_ORIGIN:
        raise P0FullEligibleSamplingFrameV2ParentValidationError(
            "seed schema/origin mismatch"
        )
    _identifier(row["seed_receipt_id"], "seed_receipt_id")
    if _sha(row["scope_sha256"], "scope_sha256") != scope["artifact_sha256"]:
        raise P0FullEligibleSamplingFrameV2ParentValidationError(
            "seed scope mismatch"
        )
    if _sha(row["frame_manifest_sha256"], "frame_manifest_sha256") != frame["artifact_sha256"]:
        raise P0FullEligibleSamplingFrameV2ParentValidationError(
            "seed frame mismatch"
        )
    if _sha(row["future_seed_spec_sha256"], "future_seed_spec_sha256") != scope["future_seed_spec_sha256"]:
        raise P0FullEligibleSamplingFrameV2ParentValidationError(
            "future seed spec mismatch"
        )
    _sha(row["revealed_seed_sha256"], "revealed_seed_sha256")
    _sha(row["frame_owner_precommit_sha256"], "frame_owner_precommit_sha256")
    sealed = _timestamp(frame["frame_sealed_at"], "frame_sealed_at")
    precommitted = _timestamp(
        row["frame_owner_precommitted_at"], "frame_owner_precommitted_at"
    )
    revealed = _timestamp(row["revealed_at"], "revealed_at")
    if not sealed < precommitted < revealed:
        raise P0FullEligibleSamplingFrameV2ParentValidationError(
            "frame/precommit/reveal chronology invalid"
        )
    for field in ("owner_authority_verified", "seed_authority_verified", "action_applied"):
        if _bool(row[field], field) is not False:
            raise P0FullEligibleSamplingFrameV2ParentValidationError(
                f"seed {field} must be false"
            )
    if row["operational_effect"] != OPERATIONAL_EFFECT:
        raise P0FullEligibleSamplingFrameV2ParentValidationError(
            "seed operational effect mismatch"
        )
    _self_hash(row, "artifact_sha256", "seed receipt")
    return row


def _plan(
    scope: Mapping[str, Any], seed: Mapping[str, Any], frame: Mapping[str, Any],
    state: Mapping[str, Any], selection_sealed_at: str,
) -> dict[str, Any]:
    if _timestamp(selection_sealed_at, "selection_sealed_at") <= _timestamp(
        seed["revealed_at"], "revealed_at"
    ):
        raise P0FullEligibleSamplingFrameV2ParentValidationError(
            "selection seal must follow reveal"
        )
    derived_seed = _digest(
        {
            "domain": SEED_DERIVATION_DOMAIN,
            "scope_sha256": scope["artifact_sha256"],
            "future_seed_spec_sha256": scope["future_seed_spec_sha256"],
            "revealed_seed_sha256": seed["revealed_seed_sha256"],
        }
    )
    populations = {
        (item["source_profile"], item["platform"], item["utc_day"]): item
        for item in state["populations"]
    }
    selected = []
    surplus = []
    for scope_stratum in scope["strata"]:
        key = (
            scope_stratum["source_profile"], scope_stratum["platform"],
            scope_stratum["utc_day"],
        )
        population = populations[key]
        ranked = []
        for item in state["by_stratum"].get(key, []):
            rank = _digest(
                {
                    "domain": RANK_DOMAIN,
                    "derived_seed_sha256": derived_seed,
                    "eligible_sampling_units_sha256": frame[
                        "eligible_sampling_units_sha256"
                    ],
                    "stratum_id": population["stratum_id"],
                    "lineage_unit_sha256": item["lineage_unit_sha256"],
                }
            )
            ranked.append((rank, item))
        ranked.sort(key=lambda pair: (pair[0], pair[1]["candidate_id"]))
        gcd = math.gcd(population["n_h"], population["N_h"])
        for rank, item in ranked[: population["n_h"]]:
            selected.append(
                {
                    "input_sequence": len(selected) + 1,
                    "candidate_id": item["candidate_id"],
                    "locator_commitment_sha256": item["locator_commitment_sha256"],
                    "lineage_group_id": item["lineage_group_id"],
                    "lineage_unit_sha256": item["lineage_unit_sha256"],
                    "adapter_id": item["adapter_id"],
                    "source_profile": item["source_profile"],
                    "platform": item["platform"], "utc_day": item["utc_day"],
                    "stratum_id": population["stratum_id"], "rank_sha256": rank,
                    "N_h": population["N_h"], "n_h": population["n_h"],
                    "inclusion_probability_numerator": population["n_h"] // gcd,
                    "inclusion_probability_denominator": population["N_h"] // gcd,
                }
            )
        surplus.extend(
            {
                "candidate_id": item["candidate_id"],
                "lineage_unit_sha256": item["lineage_unit_sha256"],
                "stratum_id": population["stratum_id"], "rank_sha256": rank,
            }
            for rank, item in ranked[population["n_h"] :]
        )
    expected_counts = {profile: 10 for profile in SOURCE_PROFILES}
    if len(selected) != 40 or dict(Counter(x["source_profile"] for x in selected)) != expected_counts:
        raise P0FullEligibleSamplingFrameV2ParentValidationError(
            "10x4 selection accounting invalid"
        )
    if len({x["candidate_id"] for x in selected}) != len(selected) or len(
        {x["lineage_group_id"] for x in selected}
    ) != len(selected):
        raise P0FullEligibleSamplingFrameV2ParentValidationError(
            "replacement/lineage duplicate invalid"
        )
    return _with_hash(
        {
            "schema_version": SAMPLING_PLAN_SCHEMA,
            "record_origin": EXAMPLE_ORIGIN,
            "scope_sha256": scope["artifact_sha256"],
            "seed_receipt_sha256": seed["artifact_sha256"],
            "frame_manifest_sha256": frame["artifact_sha256"],
            "selection_algorithm": SELECTION_ALGORITHM,
            "derived_seed_sha256": derived_seed,
            "without_replacement": True, "spill_allowed": False,
            "replacement_allowed": False, "input_count": len(selected),
            "per_profile_counts": expected_counts, "selected_inputs": selected,
            "selected_input_set_sha256": _digest(selected),
            "eligible_surplus_count": len(surplus),
            "eligible_surplus_sha256": _digest(surplus),
            "selection_sealed_at": selection_sealed_at,
            "presented_serialization_only": True,
            **{field: False for field in FALSE_AUTHORITY_FIELDS},
            "gate_status": "NO_GO_DETERMINISTIC_EXAMPLE_PLAN_ONLY",
            "action_applied": False, "operational_effect": OPERATIONAL_EFFECT,
        }
    )


def validate_frame_and_plan_against_raw_inputs(
    frame_manifest_raw: bytes,
    sampling_plan_raw: bytes,
    *,
    scope_raw: bytes,
    census_raw: bytes,
    seed_receipt_raw: bytes,
) -> dict[str, Any]:
    """Recompute frame and plan from exact raw inputs and return a NO-GO receipt."""

    scope = _scope(scope_raw)
    rows = _census(census_raw, scope)
    state = _state(scope, census_raw, rows)
    presented_frame = _strict(
        _object(frame_manifest_raw, "frame manifest", MAX_SCOPE_BYTES),
        _FRAME_FIELDS,
        "frame manifest",
    )
    expected_frame = _frame(scope, state, presented_frame["frame_sealed_at"])
    if frame_manifest_raw != _file(expected_frame):
        raise P0FullEligibleSamplingFrameV2ParentValidationError(
            "frame differs from independent replay"
        )
    seed = _seed(seed_receipt_raw, scope, expected_frame)
    presented_plan = _strict(
        _object(sampling_plan_raw, "sampling plan", MAX_CENSUS_BYTES),
        _PLAN_FIELDS,
        "sampling plan",
    )
    expected_plan = _plan(
        scope, seed, expected_frame, state, presented_plan["selection_sealed_at"]
    )
    if sampling_plan_raw != _file(expected_plan):
        raise P0FullEligibleSamplingFrameV2ParentValidationError(
            "plan differs from independent replay"
        )
    material = {
        "schema_version": VALIDATION_RECEIPT_SCHEMA,
        "expected_component_manifest_sha256": EXPECTED_COMPONENT_MANIFEST_SHA256,
        "scope_raw_sha256": _raw_digest(scope_raw),
        "census_raw_sha256": _raw_digest(census_raw),
        "frame_manifest_raw_sha256": _raw_digest(frame_manifest_raw),
        "seed_receipt_raw_sha256": _raw_digest(seed_receipt_raw),
        "sampling_plan_raw_sha256": _raw_digest(sampling_plan_raw),
        "frame_manifest_artifact_sha256": expected_frame["artifact_sha256"],
        "sampling_plan_artifact_sha256": expected_plan["artifact_sha256"],
        "selected_input_count": expected_plan["input_count"],
        "parent_separate_implementation_frame_replay_verified": True,
        "same_process_isolation_verified": False,
        "core_code_identity_verified": False,
        "parent_code_identity_verified": False,
        "external_population_completeness_verified": False,
        "owner_authority_verified": False,
        "external_seed_provenance_verified": False,
        "runtime_execution_verified": False,
        "actual_source_evidence_verified": False,
        "actual_authority_granted": False,
        "p0_phase_exit": False,
        "production_approval": False,
        "full_scan_approval": False,
        "gate_status": GATE_STATUS,
    }
    return {**material, "receipt_sha256": _digest(material)}


validate_frame_and_plan = validate_frame_and_plan_against_raw_inputs


__all__ = [
    "ARTIFACT_FIELDS",
    "CENSUS_ROW_SCHEMA",
    "EXPECTED_COMPONENT_MANIFEST",
    "EXPECTED_COMPONENT_MANIFEST_SHA256",
    "FRAME_MANIFEST_SCHEMA",
    "GATE_STATUS",
    "MAX_CENSUS_BYTES",
    "MAX_CENSUS_ROWS",
    "MAX_SCOPE_BYTES",
    "MAX_SEED_RECEIPT_BYTES",
    "P0FullEligibleSamplingFrameV2ParentValidationError",
    "SAMPLING_PLAN_SCHEMA",
    "SCOPE_SCHEMA",
    "SEED_RECEIPT_SCHEMA",
    "VALIDATION_RECEIPT_SCHEMA",
    "validate_frame_and_plan",
    "validate_frame_and_plan_against_raw_inputs",
]
