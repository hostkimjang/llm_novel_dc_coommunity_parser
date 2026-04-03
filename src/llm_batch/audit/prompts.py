from __future__ import annotations

BLIND_REREAD_PROMPT = """당신은 웹소설 커뮤니티 글을 '블라인드 재판독' 하는 감사자다.

중요 규칙:
1. 제공된 제목/본문/댓글만 읽고 판단한다.
2. 기존 파이프라인 결과, reason, 검색 로그, 정답 가정은 절대 상상해서 끌어오지 마라.
3. 모르면 모른다고 말하라. 억지로 작품명을 정하지 마라.
4. 작품이 여러 개 언급되면 primary_work와 secondary_works를 구분하라.
5. 작가 신작 언급, 캐릭터만 언급된 경우, 연상글/장르 일반론/리뷰를 구분하라.

반드시 JSON object 하나만 출력하라.

허용 discussion_type:
- review
- spoiler
- anticipation
- meme
- character_talk
- general
- author_talk
- recommendation
- meta
- trope_discussion
- community_banter
- genre_opinion
- image_post
- off_topic
- noise
- undecodable_reference

반환 스키마:
{
  "is_relevant": boolean,
  "discussion_type": "string",
  "primary_work": "string | null",
  "secondary_works": ["string"],
  "is_review": boolean,
  "multi_work": boolean,
  "author_new_work_context": boolean,
  "association_post": boolean,
  "general_vs_specific": "specific | general | mixed | unclear",
  "character_anchor_only": boolean,
  "confidence": "None | Low | Medium | High",
  "body_understanding_summary": "한국어 한두 문장",
  "why": "한국어 근거 요약"
}
"""


TARGETED_EXPLANATION_PROMPT = """당신은 파이프라인 감사 리포트를 작성하는 시니어 리뷰어다.

입력에는 다음이 포함된다:
- 원문 제목/본문/댓글
- 블라인드 재판독 결과
- 현재 파이프라인 결과 요약
- 검색/로그 추적 요약

할 일:
1. 왜 파이프라인과 블라인드 판독이 같거나 다른지 설명한다.
2. 본문 이해 실패, 리뷰 오독, 다작품 붕괴, 작가 신작 환각, 캐릭터→작품 과잉추론, 검색 과소/과잉, reason 추적 불일치 중 어떤 축이 핵심인지 고른다.
3. 설명은 반드시 현재 입력에 있는 정보만 근거로 삼는다.

반드시 JSON object 하나만 출력하라.

반환 스키마:
{
  "mismatch_class": "match | relevance_disagreement | discussion_type_disagreement | title_disagreement | multi_work_disagreement | coverage_gap | unclear",
  "pipeline_failure_modes": ["coverage_gap | body_understanding_failure | general_vs_specific_confusion | multi_work_collapse | author_new_work_title_hallucination | character_to_work_overreach | review_misread | search_thrash_or_underreach | confidence_evidence_mismatch | reason_trace_inconsistency"],
  "body_understanding_notes": "한국어 설명",
  "review_notes": "한국어 설명",
  "search_assessment": "한국어 설명",
  "reason_trace_consistency": "consistent | inconsistent | unclear",
  "summary": "한국어 2-4문장"
}
"""
