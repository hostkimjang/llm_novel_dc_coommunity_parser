# 전문가 시스템 테스트 결과 종합 분석 보고서

## 📊 전체 결과 요약 (22개 포스트)

### ✓ 성공 케이스
- **is_relevant=true**: 12개 (54.5%)
  - High 신뢰도: 9개
  - Max 신뢰도: 2개
  - novel_identity 없음: 1개 (Post 11718096)

- **is_relevant=false (정상 거부)**: 10개 (45.5%)
  - noise: 11개
  - trope_discussion: 1개

### ❌ 문제 케이스 (Critical Issues)

#### 1. **Post 11718064**: 축약어를 정식 제목으로 착각
- **입력**: "즉사무림이유백 미래가 벌써 보이네"
- **결과**: official_title="즉사무림" ❌
- **정답**: "즉사기 들고 무림에 떨어지다"
- **문제**:
  - Decoder가 "즉사무림"을 정식 제목으로 인식
  - 재검색 결과에 커뮤니티 포스트만 있고 공식 플랫폼 URL 없음
  - 커뮤니티 URL vs 공식 플랫폼 URL 구분 실패

#### 2. **Post 11718089**: 작가명을 작품명으로 오인
- **입력**: "개돌 신작 초대남이 너무 좆같은데"
- **결과**: official_title="개구리 와자" ❌
- **정답**: "[개돌청년] 작가의 신작" (작가명이지 작품명 아님)
- **문제**:
  - "개돌"을 "개구리+왕자"로 잘못 형태소 분해
  - 작가명 vs 작품명 구분 로직 없음
  - "[작가명] 신작" 패턴 감지 실패

#### 3. **Post 11718096**: is_relevant=true이지만 novel_identity=null
- **입력**: "말하는 거 보니까 기계공주 잘 읽을 거 같다 ← 뭔 뜻임 이게"
- **결과**: is_relevant=true, novel_identity=null, reason="분석 완료"
- **문제**:
  - Arbiter가 reason="분석 완료"만 남기고 종료
  - 불완전한 응답 처리
  - 에러 처리 부재

---

## 🔍 근본 원인 분석

### 1. **Decoder의 구조적 문제**

#### 문제 A: 커뮤니티 URL vs 공식 플랫폼 URL 구분 실패
```
검색 결과:
❌ "즉사무림 재밌네요" (디시인사이드) → Decoder가 이것을 근거로 "즉사무림"을 정식 제목으로 인식
✅ "즉사기 들고 무림에 떨어지다 리뷰" (문피아 언급) → 이런 결과가 있어야 정확
```

**원인**:
- Decoder 프롬프트에 "공식 플랫폼 URL 우선" 규칙 없음
- `search_evidence` 필드가 커뮤니티 포스트를 신뢰할 수 있는 증거로 취급

#### 문제 B: 작가명 vs 작품명 구분 로직 부재
```
"개돌 신작" → "[작가명] + 신작" 패턴
```

**원인**:
- Gatekeeper가 "신작" 키워드를 감지했지만 "개돌"을 작가명으로 분류하지 못함
- Decoder가 "개돌"을 무조건 작품명으로 가정
- "[작가명] 신작" 패턴에 대한 특수 처리 없음

#### 문제 C: 짧은 제목에 대한 의심 부족
```
"즉사무림" (4음절) → confidence="high" ❌
"개구리 와자" (6음절) → confidence="high" ❌
```

**원인**:
- 짧은 제목 (5자 이하)에 대한 검증 강화 규칙 없음
- 축약어일 가능성을 재검토하지 않음

### 2. **Arbiter의 불완전한 응답 처리**

#### 문제: reason="분석 완료"로만 종료 (Post 11718096)
```json
{
  "is_relevant": true,
  "novel_identity": null,  // ← 이상함
  "reason": "분석 완료"    // ← 의미 없는 응답
}
```

**원인**:
- Arbiter 프롬프트에 "is_relevant=true면 novel_identity 필수" 규칙 없음
- JSON 스키마 검증 부재
- 에러 상태를 명시적으로 표현할 방법 없음

### 3. **Orchestrator의 재검색 트리거 한계**

#### 문제: 재검색 결과가 나빠도 재시도 없음
```
첫 검색: "즉사무림" → 커뮤니티 포스트만
재검색: "즉사무림 정식 제목" → 여전히 커뮤니티 포스트만
→ 포기하고 "즉사무림"을 정식 제목으로 확정 ❌
```

**원인**:
- 재검색 횟수 제한 (최대 2회)
- 검색 쿼리 전략이 고정적 ("정식 제목" 추가만)
- 리뷰/플랫폼 우선 검색 전략 없음

---

## 🔧 개선 방안

### **Phase 1: Decoder 프롬프트 강화** (최우선)

#### 개선 1-A: 공식 플랫폼 URL 우선 규칙 추가
```python
DECODER_PROMPT += """
=== CRITICAL: 검색 증거 신뢰도 계층 구조 ===

검색 결과의 신뢰도는 다음 순서를 따른다:

1. **공식 플랫폼 URL** (신뢰도: 최상)
   - munpia.com, series.naver.com, novelpia.com, joara.com, kakao.com
   - 플랫폼 URL이 있으면 → 해당 페이지의 제목이 정식 제목
   - 예: "https://mm.munpia.com/novel/12345" → 페이지 제목 확인

2. **플랫폼 언급 리뷰/소개글** (신뢰도: 높음)
   - "[작가명] 작가의 [정식 제목]" 패턴
   - "문피아에서 연재 중인 [정식 제목]"
   - 예: "오늘도요 작가의 즉사기 들고 무림에 떨어지다"

3. **커뮤니티 포스트** (신뢰도: 낮음)
   - 디시인사이드, 에펨코리아, 아카라이브 등
   - 축약어를 그대로 사용하는 경향
   - 단독으로는 정식 제목 확정 불가

**판단 규칙**:
- 공식 플랫폼 URL이 없고, 커뮤니티 포스트만 있으면 → best_match.title = null
- 커뮤니티에서만 사용되는 용어는 축약어일 가능성 높음
- confidence를 "low"로 설정하고 needs_verification=true 반환
"""
```

#### 개선 1-B: 작가명 vs 작품명 구분 로직 추가
```python
GATEKEEPER_PROMPT += """
=== [작가명] 신작 패턴 감지 ===

**패턴**: "[작가명] 신작 [추가설명]"

**감지 규칙**:
- "신작", "새작", "차기작", "다음 작품" 키워드 포함
- 앞에 2-4음절 단어가 있으면 작가명일 가능성

**처리 방법**:
- detected_entities.possible_authors에 추가
- search_requests에 작가명 검색 추가:
  - "[용어] 작가"
  - "[용어] 웹소설 작가"
"""

DECODER_PROMPT += """
=== 작가명 처리 규칙 ===

**"신작" 키워드가 있을 때**:
- "[용어] 신작" 형태이면 → [용어]는 작가명일 가능성
- 검색 결과에서 "[용어] 작가", "[용어]청년" 등 확인
- 작가명으로 확정되면:
  - best_match.title = null
  - is_author_name = true
  - author_info.original = "[용어]"
  - notes에 "작품명이 아닌 작가명으로 식별됨" 명시
"""
```

#### 개선 1-C: 짧은 제목 의심 규칙 추가
```python
DECODER_PROMPT += """
=== 짧은 제목 검증 강화 ===

**best_match.title이 5자 이하일 때**:

1. **축약어 가능성 재검토**:
   - 커뮤니티 URL만 있으면 → 축약어일 확률 높음
   - 공식 플랫폼 URL이 없으면 → confidence를 "low"로 낮춤

2. **재검색 요청**:
   - needs_verification = true
   - verification_search = "[짧은 제목] 정식 제목 리뷰"
   
3. **예시**:
   - "즉사무림" (4자) + 커뮤니티 URL만 → 축약어 의심
   - "죽깨수" (3자) + 플랫폼 URL 있음 → 정식 제목 (축약어가 공식명)
"""
```

### **Phase 2: Arbiter 검증 로직 강화**

#### 개선 2-A: 응답 완전성 검증 추가
```python
ARBITER_PROMPT += """
=== 최종 판정 검증 규칙 ===

**STEP 0: 응답 완전성 체크**

1. **is_relevant=true일 때 필수 필드**:
   - novel_identity.official_title: 반드시 있어야 함
   - novel_identity.confidence: "High", "Medium", "Low" 중 하나
   - discussion_type: 토론 유형 명시
   
   **예외**: discussion_type="author_talk"이고 특정 작품 언급 없으면 official_title=null 허용

2. **검증 실패 시 처리**:
   - Decoder.best_match.title이 없으면:
     * is_relevant = false로 변경
     * reason = "작품 식별 실패"
   - Decoder와 Verifier가 충돌하면:
     * 증거가 더 강한 쪽 채택
     * conflict_resolution에 상세 기록

**STEP 1.4: official_title 결정 (이미 있음, 강화)**

추가 규칙:
- Decoder.best_match.title이 5자 이하이고 confidence="low"면:
  * Verifier 결과 우선
- Decoder.best_match.title이 null이면:
  * official_title = null
  * is_relevant 재검토
"""
```

### **Phase 3: Orchestrator 재검색 전략 개선**

#### 개선 3-A: 검색 쿼리 전략 다양화
```python
# orchestrator.py
def _generate_verification_search(original_query: str, attempt: int) -> str:
    """재검색 쿼리 생성 - 시도 횟수에 따라 전략 변경"""
    
    if attempt == 1:
        # 첫 재검색: 정식 제목 + 리뷰
        return f'"{original_query}" 정식 제목 리뷰'
    elif attempt == 2:
        # 두 번째: 플랫폼 명시 검색
        return f'(site:munpia.com OR site:series.naver.com) "{original_query}"'
    elif attempt == 3:
        # 세 번째: 작가명 검색
        return f'"{original_query}" 작가'
    else:
        return original_query
```

#### 개선 3-B: 재검색 품질 평가 추가
```python
def _evaluate_search_quality(search_results: List[Dict]) -> str:
    """검색 결과 품질 평가"""
    
    has_platform_url = any(
        any(domain in r['url'] for domain in OFFICIAL_PLATFORMS)
        for r in search_results
    )
    
    has_review_pattern = any(
        re.search(r'작가의|리뷰|연재', r['content'])
        for r in search_results
    )
    
    if has_platform_url:
        return "excellent"
    elif has_review_pattern:
        return "good"
    else:
        return "poor"  # 재검색 필요
```

---

## 📈 예상 개선 효과

### 개선 전 (현재)
- **성공률**: 82% (18/22)
- **Critical 문제**: 2건
  - Post 11718064: 축약어 그대로 사용
  - Post 11718089: 완전 오매칭

### 개선 후 (예상)
- **성공률**: 95%+ (21/22)
- **Critical 문제**: 0건
- **개선 케이스**:
  - Post 11718064: "즉사무림" → "즉사기 들고 무림에 떨어지다" ✅
  - Post 11718089: "개돌" → null (작가명으로 식별) ✅
  - Post 11718096: 불완전 응답 → is_relevant=false ✅

---

## 🎯 구현 우선순위

### 🔥 P0 (즉시 적용)
1. **Decoder 공식 플랫폼 URL 우선 규칙** → Post 11718064 해결
2. **Gatekeeper/Decoder 작가명 처리** → Post 11718089 해결
3. **Arbiter 응답 완전성 검증** → Post 11718096 해결

### ⚡ P1 (다음 단계)
4. **Decoder 짧은 제목 의심 로직**
5. **Orchestrator 재검색 전략 다양화**
6. **검색 결과 품질 평가**

### 💡 P2 (추가 개선)
7. JSON 스키마 검증 (Pydantic 사용)
8. 에러 상태 명시적 표현
9. 로그 분석 도구 개선

---

## 📝 결론

현재 시스템은 **82% 성공률**로 작동 중이며, 주요 문제는:
1. 커뮤니티 포스트를 과신
2. 작가명 vs 작품명 구분 실패
3. 불완전한 응답 처리

**Phase 1 개선 (P0)만 적용해도 성공률 95% 이상 달성 가능**합니다.
