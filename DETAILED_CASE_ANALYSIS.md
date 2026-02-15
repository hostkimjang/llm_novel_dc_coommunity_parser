# 추가 문제 케이스 상세 분석 (Post 11718087, 11718103, 11718102)

## 🔍 핵심 발견사항

세 포스트 모두 **이미지 첨부 글**이며, **매우 짧은 본문** (3~14자)을 가지고 있습니다.

---

## 📊 케이스별 분석

### 1. ❌ **Post 11718087 - False Positive (추천 요청 → 작품 식별 오류)**

| 항목 | 내용 |
|------|------|
| **제목** | "노벨피아 성인 백합소설 추천좀" |
| **본문** | "ts잘먹음" (5자) |
| **댓글** | "강지갑꺼", "계모가키운백설공주", "아, 저질러버렸다" |
| **식별 작품** | "계모헨텔) 어째서 부정하지 않는거지 강지갑" |
| **실제 의도** | 작품 추천 요청 |

#### 문제점

1. **Gatekeeper 판단**:
   - `post_type`: "recommendation" ✅ (정확)
   - `is_asking_recommendation`: true ✅
   - `possible_titles`: ["ts잘먹음", "강지갑꺼"] ⚠️

2. **Decoder 오작동**:
   - 댓글의 "강지갑꺼"를 **작품명으로 오인**
   - "계모가키운백설공주" (댓글)와 매칭하여 "계모헨텔) 어째서 부정하지 않는거지 강지갑" 도출

3. **Verifier 실패**:
   - `is_relevant`: True (오판)
   - 추천 요청 글임에도 특정 작품으로 확정

4. **Arbiter 최종 확정**:
   - `confidence`: High
   - **추천 요청 글을 특정 작품 논의로 오인**

#### 원인

- **댓글의 작품명**을 **본문의 작품명**으로 착각
- "추천좀" 패턴이 있어도 댓글에 작품명이 있으면 relevant=True로 판단
- 짧은 본문 + 이미지 → 댓글에 과도하게 의존

---

### 2. ⚠️ **Post 11718103 - 경계선 케이스 (meme/community 혼재)**

| 항목 | 내용 |
|------|------|
| **제목** | "부기피아 뚱라니 뱃지 개쳐귀엽네" |
| **본문** | "나도줘" (3자) |
| **댓글** | "부럽다 부러워", "", "지금 쪽팔이 와있고", "" |
| **식별 작품** | "부기피아" |
| **실제 의도** | 플랫폼 기능(뱃지) 논의 or 작품 밈? |

#### 애매한 이유

1. **"부기피아"는 작품명일까 플랫폼명일까?**
   - 제목: "부**기**피아" (novelpia → 부기피아)
   - "뱃지" → 플랫폼 기능 (북마크, 출석체크 등)
   - BUT 실제로 "부기피아"라는 작품이 존재할 수도...

2. **현재 판단**:
   - `official_title`: "부기피아"
   - `discussion_type`: "meme"
   - `is_relevant`: True

3. **문제**:
   - 플랫폼 기능 논의(뱃지)인데 작품으로 분류
   - "뚱라니"가 캐릭터명인지, 뱃지 디자인 묘사인지 불명확

#### 판단

- **실제 확인 필요**: "부기피아"가 실제 작품인지 확인
- 만약 작품이 아니라면 → False Positive
- 만약 작품이 맞다면 → ✅ 정상 (캐릭터 굿즈 논의)

---

### 3. ✅ **Post 11718102 - 정상 케이스 (작품명 정확 식별)**

| 항목 | 내용 |
|------|------|
| **제목** | "노피아 가운데에서 빔 나오는 콘이 있는거보소" |
| **본문** | "하 ㅈㄴ 귀엽긴하네 ㅋㅋㅋ" (14자) |
| **식별 작품** | "노피아 가운드" |
| **실제 의도** | 작품 내용 밈 |

#### 정상 판단 근거

1. **제목에 작품명 명시**:
   - "노피아" = "노벨피아" (플랫폼) ❌
   - "노피아" = "노피아 가운드" (작품) ✅

2. **구체적인 내용 묘사**:
   - "가운데에서 빔 나오는 콘" → 작품 내 특정 장면/설정
   - "귀엽다" → 감상 표현

3. **Confidence**: Max (매우 확신)

#### 결론: 정확한 식별 ✅

---

## 🎯 공통 패턴 및 문제점

### 공통점

1. **모두 이미지 첨부 글** (본문에 이미지 URL)
2. **매우 짧은 본문** (3~14자)
3. **댓글에 중요 정보** (작품명, 평가 등)

### 문제 패턴

| 케이스 | 제목 | 본문 | 댓글 | 문제 |
|--------|------|------|------|------|
| 11718087 | "추천좀" | 짧음 (5자) | 작품명 있음 | 댓글 작품명을 본문으로 착각 |
| 11718103 | 작품/플랫폼 애매 | 짧음 (3자) | 플랫폼 기능 언급 | 플랫폼 기능 vs 작품 구분 실패? |
| 11718102 | 작품명 명시 | 짧음 (14자) | 없음 | 정상 ✅ |

---

## 🛠️ 개선 방안

### Priority 1: **추천 요청 글 + 댓글 작품명 → False Positive 방지**

#### A. Gatekeeper 강화

```python
# expert_prompts.py - GATEKEEPER_PROMPT

post_type 분류 규칙 추가:
- "추천좀", "추천해줘", "추천 부탁" → recommendation_request
- recommendation_request일 경우:
  - possible_titles는 제목/본문에서만 추출
  - 댓글의 작품명은 "recommended_by_commenter"로 별도 분류
```

#### B. Verifier 규칙 추가

```python
# verifier.py

if gatekeeper_result.get("post_type") == "recommendation_request":
    # 추천 요청 글은 원글 작성자의 의도만 보고 판단
    # 댓글의 추천은 무시
    if not has_title_in_post_or_title:
        return {
            "is_relevant": False,
            "reason": "추천 요청 글이며 원글에 작품명 없음. 댓글의 추천은 별도 처리 필요"
        }
```

#### C. 댓글 분리 처리

**새로운 접근**:
- 추천 요청 글 자체는 `is_relevant=False`
- 댓글의 작품명은 별도로 `recommended_titles` 필드에 저장
- 나중에 추천 그래프 구축 시 활용

```json
{
  "post_id": 11718087,
  "is_relevant": false,
  "post_type": "recommendation_request",
  "recommended_titles": [
    "계모가키운백설공주",
    "계모헨텔) 어째서 부정하지 않는거지 강지갑"
  ]
}
```

---

### Priority 2: **플랫폼 기능 vs 작품 구분**

#### A. Gatekeeper 키워드 추가

```python
platform_feature_keywords = [
    "뱃지", "출석", "이벤트", "쿠폰", "포인트",
    "랭킹", "순위", "추천 알고리즘"
]

if any(kw in title for kw in platform_feature_keywords):
    context_clues["is_platform_feature_discussion"] = True
```

#### B. Verifier 검증

```python
# 플랫폼 기능 논의인지 확인
if "뱃지" in title and not has_character_or_plot_discussion:
    return {
        "is_relevant": False,
        "reason": "플랫폼 기능 논의로 판단 (작품 내용 무관)"
    }
```

---

### Priority 3: **짧은 본문 + 이미지 → 엄격한 검증**

```python
# arbiter.py

if len(post_body) < 20 and has_image and novel_identity:
    # 본문이 너무 짧으면 confidence 낮추기
    if novel_identity.get("confidence") == "High":
        novel_identity["confidence"] = "Medium"
        novel_identity["warning"] = "본문이 짧아 이미지 의존도가 높음"
```

---

## 📋 즉시 적용 체크리스트

### 1. Post 11718087 False Positive 해결

- [ ] Gatekeeper: `possible_titles` vs `recommended_by_commenter` 분리
- [ ] Verifier: `recommendation_request` 엄격 검증
- [ ] Arbiter: 추천 요청 + 작품 식별 → confidence 낮추기

### 2. Post 11718103 확인

- [ ] "부기피아" 실제 작품 존재 여부 확인
- [ ] 플랫폼 기능 키워드("뱃지") 처리 규칙 추가

### 3. 짧은 본문 처리

- [ ] 본문 < 20자 → confidence 조정 로직
- [ ] 이미지 의존도 경고 플래그

---

## ✅ 결론

| Post | 판단 | 조치 |
|------|------|------|
| 11718087 | ❌ False Positive | 즉시 수정 필요 |
| 11718103 | ⚠️ 확인 필요 | 작품 존재 여부 확인 |
| 11718102 | ✅ 정상 | 유지 |

**핵심 이슈**: 추천 요청 글에서 **댓글의 작품명**을 **원글의 작품명**으로 착각하는 문제
