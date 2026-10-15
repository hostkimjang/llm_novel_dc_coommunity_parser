from __future__ import annotations

"""Deterministic, review-only routing from a completed result's own evidence.

This module deliberately has no external review-label input.  It creates an
attempt-local receipt for a review queue; it neither changes nor authorizes a
publication decision.
"""

import hashlib
import json
import re
import unicodedata
from typing import Any, Mapping


SEMANTIC_REVIEW_ROUTER_SCHEMA = "semantic_review_router_receipt_v1"
SEMANTIC_REVIEW_ROUTER_MODE = "REVIEW_ONLY"
SEMANTIC_REVIEW_ROUTER_AUTHORITY = "attempt_local_result_evidence"
SEMANTIC_REVIEW_ROUTER_LEGACY_RULE_VERSION = "strict_evidence_v1"
SEMANTIC_REVIEW_ROUTER_RULE_VERSION = "strict_evidence_v2"
_RULE_VERSIONS = (SEMANTIC_REVIEW_ROUTER_LEGACY_RULE_VERSION, SEMANTIC_REVIEW_ROUTER_RULE_VERSION)
_MAX_DIRECT_OCR_ITEMS = 128

REVIEW_REQUIRED = "REVIEW_REQUIRED"
NO_REVIEW = "NO_REVIEW"
NOT_APPLICABLE = "NOT_APPLICABLE"
UNKNOWN = "UNKNOWN"

_STATES = frozenset({REVIEW_REQUIRED, NO_REVIEW, NOT_APPLICABLE, UNKNOWN})
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_TOP_LEVEL_FIELDS = {
    "schema_version",
    "publication_scope_id",
    "input_index",
    "post_id",
    "attempt_run_id",
    "authority",
    "mode",
    "public_apply",
    "rule_version",
    "source_view",
    "source_view_sha256",
    "trigger_codes",
    "unknown_reason_codes",
    "state",
    "publication_decision_id",
    "public_projection_sha256",
    "stable_result_sha256",
    "router_decision_sha256",
    "receipt_sha256",
}
_COMPLETE_SOURCE_VIEW_FIELDS = {
    "evidence_status",
    "is_relevant",
    "work_resolution",
    "publish_allowed",
    "scope_confidence",
    "reason_codes",
    "consistency_flags",
    "output_consistency_lint",
    "title_candidates",
    "candidate_preservation_present",
    "image_count",
    "comments_count",
}
_INVALID_SOURCE_VIEW_FIELDS = {"evidence_status", "errors"}
_CANDIDATE_VIEW_FIELDS = {
    "has_title",
    "reference_role",
    "source_tier",
    "page_type",
    "locked",
    "title_relation",
}
_CONFLICT_FLAGS = frozenset(
    {
        "vlm_ocr_title_conflict_with_final_title",
        "ocr_title_conflict_with_stable_alias",
        "promoted_image_work_title_conflicts_with_public_title",
        "official_detail_display_title_mismatch_held",
        "search_title_conflict_with_stable_alias",
        "stable_alias_conflict_weak_relation_hold",
    }
)
_NON_NOVEL_PAGE_TYPES = frozenset(
    {"news_page", "program_page", "game_page", "comic_page", "webtoon_page"}
)


class SemanticReviewRouterError(ValueError):
    """Raised when a receipt or its publication binding is not trustworthy."""


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


def _hex64(value: Any, *, field: str) -> str:
    normalized = str(value or "").strip().lower()
    if _HEX64.fullmatch(normalized) is None:
        raise SemanticReviewRouterError(f"{field} must be lowercase sha256")
    return normalized


def _post_id(value: Any, *, field: str = "post_id") -> int | str:
    if isinstance(value, bool) or value is None:
        raise SemanticReviewRouterError(f"{field} is invalid")
    if isinstance(value, int):
        if value <= 0:
            raise SemanticReviewRouterError(f"{field} is invalid")
        return value
    normalized = str(value).strip()
    if not normalized:
        raise SemanticReviewRouterError(f"{field} is invalid")
    return normalized


def _positive_index(value: Any, *, field: str = "input_index") -> int:
    if isinstance(value, bool):
        raise SemanticReviewRouterError(f"{field} must be a positive integer")
    try:
        normalized = int(value)
    except (TypeError, ValueError) as exc:
        raise SemanticReviewRouterError(f"{field} must be a positive integer") from exc
    if normalized <= 0:
        raise SemanticReviewRouterError(f"{field} must be a positive integer")
    return normalized


def _nonempty_text(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SemanticReviewRouterError(f"{field} must be non-empty text")
    return value.strip()


def _normalized_title(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        return ""
    return "".join(
        character
        for character in unicodedata.normalize("NFKC", value).casefold()
        if character.isalnum()
    )


def _string_list(value: Any, *, field: str, errors: list[str]) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        errors.append(f"INVALID_{field.upper()}")
        return []
    return sorted(set(item for item in value if item))


def _receipt_value(receipt: Any, field: str) -> Any:
    return receipt.get(field) if isinstance(receipt, Mapping) else getattr(receipt, field, None)


def _publication_binding(receipt: Any) -> dict[str, Any]:
    scope = _hex64(_receipt_value(receipt, "publication_scope_id"), field="publication_scope_id")
    index = _positive_index(_receipt_value(receipt, "input_index"))
    post_id = _post_id(_receipt_value(receipt, "post_id"))
    attempt_run_id = _nonempty_text(
        _receipt_value(receipt, "attempt_run_id"), field="publication receipt attempt_run_id"
    )
    return {
        "publication_scope_id": scope,
        "input_index": index,
        "post_id": post_id,
        "attempt_run_id": attempt_run_id,
        "publication_decision_id": _hex64(
            _receipt_value(receipt, "decision_id"), field="publication decision_id"
        ),
        "public_projection_sha256": _hex64(
            _receipt_value(receipt, "public_projection_sha256"),
            field="publication public_projection_sha256",
        ),
        "stable_result_sha256": _hex64(
            _receipt_value(receipt, "stable_result_sha256"),
            field="publication stable_result_sha256",
        ),
    }


def _unknown_view(errors: list[str]) -> dict[str, Any]:
    return {"evidence_status": "INVALID", "errors": sorted(set(errors))}


def _source_view(result: Any) -> tuple[dict[str, Any], list[str]]:
    """Return a title-free, whitelisted evidence snapshot and validation errors."""

    errors: list[str] = []
    if not isinstance(result, Mapping):
        return _unknown_view(["INVALID_RESULT"]), ["INVALID_RESULT"]
    analysis = result.get("analysis_result")
    identity = analysis.get("identity") if isinstance(analysis, Mapping) else None
    if not isinstance(identity, Mapping):
        return _unknown_view(["MISSING_TYPED_IDENTITY"]), ["MISSING_TYPED_IDENTITY"]

    is_relevant = identity.get("is_relevant")
    work_resolution = identity.get("work_resolution")
    decision = identity.get("promotion_decision")
    gate = identity.get("promotion_gate_state")
    if not isinstance(is_relevant, bool):
        errors.append("INVALID_IS_RELEVANT")
    if not isinstance(work_resolution, str) or not work_resolution:
        errors.append("INVALID_WORK_RESOLUTION")
    if not isinstance(decision, Mapping):
        errors.append("MISSING_PROMOTION_DECISION")
        decision = {}
    if not isinstance(gate, Mapping):
        errors.append("MISSING_PROMOTION_GATE_STATE")
        gate = {}

    publish_allowed = decision.get("publish_allowed")
    scope = decision.get("scope")
    if not isinstance(publish_allowed, bool):
        errors.append("INVALID_PUBLISH_ALLOWED")
    if not isinstance(scope, Mapping) or not isinstance(scope.get("confidence"), str):
        errors.append("INVALID_SCOPE_CONFIDENCE")
        scope = {}
    reason_codes = _string_list(decision.get("reason_codes"), field="reason_codes", errors=errors)
    flags = _string_list(identity.get("consistency_flags"), field="consistency_flags", errors=errors)
    output_lint = _string_list(
        identity.get("output_consistency_lint"), field="output_consistency_lint", errors=errors
    )

    title_candidates = identity.get("title_candidates")
    if title_candidates is None:
        title_candidates = []
    elif not isinstance(title_candidates, list):
        errors.append("INVALID_TITLE_CANDIDATES")
        title_candidates = []
    candidates: list[dict[str, Any]] = []
    public_title = _normalized_title(decision.get("official_title"))
    for item in title_candidates:
        if not isinstance(item, Mapping):
            errors.append("INVALID_TITLE_CANDIDATE")
            continue
        role, tier, page_type, locked = (
            item.get("reference_role"),
            item.get("source_tier"),
            item.get("page_type"),
            item.get("locked"),
        )
        if role is not None and not isinstance(role, str):
            errors.append("INVALID_CANDIDATE_ROLE")
        if tier is not None and not isinstance(tier, str):
            errors.append("INVALID_CANDIDATE_SOURCE_TIER")
        if page_type is not None and not isinstance(page_type, str):
            errors.append("INVALID_CANDIDATE_PAGE_TYPE")
        if locked is not None and not isinstance(locked, bool):
            errors.append("INVALID_CANDIDATE_LOCKED")
        candidate_title = _normalized_title(item.get("official_title"))
        candidates.append(
            {
                "has_title": bool(candidate_title),
                "reference_role": role if isinstance(role, str) else None,
                "source_tier": tier if isinstance(tier, str) else None,
                "page_type": page_type if isinstance(page_type, str) else None,
                "locked": locked if isinstance(locked, bool) else None,
                "title_relation": (
                    "MATCH_PUBLIC"
                    if candidate_title and candidate_title == public_title
                    else "DIFFERS_PUBLIC"
                    if candidate_title and public_title
                    else "UNBOUND"
                ),
            }
        )
    candidates.sort(
        key=lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )

    preserved = identity.get("candidate_preservation_sources")
    if preserved is None:
        preserved = []
    elif not isinstance(preserved, list):
        errors.append("INVALID_CANDIDATE_PRESERVATION_SOURCES")
        preserved = []
    if not all(isinstance(item, Mapping) for item in preserved):
        errors.append("INVALID_CANDIDATE_PRESERVATION_ITEM")

    image_count = result.get("image_count")
    comments = result.get("comments")
    if isinstance(image_count, bool) or not isinstance(image_count, int) or image_count < 0:
        errors.append("INVALID_IMAGE_COUNT")
    if not isinstance(comments, list):
        errors.append("INVALID_COMMENTS")

    gate_work_resolution = gate.get("work_resolution")
    if gate_work_resolution is not None and gate_work_resolution != work_resolution:
        errors.append("GATE_WORK_RESOLUTION_MISMATCH")
    if errors:
        return _unknown_view(errors), sorted(set(errors))
    return (
        {
            "evidence_status": "COMPLETE",
            "is_relevant": is_relevant,
            "work_resolution": work_resolution,
            "publish_allowed": publish_allowed,
            "scope_confidence": scope["confidence"],
            "reason_codes": reason_codes,
            "consistency_flags": flags,
            "output_consistency_lint": output_lint,
            "title_candidates": candidates,
            "candidate_preservation_present": bool(preserved),
            "image_count": image_count,
            "comments_count": len(comments),
        },
        [],
    )


def _validate_source_view(value: Any) -> tuple[dict[str, Any], list[str]]:
    if not isinstance(value, Mapping):
        raise SemanticReviewRouterError("source_view must be an object")
    source_view = dict(value)
    status = source_view.get("evidence_status")
    if status == "INVALID":
        if set(source_view) != _INVALID_SOURCE_VIEW_FIELDS:
            raise SemanticReviewRouterError("invalid source_view fields mismatch")
        errors = source_view.get("errors")
        if (
            not isinstance(errors, list)
            or not errors
            or not all(isinstance(item, str) and item for item in errors)
            or errors != sorted(set(errors))
        ):
            raise SemanticReviewRouterError("invalid source_view errors are invalid")
        return source_view, list(errors)
    if status != "COMPLETE" or set(source_view) != _COMPLETE_SOURCE_VIEW_FIELDS:
        raise SemanticReviewRouterError("complete source_view fields mismatch")
    if not isinstance(source_view.get("is_relevant"), bool):
        raise SemanticReviewRouterError("source_view is_relevant is invalid")
    if not isinstance(source_view.get("publish_allowed"), bool):
        raise SemanticReviewRouterError("source_view publish_allowed is invalid")
    for key in ("work_resolution", "scope_confidence"):
        if not isinstance(source_view.get(key), str) or not source_view[key]:
            raise SemanticReviewRouterError(f"source_view {key} is invalid")
    for key in ("reason_codes", "consistency_flags", "output_consistency_lint"):
        items = source_view.get(key)
        if (
            not isinstance(items, list)
            or not all(isinstance(item, str) and item for item in items)
            or items != sorted(set(items))
        ):
            raise SemanticReviewRouterError(f"source_view {key} is invalid")
    for key in ("candidate_preservation_present",):
        if not isinstance(source_view.get(key), bool):
            raise SemanticReviewRouterError(f"source_view {key} is invalid")
    for key in ("image_count", "comments_count"):
        numeric = source_view.get(key)
        if isinstance(numeric, bool) or not isinstance(numeric, int) or numeric < 0:
            raise SemanticReviewRouterError(f"source_view {key} is invalid")
    candidates = source_view.get("title_candidates")
    if not isinstance(candidates, list):
        raise SemanticReviewRouterError("source_view title_candidates is invalid")
    for candidate in candidates:
        if not isinstance(candidate, Mapping) or set(candidate) != _CANDIDATE_VIEW_FIELDS:
            raise SemanticReviewRouterError("source_view candidate fields mismatch")
        if not isinstance(candidate.get("has_title"), bool):
            raise SemanticReviewRouterError("source_view candidate has_title is invalid")
        for key in ("reference_role", "source_tier", "page_type"):
            if candidate.get(key) is not None and not isinstance(candidate.get(key), str):
                raise SemanticReviewRouterError(f"source_view candidate {key} is invalid")
        if candidate.get("locked") is not None and not isinstance(candidate.get("locked"), bool):
            raise SemanticReviewRouterError("source_view candidate locked is invalid")
        if candidate.get("title_relation") not in {"MATCH_PUBLIC", "DIFFERS_PUBLIC", "UNBOUND"}:
            raise SemanticReviewRouterError("source_view candidate title_relation is invalid")
    canonical_candidates = sorted(
        candidates,
        key=lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
    )
    if candidates != canonical_candidates:
        raise SemanticReviewRouterError("source_view title_candidates must be sorted")
    return source_view, []


def _route(source_view: Mapping[str, Any], errors: list[str]) -> tuple[str, list[str], list[str]]:
    if errors:
        return UNKNOWN, [], sorted(set(errors))
    flags = set(source_view["consistency_flags"])
    reason_codes = set(source_view["reason_codes"])
    candidates = source_view["title_candidates"]
    publish_allowed = source_view["publish_allowed"]
    triggers: set[str] = set()

    if source_view["output_consistency_lint"]:
        triggers.add("OUTPUT_CONSISTENCY_LINT")
    if flags.intersection(_CONFLICT_FLAGS):
        triggers.add("EXPLICIT_TITLE_CONFLICT")
    if source_view["work_resolution"] == "multi_work" or any(
        "multi_work" in flag or "competing" in flag for flag in flags
    ):
        triggers.add("MULTI_OR_COMPETING_EVIDENCE")
    if any(candidate["page_type"] in _NON_NOVEL_PAGE_TYPES for candidate in candidates):
        triggers.add("NON_NOVEL_MEDIA_CANDIDATE")
    if publish_allowed and (
        source_view["scope_confidence"] != "high"
        or any(
            candidate["reference_role"] == "primary"
            and candidate["title_relation"] == "DIFFERS_PUBLIC"
            for candidate in candidates
        )
    ):
        triggers.add("PUBLISHED_AMBIGUOUS_PRIMARY")
    if not publish_allowed and source_view["work_resolution"] != "resolved":
        if any(candidate["source_tier"] == "official_detail" for candidate in candidates):
            triggers.add("UNRESOLVED_OFFICIAL_DETAIL")
        if "ocr_explicit_title_unresolved" in flags:
            triggers.add("OCR_TITLE_UNRESOLVED")
        if "official_url_evidence_missing" in reason_codes:
            triggers.add("OFFICIAL_URL_EVIDENCE_MISSING")
    if triggers:
        return REVIEW_REQUIRED, sorted(triggers), []
    if (
        source_view["is_relevant"] is False
        and source_view["work_resolution"] == "none"
        and source_view["image_count"] == 0
        and source_view["comments_count"] == 0
        and not candidates
        and source_view["candidate_preservation_present"] is False
        and publish_allowed is False
    ):
        return NOT_APPLICABLE, [], []
    return NO_REVIEW, [], []


def _direct_ocr_evidence(result: Mapping[str, Any]) -> dict[str, Any]:
    """최종 catalog를 기존 제안 추출기로 검산하고 제목 없는 요약만 반환한다."""
    from ..ledger.recovery_activation import extract_direct_ocr_review_proposals

    identity = result["analysis_result"]["identity"]
    catalog = identity.get("image_evidence_catalog")
    if catalog is None:
        catalog = []
    if not isinstance(catalog, list) or not all(isinstance(item, Mapping) for item in catalog):
        raise SemanticReviewRouterError("direct OCR catalog is invalid")
    if len(catalog) > _MAX_DIRECT_OCR_ITEMS:
        raise SemanticReviewRouterError("direct OCR catalog limit exceeded")
    # v1의 canonical/hash 동작은 바꾸지 않고 새 evidence만 JSON wire로 제한한다.
    json.dumps(catalog, ensure_ascii=False, allow_nan=False)
    proposals = [item.to_dict() for item in extract_direct_ocr_review_proposals(result)]
    proposals.sort(key=_canonical_sha256)
    return {
        "proposal_count": len(proposals),
        "catalog_sha256": _canonical_sha256(catalog),
        "proposal_set_sha256": _canonical_sha256(proposals),
        "source_payload_sha256": sorted(item["source_payload_sha256"] for item in proposals),
    }


def _source_view_for_rule(result: Any, rule_version: str):
    source, errors = _source_view(result)
    if rule_version == SEMANTIC_REVIEW_ROUTER_LEGACY_RULE_VERSION or errors:
        return source, errors
    try:
        evidence = _direct_ocr_evidence(result)
    except (TypeError, ValueError):
        errors = ["INVALID_DIRECT_OCR_EVIDENCE"]
        return _unknown_view(errors), errors
    return {**source, "direct_ocr_evidence": evidence}, []


def _validate_source_view_for_rule(value: Any, rule_version: str):
    if (rule_version == SEMANTIC_REVIEW_ROUTER_LEGACY_RULE_VERSION
            or not isinstance(value, Mapping) or value.get("evidence_status") == "INVALID"):
        return _validate_source_view(value)
    if set(value) != _COMPLETE_SOURCE_VIEW_FIELDS | {"direct_ocr_evidence"}:
        raise SemanticReviewRouterError("complete v2 source_view fields mismatch")
    legacy = {key: item for key, item in value.items() if key != "direct_ocr_evidence"}
    _validate_source_view(legacy)
    evidence = value["direct_ocr_evidence"]
    if not isinstance(evidence, Mapping) or set(evidence) != {
            "proposal_count", "catalog_sha256", "proposal_set_sha256", "source_payload_sha256"}:
        raise SemanticReviewRouterError("direct OCR evidence fields mismatch")
    count = evidence["proposal_count"]
    if type(count) is not int or not 0 <= count <= _MAX_DIRECT_OCR_ITEMS:
        raise SemanticReviewRouterError("direct OCR proposal count is invalid")
    pins = evidence["source_payload_sha256"]
    if (not isinstance(pins, list) or len(pins) != count
            or any(type(pin) is not str or _HEX64.fullmatch(pin) is None for pin in pins)
            or pins != sorted(set(pins))):
        raise SemanticReviewRouterError("direct OCR source pins are invalid")
    for key in ("catalog_sha256", "proposal_set_sha256"):
        if type(evidence[key]) is not str or _HEX64.fullmatch(evidence[key]) is None:
            raise SemanticReviewRouterError("direct OCR evidence hash is invalid")
    if count == 0 and evidence["proposal_set_sha256"] != _canonical_sha256([]):
        raise SemanticReviewRouterError("empty direct OCR proposal hash mismatch")
    return dict(value), []


def _route_for_rule(source_view, errors, rule_version):
    state, triggers, unknown = _route(source_view, errors)
    if (rule_version == SEMANTIC_REVIEW_ROUTER_LEGACY_RULE_VERSION or errors
            or source_view["publish_allowed"] or source_view["work_resolution"] == "resolved"):
        return state, triggers, unknown
    count = source_view["direct_ocr_evidence"]["proposal_count"]
    if count:
        code = "DIRECT_OCR_HOLD_CANDIDATE" if count == 1 else "MULTIPLE_DIRECT_OCR_HOLD_CANDIDATES"
        return REVIEW_REQUIRED, sorted({*triggers, code}), []
    return state, triggers, unknown


def _validate_v2_result_binding(result, receipt):
    # source_view까지 재봉인해도 원래 WAL의 공개/안정 payload 지문은 대체할 수 없다.
    from ..ledger.publication_commit import compute_publication_decision_commit

    try:
        actual = compute_publication_decision_commit(
            result, publication_scope_id=receipt["publication_scope_id"],
            attempt_run_id=receipt["attempt_run_id"], input_index=receipt["input_index"],
            post_id=receipt["post_id"],
        )
        binding = _publication_binding(actual)
    except (TypeError, ValueError) as exc:
        raise SemanticReviewRouterError("v2 result publication binding is invalid") from exc
    for key in ("publication_decision_id", "public_projection_sha256", "stable_result_sha256"):
        if receipt[key] != binding[key]:
            raise SemanticReviewRouterError("v2 result publication binding mismatch: " + key)



def _router_decision_material(receipt: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: receipt[key]
        for key in (
            "schema_version",
            "publication_scope_id",
            "input_index",
            "post_id",
            "attempt_run_id",
            "authority",
            "mode",
            "public_apply",
            "rule_version",
            "source_view_sha256",
            "trigger_codes",
            "unknown_reason_codes",
            "state",
            "publication_decision_id",
            "public_projection_sha256",
            "stable_result_sha256",
        )
    }


def build_semantic_review_router_receipt(
    result: Mapping[str, Any],
    publication_receipt: Any,
    *,
    attempt_run_id: str,
    rule_version: str = SEMANTIC_REVIEW_ROUTER_RULE_VERSION,
) -> dict[str, Any]:
    """Build a self-hashed, no-public-write receipt from result evidence only."""

    if rule_version not in _RULE_VERSIONS:
        raise SemanticReviewRouterError("receipt rule version mismatch")
    binding = _publication_binding(publication_receipt)
    requested_attempt = _nonempty_text(attempt_run_id, field="attempt_run_id")
    if requested_attempt != binding["attempt_run_id"]:
        raise SemanticReviewRouterError("attempt_run_id does not match publication receipt")
    if not isinstance(result, Mapping):
        raise SemanticReviewRouterError("result must be an object")
    if str(_post_id(result.get("post_id"), field="result post_id")) != str(binding["post_id"]):
        raise SemanticReviewRouterError("result post_id does not match publication receipt")
    source_view, errors = _source_view_for_rule(result, rule_version)
    state, trigger_codes, unknown_reason_codes = _route_for_rule(source_view, errors, rule_version)
    material = {
        "schema_version": SEMANTIC_REVIEW_ROUTER_SCHEMA,
        "publication_scope_id": binding["publication_scope_id"],
        "input_index": binding["input_index"],
        "post_id": binding["post_id"],
        "attempt_run_id": requested_attempt,
        "authority": SEMANTIC_REVIEW_ROUTER_AUTHORITY,
        "mode": SEMANTIC_REVIEW_ROUTER_MODE,
        "public_apply": False,
        "rule_version": rule_version,
        "source_view": source_view,
        "source_view_sha256": _canonical_sha256(source_view),
        "trigger_codes": trigger_codes,
        "unknown_reason_codes": unknown_reason_codes,
        "state": state,
        **binding,
    }
    material.pop("attempt_run_id")
    material["attempt_run_id"] = requested_attempt
    material["router_decision_sha256"] = _canonical_sha256(_router_decision_material(material))
    return {**material, "receipt_sha256": _canonical_sha256(material)}


def validate_semantic_review_router_receipt(
    value: Any,
    *,
    result: Mapping[str, Any] | None = None,
    expected_publication_receipt: Any = None,
    expected_scope_id: Any = None,
    expected_input_index: Any = None,
    expected_post_id: Any = None,
    expected_attempt_run_id: str | None = None,
) -> dict[str, Any]:
    """Validate exact schema, hashes, routing semantics, and optional bindings."""

    if not isinstance(value, Mapping):
        raise SemanticReviewRouterError("receipt must be an object")
    if set(value) != _TOP_LEVEL_FIELDS:
        raise SemanticReviewRouterError("receipt fields mismatch")
    if value.get("schema_version") != SEMANTIC_REVIEW_ROUTER_SCHEMA:
        raise SemanticReviewRouterError("receipt schema mismatch")
    if value.get("authority") != SEMANTIC_REVIEW_ROUTER_AUTHORITY:
        raise SemanticReviewRouterError("receipt authority mismatch")
    if value.get("mode") != SEMANTIC_REVIEW_ROUTER_MODE:
        raise SemanticReviewRouterError("receipt mode mismatch")
    if value.get("public_apply") is not False:
        raise SemanticReviewRouterError("receipt cannot apply publicly")
    rule_version = value.get("rule_version")
    if rule_version not in _RULE_VERSIONS:
        raise SemanticReviewRouterError("receipt rule version mismatch")

    normalized = dict(value)
    normalized["publication_scope_id"] = _hex64(value.get("publication_scope_id"), field="publication_scope_id")
    normalized["input_index"] = _positive_index(value.get("input_index"))
    normalized["post_id"] = _post_id(value.get("post_id"))
    normalized["attempt_run_id"] = _nonempty_text(value.get("attempt_run_id"), field="attempt_run_id")
    for key in (
        "source_view_sha256",
        "publication_decision_id",
        "public_projection_sha256",
        "stable_result_sha256",
        "router_decision_sha256",
        "receipt_sha256",
    ):
        normalized[key] = _hex64(value.get(key), field=key)
    if not isinstance(value.get("source_view"), Mapping):
        raise SemanticReviewRouterError("source_view must be an object")
    normalized["source_view"] = dict(value["source_view"])
    if normalized["source_view_sha256"] != _canonical_sha256(normalized["source_view"]):
        raise SemanticReviewRouterError("source_view hash mismatch")
    for key in ("trigger_codes", "unknown_reason_codes"):
        items = value.get(key)
        if not isinstance(items, list) or not all(isinstance(item, str) and item for item in items):
            raise SemanticReviewRouterError(f"{key} must be non-empty string list")
        if items != sorted(set(items)):
            raise SemanticReviewRouterError(f"{key} must be sorted and unique")
        normalized[key] = list(items)
    state = value.get("state")
    if state not in _STATES:
        raise SemanticReviewRouterError("receipt state is invalid")
    normalized["state"] = state
    if rule_version == SEMANTIC_REVIEW_ROUTER_RULE_VERSION and result is not None:
        # 원문과 값이 같더라도 True == 1 같은 타입 치환은 먼저 거절한다.
        _validate_source_view_for_rule(normalized["source_view"], rule_version)
    if result is not None:
        if str(_post_id(result.get("post_id"), field="result post_id")) != str(normalized["post_id"]):
            raise SemanticReviewRouterError("result post_id mismatch")
        source_view, errors = _source_view_for_rule(result, rule_version)
    else:
        source_view, errors = _validate_source_view_for_rule(normalized["source_view"], rule_version)
    if result is not None and normalized["source_view"] != source_view:
        raise SemanticReviewRouterError("source_view does not match result")
    expected_state, expected_triggers, expected_unknown = _route_for_rule(source_view, errors, rule_version)
    if (
        state != expected_state
        or normalized["trigger_codes"] != expected_triggers
        or normalized["unknown_reason_codes"] != expected_unknown
    ):
        raise SemanticReviewRouterError("receipt state/trigger consistency mismatch")
    if normalized["router_decision_sha256"] != _canonical_sha256(_router_decision_material(normalized)):
        raise SemanticReviewRouterError("router decision hash mismatch")
    receipt_material = {key: normalized[key] for key in _TOP_LEVEL_FIELDS if key != "receipt_sha256"}
    if normalized["receipt_sha256"] != _canonical_sha256(receipt_material):
        raise SemanticReviewRouterError("receipt hash mismatch")

    if expected_publication_receipt is not None:
        binding = _publication_binding(expected_publication_receipt)
        for key, expected in binding.items():
            if normalized[key] != expected:
                raise SemanticReviewRouterError(f"publication receipt {key} mismatch")
    if expected_scope_id is not None and normalized["publication_scope_id"] != _hex64(expected_scope_id, field="expected_scope_id"):
        raise SemanticReviewRouterError("publication_scope_id mismatch")
    if expected_input_index is not None and normalized["input_index"] != _positive_index(expected_input_index, field="expected_input_index"):
        raise SemanticReviewRouterError("input_index mismatch")
    if expected_post_id is not None and str(normalized["post_id"]) != str(_post_id(expected_post_id, field="expected_post_id")):
        raise SemanticReviewRouterError("post_id mismatch")
    if expected_attempt_run_id is not None and normalized["attempt_run_id"] != _nonempty_text(expected_attempt_run_id, field="expected_attempt_run_id"):
        raise SemanticReviewRouterError("attempt_run_id mismatch")
    if rule_version == SEMANTIC_REVIEW_ROUTER_RULE_VERSION and result is not None:
        _validate_v2_result_binding(result, normalized)
    return normalized
