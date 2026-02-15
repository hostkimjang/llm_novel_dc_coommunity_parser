# 테스트 결과 상세 분석 및 개선 방안

## 📊 전체 통계 요약

- **총 포스트**: 30개
- **Relevant**: 15개 (50.0%) ✅
- **Identified (제목 확인)**: 14개 (46.7%) ✅
- **오류**: 1건 (3.3%)

### Confidence 분포
- **High**: 9건 (64.3%)
- **Max**: 5건 (35.7%)
- **Low/Medium**: 0건

---

## 🔍 주요 문제점 및 원인 분석

### 1. ❌ **Pydantic Validation 오류 (1건)**

**Post 11718094**: "집착보다 더 좋은 것은 의존"

```
Error: 1 validation error for PickvelAnalysis
is_nsfw
  Input should be a valid boolean [type=bool_type, input_value=None, input_type=NoneType]
```

**원인**: Critic이 `is_nsfw` 필드를 `None`으로 반환했으나 Pydantic 모델은 `bool`만 허용

**해결 방안**:
1. Critic 프롬프트에 `is_nsfw` 필수 반환 명시
2. Pydantic 모델에 `Optional[bool]` 또는 기본값 `False` 설정
3. Validation 전 None → False 변환 로직 추가

---

### 2. ⚠️ **Relevant이지만 title 없는 케이스 (1건)**

**Post 11718089**: "개돌 신작 초대남이 너무 좆같은데"

**현재 판단**:
- `is_relevant`: True
- `discussion_type`: character_talk
- `novel_identity`: **None** (작품명 식별 실패)

**원인 분석**:
- Decoder가 "개돌"을 "개미돌" 장르로 해석했으나 특정 작품명으로 식별 못함
- "신작"이라는 키워드는 있으나 구체적인 작품명 부재
- "좆돼지 청소부"는 캐릭터/설정으로 추정되나 검색 결과 부족

**해결 방안**:
1. **Gatekeeper 강화**: "장르 일반론" vs "특정 작품 논의" 구분 로직 강화
2. **Verifier 규칙 추가**: 작품명 없이 캐릭터만 언급된 경우 `is_relevant=False` 고려
3. **현 상태 유지**: 이는 실제로 특정 작품 논의일 수 있으나, 정보 부족으로 식별 불가한 정상 케이스

**권장**: 현 상태 유지 (정보 부족 케이스, 오류 아님)

---

### 3. 🖼️ **이미지 기반 판단 케이스 (8건 / 53.3%)**

다음 케이스들이 이미지를 주요 증거로 활용:

| Post ID | 식별된 작품 | 원본 제목 | 비고 |
|---------|------------|---------|------|
| 11718077 | 즉사기 들고 무림에 떨어지다 | 스포) 즉사무림 예상된 전개긴하지만 | ✅ 정확 |
| 11718076 | 즉사기 들고 무림에 떨어지다 | 즉사무림 은영이 너무 불쌍해 | ✅ 정확 |
| 11718075 | 죽었다 깨어나도 수선 | 이제는 죽깨수 올 때 됐다 | ✅ 정확 |
| 11718087 | 계모헨텔) 어째서 부정하지 않는거지 강지갑 | 노벨피아 성인 백합소설 추천좀 | ⚠️ **False Positive 의심** |
| 11718103 | 부기피아 | 부기피아 뚱라니 뱃지 개쳐귀엽네 | ✅ 정확 |
| 11718102 | 노피아 가운드 | 노피아 가운데에서 빔 나오는 콘이 있는거보소 | ✅ 정확 |
| 11718099 | 빌어먹을 환생 | 빌환 표지변경됨 | ✅ 정확 |
| 11718095 | Harry Potter: Ero World | 해리포터 패러디 읽는데 조앤롤링 존나 돌리네ㅋㅋ | ✅ 정확 |

**문제점**:
- **Post 11718087**이 의심스러움:
  - 원본 제목: "노벨피아 성인 백합소설 추천좀"
  - 식별된 작품: "계모헨텔) 어째서 부정하지 않는거지 강지갑"
  - 본문: "ts하냐?"
  - **추천 요청 글인데 특정 작품으로 식별됨** → False Positive!

**해결 방안**:
1. **Gatekeeper 규칙 강화**: "추천좀", "추천해줘" 패턴 → `post_type: recommendation_request`
2. **Verifier 검증 강화**: 
   - 제목에 "추천"이 있고 본문이 짧으면 의심
   - 이미지만으로 판단하지 말고 텍스트 컨텍스트 필수 확인
3. **Arbiter 최종 검증**: 
   - `post_type=recommendation_request` + `novel_identity != None` → confidence 낮추기
   - 본문이 1~2줄이고 질문형이면 추천 요청으로 재분류

---

### 4. 📝 **Discussion Type 분포 분석**

| Type | 건수 | 비율 | 평가 |
|------|------|------|------|
| review | 6 | 40.0% | ✅ 적절 |
| character_talk | 3 | 20.0% | ✅ 적절 |
| anticipation | 2 | 13.3% | ✅ 적절 |
| meme | 2 | 13.3% | ✅ 적절 |
| recommendation | 1 | 6.7% | ⚠️ 확인 필요 (False Positive?) |
| general | 1 | 6.7% | ✅ 적절 |

**문제**: `recommendation` 1건이 Post 11718087일 가능성 높음 → False Positive

---

## 🎯 개선 우선순위

### Priority 1: **False Positive 방지 (Post 11718087 유형)**

**개선 대상**: Gatekeeper, Verifier, Arbiter

#### A. Gatekeeper 개선

```python
# expert_prompts.py - GATEKEEPER_PROMPT 추가

post_type 분류 규칙:
- "추천좀", "추천해줘", "추천해주세요", "추천 부탁" → recommendation_request
- recommendation_request는 본문이 구체적인 작품명 언급 없이 질문만 있으면 noise로 간주
```

#### B. Verifier 개선

```python
# verifier.py - analyze() 메서드

if gatekeeper_result.get("post_type") == "recommendation_request":
    # 추천 요청 글은 더 엄격하게 검증
    if len(post_content) < 50:  # 본문이 너무 짧으면
        # 이미지만으로 판단하지 않음
        if not explicit_title_mention:
            return {
                "is_relevant": False,
                "reason": "추천 요청 글이며 명확한 작품명 언급 없음"
            }
```

#### C. Arbiter 개선

```python
# arbiter.py - analyze() 메서드

# 추천 요청 글인데 작품명이 식별된 경우 재검증
if gatekeeper_result.get("post_type") == "recommendation_request" and novel_identity:
    # 본문 길이 체크
    if len(post_content) < 50:
        # confidence를 Low로 낮추고 추가 플래그
        novel_identity["confidence"] = "Low"
        novel_identity["needs_manual_review"] = True
```

---

### Priority 2: **Pydantic Validation 오류 해결**

**개선 대상**: Critic 프롬프트 + Pydantic 모델

#### A. Critic 프롬프트 강화

```python
# expert_prompts.py - CRITIC_PROMPT

⚠️ CRITICAL: is_nsfw 필드는 **반드시** true 또는 false로 응답해야 합니다. null 불가!

- 성인/NSFW 컨텐츠가 명확하면: "is_nsfw": true
- 불분명하거나 없으면: "is_nsfw": false
```

#### B. Pydantic 모델 기본값 설정

```python
# models.py - PickvelAnalysis

class PickvelAnalysis(BaseModel):
    is_nsfw: bool = False  # 기본값 False 추가
```

#### C. 안전 변환 로직 추가

```python
# critic.py - analyze() 메서드

result = self._call_llm(user_prompt)
# is_nsfw가 None이면 False로 변환
if result.get("analysis"):
    if result["analysis"].get("is_nsfw") is None:
        result["analysis"]["is_nsfw"] = False
```

---

### Priority 3: **"Relevant이지만 title 없음" 케이스 처리**

**현재 상태**: Post 11718089 (개돌 신작)

**권장 조치**:
1. **단기**: 현 상태 유지 (정보 부족 케이스로 정상 처리)
2. **중기**: 검색 엔진 개선 (더 다양한 쿼리 생성)
3. **장기**: Community Knowledge Base 구축 (갤러리 내 은어/신조어 DB)

---

## 📋 구현 체크리스트

### Immediate (오늘 적용)

- [ ] **Critic is_nsfw 기본값 설정** (`models.py` 또는 `critic.py`)
- [ ] **Gatekeeper recommendation_request 패턴 추가**
- [ ] **Verifier 추천 요청 글 검증 강화**

### Short-term (이번 주)

- [ ] **Arbiter False Positive 재검증 로직**
- [ ] **Critic 프롬프트 is_nsfw 명확화**
- [ ] **테스트 케이스 추가** (Post 11718087 유형)

### Medium-term (다음 주)

- [ ] **검색 쿼리 생성 로직 개선** (Decoder)
- [ ] **은어/신조어 DB 구축 시작**

---

## ✅ 현재 시스템 강점

1. **높은 Confidence**: Low/Medium 케이스 없음 (모두 High/Max)
2. **적절한 Relevant 비율**: 50% (노이즈 필터링 잘 작동)
3. **다양한 Discussion Type 분류**: 6가지 유형 정확히 분류
4. **이미지 기반 판단 효과적**: 대부분의 이미지 케이스 정확 식별

---

## 🎯 최종 권장 사항

### 즉시 수정 필요
1. ✅ Pydantic validation 오류 (is_nsfw)
2. ✅ False Positive 방지 (추천 요청 글)

### 모니터링 필요
1. 이미지 기반 판단 케이스 (정확도 추적)
2. "Relevant but no title" 케이스 (패턴 분석)

### 현 상태 유지
1. Confidence 분포 (High/Max만 있는 것은 양호)
2. Discussion type 분류
3. 전반적인 Relevant/Noise 비율

---

**다음 테스트**: 위 개선사항 적용 후 동일 30개 포스트로 재테스트하여 개선 효과 측정
