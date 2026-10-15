"""P0 source-lineage and four-axis annotation contract.

This module is a standalone, synthetic-fixture contract.  It neither imports
nor writes the publication WAL, runtime pipeline, or Slang DB.  The fixture is
only evidence that the P0 schema and fail-closed invariants are executable; it
is not actual source review or semantic-performance evidence.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import urlsplit


SOURCE_CLAIM_SCHEMA = "p0_source_claim_v1"
CONTEXT_DECISION_SCHEMA = "p0_context_decision_v1"
FIXTURE_MANIFEST_SCHEMA = "p0_grounding_contract_fixture_manifest_v1"
VALIDATION_RECEIPT_SCHEMA = "p0_grounding_contract_validation_receipt_v1"
FIXTURE_ORIGIN = "SYNTHETIC_CONTRACT_ONLY"
OPERATIONAL_EFFECT = "NONE_SHADOW_ONLY"

SOURCE_PROFILES = (
    "OFFICIAL_STRUCTURED",
    "COMMUNITY_STRUCTURED",
    "MEDIA_OCR",
    "GENERIC_FALLBACK",
)
TRACKS = ("A", "B")
ANNOTATION_STATUSES = ("JUDGED", "UNJUDGED", "UNAVAILABLE")
INFERENCE_DECISIONS = ("ASSERT_WORK", "ASSERT_NIL", "ABSTAIN")
PUBLICATION_ACTIONS = ("PUBLISH", "HOLD", "REJECT")

AUTHOR_UNKNOWN_REASONS = frozenset(
    {
        "anonymous_source",
        "author_not_exposed",
        "source_deleted",
        "platform_access_restricted",
    }
)
TIME_UNKNOWN_REASONS = frozenset(
    {
        "source_time_not_exposed",
        "source_modified_time_not_exposed",
        "source_deleted",
        "platform_access_restricted",
    }
)
TRUTH_REASON_CODES = frozenset(
    {
        "truth_direct_official_id",
        "truth_explicit_alias_relation",
        "truth_context_work_relation",
        "truth_nil_non_work",
        "truth_nil_out_of_universe",
        "truth_nil_no_canonical_target_after_complete_enumeration",
    }
)
ANNOTATION_REASON_CODES = frozenset(
    {
        "annotation_human_review_completed",
        "annotation_synthetic_contract_example",
        "annotation_alias_sense_unresolved",
        "annotation_multiwork_primary_unresolved",
        "annotation_conflicting_evidence",
        "annotation_insufficient_context",
        "evidence_source_deleted",
        "evidence_access_restricted",
        "evidence_retrieval_unavailable",
        "evidence_ocr_unavailable",
        "evidence_snapshot_mismatch",
    }
)
INFERENCE_REASON_CODES = frozenset(
    {
        "inference_candidate_selected",
        "inference_complete_candidate_universe_nil",
        "retrieval_failclose_requires_abstain",
        "candidate_set_integrity_requires_abstain",
        "selective_risk_threshold_requires_abstain",
        "nil_threshold_requires_abstain",
        "rerank_unavailable_requires_abstain",
        "multiwork_role_conflict_requires_abstain",
        "source_lineage_unbound_requires_abstain",
        "temporal_snapshot_unbound_requires_abstain",
    }
)
PUBLICATION_REASON_CODES = frozenset(
    {
        "publication_evidence_verified",
        "publication_abstain_hold",
        "publication_unavailable_hold",
        "publication_unjudged_hold",
        "publication_nil_reject",
        "publication_selective_risk_hold",
        "publication_required_search_unrecovered",
        "publication_wrong_work_blocked",
        "publication_existing_wal_no_write",
    }
)
NIL_REASONS = frozenset(
    {
        "NIL_NON_WORK",
        "NIL_OUT_OF_UNIVERSE",
        "NIL_NO_VALID_CANDIDATE",
    }
)
ABSTAIN_BLOCKERS = frozenset(
    {
        "retrieval_failclose_requires_abstain",
        "candidate_set_integrity_requires_abstain",
        "selective_risk_threshold_requires_abstain",
        "nil_threshold_requires_abstain",
        "rerank_unavailable_requires_abstain",
        "multiwork_role_conflict_requires_abstain",
        "source_lineage_unbound_requires_abstain",
        "temporal_snapshot_unbound_requires_abstain",
    }
)

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SOURCE_FIELDS = frozenset(
    {
        "schema_version",
        "fixture_origin",
        "claim_id",
        "track",
        "source_profile",
        "source_id",
        "community_scope",
        "platform",
        "canonical_url",
        "locator",
        "item_locator",
        "lineage_root_id",
        "parent_source_id",
        "derivation_kind",
        "independence_group_id",
        "independence_status",
        "author",
        "author_unknown_reason",
        "published_at",
        "published_at_unknown_reason",
        "modified_at",
        "modified_at_unknown_reason",
        "collected_at",
        "http_status",
        "content_type",
        "response_text",
        "response_sha256",
        "response_bytes",
        "content_sha256",
        "span_start",
        "span_end",
        "span_text",
        "span_sha256",
        "claim_direction",
        "surface_text",
        "target_text",
        "target_work_id",
        "claim_kind",
        "parse_disposition",
        "parser_profile",
        "parser_version",
        "parser_route",
        "repair_mode",
        "repair_output_text",
        "repair_source_span_sha256",
        "rights_status",
        "rights_basis",
        "source_record_sha256",
        "snapshot_id",
        "snapshot_regime",
        "snapshot_sha256",
        "action_applied",
        "operational_effect",
        "row_sha256",
    }
)
_CONTEXT_FIELDS = frozenset(
    {
        "schema_version",
        "fixture_origin",
        "context_id",
        "track",
        "post_id",
        "content_text",
        "content_fingerprint",
        "source_claim_ids",
        "snapshot_id",
        "canonical_universe_work_ids",
        "canonical_universe_sha256",
        "candidate_work_ids",
        "candidate_canonical_urls",
        "candidate_set_fingerprint",
        "producer_status",
        "retrieval_status",
        "candidate_integrity_status",
        "truth_kind",
        "truth_work_id",
        "truth_nil_reason",
        "truth_reason_codes",
        "annotation_status",
        "annotation_reason_codes",
        "inference_decision",
        "inference_work_id",
        "inference_reason_codes",
        "publication_action",
        "public_work_id",
        "public_url",
        "publication_reason_codes",
        "canonical_work_receipt_sha256",
        "post_relation_receipt_sha256",
        "nil_receipt_sha256",
        "action_applied",
        "operational_effect",
        "row_sha256",
    }
)
_MANIFEST_FIELDS = frozenset(
    {
        "schema_version",
        "fixture_origin",
        "source_claims",
        "context_decisions",
        "profile_counts",
        "track_counts",
        "required_independence_groups",
        "gate_scope",
        "authority",
        "public_apply",
        "central_slang_db_write",
        "publication_wal_write",
        "external_retriever",
        "core_dependency_delta",
        "noninterference_contract_scope",
        "action_applied",
        "operational_effect",
        "manifest_sha256",
    }
)


class P0GroundingContractError(ValueError):
    """Raised when a P0 contract record is structurally invalid."""


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


def _strict_fields(value: Mapping[str, Any], expected: frozenset[str], label: str) -> None:
    if set(value) != expected:
        missing = sorted(expected - set(value))
        extra = sorted(set(value) - expected)
        raise P0GroundingContractError(
            f"{label} fields mismatch: missing={missing}, extra={extra}"
        )


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise P0GroundingContractError(f"{field} must be non-empty text")
    if value != value.strip():
        raise P0GroundingContractError(f"{field} must be canonical text without edge whitespace")
    return value


def _optional_text(value: Any, field: str) -> str | None:
    if value is None:
        return None
    return _text(value, field)


def _https_url(value: Any, field: str) -> str:
    text = _text(value, field)
    try:
        parsed = urlsplit(text)
        hostname = parsed.hostname
        parsed.port
    except ValueError as exc:
        raise P0GroundingContractError(
            f"{field} must be a valid https URL with a hostname"
        ) from exc
    if (
        parsed.scheme.lower() != "https"
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise P0GroundingContractError(
            f"{field} must be a valid https URL with a hostname"
        )
    return text


def _sha(value: Any, field: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise P0GroundingContractError(f"{field} must be lowercase sha256")
    return value


def _optional_sha(value: Any, field: str) -> str | None:
    if value is None:
        return None
    return _sha(value, field)


def _timestamp(value: Any, field: str) -> datetime:
    text = _text(value, field)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise P0GroundingContractError(f"{field} must be RFC3339") from exc
    if parsed.tzinfo is None:
        raise P0GroundingContractError(f"{field} must include timezone")
    return parsed


def _value_or_unknown(
    value: Any,
    reason: Any,
    *,
    field: str,
    reasons: frozenset[str],
) -> str | None:
    if value is None:
        if reason not in reasons:
            raise P0GroundingContractError(f"{field} requires an allowlisted unknown reason")
        return None
    result = _text(value, field)
    if reason is not None:
        raise P0GroundingContractError(f"{field} value must not carry an unknown reason")
    return result


def _sorted_unique_texts(value: Any, field: str, *, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list):
        raise P0GroundingContractError(f"{field} must be a list")
    output = [_text(item, field) for item in value]
    if output != sorted(output) or len(output) != len(set(output)):
        raise P0GroundingContractError(f"{field} must be sorted and unique")
    if not allow_empty and not output:
        raise P0GroundingContractError(f"{field} must not be empty")
    return output


def _reason_codes(
    value: Any,
    field: str,
    allowed: frozenset[str],
    *,
    allow_empty: bool = False,
) -> list[str]:
    output = _sorted_unique_texts(value, field, allow_empty=allow_empty)
    unknown = sorted(set(output) - allowed)
    if unknown:
        raise P0GroundingContractError(f"{field} contains unregistered codes: {unknown}")
    return output


def _validate_self_hash(value: Mapping[str, Any], hash_field: str, field: str) -> None:
    row_hash = _sha(value[hash_field], hash_field)
    material = {key: item for key, item in value.items() if key != hash_field}
    if row_hash != canonical_sha256(material):
        raise P0GroundingContractError(f"{field} hash mismatch")


def with_row_hash(value: Mapping[str, Any]) -> dict[str, Any]:
    material = dict(value)
    material.pop("row_sha256", None)
    return {**material, "row_sha256": canonical_sha256(material)}


_SOURCE_RECORD_HASH_FIELDS = (
    "source_id",
    "source_profile",
    "community_scope",
    "platform",
    "canonical_url",
    "locator",
    "lineage_root_id",
    "parent_source_id",
    "derivation_kind",
    "independence_group_id",
    "independence_status",
    "author",
    "author_unknown_reason",
    "published_at",
    "published_at_unknown_reason",
    "modified_at",
    "modified_at_unknown_reason",
    "collected_at",
    "http_status",
    "content_type",
    "response_sha256",
    "response_bytes",
    "content_sha256",
    "parser_profile",
    "parser_version",
    "rights_status",
    "rights_basis",
    "snapshot_id",
    "snapshot_regime",
    "snapshot_sha256",
)


def source_record_sha256(value: Mapping[str, Any]) -> str:
    return canonical_sha256({field: value[field] for field in _SOURCE_RECORD_HASH_FIELDS})


def validate_source_claim(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise P0GroundingContractError("source claim must be an object")
    _strict_fields(value, _SOURCE_FIELDS, "source claim")
    if value["schema_version"] != SOURCE_CLAIM_SCHEMA:
        raise P0GroundingContractError("source claim schema mismatch")
    if value["fixture_origin"] != FIXTURE_ORIGIN:
        raise P0GroundingContractError("source fixture origin mismatch")
    if value["track"] not in TRACKS:
        raise P0GroundingContractError("source track is invalid")
    if value["source_profile"] not in SOURCE_PROFILES:
        raise P0GroundingContractError("source profile is invalid")
    for field in (
        "claim_id",
        "source_id",
        "community_scope",
        "platform",
        "canonical_url",
        "locator",
        "item_locator",
        "lineage_root_id",
        "independence_group_id",
        "content_type",
        "response_text",
        "span_text",
        "parser_profile",
        "parser_version",
        "parser_route",
        "rights_basis",
        "snapshot_id",
    ):
        _text(value[field], field)
    _https_url(value["canonical_url"], "canonical_url")
    expected_profile_contract = {
        "OFFICIAL_STRUCTURED": ("official_structured", "structured_profile", "application/json"),
        "COMMUNITY_STRUCTURED": ("community_structured", "structured_profile", "text/plain"),
        "MEDIA_OCR": ("media_ocr", "structured_profile", "text/plain"),
        "GENERIC_FALLBACK": ("generic_fallback", "generic_queue", "text/plain"),
    }[value["source_profile"]]
    actual_profile_contract = (
        value["parser_profile"],
        value["parser_route"],
        value["content_type"],
    )
    if actual_profile_contract != expected_profile_contract:
        raise P0GroundingContractError("source profile/parser/content-type contract mismatch")
    if value["parser_version"] != "p0-parser-contract-v1":
        raise P0GroundingContractError("synthetic parser version contract mismatch")
    _optional_text(value["parent_source_id"], "parent_source_id")
    if value["derivation_kind"] not in {
        "ORIGINAL",
        "MIRROR",
        "REPOST",
        "QUOTE",
        "OCR_DERIVED",
        "UNKNOWN_LINEAGE",
    }:
        raise P0GroundingContractError("derivation_kind is invalid")
    if value["independence_status"] not in {
        "ELIGIBLE_ROOT",
        "COLLAPSED_DERIVATIVE",
        "COLLAPSED_UNKNOWN_LINEAGE",
    }:
        raise P0GroundingContractError("independence_status is invalid")

    _value_or_unknown(
        value["author"],
        value["author_unknown_reason"],
        field="author",
        reasons=AUTHOR_UNKNOWN_REASONS,
    )
    published = _value_or_unknown(
        value["published_at"],
        value["published_at_unknown_reason"],
        field="published_at",
        reasons=TIME_UNKNOWN_REASONS,
    )
    modified = _value_or_unknown(
        value["modified_at"],
        value["modified_at_unknown_reason"],
        field="modified_at",
        reasons=TIME_UNKNOWN_REASONS,
    )
    collected_at = _timestamp(value["collected_at"], "collected_at")
    published_at = _timestamp(published, "published_at") if published is not None else None
    modified_at = _timestamp(modified, "modified_at") if modified is not None else None
    if published_at is not None and published_at > collected_at:
        raise P0GroundingContractError("published_at must not follow collected_at")
    if modified_at is not None and modified_at > collected_at:
        raise P0GroundingContractError("modified_at must not follow collected_at")
    if published_at is not None and modified_at is not None and published_at > modified_at:
        raise P0GroundingContractError("published_at must not follow modified_at")

    http_status = value["http_status"]
    response_bytes = value["response_bytes"]
    span_start = value["span_start"]
    span_end = value["span_end"]
    for item, field, minimum in (
        (http_status, "http_status", 100),
        (response_bytes, "response_bytes", 1),
        (span_start, "span_start", 0),
        (span_end, "span_end", 1),
    ):
        if isinstance(item, bool) or not isinstance(item, int) or item < minimum:
            raise P0GroundingContractError(f"{field} is invalid")
    if http_status > 599:
        raise P0GroundingContractError("http_status is invalid")
    response_text = value["response_text"]
    response_encoded = response_text.encode("utf-8")
    if response_bytes != len(response_encoded):
        raise P0GroundingContractError("response_bytes mismatch")
    if _sha(value["response_sha256"], "response_sha256") != hashlib.sha256(response_encoded).hexdigest():
        raise P0GroundingContractError("response_sha256 mismatch")
    if _sha(value["content_sha256"], "content_sha256") != canonical_sha256(response_text):
        raise P0GroundingContractError("content_sha256 mismatch")
    if span_end <= span_start or response_text[span_start:span_end] != value["span_text"]:
        raise P0GroundingContractError("span offsets/text mismatch")
    if _sha(value["span_sha256"], "span_sha256") != canonical_sha256(value["span_text"]):
        raise P0GroundingContractError("span_sha256 mismatch")

    if value["claim_direction"] not in {
        "SURFACE_TO_WORK",
        "WORK_TO_SURFACE",
        "SURFACE_TO_SENSE",
        "UNKNOWN_DIRECTION",
    }:
        raise P0GroundingContractError("claim_direction is invalid")
    surface_text = _text(value["surface_text"], "surface_text")
    target_text = _optional_text(value["target_text"], "target_text")
    target_work_id = _optional_text(value["target_work_id"], "target_work_id")
    if surface_text not in value["span_text"] or (
        target_text is not None and target_text not in value["span_text"]
    ):
        raise P0GroundingContractError("surface/target must be bound to the existing claim span")
    if value["claim_kind"] not in {"WORK_ALIAS", "COMMUNITY_SENSE", "UNKNOWN"}:
        raise P0GroundingContractError("claim_kind is invalid")
    if value["parse_disposition"] not in {"PARSED", "GENERIC_PENDING", "ABSTAIN"}:
        raise P0GroundingContractError("parse_disposition is invalid")
    if value["parse_disposition"] == "PARSED":
        if target_text is None or value["claim_direction"] == "UNKNOWN_DIRECTION" or value["claim_kind"] == "UNKNOWN":
            raise P0GroundingContractError("PARSED claim requires typed direction, kind, and target")
    elif target_text is not None:
        raise P0GroundingContractError("pending/abstained claim must not invent a target")
    if value["track"] == "A" and value["claim_kind"] not in {"WORK_ALIAS", "UNKNOWN"}:
        raise P0GroundingContractError("track A claim kind mismatch")
    if value["track"] == "B" and value["claim_kind"] not in {"COMMUNITY_SENSE", "UNKNOWN"}:
        raise P0GroundingContractError("track B claim kind mismatch")
    allowed_directions_by_kind = {
        "WORK_ALIAS": {"SURFACE_TO_WORK", "WORK_TO_SURFACE"},
        "COMMUNITY_SENSE": {"SURFACE_TO_SENSE"},
        "UNKNOWN": {"UNKNOWN_DIRECTION"},
    }
    if value["claim_direction"] not in allowed_directions_by_kind[value["claim_kind"]]:
        raise P0GroundingContractError("claim kind/direction contract mismatch")
    if value["claim_kind"] == "WORK_ALIAS" and value["parse_disposition"] == "PARSED":
        if target_work_id is None:
            raise P0GroundingContractError("parsed WORK_ALIAS claim requires target_work_id")
    elif target_work_id is not None:
        raise P0GroundingContractError("only parsed WORK_ALIAS claim may bind target_work_id")

    if value["source_profile"] == "GENERIC_FALLBACK" and value["parser_route"] != "generic_queue":
        raise P0GroundingContractError("generic fallback must enter generic_queue")
    if value["source_profile"] == "GENERIC_FALLBACK" and value["parse_disposition"] != "GENERIC_PENDING":
        raise P0GroundingContractError("generic fallback must remain GENERIC_PENDING")
    if value["source_profile"] != "GENERIC_FALLBACK" and value["parser_route"] == "generic_queue":
        raise P0GroundingContractError("known source profile must not enter generic_queue")
    if value["repair_mode"] not in {"NONE", "REPAIR_EXISTING", "ABSTAIN"}:
        raise P0GroundingContractError("repair_mode is invalid")
    repair_output = _optional_text(value["repair_output_text"], "repair_output_text")
    repair_source = _optional_sha(value["repair_source_span_sha256"], "repair_source_span_sha256")
    if value["repair_mode"] == "REPAIR_EXISTING":
        if repair_output != value["span_text"] or repair_source != value["span_sha256"]:
            raise P0GroundingContractError("repair must be bound to the existing source span")
    elif repair_output is not None or repair_source is not None:
        raise P0GroundingContractError("non-repair action must not create repair output")

    if value["snapshot_regime"] not in {"T0", "T1", "T2"}:
        raise P0GroundingContractError("snapshot_regime is invalid")
    expected_snapshot_sha256 = canonical_sha256(
        {
            "snapshot_id": value["snapshot_id"],
            "regime": value["snapshot_regime"],
            "origin": value["fixture_origin"],
            "response_sha256": value["response_sha256"],
        }
    )
    if _sha(value["snapshot_sha256"], "snapshot_sha256") != expected_snapshot_sha256:
        raise P0GroundingContractError("snapshot_sha256 response binding mismatch")
    if value["rights_status"] not in {"PERMITTED", "RESTRICTED_REVIEW", "UNKNOWN_WITH_REASON"}:
        raise P0GroundingContractError("rights_status is invalid")
    if _sha(value["source_record_sha256"], "source_record_sha256") != source_record_sha256(value):
        raise P0GroundingContractError("source_record_sha256 mismatch")
    if value["action_applied"] is not False or value["operational_effect"] != OPERATIONAL_EFFECT:
        raise P0GroundingContractError("P0 source fixture must be no-write shadow only")
    _validate_self_hash(value, "row_sha256", "source claim")
    return dict(value)


def validate_context_decision(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise P0GroundingContractError("context decision must be an object")
    _strict_fields(value, _CONTEXT_FIELDS, "context decision")
    if value["schema_version"] != CONTEXT_DECISION_SCHEMA:
        raise P0GroundingContractError("context decision schema mismatch")
    if value["fixture_origin"] != FIXTURE_ORIGIN:
        raise P0GroundingContractError("context fixture origin mismatch")
    if value["track"] != "A":
        raise P0GroundingContractError("four-axis context fixture must use track A")
    for field in ("context_id", "post_id", "content_text", "snapshot_id"):
        _text(value[field], field)
    if _sha(value["content_fingerprint"], "content_fingerprint") != canonical_sha256(
        value["content_text"]
    ):
        raise P0GroundingContractError("content_fingerprint mismatch")
    universe_ids = _sorted_unique_texts(
        value["canonical_universe_work_ids"], "canonical_universe_work_ids"
    )
    if _sha(value["canonical_universe_sha256"], "canonical_universe_sha256") != canonical_sha256(
        universe_ids
    ):
        raise P0GroundingContractError("canonical_universe_sha256 mismatch")
    source_ids = _sorted_unique_texts(value["source_claim_ids"], "source_claim_ids")
    candidates = _sorted_unique_texts(value["candidate_work_ids"], "candidate_work_ids")
    if not set(candidates).issubset(universe_ids):
        raise P0GroundingContractError("candidate_work_ids must belong to the canonical universe")
    candidate_urls = value["candidate_canonical_urls"]
    if not isinstance(candidate_urls, Mapping) or set(candidate_urls) != set(candidates):
        raise P0GroundingContractError(
            "candidate_canonical_urls must exactly cover candidate_work_ids"
        )
    normalized_candidate_urls: dict[str, str] = {}
    for candidate_id in candidates:
        url = _text(candidate_urls[candidate_id], f"candidate_canonical_urls.{candidate_id}")
        normalized_candidate_urls[candidate_id] = _https_url(
            url, f"candidate_canonical_urls.{candidate_id}"
        )
    candidate_payload = [
        {"work_id": candidate_id, "canonical_url": normalized_candidate_urls[candidate_id]}
        for candidate_id in candidates
    ]
    if _sha(value["candidate_set_fingerprint"], "candidate_set_fingerprint") != canonical_sha256(
        candidate_payload
    ):
        raise P0GroundingContractError("candidate_set_fingerprint mismatch")
    if value["producer_status"] not in {"COMPLETE", "INCOMPLETE", "UNAVAILABLE"}:
        raise P0GroundingContractError("producer_status is invalid")
    if value["retrieval_status"] not in {"GO", "UNRECOVERED", "UNAVAILABLE"}:
        raise P0GroundingContractError("retrieval_status is invalid")
    if value["candidate_integrity_status"] not in {"GO", "NO-GO"}:
        raise P0GroundingContractError("candidate_integrity_status is invalid")
    if value["annotation_status"] not in ANNOTATION_STATUSES:
        raise P0GroundingContractError("annotation_status is invalid")
    if value["truth_kind"] not in {"WORK_ID", "NIL", None}:
        raise P0GroundingContractError("truth_kind is invalid")
    truth_work_id = _optional_text(value["truth_work_id"], "truth_work_id")
    truth_nil_reason = _optional_text(value["truth_nil_reason"], "truth_nil_reason")
    truth_reasons = _reason_codes(
        value["truth_reason_codes"],
        "truth_reason_codes",
        TRUTH_REASON_CODES,
        allow_empty=True,
    )
    annotation_reasons = _reason_codes(
        value["annotation_reason_codes"], "annotation_reason_codes", ANNOTATION_REASON_CODES
    )
    canonical_receipt = _optional_sha(
        value["canonical_work_receipt_sha256"], "canonical_work_receipt_sha256"
    )
    relation_receipt = _optional_sha(
        value["post_relation_receipt_sha256"], "post_relation_receipt_sha256"
    )
    nil_receipt = _optional_sha(value["nil_receipt_sha256"], "nil_receipt_sha256")
    if value["annotation_status"] == "JUDGED":
        if value["truth_kind"] not in {"WORK_ID", "NIL"} or not truth_reasons:
            raise P0GroundingContractError("JUDGED requires explicit truth and truth reason")
        if "annotation_synthetic_contract_example" not in annotation_reasons:
            raise P0GroundingContractError(
                "synthetic JUDGED row requires a contract-example annotation reason"
            )
        if annotation_reasons != ["annotation_synthetic_contract_example"]:
            raise P0GroundingContractError("synthetic JUDGED annotation reason family mismatch")
    else:
        if value["truth_kind"] is not None or truth_work_id is not None or truth_nil_reason is not None:
            raise P0GroundingContractError("UNJUDGED/UNAVAILABLE must keep truth null")
        if truth_reasons or canonical_receipt or relation_receipt or nil_receipt:
            raise P0GroundingContractError("unresolved annotation must not carry truth receipts")
        allowed_annotation_reasons = (
            {
                "annotation_alias_sense_unresolved",
                "annotation_multiwork_primary_unresolved",
                "annotation_conflicting_evidence",
                "annotation_insufficient_context",
            }
            if value["annotation_status"] == "UNJUDGED"
            else {
                "evidence_source_deleted",
                "evidence_access_restricted",
                "evidence_retrieval_unavailable",
                "evidence_ocr_unavailable",
                "evidence_snapshot_mismatch",
            }
        )
        if not set(annotation_reasons).issubset(allowed_annotation_reasons):
            raise P0GroundingContractError("annotation status/reason family mismatch")
        if value["annotation_status"] == "UNAVAILABLE" and (
            value["producer_status"] == "COMPLETE"
            and value["retrieval_status"] == "GO"
            and value["candidate_integrity_status"] == "GO"
        ):
            raise P0GroundingContractError("UNAVAILABLE requires an unavailable operational state")
    if value["truth_kind"] == "WORK_ID":
        if not set(truth_reasons).issubset(
            {
                "truth_direct_official_id",
                "truth_explicit_alias_relation",
                "truth_context_work_relation",
            }
        ):
            raise P0GroundingContractError("WORK_ID truth reason mismatch")
        if truth_work_id is None or truth_work_id not in candidates:
            raise P0GroundingContractError("WORK_ID truth must bind a candidate work ID")
        if truth_nil_reason is not None or canonical_receipt is None or relation_receipt is None or nil_receipt is not None:
            raise P0GroundingContractError("WORK_ID truth receipt fields mismatch")
        expected_canonical_receipt = canonical_sha256(
            {
                "work_id": truth_work_id,
                "canonical_url": normalized_candidate_urls[truth_work_id],
                "kind": "canonical",
            }
        )
        if canonical_receipt != expected_canonical_receipt:
            raise P0GroundingContractError("canonical work receipt binding mismatch")
        expected_relation_receipt = canonical_sha256(
            {
                "post_id": value["post_id"],
                "work_id": truth_work_id,
                "content_fingerprint": value["content_fingerprint"],
                "source_claim_ids": source_ids,
                "kind": "relation",
            }
        )
        if relation_receipt != expected_relation_receipt:
            raise P0GroundingContractError("post relation receipt binding mismatch")
    elif value["truth_kind"] == "NIL":
        expected_nil_truth_reason = {
            "NIL_NON_WORK": "truth_nil_non_work",
            "NIL_OUT_OF_UNIVERSE": "truth_nil_out_of_universe",
            "NIL_NO_VALID_CANDIDATE": "truth_nil_no_canonical_target_after_complete_enumeration",
        }.get(truth_nil_reason)
        if truth_reasons != ([expected_nil_truth_reason] if expected_nil_truth_reason else []):
            raise P0GroundingContractError("NIL truth reason mismatch")
        if truth_work_id is not None or truth_nil_reason not in NIL_REASONS:
            raise P0GroundingContractError("NIL truth fields mismatch")
        if canonical_receipt is not None or relation_receipt is not None or nil_receipt is None:
            raise P0GroundingContractError("NIL truth receipt fields mismatch")
        expected_nil_receipt = canonical_sha256(
            {
                "post_id": value["post_id"],
                "nil_reason": truth_nil_reason,
                "kind": "nil",
            }
        )
        if nil_receipt != expected_nil_receipt:
            raise P0GroundingContractError("NIL receipt binding mismatch")

    if value["inference_decision"] not in INFERENCE_DECISIONS:
        raise P0GroundingContractError("inference_decision is invalid")
    inference_work_id = _optional_text(value["inference_work_id"], "inference_work_id")
    inference_reasons = _reason_codes(
        value["inference_reason_codes"], "inference_reason_codes", INFERENCE_REASON_CODES
    )
    if value["inference_decision"] == "ASSERT_WORK":
        if inference_work_id is None or inference_work_id not in candidates:
            raise P0GroundingContractError("ASSERT_WORK must bind a candidate work ID")
        if (
            value["producer_status"] != "COMPLETE"
            or value["retrieval_status"] != "GO"
            or value["candidate_integrity_status"] != "GO"
        ):
            raise P0GroundingContractError("ASSERT_WORK requires complete and healthy retrieval")
        if "inference_candidate_selected" not in inference_reasons:
            raise P0GroundingContractError("ASSERT_WORK reason mismatch")
        if inference_reasons != ["inference_candidate_selected"]:
            raise P0GroundingContractError("ASSERT_WORK must not carry abstain or NIL reasons")
    elif value["inference_decision"] == "ASSERT_NIL":
        if inference_work_id is not None:
            raise P0GroundingContractError("ASSERT_NIL must not bind a work ID")
        if (
            value["producer_status"] != "COMPLETE"
            or value["retrieval_status"] != "GO"
            or value["candidate_integrity_status"] != "GO"
        ):
            raise P0GroundingContractError("ASSERT_NIL requires a complete, healthy candidate universe")
        if "inference_complete_candidate_universe_nil" not in inference_reasons:
            raise P0GroundingContractError("ASSERT_NIL reason mismatch")
        if inference_reasons != ["inference_complete_candidate_universe_nil"]:
            raise P0GroundingContractError("ASSERT_NIL must not carry work or abstain reasons")
    else:
        if inference_work_id is not None or not set(inference_reasons).intersection(ABSTAIN_BLOCKERS):
            raise P0GroundingContractError("ABSTAIN requires no work ID and a hard blocker")
        if not set(inference_reasons).issubset(ABSTAIN_BLOCKERS):
            raise P0GroundingContractError("ABSTAIN must contain only registered blocker reasons")
        if (
            "retrieval_failclose_requires_abstain" in inference_reasons
            and value["retrieval_status"] == "GO"
        ):
            raise P0GroundingContractError("retrieval abstain reason requires degraded retrieval")
        if (
            "candidate_set_integrity_requires_abstain" in inference_reasons
            and value["candidate_integrity_status"] == "GO"
        ):
            raise P0GroundingContractError("candidate-integrity abstain reason requires NO-GO")

    if value["publication_action"] not in PUBLICATION_ACTIONS:
        raise P0GroundingContractError("publication_action is invalid")
    public_work_id = _optional_text(value["public_work_id"], "public_work_id")
    public_url = _optional_text(value["public_url"], "public_url")
    publication_reasons = _reason_codes(
        value["publication_reason_codes"],
        "publication_reason_codes",
        PUBLICATION_REASON_CODES,
    )
    if "publication_existing_wal_no_write" not in publication_reasons:
        raise P0GroundingContractError("P0 publication decision must preserve the existing WAL")
    if value["publication_action"] == "PUBLISH":
        if value["inference_decision"] != "ASSERT_WORK" or public_work_id != inference_work_id:
            raise P0GroundingContractError("PUBLISH must match ASSERT_WORK")
        if (
            value["producer_status"] != "COMPLETE"
            or value["retrieval_status"] != "GO"
            or value["candidate_integrity_status"] != "GO"
        ):
            raise P0GroundingContractError("PUBLISH requires complete and healthy retrieval")
        if public_url is None:
            raise P0GroundingContractError("PUBLISH requires a canonical https URL")
        _https_url(public_url, "public_url")
        if public_url != normalized_candidate_urls[public_work_id]:
            raise P0GroundingContractError("PUBLISH URL must match the selected candidate binding")
        if "publication_evidence_verified" not in publication_reasons:
            raise P0GroundingContractError("PUBLISH reason mismatch")
        if publication_reasons != [
            "publication_evidence_verified",
            "publication_existing_wal_no_write",
        ]:
            raise P0GroundingContractError("PUBLISH must not carry hold/reject blockers")
    elif public_work_id is not None or public_url is not None:
        raise P0GroundingContractError("HOLD/REJECT must not leak public work fields")
    if value["publication_action"] == "HOLD":
        expected_hold_reasons = {
            "JUDGED": {
                "publication_existing_wal_no_write",
                "publication_selective_risk_hold",
            },
            "UNJUDGED": {
                "publication_abstain_hold",
                "publication_existing_wal_no_write",
                "publication_unjudged_hold",
            },
            "UNAVAILABLE": {
                "publication_abstain_hold",
                "publication_existing_wal_no_write",
                "publication_unavailable_hold",
            },
        }[value["annotation_status"]]
        if set(publication_reasons) != expected_hold_reasons:
            raise P0GroundingContractError("HOLD annotation/publication reason family mismatch")
    if value["publication_action"] == "REJECT":
        if (
            value["annotation_status"] != "JUDGED"
            or value["truth_kind"] != "NIL"
            or value["inference_decision"] != "ASSERT_NIL"
            or "publication_nil_reject" not in publication_reasons
        ):
            raise P0GroundingContractError("REJECT requires judged terminal NIL")
        if publication_reasons != [
            "publication_existing_wal_no_write",
            "publication_nil_reject",
        ]:
            raise P0GroundingContractError("REJECT reason mismatch")
    if value["publication_action"] == "HOLD" and value["inference_decision"] == "ASSERT_WORK":
        if publication_reasons != [
            "publication_existing_wal_no_write",
            "publication_selective_risk_hold",
        ]:
            raise P0GroundingContractError("ASSERT_WORK/HOLD reason mismatch")
    if value["publication_action"] == "HOLD" and value["inference_decision"] == "ABSTAIN":
        if "publication_abstain_hold" not in publication_reasons:
            raise P0GroundingContractError("ABSTAIN/HOLD reason mismatch")
        if set(publication_reasons).intersection(
            {"publication_evidence_verified", "publication_nil_reject", "publication_selective_risk_hold"}
        ):
            raise P0GroundingContractError("ABSTAIN/HOLD must not carry publish or terminal NIL reasons")
    if value["annotation_status"] in {"UNJUDGED", "UNAVAILABLE"} and (
        value["inference_decision"] != "ABSTAIN" or value["publication_action"] != "HOLD"
    ):
        raise P0GroundingContractError("UNJUDGED/UNAVAILABLE must project to ABSTAIN/HOLD")

    if value["action_applied"] is not False or value["operational_effect"] != OPERATIONAL_EFFECT:
        raise P0GroundingContractError("P0 context fixture must be no-write shadow only")
    _validate_self_hash(value, "row_sha256", "context decision")
    return dict(value)


def _validate_lineage(rows: Sequence[Mapping[str, Any]]) -> tuple[int, int, int]:
    by_source: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        existing = by_source.setdefault(row["source_id"], row)
        if existing["source_record_sha256"] != row["source_record_sha256"]:
            raise P0GroundingContractError("one source_id must bind one immutable source record")
    if len({row["claim_id"] for row in rows}) != len(rows):
        raise P0GroundingContractError("claim_id must be unique")
    snapshot_bindings: dict[str, str] = {}
    for row in by_source.values():
        snapshot_id = row["snapshot_id"]
        existing = snapshot_bindings.setdefault(snapshot_id, row["snapshot_sha256"])
        if existing != row["snapshot_sha256"]:
            raise P0GroundingContractError("snapshot_id must be immutably bound to one hash")
        parent_id = row["parent_source_id"]
        if parent_id is None:
            eligible_root = (
                row["lineage_root_id"] == row["source_id"]
                and row["derivation_kind"] == "ORIGINAL"
                and row["independence_status"] == "ELIGIBLE_ROOT"
            )
            collapsed_unknown = (
                row["lineage_root_id"] == row["source_id"]
                and row["derivation_kind"] == "UNKNOWN_LINEAGE"
                and row["independence_status"] == "COLLAPSED_UNKNOWN_LINEAGE"
            )
            if not eligible_root and not collapsed_unknown:
                raise P0GroundingContractError("lineage root fields mismatch")
            continue
        if parent_id not in by_source or parent_id == row["source_id"]:
            raise P0GroundingContractError("lineage parent is missing or self-referential")
        if row["derivation_kind"] == "ORIGINAL" or row["independence_status"] == "ELIGIBLE_ROOT":
            raise P0GroundingContractError("derived lineage must be collapsed")
        parent = by_source[parent_id]
        if (
            row["lineage_root_id"] != parent["lineage_root_id"]
            or row["independence_group_id"] != parent["independence_group_id"]
        ):
            raise P0GroundingContractError("derived lineage must share root and independence group")
        if row["derivation_kind"] in {"MIRROR", "REPOST"} and (
            row["response_sha256"] != parent["response_sha256"]
            or row["content_sha256"] != parent["content_sha256"]
        ):
            raise P0GroundingContractError("mirror/repost must preserve parent response content")
        if row["derivation_kind"] == "QUOTE" and parent["span_text"] not in row["response_text"]:
            raise P0GroundingContractError("quote must preserve the quoted parent span")
        seen = {row["source_id"]}
        cursor = parent
        while cursor["parent_source_id"] is not None:
            if cursor["source_id"] in seen:
                raise P0GroundingContractError("lineage graph contains a cycle")
            seen.add(cursor["source_id"])
            next_parent_id = cursor["parent_source_id"]
            if next_parent_id not in by_source:
                raise P0GroundingContractError("lineage ancestor is missing")
            cursor = by_source[next_parent_id]
        if cursor["source_id"] != row["lineage_root_id"]:
            raise P0GroundingContractError("lineage_root_id does not resolve to the root")
    eligible_roots = [
        row for row in by_source.values() if row["independence_status"] == "ELIGIBLE_ROOT"
    ]
    eligible_groups = {row["independence_group_id"] for row in eligible_roots}
    if len(eligible_groups) != len(eligible_roots):
        raise P0GroundingContractError("eligible lineage roots must own unique independence groups")
    derivative_count = sum(row["parent_source_id"] is not None for row in by_source.values())
    return len(eligible_groups), len(eligible_roots), derivative_count


def _semantic_blockers(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    blockers: set[str] = set()
    for row in rows:
        if (
            row["truth_kind"] == "WORK_ID"
            and row["inference_decision"] == "ASSERT_WORK"
            and row["inference_work_id"] != row["truth_work_id"]
        ):
            blockers.add("WRONG_WORK_INFERENCE")
        if row["publication_action"] == "PUBLISH" and (
            row["truth_kind"] != "WORK_ID"
            or row["public_work_id"] != row["truth_work_id"]
        ):
            blockers.add("WRONG_WORK_PUBLISH")
    return sorted(blockers)


def _validate_contract_bundle(
    source_claims: Sequence[Mapping[str, Any]],
    context_decisions: Sequence[Mapping[str, Any]],
    *,
    artifact_bindings: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    sources = [validate_source_claim(row) for row in source_claims]
    contexts = [validate_context_decision(row) for row in context_decisions]
    source_by_claim = {row["claim_id"]: row for row in sources}
    if len(source_by_claim) != len(sources):
        raise P0GroundingContractError("claim_id must be unique")
    if len({row["context_id"] for row in contexts}) != len(contexts):
        raise P0GroundingContractError("context_id must be unique")
    if len({row["post_id"] for row in contexts}) != len(contexts):
        raise P0GroundingContractError("context post_id must be unique")
    if len({row["content_fingerprint"] for row in contexts}) != len(contexts):
        raise P0GroundingContractError("context content_fingerprint must be unique")
    if len({row["canonical_universe_sha256"] for row in contexts}) != 1:
        raise P0GroundingContractError("all contexts must share one canonical universe binding")
    canonical_urls_by_work: dict[str, str] = {}
    for row in contexts:
        for work_id, url in row["candidate_canonical_urls"].items():
            existing_url = canonical_urls_by_work.setdefault(work_id, url)
            if existing_url != url:
                raise P0GroundingContractError("canonical work URL binding differs across contexts")
        missing = sorted(set(row["source_claim_ids"]) - set(source_by_claim))
        if missing:
            raise P0GroundingContractError(f"context references unknown source claims: {missing}")
        for claim_id in row["source_claim_ids"]:
            if source_by_claim[claim_id]["snapshot_id"] != row["snapshot_id"]:
                raise P0GroundingContractError("context/source snapshot binding mismatch")
            if source_by_claim[claim_id]["track"] != row["track"]:
                raise P0GroundingContractError("context/source track binding mismatch")
        if row["truth_kind"] == "WORK_ID":
            supporting_work_claims = [
                source_by_claim[claim_id]
                for claim_id in row["source_claim_ids"]
                if source_by_claim[claim_id]["parse_disposition"] == "PARSED"
                and source_by_claim[claim_id]["claim_kind"] == "WORK_ALIAS"
                and source_by_claim[claim_id]["target_work_id"] == row["truth_work_id"]
            ]
            if not supporting_work_claims:
                raise P0GroundingContractError(
                    "WORK_ID truth requires a referenced work-alias claim for the selected work"
                )
        if row["publication_action"] == "PUBLISH":
            source_rows = [source_by_claim[claim_id] for claim_id in row["source_claim_ids"]]
            eligible_official = [
                source
                for source in source_rows
                if source["source_profile"] == "OFFICIAL_STRUCTURED"
                and source["parse_disposition"] == "PARSED"
                and source["claim_kind"] == "WORK_ALIAS"
                and source["target_work_id"] == row["public_work_id"]
                and source["rights_status"] == "PERMITTED"
                and 200 <= source["http_status"] < 300
            ]
            if not eligible_official:
                raise P0GroundingContractError(
                    "PUBLISH requires an eligible official parsed work-alias source"
                )

    independence_groups, root_count, derivative_count = _validate_lineage(sources)
    profile_counts = Counter(row["source_profile"] for row in sources)
    track_counts = Counter(row["track"] for row in sources)
    annotation_counts = Counter(row["annotation_status"] for row in contexts)
    truth_counts = Counter(str(row["truth_kind"]) for row in contexts)
    inference_counts = Counter(row["inference_decision"] for row in contexts)
    publication_counts = Counter(row["publication_action"] for row in contexts)
    blockers = _semantic_blockers(contexts)
    if artifact_bindings is None:
        source_file_sha256 = None
        context_file_sha256 = None
        manifest_sha256 = None
    else:
        expected_binding_fields = {
            "source_file_sha256",
            "context_file_sha256",
            "manifest_sha256",
        }
        if set(artifact_bindings) != expected_binding_fields:
            raise P0GroundingContractError("artifact binding fields mismatch")
        source_file_sha256 = _sha(
            artifact_bindings["source_file_sha256"], "source_file_sha256"
        )
        context_file_sha256 = _sha(
            artifact_bindings["context_file_sha256"], "context_file_sha256"
        )
        manifest_sha256 = _sha(
            artifact_bindings["manifest_sha256"], "manifest_sha256"
        )
    for binding, code in (
        (source_file_sha256, "SOURCE_FILE_BINDING_MISSING"),
        (context_file_sha256, "CONTEXT_FILE_BINDING_MISSING"),
        (manifest_sha256, "MANIFEST_BINDING_MISSING"),
    ):
        if binding is None:
            blockers.append(code)
    artifact_binding_verified = artifact_bindings is not None
    if not artifact_binding_verified:
        blockers.append("ARTIFACT_BINDING_NOT_VERIFIED")
    expected_profiles = {profile: 10 for profile in SOURCE_PROFILES}
    expected_tracks = {track: 20 for track in TRACKS}
    quota_checks = (
        (len(sources) == 40, "SOURCE_CLAIM_COUNT_NOT_40"),
        (len(contexts) == 20, "CONTEXT_COUNT_NOT_20"),
        (dict(profile_counts) == expected_profiles, "SOURCE_PROFILE_QUOTA_MISMATCH"),
        (dict(track_counts) == expected_tracks, "SOURCE_TRACK_QUOTA_MISMATCH"),
        (independence_groups == 30, "INDEPENDENCE_GROUP_COUNT_NOT_30"),
        (root_count == 30, "LINEAGE_ROOT_COUNT_NOT_30"),
        (derivative_count == 10, "LINEAGE_DERIVATIVE_COUNT_NOT_10"),
        (sum(row["parser_route"] == "generic_queue" for row in sources) == 10, "GENERIC_QUEUE_COUNT_NOT_10"),
        (annotation_counts == Counter({"JUDGED": 14, "UNJUDGED": 3, "UNAVAILABLE": 3}), "ANNOTATION_QUOTA_MISMATCH"),
        (truth_counts == Counter({"WORK_ID": 10, "NIL": 4, "None": 6}), "TRUTH_QUOTA_MISMATCH"),
        (inference_counts == Counter({"ASSERT_WORK": 10, "ASSERT_NIL": 4, "ABSTAIN": 6}), "INFERENCE_QUOTA_MISMATCH"),
        (publication_counts == Counter({"PUBLISH": 6, "HOLD": 10, "REJECT": 4}), "PUBLICATION_QUOTA_MISMATCH"),
    )
    blockers.extend(code for passed, code in quota_checks if not passed)
    blockers = sorted(set(blockers))
    material = {
        "schema_version": VALIDATION_RECEIPT_SCHEMA,
        "fixture_origin": FIXTURE_ORIGIN,
        "gate_status": (
            "GO_P0_CONTRACT_FIXTURE_ONLY" if not blockers else "NO_GO_P0_CONTRACT_OR_SEMANTIC_SAFETY"
        ),
        "metric_status": "METRICS_NOT_ESTIMABLE",
        "review_status": "REVIEW_LOCKED",
        "full_scan_approval": False,
        "source_claim_count": len(sources),
        "context_count": len(contexts),
        "profile_counts": {key: profile_counts.get(key, 0) for key in SOURCE_PROFILES},
        "track_counts": {key: track_counts.get(key, 0) for key in TRACKS},
        "annotation_counts": {key: annotation_counts.get(key, 0) for key in ANNOTATION_STATUSES},
        "truth_counts": {
            "WORK_ID": truth_counts.get("WORK_ID", 0),
            "NIL": truth_counts.get("NIL", 0),
            "UNRESOLVED": truth_counts.get("None", 0),
        },
        "inference_counts": {key: inference_counts.get(key, 0) for key in INFERENCE_DECISIONS},
        "publication_counts": {key: publication_counts.get(key, 0) for key in PUBLICATION_ACTIONS},
        "eligible_independence_group_count": independence_groups,
        "lineage_root_count": root_count,
        "lineage_derivative_count": derivative_count,
        "generic_queue_count": sum(row["parser_route"] == "generic_queue" for row in sources),
        "record_level_no_write_verified": all(
            row["action_applied"] is False and row["operational_effect"] == OPERATIONAL_EFFECT
            for row in [*sources, *contexts]
        ),
        "no_write_evidence_scope": "RECORD_FIELDS_AND_IMPORT_BOUNDARY_ONLY",
        "p0_phase_exit": False,
        "actual_source_claim_count": 0,
        "actual_context_review_count": 0,
        "artifact_binding_verified": artifact_binding_verified,
        "authority": "SHADOW_ONLY",
        "public_apply": False,
        "central_slang_db_write": False,
        "publication_wal_write": False,
        "external_retriever": "DISABLED_P0",
        "core_dependency_delta": [],
        "source_file_sha256": _optional_sha(source_file_sha256, "source_file_sha256"),
        "context_file_sha256": _optional_sha(context_file_sha256, "context_file_sha256"),
        "manifest_sha256": _optional_sha(manifest_sha256, "manifest_sha256"),
        "blockers": blockers,
    }
    return {**material, "receipt_sha256": canonical_sha256(material)}


def validate_contract_bundle(
    source_claims: Sequence[Mapping[str, Any]],
    context_decisions: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Validate in-memory records without granting durable artifact authority."""
    return _validate_contract_bundle(source_claims, context_decisions)


def _fixture_source_claims() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    root_counts = {
        "OFFICIAL_STRUCTURED": 8,
        "COMMUNITY_STRUCTURED": 8,
        "MEDIA_OCR": 7,
        "GENERIC_FALLBACK": 7,
    }
    global_index = 0
    for profile_number, profile in enumerate(SOURCE_PROFILES, start=1):
        profile_source_ids: list[str] = []
        for local_index in range(1, 11):
            global_index += 1
            source_id = f"src-{global_index:03d}"
            claim_id = f"claim-{global_index:03d}"
            is_root = local_index <= root_counts[profile]
            if is_root:
                root_id = source_id
                parent_id = None
                group_id = f"group-{global_index:03d}"
                derivation_kind = "ORIGINAL"
                independence_status = "ELIGIBLE_ROOT"
            else:
                derived_offset = local_index - root_counts[profile] - 1
                parent_local_index = 6 + (derived_offset % 2)
                parent_id = profile_source_ids[parent_local_index - 1]
                parent = next(row for row in rows if row["source_id"] == parent_id)
                root_id = parent["lineage_root_id"]
                group_id = parent["independence_group_id"]
                derivation_kind = ("MIRROR", "REPOST", "QUOTE")[derived_offset % 3]
                independence_status = "COLLAPSED_DERIVATIVE"
            profile_source_ids.append(source_id)
            span_text = f"alias-{global_index:03d}"
            target_text = f"target-{global_index:03d}"
            claim_span = f"{span_text} -> {target_text}"
            response_text = f"synthetic contract evidence {claim_span} for parser and lineage validation"
            if not is_root and derivation_kind in {"MIRROR", "REPOST"}:
                response_text = parent["response_text"]
                claim_span = parent["span_text"]
                span_text = parent["surface_text"]
                if parent["target_text"] is not None:
                    target_text = parent["target_text"]
            elif not is_root and derivation_kind == "QUOTE":
                response_text = (
                    f"synthetic quote {parent['span_text']} with derived claim {claim_span}"
                )
            span_start = response_text.index(claim_span)
            span_end = span_start + len(claim_span)
            author_unknown = local_index in {9, 10}
            published_unknown = local_index in {9, 10}
            repair_mode = (
                "REPAIR_EXISTING"
                if profile == "MEDIA_OCR" and local_index in {1, 2}
                else "ABSTAIN" if profile == "GENERIC_FALLBACK" else "NONE"
            )
            response_sha = hashlib.sha256(response_text.encode("utf-8")).hexdigest()
            snapshot_id = f"snapshot-p0-t0-{source_id}"
            snapshot_sha = canonical_sha256(
                {
                    "snapshot_id": snapshot_id,
                    "regime": "T0",
                    "origin": FIXTURE_ORIGIN,
                    "response_sha256": response_sha,
                }
            )
            material = {
                "schema_version": SOURCE_CLAIM_SCHEMA,
                "fixture_origin": FIXTURE_ORIGIN,
                "claim_id": claim_id,
                "track": "A" if local_index <= 5 else "B",
                "source_profile": profile,
                "source_id": source_id,
                "community_scope": "SYNTHETIC_COMMUNITY",
                "platform": "SYNTHETIC_PLATFORM",
                "canonical_url": f"https://example.invalid/p0/{profile.lower()}/{source_id}",
                "locator": f"synthetic://p0/{profile_number}/{local_index}",
                "item_locator": f"synthetic://p0/{profile_number}/{local_index}#claim-1",
                "lineage_root_id": root_id,
                "parent_source_id": parent_id,
                "derivation_kind": derivation_kind,
                "independence_group_id": group_id,
                "independence_status": independence_status,
                "author": None if author_unknown else f"synthetic-author-{profile_number:02d}",
                "author_unknown_reason": "anonymous_source" if author_unknown else None,
                "published_at": None if published_unknown else f"2026-08-{local_index:02d}T09:00:00+09:00",
                "published_at_unknown_reason": "source_time_not_exposed" if published_unknown else None,
                "modified_at": None,
                "modified_at_unknown_reason": "source_modified_time_not_exposed",
                "collected_at": "2026-09-02T12:00:00+09:00",
                "http_status": 200,
                "content_type": "application/json" if profile == "OFFICIAL_STRUCTURED" else "text/plain",
                "response_text": response_text,
                "response_sha256": response_sha,
                "response_bytes": len(response_text.encode("utf-8")),
                "content_sha256": canonical_sha256(response_text),
                "span_start": span_start,
                "span_end": span_end,
                "span_text": claim_span,
                "span_sha256": canonical_sha256(claim_span),
                "claim_direction": (
                    "UNKNOWN_DIRECTION"
                    if profile == "GENERIC_FALLBACK"
                    else "SURFACE_TO_WORK" if local_index <= 5 else "SURFACE_TO_SENSE"
                ),
                "surface_text": span_text,
                "target_text": None if profile == "GENERIC_FALLBACK" else target_text,
                "target_work_id": (
                    f"work-{((profile_number - 1) * 5) + local_index:03d}"
                    if local_index <= 5 and profile != "GENERIC_FALLBACK"
                    else None
                ),
                "claim_kind": (
                    "UNKNOWN"
                    if profile == "GENERIC_FALLBACK"
                    else "WORK_ALIAS" if local_index <= 5 else "COMMUNITY_SENSE"
                ),
                "parse_disposition": "GENERIC_PENDING" if profile == "GENERIC_FALLBACK" else "PARSED",
                "parser_profile": profile.lower(),
                "parser_version": "p0-parser-contract-v1",
                "parser_route": "generic_queue" if profile == "GENERIC_FALLBACK" else "structured_profile",
                "repair_mode": repair_mode,
                "repair_output_text": claim_span if repair_mode == "REPAIR_EXISTING" else None,
                "repair_source_span_sha256": canonical_sha256(claim_span) if repair_mode == "REPAIR_EXISTING" else None,
                "rights_status": "PERMITTED",
                "rights_basis": "SYNTHETIC_NO_EXTERNAL_CONTENT",
                "snapshot_id": snapshot_id,
                "snapshot_regime": "T0",
                "snapshot_sha256": snapshot_sha,
                "action_applied": False,
                "operational_effect": OPERATIONAL_EFFECT,
            }
            material["source_record_sha256"] = source_record_sha256(material)
            rows.append(with_row_hash(material))
    return rows


def _fixture_context_decisions() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    universe_ids = [f"work-{index:03d}" for index in range(1, 21)]
    universe_sha = canonical_sha256(universe_ids)
    track_a_claim_indices = [
        1, 2, 3, 4, 5, 1,
        11, 12, 13, 14,
        21, 22, 23, 24,
        31, 32, 33, 34, 35, 31,
    ]
    claim_to_work_id = {
        claim_index: f"work-{ordinal:03d}"
        for ordinal, claim_index in enumerate(
            [1, 2, 3, 4, 5, 11, 12, 13, 14, 15, 21, 22, 23, 24, 25, 31, 32, 33, 34, 35],
            start=1,
        )
    }
    for index in range(1, 21):
        claim_index = track_a_claim_indices[index - 1]
        work_id = claim_to_work_id[claim_index] if index <= 10 else f"work-{index:03d}"
        alternate_id = f"work-{((index + 6) % 20) + 1:03d}"
        candidates = sorted({work_id, alternate_id})
        content_text = f"synthetic context {index:03d} mentions alias-{claim_index:03d}"
        content_fingerprint = canonical_sha256(content_text)
        post_id = f"synthetic-post-{index:03d}"
        source_claim_ids = [f"claim-{claim_index:03d}"]
        candidate_urls = {
            candidate_id: f"https://example.invalid/works/{candidate_id}"
            for candidate_id in candidates
        }
        if index <= 10:
            annotation_status = "JUDGED"
            truth_kind = "WORK_ID"
            truth_work_id = work_id
            truth_nil_reason = None
            truth_reasons = [
                "truth_context_work_relation",
                "truth_direct_official_id",
                "truth_explicit_alias_relation",
            ]
            annotation_reasons = ["annotation_synthetic_contract_example"]
            inference_decision = "ASSERT_WORK"
            inference_work_id = work_id
            inference_reasons = ["inference_candidate_selected"]
            publication_action = "PUBLISH" if index <= 6 else "HOLD"
            public_work_id = work_id if publication_action == "PUBLISH" else None
            public_url = (
                f"https://example.invalid/works/{work_id}" if publication_action == "PUBLISH" else None
            )
            publication_reasons = (
                ["publication_evidence_verified", "publication_existing_wal_no_write"]
                if publication_action == "PUBLISH"
                else ["publication_existing_wal_no_write", "publication_selective_risk_hold"]
            )
            canonical_receipt = canonical_sha256(
                {
                    "work_id": work_id,
                    "canonical_url": candidate_urls[work_id],
                    "kind": "canonical",
                }
            )
            relation_receipt = canonical_sha256(
                {
                    "post_id": post_id,
                    "work_id": work_id,
                    "content_fingerprint": content_fingerprint,
                    "source_claim_ids": source_claim_ids,
                    "kind": "relation",
                }
            )
            nil_receipt = None
            producer_status = "COMPLETE"
            retrieval_status = "GO"
            integrity_status = "GO"
        elif index <= 14:
            annotation_status = "JUDGED"
            truth_kind = "NIL"
            truth_work_id = None
            truth_nil_reason = ("NIL_NON_WORK", "NIL_OUT_OF_UNIVERSE", "NIL_NO_VALID_CANDIDATE", "NIL_NON_WORK")[index - 11]
            truth_reasons = [
                {
                    "NIL_NON_WORK": "truth_nil_non_work",
                    "NIL_OUT_OF_UNIVERSE": "truth_nil_out_of_universe",
                    "NIL_NO_VALID_CANDIDATE": "truth_nil_no_canonical_target_after_complete_enumeration",
                }[truth_nil_reason]
            ]
            annotation_reasons = ["annotation_synthetic_contract_example"]
            inference_decision = "ASSERT_NIL"
            inference_work_id = None
            inference_reasons = ["inference_complete_candidate_universe_nil"]
            publication_action = "REJECT"
            public_work_id = None
            public_url = None
            publication_reasons = ["publication_existing_wal_no_write", "publication_nil_reject"]
            canonical_receipt = None
            relation_receipt = None
            nil_receipt = canonical_sha256(
                {
                    "post_id": f"synthetic-post-{index:03d}",
                    "nil_reason": truth_nil_reason,
                    "kind": "nil",
                }
            )
            producer_status = "COMPLETE"
            retrieval_status = "GO"
            integrity_status = "GO"
        else:
            annotation_status = "UNJUDGED" if index <= 17 else "UNAVAILABLE"
            truth_kind = None
            truth_work_id = None
            truth_nil_reason = None
            truth_reasons = []
            annotation_reasons = (
                ["annotation_alias_sense_unresolved"]
                if annotation_status == "UNJUDGED"
                else ["evidence_retrieval_unavailable"]
            )
            inference_decision = "ABSTAIN"
            inference_work_id = None
            inference_reasons = ["retrieval_failclose_requires_abstain"]
            publication_action = "HOLD"
            public_work_id = None
            public_url = None
            publication_reasons = [
                "publication_abstain_hold",
                "publication_existing_wal_no_write",
                "publication_unjudged_hold" if annotation_status == "UNJUDGED" else "publication_unavailable_hold",
            ]
            canonical_receipt = None
            relation_receipt = None
            nil_receipt = None
            producer_status = "UNAVAILABLE"
            retrieval_status = "UNAVAILABLE"
            integrity_status = "NO-GO"
        material = {
            "schema_version": CONTEXT_DECISION_SCHEMA,
            "fixture_origin": FIXTURE_ORIGIN,
            "context_id": f"context-{index:03d}",
            "track": "A",
            "post_id": post_id,
            "content_text": content_text,
            "content_fingerprint": content_fingerprint,
            "source_claim_ids": source_claim_ids,
            "snapshot_id": f"snapshot-p0-t0-src-{claim_index:03d}",
            "canonical_universe_work_ids": universe_ids,
            "canonical_universe_sha256": universe_sha,
            "candidate_work_ids": candidates,
            "candidate_canonical_urls": candidate_urls,
            "candidate_set_fingerprint": canonical_sha256(
                [
                    {"work_id": candidate_id, "canonical_url": candidate_urls[candidate_id]}
                    for candidate_id in candidates
                ]
            ),
            "producer_status": producer_status,
            "retrieval_status": retrieval_status,
            "candidate_integrity_status": integrity_status,
            "truth_kind": truth_kind,
            "truth_work_id": truth_work_id,
            "truth_nil_reason": truth_nil_reason,
            "truth_reason_codes": truth_reasons,
            "annotation_status": annotation_status,
            "annotation_reason_codes": annotation_reasons,
            "inference_decision": inference_decision,
            "inference_work_id": inference_work_id,
            "inference_reason_codes": inference_reasons,
            "publication_action": publication_action,
            "public_work_id": public_work_id,
            "public_url": public_url,
            "publication_reason_codes": sorted(publication_reasons),
            "canonical_work_receipt_sha256": canonical_receipt,
            "post_relation_receipt_sha256": relation_receipt,
            "nil_receipt_sha256": nil_receipt,
            "action_applied": False,
            "operational_effect": OPERATIONAL_EFFECT,
        }
        rows.append(with_row_hash(material))
    return rows


def build_synthetic_contract_fixture() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return deterministic contract-only 40-claim and 20-context fixtures."""
    sources = _fixture_source_claims()
    contexts = _fixture_context_decisions()
    validate_contract_bundle(sources, contexts)
    return sources, contexts


def jsonl_bytes(rows: Iterable[Mapping[str, Any]]) -> bytes:
    return b"".join(canonical_bytes(row) + b"\n" for row in rows)


def build_fixture_manifest(
    *,
    source_path: str | Path,
    context_path: str | Path,
    source_count: int,
    context_count: int,
) -> dict[str, Any]:
    source_path = Path(source_path)
    context_path = Path(context_path)
    material = {
        "schema_version": FIXTURE_MANIFEST_SCHEMA,
        "fixture_origin": FIXTURE_ORIGIN,
        "source_claims": {
            "path": source_path.name,
            "rows": source_count,
            "bytes": source_path.stat().st_size,
            "sha256": file_sha256(source_path),
        },
        "context_decisions": {
            "path": context_path.name,
            "rows": context_count,
            "bytes": context_path.stat().st_size,
            "sha256": file_sha256(context_path),
        },
        "profile_counts": {profile: 10 for profile in SOURCE_PROFILES},
        "track_counts": {track: 20 for track in TRACKS},
        "required_independence_groups": 30,
        "gate_scope": "P0_CONTRACT_FIXTURE_ONLY_METRICS_NOT_ESTIMABLE",
        "authority": "SHADOW_ONLY",
        "public_apply": False,
        "central_slang_db_write": False,
        "publication_wal_write": False,
        "external_retriever": "DISABLED_P0",
        "core_dependency_delta": [],
        "noninterference_contract_scope": "DECLARED_NO_WRITE_FIELDS_ONLY",
        "action_applied": False,
        "operational_effect": OPERATIONAL_EFFECT,
    }
    return {**material, "manifest_sha256": canonical_sha256(material)}


def validate_fixture_manifest(value: Any, *, directory: str | Path) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise P0GroundingContractError("fixture manifest must be an object")
    _strict_fields(value, _MANIFEST_FIELDS, "fixture manifest")
    if value["schema_version"] != FIXTURE_MANIFEST_SCHEMA or value["fixture_origin"] != FIXTURE_ORIGIN:
        raise P0GroundingContractError("fixture manifest identity mismatch")
    if value["action_applied"] is not False or value["operational_effect"] != OPERATIONAL_EFFECT:
        raise P0GroundingContractError("fixture manifest must be no-write shadow only")
    if value["gate_scope"] != "P0_CONTRACT_FIXTURE_ONLY_METRICS_NOT_ESTIMABLE":
        raise P0GroundingContractError("fixture manifest gate scope mismatch")
    if (
        value["authority"] != "SHADOW_ONLY"
        or value["public_apply"] is not False
        or value["central_slang_db_write"] is not False
        or value["publication_wal_write"] is not False
        or value["external_retriever"] != "DISABLED_P0"
        or value["core_dependency_delta"] != []
        or value["noninterference_contract_scope"] != "DECLARED_NO_WRITE_FIELDS_ONLY"
    ):
        raise P0GroundingContractError("fixture manifest P0 noninterference contract mismatch")
    directory = Path(directory)
    for field in ("source_claims", "context_decisions"):
        ref = value[field]
        if not isinstance(ref, Mapping) or set(ref) != {"path", "rows", "bytes", "sha256"}:
            raise P0GroundingContractError(f"{field} file ref mismatch")
        name = _text(ref["path"], f"{field}.path")
        if Path(name).name != name:
            raise P0GroundingContractError(f"{field}.path must be a local basename")
        path = directory / name
        if not path.is_file():
            raise P0GroundingContractError(f"{field} file is missing")
        if isinstance(ref["rows"], bool) or not isinstance(ref["rows"], int) or ref["rows"] <= 0:
            raise P0GroundingContractError(f"{field}.rows is invalid")
        if ref["bytes"] != path.stat().st_size or _sha(ref["sha256"], f"{field}.sha256") != file_sha256(path):
            raise P0GroundingContractError(f"{field} file binding mismatch")
    if value["profile_counts"] != {profile: 10 for profile in SOURCE_PROFILES}:
        raise P0GroundingContractError("fixture manifest profile counts mismatch")
    if value["track_counts"] != {track: 20 for track in TRACKS}:
        raise P0GroundingContractError("fixture manifest track counts mismatch")
    if value["required_independence_groups"] != 30:
        raise P0GroundingContractError("fixture manifest independence requirement mismatch")
    _validate_self_hash(value, "manifest_sha256", "fixture manifest")
    return dict(value)


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                raise P0GroundingContractError(f"blank JSONL line at {line_number}")
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise P0GroundingContractError(f"invalid JSONL line {line_number}") from exc
            if not isinstance(value, dict):
                raise P0GroundingContractError(f"JSONL line {line_number} must be an object")
            rows.append(value)
    return rows


def validate_fixture_directory(directory: str | Path) -> dict[str, Any]:
    """Validate a manifest-bound fixture directory and return its durable receipt."""
    directory = Path(directory).resolve()
    manifest_path = directory / "p0_grounding_contract_fixture_manifest_v1.json"
    with manifest_path.open("r", encoding="utf-8") as handle:
        manifest = validate_fixture_manifest(json.load(handle), directory=directory)
    source_path = directory / manifest["source_claims"]["path"]
    context_path = directory / manifest["context_decisions"]["path"]
    sources = load_jsonl(source_path)
    contexts = load_jsonl(context_path)
    if len(sources) != manifest["source_claims"]["rows"]:
        raise P0GroundingContractError("source row count does not match manifest")
    if len(contexts) != manifest["context_decisions"]["rows"]:
        raise P0GroundingContractError("context row count does not match manifest")
    return _validate_contract_bundle(
        sources,
        contexts,
        artifact_bindings={
            "source_file_sha256": file_sha256(source_path),
            "context_file_sha256": file_sha256(context_path),
            "manifest_sha256": manifest["manifest_sha256"],
        },
    )
