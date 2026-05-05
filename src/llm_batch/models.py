from __future__ import annotations

from typing import Any, Dict, List, Optional, Literal

from pydantic import BaseModel, Field


class ContentBlock(BaseModel):
    type: str
    url: Optional[str] = None
    text: Optional[str] = None


class PostInput(BaseModel):
    gallery_id: str = "test"  # 테스트용 기본값 추가
    post_id: int
    title: str
    author: Optional[str] = None
    created_at: Optional[str] = None
    url: Optional[str] = None
    content_blocks: List[ContentBlock] = Field(default_factory=list)
    page_no: Optional[int] = None
    comments: List[Any] = Field(default_factory=list)  # Staged pipeline용 comments


class CommentInput(BaseModel):
    comment_id: str
    author: Optional[str] = None
    content: str
    content_html: Optional[str] = None
    created_at: Optional[str] = None
    ip: Optional[str] = None
    reply_to_comment_id: Optional[str] = None
    reply_level: Optional[int] = None
    post_id: int


class NovelIdentity(BaseModel):
    official_title: Optional[str]
    heretic_url: Optional[str] = None  # 작품 공식 페이지 URL (제목과 별도)
    confidence: str


class Evidence(BaseModel):
    found_in_comment: bool
    source_text: Optional[str] = None


class SlangInsight(BaseModel):
    # LLM이 종종 null을 넣는 경우가 있어 Optional로 허용.
    # (원칙상 null이면 slang_insight 자체를 생략하는게 맞지만, 파이프라인 안정성을 위해 완화)
    detected_term: Optional[str] = None
    decoded_term: Optional[str] = None
    decode_verified: Optional[bool] = None
    cultural_context: Optional[str] = None  # 밈/은어의 유래·용법·커뮤니티 맥락 설명
    canonical_work_alias: Optional[str] = None
    alias_scope: Optional[Literal[
        "pure_work_alias",
        "work_plus_character",
        "work_plus_author",
        "work_plus_meme",
        "mixed_unknown",
    ]] = None
    attached_entity_text: Optional[str] = None
    attached_entity_type: Optional[Literal["character", "author", "meme", "other"]] = None
    store_in_slang_db: Optional[bool] = None
    store_reason: Optional[str] = None


class Inference(BaseModel):
    type: str
    topic: str


class OutputItem(BaseModel):
    post_id: int
    is_relevant: bool
    novel_identity: Optional[NovelIdentity] = None
    evidence: Optional[Evidence] = None
    slang_insight: Optional[SlangInsight] = None
    inference: Optional[Inference] = None
    reason: Optional[str] = None
    reason_lines: Optional[List[str]] = None


#
# Pickvel V2: 식별(identity) + 담론 분석(analysis)
#


class PickvelIdentity(BaseModel):
    """
    post_id를 제외한 '작품 식별' 결과.
    (V1 OutputItem과 거의 동일하지만, V2에서는 post_id는 바깥 래퍼가 가진다)
    """

    is_relevant: bool
    novel_identity: Optional[NovelIdentity] = None
    discussion_type: Optional[Literal[
        # === is_relevant=true 가능 ===
        "review",            # 작품 분석/평가
        "spoiler",           # 스포일러 토론
        "anticipation",      # 기대/응원/기우제
        "meme",              # 작품 관련 밈/드립
        "character_talk",    # 캐릭터 감상
        "general",           # 기타 작품 관련 토론
        # === 항상 is_relevant=false ===
        "author_talk",       # 작가 토론/비평 (작품 특정 안됨)
        "recommendation",    # 추천 요청
        "meta",              # 플랫폼 메타 (뱃지, 이모티콘, UI, 이벤트)
        "trope_discussion",  # 장르/트로프 일반 토론 (특정 작품 없음)
        "community_banter",  # 커뮤니티 잡담/뻘글 (장붕 은어, 유저 간 대화)
        "genre_opinion",     # 장르/소재 범용 의견 ("~하는 소설 없냐", "하렘은~")
        "image_post",        # 이미지 중심 게시글 (텍스트 부족으로 식별 불가)
        "off_topic",         # 소설/웹소설과 완전 무관 (게임, 현실, 정치, 일상)
        "noise",             # 기타 미분류 노이즈
        # === 해독불가 (작품 논의이지만 특정 불가) ===
        "undecodable_reference"  # 작품 언급이 있으나 마스킹/닉네임/캐릭터명만으로 특정 불가
    ]] = None
    evidence: Optional[Evidence] = None
    slang_insight: Optional[SlangInsight] = None
    inference: Optional[Inference] = None
    # 관련 포스트에서 단일 official_title 외에 후보군을 함께 노출
    # (복수 작품/작품군 비교 맥락, 미확정 케이스 대응)
    title_candidates: Optional[List["DetectedTitle"]] = None
    primary_work: Optional["DetectedTitle"] = None
    mentioned_works: Optional[List["DetectedTitle"]] = None
    future_watch_target: Optional["DetectedTitle"] = None
    comparison_target: Optional["DetectedTitle"] = None
    recommendation_candidates: Optional[List["DetectedTitle"]] = None
    primary_subject_type: Optional[str] = None
    primary_subject_text: Optional[str] = None
    secondary_reference_works: Optional[List["DetectedTitle"]] = None
    entity_mentions: Optional[List["EntityMention"]] = None
    topicality: Optional[Literal[
        "core_relevant",
        "adjacent_relevant",
        "unrelated",
    ]] = None
    relevance_scope: Optional[Literal[
        "core",
        "adjacent",
        "off_topic",
    ]] = None
    subtype: Optional[Literal[
        "resolved_work",
        "unresolved_work",
        "multi_work_compare",
        "support_cheer",
        "resume_announcement",
        "character_talk",
        "plot_spoiler",
        "review_reaction",
        "author_meta",
        "platform_meta",
        "release_serialization_meta",
        "recommendation_request",
        "genre_trope_discussion",
        "community_work_banter",
        "fandom_meta",
        "daily_life",
        "realworld_social_talk",
        "cross_media_game",
        "pure_meme",
        "other_quarantine",
    ]] = None
    work_resolution: Optional[Literal[
        "resolved",
        "unresolved",
        "multi_work",
        "none",
    ]] = None
    anchor_type: Optional[Literal[
        "title_alias",
        "title_exact",
        "character",
        "author",
        "platform",
        "genre",
        "neighbor",
        "image",
        "none",
    ]] = None
    anchor_strength: Optional[Literal["high", "medium", "low", "none"]] = None
    context_sources: Optional[List[Literal[
        "title",
        "body",
        "comments",
        "neighbor_posts",
        "search",
        "image",
    ]]] = None
    consistency_flags: Optional[List[str]] = None
    reason: Optional[str] = None
    reason_lines: Optional[List[str]] = None
    system_state: Optional[Literal[
        "clean",
        "verifier_failed",
        "search_degraded",
        "partial_evidence",
        "pending_retry",
    ]] = None
    identity_state: Optional[Literal[
        "resolved_title",    # 관련 + 정식 제목 확정
        "unresolved_title",  # 관련이나 정식 제목 미확정
        "adjacent_relevant", # 주변 관련
        "technical_inconclusive",  # 기술 실패로 비관련로 단정하기 어려움
        "non_relevant",      # 비관련
    ]] = None


class DetectedTitle(BaseModel):
    """텍스트에서 감지된 후보 작품(여러 개일 수 있음)."""

    official_title: Optional[str] = None
    heretic_url: Optional[str] = None  # 작품 공식 페이지 URL (제목과 별도)
    confidence: Literal["None", "Low", "Medium", "High", "Max"] = "None"
    alias_or_mention: Optional[str] = None
    source_tier: Optional[Literal[
        "official_detail",
        "official_search",
        "community",
        "listing",
        "llm_only",
        "mixed",
    ]] = None
    page_type: Optional[str] = None
    content_status: Optional[str] = None
    locked: Optional[bool] = None
    negative_evidence: Optional[List[str]] = None
    reference_role: Optional[Literal[
        "primary",
        "mentioned",
        "future_watch_target",
        "candidate",
    ]] = None


class EntityMention(BaseModel):
    """작품/작가/캐릭터/밈 등 엔티티를 평탄화하지 않고 보존."""

    text: str
    entity_type: Literal["work", "author", "character", "slang", "meme", "other"] = "other"
    canonical_value: Optional[str] = None
    confidence: Literal["None", "Low", "Medium", "High", "Max"] = "None"
    source: Optional[str] = None
    role: Optional[Literal[
        "primary",
        "mentioned",
        "future_watch_target",
        "author_focus",
        "character_focus",
        "slang",
        "meme",
        "candidate",
    ]] = None


class SentimentProfile(BaseModel):
    """
    커뮤니티 담론에서 추출되는 '보이지 않는 메타데이터' 요약.
    """

    pacing: Optional[Literal["Fast", "Normal", "Slow", "FastStart_SlowEnd", "Unknown"]] = "Unknown"
    drift_risk: Optional[Literal["Low", "High", "Critical", "Unknown"]] = "Unknown"
    sentiment: Optional[Literal["Positive", "Neutral", "Negative", "Mixed", "Unknown"]] = "Unknown"


class PickvelAnalysis(BaseModel):
    """
    벡터 DB 적재를 위한 담론 분석 결과.
    - micro_tags: 고구마/사이다/드리프트/후집피/4드론/아카데미물 등의 마이크로 태그(가능하면 순화된 표현)
    - is_nsfw: 고수위/성인 표현(직설 은어 포함) 감지 여부
    - user_segment: 누렁이/무틀딱/대역퍼거 등 리뷰어 성향
    """

    detected_titles: List[DetectedTitle] = Field(default_factory=list)
    micro_tags: List[str] = Field(default_factory=list)
    sentiment_profile: Optional[SentimentProfile] = None
    is_nsfw: bool = False
    user_segment: Optional[str] = None
    notes: Optional[str] = None


class PickvelOutputItemV2(BaseModel):
    """
    V2 출력: post_id별로 identity + analysis를 함께 반환.
    """

    post_id: int
    identity: PickvelIdentity
    analysis: Optional[PickvelAnalysis] = None


class BatchInput(BaseModel):
    posts: List[PostInput]
    comments: List[CommentInput]
    metadata: Dict[str, Any] = Field(default_factory=dict)
