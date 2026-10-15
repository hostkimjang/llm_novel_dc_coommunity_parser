"""Independent parent replay for the presented dual-blind precommit v1.

The producer contract is intentionally not imported.  This module parses every
presented artifact again, rebuilds the forty review units through the standalone
upstream parent, recomputes every local projection, and delegates only the
domain-separated P-256 verification to the standalone signature-math parent.
Success remains structural, result-free, and non-authoritative.
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

from . import p0_presented_batch_exact_accounting_v1_parent_validator as batch_parent
from . import p0_presented_neutral_review_signature_math_v1_parent_validator as signature_parent


COMPONENT_VERSION = "presented-dual-blind-review-campaign-precommit-v1"
GUIDELINE_SCHEMA = "p0_presented_dual_blind_review_guideline_v1"
RESPONSE_SCHEMA_SCHEMA = "p0_presented_dual_blind_review_response_schema_v1"
ACTOR_ROW_SCHEMA = "p0_presented_dual_blind_review_actor_row_v1"
ASSIGNMENT_ROW_SCHEMA = "p0_presented_dual_blind_review_assignment_row_v1"
PRIVATE_MAP_ROW_SCHEMA = "p0_presented_dual_blind_review_private_map_row_v1"
BLIND_TASK_ROW_SCHEMA = "p0_presented_dual_blind_review_task_row_v1"
CAMPAIGN_PRECOMMIT_SCHEMA = "p0_presented_dual_blind_review_campaign_precommit_v1"
RECEIPT_SCHEMA = "p0_presented_dual_blind_review_campaign_precommit_receipt_v1"
PARENT_RECEIPT_SCHEMA = "p0_presented_dual_blind_review_campaign_precommit_parent_receipt_v1"

RECORD_ORIGIN = "ACTUAL_SCHEMA_CONTRACT_EXAMPLE_ONLY"
OPERATIONAL_EFFECT = "NONE_SHADOW_ONLY"
GATE_STATUS = "NO_GO_PRESENTED_DUAL_BLIND_REVIEW_CAMPAIGN_PRECOMMIT_ONLY"
PARENT_GATE_STATUS = "NO_GO_INDEPENDENT_PRESENTED_DUAL_BLIND_PRECOMMIT_REPLAY_ONLY"
METRIC_STATUS = "NOT_ESTIMABLE_EXTERNAL_REVIEW_AUTHORITY_ABSENT"

EXPECTED_INPUT_COUNT = 40
PRIMARY_ASSIGNMENT_COUNT = 80
RESERVE_ASSIGNMENT_COUNT = 40
TOTAL_ASSIGNMENT_COUNT = 120
MIN_REVIEWERS = 3
MAX_REVIEWERS = 16
EXPECTED_COMPONENT_MANIFEST_SHA256 = (
    "9b48da05a67eae4db3190c6443cb949462c53a799309a862818693cd9366c302"
)
_UPSTREAM_REVIEW_COMPONENT_MANIFEST_SHA256 = (
    "05ea2cf7301c770b6f3ead9e894df59d447523a1964b85a72bb68f0f1a63ef76"
)

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

CAMPAIGN_POLICY_PREAUTHORIZATION = "CAMPAIGN_POLICY_PREAUTHORIZATION"
REVIEW_LEASE = "REVIEW_LEASE"
HUMAN_REVIEW_RESULT = "HUMAN_REVIEW_RESULT"
FINAL_REVIEW_ATTESTATION = "FINAL_REVIEW_ATTESTATION"
_SIGNATURE_PROFILES: dict[str, tuple[str, str, str]] = {
    CAMPAIGN_POLICY_PREAUTHORIZATION: (
        "REVIEW_POLICY_PREAUTH_SIGNING_ONLY",
        "P0_NEUTRAL_REVIEW_CAMPAIGN_POLICY_PREAUTHORIZATION",
        "llm-novel-dc-community-parser/p0-neutral-review-policy-preauth-signature/v1",
    ),
    REVIEW_LEASE: (
        "REVIEW_LEASE_SIGNING_ONLY",
        "P0_NEUTRAL_REVIEW_LEASE",
        "llm-novel-dc-community-parser/p0-neutral-review-lease-signature/v1",
    ),
    HUMAN_REVIEW_RESULT: (
        "HUMAN_REVIEW_RESULT_SIGNING_ONLY",
        "P0_NEUTRAL_HUMAN_REVIEW_RESULT",
        "llm-novel-dc-community-parser/p0-neutral-human-review-result-signature/v1",
    ),
    FINAL_REVIEW_ATTESTATION: (
        "REVIEW_FINAL_ATTESTATION_SIGNING_ONLY",
        "P0_NEUTRAL_REVIEW_FINAL_ATTESTATION",
        "llm-novel-dc-community-parser/p0-neutral-review-final-attestation-signature/v1",
    ),
}

_MAX_OBJECT_BYTES = 1024 * 1024
_MAX_GUIDELINE_BYTES = 128 * 1024
_MAX_PIN_LINE_BYTES = 16 * 1024
_MAX_PIN_INVENTORY_BYTES = 512 * 1024
_MAX_ROSTER_BYTES = 512 * 1024
_MAX_REVIEW_UNIT_BYTES = 32 * 1024 * 1024
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

_PIN_FIELDS = frozenset({
    "schema_version", "record_origin", "component_version", "signature_kind",
    "trust_domain", "project_id", "environment", "purpose", "key_role",
    "key_id", "key_epoch", "algorithm", "curve", "cng_provider",
    "coordinate_encoding", "fingerprint_encoding", "public_key_x_base64",
    "public_key_y_base64", "public_key_fingerprint_sha256",
    "signer_principal_commitment_sha256", "authority_anchor_sha256",
    "allowed_signature_domains", "presented_revocation_snapshot_raw_sha256",
    "artifact_sha256",
})
_GUIDELINE_FIELDS = frozenset({
    "schema_version", "record_origin", "component_version", "campaign_id",
    "guideline_id", "guideline_version", "review_scope", "reviewer_visibility",
    "parser_projection_release_stage", "semantic_target_decision_policy",
    "instructions", "presented_policy_only", "action_applied",
    "operational_effect", "artifact_sha256",
})
_RESPONSE_SCHEMA_FIELDS = frozenset({
    "schema_version", "record_origin", "component_version", "campaign_id",
    "response_schema_id", "terminal_statuses", "required_response_fields",
    "full_payload_gold_set_requirement", "primary_result_mutability_policy",
    "canonical_gold_set_comparison_profile", "terminal_field_semantics",
    "presented_policy_only", "action_applied", "operational_effect",
    "artifact_sha256",
})
_ACTOR_FIELDS = frozenset({
    "schema_version", "actor_sequence", "actor_kind", "actor_id",
    "declared_independence_group_id", "pin_sequence", "pin_raw_bytes",
    "pin_raw_sha256", "pin_artifact_sha256", "signature_kind", "key_role",
    "purpose", "domain", "key_id", "key_epoch",
    "public_key_fingerprint_sha256", "signer_principal_commitment_sha256",
    "actor_row_sha256",
})
_ASSIGNMENT_FIELDS = frozenset({
    "schema_version", "assignment_sequence", "campaign_id", "run_id",
    "input_sequence", "assignment_slot", "reviewer_id",
    "reviewer_pin_raw_sha256", "reviewer_key_id", "reviewer_key_epoch",
    "reviewer_public_key_fingerprint_sha256",
    "reviewer_principal_commitment_sha256", "reviewer_independence_group_id",
    "opaque_task_id", "assignment_row_sha256",
})
_REVIEW_UNIT_FIELDS = frozenset({
    "schema_version", "review_unit_sequence", "input_sequence",
    "frame_candidate_id", "registry_record_id", "selected_input_sha256",
    "bridge_row_sha256", "payload_base64", "payload_bytes", "payload_sha256",
    "result_row_sha256", "parser_terminal_disposition",
    "full_payload_missed_span_unit_sha256", "emitted_observation_subjects",
    "emitted_observation_subjects_sha256", "emitted_observation_count",
    "input_review_unit_sha256",
})
_UPSTREAM_BRIDGE_FIELDS = frozenset({
    "schema_version", "input_sequence", "candidate_id",
    "locator_commitment_sha256", "lineage_group_id", "lineage_unit_sha256",
    "adapter_id", "source_profile", "platform", "utc_day", "stratum_id",
    "selected_input_sha256", "registry_record_id",
    "registry_record_commitment_sha256", "content_type", "capture_version",
    "normalization_version", "payload_base64", "payload_bytes",
    "payload_sha256", "bridge_row_sha256",
})
_UPSTREAM_RESULT_FIELDS = frozenset({
    "schema_version", "input_sequence", "frame_candidate_id",
    "registry_record_id", "registry_record_commitment_sha256", "source_profile",
    "selected_input_sha256", "bridge_row_sha256", "payload_sha256",
    "attempt_count", "retry_performed", "replacement_performed",
    "terminal_disposition", "core_result", "core_result_sha256",
    "core_observations_sha256", "observation_count", "core_error_stage",
    "core_error_code", "core_error_presented_only", "result_row_sha256",
})
_UPSTREAM_FALSE_AUTHORITY_FIELDS = (
    "external_population_completeness_verified", "external_owner_authority_verified",
    "external_registry_authority_verified", "external_capture_authority_verified",
    "trusted_time_verified", "hidden_retry_absence_verified",
    "core_error_factuality_verified", "code_identity_verified",
    "dependency_closure_verified", "process_isolation_verified",
    "runtime_execution_authority_verified", "route_packet_ledger_credit_verified",
    "actual_source_evidence_verified", "actual_authority_granted", "p0_phase_exit",
    "production_approval", "full_scan_approval",
)
_UPSTREAM_UNREVIEWED_FIELDS = frozenset({
    "schema_version", "record_origin", "component_version",
    "batch_receipt_raw_sha256", "batch_receipt_artifact_sha256",
    "results_raw_sha256", "contextual_observation_review_units",
    "contextual_observation_review_units_sha256", "contextual_observation_count",
    "full_payload_missed_span_review_units",
    "full_payload_missed_span_review_units_sha256",
    "full_payload_missed_span_input_count",
    "human_reviewed_contextual_observation_count",
    "human_reviewed_full_payload_input_count",
    "unreviewed_contextual_observation_count",
    "unreviewed_full_payload_input_count", "review_inventory_sealed_at",
    "exhaustive_human_review_verified", *_UPSTREAM_FALSE_AUTHORITY_FIELDS,
    "gate_status", "action_applied", "operational_effect", "artifact_sha256",
})
_PRIVATE_MAP_FIELDS = frozenset({
    "schema_version", "map_sequence", "campaign_id", "run_id",
    "input_sequence", "assignment_slot", "opaque_task_id", "reviewer_id",
    "reviewer_pin_raw_sha256", "reviewer_key_id", "reviewer_key_epoch",
    "reviewer_public_key_fingerprint_sha256",
    "reviewer_principal_commitment_sha256", "reviewer_independence_group_id",
    "assignment_row_sha256", "input_review_unit_sha256", "frame_candidate_id",
    "registry_record_id", "selected_input_sha256", "bridge_row_sha256",
    "payload_base64", "payload_bytes", "payload_sha256",
    "parser_result_row_sha256", "parser_terminal_disposition",
    "full_payload_missed_span_unit_sha256",
    "emitted_observation_subjects_sha256", "emitted_observation_count",
    "private_map_row_sha256",
})
_BLIND_TASK_FIELDS = frozenset({
    "schema_version", "task_sequence", "campaign_id", "run_id",
    "opaque_task_id", "payload_base64", "payload_bytes", "payload_sha256",
    "review_guideline_raw_sha256", "review_guideline_artifact_sha256",
    "response_schema_raw_sha256", "response_schema_artifact_sha256",
    "blind_task_row_sha256",
})
_PRECOMMIT_FIELDS = frozenset({
    "schema_version", "record_origin", "component_version", "campaign_id",
    "run_id", "trust_domain", "project_id", "environment",
    "component_manifest_sha256",
    "upstream_review_component_manifest_sha256",
    "upstream_sampling_plan_raw_sha256", "upstream_bridge_inventory_raw_sha256",
    "upstream_batch_precommit_raw_sha256", "upstream_parser_results_raw_sha256",
    "upstream_batch_receipt_raw_sha256",
    "upstream_unreviewed_inventory_raw_sha256",
    "upstream_review_unit_inventory_raw_sha256",
    "upstream_review_unit_inventory_sha256", "review_guideline_raw_sha256",
    "review_guideline_artifact_sha256", "response_schema_raw_sha256",
    "response_schema_artifact_sha256", "key_pin_inventory_raw_sha256",
    "key_pin_count", "actor_roster_raw_sha256", "actor_count", "reviewer_count",
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
})
_SIGNATURE_SUBJECT_FIELDS = frozenset({
    "schema_version", "record_origin", "component_version", "signature_kind",
    "domain", "trust_domain", "project_id", "environment", "purpose",
    "key_role", "campaign_id", "run_id", "subject_id", "presented_issued_at",
    "nonce_commitment_sha256", "payload_schema", "payload_bytes",
    "payload_raw_sha256", "payload_artifact_sha256",
    "predecessor_subject_raw_sha256", "caller_presented_subject_only",
    "external_authority_claimed", "actual_human_review_claimed",
    "semantic_promotion_claimed", "action_applied", "operational_effect",
    "artifact_sha256",
})

_FALSE_AUTHORITY_FIELDS = (
    "external_key_provisioning_verified", "external_authority_anchor_verified",
    "reviewer_identity_verified", "reviewer_independence_factuality_verified",
    "reviewer_blinding_verified", "reviewer_dispatch_isolation_verified",
    "mapping_confidentiality_verified", "opaque_identifier_unpredictability_verified",
    "trusted_time_verified", "revocation_state_verified",
    "durable_replay_prevention_verified", "lease_signature_verified",
    "final_attestation_signature_verified", "human_judgment_factuality_verified",
    "gold_span_semantic_factuality_verified", "actual_human_review_verified",
    "primary_result_inventory_verified", "all_80_primary_terminals_verified",
    "all_40_pairs_complete_verified", "disagreement_inventory_verified",
    "required_adjudication_complete_verified", "final_40_judged_verified",
    "actual_source_evidence_verified", "metric_eligibility_verified",
    "descriptive_quality_metrics_allowed", "inferential_metrics_allowed",
    "complete_case_metrics_allowed", "semantic_metrics_allowed",
    "actual_authority_granted", "p0_phase_exit", "production_approval",
    "full_scan_approval",
)


class P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(ValueError):
    """Independent parent rejected the presented precommit bundle."""


def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, RecursionError) as exc:
        raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
            "value is not canonical JSON data"
        ) from exc


def _file(value: Any) -> bytes:
    return _canonical(value) + b"\n"


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _raw_digest(raw: bytes) -> str:
    if type(raw) is not bytes:
        raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
            "raw value must be bytes"
        )
    return hashlib.sha256(raw).hexdigest()


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
                "duplicate JSON key is forbidden"
            )
        value[key] = item
    return value


def _constant(token: str) -> None:
    raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
        f"non-finite JSON constant is forbidden: {token}"
    )


def _object(raw: bytes, label: str, *, maximum: int = _MAX_OBJECT_BYTES) -> dict[str, Any]:
    if (
        type(raw) is not bytes or not raw or len(raw) > maximum
        or raw.startswith(b"\xef\xbb\xbf") or b"\r" in raw
        or not raw.endswith(b"\n") or raw.count(b"\n") != 1
    ):
        raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
            f"{label} framing is invalid"
        )
    try:
        value = json.loads(
            raw.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_constant
        )
    except P0PresentedDualBlindReviewCampaignPrecommitV1ParentError:
        raise
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
            f"{label} must be strict UTF-8 JSON"
        ) from exc
    if type(value) is not dict or raw != _file(value):
        raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
            f"{label} must be one canonical object plus LF"
        )
    return value


def _jsonl(
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
        raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
            f"{label} framing is invalid"
        )
    lines = raw.splitlines(keepends=True)
    if not lines or any(line == b"\n" or len(line) > line_maximum for line in lines):
        raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
            f"{label} line inventory is invalid"
        )
    rows = [
        _object(line, f"{label} row {index}", maximum=line_maximum)
        for index, line in enumerate(lines, start=1)
    ]
    if b"".join(_file(row) for row in rows) != raw:
        raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
            f"{label} is not canonical JSONL"
        )
    return rows, lines


def _strict(value: Any, fields: frozenset[str], label: str) -> dict[str, Any]:
    if type(value) is not dict or frozenset(value) != fields:
        raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
            f"{label} field inventory mismatch"
        )
    return dict(value)


def _sha(value: Any, label: str) -> str:
    if type(value) is not str or _SHA_RE.fullmatch(value) is None:
        raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
            f"{label} must be lowercase SHA-256"
        )
    return value


def _identifier(value: Any, label: str) -> str:
    if type(value) is not str or _ID_RE.fullmatch(value) is None:
        raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
            f"{label} is invalid"
        )
    return value


def _opaque_id(value: Any, label: str) -> str:
    if type(value) is not str or _OPAQUE_ID_RE.fullmatch(value) is None:
        raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
            f"{label} must be a 256-bit lowercase hexadecimal identifier"
        )
    return value


def _integer(value: Any, label: str, minimum: int = 0, maximum: int | None = None) -> int:
    if (
        isinstance(value, bool) or not isinstance(value, int) or value < minimum
        or (maximum is not None and value > maximum)
    ):
        raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
            f"{label} is outside the integer contract"
        )
    return value


def _text(value: Any, label: str, *, maximum: int = _MAX_TEXT_CHARS) -> str:
    if (
        type(value) is not str or not value or len(value) > maximum
        or "\r" in value or "\x00" in value
        or unicodedata.normalize("NFC", value) != value
    ):
        raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
            f"{label} is invalid"
        )
    return value


def _time(value: Any, label: str) -> datetime:
    if type(value) is not str or _TIME_RE.fullmatch(value) is None:
        raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
            f"{label} must be second-precision UTC"
        )
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError as exc:
        raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
            f"{label} is not a real UTC timestamp"
        ) from exc
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
        raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
            f"{label} is not canonical UTC"
        )
    return parsed


def _self_hash(
    row: Mapping[str, Any], field: str, label: str, *, domain: str | None = None
) -> str:
    stored = _sha(row.get(field), f"{label}.{field}")
    material = {key: value for key, value in row.items() if key != field}
    digest_material: Any = (
        material
        if domain is None
        else {"self_hash_domain": domain, "self_hash_material": material}
    )
    if not hmac.compare_digest(stored, _digest(digest_material)):
        raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
            f"{label} self-hash mismatch"
        )
    return stored


def _decode_base64(value: Any, *, length: int | None, label: str) -> bytes:
    if type(value) is not str or not value or any(char.isspace() for char in value):
        raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
            f"{label} must be canonical base64"
        )
    try:
        decoded = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
            f"{label} must be canonical base64"
        ) from exc
    if (
        (length is not None and len(decoded) != length)
        or base64.b64encode(decoded).decode("ascii") != value
    ):
        raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
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
        raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
            "presented public key is not a P-256 affine point"
        )


def _profile(kind: Any) -> tuple[str, str, str]:
    if type(kind) is not str or kind not in _SIGNATURE_PROFILES:
        raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
            "signature kind is invalid"
        )
    return _SIGNATURE_PROFILES[kind]


def _pin(row: Any, raw: bytes, index: int) -> dict[str, Any]:
    pin = _strict(row, _PIN_FIELDS, f"pin {index}")
    role, purpose, domain = _profile(pin["signature_kind"])
    if not (
        pin["schema_version"] == signature_parent.PUBLIC_KEY_PIN_SCHEMA
        and pin["record_origin"] == signature_parent.PRESENTED_PIN_ORIGIN
        and pin["component_version"] == signature_parent.COMPONENT_VERSION
        and pin["key_role"] == role and pin["purpose"] == purpose
        and pin["allowed_signature_domains"] == [domain]
        and pin["algorithm"] == signature_parent.ALGORITHM
        and pin["curve"] == signature_parent.CURVE
        and pin["cng_provider"] == signature_parent.CNG_PROVIDER
        and pin["coordinate_encoding"] == signature_parent.COORDINATE_ENCODING
        and pin["fingerprint_encoding"] == signature_parent.FINGERPRINT_ENCODING
    ):
        raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
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
    expected_fingerprint = hashlib.sha256(_P256_SPKI_PREFIX + x + y).hexdigest()
    if not hmac.compare_digest(expected_fingerprint, pin["public_key_fingerprint_sha256"]):
        raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
            "pin RFC 5480 fingerprint mismatch"
        )
    _self_hash(pin, "artifact_sha256", f"pin {index}")
    if raw != _file(pin):
        raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
            "pin exact raw line mismatch"
        )
    return pin


def _guideline(raw: bytes) -> dict[str, Any]:
    row = _strict(
        _object(raw, "review guideline", maximum=_MAX_GUIDELINE_BYTES),
        _GUIDELINE_FIELDS,
        "review guideline",
    )
    instructions = row["instructions"]
    if type(instructions) is not list or not 1 <= len(instructions) <= _MAX_INSTRUCTIONS:
        raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
            "guideline instruction inventory is invalid"
        )
    for index, item in enumerate(instructions, start=1):
        _text(item, f"guideline instruction {index}", maximum=_MAX_INSTRUCTION_CHARS)
    if not (
        row["schema_version"] == GUIDELINE_SCHEMA
        and row["record_origin"] == RECORD_ORIGIN
        and row["component_version"] == COMPONENT_VERSION
        and row["review_scope"] == "FULL_PAYLOAD_NEUTRAL_RELATION_EXTRACTION_ONLY"
        and row["reviewer_visibility"] == "PAYLOAD_GUIDELINE_AND_RESPONSE_SCHEMA_ONLY"
        and row["parser_projection_release_stage"] == "AFTER_BOTH_PRIMARY_RESULTS_FROZEN"
        and row["semantic_target_decision_policy"] == "FORBIDDEN"
        and instructions == list(REVIEW_GUIDELINE_INSTRUCTIONS)
        and row["presented_policy_only"] is True
        and row["action_applied"] is False
        and row["operational_effect"] == OPERATIONAL_EFFECT
    ):
        raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
            "guideline policy mismatch"
        )
    _identifier(row["campaign_id"], "guideline.campaign_id")
    _identifier(row["guideline_id"], "guideline.guideline_id")
    _integer(row["guideline_version"], "guideline.guideline_version", 1)
    _self_hash(row, "artifact_sha256", "review guideline")
    return row


def _response_schema(raw: bytes) -> dict[str, Any]:
    row = _strict(_object(raw, "response schema"), _RESPONSE_SCHEMA_FIELDS, "response schema")
    _identifier(row["campaign_id"], "response.campaign_id")
    _identifier(row["response_schema_id"], "response.response_schema_id")
    fixed = {
        "schema_version": RESPONSE_SCHEMA_SCHEMA,
        "record_origin": RECORD_ORIGIN,
        "component_version": COMPONENT_VERSION,
        "campaign_id": row["campaign_id"],
        "response_schema_id": row["response_schema_id"],
        "terminal_statuses": ["JUDGED", "UNAVAILABLE", "UNJUDGED"],
        "required_response_fields": [
            "opaque_task_id", "annotation_status", "terminal_reason_code",
            "reviewed_at", "presented_gold_spans", "reviewer_note_commitment_sha256",
        ],
        "full_payload_gold_set_requirement": "COMPLETE_SET_OR_NONJUDGED_TERMINAL",
        "primary_result_mutability_policy": "IMMUTABLE_AFTER_FIRST_VALID_SIGNATURE",
        "canonical_gold_set_comparison_profile": {
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
        },
        "terminal_field_semantics": {
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
        },
        "presented_policy_only": True,
        "action_applied": False,
        "operational_effect": OPERATIONAL_EFFECT,
    }
    expected = {**fixed, "artifact_sha256": _digest(fixed)}
    if row != expected or raw != _file(expected):
        raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
            "response schema exact fixed contract mismatch"
        )
    return row


def _pins_and_roster(
    pin_inventory_raw: bytes, roster_raw: bytes
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    pin_values, pin_lines = _jsonl(
        pin_inventory_raw, "key pin inventory", maximum=_MAX_PIN_INVENTORY_BYTES,
        line_maximum=_MAX_PIN_LINE_BYTES,
    )
    actor_values, _ = _jsonl(roster_raw, "actor roster", maximum=_MAX_ROSTER_BYTES)
    if not MIN_REVIEWERS + 3 <= len(pin_values) == len(actor_values) <= MAX_REVIEWERS + 3:
        raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
            "pin/actor count mismatch"
        )
    kinds = [
        CAMPAIGN_POLICY_PREAUTHORIZATION, REVIEW_LEASE, FINAL_REVIEW_ATTESTATION,
        *([HUMAN_REVIEW_RESULT] * (len(pin_values) - 3)),
    ]
    actor_ids: set[str] = set()
    singleton_groups: set[str] = set()
    key_ids: set[str] = set()
    fingerprints: set[str] = set()
    principals: set[str] = set()
    pin_hashes: set[str] = set()
    scope: tuple[str, str, str] | None = None
    revocation: str | None = None
    authority_anchor: str | None = None
    pins: list[dict[str, Any]] = []
    actors: list[dict[str, Any]] = []
    singleton_ids = ("CAMPAIGN_POLICY_SIGNER", "REVIEW_LEASE_SIGNER", "FINAL_REVIEW_ATTESTER")
    for index, (pin_value, pin_raw, actor_value, kind) in enumerate(
        zip(pin_values, pin_lines, actor_values, kinds, strict=True), start=1
    ):
        pin = _pin(pin_value, pin_raw, index)
        actor = _strict(actor_value, _ACTOR_FIELDS, f"actor {index}")
        role, purpose, domain = _profile(kind)
        expected = {
            "schema_version": ACTOR_ROW_SCHEMA,
            "actor_sequence": index,
            "actor_kind": "SINGLETON_ROLE" if index <= 3 else "HUMAN_REVIEWER",
            "actor_id": singleton_ids[index - 1] if index <= 3 else actor["actor_id"],
            "pin_sequence": index,
            "pin_raw_bytes": len(pin_raw),
            "pin_raw_sha256": _raw_digest(pin_raw),
            "pin_artifact_sha256": pin["artifact_sha256"],
            "signature_kind": kind,
            "key_role": role,
            "purpose": purpose,
            "domain": domain,
            "key_id": pin["key_id"],
            "key_epoch": pin["key_epoch"],
            "public_key_fingerprint_sha256": pin["public_key_fingerprint_sha256"],
            "signer_principal_commitment_sha256": pin["signer_principal_commitment_sha256"],
        }
        if pin["signature_kind"] != kind or any(actor[field] != value for field, value in expected.items()):
            raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
                "actor/exact pin projection mismatch"
            )
        actor_id = _identifier(actor["actor_id"], "actor ID")
        group = _identifier(actor["declared_independence_group_id"], "actor group")
        if actor_id in actor_ids:
            raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
                "actor IDs must be globally distinct"
            )
        actor_ids.add(actor_id)
        if index <= 3:
            if group in singleton_groups:
                raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
                    "singleton groups must be distinct"
                )
            singleton_groups.add(group)
        elif group in singleton_groups:
            raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
                "reviewer group conflicts with a singleton role"
            )
        for seen, value in (
            (key_ids, pin["key_id"]),
            (fingerprints, pin["public_key_fingerprint_sha256"]),
            (principals, pin["signer_principal_commitment_sha256"]),
            (pin_hashes, _raw_digest(pin_raw)),
        ):
            if value in seen:
                raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
                    "global key/pin/principal separation failed"
                )
            seen.add(value)
        current_scope = (pin["trust_domain"], pin["project_id"], pin["environment"])
        if scope is None:
            scope = current_scope
            revocation = pin["presented_revocation_snapshot_raw_sha256"]
            authority_anchor = pin["authority_anchor_sha256"]
        elif (
            current_scope != scope
            or pin["presented_revocation_snapshot_raw_sha256"] != revocation
            or pin["authority_anchor_sha256"] != authority_anchor
        ):
            raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
                "pin campaign scope/authority-anchor/revocation mismatch"
            )
        _self_hash(
            actor, "actor_row_sha256", f"actor {index}",
            domain="P0_DUAL_BLIND_REVIEW_ACTOR_ROW_V1",
        )
        pins.append(pin)
        actors.append(actor)
    return pins, actors


def _review_units_from_upstream(
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
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    try:
        batch_parent_receipt = batch_parent.validate_batch_bundle_against_raw_inputs(
            sampling_plan_raw=sampling_plan_raw,
            expected_sampling_plan_raw_sha256=expected_sampling_plan_raw_sha256,
            bridge_inventory_raw=bridge_inventory_raw,
            batch_precommit_raw=batch_precommit_raw,
            expected_precommit_raw_sha256=expected_batch_precommit_raw_sha256,
            results_raw=parser_results_raw,
            batch_receipt_raw=batch_receipt_raw,
            unreviewed_inventory_raw=unreviewed_inventory_raw,
        )
    except Exception as exc:
        raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
            "standalone upstream parent rejected plan-to-review-unit lineage"
        ) from exc
    bridge_values, _ = _jsonl(
        bridge_inventory_raw, "upstream bridge inventory",
        maximum=_MAX_UPSTREAM_BRIDGE_BYTES,
    )
    result_values, _ = _jsonl(
        parser_results_raw, "upstream parser results",
        maximum=_MAX_UPSTREAM_RESULT_BYTES,
    )
    unreviewed = _strict(
        _object(
            unreviewed_inventory_raw, "upstream unreviewed inventory",
            maximum=_MAX_UPSTREAM_UNREVIEWED_BYTES,
        ),
        _UPSTREAM_UNREVIEWED_FIELDS,
        "upstream unreviewed inventory",
    )
    if len(bridge_values) != EXPECTED_INPUT_COUNT or len(result_values) != EXPECTED_INPUT_COUNT:
        raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
            "upstream bridge/result count mismatch"
        )
    bridges = [
        _strict(value, _UPSTREAM_BRIDGE_FIELDS, f"upstream bridge {index}")
        for index, value in enumerate(bridge_values, start=1)
    ]
    results = [
        _strict(value, _UPSTREAM_RESULT_FIELDS, f"upstream result {index}")
        for index, value in enumerate(result_values, start=1)
    ]
    contextual_by_input: dict[int, list[Mapping[str, Any]]] = {}
    contextual = unreviewed["contextual_observation_review_units"]
    missed = unreviewed["full_payload_missed_span_review_units"]
    if type(contextual) is not list or type(missed) is not list or len(missed) != EXPECTED_INPUT_COUNT:
        raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
            "upstream unreviewed review universe shape mismatch"
        )
    for value in contextual:
        if type(value) is not dict:
            raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
                "contextual review unit must be an object"
            )
        input_sequence = _integer(
            value.get("input_sequence"), "contextual input sequence", 1,
            EXPECTED_INPUT_COUNT,
        )
        contextual_by_input.setdefault(input_sequence, []).append(value)
    missed_by_input: dict[int, Mapping[str, Any]] = {}
    for value in missed:
        if type(value) is not dict:
            raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
                "missed-span review unit must be an object"
            )
        input_sequence = _integer(
            value.get("input_sequence"), "missed-span input sequence", 1,
            EXPECTED_INPUT_COUNT,
        )
        if input_sequence in missed_by_input:
            raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
                "missed-span input sequence duplicate"
            )
        missed_by_input[input_sequence] = value
    expected_units: list[dict[str, Any]] = []
    for index, (bridge, result) in enumerate(zip(bridges, results, strict=True), start=1):
        if (
            _integer(bridge["input_sequence"], "bridge input sequence", 1) != index
            or _integer(result["input_sequence"], "result input sequence", 1) != index
        ):
            raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
                "upstream physical order mismatch"
            )
        core = result["core_result"]
        observations = [] if core is None else core.get("observations")
        if type(observations) is not list:
            raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
                "upstream observations must be a list"
            )
        contextual_rows = contextual_by_input.get(index, [])
        if len(contextual_rows) != len(observations) or index not in missed_by_input:
            raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
                "review-unit upstream review-universe mismatch"
            )
        subjects: list[dict[str, Any]] = []
        for contextual_row, observation in zip(contextual_rows, observations, strict=True):
            if type(observation) is not dict:
                raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
                    "upstream observation must be an object"
                )
            subjects.append({
                "contextual_observation_unit_sha256": contextual_row[
                    "contextual_observation_unit_sha256"
                ],
                **observation,
            })
        material = {
            "schema_version": "p0_presented_neutral_input_review_unit_v1",
            "review_unit_sequence": index,
            "input_sequence": index,
            "frame_candidate_id": bridge["candidate_id"],
            "registry_record_id": bridge["registry_record_id"],
            "selected_input_sha256": bridge["selected_input_sha256"],
            "bridge_row_sha256": bridge["bridge_row_sha256"],
            "payload_base64": bridge["payload_base64"],
            "payload_bytes": bridge["payload_bytes"],
            "payload_sha256": bridge["payload_sha256"],
            "result_row_sha256": result["result_row_sha256"],
            "parser_terminal_disposition": result["terminal_disposition"],
            "full_payload_missed_span_unit_sha256": missed_by_input[index][
                "full_payload_missed_span_unit_sha256"
            ],
            "emitted_observation_subjects": subjects,
            "emitted_observation_subjects_sha256": _digest(subjects),
            "emitted_observation_count": len(subjects),
        }
        expected_units.append({
            **material,
            "input_review_unit_sha256": _digest({
                "domain": "P0_PRESENTED_NEUTRAL_INPUT_REVIEW_UNIT_V1", **material
            }),
        })
    if review_unit_inventory_raw != b"".join(_file(row) for row in expected_units):
        raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
            "review-unit inventory differs from independent upstream rebuild"
        )
    rows, _ = _jsonl(
        review_unit_inventory_raw, "review-unit inventory",
        maximum=_MAX_REVIEW_UNIT_BYTES,
    )
    if len(rows) != EXPECTED_INPUT_COUNT:
        raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
            "review-unit inventory must contain exactly 40 rows"
        )
    for index, row_value in enumerate(rows, start=1):
        row = _strict(row_value, _REVIEW_UNIT_FIELDS, f"review unit {index}")
        if (
            row["schema_version"] != "p0_presented_neutral_input_review_unit_v1"
            or _integer(row["review_unit_sequence"], "review unit sequence", 1) != index
            or _integer(row["input_sequence"], "input sequence", 1) != index
            or row != expected_units[index - 1]
        ):
            raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
                "review-unit exact replay mismatch"
            )
        payload = _decode_base64(row["payload_base64"], length=None, label="review payload")
        if (
            len(payload) != _integer(row["payload_bytes"], "payload bytes")
            or _raw_digest(payload) != _sha(row["payload_sha256"], "payload SHA")
            or type(row["emitted_observation_subjects"]) is not list
            or len(row["emitted_observation_subjects"])
            != _integer(row["emitted_observation_count"], "observation count")
            or _digest(row["emitted_observation_subjects"])
            != _sha(row["emitted_observation_subjects_sha256"], "observation SHA")
        ):
            raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
                "review-unit payload/parser projection mismatch"
            )
        stored_unit_sha = _sha(
            row["input_review_unit_sha256"], "review unit self-hash"
        )
        legacy_material = dict(row)
        legacy_material.pop("input_review_unit_sha256")
        if not hmac.compare_digest(
            stored_unit_sha,
            _digest({"domain": "P0_PRESENTED_NEUTRAL_INPUT_REVIEW_UNIT_V1", **legacy_material}),
        ):
            raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
                "review-unit self-hash mismatch"
            )
    return rows, unreviewed, batch_parent_receipt


def _assignments(
    raw: bytes,
    reviewers: Sequence[Mapping[str, Any]],
    *,
    campaign_id: str,
    run_id: str,
) -> list[dict[str, Any]]:
    rows, _ = _jsonl(raw, "assignment inventory", maximum=_MAX_ASSIGNMENT_BYTES)
    if len(rows) != TOTAL_ASSIGNMENT_COUNT:
        raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
            "assignment inventory must contain exactly 120 rows"
        )
    by_id = {row["actor_id"]: row for row in reviewers}
    if len(by_id) != len(reviewers):
        raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
            "reviewer actor ID duplicate"
        )
    opaque_ids: set[str] = set()
    validated: list[dict[str, Any]] = []
    for index, value in enumerate(rows, start=1):
        row = _strict(value, _ASSIGNMENT_FIELDS, f"assignment {index}")
        input_sequence = (index - 1) // 3 + 1
        slot = ASSIGNMENT_SLOTS[(index - 1) % 3]
        reviewer_id = _identifier(row["reviewer_id"], "assignment reviewer ID")
        reviewer = by_id.get(reviewer_id)
        if not (
            row["schema_version"] == ASSIGNMENT_ROW_SCHEMA
            and _integer(row["assignment_sequence"], "assignment sequence", 1) == index
            and row["campaign_id"] == campaign_id and row["run_id"] == run_id
            and _integer(row["input_sequence"], "input sequence", 1, EXPECTED_INPUT_COUNT)
            == input_sequence
            and row["assignment_slot"] == slot and reviewer is not None
        ):
            raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
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
            raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
                "assignment reviewer projection mismatch"
            )
        opaque = _opaque_id(row["opaque_task_id"], "assignment opaque task ID")
        if opaque in opaque_ids:
            raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
                "assignment opaque task ID duplicate"
            )
        opaque_ids.add(opaque)
        _self_hash(
            row, "assignment_row_sha256", f"assignment {index}",
            domain="P0_DUAL_BLIND_REVIEW_ASSIGNMENT_ROW_V1",
        )
        validated.append(row)
    for start in range(0, TOTAL_ASSIGNMENT_COUNT, 3):
        triad = validated[start:start + 3]
        for field in (
            "reviewer_id", "reviewer_pin_raw_sha256", "reviewer_key_id",
            "reviewer_public_key_fingerprint_sha256",
            "reviewer_principal_commitment_sha256", "reviewer_independence_group_id",
        ):
            if len({row[field] for row in triad}) != 3:
                raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
                    "assignment triad separation mismatch"
                )
    return validated


def _private_map(
    raw: bytes,
    units: Sequence[Mapping[str, Any]],
    assignments: Sequence[Mapping[str, Any]],
    *,
    campaign_id: str,
    run_id: str,
) -> list[dict[str, Any]]:
    rows, _ = _jsonl(raw, "evaluator-private map", maximum=_MAX_PRIVATE_MAP_BYTES)
    if len(rows) != TOTAL_ASSIGNMENT_COUNT:
        raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
            "evaluator-private map must contain exactly 120 rows"
        )
    validated: list[dict[str, Any]] = []
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
            raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
                "evaluator-private map projection mismatch"
            )
        _self_hash(
            row, "private_map_row_sha256", f"private map {index}",
            domain="P0_DUAL_BLIND_REVIEW_PRIVATE_MAP_ROW_V1",
        )
        validated.append(row)
    return validated


def _blind_tasks(
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
    rows, _ = _jsonl(raw, "reviewer-facing task inventory", maximum=_MAX_BLIND_TASK_BYTES)
    if len(rows) != TOTAL_ASSIGNMENT_COUNT or len(private_rows) != TOTAL_ASSIGNMENT_COUNT:
        raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
            "reviewer-facing task inventory must contain exactly 120 rows"
        )
    by_task_id: dict[str, Mapping[str, Any]] = {}
    for index, private in enumerate(private_rows, start=1):
        task_id = _opaque_id(
            private.get("opaque_task_id"), f"private map {index} opaque task ID"
        )
        if task_id in by_task_id:
            raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
                "evaluator-private opaque task ID duplicate"
            )
        by_task_id[task_id] = private
    if len(by_task_id) != TOTAL_ASSIGNMENT_COUNT:
        raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
            "evaluator-private opaque task ID duplicate"
        )
    order = sorted(by_task_id)
    validated: list[dict[str, Any]] = []
    for index, value in enumerate(rows, start=1):
        row = _strict(value, _BLIND_TASK_FIELDS, f"blind task {index}")
        if row["opaque_task_id"] != order[index - 1]:
            raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
                "reviewer-facing task inventory must use opaque-ID order"
            )
        private = by_task_id[row["opaque_task_id"]]
        expected = {
            "schema_version": BLIND_TASK_ROW_SCHEMA,
            "task_sequence": index,
            "campaign_id": campaign_id,
            "run_id": run_id,
            "opaque_task_id": private["opaque_task_id"],
            "payload_base64": private["payload_base64"],
            "payload_bytes": private["payload_bytes"],
            "payload_sha256": private["payload_sha256"],
            "review_guideline_raw_sha256": _raw_digest(guideline_raw),
            "review_guideline_artifact_sha256": guideline["artifact_sha256"],
            "response_schema_raw_sha256": _raw_digest(response_raw),
            "response_schema_artifact_sha256": response["artifact_sha256"],
        }
        if any(row[field] != expected_value for field, expected_value in expected.items()):
            raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
                "reviewer-facing task safe projection mismatch"
            )
        payload = _decode_base64(row["payload_base64"], length=None, label="blind task payload")
        if (
            len(payload) != _integer(row["payload_bytes"], "blind task payload bytes")
            or _raw_digest(payload) != row["payload_sha256"]
        ):
            raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
                "blind task payload binding mismatch"
            )
        _opaque_id(row["opaque_task_id"], "blind task opaque ID")
        _self_hash(
            row, "blind_task_row_sha256", f"blind task {index}",
            domain="P0_DUAL_BLIND_REVIEW_TASK_ROW_V1",
        )
        validated.append(row)
    return validated


def _policy_subject(
    raw: bytes, *, precommit_raw: bytes, precommit: Mapping[str, Any]
) -> dict[str, Any]:
    row = _strict(_object(raw, "policy signature subject"), _SIGNATURE_SUBJECT_FIELDS, "policy signature subject")
    role, purpose, domain = _profile(CAMPAIGN_POLICY_PREAUTHORIZATION)
    if not (
        row["schema_version"] == signature_parent.SUBJECT_SCHEMA
        and row["record_origin"] == signature_parent.PRESENTED_SUBJECT_ORIGIN
        and row["component_version"] == signature_parent.COMPONENT_VERSION
        and row["signature_kind"] == CAMPAIGN_POLICY_PREAUTHORIZATION
        and row["domain"] == domain and row["purpose"] == purpose and row["key_role"] == role
        and row["campaign_id"] == precommit["campaign_id"]
        and row["run_id"] == precommit["run_id"]
        and row["trust_domain"] == precommit["trust_domain"]
        and row["project_id"] == precommit["project_id"]
        and row["environment"] == precommit["environment"]
        and row["presented_issued_at"] == precommit["presented_campaign_precommitted_at"]
        and row["payload_schema"] == CAMPAIGN_PRECOMMIT_SCHEMA
        and row["payload_bytes"] == len(precommit_raw)
        and row["payload_raw_sha256"] == _raw_digest(precommit_raw)
        and row["payload_artifact_sha256"] == precommit["artifact_sha256"]
        and row["predecessor_subject_raw_sha256"] is None
        and row["caller_presented_subject_only"] is True
        and row["external_authority_claimed"] is False
        and row["actual_human_review_claimed"] is False
        and row["semantic_promotion_claimed"] is False
        and row["action_applied"] is False
        and row["operational_effect"] == OPERATIONAL_EFFECT
    ):
        raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
            "campaign-policy signature subject mismatch"
        )
    for field in (
        "trust_domain", "project_id", "environment", "campaign_id", "run_id",
        "subject_id", "payload_schema",
    ):
        _identifier(row[field], f"policy subject.{field}")
    _time(row["presented_issued_at"], "policy subject issued at")
    _sha(row["nonce_commitment_sha256"], "policy subject nonce")
    _self_hash(row, "artifact_sha256", "policy signature subject")
    return row


def validate_presented_dual_blind_review_campaign_precommit_against_raw_inputs(
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
    component_receipt_raw: bytes,
) -> dict[str, Any]:
    """Replay the complete result-free campaign bundle and exact child receipt."""

    _sha(expected_sampling_plan_raw_sha256, "expected sampling plan SHA")
    _sha(expected_batch_precommit_raw_sha256, "expected batch precommit SHA")
    if _raw_digest(sampling_plan_raw) != expected_sampling_plan_raw_sha256:
        raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
            "sampling plan expectation mismatch"
        )
    if _raw_digest(batch_precommit_raw) != expected_batch_precommit_raw_sha256:
        raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
            "batch precommit expectation mismatch"
        )
    precommit = _strict(
        _object(campaign_precommit_raw, "campaign precommit"),
        _PRECOMMIT_FIELDS,
        "campaign precommit",
    )
    campaign_id = _identifier(precommit["campaign_id"], "campaign_id")
    run_id = _identifier(precommit["run_id"], "run_id")
    trust_domain = _identifier(precommit["trust_domain"], "trust_domain")
    project_id = _identifier(precommit["project_id"], "project_id")
    environment = _identifier(precommit["environment"], "environment")
    units, unreviewed, batch_parent_receipt = _review_units_from_upstream(
        sampling_plan_raw=sampling_plan_raw,
        expected_sampling_plan_raw_sha256=expected_sampling_plan_raw_sha256,
        bridge_inventory_raw=bridge_inventory_raw,
        batch_precommit_raw=batch_precommit_raw,
        expected_batch_precommit_raw_sha256=expected_batch_precommit_raw_sha256,
        parser_results_raw=parser_results_raw,
        batch_receipt_raw=batch_receipt_raw,
        unreviewed_inventory_raw=unreviewed_inventory_raw,
        review_unit_inventory_raw=review_unit_inventory_raw,
    )
    guideline = _guideline(review_guideline_raw)
    response = _response_schema(response_schema_raw)
    pins, actors = _pins_and_roster(key_pin_inventory_raw, actor_roster_raw)
    if not (
        guideline["campaign_id"] == campaign_id
        and response["campaign_id"] == campaign_id
        and (pins[0]["trust_domain"], pins[0]["project_id"], pins[0]["environment"])
        == (trust_domain, project_id, environment)
    ):
        raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
            "campaign scope projection mismatch"
        )
    reviewers = actors[3:]
    assignments = _assignments(
        assignment_inventory_raw, reviewers, campaign_id=campaign_id, run_id=run_id
    )
    private_rows = _private_map(
        evaluator_private_map_raw, units, assignments,
        campaign_id=campaign_id, run_id=run_id,
    )
    tasks = _blind_tasks(
        reviewer_facing_task_inventory_raw, private_rows, guideline, response,
        guideline_raw=review_guideline_raw, response_raw=response_schema_raw,
        campaign_id=campaign_id, run_id=run_id,
    )
    upstream_sealed_at = _time(
        unreviewed.get("review_inventory_sealed_at"), "upstream review inventory seal"
    )
    assignment_sealed_at = _time(
        precommit["presented_assignment_sealed_at"], "assignment seal"
    )
    campaign_precommitted_at = _time(
        precommit["presented_campaign_precommitted_at"], "campaign precommit"
    )
    if not upstream_sealed_at < assignment_sealed_at < campaign_precommitted_at:
        raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
            "presented campaign chronology is invalid"
        )
    expected_precommit_material = {
        "schema_version": CAMPAIGN_PRECOMMIT_SCHEMA,
        "record_origin": RECORD_ORIGIN,
        "component_version": COMPONENT_VERSION,
        "campaign_id": campaign_id,
        "run_id": run_id,
        "trust_domain": trust_domain,
        "project_id": project_id,
        "environment": environment,
        "component_manifest_sha256": EXPECTED_COMPONENT_MANIFEST_SHA256,
        "upstream_review_component_manifest_sha256": _UPSTREAM_REVIEW_COMPONENT_MANIFEST_SHA256,
        "upstream_sampling_plan_raw_sha256": _raw_digest(sampling_plan_raw),
        "upstream_bridge_inventory_raw_sha256": _raw_digest(bridge_inventory_raw),
        "upstream_batch_precommit_raw_sha256": _raw_digest(batch_precommit_raw),
        "upstream_parser_results_raw_sha256": _raw_digest(parser_results_raw),
        "upstream_batch_receipt_raw_sha256": _raw_digest(batch_receipt_raw),
        "upstream_unreviewed_inventory_raw_sha256": _raw_digest(unreviewed_inventory_raw),
        "upstream_review_unit_inventory_raw_sha256": _raw_digest(review_unit_inventory_raw),
        "upstream_review_unit_inventory_sha256": _digest(units),
        "review_guideline_raw_sha256": _raw_digest(review_guideline_raw),
        "review_guideline_artifact_sha256": guideline["artifact_sha256"],
        "response_schema_raw_sha256": _raw_digest(response_schema_raw),
        "response_schema_artifact_sha256": response["artifact_sha256"],
        "key_pin_inventory_raw_sha256": _raw_digest(key_pin_inventory_raw),
        "key_pin_count": len(pins),
        "actor_roster_raw_sha256": _raw_digest(actor_roster_raw),
        "actor_count": len(actors),
        "reviewer_count": len(reviewers),
        "assignment_inventory_raw_sha256": _raw_digest(assignment_inventory_raw),
        "assignment_inventory_sha256": _digest(assignments),
        "evaluator_private_map_raw_sha256": _raw_digest(evaluator_private_map_raw),
        "evaluator_private_map_sha256": _digest(private_rows),
        "reviewer_facing_task_inventory_raw_sha256": _raw_digest(reviewer_facing_task_inventory_raw),
        "reviewer_facing_task_inventory_sha256": _digest(tasks),
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
        "review_protocol": {
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
        },
        "prior_presented_result_import_policy": "FORBIDDEN_NEW_CAMPAIGN_ONLY",
        "presented_assignment_sealed_at": precommit["presented_assignment_sealed_at"],
        "presented_campaign_precommitted_at": precommit["presented_campaign_precommitted_at"],
        "presented_policy_only": True,
        "action_applied": False,
        "operational_effect": OPERATIONAL_EFFECT,
    }
    expected_precommit = {
        **expected_precommit_material,
        "artifact_sha256": _digest(expected_precommit_material),
    }
    if precommit != expected_precommit or campaign_precommit_raw != _file(expected_precommit):
        raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
            "campaign precommit exact recomputation mismatch"
        )
    _policy_subject(
        policy_signature_subject_raw,
        precommit_raw=campaign_precommit_raw,
        precommit=precommit,
    )
    child = _object(component_receipt_raw, "component receipt")
    signature_receipt = child.get("policy_signature_math_receipt")
    if type(signature_receipt) is not dict:
        raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
            "component receipt signature receipt is invalid"
        )
    policy_pin_raw = key_pin_inventory_raw.splitlines(keepends=True)[0]
    try:
        signature_parent_receipt = (
            signature_parent.validate_presented_neutral_review_signature_math_against_raw_inputs(
                public_key_pin_raw=policy_pin_raw,
                subject_raw=policy_signature_subject_raw,
                payload_raw=campaign_precommit_raw,
                signature_envelope_raw=policy_signature_envelope_raw,
                component_receipt_raw=_file(signature_receipt),
                expected_signature_kind=CAMPAIGN_POLICY_PREAUTHORIZATION,
                expected_public_key_pin_raw_sha256=_raw_digest(policy_pin_raw),
                expected_subject_raw_sha256=_raw_digest(policy_signature_subject_raw),
            )
        )
    except Exception as exc:
        raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
            "independent campaign-policy signature replay rejected"
        ) from exc
    expected_child_material: dict[str, Any] = {
        "schema_version": RECEIPT_SCHEMA,
        "record_origin": RECORD_ORIGIN,
        "component_version": COMPONENT_VERSION,
        "campaign_id": campaign_id,
        "run_id": run_id,
        "component_manifest_sha256": EXPECTED_COMPONENT_MANIFEST_SHA256,
        "campaign_precommit_raw_sha256": _raw_digest(campaign_precommit_raw),
        "campaign_precommit_artifact_sha256": precommit["artifact_sha256"],
        "policy_signature_subject_raw_sha256": _raw_digest(policy_signature_subject_raw),
        "policy_signature_envelope_raw_sha256": _raw_digest(policy_signature_envelope_raw),
        "policy_signature_math_receipt": signature_receipt,
        "policy_signature_math_receipt_sha256": signature_receipt.get("receipt_sha256"),
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
        "reviewer_count": len(reviewers),
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
    expected_child = {
        **expected_child_material,
        "receipt_sha256": _digest(expected_child_material),
    }
    _strict(child, frozenset(expected_child), "component receipt")
    if child != expected_child:
        raise P0PresentedDualBlindReviewCampaignPrecommitV1ParentError(
            "component receipt differs from independent reconstruction"
        )
    parent_material: dict[str, Any] = {
        "schema_version": PARENT_RECEIPT_SCHEMA,
        "record_origin": RECORD_ORIGIN,
        "component_version": COMPONENT_VERSION,
        "expected_component_manifest_sha256": EXPECTED_COMPONENT_MANIFEST_SHA256,
        "component_receipt_raw_sha256": _raw_digest(component_receipt_raw),
        "component_receipt_sha256": child["receipt_sha256"],
        "campaign_precommit_raw_sha256": _raw_digest(campaign_precommit_raw),
        "campaign_precommit_artifact_sha256": precommit["artifact_sha256"],
        "signature_math_parent_receipt_sha256": signature_parent_receipt["receipt_sha256"],
        "batch_parent_receipt_sha256": batch_parent_receipt["receipt_sha256"],
        "upstream_parent_plan_to_review_unit_replay_verified": True,
        "parent_separate_implementation_raw_replay_verified": True,
        "parent_exact_child_receipt_projection_verified": True,
        "parent_imports_producer_contract": False,
        "presented_assignment_slot_count": TOTAL_ASSIGNMENT_COUNT,
        "effective_upstream_byte_bounds": {
            "bridge_inventory": _MAX_UPSTREAM_BRIDGE_BYTES,
            "parser_results": _MAX_UPSTREAM_RESULT_BYTES,
            "unreviewed_inventory": _MAX_UPSTREAM_UNREVIEWED_BYTES,
        },
        "selected_input_itt_denominator": EXPECTED_INPUT_COUNT,
        "planned_primary_review_opportunity_denominator": PRIMARY_ASSIGNMENT_COUNT,
        "primary_pair_input_denominator": EXPECTED_INPUT_COUNT,
        "maximum_reserve_adjudication_opportunity_denominator": RESERVE_ASSIGNMENT_COUNT,
        "planned_final_judged_input_denominator": EXPECTED_INPUT_COUNT,
        "required_adjudication_denominator": None,
        "required_adjudication_denominator_derivation": "AFTER_ALL_80_PRIMARY_TERMINALS_FROZEN_COUNT_BOTH_AUTHORITY_QUALIFIED_JUDGED_PAIRS_WITH_DIFFERENT_CANONICAL_FULL_GOLD_SETS",
        "actual_review_event_count": 0,
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
        "gate_status": PARENT_GATE_STATUS,
        "action_applied": False,
        "operational_effect": OPERATIONAL_EFFECT,
    }
    return {**parent_material, "receipt_sha256": _digest(parent_material)}


__all__ = [
    "P0PresentedDualBlindReviewCampaignPrecommitV1ParentError",
    "PARENT_GATE_STATUS",
    "PARENT_RECEIPT_SCHEMA",
    "validate_presented_dual_blind_review_campaign_precommit_against_raw_inputs",
]
