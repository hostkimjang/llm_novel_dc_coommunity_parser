"""최종 same-pass 객체의 진단 필드만 제한된 JSON으로 투영한다. 공개 판정 권한은 없다."""
from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "source_context_diagnostics_v1"
MAX_BYTES = 65536
MAX_ITEMS = 24
MAX_TEXT = 512

PROJECTION_FIELDS = ("speech_act", "target_kind", "target_surface", "target_span", "target_media",
    "request_conditions", "reference_works", "excluded_works", "work_roles", "work_relation_evidence",
    "scope_hint", "fallback", "reasons")
LOCATION_FIELDS = ("raw_path", "raw_text_span", "raw_span", "source_origin", "source_index", "original_index",
                   "selection_key", "carrier_alignment", "kind", "span", "line_span")
SOURCE_FIELDS = ("source_id", "parent_source_id", "text", "span", "source_role", "source_origin",
                 "source_index", "original_index", "raw_path", "raw_text_span", "carrier_alignment")
CLAIM_FIELDS = ("claim_id", "source_id", "speaker", "kind", "text", "span", "evaluation_event_ids",
                "initial_support", "final_support", "attribution", "speaker_source", "support_attribution")
EVENT_FIELDS = ("source_id", "event_id", "parent_event_id", "predicate", "predicate_span", "actor", "speaker",
    "polarity", "evaluation_polarity", "realization", "realization_source", "assertion_span", "kind", "claim_id", "evidence_text",
    "final_support", "temporal_scope", "attribution", "support_attribution")
SCOPE_GUARD_FIELDS = ("gate", "status", "code", "calls", "first_rejection", "applied", "publication_authority")

PROOF_FIELDS = ("rule", "source_id", "claim_id", "raw_path", "raw_span", "sourcequote", "source_sha256",
                "claimant", "claim_kind", "final_support", "predicate_spans", "event_ids", "claim_view")


def _get(obj: Any, key: str, default=None):
    return obj.get(key, default) if isinstance(obj, dict) else getattr(obj, key, default)


def _encoded(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


class _Projection:
    def __init__(self):
        self.omitted = {}

    def omit(self, path: str, amount: int = 1):
        self.omitted[path] = self.omitted.get(path, 0) + amount

    def scalar(self, value: Any, path: str, depth: int = 0):
        if value is None or isinstance(value, (bool, int)):
            return value
        if isinstance(value, str):
            if len(value) > MAX_TEXT:
                self.omit(path + ".characters", len(value) - MAX_TEXT)
            return value[:MAX_TEXT]
        if isinstance(value, (tuple, list)) and depth < 3:
            if len(value) > MAX_ITEMS:
                self.omit(path + ".items", len(value) - MAX_ITEMS)
            return [self.scalar(item, path, depth + 1) for item in value[:MAX_ITEMS]]
        # 함수·원문 owner 객체·알 수 없는 객체를 repr/asdict로 직렬화하지 않는다.
        self.omit(path + ".unsupported_values")
        return None

    def fields(self, obj: Any, names: tuple, path: str) -> dict:
        return {name: self.scalar(_get(obj, name), path + "." + name) for name in names}

    def records(self, values: Any, names: tuple, path: str) -> list:
        values = values if isinstance(values, (tuple, list)) else ()
        if len(values) > MAX_ITEMS:
            self.omit(path + ".items", len(values) - MAX_ITEMS)
        return [self.fields(value, names, path) for value in values[:MAX_ITEMS]]


def _base(status: str, reason: str | None = None) -> dict:
    return {"schema_version": SCHEMA_VERSION, "status": status, "publication_authority": False,
            "max_bytes": MAX_BYTES, "byte_count_basis": "UTF8_CANONICAL_JSON",
            "reason_codes": [reason] if reason else [], "omitted_counts": {},
            "projection": {}, "channels": [], "ledgers": [], "explanation": {}, "scope_state_guards": []}


def _bound_payload(payload: dict, omitted: dict) -> dict:
    """UTF-8 JSON 전체에 상한을 적용하고 생략한 항목 수를 기록한다."""
    # 생략 경로도 producer의 고정 whitelist에서만 나오며 원문은 key가 되지 않는다.
    payload["omitted_counts"] = dict(omitted)
    if omitted:
        payload["status"] = "TRUNCATED"
        payload["reason_codes"].append("FIELD_LIMIT")
    while len(_encoded(payload)) > MAX_BYTES:
        choices = []
        for name in ("channels", "ledgers", "scope_state_guards"):
            if payload[name]:
                choices.append((len(_encoded(payload[name][-1])), name, payload[name]))
        for name in ("proofs", "unresolved"):
            values = payload["explanation"].get(name)
            if isinstance(values, list) and values:
                choices.append((len(_encoded(values[-1])), "explanation." + name, values))
        if not choices:
            # 단일 projection도 예외적으로 큰 경우 진단 본문만 생략한다.
            payload["projection"] = {}
            payload["explanation"] = {}
            payload["omitted_counts"]["payload_sections"] = 2
            payload["status"] = "TRUNCATED"
            if "BYTE_LIMIT" not in payload["reason_codes"]:
                payload["reason_codes"].append("BYTE_LIMIT")
            break
        _, name, values = max(choices, key=lambda item: item[0])
        values.pop()
        payload["omitted_counts"][name + ".byte_limit_items"] = payload["omitted_counts"].get(name + ".byte_limit_items", 0) + 1
        payload["status"] = "TRUNCATED"
        if "BYTE_LIMIT" not in payload["reason_codes"]:
            payload["reason_codes"].append("BYTE_LIMIT")
    # 공개 결과나 producer 객체는 변경하지 않는다.
    assert len(_encoded(payload)) <= MAX_BYTES
    return payload


def export_source_context_diagnostics(output: Any, *, enabled: bool) -> dict:
    if not enabled:
        return _base("OFF", "DISABLED")
    private = getattr(output, "__dict__", {})
    receipt = private.get("_final_source_context_receipt")
    guard_values = private.get("_source_scope_state_diagnostics")
    guard_values = guard_values if isinstance(guard_values, dict) else {}
    guards = [guard_values[name] for name in ("surface_title_anchor", "propriety_question_scope", "propriety_callback",
        "general_context_capture", "general_context_verify", "general_context_adoption")
        if isinstance(guard_values.get(name), dict)]
    if not isinstance(receipt, dict):
        projection = _Projection()
        payload = _base("NOT_AVAILABLE", "NO_FINAL_NATIVE_RECEIPT")
        payload["scope_state_guards"] = projection.records(guards, SCOPE_GUARD_FIELDS, "scope_state_guards")
        return _bound_payload(payload, projection.omitted)
    native = receipt.get("native_object")
    context = receipt.get("context")
    if native is None or native is not private.get("_final_source_context_native") or context is not private.get("_final_source_context_owner"):
        return _base("NOT_AVAILABLE", "NATIVE_RECEIPT_BINDING_UNAVAILABLE")
    projection = _Projection()
    payload = _base("STORED")
    payload["scope_state_guards"] = projection.records(guards, SCOPE_GUARD_FIELDS, "scope_state_guards")
    payload["capture_status"] = projection.scalar(_get(native, "capture_status"), "capture_status")
    payload["native_verification_status"] = projection.scalar(receipt.get("native_verification_status"), "native_verification_status")
    payload["projection"] = projection.fields(_get(native, "projection"), PROJECTION_FIELDS, "projection")
    channels = _get(native, "channel_values", ())
    if len(channels) > MAX_ITEMS:
        projection.omit("channels.items", len(channels) - MAX_ITEMS)
    for channel in channels[:MAX_ITEMS]:
        item = projection.fields(channel, ("channel", "field", "index", "value", "value_kind", "rule"), "channels")
        item["locations"] = projection.records(_get(channel, "locations", ()), LOCATION_FIELDS, "channels.locations")
        payload["channels"].append(item)
    ledgers = [ledger for ledger in (_get(native, "author_ledger"), *(_get(native, "comment_ledgers", ()) or ())) if ledger is not None]
    if len(ledgers) > MAX_ITEMS:
        projection.omit("ledgers.items", len(ledgers) - MAX_ITEMS)
    for ledger in ledgers[:MAX_ITEMS]:
        item = projection.fields(ledger, ("source_id", "source_role", "source_index", "native_version", "input_alignment"), "ledgers")
        for key, fields in (("sources", SOURCE_FIELDS), ("claims", CLAIM_FIELDS), ("evaluations", EVENT_FIELDS),
                            ("graph_edges", ("source_id", "relation", "target_id", "recorded_by"))):
            item[key] = projection.records(_get(ledger, key, ()), fields, "ledgers." + key)
        for event, exported in zip((_get(ledger, "evaluations", ()) or ())[:MAX_ITEMS], item["evaluations"]):
            exported["objects"] = projection.records(_get(event, "objects", ()),
                ("text", "span", "head", "works", "relation", "owner", "owner_span"), "ledgers.evaluations.objects")
            exported["grammatical_subject"] = projection.fields(_get(event, "grammatical_subject"),
                ("actor", "text", "span", "explicit"), "ledgers.evaluations.grammatical_subject")
        payload["ledgers"].append(item)
    explanation = _get(context, "_final_source_context_explanation")
    if explanation is not None:
        payload["explanation"] = projection.fields(explanation, ("supported", "input_fingerprint", "unresolved", "source_kind"), "explanation")
        payload["explanation"]["proofs"] = projection.records(_get(explanation, "proofs", ()), PROOF_FIELDS, "explanation.proofs")
    return _bound_payload(payload, projection.omitted)


def diagnostics_policy(enabled: bool) -> dict:
    return {"schema_version": SCHEMA_VERSION, "enabled": enabled, "max_bytes": MAX_BYTES,
            "byte_count_basis": "UTF8_CANONICAL_JSON",
            "max_items_per_collection": MAX_ITEMS, "max_text_characters": MAX_TEXT,
            "publication_authority": False}
