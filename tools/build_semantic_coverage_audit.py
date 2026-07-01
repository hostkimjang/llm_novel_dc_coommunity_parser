from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


ROW_CONTAINER_KEYS = ("rows", "results", "items", "data", "records", "outputs", "completed")
ROW_WRAPPER_KEYS = ("result", "row", "item", "payload")
ROW_MARKER_KEYS = (
    "post_id",
    "analysis_result",
    "identity",
    "comment_metadata",
    "comment_dialogue_context_lines",
    "image_urls",
    "content_blocks",
    "comments",
    "title",
)
IMAGE_URL_RE = re.compile(r"\.(?:png|jpe?g|gif|webp|bmp)(?:[?#].*)?$", re.IGNORECASE)
DIRECT_IMAGE_TEXT_RE = re.compile(
    r"(?:이미지\s*OCR|OCR\s*표기|이미지\s*표기|cover_title|direct_image_title|"
    r"\[이미지\s*첨부\]|image_evidence_catalog|context_sources\s*[:=][^\n\r]*image)",
    re.IGNORECASE,
)
IMAGE_OCR_REASON_RE = re.compile(
    r"(?:\[?\s*이미지\s*OCR\s*\]?|OCR\s*표기|이미지\s*표기|cover_title|"
    r"direct_image_title|explicit_work_title|ocr_text)",
    re.IGNORECASE,
)
SEMANTIC_SEED_TEXT_MARKERS = (
    "semantic_seed_review",
    "surface_paraphrase",
    "context_only_no_work_anchor",
    "작품 seed 제외",
    "표면 표현 해석",
)
FINAL_SEMANTIC_REREAD_POSITIVE_MARKERS = (
    "final_semantic_reread_reviewed",
    "final_semantic_reread_accepted_resolution",
    "final_semantic_reread_rejected_resolution",
    "final_semantic_reread_reprocess_resolution",
    "final_semantic_reread_verified_alias_guarded_resolution",
)
COMMENT_CONTEXT_MARKERS = (
    "댓글 힌트",
    "댓글 맥락",
    "comment_context",
    "comment_dialogue_context",
    "comment_dialogue_context_lines",
    "context_sources: comments",
    "context_sources=comments",
)
COMMENT_AUTHOR_UNVERIFIED_MARKERS = (
    "author_match_unverified",
    "post_author_match_unverified",
    "comment_author_match_unverified",
)
SEARCH_ONLY_MARKERS = (
    "search_only",
    "official_search_only_without_post_anchor",
    "search_only_title_promotion",
    "grounding_anchor=search_only",
    "grounding_anchor: search_only",
    "anchor_found=search_only",
    "anchor_found: search_only",
)
BLOCKED_RESOLUTION_INTENTS = (
    "community_banter",
    "trope_discussion",
    "author_talk",
    "recommendation",
)
INTENT_DENIED_TITLE_MARKERS = (
    "intent_permit_for_title_search=false",
    "semantic_seed_review_specific_work_denied",
    "semantic_seed_review(no_work_anchor)",
    "context_only_no_work_anchor",
    "friend_social_lament",
    "social_lament",
    "no_work_anchor",
)
CONTEXT_ONLY_STATES = (
    "context_only",
    "nonwork",
    "no_work",
    "unresolvable_memory_query",
)
SPECIFIC_WORK_MARKERS = (
    "specific_work",
    "discussion_target=specific_work",
    "discussion_target: specific_work",
)
SPECIFIC_WORK_PROMOTION_MARKERS = (
    "promotion_decision=hold",
    "promotion_decision: hold",
    "promotion_decision=allow",
    "promotion_decision: allow",
)
DIRECT_ANCHOR_KEYS = (
    "direct_title_anchor",
    "direct_alias_anchor",
    "body_alias_anchor",
    "post_title_anchor",
    "raw_title_span",
    "post_spans",
    "direct_post_anchor",
    "post_anchor",
    "title_span",
)
DIRECT_ANCHOR_MARKERS = (
    "direct_title_anchor",
    "direct_alias_anchor",
    "body_alias_anchor",
    "post_title_anchor",
    "raw_title_span",
    "direct_post_anchor",
    "post_anchor",
)
TITLE_ALIAS_SUPPORT_MARKERS = (
    "title_exact",
    "title_alias",
    "title_reaction_link",
    "title_in_post: true",
    "title_in_post=true",
    "title_lead_alias_search_work_support",
)
OFFICIAL_OR_PLATFORM_SUPPORT_MARKERS = (
    "official_title_evidence: true",
    "official_title_evidence=true",
    "heretic_url_platform",
    "search_platform_url",
    "source_tier: official_detail",
    "source_tier=official_detail",
    "source_tier: novel_platform",
    "source_tier=novel_platform",
    "novel_platform",
    "작품 상세 URL(플랫폼)",
)
PLATFORM_DOMAINS = (
    "novelpia.com",
    "munpia.com",
    "series.naver.com",
    "page.kakao.com",
    "joara.com",
)
BROWSER_OR_DIRECT_VISUAL_KEYS = (
    "browser_visual_evidence",
    "browser_visual_review",
    "browser_visual_checks",
    "browser_visual_artifacts",
    "browser_screenshot",
    "browser_screenshot_path",
    "browser_visual_manifest",
    "direct_visual_evidence",
    "visual_evidence",
    "browser_visual_available",
    "browser_visual_verified",
    "browser_visual_reviewed",
)
BROWSER_EXPLICIT_VERIFIED_KEYS = (
    "browser_visual_available",
    "browser_visual_verified",
    "browser_visual_reviewed",
)
BROWSER_DIRECT_EVIDENCE_KEYS = (
    "browser_visual_evidence",
    "browser_visual_review",
    "browser_visual_checks",
    "browser_visual_artifacts",
    "direct_visual_evidence",
    "visual_evidence",
)
BROWSER_ARTIFACT_PATH_KEYS = (
    "browser_screenshot",
    "browser_screenshot_path",
    "browser_visual_manifest",
)
VLM_FETCH_CHUNK_KEYS = (
    "vlm_enrichment_used",
    "vlm_used",
    "image_enrichment_used",
    "vlm_fetch_count",
    "vlm_fetch_success_count",
    "vlm_chunk_count",
    "vlm_chunks",
    "image_fetch_count",
    "image_fetch_success",
    "image_fetch_success_count",
    "image_enrichment_fetch_count",
    "image_enrichment_chunk_count",
    "vlm_chunks_sent",
    "vlm_total_bytes",
)
IMAGE_CATALOG_SOURCE_KEYS = (
    "source",
    "source_type",
    "provider",
    "mode",
    "extractor",
)
IMAGE_CATALOG_TEXT_KEYS = (
    "text",
    "snippet",
    "ocr_text",
    "detected_text",
    "visual_summary",
    "explicit_work_title",
    "explicit_author_name",
    "work_cues",
    "title",
    "summary",
)
IMAGE_CATALOG_TRACE_KEYS = (
    "source_url",
    "url",
    "image_url",
    "image_index",
    "image_idx",
    "content_block_index",
    "status",
    "state",
    "grade",
    "visual_evidence_grade",
    "evidence_grade",
    "confidence",
    "title_role",
    "promotion_eligible",
)
NEGATIVE_STATUS_STRINGS = {
    "blocked",
    "disabled",
    "error",
    "failed",
    "failure",
    "fetch_failed",
    "missing",
    "none",
    "not_available",
    "null",
    "pending",
    "skip",
    "skipped",
    "timeout",
    "timed_out",
    "unavailable",
    "unsupported",
}
POSITIVE_STATUS_STRINGS = {
    "available",
    "complete",
    "completed",
    "enabled",
    "ok",
    "present",
    "ready",
    "success",
    "succeeded",
    "used",
    "verified",
}
BROWSER_LOADING_TOTAL_KEYS = ("article_image_count", "browser_article_image_count", "image_load_total")
BROWSER_LOADING_LOADED_KEYS = ("article_loaded_count", "browser_loaded_image_count", "image_loaded_count")
BROWSER_LOADING_PENDING_KEYS = (
    "article_lazy_pending_count",
    "data_original_pending_count",
    "placeholder_current_src_count",
    "image_loading_pending_count",
    "article_incomplete_count",
    "article_broken_count",
    "placeholder_count",
    "image_placeholder_count",
    "browser_placeholder_count",
    "incomplete_count",
    "image_incomplete_count",
    "browser_incomplete_count",
    "broken_count",
    "image_broken_count",
    "browser_broken_count",
)
BROWSER_LOADING_PENDING_BOOL_KEYS = (
    "image_loading_pending",
    "article_image_loading_pending",
    "browser_image_loading_pending",
)
REVIEW_LABEL_CLOSABLE_ISSUES = {
    "comment_author_match_unverified_resolution_review_only",
    "search_only_resolved_title_review_only",
    "blocked_intent_resolved_title_review_only",
    "adjacent_reason_non_relevant_wording_conflict",
    "final_semantic_reread_coverage_missing",
    "comment_metadata_missing",
    "comment_dialogue_context_missing",
}
REVIEW_LABEL_ACCEPT_VALUES = {"ACCEPT"}
REVIEW_LABEL_NO_ACTION_VALUES = {"no_action", "docs_issue"}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as f:
        for line in f:
            if not line.strip():
                continue
            value = json.loads(line)
            if isinstance(value, dict):
                rows.append(value)
    return rows


def load_review_labels(path: Path) -> list[dict[str, Any]]:
    return load_jsonl(path)


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _looks_like_row(value: Any) -> bool:
    return isinstance(value, dict) and any(key in value for key in ROW_MARKER_KEYS)


def _coerce_row(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    for key in ROW_WRAPPER_KEYS:
        nested = value.get(key)
        if _looks_like_row(nested):
            return nested
    return value if _looks_like_row(value) else None


def _extract_rows(data: Any, source: str = "$") -> tuple[list[dict[str, Any]], str]:
    if isinstance(data, list):
        rows = [row for item in data if (row := _coerce_row(item)) is not None]
        return rows, source

    if isinstance(data, dict):
        for key in ROW_CONTAINER_KEYS:
            if key not in data:
                continue
            rows, nested_source = _extract_rows(data.get(key), f"{source}.{key}")
            if rows or isinstance(data.get(key), list):
                return rows, nested_source
        row = _coerce_row(data)
        if row is not None:
            return [row], source

    return [], source


def result_rows(data: Any) -> tuple[list[dict[str, Any]], str]:
    return _extract_rows(data)


def _to_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value in (None, ""):
        return None
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return None


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    if isinstance(value, str):
        return bool(value.strip())
    return True


def _analysis(row: dict[str, Any]) -> dict[str, Any]:
    return _as_dict(row.get("analysis_result"))


def _identity(row: dict[str, Any]) -> dict[str, Any]:
    analysis = _analysis(row)
    identity = _as_dict(analysis.get("identity"))
    if identity:
        return identity
    return _as_dict(row.get("identity"))


def _scopes(row: dict[str, Any]) -> list[dict[str, Any]]:
    analysis = _analysis(row)
    identity = _identity(row)
    analysis_section = _as_dict(analysis.get("analysis"))
    scopes = [row, identity, analysis, analysis_section]
    return [scope for idx, scope in enumerate(scopes) if scope and scope not in scopes[:idx]]


def _first_present(scopes: Iterable[dict[str, Any]], keys: Iterable[str]) -> Any:
    for scope in scopes:
        for key in keys:
            if key in scope:
                return scope.get(key)
    return None


def _field_has_value(scopes: Iterable[dict[str, Any]], keys: Iterable[str]) -> bool:
    for scope in scopes:
        for key in keys:
            if key in scope and _has_value(scope.get(key)):
                return True
    return False


def _flatten_text(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, dict):
        out: list[str] = []
        for item in value.values():
            out.extend(_flatten_text(item))
        return out
    if isinstance(value, (list, tuple, set)):
        out = []
        for item in value:
            out.extend(_flatten_text(item))
        return out
    text = str(value).strip()
    return [text] if text else []


def _combined_public_text(row: dict[str, Any], identity: dict[str, Any], analysis: dict[str, Any]) -> str:
    fragments: list[str] = []
    for source, keys in (
        (row, ("title", "content", "comments", "comment_context_lines", "comment_dialogue_context_lines")),
        (identity, ("reason", "reason_lines", "context_sources", "consistency_flags")),
        (_as_dict(analysis.get("analysis")), ("notes",)),
    ):
        for key in keys:
            fragments.extend(_flatten_text(source.get(key)))
    return "\n".join(fragments)


def _row_id(row: dict[str, Any]) -> str:
    for key in ("post_id", "id", "global_idx", "index"):
        value = row.get(key)
        if value not in (None, ""):
            return str(value)
    return "<unknown>"


def _comments_count(row: dict[str, Any]) -> int:
    explicit = _to_int(row.get("comment_count") or row.get("comments_count"))
    comments = row.get("comments")
    if isinstance(comments, list):
        return max(explicit or 0, len(comments))
    if isinstance(comments, dict):
        return max(explicit or 0, len(comments))
    if isinstance(comments, str) and comments.strip():
        return max(explicit or 0, 1)
    return explicit or 0


def _list_values(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if value in (None, ""):
        return []
    return [value]


def _image_urls_from_row(row: dict[str, Any]) -> list[str]:
    seen: set[str] = set()
    urls: list[str] = []

    def push(raw: Any) -> None:
        url = str(raw or "").strip()
        if url and url not in seen:
            seen.add(url)
            urls.append(url)

    for raw in _list_values(row.get("image_urls")):
        push(raw)
    for block in _list_values(row.get("content_blocks")):
        if not isinstance(block, dict):
            continue
        url = str(block.get("url") or block.get("src") or "").strip()
        block_type = str(block.get("type") or "").strip().lower()
        if block_type in {"image", "img", "photo", "picture"} or IMAGE_URL_RE.search(url):
            push(url)
    return urls


def _image_count_from_row(row: dict[str, Any]) -> int:
    for key in ("image_count", "article_image_count", "content_image_count", "attachment_image_count"):
        explicit = _to_int(row.get(key))
        if explicit is not None and explicit >= 0:
            return explicit
    return len(_image_urls_from_row(row))


def _image_evidence_catalog(scopes: Iterable[dict[str, Any]]) -> list[Any]:
    value = _first_present(scopes, ("image_evidence_catalog", "image_catalog", "visual_evidence_catalog"))
    if isinstance(value, list):
        return [item for item in value if _has_value(item)]
    if isinstance(value, dict) and value:
        return [value]
    return []


def _image_catalog_item_reviewable(item: Any) -> bool:
    if not isinstance(item, dict):
        return False
    has_content = any(_has_value(item.get(key)) for key in IMAGE_CATALOG_TEXT_KEYS)
    has_trace = any(
        _has_value(item.get(key))
        for key in (*IMAGE_CATALOG_SOURCE_KEYS, *IMAGE_CATALOG_TRACE_KEYS)
    )
    return has_content and has_trace


def _image_catalog_unreviewable(catalog: Iterable[Any]) -> bool:
    items = list(catalog)
    return bool(items) and not all(_image_catalog_item_reviewable(item) for item in items)


def _image_catalog_mentions_vlm_or_ocr(catalog: Iterable[Any]) -> bool:
    text = "\n".join(_flatten_text(list(catalog))).lower()
    return any(marker in text for marker in ("vlm", "ocr", "이미지 ocr", "image_enrichment"))


def _semantic_seed_review_present(scopes: Iterable[dict[str, Any]], text: str) -> bool:
    if _field_has_value(
        scopes,
        (
            "semantic_seed_review",
            "semantic_seed_review_context_terms",
            "semantic_seed_review_present",
        ),
    ):
        return True
    lower = text.lower()
    return any(marker.lower() in lower for marker in SEMANTIC_SEED_TEXT_MARKERS)


def _final_semantic_reread_present(scopes: Iterable[dict[str, Any]], text: str) -> bool:
    if _field_has_value(
        scopes,
        ("_final_semantic_reread", "final_semantic_reread", "final_semantic_reread_record"),
    ):
        return True
    flags = _flatten_text(_first_present(scopes, ("consistency_flags", "flags", "warnings")))
    if any(
        flag.startswith("final_semantic_reread_") and "missing" not in flag
        for flag in flags
    ):
        return True
    lower = text.lower()
    return any(marker in lower for marker in FINAL_SEMANTIC_REREAD_POSITIVE_MARKERS)


def _resolved_title_present(row: dict[str, Any], scopes: Iterable[dict[str, Any]]) -> bool:
    if _field_has_value(
        scopes,
        (
            "official_title",
            "official_novel_title",
            "resolved_title",
            "canonical_title",
            "work_title",
        ),
    ):
        return True
    identity = _identity(row)
    novel_identity = identity.get("novel_identity")
    if isinstance(novel_identity, dict) and _has_value(novel_identity.get("official_title")):
        return True
    analysis = _analysis(row)
    novel_identity = analysis.get("novel_identity")
    return isinstance(novel_identity, dict) and _has_value(novel_identity.get("official_title"))


def _resolved_relevant_row(row: dict[str, Any], scopes: Iterable[dict[str, Any]]) -> bool:
    relevant = _to_bool(_first_present(scopes, ("is_relevant", "is_novel_related")))
    if relevant is False:
        return False
    resolved_state = str(
        _first_present(scopes, ("title_resolution_state", "work_resolution", "resolution_state")) or ""
    ).strip().lower()
    if resolved_state and resolved_state not in {"resolved", "resolved_work", "title_resolved"}:
        return False
    return bool(relevant is True and _resolved_title_present(row, scopes))


def _resolved_title_row(row: dict[str, Any], scopes: Iterable[dict[str, Any]]) -> bool:
    if not _resolved_title_present(row, scopes):
        return False
    resolved_state = str(
        _first_present(scopes, ("title_resolution_state", "work_resolution", "resolution_state")) or ""
    ).strip().lower()
    if not resolved_state:
        return True
    return resolved_state in {"resolved", "resolved_work", "title_resolved"}


def _adjacent_reason_non_relevant_wording_conflict(scopes: Iterable[dict[str, Any]], text: str) -> bool:
    if "최종 판정은 비관련 포스트" not in (text or ""):
        return False
    topicality = str(_first_present(scopes, ("topicality", "topic_state")) or "").strip().lower()
    title_state = str(
        _first_present(scopes, ("title_resolution_state", "work_resolution", "resolution_state")) or ""
    ).strip().lower()
    discussion_type = str(_first_present(scopes, ("discussion_type", "post_type")) or "").strip().lower()
    return bool(
        topicality == "adjacent_relevant"
        or title_state == "adjacent"
        or "주변 관련" in text
        or (
            discussion_type in {"trope_discussion", "recommendation", "author_talk", "meta", "community_banter"}
            and "특정 작품보다" in text
        )
    )


def _context_sources_include_image(identity: dict[str, Any]) -> bool:
    sources = _list_values(identity.get("context_sources"))
    return any(str(source).strip().lower() == "image" for source in sources)


def _context_sources_include_comments(identity: dict[str, Any]) -> bool:
    sources = _list_values(identity.get("context_sources"))
    return any(str(source).strip().lower() in {"comment", "comments"} for source in sources)


def _image_anchor_claimed(identity: dict[str, Any]) -> bool:
    for key in ("anchor_type", "grounding_anchor"):
        value = str(identity.get(key) or "").strip().lower()
        if value == "image":
            return True
    return False


def _comment_context_claimed(
    row_scopes: Iterable[dict[str, Any]],
    identity: dict[str, Any],
    public_text: str,
) -> bool:
    if _context_sources_include_comments(identity):
        return True
    if _field_has_value(
        row_scopes,
        (
            "comment_context",
            "comment_context_lines",
            "comment_dialogue_context",
            "comment_dialogue_context_lines",
            "comment_evidence",
            "comment_evidence_catalog",
        ),
    ):
        return True
    lower = public_text.lower()
    return any(marker.lower() in lower for marker in COMMENT_CONTEXT_MARKERS)


def _comment_author_unverified_signal(row_scopes: Iterable[dict[str, Any]], public_text: str) -> bool:
    fragments: list[str] = [public_text]
    for scope in row_scopes:
        for key in (
            "comment_metadata",
            "comment_context",
            "comment_context_lines",
            "comment_dialogue_context",
            "comment_dialogue_context_lines",
            "consistency_flags",
            "risk_tags",
            "warnings",
        ):
            fragments.extend(_flatten_text(scope.get(key)))
    lower = "\n".join(fragments).lower()
    return any(marker.lower() in lower for marker in COMMENT_AUTHOR_UNVERIFIED_MARKERS)


def _semantic_signal_text(row_scopes: Iterable[dict[str, Any]], public_text: str) -> str:
    fragments: list[str] = [public_text]
    for scope in row_scopes:
        for key in (
            "anchor_type",
            "grounding_anchor",
            "anchor_found",
            "discussion_type",
            "intent",
            "post_intent",
            "content_intent",
            "semantic_intent",
            "relation_judgment",
            "promotion_decision",
            "direct_title_anchor",
            "direct_alias_anchor",
            "body_alias_anchor",
            "post_title_anchor",
            "raw_title_span",
            "post_spans",
            "direct_post_anchor",
            "post_anchor",
            "title_span",
            "consistency_flags",
            "risk_tags",
            "warnings",
            "uncertainty_sources",
            "_title_null_block_reasons",
            "semantic_seed_review",
        ):
            fragments.extend(_flatten_text(scope.get(key)))
    return "\n".join(fragments).lower()


def _search_only_signal(row_scopes: Iterable[dict[str, Any]], public_text: str) -> bool:
    text = _semantic_signal_text(row_scopes, public_text)
    return any(marker.lower() in text for marker in SEARCH_ONLY_MARKERS)


def _blocked_resolution_intent(row_scopes: Iterable[dict[str, Any]], public_text: str) -> bool:
    text = _semantic_signal_text(row_scopes, public_text)
    return any(marker.lower() in text for marker in BLOCKED_RESOLUTION_INTENTS)


def _intent_denied_title_signal(row_scopes: Iterable[dict[str, Any]], public_text: str) -> bool:
    text = _semantic_signal_text(row_scopes, public_text)
    if any(marker.lower() in text for marker in INTENT_DENIED_TITLE_MARKERS):
        return True
    allowed = _first_present(row_scopes, ("title_resolution_allowed",))
    if _to_bool(allowed) is False:
        return True
    for scope in row_scopes:
        for key in ("title_resolution_state", "work_resolution", "resolution_state"):
            state = str(scope.get(key) or "").strip().lower()
            if state in CONTEXT_ONLY_STATES:
                return True
    return False


def _specific_work_hold_with_direct_anchor(
    row_scopes: Iterable[dict[str, Any]],
    public_text: str,
) -> bool:
    text = _semantic_signal_text(row_scopes, public_text)
    specific_work = any(marker.lower() in text for marker in SPECIFIC_WORK_MARKERS)
    promotion_ok = any(marker.lower() in text for marker in SPECIFIC_WORK_PROMOTION_MARKERS)
    for scope in row_scopes:
        promotion = str(scope.get("promotion_decision") or "").strip().lower()
        if promotion in {"hold", "allow", "accept"}:
            promotion_ok = True
        relation = scope.get("relation_judgment")
        if isinstance(relation, dict):
            promotion = str(relation.get("promotion_decision") or "").strip().lower()
            if promotion in {"hold", "allow", "accept"}:
                promotion_ok = True
    direct_anchor = _field_has_value(row_scopes, DIRECT_ANCHOR_KEYS) or any(
        marker.lower() in text for marker in DIRECT_ANCHOR_MARKERS
    )
    return bool(specific_work and promotion_ok and direct_anchor)


def _catalog_has_platform_evidence(row_scopes: Iterable[dict[str, Any]]) -> bool:
    for scope in row_scopes:
        for key in ("search_evidence_catalog", "evidence", "title_candidates", "primary_work"):
            for item in _list_values(scope.get(key)):
                if not isinstance(item, dict):
                    continue
                source_tier = str(item.get("source_tier") or "").strip().lower()
                if source_tier in {"official_detail", "novel_platform"}:
                    return True
                url = str(item.get("url") or item.get("heretic_url") or "").strip().lower()
                if any(domain in url for domain in PLATFORM_DOMAINS):
                    return True
    return False


def _title_or_alias_resolution_support(
    row_scopes: Iterable[dict[str, Any]],
    public_text: str,
    *,
    require_platform: bool,
) -> bool:
    text = f"{_semantic_signal_text(row_scopes, public_text)}\n{public_text}".lower()
    title_or_alias_anchor = (
        _field_has_value(row_scopes, DIRECT_ANCHOR_KEYS)
        or any(marker.lower() in text for marker in TITLE_ALIAS_SUPPORT_MARKERS)
    )
    if not title_or_alias_anchor:
        return False
    platform_support = (
        any(marker.lower() in text for marker in OFFICIAL_OR_PLATFORM_SUPPORT_MARKERS)
        or _catalog_has_platform_evidence(row_scopes)
    )
    return bool(platform_support if require_platform else (platform_support or "title_lead_alias_search_work_support" in text))


def _positive_vlm_counter(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    bool_value = _to_bool(value)
    if bool_value is not None:
        return bool_value
    count = _to_int(value)
    if count is not None:
        return count > 0
    if isinstance(value, str):
        status = value.strip().lower()
        if not status or status in NEGATIVE_STATUS_STRINGS:
            return False
        return status in POSITIVE_STATUS_STRINGS
    if isinstance(value, dict):
        status = value.get("status") or value.get("state") or value.get("result")
        if isinstance(status, str) and status.strip().lower() in NEGATIVE_STATUS_STRINGS:
            counter_keys = ("fetch_count", "fetch_success_count", "chunks", "chunk_count", "images")
            return any(_positive_vlm_counter(value.get(key)) for key in counter_keys)
        return any(
            _positive_vlm_counter(value.get(key))
            for key in (
                "used",
                "fetch",
                "fetch_count",
                "fetch_success",
                "fetch_success_count",
                "chunks",
                "chunk_count",
                "images",
                "status",
                "state",
                "result",
            )
        )
    return False


def _vlm_fetch_or_chunk_evidence_present(scopes: Iterable[dict[str, Any]]) -> bool:
    for scope in scopes:
        for key in VLM_FETCH_CHUNK_KEYS:
            if key in scope and _positive_vlm_counter(scope.get(key)):
                return True
        vlm_meta = scope.get("vlm")
        if isinstance(vlm_meta, dict) and _positive_vlm_counter(vlm_meta):
            return True
    return False


def _browser_visual_required(scopes: Iterable[dict[str, Any]], image_related: bool) -> bool:
    explicit = _to_bool(_first_present(scopes, ("browser_visual_required", "requires_browser_visual")))
    return explicit is True or image_related


def _browser_loading_counters_ok(scopes: Iterable[dict[str, Any]]) -> bool:
    total = _to_int(_first_present(scopes, BROWSER_LOADING_TOTAL_KEYS))
    loaded = _to_int(_first_present(scopes, BROWSER_LOADING_LOADED_KEYS))
    pending_values = [_to_int(_first_present(scopes, (key,))) or 0 for key in BROWSER_LOADING_PENDING_KEYS]
    pending_flags = [
        _to_bool(_first_present(scopes, (key,))) is True
        for key in BROWSER_LOADING_PENDING_BOOL_KEYS
    ]
    return (
        total is not None
        and total > 0
        and loaded is not None
        and loaded >= total
        and all(value == 0 for value in pending_values)
        and not any(pending_flags)
    )


def _browser_loading_state_failed(scopes: Iterable[dict[str, Any]]) -> bool:
    total = _to_int(_first_present(scopes, BROWSER_LOADING_TOTAL_KEYS))
    loaded = _to_int(_first_present(scopes, BROWSER_LOADING_LOADED_KEYS))
    if total is not None and loaded is not None and loaded < total:
        return True
    for key in BROWSER_LOADING_PENDING_BOOL_KEYS:
        if _to_bool(_first_present(scopes, (key,))) is True:
            return True
    for key in BROWSER_LOADING_PENDING_KEYS:
        value = _to_int(_first_present(scopes, (key,)))
        if value is not None and value > 0:
            return True
    return False


def _explicit_browser_visual_verified(scopes: Iterable[dict[str, Any]]) -> bool:
    for scope in scopes:
        for key in BROWSER_EXPLICIT_VERIFIED_KEYS:
            if key not in scope:
                continue
            if _positive_vlm_counter(scope.get(key)):
                return True
    return False


def _direct_visual_evidence_present(scopes: Iterable[dict[str, Any]]) -> bool:
    for scope in scopes:
        for key in BROWSER_DIRECT_EVIDENCE_KEYS:
            if key not in scope:
                continue
            value = scope.get(key)
            if isinstance(value, str):
                status = value.strip().lower()
                if status in NEGATIVE_STATUS_STRINGS:
                    continue
            if _has_value(value):
                return True
    return False


def _artifact_path_exists(value: Any, *, manifest_parent: Path | None = None) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    path = Path(text)
    if path.exists():
        return True
    if manifest_parent:
        return (manifest_parent / path).exists()
    return False


def _browser_artifact_row_available(row: dict[str, Any], *, manifest_parent: Path | None = None) -> bool:
    screenshot = str(row.get("screenshot") or row.get("screenshot_path") or "").strip()
    snapshot = str(row.get("snapshot") or row.get("snapshot_path") or "").strip()
    status = str(row.get("status") or row.get("browser_status") or "").strip().lower()
    if status in NEGATIVE_STATUS_STRINGS:
        return False
    has_artifact = bool(
        _artifact_path_exists(screenshot, manifest_parent=manifest_parent)
        or _artifact_path_exists(snapshot, manifest_parent=manifest_parent)
    )
    if not has_artifact:
        return False

    if _browser_loading_state_failed([row]):
        return False
    if not _browser_loading_counters_ok([row]):
        return False
    grade = str(row.get("visual_evidence_grade") or row.get("evidence_grade") or "").strip().lower()
    if grade:
        return grade in {"strong", "medium"}

    visible_signals = row.get("visible_signals")
    if isinstance(visible_signals, list):
        normalized = {str(item).strip().lower() for item in visible_signals}
        if normalized.intersection(
            {
                "article_image_node",
                "article_image_loaded",
                "loaded_article_image",
                "direct_visual_evidence",
                "browser_visual_verified",
            }
        ):
            return True

    return _explicit_browser_visual_verified([row]) or _direct_visual_evidence_present([row])


def load_browser_artifacts(path: Path) -> dict[str, dict[str, Any]]:
    raw = load_json(path)
    rows = raw.get("rows") if isinstance(raw, dict) else raw
    if not isinstance(rows, list) and isinstance(raw, dict):
        fallback = raw.get("fallback_browser")
        if isinstance(fallback, dict) and fallback.get("used") is not False:
            rows = [fallback]
    if not isinstance(rows, list) and isinstance(raw, dict):
        output_path = str(raw.get("output_path") or "").strip()
        if output_path:
            candidate = Path(output_path)
            if not candidate.exists() and not candidate.is_absolute():
                candidate = path.parent / candidate
            if candidate.exists() and candidate.suffix.lower() == ".jsonl":
                rows = load_jsonl(candidate)
    if not isinstance(rows, list):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        post_id = row.get("post_id")
        if post_id in (None, ""):
            continue
        if not _browser_artifact_row_available(row, manifest_parent=path.parent):
            continue
        out[str(post_id)] = {
            "browser_visual_artifacts": [row],
            "browser_visual_reviewed": True,
            "browser_visual_available": True,
            "browser_visual_source": "external_artifact_manifest",
        }
    return out


def _browser_or_direct_visual_available(scopes: Iterable[dict[str, Any]]) -> bool:
    if _browser_loading_state_failed(scopes):
        return False
    return (
        _browser_loading_counters_ok(scopes)
        or _explicit_browser_visual_verified(scopes)
        or _direct_visual_evidence_present(scopes)
    )


def _issue(
    code: str,
    severity: str,
    count: int,
    sample_post_ids: Iterable[str],
    description: str,
    action: str,
) -> dict[str, Any]:
    return {
        "code": code,
        "severity": severity,
        "count": count,
        "sample_post_ids": list(sample_post_ids)[:10],
        "description": description,
        "recommended_action": action,
    }


def _gate_from_issues(issues: list[dict[str, Any]]) -> str:
    if any(item.get("severity") == "REVIEW-LOCKED" for item in issues):
        return "REVIEW-LOCKED"
    if issues:
        return "REVIEW"
    return "GO"


def _label_issue_codes(label: dict[str, Any]) -> set[str]:
    values: list[Any] = []
    for key in (
        "issue_code",
        "coverage_issue_code",
        "semantic_coverage_issue_code",
        "review_issue_code",
    ):
        values.extend(_list_values(label.get(key)))
    for key in (
        "issue_codes",
        "coverage_issue_codes",
        "semantic_coverage_issue_codes",
        "risk_tags",
    ):
        values.extend(_list_values(label.get(key)))
    return {str(value).strip() for value in values if str(value or "").strip()}


def _label_actions(label: dict[str, Any]) -> set[str]:
    values = _list_values(label.get("action") or label.get("actions"))
    return {str(value).strip() for value in values if str(value or "").strip()}


def _review_label_closes_issue(label: dict[str, Any], *, issue_code: str, post_id: str) -> bool:
    if str(label.get("post_id") or "").strip() != str(post_id):
        return False
    if issue_code not in _label_issue_codes(label):
        return False
    if str(label.get("review_label") or "").strip().upper() not in REVIEW_LABEL_ACCEPT_VALUES:
        return False
    actions = _label_actions(label)
    if actions and not actions.issubset(REVIEW_LABEL_NO_ACTION_VALUES):
        return False
    if _has_value(label.get("rationale_ko")) or _has_value(label.get("rationale")):
        return True
    return False


def _apply_review_label_closures(
    issues: list[dict[str, Any]],
    review_labels: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not review_labels:
        return issues, []

    remaining: list[dict[str, Any]] = []
    closures: list[dict[str, Any]] = []
    for issue in issues:
        issue_code = str(issue.get("code") or "")
        severity = str(issue.get("severity") or "")
        samples = [str(value) for value in issue.get("sample_post_ids") or []]
        if severity != "REVIEW" or issue_code not in REVIEW_LABEL_CLOSABLE_ISSUES:
            remaining.append(issue)
            continue

        closed_posts: list[str] = []
        for post_id in samples:
            if any(
                _review_label_closes_issue(label, issue_code=issue_code, post_id=post_id)
                for label in review_labels
            ):
                closed_posts.append(post_id)

        closed_count = len(set(closed_posts))
        issue_count = _to_int(issue.get("count")) or 0
        if closed_count <= 0:
            remaining.append(issue)
            continue

        closures.append(
            {
                "issue_code": issue_code,
                "closed_count": closed_count,
                "closed_post_ids": sorted(set(closed_posts)),
                "closure_source": "review_labels",
            }
        )
        if closed_count < issue_count:
            kept = [post_id for post_id in samples if post_id not in set(closed_posts)]
            updated = dict(issue)
            updated["count"] = issue_count - closed_count
            updated["sample_post_ids"] = kept[:10]
            remaining.append(updated)

    return remaining, closures


def _recommended_actions(issues: list[dict[str, Any]]) -> list[str]:
    actions: list[str] = []
    seen: set[str] = set()
    for issue in issues:
        action = str(issue.get("recommended_action") or "").strip()
        if action and action not in seen:
            seen.add(action)
            actions.append(action)
    final_boundary = (
        "이 도구의 `GO`는 구조/공개 evidence coverage sanity만 뜻하며, "
        "10만 건 semantic approval은 expanded random/high-risk review로 별도 판정한다."
    )
    if final_boundary not in seen:
        actions.append(final_boundary)
    return actions


def audit_rows(
    rows: list[dict[str, Any]],
    *,
    result_path: Path | None = None,
    rows_source: str = "$",
    browser_artifacts: dict[str, dict[str, Any]] | None = None,
    browser_artifact_manifest: Path | None = None,
    review_labels: list[dict[str, Any]] | None = None,
    review_labels_path: Path | None = None,
) -> dict[str, Any]:
    counters: Counter[str] = Counter()
    samples: dict[str, list[str]] = defaultdict(list)
    browser_artifacts = browser_artifacts or {}

    for row in rows:
        counters["total_rows"] += 1
        row_scopes = _scopes(row)
        identity = _identity(row)
        analysis = _analysis(row)
        public_text = _combined_public_text(row, identity, analysis)
        post_id = _row_id(row)
        external_browser_artifact = browser_artifacts.get(post_id)
        if external_browser_artifact:
            row_scopes = row_scopes + [external_browser_artifact]
            counters["browser_visual_external_artifact_available"] += 1

        comments_count = _comments_count(row)
        comment_metadata_present = False
        comment_dialogue_context_present = False
        if comments_count > 0:
            counters["comment_row_count"] += 1
            if _field_has_value(row_scopes, ("comment_metadata",)):
                comment_metadata_present = True
                counters["comment_metadata_present"] += 1
            else:
                counters["comment_metadata_missing"] += 1
                samples["comment_metadata_missing"].append(post_id)
            if _field_has_value(row_scopes, ("comment_dialogue_context_lines", "comment_dialogue_context")):
                comment_dialogue_context_present = True
                counters["comment_dialogue_context_present"] += 1
            else:
                counters["comment_dialogue_context_missing"] += 1
                samples["comment_dialogue_context_missing"].append(post_id)
        comment_context_claimed = _comment_context_claimed(row_scopes, identity, public_text)
        comment_author_unverified = _comment_author_unverified_signal(row_scopes, public_text)
        if comment_context_claimed:
            counters["comment_context_claimed_row_count"] += 1
        if comment_author_unverified:
            counters["comment_author_match_unverified_signal"] += 1
        comment_context_resolution = bool(
            comments_count > 0
            and comment_context_claimed
            and _resolved_relevant_row(row, row_scopes)
        )
        if comment_context_resolution:
            counters["comment_context_resolution_row_count"] += 1
            if not (comment_metadata_present and comment_dialogue_context_present):
                counters["comment_context_resolution_without_attribution"] += 1
                samples["comment_context_resolution_without_attribution"].append(post_id)
            if comment_author_unverified:
                if _title_or_alias_resolution_support(
                    row_scopes,
                    public_text,
                    require_platform=False,
                ):
                    counters["comment_author_match_unverified_resolution_review_only"] += 1
                    samples["comment_author_match_unverified_resolution_review_only"].append(post_id)
                else:
                    counters["comment_author_match_unverified_used_for_resolution"] += 1
                    samples["comment_author_match_unverified_used_for_resolution"].append(post_id)

        resolved_title_row = _resolved_title_row(row, row_scopes)
        specific_work_review_exception = _specific_work_hold_with_direct_anchor(row_scopes, public_text)
        if resolved_title_row and _search_only_signal(row_scopes, public_text):
            if specific_work_review_exception or _title_or_alias_resolution_support(
                row_scopes,
                public_text,
                require_platform=True,
            ):
                counters["search_only_resolved_title_review_only"] += 1
                samples["search_only_resolved_title_review_only"].append(post_id)
            else:
                counters["search_only_resolved_title"] += 1
                samples["search_only_resolved_title"].append(post_id)
        if resolved_title_row and _blocked_resolution_intent(row_scopes, public_text):
            if specific_work_review_exception:
                counters["blocked_intent_resolved_title_review_only"] += 1
                samples["blocked_intent_resolved_title_review_only"].append(post_id)
            else:
                counters["blocked_intent_resolved_title"] += 1
                samples["blocked_intent_resolved_title"].append(post_id)
        if _resolved_title_present(row, row_scopes) and _intent_denied_title_signal(row_scopes, public_text):
            counters["intent_denied_title_present"] += 1
            samples["intent_denied_title_present"].append(post_id)
        if _adjacent_reason_non_relevant_wording_conflict(row_scopes, public_text):
            counters["adjacent_reason_non_relevant_wording_conflict"] += 1
            samples["adjacent_reason_non_relevant_wording_conflict"].append(post_id)

        image_count = _image_count_from_row(row)
        image_urls = _image_urls_from_row(row)
        actual_image_row = bool(image_count > 0 or image_urls)
        if actual_image_row:
            counters["image_post_count"] += 1

        image_context_claimed = bool(_context_sources_include_image(identity) or _image_anchor_claimed(identity))
        image_ocr_reason_claimed = bool(IMAGE_OCR_REASON_RE.search(public_text))
        image_related = bool(
            actual_image_row
            or image_context_claimed
            or DIRECT_IMAGE_TEXT_RE.search(public_text)
        )
        if image_related:
            counters["image_related_row_count"] += 1
        if image_ocr_reason_claimed:
            counters["image_ocr_reason_claimed"] += 1

        image_catalog = _image_evidence_catalog(row_scopes)
        vlm_fetch_or_chunk_evidence = _vlm_fetch_or_chunk_evidence_present(row_scopes)
        if image_catalog:
            counters["image_evidence_catalog_row_count"] += 1
            if _image_catalog_unreviewable(image_catalog):
                counters["image_evidence_catalog_unreviewable"] += 1
                samples["image_evidence_catalog_unreviewable"].append(post_id)
        if image_related and image_catalog:
            counters["image_evidence_catalog_present"] += 1
        elif image_related:
            counters["image_evidence_catalog_missing"] += 1
            samples["image_evidence_catalog_missing"].append(post_id)
        if (
            image_catalog
            and not vlm_fetch_or_chunk_evidence
            and (
                actual_image_row
                or image_context_claimed
                or image_ocr_reason_claimed
                or _image_catalog_mentions_vlm_or_ocr(image_catalog)
            )
        ):
            counters["image_catalog_present_but_vlm_counter_missing"] += 1
            samples["image_catalog_present_but_vlm_counter_missing"].append(post_id)
        if image_ocr_reason_claimed and not vlm_fetch_or_chunk_evidence:
            counters["image_ocr_reason_without_public_vlm_counter"] += 1
            samples["image_ocr_reason_without_public_vlm_counter"].append(post_id)
        if image_context_claimed and not (image_catalog or vlm_fetch_or_chunk_evidence):
            counters["image_context_without_vlm_catalog"] += 1
            samples["image_context_without_vlm_catalog"].append(post_id)

        browser_required = _browser_visual_required(row_scopes, image_related)
        if browser_required:
            counters["browser_visual_required"] += 1
            browser_loading_failed = _browser_loading_state_failed(row_scopes)
            if _browser_or_direct_visual_available(row_scopes):
                counters["browser_visual_available"] += 1
            else:
                counters["browser_visual_missing"] += 1
                samples["browser_visual_missing"].append(post_id)
            if browser_loading_failed and (
                resolved_title_row
                or image_ocr_reason_claimed
                or _search_only_signal(row_scopes, public_text)
            ):
                counters["browser_loading_failed_or_pending_text_match_used"] += 1
                samples["browser_loading_failed_or_pending_text_match_used"].append(post_id)
            if (
                _browser_loading_counters_ok(row_scopes)
                and not (
                    _explicit_browser_visual_verified(row_scopes)
                    or _direct_visual_evidence_present(row_scopes)
                )
            ):
                counters["browser_loading_ok_but_visual_artifact_missing"] += 1
                samples["browser_loading_ok_but_visual_artifact_missing"].append(post_id)

        seed_present = _semantic_seed_review_present(row_scopes, public_text)
        final_reread_present = _final_semantic_reread_present(row_scopes, public_text)
        final_reread_required = bool(seed_present and _resolved_relevant_row(row, row_scopes))
        if seed_present:
            counters["semantic_seed_review_present"] += 1
        if final_reread_required:
            counters["final_semantic_reread_required"] += 1
        if final_reread_present:
            counters["final_semantic_reread_present"] += 1
            if final_reread_required:
                counters["final_semantic_reread_required_present"] += 1
        else:
            counters["final_semantic_reread_missing"] += 1
        if final_reread_required and not final_reread_present:
            counters["final_semantic_reread_required_missing"] += 1
            counters["semantic_seed_review_present_final_semantic_reread_missing"] += 1
            samples["semantic_seed_review_without_final_semantic_reread"].append(post_id)

    coverage_keys = (
        "total_rows",
        "image_post_count",
        "image_related_row_count",
        "image_evidence_catalog_row_count",
        "image_evidence_catalog_present",
        "image_evidence_catalog_missing",
        "image_evidence_catalog_unreviewable",
        "image_catalog_present_but_vlm_counter_missing",
        "image_ocr_reason_claimed",
        "image_ocr_reason_without_public_vlm_counter",
        "image_context_without_vlm_catalog",
        "comment_row_count",
        "comment_metadata_present",
        "comment_metadata_missing",
        "comment_dialogue_context_present",
        "comment_dialogue_context_missing",
        "comment_context_claimed_row_count",
        "comment_context_resolution_row_count",
        "comment_context_resolution_without_attribution",
        "comment_author_match_unverified_signal",
        "comment_author_match_unverified_used_for_resolution",
        "comment_author_match_unverified_resolution_review_only",
        "search_only_resolved_title",
        "search_only_resolved_title_review_only",
        "blocked_intent_resolved_title",
        "blocked_intent_resolved_title_review_only",
        "intent_denied_title_present",
        "adjacent_reason_non_relevant_wording_conflict",
        "final_semantic_reread_present",
        "final_semantic_reread_missing",
        "final_semantic_reread_required",
        "final_semantic_reread_required_present",
        "final_semantic_reread_required_missing",
        "semantic_seed_review_present",
        "semantic_seed_review_present_final_semantic_reread_missing",
        "browser_visual_required",
        "browser_visual_available",
        "browser_visual_missing",
        "browser_loading_failed_or_pending_text_match_used",
        "browser_loading_ok_but_visual_artifact_missing",
        "browser_visual_external_artifact_available",
    )
    coverage = {key: int(counters.get(key, 0)) for key in coverage_keys}

    issues: list[dict[str, Any]] = []
    if coverage["total_rows"] == 0:
        issues.append(
            _issue(
                "no_result_rows_found",
                "REVIEW-LOCKED",
                1,
                [],
                "입력 JSON에서 rows/results/items/data 계열 result row를 찾지 못했다.",
                "result JSON 구조를 확인하거나 실제 result list/dict를 --result로 전달한다.",
            )
        )
    if coverage["image_evidence_catalog_missing"] > 0:
        issues.append(
            _issue(
                "image_evidence_catalog_missing",
                "REVIEW-LOCKED",
                coverage["image_evidence_catalog_missing"],
                samples["image_evidence_catalog_missing"],
                "이미지/VLM/OCR 관련 row인데 공개 image_evidence_catalog가 없다.",
                "이미지 row를 VLM/OCR on 결과 또는 reviewable image_evidence_catalog가 포함된 산출물로 재생성/보강한다.",
            )
        )
    if coverage["image_catalog_present_but_vlm_counter_missing"] > 0:
        issues.append(
            _issue(
                "image_catalog_present_but_vlm_counter_missing",
                "REVIEW-LOCKED",
                coverage["image_catalog_present_but_vlm_counter_missing"],
                samples["image_catalog_present_but_vlm_counter_missing"],
                "이미지 evidence catalog는 있으나 공개 row에서 VLM/OCR fetch/chunk counter를 찾지 못했다.",
                "이미지 row에는 image_fetch_count/success, vlm_chunks_sent/count, vlm_total_bytes 또는 동등한 OCR/VLM 상태 필드를 남긴다.",
            )
        )
    if coverage["image_ocr_reason_without_public_vlm_counter"] > 0:
        issues.append(
            _issue(
                "image_ocr_reason_without_public_vlm_counter",
                "REVIEW-LOCKED",
                coverage["image_ocr_reason_without_public_vlm_counter"],
                samples["image_ocr_reason_without_public_vlm_counter"],
                "reason/public text가 이미지 OCR/VLM 근거를 언급하지만 공개 VLM/OCR fetch/chunk counter가 없다.",
                "reason에만 남은 OCR 주장을 근거로 승인하지 말고 VLM/OCR 실행/실패/skip 상태를 공개 필드로 재생성한다.",
            )
        )
    if coverage["image_evidence_catalog_unreviewable"] > 0:
        issues.append(
            _issue(
                "image_evidence_catalog_unreviewable",
                "REVIEW",
                coverage["image_evidence_catalog_unreviewable"],
                samples["image_evidence_catalog_unreviewable"],
                "image_evidence_catalog item에 source/URL/status 계열 trace 또는 OCR/VLM snippet이 부족해 packet 단위 검토성이 낮다.",
                "catalog item에 source_url/image_index, ocr_text/visual_summary/explicit_work_title, status/grade를 보강한다.",
            )
        )
    if coverage["browser_loading_ok_but_visual_artifact_missing"] > 0:
        issues.append(
            _issue(
                "browser_loading_ok_but_visual_artifact_missing",
                "REVIEW",
                coverage["browser_loading_ok_but_visual_artifact_missing"],
                samples["browser_loading_ok_but_visual_artifact_missing"],
                "브라우저 이미지 로딩 counter는 정상이나 screenshot/snapshot/direct visual review linkage가 없다.",
                "로딩 성공과 사람이/비전이 화면을 확인했다는 증거를 분리해 browser artifact manifest 또는 direct visual evidence를 연결한다.",
            )
        )
    if coverage["browser_loading_failed_or_pending_text_match_used"] > 0:
        issues.append(
            _issue(
                "image_loading_failed_or_pending_text_match_used",
                "REVIEW-LOCKED",
                coverage["browser_loading_failed_or_pending_text_match_used"],
                samples["browser_loading_failed_or_pending_text_match_used"],
                "이미지 로딩이 실패/대기 상태인데 resolved title, OCR/reason, search-only 텍스트 매칭이 결론 근거로 쓰인 흔적이 있다.",
                "해당 row는 텍스트/OCR 매칭만으로 Strong/GO 처리하지 말고 Browser screenshot/snapshot 또는 VLM/OCR 재처리로 이미지 로딩 완료와 시각 정합성을 확인한다.",
            )
        )
    if coverage["browser_visual_missing"] > 0:
        issues.append(
            _issue(
                "browser_visual_or_direct_evidence_missing",
                "REVIEW-LOCKED",
                coverage["browser_visual_missing"],
                samples["browser_visual_missing"],
                "browser visual이 필요해 보이는 row에서 공개 browser/direct visual evidence를 찾지 못했다.",
                "Codex IAB/browser visual review 또는 direct visual evidence artifact를 별도 연결한다.",
            )
        )
    if coverage["image_context_without_vlm_catalog"] > 0:
        issues.append(
            _issue(
                "image_context_without_vlm_catalog",
                "REVIEW-LOCKED",
                coverage["image_context_without_vlm_catalog"],
                samples["image_context_without_vlm_catalog"],
                "context_sources=image 또는 anchor_type=image가 있지만 image_evidence_catalog나 VLM fetch/chunk 근거가 없다.",
                "image context claim을 약한 힌트로 낮추거나 VLM/OCR catalog/fetch/chunk status가 포함된 산출물로 재생성한다.",
            )
        )
    if coverage["semantic_seed_review_present_final_semantic_reread_missing"] > 0:
        issues.append(
            _issue(
                "semantic_seed_review_without_final_semantic_reread",
                "REVIEW-LOCKED",
                coverage["semantic_seed_review_present_final_semantic_reread_missing"],
                samples["semantic_seed_review_without_final_semantic_reread"],
                "semantic_seed_review/context-only 위험 신호가 있으나 final semantic reread 공개 흔적이 없다.",
                "semantic seed demotion row의 후단 final_semantic_reread 기록을 남기거나 expanded review packet에서 별도 검토한다.",
            )
        )
    if coverage["comment_context_resolution_without_attribution"] > 0:
        issues.append(
            _issue(
                "comment_context_resolution_without_attribution",
                "REVIEW-LOCKED",
                coverage["comment_context_resolution_without_attribution"],
                samples["comment_context_resolution_without_attribution"],
                "댓글 맥락이 resolved 판정에 관여한 것으로 보이지만 comment_metadata와 comment_dialogue_context가 모두 갖춰져 있지 않다.",
                "댓글 author/IP/comment_id와 speaker-aware dialogue context를 포함한 source/result로 재생성하거나 해당 판정을 HOLD/human_review로 낮춘다.",
            )
        )
    if coverage["comment_author_match_unverified_used_for_resolution"] > 0:
        issues.append(
            _issue(
                "comment_author_match_unverified_used_for_resolution",
                "REVIEW-LOCKED",
                coverage["comment_author_match_unverified_used_for_resolution"],
                samples["comment_author_match_unverified_used_for_resolution"],
                "author_match_unverified 또는 post_author_match_unverified 신호가 있는 댓글 맥락이 resolved 판정에 관여했다.",
                "동일 닉네임/익명 댓글을 원글 작성자 발화나 독립 작품 evidence로 승격하지 않았는지 packet별로 재검토한다.",
            )
        )
    if coverage["comment_author_match_unverified_resolution_review_only"] > 0:
        issues.append(
            _issue(
                "comment_author_match_unverified_resolution_review_only",
                "REVIEW",
                coverage["comment_author_match_unverified_resolution_review_only"],
                samples["comment_author_match_unverified_resolution_review_only"],
                "unverified comment author 신호가 있지만 title/alias/search support가 별도로 있어 댓글을 독립 작품 evidence로 썼는지 확인하면 되는 review-only 상태다.",
                "대량 승인 전 packet별로 댓글 author 신호가 title resolution의 필수 근거인지 확인한다.",
            )
        )
    if coverage["search_only_resolved_title"] > 0:
        issues.append(
            _issue(
                "search_only_resolved_title",
                "REVIEW-LOCKED",
                coverage["search_only_resolved_title"],
                samples["search_only_resolved_title"],
                "search_only/official_search_only 신호가 있는데도 resolved title이 공개 결과에 남아 있다.",
                "검색 snippet만으로 살아남은 title인지 packet별로 재검토하고, 직접 원문/공식/detail evidence 없으면 HOLD/REJECT로 낮춘다.",
            )
        )
    if coverage["blocked_intent_resolved_title"] > 0:
        issues.append(
            _issue(
                "blocked_intent_resolved_title",
                "REVIEW-LOCKED",
                coverage["blocked_intent_resolved_title"],
                samples["blocked_intent_resolved_title"],
                "community_banter/trope_discussion/author_talk/recommendation intent인데 resolved title이 공개 결과에 남아 있다.",
                "해당 packet의 원문 intent와 direct anchor를 재검토하고, 특정 작품 토론이 아니면 title 확정을 차단한다.",
            )
        )
    if coverage["intent_denied_title_present"] > 0:
        issues.append(
            _issue(
                "intent_denied_title_present",
                "REVIEW-LOCKED",
                coverage["intent_denied_title_present"],
                samples["intent_denied_title_present"],
                "`intent_permit_for_title_search=false`, `title_resolution_allowed=false`, `context_only/no_work` 신호가 있는데 공개 결과에 title이 남아 있다.",
                "no-work/social-lament/context-only 결과를 search/rescue/known alias/session knowledge/Arbiter promotion이 되살린 경로인지 확인하고, direct hard anchor가 없으면 title을 null로 낮춘다.",
            )
        )
    if coverage["search_only_resolved_title_review_only"] > 0:
        issues.append(
            _issue(
                "search_only_resolved_title_review_only",
                "REVIEW",
                coverage["search_only_resolved_title_review_only"],
                samples["search_only_resolved_title_review_only"],
                "search_only 신호가 있으나 specific_work hold와 직접 anchor가 함께 보여 hard blocker가 아니라 정성 확인 대상으로 분리됐다.",
                "direct alias/body anchor와 공식/detail evidence가 실제 결론을 지지하는지 review packet에서 확인한다.",
            )
        )
    if coverage["blocked_intent_resolved_title_review_only"] > 0:
        issues.append(
            _issue(
                "blocked_intent_resolved_title_review_only",
                "REVIEW",
                coverage["blocked_intent_resolved_title_review_only"],
                samples["blocked_intent_resolved_title_review_only"],
                "차단 intent 신호가 있으나 specific_work hold와 직접 anchor가 함께 보여 hard blocker가 아니라 정성 확인 대상으로 분리됐다.",
                "community/trope/author/recommendation 표면이 실제 특정 작품 토론인지 packet별로 확인한다.",
            )
        )
    if coverage["adjacent_reason_non_relevant_wording_conflict"] > 0:
        issues.append(
            _issue(
                "adjacent_reason_non_relevant_wording_conflict",
                "REVIEW",
                coverage["adjacent_reason_non_relevant_wording_conflict"],
                samples["adjacent_reason_non_relevant_wording_conflict"],
                "adjacent/주변 관련 row의 public reason에 `최종 판정은 비관련 포스트` 문구가 함께 남아 판정 범위가 혼동될 수 있다.",
                "future run에서는 adjacent reason을 `작품 주변 맥락은 인정하되 단일 공식 제목 미확정`으로 유지하고, 기존 artifact는 정성 라벨에서 HOLD로 분리한다.",
            )
        )
    if coverage["final_semantic_reread_required"] > 0 and coverage["final_semantic_reread_required_present"] == 0:
        issues.append(
            _issue(
                "final_semantic_reread_coverage_missing",
                "REVIEW",
                coverage["final_semantic_reread_required"],
                samples["semantic_seed_review_without_final_semantic_reread"],
                "final semantic reread가 필요한 resolved semantic-risk row에서 공개 reread 흔적을 찾지 못했다.",
                "resolved semantic-risk row에는 후단 final_semantic_reread 기록을 남기거나 expanded review packet에서 별도 검토한다.",
            )
        )
    if coverage["comment_metadata_missing"] > 0:
        issues.append(
            _issue(
                "comment_metadata_missing",
                "REVIEW",
                coverage["comment_metadata_missing"],
                samples["comment_metadata_missing"],
                "댓글이 있는 row에서 author/IP/comment_id 기반 comment_metadata를 찾지 못했다.",
                "댓글 있는 source/result에는 comment_metadata를 공개 필드로 유지해 speaker attribution을 검토한다.",
            )
        )
    if coverage["comment_dialogue_context_missing"] > 0:
        issues.append(
            _issue(
                "comment_dialogue_context_missing",
                "REVIEW",
                coverage["comment_dialogue_context_missing"],
                samples["comment_dialogue_context_missing"],
                "댓글이 있는 row에서 comment_dialogue_context_lines를 찾지 못했다.",
                "semantic prompt/review packet에 댓글 대화 맥락 line을 보존했는지 재확인한다.",
            )
        )

    issues, review_closures = _apply_review_label_closures(issues, review_labels or [])
    gate = _gate_from_issues(issues)
    return {
        "tool_purpose": (
            "Audit public semantic/VLM/comment coverage gaps in large or partial expert_main result JSON. "
            "This is a coverage audit, not a semantic approval tool."
        ),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "result_path": str(result_path or ""),
        "rows_source": rows_source,
        "semantic_approval": {
            "status": "not_granted_by_semantic_coverage_audit",
            "reason": (
                "이 도구는 구조 필드와 공개 evidence coverage만 집계한다. "
                "targeted canary 회복이나 coverage GO를 10만 건 semantic approval로 승격하지 않는다."
            ),
        },
        "gate": gate,
        "coverage": coverage,
        "issues": issues,
        "review_closures": review_closures,
        "recommended_actions": _recommended_actions(issues),
        "review_labels_path": review_labels_path.as_posix() if review_labels_path else None,
        "external_browser_artifact_manifest": browser_artifact_manifest.as_posix()
        if browser_artifact_manifest
        else None,
        "external_browser_artifact_rows": len(browser_artifacts),
    }


def audit_data(
    data: Any,
    *,
    result_path: Path | None = None,
    browser_artifacts: dict[str, dict[str, Any]] | None = None,
    browser_artifact_manifest: Path | None = None,
    review_labels: list[dict[str, Any]] | None = None,
    review_labels_path: Path | None = None,
) -> dict[str, Any]:
    rows, rows_source = result_rows(data)
    return audit_rows(
        rows,
        result_path=result_path,
        rows_source=rows_source,
        browser_artifacts=browser_artifacts,
        browser_artifact_manifest=browser_artifact_manifest,
        review_labels=review_labels,
        review_labels_path=review_labels_path,
    )


def audit_result(
    path: Path,
    *,
    browser_artifact_manifest: Path | None = None,
    review_labels_path: Path | None = None,
) -> dict[str, Any]:
    browser_artifacts = (
        load_browser_artifacts(browser_artifact_manifest)
        if browser_artifact_manifest
        else None
    )
    review_labels = load_review_labels(review_labels_path) if review_labels_path else None
    return audit_data(
        load_json(path),
        result_path=path,
        browser_artifacts=browser_artifacts,
        browser_artifact_manifest=browser_artifact_manifest,
        review_labels=review_labels,
        review_labels_path=review_labels_path,
    )


def build_markdown(audit: dict[str, Any]) -> str:
    coverage = audit.get("coverage") or {}
    issues = audit.get("issues") or []
    actions = audit.get("recommended_actions") or []
    closures = audit.get("review_closures") or []
    issue_lines = "\n".join(
        "- `{severity}` `{code}` count=`{count}` samples=`{samples}`: {description}".format(
            severity=item.get("severity"),
            code=item.get("code"),
            count=item.get("count"),
            samples=", ".join(str(v) for v in (item.get("sample_post_ids") or [])) or "none",
            description=item.get("description"),
        )
        for item in issues
    ) or "- 없음"
    action_lines = "\n".join(f"- {action}" for action in actions) or "- 추가 조치 없음"
    closure_lines = "\n".join(
        "- `{code}` closed_count=`{count}` posts=`{posts}`".format(
            code=item.get("issue_code"),
            count=item.get("closed_count"),
            posts=", ".join(str(value) for value in item.get("closed_post_ids") or []) or "none",
        )
        for item in closures
    ) or "- 없음"
    text = f"""# Semantic/VLM/댓글 커버리지 감사

## 요약

- gate: `{audit.get('gate')}`
- semantic_approval: `{(audit.get('semantic_approval') or {}).get('status')}`
- result: `{audit.get('result_path') or 'stdin/object'}`
- rows_source: `{audit.get('rows_source')}`
- total_rows: `{coverage.get('total_rows', 0)}`
- review_labels_path: `{audit.get('review_labels_path') or 'none'}`
- external_browser_artifact_manifest: `{audit.get('external_browser_artifact_manifest') or 'none'}`

## 커버리지

- image_post_count: `{coverage.get('image_post_count', 0)}`
- image_related_row_count: `{coverage.get('image_related_row_count', 0)}`
- image_evidence_catalog_present/missing: `{coverage.get('image_evidence_catalog_present', 0)}/{coverage.get('image_evidence_catalog_missing', 0)}`
- image_evidence_catalog_unreviewable: `{coverage.get('image_evidence_catalog_unreviewable', 0)}`
- image_catalog_present_but_vlm_counter_missing: `{coverage.get('image_catalog_present_but_vlm_counter_missing', 0)}`
- image_ocr_reason_claimed/without_public_vlm_counter: `{coverage.get('image_ocr_reason_claimed', 0)}/{coverage.get('image_ocr_reason_without_public_vlm_counter', 0)}`
- image_context_without_vlm_catalog: `{coverage.get('image_context_without_vlm_catalog', 0)}`
- comment_row_count: `{coverage.get('comment_row_count', 0)}`
- comment_metadata_present/missing: `{coverage.get('comment_metadata_present', 0)}/{coverage.get('comment_metadata_missing', 0)}`
- comment_dialogue_context_present/missing: `{coverage.get('comment_dialogue_context_present', 0)}/{coverage.get('comment_dialogue_context_missing', 0)}`
- comment_context_claimed/resolution/without_attribution: `{coverage.get('comment_context_claimed_row_count', 0)}/{coverage.get('comment_context_resolution_row_count', 0)}/{coverage.get('comment_context_resolution_without_attribution', 0)}`
- comment_author_match_unverified_signal/used_for_resolution/review_only: `{coverage.get('comment_author_match_unverified_signal', 0)}/{coverage.get('comment_author_match_unverified_used_for_resolution', 0)}/{coverage.get('comment_author_match_unverified_resolution_review_only', 0)}`
- search_only_resolved_title/review_only: `{coverage.get('search_only_resolved_title', 0)}/{coverage.get('search_only_resolved_title_review_only', 0)}`
- blocked_intent_resolved_title/review_only: `{coverage.get('blocked_intent_resolved_title', 0)}/{coverage.get('blocked_intent_resolved_title_review_only', 0)}`
- intent_denied_title_present: `{coverage.get('intent_denied_title_present', 0)}`
- final_semantic_reread_present/missing: `{coverage.get('final_semantic_reread_present', 0)}/{coverage.get('final_semantic_reread_missing', 0)}`
- final_semantic_reread_required/present/missing: `{coverage.get('final_semantic_reread_required', 0)}/{coverage.get('final_semantic_reread_required_present', 0)}/{coverage.get('final_semantic_reread_required_missing', 0)}`
- semantic_seed_review_present: `{coverage.get('semantic_seed_review_present', 0)}`
- semantic_seed_review_present + final_semantic_reread_missing: `{coverage.get('semantic_seed_review_present_final_semantic_reread_missing', 0)}`
- browser_visual_required/available/missing: `{coverage.get('browser_visual_required', 0)}/{coverage.get('browser_visual_available', 0)}/{coverage.get('browser_visual_missing', 0)}`
- browser_loading_failed_or_pending_text_match_used: `{coverage.get('browser_loading_failed_or_pending_text_match_used', 0)}`
- browser_loading_ok_but_visual_artifact_missing: `{coverage.get('browser_loading_ok_but_visual_artifact_missing', 0)}`
- browser_visual_external_artifact_available: `{coverage.get('browser_visual_external_artifact_available', 0)}`

## 이슈

{issue_lines}

## Review Label Closure

{closure_lines}

## 권장 조치

{action_lines}

## 판정 메모

이 감사는 공개 구조 필드, VLM/OCR image evidence catalog와 fetch/chunk counter, 댓글 speaker metadata, 댓글 맥락 attribution, search_only/차단 intent resolved title, final semantic reread 흔적을 한 번에 세는 보조 도구다.
`GO`가 나오더라도 10만 건 semantic approval이 아니며, expanded random/high-risk semantic review와 browser visual 검증은 별도 gate로 유지한다.
"""
    return text


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit semantic/VLM/comment public coverage in result JSON.")
    parser.add_argument("--result", required=True, type=Path, help="expert_main result JSON; list or dict wrapper")
    parser.add_argument(
        "--browser-artifacts-manifest",
        type=Path,
        default=None,
        help="Optional manifest with browser screenshots/snapshots keyed by post_id.",
    )
    parser.add_argument(
        "--review-labels",
        type=Path,
        default=None,
        help="Optional JSONL labels that close REVIEW-only packet issues by post_id and issue_code.",
    )
    parser.add_argument("--output-json", type=Path, default=None)
    parser.add_argument("--output-md", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    audit = audit_result(
        args.result,
        browser_artifact_manifest=args.browser_artifacts_manifest,
        review_labels_path=args.review_labels,
    )
    payload = json.dumps(audit, ensure_ascii=False, indent=2)
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(payload + "\n", encoding="utf-8")
    if args.output_md:
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        args.output_md.write_text(build_markdown(audit), encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
