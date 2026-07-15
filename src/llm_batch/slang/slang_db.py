"""작품 약칭과 커뮤니티 용어를 조회하는 Slang DB 계층.

조회와 후보 제안은 허용하지만 중앙 DB 변경은 이 모듈이 직접 확정하지 않는다.
변경은 governance 승인과 transaction sidecar를 거쳐야 한다.
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from ..experts.decoder import KNOWN_ABBREVIATIONS, abbreviation_match_score
from ..experts.utils import KNOWN_TITLE_ABBREVIATIONS
from ..domain.rules import GENRE_ARCHETYPE_TERMS, SLANG_DICTIONARY

_NORMALIZE_TERM_RE = re.compile(r"[^\uac00-\ud7a3A-Za-z0-9]")

_GENERIC_TERM_STOPLIST = {
    "로판",
    "현판",
    "판타지",
    "무협",
    "소설",
    "작품",
    "작가",
    "시리즈",
    "노벨피아",
    "문피아",
    "카카페",
    "추천",
    "리뷰",
    "광고",
    "회차",
    "유료화",
    "표지",
    "신작",
    "막화",
    "결말",
    "다운",
    "기우제",
    "novel",
    "dc",
    "www",
    "http",
    "https",
    "com",
    "net",
    "org",
    "kr",
    "munpia",
    "novelpia",
    "kakao",
    "page",
    "naver",
    "series",
    "dcinside",
    "novel.munpia.com",
    "novelpia.com",
    "series.naver.com",
    "page.kakao.com",
}

_GENERIC_TERM_STOPLIST_NORMALIZED = {
    _NORMALIZE_TERM_RE.sub("", item).lower().strip()
    for item in _GENERIC_TERM_STOPLIST
}
_GENRE_ARCHETYPE_TERMS_NORMALIZED = {
    _NORMALIZE_TERM_RE.sub("", item).lower().strip()
    for item in GENRE_ARCHETYPE_TERMS
}

_LOW_INFORMATION_ALIAS_SURFACES = {
    "있다",
    "없다",
    "있어",
    "있음",
    "있네",
    "있고",
    "있냐",
    "있니",
    "있어도",
    "있어서",
    "없어",
    "없음",
    "없네",
    "없고",
    "없냐",
    "없어도",
    "없어서",
    "했다",
    "한다",
    "하는",
    "하면",
    "됐다",
    "된다",
    "같다",
    "보다",
    "본다",
    "봤다",
    "너무",
    "그냥",
    "진짜",
    "무슨",
    "모든",
    "수상할",
    "정도로",
    "어느",
    "아니라",
    "그리고",
    "그래서",
    "그러나",
    "근데",
    "또",
    "더",
    "좀",
    "뭐냐",
    "이거",
    "저거",
    "그거",
    "네가",
    "내가",
    "너가",
    "제가",
    "그가",
    "너에겐",
    "나에겐",
    "너에게",
    "나에게",
    "친구",
    "현실",
    "레전드",
    "레전드임",
    "장갤",
    "변화도",
    "위기",
    "소설",
    "작품",
    "제목",
    "내용",
}

_LOW_INFORMATION_ALIAS_SURFACES_NORMALIZED = {
    _NORMALIZE_TERM_RE.sub("", item).lower().strip()
    for item in _LOW_INFORMATION_ALIAS_SURFACES
}

_PRONOUN_PARTICLE_ALIAS_RE = re.compile(
    r"^(?:"
    r"너|나|네|내|저|제|그|이|걔|쟤|얘|누구|무엇|뭐|그것|이것|저것"
    r")(?:"
    r"에게|에겐|한테|한텐|에게서|한테서|와|과|랑|하고|의|도|만|조차|마저|부터|까지|"
    r"가|이|는|은|를|을|로|으로|야|냐|네"
    r")$"
)

_DOMAIN_OR_URL_LABEL_RE = re.compile(
    r"^(?:https?://)?(?:www\.)?(?:[a-z0-9-]+\.)+(?:com|net|org|kr|co)(?:/[^\s]*)?$",
    re.IGNORECASE,
)

_FAMILY_ALIAS_AUTO_PROMOTE_MIN_TITLES = 3
_FAMILY_ALIAS_AUTO_PROMOTE_MIN_CONFIRMED_TITLES = 2
_FLUSH_PREVIEW_LIMIT = 5
_PENDING_KIND_ALIAS_CANDIDATE = "alias_candidate"
_PENDING_KIND_REFERENCE_MENTION = "reference_mention"
_PENDING_KIND_META_LABEL = "meta_label"
_PENDING_KIND_TROPE_OR_GENRE = "trope_or_genre"


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _normalize_term(text: Any) -> str:
    return _NORMALIZE_TERM_RE.sub("", str(text or "")).lower().strip()


def _normalize_title(text: Any) -> str:
    return _normalize_term(text)


def _looks_domain_or_url_label(text: Any) -> bool:
    raw = str(text or "").strip()
    if not raw:
        return True
    return bool(_DOMAIN_OR_URL_LABEL_RE.fullmatch(raw))


def _is_generic_term(term: str) -> bool:
    raw = str(term or "").strip()
    norm = _normalize_term(raw)
    if not norm or len(norm) < 2:
        return True
    if _looks_domain_or_url_label(raw):
        return True
    if _is_low_information_alias_term(raw):
        return True
    if norm in _GENERIC_TERM_STOPLIST_NORMALIZED:
        return True
    if norm in _GENRE_ARCHETYPE_TERMS_NORMALIZED:
        return True
    if re.fullmatch(r"(로판|판무|현판|무협|bl|gl|ts|ntr|장르|웹소설)", norm):
        return True
    return False


def _is_low_information_alias_term(term: str) -> bool:
    raw = str(term or "").strip()
    norm = _normalize_term(raw)
    if not norm:
        return True
    if norm in _LOW_INFORMATION_ALIAS_SURFACES_NORMALIZED:
        return True
    return bool(_PRONOUN_PARTICLE_ALIAS_RE.fullmatch(norm))


def _is_generic_title_label(title: str) -> bool:
    raw = str(title or "").strip()
    if not raw:
        return True
    if _looks_domain_or_url_label(raw):
        return True
    meta_suffixes = {
        "캐릭터",
        "등장인물",
        "인물",
        "작가",
        "표지",
        "리뷰",
        "설정",
        "설정오류지적",
        "댓글",
    }
    raw_norm = _normalize_title(raw)
    for suffix in meta_suffixes:
        suffix_norm = _normalize_title(suffix)
        if raw_norm and suffix_norm and raw_norm != suffix_norm and raw_norm.endswith(suffix_norm):
            return True
    tokens = [
        _NORMALIZE_TERM_RE.sub("", tok).lower().strip()
        for tok in re.findall(r"[가-힣A-Za-z0-9]+", raw)
    ]
    tokens = [tok for tok in tokens if tok]
    if not tokens:
        return True

    genre_tokens = {
        "판타지",
        "퓨전판타지",
        "로맨스",
        "로맨스판타지",
        "로판",
        "현판",
        "무협",
        "bl",
        "gl",
        "백합",
        "ts",
        "ntr",
        "sf",
        "헌터",
        "아카데미",
        "이세계",
        "장르",
    }
    medium_tokens = {"소설", "웹소설", "장르소설", "웹툰", "만화"}
    filler_tokens = {"형식", "표지", "표기", "작품"}

    if any(tok not in genre_tokens and tok not in medium_tokens and tok not in filler_tokens for tok in tokens):
        return False
    return bool(any(tok in genre_tokens for tok in tokens) and any(tok in medium_tokens for tok in tokens))


def _normalized_consistency_flags(raw_flags: Any) -> set[str]:
    if isinstance(raw_flags, str):
        values = [raw_flags]
    elif isinstance(raw_flags, (list, tuple, set)):
        values = list(raw_flags)
    else:
        values = []
    return {
        str(flag or "").strip().lower()
        for flag in values
        if str(flag or "").strip()
    }


def _confirmed_alias_norms_from_flags(raw_flags: Any) -> set[str]:
    norms: set[str] = set()
    for flag in _normalized_consistency_flags(raw_flags):
        if not flag.startswith("confirmed_alias:"):
            continue
        normalized = _normalize_term(flag.split(":", 1)[1])
        if normalized:
            norms.add(normalized)
    return norms


def _normalized_source_roles(raw_roles: Any, raw_role: Any = None) -> set[str]:
    roles: set[str] = set()
    if isinstance(raw_roles, (list, tuple, set)):
        for role in raw_roles:
            role_norm = str(role or "").strip().lower()
            if role_norm:
                roles.add(role_norm)
    elif isinstance(raw_roles, str):
        role_norm = str(raw_roles or "").strip().lower()
        if role_norm:
            roles.add(role_norm)

    role_single = str(raw_role or "").strip().lower()
    if role_single:
        roles.add(role_single)
    return roles


_ALIAS_WRITE_SOURCE_ROLES = frozenset({"slang_insight", "primary_work", "title_candidate"})
_REFERENCE_ONLY_ALIAS_ROLES = frozenset(
    {"mentioned_work", "secondary_reference", "recommendation_candidate", "comparison_target"}
)
_TRUSTED_ALIAS_REGISTRIES = {
    ("known_abbreviation", "known_abbreviations"): KNOWN_ABBREVIATIONS,
    ("known_title_abbreviation", "known_title_abbreviations"): KNOWN_TITLE_ABBREVIATIONS,
    ("slang_dictionary", "slang_dictionary"): SLANG_DICTIONARY,
}


def _alias_resolution_sources_verify_pair(
    title: Any,
    term: Any,
    raw_sources: Any,
) -> bool:
    """Return whether serialized registry provenance verifies this exact alias pair."""
    title_norm = _normalize_title(title)
    term_norm = _normalize_term(term)
    if not title_norm or not term_norm or not isinstance(raw_sources, list):
        return False
    for source in raw_sources:
        if not isinstance(source, dict):
            continue
        if (
            _normalize_term(source.get("alias")) != term_norm
            or _normalize_title(source.get("canonical_title")) != title_norm
        ):
            continue
        resolution_source = str(source.get("alias_resolution_source") or "").strip().lower()
        source_registry = str(source.get("source_registry") or "").strip().lower()
        registry = _TRUSTED_ALIAS_REGISTRIES.get((resolution_source, source_registry))
        if not isinstance(registry, dict):
            continue
        for registry_alias, registry_title in registry.items():
            if (
                _normalize_term(registry_alias) == term_norm
                and _normalize_title(registry_title) == title_norm
            ):
                return True
    return False


def _verified_alias_pair_proof_mode(
    title: Any,
    term: Any,
    *,
    store_in_db: Any = None,
    decode_verified: Any = None,
    alias_scope: Any = None,
    store_reason: Any = None,
    detected_term: Any = None,
    canonical_alias: Any = None,
    decoded_term: Any = None,
    consistency_flags: Any = None,
    alias_resolution_sources: Any = None,
    official_title: Any = None,
    source_roles: Any = None,
) -> Optional[str]:
    """Return the proof mode for an exact alias/title pair, or None when fail-closed."""
    title_norm = _normalize_title(title)
    term_norm = _normalize_term(term)
    if not title_norm or not term_norm:
        return None

    roles = _normalized_source_roles(source_roles)
    if roles and not roles & _ALIAS_WRITE_SOURCE_ROLES:
        return None

    # None is the schema's unset value. Any other non-bool value is malformed;
    # in particular 0/1 and "false"/"true" must not emulate explicit policy.
    if store_in_db is not None and type(store_in_db) is not bool:
        return None

    strict_contract = bool(
        store_in_db is True
        and decode_verified is True
        and str(alias_scope or "").strip().lower() == "pure_work_alias"
        and str(store_reason or "").strip().lower() == "pure_work_alias"
        and _normalize_term(detected_term) == term_norm
        and _normalize_term(canonical_alias) == term_norm
        and _normalize_title(decoded_term) == title_norm
    )
    if store_in_db is True and not strict_contract:
        return None
    if store_in_db is False and _normalize_term(detected_term) == term_norm:
        return None
    if strict_contract:
        return "strict_slang_contract"

    flags = _normalized_consistency_flags(consistency_flags)
    verified_flag_pair = bool(
        _normalize_title(official_title) == title_norm
        and term_norm in _confirmed_alias_norms_from_flags(flags)
        and flags
        & {
            "verified_alias_official_detail_anchor",
            "explicit_alias_official_work_lock",
        }
    )
    if verified_flag_pair:
        return "verified_official_alias_flag"

    if (
        _normalize_title(official_title) == title_norm
        and _alias_resolution_sources_verify_pair(title, term, alias_resolution_sources)
    ):
        return "trusted_registry_exact_pair"
    return None


def _classify_pending_kind(
    *,
    title: str,
    source_roles: List[str],
    discussion_type: str,
    subtype: str,
    work_resolution: str,
) -> Tuple[str, str, str]:
    title_raw = str(title or "").strip()
    source_set = {str(x or "").strip().lower() for x in (source_roles or []) if str(x or "").strip()}
    discussion_type_norm = str(discussion_type or "").strip().lower()
    subtype_norm = str(subtype or "").strip().lower()
    work_resolution_norm = str(work_resolution or "").strip().lower()

    if _is_generic_title_label(title_raw):
        return _PENDING_KIND_META_LABEL, "generic_or_meta_title_label", "high"

    if discussion_type_norm in {"trope_discussion", "genre_opinion"} or subtype_norm == "genre_trope_discussion":
        return _PENDING_KIND_TROPE_OR_GENRE, "genre_or_trope_context", "high"

    if subtype_norm in {
        "author_meta",
        "platform_meta",
        "release_serialization_meta",
        "community_work_banter",
    }:
        return _PENDING_KIND_META_LABEL, "meta_context", "medium"

    if source_set & {"comparison_target", "mentioned_work", "secondary_reference", "recommendation_candidate"}:
        return _PENDING_KIND_REFERENCE_MENTION, "reference_or_comparison_context", "high"

    if work_resolution_norm in {"multi_work", "none"}:
        return _PENDING_KIND_REFERENCE_MENTION, "non_single_work_resolution", "medium"

    if source_set & {"slang_insight", "primary_work", "title_candidate"}:
        return _PENDING_KIND_ALIAS_CANDIDATE, "work_alias_candidate", "medium"

    return _PENDING_KIND_REFERENCE_MENTION, "fallback_reference_context", "low"


def _looks_sentence_like_term(term: str) -> bool:
    raw = str(term or "").strip()
    if not raw:
        return True
    norm = _normalize_term(raw)
    if not norm:
        return True
    tokens = [tok for tok in re.findall(r"[가-힣A-Za-z0-9]+", raw) if tok]
    if len(tokens) >= 2 and re.search(r"\s", raw):
        return True
    if len(tokens) >= 4:
        return True
    if len(norm) >= 18:
        return True
    if len(tokens) >= 3 and len(norm) >= 10:
        return True
    if any(ch in raw for ch in ("\n", "?", "!", "…", ";", ":")):
        return True
    separator_count = sum(raw.count(ch) for ch in (",", "/", "|", "·"))
    if separator_count >= 2:
        return True
    if separator_count >= 1 and len(tokens) >= 2:
        return True
    if len(tokens) >= 2 and any(tok.lower() in {"on", "off"} for tok in tokens[1:]):
        return True
    phrase_markers = (
        "너무",
        "불쌍",
        "무서",
        "하차",
        "하렘",
        "몇화",
        "급함",
        "떡씬",
        "후기",
        "리뷰",
        "스포",
        "질문",
        "어떰",
        "어때",
        "봤",
        "보고",
        "보는중",
        "재밌",
        "재미",
        "아쉽",
        "왔다",
        "떴",
        "휴재",
        "각임",
        "같아",
        "같음",
        "좋네",
        "좋다",
        "싫네",
        "싫다",
    )
    if len(tokens) >= 2 and any(marker in raw for marker in phrase_markers):
        return True
    sentence_tail_patterns = (
        r"(뭔데|뭐냐|맞냐|아니냐|같음|같다|아쉽노|가능하다는말이있다|더보고싶었는데|보고싶었는데|해결가능하다는말이있다)$",
    )
    if len(tokens) >= 2 and any(re.search(pat, raw) for pat in sentence_tail_patterns):
        return True
    return False


def _looks_mixed_entity_slang(term: str, title: str, decoded_term: Any = None) -> bool:
    raw_decoded = str(decoded_term or "").strip()
    if not raw_decoded:
        return False
    term_norm = _normalize_term(term)
    title_norm = _normalize_title(title)
    decoded_norm = _normalize_title(raw_decoded)
    if not term_norm or not title_norm or not decoded_norm:
        return False
    if title_norm not in decoded_norm or decoded_norm == title_norm:
        return False

    raw_decoded_lower = raw_decoded.lower()
    has_role_marker = (
        "+" in raw_decoded
        or "캐릭터" in raw_decoded
        or "인물" in raw_decoded
        or "작가" in raw_decoded
        or "character" in raw_decoded_lower
        or "author" in raw_decoded_lower
    )
    if not has_role_marker:
        return False

    extra_norm = decoded_norm.replace(title_norm, "", 1).strip()
    return bool(extra_norm)


def _looks_title_plus_entity_alias(term: str, title: str, entity_terms: List[str]) -> bool:
    term_norm = _normalize_term(term)
    title_norm = _normalize_title(title)
    if not term_norm or not title_norm or not entity_terms:
        return False

    for entity_term in entity_terms:
        ent_norm = _normalize_term(entity_term)
        if not ent_norm or len(ent_norm) < 2 or term_norm == ent_norm:
            continue
        if not term_norm.endswith(ent_norm):
            continue
        prefix_norm = term_norm[: len(term_norm) - len(ent_norm)]
        if len(prefix_norm) < 2:
            continue
        if prefix_norm == title_norm or prefix_norm in title_norm or title_norm.startswith(prefix_norm):
            return True
        try:
            if float(abbreviation_match_score(prefix_norm, title)) >= 0.45:
                return True
        except Exception:
            continue
    return False


def _is_exact_title_alias(term: str, title: str) -> bool:
    return bool(_normalize_term(term) and _normalize_term(term) == _normalize_title(title))


def _should_hold_direct_slang_promotion(source_roles: List[str]) -> bool:
    normalized_roles = {
        str(role or "").strip().lower()
        for role in (source_roles or [])
        if str(role or "").strip()
    }
    # slang_insight 단독 관측은 한 번의 LLM/OCR 추정만으로 확정 slang 버킷에 오를 수 있어
    # ambiguous alias 오염을 만들기 쉽다. 1차로 pending에 두고 후속 근거를 기다린다.
    return normalized_roles == {"slang_insight"}


def _is_reviewable_context(
    *,
    topicality: str,
    subtype: str,
    work_resolution: str,
    discussion_type: str,
    anchor_type: str,
) -> bool:
    topicality_norm = str(topicality or "").strip().lower()
    subtype_norm = str(subtype or "").strip().lower()
    work_resolution_norm = str(work_resolution or "").strip().lower()
    discussion_type_norm = str(discussion_type or "").strip().lower()
    anchor_type_norm = str(anchor_type or "").strip().lower()

    if topicality_norm == "unrelated":
        return False
    if subtype_norm in {
        "daily_life",
        "realworld_social_talk",
        "cross_media_game",
        "pure_meme",
        "other_quarantine",
    }:
        return False
    if discussion_type_norm in {"noise", "undecodable_reference"} and topicality_norm != "adjacent_relevant":
        return False
    if anchor_type_norm == "image" and work_resolution_norm not in {"resolved", "unresolved", "multi_work"}:
        return False
    if topicality_norm in {"core_relevant", "adjacent_relevant"}:
        return True
    return work_resolution_norm in {"resolved", "unresolved", "multi_work"}


def _example_is_reviewable(example: Dict[str, Any]) -> bool:
    return _is_reviewable_context(
        topicality=str(example.get("topicality") or ""),
        subtype=str(example.get("subtype") or ""),
        work_resolution=str(example.get("work_resolution") or ""),
        discussion_type=str(example.get("discussion_type") or ""),
        anchor_type=str(example.get("anchor_type") or ""),
    )


def _is_unresolvable_memory_query_context(
    *,
    title_resolution_state: str,
    title_resolution_allowed: Any,
    subtype: str,
    work_resolution: str,
    discussion_type: str,
) -> bool:
    state_norm = str(title_resolution_state or "").strip().lower()
    subtype_norm = str(subtype or "").strip().lower()
    work_resolution_norm = str(work_resolution or "").strip().lower()
    discussion_type_norm = str(discussion_type or "").strip().lower()
    allowed_false = (
        title_resolution_allowed is False
        or str(title_resolution_allowed).strip().lower() in {"false", "0", "no", "off"}
    )
    return bool(
        allowed_false
        and state_norm == "unresolvable_memory_query"
        and work_resolution_norm == "none"
        and (
            subtype_norm
            in {"recommendation_request", "unresolved_work", "memory_query", "other_quarantine"}
            or discussion_type_norm in {"recommendation", "off_topic", "undecodable_reference", "noise"}
        )
    )


def _example_has_polluted_alias_seed_signal(example: Dict[str, Any]) -> bool:
    flags = _normalized_consistency_flags(example.get("consistency_flags"))
    title_resolution_state = str(example.get("title_resolution_state") or "").strip().lower()
    title_resolution_allowed = example.get("title_resolution_allowed")
    allowed_false = (
        title_resolution_allowed is False
        or str(title_resolution_allowed).strip().lower() in {"false", "0", "no", "off"}
    )
    if allowed_false and (
        title_resolution_state in {"context_only", "nonwork", "unresolvable_memory_query"}
        or flags
        & {
            "context_only_no_work_anchor",
            "semantic_seed_review_specific_work_denied",
            "semantic_seed_review_non_title_terms_removed",
            "surface_paraphrase_non_title_terms_removed",
            "batch_memory_alias_rescue_blocked_semantic_seed",
        }
    ):
        return True
    if _is_unresolvable_memory_query_context(
        title_resolution_state=title_resolution_state,
        title_resolution_allowed=title_resolution_allowed,
        subtype=str(example.get("subtype") or ""),
        work_resolution=str(example.get("work_resolution") or ""),
        discussion_type=str(example.get("discussion_type") or ""),
    ):
        return True
    rescue_flags = {
        "batch_memory_exact_alias_rescued",
        "title_surface_primary_candidate_rescued",
    }
    demotion_flags = {
        "notes_demoted_for_unresolved",
        "primary_work_cleared_non_core",
        "primary_work_cleared_non_resolved",
        "memory_query_canonical_rescue_blocked",
    }
    source_roles = _normalized_source_roles(example.get("source_roles"), example.get("source_role"))
    legacy_reference_memory_query = bool(
        str(example.get("subtype") or "").strip().lower() == "recommendation_request"
        and str(example.get("work_resolution") or "").strip().lower() == "none"
        and str(example.get("discussion_type") or "").strip().lower() == "recommendation"
        and source_roles
        & {
            "mentioned_work",
            "secondary_reference",
            "recommendation_candidate",
            "comparison_target",
        }
        and flags
        & {
            "notes_demoted_for_unresolved",
            "primary_work_cleared_non_core",
            "memory_query_canonical_rescue_blocked",
        }
    )
    if legacy_reference_memory_query:
        return True
    return bool(flags & rescue_flags and flags & demotion_flags)


def _example_has_verified_alias_write_contract(
    title: str,
    term: str,
    example: Dict[str, Any],
    *,
    fallback_source_roles: Any = None,
) -> bool:
    title_norm = _normalize_title(title)
    term_norm = _normalize_term(term)
    if not title_norm or not term_norm or not isinstance(example, dict):
        return False
    source_roles = (
        example.get("source_roles")
        or example.get("sources")
        or fallback_source_roles
    )
    proof_mode = _verified_alias_pair_proof_mode(
        title,
        term,
        store_in_db=example.get("slang_store_in_db"),
        decode_verified=example.get("slang_decode_verified"),
        alias_scope=example.get("slang_alias_scope"),
        store_reason=example.get("slang_store_reason"),
        detected_term=example.get("slang_detected_term"),
        canonical_alias=example.get("slang_canonical_alias"),
        decoded_term=example.get("slang_decoded_term"),
        consistency_flags=example.get("consistency_flags"),
        alias_resolution_sources=example.get("alias_resolution_sources"),
        official_title=example.get("official_title") or title,
        source_roles=source_roles,
    )
    return proof_mode is not None


def slang_db_alias_seed_is_safe(title: Any, entry: Dict[str, Any], bucket: Dict[str, Any]) -> bool:
    """Return whether a persisted slang entry may seed batch-memory alias recall."""
    title_raw = str(title or "").strip()
    term_raw = str((entry or {}).get("term") or "").strip()
    if (
        not title_raw
        or not term_raw
        or _is_generic_term(term_raw)
        or _is_generic_title_label(title_raw)
        or _looks_sentence_like_term(term_raw)
        or _is_exact_title_alias(term_raw, title_raw)
    ):
        return False
    examples = (bucket or {}).get("examples") or []
    if not isinstance(examples, list):
        return False
    title_norm = _normalize_title(title_raw)
    term_norm = _normalize_term(term_raw)
    matching_examples = [
        ex
        for ex in examples
        if isinstance(ex, dict)
        and _normalize_title(str(ex.get("official_title") or "")) == title_norm
        and _normalize_term(str(ex.get("alias") or "")) == term_norm
    ]
    if not matching_examples:
        return False
    clean_examples = [
        ex for ex in matching_examples
        if not _example_has_polluted_alias_seed_signal(ex)
    ]
    if not clean_examples:
        return False
    return any(
        _example_has_verified_alias_write_contract(
            title_raw,
            term_raw,
            ex,
            fallback_source_roles=(entry or {}).get("sources"),
        )
        for ex in clean_examples
    )


def _is_title_candidate_only_roles(raw_roles: Any, raw_role: Any = None) -> bool:
    roles = _normalized_source_roles(raw_roles, raw_role)
    return bool(roles) and roles <= {"title_candidate"}


def _has_strong_work_roles(raw_roles: Any, raw_role: Any = None, bucket: Any = None) -> bool:
    roles = _normalized_source_roles(raw_roles, raw_role)
    if roles & {"primary_work", "slang_insight"}:
        return True
    return str(bucket or "").strip().lower() == "slang"


def _empty_title_bucket() -> Dict[str, Any]:
    return {
        "raw_titles": [],
        "slang": [],
        "pending": [],
        "conflicts": [],
        "examples": [],
        "updated_at": None,
    }


def _empty_family_alias_bucket(term: str = "") -> Dict[str, Any]:
    raw = str(term or "").strip()
    return {
        "term": raw,
        "normalized_term": _normalize_term(raw),
        "variant_terms": [raw] if raw else [],
        "titles": [],
        "sources": [],
        "count": 0,
        "examples": [],
        "last_seen": None,
        "updated_at": None,
    }


def _normalize_bucket_shape(title: str, bucket: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    bucket = bucket if isinstance(bucket, dict) else {}
    raw_titles = bucket.get("raw_titles")
    if isinstance(raw_titles, str):
        raw_title_list = [raw_titles]
    elif isinstance(raw_titles, list):
        raw_title_list = [str(x).strip() for x in raw_titles if str(x).strip()]
    else:
        raw_title_list = []
    if str(title).strip():
        raw_title_list.append(str(title).strip())
    return {
        "raw_titles": sorted({x for x in raw_title_list if x}),
        "slang": list(bucket.get("slang") or []),
        "pending": list(bucket.get("pending") or []),
        "conflicts": list(bucket.get("conflicts") or []),
        "examples": list(bucket.get("examples") or []),
        "updated_at": bucket.get("updated_at"),
    }


def _normalize_family_alias_shape(term: str, bucket: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    bucket = bucket if isinstance(bucket, dict) else {}
    raw = str(term or bucket.get("term") or "").strip()
    variant_terms_raw = bucket.get("variant_terms")
    if isinstance(variant_terms_raw, str):
        variant_terms = [variant_terms_raw]
    elif isinstance(variant_terms_raw, list):
        variant_terms = [str(x).strip() for x in variant_terms_raw if str(x).strip()]
    else:
        variant_terms = []
    if raw:
        variant_terms.append(raw)
    titles_raw = bucket.get("titles")
    if isinstance(titles_raw, str):
        titles = [titles_raw]
    elif isinstance(titles_raw, list):
        titles = [str(x).strip() for x in titles_raw if str(x).strip()]
    else:
        titles = []
    sources_raw = bucket.get("sources")
    if isinstance(sources_raw, str):
        sources = [sources_raw]
    elif isinstance(sources_raw, list):
        sources = [str(x).strip() for x in sources_raw if str(x).strip()]
    else:
        sources = []
    display_term = min(variant_terms, key=len) if variant_terms else raw
    normalized_term = _normalize_term(display_term or raw)
    return {
        "term": display_term,
        "normalized_term": normalized_term,
        "variant_terms": sorted({x for x in variant_terms if x}),
        "titles": sorted({x for x in titles if x}),
        "sources": sorted({x for x in sources if x}),
        "count": int(bucket.get("count") or 0),
        "examples": list(bucket.get("examples") or []),
        "last_seen": bucket.get("last_seen"),
        "updated_at": bucket.get("updated_at"),
    }


def _empty_db() -> Dict[str, Any]:
    return {
        "version": 2,
        "updated_at": None,
        "titles": {},
        "family_aliases": {},
    }


class SlangDBManager:
    def __init__(
        self,
        *,
        path: Path,
        run_id: str,
        enabled: bool = False,
        flush_posts: int = 1,
        flush_seconds: int = 0,
        max_examples_per_title: int = 30,
        log_fn: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.path = Path(path)
        self.run_id = str(run_id or "").strip() or "unknown"
        self.enabled = bool(enabled)
        self.flush_posts = max(1, int(flush_posts))
        self.flush_seconds = max(0, int(flush_seconds))
        self.max_examples_per_title = max(1, int(max_examples_per_title))
        self.log_fn = log_fn
        self._db = self._load_db()
        self._processed_since_flush = 0
        self._observations_since_flush = 0
        self._touched_titles_since_flush: set[str] = set()
        self._observation_previews_since_flush: list[str] = []
        self._dirty = False
        self._last_flush_monotonic = time.monotonic()

    def _load_db(self) -> Dict[str, Any]:
        if not self.enabled:
            return _empty_db()
        source_path = self.path
        if not source_path.exists():
            legacy_path = self._legacy_path()
            if legacy_path is not None and legacy_path.exists():
                source_path = legacy_path
            else:
                return _empty_db()
        try:
            payload = json.loads(source_path.read_text(encoding="utf-8"))
        except Exception:
            return _empty_db()
        if not isinstance(payload, dict):
            return _empty_db()
        titles = payload.get("titles")
        if not isinstance(titles, dict):
            payload["titles"] = {}
        family_aliases = payload.get("family_aliases")
        if not isinstance(family_aliases, dict):
            payload["family_aliases"] = {}
        payload["version"] = max(int(payload.get("version") or 0), 2)
        payload.setdefault("updated_at", None)
        for title, bucket in list((payload.get("titles") or {}).items()):
            if not isinstance(bucket, dict):
                payload["titles"][title] = _empty_title_bucket()
                continue
            payload["titles"][title] = _normalize_bucket_shape(str(title), bucket)
        for term, bucket in list((payload.get("family_aliases") or {}).items()):
            if not isinstance(bucket, dict):
                payload["family_aliases"][term] = _empty_family_alias_bucket(str(term))
                continue
            payload["family_aliases"][term] = _normalize_family_alias_shape(str(term), bucket)
        return payload

    def _legacy_path(self) -> Optional[Path]:
        try:
            if self.path.name != "slang_db.json":
                return None
            if self.path.parent.name != "slang_db":
                return None
            legacy = self.path.parent.parent / "slang_db.json"
            if legacy.resolve() == self.path.resolve():
                return None
            return legacy
        except Exception:
            return None

    def record_result(self, full_result: Dict[str, Any]) -> None:
        if not self.enabled:
            return
        self._processed_since_flush += 1
        for obs in self._extract_observations(full_result):
            self._merge_observation(obs)
        self.maybe_flush()

    def maybe_flush(self) -> None:
        if not self.enabled or not self._dirty:
            return
        elapsed = time.monotonic() - self._last_flush_monotonic
        if self._processed_since_flush >= self.flush_posts:
            self.flush(force=True, reason=f"posts>={self.flush_posts}")
            return
        if self.flush_seconds > 0 and elapsed >= self.flush_seconds:
            self.flush(force=True, reason=f"seconds>={self.flush_seconds}")

    def flush(self, *, force: bool = False, reason: str = "manual") -> None:
        if not self.enabled:
            return
        if not self._dirty and not force:
            return
        buffered_posts = self._processed_since_flush
        buffered_observations = self._observations_since_flush
        touched_titles = sorted(self._touched_titles_since_flush)
        previews = list(self._observation_previews_since_flush)
        self._rebuild_conflicts()
        written_at = _now_iso()
        self._db["version"] = max(int(self._db.get("version") or 0), 2)
        self._db["updated_at"] = written_at
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp_path.write_text(
            json.dumps(self._db, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp_path.replace(self.path)
        self._log_flush(
            buffered_posts=buffered_posts,
            buffered_observations=buffered_observations,
            touched_titles=touched_titles,
            previews=previews,
            written_at=written_at,
            reason=reason,
        )
        self._processed_since_flush = 0
        self._observations_since_flush = 0
        self._touched_titles_since_flush.clear()
        self._observation_previews_since_flush.clear()
        self._dirty = False
        self._last_flush_monotonic = time.monotonic()

    def finalize(self) -> None:
        if not self.enabled:
            return
        self.flush(force=True, reason="finalize")

    @property
    def data(self) -> Dict[str, Any]:
        return self._db

    def _ensure_bucket(self, title: str) -> Dict[str, Any]:
        titles = self._db.setdefault("titles", {})
        if title not in titles or not isinstance(titles[title], dict):
            titles[title] = _empty_title_bucket()
        titles[title] = _normalize_bucket_shape(title, titles[title])
        bucket = titles[title]
        return bucket

    def _ensure_family_alias_bucket(self, term: str) -> Tuple[str, Dict[str, Any]]:
        family_aliases = self._db.setdefault("family_aliases", {})
        normalized = _normalize_term(term)
        if not normalized:
            key = str(term or "").strip()
            family_aliases[key] = _normalize_family_alias_shape(key, family_aliases.get(key))
            return key, family_aliases[key]

        for key, bucket in list(family_aliases.items()):
            bucket_norm = _normalize_term((bucket or {}).get("normalized_term") or key)
            if bucket_norm == normalized:
                family_aliases[key] = _normalize_family_alias_shape(str(key), bucket)
                return key, family_aliases[key]

        key = str(term or "").strip() or normalized
        family_aliases[key] = _empty_family_alias_bucket(key)
        family_aliases[key] = _normalize_family_alias_shape(key, family_aliases[key])
        return key, family_aliases[key]

    def _remove_alias_from_title_buckets(self, normalized_term: str) -> None:
        if not normalized_term:
            return
        titles = self._db.setdefault("titles", {})
        for title, bucket in list(titles.items()):
            if not isinstance(bucket, dict):
                continue
            bucket["slang"] = [
                item
                for item in (bucket.get("slang") or [])
                if _normalize_term(item.get("normalized_term") or item.get("term")) != normalized_term
            ]
            bucket["pending"] = [
                item
                for item in (bucket.get("pending") or [])
                if _normalize_term(item.get("normalized_term") or item.get("term")) != normalized_term
            ]
            bucket["conflicts"] = [
                item
                for item in (bucket.get("conflicts") or [])
                if _normalize_term(item.get("normalized_term") or item.get("term")) != normalized_term
            ]
            titles[title] = _normalize_bucket_shape(title, bucket)

    def _merge_family_alias_observation(self, obs: Dict[str, Any]) -> None:
        term = str(obs.get("term") or "").strip()
        if not term:
            return
        title = str(obs.get("official_title") or "").strip()
        normalized_term = _normalize_term(term)
        if not normalized_term:
            return

        key, bucket = self._ensure_family_alias_bucket(term)
        variant_terms = set(str(x).strip() for x in (bucket.get("variant_terms") or []) if str(x).strip())
        variant_terms.add(term)
        bucket["variant_terms"] = sorted(variant_terms)
        bucket["term"] = min(bucket["variant_terms"], key=len) if bucket["variant_terms"] else term
        bucket["normalized_term"] = normalized_term
        if title:
            titles = set(str(x).strip() for x in (bucket.get("titles") or []) if str(x).strip())
            titles.add(title)
            bucket["titles"] = sorted(titles)
        bucket["count"] = int(bucket.get("count") or 0) + 1
        bucket["last_seen"] = obs.get("seen_at") or _now_iso()
        sources = set(str(x).strip() for x in (bucket.get("sources") or []) if str(x).strip())
        sources.update(str(x).strip() for x in (obs.get("sources") or []) if str(x).strip())
        bucket["sources"] = sorted(sources)

        example = dict(obs.get("example") or {})
        if example:
            examples = bucket.get("examples") or []
            example_key = (
                str(example.get("post_id") or ""),
                normalized_term,
                str(example.get("official_title") or "").strip(),
            )
            if not any(
                (
                    str(e.get("post_id") or ""),
                    _normalize_term(e.get("alias") or ""),
                    str(e.get("official_title") or "").strip(),
                ) == example_key
                for e in examples
            ):
                examples.append(example)
                if len(examples) > self.max_examples_per_title:
                    del examples[:-self.max_examples_per_title]
            bucket["examples"] = examples

        bucket["updated_at"] = obs.get("seen_at") or _now_iso()
        self._db.setdefault("family_aliases", {})[key] = _normalize_family_alias_shape(key, bucket)
        self._remove_alias_from_title_buckets(normalized_term)
        self._observations_since_flush += 1
        self._touched_titles_since_flush.add(f"family_alias:{key}")
        self._dirty = True

    def _merge_observation(self, obs: Dict[str, Any]) -> None:
        title = str(obs.get("official_title") or "").strip()
        term = str(obs.get("term") or "").strip()
        bucket_name = str(obs.get("bucket") or "").strip().lower()
        self._remember_observation_preview(obs)
        if bucket_name == "family_alias":
            self._merge_family_alias_observation(obs)
            return
        if not title or not term:
            return
        bucket = self._ensure_bucket(title)
        target_key = "slang" if obs.get("bucket") == "slang" else "pending"
        entries = bucket[target_key]
        normalized_term = _normalize_term(term)
        if not normalized_term:
            return

        existing = None
        for entry in entries:
            if _normalize_term(entry.get("normalized_term") or entry.get("term")) == normalized_term:
                existing = entry
                break

        if existing is None:
            existing = {
                "term": term,
                "normalized_term": normalized_term,
                "count": 0,
                "sources": [],
                "last_seen": None,
            }
            entries.append(existing)

        existing["term"] = term if len(term) >= len(str(existing.get("term") or "")) else existing.get("term")
        existing["count"] = int(existing.get("count") or 0) + 1
        existing["last_seen"] = obs.get("seen_at") or _now_iso()
        existing_sources = {str(x) for x in (existing.get("sources") or []) if str(x).strip()}
        existing_sources.update(str(x) for x in (obs.get("sources") or []) if str(x).strip())
        existing["sources"] = sorted(existing_sources)
        if target_key == "pending":
            existing["pending_kind"] = str(obs.get("pending_kind") or existing.get("pending_kind") or _PENDING_KIND_REFERENCE_MENTION)
            existing["pending_reason"] = str(obs.get("pending_reason") or existing.get("pending_reason") or "").strip() or None
            existing["classification_confidence"] = str(
                obs.get("classification_confidence") or existing.get("classification_confidence") or "low"
            ).strip().lower()
            evidence_roles = {
                str(x).strip()
                for x in (existing.get("evidence_roles") or [])
                if str(x).strip()
            }
            evidence_roles.update(str(x).strip() for x in (obs.get("sources") or []) if str(x).strip())
            existing["evidence_roles"] = sorted(evidence_roles)
        if target_key == "slang":
            bucket["pending"] = [
                item
                for item in (bucket.get("pending") or [])
                if _normalize_term(item.get("normalized_term") or item.get("term")) != normalized_term
            ]
        raw_titles = bucket.get("raw_titles")
        if isinstance(raw_titles, str):
            raw_titles = [raw_titles]
        elif not isinstance(raw_titles, list):
            raw_titles = []
        if title not in raw_titles:
            raw_titles.append(title)
        bucket["raw_titles"] = sorted({str(x).strip() for x in raw_titles if str(x).strip()})
        bucket = _normalize_bucket_shape(title, bucket)
        self._db.setdefault("titles", {})[title] = bucket

        example = dict(obs.get("example") or {})
        if example:
            examples = bucket["examples"]
            example_key = (
                str(example.get("post_id") or ""),
                normalized_term,
                str(example.get("bucket") or target_key),
            )
            if not any(
                (
                    str(e.get("post_id") or ""),
                    _normalize_term(e.get("alias") or ""),
                    str(e.get("bucket") or ""),
                ) == example_key
                for e in examples
            ):
                examples.append(example)
                if len(examples) > self.max_examples_per_title:
                    del examples[:-self.max_examples_per_title]

        bucket["updated_at"] = obs.get("seen_at") or _now_iso()
        self._observations_since_flush += 1
        self._touched_titles_since_flush.add(title)
        self._dirty = True

    def _log_flush(
        self,
        *,
        buffered_posts: int,
        buffered_observations: int,
        touched_titles: List[str],
        previews: List[str],
        written_at: str,
        reason: str,
    ) -> None:
        if not self.log_fn:
            return
        title_preview = ", ".join(touched_titles[:5])
        if len(touched_titles) > 5:
            title_preview += f" ... (+{len(touched_titles) - 5})"
        if not title_preview:
            title_preview = "-"
        obs_preview = "; ".join(previews[:_FLUSH_PREVIEW_LIMIT])
        if len(previews) > _FLUSH_PREVIEW_LIMIT:
            obs_preview += f" ... (+{len(previews) - _FLUSH_PREVIEW_LIMIT})"
        if not obs_preview:
            obs_preview = "-"
        self.log_fn(
            "🗂️ Slang DB flush: "
            f"reason={reason}, buffered_posts={buffered_posts}, buffered_observations={buffered_observations}, "
            f"titles={len(touched_titles)} [{title_preview}], previews=[{obs_preview}], "
            f"written_at={written_at}, path={self.path}"
        )

    def _remember_observation_preview(self, obs: Dict[str, Any]) -> None:
        term = str(obs.get("term") or "").strip()
        title = str(obs.get("official_title") or "").strip()
        bucket = str(obs.get("bucket") or "").strip().lower() or "pending"
        if not term or not title:
            return
        preview = f"{term} -> {title} ({bucket})"
        if preview in self._observation_previews_since_flush:
            return
        self._observation_previews_since_flush.append(preview)
        if len(self._observation_previews_since_flush) > (_FLUSH_PREVIEW_LIMIT * 2):
            del self._observation_previews_since_flush[:-(_FLUSH_PREVIEW_LIMIT * 2)]

    def _rebuild_conflicts(self) -> None:
        titles = self._db.setdefault("titles", {})
        family_aliases = self._db.setdefault("family_aliases", {})
        self._prune_unreviewable_entries()
        for key, bucket in list(family_aliases.items()):
            normalized = _normalize_term((bucket or {}).get("normalized_term") or key)
            titles_list = [str(x).strip() for x in ((bucket or {}).get("titles") or []) if str(x).strip()]
            examples = list((bucket or {}).get("examples") or [])
            if not normalized or (not titles_list and not examples):
                family_aliases.pop(key, None)
                continue
            family_aliases[key] = _normalize_family_alias_shape(key, bucket)
        family_alias_norms = {
            _normalize_term((bucket or {}).get("normalized_term") or key)
            for key, bucket in family_aliases.items()
            if _normalize_term((bucket or {}).get("normalized_term") or key)
        }
        for title, bucket in list(titles.items()):
            if not isinstance(bucket, dict):
                continue
            for source_key in ("slang", "pending", "conflicts"):
                bucket[source_key] = [
                    item
                    for item in (bucket.get(source_key) or [])
                    if _normalize_term(item.get("normalized_term") or item.get("term")) not in family_alias_norms
                ]
            titles[title] = _normalize_bucket_shape(title, bucket)

        alias_map: Dict[str, List[Tuple[str, Dict[str, Any], str]]] = {}
        for title, bucket in titles.items():
            if not isinstance(bucket, dict):
                continue
            bucket["conflicts"] = []
            for source_key in ("slang", "pending"):
                for entry in (bucket.get(source_key) or []):
                    norm = _normalize_term(entry.get("normalized_term") or entry.get("term"))
                    if not norm or norm in family_alias_norms:
                        continue
                    alias_map.setdefault(norm, []).append((title, entry, source_key))
            for example in (bucket.get("examples") or []):
                if not isinstance(example, dict):
                    continue
                alias = str(example.get("alias") or "").strip()
                if (
                    not alias
                    or _is_generic_term(alias)
                    or _looks_sentence_like_term(alias)
                    or _is_exact_title_alias(alias, title)
                ):
                    continue
                norm = _normalize_term(alias)
                if not norm or norm in family_alias_norms:
                    continue
                alias_map.setdefault(norm, []).append(
                    (
                        title,
                        {
                            "term": alias,
                            "last_seen": example.get("seen_at") or bucket.get("updated_at"),
                        },
                        "example",
                    )
                )

        for norm_term, refs in list(alias_map.items()):
            title_names = sorted({title for title, _, _ in refs})
            confirmed_titles = {
                title
                for title, entry, source_key in refs
                if source_key == "slang" or str((entry or {}).get("bucket") or "").strip().lower() == "slang"
            }
            if len(title_names) < _FAMILY_ALIAS_AUTO_PROMOTE_MIN_TITLES:
                continue
            if len(confirmed_titles) < _FAMILY_ALIAS_AUTO_PROMOTE_MIN_CONFIRMED_TITLES:
                continue
            display_term = ""
            last_seen = ""
            sources = set()
            examples: List[Dict[str, Any]] = []
            for title, entry, source_key in refs:
                if source_key in {"slang", "pending"}:
                    bucket = titles.get(title) or {}
                    bucket["slang"] = [
                        item for item in (bucket.get("slang") or [])
                        if _normalize_term(item.get("normalized_term") or item.get("term")) != norm_term
                    ]
                    bucket["pending"] = [
                        item for item in (bucket.get("pending") or [])
                        if _normalize_term(item.get("normalized_term") or item.get("term")) != norm_term
                    ]
                    titles[title] = _normalize_bucket_shape(title, bucket)
                if not display_term:
                    display_term = str(entry.get("term") or "").strip()
                last_seen = max(last_seen, str(entry.get("last_seen") or ""))
                if source_key in {"slang", "pending"}:
                    sources.update(
                        str(x).strip()
                        for x in ((entry or {}).get("sources") or [])
                        if str(x).strip()
                    )
            for title in title_names:
                bucket = titles.get(title) or {}
                matched_examples = [
                    e for e in (bucket.get("examples") or [])
                    if _normalize_term(e.get("alias") or "") == norm_term
                ]
                examples.extend(matched_examples)
                for example in matched_examples:
                    src_role = str(example.get("source_role") or "").strip()
                    if src_role:
                        sources.add(src_role)
                    sources.update(
                        str(x).strip()
                        for x in (example.get("source_roles") or [])
                        if str(x).strip()
                    )

            key, family_bucket = self._ensure_family_alias_bucket(display_term or norm_term)
            family_bucket["titles"] = sorted({*list(family_bucket.get("titles") or []), *title_names})
            family_bucket["sources"] = sorted({*list(family_bucket.get("sources") or []), *sources})
            family_bucket["count"] = max(int(family_bucket.get("count") or 0), len(examples))
            family_bucket["last_seen"] = last_seen or family_bucket.get("last_seen") or _now_iso()
            merged_examples = list(family_bucket.get("examples") or [])
            for example in examples[-self.max_examples_per_title :]:
                example_key = (
                    str(example.get("post_id") or ""),
                    _normalize_term(example.get("alias") or ""),
                    str(example.get("official_title") or "").strip(),
                )
                if any(
                    (
                        str(e.get("post_id") or ""),
                        _normalize_term(e.get("alias") or ""),
                        str(e.get("official_title") or "").strip(),
                    ) == example_key
                    for e in merged_examples
                ):
                    continue
                merged_examples.append(example)
            if len(merged_examples) > self.max_examples_per_title:
                del merged_examples[:-self.max_examples_per_title]
            family_bucket["examples"] = merged_examples
            family_bucket["updated_at"] = family_bucket.get("last_seen")
            family_aliases[key] = _normalize_family_alias_shape(key, family_bucket)
            family_alias_norms.add(norm_term)
            alias_map.pop(norm_term, None)

        for norm_term, refs in alias_map.items():
            title_names = sorted({title for title, _, _ in refs})
            confirmed_titles = {
                title
                for title, entry, source_key in refs
                if source_key == "slang" or str((entry or {}).get("bucket") or "").strip().lower() == "slang"
            }
            if len(confirmed_titles) == 1:
                continue
            if len(title_names) <= 1:
                continue
            display_term = ""
            last_seen = ""
            for title, entry, source_key in refs:
                if source_key in {"slang", "pending"}:
                    bucket = titles.get(title) or {}
                    bucket["slang"] = [
                        item for item in (bucket.get("slang") or [])
                        if _normalize_term(item.get("normalized_term") or item.get("term")) != norm_term
                    ]
                    bucket["pending"] = [
                        item for item in (bucket.get("pending") or [])
                        if _normalize_term(item.get("normalized_term") or item.get("term")) != norm_term
                    ]
                if not display_term:
                    display_term = str(entry.get("term") or "").strip()
                last_seen = max(last_seen, str(entry.get("last_seen") or ""))

            for title in title_names:
                bucket = titles.get(title) or {}
                examples = [
                    e for e in (bucket.get("examples") or [])
                    if _normalize_term(e.get("alias") or "") == norm_term
                ]
                bucket["conflicts"] = [
                    item for item in (bucket.get("conflicts") or [])
                    if _normalize_term(item.get("normalized_term") or item.get("term")) != norm_term
                ]
                bucket["conflicts"].append(
                    {
                        "term": display_term or norm_term,
                        "normalized_term": norm_term,
                        "titles": title_names,
                        "post_ids": sorted(
                            {
                                int(e.get("post_id"))
                                for e in examples
                                if str(e.get("post_id") or "").isdigit()
                            }
                        ),
                        "examples": examples[-5:],
                        "last_seen": last_seen or _now_iso(),
                    }
                )

    def _prune_unreviewable_entries(self) -> None:
        titles = self._db.setdefault("titles", {})
        strong_titles_by_post: Dict[str, set[str]] = {}
        for title, bucket in list(titles.items()):
            if not isinstance(bucket, dict):
                continue
            for example in (bucket.get("examples") or []):
                if not isinstance(example, dict):
                    continue
                post_id = str(example.get("post_id") or "").strip()
                if not post_id:
                    continue
                if not _has_strong_work_roles(
                    example.get("source_roles"),
                    example.get("source_role"),
                    example.get("bucket"),
                ):
                    continue
                strong_titles_by_post.setdefault(post_id, set()).add(title)

        for title, bucket in list(titles.items()):
            if not isinstance(bucket, dict):
                continue
            examples = list(bucket.get("examples") or [])
            if not isinstance(examples, list):
                examples = []
            slang_entries = list(bucket.get("slang") or [])
            kept_slang: List[Dict[str, Any]] = []
            removed_slang_norms: set[str] = set()
            for entry in slang_entries:
                norm = _normalize_term(entry.get("normalized_term") or entry.get("term"))
                if not norm:
                    continue
                if _is_generic_term(entry.get("term") or entry.get("normalized_term")):
                    removed_slang_norms.add(norm)
                    continue
                matching_examples = [
                    e for e in examples
                    if _normalize_term(e.get("alias") or "") == norm
                ]
                if matching_examples and all(_example_has_polluted_alias_seed_signal(e) for e in matching_examples):
                    removed_slang_norms.add(norm)
                    continue
                kept_slang.append(entry)
            if removed_slang_norms:
                bucket["slang"] = kept_slang
                bucket["examples"] = [
                    e for e in examples
                    if not (
                        _normalize_term(e.get("alias") or "") in removed_slang_norms
                        and str(e.get("bucket") or "") == "slang"
                    )
                ]
                examples = list(bucket.get("examples") or [])
                bucket["updated_at"] = _now_iso()
            pending_entries = list(bucket.get("pending") or [])
            slang_norms = {
                _normalize_term(item.get("normalized_term") or item.get("term"))
                for item in (bucket.get("slang") or [])
                if _normalize_term(item.get("normalized_term") or item.get("term"))
            }
            kept_pending: List[Dict[str, Any]] = []
            removed_norms: set[str] = set()

            for entry in pending_entries:
                norm = _normalize_term(entry.get("normalized_term") or entry.get("term"))
                if not norm:
                    continue
                if _is_generic_term(entry.get("term") or entry.get("normalized_term")):
                    removed_norms.add(norm)
                    continue
                if norm in slang_norms:
                    removed_norms.add(norm)
                    continue
                matching_examples = [
                    e for e in examples
                    if _normalize_term(e.get("alias") or "") == norm
                ]
                if matching_examples and not any(_example_is_reviewable(e) for e in matching_examples):
                    removed_norms.add(norm)
                    continue
                if matching_examples and all(_example_has_polluted_alias_seed_signal(e) for e in matching_examples):
                    removed_norms.add(norm)
                    continue
                if matching_examples and all(
                    _is_title_candidate_only_roles(e.get("source_roles"), e.get("source_role"))
                    for e in matching_examples
                ):
                    if any(
                        any(other_title != title for other_title in strong_titles_by_post.get(str(e.get("post_id") or "").strip(), set()))
                        for e in matching_examples
                    ):
                        removed_norms.add(norm)
                        continue
                kept_pending.append(entry)

            if removed_norms:
                bucket["pending"] = kept_pending
                bucket["examples"] = [
                    e for e in examples
                    if not (
                        _normalize_term(e.get("alias") or "") in removed_norms
                        and str(e.get("bucket") or "") == "pending"
                    )
                ]
                bucket["updated_at"] = _now_iso()

            if not (bucket.get("slang") or bucket.get("pending") or bucket.get("conflicts") or bucket.get("examples")):
                titles.pop(title, None)

    def _extract_observations(self, full_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        result_dict = ((full_result or {}).get("analysis_result") or {})
        if not isinstance(result_dict, dict):
            return []
        identity = result_dict.get("identity") or {}
        if not isinstance(identity, dict):
            return []

        topicality = str(identity.get("topicality") or "").strip().lower()
        subtype = str(identity.get("subtype") or "").strip().lower()
        work_resolution = str(identity.get("work_resolution") or "").strip().lower()
        anchor_type = str(identity.get("anchor_type") or "").strip().lower()
        anchor_strength = str(identity.get("anchor_strength") or "").strip()
        discussion_type = str(identity.get("discussion_type") or "").strip()
        title_resolution_state = str(identity.get("title_resolution_state") or "").strip().lower()
        title_resolution_allowed = identity.get("title_resolution_allowed")
        consistency_flags = _normalized_consistency_flags(identity.get("consistency_flags"))
        novel_identity = identity.get("novel_identity") or {}
        if not isinstance(novel_identity, dict):
            novel_identity = {}
        official_title = str(novel_identity.get("official_title") or "").strip()
        heretic_url = str(novel_identity.get("heretic_url") or "").strip()
        confidence = str(novel_identity.get("confidence") or "").strip()
        reason = str(identity.get("reason") or "")
        slang_insight = identity.get("slang_insight") or {}
        if not isinstance(slang_insight, dict):
            slang_insight = {}
        slang_detected_term = str(slang_insight.get("detected_term") or "").strip()
        slang_canonical_alias = str(slang_insight.get("canonical_work_alias") or "").strip()
        slang_decoded_term = str(slang_insight.get("decoded_term") or "").strip()
        slang_alias_scope = str(slang_insight.get("alias_scope") or "").strip().lower()
        slang_store_in_db = slang_insight.get("store_in_slang_db")
        slang_store_reason = str(slang_insight.get("store_reason") or "").strip().lower()
        slang_contract_write_eligible = bool(
            slang_store_in_db is True
            and slang_insight.get("decode_verified") is True
            and slang_alias_scope == "pure_work_alias"
            and slang_store_reason == "pure_work_alias"
            and slang_detected_term
            and slang_canonical_alias
            and slang_decoded_term
            and _normalize_term(slang_detected_term) == _normalize_term(slang_canonical_alias)
            and (
                not official_title
                or _normalize_title(slang_decoded_term) == _normalize_title(official_title)
            )
        )
        is_reviewable_context = _is_reviewable_context(
            topicality=topicality,
            subtype=subtype,
            work_resolution=work_resolution,
            discussion_type=discussion_type,
            anchor_type=anchor_type,
        )
        if not is_reviewable_context:
            return []

        is_confirmable = bool(
            topicality == "core_relevant"
            and work_resolution == "resolved"
            and official_title
            and subtype not in {
                "author_meta",
                "platform_meta",
                "release_serialization_meta",
                "recommendation_request",
                "genre_trope_discussion",
                "community_work_banter",
                "multi_work_compare",
            }
            and (
                bool(heretic_url)
                or "official_title_evidence: true" in reason.lower()
                or anchor_type in {"title_exact", "title_alias", "character", "image"}
            )
        )
        reason_l = reason.lower()
        zero_public_evidence_signal = bool(
            "evidence_bucket: post_spans=0, search_snippets=0, official_urls=0" in reason_l
            or "evidence bucket: post_spans=0, search_snippets=0, official_urls=0" in reason_l
        )
        weak_grounding_signal = bool(
            "grounding_anchor: none" in reason_l
            or "grounding_anchor: search_only" in reason_l
            or "anchor=none" in reason_l
        )
        critical_negative_signal = bool(
            "critical" in reason_l
            or "thematic_overlap_only" in reason_l
            or "no specific work" in reason_l
            or "no direct work" in reason_l
            or "특정 작품" in reason
        )
        late_rescue_contaminated = bool(
            consistency_flags
            & {
                "batch_memory_exact_alias_rescued",
                "title_surface_primary_candidate_rescued",
            }
            and (
                zero_public_evidence_signal
                or consistency_flags
                & {
                    "notes_demoted_for_unresolved",
                    "primary_work_cleared_non_core",
                    "primary_work_cleared_non_resolved",
                }
            )
            and weak_grounding_signal
            and critical_negative_signal
        )
        unresolvable_memory_query_context = _is_unresolvable_memory_query_context(
            title_resolution_state=title_resolution_state,
            title_resolution_allowed=title_resolution_allowed,
            subtype=subtype,
            work_resolution=work_resolution,
            discussion_type=discussion_type,
        )
        if unresolvable_memory_query_context:
            return []

        seen_at = _now_iso()
        example_base = {
            "post_id": full_result.get("post_id"),
            "run_id": self.run_id,
            "topicality": topicality or None,
            "subtype": subtype or None,
            "work_resolution": work_resolution or None,
            "confidence": confidence or None,
            "anchor_type": anchor_type or None,
            "anchor_strength": anchor_strength or None,
            "created_at": full_result.get("created_at"),
            "discussion_type": discussion_type or None,
            "title_resolution_state": title_resolution_state or None,
            "title_resolution_allowed": title_resolution_allowed,
            "consistency_flags": sorted(consistency_flags) if consistency_flags else None,
            "slang_detected_term": slang_detected_term or None,
            "slang_decoded_term": slang_decoded_term or None,
            "slang_decode_verified": slang_insight.get("decode_verified"),
            "slang_canonical_alias": slang_canonical_alias or None,
            "slang_alias_scope": slang_alias_scope or None,
            "slang_store_in_db": slang_store_in_db,
            "slang_store_reason": slang_store_reason or None,
            "alias_resolution_sources": (
                novel_identity.get("alias_resolution_sources")
                if isinstance(novel_identity.get("alias_resolution_sources"), list)
                else None
            ),
        }
        family_alias_signal = bool(
            consistency_flags & {
                "family_alias_precision_hold",
                "family_alias_group_unresolved",
                "family_alias_announcement_unresolved",
            }
        )

        slang_fallback_title = ""
        slang_fallback_source_tier = ""
        allow_pending_slang_insight = bool(
            not official_title
            and topicality == "core_relevant"
            and work_resolution in {"resolved", "unresolved"}
            and subtype not in {
                "author_meta",
                "platform_meta",
                "release_serialization_meta",
                "recommendation_request",
                "genre_trope_discussion",
                "community_work_banter",
                "multi_work_compare",
            }
            and discussion_type not in {"noise", "author_talk", "meta", "undecodable_reference"}
        )
        entity_tail_terms: List[str] = []
        for mention in (identity.get("entity_mentions") or []):
            if not isinstance(mention, dict):
                continue
            mention_type = str(mention.get("entity_type") or "").strip().lower()
            mention_role = str(mention.get("role") or "").strip().lower()
            if mention_type not in {"character", "author"} and mention_role not in {"character_focus", "author_focus"}:
                continue
            mention_text = str(mention.get("text") or "").strip()
            if mention_text:
                entity_tail_terms.append(mention_text)
        entity_tail_terms = list(dict.fromkeys(entity_tail_terms))
        blocked_surface_norms: set[str] = set()
        detected_surface_norm = _normalize_term(slang_detected_term)
        canonical_surface_norm = _normalize_term(slang_canonical_alias)
        slang_surface_norms = {norm for norm in (detected_surface_norm, canonical_surface_norm) if norm}
        if slang_store_in_db is False:
            blocked_surface_norms.add(detected_surface_norm)
        malformed_explicit_store_value = bool(
            slang_store_in_db is not None and type(slang_store_in_db) is not bool
        )
        invalid_explicit_store_contract = bool(
            malformed_explicit_store_value
            or (slang_store_in_db is True and not slang_contract_write_eligible)
        )
        if invalid_explicit_store_contract:
            blocked_surface_norms.update(slang_surface_norms)
        alias_resolution_sources = novel_identity.get("alias_resolution_sources")

        refs: Dict[Tuple[str, str], Dict[str, Any]] = {}

        def _append_ref(
            source_role: str,
            title: Any,
            term: Any,
            *,
            confidence_hint: Any = None,
            source_tier: Any = None,
            decoded_term_hint: Any = None,
        ) -> None:
            title_raw = str(title or "").strip()
            term_raw = str(term or "").strip()
            term_norm = _normalize_term(term_raw)
            if source_role in _REFERENCE_ONLY_ALIAS_ROLES:
                # reference/candidate 보존은 결과 CandidateLedger의 책임이다. 별칭 관계를
                # 직접 증명하지 않는 주변 작품 후보는 Slang DB mutation으로 번역하지 않는다.
                return
            if (
                late_rescue_contaminated
                and source_role in {"slang_insight", "primary_work", "title_candidate"}
            ):
                return
            if invalid_explicit_store_contract and source_role in {
                "slang_insight",
                "primary_work",
                "title_candidate",
            }:
                # true 계약 불완전 또는 non-bool store 값이면 상관 alias 전체를 fail-close한다.
                return
            if (
                unresolvable_memory_query_context
                and source_role in {
                    "mentioned_work",
                    "secondary_reference",
                    "recommendation_candidate",
                    "comparison_target",
                }
            ):
                return
            if (
                not title_raw
                or not term_raw
                or _is_generic_term(term_raw)
                or _is_generic_title_label(title_raw)
                or _looks_sentence_like_term(term_raw)
                or _is_exact_title_alias(term_raw, title_raw)
            ):
                return
            if term_norm in blocked_surface_norms:
                return
            if (
                slang_store_in_db is False
                and canonical_surface_norm
                and term_norm == canonical_surface_norm
                and source_role not in {"primary_work", "title_candidate"}
            ):
                # composite raw surface의 clean canonical alias는 독립 작품 후보 경로에서만
                # exact-pair 증명을 다시 통과시킨다. reference 우회에는 사용하지 않는다.
                return
            if source_role == "slang_insight" and _looks_mixed_entity_slang(
                term_raw,
                title_raw,
                decoded_term_hint,
            ):
                return
            if source_role in {"slang_insight", "primary_work", "title_candidate"} and _looks_title_plus_entity_alias(
                term_raw,
                title_raw,
                entity_tail_terms,
            ):
                return
            if (
                not official_title
                and consistency_flags & {
                    "verifier_title_repromotion_veto",
                    "canonical_title_blocked",
                }
                and source_role in {"slang_insight", "primary_work", "title_candidate"}
            ):
                return
            proof_mode = _verified_alias_pair_proof_mode(
                title_raw,
                term_raw,
                store_in_db=slang_store_in_db,
                decode_verified=slang_insight.get("decode_verified"),
                alias_scope=slang_alias_scope,
                store_reason=slang_store_reason,
                detected_term=slang_detected_term,
                canonical_alias=slang_canonical_alias,
                decoded_term=slang_decoded_term,
                consistency_flags=consistency_flags,
                alias_resolution_sources=alias_resolution_sources,
                official_title=official_title,
                source_roles={source_role},
            )
            if proof_mode is None:
                # abbreviation_match_score는 후보 구조 유사도일 뿐 alias 관계 증명이 아니다.
                # 검증된 exact pair가 아니면 confirmed/pending 어느 버킷에도 기록하지 않는다.
                return
            key = (_normalize_title(title_raw), _normalize_term(term_raw))
            existing = refs.get(key)
            if existing is None:
                refs[key] = {
                    "title": title_raw,
                    "term": term_raw,
                    "sources": {source_role},
                    "family_alias": bool(
                        family_alias_signal
                        and source_role in {"slang_insight", "primary_work", "title_candidate"}
                    ),
                }
                return
            if len(term_raw) >= len(str(existing.get("term") or "")):
                existing["term"] = term_raw
            if len(title_raw) >= len(str(existing.get("title") or "")):
                existing["title"] = title_raw
            existing["sources"].add(source_role)
            existing["family_alias"] = bool(
                existing.get("family_alias")
                or (
                    family_alias_signal
                    and source_role in {"slang_insight", "primary_work", "title_candidate"}
                )
            )

        def _iter_title_objs(raw: Any) -> List[Dict[str, Any]]:
            if isinstance(raw, dict):
                return [raw]
            if isinstance(raw, list):
                return [x for x in raw if isinstance(x, dict)]
            return []

        if allow_pending_slang_insight:
            decoded_term = str(slang_insight.get("decoded_term") or "").strip()
            for obj in _iter_title_objs(identity.get("primary_work")) + _iter_title_objs(identity.get("title_candidates")):
                cand_title = str((obj or {}).get("official_title") or "").strip()
                if not cand_title or _is_generic_title_label(cand_title):
                    continue
                if decoded_term and _normalize_title(decoded_term) != _normalize_title(cand_title):
                    continue
                slang_fallback_title = cand_title
                slang_fallback_source_tier = str((obj or {}).get("source_tier") or "").strip()
                break

        slang_term_for_storage = slang_canonical_alias or slang_detected_term
        if (official_title or slang_fallback_title) and slang_term_for_storage and slang_contract_write_eligible:
            _append_ref(
                "slang_insight",
                official_title or slang_fallback_title or slang_insight.get("decoded_term"),
                slang_term_for_storage,
                confidence_hint=confidence or slang_insight.get("confidence"),
                source_tier="verified" if official_title else (slang_fallback_source_tier or "pending"),
                decoded_term_hint=slang_insight.get("decoded_term"),
            )

        for obj in _iter_title_objs(identity.get("primary_work")):
            _append_ref(
                "primary_work",
                obj.get("official_title") or official_title,
                obj.get("alias_or_mention"),
                confidence_hint=obj.get("confidence") or confidence,
                source_tier=obj.get("source_tier"),
            )
        for obj in _iter_title_objs(identity.get("title_candidates")):
            _append_ref(
                "title_candidate",
                obj.get("official_title"),
                obj.get("alias_or_mention"),
                confidence_hint=obj.get("confidence") or confidence,
                source_tier=obj.get("source_tier"),
            )
        for obj in _iter_title_objs(identity.get("mentioned_works")):
            _append_ref(
                "mentioned_work",
                obj.get("official_title"),
                obj.get("alias_or_mention"),
                confidence_hint=obj.get("confidence") or confidence,
                source_tier=obj.get("source_tier"),
            )
        for obj in _iter_title_objs(identity.get("secondary_reference_works")):
            _append_ref(
                "secondary_reference",
                obj.get("official_title"),
                obj.get("alias_or_mention"),
                confidence_hint=obj.get("confidence") or confidence,
                source_tier=obj.get("source_tier"),
            )
        for obj in _iter_title_objs(identity.get("recommendation_candidates")):
            _append_ref(
                "recommendation_candidate",
                obj.get("official_title"),
                obj.get("alias_or_mention"),
                confidence_hint=obj.get("confidence") or confidence,
                source_tier=obj.get("source_tier"),
            )
        for obj in _iter_title_objs(identity.get("comparison_target")):
            _append_ref(
                "comparison_target",
                obj.get("official_title"),
                obj.get("alias_or_mention"),
                confidence_hint=obj.get("confidence") or confidence,
                source_tier=obj.get("source_tier"),
            )

        preferred_title_norms: set[str] = set()
        if official_title:
            official_title_norm = _normalize_title(official_title)
            if official_title_norm:
                preferred_title_norms.add(official_title_norm)
        preferred_title_norms.update(
            _normalize_title(str(ref.get("title") or "").strip())
            for ref in refs.values()
            if _normalized_source_roles(ref.get("sources")) & {"primary_work", "slang_insight"}
        )
        preferred_title_norms = {norm for norm in preferred_title_norms if norm}
        if preferred_title_norms:
            refs = {
                key: ref
                for key, ref in refs.items()
                if not (
                    _is_title_candidate_only_roles(ref.get("sources"))
                    and _normalize_title(str(ref.get("title") or "").strip()) not in preferred_title_norms
                )
            }

        observations: List[Dict[str, Any]] = []
        for ref in refs.values():
            title = str(ref.get("title") or "").strip()
            term = str(ref.get("term") or "").strip()
            source_roles = sorted(str(x) for x in (ref.get("sources") or set()) if str(x).strip())
            pending_kind = None
            pending_reason = None
            classification_confidence = None
            if ref.get("family_alias"):
                bucket = "family_alias"
            else:
                bucket = "slang" if (is_confirmable and _normalize_title(title) == _normalize_title(official_title)) else "pending"
                if bucket == "slang" and _should_hold_direct_slang_promotion(source_roles):
                    bucket = "pending"
                if bucket == "pending":
                    pending_kind, pending_reason, classification_confidence = _classify_pending_kind(
                        title=title,
                        source_roles=source_roles,
                        discussion_type=discussion_type,
                        subtype=subtype,
                        work_resolution=work_resolution,
                    )
            observations.append(
                {
                    "official_title": title,
                    "term": term,
                    "bucket": bucket,
                    "sources": source_roles,
                    "pending_kind": pending_kind,
                    "pending_reason": pending_reason,
                    "classification_confidence": classification_confidence,
                    "seen_at": seen_at,
                    "example": {
                        **example_base,
                        "alias": term,
                        "official_title": title,
                        "bucket": bucket,
                        "source_role": source_roles[0] if source_roles else None,
                        "source_roles": source_roles,
                        "pending_kind": pending_kind,
                        "pending_reason": pending_reason,
                        "classification_confidence": classification_confidence,
                    },
                }
            )

        return observations
