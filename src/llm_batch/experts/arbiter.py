"""
Final Arbiter - 최종 종합 판정 전문가
모든 전문가의 의견을 종합하여 최종 결론을 도출합니다.
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, TYPE_CHECKING

from .utils import parse_json_with_think_removal, _ts
from ..prompts.expert_prompts import LF_ARBITER, PLATFORM_ABBREVIATION_MAP
from ..rules import OFFICIAL_PLATFORMS, GENRE_ARCHETYPE_TERMS

if TYPE_CHECKING:
    from .orchestrator import ConversationContext


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

**항상 is_relevant=false인 discussion_type:**
- "author_talk": 작가에 대한 토론/비평 ("[작가명]은 [장르]이나 써야됨" 패턴) → official_novel_title=null
- "recommendation": 추천 요청 ("추천좀", "뭐 읽을거" 패턴)
- "meta": 플랫폼 메타
- "noise": 노이즈/뻘글
- "trope_discussion": 특정 작품 없이 장르/트로프 일반 토론

🚨 **discussion_type 정합성 규칙:**
- is_relevant=true + discussion_type="recommendation" → 불가!
- is_relevant=true + discussion_type="noise" → 불가!
- is_relevant=true + discussion_type="author_talk" → 불가! (작가 비평은 항상 is_relevant=false)
- is_relevant=true + discussion_type="community_banter" → 불가!
- is_relevant=true + discussion_type="genre_opinion" → 불가!
- is_relevant=true + discussion_type="image_post" → 불가!
- is_relevant=true + discussion_type="off_topic" → 불가!
- 작가 비평인데 예시로 작품이 언급되면 → discussion_type="author_talk", is_relevant=false, official_novel_title=null

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
⚖️ FINAL ARBITER - Ultra-Compact Review

=== POST (ID: {post_id}) ===
Title: {title}
Body: {body_preview}
Comments: {comment_count} total

=== EXPERT CONSENSUS (Compact) ===

🎭 Gatekeeper: {gk_verdict}
🔤 Decoder: {dc_verdict}
🔍 Verifier: {vf_verdict}{verifier_veto}
📚 Critic: {cr_verdict}

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
  "final_reasoning": "string (Korean - comprehensive explanation)",
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
        
        # 각 전문가 결과 요약 (토큰 절약)
        gk_summary = self._summarize_gatekeeper(gatekeeper_out)
        dc_summary = self._summarize_decoder(decoder_out)
        vf_summary = self._summarize_verifier(verifier_out)
        cr_summary = self._summarize_critic(critic_out)
        
        # post_data None 체크
        post_data = ctx.post_data or {}
        
        # Ultra-compact 프롬프트 구성
        content_blocks = post_data.get("content_blocks", [])
        # content_blocks가 문자열 리스트인지 확인하고 안전하게 변환
        # 🆕 BUG-3: 블록 수를 2 → 4로 확장하여 이미지 뒤 텍스트 누락 방지
        total_text_len = 0  # 전체 텍스트 길이 추적
        if content_blocks:
            safe_blocks = []
            for block in content_blocks[:4]:
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
            for block in content_blocks[4:]:
                if isinstance(block, str):
                    total_text_len += len(block.strip())
                elif isinstance(block, dict) and block.get('text'):
                    total_text_len += len(str(block['text']).strip())
        else:
            body_preview = "(empty)"
            total_text_len = 0
        
        # 🆕 BUG-3: body_preview 길이 200 → 400으로 확장
        if len(body_preview) > 400:
            body_preview = body_preview[:400] + "..."
        
        # 🆕 BUG-3: 텍스트 존재 여부 플래그 — image_post 환각 방지
        has_text_content = total_text_len >= 30
        if has_text_content:
            body_preview += f"\n[TEXT_CONTENT: {total_text_len}자 텍스트 존재 — 이미지 전용 포스트 아님]"
        
        comments = ctx.comments or []
        
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
        
        cr_verdict = f"titles={len(cr_summary.get('detected_titles', []))}, sentiment={cr_summary.get('sentiment')}"
        
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
        
        ctx.suspected_titles = sorted(merged, key=lambda x: x.get('confidence', 0), reverse=True)[:5]
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
            gk_verdict=gk_verdict,
            dc_verdict=dc_verdict,
            vf_verdict=vf_verdict,
            verifier_veto=verifier_veto,
            cr_verdict=cr_verdict,
            key_evidence=key_evidence,
            suspected_titles=suspected_titles_str,
        ) + expert_confidence_info + uncertainty_info + discourse_info
        
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
        
        try:
            result = self._call_llm(user_prompt)
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
            
            # suspected_titles를 Context에 저장 (다른 전문가들도 접근 가능)
            decision = result.get("final_decision") or {}
            if decision.get("suspected_titles"):
                ctx.suspected_titles = decision["suspected_titles"]
            
            # 🚨 P1-5: suspected_titles에서 최고 confidence 제목을 official_title로 강제 설정
            # (LLM이 축약어를 선택하는 것을 방지)
            # 🔧 P1-5-FIX: 검색 결과와 문자 단위 비교하여 LLM 변형 오류 방지
            # 🔧 author_talk 예외: Arbiter가 의도적으로 null 설정한 경우 강제 적용 스킵
            discussion_type_val = decision.get("discussion_type", "")
            skip_forced_title = discussion_type_val in ("author_talk", "author_criticism")
            
            # 🔧 Phase26-A: Arbiter LLM이 명시적으로 official_novel_title=null로 판단한 경우
            # suspected_titles 기반 강제 승격을 스킵 (LLM의 의도적 null 판단 존중)
            # 🔧 Phase27-A: 단, suspected_titles에 High confidence 후보가 있으면 스킵하지 않음
            #   (Arbiter LLM이 title을 null로 남겨도, 검색 증거 기반 강한 후보는 적용해야 함)
            arbiter_explicit_null = (
                decision.get("official_novel_title") is None
                and decision.get("is_relevant", False)
            )
            if arbiter_explicit_null and not skip_forced_title:
                # suspected_titles에 High confidence 후보가 있으면 null 가드를 우회
                _has_high_suspected = any(
                    isinstance(st, dict)
                    and st.get("title")
                    and str(st.get("confidence", "")).lower() in ("high", "0.95")
                    for st in (ctx.suspected_titles or [])
                )
                if _has_high_suspected:
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
                    # suspected_titles에 medium 이상 후보가 있는지 확인
                    _has_strong_suspect = False
                    if ctx.suspected_titles:
                        _conf_map = {"high": 3, "medium": 2, "low": 1, "none": 0}
                        for _st in ctx.suspected_titles:
                            _st_conf = _st.get("confidence", 0)
                            if isinstance(_st_conf, (int, float)) and _st_conf >= 0.7:
                                _has_strong_suspect = True
                                break
                            elif isinstance(_st_conf, str) and _conf_map.get(_st_conf.lower(), 0) >= 2:
                                _has_strong_suspect = True
                                break

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
                        else:
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
                            _is_genre_warn_guard = (
                                "genre_discussion" in _warn_lower
                                or "discuss_genre" in _warn_lower
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

                            if (not _decoder_grounded_guard) or (_anchor_guard in ("search_only", "none")):
                                print(
                                    f"[{_ts()}][{self.emoji}] 🛡️ 강제승격 차단(앵커 약함): "
                                    f"anchor={_anchor_guard}, decoder_grounded={_decoder_grounded_guard} "
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
            decoder_out_raw = ctx.expert_outputs.get("decoder") or {} if hasattr(ctx, 'expert_outputs') else {}
            for term in decoder_out_raw.get("decoded_terms", []):
                if term.get("is_author_name"):
                    # author_info.name 또는 original 추출
                    author_info = term.get("author_info") or {}
                    if author_info.get("name"):
                        decoder_author_names.add(author_info["name"])
                    if term.get("original"):
                        decoder_author_names.add(term["original"])
            
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
                
                # 🛡️ 아이디어 H: 작가명과 일치하는 항목 필터링
                filtered_titles = [
                    st for st in ctx.suspected_titles
                    if st.get("title") not in decoder_author_names
                ]
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
                
                # 가장 높은 confidence를 가진 항목 찾기 (작가명 제외 후)
                if not skip_forced_title:
                    best = max(
                        filtered_titles,
                        key=lambda x: conf_to_num(x.get("confidence", 0))
                    )
                else:
                    best = None
                best_conf_num = conf_to_num(best.get("confidence", 0)) if best else 0
                
                # high나 medium이면 강제 적용 (숫자 2 이상)
                if best_conf_num >= 2:  # medium 이상
                    best_title = best.get("title") if best else None
                    
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
            
            # � Arbiter LLM 응답의 official_title도 검색 결과로 교정
            for title_key in ("official_title", "official_novel_title"):
                arbiter_llm_title = decision.get(title_key)
                if arbiter_llm_title and ctx.search_results:
                    corrected = self._correct_title_from_search(arbiter_llm_title, ctx.search_results)
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
            _SITE_NOISE_INDICATORS = (
                "블라인드 |", "에펨코리아", "| 웹소설", "| 장르소설",
                "> 작품소개", "종토방:", "오늘도요 -", "마이너 갤러리",
                "- 웹툰/웹소설", "- 나무위키", "- 네이버 블로그",
                "- 리디", "- 예스24", " | ", "- 에펨코리아",
            )
            for title_key in ("official_title", "official_novel_title"):
                final_title = decision.get(title_key)
                if not final_title:
                    continue
                if any(indicator in final_title for indicator in _SITE_NOISE_INDICATORS):
                    # " - " 마지막 파트를 추출
                    cleaned = final_title
                    if " - " in final_title:
                        parts = final_title.split(" - ")
                        # 마지막 파트가 사이트명이면 마지막 전, 아니면 마지막
                        candidate = parts[-1].strip()
                        if len(candidate) < 3 or any(s in candidate for s in ("나무위키", "갤러리", "블로그", "리디", "에펨")):
                            # 마지막이 사이트명 → 그 앞에서 추출
                            for p in reversed(parts[:-1]):
                                p = p.strip()
                                if len(p) >= 3 and not any(s in p for s in ("블라인드", "웹소설 종토방", "갤러리")):
                                    candidate = p
                                    break
                        cleaned = candidate
                    elif " | " in final_title:
                        parts = final_title.split(" | ")
                        cleaned = parts[-1].strip()
                    
                    if cleaned != final_title and 3 <= len(cleaned) <= 50:
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
                            
                            if any(a in _body_lower for a in _all_auth if a):
                                _veto_exempt = True
                                _matched_auth = [a for a in _all_auth if a and a in _body_lower]
                                print(
                                    f"[{_ts()}][{self.emoji}] 🔄 Verifier 거부권 면제: "
                                    f"제목에 검증된 약칭 + 본문에 검증된 작가명 존재 (작가: {_matched_auth})",
                                    file=sys.stderr
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
            _is_genre_warn = 'genre_discussion' in _discourse_warn or 'discuss_genre' in _discourse_warn
            
            if decision.get("is_relevant") == False and decoder_out and verifier_out:
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

                if (
                    _titles_match
                    and _dec_conf in _HIGH
                    and _ver_conf in _HIGH
                    and _ver_relevant is True
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
                    if disc_out:
                        d_analysis = disc_out.get("discourse_analysis", {})
                        disc_domain = d_analysis.get("primary_domain", "")
                        is_assoc = d_analysis.get("is_association_not_discussion", False)
                    
                    # 🛡️ 연상글/뻘글에서 억지로 찾은 작가는 author_talk 보정 대상 아님
                    # 예: "모도쿠가 오소우" (VOCALOID곡) → 검색 중 "도쿠이모" 작가 발견
                    #     → 실제로는 작가 토론이 아닌 연상글/뻘글
                    _is_assoc_post = getattr(ctx, 'is_association_post', False) or is_assoc
                    
                    current_dt = decision.get("discussion_type", "")
                    # novel_literature 도메인 + 작가 식별 + noise/off_topic 분류 → author_talk로 보정
                    # 단, 연상글/뻘글(is_association_post)이면 보정 차단
                    if disc_domain == "novel_literature" and current_dt in ("noise", "off_topic", "community_banter") and not _is_assoc_post:
                        print(
                            f"[{_ts()}][{self.emoji}] 🔧 author_talk 보정: "
                            f"Decoder 작가 식별={detected_authors}, Discourse={disc_domain}, "
                            f"기존 discussion_type={current_dt} → author_talk",
                            file=sys.stderr,
                        )
                        decision["discussion_type"] = "author_talk"
                        decision["is_relevant"] = False  # 작가 토론은 is_relevant=false
                        decision["notes"] = (
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
            
            # �🚨 P0-3: Arbiter 독자 제목 생성 금지
            # Decoder와 Verifier 모두 title을 식별하지 못했는데 Arbiter가 독자적으로 제목을 만들어낸 경우 차단
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
                            if not _in_suspected:
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
                    title_norm = final_title.replace(" ", "")
                    for arch_term in blocked_archetypes:
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
            if final_title and decision.get("is_relevant") and decoder_out and verifier_out:
                # Decoder의 overall confidence 확인
                dc_overall_conf = (decoder_out.get("overall_confidence") or "none").lower()
                
                # Verifier의 grounding 확인
                vf_grounding = (verifier_out.get("verification_result") or {}).get("grounding_check", {})
                vf_grounded = vf_grounding.get("decoder_grounded", True)
                vf_anchor = vf_grounding.get("anchor_found", "none")
                
                # Decoder confidence가 low/none이고 Verifier grounding도 약한 경우
                # 🆕 예외: Verifier confidence가 High이면 차단하지 않음
                #   (Verifier가 충분한 증거로 High 판정한 경우 존중)
                # 🔧 BUG-FIX: Verifier는 'novel_identity'를 반환하나 기존 코드가
                #   'novel_identification'을 읽어서 항상 기본값 'Low'가 되던 문제 수정
                _vr_for_conf = (verifier_out.get("verification_result") or {})
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
                    if vf_is_high and verifier_out.get("verification_result", {}).get("is_relevant"):
                        # Verifier가 High confidence로 is_relevant=True → 차단하지 않고 경고만
                        print(
                            f"[{_ts()}][{self.emoji}] ⚠️ 저신뢰 매칭 감지 but Verifier High 존중: "
                            f"Decoder conf={dc_overall_conf}, Verifier conf={vf_conf} "
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

            metadata_synthesis = result.get("metadata_synthesis")
            if not isinstance(metadata_synthesis, dict):
                metadata_synthesis = {}
                result["metadata_synthesis"] = metadata_synthesis

            vf_author_info = vf_result.get("author_info") or {}
            if not isinstance(vf_author_info, dict):
                vf_author_info = {}
            detected_author = str(vf_author_info.get("detected_author") or "").strip()

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

            if detected_author and not metadata_synthesis.get("detected_author"):
                metadata_synthesis["detected_author"] = detected_author
                print(
                    f"[{_ts()}][{self.emoji}] 🔬 metadata_synthesis.detected_author 보강: '{detected_author}'",
                    file=sys.stderr,
                )

            should_inject_author_reason = (
                decision.get("is_relevant") is True
                and bool(detected_author)
                and not bool(vf_author_info.get("is_author_criticism"))
            )
            if should_inject_author_reason:
                author_evidence_sentence = (
                    f"추가 근거: Verifier 및 검색 증거에서 '{detected_author}'가 해당 작품의 작가로 확인됨."
                )
                reasoning_text = decision.get("final_reasoning") or decision.get("reason") or ""
                if isinstance(reasoning_text, str):
                    reasoning_text = reasoning_text.strip()
                else:
                    reasoning_text = ""
                if reasoning_text and "작가는 식별되지 않았으나" in reasoning_text:
                    reasoning_text = reasoning_text.replace(
                        "작가는 식별되지 않았으나",
                        f"작가 '{detected_author}'가 식별되며",
                    )
                if detected_author not in reasoning_text:
                    if reasoning_text:
                        if not reasoning_text.endswith((".", "!", "?")):
                            reasoning_text += "."
                        reasoning_text += " " + author_evidence_sentence
                    else:
                        reasoning_text = author_evidence_sentence
                    decision["final_reasoning"] = reasoning_text
                    print(
                        f"[{_ts()}][{self.emoji}] 🔬 final_reasoning 작가 근거 보강: '{detected_author}'",
                        file=sys.stderr,
                    )
            
            # 🔧 Phase26-D: Arbiter 후처리 완료 후 official_title이 null이면
            # downstream(agentic_pipeline)이 Verifier로 폴백하지 않도록 플래그 설정
            # 🔧 Phase27-B: 단, suspected_titles에 High confidence 후보가 있으면 플래그를 설정하지 않음
            #   (downstream에서 suspected_titles 기반으로 title을 복구할 수 있도록 허용)
            _final_title = decision.get("official_title") or decision.get("official_novel_title")
            if not _final_title:
                _has_high_suspected_for_null = any(
                    isinstance(st, dict)
                    and st.get("title")
                    and str(st.get("confidence", "")).lower() in ("high", "0.95")
                    for st in (ctx.suspected_titles or [])
                )
                if _has_high_suspected_for_null and decision.get("is_relevant", False):
                    # suspected_titles에 강한 후보가 있으므로 deliberate null 차단 안 함
                    # → agentic_pipeline에서 Verifier 폴백 또는 suspected_titles로 복구 가능
                    _best_suspected = max(
                        (st for st in (ctx.suspected_titles or [])
                         if isinstance(st, dict) and st.get("title")
                         and str(st.get("confidence", "")).lower() in ("high", "0.95")),
                        key=lambda s: s.get("confidence", ""),
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
                else:
                    decision["_title_deliberately_null"] = True
                    print(
                        f"[{_ts()}][{self.emoji}] 🏷️ _title_deliberately_null 플래그 설정: "
                        f"Arbiter 후처리 결과 official_title=null → Verifier 폴백 차단",
                        file=sys.stderr
                    )

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
            return self._fallback_decision(ctx, str(e))
    
    def _call_llm(self, user_prompt: str) -> Dict[str, Any]:
        """LLM 호출"""
        system_content = ARBITER_SYSTEM.replace("{platform_map}", PLATFORM_ABBREVIATION_MAP)
        max_tokens = int(os.getenv("ARBITER_MAX_TOKENS", "1536"))
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
    
    def _correct_title_from_search(self, llm_title: str, search_results: list) -> str:
        """
        🔥 LLM 제목을 검색 결과의 공식 제목과 대조하여 교정.
        best-match 방식 + 0.80 임계값 + LLM 제목이 검색에 있으면 교정 안 함
        """
        import re
        from difflib import SequenceMatcher
        from collections import Counter
        
        official_platforms = OFFICIAL_PLATFORMS
        
        # Step 0: LLM 제목이 검색 결과에 정확히 존재하면 교정 불필요
        for sr in search_results:
            url = sr.get("url", "")
            if not any(p in url for p in official_platforms):
                continue
            sr_title = sr.get("title", "")
            if " - " in sr_title:
                sr_title = sr_title.split(" - ")[-1].strip()
            sr_title = re.sub(r'\s*\(r\d+\s*판\)$', '', sr_title).strip()
            if sr_title == llm_title:
                return llm_title
        
        # Step 1: 모든 공식 후보 수집 + 빈도 계산
        candidates = []
        for sr in search_results:
            url = sr.get("url", "")
            if not any(p in url for p in official_platforms):
                continue
            sr_title = sr.get("title", "")
            if " - " in sr_title:
                sr_title = sr_title.split(" - ")[-1].strip()
            sr_title = re.sub(r'\s*\(r\d+\s*판\)$', '', sr_title).strip()
            if sr_title and len(sr_title) >= 3:
                candidates.append(sr_title)
        
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
        
        강제승격 / 합의보호 / Verifier 거부권 등
        후처리 교정 시 한쪽 전문가 reason만 가져오지 않고
        전체 파이프라인 증거를 종합한다.
        
        Args:
            ctx: ConversationContext (전문가 outputs 포함)
            tag: 교정 유형 태그 (e.g. "강제승격", "합의보호", "거부권")
            is_relevant: 교정 후 최종 판정
        
        Returns:
            종합된 reason 문자열
        """
        from .orchestrator import ExpertType
        
        parts = []
        
        # --- 1) Decoder 증거 ---
        decoder_out = ctx.get_expert_output(ExpertType.DECODER) or {}
        dec_terms = decoder_out.get("decoded_terms", [])
        dec_items = []
        for dt in dec_terms:
            bm = dt.get("best_match") or {}
            if bm.get("title"):
                orig = dt.get("original", "?")
                title = bm["title"]
                anchor = bm.get("anchor_evidence", "")
                conf = bm.get("confidence", "")
                item = f"'{orig}'→'{title}'({conf})"
                if anchor:
                    item += f" anchor={anchor}"
                dec_items.append(item)
            if dt.get("is_author_name"):
                ai = (dt.get("author_info") or {}).get("name", "")
                if ai:
                    dec_items.append(f"작가 '{ai}' 식별")
        if dec_items:
            parts.append(f"Decoder: {'; '.join(dec_items)}")
        
        # --- 2) Verifier 증거 ---
        verifier_out = ctx.get_expert_output(ExpertType.VERIFIER) or {}
        vf_result = verifier_out.get("verification_result") or {}
        vf_relevant = vf_result.get("is_relevant")
        vf_novel = vf_result.get("novel_identity") or {}
        vf_title = vf_novel.get("official_novel_title") or vf_novel.get("official_title") or ""
        vf_reason = verifier_out.get("reason") or verifier_out.get("final_reasoning") or ""
        vf_conf = vf_novel.get("confidence") or vf_result.get("confidence") or ""
        vf_author_info = vf_result.get("author_info") or {}
        vf_detected_author = ""
        vf_is_author_criticism = False
        if isinstance(vf_author_info, dict):
            vf_detected_author = str(vf_author_info.get("detected_author") or "").strip()
            vf_is_author_criticism = bool(vf_author_info.get("is_author_criticism"))
        rejection = vf_result.get("rejection_reason") or ""
        vf_grounding = vf_result.get("grounding_check") or {}
        vf_anchor = vf_grounding.get("anchor_found")
        vf_decoder_grounded = vf_grounding.get("decoder_grounded")
        vf_counters = vf_result.get("counter_arguments") or []
        vf_critical_counters = [
            str((arg or {}).get("issue", "")).strip()
            for arg in vf_counters
            if isinstance(arg, dict)
            and str((arg or {}).get("severity", "")).lower() == "critical"
            and str((arg or {}).get("action", "")).lower() == "reject"
            and str((arg or {}).get("issue", "")).strip()
        ]
        
        vf_parts = []
        if vf_title:
            vf_parts.append(f"제목='{vf_title}'({vf_conf})")
        if vf_detected_author:
            author_role = "author_criticism" if vf_is_author_criticism else "author_mention"
            vf_parts.append(f"author={vf_detected_author}({author_role})")
        vf_parts.append(f"relevant={vf_relevant}")
        if vf_anchor is not None or vf_decoder_grounded is not None:
            vf_parts.append(
                f"grounding(anchor={vf_anchor}, decoder_grounded={vf_decoder_grounded})"
            )
        if vf_reason:
            vf_reason_text = " ".join(str(vf_reason).split())
            vf_parts.append(vf_reason_text)
        if rejection and not vf_relevant:
            rejection_text = " ".join(str(rejection).split())
            vf_parts.append(f"거부사유: {rejection_text}")
        if vf_critical_counters:
            vf_parts.append(
                "critical_counter=" + ", ".join(vf_critical_counters)
            )
        parts.append(f"Verifier: {'; '.join(vf_parts)}")
        
        # --- 3) DiscourseAnalyzer 증거 ---
        primary_domain = getattr(ctx, 'primary_domain', '') or ''
        discourse_intent = getattr(ctx, 'discourse_intent', '') or ''
        discourse_warning = getattr(ctx, 'discourse_warning', '') or ''
        if primary_domain:
            disc_str = f"DiscourseAnalyzer: domain={primary_domain}, intent={discourse_intent}"
            if discourse_warning:
                discourse_warning_text = " ".join(str(discourse_warning).split())
                disc_str += f", ⚠️ warning={discourse_warning_text}"
                _dw = discourse_warning.lower()
                if "genre_discussion" in _dw or "discuss_genre" in _dw:
                    disc_str += ", genre_warning=ON"
            parts.append(disc_str)
        
        # --- 4) 검색 증거 (suspected_titles) ---
        if ctx.suspected_titles:
            st_items = []
            for st in ctx.suspected_titles[:3]:
                st_title = st.get("title", "?")
                st_conf = st.get("confidence", "?")
                st_source = st.get("source_expert", "")
                st_items.append(f"'{st_title}'(conf={st_conf})")
            parts.append(f"검색증거: {'; '.join(st_items)}")
        
        # --- 5) Gatekeeper 간략 ---
        gk_out = ctx.get_expert_output(ExpertType.GATEKEEPER) or {}
        gk_noise = gk_out.get("is_noise")
        gk_type = gk_out.get("post_type", "")
        if gk_type or gk_noise is not None:
            parts.append(f"Gatekeeper: noise={gk_noise}, type={gk_type}")
        
        # --- 종합 구성 ---
        verdict = "관련 포스트" if is_relevant else "비관련 포스트"
        header = f"[{tag}] 종합 판정: {verdict}."
        body = " | ".join(parts) if parts else "증거 없음"
        
        return f"{header} {body}"
    
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
        reason = vf_result.get("reason") if vf_result else None
        
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
