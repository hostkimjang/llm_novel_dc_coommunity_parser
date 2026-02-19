# Expert Orchestration System - 전문가 오케스트레이션 시스템

디시인사이드 장르소설 갤러리 크롤링 데이터를 **유기적 전문가 시스템(Agentic Expert System)**으로 분석하여 웹소설을 식별하고 담론 메타데이터를 추출합니다.

---

## 📋 목차

1. [핵심 개념](#-핵심-개념)
2. [전문가 시스템 아키텍처](#-전문가-시스템-아키텍처)
3. [전문가 간 협력 메커니즘](#-전문가-간-협력-메커니즘)
4. [파이프라인 단계별 상세](#-파이프라인-단계별-상세)
5. [후처리 시스템](#-후처리-시스템)
6. [타임어택 시스템](#-타임어택-시스템)
7. [설치 및 실행](#-설치-및-실행)
8. [프로젝트 구조](#-프로젝트-구조)
9. [전문가 역할 상세](#-전문가-역할-상세)
10. [실행 흐름도](#-실행-흐름도)
11. [규칙 엔진 (rules.py)](#-규칙-엔진-rulespy)
12. [출력 형식](#-출력-형식)
13. [환경 설정](#-환경-설정)
14. [병렬 처리 & 대시보드](#-병렬-처리--대시보드)
15. [고급 기능](#-고급-기능)
16. [트러블슈팅](#-트러블슈팅)

---

## 🎯 핵심 개념

### 유기적 전문가 시스템 (Agentic Expert System)

기존의 단방향 파이프라인과 달리, **8명의 전문가들이 서로 소통하고 협력**하여 문제를 해결하는 시스템입니다:

```
❌ 기존 방식 (Sequential Pipeline):
Stage0 → Stage1 → Stage2 → 결과

✅ 전문가 시스템 (Collaborative):
Orchestrator
    ↓
Gatekeeper ↔ Discourse ↔ Decoder ↔ Verifier ↔ Critic ↔ Synthesizer
    ↕           ↕          ↕          ↕          ↕          ↕
                    [검색/질문/요청]
    ↕           ↕          ↕          ↕          ↕          ↕
                   Arbiter (최종 판정)
```

**핵심 특징:**
- 🤝 **협력적**: 전문가들이 서로에게 질문하고 요청
  - Decoder → Verifier: "이 후보 검증해줘"
  - Verifier → Gatekeeper: "원문 다시 확인해줘"
  - Synthesizer → Arbiter: "증거 기반으로 재해석한 결과야"
- 🔄 **반복적**: 확신이 생길 때까지 재분석
  - 최대 10회 반복 (max_iterations=10)
  - 각 반복마다 전문가들이 새로운 정보 교환
- ⏱️ **타임어택**: 분석 시간이 부족하면 긴급 모드 진입
  - **NORMAL** → 충분한 시간, 자유로운 협력
  - **HIGH** → ⚠️ 시간 부족, 의견 정리 요구
  - **CRITICAL** → 🚨 즉시 결론 도출, Arbiter 강제 소환
- 🧠 **지능적**: 상황에 따라 동적으로 분석 전략 조정
- ⚖️ **균형적**: Arbiter가 갈등을 조정하고 최종 판단
- 🔬 **증거 기반**: Synthesizer가 모든 증거를 종합하여 재해석

---

## 🏗️ 전문가 시스템 아키텍처

### 전문가 구성원 (총 8명)

| 전문가 | 이모지 | 역할 | 전문 분야 | 코드 규모 |
|--------|--------|------|-----------|-----------|
| **Orchestrator** | 🎼 | 전문가 조율 | 전문가 간 라우팅, 대화 관리, 반복 제어 | ~3,744줄 |
| **Gatekeeper** | 🎭 | 커뮤니티 문화 분석 | 게시글 분류, 노이즈 필터, 엔티티 추출 | ~456줄 |
| **DiscourseAnalyzer** | 📖 | 담론/도메인 분석 | 글의 본질적 의도, 도메인 식별, 연상 vs 토론 구분 | ~367줄 |
| **Decoder** | 🔤 | 한글 슬랭 해독 | 초성체/축약어 복원, 검색 결과 매칭, snippet 분석 | ~4,060줄 |
| **Verifier** | 🔍 | 증거 검증 | 교차 검증, 거짓 긍정 방지, 증거 체인 구축 | ~986줄 |
| **Critic** | 📚 | 문학 비평 | 담론 분석, 감성 프로파일, NSFW 탐지 | ~246줄 |
| **Synthesizer** | 🔬 | 증거 기반 재해석 | 숨은 참조 발견, 증거 정합성 평가, 댓글 인사이트 | ~460줄 |
| **Arbiter** | ⚖️ | 최종 판정 | 전문가 의견 종합, 갈등 해소, 최종 결론 | ~2,859줄 |

> 전문가 코드 총 합계: **~13,178줄**

### ExpertType 열거형

```python
class ExpertType(Enum):
    GATEKEEPER   = "gatekeeper"
    DISCOURSE    = "discourse"
    DECODER      = "decoder"
    VERIFIER     = "verifier"
    CRITIC       = "critic"
    SYNTHESIZER  = "synthesizer"   # 증거 기반 재해석기
    ARBITER      = "arbiter"
```

### 시스템 흐름

```mermaid
graph TB
    Input[📥 커뮤니티 게시글] --> Orchestrator[🎼 Orchestrator]
    
    Orchestrator --> GK[🎭 Gatekeeper<br/>노이즈 필터 & 엔티티 추출]
    Orchestrator --> DA[📖 DiscourseAnalyzer<br/>도메인 & 의도 분석]
    
    DA -->|도메인 판정| GK
    DA -->|연상 글| Arbiter[⚖️ Arbiter<br/>최종 판정]
    
    GK -->|명확한 증거| Arbiter
    GK -->|불명확| SA[📋 snippet_analyzer<br/>본문/댓글 정밀 분석]
    
    SA -->|힌트 추출| Decoder[🔤 Decoder<br/>슬랭 해독]
    
    Decoder -->|후보 발견| Verifier[🔍 Verifier<br/>증거 검증]
    Decoder -->|추가 정보 필요| Search[🔍 SearchXNG]
    
    Search --> Decoder
    Search --> Verifier
    
    Verifier -->|확정| Critic[📚 Critic<br/>담론 분석]
    Verifier -->|불확실| GK
    
    Critic --> Synthesizer[🔬 Synthesizer<br/>증거 기반 재해석]
    
    Synthesizer --> Arbiter
    
    Arbiter --> PostProc[🔧 후처리<br/>일관성 검증 & 하드 게이트]
    PostProc --> Output[📤 최종 결과<br/>PickvelOutputItemV2]
    
    style Orchestrator fill:#e3f2fd
    style GK fill:#fff3e0
    style DA fill:#e1f5fe
    style SA fill:#f1f8e9
    style Decoder fill:#f3e5f5
    style Verifier fill:#e8f5e9
    style Critic fill:#fce4ec
    style Synthesizer fill:#ede7f6
    style Arbiter fill:#fff9c4
    style PostProc fill:#fbe9e7
    style Search fill:#e0f2f1
```

---

## 🤝 전문가 간 협력 메커니즘

### 메시지 교환 시스템

전문가들은 `ExpertMessage` 객체를 통해 서로 소통합니다:

```python
@dataclass
class ExpertMessage:
    from_expert: ExpertType      # 발신 전문가
    to_expert: ExpertType        # 수신 전문가 (None이면 전체)
    message_type: str            # "request", "question", "answer", "analysis"
    content: Dict[str, Any]      # 메시지 내용
    timestamp: float             # 타임스탬프
```

### 협력 패턴

#### 패턴 1: 순차 협력 (Sequential)
```
🎭 Gatekeeper → 🎼 Orchestrator
  "작품 토론으로 보이지만 제목이 모호함. 슬랭 해독 필요."
🎼 Orchestrator → 🔤 Decoder
  "'전독시' 해독해주세요"
🔤 Decoder → 🎼 Orchestrator
  "'전지적 독자 시점'으로 추정됨 (95% 신뢰도)"
🎼 Orchestrator → 🔍 Verifier
  "'전지적 독자 시점' 맞는지 검증해주세요"
```

#### 패턴 2: 증거 기반 재해석 (Synthesizer 협력)
```
🔤 Decoder → 🔬 Synthesizer
  "해독 결과: 캐릭터명 3개, 작가명 1개 식별"
🔍 Verifier → 🔬 Synthesizer
  "검증 결과: URL 증거 있지만 본문이 애매"
🔬 Synthesizer → ⚖️ Arbiter
  "원본 재해석: 본문+댓글이 작품에 대해 논의. 숨은 참조 2개 발견."
```

#### 패턴 3: 갈등 해소 (Conflict Resolution)
```
🔤 Decoder: "'노피아'는 '노벨피아 웹소설' 추천 글"
🔍 Verifier: "'노피아'는 플랫폼명, 작품명 아님"
🎼 Orchestrator → ⚖️ Arbiter
  "Decoder와 Verifier 의견 충돌. 판정 필요."
⚖️ Arbiter:
  "Verifier가 맞음. 플랫폼명 단독 언급은 is_relevant=false"
```

### 대화 컨텍스트 공유

모든 전문가는 공통 컨텍스트를 공유합니다:

```python
class ConversationContext:
    post_data: Dict           # 원본 게시글
    comments: List[str]       # 댓글 목록 (최대 15개)
    search_results: List      # 검색 결과 (누적)
    messages: List            # 전문가 간 메시지 기록
    expert_outputs: Dict      # 각 전문가의 분석 결과
    iteration: int            # 현재 반복 횟수
    snippet_hints: Dict       # snippet_analyzer 힌트
    verified_character_work_links: List  # 검증된 캐릭터-작품 연결
```

---

## 🔬 파이프라인 단계별 상세

Orchestrator가 관리하는 전체 파이프라인 흐름:

### Phase 1: 초기 분석
| 순서 | 전문가 | 역할 |
|------|--------|------|
| 1-1 | **Gatekeeper** | 게시글 분류, 엔티티 추출, 노이즈 필터링 |
| 1-2 | **DiscourseAnalyzer** | 도메인 식별, 연상 vs 토론 판별 |

### Phase 2: 검색 & 해독
| 순서 | 전문가 | 역할 |
|------|--------|------|
| 2-1 | **snippet_analyzer** | 본문/댓글에서 제목·약어·작가·캐릭터 힌트 정밀 추출 |
| 2-2 | **Decoder** (1~3차) | 슬랭 해독, 검색 결과 매칭, 후보 생성 |
| 2-3 | **SearchXNG** | Decoder/Verifier 요청에 따른 웹 검색 |

> **3차 Decoder 최적화**: 2차 결과가 이미 medium/high 이상이면 3차 실행 생략

### Phase 3: 검증 & 비평
| 순서 | 전문가 | 역할 |
|------|--------|------|
| 3-1 | **Verifier** | 교차 검증, URL/앵커 증거 확인, 거짓 긍정 방지 |
| 3-2 | **Critic** | 담론 메타데이터 추출, 감성 분석, NSFW 탐지 |

### Phase 3.5: 증거 종합 ⭐ NEW
| 순서 | 전문가 | 역할 |
|------|--------|------|
| 3.5 | **Synthesizer** | 축적된 증거를 바탕으로 원본 전문 재해석, 숨은 참조 발견 |

### Phase 4: 최종 판정
| 순서 | 전문가 | 역할 |
|------|--------|------|
| 4-1 | **Arbiter** | 모든 전문가 의견 종합, 갈등 해소, 최종 결론 |
| 4-2 | **후처리** | 증거 버킷 검증, 앵커 하드 게이트, 일관성 교정 |

---

## 🔧 후처리 시스템

Arbiter 판정 이후 `agentic_pipeline.py`에서 수행되는 자동 교정 로직입니다.

### Discussion Type 분류 체계 (16종)

#### 작품 관련 (is_relevant=True 가능) — 7종
| 타입 | 설명 |
|------|------|
| `general` | 일반 작품 토론 |
| `review` | 작품 리뷰/평가 |
| `spoiler` | 스포일러 포함 토론 |
| `anticipation` | 연재/출간 기대 |
| `meme` | 작품 관련 밈/드립 |
| `character_talk` | 등장인물 토론 |
| `general_discussion` | 범용 토론 |

#### 항상 비관련 (is_relevant=False 강제) — 9종
| 타입 | 설명 |
|------|------|
| `noise` | 무관한 노이즈 |
| `meta` | 커뮤니티 메타 토론 |
| `author_talk` | 작가 품평/비교 |
| `recommendation` | 추천 요청 |
| `trope_discussion` | 장르/클리셰 토론 |
| `community_banter` | 커뮤니티 잡담 |
| `genre_opinion` | 장르 의견 |
| `image_post` | 이미지 게시글 |
| `off_topic` | 주제 벗어남 |

### 증거 버킷 검증 (Evidence Bucket)

```python
# suspected_titles에서 medium 이상만 필터
strong_suspected_titles = [t for t in suspected if conf_rank >= 2]

# Verifier 앵커 확인
has_work_anchor = anchor in {
    "title_mention", "author_mention",
    "character_title_link", "character_mention", "plot_mention"
}
```

### 앵커 하드 게이트

**조건**: `is_relevant=True` + `official_title` 존재 시 적용

```
차단 트리거:
  1. 본문에 강한 앵커가 없음 (_no_body_evidence)
  2. 제목-본문 불일치 연상글 (_association_block)

Rescue 면제 조건 (하나라도 충족하면 차단하지 않음):
  1. strong_suspected_title + has_work_anchor
  2. Decoder가 title_mention/character_title_link 앵커 + high/max confidence
  3. verified_character_work_links 존재

차단 시 → is_relevant=False, confidence="None", discussion_type="noise"
```

### 일관성 교정 (Consistency Correction)

| 상황 | 교정 내용 |
|------|-----------|
| `always_irrelevant` 타입 + `is_relevant=True` + 제목 있음 | **Rescue**: discussion_type → `"general"` |
| `author_talk` + `is_author_criticism` + 2개 이상 작품 | **Rescue 차단**: FP 방지 |
| `is_relevant=True` + `discussion_type="noise"` | `"noise"` → `"general"` 교정 |
| `is_relevant=False` + `work_relevant_types` | discussion_type → `"noise"` 교정 |

---

## ⏱️ 타임어택 시스템

### 시간 상태 3단계

| 단계 | 남은 Step | 전문가 행동 | Orchestrator 행동 |
|------|-----------|-------------|-------------------|
| **NORMAL** | 충분 | 자유로운 탐색, 추가 검색 허용 | 메시지 자유롭게 라우팅 |
| **HIGH** | ≤ 4 | 의견 정리, 불확실성 감소 집중 | 우선순위 높은 전문가만 호출 |
| **CRITICAL** | ≤ 2 | 즉시 최선의 답변 제공 | Arbiter 강제 소환, 판정 강제 |

### 타임어택 동작 예시

```
=== Iteration 1/10 (NORMAL) ===
🎭 Gatekeeper: "작품 토론 같은데 확실하지 않아요. 검색해볼게요."

=== Iteration 2-4/10 (NORMAL) ===
🔤 Decoder 1~3차: 슬랭 해독 + 검색 결과 매칭

=== Iteration 5-6/10 (NORMAL) ===
🔍 Verifier: 증거 검증 + 📚 Critic: 담론 분석
🔬 Synthesizer: 증거 기반 재해석

⚠️ === Iteration 7-8/10 (HIGH) === ⚠️
🎼 Orchestrator: "분석 시간이 얼마 남지 않았습니다!"

🚨 === Iteration 9-10/10 (CRITICAL) === 🚨
⚖️ Arbiter: "강제 판정 모드. 현재 증거 기반 최종 결론 도출."
```

### 조기 종료 조건

시간이 남아도 결론이 명확하면 조기 종료:

```python
if gatekeeper.noise_score > 0.95:
    # 명백한 노이즈 → 즉시 Arbiter
    return arbiter.reject(reason="노이즈")

if verifier.confidence == "Max" and verifier.has_url_evidence:
    # URL 증거 → 즉시 Arbiter
    return arbiter.confirm(title_from_url)
```

### max_iterations 설정 가이드

```python
pipeline = AgenticPipeline(
    max_iterations=3,   # 빠른 처리 (정확도 약간 하락)
    max_iterations=5,   # 가벼운 분석
    max_iterations=10,  # 정밀 분석 (현재 기본값) ⭐
)
```

---

## 🚀 설치 및 실행

### 설치

```bash
pip install -e .
```

### 빠른 시작

```bash
# 기본 실행 (단일 워커)
python expert_main.py

# 입력 파일 지정
python expert_main.py tests/inputs/sample.jsonl

# 병렬 4워커
python expert_main.py tests/inputs/sample.jsonl --parallel 4

# 대시보드 비활성화
python expert_main.py --no-dashboard
```

### CLI 인자

| 인자 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `input` | positional | `tests/inputs/test01.jsonl` | 입력 JSONL 파일 경로 |
| `--parallel`, `-p` | int | `1` | 병렬 처리 워커 수 |
| `--no-dashboard` | flag | — | 대시보드 비활성화 |

### LLM 모드

#### Remote (기본 — 원격 서버)
```python
LLM_MODE = "remote"
# LLM_ENDPOINT = http://a100:10000/
# LLM_MODEL = unsloth/GLM-4.7-Flash-GGUF:IQ3_XXS
```

#### Local (로컬 GGUF)
```python
LLM_MODE = "local"
# LLM_MODEL_PATH = GLM-4.7-Flash-UD-IQ3_XXS.gguf
# LLM_N_GPU_LAYERS = 60
```

---

## 📁 프로젝트 구조

### 디렉토리 구조

```
llm_novel_dc_coommunity_parser/
├── src/
│   └── llm_batch/
│       ├── experts/               # 전문가 시스템 (~13,178줄)
│       │   ├── orchestrator.py    # 🎼 오케스트레이터 (~3,744줄)
│       │   ├── decoder.py         # 🔤 디코더 (~4,060줄)
│       │   ├── arbiter.py         # ⚖️ 중재자 (~2,859줄)
│       │   ├── verifier.py        # 🔍 검증자 (~986줄)
│       │   ├── synthesizer.py     # 🔬 재해석기 (~460줄) ⭐ NEW
│       │   ├── gatekeeper.py      # 🎭 게이트키퍼 (~456줄)
│       │   ├── discourse.py       # 📖 담론 분석가 (~367줄)
│       │   ├── critic.py          # 📚 비평가 (~246줄)
│       │   ├── prompts.py         # 전문가 프롬프트
│       │   └── utils.py           # 유틸리티 함수
│       ├── llm/                   # LLM 클라이언트
│       │   ├── client.py          # LLM 백엔드 인터페이스
│       │   └── prompt.py          # 프롬프트 템플릿
│       ├── search/                # 검색 시스템
│       │   └── client.py          # MCP/SearchXNG 클라이언트
│       ├── mcp_bridge/            # MCP 브릿지 서버
│       │   └── server.py
│       ├── agentic_pipeline.py    # 전문가 파이프라인 (~1,408줄)
│       ├── pipeline.py            # 기존 Sequential 파이프라인
│       ├── models.py              # 데이터 모델 (~159줄)
│       └── rules.py               # 규칙 엔진 (~325줄)
├── tests/
│   ├── inputs/                    # 테스트 입력 데이터
│   └── test_*.py                  # 각종 테스트
├── docker/                        # Docker 설정
│   ├── mcp-bridge/Dockerfile
│   └── searchxng/settings.yml
├── expert_main.py                 # 전문가 시스템 실행 엔트리포인트 (~816줄)
├── main.py                        # 기존 파이프라인 엔트리포인트
├── expert_readme.md               # 이 문서
└── README.md                      # 기존 파이프라인 문서
```

### 주요 파일 역할

| 파일 | 역할 |
|------|------|
| `expert_main.py` | 전문가 시스템 원클릭 실행 (병렬 처리, 대시보드, 로깅 관리) |
| `agentic_pipeline.py` | 유기적 전문가 협력 파이프라인 + 후처리 로직 |
| `orchestrator.py` | 전문가 라우팅, 대화 관리, snippet_analyzer, Phase 제어 |
| `decoder.py` | 한글 슬랭 해독, 검색 매칭, resolved_mappings 필터링 |
| `arbiter.py` | 최종 판정, 갈등 해소, author_talk 업그레이드 로직 |
| `verifier.py` | 증거 교차 검증, 앵커 확인, 작가 비평 판별 |
| `synthesizer.py` | 증거 기반 원문 재해석, 숨은 참조 발견 |
| `gatekeeper.py` | 1차 필터링, 엔티티 추출, 커뮤니티 접두어 제거 |
| `discourse.py` | 도메인/의도 분석, 연상 vs 토론 구분 |
| `critic.py` | 담론 메타데이터 추출, 감성 프로파일 |
| `models.py` | 출력 스키마 (PickvelOutputItemV2), 데이터 모델 |
| `rules.py` | 장르 용어, 플랫폼 사전, 연상 패턴, 커뮤니티 접두어 |

---

## 🧩 전문가 역할 상세

### 🎼 Orchestrator (오케스트레이터)

**책임:**
- 전문가 간 메시지 라우팅 및 대화 컨텍스트 관리
- 반복 횟수 제어 (기본: 최대 10회)
- snippet_analyzer 내장 실행 (Phase 2-1)
- 3차 Decoder 회귀 방지 (2차에서 medium/high면 3차 생략)
- `irrelevant_authors` 보호 (Gatekeeper가 work_discussion + 3+ 캐릭터면 제거 차단)

**snippet_analyzer:**

Orchestrator 내부에 구현된 분석 모듈로, Decoder 호출 전에 본문/댓글을 정밀 분석하여 힌트를 추출합니다:
- 제목 힌트 (`title_hints`)
- 약어 힌트 (`abbreviation_hints`)
- 작가/캐릭터 힌트
- 장르 패턴 식별

### 🎭 Gatekeeper (게이트키퍼)

**전문 분야:**
- 커뮤니티 문화와 속어 이해
- 노이즈 게시글 필터링
- 작품명/작가명/캐릭터명 추출
- 커뮤니티 접두어 (`소신발언)`, `스포)`, `추천)` 등) 자동 제거

**출력 예시:**
```json
{
  "classification": "work_discussion",
  "confidence": 0.85,
  "detected_entities": {
    "titles": ["전독시", "ORV"],
    "authors": ["싱숑"],
    "characters": ["김독자", "유중혁"]
  },
  "noise_score": 0.1,
  "search_strategy": {
    "should_search": true,
    "queries": ["전독시 웹소설", "site:namu.wiki 전독시"]
  }
}
```

### 📖 DiscourseAnalyzer (담론 분석가)

**전문 분야:**
- 글의 본질적 의도 파악
- 도메인 식별 (20+ 도메인: `novel_literature`, `manga_comics`, `gaming`, `medical_health` 등)
- 연상(Association) vs 토론(Discussion) 구분

**연상 vs 토론 구분:**
```
# 연상 (Association) - is_relevant: false
"길 가다가 전독시 생각남"           # 수동적 회상
"사진 보니까 ㅇㅇ 떠올랐다"         # 외부 자극

# 토론 (Discussion) - is_relevant: true  
"전독시 읽는중인데 복선 미쳤다"     # 능동적 몰입
"ㅇㅇ 봤는데 전개가 이상함"        # 분석적 평가
```

**출력 예시:**
```json
{
  "domain": "novel_literature",
  "domain_confidence": 0.95,
  "intent": "discuss_work",
  "intent_confidence": 0.90,
  "is_association": false,
  "reasoning": "게시글이 '전독시'에 대한 깊이 있는 토론"
}
```

### 🔤 Decoder (디코더)

**전문 분야:**
- 한글 초성체 복원 (ㅈㄷㅅ → 전독시)
- 축약어 해독 (화귀, 죽깨수, 약먹마)
- 검색 결과와 후보 매칭
- `resolved_mappings` 가비지 필터링 (자기 참조, 사전 항목, 비속어, 장르 용어 차단)

**다중 실행 (최대 3차):**
- 1차: 기본 검색 + 해독
- 2차: 1차 결과 반영 재검색
- 3차: (2차가 medium/high 이상이면 **생략**)

**형태소 분석 예시:**
```
입력: "즉사무림"
분석:
  - 즉[즉시] + 사[死, 사망] + 무림[武林]
  - 패턴: 즉시 죽는 + 무협
후보: "즉사 무협", "즉시 사망 무협"
검색: "즉사무림 웹소설"
매칭: "모두가 죽는 무림에서 나홀로 즉사합니다"
```

### 🔍 Verifier (검증자)

**전문 분야:**
- 증거 교차 검증
- 앵커 유형 확인 (`title_mention`, `author_mention`, `character_title_link`, `character_mention`, `plot_mention`)
- 거짓 긍정 방지
- 작가 비평(`is_author_criticism`) 판별

**검증 프로세스:**
```
1. 증거 수집 (본문, 댓글, 검색 URL/스니펫)
2. 교차 검증 (여러 소스에서 일관성 확인)
3. 신뢰도 평가
   - Max: URL 증거 또는 명시적 제목
   - High: 사전 매칭 + 검색 확인
   - Medium: 문맥 추론
   - Low: 불확실
4. 결론 → Critic/Synthesizer로 전달
```

### 📚 Critic (비평가)

**전문 분야:**
- 담론 분석 (고구마/사이다/드리프트)
- 감성 프로파일 (pacing, sentiment, drift_risk)
- NSFW/스포일러 탐지
- 독자 세그먼트 (누렁이/무틀딱)

**커뮤니티 용어 매핑:**

| 용어 | 의미 | 추출 필드 |
|------|------|-----------|
| 고구마 | 전개 지연, 답답함 | `pacing: Slow` |
| 사이다 | 즉각 해결, 시원함 | `pacing: Fast`, `sentiment: Positive` |
| 4드론 | 초반 자극 몰아치기 | `micro_tag: 4드론` |
| 드리프트 | 장르 급전환 | `drift_risk: High` |
| 후집피 | 후회/집착/피폐 | `micro_tag: 후집피` |

### 🔬 Synthesizer (증거 기반 재해석기) ⭐ NEW

**Phase 3.5에서 실행** — 모든 전문가(Decoder, Verifier, Critic) 분석 완료 후, Arbiter 판정 전에 개입합니다.

**핵심 역할:**
1. **텍스트 재해석**: 본문의 각 문장/표현을 증거 기반으로 재해석
2. **댓글 재해석**: 댓글에서 작품/캐릭터 관련 추가 실마리 발견
3. **숨은 참조 발견**: 초기 Decoder가 놓쳤지만 증거로 뒷받침되는 참조
4. **증거 정합성 평가**: 전문가들의 식별이 원문 맥락과 실제로 맞는지
5. **최종 확신도**: 모든 증거를 종합한 뒤의 판단

**입력:** Decoder 해독 결과, Verifier 검증 결과, 검색 증거, snippet 힌트, Discourse 분석, Critic 감지 제목

**출력 예시:**
```json
{
  "reinterpretation": {
    "post_intent": "개돌청년 작가의 신작에 대한 비평 글",
    "text_analysis": [
      {
        "segment": "초대남이 너무 좆같은데",
        "interpretation": "작품 속 '초대남' 캐릭터에 대한 부정적 평가",
        "evidence_source": "search"
      }
    ],
    "comment_insights": [...]
  },
  "hidden_references": [
    {
      "text": "금태양",
      "reference_type": "character",
      "matched_to": "신작의 등장인물",
      "evidence": "검색 결과에서 개돌청년 작품 캐릭터로 확인"
    }
  ],
  "evidence_alignment": {
    "decoder_match": "strong",
    "verifier_match": "partial",
    "overall_coherence": "high"
  },
  "confidence_assessment": {
    "is_about_identified_work": true,
    "confidence": "High",
    "reasoning": "캐릭터명 3개 + 작가명이 모두 검색 증거와 일치"
  },
  "synthesis_summary": "Arbiter에게 전달할 핵심 요약 3-5문장"
}
```

**Arbiter 전달:** `summarize_for_arbiter()` 메서드로 compact 요약을 생성하여 Arbiter 프롬프트에 삽입

### ⚖️ Arbiter (중재자)

**전문 분야:**
- 전문가 의견 종합 및 갈등 해소
- Synthesizer 재해석 결과 반영
- Verifier의 확정 제목을 suspected_titles에 우선 주입 (null-guard)
- `author_talk` → `work_discussion` 업그레이드 로직
  - 조건: Gatekeeper=`work_discussion` + 3+캐릭터 + Decoder가 작가 식별

**판정 프로세스:**
```
1. 의견 수집 — 모든 전문가 + Synthesizer 분석 결과 검토
2. 갈등 해소 — 불일치 지점 파악, 증거 무게 평가
3. 종합 판정 — is_relevant, official_title, confidence, discussion_type
4. 메타데이터 병합 — Critic의 분석 통합
```

**중요 규칙:**
```
⚠️ 플랫폼 이름은 작품이 아닙니다:
- 노벨피아, 문피아, 카카오페이지 → is_relevant: false
- "노피에서 뭐 볼까?" → 추천 요청, 작품 아님
```

---

## 📊 실행 흐름도

```mermaid
sequenceDiagram
    participant U as User
    participant O as Orchestrator
    participant GK as Gatekeeper
    participant DA as DiscourseAnalyzer
    participant SA as snippet_analyzer
    participant D as Decoder
    participant S as SearchXNG
    participant V as Verifier
    participant C as Critic
    participant SY as Synthesizer
    participant A as Arbiter
    participant PP as 후처리

    U->>O: 게시글 입력

    Note over O: Phase 1: 초기 분석
    O->>GK: 분류 + 엔티티 추출
    O->>DA: 도메인 + 의도 분석

    alt 명확한 노이즈
        GK-->>O: is_relevant=false
        O->>A: 즉시 판정 요청
        A-->>PP: 결과
        PP-->>U: 최종 출력
    else 불명확
        Note over O: Phase 2: 검색 & 해독
        O->>SA: 본문/댓글 정밀 분석
        SA-->>O: snippet 힌트
        O->>D: 슬랭 해독 (1~3차)
        D->>S: 검색 쿼리 실행
        S-->>D: 검색 결과

        Note over O: Phase 3: 검증 & 비평
        O->>V: 증거 검증
        O->>C: 담론 분석

        Note over O: Phase 3.5: 증거 종합
        O->>SY: 증거 기반 재해석
        SY-->>O: 재해석 + 숨은 참조

        Note over O: Phase 4: 최종 판정
        O->>A: 전문가 의견 + Synthesizer 요약
        A-->>PP: Arbiter 판정
        PP-->>U: 후처리 → 최종 출력
    end
```

---

## 📏 규칙 엔진 (rules.py)

### GENRE_ARCHETYPE_TERMS

작품명이 아닌 **장르/속성 용어** — 제목 후보에서 제외합니다:

```python
(
    "초대남", "금태양", "거근쇼타", "거근", "쇼타",
    "NTR", "네토라레", "순애", "하렘",
    "먼치킨", "사이다", "고구마", "빌런", "흔막",
    "현판", "현판물", "백합난입",
    "회귀물", "환생물", "빙의물", "전생물",
    "막내아들물", "아카데물", "무협물", "이세계물", "헌터물",
    "로판", "판무",
    "시스템", "상태창", "만담", "스텟", "스킬",
    "파이어볼", "마검사", "타임슬립", "루프물",
    "농", "ts물", "TS물", "TS"
)
```

### COMMUNITY_PREFIX_PATTERNS

게시글 제목에서 자동 제거되는 커뮤니티 태그 접두어:

```python
(
    "소신발언)", "소신발언))", "소신발언 )",
    "스포)", "스포))", "스포 )",
    "추천)", "추천))", "질문)", "질문))",
    "정보)", "정보))", "후기)", "후기))",
    "잡담)", "잡담))", "리뷰)", "리뷰))",
    "토론)", "토론))", "공지)", "공지))",
    "속보)", "속보))", "ㅈㄴ)"
)
```

### 기타 주요 상수

| 상수 | 설명 |
|------|------|
| `NOVEL_SITES` | `novelpia.com`, `munpia.com`, `page.kakao.com`, `kakao.page`, `joara.com`, `series.naver.com`, `ridibooks.com` |
| `OFFICIAL_PLATFORMS` | `NOVEL_SITES` + `namu.wiki` |
| `SLANG_DICTIONARY` | 음절 두문자 사전 (아카살, 전독시, 죽신성, 로나좋, 나혼렙 등) |
| `NOISE_TERMS` | `글카`, `채굴`, `날씨`, `음식`, `애니`, `만화` 등 |
| `PLATFORM_ABBREVIATIONS` | 노피아, 문피, 카카페, 시리즈, 리디, 조아라 등 |
| `PLATFORM_FEATURE_TERMS` | 콘, 이모티콘, 뱃지, 캐시, 쿠폰, 이벤트 등 |
| `ASSOCIATION_PATTERNS` | 연상글 감지 패턴 11종 |
| `GENRE_KEYWORDS` | `fantasy`, `martial_arts`, `romance`, `modern` 4개 장르별 키워드 사전 |
| `NON_NOVEL_MEDIA_KEYWORDS` | 히토미, 엔헨, 이헨, 마루마루, 뉴토끼 등 (비소설 미디어) |

---

## 📤 출력 형식

### PickvelOutputItemV2 스키마

```
PickvelOutputItemV2
├── post_id: int
├── identity: PickvelIdentity
│   ├── is_relevant: bool
│   ├── novel_identity: Optional[NovelIdentity]
│   │   ├── official_title: Optional[str]
│   │   ├── heretic_url: Optional[str]    # 작품 공식 페이지 URL
│   │   └── confidence: str               # None|Low|Medium|High|Max
│   ├── discussion_type: Optional[str]    # 16종 중 하나
│   ├── evidence: Optional[Evidence]
│   ├── slang_insight: Optional[SlangInsight]
│   ├── inference: Optional[Inference]
│   └── reason: Optional[str]
└── analysis: Optional[PickvelAnalysis]
    ├── detected_titles: List[DetectedTitle]
    │   ├── official_title, heretic_url, confidence, alias_or_mention
    ├── micro_tags: List[str]
    ├── sentiment_profile: Optional[SentimentProfile]
    │   ├── pacing: Fast|Normal|Slow|FastStart_SlowEnd|Unknown
    │   ├── drift_risk: Low|High|Critical|Unknown
    │   └── sentiment: Positive|Neutral|Negative|Mixed|Unknown
    ├── is_nsfw: bool
    ├── user_segment: Optional[str]
    └── notes: Optional[str]
```

### 출력 파일

| 파일 | 경로 | 설명 |
|------|------|------|
| 결과 JSON | `out/expert_result_YYYYMMDD_HHMMSS.json` | 전체 분석 결과 |
| 통합 로그 | `logs/expert_run_YYYYMMDD_HHMMSS.log` | 전문가 간 대화 로그 |
| 워커별 로그 | `logs/expert_run_YYYYMMDD_HHMMSS_W{N}.log` | 병렬 모드 워커별 로그 |

---

## ⚙️ 환경 설정

### LLM 설정

| 변수 | 현재 값 | 설명 |
|------|---------|------|
| `LLM_BACKEND` | `http` | `local` 또는 `http` |
| `LLM_ENDPOINT` | `http://a100:10000/` | HTTP 모드 서버 주소 |
| `LLM_MODEL` | `unsloth/GLM-4.7-Flash-GGUF:IQ3_XXS` | 모델 이름 |
| `LLM_N_CTX` | `65536` | 컨텍스트 윈도우 (64K) |
| `LLM_MAX_TOKENS` | `16384` | 최대 생성 토큰 |
| `LLM_FLASH_ATTN` | `1` | Flash Attention 활성화 |
| `LLM_CACHE_TYPE_K` / `V` | `q8_0` | KV 캐시 양자화 |
| `LLM_JSON_GRAMMAR` | `1` | JSON 문법 강제 |
| `LLM_STREAM` | `1` | 스트리밍 출력 활성화 |
| `LLM_ENABLE_THINKING` | `0` | 사고 모드 비활성화 |
| `LLM_N_GPU_LAYERS` | `60` | GPU 오프로드 레이어 (local 모드) |

### MCP (SearchXNG) 설정

| 변수 | 현재 값 | 설명 |
|------|---------|------|
| `MCP_ENDPOINT` | `http://localhost:3333` | SearchXNG 브릿지 주소 |
| `MCP_TOP_K_RESULTS` | `10` | 최대 검색 결과 수 |
| `MCP_DEFAULT_NUM_RESULTS` | `15` | 기본 검색 결과 수 |
| `MCP_MAX_CONTENT_CHARS` | `400` | 결과당 최대 문자 수 |

### Agentic 설정

| 변수 | 현재 값 | 설명 |
|------|---------|------|
| `LLM_MAX_SEARCH_ROUNDS` | `2` | 최대 검색 라운드 |
| `LLM_MAX_SEARCH_QUERIES` | `2` | 라운드당 최대 쿼리 수 |
| `LLM_PROGRESS_EVERY` | `5` | 진행률 출력 간격 |

### Pipeline 설정

```python
pipeline = AgenticPipeline(
    llm=llm_client,
    mcp=mcp_client,
    output_dir=Path("out"),
    max_iterations=10,  # 전문가 협력 최대 반복 횟수 (기본값)
)
```

---

## 🔀 병렬 처리 & 대시보드

### 병렬 실행

```bash
python expert_main.py tests/inputs/sample.jsonl --parallel 4
```

**ThreadPoolExecutor** 기반 병렬 처리:
- 각 워커는 독립된 게시글 묶음을 처리
- `_worker_tls` (thread-local storage)로 워커별 상태 관리
- `_print_lock` / `_results_lock`으로 스레드 안전 보장
- `_shutdown_event`로 `Ctrl+C` graceful 종료

### _Tee 로그 시스템

`stdout`/`stderr`를 **파일과 콘솔에 동시 출력**하는 커스텀 스트림:

| 모드 | 콘솔 | 통합 로그 | 워커별 로그 | 대시보드 |
|------|------|-----------|-------------|----------|
| 단일 워커 | ✅ | ✅ | — | ✅ |
| 병렬 (메인 스레드) | ✅ | ✅ | — | ✅ |
| 병렬 (워커 스레드) | ❌ (억제) | ✅ | ✅ | ✅ |

### 대시보드

`monitor.event_bus`를 통해 실시간 로그 포워딩:
- 줄바꿈 단위 버퍼링
- `monitor.add_log(line, worker_id=wid)` 전송
- `--no-dashboard` 플래그로 비활성화 가능

### Session Knowledge

- `parallel_count <= 1`일 때만 활성화
- 이전 게시글 분석에서 학습한 지식을 다음 게시글에 전달

---

## 🔧 고급 기능

### 1. 전문가 협력 모니터링

로그에서 전문가 간 대화 추적:

```
[14:32:15.123] 🎭 Gatekeeper: 작품 토론 감지 (work_discussion, 5 characters)
[14:32:16.456] 📋 snippet_analyzer: 제목 힌트 ["전독시"], 약어 힌트 ["ㅈㄷㅅ"]
[14:32:17.789] 🔤 Decoder 1차: "전독시" → "전지적 독자 시점" (95%)
[14:32:19.012] 🔍 Verifier: URL 증거 확정, anchor=title_mention
[14:32:20.345] 📚 Critic: 사이다, 생존물
[14:32:21.678] 🔬 Synthesizer: 숨은 참조 2개, coherence=high
[14:32:23.901] ⚖️ Arbiter: is_relevant=true, 전지적 독자 시점 (Max)
[14:32:24.012] 🔧 후처리: 앵커 하드 게이트 통과
```

### 2. 동적 검색 전략

전문가들이 상황에 따라 검색 전략 조정:

```python
# Gatekeeper: 일반 검색
queries = ["전독시 웹소설"]

# Decoder: 정밀 검색
queries = [
    "전독시 웹소설",
    "site:namu.wiki 전독시",
    "site:novelpia.com 전독시"
]

# Verifier: 검증 검색
queries = [
    "\"전지적 독자 시점\" 싱숑",
    "site:novelpia.com \"전지적 독자 시점\""
]
```

### 3. 커스텀 전문가 추가

새로운 전문가 추가 방법:

```python
# 1. 전문가 클래스 정의
class MyExpert:
    def __init__(self, llm_client):
        self.llm = llm_client
        self.name = "MyExpert"
        self.emoji = "🌟"
    
    def analyze(self, ctx: ConversationContext) -> Dict:
        # 분석 로직
        return {...}

# 2. ExpertType에 추가
class ExpertType(Enum):
    MY_EXPERT = "my_expert"

# 3. experts/__init__.py에서 export
```

---

## 🐛 트러블슈팅

### Q: Decoder의 resolved_mappings에 가비지가 섞여요
A: `decoder.py`의 `resolved_mappings` 필터가 자동으로 차단합니다:
- 자기 참조 (포스트 제목과 동일)
- 사전 항목 ("욕설/러시아어", "네이버 국어사전")
- 장르 용어 (`GENRE_ARCHETYPE_TERMS`)
- `/ ( )` 패턴 포함 항목
- 비속어/욕설

### Q: 전문가들이 무한 루프에 빠졌어요
A: `max_iterations=10`이 기본이므로 반드시 종료됩니다. 그래도 문제 시 값을 낮추세요.

### Q: 작가 품평 글이 작품으로 잘못 매칭돼요
A: Verifier의 `is_author_criticism` + 2개 이상 작품 식별 시 후처리에서 rescue가 차단됩니다.

### Q: 커뮤니티 접두어가 제목에 포함돼요
A: Gatekeeper가 `COMMUNITY_PREFIX_PATTERNS`에 매칭되는 접두어를 자동 제거합니다.

### Q: 명백한 작품 토론인데 noise로 분류돼요
A: Arbiter의 `author_talk` → `work_discussion` 업그레이드 로직이 Gatekeeper 증거(work_discussion + 3+ 캐릭터)를 확인하여 교정합니다.

### Q: 토큰 사용량이 너무 많아요
A: `max_iterations`를 줄이거나, `SYNTHESIZER_MAX_TOKENS` 환경변수(기본 1536)를 낮추세요.

---

## 🔗 관련 문서

- [README.md](README.md) - 기존 Sequential Pipeline 문서
- [src/llm_batch/experts/prompts.py](src/llm_batch/experts/prompts.py) - 전문가 프롬프트
- [src/llm_batch/agentic_pipeline.py](src/llm_batch/agentic_pipeline.py) - Pipeline 구현
- [src/llm_batch/rules.py](src/llm_batch/rules.py) - 규칙 엔진
- [src/llm_batch/models.py](src/llm_batch/models.py) - 데이터 모델
- [expert_main.py](expert_main.py) - 실행 엔트리포인트
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) - 아키텍처 문서
