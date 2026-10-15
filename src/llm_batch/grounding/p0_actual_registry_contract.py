"""Actual-P0 source registry, B-sense, and annotation-journal foundation.

The module is deliberately disconnected from the runtime pipeline, publication
WAL, and Slang DB.  Its durable fixture validates only the *shape* of a future
actual-P0 packet.  It cannot approve actual data, semantic quality, or a full
scan; those gates remain closed until separately reviewed actual artifacts exist.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import urlsplit


SOURCE_SNAPSHOT_SCHEMA = "p0_source_snapshot_registry_actual_v1"
SOURCE_CLAIM_SCHEMA = "p0_source_claim_actual_v1"
B_SENSE_SCHEMA = "p0_b_sense_contract_v1"
ANNOTATION_EVENT_SCHEMA = "p0_annotation_event_actual_v1"
EXAMPLE_MANIFEST_SCHEMA = "p0_actual_contract_example_manifest_v1"
RECEIPT_SCHEMA = "p0_actual_contract_foundation_receipt_v1"

ACTUAL_ORIGIN = "ACTUAL_OBSERVED_SOURCE"
EXAMPLE_ORIGIN = "ACTUAL_SCHEMA_CONTRACT_EXAMPLE_ONLY"
OPERATIONAL_EFFECT = "NONE_SHADOW_ONLY"

SOURCE_PROFILES = (
    "OFFICIAL_STRUCTURED",
    "COMMUNITY_STRUCTURED",
    "MEDIA_OCR",
    "GENERIC_FALLBACK",
)
TRACKS = ("A", "B")
ANNOTATION_STATUSES = ("JUDGED", "UNJUDGED", "UNAVAILABLE")
B_TRUTH_KINDS = ("SENSE_ID", "NEW_SENSE", "NON_TERM", "UNRESOLVED")
B_INFERENCE_DECISIONS = (
    "ASSERT_SENSE",
    "ASSERT_NEW_SENSE",
    "ASSERT_NON_TERM",
    "ABSTAIN",
)
PUBLICATION_ACTIONS = ("PUBLISH", "HOLD", "REJECT")

_RIGHTS_REASONS = {
    "rights_policy_assessed",
    "rights_unknown_fail_closed",
    "rights_revoked_and_deleted",
}
_LINEAGE_REASONS = {
    "lineage_original_verified",
    "lineage_derivative_verified",
    "lineage_temporal_revision_collapsed",
    "lineage_unknown_fail_closed",
}

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_UNKNOWN_TIME_REASONS = {
    "source_time_not_exposed",
    "source_modified_time_not_exposed",
    "source_deleted",
    "access_restricted",
}
_B_TRUTH_REASONS = {
    "truth_existing_sense_confirmed",
    "truth_new_sense_confirmed",
    "truth_non_term_confirmed",
}
_B_ANNOTATION_REASONS = {
    "annotation_human_review_completed",
    "annotation_sense_ambiguous",
    "annotation_temporal_scope_unresolved",
    "evidence_unavailable",
    "evidence_access_restricted",
    "evidence_deleted",
}
_B_INFERENCE_REASONS = {
    "inference_existing_sense_selected",
    "inference_new_sense_candidate",
    "inference_non_term_selected",
    "retrieval_unavailable_requires_abstain",
    "candidate_integrity_requires_abstain",
    "temporal_scope_requires_abstain",
    "sensitive_review_requires_abstain",
}
_B_PUBLICATION_REASONS = {
    "publication_evidence_verified",
    "publication_existing_wal_no_write",
    "publication_new_sense_review_hold",
    "publication_unjudged_hold",
    "publication_unavailable_hold",
    "publication_stale_review_hold",
    "publication_sensitive_review_hold",
    "publication_rights_hold",
    "publication_abstain_hold",
    "publication_non_term_reject",
}

_SNAPSHOT_FIELDS = frozenset(
    {
        "schema_version",
        "record_origin",
        "registry_record_id",
        "source_id",
        "snapshot_id",
        "snapshot_regime",
        "platform",
        "community_scope",
        "canonical_url",
        "locator",
        "author_pseudonym_sha256",
        "published_at",
        "published_at_unknown_reason",
        "modified_at",
        "modified_at_unknown_reason",
        "collected_at",
        "http_status",
        "content_type",
        "response_bytes",
        "response_sha256",
        "normalized_text_sha256",
        "normalization_version",
        "payload_ref",
        "capture_profile",
        "capture_version",
        "capture_run_manifest_sha256",
        "capture_receipt_sha256",
        "lineage_root_id",
        "parent_registry_record_id",
        "derivation_kind",
        "independence_group_id",
        "independence_status",
        "lineage_review_status",
        "lineage_reason_codes",
        "lineage_evidence_sha256",
        "source_profile",
        "parser_route",
        "collection_allowed",
        "content_retention_allowed",
        "derived_index_allowed",
        "quotation_allowed",
        "publication_evidence_eligible",
        "rights_basis",
        "rights_policy_sha256",
        "rights_assessment_status",
        "rights_reason_codes",
        "rights_reviewed_at",
        "retention_class",
        "takedown_status",
        "payload_deletion_receipt_sha256",
        "derived_index_deletion_receipt_sha256",
        "action_applied",
        "operational_effect",
        "registry_record_sha256",
        "row_sha256",
    }
)

_CLAIM_FIELDS = frozenset(
    {
        "schema_version",
        "record_origin",
        "claim_id",
        "registry_record_id",
        "registry_record_sha256",
        "snapshot_id",
        "track",
        "span_start",
        "span_end",
        "span_text",
        "span_sha256",
        "surface_text",
        "normalized_surface",
        "claim_direction",
        "claim_kind",
        "target_work_id",
        "target_sense_id",
        "definition",
        "parse_disposition",
        "parser_profile",
        "parser_version",
        "parser_run_id",
        "parser_manifest_sha256",
        "repair_mode",
        "repair_output_text",
        "repair_source_span_sha256",
        "claim_evidence_receipt_sha256",
        "action_applied",
        "operational_effect",
        "row_sha256",
    }
)

_B_CONTEXT_FIELDS = frozenset(
    {
        "schema_version",
        "record_origin",
        "context_id",
        "post_id",
        "content_text",
        "content_fingerprint",
        "context_observed_at",
        "surface_text",
        "surface_start",
        "surface_end",
        "surface_sha256",
        "normalized_surface",
        "community_scope",
        "platform_scope",
        "candidate_sense_ids",
        "candidate_set_fingerprint",
        "candidate_registry_snapshot_sha256",
        "candidate_registry_status",
        "annotation_subject_sha256",
        "truth_source_claim_ids",
        "truth_claim_set_sha256",
        "truth_evidence_cutoff",
        "truth_evidence_receipt_sha256",
        "inference_source_claim_ids",
        "inference_claim_set_sha256",
        "inference_evidence_cutoff",
        "inference_input_receipt_sha256",
        "truth_kind",
        "truth_sense_id",
        "new_sense_proposal_id",
        "novelty_review_receipt_sha256",
        "truth_reason_codes",
        "annotation_status",
        "annotation_reason_codes",
        "annotation_event_id",
        "inference_decision",
        "inference_sense_id",
        "inference_reason_codes",
        "publication_action",
        "public_sense_id",
        "public_definition",
        "publication_reason_codes",
        "term_type",
        "definition",
        "discourse_function",
        "valid_from",
        "valid_to",
        "temporal_status",
        "sensitivity_class",
        "sensitive_review_status",
        "action_applied",
        "operational_effect",
        "row_sha256",
    }
)

_ANNOTATION_EVENT_FIELDS = frozenset(
    {
        "schema_version",
        "record_origin",
        "journal_id",
        "journal_sequence",
        "event_id",
        "event_sha256",
        "previous_event_id",
        "previous_event_sha256",
        "target_record_type",
        "target_id",
        "target_subject_sha256",
        "reviewer_pseudonym_sha256",
        "reviewer_principal_sha256",
        "reviewer_role",
        "independent_review",
        "reviewer_assignment_receipt_sha256",
        "guideline_path",
        "guideline_version",
        "guideline_sha256",
        "event_kind",
        "supersedes_event_ids",
        "occurred_at",
        "evidence_cutoff",
        "evidence_claim_ids",
        "annotation_status",
        "decision_kind",
        "decision_sense_id",
        "decision_payload_sha256",
        "reason_codes",
        "action_applied",
        "operational_effect",
        "row_sha256",
    }
)

_MANIFEST_FIELDS = frozenset(
    {
        "schema_version",
        "record_origin",
        "source_snapshots",
        "source_claims",
        "b_sense_contexts",
        "annotation_events",
        "gate_scope",
        "authority",
        "public_apply",
        "central_slang_db_write",
        "publication_wal_write",
        "actual_a_context_reviews",
        "p0_phase_exit",
        "manifest_sha256",
    }
)


class P0ActualContractError(ValueError):
    """Raised when the actual-P0 foundation contract fails closed."""


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def with_row_hash(value: Mapping[str, Any]) -> dict[str, Any]:
    material = dict(value)
    material.pop("row_sha256", None)
    return {**material, "row_sha256": canonical_sha256(material)}


def _strict(value: Any, fields: frozenset[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise P0ActualContractError(f"{label} must be an object")
    if set(value) != fields:
        raise P0ActualContractError(
            f"{label} fields mismatch: missing={sorted(fields - set(value))}, "
            f"extra={sorted(set(value) - fields)}"
        )
    return value


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise P0ActualContractError(f"{field} must be canonical non-empty text")
    return value


def _nonempty_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise P0ActualContractError(f"{field} must be non-empty text")
    return value


def _optional_text(value: Any, field: str) -> str | None:
    return None if value is None else _text(value, field)


def _sha(value: Any, field: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise P0ActualContractError(f"{field} must be lowercase sha256")
    return value


def _optional_sha(value: Any, field: str) -> str | None:
    return None if value is None else _sha(value, field)


def _timestamp(value: Any, field: str) -> datetime:
    text = _text(value, field)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise P0ActualContractError(f"{field} must be RFC3339") from exc
    if parsed.tzinfo is None:
        raise P0ActualContractError(f"{field} must include timezone")
    return parsed


def _optional_timestamp(value: Any, field: str) -> datetime | None:
    return None if value is None else _timestamp(value, field)


def _https_url(value: Any, field: str, *, example_origin: bool) -> str:
    text = _text(value, field)
    try:
        parsed = urlsplit(text)
        hostname = parsed.hostname
        parsed.port
    except ValueError as exc:
        raise P0ActualContractError(f"{field} must be a canonical https URL") from exc
    if (
        parsed.scheme != "https"
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        raise P0ActualContractError(f"{field} must be a canonical https URL")
    lowered = hostname.lower()
    reserved = lowered == "localhost" or lowered.endswith(
        (".invalid", ".example", ".test", ".localhost")
    )
    if example_origin != reserved:
        expected = "reserved example" if example_origin else "non-reserved actual"
        raise P0ActualContractError(f"{field} must use a {expected} hostname")
    return text


def _sorted_texts(value: Any, field: str, *, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list):
        raise P0ActualContractError(f"{field} must be a list")
    output = [_text(item, field) for item in value]
    if output != sorted(output) or len(output) != len(set(output)):
        raise P0ActualContractError(f"{field} must be sorted and unique")
    if not allow_empty and not output:
        raise P0ActualContractError(f"{field} must not be empty")
    return output


def _reasons(value: Any, field: str, allowed: set[str], *, allow_empty: bool = False) -> list[str]:
    output = _sorted_texts(value, field, allow_empty=allow_empty)
    unknown = sorted(set(output) - allowed)
    if unknown:
        raise P0ActualContractError(f"{field} contains unregistered codes: {unknown}")
    return output


def _self_hash(value: Mapping[str, Any], field: str, label: str) -> None:
    stored = _sha(value[field], field)
    material = {key: item for key, item in value.items() if key != field}
    if stored != canonical_sha256(material):
        raise P0ActualContractError(f"{label} hash mismatch")


def _origin(value: Mapping[str, Any], expected_origin: str) -> None:
    if expected_origin not in {ACTUAL_ORIGIN, EXAMPLE_ORIGIN}:
        raise P0ActualContractError("unsupported record origin")
    if value["record_origin"] != expected_origin:
        raise P0ActualContractError("actual/example origin namespace mismatch")


def _record_sha(value: Mapping[str, Any], digest_field: str) -> str:
    return canonical_sha256(
        {
            key: item
            for key, item in value.items()
            if key not in {digest_field, "row_sha256"}
        }
    )


def _capture_receipt(row: Mapping[str, Any]) -> str:
    return canonical_sha256(
        {
            "source_id": row["source_id"],
            "snapshot_id": row["snapshot_id"],
            "canonical_url": row["canonical_url"],
            "locator": row["locator"],
            "capture_profile": row["capture_profile"],
            "capture_version": row["capture_version"],
            "capture_run_manifest_sha256": row["capture_run_manifest_sha256"],
            "collected_at": row["collected_at"],
            "http_status": row["http_status"],
            "response_bytes": row["response_bytes"],
            "response_sha256": row["response_sha256"],
        }
    )


def _validate_source_snapshot(value: Any, expected_origin: str) -> dict[str, Any]:
    row = _strict(value, _SNAPSHOT_FIELDS, "source snapshot")
    if row["schema_version"] != SOURCE_SNAPSHOT_SCHEMA:
        raise P0ActualContractError("source snapshot schema mismatch")
    _origin(row, expected_origin)
    for field in (
        "registry_record_id",
        "source_id",
        "snapshot_id",
        "snapshot_regime",
        "platform",
        "community_scope",
        "locator",
        "capture_profile",
        "capture_version",
        "normalization_version",
        "lineage_root_id",
        "independence_group_id",
        "content_type",
        "rights_basis",
    ):
        _text(row[field], field)
    _https_url(row["canonical_url"], "canonical_url", example_origin=expected_origin == EXAMPLE_ORIGIN)
    _optional_sha(row["author_pseudonym_sha256"], "author_pseudonym_sha256")

    published = _optional_timestamp(row["published_at"], "published_at")
    modified = _optional_timestamp(row["modified_at"], "modified_at")
    collected = _timestamp(row["collected_at"], "collected_at")
    for timestamp, reason, field in (
        (published, row["published_at_unknown_reason"], "published_at"),
        (modified, row["modified_at_unknown_reason"], "modified_at"),
    ):
        if timestamp is None and reason not in _UNKNOWN_TIME_REASONS:
            raise P0ActualContractError(f"{field} requires an allowlisted unknown reason")
        if timestamp is not None and reason is not None:
            raise P0ActualContractError(f"{field} value must not carry unknown reason")
        if timestamp is not None and timestamp > collected:
            raise P0ActualContractError(f"{field} must not follow collected_at")
    if published is not None and modified is not None and published > modified:
        raise P0ActualContractError("published_at must not follow modified_at")

    for field, minimum, maximum in (
        ("http_status", 100, 599),
        ("response_bytes", 0, None),
    ):
        item = row[field]
        if (
            isinstance(item, bool)
            or not isinstance(item, int)
            or item < minimum
            or maximum is not None
            and item > maximum
        ):
            raise P0ActualContractError(f"{field} is invalid")
    _sha(row["response_sha256"], "response_sha256")
    _sha(row["normalized_text_sha256"], "normalized_text_sha256")
    _sha(row["capture_run_manifest_sha256"], "capture_run_manifest_sha256")
    if _sha(row["capture_receipt_sha256"], "capture_receipt_sha256") != _capture_receipt(
        row
    ):
        raise P0ActualContractError("capture receipt binding mismatch")
    payload_ref = _optional_text(row["payload_ref"], "payload_ref")
    if payload_ref is not None:
        payload_path = Path(payload_ref)
        if payload_path.is_absolute() or ".." in payload_path.parts:
            raise P0ActualContractError("payload_ref must be a contained relative path")

    if row["source_profile"] not in SOURCE_PROFILES:
        raise P0ActualContractError("source_profile is invalid")
    expected_route = "generic_queue" if row["source_profile"] == "GENERIC_FALLBACK" else "structured_profile"
    if row["parser_route"] != expected_route:
        raise P0ActualContractError("source profile/parser route mismatch")
    if row["derivation_kind"] not in {
        "ORIGINAL",
        "MIRROR",
        "REPOST",
        "QUOTE",
        "OCR_DERIVED",
        "TEMPORAL_REVISION",
        "UNKNOWN_LINEAGE",
    }:
        raise P0ActualContractError("derivation_kind is invalid")
    if row["independence_status"] not in {
        "ELIGIBLE_ROOT",
        "COLLAPSED_DERIVATIVE",
        "COLLAPSED_UNKNOWN_LINEAGE",
    }:
        raise P0ActualContractError("independence_status is invalid")
    parent_id = _optional_text(row["parent_registry_record_id"], "parent_registry_record_id")
    if parent_id is None:
        valid_root = (
            row["lineage_root_id"] == row["registry_record_id"]
            and row["derivation_kind"] == "ORIGINAL"
            and row["independence_status"] == "ELIGIBLE_ROOT"
        )
        valid_unknown = (
            row["lineage_root_id"] == row["registry_record_id"]
            and row["derivation_kind"] == "UNKNOWN_LINEAGE"
            and row["independence_status"] == "COLLAPSED_UNKNOWN_LINEAGE"
        )
        if not (valid_root or valid_unknown):
            raise P0ActualContractError("root/unknown lineage fields mismatch")
    elif row["independence_status"] != "COLLAPSED_DERIVATIVE" or row["derivation_kind"] in {
        "ORIGINAL",
        "UNKNOWN_LINEAGE",
    }:
        raise P0ActualContractError("derived lineage must be collapsed")
    if row["lineage_review_status"] not in {"VERIFIED", "UNKNOWN"}:
        raise P0ActualContractError("lineage_review_status is invalid")
    lineage_reasons = _reasons(
        row["lineage_reason_codes"], "lineage_reason_codes", _LINEAGE_REASONS
    )
    _sha(row["lineage_evidence_sha256"], "lineage_evidence_sha256")
    if row["lineage_review_status"] == "UNKNOWN":
        if (
            lineage_reasons != ["lineage_unknown_fail_closed"]
            or row["derivation_kind"] != "UNKNOWN_LINEAGE"
            or row["independence_status"] != "COLLAPSED_UNKNOWN_LINEAGE"
        ):
            raise P0ActualContractError("unknown lineage must fail closed")
    else:
        expected_lineage_reason = (
            "lineage_original_verified"
            if row["derivation_kind"] == "ORIGINAL"
            else "lineage_temporal_revision_collapsed"
            if row["derivation_kind"] == "TEMPORAL_REVISION"
            else "lineage_derivative_verified"
        )
        if lineage_reasons != [expected_lineage_reason]:
            raise P0ActualContractError("verified lineage reason family mismatch")

    rights_flags = (
        "collection_allowed",
        "content_retention_allowed",
        "derived_index_allowed",
        "quotation_allowed",
        "publication_evidence_eligible",
    )
    if any(not isinstance(row[field], bool) for field in rights_flags):
        raise P0ActualContractError("rights capability flags must be booleans")
    _sha(row["rights_policy_sha256"], "rights_policy_sha256")
    _timestamp(row["rights_reviewed_at"], "rights_reviewed_at")
    if row["rights_assessment_status"] not in {"ASSESSED", "UNKNOWN", "REVOKED"}:
        raise P0ActualContractError("rights_assessment_status is invalid")
    rights_reasons = _reasons(
        row["rights_reason_codes"], "rights_reason_codes", _RIGHTS_REASONS
    )
    expected_rights_reason = {
        "ASSESSED": "rights_policy_assessed",
        "UNKNOWN": "rights_unknown_fail_closed",
        "REVOKED": "rights_revoked_and_deleted",
    }[row["rights_assessment_status"]]
    if rights_reasons != [expected_rights_reason]:
        raise P0ActualContractError("rights assessment reason family mismatch")
    if row["rights_assessment_status"] != "ASSESSED" and any(
        row[field] for field in rights_flags
    ):
        raise P0ActualContractError("unknown/revoked rights must disable every capability")
    if row["retention_class"] not in {"METADATA_ONLY", "HASH_ONLY", "CONTROLLED_RAW"}:
        raise P0ActualContractError("retention_class is invalid")
    if row["takedown_status"] not in {"ACTIVE", "PENDING_REMOVAL", "REMOVED"}:
        raise P0ActualContractError("takedown_status is invalid")
    payload_deletion = _optional_sha(
        row["payload_deletion_receipt_sha256"], "payload_deletion_receipt_sha256"
    )
    index_deletion = _optional_sha(
        row["derived_index_deletion_receipt_sha256"],
        "derived_index_deletion_receipt_sha256",
    )
    if not row["collection_allowed"] and any(row[field] for field in rights_flags[1:]):
        raise P0ActualContractError("collection denial must disable downstream rights")
    if row["content_retention_allowed"] != (row["retention_class"] == "CONTROLLED_RAW"):
        raise P0ActualContractError("content retention capability/class mismatch")
    if row["retention_class"] == "CONTROLLED_RAW" and payload_ref is None:
        raise P0ActualContractError("CONTROLLED_RAW requires payload_ref")
    if row["retention_class"] != "CONTROLLED_RAW" and payload_ref is not None:
        raise P0ActualContractError("non-raw retention must not expose payload_ref")
    if row["takedown_status"] != "ACTIVE" and (
        payload_ref is not None
        or row["content_retention_allowed"]
        or row["derived_index_allowed"]
        or row["quotation_allowed"]
        or row["publication_evidence_eligible"]
    ):
        raise P0ActualContractError("takedown must disable retained/indexed/public evidence")
    if row["takedown_status"] == "ACTIVE" and (
        payload_deletion is not None or index_deletion is not None
    ):
        raise P0ActualContractError("active source must not carry deletion receipts")
    if row["takedown_status"] != "ACTIVE" and (
        payload_deletion is None or index_deletion is None
    ):
        raise P0ActualContractError("takedown requires payload and index deletion receipts")
    if row["rights_assessment_status"] == "REVOKED" and row["takedown_status"] == "ACTIVE":
        raise P0ActualContractError("revoked rights require takedown state")
    if row["publication_evidence_eligible"] and (
        not row["collection_allowed"]
        or not row["quotation_allowed"]
        or row["takedown_status"] != "ACTIVE"
        or row["independence_status"] != "ELIGIBLE_ROOT"
        or not 200 <= row["http_status"] < 300
    ):
        raise P0ActualContractError("publication evidence rights/lineage/status mismatch")
    if row["independence_status"] != "ELIGIBLE_ROOT" and row["publication_evidence_eligible"]:
        raise P0ActualContractError("collapsed lineage cannot become publication evidence")
    if row["action_applied"] is not False or row["operational_effect"] != OPERATIONAL_EFFECT:
        raise P0ActualContractError("source registry foundation must be no-write shadow only")
    if _sha(row["registry_record_sha256"], "registry_record_sha256") != _record_sha(
        row, "registry_record_sha256"
    ):
        raise P0ActualContractError("registry_record_sha256 mismatch")
    _self_hash(row, "row_sha256", "source snapshot")
    return dict(row)


def validate_actual_source_snapshot(value: Any) -> dict[str, Any]:
    return _validate_source_snapshot(value, ACTUAL_ORIGIN)


def _claim_receipt(row: Mapping[str, Any], response_sha256: str) -> str:
    return canonical_sha256(
        {
            "registry_record_id": row["registry_record_id"],
            "registry_record_sha256": row["registry_record_sha256"],
            "snapshot_id": row["snapshot_id"],
            "response_sha256": response_sha256,
            "span_start": row["span_start"],
            "span_end": row["span_end"],
            "span_sha256": row["span_sha256"],
            "claim_direction": row["claim_direction"],
            "claim_kind": row["claim_kind"],
            "normalized_surface": row["normalized_surface"],
            "target_work_id": row["target_work_id"],
            "target_sense_id": row["target_sense_id"],
            "definition": row["definition"],
        }
    )


def _validate_source_claim(
    value: Any,
    expected_origin: str,
    *,
    response_sha256: str | None = None,
) -> dict[str, Any]:
    row = _strict(value, _CLAIM_FIELDS, "source claim")
    if row["schema_version"] != SOURCE_CLAIM_SCHEMA:
        raise P0ActualContractError("source claim schema mismatch")
    _origin(row, expected_origin)
    for field in (
        "claim_id",
        "registry_record_id",
        "snapshot_id",
        "surface_text",
        "normalized_surface",
        "parser_profile",
        "parser_version",
        "parser_run_id",
    ):
        _text(row[field], field)
    _nonempty_text(row["span_text"], "span_text")
    _sha(row["registry_record_sha256"], "registry_record_sha256")
    _sha(row["parser_manifest_sha256"], "parser_manifest_sha256")
    for field in ("span_start", "span_end"):
        item = row[field]
        if isinstance(item, bool) or not isinstance(item, int) or item < 0:
            raise P0ActualContractError(f"{field} is invalid")
    if row["span_end"] <= row["span_start"]:
        raise P0ActualContractError("claim span must be non-empty")
    if _sha(row["span_sha256"], "span_sha256") != canonical_sha256(row["span_text"]):
        raise P0ActualContractError("span_sha256 mismatch")
    if row["surface_text"] not in row["span_text"]:
        raise P0ActualContractError("surface must be present in the captured span")
    if row["track"] not in TRACKS:
        raise P0ActualContractError("claim track is invalid")
    target_work = _optional_text(row["target_work_id"], "target_work_id")
    target_sense = _optional_text(row["target_sense_id"], "target_sense_id")
    definition = _optional_text(row["definition"], "definition")
    allowed = {
        "WORK_ALIAS": ("A", {"SURFACE_TO_WORK", "WORK_TO_SURFACE"}),
        "COMMUNITY_SENSE": ("B", {"SURFACE_TO_SENSE"}),
        "NEW_SENSE_CANDIDATE": ("B", {"SURFACE_TO_SENSE"}),
        "NON_TERM_EVIDENCE": ("B", {"SURFACE_TO_SENSE"}),
        "UNKNOWN": (row["track"], {"UNKNOWN_DIRECTION"}),
    }
    if row["claim_kind"] not in allowed:
        raise P0ActualContractError("claim_kind is invalid")
    required_track, directions = allowed[row["claim_kind"]]
    if row["track"] != required_track or row["claim_direction"] not in directions:
        raise P0ActualContractError("claim kind/track/direction mismatch")
    if row["claim_kind"] == "WORK_ALIAS":
        if target_work is None or target_sense is not None or definition is not None:
            raise P0ActualContractError("WORK_ALIAS target fields mismatch")
    elif row["claim_kind"] == "COMMUNITY_SENSE":
        if target_work is not None or target_sense is None or definition is None:
            raise P0ActualContractError("COMMUNITY_SENSE target fields mismatch")
        if definition not in row["span_text"]:
            raise P0ActualContractError("COMMUNITY_SENSE definition must occur in evidence span")
    elif row["claim_kind"] == "NEW_SENSE_CANDIDATE":
        if target_work is not None or target_sense is not None or definition is None:
            raise P0ActualContractError("NEW_SENSE_CANDIDATE target fields mismatch")
        if definition not in row["span_text"]:
            raise P0ActualContractError("NEW_SENSE definition must occur in evidence span")
    elif target_work is not None or target_sense is not None or definition is not None:
        raise P0ActualContractError("non-target claim must not invent target fields")
    if row["parse_disposition"] not in {"PARSED", "GENERIC_PENDING", "ABSTAIN"}:
        raise P0ActualContractError("parse_disposition is invalid")
    if row["claim_kind"] == "UNKNOWN":
        if row["parse_disposition"] == "PARSED" or row["repair_mode"] != "ABSTAIN":
            raise P0ActualContractError("UNKNOWN claim must remain pending/abstained")
    elif row["parse_disposition"] != "PARSED":
        raise P0ActualContractError("typed actual claim must be PARSED")
    if row["repair_mode"] not in {"NONE", "NORMALIZE_EXISTING", "ABSTAIN"}:
        raise P0ActualContractError("repair_mode is invalid")
    repair_output = _optional_text(row["repair_output_text"], "repair_output_text")
    repair_source_sha = _optional_sha(
        row["repair_source_span_sha256"], "repair_source_span_sha256"
    )
    if row["repair_mode"] == "NONE":
        if repair_output is not None or repair_source_sha is not None:
            raise P0ActualContractError("NONE repair must not carry repair output")
    elif row["repair_mode"] == "NORMALIZE_EXISTING":
        if (
            repair_output is None
            or repair_source_sha != row["span_sha256"]
            or repair_output != row["normalized_surface"]
        ):
            raise P0ActualContractError("repair must bind to existing captured span")
    elif repair_output is not None or repair_source_sha is not None:
        raise P0ActualContractError("ABSTAIN repair must not invent output")
    if response_sha256 is not None:
        _sha(response_sha256, "response_sha256")
        if _sha(
            row["claim_evidence_receipt_sha256"], "claim_evidence_receipt_sha256"
        ) != _claim_receipt(row, response_sha256):
            raise P0ActualContractError("claim evidence receipt binding mismatch")
    else:
        _sha(row["claim_evidence_receipt_sha256"], "claim_evidence_receipt_sha256")
    if row["action_applied"] is not False or row["operational_effect"] != OPERATIONAL_EFFECT:
        raise P0ActualContractError("source claim foundation must be no-write shadow only")
    _self_hash(row, "row_sha256", "source claim")
    return dict(row)


def validate_actual_source_claim(value: Any) -> dict[str, Any]:
    return _validate_source_claim(value, ACTUAL_ORIGIN)


def _b_receipts(row: Mapping[str, Any]) -> tuple[str | None, str]:
    truth_receipt = None
    if row["truth_kind"] != "UNRESOLVED":
        truth_receipt = canonical_sha256(
            {
                "post_id": row["post_id"],
                "content_fingerprint": row["content_fingerprint"],
                "context_observed_at": row["context_observed_at"],
                "truth_kind": row["truth_kind"],
                "truth_sense_id": row["truth_sense_id"],
                "new_sense_proposal_id": row["new_sense_proposal_id"],
                "novelty_review_receipt_sha256": row[
                    "novelty_review_receipt_sha256"
                ],
                "source_claim_ids": row["truth_source_claim_ids"],
                "claim_set_sha256": row["truth_claim_set_sha256"],
                "evidence_cutoff": row["truth_evidence_cutoff"],
            }
        )
    inference_receipt = canonical_sha256(
        {
            "post_id": row["post_id"],
            "content_fingerprint": row["content_fingerprint"],
            "context_observed_at": row["context_observed_at"],
            "candidate_sense_ids": row["candidate_sense_ids"],
            "candidate_registry_snapshot_sha256": row[
                "candidate_registry_snapshot_sha256"
            ],
            "candidate_registry_status": row["candidate_registry_status"],
            "source_claim_ids": row["inference_source_claim_ids"],
            "claim_set_sha256": row["inference_claim_set_sha256"],
            "evidence_cutoff": row["inference_evidence_cutoff"],
        }
    )
    return truth_receipt, inference_receipt


def _annotation_subject_sha(row: Mapping[str, Any]) -> str:
    return canonical_sha256(
        {
            "post_id": row["post_id"],
            "content_fingerprint": row["content_fingerprint"],
            "context_observed_at": row["context_observed_at"],
            "surface_text": row["surface_text"],
            "surface_start": row["surface_start"],
            "surface_end": row["surface_end"],
            "surface_sha256": row["surface_sha256"],
            "normalized_surface": row["normalized_surface"],
            "community_scope": row["community_scope"],
            "platform_scope": row["platform_scope"],
            "candidate_sense_ids": row["candidate_sense_ids"],
            "candidate_set_fingerprint": row["candidate_set_fingerprint"],
            "candidate_registry_snapshot_sha256": row[
                "candidate_registry_snapshot_sha256"
            ],
            "candidate_registry_status": row["candidate_registry_status"],
            "truth_source_claim_ids": row["truth_source_claim_ids"],
            "truth_claim_set_sha256": row["truth_claim_set_sha256"],
            "truth_evidence_cutoff": row["truth_evidence_cutoff"],
        }
    )


def _claim_set_sha(claim_rows: Sequence[Mapping[str, Any]]) -> str:
    return canonical_sha256(
        [
            {
                "claim_id": row["claim_id"],
                "row_sha256": row["row_sha256"],
                "claim_evidence_receipt_sha256": row[
                    "claim_evidence_receipt_sha256"
                ],
            }
            for row in sorted(claim_rows, key=lambda item: item["claim_id"])
        ]
    )


def _decision_payload_sha(row: Mapping[str, Any]) -> str:
    return canonical_sha256(
        {
            "truth_kind": row["truth_kind"],
            "truth_sense_id": row["truth_sense_id"],
            "definition": row["definition"],
            "new_sense_proposal_id": row["new_sense_proposal_id"],
            "novelty_review_receipt_sha256": row[
                "novelty_review_receipt_sha256"
            ],
            "term_type": row["term_type"],
            "discourse_function": row["discourse_function"],
            "valid_from": row["valid_from"],
            "valid_to": row["valid_to"],
            "temporal_status": row["temporal_status"],
            "sensitivity_class": row["sensitivity_class"],
            "sensitive_review_status": row["sensitive_review_status"],
        }
    )


def _validate_b_context(value: Any, expected_origin: str) -> dict[str, Any]:
    row = _strict(value, _B_CONTEXT_FIELDS, "B sense context")
    if row["schema_version"] != B_SENSE_SCHEMA:
        raise P0ActualContractError("B sense schema mismatch")
    _origin(row, expected_origin)
    for field in (
        "context_id",
        "post_id",
        "surface_text",
        "normalized_surface",
        "community_scope",
        "platform_scope",
        "annotation_event_id",
        "term_type",
        "discourse_function",
    ):
        _text(row[field], field)
    _nonempty_text(row["content_text"], "content_text")
    if _sha(row["content_fingerprint"], "content_fingerprint") != canonical_sha256(
        row["content_text"]
    ):
        raise P0ActualContractError("B context content_fingerprint mismatch")
    if row["surface_text"] not in row["content_text"]:
        raise P0ActualContractError("B surface must occur in context content")
    for field in ("surface_start", "surface_end"):
        item = row[field]
        if isinstance(item, bool) or not isinstance(item, int) or item < 0:
            raise P0ActualContractError(f"{field} is invalid")
    if (
        row["surface_end"] <= row["surface_start"]
        or row["surface_end"] > len(row["content_text"])
        or row["content_text"][row["surface_start"] : row["surface_end"]]
        != row["surface_text"]
    ):
        raise P0ActualContractError("B surface span does not match context content")
    if _sha(row["surface_sha256"], "surface_sha256") != canonical_sha256(
        row["surface_text"]
    ):
        raise P0ActualContractError("B surface_sha256 mismatch")
    context_observed = _timestamp(row["context_observed_at"], "context_observed_at")
    candidates = _sorted_texts(
        row["candidate_sense_ids"], "candidate_sense_ids", allow_empty=True
    )
    if _sha(row["candidate_set_fingerprint"], "candidate_set_fingerprint") != canonical_sha256(
        candidates
    ):
        raise P0ActualContractError("B candidate_set_fingerprint mismatch")
    _sha(
        row["candidate_registry_snapshot_sha256"],
        "candidate_registry_snapshot_sha256",
    )
    if row["candidate_registry_status"] not in {"COMPLETE", "INCOMPLETE", "UNAVAILABLE"}:
        raise P0ActualContractError("candidate_registry_status is invalid")
    if row["candidate_registry_status"] == "UNAVAILABLE" and candidates:
        raise P0ActualContractError("unavailable candidate registry must not expose candidates")
    if _sha(
        row["annotation_subject_sha256"], "annotation_subject_sha256"
    ) != _annotation_subject_sha(row):
        raise P0ActualContractError("annotation subject binding mismatch")
    truth_claims = _sorted_texts(row["truth_source_claim_ids"], "truth_source_claim_ids")
    _sha(row["truth_claim_set_sha256"], "truth_claim_set_sha256")
    inference_claims = _sorted_texts(
        row["inference_source_claim_ids"], "inference_source_claim_ids"
    )
    _sha(row["inference_claim_set_sha256"], "inference_claim_set_sha256")
    truth_cutoff = _timestamp(row["truth_evidence_cutoff"], "truth_evidence_cutoff")
    inference_cutoff = _timestamp(row["inference_evidence_cutoff"], "inference_evidence_cutoff")
    if inference_cutoff > truth_cutoff:
        raise P0ActualContractError("inference evidence cutoff must not follow truth cutoff")
    if inference_cutoff > context_observed:
        raise P0ActualContractError("inference evidence cutoff must not follow context observation")
    expected_truth_receipt, expected_inference_receipt = _b_receipts(row)
    if _optional_sha(
        row["truth_evidence_receipt_sha256"], "truth_evidence_receipt_sha256"
    ) != expected_truth_receipt:
        raise P0ActualContractError("truth evidence receipt binding mismatch")
    if _sha(
        row["inference_input_receipt_sha256"], "inference_input_receipt_sha256"
    ) != expected_inference_receipt:
        raise P0ActualContractError("inference input receipt binding mismatch")

    if row["truth_kind"] not in B_TRUTH_KINDS:
        raise P0ActualContractError("B truth_kind is invalid")
    truth_sense = _optional_text(row["truth_sense_id"], "truth_sense_id")
    truth_reasons = _reasons(
        row["truth_reason_codes"],
        "truth_reason_codes",
        _B_TRUTH_REASONS,
        allow_empty=True,
    )
    if row["annotation_status"] not in ANNOTATION_STATUSES:
        raise P0ActualContractError("B annotation_status is invalid")
    annotation_reasons = _reasons(
        row["annotation_reason_codes"],
        "annotation_reason_codes",
        _B_ANNOTATION_REASONS,
    )
    expected_truth_reason = {
        "SENSE_ID": "truth_existing_sense_confirmed",
        "NEW_SENSE": "truth_new_sense_confirmed",
        "NON_TERM": "truth_non_term_confirmed",
    }.get(row["truth_kind"])
    if row["annotation_status"] == "JUDGED":
        if row["truth_kind"] == "UNRESOLVED" or truth_reasons != [expected_truth_reason]:
            raise P0ActualContractError("JUDGED B context requires terminal truth")
        if annotation_reasons != ["annotation_human_review_completed"]:
            raise P0ActualContractError("JUDGED annotation reason family mismatch")
    else:
        if row["truth_kind"] != "UNRESOLVED" or truth_sense is not None or truth_reasons:
            raise P0ActualContractError("unresolved annotation must keep truth unresolved")
        allowed = (
            {"annotation_sense_ambiguous", "annotation_temporal_scope_unresolved"}
            if row["annotation_status"] == "UNJUDGED"
            else {"evidence_unavailable", "evidence_access_restricted", "evidence_deleted"}
        )
        if not set(annotation_reasons).issubset(allowed):
            raise P0ActualContractError("annotation status/reason family mismatch")
    if row["truth_kind"] == "SENSE_ID":
        if truth_sense is None or truth_sense not in candidates:
            raise P0ActualContractError("SENSE_ID truth must bind a candidate sense")
    elif truth_sense is not None:
        raise P0ActualContractError("non-SENSE truth must not bind truth_sense_id")
    new_sense_proposal = _optional_text(
        row["new_sense_proposal_id"], "new_sense_proposal_id"
    )
    novelty_receipt = _optional_sha(
        row["novelty_review_receipt_sha256"], "novelty_review_receipt_sha256"
    )
    if row["truth_kind"] == "NEW_SENSE":
        if (
            new_sense_proposal is None
            or novelty_receipt is None
            or row["candidate_registry_status"] != "COMPLETE"
        ):
            raise P0ActualContractError("NEW_SENSE requires complete candidate novelty review")
    elif new_sense_proposal is not None or novelty_receipt is not None:
        raise P0ActualContractError("non-new truth must not carry novelty proposal fields")

    if row["inference_decision"] not in B_INFERENCE_DECISIONS:
        raise P0ActualContractError("B inference_decision is invalid")
    inference_sense = _optional_text(row["inference_sense_id"], "inference_sense_id")
    inference_reasons = _reasons(
        row["inference_reason_codes"], "inference_reason_codes", _B_INFERENCE_REASONS
    )
    expected_inference = {
        "ASSERT_SENSE": ("inference_existing_sense_selected", True),
        "ASSERT_NEW_SENSE": ("inference_new_sense_candidate", False),
        "ASSERT_NON_TERM": ("inference_non_term_selected", False),
    }
    if row["inference_decision"] in expected_inference:
        reason, needs_sense = expected_inference[row["inference_decision"]]
        if inference_reasons != [reason]:
            raise P0ActualContractError("terminal B inference reason mismatch")
        if needs_sense != (inference_sense is not None):
            raise P0ActualContractError("terminal B inference sense binding mismatch")
        if needs_sense and inference_sense not in candidates:
            raise P0ActualContractError("ASSERT_SENSE must bind a candidate sense")
    else:
        if inference_sense is not None or not set(inference_reasons).issubset(
            {
                "retrieval_unavailable_requires_abstain",
                "candidate_integrity_requires_abstain",
                "temporal_scope_requires_abstain",
                "sensitive_review_requires_abstain",
            }
        ):
            raise P0ActualContractError("ABSTAIN fields/reasons mismatch")
    if row["candidate_registry_status"] != "COMPLETE" and row["inference_decision"] != "ABSTAIN":
        raise P0ActualContractError("incomplete candidate registry requires ABSTAIN")

    definition = _optional_text(row["definition"], "definition")
    if row["truth_kind"] in {"SENSE_ID", "NEW_SENSE"} and definition is None:
        raise P0ActualContractError("sense truth requires a definition")
    if row["truth_kind"] in {"NON_TERM", "UNRESOLVED"} and definition is not None:
        raise P0ActualContractError("non-sense truth must not invent a definition")
    if row["term_type"] not in {
        "ABBREVIATION",
        "COMMUNITY_JARGON",
        "MEME",
        "NON_TERM",
        "UNRESOLVED",
    }:
        raise P0ActualContractError("term_type is invalid")
    if row["discourse_function"] not in {
        "REFERENCE",
        "STANCE",
        "IN_GROUP_MARKER",
        "OTHER",
        "UNRESOLVED",
    }:
        raise P0ActualContractError("discourse_function is invalid")
    if row["truth_kind"] == "NON_TERM" and row["term_type"] != "NON_TERM":
        raise P0ActualContractError("NON_TERM truth requires NON_TERM term_type")
    if row["truth_kind"] == "UNRESOLVED" and row["term_type"] != "UNRESOLVED":
        raise P0ActualContractError("unresolved truth requires unresolved term_type")
    valid_from = _optional_timestamp(row["valid_from"], "valid_from")
    valid_to = _optional_timestamp(row["valid_to"], "valid_to")
    if valid_from is not None and valid_to is not None and valid_from >= valid_to:
        raise P0ActualContractError("B sense validity interval is reversed")
    if row["temporal_status"] not in {
        "CURRENT",
        "STALE_REVIEW",
        "HISTORICAL",
        "RETIRED",
        "UNKNOWN",
    }:
        raise P0ActualContractError("temporal_status is invalid")
    in_valid_interval = (valid_from is None or valid_from <= context_observed) and (
        valid_to is None or context_observed < valid_to
    )
    if row["temporal_status"] == "CURRENT" and not in_valid_interval:
        raise P0ActualContractError("CURRENT sense must cover context observation time")
    if row["sensitivity_class"] not in {"NOT_ASSESSED", "NONE", "SENSITIVE"}:
        raise P0ActualContractError("sensitivity_class is invalid")
    if row["sensitive_review_status"] not in {
        "NOT_ASSESSED",
        "NOT_REQUIRED",
        "PENDING",
        "APPROVED",
        "RESTRICTED",
    }:
        raise P0ActualContractError("sensitive_review_status is invalid")
    valid_sensitivity = {
        "NOT_ASSESSED": {"NOT_ASSESSED"},
        "NONE": {"NOT_REQUIRED"},
        "SENSITIVE": {"PENDING", "APPROVED", "RESTRICTED"},
    }
    if row["sensitive_review_status"] not in valid_sensitivity[row["sensitivity_class"]]:
        raise P0ActualContractError("sensitive review status mismatch")

    if row["publication_action"] not in PUBLICATION_ACTIONS:
        raise P0ActualContractError("B publication_action is invalid")
    public_sense = _optional_text(row["public_sense_id"], "public_sense_id")
    public_definition = _optional_text(row["public_definition"], "public_definition")
    publication_reasons = _reasons(
        row["publication_reason_codes"],
        "publication_reason_codes",
        _B_PUBLICATION_REASONS,
    )
    if "publication_existing_wal_no_write" not in publication_reasons:
        raise P0ActualContractError("B publication must preserve existing WAL")
    if row["publication_action"] == "PUBLISH":
        if (
            row["annotation_status"] != "JUDGED"
            or row["truth_kind"] != "SENSE_ID"
            or row["inference_decision"] != "ASSERT_SENSE"
            or public_sense != truth_sense
            or inference_sense != truth_sense
            or public_definition != definition
            or row["temporal_status"] != "CURRENT"
            or row["sensitivity_class"] != "NONE"
            or row["sensitive_review_status"] != "NOT_REQUIRED"
            or publication_reasons
            != ["publication_evidence_verified", "publication_existing_wal_no_write"]
        ):
            raise P0ActualContractError("PUBLISH B sense projection mismatch")
    elif public_sense is not None or public_definition is not None:
        raise P0ActualContractError("HOLD/REJECT must not leak public B fields")
    if row["publication_action"] == "REJECT":
        if (
            row["truth_kind"] != "NON_TERM"
            or row["inference_decision"] != "ASSERT_NON_TERM"
            or publication_reasons
            != ["publication_existing_wal_no_write", "publication_non_term_reject"]
        ):
            raise P0ActualContractError("REJECT requires judged terminal NON_TERM")
    if row["publication_action"] == "HOLD":
        required_hold_reason = (
            "publication_new_sense_review_hold"
            if row["truth_kind"] == "NEW_SENSE"
            else "publication_unjudged_hold"
            if row["annotation_status"] == "UNJUDGED"
            else "publication_unavailable_hold"
            if row["annotation_status"] == "UNAVAILABLE"
            else "publication_stale_review_hold"
            if row["temporal_status"] != "CURRENT"
            else "publication_sensitive_review_hold"
            if row["sensitivity_class"] != "NONE"
            or row["sensitive_review_status"] != "NOT_REQUIRED"
            else "publication_rights_hold"
        )
        if required_hold_reason not in publication_reasons:
            raise P0ActualContractError("HOLD B reason family mismatch")
        if row["inference_decision"] == "ABSTAIN" and "publication_abstain_hold" not in publication_reasons:
            raise P0ActualContractError("ABSTAIN requires publication hold reason")
    if row["action_applied"] is not False or row["operational_effect"] != OPERATIONAL_EFFECT:
        raise P0ActualContractError("B context foundation must be no-write shadow only")
    _self_hash(row, "row_sha256", "B sense context")
    return dict(row)


def validate_actual_b_sense_context(value: Any) -> dict[str, Any]:
    return _validate_b_context(value, ACTUAL_ORIGIN)


def _event_sha(row: Mapping[str, Any]) -> str:
    return canonical_sha256(
        {
            key: item
            for key, item in row.items()
            if key not in {"event_sha256", "row_sha256"}
        }
    )


def _validate_annotation_event(value: Any, expected_origin: str) -> dict[str, Any]:
    row = _strict(value, _ANNOTATION_EVENT_FIELDS, "annotation event")
    if row["schema_version"] != ANNOTATION_EVENT_SCHEMA:
        raise P0ActualContractError("annotation event schema mismatch")
    _origin(row, expected_origin)
    for field in (
        "journal_id",
        "event_id",
        "target_record_type",
        "target_id",
        "reviewer_role",
        "guideline_path",
        "guideline_version",
    ):
        _text(row[field], field)
    sequence = row["journal_sequence"]
    if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 1:
        raise P0ActualContractError("journal_sequence is invalid")
    previous_id = _optional_text(row["previous_event_id"], "previous_event_id")
    previous_sha = _optional_sha(row["previous_event_sha256"], "previous_event_sha256")
    if sequence == 1 and (previous_id is not None or previous_sha is not None):
        raise P0ActualContractError("first annotation event must not carry previous event")
    if sequence > 1 and (previous_id is None or previous_sha is None):
        raise P0ActualContractError("later annotation event requires previous chain binding")
    if row["target_record_type"] not in {"B_SENSE_CONTEXT", "A_CONTEXT", "SOURCE_CLAIM"}:
        raise P0ActualContractError("annotation target type is invalid")
    _sha(row["target_subject_sha256"], "target_subject_sha256")
    _sha(row["reviewer_pseudonym_sha256"], "reviewer_pseudonym_sha256")
    _sha(row["reviewer_principal_sha256"], "reviewer_principal_sha256")
    _sha(
        row["reviewer_assignment_receipt_sha256"],
        "reviewer_assignment_receipt_sha256",
    )
    if row["reviewer_role"] != "HUMAN_CURATOR" or not isinstance(row["independent_review"], bool):
        raise P0ActualContractError("annotation reviewer contract mismatch")
    _sha(row["guideline_sha256"], "guideline_sha256")
    if row["event_kind"] not in {"PRIMARY_REVIEW", "INTRA_RATER_RECHECK"}:
        raise P0ActualContractError("annotation event_kind is invalid")
    supersedes = _sorted_texts(
        row["supersedes_event_ids"], "supersedes_event_ids", allow_empty=True
    )
    if row["event_kind"] == "PRIMARY_REVIEW":
        if supersedes or row["independent_review"] is not True:
            raise P0ActualContractError("primary review independence contract mismatch")
    elif not supersedes or row["independent_review"] is not False:
        raise P0ActualContractError("intra-rater recheck must supersede without a new vote")
    occurred = _timestamp(row["occurred_at"], "occurred_at")
    cutoff = _timestamp(row["evidence_cutoff"], "evidence_cutoff")
    if cutoff > occurred:
        raise P0ActualContractError("annotation evidence cutoff must not follow event")
    _sorted_texts(row["evidence_claim_ids"], "evidence_claim_ids")
    if row["annotation_status"] not in ANNOTATION_STATUSES:
        raise P0ActualContractError("annotation event status is invalid")
    if row["decision_kind"] not in B_TRUTH_KINDS:
        raise P0ActualContractError("annotation decision_kind is invalid")
    _sha(row["decision_payload_sha256"], "decision_payload_sha256")
    decision_sense = _optional_text(row["decision_sense_id"], "decision_sense_id")
    reasons = _reasons(
        row["reason_codes"],
        "reason_codes",
        _B_TRUTH_REASONS | _B_ANNOTATION_REASONS,
    )
    if row["annotation_status"] == "JUDGED":
        expected_reason = {
            "SENSE_ID": "truth_existing_sense_confirmed",
            "NEW_SENSE": "truth_new_sense_confirmed",
            "NON_TERM": "truth_non_term_confirmed",
        }.get(row["decision_kind"])
        if expected_reason is None or reasons != [expected_reason]:
            raise P0ActualContractError("judged event decision/reason mismatch")
    elif row["decision_kind"] != "UNRESOLVED" or not set(reasons).issubset(
        _B_ANNOTATION_REASONS
    ):
        raise P0ActualContractError("unresolved event decision/reason mismatch")
    if (row["decision_kind"] == "SENSE_ID") != (decision_sense is not None):
        raise P0ActualContractError("annotation decision sense binding mismatch")
    if row["action_applied"] is not False or row["operational_effect"] != OPERATIONAL_EFFECT:
        raise P0ActualContractError("annotation event must be no-write shadow only")
    if _sha(row["event_sha256"], "event_sha256") != _event_sha(row):
        raise P0ActualContractError("annotation event_sha256 mismatch")
    _self_hash(row, "row_sha256", "annotation event")
    return dict(row)


def validate_actual_annotation_event(value: Any) -> dict[str, Any]:
    return _validate_annotation_event(value, ACTUAL_ORIGIN)


def _validate_lineage(rows: Sequence[Mapping[str, Any]]) -> None:
    by_id = {row["registry_record_id"]: row for row in rows}
    if len(by_id) != len(rows):
        raise P0ActualContractError("registry_record_id must be unique")
    if len({row["snapshot_id"] for row in rows}) != len(rows):
        raise P0ActualContractError("snapshot_id must be unique")
    root_groups: set[str] = set()
    for row in rows:
        parent_id = row["parent_registry_record_id"]
        if parent_id is None:
            if row["independence_status"] == "ELIGIBLE_ROOT":
                if row["independence_group_id"] in root_groups:
                    raise P0ActualContractError("eligible roots require unique independence groups")
                root_groups.add(row["independence_group_id"])
            continue
        if parent_id not in by_id or parent_id == row["registry_record_id"]:
            raise P0ActualContractError("lineage parent is missing or self-referential")
        parent = by_id[parent_id]
        if row["derivation_kind"] == "TEMPORAL_REVISION" and row["source_id"] != parent[
            "source_id"
        ]:
            raise P0ActualContractError("temporal revision must preserve logical source_id")
        if (
            row["lineage_root_id"] != parent["lineage_root_id"]
            or row["independence_group_id"] != parent["independence_group_id"]
        ):
            raise P0ActualContractError("derived lineage root/group mismatch")
        if row["derivation_kind"] == "MIRROR" and row["response_sha256"] != parent[
            "response_sha256"
        ]:
            raise P0ActualContractError("mirror must preserve parent response hash")
        seen = {row["registry_record_id"]}
        cursor = parent
        while cursor["parent_registry_record_id"] is not None:
            if cursor["registry_record_id"] in seen:
                raise P0ActualContractError("source lineage contains a cycle")
            seen.add(cursor["registry_record_id"])
            cursor = by_id.get(cursor["parent_registry_record_id"])
            if cursor is None:
                raise P0ActualContractError("source lineage ancestor is missing")
        if cursor["registry_record_id"] != row["lineage_root_id"]:
            raise P0ActualContractError("lineage_root_id does not resolve to root")


def _validate_event_chains(events: Sequence[Mapping[str, Any]]) -> None:
    by_event = {row["event_id"]: row for row in events}
    if len(by_event) != len(events):
        raise P0ActualContractError("annotation event_id must be unique")
    by_journal: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in events:
        by_journal[row["journal_id"]].append(row)
    for journal_rows in by_journal.values():
        ordered = sorted(journal_rows, key=lambda row: row["journal_sequence"])
        if [row["journal_sequence"] for row in ordered] != list(range(1, len(ordered) + 1)):
            raise P0ActualContractError("annotation journal sequence must be contiguous")
        for index, row in enumerate(ordered):
            for superseded_id in row["supersedes_event_ids"]:
                superseded = by_event.get(superseded_id)
                if (
                    superseded is None
                    or superseded["journal_id"] != row["journal_id"]
                    or superseded["journal_sequence"] >= row["journal_sequence"]
                    or superseded["target_record_type"] != row["target_record_type"]
                    or superseded["target_id"] != row["target_id"]
                    or superseded["reviewer_principal_sha256"]
                    != row["reviewer_principal_sha256"]
                ):
                    raise P0ActualContractError("annotation supersedes binding mismatch")
            if index == 0:
                continue
            previous = ordered[index - 1]
            if (
                row["previous_event_id"] != previous["event_id"]
                or row["previous_event_sha256"] != previous["event_sha256"]
                or row["target_record_type"] != previous["target_record_type"]
                or row["target_id"] != previous["target_id"]
                or row["target_subject_sha256"] != previous["target_subject_sha256"]
                or _timestamp(row["occurred_at"], "occurred_at")
                <= _timestamp(previous["occurred_at"], "occurred_at")
            ):
                raise P0ActualContractError("annotation journal previous-event chain mismatch")


def _validate_bundle(
    snapshots: Sequence[Mapping[str, Any]],
    claims: Sequence[Mapping[str, Any]],
    b_contexts: Sequence[Mapping[str, Any]],
    events: Sequence[Mapping[str, Any]],
    *,
    expected_origin: str,
    artifact_bindings: Mapping[str, str] | None = None,
    payload_text_by_registry: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    source_rows = [_validate_source_snapshot(row, expected_origin) for row in snapshots]
    by_registry = {row["registry_record_id"]: row for row in source_rows}
    if len(by_registry) != len(source_rows):
        raise P0ActualContractError("registry_record_id must be unique")
    claim_rows: list[dict[str, Any]] = []
    for value in claims:
        if not isinstance(value, Mapping) or value.get("registry_record_id") not in by_registry:
            raise P0ActualContractError("claim references unknown registry record")
        source = by_registry[value["registry_record_id"]]
        row = _validate_source_claim(
            value,
            expected_origin,
            response_sha256=source["response_sha256"],
        )
        if (
            row["registry_record_sha256"] != source["registry_record_sha256"]
            or row["snapshot_id"] != source["snapshot_id"]
        ):
            raise P0ActualContractError("claim/registry snapshot binding mismatch")
        expected_profile = source["source_profile"].lower()
        if row["parser_profile"] != expected_profile:
            raise P0ActualContractError("claim parser/source profile mismatch")
        if source["source_profile"] == "GENERIC_FALLBACK" and row["claim_kind"] != "UNKNOWN":
            raise P0ActualContractError("generic source must remain UNKNOWN claim")
        if payload_text_by_registry is not None:
            payload_text = payload_text_by_registry.get(source["registry_record_id"])
            if payload_text is None:
                raise P0ActualContractError("claim source lacks replayable controlled payload")
            if (
                row["span_end"] > len(payload_text)
                or payload_text[row["span_start"] : row["span_end"]] != row["span_text"]
            ):
                raise P0ActualContractError("claim span does not match controlled payload")
        claim_rows.append(row)
    by_claim = {row["claim_id"]: row for row in claim_rows}
    if len(by_claim) != len(claim_rows):
        raise P0ActualContractError("claim_id must be unique")
    claim_units = {
        (
            row["registry_record_id"],
            row["span_start"],
            row["span_end"],
            row["claim_kind"],
            row["claim_direction"],
            row["normalized_surface"],
            row["target_work_id"],
            row["target_sense_id"],
            row["definition"],
        )
        for row in claim_rows
    }
    if len(claim_units) != len(claim_rows):
        raise P0ActualContractError("source claim sampling unit must be unique")
    context_rows = [_validate_b_context(row, expected_origin) for row in b_contexts]
    event_rows = [_validate_annotation_event(row, expected_origin) for row in events]
    _validate_lineage(source_rows)
    _validate_event_chains(event_rows)
    target_journals: dict[tuple[str, str], set[str]] = defaultdict(set)
    for event_row in event_rows:
        target_journals[
            (event_row["target_record_type"], event_row["target_id"])
        ].add(event_row["journal_id"])
    if any(len(journals) != 1 for journals in target_journals.values()):
        raise P0ActualContractError("annotation subject must have one authoritative journal")
    by_event = {row["event_id"]: row for row in event_rows}
    if len({row["context_id"] for row in context_rows}) != len(context_rows):
        raise P0ActualContractError("B context_id must be unique")
    context_ids = {row["context_id"] for row in context_rows}
    for event_row in event_rows:
        if event_row["target_record_type"] != "B_SENSE_CONTEXT":
            raise P0ActualContractError(
                "actual-P0 B foundation annotation event must target B_SENSE_CONTEXT"
            )
        if event_row["target_id"] not in context_ids:
            raise P0ActualContractError(
                "annotation event targets unknown B context (orphan event)"
            )
    context_units = {
        (
            row["post_id"],
            row["content_fingerprint"],
            row["normalized_surface"],
            row["surface_start"],
            row["surface_end"],
        )
        for row in context_rows
    }
    if len(context_units) != len(context_rows):
        raise P0ActualContractError("B context sampling unit must be unique")
    for context in context_rows:
        referenced = set(context["truth_source_claim_ids"]) | set(
            context["inference_source_claim_ids"]
        )
        missing = sorted(referenced - set(by_claim))
        if missing:
            raise P0ActualContractError(f"B context references unknown claims: {missing}")
        if any(by_claim[claim_id]["track"] != "B" for claim_id in referenced):
            raise P0ActualContractError("B context may reference only track-B claims")
        if any(
            by_claim[claim_id]["normalized_surface"] != context["normalized_surface"]
            for claim_id in referenced
        ):
            raise P0ActualContractError("B context/source surface binding mismatch")
        if any(
            (
                by_registry[by_claim[claim_id]["registry_record_id"]]["platform"]
                != context["platform_scope"]
                or by_registry[by_claim[claim_id]["registry_record_id"]][
                    "community_scope"
                ]
                != context["community_scope"]
            )
            for claim_id in referenced
        ):
            raise P0ActualContractError("B context/source community scope mismatch")
        truth_claim_rows = [by_claim[claim_id] for claim_id in context["truth_source_claim_ids"]]
        if context["truth_claim_set_sha256"] != _claim_set_sha(truth_claim_rows):
            raise P0ActualContractError("B truth claim set binding mismatch")
        truth_supported = {
            "SENSE_ID": any(
                row["claim_kind"] == "COMMUNITY_SENSE"
                and row["target_sense_id"] == context["truth_sense_id"]
                and row["definition"] == context["definition"]
                for row in truth_claim_rows
            ),
            "NEW_SENSE": any(
                row["claim_kind"] == "NEW_SENSE_CANDIDATE"
                and row["definition"] == context["definition"]
                for row in truth_claim_rows
            ),
            "NON_TERM": any(
                row["claim_kind"] == "NON_TERM_EVIDENCE" for row in truth_claim_rows
            ),
            "UNRESOLVED": any(
                row["claim_kind"] == "UNKNOWN" for row in truth_claim_rows
            ),
        }[context["truth_kind"]]
        if not truth_supported:
            raise P0ActualContractError("B truth lacks claim-kind/target/definition support")
        inference_claim_rows = [
            by_claim[claim_id] for claim_id in context["inference_source_claim_ids"]
        ]
        if context["inference_claim_set_sha256"] != _claim_set_sha(
            inference_claim_rows
        ):
            raise P0ActualContractError("B inference claim set binding mismatch")
        inference_supported = {
            "ASSERT_SENSE": any(
                row["claim_kind"] == "COMMUNITY_SENSE"
                and row["target_sense_id"] == context["inference_sense_id"]
                for row in inference_claim_rows
            ),
            "ASSERT_NEW_SENSE": any(
                row["claim_kind"] == "NEW_SENSE_CANDIDATE"
                for row in inference_claim_rows
            ),
            "ASSERT_NON_TERM": any(
                row["claim_kind"] == "NON_TERM_EVIDENCE"
                for row in inference_claim_rows
            ),
            "ABSTAIN": any(
                row["claim_kind"] == "UNKNOWN" for row in inference_claim_rows
            ),
        }[context["inference_decision"]]
        if not inference_supported:
            raise P0ActualContractError("B inference lacks claim-kind/target support")
        for claim_id in referenced:
            source = by_registry[by_claim[claim_id]["registry_record_id"]]
            cutoff_field = (
                "inference_evidence_cutoff"
                if claim_id in context["inference_source_claim_ids"]
                else "truth_evidence_cutoff"
            )
            if _timestamp(source["collected_at"], "collected_at") > _timestamp(
                context[cutoff_field], cutoff_field
            ):
                raise P0ActualContractError("B context uses evidence collected after cutoff")
        event = by_event.get(context["annotation_event_id"])
        if event is None or (
            event["target_record_type"] != "B_SENSE_CONTEXT"
            or event["target_id"] != context["context_id"]
            or event["target_subject_sha256"] != context["annotation_subject_sha256"]
            or event["annotation_status"] != context["annotation_status"]
            or event["decision_kind"] != context["truth_kind"]
            or event["decision_sense_id"] != context["truth_sense_id"]
            or event["decision_payload_sha256"] != _decision_payload_sha(context)
            or event["evidence_claim_ids"] != context["truth_source_claim_ids"]
            or event["evidence_cutoff"] != context["truth_evidence_cutoff"]
        ):
            raise P0ActualContractError("B context/latest annotation event binding mismatch")
        journal_events = [row for row in event_rows if row["journal_id"] == event["journal_id"]]
        if event["journal_sequence"] != max(row["journal_sequence"] for row in journal_events):
            raise P0ActualContractError("B context must reference latest annotation event")
        if context["publication_action"] == "PUBLISH":
            evidence_sources = [
                by_registry[by_claim[claim_id]["registry_record_id"]]
                for claim_id in context["truth_source_claim_ids"]
            ]
            if not evidence_sources or any(
                not source["publication_evidence_eligible"] for source in evidence_sources
            ):
                raise P0ActualContractError("PUBLISH B context requires eligible source rights")
            supporting_claims = [
                by_claim[claim_id]
                for claim_id in context["truth_source_claim_ids"]
                if by_claim[claim_id]["claim_kind"] == "COMMUNITY_SENSE"
                and by_claim[claim_id]["target_sense_id"] == context["public_sense_id"]
                and by_claim[claim_id]["definition"] == context["public_definition"]
            ]
            if not supporting_claims:
                raise P0ActualContractError("PUBLISH B context lacks selected-sense claim support")

    if artifact_bindings is None:
        bindings: dict[str, str | None] = {
            "source_snapshots_sha256": None,
            "source_claims_sha256": None,
            "b_sense_contexts_sha256": None,
            "annotation_events_sha256": None,
            "manifest_sha256": None,
        }
        artifact_verified = False
    else:
        expected = {
            "source_snapshots_sha256",
            "source_claims_sha256",
            "b_sense_contexts_sha256",
            "annotation_events_sha256",
            "manifest_sha256",
        }
        if set(artifact_bindings) != expected:
            raise P0ActualContractError("artifact binding fields mismatch")
        bindings = {key: _sha(artifact_bindings[key], key) for key in sorted(expected)}
        artifact_verified = True
    payload_verified = payload_text_by_registry is not None
    example_schema_pass = (
        expected_origin == EXAMPLE_ORIGIN and artifact_verified and payload_verified
    )
    material = {
        "schema_version": RECEIPT_SCHEMA,
        "record_origin": expected_origin,
        "gate_status": "NO_GO_ACTUAL_P0_NOT_STARTED",
        "schema_check_status": (
            "PASS_ACTUAL_SCHEMA_CONTRACT_EXAMPLE_ONLY"
            if example_schema_pass
            else "STRUCTURE_VALID_NO_DURABLE_AUTHORITY"
        ),
        "actual_gate_status": "NO_GO_ACTUAL_P0_NOT_STARTED",
        "metric_status": "METRICS_NOT_ESTIMABLE",
        "review_status": "REVIEW_LOCKED",
        "full_scan_approval": False,
        "p0_phase_exit": False,
        "source_snapshot_count": len(source_rows),
        "source_claim_count": len(claim_rows),
        "eligible_independence_group_count": len(
            {
                row["independence_group_id"]
                for row in source_rows
                if row["independence_status"] == "ELIGIBLE_ROOT"
            }
        ),
        "b_sense_context_count": len(context_rows),
        "annotation_event_count": len(event_rows),
        "actual_source_claim_count": 0,
        "actual_a_context_review_count": 0,
        "artifact_binding_verified": artifact_verified,
        "payload_binding_verified": payload_verified,
        "capture_authority_verified": False,
        "rights_policy_authority_verified": False,
        "annotation_append_only_verified": False,
        "guideline_authority_verified": False,
        "reviewer_assignment_authority_verified": False,
        "candidate_registry_authority_verified": False,
        "novelty_authority_verified": False,
        "runtime_noninterference_verified": False,
        "actual_pilot_manifest_verified": False,
        "authority": "SHADOW_ONLY",
        "public_apply": False,
        "central_slang_db_write": False,
        "publication_wal_write": False,
        "blockers": [
            "ACTUAL_A_CONTEXT_REVIEWS_0_OF_20",
            "ACTUAL_CAPTURE_AND_RIGHTS_POLICY_AUTHORITY_NOT_VERIFIED",
            "ACTUAL_GUIDELINE_REVIEWER_CANDIDATE_NOVELTY_AUTHORITY_NOT_VERIFIED",
            "ACTUAL_ANNOTATION_APPEND_ONLY_PREFIX_NOT_VERIFIED",
            "ACTUAL_P0_MANIFEST_AND_RUNTIME_AUDIT_NOT_IMPLEMENTED",
            "ACTUAL_SEMANTIC_REVIEW_NOT_COMPLETE",
        ],
        **bindings,
    }
    return {**material, "receipt_sha256": canonical_sha256(material)}


def validate_actual_foundation_bundle(
    snapshots: Sequence[Mapping[str, Any]],
    claims: Sequence[Mapping[str, Any]],
    b_contexts: Sequence[Mapping[str, Any]],
    events: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Validate actual-origin rows but never grant actual-P0 approval."""
    return _validate_bundle(
        snapshots,
        claims,
        b_contexts,
        events,
        expected_origin=ACTUAL_ORIGIN,
    )


def jsonl_bytes(rows: Iterable[Mapping[str, Any]]) -> bytes:
    return b"".join(canonical_bytes(row) + b"\n" for row in rows)


def _file_ref(path: Path, rows: int) -> dict[str, Any]:
    return {
        "path": path.name,
        "rows": rows,
        "bytes": path.stat().st_size,
        "sha256": file_sha256(path),
    }


def build_example_manifest(
    *,
    snapshot_path: Path,
    claim_path: Path,
    b_context_path: Path,
    event_path: Path,
    counts: Mapping[str, int],
) -> dict[str, Any]:
    material = {
        "schema_version": EXAMPLE_MANIFEST_SCHEMA,
        "record_origin": EXAMPLE_ORIGIN,
        "source_snapshots": _file_ref(snapshot_path, counts["source_snapshots"]),
        "source_claims": _file_ref(claim_path, counts["source_claims"]),
        "b_sense_contexts": _file_ref(b_context_path, counts["b_sense_contexts"]),
        "annotation_events": _file_ref(event_path, counts["annotation_events"]),
        "gate_scope": "ACTUAL_SCHEMA_CONTRACT_EXAMPLE_ONLY_METRICS_NOT_ESTIMABLE",
        "authority": "SHADOW_ONLY",
        "public_apply": False,
        "central_slang_db_write": False,
        "publication_wal_write": False,
        "actual_a_context_reviews": 0,
        "p0_phase_exit": False,
    }
    return {**material, "manifest_sha256": canonical_sha256(material)}


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise P0ActualContractError(f"duplicate JSON key: {key}")
        output[key] = value
    return output


def _stable_bytes(path: Path) -> bytes:
    before = path.stat()
    data = path.read_bytes()
    after = path.stat()
    before_id = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
    after_id = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
    if before_id != after_id or len(data) != after.st_size:
        raise P0ActualContractError(f"artifact changed during validation: {path.name}")
    return data


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        text = _stable_bytes(path).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise P0ActualContractError(f"JSONL must be UTF-8: {path.name}") from exc
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            raise P0ActualContractError(f"blank JSONL line at {line_number}")
        try:
            row = json.loads(line, object_pairs_hook=_reject_duplicate_pairs)
        except json.JSONDecodeError as exc:
            raise P0ActualContractError(f"invalid JSONL line {line_number}") from exc
        if not isinstance(row, dict):
            raise P0ActualContractError(f"JSONL line {line_number} must be an object")
        rows.append(row)
    return rows


def validate_example_directory(directory: str | Path) -> dict[str, Any]:
    """Validate the bound contract-example directory; never approve actual P0."""
    root = Path(directory).resolve()
    manifest_path = root / "p0_actual_contract_example_manifest_v1.json"
    try:
        manifest_value = json.loads(
            _stable_bytes(manifest_path).decode("utf-8"),
            object_pairs_hook=_reject_duplicate_pairs,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise P0ActualContractError("example manifest must be canonical UTF-8 JSON") from exc
    manifest = _strict(manifest_value, _MANIFEST_FIELDS, "example manifest")
    if (
        manifest["schema_version"] != EXAMPLE_MANIFEST_SCHEMA
        or manifest["record_origin"] != EXAMPLE_ORIGIN
        or manifest["gate_scope"]
        != "ACTUAL_SCHEMA_CONTRACT_EXAMPLE_ONLY_METRICS_NOT_ESTIMABLE"
        or manifest["authority"] != "SHADOW_ONLY"
        or manifest["public_apply"] is not False
        or manifest["central_slang_db_write"] is not False
        or manifest["publication_wal_write"] is not False
        or manifest["actual_a_context_reviews"] != 0
        or manifest["p0_phase_exit"] is not False
    ):
        raise P0ActualContractError("example manifest approval boundary mismatch")
    _self_hash(manifest, "manifest_sha256", "example manifest")
    paths: dict[str, Path] = {}
    expected_names = {
        "source_snapshots": "p0_source_snapshot_registry_example_v1.jsonl",
        "source_claims": "p0_source_claim_example_v1.jsonl",
        "b_sense_contexts": "p0_b_sense_contract_example_v1.jsonl",
        "annotation_events": "p0_annotation_events_example_v1.jsonl",
    }
    for field, expected_name in expected_names.items():
        ref = manifest[field]
        if not isinstance(ref, Mapping) or set(ref) != {"path", "rows", "bytes", "sha256"}:
            raise P0ActualContractError(f"{field} file ref mismatch")
        name = _text(ref["path"], f"{field}.path")
        if Path(name).name != name or name != expected_name:
            raise P0ActualContractError(f"{field}.path must use fixed contract basename")
        path = (root / name).resolve()
        if path.parent != root or path.is_symlink() or not path.is_file():
            raise P0ActualContractError(f"{field} file is missing")
        if (
            isinstance(ref["rows"], bool)
            or not isinstance(ref["rows"], int)
            or ref["rows"] <= 0
            or ref["bytes"] != path.stat().st_size
            or _sha(ref["sha256"], f"{field}.sha256") != file_sha256(path)
        ):
            raise P0ActualContractError(f"{field} file binding mismatch")
        paths[field] = path
    loaded = {field: _load_jsonl(path) for field, path in paths.items()}
    for field, rows in loaded.items():
        if len(rows) != manifest[field]["rows"]:
            raise P0ActualContractError(f"{field} row count mismatch")
    payload_text_by_registry: dict[str, str] = {}
    for snapshot in loaded["source_snapshots"]:
        if snapshot.get("retention_class") != "CONTROLLED_RAW":
            continue
        registry_id = snapshot.get("registry_record_id")
        payload_ref = snapshot.get("payload_ref")
        if not isinstance(registry_id, str) or not isinstance(payload_ref, str):
            raise P0ActualContractError("controlled payload binding is incomplete")
        payload_path = (root / payload_ref).resolve()
        if root not in payload_path.parents or payload_path.is_symlink() or not payload_path.is_file():
            raise P0ActualContractError("payload_ref escapes or is not a regular file")
        payload_bytes = _stable_bytes(payload_path)
        if (
            len(payload_bytes) != snapshot.get("response_bytes")
            or hashlib.sha256(payload_bytes).hexdigest() != snapshot.get("response_sha256")
        ):
            raise P0ActualContractError("controlled payload response binding mismatch")
        try:
            payload_text = payload_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise P0ActualContractError("controlled payload must be UTF-8") from exc
        if (
            snapshot.get("normalization_version") != "utf8_identity_v1"
            or hashlib.sha256(payload_text.encode("utf-8")).hexdigest()
            != snapshot.get("normalized_text_sha256")
        ):
            raise P0ActualContractError("controlled payload normalization binding mismatch")
        payload_text_by_registry[registry_id] = payload_text
    return _validate_bundle(
        loaded["source_snapshots"],
        loaded["source_claims"],
        loaded["b_sense_contexts"],
        loaded["annotation_events"],
        expected_origin=EXAMPLE_ORIGIN,
        artifact_bindings={
            "source_snapshots_sha256": file_sha256(paths["source_snapshots"]),
            "source_claims_sha256": file_sha256(paths["source_claims"]),
            "b_sense_contexts_sha256": file_sha256(paths["b_sense_contexts"]),
            "annotation_events_sha256": file_sha256(paths["annotation_events"]),
            "manifest_sha256": manifest["manifest_sha256"],
        },
        payload_text_by_registry=payload_text_by_registry,
    )
