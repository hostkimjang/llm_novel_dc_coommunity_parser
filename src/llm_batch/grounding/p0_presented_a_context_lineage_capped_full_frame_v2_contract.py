"""제시된 A-context를 source lineage 단위로 제한하는 additive V2 계약.

이 모듈은 V1 A-context census를 다시 해석하거나 수정하지 않는다. 검증된
source-frame V2와 registry/capture bridge에 연결된 V1 context를 source
lineage별로 묶고, lineage를 먼저 뽑은 뒤 그 lineage 안에서 context 하나를
뽑는 제시 전용 2단계 계획을 만든다. 외부 lineage 사실성, seed 권위, 실제
review/metric, publication, production 권한은 부여하지 않는다.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from fractions import Fraction
import base64
import hashlib
import json
import re
import unicodedata
from typing import Any, Mapping, Sequence

from . import p0_full_eligible_sampling_frame_v2_contract as source_v2
from . import p0_presented_batch_exact_accounting_v1_contract as bridge_v1
from . import p0_presented_a_context_full_frame_v1_contract as a_v1


FRAME_SCHEMA = "p0_presented_a_context_lineage_capped_frame_v2"
SEED_SCHEMA = "p0_presented_a_context_lineage_capped_seed_receipt_v2"
PLAN_SCHEMA = "p0_presented_a_context_lineage_capped_plan_v2"
COMPONENT_MANIFEST_SCHEMA = "p0_presented_a_context_lineage_capped_component_manifest_v2"
COMPONENT_VERSION = "presented-a-context-lineage-capped-full-frame-v2"
RECORD_ORIGIN = "ACTUAL_SCHEMA_CONTRACT_EXAMPLE_ONLY"
OPERATIONAL_EFFECT = "NONE_SHADOW_ONLY"
GATE_STATUS = "NO_GO_PRESENTED_LINEAGE_CAPPED_FRAME_ONLY"
METRIC_STATUS = "NOT_ESTIMABLE_LINEAGE_CAPPED_PRESENTED_FRAME_ONLY"
SELECTION_ALGORITHM = "SHA256_TWO_STAGE_LINEAGE_THEN_CONTEXT_SRSWOR_V2"
LINEAGE_RANK_DOMAIN = "P0_PRESENTED_A_CONTEXT_LINEAGE_CAPPED_V2_LINEAGE_RANK"
CONTEXT_RANK_DOMAIN = "P0_PRESENTED_A_CONTEXT_LINEAGE_CAPPED_V2_CONTEXT_RANK"
SEED_DERIVATION_DOMAIN = "P0_PRESENTED_A_CONTEXT_LINEAGE_CAPPED_V2_DERIVED_SEED"
SEED_DERIVATION_INPUTS = (
    "component_manifest_sha256", "future_seed_spec_sha256",
    "revealed_seed_sha256", "frame_owner_precommit_sha256",
)
REPLAY_DOMAIN = "P0_PRESENTED_A_CONTEXT_LINEAGE_CAPPED_V2_REPLAY"
EXPECTED_PER_PROFILE_QUOTA = 5
EXPECTED_TOTAL_QUOTA = 20
MAX_SELECTED_PER_SOURCE_LINEAGE = 1

SOURCE_COMPONENT_MANIFEST_SHA256 = "efed07649c14cc2af0b0916ef6e6a04b39ad0c9147b97daec74428521287111b"
BRIDGE_COMPONENT_MANIFEST_SHA256 = "c7beb367d62a4af025643d42caddf20caccb4938cd5a68dac8b649ee49b165c1"
A_V1_COMPONENT_MANIFEST_SHA256 = "5b38f560cbe6c2af9294e79ad6298b798e7256426c2e1ca353162e7531c47aa9"

MAX_OBJECT_BYTES = 64 * 1024 * 1024
MAX_AGGREGATE_RAW_BYTES = 192 * 1024 * 1024
MAX_ROWS = 1_000_000
MAX_ID_CHARS = 512
MAX_BRIDGE_JSONL_BYTES = 16 * 1024 * 1024

SOURCE_RAW_KEYS = (
    "source_scope_raw", "source_census_raw", "source_frame_raw",
    "source_seed_raw", "source_plan_raw",
)
A_RAW_KEYS = ("a_scope_raw", "a_census_raw", "a_frame_raw", "a_seed_raw", "a_plan_raw")
PRESEED_RAW_KEYS = (*SOURCE_RAW_KEYS, "bridge_inventory_raw", "a_scope_raw", "a_census_raw", "a_frame_raw")
ALL_RAW_KEYS = (*SOURCE_RAW_KEYS, "bridge_inventory_raw", *A_RAW_KEYS)

FALSE_AUTHORITY_FIELDS = (
    "external_owner_authority_verified", "lineage_factual_authority_verified",
    "enumeration_completeness_authority_verified", "rights_authority_verified",
    "capture_authority_verified", "seed_authority_verified",
    "seed_randomness_authority_verified", "trusted_time_verified",
    "runtime_execution_verified", "code_identity_verified",
    "same_process_isolation_verified", "actual_source_evidence_verified",
    "actual_a_context_review_credited", "descriptive_metrics_allowed",
    "inferential_metrics_allowed", "complete_case_metrics_allowed",
    "semantic_claims_allowed", "write_authority_granted", "p0_phase_exit",
    "production_approval", "full_scan_approval", "action_applied",
)

_SHA_RE = re.compile(r"^[0-9a-f]{64}$")
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,511}$")


class P0PresentedAContextLineageCappedV2Error(ValueError):
    pass


def canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (RecursionError, UnicodeEncodeError, TypeError, ValueError) as exc:
        raise P0PresentedAContextLineageCappedV2Error("canonical JSON invalid") from exc


def canonical_file_bytes(value: Any) -> bytes:
    return canonical_bytes(value) + b"\n"


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def raw_sha256(raw: bytes) -> str:
    if type(raw) is not bytes:
        raise P0PresentedAContextLineageCappedV2Error("raw input must be exact bytes")
    return hashlib.sha256(raw).hexdigest()


def with_self_hash(value: Mapping[str, Any], field: str = "artifact_sha256") -> dict[str, Any]:
    material = dict(value)
    material.pop(field, None)
    return {**material, field: canonical_sha256(material)}


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise P0PresentedAContextLineageCappedV2Error(f"duplicate JSON key: {key}")
        out[key] = value
    return out


def _constant(value: str) -> None:
    raise P0PresentedAContextLineageCappedV2Error(f"non-finite JSON constant: {value}")


def _object(raw: bytes, label: str) -> dict[str, Any]:
    if type(raw) is not bytes or not raw or len(raw) > MAX_OBJECT_BYTES or raw.startswith(b"\xef\xbb\xbf") or b"\r" in raw or not raw.endswith(b"\n"):
        raise P0PresentedAContextLineageCappedV2Error(f"{label} framing invalid")
    try:
        text = raw.decode("utf-8", errors="strict")
        if unicodedata.normalize("NFC", text) != text:
            raise P0PresentedAContextLineageCappedV2Error(f"{label} must be NFC")
        value = json.loads(text, object_pairs_hook=_pairs, parse_constant=_constant)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValueError) as exc:
        raise P0PresentedAContextLineageCappedV2Error(f"{label} JSON invalid") from exc
    if type(value) is not dict or canonical_file_bytes(value) != raw:
        raise P0PresentedAContextLineageCappedV2Error(f"{label} must be canonical object bytes")
    return value


def _strict(value: Any, fields: frozenset[str], label: str) -> dict[str, Any]:
    if type(value) is not dict or frozenset(value) != fields:
        raise P0PresentedAContextLineageCappedV2Error(f"{label} fields mismatch")
    return value


def _sha(value: Any, field: str) -> str:
    if type(value) is not str or _SHA_RE.fullmatch(value) is None:
        raise P0PresentedAContextLineageCappedV2Error(f"{field} must be lowercase SHA-256")
    return value


def _identifier(value: Any, field: str) -> str:
    if type(value) is not str or len(value) > MAX_ID_CHARS or _ID_RE.fullmatch(value) is None:
        raise P0PresentedAContextLineageCappedV2Error(f"{field} is invalid")
    return value


def _integer(value: Any, field: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise P0PresentedAContextLineageCappedV2Error(f"{field} must be integer >= {minimum}")
    return value


def _boolean(value: Any, field: str) -> bool:
    if type(value) is not bool:
        raise P0PresentedAContextLineageCappedV2Error(f"{field} must be boolean")
    return value


def _timestamp(value: Any, field: str) -> datetime:
    if type(value) is not str or not value.endswith("Z") or len(value) > 64:
        raise P0PresentedAContextLineageCappedV2Error(f"{field} must be UTC Z time")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise P0PresentedAContextLineageCappedV2Error(f"{field} invalid") from exc
    if parsed.isoformat().replace("+00:00", "Z") != value:
        raise P0PresentedAContextLineageCappedV2Error(f"{field} noncanonical")
    return parsed


def _self_hash(row: Mapping[str, Any], field: str, label: str) -> None:
    _sha(row[field], field)
    if canonical_sha256({key: value for key, value in row.items() if key != field}) != row[field]:
        raise P0PresentedAContextLineageCappedV2Error(f"{label} self hash mismatch")


def _false_authority(row: Mapping[str, Any], label: str) -> None:
    for field in FALSE_AUTHORITY_FIELDS:
        if _boolean(row[field], field) is not False:
            raise P0PresentedAContextLineageCappedV2Error(f"{label} must keep {field}=false")


def _preflight(raws: Mapping[str, bytes], keys: Sequence[str]) -> dict[str, bytes]:
    if type(raws) is not dict or tuple(raws) != tuple(keys):
        raise P0PresentedAContextLineageCappedV2Error("raw role order/membership mismatch")
    total = 0
    snap: dict[str, bytes] = {}
    for key in keys:
        value = raws[key]
        if type(value) is not bytes or not value or len(value) > MAX_OBJECT_BYTES:
            raise P0PresentedAContextLineageCappedV2Error(f"{key} byte bound/type mismatch")
        if key == "bridge_inventory_raw" and len(value) > MAX_BRIDGE_JSONL_BYTES:
            raise P0PresentedAContextLineageCappedV2Error("bridge inventory role byte bound exceeded")
        total += len(value)
        if total > MAX_AGGREGATE_RAW_BYTES:
            raise P0PresentedAContextLineageCappedV2Error("aggregate raw byte bound exceeded")
        snap[key] = value
    return snap


def _artifact_preflight(*artifacts: tuple[str, bytes]) -> None:
    total = 0
    for label, raw in artifacts:
        if type(raw) is not bytes or not raw or len(raw) > MAX_OBJECT_BYTES:
            raise P0PresentedAContextLineageCappedV2Error(
                f"{label} byte bound/type mismatch"
            )
        total += len(raw)
        if total > MAX_AGGREGATE_RAW_BYTES:
            raise P0PresentedAContextLineageCappedV2Error(
                "new artifact aggregate byte bound exceeded"
            )


def _rows(raw: bytes, label: str) -> list[dict[str, Any]]:
    if type(raw) is not bytes or not raw or len(raw) > MAX_OBJECT_BYTES or b"\r" in raw or not raw.endswith(b"\n"):
        raise P0PresentedAContextLineageCappedV2Error(f"{label} framing invalid")
    result: list[dict[str, Any]] = []
    offset = 0
    for index, line in enumerate(raw.splitlines(keepends=True), start=1):
        if index > MAX_ROWS or len(line) > MAX_OBJECT_BYTES:
            raise P0PresentedAContextLineageCappedV2Error(f"{label} row bound exceeded")
        offset += len(line)
        result.append(_object(line, f"{label} row {index}"))
    if offset != len(raw):
        raise P0PresentedAContextLineageCappedV2Error(f"{label} byte accounting mismatch")
    return result


def _source_plan(raws: Mapping[str, bytes]) -> dict[str, Any]:
    if source_v2.COMPONENT_MANIFEST_SHA256 != SOURCE_COMPONENT_MANIFEST_SHA256:
        raise P0PresentedAContextLineageCappedV2Error("source predecessor manifest drift")
    return source_v2.validate_sampling_plan_bytes(
        raws["source_plan_raw"], raws["source_scope_raw"], raws["source_census_raw"],
        raws["source_seed_raw"], raws["source_frame_raw"],
    )


def _a_chain(raws: Mapping[str, bytes], *, require_plan: bool) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    if a_v1.COMPONENT_MANIFEST_SHA256 != A_V1_COMPONENT_MANIFEST_SHA256:
        raise P0PresentedAContextLineageCappedV2Error("A V1 predecessor manifest drift")
    scope = a_v1.validate_scope_bytes(raws["a_scope_raw"])
    census = a_v1.validate_census_bytes(raws["a_census_raw"], raws["a_scope_raw"])
    frame = a_v1.validate_frame_manifest_bytes(raws["a_frame_raw"], raws["a_scope_raw"], raws["a_census_raw"])
    if require_plan:
        a_v1.validate_seed_receipt_bytes(raws["a_seed_raw"], raws["a_scope_raw"], raws["a_frame_raw"], raws["a_census_raw"])
        a_v1.validate_sampling_plan_bytes(raws["a_plan_raw"], raws["a_scope_raw"], raws["a_census_raw"], raws["a_seed_raw"], raws["a_frame_raw"])
    return scope, census, frame


def _bridge_rows(raws: Mapping[str, bytes], plan: Mapping[str, Any]) -> list[dict[str, Any]]:
    if bridge_v1.COMPONENT_MANIFEST_SHA256 != BRIDGE_COMPONENT_MANIFEST_SHA256:
        raise P0PresentedAContextLineageCappedV2Error("bridge predecessor manifest drift")
    rows, _, _ = bridge_v1._validate_bridge_rows(raws["bridge_inventory_raw"], plan)
    return rows


def _bound_state(raws: Mapping[str, bytes], *, require_a_plan: bool) -> dict[str, Any]:
    plan = _source_plan(raws)
    source_census_rows = source_v2.validate_census_bytes(
        raws["source_census_raw"], raws["source_scope_raw"]
    )
    a_scope, a_rows, a_frame = _a_chain(raws, require_plan=require_a_plan)
    bridge_rows = _bridge_rows(raws, plan)
    if a_scope["upstream_source_sampling_plan_raw_sha256"] != raw_sha256(raws["source_plan_raw"]):
        raise P0PresentedAContextLineageCappedV2Error("A scope/source plan binding mismatch")
    if a_scope["upstream_bridge_inventory_raw_sha256"] != raw_sha256(raws["bridge_inventory_raw"]):
        raise P0PresentedAContextLineageCappedV2Error("A scope/bridge binding mismatch")
    if _timestamp(plan["selection_sealed_at"], "source selection_sealed_at") >= _timestamp(a_scope["created_at"], "A created_at"):
        raise P0PresentedAContextLineageCappedV2Error("source plan must precede A scope creation")
    source_by_id = {row["candidate_id"]: row for row in plan["selected_inputs"]}
    source_census_by_id = {row["candidate_id"]: row for row in source_census_rows}
    bridge_by_id = {row["candidate_id"]: row for row in bridge_rows}
    if len(source_by_id) != len(plan["selected_inputs"]) or len(bridge_by_id) != len(bridge_rows):
        raise P0PresentedAContextLineageCappedV2Error("predecessor selected identity duplicate")
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    enriched: list[dict[str, Any]] = []
    for row in a_rows:
        source = source_by_id.get(row["upstream_frame_candidate_id"])
        bridge = bridge_by_id.get(row["upstream_frame_candidate_id"])
        if source is None or bridge is None:
            raise P0PresentedAContextLineageCappedV2Error("A row upstream candidate is not selected/bridged")
        source_candidate = source_census_by_id.get(source["candidate_id"])
        if source_candidate is None:
            raise P0PresentedAContextLineageCappedV2Error("selected source candidate is absent from census")
        try:
            payload_text = base64.b64decode(
                bridge["payload_base64"].encode("ascii"), validate=True
            ).decode("utf-8", errors="strict")
        except (AttributeError, UnicodeDecodeError, UnicodeEncodeError, ValueError) as exc:
            raise P0PresentedAContextLineageCappedV2Error("bridged A payload must be canonical UTF-8 text") from exc
        start, end = row["surface_start"], row["surface_end"]
        if type(start) is not int or type(end) is not int or start < 0 or end <= start or end > len(payload_text):
            raise P0PresentedAContextLineageCappedV2Error("A surface span is outside bridged payload")
        expected = {
            "registry_record_id": bridge["registry_record_id"], "adapter_id": source["adapter_id"],
            "platform_scope": source["platform"], "payload_sha256": bridge["payload_sha256"],
            "source_profile": source["source_profile"], "utc_day": source["utc_day"],
            "content_fingerprint": canonical_sha256(payload_text),
            "surface_sha256": canonical_sha256(payload_text[start:end]),
            "context_observed_at": source_candidate["observed_at"],
            "source_published_at": source_candidate["published_at"],
        }
        if any(row[field] != value for field, value in expected.items()):
            raise P0PresentedAContextLineageCappedV2Error("A row/source/bridge cross binding mismatch")
        item = {
            "candidate_id": row["candidate_id"], "context_unit_sha256": row["context_unit_sha256"],
            "source_frame_candidate_id": source["candidate_id"],
            "source_lineage_group_id": source["lineage_group_id"],
            "source_lineage_unit_sha256": source["lineage_unit_sha256"],
            "source_profile": source["source_profile"], "platform_scope": source["platform"],
            "utc_day": source["utc_day"], "adapter_id": source["adapter_id"],
            "eligibility_status": row["eligibility_status"],
        }
        enriched.append(item)
        if row["eligibility_status"] == "ELIGIBLE":
            groups[item["source_lineage_unit_sha256"]].append(item)
    if len(enriched) > MAX_ROWS:
        raise P0PresentedAContextLineageCappedV2Error("A census row bound exceeded")
    eligible = [row for row in enriched if row["eligibility_status"] == "ELIGIBLE"]
    strata = {(x["source_profile"], x["platform_scope"], x["utc_day"]): x["quota"] for x in a_scope["strata"]}
    lineages_by_stratum: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    inventory: list[dict[str, Any]] = []
    seen_groups: set[str] = set()
    for unit, members in groups.items():
        members.sort(key=lambda x: x["candidate_id"])
        first = members[0]
        if any((m["source_profile"], m["platform_scope"], m["utc_day"], m["source_lineage_group_id"]) != (first["source_profile"], first["platform_scope"], first["utc_day"], first["source_lineage_group_id"]) for m in members):
            raise P0PresentedAContextLineageCappedV2Error("source lineage crosses strata or group identity")
        if first["source_lineage_group_id"] in seen_groups:
            raise P0PresentedAContextLineageCappedV2Error("source lineage group splits across units")
        seen_groups.add(first["source_lineage_group_id"])
        key = (first["source_profile"], first["platform_scope"], first["utc_day"])
        if key not in strata:
            raise P0PresentedAContextLineageCappedV2Error("eligible lineage outside fixed strata")
        lineages_by_stratum[key].append(unit)
        inventory.append({
            "source_lineage_unit_sha256": unit,
            "source_lineage_group_id": first["source_lineage_group_id"],
            "source_frame_candidate_id": first["source_frame_candidate_id"],
            "source_profile": first["source_profile"], "platform_scope": first["platform_scope"],
            "utc_day": first["utc_day"], "eligible_context_count": len(members),
            "eligible_context_set_sha256": canonical_sha256([m["context_unit_sha256"] for m in members]),
        })
    inventory.sort(key=lambda x: x["source_lineage_unit_sha256"])
    populations: list[dict[str, Any]] = []
    for scope_stratum in a_scope["strata"]:
        key = (scope_stratum["source_profile"], scope_stratum["platform_scope"], scope_stratum["utc_day"])
        units = sorted(lineages_by_stratum.get(key, []))
        G_h, n_h = len(units), scope_stratum["quota"]
        if G_h < n_h:
            raise P0PresentedAContextLineageCappedV2Error(f"hard lineage underfill in fixed stratum: G_h={G_h}, n_h={n_h}")
        populations.append({
            "source_profile": key[0], "platform_scope": key[1], "utc_day": key[2],
            "stratum_id": a_v1.stratum_id(*key), "eligible_context_count": sum(len(groups[u]) for u in units),
            "G_h": G_h, "n_h": n_h,
            "eligible_lineage_set_sha256": canonical_sha256(units),
        })
    if sum(row["n_h"] for row in populations) != EXPECTED_TOTAL_QUOTA:
        raise P0PresentedAContextLineageCappedV2Error("total quota mismatch")
    return {
        "source_plan": plan, "a_scope": a_scope, "a_frame": a_frame,
        "eligible": eligible, "groups": groups, "inventory": inventory,
        "populations": populations,
    }


_RAW_SHA_FIELDS = frozenset(PRESEED_RAW_KEYS)
_POP_FIELDS = frozenset({"source_profile", "platform_scope", "utc_day", "stratum_id", "eligible_context_count", "G_h", "n_h", "eligible_lineage_set_sha256"})
_INVENTORY_FIELDS = frozenset({"source_lineage_unit_sha256", "source_lineage_group_id", "source_frame_candidate_id", "source_profile", "platform_scope", "utc_day", "eligible_context_count", "eligible_context_set_sha256"})
_FRAME_FIELDS = frozenset({
    "schema_version", "record_origin", "component_version", "component_manifest_sha256",
    "source_component_manifest_sha256", "bridge_component_manifest_sha256", "a_v1_component_manifest_sha256",
    "preseed_raw_sha256", "lineage_frame_sealed_at", "eligible_context_count",
    "eligible_source_lineage_count", "eligible_context_set_sha256", "eligible_lineage_set_sha256",
    "lineage_inventory", "lineage_inventory_sha256", "stratum_populations",
    "max_selected_contexts_per_source_lineage", "lineage_policy_preseed_sealed",
    "source_a_bridge_cross_binding_verified", "presented_serialization_only",
    "downstream_wiring_count", "consumed_by_subject_v2", "consumed_by_packet_v2",
    "actual_source_evidence_count", "actual_a_context_review_count", "actual_surplus_review_count",
    "statistical_denominator", "metric_status", *FALSE_AUTHORITY_FIELDS,
    "operational_effect", "gate_status", "replay_idempotency_key_sha256", "artifact_sha256",
})


def _frame_material(raws: Mapping[str, bytes], lineage_frame_sealed_at: str) -> dict[str, Any]:
    state = _bound_state(raws, require_a_plan=False)
    sealed = _timestamp(lineage_frame_sealed_at, "lineage_frame_sealed_at")
    if sealed <= _timestamp(state["a_frame"]["frame_sealed_at"], "a frame_sealed_at"):
        raise P0PresentedAContextLineageCappedV2Error("lineage frame seal must follow A frame seal")
    raw_hashes = {key: raw_sha256(raws[key]) for key in PRESEED_RAW_KEYS}
    eligible_context_ids = sorted(row["context_unit_sha256"] for row in state["eligible"])
    lineage_ids = sorted(state["groups"])
    material = {
        "schema_version": FRAME_SCHEMA, "record_origin": RECORD_ORIGIN,
        "component_version": COMPONENT_VERSION, "component_manifest_sha256": COMPONENT_MANIFEST_SHA256,
        "source_component_manifest_sha256": SOURCE_COMPONENT_MANIFEST_SHA256,
        "bridge_component_manifest_sha256": BRIDGE_COMPONENT_MANIFEST_SHA256,
        "a_v1_component_manifest_sha256": A_V1_COMPONENT_MANIFEST_SHA256,
        "preseed_raw_sha256": raw_hashes, "lineage_frame_sealed_at": lineage_frame_sealed_at,
        "eligible_context_count": len(eligible_context_ids), "eligible_source_lineage_count": len(lineage_ids),
        "eligible_context_set_sha256": canonical_sha256(eligible_context_ids),
        "eligible_lineage_set_sha256": canonical_sha256(lineage_ids),
        "lineage_inventory": state["inventory"], "lineage_inventory_sha256": canonical_sha256(state["inventory"]),
        "stratum_populations": state["populations"],
        "max_selected_contexts_per_source_lineage": MAX_SELECTED_PER_SOURCE_LINEAGE,
        "lineage_policy_preseed_sealed": True, "source_a_bridge_cross_binding_verified": True,
        "presented_serialization_only": True, "downstream_wiring_count": 0,
        "consumed_by_subject_v2": False, "consumed_by_packet_v2": False,
        "actual_source_evidence_count": 0, "actual_a_context_review_count": 0,
        "actual_surplus_review_count": 0, "statistical_denominator": "NONE",
        "metric_status": METRIC_STATUS, **{field: False for field in FALSE_AUTHORITY_FIELDS},
        "operational_effect": OPERATIONAL_EFFECT, "gate_status": GATE_STATUS,
        "replay_idempotency_key_sha256": canonical_sha256({"domain": REPLAY_DOMAIN, "stage": "FRAME", "raw_sha256": raw_hashes, "sealed_at": lineage_frame_sealed_at}),
    }
    return with_self_hash(material)


def _runtime_guard() -> None:
    current_helpers = (
        canonical_bytes, canonical_file_bytes, canonical_sha256, raw_sha256,
        with_self_hash, _object, _strict, _sha, _identifier, _integer,
        _boolean, _timestamp, _self_hash, _false_authority, _preflight,
        _artifact_preflight, _rows, _source_plan, _a_chain, _bridge_rows, _bound_state,
        _frame_material, _validate_frame_shape, _fraction_pair,
        _probability_fields, _plan_material, _validate_plan_shape,
    )
    current_constants = (
        FRAME_SCHEMA, SEED_SCHEMA, PLAN_SCHEMA, COMPONENT_MANIFEST_SCHEMA,
        COMPONENT_VERSION, RECORD_ORIGIN, OPERATIONAL_EFFECT, GATE_STATUS,
        METRIC_STATUS, SELECTION_ALGORITHM, LINEAGE_RANK_DOMAIN,
        CONTEXT_RANK_DOMAIN, SEED_DERIVATION_DOMAIN, SEED_DERIVATION_INPUTS,
        REPLAY_DOMAIN, EXPECTED_PER_PROFILE_QUOTA, EXPECTED_TOTAL_QUOTA,
        MAX_SELECTED_PER_SOURCE_LINEAGE, SOURCE_COMPONENT_MANIFEST_SHA256,
        BRIDGE_COMPONENT_MANIFEST_SHA256, A_V1_COMPONENT_MANIFEST_SHA256,
        MAX_OBJECT_BYTES, MAX_AGGREGATE_RAW_BYTES, MAX_ROWS, MAX_ID_CHARS,
        MAX_BRIDGE_JSONL_BYTES,
        SOURCE_RAW_KEYS, A_RAW_KEYS, PRESEED_RAW_KEYS, ALL_RAW_KEYS,
        FALSE_AUTHORITY_FIELDS, _RAW_SHA_FIELDS, _POP_FIELDS,
        _INVENTORY_FIELDS, _FRAME_FIELDS, _SEED_FIELDS,
        _LINEAGE_ITEM_FIELDS, _CONTEXT_ITEM_FIELDS, _ALL_RAW_SHA_FIELDS,
        _PLAN_FIELDS, COMPONENT_MANIFEST_SHA256,
    )
    if (
        source_v2 is not _SOURCE_MODULE
        or bridge_v1 is not _BRIDGE_MODULE
        or a_v1 is not _A_MODULE
        or source_v2.validate_sampling_plan_bytes is not _SOURCE_VALIDATE_PLAN
        or source_v2.validate_sampling_plan_bytes.__code__ is not _SOURCE_VALIDATE_PLAN_CODE
        or source_v2.validate_census_bytes is not _SOURCE_VALIDATE_CENSUS
        or bridge_v1._validate_bridge_rows is not _BRIDGE_VALIDATE_ROWS
        or bridge_v1._validate_bridge_rows.__code__ is not _BRIDGE_VALIDATE_ROWS_CODE
        or a_v1.validate_scope_bytes is not _A_VALIDATE_SCOPE
        or a_v1.validate_census_bytes is not _A_VALIDATE_CENSUS
        or a_v1.validate_frame_manifest_bytes is not _A_VALIDATE_FRAME
        or a_v1.validate_seed_receipt_bytes is not _A_VALIDATE_SEED
        or a_v1.validate_sampling_plan_bytes is not _A_VALIDATE_PLAN
        or a_v1.stratum_id is not _A_STRATUM_ID
        or tuple(callable_.__code__ for callable_ in _PREDECESSOR_CALLABLES) != _PREDECESSOR_CALLABLE_CODES
        or tuple(callable_.__defaults__ for callable_ in _PREDECESSOR_CALLABLES) != _PREDECESSOR_CALLABLE_DEFAULTS
        or tuple(callable_.__kwdefaults__ for callable_ in _PREDECESSOR_CALLABLES) != _PREDECESSOR_CALLABLE_KWDEFAULTS
        or hashlib.sha256 is not _HASHLIB_SHA256
        or json.loads is not _JSON_LOADS
        or json.dumps is not _JSON_DUMPS
        or current_helpers != _PRODUCER_HELPERS
        or tuple(helper.__code__ for helper in _PRODUCER_HELPERS) != _PRODUCER_HELPER_CODES
        or tuple(helper.__defaults__ for helper in _PRODUCER_HELPERS) != _PRODUCER_HELPER_DEFAULTS
        or tuple(helper.__kwdefaults__ for helper in _PRODUCER_HELPERS) != _PRODUCER_HELPER_KWDEFAULTS
        or current_constants != _PRODUCER_CONSTANTS
        or canonical_bytes(COMPONENT_MANIFEST) != _PRODUCER_MANIFEST_BYTES
        or canonical_sha256(COMPONENT_MANIFEST) != COMPONENT_MANIFEST_SHA256
    ):
        raise P0PresentedAContextLineageCappedV2Error("runtime callable/constant integrity drift")


def build_lineage_frame_bytes(*, lineage_frame_sealed_at: str, _integrity_guard: Any = _runtime_guard, **raw_inputs: bytes) -> bytes:
    if _integrity_guard is not _runtime_guard or _integrity_guard.__code__ is not _PRODUCER_GUARD_CODE:
        raise P0PresentedAContextLineageCappedV2Error("runtime guard integrity drift")
    _integrity_guard()
    raws = _preflight(raw_inputs, PRESEED_RAW_KEYS)
    raw = canonical_file_bytes(_frame_material(raws, lineage_frame_sealed_at))
    validate_lineage_frame_bytes(raw, **raws)
    return raw


def _validate_frame_shape(row: dict[str, Any]) -> None:
    _strict(row, _FRAME_FIELDS, "lineage frame")
    if row["schema_version"] != FRAME_SCHEMA or row["record_origin"] != RECORD_ORIGIN or row["component_version"] != COMPONENT_VERSION or row["component_manifest_sha256"] != COMPONENT_MANIFEST_SHA256:
        raise P0PresentedAContextLineageCappedV2Error("lineage frame contract mismatch")
    _strict(row["preseed_raw_sha256"], _RAW_SHA_FIELDS, "preseed raw SHA map")
    for value in row["preseed_raw_sha256"].values(): _sha(value, "preseed raw SHA")
    if type(row["lineage_inventory"]) is not list or type(row["stratum_populations"]) is not list:
        raise P0PresentedAContextLineageCappedV2Error("lineage frame inventory/populations invalid")
    for item in row["lineage_inventory"]: _strict(item, _INVENTORY_FIELDS, "lineage inventory item")
    for item in row["stratum_populations"]: _strict(item, _POP_FIELDS, "stratum population")
    _false_authority(row, "lineage frame")
    _self_hash(row, "artifact_sha256", "lineage frame")


def validate_lineage_frame_bytes(frame_raw: bytes, _integrity_guard: Any = _runtime_guard, **raw_inputs: bytes) -> dict[str, Any]:
    if _integrity_guard is not _runtime_guard or _integrity_guard.__code__ is not _PRODUCER_GUARD_CODE:
        raise P0PresentedAContextLineageCappedV2Error("runtime guard integrity drift")
    _integrity_guard()
    _artifact_preflight(("lineage frame", frame_raw))
    raws = _preflight(raw_inputs, PRESEED_RAW_KEYS)
    row = _object(frame_raw, "lineage frame")
    _validate_frame_shape(row)
    expected = _frame_material(raws, row["lineage_frame_sealed_at"])
    if row != expected:
        raise P0PresentedAContextLineageCappedV2Error("lineage frame replay mismatch")
    return row


_SEED_FIELDS = frozenset({
    "schema_version", "record_origin", "component_version", "component_manifest_sha256",
    "seed_receipt_id", "lineage_frame_raw_sha256", "lineage_frame_artifact_sha256",
    "future_seed_spec_sha256", "revealed_seed_sha256", "frame_owner_precommit_sha256",
    "frame_owner_precommitted_at", "revealed_at", "owner_authority_verified",
    "seed_authority_verified", "seed_randomness_authority_verified", "trusted_time_verified",
    "action_applied", "operational_effect", "artifact_sha256",
})


def build_seed_receipt_bytes(material: Mapping[str, Any], lineage_frame_raw: bytes, _integrity_guard: Any = _runtime_guard, **raw_inputs: bytes) -> bytes:
    if _integrity_guard is not _runtime_guard or _integrity_guard.__code__ is not _PRODUCER_GUARD_CODE:
        raise P0PresentedAContextLineageCappedV2Error("runtime guard integrity drift")
    _integrity_guard()
    _artifact_preflight(("lineage frame", lineage_frame_raw))
    raws = _preflight(raw_inputs, PRESEED_RAW_KEYS)
    frame = validate_lineage_frame_bytes(lineage_frame_raw, **raws)
    value = dict(material)
    value.update({
        "schema_version": SEED_SCHEMA, "record_origin": RECORD_ORIGIN, "component_version": COMPONENT_VERSION,
        "component_manifest_sha256": COMPONENT_MANIFEST_SHA256,
        "lineage_frame_raw_sha256": raw_sha256(lineage_frame_raw),
        "lineage_frame_artifact_sha256": frame["artifact_sha256"],
        "future_seed_spec_sha256": _bound_state(raws, require_a_plan=False)["a_scope"]["future_seed_spec_sha256"],
        "owner_authority_verified": False, "seed_authority_verified": False,
        "seed_randomness_authority_verified": False, "trusted_time_verified": False,
        "action_applied": False, "operational_effect": OPERATIONAL_EFFECT,
    })
    raw = canonical_file_bytes(with_self_hash(value))
    validate_seed_receipt_bytes(raw, lineage_frame_raw, **raws)
    return raw


def validate_seed_receipt_bytes(seed_raw: bytes, lineage_frame_raw: bytes, _integrity_guard: Any = _runtime_guard, **raw_inputs: bytes) -> dict[str, Any]:
    if _integrity_guard is not _runtime_guard or _integrity_guard.__code__ is not _PRODUCER_GUARD_CODE:
        raise P0PresentedAContextLineageCappedV2Error("runtime guard integrity drift")
    _integrity_guard()
    _artifact_preflight(("lineage seed", seed_raw), ("lineage frame", lineage_frame_raw))
    raws = _preflight(raw_inputs, PRESEED_RAW_KEYS)
    frame = validate_lineage_frame_bytes(lineage_frame_raw, **raws)
    row = _strict(_object(seed_raw, "lineage seed receipt"), _SEED_FIELDS, "lineage seed receipt")
    if row["schema_version"] != SEED_SCHEMA or row["record_origin"] != RECORD_ORIGIN or row["component_version"] != COMPONENT_VERSION or row["component_manifest_sha256"] != COMPONENT_MANIFEST_SHA256:
        raise P0PresentedAContextLineageCappedV2Error("lineage seed contract mismatch")
    _identifier(row["seed_receipt_id"], "seed_receipt_id")
    state = _bound_state(raws, require_a_plan=False)
    expected = {"lineage_frame_raw_sha256": raw_sha256(lineage_frame_raw), "lineage_frame_artifact_sha256": frame["artifact_sha256"], "future_seed_spec_sha256": state["a_scope"]["future_seed_spec_sha256"]}
    if any(row[key] != value for key, value in expected.items()):
        raise P0PresentedAContextLineageCappedV2Error("lineage seed binding mismatch")
    for field in ("revealed_seed_sha256", "frame_owner_precommit_sha256"): _sha(row[field], field)
    precommit = _timestamp(row["frame_owner_precommitted_at"], "frame_owner_precommitted_at")
    reveal = _timestamp(row["revealed_at"], "revealed_at")
    if precommit <= _timestamp(frame["lineage_frame_sealed_at"], "lineage_frame_sealed_at") or reveal <= precommit:
        raise P0PresentedAContextLineageCappedV2Error("lineage seed chronology mismatch")
    for field in ("owner_authority_verified", "seed_authority_verified", "seed_randomness_authority_verified", "trusted_time_verified", "action_applied"):
        if _boolean(row[field], field) is not False: raise P0PresentedAContextLineageCappedV2Error(f"lineage seed must keep {field}=false")
    if row["operational_effect"] != OPERATIONAL_EFFECT: raise P0PresentedAContextLineageCappedV2Error("lineage seed operational effect mismatch")
    _self_hash(row, "artifact_sha256", "lineage seed receipt")
    return row


def _fraction_pair(numerator: int, denominator: int) -> tuple[int, int]:
    value = Fraction(numerator, denominator)
    return value.numerator, value.denominator


def _probability_fields(G_h: int, n_h: int, K_g: int) -> dict[str, int]:
    lp = _fraction_pair(n_h, G_h); lw = _fraction_pair(G_h, n_h)
    cp = _fraction_pair(1, K_g); cw = _fraction_pair(K_g, 1)
    mp = _fraction_pair(n_h, G_h * K_g); mw = _fraction_pair(G_h * K_g, n_h)
    return {
        "lineage_inclusion_probability_numerator": lp[0], "lineage_inclusion_probability_denominator": lp[1],
        "lineage_weight_numerator": lw[0], "lineage_weight_denominator": lw[1],
        "within_lineage_probability_numerator": cp[0], "within_lineage_probability_denominator": cp[1],
        "within_lineage_weight_numerator": cw[0], "within_lineage_weight_denominator": cw[1],
        "marginal_inclusion_probability_numerator": mp[0], "marginal_inclusion_probability_denominator": mp[1],
        "marginal_weight_numerator": mw[0], "marginal_weight_denominator": mw[1],
    }


_LINEAGE_ITEM_FIELDS = frozenset({
    "source_lineage_unit_sha256", "source_lineage_group_id", "source_frame_candidate_id",
    "source_profile", "platform_scope", "utc_day", "stratum_id", "G_h", "n_h", "K_g",
    "lineage_rank_sha256", "eligible_context_set_sha256",
    "lineage_inclusion_probability_numerator", "lineage_inclusion_probability_denominator",
    "lineage_weight_numerator", "lineage_weight_denominator",
})
_CONTEXT_ITEM_FIELDS = frozenset({
    "input_sequence", "disposition", "surplus_reason", "candidate_id", "context_unit_sha256",
    "source_lineage_unit_sha256", "source_lineage_group_id", "source_frame_candidate_id",
    "source_profile", "platform_scope", "utc_day", "stratum_id", "adapter_id", "G_h", "n_h", "K_g",
    "lineage_rank_sha256", "context_rank_sha256", "eligible_context_set_sha256",
    "lineage_inclusion_probability_numerator", "lineage_inclusion_probability_denominator",
    "lineage_weight_numerator", "lineage_weight_denominator",
    "within_lineage_probability_numerator", "within_lineage_probability_denominator",
    "within_lineage_weight_numerator", "within_lineage_weight_denominator",
    "marginal_inclusion_probability_numerator", "marginal_inclusion_probability_denominator",
    "marginal_weight_numerator", "marginal_weight_denominator",
})
_ALL_RAW_SHA_FIELDS = frozenset(ALL_RAW_KEYS)
_PLAN_FIELDS = frozenset({
    "schema_version", "record_origin", "component_version", "component_manifest_sha256",
    "all_raw_sha256", "lineage_frame_raw_sha256", "lineage_frame_artifact_sha256",
    "lineage_seed_receipt_raw_sha256", "lineage_seed_receipt_artifact_sha256",
    "predecessor_a_plan_selection_used", "selection_algorithm", "derived_seed_sha256",
    "selected_lineages", "eligible_lineage_surplus", "selected_inputs", "eligible_context_surplus",
    "selected_lineage_count", "eligible_lineage_surplus_count", "selected_input_count",
    "eligible_context_surplus_count", "selected_lineage_set_sha256", "lineage_surplus_set_sha256",
    "selected_input_set_sha256", "context_surplus_set_sha256", "per_profile_counts",
    "lineage_partition_exact", "context_partition_exact", "global_lineage_cap_verified",
    "max_selected_contexts_per_source_lineage", "replacement_allowed", "spill_allowed",
    "backfill_allowed", "contexts_are_iid", "same_lineage_pairwise_joint_inclusion_probability",
    "probability_design_is_conditional_presented_only", "presented_serialization_only",
    "downstream_wiring_count", "consumed_by_subject_v2", "consumed_by_packet_v2",
    "actual_source_evidence_count", "actual_a_context_review_count", "actual_surplus_review_count",
    "statistical_denominator", "metric_status", *FALSE_AUTHORITY_FIELDS,
    "selection_sealed_at", "replay_idempotency_key_sha256", "operational_effect", "gate_status",
    "artifact_sha256",
})


def _plan_material(raws: Mapping[str, bytes], frame_raw: bytes, seed_raw: bytes, selection_sealed_at: str) -> dict[str, Any]:
    frame = validate_lineage_frame_bytes(frame_raw, **{key: raws[key] for key in PRESEED_RAW_KEYS})
    seed = validate_seed_receipt_bytes(seed_raw, frame_raw, **{key: raws[key] for key in PRESEED_RAW_KEYS})
    state = _bound_state(raws, require_a_plan=True)
    predecessor_a_plan = _object(raws["a_plan_raw"], "A predecessor plan")
    if _timestamp(predecessor_a_plan["selection_sealed_at"], "A selection_sealed_at") >= _timestamp(frame["lineage_frame_sealed_at"], "lineage_frame_sealed_at"):
        raise P0PresentedAContextLineageCappedV2Error("A predecessor plan must precede lineage frame seal")
    sealed = _timestamp(selection_sealed_at, "selection_sealed_at")
    if sealed <= _timestamp(seed["revealed_at"], "revealed_at"):
        raise P0PresentedAContextLineageCappedV2Error("selection seal must follow seed reveal")
    derived_seed = canonical_sha256({
        "domain": SEED_DERIVATION_DOMAIN, "component_manifest_sha256": COMPONENT_MANIFEST_SHA256,
        "future_seed_spec_sha256": seed["future_seed_spec_sha256"],
        "revealed_seed_sha256": seed["revealed_seed_sha256"],
        "frame_owner_precommit_sha256": seed["frame_owner_precommit_sha256"],
    })
    inventory_by_unit = {x["source_lineage_unit_sha256"]: x for x in state["inventory"]}
    pop_by_key = {(x["source_profile"], x["platform_scope"], x["utc_day"]): x for x in state["populations"]}
    selected_lineages: list[dict[str, Any]] = []
    surplus_lineages: list[dict[str, Any]] = []
    selected_units: set[str] = set()
    rank_by_unit: dict[str, str] = {}
    lineage_item_by_unit: dict[str, dict[str, Any]] = {}
    for pop in state["populations"]:
        key = (pop["source_profile"], pop["platform_scope"], pop["utc_day"])
        units = [u for u, members in state["groups"].items() if (members[0]["source_profile"], members[0]["platform_scope"], members[0]["utc_day"]) == key]
        ranked: list[tuple[str, str]] = []
        for unit in units:
            rank = canonical_sha256({"domain": LINEAGE_RANK_DOMAIN, "derived_seed_sha256": derived_seed, "stratum_id": pop["stratum_id"], "eligible_lineage_set_sha256": pop["eligible_lineage_set_sha256"], "source_lineage_unit_sha256": unit})
            ranked.append((rank, unit)); rank_by_unit[unit] = rank
        ranked.sort()
        chosen = {unit for _, unit in ranked[:pop["n_h"]]}
        selected_units.update(chosen)
        for rank, unit in ranked:
            inv = inventory_by_unit[unit]; K_g = inv["eligible_context_count"]
            lp = _probability_fields(pop["G_h"], pop["n_h"], K_g)
            item = {
                "source_lineage_unit_sha256": unit, "source_lineage_group_id": inv["source_lineage_group_id"],
                "source_frame_candidate_id": inv["source_frame_candidate_id"],
                "source_profile": inv["source_profile"], "platform_scope": inv["platform_scope"], "utc_day": inv["utc_day"],
                "stratum_id": pop["stratum_id"], "G_h": pop["G_h"], "n_h": pop["n_h"], "K_g": K_g,
                "lineage_rank_sha256": rank, "eligible_context_set_sha256": inv["eligible_context_set_sha256"],
                **{k: lp[k] for k in ("lineage_inclusion_probability_numerator", "lineage_inclusion_probability_denominator", "lineage_weight_numerator", "lineage_weight_denominator")},
            }
            lineage_item_by_unit[unit] = item
            (selected_lineages if unit in chosen else surplus_lineages).append(item)
    selected_lineages.sort(key=lambda x: (x["source_profile"], x["platform_scope"], x["utc_day"], x["lineage_rank_sha256"], x["source_lineage_unit_sha256"]))
    surplus_lineages.sort(key=lambda x: (x["source_profile"], x["platform_scope"], x["utc_day"], x["lineage_rank_sha256"], x["source_lineage_unit_sha256"]))
    selected_contexts: list[dict[str, Any]] = []
    surplus_contexts: list[dict[str, Any]] = []
    for unit, members in state["groups"].items():
        lineage_item = lineage_item_by_unit[unit]
        ranked_members: list[tuple[str, dict[str, Any]]] = []
        for member in members:
            rank = canonical_sha256({"domain": CONTEXT_RANK_DOMAIN, "derived_seed_sha256": derived_seed, "source_lineage_unit_sha256": unit, "eligible_context_set_sha256": lineage_item["eligible_context_set_sha256"], "context_unit_sha256": member["context_unit_sha256"]})
            ranked_members.append((rank, member))
        ranked_members.sort(key=lambda x: (x[0], x[1]["candidate_id"]))
        chosen_id = ranked_members[0][1]["candidate_id"] if unit in selected_units else None
        probability = _probability_fields(lineage_item["G_h"], lineage_item["n_h"], lineage_item["K_g"])
        for context_rank, member in ranked_members:
            is_selected = member["candidate_id"] == chosen_id
            item = {
                "input_sequence": 0, "disposition": "SELECTED" if is_selected else "SURPLUS",
                "surplus_reason": "NONE" if is_selected else ("WITHIN_SELECTED_LINEAGE_SURPLUS" if unit in selected_units else "UNSELECTED_LINEAGE_SURPLUS"),
                "candidate_id": member["candidate_id"], "context_unit_sha256": member["context_unit_sha256"],
                "source_lineage_unit_sha256": unit, "source_lineage_group_id": member["source_lineage_group_id"],
                "source_frame_candidate_id": member["source_frame_candidate_id"], "source_profile": member["source_profile"],
                "platform_scope": member["platform_scope"], "utc_day": member["utc_day"], "stratum_id": lineage_item["stratum_id"],
                "adapter_id": member["adapter_id"], "G_h": lineage_item["G_h"], "n_h": lineage_item["n_h"], "K_g": lineage_item["K_g"],
                "lineage_rank_sha256": rank_by_unit[unit], "context_rank_sha256": context_rank,
                "eligible_context_set_sha256": lineage_item["eligible_context_set_sha256"], **probability,
            }
            (selected_contexts if is_selected else surplus_contexts).append(item)
    selected_contexts.sort(key=lambda x: (x["source_profile"], x["platform_scope"], x["utc_day"], x["lineage_rank_sha256"], x["context_rank_sha256"]))
    for sequence, item in enumerate(selected_contexts, start=1): item["input_sequence"] = sequence
    surplus_contexts.sort(key=lambda x: (x["source_profile"], x["platform_scope"], x["utc_day"], x["lineage_rank_sha256"], x["context_rank_sha256"]))
    if len(selected_contexts) != EXPECTED_TOTAL_QUOTA or len({x["source_lineage_unit_sha256"] for x in selected_contexts}) != EXPECTED_TOTAL_QUOTA:
        raise P0PresentedAContextLineageCappedV2Error("selected context lineage cap/count mismatch")
    all_eligible = {x["context_unit_sha256"] for x in state["eligible"]}
    selected_ids = {x["context_unit_sha256"] for x in selected_contexts}; surplus_ids = {x["context_unit_sha256"] for x in surplus_contexts}
    if selected_ids & surplus_ids or selected_ids | surplus_ids != all_eligible:
        raise P0PresentedAContextLineageCappedV2Error("eligible context partition mismatch")
    all_lineages = set(state["groups"]); lineage_surplus_ids = {x["source_lineage_unit_sha256"] for x in surplus_lineages}
    if selected_units & lineage_surplus_ids or selected_units | lineage_surplus_ids != all_lineages:
        raise P0PresentedAContextLineageCappedV2Error("eligible lineage partition mismatch")
    counts = Counter(x["source_profile"] for x in selected_contexts)
    expected_counts = {profile: EXPECTED_PER_PROFILE_QUOTA for profile in a_v1.SOURCE_PROFILES}
    if dict(counts) != expected_counts: raise P0PresentedAContextLineageCappedV2Error("selected per-profile count mismatch")
    all_raw_hashes = {key: raw_sha256(raws[key]) for key in ALL_RAW_KEYS}
    material = {
        "schema_version": PLAN_SCHEMA, "record_origin": RECORD_ORIGIN, "component_version": COMPONENT_VERSION,
        "component_manifest_sha256": COMPONENT_MANIFEST_SHA256, "all_raw_sha256": all_raw_hashes,
        "lineage_frame_raw_sha256": raw_sha256(frame_raw), "lineage_frame_artifact_sha256": frame["artifact_sha256"],
        "lineage_seed_receipt_raw_sha256": raw_sha256(seed_raw), "lineage_seed_receipt_artifact_sha256": seed["artifact_sha256"],
        "predecessor_a_plan_selection_used": False, "selection_algorithm": SELECTION_ALGORITHM,
        "derived_seed_sha256": derived_seed, "selected_lineages": selected_lineages,
        "eligible_lineage_surplus": surplus_lineages, "selected_inputs": selected_contexts,
        "eligible_context_surplus": surplus_contexts, "selected_lineage_count": len(selected_lineages),
        "eligible_lineage_surplus_count": len(surplus_lineages), "selected_input_count": len(selected_contexts),
        "eligible_context_surplus_count": len(surplus_contexts),
        "selected_lineage_set_sha256": canonical_sha256(selected_lineages), "lineage_surplus_set_sha256": canonical_sha256(surplus_lineages),
        "selected_input_set_sha256": canonical_sha256(selected_contexts), "context_surplus_set_sha256": canonical_sha256(surplus_contexts),
        "per_profile_counts": expected_counts, "lineage_partition_exact": True, "context_partition_exact": True,
        "global_lineage_cap_verified": True, "max_selected_contexts_per_source_lineage": MAX_SELECTED_PER_SOURCE_LINEAGE,
        "replacement_allowed": False, "spill_allowed": False, "backfill_allowed": False,
        "contexts_are_iid": False, "same_lineage_pairwise_joint_inclusion_probability": "ZERO",
        "probability_design_is_conditional_presented_only": True, "presented_serialization_only": True,
        "downstream_wiring_count": 0, "consumed_by_subject_v2": False, "consumed_by_packet_v2": False,
        "actual_source_evidence_count": 0, "actual_a_context_review_count": 0, "actual_surplus_review_count": 0,
        "statistical_denominator": "NONE", "metric_status": METRIC_STATUS,
        **{field: False for field in FALSE_AUTHORITY_FIELDS}, "selection_sealed_at": selection_sealed_at,
        "replay_idempotency_key_sha256": canonical_sha256({"domain": REPLAY_DOMAIN, "stage": "PLAN", "raw_sha256": all_raw_hashes, "frame_raw_sha256": raw_sha256(frame_raw), "seed_raw_sha256": raw_sha256(seed_raw), "selection_sealed_at": selection_sealed_at}),
        "operational_effect": OPERATIONAL_EFFECT, "gate_status": GATE_STATUS,
    }
    return with_self_hash(material)


def build_sampling_plan_bytes(*, lineage_frame_raw: bytes, lineage_seed_raw: bytes, selection_sealed_at: str, _integrity_guard: Any = _runtime_guard, **raw_inputs: bytes) -> bytes:
    if _integrity_guard is not _runtime_guard or _integrity_guard.__code__ is not _PRODUCER_GUARD_CODE:
        raise P0PresentedAContextLineageCappedV2Error("runtime guard integrity drift")
    _integrity_guard()
    _artifact_preflight(("lineage frame", lineage_frame_raw), ("lineage seed", lineage_seed_raw))
    raws = _preflight(raw_inputs, ALL_RAW_KEYS)
    raw = canonical_file_bytes(_plan_material(raws, lineage_frame_raw, lineage_seed_raw, selection_sealed_at))
    validate_sampling_plan_bytes(raw, lineage_frame_raw=lineage_frame_raw, lineage_seed_raw=lineage_seed_raw, **raws)
    return raw


def _validate_plan_shape(row: dict[str, Any]) -> None:
    _strict(row, _PLAN_FIELDS, "lineage plan")
    if row["schema_version"] != PLAN_SCHEMA or row["record_origin"] != RECORD_ORIGIN or row["component_version"] != COMPONENT_VERSION or row["component_manifest_sha256"] != COMPONENT_MANIFEST_SHA256:
        raise P0PresentedAContextLineageCappedV2Error("lineage plan contract mismatch")
    _strict(row["all_raw_sha256"], _ALL_RAW_SHA_FIELDS, "all raw SHA map")
    for field in ("selected_lineages", "eligible_lineage_surplus", "selected_inputs", "eligible_context_surplus"):
        if type(row[field]) is not list: raise P0PresentedAContextLineageCappedV2Error(f"{field} must be list")
    for item in row["selected_lineages"] + row["eligible_lineage_surplus"]: _strict(item, _LINEAGE_ITEM_FIELDS, "lineage plan item")
    for item in row["selected_inputs"] + row["eligible_context_surplus"]: _strict(item, _CONTEXT_ITEM_FIELDS, "context plan item")
    _false_authority(row, "lineage plan")
    _self_hash(row, "artifact_sha256", "lineage plan")


def validate_sampling_plan_bytes(plan_raw: bytes, *, lineage_frame_raw: bytes, lineage_seed_raw: bytes, _integrity_guard: Any = _runtime_guard, **raw_inputs: bytes) -> dict[str, Any]:
    if _integrity_guard is not _runtime_guard or _integrity_guard.__code__ is not _PRODUCER_GUARD_CODE:
        raise P0PresentedAContextLineageCappedV2Error("runtime guard integrity drift")
    _integrity_guard()
    _artifact_preflight(("lineage plan", plan_raw), ("lineage frame", lineage_frame_raw), ("lineage seed", lineage_seed_raw))
    raws = _preflight(raw_inputs, ALL_RAW_KEYS)
    row = _object(plan_raw, "lineage plan")
    _validate_plan_shape(row)
    expected = _plan_material(raws, lineage_frame_raw, lineage_seed_raw, row["selection_sealed_at"])
    if row != expected: raise P0PresentedAContextLineageCappedV2Error("lineage plan replay mismatch")
    return row


COMPONENT_MANIFEST = {
    "schema_version": COMPONENT_MANIFEST_SCHEMA, "component_version": COMPONENT_VERSION,
    "source_component_manifest_sha256": SOURCE_COMPONENT_MANIFEST_SHA256,
    "bridge_component_manifest_sha256": BRIDGE_COMPONENT_MANIFEST_SHA256,
    "a_v1_component_manifest_sha256": A_V1_COMPONENT_MANIFEST_SHA256,
    "preseed_raw_roles": list(PRESEED_RAW_KEYS), "all_raw_roles": list(ALL_RAW_KEYS),
    "frame_schema": FRAME_SCHEMA, "seed_schema": SEED_SCHEMA, "plan_schema": PLAN_SCHEMA,
    "selection_algorithm": SELECTION_ALGORITHM, "lineage_rank_domain": LINEAGE_RANK_DOMAIN,
    "context_rank_domain": CONTEXT_RANK_DOMAIN, "seed_derivation_domain": SEED_DERIVATION_DOMAIN,
    "seed_derivation_inputs": list(SEED_DERIVATION_INPUTS),
    "max_selected_per_source_lineage": MAX_SELECTED_PER_SOURCE_LINEAGE,
    "hard_lineage_underfill": True, "replacement_allowed": False, "spill_allowed": False,
    "backfill_allowed": False, "downstream_wiring_count": 0,
    "authority": "NONE", "metric_status": METRIC_STATUS,
    "max_object_bytes": MAX_OBJECT_BYTES, "max_aggregate_raw_bytes": MAX_AGGREGATE_RAW_BYTES,
    "max_rows": MAX_ROWS, "bridge_inventory_max_bytes": MAX_BRIDGE_JSONL_BYTES,
}
COMPONENT_MANIFEST_SHA256 = canonical_sha256(COMPONENT_MANIFEST)
_PRODUCER_MANIFEST_BYTES = canonical_bytes(COMPONENT_MANIFEST)

_SOURCE_MODULE = source_v2
_BRIDGE_MODULE = bridge_v1
_A_MODULE = a_v1
_SOURCE_VALIDATE_PLAN = source_v2.validate_sampling_plan_bytes
_SOURCE_VALIDATE_PLAN_CODE = _SOURCE_VALIDATE_PLAN.__code__
_SOURCE_VALIDATE_CENSUS = source_v2.validate_census_bytes
_BRIDGE_VALIDATE_ROWS = bridge_v1._validate_bridge_rows
_BRIDGE_VALIDATE_ROWS_CODE = _BRIDGE_VALIDATE_ROWS.__code__
_A_VALIDATE_SCOPE = a_v1.validate_scope_bytes
_A_VALIDATE_CENSUS = a_v1.validate_census_bytes
_A_VALIDATE_FRAME = a_v1.validate_frame_manifest_bytes
_A_VALIDATE_SEED = a_v1.validate_seed_receipt_bytes
_A_VALIDATE_PLAN = a_v1.validate_sampling_plan_bytes
_A_STRATUM_ID = a_v1.stratum_id
_PREDECESSOR_CALLABLES = (
    _SOURCE_VALIDATE_PLAN, _SOURCE_VALIDATE_CENSUS, _BRIDGE_VALIDATE_ROWS,
    _A_VALIDATE_SCOPE, _A_VALIDATE_CENSUS, _A_VALIDATE_FRAME,
    _A_VALIDATE_SEED, _A_VALIDATE_PLAN, _A_STRATUM_ID,
)
_PREDECESSOR_CALLABLE_CODES = tuple(callable_.__code__ for callable_ in _PREDECESSOR_CALLABLES)
_PREDECESSOR_CALLABLE_DEFAULTS = tuple(callable_.__defaults__ for callable_ in _PREDECESSOR_CALLABLES)
_PREDECESSOR_CALLABLE_KWDEFAULTS = tuple(callable_.__kwdefaults__ for callable_ in _PREDECESSOR_CALLABLES)
_HASHLIB_SHA256 = hashlib.sha256
_JSON_LOADS = json.loads
_JSON_DUMPS = json.dumps
_PRODUCER_HELPERS = (
    canonical_bytes, canonical_file_bytes, canonical_sha256, raw_sha256,
    with_self_hash, _object, _strict, _sha, _identifier, _integer,
    _boolean, _timestamp, _self_hash, _false_authority, _preflight,
    _artifact_preflight, _rows, _source_plan, _a_chain, _bridge_rows, _bound_state,
    _frame_material, _validate_frame_shape, _fraction_pair,
    _probability_fields, _plan_material, _validate_plan_shape,
)
_PRODUCER_HELPER_CODES = tuple(helper.__code__ for helper in _PRODUCER_HELPERS)
_PRODUCER_HELPER_DEFAULTS = tuple(helper.__defaults__ for helper in _PRODUCER_HELPERS)
_PRODUCER_HELPER_KWDEFAULTS = tuple(helper.__kwdefaults__ for helper in _PRODUCER_HELPERS)
_PRODUCER_CONSTANTS = (
    FRAME_SCHEMA, SEED_SCHEMA, PLAN_SCHEMA, COMPONENT_MANIFEST_SCHEMA,
    COMPONENT_VERSION, RECORD_ORIGIN, OPERATIONAL_EFFECT, GATE_STATUS,
    METRIC_STATUS, SELECTION_ALGORITHM, LINEAGE_RANK_DOMAIN,
    CONTEXT_RANK_DOMAIN, SEED_DERIVATION_DOMAIN, SEED_DERIVATION_INPUTS,
    REPLAY_DOMAIN, EXPECTED_PER_PROFILE_QUOTA, EXPECTED_TOTAL_QUOTA,
    MAX_SELECTED_PER_SOURCE_LINEAGE, SOURCE_COMPONENT_MANIFEST_SHA256,
    BRIDGE_COMPONENT_MANIFEST_SHA256, A_V1_COMPONENT_MANIFEST_SHA256,
    MAX_OBJECT_BYTES, MAX_AGGREGATE_RAW_BYTES, MAX_ROWS, MAX_ID_CHARS,
    MAX_BRIDGE_JSONL_BYTES,
    SOURCE_RAW_KEYS, A_RAW_KEYS, PRESEED_RAW_KEYS, ALL_RAW_KEYS,
    FALSE_AUTHORITY_FIELDS, _RAW_SHA_FIELDS, _POP_FIELDS,
    _INVENTORY_FIELDS, _FRAME_FIELDS, _SEED_FIELDS,
    _LINEAGE_ITEM_FIELDS, _CONTEXT_ITEM_FIELDS, _ALL_RAW_SHA_FIELDS,
    _PLAN_FIELDS, COMPONENT_MANIFEST_SHA256,
)
_PRODUCER_GUARD_CODE = _runtime_guard.__code__


ARTIFACT_FIELDS = {"frame": _FRAME_FIELDS, "seed": _SEED_FIELDS, "plan": _PLAN_FIELDS}


__all__ = [
    "P0PresentedAContextLineageCappedV2Error", "FRAME_SCHEMA", "SEED_SCHEMA", "PLAN_SCHEMA",
    "COMPONENT_VERSION", "COMPONENT_MANIFEST", "COMPONENT_MANIFEST_SHA256",
    "SELECTION_ALGORITHM", "METRIC_STATUS", "GATE_STATUS", "PRESEED_RAW_KEYS", "ALL_RAW_KEYS",
    "canonical_bytes", "canonical_file_bytes", "canonical_sha256", "raw_sha256", "with_self_hash",
    "build_lineage_frame_bytes", "validate_lineage_frame_bytes", "build_seed_receipt_bytes",
    "validate_seed_receipt_bytes", "build_sampling_plan_bytes", "validate_sampling_plan_bytes",
]
