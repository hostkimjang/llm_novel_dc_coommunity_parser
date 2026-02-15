# 🏗️ 시스템 아키텍처 문서

> **프로젝트**: llm_novel_dc_coommunity_parser  
> **목적**: DC인사이드 장르소설 갤러리 포스트에서 웹소설 작품을 식별하는 LLM Agentic Pipeline  
> **최종 갱신**: 2025-01-XX  

---

## 목차

1. [시스템 개요](#1-시스템-개요)
2. [파이프라인 흐름](#2-파이프라인-흐름)
3. [전문가 상세 명세](#3-전문가-상세-명세)
4. [데이터 흐름 및 공유 객체](#4-데이터-흐름-및-공유-객체)
5. [공유 구성 요소](#5-공유-구성-요소)
6. [Orchestrator 라우팅 정책](#6-orchestrator-라우팅-정책)
7. [후처리 정책 (Arbiter 하드코드 규칙)](#7-후처리-정책)
8. [검색 시스템](#8-검색-시스템)
9. [토큰 최적화 이력](#9-토큰-최적화-이력)
10. [파일 구조 인덱스](#10-파일-구조-인덱스)

---

## 1. 시스템 개요

### 1.1 도메인 컨텍스트

DC인사이드 장르소설 갤러리(장르소설 마이너갤러리)의 포스트를 입력받아, 해당 포스트가 **특정 웹소설 작품에 대한 토론인지** 식별합니다.

핵심 난제:
- **한국 웹소설 커뮤니티 축약어**: "죽깨수" → "죽음에서 깨어난 수학 천재", "전독시" → "전지적 독자 시점"
- **작가명/캐릭터명/작품명 혼동**: 동일 텍스트가 맥락에 따라 작가명 or 작품명
- **장르 토론 vs 작품 토론**: "요즘 무협물 추세" ≠ 특정 작품 토론
- **밈/비유/비꼼**: 커뮤니티 특유의 표현 방식

### 1.2 설계 원칙

| 원칙 | 설명 |
|------|------|
| **문장 구조 기반 원칙** | LLM 이해력은 특정 작품 하드코딩이 아닌, 한국어 문장 구조와 화용론 원칙으로 유도 |
| **플랫폼 매핑은 예시 제공** | "문피아→munpia.com" 등 사실적 매핑 테이블은 공유 상수로 제공 |
| **전문가 분업** | 각 전문가는 자기 역할에 특화된 관점으로만 분석 |
| **검증 우선** | Decoder가 식별 → Verifier가 반론 → Critic이 메타분석 → Arbiter가 종합 |
| **환각 방지** | Arbiter는 Decoder/Verifier가 제시하지 않은 제목을 독자적으로 생성할 수 없음 |

---

## 2. 파이프라인 흐름

### 2.1 전체 흐름도

```
┌──────────────────────────────────────────────────────────────────┐
│                     AgenticPipeline                              │
│  ┌───────────────────────────────────────────────────────────┐   │
│  │                    Orchestrator                           │   │
│  │                                                           │   │
│  │  Phase 1: Gatekeeper ──── noise? ──→ [조기 종료]          │   │
│  │     │                                                     │   │
│  │  Phase 1.5: DiscourseAnalyzer (도메인/의도 파악)          │   │
│  │     │                                                     │   │
│  │  Phase 2: 검색 실행 (Gatekeeper의 search_requests)        │   │
│  │     │                                                     │   │
│  │  Phase 3: 동적 루프 ─────────────────────────┐            │   │
│  │     │  ┌─────────────────────────────────┐   │            │   │
│  │     │  │ Decoder ──→ Verifier ──→ Critic │   │            │   │
│  │     │  │    ↕              ↕              │   │            │   │
│  │     │  │   [검색 재실행] [협력 요청]       │   │            │   │
│  │     │  └─────────────────────────────────┘   │            │   │
│  │     │                                        │            │   │
│  │  Phase 4: Arbiter (최종 종합 판정)            │            │   │
│  │                                               │            │   │
│  └───────────────────────────────────────────────────────────┘   │
│                                                                  │
│  _context_to_output() → PickvelOutputItemV2                      │
└──────────────────────────────────────────────────────────────────┘
```

### 2.2 Phase별 상세

| Phase | 전문가 | 조건 | 결과 |
|-------|--------|------|------|
| **1** | Gatekeeper | 항상 실행 | `is_noise`=true면 Phase 4 건너뛰고 조기 종료 |
| **1.5** | DiscourseAnalyzer | Gatekeeper 통과 시 | `primary_domain`, `discourse_intent` 설정 |
| **2** | (검색) | search_requests 존재 시 | `ctx.search_results`에 저장 |
| **3** | Decoder → Verifier → Critic | 순차적 | 동적 협력/재검색 포함 |
| **4** | Arbiter | 항상 실행 (Phase 3 완료 후) | 최종 판정 + 후처리 규칙 적용 |

### 2.3 Phase 3 동적 루프 내부 로직

```
_decide_next_action(ctx) 반환값:
├── "call_expert" → 전문가 호출
│   ├── 협력 요청 처리 (request_expert 필드 확인)
│   ├── verification_search → Decoder+Verifier 재호출 사이클
│   ├── unresolved_terms → 자동 재검색
│   └── low confidence → 자동 추가 검색 + Decoder 재호출
├── "search" → 추가 검색
└── "finalize" → 루프 종료, Phase 4로
```

---

## 3. 전문가 상세 명세

### 3.1 Gatekeeper

| 속성 | 값 |
|------|-----|
| **파일** | `experts/gatekeeper.py` (273줄) |
| **프롬프트** | `GATEKEEPER_SYSTEM` (L538~688), `GATEKEEPER_PROMPT` (L689~) |
| **LF 버전** | `LF_GATEKEEPER` (~1000 tok): §1화용론, §2담화구조, §4온라인언어, §6주제vs참조, §7담화영역 |
| **역할** | 첫 관문 — 노이즈 필터링 + 엔티티 추출 + 검색 쿼리 생성 |
| **특수 기능** | Kiwi 형태소 분석기 통합 (NNG/NNP/SL 품사 추출) |

**입력**:
- `post_data`: 포스트 원문 (title, content_blocks, author, url)
- `comments`: 댓글 리스트 (최대 15개)
- `rules_config`: noise_terms, novel_sites, slang_dictionary, trope_terms

**출력**:
```json
{
  "is_noise": false,
  "noise_reason": null,
  "detected_entities": {
    "possible_titles": ["죽깨수"],
    "possible_characters": ["이유백"],
    "possible_authors": [],
    "unknown_terms": ["목마"]
  },
  "search_requests": [
    {"query": "\"죽깨수\" 웹소설", "purpose": "title_verification", "priority": 1}
  ]
}
```

**Kiwi 통합 흐름**:
```
LLM 분석 결과 ←→ Kiwi 형태소 분석 결과 → _merge_entities() → 최종 엔티티
```

---

### 3.2 DiscourseAnalyzer

| 속성 | 값 |
|------|-----|
| **파일** | `experts/discourse.py` (규칙 기반 + LLM) |
| **역할** | 포스트의 담론적 도메인과 의도를 파악 |
| **호출 조건** | Gatekeeper 통과 후 (Phase 1.5) |

**입력**: `post_data`, `comments`

**출력**:
```json
{
  "discourse_analysis": {
    "primary_domain": "novel_work",  // novel_work | real_world | meta | mixed
    "intent": "discussion",          // discussion | recommendation | meme | review | ...
    "confidence": 0.85
  }
}
```

**ctx에 저장되는 필드**: `ctx.primary_domain`, `ctx.discourse_intent`  
→ 이후 Verifier, Arbiter가 도메인 교차 검증에 활용

---

### 3.3 Decoder

| 속성 | 값 |
|------|-----|
| **파일** | `experts/decoder.py` (661줄) |
| **프롬프트** | `DECODER_SYSTEM` (L1392~1776), `DECODER_PROMPT` (L1777~) |
| **LF 버전** | `LF_DECODER` (~800 tok): §4축약어원리, §5정보확정성, §8지시표현, §3문법구조 |
| **역할** | 축약어/은어 해독 + 검색 결과 매칭 + 작가 식별 |
| **공유 상수** | `PLATFORM_ABBREVIATION_MAP` (`{platform_map}` placeholder) |

**입력**:
- `gatekeeper_output`: Gatekeeper의 detected_entities
- `search_results`: 현재까지의 검색 결과
- `slang_dictionary`: 알려진 은어 사전
- `conversation_context`: 대화 요약
- `ctx`: ConversationContext (suspected_titles 초기 생성용)

**출력**:
```json
{
  "decoded_terms": [
    {
      "original": "죽깨수",
      "type": "abbreviation",
      "decoded_meaning": "죽음에서 깨어난 수학 천재",
      "best_match": {
        "title": "죽음에서 깨어난 수학 천재",
        "url": "https://novelpia.com/...",
        "confidence": 0.95
      },
      "is_author_name": false,
      "author_info": null,
      "candidates": [...],
      "supporting_evidence": [...]
    }
  ],
  "overall_confidence": "High",
  "verification_search": ["\"죽음에서 깨어난 수학 천재\" 웹소설"],  // 재검색 요청
  "unresolved_terms": [...]  // 미해결 용어
}
```

**특수 로직**:
- `_try_split_abbreviation_boundary()`: 한국어 축약어의 음절 경계를 형태소 분석으로 분할 시도
- `_expand_repetition_patterns()`: 반복 패턴 확장 (ㅋㅋㅋ 등)
- `_check_session_knowledge()`: 이전 포스트에서 학습한 축약어 재활용
- `_init_suspected_titles()`: 첫 호출 시 ctx.suspected_titles 초기 생성
- `_call_llm()`: `DECODER_SYSTEM.replace("{platform_map}", PLATFORM_ABBREVIATION_MAP)`

---

### 3.4 Verifier

| 속성 | 값 |
|------|-----|
| **파일** | `experts/verifier.py` (363줄) |
| **프롬프트** | `VERIFIER_SYSTEM` (L2384~3024), `VERIFIER_PROMPT` (L3025~3270) |
| **LF 버전** | `LF_VERIFIER` (~700 tok): §1발화대상구분, §2일관성검증, §6주제vs참조, §7담화영역일관성 |
| **역할** | Decoder 결과 비판적 검증 — 반론 생성, 앵커 검증, 환각 탐지 |

**입력**:
- `post_data`, `comments`
- `gatekeeper_output` (요약: `_summarize_gatekeeper()`)
- `decoder_output` (요약: `_summarize_decoder()`)
- `search_results` **(제한됨)**: Decoder가 실제 참조한 URL만 필터링 (최대 8개)
- `conversation_context`, `ctx`

**출력**:
```json
{
  "verification_result": {
    "is_relevant": true,
    "novel_identity": {
      "official_novel_title": "죽음에서 깨어난 수학 천재",
      "heretic_url": "https://...",
      "confidence": "High"
    },
    "rejection_reason": null,
    "reason": "..."
  },
  "verification_search": [...]  // 추가 검색 요청
}
```

**토큰 최적화 (Orchestrator가 수행)**:
```python
# Decoder가 참조한 URL만 추출
used_urls = {term["best_match"]["url"] for term in decoded_terms if ...}
limited_search = [r for r in search_results if r["url"] in used_urls][:8]
```

**특수 로직**:
- `_update_suspected_titles()`: Verifier 판정 결과로 suspected_titles 업데이트
- `_summarize_gatekeeper()`: Gatekeeper 출력을 핵심만 추출
- `_summarize_decoder()`: Decoder 출력을 핵심만 추출

**프롬프트 핵심 정책 (VERIFIER_SYSTEM)**:
- 비판적 사고 4원칙 + 반론 생성 의무
- BLOCKING RULES (부분 문자열 매칭 금지, 순환 참조 금지)
- 앵커 검증: 본문에서 직접 증거가 없으면 거부
- 검색 결과 해석: URL 도메인 기반 신뢰도 평가
- 작가 비평 vs 작품 토론 구분

---

### 3.5 Critic

| 속성 | 값 |
|------|-----|
| **파일** | `experts/critic.py` (256줄) |
| **프롬프트** | `CRITIC_SYSTEM` (L3271~3298), `CRITIC_PROMPT` (L3299~) |
| **역할** | 메타 분석 — 다른 전문가들의 분석 과정 자체를 비판적으로 검토 |
| **호출 조건** | `is_relevant=true`일 때만 호출 (비관련이면 스킵) |

**입력**:
- `post_data`, `comments`
- `verifier_result` (요약: `_summarize_verifier()`)
- `conversation_context`, `ctx`

**출력**:
```json
{
  "meta_analysis": {
    "agreement_level": "high",
    "potential_issues": [...],
    "confidence_adjustment": 0,
    "final_recommendation": "accept"
  }
}
```

**특수 로직**:
- `_adjust_suspected_titles()`: Critic 메타분석 결과로 suspected_titles의 신뢰도 조정

---

### 3.6 Arbiter

| 속성 | 값 |
|------|-----|
| **파일** | `experts/arbiter.py` (1230줄) |
| **프롬프트** | `ARBITER_SYSTEM` (인라인, L25~626) |
| **LF 버전** | `LF_ARBITER` (~400 tok): 6개 핵심 원칙 요약 |
| **역할** | 최종 종합 판정 — 전문가 합의 평가, 갈등 해소, official_title 결정 |
| **공유 상수** | `PLATFORM_ABBREVIATION_MAP` (`{platform_map}` placeholder) |

**입력**: `ctx` (ConversationContext 전체)

**출력**:
```json
{
  "final_decision": {
    "is_relevant": true,
    "official_novel_title": "...",
    "official_title": "...",
    "heretic_url": "...",
    "confidence": "High",
    "discussion_type": "review",
    "reason": "..."
  },
  "expert_consensus": {
    "unanimous": true,
    "agreeing_experts": ["decoder", "verifier", "critic"]
  },
  "metadata_synthesis": {
    "sentiment": "positive",
    "micro_tags": [...],
    "is_nsfw": false
  },
  "final_reasoning": "..."
}
```

**특수 로직**:
- suspected_titles 병합: Decoder→Verifier→Critic이 업데이트한 목록을 최종 병합
- `_call_llm()`: `ARBITER_SYSTEM.replace("{platform_map}", PLATFORM_ABBREVIATION_MAP)`
- **후처리 규칙**: 아래 [§7](#7-후처리-정책) 참조

---

## 4. 데이터 흐름 및 공유 객체

### 4.1 ConversationContext (핵심 공유 객체)

`orchestrator.py` L98에 정의된 `@dataclass`. 모든 전문가가 이 객체를 통해 데이터를 공유합니다.

```
ConversationContext
├── post_id: int                    # 포스트 ID
├── post_data: Dict                 # 원본 포스트 데이터
├── comments: List[str]             # 댓글 리스트 (최대 15개)
├── search_results: List[Dict]      # 누적 검색 결과 (URL 중복 제거됨)
├── messages: List[ExpertMessage]   # 전문가 간 메시지 로그
├── expert_outputs: Dict            # 전문가별 최종 출력 {"gatekeeper": {...}, ...}
├── suspected_titles: List[Dict]    # ⭐ 추정 작품 목록 (전문가 간 공유)
├── primary_domain: Optional[str]   # DiscourseAnalyzer 결과
├── discourse_intent: Optional[str] # DiscourseAnalyzer 결과
├── expert_confidence: Dict         # 전문가별 신뢰도
├── uncertainty_sources: List[str]  # 불확실성 요인
├── token_usage: Dict               # 토큰 사용량 추적
└── iteration: int                  # 현재 루프 반복 횟수
```

### 4.2 suspected_titles 생명주기

`suspected_titles`는 가장 중요한 전문가 간 공유 데이터입니다.

```
Decoder._init_suspected_titles()    ← 최초 생성 (decoded_terms에서 후보 추출)
    │
    ▼
Verifier._update_suspected_titles() ← 검증 결과로 업데이트 (확인/거부/신뢰도 조정)
    │
    ▼
Critic._adjust_suspected_titles()   ← 메타분석 결과로 신뢰도 재조정
    │
    ▼
Arbiter.analyze()                   ← 최종 병합 + 정렬 (상위 5개 유지)
    │
    ▼
P0-3 후처리                         ← suspected에 있으면 Low로 허용, 없으면 차단
```

**suspected_titles 항목 구조**:
```json
{
  "title": "죽음에서 깨어난 수학 천재",
  "confidence": 0.85,
  "source": "decoder",
  "url": "https://...",
  "is_author": false
}
```

### 4.3 전문가 간 데이터 의존성

```
                    ┌─────────────────────────────────────────┐
                    │                                         │
Gatekeeper ────────▶ Decoder ────────▶ Verifier ────────▶ Critic
  │ detected_entities  │ decoded_terms    │ verification_     │ meta_analysis
  │ search_requests    │ suspected_titles │   result          │ adjusted_titles
  │                    │ verification_    │ updated_titles    │
  │                    │   search         │                   │
  │                    │                  │                   │
  └────────────────────┴──────────────────┴───────────────────┘
                    │                                         │
                    ▼                                         ▼
               Arbiter ◀──────────────────────────────────────┘
                    │
                    ▼
            final_decision + 후처리 규칙
```

### 4.4 검색 결과 공유 패턴

```
ctx.search_results (전체 누적)
    │
    ├── Decoder: 전체 search_results 수신
    │
    └── Verifier: ⭐ Decoder가 참조한 URL만 필터링 (limited_search)
        └── Orchestrator._call_expert()에서 필터링 로직 수행
            used_urls = Decoder의 best_match + supporting_evidence URL
            limited_search = [r for r if r.url in used_urls][:8]
```

---

## 5. 공유 구성 요소

### 5.1 LINGUISTIC_FRAMEWORK 체계

`expert_prompts.py`에 정의된 언어학 프레임워크입니다.

| 상수 | 위치 | 토큰 | 사용처 | 포함 섹션 |
|------|------|------|--------|-----------|
| `LINGUISTIC_FRAMEWORK` | L11~421 | ~6,259 | 참조용 (삽입 안 됨) | 전체 8개 섹션 |
| `LF_GATEKEEPER` | L447~474 | ~1,000 | GATEKEEPER_SYSTEM | §1화용론, §2담화구조, §4온라인언어, §6주제vs참조, §7담화영역 |
| `LF_DECODER` | L475~498 | ~800 | DECODER_SYSTEM | §4축약어원리, §5정보확정성, §8지시표현, §3문법구조 |
| `LF_VERIFIER` | L499~521 | ~700 | VERIFIER_SYSTEM | §1발화대상구분, §2일관성검증, §6주제vs참조, §7담화영역일관성 |
| `LF_ARBITER` | L522~537 | ~400 | ARBITER_SYSTEM | 6개 핵심 원칙 요약 |

**설계 원칙**: 각 전문가는 자기 역할에 필요한 언어학 섹션만 수신하여 토큰 절약.

### 5.2 PLATFORM_ABBREVIATION_MAP

`expert_prompts.py` L422~446에 정의된 공유 플랫폼 약칭 매핑 테이블.

```
약칭 → 정식명 → 도메인
문피아   munpia       munpia.com
노벨피아 novelpia     novelpia.com
조아라   joara        joara.com
카카오   kakaopage    page.kakao.com
네이버   naver series series.naver.com
리디     ridibooks    ridibooks.com
북큐브   bookcube     bookcube.com

UI/메타 용어:
헤레틱(heretic) → 작품 고유 URL/페이지
```

**삽입 방식**: `{platform_map}` placeholder → `.replace("{platform_map}", PLATFORM_ABBREVIATION_MAP)`

| 사용 파일 | 삽입 위치 |
|-----------|-----------|
| `decoder.py` L397 | `DECODER_SYSTEM.replace("{platform_map}", ...)` |
| `arbiter.py` | `ARBITER_SYSTEM.replace("{platform_map}", ...)` |

### 5.3 Rules Config (rules.py)

`rules.py`에 정의된 정적 규칙 세트.

| 상수 | 용도 |
|------|------|
| `NOISE_TERMS` | 노이즈 판별 키워드 (광고, 정치, 스포츠 등) |
| `NOVEL_SITES` | 공식 웹소설 플랫폼 도메인 목록 |
| `SLANG_DICTIONARY` | 알려진 축약어→정식명 사전 |
| `TROPE_TERMS` | 장르 트로프 키워드 (회귀, 빙의, 현판 등) |

→ `AgenticPipeline.__init__()`에서 `self.rules_config`로 합산, Gatekeeper/Decoder에 전달

---

## 6. Orchestrator 라우팅 정책

### 6.1 _decide_next_action() 결정 트리

```
_decide_next_action(ctx):
│
├── 1. 협력 요청 확인 (request_expert 필드)
│   ├── 전체 협력 횟수 ≥ MAX_TOTAL_COLLABORATIONS(2)? → 무시
│   ├── 같은 쌍(request_key) 이미 처리? → 무시
│   └── 통과 → {"action": "call_expert", "expert": requested, "collaboration": True}
│
├── 2. 순차 진행
│   ├── Decoder 완료 & Verifier 미완료 → Verifier 호출
│   ├── Verifier 완료 & Critic 미완료 & is_relevant=true → Critic 호출
│   └── Gatekeeper 완료 & Decoder 미완료 → Decoder 호출
│
├── 3. 종료 조건
│   ├── GK+DC+VF 완료 & is_relevant=false → finalize (Critic 불필요)
│   ├── GK+DC+VF+CR 완료 → finalize
│   └── iteration ≥ max_iterations → finalize
│
└── 4. 기본값 → finalize
```

### 6.2 협력 제한 정책

| 제한 | 값 | 적용 위치 |
|------|-----|-----------|
| 같은 전문가 쌍 협력 | **최대 1회** | `_processed_requests` set |
| 전체 협력 요청 | **최대 2회** | `_total_collaborations` counter |
| 동적 루프 최대 반복 | **10회** (안전장치, 실제 3~5회) | `ctx.max_iterations` |

### 6.3 자동 재검색 트리거

| 트리거 | 조건 | 동작 |
|--------|------|------|
| `verification_search` | Decoder/Verifier가 요청 | 검색 실행 → Decoder 재호출 → Verifier 재호출 |
| `unresolved_terms` | Decoder가 미해결 용어 반환 | 자동 검색 (용어당 쿼리 생성) |
| Low confidence | Decoder confidence = low/none | 형태소 분석으로 명사 추출 → 자동 검색 → Decoder 재호출 |

### 6.4 Critic 호출 조건

```
Critic은 is_relevant=true일 때만 호출됨.
이유: is_relevant=false인 경우 메타분석 불필요, 토큰 절약.
```

---

## 7. 후처리 정책

Arbiter의 `analyze()` 메서드 후반부에 하드코드된 후처리 규칙들입니다. LLM 응답을 받은 후 Python 코드로 강제 보정합니다.

### 7.1 P0-1: Verifier 거부권 (arbiter.py ~L964)

```
조건: Verifier의 verification_result.is_relevant == false
동작: 강제로 is_relevant=false, official_title=null 설정
우선순위: 최고 — LLM이 무시해도 코드가 강제 적용
```

### 7.2 P0-2: 작가 이름 필터 (arbiter.py ~L987)

```
조건: Decoder의 decoded_terms에 is_author_name=true인 항목 존재
     AND official_title == 작가 이름
동작: official_title=null, is_relevant=false, discussion_type="author_talk"
```

### 7.3 P0-3: Arbiter 독자 제목 생성 금지 (arbiter.py ~L1010)

```
Case A: Decoder도 Verifier도 title 없음
  ├── arbiter_title이 suspected_titles에 있으면 → confidence="Low"로 허용
  └── suspected_titles에도 없으면 → null 강제, is_relevant=false

Case B: Decoder 후보에도 없고 Verifier와도 다른 새 제목
  ├── suspected_titles에 있으면 → 허용
  └── suspected_titles에도 없으면 → Decoder 최선 후보로 교체
```

### 7.4 suspected_titles 최종 병합 (arbiter.py ~L813)

```
기존 ctx.suspected_titles + Arbiter LLM 응답의 suspected_titles
→ confidence 기준 내림차순 정렬
→ 상위 5개만 유지
→ ctx.suspected_titles에 저장
```

### 7.5 5단계 폴백 체인 (agentic_pipeline.py ~L310)

`_context_to_output()`에서 `reason` 필드 생성 시 적용:

```
1. arbiter_out["final_reasoning"]
2. arbiter_out["conflict_resolution"][0]["reasoning"]
3. final_decision["reason"]
4. verifier_out["verification_result"]["rejection_reason"] 또는 ["reason"]
5. gatekeeper_out["noise_reason"]
6. 컨텍스트 기반 기본 메시지 (is_relevant/official_title/discussion_type 조합)
   → "분석 완료" 같은 무의미한 텍스트 방지
```

### 7.6 discussion_type 정합성 검증 (agentic_pipeline.py ~L280)

```
유효값: review, spoiler, anticipation, meme, author_talk, character_talk,
       general, meta, recommendation, trope_discussion, noise

레거시 매핑:
  work_discussion → review
  author_criticism → author_talk
  genre_discussion → trope_discussion

정합성 규칙:
  is_relevant=true AND discussion_type="noise" → "general"로 변경
```

---

## 8. 검색 시스템

### 8.1 검색 실행 흐름

```
AgenticPipeline._search(query)
    │
    ├── MCPClient.search(query)  → raw 결과
    │
    ├── top_k 제한 (환경변수 MCP_TOP_K_RESULTS, 기본 10)
    │
    └── content 축소 (환경변수 MCP_MAX_CONTENT_CHARS, 기본 400)
        └── compacted results 반환
```

### 8.2 Orchestrator._execute_searches()

```
입력: search_requests 리스트 (최대 5개 쿼리)
    │
    ├── URL 기반 중복 제거 (seen_urls set)
    │
    ├── 관련성 필터링 (_is_relevant_result)
    │   ├── 무관 도메인 제외 (youtube, github, wikipedia 등)
    │   ├── 관련 도메인 통과 (munpia, novelpia, dcinside 등)
    │   └── 키워드 기반 판단 (소설, 웹소설, 작가, 연재 등)
    │
    ├── content 축소 (100자)
    │
    └── 우선순위 재정렬 (_prioritize_search_results)
        ├── 0순위: 공식 플랫폼 + 작가 패턴
        ├── 1순위: 공식 플랫폼
        ├── 2순위: 작가 패턴 포함
        ├── 3순위: 커뮤니티 토론
        └── 4순위: 기타
```

### 8.3 자기 참조 방지 (ConversationContext.add_search_results)

```
현재 post_id / post_url을 검색 결과 URL과 대조
→ 자기 참조 URL은 자동 제외
→ URL 기반 중복도 제거
```

---

## 9. 토큰 최적화 이력

### 9.1 최적화 전후 비교

| 전문가 | 최적화 전 (토큰) | 주요 변경 | 예상 절감 |
|--------|------------------|-----------|-----------|
| **Verifier** | ~43,948 | SYSTEM+PROMPT 대규모 압축, LF_VERIFIER | **~60%** (~17,500 토큰) |
| **Decoder** | ~23,492 | LF_DECODER, 플랫폼 매핑 공유 | ~15% |
| **Gatekeeper** | ~22,100 | LF_GATEKEEPER | ~15% |
| **Arbiter** | ~17,298 | LF_ARBITER, 플랫폼 매핑 공유 | ~10% |
| **Critic** | ~3,202 | 변경 없음 | 0% |

### 9.2 expert_prompts.py 줄 수 변화

```
최적화 전: 4,982줄
최적화 후: 3,505줄 (약 30% 감소)
```

### 9.3 주요 최적화 내용

| 카테고리 | 세부 항목 | 절감 |
|----------|-----------|------|
| **LF 슬림화** | 6,259 tok 풀 버전 → 전문가별 400~1,000 tok | ~19K tok (4회 삽입 기준) |
| **Verifier SYSTEM** | 한국어 문맥 이해력 100줄→20줄 | ~3,500 tok |
| | 검색 결과 재평가 250줄→30줄 | ~5,000 tok |
| | 부분 문자열 매칭 반복 3~4회→1회 | ~2,500 tok |
| | 본문 다시 읽기 120줄→15줄 | ~2,000 tok |
| **Verifier PROMPT** | [1-6단계] 형태소 검증 프로세스 삭제 | ~4,400 tok |
| | 축약어 감지 CRITICAL 2+3 200줄→15줄 | ~4,000 tok |
| | 작가 비평 판별 120줄→10줄 | ~3,000 tok |
| | 장르 토론 구분 120줄→8줄 | ~3,000 tok |
| **플랫폼 매핑** | Decoder+Arbiter 인라인 중복 → 공유 상수 | ~500 tok |

### 9.4 최적화 원칙

1. **중복 제거**: 같은 내용이 SYSTEM과 PROMPT 양쪽에 있으면 한 곳에만 유지
2. **SYSTEM 참조**: PROMPT에서 "SYSTEM의 BLOCKING RULES 참조" 식으로 참조만 남김
3. **체크리스트화**: 긴 설명을 → 짧은 체크리스트로 압축
4. **핵심 보존**: 압축 시 판단 품질에 직접 영향을 주는 원칙은 절대 삭제하지 않음

---

## 10. 파일 구조 인덱스

### 10.1 핵심 파일 목록

| 파일 | 줄 수 | 역할 |
|------|-------|------|
| `src/llm_batch/prompts/expert_prompts.py` | 3,505 | 모든 프롬프트 + LF 슬림 + 공유 상수 |
| `src/llm_batch/experts/arbiter.py` | 1,230 | Arbiter 전문가 + 인라인 시스템 프롬프트 + 후처리 규칙 |
| `src/llm_batch/experts/orchestrator.py` | 1,025 | ConversationContext + Orchestrator (동적 라우팅) |
| `src/llm_batch/experts/decoder.py` | 661 | Decoder 전문가 + 축약어 분할 로직 |
| `src/llm_batch/agentic_pipeline.py` | 523 | 파이프라인 진입점 + 결과 변환 + 세션 지식 |
| `src/llm_batch/experts/verifier.py` | 363 | Verifier 전문가 + suspected_titles 업데이트 |
| `src/llm_batch/experts/gatekeeper.py` | 273 | Gatekeeper + Kiwi 형태소 분석기 |
| `src/llm_batch/experts/critic.py` | 256 | Critic 메타분석 + suspected_titles 조정 |
| `src/llm_batch/experts/discourse.py` | ~370 | DiscourseAnalyzer (담론 분석) |
| `src/llm_batch/experts/prompts.py` | ~30 | 레거시 호환 리다이렉트 모듈 |

### 10.2 expert_prompts.py 내부 구조

```
L11-421     LINGUISTIC_FRAMEWORK (원본, 참조용)
L422-446    PLATFORM_ABBREVIATION_MAP (공유 상수)
L447-474    LF_GATEKEEPER (슬림)
L475-498    LF_DECODER (슬림)
L499-521    LF_VERIFIER (슬림)
L522-537    LF_ARBITER (슬림)
L538-688    GATEKEEPER_SYSTEM
L689-1391   GATEKEEPER_PROMPT
L1392-1776  DECODER_SYSTEM
L1777-2383  DECODER_PROMPT
L2384-3024  VERIFIER_SYSTEM
L3025-3270  VERIFIER_PROMPT
L3271-3298  CRITIC_SYSTEM
L3299-3450  CRITIC_PROMPT
L3451-3505  assemble_final_output() 함수
```

### 10.3 지원 파일

| 파일 | 역할 |
|------|------|
| `src/llm_batch/models.py` | Pydantic 데이터 모델 (PostInput, PickvelOutputItemV2 등) |
| `src/llm_batch/rules.py` | 정적 규칙 세트 (NOISE_TERMS, NOVEL_SITES 등) |
| `src/llm_batch/llm/client.py` | LLM API 클라이언트 (OpenAI 호환) |
| `src/llm_batch/search/client.py` | MCP 검색 클라이언트 |
| `src/llm_batch/cli.py` | CLI 진입점 |
| `src/llm_batch/pipeline.py` | 기존 비-Agentic 파이프라인 (레거시) |

### 10.4 세션 지식 베이스

`AgenticPipeline.session_knowledge`는 배치 처리 시 포스트 간 학습을 유지합니다.

```python
session_knowledge = {
    "resolved_slang": {},       # 축약어 → 정식 제목 매핑
    "resolved_authors": {},     # 작가명 → 대표작 매핑
    "resolved_characters": {},  # 캐릭터명 → 작품 매핑
}
```

**학습 조건**: `confidence >= "High"` (잘못된 매칭 학습 방지)
**학습 시점**: `_update_session_knowledge()` (포스트 처리 완료 후)

---

## 부록: 정책 요약 체크리스트

### A. 환각 방지 정책

- [ ] Decoder/Verifier가 식별하지 못한 제목을 Arbiter가 생성하면 차단 (P0-3)
- [ ] suspected_titles에 존재하면 Low로 허용 (완화)
- [ ] 프롬프트에 특정 작품명 하드코딩 금지

### B. 작가 비평 구분 정책

- [ ] Decoder의 is_author_name 판정 → Arbiter 후처리에서 author_talk 분류 (P0-2)
- [ ] Verifier의 author_info 전달 → Arbiter가 참조 (P2-6)

### C. 토큰 절약 정책

- [ ] Verifier에게 Decoder가 참조한 검색 결과만 전달 (limited_search)
- [ ] 검색 결과 content 100자 축소
- [ ] 전문가별 LF 슬림 버전 사용
- [ ] is_relevant=false면 Critic 호출 스킵

### D. 무한 루프 방지 정책

- [ ] 전체 협력 최대 2회
- [ ] 같은 쌍 협력 최대 1회
- [ ] request_expert 필드 즉시 클리어
- [ ] 동적 루프 최대 10회 (안전장치)

### E. 데이터 정합성 정책

- [ ] 검색 결과 URL 기반 중복 제거
- [ ] 자기 참조(현재 post_id) URL 자동 제외
- [ ] discussion_type과 is_relevant 정합성 검증
- [ ] Confidence 값 정규화 (대소문자 통일)
