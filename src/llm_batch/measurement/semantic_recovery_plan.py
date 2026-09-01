from __future__ import annotations

"""Deterministic P1 recovery plans that never execute or publish anything."""

import hashlib
import json
import re
import unicodedata
from typing import Any, Mapping
from urllib.parse import parse_qs, urlsplit, urlunsplit

from ..ledger.publication_commit import (
    PublicationCommitError,
    PublicationDecisionCommit,
    validate_publication_result_commit,
)


SEMANTIC_RECOVERY_PLAN_SCHEMA = "semantic_recovery_plan_receipt_v1"
SEMANTIC_RECOVERY_PLAN_MODE = "PLAN_ONLY"
SEMANTIC_RECOVERY_PLAN_AUTHORITY = "attempt_local_completed_result_evidence"
SEMANTIC_RECOVERY_PLAN_RULE_VERSION = "p1_review_recovery_plan_v1"

PLAN_HOLD = "HOLD"
PLAN_NOT_APPLICABLE = "NOT_APPLICABLE"
PLAN_UNKNOWN = "UNKNOWN"

_PLAN_STATES = frozenset({PLAN_HOLD, PLAN_NOT_APPLICABLE, PLAN_UNKNOWN})
_RELATION_ROLES = frozenset({"primary", "previous", "mentioned", "comparison"})
_NOVEL_PAGE_TYPES = frozenset({"novel_page"})
_ACTIVE_CONTENT_STATUSES = frozenset({"active", "ongoing", "completed"})
_NON_NOVEL_PAGE_TYPES = frozenset(
    {"news_page", "program_page", "game_page", "comic_page", "webtoon_page"}
)
_HEALTHY_SEARCH_STATUSES = frozenset({"healthy", "ok", "search_ok"})
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
    "plan",
    "plan_sha256",
    "publication_decision_id",
    "public_projection_sha256",
    "stable_result_sha256",
    "receipt_sha256",
}
_PLAN_FIELDS = {
    "state",
    "blocker_codes",
    "relationship_counts",
    "primary_identity_count",
    "media_action",
    "canonical_bindings",
    "raw_ocr_evidence_count",
    "query_plan",
    "search_calls_executed",
    "network_calls_executed",
}
_QUERY_PLAN_FIELDS = {
    "purposes",
    "query_execution_allowed",
    "max_queries",
    "search_health",
}
_BINDING_FIELDS = {
    "canonical_work_id",
    "canonical_url",
    "display_title",
    "relation_role",
}
_COMPLETE_SOURCE_FIELDS = {
    "evidence_status",
    "is_relevant",
    "work_resolution",
    "publish_allowed",
    "decision_reason_codes",
    "semantic_publication",
    "candidate_evidence",
    "raw_ocr_evidence_count",
    "search_health",
}
_INVALID_SOURCE_FIELDS = {"evidence_status", "errors"}
_SEMANTIC_FIELDS = {"evidence_status", "media_domain_class", "primary_work_status"}
_CANDIDATE_FIELDS = {
    "relation_role",
    "source_tier",
    "page_type",
    "content_status",
    "has_display_title",
    "display_key_sha256",
    "stable_identity_status",
    "canonical_work_id",
    "canonical_url",
    "verified_display_title",
}


class SemanticRecoveryPlanError(ValueError):
    """Raised when plan evidence or receipt integrity is not trustworthy."""


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


def _receipt_value(receipt: Any, field: str) -> Any:
    return receipt.get(field) if isinstance(receipt, Mapping) else getattr(receipt, field, None)


def _hex64(value: Any, *, field: str) -> str:
    normalized = str(value or "").strip().lower()
    if _HEX64.fullmatch(normalized) is None:
        raise SemanticRecoveryPlanError(f"{field} must be lowercase sha256")
    return normalized


def _post_id(value: Any, *, field: str = "post_id") -> int | str:
    if isinstance(value, bool) or value is None:
        raise SemanticRecoveryPlanError(f"{field} is invalid")
    if isinstance(value, int):
        if value <= 0:
            raise SemanticRecoveryPlanError(f"{field} is invalid")
        return value
    normalized = str(value).strip()
    if not normalized:
        raise SemanticRecoveryPlanError(f"{field} is invalid")
    return normalized


def _positive_index(value: Any, *, field: str = "input_index") -> int:
    if isinstance(value, bool):
        raise SemanticRecoveryPlanError(f"{field} must be a positive integer")
    try:
        normalized = int(value)
    except (TypeError, ValueError) as exc:
        raise SemanticRecoveryPlanError(f"{field} must be a positive integer") from exc
    if normalized <= 0:
        raise SemanticRecoveryPlanError(f"{field} must be a positive integer")
    return normalized


def _text(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SemanticRecoveryPlanError(f"{field} must be non-empty text")
    return value.strip()


def _publication_binding(receipt: Any) -> dict[str, Any]:
    authoritative = _publication_commit(receipt)
    return {
        "publication_scope_id": _hex64(
            _receipt_value(authoritative, "publication_scope_id"), field="publication_scope_id"
        ),
        "input_index": _positive_index(_receipt_value(authoritative, "input_index")),
        "post_id": _post_id(_receipt_value(authoritative, "post_id")),
        "attempt_run_id": _text(
            _receipt_value(authoritative, "attempt_run_id"), field="publication attempt_run_id"
        ),
        "publication_decision_id": _hex64(
            _receipt_value(authoritative, "decision_id"), field="publication decision_id"
        ),
        "public_projection_sha256": _hex64(
            _receipt_value(authoritative, "public_projection_sha256"),
            field="publication public_projection_sha256",
        ),
        "stable_result_sha256": _hex64(
            _receipt_value(authoritative, "stable_result_sha256"),
            field="publication stable_result_sha256",
        ),
    }


def _publication_commit(receipt: Any) -> PublicationDecisionCommit:
    try:
        if isinstance(receipt, PublicationDecisionCommit):
            authoritative = receipt
        elif isinstance(receipt, Mapping):
            authoritative = PublicationDecisionCommit.from_dict(receipt)
        else:
            serializer = getattr(receipt, "to_dict", None)
            if not callable(serializer):
                raise PublicationCommitError(
                    "publication decision commit must be an object"
                )
            authoritative = PublicationDecisionCommit.from_dict(serializer())
        authoritative.validate()
    except (PublicationCommitError, TypeError, ValueError) as exc:
        raise SemanticRecoveryPlanError("publication receipt is invalid") from exc
    return authoritative


def _normalized_display(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        return ""
    return "".join(
        character
        for character in unicodedata.normalize("NFKC", value).casefold()
        if character.isalnum()
    )


def _normalized_text(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_")


def _string_list(value: Any, *, field: str, errors: list[str]) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        errors.append(f"INVALID_{field.upper()}")
        return []
    return sorted(set(item.strip() for item in value if item.strip()))


def _canonical_detail_identity(value: Any) -> tuple[str, str] | None:
    """Parse stable numeric official-detail identities without resolving URLs."""

    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = urlsplit(value.strip())
    except ValueError:
        return None
    if parsed.scheme.lower() != "https" or parsed.fragment:
        return None
    host = (parsed.hostname or "").lower()
    path = parsed.path.rstrip("/")
    if host == "page.kakao.com":
        match = re.fullmatch(r"/content/(\d+)", path)
        if not match or parsed.query:
            return None
        return f"kakao:{match.group(1)}", urlunsplit(("https", host, path, "", ""))
    if host == "series.naver.com" and path == "/novel/detail.series":
        query = parse_qs(parsed.query, keep_blank_values=False)
        values = query.get("productNo")
        if set(query) != {"productNo"} or not values or len(values) != 1:
            return None
        if re.fullmatch(r"\d+", values[0]) is None:
            return None
        canonical = f"https://{host}{path}?productNo={values[0]}"
        return f"naver:{values[0]}", canonical
    if host == "novelpia.com":
        match = re.fullmatch(r"/novel/(\d+)", path)
        if not match or parsed.query:
            return None
        return f"novelpia:{match.group(1)}", urlunsplit(("https", host, path, "", ""))
    return None


def _relation_role(value: Any, *, default: str | None, errors: list[str]) -> str:
    role = _normalized_text(value) if value not in (None, "") else default or ""
    aliases = {
        "secondary": "mentioned",
        "candidate": "mentioned",
        "recommendation": "mentioned",
        "recommendation_candidate": "mentioned",
        "future_watch_target": "mentioned",
        "previous_work": "previous",
        "comparison_target": "comparison",
    }
    if role in aliases:
        role = aliases[role]
    if role not in _RELATION_ROLES:
        errors.append("INVALID_RELATION_ROLE")
        return "mentioned"
    return role


def _candidate_view(
    item: Mapping[str, Any], *, default_role: str | None, errors: list[str]
) -> dict[str, Any]:
    role = _relation_role(item.get("reference_role"), default=default_role, errors=errors)
    tier = _normalized_text(item.get("source_tier"))
    page_type = _normalized_text(item.get("page_type"))
    content_status = _normalized_text(item.get("content_status"))
    display_title = item.get("official_title")
    if display_title is not None and not isinstance(display_title, str):
        errors.append("INVALID_CANDIDATE_DISPLAY_TITLE")
        display_title = ""
    display = str(display_title or "").strip()
    display_key = _normalized_display(display)
    candidate_url = item.get("heretic_url") or item.get("official_url")
    if candidate_url is not None and not isinstance(candidate_url, str):
        errors.append("INVALID_CANDIDATE_URL")
        candidate_url = ""
    stable = _canonical_detail_identity(candidate_url)
    typed_official = (
        tier == "official_detail"
        and page_type in _NOVEL_PAGE_TYPES
        and content_status in _ACTIVE_CONTENT_STATUSES
        and bool(display_key)
        and stable is not None
    )
    return {
        "relation_role": role,
        "source_tier": tier,
        "page_type": page_type,
        "content_status": content_status,
        "has_display_title": bool(display_key),
        "display_key_sha256": _canonical_sha256(display_key) if display_key else None,
        "stable_identity_status": (
            "VERIFIED_OFFICIAL_DETAIL"
            if typed_official
            else "MALFORMED_OR_LISTING_OFFICIAL_DETAIL"
            if tier == "official_detail"
            else "UNVERIFIED_RAW_EVIDENCE"
        ),
        "canonical_work_id": stable[0] if typed_official else None,
        "canonical_url": stable[1] if typed_official else None,
        "verified_display_title": display if typed_official else None,
    }


def _collect_candidates(identity: Mapping[str, Any], errors: list[str]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    containers = (
        ("title_candidates", None, True),
        ("primary_work", "primary", False),
        ("mentioned_works", "mentioned", True),
        ("secondary_reference_works", "mentioned", True),
        ("comparison_target", "comparison", False),
    )
    for key, default_role, multiple in containers:
        value = identity.get(key)
        if value is None:
            continue
        items = value if multiple else [value]
        if not isinstance(items, list):
            errors.append(f"INVALID_{key.upper()}")
            continue
        for item in items:
            if not isinstance(item, Mapping):
                errors.append("INVALID_CANDIDATE_EVIDENCE")
                continue
            candidates.append(_candidate_view(item, default_role=default_role, errors=errors))
    deduplicated: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        key = json.dumps(candidate, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        deduplicated[key] = candidate
    return [deduplicated[key] for key in sorted(deduplicated)]


def _semantic_view(gate: Mapping[str, Any], errors: list[str]) -> dict[str, str]:
    value = gate.get("semantic_publication")
    if value is None:
        return {field: "" for field in sorted(_SEMANTIC_FIELDS)}
    if not isinstance(value, Mapping) or set(value) != _SEMANTIC_FIELDS:
        errors.append("INVALID_SEMANTIC_PUBLICATION_STATE")
        return {field: "" for field in sorted(_SEMANTIC_FIELDS)}
    normalized: dict[str, str] = {}
    for field in sorted(_SEMANTIC_FIELDS):
        item = value.get(field)
        if not isinstance(item, str):
            errors.append("INVALID_SEMANTIC_PUBLICATION_STATE")
            item = ""
        normalized[field] = _normalized_text(item)
    return normalized


def _raw_ocr_count(identity: Mapping[str, Any], errors: list[str]) -> int:
    catalog = identity.get("image_evidence_catalog")
    if catalog is None:
        return 0
    if not isinstance(catalog, list):
        errors.append("INVALID_IMAGE_EVIDENCE_CATALOG")
        return 0
    count = 0
    for item in catalog:
        if not isinstance(item, Mapping):
            errors.append("INVALID_IMAGE_EVIDENCE_ITEM")
            continue
        if (
            _normalized_text(item.get("evidence_type")) == "explicit_text"
            and _normalized_text(item.get("title_role")) == "work_title"
            and isinstance(item.get("explicit_work_title"), str)
            and item["explicit_work_title"].strip()
        ):
            count += 1
    return count


def _source_view(result: Any) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    if not isinstance(result, Mapping):
        return {"evidence_status": "INVALID", "errors": ["INVALID_RESULT"]}, ["INVALID_RESULT"]
    analysis = result.get("analysis_result")
    identity = analysis.get("identity") if isinstance(analysis, Mapping) else None
    if not isinstance(identity, Mapping):
        errors.append("MISSING_TYPED_IDENTITY")
        return {"evidence_status": "INVALID", "errors": errors}, errors
    decision = identity.get("promotion_decision")
    gate = identity.get("promotion_gate_state")
    if not isinstance(decision, Mapping):
        errors.append("MISSING_PROMOTION_DECISION")
        decision = {}
    if not isinstance(gate, Mapping):
        errors.append("MISSING_PROMOTION_GATE_STATE")
        gate = {}
    is_relevant = identity.get("is_relevant")
    work_resolution = identity.get("work_resolution")
    publish_allowed = decision.get("publish_allowed")
    if not isinstance(is_relevant, bool):
        errors.append("INVALID_IS_RELEVANT")
    if not isinstance(work_resolution, str) or not work_resolution.strip():
        errors.append("INVALID_WORK_RESOLUTION")
    if not isinstance(publish_allowed, bool):
        errors.append("INVALID_PUBLISH_ALLOWED")
    reason_codes = _string_list(
        decision.get("reason_codes"), field="decision_reason_codes", errors=errors
    )
    semantic = _semantic_view(gate, errors)
    candidates = _collect_candidates(identity, errors)
    raw_ocr_count = _raw_ocr_count(identity, errors)
    search = identity.get("search_health")
    if search is None:
        search_status = "unknown"
    elif isinstance(search, Mapping) and isinstance(search.get("status"), str):
        search_status = _normalized_text(search.get("status")) or "unknown"
    else:
        errors.append("INVALID_SEARCH_HEALTH")
        search_status = "unknown"
    if errors:
        normalized_errors = sorted(set(errors))
        return {"evidence_status": "INVALID", "errors": normalized_errors}, normalized_errors
    return (
        {
            "evidence_status": "COMPLETE",
            "is_relevant": is_relevant,
            "work_resolution": work_resolution.strip().lower(),
            "publish_allowed": publish_allowed,
            "decision_reason_codes": reason_codes,
            "semantic_publication": semantic,
            "candidate_evidence": candidates,
            "raw_ocr_evidence_count": raw_ocr_count,
            "search_health": search_status,
        },
        [],
    )


def _identity_key(candidate: Mapping[str, Any]) -> str | None:
    display_key = candidate.get("display_key_sha256")
    if isinstance(display_key, str):
        return f"display:{display_key}"
    canonical_id = candidate.get("canonical_work_id")
    return f"id:{canonical_id}" if isinstance(canonical_id, str) else None


def _query_purposes(blockers: set[str]) -> list[str]:
    mapping = {
        "MISSING_PRIMARY": "RESOLVE_PRIMARY_RELATION",
        "MULTIPLE_PRIMARY": "DISAMBIGUATE_PRIMARY_RELATION",
        "PRIMARY_AMBIGUOUS": "DISAMBIGUATE_PRIMARY_RELATION",
        "PRIMARY_CANONICAL_ID_UNBOUND": "VERIFY_OFFICIAL_DETAIL_ID",
        "OFFICIAL_DETAIL_ID_UNAVAILABLE": "VERIFY_OFFICIAL_DETAIL_ID",
        "CANONICAL_ID_DISPLAY_COLLISION": "RESOLVE_CANONICAL_ID_DISPLAY_COLLISION",
        "EVIDENCE_CONFLICT": "RESOLVE_EVIDENCE_CONFLICT",
        "EVIDENCE_INSUFFICIENT": "RESOLVE_EVIDENCE_SUFFICIENCY",
        "CROSS_MEDIA_CONFLICT": "RESOLVE_CROSS_MEDIA_RELATION",
        "OFFICIAL_URL_EVIDENCE_MISSING": "VERIFY_OFFICIAL_DETAIL_ID",
    }
    return sorted({mapping[blocker] for blocker in blockers if blocker in mapping})


def _plan(source: Mapping[str, Any], errors: list[str]) -> dict[str, Any]:
    if errors:
        return {
            "state": PLAN_UNKNOWN,
            "blocker_codes": sorted(set(errors)),
            "relationship_counts": {role: 0 for role in sorted(_RELATION_ROLES)},
            "primary_identity_count": 0,
            "media_action": "UNKNOWN",
            "canonical_bindings": [],
            "raw_ocr_evidence_count": 0,
            "query_plan": {
                "purposes": [],
                "query_execution_allowed": False,
                "max_queries": 0,
                "search_health": "unknown",
            },
            "search_calls_executed": 0,
            "network_calls_executed": 0,
        }
    candidates = source["candidate_evidence"]
    counts = {
        role: sum(candidate["relation_role"] == role for candidate in candidates)
        for role in sorted(_RELATION_ROLES)
    }
    primary_keys = {
        key
        for candidate in candidates
        if candidate["relation_role"] == "primary"
        for key in [_identity_key(candidate)]
        if key is not None
    }
    blockers: set[str] = set()
    if not primary_keys:
        blockers.add("MISSING_PRIMARY")
    elif len(primary_keys) > 1:
        blockers.add("MULTIPLE_PRIMARY")
    primary_candidates = [
        candidate for candidate in candidates if candidate["relation_role"] == "primary"
    ]
    if primary_candidates and not any(
        candidate["stable_identity_status"] == "VERIFIED_OFFICIAL_DETAIL"
        for candidate in primary_candidates
    ):
        blockers.add("PRIMARY_CANONICAL_ID_UNBOUND")
    if any(
        candidate["source_tier"] == "official_detail"
        and candidate["stable_identity_status"] != "VERIFIED_OFFICIAL_DETAIL"
        for candidate in candidates
    ):
        blockers.add("OFFICIAL_DETAIL_ID_UNAVAILABLE")
    semantic = source["semantic_publication"]
    evidence_status = semantic["evidence_status"]
    if evidence_status and evidence_status != "sufficient":
        blockers.add("EVIDENCE_CONFLICT" if evidence_status == "conflict" else "EVIDENCE_INSUFFICIENT")
    media_domain = semantic["media_domain_class"]
    typed_non_novel = media_domain == "non_novel_media" or any(
        candidate["page_type"] in _NON_NOVEL_PAGE_TYPES for candidate in candidates
    )
    cross_media = media_domain == "cross_media_unresolved"
    if typed_non_novel:
        blockers.add("TYPED_NON_NOVEL_MEDIA")
    if cross_media:
        blockers.add("CROSS_MEDIA_CONFLICT")
    primary_status = semantic["primary_work_status"]
    if primary_status in {"multiple", "multiwork"}:
        blockers.add("MULTIPLE_PRIMARY")
    elif primary_status in {"missing", "none", "no_unique", "ambiguous"}:
        blockers.add("MISSING_PRIMARY" if primary_status != "ambiguous" else "PRIMARY_AMBIGUOUS")
    if "official_url_evidence_missing" in source["decision_reason_codes"]:
        blockers.add("OFFICIAL_URL_EVIDENCE_MISSING")

    verified = [
        candidate
        for candidate in candidates
        if candidate["stable_identity_status"] == "VERIFIED_OFFICIAL_DETAIL"
    ]
    by_id: dict[str, set[str]] = {}
    by_display: dict[str, set[str]] = {}
    for candidate in verified:
        canonical_id = candidate["canonical_work_id"]
        display_key = candidate["display_key_sha256"]
        by_id.setdefault(canonical_id, set()).add(display_key)
        by_display.setdefault(display_key, set()).add(canonical_id)
    collision = any(len(values) > 1 for values in by_id.values()) or any(
        len(values) > 1 for values in by_display.values()
    )
    if collision:
        blockers.add("CANONICAL_ID_DISPLAY_COLLISION")
    canonical_bindings = []
    if not collision:
        seen: set[tuple[str, str]] = set()
        for candidate in verified:
            key = (candidate["canonical_work_id"], candidate["relation_role"])
            if key in seen:
                continue
            seen.add(key)
            canonical_bindings.append(
                {
                    "canonical_work_id": candidate["canonical_work_id"],
                    "canonical_url": candidate["canonical_url"],
                    "display_title": candidate["verified_display_title"],
                    "relation_role": candidate["relation_role"],
                }
            )
    canonical_bindings.sort(
        key=lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )
    no_signal = (
        source["publish_allowed"] is False
        and source["is_relevant"] is False
        and source["work_resolution"] == "none"
        and not candidates
        and source["raw_ocr_evidence_count"] == 0
        and not semantic["evidence_status"]
        and not semantic["media_domain_class"]
        and not semantic["primary_work_status"]
    )
    state = (
        PLAN_NOT_APPLICABLE
        if no_signal or (source["publish_allowed"] is True and not blockers)
        else PLAN_HOLD
    )
    if state == PLAN_NOT_APPLICABLE:
        blockers.clear()
        canonical_bindings = []
    purposes = _query_purposes(blockers)
    healthy = source["search_health"] in _HEALTHY_SEARCH_STATUSES
    query_allowed = state == PLAN_HOLD and healthy and bool(purposes)
    query_plan = {
        "purposes": purposes if state == PLAN_HOLD else [],
        "query_execution_allowed": query_allowed,
        "max_queries": min(len(purposes), 2) if query_allowed else 0,
        "search_health": source["search_health"],
    }
    return {
        "state": state,
        "blocker_codes": sorted(blockers),
        "relationship_counts": counts,
        "primary_identity_count": len(primary_keys),
        "media_action": (
            "QUARANTINE_NON_NOVEL"
            if typed_non_novel
            else "HOLD_CROSS_MEDIA"
            if cross_media
            else "NO_MEDIA_ACTION"
        ),
        "canonical_bindings": canonical_bindings,
        "raw_ocr_evidence_count": source["raw_ocr_evidence_count"],
        "query_plan": query_plan,
        "search_calls_executed": 0,
        "network_calls_executed": 0,
    }


def _validate_sorted_strings(value: Any, *, field: str) -> list[str]:
    if (
        not isinstance(value, list)
        or not all(isinstance(item, str) and item for item in value)
        or value != sorted(set(value))
    ):
        raise SemanticRecoveryPlanError(f"{field} must be sorted unique strings")
    return list(value)


def _validate_source_view(value: Any) -> tuple[dict[str, Any], list[str]]:
    if not isinstance(value, Mapping):
        raise SemanticRecoveryPlanError("source_view must be an object")
    source = dict(value)
    if source.get("evidence_status") == "INVALID":
        if set(source) != _INVALID_SOURCE_FIELDS:
            raise SemanticRecoveryPlanError("invalid source_view fields mismatch")
        errors = _validate_sorted_strings(source.get("errors"), field="source_view.errors")
        if not errors:
            raise SemanticRecoveryPlanError("invalid source_view errors cannot be empty")
        return source, errors
    if source.get("evidence_status") != "COMPLETE" or set(source) != _COMPLETE_SOURCE_FIELDS:
        raise SemanticRecoveryPlanError("complete source_view fields mismatch")
    if not isinstance(source.get("is_relevant"), bool) or not isinstance(
        source.get("publish_allowed"), bool
    ):
        raise SemanticRecoveryPlanError("source_view booleans are invalid")
    if not isinstance(source.get("work_resolution"), str) or not source["work_resolution"]:
        raise SemanticRecoveryPlanError("source_view work_resolution is invalid")
    _validate_sorted_strings(source.get("decision_reason_codes"), field="decision_reason_codes")
    semantic = source.get("semantic_publication")
    if not isinstance(semantic, Mapping) or set(semantic) != _SEMANTIC_FIELDS or not all(
        isinstance(semantic[field], str) for field in _SEMANTIC_FIELDS
    ):
        raise SemanticRecoveryPlanError("source_view semantic publication is invalid")
    candidates = source.get("candidate_evidence")
    if not isinstance(candidates, list):
        raise SemanticRecoveryPlanError("source_view candidate evidence is invalid")
    for candidate in candidates:
        if not isinstance(candidate, Mapping) or set(candidate) != _CANDIDATE_FIELDS:
            raise SemanticRecoveryPlanError("source_view candidate fields mismatch")
        if candidate.get("relation_role") not in _RELATION_ROLES:
            raise SemanticRecoveryPlanError("source_view relation role is invalid")
        if not isinstance(candidate.get("has_display_title"), bool):
            raise SemanticRecoveryPlanError("source_view display presence is invalid")
        for field in ("source_tier", "page_type", "content_status", "stable_identity_status"):
            if not isinstance(candidate.get(field), str):
                raise SemanticRecoveryPlanError(f"source_view candidate {field} is invalid")
        if candidate["stable_identity_status"] not in {
            "VERIFIED_OFFICIAL_DETAIL",
            "MALFORMED_OR_LISTING_OFFICIAL_DETAIL",
            "UNVERIFIED_RAW_EVIDENCE",
        }:
            raise SemanticRecoveryPlanError("source_view stable identity status is invalid")
        for field in (
            "display_key_sha256",
            "canonical_work_id",
            "canonical_url",
            "verified_display_title",
        ):
            if candidate.get(field) is not None and not isinstance(candidate.get(field), str):
                raise SemanticRecoveryPlanError(f"source_view candidate {field} is invalid")
        if candidate.get("display_key_sha256") is not None:
            _hex64(candidate["display_key_sha256"], field="candidate display key")
        verified = candidate["stable_identity_status"] == "VERIFIED_OFFICIAL_DETAIL"
        if verified:
            if (
                candidate["source_tier"] != "official_detail"
                or candidate["page_type"] not in _NOVEL_PAGE_TYPES
                or candidate["content_status"] not in _ACTIVE_CONTENT_STATUSES
                or not all(
                    isinstance(candidate.get(field), str) and candidate[field]
                    for field in (
                        "display_key_sha256",
                        "canonical_work_id",
                        "canonical_url",
                        "verified_display_title",
                    )
                )
            ):
                raise SemanticRecoveryPlanError("verified source_view binding is incomplete")
            parsed = _canonical_detail_identity(candidate["canonical_url"])
            if parsed is None or parsed[0] != candidate["canonical_work_id"]:
                raise SemanticRecoveryPlanError("verified source_view binding identity mismatch")
            display_key = _normalized_display(candidate["verified_display_title"])
            if not display_key or _canonical_sha256(display_key) != candidate["display_key_sha256"]:
                raise SemanticRecoveryPlanError("verified source_view display binding mismatch")
        elif any(
            candidate.get(field) is not None
            for field in ("canonical_work_id", "canonical_url", "verified_display_title")
        ):
            raise SemanticRecoveryPlanError("unverified source_view cannot carry canonical binding")
    if candidates != sorted(
        candidates,
        key=lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
    ):
        raise SemanticRecoveryPlanError("source_view candidates must be sorted")
    for field in ("raw_ocr_evidence_count",):
        count = source.get(field)
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise SemanticRecoveryPlanError(f"source_view {field} is invalid")
    if not isinstance(source.get("search_health"), str) or not source["search_health"]:
        raise SemanticRecoveryPlanError("source_view search health is invalid")
    return source, []


def _validate_plan(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != _PLAN_FIELDS:
        raise SemanticRecoveryPlanError("plan fields mismatch")
    plan = dict(value)
    if plan.get("state") not in _PLAN_STATES:
        raise SemanticRecoveryPlanError("plan state is invalid")
    _validate_sorted_strings(plan.get("blocker_codes"), field="blocker_codes")
    counts = plan.get("relationship_counts")
    if not isinstance(counts, Mapping) or set(counts) != _RELATION_ROLES:
        raise SemanticRecoveryPlanError("relationship counts are invalid")
    for count in counts.values():
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise SemanticRecoveryPlanError("relationship count is invalid")
    primary_count = plan.get("primary_identity_count")
    if isinstance(primary_count, bool) or not isinstance(primary_count, int) or primary_count < 0:
        raise SemanticRecoveryPlanError("primary identity count is invalid")
    if plan.get("media_action") not in {
        "UNKNOWN",
        "QUARANTINE_NON_NOVEL",
        "HOLD_CROSS_MEDIA",
        "NO_MEDIA_ACTION",
    }:
        raise SemanticRecoveryPlanError("media action is invalid")
    bindings = plan.get("canonical_bindings")
    if not isinstance(bindings, list):
        raise SemanticRecoveryPlanError("canonical bindings are invalid")
    for binding in bindings:
        if not isinstance(binding, Mapping) or set(binding) != _BINDING_FIELDS:
            raise SemanticRecoveryPlanError("canonical binding fields mismatch")
        if binding.get("relation_role") not in _RELATION_ROLES or not all(
            isinstance(binding.get(field), str) and binding[field]
            for field in ("canonical_work_id", "canonical_url", "display_title")
        ):
            raise SemanticRecoveryPlanError("canonical binding is invalid")
        parsed = _canonical_detail_identity(binding["canonical_url"])
        if parsed is None or parsed[0] != binding["canonical_work_id"]:
            raise SemanticRecoveryPlanError("canonical binding identity mismatch")
    if bindings != sorted(
        bindings,
        key=lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
    ):
        raise SemanticRecoveryPlanError("canonical bindings must be sorted")
    ocr_count = plan.get("raw_ocr_evidence_count")
    if isinstance(ocr_count, bool) or not isinstance(ocr_count, int) or ocr_count < 0:
        raise SemanticRecoveryPlanError("raw OCR count is invalid")
    query = plan.get("query_plan")
    if not isinstance(query, Mapping) or set(query) != _QUERY_PLAN_FIELDS:
        raise SemanticRecoveryPlanError("query plan fields mismatch")
    _validate_sorted_strings(query.get("purposes"), field="query purposes")
    if not isinstance(query.get("query_execution_allowed"), bool):
        raise SemanticRecoveryPlanError("query execution flag is invalid")
    maximum = query.get("max_queries")
    if isinstance(maximum, bool) or not isinstance(maximum, int) or not 0 <= maximum <= 2:
        raise SemanticRecoveryPlanError("max_queries is invalid")
    if not isinstance(query.get("search_health"), str) or not query["search_health"]:
        raise SemanticRecoveryPlanError("query search health is invalid")
    if not query["query_execution_allowed"] and maximum != 0:
        raise SemanticRecoveryPlanError("disabled query execution requires max_queries=0")
    for field in ("search_calls_executed", "network_calls_executed"):
        if plan.get(field) != 0:
            raise SemanticRecoveryPlanError(f"{field} must remain zero")
    return plan


def build_semantic_recovery_plan_receipt(
    result: Mapping[str, Any], publication_receipt: Any, *, attempt_run_id: str
) -> dict[str, Any]:
    authoritative = _publication_commit(publication_receipt)
    binding = _publication_binding(authoritative)
    requested_attempt = _text(attempt_run_id, field="attempt_run_id")
    if requested_attempt != binding["attempt_run_id"]:
        raise SemanticRecoveryPlanError("attempt_run_id does not match publication receipt")
    if not isinstance(result, Mapping):
        raise SemanticRecoveryPlanError("result must be an object")
    if str(_post_id(result.get("post_id"), field="result post_id")) != str(binding["post_id"]):
        raise SemanticRecoveryPlanError("result post_id does not match publication receipt")
    validate_publication_result_commit(
        result,
        authoritative,
        expected_scope_id=binding["publication_scope_id"],
        expected_input_index=binding["input_index"],
        expected_post_id=binding["post_id"],
    )
    source, errors = _source_view(result)
    plan = _plan(source, errors)
    material = {
        "schema_version": SEMANTIC_RECOVERY_PLAN_SCHEMA,
        "publication_scope_id": binding["publication_scope_id"],
        "input_index": binding["input_index"],
        "post_id": binding["post_id"],
        "attempt_run_id": requested_attempt,
        "authority": SEMANTIC_RECOVERY_PLAN_AUTHORITY,
        "mode": SEMANTIC_RECOVERY_PLAN_MODE,
        "public_apply": False,
        "rule_version": SEMANTIC_RECOVERY_PLAN_RULE_VERSION,
        "source_view": source,
        "source_view_sha256": _canonical_sha256(source),
        "plan": plan,
        "plan_sha256": _canonical_sha256(plan),
        "publication_decision_id": binding["publication_decision_id"],
        "public_projection_sha256": binding["public_projection_sha256"],
        "stable_result_sha256": binding["stable_result_sha256"],
    }
    return {**material, "receipt_sha256": _canonical_sha256(material)}


def validate_semantic_recovery_plan_receipt(
    value: Any,
    *,
    result: Mapping[str, Any] | None = None,
    expected_publication_receipt: Any = None,
    expected_scope_id: Any = None,
    expected_input_index: Any = None,
    expected_post_id: Any = None,
    expected_attempt_run_id: str | None = None,
) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != _TOP_LEVEL_FIELDS:
        raise SemanticRecoveryPlanError("receipt fields mismatch")
    if value.get("schema_version") != SEMANTIC_RECOVERY_PLAN_SCHEMA:
        raise SemanticRecoveryPlanError("receipt schema mismatch")
    if value.get("authority") != SEMANTIC_RECOVERY_PLAN_AUTHORITY:
        raise SemanticRecoveryPlanError("receipt authority mismatch")
    if value.get("mode") != SEMANTIC_RECOVERY_PLAN_MODE or value.get("public_apply") is not False:
        raise SemanticRecoveryPlanError("receipt must remain PLAN_ONLY/public_apply=false")
    if value.get("rule_version") != SEMANTIC_RECOVERY_PLAN_RULE_VERSION:
        raise SemanticRecoveryPlanError("receipt rule version mismatch")
    normalized = dict(value)
    normalized["publication_scope_id"] = _hex64(value.get("publication_scope_id"), field="publication_scope_id")
    normalized["input_index"] = _positive_index(value.get("input_index"))
    normalized["post_id"] = _post_id(value.get("post_id"))
    normalized["attempt_run_id"] = _text(value.get("attempt_run_id"), field="attempt_run_id")
    for field in (
        "source_view_sha256",
        "plan_sha256",
        "publication_decision_id",
        "public_projection_sha256",
        "stable_result_sha256",
        "receipt_sha256",
    ):
        normalized[field] = _hex64(value.get(field), field=field)
    source, errors = _validate_source_view(value.get("source_view"))
    plan = _validate_plan(value.get("plan"))
    normalized["source_view"] = source
    normalized["plan"] = plan
    if normalized["source_view_sha256"] != _canonical_sha256(source):
        raise SemanticRecoveryPlanError("source_view hash mismatch")
    if normalized["plan_sha256"] != _canonical_sha256(plan):
        raise SemanticRecoveryPlanError("plan hash mismatch")
    if plan != _plan(source, errors):
        raise SemanticRecoveryPlanError("plan does not deterministically match source_view")
    material = {field: normalized[field] for field in _TOP_LEVEL_FIELDS if field != "receipt_sha256"}
    if normalized["receipt_sha256"] != _canonical_sha256(material):
        raise SemanticRecoveryPlanError("receipt hash mismatch")
    if result is not None:
        if str(_post_id(result.get("post_id"), field="result post_id")) != str(normalized["post_id"]):
            raise SemanticRecoveryPlanError("result post_id mismatch")
        recomputed_source, recomputed_errors = _source_view(result)
        if source != recomputed_source or plan != _plan(recomputed_source, recomputed_errors):
            raise SemanticRecoveryPlanError("receipt source/plan does not match result")
    if expected_publication_receipt is not None:
        authoritative = _publication_commit(expected_publication_receipt)
        binding = _publication_binding(authoritative)
        for field, expected in binding.items():
            if normalized[field] != expected:
                raise SemanticRecoveryPlanError(f"publication receipt {field} mismatch")
        if result is not None:
            validate_publication_result_commit(
                result,
                authoritative,
                expected_scope_id=binding["publication_scope_id"],
                expected_input_index=binding["input_index"],
                expected_post_id=binding["post_id"],
            )
    if expected_scope_id is not None and normalized["publication_scope_id"] != _hex64(
        expected_scope_id, field="expected_scope_id"
    ):
        raise SemanticRecoveryPlanError("publication_scope_id mismatch")
    if expected_input_index is not None and normalized["input_index"] != _positive_index(
        expected_input_index, field="expected_input_index"
    ):
        raise SemanticRecoveryPlanError("input_index mismatch")
    if expected_post_id is not None and str(normalized["post_id"]) != str(
        _post_id(expected_post_id, field="expected_post_id")
    ):
        raise SemanticRecoveryPlanError("post_id mismatch")
    if expected_attempt_run_id is not None and normalized["attempt_run_id"] != _text(
        expected_attempt_run_id, field="expected_attempt_run_id"
    ):
        raise SemanticRecoveryPlanError("attempt_run_id mismatch")
    return normalized
