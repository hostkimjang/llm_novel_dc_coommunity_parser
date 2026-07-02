"""
Final Arbiter - 최종 종합 판정 전문가
모든 전문가의 의견을 종합하여 최종 결론을 도출합니다.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, TYPE_CHECKING

from .utils import (
    parse_json_with_think_removal,
    build_search_aggregation_summary,
    _ts,
    _norm_domain_text,
    _detect_domain_groups,
    _has_domain_conflict_for_mapping,
    _has_curated_alias_work_discussion_cue,
    KNOWN_TITLE_ABBREVIATIONS,
)
from ..prompts.expert_prompts import LF_ARBITER, PLATFORM_ABBREVIATION_MAP
from ..prompts.prompt_router import build_arbiter_system_prompt
from ..rules import OFFICIAL_PLATFORMS, GENRE_ARCHETYPE_TERMS, PLATFORM_ABBREVIATIONS
from .decoder import abbreviation_match_score, KNOWN_ABBREVIATIONS

if TYPE_CHECKING:
    from .orchestrator import ConversationContext


# 도메인 충돌 감지 + 아는 약어: utils.py 에서 import


ARBITER_SYSTEM = """\
You are ⚖️ FINAL ARBITER, the supreme judge of web novel identification.

YOU ARE THE FINAL DECISION MAKER:
- You are called when analysis time is almost exhausted
- All other experts have provided their opinions
- You MUST make a definitive conclusion NOW
- There is no more time for additional analysis or collaboration

YOUR ROLE:
- Review ALL expert opinions and their reasoning
- Resolve conflicts between experts
- Make the FINAL determination on novel identity
- Synthesize metadata from all sources

""" + LF_ARBITER + """

=== 제안 2: 전문가 신뢰도 가중 평균 (Expert Confidence Weighting) ===

**전문가별 신뢰도 가중치:**
- Verifier: 2.0 (증거 검증 전문가, 가장 높은 가중치)
- Decoder: 1.5 (축약어 해독이 핵심)
- Gatekeeper: 1.0 (초기 필터, 기본 가중치)
- Critic: 0.5 (메타데이터 전문가, 식별에는 보조적)
- DiscourseAnalyzer: 0.8 (도메인 파악, 보조 역할)

**가중 평균 계산 원칙:**
1. 각 전문가의 confidence를 숫자로 변환:
   - high=0.95, medium=0.7, low=0.4
2. 가중치를 곱하여 합산:
   - (Verifier conf × 2.0) + (Decoder conf × 1.5) + (Gatekeeper conf × 1.0)
3. 가중치 합으로 나눔:
   - 결과 / (2.0 + 1.5 + 1.0 + ...)
4. 최종 confidence 판정:
   - 0.8 이상 → high
   - 0.5-0.8 → medium
   - 0.5 미만 → low

**의견 충돌 해결 원칙:**
- 🚨 **Verifier 거부권 (최우선)**: Verifier가 "is_relevant=false" 판단 → **무조건 final_decision.is_relevant=false**
  - Verifier confidence에 관계없이 거부권 발동
  - Decoder/Gatekeeper가 작품 식별해도 Verifier가 거부하면 최종 is_relevant=false
  - 이유: Verifier는 본문 맥락 검증 전문가 (가중치 2.0)
- Decoder + Verifier 모두 "is_relevant=true" → **거의 확정**
- Gatekeeper만 "is_relevant=true" → **추가 검증 필요** (신뢰도 낮음)

=== 제안 4: 불확실성 정량화 (Uncertainty Quantification) ===

**불확실성 요인 체크:**
프롬프트 하단에 제공된 "불확실성 요인" 리스트를 확인하세요.

**불확실성 요인이 3개 이상이면:**
1. confidence를 자동으로 'low'로 하향
2. notes에 불확실성 요인 명시
3. is_relevant=true여도 신뢰도 낮음을 표시

**일반적인 불확실성 요인:**
- "공식 플랫폼 증거 없음 (커뮤니티 포스트만)"
- "본문에 작품 직접 언급 없음 (제목만)"
- "검색 결과 모호함"
- "형태소 매칭 불일치"
- "도메인 불일치 (DiscourseAnalyzer vs Decoder)"

**불확실성 처리 예시:**
```
불확실성 요인: 3개
- Verifier: 공식 플랫폼 증거 없음
- Verifier: 본문에 직접 언급 없음
- Decoder: 검색 결과 모호

최종 판정:
- is_relevant: true (작품 식별됨)
- confidence: low (불확실성 요인 다수)
- notes: "커뮤니티 증거만 있음. 공식 플랫폼 확인 필요."
```

=== ARBITER 전용: 프레임워크 기반 최종 판정 ===

**모든 전문가의 분석을 프레임워크로 최종 검증하라:**

1. **화용론적 최종 확인 - 발화 행위 판정**
   전문가들 간 판단이 다르면, 어미와 표현에서 의도를 최종 결정:
   - 지시 표현(-좀, -줘, 추천) → recommendation
   - 명령/조언 표현(-해라, -써라) + 작가 대상 → author_criticism
   - 진술 표현 + 작품 내용 → work_discussion

2. **문법 구조 최종 확인 - 명사 역할 판정**
   Decoder가 식별한 것이 정말 작품명인가?
   - 주어 위치 + 행위 동사 → 작품명 아닐 가능성
   - 목적어/수식어 위치 → 작품명 가능성

3. **담화 일관성 최종 확인 - 주제 vs 예시**
   식별된 작품이 실제 주제인가?
   - 비교 구문 내 → 예시 → official_title = null
   - 본문이 작품 내용 직접 논의 → 주제 확인

4. **정보 확실성 최종 확인**
   - 검색에서 명시적 확인 → 확정
   - 불확정 지시("신작") → null
   - 추측 생성 → 거부

CRITICAL RULES:
- Output ONLY valid JSON. No markdown.
- DO NOT include "thinking", "reasoning_process", or analysis text inside JSON.
- If experts disagree, explain your reasoning for choosing one side.
- Your decision is FINAL - be confident but fair.
- All Korean values must be in Korean.

=== CRITICAL: is_relevant 판단 기준 (작품 식별 + 담론적 연결) ===

**is_relevant의 핵심 정의:**
is_relevant = "이 포스트가 특정 웹소설 작품에 대해 실제로 이야기하는가?"

**is_relevant=true 조건 (두 가지 모두 충족):**
1. **작품 식별**: Decoder가 특정 작품을 High/Max 신뢰도로 식별함
2. **담론적 연결**: 본문/댓글이 해당 작품과 실제로 연결됨

**담론적 연결 분석 (원칙 기반):**

핵심 질문: "제목에서 작품이 식별되었지만, 본문/댓글이 그 작품에 대해 이야기하는가?"

- **연결됨**: 본문/댓글이 작품의 캐릭터, 줄거리, 전개, 작가를 다룸
  패턴: "[캐릭터명]이 불쌍해" + "작품 내용 언급" → 작품의 캐릭터/줄거리 토론
  패턴: "가자 [X]!" + Decoder가 [X]를 작가명으로 식별 → 작가 응원
  
- **연결 안됨 (뻘글/연상글)**: 제목에만 작품명, 본문은 완전히 무관한 주제
  분석 원칙:
  * 본문이 현실 세계 영역(날씨, 음식, 일상)을 다루는가?
  * 본문에 작품 고유 정보(캐릭터명, 줄거리, 설정)가 전혀 없는가?
  * 댓글도 작품 내용을 다루지 않는가?
  * **단, Decoder가 식별한 용어가 본문/댓글에 있다면 → 작품 관련 가능성 재고려**
  * 위 조건이 모두 참이고 Decoder 식별 용어도 없으면 → is_relevant=FALSE (연상글/뻘글)

**🚨 CRITICAL: Decoder 식별 정보가 DiscourseAnalyzer보다 우선 🚨**

Decoder와 DiscourseAnalyzer의 해석이 충돌할 때:

**Decoder 식별 우선 원칙:**
- Decoder가 용어를 **작가명**으로 식별했다면 → 해당 용어는 일반명사가 아님
- Decoder가 용어를 **작품 약칭**으로 식별했다면 → 해당 용어는 일반명사가 아님
- DiscourseAnalyzer가 해당 용어를 현실 세계 영역으로 해석했더라도 → **Decoder 식별을 따르라**

**⚠️ 예외: Discourse 역방향 Override (DISCOURSE DOMAIN WARNING 활성 시)**
- DiscourseAnalyzer가 non-novel 도메인(memes_humor, daily_life 등)을 **high confidence**로 판정한 경우
- 본문/댓글에 해당 작품의 줄거리·작가명·캐릭터 이름·플랫폼 URL 등 **구체적 증거가 전혀 없으면**
- → Decoder 식별보다 **Discourse 판정을 따르라** (is_relevant=false 또는 confidence=Low)
- 이유: 커뮤니티 은어(장붕=갤러리 유저)를 소설 캐릭터로 오인한 Decoder 오류 방지

**적용 원칙:**
- DiscourseAnalyzer: domain="daily_life" (일상 영역으로 해석)
- Decoder: "용어 X"를 작가명으로 식별, "용어 Y"를 작품 약칭으로 식별
- 판단: **Decoder 식별 우선** → 작품 관련 토론으로 판단, is_relevant=TRUE

**응원/기대 패턴 인식 (언어학적 원칙):**
- "가자 [X]!" 패턴: 응원/격려 표현
- "[X] 올 때 됐다" 패턴: 기대/갈망 표현
- 이런 패턴 + Decoder가 [X]를 작가/작품으로 식별 = is_relevant=TRUE, discussion_type="anticipation"

**뻘글/연상글 판단 원칙 (담론 영역 불일치):**
- 제목: 소설 작품 영역 (작품명 언급)
- 본문: 현실 세계 영역 (날씨, 음식, 일상 질문)
- 댓글: 없거나 작품 무관
- **Decoder가 식별한 용어가 본문/댓글에 없음**
→ 담론 영역 불일치 + Decoder 식별 용어 없음 = 뻘글 (is_relevant=FALSE, discussion_type="noise")

예시 원칙:
- 제목 "[작품약칭]" + 본문 "날씨 언제풀리지" → 담론 영역 불일치 → 뻘글
- 제목 "[작품약칭]" + 본문 "[캐릭터] 불쌍해" → 담론 영역 일치 → 작품 토론
- 제목 "[작품약칭] 올 때 됐다" + 본문 "가자 [X]!" + Decoder가 [X]를 작가명으로 식별 → 작품 응원!

**discussion_type으로 토론 유형 세분화:**
is_relevant=true일 때, discussion_type으로 토론 형태를 구분:
- "review": 작품의 줄거리, 캐릭터, 전개를 분석/평가
- "spoiler": 스포일러 포함 토론
- "anticipation": 작품에 대한 기대, 응원 ("가자 [X]!", "[X] 올 때 됐다" 패턴)
- "meme": 작품 관련 밈, 드립, 구호
- "character_talk": 캐릭터에 대한 감상/토론
- "general": 기타 작품 관련 토론

**ENTITY ROLE 확정 규칙 (작가/캐릭터 오인 방지):**
- 동일 이름에 대해 작가 근거와 캐릭터 근거가 충돌하면, 캐릭터로 단정하지 말고 중립 표현("고유명사/대상") 사용
- "등장인물/대사"라고 쓰려면 검색/전문가 출력에 명시적 캐릭터 근거가 있어야 함
- Decoder가 is_author_name=true로 식별한 이름은 반증 없으면 작가/중립으로 유지

**기본적으로 adjacent_relevant를 우선 검토할 discussion_type:**
- "author_talk": 작가에 대한 토론/비평 ("[작가명]은 [장르]이나 써야됨" 패턴) → official_novel_title=null
- "recommendation": 추천 요청 ("추천좀", "뭐 읽을거" 패턴) → official_novel_title=null
- "meta": 플랫폼 메타 → official_novel_title=null
- "trope_discussion": 특정 작품 없이 장르/트로프 일반 토론 → official_novel_title=null
- "community_banter": 작품 주변 팬덤/반응/팬아트 감상처럼 주변 담론이면 adjacent_relevant 가능
- 단, "noise", "image_post", "off_topic", "genre_opinion"은 여전히 is_relevant=false를 우선한다.

🚨 **discussion_type 정합성 규칙:**
- adjacent_relevant는 주변 담론으로 보존하되, legacy is_relevant는 false가 기본값이다. 이 경우 official_novel_title은 null이 기본값이다.
- is_relevant=true + discussion_type="noise" → 불가!
- is_relevant=true + discussion_type="genre_opinion" → 불가!
- is_relevant=true + discussion_type="image_post" → 불가!
- is_relevant=true + discussion_type="off_topic" → 불가!
- 작가 비평/플랫폼 메타인데 작품 예시가 언급되면 → discussion_type은 유지하되 single official_novel_title 강제 확정은 금지

**💡 discussion_type 선택 우선순위 (is_relevant=false일 때):**
1. 본문이 type=image만 있고 텍스트 부족 → "image_post"
2. 웹소설과 완전 무관한 주제 (게임/현실/날씨/정치) → "off_topic"
3. 작가에 대한 토론/비평 → "author_talk"
4. 추천 요청 → "recommendation"
5. 플랫폼 메타 (뱃지/이모티콘/UI) → "meta"
6. 장르/트로프 구조 분석 → "trope_discussion"
7. 장르/소재 범용 의견 ("하렘은 다~", "~하는 소설 없냐") → "genre_opinion"
8. 커뮤니티 잡담/뻘글 (장붕 은어, 유저 간 대화) → "community_banter"
9. 위 어디에도 해당 안되면 → "noise"

=== CRITICAL: 장르 트로프 vs 작품 구분 (원칙 기반) ===

**장르/트로프 토론 판단 원칙:**

판단 기준: "포스트에 특정 작품을 식별할 수 있는 고유 정보가 있는가?"

1. **제목 패턴 분석:**
   - 제목이 장르명/트로프명 + 일반론 형태: "[X]는 [Y]가 맛있다", "[X]은 사실상 [Y]다"
   - 장르/트로프명 식별: 웹소설 클리셰/장르 용어 ("-물", "-판", "-난입", "-좌" 접미사)
   - 🔑 **"[한글1~5자]물" 패턴은 모두 장르/트로프 용어로 간주**: 회귀물, 빙의물, 하렘물 같은 대표적인 것뿐 아니라, 일상물, 힐링물, 좀비물, 먹방물, 집착물, 뚝배기물 등 "~물"로 끝나는 1~5글자 한글 단어는 장르 카테고리이며 소설 제목이 아님
   
2. **본문 분석:**
   - 특정 작품명, 캐릭터명, 작가명이 없음
   - 장르/트로프의 일반적 특성을 논함
   
3. **판단:**
   - 작품 고유 정보 없음 → is_relevant=FALSE, discussion_type="trope_discussion"
   - 작품 고유 정보 있음 → is_relevant=TRUE

**is_relevant=false 조건 (작품 식별 불가):**
1. official_novel_title=null (특정 작품이 식별되지 않음)
2. 식별된 것이 플랫폼명 (도메인명과 동일: novelpia, munpia 등)
3. 플랫폼 메타 토론: 이모티콘, 뱃지, UI, 이벤트
4. 추천 요청: "추천좀", "뭐 읽을거 없나" (작품 식별 없이 추천만 요청)
5. 현실 세계 주제: 의료, 뉴스, 정치, 일상
6. 작품과 무관한 장르/트로프 일반 토론

**핵심 원칙: 작품이 식별되면 relevant!**
- Decoder가 작품 식별 (High/Max) + 응원/기대 패턴 → is_relevant=TRUE, discussion_type="anticipation"
- 캐릭터 감상 패턴 + 작품 식별됨 → is_relevant=TRUE, discussion_type="character_talk"
- 작품 식별이 핵심이며, 토론 형태(밈/응원/리뷰)는 discussion_type으로 구분

=== CRITICAL: PLATFORM vs NOVEL DISTINCTION ===

**PLATFORM identification principle (언어적 원칙):**
- URL 도메인명과 동일한 이름 = 플랫폼명 (novelpia.com → 노벨피아, munpia.com → 문피아)
- "[서비스명] : [슬로건]" 형태로 검색되는 것 = 플랫폼
- 플랫폼명은 소설 제목이 될 수 없음 → official_novel_title=null

{platform_map}

판별 원리 (문장 구조):
- "[플랫폼약칭] [UI용어]가 [감탄/평가]" → 플랫폼 메타 (is_relevant=false)
- "[작품약칭] [서사요소]가 [감탄/평가]" → 작품 토론 (is_relevant=true)
핵심: **화제(topic)가 되는 명사**가 UI 요소인지 서사 요소인지 구분!

**PLATFORM META DISCUSSION = is_relevant=false:**
- 이모티콘/콘/뱃지: 플랫폼 부가 기능
- 투표/이벤트: 플랫폼 행사
- UI/버그/포인트: 플랫폼 기능

CONFLICT RESOLUTION PRIORITY:
1. **작품 식별 여부가 최우선** - Decoder가 High/Max로 식별했으면 is_relevant=true
2. Direct evidence (URL from comment) > Search evidence > Inference
3. Platform URL > Wiki > Community mention
4. Multiple experts agreeing > Single expert opinion
5. Higher confidence expert > Lower confidence expert

=== 전문가 투표 시스템 (Expert Voting System) ===

**전문가 신뢰도 가중치:**

Verifier 직관 우선 원칙:
- Verifier = 2표 (맥락 분석 전문가)
- Decoder = 1표 (검색 기반)
- Critic = 1표 (메타 분석)
- DiscourseAnalyzer = 0.5표 (보조 정보)

**충돌 해결 알고리즘:**

Case 1: Verifier vs Decoder 충돌
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Verifier: "현실 영역 토론" (어휘 클러스터 분석)
Decoder: "작품 발견" (검색 매칭)

판단 흐름:
Step 1: 본문 어휘 클러스터 재확인
→ 현실 어휘 70% 이상? (의학, 법률, 일상, 기술)
→ YES → Verifier 우선 (어휘 분석 > 검색)

Step 2: 작품 고유 정보 확인
→ 본문에 고유명사(인명/캐릭터) 있는가?
→ NO → Verifier 우선 (키워드 중첩일 뿐)

Step 3: 형태소 구조 확인
→ 제목이 장르 카테고리 패턴? (-물, -판, -난입)
→ YES → Verifier 우선 (장르 토론)

결론:
→ Verifier 2표 vs Decoder 1표
→ Verifier 승리 → is_relevant=FALSE

Case 2: Verifier "일반 명사" vs Decoder "고유명사"
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Verifier: "공/수는 역할 명칭 (일반 명사)"
Decoder: "작품의 캐릭터 (고유명사)"

판단 흐름:
Step 1: 복수형 확인
→ "공들은 죄다" = 복수형 역할 지칭
→ 특정 캐릭터가 아님
→ Verifier 우선

Step 2: 문장 구조 확인
→ "[장르트로프]은 [역할]을 [행위]하는 게 [평가]"
→ 주어가 카테고리, 목적어가 역할
→ Verifier 우선

결론: Verifier 승리 → 장르 일반론

Case 3: Verifier 초기 판단 vs Arbiter 검색 재평가
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Verifier (초기): "현실 의학 토론"
Arbiter (재평가): 검색에서 작품 발견

판단 흐름:
Step 1: Verifier 직관 재확인
→ 어휘 분석 근거가 타당한가?
→ "효과, 케바케, 부작용" = 현실 의학 어휘
→ YES → Verifier 직관 존중

Step 2: 검색 결과 재해석
→ 키워드 음절 유사성만으로 매칭했는가?
→ 본문 맥락과 불일치하는가?
→ YES → 검색 결과는 우연한 중첩

결론: Verifier 직관 우선 → is_relevant=FALSE

**투표 집계:**
→ Verifier 동의 전문가 수 × 2
→ Decoder 동의 전문가 수 × 1
→ 과반수 쪽 판정 채택
→ 동점 시 → 어휘 클러스터 분석 우선

=== 한국어 맥락 우선 원칙 (Korean Context Priority) ===

**검색보다 맥락이 우선:**

원칙: 검색에서 키워드 매칭 작품을 찾았어도,
      본문 맥락이 그 작품과 무관하면 거부한다.

검증 체크리스트:
□ 본문 어휘 영역 = 작품 세계?
  → 현실 어휘 클러스터면 거부
  
□ 본문에 고유명사 존재?
  → 역할 명칭만 있으면 거부
  
□ 형태소 구조 = 작품명 패턴?
  → 장르 카테고리 패턴이면 거부
  
□ 문장 구조 = 작품 토론?
  → 일반론 패턴이면 거부

하나라도 거부 조건 충족 시:
→ 검색 결과 무시
→ is_relevant=FALSE

**IMPORTANT: Decoder/Verifier 합의 존중**
- Decoder가 작품을 High 신뢰도로 식별하고
- Verifier가 is_relevant=true로 판단했다면
- Arbiter는 "밈/구호"라는 이유로 이를 뒤집지 말 것
- 대신 discussion_type을 "meme" 또는 "anticipation"으로 설정

YOUR JUDGMENT MUST INCLUDE:
- final_decision: The conclusive answer
- confidence_level: How certain you are (Max/High/Medium/Low/None)
- reasoning: Why you made this decision (Korean)
- dissenting_opinions: Any expert opinions you overruled and why
- metadata_synthesis: Combined metadata from all sources
"""

ARBITER_PROMPT = """\
⚖️ FINAL ARBITER - Comprehensive Review

=== POST (ID: {post_id}) ===
Title: {title}
Body: {body_preview}
Comments ({comment_count} total):
{comment_preview}

=== EXPERT CONSENSUS ===

🎭 Gatekeeper: {gk_verdict}
🔤 Decoder: {dc_verdict}
🔍 Verifier: {vf_verdict}{verifier_veto}

(메타데이터 분석 — micro_tags, sentiment, NSFW, spoiler — 은 당신이 직접 수행합니다.
 metadata_synthesis 필드에 본문/댓글 분석 기반으로 직접 작성하세요.)

=== KEY EVIDENCE ===
{key_evidence}

=== SUSPECTED TITLES (Decoder Candidates) ===
{suspected_titles}

=== CRITICAL: is_relevant 판단 흐름 ===

━━━ STEP 0: confidence 기반 즉결 판정 (HIGHEST PRIORITY) ━━━

아래 조건에 해당하면 나머지 STEP을 건너뛰고 즉시 판정:

**즉결 판정 A: Decoder confidence=None**
→ official_novel_title=null (필수!)
→ is_relevant=false
→ 이유: 작품 식별 자체가 불가능

**즉결 판정 B: Decoder confidence=Low + 본문 증거 전무**
→ 본문에 캐릭터명, 줄거리, 작가명, 회차, 플랫폼URL 중 하나도 없으면:
→ official_novel_title=null, is_relevant=false
→ 이유: 키워드 우연 일치 가능성 높음

**즉결 판정 C: Verifier grounding=false + anchor=search_only/none**
→ Verifier가 "본문에 근거 없음"을 판정한 경우:
→ official_novel_title=null, is_relevant=false
→ 이유: 검색에서만 찾은 매칭, 본문과 무관

**즉결 판정 D: 장르/트로프 일반론 감지 (DISCOURSE WARNING 또는 snippet_analyzer 경고)**
→ DISCOURSE WARNING에 "genre_discussion"이 포함되어 있으면:
→ 게시글이 장르/트로프 일반론을 다루고 있을 가능성 높음
→ 이 경우 Decoder가 작품을 매칭했더라도, 아래를 반드시 검증:
  1. 본문에 매칭된 작품의 **고유 정보**(캐릭터 고유명, 구체적 줄거리, 작가명, 회차)가 있는가?
  2. 제목의 주제어가 일반 개념/장르어인가, 특정 작품의 고유 약어인가?
  3. 본문이 복수형/일반화 표현("~하는 소설들", "~이 국룰")을 사용하는가?
→ 고유 정보 없음 + 일반 개념 + 일반화 표현 → is_relevant=false, discussion_type="genre_opinion" 또는 "trope_discussion"
→ 이유: 검색 키워드와 소설 제목의 우연한 겹침이지, 해당 소설에 대한 토론이 아님

⚠️ 위 즉결 판정에 해당하지 않을 때만 아래 STEP 1로 진행
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**STEP 1: 작품 식별 여부 확인**
- Decoder가 특정 작품을 High/Max 신뢰도로 식별했는가?
- 검색 결과에서 작품명, 작가명이 확인되었는가?
- 식별된 것이 플랫폼명이 아닌 실제 소설 작품인가?

→ 작품이 식별되었으면: STEP 1.5로 (담론적 연결 확인)
→ 작품 식별 불가: STEP 2로

**STEP 1.4: official_title 결정 (🚨 CRITICAL: Decoder 결과 사용) 🚨**

official_title은 **반드시 Decoder의 best_match에서 가져와야 함**:

1. **Decoder 결과 확인:**
   - Decoder의 decoded_terms 배열에서 best_match가 있는 항목 찾기
   - best_match.title이 있으면 → 그것을 official_title로 사용
   - **절대로** 원본 축약어(original)를 official_title로 사용하지 말 것!

2. **정식 제목 vs 축약어 판단:**
   ❌ 잘못된 예:
   - original: "[축약어]"
   - best_match.title: "[정식 제목]"
   - 사용: "[축약어]" ← **절대 안 됨!**
   
   ✅ 올바른 예:
   - original: "[축약어]"
   - best_match.title: "[정식 제목]"
   - 사용: "[정식 제목]" ← **정답!**

3. **Decoder가 축약어를 정식 제목으로 풀어냈다면:**
   - Decoder가 형태소 분석과 검색으로 정식 제목을 찾은 것
   - 그 결과를 **그대로** 사용해야 함
   - Arbiter가 임의로 축약어를 채택하면 안 됨

4. **예외 상황:**
   - best_match.title이 null이면 → official_title=null
   - Decoder가 작품을 식별하지 못했으면 → official_title=null

**적용 원칙:**
```
IF Decoder.best_match.title EXISTS:
    official_title = Decoder.best_match.title  # 정식 제목
ELSE:
    official_title = null
```

**절대 금지:**
- original을 official_title로 사용 (축약어를 정식 제목으로 착각)
- Arbiter가 임의로 제목 변경
- 검색 결과를 무시하고 축약어 채택

**STEP 1.5: 담론적 연결 확인 (뻘글/연상글 감지) 🚨 중요!**
작품이 식별되었더라도, 본문/댓글이 그 작품과 실제로 연결되는지 확인:

담론 영역 분석:
- 제목: 어떤 담론 영역? (소설 작품 영역 = 작품명/작가명 언급)
- 본문: 어떤 담론 영역? (소설 영역 vs 현실 세계 영역)
- 댓글: 어떤 담론 영역?

**담론 영역 판단의 핵심: 어휘 클러스터와 검색 증거를 통합하라**

본문의 일반 명사("가족", "죽음" 등)가 현실을 말하는지, 
소설 속 캐릭터 상황을 말하는지는 **맥락**으로 판단해야 한다:

- 서사 어휘군(막화, 전개, 캐릭터, 스포 등)이 함께 나오는가?
- 검색 결과에서 캐릭터가 확인되었는가?
- 댓글들이 작품 내용에 공감하는가?

위 신호들이 있으면 → 본문은 **소설 세계**를 다루는 것
위 신호들이 없고 일상 어휘만 있으면 → **현실 세계** 담론

**연상글/뻘글 판단:**
- 제목: 작품명 있음
- 본문: 서사 어휘 없고, 검색 증거와 무관한 일상 주제
- 댓글: 작품 무관
→ 담론 영역 불일치 = is_relevant=FALSE

**작품 토론 판단:**
- 본문/댓글이 작품의 캐릭터, 줄거리, 전개를 다룸
- 서사 어휘군이 존재하거나 검색에서 캐릭터 확인됨
- 댓글이 작품 내용에 반응함
→ 담론적 연결 = is_relevant=TRUE

→ 담론적 연결 있음: is_relevant=TRUE
→ 담론 영역 불일치 (뻘글): is_relevant=FALSE, discussion_type="noise"

**STEP 1.6: 작가 비평 vs 작품 토론 구분 (원칙 기반)**

판단 기준: "포스트의 주제가 작가인가, 작품인가?"

**작가 비평 패턴 분석:**
- 제목에 작가명/필명이 주어로 등장: "[작가명]는 [판단/추천]"
- 본문에서 작가의 커리어, 글쓰기 스타일, 작품 경향을 논함
- 특정 작품이 "예시" 또는 "비교대상"으로 언급됨: "[제목] 같은거 하나 써라", "[제목]로 커리어하이"
→ is_relevant=FALSE, discussion_type="author_talk"
→ official_novel_title=null (예시 작품은 주제가 아님)

**작품 토론 패턴 분석:**
- 제목에 작품명/약칭이 주어로 등장
- 본문에서 해당 작품의 캐릭터, 줄거리, 전개를 논함
→ is_relevant=TRUE, official_novel_title="[작품명]"

**STEP 1.7: 장르/트로프 일반 토론 구분 (원칙 기반)**

판단 기준: "특정 작품을 식별할 수 있는 고유 정보가 있는가?"

**장르/트로프 토론 패턴:**
- 제목이 장르명/트로프명 ("-물", "-판", "-난입" 접미사 패턴)
- 🔑 "[한글1~5자]물" 형태의 단어(예: 일상물, 힐링물, 좀비물, 먹방물, 집착물, 성장물, 고능이물 등)는 모두 장르 카테고리이며 소설 제목이 아님. 리스트에 없는 "X물"도 동일하게 장르 용어로 취급할 것
- 본문이 해당 장르/트로프의 일반적 특성을 논함
- 특정 작품명, 캐릭터명, 작가명이 없음
→ is_relevant=FALSE, discussion_type="trope_discussion"

**STEP 2: is_relevant=false일 때 discussion_type 세분화 (CRITICAL!)**

is_relevant=false로 판단했으면, **반드시 아래 우선순위대로 discussion_type을 세분화**:
"noise"는 마지막 수단이다. 가능한 한 구체적인 카테고리를 선택하라.

**우선순위 1 — 본문 형태 기반:**
- 본문이 type=image만 있고 텍스트 부족 → discussion_type="image_post"
  * 이미지 해독 불가로 작품 식별 불가능한 경우

**우선순위 2 — 주제 영역 기반:**
- 웹소설과 완전 무관한 주제 (게임, 현실 뉴스, 정치, 일상 날씨 등) → discussion_type="off_topic"
- 작가에 대한 토론/비평 → discussion_type="author_talk"
- 추천 요청 ("추천좀", "뭐 읽을거 없나") → discussion_type="recommendation"
- 플랫폼 메타 (뱃지, 이모티콘, UI, 이벤트) → discussion_type="meta"

**우선순위 3 — 소설 관련이지만 작품 특정 불가:**
- 장르/트로프의 구조적 분석 ("~물의 결말 패턴", "트로프 자체 토론") → discussion_type="trope_discussion"
- 장르/소재에 대한 범용 의견 ("~하는 소설 없냐", "하렘은 다~", "고능이물은~") → discussion_type="genre_opinion"
  * trope_discussion과의 차이: trope_discussion은 트로프 구조 분석, genre_opinion은 취향/의견 표현

**우선순위 4 — 커뮤니티 문화:**
- 커뮤니티 은어 사용한 잡담/뻘글 (장붕=유저, 파딱=완장, 분충=분탕충) → discussion_type="community_banter"
  * 소설과 무관한 유저 간 대화, DC 갤러리 문화 관련 글

**우선순위 5 — 정말 분류 불가:**
- 위 카테고리 어디에도 해당 안 됨 → discussion_type="noise"

다음 조건 중 하나라도 해당되면 is_relevant=FALSE:
- **추천 요청 (화용론적 이해)**:
  * 발화 행위: 글쓴이가 "정보를 요청"하는 행위
  * 제목의 어미 분석: "-좀", "-줘", "있어?", "알려줘" → 요청 의도
  * 본문에 특정 작품명이 있어도 제목이 요청 형태면 추천 요청
  * 댓글의 작품명은 "답변"이지 포스트 주제 아님
  * 예시 (가상): 제목 "[장르갑] 추천좀" + 댓글 "[작품을] 추천" 
    → 포스트는 요청, 댓글은 답변 → is_relevant=false
  * **CRITICAL**: 댓글 작품명을 official_title로 승격시키지 말 것!
- 플랫폼 메타: 이모티콘, 뱃지, UI, 이벤트 토론
- 현실 세계 주제: 의료, 뉴스, 정치, 일상
- official_novel_title=null: 특정 작품이 식별되지 않음

**STEP 3: discussion_type 결정 (is_relevant=true인 경우)**
작품이 식별되었으면, 토론 형태를 세분화:
- "review": 작품의 줄거리, 캐릭터, 전개를 분석/평가
- "spoiler": 스포일러 포함 토론
- "anticipation": 기대, 응원, 기우제 ("가자 [X]!", "[X] 올 때 됐다" 패턴)
- "meme": 작품 관련 밈, 드립, 구호 (작품 고유 용어 사용)
- "character_talk": 캐릭터 감상 ("[캐릭터명]이 불쌍해" 패턴)
- "general": 기타 작품 관련 토론

**CRITICAL EXAMPLES (원칙 기반):**

1. **응원/기대 패턴:**
   - 제목: "[약칭] 올 때 됐다" + "가자 [작가명]!" 패턴
   - Decoder가 작품 식별 (High/Max)
   → is_relevant=TRUE, discussion_type="anticipation"
  
2. **캐릭터 감상 패턴:**
   - 제목: "[작품명] [캐릭터]가 너무 [감정]" 패턴
   - 본문이 해당 캐릭터의 행동/전개를 논함
   → is_relevant=TRUE, discussion_type="character_talk"

3. **플랫폼 메타 패턴:**
   - 제목에 플랫폼 부가기능 (콘, 빔, 이모티콘)
   - 작품 식별 없음
   → is_relevant=FALSE, discussion_type="meta"

=== CRITICAL: official_novel_title 무결성 규칙 ===

**❌ 절대 금지: 게시글 제목을 official_novel_title로 사용!**
- official_novel_title은 **웹소설 플랫폼에 등록된 정식 소설 제목**만 넣어야 한다
- 게시글 제목 "[축약어] [내용]"을 그대로 official_novel_title에 복사하지 마라!
- Decoder가 title=null이면 → Arbiter도 official_novel_title=null로 유지
- Verifier가 게시글 제목을 official_novel_title로 넣어도 → Arbiter가 거부해야 함

**"[작가명] 신작 [명사]" 패턴 = 소설 제목이 아님!**
- Decoder가 is_author_name=true로 식별한 경우:
  → official_novel_title=null (작가는 식별되었지만 작품명은 불확정)
  → discussion_type="review" 또는 "general" (작품 내용을 논하므로)
  → detected_author에 작가명 기재

**"[축약어][캐릭터명]" 패턴 = 소설 제목이 아님!**
- Decoder가 축약어를 정식 제목으로 풀어냈으면 → 그 정식 제목을 사용
- 커뮤니티에서 "[축약어][캐릭터명]"으로 불리더라도 → Decoder의 정식 제목 우선

=== YOUR TASK ===
1. **FIRST**: Decoder가 작품을 식별했는가? (High/Max 신뢰도)
   - 식별되었으면 → is_relevant=TRUE, discussion_type 결정
2. **SECOND**: 식별 안 되었으면 is_relevant=false 조건 확인
3. Review each expert's analysis
4. Identify agreements and conflicts
5. Resolve conflicts using evidence hierarchy
6. Make FINAL determination

OUTPUT JSON:
{{
  "final_decision": {{
    "is_relevant": boolean,  // TRUE if specific novel is IDENTIFIED (regardless of discussion type)
    "is_novel_discussion": boolean,
    "official_novel_title": "string | null",  // 확정된 소설 제목 (하나)
    "suspected_titles": [  // 추정/의심 작품 목록 (하나 이상, Decoder 후보들)
      {{
        "title": "string",
        "confidence": "Max" | "High" | "Medium" | "Low",
        "reason": "string (Korean)"  // 왜 의심되는지
      }}
    ],
    "heretic_url": "string | null",  // 🚨 검색 결과에 실제 존재하는 URL만! 추측/날조 절대 금지! 모르면 null
    "confidence": "Max" | "High" | "Medium" | "Low" | "None",
    "discussion_type": "review" | "spoiler" | "anticipation" | "meme" | "author_talk" | "character_talk" | "general" | "meta" | "recommendation" | "noise"
    // discussion_type 설명:
    // - review: 작품 분석/평가
    // - spoiler: 스포일러 토론
    // - anticipation: 기대/응원/기우제 ("가자 X!")
    // - meme: 작품 관련 밈/드립
    // - author_talk: 작가 토론
    // - character_talk: 캐릭터 감상
    // - general: 기타 작품 토론
    // - meta: 플랫폼 메타 (is_relevant=false)
    // - recommendation: 추천 요청 (is_relevant=false)
    // - noise: 노이즈 (is_relevant=false)
  }},
  "expert_consensus": {{
    "unanimous": boolean,
    "agreeing_experts": ["string"],
    "dissenting_experts": ["string"]
  }},
  "conflict_resolution": [
    {{
      "issue": "string",
      "expert_opinions": {{"gatekeeper": "...", "decoder": "...", ...}},
      "arbiter_decision": "string",
      "reasoning": "string (Korean)"
    }}
  ],
  "metadata_synthesis": {{
    "detected_author": "string | null",
    "detected_characters": ["string"],
    "micro_tags": ["string"],
    "sentiment": "Positive" | "Neutral" | "Negative" | "Mixed",
    "is_nsfw": boolean,
    "spoiler_level": "none" | "minor" | "major"
  }},
  "final_reasoning": "string (Korean - 아래 구조를 반드시 따라 작성, 최소 200자 이상 상세하게)",
  // ★★★ final_reasoning 작성 가이드 ★★★
  // 이 필드는 최종 사용자가 "왜 이 글을 이렇게 판정했는지"를 이해하기 위해 읽는 유일한 설명이다.
  // 기계적 나열이 아니라, 논리적 서사 흐름으로 상세하게 작성하라.
  // 판정 과정을 읽는 사람이 "LLM이 어떻게 이 결론에 도달했는지" 완전히 이해할 수 있어야 한다.
  //
  // **필수 포함 요소 (이 순서로 작성, 각 항목 2-3문장 이상):**
  //
  // 1. [본문 이해] 게시글 제목/본문을 읽고 무슨 내용인지 자연어로 요약
  //    - "이 게시글은 ~에 대해 이야기하는 글이다" / "글쓴이는 ~에 대한 의견을 표현하고 있다"
  //    - 핵심 키워드들이 어떤 맥락에서 사용되었는지 구체적으로 설명
  //    - 댓글이 있다면 댓글의 맥락도 함께 설명 (예: "댓글에서 A 캐릭터에 대한 반응이 이어지고 있어...")
  //
  // 2. [핵심 키워드 해독] 제목/본문에서 추출된 핵심 키워드가 무엇이고, 각각 어떻게 해독되었는지
  //    - 약칭/은어가 있으면: "키워드 'X'는 검색 결과 ~의 약칭으로 확인되었다"
  //    - 작가명/캐릭터명이면: "'Y'는 ~의 등장인물/작가로 확인되었다"
  //    - 복수 해석 가능성: "이 키워드는 ~로도 해석될 수 있었으나, 본문 맥락상 ~이 더 적합하다"
  //
  // 3. [검색/증거 분석] 검색/전문가 분석에서 어떤 증거를 찾았고 어떻게 해석했는지
  //    - Decoder가 식별한 후보 작품과 근거
  //    - Verifier가 본문에서 찾은 작품 고유 정보 (캐릭터명, 줄거리, 작가명, 회차 등)
  //    - 검색 결과에서 어떤 출처(공식 플랫폼/나무위키/커뮤니티 글)로 확인했는지
  //    - 불충분한 근거: 검색에서 나왔지만 본문과 연결되지 않는 증거는 명시적으로 기각 이유 설명
  //
  // 4. [전문가 합의/충돌] 전문가들의 판단이 일치했는지, 충돌이 있었다면 누구의 판단을 왜 채택했는지
  //    - "모든 전문가가 ~로 합의했다" 또는
  //    - "Decoder는 ~로 판단했으나 Verifier는 ~로 판단, 본문 증거 기반으로 Decoder의 판단을 채택했다"
  //
  // 5. [판단 근거 종합] 왜 이 결론에 도달했는지 논리적 이유
  //    - 작품 매칭이면: 어떤 증거가 결정적이었는지 ("~캐릭터 이름이 본문에 직접 언급되어 확실한 증거")
  //    - 비관련이면: 왜 작품 토론이 아닌지 구체적 이유 (장르 일반론/플랫폼 메타/커뮤니티 잡담/팬 요청 등)
  //    - 엔티티 타입 정합성: detected_author(작가)와 detected_characters(캐릭터)를 혼동해 서술하지 말 것
  //
  // 6. [결론] "따라서 이 글은 ~로 판정한다" — 자신감 있는 최종 선언
  //
  // **금지:**
  // - "어휘 클러스터 분석 결과" 같은 추상적 표현
  // - evidence_chain을 그대로 복사한 것 같은 목록 나열
  // - "Verifier는 검색을 통해 해당 작품과 URL을 정확히 식별했으며" 같은 자기 인용
  // - 판정 이유 없이 결론만 쓰는 것
  // - 1-2문장으로 끝나는 짧은 요약 (최소 200자 이상 작성할 것)
  "evidence_chain": [
    {{
      "source": "string",
      "content": "string",
      "weight": "high" | "medium" | "low"
    }}
  ]
}}

RETURN ONLY THE JSON."""


class ArbiterExpert:
    """
    ⚖️ Final Arbiter - 최종 판정자
    
    역할:
    - 모든 전문가 의견 검토
    - 충돌 해결
    - 최종 결론 도출
    - 메타데이터 종합
    """
    
    def __init__(self, llm_client):
        self.llm = llm_client
        self.name = "Arbiter"
        self.emoji = "⚖️"
        # reason "다 설명 모드": evidence reason에서 축약 최소화
        self.reason_full_mode = os.getenv(
            "ARBITER_REASON_FULL_MODE",
            os.getenv("PIPELINE_REASON_FULL_MODE", os.getenv("REASON_FULL_MODE", "1")),
        ) == "1"

    @staticmethod
    def _normalize_match_text(text: Any) -> str:
        import re as _re_norm
        return _re_norm.sub(r"[^\w가-힣]", "", str(text or "")).lower()

    def _text_matches_title_strict(self, raw_text: Any, title: Any) -> bool:
        raw_norm = self._normalize_match_text(raw_text)
        title_norm = self._normalize_match_text(title)
        if not raw_norm or not title_norm:
            return False
        return title_norm in raw_norm

    def _should_block_memory_query_forced_upgrade(
        self,
        ctx: Optional["ConversationContext"],
        verifier_out: Optional[Dict[str, Any]],
        candidate_title: Optional[Any] = None,
    ) -> bool:
        """Block suspected-title rescue when a memory-query only has weak search overlap.

        This is intentionally structural: it keys off memory-query wording,
        relation-hold fields, missing direct post grounding, and missing explicit
        bridge evidence. It must not depend on a particular post id or title.
        """
        if ctx is None:
            return False
        verifier_out = verifier_out or {}
        verifier_result = verifier_out.get("verification_result") or {}
        if not isinstance(verifier_result, dict):
            verifier_result = {}

        post_data = getattr(ctx, "post_data", None) or {}
        chunks: List[str] = [
            str(post_data.get("title") or ""),
            str(post_data.get("normalized_title") or ""),
        ]
        for block in post_data.get("content_blocks") or []:
            if isinstance(block, dict):
                chunks.append(str(block.get("text") or block.get("content") or ""))
            else:
                chunks.append(str(block or ""))
        for comment in getattr(ctx, "comments", None) or []:
            if isinstance(comment, dict):
                chunks.append(str(comment.get("content") or comment.get("text") or ""))
            else:
                chunks.append(str(comment or ""))
        merged_text = " ".join(chunk for chunk in chunks if str(chunk or "").strip())
        merged_norm = merged_text.lower()

        relation = verifier_result.get("relation_judgment") or {}
        if not isinstance(relation, dict):
            relation = {}
        relation_reason = str(
            relation.get("reason")
            or verifier_result.get("relation_hold_reason")
            or verifier_result.get("reason")
            or verifier_out.get("reason")
            or ""
        )
        memory_query_context = bool(
            str(getattr(ctx, "search_budget_profile", "") or "").strip().lower() == "memory_query_lookup"
            or re.search(
                r"(무슨|어떤).{0,16}(소설|작품)|"
                r"(소설|작품).{0,16}(기억|기억이|모르|못찾|뭐였)|"
                r"(대사|문장).{0,16}(기억|기억이|뭐였|어디서|나온)|"
                r"기억.{0,8}(안남|안 남|안나|안 나|못|없)|뭐였지",
                merged_norm,
            )
            or "기억 회수" in relation_reason
        )
        title = str(candidate_title or "").strip()
        if not title:
            novel_identity = verifier_result.get("novel_identity") or {}
            if isinstance(novel_identity, dict):
                title = str(
                    novel_identity.get("official_novel_title")
                    or novel_identity.get("official_title")
                    or novel_identity.get("title")
                    or ""
                ).strip()
        if title and self._text_matches_title_strict(merged_text, title):
            return False

        grounding = verifier_result.get("grounding_check") or {}
        if not isinstance(grounding, dict):
            grounding = {}
        anchor = str(grounding.get("anchor_found") or "").strip().lower()
        if anchor in {
            "quote_source",
            "direct_quote_source",
            "official_url",
            "post_official_url",
            "character_work_link",
            "character_title_link",
            "direct_title",
        }:
            return False

        support_summary = relation.get("search_support_summary") or {}
        if not isinstance(support_summary, dict):
            support_summary = {}
        explicit_bridge_count = int(support_summary.get("explicit_alias_bridge_count") or 0)
        closed_bridge = bool(support_summary.get("closed_bridge"))
        converged_official_signal = bool(support_summary.get("converged_official_signal"))
        post_direct_grounding = bool(relation.get("post_direct_grounding"))
        promotion = str(relation.get("promotion_decision") or "").strip().lower()
        relation_type = str(relation.get("relation_type") or "").strip().lower()
        relation_target = str(relation.get("discussion_target") or "").strip().lower()
        bridge_quality = str(support_summary.get("bridge_quality") or "").strip().lower()

        counters = verifier_result.get("counter_arguments") or []
        has_downgrade_counter = any(
            isinstance(counter, dict)
            and str(counter.get("severity") or "").strip().lower() in {"critical", "major"}
            and str(counter.get("action") or "").strip().lower()
            in {"reject", "nullify_title", "downgrade_confidence"}
            for counter in counters
        )

        relation_reason_lower = relation_reason.lower()
        nonwork_relation_context = bool(
            relation_target in {
                "community_banter",
                "genre_general",
                "platform_meta",
                "mixed_or_uncertain",
                "topic",
                "off_topic",
            }
            or "community_banter" in relation_reason_lower
            or "작품에 대한 논의가 아닌" in relation_reason
            or "작품의 줄거리" in relation_reason
            or "작품 고유" in relation_reason
            or "커뮤니티 내의 농담" in relation_reason
            or "유머/밈" in relation_reason
            or "meme" in relation_reason_lower
        )
        hold_or_reject = promotion in {
            "hold",
            "reject",
            "nullify",
            "nullify_title",
            "downgrade",
            "keep_unresolved",
        }
        alias_only_nonwork_forced_upgrade = bool(
            not memory_query_context
            and hold_or_reject
            and not post_direct_grounding
            and not explicit_bridge_count
            and not closed_bridge
            and (nonwork_relation_context or has_downgrade_counter)
        )
        if alias_only_nonwork_forced_upgrade:
            return True
        if not memory_query_context:
            return False

        weak_relation = bool(
            not post_direct_grounding
            and not explicit_bridge_count
            and not closed_bridge
            and not converged_official_signal
            and (
                promotion in {"hold", "reject", "nullify", "nullify_title"}
                or has_downgrade_counter
            )
            and (
                bridge_quality in {"", "weak", "thematic_overlap_only", "supporting"}
                or relation_type in {"", "thematic_overlap_only", "work_specific_nickname", "mixed_or_uncertain"}
                or bool(
                    re.search(
                        r"(직접|명시|bridge|브릿지|브리지|검증|확정).{0,24}(부족|불충분|불가|없)",
                        relation_reason,
                    )
                )
            )
        )
        return weak_relation

    def _title_mentioned_in_post_main_context(self, ctx: "ConversationContext", title: Optional[str]) -> bool:
        if not title:
            return False
        post_data = getattr(ctx, "post_data", None) or {}
        chunks: List[str] = [str(post_data.get("title") or "")]
        for block in (post_data.get("content_blocks") or []):
            if isinstance(block, dict):
                chunks.append(str(block.get("text") or ""))
            elif isinstance(block, str):
                chunks.append(block)
        raw_text = " ".join(chunk for chunk in chunks if str(chunk or "").strip())
        return self._text_matches_title_strict(raw_text, title)

    def _ocr_catalog_structure_marker(self, text: Any) -> bool:
        raw = str(text or "")
        if not raw.strip():
            return False
        platform_terms = (
            "노벨피아",
            "문피아",
            "카카오페이지",
            "네이버시리즈",
            "시리즈",
            "조아라",
            "리디",
            "novelpia",
            "munpia",
            "kakaopage",
        )
        if any(term.lower() in raw.lower() for term in platform_terms):
            return True
        return bool(
            re.search(
                r"(조회수?|추천수?|선호작|관심수|별점|평점|회차|\d+\s*화\b|완결|연재중|연재|줄거리|시놉시스|소개글)",
                raw,
            )
        )

    def _collect_direct_image_ocr_catalog_titles(self, ctx: "ConversationContext") -> List[str]:
        """Collect vetted OCR work-surface titles without granting URL evidence."""
        post_data = getattr(ctx, "post_data", None) or {}
        if not isinstance(post_data, dict):
            return []
        titles: List[str] = []
        for item in post_data.get("image_enrichment") or []:
            if not isinstance(item, dict):
                continue
            explicit_title = str(item.get("explicit_work_title") or "").strip()
            title_norm = self._normalize_match_text(explicit_title)
            if not title_norm:
                continue
            if self._is_platform_branding_title(explicit_title):
                continue
            if bool(item.get("is_background_listing")):
                continue
            evidence_type = str(item.get("evidence_type") or "").strip().lower()
            title_role = str(item.get("title_role") or "").strip().lower()
            focus_role = str(item.get("focus_role") or "").strip().lower()
            screen_type = str(item.get("screen_type") or "").strip().lower()
            surface_type = str(item.get("surface_type") or "").strip().lower()
            if evidence_type not in {"explicit_text", "cover_title"}:
                continue
            if title_role not in {"", "work_title"}:
                continue
            if focus_role not in {"work_anchor", "supporting_text"}:
                continue
            if screen_type in {"text_surface", "platform_catalog_ui", "search_results", "ranking", "home"}:
                continue
            if surface_type in {"platform_catalog", "search_results", "ranking", "home"}:
                continue
            if item.get("promotion_eligible") is not True:
                continue
            cues_text = " ".join(
                [
                    str(item.get("ocr_text") or ""),
                    " ".join(str(cue or "") for cue in (item.get("work_cues") or [])),
                ]
            )
            if not self._ocr_catalog_structure_marker(cues_text):
                continue
            titles.append(explicit_title)
        return list(dict.fromkeys(titles))

    def _direct_image_forced_title_guard(
        self,
        ctx: "ConversationContext",
        candidate_title: Optional[str],
        decoder_out: Optional[Dict[str, Any]],
        verifier_out: Optional[Dict[str, Any]],
    ) -> str:
        """Prefer a vetted OCR work-surface title over a weak conflicting forced title.

        This is a precision guard for suspected-title forcing. It preserves the
        packet-local direct image title as title evidence, but it does not grant
        a heretic URL or external official verification.
        """
        candidate = str(candidate_title or "").strip()
        candidate_norm = self._normalize_match_text(candidate)
        if not candidate_norm:
            return ""
        direct_titles = self._collect_direct_image_ocr_catalog_titles(ctx)
        direct_norms = {
            self._normalize_match_text(title): title
            for title in direct_titles
            if self._normalize_match_text(title)
        }
        if len(direct_norms) != 1:
            return ""
        direct_norm, direct_title = next(iter(direct_norms.items()))
        if candidate_norm == direct_norm:
            return ""
        candidate_has_strong_support = bool(
            self._has_strong_title_support(ctx, candidate)
            or self._title_directly_in_post(ctx, candidate)
            or self._has_decoder_alignment_support(decoder_out or {}, candidate, min_score=0.45)
            or self._has_non_character_anchor_support(candidate, decoder_out or {}, verifier_out or {})
        )
        if candidate_has_strong_support:
            return ""
        return direct_title

    def _has_strong_work_signals(
        self,
        ctx: "ConversationContext",
        decoder_out: Optional[Dict[str, Any]],
        verifier_out: Optional[Dict[str, Any]],
    ) -> bool:
        """genre 경고를 덮을 수 있는 강한 작품 앵커가 있는지 판별."""
        strong_anchors = {"title_mention", "character_mention", "character_title_link", "plot_mention"}
        high_conf = {"high", "max", "very_high", "very high"}

        # 1) Verifier가 relevant=true + 강한 앵커
        vf_result = (verifier_out or {}).get("verification_result") or {}
        if vf_result.get("is_relevant") is True:
            grounding = vf_result.get("grounding_check") or {}
            anchor = str(grounding.get("anchor_found") or "").lower()
            if anchor in strong_anchors:
                return True

        # 2) Decoder가 high+ + 강한 앵커로 제목 식별
        for dt in (decoder_out or {}).get("decoded_terms", []) or []:
            if not isinstance(dt, dict):
                continue
            bm = dt.get("best_match") or {}
            title = str(bm.get("title") or "").strip()
            conf = str(bm.get("confidence") or "").lower().strip()
            gr = dt.get("grounding") or {}
            anchor = str(gr.get("anchor_type") or "").lower()
            if title and conf in high_conf and anchor in strong_anchors and not dt.get("is_author_name"):
                return True

        # 3) Gatekeeper가 work_discussion + 캐릭터/제목 엔티티 보유
        try:
            from .orchestrator import ExpertType
            gk_out = ctx.get_expert_output(ExpertType.GATEKEEPER) or {}
        except Exception:
            gk_out = {}
        if isinstance(gk_out, dict):
            if str(gk_out.get("post_type") or "").lower() == "work_discussion":
                clues = gk_out.get("context_clues") or {}
                ents = gk_out.get("detected_entities") or {}
                chars = [c for c in (ents.get("possible_characters") or []) if isinstance(c, str) and c.strip()]
                titles = [t for t in (ents.get("possible_titles") or []) if isinstance(t, str) and t.strip()]
                # 제목 토큰만으로는 약하므로, 캐릭터/회차/URL 등 보조 앵커가 필요
                has_strong_gk_clue = bool(
                    clues.get("has_url_in_comments")
                    or clues.get("has_episode_reference")
                    or (clues.get("episode_info") or {}).get("episode_number")
                )
                if chars or (titles and has_strong_gk_clue):
                    return True

        # 4) snippet analyzer가 작품 제목/캐릭터를 직접 식별
        llm_snippet = getattr(ctx, "llm_snippet_analysis", None) or {}
        if isinstance(llm_snippet, dict):
            sid_title = str(llm_snippet.get("identified_title") or "").strip()
            sid_cat = str(llm_snippet.get("identified_category") or "").lower().strip()
            sid_intent = str(llm_snippet.get("post_intent") or "").lower().strip()
            rel_chars = llm_snippet.get("relevant_characters") or []
            if sid_title and sid_cat in {"web_novel", "novel"}:
                return True
            if sid_title and sid_intent == "work_discussion":
                return True
            if isinstance(rel_chars, list) and len([c for c in rel_chars if isinstance(c, str) and c.strip()]) >= 2:
                return True

        return False

    def _is_effective_genre_warning(
        self,
        ctx: "ConversationContext",
        decoder_out: Optional[Dict[str, Any]],
        verifier_out: Optional[Dict[str, Any]],
    ) -> bool:
        """genre/discuss_genre 경고를 최종 판정에 강하게 반영할지 결정."""
        warning = str(getattr(ctx, "discourse_warning", "") or "").strip().lower()
        if not warning:
            return False
        is_genre_warn = ("genre_discussion" in warning) or ("discuss_genre" in warning)
        if not is_genre_warn:
            return False

        # snippet 단독 경고는 강한 작품 앵커가 있으면 soft 처리
        if "snippet_analyzer" in warning and self._has_strong_work_signals(ctx, decoder_out, verifier_out):
            return False
        return True

    def _confidence_to_unit(self, value: Any) -> float:
        """confidence 문자열/숫자를 0~1 구간 점수로 정규화."""
        if isinstance(value, (int, float)):
            try:
                v = float(value)
            except Exception:
                return 0.0
            if v > 1.0:
                v = v / 100.0 if v <= 100 else 1.0
            return max(0.0, min(1.0, v))
        if isinstance(value, str):
            s = value.strip().lower()
            mapping = {
                "max": 1.0,
                "high": 0.9,
                "medium": 0.65,
                "low": 0.35,
                "none": 0.0,
            }
            if s in mapping:
                return mapping[s]
            try:
                return max(0.0, min(1.0, float(s)))
            except Exception:
                return 0.0
        return 0.0

    def _suspected_title_sort_key(self, item: Dict[str, Any]) -> tuple[float, str]:
        """suspected_titles 정렬용 confidence 키를 숫자로 정규화."""
        return (
            self._confidence_to_unit((item or {}).get("confidence", 0)),
            str((item or {}).get("title") or ""),
        )

    def _build_hypothesis_scores(
        self,
        *,
        ctx: "ConversationContext",
        gatekeeper_out: Dict[str, Any],
        decoder_out: Dict[str, Any],
        verifier_out: Dict[str, Any],
        discourse_out: Dict[str, Any],
        synthesizer_out: Dict[str, Any],
        decision: Dict[str, Any],
    ) -> Dict[str, Any]:
        """전문가 출력들을 합쳐 담론 가설 점수를 계산한다."""
        scores: Dict[str, float] = {
            "single_work": 0.0,
            "genre_discussion": 0.0,
            "recommendation": 0.0,
            "author_talk": 0.0,
            "noise": 0.0,
        }
        reasons: Dict[str, List[str]] = {k: [] for k in scores.keys()}

        def add(label: str, delta: float, reason: str) -> None:
            if label not in scores or delta <= 0:
                return
            scores[label] += float(delta)
            if reason:
                reasons[label].append(reason)

        # Gatekeeper 신호
        gk_conf = self._confidence_to_unit((gatekeeper_out or {}).get("confidence"))
        gk_post_type = str((gatekeeper_out or {}).get("post_type") or "").lower().strip()
        gk_clues = (gatekeeper_out or {}).get("context_clues") or {}
        if gk_post_type in {"work_discussion", "work_reference", "specific_work"}:
            add("single_work", 0.08 + 0.14 * gk_conf, f"gatekeeper.post_type={gk_post_type}")
        elif gk_post_type in {"recommendation", "request"}:
            add("recommendation", 0.10 + 0.16 * max(gk_conf, 0.5), f"gatekeeper.post_type={gk_post_type}")
        elif "author" in gk_post_type:
            add("author_talk", 0.10 + 0.14 * max(gk_conf, 0.5), f"gatekeeper.post_type={gk_post_type}")
        elif gk_post_type in {"noise", "community_banter"}:
            add("noise", 0.10 + 0.14 * max(gk_conf, 0.5), f"gatekeeper.post_type={gk_post_type}")

        if bool(gk_clues.get("is_asking_recommendation")):
            add("recommendation", 0.22, "gatekeeper.context_clues.is_asking_recommendation=true")
        if bool((gatekeeper_out or {}).get("is_noise")):
            add("noise", 0.22, "gatekeeper.is_noise=true")

        # Discourse 신호
        disc = (discourse_out or {}).get("discourse_analysis") or {}
        d_conf = self._confidence_to_unit(disc.get("intent_confidence")) or self._confidence_to_unit(disc.get("domain_confidence"))
        d_intent = str(disc.get("intent") or "").lower().strip()
        d_domain = str(disc.get("primary_domain") or "").lower().strip()
        if d_intent in {"discuss_work", "review", "spoiler", "character_talk"}:
            add("single_work", 0.10 + 0.14 * max(d_conf, 0.4), f"discourse.intent={d_intent}")
        if d_intent in {"recommendation", "request_recommendation"}:
            add("recommendation", 0.18 + 0.08 * max(d_conf, 0.4), f"discourse.intent={d_intent}")
        if d_intent in {"genre_discussion", "discuss_genre", "general_opinion", "trope_discussion"}:
            add("genre_discussion", 0.18 + 0.10 * max(d_conf, 0.4), f"discourse.intent={d_intent}")
        if d_intent in {"author_talk", "author_discussion", "author_criticism"}:
            add("author_talk", 0.18 + 0.10 * max(d_conf, 0.4), f"discourse.intent={d_intent}")
        if bool(disc.get("is_association_not_discussion")):
            add("genre_discussion", 0.16, "discourse.is_association_not_discussion=true")
            add("noise", 0.08, "discourse.association_penalty")

        if d_domain and d_domain not in {"novel_literature", "web_novel", "novel"}:
            add("noise", 0.08 + 0.08 * max(d_conf, 0.3), f"discourse.primary_domain={d_domain}")

        # Decoder 신호
        dc_conf = self._confidence_to_unit((decoder_out or {}).get("overall_confidence"))
        dc_overall = (decoder_out or {}).get("overall_best_match") or {}
        dc_title = str((dc_overall or {}).get("title") or "").strip()
        dc_title_conf = self._confidence_to_unit((dc_overall or {}).get("confidence"))
        decoded_terms = (decoder_out or {}).get("decoded_terms") or []
        dc_has_author_only = False
        if decoded_terms:
            author_like = 0
            title_like = 0
            for term in decoded_terms:
                if not isinstance(term, dict):
                    continue
                if term.get("is_author_name"):
                    author_like += 1
                bm = term.get("best_match") or {}
                if isinstance(bm, dict) and bm.get("title"):
                    title_like += 1
            dc_has_author_only = author_like > 0 and title_like == 0

        if dc_title:
            add("single_work", 0.08 + 0.14 * max(dc_title_conf, dc_conf), "decoder.overall_best_match.title")
        elif dc_conf <= 0.35:
            add("noise", 0.10, "decoder.overall_confidence=low/none")
        if dc_has_author_only:
            add("author_talk", 0.16, "decoder: author_only_signal")

        unresolved_terms = (decoder_out or {}).get("unresolved_terms") or []
        if unresolved_terms and not dc_title:
            add("genre_discussion", 0.08, "decoder.unresolved_terms")
            add("noise", 0.06, "decoder.unresolved_terms_without_title")

        # Verifier 신호
        vf = (verifier_out or {}).get("verification_result") or {}
        vf_relevant = vf.get("is_relevant")
        if vf_relevant is True:
            add("single_work", 0.36, "verifier.is_relevant=true")
        elif vf_relevant is False:
            add("noise", 0.32, "verifier.is_relevant=false")

        vf_ground = vf.get("grounding_check") or {}
        vf_anchor = str(vf_ground.get("anchor_found") or "").lower().strip()
        strong_anchors = {"plot_mention", "character_mention", "character_title_link", "title_mention"}
        if vf_anchor in strong_anchors:
            add("single_work", 0.18, f"verifier.anchor={vf_anchor}")
        elif vf_anchor in {"none", "search_only"}:
            add("noise", 0.12, f"verifier.anchor={vf_anchor}")

        vf_author_info = vf.get("author_info") or {}
        if bool(vf_author_info.get("is_author_criticism")):
            add("author_talk", 0.30, "verifier.author_info.is_author_criticism=true")

        vf_inference = vf.get("inference") or {}
        vf_infer_type = str(vf_inference.get("type") or "").lower().strip()
        if any(t in vf_infer_type for t in ("genre", "trope", "general_opinion")):
            add("genre_discussion", 0.18, f"verifier.inference.type={vf_infer_type}")
        if "recommend" in vf_infer_type:
            add("recommendation", 0.18, f"verifier.inference.type={vf_infer_type}")
        if "author" in vf_infer_type:
            add("author_talk", 0.16, f"verifier.inference.type={vf_infer_type}")

        vf_identity = vf.get("novel_identity") or {}
        vf_identity_conf = self._confidence_to_unit(
            vf_identity.get("confidence") or (verifier_out or {}).get("final_confidence")
        )
        if vf_identity.get("official_novel_title") and vf_relevant is True:
            add("single_work", 0.06 + 0.10 * vf_identity_conf, "verifier.novel_identity.title")

        # Synthesizer 신호
        sy_ca = (synthesizer_out or {}).get("confidence_assessment") or {}
        sy_is_work = sy_ca.get("is_about_identified_work")
        sy_conf = self._confidence_to_unit(sy_ca.get("confidence"))
        vf_relation = vf.get("relation_judgment") or {}
        vf_relation_type = str(vf_relation.get("relation_type") or "").lower().strip()
        vf_relation_target = str(vf_relation.get("discussion_target") or "").lower().strip()
        vf_relation_promotion = str(vf_relation.get("promotion_decision") or "").lower().strip()
        vf_relation_support = vf_relation.get("search_support_summary") or {}
        vf_explicit_alias_bridge = int(vf_relation_support.get("explicit_alias_bridge_count") or 0)
        vf_community_alias_support = int(vf_relation_support.get("community_alias_support_count") or 0)
        vf_hold_without_bridge = bool(
            vf_relevant is True
            and not vf_identity.get("official_novel_title")
            and vf_relation_type in {"explicit_alias", "work_specific_nickname"}
            and vf_relation_target == "specific_work"
            and vf_relation_promotion == "hold"
            and vf_explicit_alias_bridge <= 0
            and vf_community_alias_support <= 0
            and not getattr(ctx, "verified_character_work_links", [])
        )
        if sy_is_work is True:
            if vf_hold_without_bridge:
                add("noise", 0.06, "synthesizer.deferred_to_verifier_hold")
            else:
                add("single_work", 0.08 + 0.12 * max(sy_conf, 0.4), "synthesizer.is_about_identified_work=true")
        elif sy_is_work is False:
            add("genre_discussion", 0.10 + 0.08 * max(0.3, 1.0 - sy_conf), "synthesizer.is_about_identified_work=false")
            add("noise", 0.06, "synthesizer.non_work_bias")

        # Snippet analyzer 신호
        lsa = getattr(ctx, "llm_snippet_analysis", None) or {}
        lsa_intent = str(lsa.get("post_intent") or "").lower().strip()
        lsa_title = str(lsa.get("identified_title") or "").strip()
        if lsa_intent in {"genre_discussion", "trope_discussion", "general_opinion"}:
            add("genre_discussion", 0.16, f"snippet.post_intent={lsa_intent}")
        if lsa_intent in {"work_discussion", "discuss_work"} and lsa_title:
            add("single_work", 0.14, "snippet.work_discussion+title")
        if lsa_intent in {"recommendation", "request_recommendation"}:
            add("recommendation", 0.16, f"snippet.post_intent={lsa_intent}")

        # 최종 제목 증거 품질
        final_title = str(
            decision.get("official_title")
            or decision.get("official_novel_title")
            or ""
        ).strip()
        title_support_ok = False
        bucket = {}
        post_cnt = 0
        official_cnt = 0
        search_cnt = 0
        if final_title:
            if hasattr(ctx, "get_candidate_evidence"):
                try:
                    bucket = ctx.get_candidate_evidence(final_title) or {}
                except Exception:
                    bucket = {}
            post_cnt = len((bucket or {}).get("post_spans", []))
            official_cnt = len((bucket or {}).get("official_urls", []))
            search_cnt = len((bucket or {}).get("search_snippets", []))
            title_support_ok = bool(
                self._has_strong_title_support(ctx, final_title)
                or (vf_anchor in strong_anchors and post_cnt > 0)
            )
            if title_support_ok:
                add("single_work", 0.16, "final_title.strong_support")
            else:
                add("noise", 0.12, "final_title.weak_support")
                if post_cnt == 0:
                    add("genre_discussion", 0.06, "final_title.no_post_anchor")
            if official_cnt > 0:
                add("single_work", 0.12, "final_title.official_url")
            elif post_cnt == 0 and search_cnt > 0:
                add("noise", 0.10, "final_title.search_only")

        ordered = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        top_label, top_score = ordered[0]
        second_score = ordered[1][1] if len(ordered) > 1 else 0.0
        return {
            "scores": scores,
            "reasons": reasons,
            "top_label": top_label,
            "top_score": top_score,
            "second_score": second_score,
            "margin": top_score - second_score,
            "final_title": final_title,
            "title_support_ok": title_support_ok,
            "title_evidence_counts": {
                "post_spans": post_cnt,
                "official_urls": official_cnt,
                "search_snippets": search_cnt,
            },
        }

    def _apply_hypothesis_guard(
        self,
        *,
        ctx: "ConversationContext",
        decision: Dict[str, Any],
        gatekeeper_out: Dict[str, Any],
        decoder_out: Dict[str, Any],
        verifier_out: Dict[str, Any],
        discourse_out: Dict[str, Any],
        synthesizer_out: Dict[str, Any],
    ) -> Dict[str, Any]:
        """최종 결정 직전에 가설 점수 기반 정합성 보정."""
        board = self._build_hypothesis_scores(
            ctx=ctx,
            gatekeeper_out=gatekeeper_out,
            decoder_out=decoder_out,
            verifier_out=verifier_out,
            discourse_out=discourse_out,
            synthesizer_out=synthesizer_out,
            decision=decision,
        )
        scores = board["scores"]
        top = board["top_label"]
        margin = float(board["margin"])
        single_score = float(scores.get("single_work", 0.0))
        title_support_ok = bool(board.get("title_support_ok"))

        # 로그: 상위 3개 가설만 출력
        top3 = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:3]
        top3_text = ", ".join(f"{k}={v:.2f}" for k, v in top3)
        print(
            f"[{_ts()}][{self.emoji}] 🧠 가설보드: {top3_text}, "
            f"margin={margin:.2f}, title_support_ok={title_support_ok}",
            file=sys.stderr,
        )

        # 1) relevant=true인데 non-work 가설 우세면 강제 다운시프트
        if decision.get("is_relevant") is True:
            non_work_map = {
                "genre_discussion": "genre_opinion",
                "recommendation": "recommendation",
                "author_talk": "author_talk",
                "noise": "noise",
            }
            # 🆕 FIX: Verifier 거부권 면제 시 hypothesis_guard 하향 차단
            # (검증된 약칭+작가 조합이면 Verifier의 잘못된 noise 신호를 무시해야 함)
            _veto_exempt_active = bool(decision.get("_verifier_veto_exempt"))
            if _veto_exempt_active and top in non_work_map and title_support_ok:
                print(
                    f"[{_ts()}][{self.emoji}] 🛡️ hypothesis_guard 하향 차단: "
                    f"_verifier_veto_exempt=True + title_support_ok "
                    f"(top={top}, margin={margin:.2f})",
                    file=sys.stderr,
                )
                return board

            if top in non_work_map and margin >= 0.18 and single_score <= 0.78:
                decision["is_relevant"] = False
                decision["is_novel_discussion"] = False
                decision["official_title"] = None
                decision["official_novel_title"] = None
                decision["heretic_url"] = None
                decision["confidence"] = "Low"
                decision["discussion_type"] = non_work_map[top]
                _msg = (
                    f"[hypothesis_guard] top={top} margin={margin:.2f} "
                    f"single_work={single_score:.2f} → non-work로 하향."
                )
                _old_notes = str(decision.get("notes") or "").strip()
                decision["notes"] = f"{_msg} {_old_notes}".strip()
                decision["final_reasoning"] = (
                    f"가설 보드에서 '{top}' 담론이 단일 작품 토론보다 우세하게 나타남 "
                    f"(margin={margin:.2f}). 단일 작품 증거 강도가 충분하지 않아 "
                    f"비관련으로 최종 보정."
                )
                if decision.get("reason"):
                    decision["reason"] = decision["final_reasoning"]
                print(
                    f"[{_ts()}][{self.emoji}] 🛡️ hypothesis_guard 하향: "
                    f"relevant=true → false ({top})",
                    file=sys.stderr,
                )
                return board

            # 2) single_work가 우세해도 제목 증거 품질이 약하면 보수적으로 차단
            if (
                top == "single_work"
                and margin < 0.12
                and not title_support_ok
                and board.get("final_title")
            ):
                decision["is_relevant"] = False
                decision["is_novel_discussion"] = False
                decision["official_title"] = None
                decision["official_novel_title"] = None
                decision["heretic_url"] = None
                decision["confidence"] = "Low"
                if decision.get("discussion_type") in {
                    "general", "review", "spoiler", "anticipation",
                    "meme", "character_talk", "general_discussion",
                }:
                    decision["discussion_type"] = "noise"
                decision["final_reasoning"] = (
                    "단일 작품 가설이 근소 우세였지만 제목 증거(본문/공식 출처) 강도가 약해 "
                    "작품 확정 판정을 보류하고 비관련으로 보정."
                )
                if decision.get("reason"):
                    decision["reason"] = decision["final_reasoning"]
                print(
                    f"[{_ts()}][{self.emoji}] 🛡️ hypothesis_guard 보수 차단: "
                    f"single_work margin={margin:.2f}, weak_title_support",
                    file=sys.stderr,
                )
                return board

        # 3) 이미 비관련인데 discussion_type이 noise로만 떨어진 경우, 우세 가설로 보강
        if decision.get("is_relevant") is False and decision.get("discussion_type") == "noise":
            type_map = {
                "genre_discussion": "genre_opinion",
                "recommendation": "recommendation",
                "author_talk": "author_talk",
            }
            if top in type_map and margin >= 0.20:
                decision["discussion_type"] = type_map[top]
                print(
                    f"[{_ts()}][{self.emoji}] ℹ️ hypothesis_guard 유형 보강: "
                    f"noise → {type_map[top]} (top={top}, margin={margin:.2f})",
                    file=sys.stderr,
                )

        return board
    
    def analyze(self, ctx: "ConversationContext") -> Dict[str, Any]:
        """
        모든 전문가 의견을 종합하여 최종 판정
        
        Args:
            ctx: ConversationContext with all expert outputs
            
        Returns:
            Final arbiter decision
        """
        start_time = time.time()
        
        print(f"[{_ts()}][{self.emoji}] {self.name} 최종 판정 시작: post_id={ctx.post_id}", file=sys.stderr)
        
        # 전문가 출력 수집 및 요약 (토큰 다이어트)
        from .orchestrator import ExpertType
        
        gatekeeper_out = ctx.get_expert_output(ExpertType.GATEKEEPER) or {}
        decoder_out = ctx.get_expert_output(ExpertType.DECODER) or {}
        verifier_out = ctx.get_expert_output(ExpertType.VERIFIER) or {}
        vf_result = verifier_out.get("verification_result") or {}
        critic_out = ctx.get_expert_output(ExpertType.CRITIC) or {}
        discourse_out = ctx.get_expert_output(ExpertType.DISCOURSE) or {}
        synthesizer_out = ctx.get_expert_output(ExpertType.SYNTHESIZER) or {}

        # Fallback 정의: Verifier 거부권 분기를 타지 않아도 title 정제 함수가 항상 존재하도록 보장.
        def _clean_assignable_title(_candidate_title: str, require_hard_support: bool = False) -> str:
            _raw_title = str(_candidate_title or "").strip()
            if not _raw_title:
                return ""
            _clean_title = str(self._sanitize_site_noise_title(_raw_title) or "").strip()
            if not _clean_title:
                return ""
            if self._is_platform_branding_title(_clean_title):
                return ""
            _suspicious_tokens = ("=", "갤러리", "채널", "포텐", "독후감")
            if require_hard_support and any(tok in _clean_title for tok in _suspicious_tokens):
                return ""
            return _clean_title
        
        # 각 전문가 결과 요약 (토큰 절약)
        gk_summary = self._summarize_gatekeeper(gatekeeper_out)
        dc_summary = self._summarize_decoder(decoder_out)
        vf_summary = self._summarize_verifier(verifier_out)
        # [Phase28] Critic→Arbiter 통합: Critic LLM 호출 제거, 코드레벨 처리만 유지
        cr_summary = self._summarize_critic(critic_out)  # critic_out이 비어도 안전
        
        # [Phase28] Critic의 _adjust_suspected_titles 로직을 Arbiter에서 코드레벨로 실행
        # (별도 LLM 호출 없이, confidence < 0.2 필터 + critic_reviewed 플래그)
        if hasattr(ctx, 'suspected_titles') and ctx.suspected_titles:
            _adjusted = []
            for _st in ctx.suspected_titles:
                if not isinstance(_st, dict):
                    continue
                # verified 상태는 무조건 유지
                if _st.get("status") == "verified":
                    _adjusted.append(_st)
                    continue
                # 신뢰도 너무 낮으면 제거
                if self._confidence_to_unit(_st.get("confidence", 0)) < 0.2:
                    continue
                _st["critic_reviewed"] = True
                _adjusted.append(_st)
            ctx.suspected_titles = _adjusted[:5]
            print(f"[{_ts()}][{self.emoji}] [Phase28] suspected_titles 코드레벨 정리: {len(ctx.suspected_titles)}건", file=sys.stderr)
        
        # post_data None 체크
        post_data = ctx.post_data or {}
        
        # Ultra-compact 프롬프트 구성
        content_blocks = post_data.get("content_blocks", [])
        # content_blocks가 문자열 리스트인지 확인하고 안전하게 변환
        # 🆕 BUG-3: 블록 수를 2 → 8로 확장하여 본문 전체 맥락 파악 개선
        total_text_len = 0  # 전체 텍스트 길이 추적
        if content_blocks:
            safe_blocks = []
            for block in content_blocks[:8]:
                if isinstance(block, str):
                    safe_blocks.append(block)
                    total_text_len += len(block.strip())
                elif isinstance(block, dict):
                    # dict일 경우 'text' 또는 'content' 키 추출 시도
                    block_text = str(block.get('text') or block.get('content') or block)
                    safe_blocks.append(block_text)
                    if block.get('text'):
                        total_text_len += len(str(block['text']).strip())
                else:
                    safe_blocks.append(str(block))
            body_preview = " / ".join(safe_blocks) if safe_blocks else "(empty)"
            # 나머지 블록의 텍스트 길이도 계산 (preview에는 포함 안 하지만 길이는 추적)
            for block in content_blocks[8:]:
                if isinstance(block, str):
                    total_text_len += len(block.strip())
                elif isinstance(block, dict) and block.get('text'):
                    total_text_len += len(str(block['text']).strip())
        else:
            body_preview = "(empty)"
            total_text_len = 0
        
        # 🆕 BUG-3: body_preview 길이 400 → 800으로 확장 (본문 내용 상세 이해)
        if len(body_preview) > 800:
            body_preview = body_preview[:800] + "..."
        
        # 🆕 BUG-3: 텍스트 존재 여부 플래그 — image_post 환각 방지
        has_text_content = total_text_len >= 30
        if has_text_content:
            body_preview += f"\n[TEXT_CONTENT: {total_text_len}자 텍스트 존재 — 이미지 전용 포스트 아님]"
        
        comments = ctx.comments or []
        
        # \ub313\uae00 \ud14d\uc2a4\ud2b8 \uc0c1\uc704 N\uac1c \ucd94\ucd9c (Arbiter\uc5d0\uac8c \ub313\uae00 \ub0b4\uc6a9 \uc804\ub2ec)
        _max_comment_preview = 7
        _comment_texts = []
        for c in comments[:_max_comment_preview]:
            if isinstance(c, str) and c.strip():
                _ct = c.strip()
                if len(_ct) > 80:
                    _ct = _ct[:80] + "..."
                _comment_texts.append(_ct)
            elif isinstance(c, dict):
                _ct = str(c.get('text') or c.get('content') or '').strip()
                if _ct:
                    if len(_ct) > 80:
                        _ct = _ct[:80] + "..."
                    _comment_texts.append(_ct)
        _comment_preview = "\n".join(f"  - {ct}" for ct in _comment_texts) if _comment_texts else "(\ub313\uae00 \uc5c6\uc74c)"
        _comment_context_lines = [
            str(line)
            for line in ((post_data or {}).get("comment_context_lines") or [])[:_max_comment_preview]
            if str(line).strip()
        ]
        _comment_dialogue_lines = [
            str(line)
            for line in ((post_data or {}).get("comment_dialogue_context_lines") or [])[:_max_comment_preview]
            if str(line).strip()
        ]
        
        # Expert verdict 요약 (안전한 문자열 변환)
        gk_verdict = f"noise={gk_summary.get('is_noise')}, type={gk_summary.get('post_type')}, conf={gk_summary.get('confidence')}"
        
        # dc_verdict: decoded_terms에서 안전하게 title 추출
        dc_title = None
        if dc_summary.get('decoded_terms'):
            first_term = dc_summary['decoded_terms'][0]
            if isinstance(first_term, dict):
                dc_title = first_term.get('title')
                if isinstance(dc_title, dict):
                    dc_title = dc_title.get('title') or str(dc_title)
        dc_verdict = f"title={dc_title}, conf={dc_summary.get('overall_confidence')}"
        
        vf_verdict = f"relevant={vf_summary.get('is_relevant')}, title={vf_summary.get('official_novel_title')}, conf={vf_summary.get('confidence')}"
        
        # Verifier author_info 전달 (작가비평 판단 정보)
        vf_author_info = vf_summary.get('author_info') or {}
        if vf_author_info.get('is_author_criticism'):
            vf_verdict += f", is_author_criticism=true, detected_author={vf_author_info.get('detected_author', 'unknown')}"
        
        # Verifier 거부권 상태 확인
        verifier_veto = ""
        if vf_summary.get('is_relevant') == False:
            verifier_veto = " 🚨 [VETO: 거부권 발동! 최종 is_relevant=false 필수]"
        
        # [Phase28] cr_verdict 제거 — Critic LLM 호출 폐지, 메타데이터는 Arbiter가 직접 생성
        
        # Key evidence 추출 (안전한 문자열 변환)
        key_evidence_items = []
        if gk_summary.get('key_terms'):
            terms_list = gk_summary['key_terms'][:3]
            # 안전한 문자열 변환
            terms_str = ', '.join([str(t) for t in terms_list if t])
            if terms_str:
                key_evidence_items.append(f"Terms: {terms_str}")
        
        if dc_summary.get('decoded_terms'):
            for term in dc_summary['decoded_terms'][:2]:
                # term이 dict인지 확인
                if not term or not isinstance(term, dict):
                    continue
                # 안전한 값 추출 및 문자열 변환
                original = str(term.get('original', '')) if term.get('original') else ''
                title_val = term.get('title')
                title = str(title_val) if title_val else 'Unknown'
                conf_val = term.get('confidence')
                conf = str(conf_val) if conf_val else 'None'
                
                key_evidence_items.append(f"{original} → {title} ({conf})")
        
        if vf_summary.get('grounding_check', {}).get('anchor_found'):
            key_evidence_items.append("Anchor: Found")
        
        # 최종 join (모든 항목이 str임을 보장)
        key_evidence = "\n".join([str(item) for item in key_evidence_items]) if key_evidence_items else "None"
        
        # Suspected titles 추출 (원본 Decoder 출력에서 candidates 가져오기)
        # 작품명만 필터링 (캐릭터명 제외)
        suspected_titles = []
        if decoder_out:
            decoded_terms = decoder_out.get('decoded_terms', [])
            for term in decoded_terms[:3]:
                if not term:
                    continue
                
                # 캐릭터명이나 작가명 제외 (작품명만 포함)
                is_author = term.get('is_author_name', False)
                best_match = term.get('best_match') or {}
                
                # best_match의 title이 없으면 스킵 (캐릭터로 추정)
                if not best_match.get('title'):
                    continue
                if is_author:
                    continue
                
                # 원본 candidates 접근 (요약본이 아님!)
                candidates = term.get('candidates', [])
                if not isinstance(candidates, list):
                    continue
                
                for cand in candidates[:2]:  # 각 용어당 상위 2개 후보
                    if not cand or not isinstance(cand, dict):
                        continue
                    
                    novel_title = cand.get('official_novel_title')
                    if not novel_title:
                        continue
                    
                    # 작품명 추가
                    suspected_titles.append({
                        "title": novel_title,
                        "confidence": cand.get('morphological_score', 0.5),
                        "source_term": term.get('original', 'Unknown')
                    })
        # 중복 제거
        seen_titles = set()
        unique_suspected = []
        for st in suspected_titles:
            if st['title'] not in seen_titles:
                seen_titles.add(st['title'])
                unique_suspected.append(st)
        
        # suspected_titles_str 생성 (안전한 포맷팅)
        suspected_items = []
        for st in unique_suspected[:3]:
            title = str(st.get('title', 'Unknown'))
            conf = st.get('confidence', 0.5)
            # confidence가 숫자가 아닐 경우 안전하게 처리
            try:
                conf_str = f"{float(conf):.2f}"
            except (ValueError, TypeError):
                conf_str = str(conf)
            source = str(st.get('source_term', 'Unknown'))
            status = st.get('status', 'suspected')
            suspected_items.append(f"- {title} (conf={conf_str}, status={status}, from '{source}')")
        suspected_titles_str = "\n".join(suspected_items) if suspected_items else "None"
        
        # ⭐ 기존 suspected_titles와 병합 (Decoder→Verifier→Critic이 이미 업데이트함)
        existing = getattr(ctx, 'suspected_titles', []) or []
        
        # 기존 것 우선, 새로운 것 추가 (중복 제거)
        merged = []
        seen_titles = set()
        
        # 기존 것 먼저 (Verifier가 verified로 업데이트한 것 포함)
        for st in existing:
            if st.get('title') and st['title'] not in seen_titles:
                seen_titles.add(st['title'])
                merged.append(st)
        
        # Arbiter가 새로 발견한 것 추가
        for st in unique_suspected:
            if st.get('title') and st['title'] not in seen_titles:
                seen_titles.add(st['title'])
                st['source_expert'] = 'arbiter'
                merged.append(st)
        
        ctx.suspected_titles = sorted(merged, key=self._suspected_title_sort_key, reverse=True)[:5]
        print(f"[{_ts()}][{self.emoji}] 📋 suspected_titles 최종 병합: {len(ctx.suspected_titles)}건", file=sys.stderr)
        
        # suspected_titles 내용 출력
        if ctx.suspected_titles:
            print(f"[{_ts()}][{self.emoji}] 📋 suspected_titles 상세:", file=sys.stderr)
            for i, st in enumerate(ctx.suspected_titles, 1):
                title = st.get('title', 'N/A')
                conf = st.get('confidence', 'N/A')
                source = st.get('source_expert', 'unknown')
                print(f"[{_ts()}][{self.emoji}]    [{i}] {title} (conf={conf}, from={source})", file=sys.stderr)
        
        # 제안 2 & 4: 전문가 신뢰도와 불확실성 정보 추가
        expert_confidence_info = ""
        if hasattr(ctx, 'expert_confidence') and ctx.expert_confidence:
            conf_items = [f"{k}={v:.2f}" for k, v in ctx.expert_confidence.items()]
            expert_confidence_info = f"\n\n=== 전문가 신뢰도 (제안 2) ===\n" + ", ".join(conf_items)
            expert_confidence_info += "\n(Verifier 0.95=high, 0.7=medium, 0.4=low)"
        
        uncertainty_info = ""
        if hasattr(ctx, 'uncertainty_sources') and ctx.uncertainty_sources:
            uncertainty_info = f"\n\n=== 불확실성 요인 (제안 4) ===\n" + "\n".join(f"- {u}" for u in ctx.uncertainty_sources)
            uncertainty_info += f"\n\n⚠️ 불확실성 요인 {len(ctx.uncertainty_sources)}개 발견!"
            if len(ctx.uncertainty_sources) >= 3:
                uncertainty_info += "\n→ confidence를 'low'로 하향하거나 notes에 불확실성 명시 권장"
        
        # ━━ 개선: candidate evidence bucket 요약 + source trust 정보를 Arbiter에 전달 ━━
        evidence_bucket_info = ""
        if hasattr(ctx, 'candidate_evidence') and ctx.candidate_evidence:
            evidence_bucket_info = "\n\n=== 후보별 증거 버킷 (Evidence Buckets) ===\n"
            for cand_title, bucket in ctx.candidate_evidence.items():
                post_count = len(bucket.get("post_spans", []))
                search_count = len(bucket.get("search_snippets", []))
                official_count = len(bucket.get("official_urls", []))
                # 소스 신뢰도 가중 점수 계산
                trust_scores = [s.get("trust_score", 0.2) for s in bucket.get("search_snippets", []) if isinstance(s, dict)]
                avg_trust = sum(trust_scores) / len(trust_scores) if trust_scores else 0.0
                evidence_bucket_info += (
                    f"  [{cand_title}] 본문증거={post_count}, 검색증거={search_count}, "
                    f"공식URL={official_count}, 평균신뢰도={avg_trust:.2f}\n"
                )
            evidence_bucket_info += (
                "\n⚠️ 후보 간 증거 혼용 금지: 각 후보의 증거는 해당 후보에 대해서만 유효합니다.\n"
                "   본문증거 0개 + 검색증거만 있는 후보는 확정 불가 (검색 결과만으로 is_relevant=true 판정 금지)\n"
            )
        
        # ━━ 개선: 가설 상태머신 이력 전달 ━━
        hypothesis_info = ""
        if hasattr(ctx, 'hypothesis_history') and ctx.hypothesis_history:
            invalidated = [h for h in ctx.hypothesis_history if h.get("invalidated")]
            if invalidated:
                hypothesis_info = "\n\n=== 가설 전환 이력 (Hypothesis History) ===\n"
                for h in invalidated:
                    hypothesis_info += (
                        f"  ❌ v{h['version']} '{h['title']}' → "
                        f"무효화됨 (by '{h.get('invalidated_by', '?')}', step {h.get('invalidated_at_step', '?')})\n"
                    )
                hypothesis_info += "⚠️ 가설이 전환된 경우, 이전 가설의 증거를 현재 후보에 적용하지 마세요.\n"
        
        discourse_info = ""
        if hasattr(ctx, 'primary_domain') and ctx.primary_domain:
            discourse_info = f"\n\n=== DiscourseAnalyzer 분석 (제안 1) ===\nDomain: {ctx.primary_domain}\nIntent: {ctx.discourse_intent}"
            
            # 🔥 Discourse 역방향 경고: non-novel 도메인이면 Arbiter에게 강력 경고
            if getattr(ctx, 'discourse_warning', None):
                discourse_info += f"\n\n🚨 DISCOURSE DOMAIN WARNING: {ctx.discourse_warning}\n"
                discourse_info += "이 포스트는 소설/웹소설과 무관한 밈/유머/일상 포스트일 가능성이 높습니다.\n"
                discourse_info += "Decoder가 식별한 제목이 있더라도, 본문/댓글에 해당 작품의 줄거리·작가명·플랫폼 URL 등 구체적 증거가 없으면:\n"
                discourse_info += "  → is_relevant=false 또는 confidence='Low'로 판정하세요.\n"
                discourse_info += "  → '장붕', '완장', '고닉' 등은 DC Inside 커뮤니티 자체 은어이므로 소설 캐릭터가 아닙니다.\n"
                discourse_info += "[CRITICAL] Decoder 우선 원칙의 예외: Discourse가 non-novel(high)이고 본문에 작품 관련 증거가 전혀 없으면 → Discourse 판정을 따르세요."
        
        user_prompt = ARBITER_PROMPT.format(
            post_id=ctx.post_id,
            title=post_data.get("title", ""),
            body_preview=body_preview,
            comment_count=len(comments),
            comment_preview=_comment_preview,
            gk_verdict=gk_verdict,
            dc_verdict=dc_verdict,
            vf_verdict=vf_verdict,
            verifier_veto=verifier_veto,
            key_evidence=key_evidence,
            suspected_titles=suspected_titles_str,
        ) + expert_confidence_info + uncertainty_info + evidence_bucket_info + hypothesis_info + discourse_info
        if _comment_context_lines:
            user_prompt += (
                "\n\n=== 댓글 작성자/대화 맥락 ===\n"
                "아래 #번호는 댓글 preview 순서와 대응합니다. role=post_author는 본문 작성자의 댓글입니다.\n"
                + "\n".join(f"  - {line}" for line in _comment_context_lines)
            )
        if _comment_dialogue_lines:
            user_prompt += (
                "\n\n=== 댓글 발화 재구성 ===\n"
                "speaker/author/ip는 대화 흐름 추적용이며, 그 자체를 작품명/별칭 증거로 쓰지 마세요.\n"
                + "\n".join(f"  - {line}" for line in _comment_dialogue_lines)
            )

        # 검색 집계 요약을 Arbiter에 직접 주입 (전문가 충돌 시 인프라/효율 맥락 보정)
        _search_agg = build_search_aggregation_summary(
            ctx,
            max_domains=6,
            max_purposes=6,
            max_queries=10,
        )
        if _search_agg:
            user_prompt += _search_agg

        # Canonical EID 카탈로그를 Arbiter에 직접 주입 (근거 인용 정합성 강화)
        try:
            _eid_catalog = ctx.build_search_evidence_catalog(max_items=999999) if hasattr(ctx, "build_search_evidence_catalog") else ""
        except Exception:
            _eid_catalog = ""
        if _eid_catalog:
            user_prompt += (
                "\n\n=== SEARCH EVIDENCE CATALOG (CANONICAL EID) ===\n"
                + _eid_catalog
                + "\n\nEvidence ID rule:\n"
                  "- 반드시 위 카탈로그의 EID만 근거 인용에 사용하세요.\n"
                  "- 임의 번호([1], [2] 등) 생성 금지.\n"
            )
        
        # 🆕 코드레벨 약어 분석 힌트 주입 → Arbiter 최종 판정 시 참고
        if hasattr(ctx, 'code_level_hints') and ctx.code_level_hints:
            code_hints_section = "\n\n=== CODE-LEVEL ANALYSIS (코드 레벨 약어 분석) ===\n"
            for i, hint in enumerate(ctx.code_level_hints[:3], 1):
                code_hints_section += (
                    f"  [{i}] '{hint.get('effective_keyword', '?')}' → "
                    f"'{hint.get('corrected_title', '?')}' "
                    f"(score={hint.get('abbreviation_score', 0):.2f})\n"
                )
            code_hints_section += "위 코드 분석은 음절 매칭 알고리즘의 객관적 결과입니다. 높은 score(≥0.8)는 강한 증거입니다.\n"
            user_prompt += code_hints_section
        
        # 🧷 Decoder+Verifier 제목 합의가 있으면 Arbiter에 잠금 힌트 주입
        # (동일 작가의 타 작품/후속작 가설로 합의 제목이 덮어써지는 드리프트 방지)
        def _norm_title_local(t: Any) -> str:
            if t is None:
                return ""
            return re.sub(r"\s+", "", str(t).strip()).lower()

        _dv_lock_title = ""
        _dec_title_cands: List[str] = []
        _dec_ov = decoder_out.get("overall_best_match") or {}
        if isinstance(_dec_ov, dict) and _dec_ov.get("title"):
            _dec_title_cands.append(str(_dec_ov.get("title")))
        for _dt in (decoder_out.get("decoded_terms") or []):
            if not isinstance(_dt, dict) or _dt.get("is_author_name"):
                continue
            _bm = _dt.get("best_match") or {}
            _bt = _bm.get("title")
            _bc = str(_bm.get("confidence") or "").lower()
            if _bt and _bc in {"high", "max", "medium"}:
                _dec_title_cands.append(str(_bt))

        _vf_title_cands: List[str] = []
        _vn = vf_result.get("novel_identity") or {}
        if isinstance(_vn, dict):
            for _k in ("official_novel_title", "official_title", "title"):
                _v = _vn.get(_k)
                if _v:
                    _vf_title_cands.append(str(_v))
        for _k in ("verified_title", "title"):
            _v = verifier_out.get(_k) if isinstance(verifier_out, dict) else None
            if _v:
                _vf_title_cands.append(str(_v))

        _dec_norm_to_raw = {_norm_title_local(t): t for t in _dec_title_cands if _norm_title_local(t)}
        _vf_norm_set = {_norm_title_local(t) for t in _vf_title_cands if _norm_title_local(t)}
        _dv_overlap = [n for n in _dec_norm_to_raw.keys() if n in _vf_norm_set]
        if _dv_overlap:
            _dv_lock_title = _dec_norm_to_raw[_dv_overlap[0]]
            user_prompt += (
                "\n\n=== CONSENSUS TITLE LOCK (합의 제목 잠금) ===\n"
                f"- Decoder+Verifier 합의 제목: {_dv_lock_title}\n"
                "- 위 제목과 다른 작품명/연작/후속작 가설은 참고 정보로만 취급하세요.\n"
                "- 본문/댓글 직접 근거(캐릭터명·줄거리·회차·플랫폼 상세페이지)가 없는 "
                "타 작품 치환은 금지합니다.\n"
            )
            print(
                f"[{_ts()}][{self.emoji}] 🧷 CONSENSUS TITLE LOCK 주입: '{_dv_lock_title}'",
                file=sys.stderr,
            )

        _canonical_lock_title = str(getattr(ctx, "canonical_title_lock", "") or "").strip()
        _canonical_lock_author = str(getattr(ctx, "canonical_author_lock", "") or "").strip()
        if _canonical_lock_title:
            _canonical_lock_norm = _norm_title_local(_canonical_lock_title)
            _overlap_norms = set(_dv_overlap)
            if _canonical_lock_norm and _canonical_lock_norm not in _overlap_norms:
                user_prompt += (
                    "\n\n=== SNIPPET CANONICAL LOCK (스니펫 정식 후보 잠금) ===\n"
                    f"- snippet canonical title: {_canonical_lock_title}\n"
                    f"{f'- snippet canonical author: {_canonical_lock_author}\n' if _canonical_lock_author else ''}"
                    "- 이 제목은 약칭, 본문 앵커, 작가/캐릭터 단서가 결합된 스니펫 기반 정식 후보입니다.\n"
                    "- 이후 검색에서 표면 유사 후보가 나타나더라도, "
                    "본문 직접 단서와 작가/캐릭터 결합이 약한 후보로 대체하지 마세요.\n"
                )
                print(
                    f"[{_ts()}][{self.emoji}] 🔐 snippet canonical lock 주입: "
                    f"'{_canonical_lock_title}'",
                    file=sys.stderr,
                )

        # 🆕 Synthesizer 증거 기반 재해석 결과 주입 (Critic → Synthesizer → Arbiter 흐름)
        synthesizer_out = ctx.get_expert_output(ExpertType.SYNTHESIZER) if hasattr(ctx, 'get_expert_output') else None
        if synthesizer_out and "error" not in synthesizer_out:
            from .synthesizer import SynthesizerExpert
            synth_section = SynthesizerExpert.summarize_for_arbiter(synthesizer_out)
            if synth_section:
                user_prompt += synth_section
                print(f"[{_ts()}][{self.emoji}] 🔬 Synthesizer 재해석 결과 주입 완료", file=sys.stderr)
        
        # 🆕 Multi-Expert Deliberation: EvidenceScorer 결과 주입
        _delib_evidence = getattr(ctx, '_deliberation_evidence_text', None)
        if _delib_evidence:
            user_prompt += str(_delib_evidence)
            print(f"[{_ts()}][{self.emoji}] 📊 EvidenceScorer 증거 분석 주입 완료", file=sys.stderr)
        else:
            # 기본 단독 호출 시에도 EvidenceScorer 실행 (0 cost)
            try:
                from .deliberation import EvidenceScorer
                _ev_result = EvidenceScorer.compute(ctx)
                _ev_text = EvidenceScorer.format_for_prompt(_ev_result)
                user_prompt += _ev_text
                print(
                    f"[{_ts()}][{self.emoji}] 📊 EvidenceScorer 자동 주입: "
                    f"score={_ev_result['total_score']}, prob={_ev_result['relevance_probability']}",
                    file=sys.stderr,
                )
            except Exception as _ev_err:
                print(f"[{_ts()}][{self.emoji}] ⚠️ EvidenceScorer 주입 실패: {_ev_err}", file=sys.stderr)
        
        try:
            result = self._call_llm(
                user_prompt,
                ctx=ctx,
                gatekeeper_result=gatekeeper_out,
                decoder_result=decoder_out,
                verifier_result=verifier_out,
                discourse_result=discourse_out,
            )
            elapsed = time.time() - start_time
            
            # None 체크
            if not result:
                print(f"[{_ts()}][{self.emoji}] {self.name} LLM 응답 없음 → 폴백", file=sys.stderr)
                return self._fallback_decision(ctx, "LLM returned None")
            
            # 🚨 LLM이 Verifier 스키마(verification_result)를 반복 출력한 경우 감지 → 폴백
            if "verification_result" in result and "final_decision" not in result:
                print(
                    f"[{_ts()}][{self.emoji}] ⚠️ Arbiter가 Verifier 스키마를 반복 출력 → 폴백 전환",
                    file=sys.stderr
                )
                return self._fallback_decision(ctx, "LLM echoed Verifier schema instead of Arbiter schema")
            
            # suspected_titles를 Context에 반영 (LLM 출력 직접 덮어쓰기 금지)
            # - 과거 이 지점에서 Arbiter LLM 환각 후보가 기존 Decoder/Verifier 합의를 덮어써
            #   강제 승격되는 오매칭이 발생함.
            # - 따라서 "병합 + 증거 필터"로만 반영한다.
            decision = result.get("final_decision") or {}

            # 🆕 Smart Deliberation: 후처리 가드 적용 전 LLM 원본 판정을 보존
            # 밈 가드/multi_work 가드 등이 is_relevant를 뒤집어도 deliberation에서
            # 원래 LLM 판단을 투표에 반영할 수 있도록 함
            decision["_raw_llm_relevant"] = decision.get("is_relevant")
            decision["_raw_llm_title"] = decision.get("official_novel_title") or decision.get("official_title")
            decision["_raw_llm_confidence"] = decision.get("confidence")
            decision["_raw_llm_discussion_type"] = decision.get("discussion_type")

            def _st_norm(v: Any) -> str:
                return re.sub(r"\s+", "", str(v or "")).lower()

            def _st_conf_num(conf_val: Any) -> int:
                if isinstance(conf_val, (int, float)):
                    v = float(conf_val)
                    if v >= 0.7:
                        return 3
                    if v >= 0.5:
                        return 2
                    if v >= 0.3:
                        return 1
                    return 0
                if isinstance(conf_val, str):
                    return {"high": 3, "medium": 2, "low": 1, "none": 0}.get(conf_val.lower(), 0)
                return 0

            def _title_evidence_counts(_title: Any) -> tuple[int, int, int]:
                if not _title or not hasattr(ctx, "get_candidate_evidence"):
                    return (0, 0, 0)
                try:
                    _bucket = ctx.get_candidate_evidence(_title) or {}
                except Exception:
                    return (0, 0, 0)
                if not isinstance(_bucket, dict):
                    return (0, 0, 0)
                _post_cnt = len((_bucket.get("post_spans") or []))
                _snippet_cnt = len((_bucket.get("search_snippets") or []))
                _official_cnt = len((_bucket.get("official_urls") or []))
                return (_post_cnt, _snippet_cnt, _official_cnt)

            def _title_has_supported_evidence(
                _title: Any,
                *,
                require_post_or_official: bool = False,
            ) -> bool:
                _post_cnt, _snippet_cnt, _official_cnt = _title_evidence_counts(_title)
                if require_post_or_official:
                    return (_post_cnt > 0) or (_official_cnt > 0)
                return (_post_cnt > 0) or (_official_cnt > 0) or (_snippet_cnt >= 2)

            def _score_forced_upgrade(
                *,
                candidate_title: Any,
                candidate_conf: Any,
                decoder_out_local: Dict[str, Any],
                verifier_out_local: Dict[str, Any],
            ) -> Dict[str, Any]:
                """
                강제승격 여부를 하드코딩 분기 대신 점수로 판정.
                score: 0.0~1.0, threshold 이상일 때만 승격 허용.
                """
                _title = str(candidate_title or "").strip()
                _reasons: List[str] = []

                def _text_matches_title(_text: Any, _needle: str) -> bool:
                    _text_norm = re.sub(r"[^0-9a-zA-Z가-힣]", "", str(_text or "")).lower()
                    _needle_norm = re.sub(r"[^0-9a-zA-Z가-힣]", "", str(_needle or "")).lower()
                    if not _text_norm or not _needle_norm:
                        return False
                    return _needle_norm in _text_norm

                def _add(delta: float, reason: str) -> None:
                    nonlocal _score
                    _score += float(delta)
                    _reasons.append(f"{delta:+.2f}:{reason}")

                def _is_derivative_variant_of(_cand: str, _base: str) -> bool:
                    _cand_s = str(_cand or "").strip()
                    _base_s = str(_base or "").strip()
                    if not _cand_s or not _base_s:
                        return False
                    _cand_norm = re.sub(r"[^0-9a-zA-Z가-힣]", "", _cand_s).lower()
                    _base_norm = re.sub(r"[^0-9a-zA-Z가-힣]", "", _base_s).lower()
                    if not _cand_norm or not _base_norm or _cand_norm == _base_norm:
                        return False
                    if len(_cand_norm) <= len(_base_norm) + 2:
                        return False
                    _br = re.match(r"^\s*\[([^\]]+)\]", _cand_s)
                    _br_norm = re.sub(r"[^0-9a-zA-Z가-힣]", "", _br.group(1)).lower() if _br else ""
                    if (_base_norm not in _cand_norm) and (_br_norm != _base_norm):
                        return False
                    _markers = (
                        "패러디", "팬픽", "팬아트", "외전", "리메이크", "스핀오프",
                        "후속", "if", "빙의", "환생", "전생", "조력자", "마왕",
                        "세계", "속", "겨울", "여름", "봄", "가을", "학교", "되었다",
                    )
                    _cand_compact = re.sub(r"\s+", "", _cand_s).lower()
                    return any(_m.lower() in _cand_compact for _m in _markers) or (_br_norm == _base_norm)

                if not _title:
                    return {
                        "score": 0.0,
                        "threshold": 1.0,
                        "allowed": False,
                        "reasons": ["+0.00:empty_title"],
                    }
                if self._curated_alias_lacks_contextual_work_anchor(
                    ctx,
                    _title,
                    verifier_out=verifier_out_local,
                ):
                    return {
                        "score": 0.0,
                        "threshold": 1.0,
                        "allowed": False,
                        "reasons": ["-1.00:curated_alias_missing_contextual_work_anchor"],
                    }

                _score = 0.0
                _warning = str(getattr(ctx, "discourse_warning", "") or "").lower().strip()
                _post_title_local = str((getattr(ctx, "post_data", {}) or {}).get("title") or "")
                _main_text_local = _post_title_local
                try:
                    _post_data_local = (getattr(ctx, "post_data", {}) or {})
                    _main_parts_local: List[str] = [str(_post_data_local.get("title") or "")]
                    for _blk_local in (_post_data_local.get("content_blocks") or []):
                        if isinstance(_blk_local, dict):
                            _main_parts_local.append(str(_blk_local.get("text") or ""))
                        elif isinstance(_blk_local, str):
                            _main_parts_local.append(_blk_local)
                    _main_text_local = " ".join(x for x in _main_parts_local if isinstance(x, str) and x.strip())
                except Exception:
                    _main_text_local = _post_title_local
                _title_in_main_post = _text_matches_title(_main_text_local, _title)

                # 1) 후보 자체 품질
                _conf_unit = self._confidence_to_unit(candidate_conf)
                if _conf_unit <= 0.0:
                    # 문자열 low/medium/high를 못 읽는 케이스 대비
                    _conf_unit = max(0.0, min(1.0, _st_conf_num(candidate_conf) / 3.0))
                _add(0.28 * _conf_unit, "candidate_confidence")

                _has_post_or_official = _title_has_supported_evidence(_title, require_post_or_official=True)
                _has_strong = bool(self._has_strong_title_support(ctx, _title))
                _direct_anchor = bool(self._title_directly_in_post(ctx, _title))
                _decoder_align = bool(
                    self._has_decoder_alignment_support(decoder_out_local, _title, min_score=0.45)
                )
                _post_cnt, _snippet_cnt, _official_cnt = _title_evidence_counts(_title)
                _support_type_cnt = int(_post_cnt > 0) + int(_snippet_cnt > 0) + int(_official_cnt > 0)
                _search_hit_cnt = 0
                _seen_hit_urls: Set[str] = set()
                for _sr in (getattr(ctx, "search_results", None) or []):
                    if not isinstance(_sr, dict):
                        continue
                    _sr_title = str(_sr.get("title") or "")
                    _sr_body = str(_sr.get("content") or "")
                    if not (
                        _text_matches_title(f"{_sr_title} {_sr_body}", _title)
                        or self._is_similar_title(_sr_title, _title)
                    ):
                        continue
                    _sr_url = str(_sr.get("url") or "").strip().lower()
                    _key = re.sub(r"/+$", "", _sr_url)
                    if not _key or _key in _seen_hit_urls:
                        continue
                    _seen_hit_urls.add(_key)
                    _search_hit_cnt += 1

                _character_parenthetical_support = any(
                    isinstance(_v, dict)
                    and not bool(_v.get("_weak_match"))
                    and _norm_title_local(_v.get("title")) == _norm_title_local(_title)
                    and str(_v.get("source") or "") == "character_parenthetical_wiki"
                    for _v in (getattr(ctx, "verified_character_work_links", []) or [])
                )
                if _character_parenthetical_support:
                    _has_post_or_official = True

                if _has_post_or_official:
                    _add(0.24, "post_or_official_evidence")
                else:
                    _add(-0.30, "no_post_or_official_evidence")
                if _has_strong:
                    _add(0.22, "strong_title_support")
                if _direct_anchor:
                    _add(0.15, "direct_title_anchor")
                if _decoder_align:
                    _add(0.12, "decoder_alignment")
                if _official_cnt > 0:
                    _add(min(0.12, 0.06 * _official_cnt), "official_url_count")
                if _post_cnt > 0:
                    _add(min(0.10, 0.05 * _post_cnt), "post_span_count")
                if _snippet_cnt > 0:
                    _add(min(0.04, 0.01 * _snippet_cnt), "search_snippet_count")
                if _support_type_cnt >= 2:
                    _add(min(0.10, 0.05 * (_support_type_cnt - 1)), "evidence_type_diversity")
                if _search_hit_cnt > 0:
                    _add(min(0.09, 0.03 * _search_hit_cnt), "search_hit_count")
                if _character_parenthetical_support:
                    _add(0.36, "character_parenthetical_bridge")
                if _snippet_cnt > 0 and _search_hit_cnt <= 1 and _official_cnt == 0 and _post_cnt == 0:
                    _add(-0.08, "single_path_snippet_support")
                if _title_in_main_post:
                    _add(0.08, "title_in_main_post")

                if self._looks_like_platform_event_meta_post(ctx) and not _title_in_main_post:
                    _add(-0.35, "platform_event_meta_comment_only")

                if self._is_platform_branding_title(_title):
                    _add(-0.25, "platform_branding_title")
                if _post_title_local and _has_domain_conflict_for_mapping(_post_title_local, _title):
                    _add(-0.20, "domain_conflict_with_post_title")

                _candidate_pool: List[str] = []
                for _st in (getattr(ctx, "suspected_titles", None) or []):
                    if not isinstance(_st, dict):
                        continue
                    _st_title = str(_st.get("title") or "").strip()
                    if _st_title:
                        _candidate_pool.append(_st_title)
                for _dt in (decoder_out_local.get("decoded_terms") or []):
                    if not isinstance(_dt, dict):
                        continue
                    _bm = _dt.get("best_match") or {}
                    _bm_title = str(_bm.get("title") or "").strip()
                    if _bm_title:
                        _candidate_pool.append(_bm_title)
                    for _cand in (_dt.get("candidates") or []):
                        if not isinstance(_cand, dict):
                            continue
                        _cand_title = str(
                            _cand.get("official_novel_title")
                            or _cand.get("official_title")
                            or _cand.get("title")
                            or ""
                        ).strip()
                        if _cand_title:
                            _candidate_pool.append(_cand_title)

                _derivative_base = ""
                _title_norm_local = re.sub(r"[^0-9a-zA-Z가-힣]", "", _title).lower()
                for _other_title in _candidate_pool:
                    _other_norm = re.sub(r"[^0-9a-zA-Z가-힣]", "", str(_other_title or "")).lower()
                    if not _other_norm or _other_norm == _title_norm_local:
                        continue
                    if _is_derivative_variant_of(_title, _other_title):
                        _derivative_base = _other_title
                        break
                if _derivative_base:
                    _base_post_cnt, _base_snippet_cnt, _base_official_cnt = _title_evidence_counts(_derivative_base)
                    _base_bucket_like = (_base_post_cnt * 2) + _base_snippet_cnt + (_base_official_cnt * 3)
                    _base_supported = bool(
                        self._has_strong_title_support(ctx, _derivative_base)
                        or _base_official_cnt > 0
                        or _base_bucket_like >= 3
                    )
                    _add(-0.18, f"derivative_variant:{_derivative_base}")
                    if _base_supported:
                        _add(-0.22, "competing_canonical_title")

                # 1a-2) 에피소드 제목 패턴 감지 페널티
                # "LV.157 성기사 황건욱" 같은 에피소드 제목이 정식 시리즈 제목을 덮어쓰지 않도록 함
                # joara.com/viewer URL은 개별 에피소드이지 시리즈가 아님
                import re as _re_ep
                _ep_patterns = [
                    r'^(?:LV|Lv|lv)\s*\.?\s*\d+',           # LV.157 ...
                    r'^\d+화\s',                              # 170화 ...
                    r'[-]\s*\[\d+\]\s*\(\d+편\)',             # - [3](170편)
                    r'^\d+부\s+\d+화',                        # 2부 15화
                    r'^(?:EP|ep|Ep)\s*\.?\s*\d+',            # EP.15 ...
                    r'^제?\s*\d+\s*(?:화|편|장|절|회)\b',      # 제15화
                ]
                if any(_re_ep.search(p, _title) for p in _ep_patterns):
                    _add(-0.40, "episode_title_pattern")

                # 1b) 포스트 제목 꺾쇠/괄호 표기 보너스
                # <마법으로 딸깍하니 전설의 마법사> ㅊㅊ함 → 꺾쇠 안 제목은 거의 확정적
                import re as _re_score
                _bracket_m = _re_score.search(
                    r'[<《「『【]([\w가-힣\s]{2,})[>》」』】]', _post_title_local
                )
                if _bracket_m:
                    _bracket_title_raw = _bracket_m.group(1).strip()
                    _bracket_norm = _bracket_title_raw.replace(" ", "").lower()
                    _title_norm_for_bracket = _title.replace(" ", "").lower()
                    if _bracket_norm and _bracket_norm == _title_norm_for_bracket:
                        _add(0.35, "post_title_bracket_exact_match")
                    elif _bracket_norm and _bracket_norm in _title_norm_for_bracket:
                        _add(0.20, "post_title_bracket_partial_match")

                # 2) 전역 판정 신호
                _effective_genre_warn = self._is_effective_genre_warning(
                    ctx, decoder_out_local, verifier_out_local
                )
                if _effective_genre_warn:
                    _add(-0.20, "effective_genre_warning")
                if "non_novel(" in _warning:
                    _add(-0.20, "non_novel_warning")

                _is_assoc = bool(getattr(ctx, "is_association_post", False))
                _dec_overall_conf = str(decoder_out_local.get("overall_confidence", "")).lower().strip()
                if _is_assoc and _dec_overall_conf in {"none", "low", ""}:
                    _add(-0.12, "association_low_decoder_conf")
                if (
                    (not _title_in_main_post)
                    and (_post_cnt <= 0)
                    and (_official_cnt > 0 or _snippet_cnt > 0)
                    and (_effective_genre_warn or _is_assoc)
                    and not _decoder_align
                ):
                    _add(-0.16, "no_main_post_grounding")

                _post_title_norm_local = _post_title_local.lower().replace(" ", "")
                _temporal_kws_local = ("신작", "최신작", "새작품", "이번작", "전작", "차기작", "신간")
                _launch_kws_local = ("스타트", "초반", "초반부", "첫인상", "첫화", "도입", "출발")
                _author_new_work_local = bool(
                    any(_kw in _post_title_norm_local for _kw in _temporal_kws_local)
                    or (
                        re.match(
                            r"^\s*[가-힣A-Za-z0-9]{2,12}(?:꺼)?\s*(?:신작|최신작|새작품|이번작|전작|차기작|신간)",
                            _post_title_local,
                        )
                        and any(_kw in _post_title_norm_local for _kw in _launch_kws_local)
                    )
                )
                if _author_new_work_local and (not _title_in_main_post):
                    _add(-0.22, "author_new_work_without_main_title")

                # Decoder 강한 앵커 보너스 (candidate와 연결된 경우)
                _dec_anchor_hit = False
                for _dt in decoder_out_local.get("decoded_terms", []) or []:
                    if not isinstance(_dt, dict):
                        continue
                    _bm = _dt.get("best_match") or {}
                    _bm_title = str(_bm.get("title") or "").strip()
                    _bm_conf = str(_bm.get("confidence") or "").lower().strip()
                    _gr = _dt.get("grounding") or {}
                    _a = str(_gr.get("anchor_type") or "").lower().strip()
                    if (
                        _bm_title
                        and _norm_title_local(_bm_title) == _norm_title_local(_title)
                        and _bm_conf in {"high", "max"}
                        and _a in {"title_mention", "character_title_link", "plot_mention"}
                        and not _dt.get("is_author_name")
                    ):
                        _dec_anchor_hit = True
                        break
                if _dec_anchor_hit:
                    _add(0.18, "decoder_strong_anchor_match")

                _vf_result_local = (verifier_out_local.get("verification_result") or {}) if isinstance(verifier_out_local, dict) else {}
                _vf_relevant_local = _vf_result_local.get("is_relevant")
                if _vf_relevant_local is True:
                    _add(0.10, "verifier_relevant_true")
                elif _vf_relevant_local is False:
                    _add(-0.10, "verifier_relevant_false")

                _vf_ground_local = _vf_result_local.get("grounding_check") or {}
                _vf_anchor_local = str(_vf_ground_local.get("anchor_found") or "").lower().strip()
                if _vf_anchor_local in {"none", "search_only"}:
                    _add(-0.10, f"verifier_anchor={_vf_anchor_local}")

                _counter_args_local = _vf_result_local.get("counter_arguments") or []
                _critical_reject = any(
                    isinstance(_ca, dict)
                    and str(_ca.get("severity", "")).lower() == "critical"
                    and str(_ca.get("action", "")).lower() == "reject"
                    for _ca in _counter_args_local
                )
                if _critical_reject:
                    _add(-0.15, "verifier_critical_reject_counter")

                _score = max(0.0, min(1.0, _score))
                _threshold = float(
                    os.getenv("ARBITER_FORCE_UPGRADE_SCORE_THRESHOLD", "0.62").strip() or "0.62"
                )
                _allowed = _score >= _threshold
                return {
                    "score": round(_score, 4),
                    "threshold": round(_threshold, 4),
                    "allowed": _allowed,
                    "reasons": _reasons,
                    "metrics": {
                        "title": _title,
                        "conf_unit": round(_conf_unit, 4),
                        "post_or_official": _has_post_or_official,
                        "strong_support": _has_strong,
                        "direct_anchor": _direct_anchor,
                        "decoder_align": _decoder_align,
                        "post_cnt": _post_cnt,
                        "official_cnt": _official_cnt,
                        "snippet_cnt": _snippet_cnt,
                    },
                }

            # 기존 suspected_titles 정규화 (str 섞임 방지: 'str' object has no attribute 'get')
            _existing_normed: List[Dict[str, Any]] = []
            for _st in (getattr(ctx, "suspected_titles", []) or []):
                if isinstance(_st, str):
                    _title = _st.strip()
                    if _title:
                        _existing_normed.append({
                            "title": _title,
                            "confidence": "low",
                            "source_expert": "legacy",
                        })
                    continue
                if not isinstance(_st, dict):
                    continue
                _title = (
                    _st.get("title")
                    or _st.get("official_novel_title")
                    or _st.get("official_title")
                )
                if not _title:
                    continue
                _new_st = dict(_st)
                _new_st["title"] = _title
                _existing_normed.append(_new_st)
            ctx.suspected_titles = _existing_normed

            _llm_raw = decision.get("suspected_titles")
            if isinstance(_llm_raw, list) and _llm_raw:
                # Decoder/Verifier 합의 키 집합
                _decoder_norm_titles: Set[str] = set()
                if decoder_out:
                    _overall_bm = decoder_out.get("overall_best_match") or {}
                    if isinstance(_overall_bm, dict):
                        _ov_title = _overall_bm.get("title")
                        if _ov_title:
                            _decoder_norm_titles.add(_st_norm(_ov_title))
                    for _term in (decoder_out.get("decoded_terms") or []):
                        if not isinstance(_term, dict):
                            continue
                        if _term.get("is_author_name"):
                            continue
                        _bm = _term.get("best_match") or {}
                        _dt = _bm.get("title")
                        if _dt:
                            _decoder_norm_titles.add(_st_norm(_dt))

                _verifier_norm_titles: Set[str] = set()
                if isinstance(vf_result, dict):
                    _vn = vf_result.get("novel_identity") or {}
                    if isinstance(_vn, dict):
                        for _k in ("official_novel_title", "official_title", "title"):
                            _v = _vn.get(_k)
                            if _v:
                                _verifier_norm_titles.add(_st_norm(_v))
                    for _k in ("verified_title", "title"):
                        _v = vf_result.get(_k)
                        if _v:
                            _verifier_norm_titles.add(_st_norm(_v))

                _accepted_llm: List[Dict[str, Any]] = []
                _rejected_llm: List[str] = []
                for _item in _llm_raw[:5]:
                    if isinstance(_item, str):
                        _cand = {
                            "title": _item.strip(),
                            "confidence": "low",
                            "source_expert": "arbiter_llm",
                            "status": "suspected",
                        }
                    elif isinstance(_item, dict):
                        _title = (
                            _item.get("title")
                            or _item.get("official_novel_title")
                            or _item.get("official_title")
                        )
                        if not _title:
                            continue
                        _cand = dict(_item)
                        _cand["title"] = _title
                        _cand.setdefault("confidence", "low")
                        _cand["source_expert"] = "arbiter_llm"
                        _cand.setdefault("status", "suspected")
                    else:
                        continue

                    _title = str(_cand.get("title", "")).strip()
                    if not _title:
                        continue

                    _title_norm = _st_norm(_title)
                    _bucket = ctx.get_candidate_evidence(_title) if hasattr(ctx, "get_candidate_evidence") else {}
                    _post_cnt = len((_bucket or {}).get("post_spans", []))
                    _official_cnt = len((_bucket or {}).get("official_urls", []))
                    _character_parenthetical_supported = any(
                        isinstance(_v, dict)
                        and not bool(_v.get("_weak_match"))
                        and _st_norm(_v.get("title")) == _title_norm
                        and str(_v.get("source") or "") == "character_parenthetical_wiki"
                        for _v in (getattr(ctx, "verified_character_work_links", []) or [])
                    )
                    _strong_title_support = bool(self._has_strong_title_support(ctx, _title))

                    # Arbiter-LLM 후보 수용 조건:
                    # 1) Decoder/Verifier 합의 타이틀과 일치, 또는
                    # 2) 최소한 본문/공식URL 증거 버킷이 존재
                    # 3) 캐릭터명(작품명) 위키 브리지 + 공식/강검색 근거가 존재
                    _is_supported = (
                        (_title_norm in _decoder_norm_titles)
                        or (_title_norm in _verifier_norm_titles)
                        or (_post_cnt > 0)
                        or (_official_cnt > 0)
                        or (_character_parenthetical_supported and _strong_title_support)
                    )

                    if _is_supported:
                        _accepted_llm.append(_cand)
                    else:
                        _rejected_llm.append(_title)

                if _accepted_llm:
                    _by_norm: Dict[str, Dict[str, Any]] = {}
                    for _st in (ctx.suspected_titles or []):
                        if not isinstance(_st, dict):
                            continue
                        _t = _st.get("title")
                        if not _t:
                            continue
                        _by_norm[_st_norm(_t)] = _st

                    for _cand in _accepted_llm:
                        _key = _st_norm(_cand.get("title"))
                        _prev = _by_norm.get(_key)
                        if _prev is None:
                            _by_norm[_key] = _cand
                            continue
                        if _st_conf_num(_cand.get("confidence")) > _st_conf_num(_prev.get("confidence")):
                            _by_norm[_key] = _cand

                    ctx.suspected_titles = list(_by_norm.values())
                    ctx.suspected_titles.sort(key=lambda x: _st_conf_num(x.get("confidence")), reverse=True)
                    ctx.suspected_titles = ctx.suspected_titles[:5]

                    print(
                        f"[{_ts()}][{self.emoji}] 📋 Arbiter LLM suspected 병합: "
                        f"accept={len(_accepted_llm)}, keep_total={len(ctx.suspected_titles)}",
                        file=sys.stderr,
                    )
                if _rejected_llm:
                    print(
                        f"[{_ts()}][{self.emoji}] 🛡️ Arbiter LLM suspected 기각: "
                        f"{_rejected_llm[:3]} (증거 버킷/합의 불충분)",
                        file=sys.stderr,
                    )
            
            # 🚨 P1-5: suspected_titles에서 최고 confidence 제목을 official_title로 강제 설정
            # (LLM이 축약어를 선택하는 것을 방지)
            # 🔧 P1-5-FIX: 검색 결과와 문자 단위 비교하여 LLM 변형 오류 방지
            # 🔧 author_talk 예외: Arbiter가 의도적으로 null 설정한 경우 강제 적용 스킵
            discussion_type_val = decision.get("discussion_type", "")
            skip_forced_title = discussion_type_val in ("author_talk", "author_criticism")
            author_criticism_guard_active = False
            forced_upgrade_eval: Dict[str, Any] = {
                "score": 0.0,
                "threshold": float(os.getenv("ARBITER_FORCE_UPGRADE_SCORE_THRESHOLD", "0.62") or 0.62),
                "allowed": False,
                "title": None,
                "reasons": [],
            }

            # 🛡️ 작가 비평형 게시글(예: "[작가]는 [장르]이나 써라")은
            # suspected_titles 강제 승격으로 작품명이 확정되지 않도록 선제 차단
            _is_author_criticism_post, _author_criticism_signals = self._detect_author_criticism_post(
                post_data=post_data,
                comments=comments,
                gatekeeper_out=gatekeeper_out,
                decoder_out=decoder_out,
            )
            if _is_author_criticism_post:
                author_criticism_guard_active = True
                skip_forced_title = True
                decision["is_relevant"] = False
                decision["is_novel_discussion"] = False
                decision["official_title"] = None
                decision["official_novel_title"] = None
                decision["heretic_url"] = None
                decision["discussion_type"] = "author_talk"
                decision["confidence"] = "Low"
                _signals_text = ", ".join(_author_criticism_signals[:4]) if _author_criticism_signals else "pattern_match"
                _guard_note = f"[author_criticism 가드] 작가 비평 패턴 감지 ({_signals_text})"
                _existing_notes = str(decision.get("notes") or "").strip()
                decision["notes"] = f"{_guard_note}. {_existing_notes}" if _existing_notes else _guard_note
                _guard_reason = (
                    "작가 지칭 + 지시형 어미 + 장르/예시 표현이 함께 나타나 "
                    "특정 작품 토론이 아닌 author_talk(작가 비평)으로 분류."
                )
                decision["final_reasoning"] = _guard_reason
                if decision.get("reason"):
                    decision["reason"] = _guard_reason
                _null_reasons = decision.get("_title_null_block_reasons")
                if not isinstance(_null_reasons, list):
                    _null_reasons = []
                _null_reasons.append("author_criticism_guard")
                decision["_title_null_block_reasons"] = sorted(set(_null_reasons))
                print(
                    f"[{_ts()}][{self.emoji}] 🛡️ author_criticism 선제 가드: "
                    f"signals={_author_criticism_signals[:4]} → title 강제승격 차단 + author_talk 고정",
                    file=sys.stderr,
                )

            # 🛡️ 추천 요청형 게시글은 단일 작품 강제승격을 금지
            # 댓글/검색에서 특정 작품이 보여도 "질문-응답" 담화가 우선이므로
            # 작품 토론(is_relevant=true)으로 뒤집지 않는다.
            _is_reco_request_post, _reco_signals = self._detect_recommendation_request_post(
                post_data=post_data,
                gatekeeper_out=gatekeeper_out,
                discourse_out=discourse_out,
            )
            _reco_candidate_title = str(
                decision.get("official_title")
                or decision.get("official_novel_title")
                or ""
            ).strip()
            _recommendation_specific_work_exempt = self._has_question_plot_title_support(
                ctx=ctx,
                candidate_title=_reco_candidate_title,
                post_data=post_data,
                gatekeeper_out=gatekeeper_out,
                discourse_out=discourse_out,
            )
            if _is_reco_request_post and not author_criticism_guard_active and not _recommendation_specific_work_exempt:
                skip_forced_title = True
                decision["is_relevant"] = False
                decision["is_novel_discussion"] = False
                decision["official_title"] = None
                decision["official_novel_title"] = None
                decision["heretic_url"] = None
                decision["discussion_type"] = "recommendation"
                if not decision.get("confidence"):
                    decision["confidence"] = "Low"
                _reco_reason = (
                    "요청형 어미/의도(추천좀 등)와 전문가 신호가 합치되어 "
                    "추천 요청 게시글로 판정. 댓글의 작품명은 답변 예시로 간주."
                )
                decision["final_reasoning"] = _reco_reason
                if decision.get("reason"):
                    decision["reason"] = _reco_reason
                _null_reasons = decision.get("_title_null_block_reasons")
                if not isinstance(_null_reasons, list):
                    _null_reasons = []
                _null_reasons.append("recommendation_guard")
                decision["_title_null_block_reasons"] = sorted(set(_null_reasons))
                _reco_note = f"[recommendation 가드] 추천 요청 화행 감지 ({', '.join(_reco_signals[:4])})"
                _old_notes = str(decision.get("notes") or "").strip()
                decision["notes"] = f"{_reco_note}. {_old_notes}" if _old_notes else _reco_note
                print(
                    f"[{_ts()}][{self.emoji}] 🛡️ recommendation 선제 가드: "
                    f"signals={_reco_signals[:4]} → 강제승격 차단 + recommendation 고정",
                    file=sys.stderr,
                )
            elif _recommendation_specific_work_exempt:
                print(
                    f"[{_ts()}][{self.emoji}] 🛡️ recommendation 가드 면제: "
                    f"question+comment_plot_support title='{_reco_candidate_title}'",
                    file=sys.stderr,
                )

            # 🛡️ 다작/복수작 맥락 가드:
            # 댓글/본문에서 여러 작품을 나열/비교하는 경우 단일 작품 강제승격을 막는다.
            # (예: "트럭커랑 몰락, 망배우 재밌음?")
            _is_multi_work_context, _multi_work_signals = self._detect_multi_work_context_post(
                post_data=post_data,
                comments=comments,
                gatekeeper_out=gatekeeper_out,
                discourse_out=discourse_out,
                decoder_out=decoder_out,
                verifier_out=verifier_out,
            )
            if _is_multi_work_context and not author_criticism_guard_active:
                _mw_abbrev_exempt = False
                _mw_current_title = decision.get("official_novel_title") or decision.get("official_title")
                if _mw_current_title:
                    _mw_abbrev_exempt = self._has_curated_alias_guard_exception(
                        ctx,
                        _mw_current_title,
                        decoder_out=decoder_out,
                        verifier_out=verifier_out,
                    )
                if _mw_abbrev_exempt:
                    print(
                        f"[{_ts()}][{self.emoji}] 🔑 multi_work 가드 면제: "
                        f"등록 약칭 + 독립 작품 앵커 확인 → title 유지",
                        file=sys.stderr,
                    )
                else:
                    skip_forced_title = True
                    decision["official_title"] = None
                    decision["official_novel_title"] = None
                    decision["heretic_url"] = None
                    if decision.get("discussion_type") in {"review", "anticipation", "character_talk", "spoiler", "unknown", ""}:
                        decision["discussion_type"] = "general"
                    _multi_reason = (
                        "복수 작품/작품군 비교 맥락이 감지되어 단일 official_title 확정을 보류함."
                    )
                    if decision.get("is_relevant", False):
                        decision["is_novel_discussion"] = True
                    _old_reason = str(decision.get("final_reasoning") or "").strip()
                    decision["final_reasoning"] = f"{_multi_reason} {_old_reason}".strip()
                    _old_notes = str(decision.get("notes") or "").strip()
                    _multi_note = f"[multi_work 가드] 복수 작품 맥락 감지 ({', '.join(_multi_work_signals[:4])})"
                    decision["notes"] = f"{_multi_note}. {_old_notes}" if _old_notes else _multi_note
                    _null_reasons = decision.get("_title_null_block_reasons")
                    if not isinstance(_null_reasons, list):
                        _null_reasons = []
                    _null_reasons.append("multi_work_guard")
                    decision["_title_null_block_reasons"] = sorted(set(_null_reasons))
                    print(
                        f"[{_ts()}][{self.emoji}] 🛡️ multi_work 선제 가드: "
                        f"signals={_multi_work_signals[:4]} → 단일 title 강제승격 차단",
                        file=sys.stderr,
                    )
            
            # 🔧 Phase26-A: Arbiter LLM이 명시적으로 official_novel_title=null로 판단한 경우
            # suspected_titles 기반 강제 승격을 스킵 (LLM의 의도적 null 판단 존중)
            # 🔧 Phase27-A: 단, suspected_titles에 High confidence 후보가 있으면 스킵하지 않음
            #   (Arbiter LLM이 title을 null로 남겨도, 검색 증거 기반 강한 후보는 적용해야 함)
            arbiter_explicit_null = (
                decision.get("official_novel_title") is None
                and decision.get("is_relevant", False)
            )
            def _suspected_conf_highish(_st: Dict[str, Any]) -> bool:
                if not isinstance(_st, dict):
                    return False
                return _st_conf_num(_st.get("confidence")) >= 3

            def _character_parenthetical_suspect_supported(_st: Dict[str, Any]) -> bool:
                if not isinstance(_st, dict):
                    return False
                _title = str(_st.get("title") or "").strip()
                if not _title:
                    return False
                _src = str(_st.get("source_expert") or _st.get("from") or "").lower()
                if _src != "character_parenthetical":
                    return False
                _title_norm = _st_norm(_title)
                _has_link = any(
                    isinstance(_v, dict)
                    and not bool(_v.get("_weak_match"))
                    and _st_norm(_v.get("title")) == _title_norm
                    and str(_v.get("source") or "") == "character_parenthetical_wiki"
                    for _v in (getattr(ctx, "verified_character_work_links", []) or [])
                )
                if not _has_link:
                    return False
                _parenthetical_search_hit = False
                for _sr in (getattr(ctx, "search_results", None) or []):
                    if not isinstance(_sr, dict):
                        continue
                    _sr_title_norm = _st_norm(_sr.get("title"))
                    if _title_norm and _title_norm in _sr_title_norm and "(" in str(_sr.get("title") or ""):
                        _parenthetical_search_hit = True
                        break
                return bool(
                    self._has_strong_title_support(ctx, _title)
                    or _title_has_supported_evidence(_title, require_post_or_official=False)
                    or _parenthetical_search_hit
                )

            if arbiter_explicit_null and not skip_forced_title:
                # suspected_titles에 High confidence 후보가 있으면 null 가드를 우회
                _has_high_suspected = any(
                    isinstance(st, dict)
                    and st.get("title")
                    and _suspected_conf_highish(st)
                    and (
                        _title_has_supported_evidence(
                            st.get("title"),
                            require_post_or_official=True,
                        )
                        or _character_parenthetical_suspect_supported(st)
                    )
                    for st in (ctx.suspected_titles or [])
                )
                if _has_high_suspected:
                    # 🆕 Verifier가 확인한 풀 제목이 있으면 suspected_titles에 주입
                    # Arbiter LLM이 약어만 suspected에 넣고 풀 제목을 누락하는 패턴 방지
                    # 예: Verifier가 '즉사기 들고 무림에 떨어지다'(High)를 확인했는데
                    #     Arbiter suspected에 '즉사무림'(약어)만 있으면 풀 제목으로 교체
                    _vf_out = ctx.expert_outputs.get("verifier") or {} if hasattr(ctx, 'expert_outputs') else {}
                    _vf_vr = _vf_out.get("verification_result") or {}
                    _vf_ni = _vf_vr.get("novel_identity") or {}
                    _vf_title = _vf_ni.get("official_novel_title") or _vf_ni.get("official_title", "")
                    _vf_conf = str(_vf_ni.get("confidence", "")).lower()
                    _vf_url = _vf_ni.get("heretic_url", "")
                    if _vf_title and _vf_conf in ("high", "medium") and len(_vf_title) > 4:
                        # suspected_titles에 Verifier 확인 풀 제목 주입 (최고 우선순위)
                        _already_in = any(
                            st.get("title") == _vf_title
                            for st in (ctx.suspected_titles or [])
                            if isinstance(st, dict)
                        )
                        if not _already_in:
                            ctx.suspected_titles.insert(0, {
                                "title": _vf_title,
                                "confidence": _vf_conf.capitalize(),
                                "url": _vf_url,
                                "from": "verifier_confirmed",
                            })
                            print(
                                f"[{_ts()}][{self.emoji}] 🔧 Verifier 확인 풀 제목 suspected에 주입: "
                                f"'{_vf_title}' (conf={_vf_conf}) — 약어 대신 풀 제목 우선 채택",
                                file=sys.stderr,
                            )
                    print(
                        f"[{_ts()}][{self.emoji}] 🔓 Arbiter null 가드 우회: "
                        f"LLM이 official_novel_title=null이지만 suspected_titles에 High 후보 존재 → 강제 적용 허용",
                        file=sys.stderr
                    )
                else:
                    print(
                        f"[{_ts()}][{self.emoji}] 🛡️ Arbiter null 가드: "
                        f"LLM이 official_novel_title=null 판단 → suspected_titles 강제 승격 스킵",
                        file=sys.stderr
                    )
                    skip_forced_title = True
            
            # 🔧 Phase26-B: Arbiter LLM이 명시적으로 is_relevant=false로 판단한 경우
            # suspected_titles 승격으로 역전되는 것을 방지 (Arbiter의 거부 판단 존중)
            # 🆕 예외: suspected_titles에 검색 증거 기반 medium+ 후보가 있으면 거부 가드 무시
            #   (검색에서 약칭→정식제목이 확인된 경우, LLM 환각보다 검색 증거가 우선)
            arbiter_explicit_false = (decision.get("is_relevant") == False)
            if arbiter_explicit_false and not skip_forced_title:
                # 강제 승격(거부 가드 무시) 기능 전체 on/off
                # 기본값: ON(1). 실험적으로 FP를 줄이려면 ARBITER_FORCE_UPGRADE=0 설정.
                _force_upgrade_enabled = os.getenv("ARBITER_FORCE_UPGRADE", "1").strip().lower() not in (
                    "0", "false", "no", "off"
                )
                if not _force_upgrade_enabled:
                    print(
                        f"[{_ts()}][{self.emoji}] 🛡️ Arbiter 강제승격 비활성화: "
                        f"ARBITER_FORCE_UPGRADE=0 → LLM is_relevant=false 존중",
                        file=sys.stderr,
                    )
                    skip_forced_title = True
                else:
                    # suspected_titles 후보를 점수화해서 강제승격 가능성을 판정
                    _has_strong_suspect = False
                    _best_force_eval: Optional[Dict[str, Any]] = None
                    if ctx.suspected_titles:
                        for _st in ctx.suspected_titles:
                            if not isinstance(_st, dict):
                                continue
                            _st_title = _st.get("title")
                            if not _st_title:
                                continue
                            _eval = _score_forced_upgrade(
                                candidate_title=_st_title,
                                candidate_conf=_st.get("confidence"),
                                decoder_out_local=decoder_out or {},
                                verifier_out_local=verifier_out or {},
                            )
                            _eval["title"] = _st_title
                            if (_best_force_eval is None) or (_eval.get("score", 0.0) > _best_force_eval.get("score", 0.0)):
                                _best_force_eval = _eval

                    if _best_force_eval:
                        forced_upgrade_eval = {
                            "score": _best_force_eval.get("score", 0.0),
                            "threshold": _best_force_eval.get("threshold", forced_upgrade_eval.get("threshold", 0.62)),
                            "allowed": bool(_best_force_eval.get("allowed")),
                            "title": _best_force_eval.get("title"),
                            "reasons": _best_force_eval.get("reasons", []),
                        }
                        decision["_forced_upgrade_score"] = forced_upgrade_eval["score"]
                        decision["_forced_upgrade_threshold"] = forced_upgrade_eval["threshold"]
                        decision["_forced_upgrade_title"] = forced_upgrade_eval["title"]
                        _has_strong_suspect = forced_upgrade_eval["allowed"]
                        if _has_strong_suspect and self._should_block_memory_query_forced_upgrade(
                            ctx,
                            verifier_out,
                            forced_upgrade_eval.get("title"),
                        ):
                            _has_strong_suspect = False
                            forced_upgrade_eval["allowed"] = False
                            skip_forced_title = True
                            _null_reasons = decision.get("_title_null_block_reasons")
                            if not isinstance(_null_reasons, list):
                                _null_reasons = []
                            _null_reasons.append("memory_query_forced_upgrade_guard")
                            decision["_title_null_block_reasons"] = sorted(set(_null_reasons))
                            print(
                                f"[{_ts()}][{self.emoji}] 🛡️ memory-query 강제승격 차단: "
                                f"title='{forced_upgrade_eval.get('title')}', "
                                f"score={forced_upgrade_eval.get('score', 0.0):.3f} "
                                "→ relation hold + direct bridge 없음",
                                file=sys.stderr,
                            )
                        if _has_strong_suspect:
                            print(
                                f"[{_ts()}][{self.emoji}] 📈 강제승격 점수 통과: "
                                f"title='{forced_upgrade_eval['title']}', "
                                f"score={forced_upgrade_eval['score']:.3f} >= {forced_upgrade_eval['threshold']:.3f}",
                                file=sys.stderr,
                            )
                        else:
                            print(
                                f"[{_ts()}][{self.emoji}] 🛡️ 강제승격 점수 미달: "
                                f"title='{forced_upgrade_eval['title']}', "
                                f"score={forced_upgrade_eval['score']:.3f} < {forced_upgrade_eval['threshold']:.3f}",
                                file=sys.stderr,
                            )
                            print(
                                f"[{_ts()}][{self.emoji}]    └ score_breakdown: "
                                f"{', '.join((forced_upgrade_eval.get('reasons') or [])[:8])}",
                                file=sys.stderr,
                            )

                    if _has_strong_suspect:
                        # 🆕 시간참조 키워드가 게시글 제목에 있으면 강제승격 차단
                        _temporal_kws_force = ["신작", "최신작", "새작품", "이번작", "전작", "차기작", "신간"]
                        _pt_raw_force = ""
                        if ctx and hasattr(ctx, "post_data"):
                            _pt_raw_force = (getattr(ctx, "post_data", {}) or {}).get("title", "").lower().replace(" ", "")
                        _has_temporal_force = any(tk in _pt_raw_force for tk in _temporal_kws_force)

                        if _has_temporal_force:
                            print(
                                f"[{_ts()}][{self.emoji}] 🛡️ 시간참조 강제승격 차단: "
                                f"게시글 제목에 시간참조 키워드 → suspected_titles 강제 승격 차단",
                                file=sys.stderr,
                            )
                            skip_forced_title = True
                        
                        # 🆕 연상글(is_association) + Decoder confidence none/low → 강제승격 차단
                        # Arbiter/Decoder가 모두 작품 매칭을 거부한 연상글에서
                        # suspected_titles만으로 강제승격하면 FP 발생
                        if not skip_forced_title:
                            _is_assoc = getattr(ctx, "is_association_post", False)
                            _dec_overall_conf = str(decoder_out.get("overall_confidence", "")).lower() if decoder_out else ""
                            if _is_assoc and _dec_overall_conf in ("none", "low", ""):
                                print(
                                    f"[{_ts()}][{self.emoji}] 🛡️ 연상글 강제승격 차단: "
                                    f"is_association=True + Decoder confidence={_dec_overall_conf} "
                                    f"→ LLM is_relevant=false 존중",
                                    file=sys.stderr,
                                )
                                skip_forced_title = True
                        
                        if not skip_forced_title:
                            # 🛡️ 강제승격 차단 조건 (FP 방지):
                            # - Verifier grounding이 search_only/none 이면 검색 충돌 가능성이 높음
                            # - Discourse warning이 있는데 본문/댓글 강앵커(캐릭터/줄거리/작가)도 없으면 강제승격 금지
                            _discourse_warn = (getattr(ctx, "discourse_warning", "") or "").strip()
                            _vf_result_guard = (verifier_out.get("verification_result") or {}) if verifier_out else {}
                            _grounding_guard = _vf_result_guard.get("grounding_check") or {}
                            _anchor_guard = str(_grounding_guard.get("anchor_found") or "none").lower()
                            _decoder_grounded_guard = bool(_grounding_guard.get("decoder_grounded", True))
                            _strong_anchors = {
                                "title_mention",
                                "character_mention",
                                "plot_mention",
                                "author_mention",
                            }
                            _warn_lower = _discourse_warn.lower()
                            _is_genre_warn_guard_raw = (
                                "genre_discussion" in _warn_lower
                                or "discuss_genre" in _warn_lower
                            )
                            _is_genre_warn_guard = (
                                _is_genre_warn_guard_raw
                                and self._is_effective_genre_warning(ctx, decoder_out, verifier_out)
                            )
                            _verifier_relevant_guard = (_vf_result_guard.get("is_relevant") is True)
                            _counter_args_guard = _vf_result_guard.get("counter_arguments") or []
                            _has_critical_reject_counter = any(
                                (
                                    str((_ca or {}).get("severity", "")).lower() == "critical"
                                    and str((_ca or {}).get("action", "")).lower() == "reject"
                                )
                                for _ca in _counter_args_guard
                                if isinstance(_ca, dict)
                            )
                            _has_title_anchor = _anchor_guard in ("title_mention", "character_title_link")

                            # 🆕 FIX: Verifier 앵커가 약해도, Decoder 자체에 강한 앵커가 있으면
                            # 강제승격을 허용. Verifier가 작품을 못 찾았지만 Decoder가 확실히 찾은 경우.
                            # 예: "빌환 표지변경됨" — Decoder: title_mention+high, Verifier: none
                            _dec_has_strong_anchor_for_rescue = False
                            if decoder_out:
                                for _dt_rescue in decoder_out.get("decoded_terms", []):
                                    _bm_rescue = _dt_rescue.get("best_match") or {}
                                    _gr_rescue = _dt_rescue.get("grounding") or {}
                                    _a_rescue = str(_gr_rescue.get("anchor_type") or "").lower()
                                    _c_rescue = str(_bm_rescue.get("confidence") or "").lower()
                                    _t_rescue = str(_bm_rescue.get("title") or "").strip()
                                    _support_rescue = bool(
                                        _t_rescue
                                        and self._has_strong_title_support(ctx, _t_rescue)
                                        and (not self._is_platform_branding_title(_t_rescue))
                                    )
                                    if (_a_rescue in ("title_mention", "character_title_link")
                                            and _c_rescue in ("high", "max")
                                            and _support_rescue
                                            and not _dt_rescue.get("is_author_name")):
                                        _dec_has_strong_anchor_for_rescue = True
                                        break

                            if (not _decoder_grounded_guard) or (_anchor_guard in ("search_only", "none")):
                                # 장르 일반론 경고가 유효하면 약한 앵커 상태에서 승격하지 않는다.
                                if _is_genre_warn_guard:
                                    print(
                                        f"[{_ts()}][{self.emoji}] 🛡️ 강제승격 차단(유효 장르경고+앵커약함): "
                                        f"warning='{_discourse_warn}', anchor={_anchor_guard}, "
                                        f"grounded={_decoder_grounded_guard} "
                                        f"→ LLM is_relevant=false 존중",
                                        file=sys.stderr,
                                    )
                                    skip_forced_title = True
                                elif _dec_has_strong_anchor_for_rescue:
                                    # Decoder 자체 앵커가 강함 → Verifier 앵커 무시, 승격 허용
                                    print(
                                        f"[{_ts()}][{self.emoji}] 🔄 강제승격 허용(Decoder 앵커 우선): "
                                        f"Verifier anchor={_anchor_guard}, grounded={_decoder_grounded_guard} "
                                        f"BUT Decoder has title_mention+high → 승격 허용",
                                        file=sys.stderr,
                                    )
                                else:
                                    # 🆕 FIX: snippet_analyzer identified_title이 게시글 제목에 존재하면 승격 허용
                                    # "지구온라인 재밌다며 장붕아" — Decoder 실패해도 snippet_analyzer가 식별
                                    _snippet_rescue = False
                                    _lsa_rescue = getattr(ctx, 'llm_snippet_analysis', None) or {}
                                    _sid_rescue = (_lsa_rescue.get('identified_title') or '').strip()
                                    _sid_cat_rescue = (_lsa_rescue.get('identified_category') or '').lower()
                                    if _sid_rescue and len(_sid_rescue) >= 2:
                                        _post_data_r = getattr(ctx, 'post_data', {}) or {}
                                        _pt_r = (_post_data_r.get('title') or '').replace(' ', '').lower()
                                        _norm_sid_r = _sid_rescue.replace(' ', '').lower()
                                        if _norm_sid_r in _pt_r and _sid_cat_rescue in (
                                            'web_novel', 'novel', 'web_fiction', 'light_novel', '',
                                        ):
                                            _snippet_rescue = True

                                    if _snippet_rescue:
                                        print(
                                            f"[{_ts()}][{self.emoji}] 🔄 강제승격 허용(snippet_analyzer 식별): "
                                            f"identified_title='{_sid_rescue}' 이 게시글 제목에 존재 "
                                            f"→ 승격 허용",
                                            file=sys.stderr,
                                        )
                                    else:
                                        # 🆕 Fix E: Verifier rescue — Verifier가 is_relevant=True이고
                                        # suspected_titles에 Verifier medium+ 제목이 있으면 승격 허용
                                        # (댓글에서 제목을 명시적으로 언급한 패턴 복구)
                                        _verifier_rescue = False
                                        if _verifier_relevant_guard:
                                            for _vr_st in (ctx.suspected_titles or []):
                                                if not isinstance(_vr_st, dict):
                                                    continue
                                                _vr_src = str(
                                                    _vr_st.get("source_expert")
                                                    or _vr_st.get("from")
                                                    or ""
                                                ).lower()
                                                _vr_title = str(
                                                    _vr_st.get("title") or ""
                                                ).strip()
                                                _vr_conf_raw = _vr_st.get(
                                                    "confidence", 0
                                                )
                                                _vr_conf_f = (
                                                    float(_vr_conf_raw)
                                                    if isinstance(
                                                        _vr_conf_raw, (int, float)
                                                    )
                                                    else 0.0
                                                )
                                                if (
                                                    _vr_src
                                                    in (
                                                        "verifier",
                                                        "verifier_grounding",
                                                    )
                                                    and _vr_conf_f >= 0.6
                                                    and _vr_title
                                                ):
                                                    _verifier_rescue = True
                                                    break
                                        if _verifier_rescue:
                                            print(
                                                f"[{_ts()}][{self.emoji}] 🔄 강제승격 허용(Verifier 식별): "
                                                f"Verifier is_relevant=True + "
                                                f"suspected_title(verifier, conf≥0.6) "
                                                f"→ 앵커 약함에도 승격 허용",
                                                file=sys.stderr,
                                            )
                                            # is_relevant을 true로 교정 (Verifier 전문가 판단 존중)
                                            decision["is_relevant"] = True
                                            decision["is_novel_discussion"] = True
                                            _ALWAYS_IRRELEVANT_DT_VR = {
                                                "noise", "off_topic", "meta",
                                                "community_banter", "genre_opinion",
                                                "trope_discussion", "recommendation",
                                                "image_post",
                                            }
                                            _dt_vr = decision.get(
                                                "discussion_type", ""
                                            )
                                            if _dt_vr in _ALWAYS_IRRELEVANT_DT_VR:
                                                decision["discussion_type"] = (
                                                    "general"
                                                )
                                            _upgrade_reason_vr = (
                                                self._synthesize_evidence_reason(
                                                    ctx, "강제승격(Verifier)", True
                                                )
                                            )
                                            decision["final_reasoning"] = (
                                                _upgrade_reason_vr
                                            )
                                            if decision.get("reason"):
                                                decision["reason"] = (
                                                    _upgrade_reason_vr
                                                )
                                            # confidence: Verifier 신뢰도 사용
                                            _vf_result_vr = (
                                                verifier_out.get(
                                                    "verification_result"
                                                )
                                                or {}
                                            ) if verifier_out else {}
                                            _vf_is_rel_vr = _vf_result_vr.get(
                                                "is_relevant", False
                                            )
                                            _vf_conf_vr = (
                                                verifier_out.get(
                                                    "final_confidence", ""
                                                )
                                                if verifier_out
                                                else ""
                                            )
                                            if _vf_is_rel_vr and _vf_conf_vr:
                                                decision["confidence"] = (
                                                    _vf_conf_vr
                                                )
                                            else:
                                                decision["confidence"] = "Medium"
                                        else:
                                            print(
                                                f"[{_ts()}][{self.emoji}] 🛡️ 강제승격 차단(앵커 약함): "
                                                f"anchor={_anchor_guard}, "
                                                f"decoder_grounded="
                                                f"{_decoder_grounded_guard} "
                                                f"→ LLM is_relevant=false 존중",
                                                file=sys.stderr,
                                            )
                                            skip_forced_title = True
                            elif _is_genre_warn_guard and not _has_title_anchor:
                                print(
                                    f"[{_ts()}][{self.emoji}] 🛡️ 강제승격 차단(장르 일반론 경고): "
                                    f"warning='{_discourse_warn}', anchor={_anchor_guard} "
                                    f"→ title_anchor 부재, LLM is_relevant=false 존중",
                                    file=sys.stderr,
                                )
                                skip_forced_title = True
                            elif _discourse_warn and (not _verifier_relevant_guard):
                                print(
                                    f"[{_ts()}][{self.emoji}] 🛡️ 강제승격 차단(Discourse 경고+Verifier 비동의): "
                                    f"warning='{_discourse_warn}', verifier_relevant={_verifier_relevant_guard} "
                                    f"→ LLM is_relevant=false 존중",
                                    file=sys.stderr,
                                )
                                skip_forced_title = True
                            elif _has_critical_reject_counter and not _has_title_anchor:
                                print(
                                    f"[{_ts()}][{self.emoji}] 🛡️ 강제승격 차단(Verifier 반대논거): "
                                    f"critical_reject_counter=True, anchor={_anchor_guard} "
                                    f"→ LLM is_relevant=false 존중",
                                    file=sys.stderr,
                                )
                                skip_forced_title = True
                            elif _discourse_warn and (_anchor_guard not in _strong_anchors):
                                print(
                                    f"[{_ts()}][{self.emoji}] 🛡️ 강제승격 차단(Discourse 경고): "
                                    f"warning='{_discourse_warn}', anchor={_anchor_guard} "
                                    f"→ LLM is_relevant=false 존중",
                                    file=sys.stderr,
                                )
                                skip_forced_title = True
                            else:
                                print(
                                    f"[{_ts()}][{self.emoji}] 🔄 Arbiter 거부 가드 무시: "
                                    f"LLM이 is_relevant=false지만 suspected_titles에 검색 증거 기반 후보 있음 → 강제 승격 허용",
                                    file=sys.stderr,
                                )
                                # is_relevant을 true로 교정
                                decision["is_relevant"] = True
                                decision["is_novel_discussion"] = True
                                # discussion_type이 always_irrelevant_types에 해당하면 general로 교정
                                # (정합성 교정에서 is_relevant=false로 다시 뒤집히는 것 방지)
                                _ALWAYS_IRRELEVANT_DT = {
                                    "noise", "off_topic", "meta", "community_banter",
                                    "genre_opinion", "trope_discussion", "recommendation",
                                    "image_post",
                                }
                                _dt = decision.get("discussion_type", "")
                                if _dt in _ALWAYS_IRRELEVANT_DT:
                                    decision["discussion_type"] = "general"
                                    print(
                                        f"[{_ts()}][{self.emoji}] 🔧 강제 승격 시 discussion_type 교정: "
                                        f"'{_dt}' → 'general'",
                                        file=sys.stderr,
                                    )
                                # 🔧 강제 승격 시 reason/confidence 교정
                                _upgrade_reason = self._synthesize_evidence_reason(ctx, "강제승격", True)

                                decision["final_reasoning"] = _upgrade_reason
                                if decision.get("reason"):
                                    decision["reason"] = _upgrade_reason
                                print(
                                    f"[{_ts()}][{self.emoji}] 🔧 강제 승격 시 reason 교정: 전문가 증거 종합",
                                    file=sys.stderr,
                                )

                                _vf_result = verifier_out.get("verification_result") or {} if verifier_out else {}
                                _verifier_is_relevant = _vf_result.get("is_relevant", False)
                                _verifier_conf = verifier_out.get("final_confidence", "") if verifier_out else ""
                                if _verifier_is_relevant and _verifier_conf:
                                    decision["confidence"] = _verifier_conf
                                elif not _verifier_is_relevant:
                                    # Verifier도 false인데 강제승격 → confidence는 Medium으로 설정
                                    decision["confidence"] = "Medium"
                                if decision.get("confidence"):
                                    print(
                                        f"[{_ts()}][{self.emoji}] 🔧 강제 승격 시 confidence 교정: → {decision['confidence']}",
                                        file=sys.stderr,
                                    )
                    else:
                        print(
                            f"[{_ts()}][{self.emoji}] 🛡️ Arbiter 거부 가드: "
                            f"LLM이 is_relevant=false 판단 → suspected_titles 강제 승격 스킵",
                            file=sys.stderr,
                        )
                        skip_forced_title = True
            
            # 🛡️ 아이디어 H: Decoder가 식별한 작가명 목록 수집
            # suspected_titles 강제 적용 시 작가명과 일치하는 제목 차단
            decoder_author_names = set()
            # 🛡️ Fix C: 작가명 원본 텀 추적 → 작가 term에서 파생된 suspected_title 차단
            decoder_author_originals = set()  # 작가로 식별된 term의 original 값
            decoder_out_raw = ctx.expert_outputs.get("decoder") or {} if hasattr(ctx, 'expert_outputs') else {}
            for term in decoder_out_raw.get("decoded_terms", []):
                if term.get("is_author_name"):
                    # author_info.name 또는 original 추출
                    author_info = term.get("author_info") or {}
                    if author_info.get("name"):
                        decoder_author_names.add(author_info["name"])
                    if term.get("original"):
                        decoder_author_names.add(term["original"])
                        decoder_author_originals.add(term["original"])
            
            if ctx.suspected_titles and len(ctx.suspected_titles) > 0 and not skip_forced_title:
                # confidence를 숫자로 변환하는 헬퍼 함수
                def conf_to_num(conf_val):
                    """confidence 값을 통일된 스케일(0~3)로 변환
                    
                    - 문자열: "high"=3, "medium"=2, "low"=1, "none"=0
                    - 실수(0.0~1.0): 0.7+ → 3(high), 0.5~0.7 → 2(medium), 0.3~0.5 → 1(low), <0.3 → 0
                    """
                    if isinstance(conf_val, (int, float)):
                        v = float(conf_val)
                        if v >= 0.7:
                            return 3  # high
                        elif v >= 0.5:
                            return 2  # medium
                        elif v >= 0.3:
                            return 1  # low
                        else:
                            return 0
                    elif isinstance(conf_val, str):
                        conf_map = {"high": 3, "medium": 2, "low": 1, "none": 0}
                        return conf_map.get(str(conf_val).lower(), 0)
                    else:
                        return 0
                
                def _norm_title_local(v: Any) -> str:
                    return re.sub(r"\s+", "", str(v or "")).lower()

                _post_title_for_domain = str((getattr(ctx, "post_data", {}) or {}).get("title") or "")

                # Decoder/Verifier 타이틀 집합 (Arbiter-LLM 단독 후보 필터용)
                _decoder_title_norms: Set[str] = set()
                _overall_bm_local = decoder_out_raw.get("overall_best_match") or {}
                if isinstance(_overall_bm_local, dict) and _overall_bm_local.get("title"):
                    _decoder_title_norms.add(_norm_title_local(_overall_bm_local.get("title")))
                for _term_local in decoder_out_raw.get("decoded_terms", []):
                    if not isinstance(_term_local, dict):
                        continue
                    if _term_local.get("is_author_name"):
                        continue
                    _bm_local = _term_local.get("best_match") or {}
                    _t_local = _bm_local.get("title")
                    if _t_local:
                        _decoder_title_norms.add(_norm_title_local(_t_local))

                _verifier_title_norms: Set[str] = set()
                _vf_result_local = (verifier_out or {}).get("verification_result") or {}
                _vf_title_lock = ""
                _vf_conf_lock_num = 0
                if isinstance(_vf_result_local, dict):
                    _vn_local = _vf_result_local.get("novel_identity") or {}
                    if isinstance(_vn_local, dict):
                        for _k_local in ("official_novel_title", "official_title", "title"):
                            _v_local = _vn_local.get(_k_local)
                            if _v_local:
                                _verifier_title_norms.add(_norm_title_local(_v_local))
                        _vf_title_lock = str(
                            _vn_local.get("official_novel_title")
                            or _vn_local.get("official_title")
                            or ""
                        ).strip()
                        _vf_conf_lock_num = conf_to_num(
                            _vn_local.get("confidence")
                            or _vf_result_local.get("final_confidence")
                            or verifier_out.get("final_confidence")
                            or ""
                        )
                    for _k_local in ("verified_title", "title"):
                        _v_local = _vf_result_local.get(_k_local)
                        if _v_local:
                            _verifier_title_norms.add(_norm_title_local(_v_local))

                # 🛡️ 작가명 + Arbiter-LLM 무증거 후보 필터링
                filtered_titles: List[Dict[str, Any]] = []
                _effective_genre_warn_filter = self._is_effective_genre_warning(
                    ctx, decoder_out_raw, verifier_out
                )
                _post_text_for_fragment = " ".join(
                    [
                        str((getattr(ctx, "post_data", {}) or {}).get("title") or ""),
                        " ".join(
                            str((b or {}).get("text") or "")
                            for b in ((getattr(ctx, "post_data", {}) or {}).get("content_blocks") or [])
                            if isinstance(b, dict)
                        ),
                    ]
                )
                _particle_suffixes = (
                    "가", "이", "은", "는", "을", "를", "에", "도",
                    "로", "으로", "만", "부터", "까지", "처럼", "같",
                    "네", "다", "냐", "임", "듯",
                )

                def _is_weak_fragment_title(_title: Any) -> bool:
                    """
                    짧은 단일어가 문장 파편으로 쓰인 경우를 약한 제목 후보로 본다.
                    - 하드코딩 작품명 없이 길이/문장 형태 기반만 사용
                    """
                    _t = str(_title or "").strip()
                    if not _t:
                        return False
                    _norm_t = _norm_title_local(_t)
                    if len(_norm_t) == 0 or len(_norm_t) > 3:
                        return False
                    _tokens = re.findall(r"[가-힣A-Za-z0-9]+", _t)
                    if len(_tokens) != 1:
                        return False
                    _tok = _tokens[0]
                    # 조사/어미가 바로 붙는 형태면 문장 성분일 가능성이 높다.
                    if any(f"{_tok}{_sfx}" in _post_text_for_fragment for _sfx in _particle_suffixes):
                        return True
                    return False

                for st in (ctx.suspected_titles or []):
                    if not isinstance(st, dict):
                        continue
                    _st_title = st.get("title")
                    if not _st_title:
                        continue
                    if self._is_platform_branding_title(str(_st_title)):
                        continue
                    if _st_title in decoder_author_names:
                        continue
                    # 🛡️ Fix C: 작가 term에서 파생된 suspected_title 차단
                    # source_term이 작가명 원본과 일치하면 작가→대표작 역매핑이므로 차단
                    _st_source_term = str(st.get("source_term") or "").strip()
                    if _st_source_term and _st_source_term in decoder_author_originals:
                        print(
                            f"[{_ts()}][{self.emoji}] 🚫 suspected_titles 필터: 작가 term 파생 "
                            f"(title='{_st_title}', source_term='{_st_source_term}', "
                            f"author_originals={decoder_author_originals})",
                            file=sys.stderr,
                        )
                        continue
                    if _post_title_for_domain and _has_domain_conflict_for_mapping(_post_title_for_domain, _st_title):
                        print(
                            f"[{_ts()}][{self.emoji}] 🚫 suspected_titles 필터: 도메인 충돌 "
                            f"(title='{_st_title}', post_title='{_post_title_for_domain[:40]}...')",
                            file=sys.stderr,
                        )
                        continue
                    _st_direct_anchor = self._title_directly_in_post(ctx, _st_title)
                    _st_decoder_align = self._has_decoder_alignment_support(
                        decoder_out_raw, _st_title, min_score=0.45
                    )
                    _st_strong_support = self._has_strong_title_support(ctx, _st_title)
                    _st_character_parenthetical_support = any(
                        isinstance(_v, dict)
                        and not bool(_v.get("_weak_match"))
                        and _norm_title_local(_v.get("title")) == _norm_title_local(_st_title)
                        and str(_v.get("source") or "") == "character_parenthetical_wiki"
                        for _v in (getattr(ctx, "verified_character_work_links", []) or [])
                    )
                    if _is_weak_fragment_title(_st_title) and (not _st_strong_support):
                        print(
                            f"[{_ts()}][{self.emoji}] 🚫 suspected_titles 필터: 단일어 파편 "
                            f"(title='{_st_title}', strong={_st_strong_support})",
                            file=sys.stderr,
                        )
                        continue
                    _src = str(st.get("source_expert") or st.get("from") or "").lower()
                    if self._curated_alias_lacks_contextual_work_anchor(
                        ctx,
                        _st_title,
                        verifier_out=verifier_out,
                    ):
                        print(
                            f"[{_ts()}][{self.emoji}] 🚫 suspected_titles 필터: "
                            f"curated alias lacks contextual work anchor "
                            f"(title='{_st_title}', src={_src})",
                            file=sys.stderr,
                        )
                        continue

                    # 검색 표면 증거만으로 후보 승격하지 않도록,
                    # 본문 직앵커/디코더 정합/강한 title support 중 하나는 필수
                    # 🆕 FIX-6: Verifier High confidence 제목은 앵커 부재여도 유지
                    _st_conf_val = conf_to_num(st.get("confidence", 0))
                    _st_from_verifier = _src in {"verifier", "verifier_grounding"}
                    _st_has_evidence_bucket = False
                    if hasattr(ctx, "get_candidate_evidence"):
                        _st_eb = ctx.get_candidate_evidence(_st_title) or {}
                        _st_eb_score = (
                            len(_st_eb.get("post_spans", [])) * 2
                            + len(_st_eb.get("search_snippets", []))
                            + len(_st_eb.get("official_urls", [])) * 3
                        )
                        _st_has_evidence_bucket = _st_eb_score >= 3
                    if not (_st_direct_anchor or _st_decoder_align or _st_strong_support or _st_character_parenthetical_support):
                        if _st_from_verifier and (_st_conf_val >= 3 or _st_has_evidence_bucket):
                            print(
                                f"[{_ts()}][{self.emoji}] ✅ suspected_titles 필터: 앵커 부재지만 "
                                f"Verifier 고신뢰로 유지 "
                                f"(title='{_st_title}', conf={_st_conf_val}, from={_src}, "
                                f"ev_bucket={_st_has_evidence_bucket})",
                                file=sys.stderr,
                            )
                        else:
                            print(
                                f"[{_ts()}][{self.emoji}] 🚫 suspected_titles 필터: 앵커 부재 "
                                f"(title='{_st_title}', direct={_st_direct_anchor}, "
                                f"decoder_align={_st_decoder_align}, strong={_st_strong_support})",
                                file=sys.stderr,
                            )
                            continue
                    # Arbiter/Decoder가 만든 약한 후보가 decoder_align만으로 되살아나는 경우 차단
                    if (
                        _src in {"arbiter", "arbiter_llm", "decoder", "decoder_multi_interp"}
                        and _st_decoder_align
                        and (not _st_direct_anchor)
                        and (not _st_strong_support)
                    ):
                        print(
                            f"[{_ts()}][{self.emoji}] 🚫 suspected_titles 필터: "
                            f"weak decoder-align only "
                            f"(title='{_st_title}', src={_src})",
                            file=sys.stderr,
                        )
                        continue
                    # 장르 일반론 경고가 유효하면 간접근거만으로 승격 금지
                    if (
                        _effective_genre_warn_filter
                        and (not _st_direct_anchor)
                        and (not (_st_decoder_align and _st_strong_support))
                    ):
                        print(
                            f"[{_ts()}][{self.emoji}] 🚫 suspected_titles 필터: 유효 장르경고+약한근거 "
                            f"(title='{_st_title}', decoder_align={_st_decoder_align}, strong={_st_strong_support})",
                            file=sys.stderr,
                        )
                        continue
                    if _src == "arbiter_llm":
                        _bucket = ctx.get_candidate_evidence(_st_title) if hasattr(ctx, "get_candidate_evidence") else {}
                        _post_cnt = len((_bucket or {}).get("post_spans", []))
                        _official_cnt = len((_bucket or {}).get("official_urls", []))
                        _title_norm = _norm_title_local(_st_title)
                        _supported = (
                            _title_norm in _decoder_title_norms
                            or _title_norm in _verifier_title_norms
                            or _post_cnt > 0
                            or _official_cnt > 0
                        )
                        if not _supported:
                            continue
                    filtered_titles.append(st)
                if len(filtered_titles) < len(ctx.suspected_titles):
                    removed = len(ctx.suspected_titles) - len(filtered_titles)
                    print(
                        f"[{_ts()}][{self.emoji}] 🛡️ 작가명 필터: "
                        f"suspected_titles에서 작가명 {removed}건 제거 "
                        f"(작가명: {decoder_author_names})",
                        file=sys.stderr,
                    )
                
                if not filtered_titles:
                    # 모두 작가명이면 강제 적용 스킵
                    skip_forced_title = True

                def _looks_post_reaction_title(_title: Any) -> bool:
                    _raw_t = str(_title or "").strip()
                    _post_raw = str((getattr(ctx, "post_data", {}) or {}).get("title") or "").strip()
                    if not _raw_t or not _post_raw:
                        return False
                    if _norm_title_local(_raw_t) != _norm_title_local(_post_raw):
                        return False
                    _tokens = re.findall(r"[가-힣A-Za-z0-9]+", _raw_t)
                    if len(_tokens) <= 1:
                        return False
                    _tail = _raw_t.split(" ", 1)[1].strip() if " " in _raw_t else ""
                    if not _tail:
                        return False
                    return bool(
                        re.search(r"[?!…\.]{1,}\s*$", _raw_t)
                        or re.search(r"(냐|네|인가|같음|같네|왜이러|뭐다이|불쌍해|재밌네)", _tail)
                    )

                # Arbiter LLM이 이미 낸 official title이 강한 증거(약칭/공식 상세 URL)로
                # 지지되는 경우, suspected confidence 역전으로 덮어쓰지 않도록 보호.
                preferred_title = str(
                    decision.get("official_novel_title") or decision.get("official_title") or ""
                ).strip()
                if (
                    not skip_forced_title
                    and preferred_title
                    and (not self._is_platform_branding_title(preferred_title))
                    and self._has_strong_title_support(ctx, preferred_title)
                    and not self._curated_alias_lacks_contextual_work_anchor(
                        ctx,
                        preferred_title,
                        verifier_out=verifier_out,
                    )
                ):
                    preferred_norm = _norm_title_local(preferred_title)
                    if all(
                        _norm_title_local(item.get("title")) != preferred_norm
                        for item in filtered_titles
                        if isinstance(item, dict)
                    ):
                        filtered_titles.append(
                            {
                                "title": preferred_title,
                                "confidence": 0.99,
                                "source_expert": "arbiter_supported_title",
                            }
                        )
                    print(
                        f"[{_ts()}][{self.emoji}] 🧩 Arbiter 공식제목 보호 후보 추가: "
                        f"'{preferred_title}' (약칭/상세URL 근거)",
                        file=sys.stderr,
                    )
                
                def _bucket_score_for_title(_title: Any) -> int:
                    if not _title or not hasattr(ctx, "get_candidate_evidence"):
                        return 0
                    try:
                        _bucket = ctx.get_candidate_evidence(_title) or {}
                    except Exception:
                        return 0
                    if not isinstance(_bucket, dict):
                        return 0
                    _post_cnt = len((_bucket.get("post_spans") or []))
                    _snippet_cnt = len((_bucket.get("search_snippets") or []))
                    _official_cnt = len((_bucket.get("official_urls") or []))
                    return (_post_cnt * 2) + _snippet_cnt + (_official_cnt * 3)

                # 가장 높은 후보 선택: confidence 단독이 아니라 forced-upgrade score 우선
                best_eval: Optional[Dict[str, Any]] = None
                if not skip_forced_title:
                    _scored_candidates: List[tuple[Dict[str, Any], Dict[str, Any]]] = []
                    for _cand in filtered_titles:
                        _cand_title = _cand.get("title")
                        _eval = _score_forced_upgrade(
                            candidate_title=_cand_title,
                            candidate_conf=_cand.get("confidence"),
                            decoder_out_local=decoder_out_raw,
                            verifier_out_local=verifier_out or {},
                        )
                        _scored_candidates.append((_cand, _eval))
                    _scored_candidates.sort(
                        key=lambda x: (
                            float((x[1] or {}).get("score", 0.0)),
                            conf_to_num((x[0] or {}).get("confidence", 0)),
                            _bucket_score_for_title((x[0] or {}).get("title")),
                        ),
                        reverse=True,
                    )
                    if _scored_candidates:
                        best, best_eval = _scored_candidates[0]
                        decision["_forced_upgrade_best_score"] = float(best_eval.get("score", 0.0))
                        decision["_forced_upgrade_best_title"] = best.get("title")
                    else:
                        best = None
                else:
                    best = None
                best_conf_num = conf_to_num(best.get("confidence", 0)) if best else 0

                if best and best_eval and not bool(best_eval.get("allowed")):
                    print(
                        f"[{_ts()}][{self.emoji}] 🛡️ suspected best 후보 점수 미달: "
                        f"title='{best.get('title')}', score={best_eval.get('score', 0.0):.3f} "
                        f"< {best_eval.get('threshold', 0.62):.3f}",
                        file=sys.stderr,
                    )
                    print(
                        f"[{_ts()}][{self.emoji}]    └ score_breakdown: "
                        f"{', '.join((best_eval.get('reasons') or [])[:8])}",
                        file=sys.stderr,
                    )
                    best = None
                    best_conf_num = 0
                
                # high나 medium이면 강제 적용 (숫자 2 이상)
                if best_conf_num >= 2:  # medium 이상
                    best_title = best.get("title") if best else None
                    _vf_bucket_score = _bucket_score_for_title(_vf_title_lock)
                    _best_bucket_score = _bucket_score_for_title(best_title)
                    _vf_lock_supported_any = bool(
                        (
                            _vf_title_lock
                            and self._has_strong_title_support(ctx, _vf_title_lock)
                        )
                        or (
                            _vf_title_lock
                            and _vf_conf_lock_num >= 2
                            and _vf_bucket_score >= 2
                        )
                    )
                    _vf_lock_supported = bool(
                        _vf_title_lock
                        and _vf_conf_lock_num >= 2
                        and (
                            self._has_strong_title_support(ctx, _vf_title_lock)
                            or _vf_bucket_score >= 3
                        )
                    )
                    if (
                        best_title
                        and _vf_title_lock
                        and _norm_title_local(best_title) != _norm_title_local(_vf_title_lock)
                        and _vf_conf_lock_num >= 2
                        and _vf_bucket_score >= max(2, _best_bucket_score + 1)
                        and not self._has_strong_title_support(ctx, best_title)
                    ):
                        print(
                            f"[{_ts()}][{self.emoji}] 🛡️ verifier evidence bucket 우선: "
                            f"best='{best_title}'({_best_bucket_score}) -> verifier='{_vf_title_lock}'({_vf_bucket_score})",
                            file=sys.stderr,
                        )
                        best_title = _vf_title_lock
                        _best_bucket_score = _vf_bucket_score
                    if (
                        best_title
                        and _vf_lock_supported
                        and _norm_title_local(best_title) != _norm_title_local(_vf_title_lock)
                        and (not self._has_strong_title_support(ctx, best_title))
                    ):
                        print(
                            f"[{_ts()}][{self.emoji}] 🛡️ forced-title 충돌 방지: "
                            f"weak best='{best_title}' < verifier_locked='{_vf_title_lock}' "
                            f"(best_conf={best.get('confidence')}, vf_conf={_vf_conf_lock_num})",
                            file=sys.stderr,
                        )
                        best_title = _vf_title_lock
                    # 단일어 파편 후보가 Verifier의 고신뢰 긴 제목을 덮어쓰는 현상 방지
                    if (
                        best_title
                        and _vf_title_lock
                        and _vf_conf_lock_num >= 2
                        and _norm_title_local(best_title) != _norm_title_local(_vf_title_lock)
                        and _is_weak_fragment_title(best_title)
                        and len(_norm_title_local(_vf_title_lock)) >= len(_norm_title_local(best_title)) + 2
                    ):
                        print(
                            f"[{_ts()}][{self.emoji}] 🛡️ 단일어 파편 덮어쓰기 차단: "
                            f"best='{best_title}' → verifier='{_vf_title_lock}'",
                            file=sys.stderr,
                        )
                        best_title = _vf_title_lock
                    # Verifier confidence가 Low여도, Verifier 제목에 강한 증거가 있고
                    # 현재 best가 약한 후보(본문 직앵커/디코더 정합 부족)면 Verifier 제목 우선.
                    if best_title:
                        _best_supported = bool(self._has_strong_title_support(ctx, best_title))
                        _best_direct_anchor = bool(self._title_directly_in_post(ctx, best_title))
                        _best_decoder_align = bool(
                            self._has_decoder_alignment_support(
                                decoder_out_raw, best_title, min_score=0.45
                            )
                        )
                        if (
                            _vf_lock_supported_any
                            and _norm_title_local(best_title) != _norm_title_local(_vf_title_lock)
                            and (
                                (not _best_supported)
                                or (not (_best_direct_anchor or _best_decoder_align))
                            )
                        ):
                            print(
                                f"[{_ts()}][{self.emoji}] 🛡️ verifier-title 드리프트 보정: "
                                f"best='{best_title}' → verifier='{_vf_title_lock}' "
                                f"(vf_conf={_vf_conf_lock_num}, best_supported={_best_supported}, "
                                f"best_anchor={_best_direct_anchor}, best_align={_best_decoder_align})",
                                file=sys.stderr,
                            )
                            best_title = _vf_title_lock

                    _direct_image_guard_title = self._direct_image_forced_title_guard(
                        ctx,
                        best_title,
                        decoder_out_raw,
                        verifier_out or {},
                    )
                    if _direct_image_guard_title:
                        print(
                            f"[{_ts()}][{self.emoji}] 🖼️ direct-image forced-title guard: "
                            f"best='{best_title}' → image_title='{_direct_image_guard_title}'",
                            file=sys.stderr,
                        )
                        best_title = _direct_image_guard_title
                        best = dict(best or {})
                        best["title"] = best_title
                        best["confidence"] = best.get("confidence") or "High"
                        best["source_expert"] = "direct_image_ocr_catalog"

                    # 🔧 검색 결과에서 정확한 제목 찾기 (title 필드 + content 직접 비교)
                    if best_title and ctx.search_results:
                        corrected_title = self._correct_title_from_search(best_title, ctx.search_results)
                        if corrected_title != best_title:
                            print(
                                f"[{_ts()}][{self.emoji}] ⚠️ 검색 결과와 제목 불일치 감지: "
                                f"LLM='{best_title}' vs 검색='{corrected_title}' → 검색 결과 우선",
                                file=sys.stderr
                            )
                            best_title = corrected_title

                    if (
                        best_title
                        and preferred_title
                        and _norm_title_local(best_title) != _norm_title_local(preferred_title)
                        and _looks_post_reaction_title(best_title)
                        and self._has_strong_title_support(ctx, preferred_title)
                    ):
                        print(
                            f"[{_ts()}][{self.emoji}] 🛡️ post 반응형 제목 강제적용 차단: "
                            f"best='{best_title}' → preferred='{preferred_title}'",
                            file=sys.stderr,
                        )
                        best_title = preferred_title

                    if best_title:
                        _best_char_like = self._is_character_like_short_title(
                            ctx,
                            best_title,
                            decoder_out_raw,
                            verifier_out,
                        )
                        _best_non_char_anchor = self._has_non_character_anchor_support(
                            best_title,
                            decoder_out_raw,
                            verifier_out,
                        )
                        _best_hard_support = bool(self._has_strong_title_support(ctx, best_title))
                        if _best_char_like and not (_best_hard_support and _best_non_char_anchor):
                            print(
                                f"[{_ts()}][{self.emoji}] 🚫 suspected_titles 강제적용 차단: "
                                f"character-like short title '{best_title}' "
                                f"(hard={_best_hard_support}, non_char_anchor={_best_non_char_anchor})",
                                file=sys.stderr,
                            )
                            best_title = None
                    
                    # 🆕 포스트 제목 꺾쇠 표기 우선: <정식제목> 패턴이 있으면 강제 우선
                    # 예: "<마법으로 딸깍하니 전설의 마법사> ㅊㅊ함" → 꺾쇠 안 제목이 확정적
                    import re as _re_bracket
                    _post_title_for_bracket = str(
                        (getattr(ctx, "post_data", {}) or {}).get("title") or ""
                    )
                    _bracket_m2 = _re_bracket.search(
                        r'[<《「『【]([\w가-힣\s]{2,})[>》」』】]',
                        _post_title_for_bracket,
                    )
                    if _bracket_m2:
                        _bracket_title2 = _bracket_m2.group(1).strip()
                        _bracket_norm2 = _norm_title_local(_bracket_title2)
                        _best_norm2 = _norm_title_local(best_title) if best_title else ""
                        if _bracket_norm2 and _bracket_norm2 != _best_norm2:
                            # 꺾쇠 제목이 suspected_titles에 있는지 확인
                            _bracket_in_suspected = any(
                                _norm_title_local(st.get("title")) == _bracket_norm2
                                for st in (ctx.suspected_titles or [])
                                if isinstance(st, dict)
                            )
                            # 꺾쇠 제목이 검색 결과에 있는지 확인
                            _bracket_in_search = False
                            for _sr in (getattr(ctx, "search_results", []) or []):
                                _sr_blob = (
                                    str((_sr or {}).get("title") or "")
                                    + " "
                                    + str((_sr or {}).get("content") or "")
                                ).replace(" ", "").lower()
                                if _bracket_norm2.replace(" ", "").lower() in _sr_blob:
                                    _bracket_in_search = True
                                    break
                            if _bracket_in_suspected or _bracket_in_search:
                                print(
                                    f"[{_ts()}][{self.emoji}] 📐 포스트 제목 꺾쇠 표기 우선: "
                                    f"'{best_title}' → '{_bracket_title2}' "
                                    f"(in_suspected={_bracket_in_suspected}, in_search={_bracket_in_search})",
                                    file=sys.stderr,
                                )
                                best_title = _bracket_title2

                    if best_title and best_title != decision.get("official_title"):
                        print(
                            f"[{_ts()}][{self.emoji}] 🔧 suspected_titles에서 최고 신뢰도 제목 강제 적용: "
                            f"{decision.get('official_title')} → {best_title} (conf={best.get('confidence')})",
                            file=sys.stderr
                        )
                        decision["official_title"] = best_title
                        # heretic_url도 업데이트
                        if best.get("url"):
                            decision["heretic_url"] = best.get("url")
                        # discussion_type이 noise·irrelevant 계열이면 general로 교정
                        _ALWAYS_IRRELEVANT_DT2 = {
                            "noise", "off_topic", "meta", "community_banter",
                            "genre_opinion", "trope_discussion", "recommendation",
                            "image_post",
                        }
                        _dt2 = decision.get("discussion_type", "")
                        if _dt2 in _ALWAYS_IRRELEVANT_DT2:
                            decision["discussion_type"] = "general"
                            print(
                                f"[{_ts()}][{self.emoji}] 🔧 suspected_titles 적용 시 discussion_type 교정: "
                                f"'{_dt2}' → 'general'",
                                file=sys.stderr
                            )
            
            _post_title_for_domain2 = str((getattr(ctx, "post_data", {}) or {}).get("title") or "")

            # � Arbiter LLM 응답의 official_title도 검색 결과로 교정
            for title_key in ("official_title", "official_novel_title"):
                arbiter_llm_title = decision.get(title_key)
                if (
                    arbiter_llm_title
                    and _post_title_for_domain2
                    and _has_domain_conflict_for_mapping(_post_title_for_domain2, arbiter_llm_title)
                ):
                    print(
                        f"[{_ts()}][{self.emoji}] 🚫 Arbiter 제목 차단: 도메인 충돌 "
                        f"('{arbiter_llm_title}' vs post_title)",
                        file=sys.stderr,
                    )
                    decision[title_key] = None
                    continue
                if (
                    arbiter_llm_title
                    and self._curated_alias_lacks_contextual_work_anchor(
                        ctx,
                        arbiter_llm_title,
                        verifier_out=verifier_out,
                    )
                ):
                    print(
                        f"[{_ts()}][{self.emoji}] 🚫 Arbiter 제목 차단: "
                        f"curated alias lacks contextual work anchor "
                        f"('{arbiter_llm_title}')",
                        file=sys.stderr,
                    )
                    decision[title_key] = None
                    _null_reasons = decision.get("_title_null_block_reasons")
                    if not isinstance(_null_reasons, list):
                        _null_reasons = []
                    _null_reasons.append("curated_alias_missing_contextual_work_anchor")
                    decision["_title_null_block_reasons"] = sorted(set(_null_reasons))
                    continue
                if arbiter_llm_title and ctx.search_results:
                    corrected = self._correct_title_from_search(arbiter_llm_title, ctx.search_results)
                    if (
                        corrected
                        and _post_title_for_domain2
                        and _has_domain_conflict_for_mapping(_post_title_for_domain2, corrected)
                    ):
                        print(
                            f"[{_ts()}][{self.emoji}] 🚫 Arbiter 제목 교정 차단: "
                            f"검색 교정값 도메인 충돌 ('{arbiter_llm_title}' → '{corrected}')",
                            file=sys.stderr,
                        )
                        decision[title_key] = None
                        continue
                    if corrected != arbiter_llm_title:
                        print(
                            f"[{_ts()}][{self.emoji}] ⚠️ Arbiter 제목 교정: '{arbiter_llm_title}' → '{corrected}'",
                            file=sys.stderr
                        )
                        decision[title_key] = corrected
            
            # 🛡️ 아이디어 H-2: Arbiter LLM이 official_title에 작가명을 직접 넣은 경우 null로 교정
            if decoder_author_names:
                for title_key in ("official_title", "official_novel_title"):
                    final_title = decision.get(title_key)
                    if final_title and final_title in decoder_author_names:
                        print(
                            f"[{_ts()}][{self.emoji}] 🛡️ 작가명→제목 차단: "
                            f"'{final_title}'은 Decoder가 작가명으로 식별 → official_title=null",
                            file=sys.stderr,
                        )
                        decision[title_key] = None
            
            # 🆕 BUG-B 최종 방어: official_title에 사이트명/게시판 접두어가 포함되어 있으면 정제
            for title_key in ("official_title", "official_novel_title"):
                final_title = decision.get(title_key)
                if not final_title:
                    continue
                cleaned = self._sanitize_site_noise_title(final_title)
                if cleaned != final_title and 3 <= len(cleaned) <= 80:
                    print(
                        f"[{_ts()}][{self.emoji}] 🛡️ 사이트명 오염 정제: "
                        f"'{final_title}' → '{cleaned}'",
                        file=sys.stderr,
                    )
                    decision[title_key] = cleaned
            
            # 🚨 P0-1: Verifier 거부권 강제 적용 (LLM이 무시했을 경우 대비)
            # 🆕 예외: 제목에 검증된 약칭 + 본문에 검증된 작가명이 동시 존재하면 거부권 면제
            #    (팬 응원/기원글 패턴: "죽깨수 올 때 됐다" + "가자 돌마늘!")
            if verifier_out:
                vf_result = verifier_out.get("verification_result") or {}
                if vf_result.get("is_relevant") == False:
                    # 약칭+작가명 동시 존재 확인
                    _veto_exempt = False
                    _relation_guard_blocks_loose_veto = False
                    _genre_warning_effective = self._is_effective_genre_warning(
                        ctx, decoder_out, verifier_out
                    )
                    _vf_verification_error = bool(vf_result.get("verification_error"))
                    if not _vf_verification_error:
                        _vf_error_blob = " ".join(
                            str(raw or "")
                            for raw in (
                                vf_result.get("rejection_reason"),
                                vf_result.get("reason"),
                                vf_result.get("reasoning"),
                            )
                            if str(raw or "").strip()
                        ).lower()
                        _vf_verification_error = any(
                            marker in _vf_error_blob
                            for marker in (
                                "verifier 검증 오류",
                                "검증 오류로 인한 폴백",
                                "empty verifier response",
                                "verifier truncated",
                            )
                        )
                    def _norm_veto_text(v: Any) -> str:
                        return re.sub(r"[^\w가-힣]", "", str(v or "")).lower()

                    _decoder_title_norms: Set[str] = set()
                    if isinstance(decoder_out, dict):
                        _ov_veto = decoder_out.get("overall_best_match") or {}
                        if isinstance(_ov_veto, dict) and _ov_veto.get("title"):
                            _decoder_title_norms.add(_norm_veto_text(_ov_veto.get("title")))
                        for _dt_veto_norm in decoder_out.get("decoded_terms", []) or []:
                            if not isinstance(_dt_veto_norm, dict):
                                continue
                            _bm_veto_norm = _dt_veto_norm.get("best_match") or {}
                            if isinstance(_bm_veto_norm, dict) and _bm_veto_norm.get("title"):
                                _decoder_title_norms.add(_norm_veto_text(_bm_veto_norm.get("title")))

                    _suspected_title_norms: Set[str] = set(
                        _norm_veto_text(st.get("title"))
                        for st in (getattr(ctx, "suspected_titles", []) or [])
                        if isinstance(st, dict) and st.get("title")
                    )

                    def _has_hard_candidate_support(_candidate_title: str) -> bool:
                        _cand_norm = _norm_veto_text(_candidate_title)
                        if not _cand_norm:
                            return False
                        if self._is_platform_branding_title(str(_candidate_title or "")):
                            return False

                        _bucket = {}
                        if hasattr(ctx, "get_candidate_evidence"):
                            try:
                                _bucket = ctx.get_candidate_evidence(_candidate_title) or {}
                            except Exception:
                                _bucket = {}
                        _official_cnt = len((_bucket or {}).get("official_urls", []))
                        _post_cnt = len((_bucket or {}).get("post_spans", []))
                        _search_cnt = len((_bucket or {}).get("search_snippets", []))
                        _has_direct_anchor = self._title_directly_in_post(ctx, _candidate_title)
                        _has_decoder_align = self._has_decoder_alignment_support(
                            decoder_out, _candidate_title, min_score=0.45
                        )
                        _has_strong_support = self._has_strong_title_support(ctx, _candidate_title)

                        # 제목 직등장/디코더 정합성 둘 다 없는 후보는 검색 증거만으로 채택 금지
                        if not (_has_direct_anchor or _has_decoder_align):
                            return False

                        # genre 경고가 유효하면 약칭/간접근거만으로 거부권 면제 금지
                        if (
                            _genre_warning_effective
                            and not _has_direct_anchor
                            and not (_has_decoder_align and _has_strong_support)
                        ):
                            return False

                        if _official_cnt > 0 and (_has_direct_anchor or _has_decoder_align):
                            return True
                        if (
                            (_cand_norm in _decoder_title_norms or _cand_norm in _suspected_title_norms)
                            and (_post_cnt > 0 or _search_cnt > 0)
                            and (_has_direct_anchor or _has_decoder_align)
                        ):
                            return True

                        _has_official_detail_match = False
                        for _sr in (getattr(ctx, "search_results", None) or []):
                            if not isinstance(_sr, dict):
                                continue
                            _sr_url = str(_sr.get("url") or "")
                            if not any(p in _sr_url for p in OFFICIAL_PLATFORMS):
                                continue
                            if not self._is_novel_detail_url(_sr_url):
                                continue
                            _sr_text = _norm_veto_text(f"{_sr.get('title', '')} {_sr.get('content', '')}")
                            if _cand_norm and _cand_norm in _sr_text:
                                _has_official_detail_match = True
                                break

                        return bool(_has_official_detail_match and (_has_direct_anchor or _has_decoder_align))

                    def _clean_assignable_title(_candidate_title: str, require_hard_support: bool = False) -> str:
                        """공식 제목으로 저장 가능한 문자열만 통과시킨다."""
                        _raw_title = str(_candidate_title or "").strip()
                        if not _raw_title:
                            return ""
                        _clean_title = str(self._sanitize_site_noise_title(_raw_title) or "").strip()
                        if not _clean_title:
                            return ""
                        if self._is_platform_branding_title(_clean_title):
                            return ""

                        _hard_support = _has_hard_candidate_support(_clean_title)
                        if require_hard_support and not _hard_support:
                            return ""

                        _suspicious_tokens = ("=", "갤러리", "채널", "포텐", "독후감")
                        if any(tok in _clean_title for tok in _suspicious_tokens) and not _hard_support:
                            return ""

                        return _clean_title

                    def _is_ambiguous_abbrev_context(_abbr_raw: str, _candidate_title: str) -> bool:
                        """약칭이 일반 문맥에 과도하게 퍼져 있고 후보 제목과 결속이 약한지 판정."""
                        _abbr_norm = _norm_veto_text(_abbr_raw)
                        _cand_norm = _norm_veto_text(_candidate_title)
                        if not _abbr_norm or len(_abbr_norm) < 2 or not _cand_norm:
                            return False

                        total = 0
                        linked = 0
                        official_linked = 0

                        for _sr in (getattr(ctx, "search_results", None) or [])[:120]:
                            if not isinstance(_sr, dict):
                                continue
                            _sr_text = _norm_veto_text(f"{_sr.get('title', '')} {_sr.get('content', '')}")
                            if not _sr_text or _abbr_norm not in _sr_text:
                                continue
                            total += 1
                            _has_candidate = _cand_norm in _sr_text
                            if _has_candidate:
                                linked += 1

                            _sr_url = str(_sr.get("url") or "")
                            if (
                                _has_candidate
                                and any(p in _sr_url for p in OFFICIAL_PLATFORMS)
                                and self._is_novel_detail_url(_sr_url)
                            ):
                                official_linked += 1

                        if total < 3:
                            return False

                        linked_ratio = linked / max(total, 1)
                        # 공식 결속이 0이고, 약칭 노출 대비 후보 결속이 낮으면 일반어/모호 약칭으로 본다.
                        return official_linked == 0 and (linked == 0 or (total >= 5 and linked_ratio < 0.2))

                    if not _veto_exempt and _vf_verification_error:
                        _cand_from_error = ""
                        _cand_from_error = _clean_assignable_title(
                            str(decision.get("official_title") or decision.get("official_novel_title") or "").strip()
                        )
                        if not _cand_from_error and isinstance(decoder_out, dict):
                            _ov_err = decoder_out.get("overall_best_match") or {}
                            if isinstance(_ov_err, dict) and _ov_err.get("title"):
                                _cand_from_error = _clean_assignable_title(str(_ov_err.get("title") or "").strip())
                        if not _cand_from_error and isinstance(decoder_out, dict):
                            for _dt_err in (decoder_out.get("decoded_terms") or []):
                                if not isinstance(_dt_err, dict):
                                    continue
                                _bm_err = _dt_err.get("best_match") or {}
                                _cand_from_error = _clean_assignable_title(str(_bm_err.get("title") or "").strip())
                                if _cand_from_error:
                                    break
                        if not _cand_from_error:
                            for _st_err in (getattr(ctx, "suspected_titles", []) or []):
                                if isinstance(_st_err, dict) and _st_err.get("title"):
                                    _cand_from_error = _clean_assignable_title(str(_st_err.get("title") or "").strip())
                                    if _cand_from_error:
                                        break

                        _cand_direct_err = self._title_directly_in_post(ctx, _cand_from_error) if _cand_from_error else False
                        _cand_align_err = self._has_decoder_alignment_support(
                            decoder_out, _cand_from_error, min_score=0.35
                        ) if _cand_from_error else False
                        _cand_hard_err = _has_hard_candidate_support(_cand_from_error) if _cand_from_error else False
                        _cand_strong_err = self._has_strong_title_support(ctx, _cand_from_error) if _cand_from_error else False
                        _gk_post_type_err = str((gatekeeper_out or {}).get("post_type") or "").lower().strip()
                        _gk_work_err = _gk_post_type_err in {"work_discussion", "short_reaction", "character_talk"}
                        if (
                            _cand_from_error
                            and not _genre_warning_effective
                            and (
                                (_cand_hard_err and (_cand_direct_err or _cand_align_err))
                                or (_cand_strong_err and (_cand_align_err or _gk_work_err))
                            )
                        ):
                            _veto_exempt = True
                            decision["_verifier_veto_exempt"] = True
                            decision["is_relevant"] = True
                            decision["is_novel_discussion"] = True
                            if not decision.get("official_title"):
                                decision["official_title"] = _cand_from_error
                                decision["official_novel_title"] = _cand_from_error
                            if decision.get("discussion_type") in {
                                "noise", "off_topic", "meta", "community_banter",
                                "genre_opinion", "trope_discussion", "image_post",
                            }:
                                decision["discussion_type"] = "work_discussion"
                            decision["final_reasoning"] = self._synthesize_evidence_reason(
                                ctx, "Verifier오류면제", True
                            )
                            print(
                                f"[{_ts()}][{self.emoji}] 🔄 Verifier 오류 면제: "
                                f"title='{_cand_from_error}', direct={_cand_direct_err}, "
                                f"align={_cand_align_err}, hard={_cand_hard_err}, strong={_cand_strong_err}, "
                                f"gk_type='{_gk_post_type_err}'",
                                file=sys.stderr,
                            )

                    if ctx.suspected_titles:
                        _conf_map_v = {"high": 3, "medium": 2, "low": 1, "none": 0}
                        _has_strong_v = any(
                            (isinstance(st.get("confidence", 0), (int, float)) and st.get("confidence", 0) >= 0.7)
                            or (isinstance(st.get("confidence", ""), str) and _conf_map_v.get(str(st.get("confidence", "")).lower(), 0) >= 2)
                            for st in ctx.suspected_titles
                        )
                        if _has_strong_v:
                            # 본문에 검색 확인 작가명이 있는지 확인
                            _post_data = getattr(ctx, 'post_data', {}) or {}
                            _body_parts = []
                            for _blk in _post_data.get("content_blocks", []):
                                if isinstance(_blk, dict) and _blk.get("text"):
                                    _body_parts.append(_blk["text"])
                                elif isinstance(_blk, str):
                                    _body_parts.append(_blk)
                            _body_comments = " ".join(_body_parts + (getattr(ctx, 'comments', []) or []))
                            _body_lower = _body_comments.lower().replace(" ", "")
                            _vf_result_veto = (verifier_out.get("verification_result") or {}) if verifier_out else {}
                            _vf_author_info_veto = _vf_result_veto.get("author_info") or {}
                            _vf_relation_veto = _vf_result_veto.get("relation_judgment") or {}
                            _vf_author_criticism_veto = bool(
                                isinstance(_vf_author_info_veto, dict)
                                and _vf_author_info_veto.get("is_author_criticism") is True
                            )
                            _vf_relation_target_veto = str(
                                _vf_relation_veto.get("discussion_target") or "mixed_or_uncertain"
                            ).strip().lower()
                            _vf_relation_promotion_veto = str(
                                _vf_relation_veto.get("promotion_decision") or ""
                            ).strip().lower()
                            _authorish_veto_block = bool(
                                author_criticism_guard_active
                                or _vf_author_criticism_veto
                                or _vf_relation_target_veto in {
                                    "mixed_or_uncertain",
                                    "community_banter",
                                    "genre_general",
                                    "platform_meta",
                                }
                                or _vf_relation_promotion_veto in {"hold", "reject"}
                            )
                            _relation_guard_blocks_loose_veto = _authorish_veto_block
                            
                            _snippet_h = getattr(ctx, 'snippet_hints', {}) or {}
                            _author_h = _snippet_h.get("author_hints", []) or []
                            # Decoder is_author_name도 추가
                            _dec_authors = set()
                            _dec_out_v = ctx.expert_outputs.get("decoder") or {} if hasattr(ctx, 'expert_outputs') else {}
                            for _dt_v in _dec_out_v.get("decoded_terms", []):
                                if _dt_v.get("is_author_name"):
                                    _ai = (_dt_v.get("author_info") or {}).get("name", "")
                                    if _ai:
                                        _dec_authors.add(_ai.lower().replace(" ", ""))
                                    _ov = _dt_v.get("original", "")
                                    if _ov:
                                        _dec_authors.add(_ov.lower().replace(" ", ""))
                            _all_auth = set(
                                (a.get("name") if isinstance(a, dict) else str(a)).lower().replace(" ", "")
                                for a in _author_h
                                if a and len((a.get("name") if isinstance(a, dict) else str(a))) >= 2
                            )
                            _all_auth |= _dec_authors
                            
                            if _authorish_veto_block:
                                print(
                                    f"[{_ts()}][{self.emoji}] 🛡️ Verifier 거부권 면제 차단: "
                                    f"author/meta 문맥(target={_vf_relation_target_veto}, "
                                    f"promotion={_vf_relation_promotion_veto}, "
                                    f"author_criticism={_vf_author_criticism_veto})",
                                    file=sys.stderr,
                                )
                            elif any(a in _body_lower for a in _all_auth if a):
                                _veto_exempt = True
                                _matched_auth = [a for a in _all_auth if a and a in _body_lower]
                                print(
                                    f"[{_ts()}][{self.emoji}] 🔄 Verifier 거부권 면제: "
                                    f"제목에 검증된 약칭 + 본문에 검증된 작가명 존재 (작가: {_matched_auth})",
                                    file=sys.stderr
                                )
                    
                    # 🆕 추가 거부권 면제: 게시글 제목에 snippet_analyzer 약칭 존재
                    # "게시글 제목 = 본문의 시작점" 원칙: 제목에 약칭이 있으면 작품 직접 지칭
                    # 예: "즉사무림이유백 미래가 벌써 보이네" — 제목 자체에 약칭
                    _post_title_veto = (
                        (getattr(ctx, 'post_data', {}) or {}).get('title', '')
                        .replace(' ', '').lower()
                    )

                    if (
                        (not _veto_exempt)
                        and decision.get("is_relevant") is True
                        and (not _relation_guard_blocks_loose_veto)
                    ):
                        _sh_veto = getattr(ctx, 'snippet_hints', None) or {}
                        _abbrev_hints_veto = _sh_veto.get('abbreviation_hints', []) or []
                        if _post_title_veto and _abbrev_hints_veto:
                            for _abh_veto in _abbrev_hints_veto:
                                if isinstance(_abh_veto, dict):
                                    _abh_abbrev_raw = str(_abh_veto.get('abbrev') or '')
                                    _abh_full_veto = str(_abh_veto.get('full') or '')
                                    _abh_source_veto = str(_abh_veto.get('source') or '').lower()
                                elif isinstance(_abh_veto, str):
                                    _abh_abbrev_raw = _abh_veto
                                    _abh_full_veto = ""
                                    _abh_source_veto = ""
                                else:
                                    continue

                                _abh_abbrev_veto = _abh_abbrev_raw.replace(' ', '').lower()
                                # 저신뢰 약칭 매핑으로 Verifier 거부권이 풀리는 것을 방지
                                _trusted_abbrev_sources = {
                                    "author_bridge",
                                    "url_fetch_platform",
                                    "platform_title",
                                    "known_abbreviation",
                                }
                                if self._is_generic_abbreviation_token(_abh_abbrev_raw, _abh_full_veto):
                                    continue
                                _hard_support_veto = _has_hard_candidate_support(_abh_full_veto)
                                _strong_support_veto = _hard_support_veto or self._has_strong_title_support(ctx, _abh_full_veto)
                                _ambiguous_abbrev_veto = _is_ambiguous_abbrev_context(
                                    _abh_abbrev_raw,
                                    _abh_full_veto,
                                )
                                _suspicious_full_veto = any(
                                    tok in _abh_full_veto for tok in ("=", "갤러리", "채널", "포텐", "독후감")
                                )
                                if not _abh_full_veto:
                                    continue
                                if (
                                    _abh_source_veto not in _trusted_abbrev_sources
                                    and not _strong_support_veto
                                ):
                                    continue
                                if _ambiguous_abbrev_veto and not _strong_support_veto:
                                    continue
                                if _suspicious_full_veto and not _strong_support_veto:
                                    continue
                                if _abh_abbrev_veto and len(_abh_abbrev_veto) >= 2 and _abh_abbrev_veto in _post_title_veto:
                                    _veto_exempt = True
                                    print(
                                        f"[{_ts()}][{self.emoji}] 🔄 Verifier 거부권 면제: "
                                        f"게시글 제목에 검증된 약칭 '{_abh_abbrev_raw}' 존재 "
                                        f"→ '{_abh_full_veto}' (제목=본문 시작점 원칙)",
                                        file=sys.stderr,
                                    )
                                    # 만약 Arbiter가 올바른 제목을 설정하지 않았으면 약칭 매핑의 full 사용
                                    if _abh_full_veto and not decision.get("official_title"):
                                        _assign_title = _clean_assignable_title(_abh_full_veto)
                                        if _assign_title:
                                            decision["official_title"] = _assign_title
                                            decision["official_novel_title"] = _assign_title
                                        else:
                                            print(
                                                f"[{_ts()}][{self.emoji}] 🧹 약칭 full 제목 주입 스킵: "
                                                f"'{_abh_full_veto}' (오염/근거부족)",
                                                file=sys.stderr,
                                            )
                                    break

                    # 🆕 추가 거부권 면제: 제목 내 '검증된 고정 약칭'이 Decoder/의심제목과 합치되는 경우
                    # 예: "아생갤" → "아카데미 생존 갤러리"
                    if (
                        (not _veto_exempt)
                        and decision.get("is_relevant") is True
                        and (not _relation_guard_blocks_loose_veto)
                    ):
                        _title_norm = (
                            (getattr(ctx, "post_data", {}) or {}).get("title", "")
                            .replace(" ", "")
                            .lower()
                        )
                        _suspect_norms = set(
                            str(st.get("title", "")).replace(" ", "").lower()
                            for st in (getattr(ctx, "suspected_titles", []) or [])
                            if isinstance(st, dict) and st.get("title")
                        )
                        _decoder_norms = set()
                        if isinstance(decoder_out, dict):
                            _ov = decoder_out.get("overall_best_match") or {}
                            if isinstance(_ov, dict) and _ov.get("title"):
                                _decoder_norms.add(str(_ov.get("title")).replace(" ", "").lower())
                            for _dt in decoder_out.get("decoded_terms", []) or []:
                                if not isinstance(_dt, dict):
                                    continue
                                _bm = _dt.get("best_match") or {}
                                if isinstance(_bm, dict) and _bm.get("title"):
                                    _decoder_norms.add(str(_bm.get("title")).replace(" ", "").lower())

                        for _abbr, _full in KNOWN_TITLE_ABBREVIATIONS.items():
                            _abbr_n = _abbr.replace(" ", "").lower()
                            _full_n = _full.replace(" ", "").lower()
                            if _abbr_n and _abbr_n in _title_norm and (
                                _full_n in _suspect_norms or _full_n in _decoder_norms
                            ):
                                _known_hard_support = _has_hard_candidate_support(_full)
                                _known_direct_anchor = self._title_directly_in_post(ctx, _full)
                                _known_decoder_align = self._has_decoder_alignment_support(
                                    decoder_out, _full, min_score=0.50
                                )
                                _known_curated_anchor = self._has_curated_alias_guard_exception(
                                    ctx,
                                    _full,
                                    decoder_out=decoder_out,
                                    verifier_out=verifier_out,
                                )
                                if not _known_hard_support:
                                    continue
                                if not (
                                    _known_direct_anchor
                                    or (_known_decoder_align and _known_curated_anchor)
                                ):
                                    continue
                                if (
                                    _genre_warning_effective
                                    and (not _known_direct_anchor)
                                    and (not (_known_decoder_align and _known_hard_support and _known_curated_anchor))
                                ):
                                    continue
                                _veto_exempt = True
                                if not decision.get("official_title"):
                                    decision["official_title"] = _full
                                    decision["official_novel_title"] = _full
                                print(
                                    f"[{_ts()}][{self.emoji}] 🔄 Verifier 거부권 면제: "
                                    f"제목 고정약칭 '{_abbr}' 검증됨 → '{_full}'",
                                    file=sys.stderr,
                                )
                                break

                    # 🆕 추가 거부권 면제: snippet_analyzer의 identified_title이 게시글 제목에 존재
                    # "지구온라인 재밌다며 장붕아" — snippet_analyzer가 "지구온라인"을 식별
                    # 제목에 작품명이 직접 있으면 제목=본문 시작점 원칙 적용
                    if (
                        (not _veto_exempt)
                        and decision.get("is_relevant") is True
                        and (not _relation_guard_blocks_loose_veto)
                    ):
                        _lsa_veto = getattr(ctx, 'llm_snippet_analysis', None) or {}
                        _snippet_id_title = (_lsa_veto.get('identified_title') or '').strip()
                        _snippet_cat = str(_lsa_veto.get("identified_category") or "").lower().strip()
                        _snippet_intent = str(_lsa_veto.get("post_intent") or "").lower().strip()
                        _snippet_is_novel = (
                            _snippet_cat in {"web_novel", "novel_literature", "novel"}
                            or _snippet_intent in {"work_discussion", "discuss_work"}
                        )
                        if (
                            _snippet_id_title
                            and len(_snippet_id_title) >= 2
                            and _post_title_veto  # already normalized above
                            and (not self._is_platform_branding_title(_snippet_id_title))
                        ):
                            _norm_sid = _snippet_id_title.replace(' ', '').lower()
                            _sid_hard_support = _has_hard_candidate_support(_snippet_id_title)
                            if _norm_sid in _post_title_veto and _snippet_is_novel and _sid_hard_support:
                                _veto_exempt = True
                                print(
                                    f"[{_ts()}][{self.emoji}] 🔄 Verifier 거부권 면제: "
                                    f"snippet_analyzer identified_title '{_snippet_id_title}' "
                                    f"이 게시글 제목에 존재 (제목=본문 시작점 원칙)",
                                    file=sys.stderr,
                                )
                                if not decision.get("official_title"):
                                    _assign_title = _clean_assignable_title(
                                        _snippet_id_title,
                                        require_hard_support=True,
                                    )
                                    if _assign_title:
                                        decision["official_title"] = _assign_title
                                        decision["official_novel_title"] = _assign_title

                    # 🆕 추가 거부권 면제: Arbiter LLM이 is_relevant=true로 판정했고,
                    # Decoder가 high confidence로 작품을 식별한 경우
                    # (Verifier 다중호출 시 2차 호출이 1차를 뒤집는 문제 방지)
                    if (
                        (not _veto_exempt)
                        and decision.get("is_relevant") is True
                        and (not _relation_guard_blocks_loose_veto)
                    ):
                        for _dt_veto in decoder_out.get("decoded_terms", []):
                            _bm_veto = _dt_veto.get("best_match") or {}
                            _conf_veto_str = str(_bm_veto.get("confidence") or "").lower()
                            _bm_title_veto = str(_bm_veto.get("title") or "")
                            _gr_veto = _dt_veto.get("grounding") or {}
                            _anchor_veto = str(_gr_veto.get("anchor_type") or "").lower()
                            _bm_hard_support = _has_hard_candidate_support(_bm_title_veto)
                            # Decoder가 high/max + title_mention 앵커 → 강한 증거
                            if (
                                _conf_veto_str in ("high", "max")
                                and _anchor_veto in ("title_mention", "character_title_link")
                                and _bm_hard_support
                                and (not _genre_warning_effective)
                            ):
                                _veto_exempt = True
                                print(
                                    f"[{_ts()}][{self.emoji}] 🔄 Verifier 거부권 면제: "
                                    f"Arbiter LLM=true + Decoder='{_bm_title_veto}'"
                                    f"(conf={_conf_veto_str}, anchor={_anchor_veto})",
                                    file=sys.stderr,
                                )
                                break
                        if (
                            (not _veto_exempt)
                            and decision.get("is_relevant") is True
                            and _genre_warning_effective
                        ):
                            print(
                                f"[{_ts()}][{self.emoji}] 🛡️ Verifier 거부권 면제 차단: "
                                f"유효 장르경고 상태에서는 Decoder 단독 고신뢰 면제 금지",
                                file=sys.stderr,
                            )
                    
                    # 🆕 추가 거부권 면제: Decoder가 KNOWN_ABBREVIATION + 캐릭터 검색 검증 완료
                    # (다중호출 시 마지막 결과가 덮어써도 ctx에 영구 저장된 검증 사실 활용)
                    if not _veto_exempt and getattr(ctx, 'verified_character_work_links', []):
                        _vcwl_all = list(ctx.verified_character_work_links or [])
                        _vcwl_strong = [
                            v for v in _vcwl_all
                            if isinstance(v, dict) and not bool(v.get("_weak_match"))
                        ]
                        _vcwl_supported = [
                            v for v in _vcwl_strong
                            if self._has_strong_title_support(ctx, str(v.get("title") or ""))
                        ]
                        _vcwl_titles = [str(v.get("title") or "") for v in _vcwl_supported if v.get("title")]

                        if _genre_warning_effective:
                            print(
                                f"[{_ts()}][{self.emoji}] 🛡️ 캐릭터검증 면제 차단: "
                                f"유효 장르경고 상태에서 강제 복원 금지",
                                file=sys.stderr,
                            )
                        elif _vcwl_titles:
                            _veto_exempt = True
                            # Arbiter LLM도 is_relevant=false로 판정한 경우 → 강제 복원
                            if decision.get("is_relevant") == False:
                                _restore_title = _clean_assignable_title(
                                    _vcwl_titles[0] if _vcwl_titles else None,
                                    require_hard_support=True,
                                )
                                decision["is_relevant"] = True
                                decision["is_novel_discussion"] = True
                                if _restore_title:
                                    decision["official_title"] = _restore_title
                                    decision["official_novel_title"] = _restore_title
                                # discussion_type 교정
                                _dt = decision.get("discussion_type", "")
                                _ALWAYS_IRRELEVANT_DT = {
                                    "noise", "off_topic", "meta", "community_banter",
                                    "genre_opinion", "trope_discussion", "recommendation",
                                    "image_post",
                                }
                                if _dt in _ALWAYS_IRRELEVANT_DT:
                                    decision["discussion_type"] = "character_talk"
                                decision["confidence"] = "Medium"
                                decision["final_reasoning"] = self._synthesize_evidence_reason(ctx, "캐릭터검증면제", True)
                            print(
                                f"[{_ts()}][{self.emoji}] 🔄 Verifier 거부권 면제 + 강제 복원: "
                                f"캐릭터-작품 강검증 완료 (titles={_vcwl_titles})",
                                file=sys.stderr,
                            )
                        else:
                            print(
                                f"[{_ts()}][{self.emoji}] 🛡️ 캐릭터검증 면제 차단: "
                                f"weak/unsupported links={len(_vcwl_all)}",
                                file=sys.stderr,
                            )

                    # 🆕 추가 거부권 면제: Decoder rescue (코드 레벨 약어 매칭)가
                    # 공식 플랫폼에서 높은 점수로 작품을 확인 + 본문에 작가명 또는 게시글 제목에 약어
                    if not _veto_exempt and isinstance(decoder_out, dict):
                        _OFFICIAL_RESCUE_PLATFORMS = (
                            "novelpia", "munpia", "naver", "kakao", "joara", "ridi",
                            "platform:novelpia", "platform:munpia", "platform:series.naver",
                        )
                        for _dt_rescue in (decoder_out.get("decoded_terms") or []):
                            if not isinstance(_dt_rescue, dict):
                                continue
                            _bm_rescue = _dt_rescue.get("best_match") or {}
                            _rescue_title_r = str(_bm_rescue.get("title") or "").strip()
                            if not _rescue_title_r:
                                continue
                            # rescue 여부 + 공식 플랫폼 + 높은 점수 확인
                            _rescue_found = None
                            for _c_r in (_dt_rescue.get("candidates") or [])[:5]:
                                if not isinstance(_c_r, dict):
                                    continue
                                _dl_r = str(_c_r.get("decode_logic") or "").lower()
                                _se_r = str(_c_r.get("search_evidence") or "").lower()
                                if "rescue" in _dl_r:
                                    try:
                                        _ms_r = float(_c_r.get("morphological_score") or 0)
                                    except (ValueError, TypeError):
                                        _ms_r = 0.0
                                    _from_platform_r = any(p in _se_r for p in _OFFICIAL_RESCUE_PLATFORMS)
                                    if _ms_r >= 0.85 and _from_platform_r:
                                        _rescue_found = {"title": _rescue_title_r, "score": _ms_r, "src": _se_r}
                                        break
                            if not _rescue_found:
                                continue
                            # 추가 신호: 게시글 제목에 약어 존재 OR 본문에 작가명 존재
                            _post_title_r = (
                                (getattr(ctx, "post_data", {}) or {}).get("title", "")
                                .replace(" ", "").lower()
                            )
                            _orig_r = str(_dt_rescue.get("original") or "").replace(" ", "").lower()
                            _has_abbrev_in_title_r = bool(
                                _orig_r and len(_orig_r) >= 2 and _orig_r in _post_title_r
                            )
                            # 작가명 확인
                            _dec_auths_r: Set[str] = set()
                            for _dt_a_r in (decoder_out.get("decoded_terms") or []):
                                if not isinstance(_dt_a_r, dict) or not _dt_a_r.get("is_author_name"):
                                    continue
                                _ai_r = ((_dt_a_r.get("author_info") or {}).get("name") or "")
                                if _ai_r:
                                    _dec_auths_r.add(_ai_r.lower().replace(" ", ""))
                                _ov_r = str(_dt_a_r.get("original") or "")
                                if _ov_r:
                                    _dec_auths_r.add(_ov_r.lower().replace(" ", ""))
                            _has_author_body_r = False
                            if _dec_auths_r:
                                _body_ps_r: List[str] = []
                                _pd_r = getattr(ctx, "post_data", {}) or {}
                                for _blk_r in (_pd_r.get("content_blocks") or []):
                                    if isinstance(_blk_r, dict) and _blk_r.get("text"):
                                        _body_ps_r.append(str(_blk_r["text"]))
                                    elif isinstance(_blk_r, str):
                                        _body_ps_r.append(_blk_r)
                                _body_ps_r.extend(
                                    str(c) for c in (getattr(ctx, "comments", []) or []) if c
                                )
                                _body_r = " ".join(_body_ps_r).lower().replace(" ", "")
                                _has_author_body_r = any(a in _body_r for a in _dec_auths_r if a)

                            if _has_abbrev_in_title_r or _has_author_body_r:
                                _veto_exempt = True
                                _rescue_clean_r = _clean_assignable_title(_rescue_found["title"])
                                if _rescue_clean_r:
                                    decision["official_title"] = _rescue_clean_r
                                    decision["official_novel_title"] = _rescue_clean_r
                                decision["is_relevant"] = True
                                decision["is_novel_discussion"] = True
                                _NOISE_DT_R = {
                                    "noise", "off_topic", "meta", "community_banter",
                                    "genre_opinion", "trope_discussion", "image_post",
                                }
                                if decision.get("discussion_type") in _NOISE_DT_R:
                                    decision["discussion_type"] = "work_discussion"
                                decision["final_reasoning"] = self._synthesize_evidence_reason(
                                    ctx, "Decoder-rescue면제", True
                                )
                                _signals_r = []
                                if _has_abbrev_in_title_r:
                                    _signals_r.append(f"제목약어='{_orig_r}'")
                                if _has_author_body_r:
                                    _signals_r.append(f"작가명={list(_dec_auths_r)[:2]}")
                                print(
                                    f"[{_ts()}][{self.emoji}] 🔄 Verifier 거부권 면제: "
                                    f"Decoder rescue '{_rescue_found['title']}' "
                                    f"(score={_rescue_found['score']:.2f}, {_rescue_found['src']}) "
                                    f"+ {', '.join(_signals_r)}",
                                    file=sys.stderr,
                                )
                                break

                    if _veto_exempt:
                        _cand_for_veto = str(
                            decision.get("official_title")
                            or decision.get("official_novel_title")
                            or ""
                        ).strip()
                        # 🆕 Fallback: decision에 제목이 없을 때 Decoder rescue/suspected_titles에서 후보 확보
                        # (_title_deliberately_null 처리로 title이 비어있는 경우 대비)
                        _cand_from_fallback = False
                        if not _cand_for_veto and isinstance(decoder_out, dict):
                            # 1) Decoder decoded_terms에서 rescue 성공한 제목 찾기
                            for _dt_fb in (decoder_out.get("decoded_terms") or []):
                                if not isinstance(_dt_fb, dict):
                                    continue
                                _bm_fb = _dt_fb.get("best_match") or {}
                                _fb_title = str(_bm_fb.get("title") or "").strip()
                                if not _fb_title:
                                    continue
                                # rescue 여부: candidates에 "rescue" decode_logic이 있는가
                                _fb_cands = _dt_fb.get("candidates") or []
                                _is_rescue_fb = any(
                                    isinstance(c, dict) and "rescue" in str(c.get("decode_logic") or "").lower()
                                    for c in _fb_cands[:5]
                                )
                                if _is_rescue_fb:
                                    _fb_cleaned = _clean_assignable_title(_fb_title)
                                    if _fb_cleaned:
                                        _cand_for_veto = _fb_cleaned
                                        _cand_from_fallback = True
                                        break
                            # 2) Decoder overall_best_match
                            if not _cand_for_veto:
                                _ov_fb = decoder_out.get("overall_best_match") or {}
                                if isinstance(_ov_fb, dict) and _ov_fb.get("title"):
                                    _fb_cleaned = _clean_assignable_title(str(_ov_fb["title"]))
                                    if _fb_cleaned:
                                        _cand_for_veto = _fb_cleaned
                                        _cand_from_fallback = True
                        # 3) suspected_titles fallback
                        if not _cand_for_veto:
                            for _st_fb in (getattr(ctx, 'suspected_titles', []) or []):
                                if isinstance(_st_fb, dict) and _st_fb.get("title"):
                                    _fb_cleaned = _clean_assignable_title(str(_st_fb["title"]), require_hard_support=True)
                                    if _fb_cleaned:
                                        _cand_for_veto = _fb_cleaned
                                        _cand_from_fallback = True
                                        break
                        if _cand_from_fallback and _cand_for_veto:
                            print(
                                f"[{_ts()}][{self.emoji}] 🔄 거부권 면제 재검증: "
                                f"decision 제목 비어있음 → Decoder/suspected fallback='{_cand_for_veto}'",
                                file=sys.stderr,
                            )

                        _cand_direct_veto = self._title_directly_in_post(ctx, _cand_for_veto)
                        _cand_align_veto = self._has_decoder_alignment_support(
                            decoder_out, _cand_for_veto, min_score=0.45
                        )
                        _cand_hard_veto = _has_hard_candidate_support(_cand_for_veto) if _cand_for_veto else False
                        if not (_cand_hard_veto and (_cand_direct_veto or _cand_align_veto)):
                            # 🆕 Fallback: hard support 불충분이지만 공식 플랫폼 증거가 있으면 면제 유지
                            _cand_strong_fallback = (
                                self._has_strong_title_support(ctx, _cand_for_veto)
                                if _cand_for_veto
                                else False
                            )
                            if _cand_strong_fallback:
                                print(
                                    f"[{_ts()}][{self.emoji}] 🔄 거부권 면제 재검증 soft pass: "
                                    f"hard support 불충분이지만 공식 플랫폼 증거 확인 "
                                    f"→ '{_cand_for_veto}'",
                                    file=sys.stderr,
                                )
                            else:
                                print(
                                    f"[{_ts()}][{self.emoji}] 🛡️ Verifier 거부권 면제 재검증 실패: "
                                    f"title='{_cand_for_veto}', hard={_cand_hard_veto}, "
                                    f"direct_anchor={_cand_direct_veto}, decoder_align={_cand_align_veto} "
                                    f"→ 면제 취소",
                                    file=sys.stderr,
                                )
                                _veto_exempt = False

                    if _veto_exempt:
                        decision["_verifier_veto_exempt"] = True
                        # 🆕 면제 성공 + fallback 제목이 있으면 → 제목/관련성 복원
                        if _cand_from_fallback and _cand_for_veto:
                            if not decision.get("official_title"):
                                decision["official_title"] = _cand_for_veto
                                decision["official_novel_title"] = _cand_for_veto
                            if decision.get("is_relevant") is False:
                                decision["is_relevant"] = True
                                decision["is_novel_discussion"] = True
                            # noise/off_topic → 적절한 discussion_type으로 교정
                            _NOISE_DT = {"noise", "off_topic", "meta", "community_banter",
                                         "genre_opinion", "trope_discussion", "image_post"}
                            if decision.get("discussion_type") in _NOISE_DT:
                                decision["discussion_type"] = "work_discussion"
                            decision["final_reasoning"] = self._synthesize_evidence_reason(
                                ctx, "거부권면제+Decoder복원", True
                            )
                            print(
                                f"[{_ts()}][{self.emoji}] ✅ 거부권 면제 + 제목 복원: "
                                f"'{_cand_for_veto}' (from={'rescue' if _cand_from_fallback else 'decision'})",
                                file=sys.stderr,
                            )

                    if not _veto_exempt:
                        _decision_title_for_question = str(
                            decision.get("official_title")
                            or decision.get("official_novel_title")
                            or ""
                        ).strip()
                        _question_plot_veto_exempt = self._has_question_plot_title_support(
                            ctx=ctx,
                            candidate_title=_decision_title_for_question,
                            post_data=post_data,
                            gatekeeper_out=gatekeeper_out,
                            discourse_out=discourse_out,
                        )
                        if _question_plot_veto_exempt:
                            _veto_exempt = True
                            decision["_verifier_veto_exempt"] = True
                            if decision.get("is_relevant") is False:
                                decision["is_relevant"] = True
                                decision["is_novel_discussion"] = True
                            if decision.get("discussion_type") in {"noise", "off_topic", "meta", "community_banter", "recommendation"}:
                                decision["discussion_type"] = "general"
                            print(
                                f"[{_ts()}][{self.emoji}] ✅ Verifier 거부권 면제(question_plot_support): "
                                f"title='{_decision_title_for_question}'",
                                file=sys.stderr,
                            )
                    
                    if not _veto_exempt:
                        # Verifier가 is_relevant=false로 판단했으면 거부
                        print(
                            f"[{_ts()}][{self.emoji}] ⚠️ Verifier 거부권 발동: is_relevant=false 강제 적용",
                            file=sys.stderr
                        )
                        decision["is_relevant"] = False
                        decision["official_title"] = None
                        decision["heretic_url"] = None
                        # confidence는 유지 (Verifier의 판단 신뢰도)
                        # notes에 거부 이유 추가
                        vf_reason = vf_result.get("rejection_reason") or vf_result.get("reason") or "Verifier가 작품 토론이 아니라고 판단"
                        if "notes" in decision:
                            decision["notes"] = f"[Verifier 거부권] {vf_reason}. " + decision.get("notes", "")
                        else:
                            decision["notes"] = f"[Verifier 거부권] {vf_reason}"
                        # reason도 종합 증거로 교정 (LLM의 true 사유 대체)
                        decision["final_reasoning"] = self._synthesize_evidence_reason(ctx, "거부권", False)
            
            # �️ P0-1.5: Decoder+Verifier 합의 보호
            # 두 전문가 모두 동일 작품을 High+ 신뢰도로 식별했는데
            # Arbiter LLM이 is_relevant=false로 뒤집은 경우 → 합의 우선
            # 🆕 단, discourse_warning에 genre_discussion이 포함되면 합의 보호 비활성화
            #    (장르 일반론은 Decoder/Verifier가 모두 High를 줘도 FP일 수 있음)
            _discourse_warn = getattr(ctx, 'discourse_warning', '') or ''
            _is_genre_warn_raw = 'genre_discussion' in _discourse_warn.lower() or 'discuss_genre' in _discourse_warn.lower()
            _is_genre_warn = self._is_effective_genre_warning(ctx, decoder_out, verifier_out)
            if _is_genre_warn_raw and not _is_genre_warn:
                print(
                    f"[{_ts()}][{self.emoji}] ℹ️ 장르 경고 soft 처리: "
                    f"warning='{_discourse_warn}' + strong_work_signals=True "
                    f"→ 합의 보호 유지",
                    file=sys.stderr,
                )
            
            if (
                decision.get("is_relevant") == False
                and decoder_out
                and verifier_out
                and not author_criticism_guard_active
            ):
                _dec_title = None
                _dec_conf = ""
                _dec_url = None
                for _t in decoder_out.get("decoded_terms", []):
                    _bm = _t.get("best_match") or {}
                    if _bm.get("title"):
                        _dec_title = _bm["title"]
                        _dec_conf = (_bm.get("confidence") or "").strip().lower()
                        for _c in _t.get("candidates", []):
                            if _c.get("platform_url"):
                                _dec_url = _c["platform_url"]
                                break
                        break

                _vr = verifier_out.get("verification_result") or {}
                _vn = _vr.get("novel_identity") or {}
                _ver_title = ""
                _ver_conf = ""
                _ver_relevant = _vr.get("is_relevant")
                if isinstance(_vn, dict):
                    _ver_title = (
                        _vn.get("official_novel_title")
                        or _vn.get("official_title")
                        or ""
                    )
                    _ver_conf = (
                        _vn.get("confidence")
                        or _vr.get("confidence")
                        or ""
                    ).strip().lower()

                _HIGH = {"high", "very_high", "very high", "확정적", "확실"}
                _norm_t = lambda s: (
                    s.replace(" ", "").replace(",", "").replace(".", "")
                    if s else ""
                )
                _titles_match = (
                    _dec_title
                    and _ver_title
                    and (
                        _dec_title == _ver_title
                        or _norm_t(_dec_title) == _norm_t(_ver_title)
                    )
                )

                _consensus_direct_anchor = bool(self._title_directly_in_post(ctx, _dec_title)) if _dec_title else False
                _consensus_decoder_align = bool(
                    self._has_decoder_alignment_support(
                        decoder_out,
                        _dec_title,
                        min_score=0.55,
                        require_non_generic=True,
                    )
                ) if _dec_title else False
                _consensus_hard_support = bool(self._has_strong_title_support(ctx, _dec_title)) if _dec_title else False
                _consensus_anchor_safe = bool(
                    _consensus_direct_anchor or (_consensus_decoder_align and _consensus_hard_support)
                )

                if (
                    _titles_match
                    and _dec_conf in _HIGH
                    and _ver_conf in _HIGH
                    and _ver_relevant is True
                    and _consensus_anchor_safe
                    and not _is_genre_warn  # 🆕 장르 일반론 경고 시 합의 보호 비활성
                ):
                    print(
                        f"[{_ts()}][{self.emoji}] 🛡️ Decoder+Verifier 합의 보호 발동: "
                        f"'{_dec_title}' (D={_dec_conf}, V={_ver_conf}) "
                        f"→ Arbiter is_relevant=false 무효화",
                        file=sys.stderr,
                    )
                    decision["is_relevant"] = True
                    decision["official_title"] = _dec_title
                    decision["official_novel_title"] = _dec_title
                    if decision.get("confidence", "").lower() in (
                        "none", "low", "",
                    ):
                        decision["confidence"] = "High"
                    if _dec_url and not decision.get("heretic_url"):
                        decision["heretic_url"] = _dec_url
                    _cons_note = (
                        f"[합의 보호] Decoder+Verifier 모두 "
                        f"'{_dec_title}' High+ 합의 "
                        f"→ Arbiter 거부 무효화"
                    )
                    decision["notes"] = (
                        _cons_note + ". " + decision.get("notes", "")
                    )
                    # reason도 종합 증거로 교정 (LLM의 false 사유 대체)
                    decision["final_reasoning"] = self._synthesize_evidence_reason(ctx, "합의보호", True)

                # 🆕 확장 합의 보호: Decoder first-term이 high이고
                # Verifier도 같은 제목+relevant=true인 경우 (Verifier conf 무관)
                # → 캐릭터명 등 부수 term에 의한 overall 하향 보정
                elif (
                    _titles_match
                    and _ver_relevant is True
                    and _dec_conf in _HIGH
                    and _consensus_anchor_safe
                    and not _is_genre_warn  # 🆕 장르 일반론 경고 시 확장 합의 보호도 비활성
                ):
                    print(
                        f"[{_ts()}][{self.emoji}] 🛡️ 확장 합의 보호: "
                        f"Decoder '{_dec_title}' ({_dec_conf}) + "
                        f"Verifier '{_ver_title}' ({_ver_conf}, relevant=true) "
                        f"→ Arbiter 거부 무효화 (confidence=Medium)",
                        file=sys.stderr,
                    )
                    decision["is_relevant"] = True
                    decision["official_title"] = _dec_title
                    decision["official_novel_title"] = _dec_title
                    if decision.get("confidence", "").lower() in (
                        "none", "low", "",
                    ):
                        decision["confidence"] = "Medium"
                    if _dec_url and not decision.get("heretic_url"):
                        decision["heretic_url"] = _dec_url
                    decision["notes"] = (
                        f"[확장 합의 보호] Decoder high + Verifier relevant "
                        f"→ Arbiter 거부 무효화. "
                        + decision.get("notes", "")
                    )
                    # reason도 종합 증거로 교정
                    decision["final_reasoning"] = self._synthesize_evidence_reason(ctx, "확장합의보호", True)

                if (
                    _titles_match
                    and _ver_relevant is True
                    and _dec_conf in _HIGH
                    and not _consensus_anchor_safe
                ):
                    print(
                        f"[{_ts()}][{self.emoji}] 🛡️ 합의 보호 차단: "
                        f"title='{_dec_title}', direct_anchor={_consensus_direct_anchor}, "
                        f"decoder_align={_consensus_decoder_align}, hard_support={_consensus_hard_support} "
                        f"→ 약한 정합으로 강제 복구 금지",
                        file=sys.stderr,
                    )
                
                # 🆕 장르 일반론 경고로 합의 보호가 비활성화된 경우 로그
                if _is_genre_warn and _titles_match and _dec_conf in _HIGH and _ver_relevant is True:
                    print(
                        f"[{_ts()}][{self.emoji}] ⚠️ 장르 일반론 경고로 합의 보호 비활성: "
                        f"'{_dec_title}' (D={_dec_conf}, V={_ver_conf}) "
                        f"+ discourse_warning='{_discourse_warn}' "
                        f"→ Arbiter의 is_relevant=false 유지",
                        file=sys.stderr,
                    )

            # 🆕 BUG-3: image_post 환각 방지 가드
            # Arbiter가 image_post를 반환했지만 실제 텍스트 콘텐츠가 충분한 경우 오버라이드
            if decision.get("discussion_type") == "image_post" and has_text_content:
                print(
                    f"[{_ts()}][{self.emoji}] ⚠️ image_post 환각 감지: "
                    f"discussion_type=image_post이지만 텍스트 {total_text_len}자 존재 "
                    f"→ discussion_type 재설정",
                    file=sys.stderr,
                )
                # Decoder/Verifier가 관련 작품을 찾았으면 해당 판정 반영
                if dc_title and decision.get("is_relevant"):
                    decision["discussion_type"] = "general_discussion"
                    decision["notes"] = (
                        f"[image_post→general_discussion] 텍스트 {total_text_len}자 존재, "
                        f"이미지 전용 아님. " + decision.get("notes", "")
                    )
                else:
                    # 작품 매칭 없으면 noise로
                    decision["discussion_type"] = "noise"
                    decision["notes"] = (
                        f"[image_post 환각 수정] 텍스트 {total_text_len}자 존재하나 "
                        f"작품 매칭 없음. " + decision.get("notes", "")
                    )

            # ️🚨 P0-2: 작가 이름 필터링 (Decoder가 작가로 식별한 경우)
            if decoder_out and decision.get("official_title"):
                decoded_terms = decoder_out.get("decoded_terms", [])
                current_title = decision.get("official_title")
                
                # decoded_terms에서 작가로 식별된 것이 있는지 확인
                for term in decoded_terms:
                    if term.get("is_author_name") == True:
                        # 작가 정보 추출
                        author_info = term.get("author_info") or {}
                        author_name = author_info.get("name") or author_info.get("alias") or term.get("original")
                        
                        # 현재 official_title이 작가 이름과 일치하거나 포함하면 제거
                        is_exact_match = (
                            current_title == author_name
                            or current_title == term.get("original")
                        )
                        author_in_title = (
                            is_exact_match
                            or (author_name and author_name in current_title)
                            or (term.get("original") and term.get("original") in current_title)
                        )
                        # "[작가명] 신작" 패턴 감지
                        has_shinwork_pattern = any(
                            kw in current_title for kw in ("신작", "새 작품", "차기작", "신간")
                        )
                        # 정확히 일치하거나 (작가명 포함 + 신작 패턴)이면 제거
                        if current_title and (is_exact_match or (author_in_title and has_shinwork_pattern)):
                            print(
                                f"[{_ts()}][{self.emoji}] ⚠️ 작가 이름 필터: '{current_title}'는 작가명"
                                f"{'(+신작패턴)' if has_shinwork_pattern else ''}이므로 official_title에서 제거",
                                file=sys.stderr
                            )
                            decision["official_title"] = None
                            if is_exact_match:
                                # 작가명 자체가 title인 경우 → 작가 토론
                                decision["is_relevant"] = False
                                decision["discussion_type"] = "author_talk"
                            else:
                                # "[작가명] 신작 [캐릭터/설정]" → 작품 토론이지만 제목 불확정
                                # is_relevant은 본문 내용에 따라 유지 (작품 내용을 논하고 있을 수 있음)
                                decision["confidence"] = "Low"
                            note_msg = (
                                f"[작가 토론] '{author_name}' 작가에 대한 토론"
                                if is_exact_match else
                                f"[작가 신작] '{author_name}' 작가의 신작 토론이나 정식 제목 불확정"
                            )
                            if "notes" in decision:
                                decision["notes"] = note_msg + ". " + decision.get("notes", "")
                            else:
                                decision["notes"] = note_msg
                            # detected_author에 작가명 기재
                            if "metadata_synthesis" in result:
                                result["metadata_synthesis"]["detected_author"] = author_name
                            break
            
            # 🆕 범용 시간참조 가드 (is_author_name 무관)
            # 게시글 제목에 "신작/전작/최신작" 등 시간참조가 있고,
            # official_title이 본문/제목에 직접 등장하지 않으면 → 제목 불확정
            # 핵심: "개돌 신작 초대남이..." → LLM이 "개돌"을 작가로 인식 못하더라도
            #       "신작"이 제목에 있고 매칭 제목이 본문에 없으면 제목 확정 불가
            if decision.get("official_title") or decision.get("official_novel_title"):
                _temporal_kws = ["신작", "최신작", "새작품", "이번작", "전작", "차기작", "신간"]
                _post_title_raw = ""
                if ctx and hasattr(ctx, 'post_data'):
                    _post_data = getattr(ctx, 'post_data', {}) or {}
                    _post_title_raw = (_post_data.get("title") or "").lower().replace(" ", "")
                _has_temporal_in_title = any(tk in _post_title_raw for tk in _temporal_kws)
                
                if _has_temporal_in_title:
                    _current_official = (
                        decision.get("official_title") or decision.get("official_novel_title") or ""
                    )
                    _official_clean = _current_official.replace(" ", "").lower()
                    
                    # 본문+제목+댓글에 매칭 제목이 직접 존재하는지 확인
                    _body_parts = []
                    if ctx and hasattr(ctx, 'post_data'):
                        _pd = getattr(ctx, 'post_data', {}) or {}
                        for _blk in _pd.get("content_blocks", []):
                            if isinstance(_blk, dict) and _blk.get("text"):
                                _body_parts.append(_blk["text"])
                        _body_parts.append(_pd.get("title", ""))
                    _comments = getattr(ctx, 'comments', []) or [] if ctx else []
                    _full_text_arb = " ".join(_body_parts + list(_comments)).lower().replace(" ", "")
                    
                    _title_in_text_arb = _official_clean and _official_clean in _full_text_arb
                    
                    # 🔧 Phase26-E: 약칭도 본문에 있는지 확인
                    # Decoder가 식별한 원본(original) 약칭이 본문에 있으면
                    # 해당 작품에 대한 실제 토론 → 시간참조 가드 면제
                    _abbrev_in_text_arb = False
                    if not _title_in_text_arb and decoder_out:
                        for _dt_arb in decoder_out.get("decoded_terms", []):
                            _bm_arb = _dt_arb.get("best_match") or {}
                            _bm_title = (_bm_arb.get("title") or "").replace(" ", "").lower()
                            if _bm_title == _official_clean:
                                # 이 term의 original(약칭)이 본문에 있는지 확인
                                _orig_arb = (_dt_arb.get("original") or "").replace(" ", "").lower()
                                if _orig_arb and len(_orig_arb) >= 2 and _orig_arb in _full_text_arb:
                                    _abbrev_in_text_arb = True
                                    print(
                                        f"[{_ts()}][{self.emoji}] ✅ 시간참조 가드 약칭 면제: "
                                        f"약칭 '{_dt_arb.get('original')}'이 본문에 존재 "
                                        f"→ '{_current_official}' 유지",
                                        file=sys.stderr,
                                    )
                                    break
                    
                    if not _title_in_text_arb and not _abbrev_in_text_arb:
                        print(
                            f"[{_ts()}][{self.emoji}] 🛡️ 범용 시간참조 가드: "
                            f"게시글 제목에 시간참조 키워드 + official_title='{_current_official}'가 "
                            f"본문에 미등장 → official_title=null",
                            file=sys.stderr,
                        )
                        decision["official_title"] = None
                        decision["official_novel_title"] = None
                        decision["confidence"] = "Low"
                        _null_reasons = decision.get("_title_null_block_reasons")
                        if not isinstance(_null_reasons, list):
                            _null_reasons = []
                        _null_reasons.append("temporal_reference_guard")
                        decision["_title_null_block_reasons"] = sorted(set(_null_reasons))
                        _temporal_note = (
                            f"[시간참조 불확정] 게시글 제목에 시간참조 키워드 존재, "
                            f"매칭 작품 '{_current_official}'이 본문에 미등장 → 제목 불확정"
                        )
                        decision["notes"] = _temporal_note + ". " + decision.get("notes", "")
            
            # 🔧 Fix D: Decoder가 is_author_name=true인 용어를 식별했고,
            # official_title=null이고 discussion_type="noise"인 경우 → "author_talk"로 보정
            # 작가에 대한 토론/비평은 noise가 아니라 author_talk로 분류되어야 함
            if decoder_out and not decision.get("official_title") and not decision.get("official_novel_title"):
                decoded_terms = decoder_out.get("decoded_terms", [])
                detected_authors = []
                for term in decoded_terms:
                    if term.get("is_author_name") == True:
                        author_info = term.get("author_info") or {}
                        a_name = author_info.get("name") or term.get("original", "")
                        if a_name:
                            detected_authors.append(a_name)
                
                if detected_authors:
                    disc_out = ctx.get_expert_output(ExpertType.DISCOURSE)
                    disc_domain = ""
                    is_assoc = False
                    _post_title_at = str((((getattr(ctx, "post_data", {}) or {}).get("title")) or "")).strip()
                    if disc_out:
                        d_analysis = disc_out.get("discourse_analysis", {})
                        disc_domain = d_analysis.get("primary_domain", "")
                        is_assoc = d_analysis.get("is_association_not_discussion", False)
                    _author_new_work_assoc = bool(
                        detected_authors
                        and _post_title_at
                        and re.search(
                            r"^\s*[가-힣A-Za-z0-9]{2,16}(?:꺼)?\s*(?:신작|최신작|새작품|이번작|전작|차기작|신간)",
                            _post_title_at,
                        )
                    )
                    
                    # 🛡️ 연상글/뻘글에서 억지로 찾은 작가는 author_talk 보정 대상 아님
                    # 예: "모도쿠가 오소우" (VOCALOID곡) → 검색 중 "도쿠이모" 작가 발견
                    #     → 실제로는 작가 토론이 아닌 연상글/뻘글
                    _is_assoc_post = (
                        (getattr(ctx, 'is_association_post', False) or is_assoc)
                        and (not _author_new_work_assoc)
                    )
                    
                    current_dt = decision.get("discussion_type", "")
                    # novel_literature 도메인 + 작가 식별 + noise/off_topic 분류 → author_talk로 보정
                    # 단, 연상글/뻘글(is_association_post)이면 보정 차단
                    if disc_domain == "novel_literature" and current_dt in ("noise", "off_topic", "community_banter") and not _is_assoc_post:
                        # 🔧 Fix E: 캐릭터 3명 이상 + Gatekeeper가 work_discussion
                        # → 단순 author_talk이 아닌 실제 작품 토론 (작품명 미확정)
                        gk_out = ctx.get_expert_output(ExpertType.GATEKEEPER) if ctx else None
                        gk_post_type = ""
                        gk_characters = []
                        if gk_out:
                            gk_post_type = gk_out.get("post_type", "")
                            _gk_ent = gk_out.get("detected_entities") or {}
                            gk_characters = _gk_ent.get("possible_characters") or []
                        
                        _is_work_discussion = (
                            gk_post_type == "work_discussion"
                            and len(gk_characters) >= 3
                            and not is_assoc
                        )
                        
                        if _is_work_discussion:
                            print(
                                f"[{_ts()}][{self.emoji}] 🔧 work_discussion 승격: "
                                f"Decoder 작가={detected_authors}, GK 캐릭터 {len(gk_characters)}명"
                                f"({gk_characters[:3]}...), Discourse={disc_domain} "
                                f"→ 작품 토론(제목 미확정)으로 판정",
                                file=sys.stderr,
                            )
                            decision["discussion_type"] = "work_discussion"
                            decision["is_relevant"] = True
                            decision["confidence"] = "Medium"
                            decision["notes"] = (
                                f"[work_discussion 승격] 작가 {', '.join(detected_authors)}의 "
                                f"작품 토론 감지 (캐릭터: {', '.join(gk_characters[:4])}). "
                                + decision.get("notes", "")
                            )
                            if "metadata_synthesis" in result:
                                result["metadata_synthesis"]["detected_author"] = detected_authors[0]
                                result["metadata_synthesis"]["detected_characters"] = gk_characters[:5]
                        else:
                            print(
                                f"[{_ts()}][{self.emoji}] 🔧 author_talk 보정: "
                                f"Decoder 작가 식별={detected_authors}, Discourse={disc_domain}, "
                                f"기존 discussion_type={current_dt} → author_talk",
                                file=sys.stderr,
                            )
                            decision["discussion_type"] = "author_talk"
                            decision["is_relevant"] = False  # 작가 토론은 is_relevant=false
                        decision["notes"] = (
                            decision.get("notes", "") if _is_work_discussion else
                            f"[author_talk 보정] 작가 {', '.join(detected_authors)} 토론 감지. "
                            + decision.get("notes", "")
                        )
                        # metadata에 작가 정보 기재
                        if "metadata_synthesis" in result:
                            result["metadata_synthesis"]["detected_author"] = detected_authors[0]
                    elif _is_assoc_post:
                        print(
                            f"[{_ts()}][{self.emoji}] 🛡️ author_talk 보정 차단: "
                            f"연상글/뻘글(is_association={is_assoc}) → Decoder가 찾은 작가 "
                            f"{detected_authors}는 부수적 검색 결과, 실제 작가 토론 아님",
                            file=sys.stderr,
                        )
                    elif _author_new_work_assoc and disc_domain == "novel_literature":
                        print(
                            f"[{_ts()}][{self.emoji}] 🔧 author_new_work 연상 예외: "
                            f"제목 '{_post_title_at}'은 작가 신작 패턴 → author_talk 유지",
                            file=sys.stderr,
                        )
                        decision["discussion_type"] = "author_talk"
                        decision["is_relevant"] = False
                        decision["notes"] = (
                            f"[author_new_work 예외] 작가 {', '.join(detected_authors)}의 신작 언급(정식 제목 미확정). "
                            + decision.get("notes", "")
                        )
                        if "metadata_synthesis" in result:
                            result["metadata_synthesis"]["detected_author"] = detected_authors[0]
            
            # �🚨 P0-3: Arbiter 독자 제목 생성 금지
            # Decoder와 Verifier 모두 title을 식별하지 못했는데 Arbiter가 독자적으로 제목을 만들어낸 경우 차단
            if decision.get("official_title") or decision.get("official_novel_title"):
                arbiter_title_raw = decision.get("official_title") or decision.get("official_novel_title")
                arbiter_title = _clean_assignable_title(arbiter_title_raw)
                if not arbiter_title:
                    # 제목이 오염 문자열이면 title만 비우고 관련성 자체는 유지
                    print(
                        f"[{_ts()}][{self.emoji}] 🧹 독자 제목 오염 정리: '{arbiter_title_raw}' "
                        f"→ official_title=null (is_relevant 유지)",
                        file=sys.stderr,
                    )
                    decision["official_title"] = None
                    decision["official_novel_title"] = None
                    arbiter_title = None
                else:
                    if arbiter_title != arbiter_title_raw:
                        print(
                            f"[{_ts()}][{self.emoji}] 🧹 독자 제목 정제: "
                            f"'{arbiter_title_raw}' → '{arbiter_title}'",
                            file=sys.stderr,
                        )
                    decision["official_title"] = arbiter_title
                    decision["official_novel_title"] = arbiter_title

            if decision.get("official_title") or decision.get("official_novel_title"):
                arbiter_title = decision.get("official_title") or decision.get("official_novel_title")
                
                # Decoder가 식별한 제목 목록
                decoder_titles = set()
                if decoder_out:
                    for term in decoder_out.get("decoded_terms") or []:
                        best = term.get("best_match") or {}
                        if best and best.get("title"):
                            decoder_titles.add(best["title"])
                        for cand in term.get("candidates") or []:
                            if cand.get("official_novel_title"):
                                decoder_titles.add(cand["official_novel_title"])
                
                # Verifier가 식별한 제목
                verifier_title = None
                if verifier_out:
                    vf_novel = vf_result.get("novel_identity") or {}
                    if vf_novel and isinstance(vf_novel, dict):
                        verifier_title = vf_novel.get("official_novel_title") or vf_novel.get("official_title")
                
                # Decoder도 Verifier도 식별하지 못했는데 Arbiter가 만들어낸 경우
                if not decoder_titles and not verifier_title:
                    # suspected_titles에 있으면 허용 (다른 전문가가 후보로 제시한 것)
                    suspected = {s.get("title") for s in (ctx.suspected_titles or []) if s.get("title")}
                    if arbiter_title in suspected:
                        print(
                            f"[{_ts()}][{self.emoji}] ℹ️ Arbiter 제목 '{arbiter_title}' - "
                            f"Decoder/Verifier null이지만 suspected_titles에 존재, confidence 하향 허용",
                            file=sys.stderr
                        )
                        decision["confidence"] = "Low"
                    else:
                        # snippet/synthesizer 강한 합의가 있으면 독자 제목 차단을 유예한다.
                        _arbiter_title_supported = False
                        try:
                            _arbiter_title_supported = bool(
                                self._has_strong_title_support(ctx, arbiter_title)
                            )
                        except Exception:
                            _arbiter_title_supported = False
                        if not _arbiter_title_supported:
                            _lsa = getattr(ctx, "llm_snippet_analysis", None) or {}
                            _lsa_title = str(_lsa.get("identified_title") or "").strip()
                            _lsa_intent = str(_lsa.get("post_intent") or "").lower().strip()
                            if _lsa_title and _lsa_intent in {"work_discussion", "discuss_work"}:
                                from difflib import SequenceMatcher
                                _lsa_sim = SequenceMatcher(
                                    None,
                                    arbiter_title.replace(" ", ""),
                                    _lsa_title.replace(" ", ""),
                                ).ratio()
                                _arbiter_title_supported = _lsa_sim >= 0.88
                        if not _arbiter_title_supported:
                            _sy_out = ctx.get_expert_output(ExpertType.SYNTHESIZER) or {}
                            _sy_ca = (_sy_out.get("confidence_assessment") or {}) if isinstance(_sy_out, dict) else {}
                            _sy_is_work = bool(_sy_ca.get("is_about_identified_work") is True)
                            _sy_conf = self._confidence_to_unit(_sy_ca.get("confidence"))
                            if _sy_is_work and _sy_conf >= 0.80:
                                _arb_norm = re.sub(r"[^\w가-힣]", "", str(arbiter_title or "")).lower()
                                _sy_blob_parts = []
                                for _k in ("synthesis_summary",):
                                    _sy_blob_parts.append(str((_sy_out or {}).get(_k) or ""))
                                _ri = (_sy_out or {}).get("reinterpretation") or {}
                                if isinstance(_ri, dict):
                                    _sy_blob_parts.append(str(_ri.get("post_intent") or ""))
                                for _hr in ((_sy_out or {}).get("hidden_references") or []):
                                    if isinstance(_hr, dict):
                                        _sy_blob_parts.append(str(_hr.get("matched_to") or ""))
                                        _sy_blob_parts.append(str(_hr.get("text") or ""))
                                _sy_blob = re.sub(
                                    r"[^\w가-힣]",
                                    "",
                                    " ".join(_sy_blob_parts),
                                ).lower()
                                _arbiter_title_supported = bool(_arb_norm and _arb_norm in _sy_blob)

                        if _arbiter_title_supported:
                            print(
                                f"[{_ts()}][{self.emoji}] ℹ️ Arbiter 독자 제목 차단 유예: '{arbiter_title}' "
                                f"(Decoder/Verifier null이지만 snippet/synth 강한 근거 확인)",
                                file=sys.stderr,
                            )
                            if str(decision.get("confidence") or "").lower() == "high":
                                decision["confidence"] = "Medium"
                        else:
                            print(
                                f"[{_ts()}][{self.emoji}] ⚠️ Arbiter 독자 제목 생성 차단: '{arbiter_title}' "
                                f"(Decoder/Verifier 모두 title=None, suspected_titles에도 없음 → null 강제)",
                                file=sys.stderr
                            )
                            decision["official_title"] = None
                            decision["official_novel_title"] = None
                            if decision.get("discussion_type") not in (
                                "noise", "meta", "recommendation", "community_banter",
                                "genre_opinion", "image_post", "off_topic", "trope_discussion",
                                "author_talk"
                            ):
                                decision["discussion_type"] = "off_topic"
                            decision["is_relevant"] = False
                
                # Arbiter 제목이 Decoder 후보에도 없고 Verifier와도 다른 완전 새 제목인 경우
                # 교정(오타 수정)된 제목도 원본 후보의 변형일 수 있으므로 유사도 검사 포함
                elif decoder_titles and arbiter_title not in decoder_titles and arbiter_title != verifier_title:
                    # 사이트명 정제 결과인지 확인: 정제된 제목이 원본 후보의 부분문자열이면 환각이 아님
                    _is_sanitized_variant = any(
                        arbiter_title in dt or dt.endswith(arbiter_title)
                        for dt in decoder_titles
                    )
                    if _is_sanitized_variant:
                        print(
                            f"[{_ts()}][{self.emoji}] ℹ️ 사이트명 정제 변형 허용: '{arbiter_title}' "
                            f"(Decoder 후보의 정제 버전)",
                            file=sys.stderr
                        )
                    else:
                        # 교정된 제목이 원본 후보와 유사한지 확인 (오타 교정 케이스)
                        from difflib import SequenceMatcher
                        _is_corrected_variant = any(
                            SequenceMatcher(None, arbiter_title.replace(" ", ""), dt.replace(" ", "")).ratio() >= 0.85
                            for dt in decoder_titles
                        )
                        if _is_corrected_variant:
                            # 교정된 제목이 원본 후보의 변형 → 환각이 아님
                            print(
                                f"[{_ts()}][{self.emoji}] ℹ️ Arbiter 제목 교정 변형 허용: '{arbiter_title}' "
                                f"(Decoder 후보: {decoder_titles}의 교정 버전)",
                                file=sys.stderr
                            )
                        else:
                            # suspected_titles에도 없으면 환각 제목
                            suspected = {s.get("title") for s in (ctx.suspected_titles or []) if s.get("title")}
                            # suspected_titles에서도 교정 변형 확인
                            _in_suspected = arbiter_title in suspected or any(
                                SequenceMatcher(None, arbiter_title.replace(" ", ""), st.replace(" ", "")).ratio() >= 0.85
                                for st in suspected
                            )
                            # 검색 근거가 있으면 Decoder 후보와 달라도 환각으로 보지 않음
                            _has_search_support = False
                            try:
                                _arb_norm = re.sub(r"[^\w가-힣]", "", str(arbiter_title or "")).lower()
                                if _arb_norm:
                                    for _sr in (ctx.search_results or []):
                                        _blob = re.sub(
                                            r"[^\w가-힣]",
                                            "",
                                            f"{_sr.get('title', '')} {_sr.get('content', '')} {_sr.get('snippet', '')}",
                                        ).lower()
                                        if _arb_norm in _blob:
                                            _has_search_support = True
                                            break
                            except Exception:
                                _has_search_support = False

                            if (not _in_suspected) and (not _has_search_support):
                                print(
                                    f"[{_ts()}][{self.emoji}] ⚠️ Arbiter 환각 제목 감지: '{arbiter_title}' "
                                    f"(Decoder 후보: {decoder_titles}, Verifier: {verifier_title}) → Decoder 최선 후보 사용",
                                    file=sys.stderr
                                )
                                # Decoder의 가장 좋은 후보로 교체 (작가명 제외, 가장 긴 제목 우선)
                                _non_author_titles = decoder_titles - (decoder_author_names or set())
                                _fallback_titles = _non_author_titles or decoder_titles
                                if _fallback_titles:
                                    _best_fallback = max(_fallback_titles, key=len)
                                    decision["official_title"] = _best_fallback
                                    decision["official_novel_title"] = _best_fallback
                                elif verifier_title:
                                    decision["official_title"] = verifier_title
                                    decision["official_novel_title"] = verifier_title
                            elif (not _in_suspected) and _has_search_support:
                                print(
                                    f"[{_ts()}][{self.emoji}] ℹ️ Arbiter 제목 유지: '{arbiter_title}' "
                                    f"(Decoder 후보와 불일치하지만 검색 근거 확인)",
                                    file=sys.stderr
                                )

            # �️ 아키타입 용어 가드: Decoder가 차단한 아키타입 제목을 Arbiter가 재도입하는 것 방지
            final_title = decision.get("official_title") or decision.get("official_novel_title")
            if final_title and decoder_out:
                blocked_archetypes = set()
                for term in decoder_out.get("decoded_terms") or []:
                    original = (term.get("original") or "").strip()
                    if original in GENRE_ARCHETYPE_TERMS:
                        best = term.get("best_match") or {}
                        if not best.get("title") and best.get("confidence") in ("none", None):
                            blocked_archetypes.add(original)
                if blocked_archetypes:
                    _final_url = str(decision.get("heretic_url") or "").strip()
                    _vf_out = ctx.get_expert_output(ExpertType.VERIFIER) or {}
                    _vf_res = (_vf_out.get("verification_result") or {}) if isinstance(_vf_out, dict) else {}
                    _vf_novel = (_vf_res.get("novel_identity") or {}) if isinstance(_vf_res, dict) else {}
                    _vf_title = str(
                        _vf_novel.get("official_novel_title")
                        or _vf_novel.get("official_title")
                        or ""
                    ).strip()
                    _vf_url = str(_vf_novel.get("heretic_url") or "").strip()
                    _vf_relation = (_vf_res.get("relation_judgment") or {}) if isinstance(_vf_res, dict) else {}
                    _vf_promotion = str(_vf_relation.get("promotion_decision") or "").strip().lower()
                    if _vf_promotion in {"promote", "accept", "keep"}:
                        _vf_promotion = "allow"
                    _strong_exact_title_support = bool(
                        self._title_directly_in_post(ctx, final_title)
                        and (
                            self._is_novel_detail_url(_final_url)
                            or (
                                _vf_title
                                and re.sub(r"[^\w가-힣]", "", _vf_title).lower()
                                == re.sub(r"[^\w가-힣]", "", str(final_title or "")).lower()
                                and self._is_novel_detail_url(_vf_url)
                                and _vf_promotion == "allow"
                            )
                            or self._has_strong_title_support(ctx, final_title)
                        )
                    )
                    title_norm = final_title.replace(" ", "")
                    for arch_term in blocked_archetypes:
                        if _strong_exact_title_support:
                            break
                        if arch_term.replace(" ", "") in title_norm:
                            print(
                                f"[{_ts()}][{self.emoji}] 🛡️ 아키타입 재도입 차단: "
                                f"Decoder가 '{arch_term}' 아키타입 차단 → "
                                f"Arbiter '{final_title}' 재도입 불허 → null 강제",
                                file=sys.stderr,
                            )
                            decision["official_title"] = None
                            decision["official_novel_title"] = None
                            decision["confidence"] = "Low"
                            final_title = None
                            break

            # 🚨 P0-4: 포스트 제목 도용 방지
            # official_title이 분석 대상 포스트의 제목과 높은 유사도면 차단
            final_title = decision.get("official_title") or decision.get("official_novel_title")
            if final_title and post_data:
                post_title = post_data.get("title", "")
                if post_title:
                    # 🔧 꺾쇠 패턴 면제: 게시글 제목에 <작품명>이 명시적으로 기재된 경우
                    # 사용자가 의도적으로 작품명을 꺾쇠로 감싼 것이므로 도용이 아님
                    import re as _re_p04
                    _bracket_m = _re_p04.search(r"[<＜《<](.+?)[>＞》>]", post_title)
                    _bracket_title_norm = _bracket_m.group(1).replace(" ", "").lower() if _bracket_m else ""
                    _final_norm_check = final_title.replace(" ", "").lower()
                    _bracket_exempt = (
                        _bracket_m is not None
                        and len(_bracket_title_norm) >= 3
                        and (
                            _bracket_title_norm in _final_norm_check
                            or _final_norm_check in _bracket_title_norm
                            or _re_p04.sub(r"[^가-힣a-z0-9]", "", _bracket_title_norm)
                               == _re_p04.sub(r"[^가-힣a-z0-9]", "", _final_norm_check)
                        )
                    )
                    if _bracket_exempt:
                        print(
                            f"[{_ts()}][{self.emoji}] ✅ 꺾쇠 패턴 면제: "
                            f"post_title '{post_title}' 에 <{_bracket_m.group(1)}> 명시 → "
                            f"'{final_title}' 도용 차단 스킵",
                            file=sys.stderr,
                        )
                    else:
                        from difflib import SequenceMatcher
                        norm_post = post_title.replace(" ", "")
                        norm_title = final_title.replace(" ", "")
                        sim = SequenceMatcher(None, norm_post, norm_title).ratio()
                        is_substring = norm_title in norm_post or norm_post in norm_title
                        
                        if (sim >= 0.7 or is_substring) and len(final_title) > 3:
                            # 🔧 축약어 포함 패턴 예외: 소설 제목이 게시글 제목의 작은 부분이면 도용 아님
                            if is_substring and norm_title in norm_post:
                                title_ratio = len(norm_title) / max(len(norm_post), 1)
                                if title_ratio < 0.6:
                                    print(
                                        f"[{_ts()}][{self.emoji}] ✅ 축약어 포함 허용: "
                                        f"'{final_title}' ⊂ '{post_title}' "
                                        f"(title_ratio={title_ratio:.2f} < 0.6, sim={sim:.2f})",
                                        file=sys.stderr,
                                    )
                                else:
                                    # 60% 이상 → 도용 검사 실행
                                    self._check_platform_or_block(
                                    decision, final_title, post_title, sim, decoder_out
                                )
                            else:
                                self._check_platform_or_block(
                                    decision, final_title, post_title, sim, decoder_out
                                )
            
            # 🔥 P0-5: Decoder 저신뢰 매칭 + Verifier 본문 증거 없음 → is_relevant=false 강제
            # 64개 FP 분석 결과: Decoder가 High confidence로 잘못 매칭한 경우가 83%
            # 본문에 작품 증거가 없는데 Decoder만 믿고 relevant로 판정하는 것을 방지
            final_title = decision.get("official_title") or decision.get("official_novel_title")
            if final_title and decision.get("is_relevant"):
                _char_like_final = self._is_character_like_short_title(ctx, final_title, decoder_out, verifier_out)
                _non_char_final = self._has_non_character_anchor_support(final_title, decoder_out, verifier_out)
                _hard_final = bool(self._has_strong_title_support(ctx, final_title))
                if _char_like_final and not (_hard_final and _non_char_final):
                    print(
                        f"[{_ts()}][{self.emoji}] 🛡️ 캐릭터형 short title 최종 차단: "
                        f"'{final_title}' (hard={_hard_final}, non_char_anchor={_non_char_final}) "
                        f"→ official_title=null",
                        file=sys.stderr,
                    )
                    decision["official_title"] = None
                    decision["official_novel_title"] = None
                    decision["confidence"] = "Low"
                    final_title = None

            # 🆕 밈/유행어 오매칭 방지:
            # 제목이 밈/조크 패턴이고 본문에 작품 증거(캐릭터, 줄거리, URL)가 없으면
            # 소설 제목 단어가 문맥 없이 사용된 것으로 판정 → FP 차단
            if final_title and decision.get("is_relevant"):
                _post_data = getattr(ctx, "post_data", None) or {}
                _post_title_meme = str(_post_data.get("title") or "")
                # body는 content_blocks에서도 추출
                _post_body_meme = str(_post_data.get("body") or "")
                if not _post_body_meme:
                    _blocks = _post_data.get("content_blocks") or []
                    _post_body_meme = " ".join(
                        str(b.get("text") or "") if isinstance(b, dict) else str(b or "")
                        for b in _blocks[:10]
                    )
                _meme_full_text = _post_title_meme + " " + _post_body_meme
                _meme_final_norm = final_title.replace(" ", "").lower()

                # 밈/조크 패턴: 제목에 소설명이 우연히 포함된 경우 감지
                # "남궁형의 후장은 금강불괴" → "금강불괴"가 소설명이지만 실제론 밈/드립
                # "스바루는 6장이 ㄹㅇ개씹테토남" → 리제로 논의이지만 카사네와로 오매칭
                _meme_signals = 0
                _meme_details = []

                # (1) 제목에 소설명이 직접 포함되지 않음 (약칭도 아님)
                _title_norm_meme = _post_title_meme.replace(" ", "").lower()
                _title_contains_novel = _meme_final_norm in _title_norm_meme
                if not _title_contains_novel:
                    _meme_signals += 1
                    _meme_details.append("title_no_novel_name")

                # (2) Verifier가 본문 앵커를 못찾음
                _vf_grounding_meme = (verifier_out or {}).get("verification_result", {}).get("grounding_check", {})
                _vf_anchor_meme = str(_vf_grounding_meme.get("anchor_found", "none")).lower()
                if _vf_anchor_meme in ("none", "search_only", ""):
                    _meme_signals += 1
                    _meme_details.append(f"weak_anchor={_vf_anchor_meme}")

                # (3) 본문에 소설 관련 실질 증거(줄거리/캐릭터/플랫폼URL)가 없음
                _body_text_len = sum(
                    1 for c in _post_body_meme
                    if ord('가') <= ord(c) <= ord('힣') or c.isalpha()
                )
                _has_platform_url_in_post = bool(
                    re.search(
                        r'(munpia|novelpia|kakao|naver|ridibooks|joara)\.(com|co\.kr)',
                        _meme_full_text,
                    )
                )
                if _body_text_len < 30 and not _has_platform_url_in_post:
                    _meme_signals += 1
                    _meme_details.append(f"no_substance_body={_body_text_len}")

                # (4) discussion_type이 meme → 밈으로 분류됨
                if decision.get("discussion_type") == "meme":
                    _meme_signals += 1
                    _meme_details.append("dt=meme")

                # (5) evidence_bucket에 post_spans가 0 → 포스트 자체엔 증거 없음
                _bucket_meme = {}
                if hasattr(ctx, "get_candidate_evidence"):
                    try:
                        _bucket_meme = ctx.get_candidate_evidence(final_title) or {}
                    except Exception:
                        pass
                _post_spans_count = len((_bucket_meme.get("post_spans") or []))
                if _post_spans_count == 0:
                    _meme_signals += 1
                    _meme_details.append("no_post_spans")

                # (6) Verifier counter_arguments에 critical이 있음
                _vf_counter_args = (verifier_out or {}).get("verification_result", {}).get("counter_arguments") or []
                _has_critical_counter = any(
                    isinstance(ca, dict)
                    and str(ca.get("severity", "")).lower() == "critical"
                    for ca in _vf_counter_args
                )
                if _has_critical_counter:
                    _meme_signals += 1
                    _meme_details.append("verifier_critical_counter")

                # 3개 이상 밈 신호 → FP 가능성 높음
                # ★핵심 변경: 검색 결과 기반 _has_strong_title_support 대신
                # 포스트 로컬 증거만 체크 — 소설이 실제 존재해도 포스트가 밈이면 차단

                _abbrev_meme_exempt = False
                if _meme_signals >= 3 and final_title:
                    _abbrev_meme_exempt = self._has_curated_alias_guard_exception(
                        ctx,
                        final_title,
                        decoder_out=decoder_out,
                        verifier_out=verifier_out,
                    )
                    if _abbrev_meme_exempt:
                        print(
                            f"[{_ts()}][{self.emoji}] 🔑 밈 가드 면제: "
                            f"등록 약칭 + 독립 작품 앵커 확인 → 밈 가드 건너뜀",
                            file=sys.stderr,
                        )

                _verified_alias_meme_exempt = False
                if _meme_signals >= 3 and (not _abbrev_meme_exempt) and final_title:
                    _final_title_norm = str(final_title or "").replace(" ", "").lower()
                    _vcwl = getattr(ctx, "verified_character_work_links", []) or []
                    for _entry in _vcwl:
                        if not isinstance(_entry, dict):
                            continue
                        if bool(_entry.get("_weak_match")):
                            continue
                        _entry_title = str(_entry.get("title") or "").replace(" ", "").lower()
                        if _entry_title and _entry_title == _final_title_norm:
                            _verified_alias_meme_exempt = True
                            break
                    if not _verified_alias_meme_exempt:
                        _vf_grounding = (verifier_out or {}).get("verification_result", {}).get("grounding_check") or {}
                        _vf_anchor_meme_norm = str(_vf_grounding.get("anchor_found") or "").strip().lower()
                        _vf_alias_support = bool(_vf_grounding.get("matched_alias") or _vf_grounding.get("title_abbrev_mentioned"))
                        _vf_relation = (verifier_out or {}).get("verification_result", {}).get("relation_judgment") or {}
                        _vf_relation_target = str(_vf_relation.get("discussion_target") or "").strip().lower()
                        _vf_relation_promotion = str(_vf_relation.get("promotion_decision") or "").strip().lower()
                        _vf_anchor_is_abbrev_only = _vf_anchor_meme_norm in {
                            "title_abbrev_mention",
                            "body_abbrev_mention",
                        }
                        _has_official_support = bool(
                            self._has_strong_title_support(ctx, final_title)
                            or self._has_official_title_evidence(ctx, final_title)
                        )
                        if (
                            _vf_anchor_meme_norm in {
                                "character_mention",
                                "title_abbrev_mention",
                                "body_abbrev_mention",
                                "plot_mention",
                                "title_reaction_link",
                                "decoder_grounded_official",
                                "llm_cross_check",
                            }
                            and _vf_alias_support
                            and _has_official_support
                            and (
                                not _vf_anchor_is_abbrev_only
                                or _abbrev_meme_exempt
                            )
                        ):
                            _verified_alias_meme_exempt = True
                        elif (
                            _vf_relation_target == "specific_work"
                            and _vf_relation_promotion == "hold"
                            and (
                                _vf_alias_support
                                or _vf_anchor_meme_norm in {
                                    "title_reaction_link",
                                    "decoder_grounded_official",
                                    "llm_cross_check",
                                }
                            )
                            and (
                                not _vf_anchor_is_abbrev_only
                                or _abbrev_meme_exempt
                            )
                        ):
                            _verified_alias_meme_exempt = True
                    if _verified_alias_meme_exempt:
                        print(
                            f"[{_ts()}][{self.emoji}] 🔑 밈 가드 면제: "
                            f"title='{final_title}' verified alias/character bridge 확인",
                            file=sys.stderr,
                        )

                if _meme_signals >= 3 and not _abbrev_meme_exempt and not _verified_alias_meme_exempt:
                    # 포스트 로컬 강 증거: 본문에 해당 소설의 줄거리/캐릭터/URL이 직접 등장
                    _has_post_local_evidence = bool(
                        _has_platform_url_in_post  # 본문에 소설 플랫폼 URL
                        or _post_spans_count >= 2   # 본문에서 2건 이상 직접 증거
                        or (
                            _body_text_len >= 80  # 본문이 충분히 길고
                            and _vf_anchor_meme not in ("none", "search_only", "")  # 앵커도 있음
                        )
                        # 🆕 Chapter/episode 참조는 특정 작품 토론의 강한 증거
                        or bool(re.search(r'\d+\s*[장화]', _meme_full_text))
                    )
                    if not _has_post_local_evidence:
                        print(
                            f"[{_ts()}][{self.emoji}] 🃏 밈/유행어 오매칭 차단: "
                            f"'{final_title}' (signals={_meme_signals}: {', '.join(_meme_details)}) "
                            f"→ is_relevant=false",
                            file=sys.stderr,
                        )
                        decision["is_relevant"] = False
                        decision["is_novel_discussion"] = False
                        decision["official_title"] = None
                        decision["official_novel_title"] = None
                        decision["confidence"] = "Low"
                        decision["discussion_type"] = "noise"
                        decision["_meme_blocked"] = True  # Phase31: High-title Lock 복원 방지
                        decision["notes"] = (
                            f"[밈 오매칭 차단] '{final_title}' — "
                            f"본문에 작품 증거 없음 ({', '.join(_meme_details)}). "
                            + decision.get("notes", "")
                        )
                        final_title = None

            if final_title and decision.get("is_relevant") and decision.get("_verifier_veto_exempt"):
                _vcwl_hard_support = any(
                    isinstance(v, dict)
                    and (not bool(v.get("_weak_match")))
                    and self._has_strong_title_support(ctx, str(v.get("title") or ""))
                    for v in (getattr(ctx, "verified_character_work_links", []) or [])
                )
                _veto_hard_support = bool(
                    self._has_strong_title_support(ctx, final_title)
                    or _vcwl_hard_support
                )
                if not _veto_hard_support:
                    decision["_verifier_veto_exempt"] = False
                    print(
                        f"[{_ts()}][{self.emoji}] 🔧 거부권 면제 재검증: "
                        f"title='{final_title}' hard_support 부족 → _verifier_veto_exempt 해제",
                        file=sys.stderr,
                    )

            if (
                final_title
                and decision.get("is_relevant")
                and decoder_out
                and verifier_out
                and not decision.get("_verifier_veto_exempt")
            ):
                # Decoder의 overall confidence 확인
                dc_overall_conf = (decoder_out.get("overall_confidence") or "none").lower()
                
                # Verifier의 grounding 확인
                _vf_result_lowconf = (verifier_out.get("verification_result") or {})
                vf_grounding = _vf_result_lowconf.get("grounding_check", {})
                vf_grounded = vf_grounding.get("decoder_grounded", True)
                vf_anchor = vf_grounding.get("anchor_found", "none")
                vf_title_abbrev_mentioned = bool(vf_grounding.get("title_abbrev_mentioned"))
                vf_body_abbrev_mentioned = bool(vf_grounding.get("body_abbrev_mentioned"))
                vf_matched_alias = str(vf_grounding.get("matched_alias") or "").strip()
                vf_slang = _vf_result_lowconf.get("slang_insight") or {}
                vf_decode_verified = bool(vf_slang.get("decode_verified"))
                vf_decoded_term = str(vf_slang.get("decoded_term") or "").strip()
                
                # Decoder confidence가 low/none이고 Verifier grounding도 약한 경우
                # 🆕 예외: Verifier confidence가 High이면 차단하지 않음
                #   (Verifier가 충분한 증거로 High 판정한 경우 존중)
                # 🔧 BUG-FIX: Verifier는 'novel_identity'를 반환하나 기존 코드가
                #   'novel_identification'을 읽어서 항상 기본값 'Low'가 되던 문제 수정
                _vr_for_conf = _vf_result_lowconf
                vf_conf = (
                    _vr_for_conf.get("novel_identity") or
                    _vr_for_conf.get("novel_identification") or {}
                ).get("confidence", "Low")
                # Verifier 최상위 final_confidence도 체크 (Verifier가 직접 설정하는 경우)
                if vf_conf == "Low":
                    _top_conf = verifier_out.get("final_confidence", "")
                    if isinstance(_top_conf, str) and _top_conf.lower() == "high":
                        vf_conf = "High"
                vf_is_high = vf_conf.lower() == "high" if isinstance(vf_conf, str) else False
                
                if dc_overall_conf in ("low", "none") and (
                    not vf_grounded or vf_anchor in ("search_only", "none")
                ):
                    # cross-expert 강한 정합 신호가 있으면 저신뢰 차단을 유예한다.
                    _gk_post_type = str((gatekeeper_out or {}).get("post_type") or "").lower().strip()
                    _disc = (discourse_out or {}).get("discourse_analysis") or {}
                    _disc_domain = str(_disc.get("primary_domain") or "").lower().strip()
                    _disc_intent = str(_disc.get("intent") or "").lower().strip()
                    _dw = str(getattr(ctx, "discourse_warning", "") or "").lower()
                    _disc_non_novel_hard = "non_novel(" in _dw and _disc_domain in {
                        "daily_life", "memes_humor", "medical_health", "gaming"
                    }
                    _sy_out_low = synthesizer_out or {}
                    _sy_ca_low = (_sy_out_low.get("confidence_assessment") or {}) if isinstance(_sy_out_low, dict) else {}
                    _sy_is_work_low = bool(_sy_ca_low.get("is_about_identified_work") is True)
                    _sy_conf_low = self._confidence_to_unit(_sy_ca_low.get("confidence"))
                    _cross_strong = (
                        _gk_post_type == "work_discussion"
                        and _disc_intent in {"discuss_work", "review", "express_opinion", "anticipation"}
                        and not _disc_non_novel_hard
                        and _sy_is_work_low
                        and _sy_conf_low >= 0.75
                        and bool(_vf_result_lowconf.get("is_relevant"))
                    )
                    _lowconf_title_supported = bool(
                        final_title and self._has_strong_title_support(ctx, final_title)
                    )
                    _lowconf_strong_anchor = str(vf_anchor or "").lower() in {
                        "character_mention",
                        "character_title_link",
                        "plot_mention",
                        "title_abbrev_mention",
                        "body_abbrev_mention",
                        "title_mention",
                    }
                    _lowconf_abbrev_verified = bool(
                        _vf_result_lowconf.get("is_relevant")
                        and _lowconf_title_supported
                        and (
                            vf_title_abbrev_mentioned
                            or vf_body_abbrev_mentioned
                            or vf_matched_alias
                        )
                        and (
                            vf_decode_verified
                            or (
                                vf_decoded_term
                                and re.sub(r"[^\w가-힣]", "", vf_decoded_term).lower()
                                == re.sub(r"[^\w가-힣]", "", str(final_title or "")).lower()
                            )
                        )
                        and _lowconf_strong_anchor
                    )
                    _abbrev_lowconf_exempt = False
                    if final_title:
                        _abbrev_lowconf_exempt = self._has_curated_alias_guard_exception(
                            ctx,
                            final_title,
                            decoder_out=decoder_out,
                            verifier_out=verifier_out,
                        )
                        if _abbrev_lowconf_exempt:
                            print(
                                f"[{_ts()}][{self.emoji}] 🔑 저신뢰 차단 면제: "
                                f"등록 약칭 + 독립 작품 앵커 확인 → 저신뢰 차단 건너뜀",
                                file=sys.stderr,
                            )
                    _lowconf_abbrev_anchor_only = str(vf_anchor or "").lower() in {
                        "title_abbrev_mention",
                        "body_abbrev_mention",
                    }
                    if (
                        _lowconf_abbrev_verified
                        and _lowconf_abbrev_anchor_only
                        and not _abbrev_lowconf_exempt
                    ):
                        _lowconf_abbrev_verified = False

                    if _abbrev_lowconf_exempt:
                        # KNOWN_ABBREVIATIONS 면제 — Arbiter LLM의 원래 판정 유지
                        print(
                            f"[{_ts()}][{self.emoji}] ⚠️ 저신뢰 매칭 감지 but KNOWN_ABBREVIATIONS 면제: "
                            f"Decoder conf={dc_overall_conf}, Verifier grounded={vf_grounded} "
                            f"→ '{final_title}' 유지",
                            file=sys.stderr,
                        )
                    elif vf_is_high and verifier_out.get("verification_result", {}).get("is_relevant"):
                        # Verifier가 High confidence로 is_relevant=True → 차단하지 않고 경고만
                        print(
                            f"[{_ts()}][{self.emoji}] ⚠️ 저신뢰 매칭 감지 but Verifier High 존중: "
                            f"Decoder conf={dc_overall_conf}, Verifier conf={vf_conf} "
                            f"→ '{final_title}' 유지",
                            file=sys.stderr,
                        )
                    elif _cross_strong:
                        print(
                            f"[{_ts()}][{self.emoji}] ⚠️ 저신뢰 매칭 감지 but cross-expert strong 존중: "
                            f"gk={_gk_post_type}, discourse={_disc_domain}/{_disc_intent}, "
                            f"synth_conf={_sy_conf_low:.2f} → '{final_title}' 유지",
                            file=sys.stderr,
                        )
                    elif _lowconf_abbrev_verified:
                        print(
                            f"[{_ts()}][{self.emoji}] ⚠️ 저신뢰 매칭 감지 but 축약어 검증+강증거 존중: "
                            f"anchor={vf_anchor}, alias={vf_matched_alias or '-'}, "
                            f"decode_verified={vf_decode_verified}, title_supported={_lowconf_title_supported} "
                            f"→ '{final_title}' 유지",
                            file=sys.stderr,
                        )
                    else:
                        print(
                            f"[{_ts()}][{self.emoji}] 🛡️ 저신뢰 매칭 차단: "
                            f"Decoder conf={dc_overall_conf}, Verifier grounded={vf_grounded}, anchor={vf_anchor} "
                            f"→ '{final_title}' → is_relevant=false",
                            file=sys.stderr,
                        )
                        decision["is_relevant"] = False
                        decision["is_novel_discussion"] = False
                        decision["official_title"] = None
                        decision["official_novel_title"] = None
                        decision["confidence"] = "Low"
                        if decision.get("discussion_type") in (
                            "general", "review", "spoiler", "anticipation",
                            "meme", "character_talk", "general_discussion",
                        ):
                            decision["discussion_type"] = "noise"
                        decision["notes"] = (
                            f"[저신뢰 차단] Decoder({dc_overall_conf}) + Verifier(grounded={vf_grounded}) "
                            f"→ '{final_title}' 매칭 증거 부족. "
                            + decision.get("notes", "")
                        )
                        decision["final_reasoning"] = self._synthesize_evidence_reason(
                            ctx, "저신뢰차단", False
                        )
                        if decision.get("reason"):
                            decision["reason"] = decision["final_reasoning"]
            elif (
                final_title
                and decision.get("is_relevant")
                and decision.get("_verifier_veto_exempt")
            ):
                print(
                    f"[{_ts()}][{self.emoji}] 🔒 저신뢰 차단 스킵: "
                    f"Verifier 거부권 면제 플래그 유지 ('{final_title}')",
                    file=sys.stderr,
                )

            # 🧠 비하드코딩 최종 보정: 전문가 가설 점수 기반으로 담론 타입 재검증
            _hypothesis_board = self._apply_hypothesis_guard(
                ctx=ctx,
                decision=decision,
                gatekeeper_out=gatekeeper_out,
                decoder_out=decoder_out,
                verifier_out=verifier_out,
                discourse_out=discourse_out,
                synthesizer_out=synthesizer_out,
            )
            if isinstance(_hypothesis_board, dict):
                decision["_hypothesis_top"] = _hypothesis_board.get("top_label")
                decision["_hypothesis_margin"] = round(float(_hypothesis_board.get("margin", 0.0)), 4)

            # is_relevant=false일 때 작품형 discussion_type이 남는 정합성 오류 방지
            if decision.get("is_relevant") is False and decision.get("discussion_type") in (
                "general", "review", "spoiler", "anticipation",
                "meme", "character_talk", "general_discussion",
            ):
                prev_dt = decision.get("discussion_type")
                decision["discussion_type"] = "noise"
                print(
                    f"[{_ts()}][{self.emoji}] ⚠️ is_relevant=false 정합성 교정: "
                    f"discussion_type '{prev_dt}' → 'noise'",
                    file=sys.stderr,
                )

            # 최종 비관련 판정이면 작품 식별 필드는 비워 정합성을 보장한다.
            if decision.get("is_relevant") is False:
                if decision.get("official_title") or decision.get("official_novel_title"):
                    print(
                        f"[{_ts()}][{self.emoji}] 🧹 비관련 정합성 교정: "
                        f"official_title/heretic_url 제거",
                        file=sys.stderr,
                    )
                decision["official_title"] = None
                decision["official_novel_title"] = None
                decision["heretic_url"] = None
            
            # 🆕 FIX-6b: 비소설 미디어(만화/웹툰) 감지 가드
            # 제목+본문+댓글에 시각 미디어 지표가 2개 이상이면 noise 처리
            if decision.get("is_relevant") is True:
                _vm_post_data = getattr(ctx, "post_data", {}) or {}
                _vm_title = str(_vm_post_data.get("title") or getattr(ctx, "title", "") or "")
                _vm_body = " ".join(
                    str((b.get("text") or "") if isinstance(b, dict) else str(b or ""))
                    for b in (_vm_post_data.get("content_blocks") or [])
                )
                _vm_comments = " ".join(
                    c for c in (getattr(ctx, "comments", None) or [])
                    if isinstance(c, str)
                )
                _vm_all_text = _vm_title + " " + _vm_body + " " + _vm_comments
                _vm_visual_keywords = {"그림체", "작화", "정액", "채색", "선화", "컷분할"}
                _vm_hit_count = sum(1 for kw in _vm_visual_keywords if kw in _vm_all_text)
                if _vm_hit_count >= 2:
                    print(
                        f"[{_ts()}][{self.emoji}] 🛡️ 비소설 미디어 감지: "
                        f"시각 미디어 키워드 {_vm_hit_count}개 → noise 처리 "
                        f"(title='{decision.get('official_title')}')",
                        file=sys.stderr,
                    )
                    decision["is_relevant"] = False
                    decision["discussion_type"] = "noise"
                    decision["official_title"] = None
                    decision["official_novel_title"] = None
                    decision["heretic_url"] = None
                    decision["confidence"] = "None"
                    decision["notes"] = (
                        f"[비소설 미디어 감지] 본문/댓글에 시각 미디어 지표({_vm_hit_count}개) 발견. "
                        f"만화/웹툰 등 비소설 콘텐츠로 판정. " + (decision.get("notes") or "")
                    )
            
            # ━━ 개선: evidence bucket 기반 최종 검증 ━━
            # is_relevant=true인데 해당 후보의 본문 증거(post_spans)가 0개이면 경고/차단
            _final_title_eb = decision.get("official_title") or decision.get("official_novel_title")
            if (
                decision.get("is_relevant") is True
                and _final_title_eb
                and hasattr(ctx, 'candidate_evidence')
                and ctx.candidate_evidence
            ):
                _bucket = ctx.get_candidate_evidence(_final_title_eb)
                _post_ev_count = len(_bucket.get("post_spans", []))
                _search_ev_count = len(_bucket.get("search_snippets", []))
                _official_ev_count = len(_bucket.get("official_urls", []))
                
                if _post_ev_count == 0 and _official_ev_count == 0:
                    # 🆕 FIX-2: LLM reasoning 보호 — evidence_chain에 high-weight 항목이
                    # 충분히 있으면 LLM의 판정을 신뢰하고 교체하지 않음
                    _eb_evidence_chain = decision.get("evidence_chain") or []
                    _eb_high_weight_count = sum(
                        1 for _ec in _eb_evidence_chain
                        if isinstance(_ec, dict) and str(_ec.get("weight") or "").lower() == "high"
                    )
                    if _eb_high_weight_count >= 2:
                        print(
                            f"[{_ts()}][{self.emoji}] 🛡️ LLM 고신뢰 reasoning 보호: "
                            f"'{_final_title_eb}' evidence_chain high={_eb_high_weight_count}건 "
                            f"→ bucket 증거 부족이지만 LLM 판정 유지 (confidence→Medium)",
                            file=sys.stderr,
                        )
                        decision["confidence"] = "Medium"
                    else:
                        pass  # 기존 로직 진행 (아래에서 Decoder+Verifier 합의 교체 시도)

                if _post_ev_count == 0 and _official_ev_count == 0 and not (
                    sum(
                        1 for _ec in (decision.get("evidence_chain") or [])
                        if isinstance(_ec, dict) and str(_ec.get("weight") or "").lower() == "high"
                    ) >= 2
                ):
                    # 증거 부족한 제목 → Decoder+Verifier 합의 제목으로 교체 시도
                    # 예: Synthesizer가 나무위키 검색 결과에 오염되어 엉뚱한 제목 채택,
                    #     Decoder+Verifier는 올바른 제목에 합의한 경우 → 합의 제목으로 복구
                    _eb_decoder_titles = set()
                    if decoder_out:
                        _eb_overall = decoder_out.get("overall_best_match") or {}
                        if isinstance(_eb_overall, dict):
                            _eb_ov_title = _eb_overall.get("title")
                            if _eb_ov_title:
                                _eb_decoder_titles.add(_eb_ov_title)
                        for _eb_term in decoder_out.get("decoded_terms") or []:
                            _eb_bm = _eb_term.get("best_match") or {}
                            if _eb_bm.get("title") and not _eb_term.get("is_author_name"):
                                _eb_decoder_titles.add(_eb_bm["title"])
                    _eb_verifier_title = None
                    _eb_vn = {}
                    if vf_result:
                        if isinstance(vf_result, dict):
                            _eb_verifier_title = (
                                vf_result.get("verified_title")
                                or vf_result.get("title")
                            )
                        _eb_vn = vf_result.get("novel_identity") or {}
                        if isinstance(_eb_vn, dict):
                            _eb_verifier_title = (
                                _eb_vn.get("official_novel_title")
                                or _eb_vn.get("official_title")
                                or _eb_vn.get("title")
                                or _eb_verifier_title
                            )

                    # Decoder+Verifier 합의 제목이 현재 제목과 다르고 증거가 있으면 교체
                    _eb_consensus = None
                    if _eb_verifier_title and _eb_verifier_title in _eb_decoder_titles:
                        _eb_consensus = _eb_verifier_title
                    elif _eb_verifier_title and _eb_decoder_titles:
                        # 유사도 0.85 이상이면 합의로 간주
                        from difflib import SequenceMatcher
                        for _eb_dt in _eb_decoder_titles:
                            if SequenceMatcher(
                                None,
                                _eb_verifier_title.replace(" ", ""),
                                _eb_dt.replace(" ", ""),
                            ).ratio() >= 0.85:
                                _eb_consensus = _eb_verifier_title
                                break

                    # 합의가 없어도 Verifier 제목 증거가 현재 제목보다 강하면 Verifier 우선 복구
                    if (
                        (not _eb_consensus)
                        and _eb_verifier_title
                        and (_eb_verifier_title != _final_title_eb)
                    ):
                        def _norm_local(s: Any) -> str:
                            return re.sub(r"[^\uac00-\ud7a3A-Za-z0-9]", "", str(s or "")).lower()

                        def _domain_tokens(s: Any) -> set[str]:
                            _n = _norm_local(s)
                            _tokens = {
                                "무림", "게임", "헌터", "현판", "아카데미",
                                "회귀", "빙의", "백합", "BL", "스포츠",
                            }
                            return {t for t in _tokens if t in _n}

                        _post_blob = _norm_local((post_data or {}).get("title") or "")
                        for _blk in ((post_data or {}).get("content_blocks") or []):
                            if isinstance(_blk, dict):
                                _post_blob += " " + _norm_local(_blk.get("text") or "")
                            elif isinstance(_blk, str):
                                _post_blob += " " + _norm_local(_blk)

                        _cur_dom = _domain_tokens(_final_title_eb)
                        _vf_dom = _domain_tokens(_eb_verifier_title)
                        _domain_conflict = bool(_cur_dom and _vf_dom and _cur_dom.isdisjoint(_vf_dom))
                        _vf_dom_supported_by_post = any(tok in _post_blob for tok in _vf_dom)
                        if _domain_conflict and (not _vf_dom_supported_by_post):
                            print(
                                f"[{_ts()}][{self.emoji}] 🚫 Verifier 우선 복구 보류: "
                                f"domain_conflict cur={sorted(_cur_dom)} vf={sorted(_vf_dom)} "
                                f"(post_support=False, final='{_final_title_eb}', verifier='{_eb_verifier_title}')",
                                file=sys.stderr,
                            )
                            _eb_verifier_title = None

                    if (
                        (not _eb_consensus)
                        and _eb_verifier_title
                        and (_eb_verifier_title != _final_title_eb)
                    ):
                        _cur_url_lock = str(decision.get("heretic_url") or "").strip()
                        _vf_url_lock = ""
                        if isinstance(vf_result, dict):
                            _vf_url_lock = str(
                                (vf_result.get("novel_identity") or {}).get("heretic_url") or ""
                            ).strip()
                        if (
                            _cur_url_lock
                            and _vf_url_lock
                            and self._is_novel_detail_url(_cur_url_lock)
                            and self._is_novel_detail_url(_vf_url_lock)
                            and (_cur_url_lock != _vf_url_lock)
                        ):
                            print(
                                f"[{_ts()}][{self.emoji}] 🛡️ Verifier 우선 복구 차단: "
                                f"current heretic_url='{_cur_url_lock}' ≠ verifier heretic_url='{_vf_url_lock}' "
                                f"(final='{_final_title_eb}', verifier='{_eb_verifier_title}')",
                                file=sys.stderr,
                            )
                            _eb_verifier_title = None

                    if (
                        (not _eb_consensus)
                        and _eb_verifier_title
                        and (_eb_verifier_title != _final_title_eb)
                    ):
                        _eb_alt_bucket = ctx.get_candidate_evidence(_eb_verifier_title)
                        _eb_alt_post = len(_eb_alt_bucket.get("post_spans", []))
                        _eb_alt_search = len(_eb_alt_bucket.get("search_snippets", []))
                        _eb_alt_official = len(_eb_alt_bucket.get("official_urls", []))

                        _vf_conf = ""
                        if isinstance(vf_result, dict):
                            _vf_conf = str(
                                vf_result.get("confidence")
                                or vf_result.get("final_confidence")
                                or ""
                            ).lower()
                        if not _vf_conf and isinstance(_eb_vn, dict):
                            _vf_conf = str(_eb_vn.get("confidence") or "").lower()
                        _vf_strong = _vf_conf in ("high", "max", "medium")

                        if (
                            _eb_alt_post > 0
                            or _eb_alt_official > 0
                            or (_vf_strong and _eb_alt_search > _search_ev_count)
                        ):
                            print(
                                f"[{_ts()}][{self.emoji}] 🔄 evidence bucket Verifier 우선 복구: "
                                f"'{_final_title_eb}' (post={_post_ev_count}, search={_search_ev_count}, official={_official_ev_count}) "
                                f"→ '{_eb_verifier_title}' "
                                f"(post={_eb_alt_post}, search={_eb_alt_search}, official={_eb_alt_official}, vf_conf={_vf_conf or 'unknown'})",
                                file=sys.stderr,
                            )
                            _eb_consensus = _eb_verifier_title

                    if (
                        _eb_consensus
                        and _eb_consensus != _final_title_eb
                    ):
                        # 합의 제목의 evidence bucket 확인
                        _eb_alt_bucket = ctx.get_candidate_evidence(_eb_consensus)
                        _eb_alt_post = len(_eb_alt_bucket.get("post_spans", []))
                        _eb_alt_search = len(_eb_alt_bucket.get("search_snippets", []))
                        _eb_alt_official = len(_eb_alt_bucket.get("official_urls", []))

                        if _eb_alt_post > 0 or _eb_alt_official > 0 or _eb_alt_search > _search_ev_count:
                            # 합의 제목에 더 많은 증거 → 교체
                            _eb_consensus_clean = self._sanitize_site_noise_title(_eb_consensus)
                            if _eb_consensus_clean != _eb_consensus:
                                print(
                                    f"[{_ts()}][{self.emoji}] 🛡️ evidence bucket 합의제목 정제: "
                                    f"'{_eb_consensus}' → '{_eb_consensus_clean}'",
                                    file=sys.stderr,
                                )
                            print(
                                f"[{_ts()}][{self.emoji}] 🔄 evidence bucket 기반 제목 교체: "
                                f"'{_final_title_eb}' (증거 0) → '{_eb_consensus_clean}' "
                                f"(post={_eb_alt_post}, search={_eb_alt_search}, official={_eb_alt_official}) "
                                f"[Decoder+Verifier 합의]",
                                file=sys.stderr,
                            )
                            decision["official_title"] = _eb_consensus_clean
                            decision["official_novel_title"] = _eb_consensus_clean
                            _final_title_eb = _eb_consensus_clean
                            # 교체 후에도 confidence는 합의 강도에 따라 결정
                            decision["confidence"] = "Medium"
                        else:
                            # 합의 제목도 증거 부족 → 교체하지 않고 Low
                            print(
                                f"[{_ts()}][{self.emoji}] 📊 evidence bucket 검증: "
                                f"'{_final_title_eb}' 증거 부족, 합의 제목 '{_eb_consensus}'도 증거 부족 → Low",
                                file=sys.stderr,
                            )
                            decision["confidence"] = "Low"
                    elif _search_ev_count > 0:
                        # 합의 없지만 검색 증거만 있음 → confidence 하향
                        _old_conf = decision.get("confidence", "Low")
                        if _old_conf in ("High", "high", "Max", "max"):
                            decision["confidence"] = "Low"
                            print(
                                f"[{_ts()}][{self.emoji}] 📊 evidence bucket 검증: "
                                f"'{_final_title_eb}' → 본문증거 0개, 검색만 {_search_ev_count}개 "
                                f"→ confidence: {_old_conf}→Low (검색만으로 확정 불가)",
                                file=sys.stderr,
                            )
                    else:
                        # 증거 전혀 없음 → 환각 의심
                        # 합의 제목도 없으면 Low 유지
                        if _eb_consensus and _eb_consensus != _final_title_eb:
                            # 합의 제목은 있지만 증거가 없는 케이스 (위에서 처리)
                            pass
                        else:
                            print(
                                f"[{_ts()}][{self.emoji}] 📊 evidence bucket 검증: "
                                f"'{_final_title_eb}' → 증거 버킷 완전 비어있음 → is_relevant 유지하되 Low",
                                file=sys.stderr,
                            )
                            decision["confidence"] = "Low"

            # Phase31: Verifier critical counter_arguments → confidence 다운그레이드
            # novel_identity.confidence가 High여도 critical counter가 있으면
            # 실질적으론 Medium 수준이므로 High-title Lock이 과도하게 작동하는 것을 방지
            _vf_ni_for_crit = vf_result.get("novel_identity") or {}
            _vf_counters_for_crit = (vf_result.get("verification_result") or {}).get("counter_arguments") or []
            _vf_has_critical_counter = any(
                isinstance(_ca, dict)
                and str(_ca.get("severity", "")).lower() == "critical"
                for _ca in _vf_counters_for_crit
            )
            if _vf_has_critical_counter:
                _orig_ni_conf = str(_vf_ni_for_crit.get("confidence") or "").strip().lower()
                if _orig_ni_conf in ("high", "max"):
                    _vf_ni_for_crit["confidence"] = "Medium"
                    _vf_ni_for_crit["_confidence_downgraded_by_critical"] = True
                    print(
                        f"[{_ts()}][{self.emoji}] ⚠️ Verifier critical counter detected → "
                        f"novel_identity.confidence downgraded: {_orig_ni_conf} → Medium",
                        file=sys.stderr,
                    )

            # 🧷 Verifier High-title lock:
            # 강한 Verifier 근거(High + 앵커/증거 버킷)가 존재하면
            # Synthesizer/Arbiter 드리프트로 다른 제목이 최종 확정되는 것을 차단한다.
            _vf_title_lock2 = str(
                (vf_result.get("novel_identity") or {}).get("official_novel_title")
                or (vf_result.get("novel_identity") or {}).get("official_title")
                or vf_result.get("verified_title")
                or ""
            ).strip()
            _vf_conf_lock2 = str(
                (vf_result.get("novel_identity") or {}).get("confidence")
                or verifier_out.get("final_confidence")
                or ""
            ).strip().lower()
            _vf_anchor_lock2 = str(
                (vf_result.get("grounding_check") or {}).get("anchor_found")
                or ""
            ).strip().lower()
            _vf_is_rel_lock2 = (vf_result.get("is_relevant") is True)
            _vf_post2, _vf_snip2, _vf_off2 = _title_evidence_counts(_vf_title_lock2)
            _vf_anchor_is_strong2 = _vf_anchor_lock2 in {
                "title_mention", "plot_mention", "character_title_link", "character_mention",
            }
            _vf_supported2 = bool(
                _title_has_supported_evidence(_vf_title_lock2, require_post_or_official=True)
                or (_vf_anchor_is_strong2 and _vf_snip2 >= 2)
            )
            _vf_domain_conflict2 = False
            try:
                _post_title_lock2 = str((getattr(ctx, "post_data", {}) or {}).get("title") or "")
                if _vf_title_lock2 and _post_title_lock2:
                    _vf_domain_conflict2 = _has_domain_conflict_for_mapping(_post_title_lock2, _vf_title_lock2)
            except Exception:
                _vf_domain_conflict2 = False
            _null_block_reasons2 = decision.get("_title_null_block_reasons")
            if not isinstance(_null_block_reasons2, list):
                _null_block_reasons2 = []
            _has_hard_null_block2 = any(
                _r in {"author_criticism_guard", "recommendation_guard", "temporal_reference_guard", "post_title_theft_guard"}
                for _r in _null_block_reasons2
            )
            _memory_query_vf_lock_block2 = bool(
                _vf_title_lock2
                and self._should_block_memory_query_forced_upgrade(
                    ctx,
                    verifier_out,
                    _vf_title_lock2,
                )
            )
            if _memory_query_vf_lock_block2:
                _null_block_reasons2.append("memory_query_forced_upgrade_guard")
                decision["_title_null_block_reasons"] = sorted(set(_null_block_reasons2))
                _has_hard_null_block2 = True
                print(
                    f"[{_ts()}][{self.emoji}] 🛡️ Verifier High-title lock 차단: "
                    f"title='{_vf_title_lock2}', reason=memory_query_forced_upgrade_guard",
                    file=sys.stderr,
                )
            _vf_skip_for_author_new_work2 = False
            _vf_skip_for_author_talk2 = False
            _vf_skip_for_genre_talk2 = False
            try:
                _post_data_lock2 = (getattr(ctx, "post_data", {}) or {})
                _post_title_lock2_raw = str(_post_data_lock2.get("title") or "")
                _post_title_lock2_norm = _post_title_lock2_raw.lower().replace(" ", "")
                _temporal_kws_lock2 = ["신작", "최신작", "새작품", "이번작", "전작", "차기작", "신간"]
                _launch_kws_lock2 = ["스타트", "초반", "초반부", "첫인상", "첫화", "도입", "출발"]
                _has_temporal_lock2 = any(_kw in _post_title_lock2_norm for _kw in _temporal_kws_lock2)
                _has_launch_lock2 = any(_kw in _post_title_lock2_norm for _kw in _launch_kws_lock2)
                _author_lead_lock2 = bool(
                    re.match(
                        r"^\s*[가-힣A-Za-z0-9]{2,12}(?:꺼)?\s*(?:신작|최신작|새작품|이번작|전작|차기작|신간)",
                        _post_title_lock2_raw,
                    )
                )
                _has_author_new_work_lock2 = _has_temporal_lock2 or (_author_lead_lock2 and _has_launch_lock2)
                if _vf_title_lock2 and _vf_anchor_lock2 == "author_mention" and _has_author_new_work_lock2:
                    _body_parts_lock2 = []
                    for _blk in _post_data_lock2.get("content_blocks", []):
                        if isinstance(_blk, dict) and _blk.get("text"):
                            _body_parts_lock2.append(_blk["text"])
                    _main_text_lock2 = " ".join(_body_parts_lock2).lower().replace(" ", "")
                    _comments_lock2 = getattr(ctx, "comments", []) or []
                    _full_text_lock2 = " ".join(_body_parts_lock2 + list(_comments_lock2)).lower().replace(" ", "")
                    _vf_title_clean2 = _vf_title_lock2.replace(" ", "").lower()
                    _vf_title_in_main_text2 = bool(_vf_title_clean2 and _vf_title_clean2 in _main_text_lock2)
                    _vf_title_in_text2 = bool(_vf_title_clean2 and _vf_title_clean2 in _full_text_lock2)
                    _vf_abbrev_in_text2 = False
                    _vf_abbrev_in_main_text2 = False
                    if (not _vf_title_in_text2) and decoder_out:
                        for _dt_lock2 in (decoder_out.get("decoded_terms") or []):
                            _bm_lock2 = _dt_lock2.get("best_match") or {}
                            _bm_title_lock2 = str(_bm_lock2.get("title") or "").replace(" ", "").lower()
                            if _bm_title_lock2 != _vf_title_clean2:
                                continue
                            _orig_lock2 = str(_dt_lock2.get("original") or "").replace(" ", "").lower()
                            _orig_surface_lock2 = str(_dt_lock2.get("original") or "")
                            _orig_norm_lock2 = _orig_surface_lock2.replace(" ", "").lower()
                            _orig_is_author_new_work_lock2 = bool(
                                _orig_surface_lock2
                                and (
                                    any(_kw in _orig_norm_lock2 for _kw in _temporal_kws_lock2)
                                    or re.match(
                                        r"^\s*[가-힣A-Za-z0-9]{2,12}(?:꺼)?\s*(?:신작|최신작|새작품|이번작|전작|차기작|신간)",
                                        _orig_surface_lock2,
                                    )
                                )
                            )
                            if (
                                _orig_norm_lock2
                                and len(_orig_norm_lock2) >= 2
                                and _orig_norm_lock2 in _full_text_lock2
                                and not _orig_is_author_new_work_lock2
                            ):
                                _vf_abbrev_in_text2 = True
                            if (
                                _orig_norm_lock2
                                and len(_orig_norm_lock2) >= 2
                                and _orig_norm_lock2 in _main_text_lock2
                                and not _orig_is_author_new_work_lock2
                            ):
                                _vf_abbrev_in_main_text2 = True
                            if _vf_abbrev_in_text2 and _vf_abbrev_in_main_text2:
                                break
                    _vf_author_surfaces_lock2 = set()
                    try:
                        for _dt_lock2 in (decoder_out.get("decoded_terms") or []):
                            if not isinstance(_dt_lock2, dict) or not _dt_lock2.get("is_author_name"):
                                continue
                            for _cand_surface in (
                                _dt_lock2.get("original"),
                                (_dt_lock2.get("author_info") or {}).get("name"),
                                ((vf_result.get("author_info") or {}).get("detected_author")),
                            ):
                                _cand_norm = str(_cand_surface or "").replace(" ", "").lower()
                                if _cand_norm:
                                    _vf_author_surfaces_lock2.add(_cand_norm)
                    except Exception:
                        _vf_author_surfaces_lock2 = set()
                    _vf_title_is_author_surface2 = _vf_title_clean2 in _vf_author_surfaces_lock2
                    _vf_title_grounded_in_main_post2 = _vf_title_in_main_text2 or _vf_abbrev_in_main_text2
                    if (not _vf_title_grounded_in_main_post2) or _vf_title_is_author_surface2:
                        _vf_skip_for_author_new_work2 = True
                        print(
                            f"[{_ts()}][{self.emoji}] 🛡️ Verifier High-title lock 스킵: "
                            f"author_new_work/title_unresolved (title='{_vf_title_lock2}', "
                            f"anchor={_vf_anchor_lock2}, title_in_main={_vf_title_in_main_text2}, "
                            f"abbrev_in_main={_vf_abbrev_in_main_text2}, author_surface={_vf_title_is_author_surface2})",
                            file=sys.stderr,
                        )
            except Exception:
                _vf_skip_for_author_new_work2 = False
            try:
                _decision_dt_lock2 = str(decision.get("discussion_type") or "").strip().lower()
                _raw_llm_title_lock2 = str(decision.get("_raw_llm_title") or "").strip()
                _raw_llm_rel_lock2 = decision.get("_raw_llm_relevant")
                _raw_llm_dt_lock2 = str(decision.get("_raw_llm_discussion_type") or "").strip().lower()
                _raw_llm_author_null2 = (
                    _vf_title_lock2
                    and not _raw_llm_title_lock2
                    and _raw_llm_dt_lock2 in {"author_talk", "author_criticism"}
                    and _raw_llm_rel_lock2 is not True
                )
                if (
                    _raw_llm_author_null2
                    or (
                        _vf_title_lock2
                        and _decision_dt_lock2 in {"author_talk", "author_criticism"}
                        and not _raw_llm_title_lock2
                    )
                ):
                    _vf_skip_for_author_talk2 = True
                    print(
                        f"[{_ts()}][{self.emoji}] 🛡️ Verifier High-title lock 스킵: "
                        f"arbiter_author_talk_null "
                        f"(title='{_vf_title_lock2}', raw_dt={_raw_llm_dt_lock2 or 'none'}, dt={_decision_dt_lock2 or 'none'})",
                        file=sys.stderr,
                    )
            except Exception:
                _vf_skip_for_author_talk2 = False
            try:
                _dw_lock2 = str(getattr(ctx, "discourse_warning", "") or "").lower()
                _genre_warn_lock2 = any(
                    _tok in _dw_lock2
                    for _tok in (
                        "genre_discussion",
                        "discuss_genre",
                        "trope_discussion",
                        "genre_opinion",
                        "community_banter",
                        "title_body_mismatch",
                        "incoherent_post",
                    )
                )
                _vf_anchor_weak2 = _vf_anchor_lock2 in {
                    "none",
                    "search_only",
                    "",
                    "title_mention",
                    "title_abbrev_mention",
                    "body_abbrev_mention",
                    "community_mention",
                }
                _vf_has_verified_char_links2 = bool(getattr(ctx, "verified_character_work_links", []))
                _post_data_lock2 = (getattr(ctx, "post_data", {}) or {})
                _body_parts_lock2 = []
                for _blk in _post_data_lock2.get("content_blocks", []):
                    if isinstance(_blk, dict) and _blk.get("text"):
                        _body_parts_lock2.append(_blk["text"])
                _comments_lock2 = getattr(ctx, "comments", []) or []
                _full_text_lock2 = " ".join(_body_parts_lock2 + list(_comments_lock2)).lower().replace(" ", "")
                _vf_title_clean2 = _vf_title_lock2.replace(" ", "").lower()
                _vf_title_in_text2 = bool(_vf_title_clean2 and _vf_title_clean2 in _full_text_lock2)
                _gk_lock2 = gatekeeper_out or {}
                _gk_ctx_lock2 = (_gk_lock2.get("context_clues") or {}) if isinstance(_gk_lock2, dict) else {}
                _has_episode_ref_lock2 = bool(_gk_ctx_lock2.get("has_episode_reference"))
                if (
                    _vf_title_lock2
                    and _genre_warn_lock2
                    and _vf_anchor_weak2
                    and not _vf_title_in_text2
                    and not _vf_has_verified_char_links2
                    and not _has_episode_ref_lock2
                ):
                    _vf_skip_for_genre_talk2 = True
                    print(
                        f"[{_ts()}][{self.emoji}] 🛡️ Verifier High-title lock 스킵: "
                        f"genre_talk/weak_anchor (title='{_vf_title_lock2}', anchor={_vf_anchor_lock2 or 'none'})",
                        file=sys.stderr,
                    )
            except Exception:
                _vf_skip_for_genre_talk2 = False

            if (
                _vf_title_lock2
                and _vf_is_rel_lock2
                and _st_conf_num(_vf_conf_lock2) >= 3
                and _vf_supported2
                and (not _vf_domain_conflict2)
                and (not _has_hard_null_block2)
                and (not _vf_skip_for_author_new_work2)
                and (not _vf_skip_for_author_talk2)
                and (not _vf_skip_for_genre_talk2)
                and not self._curated_alias_lacks_contextual_work_anchor(
                    ctx,
                    _vf_title_lock2,
                    verifier_out=verifier_out,
                )
                and (not decision.get("_meme_blocked"))  # Phase31: 밈 가드 차단 존중
            ):
                _cur_title_lock2 = str(
                    decision.get("official_title")
                    or decision.get("official_novel_title")
                    or ""
                ).strip()
                _cur_supported2 = bool(
                    _title_has_supported_evidence(_cur_title_lock2, require_post_or_official=True)
                    or (_cur_title_lock2 and self._has_strong_title_support(ctx, _cur_title_lock2))
                )
                _needs_lock_apply = (
                    (decision.get("is_relevant") is not True)
                    or (not _cur_title_lock2)
                    or (
                        _st_norm(_cur_title_lock2) != _st_norm(_vf_title_lock2)
                        and (not _cur_supported2)
                    )
                )
                _event_meta_lock_block = bool(
                    self._looks_like_platform_event_meta_post(ctx)
                    and not self._title_mentioned_in_post_main_context(ctx, _vf_title_lock2)
                )
                if _event_meta_lock_block:
                    print(
                        f"[{_ts()}][{self.emoji}] 🛡️ Verifier High-title lock 차단: "
                        f"title='{_vf_title_lock2}', reason=platform_event_meta",
                        file=sys.stderr,
                    )
                if _needs_lock_apply:
                    if _event_meta_lock_block:
                        pass
                    else:
                        _prev_title_lock2 = _cur_title_lock2 or "None"
                        decision["is_relevant"] = True
                        decision["is_novel_discussion"] = True
                        decision["official_title"] = _vf_title_lock2
                        decision["official_novel_title"] = _vf_title_lock2
                        _vf_url_lock2 = (vf_result.get("novel_identity") or {}).get("heretic_url")
                        if _vf_url_lock2 and isinstance(_vf_url_lock2, str) and _vf_url_lock2.startswith("http"):
                            decision["heretic_url"] = _vf_url_lock2
                        if _st_conf_num(decision.get("confidence")) < 3:
                            decision["confidence"] = "High"
                        if decision.get("discussion_type") in {
                            "noise", "off_topic", "meta", "community_banter",
                            "genre_opinion", "trope_discussion", "recommendation", "image_post",
                        }:
                            decision["discussion_type"] = "general"
                        decision["final_reasoning"] = self._synthesize_evidence_reason(ctx, "verifier_high_lock", True)
                        if decision.get("reason"):
                            decision["reason"] = decision["final_reasoning"]
                        print(
                            f"[{_ts()}][{self.emoji}] 🧷 Verifier High-title lock 적용: "
                            f"'{_prev_title_lock2}' → '{_vf_title_lock2}' "
                            f"(anchor={_vf_anchor_lock2 or 'none'}, post={_vf_post2}, search={_vf_snip2}, official={_vf_off2})",
                            file=sys.stderr,
                        )

            metadata_synthesis = result.get("metadata_synthesis")
            if not isinstance(metadata_synthesis, dict):
                metadata_synthesis = {}
                result["metadata_synthesis"] = metadata_synthesis

            vf_author_info = vf_result.get("author_info") or {}
            if not isinstance(vf_author_info, dict):
                vf_author_info = {}
            _gk_for_author = ctx.get_expert_output(ExpertType.GATEKEEPER) or {}
            if not isinstance(_gk_for_author, dict):
                _gk_for_author = {}
            _gk_entities_for_author = _gk_for_author.get("detected_entities") or {}
            if not isinstance(_gk_entities_for_author, dict):
                _gk_entities_for_author = {}
            _gk_possible_authors = [
                str(a).strip()
                for a in (_gk_entities_for_author.get("possible_authors") or [])
                if isinstance(a, str) and str(a).strip()
            ]
            _post_data_for_author = (getattr(ctx, "post_data", {}) or {}) if ctx is not None else {}
            _post_title_for_author = str(_post_data_for_author.get("title") or "")
            _post_body_for_author = " ".join(
                str(x).strip()
                for x in (_post_data_for_author.get("content") or [])
                if isinstance(x, str) and str(x).strip()
            )
            _post_comments_for_author = " ".join(
                str(x).strip()
                for x in (_post_data_for_author.get("comments") or [])
                if isinstance(x, str) and str(x).strip()
            )
            _post_hay_for_author = " ".join(
                [
                    _post_title_for_author,
                    _post_body_for_author,
                    _post_comments_for_author,
                ]
            )
            _post_hay_norm_for_author = re.sub(r"\s+", "", _post_hay_for_author).lower()
            _possible_author_anchor = any(
                re.sub(r"\s+", "", str(a or "")).lower() in _post_hay_norm_for_author
                for a in _gk_possible_authors
                if str(a or "").strip()
            )
            _explicit_author_signal = bool(
                re.search(
                    r"(?:\b|^)(?:작가|필명|글쓴이|연재자|저자|author)(?:\b|$)",
                    _post_hay_for_author,
                    flags=re.IGNORECASE,
                )
            )
            _author_fallback_allowed = bool(vf_author_info.get("is_author_criticism")) or (
                _explicit_author_signal and _possible_author_anchor
            )
            detected_author = str(vf_author_info.get("detected_author") or "").strip()
            _final_title_for_author_check = (
                decision.get("official_title")
                or decision.get("official_novel_title")
                or ""
            )

            if not detected_author and decoder_out:
                for term in decoder_out.get("decoded_terms") or []:
                    if not term.get("is_author_name"):
                        continue
                    author_info = term.get("author_info") or {}
                    candidate = ""
                    if isinstance(author_info, dict):
                        candidate = str(author_info.get("name") or author_info.get("author_name") or "").strip()
                    if not candidate:
                        candidate = str(term.get("original") or "").strip()
                    if candidate:
                        detected_author = candidate
                        break

            # 숫자/리비전 토큰 같은 비작가 노이즈는 제거
            _detected_author_norm = detected_author.strip().lower()
            if detected_author and (
                detected_author.isdigit()
                or _detected_author_norm.startswith("r") and _detected_author_norm[1:].isdigit()
                or _detected_author_norm.startswith("v") and _detected_author_norm[1:].isdigit()
            ):
                print(
                    f"[{_ts()}][{self.emoji}] 🧹 detected_author 노이즈 제거: '{detected_author}'",
                    file=sys.stderr,
                )
                detected_author = ""

            # Verifier/Decoder가 준 작가명이라도, 검색/페치 증거가 없으면 주입 금지
            if (
                detected_author
                and decision.get("is_relevant")
                and not self._is_author_grounded(
                    author=detected_author,
                    title=_final_title_for_author_check,
                    ctx=ctx,
                )
            ):
                print(
                    f"[{_ts()}][{self.emoji}] 🧹 detected_author 근거 부족 제거: "
                    f"'{detected_author}' (title='{_final_title_for_author_check}')",
                    file=sys.stderr,
                )
                detected_author = ""

            # 🆕 검색 결과에서 반복 패턴 기반 작가명 추출 (Decoder/Verifier 모두 실패한 경우)
            # 기본 OFF: 불충분한 검색 스니펫에서 정렬 토큰/메타 텍스트가 작가로 오인되는 사례 방지.
            _author_search_fallback_enabled = os.getenv(
                "ARBITER_ENABLE_SEARCH_AUTHOR_FALLBACK",
                "0",
            ).strip().lower() in {"1", "true", "yes", "on"}
            if not detected_author and decision.get("is_relevant") and _author_search_fallback_enabled:
                _final_title_for_author = _final_title_for_author_check
                if _final_title_for_author and _author_fallback_allowed:
                    _extracted_author = self._extract_author_from_search(
                        _final_title_for_author, ctx
                    )
                    if _extracted_author and not _extracted_author.strip().isdigit():
                        # 검색 패턴 기반 추출값도 반드시 grounding 검증 후에만 주입
                        if self._is_author_grounded(
                            author=_extracted_author,
                            title=_final_title_for_author,
                            ctx=ctx,
                        ):
                            detected_author = _extracted_author
                            print(
                                f"[{_ts()}][{self.emoji}] 🔬 검색 패턴 기반 작가명 추출: "
                                f"'{detected_author}' (제목='{_final_title_for_author}')",
                                file=sys.stderr,
                            )
                        else:
                            print(
                                f"[{_ts()}][{self.emoji}] 🧹 검색 기반 작가명 근거 부족 제거: "
                                f"'{_extracted_author}' (제목='{_final_title_for_author}')",
                                file=sys.stderr,
                            )
                    elif _extracted_author:
                            print(
                                f"[{_ts()}][{self.emoji}] 🧹 검색 기반 작가명 노이즈 제거: "
                                f"'{_extracted_author}' (제목='{_final_title_for_author}')",
                                file=sys.stderr,
                            )
                elif _final_title_for_author:
                    print(
                        f"[{_ts()}][{self.emoji}] ⏭️ 검색 기반 작가 fallback 스킵: "
                        f"author_signals_absent (title='{_final_title_for_author}')",
                        file=sys.stderr,
                    )
            elif not detected_author and decision.get("is_relevant"):
                _final_title_for_author = _final_title_for_author_check
                if _final_title_for_author:
                    print(
                        f"[{_ts()}][{self.emoji}] ⏭️ 검색 기반 작가 fallback 비활성: "
                        f"ARBITER_ENABLE_SEARCH_AUTHOR_FALLBACK=0 (title='{_final_title_for_author}')",
                        file=sys.stderr,
                    )

            if detected_author and not metadata_synthesis.get("detected_author"):
                metadata_synthesis["detected_author"] = detected_author
                print(
                    f"[{_ts()}][{self.emoji}] 🔬 metadata_synthesis.detected_author 보강: '{detected_author}'",
                    file=sys.stderr,
                )

            should_inject_author_reason = (
                decision.get("is_relevant") is True
                and bool(detected_author)
                and bool(_final_title_for_author_check)
                and bool(_author_fallback_allowed)
                and not bool(vf_author_info.get("is_author_criticism"))
                and self._is_author_grounded(
                    author=detected_author,
                    title=_final_title_for_author_check,
                    ctx=ctx,
                )
            )
            if should_inject_author_reason:
                import re as _re_author_inject
                _iga = self._korean_iga(detected_author)
                author_evidence_sentence = (
                    f"추가 근거: 검색 증거에서 '{detected_author}'{_iga} 해당 작품의 작가로 확인됨."
                )
                # decision 내부 reason이 비어있어도 Arbiter top-level final_reasoning이 있을 수 있음.
                reasoning_text = (
                    decision.get("final_reasoning")
                    or decision.get("reason")
                    or result.get("final_reasoning")
                    or result.get("reason")
                    or ""
                )
                if isinstance(reasoning_text, str):
                    reasoning_text = reasoning_text.strip()
                else:
                    reasoning_text = ""

                # reason 본문에 이미 다른 작가명이 있으면 모순 주입 금지
                _existing_author = ""
                _m_author = _re_author_inject.search(
                    r"작가\s*['\"“”]?\s*([가-힣a-zA-Z0-9_]{2,20})",
                    reasoning_text,
                )
                if _m_author:
                    _existing_author = (_m_author.group(1) or "").strip()
                if _existing_author:
                    _norm_author = lambda s: _re_author_inject.sub(r"\s+", "", str(s or "")).lower()
                    if _norm_author(_existing_author) != _norm_author(detected_author):
                        print(
                            f"[{_ts()}][{self.emoji}] 🧹 작가 근거 주입 스킵(충돌): "
                            f"reason='{_existing_author}' vs extracted='{detected_author}'",
                            file=sys.stderr,
                        )
                        # metadata에도 추출값을 남기지 않도록 정합성 유지
                        if (metadata_synthesis.get("detected_author") or "").strip() == detected_author:
                            metadata_synthesis["detected_author"] = _existing_author
                        should_inject_author_reason = False
                
                # reasoning이 비어있으면 Decoder/Verifier 정보로 reason 생성 (author 단독 문구는 제외)
                if not reasoning_text:
                    reasoning_text = self._build_rich_reason(ctx)
                
                if should_inject_author_reason and reasoning_text and "작가는 식별되지 않았으나" in reasoning_text:
                    reasoning_text = reasoning_text.replace(
                        "작가는 식별되지 않았으나",
                        f"작가 '{detected_author}'{_iga} 식별되며",
                    )
                if should_inject_author_reason and detected_author not in reasoning_text:
                    if reasoning_text:
                        if not reasoning_text.endswith((".", "!", "?")):
                            reasoning_text += "."
                        reasoning_text += " " + author_evidence_sentence
                        decision["final_reasoning"] = reasoning_text
                        print(
                            f"[{_ts()}][{self.emoji}] 🔬 final_reasoning 작가 근거 보강: '{detected_author}'",
                            file=sys.stderr,
                        )
                    else:
                        # 근거 본문 없이 작가 문구만 reason으로 쓰면 품질이 급격히 떨어지므로 스킵.
                        print(
                            f"[{_ts()}][{self.emoji}] ⚠️ 작가 근거 주입 스킵: base reasoning 없음 "
                            f"(author='{detected_author}')",
                            file=sys.stderr,
                        )
                elif should_inject_author_reason and reasoning_text:
                    decision["final_reasoning"] = reasoning_text
            
            # 🔧 Phase26-D: Arbiter 후처리 완료 후 official_title이 null이면
            # downstream(agentic_pipeline)이 Verifier로 폴백하지 않도록 플래그 설정
            # 🔧 Phase27-B: 단, suspected_titles에 High confidence 후보가 있으면 플래그를 설정하지 않음
            #   (downstream에서 suspected_titles 기반으로 title을 복구할 수 있도록 허용)
            _final_title = decision.get("official_title") or decision.get("official_novel_title")
            if not _final_title:
                _null_block_reasons = decision.get("_title_null_block_reasons")
                if not isinstance(_null_block_reasons, list):
                    _null_block_reasons = []
                _has_strong_null_block = any(
                    r in {"temporal_reference_guard", "post_title_theft_guard", "author_criticism_guard", "recommendation_guard"}
                    for r in _null_block_reasons
                )

                # 🆕 Verifier 고신뢰 복구:
                # Arbiter LLM/후처리로 title이 null이 되었더라도,
                # Verifier novel_identity가 고신뢰이고 검색 버킷 근거가 충분하면 null 고정을 해제한다.
                _vf_title_for_null = ""
                _vf_conf_for_null = ""
                _vf_anchor_for_null = ""
                _vf_url_for_null = None
                _vf_post_cnt = 0
                _vf_search_cnt = 0
                _vf_official_cnt = 0
                _vf_domain_conflict = False
                _vf_out_for_null: Dict[str, Any] = {}
                try:
                    _vf_out_for_null = ctx.get_expert_output(ExpertType.VERIFIER) or {}
                    _vf_result_for_null = _vf_out_for_null.get("verification_result") or {}
                    _vf_novel_for_null = _vf_result_for_null.get("novel_identity") or {}
                    _vf_title_for_null = str(
                        _vf_novel_for_null.get("official_novel_title")
                        or _vf_novel_for_null.get("official_title")
                        or _vf_novel_for_null.get("title")
                        or _vf_result_for_null.get("verified_title")
                        or _vf_result_for_null.get("title")
                        or ""
                    ).strip()
                    # final_confidence보다 novel_identity.confidence를 우선 사용
                    _vf_conf_for_null = str(
                        _vf_novel_for_null.get("confidence")
                        or _vf_result_for_null.get("confidence")
                        or _vf_out_for_null.get("final_confidence")
                        or ""
                    ).lower().strip()
                    _vf_anchor_for_null = str(
                        (_vf_result_for_null.get("grounding_check") or {}).get("anchor_found")
                        or ""
                    ).lower().strip()
                    _vf_url_for_null = _vf_novel_for_null.get("heretic_url")
                    if _vf_title_for_null and hasattr(ctx, "get_candidate_evidence"):
                        _vf_bucket_for_null = ctx.get_candidate_evidence(_vf_title_for_null) or {}
                        _vf_post_cnt = len((_vf_bucket_for_null or {}).get("post_spans", []))
                        _vf_search_cnt = len((_vf_bucket_for_null or {}).get("search_snippets", []))
                        _vf_official_cnt = len((_vf_bucket_for_null or {}).get("official_urls", []))
                    _post_title_for_null = str((ctx.post_data or {}).get("title") or "")
                    if _post_title_for_null and _vf_title_for_null:
                        _vf_domain_conflict = _has_domain_conflict_for_mapping(
                            _post_title_for_null, _vf_title_for_null
                        )
                except Exception:
                    _vf_title_for_null = ""

                _vf_anchor_strong = _vf_anchor_for_null in {
                    "title_mention", "plot_mention", "character_title_link", "character_mention",
                }
                _vf_conf_strong = _vf_conf_for_null in {"high", "max", "0.95"}
                _vf_bucket_support = (
                    _vf_official_cnt > 0
                    or _vf_post_cnt > 0
                    or (_vf_search_cnt >= 2 and _vf_anchor_strong)
                )
                _memory_query_null_upgrade_block = self._should_block_memory_query_forced_upgrade(
                    ctx,
                    _vf_out_for_null,
                    _vf_title_for_null,
                )
                _curated_alias_null_upgrade_block = self._curated_alias_lacks_contextual_work_anchor(
                    ctx,
                    _vf_title_for_null,
                    verifier_out=_vf_out_for_null,
                )
                if _memory_query_null_upgrade_block:
                    _null_block_reasons.append("memory_query_forced_upgrade_guard")
                    decision["_title_null_block_reasons"] = sorted(set(_null_block_reasons))
                    _has_strong_null_block = True
                    print(
                        f"[{_ts()}][{self.emoji}] 🛡️ memory-query null 우회 차단: "
                        f"verifier_title='{_vf_title_for_null or '-'}' "
                        "→ suspected title 복구 금지",
                        file=sys.stderr,
                    )
                if _curated_alias_null_upgrade_block:
                    _null_block_reasons.append("curated_alias_missing_contextual_work_anchor")
                    decision["_title_null_block_reasons"] = sorted(set(_null_block_reasons))
                    _has_strong_null_block = True
                    _disc_semantic = (
                        ((discourse_out.get("discourse_analysis") or {}).get("semantic_seed_review") or {})
                        if isinstance(discourse_out, dict)
                        else {}
                    )
                    _disc_intent = str(
                        ((discourse_out.get("discourse_analysis") or {}).get("intent") or "")
                        if isinstance(discourse_out, dict)
                        else ""
                    ).strip()
                    _gate_post_type = str(
                        (gatekeeper_out.get("post_type") or "")
                        if isinstance(gatekeeper_out, dict)
                        else ""
                    ).strip()
                    _has_semantic_work_context = (
                        bool(_disc_semantic.get("is_specific_work_discussion"))
                        or _disc_intent in {"discuss_work", "episode_discussion", "express_opinion"}
                        or _gate_post_type in {"work_discussion", "novel_discussion"}
                    )
                    if decision.get("is_relevant") and not _has_semantic_work_context:
                        decision["is_relevant"] = False
                        decision["is_novel_discussion"] = False
                        if str(decision.get("discussion_type") or "").strip() in {
                            "review",
                            "work_discussion",
                            "general",
                            "novel_discussion",
                        }:
                            decision["discussion_type"] = "noise"
                        _old_notes = str(decision.get("notes") or "").strip()
                        _guard_note = (
                            "[curated_alias_context_guard] 등록 약칭 표면만 있고 독립 작품 앵커가 없어 "
                            "저신뢰 차단/relevance를 내림"
                        )
                        decision["notes"] = f"{_guard_note}. {_old_notes}" if _old_notes else _guard_note
                        if _gate_post_type == "community_banter" or _disc_intent == "community_banter":
                            decision["_meme_blocked"] = True
                    print(
                        f"[{_ts()}][{self.emoji}] 🛡️ curated-alias null 우회 차단: "
                        f"verifier_title='{_vf_title_for_null or '-'}' "
                        "→ contextual work anchor 없음",
                        file=sys.stderr,
                    )

                if (
                    decision.get("is_relevant", False)
                    and (not _has_strong_null_block)
                    and _vf_title_for_null
                    and _vf_conf_strong
                    and _vf_bucket_support
                    and (not _vf_domain_conflict)
                ):
                    decision["official_title"] = _vf_title_for_null
                    decision["official_novel_title"] = _vf_title_for_null
                    if _vf_url_for_null and isinstance(_vf_url_for_null, str) and _vf_url_for_null.startswith("http"):
                        decision["heretic_url"] = _vf_url_for_null
                    print(
                        f"[{_ts()}][{self.emoji}] 🔓 Verifier null 복구 적용: "
                        f"None → {_vf_title_for_null} "
                        f"(vf_conf={_vf_conf_for_null or 'unknown'}, anchor={_vf_anchor_for_null or 'none'}, "
                        f"post={_vf_post_cnt}, search={_vf_search_cnt}, official={_vf_official_cnt})",
                        file=sys.stderr,
                    )
                    _final_title = _vf_title_for_null

                _has_high_suspected_for_null = any(
                    isinstance(st, dict)
                    and st.get("title")
                    and _suspected_conf_highish(st)
                    and (
                        _title_has_supported_evidence(
                            st.get("title"),
                            require_post_or_official=True,
                        )
                        or _character_parenthetical_suspect_supported(st)
                    )
                    for st in (ctx.suspected_titles or [])
                )
                if (not _final_title) and _has_high_suspected_for_null and decision.get("is_relevant", False) and not _has_strong_null_block:
                    # suspected_titles에 강한 후보가 있으므로 deliberate null 차단 안 함
                    # → agentic_pipeline에서 Verifier 폴백 또는 suspected_titles로 복구 가능
                    _best_suspected = max(
                        (st for st in (ctx.suspected_titles or [])
                         if isinstance(st, dict) and st.get("title")
                         and _suspected_conf_highish(st)),
                        key=lambda s: _st_conf_num(s.get("confidence")),
                        default=None,
                    )
                    if _best_suspected:
                        decision["official_title"] = _best_suspected["title"]
                        if _best_suspected.get("url"):
                            decision["heretic_url"] = _best_suspected["url"]
                        print(
                            f"[{_ts()}][{self.emoji}] 🔓 _title_deliberately_null 우회: "
                            f"suspected_titles에서 High 후보 적용: "
                            f"None → {_best_suspected['title']} (conf={_best_suspected.get('confidence')})",
                            file=sys.stderr
                        )
                elif not _final_title:
                    decision["_title_deliberately_null"] = True
                    print(
                        f"[{_ts()}][{self.emoji}] 🏷️ _title_deliberately_null 플래그 설정: "
                        f"Arbiter 후처리 결과 official_title=null → Verifier 폴백 차단"
                        f"{' (block=' + ','.join(_null_block_reasons) + ')' if _null_block_reasons else ''}",
                        file=sys.stderr
                    )

            # 🆕 heretic_url 폴백: Arbiter LLM이 null을 출력했지만 Verifier/Decoder에 URL이 있는 경우
            _null_block_reasons_for_url = decision.get("_title_null_block_reasons")
            if not isinstance(_null_block_reasons_for_url, list):
                _null_block_reasons_for_url = []
            _memory_query_null_block_for_url = "memory_query_forced_upgrade_guard" in _null_block_reasons_for_url
            if decision.get("is_relevant") and not decision.get("heretic_url") and not _memory_query_null_block_for_url:
                _fallback_url = None
                # 1순위: Verifier가 확인한 URL
                _vf_out = ctx.get_expert_output(ExpertType.VERIFIER) or {}
                _vf_result = _vf_out.get("verification_result") or {}
                _vf_novel_id = _vf_result.get("novel_identity") or {}
                _vf_url = _vf_novel_id.get("heretic_url")
                if _vf_url and isinstance(_vf_url, str) and _vf_url.startswith("http"):
                    _fallback_url = _vf_url
                # 2순위: Decoder best_match의 URL
                if not _fallback_url:
                    _dc_out = ctx.get_expert_output(ExpertType.DECODER) or {}
                    for _dt in (_dc_out.get("decoded_terms") or []):
                        if not isinstance(_dt, dict):
                            continue
                        for _cand in (_dt.get("candidates") or []):
                            _cand_url = _cand.get("url")
                            if _cand_url and isinstance(_cand_url, str) and _cand_url.startswith("http"):
                                # URL이 공식 플랫폼인지 확인
                                _is_official = any(
                                    p in _cand_url
                                    for p in ("munpia", "novelpia", "kakao", "naver", "joara", "ridibooks")
                                )
                                if _is_official:
                                    _fallback_url = _cand_url
                                    break
                        if _fallback_url:
                            break
                if _fallback_url:
                    decision["heretic_url"] = _fallback_url
                    print(
                        f"[{_ts()}][{self.emoji}] 🔗 heretic_url 폴백 적용: "
                        f"{_fallback_url} (Arbiter LLM이 null 출력 → Verifier/Decoder에서 복구)",
                        file=sys.stderr,
                    )

            # 🆕 최종 안전망: 후처리 과정에서 다시 유입된 사이트/게시판 접두 제거
            for title_key in ("official_title", "official_novel_title"):
                _t = decision.get(title_key)
                if not _t:
                    continue
                _clean_t = self._sanitize_site_noise_title(_t)
                if _clean_t != _t:
                    print(
                        f"[{_ts()}][{self.emoji}] 🧹 최종 제목 정제: "
                        f"'{_t}' → '{_clean_t}'",
                        file=sys.stderr,
                    )
                    decision[title_key] = _clean_t

            # 🔧 후처리로 final_decision이 바뀐 경우(강제승격/차단 등)에도
            # top-level final_reasoning이 stale해지지 않도록 동기화
            _decision_reasoning = decision.get("final_reasoning") or decision.get("reason")
            if isinstance(_decision_reasoning, str) and _decision_reasoning.strip():
                result["final_reasoning"] = _decision_reasoning
            
            print(
                f"[{_ts()}][{self.emoji}] {self.name} 완료 ({elapsed:.1f}s): "
                f"title={decision.get('official_title')}, confidence={decision.get('confidence')}",
                file=sys.stderr
            )
            
            return result
            
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"[{_ts()}][{self.emoji}] {self.name} 오류 ({elapsed:.1f}s): {e}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
            return self._fallback_decision(ctx, str(e))
    
    def _call_llm(
        self,
        user_prompt: str,
        *,
        ctx: Optional["ConversationContext"] = None,
        gatekeeper_result: Optional[Dict[str, Any]] = None,
        decoder_result: Optional[Dict[str, Any]] = None,
        verifier_result: Optional[Dict[str, Any]] = None,
        discourse_result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """LLM 호출"""
        base_system = ARBITER_SYSTEM.replace("{platform_map}", PLATFORM_ABBREVIATION_MAP)
        system_content = build_arbiter_system_prompt(
            base_system,
            gatekeeper_result=gatekeeper_result,
            decoder_result=decoder_result,
            verifier_result=verifier_result,
            discourse_result=discourse_result,
            ctx=ctx,
        )
        try:
            global_cap = int(os.getenv("LLM_EXPERT_MAX_TOKENS", os.getenv("LLM_MAX_TOKENS", "32768")))
        except Exception:
            global_cap = 32768
        try:
            # Arbiter는 최종 JSON + reasoning을 함께 내보내므로 4k는 실제 런에서 자주 부족했다.
            max_tokens = int(os.getenv("LLM_ARBITER_MAX_TOKENS", "8192"))
        except Exception:
            max_tokens = 8192
        max_tokens = max(512, min(max_tokens, global_cap, 16384))
        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_prompt},
        ]
        
        response_text = self.llm._stream_chat_http(
            messages=messages,
            tag="arbiter",
            use_grammar=True,
            max_tokens=max_tokens,
        )
        
        return self._parse_json_response(response_text)
    
    def _check_platform_or_block(
        self,
        decision: Dict[str, Any],
        final_title: str,
        post_title: str,
        sim: float,
        decoder_out: Dict[str, Any],
    ) -> None:
        """Decoder 플랫폼 URL 확인 후, 없으면 도용으로 차단"""
        decoder_has_platform_url = False
        if decoder_out:
            for term in decoder_out.get("decoded_terms") or []:
                best = term.get("best_match") or {}
                if best and best.get("title") == final_title:
                    for cand in term.get("candidates") or []:
                        if cand.get("official_novel_title") == final_title and cand.get("platform"):
                            decoder_has_platform_url = True
                            break
        norm_post = str(post_title or "").replace(" ", "").lower()
        norm_title = str(final_title or "").replace(" ", "").lower()
        _detail_url = str(decision.get("heretic_url") or "").strip()
        if norm_title and norm_title in norm_post and self._is_novel_detail_url(_detail_url):
            _remainder = norm_post.replace(norm_title, "", 1).strip()
            if len(_remainder) <= 8:
                print(
                    f"[{_ts()}][{self.emoji}] ✅ 제목+짧은 접미사 허용: "
                    f"official_title='{final_title}' ⊂ post_title='{post_title}' "
                    f"(remainder='{_remainder or '-'}', official_url='{_detail_url}')",
                    file=sys.stderr,
                )
                return
        if self._is_novel_detail_url(_detail_url):
            _post_stem = re.split(r"(?:무슨내용임|무슨\s*내용|내용임|뭐임|뭔내용|\?)", str(post_title or ""), maxsplit=1)[0].strip()
            _post_stem_norm = str(_post_stem or "").replace(" ", "").lower()
            if _post_stem_norm and norm_title and _post_stem_norm in norm_title and (len(norm_title) - len(_post_stem_norm)) <= 2:
                print(
                    f"[{_ts()}][{self.emoji}] ✅ 제목 stem 허용: "
                    f"official_title='{final_title}' ~ post_stem='{_post_stem}' "
                    f"(official_url='{_detail_url}')",
                    file=sys.stderr,
                )
                return
        if not decoder_has_platform_url:
            print(
                f"[{_ts()}][{self.emoji}] ⚠️ 포스트 제목 도용 감지: "
                f"official_title='{final_title}' ≈ post_title='{post_title}' "
                f"(sim={sim:.2f}) → null 강제",
                file=sys.stderr
            )
            decision["official_title"] = None
            decision["official_novel_title"] = None
            decision["confidence"] = "Low"
            _null_reasons = decision.get("_title_null_block_reasons")
            if not isinstance(_null_reasons, list):
                _null_reasons = []
            _null_reasons.append("post_title_theft_guard")
            decision["_title_null_block_reasons"] = sorted(set(_null_reasons))

    @staticmethod
    def _is_platform_branding_title(title: str) -> bool:
        import re

        if not isinstance(title, str):
            return False
        raw = title.strip()
        if not raw:
            return False

        norm = re.sub(r"[^\w가-힣]", "", raw).lower()
        branding_norms = {
            "웹소설로꿈꾸는세상",
            "웹소설의유토피아",
            "노벨피아",
            "문피아",
            "카카오페이지",
            "네이버시리즈",
            "리디",
            "조아라",
        }
        if norm in branding_norms:
            return True
        if re.match(
            r"^(?:노벨피아|문피아|카카오페이지|네이버\s*시리즈|조아라|리디)\s*[:：]\s*.+$",
            raw,
            flags=re.IGNORECASE,
        ):
            return True
        # 비소설 이벤트/스포츠 명칭 오염 (대문자 약어 + ...시리즈/리그/컵)
        if re.match(r"^[A-Z]{2,6}\s*[가-힣A-Za-z]{1,12}(?:시리즈|리그|컵)\s*$", raw):
            return True
        # 🆕 FIX-4: 사용자 블로그/서재 패턴 차단 ("세드릭군님의 서재" 등)
        if re.match(r"^[가-힣A-Za-z0-9]+(?:군)?님의\s*(?:서재|작품\s*목록|소설\s*목록|글\s*목록)$", raw):
            return True
        # 작가 프로필/블로그 패턴
        if re.match(r"^[가-힣A-Za-z0-9]+(?:의)?\s*(?:블로그|프로필|홈페이지)$", raw):
            return True
        return False

    @staticmethod
    def _is_generic_abbreviation_token(token: str, full_title: str = "") -> bool:
        """하드코딩 목록 없이 약칭-정식명 정합성으로 약칭 신뢰도를 판별."""

        def _norm(v: Any) -> str:
            return re.sub(r"[^\w가-힣]", "", str(v or "")).lower()

        abbr = _norm(token)
        if not abbr or len(abbr) < 2 or abbr.isdigit():
            return True
        if re.fullmatch(r"\d{1,4}(?:화|호|편|부|권)?", abbr):
            return True

        # 플랫폼 자체 명칭은 작품 약칭이 아닌 경우가 대부분
        platform_norms = {
            _norm(p)
            for p in PLATFORM_ABBREVIATIONS
        }
        if abbr in platform_norms:
            return True

        # 약칭치고 과도하게 긴 표현은 일반 문구일 가능성 높음
        if len(abbr) >= 9:
            return True

        title = _norm(full_title)
        if not title:
            # full title이 없으면 이 단계에서 단정하지 않음(다른 하드증거 로직이 판정)
            return False
        if len(title) < 3:
            return True

        # 약칭이 정식명에 부분 포함되면 통과(예: 빌환, 즉사무림)
        if abbr in title:
            return False

        # 정식명에 약칭 문자가 순서대로 얼마나 등장하는지(부분수열 적합도)
        i = 0
        matched = 0
        for ch in title:
            if i < len(abbr) and ch == abbr[i]:
                matched += 1
                i += 1
        subseq_ratio = matched / max(len(abbr), 1)

        # 문자 집합 겹침 비율(형태적 연관성 보조 지표)
        abbr_chars = set(abbr)
        title_chars = set(title)
        char_overlap = len(abbr_chars & title_chars) / max(len(abbr_chars), 1)

        # 두 지표 모두 낮으면 작품 약칭으로 보기 어려움
        return subseq_ratio < 0.5 and char_overlap < 0.6

    @staticmethod
    def _is_novel_detail_url(url: str) -> bool:
        """공식 플랫폼 URL 중 작품 상세 페이지만 True."""
        if not isinstance(url, str) or not url:
            return False
        try:
            from urllib.parse import urlparse

            parsed = urlparse(url)
            host = (parsed.netloc or "").lower()
            path = (parsed.path or "").lower()
            query = (parsed.query or "").lower()
        except Exception:
            return False

        # listing/search 우선 차단
        if any(tok in path for tok in ("/search", "/author", "/writers", "/ranking", "/best", "/genre", "/tag", "/list")):
            return False
        if any(tok in query for tok in ("search=", "q=", "query=", "keyword=", "writer=", "author=", "tag=", "genre=", "page=")):
            return False

        if "novelpia.com" in host and re.search(r"/novel/\d+", path):
            return True
        if "series.naver.com" in host and "/novel/detail.series" in path and "productno=" in query:
            return True
        if "ridibooks.com" in host and re.search(r"^/books/\d+", path):
            return True
        if "munpia.com" in host and (
            ("action=view" in query and "id=" in query)
            or re.search(r"/novel/\d+", path)
            or ("novel" in host and re.search(r"^/\d+", path))
        ):
            return True
        if "joara.com" in host and ("/book/" in path or "book_no=" in query or "bookcode=" in query):
            return True
        if ("kakao.page" in host or "page.kakao.com" in host) and "/content/" in path:
            return True

        return False

    def _has_strong_title_support(self, ctx: "ConversationContext", title: str) -> bool:
        """약칭 힌트/공식 상세 URL/페치 증거로 title을 강하게 지지하는지 확인."""
        if not title:
            return False

        def _norm(v: Any) -> str:
            return re.sub(r"[^\w가-힣]", "", str(v or "")).lower()

        title_norm = _norm(title)
        if not title_norm:
            return False
        short_title = len(title_norm) <= 4 and (" " not in str(title or "").strip())

        def _contains_as_token(raw_text: Any, token: str) -> bool:
            raw = str(raw_text or "")
            if not raw:
                return False
            return bool(
                re.search(
                    rf"(?<![가-힣A-Za-z0-9]){re.escape(token)}(?![가-힣A-Za-z0-9])",
                    raw,
                )
            )

        def _title_supported_in_text(raw_text: Any) -> bool:
            raw = str(raw_text or "")
            if not raw:
                return False
            if short_title:
                return _contains_as_token(raw, str(title))
            raw_norm = _norm(raw)
            return bool(title_norm and title_norm in raw_norm)

        def _normalized_url(url: Any) -> str:
            return re.sub(r"/+$", "", str(url or "").strip().lower())

        def _summarize_page_state(url: str) -> Dict[str, Any]:
            summary: Dict[str, Any] = {
                "has_fetched_entry": False,
                "is_deleted_or_unavailable": False,
                "is_community_post": False,
                "is_listing": False,
                "has_active_detail_like": False,
            }
            norm_url = _normalized_url(url)
            if not norm_url:
                return summary

            for fe in (getattr(ctx, "fetched_page_info", None) or []):
                if not isinstance(fe, dict):
                    continue
                if _normalized_url(fe.get("url")) != norm_url:
                    continue
                summary["has_fetched_entry"] = True
                structured = fe.get("structured_info") or {}
                if not isinstance(structured, dict):
                    structured = {}
                page_type = str(structured.get("page_type") or "").strip().lower()
                content_status = str(structured.get("content_status") or "").strip().lower()
                if fe.get("_content_deleted") and not content_status:
                    content_status = "deleted"
                if content_status in {"deleted", "unavailable"}:
                    summary["is_deleted_or_unavailable"] = True
                if page_type == "community_post":
                    summary["is_community_post"] = True
                elif page_type == "listing":
                    summary["is_listing"] = True

            summary["has_active_detail_like"] = bool(
                self._is_novel_detail_url(url)
                and not summary["is_deleted_or_unavailable"]
                and not summary["is_community_post"]
                and not summary["is_listing"]
            )
            return summary

        def _collect_source_quality() -> Dict[str, Any]:
            quality: Dict[str, Any] = {
                "active_detail_match_count": 0,
                "deleted_detail_match_count": 0,
                "community_post_match_count": 0,
                "listing_match_count": 0,
                "official_search_hit_count": 0,
                "trusted_official_search_hit_count": 0,
                "search_trust_sum": 0.0,
                "score": 0.0,
            }
            seen_urls: Set[str] = set()

            def _mark(url: str, trust: float, *, matched_via_search: bool) -> None:
                norm_url = _normalized_url(url)
                if not norm_url or norm_url in seen_urls:
                    return
                seen_urls.add(norm_url)

                state = _summarize_page_state(url)
                if matched_via_search:
                    quality["official_search_hit_count"] += 1
                    quality["search_trust_sum"] += max(0.0, trust)
                    if trust >= 0.8:
                        quality["trusted_official_search_hit_count"] += 1

                if state["is_deleted_or_unavailable"]:
                    quality["deleted_detail_match_count"] += 1
                elif state["is_community_post"]:
                    quality["community_post_match_count"] += 1
                elif state["is_listing"]:
                    quality["listing_match_count"] += 1
                elif state["has_active_detail_like"]:
                    quality["active_detail_match_count"] += 1

            for sr in (getattr(ctx, "search_results", None) or []):
                if not isinstance(sr, dict):
                    continue
                if sr.get("_is_derivative"):
                    continue
                sr_url = str(sr.get("url") or "")
                if not any(p in sr_url for p in OFFICIAL_PLATFORMS):
                    continue
                if not self._is_novel_detail_url(sr_url):
                    continue
                if not (
                    _title_supported_in_text(sr.get("title"))
                    or _title_supported_in_text(sr.get("content"))
                    or _title_supported_in_text(sr.get("snippet"))
                ):
                    continue
                trust = float(sr.get("_trust_score") or 0.0)
                if trust <= 0.0 and hasattr(ctx, "score_source_trust"):
                    try:
                        trust = float(ctx.score_source_trust(sr_url))
                    except Exception:
                        trust = 0.0
                _mark(sr_url, trust, matched_via_search=True)

            for fe in (getattr(ctx, "fetched_page_info", None) or []):
                if not isinstance(fe, dict):
                    continue
                fe_url = str(fe.get("url") or "")
                if not any(p in fe_url for p in OFFICIAL_PLATFORMS):
                    continue
                if not self._is_novel_detail_url(fe_url):
                    continue
                structured = fe.get("structured_info") or {}
                if not isinstance(structured, dict):
                    structured = {}
                matched = any(
                    _title_supported_in_text(candidate)
                    for candidate in (
                        structured.get("llm_identified_title"),
                        structured.get("title"),
                        structured.get("page_title"),
                        structured.get("work_title"),
                        fe.get("title"),
                        fe.get("page_title"),
                        fe.get("text_preview"),
                    )
                )
                if not matched:
                    continue
                _mark(fe_url, 0.0, matched_via_search=False)

            quality["score"] = (
                (quality["active_detail_match_count"] * 6.0)
                + (quality["trusted_official_search_hit_count"] * 2.0)
                + min(float(quality["official_search_hit_count"]), 2.0)
                + min(float(quality["search_trust_sum"]), 2.5)
                - (quality["deleted_detail_match_count"] * 7.0)
                - (quality["community_post_match_count"] * 4.0)
                - (quality["listing_match_count"] * 3.0)
            )
            return quality

        source_quality = _collect_source_quality()
        if (
            source_quality["active_detail_match_count"] == 0
            and (
                source_quality["deleted_detail_match_count"] > 0
                or source_quality["community_post_match_count"] > 0
                or source_quality["listing_match_count"] > 0
            )
        ):
            return False
        has_official_detail_hit = bool(
            source_quality["active_detail_match_count"] > 0
            or source_quality["trusted_official_search_hit_count"] > 0
            or (
                source_quality["official_search_hit_count"] > 0
                and source_quality["deleted_detail_match_count"] == 0
                and source_quality["community_post_match_count"] == 0
                and source_quality["listing_match_count"] == 0
                and source_quality["score"] >= 2.0
            )
        )
        post_title = str((getattr(ctx, "post_data", {}) or {}).get("title") or "")
        post_title_norm = _norm(post_title)
        snippet_hints = getattr(ctx, "snippet_hints", None) or {}

        for ah in (snippet_hints.get("abbreviation_hints") or []):
            if not isinstance(ah, dict):
                continue
            full_norm = _norm(ah.get("full"))
            abbr_norm = _norm(ah.get("abbrev"))
            if full_norm != title_norm:
                continue
            if not (abbr_norm and abbr_norm in post_title_norm):
                continue
            src = str(ah.get("source") or "").lower()
            conf = str(ah.get("confidence") or "").lower()
            trusted_non_registry_sources = {
                "platform_title",
                "url_fetch_platform",
                "author_bridge",
            }
            # generic 토큰(예: 시리즈/플랫폼 약칭)은 공식 상세 증거가 없으면 강증거로 채택하지 않는다.
            if self._is_generic_abbreviation_token(str(ah.get("abbrev") or ""), str(ah.get("full") or "")):
                if not has_official_detail_hit:
                    continue
            # short title은 공식 상세 증거가 없으면 약칭 힌트만으로 강증거 처리 금지
            if short_title and not has_official_detail_hit:
                continue
            if has_official_detail_hit or source_quality["score"] >= 6.0:
                return True
            if (
                src in trusted_non_registry_sources
                and conf in {"high", "max"}
                and source_quality["official_search_hit_count"] > 0
            ):
                return True

        for th in (snippet_hints.get("title_hints") or []):
            if not isinstance(th, dict):
                continue
            if (
                _norm(th.get("title")) == title_norm
                and (has_official_detail_hit or source_quality["score"] >= 6.0)
            ):
                return True

        if has_official_detail_hit:
            return True

        return False

    def _has_official_title_evidence(self, ctx: "ConversationContext", title: Optional[str]) -> bool:
        """
        Arbiter 경로용 얇은 official-title evidence helper.
        AgenticPipeline의 richer helper만큼 정밀하진 않아도,
        최소한 공식 플랫폼 상세/페치 기반 title support 여부는 일관되게 판단한다.
        """
        title_raw = str(title or "").strip()
        if not title_raw:
            return False

        def _norm(v: Any) -> str:
            return re.sub(r"[^\w가-힣]", "", str(v or "")).lower()

        title_norm = _norm(title_raw)
        if not title_norm:
            return False
        short_title = len(title_norm) <= 4 and (" " not in title_raw)

        def _contains_as_token(raw_text: Any, token: str) -> bool:
            raw = str(raw_text or "")
            if not raw:
                return False
            return bool(
                re.search(
                    rf"(?<![가-힣A-Za-z0-9]){re.escape(token)}(?![가-힣A-Za-z0-9])",
                    raw,
                )
            )

        def _title_supported(raw_text: Any) -> bool:
            if short_title:
                return _contains_as_token(raw_text, title_raw)
            raw_norm = _norm(raw_text)
            return bool(title_norm and title_norm in raw_norm)

        def _normalized_url(url: Any) -> str:
            return re.sub(r"/+$", "", str(url or "").strip().lower())

        def _page_state(url: str) -> Dict[str, Any]:
            state = {
                "has_fetched_entry": False,
                "is_deleted_or_unavailable": False,
                "is_community_post": False,
                "is_listing": False,
                "has_active_detail_like": False,
            }
            norm_url = _normalized_url(url)
            if not norm_url:
                return state
            for fe in (getattr(ctx, "fetched_page_info", None) or []):
                if not isinstance(fe, dict):
                    continue
                if _normalized_url(fe.get("url")) != norm_url:
                    continue
                state["has_fetched_entry"] = True
                structured = fe.get("structured_info") or {}
                if not isinstance(structured, dict):
                    structured = {}
                page_type = str(structured.get("page_type") or "").strip().lower()
                content_status = str(structured.get("content_status") or "").strip().lower()
                if fe.get("_content_deleted") and not content_status:
                    content_status = "deleted"
                if content_status in {"deleted", "unavailable"}:
                    state["is_deleted_or_unavailable"] = True
                if page_type == "community_post":
                    state["is_community_post"] = True
                elif page_type == "listing":
                    state["is_listing"] = True
                break
            state["has_active_detail_like"] = bool(
                self._is_novel_detail_url(url)
                and not state["is_deleted_or_unavailable"]
                and not state["is_community_post"]
                and not state["is_listing"]
            )
            return state

        def _state_allows_official(state: Dict[str, Any]) -> bool:
            return bool(
                state.get("has_active_detail_like")
                and not state.get("is_deleted_or_unavailable")
                and not state.get("is_community_post")
                and not state.get("is_listing")
            )

        seen: Set[str] = set()
        for sr in (getattr(ctx, "search_results", None) or []):
            if not isinstance(sr, dict) or sr.get("_is_derivative"):
                continue
            sr_url = str(sr.get("url") or "").strip()
            norm_url = _normalized_url(sr_url)
            if not norm_url or norm_url in seen:
                continue
            if not any(p in sr_url for p in OFFICIAL_PLATFORMS):
                continue
            if not self._is_novel_detail_url(sr_url):
                continue
            if not (
                _title_supported(sr.get("title"))
                or _title_supported(sr.get("content"))
                or _title_supported(sr.get("snippet"))
            ):
                continue
            state = _page_state(sr_url)
            if not _state_allows_official(state):
                continue
            seen.add(norm_url)
            return True

        for fe in (getattr(ctx, "fetched_page_info", None) or []):
            if not isinstance(fe, dict):
                continue
            fe_url = str(fe.get("url") or "").strip()
            norm_url = _normalized_url(fe_url)
            if not norm_url or norm_url in seen:
                continue
            if not any(p in fe_url for p in OFFICIAL_PLATFORMS):
                continue
            if not self._is_novel_detail_url(fe_url):
                continue
            state = _page_state(fe_url)
            if not _state_allows_official(state):
                continue
            structured = fe.get("structured_info") or {}
            if not isinstance(structured, dict):
                structured = {}
            if any(
                _title_supported(candidate)
                for candidate in (
                    structured.get("llm_identified_title"),
                    structured.get("title"),
                    structured.get("page_title"),
                    structured.get("work_title"),
                    fe.get("title"),
                    fe.get("page_title"),
                    fe.get("text_preview"),
                )
            ):
                return True

        return False

    def _post_main_text_for_curated_alias(self, ctx: "ConversationContext") -> str:
        post_data = getattr(ctx, "post_data", None) or {}
        chunks: List[str] = [
            str(post_data.get("title") or ""),
            str(post_data.get("normalized_title") or ""),
        ]
        for block in (post_data.get("content_blocks") or []):
            if isinstance(block, dict):
                block_type = str(block.get("type") or "").strip().lower()
                if block_type in {"image", "ocr_text", "image_summary"}:
                    continue
                chunks.append(str(block.get("text") or block.get("content") or ""))
            elif isinstance(block, str):
                chunks.append(block)
        return " ".join(chunk for chunk in chunks if str(chunk or "").strip())

    def _curated_alias_surface_in_text(self, text: Any, alias: Any) -> bool:
        alias_raw = str(alias or "").strip()
        alias_norm = self._normalize_match_text(alias_raw)
        raw_text = str(text or "")
        if not raw_text or not alias_norm or len(alias_norm) < 2:
            return False
        if re.search(
            rf"(?<![0-9A-Za-z가-힣]){re.escape(alias_raw)}(?![0-9A-Za-z가-힣])",
            raw_text,
        ):
            return True
        suffix = (
            r"(?:의|은|는|이|가|을|를|도|만|에서|에게|한테|랑|하고|와|과|로|으로|"
            r"작가|스포|최신화|휴재|연재|완결|후기|리뷰|팬덤|캐릭터|등장인물)"
        )
        if re.search(
            rf"(?<![0-9A-Za-z가-힣]){re.escape(alias_raw)}(?={suffix}|[^0-9A-Za-z가-힣]|$)",
            raw_text,
        ):
            return True
        return bool(len(alias_norm) >= 4 and alias_norm in self._normalize_match_text(raw_text))

    def _curated_alias_for_title_mentioned_in_post_main(
        self,
        ctx: "ConversationContext",
        title: Optional[str],
    ) -> bool:
        title_norm = self._normalize_match_text(title)
        if not ctx or not title_norm:
            return False
        post_text = self._post_main_text_for_curated_alias(ctx)
        if not self._normalize_match_text(post_text):
            return False
        for mapping in (KNOWN_ABBREVIATIONS or {}, KNOWN_TITLE_ABBREVIATIONS or {}):
            for alias, full_title in mapping.items():
                if self._normalize_match_text(full_title) != title_norm:
                    continue
                if self._curated_alias_surface_in_text(post_text, alias):
                    return True
        return False

    def _semantic_no_work_signal_for_curated_alias(
        self,
        ctx: "ConversationContext",
        *,
        verifier_out: Optional[Dict[str, Any]] = None,
    ) -> bool:
        try:
            from .orchestrator import ExpertType
            discourse_out = ctx.get_expert_output(ExpertType.DISCOURSE) or {}
            gatekeeper_out = ctx.get_expert_output(ExpertType.GATEKEEPER) or {}
        except Exception:
            discourse_out = {}
            gatekeeper_out = {}

        da = (discourse_out.get("discourse_analysis") or {}) if isinstance(discourse_out, dict) else {}
        if not isinstance(da, dict):
            da = {}
        seed = da.get("semantic_seed_review") or {}
        if isinstance(seed, dict) and seed.get("is_specific_work_discussion") is False:
            return True

        intent = str(da.get("intent") or "").strip().lower()
        gk_type = str(
            gatekeeper_out.get("post_type") or gatekeeper_out.get("classification") or ""
        ).strip().lower() if isinstance(gatekeeper_out, dict) else ""
        if intent in {"community_banter", "daily_life", "make_joke", "vent", "noise", "off_topic"}:
            return True
        if gk_type in {"community_banter", "noise", "off_topic", "daily_life"}:
            return True

        vf_result = (verifier_out or {}).get("verification_result") or {}
        relation = vf_result.get("relation_judgment") or {}
        if isinstance(relation, dict):
            target = str(relation.get("discussion_target") or "").strip().lower()
            promotion = str(relation.get("promotion_decision") or "").strip().lower()
            if target in {"generic_topic", "non_work", "author_talk", "community_banter"}:
                return True
            if promotion == "reject":
                return True

        for src in getattr(ctx, "uncertainty_sources", []) or []:
            src_text = str(src or "").lower()
            if (
                "semantic_seed_review_not_specific_work" in src_text
                or "intent_permit_for_title_search=false" in src_text
                or "context_only_no_work_anchor" in src_text
            ):
                return True
        return False

    def _has_curated_alias_contextual_work_anchor(
        self,
        ctx: "ConversationContext",
        title: Optional[str],
        *,
        verifier_out: Optional[Dict[str, Any]] = None,
    ) -> bool:
        if not self._curated_alias_for_title_mentioned_in_post_main(ctx, title):
            return False
        if self._semantic_no_work_signal_for_curated_alias(ctx, verifier_out=verifier_out):
            return False

        post_text = self._post_main_text_for_curated_alias(ctx)
        try:
            from .orchestrator import ExpertType
            gatekeeper_out = ctx.get_expert_output(ExpertType.GATEKEEPER) or {}
            discourse_out = ctx.get_expert_output(ExpertType.DISCOURSE) or {}
        except Exception:
            gatekeeper_out = {}
            discourse_out = {}

        gk_entities = (gatekeeper_out.get("detected_entities") or {}) if isinstance(gatekeeper_out, dict) else {}
        gk_clues = (gatekeeper_out.get("context_clues") or {}) if isinstance(gatekeeper_out, dict) else {}
        gk_type = str(
            gatekeeper_out.get("post_type") or gatekeeper_out.get("classification") or ""
        ).strip().lower() if isinstance(gatekeeper_out, dict) else ""
        da = (discourse_out.get("discourse_analysis") or {}) if isinstance(discourse_out, dict) else {}
        if not isinstance(da, dict):
            da = {}
        seed = da.get("semantic_seed_review") or {}
        if not isinstance(seed, dict):
            seed = {}
        intent = str(da.get("intent") or "").strip().lower()

        has_episode_or_serial_cue = bool(
            gk_clues.get("has_episode_reference")
            or gk_clues.get("is_spoiler_discussion")
            or re.search(r"\d+\s*(?:화|회차|호)\b|휴재|연재|스포|작가의\s*말|최신화|완결", post_text)
        )
        has_positive_semantic_cue = bool(
            seed.get("is_specific_work_discussion") is True
            or intent in {"discuss_work", "express_opinion", "review_work", "ask_work_question"}
            or gk_type in {"work_discussion", "review", "spoiler_discussion", "character_talk"}
        )
        has_character_entity_cue = bool(
            gk_entities.get("possible_characters")
        )
        has_concrete_work_cue = bool(
            re.search(
                r"\d+\s*(?:화|회차|호)\b|휴재|연재|스포|작가의\s*말|최신화|완결|"
                r"주인공|히로인|남주|여주|작중|등장인물|캐릭터|빌런|마왕|능력|스킬|세계관|에피소드",
                post_text,
            )
            or _has_curated_alias_work_discussion_cue(post_text)
        )
        return bool(has_positive_semantic_cue and (has_episode_or_serial_cue or has_character_entity_cue or has_concrete_work_cue))

    def _curated_alias_lacks_contextual_work_anchor(
        self,
        ctx: "ConversationContext",
        title: Optional[str],
        *,
        verifier_out: Optional[Dict[str, Any]] = None,
    ) -> bool:
        title_raw = str(title or "").strip()
        if not title_raw:
            return False
        if not self._curated_alias_for_title_mentioned_in_post_main(ctx, title_raw):
            return False
        if self._title_directly_in_post(ctx, title_raw):
            return False
        if self._has_curated_alias_contextual_work_anchor(ctx, title_raw, verifier_out=verifier_out):
            return False
        title_norm = self._normalize_match_text(title_raw)
        for entry in getattr(ctx, "verified_character_work_links", []) or []:
            if not isinstance(entry, dict) or entry.get("_weak_match"):
                continue
            if self._normalize_match_text(entry.get("title")) == title_norm:
                return False
        return True

    def _has_curated_alias_guard_exception(
        self,
        ctx: "ConversationContext",
        title: Optional[str],
        *,
        decoder_out: Optional[Dict[str, Any]] = None,
        verifier_out: Optional[Dict[str, Any]] = None,
    ) -> bool:
        title_raw = str(title or "").strip()
        if not ctx or not title_raw:
            return False
        if self._title_directly_in_post(ctx, title_raw):
            return True
        title_norm = self._normalize_match_text(title_raw)
        for entry in getattr(ctx, "verified_character_work_links", []) or []:
            if not isinstance(entry, dict) or entry.get("_weak_match"):
                continue
            if self._normalize_match_text(entry.get("title")) == title_norm:
                return True
        if self._has_curated_alias_contextual_work_anchor(ctx, title_raw, verifier_out=verifier_out):
            return True
        if (
            self._has_non_character_anchor_support(title_raw, decoder_out=decoder_out, verifier_out=verifier_out)
            and not self._curated_alias_for_title_mentioned_in_post_main(ctx, title_raw)
        ):
            return True
        return False

    def _looks_like_platform_event_meta_post(self, ctx: "ConversationContext") -> bool:
        post_data = getattr(ctx, "post_data", None) or {}
        chunks: List[str] = [str(post_data.get("title") or "")]
        for block in (post_data.get("content_blocks") or []):
            if isinstance(block, dict):
                chunks.append(str(block.get("text") or ""))
            elif isinstance(block, str):
                chunks.append(block)
        chunks.extend([str(c or "") for c in (getattr(ctx, "comments", None) or []) if str(c or "").strip()])
        for item in (post_data.get("image_enrichment") or []):
            if not isinstance(item, dict):
                continue
            chunks.append(str(item.get("ocr_text") or ""))
            chunks.append(str(item.get("visual_summary") or ""))
            chunks.append(" ".join(str(x or "") for x in (item.get("work_cues") or [])))

        raw = " ".join(part for part in chunks if str(part or "").strip())
        if not raw:
            return False
        norm = re.sub(r"[^\w가-힣]", "", raw).lower()
        if not norm:
            return False

        event_terms = (
            "행사", "이벤트", "현장", "오프라인", "팝업", "부스", "방문", "참여",
            "스탭", "스태프", "굿즈", "뱃지", "쇼핑백", "드레스코드", "agf",
            "킨텍스", "vvip", "마일리지", "출석체크",
        )
        event_hits = sum(
            1 for term in event_terms
            if term in raw.lower() or re.sub(r"[^\w가-힣]", "", term).lower() in norm
        )
        if event_hits < 2:
            experience_terms = ("먹고", "남아서", "떠들", "줄서", "대답해", "물어보", "옆자리", "현장", "후기")
            social_terms = ("스탭", "스태프", "스탭쟝", "staff")
            has_social = any(term in raw.lower() or self._normalize_match_text(term) in norm for term in social_terms)
            has_experience = any(term in raw.lower() or self._normalize_match_text(term) in norm for term in experience_terms)
            if not (has_social and has_experience):
                return False
            event_hits = 2

        work_anchor_terms = (
            "주인공", "작가", "회차", "줄거리", "설정", "캐릭터",
            "최신화", "막화", "엔딩", "하차", "리뷰",
        )
        work_hits = sum(1 for term in work_anchor_terms if term in raw)
        return event_hits >= max(2, work_hits + 1)

    def _has_question_plot_title_support(
        self,
        *,
        ctx: "ConversationContext",
        candidate_title: str,
        post_data: Dict[str, Any],
        gatekeeper_out: Dict[str, Any],
        discourse_out: Dict[str, Any],
    ) -> bool:
        candidate_title = str(candidate_title or "").strip()
        if not candidate_title:
            return False

        _is_reco_request_post, _ = self._detect_recommendation_request_post(
            post_data or {},
            gatekeeper_out or {},
            discourse_out or {},
        )
        discourse_analysis = (discourse_out or {}).get("discourse_analysis") or {}
        discourse_intent = str(discourse_analysis.get("intent") or "").lower()
        if (not _is_reco_request_post) and discourse_intent != "ask_question":
            return False

        def _norm(v: Any) -> str:
            return re.sub(r"[^\w가-힣]", "", str(v or "")).lower()

        post_title = str((post_data or {}).get("title") or "").strip()
        stem_match = re.split(r"(?:무슨내용임|무슨\s*내용|내용임|뭐임|뭔내용|\?)", post_title, maxsplit=1)[0].strip()
        stem_norm = _norm(stem_match)
        cand_norm = _norm(candidate_title)
        if not cand_norm:
            return False
        if stem_norm and stem_norm not in cand_norm and cand_norm not in stem_norm:
            return False

        comments = [
            str(c or "").strip()
            for c in (getattr(ctx, "comments", None) or [])
            if str(c or "").strip()
        ]
        if len(comments) < 2:
            return False

        support_parts: List[str] = []
        support_urls: set[str] = set()
        for sr in (getattr(ctx, "search_results", None) or []):
            if not isinstance(sr, dict):
                continue
            sr_url = str(sr.get("url") or "").strip()
            if not self._is_novel_detail_url(sr_url):
                continue
            sr_title = str(sr.get("title") or "").strip()
            sr_title_norm = _norm(sr_title)
            if cand_norm != sr_title_norm and cand_norm not in sr_title_norm and sr_title_norm not in cand_norm:
                continue
            support_parts.append(sr_title)
            support_parts.append(str(sr.get("content") or sr.get("snippet") or ""))
            support_urls.add(sr_url.rstrip("/").lower())

        for fe in (getattr(ctx, "fetched_page_info", None) or []):
            if not isinstance(fe, dict):
                continue
            fe_url = str(fe.get("url") or "").strip().rstrip("/").lower()
            if support_urls and fe_url not in support_urls:
                continue
            structured = fe.get("structured_info") or {}
            support_parts.append(str(fe.get("text") or fe.get("text_preview") or ""))
            if isinstance(structured, dict):
                for key in ("title", "page_title", "work_title", "summary", "description", "synopsis"):
                    support_parts.append(str(structured.get(key) or ""))

        support_blob = " ".join(part for part in support_parts if str(part or "").strip())
        support_norm = _norm(support_blob)
        if not support_norm:
            return False

        stop_terms = {
            "하렘", "캐빨", "좋음", "좋냐", "작품", "내용", "질문", "추천",
            "주인공", "중도하차", "댓글", "설명", "정도", "작가", "개연성",
            "평가", "정보", "문의", "먼치킨",
        }
        stop_norms = {_norm(term) for term in stop_terms if _norm(term)}
        seen_terms: set[str] = set()
        match_count = 0
        for comment in comments:
            for tok in re.findall(r"[가-힣A-Za-z0-9]{2,}", comment):
                tok_norm = _norm(tok)
                if not tok_norm or tok_norm in stop_norms or tok_norm in seen_terms:
                    continue
                seen_terms.add(tok_norm)
                if tok_norm in support_norm:
                    match_count += 1

        return match_count >= 2 and self._has_strong_title_support(ctx, candidate_title)

    def _is_character_like_short_title(
        self,
        ctx: "ConversationContext",
        title: str,
        decoder_out: Optional[Dict[str, Any]] = None,
        verifier_out: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """short title이 캐릭터 호칭으로 쓰였을 가능성이 높은지 판별."""
        norm_title = re.sub(r"[^\w가-힣]", "", str(title or "")).lower()
        if not norm_title or len(norm_title) > 3:
            return False

        # 1) Gatekeeper character 목록 충돌
        try:
            from .orchestrator import ExpertType
            gk_out = ctx.get_expert_output(ExpertType.GATEKEEPER) or {}
        except Exception:
            gk_out = {}
        gk_chars = []
        if isinstance(gk_out, dict):
            ents = gk_out.get("detected_entities") or {}
            gk_chars = ents.get("possible_characters") or []
        if any(re.sub(r"[^\w가-힣]", "", str(c or "")).lower() == norm_title for c in gk_chars):
            return True

        # 2) 제목/본문/댓글에서 조사 결합(은영이/은영은...) 패턴
        post_data = getattr(ctx, "post_data", {}) or {}
        chunks: List[str] = [str(post_data.get("title") or "")]
        for blk in (post_data.get("content_blocks") or []):
            if isinstance(blk, dict):
                if blk.get("text"):
                    chunks.append(str(blk.get("text")))
            elif isinstance(blk, str):
                chunks.append(blk)
        chunks.extend([str(c) for c in (getattr(ctx, "comments", []) or []) if c])
        full_text = " ".join(chunks)
        suffixes = ("가", "이", "은", "는", "을", "를", "도", "만", "네", "다", "냐", "임", "듯")
        if any(f"{title}{sfx}" in full_text for sfx in suffixes):
            return True

        # 3) Verifier/Decoder 앵커가 character_mention 중심인지 확인
        vf = (verifier_out or {}).get("verification_result") or {}
        vf_novel = vf.get("novel_identity") or {}
        vf_title = str(vf_novel.get("official_novel_title") or vf_novel.get("official_title") or "").strip()
        vf_anchor = str((vf.get("grounding_check") or {}).get("anchor_found") or "").lower()
        if vf_title and re.sub(r"[^\w가-힣]", "", vf_title).lower() == norm_title and vf_anchor == "character_mention":
            return True

        for dt in (decoder_out or {}).get("decoded_terms", []) or []:
            if not isinstance(dt, dict):
                continue
            bm = dt.get("best_match") or {}
            bm_title = str(bm.get("title") or "").strip()
            if re.sub(r"[^\w가-힣]", "", bm_title).lower() != norm_title:
                continue
            anchor = str((dt.get("grounding") or {}).get("anchor_type") or "").lower()
            if anchor == "character_mention":
                return True

        return False

    def _has_non_character_anchor_support(
        self,
        title: str,
        decoder_out: Optional[Dict[str, Any]] = None,
        verifier_out: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """해당 title이 character_mention 외 앵커(제목/줄거리 링크)로 지지되는지 확인."""
        norm_title = re.sub(r"[^\w가-힣]", "", str(title or "")).lower()
        if not norm_title:
            return False

        vf = (verifier_out or {}).get("verification_result") or {}
        vf_novel = vf.get("novel_identity") or {}
        vf_title = str(vf_novel.get("official_novel_title") or vf_novel.get("official_title") or "").strip()
        vf_anchor = str((vf.get("grounding_check") or {}).get("anchor_found") or "").lower()
        if (
            vf_title
            and re.sub(r"[^\w가-힣]", "", vf_title).lower() == norm_title
            and vf_anchor in {"title_mention", "plot_mention", "character_title_link"}
        ):
            return True

        for dt in (decoder_out or {}).get("decoded_terms", []) or []:
            if not isinstance(dt, dict):
                continue
            bm = dt.get("best_match") or {}
            bm_title = str(bm.get("title") or "").strip()
            if re.sub(r"[^\w가-힣]", "", bm_title).lower() != norm_title:
                continue
            conf = str(bm.get("confidence") or "").lower()
            anchor = str((dt.get("grounding") or {}).get("anchor_type") or "").lower()
            if conf in {"high", "max", "medium"} and anchor in {"title_mention", "plot_mention", "character_title_link"}:
                return True
        return False

    def _title_directly_in_post(self, ctx: "ConversationContext", title: str) -> bool:
        """정식 제목 문자열이 제목/본문/댓글에 직접 등장하는지 확인."""
        if not title:
            return False
        norm_title = re.sub(r"[^\w가-힣]", "", str(title)).lower()
        if not norm_title:
            return False

        post_data = getattr(ctx, "post_data", {}) or {}
        chunks: List[str] = [str(post_data.get("title") or "")]
        for blk in (post_data.get("content_blocks") or []):
            if isinstance(blk, dict):
                if blk.get("text"):
                    chunks.append(str(blk.get("text")))
            elif isinstance(blk, str):
                chunks.append(blk)
        chunks.extend([str(c) for c in (getattr(ctx, "comments", []) or []) if c])
        full_norm = re.sub(r"[^\w가-힣]", "", " ".join(chunks)).lower()
        return bool(norm_title and norm_title in full_norm)

    def _has_decoder_alignment_support(
        self,
        decoder_out: Optional[Dict[str, Any]],
        title: str,
        *,
        min_score: float = 0.45,
        require_non_generic: bool = False,
    ) -> bool:
        """
        Decoder가 해당 title을 본문 약칭/용어로 정합성 있게 식별했는지 확인.
        - best_match / candidates / interpretations 중 title 일치
        - original term ↔ title 약칭 정합성 점수 충족
        - 고신뢰(anchor/confidence) best_match는 완화 허용
        """
        if not isinstance(decoder_out, dict) or not title:
            return False

        norm_title = re.sub(r"[^\w가-힣]", "", str(title)).lower()
        if not norm_title:
            return False

        known_norm_map = {
            re.sub(r"[^\w가-힣]", "", str(k)).lower():
            re.sub(r"[^\w가-힣]", "", str(v)).lower()
            for k, v in KNOWN_ABBREVIATIONS.items()
        }

        for dt in (decoder_out.get("decoded_terms") or []):
            if not isinstance(dt, dict):
                continue
            if dt.get("is_author_name"):
                continue
            original = str(dt.get("original") or "").strip()
            if not original:
                continue
            if require_non_generic and self._is_generic_abbreviation_token(original, title):
                continue

            bm = dt.get("best_match") or {}
            bm_title = str(bm.get("title") or "").strip()
            bm_norm = re.sub(r"[^\w가-힣]", "", bm_title).lower() if bm_title else ""
            bm_conf = str(bm.get("confidence") or "").strip().lower()
            anchor = str(((dt.get("grounding") or {}).get("anchor_type") or "")).strip().lower()

            # title 매칭 후보 수집: best_match + candidates + interpretations
            matched_any = False
            matched_from_candidates = False
            candidate_morph_score = 0.0
            for cand in (dt.get("candidates") or []):
                if not isinstance(cand, dict):
                    continue
                for k in ("official_novel_title", "title", "official_title"):
                    c_title = str(cand.get(k) or "").strip()
                    if not c_title:
                        continue
                    c_norm = re.sub(r"[^\w가-힣]", "", c_title).lower()
                    if c_norm == norm_title:
                        matched_any = True
                        matched_from_candidates = True
                        try:
                            candidate_morph_score = max(candidate_morph_score, float(cand.get("morphological_score") or 0.0))
                        except Exception:
                            pass
                        break
                if matched_any:
                    break

            if (not matched_any) and bm_norm == norm_title:
                matched_any = True

            if not matched_any:
                for interp in (dt.get("interpretations") or []):
                    if not isinstance(interp, dict):
                        continue
                    it = str(interp.get("type") or "").strip().lower()
                    if it not in {"novel_title", "work_title", "title"}:
                        continue
                    iv = str(interp.get("value") or "").strip()
                    if not iv:
                        continue
                    iv_norm = re.sub(r"[^\w가-힣]", "", iv).lower()
                    if iv_norm == norm_title:
                        matched_any = True
                        break

            if not matched_any:
                continue

            score = abbreviation_match_score(original, title)
            if score >= min_score:
                return True

            # best_match가 강한 앵커/신뢰도를 가지면 정합성 완화 허용
            if (
                bm_norm == norm_title
                and bm_conf in {"high", "max", "medium"}
                and anchor in {"title_mention", "title_reaction_link", "plot_mention", "character_mention", "character_title_link"}
            ):
                return True

            # decoder candidate의 형태소 점수 보조 신호
            if matched_from_candidates and candidate_morph_score >= max(0.45, min_score - 0.05):
                return True

            orig_norm = re.sub(r"[^\w가-힣]", "", original).lower()
            if orig_norm and known_norm_map.get(orig_norm) == norm_title:
                return True

        return False

    def _sanitize_site_noise_title(self, title: str) -> str:
        """검색/커뮤니티 접두·접미가 섞인 제목을 코어 작품명으로 정제."""
        import re

        if not isinstance(title, str):
            return title

        raw = title.strip()
        if not raw:
            return raw
        if self._is_platform_branding_title(raw):
            return ""

        noise_tokens = (
            "블라인드",
            "에펨코리아",
            "마이너 갤러리",
            "장르소설",
            "웹소설",
            "나무위키",
            "네이버 블로그",
            "리디",
            "예스24",
            "종토방",
            "작품소개",
        )

        # 접두로 자주 붙는 매체명 제거
        raw = re.sub(r"^\s*블라인드\s*\|\s*", "", raw)
        raw = re.sub(r"^\s*[^:]{0,40}\s*종토방:\s*", "", raw)

        # "A - B - 사이트" 형태에서 사이트/게시판 토큰을 제외한 가장 타이틀다운 파트를 선택
        def _pick_candidate(parts: list[str]) -> str:
            for p in reversed(parts):
                p = p.strip()
                if len(p) < 3:
                    continue
                if any(tok in p for tok in noise_tokens):
                    continue
                return p
            return parts[-1].strip() if parts else ""

        cleaned = raw
        if " - " in cleaned:
            cleaned = _pick_candidate([p for p in cleaned.split(" - ") if p.strip()])
        elif " | " in cleaned:
            cleaned = _pick_candidate([p for p in cleaned.split(" | ") if p.strip()])

        # 제목형식 노이즈 정리
        # 커뮤니티 감상 꼬리 제거 (예: "제목이 잘못된 듯", "이거 뭐임")
        cleaned = re.sub(
            r"(?:\s+)(?:이거|이게|제목이|제목은|뭐임|뭐냐|재밌네|재밌다|잘못된듯|잘못된\s*듯).*$",
            "",
            cleaned,
        ).strip()
        # 사이트/매체 꼬리 제거 (공백/무공백 모두 허용)
        tail_patterns = (
            r"\s*[-|]?\s*(?:나무위키|더위키|위키|wikipedia)\s*$",
            r"\s*[-|]?\s*(?:에펨코리아|디시인사이드|루리웹|블라인드)\s*$",
            r"\s*[-|]?\s*(?:웹툰/웹소설/만화|장르소설\s*마이너\s*갤러리)\s*$",
            r"\s*[-|]?\s*(?:문피아|노벨피아|카카오페이지|네이버\s*시리즈|리디(?:북스)?)\s*$",
            r"\s*[-|]?\s*(?:판타지|무협|현판)\s*웹소설\s*$",
        )
        for pat in tail_patterns:
            cleaned = re.sub(pat, "", cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"^\s*[>\-\|]+\s*", "", cleaned).strip()
        cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
        if self._is_platform_branding_title(cleaned):
            return ""

        return cleaned if cleaned else title
    
    def _correct_title_from_search(self, llm_title: str, search_results: list) -> str:
        """
        🔥 LLM 제목을 검색 결과의 공식 제목과 대조하여 교정.
        best-match 방식 + 0.80 임계값 + LLM 제목이 검색에 있으면 교정 안 함
        """
        import re
        from difflib import SequenceMatcher
        from collections import Counter
        
        official_platforms = OFFICIAL_PLATFORMS

        def _extract_titleish_candidates(raw_title: str) -> list[str]:
            out: list[str] = []
            if not isinstance(raw_title, str):
                return out
            base = self._sanitize_site_noise_title(raw_title)
            if base and (not self._is_platform_branding_title(base)):
                out.append(base.strip())

            # "A - 플랫폼" 형태는 좌측이 제목일 확률이 높다.
            if " - " in raw_title:
                parts = [p.strip() for p in raw_title.split(" - ") if p.strip()]
                for p in parts:
                    p2 = self._sanitize_site_noise_title(p)
                    if p2 and (not self._is_platform_branding_title(p2)):
                        out.append(p2.strip())

            # "A | B" 구분자도 후보로 본다.
            if " | " in raw_title:
                parts = [p.strip() for p in raw_title.split(" | ") if p.strip()]
                for p in parts:
                    p2 = self._sanitize_site_noise_title(p)
                    if p2 and (not self._is_platform_branding_title(p2)):
                        out.append(p2.strip())

            # 중복 제거
            uniq: list[str] = []
            seen = set()
            for x in out:
                if not x:
                    continue
                if x in seen:
                    continue
                seen.add(x)
                uniq.append(x)
            return uniq
        
        # Step 0: LLM 제목이 검색 결과에 정확히 존재하면 교정 불필요
        for sr in search_results:
            url = sr.get("url", "")
            if not any(p in url for p in official_platforms):
                continue
            if not self._is_novel_detail_url(url):
                continue
            # 🆕 파생작/2차창작은 원작 확인 대상에서 제외
            if sr.get("_is_derivative"):
                continue
            sr_title = sr.get("title", "") or ""
            title_cands = _extract_titleish_candidates(sr_title)
            for cand in title_cands:
                cand2 = re.sub(r'\s*\(r\d+\s*판\)$', '', cand).strip()
                if not cand2 or self._is_platform_branding_title(cand2):
                    continue
                if cand2 == llm_title:
                    return llm_title
                if cand2.replace(" ", "") == str(llm_title or "").replace(" ", ""):
                    return llm_title
        
        # Step 0.5: 공신력 낮은 커뮤니티 결과라도, 정규화 후 완전 일치하면 교정 불필요
        llm_norm = str(llm_title or "").replace(" ", "")
        for sr in search_results:
            sr_title = sr.get("title", "") or ""
            for cand in _extract_titleish_candidates(sr_title):
                cand_norm = cand.replace(" ", "")
                if cand_norm and llm_norm and cand_norm == llm_norm:
                    return llm_title
        
        # Step 1: 모든 공식 후보 수집 + 빈도 계산
        candidates = []
        for sr in search_results:
            url = sr.get("url", "")
            if not any(p in url for p in official_platforms):
                continue
            if not self._is_novel_detail_url(url):
                continue
            sr_title = sr.get("title", "") or ""
            # 🆕 파생작/2차창작 검색 결과는 교정 후보에서 제외
            if sr.get("_is_derivative"):
                continue
            for cand in _extract_titleish_candidates(sr_title):
                cand2 = re.sub(r'\s*\(r\d+\s*판\)$', '', cand).strip()
                if not cand2 or self._is_platform_branding_title(cand2):
                    continue
                if len(cand2) >= 3:
                    candidates.append(cand2)
        
        if not candidates:
            return llm_title
        
        title_freq = Counter(candidates)
        
        # Step 2: best-match 방식
        best_candidate = None
        best_score = 0.0
        
        for title in set(candidates):
            if title == llm_title:
                continue
            if abs(len(title) - len(llm_title)) > 4:
                continue
            similarity = SequenceMatcher(None, llm_title, title).ratio()
            freq_bonus = min(title_freq[title] * 0.02, 0.10)
            adjusted_score = similarity + freq_bonus
            if adjusted_score > best_score:
                best_score = adjusted_score
                best_candidate = title
        
        # Step 3: 임계값 0.80 이상일 때만 교정
        if best_candidate and best_score >= 0.80:
            return best_candidate
        
        return llm_title
    
    def _synthesize_evidence_reason(
        self,
        ctx: "ConversationContext",
        tag: str,
        is_relevant: bool,
    ) -> str:
        """
        모든 전문가 증거를 종합하여 교정 판정 사유를 구성한다.
        
        "[본문 이해] → [증거 대입] → [판단 근거] → [결론]" 순서의 서사 형태로 작성.
        
        Args:
            ctx: ConversationContext (전문가 outputs 포함)
            tag: 교정 유형 태그 (e.g. "강제승격", "합의보호", "거부권")
            is_relevant: 교정 후 최종 판정
        
        Returns:
            종합된 reason 문자열
        """
        from .orchestrator import ExpertType
        
        # === 원본 게시글 정보 ===
        post_data = ctx.post_data or {}
        post_title = post_data.get("title", "")
        post_body = ""
        content_blocks = post_data.get("content_blocks") or post_data.get("content") or []
        if isinstance(content_blocks, list):
            body_parts = []
            if self.reason_full_mode:
                block_iter = content_blocks
            else:
                block_iter = content_blocks[:5]
            for block in block_iter:
                if isinstance(block, dict):
                    text = block.get("text")
                    if text is None:
                        text = block.get("content")
                    if text is None:
                        continue
                    body_parts.append(str(text))
                elif isinstance(block, str):
                    body_parts.append(block)
            post_body = " ".join(
                text for text in (str(b or "").strip() for b in body_parts) if text
            )
        if post_body:
            if self.reason_full_mode:
                post_body_short = post_body
            else:
                post_body_short = post_body[:100] + ("..." if len(post_body) > 100 else "")
        else:
            post_body_short = "(본문 없음)"
        
        # === 1) Decoder 증거 수집 ===
        decoder_out = ctx.get_expert_output(ExpertType.DECODER) or {}
        dec_terms = decoder_out.get("decoded_terms", [])
        dec_summaries = []
        dec_author = ""
        for dt in dec_terms:
            bm = dt.get("best_match") or {}
            if bm.get("title"):
                orig = dt.get("original", "?")
                title = bm["title"]
                conf = bm.get("confidence", "")
                dec_summaries.append(f"'{orig}'을(를) '{title}'({conf})로 식별")
            if dt.get("is_author_name"):
                ai = (dt.get("author_info") or {}).get("name", "")
                if ai:
                    dec_author = ai
        
        # === 2) Verifier 증거 수집 ===
        verifier_out = ctx.get_expert_output(ExpertType.VERIFIER) or {}
        vf_result = verifier_out.get("verification_result") or {}
        vf_relevant = vf_result.get("is_relevant")
        vf_novel = vf_result.get("novel_identity") or {}
        vf_title = vf_novel.get("official_novel_title") or vf_novel.get("official_title") or ""
        vf_reason = verifier_out.get("reason") or ""
        vf_grounding = vf_result.get("grounding_check") or {}
        vf_anchor = vf_grounding.get("anchor_found") or "none"
        vf_decoder_grounded = vf_grounding.get("decoder_grounded")
        rejection = vf_result.get("rejection_reason") or ""
        vf_author_info = vf_result.get("author_info") or {}
        vf_detected_author = ""
        vf_is_author_criticism = False
        if isinstance(vf_author_info, dict):
            vf_detected_author = str(vf_author_info.get("detected_author") or "").strip()
            vf_is_author_criticism = bool(vf_author_info.get("is_author_criticism"))
        
        # critical counter arguments 수집
        vf_counters = vf_result.get("counter_arguments") or []
        vf_critical_issues = []
        for arg in vf_counters:
            if isinstance(arg, dict):
                sev = str(arg.get("severity", "")).lower()
                issue = str(arg.get("issue", "")).strip()
                if sev == "critical" and issue:
                    vf_critical_issues.append(issue)
        
        # === 3) Discourse 증거 수집 ===
        primary_domain = getattr(ctx, 'primary_domain', '') or ''
        discourse_intent = getattr(ctx, 'discourse_intent', '') or ''
        discourse_warning = getattr(ctx, 'discourse_warning', '') or ''
        
        # === 4) Gatekeeper 증거 수집 ===
        gk_out = ctx.get_expert_output(ExpertType.GATEKEEPER) or {}
        gk_noise = gk_out.get("is_noise")
        gk_type = gk_out.get("post_type", "")
        
        # === 5) 검색 증강 증거 수집 ===
        # 5a) 검색 쿼리 이력
        executed_queries = list(getattr(ctx, "executed_queries", []) or [])
        searched_queries = list(getattr(ctx, 'searched_queries', set()) or set())
        # reason의 "검색 쿼리 N건 수행"은 실제 실행 쿼리 기준으로 통일
        queries_for_reason = executed_queries if executed_queries else searched_queries
        
        # 5b) 검색 결과 요약 (canonical EID 포함)
        all_search_results = getattr(ctx, 'search_results', []) or []
        search_highlights = []  # (eid, title, url_domain, snippet_short, trust, platform_type, query, purpose)
        _NOVEL_PLATFORMS = {"novelpia", "namu.wiki", "series.naver", "ridibooks", "kakaopage", "munpia"}
        _COMMUNITY_PLATFORMS = {"dcinside", "ruliweb", "arcalive", "fmkorea", "arca.live", "reddit"}
        seen_domains: set = set()
        # 검색 결과 전량 전달 (제한 없음)
        search_result_cap = len(all_search_results)
        for i, sr in enumerate(all_search_results[:search_result_cap], 1):
            sr_url = sr.get("url", "")
            sr_title = sr.get("title", "")
            sr_content = sr.get("content") or sr.get("snippet") or ""
            trust = sr.get("_trust_score", 0.5)
            eid = str(sr.get("_evidence_id") or f"T{i:03d}").strip()
            sr_query = str(sr.get("_query", "")).strip()
            sr_purpose = str(sr.get("_purpose", "")).strip()
            # 도메인 추출
            domain = ""
            try:
                from urllib.parse import urlparse
                domain = urlparse(sr_url).netloc.replace("www.", "")
            except Exception:
                pass
            if domain in seen_domains:
                continue
            seen_domains.add(domain)
            snippet_short = sr_content.strip()
            if snippet_short or sr_title:
                platform_type = "소설플랫폼" if any(p in domain for p in _NOVEL_PLATFORMS) else (
                    "커뮤니티" if any(p in domain for p in _COMMUNITY_PLATFORMS) else "기타"
                )
                search_highlights.append((eid, sr_title, domain, snippet_short, trust, platform_type, sr_query, sr_purpose))
        
        # 5c) 후보 증거 bucket
        candidate_evidence = getattr(ctx, 'candidate_evidence', {}) or {}
        evidence_summary = {}  # title -> {search_count, official_urls, platform_types}
        for cand_title, buckets in candidate_evidence.items():
            snippets = buckets.get("search_snippets", [])
            official = buckets.get("official_urls", [])
            post_spans = buckets.get("post_spans", [])
            grounded_spans = [s for s in post_spans if s.get("grounded")]
            evidence_summary[cand_title] = {
                "search_snippet_count": len(snippets),
                "official_url_count": len(official),
                "grounded_span_count": len(grounded_spans),
                "span_types": list({s.get("type", "") for s in post_spans if s.get("type")}),
            }
        
        # 5d) snippet_analyzer LLM 분석 결과
        llm_snippet = getattr(ctx, 'llm_snippet_analysis', None) or {}
        snippet_intent = llm_snippet.get("post_intent", "")
        snippet_intent_reason = llm_snippet.get("post_intent_reason", "")
        snippet_identified_title = llm_snippet.get("identified_title", "")
        snippet_identified_author = llm_snippet.get("identified_author", "")
        snippet_category = llm_snippet.get("identified_category", "")
        snippet_characters = llm_snippet.get("relevant_characters", [])
        snippet_abbrevs = llm_snippet.get("abbreviation_mappings", [])
        
        # 5e) 가설 이력
        hypothesis_history = getattr(ctx, 'hypothesis_history', []) or []
        active_hyp = getattr(ctx, 'active_hypothesis', None) or {}
        
        # ===================================================================
        # 서사 형태 reason 조립
        # ===================================================================
        sections = []

        def _clip(text: Any, limit: int) -> str:
            s = " ".join(str(text or "").split())
            if not s:
                return ""
            if self.reason_full_mode:
                return s
            if len(s) <= limit:
                return s
            return s[:limit] + "..."
        
        # [1] 본문 이해
        body_understanding = f"[{tag}] 게시글 제목: '{post_title}'"
        if post_body:
            body_understanding += f", 본문: '{post_body_short}'"
        sections.append(body_understanding)
        
        # [2] 전문가 분석 결과
        expert_findings = []
        
        # Decoder 판단
        if dec_summaries:
            expert_findings.append(f"Decoder: {'; '.join(dec_summaries)}")
        elif dec_author:
            expert_findings.append(f"Decoder: 작가 '{dec_author}' 식별 (작품명 미확정)")
        else:
            expert_findings.append("Decoder: 특정 작품 식별 실패")
        
        if dec_author:
            expert_findings.append(f"식별된 작가: '{dec_author}'")
        
        # Verifier 판단
        vf_summary = "Verifier: "
        if vf_relevant:
            if vf_title:
                vf_summary += f"'{vf_title}'로 매칭 확인, 앵커={vf_anchor}"
            else:
                vf_summary += f"관련 글로 판정 (앵커={vf_anchor})"
        else:
            vf_summary += "비관련 판정"
            if rejection:
                vf_summary += f" — {_clip(rejection, 150)}"
            elif vf_reason:
                vf_summary += f" — {_clip(vf_reason, 150)}"
        
        if vf_detected_author:
            role = "작가 비평" if vf_is_author_criticism else "작가 언급"
            vf_summary += f"; 작가 '{vf_detected_author}'({role})"
        
        expert_findings.append(vf_summary)
        
        # Critical counter arguments
        if vf_critical_issues:
            if self.reason_full_mode:
                critical_issues = vf_critical_issues
            else:
                critical_issues = vf_critical_issues[:3]
            expert_findings.append(f"핵심 반론: {'; '.join(critical_issues)}")
        
        # Discourse 판단
        if discourse_warning:
            expert_findings.append(f"Discourse 경고: {_clip(discourse_warning, 100)}")
        elif discourse_intent:
            expert_findings.append(f"Discourse: intent={discourse_intent}")
        
        sections.append(" | ".join(expert_findings))
        
        # [2.5] 검색 증강 분석
        search_narrative_parts = []
        
        # 검색 쿼리 요약
        if queries_for_reason:
            if self.reason_full_mode:
                q_display = queries_for_reason
            else:
                q_display = queries_for_reason[:4]
            q_str = ", ".join(f"'{q}'" for q in q_display)
            if (not self.reason_full_mode) and len(queries_for_reason) > 4:
                q_str += f" 외 {len(queries_for_reason) - 4}건"
            search_narrative_parts.append(f"검색 쿼리 {len(queries_for_reason)}건 수행({q_str})")
        
        # snippet_analyzer 의 본문 재해석
        if snippet_intent:
            intent_label = {
                "work_discussion": "특정 작품 토론",
                "genre_discussion": "장르 일반론",
            }.get(snippet_intent, snippet_intent)
            snippet_desc = f"스니펫 분석기 판정: '{intent_label}'"
            if snippet_intent_reason:
                snippet_desc += f" — {_clip(snippet_intent_reason, 120)}"
            if snippet_identified_title:
                snippet_desc += f", 식별 제목: '{snippet_identified_title}'"
            if snippet_identified_author:
                snippet_desc += f", 작가: '{snippet_identified_author}'"
            if snippet_category and snippet_category not in ("unknown", "web_novel"):
                snippet_desc += f", 카테고리: {snippet_category}"
            if snippet_characters:
                if self.reason_full_mode:
                    snippet_desc += f", 캐릭터: {', '.join(snippet_characters)}"
                else:
                    snippet_desc += f", 캐릭터: {', '.join(snippet_characters[:5])}"
            if snippet_abbrevs:
                if self.reason_full_mode:
                    abbr_candidates = snippet_abbrevs
                else:
                    abbr_candidates = snippet_abbrevs[:3]
                abbr_display = [f"{a.get('abbrev','?')}={a.get('full','?')}" for a in abbr_candidates]
                snippet_desc += f", 약칭: {', '.join(abbr_display)}"
            search_narrative_parts.append(snippet_desc)
        
        # 검색 결과 출처 분석 — 소설 플랫폼 vs 커뮤니티
        if search_highlights:
            platform_hits = [h for h in search_highlights if h[5] == "소설플랫폼"]
            community_hits = [h for h in search_highlights if h[5] == "커뮤니티"]
            
            if platform_hits:
                ph_list = []
                platform_display = platform_hits if self.reason_full_mode else platform_hits[:3]
                for sh_eid, sh_title, sh_domain, _sh_snippet, _sh_trust, _ptype, _sh_query, _sh_purpose in platform_display:
                    ph_list.append(f"{sh_eid} {sh_domain}: '{sh_title}'")
                search_narrative_parts.append(f"소설플랫폼 결과 {len(platform_hits)}건({'; '.join(ph_list)})")
            
            if community_hits and not is_relevant:
                # 비관련 판정에서 커뮤니티 결과만 있으면 강조
                ch_list = []
                community_display = community_hits if self.reason_full_mode else community_hits[:2]
                for sh_eid, sh_title, sh_domain, _sh_snippet, _sh_trust, _ptype, _sh_query, _sh_purpose in community_display:
                    ch_list.append(f"{sh_eid} {sh_domain}: '{sh_title}'")
                search_narrative_parts.append(f"커뮤니티 결과 {len(community_hits)}건({'; '.join(ch_list)}) — 소설 공식 출처 아님")
            
            if not platform_hits and community_hits and not is_relevant:
                search_narrative_parts.append("소설 플랫폼(novelpia/naver시리즈 등)에서 일치하는 작품 미발견")
        
        # 후보 증거 bucket 요약
        if evidence_summary:
            for cand_title, evi in evidence_summary.items():
                parts = []
                if evi["official_url_count"]:
                    parts.append(f"공식URL {evi['official_url_count']}건")
                if evi["search_snippet_count"]:
                    parts.append(f"검색스니펫 {evi['search_snippet_count']}건")
                if evi["grounded_span_count"]:
                    parts.append(f"본문근거 {evi['grounded_span_count']}건({', '.join(evi['span_types'])})")
                elif evi["span_types"]:
                    parts.append(f"본문증거유형: {', '.join(evi['span_types'])} (미검증)")
                if parts:
                    search_narrative_parts.append(f"'{cand_title}' 증거: {', '.join(parts)}")
        
        # 가설 변천
        if len(hypothesis_history) >= 2:
            first_hyp = hypothesis_history[0].get("title", "?")
            last_hyp = hypothesis_history[-1].get("title", "?")
            if first_hyp != last_hyp:
                search_narrative_parts.append(
                    f"가설 변천: '{first_hyp}' → '{last_hyp}' ({len(hypothesis_history)}단계)"
                )
        
        if search_narrative_parts:
            sections.append("검색 증강 분석: " + ". ".join(search_narrative_parts) + ".")
        
        # [3] 판단 근거
        reasoning_parts = []
        if is_relevant:
            if vf_title:
                reasoning_parts.append(f"'{vf_title}'에 대한 작품 토론으로 판정")
            elif dec_summaries:
                reasoning_parts.append("Decoder가 식별한 작품에 대한 토론으로 판정")
            if vf_anchor and vf_anchor != "none":
                anchor_desc = {
                    "title_mention": "본문에 작품명/약칭 직접 등장",
                    "character_mention": "본문에 캐릭터 고유명 등장",
                    "plot_mention": "본문에 줄거리/전개 언급",
                    "author_mention": "본문에 작가명 등장",
                    "character_title_link": "캐릭터+제목 연결 확인",
                    "comment_url": "댓글에 플랫폼 URL 존재",
                    "search_only": "검색 결과에서만 확인",
                }.get(vf_anchor, vf_anchor)
                reasoning_parts.append(f"근거: {anchor_desc}")
            # 검색 증거가 관련 판정을 뒷받침하는 경우
            if evidence_summary:
                for cand_title, evi in evidence_summary.items():
                    if evi["official_url_count"] and evi["grounded_span_count"]:
                        reasoning_parts.append(
                            f"검색에서 '{cand_title}'의 공식 페이지를 확인하고, "
                            f"본문에서 {', '.join(evi['span_types'])} 증거가 교차 검증됨"
                        )
                        break
                    elif evi["official_url_count"]:
                        reasoning_parts.append(
                            f"검색에서 '{cand_title}'의 공식 페이지 {evi['official_url_count']}건 확인"
                        )
                        break
        else:
            if gk_noise:
                reasoning_parts.append("Gatekeeper가 노이즈로 판별")
            if not vf_relevant:
                if vf_anchor == "none" and not vf_decoder_grounded:
                    reasoning_parts.append("본문에 작품 고유 정보(캐릭터명/줄거리/작가/회차) 없음")
                if "장르" in str(vf_reason) or "genre" in discourse_warning.lower():
                    reasoning_parts.append("장르/트로프 일반론으로 판별됨")
                if "플랫폼" in str(vf_reason) or "platform" in str(decoder_out.get("notes", "")).lower():
                    reasoning_parts.append("플랫폼 기능/상품에 대한 글로 판별됨")
            if dec_summaries and not is_relevant:
                # 검색에서 후보를 찾았지만 본문 근거가 없는 경우 구체적으로 설명
                if evidence_summary:
                    for cand_title, evi in evidence_summary.items():
                        if not evi["grounded_span_count"]:
                            reasoning_parts.append(
                                f"검색에서 '{cand_title}'을(를) 찾았으나 "
                                f"본문에 해당 작품의 고유 정보가 없어 매칭 불가"
                            )
                            break
                    else:
                        reasoning_parts.append("검색에서 키워드가 겹치는 소설을 찾았으나, 글쓴이가 해당 소설에 대해 쓴 것이 아님")
                else:
                    reasoning_parts.append("검색에서 키워드가 겹치는 소설을 찾았으나, 글쓴이가 해당 소설에 대해 쓴 것이 아님")
        
        if reasoning_parts:
            sections.append("판단: " + ". ".join(reasoning_parts) + ".")
        
        # [4] 결론
        if is_relevant:
            if vf_title or (dec_summaries and len(dec_summaries) > 0):
                final_title = vf_title or ""
                if not final_title and dec_terms:
                    for dt in dec_terms:
                        bm = dt.get("best_match") or {}
                        if bm.get("title"):
                            final_title = bm["title"]
                            break
                conclusion = f"따라서 이 글은 '{final_title}'에 대한 작품 토론이다."
            else:
                conclusion = "관련 포스트로 판정됨."
        else:
            if vf_is_author_criticism and vf_detected_author:
                conclusion = f"이 글은 작가 '{vf_detected_author}'에 대한 비평이며, 특정 작품 토론이 아니다."
            elif "장르" in str(vf_reason) or "genre" in discourse_warning.lower():
                conclusion = "이 글은 장르/트로프에 대한 일반 토론이며, 특정 소설에 대한 글이 아니다."
            elif gk_noise:
                conclusion = "이 글은 소설과 관련 없는 커뮤니티 잡담이다."
            else:
                conclusion = "이 글은 특정 소설에 대한 토론이 아닌 것으로 판정됨."
        
        sections.append(conclusion)
        
        return "\n".join(sections)
    
    def _is_similar_title(self, title_a: str, title_b: str) -> bool:
        """두 제목이 유사한지 (SequenceMatcher 80% 이상 + 길이 차이 ≤ 4)"""
        if abs(len(title_a) - len(title_b)) > 4:
            return False
        from difflib import SequenceMatcher
        return SequenceMatcher(None, title_a, title_b).ratio() >= 0.80
    
    def _parse_json_response(self, text: str) -> Dict[str, Any]:
        """Extract and parse JSON from response, removing <think> blocks."""
        return parse_json_with_think_removal(text)
    
    def _fallback_decision(
        self, 
        ctx: "ConversationContext", 
        error: str
    ) -> Dict[str, Any]:
        """
        LLM 실패시 규칙 기반 폴백 결정
        """
        from .orchestrator import ExpertType
        
        verifier_out = ctx.get_expert_output(ExpertType.VERIFIER) or {}
        vf_result = verifier_out.get("verification_result") or {}
        
        # Verifier 결과 우선 사용
        novel_id = vf_result.get("novel_identity") if vf_result else None
        
        # is_relevant=False일 때 reason 가져오기
        is_relevant = vf_result.get("is_relevant", False) if vf_result else False
        reason = ""
        reason_candidates = []
        if isinstance(vf_result, dict):
            reason_candidates.extend(
                [
                    vf_result.get("rejection_reason"),
                    vf_result.get("reason"),
                    (vf_result.get("grounding_check") or {}).get("grounding_issue"),
                ]
            )
        if isinstance(verifier_out, dict):
            reason_candidates.append(verifier_out.get("reason"))
        for cand in reason_candidates:
            if isinstance(cand, str) and cand.strip():
                reason = cand.strip()
                break

        # reason이 없으면 error 메시지를 reason으로 사용
        if not reason:
            reason = f"Arbiter 오류로 Verifier 결과 사용: {error}"
        
        # 폴백에서도 게시글 제목 도용 방지
        fallback_title = None
        if novel_id and isinstance(novel_id, dict):
            fallback_title = (
                novel_id.get("official_novel_title")
                or novel_id.get("official_title")
            )
            if fallback_title:
                post_data = ctx.post_data or {}
                post_title = post_data.get("title", "")
                if post_title:
                    from difflib import SequenceMatcher
                    norm_post = post_title.replace(" ", "")
                    norm_title = fallback_title.replace(" ", "")
                    sim = SequenceMatcher(None, norm_post, norm_title).ratio()
                    is_sub = norm_title in norm_post or norm_post in norm_title
                    if (sim >= 0.7 or is_sub) and len(fallback_title) > 3:
                        print(
                            f"[{_ts()}][{self.emoji}] 🚨 폴백 제목 도용 차단: "
                            f"'{fallback_title}' ≈ post_title='{post_title}' → null",
                            file=sys.stderr
                        )
                        fallback_title = None
        
        return {
            "final_decision": {
                "is_relevant": is_relevant,
                "is_novel_discussion": vf_result.get("is_novel_discussion", False) if vf_result else False,
                "official_title": fallback_title,
                "official_novel_title": fallback_title,
                "heretic_url": novel_id.get("heretic_url") if novel_id and isinstance(novel_id, dict) else None,
                "confidence": novel_id.get("confidence", "None") if novel_id and isinstance(novel_id, dict) else "None",
                "discussion_type": "unknown",
            },
            "expert_consensus": {
                "unanimous": False,
                "agreeing_experts": [],
                "dissenting_experts": [],
            },
            "conflict_resolution": [],
            "metadata_synthesis": {},
            "final_reasoning": reason,
            "evidence_chain": [],
        }

    def _detect_author_criticism_post(
        self,
        post_data: Dict[str, Any],
        comments: List[str],
        gatekeeper_out: Dict[str, Any],
        decoder_out: Dict[str, Any],
    ) -> tuple[bool, List[str]]:
        """작가 비평형 문장 패턴을 코드 레벨에서 감지한다.

        핵심 패턴:
        - 작가 지칭(Decoder is_author_name)
        - 지시형 어미(써라/써야/해라 등)
        - 장르 토론 신호(현판/로판 등 아키타입 또는 Gatekeeper genre flag)

        위 패턴이 동시에 성립하면 작품명 강제 승격을 차단하고 author_talk로 분류한다.
        """
        post_data = post_data or {}
        comments = comments or []
        gatekeeper_out = gatekeeper_out or {}
        decoder_out = decoder_out or {}

        title = str(post_data.get("title") or "")
        title_norm = title.lower().replace(" ", "")

        content_blocks = post_data.get("content_blocks") or post_data.get("content") or []
        body_parts: List[str] = []
        if isinstance(content_blocks, list):
            for block in content_blocks[:8]:
                if isinstance(block, dict):
                    text = str(block.get("text") or block.get("content") or "").strip()
                    if text:
                        body_parts.append(text)
                elif isinstance(block, str):
                    text = block.strip()
                    if text:
                        body_parts.append(text)

        comment_texts = [c.strip() for c in comments[:8] if isinstance(c, str) and c.strip()]
        merged_text = " ".join([title] + body_parts + comment_texts)
        merged_norm = merged_text.lower().replace(" ", "")

        directive_markers = (
            "써라",
            "쓰라",
            "써야",
            "써야됨",
            "써야댐",
            "써야함",
            "하나써",
            "하나써라",
            "해라",
            "하셈",
            "하라고",
        )
        has_directive_suffix = any(marker in merged_norm for marker in directive_markers)

        author_aliases: Set[str] = set()
        for term in decoder_out.get("decoded_terms") or []:
            if not isinstance(term, dict) or not term.get("is_author_name"):
                continue
            original = str(term.get("original") or "").strip()
            if len(original) >= 2:
                author_aliases.add(original.lower().replace(" ", ""))
            author_info = term.get("author_info") or {}
            if isinstance(author_info, dict):
                for key in ("name", "alias", "author_name"):
                    alias = str(author_info.get(key) or "").strip()
                    if len(alias) >= 2:
                        author_aliases.add(alias.lower().replace(" ", ""))

        gk_authors = (gatekeeper_out.get("detected_entities") or {}).get("possible_authors") or []
        for author in gk_authors:
            author_str = str(author or "").strip()
            if len(author_str) >= 2:
                author_aliases.add(author_str.lower().replace(" ", ""))

        has_author_alias_mention = any(alias and alias in merged_norm for alias in author_aliases)
        has_author_subject_pattern = bool(
            re.search(
                r"[가-힣a-zA-Z0-9]{2,12}\s*(?:는|은|도)\s*(?:그냥|걍)?\s*.*(?:써야|써라|쓰라|해라|하셈)",
                title,
            )
        )

        gk_context = gatekeeper_out.get("context_clues") or {}
        gk_flags = [str(flag) for flag in (gk_context.get("genre_discussion_flags") or [])]
        has_gk_genre_discussion = bool(gk_context.get("genre_discussion_detected")) or any(
            "genre_discussion_title" in flag for flag in gk_flags
        )

        archetypes_in_title = [
            archetype
            for archetype in GENRE_ARCHETYPE_TERMS
            if archetype and archetype.lower().replace(" ", "") in title_norm
        ]
        has_genre_archetype = bool(archetypes_in_title)

        has_example_reference = any(
            token in merged_norm
            for token in ("같은거", "같은거하나", "같은거써", "같은거써라", "이나써")
        )

        signals: List[str] = []
        if has_directive_suffix:
            signals.append("directive_suffix")
        if has_author_alias_mention:
            signals.append("decoder_author_mention")
        if has_author_subject_pattern:
            signals.append("title_author_directive_pattern")
        if has_gk_genre_discussion:
            signals.append("gatekeeper_genre_discussion")
        if has_genre_archetype:
            signals.append(f"genre_archetype:{','.join(archetypes_in_title[:2])}")
        if has_example_reference:
            signals.append("example_reference")

        is_author_criticism_post = (
            has_directive_suffix
            and (has_author_alias_mention or has_author_subject_pattern)
            and (has_gk_genre_discussion or has_genre_archetype or has_example_reference)
        )
        return is_author_criticism_post, signals

    def _detect_recommendation_request_post(
        self,
        post_data: Dict[str, Any],
        gatekeeper_out: Dict[str, Any],
        discourse_out: Dict[str, Any],
    ) -> tuple[bool, List[str]]:
        """
        추천 요청형 게시글을 감지한다.

        목적:
        - "추천좀/추천해줘"류 요청 글에서 댓글 작품명을 단일 작품 토론으로 강제 승격하는 오매칭을 방지.
        - 특정 사례 하드코딩이 아닌 한국어 요청 화행 신호를 조합해 판정.
        """
        post_data = post_data or {}
        gatekeeper_out = gatekeeper_out or {}
        discourse_out = discourse_out or {}

        gk_post_type = str(gatekeeper_out.get("post_type") or "").lower()
        gk_ctx = gatekeeper_out.get("context_clues") or {}
        discourse_analysis = discourse_out.get("discourse_analysis") or {}
        discourse_intent = str(discourse_analysis.get("intent") or "").lower()

        signals: List[str] = []
        if gk_post_type == "recommendation":
            signals.append("gatekeeper_post_type")
        if gk_ctx.get("is_recommendation_request"):
            signals.append("gatekeeper_context_clue")
        if gk_ctx.get("recommendation_suffix"):
            signals.append("gatekeeper_recommendation_suffix")
        if discourse_intent in {"request_recommendation", "recommendation"}:
            signals.append("discourse_intent")
        # 하드코딩 키워드가 아닌, 전문가(LLM) 의도 합의 신호만 사용.
        # - gatekeeper post_type/context_clue
        # - discourse intent
        #
        # 둘 이상 일치할 때만 recommendation으로 고정하여 과매칭을 줄인다.
        return (len(signals) >= 2), signals

    def _detect_multi_work_context_post(
        self,
        post_data: Dict[str, Any],
        comments: List[str],
        gatekeeper_out: Dict[str, Any],
        discourse_out: Dict[str, Any],
        decoder_out: Dict[str, Any],
        verifier_out: Dict[str, Any],
    ) -> tuple[bool, List[str]]:
        """
        복수 작품/작품군 맥락을 감지한다.

        목적:
        - 댓글/본문에 여러 작품을 비교·나열하는 질문형 화행에서
          단일 작품으로 강제 승격되는 오매칭을 방지.
        - 특정 사례 하드코딩 없이, 구조적 신호(다중 후보/나열 연결자/질문 화행) 조합으로 판정.
        """
        post_data = post_data or {}
        comments = comments or []
        gatekeeper_out = gatekeeper_out or {}
        discourse_out = discourse_out or {}
        decoder_out = decoder_out or {}
        verifier_out = verifier_out or {}

        title = str(post_data.get("title") or "")
        body_parts: List[str] = []
        for block in (post_data.get("content_blocks") or post_data.get("content") or [])[:8]:
            if isinstance(block, dict):
                txt = str(block.get("text") or block.get("content") or "").strip()
                if txt:
                    body_parts.append(txt)
            elif isinstance(block, str) and block.strip():
                body_parts.append(block.strip())
        merged_text = " ".join([title] + body_parts + [c for c in comments if isinstance(c, str)])
        # URL/링크 파편이 list/question 신호를 오염시키지 않도록 제거한다.
        # (예: kr/viewimage, ?id=... 가 list_connector(/), question_tone(?)로 오인되는 문제)
        merged_text_no_url = re.sub(r"https?://\S+", " ", merged_text, flags=re.IGNORECASE)
        merged_text_no_url = re.sub(r"www\.\S+", " ", merged_text_no_url, flags=re.IGNORECASE)
        merged_text_no_url = re.sub(r"\b\S+\.(?:com|co\.kr|kr|net|org|io|gg|me)\S*\b", " ", merged_text_no_url, flags=re.IGNORECASE)
        merged_text_no_url = re.sub(r"\s+", " ", merged_text_no_url).strip()
        merged_norm = merged_text_no_url.lower().replace(" ", "")

        # 신호 1) Decoder/Verifier에서 distinct 작품 후보가 2개 이상
        # NOTE:
        # - 과거에는 decoded_terms.candidates를 넓게 수집해 다중 후보가 과다 집계되는 문제가 있었음.
        # - 다중작 판정은 best_match + verifier 식별치 중심으로 보수적으로 계산한다.
        candidate_titles: Set[str] = set()
        # 커뮤니티/포럼 게시글 제목을 소설로 오인하지 않기 위한 필터 패턴
        _community_title_noise_pat = re.compile(
            r"(?:에펨|디시|루리웹|엠엘비|클리앙|인벤|웹툰/웹소설|넷플릭스)"
            r"|- 에펨$|- 디시$|- 루리웹$|- 인벤$",
            re.IGNORECASE,
        )
        for term in decoder_out.get("decoded_terms") or []:
            if not isinstance(term, dict):
                continue
            best = term.get("best_match") or {}
            best_title = str(best.get("title") or "").strip()
            best_conf = str(best.get("confidence") or "").lower()
            if best_title and best_conf in {"high", "medium"}:
                # 커뮤니티/포럼 게시글 제목이면 소설 후보에서 제외
                if _community_title_noise_pat.search(best_title):
                    continue
                # 제목이 과도하게 길면(30자 초과) 포럼 게시글 제목일 가능성 높음
                if len(best_title) > 30:
                    continue
                candidate_titles.add(best_title)
        vf_result = (verifier_out.get("verification_result") or {}) if isinstance(verifier_out, dict) else {}
        vf_novel = (vf_result.get("novel_identity") or {}) if isinstance(vf_result, dict) else {}
        vf_title = str(vf_novel.get("official_novel_title") or vf_novel.get("official_title") or "").strip()
        vf_conf = str(vf_novel.get("confidence") or verifier_out.get("final_confidence") or "").lower()
        if vf_title and vf_conf in {"high", "medium", "max"}:
            candidate_titles.add(vf_title)

        has_multi_titles = len(candidate_titles) >= 2

        # 신호 2) 나열/비교 연결자 (랑/와/과/,//및) + 2개 이상 항목
        # "/"는 URL/경로와 충돌이 잦아 제외하고, 자연어 연결자 중심으로 감지한다.
        list_connector_pat = re.compile(
            r"[가-힣A-Za-z0-9]{2,20}\s*(?:랑|와|과|,|및)\s*[가-힣A-Za-z0-9]{2,20}"
        )
        has_list_connector = bool(list_connector_pat.search(merged_text_no_url))

        # 신호 3) 질문/선호 확인 화행
        # 하드코딩 키워드 매칭 비중을 줄이고, 상위 전문가 신호를 우선 사용한다.
        gk_clues = (gatekeeper_out.get("context_clues") or {}) if isinstance(gatekeeper_out, dict) else {}
        gk_ask_reco = bool(gk_clues.get("is_asking_recommendation"))
        discourse_analysis = (discourse_out.get("discourse_analysis") or {}) if isinstance(discourse_out, dict) else {}
        discourse_intent = str(discourse_analysis.get("intent") or "").strip().lower()
        discourse_question_intents = {"ask_recommendation", "recommendation", "ask_compare", "compare_works"}
        has_question_tone = gk_ask_reco or (discourse_intent in discourse_question_intents)
        # 보조 신호: URL 제거 텍스트에서 실제 문장 물음표만 반영
        if not has_question_tone:
            has_question_tone = bool(re.search(r"[가-힣A-Za-z0-9][?？](?:\s|$)", merged_text_no_url))

        # 신호 4) 작가 중심 맥락
        has_author_focus = False
        gk_authors = (gatekeeper_out.get("detected_entities") or {}).get("possible_authors") or []
        if any(str(a or "").strip() for a in gk_authors):
            has_author_focus = True
        for term in decoder_out.get("decoded_terms") or []:
            if isinstance(term, dict) and term.get("is_author_name"):
                has_author_focus = True
                break
        vf_author = ((verifier_out.get("verification_result") or {}).get("author_info") or {}).get("detected_author")
        if vf_author:
            has_author_focus = True

        signals: List[str] = []
        if has_multi_titles:
            signals.append(f"decoder_multi_titles:{len(candidate_titles)}")
        if has_list_connector:
            signals.append("list_connector")
        if has_question_tone:
            signals.append("question_tone")
        if has_author_focus:
            signals.append("author_focus")

        gk_entities = gatekeeper_out.get("detected_entities") or {}
        has_character_anchor = any(
            isinstance(ch, str) and len(ch.strip()) >= 2
            for ch in (gk_entities.get("possible_characters") or [])
        )
        character_power_scaling = bool(
            has_character_anchor
            and has_list_connector
            and has_question_tone
            and not has_multi_titles
            and re.search(
                r"(?:이길|비비|상대|붙(?:이|는|어|는다)?|대결|전투력|강함|세냐|줄다리기|vs)",
                merged_text_no_url,
                flags=re.IGNORECASE,
            )
        )
        if character_power_scaling:
            signals.append("character_power_scaling_override")
            return False, signals

        # 강한 단일작 앵커가 확인되면 multi-work 가드보다 단일작을 우선한다.
        vf_grounding = (vf_result.get("grounding_check") or {}) if isinstance(vf_result, dict) else {}
        vf_anchor = str(vf_grounding.get("anchor_found") or "").strip().lower()
        strong_single_anchor = vf_anchor in {"plot_mention", "character_title_link", "character_mention"}
        # title_mention도 강한 앵커로 포함 (Verifier가 High/Max + title_mention이면 신뢰도 충분)
        _vf_conf_mw = str(vf_novel.get("confidence") or verifier_out.get("final_confidence") or "").lower()
        _title_mention_strong = (
            vf_anchor == "title_mention"
            and _vf_conf_mw in {"high", "max"}
        )
        vf_is_relevant = bool(vf_result.get("is_relevant") is True) if isinstance(vf_result, dict) else False
        if vf_is_relevant and (strong_single_anchor or _title_mention_strong) and vf_title:
            # multi_titles여도 Verifier가 강한 단일 앵커를 가지면 우선
            signals.append("single_work_override")
            return False, signals

        # 🔧 단일 High 후보 + multi_titles 아닌 경우: list_connector+question_tone만으로
        # 실제 단일 작품 논의를 잘못 차단하는 것 방지
        # 조건: Decoder 후보 1개 + High conf + (꺾쇠 패턴 또는 본문 플랫폼 URL)
        if not has_multi_titles and len(candidate_titles) == 1:
            _the_title = next(iter(candidate_titles))
            _the_conf = ""
            for _dt in (decoder_out.get("decoded_terms") or []):
                _bm = _dt.get("best_match") or {}
                if str(_bm.get("title") or "").strip() == _the_title:
                    _the_conf = str(_bm.get("confidence") or "").lower()
                    break
            # 게시글 제목에 꺾쇠 패턴이 있으면 단일 작품이 확실
            _post_title = str(post_data.get("title") or "")
            _has_bracket = bool(re.search(r"[<＜《<].{2,}[>＞》>]", _post_title))
            # 본문에 플랫폼 URL이 있으면 단일 작품이 확실
            _has_body_url = False
            for _blk in (post_data.get("content_blocks") or post_data.get("content") or [])[:10]:
                _txt = str(_blk.get("text") or _blk if isinstance(_blk, str) else "").lower()
                if any(p in _txt for p in ["munpia.com", "novelpia.com", "series.naver.com", "page.kakao.com", "joara.com", "ridibooks.com"]):
                    _has_body_url = True
                    break
            if _the_conf in ("high",) and (_has_bracket or _has_body_url):
                signals.append("single_high_with_anchor_override")
                return False, signals
            # Verifier가 relevant + confidence High/Medium이면서 Decoder 후보가 1개뿐
            if vf_is_relevant and _vf_conf_mw in {"high", "medium"} and vf_title:
                signals.append("single_vf_confirmed_override")
                return False, signals

        # 다중 작품 맥락 판정:
        # - 명시적 다중 후보 + (질문/나열) 또는
        # - 나열 + 질문 동시 충족
        # author_focus는 보조 신호로만 사용하고, 단독 트리거로 사용하지 않는다.
        is_multi_work = (
            (has_multi_titles and (has_question_tone or has_list_connector))
            or (has_list_connector and has_question_tone)
        )
        return is_multi_work, signals
    
    def _build_rich_reason(self, ctx, detected_author: str = "") -> str:
        """Decoder/Verifier 정보를 활용하여 풍부한 판정 사유를 생성.
        
        Arbiter LLM이 final_reasoning을 비워놓은 경우 사용.
        """
        from .orchestrator import ExpertType
        
        parts: list[str] = []
        
        # 1) Decoder의 decode_logic / best_match 정보
        _dec = ctx.get_expert_output(ExpertType.DECODER) if hasattr(ctx, 'get_expert_output') else {}
        _dec = _dec or {}
        for _dt in _dec.get("decoded_terms", []):
            _bm = _dt.get("best_match") or {}
            _title = _bm.get("title")
            _conf = _bm.get("confidence", "")
            _orig = _dt.get("original", "")
            if _title and str(_conf).lower() in ("high", "max"):
                # decode_logic 추출
                _candidates = _dt.get("candidates") or []
                _logic = ""
                for _c in _candidates:
                    if (_c.get("official_novel_title") or "") == _title:
                        _logic = _c.get("decode_logic", "")
                        break
                if _logic:
                    parts.append(f"약칭 '{_orig}' → '{_title}' 디코딩 근거: {_logic}")
                else:
                    parts.append(f"약칭 '{_orig}'가 '{_title}'로 디코딩됨 (신뢰도: {_conf})")
                break  # 최상위 1건만
        
        # 2) Verifier의 evidence_chain
        _vf = ctx.get_expert_output(ExpertType.VERIFIER) if hasattr(ctx, 'get_expert_output') else {}
        _vf = _vf or {}
        _vf_result = _vf.get("verification_result") or {}
        _vf_chain = _vf_result.get("evidence_chain") or []
        for _ev in _vf_chain[:2]:
            _content = _ev.get("content", "")
            _supports = _ev.get("supports", "")
            if _supports:
                parts.append(f"검증: {_supports}")
                break
        
        # 3) Verifier의 reason
        _vf_reason = _vf.get("reason") or ""
        if _vf_reason and len(_vf_reason) > 20:
            parts.append(f"Verifier 판단: {_vf_reason}")
        
        # 4) 작가 정보 (단독 reason 방지를 위해 기존 근거가 있을 때만 부착)
        if detected_author and parts:
            parts.append(f"작가 '{detected_author}' 식별됨")
        
        return " ".join(parts) if parts else ""
    
    def _extract_author_from_search(
        self,
        title: str,
        ctx,
    ) -> Optional[str]:
        """검색 결과에서 반복적으로 나타나는 작가명을 패턴 기반으로 추출.
        
        한국어 커뮤니티/플랫폼에서 작가명이 언급되는 대표 패턴:
        - "[작품명] - [작가명]" (플랫폼 검색 결과)
        - "[작가명] 작가의 [작품명]"  
        - "작가 [작가명]인것 보고"
        - "글 [작가명]" (문피아 표기)
        """
        import re as _re_auth
        
        search_results = getattr(ctx, "search_results", []) or []
        if not search_results or not title:
            return None
        
        title_clean = title.replace(" ", "").lower()
        # 제목을 단어별로 분할 (부분 문자열 필터에 사용)
        _title_words_lower = {w.lower() for w in title.split() if len(w) >= 2}
        author_candidates: dict[str, int] = {}  # 작가명 → 가중 출현 점수
        author_source_urls: dict[str, set[str]] = {}
        author_official_hits: dict[str, int] = {}
        author_community_hits: dict[str, int] = {}
        
        # 패턴 2: "작가\s*[작가명]" 또는 "[작가명]\s*작가"
        _pat_author = _re_auth.compile(
            r'(?:작가\s*[:\s]?\s*([가-힣a-zA-Z0-9]{2,10})|([가-힣a-zA-Z0-9]{2,10})\s*작가)',
        )
        
        # 일반 명사 / 플랫폼 이름 등 작가가 아닌 것 제외
        _noise_words = {
            "문피아", "노벨피아", "카카오", "네이버", "시리즈", "리디",
            "조아라", "블라인드", "에펨코리아", "나무위키", "소설넷",
            "웹소설", "소설", "무협", "판타지", "장편", "단편",
            "마이너", "갤러리", "게시판", "카카오페이지", "종토방",
            "만화", "웹툰", "코믹", "단행본", "연재", "무료", "유료",
            "이북", "e북", "ebook", "e-book", "최신화", "완결", "캘린더",
            "베스트", "랭킹", "추천", "리뷰",
            "새글순", "최신순", "인기순", "조회순", "추천순", "댓글순", "등록순",
        }
        _noise_words = {w.lower().replace(" ", "") for w in _noise_words}
        _noise_substrings = (
            "새글순", "최신순", "인기순", "조회순", "추천순", "댓글순", "등록순",
            "작품", "검색", "결과", "공지", "운영", "관리",
        )
        _trim_particles = (
            "은", "는", "이", "가", "을", "를", "에", "도", "로", "으로",
            "만", "와", "과", "랑", "의", "님",
        )
        _social_noise_domains = (
            "threads.com",
            "instagram.com",
            "x.com",
            "twitter.com",
            "facebook.com",
            "tiktok.com",
            "youtube.com",
            "youtu.be",
        )
        
        for sr in search_results:
            sr_title = sr.get("title", "")
            sr_content = (sr.get("content") or sr.get("snippet") or "")
            sr_url = sr.get("url", "")
            sr_url_l = sr_url.lower()
            combined = sr_title + " " + sr_content
            
            # 이 검색 결과가 해당 작품과 관련 있는지 확인
            if title_clean not in combined.replace(" ", "").lower():
                continue
            # 소셜/숏폼 계열은 작가 식별 근거로 쓰지 않음 (팬아트/2차 창작 노이즈 방지)
            if any(dom in sr_url_l for dom in _social_noise_domains):
                continue
            
            # 공식 플랫폼 URL에서의 패턴은 더 신뢰
            _is_official = self._is_novel_detail_url(sr_url)
            weight = 3 if _is_official else 1
            names_in_this_sr: set[str] = set()
            
            for text in [sr_title, sr_content]:
                for pat, _ptype in [(_pat_author, "author")]:
                    for m in pat.finditer(text):
                        # 캡처 그룹에서 None이 아닌 첫 번째 값
                        name = next((g for g in m.groups() if g), None)
                        if not name:
                            continue
                        name = name.strip()
                        name = _re_auth.sub(r"^[\[\(\{<\"'`]+|[\]\)\}>\"'`]+$", "", name).strip()
                        # 조사/정렬토큰 꼬리 제거
                        for _p in _trim_particles:
                            if name.endswith(_p) and len(name) >= len(_p) + 2:
                                name = name[: -len(_p)].strip()
                                break
                        if not name:
                            continue
                        name_lower = name.replace(" ", "").lower()
                        if any(ns in name_lower for ns in _noise_substrings):
                            continue
                        if name_lower.endswith("순"):
                            continue
                        if (
                            len(name) >= 2
                            and name_lower not in _noise_words
                            and name_lower != title_clean
                            and not name.isdigit()
                            and not _re_auth.fullmatch(r"[rv][0-9]+", name_lower)
                            # 🆕 제목 부분 문자열 차단: "빌어먹을" ⊂ "빌어먹을환생"
                            and name_lower not in title_clean
                            and title_clean not in name_lower
                            # 🆕 제목 개별 단어 차단: "즉사기" == title word
                            and name_lower not in _title_words_lower
                            # 🆕 노이즈 접두사 차단: "웹소설로", "카카오페이지에서" 등
                            and not any(name_lower.startswith(nw) for nw in _noise_words)
                            and not name_lower.startswith("http")
                        ):
                            names_in_this_sr.add(name)
            # 동일 검색결과 내 중복 매치를 1회로 제한 (title+snippet 중복 과가중 방지)
            for _name in names_in_this_sr:
                author_candidates[_name] = author_candidates.get(_name, 0) + weight
                author_source_urls.setdefault(_name, set()).add(sr_url_l or sr_title)
                if _is_official:
                    author_official_hits[_name] = author_official_hits.get(_name, 0) + 1
                else:
                    author_community_hits[_name] = author_community_hits.get(_name, 0) + 1
        
        if not author_candidates:
            return None

        # 가장 점수가 높은 후보를 선택하되, 출처 다양성 조건을 만족해야 채택
        best_author = max(author_candidates, key=author_candidates.get)
        best_score = author_candidates.get(best_author, 0)
        best_sources = len(author_source_urls.get(best_author, set()))
        best_official = author_official_hits.get(best_author, 0)
        best_community = author_community_hits.get(best_author, 0)

        # 작가 fallback은 공식 작품 상세 페이지 근거가 있는 경우만 허용
        if best_official >= 1 and best_score >= 3:
            return best_author
        if os.getenv("LLM_ALLOW_COMMUNITY_AUTHOR_FALLBACK", "0") == "1" and best_community >= 2 and best_sources >= 2 and best_score >= 2:
            return best_author
        return None

    @staticmethod
    def _korean_iga(text: str) -> str:
        """한글 종성 여부에 따라 주격조사(이/가)를 반환한다."""
        if not text:
            return "가"
        s = str(text).strip()
        if not s:
            return "가"
        ch = s[-1]
        code = ord(ch)
        if 0xAC00 <= code <= 0xD7A3:
            has_jong = ((code - 0xAC00) % 28) != 0
            return "이" if has_jong else "가"
        return "가"

    def _is_author_grounded(
        self,
        *,
        author: str,
        title: str,
        ctx,
    ) -> bool:
        """작가명이 실제 증거로 뒷받침되는지 검증한다.

        True 조건:
        1) fetched_page_info 구조화 정보에서 author가 일치 (최우선)
        2) 검색 결과에서 title+author가 명시적으로 결합되고,
           공식 플랫폼 1건 이상 혹은 커뮤니티 2건 이상 반복
        """
        import re as _re_ag

        def _norm(v: Any) -> str:
            return _re_ag.sub(r"\s+", "", str(v or "")).lower()

        author_norm = _norm(author)
        if not author_norm:
            return False
        _author_noise_tokens = {
            "새글순", "최신순", "인기순", "조회순", "추천순", "댓글순", "등록순",
            "more", "next", "prev", "ad", "notice",
        }
        _author_noise_tokens = {_norm(v) for v in _author_noise_tokens}
        if (
            author_norm in _author_noise_tokens
            or author_norm.endswith("순")
            or any((len(tok) >= 3) and (tok in author_norm) for tok in _author_noise_tokens)
        ):
            return False
        title_norm = _norm(title)

        # 1) fetched_page_info 우선 검증
        fetched = getattr(ctx, "fetched_page_info", None) or []
        for fi in fetched:
            if not isinstance(fi, dict):
                continue
            fi_url = str(fi.get("url") or "")
            if not self._is_novel_detail_url(fi_url):
                continue
            structured = fi.get("structured_info") or {}
            if not isinstance(structured, dict):
                continue
            fi_author = str(structured.get("author") or "").strip()
            if not fi_author:
                continue
            if _norm(fi_author) != author_norm:
                continue
            if title_norm:
                title_hay = _norm(
                    " ".join(
                        [
                            str(structured.get("title") or ""),
                            str(structured.get("page_title") or ""),
                            str(structured.get("work_title") or ""),
                            str(fi.get("text_preview") or ""),
                        ]
                    )
                )
                if title_norm and title_norm not in title_hay:
                    continue
            return True

        # 2) search_results에서 명시 패턴 검증
        search_results = getattr(ctx, "search_results", None) or []
        if not search_results:
            return False

        official_domains = (
            "novelpia.com",
            "munpia.com",
            "series.naver.com",
            "page.kakao.com",
            "joara.com",
            "ridibooks.com",
        )
        explicit_official_hits = 0
        explicit_community_hits = 0

        for sr in search_results:
            if not isinstance(sr, dict):
                continue
            sr_title = str(sr.get("title") or "")
            sr_content = str(sr.get("content") or sr.get("snippet") or "")
            sr_url = str(sr.get("url") or "").lower()
            combined_norm = _norm(f"{sr_title} {sr_content}")

            if title_norm and title_norm not in combined_norm:
                continue
            if author_norm not in combined_norm:
                continue

            is_explicit = (
                f"작가{author_norm}" in combined_norm
                or f"{author_norm}작가" in combined_norm
            )
            if not is_explicit:
                continue

            if any(dom in sr_url for dom in official_domains) and self._is_novel_detail_url(sr_url):
                explicit_official_hits += 1
            else:
                explicit_community_hits += 1

        if explicit_official_hits >= 1:
            return True
        # 기본은 커뮤니티 반복만으로 작가 확정 금지.
        # 필요 시에만 환경변수로 완화 가능(오탐 최소화 기본값).
        if os.getenv("LLM_ALLOW_COMMUNITY_AUTHOR_GROUNDING", "0") == "1":
            if title_norm and explicit_community_hits >= 3:
                return True
        return False

    def _summarize_gatekeeper(self, gk: Dict[str, Any]) -> Dict[str, Any]:
        """Gatekeeper 결과 요약 (토큰 절약)"""
        if not gk:
            return {}
        
        entities = gk.get("detected_entities") or {}
        return {
            "is_noise": gk.get("is_noise"),
            "post_type": gk.get("post_type"),
            "possible_titles": (entities.get("possible_titles") or [])[:3],
            "possible_authors": (entities.get("possible_authors") or [])[:2],
            "key_terms": (gk.get("key_terms") or [])[:5],
            "confidence": gk.get("confidence"),
        }
    
    def _summarize_decoder(self, dc: Dict[str, Any]) -> Dict[str, Any]:
        """Decoder 결과 요약 (토큰 절약)"""
        if not dc:
            return {}
        
        decoded = dc.get("decoded_terms") or []
        summary_terms = []
        for term in decoded[:3]:
            if not term:
                continue
            best = term.get("best_match") or {}
            grounding = term.get("grounding") or {}
            summary_terms.append({
                "original": term.get("original"),
                "title": best.get("title"),
                "confidence": best.get("confidence"),
                "is_grounded": grounding.get("is_grounded"),
                "anchor_type": grounding.get("anchor_type"),
            })
        
        return {
            "decoded_terms": summary_terms,
            "overall_confidence": dc.get("overall_confidence"),
            "needs_verification": dc.get("needs_verification"),
        }
    
    def _summarize_verifier(self, vf: Dict[str, Any]) -> Dict[str, Any]:
        """Verifier 결과 요약 (토큰 절약)"""
        if not vf:
            return {}
        
        vr = vf.get("verification_result") or {}
        novel_id = vr.get("novel_identity") or {}
        grounding_check = vr.get("grounding_check") or {}
        counter_args = vr.get("counter_arguments") or []
        
        return {
            "is_relevant": vr.get("is_relevant"),
            "is_novel_discussion": vr.get("is_novel_discussion"),
            "official_novel_title": novel_id.get("official_novel_title"),
            "confidence": novel_id.get("confidence"),
            "grounding_check": {
                "decoder_grounded": grounding_check.get("decoder_grounded"),
                "anchor_found": grounding_check.get("anchor_found"),
            },
            "counter_arguments": counter_args[:3],
            "author_info": vr.get("author_info"),
            "reason": vf.get("reason"),
        }
    
    def _summarize_critic(self, cr: Dict[str, Any]) -> Dict[str, Any]:
        """Critic 결과 요약 (토큰 절약)"""
        if not cr:
            return {}
        
        analysis = cr.get("analysis") or {}
        detected_titles = analysis.get("detected_titles") or []
        
        return {
            "detected_titles": [
                {"official_novel_title": t.get("official_novel_title"), "confidence": t.get("confidence")}
                for t in detected_titles[:2]
            ],
            "micro_tags": (analysis.get("micro_tags") or [])[:5],
            "sentiment": (analysis.get("sentiment_profile") or {}).get("sentiment"),
            "spoiler_level": analysis.get("spoiler_level"),
        }
