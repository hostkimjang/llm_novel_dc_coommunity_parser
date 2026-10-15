"""A-context lineage-capped V2의 producer 비의존 독립 parent replay.

현재 producer 모듈은 import하지 않는다. 두 predecessor parent를 실행하고,
source plan·bridge·A census 원문에서 lineage/context 모집단, 2단계 rank,
포함확률과 두 partition을 다시 계산한다.
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

from . import p0_full_eligible_sampling_frame_v2_parent_validator as source_parent
from . import p0_presented_a_context_full_frame_v1_parent_validator as a_parent


FRAME_SCHEMA = "p0_presented_a_context_lineage_capped_frame_v2"
SEED_SCHEMA = "p0_presented_a_context_lineage_capped_seed_receipt_v2"
PLAN_SCHEMA = "p0_presented_a_context_lineage_capped_plan_v2"
RECEIPT_SCHEMA = "p0_presented_a_context_lineage_capped_parent_receipt_v2"
COMPONENT_VERSION = "presented-a-context-lineage-capped-full-frame-v2"
COMPONENT_MANIFEST_SHA256 = "c1080b53622b1b1bb93b127361e333cadeddf664c44a94d329257a6a918d250b"
SOURCE_COMPONENT_MANIFEST_SHA256 = "efed07649c14cc2af0b0916ef6e6a04b39ad0c9147b97daec74428521287111b"
BRIDGE_COMPONENT_MANIFEST_SHA256 = "c7beb367d62a4af025643d42caddf20caccb4938cd5a68dac8b649ee49b165c1"
A_V1_COMPONENT_MANIFEST_SHA256 = "5b38f560cbe6c2af9294e79ad6298b798e7256426c2e1ca353162e7531c47aa9"
RECORD_ORIGIN = "ACTUAL_SCHEMA_CONTRACT_EXAMPLE_ONLY"
OPERATIONAL_EFFECT = "NONE_SHADOW_ONLY"
PRODUCER_GATE_STATUS = "NO_GO_PRESENTED_LINEAGE_CAPPED_FRAME_ONLY"
PARENT_GATE_STATUS = "PARENT_LINEAGE_CAPPED_REPLAY_PASS_ALL_AUTHORITY_NO_GO"
METRIC_STATUS = "NOT_ESTIMABLE_LINEAGE_CAPPED_PRESENTED_FRAME_ONLY"
SELECTION_ALGORITHM = "SHA256_TWO_STAGE_LINEAGE_THEN_CONTEXT_SRSWOR_V2"
LINEAGE_RANK_DOMAIN = "P0_PRESENTED_A_CONTEXT_LINEAGE_CAPPED_V2_LINEAGE_RANK"
CONTEXT_RANK_DOMAIN = "P0_PRESENTED_A_CONTEXT_LINEAGE_CAPPED_V2_CONTEXT_RANK"
SEED_DERIVATION_DOMAIN = "P0_PRESENTED_A_CONTEXT_LINEAGE_CAPPED_V2_DERIVED_SEED"
REPLAY_DOMAIN = "P0_PRESENTED_A_CONTEXT_LINEAGE_CAPPED_V2_REPLAY"
MAX_OBJECT_BYTES = 64 * 1024 * 1024
MAX_AGGREGATE_RAW_BYTES = 192 * 1024 * 1024
MAX_ROWS = 1_000_000
EXPECTED_TOTAL = 20
EXPECTED_PER_PROFILE = 5
MAX_METADATA_CHARS = 512
MAX_PAYLOAD_BYTES_PER_INPUT = 256 * 1024
MAX_TOTAL_PAYLOAD_BYTES = 40 * MAX_PAYLOAD_BYTES_PER_INPUT
MAX_BRIDGE_JSONL_BYTES = 16 * 1024 * 1024
SOURCE_PROFILES = ("OFFICIAL_STRUCTURED", "COMMUNITY_STRUCTURED", "MEDIA_OCR", "GENERIC_FALLBACK")

SOURCE_RAW_KEYS = ("source_scope_raw", "source_census_raw", "source_frame_raw", "source_seed_raw", "source_plan_raw")
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
_FORBIDDEN_METADATA_CATEGORIES = frozenset({"Cc", "Cf", "Cs", "Zl", "Zp"})
_BRIDGE_FIELDS = frozenset({
    "schema_version", "input_sequence", "candidate_id", "lineage_group_id", "lineage_unit_sha256",
    "source_profile", "adapter_id", "platform", "utc_day", "stratum_id", "locator_commitment_sha256",
    "selected_input_sha256", "registry_record_id", "registry_record_commitment_sha256", "content_type",
    "capture_version", "normalization_version", "payload_base64", "payload_bytes", "payload_sha256",
    "bridge_row_sha256",
})
_SELECTED_IDENTITY_FIELDS = (
    "input_sequence", "candidate_id", "lineage_group_id", "lineage_unit_sha256", "source_profile",
    "adapter_id", "platform", "utc_day", "stratum_id", "locator_commitment_sha256",
)
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
_SEED_FIELDS = frozenset({
    "schema_version", "record_origin", "component_version", "component_manifest_sha256",
    "seed_receipt_id", "lineage_frame_raw_sha256", "lineage_frame_artifact_sha256",
    "future_seed_spec_sha256", "revealed_seed_sha256", "frame_owner_precommit_sha256",
    "frame_owner_precommitted_at", "revealed_at", "owner_authority_verified",
    "seed_authority_verified", "seed_randomness_authority_verified", "trusted_time_verified",
    "action_applied", "operational_effect", "artifact_sha256",
})
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


class P0PresentedAContextLineageCappedV2ParentError(ValueError):
    pass


def _bytes(value: Any) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError, RecursionError) as exc:
        raise P0PresentedAContextLineageCappedV2ParentError("canonical JSON invalid") from exc


def _file(value: Any) -> bytes: return _bytes(value) + b"\n"
def _digest(value: Any) -> str: return hashlib.sha256(_bytes(value)).hexdigest()
def _raw_digest(raw: bytes) -> str:
    if type(raw) is not bytes: raise P0PresentedAContextLineageCappedV2ParentError("raw must be exact bytes")
    return hashlib.sha256(raw).hexdigest()


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out: raise P0PresentedAContextLineageCappedV2ParentError("duplicate JSON key")
        out[key] = value
    return out


def _constant(value: str) -> None: raise P0PresentedAContextLineageCappedV2ParentError(f"non-finite JSON: {value}")


def _object(raw: bytes, label: str) -> dict[str, Any]:
    if type(raw) is not bytes or not raw or len(raw) > MAX_OBJECT_BYTES or raw.startswith(b"\xef\xbb\xbf") or b"\r" in raw or not raw.endswith(b"\n"):
        raise P0PresentedAContextLineageCappedV2ParentError(f"{label} framing invalid")
    try:
        text = raw.decode("utf-8", errors="strict")
        if unicodedata.normalize("NFC", text) != text: raise P0PresentedAContextLineageCappedV2ParentError(f"{label} not NFC")
        value = json.loads(text, object_pairs_hook=_pairs, parse_constant=_constant)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValueError) as exc:
        raise P0PresentedAContextLineageCappedV2ParentError(f"{label} JSON invalid") from exc
    if type(value) is not dict or _file(value) != raw: raise P0PresentedAContextLineageCappedV2ParentError(f"{label} noncanonical")
    return value


def _jsonl(raw: bytes, label: str) -> list[dict[str, Any]]:
    if type(raw) is not bytes or not raw or len(raw) > MAX_OBJECT_BYTES or b"\r" in raw or not raw.endswith(b"\n"):
        raise P0PresentedAContextLineageCappedV2ParentError(f"{label} framing invalid")
    result: list[dict[str, Any]] = []; offset = 0; index = 0
    while offset < len(raw):
        index += 1
        if index > MAX_ROWS: raise P0PresentedAContextLineageCappedV2ParentError(f"{label} row bound")
        newline = raw.find(b"\n", offset)
        if newline < 0: raise P0PresentedAContextLineageCappedV2ParentError(f"{label} truncated row")
        end = newline + 1
        if end - offset > MAX_OBJECT_BYTES: raise P0PresentedAContextLineageCappedV2ParentError(f"{label} row bound")
        result.append(_object(raw[offset:end], f"{label} row {index}")); offset = end
    return result


def _strict(value: Any, fields: frozenset[str], label: str) -> dict[str, Any]:
    if type(value) is not dict or frozenset(value) != fields: raise P0PresentedAContextLineageCappedV2ParentError(f"{label} fields mismatch")
    return value


def _sha(value: Any, field: str) -> str:
    if type(value) is not str or _SHA_RE.fullmatch(value) is None: raise P0PresentedAContextLineageCappedV2ParentError(f"{field} invalid SHA")
    return value


def _integer(value: Any, field: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum: raise P0PresentedAContextLineageCappedV2ParentError(f"{field} invalid integer")
    return value


def _boolean(value: Any, field: str) -> bool:
    if type(value) is not bool: raise P0PresentedAContextLineageCappedV2ParentError(f"{field} invalid boolean")
    return value


def _time(value: Any, field: str) -> datetime:
    if type(value) is not str or not value.endswith("Z") or len(value) > 64: raise P0PresentedAContextLineageCappedV2ParentError(f"{field} invalid time")
    try: parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc: raise P0PresentedAContextLineageCappedV2ParentError(f"{field} invalid time") from exc
    if parsed.isoformat().replace("+00:00", "Z") != value: raise P0PresentedAContextLineageCappedV2ParentError(f"{field} noncanonical time")
    return parsed


def _self(row: Mapping[str, Any], field: str, label: str) -> None:
    _sha(row[field], field)
    if row[field] != _digest({key: value for key, value in row.items() if key != field}): raise P0PresentedAContextLineageCappedV2ParentError(f"{label} self hash mismatch")


def _false(row: Mapping[str, Any], label: str) -> None:
    for field in FALSE_AUTHORITY_FIELDS:
        if _boolean(row[field], field) is not False: raise P0PresentedAContextLineageCappedV2ParentError(f"{label} authority escalation")


def _preflight(raws: Mapping[str, bytes]) -> dict[str, bytes]:
    if type(raws) is not dict or tuple(raws) != ALL_RAW_KEYS: raise P0PresentedAContextLineageCappedV2ParentError("raw role order/membership mismatch")
    total = 0; snap: dict[str, bytes] = {}
    for key in ALL_RAW_KEYS:
        value = raws[key]
        if type(value) is not bytes or not value or len(value) > MAX_OBJECT_BYTES: raise P0PresentedAContextLineageCappedV2ParentError(f"{key} byte bound/type")
        if key == "bridge_inventory_raw" and len(value) > MAX_BRIDGE_JSONL_BYTES:
            raise P0PresentedAContextLineageCappedV2ParentError("bridge inventory role byte bound")
        total += len(value)
        if total > MAX_AGGREGATE_RAW_BYTES: raise P0PresentedAContextLineageCappedV2ParentError("aggregate raw byte bound")
        snap[key] = value
    return snap


def _bridge(raw: bytes, selected: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    if type(raw) is not bytes or len(raw) > MAX_BRIDGE_JSONL_BYTES:
        raise P0PresentedAContextLineageCappedV2ParentError("bridge inventory role byte bound")
    rows = _jsonl(raw, "bridge")
    if len(rows) != len(selected): raise P0PresentedAContextLineageCappedV2ParentError("bridge/source selected count mismatch")
    result: list[dict[str, Any]] = []; total_payload = 0
    registry_ids: set[str] = set()
    for index, (value, source) in enumerate(zip(rows, selected), 1):
        row = _strict(value, _BRIDGE_FIELDS, "bridge row")
        if row["schema_version"] != "p0_presented_registry_capture_bridge_row_v1" or _integer(row["input_sequence"], "input_sequence", 1) != index:
            raise P0PresentedAContextLineageCappedV2ParentError("bridge schema/order mismatch")
        if any(row[field] != source[field] for field in _SELECTED_IDENTITY_FIELDS): raise P0PresentedAContextLineageCappedV2ParentError("bridge/source identity mismatch")
        if row["selected_input_sha256"] != _digest(source): raise P0PresentedAContextLineageCappedV2ParentError("bridge selected hash mismatch")
        registry_id = row["registry_record_id"]
        if type(registry_id) is not str or not registry_id or len(registry_id) > 256 or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,255}", registry_id) is None or registry_id == source["candidate_id"] or registry_id in registry_ids: raise P0PresentedAContextLineageCappedV2ParentError("bridge registry invalid/duplicate")
        registry_ids.add(row["registry_record_id"])
        _sha(row["registry_record_commitment_sha256"], "registry_record_commitment_sha256")
        for field in ("content_type", "capture_version", "normalization_version"):
            value = row[field]
            if type(value) is not str or not value or value != value.strip() or len(value) > MAX_METADATA_CHARS or unicodedata.normalize("NFC", value) != value or any(unicodedata.category(char) in _FORBIDDEN_METADATA_CATEGORIES for char in value):
                raise P0PresentedAContextLineageCappedV2ParentError(f"bridge {field} invalid")
        try: payload = base64.b64decode(row["payload_base64"].encode("ascii"), validate=True)
        except (AttributeError, UnicodeEncodeError, ValueError) as exc: raise P0PresentedAContextLineageCappedV2ParentError("bridge payload invalid") from exc
        if len(payload) > MAX_PAYLOAD_BYTES_PER_INPUT or base64.b64encode(payload).decode("ascii") != row["payload_base64"] or _integer(row["payload_bytes"], "payload_bytes") != len(payload) or _raw_digest(payload) != row["payload_sha256"]:
            raise P0PresentedAContextLineageCappedV2ParentError("bridge payload binding mismatch")
        total_payload += len(payload)
        if total_payload > MAX_TOTAL_PAYLOAD_BYTES: raise P0PresentedAContextLineageCappedV2ParentError("bridge total payload bound")
        _self(row, "bridge_row_sha256", "bridge row"); result.append(row)
    return result


def _state(raws: Mapping[str, bytes]) -> dict[str, Any]:
    source_plan = _object(raws["source_plan_raw"], "source plan")
    source_census_rows = _jsonl(raws["source_census_raw"], "source census")
    a_scope = _object(raws["a_scope_raw"], "A scope")
    a_frame = _object(raws["a_frame_raw"], "A frame")
    a_plan = _object(raws["a_plan_raw"], "A plan")
    a_rows = _jsonl(raws["a_census_raw"], "A census")
    if a_scope["upstream_source_sampling_plan_raw_sha256"] != _raw_digest(raws["source_plan_raw"]) or a_scope["upstream_bridge_inventory_raw_sha256"] != _raw_digest(raws["bridge_inventory_raw"]):
        raise P0PresentedAContextLineageCappedV2ParentError("A predecessor raw binding mismatch")
    if _time(source_plan["selection_sealed_at"], "source selection seal") >= _time(a_scope["created_at"], "A created_at"):
        raise P0PresentedAContextLineageCappedV2ParentError("source plan must precede A scope")
    selected = source_plan["selected_inputs"]
    if type(selected) is not list: raise P0PresentedAContextLineageCappedV2ParentError("source selected invalid")
    bridges = _bridge(raws["bridge_inventory_raw"], selected)
    source_by_id = {x["candidate_id"]: x for x in selected}; bridge_by_id = {x["candidate_id"]: x for x in bridges}
    source_census_by_id = {x["candidate_id"]: x for x in source_census_rows}
    if len(source_by_id) != len(selected) or len(bridge_by_id) != len(bridges): raise P0PresentedAContextLineageCappedV2ParentError("predecessor identity duplicate")
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list); eligible: list[dict[str, Any]] = []
    for row in a_rows:
        source = source_by_id.get(row.get("upstream_frame_candidate_id")); bridge = bridge_by_id.get(row.get("upstream_frame_candidate_id"))
        if source is None or bridge is None: raise P0PresentedAContextLineageCappedV2ParentError("A row upstream missing")
        source_candidate = source_census_by_id.get(source["candidate_id"])
        if source_candidate is None: raise P0PresentedAContextLineageCappedV2ParentError("selected source absent from census")
        try: payload_text=base64.b64decode(bridge["payload_base64"].encode("ascii"),validate=True).decode("utf-8",errors="strict")
        except (AttributeError,UnicodeDecodeError,UnicodeEncodeError,ValueError) as exc: raise P0PresentedAContextLineageCappedV2ParentError("bridged A payload invalid") from exc
        start,end=row.get("surface_start"),row.get("surface_end")
        if type(start) is not int or type(end) is not int or start<0 or end<=start or end>len(payload_text): raise P0PresentedAContextLineageCappedV2ParentError("A surface outside payload")
        expected = {"registry_record_id": bridge["registry_record_id"], "adapter_id": source["adapter_id"], "platform_scope": source["platform"], "payload_sha256": bridge["payload_sha256"], "source_profile": source["source_profile"], "utc_day": source["utc_day"], "content_fingerprint":_digest(payload_text), "surface_sha256":_digest(payload_text[start:end]), "context_observed_at":source_candidate["observed_at"], "source_published_at":source_candidate["published_at"]}
        if any(row.get(key) != value for key, value in expected.items()): raise P0PresentedAContextLineageCappedV2ParentError("A/source/bridge cross binding mismatch")
        item = {"candidate_id": row["candidate_id"], "context_unit_sha256": row["context_unit_sha256"], "source_frame_candidate_id": source["candidate_id"], "source_lineage_group_id": source["lineage_group_id"], "source_lineage_unit_sha256": source["lineage_unit_sha256"], "source_profile": source["source_profile"], "platform_scope": source["platform"], "utc_day": source["utc_day"], "adapter_id": source["adapter_id"]}
        if row["eligibility_status"] == "ELIGIBLE": groups[item["source_lineage_unit_sha256"]].append(item); eligible.append(item)
    strata = {(x["source_profile"], x["platform_scope"], x["utc_day"]): x["quota"] for x in a_scope["strata"]}
    inventory: list[dict[str, Any]] = []; seen_groups: set[str] = set(); units_by_stratum: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    for unit, members in groups.items():
        members.sort(key=lambda x: x["candidate_id"]); first = members[0]
        identity = (first["source_profile"], first["platform_scope"], first["utc_day"], first["source_lineage_group_id"])
        if any((x["source_profile"], x["platform_scope"], x["utc_day"], x["source_lineage_group_id"]) != identity for x in members) or first["source_lineage_group_id"] in seen_groups:
            raise P0PresentedAContextLineageCappedV2ParentError("lineage split/cross-stratum")
        seen_groups.add(first["source_lineage_group_id"]); key = identity[:3]
        if key not in strata: raise P0PresentedAContextLineageCappedV2ParentError("lineage outside strata")
        units_by_stratum[key].append(unit)
        inventory.append({"source_lineage_unit_sha256": unit, "source_lineage_group_id": first["source_lineage_group_id"], "source_frame_candidate_id": first["source_frame_candidate_id"], "source_profile": first["source_profile"], "platform_scope": first["platform_scope"], "utc_day": first["utc_day"], "eligible_context_count": len(members), "eligible_context_set_sha256": _digest([m["context_unit_sha256"] for m in members])})
    inventory.sort(key=lambda x: x["source_lineage_unit_sha256"])
    populations: list[dict[str, Any]] = []
    for x in a_scope["strata"]:
        key = (x["source_profile"], x["platform_scope"], x["utc_day"]); units = sorted(units_by_stratum.get(key, [])); G_h = len(units); n_h = x["quota"]
        if type(n_h) is not int or G_h < n_h: raise P0PresentedAContextLineageCappedV2ParentError("hard lineage underfill")
        populations.append({"source_profile": key[0], "platform_scope": key[1], "utc_day": key[2], "stratum_id": "P0:A:FRAME:STRATUM:" + _digest({"domain": "P0_PRESENTED_A_CONTEXT_FULL_FRAME_V1_STRATUM_ID", "source_profile": key[0], "platform_scope": key[1], "utc_day": key[2]}), "eligible_context_count": sum(len(groups[u]) for u in units), "G_h": G_h, "n_h": n_h, "eligible_lineage_set_sha256": _digest(units)})
    return {"source_plan": source_plan, "a_scope": a_scope, "a_frame": a_frame, "a_plan": a_plan, "eligible": eligible, "groups": groups, "inventory": inventory, "populations": populations}


def _prob(G_h: int, n_h: int, K_g: int) -> dict[str, int]:
    lp, lw, cp, cw, mp, mw = Fraction(n_h, G_h), Fraction(G_h, n_h), Fraction(1, K_g), Fraction(K_g, 1), Fraction(n_h, G_h*K_g), Fraction(G_h*K_g, n_h)
    return {"lineage_inclusion_probability_numerator": lp.numerator, "lineage_inclusion_probability_denominator": lp.denominator, "lineage_weight_numerator": lw.numerator, "lineage_weight_denominator": lw.denominator, "within_lineage_probability_numerator": cp.numerator, "within_lineage_probability_denominator": cp.denominator, "within_lineage_weight_numerator": cw.numerator, "within_lineage_weight_denominator": cw.denominator, "marginal_inclusion_probability_numerator": mp.numerator, "marginal_inclusion_probability_denominator": mp.denominator, "marginal_weight_numerator": mw.numerator, "marginal_weight_denominator": mw.denominator}


def _expected_frame(raws: Mapping[str, bytes], state: Mapping[str, Any], sealed_at: str) -> dict[str, Any]:
    if _time(sealed_at, "lineage_frame_sealed_at") <= _time(state["a_frame"]["frame_sealed_at"], "A frame seal"): raise P0PresentedAContextLineageCappedV2ParentError("lineage frame chronology")
    raw_hashes = {key: _raw_digest(raws[key]) for key in PRESEED_RAW_KEYS}; contexts = sorted(x["context_unit_sha256"] for x in state["eligible"]); lineages = sorted(state["groups"])
    material = {"schema_version": FRAME_SCHEMA, "record_origin": RECORD_ORIGIN, "component_version": COMPONENT_VERSION, "component_manifest_sha256": COMPONENT_MANIFEST_SHA256, "source_component_manifest_sha256": SOURCE_COMPONENT_MANIFEST_SHA256, "bridge_component_manifest_sha256": BRIDGE_COMPONENT_MANIFEST_SHA256, "a_v1_component_manifest_sha256": A_V1_COMPONENT_MANIFEST_SHA256, "preseed_raw_sha256": raw_hashes, "lineage_frame_sealed_at": sealed_at, "eligible_context_count": len(contexts), "eligible_source_lineage_count": len(lineages), "eligible_context_set_sha256": _digest(contexts), "eligible_lineage_set_sha256": _digest(lineages), "lineage_inventory": state["inventory"], "lineage_inventory_sha256": _digest(state["inventory"]), "stratum_populations": state["populations"], "max_selected_contexts_per_source_lineage": 1, "lineage_policy_preseed_sealed": True, "source_a_bridge_cross_binding_verified": True, "presented_serialization_only": True, "downstream_wiring_count": 0, "consumed_by_subject_v2": False, "consumed_by_packet_v2": False, "actual_source_evidence_count": 0, "actual_a_context_review_count": 0, "actual_surplus_review_count": 0, "statistical_denominator": "NONE", "metric_status": METRIC_STATUS, **{field: False for field in FALSE_AUTHORITY_FIELDS}, "operational_effect": OPERATIONAL_EFFECT, "gate_status": PRODUCER_GATE_STATUS, "replay_idempotency_key_sha256": _digest({"domain": REPLAY_DOMAIN, "stage": "FRAME", "raw_sha256": raw_hashes, "sealed_at": sealed_at})}
    return {**material, "artifact_sha256": _digest(material)}


def _expected_plan(raws: Mapping[str, bytes], state: Mapping[str, Any], frame: Mapping[str, Any], seed: Mapping[str, Any], sealed_at: str) -> dict[str, Any]:
    if _time(sealed_at, "selection_sealed_at") <= _time(seed["revealed_at"], "revealed_at"): raise P0PresentedAContextLineageCappedV2ParentError("selection chronology")
    if _time(state["a_plan"]["selection_sealed_at"], "A selection seal") >= _time(frame["lineage_frame_sealed_at"], "lineage frame seal"):
        raise P0PresentedAContextLineageCappedV2ParentError("A plan must precede lineage frame")
    derived = _digest({"domain": SEED_DERIVATION_DOMAIN, "component_manifest_sha256": COMPONENT_MANIFEST_SHA256, "future_seed_spec_sha256": seed["future_seed_spec_sha256"], "revealed_seed_sha256": seed["revealed_seed_sha256"], "frame_owner_precommit_sha256": seed["frame_owner_precommit_sha256"]})
    inv = {x["source_lineage_unit_sha256"]: x for x in state["inventory"]}; selected_units: set[str] = set(); rank_by_unit: dict[str, str] = {}; lineage_by_unit: dict[str, dict[str, Any]] = {}; selected_lineages: list[dict[str, Any]] = []; surplus_lineages: list[dict[str, Any]] = []
    for pop in state["populations"]:
        key = (pop["source_profile"], pop["platform_scope"], pop["utc_day"]); units = [u for u, members in state["groups"].items() if (members[0]["source_profile"], members[0]["platform_scope"], members[0]["utc_day"]) == key]
        ranked = sorted((_digest({"domain": LINEAGE_RANK_DOMAIN, "derived_seed_sha256": derived, "stratum_id": pop["stratum_id"], "eligible_lineage_set_sha256": pop["eligible_lineage_set_sha256"], "source_lineage_unit_sha256": u}), u) for u in units); chosen = {u for _, u in ranked[:pop["n_h"]]}; selected_units |= chosen
        for rank, unit in ranked:
            source = inv[unit]; p = _prob(pop["G_h"], pop["n_h"], source["eligible_context_count"]); item = {"source_lineage_unit_sha256": unit, "source_lineage_group_id": source["source_lineage_group_id"], "source_frame_candidate_id": source["source_frame_candidate_id"], "source_profile": source["source_profile"], "platform_scope": source["platform_scope"], "utc_day": source["utc_day"], "stratum_id": pop["stratum_id"], "G_h": pop["G_h"], "n_h": pop["n_h"], "K_g": source["eligible_context_count"], "lineage_rank_sha256": rank, "eligible_context_set_sha256": source["eligible_context_set_sha256"], **{k:p[k] for k in ("lineage_inclusion_probability_numerator","lineage_inclusion_probability_denominator","lineage_weight_numerator","lineage_weight_denominator")}}
            rank_by_unit[unit] = rank; lineage_by_unit[unit] = item; (selected_lineages if unit in chosen else surplus_lineages).append(item)
    sort_lineage = lambda x: (x["source_profile"],x["platform_scope"],x["utc_day"],x["lineage_rank_sha256"],x["source_lineage_unit_sha256"]); selected_lineages.sort(key=sort_lineage); surplus_lineages.sort(key=sort_lineage)
    selected_contexts: list[dict[str, Any]] = []; surplus_contexts: list[dict[str, Any]] = []
    for unit, members in state["groups"].items():
        lin = lineage_by_unit[unit]; ranked = sorted((_digest({"domain": CONTEXT_RANK_DOMAIN, "derived_seed_sha256": derived, "source_lineage_unit_sha256": unit, "eligible_context_set_sha256": lin["eligible_context_set_sha256"], "context_unit_sha256": m["context_unit_sha256"]}), m) for m in members); chosen_id = ranked[0][1]["candidate_id"] if unit in selected_units else None; p = _prob(lin["G_h"],lin["n_h"],lin["K_g"])
        for context_rank, m in ranked:
            chosen = m["candidate_id"] == chosen_id; item = {"input_sequence":0,"disposition":"SELECTED" if chosen else "SURPLUS","surplus_reason":"NONE" if chosen else ("WITHIN_SELECTED_LINEAGE_SURPLUS" if unit in selected_units else "UNSELECTED_LINEAGE_SURPLUS"),"candidate_id":m["candidate_id"],"context_unit_sha256":m["context_unit_sha256"],"source_lineage_unit_sha256":unit,"source_lineage_group_id":m["source_lineage_group_id"],"source_frame_candidate_id":m["source_frame_candidate_id"],"source_profile":m["source_profile"],"platform_scope":m["platform_scope"],"utc_day":m["utc_day"],"stratum_id":lin["stratum_id"],"adapter_id":m["adapter_id"],"G_h":lin["G_h"],"n_h":lin["n_h"],"K_g":lin["K_g"],"lineage_rank_sha256":rank_by_unit[unit],"context_rank_sha256":context_rank,"eligible_context_set_sha256":lin["eligible_context_set_sha256"],**p}; (selected_contexts if chosen else surplus_contexts).append(item)
    sort_context=lambda x:(x["source_profile"],x["platform_scope"],x["utc_day"],x["lineage_rank_sha256"],x["context_rank_sha256"]); selected_contexts.sort(key=sort_context); surplus_contexts.sort(key=sort_context)
    for index,item in enumerate(selected_contexts,1): item["input_sequence"]=index
    if len(selected_contexts)!=EXPECTED_TOTAL or len({x["source_lineage_unit_sha256"] for x in selected_contexts})!=EXPECTED_TOTAL: raise P0PresentedAContextLineageCappedV2ParentError("selected lineage cap/count")
    raw_hashes={key:_raw_digest(raws[key]) for key in ALL_RAW_KEYS}; counts=Counter(x["source_profile"] for x in selected_contexts); expected_counts={p:EXPECTED_PER_PROFILE for p in SOURCE_PROFILES}
    if dict(counts)!=expected_counts: raise P0PresentedAContextLineageCappedV2ParentError("profile counts")
    material={"schema_version":PLAN_SCHEMA,"record_origin":RECORD_ORIGIN,"component_version":COMPONENT_VERSION,"component_manifest_sha256":COMPONENT_MANIFEST_SHA256,"all_raw_sha256":raw_hashes,"lineage_frame_raw_sha256":frame["_raw_sha256"],"lineage_frame_artifact_sha256":frame["artifact_sha256"],"lineage_seed_receipt_raw_sha256":seed["_raw_sha256"],"lineage_seed_receipt_artifact_sha256":seed["artifact_sha256"],"predecessor_a_plan_selection_used":False,"selection_algorithm":SELECTION_ALGORITHM,"derived_seed_sha256":derived,"selected_lineages":selected_lineages,"eligible_lineage_surplus":surplus_lineages,"selected_inputs":selected_contexts,"eligible_context_surplus":surplus_contexts,"selected_lineage_count":len(selected_lineages),"eligible_lineage_surplus_count":len(surplus_lineages),"selected_input_count":len(selected_contexts),"eligible_context_surplus_count":len(surplus_contexts),"selected_lineage_set_sha256":_digest(selected_lineages),"lineage_surplus_set_sha256":_digest(surplus_lineages),"selected_input_set_sha256":_digest(selected_contexts),"context_surplus_set_sha256":_digest(surplus_contexts),"per_profile_counts":expected_counts,"lineage_partition_exact":True,"context_partition_exact":True,"global_lineage_cap_verified":True,"max_selected_contexts_per_source_lineage":1,"replacement_allowed":False,"spill_allowed":False,"backfill_allowed":False,"contexts_are_iid":False,"same_lineage_pairwise_joint_inclusion_probability":"ZERO","probability_design_is_conditional_presented_only":True,"presented_serialization_only":True,"downstream_wiring_count":0,"consumed_by_subject_v2":False,"consumed_by_packet_v2":False,"actual_source_evidence_count":0,"actual_a_context_review_count":0,"actual_surplus_review_count":0,"statistical_denominator":"NONE","metric_status":METRIC_STATUS,**{f:False for f in FALSE_AUTHORITY_FIELDS},"selection_sealed_at":sealed_at,"replay_idempotency_key_sha256":_digest({"domain":REPLAY_DOMAIN,"stage":"PLAN","raw_sha256":raw_hashes,"frame_raw_sha256":frame["_raw_sha256"],"seed_raw_sha256":seed["_raw_sha256"],"selection_sealed_at":sealed_at}),"operational_effect":OPERATIONAL_EFFECT,"gate_status":PRODUCER_GATE_STATUS}
    return {**material,"artifact_sha256":_digest(material)}


_SOURCE_PARENT_ENTRYPOINT = source_parent.validate_frame_and_plan_against_raw_inputs
_SOURCE_PARENT_MODULE = source_parent
_SOURCE_PARENT_CODE = _SOURCE_PARENT_ENTRYPOINT.__code__
_SOURCE_PARENT_DEFAULTS = _SOURCE_PARENT_ENTRYPOINT.__defaults__
_SOURCE_PARENT_KWDEFAULTS = _SOURCE_PARENT_ENTRYPOINT.__kwdefaults__
_A_PARENT_ENTRYPOINT = a_parent.validate_a_context_frame_and_plan_against_raw_inputs
_A_PARENT_MODULE = a_parent
_A_PARENT_CODE = _A_PARENT_ENTRYPOINT.__code__
_A_PARENT_DEFAULTS = _A_PARENT_ENTRYPOINT.__defaults__
_A_PARENT_KWDEFAULTS = _A_PARENT_ENTRYPOINT.__kwdefaults__
_HASHLIB_SHA256 = hashlib.sha256
_JSON_LOADS = json.loads
_JSON_DUMPS = json.dumps
_LOCAL_HELPERS = (
    _bytes, _file, _digest, _raw_digest, _pairs, _constant, _object,
    _jsonl, _strict, _sha, _integer, _boolean, _time, _self, _false,
    _preflight, _bridge, _state, _prob, _expected_frame, _expected_plan,
)
_LOCAL_HELPER_CODES = tuple(helper.__code__ for helper in _LOCAL_HELPERS)
_LOCAL_HELPER_DEFAULTS = tuple(helper.__defaults__ for helper in _LOCAL_HELPERS)
_LOCAL_HELPER_KWDEFAULTS = tuple(helper.__kwdefaults__ for helper in _LOCAL_HELPERS)
_CONSTANT_SNAPSHOT = (
    FRAME_SCHEMA, SEED_SCHEMA, PLAN_SCHEMA, RECEIPT_SCHEMA, COMPONENT_VERSION,
    COMPONENT_MANIFEST_SHA256, SOURCE_COMPONENT_MANIFEST_SHA256,
    BRIDGE_COMPONENT_MANIFEST_SHA256, A_V1_COMPONENT_MANIFEST_SHA256,
    RECORD_ORIGIN, OPERATIONAL_EFFECT, PRODUCER_GATE_STATUS,
    PARENT_GATE_STATUS, METRIC_STATUS, SELECTION_ALGORITHM,
    LINEAGE_RANK_DOMAIN, CONTEXT_RANK_DOMAIN, SEED_DERIVATION_DOMAIN,
    REPLAY_DOMAIN, MAX_OBJECT_BYTES, MAX_AGGREGATE_RAW_BYTES, MAX_ROWS,
    MAX_METADATA_CHARS, MAX_PAYLOAD_BYTES_PER_INPUT, MAX_TOTAL_PAYLOAD_BYTES,
    MAX_BRIDGE_JSONL_BYTES,
    EXPECTED_TOTAL, EXPECTED_PER_PROFILE, SOURCE_PROFILES, SOURCE_RAW_KEYS,
    A_RAW_KEYS, PRESEED_RAW_KEYS, ALL_RAW_KEYS, FALSE_AUTHORITY_FIELDS,
    _BRIDGE_FIELDS, _SELECTED_IDENTITY_FIELDS, _FORBIDDEN_METADATA_CATEGORIES, _FRAME_FIELDS, _SEED_FIELDS,
    _LINEAGE_ITEM_FIELDS, _CONTEXT_ITEM_FIELDS, _PLAN_FIELDS,
)


def _runtime_guard() -> None:
    current_helpers = (
        _bytes, _file, _digest, _raw_digest, _pairs, _constant, _object,
        _jsonl, _strict, _sha, _integer, _boolean, _time, _self, _false,
        _preflight, _bridge, _state, _prob, _expected_frame, _expected_plan,
    )
    current_constants = (
        FRAME_SCHEMA, SEED_SCHEMA, PLAN_SCHEMA, RECEIPT_SCHEMA, COMPONENT_VERSION,
        COMPONENT_MANIFEST_SHA256, SOURCE_COMPONENT_MANIFEST_SHA256,
        BRIDGE_COMPONENT_MANIFEST_SHA256, A_V1_COMPONENT_MANIFEST_SHA256,
        RECORD_ORIGIN, OPERATIONAL_EFFECT, PRODUCER_GATE_STATUS,
        PARENT_GATE_STATUS, METRIC_STATUS, SELECTION_ALGORITHM,
        LINEAGE_RANK_DOMAIN, CONTEXT_RANK_DOMAIN, SEED_DERIVATION_DOMAIN,
        REPLAY_DOMAIN, MAX_OBJECT_BYTES, MAX_AGGREGATE_RAW_BYTES, MAX_ROWS,
        MAX_METADATA_CHARS, MAX_PAYLOAD_BYTES_PER_INPUT, MAX_TOTAL_PAYLOAD_BYTES,
        MAX_BRIDGE_JSONL_BYTES,
        EXPECTED_TOTAL, EXPECTED_PER_PROFILE, SOURCE_PROFILES, SOURCE_RAW_KEYS,
        A_RAW_KEYS, PRESEED_RAW_KEYS, ALL_RAW_KEYS, FALSE_AUTHORITY_FIELDS,
        _BRIDGE_FIELDS, _SELECTED_IDENTITY_FIELDS, _FORBIDDEN_METADATA_CATEGORIES, _FRAME_FIELDS, _SEED_FIELDS,
        _LINEAGE_ITEM_FIELDS, _CONTEXT_ITEM_FIELDS, _PLAN_FIELDS,
    )
    source_entrypoint = source_parent.validate_frame_and_plan_against_raw_inputs
    a_entrypoint = a_parent.validate_a_context_frame_and_plan_against_raw_inputs
    if (
        source_parent is not _SOURCE_PARENT_MODULE
        or a_parent is not _A_PARENT_MODULE
        or source_entrypoint is not _SOURCE_PARENT_ENTRYPOINT
        or source_entrypoint.__code__ is not _SOURCE_PARENT_CODE
        or source_entrypoint.__defaults__ != _SOURCE_PARENT_DEFAULTS
        or source_entrypoint.__kwdefaults__ != _SOURCE_PARENT_KWDEFAULTS
        or a_entrypoint is not _A_PARENT_ENTRYPOINT
        or a_entrypoint.__code__ is not _A_PARENT_CODE
        or a_entrypoint.__defaults__ != _A_PARENT_DEFAULTS
        or a_entrypoint.__kwdefaults__ != _A_PARENT_KWDEFAULTS
        or hashlib.sha256 is not _HASHLIB_SHA256
        or json.loads is not _JSON_LOADS
        or json.dumps is not _JSON_DUMPS
        or current_helpers != _LOCAL_HELPERS
        or tuple(helper.__code__ for helper in _LOCAL_HELPERS) != _LOCAL_HELPER_CODES
        or tuple(helper.__defaults__ for helper in _LOCAL_HELPERS) != _LOCAL_HELPER_DEFAULTS
        or tuple(helper.__kwdefaults__ for helper in _LOCAL_HELPERS) != _LOCAL_HELPER_KWDEFAULTS
        or current_constants != _CONSTANT_SNAPSHOT
    ):
        raise P0PresentedAContextLineageCappedV2ParentError("runtime callable integrity drift")


_RUNTIME_GUARD_CODE = _runtime_guard.__code__
_RUNTIME_GUARD_DEFAULTS = _runtime_guard.__defaults__
_RUNTIME_GUARD_KWDEFAULTS = _runtime_guard.__kwdefaults__


def validate_lineage_frame_seed_and_plan_against_raw_inputs(lineage_frame_raw: bytes, lineage_seed_raw: bytes, sampling_plan_raw: bytes, _integrity_guard: Any = _runtime_guard, **raw_inputs: bytes) -> dict[str, Any]:
    if (
        _integrity_guard is not _runtime_guard
        or _integrity_guard.__code__ is not _RUNTIME_GUARD_CODE
        or _integrity_guard.__defaults__ != _RUNTIME_GUARD_DEFAULTS
        or _integrity_guard.__kwdefaults__ != _RUNTIME_GUARD_KWDEFAULTS
    ):
        raise P0PresentedAContextLineageCappedV2ParentError("runtime guard integrity drift")
    _integrity_guard()
    raws=_preflight(raw_inputs)
    for label, raw in (("lineage frame", lineage_frame_raw), ("lineage seed", lineage_seed_raw), ("lineage plan", sampling_plan_raw)):
        if type(raw) is not bytes or not raw or len(raw) > MAX_OBJECT_BYTES:
            raise P0PresentedAContextLineageCappedV2ParentError(f"{label} byte bound/type")
    source_entrypoint = source_parent.validate_frame_and_plan_against_raw_inputs
    a_entrypoint = a_parent.validate_a_context_frame_and_plan_against_raw_inputs
    if source_entrypoint is not _SOURCE_PARENT_ENTRYPOINT or a_entrypoint is not _A_PARENT_ENTRYPOINT:
        raise P0PresentedAContextLineageCappedV2ParentError("predecessor parent callable drift")
    source_receipt=source_parent.validate_frame_and_plan_against_raw_inputs(raws["source_frame_raw"],raws["source_plan_raw"],scope_raw=raws["source_scope_raw"],census_raw=raws["source_census_raw"],seed_receipt_raw=raws["source_seed_raw"])
    a_receipt=a_parent.validate_a_context_frame_and_plan_against_raw_inputs(raws["a_frame_raw"],raws["a_plan_raw"],scope_raw=raws["a_scope_raw"],census_raw=raws["a_census_raw"],seed_receipt_raw=raws["a_seed_raw"])
    expected_source = {"schema_version":"p0_full_eligible_frame_v2_parent_receipt_v1","expected_component_manifest_sha256":SOURCE_COMPONENT_MANIFEST_SHA256,"scope_raw_sha256":_raw_digest(raws["source_scope_raw"]),"census_raw_sha256":_raw_digest(raws["source_census_raw"]),"frame_manifest_raw_sha256":_raw_digest(raws["source_frame_raw"]),"seed_receipt_raw_sha256":_raw_digest(raws["source_seed_raw"]),"sampling_plan_raw_sha256":_raw_digest(raws["source_plan_raw"]),"selected_input_count":40,"parent_separate_implementation_frame_replay_verified":True,"same_process_isolation_verified":False,"core_code_identity_verified":False,"parent_code_identity_verified":False,"external_population_completeness_verified":False,"owner_authority_verified":False,"external_seed_provenance_verified":False,"runtime_execution_verified":False,"actual_source_evidence_verified":False,"actual_authority_granted":False,"p0_phase_exit":False,"production_approval":False,"full_scan_approval":False,"gate_status":"PRESENTED_FRAME_PARENT_REPLAY_PASS_ALL_AUTHORITY_NO_GO"}
    if any(source_receipt.get(k)!=v for k,v in expected_source.items()): raise P0PresentedAContextLineageCappedV2ParentError("source parent receipt mismatch")
    source_self={k:v for k,v in source_receipt.items() if k!="receipt_sha256"}
    if source_receipt.get("receipt_sha256")!=_digest(source_self): raise P0PresentedAContextLineageCappedV2ParentError("source parent receipt self hash mismatch")
    expected_a={"schema_version":"p0_presented_a_context_full_frame_v1_parent_receipt_v1","scope_raw_sha256":_raw_digest(raws["a_scope_raw"]),"census_raw_sha256":_raw_digest(raws["a_census_raw"]),"frame_raw_sha256":_raw_digest(raws["a_frame_raw"]),"seed_receipt_raw_sha256":_raw_digest(raws["a_seed_raw"]),"plan_raw_sha256":_raw_digest(raws["a_plan_raw"]),"parent_separate_implementation_frame_replay_verified":True,"actual_a_context_review_count":0,"actual_surplus_review_count":0,"statistical_denominator_contribution":"NONE","inferential_metrics_allowed":False,"complete_case_metrics_allowed":False,"same_process_isolation_verified":False,"producer_code_identity_verified":False,"parent_code_identity_verified":False,"credited_actual_a_context_count":0,"gate_status":"PRESENTED_A_CONTEXT_FRAME_PARENT_REPLAY_PASS_ALL_AUTHORITY_NO_GO","action_applied":False,"operational_effect":OPERATIONAL_EFFECT}
    if any(a_receipt.get(k)!=v for k,v in expected_a.items()): raise P0PresentedAContextLineageCappedV2ParentError("A parent receipt mismatch")
    for field in ("external_context_enumeration_completeness_verified","external_owner_authority_verified","enumeration_adapter_runtime_verified","rights_factual_authority_verified","source_capture_authority_verified","seed_authority_verified","seed_randomness_authority_verified","probability_design_authority_verified","annotation_not_started_authority_verified","code_identity_verified","runtime_execution_verified","actual_a_context_evidence_verified","route_packet_runtime_credit_authority_verified","actual_authority_granted","p0_phase_exit","production_approval","full_scan_approval"):
        if a_receipt.get(field) is not False: raise P0PresentedAContextLineageCappedV2ParentError("A parent authority escalation")
    a_self={k:v for k,v in a_receipt.items() if k!="receipt_sha256"}
    if a_receipt.get("receipt_sha256")!=_digest(a_self): raise P0PresentedAContextLineageCappedV2ParentError("A parent receipt self hash mismatch")
    state=_state(raws); presented_frame=_strict(_object(lineage_frame_raw,"lineage frame"),_FRAME_FIELDS,"lineage frame"); expected_frame=_expected_frame(raws,state,presented_frame["lineage_frame_sealed_at"])
    if lineage_frame_raw!=_file(expected_frame): raise P0PresentedAContextLineageCappedV2ParentError("lineage frame differs from independent replay")
    presented_seed=_strict(_object(lineage_seed_raw,"lineage seed"),_SEED_FIELDS,"lineage seed")
    if presented_seed["schema_version"]!=SEED_SCHEMA or presented_seed["record_origin"]!=RECORD_ORIGIN or presented_seed["component_version"]!=COMPONENT_VERSION or presented_seed["component_manifest_sha256"]!=COMPONENT_MANIFEST_SHA256: raise P0PresentedAContextLineageCappedV2ParentError("seed contract mismatch")
    seed_id=presented_seed["seed_receipt_id"]
    if type(seed_id) is not str or not seed_id or len(seed_id)>512 or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,511}",seed_id) is None: raise P0PresentedAContextLineageCappedV2ParentError("seed_receipt_id invalid")
    for field in ("lineage_frame_raw_sha256","lineage_frame_artifact_sha256","future_seed_spec_sha256","revealed_seed_sha256","frame_owner_precommit_sha256"): _sha(presented_seed[field],field)
    if presented_seed["lineage_frame_raw_sha256"]!=_raw_digest(lineage_frame_raw) or presented_seed["lineage_frame_artifact_sha256"]!=expected_frame["artifact_sha256"] or presented_seed["future_seed_spec_sha256"]!=state["a_scope"]["future_seed_spec_sha256"]: raise P0PresentedAContextLineageCappedV2ParentError("seed binding mismatch")
    if _time(presented_seed["frame_owner_precommitted_at"],"precommit")<=_time(expected_frame["lineage_frame_sealed_at"],"frame seal") or _time(presented_seed["revealed_at"],"reveal")<=_time(presented_seed["frame_owner_precommitted_at"],"precommit"): raise P0PresentedAContextLineageCappedV2ParentError("seed chronology")
    for field in ("owner_authority_verified","seed_authority_verified","seed_randomness_authority_verified","trusted_time_verified","action_applied"):
        if _boolean(presented_seed[field],field) is not False: raise P0PresentedAContextLineageCappedV2ParentError("seed authority escalation")
    if presented_seed["operational_effect"]!=OPERATIONAL_EFFECT: raise P0PresentedAContextLineageCappedV2ParentError("seed operational effect")
    _self(presented_seed,"artifact_sha256","lineage seed")
    frame={**expected_frame,"_raw_sha256":_raw_digest(lineage_frame_raw)}; seed={**presented_seed,"_raw_sha256":_raw_digest(lineage_seed_raw)}
    presented_plan=_strict(_object(sampling_plan_raw,"lineage plan"),_PLAN_FIELDS,"lineage plan")
    for item in presented_plan["selected_lineages"]+presented_plan["eligible_lineage_surplus"]: _strict(item,_LINEAGE_ITEM_FIELDS,"lineage item")
    for item in presented_plan["selected_inputs"]+presented_plan["eligible_context_surplus"]: _strict(item,_CONTEXT_ITEM_FIELDS,"context item")
    expected_plan=_expected_plan(raws,state,frame,seed,presented_plan["selection_sealed_at"])
    if sampling_plan_raw!=_file(expected_plan): raise P0PresentedAContextLineageCappedV2ParentError("lineage plan differs from independent replay")
    _false(expected_plan,"lineage plan")
    receipt={"schema_version":RECEIPT_SCHEMA,"component_manifest_sha256":COMPONENT_MANIFEST_SHA256,"lineage_frame_raw_sha256":_raw_digest(lineage_frame_raw),"lineage_seed_raw_sha256":_raw_digest(lineage_seed_raw),"sampling_plan_raw_sha256":_raw_digest(sampling_plan_raw),"selected_context_count":EXPECTED_TOTAL,"selected_input_count":EXPECTED_TOTAL,"eligible_context_surplus_count":len(expected_plan["eligible_context_surplus"]),"selected_lineage_count":EXPECTED_TOTAL,"eligible_lineage_surplus_count":len(expected_plan["eligible_lineage_surplus"]),"parent_separate_implementation_frame_replay_verified":True,"parent_seed_structure_and_binding_validation_verified":True,"parent_separate_implementation_lineage_plan_replay_verified":True,"lineage_partition_exact":True,"context_partition_exact":True,"global_lineage_cap_verified":True,"actual_source_evidence_count":0,"actual_a_context_review_count":0,"actual_surplus_review_count":0,"statistical_denominator":"NONE","metric_status":METRIC_STATUS,**{f:False for f in FALSE_AUTHORITY_FIELDS},"operational_effect":OPERATIONAL_EFFECT,"gate_status":PARENT_GATE_STATUS}
    return {**receipt,"receipt_sha256":_digest(receipt)}


validate_lineage_frame_and_plan_against_raw_inputs = validate_lineage_frame_seed_and_plan_against_raw_inputs

__all__=["P0PresentedAContextLineageCappedV2ParentError","PARENT_GATE_STATUS","RECEIPT_SCHEMA","FALSE_AUTHORITY_FIELDS","validate_lineage_frame_seed_and_plan_against_raw_inputs","validate_lineage_frame_and_plan_against_raw_inputs"]
