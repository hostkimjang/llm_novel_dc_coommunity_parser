# 🔬 Expert Pipeline 종합 감사 보고서

> **감사 범위**: `expert_prompts.py`, `arbiter.py`, `decoder.py`, `verifier.py`, `gatekeeper.py`, `critic.py`, `orchestrator.py`, `agentic_pipeline.py`  
> **파이프라인 구조**: Gatekeeper → (DiscourseAnalyzer) → Decoder → Verifier → Critic → Arbiter  

---

## A. 사고력 저하 위험 분석 (Reasoning Degradation Risk)

### A-1. 플랫폼 약칭 매핑 테이블 — 위험도: 🟡 MEDIUM

**위치**: `expert_prompts.py` L1557–1570 (Decoder), `arbiter.py` L193–207 (Arbiter)

**현황**: 7개 플랫폼의 약칭→정식명→도메인 매핑이 하드코딩되어 있음.

| 약칭 | 정식명 | 도메인 |
|------|--------|--------|
| 노피아, 노블피아 | 노벨피아 | novelpia.com |
| 문피, 문피아 | 문피아 | munpia.com |
| 카카페, 카페 | 카카오페이지 | page.kakao.com |
| 시리즈 | 네이버 시리즈 | series.naver.com |
| 리디, 리디북스 | 리디 | ridi.com |
| 조아라, 조라 | 조아라 | joara.com |
| 부기피아, 부키피아 | 북팔 계열 | — |

**위험 분석**:
- ✅ **긍정적**: 플랫폼 약칭은 실제로 고정적이고 변화 빈도가 낮음. LLM이 "노피아"를 작품명으로 착각하는 FP를 방지하는 실익이 큼.
- ⚠️ **우려**: 이 테이블이 LLM의 "고정 사전"처럼 작동하여, 테이블에 **없는** 새 플랫폼 약칭(예: 탭툰, 봄툰, 포스타입의 커뮤니티 약칭)은 작품명으로 오분류될 가능성.
- ⚠️ **우려**: "카페"는 "카카오페이지"뿐 아니라 "네이버 카페"를 지칭할 수도 있어, 맥락 없이 테이블만 참조하면 오판 가능.

**사고력 저하 메커니즘**:
> LLM이 "약칭 X → 플랫폼 Y"를 기계적으로 적용하고, 본문 맥락에서 실제로 플랫폼을 논하는지 **확인을 생략**할 위험. 특히 약어가 다의적일 때(카페, 시리즈) 오분류 가능.

**권고**: 테이블 자체는 유지하되, "이 매핑은 **참고 사항**이며, 본문 맥락에서 실제로 플랫폼을 논하는지 반드시 확인하라"는 메타 지시를 추가. 다의어 주의 문구 필요.

---

### A-2. is_author_name 결정 트리 — 위험도: 🟢 LOW

**위치**: `expert_prompts.py` L1464–1510 (Decoder 프롬프트 내부)

**현황**: Step A–D의 4단계 구조화된 판정 트리.
1. Step A: 형태소 패턴으로 인명 여부 판단 (음절 구조, 한자+순우리말)
2. Step B: 검색 결과에서 "작가" 패턴 확인
3. Step C: 작가 활동 증거 확인 (연재, 완결, 신작)
4. Step D: 최종 판정

**위험 분석**:
- ✅ **긍정적**: 언어학적 원리(형태소, 조사 결합, 검색 교차검증)에 기반하며 특정 작가명을 하드코딩하지 않음.
- ✅ **긍정적**: 단계별 진행이라 LLM이 건너뛰기 어려움.
- ⚠️ **경미한 우려**: "인명 어미 패턴" 목록(-백, -영, -수, -진, -아, -현, -준)이 나열되어 있어, 이 패턴에 해당하지 않는 필명(예: "아삭이", "바나나")을 놓칠 수 있음. 단, 이는 Step B(검색 검증)로 보완됨.

**사고력 저하 메커니즘**: 낮음. 판정 트리가 원칙 기반이며, 각 단계에서 맥락 확인을 요구함.

---

### A-3. 복합 토큰 문자 분리 규칙 — 위험도: 🟡 MEDIUM

**위치**: `decoder.py` L112–240 (`_try_split_abbreviation_boundary`), `expert_prompts.py` L2020–2080 내 프롬프트

**현황**:
- Python 코드 레벨: 순수 한글, 5음절 이상 → 3/4음절 기준 분리 시도
- 프롬프트 레벨: "의미 경계 탐색", "인명 형태소 패턴 인식" 지침

**위험 분석**:
- ✅ **긍정적**: 코드 레벨의 분리는 "후보 생성"에 그치며, 최종 판단은 LLM+검색이 수행.
- ⚠️ **우려**: 3/4음절 기계적 분리가 잘못된 후보를 대량 생성하여 검색 노이즈 증가.
  - 예: "대마법사전생" → "대마법" + "사전생" (잘못된 분리) vs "대마법사" + "전생" (올바른 분리)
  - 현재 코드는 분리 지점이 고정(3, 4)이라 5음절의 경우 3/2 또는 4/1만 시도.
- ⚠️ **우려**: 한글 전용(영문·숫자 혼합 제목 미처리). `ord('가') <= ord(c) <= ord('힣')` 검증.

**사고력 저하 메커니즘**:
> 코드가 생성한 잘못된 분리 후보가 검색으로 전달되면, LLM이 검색 결과에 끌려가서 잘못된 매칭을 할 위험. 특히 분리된 2음절 단어가 흔한 단어일 때(예: "전생", "무림") 노이즈 검색 결과가 많아짐.

**권고**: 분리 지점을 고정값이 아닌 음절 의미 경계 기반으로 변경하거나, 최소한 분리된 각 부분이 "의미 있는 단어인지" 사전 검증 추가. Kiwi 형태소 분석기를 활용하면 보다 정확한 경계 탐색 가능.

---

### A-4. P0-3 환각 제목 차단 (hallucination title blocking) — 위험도: 🟠 MEDIUM-HIGH

**위치**: `arbiter.py` L960–1100

**현황**:
```
if Decoder title == None AND Verifier title == None:
    → Arbiter title 강제 null (Arbiter가 독자적으로 제목 생성한 것으로 간주)
if Arbiter title not in Decoder candidates AND not in suspected_titles:
    → Arbiter title = Decoder best candidate로 대체
```

**위험 분석**:
- ✅ **긍정적**: LLM 환각 방지에 효과적. Arbiter가 검색 증거 없이 제목을 "만들어내는" 것을 차단.
- 🔴 **심각한 우려**: Decoder와 Verifier가 **둘 다 놓친** 진짜 작품을 Arbiter가 올바르게 추론해도 차단됨.
  - 시나리오: Decoder 검색 실패(timeout), Verifier도 null, Arbiter가 LINGUISTIC_FRAMEWORK 지식으로 올바른 작품을 추론 → P0-3에 의해 null로 강제됨.
- 🔴 **심각한 우려**: `suspected_titles` 리스트에 의존하므로, 이 리스트 구축 로직(`_init_suspected_titles`)에 버그가 있으면 정상 제목도 차단됨.

**사고력 저하 메커니즘**:
> Arbiter의 독자적 추론 능력이 **완전히 무력화**됨. "최종 판사"가 사실상 "이전 전문가 의견 전달자"로 역할 축소. Arbiter에게 고급 프롬프트(LINGUISTIC_FRAMEWORK 포함)를 제공하는 비용 대비 실효가 떨어짐.

**권고**: P0-3을 "완전 차단"이 아닌 "경고+confidence 하향"으로 변경. 예: Arbiter 독자 생성 제목 → confidence를 자동으로 "Low"로 설정 + notes에 "Decoder/Verifier 미확인 제목" 표기.

---

### A-5. Verifier 형태소 매칭 BLOCKING RULES — 위험도: 🟡 MEDIUM

**위치**: `expert_prompts.py` L3700–3900 (VERIFIER_PROMPT 내 [3단계])

**현황**: 5개의 BLOCKING RULE이 정의되어 있어, 하나라도 위반 시 "즉시 거부" 지시.
1. 장르 형태소 불일치 → REJECT
2. 능력 형태소 누락 → WARNING
3. 캐릭터명 불일치 → REJECT
4. 작가명 불일치 → REJECT
5. 트로프/설정 불일치 → WARNING

**위험 분석**:
- ✅ **긍정적**: FP(False Positive) 방지에 매우 효과적. "즉사무림"과 "즉사게임"을 구분하는 핵심 규칙.
- ⚠️ **우려**: 공식 플랫폼 URL이 존재해도 형태소 불일치만으로 거부하라는 지시가 과도할 수 있음.
  - 예: 작가가 제목을 변경했거나, 커뮤니티 약칭이 정식 제목과 무관한 경우(예: "존버물" = "SS급 사냥꾼의 회귀") 형태소 매칭이 실패함.
- ⚠️ **우려**: "캐릭터 일치가 형태소 불일치를 덮어쓰지 않았는가? ← CRITICAL!" 같은 강조가 LLM의 유연한 판단을 억제.

**사고력 저하 메커니즘**:
> "즉시 거부" 지시가 LLM에게 "예외 없는 규칙"으로 인식되어, 형태소가 약간 다르더라도 맥락적으로 올바른 매칭을 거부할 위험. 특히 비표준 약칭(커뮤니티 밈 기반 별명)에서 FN 증가.

---

## B. 프롬프트 중복·모순 점검

### B-1. LINGUISTIC_FRAMEWORK 4중 복제 — 심각도: 🔴 HIGH

**위치 및 삽입 지점**:
| 전문가 | 삽입 방식 | 위치 |
|--------|-----------|------|
| Gatekeeper | `GATEKEEPER_SYSTEM` 내 `+ LINGUISTIC_FRAMEWORK +` | `expert_prompts.py` L434 |
| Decoder | `DECODER_SYSTEM` 내 `+ LINGUISTIC_FRAMEWORK +` | `expert_prompts.py` L1287 |
| Verifier | `VERIFIER_SYSTEM` 내 `+ LINGUISTIC_FRAMEWORK +` | `expert_prompts.py` L2440 |
| Arbiter | `ARBITER_SYSTEM` 내 `+ LINGUISTIC_FRAMEWORK +` | `arbiter.py` L40 |

**문제점**:
- LINGUISTIC_FRAMEWORK은 약 **490줄, ~12,000 토큰**(추정)의 공유 프레임워크.
- 4개 전문가 모두에 **전문(full text)** 삽입 → 포스트 1건당 ~48,000 토큰 소비(프레임워크만으로).
- Critic만 미삽입이나, Critic은 is_relevant=true일 때만 호출되므로 전체 영향은 적음.

**모순 위험**:
- 4곳 모두 **동일한 소스(LINGUISTIC_FRAMEWORK 변수)**를 참조하므로 현재 모순은 없음.
- 그러나 향후 특정 전문가에만 예외를 추가하려 할 때, LINGUISTIC_FRAMEWORK를 직접 수정하면 전 전문가에 영향 → 유지보수 위험.

---

### B-2. 플랫폼 약칭 매핑 2중 중복 — 심각도: 🟡 MEDIUM

**중복 위치**:
1. `expert_prompts.py` L1557–1570 (DECODER_SYSTEM 내) — 표 형식
2. `arbiter.py` L193–207 (ARBITER_SYSTEM 내) — 불릿 리스트 형식

**내용 비교**:
- Decoder 버전: 테이블에 도메인 컬럼 포함, "부기피아" 항목 있음
- Arbiter 버전: 불릿 리스트, "피아쨩 → 노벨피아 캐릭터/마스코트" 항목 추가, "부기피아" → 의미 다름

**모순 발견**: Arbiter에만 있는 "뚱라니/마스코트명" 항목이 Decoder에는 없음. Decoder가 "뚱라니"를 작품명으로 해석할 위험.

---

### B-3. is_relevant 판정 규칙 3중 중복 — 심각도: 🟡 MEDIUM

`is_relevant=false` 조건이 3곳에 독립 정의:

| 전문가 | 위치 | 조건 수 |
|--------|------|---------|
| Verifier | `expert_prompts.py` L3580–3620 | 6개 조건 |
| Arbiter 프롬프트 | `arbiter.py` L400–440 | 6개 조건 |
| Arbiter 시스템 | `arbiter.py` L160–230 | 7개 조건 |

**모순 발견**:
- Verifier: "작가 비평도 relevant (author_criticism, official_title=null 가능)" 명시
- Arbiter 시스템: is_relevant=true 조건에 "작가 비평"이 포함되나, Arbiter 프롬프트의 Step 1.6은 author_criticism 시 official_title=null만 명시하고 is_relevant 판정이 모호.
- Verifier의 "담론 영역이 현실 세계이고 작품 고유 정보가 없는 경우" 조건이 Arbiter에는 누락.

---

### B-4. 형태소 매칭 우선순위 중복 — 심각도: 🟢 LOW

**중복 위치**:
- Decoder 프롬프트: `expert_prompts.py` L1900–2000 (형태소 매칭 기본 규칙)
- Verifier 프롬프트: `expert_prompts.py` L2900–3100, L3700–3900 (BLOCKING RULES로 재정의)
- Verifier 프롬프트: `expert_prompts.py` L3100–3300 (동일 내용 반복 강조)

**분석**: Verifier의 형태소 매칭 규칙이 프롬프트 내에서 **3번 반복**됨 (STEP 0, 상식적 판단, 최종 점검 체크리스트). 이는 중복이지만 모순은 아님. LLM 토큰을 소비하면서 동일 규칙을 재강조.

---

### B-5. 작가 비평 판별 로직 2중 중복 — 심각도: 🟡 MEDIUM

**중복 위치**:
1. `expert_prompts.py` L4340–4540 (VERIFIER_PROMPT 말미, "필수 단계" 섹션)
2. `arbiter.py` L350–400 (ARBITER_PROMPT Step 1.6)

**모순 발견**:
- Verifier 버전: 5단계 상세 절차 (제목 구조, 어미, 본문, 작품 언급 방식, 종합)
- Arbiter 버전: 간략한 2줄 규칙 ("작가 비평이면 official_title=null")
- **위험**: Verifier가 정교한 분석으로 is_author_criticism=true 판정했는데, Arbiter가 간략한 규칙으로 이를 뒤집을 가능성.

---

## C. 에이전트 연계 점검 (Agent Connection Issues)

### C-1. suspected_titles 흐름 — 상태: ✅ 양호 (일부 취약점)

**데이터 흐름**:
```
Decoder._init_suspected_titles() → ctx.suspected_titles 초기화 (최대 5개)
    ↓
Verifier._update_suspected_titles() → status/confidence 업데이트
    ↓
Critic._adjust_suspected_titles() → 메타 분석, 낮은 신뢰도 정리
    ↓
Arbiter.analyze() → suspected_titles 참조, P0-3/P1-5에서 활용
```

**취약점**:
1. **타입 안전성**: Critic 코드에 `isinstance(st, dict)` 가드가 있음(L87) → 과거에 dict가 아닌 항목이 유입된 적 있음을 시사. 근본 원인 미해결.
2. **Decoder → Verifier 전달 시 정보 손실**: `_summarize_decoder()`가 `decoded_terms`를 3개로 제한 → 4번째 이후 후보가 유실됨.
3. **suspected_titles 최대 5개 제한**: 다작 작가의 복수 작품이 언급된 포스트에서 후보 누락 가능.

### C-2. author_info 흐름 — 상태: ⚠️ 부분적 문제

**데이터 흐름**:
```
Decoder: is_author_name=true, author_info={name, works} → decoded_terms 내
    ↓
Verifier: author_info 필드를 JSON 스키마에 포함 → 전달됨
    ↓
Arbiter._summarize_verifier(): author_info 필드 추출 → vf_verdict에 포함
    ↓
Arbiter P0-2: Decoder가 author로 식별 → official_title 클리어
```

**취약점**:
1. **Gatekeeper의 possible_authors가 Decoder에 직접 전달되지 않음**: Gatekeeper가 추출한 작가명 후보가 Decoder 프롬프트에 명시적으로 포함되지 않고, 검색 쿼리를 통해 간접적으로만 전달됨.
2. **author_info의 비정형 구조**: `_update_session_knowledge()`에서 `isinstance(author_info, str)`과 `isinstance(author_info, dict)` 모두 처리 → 구조 불일치 존재.

### C-3. 검색 결과 전달 — 상태: ⚠️ 잠재 병목

**데이터 흐름**:
```
Orchestrator._execute_searches() → 최대 5개 쿼리 실행
    ↓ content 100자 제한 (truncation)
ctx.search_results에 저장
    ↓
Decoder에 전달 → Decoder가 verification_search 추가 요청 가능
    ↓
Orchestrator가 재검색 → Verifier에 verification_search_json으로 전달
```

**취약점**:
1. **content 100자 제한이 너무 짧음**: `expert_prompts.py` L3000 부근에서 "검색 스니펫이 서사 문장인지" 판단하라고 지시하나, 100자로는 서사 패턴 판별 어려움.
2. **검색 결과 중복**: URL 기반 dedup만 수행. 동일 작품의 다른 URL(namu.wiki vs novelpia.com)은 중복 제거 안됨 → 5개 슬롯 낭비.
3. **Decoder→Verifier 재호출 시 토큰 이중 소비**: Decoder의 verification_search 요청 → 재검색 → Decoder 재호출 → Verifier 호출. 총 Decoder 2회 + Verifier 1회.

### C-4. Orchestrator 동적 라우팅 — 상태: ✅ 양호

**설계**: `_decide_next_action()`에서 협업 횟수 제한(총 2회, 동일 쌍 1회)으로 무한 루프 방지.

**확인된 흐름**:
- Verifier→Decoder 재호출(request_expert="decoder") 지원됨
- Verifier→Gatekeeper 재호출 지원됨
- Critic은 is_relevant=true일 때만 호출 → 불필요한 호출 방지

---

## D. 토큰 부담 분석 (Token Burden)

### D-1. 전문가별 시스템 프롬프트 토큰 추정

> 추정 기준: 한글 1음절 ≈ 2–3 토큰, 영문/코드 1단어 ≈ 1–2 토큰

| 전문가 | 시스템 프롬프트 | 유저 프롬프트 | 합계(추정) | 비고 |
|--------|:-------:|:-------:|:-------:|------|
| **Gatekeeper** | ~15,000 | ~2,000 | **~17,000** | LINGUISTIC_FRAMEWORK ~12K 포함 |
| **Decoder** | ~18,000 | ~3,000 | **~21,000** | LINGUISTIC_FRAMEWORK + 플랫폼 매핑 + 약어 규칙 |
| **Verifier** | ~14,000 | ~15,000 | **~29,000** | LINGUISTIC_FRAMEWORK + VERIFIER_PROMPT(가장 김) |
| **Critic** | ~800 | ~3,000 | **~3,800** | LINGUISTIC_FRAMEWORK 미포함 |
| **Arbiter** | ~16,000 | ~3,000 | **~19,000** | LINGUISTIC_FRAMEWORK + 투표 시스템 |

### D-2. 포스트 1건당 총 토큰 소비

```
최소 경로 (노이즈 포스트):
  Gatekeeper(17K) + Decoder(21K) + Verifier(29K) + Arbiter(19K)
  = ~86,000 입력 토큰

최대 경로 (협업 포함):
  Gatekeeper(17K) + Decoder(21K) × 2 + Verifier(29K) × 2 + Critic(3.8K) + Arbiter(19K)
  = ~140,800 입력 토큰
```

### D-3. 토큰 부담 핫스팟

1. **LINGUISTIC_FRAMEWORK 4중 복제**: ~12K × 4 = **~48,000 토큰** (전체의 34–56%)
2. **Verifier 프롬프트 과도한 길이**: VERIFIER_PROMPT만 ~2,200줄. 형태소 매칭 규칙 3회 반복, 가상 예시 과다.
3. **Arbiter의 인라인 시스템 프롬프트**: `arbiter.py` 내에 ARBITER_SYSTEM이 직접 정의되어 있어 `expert_prompts.py`와 분리됨.

### D-4. 절감 가능 토큰

| 개선 항목 | 절감 토큰(추정) | 난이도 |
|-----------|:---------:|:---:|
| LINGUISTIC_FRAMEWORK 전문가별 subset 추출 | ~24,000–36,000 | 🔴 높음 |
| Verifier 프롬프트 내 반복 규칙 통합 | ~3,000–5,000 | 🟢 낮음 |
| 검색 결과 content 불필요 부분 제거 | ~1,000–2,000 | 🟢 낮음 |
| Critic에게 Verifier 전체 결과 대신 요약만 전달 (이미 구현됨) | — | ✅ 완료 |

---

## E. 하드코딩 잔여물 점검

### E-1. 플랫폼 도메인/이름 하드코딩 — 분류: ⚠️ 필요한 하드코딩

**위치**: 프롬프트와 코드 양쪽에 분포

| 파일 | 위치 | 내용 |
|------|------|------|
| `expert_prompts.py` L1160, L1181 | Gatekeeper 검색 전략 | `site:novelpia.com OR site:series.naver.com OR site:munpia.com OR site:page.kakao.com OR site:joara.com` |
| `expert_prompts.py` L1557–1570 | Decoder 플랫폼 매핑 | 7개 플랫폼 테이블 |
| `arbiter.py` L193–210 | Arbiter 플랫폼 매핑 | 동일 매핑 불릿리스트 |
| `decoder.py` L525–570 | `_extract_official_titles_from_search` | `official_platforms = ["novelpia.com", "namu.wiki", "munpia.com"]` |

**분석**: 이것들은 "한국 웹소설 플랫폼 생태계"라는 도메인 지식이며, 실제로 변경 빈도가 낮음. 다만 **한 곳에서 관리**되어야 유지보수가 용이함. 현재 4곳에 분산.

### E-2. 특정 작품명·작가명·캐릭터명 하드코딩 — 분류: ✅ 없음 (양호)

**확인 결과**: `expert_prompts.py` 전체(4,982줄)와 `arbiter.py`를 검색한 결과, 실제 작품명/작가명/캐릭터명의 하드코딩은 발견되지 않음. 모든 예시가 `[작품약칭]`, `[캐릭터명]`, `[작가명]` 등 **플레이스홀더** 형태를 사용.

이는 PROMPT_GUIDELINES.md의 원칙이 잘 지켜진 결과로 평가됨.

### E-3. 장르/트로프 키워드 목록 — 분류: 🟡 경계선

**위치**: `expert_prompts.py` L3750 (Verifier BLOCKING RULES 내)

```
카테고리 A - 장르/세계관: 무림, 현대, 판타지, 게임, 학원, 아카데미, 던전, 이세계, 마법사, 헌터
카테고리 B - 능력/치트: 회귀, 환생, 빙의, 전생, 귀환, 각성, 시스템, 레벨업, 즉사
카테고리 C - 역할/관계: 악녀, 악역, 주인공, 남주, 여주, 엑스트라, 조연, 황녀, 공작, 하인
```

```
장르/배경 키워드: 무림, 현판, 회귀, 게임, 학원, 빙의, 환생, 차원, 아카데미, 판타지
```

**분석**: 이 목록들은 "형태소 카테고리 분류 가이드"로 사용됨. 목록에 없는 신조어 장르(예: "먹방물", "공유계열")는 LLM이 인식 못할 수 있으나, 이는 프롬프트의 예시 역할이므로 영향 제한적.

### E-4. 인명 어미 패턴 — 분류: 🟢 허용

**위치**: `expert_prompts.py` L3340, L2950 등

```
인명 어미: -백, -영, -수, -진, -아, -현, -준
인명 어미 패턴: -이, -아, -영, -수, -백, -진
```

**분석**: 한국어 인명 형태소 패턴으로 언어학적 원리에 기반. 다만 2곳에서 목록이 미세하게 다름(순서, 포함 항목). 통일 필요.

---

## F. 종합 권고사항 (우선순위별)

### 🔴 Priority 1: 즉시 개선

#### F-1. LINGUISTIC_FRAMEWORK 전문가별 분리

**현황**: ~490줄 전문이 4개 전문가에 동일 삽입 → 포스트당 ~48K 토큰 낭비.

**제안**:
```python
# 현재
GATEKEEPER_SYSTEM = "..." + LINGUISTIC_FRAMEWORK + "..."

# 개선안
LINGUISTIC_CORE = "..."  # 핵심 원칙만 (100줄, ~3K 토큰)
LINGUISTIC_PRAGMATICS = "..."  # 화용론 (Gatekeeper/Arbiter용)
LINGUISTIC_MORPHOLOGY = "..."  # 형태소 (Decoder/Verifier용)
LINGUISTIC_DISCOURSE = "..."   # 담화 (Verifier/Arbiter용)

GATEKEEPER_SYSTEM = "..." + LINGUISTIC_CORE + LINGUISTIC_PRAGMATICS + "..."
DECODER_SYSTEM = "..." + LINGUISTIC_CORE + LINGUISTIC_MORPHOLOGY + "..."
```

**예상 효과**: 포스트당 ~24K–36K 토큰 절감 (28–42% 감소).

---

#### F-2. Verifier 프롬프트 압축

**현황**: VERIFIER_PROMPT가 ~2,200줄로 전 전문가 중 최장. 형태소 매칭 규칙이 3회 반복, 가상 예시가 과다.

**제안**:
1. STEP 0의 형태소 매칭 규칙을 1회만 정의하고, 나머지는 "위 규칙 참조" 지시
2. 가상 예시(pseudocode 포함)를 절반으로 축소
3. 축약어 감지 세부 절차(4단계 + 예시)를 별도 참조 문서로 분리

**예상 효과**: ~3K–5K 토큰 절감, LLM 주의력 분산 감소.

---

#### F-3. P0-3 환각 차단 로직 완화

**현황**: Decoder+Verifier 모두 null → Arbiter 제목 강제 삭제.

**제안**:
```python
# 현재
if decoder_title is None and verifier_title is None:
    arbiter_title = None  # 강제 삭제

# 개선안
if decoder_title is None and verifier_title is None:
    if arbiter_confidence in ("High", "Max"):
        # Arbiter가 확신하면 유지하되 경고
        result["notes"] += " [P0-3 경고: Decoder/Verifier 미확인]"
        result["confidence"] = "Low"  # 자동 하향
    else:
        arbiter_title = None  # 확신 없으면 삭제
```

**예상 효과**: Arbiter의 독자적 추론 능력 부분 복원, FN 감소.

---

### 🟡 Priority 2: 중기 개선

#### F-4. 플랫폼 매핑 단일 소스화

**현황**: 플랫폼 도메인/약칭이 4곳에 분산(E-1 참조).

**제안**:
```python
# expert_prompts.py 상단에 단일 정의
PLATFORM_MAPPING = """
| 약칭 | 정식명 | 도메인 |
|------|--------|--------|
...
"""

# 각 전문가 프롬프트에서 참조
DECODER_SYSTEM = "..." + PLATFORM_MAPPING + "..."
ARBITER_SYSTEM = "..." + PLATFORM_MAPPING + "..."
```

또한 `decoder.py`의 `official_platforms` 리스트도 이 매핑에서 파생되도록 구조화.

---

#### F-5. 검색 결과 content 제한 완화

**현황**: `orchestrator.py`에서 content를 100자로 제한.

**제안**: 200–300자로 확대. Verifier가 "서사 문장 패턴" 판별을 하려면 최소 2–3문장(~200자) 필요. 토큰 증가 비용 대비 판정 정확도 향상이 더 큼.

---

#### F-6. Decoder `_try_split_abbreviation_boundary` 개선

**현황**: 고정 분리점(3, 4음절).

**제안**: Kiwi 형태소 분석기를 활용한 의미 경계 분리. Gatekeeper에는 이미 Kiwi가 초기화되어 있으므로, Decoder에서도 동일 인스턴스를 공유하면 구현 용이.

```python
# 현재
for split_at in [3, 4]:  # 기계적 분리

# 개선안
kiwi_result = self.kiwi.tokenize(term_clean)
# 명사(NNG/NNP) 경계에서 분리
```

---

### 🟢 Priority 3: 장기 개선

#### F-7. Arbiter 시스템 프롬프트 외부화

**현황**: `arbiter.py` 내에 `ARBITER_SYSTEM`과 `ARBITER_PROMPT`가 인라인 정의(~660줄).

**제안**: `expert_prompts.py`로 이전하여 모든 프롬프트를 단일 파일에서 관리. 코드와 프롬프트의 관심사 분리(SoC).

---

#### F-8. is_relevant 판정 규칙 단일 소스화

**현황**: 3곳에 독립 정의(B-3 참조).

**제안**: LINGUISTIC_FRAMEWORK 또는 별도 상수로 `IS_RELEVANT_RULES`를 단일 정의하고, 각 전문가가 참조.

---

#### F-9. 전문가 요약 함수 표준화

**현황**: 각 전문가에 `_summarize_*` 함수가 있으나 구조 불일치.
- `_summarize_decoder()`: 3개 항목 제한, notes 200자 절단
- `_summarize_gatekeeper()`: 3개 타이틀, 2개 작가, 5개 키워드 제한
- `_summarize_verifier()`: 구조 다름 (novel_identity 직접 추출)

**제안**: `ExpertSummary` 공통 데이터클래스를 정의하고 각 전문가의 요약이 동일 스키마를 따르도록 표준화.

---

#### F-10. 세션 지식 학습 신뢰도 강화

**현황**: `_update_session_knowledge()`가 High/Max confidence만 학습(L218). 양호하나, 학습된 슬랭이 **다른 의미로 사용되는 포스트**에서 오판 유발 가능.

**제안**: 세션 지식에 만료(TTL) 또는 사용 횟수 카운터를 추가하여, 일정 기간/횟수 이후 자동 감쇠.

---

## 부록: 전체 위험도 매트릭스

| ID | 항목 | 위험도 | 영향 범위 | 수정 난이도 |
|----|------|:------:|:---------:|:-----------:|
| A-1 | 플랫폼 약칭 매핑 | 🟡 | Decoder, Arbiter | 🟢 낮음 |
| A-2 | is_author_name 결정 트리 | 🟢 | Decoder | — |
| A-3 | 복합 토큰 분리 | 🟡 | Decoder | 🟡 중간 |
| A-4 | P0-3 환각 차단 | 🟠 | Arbiter | 🟢 낮음 |
| A-5 | BLOCKING RULES | 🟡 | Verifier | 🟡 중간 |
| B-1 | LINGUISTIC_FRAMEWORK 4중 복제 | 🔴 | 전체 | 🔴 높음 |
| B-2 | 플랫폼 매핑 중복 | 🟡 | Decoder, Arbiter | 🟢 낮음 |
| B-3 | is_relevant 3중 중복 | 🟡 | Verifier, Arbiter | 🟡 중간 |
| B-4 | 형태소 매칭 반복 | 🟢 | Verifier | 🟢 낮음 |
| B-5 | 작가 비평 중복 | 🟡 | Verifier, Arbiter | 🟡 중간 |
| C-1 | suspected_titles | ✅ | 전체 | — |
| C-2 | author_info | ⚠️ | Decoder→Arbiter | 🟢 낮음 |
| C-3 | 검색 결과 전달 | ⚠️ | Orchestrator | 🟢 낮음 |
| D-1~4 | 토큰 부담 | 🔴 | 전체 | 🔴 높음 |
| E-1 | 플랫폼 하드코딩 | ⚠️ | 4곳 분산 | 🟢 낮음 |
| E-2 | 작품명 하드코딩 | ✅ | — | — |
| E-3 | 장르 키워드 목록 | 🟡 | Verifier | 🟢 낮음 |

---

*감사 완료. 위 보고서는 코드 전문 읽기(expert_prompts.py 4,982줄, arbiter.py 1,234줄, orchestrator.py 1,026줄, decoder.py 660줄, verifier.py 364줄, gatekeeper.py 274줄, critic.py 257줄, agentic_pipeline.py 524줄)에 기반합니다.*
