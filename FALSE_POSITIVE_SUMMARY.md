# 전체 False Positive 케이스 종합 분석

## 📊 발견된 False Positive

| Post ID | 제목 | 문제 유형 | 심각도 |
|---------|------|----------|--------|
| 11718087 | 노벨피아 성인 백합소설 추천좀 | 추천 요청 → 작품 오인 | 🔴 High |
| 11718092 | 히토미 씹꼴리는거 나왔네 | 만화 → 웹소설 오인 | 🔴 Critical |
| 11718103 | 부기피아 뚱라니 뱃지 개쳐귀엽네 | 플랫폼 기능? | 🟡 Medium |

**총 False Positive**: 최소 2건 (11718087, 11718092), 최대 3건

---

## 🎯 False Positive 유형별 분석

### 유형 1: **추천 요청 글 오인** (Post 11718087)

**패턴**:
- 제목에 "추천좀", "추천해줘" 등
- 본문 매우 짧음 (5자)
- **댓글에 작품명**
- 시스템이 댓글 작품명을 원글로 착각

**해결책**:
```python
if "추천" in title and len(body) < 50 and has_comments_with_titles:
    # 댓글 추천은 별도 처리
    return {
        "is_relevant": False,
        "recommended_titles": extract_from_comments(comments)
    }
```

---

### 유형 2: **매체 타입 오인** (Post 11718092) ⚠️ 가장 심각

**패턴**:
- 본문에 **"만화", "웹툰", "게임"** 등 명시
- 검색 결과에 웹소설 나옴
- **텍스트 증거 무시 + 검색 결과만 신뢰**

**해결책**:
```python
# 최우선 체크
non_novel_keywords = ["만화", "웹툰", "게임", "영화", "드라마"]
if any(kw in f"{title} {body}" for kw in non_novel_keywords):
    return {
        "is_noise": True,
        "noise_reason": f"웹소설이 아닌 다른 매체 명시"
    }
```

---

### 유형 3: **플랫폼 기능 vs 작품 혼동** (Post 11718103)

**패턴**:
- "뱃지", "출석", "이벤트" 등 플랫폼 기능 키워드
- 작품명과 유사한 플랫폼 별칭 (부기피아 = 부커피아?)

**해결책**:
```python
platform_features = ["뱃지", "출석", "쿠폰", "이벤트", "랭킹"]
if any(kw in title for kw in platform_features):
    # 플랫폼 기능 논의 가능성 높음
    # 작품 내용 언급 없으면 noise
```

---

## 🔥 근본 원인 분석

### 1. **검색 결과 과신** (Post 11718092)

```
텍스트 증거: "만화인데"
검색 결과: 웹소설 나옴
판단: 검색 결과 믿음 ❌
```

**잘못된 우선순위**:
- 검색 결과 > 명시적 텍스트 증거
- LLM이 본문을 제대로 읽지 않음

### 2. **댓글 처리 미흡** (Post 11718087)

```
원글: "추천좀" (작품명 없음)
댓글: "강지갑꺼", "계모가키운백설공주"
판단: 댓글 작품명을 원글 작품명으로 착각 ❌
```

**구조적 문제**:
- 댓글과 원글을 동일하게 취급
- 추천 요청 vs 작품 논의 구분 실패

### 3. **매체 타입 체크 부재** (Post 11718092)

```
현재: 웹소설인지 아닌지 체크 로직 없음
결과: 만화, 게임, 영화 등도 웹소설로 오인 가능
```

---

## 🛠️ 통합 개선 방안

### Phase 1: **긴급 수정 (오늘)**

#### A. Gatekeeper - 매체 타입 필수 체크

```python
# src/llm_batch/experts/gatekeeper.py

MEDIA_TYPE_KEYWORDS = {
    "novel": ["웹소설", "소설", "라노벨", "장편"],
    "manga": ["만화", "웹툰", "코믹", "동인지"],
    "game": ["게임", "RPG", "VR게임"],
    "video": ["영화", "드라마", "애니메이션", "애니"]
}

def _detect_media_type(self, title: str, body: str) -> str:
    """매체 타입 감지"""
    text = f"{title} {body}".lower()
    
    for media_type, keywords in MEDIA_TYPE_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text:
                return media_type
    
    return "unknown"

def analyze(self, post, comments, rules_config):
    # 매체 타입 체크 (최우선)
    media_type = self._detect_media_type(post.get("title"), post_body)
    
    if media_type in ["manga", "game", "video"]:
        return {
            "is_noise": True,
            "noise_reason": f"웹소설이 아닌 다른 매체: {media_type}",
            "detected_media_type": media_type
        }
```

#### B. Gatekeeper - 추천 요청 강화

```python
def _is_recommendation_request(self, title: str, body: str) -> bool:
    """추천 요청 글 감지"""
    request_keywords = ["추천좀", "추천해줘", "추천 부탁", "추천해주세요", "추천좀요"]
    text = f"{title} {body}".lower()
    return any(kw in text for kw in request_keywords)

def analyze(self, post, comments, rules_config):
    # 추천 요청 체크
    if self._is_recommendation_request(title, body):
        # possible_titles는 제목/본문에서만
        # 댓글은 recommended_by_commenter로 분리
        return {
            "post_type": "recommendation_request",
            "possible_titles": extract_from_post_only(title, body),
            "recommended_by_commenter": extract_from_comments(comments)
        }
```

---

### Phase 2: **Verifier 검증 강화 (이번 주)**

```python
# src/llm_batch/experts/verifier.py

def analyze(self, post, comments, gatekeeper_result, decoder_result, ...):
    # 1. 매체 타입 재확인
    detected_media = gatekeeper_result.get("detected_media_type")
    if detected_media and detected_media != "novel":
        return {
            "is_relevant": False,
            "reason": f"웹소설이 아님: {detected_media}"
        }
    
    # 2. 추천 요청 글 처리
    if gatekeeper_result.get("post_type") == "recommendation_request":
        # 원글에 작품명 명시 없으면 irrelevant
        if not has_explicit_title_in_post:
            return {
                "is_relevant": False,
                "reason": "추천 요청 글이며 원글에 작품명 없음"
            }
```

---

### Phase 3: **Arbiter 최종 안전장치 (이번 주)**

```python
# src/llm_batch/experts/arbiter.py

def analyze(self, ctx):
    # ... 기존 로직 ...
    
    # 🚨 최종 안전 체크
    post_data = ctx.post_data
    title = post_data.get("title", "")
    body = ' '.join([str(b) for b in post_data.get("content", [])])
    
    # 1. 매체 타입 불일치 체크
    non_novel_keywords = ["만화", "웹툰", "게임", "영화", "드라마"]
    found_non_novel = [kw for kw in non_novel_keywords if kw in f"{title} {body}"]
    
    if found_non_novel and final_decision.get("novel_identity"):
        # 웹소설이 아닌데 작품 식별됨 → 오류!
        return {
            "is_relevant": False,
            "reason": f"본문에 '{', '.join(found_non_novel)}' 키워드 → 웹소설 아님"
        }
    
    # 2. 추천 요청 재확인
    gk_result = ctx.get_expert_output(ExpertType.GATEKEEPER)
    if gk_result.get("post_type") == "recommendation_request":
        if final_decision.get("novel_identity"):
            # 추천 요청인데 작품 식별 → 의심
            final_decision["confidence"] = "Low"
            final_decision["warning"] = "추천 요청 글에서 식별됨 (댓글 혼동 가능)"
```

---

## 📋 구현 체크리스트

### 긴급 (오늘 적용)

- [ ] **Gatekeeper**: 매체 타입 키워드 체크 (`MEDIA_TYPE_KEYWORDS`)
- [ ] **Gatekeeper**: 추천 요청 패턴 감지 강화
- [ ] **Gatekeeper**: 댓글 추천 분리 (`recommended_by_commenter`)

### 단기 (이번 주)

- [ ] **Verifier**: 매체 타입 재확인 로직
- [ ] **Verifier**: 추천 요청 글 엄격 검증
- [ ] **Arbiter**: 최종 안전 체크 (매체 키워드 불일치)

### 중기 (다음 주)

- [ ] **플랫폼/사이트 DB**: `NON_NOVEL_PLATFORMS` 구축
- [ ] **테스트 케이스**: 3개 False Positive 케이스 추가
- [ ] **회귀 테스트**: 전체 30개 포스트 재테스트

---

## ✅ 예상 효과

### Before (현재)
- False Positive: 최소 2건 (6.7%)
- 매체 타입 구분 불가
- 추천 요청 글 오인

### After (개선 후)
- False Positive: 0~1건 (0~3.3%)
- 매체 타입 필터링 작동
- 추천 요청 글 정확 분류

---

## 🎯 최종 권고

**즉시 구현해야 할 최우선 순위**:

1. ✅ **매체 타입 체크** (Post 11718092 방지)
2. ✅ **추천 요청 댓글 분리** (Post 11718087 방지)
3. ⚠️ **Arbiter 최종 검증** (안전 장치)

이 세 가지만 구현해도 **False Positive 80% 이상 감소** 예상
