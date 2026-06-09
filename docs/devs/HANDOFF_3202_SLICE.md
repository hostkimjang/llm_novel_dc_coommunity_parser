# 작업 인수 — llm_novel_dc_coommunity_parser 품질 개선 (3202건 full-scan 슬라이스, precision↔recall 양면, 실행 기반 자율 반복)

C:\Users\kimjang\Documents\GitHub\llm_novel_dc_coommunity_parser 작업을 이어받아라.
이 goal은 dcinside/노벨피아 커뮤니티 글을 작품 매칭 대상으로 처리하는 파이프라인의 품질 개선이며,
"실제 실행 결과를 근거로 개선을 반복"하는 작업이다. 이번 인수의 1차 근거는 104k full scan의
앞부분 연속 슬라이스 **3202건** 실행 결과(`out/expert_result_20260608_141239_048970.json`)다.

## 0. 개선 surface = primary repo (확정, 사용자 확인 2026-06-09)
- 이번 goal의 **코드/테스트/재실행은 primary repo**(`C:\Users\kimjang\Documents\GitHub\llm_novel_dc_coommunity_parser`)에서 한다. 사용자가 명시 확인했다.
- 근거: 이 3202 run은 primary repo에서 실행됐고(`run_meta.main_log_file`이 primary 경로), 아래 findings의 코드
  line number(agentic_pipeline.py / arbiter.py / verifier.py)도 모두 primary repo 기준이다.
- worktree `.codex/worktrees/3229`는 이전 **단건(v738) lane**이며 거기엔 `over_resolution_review/strong_bridge/
  recommended_confidence` 신호 필드와 `_apply_over_resolution_demote`(opt-in) 메커니즘이 있지만, **이 run 결과엔
  그 필드가 없다**. worktree 3229의 `GOAL.md`는 **상위 운영 계약**(과대주장·hardcode 금지, 단계 분리)으로만 참조한다.
- 시작 시 1회: primary repo에 worktree의 v740/v741 신호·demote 메커니즘을 포팅할지 검토한다(필수는 아님 —
  신호는 실재 필드로 재정의 가능). goal 문서·체크리스트는 primary repo `docs/devs/`에 둔다(이 파일이 그 시작점).

## 1. 먼저 읽을 문서 / 핵심 artifact
- 이 파일(HANDOFF_3202_SLICE.md)
- `out/_handoff_analysis/_synth.json` — **검증된 개선 백로그 18건 + 균형 원칙 + 근본원인**(아래 5~7절 원본)
- `out/_handoff_analysis/*.jsonl` — 버킷별 대표 표본(R1/R2/R3/P1/P2/P3/I1)
- `out/expert_result_20260608_141239_048970.json` — 3202건 원본 결과(81MB, 스트리밍 집계로 읽어라)
- (상위 계약) `.codex/worktrees/3229/.../GOAL.md`, `docs/devs/SCAN_RESULT_REVIEW_GUIDE.md`,
  `QUALITATIVE_SEMANTIC_REVIEW_LOOP.md`, `OPERATION_QUALITY_CHECKLIST.md`, `TODO.md`, `CHECKLIST.md`,
  `VERIFICATION_RESULTS.md`, `IMPROVEMENT_REGISTER.md`

## 2. 이번 실행 컨텍스트 (확정값)
- 입력: 104k full scan의 **앞부분 연속 슬라이스 3202건**. 무작위 표본도 high-risk over-sample도 아닌 순차
  head slice다. → **이 라벨/신호 분포를 모집단 오류율로 환산하지 마라.** 용도는 known-bad/recall-gap
  discovery + 일반화 gate의 runtime 검증이다. approval numerator/denominator가 아니다.
- 모델 `Gemma-4-E4B`(remote, `http://10.20.0.101:8000`), MCP shard 16/16 healthy.
- **effective_parallel = min(input_count, 16, healthy_endpoint_count) = 16** 이 정상이다(요청 16 = healthy 16).
  단건 v738의 "16 worker 채우려 재실행 금지"는 input<16일 때 얘기다. 3202 input엔 16이 맞다.

### 전수 분포 (N=3202)
- is_relevant: true 665 / false 2537. work_resolution: resolved **432** / none 2537 / unresolved 217 / multi_work 16.
- title_resolution_state: resolved 432, adjacent 1172, **unresolved_matchable 845**, context_only 284,
  author_new_work_context 281, **ocr_explicit_title_unresolved 100**, nonwork 51, unresolvable_memory_query 21, multi_work 16.
- discussion_type: trope 1184, noise 869, character_talk 266, general 254, undecodable 139, author_talk 132,
  review 122, off_topic 120, recommendation 53.
- resolved 432 중: confidence High **401**/Medium 30/Low 1, **locked 341**, anchor_strength high 274/**medium 132/low 4/none 22**,
  source_tier official_detail 353/mixed 51/community 18/llm_only 6, anchor_type title_exact 190/title_alias 114/image 82/none 22/author 16.
- 이미지: image_count>0 **1885건 전부** image_evidence_catalog 채워짐·vlm_enabled·fetch_success 1876 (이미지 evidence 보존은 양호).
- 웹검색: search_evidence **0건이 1115건(34.8%)**, 평균 10건.

## 3. 핵심 목표 (outcome) — precision ↔ recall 양면
이 goal은 "작품을 안 찾는다"가 아니라 **"증거가 충분하면 작품을 정확히 찾아낸다"**이다.
확정을 늘리는 것도, 보류를 늘리는 것도 목표가 아니다. 목표는 **증거 강도에 resolution/confidence/locked를 정렬**시키는 것이다.

A. RECALL — 증거 수집·이해를 키워 작품을 찾아낸다
- 웹검색 증강(RAG): query 설계·재검색·search_evidence_catalog 활용을 강화해 매칭 가능한 글의 회수율을 높인다
  (근거: search 0건 34.8%, unresolved_matchable 845 — 단 noise 제외한 진짜 기회만).
- 증거 이해력: 검색 snippet·official/detail URL·제목 anchor·comment answer·이미지 OCR/VLM를 종합 해석해 단편
  증거로도 정당하게 작품을 확정한다 (근거: ocr_explicit_title_unresolved 100 = 제목을 읽고도 미해소 → 이해 gap).
- 진짜 작품 토론/추천/탐색 글을 "검색 단어 부족"만으로 미해소로 남기는 false negative를 줄인다.

B. PRECISION — 약한 증거로 과대확정하지 않는다
- seed 없는 잡담/한탄/트로프/작가얘기/플랫폼밈을 검색 단어만으로 작품 매칭하지 않는다 (비작품 의도 resolved 217).
- 약한 anchor(medium/low/none)·약한 source_tier(community/llm_only)에 High+locked로 과잉 확정하지 않는다
  (resolved의 36.6%가 sub-high anchor).
- reason이 evidence보다 세게 말하는 overclaim을 잡는다.

C. 이미지/멀티모달
- 이미지가 표지·제목 anchor를 직접 줄 때 VLM/OCR로 작품을 찾아낸다(recall). 분위기·캐릭터·밈만으로는 확정하지 않는다(precision).

D. 일반화·검증가능성
- known-bad/high-risk를 hardcode가 아니라 gate/prompt contract/parser·schema/review artifact/test로 남긴다.
- 증거 수집·확정 판단을 runtime/result/review 단계에서 분리·검증 가능하게 한다.

## 4. 양축 균형 원칙 (모든 개선의 guardrail)
- **확정강도(locked/confidence)와 작품발견(resolved/후보존재)을 분리한다.** 모든 precision fix는 resolved title
  자체를 제거하지 말고 `locked true→false`, `confidence High→Medium/Low`의 **한 단계 강등**에만 그친다.
  → resolved 432·title_resolution_state resolved 카운트가 보존되어 recall 직접 손실이 0이다.
- 모든 recall 증강은 **명시 seed 게이트**(anchor_strength≥medium 또는 서사앵커 plot/character 또는 카탈로그
  구조신호 2종 공기)에만 발화시킨다. anchor_strength=none(콘/빔·밈·일상)은 계약상 **절대 제외**.
- recall은 "검색·후보 정화"까지만 적극적으로, **확정(lock)은 본문/이미지/공식URL 1차 앵커를 요구하는 보수
  게이트로 분리**한다. 후보 풀을 정화해도 verifier promotion 게이트(in-post bridge/convergence 요구)는 손대지 않는다.
- 주의: `locked`는 단순 표시가 아니라 다운스트림 후보선택 입력(agentic_pipeline.py:15791 has_official_candidate,
  37325/37501/40008 우열비교)이다. lock 박탈이 canonical override를 유발해 정당 resolved를 displace하지 않도록,
  lock 값만 바꾸고 **title 보존을 보장하는 단위테스트를 배포 전제**로 못박는다. 미충족 항목은 drop.
- read-only review_artifact/telemetry는 자동 트리거에 연결하지 말고 **사람 검토 큐 한정**으로 둔다.

## 5. 최우선 근본원인 (개별 패치보다 이 3갈래 재정렬이 임팩트 최대)
단일 최상위 근본원인 = **증거 등급(evidence tier)과 확정 권한(lock 권한)의 분리가 양방향 모두 미흡**.
- (A) 깨끗한 OCR 카탈로그 상세(작품명+작가+메트릭+시놉시스)와 단순 search_only를 **동일 tier로 취급** —
  `arbiter.py:7480 _has_official_title_evidence`가 web-fetch structured_info만 인정하고 image OCR 카탈로그를
  official_title_evidence=false로 일괄 처리 → R2 recall 누락의 직접 원인(+R3/P3 연결). **해소: OCR 카탈로그
  구조신호를 official_detail에 준하는 tier로 승격(recall↑).**
- (B) alias/stability 복구 경로(arbiter.py:4255/4416/4642/5186/5225 `_has_title_abbrev_stability_signal`)가
  음수 정합 스코어(-8/-5)·Verifier critical 반론·일반명사/도메인 약칭조차 무시하고 anchor_strength=medium
  하드셋 + confidence High 승격 + locked=true로 닫는다 → P1·P2·I1 과대확정의 공통 뿌리. **해소: lock 권한을
  'title_alias 단독 표면'에서 분리해 본문/이미지/공식URL 1차 앵커 또는 음수스코어·critical 부재를 요구(precision↑).**
- (C) reasoning(notes/Synthesizer/Verifier 결론 confidence)과 emit 필드(primary_work.confidence/locked) 사이에
  **캘리브레이션 ceiling이 없음** → 내부적으로 'low/확정 안 함'인데 High+locked로 출력. **해소: emit 직전
  reasoning-field 정합성 ceiling 강제(precision↑).**
이 셋은 특정 제목/별칭/post id가 아니라 '증거 구조 신호'·'앵커 출처·스코어·캘리브레이션'이라는 일반 조건으로만 작동 → hardcode-safe.

## 6. 실행 기반 반복 루프 (자율 — 상한 없이 종료조건까지)
한 사이클을 끝냈다고 턴을 끝내지 마라. 종료조건 전까지 스스로 다음 사이클로 넘어가라. 세션 사이클 상한은 없다.

[1 iteration]
1) RUN: preflight으로 healthy endpoint·input_count 확인 → effective_parallel=min(input,16,healthy). 이미 있는
   3202 run 결과를 1차 근거로 쓰고, 개선 검증이 필요하면 동일 슬라이스(또는 신호가 잡힌 대표 부분집합)로 재실행.
2) INSPECT: 3202 결과 **전체에서 신호 분포·집계**를 먼저 본다(2절 분포 + 7절 백로그의 버킷 정의 활용). 이 run엔
   worktree의 over_resolution_review 필드가 없으므로 신호는 실재 필드(anchor_strength·source_tier·locked·
   confidence·title_resolution_state·search_evidence_catalog·image_evidence_catalog)로 재정의해 집계한다.
   가장 임팩트 큰 품질 문제 1개를 post 근거+신호값으로 특정한다.
3) SELECT: 그 문제를 닫을 일반화 개선 1개. 5절 근본원인/7절 백로그/CHECKLIST·TODO와 교차.
4) IMPLEMENT: 일반화만(gate/prompt_contract/parser·schema/evidence_augmentation/review_artifact). 4절 균형
   원칙 준수(precision fix는 title 보존·한 단계 강등, recall fix는 명시 seed 게이트·promotion 게이트 불변).
   특정 post id·제목·별칭·오타를 production code에 hardcode하지 마라.
5) RE-RUN+VERIFY: 같은 슬라이스(또는 대표 부분집합)로 재실행, before/after **신호 분포 차이**로 의도대로 바뀌었는지
   확인. focused unittest 추가·실행(+ 4절 'title 보존' 회귀테스트) → goal-contract/VLM/IAB/review bundle →
   hardcode scan → git diff --check. whitespace error 0, CRLF는 기록만.
6) RECORD: CHECKLIST 체크, VERIFICATION_RESULTS에 before/after 신호 분포와 함께 append, IMPROVEMENT_REGISTER 갱신,
   HISTORY·영향 docs 리뉴얼, before/after 증거를 review artifact로 저장.
7) 진행로그: "[i] <문제→개선> — run/fixed/reran/recorded" 2줄 이내. 즉시 1)로.

[종료조건 — 이 중 하나에서만]
- 최신 3202 결과에서 코드로 닫을 수 있는 품질 문제가 더 나오지 않음
- 정책/scope 판단 등 사용자 결정이 필요한 hard blocker
- 정의된 entrypoint로 복구 불가한 인프라 장애(endpoint 전멸 등)

## 7. 우선순위 개선 백로그 (검증 완료 — 전체는 `_synth.json`)
모두 적대적 검증(hardcode 아님 / 표본 지지 / 반대축 regression)을 거쳤다. rank는 임팩트순. 각 항목은 4절 균형
원칙의 가드 조건을 반드시 동반한다(특히 precision은 title 보존, recall은 명시 seed 게이트).

- **R1·근본원인 B/C (precision):** alias/stability 복구의 locked/confidence 승격 앞에 **'음수 정합 스코어 OR
  Verifier critical 반론' 차단 게이트** 추가. title 보존, locked→false·High→Medium 강등만. (근거 11697261, 11674702)
- **R2·근본원인 A (recall):** **OCR 카탈로그 상세를 'ocr_catalog_detail' tier로 승격** — (작품명)+(작가)+
  (메트릭/시놉시스/플랫폼마커) 중 2종 공기 시에만 `_has_official_title_evidence=true`. 본문-OCR 주제 정합성
  체크로 author_talk/release_meta 제외. (근거 11695625, 11645787, 11637724)
- **R3 (precision):** lock 부여를 'title_alias 단독 표면'에서 분리 — 본문 직앵커/OCR 공식표제/공식 URL 중 1개
  동반 시에만 locked. **title 보존 회귀테스트 선행**(미충족 시 drop). (근거 11674702, 11676327)
- **R4 (precision):** 약칭이 둘 이상 상이한 정식제목으로 분기(동일 original 약칭 cardinality≥2 & 본문 교차증거
  부재)면 locked 금지·Medium 이하. `_distinct_titles_for_orig` 방식 한정, 수렴 약칭(즉사무림 등) 무영향. (11674702)
- **R5 (recall):** 검색 degraded/무결과 시 **쿼리 변형 1~2회 재시도**(플랫폼 컨텍스트 부착/한국어 원형 복원/
  대체엔진). **anchor≥medium 또는 resolved/ocr_explicit seed에만 발화**, 신규 결과는 official_detail 매칭 시에만
  locked. (근거 11697261, 11690869, 11718099)
- **R6 (precision):** OCR 표면 제목면과 최종 official_title 토큰 정합성 게이트 — 최종에 표면 없는 누출어
  (예: '하차') 포함 시 image High+locked 금지·한 단계 강등. `_is_similar_title` 재사용해 OCR 오타 근접일치 제외. (11673102)
- **R7·근본원인 C (precision):** emit 직전 **reasoning-field 캘리브레이션 ceiling** — notes/verifier가 'low/확정
  안 함'으로 구조화한 경우 그보다 높은 confidence/locked emit 차단. 구조화 신뢰도 필드로만 트리거, 강근거 면제. (11674702)
- **R8 (precision):** meme/banter/off_topic & title_in_post=false에서 alias-bridge 면제만으로 locked High 금지 —
  post-local 강증거(줄거리/캐릭터/플랫폼URL/회차참조) 1개 이상 요구, 없으면 Medium. (11650584, 11660253)
- **R9 (recall):** candidate==1 & official_evidence=false에서 무조건 withhold 금지 — 서사앵커 보유 & 플랫폼 URL
  '단일작 수렴'과 AND 시 **약확정(Low, locked=false)** 후보 제출. anchor=none 절대 제외. (11669927)
- (R10~R18: 약칭 specificity 게이트, 이미지 동명 모호성 계약, lock_justification_anchor 필드, OCR title 출처
  스키마(ocr_source), 미해소 텔레메트리, R1 버킷 review 재분할, image resolution_basis 스키마 — 전부 `_synth.json`)

## 8. 범위 — 단계적 (REVIEW-LOCKED → large-scale 진입조건)
- 이번 세션 기본은 기존 REVIEW-LOCKED 규율이다. 이 3202 순차 슬라이스로는 population/10만 semantic approval을
  주장하지 마라. 3202는 discovery + gate 검증 근거다.
- large-scale 트랙(random baseline / P0-P1 high-risk / completed-source denominator / Browser·VLM evidence /
  packet-level semantic review) **진입 조건**: ① 개선 후 신호 분포가 재실행에서 안정적으로 재현되고,
  ② completed-source denominator가 `--preflight --fail-on-locked-source` gate를 통과하고,
  ③ random baseline 표본 설계가 순차 슬라이스와 별도로 존재할 때. 충족이 보이면 별도 large-scale evidence plan을
  산출물로 만들어 사용자 판단을 받는다.

## 9. 실행/안전 규칙
- docker compose up / expert_main.py / worker / 필요한 WARP은 자유롭게 실행. 이미 떠 있는 WARP16/MCP shard는
  `--reuse-shards-only`로 재사용하고 새로 올리지 않는다.
- 파괴적 동작(shard recreate, process kill)은 복구에 꼭 필요할 때만 최소 경로로, 사유 기록.
- Data Analytics MCP는 불안정 — 명시 요청 전엔 재시도하지 말고 local manifest/JSONL/Markdown evidence 우선.
- 실행 후 shell exit만 보지 말고 wrapper audit/result manifest/stdout/stderr 확인.

## 10. 절대 금지 (과대주장·hardcode·padding)
- 순차 3202 슬라이스를 모집단 오류율 / 10만 semantic approval / population approval로 환산하지 마라.
- targeted closure / runtime GO를 population approval로 승격하지 마라.
- 사용자 대표 사례만 보고 모집단 품질을 승인하지 마라.
- 특정 post id·제목·별칭·오타를 production code에 hardcode하지 마라.

## 11. 검증 기준 (각 사이클 5단계 강제)
- 새 tool/test → focused unittest 추가·실행. (worktree에서 돌릴 경우 pytest 없음 →
  `.venv312/Scripts/python.exe -m unittest tests.test_<name>`. primary repo는 자체 러너 확인.)
- precision fix는 **title 보존 회귀테스트** 필수.
- 관련 goal-contract/VLM/IAB/review bundle 실행, known post/title/alias hardcode scan, git diff --check.
- 개선 전/후 runtime 출력의 **신호 분포 차이**를 증거로 남길 것.

## 12. parallel 기준
- worker cap = 16. effective_parallel = min(input_count, 16, healthy_endpoint_count).
- 3202 입력 + healthy 16 → parallel=16이 정상. 16을 넘기지 말고, 16 미만으로 임의 축소하지도 마라.

## 13. 최종 보고 (종료조건 충족 시에만, 한국어)
- 실행한 것(입력 슬라이스·input_count·effective_parallel·entrypoint), 발견한 신호 분포 문제 → 개선을 사이클별로.
- 각 개선의 before/after **신호 분포** runtime 증거.
- built / tested / 실행검증됨 / 미해결 구분.
- "package build / runtime execution = 품질 승인 / semantic 승인 / 10만 approval"을 절대 섞지 마라.
- large-scale 진입 조건(8절 ①②③) 충족/미충족 명시.
- 다음 세션 이어받기: 다음 입력(다음 슬라이스 또는 random baseline 설계)과 다음 개선 후보 명시.
