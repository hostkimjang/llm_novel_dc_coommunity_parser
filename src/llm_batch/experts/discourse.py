"""
DiscourseAnalyzer Expert - 담론 분석가
글의 본질적 의도와 도메인 컨텍스트를 파악하는 전문가
"""

from __future__ import annotations

import json
import sys
import time
from typing import Any, Dict, List

from .utils import parse_json_with_think_removal, _ts


DISCOURSE_SYSTEM = """\
You are 📖 DISCOURSE ANALYZER, an expert in understanding the fundamental intent and domain context of online community posts.

YOUR CORE MISSION:
Before any entity extraction or title matching, understand WHAT THIS POST IS REALLY ABOUT.
Don't get distracted by superficial keywords - dig into the true subject matter and purpose.

=== FUNDAMENTAL ANALYSIS FRAMEWORK ===

**STEP 1: DOMAIN IDENTIFICATION**
What domain/field does this post belong to?

IMPORTANT: Don't limit yourself to predefined categories. Identify the ACTUAL domain based on content.

Common Domains (examples, not exhaustive):
- **novel_literature**: Web novels, books, stories, authors, characters, plot discussions
- **manga_comics**: Manga, manhwa, webtoons, comics (visual storytelling)
  - 본문에 "만화", "동인지", "짤", "웹툰" 등 시각 매체 언급 시 이 도메인
- **anime**: Animation, anime series, voice actors, studios
- **gaming**: Video games, game mechanics, patches, esports
- **medical_health**: Medical procedures, treatments, symptoms, diseases, mental health, pharmaceuticals
- **tech_engineering**: Programming, algorithms, software, hardware, IT, DevOps
- **daily_life**: Food, cooking, weather, daily activities, personal routines
- **meta_platform**: Platform features, community rules, UI/UX, site events, moderation
- **politics**: Political issues, elections, policies, government
- **sports**: Athletics, matches, players, leagues, fitness
- **economy_finance**: Markets, investments, cryptocurrencies, business
- **education_academia**: Schools, exams, research, academic topics
- **relationships**: Dating, romance, friendships, family issues
- **military_history**: Military equipment, wars, historical events, strategy
- **music**: Musicians, concerts, instruments, genres
- **art_design**: Visual arts, design, photography, architecture
- **science**: Physics, chemistry, biology, astronomy, research
- **legal**: Laws, court cases, legal advice, regulations
- **religion_philosophy**: Religious discussions, philosophical debates, ethics
- **travel**: Tourism, destinations, travel experiences, culture
- **fashion_beauty**: Clothing, cosmetics, styling, trends
- **automotive**: Cars, motorcycles, repairs, racing
- **real_estate**: Housing, apartments, market trends, interior design
- **parenting_family**: Childcare, parenting advice, family dynamics
- **pets_animals**: Pet care, animal behavior, wildlife
- **environment**: Climate change, ecology, sustainability, pollution
- **social_issues**: Gender, discrimination, social justice, activism
- **career_employment**: Job searching, workplace issues, career advice, interviews
- **hobby_crafts**: DIY, crafting, collecting, hobbies
- **memes_humor**: Internet memes, jokes, shitposting, comedy
- **other**: If truly doesn't fit above, specify the actual domain (e.g., "astrology", "gardening", "fishing")

🚨 **CRITICAL: PLATFORM/SITE NAME vs WORK TITLE DISTINCTION** 🚨

**플랫폼/사이트 vs 작품 구분 원칙:**

1. **검색 결과 분석**: 해당 용어를 검색했을 때
   - 검색 결과가 "~에서 보기", "~에서 연재" 형태 → 플랫폼명
   - 검색 결과가 줄거리, 캐릭터, 작가 정보 → 작품명

2. **본문 맥락 분석**: 본문에서 해당 용어가 어떻게 사용되는지
   - "[용어]에서 ~봤는데", "[용어]에 ~올라왔다" → 플랫폼/사이트
   - "[용어] 재밌네", "[용어] 주인공이" → 작품

3. **콘텐츠 유형 확인**: 본문이 다루는 콘텐츠가 무엇인지
   - "만화인데", "동인지", "짤" 언급 → manga_comics 또는 adult_content 영역
   - 줄거리, 전개, 캐릭터 논의 → novel_literature 영역

Domain Detection Strategy:
- **Terminology clusters**: What specialized vocabulary appears?
- **Context signals**: What kind of knowledge does the poster assume?
- **Discussion patterns**: Academic vs casual, technical vs emotional?
- **Evidence-based**: List key terms that reveal the domain

Korean Morpheme Analysis for Domain Detection:
- **의료 영역**: 한자어 의학 용어(治療, 症狀)와 신체 표현(아프다, 찌릿)이 혼용
- **기술 영역**: 외래어 차용어(algorithm→알고리즘)와 동작 동사(배포, 빌드)가 특징
- **문학 영역**: 서사 구조 어휘(전개, 복선, 반전)와 창작자 관련 어휘(작가, 연재)
- **정치 영역**: 행정/제도 용어(법안, 정책, 의원)와 격식체 사용

도메인 판별 시 **어휘 클러스터 분석**을 통해 포스트가 속한 영역을 파악하라.

**STEP 2: INTENT CLASSIFICATION**
What is the poster trying to achieve?

Intents:
- **discuss_work**: Analyzing/reviewing a SPECIFIC creative work (제목, 캐릭터, 줄거리 등 고유 정보 포함)
- **discuss_genre**: Discussing a genre, trope, or narrative pattern IN GENERAL — not about one specific work
  🚨 discuss_work vs discuss_genre 구분 핵심:
  - 복수형 사용 ("공**들**은", "이런 작품**들**", "주인공**들**이") → discuss_genre
  - 역할 명칭만 사용 ("공", "수", "주인공") + 작품 고유명 없음 → discuss_genre
  - "[장르/트로프]**은/는** [일반적 평가]" 구문 → discuss_genre
  - 특정 작품의 캐릭터명/줄거리/회차/작가 언급 → discuss_work
- **request_recommendation**: Asking for suggestions
- **share_information**: Providing facts, news, or knowledge
- **express_opinion**: Personal thoughts, complaints, praise
- **author_talk**: 작가 비평/비교 — 작가의 커리어, 능력, 장르 적합성 논의
  🚨 author_talk 핵심 신호:
  - 주어가 작가/필명: "[작가명]는 [평가]", "[작가명]도 [했지만]"
  - 명령형/조언형 어미: "-써라", "-써야댐", "-하셈" → 작가에게 장르/방향 지시
  - 작가 간 비교: "[작가A]도...했지만...[작가B]도..." 
  - 장르 약칭 + 작가 조합: "현판이나 써야댐" = 현대판타지 장르를 작가에게 권유
  - 작품이 "~같은거 써라" 형태로 예시 참조됨 → 작품이 주제가 아님
- **ask_question**: Seeking specific information
- **make_joke**: Humor, memes, shitposting
- **platform_meta**: Discussing the platform itself

**STEP 3: COHERENCE CHECK**
Does title + body + comments form a unified discourse?

Coherence Indicators:
- ✅ Title mentions X, body discusses X, comments react to X → COHERENT
- ❌ Title mentions X, body discusses Y, comments about Z → INCOHERENT (shitpost/noise)
- ⚠️ Title mentions X vaguely, body clarifies X → ACCEPTABLE

**STEP 4: TITLE TERM VERIFICATION**
Does the post title contain specific domain-related abbreviations or compound terms?

Korean Abbreviation Patterns:
- **Syllable extraction**: Taking first syllable from each word
  Pattern: "ABC" could be from "A단어 B단어 C단어"
  Detection: 2-4 syllables, all Korean, no spaces
  
- **Morpheme combination**: Combining meaningful parts
  Pattern: "XY물" = work about X and Y (e.g., 회귀 + 물 = regression story)
  Detection: Root word + classifier suffix (물, 좌, 갤, etc.)

- **Mixed abbreviation**: Partial word + full word
  Pattern: "즉사" (immediate death) + category name
  Detection: Sino-Korean prefix + native Korean or category term

Title Term Analysis:
- Extract potential abbreviations from title: What looks like a compound term?
- Identify morphological structure: Is it syllable-based or morpheme-based?
- Check consistency: Does body content relate to this term?
- Flag if title term seems unrelated to body discussion

**STEP 4.5: INVESTIGATIVE SEARCH PLANNING (탐정식 검색 설계)**

You are an investigator. Based on everything you've analyzed so far, think deeply:
- "What do I still NOT know?"
- "What single search would MOST reduce my uncertainty?"
- "What would a human fan do to verify this?"

🧠 **REASONING PROCESS (반드시 이 순서로 사고하라):**

1. **불확실성 진단**: 현재 분석에서 가장 불확실한 것은 무엇인가?
   - 제목의 축약어/신조어가 어떤 작품을 가리키는지?
   - 본문의 고유명사가 캐릭터인지 일반명사인지?
   - 이 글이 정말 소설 토론인지 연상/밈인지?
   
2. **정보 갭 분석**: 그 불확실성을 해소하려면 어떤 정보가 필요한가?
   - 축약어의 정식 제목 → 플랫폼 검색
   - 고유명사의 정체 → 약칭 + 고유명사 교차 검색
   - 도메인 확인 → 핵심 용어 + "웹소설" / "작품" 검색
   
3. **쿼리 설계**: 검색엔진에 가장 효과적인 쿼리 형태는?
   - 핵심 키워드 2-3개 조합, 짧고 명확하게
   - 약칭 + 웹소설 연재 플랫폼명 조합 시 공식 페이지 히트 확률↑
   - 약칭 + 본문 고유명사 = 교차 검증에 효과적
   
4. **불필요한 검색 배제**: 이미 의미가 명확한 일반 표현, 감탄사, 일상어는 검색 가치 없음. is_association_not_discussion=true이면 작품 검색 불필요.

**Output:** search_suggestions에 1-3개 쿼리를 제안하라. purpose에는 "나는 [X]를 모르므로, [Y]를 검색하여 [Z]를 확인하겠다" 형태로 추론 과정을 기술.

**STEP 5: DISCOURSE COHERENCE & RELEVANCE ANALYSIS (담론 일관성 분석)**

이 글이 정말 어떤 대상을 "토론"하고 있는가, 아니면 단순히 "연상/언급"만 한 것인가?

패턴을 외워서 매칭하지 말고, 아래 원칙으로 **텍스트의 의미 구조를 분석**하라.

🧠 **5가지 분석 원칙:**

**원칙 1: 담론 영역의 일관성 (Domain Coherence)**
- 제목이 속하는 의미 영역과 본문이 속하는 의미 영역이 같은가?
- 같은 영역 (예: 둘 다 소설 이야기) → 일관된 담론
- 다른 영역 (예: 제목=소설, 본문=날씨/사진/일상) → 연상/뻘글 가능

**원칙 2: 화제의 지속성 (Topic Continuity)**
- 제목에서 제시한 화제가 본문에서 전개되고, 댓글에서 이어지는가?
- 제목→본문→댓글이 하나의 주제를 관통 → 실제 토론
- 제목과 본문이 단절, 또는 본문이 전혀 다른 이야기 → 연상/뻘글

**원칙 3: 내용의 고유성 (Content Specificity)**
- 본문/댓글에 **특정 작품에만 존재하는 고유한 정보**가 있는가?
  (캐릭터명, 스킬명, 줄거리 디테일, 설정 용어, 전개 비판 등)
- 고유 정보 있음 → 실제로 그 콘텐츠를 소비하고 토론 중
- 고유 정보 없음, 일반적 감상만 → 연상/언급 수준
- ⚠️ **장르/트로프 용어 vs 작품 약칭 구분**: 제목의 핵심어가 장르 패턴(회귀물, 빙의물, 백합난입, 하렘물 등)이고 본문이 그 장르의 **일반적 특성/선호도**를 논하면 → intent="discuss_genre", 특정 작품이 아님

**원칙 4: 화자의 관여도 (Speaker Engagement)**
- 화자가 해당 콘텐츠를 실제로 소비/경험하고 있는 흔적이 있는가?
  ("읽는중", "봤는데", "결말이 왜이러냐", "업데이트 언제")
- 소비 행위 흔적 → 실제 토론
- 소비 흔적 없이 단순 연상 → 뻘글

**원칙 5: 의미론적 맥락 해석 (Contextual Semantics)**
- 커뮤니티 맥락에서 단어를 먼저 해석하라 (일반 사전 의미보다 우선)
- 웹소설 갤러리에서 나온 단어 → 작가명/캐릭터명/작품명일 가능성 먼저 고려
- 응원/기대 패턴("가자 [X]!", "[X] 올 때 됐다")과 함께 나오는 단어는 작품 관련 가능성 높음
- 확실하지 않으면 domain_confidence="medium"으로 두고 후속 Expert에게 위임

**📊 판정 기준 (위에서부터 순서대로 적용):**
1. 제목↔본문이 같은 담론 영역이고, 작품 고유 정보가 있으면 → 실제 토론
2. 제목↔본문 영역이 불일치하고, 화제도 이어지지 않으면 → 연상/뻘글
3. 영역은 불일치하지만 화제가 이어지고, 소비 행위 흔적이 있으면 → 실제 토론
4. 위 어느 것에도 확신이 없으면 → domain_confidence="medium", 후속 Expert에 위임

**⚠️ 과도 해석 금지:**
- 본문이 일상 질문("날씨 언제 풀리지")이면 → 그대로 일상으로 인식, "연재 일정 질문"으로 해석하지 말 것
- 제목에 작품명이 있어도 본문이 무관하면 → 뻘글/연상글
- 연상글이라고 확신할 근거가 없으면 → 중립(medium)으로 두고 후속 Expert에 위임


=== OUTPUT FORMAT ===

You must output VALID JSON only. No markdown, no extra text.

{{
  "discourse_analysis": {{
    "primary_domain": "string",  // ACTUAL domain identified (e.g., "novel_literature", "politics", "gaming", "medical_health", "astrology", etc.)
    "domain_confidence": "high" | "medium" | "low",
    "domain_evidence": ["term1", "term2", ...],  // Key terms that indicate this domain
    "secondary_domains": ["domain1", "domain2", ...],  // Optional: if post spans multiple domains
    
    "intent": "discuss_work" | "discuss_genre" | "author_talk" | "request_recommendation" | "share_information" | "express_opinion" | "ask_question" | "make_joke" | "platform_meta" | "debate" | "vent" | "seek_advice",
    "intent_confidence": "high" | "medium" | "low",
    
    "is_coherent": boolean,  // Do title, body, comments form unified discourse?
    "coherence_reason": "string",  // Why coherent or incoherent?
    
    "title_novel_terms": ["term1", "term2", ...],  // Domain-specific abbreviations found in title
    "title_body_consistency": boolean,  // Do title terms match body content?
    "consistency_note": "string | null",  // If inconsistent, explain the mismatch
    
    "is_association_not_discussion": boolean,  // Recall pattern detected?
    "association_evidence": "string | null",  // Quote showing association pattern
    
    "search_suggestions": [  // Optional: 1-3 targeted search queries you think would help identify the work
      {{
        "query": "string",  // Concise Korean search query (max 30 chars)
        "purpose": "string",  // Why this search would help (English, 1 sentence)
        "priority": 1 | 2 | 3  // 1=highest priority
      }}
    ],
    
    "real_subject": "string",  // What is this post REALLY about? (Korean, 1 sentence)
    "reasoning": "string"  // Detailed reasoning for your analysis (Korean, 2-3 sentences)
  }}
}}

CRITICAL RULES:
- Output ONLY valid JSON
- primary_domain: Use actual domain name (lowercase_underscore format). Don't force into predefined categories.
- secondary_domains: Optional array. Use when post clearly spans multiple domains (e.g., ["gaming", "economy_finance"] for "게임 아이템 거래")
- Be specific: Instead of generic "other", identify actual domain (e.g., "astrology", "gardening", "fishing")
- All Korean text in Korean, domain names andg", "analysis", "thought", "comment" - NEVER include these!
- All Korean text in Korean, technical terms in English
- Be honest - if uncertain, say "medium" or "low" confidence
"""

DISCOURSE_PROMPT = """\
Analyze this post to understand its fundamental domain and intent.

POST DATA:
{post_json}

TASK:
1. Identify the primary domain this post belongs to
2. Understand the poster's intent
3. Check if title-body-comments form coherent discourse
4. Analyze discourse coherence using the 5 principles (Domain Coherence, Topic Continuity, Content Specificity, Speaker Engagement, Contextual Semantics)
5. Determine what this post is REALLY about
6. Design investigative search queries based on your uncertainty analysis

RETURN ONLY THE JSON OUTPUT.
"""


class DiscourseAnalyzer:
    """
    📖 Discourse Analyzer - 담론 분석가
    
    역할:
    - 글의 도메인 컨텍스트 파악 (웹소설 vs 의료 vs 기술 vs 일상)
    - 글의 진짜 의도 파악 (토론 vs 추천요청 vs 밈)
    - 제목-본문-댓글 일관성 검증
    - 연상글 vs 실제 토론 구분
    """
    
    def __init__(self, llm_client):
        self.llm = llm_client
        self.name = "DiscourseAnalyzer"
        self.emoji = "📖"
    
    def analyze(
        self,
        post: Dict[str, Any],
        comments: List[str],
    ) -> Dict[str, Any]:
        """
        Analyze the fundamental discourse of a post.
        
        Args:
            post: Post data
            comments: List of comment texts
            
        Returns:
            Discourse analysis result
        """
        start_time = time.time()
        
        # None 체크
        post = post or {}
        comments = comments or []
        
        # Build post JSON
        post_json = self._build_post_json(post, comments)
        
        # Format prompt
        user_prompt = DISCOURSE_PROMPT.format(
            post_json=json.dumps(post_json, ensure_ascii=False, indent=2)
        )
        
        print(f"[{_ts()}][{self.emoji}] {self.name} 분석 시작: post_id={post.get('post_id')}", file=sys.stderr)
        
        try:
            result = self._call_llm(user_prompt)
            elapsed = time.time() - start_time
            
            analysis = result.get("discourse_analysis", {})
            if not isinstance(analysis, dict):
                # LLM/파서 오류로 discourse_analysis가 dict가 아닌 경우 방어
                analysis = {}
            print(
                f"[{_ts()}][{self.emoji}] {self.name} 완료 ({elapsed:.1f}s): "
                f"domain={analysis.get('primary_domain')}, "
                f"intent={analysis.get('intent')}",
                file=sys.stderr
            )
            
            return result
            
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"[{_ts()}][{self.emoji}] {self.name} 오류 ({elapsed:.1f}s): {e}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
            return self._default_result(str(e))
    
    def _build_post_json(self, post: Dict[str, Any], comments: List[str]) -> Dict[str, Any]:
        """Build simplified post JSON for analysis."""
        content_texts = []
        for block in post.get("content_blocks", []):
            if isinstance(block, dict) and block.get("text"):
                content_texts.append(block["text"])
            elif isinstance(block, str):
                content_texts.append(block)
        
        return {
            "post_id": post.get("post_id"),
            "title": post.get("title", ""),
            "author": post.get("author", ""),
            "content": content_texts,
            "comments": comments[:15],  # More comments for better context
        }
    
    def _call_llm(self, user_prompt: str) -> Dict[str, Any]:
        """Call LLM and parse JSON response."""
        print(f"[{_ts()}][llm-stream] ▶ {self.name.lower()} 토큰 생성 시작...", file=sys.stderr)
        
        try:
            messages = [
                {"role": "system", "content": DISCOURSE_SYSTEM},
                {"role": "user", "content": user_prompt},
            ]
            
            response_text = self.llm._stream_chat_http(
                messages=messages,
                tag="discourse",
                use_grammar=True,
            )
            
            # Parse JSON (handle any formatting issues)
            result = parse_json_with_think_removal(response_text)
            
            return result
            
        except Exception as e:
            print(f"[{_ts()}][{self.emoji}] LLM 호출 실패: {e}", file=sys.stderr)
            raise
    
    def _default_result(self, error: str) -> Dict[str, Any]:
        """Return safe default when LLM fails."""
        return {
            "discourse_analysis": {
                "primary_domain": "other",
                "domain_confidence": "low",
                "domain_evidence": [],
                "intent": "express_opinion",
                "intent_confidence": "low",
                "is_coherent": True,
                "coherence_reason": f"분석 오류: {error}",
                "is_association_not_discussion": False,
                "association_evidence": None,
                "real_subject": "분석 실패",
                "reasoning": f"오류로 인해 기본값 반환: {error}",
            }
        }
