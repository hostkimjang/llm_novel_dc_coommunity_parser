# 프롬프트 작성 지침

## 핵심 원칙: 범용성 우선, 기계적 매칭 금지

### ❌ 잘못된 접근 (기계적 매칭)

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
- 특정 작품에 종속적
- 새로운 작품/용어에 적응 불가
- 하드코딩된 규칙처럼 작동
- LLM의 이해력을 활용하지 못함

---

### ✅ 올바른 접근 (범용적 원리)

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
- 모든 작품/용어에 적용 가능
- 언어학적 이해 기반
- 새로운 약어도 분석 가능
- LLM의 추론 능력 활용

---

## 구체적 지침

### 1. 예시 제공 시

**❌ 금지:**
```
Examples:
- "즉사무림" is abbreviation for "즉사기 들고 무림에 떨어지다"
- "ect" means "전지적 독자 시점"
```

**✅ 권장:**
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

**❌ 금지:**
```
If title contains "즉사무림":
    return "즉사기 들고 무림에 떨어지다"

If domain is novel_literature AND term is "히토미":
    classify as manga, not novel
```

**✅ 권장:**
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

**❌ 금지:**
```
Medical keywords: "ect", "우울증", "치료" → domain = medical_health
Novel keywords: "작가", "연재", "스포" → domain = novel_literature
```

**✅ 권장:**
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

**❌ 금지:**
```
If contains "떠올랐다" or "생각났다":
    return is_association = True
    
If contains "읽는중" or "봤는데":
    return is_discussion = True
```

**✅ 권장:**
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

프롬프트 작성/수정 시 다음을 확인:

- [ ] 특정 작품명이 예시로 하드코딩되지 않았는가?
- [ ] 규칙이 "if X then Y" 형태의 기계적 매칭인가?
- [ ] 언어학적/형태학적 원리를 설명하는가?
- [ ] 새로운 용어/작품에도 적용 가능한가?
- [ ] LLM이 추론할 수 있는 패턴을 제시하는가?

---

## 예시: Before & After

### Decoder 프롬프트

**❌ Before:**
```
Common abbreviations:
- "즉사무림" = "즉사기 들고 무림에 떨어지다"
- "망겜" = "망했어요 이 게임"
- "회귀좌" = "회귀자 본좌"

If you find these terms, directly map to the titles.
```

**✅ After:**
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

**❌ Before:**
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

**✅ After:**
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

이 지침은 다음 모든 Expert 프롬프트에 적용:

1. **Gatekeeper** - 엔티티 추출, 노이즈 감지
2. **DiscourseAnalyzer** - 도메인/의도 분석
3. **Decoder** - 약어 해독
4. **Verifier** - 증거 검증
5. **Critic** - 메타데이터 분석
6. **Arbiter** - 최종 판정

---

## 업데이트 이력

- 2026-02-01: 초안 작성 (DiscourseAnalyzer 개선 과정에서 도출)
