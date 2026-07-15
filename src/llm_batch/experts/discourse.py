"""
DiscourseAnalyzer Expert - 담론 분석가
글의 본질적 의도와 도메인 컨텍스트를 파악하는 전문가
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from typing import Any, Dict, List, Optional

from .decoder import KNOWN_ABBREVIATIONS
from .utils import parse_json_with_think_removal, _ts, KNOWN_TITLE_ABBREVIATIONS
from ..prompts.prompt_router import build_discourse_system_prompt
from ..domain.rules import surface_expression_reread_notes, surface_expression_reread_public_notes


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
- **author_discussion**: 특정 작가의 작품 스타일/패턴/경향을 논의하는 글
  🚨 author_discussion vs author_talk 구분:
  - author_talk: 작가에게 비평/조언/지시 → 결과물 평가
  - author_discussion: 작가의 작품 패턴/특징 관찰/논의 → 작가 스타일 분석
  핵심 신호:
  - 작가명(필명) + 해당 작가의 복수 작품/캐릭터 참조
  - "이 작가는 항상 ~한 캐릭터를 쓴다", "[작가명] 작품은 ~패턴이 있다"
  - 작가명이 주어이고 작품 특성이 서술어: "[필명] 작품들은 여주가 항상 ~"
  - is_relevant=True로 처리 (작가 단위의 작품 토론)
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

Surface typo/paraphrase hints:
- If POST DATA contains `surface_paraphrase_notes`, treat them as semantic reading aids.
- These hints are packet-local rereading aids, not fixed lexical rules.
- Hints with `role=non_title_semantic_context` are NOT title/alias evidence.
- Do not copy their `source_surface` into `title_novel_terms` or search suggestions.
- Use them only to reread whether the surrounding sentence is a typo/abbreviation/spacing-break expression, a comment reaction, or a direct title/alias mention.

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
  * 🔑 **"[한글1~5자]물" 패턴은 모두 장르 용어**: 일상물, 힐링물, 좀비물, 먹방물, 집착물 등 "~물"로 끝나는 짧은 한글 단어는 장르 카테고리이지 소설 제목이 아님. 리스트에 없는 신조어 "X물"도 동일 적용

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
    
    "intent": "discuss_work" | "discuss_genre" | "author_talk" | "author_discussion" | "request_recommendation" | "share_information" | "express_opinion" | "ask_question" | "make_joke" | "platform_meta" | "debate" | "vent" | "seek_advice",
    "intent_confidence": "high" | "medium" | "low",
    "speech_act": "review" | "complaint" | "question" | "support" | "announcement" | "banter" | "comparison" | "other",
    "target_kind": "work" | "author" | "platform" | "genre" | "community" | "multi" | "none" | "unknown",
    
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
- FORBIDDEN FIELDS: "thinking", "reasoning_process", "analysis", "thought", "comment" - NEVER include these!
- All Korean text in Korean, technical terms in English
- Be honest - if uncertain, say "medium" or "low" confidence
- 매체 단정 금지: 본문/댓글에 직접 단서가 없으면 "웹툰/만화/애니"를 확정 표현으로 쓰지 말고 "작품(매체 미확정)"으로 표현하라.
- search_suggestions도 동일 원칙 적용: 매체 단서가 없으면 "웹툰/애니" 전제 쿼리 대신 중립 쿼리(작품명/등장인물/줄거리 중심)를 제안하라.
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
        gatekeeper_result: Optional[Dict[str, Any]] = None,
        ctx: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Analyze the fundamental discourse of a post.
        
        Args:
            post: Post data
            comments: List of comment texts
            gatekeeper_result: Optional gatekeeper output for discourse-aware overlay
            ctx: Conversation context (time-attack and runtime hints)
            
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
            result = self._call_llm(
                user_prompt,
                post=post,
                comments=comments,
                gatekeeper_result=gatekeeper_result,
                ctx=ctx,
            )
            result = self._sanitize_result(result, post_json=post_json)
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

    def _sanitize_result(
        self,
        result: Any,
        *,
        post_json: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """
        Sanitize malformed discourse output.
        - discourse_analysis must be dict
        - domain_evidence/secondary_domains must be string lists
        - fill minimal intent when missing
        """
        if not isinstance(result, dict):
            return self._default_result("discourse result is not dict")

        analysis = result.get("discourse_analysis")
        if not isinstance(analysis, dict):
            return self._default_result("discourse_analysis is not dict")

        raw_domain_evidence = analysis.get("domain_evidence")
        domain_evidence: List[str] = []
        numeric_domain_evidence = False
        if isinstance(raw_domain_evidence, list):
            if raw_domain_evidence and all(isinstance(v, (int, float)) for v in raw_domain_evidence):
                numeric_domain_evidence = True
                print(
                    f"[{_ts()}][{self.emoji}] ⚠️ discourse domain_evidence 숫자 배열 감지 → 문자열 증거로 정리",
                    file=sys.stderr,
                )
            for item in raw_domain_evidence:
                if isinstance(item, str):
                    clean = " ".join(item.split())
                    if clean and not clean.isdigit():
                        domain_evidence.append(clean)
                if len(domain_evidence) >= 12:
                    break
        if numeric_domain_evidence and not domain_evidence:
            domain_evidence = self._fallback_domain_evidence(post_json)
            print(
                f"[{_ts()}][{self.emoji}] 🛡️ discourse domain_evidence 복구: "
                f"{len(domain_evidence)}개 (title/content 기반)",
                file=sys.stderr,
            )
        analysis["domain_evidence"] = domain_evidence

        raw_secondary = analysis.get("secondary_domains")
        secondary_domains: List[str] = []
        if isinstance(raw_secondary, list):
            for item in raw_secondary:
                if isinstance(item, str):
                    clean = item.strip()
                    if clean:
                        secondary_domains.append(clean)
                if len(secondary_domains) >= 8:
                    break
        analysis["secondary_domains"] = secondary_domains

        intent = analysis.get("intent")
        if not isinstance(intent, str) or not intent.strip():
            if str(analysis.get("primary_domain") or "").strip() == "memes_humor":
                analysis["intent"] = "make_joke"
            else:
                analysis["intent"] = "express_opinion"
            analysis["intent_confidence"] = analysis.get("intent_confidence") or "low"
        elif numeric_domain_evidence:
            # 숫자 폭주가 있었던 응답은 불안정하므로 confidence를 보수적으로 하향
            cur_conf = str(analysis.get("intent_confidence") or "").strip().lower()
            if cur_conf in ("max", "high", "medium"):
                analysis["intent_confidence"] = "low"

        speech_act = analysis.get("speech_act")
        target_kind = analysis.get("target_kind")
        if not isinstance(speech_act, str) or not speech_act.strip() or not isinstance(target_kind, str) or not target_kind.strip():
            inferred = self._infer_speech_act_target_kind(analysis, post_json)
            analysis["speech_act"] = inferred["speech_act"]
            analysis["target_kind"] = inferred["target_kind"]
        else:
            analysis["speech_act"] = str(speech_act).strip().lower()
            analysis["target_kind"] = str(target_kind).strip().lower()

        analysis = self._apply_semantic_seed_review(analysis, post_json)
        analysis = self._sanitize_surface_paraphrase_context(analysis, post_json)
        analysis = self._apply_short_worklike_recovery(analysis, post_json)

        # 매체(웹툰/애니 등) 과단정 완화:
        # 본문/댓글에 매체 단서가 없는데 결과 텍스트가 특정 매체를 확정하면
        # reason/search_suggestions를 중립 문구로 보정한다.
        analysis = self._sanitize_speculative_medium_claims(analysis, post_json)

        return {"discourse_analysis": analysis}

    @staticmethod
    def _semantic_seed_norm(value: Any) -> str:
        return re.sub(r"[^0-9A-Za-z가-힣]", "", str(value or "").lower())

    def _is_known_alias_term(self, term: str) -> bool:
        term_norm = self._semantic_seed_norm(term)
        if not term_norm:
            return False
        for mapping in (KNOWN_ABBREVIATIONS, KNOWN_TITLE_ABBREVIATIONS):
            try:
                keys = mapping.keys()
            except Exception:
                keys = []
            for raw_key in keys:
                key_norm = self._semantic_seed_norm(raw_key)
                if len(key_norm) >= 3 and key_norm == term_norm:
                    return True
        return False

    def _text_contains_known_alias_term(self, text: Any) -> bool:
        text_norm = self._semantic_seed_norm(text)
        if not text_norm:
            return False
        for mapping in (KNOWN_ABBREVIATIONS, KNOWN_TITLE_ABBREVIATIONS):
            try:
                items = mapping.items()
            except Exception:
                items = []
            for raw_key, raw_title in items:
                key_norm = self._semantic_seed_norm(raw_key)
                title_norm = self._semantic_seed_norm(raw_title)
                if key_norm and len(key_norm) >= 2 and key_norm in text_norm:
                    return True
                if title_norm and len(title_norm) >= 3 and title_norm in text_norm:
                    return True
        return False

    def _is_social_lament_or_generic_discourse_context(self, text: Any) -> bool:
        """소설 관련 단어가 있어도 단일 작품 매칭이 아닌 친구/대화 한탄인지 본다."""
        raw = str(text or "")
        if not raw.strip():
            return False
        norm = self._semantic_seed_norm(raw)
        if not norm:
            return False

        # 기억 회수/작품 찾기 글은 친구/장면 단어가 있어도 검색 가치가 있으므로 제외한다.
        memory_or_lookup = bool(
            re.search(
                r"(무슨|어느|어떤)\s*(?:웹)?소설|(?:웹)?소설(?:인|인지|이었|였|이였)|"
                r"기억(?:이)?\s*(?:안\s*남|안남|안\s*나|안나)|찾(?:고|아|음|는)|대사|장면",
                raw,
            )
        )
        if memory_or_lookup:
            return False

        webnovel_general = any(
            self._semantic_seed_norm(term) in norm
            for term in (
                "소설",
                "웹소설",
                "웹소",
                "장르소설",
                "ts",
                "갈드컵",
                "주류",
                "트로프",
                "장르",
            )
        )
        if not webnovel_general:
            return False

        social_anchor = any(
            self._semantic_seed_norm(term) in norm
            for term in (
                "친구",
                "지인",
                "같이",
                "함께",
                "밥",
                "혼밥",
                "토론",
                "대화",
                "얘기",
                "이야기",
                "말할사람",
                "보는친구",
                "읽는친구",
            )
        )
        wish_or_lament = bool(
            re.search(
                r"(있으면\s*좋|있었으면|없어서|없네|부럽|외롭|한탄|같이\s*(?:보|읽|얘기|이야기|토론)|"
                r"(?:얘기|이야기|토론)\s*할\s*(?:친구|사람|상대))",
                raw,
            )
        )
        return bool(social_anchor and wish_or_lament)

    def _semantic_seed_review_enabled(self) -> bool:
        raw = str(os.getenv("LLM_SEMANTIC_SEED_REVIEW", "auto") or "auto").strip().lower()
        return raw not in {"0", "false", "off", "no", "disabled"}

    def _should_run_semantic_seed_review(
        self,
        analysis: Dict[str, Any],
        post_json: Dict[str, Any] | None,
    ) -> bool:
        if not self._semantic_seed_review_enabled():
            return False
        if not isinstance(analysis, dict) or not isinstance(post_json, dict):
            return False

        title_terms = [
            str(term or "").strip()
            for term in (analysis.get("title_novel_terms") or [])
            if str(term or "").strip()
        ]
        suggestions = [
            item for item in (analysis.get("search_suggestions") or [])
            if isinstance(item, dict) and str(item.get("query") or "").strip()
        ]
        notes = post_json.get("surface_paraphrase_notes") or []
        title = str(post_json.get("title") or "")
        content = " ".join(str(x or "") for x in (post_json.get("content") or []))
        comments = " ".join(str(x or "") for x in (post_json.get("comments") or [])[:5])
        full_text = " ".join([title, content, comments]).strip()
        if not full_text:
            return False

        if notes:
            return True

        if title_terms and all(self._is_known_alias_term(term) for term in title_terms):
            return False

        short_context = len(self._semantic_seed_norm(full_text)) <= 180
        sentence_like_title = bool(
            re.search(
                r"(소신발언|잡담|한탄|몰랐|인\s*줄|줄\s*알|어려\s*보|어린|나이|외모|묘사|머리|친구|같이|"
                r"싶|없|있|네|냐|임|듯|보임|잖아|ㅋㅋ|ㅠㅠ|\?{2,}|!{2,})",
                full_text,
            )
        )
        query_probe = any(
            re.search(
                r"(정식\s*제목|웹소설|소설|캐릭터|등장인물|작품명|줄임말|뜻|의미)",
                str(item.get("query") or "") + " " + str(item.get("purpose") or ""),
            )
            for item in suggestions
        )
        social_lament_context = self._is_social_lament_or_generic_discourse_context(full_text)
        target_kind = str(analysis.get("target_kind") or "").strip().lower()
        intent = str(analysis.get("intent") or "").strip().lower()
        if not title_terms and not suggestions:
            claimed_specific_work = target_kind in {"work", "character"} or intent in {"discuss_work"}
            return bool(
                short_context
                and (claimed_specific_work or social_lament_context)
                and (sentence_like_title or social_lament_context)
                and not self._text_contains_known_alias_term(full_text)
            )

        ambiguous_short_term = any(
            2 <= len(self._semantic_seed_norm(term)) <= 4
            and re.fullmatch(r"[가-힣]+", self._semantic_seed_norm(term) or "")
            and not self._is_known_alias_term(term)
            for term in title_terms
        )

        return bool(
            short_context
            and (ambiguous_short_term or query_probe or social_lament_context)
            and (sentence_like_title or target_kind in {"work", "character", "unknown"} or intent in {"discuss_work", "express_opinion"})
        )

    def _call_semantic_seed_review(
        self,
        analysis: Dict[str, Any],
        post_json: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        if not hasattr(self.llm, "_stream_chat_http"):
            return None

        title_terms = [
            str(term or "").strip()
            for term in (analysis.get("title_novel_terms") or [])
            if str(term or "").strip()
        ][:8]
        suggestions = []
        for item in (analysis.get("search_suggestions") or [])[:8]:
            if not isinstance(item, dict):
                continue
            query = str(item.get("query") or "").strip()
            if not query:
                continue
            suggestions.append({
                "query": query,
                "purpose": str(item.get("purpose") or "")[:160],
            })

        comment_context = post_json.get("comment_context")
        if not comment_context:
            comment_context = post_json.get("comment_context_lines") or []
        comment_dialogue_context = post_json.get("comment_dialogue_context")
        if not comment_dialogue_context:
            comment_dialogue_context = post_json.get("comment_dialogue_context_lines") or []

        surface_public_notes = surface_expression_reread_public_notes(
            post_json.get("surface_paraphrase_notes", [])[:8]
        )
        payload = {
            "post_id": post_json.get("post_id"),
            "title": post_json.get("title", ""),
            "content": post_json.get("content", [])[:4],
            "comments": post_json.get("comments", [])[:8],
            "comment_context": comment_context[:8],
            "comment_dialogue_context": comment_dialogue_context[:8],
            "surface_paraphrase_notes": surface_public_notes,
            "current_intent": analysis.get("intent"),
            "current_target_kind": analysis.get("target_kind"),
            "title_seed_candidates": title_terms,
            "search_suggestions": suggestions,
        }
        user_prompt = f"""아래 게시글의 작품명/별칭 후보 seed가 실제 검색할 가치가 있는지 재검토하세요.
목표는 작품 매칭이 아니라, 1차 담론 분석이 문장 일부·인명처럼 보이는 표면·일반 반응을 작품 seed로 과승격했는지 확인하는 것입니다.
숨은 사고과정은 쓰지 말고 공개 가능한 짧은 근거만 JSON으로 답하세요.

판정 원칙:
- title_seed_candidates가 실제 작품명/약칭이면 keep.
- 사람 이름처럼 보이는 표면, 문장 일부, 일반어, 화행 표지, 작품 고유 앵커가 없는 일반 반응이라면 context_only 또는 drop.
- 짧은 인명/캐릭터명처럼 보이는 seed는 단독으로 keep하지 않습니다. 원문 title/body/comment에 작품명, 공식 별칭, 작가, 회차, 플랫폼 작품 URL, 또는 작품 고유 설정 앵커가 없고 일반 반응만 있으면 context_only 또는 drop입니다.
- 직접 작품 앵커가 없으면 content_interpretation/reason에서 "작품 속", "원작", "해당 작품"처럼 작품 존재를 확정하는 표현을 쓰지 말고, "인명/캐릭터명처럼 보이는 표면", "대상", "댓글 반응"처럼 약하게 표현합니다.
- 오타/축약처럼 보이는 가능성은 "표현 오타/축약 패턴(범용)"으로만 다룹니다. 즉, 표현 오타/축약 패턴 자체를 범용 신호로 보는 것이지 특정 정상형을 복원하지 않습니다.
- 어떤 표면 범주도 예시적 위험 신호일 뿐이며, 같은 계열을 자동 차단/허용하는 일반규칙으로 만들지 않습니다.
- 특정 표면어를 정답 표현으로 결정적으로 치환하거나, 전역 규칙으로 만들거나, 다른 post에 재사용하지 않습니다.
- content_interpretation/reason에는 "X -> Y"식 단정 치환을 쓰지 말고, 해당 packet 안에서 작품 고유 앵커가 부족한 원문 반응/문장 일부 가능성이 있어 작품 seed가 아니라는 식으로 약하게 씁니다.
- "소설 보는 친구", "같이 얘기할 사람", "토론할 친구"처럼 단일 작품 지시가 아니라 사회적 한탄/장르 잡담인 글은 작품명 검색 seed로 확정하지 않습니다.
- 재해독 결과가 직접 작품 앵커가 아니면 작품 seed로 쓰지 않습니다.
- surface_paraphrase_notes의 role이 non_title_semantic_context이면 작품 seed 근거가 아니라 원문 이해 힌트로 우선 반영.
- comment_dialogue_context가 있으면 본문 작성자와 댓글 작성자의 발화 흐름을 같이 읽습니다.
- 단, speaker/author/ip/comment_id/reply_to는 대화 흐름 메타이지 작품명/별칭/공식 근거가 아닙니다.
- 재해독 결과가 직접 작품 앵커 없는 원문 반응/문장 일부라면 작품명/별칭 후보에서 제외하고 public reason에 근거 경계를 남깁니다.
- 구체 사례 문구를 일반 규칙으로 만들지 말고, 각 packet의 title/body/comment에서 단일 작품 지시가 있는지 먼저 확인합니다.
- search_suggestions가 그 잘못된 seed를 검색으로 확장하면 drop.
- 캐릭터명 단독 + 일반어 검색은 작품 식별을 보장하지 않으므로, 직접 작품 앵커가 없으면 drop 또는 low-confidence context_only로 둡니다.
- 특정 작품 토론인지 불확실하면 is_specific_work_discussion=false로 두고, 단정하지 않습니다.

INPUT:
{json.dumps(payload, ensure_ascii=False, indent=2)}

OUTPUT JSON:
{{
  "post_intent": "게시글의 자연어 의도 1문장",
  "content_interpretation": "표현 오타/축약 패턴(범용)으로만 설명하고, 특정 표면어 치환을 단정하지 않는 1문장",
  "is_specific_work_discussion": true,
  "recommended_intent": "discuss_work | express_opinion | ask_question | make_joke | other",
  "recommended_target_kind": "work | character | author | trope | community | unknown",
  "title_seed_reviews": [
    {{"surface": "후보", "decision": "keep | context_only | drop", "confidence": "high | medium | low", "reason": "짧은 근거"}}
  ],
  "search_query_reviews": [
    {{"query": "검색쿼리", "decision": "keep | drop", "confidence": "high | medium | low", "reason": "짧은 근거"}}
  ],
  "warnings": ["필요 시 짧은 공개 경고"]
}}"""
        try:
            response_text = self.llm._stream_chat_http(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "당신은 웹소설 커뮤니티 게시글의 자연어 의도를 읽고, "
                            "검색 seed가 작품명인지 문맥 표현인지 보수적으로 판정하는 전문가입니다. "
                            "반드시 JSON만 반환하세요."
                        ),
                    },
                    {"role": "user", "content": user_prompt},
                ],
                tag="discourse_semantic_seed_guard",
                use_grammar=True,
                max_tokens=1024,
            )
            parsed = parse_json_with_think_removal(response_text)
            if isinstance(parsed, dict):
                return parsed
        except Exception as exc:
            print(
                f"[{_ts()}][{self.emoji}] ⚠️ semantic seed review 실패: {exc}",
                file=sys.stderr,
            )
        return None

    def _apply_semantic_seed_review(
        self,
        analysis: Dict[str, Any],
        post_json: Dict[str, Any] | None,
    ) -> Dict[str, Any]:
        if not self._should_run_semantic_seed_review(analysis, post_json):
            return analysis
        if not isinstance(post_json, dict):
            return analysis

        review = self._call_semantic_seed_review(analysis, post_json)
        if not isinstance(review, dict):
            return analysis

        analysis["semantic_seed_review"] = {
            "post_intent": str(review.get("post_intent") or "")[:300],
            "content_interpretation": str(review.get("content_interpretation") or "")[:300],
            "is_specific_work_discussion": bool(review.get("is_specific_work_discussion", True)),
            "recommended_intent": str(review.get("recommended_intent") or "")[:80],
            "recommended_target_kind": str(review.get("recommended_target_kind") or "")[:80],
            "warnings": [
                str(item or "").strip()[:160]
                for item in (review.get("warnings") or [])
                if str(item or "").strip()
            ][:6],
        }

        def _decision(value: Any) -> str:
            return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")

        def _conf_ok(value: Any) -> bool:
            return _decision(value) in {"high", "medium", "med"}

        removable_norms: set[str] = set()
        context_terms: List[str] = []
        for item in (review.get("title_seed_reviews") or []):
            if not isinstance(item, dict):
                continue
            surface = str(item.get("surface") or item.get("term") or "").strip()
            norm = self._semantic_seed_norm(surface)
            if not norm or self._is_known_alias_term(surface):
                continue
            decision = _decision(item.get("decision"))
            if decision in {"context_only", "context", "drop", "non_title", "not_title", "move_to_context"} and _conf_ok(item.get("confidence")):
                removable_norms.add(norm)
                context_terms.append(surface)

        keep_query_norms = {
            self._semantic_seed_norm(item.get("query"))
            for item in (review.get("search_query_reviews") or [])
            if isinstance(item, dict)
            and _decision(item.get("decision")) in {"keep", "search", "allow", "verify"}
            and _conf_ok(item.get("confidence"))
            and self._semantic_seed_norm(item.get("query"))
        }
        query_keep_supports_removed_term = bool(
            removable_norms
            and any(
                norm and query_norm and norm in query_norm
                for norm in removable_norms
                for query_norm in keep_query_norms
            )
        )

        raw_terms = [
            str(term or "").strip()
            for term in (analysis.get("title_novel_terms") or [])
            if str(term or "").strip()
        ]
        if removable_norms and raw_terms:
            kept_terms: List[str] = []
            removed_terms: List[str] = []
            for term in raw_terms:
                norm = self._semantic_seed_norm(term)
                if norm in removable_norms and not self._is_known_alias_term(term):
                    removed_terms.append(term)
                else:
                    kept_terms.append(term)
            if removed_terms:
                analysis["title_novel_terms"] = kept_terms
                context_terms.extend(removed_terms)
                warnings = [
                    str(item or "").strip()
                    for item in (analysis.get("warnings") or [])
                    if str(item or "").strip()
                ]
                if "semantic_seed_review_non_title_terms_removed" not in warnings:
                    warnings.append("semantic_seed_review_non_title_terms_removed")
                analysis["warnings"] = warnings

        drop_queries = {
            self._semantic_seed_norm(item.get("query"))
            for item in (review.get("search_query_reviews") or [])
            if isinstance(item, dict)
            and _decision(item.get("decision")) in {"drop", "remove", "no_search", "context_only"}
            and _conf_ok(item.get("confidence"))
            and self._semantic_seed_norm(item.get("query"))
        }
        if drop_queries and isinstance(analysis.get("search_suggestions"), list):
            kept_suggestions: List[Dict[str, Any]] = []
            removed_queries: List[str] = []
            for suggestion in analysis.get("search_suggestions") or []:
                if not isinstance(suggestion, dict):
                    continue
                query = str(suggestion.get("query") or "").strip()
                if self._semantic_seed_norm(query) in drop_queries:
                    removed_queries.append(query)
                    continue
                kept_suggestions.append(suggestion)
            if removed_queries:
                analysis["search_suggestions"] = kept_suggestions
                warnings = [
                    str(item or "").strip()
                    for item in (analysis.get("warnings") or [])
                    if str(item or "").strip()
                ]
                if "semantic_seed_review_search_suggestions_removed" not in warnings:
                    warnings.append("semantic_seed_review_search_suggestions_removed")
                analysis["warnings"] = warnings

        if (
            removable_norms
            and not analysis.get("title_novel_terms")
            and not query_keep_supports_removed_term
            and isinstance(analysis.get("search_suggestions"), list)
        ):
            kept_suggestions = []
            removed_queries = []
            for suggestion in analysis.get("search_suggestions") or []:
                if not isinstance(suggestion, dict):
                    continue
                query = str(suggestion.get("query") or "").strip()
                query_norm = self._semantic_seed_norm(query)
                if any(norm and norm in query_norm for norm in removable_norms):
                    removed_queries.append(query)
                    continue
                kept_suggestions.append(suggestion)
            if removed_queries:
                analysis["search_suggestions"] = kept_suggestions
                warnings = [
                    str(item or "").strip()
                    for item in (analysis.get("warnings") or [])
                    if str(item or "").strip()
                ]
                if "semantic_seed_review_search_suggestions_removed" not in warnings:
                    warnings.append("semantic_seed_review_search_suggestions_removed")
                analysis["warnings"] = warnings

        if context_terms:
            merged_context_terms = [
                str(item or "").strip()
                for item in (analysis.get("semantic_seed_review_context_terms") or [])
                if str(item or "").strip()
            ]
            merged_context_terms.extend(context_terms)
            analysis["semantic_seed_review_context_terms"] = list(dict.fromkeys(merged_context_terms))

        specific_work = bool(review.get("is_specific_work_discussion", True))
        if removable_norms and not analysis.get("title_novel_terms") and not query_keep_supports_removed_term:
            specific_work = False
            if isinstance(analysis.get("semantic_seed_review"), dict):
                analysis["semantic_seed_review"]["is_specific_work_discussion"] = False
        if not specific_work and not analysis.get("title_novel_terms"):
            recommended_intent = _decision(review.get("recommended_intent"))
            if recommended_intent in {"express_opinion", "ask_question", "make_joke", "other"}:
                analysis["intent"] = recommended_intent
                analysis["intent_confidence"] = "medium"
            elif str(analysis.get("intent") or "").strip().lower() == "discuss_work":
                analysis["intent"] = "express_opinion"
                analysis["intent_confidence"] = "low"

            recommended_target = _decision(review.get("recommended_target_kind"))
            if recommended_target in {"character", "author", "trope", "community", "unknown"}:
                analysis["target_kind"] = recommended_target
            elif str(analysis.get("target_kind") or "").strip().lower() == "work":
                analysis["target_kind"] = "unknown"

            if not str(analysis.get("real_subject") or "").strip():
                analysis["real_subject"] = str(
                    review.get("content_interpretation")
                    or review.get("post_intent")
                    or "특정 작품명 확정보다는 게시글 자연어 의도 확인이 필요한 문맥"
                )[:300]
            warnings = [
                str(item or "").strip()
                for item in (analysis.get("warnings") or [])
                if str(item or "").strip()
            ]
            if "semantic_seed_review_specific_work_denied" not in warnings:
                warnings.append("semantic_seed_review_specific_work_denied")
            analysis["warnings"] = warnings

        return analysis

    def _sanitize_surface_paraphrase_context(
        self,
        analysis: Dict[str, Any],
        post_json: Dict[str, Any] | None,
    ) -> Dict[str, Any]:
        if not isinstance(analysis, dict) or not isinstance(post_json, dict):
            return analysis

        text_parts = [str(post_json.get("title") or "")]
        text_parts.extend(str(x or "") for x in (post_json.get("content") or []))
        text_parts.extend(str(x or "") for x in (post_json.get("comments") or [])[:8])
        full_text = " ".join(text_parts)

        notes: List[Dict[str, str]] = []
        for item in (post_json.get("surface_paraphrase_notes") or []):
            if isinstance(item, dict):
                notes.append({str(k): str(v) for k, v in item.items()})
        notes.extend(surface_expression_reread_notes(full_text))
        if not notes:
            return analysis

        semantic_review = analysis.get("semantic_seed_review")
        warnings = [
            str(item or "").strip()
            for item in (analysis.get("warnings") or [])
            if str(item or "").strip()
        ]
        review_allows_sanitize = bool(
            isinstance(semantic_review, dict)
            and semantic_review.get("is_specific_work_discussion") is False
        ) or any(
            warning in {
                "semantic_seed_review_non_title_terms_removed",
                "semantic_seed_review_search_suggestions_removed",
                "semantic_seed_review_specific_work_denied",
            }
            for warning in warnings
        )
        if not review_allows_sanitize:
            return analysis

        def _norm(value: Any) -> str:
            return re.sub(r"[^0-9A-Za-z가-힣]", "", str(value or "").lower())

        note_norms = {
            _norm(note.get("source_surface"))
            for note in notes
            if _norm(note.get("source_surface"))
        }

        raw_terms = [
            str(term or "").strip()
            for term in (analysis.get("title_novel_terms") or [])
            if str(term or "").strip()
        ]
        kept_terms: List[str] = []
        removed_terms: List[str] = []
        for term in raw_terms:
            term_norm = _norm(term)
            if term_norm and any(term_norm == note_norm or term_norm in note_norm for note_norm in note_norms):
                removed_terms.append(term)
            else:
                kept_terms.append(term)

        def _known_alias(term: str) -> bool:
            term_norm = _norm(term)
            if not term_norm:
                return False
            for mapping in (KNOWN_ABBREVIATIONS, KNOWN_TITLE_ABBREVIATIONS):
                try:
                    keys = mapping.keys()
                except Exception:
                    keys = []
                for raw_key in keys:
                    key_norm = _norm(raw_key)
                    if len(key_norm) >= 3 and key_norm == term_norm:
                        return True
            return False

        surface_expression_context = bool(note_norms)
        character_like_terms: List[str] = []
        if surface_expression_context:
            next_terms: List[str] = []
            for term in kept_terms:
                term_norm = _norm(term)
                if (
                    term_norm
                    and 2 <= len(term_norm) <= 4
                    and re.fullmatch(r"[가-힣]+", term_norm)
                    and not _known_alias(term)
                ):
                    character_like_terms.append(term)
                else:
                    next_terms.append(term)
            kept_terms = next_terms

        if removed_terms or character_like_terms:
            analysis["title_novel_terms"] = kept_terms
            moved_terms = list(dict.fromkeys(removed_terms + character_like_terms))
            analysis["surface_paraphrase_context_terms"] = moved_terms
            warnings = [
                str(item or "").strip()
                for item in (analysis.get("warnings") or [])
                if str(item or "").strip()
            ]
            if "surface_paraphrase_non_title_terms_removed" not in warnings:
                warnings.append("surface_paraphrase_non_title_terms_removed")
            analysis["warnings"] = warnings

            if surface_expression_context and not kept_terms:
                if str(analysis.get("target_kind") or "").strip().lower() == "work":
                    analysis["target_kind"] = "unknown"
                if str(analysis.get("intent") or "").strip().lower() == "discuss_work":
                    analysis["intent"] = "express_opinion"
                    analysis["intent_confidence"] = "low"
                if str(analysis.get("speech_act") or "").strip().lower() in {"review", "discussion"}:
                    analysis["speech_act"] = "banter"
                analysis["real_subject"] = (
                    "표현 오타/축약 패턴(범용)으로 재검토해야 하는 짧은 커뮤니티 반응"
                )
                if isinstance(analysis.get("semantic_seed_review"), dict):
                    analysis["semantic_seed_review"]["is_specific_work_discussion"] = False
                    existing_interp = str(
                        analysis["semantic_seed_review"].get("content_interpretation") or ""
                    ).strip()
                    if not existing_interp:
                        analysis["semantic_seed_review"]["content_interpretation"] = (
                            "표현 오타/축약 패턴(범용)이며 작품명/별칭 seed가 아니다."
                        )
                if "surface_paraphrase_specific_work_denied" not in warnings:
                    warnings.append("surface_paraphrase_specific_work_denied")
                    analysis["warnings"] = warnings
            if surface_expression_context:
                moved_norms = {_norm(term) for term in moved_terms if _norm(term)}
                filtered_suggestions: List[Dict[str, Any]] = []
                removed_suggestions: List[str] = []
                for suggestion in analysis.get("search_suggestions") or []:
                    if not isinstance(suggestion, dict):
                        continue
                    query = str(suggestion.get("query") or "").strip()
                    query_norm = _norm(query)
                    if not query or not query_norm:
                        continue
                    generic_surface_probe = bool(
                        re.search(r"\d+[A-Za-z가-힣]{0,12}", query)
                        and re.search(r"(소설|웹소설|작품|제목|정식|캐릭터|등장인물)", query)
                    )
                    mentions_context_term = any(
                        term_norm and term_norm in query_norm
                        for term_norm in moved_norms
                    )
                    mentions_note = any(
                        note_norm and (note_norm in query_norm or query_norm in note_norm)
                        for note_norm in note_norms
                    )
                    if generic_surface_probe or mentions_context_term or mentions_note:
                        removed_suggestions.append(query)
                        continue
                    filtered_suggestions.append(suggestion)
                if removed_suggestions:
                    analysis["search_suggestions"] = filtered_suggestions
                    warnings = [
                        str(item or "").strip()
                        for item in (analysis.get("warnings") or [])
                        if str(item or "").strip()
                    ]
                    if "surface_paraphrase_search_suggestions_removed" not in warnings:
                        warnings.append("surface_paraphrase_search_suggestions_removed")
                    analysis["warnings"] = warnings
        return analysis

    def _apply_short_worklike_recovery(
        self,
        analysis: Dict[str, Any],
        post_json: Dict[str, Any] | None,
    ) -> Dict[str, Any]:
        if not isinstance(analysis, dict) or not isinstance(post_json, dict):
            return analysis

        title = str(post_json.get("title") or "").strip()
        content = " ".join(str(x or "").strip() for x in (post_json.get("content") or []) if str(x or "").strip())
        title_terms = [str(x or "").strip() for x in (analysis.get("title_novel_terms") or []) if str(x or "").strip()]
        if not title_terms or not title:
            return analysis

        title_norm = re.sub(r"\s+", "", title)
        content_norm = re.sub(r"\s+", "", content)
        if len(content_norm) > 16:
            return analysis

        has_title_term = any(term and term in title for term in title_terms)
        cheer_like = any(tok in content_norm for tok in ("드가자", "가자", "가즈아", "레츠고", "화이팅", "슛"))
        temporal_or_serial_frame = bool(
            re.search(r"(?:\d+\s*(?:일|주|달|개월|년|화)\s*만의|올해|이번|마지막|다시|드디어|오랜만)", title)
        ) or any(tok in title_norm.lower() for tok in ("연재", "정시연재", "복귀", "재개", "on", "up"))
        title_led_event = bool(
            temporal_or_serial_frame and re.search(r"(?:슛|on|왔다|됐다)[~!ㅋㅎ?]*$", title, flags=re.IGNORECASE)
        )

        primary_domain = str(analysis.get("primary_domain") or "").strip().lower()
        target_kind = str(analysis.get("target_kind") or "").strip().lower()
        speech_act = str(analysis.get("speech_act") or "").strip().lower()
        assoc = bool(analysis.get("is_association_not_discussion"))
        title_body_consistency = analysis.get("title_body_consistency")

        if not (has_title_term and temporal_or_serial_frame and (cheer_like or title_led_event)):
            return analysis
        if primary_domain not in {"memes_humor", "daily_life", "other"} and target_kind not in {"none", "community", "unknown"}:
            return analysis

        analysis["primary_domain"] = "novel_literature"
        if str(analysis.get("domain_confidence") or "").strip().lower() in {"", "low"}:
            analysis["domain_confidence"] = "medium"
        analysis["target_kind"] = "work"
        if speech_act not in {"announcement", "support"}:
            analysis["speech_act"] = "announcement"
        if title_body_consistency is False or assoc:
            analysis["title_body_consistency"] = True
            analysis["is_association_not_discussion"] = False
            analysis["association_evidence"] = None
        recovery_note = "짧은 제목-주도형 연재 알림/응원 포스트로 보정"
        cur_reason = str(analysis.get("coherence_reason") or "").strip()
        if recovery_note not in cur_reason:
            analysis["coherence_reason"] = (cur_reason + " | " + recovery_note).strip(" |")
        cur_subject = str(analysis.get("real_subject") or "").strip()
        if not cur_subject:
            analysis["real_subject"] = "작품 약칭을 축으로 한 짧은 연재 알림/응원 포스트"
        return analysis

    def _infer_speech_act_target_kind(
        self,
        analysis: Dict[str, Any],
        post_json: Dict[str, Any] | None,
    ) -> Dict[str, str]:
        title = str((post_json or {}).get("title") or "").strip()
        content = " ".join(str(x or "") for x in ((post_json or {}).get("content") or []))
        merged = f"{title} {content}".strip()
        merged_nospace = re.sub(r"\s+", "", merged)
        intent = str(analysis.get("intent") or "").strip().lower()
        domain = str(analysis.get("primary_domain") or "").strip().lower()
        title_terms = [str(x or "").strip() for x in (analysis.get("title_novel_terms") or []) if str(x or "").strip()]

        if intent in {"author_talk", "author_discussion"}:
            target_kind = "author"
        elif intent == "platform_meta" or domain == "meta_platform":
            target_kind = "platform"
        elif intent == "discuss_genre":
            target_kind = "genre"
        elif title_terms:
            target_kind = "work"
        elif domain in {"memes_humor", "daily_life"}:
            target_kind = "community"
        elif domain == "novel_literature":
            target_kind = "work"
        else:
            target_kind = "unknown"

        if intent == "ask_question":
            speech_act = "question"
        elif intent == "request_recommendation":
            speech_act = "question"
        elif intent == "make_joke":
            speech_act = "banter"
        elif intent == "share_information":
            speech_act = "announcement"
        elif intent in {"author_talk", "author_discussion"}:
            speech_act = "comparison" if "같은거" in merged_nospace or "하위호환" in merged_nospace else "complaint"
        elif intent == "express_opinion":
            if re.search(r"(?:가자|가즈아|드가자|화이팅|레츠고|존버)", merged_nospace):
                speech_act = "support"
            elif re.search(r"(?:별로|노잼|보기힘들|불쌍|아쉽|좆같|개같|싫)", merged_nospace):
                speech_act = "complaint"
            else:
                speech_act = "other"
        elif intent == "discuss_work":
            speech_act = "review"
        elif intent == "debate":
            speech_act = "comparison"
        else:
            speech_act = "other"

        return {
            "speech_act": speech_act,
            "target_kind": target_kind,
        }
    
    def _build_post_json(self, post: Dict[str, Any], comments: List[str]) -> Dict[str, Any]:
        """Build simplified post JSON for analysis."""
        content_texts = []
        for block in post.get("content_blocks", []):
            if isinstance(block, dict) and block.get("text"):
                content_texts.append(block["text"])
            elif isinstance(block, str):
                content_texts.append(block)
        
        result = {
            "post_id": post.get("post_id"),
            "gallery_id": post.get("gallery_id", ""),
            "title": post.get("title", ""),
            "post_author": post.get("post_author") or post.get("author", ""),
            "author": post.get("author", ""),
            "content": content_texts,
            "comments": comments[:15],  # More comments for better context
        }
        comment_context = post.get("comment_context_lines") or []
        if comment_context:
            result["comment_context"] = comment_context[:15]
        comment_dialogue = post.get("comment_dialogue_context_lines") or []
        if comment_dialogue:
            result["comment_dialogue_context"] = comment_dialogue[:15]
        surface_notes = post.get("surface_paraphrase_notes") or []
        if surface_notes:
            result["surface_paraphrase_notes"] = surface_notes[:10]
        return result
    
    def _call_llm(
        self,
        user_prompt: str,
        *,
        post: Optional[Dict[str, Any]] = None,
        comments: Optional[List[str]] = None,
        gatekeeper_result: Optional[Dict[str, Any]] = None,
        ctx: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Call LLM and parse JSON response."""
        print(f"[{_ts()}][llm-stream] ▶ {self.name.lower()} 토큰 생성 시작...", file=sys.stderr)
        
        try:
            system_content = build_discourse_system_prompt(
                DISCOURSE_SYSTEM,
                post=post,
                comments=comments,
                gatekeeper_result=gatekeeper_result,
                ctx=ctx,
            )
            messages = [
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_prompt},
            ]
            try:
                _max_tokens = int(
                    os.getenv("LLM_EXPERT_MAX_TOKENS", os.getenv("LLM_MAX_TOKENS", "32768"))
                )
            except Exception:
                _max_tokens = 32768
            _max_tokens = max(512, min(_max_tokens, 65536))
            
            response_text = self.llm._stream_chat_http(
                messages=messages,
                tag="discourse",
                use_grammar=True,
                max_tokens=_max_tokens,
            )
            
            # Parse JSON (handle any formatting issues)
            result = parse_json_with_think_removal(response_text)
            
            return result
            
        except Exception as e:
            print(f"[{_ts()}][{self.emoji}] LLM 호출 실패: {e}", file=sys.stderr)
            raise

    def _fallback_domain_evidence(self, post_json: Dict[str, Any] | None) -> List[str]:
        """
        domain_evidence가 숫자 폭주로 망가졌을 때 title/content/comments에서
        의미 토큰을 복구한다.
        """
        if not isinstance(post_json, dict):
            return []

        stop = {
            "그리고", "근데", "그냥", "진짜", "너무", "약간", "이거", "저거",
            "에서", "으로", "이다", "있다", "없다", "같다", "했다", "한다",
            "하는", "하게", "해서", "하면", "하면은", "근데요", "입니다",
        }

        def _tokens(s: str) -> List[str]:
            out: List[str] = []
            for t in re.findall(r"[가-힣A-Za-z0-9_]{2,24}", str(s or "")):
                tt = t.strip()
                if not tt or tt.isdigit():
                    continue
                if tt in stop:
                    continue
                out.append(tt)
            return out

        ordered: List[str] = []
        for t in post_json.get("title", "").split():
            ordered.extend(_tokens(t))
        for c in post_json.get("content") or []:
            ordered.extend(_tokens(str(c)))
        for cm in (post_json.get("comments") or [])[:8]:
            ordered.extend(_tokens(str(cm)))

        dedup: List[str] = []
        seen = set()
        for tok in ordered:
            n = tok.lower()
            if n in seen:
                continue
            seen.add(n)
            dedup.append(tok)
            if len(dedup) >= 10:
                break
        return dedup

    def _sanitize_speculative_medium_claims(
        self,
        analysis: Dict[str, Any],
        post_json: Dict[str, Any] | None,
    ) -> Dict[str, Any]:
        if not isinstance(analysis, dict):
            return analysis

        cues = self._collect_post_medium_cues(post_json)
        speculative_groups = self._find_speculative_media_groups(analysis, cues)
        if not speculative_groups:
            return analysis

        text_keys = ("coherence_reason", "consistency_note", "real_subject", "reasoning")
        for key in text_keys:
            val = analysis.get(key)
            if isinstance(val, str) and val.strip():
                analysis[key] = self._neutralize_media_text(val, speculative_groups)

        suggestions = analysis.get("search_suggestions")
        if isinstance(suggestions, list):
            sanitized: List[Dict[str, Any]] = []
            for raw in suggestions[:3]:
                if not isinstance(raw, dict):
                    continue
                q = str(raw.get("query") or "").strip()
                p = str(raw.get("purpose") or "").strip()
                if q:
                    q = self._neutralize_media_text(q, speculative_groups, query_mode=True)
                if p and self._contains_media_term_group(p, speculative_groups):
                    p = "매체 미확정 상태이므로 중립 검색으로 작품/용어 정체를 확인"
                if not q:
                    continue
                item = dict(raw)
                item["query"] = q
                if p:
                    item["purpose"] = p
                sanitized.append(item)
            analysis["search_suggestions"] = sanitized

        primary_domain = str(analysis.get("primary_domain") or "").strip().lower()
        domain_conf = str(analysis.get("domain_confidence") or "").strip().lower()
        if primary_domain in {"manga_comics", "anime"} and domain_conf in {"high", "max"}:
            analysis["domain_confidence"] = "medium"
            note = "본문/댓글 매체 단서 부족으로 매체 판정을 보수적으로 조정"
            cur_note = str(analysis.get("consistency_note") or "").strip()
            analysis["consistency_note"] = f"{cur_note} | {note}".strip(" |")

        print(
            f"[{_ts()}][{self.emoji}] 🛡️ 매체 과단정 보정: speculative={sorted(speculative_groups)}",
            file=sys.stderr,
        )
        return analysis

    def _collect_post_medium_cues(self, post_json: Dict[str, Any] | None) -> Dict[str, bool]:
        if not isinstance(post_json, dict):
            return {"webtoon": False, "anime": False, "novel": False}
        parts: List[str] = [str(post_json.get("title") or "")]
        for c in post_json.get("content") or []:
            parts.append(str(c))
        for c in post_json.get("comments") or []:
            parts.append(str(c))
        blob = " ".join(parts).lower()
        return {
            "webtoon": any(t in blob for t in ("웹툰", "만화", "코믹", "comic", "webtoon", "manga", "manhwa")),
            "anime": any(t in blob for t in ("애니메이션", "애니", "anime")),
            "novel": any(t in blob for t in ("웹소설", "장르소설", "소설", "novel")),
        }

    def _find_speculative_media_groups(self, analysis: Dict[str, Any], cues: Dict[str, bool]) -> set[str]:
        text_fields = []
        for k in ("coherence_reason", "consistency_note", "real_subject", "reasoning"):
            v = analysis.get(k)
            if isinstance(v, str):
                text_fields.append(v.lower())
        for item in (analysis.get("search_suggestions") or []):
            if isinstance(item, dict):
                text_fields.append(str(item.get("query") or "").lower())
                text_fields.append(str(item.get("purpose") or "").lower())
        blob = " ".join(text_fields)
        speculative: set[str] = set()
        if not cues.get("webtoon") and any(t in blob for t in ("웹툰", "만화", "코믹", "comic", "webtoon", "manga", "manhwa")):
            speculative.add("webtoon")
        if not cues.get("anime") and any(t in blob for t in ("애니메이션", "애니", "anime")):
            speculative.add("anime")
        return speculative

    def _contains_media_term_group(self, text: str, groups: set[str]) -> bool:
        s = str(text or "").lower()
        if "webtoon" in groups and any(t in s for t in ("웹툰", "만화", "코믹", "comic", "webtoon", "manga", "manhwa")):
            return True
        if "anime" in groups and any(t in s for t in ("애니메이션", "애니", "anime")):
            return True
        return False

    def _neutralize_media_text(self, text: str, groups: set[str], query_mode: bool = False) -> str:
        out = str(text or "")
        repl = "작품" if query_mode else "작품(매체 미확정)"
        # 매체 단정 표현(직접 용어가 아닌 우회 표현 포함)을 중립화
        out = re.sub(
            r"(시각적\s*매체|visual\s*media?|graphic\s*storytelling)",
            "작품" if query_mode else "해당 작품",
            out,
            flags=re.IGNORECASE,
        )
        if "webtoon" in groups:
            out = re.sub(
                r"(웹툰|만화|코믹스?|comic|webtoon|manga|manhwa)",
                repl,
                out,
                flags=re.IGNORECASE,
            )
        if "anime" in groups:
            out = re.sub(
                r"(애니메이션|애니|anime)",
                repl,
                out,
                flags=re.IGNORECASE,
            )
        out = re.sub(r"\s{2,}", " ", out).strip()
        return out
    
    def _default_result(self, error: str) -> Dict[str, Any]:
        """Return safe default when LLM fails."""
        return {
            "discourse_analysis": {
                "primary_domain": "other",
                "domain_confidence": "low",
                "domain_evidence": [],
                "intent": "express_opinion",
                "intent_confidence": "low",
                "speech_act": "other",
                "target_kind": "unknown",
                "is_coherent": True,
                "coherence_reason": f"분석 오류: {error}",
                "is_association_not_discussion": False,
                "association_evidence": None,
                "real_subject": "분석 실패",
                "reasoning": f"오류로 인해 기본값 반환: {error}",
            }
        }
