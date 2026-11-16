# 프롬프트 작성 지침

전문가 프롬프트를 쓰거나 고칠 때 지킬 원칙과 점검 항목이다. 그 바탕이 되는 생각은 [프롬프트 철학](PROMPT_PHILOSOPHY.md)에, 프롬프트가 있는 위치는 [아키텍처](docs/ARCHITECTURE.md)의 프롬프트와 규칙 절에 있다.

## 핵심 원칙: 범용성 우선, 기계적 매칭 금지

### 피할 접근: 기계적 매칭

```
예시:
- "즉사무림" → "즉사기 들고 무림에 떨어지다"
- "망겜" → "망했어요 이 게임"
- "히토미" → manga site

검색 패턴:
- If title contains "즉사무림", match to work X
- If author is "목마", identify as Y
```

**문제점:**
- 특정 작품에 묶인다
- 새 작품이나 용어에 적응하지 못한다
- 하드코딩한 규칙처럼 동작한다
- LLM의 이해력을 쓰지 못한다

---

### 권장하는 접근: 범용 원리

```
한글 약어 형성 원리:
- 음절 추출: 각 단어의 첫 음절 조합
  예: "A단어 B단어 C단어" → "ABC"
- 형태소 결합: 의미 단위 조합
  예: "즉사" (immediate death) + "무림" (martial world)
- 혼합형: 일부 단어 + 접미사
  예: "회귀" + "물" (regression + story type)

도메인 판별 원리:
- 의료: 한자어(치료, 증상) + 순우리말(뇌, 아프다) 혼용
- 문학: 서사 관련 어휘(전개, 복선, 작가)
- 기술: 외래어 차용(알고리즘, 버그, 배포)
```

**장점:**
- 어떤 작품·용어에도 적용할 수 있다
- 언어학적 이해에 바탕을 둔다
- 처음 보는 약어도 분석할 수 있다
- LLM의 추론 능력을 활용한다

---

## 구체적 지침

### 1. 예시 제공 시

**피할 것:**
```
Examples:
- "즉사무림" is abbreviation for "즉사기 들고 무림에 떨어지다"
- "ect" means "전지적 독자 시점"
```

**권장:**
```
Pattern Analysis:
- Two-syllable compounds often combine concept + domain
  Structure: [Action/State] + [Field/Category]
  Detection: Check if first part describes ability, second part describes setting

- Three-letter abbreviations may be acronyms or Sino-Korean terms
  Structure: Could be medical term (ECT = Electroconvulsive Therapy) or novel abbreviation
  Detection: Analyze context - medical vocabulary vs narrative vocabulary
```

### 2. 검증 로직 작성 시

**피할 것:**
```
If title contains "즉사무림":
    return "즉사기 들고 무림에 떨어지다"

If domain is novel_literature AND term is "히토미":
    classify as manga, not novel
```

**권장:**
```
Consistency Check:
- Extract abbreviated terms from title
- Analyze morphological structure (syllable-based vs morpheme-based)
- Compare title terms with body content entities
- If title term X and body discusses character Y:
  - Check if Y belongs to context of X
  - If terminology clusters mismatch, flag inconsistency

Domain Cross-Reference:
- Check terminology type: Does "히토미" appear with visual media terms (화, 권, 단행본)?
- Or narrative terms (회차, 연재, 줄거리)?
- Visual terms → manga/comics domain
- Narrative terms → novel domain
```

### 3. 도메인 분류 시

**피할 것:**
```
Medical keywords: "ect", "우울증", "치료" → domain = medical_health
Novel keywords: "작가", "연재", "스포" → domain = novel_literature
```

**권장:**
```
Terminology Cluster Analysis:
- Identify word origins:
  * Sino-Korean medical terms (治療, 症狀)
  * Native Korean bodily expressions (아프다, 찌릿찌릿)
  * → Medical domain

- Identify narrative vocabulary:
  * Process terms (전개, 복선, 반전)
  * Creator terms (작가, 작품)
  * Serialization terms (연재, 완결, 회차)
  * → Literary domain

- Identify technical vocabulary:
  * English loanwords (알고리즘, 버그)
  * Action verbs (배포, 빌드, 디버그)
  * → Technology domain
```

### 4. 연상글 vs 토론 구분 시

**피할 것:**
```
If contains "떠올랐다" or "생각났다":
    return is_association = True
    
If contains "읽는중" or "봤는데":
    return is_discussion = True
```

**권장:**
```
Verb Pattern Analysis:
- Passive recall verbs indicate association:
  * "떠올랐다" (came to mind) - involuntary memory
  * "생각났다" (remembered) - triggered recall
  * Indicates: External stimulus → memory, not active engagement

- Active engagement verbs indicate discussion:
  * "읽는중" (reading now) - present progressive
  * "봤는데" (watched and...) - action + conjunction
  * Indicates: Direct interaction + intention to discuss

Context Depth Analysis:
- Association: Brief mention + image + no analysis
- Discussion: Character names + plot details + reactions
```

---

## 프롬프트 리뷰 체크리스트

프롬프트를 쓰거나 고칠 때 다음을 확인한다.

- [ ] 특정 작품명이 예시로 하드코딩되지 않았는가?
- [ ] 규칙이 "if X then Y" 형태의 기계적 매칭에 그치지 않는가?
- [ ] 언어학적·형태론적 원리를 설명하는가?
- [ ] 새 용어·작품에도 적용할 수 있는가?
- [ ] LLM이 추론할 수 있는 패턴을 제시하는가?

---

## 고치기 전과 후

### Decoder 프롬프트

**고치기 전:**
```
Common abbreviations:
- "즉사무림" = "즉사기 들고 무림에 떨어지다"
- "망겜" = "망했어요 이 게임"
- "회귀좌" = "회귀자 본좌"

If you find these terms, directly map to the titles.
```

**고친 후:**
```
Korean Abbreviation Patterns:

1. Syllable Extraction:
   - Take first syllable from each word
   - Pattern: "A단어 B단어 C단어" → "ABC"
   - Example structure: 3-4 syllable compound

2. Morpheme Combination:
   - Combine meaningful semantic units
   - Pattern: [Concept] + [Category]
   - Common suffixes: 물 (story), 좌 (master), 갤 (gallery)

3. Mixed Form:
   - Partial word + full word
   - Pattern: Abbreviated action + full category
   - Sino-Korean prefix + native Korean term

Analysis Method:
- Break down into morphological components
- Identify semantic roles of each part
- Search for full forms matching the structure
```

### Discourse Analyzer 프롬프트

**고치기 전:**
```
Medical domain indicators:
- "ect" (Electroconvulsive Therapy)
- "우울증" (depression)
- "치료" (treatment)

Novel domain indicators:
- "작가" (author)
- "전개" (plot development)
- "스포" (spoiler)
```

**고친 후:**
```
Domain Detection via Terminology Analysis:

Medical Domain Patterns:
- Sino-Korean medical terminology (治療, 症狀, 患者)
- Native Korean bodily expressions (아프다, 찌릿찌릿, 뇌)
- Treatment-related vocabulary (약, 병원, 환자)
- Symptom descriptions (우울, 불안, 기억력)

Literary Domain Patterns:
- Narrative structure vocabulary (전개, 복선, 반전, 결말)
- Creator/work relationship (작가, 작품, 연재)
- Serialization terminology (회차, 완결, 휴재)
- Reader response vocabulary (스포, 떡밥, 복선)

Detection Method:
- Identify word origins and semantic fields
- Check vocabulary clustering
- Analyze discussion depth and terminology type
```

---

## 적용 범위

이 지침은 다음 전문가의 프롬프트에 모두 적용한다. 전문가 프롬프트는 `src/llm_batch/prompts/expert_prompts.py`에 있고, Arbiter와 Synthesizer의 system 프롬프트는 각각 `src/llm_batch/experts/arbiter.py`, `src/llm_batch/experts/synthesizer.py`에 있다.

1. **Gatekeeper** - 노이즈 판별, 엔티티 추출, 첫 검색 요청
2. **DiscourseAnalyzer** - 담론 영역·의도, 인용·비유·질문 역할 분석
3. **Decoder** - 약어·초성·별칭을 작품 후보로 풀이
4. **Verifier** - 원문과 후보의 관계, 공식 제목·URL과 출처 검증
5. **Critic** - 다른 전문가 분석의 메타 검토. 기본 경로에서는 Arbiter가 이 역할을 맡는다.
6. **Synthesizer** - 흩어진 근거·댓글·참조 종합
7. **Arbiter** - 전문가 판단을 종합해 최종 분석안 작성

---

## 업데이트 이력

- 2026-02-01: 초안 작성 (DiscourseAnalyzer 개선 과정에서 도출)
- 2026-11-16: 적용 범위를 현재 전문가 7개 구성에 맞추고 문장을 다듬음
