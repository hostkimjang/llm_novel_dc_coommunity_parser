from __future__ import annotations

"""Additive, no-public-write observation envelopes and sidecar receipts.

This module is intentionally unused by the runtime by default.  It provides a
small, independently verifiable envelope around measurement payloads while
leaving legacy receipts, ``run_meta`` and publication WAL records untouched.
Both records are self-hashed using canonical JSON and always carry
``public_apply=False``.
"""

import hashlib
import json
import re
from typing import Any, Mapping


OBSERVATION_ENVELOPE_SCHEMA = "observation_envelope_v1"
SIDECAR_RECEIPT_SCHEMA = "sidecar_receipt_v1"
# Descriptive aliases used by callers that refer to schemas as versions.
OBSERVATION_ENVELOPE_V1 = OBSERVATION_ENVELOPE_SCHEMA
SIDECAR_RECEIPT_V1 = SIDECAR_RECEIPT_SCHEMA

_HEX64 = re.compile(r"^[0-9a-f]{64}$")

OBSERVATION_KINDS = frozenset(
    {"PUBLICATION_DRIFT", "REVIEW_ROUTE", "RECOVERY_PLAN", "RECOVERY_PROPOSAL"}
)
MODES = frozenset(
    {"AUDIT_ONLY", "OBSERVATION_ONLY", "SHADOW_ONLY", "REVIEW_ONLY", "PLAN_ONLY", "MEASUREMENT_ONLY"}
)
AUTHORITY_CLASSES = frozenset(
    {"OBSERVATIONAL_ONLY", "AUTHORITATIVE_WAL_DERIVED"}
)
OPERATIONS = frozenset({"ATTACH", "APPEND", "REPLAY", "TRACE_LINK"})
STORAGE_KINDS = frozenset({"ATTEMPT_LOCAL_RUN_META", "RECOVERY_APPEND_ONLY_LEDGER", "DECISION_CALL_LEDGER"})
STATUSES = frozenset({"RECORDED", "VALIDATED", "SKIPPED", "REPLAYED", "REJECTED"})
RELATIONSHIPS = frozenset({"OBSERVED_FROM", "MEASURED_AGAINST", "TRACE_LINKED_TO"})

_ENVELOPE_FIELDS = {
    "schema_version", "observation_kind", "producer", "producer_schema_version",
    "rule_version", "mode", "authority_class", "public_apply", "coordinate",
    "publication_binding", "source_lineage", "payload_ref", "parent_refs",
    "envelope_sha256",
}
_ENVELOPE_MATERIAL_FIELDS = _ENVELOPE_FIELDS - {"envelope_sha256"}
_COORDINATE_FIELDS = {"publication_scope_id", "input_index", "post_id", "attempt_run_id"}
_PUBLICATION_FIELDS = {
    "publication_scope_id", "input_index", "post_id", "decision_id",
    "commit_sha256", "input_sha256", "result_sha256", "stable_result_sha256",
    "public_projection_sha256", "contract_input_fingerprint",
}
_LINEAGE_FIELDS = {
    "source_kind", "source_snapshot_sha256", "source_result_sha256",
    "source_stable_result_sha256", "source_view_schema", "source_view_sha256",
    "extractor_rule_version", "parent_lineage_root_sha256",
}
_PAYLOAD_REF_FIELDS = {"legacy_schema", "legacy_receipt_sha256"}
_SIDECAR_FIELDS = {
    "schema_version", "operation", "storage_kind", "status", "public_apply",
    "envelope_sha256", "publication_binding", "storage_binding", "relationship",
    "receipt_sha256",
}
_SIDECAR_MATERIAL_FIELDS = _SIDECAR_FIELDS - {"receipt_sha256"}
_STORAGE_BINDING_FIELDS = {
    "ledger_schema", "scope_id", "sequence", "prev_frame_sha256",
    "frame_sha256", "readback_sha256",
}


class ObservationEnvelopeError(ValueError):
    """Raised when an observation envelope or sidecar receipt is invalid."""


ObservationEnvelopeValidationError = ObservationEnvelopeError


def _canonical(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _canonical(v) for k, v in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (tuple, list)):
        return [_canonical(v) for v in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise ObservationEnvelopeError("value is not JSON-canonicalizable")


def canonical_sha256(value: Any) -> str:
    """Return the canonical SHA-256 used by both receipt families."""
    encoded = json.dumps(_canonical(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _hash(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or _HEX64.fullmatch(value) is None:
        raise ObservationEnvelopeError(f"{field} must be lowercase sha256")
    return value


def _text(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ObservationEnvelopeError(f"{field} must be non-empty text")
    return value.strip()


def _enum(value: Any, allowed: frozenset[str], *, field: str) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise ObservationEnvelopeError(f"{field} enum is invalid")
    return value


def _positive_int(value: Any, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ObservationEnvelopeError(f"{field} must be a positive integer")
    return value


def _post_id(value: Any) -> int | str:
    if isinstance(value, bool) or value is None:
        raise ObservationEnvelopeError("coordinate.post_id is invalid")
    if isinstance(value, int):
        if value <= 0:
            raise ObservationEnvelopeError("coordinate.post_id is invalid")
        return value
    if not isinstance(value, str) or not value.strip():
        raise ObservationEnvelopeError("coordinate.post_id is invalid")
    return value.strip()


def _coordinate(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != _COORDINATE_FIELDS:
        raise ObservationEnvelopeError("coordinate fields mismatch")
    return {
        "publication_scope_id": _hash(value["publication_scope_id"], field="coordinate.publication_scope_id"),
        "input_index": _positive_int(value["input_index"], field="coordinate.input_index"),
        "post_id": _post_id(value["post_id"]),
        "attempt_run_id": _text(value["attempt_run_id"], field="coordinate.attempt_run_id"),
    }


def _publication_binding(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != _PUBLICATION_FIELDS:
        raise ObservationEnvelopeError("publication_binding fields mismatch")
    return {
        "publication_scope_id": _hash(value["publication_scope_id"], field="publication_binding.publication_scope_id"),
        "input_index": _positive_int(value["input_index"], field="publication_binding.input_index"),
        "post_id": _post_id(value["post_id"]),
        "decision_id": _hash(value["decision_id"], field="publication_binding.decision_id"),
        "commit_sha256": _hash(value["commit_sha256"], field="publication_binding.commit_sha256"),
        "input_sha256": _hash(value["input_sha256"], field="publication_binding.input_sha256"),
        "result_sha256": _hash(value["result_sha256"], field="publication_binding.result_sha256"),
        "public_projection_sha256": _hash(value["public_projection_sha256"], field="publication_binding.public_projection_sha256"),
        "stable_result_sha256": _hash(value["stable_result_sha256"], field="publication_binding.stable_result_sha256"),
        "contract_input_fingerprint": _hash(value["contract_input_fingerprint"], field="publication_binding.contract_input_fingerprint"),
    }


def _sorted_hashes(value: Any, *, field: str) -> list[str]:
    if not isinstance(value, list):
        raise ObservationEnvelopeError(f"{field} must be a list")
    values = [_hash(item, field=field) for item in value]
    if values != sorted(values) or len(values) != len(set(values)):
        raise ObservationEnvelopeError(f"{field} must be sorted and unique")
    return values


def _source_lineage(value: Any) -> dict[str, str]:
    if not isinstance(value, Mapping) or set(value) != _LINEAGE_FIELDS:
        raise ObservationEnvelopeError("source_lineage fields mismatch")
    return {
        "source_kind": _enum(value["source_kind"], frozenset({"AUTHORITATIVE_WAL_RESULT", "FRESH_RESULT", "ATTEMPT_LOCAL_COMPLETED_RESULT"}), field="source_lineage.source_kind"),
        "source_snapshot_sha256": _hash(value["source_snapshot_sha256"], field="source_lineage.source_snapshot_sha256"),
        "source_result_sha256": _hash(value["source_result_sha256"], field="source_lineage.source_result_sha256"),
        "source_stable_result_sha256": _hash(value["source_stable_result_sha256"], field="source_lineage.source_stable_result_sha256"),
        "source_view_schema": _text(value["source_view_schema"], field="source_lineage.source_view_schema"),
        "source_view_sha256": _hash(value["source_view_sha256"], field="source_lineage.source_view_sha256"),
        "extractor_rule_version": _text(value["extractor_rule_version"], field="source_lineage.extractor_rule_version"),
        "parent_lineage_root_sha256": _hash(value["parent_lineage_root_sha256"], field="source_lineage.parent_lineage_root_sha256"),
    }


def _payload_ref(value: Any) -> dict[str, str]:
    if not isinstance(value, Mapping) or set(value) != _PAYLOAD_REF_FIELDS:
        raise ObservationEnvelopeError("payload_ref fields mismatch")
    return {
        "legacy_schema": _text(value["legacy_schema"], field="payload_ref.legacy_schema"),
        "legacy_receipt_sha256": _hash(value["legacy_receipt_sha256"], field="payload_ref.legacy_receipt_sha256"),
    }


def _validate_envelope_material(value: Mapping[str, Any]) -> dict[str, Any]:
    if set(value) != _ENVELOPE_MATERIAL_FIELDS:
        raise ObservationEnvelopeError("observation envelope fields mismatch")
    if value.get("schema_version") != OBSERVATION_ENVELOPE_SCHEMA:
        raise ObservationEnvelopeError("observation envelope schema mismatch")
    if value.get("public_apply") is not False:
        raise ObservationEnvelopeError("observation envelope cannot apply publicly")
    coordinate = _coordinate(value["coordinate"])
    binding = _publication_binding(value["publication_binding"])
    if coordinate["publication_scope_id"] != binding["publication_scope_id"] or coordinate["input_index"] != binding["input_index"] or str(coordinate["post_id"]) != str(binding["post_id"]):
        raise ObservationEnvelopeError("coordinate/publication_binding mismatch")
    return {
        "schema_version": OBSERVATION_ENVELOPE_SCHEMA,
        "observation_kind": _enum(value["observation_kind"], OBSERVATION_KINDS, field="observation_kind"),
        "producer": _text(value["producer"], field="producer"),
        "producer_schema_version": _text(value["producer_schema_version"], field="producer_schema_version"),
        "rule_version": _text(value["rule_version"], field="rule_version"),
        "mode": _enum(value["mode"], MODES, field="mode"),
        "authority_class": _enum(value["authority_class"], AUTHORITY_CLASSES, field="authority_class"),
        "public_apply": False,
        "coordinate": coordinate,
        "publication_binding": binding,
        "source_lineage": _source_lineage(value["source_lineage"]),
        "payload_ref": _payload_ref(value["payload_ref"]),
        "parent_refs": _sorted_hashes(value["parent_refs"], field="parent_refs"),
    }


def build_observation_envelope(*, observation_kind: str, producer: str, producer_schema_version: str, rule_version: str, mode: str, authority_class: str, coordinate: Mapping[str, Any], publication_binding: Mapping[str, Any], source_lineage: Mapping[str, Any], payload_ref: Mapping[str, Any], parent_refs: list[str]) -> dict[str, Any]:
    """Build a self-hashed ``observation_envelope_v1`` record."""
    material = _validate_envelope_material({
        "schema_version": OBSERVATION_ENVELOPE_SCHEMA,
        "observation_kind": observation_kind,
        "producer": producer,
        "producer_schema_version": producer_schema_version,
        "rule_version": rule_version,
        "mode": mode,
        "authority_class": authority_class,
        "public_apply": False,
        "coordinate": coordinate,
        "publication_binding": publication_binding,
        "source_lineage": source_lineage,
        "payload_ref": payload_ref,
        "parent_refs": parent_refs,
    })
    return {**material, "envelope_sha256": canonical_sha256(material)}


def validate_observation_envelope(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ObservationEnvelopeError("observation envelope must be an object")
    if set(value) != _ENVELOPE_FIELDS:
        raise ObservationEnvelopeError("observation envelope fields mismatch")
    material = _validate_envelope_material(
        {key: item for key, item in value.items() if key != "envelope_sha256"}
    )
    envelope_hash = _hash(value.get("envelope_sha256"), field="envelope_sha256")
    if envelope_hash != canonical_sha256(material):
        raise ObservationEnvelopeError("observation envelope hash mismatch")
    return {**material, "envelope_sha256": envelope_hash}


def _storage_binding(value: Any) -> dict[str, str]:
    if not isinstance(value, Mapping) or set(value) != _STORAGE_BINDING_FIELDS:
        raise ObservationEnvelopeError("storage_binding fields mismatch")
    sequence = _positive_int(value["sequence"], field="storage_binding.sequence")
    previous = value["prev_frame_sha256"]
    if sequence == 1:
        if previous is not None:
            raise ObservationEnvelopeError("first storage frame must have null prev_frame_sha256")
    else:
        previous = _hash(previous, field="storage_binding.prev_frame_sha256")
    return {
        "ledger_schema": _text(value["ledger_schema"], field="storage_binding.ledger_schema"),
        "scope_id": _hash(value["scope_id"], field="storage_binding.scope_id"),
        "sequence": sequence,
        "prev_frame_sha256": previous,
        "frame_sha256": _hash(value["frame_sha256"], field="storage_binding.frame_sha256"),
        "readback_sha256": _hash(value["readback_sha256"], field="storage_binding.readback_sha256"),
    }


def _relationship(value: Any) -> str:
    return _enum(value, RELATIONSHIPS, field="relationship")


def build_sidecar_receipt(*, operation: str, storage_kind: str, status: str, envelope_sha256: str, publication_binding: Mapping[str, Any], storage_binding: Mapping[str, Any], relationship: str) -> dict[str, Any]:
    material = _validate_sidecar_material({
        "schema_version": SIDECAR_RECEIPT_SCHEMA,
        "operation": operation,
        "storage_kind": storage_kind,
        "status": status,
        "public_apply": False,
        "envelope_sha256": envelope_sha256,
        "publication_binding": publication_binding,
        "storage_binding": storage_binding,
        "relationship": relationship,
    })
    return {**material, "receipt_sha256": canonical_sha256(material)}


def _validate_sidecar_material(value: Mapping[str, Any]) -> dict[str, Any]:
    actual_fields = set(value)
    if actual_fields not in (_SIDECAR_MATERIAL_FIELDS, _SIDECAR_FIELDS):
        raise ObservationEnvelopeError("sidecar receipt fields mismatch")
    if value.get("schema_version") != SIDECAR_RECEIPT_SCHEMA:
        raise ObservationEnvelopeError("sidecar receipt schema mismatch")
    if value.get("public_apply") is not False:
        raise ObservationEnvelopeError("sidecar receipt cannot apply publicly")
    return {
        "schema_version": SIDECAR_RECEIPT_SCHEMA,
        "operation": _enum(value["operation"], OPERATIONS, field="operation"),
        "storage_kind": _enum(value["storage_kind"], STORAGE_KINDS, field="storage_kind"),
        "status": _enum(value["status"], STATUSES, field="status"),
        "public_apply": False,
        "envelope_sha256": _hash(value["envelope_sha256"], field="envelope_sha256"),
        "publication_binding": _publication_binding(value["publication_binding"]),
        "storage_binding": _storage_binding(value["storage_binding"]),
        "relationship": _relationship(value["relationship"]),
    }


def validate_sidecar_receipt(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != _SIDECAR_FIELDS:
        raise ObservationEnvelopeError("sidecar receipt fields mismatch")
    material = _validate_sidecar_material(value)
    receipt_hash = _hash(value.get("receipt_sha256"), field="receipt_sha256")
    if receipt_hash != canonical_sha256(material):
        raise ObservationEnvelopeError("sidecar receipt hash mismatch")
    return {**material, "receipt_sha256": receipt_hash}


def reference_legacy_receipt(
    legacy_receipt: Any,
    *,
    legacy_schema: str,
    canonical_receipt_hash: str | None = None,
) -> dict[str, str]:
    """Return a hash-only reference to a validated legacy receipt.

    The input is never modified.  Callers should run the legacy validator
    before invoking this helper; this function intentionally does not rewrite
    or embed legacy fields.
    """
    if not isinstance(legacy_schema, str) or not legacy_schema.strip():
        raise ObservationEnvelopeError("legacy_schema must be non-empty text")
    if not isinstance(legacy_receipt, Mapping):
        raise ObservationEnvelopeError("legacy receipt must be an object")
    digest = canonical_sha256(legacy_receipt)
    if canonical_receipt_hash is not None and canonical_receipt_hash != digest:
        raise ObservationEnvelopeError("legacy receipt canonical hash mismatch")
    return {"legacy_schema": legacy_schema.strip(), "legacy_receipt_sha256": digest}


def reference_legacy_receipt_hash(*, legacy_schema: str, canonical_receipt_hash: str) -> dict[str, str]:
    """Reference a hash supplied by a caller that already validated its receipt."""
    if not isinstance(legacy_schema, str) or not legacy_schema.strip():
        raise ObservationEnvelopeError("legacy_schema must be non-empty text")
    return {
        "legacy_schema": legacy_schema.strip(),
        "legacy_receipt_sha256": _hash(canonical_receipt_hash, field="canonical_receipt_hash"),
    }


# Explicit aliases make the additive contract discoverable without wiring it
# into expert_main or any existing writer.
build_observation_envelope_v1 = build_observation_envelope
validate_observation_envelope_v1 = validate_observation_envelope
build_sidecar_receipt_v1 = build_sidecar_receipt
validate_sidecar_receipt_v1 = validate_sidecar_receipt
build_legacy_receipt_reference = reference_legacy_receipt
