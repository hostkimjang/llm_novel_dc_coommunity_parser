"""Presented-only precommit for a future dual-blind neutral-review campaign.

The component rebuilds the exact forty upstream review units, binds an exact
set of caller-presented public-key pins, preassigns two primary reviewers and
one reserve adjudicator per input, and proves that a reviewer-facing task
inventory is a strict projection of an evaluator-private assignment map.  The
campaign-policy payload may be signed through the existing domain-separated
P-256 signature-math component.

This module deliberately does not provide a private signer or perform I/O.  A
successful receipt proves structural/raw-byte consistency only.  All pins,
principal commitments, group labels, times, revocation commitments, and the
signature itself are caller-presented.  It therefore does not prove external
provisioning, identity, independence, delivery-time blinding, freshness,
durable replay prevention, human judgment, metric eligibility, P0 exit, or
permission to change production state.
"""

from __future__ import annotations

import base64
import binascii
from datetime import datetime, timezone
import hashlib
import hmac
import json
import re
import unicodedata
from typing import Any, Mapping, Sequence

from . import p0_presented_neutral_review_accounting_v1_contract as review_accounting
from . import p0_presented_neutral_review_signature_math_v1_contract as signature_math


COMPONENT_VERSION = "presented-dual-blind-review-campaign-precommit-v1"
GUIDELINE_SCHEMA = "p0_presented_dual_blind_review_guideline_v1"
RESPONSE_SCHEMA_SCHEMA = "p0_presented_dual_blind_review_response_schema_v1"
ACTOR_ROW_SCHEMA = "p0_presented_dual_blind_review_actor_row_v1"
ASSIGNMENT_ROW_SCHEMA = "p0_presented_dual_blind_review_assignment_row_v1"
PRIVATE_MAP_ROW_SCHEMA = "p0_presented_dual_blind_review_private_map_row_v1"
BLIND_TASK_ROW_SCHEMA = "p0_presented_dual_blind_review_task_row_v1"
CAMPAIGN_PRECOMMIT_SCHEMA = "p0_presented_dual_blind_review_campaign_precommit_v1"
RECEIPT_SCHEMA = "p0_presented_dual_blind_review_campaign_precommit_receipt_v1"
COMPONENT_MANIFEST_SCHEMA = "p0_presented_dual_blind_review_campaign_manifest_v1"

RECORD_ORIGIN = "ACTUAL_SCHEMA_CONTRACT_EXAMPLE_ONLY"
OPERATIONAL_EFFECT = "NONE_SHADOW_ONLY"
GATE_STATUS = "NO_GO_PRESENTED_DUAL_BLIND_REVIEW_CAMPAIGN_PRECOMMIT_ONLY"
METRIC_STATUS = "NOT_ESTIMABLE_EXTERNAL_REVIEW_AUTHORITY_ABSENT"

EXPECTED_INPUT_COUNT = 40
PRIMARY_ASSIGNMENT_COUNT = 80
RESERVE_ASSIGNMENT_COUNT = 40
TOTAL_ASSIGNMENT_COUNT = 120
MIN_REVIEWERS = 3
MAX_REVIEWERS = review_accounting.MAX_REVIEWERS

PRIMARY_A = "PRIMARY_A"
PRIMARY_B = "PRIMARY_B"
DISAGREEMENT_ADJUDICATOR_RESERVE = "DISAGREEMENT_ADJUDICATOR_RESERVE"
ASSIGNMENT_SLOTS = (PRIMARY_A, PRIMARY_B, DISAGREEMENT_ADJUDICATOR_RESERVE)
REVIEW_GUIDELINE_INSTRUCTIONS = (
    "Review only the supplied payload and the fixed response schema.",
    "Enumerate the complete set of neutral surface-relation spans in the full payload; an empty set is valid only when no such span exists.",
    "Treat every surface form, including 아생갤, as uninterpreted payload text and do not infer a work, alias, sense, or NIL target.",
    "Do not use or request parser output, registry identifiers, assignment slots, reviewer identities, peer task identifiers, or peer results.",
    "Return no work, alias, sense, NIL, publication, metric, production, or operational decision.",
)

_MAX_OBJECT_BYTES = 1024 * 1024
_MAX_GUIDELINE_BYTES = 128 * 1024
_MAX_PIN_LINE_BYTES = 16 * 1024
_MAX_PIN_INVENTORY_BYTES = 512 * 1024
_MAX_ROSTER_BYTES = 512 * 1024
_MAX_REVIEW_UNIT_BYTES = review_accounting.MAX_JSONL_BYTES
_MAX_UPSTREAM_BRIDGE_BYTES = 16 * 1024 * 1024
_MAX_UPSTREAM_RESULT_BYTES = 32 * 1024 * 1024
_MAX_UPSTREAM_UNREVIEWED_BYTES = 32 * 1024 * 1024
_MAX_ASSIGNMENT_BYTES = 4 * 1024 * 1024
_MAX_PRIVATE_MAP_BYTES = 4 * 1024 * 1024
_MAX_BLIND_TASK_BYTES = 4 * 1024 * 1024
_MAX_JSONL_LINE_BYTES = 1024 * 1024
_MAX_INSTRUCTIONS = 64
_MAX_INSTRUCTION_CHARS = 2048
_MAX_TEXT_CHARS = 4096

_SHA_RE = re.compile(r"^[0-9a-f]{64}$")
_OPAQUE_ID_RE = re.compile(r"^[0-9a-f]{64}$")
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,255}$")
_TIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_P256_PRIME = int("ffffffff00000001000000000000000000000000ffffffffffffffffffffffff", 16)
_P256_B = int("5ac635d8aa3a93e7b3ebbd55769886bc651d06b0cc53b0f63bce3c3e27d2604b", 16)
_P256_SPKI_PREFIX = bytes.fromhex(
    "3059301306072a8648ce3d020106082a8648ce3d03010703420004"
)

_PIN_FIELDS = frozenset(
    {
        "schema_version", "record_origin", "component_version", "signature_kind",
        "trust_domain", "project_id", "environment", "purpose", "key_role",
        "key_id", "key_epoch", "algorithm", "curve", "cng_provider",
        "coordinate_encoding", "fingerprint_encoding", "public_key_x_base64",
        "public_key_y_base64", "public_key_fingerprint_sha256",
        "signer_principal_commitment_sha256", "authority_anchor_sha256",
        "allowed_signature_domains", "presented_revocation_snapshot_raw_sha256",
        "artifact_sha256",
    }
)
_GUIDELINE_FIELDS = frozenset(
    {
        "schema_version", "record_origin", "component_version", "campaign_id",
        "guideline_id", "guideline_version", "review_scope", "reviewer_visibility",
        "parser_projection_release_stage", "semantic_target_decision_policy",
        "instructions", "presented_policy_only", "action_applied",
        "operational_effect", "artifact_sha256",
    }
)
_RESPONSE_SCHEMA_FIELDS = frozenset(
    {
        "schema_version", "record_origin", "component_version", "campaign_id",
        "response_schema_id", "terminal_statuses", "required_response_fields",
        "full_payload_gold_set_requirement", "primary_result_mutability_policy",
        "canonical_gold_set_comparison_profile", "terminal_field_semantics",
        "presented_policy_only", "action_applied", "operational_effect",
        "artifact_sha256",
    }
)
_ACTOR_FIELDS = frozenset(
    {
        "schema_version", "actor_sequence", "actor_kind", "actor_id",
        "declared_independence_group_id", "pin_sequence", "pin_raw_bytes",
        "pin_raw_sha256", "pin_artifact_sha256", "signature_kind", "key_role",
        "purpose", "domain", "key_id", "key_epoch",
        "public_key_fingerprint_sha256", "signer_principal_commitment_sha256",
        "actor_row_sha256",
    }
)
_ASSIGNMENT_FIELDS = frozenset(
    {
        "schema_version", "assignment_sequence", "campaign_id", "run_id",
        "input_sequence", "assignment_slot", "reviewer_id",
        "reviewer_pin_raw_sha256", "reviewer_key_id", "reviewer_key_epoch",
        "reviewer_public_key_fingerprint_sha256",
        "reviewer_principal_commitment_sha256",
        "reviewer_independence_group_id", "opaque_task_id",
        "assignment_row_sha256",
    }
)
_PRIVATE_MAP_FIELDS = frozenset(
    {
        "schema_version", "map_sequence", "campaign_id", "run_id",
        "input_sequence", "assignment_slot", "opaque_task_id", "reviewer_id",
        "reviewer_pin_raw_sha256", "reviewer_key_id", "reviewer_key_epoch",
        "reviewer_public_key_fingerprint_sha256",
        "reviewer_principal_commitment_sha256",
        "reviewer_independence_group_id", "assignment_row_sha256",
        "input_review_unit_sha256", "frame_candidate_id", "registry_record_id",
        "selected_input_sha256", "bridge_row_sha256", "payload_base64",
        "payload_bytes", "payload_sha256", "parser_result_row_sha256",
        "parser_terminal_disposition", "full_payload_missed_span_unit_sha256",
        "emitted_observation_subjects_sha256", "emitted_observation_count",
        "private_map_row_sha256",
    }
)
_BLIND_TASK_FIELDS = frozenset(
    {
        "schema_version", "task_sequence", "campaign_id", "run_id",
        "opaque_task_id", "payload_base64", "payload_bytes", "payload_sha256",
        "review_guideline_raw_sha256", "review_guideline_artifact_sha256",
        "response_schema_raw_sha256", "response_schema_artifact_sha256",
        "blind_task_row_sha256",
    }
)
_PRECOMMIT_FIELDS = frozenset(
    {
        "schema_version", "record_origin", "component_version", "campaign_id",
        "run_id", "trust_domain", "project_id", "environment",
        "component_manifest_sha256",
        "upstream_review_component_manifest_sha256",
        "upstream_sampling_plan_raw_sha256", "upstream_bridge_inventory_raw_sha256",
        "upstream_batch_precommit_raw_sha256", "upstream_parser_results_raw_sha256",
        "upstream_batch_receipt_raw_sha256",
        "upstream_unreviewed_inventory_raw_sha256",
        "upstream_review_unit_inventory_raw_sha256",
        "upstream_review_unit_inventory_sha256",
        "review_guideline_raw_sha256", "review_guideline_artifact_sha256",
        "response_schema_raw_sha256", "response_schema_artifact_sha256",
        "key_pin_inventory_raw_sha256", "key_pin_count",
        "actor_roster_raw_sha256", "actor_count", "reviewer_count",
        "assignment_inventory_raw_sha256", "assignment_inventory_sha256",
        "evaluator_private_map_raw_sha256", "evaluator_private_map_sha256",
        "reviewer_facing_task_inventory_raw_sha256",
        "reviewer_facing_task_inventory_sha256", "expected_input_count",
        "primary_assignment_count", "reserve_assignment_count",
        "total_assignment_count", "assignment_slot_order", "review_protocol",
        "selected_input_itt_denominator",
        "planned_primary_review_opportunity_denominator",
        "primary_pair_input_denominator",
        "maximum_reserve_adjudication_opportunity_denominator",
        "planned_final_judged_input_denominator",
        "required_adjudication_denominator",
        "required_adjudication_denominator_derivation",
        "prior_presented_result_import_policy", "presented_assignment_sealed_at",
        "presented_campaign_precommitted_at", "presented_policy_only",
        "action_applied", "operational_effect", "artifact_sha256",
    }
)
_SIGNATURE_SUBJECT_FIELDS = frozenset(
    {
        "schema_version", "record_origin", "component_version", "signature_kind",
        "domain", "trust_domain", "project_id", "environment", "purpose",
        "key_role", "campaign_id", "run_id", "subject_id", "presented_issued_at",
        "nonce_commitment_sha256", "payload_schema", "payload_bytes",
        "payload_raw_sha256", "payload_artifact_sha256",
        "predecessor_subject_raw_sha256", "caller_presented_subject_only",
        "external_authority_claimed", "actual_human_review_claimed",
        "semantic_promotion_claimed", "action_applied", "operational_effect",
        "artifact_sha256",
    }
)

_FALSE_AUTHORITY_FIELDS = (
    "external_key_provisioning_verified",
    "external_authority_anchor_verified",
    "reviewer_identity_verified",
    "reviewer_independence_factuality_verified",
    "reviewer_blinding_verified",
    "reviewer_dispatch_isolation_verified",
    "mapping_confidentiality_verified",
    "opaque_identifier_unpredictability_verified",
    "trusted_time_verified",
    "revocation_state_verified",
    "durable_replay_prevention_verified",
    "lease_signature_verified",
    "final_attestation_signature_verified",
    "human_judgment_factuality_verified",
    "gold_span_semantic_factuality_verified",
    "primary_result_inventory_verified",
    "all_80_primary_terminals_verified",
    "all_40_pairs_complete_verified",
    "disagreement_inventory_verified",
    "required_adjudication_complete_verified",
    "final_40_judged_verified",
    "actual_human_review_verified",
    "actual_source_evidence_verified",
    "metric_eligibility_verified",
    "descriptive_quality_metrics_allowed",
    "inferential_metrics_allowed",
    "complete_case_metrics_allowed",
    "semantic_metrics_allowed",
    "actual_authority_granted",
    "p0_phase_exit",
    "production_approval",
    "full_scan_approval",
)


class P0PresentedDualBlindReviewCampaignPrecommitV1Error(ValueError):
    """The presented campaign precommit failed closed."""


def canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, RecursionError) as exc:
        raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
            "value is not canonical JSON data"
        ) from exc


def canonical_file_bytes(value: Any) -> bytes:
    return canonical_bytes(value) + b"\n"


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def raw_sha256(raw: bytes) -> str:
    if type(raw) is not bytes:
        raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
            "raw value must be bytes"
        )
    return hashlib.sha256(raw).hexdigest()


def _bounded_bytes(value: Any, label: str, maximum: int) -> bytes:
    if type(value) is not bytes or not value or len(value) > maximum:
        raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
            f"{label} byte bound is invalid"
        )
    return value


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    row: dict[str, Any] = {}
    for key, value in pairs:
        if key in row:
            raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
                "duplicate JSON key is forbidden"
            )
        row[key] = value
    return row


def _constant(token: str) -> None:
    raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
        f"non-finite JSON constant is forbidden: {token}"
    )


def _parse_line(raw: bytes, label: str, *, maximum: int = _MAX_OBJECT_BYTES) -> dict[str, Any]:
    if (
        type(raw) is not bytes or not raw or len(raw) > maximum
        or raw.startswith(b"\xef\xbb\xbf") or b"\r" in raw
        or not raw.endswith(b"\n") or raw.count(b"\n") != 1
    ):
        raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
            f"{label} framing is invalid"
        )
    try:
        value = json.loads(
            raw.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_constant
        )
    except P0PresentedDualBlindReviewCampaignPrecommitV1Error:
        raise
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
            f"{label} must be strict UTF-8 JSON"
        ) from exc
    if type(value) is not dict or raw != canonical_file_bytes(value):
        raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
            f"{label} must be one canonical object plus one LF"
        )
    return value


def _parse_jsonl(
    raw: bytes,
    label: str,
    *,
    maximum: int,
    line_maximum: int = _MAX_JSONL_LINE_BYTES,
) -> tuple[list[dict[str, Any]], list[bytes]]:
    if (
        type(raw) is not bytes or not raw or len(raw) > maximum
        or raw.startswith(b"\xef\xbb\xbf") or b"\r" in raw
        or not raw.endswith(b"\n")
    ):
        raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
            f"{label} framing is invalid"
        )
    lines = raw.splitlines(keepends=True)
    if not lines or any(line == b"\n" or len(line) > line_maximum for line in lines):
        raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
            f"{label} line inventory is invalid"
        )
    rows = [
        _parse_line(line, f"{label} row {index}", maximum=line_maximum)
        for index, line in enumerate(lines, start=1)
    ]
    if b"".join(canonical_file_bytes(row) for row in rows) != raw:
        raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
            f"{label} is not canonical JSONL"
        )
    return rows, lines


def _strict(value: Any, fields: frozenset[str], label: str) -> dict[str, Any]:
    if type(value) is not dict:
        raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
            f"{label} must be an object"
        )
    keys = frozenset(value)
    if keys != fields:
        raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
            f"{label} field inventory mismatch"
        )
    return dict(value)


def _sha(value: Any, label: str) -> str:
    if type(value) is not str or _SHA_RE.fullmatch(value) is None:
        raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
            f"{label} must be lowercase SHA-256"
        )
    return value


def _identifier(value: Any, label: str) -> str:
    if type(value) is not str or _ID_RE.fullmatch(value) is None:
        raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
            f"{label} is invalid"
        )
    return value


def _opaque_id(value: Any, label: str) -> str:
    if type(value) is not str or _OPAQUE_ID_RE.fullmatch(value) is None:
        raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
            f"{label} must be a 256-bit lowercase hexadecimal identifier"
        )
    return value


def _integer(value: Any, label: str, minimum: int = 0, maximum: int | None = None) -> int:
    if (
        isinstance(value, bool) or not isinstance(value, int) or value < minimum
        or (maximum is not None and value > maximum)
    ):
        raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
            f"{label} is outside the integer contract"
        )
    return value


def _text(value: Any, label: str, *, maximum: int = _MAX_TEXT_CHARS) -> str:
    if (
        type(value) is not str or not value or len(value) > maximum
        or "\r" in value or "\x00" in value
        or unicodedata.normalize("NFC", value) != value
    ):
        raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
            f"{label} is invalid"
        )
    return value


def _time(value: Any, label: str) -> datetime:
    if type(value) is not str or _TIME_RE.fullmatch(value) is None:
        raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
            f"{label} must be second-precision UTC"
        )
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError as exc:
        raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
            f"{label} is not a real UTC timestamp"
        ) from exc
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
        raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
            f"{label} is not canonical UTC"
        )
    return parsed


def _self_hash(row: Mapping[str, Any], field: str, label: str, *, domain: str | None = None) -> str:
    stored = _sha(row.get(field), f"{label}.{field}")
    material = {key: value for key, value in row.items() if key != field}
    expected = canonical_sha256(
        material
        if domain is None
        else {"self_hash_domain": domain, "self_hash_material": material}
    )
    if not hmac.compare_digest(stored, expected):
        raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
            f"{label} self-hash mismatch"
        )
    return stored


def _with_self_hash(material: Mapping[str, Any], field: str = "artifact_sha256", *, domain: str | None = None) -> dict[str, Any]:
    body = dict(material)
    digest_material: Mapping[str, Any] = (
        body
        if domain is None
        else {"self_hash_domain": domain, "self_hash_material": body}
    )
    return {**body, field: canonical_sha256(digest_material)}


def _decode_base64(value: Any, *, length: int | None, label: str) -> bytes:
    if type(value) is not str or not value or any(char.isspace() for char in value):
        raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
            f"{label} must be canonical base64"
        )
    try:
        decoded = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
            f"{label} must be canonical base64"
        ) from exc
    if (
        (length is not None and len(decoded) != length)
        or base64.b64encode(decoded).decode("ascii") != value
    ):
        raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
            f"{label} canonical length mismatch"
        )
    return decoded


def _validate_p256_point(x: bytes, y: bytes) -> None:
    xi = int.from_bytes(x, "big")
    yi = int.from_bytes(y, "big")
    if (
        xi >= _P256_PRIME or yi >= _P256_PRIME
        or pow(yi, 2, _P256_PRIME)
        != (pow(xi, 3, _P256_PRIME) - 3 * xi + _P256_B) % _P256_PRIME
    ):
        raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
            "presented public key is not a P-256 affine point"
        )


def _validate_pin(row: Any, raw: bytes, index: int) -> dict[str, Any]:
    pin = _strict(row, _PIN_FIELDS, f"pin {index}")
    kind = pin["signature_kind"]
    if kind not in signature_math.SIGNATURE_PROFILE:
        raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
            "pin signature kind is invalid"
        )
    role, purpose, domain = signature_math.SIGNATURE_PROFILE[kind]
    if (
        pin["schema_version"] != signature_math.PUBLIC_KEY_PIN_SCHEMA
        or pin["record_origin"] != signature_math.PRESENTED_PIN_ORIGIN
        or pin["component_version"] != signature_math.COMPONENT_VERSION
        or pin["key_role"] != role or pin["purpose"] != purpose
        or pin["allowed_signature_domains"] != [domain]
        or pin["algorithm"] != signature_math.ALGORITHM
        or pin["curve"] != signature_math.CURVE
        or pin["cng_provider"] != signature_math.CNG_PROVIDER
        or pin["coordinate_encoding"] != signature_math.COORDINATE_ENCODING
        or pin["fingerprint_encoding"] != signature_math.FINGERPRINT_ENCODING
    ):
        raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
            "pin signature profile mismatch"
        )
    for field in ("trust_domain", "project_id", "environment", "key_id"):
        _identifier(pin[field], f"pin.{field}")
    _integer(pin["key_epoch"], "pin.key_epoch", 1)
    for field in (
        "public_key_fingerprint_sha256", "signer_principal_commitment_sha256",
        "authority_anchor_sha256", "presented_revocation_snapshot_raw_sha256",
    ):
        _sha(pin[field], f"pin.{field}")
    x = _decode_base64(pin["public_key_x_base64"], length=32, label="pin.x")
    y = _decode_base64(pin["public_key_y_base64"], length=32, label="pin.y")
    _validate_p256_point(x, y)
    fingerprint = hashlib.sha256(_P256_SPKI_PREFIX + x + y).hexdigest()
    if not hmac.compare_digest(fingerprint, pin["public_key_fingerprint_sha256"]):
        raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
            "pin RFC 5480 fingerprint mismatch"
        )
    _self_hash(pin, "artifact_sha256", f"pin {index}")
    if raw != canonical_file_bytes(pin):
        raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
            "pin exact raw line mismatch"
        )
    return pin


def build_review_guideline_bytes(
    *,
    campaign_id: str,
    guideline_id: str,
    guideline_version: int,
) -> bytes:
    """Build the exact fixed, no-effect review guideline."""

    _identifier(campaign_id, "campaign_id")
    _identifier(guideline_id, "guideline_id")
    _integer(guideline_version, "guideline_version", 1)
    material = {
        "schema_version": GUIDELINE_SCHEMA,
        "record_origin": RECORD_ORIGIN,
        "component_version": COMPONENT_VERSION,
        "campaign_id": campaign_id,
        "guideline_id": guideline_id,
        "guideline_version": guideline_version,
        "review_scope": "FULL_PAYLOAD_NEUTRAL_RELATION_EXTRACTION_ONLY",
        "reviewer_visibility": "PAYLOAD_GUIDELINE_AND_RESPONSE_SCHEMA_ONLY",
        "parser_projection_release_stage": "AFTER_BOTH_PRIMARY_RESULTS_FROZEN",
        "semantic_target_decision_policy": "FORBIDDEN",
        "instructions": list(REVIEW_GUIDELINE_INSTRUCTIONS),
        "presented_policy_only": True,
        "action_applied": False,
        "operational_effect": OPERATIONAL_EFFECT,
    }
    raw = canonical_file_bytes(_with_self_hash(material))
    if len(raw) > _MAX_GUIDELINE_BYTES:
        raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
            "guideline byte bound exceeded"
        )
    _validate_guideline(raw)
    return raw


def _validate_guideline(raw: bytes) -> dict[str, Any]:
    row = _strict(
        _parse_line(raw, "review guideline", maximum=_MAX_GUIDELINE_BYTES),
        _GUIDELINE_FIELDS,
        "review guideline",
    )
    instructions = row["instructions"]
    if type(instructions) is not list or not 1 <= len(instructions) <= _MAX_INSTRUCTIONS:
        raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
            "guideline instruction inventory is invalid"
        )
    for index, item in enumerate(instructions, start=1):
        _text(item, f"guideline instruction {index}", maximum=_MAX_INSTRUCTION_CHARS)
    if (
        row["schema_version"] != GUIDELINE_SCHEMA
        or row["record_origin"] != RECORD_ORIGIN
        or row["component_version"] != COMPONENT_VERSION
        or row["review_scope"] != "FULL_PAYLOAD_NEUTRAL_RELATION_EXTRACTION_ONLY"
        or row["reviewer_visibility"] != "PAYLOAD_GUIDELINE_AND_RESPONSE_SCHEMA_ONLY"
        or row["parser_projection_release_stage"] != "AFTER_BOTH_PRIMARY_RESULTS_FROZEN"
        or row["semantic_target_decision_policy"] != "FORBIDDEN"
        or instructions != list(REVIEW_GUIDELINE_INSTRUCTIONS)
        or row["presented_policy_only"] is not True
        or row["action_applied"] is not False
        or row["operational_effect"] != OPERATIONAL_EFFECT
    ):
        raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
            "guideline policy mismatch"
        )
    _identifier(row["campaign_id"], "guideline.campaign_id")
    _identifier(row["guideline_id"], "guideline.guideline_id")
    _integer(row["guideline_version"], "guideline.guideline_version", 1)
    _self_hash(row, "artifact_sha256", "review guideline")
    return row


def _canonical_gold_set_comparison_profile() -> dict[str, Any]:
    return {
        "comparison_eligibility": "BOTH_AUTHORITY_QUALIFIED_PRIMARIES_JUDGED_AND_FROZEN",
        "identity_tuple_fields": [
            "payload_sha256", "line_number", "character_span_start",
            "character_span_end", "utf8_byte_span_start", "utf8_byte_span_end",
            "evidence_text", "surface_text", "presented_definition_text",
            "relation_kind",
        ],
        "ordering": "LEXICOGRAPHIC_IDENTITY_TUPLE_ORDER_INSENSITIVE_INPUT",
        "duplicate_policy": "REJECT",
        "empty_set_policy": "VALID_JUDGED_COMPLETE_SET",
        "equality": "CANONICAL_JSON_ARRAY_BYTE_EQUALITY_AFTER_VALIDATION_AND_SORT",
        "parser_observation_input_policy": "FORBIDDEN",
    }


def _terminal_field_semantics() -> dict[str, Any]:
    return {
        "JUDGED": {
            "presented_gold_spans": "COMPLETE_LIST_EMPTY_ALLOWED",
            "terminal_reason_code": "NULL",
            "reviewed_at": "REQUIRED_SECOND_PRECISION_UTC",
            "quality_arithmetic": "DEFER_UNTIL_FINAL_40_OF_40",
        },
        "UNAVAILABLE": {
            "presented_gold_spans": "NULL",
            "terminal_reason_code": "REQUIRED_NONEMPTY",
            "reviewed_at": "REQUIRED_SECOND_PRECISION_UTC",
            "quality_arithmetic": "NULL",
        },
        "UNJUDGED": {
            "presented_gold_spans": "NULL",
            "terminal_reason_code": "REQUIRED_NONEMPTY",
            "reviewed_at": "NULL",
            "quality_arithmetic": "NULL",
        },
    }


def _result_free_review_protocol() -> dict[str, Any]:
    return {
        "primary_results_per_input": 2,
        "reserve_adjudicators_per_input": 1,
        "primary_freeze_before_parser_comparison": True,
        "parser_projection_release_stage": "AFTER_BOTH_PRIMARY_RESULTS_FROZEN",
        "reserve_activation_rule": "BOTH_AUTHORITY_QUALIFIED_PRIMARIES_JUDGED_AND_CANONICAL_FULL_GOLD_SETS_DIFFER",
        "primary_nonjudged_substitution_policy": "FORBIDDEN",
        "pair_incomplete_disposition": "INCOMPLETE_NO_FINAL_JUDGED_RESULT_PRIMARY_TERMINALS_RETAINED",
        "whole_inventory_reviewer_release_policy": "FORBIDDEN_DISPATCH_ONE_TASK_AT_A_TIME",
        "raw_primary_result_retention": "REQUIRED",
        "lease_before_dispatch_requirement": "REQUIRED",
        "final_attestation_before_credit_requirement": "REQUIRED",
    }


def _response_schema_material(*, campaign_id: str, response_schema_id: str) -> dict[str, Any]:
    return {
        "schema_version": RESPONSE_SCHEMA_SCHEMA,
        "record_origin": RECORD_ORIGIN,
        "component_version": COMPONENT_VERSION,
        "campaign_id": campaign_id,
        "response_schema_id": response_schema_id,
        "terminal_statuses": ["JUDGED", "UNAVAILABLE", "UNJUDGED"],
        "required_response_fields": [
            "opaque_task_id", "annotation_status", "terminal_reason_code",
            "reviewed_at", "presented_gold_spans", "reviewer_note_commitment_sha256",
        ],
        "full_payload_gold_set_requirement": "COMPLETE_SET_OR_NONJUDGED_TERMINAL",
        "primary_result_mutability_policy": "IMMUTABLE_AFTER_FIRST_VALID_SIGNATURE",
        "canonical_gold_set_comparison_profile": _canonical_gold_set_comparison_profile(),
        "terminal_field_semantics": _terminal_field_semantics(),
        "presented_policy_only": True,
        "action_applied": False,
        "operational_effect": OPERATIONAL_EFFECT,
    }


def build_review_response_schema_bytes(*, campaign_id: str, response_schema_id: str) -> bytes:
    """Build the fixed primary-review response schema commitment."""

    _identifier(campaign_id, "campaign_id")
    _identifier(response_schema_id, "response_schema_id")
    material = _response_schema_material(
        campaign_id=campaign_id,
        response_schema_id=response_schema_id,
    )
    raw = canonical_file_bytes(_with_self_hash(material))
    _validate_response_schema(raw)
    return raw


def _validate_response_schema(raw: bytes) -> dict[str, Any]:
    row = _strict(_parse_line(raw, "response schema"), _RESPONSE_SCHEMA_FIELDS, "response schema")
    _identifier(row["campaign_id"], "response.campaign_id")
    _identifier(row["response_schema_id"], "response.response_schema_id")
    fixed = _response_schema_material(
        campaign_id=row["campaign_id"],
        response_schema_id=row["response_schema_id"],
    )
    expected_raw = canonical_file_bytes(_with_self_hash(fixed))
    if raw != expected_raw:
        raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
            "response schema exact fixed contract mismatch"
        )
    return row


def build_key_pin_inventory_and_actor_roster_bytes(
    *,
    campaign_policy_pin_raw: bytes,
    campaign_policy_independence_group_id: str,
    review_lease_pin_raw: bytes,
    review_lease_independence_group_id: str,
    final_attestation_pin_raw: bytes,
    final_attestation_independence_group_id: str,
    reviewers: Sequence[Mapping[str, Any]],
) -> tuple[bytes, bytes]:
    """Build exact pin JSONL and its declared actor projection."""

    if type(reviewers) not in (list, tuple) or not MIN_REVIEWERS <= len(reviewers) <= MAX_REVIEWERS:
        raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
            "reviewer count is outside the campaign contract"
        )
    singleton = (
        ("CAMPAIGN_POLICY_SIGNER", campaign_policy_independence_group_id, campaign_policy_pin_raw, signature_math.CAMPAIGN_POLICY_PREAUTHORIZATION),
        ("REVIEW_LEASE_SIGNER", review_lease_independence_group_id, review_lease_pin_raw, signature_math.REVIEW_LEASE),
        ("FINAL_REVIEW_ATTESTER", final_attestation_independence_group_id, final_attestation_pin_raw, signature_math.FINAL_REVIEW_ATTESTATION),
    )
    raw_pins: list[bytes] = []
    actor_inputs: list[tuple[str, str, str, bytes, str]] = []
    for actor_id, group, raw, kind in singleton:
        actor_inputs.append(("SINGLETON_ROLE", actor_id, _identifier(group, "singleton independence group"), raw, kind))
    for index, item in enumerate(reviewers, start=1):
        spec = _strict(
            item,
            frozenset({"reviewer_id", "identity_commitment_sha256", "independence_group_id", "public_key_pin_raw"}),
            f"reviewer input {index}",
        )
        reviewer_id = _identifier(spec["reviewer_id"], "reviewer_id")
        commitment = _sha(spec["identity_commitment_sha256"], "reviewer identity commitment")
        group = _identifier(spec["independence_group_id"], "reviewer independence group")
        pin_raw = spec["public_key_pin_raw"]
        if type(pin_raw) is not bytes:
            raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
                "reviewer pin raw must be bytes"
            )
        actor_inputs.append(("HUMAN_REVIEWER", reviewer_id, group, pin_raw, signature_math.HUMAN_REVIEW_RESULT))
        # Checked against the pin after exact parsing below.
        actor_inputs[-1] = (*actor_inputs[-1], commitment)  # type: ignore[assignment]

    actors: list[dict[str, Any]] = []
    pin_rows: list[dict[str, Any]] = []
    singleton_groups = {item[1] for item in singleton}
    if len(singleton_groups) != 3:
        raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
            "singleton independence groups must be distinct"
        )
    actor_ids: set[str] = set()
    key_ids: set[str] = set()
    fingerprints: set[str] = set()
    principals: set[str] = set()
    pin_hashes: set[str] = set()
    base_scope: tuple[str, str, str] | None = None
    revocation_sha: str | None = None
    authority_anchor_sha: str | None = None
    for index, actor_input in enumerate(actor_inputs, start=1):
        actor_kind, actor_id, group, pin_raw, expected_kind, *commitment_tail = actor_input
        pin = _validate_pin(
            _parse_line(pin_raw, f"pin {index}", maximum=_MAX_PIN_LINE_BYTES),
            pin_raw,
            index,
        )
        if pin["signature_kind"] != expected_kind:
            raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
                "actor pin kind/order mismatch"
            )
        if commitment_tail and pin["signer_principal_commitment_sha256"] != commitment_tail[0]:
            raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
                "reviewer identity commitment does not match exact pin"
            )
        if actor_id in actor_ids:
            raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
                "actor IDs must be globally distinct"
            )
        actor_ids.add(actor_id)
        if actor_kind == "HUMAN_REVIEWER":
            if group in singleton_groups:
                raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
                    "reviewer identity/group conflicts with campaign roles"
                )
        scope = (pin["trust_domain"], pin["project_id"], pin["environment"])
        if base_scope is None:
            base_scope = scope
            revocation_sha = pin["presented_revocation_snapshot_raw_sha256"]
            authority_anchor_sha = pin["authority_anchor_sha256"]
        elif (
            scope != base_scope
            or pin["presented_revocation_snapshot_raw_sha256"] != revocation_sha
            or pin["authority_anchor_sha256"] != authority_anchor_sha
        ):
            raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
                "pin campaign scope, authority anchor, or revocation commitment mismatch"
            )
        unique_values = (
            (key_ids, pin["key_id"]),
            (fingerprints, pin["public_key_fingerprint_sha256"]),
            (principals, pin["signer_principal_commitment_sha256"]),
            (pin_hashes, raw_sha256(pin_raw)),
        )
        if any(value in seen for seen, value in unique_values):
            raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
                "key ID/fingerprint/principal/raw pin must be globally distinct"
            )
        for seen, value in unique_values:
            seen.add(value)
        raw_pins.append(pin_raw)
        pin_rows.append(pin)
        role, purpose, domain = signature_math.SIGNATURE_PROFILE[expected_kind]
        material = {
            "schema_version": ACTOR_ROW_SCHEMA,
            "actor_sequence": index,
            "actor_kind": actor_kind,
            "actor_id": actor_id,
            "declared_independence_group_id": group,
            "pin_sequence": index,
            "pin_raw_bytes": len(pin_raw),
            "pin_raw_sha256": raw_sha256(pin_raw),
            "pin_artifact_sha256": pin["artifact_sha256"],
            "signature_kind": expected_kind,
            "key_role": role,
            "purpose": purpose,
            "domain": domain,
            "key_id": pin["key_id"],
            "key_epoch": pin["key_epoch"],
            "public_key_fingerprint_sha256": pin["public_key_fingerprint_sha256"],
            "signer_principal_commitment_sha256": pin["signer_principal_commitment_sha256"],
        }
        actors.append(_with_self_hash(material, "actor_row_sha256", domain="P0_DUAL_BLIND_REVIEW_ACTOR_ROW_V1"))
    pin_inventory_raw = b"".join(raw_pins)
    roster_raw = b"".join(canonical_file_bytes(row) for row in actors)
    if len(pin_inventory_raw) > _MAX_PIN_INVENTORY_BYTES or len(roster_raw) > _MAX_ROSTER_BYTES:
        raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
            "pin or roster byte bound exceeded"
        )
    _validate_pin_and_roster(pin_inventory_raw, roster_raw)
    return pin_inventory_raw, roster_raw


def _validate_pin_and_roster(pin_inventory_raw: bytes, roster_raw: bytes) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    pins, pin_lines = _parse_jsonl(
        pin_inventory_raw, "key pin inventory", maximum=_MAX_PIN_INVENTORY_BYTES,
        line_maximum=_MAX_PIN_LINE_BYTES,
    )
    actors, _ = _parse_jsonl(roster_raw, "actor roster", maximum=_MAX_ROSTER_BYTES)
    if not MIN_REVIEWERS + 3 <= len(pins) == len(actors) <= MAX_REVIEWERS + 3:
        raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
            "pin/actor count mismatch"
        )
    expected_kinds = [
        signature_math.CAMPAIGN_POLICY_PREAUTHORIZATION,
        signature_math.REVIEW_LEASE,
        signature_math.FINAL_REVIEW_ATTESTATION,
        *([signature_math.HUMAN_REVIEW_RESULT] * (len(pins) - 3)),
    ]
    key_ids: set[str] = set()
    fingerprints: set[str] = set()
    principals: set[str] = set()
    pin_hashes: set[str] = set()
    actor_ids: set[str] = set()
    singleton_groups: set[str] = set()
    base_scope: tuple[str, str, str] | None = None
    revocation: str | None = None
    authority_anchor: str | None = None
    validated_pins: list[dict[str, Any]] = []
    validated_actors: list[dict[str, Any]] = []
    for index, (pin_value, pin_raw, actor_value, expected_kind) in enumerate(
        zip(pins, pin_lines, actors, expected_kinds, strict=True), start=1
    ):
        pin = _validate_pin(pin_value, pin_raw, index)
        actor = _strict(actor_value, _ACTOR_FIELDS, f"actor {index}")
        expected_actor_kind = "SINGLETON_ROLE" if index <= 3 else "HUMAN_REVIEWER"
        expected_actor_id = (
            ("CAMPAIGN_POLICY_SIGNER", "REVIEW_LEASE_SIGNER", "FINAL_REVIEW_ATTESTER")[index - 1]
            if index <= 3 else actor["actor_id"]
        )
        role, purpose, domain = signature_math.SIGNATURE_PROFILE[expected_kind]
        exact = {
            "schema_version": ACTOR_ROW_SCHEMA,
            "actor_sequence": index,
            "actor_kind": expected_actor_kind,
            "actor_id": expected_actor_id,
            "pin_sequence": index,
            "pin_raw_bytes": len(pin_raw),
            "pin_raw_sha256": raw_sha256(pin_raw),
            "pin_artifact_sha256": pin["artifact_sha256"],
            "signature_kind": expected_kind,
            "key_role": role,
            "purpose": purpose,
            "domain": domain,
            "key_id": pin["key_id"],
            "key_epoch": pin["key_epoch"],
            "public_key_fingerprint_sha256": pin["public_key_fingerprint_sha256"],
            "signer_principal_commitment_sha256": pin["signer_principal_commitment_sha256"],
        }
        for field, expected in exact.items():
            if actor[field] != expected:
                raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
                    "actor/exact pin projection mismatch"
                )
        group = _identifier(actor["declared_independence_group_id"], "actor group")
        actor_id = _identifier(actor["actor_id"], "actor ID")
        if actor_id in actor_ids:
            raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
                "actor IDs must be globally distinct"
            )
        actor_ids.add(actor_id)
        if index <= 3:
            if group in singleton_groups:
                raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
                    "singleton groups must be distinct"
                )
            singleton_groups.add(group)
        else:
            if group in singleton_groups:
                raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
                    "reviewer ID/group conflicts with campaign roles"
                )
        for seen, value in (
            (key_ids, pin["key_id"]),
            (fingerprints, pin["public_key_fingerprint_sha256"]),
            (principals, pin["signer_principal_commitment_sha256"]),
            (pin_hashes, raw_sha256(pin_raw)),
        ):
            if value in seen:
                raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
                    "global key/pin/principal separation failed"
                )
            seen.add(value)
        scope = (pin["trust_domain"], pin["project_id"], pin["environment"])
        if base_scope is None:
            base_scope = scope
            revocation = pin["presented_revocation_snapshot_raw_sha256"]
            authority_anchor = pin["authority_anchor_sha256"]
        elif (
            scope != base_scope
            or pin["presented_revocation_snapshot_raw_sha256"] != revocation
            or pin["authority_anchor_sha256"] != authority_anchor
        ):
            raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
                "pin campaign scope/authority-anchor/revocation mismatch"
            )
        _self_hash(actor, "actor_row_sha256", f"actor {index}", domain="P0_DUAL_BLIND_REVIEW_ACTOR_ROW_V1")
        validated_pins.append(pin)
        validated_actors.append(actor)
    return validated_pins, validated_actors


def build_assignment_inventory_bytes(
    *,
    campaign_id: str,
    run_id: str,
    actor_roster_raw: bytes,
    reviewer_ids_by_input: Sequence[Sequence[str]],
    opaque_task_ids_by_input: Sequence[Sequence[str]],
) -> bytes:
    """Preassign two primaries and one reserve adjudicator for all 40 inputs."""

    _identifier(campaign_id, "campaign_id")
    _identifier(run_id, "run_id")
    actors, _ = _parse_jsonl(actor_roster_raw, "actor roster", maximum=_MAX_ROSTER_BYTES)
    reviewers = [_strict(row, _ACTOR_FIELDS, "reviewer roster row") for row in actors[3:]]
    by_id: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(reviewers, start=1):
        reviewer_id = _identifier(row["actor_id"], f"reviewer actor ID {index}")
        if reviewer_id in by_id:
            raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
                "reviewer actor IDs must be distinct"
            )
        by_id[reviewer_id] = row
    if (
        type(reviewer_ids_by_input) not in (list, tuple)
        or type(opaque_task_ids_by_input) not in (list, tuple)
        or len(reviewer_ids_by_input) != EXPECTED_INPUT_COUNT
        or len(opaque_task_ids_by_input) != EXPECTED_INPUT_COUNT
    ):
        raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
            "assignment input matrix must be 40 by 3"
        )
    rows: list[dict[str, Any]] = []
    task_ids: set[str] = set()
    sequence = 0
    for input_sequence, (reviewer_ids, opaque_ids) in enumerate(
        zip(reviewer_ids_by_input, opaque_task_ids_by_input, strict=True), start=1
    ):
        if type(reviewer_ids) not in (list, tuple) or type(opaque_ids) not in (list, tuple) or len(reviewer_ids) != 3 or len(opaque_ids) != 3:
            raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
                "each input requires exactly three preassignments"
            )
        selected: list[dict[str, Any]] = []
        for reviewer_id in reviewer_ids:
            reviewer_id = _identifier(reviewer_id, "assigned reviewer ID")
            reviewer = by_id.get(reviewer_id)
            if reviewer is None:
                raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
                    "assigned reviewer is absent from the human roster"
                )
            selected.append(reviewer)
        for field in (
            "actor_id", "pin_raw_sha256", "key_id", "public_key_fingerprint_sha256",
            "signer_principal_commitment_sha256", "declared_independence_group_id",
        ):
            if len({row[field] for row in selected}) != 3:
                raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
                    "per-input reviewer identity/key/principal/group separation failed"
                )
        for slot, reviewer, opaque in zip(ASSIGNMENT_SLOTS, selected, opaque_ids, strict=True):
            sequence += 1
            opaque = _opaque_id(opaque, "opaque task ID")
            if opaque in task_ids:
                raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
                    "opaque task IDs must be globally unique"
                )
            task_ids.add(opaque)
            material = {
                "schema_version": ASSIGNMENT_ROW_SCHEMA,
                "assignment_sequence": sequence,
                "campaign_id": campaign_id,
                "run_id": run_id,
                "input_sequence": input_sequence,
                "assignment_slot": slot,
                "reviewer_id": reviewer["actor_id"],
                "reviewer_pin_raw_sha256": reviewer["pin_raw_sha256"],
                "reviewer_key_id": reviewer["key_id"],
                "reviewer_key_epoch": reviewer["key_epoch"],
                "reviewer_public_key_fingerprint_sha256": reviewer["public_key_fingerprint_sha256"],
                "reviewer_principal_commitment_sha256": reviewer["signer_principal_commitment_sha256"],
                "reviewer_independence_group_id": reviewer["declared_independence_group_id"],
                "opaque_task_id": opaque,
            }
            rows.append(_with_self_hash(material, "assignment_row_sha256", domain="P0_DUAL_BLIND_REVIEW_ASSIGNMENT_ROW_V1"))
    raw = b"".join(canonical_file_bytes(row) for row in rows)
    if len(raw) > _MAX_ASSIGNMENT_BYTES:
        raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
            "assignment byte bound exceeded"
        )
    _validate_assignments(raw, reviewers, campaign_id=campaign_id, run_id=run_id)
    return raw


def _validate_assignments(
    raw: bytes,
    reviewers: Sequence[Mapping[str, Any]],
    *,
    campaign_id: str,
    run_id: str,
) -> list[dict[str, Any]]:
    rows, _ = _parse_jsonl(raw, "assignment inventory", maximum=_MAX_ASSIGNMENT_BYTES)
    if len(rows) != TOTAL_ASSIGNMENT_COUNT:
        raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
            "assignment inventory must contain exactly 120 rows"
        )
    by_id: dict[str, Mapping[str, Any]] = {}
    for index, reviewer_row in enumerate(reviewers, start=1):
        reviewer_id = _identifier(
            reviewer_row["actor_id"], f"reviewer actor ID {index}"
        )
        if reviewer_id in by_id:
            raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
                "reviewer actor ID duplicate"
            )
        by_id[reviewer_id] = reviewer_row
    opaque_ids: set[str] = set()
    for index, value in enumerate(rows, start=1):
        row = _strict(value, _ASSIGNMENT_FIELDS, f"assignment {index}")
        input_sequence = (index - 1) // 3 + 1
        slot = ASSIGNMENT_SLOTS[(index - 1) % 3]
        reviewer_id = _identifier(row["reviewer_id"], "assignment reviewer ID")
        reviewer = by_id.get(reviewer_id)
        if (
            row["schema_version"] != ASSIGNMENT_ROW_SCHEMA
            or _integer(row["assignment_sequence"], "assignment sequence", 1) != index
            or row["campaign_id"] != campaign_id or row["run_id"] != run_id
            or _integer(row["input_sequence"], "input sequence", 1, EXPECTED_INPUT_COUNT) != input_sequence
            or row["assignment_slot"] != slot or reviewer is None
        ):
            raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
                "assignment physical identity mismatch"
            )
        exact = {
            "reviewer_pin_raw_sha256": reviewer["pin_raw_sha256"],
            "reviewer_key_id": reviewer["key_id"],
            "reviewer_key_epoch": reviewer["key_epoch"],
            "reviewer_public_key_fingerprint_sha256": reviewer["public_key_fingerprint_sha256"],
            "reviewer_principal_commitment_sha256": reviewer["signer_principal_commitment_sha256"],
            "reviewer_independence_group_id": reviewer["declared_independence_group_id"],
        }
        if any(row[field] != expected for field, expected in exact.items()):
            raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
                "assignment reviewer projection mismatch"
            )
        opaque = _opaque_id(row["opaque_task_id"], "assignment opaque task ID")
        if opaque in opaque_ids:
            raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
                "assignment opaque task ID duplicate"
            )
        opaque_ids.add(opaque)
        _self_hash(row, "assignment_row_sha256", f"assignment {index}", domain="P0_DUAL_BLIND_REVIEW_ASSIGNMENT_ROW_V1")
    for start in range(0, TOTAL_ASSIGNMENT_COUNT, 3):
        triad = rows[start : start + 3]
        for field in (
            "reviewer_id", "reviewer_pin_raw_sha256", "reviewer_key_id",
            "reviewer_public_key_fingerprint_sha256",
            "reviewer_principal_commitment_sha256", "reviewer_independence_group_id",
        ):
            if len({row[field] for row in triad}) != 3:
                raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
                    "assignment triad separation mismatch"
                )
    return rows


def _validate_review_units(raw: bytes) -> list[dict[str, Any]]:
    rows, _ = _parse_jsonl(raw, "review-unit inventory", maximum=_MAX_REVIEW_UNIT_BYTES)
    expected_fields = frozenset(review_accounting.ARTIFACT_FIELDS["review_unit_row"])
    if len(rows) != EXPECTED_INPUT_COUNT:
        raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
            "review-unit inventory must contain exactly 40 rows"
        )
    for index, value in enumerate(rows, start=1):
        row = _strict(value, expected_fields, f"review unit {index}")
        if (
            row["schema_version"] != review_accounting.REVIEW_UNIT_ROW_SCHEMA
            or _integer(row["review_unit_sequence"], "review unit sequence", 1) != index
            or _integer(row["input_sequence"], "review input sequence", 1) != index
        ):
            raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
                "review-unit physical order mismatch"
            )
        for field in (
            "selected_input_sha256", "bridge_row_sha256", "payload_sha256",
            "result_row_sha256", "full_payload_missed_span_unit_sha256",
            "emitted_observation_subjects_sha256", "input_review_unit_sha256",
        ):
            _sha(row[field], f"review unit.{field}")
        payload = _decode_base64(row["payload_base64"], length=None, label="review unit payload")
        if (
            len(payload) != _integer(row["payload_bytes"], "review unit payload bytes")
            or raw_sha256(payload) != row["payload_sha256"]
            or type(row["emitted_observation_subjects"]) is not list
            or len(row["emitted_observation_subjects"])
            != _integer(row["emitted_observation_count"], "emitted observation count")
            or canonical_sha256(row["emitted_observation_subjects"])
            != row["emitted_observation_subjects_sha256"]
        ):
            raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
                "review-unit payload or parser projection mismatch"
            )
        material = dict(row)
        declared = material.pop("input_review_unit_sha256")
        expected = canonical_sha256({"domain": "P0_PRESENTED_NEUTRAL_INPUT_REVIEW_UNIT_V1", **material})
        if not hmac.compare_digest(declared, expected):
            raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
                "review-unit self-hash mismatch"
            )
    return rows


def build_evaluator_private_map_bytes(
    *,
    campaign_id: str,
    run_id: str,
    review_unit_inventory_raw: bytes,
    assignment_inventory_raw: bytes,
    actor_roster_raw: bytes,
) -> bytes:
    """Bind 120 opaque assignments to evaluator-private upstream metadata."""

    units = _validate_review_units(review_unit_inventory_raw)
    actors, _ = _parse_jsonl(actor_roster_raw, "actor roster", maximum=_MAX_ROSTER_BYTES)
    reviewers = [_strict(row, _ACTOR_FIELDS, "reviewer actor") for row in actors[3:]]
    assignments = _validate_assignments(
        assignment_inventory_raw, reviewers, campaign_id=campaign_id, run_id=run_id
    )
    rows: list[dict[str, Any]] = []
    for index, assignment in enumerate(assignments, start=1):
        unit = units[assignment["input_sequence"] - 1]
        material = {
            "schema_version": PRIVATE_MAP_ROW_SCHEMA,
            "map_sequence": index,
            "campaign_id": campaign_id,
            "run_id": run_id,
            "input_sequence": unit["input_sequence"],
            "assignment_slot": assignment["assignment_slot"],
            "opaque_task_id": assignment["opaque_task_id"],
            "reviewer_id": assignment["reviewer_id"],
            "reviewer_pin_raw_sha256": assignment["reviewer_pin_raw_sha256"],
            "reviewer_key_id": assignment["reviewer_key_id"],
            "reviewer_key_epoch": assignment["reviewer_key_epoch"],
            "reviewer_public_key_fingerprint_sha256": assignment["reviewer_public_key_fingerprint_sha256"],
            "reviewer_principal_commitment_sha256": assignment["reviewer_principal_commitment_sha256"],
            "reviewer_independence_group_id": assignment["reviewer_independence_group_id"],
            "assignment_row_sha256": assignment["assignment_row_sha256"],
            "input_review_unit_sha256": unit["input_review_unit_sha256"],
            "frame_candidate_id": unit["frame_candidate_id"],
            "registry_record_id": unit["registry_record_id"],
            "selected_input_sha256": unit["selected_input_sha256"],
            "bridge_row_sha256": unit["bridge_row_sha256"],
            "payload_base64": unit["payload_base64"],
            "payload_bytes": unit["payload_bytes"],
            "payload_sha256": unit["payload_sha256"],
            "parser_result_row_sha256": unit["result_row_sha256"],
            "parser_terminal_disposition": unit["parser_terminal_disposition"],
            "full_payload_missed_span_unit_sha256": unit["full_payload_missed_span_unit_sha256"],
            "emitted_observation_subjects_sha256": unit["emitted_observation_subjects_sha256"],
            "emitted_observation_count": unit["emitted_observation_count"],
        }
        rows.append(_with_self_hash(material, "private_map_row_sha256", domain="P0_DUAL_BLIND_REVIEW_PRIVATE_MAP_ROW_V1"))
    raw = b"".join(canonical_file_bytes(row) for row in rows)
    if len(raw) > _MAX_PRIVATE_MAP_BYTES:
        raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
            "evaluator-private map byte bound exceeded"
        )
    _validate_private_map(raw, units, assignments, campaign_id=campaign_id, run_id=run_id)
    return raw


def _validate_private_map(
    raw: bytes,
    units: Sequence[Mapping[str, Any]],
    assignments: Sequence[Mapping[str, Any]],
    *,
    campaign_id: str,
    run_id: str,
) -> list[dict[str, Any]]:
    rows, _ = _parse_jsonl(raw, "evaluator-private map", maximum=_MAX_PRIVATE_MAP_BYTES)
    if len(rows) != TOTAL_ASSIGNMENT_COUNT:
        raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
            "evaluator-private map must contain exactly 120 rows"
        )
    for index, (value, assignment) in enumerate(zip(rows, assignments, strict=True), start=1):
        row = _strict(value, _PRIVATE_MAP_FIELDS, f"private map {index}")
        unit = units[assignment["input_sequence"] - 1]
        expected = {
            "schema_version": PRIVATE_MAP_ROW_SCHEMA,
            "map_sequence": index,
            "campaign_id": campaign_id,
            "run_id": run_id,
            "input_sequence": unit["input_sequence"],
            "assignment_slot": assignment["assignment_slot"],
            "opaque_task_id": assignment["opaque_task_id"],
            "reviewer_id": assignment["reviewer_id"],
            "reviewer_pin_raw_sha256": assignment["reviewer_pin_raw_sha256"],
            "reviewer_key_id": assignment["reviewer_key_id"],
            "reviewer_key_epoch": assignment["reviewer_key_epoch"],
            "reviewer_public_key_fingerprint_sha256": assignment["reviewer_public_key_fingerprint_sha256"],
            "reviewer_principal_commitment_sha256": assignment["reviewer_principal_commitment_sha256"],
            "reviewer_independence_group_id": assignment["reviewer_independence_group_id"],
            "assignment_row_sha256": assignment["assignment_row_sha256"],
            "input_review_unit_sha256": unit["input_review_unit_sha256"],
            "frame_candidate_id": unit["frame_candidate_id"],
            "registry_record_id": unit["registry_record_id"],
            "selected_input_sha256": unit["selected_input_sha256"],
            "bridge_row_sha256": unit["bridge_row_sha256"],
            "payload_base64": unit["payload_base64"],
            "payload_bytes": unit["payload_bytes"],
            "payload_sha256": unit["payload_sha256"],
            "parser_result_row_sha256": unit["result_row_sha256"],
            "parser_terminal_disposition": unit["parser_terminal_disposition"],
            "full_payload_missed_span_unit_sha256": unit["full_payload_missed_span_unit_sha256"],
            "emitted_observation_subjects_sha256": unit["emitted_observation_subjects_sha256"],
            "emitted_observation_count": unit["emitted_observation_count"],
        }
        if any(row[field] != expected_value for field, expected_value in expected.items()):
            raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
                "evaluator-private map projection mismatch"
            )
        _self_hash(row, "private_map_row_sha256", f"private map {index}", domain="P0_DUAL_BLIND_REVIEW_PRIVATE_MAP_ROW_V1")
    return rows


def build_reviewer_facing_task_inventory_bytes(
    *,
    campaign_id: str,
    run_id: str,
    evaluator_private_map_raw: bytes,
    review_guideline_raw: bytes,
    response_schema_raw: bytes,
) -> bytes:
    """Project 120 payload-only task rows without evaluator-private metadata."""

    guideline = _validate_guideline(review_guideline_raw)
    response = _validate_response_schema(response_schema_raw)
    if guideline["campaign_id"] != campaign_id or response["campaign_id"] != campaign_id:
        raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
            "guideline/response campaign mismatch"
        )
    private_rows, _ = _parse_jsonl(
        evaluator_private_map_raw, "evaluator-private map", maximum=_MAX_PRIVATE_MAP_BYTES
    )
    if len(private_rows) != TOTAL_ASSIGNMENT_COUNT:
        raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
            "evaluator-private map must contain exactly 120 rows"
        )
    projected: list[dict[str, Any]] = []
    for index, value in enumerate(private_rows, start=1):
        private = _strict(value, _PRIVATE_MAP_FIELDS, f"private map {index}")
        _self_hash(private, "private_map_row_sha256", f"private map {index}", domain="P0_DUAL_BLIND_REVIEW_PRIVATE_MAP_ROW_V1")
        if private["campaign_id"] != campaign_id or private["run_id"] != run_id:
            raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
                "private map campaign/run mismatch"
            )
        _opaque_id(private["opaque_task_id"], "private map opaque task ID")
        projected.append({
            "schema_version": BLIND_TASK_ROW_SCHEMA,
            "campaign_id": campaign_id,
            "run_id": run_id,
            "opaque_task_id": private["opaque_task_id"],
            "payload_base64": private["payload_base64"],
            "payload_bytes": private["payload_bytes"],
            "payload_sha256": private["payload_sha256"],
            "review_guideline_raw_sha256": raw_sha256(review_guideline_raw),
            "review_guideline_artifact_sha256": guideline["artifact_sha256"],
            "response_schema_raw_sha256": raw_sha256(response_schema_raw),
            "response_schema_artifact_sha256": response["artifact_sha256"],
        })
    # The public inventory order must not preserve the private input-major triads.
    # Sorting by a caller-presented opaque identifier gives an exact, deterministic
    # order without exposing input_sequence or assignment_slot.  This proves only
    # structural non-projection; identifier unpredictability and dispatch isolation
    # remain explicitly unverified.
    projected.sort(key=lambda row: row["opaque_task_id"])
    rows = [
        _with_self_hash(
            {**material, "task_sequence": index},
            "blind_task_row_sha256",
            domain="P0_DUAL_BLIND_REVIEW_TASK_ROW_V1",
        )
        for index, material in enumerate(projected, start=1)
    ]
    raw = b"".join(canonical_file_bytes(row) for row in rows)
    if len(raw) > _MAX_BLIND_TASK_BYTES:
        raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
            "reviewer-facing task byte bound exceeded"
        )
    _validate_blind_tasks(
        raw, private_rows, guideline, response,
        guideline_raw=review_guideline_raw, response_raw=response_schema_raw,
        campaign_id=campaign_id, run_id=run_id,
    )
    return raw


def _validate_blind_tasks(
    raw: bytes,
    private_rows: Sequence[Mapping[str, Any]],
    guideline: Mapping[str, Any],
    response: Mapping[str, Any],
    *,
    guideline_raw: bytes,
    response_raw: bytes,
    campaign_id: str,
    run_id: str,
) -> list[dict[str, Any]]:
    rows, _ = _parse_jsonl(raw, "reviewer-facing task inventory", maximum=_MAX_BLIND_TASK_BYTES)
    if len(rows) != TOTAL_ASSIGNMENT_COUNT or len(private_rows) != TOTAL_ASSIGNMENT_COUNT:
        raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
            "reviewer-facing task inventory must contain exactly 120 rows"
        )
    opaque: set[str] = set()
    private_by_task_id: dict[str, Mapping[str, Any]] = {}
    for index, private in enumerate(private_rows, start=1):
        task_id = _opaque_id(
            private["opaque_task_id"], f"evaluator-private opaque task ID {index}"
        )
        if task_id in private_by_task_id:
            raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
                "evaluator-private opaque task ID duplicate"
            )
        private_by_task_id[task_id] = private
    expected_order = sorted(private_by_task_id)
    for index, value in enumerate(rows, start=1):
        row = _strict(value, _BLIND_TASK_FIELDS, f"blind task {index}")
        if row["opaque_task_id"] != expected_order[index - 1]:
            raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
                "reviewer-facing task inventory must use opaque-ID order"
            )
        private = private_by_task_id[row["opaque_task_id"]]
        expected = {
            "schema_version": BLIND_TASK_ROW_SCHEMA,
            "task_sequence": index,
            "campaign_id": campaign_id,
            "run_id": run_id,
            "opaque_task_id": private["opaque_task_id"],
            "payload_base64": private["payload_base64"],
            "payload_bytes": private["payload_bytes"],
            "payload_sha256": private["payload_sha256"],
            "review_guideline_raw_sha256": raw_sha256(guideline_raw),
            "review_guideline_artifact_sha256": guideline["artifact_sha256"],
            "response_schema_raw_sha256": raw_sha256(response_raw),
            "response_schema_artifact_sha256": response["artifact_sha256"],
        }
        if any(row[field] != expected_value for field, expected_value in expected.items()):
            raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
                "reviewer-facing task safe projection mismatch"
            )
        task_id = _opaque_id(row["opaque_task_id"], "blind task opaque ID")
        if task_id in opaque:
            raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
                "blind task opaque ID duplicate"
            )
        opaque.add(task_id)
        payload = _decode_base64(row["payload_base64"], length=None, label="blind task payload")
        if len(payload) != _integer(row["payload_bytes"], "blind task payload bytes") or raw_sha256(payload) != row["payload_sha256"]:
            raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
                "blind task payload binding mismatch"
            )
        _self_hash(row, "blind_task_row_sha256", f"blind task {index}", domain="P0_DUAL_BLIND_REVIEW_TASK_ROW_V1")
    return rows


def _inventory_sha(rows: Sequence[Mapping[str, Any]]) -> str:
    return canonical_sha256(list(rows))


def build_campaign_precommit_bytes(
    *,
    campaign_id: str,
    run_id: str,
    trust_domain: str,
    project_id: str,
    environment: str,
    sampling_plan_raw: bytes,
    expected_sampling_plan_raw_sha256: str,
    bridge_inventory_raw: bytes,
    batch_precommit_raw: bytes,
    expected_batch_precommit_raw_sha256: str,
    parser_results_raw: bytes,
    batch_receipt_raw: bytes,
    unreviewed_inventory_raw: bytes,
    review_unit_inventory_raw: bytes,
    review_guideline_raw: bytes,
    response_schema_raw: bytes,
    key_pin_inventory_raw: bytes,
    actor_roster_raw: bytes,
    assignment_inventory_raw: bytes,
    evaluator_private_map_raw: bytes,
    reviewer_facing_task_inventory_raw: bytes,
    presented_assignment_sealed_at: str,
    presented_campaign_precommitted_at: str,
) -> bytes:
    """Build the result-free campaign-policy payload for signature."""

    campaign_id = _identifier(campaign_id, "campaign_id")
    run_id = _identifier(run_id, "run_id")
    trust_domain = _identifier(trust_domain, "trust_domain")
    project_id = _identifier(project_id, "project_id")
    environment = _identifier(environment, "environment")
    _bounded_bytes(
        bridge_inventory_raw, "upstream bridge inventory", _MAX_UPSTREAM_BRIDGE_BYTES
    )
    _bounded_bytes(
        parser_results_raw, "upstream parser results", _MAX_UPSTREAM_RESULT_BYTES
    )
    _bounded_bytes(
        unreviewed_inventory_raw,
        "upstream unreviewed inventory",
        _MAX_UPSTREAM_UNREVIEWED_BYTES,
    )
    _sha(expected_sampling_plan_raw_sha256, "expected sampling plan SHA")
    _sha(expected_batch_precommit_raw_sha256, "expected batch precommit SHA")
    if raw_sha256(sampling_plan_raw) != expected_sampling_plan_raw_sha256:
        raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
            "sampling plan expectation mismatch"
        )
    if raw_sha256(batch_precommit_raw) != expected_batch_precommit_raw_sha256:
        raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
            "batch precommit expectation mismatch"
        )
    try:
        rebuilt_units_raw = review_accounting.build_review_unit_inventory_bytes(
            sampling_plan_raw=sampling_plan_raw,
            expected_sampling_plan_raw_sha256=expected_sampling_plan_raw_sha256,
            bridge_inventory_raw=bridge_inventory_raw,
            batch_precommit_raw=batch_precommit_raw,
            expected_batch_precommit_raw_sha256=expected_batch_precommit_raw_sha256,
            results_raw=parser_results_raw,
            batch_receipt_raw=batch_receipt_raw,
            unreviewed_inventory_raw=unreviewed_inventory_raw,
        )
    except Exception as exc:
        raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
            "upstream plan-to-review-unit rebuild rejected"
        ) from exc
    if rebuilt_units_raw != review_unit_inventory_raw:
        raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
            "review-unit inventory differs from exact upstream rebuild"
        )
    units = _validate_review_units(review_unit_inventory_raw)
    guideline = _validate_guideline(review_guideline_raw)
    response = _validate_response_schema(response_schema_raw)
    pins, actors = _validate_pin_and_roster(key_pin_inventory_raw, actor_roster_raw)
    if (
        guideline["campaign_id"] != campaign_id or response["campaign_id"] != campaign_id
        or (pins[0]["trust_domain"], pins[0]["project_id"], pins[0]["environment"])
        != (trust_domain, project_id, environment)
    ):
        raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
            "campaign scope projection mismatch"
        )
    reviewers = actors[3:]
    assignments = _validate_assignments(
        assignment_inventory_raw, reviewers, campaign_id=campaign_id, run_id=run_id
    )
    private_rows = _validate_private_map(
        evaluator_private_map_raw, units, assignments,
        campaign_id=campaign_id, run_id=run_id,
    )
    task_rows = _validate_blind_tasks(
        reviewer_facing_task_inventory_raw, private_rows, guideline, response,
        guideline_raw=review_guideline_raw, response_raw=response_schema_raw,
        campaign_id=campaign_id, run_id=run_id,
    )
    unreviewed = _parse_line(
        unreviewed_inventory_raw,
        "upstream unreviewed inventory",
        maximum=_MAX_UPSTREAM_UNREVIEWED_BYTES,
    )
    upstream_sealed_at = _time(unreviewed.get("review_inventory_sealed_at"), "upstream review inventory seal")
    assignment_sealed_at = _time(presented_assignment_sealed_at, "presented assignment seal")
    campaign_precommitted_at = _time(presented_campaign_precommitted_at, "presented campaign precommit")
    if not upstream_sealed_at < assignment_sealed_at < campaign_precommitted_at:
        raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
            "presented campaign chronology is invalid"
        )
    material = {
        "schema_version": CAMPAIGN_PRECOMMIT_SCHEMA,
        "record_origin": RECORD_ORIGIN,
        "component_version": COMPONENT_VERSION,
        "campaign_id": campaign_id,
        "run_id": run_id,
        "trust_domain": trust_domain,
        "project_id": project_id,
        "environment": environment,
        "component_manifest_sha256": COMPONENT_MANIFEST_SHA256,
        "upstream_review_component_manifest_sha256": review_accounting.COMPONENT_MANIFEST_SHA256,
        "upstream_sampling_plan_raw_sha256": raw_sha256(sampling_plan_raw),
        "upstream_bridge_inventory_raw_sha256": raw_sha256(bridge_inventory_raw),
        "upstream_batch_precommit_raw_sha256": raw_sha256(batch_precommit_raw),
        "upstream_parser_results_raw_sha256": raw_sha256(parser_results_raw),
        "upstream_batch_receipt_raw_sha256": raw_sha256(batch_receipt_raw),
        "upstream_unreviewed_inventory_raw_sha256": raw_sha256(unreviewed_inventory_raw),
        "upstream_review_unit_inventory_raw_sha256": raw_sha256(review_unit_inventory_raw),
        "upstream_review_unit_inventory_sha256": _inventory_sha(units),
        "review_guideline_raw_sha256": raw_sha256(review_guideline_raw),
        "review_guideline_artifact_sha256": guideline["artifact_sha256"],
        "response_schema_raw_sha256": raw_sha256(response_schema_raw),
        "response_schema_artifact_sha256": response["artifact_sha256"],
        "key_pin_inventory_raw_sha256": raw_sha256(key_pin_inventory_raw),
        "key_pin_count": len(pins),
        "actor_roster_raw_sha256": raw_sha256(actor_roster_raw),
        "actor_count": len(actors),
        "reviewer_count": len(reviewers),
        "assignment_inventory_raw_sha256": raw_sha256(assignment_inventory_raw),
        "assignment_inventory_sha256": _inventory_sha(assignments),
        "evaluator_private_map_raw_sha256": raw_sha256(evaluator_private_map_raw),
        "evaluator_private_map_sha256": _inventory_sha(private_rows),
        "reviewer_facing_task_inventory_raw_sha256": raw_sha256(reviewer_facing_task_inventory_raw),
        "reviewer_facing_task_inventory_sha256": _inventory_sha(task_rows),
        "expected_input_count": EXPECTED_INPUT_COUNT,
        "primary_assignment_count": PRIMARY_ASSIGNMENT_COUNT,
        "reserve_assignment_count": RESERVE_ASSIGNMENT_COUNT,
        "total_assignment_count": TOTAL_ASSIGNMENT_COUNT,
        "selected_input_itt_denominator": EXPECTED_INPUT_COUNT,
        "planned_primary_review_opportunity_denominator": PRIMARY_ASSIGNMENT_COUNT,
        "primary_pair_input_denominator": EXPECTED_INPUT_COUNT,
        "maximum_reserve_adjudication_opportunity_denominator": RESERVE_ASSIGNMENT_COUNT,
        "planned_final_judged_input_denominator": EXPECTED_INPUT_COUNT,
        "required_adjudication_denominator": None,
        "required_adjudication_denominator_derivation": "AFTER_ALL_80_PRIMARY_TERMINALS_FROZEN_COUNT_BOTH_AUTHORITY_QUALIFIED_JUDGED_PAIRS_WITH_DIFFERENT_CANONICAL_FULL_GOLD_SETS",
        "assignment_slot_order": list(ASSIGNMENT_SLOTS),
        "review_protocol": _result_free_review_protocol(),
        "prior_presented_result_import_policy": "FORBIDDEN_NEW_CAMPAIGN_ONLY",
        "presented_assignment_sealed_at": presented_assignment_sealed_at,
        "presented_campaign_precommitted_at": presented_campaign_precommitted_at,
        "presented_policy_only": True,
        "action_applied": False,
        "operational_effect": OPERATIONAL_EFFECT,
    }
    raw = canonical_file_bytes(_with_self_hash(material))
    if len(raw) > _MAX_OBJECT_BYTES:
        raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
            "campaign precommit byte bound exceeded"
        )
    return raw


def _validate_policy_subject(
    subject_raw: bytes,
    *,
    precommit_raw: bytes,
    precommit: Mapping[str, Any],
) -> dict[str, Any]:
    row = _strict(_parse_line(subject_raw, "policy signature subject"), _SIGNATURE_SUBJECT_FIELDS, "policy signature subject")
    role, purpose, domain = signature_math.SIGNATURE_PROFILE[
        signature_math.CAMPAIGN_POLICY_PREAUTHORIZATION
    ]
    if (
        row["schema_version"] != signature_math.SUBJECT_SCHEMA
        or row["record_origin"] != signature_math.PRESENTED_SUBJECT_ORIGIN
        or row["component_version"] != signature_math.COMPONENT_VERSION
        or row["signature_kind"] != signature_math.CAMPAIGN_POLICY_PREAUTHORIZATION
        or row["domain"] != domain or row["purpose"] != purpose or row["key_role"] != role
        or row["campaign_id"] != precommit["campaign_id"]
        or row["run_id"] != precommit["run_id"]
        or row["trust_domain"] != precommit["trust_domain"]
        or row["project_id"] != precommit["project_id"]
        or row["environment"] != precommit["environment"]
        or row["presented_issued_at"] != precommit["presented_campaign_precommitted_at"]
        or row["payload_schema"] != CAMPAIGN_PRECOMMIT_SCHEMA
        or row["payload_bytes"] != len(precommit_raw)
        or row["payload_raw_sha256"] != raw_sha256(precommit_raw)
        or row["payload_artifact_sha256"] != precommit["artifact_sha256"]
        or row["predecessor_subject_raw_sha256"] is not None
        or row["caller_presented_subject_only"] is not True
        or row["external_authority_claimed"] is not False
        or row["actual_human_review_claimed"] is not False
        or row["semantic_promotion_claimed"] is not False
        or row["action_applied"] is not False
        or row["operational_effect"] != OPERATIONAL_EFFECT
    ):
        raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
            "campaign-policy signature subject mismatch"
        )
    _sha(row["nonce_commitment_sha256"], "policy subject nonce commitment")
    _self_hash(row, "artifact_sha256", "policy signature subject")
    return row


def validate_presented_dual_blind_review_campaign_precommit_bundle(
    *,
    sampling_plan_raw: bytes,
    expected_sampling_plan_raw_sha256: str,
    bridge_inventory_raw: bytes,
    batch_precommit_raw: bytes,
    expected_batch_precommit_raw_sha256: str,
    parser_results_raw: bytes,
    batch_receipt_raw: bytes,
    unreviewed_inventory_raw: bytes,
    review_unit_inventory_raw: bytes,
    review_guideline_raw: bytes,
    response_schema_raw: bytes,
    key_pin_inventory_raw: bytes,
    actor_roster_raw: bytes,
    assignment_inventory_raw: bytes,
    evaluator_private_map_raw: bytes,
    reviewer_facing_task_inventory_raw: bytes,
    campaign_precommit_raw: bytes,
    policy_signature_subject_raw: bytes,
    policy_signature_envelope_raw: bytes,
) -> dict[str, Any]:
    """Validate the full result-free precommit and policy signature mathematics."""

    precommit = _strict(
        _parse_line(campaign_precommit_raw, "campaign precommit"),
        _PRECOMMIT_FIELDS,
        "campaign precommit",
    )
    expected_precommit = build_campaign_precommit_bytes(
        campaign_id=precommit["campaign_id"], run_id=precommit["run_id"],
        trust_domain=precommit["trust_domain"], project_id=precommit["project_id"],
        environment=precommit["environment"], sampling_plan_raw=sampling_plan_raw,
        expected_sampling_plan_raw_sha256=expected_sampling_plan_raw_sha256,
        bridge_inventory_raw=bridge_inventory_raw,
        batch_precommit_raw=batch_precommit_raw,
        expected_batch_precommit_raw_sha256=expected_batch_precommit_raw_sha256,
        parser_results_raw=parser_results_raw, batch_receipt_raw=batch_receipt_raw,
        unreviewed_inventory_raw=unreviewed_inventory_raw,
        review_unit_inventory_raw=review_unit_inventory_raw,
        review_guideline_raw=review_guideline_raw,
        response_schema_raw=response_schema_raw,
        key_pin_inventory_raw=key_pin_inventory_raw,
        actor_roster_raw=actor_roster_raw,
        assignment_inventory_raw=assignment_inventory_raw,
        evaluator_private_map_raw=evaluator_private_map_raw,
        reviewer_facing_task_inventory_raw=reviewer_facing_task_inventory_raw,
        presented_assignment_sealed_at=precommit["presented_assignment_sealed_at"],
        presented_campaign_precommitted_at=precommit["presented_campaign_precommitted_at"],
    )
    if campaign_precommit_raw != expected_precommit:
        raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
            "campaign precommit exact recomputation mismatch"
        )
    _validate_policy_subject(
        policy_signature_subject_raw,
        precommit_raw=campaign_precommit_raw,
        precommit=precommit,
    )
    pins, actors = _validate_pin_and_roster(key_pin_inventory_raw, actor_roster_raw)
    policy_pin_raw = key_pin_inventory_raw.splitlines(keepends=True)[0]
    try:
        signature_receipt = signature_math.validate_presented_neutral_review_signature_math(
            public_key_pin_raw=policy_pin_raw,
            subject_raw=policy_signature_subject_raw,
            payload_raw=campaign_precommit_raw,
            signature_envelope_raw=policy_signature_envelope_raw,
            expected_signature_kind=signature_math.CAMPAIGN_POLICY_PREAUTHORIZATION,
            expected_public_key_pin_raw_sha256=raw_sha256(policy_pin_raw),
            expected_subject_raw_sha256=raw_sha256(policy_signature_subject_raw),
        )
    except Exception as exc:
        raise P0PresentedDualBlindReviewCampaignPrecommitV1Error(
            "campaign-policy signature mathematics rejected"
        ) from exc
    material = {
        "schema_version": RECEIPT_SCHEMA,
        "record_origin": RECORD_ORIGIN,
        "component_version": COMPONENT_VERSION,
        "component_manifest_sha256": COMPONENT_MANIFEST_SHA256,
        "campaign_id": precommit["campaign_id"],
        "run_id": precommit["run_id"],
        "campaign_precommit_raw_sha256": raw_sha256(campaign_precommit_raw),
        "campaign_precommit_artifact_sha256": precommit["artifact_sha256"],
        "policy_signature_subject_raw_sha256": raw_sha256(policy_signature_subject_raw),
        "policy_signature_envelope_raw_sha256": raw_sha256(policy_signature_envelope_raw),
        "policy_signature_math_receipt": signature_receipt,
        "policy_signature_math_receipt_sha256": signature_receipt["receipt_sha256"],
        "upstream_plan_to_review_unit_exact_rebuild_verified": True,
        "roster_exact_raw_pin_binding_verified": True,
        "presented_p256_point_and_rfc5480_fingerprint_verified": True,
        "declared_key_id_distinctness_verified": True,
        "declared_fingerprint_distinctness_verified": True,
        "declared_principal_commitment_distinctness_verified": True,
        "singleton_declared_group_distinctness_verified": True,
        "per_input_declared_group_and_key_distinctness_verified": True,
        "dual_primary_and_reserve_preassignment_structure_verified": True,
        "blind_task_strict_projection_verified": True,
        "campaign_policy_signature_math_verified": True,
        "caller_presented_pin_inventory_only": True,
        "caller_presented_time_and_revocation_only": True,
        "prior_presented_result_imported": False,
        "review_result_input_count": 0,
        "selected_input_count": EXPECTED_INPUT_COUNT,
        "primary_assignment_count": PRIMARY_ASSIGNMENT_COUNT,
        "reserve_assignment_count": RESERVE_ASSIGNMENT_COUNT,
        "total_assignment_count": TOTAL_ASSIGNMENT_COUNT,
        "opaque_task_id_count": TOTAL_ASSIGNMENT_COUNT,
        "selected_input_itt_denominator": EXPECTED_INPUT_COUNT,
        "planned_primary_review_opportunity_denominator": PRIMARY_ASSIGNMENT_COUNT,
        "primary_pair_input_denominator": EXPECTED_INPUT_COUNT,
        "maximum_reserve_adjudication_opportunity_denominator": RESERVE_ASSIGNMENT_COUNT,
        "planned_final_judged_input_denominator": EXPECTED_INPUT_COUNT,
        "required_adjudication_denominator": None,
        "required_adjudication_denominator_derivation": "AFTER_ALL_80_PRIMARY_TERMINALS_FROZEN_COUNT_BOTH_AUTHORITY_QUALIFIED_JUDGED_PAIRS_WITH_DIFFERENT_CANONICAL_FULL_GOLD_SETS",
        "key_pin_count": len(pins),
        "reviewer_count": len(actors) - 3,
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
        "actual_human_review_count": 0,
        "actual_human_unreviewed_input_count": EXPECTED_INPUT_COUNT,
        "actual_primary_review_event_count": 0,
        "actual_pair_complete_input_count": 0,
        "actual_adjudicated_input_count": 0,
        "actual_judged_input_count": 0,
        "actual_source_credit_count": 0,
        "actual_context_credit_count": 0,
        "statistical_denominator_contribution": "NONE",
        "metric_status": METRIC_STATUS,
        "gate_status": GATE_STATUS,
        "action_applied": False,
        "operational_effect": OPERATIONAL_EFFECT,
    }
    return {**material, "receipt_sha256": canonical_sha256(material)}


ARTIFACT_FIELDS = {
    "guideline": sorted(_GUIDELINE_FIELDS),
    "response_schema": sorted(_RESPONSE_SCHEMA_FIELDS),
    "actor_row": sorted(_ACTOR_FIELDS),
    "assignment_row": sorted(_ASSIGNMENT_FIELDS),
    "private_map_row": sorted(_PRIVATE_MAP_FIELDS),
    "blind_task_row": sorted(_BLIND_TASK_FIELDS),
    "campaign_precommit": sorted(_PRECOMMIT_FIELDS),
}

COMPONENT_MANIFEST = {
    "schema_version": COMPONENT_MANIFEST_SCHEMA,
    "component": "p0_presented_dual_blind_review_campaign_precommit_v1_contract",
    "component_version": COMPONENT_VERSION,
    "record_origin": RECORD_ORIGIN,
    "upstream_review_component_manifest_sha256": review_accounting.COMPONENT_MANIFEST_SHA256,
    "signature_profile": {
        kind: {"key_role": profile[0], "purpose": profile[1], "domain": profile[2]}
        for kind, profile in signature_math.SIGNATURE_PROFILE.items()
    },
    "artifact_fields": ARTIFACT_FIELDS,
    "fixed_review_guideline_instructions": list(REVIEW_GUIDELINE_INSTRUCTIONS),
    "fixed_canonical_gold_set_comparison_profile": _canonical_gold_set_comparison_profile(),
    "fixed_terminal_field_semantics": _terminal_field_semantics(),
    "fixed_result_free_review_protocol": _result_free_review_protocol(),
    "cardinality": {
        "selected_inputs": EXPECTED_INPUT_COUNT,
        "primary_assignments": PRIMARY_ASSIGNMENT_COUNT,
        "reserve_assignments": RESERVE_ASSIGNMENT_COUNT,
        "total_assignments": TOTAL_ASSIGNMENT_COUNT,
        "opaque_task_ids": TOTAL_ASSIGNMENT_COUNT,
        "minimum_reviewers": MIN_REVIEWERS,
        "maximum_reviewers": MAX_REVIEWERS,
        "singleton_role_pins": 3,
    },
    "statistical_denominators": {
        "selected_input_itt": EXPECTED_INPUT_COUNT,
        "planned_primary_review_opportunities": PRIMARY_ASSIGNMENT_COUNT,
        "primary_pair_inputs": EXPECTED_INPUT_COUNT,
        "maximum_reserve_adjudication_opportunities": RESERVE_ASSIGNMENT_COUNT,
        "planned_final_judged_inputs": EXPECTED_INPUT_COUNT,
        "required_adjudication": None,
        "required_adjudication_derivation": "AFTER_ALL_80_PRIMARY_TERMINALS_FROZEN_COUNT_BOTH_AUTHORITY_QUALIFIED_JUDGED_PAIRS_WITH_DIFFERENT_CANONICAL_FULL_GOLD_SETS",
    },
    "assignment_slots": list(ASSIGNMENT_SLOTS),
    "blind_task_exact_field_allowlist": sorted(_BLIND_TASK_FIELDS),
    "private_metadata_fields_excluded_from_blind_task": sorted(
        _PRIVATE_MAP_FIELDS - _BLIND_TASK_FIELDS
    ),
    "global_distinct_fields": [
        "key_id", "public_key_fingerprint_sha256",
        "signer_principal_commitment_sha256", "pin_raw_sha256",
    ],
    "per_input_three_way_distinct_fields": [
        "reviewer_id", "reviewer_pin_raw_sha256", "reviewer_key_id",
        "reviewer_public_key_fingerprint_sha256",
        "reviewer_principal_commitment_sha256", "reviewer_independence_group_id",
    ],
    "limits": {
        "max_object_bytes": _MAX_OBJECT_BYTES,
        "max_guideline_bytes": _MAX_GUIDELINE_BYTES,
        "max_pin_line_bytes": _MAX_PIN_LINE_BYTES,
        "max_pin_inventory_bytes": _MAX_PIN_INVENTORY_BYTES,
        "max_roster_bytes": _MAX_ROSTER_BYTES,
        "max_review_unit_bytes": _MAX_REVIEW_UNIT_BYTES,
        "max_upstream_bridge_bytes": _MAX_UPSTREAM_BRIDGE_BYTES,
        "max_upstream_result_bytes": _MAX_UPSTREAM_RESULT_BYTES,
        "max_upstream_unreviewed_bytes": _MAX_UPSTREAM_UNREVIEWED_BYTES,
        "max_assignment_bytes": _MAX_ASSIGNMENT_BYTES,
        "max_private_map_bytes": _MAX_PRIVATE_MAP_BYTES,
        "max_blind_task_bytes": _MAX_BLIND_TASK_BYTES,
        "max_jsonl_line_bytes": _MAX_JSONL_LINE_BYTES,
        "max_instructions": _MAX_INSTRUCTIONS,
        "max_instruction_chars": _MAX_INSTRUCTION_CHARS,
        "max_text_chars": _MAX_TEXT_CHARS,
    },
    "chronology": [
        "upstream_unreviewed_inventory_seal",
        "presented_assignment_seal",
        "presented_campaign_precommit",
    ],
    "old_review_roster_assignment_result_receipt_inputs": [],
    "result_input_count": 0,
    "direct_io_capabilities": [],
    "private_signing_capabilities": [],
    **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    "actual_human_review_count": 0,
    "actual_human_unreviewed_input_count": EXPECTED_INPUT_COUNT,
    "actual_source_credit_count": 0,
    "actual_context_credit_count": 0,
    "metric_status": METRIC_STATUS,
    "gate_status": GATE_STATUS,
    "action_applied": False,
    "operational_effect": OPERATIONAL_EFFECT,
}
COMPONENT_MANIFEST_SHA256 = canonical_sha256(COMPONENT_MANIFEST)


__all__ = [
    "ACTOR_ROW_SCHEMA", "ARTIFACT_FIELDS", "ASSIGNMENT_ROW_SCHEMA",
    "ASSIGNMENT_SLOTS", "BLIND_TASK_ROW_SCHEMA", "CAMPAIGN_PRECOMMIT_SCHEMA",
    "COMPONENT_MANIFEST", "COMPONENT_MANIFEST_SHA256", "COMPONENT_VERSION",
    "DISAGREEMENT_ADJUDICATOR_RESERVE", "EXPECTED_INPUT_COUNT", "GATE_STATUS",
    "GUIDELINE_SCHEMA", "MAX_REVIEWERS", "METRIC_STATUS", "MIN_REVIEWERS",
    "P0PresentedDualBlindReviewCampaignPrecommitV1Error", "PRIMARY_A", "PRIMARY_B",
    "PRIMARY_ASSIGNMENT_COUNT", "PRIVATE_MAP_ROW_SCHEMA", "RECEIPT_SCHEMA",
    "RESERVE_ASSIGNMENT_COUNT", "RESPONSE_SCHEMA_SCHEMA",
    "REVIEW_GUIDELINE_INSTRUCTIONS", "TOTAL_ASSIGNMENT_COUNT",
    "build_assignment_inventory_bytes", "build_campaign_precommit_bytes",
    "build_evaluator_private_map_bytes",
    "build_key_pin_inventory_and_actor_roster_bytes", "build_review_guideline_bytes",
    "build_review_response_schema_bytes", "build_reviewer_facing_task_inventory_bytes",
    "canonical_bytes", "canonical_file_bytes", "canonical_sha256", "raw_sha256",
    "validate_presented_dual_blind_review_campaign_precommit_bundle",
]
