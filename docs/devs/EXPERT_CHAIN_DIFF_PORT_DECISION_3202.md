# Expert 체인 diff · v740/v741 포팅 판단 — rank1-3 구현 선행 (Task B)

작성: 2026-06-09 / surface = **primary repo** / 참조 worktree = `C:\Users\kimjang\.codex\worktrees\3229\llm_novel_dc_coommunity_parser` (detached `f59d9f6`)

이 문서는 `docs/devs/GOAL_PROMPT_rank1-3.md` Task B의 산출물이다. primary vs worktree 3229의 expert 체인
(`src/llm_batch/agentic_pipeline.py`, `experts/arbiter.py`, `experts/verifier.py`, `expert_main.py`)을 핵심 심볼
단위로 diff하고, worktree에만 있는 v740/v741 메커니즘을 **port / reimplement / skip** 중 어떻게 처리할지 결정한다.
결론은 "포팅했다"가 아니라 **"rank1-3 구현에 무엇을 재사용/생성할지"**로 끝맺는다(실제 코드는 Task C).

## 1. 심볼 존재 매트릭스 (grep 출현 횟수, src/llm_batch + expert_main 기준)

| 심볼 | primary | worktree3229 | 정의 위치(primary) | rank 관련 |
|---|---|---|---|---|
| `_has_title_abbrev_stability_signal` | 49 | 52 | `agentic_pipeline.py:42232` | rank1·rank3 타깃 |
| `_has_official_title_evidence` | 135 | 135 | `arbiter.py:7480`, `agentic_pipeline.py:28197` | rank2 타깃 |
| `vf_hold_without_bridge` | 4 | 3 | `arbiter.py:1227` | rank2 가드(불변 유지) |
| `over_resolution_review` | **0** | 13 | (없음) — worktree `expert_main.py:546` | rank1 역할겹침 |
| `_apply_over_resolution_demote` | **0** | 6 | (없음) — worktree `expert_main.py:595` | rank1 역할겹침 |
| `recommended_confidence` | **0** | 3 | (없음) — worktree `expert_main.py:588` | over_resolution 부속 |
| `strong_bridge_count` | **0** | 9 | (없음) — worktree `agentic_pipeline.py:11996`, `expert_main.py:574/917` | rank1 게이트 입력 후보 |

→ HANDOFF 5절·Task B 전제 검산 완료: rank1/3·rank2 타깃 함수는 **양쪽 모두 존재** → primary에서 바로 구현 가능.
worktree-only 4종(over_resolution / demote / recommended_confidence / strong_bridge_count)은 primary에 **없음**.

## 2. worktree-only 메커니즘 분석

### 2.1 `over_resolution_review` + `_apply_over_resolution_demote` + `recommended_confidence` (worktree `expert_main.py:546-657`)
- **무엇인가:** 결과(serialized output) 층에서 동작하는 **non-mutating advisory**다. "High+locked + `strong_bridge_count==0`
  + (official/detail/official_search 강앵커 부재)" 모양을 일반 필드로 flag하고(`over_resolution_review_flag`),
  demote 권고(`recommended_confidence=Medium`, `recommended_clear_locked=true`)를 함께 싣는다.
- **어떻게 mutate하는가:** `_apply_over_resolution_demote`가 deepcopy한 output에 confidence→Medium cap·`locked`→false를
  적용. 단 `_apply_over_resolution_demote_enabled()`가 **opt-in(기본 OFF)** — CLI `--apply-over-resolution-demote`
  또는 env `LLM_APPLY_OVER_RESOLUTION_DEMOTE`로만 켜진다. 파이프라인 판정에 되먹임하지 않고 **공개 결과의 강도 표기만** 바꾼다.
- **입력 의존:** flag 판정의 핵심 입력이 `identity.evidence_instrumentation.alias_bridge.strong_bridge_count`다.

### 2.2 `strong_bridge_count` (worktree `agentic_pipeline.py:11996`)
- worktree는 alias bridge들의 강도 tally(`strength_counts`)를 집계해 `strong_bridge_count = int(strength_counts["Strong"])`를
  `evidence_instrumentation.alias_bridge`에 emit한다. over_resolution_review가 이 정수 0 여부로 "강한 alias 결속 부재"를 판정한다.
- **primary 현황:** primary에는 `evidence_instrumentation.alias_bridge.strong_bridge_count`가 **없다**. primary가 가진 것은
  `alias_bridge_pending`(부울 상태), `compound_alias_bridge`(kind 라벨), `generic_alias_bridge_only`(부울) — 모두 강도 tally가 아니다.
  즉 over_resolution_review를 그대로 포팅하려면 strong_bridge_count instrumentation 파이프라인을 **먼저 신설**해야 한다.

## 3. 포팅 결정 (port / reimplement / skip)

### 3.1 `over_resolution_review` advisory + opt-in demote → **SKIP (port 안 함). rank1 게이트로 INTENT만 reimplement.**
근거(역할 겹침 판단):
- 정밀도 의도(약한 결속 + 강앵커 부재인데 High+locked인 과대확정 차단)는 **동일**하다. 그러나 **배치가 다르다**:
  over_resolution은 emit **이후** 결과층에서 post-hoc로 잡는 advisory(+opt-in mutate)고, rank1은 emit **이전**
  파이프라인에서 lock/confidence가 **set되기 전에** 차단하는 게이트다.
- rank1 게이트가 엄격히 우월한 점: ① 과대확정을 애초에 emit하지 않음(advisory는 결과에 일단 실리고 사후 권고),
  ② opt-in 토글 불필요(게이트는 항상 작동, 단 title 보존·한 단계 강등으로 recall 무손실), ③ **strong_bridge_count
  instrumentation 신설 불필요**(2.2). 따라서 rank1-3 정밀도 목표 달성에 over_resolution 머신을 도입할 필요가 없다.
- 결정: worktree의 결과층 advisory/demote 머신은 **포팅하지 않는다.** 동일 정밀도 의도를 rank1 **in-pipeline 게이트**로
  reimplement한다. (over_resolution을 사람검토 큐용 read-only 텔레메트리로 추가하는 건 별개 백로그 R10~R18의 영역이고,
  하려면 strong_bridge_count를 먼저 신설해야 하므로 rank1-3 범위에서 제외한다.)

### 3.2 `strong_bridge_count` → **SKIP (포팅/재계산 안 함). 대체 신호로 게이트.**
- "rank1 게이트가 약한 anchor에 High+locked를 식별하는 입력으로 strong_bridge_count를 쓸 가치가 있는가"에 대한 답:
  **불필요.** primary는 lock이 실제로 set되는 chokepoint(`_resolve_batch_memory_alias_candidate`,
  `agentic_pipeline.py:36000-36019`, `locked=rank>=3`)에서 이미 더 직접적인 정밀도 신호에 접근 가능하다:
  - **음수 정합 신호:** decoder best_match의 `_title_anchor_conflict` / `_abbr_mismatch_downgrade` 부울 플래그
    (`agentic_pipeline.py:4537-4538, 7307-7308, 42489`에서 사용 중). 코드는 "음수 정합 스코어"를 raw 음수 정수가 아니라
    이 **명시적 conflict 플래그**로 표현한다(상위 scoring 함수 `_worklike_search_result_score_for_alias_title`·
    arbiter `_add` 누적은 둘 다 비음수/clamp[0,1]이라 chokepoint까지 음수가 전파되지 않음을 확인).
  - **Verifier critical 반론:** `verification_result.counter_arguments`의 `severity=="critical"`
    (기존 패턴 `_vf_has_critical_reject_j` = severity critical + action reject, `agentic_pipeline.py:4652-4657`).
- 결정: strong_bridge_count tally를 신설/포팅하지 않고, 위 **이미 존재하는 신호**로 rank1 게이트를 구성한다.
  (strong_bridge_count는 "Strong alias bridge 0개"라는 결속-부재 신호인데, primary의 conflict 플래그+critical 반론은
  "정합이 적극적으로 깨졌다"는 더 강한 정밀도 신호다. 결속 부재만으로 강등하면 정당 약칭까지 칠 위험이 있어 오히려 대체가 안전.)

### 3.3 `vf_hold_without_bridge` → **REUSE (이미 primary 존재, 불변 유지).**
- primary `arbiter.py:1227`에 존재. rank2(recall) guardrail은 "verifier promotion 게이트(in-post bridge/convergence 요구)
  불변"이므로 이 가드는 **건드리지 않는다.** rank2는 official_evidence 인정 범위만 넓히고 promotion 게이트는 그대로 통과시킨다.

### 3.4 rank1/3·rank2 타깃 함수 → **REUSE + 그 자리 확장.**
- `_has_title_abbrev_stability_signal`(agentic 42232): rank1/3가 게이트할 alias/stability 복구 경로의 신호. 함수 자체를
  바꾸지 않고(45개 호출부가 후보선택 입력으로 쓰므로 함수 return을 바꾸면 recall displace 위험), **lock이 set되는 chokepoint**
  (`_resolve_batch_memory_alias_candidate` 36000-36019, `_context_to_output` 적용부 9952-10046)에서 강등 게이트를 건다.
- `_has_official_title_evidence`(arbiter 7480 / agentic 28197): rank2가 OCR 카탈로그 상세를 official 증거로 인정하도록
  **확장**한다(둘 다 현재 image_evidence_catalog 미참조 → search/fetched URL만 봄).

## 4. rank1-3에 무엇을 재사용/생성할지 (Task C 인계)

**재사용(기존 primary):**
- lock chokepoint `_resolve_batch_memory_alias_candidate`(36000-36019) — rank1·rank3 공통 단일 lock 사이트.
- decoder conflict 플래그 `_title_anchor_conflict`·`_abbr_mismatch_downgrade` — rank1 음수 정합 신호.
- verifier `counter_arguments` severity critical 패턴(`_vf_has_critical_reject_j`) — rank1 critical 신호.
- `_confidence_label_from_rank`(11265): rank 3→High / 2→Medium → 강등을 "rank cap 2"로 표현하면 정확히 한 단계 + locked=false.
- `_has_official_title_evidence`·`_title_mentioned_in_post_main_context`·image_evidence_catalog 스키마
  (`explicit_work_title`·`explicit_author_name`·`work_cues`·`evidence_type`, builder `agentic_pipeline.py:11189-11262`) — rank2·rank3.
- `vf_hold_without_bridge`(arbiter 1227) — rank2에서 불변 유지.

**신설(generalized helper, hardcode-safe):**
- rank1: `_abbrev_alias_lock_block_signal(ctx, title, verification_result)` → 음수 정합(decoder conflict) OR verifier critical
  탐지 시 `blocked=True`. chokepoint에서 `rank=min(rank,2)`로 강등(locked T→F, conf High→Medium, title 보존).
- rank2: `_has_ocr_catalog_official_title_evidence(ctx, title)` → image_evidence_catalog에 (작품명)+(작가)+(메트릭/시놉시스/
  플랫폼마커) 중 2종 공기 + 본문-OCR 주제 정합 시 True. `_has_official_title_evidence`가 보조로 호출.
- rank3: lock 부여를 chokepoint에서 "본문 직앵커 / OCR 공식표제 / 공식 URL 중 1개 동반"으로 조건화하는 가드
  (`_lock_requires_hard_anchor` 류). title 보존 회귀테스트 선행, 미충족 시 drop.

**생성/포팅하지 않음:** `over_resolution_review`, `_apply_over_resolution_demote`, `recommended_confidence`,
`strong_bridge_count` instrumentation (3.1·3.2 근거). rank1-3은 위 재사용 신호만으로 충분하며 신규 스키마 없이 닫힌다.

## 5. 실행 메모
- worktree 3229는 detached HEAD(`f59d9f6`). 코드/테스트/재실행은 primary repo에서만 한다(HANDOFF 0절).
- primary 테스트 러너: `.venv312/Scripts/python.exe -m unittest tests.test_<name>` (venv에 pytest 미설치 확인).
