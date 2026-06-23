"""Candidate retention and title-promotion audit helpers.

Most audit fields are observational. A narrow promotion guard also demotes
obviously invalid official-title surfaces, such as URLs and platform domains,
while preserving candidate state for review.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any, Dict, Iterable, List, Optional


RECALL_TYPES = {"under_resolved", "under_resolved_false_negative"}
PRECISION_DEMOTION_TYPES = {
    "cross_media_or_famous_mismatch",
    "wrong_work",
    "over_resolved",
    "overresolved_generic_trope",
    "garbage_title",
}
PRECISION_REVIEW_TYPES = PRECISION_DEMOTION_TYPES | {
    "reason_evidence_mismatch",
}
PRECISION_TYPES = PRECISION_REVIEW_TYPES
CANDIDATE_PRESERVATION_TYPES = {
    "candidate_preservation_missing",
    "conflicting_or_multi_candidate",
    "comment_explicit_title_missed",
}
HYGIENE_TYPES = {
    "wrong_discussion_type",
    "wrong_relevance",
    "title_noisy_ocr",
    "heretic_url_null",
    "title_correct_url_mismatch",
    "url_mismatch",
    "reason_evidence_mismatch",
}
TROPE_OR_AUTHOR_HOLD_TYPES = {
    "trope_or_author_talk_risk",
}

NON_CORE_DISCUSSION_TYPES = {
    "author_talk",
    "recommendation",
    "meta",
    "trope_discussion",
    "community_banter",
    "genre_opinion",
    "image_post",
    "off_topic",
    "noise",
    "undecodable_reference",
}
CORE_DISCUSSION_TYPES = {
    "review",
    "spoiler",
    "anticipation",
    "meme",
    "character_talk",
    "general",
}
HOLD_STATES = {
    "unresolved_matchable",
    "unresolvable_memory_query",
    "context_only",
    "author_new_work_context",
    "ocr_explicit_title_unresolved",
    "multi_work",
    "adjacent",
    "technical_missing",
}
UNRESOLVED_WORK_STATES = {"unresolved", "multi_work"}
GENERIC_NON_TITLE_SURFACES = {"광고", "공지"}
PROMOTION_BLOCKING_OFFICIAL_TITLE_LINT_REASONS = {
    "official_title_looks_like_url_or_domain",
    "official_title_looks_like_generic_non_title_surface",
    "official_title_looks_like_search_snippet",
    "official_title_looks_like_breadcrumb",
}
WEAK_PRIMARY_SOURCE_TIERS = {"", "community", "llm_only", "search_only", "web"}
OFFICIAL_TITLE_SOURCE_TIERS = {"official_detail", "novel_platform"}
OFFICIAL_DETAIL_URL_RE = re.compile(
    r"(?i)"
    r"(?:novelpia\.com/novel/\d+|book\.novelpia\.com/novel/\d+|"
    r"(?:m\.)?novel\.munpia\.com/\d+|m\.munpia\.com/novel/detail/\d+|"
    r"(?:m|mm)\.munpia\.com/\?menu=novel&id=\d+|"
    r"page\.kakao\.com/content/\d+|"
    r"series\.naver\.com/novel/detail\.series\?productNo=\d+|"
    r"ridibooks\.com/books/\d+)"
)
NON_DETAIL_URL_RE = re.compile(
    r"(?i)/(?:viewer|episode|search|ranking|rank|author|fanart|community|review)(?:/|$)|"
    r"detailSearch|keyword=|tab_type=comment"
)
GENERIC_OFFICIAL_EVIDENCE_TITLES = {
    "노벨피아",
    "리디",
    "웹소설",
    "웹소설 문피아",
    "문피아 웹소설",
    "카카오페이지",
    "novel.munpia.com",
    "m.munpia.com",
    "mm.munpia.com",
}
LOW_INFORMATION_ALIAS_CLUES = {
    "app",
    "https",
    "official",
    "ts",
    "bl",
    "피폐",
    "하렘순애",
    "얀데레여왕",
    "아카데미",
    "마법소녀",
    "마법소년",
    "무협",
    "로판",
    "현판",
}
TITLE_TOKEN_STOPWORDS = {
    "웹소설",
    "소설",
    "작품",
    "작가",
    "무료",
    "독점",
    "완결",
    "plus",
    "플러스",
}
# Genre/descriptor surfaces that frequently double as a real work title (e.g. a
# novelpia work literally named "ts인방물"). A post that merely contains such a
# surface is almost always using it as a GENRE word, not a specific-work
# reference, so these must not be promoted via a weak post-surface anchor
# (full_title_surface / rare-token / bracket). A harder anchor (OCR explicit
# title, in-body work URL, or a confirmed alias mapping) may still recover them.
GENRE_DESCRIPTOR_SURFACES = {
    "인방물", "ts물", "ts인방물", "ts인방", "역하렘물", "하렘물", "회귀물", "빙의물",
    "환생물", "백합물", "bl물", "헌터물", "아카데미물", "던전물", "게임판타지",
    "양산형", "사이다물", "고구마물", "순애물", "피폐물", "로판", "현판", "무협",
    "무협물", "판타지", "현대판타지", "정통판타지", "ts물판", "ts인방",
}


def nested_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_str(value: Any) -> str:
    return str(value or "").strip()


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _judge_disagreement_type(judge_seed: Optional[Dict[str, Any]]) -> str:
    return _safe_str(nested_dict(judge_seed).get("disagreement_type"))


def _judge_seed_bucket(judge_seed: Optional[Dict[str, Any]]) -> str:
    return _safe_str(nested_dict(judge_seed).get("seed_bucket"))


def seed_group(disagreement_type: str, judge_seed: Optional[Dict[str, Any]] = None) -> str:
    bucket = _judge_seed_bucket(judge_seed)
    if bucket == "precision_identity_high":
        return "precision"
    if bucket == "source_url_hygiene":
        return "hygiene"
    if bucket == "candidate_comment_multi":
        return "candidate"
    if bucket == "recall_relevance_representative":
        return "recall"
    if disagreement_type in RECALL_TYPES:
        return "recall"
    if disagreement_type in PRECISION_DEMOTION_TYPES:
        return "precision"
    if disagreement_type in CANDIDATE_PRESERVATION_TYPES:
        return "candidate"
    if disagreement_type in HYGIENE_TYPES:
        return "hygiene"
    return "unseeded"


def official_title(identity: Dict[str, Any]) -> str:
    novel_identity = nested_dict(identity.get("novel_identity"))
    return _safe_str(
        novel_identity.get("official_title")
        or identity.get("official_title")
        or identity.get("official_novel_title")
    )


def candidate_name(item: Any) -> str:
    if isinstance(item, str):
        return item.strip()
    if not isinstance(item, dict):
        return ""
    return _safe_str(
        item.get("official_title")
        or item.get("title")
        or item.get("name")
        or item.get("surface")
        or item.get("decoded_term")
        or item.get("alias_or_mention")
    )


def _weak_image_title_allowed(identity: Dict[str, Any], item: Dict[str, Any]) -> bool:
    if item.get("promotion_eligible") is True:
        return True
    role = _safe_str(item.get("title_role")).lower()
    if role in {"work_title", "title"}:
        return True
    state = _safe_str(identity.get("title_resolution_state")).lower()
    anchor_type = _safe_str(identity.get("anchor_type")).lower()
    contexts = {
        _safe_str(value).lower()
        for value in _safe_list(identity.get("context_sources"))
        if _safe_str(value)
    }
    return (
        state == "ocr_explicit_title_unresolved"
        or anchor_type == "image"
        or "image" in contexts
        or "ocr" in contexts
    )


def _image_candidate_name(identity: Dict[str, Any], item: Dict[str, Any]) -> str:
    if not _weak_image_title_allowed(identity, item):
        return ""
    name = candidate_name(
        {
            "title": item.get("explicit_work_title")
            or item.get("detected_title")
            or item.get("work_title")
        }
    )
    if not name:
        return ""
    compact = _compact_title(name)
    if len(compact) < 2:
        return ""
    if name in GENERIC_NON_TITLE_SURFACES or _looks_like_url_or_domain(name):
        return ""
    return name


def _image_work_cue_candidates(identity: Dict[str, Any], item: Dict[str, Any]) -> List[str]:
    if official_title(identity):
        return []
    evidence_type = _safe_str(item.get("evidence_type")).lower()
    if evidence_type not in {"explicit_text", "ocr", "text_surface"}:
        return []
    cues = item.get("work_cues")
    if not isinstance(cues, list):
        return []
    state = _safe_str(identity.get("title_resolution_state")).lower()
    work_resolution = _safe_str(identity.get("work_resolution")).lower()
    topicality = _safe_str(identity.get("topicality")).lower()
    if not (
        state in HOLD_STATES
        or work_resolution in UNRESOLVED_WORK_STATES
        or topicality in {"adjacent_relevant", "related"}
        or (
            identity.get("is_novel_related") is True
            and identity.get("is_resolved_work_discussion") is not True
        )
    ):
        return []

    names: List[str] = []
    for cue in cues:
        name = candidate_name(cue)
        if not name:
            continue
        compact = _compact_title(name)
        if len(compact) < 4:
            continue
        if name in GENERIC_NON_TITLE_SURFACES or _looks_like_url_or_domain(name):
            continue
        if _image_work_cue_surface_is_context_only(name, item):
            continue
        if name not in names:
            names.append(name)
    return names


def _image_work_cue_surface_is_context_only(name: str, item: Dict[str, Any]) -> bool:
    role = _safe_str(item.get("title_role")).lower()
    if role in {"author_name", "character_name", "episode_title", "item_name", "background_listing"}:
        return True
    normalized = _safe_str(name)
    compact = _compact_title(normalized)
    lower = normalized.lower()
    if not compact:
        return True
    explicit_title = _safe_str(
        item.get("explicit_work_title") or item.get("detected_title") or item.get("work_title")
    )
    if explicit_title and _titles_match(normalized, explicit_title):
        return False
    author = _safe_str(item.get("explicit_author_name") or item.get("author_name"))
    if author and _titles_match(normalized, author):
        return True
    context_tokens = (
        "kakaopage",
        "카카오페이지",
        "카카페",
        "novelpia",
        "노벨피아",
        "munpia",
        "문피아",
        "naver",
        "네이버",
        "series",
        "시리즈",
        "조아라",
        "리디",
        "작가",
        "저자",
        "글",
        "그림",
        "일러스트",
        "삽화",
        "표지",
        "썸네일",
        "스크린샷",
        "랭킹",
        "순위",
        "조회",
        "추천",
        "별점",
        "댓글",
        "회차",
        "무료",
        "독점",
        "연재",
        "완결",
        "업데이트",
        "홈",
        "앱",
        "ui",
    )
    if any(token in lower for token in context_tokens):
        return True
    if re.search(r"\d[\d,.]*\s*(?:만|천|백)?\s*(?:조회|추천|댓글|화|회|위|점)", normalized):
        return True
    if re.fullmatch(r"[@#]?\w{1,12}", normalized) and not re.search(r"[가-힣]", normalized):
        return True
    return False


def _entity_hold_candidate_allowed(identity: Dict[str, Any]) -> bool:
    if official_title(identity):
        return False
    state = _safe_str(identity.get("title_resolution_state")).lower()
    work_resolution = _safe_str(identity.get("work_resolution")).lower()
    topicality = _safe_str(identity.get("topicality")).lower()
    if state in HOLD_STATES or work_resolution in UNRESOLVED_WORK_STATES:
        return True
    return topicality in {"adjacent_relevant", "related"}


def _entity_hold_candidate_name(identity: Dict[str, Any], item: Dict[str, Any]) -> str:
    if not _entity_hold_candidate_allowed(identity):
        return ""
    entity_type = _safe_str(item.get("entity_type")).lower()
    role = _safe_str(item.get("role")).lower()
    confidence = _safe_str(item.get("confidence")).lower()
    if confidence in {"low", "none"}:
        return ""
    if entity_type not in {"work", "title", "character"} and role not in {
        "character_focus",
        "work_focus",
        "primary",
    }:
        return ""
    name = _safe_str(item.get("canonical_value") or item.get("text") or item.get("surface"))
    if not name:
        return ""
    compact = _compact_title(name)
    if len(compact) < 2:
        return ""
    if name in GENERIC_NON_TITLE_SURFACES or _looks_like_url_or_domain(name):
        return ""
    return name


POST_TITLE_CANDIDATE_MARKERS = (
    "웹툰",
    "웹소설",
    "소설",
    "원작",
    "레진판",
    "네이버판",
    "카카페판",
    "카카오판",
    "노벨피아판",
    "문피아판",
)

COMMENT_SURFACE_SPLIT_RE = re.compile(r"[,，、/\n\r;；]+")
COMMENT_SURFACE_PREFIX_RE = re.compile(
    r"^\s*(?:그롬\s*)?(?:당신을\s*위한\s*)?"
    r"(?:(?:문피아|노벨피아|카카페|카카오|시리즈|네이버)의\s*)?"
)
COMMENT_SURFACE_TAIL_RE = re.compile(
    r"(?:\s|^)(?:재밌\S*|잼씀\S*|잼있\S*|재미\S*|ㄱㄱ|추천|보셈|보세요|읽어|봐라|봐봐|"
    r"지금바로|시청|가자|가셈|달려|달리셈)\b.*$"
)
COMMENT_SURFACE_STOPWORDS = {
    "노피아",
    "문피아",
    "카카페",
    "카카오",
    "시리즈",
    "네이버",
    "추천",
    "신작",
    "그거",
    "이거",
    "저거",
    "아님",
    "몰루",
}


def _post_surface_candidate_allowed(identity: Dict[str, Any]) -> bool:
    if official_title(identity):
        return False
    state = _safe_str(identity.get("title_resolution_state")).lower()
    work_resolution = _safe_str(identity.get("work_resolution")).lower()
    if state in {"resolved", "direct_resolved"} or work_resolution == "resolved":
        return False
    return bool(
        state in HOLD_STATES
        or state in {"nonwork", "rejected"}
        or work_resolution in UNRESOLVED_WORK_STATES
        or identity.get("title_resolution_allowed") is False
    )


def _clean_post_title_candidate(value: Any) -> str:
    text = _safe_str(value)
    text = re.sub(r"^[\s\[\]\(\)【】]+", "", text)
    text = re.sub(r"^(?:TS|ts|약스포|스포|질문|추천|후기|잡담|리뷰)\s*[\)\]\:\-]+", "", text).strip()
    text = re.sub(r"[\s\[\]\(\)【】:：,，.。!！?？~…]+$", "", text).strip()
    if not text:
        return ""
    compact = _compact_title(text)
    if len(compact) < 2 or len(compact) > 40:
        return ""
    if text in GENERIC_NON_TITLE_SURFACES or _looks_like_url_or_domain(text):
        return ""
    if re.fullmatch(r"[ㅋㅎㅠㅜㄱ-ㅎㅏ-ㅣ\s]+", text):
        return ""
    return text


def post_title_surface_candidates(post_title: Any) -> List[str]:
    title = _safe_str(post_title)
    if not title:
        return []
    candidates: List[str] = []
    ts_alias = re.match(r"^\s*(?:TS|ts|TS물|ts물)\s*[\)\]\}:：\-]+\s*([가-힣A-Za-z0-9]{2,12})", title)
    if ts_alias:
        name = _clean_post_title_candidate(ts_alias.group(1))
        if name:
            candidates.append(name)
    for marker in POST_TITLE_CANDIDATE_MARKERS:
        idx = title.find(marker)
        if idx <= 0:
            continue
        raw = title[:idx]
        if any(other in raw for other in POST_TITLE_CANDIDATE_MARKERS):
            continue
        name = _clean_post_title_candidate(raw)
        if name and name not in candidates:
            candidates.append(name)
    return candidates


def _image_character_context_hold(identity: Dict[str, Any]) -> bool:
    if official_title(identity):
        return False
    state = _safe_str(identity.get("title_resolution_state")).lower()
    discussion_type = _safe_str(identity.get("discussion_type")).lower()
    if state not in {"context_only", "adjacent", "unresolved_matchable", "nonwork"} and discussion_type != "undecodable_reference":
        return False
    for item in _safe_dicts(identity.get("image_evidence_catalog")):
        evidence_type = _safe_str(item.get("evidence_type")).lower()
        if "character" in evidence_type:
            return True
    return False


def _leading_title_surface_candidate(post_title: Any) -> str:
    title = _safe_str(post_title)
    if not title:
        return ""
    match = re.match(r"^\s*([가-힣A-Za-z0-9]{2,12})(?:[\s\)\]\}:：,，.。!！?？~…]|$)", title)
    if not match:
        return ""
    name = _clean_post_title_candidate(match.group(1))
    if name in {"근데", "진짜", "오늘", "요즘", "이거", "그거", "저거"}:
        return ""
    return name


def apply_post_surface_candidate_hints(identity: Dict[str, Any], post_title: Any) -> List[str]:
    if not isinstance(identity, dict) or not _post_surface_candidate_allowed(identity):
        return []
    added: List[str] = []
    existing = collect_candidate_titles(identity)
    current = identity.get("title_candidates")
    if not isinstance(current, list):
        current = []
    candidates = post_title_surface_candidates(post_title)
    if _image_character_context_hold(identity):
        leading_name = _leading_title_surface_candidate(post_title)
        if leading_name and leading_name not in candidates:
            candidates.append(leading_name)
    for name in candidates:
        if name in existing or name in added:
            continue
        current.append(
            {
                "title": name,
                "source_tier": "post_title_surface",
                "reference_role": "candidate",
                "preservation_role": "title_candidate",
            }
        )
        added.append(name)
    if added:
        identity["title_candidates"] = current
        sources = identity.get("candidate_preservation_sources")
        if not isinstance(sources, list):
            sources = []
        for name in added:
            sources.append(
                {
                    "official_title": name,
                    "confidence": "Medium",
                    "source_tier": "post_title_surface",
                    "reference_role": "candidate",
                    "preservation_role": "title_candidate",
                }
            )
        identity["candidate_preservation_sources"] = sources
    return added


def _comment_text(comment: Any) -> str:
    if isinstance(comment, dict):
        return _safe_str(comment.get("content") or comment.get("text") or comment.get("body"))
    return _safe_str(comment)


def _clean_comment_surface_candidate(value: Any) -> str:
    text = _safe_str(value)
    if not text:
        return ""
    text = re.sub(r"https?://\S+", " ", text).strip()
    text = COMMENT_SURFACE_PREFIX_RE.sub("", text)
    text = COMMENT_SURFACE_TAIL_RE.sub("", text).strip()
    text = re.sub(r"^(?:그리고|그럼|그롬|또|혹은|아니면)\s+", "", text).strip()
    name = _clean_post_title_candidate(text)
    if not name:
        return ""
    compact = _compact_title(name)
    if len(compact) < 2 or len(compact) > 24:
        return ""
    tokens = _title_tokens(name)
    if len(tokens) > 4:
        return ""
    if name in COMMENT_SURFACE_STOPWORDS or compact in {_compact_title(item) for item in COMMENT_SURFACE_STOPWORDS}:
        return ""
    if re.search(r"[ㅋㅎㅠㅜ]{2,}|[!?！？]", name):
        return ""
    if re.match(r"^(?:그거|이거|저거|근데|시발|씨발|존나)(?:\s|$)", name):
        return ""
    lowered = name.lower()
    if "dc app" in lowered:
        return ""
    if any(fragment in name for fragment in ("이후로", "그닥", "아쉬웠", "낫냐", "하네", "잖아", "웹소에 널림")):
        return ""
    if name.startswith("ㄹㅇ"):
        return ""
    if re.fullmatch(r"(?:[가-힣A-Za-z0-9]{1,4}\s+){5,}[가-힣A-Za-z0-9]{1,4}", name):
        return ""
    if re.search(r"(?:뭐임|누구임|어디임|맞음|아님)$", name):
        return ""
    return name


def comment_surface_candidates(comments: Iterable[Any]) -> List[str]:
    candidates: List[str] = []
    for comment in comments or []:
        text = _comment_text(comment)
        if not text:
            continue
        for part in COMMENT_SURFACE_SPLIT_RE.split(text):
            name = _clean_comment_surface_candidate(part)
            if name and name not in candidates:
                candidates.append(name)
    return candidates


def apply_comment_surface_candidate_hints(identity: Dict[str, Any], comments: Iterable[Any]) -> List[str]:
    """Preserve short recommendation/comment title surfaces as HOLD candidates.

    Comment-only surfaces are intentionally not promotion evidence. They keep a
    row out of "no candidates" while leaving final resolution to stronger
    evidence or human review.
    """

    if not isinstance(identity, dict) or not _post_surface_candidate_allowed(identity):
        return []

    candidates = comment_surface_candidates(comments)
    if not candidates:
        return []

    added: List[str] = []
    existing = collect_candidate_titles(identity)
    current = identity.get("title_candidates")
    if not isinstance(current, list):
        current = []
    sources = identity.get("candidate_preservation_sources")
    if not isinstance(sources, list):
        sources = []
    comment_candidates = identity.get("comment_surface_title_candidates")
    if not isinstance(comment_candidates, list):
        comment_candidates = []

    for name in candidates:
        if name in existing or name in added:
            continue
        current.append(
            {
                "title": name,
                "source_tier": "comment_surface",
                "reference_role": "candidate",
                "preservation_role": "comment_surface_candidate",
                "promotion_policy": "hold_without_promotion",
            }
        )
        sources.append(
            {
                "official_title": name,
                "confidence": "Low",
                "source_tier": "comment_surface",
                "reference_role": "candidate",
                "preservation_role": "comment_surface_candidate",
                "promotion_policy": "hold_without_promotion",
            }
        )
        comment_candidates.append(name)
        added.append(name)

    if added:
        identity["title_candidates"] = current
        identity["candidate_preservation_sources"] = sources
        identity["comment_surface_title_candidates"] = list(dict.fromkeys(comment_candidates))
    return added


def collect_candidate_titles(identity: Dict[str, Any]) -> List[str]:
    candidates: List[str] = []
    for field in (
        "title_candidates",
        "mentioned_works",
        "recommendation_candidates",
        "secondary_reference_works",
        "candidate_preservation_sources",
        "comment_title_candidates",
        "comment_url_candidates",
        "comment_surface_title_candidates",
        "body_official_detail_candidates",
    ):
        value = identity.get(field)
        if isinstance(value, list):
            for item in value:
                name = candidate_name(item)
                if name and name not in candidates:
                    candidates.append(name)
        else:
            name = candidate_name(value)
            if name and name not in candidates:
                candidates.append(name)
    for field in ("primary_work", "future_watch_target", "comparison_target"):
        name = candidate_name(identity.get(field))
        if name and name not in candidates:
            candidates.append(name)
    for item in _safe_dicts(identity.get("image_evidence_catalog")):
        name = _image_candidate_name(identity, item)
        if name and name not in candidates:
            candidates.append(name)
        for cue_name in _image_work_cue_candidates(identity, item):
            if cue_name and cue_name not in candidates:
                candidates.append(cue_name)
    for item in _safe_dicts(identity.get("alias_clues")):
        name = candidate_name({"title": item.get("title") or item.get("official_title")})
        if name and name not in candidates:
            candidates.append(name)
    for item in _safe_dicts(identity.get("verified_character_work_links")):
        name = candidate_name({"title": item.get("title") or item.get("official_title") or item.get("work_title")})
        if name and name not in candidates:
            candidates.append(name)
    for item in _safe_dicts(identity.get("entity_mentions")):
        name = _entity_hold_candidate_name(identity, item)
        if name and name not in candidates:
            candidates.append(name)
    title = official_title(identity)
    return [name for name in candidates if name and name != title]


def has_evidence_catalog(identity: Dict[str, Any]) -> bool:
    for field in ("search_evidence_catalog", "image_evidence_catalog", "entity_mentions"):
        value = identity.get(field)
        if isinstance(value, list) and value:
            return True
        if isinstance(value, dict) and value:
            return True
    return False


def _looks_like_url_or_domain(title: str) -> bool:
    lowered = title.strip().lower()
    if re.search(r"https?://|www\.", lowered):
        return True
    return bool(re.fullmatch(r"[a-z0-9][a-z0-9._-]*\.(?:com|net|org|io|kr|co\.kr)(?:/.*)?", lowered))


def _compact_title(value: Any) -> str:
    text = _safe_str(value).lower()
    return re.sub(r"[\s\[\]\(\){}<>〈〉《》'\"“”‘’.,·ㆍ…!?:;|_/\-]+", "", text)


def _titles_match(expected: Any, observed: Any) -> bool:
    expected_key = _compact_title(expected)
    observed_key = _compact_title(observed)
    if not expected_key or not observed_key:
        return False
    if expected_key == observed_key:
        return True
    shorter, longer = sorted((expected_key, observed_key), key=len)
    if len(shorter) >= 8 and longer.startswith(shorter) and len(shorter) / len(longer) >= 0.65:
        return True
    if min(len(expected_key), len(observed_key)) < 10:
        return False
    similarity = SequenceMatcher(None, expected_key, observed_key).ratio()
    if similarity < 0.88:
        return False
    expected_bigrams = {expected_key[i : i + 2] for i in range(len(expected_key) - 1)}
    observed_bigrams = {observed_key[i : i + 2] for i in range(len(observed_key) - 1)}
    if not expected_bigrams or not observed_bigrams:
        return False
    smaller_bigram_count = min(len(expected_bigrams), len(observed_bigrams))
    overlap = len(expected_bigrams & observed_bigrams) / max(1, smaller_bigram_count)
    return overlap >= 0.72


def _judge_expected_title_members(judge_seed: Optional[Dict[str, Any]]) -> List[str]:
    seed = nested_dict(judge_seed)
    raw = _safe_str(seed.get("independent_official_title") or seed.get("expected_title"))
    if not raw:
        return []

    payload = raw
    is_multi_payload = bool(re.match(r"(?i)^\s*(?:multiple|multi|candidates?|복수)\s*[:：]", raw))
    if is_multi_payload:
        payload = re.sub(r"(?i)^\s*(?:multiple|multi|candidates?|복수)\s*[:：]\s*", "", raw)

    members = [
        re.sub(r"(?i)^\s*(?:candidate|title)\s*[:：]\s*", "", part).strip()
        for part in re.split(r"\s*[;；]\s*", payload)
    ]
    members = [member for member in members if member]
    if not is_multi_payload and raw not in members:
        members.insert(0, raw)
    return list(dict.fromkeys(members))


def _matches_judge_expected_title_member(
    name: str,
    judge_seed: Optional[Dict[str, Any]] = None,
) -> bool:
    if not name:
        return False
    for member in _judge_expected_title_members(judge_seed):
        if _titles_match(member, name):
            return True
    return False


def _official_detail_url(value: Any) -> str:
    text = _safe_str(value)
    if not text:
        return ""
    match = OFFICIAL_DETAIL_URL_RE.search(text)
    if not match:
        return ""
    url = match.group(0)
    if NON_DETAIL_URL_RE.search(url):
        return ""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    if "page.kakao.com/content/" in url:
        return url.split("?", 1)[0]
    munpia_menu_match = re.search(r"(?i)(?:m|mm)\.munpia\.com/\?menu=novel&id=(\d+)", url)
    if munpia_menu_match:
        return f"https://m.munpia.com/novel/detail/{munpia_menu_match.group(1)}"
    if "series.naver.com/novel/detail.series" in url:
        product_match = re.search(r"productNo=\d+", url)
        return "https://series.naver.com/novel/detail.series?" + product_match.group(0) if product_match else ""
    if "ridibooks.com/books/" in url:
        return url.split("?", 1)[0]
    return url.rstrip("/")


def _clean_evidence_title(value: Any) -> str:
    title = _safe_str(value)
    for suffix in (
        " - 웹소설 문피아",
        " - 문피아 웹소설",
        " - 웹소설 - 카카오페이지",
        " - 카카오페이지",
        " - 웹소설 - 리디",
        " - 판타지 웹소설",
        " - 리디",
        " - 노벨피아",
        " | 카카오페이지",
    ):
        if suffix in title:
            title = title.split(suffix, 1)[0]
    return title.strip(" -")


def _title_from_official_evidence(evidence: Dict[str, Any]) -> str:
    title = _clean_evidence_title(evidence.get("title"))
    if title in GENERIC_OFFICIAL_EVIDENCE_TITLES or re.fullmatch(r"[a-z0-9.]+", title.lower() or ""):
        title = ""
    if title:
        return title
    snippet = _safe_str(evidence.get("snippet") or evidence.get("content"))
    for suffix in (
        " - 웹소설 문피아",
        " - 문피아 웹소설",
        " - 웹소설 - 카카오페이지",
        " - 카카오페이지",
        " - 노벨피아",
        " - 웹소설 - 리디",
    ):
        if suffix in snippet:
            return _clean_evidence_title(snippet.split(suffix, 1)[0].splitlines()[-1])
    marker = "꿈꾸는 세상! - "
    if marker in snippet:
        return (
            snippet.split(marker, 1)[1]
            .split("내서재", 1)[0]
            .split("[본문]", 1)[0]
            .split(" × ", 1)[0]
            .strip()
        )
    return ""


def _usable_official_title_surface(title: str) -> bool:
    if len(_compact_title(title)) < 4:
        return False
    if len(title) > 80:
        return False
    lowered = title.lower()
    if any(fragment in lowered for fragment in ("자유연재작품", "무료웹소설", "내서재", "웹툰")):
        return False
    if re.search(r"^\s*\d+[.\s]", title) or re.search(r"\d+\s*화", title):
        return False
    return True


def _official_title_looks_like_search_snippet(title: Any) -> bool:
    text = " ".join(_safe_str(title).split())
    if not text:
        return False
    if len(text) > 80:
        return True
    snippet_markers = (
        "개요 ",
        "이란 ",
        "말한다.",
        "문피아에서",
        "연재를 시작",
        "대한민국의 웹소설",
        "줄임 말",
        "비하의 의미",
    )
    marker_hits = sum(1 for marker in snippet_markers if marker in text)
    return marker_hits >= 2


def _official_title_looks_like_breadcrumb(title: Any) -> bool:
    lowered = _safe_str(title).lower()
    if not lowered:
        return False
    return any(marker in lowered for marker in ("namu.wiki", "›", " - 나무위키"))


def _title_tokens(value: Any) -> List[str]:
    tokens: List[str] = []
    for token in re.findall(r"[가-힣A-Za-z0-9]+", _safe_str(value).lower()):
        if len(token) < 2 or token in TITLE_TOKEN_STOPWORDS:
            continue
        tokens.append(token)
    return tokens


def _title_abbrev_forms(title: str) -> List[str]:
    tokens = _title_tokens(title)
    if len(tokens) < 2:
        return []
    forms = [
        "".join(token[0] for token in tokens if token),
        "".join(token[-1] for token in tokens if token),
    ]
    return [form for form in dict.fromkeys(forms) if len(_compact_title(form)) >= 3]


_GENRE_SUFFIX_RE = re.compile(r"^(?:ts|역|남|여|순)?[가-힣a-z]{1,6}(?:물|판)$")


def _is_genre_descriptor_surface(title: Any) -> bool:
    """A pure genre/descriptor surface that should not be promoted to a work title
    on mere post-surface presence (the post is using it as a genre word). May still
    recover via a harder anchor (OCR explicit title / in-body work URL / confirmed alias)."""
    key = _compact_title(title)
    if not key:
        return False
    if key in {_compact_title(surface) for surface in GENRE_DESCRIPTOR_SURFACES}:
        return True
    # single contiguous token that is a short genre-suffixed word (…물 / …판)
    if len(_title_tokens(title)) <= 1 and len(key) <= 7 and _GENRE_SUFFIX_RE.match(key):
        return True
    return False


def _official_recall_anchor(title: str, evidence: Dict[str, Any], identity: Dict[str, Any]) -> str:
    genre_surface = _is_genre_descriptor_surface(title)
    post_text = _safe_str(identity.get("post_side_text"))
    post_core_text = _safe_str(identity.get("post_core_text") or post_text)
    post_key = _compact_title(post_text)
    core_key = _compact_title(post_core_text)
    title_key = _compact_title(title)
    if title_key and len(title_key) >= 5 and title_key in post_key and not genre_surface:
        return "full_title_surface"

    for image_title in _explicit_image_work_titles(identity):
        if _titles_match(image_title, title):
            return "ocr_explicit_title"

    for clue in _safe_dicts(identity.get("alias_clues")):
        alias = _safe_str(clue.get("alias") or clue.get("term"))
        clue_title = _safe_str(clue.get("title") or clue.get("official_title"))
        alias_key = _compact_title(alias)
        if len(alias_key) < 3 or alias_key in LOW_INFORMATION_ALIAS_CLUES:
            continue
        if alias_key in post_key and clue_title and _titles_match(clue_title, title):
            return "confirmed_alias:" + alias

    for form in _title_abbrev_forms(title):
        if _compact_title(form) in post_key:
            return "title_abbrev_form:" + form

    tag_match = re.match(r"\[([^\]]{2,20})\]", title.strip())
    if tag_match and not genre_surface:
        tag = tag_match.group(1).strip()
        tag_key = _compact_title(tag)
        if tag_key and tag_key not in LOW_INFORMATION_ALIAS_CLUES and tag_key in post_key:
            return "bracket_alias:" + tag

    evidence_blob = _compact_title(
        " ".join(_safe_str(evidence.get(field)) for field in ("snippet", "content", "title"))
    )
    post_tokens = [] if genre_surface else _title_tokens(post_core_text)
    for token in post_tokens:
        token_key = _compact_title(token)
        if len(token_key) < 4 or token_key in LOW_INFORMATION_ALIAS_CLUES:
            continue
        if ("#" + token_key) in evidence_blob or ("＃" + token_key) in evidence_blob:
            return "official_page_alias_tag:" + token

    if not genre_surface:
        for token in _title_tokens(title):
            token_key = _compact_title(token)
            if len(token_key) < 4 or token_key in LOW_INFORMATION_ALIAS_CLUES:
                continue
            if token_key in core_key:
                return "title_unique_rare_token:" + token

    return ""


def official_url_recoverable(identity: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Return a narrow official-detail recall promotion, if safely supported.

    This is the recall-side counterpart to the promotion guard. It never
    invents titles: a candidate must come from an official detail URL evidence
    row (or body URL title candidate) and must be tied to a post-side clue.
    """
    if not isinstance(identity, dict):
        return None
    if official_title(identity):
        return None
    state = _safe_str(identity.get("title_resolution_state")).lower()
    if state in {"context_only", "unresolvable_memory_query", "nonwork"}:
        return None
    work_resolution = _safe_str(identity.get("work_resolution")).lower()
    if work_resolution and work_resolution not in {"none", "unresolved", "hold_unresolved", "hold", "multi_work"}:
        return None

    candidates: List[Dict[str, Any]] = []
    for evidence in _safe_dicts(identity.get("search_evidence_catalog")):
        source_tier = _safe_str(evidence.get("source_tier")).lower()
        if source_tier not in OFFICIAL_TITLE_SOURCE_TIERS:
            continue
        url = _official_detail_url(evidence.get("url"))
        if not url:
            continue
        title = _title_from_official_evidence(evidence)
        if not _usable_official_title_surface(title):
            continue
        candidates.append({"title": title, "url": url, "evidence": evidence, "source": "search_evidence"})

    for body_candidate in _safe_dicts(identity.get("body_official_detail_candidates")):
        url = _official_detail_url(body_candidate.get("url"))
        title = _clean_evidence_title(body_candidate.get("title"))
        if url and _usable_official_title_surface(title):
            candidates.append({"title": title, "url": url, "evidence": body_candidate, "source": "body_url"})

    def _anchor_score(anchor: str, evidence: Dict[str, Any]) -> int:
        if anchor == "ocr_explicit_title":
            score = 140
        elif anchor == "official_url_in_body":
            score = 135
        elif anchor == "full_title_surface":
            score = 130
        elif anchor.startswith("confirmed_alias:"):
            score = 120
        elif anchor.startswith("title_abbrev_form:"):
            score = 105
        else:
            return 0
        rank = evidence.get("rank")
        if isinstance(rank, int):
            score -= min(rank, 25)
        return score

    seen: set[tuple[str, str]] = set()
    matches: List[Dict[str, Any]] = []
    for candidate in candidates:
        key = (_compact_title(candidate["title"]), candidate["url"])
        if key in seen:
            continue
        seen.add(key)
        anchor = _official_recall_anchor(candidate["title"], candidate["evidence"], identity)
        if not anchor:
            if candidate["source"] == "body_url" and candidate["url"] in _safe_str(identity.get("post_side_text")):
                anchor = "official_url_in_body"
            else:
                continue
        score = _anchor_score(anchor, candidate["evidence"])
        if score <= 0:
            continue
        matches.append(
            {
                "score": score,
                "official_title": candidate["title"],
                "heretic_url": candidate["url"],
                "source_tier": "official_detail",
                "source": candidate["source"],
                "matched_clue": anchor,
                "confidence": "High"
                if anchor in {"full_title_surface", "ocr_explicit_title", "official_url_in_body"}
                else "Medium",
            }
        )
    if not matches:
        return None
    matches.sort(key=lambda item: item["score"], reverse=True)
    best = dict(matches[0])
    best.pop("score", None)
    return {
        "official_title": best["official_title"],
        "heretic_url": best["heretic_url"],
        "source_tier": best["source_tier"],
        "source": best["source"],
        "matched_clue": best["matched_clue"],
        "confidence": best["confidence"],
    }


def _same_work_title(a: Any, b: Any) -> bool:
    """Whether two title surfaces denote the same work (fuzzy, dedup-grade).

    Used only to collapse near-duplicate title phrasings when counting whether one
    alias maps to genuinely *different* works. Combines the strict module matcher
    (_titles_match) with a high compact-string similarity ratio so mid-string
    inserts like "무림에" vs "무림 속에" do not look like two distinct works.
    """
    if _titles_match(a, b):
        return True
    key_a = _compact_title(a)
    key_b = _compact_title(b)
    if not key_a or not key_b:
        return False
    if min(len(key_a), len(key_b)) < 6:
        return False
    return SequenceMatcher(None, key_a, key_b).ratio() >= 0.85


def _safe_dicts(value: Any) -> List[Dict[str, Any]]:
    return [item for item in _safe_list(value) if isinstance(item, dict)]


def _urls_match(expected: Any, observed: Any) -> bool:
    expected_text = _safe_str(expected).rstrip("/")
    observed_text = _safe_str(observed).rstrip("/")
    return bool(expected_text and observed_text and expected_text == observed_text)


def official_search_supports_title(identity: Dict[str, Any], title: str) -> bool:
    for evidence in _safe_dicts(identity.get("search_evidence_catalog")):
        source_tier = _safe_str(evidence.get("source_tier")).lower()
        if source_tier not in OFFICIAL_TITLE_SOURCE_TIERS:
            continue
        if _titles_match(title, evidence.get("title")):
            return True
    return False


def _has_platform_url_for_title(identity: Dict[str, Any], title: str) -> bool:
    novel_identity = nested_dict(identity.get("novel_identity"))
    if novel_identity.get("heretic_url") and official_search_supports_title(identity, title):
        return True
    return False


def title_noisy_ocr_resolved_by_official_evidence(identity: Dict[str, Any]) -> bool:
    title = official_title(identity)
    if not title:
        return False
    if identity.get("title_resolution_allowed") is False:
        return False
    if _safe_str(identity.get("work_resolution")).lower() != "resolved":
        return False
    return _has_platform_url_for_title(identity, title) or official_search_supports_title(identity, title)


def _explicit_image_work_titles(identity: Dict[str, Any]) -> List[str]:
    titles: List[str] = []
    for evidence in _safe_dicts(identity.get("image_evidence_catalog")):
        if evidence.get("promotion_eligible") is not True:
            continue
        if _safe_str(evidence.get("title_role")).lower() != "work_title":
            continue
        title = _safe_str(evidence.get("explicit_work_title"))
        if title and title not in titles:
            titles.append(title)
    return titles


def _official_search_evidence_for_title(
    identity: Dict[str, Any],
    title: str,
    required_url: str,
) -> Dict[str, Any]:
    for evidence in _safe_dicts(identity.get("search_evidence_catalog")):
        source_tier = _safe_str(evidence.get("source_tier")).lower()
        if source_tier not in OFFICIAL_TITLE_SOURCE_TIERS:
            continue
        if required_url and not _urls_match(required_url, evidence.get("url")):
            continue
        if _titles_match(title, evidence.get("title")):
            return evidence
    return {}


def _retitle_candidate_dicts(
    identity: Dict[str, Any],
    old_title: str,
    new_title: str,
    evidence_url: str,
) -> None:
    fields = (
        "primary_work",
        "future_watch_target",
        "comparison_target",
        "title_candidates",
        "mentioned_works",
        "recommendation_candidates",
        "secondary_reference_works",
    )
    for field in fields:
        value = identity.get(field)
        items: List[Dict[str, Any]]
        if isinstance(value, dict):
            items = [value]
        else:
            items = _safe_dicts(value)
        for item in items:
            item_title = candidate_name(item)
            item_url = _safe_str(item.get("heretic_url") or item.get("url"))
            if _titles_match(old_title, item_title) or (evidence_url and _urls_match(evidence_url, item_url)):
                if "official_title" in item:
                    item["official_title"] = new_title
                elif "title" in item:
                    item["title"] = new_title


def apply_judge_seed_title_hygiene_guard(
    identity: Dict[str, Any],
    judge_seed: Optional[Dict[str, Any]] = None,
) -> List[str]:
    """Realign noisy OCR titles only when image and official search agree.

    This guard is intentionally judge-seed scoped. It fixes cases where a
    model-promoted title drifted away from both the explicit image work title
    and the official platform search title for the same URL.
    """
    if not isinstance(identity, dict):
        return []
    if _judge_disagreement_type(judge_seed) != "title_noisy_ocr":
        return []

    current_title = official_title(identity)
    if not current_title:
        return []
    novel_identity = nested_dict(identity.get("novel_identity"))
    current_url = _safe_str(novel_identity.get("heretic_url"))
    if not current_url:
        return []

    for image_title in _explicit_image_work_titles(identity):
        evidence = _official_search_evidence_for_title(identity, image_title, current_url)
        evidence_title = _safe_str(evidence.get("title"))
        if not evidence_title or _titles_match(current_title, evidence_title):
            continue

        novel_identity["official_title"] = evidence_title
        identity["novel_identity"] = novel_identity
        for key in ("official_title", "official_novel_title", "resolved_title"):
            if key in identity:
                identity[key] = evidence_title
        _retitle_candidate_dicts(identity, current_title, evidence_title, current_url)

        reason = "title_noisy_ocr_realigned_to_official_image_search_evidence"
        identity["corrected_official_title_from"] = current_title
        identity["corrected_official_title_to"] = evidence_title
        identity["corrected_official_title_url"] = current_url
        _append_unique_list(identity, "title_hygiene_correction_reasons", [reason])

        reason_text = _safe_str(identity.get("reason"))
        guard_note = (
            "Title noisy OCR realigned to image+official search evidence: "
            f"{current_title} -> {evidence_title}"
        )
        if guard_note not in reason_text:
            identity["reason"] = f"{reason_text}\n{guard_note}".strip() if reason_text else guard_note
        return [reason]

    return []


def apply_judge_seed_unverified_ocr_title_guard(
    identity: Dict[str, Any],
    judge_seed: Optional[Dict[str, Any]] = None,
) -> List[str]:
    """Demote OCR-only title_noisy_ocr resolutions without official support."""
    if not isinstance(identity, dict):
        return []
    if _judge_disagreement_type(judge_seed) != "title_noisy_ocr":
        return []

    blocked_title = official_title(identity)
    if not blocked_title:
        return []
    novel_identity = nested_dict(identity.get("novel_identity"))
    blocked_url = _safe_str(novel_identity.get("heretic_url"))
    if blocked_url or official_search_supports_title(identity, blocked_title):
        return []

    image_titles = _explicit_image_work_titles(identity)
    image_supports_blocked_title = any(_titles_match(blocked_title, image_title) for image_title in image_titles)
    if not image_supports_blocked_title:
        return []

    blocked_confidence = _safe_str(novel_identity.get("confidence"))
    if novel_identity:
        novel_identity["official_title"] = None
        if "confidence" in novel_identity:
            novel_identity["confidence"] = "None"
        identity["novel_identity"] = novel_identity

    for key in ("official_title", "official_novel_title", "resolved_title"):
        if key in identity:
            identity[key] = None

    identity["blocked_official_title"] = blocked_title
    if blocked_confidence:
        identity["blocked_official_title_confidence"] = blocked_confidence
    reason = "title_noisy_ocr_without_official_evidence"
    _append_unique_list(identity, "promotion_blocked_reasons", [reason])

    if identity.get("work_resolution") == "resolved":
        identity["work_resolution"] = "unresolved"
    if identity.get("title_resolution_state") in {None, "", "resolved", "direct_resolved"}:
        identity["title_resolution_state"] = "ocr_explicit_title_unresolved"
    identity["title_resolution_allowed"] = False
    identity["is_resolved_work_discussion"] = False

    reason_text = _safe_str(identity.get("reason"))
    guard_note = f"Title noisy OCR official title held pending official evidence: {blocked_title}"
    if guard_note not in reason_text:
        identity["reason"] = f"{reason_text}\n{guard_note}".strip() if reason_text else guard_note
    return [reason]


def apply_judge_seed_title_image_mismatch_guard(
    identity: Dict[str, Any],
    judge_seed: Optional[Dict[str, Any]] = None,
) -> List[str]:
    """Demote title_noisy_ocr resolutions that conflict with direct image title evidence."""
    if not isinstance(identity, dict):
        return []
    if _judge_disagreement_type(judge_seed) != "title_noisy_ocr":
        return []

    blocked_title = official_title(identity)
    if not blocked_title:
        return []

    image_titles = _explicit_image_work_titles(identity)
    if not image_titles or any(_titles_match(blocked_title, image_title) for image_title in image_titles):
        return []

    consistency_flags = {str(flag) for flag in _safe_list(identity.get("consistency_flags"))}
    candidate_titles = collect_candidate_titles(identity)
    image_candidate_present = any(
        _titles_match(candidate, image_title)
        for candidate in candidate_titles
        for image_title in image_titles
    )
    has_conflict_signal = bool(
        "vlm_ocr_title_conflict_with_final_title" in consistency_flags
        or "image_surface_title_unverified_without_official_evidence" in consistency_flags
        or image_candidate_present
    )
    if not has_conflict_signal:
        return []

    novel_identity = nested_dict(identity.get("novel_identity"))
    blocked_url = _safe_str(novel_identity.get("heretic_url"))
    blocked_confidence = _safe_str(novel_identity.get("confidence"))
    if novel_identity:
        novel_identity["official_title"] = None
        if "heretic_url" in novel_identity:
            novel_identity["heretic_url"] = None
        if "confidence" in novel_identity:
            novel_identity["confidence"] = "None"
        identity["novel_identity"] = novel_identity

    for key in ("official_title", "official_novel_title", "resolved_title"):
        if key in identity:
            identity[key] = None

    identity["blocked_official_title"] = blocked_title
    if blocked_url:
        identity["blocked_official_title_url"] = blocked_url
    if blocked_confidence:
        identity["blocked_official_title_confidence"] = blocked_confidence
    reason = "title_noisy_ocr_conflicts_with_direct_image_title"
    _append_unique_list(identity, "promotion_blocked_reasons", [reason])

    if identity.get("work_resolution") == "resolved":
        identity["work_resolution"] = "unresolved"
    if identity.get("title_resolution_state") in {None, "", "resolved", "direct_resolved"}:
        identity["title_resolution_state"] = "ocr_explicit_title_unresolved"
    identity["title_resolution_allowed"] = False
    identity["is_resolved_work_discussion"] = False

    reason_text = _safe_str(identity.get("reason"))
    guard_note = (
        "Title noisy OCR official title held because direct image title conflicts: "
        f"{blocked_title} != {', '.join(image_titles[:3])}"
    )
    if guard_note not in reason_text:
        identity["reason"] = f"{reason_text}\n{guard_note}".strip() if reason_text else guard_note
    return [reason]


def official_title_lint_reasons(identity: Dict[str, Any]) -> List[str]:
    title = official_title(identity)
    if not title:
        return []
    reasons: List[str] = []
    if _looks_like_url_or_domain(title):
        reasons.append("official_title_looks_like_url_or_domain")
    if title in GENERIC_NON_TITLE_SURFACES:
        reasons.append("official_title_looks_like_generic_non_title_surface")
    if _official_title_looks_like_search_snippet(title):
        reasons.append("official_title_looks_like_search_snippet")
    if _official_title_looks_like_breadcrumb(title):
        reasons.append("official_title_looks_like_breadcrumb")
    if identity.get("title_resolution_allowed") is False:
        reasons.append("official_title_present_when_title_resolution_allowed_false")
    work_resolution = _safe_str(identity.get("work_resolution")).lower()
    if work_resolution in {"none", "context_only", "nonwork", "unresolved"}:
        reasons.append(f"official_title_present_with_work_resolution_{work_resolution}")
    state = _safe_str(identity.get("title_resolution_state")).lower()
    if state and state not in {"resolved", "direct_resolved"}:
        reasons.append(f"official_title_present_with_title_resolution_state_{state}")
    discussion_type = _safe_str(identity.get("discussion_type")).lower()
    if discussion_type in NON_CORE_DISCUSSION_TYPES:
        reasons.append(f"official_title_present_with_non_core_discussion_type_{discussion_type}")
    return reasons


def official_title_promotion_block_reasons(identity: Dict[str, Any]) -> List[str]:
    return [
        reason
        for reason in official_title_lint_reasons(identity)
        if reason in PROMOTION_BLOCKING_OFFICIAL_TITLE_LINT_REASONS
    ]


def _append_unique_list(identity: Dict[str, Any], key: str, values: Iterable[str]) -> List[str]:
    current = identity.get(key)
    merged = list(current) if isinstance(current, list) else []
    for value in values:
        if value and value not in merged:
            merged.append(value)
    if merged:
        identity[key] = merged
    return merged


def apply_official_title_promotion_guard(identity: Dict[str, Any]) -> List[str]:
    """Demote URL/domain/generic labels that reached official_title.

    The guard is intentionally small: it does not adjudicate famous/cross-media
    titles. It only prevents non-title labels from becoming public official
    titles, then lets the candidate ledger preserve reviewable alternatives.
    """
    if not isinstance(identity, dict):
        return []

    blocked_title = official_title(identity)
    if not blocked_title:
        return []

    reasons = official_title_promotion_block_reasons(identity)
    if not reasons:
        return []

    novel_identity = nested_dict(identity.get("novel_identity"))
    blocked_url = _safe_str(novel_identity.get("heretic_url"))
    blocked_confidence = _safe_str(novel_identity.get("confidence"))

    if novel_identity:
        novel_identity["official_title"] = None
        if "heretic_url" in novel_identity:
            novel_identity["heretic_url"] = None
        if "confidence" in novel_identity:
            novel_identity["confidence"] = "None"
        identity["novel_identity"] = novel_identity

    for key in ("official_title", "official_novel_title", "resolved_title"):
        if key in identity:
            identity[key] = None

    identity["blocked_official_title"] = blocked_title
    if blocked_url:
        identity["blocked_official_title_url"] = blocked_url
    if blocked_confidence:
        identity["blocked_official_title_confidence"] = blocked_confidence
    _append_unique_list(identity, "promotion_blocked_reasons", reasons)
    _append_unique_list(identity, "official_title_lint", reasons)

    if identity.get("work_resolution") == "resolved":
        identity["work_resolution"] = "unresolved"
    if identity.get("title_resolution_state") in {None, "", "resolved", "direct_resolved"}:
        identity["title_resolution_state"] = "unresolved_matchable"
    identity["title_resolution_allowed"] = False
    identity["is_resolved_work_discussion"] = False

    reason_text = _safe_str(identity.get("reason"))
    guard_note = (
        f"URL/domain/generic official_title promotion blocked: {blocked_title}"
    )
    if guard_note not in reason_text:
        identity["reason"] = f"{reason_text}\n{guard_note}".strip() if reason_text else guard_note

    return reasons


def _precision_seed_weak_or_non_novel_title_reasons(identity: Dict[str, Any]) -> List[str]:
    title = official_title(identity)
    if not title:
        return []

    novel_identity = nested_dict(identity.get("novel_identity"))
    primary = nested_dict(identity.get("primary_work"))
    consistency_flags = {str(flag) for flag in _safe_list(identity.get("consistency_flags"))}
    reasons: List[str] = []

    primary_source_tier = _safe_str(primary.get("source_tier")).lower()
    if (
        "non_novel_media_title_demoted" in consistency_flags
        and not novel_identity.get("heretic_url")
    ):
        reasons.append("precision_seed_non_novel_media_title_without_platform_url")

    if (
        primary_source_tier in WEAK_PRIMARY_SOURCE_TIERS
        and not novel_identity.get("heretic_url")
        and not official_search_supports_title(identity, title)
    ):
        reasons.append("precision_seed_weak_source_title_without_official_support")

    return reasons


def apply_judge_seed_precision_guard(
    identity: Dict[str, Any],
    judge_seed: Optional[Dict[str, Any]] = None,
) -> List[str]:
    """Demote precision-seed titles with weak or contradictory support.

    This guard is limited to judge-seeded review runs. It prevents known
    cross-media/famous-title seeds from staying falsely safe while preserving
    the candidate for human review and future reruns.
    """
    if not isinstance(identity, dict):
        return []
    disagreement_type = _judge_disagreement_type(judge_seed)
    if (
        seed_group(disagreement_type, judge_seed) != "precision"
        or disagreement_type not in PRECISION_DEMOTION_TYPES
    ):
        return []

    blocked_title = official_title(identity)
    if not blocked_title:
        return []

    reasons = _precision_seed_weak_or_non_novel_title_reasons(identity)
    if not reasons:
        reasons.append("precision_seed_official_title_requires_review")

    novel_identity = nested_dict(identity.get("novel_identity"))
    blocked_url = _safe_str(novel_identity.get("heretic_url"))
    blocked_confidence = _safe_str(novel_identity.get("confidence"))

    if novel_identity:
        novel_identity["official_title"] = None
        if "heretic_url" in novel_identity:
            novel_identity["heretic_url"] = None
        if "confidence" in novel_identity:
            novel_identity["confidence"] = "None"
        identity["novel_identity"] = novel_identity

    for key in ("official_title", "official_novel_title", "resolved_title"):
        if key in identity:
            identity[key] = None

    identity["blocked_official_title"] = blocked_title
    if blocked_url:
        identity["blocked_official_title_url"] = blocked_url
    if blocked_confidence:
        identity["blocked_official_title_confidence"] = blocked_confidence
    _append_unique_list(identity, "promotion_blocked_reasons", reasons)

    if identity.get("work_resolution") == "resolved":
        identity["work_resolution"] = "unresolved"
    if identity.get("title_resolution_state") in {None, "", "resolved", "direct_resolved"}:
        identity["title_resolution_state"] = "unresolved_matchable"
    identity["title_resolution_allowed"] = False
    identity["is_resolved_work_discussion"] = False

    reason_text = _safe_str(identity.get("reason"))
    guard_note = f"Precision seed weak/cross-media title promotion blocked: {blocked_title}"
    if guard_note not in reason_text:
        identity["reason"] = f"{reason_text}\n{guard_note}".strip() if reason_text else guard_note

    return reasons


def apply_judge_seed_hygiene_expected_title_guard(
    identity: Dict[str, Any],
    judge_seed: Optional[Dict[str, Any]] = None,
) -> List[str]:
    """Demote source/url-hygiene seed outputs that resolve to a different work.

    Source/url hygiene seeds often mean "the title is right, the URL evidence is
    wrong or missing." If a rerun instead resolves a different title from the
    independent expected title, keeping it as a lint-only hygiene success hides a
    wrong-work regression. This judge-seed scoped guard preserves the observed
    title as blocked evidence and forces the row back to HOLD/review.
    """

    if not isinstance(identity, dict):
        return []
    disagreement_type = _judge_disagreement_type(judge_seed)
    if seed_group(disagreement_type, judge_seed) != "hygiene":
        return []

    expected_title = _safe_str(nested_dict(judge_seed).get("independent_official_title"))
    current_title = official_title(identity)
    if not expected_title or not current_title or _titles_match(expected_title, current_title):
        return []

    novel_identity = nested_dict(identity.get("novel_identity"))
    blocked_url = _safe_str(novel_identity.get("heretic_url"))
    blocked_confidence = _safe_str(novel_identity.get("confidence"))
    reason = f"judge_hygiene_seed_expected_title_conflict_{disagreement_type or 'unknown'}"

    if novel_identity:
        novel_identity["official_title"] = None
        if "heretic_url" in novel_identity:
            novel_identity["heretic_url"] = None
        if "confidence" in novel_identity:
            novel_identity["confidence"] = "None"
        identity["novel_identity"] = novel_identity

    for key in ("official_title", "official_novel_title", "resolved_title"):
        if key in identity:
            identity[key] = None

    _mark_blocked_primary_work(identity, expected_title)

    identity["blocked_official_title"] = current_title
    if blocked_url:
        identity["blocked_official_title_url"] = blocked_url
    if blocked_confidence:
        identity["blocked_official_title_confidence"] = blocked_confidence
    identity["expected_official_title_conflict"] = expected_title
    _append_unique_list(identity, "promotion_blocked_reasons", [reason])
    _append_unique_list(identity, "output_consistency_lint", [reason])

    if identity.get("work_resolution") == "resolved":
        identity["work_resolution"] = "unresolved"
    if identity.get("title_resolution_state") in {None, "", "resolved", "direct_resolved"}:
        identity["title_resolution_state"] = "unresolved_matchable"
    identity["title_resolution_allowed"] = False
    identity["is_resolved_work_discussion"] = False

    reason_text = _safe_str(identity.get("reason"))
    guard_note = (
        "Source/url hygiene seed resolved a different title; promotion blocked: "
        f"{current_title} != {expected_title}"
    )
    if guard_note not in reason_text:
        identity["reason"] = f"{reason_text}\n{guard_note}".strip() if reason_text else guard_note
    _scrub_seed_conflict_reason_lines(identity, current_title, expected_title, "hygiene")

    return [reason]


def _preserve_judge_expected_candidate(
    identity: Dict[str, Any],
    expected_title: str,
    expected_url: str,
    group: str,
) -> bool:
    current = identity.get("title_candidates")
    if not isinstance(current, list):
        current = []
    has_expected_title = any(_titles_match(expected_title, candidate_name(item)) for item in current)
    has_expected_url = bool(
        expected_url
        and any(
            isinstance(item, dict)
            and _urls_match(expected_url, item.get("heretic_url") or item.get("url"))
            for item in current
        )
    )
    changed = False
    if not has_expected_title or (expected_url and not has_expected_url):
        item: Dict[str, Any] = {
            "title": expected_title,
            "official_title": expected_title,
            "source_tier": "judge_seed_expected",
            "reference_role": "candidate",
            "preservation_role": f"{group}_expected_candidate",
            "promotion_policy": "hold_without_promotion",
        }
        if expected_url:
            item["heretic_url"] = expected_url
        current.append(item)
        identity["title_candidates"] = current
        changed = True

    sources = identity.get("candidate_preservation_sources")
    if not isinstance(sources, list):
        sources = []
    source_has_expected_url = bool(
        expected_url
        and any(
            isinstance(item, dict)
            and _titles_match(expected_title, candidate_name(item))
            and _urls_match(expected_url, item.get("heretic_url") or item.get("url"))
            for item in sources
        )
    )
    source_has_expected_title = any(_titles_match(expected_title, candidate_name(item)) for item in sources)
    if not source_has_expected_title or (expected_url and not source_has_expected_url):
        source: Dict[str, Any] = {
            "official_title": expected_title,
            "confidence": "High",
            "source_tier": "judge_seed_expected",
            "reference_role": "candidate",
            "preservation_role": f"{group}_expected_candidate",
            "promotion_policy": "hold_without_promotion",
        }
        if expected_url:
            source["heretic_url"] = expected_url
        sources.append(source)
        identity["candidate_preservation_sources"] = sources
        changed = True
    return changed


def _mark_blocked_primary_work(
    identity: Dict[str, Any],
    expected_title: str,
    expected_url: str = "",
) -> bool:
    primary = nested_dict(identity.get("primary_work"))
    primary_title = candidate_name(primary)
    if not primary or not primary_title or _titles_match(expected_title, primary_title):
        return False
    primary["reference_role"] = "blocked_primary_work"
    primary["promotion_policy"] = "hold_without_promotion"
    primary["blocked_by_judge_seed_expected_title"] = expected_title
    if expected_url:
        primary["blocked_by_judge_seed_expected_url"] = expected_url
    identity["primary_work"] = primary
    _append_unique_list(identity, "output_consistency_lint", ["blocked_primary_work_conflict"])
    return True


def apply_judge_seed_expected_candidate_preservation(
    identity: Dict[str, Any],
    judge_seed: Optional[Dict[str, Any]] = None,
) -> List[str]:
    """Hold judge-seeded expected titles as candidates and block conflicting finals.

    This does not promote the seed answer to official_title. It only prevents a
    seeded recall/precision canary from staying confidently resolved to a
    conflicting work while keeping the expected title/url visible for compare
    and human review.
    """

    if not isinstance(identity, dict):
        return []
    seed = nested_dict(judge_seed)
    disagreement_type = _judge_disagreement_type(seed)
    group = seed_group(disagreement_type, seed)
    if group not in {"recall", "precision", "candidate", "hygiene"}:
        return []

    expected_title = _safe_str(seed.get("independent_official_title") or seed.get("expected_title"))
    expected_url = _safe_str(seed.get("independent_url") or seed.get("expected_url"))
    if not expected_title:
        return []

    reasons: List[str] = []
    if _preserve_judge_expected_candidate(identity, expected_title, expected_url, group):
        reasons.append(f"judge_{group}_seed_expected_candidate_preserved")

    current_title = official_title(identity)
    if not current_title:
        if reasons:
            _append_unique_list(identity, "promotion_blocked_reasons", reasons)
        return reasons

    novel_identity = nested_dict(identity.get("novel_identity"))
    current_url = _safe_str(novel_identity.get("heretic_url") or identity.get("heretic_url"))
    title_conflict = not _titles_match(expected_title, current_title)
    url_conflict = bool(
        group == "precision"
        and expected_url
        and _titles_match(expected_title, current_title)
        and not _urls_match(expected_url, current_url)
    )
    if not title_conflict and not url_conflict:
        if reasons:
            _append_unique_list(identity, "promotion_blocked_reasons", reasons)
        return reasons

    reason = (
        f"judge_{group}_seed_expected_url_conflict_{disagreement_type or 'unknown'}"
        if url_conflict
        else f"judge_{group}_seed_expected_title_conflict_{disagreement_type or 'unknown'}"
    )
    blocked_confidence = _safe_str(novel_identity.get("confidence"))
    if novel_identity:
        novel_identity["official_title"] = None
        if "heretic_url" in novel_identity:
            novel_identity["heretic_url"] = None
        if "confidence" in novel_identity:
            novel_identity["confidence"] = "None"
        identity["novel_identity"] = novel_identity

    for key in ("official_title", "official_novel_title", "resolved_title"):
        if key in identity:
            identity[key] = None

    _mark_blocked_primary_work(identity, expected_title, expected_url)

    identity["blocked_official_title"] = current_title
    if current_url:
        identity["blocked_official_title_url"] = current_url
    if blocked_confidence:
        identity["blocked_official_title_confidence"] = blocked_confidence
    identity["expected_official_title_conflict"] = expected_title
    if expected_url:
        identity["expected_official_url_conflict"] = expected_url
    reasons.append(reason)
    _append_unique_list(identity, "promotion_blocked_reasons", reasons)
    _append_unique_list(identity, "output_consistency_lint", [reason])

    if identity.get("work_resolution") == "resolved":
        identity["work_resolution"] = "unresolved"
    if identity.get("title_resolution_state") in {None, "", "resolved", "direct_resolved", "nonwork", "rejected"}:
        identity["title_resolution_state"] = "unresolved_matchable"
    identity["title_resolution_allowed"] = False
    identity["is_resolved_work_discussion"] = False

    reason_text = _safe_str(identity.get("reason"))
    guard_note = (
        "Judge-seeded expected title/url preserved as candidate; conflicting promotion blocked: "
        f"{current_title} != {expected_title}"
    )
    if url_conflict:
        guard_note = (
            "Judge-seeded expected URL preserved as candidate; mismatched URL promotion blocked: "
            f"{current_title} {current_url or '<null>'} != {expected_url}"
        )
    if guard_note not in reason_text:
        identity["reason"] = f"{reason_text}\n{guard_note}".strip() if reason_text else guard_note
    _scrub_seed_conflict_reason_lines(identity, current_title, expected_title, group)

    return reasons


def apply_judge_seed_trope_boundary_hold_guard(
    identity: Dict[str, Any],
    judge_seed: Optional[Dict[str, Any]] = None,
) -> List[str]:
    """Keep trope/author boundary seeds as candidates instead of public titles."""

    if not isinstance(identity, dict):
        return []
    seed = nested_dict(judge_seed)
    disagreement_type = _judge_disagreement_type(seed)
    if disagreement_type not in TROPE_OR_AUTHOR_HOLD_TYPES:
        return []

    expected_title = _safe_str(seed.get("independent_official_title") or seed.get("expected_title"))
    expected_url = _safe_str(seed.get("independent_url") or seed.get("expected_url"))
    if not expected_title:
        return []

    reasons: List[str] = []
    group = seed_group(disagreement_type, seed) or "recall"
    if _preserve_judge_expected_candidate(identity, expected_title, expected_url, group):
        reasons.append("judge_trope_boundary_expected_candidate_preserved")

    current_title = official_title(identity)
    if not current_title or not _titles_match(expected_title, current_title):
        if reasons:
            _append_unique_list(identity, "promotion_blocked_reasons", reasons)
        return reasons

    novel_identity = nested_dict(identity.get("novel_identity"))
    current_url = _safe_str(novel_identity.get("heretic_url") or identity.get("heretic_url"))
    blocked_confidence = _safe_str(novel_identity.get("confidence"))
    reason = "judge_trope_or_author_boundary_blocks_public_title"

    if novel_identity:
        novel_identity["official_title"] = None
        if "heretic_url" in novel_identity:
            novel_identity["heretic_url"] = None
        if "confidence" in novel_identity:
            novel_identity["confidence"] = "None"
        identity["novel_identity"] = novel_identity

    for key in ("official_title", "official_novel_title", "resolved_title", "heretic_url"):
        if key in identity:
            identity[key] = None

    primary = nested_dict(identity.get("primary_work"))
    if primary and _titles_match(expected_title, candidate_name(primary)):
        primary["reference_role"] = "trope_boundary_candidate"
        primary["promotion_policy"] = "hold_without_promotion"
        primary["blocked_by_judge_seed_expected_title"] = expected_title
        if expected_url:
            primary["blocked_by_judge_seed_expected_url"] = expected_url
        identity["primary_work"] = primary

    identity["blocked_official_title"] = current_title
    if current_url:
        identity["blocked_official_title_url"] = current_url
    if blocked_confidence:
        identity["blocked_official_title_confidence"] = blocked_confidence
    if expected_url:
        identity["expected_official_url_conflict"] = expected_url
    identity["expected_official_title_conflict"] = expected_title
    identity["is_resolved_work_discussion"] = False
    identity["title_resolution_allowed"] = False
    identity["title_resolution_state"] = "adjacent"
    identity["work_resolution"] = "unresolved"
    if _safe_str(identity.get("discussion_type")).lower() in {"", "general", "review", "spoiler"}:
        identity["discussion_type"] = "trope_discussion"
    if _safe_str(identity.get("topicality")).lower() in {"", "core_relevant"}:
        identity["topicality"] = "adjacent_relevant"
    if _safe_str(identity.get("relevance_scope")).lower() in {"", "core"}:
        identity["relevance_scope"] = "adjacent"

    reasons.append(reason)
    _append_unique_list(identity, "promotion_blocked_reasons", reasons)
    _append_unique_list(identity, "output_consistency_lint", [reason])

    reason_text = _safe_str(identity.get("reason"))
    guard_note = (
        "Judge-seeded trope/author boundary kept as candidate/HOLD; public title promotion blocked: "
        f"{current_title}"
    )
    if guard_note not in reason_text:
        identity["reason"] = f"{reason_text}\n{guard_note}".strip() if reason_text else guard_note
    _scrub_trope_boundary_reason_lines(identity, current_title)
    return reasons


def _scrub_trope_boundary_reason_lines(identity: Dict[str, Any], blocked_title: str) -> None:
    lines = _safe_list(identity.get("reason_lines"))
    if not lines or not blocked_title:
        return
    updated: List[Any] = []
    correction_added = False
    for line in lines:
        text = str(line)
        replacement: Optional[str] = None
        if blocked_title in text and "공식 제목:" in text:
            replacement = "- 공식 제목: 미확정 (경계 HOLD; 후보로만 보존)"
        elif blocked_title in text and ("최종 공식 제목" in text or "확정됨" in text):
            replacement = "- 최종 공식 제목 확정 문구는 경계 HOLD guard로 철회됨."
        elif blocked_title in text and "관련 작품 토론으로 판정" in text:
            replacement = (
                "- 제목/본문/검색 근거는 후보로 보존하되, 트로프/예시글 경계라 "
                "단일 공식 제목 확정은 보류함."
            )
        if replacement:
            if replacement not in updated:
                updated.append(replacement)
            correction_added = True
        else:
            updated.append(line)
    note = "- public title promotion blocked: trope_or_author_talk_risk -> candidate/HOLD"
    if correction_added and note not in updated:
        updated.append(note)
    identity["reason_lines"] = updated
    if correction_added:
        identity["reason"] = "\n".join(str(line) for line in updated if str(line).strip())


def _scrub_seed_conflict_reason_lines(
    identity: Dict[str, Any],
    blocked_title: str,
    expected_title: str,
    group: str,
) -> None:
    lines = _safe_list(identity.get("reason_lines"))
    if not lines or not blocked_title:
        return
    updated: List[Any] = []
    correction_added = False
    for line in lines:
        text = str(line)
        replacement: Optional[str] = None
        if blocked_title in text and "공식 제목:" in text:
            replacement = "- 공식 제목: 미확정 (judge seed conflict; 후보/HOLD로 보존)"
        elif blocked_title in text and ("최종 공식 제목" in text or "확정됨" in text):
            replacement = "- 최종 공식 제목 확정 문구는 judge seed conflict guard로 철회됨."
        elif blocked_title in text and "관련 작품 토론으로 판정" in text:
            replacement = (
                "- 검색 후보는 보존하되, seed 기대 후보와 충돌하여 단일 공식 제목 "
                "확정은 보류함."
            )
        if replacement:
            if replacement not in updated:
                updated.append(replacement)
            correction_added = True
        else:
            updated.append(line)
    note = (
        f"- public title promotion blocked: judge_{group}_seed_conflict"
        + (f" ({blocked_title} != {expected_title})" if expected_title else "")
    )
    if correction_added and note not in updated:
        updated.append(note)
    identity["reason_lines"] = updated
    if correction_added:
        identity["reason"] = "\n".join(str(line) for line in updated if str(line).strip())


def noisy_expected_seed_candidate_lint_reasons(
    identity: Dict[str, Any],
    judge_seed: Optional[Dict[str, Any]] = None,
) -> List[str]:
    seed = nested_dict(judge_seed)
    expected_title = _safe_str(seed.get("independent_official_title") or seed.get("expected_title"))
    if not expected_title:
        return []
    group = seed_group(_judge_disagreement_type(seed), seed)
    if group not in {"hygiene", "recall"}:
        return []
    candidates = _safe_list(identity.get("title_candidates"))
    concrete_non_expected = [
        candidate_name(item)
        for item in candidates
        if isinstance(item, dict)
        and candidate_name(item)
        and not _matches_judge_expected_title_member(candidate_name(item), seed)
        and _safe_str(item.get("source_tier")).lower() in {"official_detail", "mixed"}
    ]
    if not concrete_non_expected:
        return []
    expected_present = any(_matches_judge_expected_title_member(candidate_name(item), seed) for item in candidates)
    if not expected_present:
        return [f"judge_{group}_seed_expected_candidate_missing_with_concrete_alternates"]
    if len(concrete_non_expected) >= 2:
        return [f"judge_{group}_seed_expected_candidate_polluted_by_concrete_alternates"]
    return []


def identity_consistency_lint_reasons(
    identity: Dict[str, Any],
    judge_seed: Optional[Dict[str, Any]] = None,
) -> List[str]:
    title = official_title(identity)
    disagreement_type = _judge_disagreement_type(judge_seed)
    reasons: List[str] = []
    if title and identity.get("is_resolved_work_discussion") is False:
        reasons.append("official_title_present_when_is_resolved_work_discussion_false")
    if title and identity.get("is_relevant") is False:
        reasons.append("official_title_present_when_is_relevant_false")
    if seed_group(disagreement_type, judge_seed) == "precision" and title:
        reasons.append(f"judge_precision_seed_{disagreement_type}")
    return reasons


def output_consistency_lint_reasons(
    identity: Dict[str, Any],
    judge_seed: Optional[Dict[str, Any]] = None,
) -> List[str]:
    disagreement_type = _judge_disagreement_type(judge_seed)
    reasons: List[str] = _safe_list(identity.get("output_consistency_lint"))
    is_relevant = identity.get("is_relevant")
    discussion_type = _safe_str(identity.get("discussion_type")).lower()
    if is_relevant is False and discussion_type in CORE_DISCUSSION_TYPES:
        reasons.append(f"is_relevant_false_with_core_discussion_type_{discussion_type}")
    if is_relevant is True and discussion_type in {"off_topic", "noise"}:
        reasons.append(f"is_relevant_true_with_non_relevant_discussion_type_{discussion_type}")
    work_resolution = _safe_str(identity.get("work_resolution")).lower()
    if work_resolution == "resolved" and not official_title(identity):
        reasons.append("work_resolution_resolved_without_official_title")
    if disagreement_type == "title_noisy_ocr" and title_noisy_ocr_resolved_by_official_evidence(identity):
        return reasons
    if disagreement_type == "title_noisy_ocr" and not official_title(identity) and _unresolved_hold_signal(identity):
        return reasons
    group = seed_group(disagreement_type, judge_seed)
    if group == "hygiene":
        reasons.append(f"judge_hygiene_seed_{disagreement_type}")
    if group == "candidate" and official_title(identity):
        reasons.append(f"judge_candidate_seed_requires_preservation_{disagreement_type}")
    return list(dict.fromkeys(reasons))


def _unresolved_hold_signal(identity: Dict[str, Any]) -> bool:
    state = _safe_str(identity.get("title_resolution_state")).lower()
    work_resolution = _safe_str(identity.get("work_resolution")).lower()
    return bool(
        identity.get("is_novel_related") is True
        or state in HOLD_STATES
        or work_resolution in UNRESOLVED_WORK_STATES
    )


def build_candidate_ledger(
    identity: Dict[str, Any],
    judge_seed: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    candidates = collect_candidate_titles(identity)
    return {
        "pipeline_official_title": official_title(identity) or None,
        "blocked_official_title": identity.get("blocked_official_title"),
        "blocked_official_title_url": identity.get("blocked_official_title_url"),
        "promotion_blocked_reasons": _safe_list(identity.get("promotion_blocked_reasons")),
        "title_candidates": candidates,
        "candidate_count": len(candidates),
        "candidate_preservation_sources": _safe_list(identity.get("candidate_preservation_sources")),
        "title_resolution_state": identity.get("title_resolution_state"),
        "title_resolution_allowed": identity.get("title_resolution_allowed"),
        "work_resolution": identity.get("work_resolution"),
        "discussion_type": identity.get("discussion_type"),
        "topicality": identity.get("topicality"),
        "is_relevant": identity.get("is_relevant"),
        "is_novel_related": identity.get("is_novel_related"),
        "is_resolved_work_discussion": identity.get("is_resolved_work_discussion"),
        "anchor_type": identity.get("anchor_type"),
        "anchor_strength": identity.get("anchor_strength"),
        "context_sources": _safe_list(identity.get("context_sources")),
        "has_evidence_catalog": has_evidence_catalog(identity),
        "judge_seed_bucket": _judge_seed_bucket(judge_seed) or None,
        "judge_seed_group": seed_group(_judge_disagreement_type(judge_seed), judge_seed),
        "judge_disagreement_type": _judge_disagreement_type(judge_seed) or None,
        "judge_expected_title": nested_dict(judge_seed).get("independent_official_title"),
        "judge_expected_url": nested_dict(judge_seed).get("independent_url"),
    }


def classify_candidate_audit(
    identity: Dict[str, Any],
    judge_seed: Optional[Dict[str, Any]] = None,
) -> str:
    title = official_title(identity)
    candidates = collect_candidate_titles(identity)
    disagreement_type = _judge_disagreement_type(judge_seed)
    group = seed_group(disagreement_type, judge_seed)

    if official_title_lint_reasons(identity):
        return "official_title_lint"
    if identity_consistency_lint_reasons(identity, judge_seed):
        return "identity_consistency_lint"
    if output_consistency_lint_reasons(identity, judge_seed) and group in {"hygiene", "candidate"}:
        return "output_consistency_lint"
    if title:
        return "safe_resolved"
    if group == "hygiene" and disagreement_type == "title_noisy_ocr" and _unresolved_hold_signal(identity):
        return "hold_unresolved"
    if candidates:
        return "promotion_blocked"
    if group == "precision":
        return "promotion_blocked"
    if group == "candidate":
        return "hold_without_candidates" if _unresolved_hold_signal(identity) else "candidate_generation_miss"
    if group == "recall":
        return "hold_without_candidates" if _unresolved_hold_signal(identity) else "candidate_generation_miss"
    if _unresolved_hold_signal(identity):
        return "hold_without_candidates"
    if output_consistency_lint_reasons(identity, judge_seed):
        return "output_consistency_lint"
    return "review_only"


NOISY_LLM_ONLY_CANDIDATE_FIELDS = (
    "title_candidates",
    "mentioned_works",
    "recommendation_candidates",
    "secondary_reference_works",
    "candidate_preservation_sources",
)


def _candidate_item_url(item: Dict[str, Any]) -> str:
    return _safe_str(item.get("heretic_url") or item.get("url"))


def _weak_candidate_surface_is_noisy(
    item: Dict[str, Any],
    judge_seed: Optional[Dict[str, Any]] = None,
) -> bool:
    source_tier = _safe_str(item.get("source_tier")).lower()
    if source_tier not in {"llm_only", "comment_surface"}:
        return False
    if _candidate_item_url(item):
        return False
    name = candidate_name(item)
    if not name:
        return False
    if _matches_judge_expected_title_member(name, judge_seed):
        return False
    if source_tier == "comment_surface" and not _clean_comment_surface_candidate(name):
        return True
    tokens = _title_tokens(name)
    if len(tokens) > 4:
        return True
    if re.search(r"[ㅋㅎㅠㅜ]{2,}|[!?！？]", name):
        return True
    if re.search(r"(?:시발|씨발|존나|언제와|낫냐|아쉬웠|이후로|그닥|하네|잖아|였음|소개문|기분인데)", name):
        return True
    if "dc app" in name.lower() or name.startswith("ㄹㅇ"):
        return True
    if len(_compact_title(name)) > 18 and re.search(r"(?:은|는|이|가|을|를|에서|으로|하고)", name):
        return True
    return False


def prune_noisy_llm_only_candidates(
    identity: Dict[str, Any],
    judge_seed: Optional[Dict[str, Any]] = None,
) -> List[str]:
    if not isinstance(identity, dict):
        return []
    removed: List[str] = []
    for field in NOISY_LLM_ONLY_CANDIDATE_FIELDS:
        value = identity.get(field)
        if not isinstance(value, list):
            continue
        kept: List[Any] = []
        for item in value:
            if isinstance(item, dict) and _weak_candidate_surface_is_noisy(item, judge_seed):
                name = candidate_name(item)
                if name and name not in removed:
                    removed.append(name)
                continue
            kept.append(item)
        if len(kept) != len(value):
            identity[field] = kept
    if removed:
        identity["candidate_pruned_llm_only_surfaces"] = removed
        _append_unique_list(identity, "candidate_audit_lint", ["llm_only_sentence_candidate_pruned"])
    return removed


def build_candidate_audit_fields(
    identity: Dict[str, Any],
    judge_seed: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    ledger = build_candidate_ledger(identity, judge_seed)
    existing_official_lint = _safe_list(identity.get("official_title_lint"))
    official_lint = list(dict.fromkeys(existing_official_lint + official_title_lint_reasons(identity)))
    identity_lint = identity_consistency_lint_reasons(identity, judge_seed)
    output_lint = output_consistency_lint_reasons(identity, judge_seed)
    existing_candidate_lint = _safe_list(identity.get("candidate_audit_lint"))
    candidate_lint = list(
        dict.fromkeys(existing_candidate_lint + noisy_expected_seed_candidate_lint_reasons(identity, judge_seed))
    )
    status = classify_candidate_audit(identity, judge_seed)
    fields: Dict[str, Any] = {
        "candidate_ledger": {
            **ledger,
            "official_title_lint_reasons": official_lint,
            "identity_consistency_lint_reasons": identity_lint,
            "output_consistency_lint_reasons": output_lint,
            "candidate_audit_lint_reasons": candidate_lint,
        },
        "candidate_ledger_status": status,
        "candidate_generation_miss": status == "candidate_generation_miss",
        "promotion_blocked": status == "promotion_blocked",
        "hold_unresolved": status == "hold_unresolved",
        "hold_without_candidates": status == "hold_without_candidates",
        "safe_resolved": status == "safe_resolved",
        "official_title_lint": official_lint,
        "identity_consistency_lint": identity_lint,
        "output_consistency_lint": output_lint,
        "candidate_audit_lint": candidate_lint,
    }
    return fields


def apply_candidate_audit_fields(
    identity: Dict[str, Any],
    judge_seed: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not isinstance(identity, dict):
        return {}
    prune_noisy_llm_only_candidates(identity, judge_seed)
    fields = build_candidate_audit_fields(identity, judge_seed)
    identity.update(fields)
    consistency_flags = identity.get("consistency_flags")
    if not isinstance(consistency_flags, list):
        consistency_flags = []
    for key in ("official_title_lint", "identity_consistency_lint", "output_consistency_lint", "candidate_audit_lint"):
        for reason in fields.get(key) or []:
            if reason not in consistency_flags:
                consistency_flags.append(reason)
    if consistency_flags:
        identity["consistency_flags"] = consistency_flags
    return fields


def slang_audit(identity: Dict[str, Any]) -> Dict[str, Any]:
    """Deterministic axis-D slang precompute (no LLM).

    Wraps the slang_db gate helpers (_is_generic_term / _is_exact_title_alias /
    _example_has_polluted_alias_seed_signal / _is_unresolvable_memory_query_context)
    to derive the §2.3 FULL_POST_JUDGE precomputed slang fields directly from an
    identity dict. This is additive: it does not mutate identity and matches the
    deterministic-first routing in the runbook so only rows that actually need
    axis-D judging are routed to the LLM.

    Returns the six precomputed slang fields:
      slang_present, slang_store_in_db, slang_pollution_suspect,
      slang_suspect_reasons, slang_axis_route, deterministic_slang_verdict.
    """
    # Imported lazily so candidate_audit stays importable even if slang_db's
    # optional deps are unavailable in a given context.
    from llm_batch.slang_db import (  # noqa: WPS433 (intentional local import)
        _example_has_polluted_alias_seed_signal,
        _is_exact_title_alias,
        _is_generic_term,
        _is_unresolvable_memory_query_context,
        _normalize_term,
        _normalize_title,
    )

    ident = identity if isinstance(identity, dict) else {}
    slang = nested_dict(ident.get("slang_insight"))

    detected_term = _safe_str(slang.get("detected_term"))
    decoded_term = _safe_str(slang.get("decoded_term"))
    canonical_alias = _safe_str(slang.get("canonical_work_alias"))
    alias_scope = _safe_str(slang.get("alias_scope"))
    decode_verified = slang.get("decode_verified") is True
    store_in_db = slang.get("store_in_slang_db") is True
    title = official_title(ident)

    # The probe term mirrors what the pipeline would store: prefer the canonical
    # alias surface, then detected term, then decoded term.
    probe_term = canonical_alias or detected_term or decoded_term

    # slang_present: a slang/alias surface is exposed (store candidacy OR a
    # non-generic decoded alias term present).
    decoded_alias_present = bool(probe_term) and not _is_generic_term(probe_term)
    slang_present = bool(store_in_db or decoded_alias_present)

    # Build the example dict slang_db expects from identity.
    example = {
        "consistency_flags": _safe_list(ident.get("consistency_flags")),
        "title_resolution_state": ident.get("title_resolution_state"),
        "title_resolution_allowed": ident.get("title_resolution_allowed"),
        "subtype": ident.get("subtype"),
        "work_resolution": ident.get("work_resolution"),
        "discussion_type": ident.get("discussion_type"),
        "official_title": title,
        "alias": probe_term,
    }

    memory_query_context = _is_unresolvable_memory_query_context(
        title_resolution_state=_safe_str(ident.get("title_resolution_state")),
        title_resolution_allowed=ident.get("title_resolution_allowed"),
        subtype=_safe_str(ident.get("subtype")),
        work_resolution=_safe_str(ident.get("work_resolution")),
        discussion_type=_safe_str(ident.get("discussion_type")),
    )
    polluted_seed_signal = _example_has_polluted_alias_seed_signal(example)
    exact_title_alias = bool(probe_term) and _is_exact_title_alias(probe_term, title)

    # one-alias-many-works: the same canonical alias is mapped to more than one
    # *distinct* candidate work title within this row. Near-duplicate phrasings of
    # the same work (e.g. "...무림에 떨어지다" vs "...무림 속에 떨어지다") must collapse,
    # so dedupe with the module's fuzzy _titles_match plus a high compact-string
    # similarity ratio rather than exact normalized equality.
    alias_norm = _normalize_term(probe_term)
    distinct_titles: List[str] = []
    if alias_norm:
        for cand in ([title] if title else []) + collect_candidate_titles(ident):
            cand = _safe_str(cand)
            if not cand:
                continue
            if any(_same_work_title(cand, existing) for existing in distinct_titles):
                continue
            distinct_titles.append(cand)
    one_alias_many_works = bool(store_in_db and alias_norm and len(distinct_titles) > 1)

    # The alias-seed pollution helpers (_example_has_polluted_alias_seed_signal /
    # _is_unresolvable_memory_query_context) are designed to score a seed *example*
    # (an alias->title mapping). On rows with no slang/alias surface they merely
    # echo general title-resolution state (e.g. nonwork/context_only), which is NOT
    # an alias-pollution signal and would needlessly route work-less rows to the
    # axis-D LLM. So those two signals only count when a real alias surface exists
    # (store candidacy or a non-generic decoded alias term). This keeps the route
    # scoped to rows that actually need axis-D judging.
    alias_surface_present = bool(store_in_db or decoded_alias_present)

    reasons: List[str] = []
    # §2.3 ANY conditions for pollution suspect.
    if store_in_db and not decode_verified:
        reasons.append("store_without_decode_verified")
    if store_in_db and not title:
        reasons.append("store_without_official_title")
    if store_in_db and alias_scope and alias_scope != "pure_work_alias":
        reasons.append("store_with_non_pure_alias_scope")
    if store_in_db and exact_title_alias:
        reasons.append("exact_title_alias_stored")
    if alias_surface_present and memory_query_context:
        reasons.append("memory_query_context")
    if alias_surface_present and polluted_seed_signal:
        reasons.append("polluted_alias_seed_signal")
    if one_alias_many_works:
        reasons.append("one_alias_many_works")
    if not store_in_db and decoded_alias_present and _is_generic_term(probe_term):
        # Defensive: generic term should not be considered a real alias surface.
        reasons.append("generic_term")

    # De-duplicate while preserving order.
    suspect_reasons = list(dict.fromkeys(reasons))
    slang_pollution_suspect = bool(suspect_reasons)

    slang_axis_route = "llm" if (store_in_db or slang_pollution_suspect) else "deterministic_na"

    if slang_axis_route == "deterministic_na":
        deterministic_slang_verdict = "na"
    elif slang_pollution_suspect:
        deterministic_slang_verdict = "pollution_risk"
    else:
        # store_in_db == true with no suspect signals -> deterministic ok start point.
        deterministic_slang_verdict = "ok"

    return {
        "slang_present": slang_present,
        "slang_store_in_db": store_in_db,
        "slang_pollution_suspect": slang_pollution_suspect,
        "slang_suspect_reasons": suspect_reasons,
        "slang_axis_route": slang_axis_route,
        "deterministic_slang_verdict": deterministic_slang_verdict,
    }
