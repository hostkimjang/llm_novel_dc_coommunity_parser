# Post 11718092 False Positive 분석

## ❌ 심각한 오류: 만화 사이트를 웹소설로 오인

### 📋 포스트 정보

| 항목 | 내용 |
|------|------|
| **Post ID** | 11718092 |
| **제목** | "히토미 씹꼴리는거 나왔네" |
| **본문** | "연상여친이 모성애 보여주는 **만화**인데<br>ㄹㅇ 스토리가 너무 꼴리네" |
| **댓글** | 없음 |
| **식별된 작품** | "연상 여친 연하 남친의 사정" (웹소설) |
| **Confidence** | High |
| **실제 내용** | 히토미(Hitomi.la) 만화/동인지 사이트 |

---

## 🔍 오류 분석

### 1. **"히토미" = 만화/성인 사이트**

- **Hitomi.la**: 일본 만화/동인지 공유 사이트
- **웹소설이 아님!**
- 본문에 **"만화인데"**라고 명시되어 있음

### 2. 각 전문가의 판단

#### A. Gatekeeper ⚠️
```json
{
  "post_type": "work_discussion",
  "possible_titles": ["히토미", "히토미 씹꼴리는거"],
  "key_terms": ["히토미", "연상여친", "모성애", "스토리"],
  "notes": "제목의 '히토미'는 웹소설 제목 '히토미' 혹은 '히토미 씹꼴리는거'의 약어로 추정됨"
}
```

**문제점**:
- "만화인데"를 무시함
- 히토미를 웹소설로 추정

#### B. Decoder
- "히토미" 검색 → 관련 없는 웹소설 매칭
- "연상여친" 키워드 → "연상 여친 연하 남친의 사정" 웹소설과 매칭

#### C. Verifier
- 검색 결과의 웹소설을 신뢰
- "만화인데"라는 명시적 키워드 간과

#### D. Arbiter (최악의 판단)
```
Arbiter는 Decoder의 식별 우선 원칙을 따르기로 결정함.
제목의 '히토미'는 웹소설 '히토미'의 고유한 약칭으로 등장하며,
본문의 '모성애 보여주는 만화'라는 설명은 해당 작품을 언급하고 있음.
```

**심각한 오류**:
- "만화"라는 단어를 완전히 무시
- 검색 결과만 믿고 텍스트 증거 무시

---

## 🎯 근본 원인

### 1. **"만화" vs "소설" 구분 실패**

본문에 **"만화인데"**라고 명시되어 있음에도:
- Gatekeeper: 무시
- Decoder: 무시
- Verifier: 무시
- Arbiter: "해당 작품을 언급"으로 왜곡 해석

### 2. **검색 결과 과신**

- "히토미" 검색 → 웹소설 결과 나옴
- 텍스트 증거("만화") < 검색 결과 신뢰도
- **잘못된 우선순위**

### 3. **플랫폼/사이트 vs 작품 구분 실패**

- "히토미" = 플랫폼명 (Hitomi.la)
- "노벨피아" = 플랫폼명 (Novelpia.com)
- 같은 패턴인데 처리 방식이 다름

---

## 🛠️ 해결 방안

### Priority 1: **매체 키워드 필수 체크**

#### A. Gatekeeper 규칙 추가

```python
# expert_prompts.py - GATEKEEPER_PROMPT

⚠️ CRITICAL: 매체 타입 확인 우선순위 1위

매체 타입 키워드:
- 만화, 웹툰, 코믹, 동인지 → NOT 웹소설 → is_noise=true
- 게임, RPG, VR → NOT 웹소설 → is_noise=true
- 영화, 드라마, 애니메이션 → NOT 웹소설 → is_noise=true
- 웹소설, 소설, 라노벨, 장편 → 웹소설 ✓

**본문이나 제목에 위 키워드가 명시되면 검색 결과보다 우선!**
```

#### B. 키워드 체크 로직

```python
# gatekeeper.py

def _check_media_type(self, title: str, content: str) -> tuple[bool, str]:
    """매체 타입 체크 (웹소설이 아닌 것 필터링)"""
    
    non_novel_keywords = {
        "만화": "manga",
        "웹툰": "webtoon",
        "코믹": "comic",
        "동인지": "doujinshi",
        "게임": "game",
        "영화": "movie",
        "드라마": "drama",
        "애니": "animation"
    }
    
    text = f"{title} {content}".lower()
    
    for keyword, media_type in non_novel_keywords.items():
        if keyword in text:
            return True, f"'{keyword}' 키워드 발견 → {media_type}"
    
    return False, ""

# analyze() 메서드에서 사용
is_non_novel, reason = self._check_media_type(title, body)
if is_non_novel:
    return {
        "is_noise": True,
        "noise_reason": f"웹소설이 아닌 다른 매체: {reason}"
    }
```

---

### Priority 2: **플랫폼/사이트명 필터링**

```python
# config/known_platforms.py

NON_NOVEL_PLATFORMS = {
    "히토미": "Hitomi.la - 만화/동인지 사이트",
    "익헨": "ExHentai - 성인 만화 사이트",
    "마루마루": "Marumaru - 일본 만화 사이트",
    "밤토끼": "Bamtoki - 웹툰 사이트",
    "네이버웹툰": "Naver Webtoon - 웹툰 플랫폼",
    "카카오페이지": "Kakao Page - 웹툰/웹소설 혼재 (별도 처리)"
}

# Gatekeeper에서 사용
if any(platform in title for platform in NON_NOVEL_PLATFORMS):
    return {
        "is_noise": True,
        "noise_reason": f"웹소설 플랫폼이 아닌 사이트: {NON_NOVEL_PLATFORMS[platform]}"
    }
```

---

### Priority 3: **Arbiter 최종 검증 강화**

```python
# arbiter.py - analyze()

# 본문에 명시적 매체 키워드가 있는지 체크
body_text = ' '.join([str(b) for b in post_data.get('content', [])])
title_text = post_data.get('title', '')

# "만화", "웹툰" 등이 명시되어 있으면 경고
non_novel_keywords = ["만화", "웹툰", "코믹", "게임", "영화", "드라마"]
found_keywords = [kw for kw in non_novel_keywords if kw in f"{title_text} {body_text}"]

if found_keywords and novel_identity:
    # 웹소설이 아닌 매체 키워드가 있는데 작품이 식별됨
    # → 오류 가능성 높음
    return {
        "is_relevant": False,
        "reason": f"본문에 '{', '.join(found_keywords)}' 키워드 명시 → 웹소설 아님"
    }
```

---

## 📊 영향도 분석

### 이 오류가 시사하는 것

1. **매체 타입 구분 전무**
   - "만화인데"라는 명시적 증거 무시
   - 검색 결과만 믿음

2. **텍스트 이해력 부족**
   - 본문의 핵심 키워드를 간과
   - LLM이 제대로 읽지 못함

3. **False Positive 심각도 상승**
   - 완전히 다른 매체를 웹소설로 오인
   - Confidence=High로 확신까지 함

---

## ✅ 즉시 적용 체크리스트

### Gatekeeper
- [ ] 매체 타입 키워드 체크 로직 추가
- [ ] 플랫폼/사이트명 필터링
- [ ] "만화", "웹툰" 등 발견 시 즉시 noise 처리

### Decoder/Verifier
- [ ] 검색 결과보다 텍스트 증거 우선 원칙
- [ ] 매체 타입 불일치 시 검색 결과 무시

### Arbiter
- [ ] 최종 검증 단계에서 매체 키워드 재확인
- [ ] 불일치 발견 시 is_relevant=False 강제 설정

---

## 🎯 결론

**Post 11718092는 명백한 False Positive**

- **제목**: "히토미 씹꼴리는거 나왔네"
- **본문**: "연상여친이 모성애 보여주는 **만화인데**"
- **식별**: "연상 여친 연하 남친의 사정" (웹소설) ❌

**"만화"라는 명시적 키워드가 있는데도 웹소설로 오인**

→ **매체 타입 구분 로직 즉시 추가 필요!**
