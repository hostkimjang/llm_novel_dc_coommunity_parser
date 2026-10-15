"""P0 full-eligible sampling-frame V2의 순수 직렬화 계약.

이 모듈은 파일, 네트워크, 시계 및 난수 장치를 읽지 않는다. 호출자가 제시한
canonical JSON scope, canonical JSONL census, canonical JSON seed receipt만을
검증하고, 그 *제시된 직렬화*에 한정된 frame manifest와 층화 SRSWOR 계획을
결정적으로 만든다. 실제 수집 완전성, 소유자/seed 권한, 실행 또는 production
승인을 증명하지 않는다.

작품명, 별칭, 본문, surface, claim, target, route, credit 같은 의미 필드는 census
schema에 존재하지 않는다. 따라서 ``아생갤`` 같은 문자열 표면은 profile 또는
eligibility를 바꾸는 입력이 될 수 없다. profile은 봉인된 adapter-id mapping만으로
결정된다.
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

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")
_PLATFORM_RE = re.compile(r"^[a-z0-9][a-z0-9._:-]{0,127}$")
_UTC_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_UTC_DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class P0FullEligibleFrameV2Error(ValueError):
    """V2 frame 계약이 입력을 fail-closed로 거부할 때 발생한다."""


def canonical_bytes(value: Any) -> bytes:
    """한 JSON 값을 UTF-8 canonical bytes(개행 없음)로 직렬화한다."""

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_file_bytes(value: Any) -> bytes:
    """한 canonical JSON object와 정확히 하나의 LF를 반환한다."""

    return canonical_bytes(value) + b"\n"


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def raw_sha256(value: bytes) -> str:
    if type(value) is not bytes:
        raise P0FullEligibleFrameV2Error("raw value must be exact bytes")
    return hashlib.sha256(value).hexdigest()


def with_self_hash(
    value: Mapping[str, Any], field: str = "artifact_sha256"
) -> dict[str, Any]:
    """self-hash field를 제외한 canonical object hash를 붙인다."""

    material = dict(value)
    material.pop(field, None)
    return {**material, field: canonical_sha256(material)}


def _reject_constant(value: str) -> None:
    raise P0FullEligibleFrameV2Error(f"non-finite JSON number is forbidden: {value}")


def _pairs_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise P0FullEligibleFrameV2Error(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _decode_json_object(raw: bytes, *, label: str, max_bytes: int) -> dict[str, Any]:
    if type(raw) is not bytes:
        raise P0FullEligibleFrameV2Error(f"{label} must be exact bytes")
    if not raw or len(raw) > max_bytes:
        raise P0FullEligibleFrameV2Error(f"{label} byte length is invalid")
    if raw.startswith(b"\xef\xbb\xbf"):
        raise P0FullEligibleFrameV2Error(f"{label} BOM is forbidden")
    if b"\r" in raw:
        raise P0FullEligibleFrameV2Error(f"{label} CR is forbidden")
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise P0FullEligibleFrameV2Error(f"{label} must be strict UTF-8") from exc
    if unicodedata.normalize("NFC", text) != text:
        raise P0FullEligibleFrameV2Error(f"{label} must be NFC")
    try:
        value = json.loads(
            text,
            object_pairs_hook=_pairs_object,
            parse_constant=_reject_constant,
        )
    except (json.JSONDecodeError, TypeError) as exc:
        raise P0FullEligibleFrameV2Error(f"{label} is invalid JSON") from exc
    if type(value) is not dict:
        raise P0FullEligibleFrameV2Error(f"{label} must be a JSON object")
    try:
        expected_raw = canonical_file_bytes(value)
    except (UnicodeEncodeError, TypeError, ValueError) as exc:
        raise P0FullEligibleFrameV2Error(
            f"{label} contains a noncanonical JSON value"
        ) from exc
    if raw != expected_raw:
        raise P0FullEligibleFrameV2Error(
            f"{label} must be canonical JSON with one terminal LF"
        )
    return value


def _decode_jsonl(raw: bytes, *, label: str) -> list[dict[str, Any]]:
    if type(raw) is not bytes:
        raise P0FullEligibleFrameV2Error(f"{label} must be exact bytes")
    if not raw or len(raw) > MAX_CENSUS_BYTES:
        raise P0FullEligibleFrameV2Error(f"{label} byte length is invalid")
    if raw.startswith(b"\xef\xbb\xbf"):
        raise P0FullEligibleFrameV2Error(f"{label} BOM is forbidden")
    if b"\r" in raw:
        raise P0FullEligibleFrameV2Error(f"{label} CR is forbidden")
    if not raw.endswith(b"\n") or raw.endswith(b"\n\n"):
        raise P0FullEligibleFrameV2Error(
            f"{label} requires one LF per row and no blank row"
        )
    lines = raw[:-1].split(b"\n")
    if not lines or len(lines) > MAX_CENSUS_ROWS or any(not line for line in lines):
        raise P0FullEligibleFrameV2Error(f"{label} row count is invalid")
    rows: list[dict[str, Any]] = []
    for index, line in enumerate(lines, start=1):
        rows.append(
            _decode_json_object(
                line + b"\n",
                label=f"{label} row {index}",
                max_bytes=MAX_CENSUS_BYTES,
            )
        )
    if raw != b"".join(canonical_file_bytes(row) for row in rows):
        raise P0FullEligibleFrameV2Error(f"{label} is not canonical JSONL")
    return rows


def _strict(value: Any, fields: frozenset[str], label: str) -> Mapping[str, Any]:
    if type(value) is not dict:
        raise P0FullEligibleFrameV2Error(f"{label} must be an exact object")
    actual = set(value)
    if actual != fields:
        raise P0FullEligibleFrameV2Error(
            f"{label} fields mismatch: missing={sorted(fields - actual)}, "
            f"extra={sorted(actual - fields)}"
        )
    return value


def _text(value: Any, field: str) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise P0FullEligibleFrameV2Error(f"{field} must be canonical nonempty text")
    if unicodedata.normalize("NFC", value) != value:
        raise P0FullEligibleFrameV2Error(f"{field} must be NFC")
    return value


def _identifier(value: Any, field: str) -> str:
    text = _text(value, field)
    if _SAFE_ID_RE.fullmatch(text) is None:
        raise P0FullEligibleFrameV2Error(f"{field} must be a safe identifier")
    return text


def _platform(value: Any, field: str = "platform") -> str:
    text = _text(value, field)
    if _PLATFORM_RE.fullmatch(text) is None:
        raise P0FullEligibleFrameV2Error(f"{field} must be a lowercase platform id")
    return text


def _sha(value: Any, field: str) -> str:
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        raise P0FullEligibleFrameV2Error(f"{field} must be lowercase sha256")
    return value


def _bool(value: Any, field: str) -> bool:
    if type(value) is not bool:
        raise P0FullEligibleFrameV2Error(f"{field} must be an exact boolean")
    return value


def _integer(value: Any, field: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise P0FullEligibleFrameV2Error(
            f"{field} must be an integer >= {minimum}; bool is forbidden"
        )
    return value


def _timestamp(value: Any, field: str) -> datetime:
    text = _text(value, field)
    if _UTC_TIMESTAMP_RE.fullmatch(text) is None:
        raise P0FullEligibleFrameV2Error(f"{field} must be second-precision UTC Z")
    try:
        parsed = datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError as exc:
        raise P0FullEligibleFrameV2Error(f"{field} is not a real UTC timestamp") from exc
    return parsed


def _day(value: Any, field: str = "utc_day") -> str:
    text = _text(value, field)
    if _UTC_DAY_RE.fullmatch(text) is None:
        raise P0FullEligibleFrameV2Error(f"{field} must be YYYY-MM-DD")
    try:
        datetime.strptime(text, "%Y-%m-%d")
    except ValueError as exc:
        raise P0FullEligibleFrameV2Error(f"{field} is not a real UTC day") from exc
    return text


def _self_hash(value: Mapping[str, Any], field: str, label: str) -> None:
    stored = _sha(value[field], field)
    material = {key: item for key, item in value.items() if key != field}
    if stored != canonical_sha256(material):
        raise P0FullEligibleFrameV2Error(f"{label} self hash mismatch")


def _false(value: Mapping[str, Any], field: str, label: str) -> None:
    if _bool(value[field], field) is not False:
        raise P0FullEligibleFrameV2Error(f"{label} must keep {field}=false")


_ADAPTER_MAP_ITEM_FIELDS = frozenset({"adapter_id", "source_profile"})
_STRATUM_SCOPE_FIELDS = frozenset(
    {"source_profile", "platform", "utc_day", "quota"}
)
_SCOPE_FIELDS = frozenset(
    {
        "schema_version",
        "record_origin",
        "scope_id",
        "created_at",
        "frame_cutoff",
        "adapter_profile_map",
        "strata",
        "enumeration_policy_sha256",
        "eligibility_policy_sha256",
        "rights_policy_sha256",
        "strata_policy_sha256",
        "future_seed_spec_sha256",
        "expected_per_profile_quota",
        "expected_total_quota",
        "selection_algorithm",
        "lineage_policy",
        "labels_observed",
        "semantic_fields_used",
        "action_applied",
        "operational_effect",
        "artifact_sha256",
    }
)


def _validate_scope_value(value: Any) -> dict[str, Any]:
    row = _strict(value, _SCOPE_FIELDS, "scope")
    if row["schema_version"] != SCOPE_SCHEMA or row["record_origin"] != EXAMPLE_ORIGIN:
        raise P0FullEligibleFrameV2Error("scope schema/origin mismatch")
    _identifier(row["scope_id"], "scope_id")
    created = _timestamp(row["created_at"], "created_at")
    cutoff = _timestamp(row["frame_cutoff"], "frame_cutoff")
    if created > cutoff:
        raise P0FullEligibleFrameV2Error("scope created_at cannot follow frame_cutoff")
    for field in (
        "enumeration_policy_sha256",
        "eligibility_policy_sha256",
        "rights_policy_sha256",
        "strata_policy_sha256",
        "future_seed_spec_sha256",
    ):
        _sha(row[field], field)
    if type(row["adapter_profile_map"]) is not list or not row["adapter_profile_map"]:
        raise P0FullEligibleFrameV2Error("adapter_profile_map must be a nonempty list")
    adapter_rows: list[dict[str, str]] = []
    for item in row["adapter_profile_map"]:
        item = _strict(item, _ADAPTER_MAP_ITEM_FIELDS, "adapter mapping")
        adapter_id = _identifier(item["adapter_id"], "adapter_id")
        profile = _text(item["source_profile"], "source_profile")
        if profile not in SOURCE_PROFILES:
            raise P0FullEligibleFrameV2Error("adapter mapping profile is invalid")
        adapter_rows.append({"adapter_id": adapter_id, "source_profile": profile})
    if adapter_rows != sorted(adapter_rows, key=lambda item: item["adapter_id"]):
        raise P0FullEligibleFrameV2Error("adapter_profile_map must use adapter_id order")
    if len({item["adapter_id"] for item in adapter_rows}) != len(adapter_rows):
        raise P0FullEligibleFrameV2Error("adapter_id must map exactly once")

    if type(row["strata"]) is not list or not row["strata"]:
        raise P0FullEligibleFrameV2Error("strata must be a nonempty list")
    profile_order = {profile: index for index, profile in enumerate(SOURCE_PROFILES)}
    strata: list[dict[str, Any]] = []
    for item in row["strata"]:
        item = _strict(item, _STRATUM_SCOPE_FIELDS, "scope stratum")
        profile = _text(item["source_profile"], "source_profile")
        if profile not in SOURCE_PROFILES:
            raise P0FullEligibleFrameV2Error("stratum profile is invalid")
        strata.append(
            {
                "source_profile": profile,
                "platform": _platform(item["platform"]),
                "utc_day": _day(item["utc_day"]),
                "quota": _integer(item["quota"], "quota", minimum=1),
            }
        )
    order_key = lambda item: (
        profile_order[item["source_profile"]],
        item["platform"],
        item["utc_day"],
    )
    if strata != sorted(strata, key=order_key):
        raise P0FullEligibleFrameV2Error("strata must use fixed canonical order")
    keys = [(x["source_profile"], x["platform"], x["utc_day"]) for x in strata]
    if len(set(keys)) != len(keys):
        raise P0FullEligibleFrameV2Error("fixed stratum keys must be unique")
    quotas = Counter()
    for item in strata:
        quotas[item["source_profile"]] += item["quota"]
    if dict(quotas) != {
        profile: EXPECTED_PER_PROFILE_QUOTA for profile in SOURCE_PROFILES
    }:
        raise P0FullEligibleFrameV2Error("strata quotas must total 10 per profile")
    if _integer(
        row["expected_per_profile_quota"], "expected_per_profile_quota", minimum=1
    ) != EXPECTED_PER_PROFILE_QUOTA:
        raise P0FullEligibleFrameV2Error("expected_per_profile_quota must be 10")
    if _integer(
        row["expected_total_quota"], "expected_total_quota", minimum=1
    ) != EXPECTED_TOTAL_QUOTA:
        raise P0FullEligibleFrameV2Error("expected_total_quota must be 40")
    if row["selection_algorithm"] != SELECTION_ALGORITHM:
        raise P0FullEligibleFrameV2Error("selection_algorithm mismatch")
    if row["lineage_policy"] != LINEAGE_POLICY:
        raise P0FullEligibleFrameV2Error("lineage_policy mismatch")
    _false(row, "labels_observed", "scope")
    _false(row, "semantic_fields_used", "scope")
    _false(row, "action_applied", "scope")
    if row["operational_effect"] != OPERATIONAL_EFFECT:
        raise P0FullEligibleFrameV2Error("scope must remain shadow-only")
    _self_hash(row, "artifact_sha256", "scope")
    return dict(row)


def validate_scope_bytes(raw: bytes) -> dict[str, Any]:
    return _validate_scope_value(
        _decode_json_object(raw, label="scope", max_bytes=MAX_SCOPE_BYTES)
    )


def build_scope_bytes(material: Mapping[str, Any]) -> bytes:
    row = with_self_hash(material)
    raw = canonical_file_bytes(row)
    validate_scope_bytes(raw)
    return raw


_SEED_FIELDS = frozenset(
    {
        "schema_version",
        "record_origin",
        "seed_receipt_id",
        "scope_sha256",
        "frame_manifest_sha256",
        "future_seed_spec_sha256",
        "revealed_seed_sha256",
        "frame_owner_precommit_sha256",
        "frame_owner_precommitted_at",
        "revealed_at",
        "owner_authority_verified",
        "seed_authority_verified",
        "action_applied",
        "operational_effect",
        "artifact_sha256",
    }
)


def _validate_seed_value(
    value: Any, scope: Mapping[str, Any], frame: Mapping[str, Any]
) -> dict[str, Any]:
    row = _strict(value, _SEED_FIELDS, "seed receipt")
    if (
        row["schema_version"] != SEED_RECEIPT_SCHEMA
        or row["record_origin"] != EXAMPLE_ORIGIN
    ):
        raise P0FullEligibleFrameV2Error("seed receipt schema/origin mismatch")
    _identifier(row["seed_receipt_id"], "seed_receipt_id")
    if _sha(row["scope_sha256"], "scope_sha256") != scope["artifact_sha256"]:
        raise P0FullEligibleFrameV2Error("seed receipt scope binding mismatch")
    if _sha(row["frame_manifest_sha256"], "frame_manifest_sha256") != frame[
        "artifact_sha256"
    ]:
        raise P0FullEligibleFrameV2Error("seed receipt frame binding mismatch")
    _sha(row["revealed_seed_sha256"], "revealed_seed_sha256")
    seed_spec = _sha(row["future_seed_spec_sha256"], "future_seed_spec_sha256")
    if seed_spec != scope["future_seed_spec_sha256"]:
        raise P0FullEligibleFrameV2Error("seed receipt future-event spec mismatch")
    _sha(row["frame_owner_precommit_sha256"], "frame_owner_precommit_sha256")
    precommitted = _timestamp(
        row["frame_owner_precommitted_at"], "frame_owner_precommitted_at"
    )
    revealed = _timestamp(row["revealed_at"], "revealed_at")
    frame_sealed = _timestamp(frame["frame_sealed_at"], "frame_sealed_at")
    if not frame_sealed < precommitted < revealed:
        raise P0FullEligibleFrameV2Error(
            "chronology must be frame seal < owner precommit < seed reveal"
        )
    _false(row, "owner_authority_verified", "seed receipt")
    _false(row, "seed_authority_verified", "seed receipt")
    _false(row, "action_applied", "seed receipt")
    if row["operational_effect"] != OPERATIONAL_EFFECT:
        raise P0FullEligibleFrameV2Error("seed receipt must remain shadow-only")
    _self_hash(row, "artifact_sha256", "seed receipt")
    return dict(row)


def validate_seed_receipt_bytes(
    raw: bytes, scope_raw: bytes, frame_manifest_raw: bytes, census_raw: bytes
) -> dict[str, Any]:
    scope = validate_scope_bytes(scope_raw)
    frame = validate_frame_manifest_bytes(frame_manifest_raw, scope_raw, census_raw)
    value = _decode_json_object(
        raw, label="seed receipt", max_bytes=MAX_SEED_RECEIPT_BYTES
    )
    return _validate_seed_value(value, scope, frame)


def build_seed_receipt_bytes(
    material: Mapping[str, Any],
    scope_raw: bytes,
    frame_manifest_raw: bytes,
    census_raw: bytes,
) -> bytes:
    row = with_self_hash(material)
    raw = canonical_file_bytes(row)
    validate_seed_receipt_bytes(raw, scope_raw, frame_manifest_raw, census_raw)
    return raw


_CENSUS_BASE_FIELDS = frozenset(
    {
        "locator_commitment_sha256",
        "adapter_id",
        "platform",
        "observed_at",
        "published_at",
        "lineage_root_locator_commitment_sha256",
        "lineage_role",
        "presented_rights_policy_assessed",
        "presented_collection_allowed",
        "presented_takedown_status",
        "presented_adapter_contract_verified",
    }
)
_CENSUS_FIELDS = frozenset(
    {
        "schema_version",
        "record_origin",
        "enumeration_sequence",
        "candidate_id",
        *_CENSUS_BASE_FIELDS,
        "lineage_group_id",
        "utc_day",
        "eligibility_status",
        "exclusion_reason_codes",
        "action_applied",
        "operational_effect",
        "row_sha256",
    }
)


def candidate_id_from_locator(locator_commitment_sha256: str) -> str:
    locator = _sha(locator_commitment_sha256, "locator_commitment_sha256")
    digest = canonical_sha256(
        {"domain": CANDIDATE_ID_DOMAIN, "locator_commitment_sha256": locator}
    )
    return f"P0:FRAME:CANDIDATE:{digest}"


def lineage_group_id_from_root(root_locator_commitment_sha256: str) -> str:
    root = _sha(
        root_locator_commitment_sha256, "lineage_root_locator_commitment_sha256"
    )
    digest = canonical_sha256(
        {"domain": LINEAGE_GROUP_DOMAIN, "root_locator_commitment_sha256": root}
    )
    return f"P0:FRAME:LINEAGE:{digest}"


def _adapter_map(scope: Mapping[str, Any]) -> dict[str, str]:
    return {
        item["adapter_id"]: item["source_profile"]
        for item in scope["adapter_profile_map"]
    }


def _validate_base_candidate(
    value: Any, scope: Mapping[str, Any], *, label: str
) -> dict[str, Any]:
    item = _strict(value, _CENSUS_BASE_FIELDS, label)
    locator = _sha(item["locator_commitment_sha256"], "locator_commitment_sha256")
    adapter_id = _identifier(item["adapter_id"], "adapter_id")
    if adapter_id not in _adapter_map(scope):
        raise P0FullEligibleFrameV2Error("census adapter_id is outside sealed mapping")
    observed = _timestamp(item["observed_at"], "observed_at")
    published = _timestamp(item["published_at"], "published_at")
    cutoff = _timestamp(scope["frame_cutoff"], "frame_cutoff")
    if published > observed or observed > cutoff:
        raise P0FullEligibleFrameV2Error(
            "census chronology must satisfy published_at <= observed_at <= cutoff"
        )
    lineage_role = _text(item["lineage_role"], "lineage_role")
    if lineage_role not in LINEAGE_ROLES:
        raise P0FullEligibleFrameV2Error("lineage_role is invalid")
    root_locator = _sha(
        item["lineage_root_locator_commitment_sha256"],
        "lineage_root_locator_commitment_sha256",
    )
    takedown = _text(item["presented_takedown_status"], "presented_takedown_status")
    if takedown not in TAKEDOWN_STATUSES:
        raise P0FullEligibleFrameV2Error("takedown_status is invalid")
    return {
        "locator_commitment_sha256": locator,
        "adapter_id": adapter_id,
        "platform": _platform(item["platform"]),
        "observed_at": item["observed_at"],
        "published_at": item["published_at"],
        "lineage_root_locator_commitment_sha256": root_locator,
        "lineage_role": lineage_role,
        "presented_rights_policy_assessed": _bool(
            item["presented_rights_policy_assessed"],
            "presented_rights_policy_assessed",
        ),
        "presented_collection_allowed": _bool(
            item["presented_collection_allowed"], "presented_collection_allowed"
        ),
        "presented_takedown_status": takedown,
        "presented_adapter_contract_verified": _bool(
            item["presented_adapter_contract_verified"],
            "presented_adapter_contract_verified",
        ),
    }


def _derive_reason_map(
    rows: Sequence[Mapping[str, Any]], scope: Mapping[str, Any]
) -> dict[str, list[str]]:
    adapter_map = _adapter_map(scope)
    groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row["lineage_group_id"])].append(row)
    result: dict[str, list[str]] = {}
    for group_id, members in groups.items():
        profiles = {adapter_map[str(item["adapter_id"])] for item in members}
        if len(profiles) != 1:
            raise P0FullEligibleFrameV2Error(
                f"lineage group crosses derived profiles: {group_id}"
            )
        lineage_strata = {
            (
                adapter_map[str(item["adapter_id"])],
                str(item["platform"]),
                str(item["utc_day"]),
            )
            for item in members
        }
        if len(lineage_strata) != 1:
            raise P0FullEligibleFrameV2Error(
                f"lineage group crosses fixed platform/UTC-day strata: {group_id}"
            )
        roots = [item for item in members if item["lineage_role"] == "ROOT"]
        if len(roots) > 1:
            raise P0FullEligibleFrameV2Error(
                f"lineage group may contain at most one ROOT: {group_id}"
            )
        canonical_root = roots[0] if roots else None
        if canonical_root is None:
            if any(item["lineage_role"] != "UNKNOWN" for item in members):
                raise P0FullEligibleFrameV2Error(
                    "rootless lineage group may contain only UNKNOWN members"
                )
        else:
            minimum_member = min(
                members,
                key=lambda item: (
                    item["locator_commitment_sha256"],
                    item["candidate_id"],
                ),
            )
            if canonical_root is not minimum_member:
                raise P0FullEligibleFrameV2Error(
                    f"ROOT must be canonical-min across all lineage members: {group_id}"
                )
            if canonical_root["locator_commitment_sha256"] != canonical_root[
                "lineage_root_locator_commitment_sha256"
            ]:
                raise P0FullEligibleFrameV2Error("ROOT locator commitment mismatch")
        declared_root = members[0]["lineage_root_locator_commitment_sha256"]
        if any(
            item["lineage_root_locator_commitment_sha256"]
            != declared_root
            for item in members
        ):
            raise P0FullEligibleFrameV2Error("lineage root commitment must be uniform")
        for item in members:
            reasons: list[str] = []
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
            if canonical_root is None:
                reasons.append("LINEAGE_GROUP_HAS_NO_ROOT")
            ordered = [reason for reason in EXCLUSION_REASON_ORDER if reason in reasons]
            result[str(item["candidate_id"])] = ordered
    return result


def build_census_bytes(
    scope_raw: bytes, candidate_rows: Sequence[Mapping[str, Any]]
) -> bytes:
    """중립 candidate records로 eligible/excluded 전체 canonical JSONL을 만든다."""

    scope = validate_scope_bytes(scope_raw)
    if isinstance(candidate_rows, (str, bytes, bytearray)) or not isinstance(
        candidate_rows, Sequence
    ):
        raise P0FullEligibleFrameV2Error("candidate_rows must be a sequence")
    if not candidate_rows or len(candidate_rows) > MAX_CENSUS_ROWS:
        raise P0FullEligibleFrameV2Error("candidate_rows count is invalid")
    prepared: list[dict[str, Any]] = []
    for index, value in enumerate(candidate_rows, start=1):
        base = _validate_base_candidate(value, scope, label=f"candidate {index}")
        prepared.append(
            {
                **base,
                "candidate_id": candidate_id_from_locator(
                    base["locator_commitment_sha256"]
                ),
                "lineage_group_id": lineage_group_id_from_root(
                    base["lineage_root_locator_commitment_sha256"]
                ),
                "utc_day": base["published_at"][:10],
            }
        )
    locators = [item["locator_commitment_sha256"] for item in prepared]
    candidate_ids = [item["candidate_id"] for item in prepared]
    if len(set(locators)) != len(locators) or len(set(candidate_ids)) != len(candidate_ids):
        raise P0FullEligibleFrameV2Error(
            "duplicate candidate_id or locator commitment is forbidden"
        )
    prepared.sort(key=lambda item: item["candidate_id"])
    reason_map = _derive_reason_map(prepared, scope)
    rows: list[dict[str, Any]] = []
    for sequence, item in enumerate(prepared, start=1):
        reasons = reason_map[item["candidate_id"]]
        row = {
            "schema_version": CENSUS_ROW_SCHEMA,
            "record_origin": EXAMPLE_ORIGIN,
            "enumeration_sequence": sequence,
            "candidate_id": item["candidate_id"],
            **{field: item[field] for field in _CENSUS_BASE_FIELDS},
            "lineage_group_id": item["lineage_group_id"],
            "utc_day": item["utc_day"],
            "eligibility_status": "EXCLUDED" if reasons else "ELIGIBLE",
            "exclusion_reason_codes": reasons,
            "action_applied": False,
            "operational_effect": OPERATIONAL_EFFECT,
        }
        rows.append(with_self_hash(row, "row_sha256"))
    raw = b"".join(canonical_file_bytes(row) for row in rows)
    validate_census_bytes(raw, scope_raw)
    return raw


def _validate_census_values(
    values: Sequence[Any], scope: Mapping[str, Any]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    adapter_map = _adapter_map(scope)
    fixed_strata = {
        (item["source_profile"], item["platform"], item["utc_day"])
        for item in scope["strata"]
    }
    for index, value in enumerate(values, start=1):
        row = _strict(value, _CENSUS_FIELDS, f"census row {index}")
        if (
            row["schema_version"] != CENSUS_ROW_SCHEMA
            or row["record_origin"] != EXAMPLE_ORIGIN
        ):
            raise P0FullEligibleFrameV2Error("census row schema/origin mismatch")
        if _integer(row["enumeration_sequence"], "enumeration_sequence", minimum=1) != index:
            raise P0FullEligibleFrameV2Error("census enumeration must be contiguous")
        candidate_id = _identifier(row["candidate_id"], "candidate_id")
        base = {field: row[field] for field in _CENSUS_BASE_FIELDS}
        normalized = _validate_base_candidate(base, scope, label=f"census row {index} base")
        expected_id = candidate_id_from_locator(normalized["locator_commitment_sha256"])
        if candidate_id != expected_id:
            raise P0FullEligibleFrameV2Error("candidate_id/locator commitment mismatch")
        expected_group = lineage_group_id_from_root(
            normalized["lineage_root_locator_commitment_sha256"]
        )
        if _identifier(row["lineage_group_id"], "lineage_group_id") != expected_group:
            raise P0FullEligibleFrameV2Error("lineage_group_id/root commitment mismatch")
        day = _day(row["utc_day"])
        if day != normalized["published_at"][:10]:
            raise P0FullEligibleFrameV2Error("utc_day must derive from published_at")
        profile = adapter_map[normalized["adapter_id"]]
        if (profile, normalized["platform"], day) not in fixed_strata:
            raise P0FullEligibleFrameV2Error(
                "every census row must belong to a fixed profile/platform/UTC-day stratum"
            )
        status = _text(row["eligibility_status"], "eligibility_status")
        if status not in ELIGIBILITY_STATUSES:
            raise P0FullEligibleFrameV2Error("eligibility_status is invalid")
        reasons = row["exclusion_reason_codes"]
        if type(reasons) is not list or any(type(item) is not str for item in reasons):
            raise P0FullEligibleFrameV2Error("exclusion_reason_codes must be a string list")
        if reasons != [reason for reason in EXCLUSION_REASON_ORDER if reason in reasons]:
            raise P0FullEligibleFrameV2Error(
                "exclusion reasons must be unique and use canonical order"
            )
        if any(reason not in EXCLUSION_REASON_ORDER for reason in reasons):
            raise P0FullEligibleFrameV2Error("unknown exclusion reason")
        _false(row, "action_applied", "census row")
        if row["operational_effect"] != OPERATIONAL_EFFECT:
            raise P0FullEligibleFrameV2Error("census row must remain shadow-only")
        _self_hash(row, "row_sha256", "census row")
        rows.append(dict(row))
    if rows != sorted(rows, key=lambda item: item["candidate_id"]):
        raise P0FullEligibleFrameV2Error("census rows must use canonical candidate order")
    ids = [item["candidate_id"] for item in rows]
    locators = [item["locator_commitment_sha256"] for item in rows]
    if len(set(ids)) != len(rows) or len(set(locators)) != len(rows):
        raise P0FullEligibleFrameV2Error(
            "duplicate candidate_id or locator commitment is forbidden"
        )
    reason_map = _derive_reason_map(rows, scope)
    eligible_groups: set[str] = set()
    for row in rows:
        expected_reasons = reason_map[row["candidate_id"]]
        expected_status = "EXCLUDED" if expected_reasons else "ELIGIBLE"
        if (
            row["exclusion_reason_codes"] != expected_reasons
            or row["eligibility_status"] != expected_status
        ):
            raise P0FullEligibleFrameV2Error(
                "eligibility and exclusions must be recomputed from rights/adapter/lineage"
            )
        if expected_status == "ELIGIBLE":
            group = row["lineage_group_id"]
            if group in eligible_groups:
                raise P0FullEligibleFrameV2Error(
                    "duplicate eligible lineage sampling unit is forbidden"
                )
            eligible_groups.add(group)
    return rows


def validate_census_bytes(raw: bytes, scope_raw: bytes) -> list[dict[str, Any]]:
    scope = validate_scope_bytes(scope_raw)
    return _validate_census_values(_decode_jsonl(raw, label="census"), scope)


def stratum_id(source_profile: str, platform: str, utc_day: str) -> str:
    if source_profile not in SOURCE_PROFILES:
        raise P0FullEligibleFrameV2Error("source_profile is invalid")
    platform = _platform(platform)
    utc_day = _day(utc_day)
    digest = canonical_sha256(
        {
            "domain": STRATUM_ID_DOMAIN,
            "source_profile": source_profile,
            "platform": platform,
            "utc_day": utc_day,
        }
    )
    return f"P0:FRAME:STRATUM:{digest}"


_TRUTH_FALSE_FIELDS = (
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
_STRATUM_POPULATION_FIELDS = frozenset(
    {"source_profile", "platform", "utc_day", "stratum_id", "N_h", "n_h"}
)
_REASON_COUNT_FIELDS = frozenset({"reason_code", "count"})
_FRAME_FIELDS = frozenset(
    {
        "schema_version",
        "record_origin",
        "scope_sha256",
        "frame_sealed_at",
        "census_byte_count",
        "census_raw_sha256",
        "census_row_count",
        "derived_candidate_inventory_sha256",
        "eligible_candidate_count",
        "excluded_candidate_count",
        "eligible_lineage_unit_count",
        "eligible_sampling_units_sha256",
        "excluded_candidates_sha256",
        "exclusion_reason_counts",
        "stratum_populations",
        "presented_census_serialization_verified",
        "presented_serialization_only",
        *_TRUTH_FALSE_FIELDS,
        "gate_status",
        "action_applied",
        "operational_effect",
        "artifact_sha256",
    }
)
_SELECTED_FIELDS = frozenset(
    {
        "input_sequence",
        "candidate_id",
        "locator_commitment_sha256",
        "lineage_group_id",
        "lineage_unit_sha256",
        "adapter_id",
        "source_profile",
        "platform",
        "utc_day",
        "stratum_id",
        "rank_sha256",
        "N_h",
        "n_h",
        "inclusion_probability_numerator",
        "inclusion_probability_denominator",
    }
)
_PLAN_FIELDS = frozenset(
    {
        "schema_version",
        "record_origin",
        "scope_sha256",
        "seed_receipt_sha256",
        "frame_manifest_sha256",
        "selection_algorithm",
        "derived_seed_sha256",
        "without_replacement",
        "spill_allowed",
        "replacement_allowed",
        "input_count",
        "per_profile_counts",
        "selected_inputs",
        "selected_input_set_sha256",
        "eligible_surplus_count",
        "eligible_surplus_sha256",
        "selection_sealed_at",
        "presented_serialization_only",
        *_TRUTH_FALSE_FIELDS,
        "gate_status",
        "action_applied",
        "operational_effect",
        "artifact_sha256",
    }
)


def _frame_state(
    scope: Mapping[str, Any], census_raw: bytes, rows: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    adapter_map = _adapter_map(scope)
    eligible: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    reason_counts: Counter[str] = Counter()
    by_stratum: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    projections: list[dict[str, Any]] = []
    for row in rows:
        profile = adapter_map[row["adapter_id"]]
        unit_sha = canonical_sha256(
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
            "lineage_unit_sha256": unit_sha,
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
    populations: list[dict[str, Any]] = []
    for item in scope["strata"]:
        key = (item["source_profile"], item["platform"], item["utc_day"])
        N_h = len(by_stratum.get(key, []))
        n_h = item["quota"]
        if N_h < n_h:
            raise P0FullEligibleFrameV2Error(
                f"hard underfill in fixed stratum {key}: N_h={N_h}, n_h={n_h}; "
                "spill and replacement are forbidden"
            )
        populations.append(
            {
                "source_profile": key[0],
                "platform": key[1],
                "utc_day": key[2],
                "stratum_id": stratum_id(*key),
                "N_h": N_h,
                "n_h": n_h,
            }
        )
    return {
        "eligible": eligible,
        "excluded": excluded,
        "by_stratum": by_stratum,
        "projections": projections,
        "populations": populations,
        "reason_counts": reason_counts,
        "census_raw": census_raw,
    }


def _build_frame_value(
    scope: Mapping[str, Any], state: Mapping[str, Any], frame_sealed_at: str
) -> dict[str, Any]:
    sealed = _timestamp(frame_sealed_at, "frame_sealed_at")
    if sealed <= _timestamp(scope["frame_cutoff"], "frame_cutoff"):
        raise P0FullEligibleFrameV2Error("frame seal must strictly follow frame cutoff")
    reason_counts = [
        {"reason_code": reason, "count": state["reason_counts"].get(reason, 0)}
        for reason in EXCLUSION_REASON_ORDER
    ]
    material = {
        "schema_version": FRAME_MANIFEST_SCHEMA,
        "record_origin": EXAMPLE_ORIGIN,
        "scope_sha256": scope["artifact_sha256"],
        "frame_sealed_at": frame_sealed_at,
        "census_byte_count": len(state["census_raw"]),
        "census_raw_sha256": raw_sha256(state["census_raw"]),
        "census_row_count": len(state["projections"]),
        "derived_candidate_inventory_sha256": canonical_sha256(state["projections"]),
        "eligible_candidate_count": len(state["eligible"]),
        "excluded_candidate_count": len(state["excluded"]),
        "eligible_lineage_unit_count": len(state["eligible"]),
        "eligible_sampling_units_sha256": canonical_sha256(state["eligible"]),
        "excluded_candidates_sha256": canonical_sha256(state["excluded"]),
        "exclusion_reason_counts": reason_counts,
        "stratum_populations": state["populations"],
        "presented_census_serialization_verified": True,
        "presented_serialization_only": True,
        **{field: False for field in _TRUTH_FALSE_FIELDS},
        "gate_status": "NO_GO_PRESENTED_SERIALIZATION_ONLY",
        "action_applied": False,
        "operational_effect": OPERATIONAL_EFFECT,
    }
    return with_self_hash(material)


def _build_plan_value(
    scope: Mapping[str, Any],
    seed: Mapping[str, Any],
    frame: Mapping[str, Any],
    state: Mapping[str, Any],
    selection_sealed_at: str,
) -> dict[str, Any]:
    selection_sealed = _timestamp(selection_sealed_at, "selection_sealed_at")
    if selection_sealed <= _timestamp(seed["revealed_at"], "revealed_at"):
        raise P0FullEligibleFrameV2Error(
            "selection seal must strictly follow seed reveal"
        )
    derived_seed = canonical_sha256(
        {
            "domain": SEED_DERIVATION_DOMAIN,
            "scope_sha256": scope["artifact_sha256"],
            "future_seed_spec_sha256": scope["future_seed_spec_sha256"],
            "revealed_seed_sha256": seed["revealed_seed_sha256"],
        }
    )
    population_by_key = {
        (item["source_profile"], item["platform"], item["utc_day"]): item
        for item in state["populations"]
    }
    selected: list[dict[str, Any]] = []
    surplus: list[dict[str, Any]] = []
    for scope_stratum in scope["strata"]:
        key = (
            scope_stratum["source_profile"],
            scope_stratum["platform"],
            scope_stratum["utc_day"],
        )
        population = population_by_key[key]
        sid = population["stratum_id"]
        ranked: list[tuple[str, dict[str, Any]]] = []
        for item in state["by_stratum"].get(key, []):
            rank = canonical_sha256(
                {
                    "domain": RANK_DOMAIN,
                    "derived_seed_sha256": derived_seed,
                    "eligible_sampling_units_sha256": frame[
                        "eligible_sampling_units_sha256"
                    ],
                    "stratum_id": sid,
                    "lineage_unit_sha256": item["lineage_unit_sha256"],
                }
            )
            ranked.append((rank, item))
        ranked.sort(key=lambda pair: (pair[0], pair[1]["candidate_id"]))
        n_h = population["n_h"]
        for rank, item in ranked[:n_h]:
            selected.append(
                {
                    "input_sequence": len(selected) + 1,
                    "candidate_id": item["candidate_id"],
                    "locator_commitment_sha256": item["locator_commitment_sha256"],
                    "lineage_group_id": item["lineage_group_id"],
                    "lineage_unit_sha256": item["lineage_unit_sha256"],
                    "adapter_id": item["adapter_id"],
                    "source_profile": item["source_profile"],
                    "platform": item["platform"],
                    "utc_day": item["utc_day"],
                    "stratum_id": sid,
                    "rank_sha256": rank,
                    "N_h": population["N_h"],
                    "n_h": n_h,
                    "inclusion_probability_numerator": n_h
                    // math.gcd(n_h, population["N_h"]),
                    "inclusion_probability_denominator": population["N_h"]
                    // math.gcd(n_h, population["N_h"]),
                }
            )
        surplus.extend(
            {
                "candidate_id": item["candidate_id"],
                "lineage_unit_sha256": item["lineage_unit_sha256"],
                "stratum_id": sid,
                "rank_sha256": rank,
            }
            for rank, item in ranked[n_h:]
        )
    profile_counts = Counter(item["source_profile"] for item in selected)
    expected_counts = {
        profile: EXPECTED_PER_PROFILE_QUOTA for profile in SOURCE_PROFILES
    }
    if len(selected) != EXPECTED_TOTAL_QUOTA or dict(profile_counts) != expected_counts:
        raise P0FullEligibleFrameV2Error("exact 10x4 selection accounting failed")
    if len({item["candidate_id"] for item in selected}) != len(selected):
        raise P0FullEligibleFrameV2Error("selection replacement is forbidden")
    if len({item["lineage_group_id"] for item in selected}) != len(selected):
        raise P0FullEligibleFrameV2Error("selected lineage units must be unique")
    material = {
        "schema_version": SAMPLING_PLAN_SCHEMA,
        "record_origin": EXAMPLE_ORIGIN,
        "scope_sha256": scope["artifact_sha256"],
        "seed_receipt_sha256": seed["artifact_sha256"],
        "frame_manifest_sha256": frame["artifact_sha256"],
        "selection_algorithm": SELECTION_ALGORITHM,
        "derived_seed_sha256": derived_seed,
        "without_replacement": True,
        "spill_allowed": False,
        "replacement_allowed": False,
        "input_count": len(selected),
        "per_profile_counts": expected_counts,
        "selected_inputs": selected,
        "selected_input_set_sha256": canonical_sha256(selected),
        "eligible_surplus_count": len(surplus),
        "eligible_surplus_sha256": canonical_sha256(surplus),
        "selection_sealed_at": selection_sealed_at,
        "presented_serialization_only": True,
        **{field: False for field in _TRUTH_FALSE_FIELDS},
        "gate_status": "NO_GO_DETERMINISTIC_EXAMPLE_PLAN_ONLY",
        "action_applied": False,
        "operational_effect": OPERATIONAL_EFFECT,
    }
    return with_self_hash(material)


def build_frame_manifest_bytes(
    scope_raw: bytes, census_raw: bytes, *, frame_sealed_at: str
) -> bytes:
    """seed reveal 전에 제시된 census를 frame manifest로 봉인한다."""
    scope = validate_scope_bytes(scope_raw)
    rows = validate_census_bytes(census_raw, scope_raw)
    state = _frame_state(scope, census_raw, rows)
    frame = _build_frame_value(scope, state, frame_sealed_at)
    return canonical_file_bytes(frame)


def build_sampling_plan_bytes(
    scope_raw: bytes,
    census_raw: bytes,
    frame_manifest_raw: bytes,
    seed_receipt_raw: bytes,
    *,
    selection_sealed_at: str,
) -> bytes:
    """frame 이후 reveal된 seed로 deterministic 층화 계획을 봉인한다."""

    scope = validate_scope_bytes(scope_raw)
    frame = validate_frame_manifest_bytes(frame_manifest_raw, scope_raw, census_raw)
    seed = validate_seed_receipt_bytes(
        seed_receipt_raw, scope_raw, frame_manifest_raw, census_raw
    )
    rows = validate_census_bytes(census_raw, scope_raw)
    state = _frame_state(scope, census_raw, rows)
    plan = _build_plan_value(
        scope, seed, frame, state, selection_sealed_at
    )
    return canonical_file_bytes(plan)


def _validate_truth_flags(value: Mapping[str, Any], label: str) -> None:
    for field in _TRUTH_FALSE_FIELDS:
        _false(value, field, label)
    _false(value, "action_applied", label)
    if value["operational_effect"] != OPERATIONAL_EFFECT:
        raise P0FullEligibleFrameV2Error(f"{label} must remain shadow-only")


def validate_frame_manifest_bytes(
    raw: bytes, scope_raw: bytes, census_raw: bytes
) -> dict[str, Any]:
    value = _decode_json_object(
        raw, label="frame manifest", max_bytes=MAX_SCOPE_BYTES
    )
    row = _strict(value, _FRAME_FIELDS, "frame manifest")
    if (
        row["schema_version"] != FRAME_MANIFEST_SCHEMA
        or row["record_origin"] != EXAMPLE_ORIGIN
    ):
        raise P0FullEligibleFrameV2Error("frame manifest schema/origin mismatch")
    if _bool(
        row["presented_census_serialization_verified"],
        "presented_census_serialization_verified",
    ) is not True:
        raise P0FullEligibleFrameV2Error("presented serialization flag must be true")
    if _bool(row["presented_serialization_only"], "presented_serialization_only") is not True:
        raise P0FullEligibleFrameV2Error("frame truth must be presented-only")
    _validate_truth_flags(row, "frame manifest")
    _self_hash(row, "artifact_sha256", "frame manifest")
    expected_raw = build_frame_manifest_bytes(
        scope_raw, census_raw, frame_sealed_at=row["frame_sealed_at"]
    )
    if raw != expected_raw:
        raise P0FullEligibleFrameV2Error("frame manifest is not the exact recomputation")
    return dict(row)


def validate_sampling_plan_bytes(
    raw: bytes,
    scope_raw: bytes,
    census_raw: bytes,
    seed_receipt_raw: bytes,
    frame_manifest_raw: bytes,
) -> dict[str, Any]:
    validate_frame_manifest_bytes(frame_manifest_raw, scope_raw, census_raw)
    value = _decode_json_object(raw, label="sampling plan", max_bytes=MAX_CENSUS_BYTES)
    row = _strict(value, _PLAN_FIELDS, "sampling plan")
    if (
        row["schema_version"] != SAMPLING_PLAN_SCHEMA
        or row["record_origin"] != EXAMPLE_ORIGIN
    ):
        raise P0FullEligibleFrameV2Error("sampling plan schema/origin mismatch")
    if _bool(row["without_replacement"], "without_replacement") is not True:
        raise P0FullEligibleFrameV2Error("without_replacement must be true")
    _false(row, "spill_allowed", "sampling plan")
    _false(row, "replacement_allowed", "sampling plan")
    if _bool(row["presented_serialization_only"], "presented_serialization_only") is not True:
        raise P0FullEligibleFrameV2Error("plan truth must be presented-only")
    _validate_truth_flags(row, "sampling plan")
    _self_hash(row, "artifact_sha256", "sampling plan")
    expected_plan_raw = build_sampling_plan_bytes(
        scope_raw,
        census_raw,
        frame_manifest_raw,
        seed_receipt_raw,
        selection_sealed_at=row["selection_sealed_at"],
    )
    if raw != expected_plan_raw:
        raise P0FullEligibleFrameV2Error("sampling plan is not the exact recomputation")
    return dict(row)


ARTIFACT_FIELDS = {
    "scope": sorted(_SCOPE_FIELDS),
    "seed_receipt": sorted(_SEED_FIELDS),
    "census_row": sorted(_CENSUS_FIELDS),
    "frame_manifest": sorted(_FRAME_FIELDS),
    "sampling_plan": sorted(_PLAN_FIELDS),
    "selected_input": sorted(_SELECTED_FIELDS),
}
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
FALSE_AUTHORITY_FIELDS = _TRUTH_FALSE_FIELDS


COMPONENT_MANIFEST = {
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
    "raw_inputs": ["canonical_json_scope", "canonical_jsonl_census", "canonical_json_seed_receipt"],
    "chronology": [
        "scope_and_future_event_spec",
        "enumeration_and_frame_cutoff",
        "frame_seal",
        "presented_owner_precommit",
        "future_seed_reveal",
        "selection_seal",
    ],
    "semantic_fields_used": False,
    "bounded_scope_completeness_verified": False,
    "external_owner_authority_verified": False,
    "enumeration_adapter_runtime_verified": False,
    "eligibility_factual_authority_verified": False,
    "lineage_factual_authority_verified": False,
    "seed_authority_verified": False,
    "seed_randomness_authority_verified": False,
    "probability_design_authority_verified": False,
    "capture_not_started_authority_verified": False,
    "code_identity_verified": False,
    "runtime_execution_verified": False,
    "actual_source_evidence_verified": False,
    "route_packet_runtime_credit_authority_verified": False,
    "actual_authority_granted": False,
    "production_approval": False,
    "full_scan_approval": False,
    "action_applied": False,
    "operational_effect": OPERATIONAL_EFFECT,
}
COMPONENT_MANIFEST_SHA256 = canonical_sha256(COMPONENT_MANIFEST)


__all__ = [
    "SCOPE_SCHEMA",
    "SEED_RECEIPT_SCHEMA",
    "CENSUS_ROW_SCHEMA",
    "FRAME_MANIFEST_SCHEMA",
    "SAMPLING_PLAN_SCHEMA",
    "EXAMPLE_ORIGIN",
    "OPERATIONAL_EFFECT",
    "SOURCE_PROFILES",
    "EXPECTED_PER_PROFILE_QUOTA",
    "EXPECTED_TOTAL_QUOTA",
    "SELECTION_ALGORITHM",
    "LINEAGE_POLICY",
    "RANK_DOMAIN",
    "MAX_SCOPE_BYTES",
    "MAX_SEED_RECEIPT_BYTES",
    "MAX_CENSUS_BYTES",
    "MAX_CENSUS_ROWS",
    "EXCLUSION_REASON_ORDER",
    "ARTIFACT_FIELDS",
    "POLICY_COMMITMENT_FIELDS",
    "SELECTION_RANK_INPUT_FIELDS",
    "FALSE_AUTHORITY_FIELDS",
    "COMPONENT_MANIFEST",
    "COMPONENT_MANIFEST_SHA256",
    "P0FullEligibleFrameV2Error",
    "canonical_bytes",
    "canonical_file_bytes",
    "canonical_sha256",
    "raw_sha256",
    "with_self_hash",
    "candidate_id_from_locator",
    "lineage_group_id_from_root",
    "stratum_id",
    "build_scope_bytes",
    "validate_scope_bytes",
    "build_seed_receipt_bytes",
    "validate_seed_receipt_bytes",
    "build_census_bytes",
    "validate_census_bytes",
    "build_frame_manifest_bytes",
    "build_sampling_plan_bytes",
    "validate_frame_manifest_bytes",
    "validate_sampling_plan_bytes",
]
