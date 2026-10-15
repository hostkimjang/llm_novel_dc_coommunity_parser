"""Actual-P0 parser route를 봉인하는 무쓰기 계약 검증기.

이 모듈은 실제 source snapshot에서 4개 profile별 10건을 역산하고,
label을 보기 전에 입력 선택을 봉인하며, 모든 입력을 ``TYPED``,
``GENERIC_PENDING``, ``PARSER_ERROR`` 중 정확히 하나로 귀속한다. 검증
성공은 actual/production/full-scan 권한을 부여하지 않는다.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
import hashlib
import json
import re
from typing import Any, Mapping, Sequence

from llm_batch.grounding import p0_actual_authority_contract as authority_contract
from llm_batch.grounding import p0_actual_registry_contract as registry_contract


SOURCE_INPUT_PLAN_SCHEMA = "p0_actual_source_input_plan_v1"
LABEL_BLIND_SEAL_SCHEMA_V1 = "p0_actual_label_blind_claim_selection_seal_v1"
LABEL_BLIND_SEAL_SCHEMA = "p0_actual_label_blind_claim_selection_seal_v2"
TERMINAL_QUEUE_SCHEMA = "p0_actual_parser_terminal_queue_v1"
ROUTE_RECEIPT_SCHEMA = "p0_actual_parser_route_contract_receipt_v2"

ACTUAL_ORIGIN = registry_contract.ACTUAL_ORIGIN
EXAMPLE_ORIGIN = registry_contract.EXAMPLE_ORIGIN
OPERATIONAL_EFFECT = registry_contract.OPERATIONAL_EFFECT
SOURCE_PROFILES = registry_contract.SOURCE_PROFILES
TERMINAL_DISPOSITIONS = ("GENERIC_PENDING", "PARSER_ERROR")
ROUTE_CLASSES = ("TYPED", *TERMINAL_DISPOSITIONS)
EXPECTED_PER_PROFILE_QUOTA = 10
EXPECTED_INPUT_COUNT = len(SOURCE_PROFILES) * EXPECTED_PER_PROFILE_QUOTA
SELECTION_ALGORITHM_V1 = "SHA256_RANK_WITHIN_PROFILE_V1"
SELECTION_ALGORITHM = "SHA256_RANK_ONE_CLAIM_PER_INPUT_WITHIN_PROFILE_V2"

SELECTION_BASIS_FIELDS = (
    "response_sha256",
    "normalized_text_sha256",
    "span_start",
    "span_end",
    "span_sha256",
    "normalized_surface",
)
FORBIDDEN_LABEL_FIELDS = (
    "annotation_status",
    "claim_direction",
    "claim_kind",
    "definition",
    "gold_label",
    "target_sense_id",
    "target_work_id",
    "truth_kind",
)
FORBIDDEN_LABEL_FIELDS_SHA256 = ""

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")


class P0ActualRouteError(ValueError):
    """Actual-P0 route 계약이 fail-closed로 거부될 때 발생한다."""


def canonical_bytes(value: Any) -> bytes:
    """JSON 값을 결정적 UTF-8 바이트로 직렬화한다."""

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    """결정적 JSON 표현의 SHA-256을 계산한다."""

    return hashlib.sha256(canonical_bytes(value)).hexdigest()


FORBIDDEN_LABEL_FIELDS_SHA256 = canonical_sha256(list(FORBIDDEN_LABEL_FIELDS))


def with_artifact_hash(value: Mapping[str, Any]) -> dict[str, Any]:
    """기존 self-hash를 제외한 내용으로 artifact hash를 다시 만든다."""

    material = dict(value)
    material.pop("artifact_sha256", None)
    return {**material, "artifact_sha256": canonical_sha256(material)}


def with_row_hash(value: Mapping[str, Any]) -> dict[str, Any]:
    """기존 self-hash를 제외한 내용으로 row hash를 다시 만든다."""

    material = dict(value)
    material.pop("row_sha256", None)
    return {**material, "row_sha256": canonical_sha256(material)}


def _strict(value: Any, fields: frozenset[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise P0ActualRouteError(f"{label} must be an object")
    if set(value) != fields:
        raise P0ActualRouteError(
            f"{label} fields mismatch: missing={sorted(fields - set(value))}, "
            f"extra={sorted(set(value) - fields)}"
        )
    return value


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise P0ActualRouteError(f"{field} must be canonical non-empty text")
    return value


def _optional_text(value: Any, field: str) -> str | None:
    return None if value is None else _text(value, field)


def _identifier(value: Any, field: str) -> str:
    text = _text(value, field)
    if _SAFE_ID.fullmatch(text) is None:
        raise P0ActualRouteError(f"{field} must be a safe identifier")
    return text


def _sha(value: Any, field: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise P0ActualRouteError(f"{field} must be lowercase sha256")
    return value


def _optional_sha(value: Any, field: str) -> str | None:
    return None if value is None else _sha(value, field)


def _timestamp(value: Any, field: str) -> datetime:
    text = _text(value, field)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise P0ActualRouteError(f"{field} must be RFC3339") from exc
    if parsed.tzinfo is None:
        raise P0ActualRouteError(f"{field} must include timezone")
    return parsed


def _nonnegative_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise P0ActualRouteError(f"{field} must be a nonnegative integer")
    return value


def _origin(value: Mapping[str, Any], expected_origin: str) -> None:
    if expected_origin not in {ACTUAL_ORIGIN, EXAMPLE_ORIGIN}:
        raise P0ActualRouteError("unsupported route origin")
    if value["record_origin"] != expected_origin:
        raise P0ActualRouteError("actual/example route origin mismatch")


def _self_hash(value: Mapping[str, Any], field: str, label: str) -> None:
    stored = _sha(value[field], field)
    material = {key: item for key, item in value.items() if key != field}
    if stored != canonical_sha256(material):
        raise P0ActualRouteError(f"{label} self hash mismatch")


def _no_write(value: Mapping[str, Any], label: str) -> None:
    if value["action_applied"] is not False:
        raise P0ActualRouteError(f"{label} must keep action_applied=false")
    if value["operational_effect"] != OPERATIONAL_EFFECT:
        raise P0ActualRouteError(f"{label} must remain shadow-only")


def _validate_snapshots(
    source_snapshots: Sequence[Mapping[str, Any]], expected_origin: str
) -> list[dict[str, Any]]:
    try:
        rows = [
            registry_contract._validate_source_snapshot(row, expected_origin)
            for row in source_snapshots
        ]
    except registry_contract.P0ActualContractError as exc:
        raise P0ActualRouteError(f"source snapshot invalid: {exc}") from exc
    ids = [row["registry_record_id"] for row in rows]
    source_ids = [row["source_id"] for row in rows]
    snapshots = [row["snapshot_id"] for row in rows]
    groups = [row["independence_group_id"] for row in rows]
    response_hashes = [row["response_sha256"] for row in rows]
    normalized_hashes = [row["normalized_text_sha256"] for row in rows]
    if (
        len(set(ids)) != len(rows)
        or len(set(source_ids)) != len(rows)
        or len(set(snapshots)) != len(rows)
    ):
        raise P0ActualRouteError("source input registry/snapshot ids must be unique")
    if len(set(groups)) != len(rows):
        raise P0ActualRouteError("source input independence groups must be unique")
    if len(set(response_hashes)) != len(rows):
        raise P0ActualRouteError(
            "eligible source inputs must have unique response content hashes"
        )
    if len(set(normalized_hashes)) != len(rows):
        raise P0ActualRouteError(
            "eligible source inputs must have unique normalized content hashes"
        )
    if any(row["independence_status"] != "ELIGIBLE_ROOT" for row in rows):
        raise P0ActualRouteError("source input must contain only eligible lineage roots")
    return rows


def validate_exact_profile_quota(
    source_snapshots: Sequence[Mapping[str, Any]],
    *,
    expected_origin: str = ACTUAL_ORIGIN,
) -> dict[str, int]:
    """검증된 source snapshot 자체에서 정확한 10x4 quota를 역산한다."""

    rows = _validate_snapshots(source_snapshots, expected_origin)
    counts = Counter(row["source_profile"] for row in rows)
    expected = {profile: EXPECTED_PER_PROFILE_QUOTA for profile in SOURCE_PROFILES}
    if len(rows) != EXPECTED_INPUT_COUNT or dict(counts) != expected:
        raise P0ActualRouteError(
            f"source profile quota must be exact 10x4: actual={dict(counts)}"
        )
    return expected


_PLAN_INPUT_FIELDS = frozenset(
    {
        "input_sequence",
        "input_registry_id",
        "source_id",
        "source_profile",
        "locator_commitment_sha256",
    }
)
_PLAN_FIELDS = frozenset(
    {
        "schema_version",
        "record_origin",
        "plan_id",
        "selection_method",
        "selection_seed_sha256",
        "required_profiles",
        "per_profile_quota",
        "input_count",
        "selected_inputs",
        "selected_input_set_sha256",
        "sampling_frame_sha256",
        "created_at",
        "labels_observed",
        "action_applied",
        "operational_effect",
        "artifact_sha256",
    }
)


def selected_input_projection(
    source_snapshots: Sequence[Mapping[str, Any]],
    *,
    expected_origin: str = ACTUAL_ORIGIN,
) -> list[dict[str, Any]]:
    """검증된 snapshot을 plan의 고정 입력 projection으로 변환한다."""

    rows = _validate_snapshots(source_snapshots, expected_origin)
    return [
        {
            "input_sequence": index,
            "input_registry_id": row["source_id"],
            "source_id": row["source_id"],
            "source_profile": row["source_profile"],
            "locator_commitment_sha256": canonical_sha256(
                {
                    "source_id": row["source_id"],
                    "platform": row["platform"],
                    "community_scope": row["community_scope"],
                    "canonical_url": row["canonical_url"],
                    "locator": row["locator"],
                }
            ),
        }
        for index, row in enumerate(rows, start=1)
    ]


def validate_source_input_plan(
    value: Any,
    source_snapshots: Sequence[Mapping[str, Any]],
    *,
    expected_origin: str = ACTUAL_ORIGIN,
) -> dict[str, Any]:
    """source snapshot 40건과 strict 입력 계획의 모든 binding을 검증한다."""

    row = _strict(value, _PLAN_FIELDS, "source input plan")
    if row["schema_version"] != SOURCE_INPUT_PLAN_SCHEMA:
        raise P0ActualRouteError("source input plan schema mismatch")
    _origin(row, expected_origin)
    _identifier(row["plan_id"], "plan_id")
    if row["selection_method"] != "CALLER_PRECOMMITTED_PROFILE_10X4_V1":
        raise P0ActualRouteError("source input selection method mismatch")
    _sha(row["selection_seed_sha256"], "selection_seed_sha256")
    if row["required_profiles"] != list(SOURCE_PROFILES):
        raise P0ActualRouteError("required_profiles must use the fixed ordered profiles")
    if row["per_profile_quota"] != EXPECTED_PER_PROFILE_QUOTA:
        raise P0ActualRouteError("per_profile_quota must be 10")
    if row["input_count"] != EXPECTED_INPUT_COUNT:
        raise P0ActualRouteError("input_count must be 40")
    _timestamp(row["created_at"], "created_at")
    if row["labels_observed"] is not False:
        raise P0ActualRouteError("source selection must be label blind")

    validate_exact_profile_quota(source_snapshots, expected_origin=expected_origin)
    profile_order = {profile: index for index, profile in enumerate(SOURCE_PROFILES)}
    source_rows = _validate_snapshots(source_snapshots, expected_origin)
    if source_rows != sorted(
        source_rows,
        key=lambda source: (
            profile_order[source["source_profile"]],
            source["source_id"],
        ),
    ):
        raise P0ActualRouteError("source inputs must use canonical profile/source order")
    expected_inputs = selected_input_projection(
        source_snapshots, expected_origin=expected_origin
    )
    if not isinstance(row["selected_inputs"], list):
        raise P0ActualRouteError("selected_inputs must be a list")
    inputs = [
        dict(_strict(item, _PLAN_INPUT_FIELDS, "selected input"))
        for item in row["selected_inputs"]
    ]
    for index, item in enumerate(inputs, start=1):
        if item["input_sequence"] != index:
            raise P0ActualRouteError("selected input sequence must be contiguous")
        _sha(item["locator_commitment_sha256"], "locator_commitment_sha256")
        for field in ("input_registry_id", "source_id"):
            _identifier(item[field], field)
        if item["input_registry_id"] != item["source_id"]:
            raise P0ActualRouteError("input registry id must bind the pre-capture source id")
        if item["source_profile"] not in SOURCE_PROFILES:
            raise P0ActualRouteError("selected input source_profile is invalid")
    if inputs != expected_inputs:
        raise P0ActualRouteError("selected inputs do not exactly bind supplied snapshots")
    if _sha(
        row["selected_input_set_sha256"], "selected_input_set_sha256"
    ) != canonical_sha256(inputs):
        raise P0ActualRouteError("selected input set binding mismatch")
    if _sha(row["sampling_frame_sha256"], "sampling_frame_sha256") != canonical_sha256(
        {
            "selection_seed_sha256": row["selection_seed_sha256"],
            "selected_inputs": inputs,
        }
    ):
        raise P0ActualRouteError("sampling frame binding mismatch")
    created = _timestamp(row["created_at"], "created_at")
    if any(
        created >= _timestamp(source["collected_at"], "collected_at")
        for source in source_rows
    ):
        raise P0ActualRouteError("source input plan must predate every capture")
    _no_write(row, "source input plan")
    _self_hash(row, "artifact_sha256", "source input plan")
    return dict(row)


_SEAL_FIELDS = frozenset(
    {
        "schema_version",
        "record_origin",
        "seal_id",
        "source_input_plan_sha256",
        "sampling_frame_sha256",
        "captured_source_registry_sha256",
        "selected_input_set_sha256",
        "claim_selection_policy_sha256",
        "claim_selection_seed_sha256",
        "selection_algorithm",
        "selection_basis_fields",
        "forbidden_label_fields_sha256",
        "observed_claim_unit_count",
        "selected_claim_count",
        "selected_claim_units",
        "selected_claim_units_sha256",
        "selected_profile_counts",
        "selection_complete",
        "labels_observed",
        "gold_artifact_sha256",
        "annotation_artifact_sha256",
        "sealed_at",
        "action_applied",
        "operational_effect",
        "artifact_sha256",
    }
)

_BLIND_CLAIM_UNIT_FIELDS = frozenset(
    {
        "claim_id",
        "registry_record_id",
        "registry_record_sha256",
        "snapshot_id",
        "source_profile",
        "response_sha256",
        "normalized_text_sha256",
        "span_start",
        "span_end",
        "span_sha256",
        "normalized_surface",
        "blind_claim_unit_sha256",
        "selection_rank_sha256",
    }
)


def blind_claim_sampling_unit(
    claim: Mapping[str, Any], source: Mapping[str, Any]
) -> tuple[Any, ...]:
    """human/gold label을 쓰지 않는 post-parse claim 선택 단위를 반환한다."""

    return (
        source["response_sha256"],
        source["normalized_text_sha256"],
        claim["span_start"],
        claim["span_end"],
        claim["span_sha256"],
        claim["normalized_surface"],
    )


def _blind_claim_projection(
    claim: Mapping[str, Any], source: Mapping[str, Any], selection_seed: str
) -> dict[str, Any]:
    unit_sha = canonical_sha256(list(blind_claim_sampling_unit(claim, source)))
    return {
        "claim_id": claim["claim_id"],
        "registry_record_id": claim["registry_record_id"],
        "registry_record_sha256": claim["registry_record_sha256"],
        "snapshot_id": claim["snapshot_id"],
        "source_profile": source["source_profile"],
        "response_sha256": source["response_sha256"],
        "normalized_text_sha256": source["normalized_text_sha256"],
        "span_start": claim["span_start"],
        "span_end": claim["span_end"],
        "span_sha256": claim["span_sha256"],
        "normalized_surface": claim["normalized_surface"],
        "blind_claim_unit_sha256": unit_sha,
        "selection_rank_sha256": canonical_sha256(
            {"selection_seed_sha256": selection_seed, "blind_claim_unit_sha256": unit_sha}
        ),
    }


def validate_exact_claim_profile_quota(
    selected_claim_units: Sequence[Mapping[str, Any]],
    source_snapshots: Sequence[Mapping[str, Any]],
    *,
    expected_origin: str = ACTUAL_ORIGIN,
    require_distinct_inputs: bool = False,
) -> dict[str, int]:
    """sealed claim→snapshot binding에서 정확한 profile 10x4를 역산한다.

    ``False`` 기본값은 archived v1 direct-caller 의미를 보존한다. 안전한 v2
    route validator는 source input별 최대 1 credit을 명시적으로 요구한다.
    """

    sources = _validate_snapshots(source_snapshots, expected_origin)
    source_by_id = {row["registry_record_id"]: row for row in sources}
    counts: Counter[str] = Counter()
    seen_units: set[str] = set()
    seen_registry_ids: set[str] = set()
    if not isinstance(selected_claim_units, Sequence) or isinstance(
        selected_claim_units, (str, bytes)
    ):
        raise P0ActualRouteError("selected claim units must be a sequence")
    for value in selected_claim_units:
        unit = _strict(value, _BLIND_CLAIM_UNIT_FIELDS, "selected claim unit")
        source = source_by_id.get(unit["registry_record_id"])
        if source is None:
            raise P0ActualRouteError("selected claim unit references unknown snapshot")
        for field in (
            "registry_record_sha256",
            "response_sha256",
            "normalized_text_sha256",
            "span_sha256",
            "blind_claim_unit_sha256",
            "selection_rank_sha256",
        ):
            _sha(unit[field], field)
        if (
            unit["registry_record_sha256"] != source["registry_record_sha256"]
            or unit["snapshot_id"] != source["snapshot_id"]
            or unit["source_profile"] != source["source_profile"]
            or unit["response_sha256"] != source["response_sha256"]
            or unit["normalized_text_sha256"]
            != source["normalized_text_sha256"]
        ):
            raise P0ActualRouteError("selected claim unit/snapshot binding mismatch")
        unit_sha = str(unit["blind_claim_unit_sha256"])
        expected_unit_sha = canonical_sha256(
            [unit[field] for field in SELECTION_BASIS_FIELDS]
        )
        if unit_sha != expected_unit_sha:
            raise P0ActualRouteError("selected blind claim unit hash mismatch")
        if unit_sha in seen_units:
            raise P0ActualRouteError("selected blind claim sampling unit must be unique")
        seen_units.add(unit_sha)
        registry_id = str(unit["registry_record_id"])
        if require_distinct_inputs and registry_id in seen_registry_ids:
            raise P0ActualRouteError(
                "selected claim quota must credit each source input at most once"
            )
        seen_registry_ids.add(registry_id)
        counts[str(source["source_profile"])] += 1
    expected = {profile: EXPECTED_PER_PROFILE_QUOTA for profile in SOURCE_PROFILES}
    if len(selected_claim_units) != EXPECTED_INPUT_COUNT or dict(counts) != expected:
        raise P0ActualRouteError(
            f"selected claim profile quota must be exact 10x4: actual={dict(counts)}"
        )
    return expected


def _validate_label_blind_selection_seal_version(
    value: Any,
    *,
    input_plan: Mapping[str, Any],
    source_snapshots: Sequence[Mapping[str, Any]],
    source_claims: Sequence[Mapping[str, Any]],
    expected_origin: str = ACTUAL_ORIGIN,
    seal_schema: str,
    selection_algorithm: str,
) -> dict[str, Any]:
    """label 접근 전 claim 입력 선택 봉인과 plan binding을 검증한다."""

    row = _strict(value, _SEAL_FIELDS, "label-blind selection seal")
    if row["schema_version"] != seal_schema:
        raise P0ActualRouteError("label-blind seal schema mismatch")
    _origin(row, expected_origin)
    _identifier(row["seal_id"], "seal_id")
    if _sha(row["source_input_plan_sha256"], "source_input_plan_sha256") != input_plan[
        "artifact_sha256"
    ]:
        raise P0ActualRouteError("seal/input plan binding mismatch")
    for field in ("sampling_frame_sha256", "selected_input_set_sha256"):
        if _sha(row[field], field) != input_plan[field]:
            raise P0ActualRouteError(f"seal/{field} binding mismatch")
    _sha(row["claim_selection_policy_sha256"], "claim_selection_policy_sha256")
    selection_seed = _sha(
        row["claim_selection_seed_sha256"], "claim_selection_seed_sha256"
    )
    if row["selection_algorithm"] != selection_algorithm:
        raise P0ActualRouteError("claim selection algorithm mismatch")
    if row["selection_basis_fields"] != list(SELECTION_BASIS_FIELDS):
        raise P0ActualRouteError("selection basis must use fixed non-label fields")
    if _sha(
        row["forbidden_label_fields_sha256"], "forbidden_label_fields_sha256"
    ) != FORBIDDEN_LABEL_FIELDS_SHA256:
        raise P0ActualRouteError("forbidden label field binding mismatch")
    sources = _validate_snapshots(source_snapshots, expected_origin)
    if _sha(
        row["captured_source_registry_sha256"], "captured_source_registry_sha256"
    ) != canonical_sha256(sources):
        raise P0ActualRouteError("seal/captured source registry binding mismatch")
    source_by_id = {source["registry_record_id"]: source for source in sources}
    claims = _validate_claim_inventory(source_claims, source_by_id, expected_origin)
    candidates = [
        _blind_claim_projection(claim, source_by_id[claim["registry_record_id"]], selection_seed)
        for claim in claims
    ]
    candidate_unit_shas = [item["blind_claim_unit_sha256"] for item in candidates]
    if len(set(candidate_unit_shas)) != len(candidate_unit_shas):
        raise P0ActualRouteError("blind claim sampling unit must be unique")
    by_profile: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in candidates:
        by_profile[item["source_profile"]].append(item)
    selected: list[dict[str, Any]] = []
    selected_counts: dict[str, int] = {}
    for profile in SOURCE_PROFILES:
        if selection_algorithm == SELECTION_ALGORITHM:
            by_input: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for item in by_profile[profile]:
                by_input[item["registry_record_id"]].append(item)
            # One source input is one sampling/credit unit even when the parser
            # emits 1:N claims.  Pick that input's deterministic representative
            # before ranking inputs, otherwise one prolific source can occupy
            # the whole profile quota and hide missing sources.
            representatives = [
                min(rows, key=lambda item: item["selection_rank_sha256"])
                for rows in by_input.values()
            ]
        else:
            # Archived v1 validation only.  Route completion never uses this
            # branch, but preserving it avoids silently redefining stored v1
            # seals after the source-credit inflation fix.
            representatives = list(by_profile[profile])
        ranked = sorted(
            representatives,
            key=lambda item: item["selection_rank_sha256"],
        )
        chosen = ranked[:EXPECTED_PER_PROFILE_QUOTA]
        selected.extend(chosen)
        selected_counts[profile] = len(chosen)
    selection_complete = all(
        selected_counts[profile] == EXPECTED_PER_PROFILE_QUOTA
        for profile in SOURCE_PROFILES
    )
    if row["observed_claim_unit_count"] != len(candidates):
        raise P0ActualRouteError("observed claim unit count mismatch")
    if row["selected_claim_count"] != len(selected):
        raise P0ActualRouteError("selected claim count mismatch")
    if not isinstance(row["selected_claim_units"], list) or row[
        "selected_claim_units"
    ] != selected:
        raise P0ActualRouteError("selected claims do not match deterministic rank")
    if _sha(
        row["selected_claim_units_sha256"], "selected_claim_units_sha256"
    ) != canonical_sha256(selected):
        raise P0ActualRouteError("selected claim unit set binding mismatch")
    if row["selected_profile_counts"] != selected_counts:
        raise P0ActualRouteError("selected claim profile counts mismatch")
    if row["selection_complete"] is not selection_complete:
        raise P0ActualRouteError("selection completeness projection mismatch")
    if selection_complete:
        validate_exact_claim_profile_quota(
            selected,
            source_snapshots,
            expected_origin=expected_origin,
            require_distinct_inputs=selection_algorithm == SELECTION_ALGORITHM,
        )
    if (
        row["labels_observed"] is not False
        or _optional_sha(row["gold_artifact_sha256"], "gold_artifact_sha256") is not None
        or _optional_sha(
            row["annotation_artifact_sha256"], "annotation_artifact_sha256"
        )
        is not None
    ):
        raise P0ActualRouteError("selection seal must be label blind")
    sealed_at = _timestamp(row["sealed_at"], "sealed_at")
    if sealed_at < _timestamp(input_plan["created_at"], "created_at"):
        raise P0ActualRouteError("selection seal cannot predate input plan")
    if any(
        sealed_at <= _timestamp(source["collected_at"], "collected_at")
        for source in sources
    ):
        raise P0ActualRouteError("post-parse selection seal must follow every capture")
    _no_write(row, "label-blind selection seal")
    _self_hash(row, "artifact_sha256", "label-blind selection seal")
    return dict(row)


def validate_label_blind_selection_seal(
    value: Any,
    *,
    input_plan: Mapping[str, Any],
    source_snapshots: Sequence[Mapping[str, Any]],
    source_claims: Sequence[Mapping[str, Any]],
    expected_origin: str = ACTUAL_ORIGIN,
) -> dict[str, Any]:
    """Validate the v2 one-source/one-credit seal used by route completion."""

    return _validate_label_blind_selection_seal_version(
        value,
        input_plan=input_plan,
        source_snapshots=source_snapshots,
        source_claims=source_claims,
        expected_origin=expected_origin,
        seal_schema=LABEL_BLIND_SEAL_SCHEMA,
        selection_algorithm=SELECTION_ALGORITHM,
    )


def validate_label_blind_selection_seal_v1(
    value: Any,
    *,
    input_plan: Mapping[str, Any],
    source_snapshots: Sequence[Mapping[str, Any]],
    source_claims: Sequence[Mapping[str, Any]],
    expected_origin: str = ACTUAL_ORIGIN,
) -> dict[str, Any]:
    """Validate archived v1 bytes without making them route-complete."""

    return _validate_label_blind_selection_seal_version(
        value,
        input_plan=input_plan,
        source_snapshots=source_snapshots,
        source_claims=source_claims,
        expected_origin=expected_origin,
        seal_schema=LABEL_BLIND_SEAL_SCHEMA_V1,
        selection_algorithm=SELECTION_ALGORITHM_V1,
    )


_TERMINAL_FIELDS = frozenset(
    {
        "schema_version",
        "record_origin",
        "terminal_id",
        "parser_run_id",
        "source_input_plan_sha256",
        "registry_record_id",
        "registry_record_sha256",
        "snapshot_id",
        "source_profile",
        "response_sha256",
        "terminal_disposition",
        "reason_code",
        "error_class",
        "error_detail_sha256",
        "action_applied",
        "operational_effect",
        "row_sha256",
    }
)
_PARSER_ERROR_REASONS = {
    "input_payload_unavailable",
    "parser_internal_error",
    "parser_output_unbound",
    "parser_schema_error",
    "parser_timeout",
}


def validate_terminal_queue_row(
    value: Any, *, expected_origin: str = ACTUAL_ORIGIN
) -> dict[str, Any]:
    """generic/error terminal queue 한 행을 strict schema로 검증한다."""

    row = _strict(value, _TERMINAL_FIELDS, "terminal queue row")
    if row["schema_version"] != TERMINAL_QUEUE_SCHEMA:
        raise P0ActualRouteError("terminal queue schema mismatch")
    _origin(row, expected_origin)
    for field in (
        "terminal_id",
        "parser_run_id",
        "registry_record_id",
        "snapshot_id",
    ):
        _identifier(row[field], field)
    for field in (
        "source_input_plan_sha256",
        "registry_record_sha256",
        "response_sha256",
    ):
        _sha(row[field], field)
    if row["source_profile"] not in SOURCE_PROFILES:
        raise P0ActualRouteError("terminal source_profile is invalid")
    if row["terminal_disposition"] not in TERMINAL_DISPOSITIONS:
        raise P0ActualRouteError("terminal disposition is invalid")
    reason = _text(row["reason_code"], "reason_code")
    error_class = _optional_text(row["error_class"], "error_class")
    error_detail = _optional_sha(row["error_detail_sha256"], "error_detail_sha256")
    if row["terminal_disposition"] == "GENERIC_PENDING":
        if (
            row["source_profile"] != "GENERIC_FALLBACK"
            or reason != "generic_profile_requires_manual_queue"
            or error_class is not None
            or error_detail is not None
        ):
            raise P0ActualRouteError("generic terminal fields mismatch")
    elif reason not in _PARSER_ERROR_REASONS or error_class is None or error_detail is None:
        raise P0ActualRouteError("parser error terminal requires bounded error witness")
    _no_write(row, "terminal queue row")
    _self_hash(row, "row_sha256", "terminal queue row")
    return dict(row)


def claim_sampling_unit(claim: Mapping[str, Any]) -> tuple[Any, ...]:
    """ID 재발급으로 우회할 수 없는 claim sampling unit을 반환한다."""

    return (
        claim["registry_record_id"],
        claim["span_start"],
        claim["span_end"],
        claim["claim_kind"],
        claim["claim_direction"],
        claim["normalized_surface"],
        claim["target_work_id"],
        claim["target_sense_id"],
        claim["definition"],
    )


def _validate_claim_inventory(
    claims: Sequence[Mapping[str, Any]],
    source_by_id: Mapping[str, Mapping[str, Any]],
    expected_origin: str,
) -> list[dict[str, Any]]:
    parsed: list[dict[str, Any]] = []
    for value in claims:
        if not isinstance(value, Mapping):
            raise P0ActualRouteError("source claim must be an object")
        source = source_by_id.get(value.get("registry_record_id"))
        if source is None:
            raise P0ActualRouteError("claim references an unselected registry input")
        try:
            row = registry_contract._validate_source_claim(
                value,
                expected_origin,
                response_sha256=source["response_sha256"],
            )
        except registry_contract.P0ActualContractError as exc:
            raise P0ActualRouteError(f"source claim invalid: {exc}") from exc
        if (
            row["registry_record_sha256"] != source["registry_record_sha256"]
            or row["snapshot_id"] != source["snapshot_id"]
            or row["parser_profile"] != source["source_profile"].lower()
        ):
            raise P0ActualRouteError("claim/source snapshot binding mismatch")
        parsed.append(row)
    if len({row["claim_id"] for row in parsed}) != len(parsed):
        raise P0ActualRouteError("claim_id must be unique")
    units = [claim_sampling_unit(row) for row in parsed]
    if len(set(units)) != len(units):
        raise P0ActualRouteError("claim sampling unit must be unique")
    return parsed


def _partition_claim_inventory(
    claims: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    typed: list[dict[str, Any]] = []
    generic: list[dict[str, Any]] = []
    for row in claims:
        if row["claim_kind"] == "UNKNOWN":
            if row["parse_disposition"] != "GENERIC_PENDING":
                raise P0ActualRouteError(
                    "generic selection claim must remain GENERIC_PENDING"
                )
            generic.append(dict(row))
        else:
            if row["parse_disposition"] != "PARSED":
                raise P0ActualRouteError("typed route may contain only parsed claims")
            typed.append(dict(row))
    return typed, generic


def validate_route_bundle(
    *,
    source_snapshots: Sequence[Mapping[str, Any]],
    input_plan: Mapping[str, Any],
    selection_seal: Mapping[str, Any],
    source_claims: Sequence[Mapping[str, Any]],
    terminal_rows: Sequence[Mapping[str, Any]],
    parser_receipt: Mapping[str, Any] | None = None,
    expected_origin: str = ACTUAL_ORIGIN,
) -> dict[str, Any]:
    """40개 입력의 exact-one route와 parser v2 1:N 회계를 함께 검증한다."""

    plan = validate_source_input_plan(
        input_plan, source_snapshots, expected_origin=expected_origin
    )
    seal = validate_label_blind_selection_seal(
        selection_seal,
        input_plan=plan,
        source_snapshots=source_snapshots,
        source_claims=source_claims,
        expected_origin=expected_origin,
    )
    sources = _validate_snapshots(source_snapshots, expected_origin)
    source_by_id = {row["registry_record_id"]: row for row in sources}
    claim_inventory = _validate_claim_inventory(
        source_claims, source_by_id, expected_origin
    )
    claims, generic_claims = _partition_claim_inventory(claim_inventory)
    terminals = [
        validate_terminal_queue_row(row, expected_origin=expected_origin)
        for row in terminal_rows
    ]
    if len({row["terminal_id"] for row in terminals}) != len(terminals):
        raise P0ActualRouteError("terminal_id must be unique")
    terminal_by_input: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in terminals:
        source = source_by_id.get(row["registry_record_id"])
        if source is None:
            raise P0ActualRouteError("terminal row references an unselected registry input")
        if (
            row["source_input_plan_sha256"] != plan["artifact_sha256"]
            or row["registry_record_sha256"] != source["registry_record_sha256"]
            or row["snapshot_id"] != source["snapshot_id"]
            or row["source_profile"] != source["source_profile"]
            or row["response_sha256"] != source["response_sha256"]
        ):
            raise P0ActualRouteError("terminal/source input binding mismatch")
        terminal_by_input[row["registry_record_id"]].append(row)
    claims_by_input: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in claims:
        claims_by_input[row["registry_record_id"]].append(row)
    generic_claims_by_input: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in generic_claims:
        generic_claims_by_input[row["registry_record_id"]].append(row)

    classifications: list[dict[str, str]] = []
    for source in sources:
        registry_id = source["registry_record_id"]
        typed = claims_by_input.get(registry_id, [])
        generic_units = generic_claims_by_input.get(registry_id, [])
        terminal = terminal_by_input.get(registry_id, [])
        if bool(typed) == bool(terminal) or len(terminal) > 1:
            raise P0ActualRouteError(
                "each registry input must have exactly one terminal route class"
            )
        if typed:
            route_class = "TYPED"
            if source["source_profile"] == "GENERIC_FALLBACK" or generic_units:
                raise P0ActualRouteError("generic fallback input cannot become typed")
        else:
            route_class = terminal[0]["terminal_disposition"]
            if route_class == "GENERIC_PENDING" and source[
                "source_profile"
            ] != "GENERIC_FALLBACK":
                raise P0ActualRouteError("structured input cannot enter generic queue")
            if route_class == "GENERIC_PENDING" and len(generic_units) != 1:
                raise P0ActualRouteError(
                    "generic terminal requires exactly one sealed generic claim unit"
                )
            if route_class == "PARSER_ERROR" and generic_units:
                raise P0ActualRouteError(
                    "parser error input cannot carry a generic claim unit"
                )
        classifications.append(
            {"registry_record_id": registry_id, "route_class": route_class}
        )

    parser_run_ids = {
        row["parser_run_id"] for row in [*claim_inventory, *terminals]
    }
    if len(parser_run_ids) != 1:
        raise P0ActualRouteError("all route outputs must share one parser_run_id")
    parser_manifest_sha256s = {
        row["parser_manifest_sha256"] for row in claim_inventory
    }
    parser_versions = {row["parser_version"] for row in claim_inventory}
    if len(parser_manifest_sha256s) != 1 or len(parser_versions) != 1:
        raise P0ActualRouteError(
            "all parser claim rows must share one parser manifest and version"
        )
    parser_manifest_sha256 = next(iter(parser_manifest_sha256s))
    parser_version = next(iter(parser_versions))
    typed_input_count = sum(
        item["route_class"] == "TYPED" for item in classifications
    )
    generic_count = sum(
        item["route_class"] == "GENERIC_PENDING" for item in classifications
    )
    error_count = sum(
        item["route_class"] == "PARSER_ERROR" for item in classifications
    )
    if typed_input_count + generic_count + error_count != EXPECTED_INPUT_COUNT:
        raise P0ActualRouteError("route exact accounting mismatch")
    if len(claims) < typed_input_count:
        raise P0ActualRouteError("1:N claim accounting cannot undercount typed inputs")

    parser_generic_queue_material = {
        "terminal_rows": terminals,
        "generic_claim_rows": generic_claims,
    }

    parser_verified = False
    parser_runtime_status: str | None = None
    parser_runtime_noninterference_verified = False
    parser_launch_sha256: str | None = None
    parser_capture_manifest_sha256: str | None = None
    if expected_origin == ACTUAL_ORIGIN and parser_receipt is None:
        raise P0ActualRouteError("actual route bundle requires parser receipt v2")
    if parser_receipt is not None:
        authority_origin = (
            authority_contract.ACTUAL_ORIGIN
            if expected_origin == ACTUAL_ORIGIN
            else authority_contract.EXAMPLE_ORIGIN
        )
        try:
            runtime = authority_contract.validate_parser_receipt(
                parser_receipt, authority_origin
            )
        except authority_contract.P0ActualAuthorityError as exc:
            raise P0ActualRouteError(f"parser receipt invalid: {exc}") from exc
        expected_counts = {
            "input_count": EXPECTED_INPUT_COUNT,
            "processed_count": EXPECTED_INPUT_COUNT,
            "typed_input_count": typed_input_count,
            "claim_row_count": len(claims),
            "generic_count": generic_count,
            "error_count": error_count,
        }
        if any(runtime[field] != count for field, count in expected_counts.items()):
            raise P0ActualRouteError("parser receipt/route count binding mismatch")
        if (
            runtime["parser_run_id"] not in parser_run_ids
            or runtime["input_registry_sha256"]
            != seal["captured_source_registry_sha256"]
            or runtime["output_claims_sha256"] != canonical_sha256(claims)
            or runtime["generic_queue_sha256"]
            != canonical_sha256(parser_generic_queue_material)
            or runtime["exact_accounting_verified"] is not True
        ):
            raise P0ActualRouteError("parser receipt/route artifact binding mismatch")
        if expected_origin == ACTUAL_ORIGIN and _timestamp(
            runtime["started_at"], "started_at"
        ) < max(
            _timestamp(source["collected_at"], "collected_at")
            for source in sources
        ):
            raise P0ActualRouteError("parser cannot start before every source capture")
        if _timestamp(runtime["completed_at"], "completed_at") >= _timestamp(
            seal["sealed_at"], "sealed_at"
        ):
            raise P0ActualRouteError(
                "selection seal must strictly follow parser completion"
            )
        parser_verified = True
        parser_runtime_status = runtime["runtime_status"]
        parser_runtime_noninterference_verified = runtime[
            "runtime_noninterference_verified"
        ]
        parser_launch_sha256 = runtime["launch_sha256"]
        parser_capture_manifest_sha256 = runtime["capture_manifest_sha256"]

    route_accounting_packet_complete = (
        parser_verified
        and parser_runtime_status == "COMPLETE"
        and parser_runtime_noninterference_verified
        and error_count == 0
        and seal["selection_complete"] is True
    )

    return {
        "schema_version": ROUTE_RECEIPT_SCHEMA,
        "record_origin": expected_origin,
        "source_input_plan_sha256": plan["artifact_sha256"],
        "selection_seal_sha256": seal["artifact_sha256"],
        "selection_seal_schema_version": seal["schema_version"],
        "selection_algorithm": seal["selection_algorithm"],
        "sampling_frame_sha256": plan["sampling_frame_sha256"],
        "captured_source_registry_sha256": seal[
            "captured_source_registry_sha256"
        ],
        "route_classifications_sha256": canonical_sha256(classifications),
        "output_claims_sha256": canonical_sha256(claims),
        "terminal_queue_sha256": canonical_sha256(terminals),
        "generic_claim_rows_sha256": canonical_sha256(generic_claims),
        "parser_generic_queue_sha256": canonical_sha256(
            parser_generic_queue_material
        ),
        "parser_manifest_sha256": parser_manifest_sha256,
        "parser_version": parser_version,
        "input_count": EXPECTED_INPUT_COUNT,
        "typed_input_count": typed_input_count,
        "claim_row_count": len(claims),
        "observed_claim_unit_count": len(claim_inventory),
        "selected_claim_count": seal["selected_claim_count"],
        "selected_claim_units_sha256": seal["selected_claim_units_sha256"],
        "selection_complete": seal["selection_complete"],
        "generic_count": generic_count,
        "error_count": error_count,
        "exact_accounting_verified": True,
        "label_blind_selection_verified": True,
        "parser_receipt_verified": parser_verified,
        "parser_runtime_status": parser_runtime_status,
        "parser_runtime_noninterference_verified": (
            parser_runtime_noninterference_verified
        ),
        "parser_launch_sha256": parser_launch_sha256,
        "parser_capture_manifest_sha256": parser_capture_manifest_sha256,
        "route_accounting_packet_complete": route_accounting_packet_complete,
        "gate_status": "NO_GO_ROUTE_CONTRACT_ONLY",
        "actual_authority_granted": False,
        "production_approval": False,
        "full_scan_approval": False,
        "action_applied": False,
        "operational_effect": OPERATIONAL_EFFECT,
    }
