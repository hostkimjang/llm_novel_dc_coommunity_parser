# GOAL: 3202 슬라이스 근본원인 직격 — expert 체인 diff · 백로그 rank1-3 구현 · HANDOFF 커밋 (primary repo)

작성: 2026-06-09 / surface = **primary repo** (`C:\Users\kimjang\Documents\GitHub\llm_novel_dc_coommunity_parser`, 사용자 확인)

이 goal은 분석이 아니라 **실행 작업 3건을 순서대로 닫는** work order다. 아래 핵심 목표·균형 원칙을 모든 작업에 적용한다.
더 넓은 맥락(전수 신호 분포, 근본원인 3갈래, 백로그 18건)은 `docs/devs/HANDOFF_3202_SLICE.md`와 `out/_handoff_analysis/_synth.json`을 따른다.

## 먼저 읽을 것
- `docs/devs/HANDOFF_3202_SLICE.md` — 상위 계약: 전수 신호 분포, 근본원인 3갈래, 백로그.
- `out/_handoff_analysis/_synth.json` — 검증된 백로그 18건 원본(rank·근거 post·regression 위험).
- (참조) worktree `.codex/worktrees/3229/.../GOAL.md` — 과대주장·hardcode 금지, 단계 분리 계약.

## 핵심 목표 (outcome) — precision ↔ recall 양면
이 goal은 "작품을 안 찾는다"가 아니라 **"증거가 충분하면 작품을 정확히 찾아낸다"**이다.
확정을 늘리는 것도, 보류를 늘리는 것도 목표가 아니다. 목표는 **증거 강도에 resolution/confidence/locked를 정렬**시키는 것이다.

A. RECALL — 증거 수집·이해를 키워 작품을 찾아낸다
- 웹검색 증강(RAG): query 설계·재검색·search_evidence_catalog 활용을 강화해, 매칭 가능한 글의 resolved 회수율을 높인다.
  (현 run 근거: search_evidence 0건 34.8%, unresolved_matchable 845 — 단 noise 제외한 진짜 기회만)
- 증거 이해력: 검색 snippet·official/detail URL·제목 anchor·comment answer·이미지 OCR/VLM를 종합 해석해
  단편 증거로도 정당하게 작품을 확정한다. (ocr_explicit_title_unresolved 100 = 제목을 읽고도 미해소 → 이해 gap)
- 진짜 작품 토론/추천/탐색 글을 "검색 단어 부족"만으로 미해소로 남기는 false negative를 줄인다.

B. PRECISION — 약한 증거로 과대확정하지 않는다
- seed 없는 잡담/한탄/트로프/작가얘기/플랫폼밈을 검색 단어만으로 작품 매칭하지 않는다.
  (비작품 의도에서 resolved 217건)
- 약한 anchor(medium/low/none)·약한 source_tier(community/llm_only)에 High+locked로 과잉 확정하지 않는다.
  (resolved의 36.6%가 sub-high anchor)
- reason이 evidence보다 세게 말하는 overclaim을 잡는다.

C. 두 축의 균형 (가장 중요)
- recall을 올리되 그 게이트가 precision을 깨지 않게 한다. "증거 충분도"를
  anchor 강도 + source tier + 교차 증거 수의 일반화 함수로 정의하고, 충분할 때만 확정(High+locked)을 허용한다.
- 증거가 약하면 unresolved 또는 Medium/unlocked로 남기는 것이 정답이다(틀린 확정보다 정직한 보류).

D. 이미지/멀티모달
- 이미지가 표지·제목 anchor를 직접 줄 때 VLM/OCR로 작품을 찾아낸다(recall).
  분위기·캐릭터·밈만으로는 확정하지 않는다(precision).

E. 일반화·검증가능성
- known-bad/high-risk를 hardcode가 아니라 gate/prompt contract/parser·schema/review artifact/test로 남긴다.
- 증거 수집·확정 판단을 runtime/result/review 단계에서 분리·검증 가능하게 한다.

## 공통 guardrail (핵심 목표 C를 코드에서 안전하게 구현하는 방식 — 3건 모두에 적용)
- **균형 원칙**: precision fix는 resolved title 보존 + `locked true→false`·`confidence High→Medium/Low` 한 단계
  강등만(recall 손실 0). recall fix는 명시 seed 게이트(anchor_strength≥medium/서사앵커/카탈로그 구조신호 2종)에만
  발화, anchor_strength=none 절대 제외, verifier promotion 게이트(in-post bridge/convergence 요구) 불변.
- **title 보존 회귀테스트**: precision fix(특히 lock 박탈)는 `locked`만 바꾸고 resolved title/후보가 그대로
  보존됨을 단위테스트로 증명한 뒤에만 배포. 미충족이면 그 fix는 drop.
- **hardcode 금지**: 특정 post id/제목/별칭/오타를 production code에 박지 마라. 증거 구조신호·앵커 출처·스코어·
  캘리브레이션 같은 일반 조건으로만.
- **과대주장 금지**: 3202는 순차 head slice다. 모집단 오류율/10만 approval/population approval로 환산 금지.
- **parallel**: effective_parallel = min(input_count, 16, healthy_endpoint_count). 재실행은 16이 정상,
  대표 부분집합이면 그 수에 맞춘다. `--reuse-shards-only`로 기존 WARP16/MCP 재사용.

## Task A — HANDOFF + 분석 산출물 git commit (먼저, 독립)
지금 `docs/devs/HANDOFF_3202_SLICE.md`, `docs/devs/GOAL_PROMPT_rank1-3.md`(이 파일)와 `out/_handoff_analysis/*`는 작업트리에만 있다.
1. main에서 작업 브랜치를 만든다(기본 브랜치 직접 커밋 금지).
2. **focused commit**: 위 goal/handoff 문서(+ gitignore 안 된 `out/_handoff_analysis/_synth.json`·버킷 표본)만
   스테이징한다. 기존에 이미 수정돼 있던 무관한 파일들을 이 커밋에 쓸어담지 마라.
3. 커밋 메시지에 "3202 슬라이스 인수 계약 + 검증된 개선 백로그 + rank1-3 goal"임을 적는다.
4. `git diff --check`(whitespace 0, CRLF는 기록만) 후 커밋.

## Task B — expert 체인 diff · v740/v741 포팅 판단 (rank 구현 전 선행)
primary vs worktree 3229의 `src/llm_batch/agentic_pipeline.py`, `src/llm_batch/experts/arbiter.py`,
`src/llm_batch/experts/verifier.py`, `expert_main.py`를 diff하고, 무엇을 primary로 포팅할지 결정한다.

이미 확인된 사실(검산 후 사용):
- rank1/3 타깃 `_has_title_abbrev_stability_signal`(agentic_pipeline), rank2 타깃 `_has_official_title_evidence`
  (agentic_pipeline+arbiter), `vf_hold_without_bridge`(arbiter)는 **양쪽 모두 존재** → rank1-3은 primary에서 바로 구현 가능.
- **primary에 없고 worktree에만 있는 것**: `over_resolution_review`·`_apply_over_resolution_demote`·
  `recommended_confidence`(worktree `expert_main.py`), `strong_bridge_count`(worktree `agentic_pipeline.py`+expert_main).

판단 산출물(`docs/devs/`에 1개 문서):
- 각 포팅 후보에 `port / reimplement / skip`을 근거와 함께 결정. 특히:
  - `strong_bridge_count`: rank1 게이트가 "약한 anchor에 High+locked"를 식별하는 입력으로 쓸 수 있다.
    primary 코어에 포팅/재계산할 가치가 있는지(없으면 rank1을 어떤 대체 신호로 게이트할지) 결정.
  - over_resolution advisory + opt-in demote: rank1의 arbiter **게이트**(승격 전 차단)와 역할이 겹치는
    post-hoc 안전망이다. 게이트로 충분한지, advisory를 보조로 둘지 결정.
- 결정은 "포팅했다"가 아니라 "rank1-3 구현에 무엇을 재사용/생성할지"로 끝맺는다. 실제 포팅 코드는 Task C에서 함께.

## Task C — 백로그 rank 1~3 구현 (근본원인 A·B 직격, 한 rank씩 사이클)
각 rank는 [구현 → 대표 부분집합 재실행 → before/after 신호 분포 → focused unittest(+title 보존 회귀) →
hardcode scan → git diff --check → focused commit → docs 기록] 한 사이클로 닫는다.

- **rank 1 (precision / 근본원인 B)**: alias/stability 복구(`_has_title_abbrev_stability_signal` 경로)의
  locked/confidence 승격 **앞에** "음수 정합 스코어 OR Verifier critical 반론" 차단 게이트 추가.
  대상 P1(94)·P2(51)·I1(217) 교집합. title 보존·한 단계 강등만. 근거 post 11697261, 11674702.
  기대: 음수스코어·critical 동반 resolved의 `locked` 감소·`confidence` High→Medium, resolved 카운트 보존.
- **rank 2 (recall / 근본원인 A)**: OCR 카탈로그 상세를 `ocr_catalog_detail` tier로 승격 —
  `_has_official_title_evidence`가 (작품명)+(작가)+(메트릭/시놉시스/플랫폼마커) 중 2종 공기 시 image OCR
  카탈로그도 official_title_evidence=true로 인정. 본문-OCR 주제 정합성 체크로 author_talk/release_meta 제외.
  대상 R2(100). 근거 post 11695625, 11645787, 11637724. 기대: ocr_explicit_title_unresolved 감소·resolved 증가(명시 seed에만).
- **rank 3 (precision / 근본원인 B)**: lock 부여를 'title_alias 단독 표면일치'에서 분리 — 본문 직앵커/OCR
  공식표제/공식 URL 중 1개 동반 시에만 `locked`. **title 보존 회귀테스트 선행, 미충족 시 drop.**
  대상 P2·P1. 근거 post 11674702, 11676327. 기대: 약-tier alias 단독 `locked` 감소, resolved 보존.

순서: rank1 → rank3(둘 다 근본원인 B, 상호작용 함께 검증) → rank2. rank1·rank3는 `locked`가 다운스트림
후보선택 입력(agentic_pipeline has_official_candidate·우열비교)임을 유의해 displace 회귀를 title 보존 테스트로 막는다.

## 검증 기준 (각 rank 사이클 강제)
- focused unittest 추가·실행 + precision fix의 title 보존 회귀테스트.
- 대표 부분집합 재실행으로 before/after 신호 분포 차이를 증거로 남김.
- known post/title/alias hardcode scan, `git diff --check`.
- 관련 goal-contract/review bundle 실행(있으면).

## 종료조건 (이 중 하나)
- Task A·B·C(rank1-3) 모두 닫힘(또는 drop 사유 기록).
- 정책/scope 사용자 결정이 필요한 hard blocker.
- 복구 불가 인프라 장애(endpoint 전멸 등).

## 기록
- HISTORY/CHECKLIST/VERIFICATION_RESULTS(before/after 신호 분포)/IMPROVEMENT_REGISTER 갱신.
- rank별 focused commit. HANDOFF 백로그에서 닫은 항목 표시.
- 완료/승인 표현 주의: rank 구현·재실행 검증을 semantic/population approval로 섞지 마라.
