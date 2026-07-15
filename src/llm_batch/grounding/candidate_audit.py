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
GENERIC_NON_TITLE_SURFACES = {"광고", "공지", "없음", "미상", "불명"}
GENERIC_WORK_SURFACE_TITLES = {
    "용사파티",
    "용사 파티",
}
PROMOTION_BLOCKING_OFFICIAL_TITLE_LINT_REASONS = {
    "official_title_looks_like_url_or_domain",
    "official_title_looks_like_generic_non_title_surface",
    "official_title_looks_like_generic_evidence_label",
    "official_title_looks_like_search_snippet",
    "official_title_looks_like_breadcrumb",
    "official_title_looks_like_listing_description",
}
WEAK_PRIMARY_SOURCE_TIERS = {"", "community", "llm_only", "search_only", "web"}
OFFICIAL_TITLE_SOURCE_TIERS = {"official_detail", "novel_platform"}
BATCH_ALIAS_COMPETING_HOLD_FLAGS = {
    "official_url_recall_blocked_competing_candidate",
    "multi_work_title_cleared",
    "secondary_reference_official_alias_blocked_after_multi_work_title_cleared",
}
BATCH_ALIAS_CONFLICT_HOLD_FLAGS = BATCH_ALIAS_COMPETING_HOLD_FLAGS | {
    "expert_conflict",
    "budget_quarantine_candidate",
}
TITLE_LED_ALIAS_EXEMPT_FLAGS = {
    "batch_memory_alias_rescue_cleared_stale_demotions",
    "weak_public_title_bridge_batch_alias_exact_exempt",
    "title_lead_alias_official_detail_release",
}
TITLE_LED_WORK_CONSUMPTION_RE = re.compile(
    r"(이벤트|무료분|무료\s*분|기다무|무료화|유료화|봐야|볼까|보는중|보는\s*중|"
    r"봤다|봤는데|봤음|보고옴|먹어볼|찍먹|달릴까|정주행|하차|연중|연재\s*중단|"
    r"연재중단|휴재|완결|죽어버림|뒤져버림|아까움|아깝|볼\s*만(?:하|한|함|했)|"
    r"좋(?:았|네|다|음|구나|아)|"
    r"재(?:밌|밋)(?:게\s*봤|네|다|음|냐|나|어|었|더라|긴|고|게)?|"
    r"재(?:미있|미잇)(?:네|다|음|냐|나|어|었|더라|긴|고|게)?)"
)
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


def has_authoritative_publish_contract(identity: Any) -> bool:
    """Return whether *identity* carries an authoritative v2 contract marker.

    The serializer/final-sync contract deliberately accepts structural markers
    when a lossy intermediate writer drops an explicit version field.  Every
    pre-audit mutation guard must use the same predicate; otherwise a v2 row can
    be changed by legacy candidate/title helpers before final sync fail-closes
    the mismatch.
    """
    if not isinstance(identity, dict):
        return False
    ledger = nested_dict(identity.get("candidate_ledger"))
    decision = nested_dict(identity.get("promotion_decision"))
    ledger_decision = nested_dict(ledger.get("promotion_decision"))
    contract_version = _safe_str(
        identity.get("publish_contract_version")
        or ledger.get("publish_contract_version")
        or decision.get("contract_version")
        or ledger_decision.get("contract_version")
    )
    root_marker = bool(
        isinstance(identity.get("promotion_gate_state"), dict)
        and isinstance(identity.get("promotion_gate_evidence"), list)
        and isinstance(identity.get("publish_contract_trace"), dict)
    )
    ledger_marker = bool(
        isinstance(ledger.get("promotion_gate_state"), dict)
        and isinstance(ledger.get("promotion_gate_evidence"), list)
        and isinstance(ledger.get("publish_contract_trace"), dict)
    )
    return bool(
        contract_version == "promotion_contract_v2"
        or root_marker
        or ledger_marker
    )


def _has_authoritative_publish_contract(identity: Any) -> bool:
    """Backward-compatible private alias for legacy helper call sites."""
    return has_authoritative_publish_contract(identity)


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
    if name.startswith("@"):
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
        " - 판타지 e북",
        " - 판타지 웹소설",
        " - 리디",
        " - 노벨피아",
        " | 카카오페이지",
    ):
        if suffix in title:
            title = title.split(suffix, 1)[0]
    return title.strip(" -")


def _official_support_title_matches(expected: Any, observed: Any) -> bool:
    return bool(
        _titles_match(expected, observed)
        or _titles_match(expected, _clean_evidence_title(observed))
        or _title_surface_compatible(expected, observed)
    )


def _author_angle_inner_title(value: Any) -> str:
    title = _safe_str(value)
    if not title:
        return ""
    match = re.fullmatch(r"(.{1,40}?)\s*[<〈《]\s*(.{2,80}?)\s*[>〉》]\s*", title)
    if not match:
        return ""
    prefix = match.group(1).strip()
    inner = match.group(2).strip()
    if not prefix or not inner:
        return ""
    if _looks_like_url_or_domain(prefix) or _looks_like_url_or_domain(inner):
        return ""
    if _compact_title(prefix) == _compact_title(inner):
        return ""
    return inner


def _candidate_dicts_for_canonicalization(identity: Dict[str, Any]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for field in (
        "primary_work",
        "title_candidates",
        "mentioned_works",
        "secondary_reference_works",
        "candidate_preservation_sources",
        "recommendation_candidates",
    ):
        value = identity.get(field)
        if isinstance(value, dict):
            items.append(value)
        elif isinstance(value, list):
            items.extend(_safe_dicts(value))
    return items


def apply_author_angle_official_detail_canonicalization(identity: Dict[str, Any]) -> List[str]:
    """Prefer official detail title over author-prefixed search surfaces."""
    if not isinstance(identity, dict):
        return []
    if _has_authoritative_publish_contract(identity):
        return []

    current_title = official_title(identity)
    inner_title = _author_angle_inner_title(current_title)
    if not inner_title:
        return []

    canonical: Optional[Dict[str, Any]] = None
    for item in _candidate_dicts_for_canonicalization(identity):
        item_title = candidate_name(item)
        if not item_title or not _titles_match(inner_title, item_title):
            continue
        url = _official_detail_url(item.get("heretic_url") or item.get("url"))
        source_tier = _safe_str(item.get("source_tier")).lower()
        page_type = _safe_str(item.get("page_type")).lower()
        if not url:
            continue
        if source_tier not in {"official_detail", "novel_platform", "mixed", "official_search"}:
            continue
        if page_type and page_type not in {"novel_page", "official_detail"}:
            continue
        canonical = item
        break

    if canonical is None:
        return []

    canonical_title = candidate_name(canonical)
    canonical_url = _official_detail_url(canonical.get("heretic_url") or canonical.get("url"))
    if not canonical_title or not canonical_url:
        return []

    novel_identity = nested_dict(identity.get("novel_identity"))
    if novel_identity:
        novel_identity["official_title"] = canonical_title
        novel_identity["heretic_url"] = canonical_url
        novel_identity["confidence"] = novel_identity.get("confidence") or canonical.get("confidence") or "High"
        identity["novel_identity"] = novel_identity
    identity["official_title"] = canonical_title
    identity["official_novel_title"] = canonical_title
    identity["resolved_title"] = canonical_title
    identity["heretic_url"] = canonical_url

    primary = dict(canonical)
    primary["official_title"] = canonical_title
    primary["heretic_url"] = canonical_url
    primary["reference_role"] = "primary"
    if not primary.get("confidence"):
        primary["confidence"] = novel_identity.get("confidence") if novel_identity else "High"
    if not primary.get("source_tier"):
        primary["source_tier"] = "official_detail"
    identity["primary_work"] = primary

    reason = "author_angle_official_detail_canonicalized"
    identity["author_angle_surface_title"] = current_title
    reason_text = _safe_str(identity.get("reason"))
    if reason_text and current_title in reason_text:
        identity["reason"] = reason_text.replace(current_title, canonical_title)
    reason_lines = _safe_list(identity.get("reason_lines"))
    if reason_lines:
        identity["reason_lines"] = [
            line.replace(current_title, canonical_title) if isinstance(line, str) else line
            for line in reason_lines
        ]
    _append_unique_list(identity, "output_consistency_lint", [reason])
    flags = identity.get("consistency_flags")
    if not isinstance(flags, list):
        flags = []
    if reason not in flags:
        flags.append(reason)
    identity["consistency_flags"] = flags
    return [reason]


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


def _description_like_title_surface(title: Any) -> bool:
    text = " ".join(_safe_str(title).split())
    key = _compact_title(text)
    if len(key) < 20:
        return False
    sentence_markers = ("…", "...", "?", "!", "[", "]", "되었다", "아니었다", "했더니", "아닌가")
    marker_hits = sum(1 for marker in sentence_markers if marker in text)
    if marker_hits >= 2:
        return True
    return len(_title_tokens(text)) >= 6 and any(marker in text for marker in ("다.", "요.", "했다", "한다"))


def _direct_hard_title_surface(identity: Dict[str, Any], title: Any) -> bool:
    title_key = _compact_title(title)
    if len(title_key) < 6:
        return False
    for field in ("post_core_text", "post_side_text"):
        if title_key in _compact_title(identity.get(field)):
            return True
    for item in _safe_dicts(identity.get("image_evidence_catalog")):
        image_title = candidate_name(
            {
                "title": item.get("explicit_work_title")
                or item.get("detected_title")
                or item.get("work_title")
            }
        )
        if not image_title or not _titles_match(title, image_title):
            continue
        role = _safe_str(item.get("title_role")).lower()
        if item.get("promotion_eligible") is True or role in {"work_title", "title"}:
            return True
    return False


def _official_title_looks_like_listing_description(identity: Dict[str, Any], title: Any) -> bool:
    """Detect a platform listing synopsis accidentally promoted as a title.

    Some platform listing/search pages put neighboring work descriptions in the
    result snippet. If a long sentence-like surface appears as snippet text on
    multiple *other* official-detail URLs, and the packet has no direct hard
    title surface, treat it as review-only candidate evidence.
    """
    title_text = _safe_str(title)
    title_key = _compact_title(title_text)
    if not title_key or not _description_like_title_surface(title_text):
        return False
    if _direct_hard_title_surface(identity, title_text):
        return False

    novel_identity = nested_dict(identity.get("novel_identity"))
    primary = nested_dict(identity.get("primary_work"))
    current_url = _official_detail_url(
        novel_identity.get("heretic_url")
        or identity.get("heretic_url")
        or primary.get("heretic_url")
        or primary.get("url")
    )
    if not current_url:
        return False

    other_url_snippet_hits = 0
    for evidence in _safe_dicts(identity.get("search_evidence_catalog")):
        evidence_url = _official_detail_url(evidence.get("url"))
        if not evidence_url or _official_detail_urls_match(current_url, evidence_url):
            continue
        evidence_title = candidate_name(evidence)
        if evidence_title and _titles_match(title_text, evidence_title):
            continue
        blob = _compact_title(
            " ".join(_safe_str(evidence.get(field)) for field in ("snippet", "content", "description"))
        )
        if title_key in blob:
            other_url_snippet_hits += 1
            if other_url_snippet_hits >= 2:
                return True
    return False


def _official_title_looks_like_breadcrumb(title: Any) -> bool:
    lowered = _safe_str(title).lower()
    if not lowered:
        return False
    return any(marker in lowered for marker in ("namu.wiki", "›", " - 나무위키"))


def _title_resolution_confirmed(identity: Dict[str, Any]) -> bool:
    state = _safe_str(identity.get("title_resolution_state")).lower()
    discussion_type = _safe_str(identity.get("discussion_type")).lower()
    return bool(
        identity.get("title_resolution_allowed") is not False
        and state in {"resolved", "direct_resolved"}
        and discussion_type in CORE_DISCUSSION_TYPES
    )


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
_WEAK_ALIAS_PHRASE_RE = re.compile(
    r"(?:정도로|같은|같은거|이런|저런|그런|뭐임|재밌냐|레전드임|현실)$"
)
WEAK_ALIAS_BRIDGE_TOKENS = {
    "되었다",
    "됐다",
    "되는",
    "되다",
    "빙의",
    "빙의했다",
    "빙의함",
    "환생",
    "환생했다",
    "회귀",
    "회귀했다",
    "한다",
    "하는",
    "하고",
    "없는",
    "있음",
    "있습니다",
    "있었다",
    "있다는",
    "있었음",
    "좋네",
    "좋다",
    "재밌냐",
    "같다",
    "생각나게",
    "요소",
    "회차",
    "회차를",
    "본문",
    "이미지",
    "작품",
    "게임적",
}


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
        title = _strip_platform_seo_title_suffix(_title_from_official_evidence(evidence))
        if not _usable_official_title_surface(title):
            continue
        candidates.append({"title": title, "url": url, "evidence": evidence, "source": "search_evidence"})

    for body_candidate in _safe_dicts(identity.get("body_official_detail_candidates")):
        url = _official_detail_url(body_candidate.get("url"))
        title = _clean_evidence_title(body_candidate.get("title"))
        if url and _usable_official_title_surface(title):
            candidates.append({"title": title, "url": url, "evidence": body_candidate, "source": "body_url"})

    alias_clue_keys = {
        _compact_title(clue.get("alias") or clue.get("term"))
        for clue in _safe_dicts(identity.get("alias_clues"))
        if _compact_title(clue.get("alias") or clue.get("term"))
    }
    cue_texts: List[str] = [
        _safe_str(identity.get("post_core_text")),
        _safe_str(identity.get("post_side_text")),
    ]
    phrase_cue_texts: List[str] = []
    for image_evidence in _safe_dicts(identity.get("image_evidence_catalog")):
        cue_texts.append(_safe_str(image_evidence.get("ocr_text")))
        cue_texts.append(_safe_str(image_evidence.get("visual_summary")))
        for cue in _safe_list(image_evidence.get("work_cues")):
            cue_text = _safe_str(cue)
            cue_texts.append(cue_text)
            phrase_cue_texts.append(cue_text)

    cue_keys: set[str] = set()

    def _add_cue_key(raw: Any) -> None:
        text = _safe_str(raw)
        key = _compact_title(text)
        if len(key) < 3:
            return
        if key in LOW_INFORMATION_ALIAS_CLUES or key in TITLE_TOKEN_STOPWORDS or key in WEAK_ALIAS_BRIDGE_TOKENS:
            return
        cue_keys.add(key)

    for cue_text in phrase_cue_texts:
        _add_cue_key(cue_text)
    for cue_text in cue_texts:
        for token in _title_tokens(cue_text):
            _add_cue_key(token)

    def _cue_overlap_score(title: str, evidence: Dict[str, Any]) -> int:
        if not cue_keys:
            return 0
        evidence_key = _compact_title(
            " ".join(_safe_str(evidence.get(field)) for field in ("title", "snippet", "content", "description"))
        )
        title_key = _compact_title(title)
        score = 0
        for cue_key in sorted(cue_keys, key=len, reverse=True):
            if cue_key not in evidence_key:
                continue
            if cue_key in alias_clue_keys:
                score += 1
                continue
            score += 4
            if cue_key and cue_key in title_key:
                score += 4
        return min(score, 24)

    def _anchor_score(anchor: str, evidence: Dict[str, Any], title: str) -> int:
        if anchor == "ocr_explicit_title":
            score = 140
        elif anchor == "official_url_in_body":
            score = 135
        elif anchor == "full_title_surface":
            score = 130
        elif anchor.startswith("confirmed_alias:"):
            score = 120
        elif anchor.startswith("bracket_alias:"):
            score = 116
        elif anchor.startswith("title_abbrev_form:"):
            score = 105
        elif anchor.startswith("official_page_alias_tag:"):
            score = 98
        elif anchor.startswith("title_unique_rare_token:"):
            score = 96
        else:
            return 0
        score += _cue_overlap_score(title, evidence)
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
        score = _anchor_score(anchor, candidate["evidence"], candidate["title"])
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


def _official_detail_candidate_preservation_recoverable(identity: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Recover official-detail candidates for ledger display only.

    This intentionally stays separate from ``official_url_recoverable`` because
    image/work-cue overlap is enough to preserve a candidate for review, but it
    is not enough to publish a public title.
    """

    if not isinstance(identity, dict) or official_title(identity):
        return None
    state = _safe_str(identity.get("title_resolution_state")).lower()
    if state in {"context_only", "unresolvable_memory_query", "nonwork"}:
        return None
    work_resolution = _safe_str(identity.get("work_resolution")).lower()
    if work_resolution and work_resolution not in {"none", "unresolved", "hold_unresolved", "hold", "multi_work"}:
        return None

    cue_keys: set[str] = set()

    def add_cue(raw: Any) -> None:
        key = _compact_title(raw)
        if len(key) < 3:
            return
        if key in LOW_INFORMATION_ALIAS_CLUES or key in TITLE_TOKEN_STOPWORDS:
            return
        cue_keys.add(key)

    for field in ("post_core_text", "post_side_text"):
        for token in _title_tokens(identity.get(field)):
            add_cue(token)
    for image_evidence in _safe_dicts(identity.get("image_evidence_catalog")):
        for cue in _safe_list(image_evidence.get("work_cues")):
            add_cue(cue)
        for token in _title_tokens(image_evidence.get("ocr_text")):
            add_cue(token)
        for token in _title_tokens(image_evidence.get("visual_summary")):
            add_cue(token)
    for clue in _safe_dicts(identity.get("alias_clues")):
        add_cue(clue.get("alias") or clue.get("term"))

    if not cue_keys:
        return None

    matches: List[Dict[str, Any]] = []
    for evidence in _safe_dicts(identity.get("search_evidence_catalog")):
        source_tier = _safe_str(evidence.get("source_tier")).lower()
        if source_tier not in OFFICIAL_TITLE_SOURCE_TIERS:
            continue
        url = _official_detail_url(evidence.get("url"))
        if not url:
            continue
        title = _strip_platform_seo_title_suffix(_title_from_official_evidence(evidence))
        if not _usable_official_title_surface(title):
            continue
        evidence_blob = _compact_title(
            " ".join(_safe_str(evidence.get(field)) for field in ("title", "snippet", "content", "description"))
        )
        matched_cues = [cue for cue in sorted(cue_keys, key=len, reverse=True) if cue in evidence_blob]
        if not matched_cues:
            continue
        rank = evidence.get("rank")
        rank_penalty = min(rank, 25) if isinstance(rank, int) else 0
        score = max(len(cue) for cue in matched_cues) * 10 - rank_penalty
        matches.append(
            {
                "score": score,
                "official_title": title,
                "heretic_url": url,
                "source_tier": "official_detail",
                "source": "search_evidence_candidate_preservation",
                "matched_clue": "official_detail_candidate_cue:" + matched_cues[0],
                "confidence": "Medium",
            }
        )

    if not matches:
        return None
    matches.sort(key=lambda item: item["score"], reverse=True)
    best = dict(matches[0])
    best.pop("score", None)
    return best


def _candidate_source_matches_title(item: Any, title: str) -> bool:
    if not isinstance(item, dict) or not title:
        return False
    return _titles_match(title, candidate_name(item))


def _weak_comment_only_candidate(item: Any) -> bool:
    if not isinstance(item, dict):
        return False
    if _candidate_item_url(item):
        return False
    source_tier = _safe_str(item.get("source_tier")).lower()
    preservation_role = _safe_str(item.get("preservation_role")).lower()
    promotion_policy = _safe_str(item.get("promotion_policy")).lower()
    negative = {_safe_str(value).lower() for value in _safe_list(item.get("negative_evidence"))}
    return bool(
        source_tier in {"comment_surface", "community", "llm_only"}
        and (
            preservation_role in {"comment_surface_candidate", "recommendation_candidate"}
            or promotion_policy == "hold_without_promotion"
            or "comment_answer_preservation_only" in negative
        )
    )


def _blocked_title_is_weak_comment_only(identity: Dict[str, Any], title: str) -> bool:
    if not title or _safe_str(identity.get("blocked_official_title_url")):
        return False
    for field in (
        "title_candidates",
        "candidate_preservation_sources",
        "comment_surface_title_candidates",
        "recommendation_candidates",
    ):
        value = identity.get(field)
        values = value if isinstance(value, list) else [value]
        for item in values:
            if isinstance(item, str):
                if _titles_match(title, item):
                    return True
                continue
            if _weak_comment_only_candidate(item) and _candidate_source_matches_title(item, title):
                return True
    return False


def preserve_recoverable_official_detail_candidate(identity: Dict[str, Any]) -> List[str]:
    """Keep official-detail recall evidence as candidate-only review material.

    This does not publish the title. It only prevents weak comment-only surfaces
    from becoming the representative blocked candidate when a recoverable
    official-detail candidate is already present in search evidence.
    """

    recovered = official_url_recoverable(identity) or _official_detail_candidate_preservation_recoverable(identity)
    if not recovered:
        return []
    title = _safe_str(recovered.get("official_title"))
    url = _safe_str(recovered.get("heretic_url"))
    if not title:
        return []

    changed: List[str] = []
    title_candidates = identity.get("title_candidates")
    if not isinstance(title_candidates, list):
        title_candidates = []
    has_title_candidate = any(
        isinstance(item, dict)
        and _candidate_source_matches_title(item, title)
        and (not url or _official_detail_urls_match(url, item.get("heretic_url") or item.get("url")))
        for item in title_candidates
    )
    if not has_title_candidate:
        entry: Dict[str, Any] = {
            "official_title": title,
            "source_tier": "official_detail",
            "reference_role": "candidate",
            "preservation_role": "title_candidate",
            "promotion_policy": "hold_without_promotion",
            "matched_clue": recovered.get("matched_clue"),
            "candidate_preservation_reason": "official_url_recall_candidate_preserved",
        }
        if url:
            entry["heretic_url"] = url
        if recovered.get("confidence"):
            entry["confidence"] = recovered.get("confidence")
        title_candidates.insert(0, entry)
        identity["title_candidates"] = title_candidates
        changed.append("official_url_recall_candidate_preserved")

    sources = identity.get("candidate_preservation_sources")
    if not isinstance(sources, list):
        sources = []
    has_source = any(
        isinstance(item, dict)
        and _candidate_source_matches_title(item, title)
        and (not url or _official_detail_urls_match(url, item.get("heretic_url") or item.get("url")))
        for item in sources
    )
    if not has_source:
        source_entry: Dict[str, Any] = {
            "official_title": title,
            "source_tier": "official_detail",
            "reference_role": "candidate",
            "preservation_role": "title_candidate",
            "promotion_policy": "hold_without_promotion",
            "matched_clue": recovered.get("matched_clue"),
            "candidate_preservation_reason": "official_url_recall_candidate_preserved",
            "confidence": recovered.get("confidence") or "Medium",
        }
        if url:
            source_entry["heretic_url"] = url
        sources.insert(0, source_entry)
        identity["candidate_preservation_sources"] = sources
        changed.append("official_url_recall_candidate_source_preserved")

    blocked_title = _safe_str(identity.get("blocked_official_title"))
    if blocked_title and not _titles_match(blocked_title, title) and _blocked_title_is_weak_comment_only(identity, blocked_title):
        identity["comment_surface_blocked_official_title"] = blocked_title
        identity["blocked_official_title"] = title
        if url:
            identity["blocked_official_title_url"] = url
        identity["blocked_official_title_confidence"] = recovered.get("confidence") or "Medium"
        changed.append("blocked_candidate_representative_upgraded_to_official_detail")

    if changed:
        _append_unique_list(identity, "candidate_audit_lint", changed)
        _append_unique_list(identity, "consistency_flags", changed)
    return changed


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


def _official_detail_urls_match(expected: Any, observed: Any) -> bool:
    expected_detail = _official_detail_url(expected)
    observed_detail = _official_detail_url(observed)
    if expected_detail or observed_detail:
        return bool(expected_detail and observed_detail and expected_detail == observed_detail)
    return _urls_match(expected, observed)


def official_search_supports_title(identity: Dict[str, Any], title: str) -> bool:
    for evidence in _safe_dicts(identity.get("search_evidence_catalog")):
        source_tier = _safe_str(evidence.get("source_tier")).lower()
        if source_tier not in OFFICIAL_TITLE_SOURCE_TIERS:
            continue
        if _official_support_title_matches(title, evidence.get("title")):
            return True
    return False


def _official_evidence_mentions_title(identity: Dict[str, Any], title: str) -> bool:
    title_key = _compact_title(title)
    if not title_key or len(title_key) < 4:
        return False
    for evidence in _safe_dicts(identity.get("search_evidence_catalog")):
        source_tier = _safe_str(evidence.get("source_tier")).lower()
        if source_tier not in OFFICIAL_TITLE_SOURCE_TIERS:
            continue
        text = " ".join(
            _safe_str(evidence.get(key))
            for key in ("title", "snippet", "content")
            if _safe_str(evidence.get(key))
        )
        if title_key in _compact_title(text):
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
        "candidate_preservation_sources",
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


def _official_detail_support_dicts(identity: Dict[str, Any]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    def add_item(item: Dict[str, Any]) -> None:
        title = candidate_name(item)
        url = _official_detail_url(item.get("heretic_url") or item.get("url"))
        source_tier = _safe_str(item.get("source_tier")).lower()
        if not title or not url or source_tier not in OFFICIAL_TITLE_SOURCE_TIERS | {"mixed", "official_search"}:
            return
        page_type = _safe_str(item.get("page_type")).lower()
        if page_type and not any(marker in page_type for marker in ("novel_page", "official_detail", "unknown")):
            return
        if not _usable_official_title_surface(title):
            return
        key = (_compact_title(title), url, source_tier)
        if key in seen:
            return
        seen.add(key)
        items.append(item)

    for item in _candidate_dicts_for_canonicalization(identity):
        add_item(item)
    for evidence in _safe_dicts(identity.get("search_evidence_catalog")):
        add_item(evidence)
    for body_candidate in _safe_dicts(identity.get("body_official_detail_candidates")):
        add_item(body_candidate)
    return items


def _apply_same_url_official_detail_canonicalization(identity: Dict[str, Any]) -> List[str]:
    if _has_authoritative_publish_contract(identity):
        return []
    current_title = official_title(identity)
    if not current_title:
        return []
    novel_identity = nested_dict(identity.get("novel_identity"))
    primary = nested_dict(identity.get("primary_work"))
    current_url = _official_detail_url(
        novel_identity.get("heretic_url")
        or identity.get("heretic_url")
        or primary.get("heretic_url")
        or primary.get("url")
    )
    if not current_url:
        return []

    current_key = _compact_title(current_title)
    better: List[Dict[str, Any]] = []
    for item in _official_detail_support_dicts(identity):
        item_title = candidate_name(item)
        item_url = _official_detail_url(item.get("heretic_url") or item.get("url"))
        item_key = _compact_title(item_title)
        if not item_title or not _urls_match(current_url, item_url):
            continue
        if item_key == current_key or len(item_key) <= len(current_key):
            continue
        if not (
            _titles_match(current_title, item_title)
            or (len(current_key) >= 6 and current_key in item_key)
        ):
            continue
        better.append(item)
    if not better:
        return []

    better.sort(key=lambda item: len(_compact_title(candidate_name(item))), reverse=True)
    canonical = better[0]
    canonical_title = candidate_name(canonical)
    canonical_url = _official_detail_url(canonical.get("heretic_url") or canonical.get("url"))
    if not canonical_title or not canonical_url:
        return []

    if novel_identity:
        novel_identity["official_title"] = canonical_title
        novel_identity["heretic_url"] = canonical_url
        novel_identity["confidence"] = novel_identity.get("confidence") or canonical.get("confidence") or "High"
        identity["novel_identity"] = novel_identity
    for key in ("official_title", "official_novel_title", "resolved_title"):
        if key in identity:
            identity[key] = canonical_title
    identity["heretic_url"] = canonical_url

    _retitle_candidate_dicts(identity, current_title, canonical_title, canonical_url)
    primary = nested_dict(identity.get("primary_work"))
    if primary:
        primary["official_title"] = canonical_title
        primary["heretic_url"] = canonical_url
        primary["reference_role"] = "primary"
        if not primary.get("source_tier"):
            primary["source_tier"] = "official_detail"
        identity["primary_work"] = primary

    reason = "same_url_official_detail_canonicalized"
    identity["same_url_official_detail_surface_title"] = current_title
    _append_unique_list(identity, "output_consistency_lint", [reason])
    flags = identity.get("consistency_flags")
    if not isinstance(flags, list):
        flags = []
    if reason not in flags:
        flags.append(reason)
    identity["consistency_flags"] = flags
    return [reason]


def _apply_same_url_official_page_title_over_alias_canonicalization(identity: Dict[str, Any]) -> List[str]:
    if _has_authoritative_publish_contract(identity):
        return []
    current_title = official_title(identity)
    if not current_title:
        return []
    novel_identity = nested_dict(identity.get("novel_identity"))
    primary = nested_dict(identity.get("primary_work"))
    current_url = _official_detail_url(
        novel_identity.get("heretic_url")
        or identity.get("heretic_url")
        or primary.get("heretic_url")
        or primary.get("url")
    )
    if not current_url:
        return []

    current_key = _compact_title(current_title)
    alias_key = _compact_title(primary.get("alias_or_mention"))
    if not current_key or alias_key != current_key:
        return []

    better: List[Dict[str, Any]] = []
    for item in _official_detail_support_dicts(identity):
        item_url = _official_detail_url(item.get("heretic_url") or item.get("url"))
        if not _official_detail_urls_match(current_url, item_url):
            continue
        item_title = _strip_platform_seo_title_suffix(_title_from_official_evidence(item) or candidate_name(item))
        item_key = _compact_title(item_title)
        if not item_title or not item_key or item_key == current_key:
            continue
        if not _usable_official_title_surface(item_title):
            continue
        if _titles_match(current_title, item_title) or current_key in item_key:
            continue
        better.append(dict(item, official_title=item_title, heretic_url=item_url))
    if not better:
        return []

    better.sort(key=lambda item: len(_compact_title(candidate_name(item))), reverse=True)
    canonical = better[0]
    canonical_title = candidate_name(canonical)
    canonical_url = _official_detail_url(canonical.get("heretic_url") or canonical.get("url"))
    if not canonical_title or not canonical_url:
        return []

    if novel_identity:
        novel_identity["official_title"] = canonical_title
        novel_identity["heretic_url"] = canonical_url
        novel_identity["confidence"] = novel_identity.get("confidence") or canonical.get("confidence") or "High"
        identity["novel_identity"] = novel_identity
    for key in ("official_title", "official_novel_title", "resolved_title"):
        if key in identity:
            identity[key] = canonical_title
    identity["heretic_url"] = canonical_url

    _retitle_candidate_dicts(identity, current_title, canonical_title, canonical_url)
    primary = nested_dict(identity.get("primary_work"))
    if primary:
        primary["official_title"] = canonical_title
        primary["heretic_url"] = canonical_url
        primary["reference_role"] = "primary"
        if not primary.get("source_tier"):
            primary["source_tier"] = "official_detail"
        identity["primary_work"] = primary

    reason = "same_url_official_page_title_over_alias_canonicalized"
    identity["same_url_alias_surface_title"] = current_title
    _append_unique_list(identity, "output_consistency_lint", [reason])
    flags = identity.get("consistency_flags")
    if not isinstance(flags, list):
        flags = []
    if reason not in flags:
        flags.append(reason)
    identity["consistency_flags"] = flags
    return [reason]


_PLATFORM_SEO_TITLE_SUFFIX_PATTERNS = (
    re.compile(r"\s*[-–—]\s*문피아\s*웹소설(?:\s*[-–—]\s*Munpia)?\s*$", re.IGNORECASE),
    re.compile(r"\s*[-–—]\s*웹소설\s*문피아(?:\s*[-–—]\s*Munpia)?\s*$", re.IGNORECASE),
    re.compile(r"\s*[-–—]\s*네이버\s*시리즈\s*$", re.IGNORECASE),
    re.compile(r"\s*[-–—]\s*카카오페이지\s*$", re.IGNORECASE),
    re.compile(r"\s*[-–—]\s*노벨피아\s*$", re.IGNORECASE),
)
_PLATFORM_SEO_TITLE_PREFIX_PATTERNS = (
    re.compile(r"^\s*웹소설로\s*꿈꾸는\s*세상!\s*[-–—]\s*", re.IGNORECASE),
)


def _normalize_common_title_surface_ocr(title: Any) -> str:
    text = _safe_str(title)
    if not text:
        return ""
    text = re.sub(r"(?i)(?<![a-z])l\s*p\s*코", "럽코", text)
    text = re.sub(r"럽\s+코", "럽코", text)
    return text.strip()


def _strip_platform_seo_title_suffix(title: Any) -> str:
    current = _normalize_common_title_surface_ocr(title)
    if not current:
        return ""
    stripped = current
    for pattern in _PLATFORM_SEO_TITLE_PREFIX_PATTERNS:
        stripped = pattern.sub("", stripped).strip()
    for pattern in _PLATFORM_SEO_TITLE_SUFFIX_PATTERNS:
        stripped = pattern.sub("", stripped).strip()
    return _normalize_common_title_surface_ocr(stripped)


def _apply_platform_seo_title_suffix_canonicalization(identity: Dict[str, Any]) -> List[str]:
    if _has_authoritative_publish_contract(identity):
        return []
    current_title = official_title(identity)
    canonical_title = _strip_platform_seo_title_suffix(current_title)
    if not current_title or not canonical_title or canonical_title == current_title:
        return []
    if not _usable_official_title_surface(canonical_title):
        return []

    novel_identity = nested_dict(identity.get("novel_identity"))
    primary = nested_dict(identity.get("primary_work"))
    current_url = _official_detail_url(
        novel_identity.get("heretic_url")
        or identity.get("heretic_url")
        or primary.get("heretic_url")
        or primary.get("url")
    )
    primary_source_tier = _safe_str(primary.get("source_tier")).lower()
    if not current_url and primary_source_tier not in OFFICIAL_TITLE_SOURCE_TIERS | {"mixed", "official_search"}:
        return []

    if novel_identity:
        novel_identity["official_title"] = canonical_title
        identity["novel_identity"] = novel_identity
    for key in ("official_title", "official_novel_title", "resolved_title"):
        if key in identity:
            identity[key] = canonical_title

    _retitle_candidate_dicts(identity, current_title, canonical_title, current_url)
    if primary:
        primary["official_title"] = canonical_title
        identity["primary_work"] = primary

    reason = "platform_seo_title_suffix_canonicalized"
    identity["platform_seo_title_surface_title"] = current_title
    _append_unique_list(identity, "output_consistency_lint", [reason])
    _append_unique_list(identity, "consistency_flags", [reason])
    return [reason]


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
    if _has_authoritative_publish_contract(identity):
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
    blocked_url = _safe_str(novel_identity.get("heretic_url") or identity.get("heretic_url"))
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

    for key in ("official_title", "official_novel_title", "resolved_title", "heretic_url"):
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
    if title in GENERIC_OFFICIAL_EVIDENCE_TITLES and not _looks_like_url_or_domain(title):
        reasons.append("official_title_looks_like_generic_evidence_label")
    if _official_title_looks_like_search_snippet(title):
        reasons.append("official_title_looks_like_search_snippet")
    if _official_title_looks_like_listing_description(identity, title):
        reasons.append("official_title_looks_like_listing_description")
    if _official_title_looks_like_breadcrumb(title):
        reasons.append("official_title_looks_like_breadcrumb")
    if identity.get("title_resolution_allowed") is False:
        reasons.append("official_title_present_when_title_resolution_allowed_false")
    work_resolution = _safe_str(identity.get("work_resolution")).lower()
    if work_resolution in {"none", "context_only", "nonwork", "unresolved"} and not _title_resolution_confirmed(identity):
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


def _promotion_gate_decision(identity: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(identity, dict):
        return {}
    decision = identity.get("promotion_decision")
    if isinstance(decision, dict):
        return decision
    ledger = identity.get("candidate_ledger")
    if isinstance(ledger, dict):
        decision = ledger.get("promotion_decision")
        if isinstance(decision, dict):
            return decision
    return {}


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


def _append_candidate_preservation_source(
    identity: Dict[str, Any],
    *,
    title: str,
    url: str = "",
    confidence: str = "",
    source_tier: str = "",
    alias_or_mention: str = "",
    reason: str = "",
) -> None:
    current = identity.get("candidate_preservation_sources")
    if not isinstance(current, list):
        current = []
    title_key = _compact_title(title)
    url_key = _safe_str(url)
    for item in current:
        if not isinstance(item, dict):
            continue
        if _compact_title(candidate_name(item)) == title_key and _safe_str(item.get("heretic_url")) == url_key:
            return
    entry: Dict[str, Any] = {
        "official_title": title,
        "confidence": confidence or "Medium",
        "source_tier": source_tier or "official_detail",
        "reference_role": "candidate",
        "preservation_role": "title_candidate",
        "promotion_policy": "hold_without_promotion",
    }
    if url:
        entry["heretic_url"] = url
    if alias_or_mention:
        entry["alias_or_mention"] = alias_or_mention
    if reason:
        entry["negative_evidence"] = [reason]
    current.append(entry)
    identity["candidate_preservation_sources"] = current


def _demote_official_title_to_hold(
    identity: Dict[str, Any],
    *,
    reason: str,
    state: str = "unresolved_matchable",
) -> List[str]:
    blocked_title = official_title(identity)
    if not blocked_title:
        return []

    novel_identity = nested_dict(identity.get("novel_identity"))
    blocked_url = _safe_str(novel_identity.get("heretic_url"))
    blocked_confidence = _safe_str(novel_identity.get("confidence"))
    primary = nested_dict(identity.get("primary_work"))
    alias = _safe_str(primary.get("alias_or_mention"))
    source_tier = _safe_str(primary.get("source_tier"))

    _append_candidate_preservation_source(
        identity,
        title=blocked_title,
        url=blocked_url,
        confidence=blocked_confidence,
        source_tier=source_tier,
        alias_or_mention=alias,
        reason=reason,
    )

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
    _append_unique_list(identity, "promotion_blocked_reasons", [reason])
    _append_unique_list(identity, "candidate_audit_lint", [reason])

    if identity.get("work_resolution") == "resolved":
        identity["work_resolution"] = "unresolved"
    if identity.get("title_resolution_state") in {None, "", "resolved", "direct_resolved"}:
        identity["title_resolution_state"] = state
    identity["title_resolution_allowed"] = False
    identity["is_resolved_work_discussion"] = False

    reason_text = _safe_str(identity.get("reason"))
    guard_note = f"Public title promotion held by weak bridge guard: {blocked_title} ({reason})"
    if guard_note not in reason_text:
        identity["reason"] = f"{reason_text}\n{guard_note}".strip() if reason_text else guard_note
    return [reason]


def _confirmed_alias_flags(identity: Dict[str, Any]) -> List[str]:
    return [
        _safe_str(flag)
        for flag in _safe_list(identity.get("consistency_flags"))
        if _safe_str(flag).startswith("confirmed_alias:")
        or _safe_str(flag) == "verified_alias_official_detail_anchor"
    ]


def _explicit_promoted_image_titles(identity: Dict[str, Any]) -> List[str]:
    titles: List[str] = []
    for evidence in _safe_dicts(identity.get("image_evidence_catalog")):
        if evidence.get("promotion_eligible") is not True:
            continue
        if _safe_str(evidence.get("title_role")).lower() != "work_title":
            continue
        title = _safe_str(evidence.get("explicit_work_title") or evidence.get("detected_title") or evidence.get("work_title"))
        if title and title not in titles:
            titles.append(title)
    return titles


def _title_surface_compatible(left: Any, right: Any) -> bool:
    if _titles_match(left, right):
        return True
    left_key = _compact_title(_strip_platform_seo_title_suffix(left))
    right_key = _compact_title(_strip_platform_seo_title_suffix(right))
    if not left_key or not right_key:
        return False
    if left_key == right_key:
        return True
    shorter, longer = sorted((left_key, right_key), key=len)
    return bool(len(shorter) >= 6 and shorter in longer)


def _title_led_current_work_gate_exempts_generic_genre_bridge(
    identity: Dict[str, Any],
    post_title: Any,
    title: Any,
) -> bool:
    title_text = _safe_str(title)
    title_key = _compact_title(title_text)
    post_key = _compact_title(post_title)
    if not (
        len(title_key) >= 4
        and post_key
        and (post_key.startswith(title_key) or title_key in post_key)
    ):
        return False
    if not TITLE_LED_WORK_CONSUMPTION_RE.search(_safe_str(post_title)):
        return False

    flags = set(_safe_list(identity.get("consistency_flags")))
    if "title_led_consumption_bridge" not in flags:
        return False
    hard_negative_flags = BATCH_ALIAS_CONFLICT_HOLD_FLAGS | {
        "recommendation_context_only_no_work_anchor",
        "recommendation_context_only_public_title_conflict",
        "batch_memory_alias_rescue_blocked_nonwork_context",
        "batch_memory_alias_rescue_blocked_genre_context",
        "semantic_seed_no_work_context",
    }
    if flags & hard_negative_flags:
        return False

    primary = nested_dict(identity.get("primary_work"))
    novel_identity = nested_dict(identity.get("novel_identity"))
    primary_source_tier = _safe_str(primary.get("source_tier")).lower()
    candidate_url = _official_detail_url(
        novel_identity.get("heretic_url")
        or identity.get("heretic_url")
        or primary.get("heretic_url")
        or primary.get("url")
    )
    if not (candidate_url and primary_source_tier in OFFICIAL_TITLE_SOURCE_TIERS):
        return False

    context_sources = {_safe_str(value).lower() for value in _safe_list(identity.get("context_sources"))}
    has_search_context = bool(
        "search" in context_sources
        or _safe_dicts(identity.get("search_evidence_catalog"))
        or _safe_dicts(nested_dict(identity.get("candidate_ledger")).get("search_evidence_catalog"))
    )
    if "title" not in context_sources or not has_search_context:
        return False

    discussion_type = _safe_str(identity.get("discussion_type")).lower()
    if discussion_type not in CORE_DISCUSSION_TYPES:
        return False
    primary_subject_type = _safe_str(identity.get("primary_subject_type")).lower()
    if primary_subject_type not in {"", "work_discussion", "specific_work", "single_work"}:
        return False

    decision = _promotion_gate_decision(identity)
    gate_state = nested_dict(identity.get("promotion_gate_state"))
    if not gate_state:
        gate_state = nested_dict(nested_dict(identity.get("candidate_ledger")).get("promotion_gate_state"))
    scope = nested_dict(decision.get("scope"))
    if not scope:
        scope = nested_dict(gate_state.get("scope"))
    if _safe_str(scope.get("scope_kind")).lower() != "current_work":
        return False

    direct_sources = {_safe_str(value) for value in _safe_list(scope.get("direct_bridge_sources"))}
    reason_codes = {_safe_str(code) for code in _safe_list(decision.get("reason_codes"))}
    if "title_led_consumption_bridge" not in (direct_sources | reason_codes):
        return False

    if gate_state:
        gate_title = _safe_str(gate_state.get("candidate_title"))
        if gate_title and not _titles_match(gate_title, title_text):
            return False
        gate_url = _official_detail_url(gate_state.get("candidate_url"))
        if gate_url and not _official_detail_urls_match(gate_url, candidate_url):
            return False
        if gate_state.get("official_title_exists") is False:
            return False
        if gate_state.get("row_discusses_work_as_work") is False:
            return False

    return True


def _official_title_conflicts_with_promoted_image(identity: Dict[str, Any], title: str) -> bool:
    image_titles = _explicit_promoted_image_titles(identity)
    if not image_titles:
        return False
    if _verified_alias_detail_lock_exempts_promoted_image_conflict(identity, title, image_titles):
        return False
    return not any(_title_surface_compatible(image_title, title) for image_title in image_titles)


def _verified_alias_detail_lock_exempts_promoted_image_conflict(
    identity: Dict[str, Any],
    title: str,
    image_titles: List[str],
) -> bool:
    flags = {str(flag or "").strip() for flag in _safe_list(identity.get("consistency_flags"))}
    if not (
        "verified_alias_official_detail_anchor" in flags
        and "explicit_alias_official_work_lock" in flags
    ):
        return False

    aliases = [
        flag.split(":", 1)[1].strip()
        for flag in flags
        if flag.startswith("confirmed_alias:") and flag.split(":", 1)[1].strip()
    ]
    if not aliases:
        return False

    image_keys = [_compact_title(image_title) for image_title in image_titles]
    alias_hits_image_title = any(
        alias_key and image_key and (alias_key in image_key or image_key in alias_key)
        for alias in aliases
        for alias_key in [_compact_title(alias)]
        for image_key in image_keys
    )
    if not alias_hits_image_title:
        return False

    novel_identity = nested_dict(identity.get("novel_identity"))
    primary = nested_dict(identity.get("primary_work"))
    official_url = _official_detail_url(
        novel_identity.get("heretic_url")
        or identity.get("heretic_url")
        or primary.get("heretic_url")
        or primary.get("url")
    )
    if not official_url:
        return False

    if _official_support_title_matches(title, candidate_name(primary)):
        return True
    return official_search_supports_title(identity, title)


def _unverified_promoted_image_title(identity: Dict[str, Any], title: str) -> bool:
    """Direct OCR/VLM titles still need public support before safe resolution."""
    image_titles = _explicit_promoted_image_titles(identity)
    if not image_titles or not any(_title_surface_compatible(image_title, title) for image_title in image_titles):
        return False

    novel_identity = nested_dict(identity.get("novel_identity"))
    primary = nested_dict(identity.get("primary_work"))
    if _safe_str(novel_identity.get("heretic_url")):
        return False
    if official_search_supports_title(identity, title):
        return False
    if _safe_str(primary.get("source_tier")).lower() not in WEAK_PRIMARY_SOURCE_TIERS:
        return False

    anchor_type = _safe_str(identity.get("anchor_type")).lower()
    flags = set(_safe_list(identity.get("consistency_flags")))
    return bool(
        anchor_type == "image"
        or "direct_image_explicit_title_rescued" in flags
        or "image_surface_title_unverified_without_official_evidence" in flags
    )


def _weak_alias_surface(alias: Any, title: Any) -> bool:
    alias_text = _safe_str(alias)
    alias_key = _compact_title(alias_text)
    title_key = _compact_title(title)
    if not alias_key:
        return False
    if alias_key in LOW_INFORMATION_ALIAS_CLUES or len(alias_key) <= 2:
        return True
    if _WEAK_ALIAS_PHRASE_RE.search(alias_text) or _WEAK_ALIAS_PHRASE_RE.search(alias_key):
        return True
    if title_key and alias_key in title_key and len(alias_key) < 6:
        return True
    if title_key and alias_key in title_key and len(alias_key) / max(1, len(title_key)) < 0.45:
        return True
    tokens = _title_tokens(alias_text)
    if tokens and all(_compact_title(token) in LOW_INFORMATION_ALIAS_CLUES | WEAK_ALIAS_BRIDGE_TOKENS for token in tokens):
        return True
    return False


def _confirmed_alias_exempts_weak_bridge(identity: Dict[str, Any], alias: Any, title: Any) -> bool:
    if not _confirmed_alias_flags(identity):
        return False
    alias_key = _compact_title(alias)
    title_key = _compact_title(title)
    if (
        alias_key
        and title_key
        and alias_key != title_key
        and alias_key in title_key
        and len(alias_key) <= 5
        and len(alias_key) / max(1, len(title_key)) < 0.5
    ):
        return False
    return True


def _shared_current_work_gate_exempts_weak_alias_bridge(
    identity: Dict[str, Any],
    post_title: Any,
    alias: Any,
    title: Any,
) -> bool:
    authoritative_ledger = nested_dict(identity.get("candidate_ledger"))
    authoritative_version = _safe_str(
        identity.get("publish_contract_version")
        or authoritative_ledger.get("publish_contract_version")
    )
    if authoritative_version == "promotion_contract_v2":
        return _promotion_gate_decision(identity).get("publish_allowed") is True

    alias_key = _compact_title(alias)
    title_key = _compact_title(title)
    post_key = _compact_title(post_title)
    if not alias_key or not title_key:
        return False
    exact_title_surface = bool(
        alias_key == title_key
        and len(title_key) >= 4
        and (post_key.startswith(title_key) or title_key in post_key)
    )
    title_led_alias_surface = bool(
        TITLE_LED_WORK_CONSUMPTION_RE.search(_safe_str(post_title))
        and 2 <= len(alias_key) <= 8
        and alias_key in post_key
        and alias_key != title_key
        and alias_key not in LOW_INFORMATION_ALIAS_CLUES
        and not _is_genre_descriptor_surface(alias)
    )
    if not (exact_title_surface or title_led_alias_surface):
        return False

    flags = set(_safe_list(identity.get("consistency_flags")))
    if exact_title_surface and not (
        "decoder_exact_post_title_surface_resolved" in flags
        or _safe_str(identity.get("anchor_type")).lower() in {"title_exact", "full_title_surface"}
    ):
        return False
    hard_negative_flags = BATCH_ALIAS_CONFLICT_HOLD_FLAGS | {
        "recommendation_context_only_no_work_anchor",
        "recommendation_context_only_public_title_conflict",
        "batch_memory_alias_rescue_blocked_nonwork_context",
        "batch_memory_alias_rescue_blocked_genre_context",
        "semantic_seed_no_work_context",
    }
    if flags & hard_negative_flags:
        return False

    primary = nested_dict(identity.get("primary_work"))
    novel_identity = nested_dict(identity.get("novel_identity"))
    candidate_url = _official_detail_url(
        novel_identity.get("heretic_url")
        or identity.get("heretic_url")
        or primary.get("heretic_url")
        or primary.get("url")
    )
    if not candidate_url:
        return False

    context_sources = {_safe_str(value).lower() for value in _safe_list(identity.get("context_sources"))}
    has_search_context = bool(
        "search" in context_sources
        or _safe_dicts(identity.get("search_evidence_catalog"))
        or _safe_dicts(nested_dict(identity.get("candidate_ledger")).get("search_evidence_catalog"))
    )
    if "title" not in context_sources or not has_search_context:
        return False
    if not context_sources & {"body", "comments"} and not title_led_alias_surface:
        return False
    discussion_type = _safe_str(identity.get("discussion_type")).lower()
    if discussion_type not in CORE_DISCUSSION_TYPES:
        return False
    primary_subject_type = _safe_str(identity.get("primary_subject_type")).lower()
    if primary_subject_type not in {"", "work_discussion", "specific_work", "single_work"}:
        return False

    decision = _promotion_gate_decision(identity)
    gate_state = nested_dict(identity.get("promotion_gate_state"))
    if not gate_state:
        gate_state = nested_dict(nested_dict(identity.get("candidate_ledger")).get("promotion_gate_state"))
    scope = nested_dict(decision.get("scope"))
    if not scope:
        scope = nested_dict(gate_state.get("scope"))
    if _safe_str(scope.get("scope_kind")).lower() != "current_work":
        return False
    if _safe_str(scope.get("confidence")).lower() not in {"", "high", "medium"}:
        return False
    direct_sources = {_safe_str(value) for value in _safe_list(scope.get("direct_bridge_sources"))}
    if title_led_alias_surface and not (
        direct_sources
        & {
            "title_led_consumption_bridge",
            "resolved_public_title_scope",
            "alias_surface",
            "title",
        }
    ):
        return False

    if gate_state:
        gate_title = _safe_str(gate_state.get("candidate_title"))
        if gate_title and not _titles_match(gate_title, title):
            return False
        gate_url = _official_detail_url(gate_state.get("candidate_url"))
        if gate_url and not _official_detail_urls_match(gate_url, candidate_url):
            return False
        if gate_state.get("official_title_exists") is False:
            return False
        if gate_state.get("row_discusses_work_as_work") is False:
            return False

    reason_codes = {_safe_str(code) for code in _safe_list(decision.get("reason_codes"))}
    if decision and decision.get("publish_allowed") is False and "row_discusses_work_as_work" not in reason_codes:
        return False
    if title_led_alias_surface and not (
        reason_codes
        & {
            "title_led_consumption_bridge",
            "resolved_public_title_scope",
            "scope_current_work",
        }
    ):
        return False
    if title_led_alias_surface and decision and decision.get("publish_allowed") is False:
        clean_reason_codes = [
            code
            for code in _safe_list(decision.get("reason_codes"))
            if code
            not in {
                "weak_alias_surface_public_title_bridge",
                "serialized_public_identity_scrubbed",
            }
        ]
        for code in (
            "weak_public_title_bridge_shared_gate_exempt",
            "title_led_consumption_bridge",
            "serialized_public_identity_shared_gate_restored",
        ):
            if code not in clean_reason_codes:
                clean_reason_codes.append(code)
        direct_sources = list(_safe_list(scope.get("direct_bridge_sources")))
        for source in ("title_led_consumption_bridge", "alias_surface", "official_detail_url"):
            if source not in direct_sources:
                direct_sources.append(source)
        scope_payload = dict(scope)
        scope_payload["scope_kind"] = "current_work"
        scope_payload["direct_bridge_sources"] = direct_sources
        restored_decision = dict(decision)
        restored_decision.update(
            {
                "status": "publish",
                "publish_allowed": True,
                "official_title": title,
                "official_url": candidate_url,
                "candidate_preserved": False,
                "reason_codes": clean_reason_codes,
                "bypassed_gate": False,
                "scope": scope_payload,
            }
        )
        identity["promotion_decision"] = restored_decision
        gate_state_payload = dict(gate_state) if gate_state else {}
        gate_state_payload["candidate_title"] = title
        gate_state_payload["candidate_url"] = candidate_url
        gate_state_payload["official_title_exists"] = True
        gate_state_payload["row_discusses_work_as_work"] = True
        gate_state_payload["scope"] = scope_payload
        identity["promotion_gate_state"] = gate_state_payload
        ledger = nested_dict(identity.get("candidate_ledger"))
        ledger["promotion_decision"] = restored_decision
        ledger["promotion_gate_state"] = gate_state_payload
        identity["candidate_ledger"] = ledger
        flags_list = list(_safe_list(identity.get("consistency_flags")))
        flags_list = [flag for flag in flags_list if flag != "weak_alias_surface_public_title_bridge"]
        for flag in (
            "weak_public_title_bridge_shared_gate_exempt",
            "serialized_public_identity_shared_gate_restored",
        ):
            if flag not in flags_list:
                flags_list.append(flag)
        identity["consistency_flags"] = flags_list
    return True


def _title_led_consumption_exempts_unconfirmed_alias_bridge(
    identity: Dict[str, Any],
    post_title: Any,
    alias: Any,
    title: Any,
) -> bool:
    flags = set(_safe_list(identity.get("consistency_flags")))
    if not flags & TITLE_LED_ALIAS_EXEMPT_FLAGS:
        return False
    if flags & BATCH_ALIAS_CONFLICT_HOLD_FLAGS:
        return False

    discussion_type = _safe_str(identity.get("discussion_type")).lower()
    if discussion_type not in {"general", "review", "spoiler", "anticipation", "character_talk"}:
        return False
    primary_subject_type = _safe_str(identity.get("primary_subject_type")).lower()
    if primary_subject_type not in {"", "work_discussion", "specific_work", "single_work"}:
        return False

    context_sources = {_safe_str(value).lower() for value in _safe_list(identity.get("context_sources"))}
    if not {"title", "search"}.issubset(context_sources):
        return False
    post_title_text = _safe_str(post_title)
    title_has_consumption_marker = bool(TITLE_LED_WORK_CONSUMPTION_RE.search(post_title_text))
    if not context_sources & {"body", "comments"} and not title_has_consumption_marker:
        return False

    alias_key = _compact_title(alias)
    post_key = _compact_title(post_title)
    if not (2 <= len(alias_key) <= 8) or alias_key not in post_key:
        return False
    if alias_key in LOW_INFORMATION_ALIAS_CLUES or _is_genre_descriptor_surface(alias):
        return False

    context_text = " ".join(
        text
        for text in (
            _safe_str(post_title),
            _safe_str(identity.get("post_core_text")),
            _safe_str(identity.get("post_side_text")),
            " ".join(_safe_str(line) for line in _safe_list(identity.get("reason_lines"))),
        )
        if text
    )
    if not TITLE_LED_WORK_CONSUMPTION_RE.search(context_text):
        return False

    warning_text = _safe_str(identity.get("discourse_warning")).lower()
    if any(token in warning_text for token in ("non_novel", "daily_life", "real_life", "meta_platform")):
        return False
    if any(_safe_str(flag).startswith("non_novel") for flag in flags):
        return False

    return official_search_supports_title(identity, title) or _official_evidence_mentions_title(identity, title)


def _shared_current_work_gate_exempts_unconfirmed_alias_bridge(
    identity: Dict[str, Any],
    post_title: Any,
    alias: Any,
    title: Any,
) -> bool:
    decision = _promotion_gate_decision(identity)
    if not decision or decision.get("publish_allowed") is not True:
        return False
    if _safe_str(decision.get("status")).lower() not in {"", "publish"}:
        return False

    candidate_title = _safe_str(decision.get("official_title") or title)
    if not _titles_match(candidate_title, title):
        return False
    candidate_url = _official_detail_url(decision.get("official_url"))
    primary = nested_dict(identity.get("primary_work"))
    novel_identity = nested_dict(identity.get("novel_identity"))
    candidate_url = candidate_url or _official_detail_url(
        novel_identity.get("heretic_url") or primary.get("heretic_url")
    )
    if not candidate_url:
        return False

    flags = set(_safe_list(identity.get("consistency_flags")))
    hard_negative_flags = BATCH_ALIAS_CONFLICT_HOLD_FLAGS | {
        "recommendation_context_only_no_work_anchor",
        "recommendation_context_only_public_title_conflict",
        "batch_memory_alias_rescue_blocked_nonwork_context",
        "batch_memory_alias_rescue_blocked_genre_context",
        "unresolved_worklike_hold:alias_character_discussion",
        "semantic_seed_no_work_context",
    }
    if flags & hard_negative_flags:
        return False

    context_sources = {_safe_str(value).lower() for value in _safe_list(identity.get("context_sources"))}
    if not {"title", "search"}.issubset(context_sources):
        return False
    if not context_sources & {"body", "comments"}:
        return False
    discussion_type = _safe_str(identity.get("discussion_type")).lower()
    if discussion_type not in {"general", "review", "spoiler", "anticipation", "character_talk"}:
        return False
    primary_subject_type = _safe_str(identity.get("primary_subject_type")).lower()
    if primary_subject_type not in {"", "work_discussion", "specific_work", "single_work"}:
        return False

    alias_key = _compact_title(alias)
    post_key = _compact_title(post_title)
    if not (2 <= len(alias_key) <= 8) or alias_key not in post_key:
        return False
    if alias_key in LOW_INFORMATION_ALIAS_CLUES or _is_genre_descriptor_surface(alias):
        return False

    reason_codes = {_safe_str(code) for code in _safe_list(decision.get("reason_codes"))}
    if "scope_current_work" not in reason_codes:
        return False
    if not (
        reason_codes
        & {
            "batch_alias_public_title_bridge",
            "title_led_consumption_bridge",
            "resolved_public_title_scope",
        }
    ):
        return False
    if "official_detail_url" not in reason_codes:
        return False

    scope = nested_dict(decision.get("scope"))
    gate_state = nested_dict(identity.get("promotion_gate_state"))
    if not gate_state:
        gate_state = nested_dict(nested_dict(identity.get("candidate_ledger")).get("promotion_gate_state"))
    if not scope:
        scope = nested_dict(gate_state.get("scope"))
    if _safe_str(scope.get("scope_kind")).lower() != "current_work":
        return False
    direct_sources = {_safe_str(value) for value in _safe_list(scope.get("direct_bridge_sources"))}
    if "official_detail_url" not in direct_sources:
        return False
    if not (
        direct_sources
        & {
            "batch_alias_candidate_accepted",
            "search_evidence_alias_inference",
            "title_led_consumption_bridge",
            "alias_surface",
        }
    ):
        return False
    if gate_state:
        gate_title = _safe_str(gate_state.get("candidate_title"))
        if gate_title and not _titles_match(gate_title, title):
            return False
        gate_url = _official_detail_url(gate_state.get("candidate_url"))
        if gate_url and gate_url != candidate_url:
            return False
        if gate_state.get("official_title_exists") is False:
            return False
        if gate_state.get("row_discusses_work_as_work") is False:
            return False

    return True


def _unconfirmed_alias_official_detail_bridge(identity: Dict[str, Any], post_title: Any, title: Any) -> bool:
    """Detect an official detail hit attached to an alias that never binds to the title."""
    primary = nested_dict(identity.get("primary_work"))
    alias = _safe_str(primary.get("alias_or_mention"))
    if not alias:
        return False
    if _confirmed_alias_flags(identity):
        return False
    if _title_surface_compatible(alias, title):
        return False
    if _title_surface_compatible(post_title, title):
        return False
    if any(_title_surface_compatible(image_title, title) for image_title in _explicit_promoted_image_titles(identity)):
        return False

    anchor_type = _safe_str(identity.get("anchor_type")).lower()
    anchor_strength = _safe_str(identity.get("anchor_strength")).lower()
    flags = set(_safe_list(identity.get("consistency_flags")))
    if anchor_type != "title_alias":
        return False
    if anchor_strength not in {"", "low", "medium"} and "batch_memory_exact_alias_rescued" not in flags:
        return False

    novel_identity = nested_dict(identity.get("novel_identity"))
    primary_source_tier = _safe_str(primary.get("source_tier")).lower()
    has_official_detail = primary_source_tier in OFFICIAL_TITLE_SOURCE_TIERS or bool(
        _official_detail_url(novel_identity.get("heretic_url") or primary.get("heretic_url"))
    )
    if not has_official_detail:
        return False

    context_sources = {_safe_str(value).lower() for value in _safe_list(identity.get("context_sources"))}
    primary_subject_type = _safe_str(identity.get("primary_subject_type")).lower()
    discussion_type = _safe_str(identity.get("discussion_type")).lower()
    if (
        discussion_type == "character_talk"
        and primary_subject_type in {"", "work_discussion", "specific_work", "single_work"}
        and "batch_memory_alias_rescue_cleared_stale_demotions" in flags
        and "search" in context_sources
        and bool(context_sources & {"title", "body", "comments"})
        and official_search_supports_title(identity, title)
    ):
        return False

    if _title_led_consumption_exempts_unconfirmed_alias_bridge(identity, post_title, alias, title):
        return False
    if _shared_current_work_gate_exempts_unconfirmed_alias_bridge(identity, post_title, alias, title):
        return False

    alias_key = _compact_title(alias)
    title_key = _compact_title(title)
    if not alias_key or not title_key:
        return False
    if alias_key in title_key or title_key in alias_key:
        return False

    return True


def _post_title_short_lead_for_official(post_title: Any, title: Any) -> bool:
    title_key = _compact_title(title)
    if not title_key:
        return False
    text = _safe_str(post_title)
    if not text:
        return False
    if title_key in _compact_title(text):
        return False
    lead = re.split(r"[\s<>\(\)\[\]\?!,\.…]+", text, maxsplit=1)[0]
    lead_key = _compact_title(lead)
    if not lead_key or len(lead_key) > 5:
        return False
    if lead_key in LOW_INFORMATION_ALIAS_CLUES:
        return True
    return bool(lead_key in title_key and lead_key != title_key and len(lead_key) / max(1, len(title_key)) < 0.5)


def _weak_template_overlap_public_title_bridge(identity: Dict[str, Any], post_title: Any, title: Any) -> bool:
    """Detect official-detail promotion supported only by generic title-template overlap."""
    post_text = _safe_str(post_title)
    title_text = _safe_str(title)
    if not post_text or not title_text:
        return False
    if _title_surface_compatible(post_text, title_text):
        return False

    post_key = _compact_title(post_text)
    title_key = _compact_title(title_text)
    if not post_key or not title_key:
        return False
    if title_key in post_key:
        return False

    anchor_type = _safe_str(identity.get("anchor_type")).lower()
    anchor_strength = _safe_str(identity.get("anchor_strength")).lower()
    if anchor_type not in {"title_alias", "title_exact"}:
        return False
    if anchor_strength not in {"", "low", "medium"}:
        return False
    if _confirmed_alias_flags(identity):
        return False
    if any(_title_surface_compatible(image_title, title_text) for image_title in _explicit_promoted_image_titles(identity)):
        return False

    primary = nested_dict(identity.get("primary_work"))
    novel_identity = nested_dict(identity.get("novel_identity"))
    primary_source_tier = _safe_str(primary.get("source_tier")).lower()
    has_official_detail = primary_source_tier in OFFICIAL_TITLE_SOURCE_TIERS or bool(
        _official_detail_url(novel_identity.get("heretic_url") or primary.get("heretic_url"))
    )
    if not has_official_detail:
        return False

    post_tokens = {_compact_title(token) for token in _title_tokens(post_text) if _compact_title(token)}
    title_tokens = {_compact_title(token) for token in _title_tokens(title_text) if _compact_title(token)}
    if len(title_tokens) < 2 or not post_tokens:
        return False

    common = post_tokens & title_tokens
    if not common:
        return False

    weak_keys = {
        _compact_title(token)
        for token in (LOW_INFORMATION_ALIAS_CLUES | WEAK_ALIAS_BRIDGE_TOKENS | TITLE_TOKEN_STOPWORDS)
        if _compact_title(token)
    }
    distinctive_common = {
        token
        for token in common
        if len(token) >= 4 and token not in weak_keys and not _is_genre_descriptor_surface(token)
    }
    if distinctive_common:
        return False

    return len(common) <= 2 or all(token in weak_keys or len(token) < 4 for token in common)


def _image_scene_cue_terms(identity: Dict[str, Any]) -> List[str]:
    terms: List[str] = []
    for evidence in _safe_dicts(identity.get("image_evidence_catalog")):
        if evidence.get("promotion_eligible") is True:
            continue
        cue_values = list(_safe_list(evidence.get("work_cues")))
        ocr_text = _safe_str(evidence.get("ocr_text"))
        if ocr_text:
            cue_values.extend(re.findall(r"[가-힣A-Za-z0-9]{2,}", ocr_text))
        for cue in cue_values:
            for token in _title_tokens(cue):
                key = _compact_title(token)
                if len(key) < 2:
                    continue
                if key in LOW_INFORMATION_ALIAS_CLUES or key in TITLE_TOKEN_STOPWORDS:
                    continue
                if key not in terms:
                    terms.append(key)
    return terms


def _official_evidence_text_for_title(identity: Dict[str, Any], title: Any) -> str:
    title_text = _safe_str(title)
    if not title_text:
        return ""
    texts: List[str] = []
    for evidence in _safe_dicts(identity.get("search_evidence_catalog")):
        source_tier = _safe_str(evidence.get("source_tier")).lower()
        if source_tier not in OFFICIAL_TITLE_SOURCE_TIERS:
            continue
        evidence_title = _safe_str(evidence.get("title"))
        if not _title_surface_compatible(evidence_title, title_text):
            continue
        texts.extend(
            _safe_str(evidence.get(key))
            for key in ("title", "snippet", "query")
            if _safe_str(evidence.get(key))
        )
    return " ".join(texts)


def _image_scene_cues_unverified_public_title_bridge(
    identity: Dict[str, Any],
    post_title: Any,
    title: Any,
) -> bool:
    if _title_surface_compatible(post_title, title):
        return False

    cue_terms = _image_scene_cue_terms(identity)
    if len(cue_terms) < 2:
        return False

    evidence_text = _official_evidence_text_for_title(identity, title)
    if not evidence_text:
        return False
    evidence_key = _compact_title(evidence_text)
    if any(cue in evidence_key for cue in cue_terms):
        return False

    primary = nested_dict(identity.get("primary_work"))
    novel_identity = nested_dict(identity.get("novel_identity"))
    primary_source_tier = _safe_str(primary.get("source_tier")).lower()
    has_official_detail = primary_source_tier in OFFICIAL_TITLE_SOURCE_TIERS or bool(
        _official_detail_url(novel_identity.get("heretic_url") or primary.get("heretic_url"))
    )
    return has_official_detail


def _known_abbreviation_exact_title_exempts_weak_source_bridge(
    identity: Dict[str, Any],
    post_title: Any,
    title: Any,
) -> bool:
    title_text = _safe_str(title)
    title_key = _compact_title(title_text)
    post_key = _compact_title(post_title)
    if not (
        len(title_key) >= 6
        and post_key
        and (post_key.startswith(title_key) or title_key in post_key)
    ):
        return False
    if _is_genre_descriptor_surface(title_text):
        return False

    flags = set(_safe_list(identity.get("consistency_flags")))
    hard_negative_flags = BATCH_ALIAS_CONFLICT_HOLD_FLAGS | {
        "recommendation_context_only_no_work_anchor",
        "recommendation_context_only_public_title_conflict",
        "batch_memory_alias_rescue_blocked_nonwork_context",
        "batch_memory_alias_rescue_blocked_genre_context",
        "semantic_seed_no_work_context",
    }
    if flags & hard_negative_flags:
        return False

    discussion_type = _safe_str(identity.get("discussion_type")).lower()
    if discussion_type not in CORE_DISCUSSION_TYPES:
        return False
    primary_subject_type = _safe_str(identity.get("primary_subject_type")).lower()
    if primary_subject_type not in {"", "work_discussion", "specific_work", "single_work"}:
        return False

    context_sources = {_safe_str(value).lower() for value in _safe_list(identity.get("context_sources"))}
    if "title" not in context_sources or not context_sources & {"body", "comments"}:
        return False
    has_search_context = bool(
        "search" in context_sources
        or _safe_dicts(identity.get("search_evidence_catalog"))
        or _safe_dicts(nested_dict(identity.get("candidate_ledger")).get("search_evidence_catalog"))
    )
    if not has_search_context:
        return False

    decision = _promotion_gate_decision(identity)
    gate_state = nested_dict(identity.get("promotion_gate_state"))
    if not gate_state:
        gate_state = nested_dict(nested_dict(identity.get("candidate_ledger")).get("promotion_gate_state"))
    gate_source = _safe_str(gate_state.get("source")).lower()
    if not gate_source.startswith("known_abbreviation_title_guard"):
        return False

    gate_title = _safe_str(gate_state.get("candidate_title"))
    if gate_title and not _titles_match(gate_title, title_text):
        return False
    if gate_state.get("row_discusses_work_as_work") is False:
        return False

    scope = nested_dict(decision.get("scope")) or nested_dict(gate_state.get("scope"))
    if _safe_str(scope.get("scope_kind")).lower() != "current_work":
        return False
    if _safe_str(scope.get("confidence")).lower() not in {"", "high", "medium"}:
        return False

    reason_codes = {_safe_str(code) for code in _safe_list(decision.get("reason_codes"))}
    direct_sources = {_safe_str(value) for value in _safe_list(scope.get("direct_bridge_sources"))}
    if "scope_current_work" not in reason_codes:
        return False
    if not ("row_discusses_work_as_work" in reason_codes or "row_discusses_work_as_work" in direct_sources):
        return False
    if "alias_bridge" not in reason_codes and "title_led_consumption_bridge" not in reason_codes:
        return False
    if not (
        "work_consumption_marker" in reason_codes
        or "title_led_consumption_bridge" in reason_codes
        or TITLE_LED_WORK_CONSUMPTION_RE.search(_safe_str(post_title))
    ):
        return False

    _append_unique_list(
        identity,
        "consistency_flags",
        ["known_abbreviation_exact_title_public_title_bridge"],
    )
    return True


def apply_weak_public_title_bridge_guard(identity: Dict[str, Any], post_title: Any = "") -> List[str]:
    """Hold public titles promoted through weak/generic surfaces only.

    This is a production precision guard, not a judge-seed shortcut: it preserves
    the demoted title as a candidate and only blocks public promotion when the
    bridge is a low-information alias, a generic genre surface, or a promoted OCR
    title explicitly points at a different work or recommendation-only image
    reference.
    """
    if not isinstance(identity, dict):
        return []
    if _has_authoritative_publish_contract(identity):
        return []
    _apply_same_url_official_page_title_over_alias_canonicalization(identity)
    _apply_same_url_official_detail_canonicalization(identity)
    _apply_platform_seo_title_suffix_canonicalization(identity)
    title = official_title(identity)
    if not title:
        return []
    if identity.get("title_resolution_allowed") is False:
        return []

    anchor_type = _safe_str(identity.get("anchor_type")).lower()
    anchor_strength = _safe_str(identity.get("anchor_strength")).lower()
    primary = nested_dict(identity.get("primary_work"))
    alias = _safe_str(primary.get("alias_or_mention"))
    flags = set(_safe_list(identity.get("consistency_flags")))
    batch_alias_competing_hold = bool(
        "batch_memory_exact_alias_rescued" in flags
        and (
            flags & BATCH_ALIAS_COMPETING_HOLD_FLAGS
            or {"expert_conflict", "budget_quarantine_candidate"}.issubset(flags)
        )
    )
    novel_identity = nested_dict(identity.get("novel_identity"))
    primary_source_tier = _safe_str(primary.get("source_tier")).lower()
    if (
        primary_source_tier in WEAK_PRIMARY_SOURCE_TIERS
        and anchor_strength == "high"
        and not _official_detail_url(novel_identity.get("heretic_url") or primary.get("heretic_url"))
        and not official_search_supports_title(identity, title)
        and not _confirmed_alias_flags(identity)
        and not _explicit_promoted_image_titles(identity)
        and not _safe_list(novel_identity.get("alias_resolution_sources"))
    ):
        if _known_abbreviation_exact_title_exempts_weak_source_bridge(identity, post_title, title):
            return []
        return _demote_official_title_to_hold(
            identity,
            reason="weak_source_exact_title_without_official_support_public_title_bridge",
        )

    image_recommendation_conflict_flags = {
        "vlm_ocr_title_conflict_with_final_title",
        "ocr_title_conflict_with_stable_alias",
        "image_surface_title_unverified_without_official_evidence",
        "weak_image_title_canonical_rescue",
    }
    if (
        "direct_image_reference_recommendation_hold" in flags
        and flags & image_recommendation_conflict_flags
        and not _confirmed_alias_flags(identity)
    ):
        return _demote_official_title_to_hold(
            identity,
            reason="direct_image_reference_recommendation_public_title_conflict",
        )

    if (
        "recommendation_context_only_no_work_anchor" in flags
        and flags & image_recommendation_conflict_flags
        and _safe_str(identity.get("primary_subject_type")).lower() == "recommendation_request"
        and not _confirmed_alias_flags(identity)
    ):
        return _demote_official_title_to_hold(
            identity,
            reason="recommendation_context_only_public_title_conflict",
        )

    if (
        _safe_str(identity.get("primary_subject_type")).lower()
        in {"cross_media", "cross_media_game", "game", "gaming"}
        and "official_url_recall_gate_recovered" in flags
        and "title_body_official_detail_anchor" in flags
        and not _confirmed_alias_flags(identity)
    ):
        return _demote_official_title_to_hold(
            identity,
            reason="cross_media_title_body_official_detail_public_title_bridge",
        )

    secondary_reference_rescue_flags = {
        "secondary_reference_official_alias_rescued",
        "secondary_reference_official_alias_author_meta_override",
    }
    secondary_reference_hard_hold_flags = {
        "title_precision_downgrade",
        "primary_work_cleared_non_resolved",
    }
    if (
        alias
        and flags & secondary_reference_rescue_flags
        and flags & secondary_reference_hard_hold_flags
        and not _title_surface_compatible(alias, title)
        and not _title_surface_compatible(post_title, title)
    ):
        return _demote_official_title_to_hold(
            identity,
            reason="secondary_reference_precision_downgrade_public_title_bridge",
        )

    if (
        alias
        and batch_alias_competing_hold
        and not _title_surface_compatible(alias, title)
        and not _title_surface_compatible(post_title, title)
        and not any(_title_surface_compatible(image_title, title) for image_title in _explicit_promoted_image_titles(identity))
    ):
        return _demote_official_title_to_hold(
            identity,
            reason="batch_memory_alias_competing_hold_public_title_bridge",
        )

    if _official_title_conflicts_with_promoted_image(identity, title):
        return _demote_official_title_to_hold(
            identity,
            reason="promoted_image_work_title_conflicts_with_public_title",
            state="ocr_explicit_title_unresolved",
        )

    if _unverified_promoted_image_title(identity, title):
        return _demote_official_title_to_hold(
            identity,
            reason="unverified_promoted_image_work_title_without_official_support",
            state="ocr_explicit_title_unresolved",
        )

    if anchor_type == "genre" and (
        anchor_strength in {"", "low", "medium"} or _compact_title(title) in {_compact_title(v) for v in GENERIC_WORK_SURFACE_TITLES}
    ):
        if _title_led_current_work_gate_exempts_generic_genre_bridge(identity, post_title, title):
            return []
        return _demote_official_title_to_hold(
            identity,
            reason="generic_genre_surface_public_title_bridge",
        )

    if alias and _weak_alias_surface(alias, title):
        alias_key = _compact_title(alias)
        title_key = _compact_title(title)
        post_key = _compact_title(post_title)
        if (
            alias_key == title_key
            and len(title_key) >= 4
            and anchor_type == "title_exact"
            and anchor_strength in {"high", "medium"}
            and post_key.startswith(title_key)
        ):
            return []
        if batch_alias_competing_hold:
            return _demote_official_title_to_hold(
                identity,
                reason="batch_memory_alias_competing_hold_public_title_bridge",
            )
        if (
            "precision_seed_independent_official_detail_supported" in flags
            and _precision_seed_independent_official_support(identity, title)
        ):
            return []
        if (
            "same_url_official_detail_canonicalized" in flags
            and _precision_seed_independent_official_support(identity, title)
        ):
            return []
        if (
            _confirmed_alias_exempts_weak_bridge(identity, alias, title)
            and "batch_memory_exact_alias_rescued" not in flags
        ):
            return []
        if _shared_current_work_gate_exempts_weak_alias_bridge(identity, post_title, alias, title):
            return []
        novel_identity = nested_dict(identity.get("novel_identity"))
        primary_source_tier = _safe_str(primary.get("source_tier")).lower()
        primary_locked = bool(primary.get("locked"))
        has_official_detail = primary_source_tier in OFFICIAL_TITLE_SOURCE_TIERS and bool(
            _official_detail_url(novel_identity.get("heretic_url") or primary.get("heretic_url"))
        )
        if (
            "batch_memory_exact_alias_rescued" in flags
            and primary_locked
            and has_official_detail
        ):
            return []
        return _demote_official_title_to_hold(
            identity,
            reason="weak_alias_surface_public_title_bridge",
        )

    if _unconfirmed_alias_official_detail_bridge(identity, post_title, title):
        return _demote_official_title_to_hold(
            identity,
            reason="unconfirmed_alias_official_detail_bridge",
        )

    scene_only_bridge_anchor_types = {
        "title_alias",
        "author",
        "character",
        "character_mention",
        "plot_mention",
    }
    if (
        not alias
        and anchor_type in scene_only_bridge_anchor_types
        and anchor_strength in {"", "low", "medium"}
        and not _confirmed_alias_flags(identity)
        and _image_scene_cues_unverified_public_title_bridge(identity, post_title, title)
    ):
        return _demote_official_title_to_hold(
            identity,
            reason="image_scene_cues_unverified_public_title_bridge",
        )

    if (
        not alias
        and anchor_type in {"title_exact", "title_alias"}
        and _post_title_short_lead_for_official(post_title, title)
    ):
        return _demote_official_title_to_hold(
            identity,
            reason="short_lead_surface_public_title_bridge",
        )

    if not alias and _weak_template_overlap_public_title_bridge(identity, post_title, title):
        return _demote_official_title_to_hold(
            identity,
            reason="weak_template_surface_public_title_bridge",
        )

    return []


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
    if _author_plot_composite_alias_bridge(identity):
        reasons.append("precision_seed_author_plot_composite_requires_review")

    return reasons


def _phase2_hold_seed_precision_reasons(judge_seed: Optional[Dict[str, Any]]) -> List[str]:
    seed = nested_dict(judge_seed)
    label = _safe_str(seed.get("phase2_resolution_label")).lower().replace("-", "_")
    action = _safe_str(seed.get("phase2_recommended_action")).lower().replace("-", "_")
    fix_axis = _safe_str(seed.get("phase2_fix_axis")).lower()
    if label != "hold":
        return []
    if action not in {"re_search", "review", "hold"} and fix_axis != "resolution_promotion_gate":
        return []
    return ["phase2_hold_seed_requires_review"]


def _author_plot_composite_alias_bridge(identity: Dict[str, Any]) -> bool:
    slang = nested_dict(identity.get("slang_insight"))
    if not slang:
        return False
    alias_scope = _safe_str(slang.get("alias_scope")).lower()
    attached_type = _safe_str(slang.get("attached_entity_type")).lower()
    store_reason = _safe_str(slang.get("store_reason")).lower()
    attached_text = _safe_str(slang.get("attached_entity_text"))
    return bool(
        alias_scope == "work_plus_author"
        and store_reason == "composite_alias"
        and (
            attached_type in {"", "author"}
            or bool(attached_text)
        )
    )


def _precision_seed_independent_official_support(identity: Dict[str, Any], title: Any) -> bool:
    title_text = _safe_str(title)
    if not title_text:
        return False
    novel_identity = nested_dict(identity.get("novel_identity"))
    primary = nested_dict(identity.get("primary_work"))
    official_url = _official_detail_url(
        novel_identity.get("heretic_url")
        or identity.get("heretic_url")
        or primary.get("heretic_url")
        or primary.get("url")
    )
    if not official_url:
        return False

    flags = {str(flag) for flag in _safe_list(identity.get("consistency_flags"))}
    support_items = [
        item
        for item in _official_detail_support_dicts(identity)
        if _official_detail_urls_match(official_url, item.get("heretic_url") or item.get("url"))
        and _official_support_title_matches(title_text, candidate_name(item))
    ]
    context_sources = {_safe_str(value).lower() for value in _safe_list(identity.get("context_sources"))}
    primary_subject_type = _safe_str(identity.get("primary_subject_type")).lower()
    recoverable_stale_competition_flags = {
        "multi_work_title_cleared",
        "secondary_reference_official_alias_blocked_after_multi_work_title_cleared",
    }
    locked_official_base_support = bool(
        "locked_official_candidate_rescued" in flags
        and (
            "weak_public_title_bridge_locked_official_exempt" in flags
            or "weak_public_title_bridge_verified_alias_detail_exempt" in flags
            or "explicit_alias_official_work_lock" in flags
        )
        and _safe_str(identity.get("discussion_type")).lower() in CORE_DISCUSSION_TYPES
        and primary_subject_type in {"", "work_discussion", "specific_work", "single_work"}
    )

    locked_official_detail_support = False
    if locked_official_base_support:
        for item in support_items:
            role = _safe_str(item.get("reference_role")).lower()
            if item is primary or item.get("locked") is True or role in {"primary", "candidate", ""}:
                locked_official_detail_support = True
                break

    locked_official_reread_support = bool(
        locked_official_base_support
        and (
            "final_semantic_reread_accepted_resolution" in flags
            or locked_official_detail_support
        )
    )
    verified_alias_stale_reread_support = bool(
        support_items
        and flags & recoverable_stale_competition_flags
        and "verified_alias_official_detail_anchor" in flags
        and "final_semantic_reread_accepted_resolution" in flags
        and any(flag.startswith("confirmed_alias:") for flag in flags)
        and _safe_str(identity.get("discussion_type")).lower() in CORE_DISCUSSION_TYPES
        and primary_subject_type
        in {"", "work_discussion", "specific_work", "single_work", "multi_work_bundle"}
        and "search" in context_sources
        and bool(context_sources & {"title", "body", "comments"})
    )
    stale_reread_support = locked_official_reread_support or verified_alias_stale_reread_support

    if identity.get("title_resolution_allowed") is False:
        return False
    work_resolution = _safe_str(identity.get("work_resolution")).lower()
    if work_resolution not in {"resolved", "safe_resolved"} and not (
        work_resolution in {"", "unresolved", "hold_unresolved"}
        and stale_reread_support
    ):
        return False

    hard_hold_flags = {
        "title_precision_downgrade",
        "primary_work_cleared_non_resolved",
        "official_url_recall_blocked_relation_non_work_context",
        "official_url_recall_blocked_hard_non_novel_context",
        "official_url_recall_blocked_cross_media_title_body_hold",
        "official_url_recall_blocked_competing_candidate",
        "expert_conflict",
        "multi_work_title_cleared",
        "secondary_reference_official_alias_blocked_after_multi_work_title_cleared",
        "budget_quarantine_candidate",
        "title_hold",
        "fanfic_derivative_title_unanchored_hold",
        "multi_work_relation_hold_demoted",
        "non_novel_media_title_demoted",
        "vlm_ocr_title_conflict_with_final_title",
        "ocr_title_conflict_with_stable_alias",
        "image_surface_title_unverified_without_official_evidence",
    }
    if locked_official_reread_support and "locked_official_rescue_cleared_stale_demotions" in flags:
        recoverable_stale_competition_flags.add("official_url_recall_blocked_competing_candidate")
    hard_hold_hits = flags & hard_hold_flags
    stale_competition_only = bool(
        hard_hold_hits
        and hard_hold_hits <= recoverable_stale_competition_flags
        and stale_reread_support
    )
    if (
        (hard_hold_hits and not stale_competition_only)
        or any(str(flag).startswith("unresolved_worklike_hold:") for flag in flags)
    ):
        return False

    if _author_plot_composite_alias_bridge(identity):
        return False

    if not support_items and not official_search_supports_title(identity, title_text):
        return False

    has_context = bool(context_sources & {"title", "body", "comments", "image", "search"})
    if not has_context:
        return False

    anchor_type = _safe_str(identity.get("anchor_type")).lower()
    anchor_strength = _safe_str(identity.get("anchor_strength")).lower()
    has_direct_anchor = bool(
        anchor_type in {"image", "title_exact", "title_alias", "ocr_explicit_title", "full_title_surface", "official_url"}
        and anchor_strength in {"high", "medium"}
    )
    has_locked_contextual_anchor = bool(
        locked_official_reread_support
        and anchor_type in {"author", "character", "character_mention", "plot_mention", "title_alias"}
        and anchor_strength in {"high", "medium"}
        and "search" in context_sources
        and bool(context_sources & {"title", "body", "comments"})
    )
    has_verified_alias_lock = bool(
        any(flag.startswith("confirmed_alias:") for flag in flags)
        and (
            "verified_alias_official_detail_anchor" in flags
            or "explicit_alias_official_work_lock" in flags
        )
    )
    if primary_subject_type in {"cross_media", "cross_media_game", "game", "gaming"} and not has_verified_alias_lock:
        return False

    def alias_source_supported(item: Dict[str, Any]) -> bool:
        alias = _safe_str(item.get("alias_or_mention") or item.get("matched_clue"))
        alias_key = _compact_title(alias)
        if len(alias_key) < 3:
            return False
        if alias_key in LOW_INFORMATION_ALIAS_CLUES or alias_key in TITLE_TOKEN_STOPWORDS:
            return False
        role = _safe_str(item.get("reference_role")).lower()
        return role in {"primary", "mentioned", ""} and _safe_str(item.get("promotion_policy")).lower() != "hold_without_promotion"

    has_official_alias_source = any(alias_source_supported(item) for item in support_items)
    has_primary_official_detail = any(
        _safe_str(item.get("reference_role")).lower() == "primary"
        or item is primary
        for item in support_items
    )
    has_locked_primary_official_detail = bool(
        locked_official_reread_support
        and (has_direct_anchor or has_locked_contextual_anchor)
        and has_primary_official_detail
        and support_items
    )
    return bool(
        has_verified_alias_lock
        or has_locked_primary_official_detail
        or (has_direct_anchor and has_official_alias_source)
        or (has_direct_anchor and has_primary_official_detail and official_search_supports_title(identity, title_text))
    )


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

    _apply_same_url_official_detail_canonicalization(identity)
    _apply_platform_seo_title_suffix_canonicalization(identity)
    blocked_title = official_title(identity)
    if not blocked_title:
        return []
    phase2_hold_reasons = _phase2_hold_seed_precision_reasons(judge_seed)
    if not phase2_hold_reasons and _precision_seed_independent_official_support(identity, blocked_title):
        _append_unique_list(
            identity,
            "precision_seed_bypass_reasons",
            ["precision_seed_independent_official_detail_supported"],
        )
        _append_unique_list(
            identity,
            "consistency_flags",
            ["precision_seed_independent_official_detail_supported"],
        )
        return []

    reasons = _precision_seed_weak_or_non_novel_title_reasons(identity)
    for reason in phase2_hold_reasons:
        if reason not in reasons:
            reasons.append(reason)
    if not reasons:
        reasons.append("precision_seed_official_title_requires_review")

    novel_identity = nested_dict(identity.get("novel_identity"))
    blocked_url = _safe_str(novel_identity.get("heretic_url") or identity.get("heretic_url"))
    blocked_confidence = _safe_str(novel_identity.get("confidence"))

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
    _scrub_precision_seed_reason_lines(identity, blocked_title)

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


def apply_judge_seed_hygiene_alias_conflict_guard(
    identity: Dict[str, Any],
    judge_seed: Optional[Dict[str, Any]] = None,
) -> List[str]:
    """Demote hygiene-seed titles when image/OCR and stable-alias evidence disagree.

    Hygiene seeds are review probes, not approval lanes. If a rerun still carries
    both a final-title-vs-image conflict and a stable-alias conflict, leaving a
    public title in place hides the contradiction as lint-only evidence.
    """

    if not isinstance(identity, dict):
        return []
    disagreement_type = _judge_disagreement_type(judge_seed)
    if seed_group(disagreement_type, judge_seed) != "hygiene":
        return []

    title = official_title(identity)
    if not title:
        return []
    if identity.get("title_resolution_allowed") is False:
        return []

    flags = {str(flag or "").strip() for flag in _safe_list(identity.get("consistency_flags"))}
    has_image_title_conflict = bool(
        "vlm_ocr_title_conflict_with_final_title" in flags
        or "image_surface_title_unverified_without_official_evidence" in flags
    )
    has_stable_alias_conflict = bool(
        "ocr_title_conflict_with_stable_alias" in flags
        or "search_title_conflict_with_stable_alias" in flags
        or "stable_batch_alias_conflict_corrected" in flags
    )
    if not (has_image_title_conflict and has_stable_alias_conflict):
        return []

    reason = f"judge_hygiene_seed_alias_image_conflict_{disagreement_type or 'unknown'}"
    reasons = _demote_official_title_to_hold(identity, reason=reason)
    if not reasons:
        return []

    _append_unique_list(identity, "output_consistency_lint", reasons)
    _append_unique_list(identity, "consistency_flags", reasons)

    reason_text = _safe_str(identity.get("reason"))
    guard_note = (
        "Hygiene seed kept conflicting alias/image evidence; public title held "
        f"pending review: {title}"
    )
    if guard_note not in reason_text:
        identity["reason"] = f"{reason_text}\n{guard_note}".strip() if reason_text else guard_note
    return reasons


def apply_judge_seed_wrong_relevance_public_title_guard(
    identity: Dict[str, Any],
    judge_seed: Optional[Dict[str, Any]] = None,
) -> List[str]:
    """Demote wrong-relevance probe titles to candidates instead of public titles."""

    if not isinstance(identity, dict):
        return []
    disagreement_type = _judge_disagreement_type(judge_seed)
    if disagreement_type != "wrong_relevance":
        return []
    group = seed_group(disagreement_type, judge_seed)
    if group not in {"candidate", "hygiene"}:
        return []

    title = official_title(identity)
    if not title:
        return []
    if identity.get("title_resolution_allowed") is False:
        return []

    reason = f"judge_{group}_seed_wrong_relevance_public_title_held"
    reasons = _demote_official_title_to_hold(identity, reason=reason)
    if not reasons:
        return []

    _append_unique_list(identity, "output_consistency_lint", reasons)
    _append_unique_list(identity, "consistency_flags", reasons)
    return reasons


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


def _scrub_precision_seed_reason_lines(identity: Dict[str, Any], blocked_title: str) -> None:
    raw_lines = _safe_list(identity.get("reason_lines"))
    if not raw_lines:
        reason_text = _safe_str(identity.get("reason"))
        raw_lines = reason_text.splitlines() if reason_text else []
    if not raw_lines or not blocked_title:
        return

    updated: List[Any] = []
    correction_added = False
    for line in raw_lines:
        text = str(line)
        stripped = text.strip()
        replacement: Optional[str] = None
        if stripped.startswith("- 공식 제목:"):
            replacement = "- 공식 제목: 미확정 (precision seed HOLD; 후보로만 보존)"
        elif "최종 공식 제목" in stripped and ("확정" in stripped or blocked_title in stripped):
            replacement = "- 최종 공식 제목 확정 문구는 precision seed guard로 철회됨."
        elif "heretic_url_platform" in stripped:
            replacement = "- heretic_url_platform 점수는 precision seed guard로 철회됨."
        elif blocked_title in stripped and "관련 작품 토론으로 판정" in stripped:
            replacement = (
                "- 작품/IP 후보 맥락은 보존하되, precision seed라 단일 공식 제목 "
                "확정은 보류함."
            )

        if replacement:
            if replacement not in updated:
                updated.append(replacement)
            correction_added = True
        else:
            updated.append(line)

    note = "- public title promotion blocked: precision_seed -> candidate/HOLD"
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
    if title and identity.get("is_resolved_work_discussion") is False and not _title_resolution_confirmed(identity):
        reasons.append("official_title_present_when_is_resolved_work_discussion_false")
    if title and identity.get("is_relevant") is False:
        reasons.append("official_title_present_when_is_relevant_false")
    if (
        seed_group(disagreement_type, judge_seed) == "precision"
        and title
        and not _precision_seed_independent_official_support(identity, title)
    ):
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
    promotion_decision = _promotion_gate_decision(identity)

    if official_title_lint_reasons(identity):
        return "official_title_lint"
    if identity_consistency_lint_reasons(identity, judge_seed):
        return "identity_consistency_lint"
    if output_consistency_lint_reasons(identity, judge_seed) and group in {"hygiene", "candidate"}:
        return "output_consistency_lint"
    if title and promotion_decision and promotion_decision.get("publish_allowed") is False:
        return "promotion_blocked"
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
    existing_ledger = nested_dict(identity.get("candidate_ledger"))
    promotion_decision = _promotion_gate_decision(identity)
    authoritative_v2 = has_authoritative_publish_contract(identity)
    # v2 candidate audit is observational.  Rebuilding the ledger with the
    # broad collector would append URL-less title/entity/image observations
    # after the serializer froze its typed (title, URL) inventory.  Preserve
    # the authoritative ledger byte-for-byte apart from explicit lint/status
    # mirrors added below; legacy rows still receive the broad audit ledger.
    ledger = (
        dict(existing_ledger)
        if authoritative_v2
        else build_candidate_ledger(identity, judge_seed)
    )
    shadow_lint: List[str] = []
    if authoritative_v2:
        # CandidateSet/NIL is observational only.  Keep it inside the existing
        # candidate ledger so Pydantic root output and the v2 publish
        # fingerprint remain unchanged, and never feed it back into selection
        # or public-title mutation.
        from .candidate_set_shadow import (
            selective_shadow_from_identity,
            unavailable_shadow_payload,
        )

        try:
            ledger["candidate_set_shadow"] = selective_shadow_from_identity(identity).to_dict()
        except ValueError:
            ledger["candidate_set_shadow"] = unavailable_shadow_payload(
                "typed_publish_contract_replay_failed"
            )
            shadow_lint.append("candidate_set_shadow_contract_invalid")
    if promotion_decision:
        ledger["promotion_decision"] = promotion_decision
        gate_state = nested_dict(identity.get("promotion_gate_state"))
        if not gate_state:
            gate_state = nested_dict(existing_ledger.get("promotion_gate_state"))
        if gate_state:
            ledger["promotion_gate_state"] = gate_state
        gate_evidence = identity.get("promotion_gate_evidence")
        if not isinstance(gate_evidence, list):
            gate_evidence = existing_ledger.get("promotion_gate_evidence")
        if isinstance(gate_evidence, list):
            ledger["promotion_gate_evidence"] = gate_evidence
        # Candidate-audit enrichment is observational.  It must preserve the
        # complete authoritative v2 mirror rather than rebuilding a partial
        # ledger that silently drops trace/fingerprint/version bindings.
        for field in (
            "publish_contract_trace",
            "publish_ledger",
            "publish_contract_input_fingerprint",
            "publish_contract_version",
            "publish_contract_integrity_error",
            "candidate_ledger_status",
            "title_resolution_allowed",
            "title_resolution_state",
            "work_resolution",
            "promotion_blocked",
            "hold_without_candidates",
            "safe_resolved",
        ):
            if field in identity:
                ledger[field] = identity.get(field)
            elif field in existing_ledger:
                ledger[field] = existing_ledger.get(field)
    existing_official_lint = _safe_list(identity.get("official_title_lint"))
    official_lint = list(dict.fromkeys(existing_official_lint + official_title_lint_reasons(identity)))
    identity_lint = identity_consistency_lint_reasons(identity, judge_seed)
    output_lint = output_consistency_lint_reasons(identity, judge_seed)
    existing_candidate_lint = _safe_list(identity.get("candidate_audit_lint"))
    candidate_lint = list(
        dict.fromkeys(
            existing_candidate_lint
            + noisy_expected_seed_candidate_lint_reasons(identity, judge_seed)
            + shadow_lint
        )
    )
    status = classify_candidate_audit(identity, judge_seed)
    if authoritative_v2:
        contract_status = str(
            identity.get("candidate_ledger_status")
            or existing_ledger.get("candidate_ledger_status")
            or ""
        ).strip()
        if contract_status:
            status = contract_status
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
    existing_ledger = nested_dict(identity.get("candidate_ledger"))
    promotion_decision = _promotion_gate_decision(identity)
    authoritative_v2 = has_authoritative_publish_contract(identity)
    if not authoritative_v2:
        preserve_recoverable_official_detail_candidate(identity)
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
    from llm_batch.slang.slang_db import (  # noqa: WPS433 (intentional local import)
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
