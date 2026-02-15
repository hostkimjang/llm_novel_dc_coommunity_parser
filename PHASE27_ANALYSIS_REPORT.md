# Phase 27 — 388건 테스트 결과 종합 분석 및 수정 보고서

> **테스트**: `tests/inputs/test01.jsonl` (472,851줄)  
> **결과**: `out/expert_result_20260213_155118.json` (388건)  
> **로그**: `logs/expert_run_20260213_155118.log`

---

## 1. 전체 통계 요약

| 항목 | 수치 |
|---|---|
| 총 게시물 | 388 |
| **is_relevant=True** | 103 (26.5%) |
| is_relevant=False | 285 (73.5%) |
| relevant + title 존재 | 86 |
| **relevant + title=None** | **17** (16.5% 누락률) |
| confidence High | 76 |
| confidence Medium | 7 |
| confidence Low | 2 |

### discussion_type 분포 (relevant=True)
| 타입 | 건수 |
|---|---|
| review | 35 |
| character_talk | 32 |
| general | 26 |
| anticipation | 4 |
| meme | 5 |
| spoiler | 1 |

### discussion_type 분포 (relevant=False)
| 타입 | 건수 |
|---|---|
| noise | 177 |
| genre_opinion | 24 |
| community_banter | 17 |
| general (→noise) | 16 |
| trope_discussion | 16 |
| recommendation | 14 |
| off_topic | 8 |
| author_talk | 8 |
| meta | 2 |

---

## 2. 식별된 체계적 문제 패턴 (4가지)

### 패턴 A — "강제 승격 후 정합성 교정에서 뒤집힘" (FN 유발)

**증거**: Post 11718078 ("즉사무림 그정도 재미임?")

| 단계 | 결과 |
|---|---|
| Decoder | `즉사무림` → `즉사기 들고 무림에 떨어지다` (high, abbr_score=0.90) |
| Verifier | is_relevant=True, title=`즉사기 들고 무림에 떨어지다` (High) |
| Arbiter LLM | is_relevant=false, discussion_type=**genre_opinion** |
| Arbiter 코드 (강제 승격) | is_relevant=**True** ✅, title=`즉사기 들고 무림에 떨어지다` ✅ |
| **Arbiter discussion_type 교정** | **genre_opinion → 교정 안 됨** ❌ |
| agentic_pipeline 정합성 교정 | genre_opinion ∈ always_irrelevant_types → **is_relevant=False** ❌ |

**근본 원인**: 
- `arbiter.py` 강제 승격 시 discussion_type 교정 대상이 `noise, off_topic, meta, community_banter` 4종뿐
- `genre_opinion, trope_discussion, recommendation` 등은 교정 대상에서 누락
- `agentic_pipeline.py`의 `always_irrelevant_types`에는 이 타입들이 모두 포함
- **결과**: 강제 승격 → discussion_type 미교정 → 정합성 교정에서 다시 False로 뒤집힘

**영향 범위**: FN 6건 중 최소 2건 이상이 이 패턴에 해당할 것으로 추정

---

### 패턴 B — "`_title_deliberately_null` 과잉 차단" (title=None 유발)

**증거**: Post 11718089 ("개돌 신작 초대남이 너무 좆같은데")

| 단계 | 결과 |
|---|---|
| snippet_analyzer | title=`좆돼지 청소부` (category=web_novel) |
| Decoder | best_match=None (character_mention 다수 감지) |
| Verifier | title=`좆돼지 청소부` → **환각 의심** → confidence: High→**Low** |
| Arbiter LLM | is_relevant=**True**, official_novel_title=**null** |
| suspected_titles | `[{title: 좆돼지 청소부, confidence: High}]` |
| Arbiter 코드 | `arbiter_explicit_null=True` → **skip_forced_title=True** |
| Phase26-D | `_title_deliberately_null=True` |
| 최종 결과 | is_relevant=True, **title=None** ❌ |

**근본 원인**:
- Arbiter LLM이 `is_relevant=True` + `official_novel_title=null`을 반환하면
- Phase26-A null 가드가 suspected_titles 강제 적용을 **무조건** 스킵
- Phase26-D에서 `_title_deliberately_null=True` 설정으로 Verifier 폴백까지 차단
- **suspected_titles에 High confidence 후보가 있어도 무시됨**

**영향 범위**: title=None 17건 중 다수가 이 패턴 (suspected_titles에 후보가 있었으나 차단됨)

---

### 패턴 C — "DiscourseAnalyzer 연상글 판정 과적용" (FN 유발)

**증거**: Post 11718064 ("즉사무림이유백 미래가 벌써 보이네")

| 단계 | 결과 |
|---|---|
| KNOWN_ABBREVIATION | `즉사무림` 매칭 (abbreviation_match_score 높음) |
| DiscourseAnalyzer | `association_evidence` 생성 → "연상글" 의심 |
| Arbiter | DiscourseAnalyzer 의견 우선 채택, `_title_deliberately_null=True` |
| 최종 | is_relevant=**False** ❌ |

**근본 원인**: DiscourseAnalyzer가 "본문에 작품 고유 명사가 구체적이지 않다"는 이유로 연상글 판정 → Arbiter가 이를 최우선 채택하여 KNOWN_ABBREVIATION 매칭을 무시

**이 패턴의 근본적 한계**: DiscourseAnalyzer의 "연상글" 판정은 LLM 주관적 판단에 의존하므로 코드 레벨에서 완전히 해결하기 어려움. 다만, **KNOWN_ABBREVIATION 매칭이 확인된 경우에는 연상글 판정의 가중치를 낮추는** 방어 로직이 필요.

---

### 패턴 D — "snippet_analyzer 품질 문제" (노이즈 유발)

**증거**: Post 11718077 ("스포) 즉사무림 예상된 전개긴하지만")

| 문제 | 내용 |
|---|---|
| 약칭 매핑 오류 | `일망타진` → `내 이란에 쿠데타는 없다` (일반 한국어 단어를 약어로 오인) |
| title 반환 불완전 | `title=즉사무림` (약어 그대로 반환, 정식 제목 아님) |

**증거**: Post 11718089

| 문제 | 내용 |
|---|---|
| 약칭 매핑 오류 | `신작` → `[최대 90%▼] 웹쏘 세트 어드벤처 판타지 1부 라인업` |
| NTR 매핑 | `NTR` → `장르소설 마이너 갤러리/밈` (장르 용어를 작품으로 오인) |

**현황**: `_GENERIC_TERMS` 필터가 `신작`은 걸러주지만, `일망타진` 같은 일반 한국어 단어는 필터에 없어 통과

---

## 3. 적용된 코드 수정 (Phase 27)

### Fix 27-1: 강제 승격 시 discussion_type 교정 범위 확대

**파일**: `src/llm_batch/experts/arbiter.py` (2곳)

```python
# BEFORE (L1192)
if _dt in ("noise", "off_topic", "meta", "community_banter"):

# AFTER
_ALWAYS_IRRELEVANT_DT = {
    "noise", "off_topic", "meta", "community_banter",
    "genre_opinion", "trope_discussion", "recommendation",
    "image_post",
}
if _dt in _ALWAYS_IRRELEVANT_DT:
```

**효과**: 강제 승격 후 discussion_type이 `genre_opinion` 등 irrelevant 타입이어도 `general`로 교정 → agentic_pipeline 정합성 교정에서 뒤집히지 않음

### Fix 27-2: Arbiter null 가드에 suspected_titles High 후보 예외 추가

**파일**: `src/llm_batch/experts/arbiter.py`

```python
# BEFORE: arbiter_explicit_null이면 무조건 skip_forced_title = True

# AFTER: suspected_titles에 High confidence 후보가 있으면 null 가드 우회
_has_high_suspected = any(
    isinstance(st, dict)
    and st.get("title")
    and str(st.get("confidence", "")).lower() in ("high", "0.95")
    for st in (ctx.suspected_titles or [])
)
if _has_high_suspected:
    # null 가드 우회 → 강제 적용 허용
else:
    skip_forced_title = True
```

**효과**: Arbiter LLM이 `official_novel_title=null`이어도, suspected_titles에 High 후보가 존재하면 해당 제목이 적용됨

### Fix 27-3: `_title_deliberately_null` 플래그에 suspected_titles 복구 경로

**파일**: `src/llm_batch/experts/arbiter.py`

Phase26-D에서 `_title_deliberately_null=True` 설정 시, suspected_titles에 High 후보가 있으면:
- 해당 제목을 `decision["official_title"]`에 직접 주입
- `_title_deliberately_null` 플래그를 설정하지 않음

**효과**: `is_relevant=True` + `title=None` 17건 중 suspected_titles에 High 후보가 있는 케이스 해소

### Fix 27-4: agentic_pipeline 정합성 교정에 포괄적 rescue 경로

**파일**: `src/llm_batch/agentic_pipeline.py`

```python
# BEFORE: community_banter만 rescue 경로 존재

# AFTER: is_relevant=True + official_title 존재 → 모든 irrelevant 타입에서 rescue
_rescue_irrelevant_with_evidence = (
    is_relevant
    and bool(official_title)
    and discussion_type in always_irrelevant_types
)
if _rescue_irrelevant_with_evidence:
    discussion_type = "general"  # Arbiter 강제승격 결과 보존
```

**효과**: Arbiter가 강제 승격 + title 적용까지 완료했는데 discussion_type만 미교정된 경우의 최종 방어선

---

## 4. 추가 개선 제안 (미적용)

### 제안 1: KNOWN_ABBREVIATION 매칭 시 DiscourseAnalyzer "연상글" 가중치 제한

**현상**: `즉사무림`, `괴담동`, `성좌안무서움` 등 KNOWN_ABBREVIATION에 등록된 약어가 게시물 제목에 있는데, DiscourseAnalyzer가 "연상글"로 판정하면 Arbiter가 이를 우선 채택하여 FN 발생

**제안**: Arbiter에 다음 규칙 추가:  
> KNOWN_ABBREVIATION 매칭이 확인된 경우, DiscourseAnalyzer의 "association"/"genre_discussion" 판정의 가중치를 0.8 → 0.3으로 하향

### 제안 2: snippet_analyzer 일반명사 필터 확장

**현상**: `일망타진`, `NTR` 같은 일반 한국어/장르 용어가 약칭 매핑 후보로 올라옴

**제안**: `_GENERIC_TERMS` 집합에 추가:
```python
_GENERIC_TERMS = {
    ...,
    "일망타진", "사필귀정", "권선징악",  # 사자성어/관용어
    "NTR", "BL", "GL", "TS",             # 장르 용어 코드
}
```

### 제안 3: Post 11718064류 "FN 방지 라스트 리조트"

게시물 제목에 KNOWN_ABBREVIATION이 있고 + Decoder abbreviation_match_score ≥ 0.85이면, Arbiter가 is_relevant=False로 최종 판정해도 코드 레벨에서 강제 승격하는 최종 방어선 추가.

---

## 5. 예상 효과

| 패턴 | 영향 건수 | 수정 후 예상 |
|---|---|---|
| A (강제승격 뒤집힘) | ~2-3건 FN | **FN→TP 전환** |
| B (title=None 과잉) | ~8-10건 no-title | **title 복구** |
| C (연상글 과적용) | ~3-4건 FN | 미적용 (제안으로 제시) |
| D (snippet 노이즈) | 간접 영향 | 미적용 (제안으로 제시) |

**최종 수정**: arbiter.py, agentic_pipeline.py 각 1개 파일  
**구문 검증**: ✅ 완료
