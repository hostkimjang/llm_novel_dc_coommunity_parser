# 연구 저널 · 인덱스 (파이프라인 품질 개선 프로젝트, 2026-06-26 ~ 07-05)

> 목적: 전수조사→근본원인→아키텍처 연구→codex 개선루프 감사에 이르는 전체 연구를 한 곳에 보존한다.
> 대부분의 연구 본체는 아래 §1의 개별 문서로 이미 저장돼 있고, **이 문서의 고유 가치는 §2(개선루프 감사·steering 이력)와 §3(쉬운 말 용어집)** — 채팅 세션에만 있던 내용을 여기 보존한다.

---

## §1. 연구 문서 인덱스

| 문서 | 내용 | 상태 |
|---|---|---|
| `docs/devs/DETECTION_SURVEY_AND_ROOTCAUSE_20260626.md` | 전수 재판정(577건, 불일치 23.6%) + 6갈래 코드 근본원인 + FIX-0~4 로드맵. **단일 근본원인 = 맥락결속 게이트 부재("표면 겹침=결속")** | 저장/git |
| `docs/devs/detection_survey_20260626_errors.json` | 확정 오류 136건(post_id·failure_class·fix_axis·정답추정) | 저장/git |
| `docs/devs/GOAL_REGRESSION_SAFE_GROUNDING_LOOP.md` | codex 회귀안전 개선루프 운영계약 v2(단일 술어·3중 회귀축·golden·blind judge). ※codex가 loop별 addenda 누적 중 | 저장/git |
| `docs/devs/CODEX_KICKOFF_SURVEY_AND_LOOP.md` | codex 킥오프 프롬프트(전수검사→아이디어→구현→canary→재검수→Phase G 회차보고서 @data-analytics) | 저장/git |
| `docs/devs/ARCHITECTURE_RESEARCH_AND_CASE_STUDY_20260704.md` | 아키텍처 전반 진단(판단유무=veto누산, 원리적 아님) + 유사분야 사례연구(EL/ER/RAG/judge/CACE) + 재설계 권고(하이브리드) | 저장(미커밋→커밋 필요) |
| `docs/devs/RESEARCH_JOURNAL_AND_INDEX_20260705.md` | **이 문서** — 인덱스 + 감사/steering 이력 + 쉬운 용어집 | 신규 |
| `docs/devs/loop_reports/LOOP_*.md` | codex 회차별 보고서(1~409+, @data-analytics artifact 포함) | codex 생성/git |

관련 Claude 메모리(세션 밖 영속, `.claude/.../memory/`): `detection-survey-20260626-rootcause`, `codex-loop-midcheck-20260701`, `arch-research-case-study-20260704`.

---

## §2. 개선루프 감사 · steering 이력 (채팅 전용 → 여기 보존)

codex가 `GOAL_REGRESSION_SAFE_GROUNDING_LOOP.md`를 자율 실행. Claude가 주기적으로 감사하고 steering(진행 중 주입)으로 교정한 이력. 신호등: 🟢양호 / 🟡주의 / 🔴문제.

### 점검 #1 — 2026-07-01 (loop237) → 🟡 drifting
- **이식 O**: 3중 회귀축(baseline/panel/golden) 실파일 동결, golden blind hard-FAIL, 게이트 분리, REVIEW-LOCKED·full_scan=false, Phase1 전수판정 1933/1933, `_post_discusses_work_as_work` 술어 구현.
- **문제**: (P0) recall 과교정 — 동일 packet safe_resolved 12→11→9 순감소, 정당 해소가 promotion_blocked로. (P1) 후반 137회 queue 131(0/61/70) 동결 = churn. whack-a-mole(11663540 등 15~17회 반복). (P2) 미커밋 106파일(agentic +10275줄, 06-23 이후 커밋 0).
- **steering 발송(5점)**: ①워킹트리 논리단위 커밋 ②동일 packet 재실행 중단+정지조건을 'queue감소+safe 단조 비감소'로 ③상위 수렴(PromotionDecision/publish_contract) 실구현 ④safe-loss flip rate 측정→비결정이면 재라벨, blind judge 후 hard-hold 완화 ⑤_has_verified_contextual_alias_work_bridge를 공유 술어로 통합 + 진동행 골든 편입.

### 점검 #2 — 2026-07-02 (loop238~287) → 🟢 improving(조건부)
- steering 5개 전부 실코드+커밋 반영. P2 해소(체크포인트+48커밋, 워킹트리 clean). P1 거의 해소(38-row 재실행 중단, 정지조건 코드화 `tools/evaluate_goal_convergence.py`, queue 131→7). P0 측정 이행(flip N=3).
- **신규 위험(조건부)**: stale 증거 인용 / 승인 이중 교착(런이 light/no-search라 완주해도 자기 게이트에 탈락) / 폴링 정체 조짐.
- **steering 발송(3줄)**: ①stale 증거 갱신(flip N≥5+full375 replay)+진동행 골든 편입(16→18)+golden git 추적 ②bounded non-light+search 런 발주+검색 degraded 복구 P0 ③'코드변경 없음' 3연속 시 collateral triage로 강제 전환.

### 점검 #3 — 2026-07-03 (loop288~358) → 🟡→🔴 강등 (운영축)
- steering 형식 이행되나 **런타임 blocker 신규 개방**: LLM watchdog interactive pause("터미널에 y 입력")가 background 무한대기 → search 포함 런 전멸(bounded/full375/golden18/N5 모두 0 완료), current-HEAD canary approval 도달률 0%.
- flip N=5 재측정이 그림을 뒤집음(N=3 안정으로 본 2건이 실제 0.4 비결정). collateral 183→105는 착시(95% 재분류). survey 근본원인 미착수, 하드코딩 cue 재발(R1 안티패턴).
- **steering 발송(3줄)**: ①런타임 비생산 P0-1 격상(신규 발주 동결, golden18 18/18 완주로 stall 우회 실증 후 재개) ②큐 회계 중단+OVERRIDE AUDIT blind judge 강제+collateral 2축 리포팅 ③R1 하드코딩 cue 금지+triage를 survey 136 defect로 재앵커.

### 점검 #4 — 2026-07-03 후반 (loop359~373) → 🟢 improving(진짜 회복)
- steering **실질 이행**: watchdog/stall guard 실작동→golden18 **18/18 완주 가능**해짐(loop371). collateral 2축(74/4), OVERRIDE AUDIT blind 실행, R1 하드코딩 중단 명시, survey 재앵커. promotion gate **일반 술어** 강화(wrong-publish 차단, 하드코딩 아님).
- 잔여: golden18 간헐 stall(loop373 13/18), golden 정답 14/18, search P0 OPEN.

### 점검 #5 — 2026-07-04 (loop374~409) → 🟢 꾸준한 수렴
- 런타임 blocker 사실상 해소(golden18 안정 18/18 완주). golden 정답 14→16/18 상승. **recall miss 11694019 수정**(일반 술어 `_contextual_exact_titles_without_official_detail`, R1 방향 정확). 규율 전부 유지, 하드코딩 없음.
- 잔여(정상): golden 3건(11705245 over-publish, 11668307 single↔mixed 회귀, 11698880 wrong_work), golden 18/18 미달, full375 FROZEN(올바른 순서).
- **결정: 개입 최소.** golden 18/18 → full375 해동 결과를 다음 점검에서 확인.

### 다음 점검 시 확인할 신호
1. golden expected-answer **18/18** 달성 (현재 16/18) — 11698880/11694019/11700470 닫히는지
2. 그 직후 **full375/bounded 해동 시 collateral** — 회귀 대량이면 golden 과적합, 조용하면 진짜 수렴 (**제일 중요한 분기점**)
3. golden18 간헐 stall 완전 소멸(temp=0/seed 결정성)
4. 11668307 single↔mixed 비결정 재발 여부

### 다음 개입이 필요할 신호
- full375 해동 시 회귀 대량 → 회귀패널 확대
- 코드변경 없이 docs만 반복(폴링 정체 재발)
- golden 18/18 못 넘고 같은 3~4건 두더지잡기 재발

### 합의된 아키텍처 개선 도입 순서 (B안 — 점진·안전)
1. 현재 루프는 golden 18/18 + full375 해동까지 **놔둔다**(중단 금지).
2. 새 결정방식(캘리브레이션 확률 + NIL)을 **그림자 모드**로 붙여(프로덕션 판단 불변, 확률만 로그) 같은 golden/회귀패널로 "지금 방식보다 나은가" 비교만.
3. 그림자에서 회귀 없이 이기면 그때 게이트를 확률 기반으로 스위치 + NIL 정식 배선.
4. 그 다음 "쉬운 건 싸게" 2단 캐스케이드로 비용 절감.

---

## §3. 쉬운 말 용어집 (비전문가용 primer)

이 프로젝트 = **도서관 사서**가 손님의 어렴풋한 말("무림에서 즉사기 들고 다니는 그거")을 듣고 정확한 책(『즉사기 들고 무림에 떨어지다』)을 찾아주는 일. 학계 용어로 **Entity Linking / Entity Resolution**(이미 20년 연구된 문제).

사서의 3단계: ①후보 떠올리기 ②맞는 것 고르기 ③못 찾으면 솔직히 손 들기. 우리 시스템은 **③이 약함**.

**지금 문제(딱 하나)**: 우리 시스템은 **"글자가 겹치는가"**만 본다. "이 글이 정말 그 작품을 이야기하나"는 안 본다. 그래서 "짜장면"이란 글자가 제목에 든 책이 있으면 점심 짜장면 얘기(#11668278)를 그 책으로 매칭. 마파두부→Fate, 프로모션(체스)→작품 다 같은 패턴.

| 용어 | 쉬운 뜻 | 우리 예시 |
|---|---|---|
| **판단유무 / abstention** | 확정할까 vs "모르겠음"으로 넘길까 | 마파두부는 넘겼어야 함 |
| **NIL** | "여기엔 답 없음". (a)작품 얘기 아님(짜장면) (b)작품인데 특정 불가 | 지금은 이걸 "실패 찌꺼기"로 취급, 정식 선택지 아님 |
| **calibration(신뢰도 교정)** | "90% 확신"이 실제로 10번 중 9번 맞나 | 우리 confidence는 가짜 라벨(실제 정확도와 무관) |
| **selective prediction** | 확실한 것만 답하고 모르는 건 비우기(정답률↑) | 확신 높은 것만 확정, 애매하면 보류 |
| **conformal / ε 보증** | "확정한 것 중 틀린 건 5% 이하"를 수학적으로 보장 | 지금 기준(0.18/0.78)은 손으로 대충 맞춘 것 |
| **후보생성 vs 순위** | 널널하게 모으기(글자겹침 OK) vs 깐깐하게 고르기 | 글자겹침을 최종 확정에 그대로 써버리는 게 오류 근원 |
| **표면 겹침 vs 맥락 결속** | 글자만 같음 vs 글이 실제로 그 작품을 논함 | 이게 이 프로젝트의 핵심 구분 |
| **veto 누산 캐스케이드** | "막을 이유 목록에 뭐 하나 걸리면 보류, 아니면 통과"라는 ○/× 도장 | 확률이 없어서 기준선을 못 세움 |

**유사 시스템(쉬운 말)**:
- **BLINK**(페북): 글자겹침이 아니라 "글 문맥 ↔ 작품 설명문"이 어울리나를 봄.
- **Self-RAG**: "관련 있다"와 "근거가 실제로 뒷받침한다"를 **따로** 체크(우리가 혼동하는 그 지점).
- **Learn-to-Not-Link**: "모르겠으면 손 들기"를 정식으로 가르침(안 가르치면 무조건 답하려 듦).
- **PoLL**: 심판을 한 명이 아니라 서로 다른 여러 명한테 맡겨 다수결(자기 답 편애 방지).
- **Model collapse**(네이처): AI가 자기 결과를 다시 학습하면 서서히 망가짐 → slang_db 자기저장 오염 위험과 동일.
- **CACE / whack-a-mole**: 부품이 얽혀 있으면 하나 고치면 딴 데가 터짐(우리 두더지잡기의 구조적 이유).

**결론(쉬운 말)**: 다 뜯어고치는 게 아니라 **판단 방식만 바꾸자** — "막을 이유 있나?"(○/× 도장)에서 → **"이 글이 이 작품일 확률 몇 %?" 숫자를 만들고 → 기준 넘으면 확정, 애매하면 당당히 '모르겠음'**. 그리고 쉬운 건 싸게(7분/post↓), 어려운 것만 전문가 투입. 이게 마파두부·짜장면·고능아를 한 번에 푸는 열쇠.
