# 2026-07-14 LLM 파이프라인 라이브 런 종료 스냅샷과 보강 검토

## 최신 후속 결론 — 검색 폭주 P1 최종 검증

검색 폭주 P1은 코드·회귀·6행 실런 기준 `TARGETED_PASS`다. 다만 의미 품질은 런 간 변동과 VLM 오독이 남아 `NO-GO / REVIEW-LOCKED / full_scan_approval=false`를 유지한다.

- 구현:
  - typed `explicit_work_title`이 있으면 초기 검색 계획을 `정확 작품명(+작가)`와 `정확 작품명+노벨피아` 2개로 canonicalize한다.
  - 주입 뒤 생성된 일반/분할/플랫폼 확장을 pre-execute에서 제거하고, `_execute_searches` 내부 title-led 재주입 뒤에도 initial call에 한해 다시 2개로 clamp한다.
  - `title_role=unknown`은 no-work intent prune에서도 canonical 정확 검색 2개만 허용한다. 검색 허용과 public promotion 자격은 분리했다.
  - late OCR recall은 단순 부분문자열이 아니라 bare exact/title+author/title+노벨피아/site exact query가 실제 실행됐을 때만 생략한다.
  - 선택 작품 근거 없는 generic official URL은 live fetch 전에 차단하고, post/comment 직접 URL 및 정확 선택-title 검색 근거만 예외로 둔다.
- 회귀:
  - `tests.test_title_lead_search_inferred_guard`: `259 PASS`.
  - 실제 `_execute_searches` 통합 테스트에서 title-led 재주입으로 5개가 된 요청이 `5→2`, `search_fn` 호출 2개로 고정됐다.
  - BatchContext/publication `111 PASS`, publication/retrieval 인접 `54 PASS`, 관련 `py_compile` PASS.
- 최종 실런:
  - run id `20260714_222518_895497`, 결과 `out/expert_result_20260714_promotion_slang_search_p1_final_targeted.json`.
  - requested/effective parallel `16/6`, dashboard `standalone_forward`, VLM/OCR `READY`.
  - completed/flushed/pending/failed `6/6/0/0`, `next_save_idx=7`, runtime gate `GO`, exit `0`.
  - BatchContext는 inline off, publish-only, input-ordered drain이며 최종 pending `0`; `same_wave_observation_deterministic=false`는 P2로 남는다.
- `11716480` 검색 계측:
  - inject `4→2`, pre-execute `12→2`; 실제 `🔍 검` 로그 2건만 실행됐다.
  - manifest `queries_issued`는 retry/degraded 집계를 포함해 `26→4`로 감소했다. raw OCR tag/UI 검색 `0`, token-split 검색 `0`, URL fetch `0`, generic heretic live fetch `0`이다.
  - 행 wall time은 `679,426ms→432,840ms`; 전체 런은 `680.8s→434.2s`로 줄었다. 최종 런은 VLM 첫 응답 대기가 길어 검색 감소량과 전체 시간 감소량은 동일하지 않다.
  - 실런 뒤 Sol 감사에서 발견한 `_execute_searches` 내부 재주입 edge는 위 5→2 통합 회귀로 닫았다. 이 edge는 해당 실런 W2에서는 발생하지 않아 실제 W2 호출은 이미 2개였다.
- 현실 차이:
  - 이번 VLM typed title은 `꿇은`을 `끓은`으로 오독해 exact 2개도 오타 기반으로 실행됐다. raw OCR/심의에서 올바른 후보를 회복했지만 official URL 근거가 없어 최종 `HOLD`, title `null`로 닫혔다.
  - `11718099`은 세 런에서 `HOLD→PUBLISH→HOLD`, `11716475`는 `PUBLISH→HOLD→HOLD`, `11716448`은 `HOLD→PUBLISH→PUBLISH`로 변동했다. fail-close는 작동하지만 재현 가능한 의미 품질은 아직 승인 수준이 아니다.
  - 안정 양성인 `11718077`, `11714907`과 `아생갤` 양성 경로는 보존됐다. `아생갤`은 `아카데미 생존 갤러리`로 처리됐다.
- slang DB:
  - 중앙 SHA256은 `a8c3fb9b083f6914e24bbede5adbbce73372f834dee4271611eefaaeeebcf10a`로 불변이다.
  - 최종 work DB도 `261 title / 87 slang / 173 pending / 28 conflict`, 신규 title/term `0`; 기존 `즉사기 들고 무림에 떨어지다`, `아카데미 생존 갤러리` 관측만 달라졌다.
  - manifest의 work artifact `promotion_ready=true`는 의미 승인과 다르다. `semantic_approval=NOT_EVALUATED`, `publication_slang_db_writeback_complete=false`이므로 중앙 승격은 수행하지 않았다.
- 다음 게이트:
  - VLM typed-title 오독 변형 보존, `11716475` recall loss, `11718099` OCR/title variance를 먼저 줄인다.
  - RetrievalState live wiring과 durable receipt 증거를 확인한 뒤에만 200행 canary를 시작한다. 현재 200행은 `NOT_RUN`이다.

## 결론

Run `20260714_160355_054970`은 20:23:54 KST에 partial 상태로 종료됐다. 완료한 worker 결과 `474`건 중 ordered prefix `466`건만 result에 flush됐고 `8`건은 pending snapshot에 보존됐다. 실행 실패는 `0`이지만 입력 `104,502`건 대비 완주가 아니므로 파이프라인 개선 효과와 의미 품질 승인은 `NO-GO / REVIEW-LOCKED`다.

- 실행 상태: `STOPPED_PARTIAL / RUNTIME_NO_GO`
- bounded 판정: `CONTINUE_WITH_BOUNDED_REPAIR`
- 104,502행 full run: `STOPPED_WITH_CHECKPOINT`; 새 계약과 섞어 resume하지 않음
- runtime completion: `NO_GO`, `large_run_complete=false`
- semantic quality: `REVIEW-LOCKED`
- Architecture V2 effect: `NOT_ESTIMABLE`
- production approval: `full_scan_approval=false`

핵심 이유는 다음 세 가지다.

1. 최종 저장 상태는 completed/flushed/pending/failed `474/466/8/0`, `large_run_complete=false`, `shutdown_pending_flush_gap`이다.
2. 17:47 KST canonical prefix에서 검색 상태가 기록된 flushed row `162`개 중 `SEARCH_DEGRADED=115`(`71.0%`)였고, 후속 진행에서도 검색 저하가 계속 관찰됐다.
3. Architecture V2의 DecisionLedger V2 shadow, decision-call measurement, early routing은 모두 OFF이고 typed `RetrievalState` fail-close도 live row에 연결되지 않았다.

따라서 이 명령은 일부 안전·복구 경계를 실제로 통과했지만, 완주한 full scan이나 Architecture V2의 실제 효과를 검증하는 fresh BEFORE/AFTER 또는 measurement run이 아니다.

## 범위와 증거 시점

| 항목 | 값 | 근거 |
| --- | --- | --- |
| 입력 | `tests/inputs/test01.jsonl`, unique post `104,502` | manifest/input loader |
| 병렬도 | requested/effective/active `16/16/16` | manifest + dashboard |
| dashboard | `standalone_forward`, `http://127.0.0.1:8080` | `/api/health`, `/api/status`, browser snapshot |
| VLM/OCR | `true/true`, image post `55,259` | manifest |
| 17:47 저장 상태 | completed/flushed/pending/failed `200/186/14/0` | `tools.audit_expert_run_health` |
| 저장 정합성 | checkpoint/result/pending/journal 일치, duplicate `0` | canonical audit |
| 17:50 진행 상태 | done/current/total `209/225/104,502` | dashboard `/api/status` |
| 17:50 비용 상태 | token `22,804,719`, ETA `36.6일` | dashboard `/api/status` |

결과는 입력 선두의 ordered prefix이며 random sampling metadata가 없다. 현재 prefix는 오류 유형 탐지에는 쓸 수 있지만 random baseline 오류율이나 전체 품질 추정에는 사용할 수 없다.

### 18:56–18:57 KST 최신 추적

- canonical audit: completed/flushed/pending/failed `331/316/15/0`
- checkpoint/result/pending/journal 및 `completed-flushed=pending` 정합 검사: 모두 `true`
- ordered frontier: `global_idx=317` 처리 대기, `319+` 일부 완료 상태로 `IN_PROGRESS / ordered_flush_gap_in_progress`
- dashboard: done/current `331/347`, active `16`, 평균 `31.3초/행`(약 `1.92행/분`), ETA 약 `37.7일`, token `36,288,405`
- row search health: `SEARCH_DEGRADED 197/275`(`71.6%`), `ok 67`, recovered `11`, unrecovered degraded query `733`
- 새 terminal processing error: `0`; dashboard health `ok=true`, process 진행 중

런타임은 살아 있고 저장 정합도 유지되지만 검색 저하·비용·의미 blocker가 개선되지 않아 `STOP_RECOMMENDED / CONTINUE_WITH_BOUNDED_REPAIR` 판정은 유지한다.

### 19:26 KST 최신 생존 확인

- manifest completed/flushed/pending/failed `379/356/23/0`, `large_run_complete=false`
- `runtime_completion_gate=NO_GO`: `COMPLETED_COUNT_MISMATCH`, `PENDING_ROWS`, `TERMINAL_ARTIFACTS_NOT_FINALIZED`
- requested/effective parallel `16/16`, expert process와 standalone dashboard process 모두 실행 중
- dashboard `/api/health` 200, `ok=true`
- 중앙 Slang DB SHA-256 `a8c3fb9b...cf10a`는 manifest input hash와 같아 미변경
- work Slang DB는 동시 기록 중이므로 순간 count/delta는 race 가능하며 계속 `QUARANTINE`

이는 당시 진행 중 snapshot이지 완료·승인 근거가 아니다.

### 20:40 KST 종료 상태 확정

- expert launcher/worker process는 모두 종료됐고 standalone dashboard만 유지된다. dashboard `/`와 `/api/health`는 각각 HTTP `200`, `/health`는 지원하지 않아 `404`다.
- manifest/checkpoint/result/pending은 completed/flushed/pending/failed `474/466/8/0`, `next_save_idx=467`, `partial_flush_gap=true`, `ordered_flush_blocked=true`다.
- pending global index는 `468, 469, 470, 473, 476, 478, 480, 481`이며 manifest 종료 사유는 `shutdown_pending_flush_gap`이다.
- 입력은 `104,502`건이고 `large_run_runtime_complete=false`, `large_run_complete=false`, `runtime_completion_gate=NO_GO`다.
- 중앙 Slang DB는 `261 title / 87 slang / 173 pending / 28 conflict`, SHA-256 `a8c3fb9b...cf10a`로 시작 snapshot과 동일하다.
- patch 전 process가 남긴 work DB 최종 안정 snapshot은 `279 title / 96 slang / 186 pending / 26 conflict`, SHA-256 `2a7c43a1...7333b`다. `어려운애기`, `스미스든`, `초보자` 등 추가 오염 후보가 있어 전체를 계속 `QUARANTINE`한다.

종료 신호 자체의 직접 원인은 main log에 명시되지 않았다. 따라서 `정상 완주`, `crash`, `사용자 중단` 중 하나로 임의 확정하지 않고 `STOPPED_PARTIAL / CAUSE_NOT_RECORDED`로 기록한다. 완료 subset과 pending은 보존됐지만, patch 전/후 `promotion_contract_v2` 의미를 한 런에 섞지 않기 위해 이 run을 새 코드로 resume하지 않는다.

## 실제로 적용된 경로

- `--parallel 16` 요청과 effective parallel `16`이 실제 worker 16개로 실행된다.
- VLM/OCR가 켜지고 image row에 VLM/OCR 흔적이 기록된다.
- typed `PublishContract`와 candidate audit가 final row에 적용된다.
- identical duplicate post는 첫 행 기준으로 멱등 처리되고 conflicting duplicate는 사전 차단된다.
- publication journal, checkpoint, pending snapshot, ordered flush가 동작한다.
- Slang DB는 중앙 DB 직접 변경이 아니라 attempt-local `_slang_db_work.json`에 지연 기록된다.
- dashboard forwarding과 live status/result/log 조회가 동작한다.

## 적용되지 않았거나 증명되지 않은 경로

- `decision_ledger_v2_shadow_config.enabled=false`
- `decision_call_measurement.mode=OFF`, `actual_kpi_status=NOT_ESTIMABLE`
- `early_route_measurement.enabled=false`, `gate=NOT_ENABLED`
- typed `RetrievalState`는 정적 gate에는 존재하지만 live pipeline row에 연결되지 않음
- source-backed DEV/CAL/FROZEN과 동일 RunSpec fresh BEFORE/AFTER 부재
- Slang central promotion/writeback/display 미완료

Architecture V2 통합 완료는 사실이지만, 현재 명령으로 그 효과가 실측됐다고 표현하면 안 된다.

## 런타임 건강과 검색 품질

프로세스·checkpoint 관점에서는 즉시 crash나 deadlock 증거가 없다.

- `Traceback=0`, `NameError=0`
- terminal row failure `0`
- main log의 recoverable LLM timeout/connect error는 retry 뒤 진행됨
- 16개 shard의 health/ready는 정상
- ordered flush gap은 현재 frontier row 처리 대기와 일치

반면 검색 품질은 별도 blocker다.

| search status | 행 수 | 비율(분모 162) |
| --- | ---: | ---: |
| `SEARCH_DEGRADED` | 115 | 71.0% |
| `ok` | 41 | 25.3% |
| `SEARCH_DEGRADED_RECOVERED` | 6 | 3.7% |

살아 있는 shard와 저하된 row-level 검색은 동시에 참이다. `16/16 OK`, queue 진행, dashboard 정상만으로 검색 또는 의미 품질을 승인하지 않는다.

## 발견한 결함과 위험

### P0 — context-only/unresolved 공개 승격

`post_id=11716475`는 다음 상태가 동시에 기록됐다.

- `title_resolution_state=context_only`
- `work_resolution=unresolved`
- `search_health=SEARCH_DEGRADED`
- `official_url_evidence_missing`
- `competing_candidate_present`
- `promotion_decision=publish`
- public `official_title=일편독심[一片毒心]`

검색 exact probe가 작품 페이지를 찾았더라도 원문은 문장형 표면이고 direct work anchor가 약하다. no-work/context-only 단조성 gate를 우회한 `reason_decision_contradiction`으로 보고 `REPROCESS`한다.

최종 checkpoint의 publish row `76`건을 전수 재계산하니 같은 모순은 총 `5`건이었다.

| post_id | 원문 제목 | 잘못 공개된 후보 |
| --- | --- | --- |
| `11716475` | `고능아는 일편독심 망카데미같은건가?` | `일편독심[一片毒心]` |
| `11711635` | `프로모션이 먼데` | `프로모션 ~폰은 TS하면 강해져~` |
| `11708450` | `뭣 갑송이 악살싶 강의씬이 표절이었다고` | `악당은 살고 싶다` |
| `11706839` | `여헌터를 따먹으면 주인공이 강해짐 재밌음?` | `여헌터를 따먹으면 주인공이 강해짐` |
| `11705259` | `아생갤 묵힌거푸는데 재밌다롱` | `아카데미 생존 갤러리` |

다섯 행 모두 `scope=current_work`, `title_resolution_state=context_only`, `work_resolution=unresolved`, `publish_allowed=true`였다. shared gate가 current-work scope를 resolution state보다 우선해 잘못 게시한 일반 계약 결함이다.

`src/llm_batch/promotion_gate.py`는 빈 legacy state만 호환하고, 명시적 title state는 `resolved/direct_resolved`, work state는 `resolved`만 게시하도록 fail-close했다. 나머지 현재 enum과 미래 HOLD state는 각각 `title_resolution_state_not_publishable`, `work_resolution_not_publishable`로 `candidate_only` 보존한다. frozen checkpoint 무기록 투영에서 모순 `5/5`가 차단됐고 `resolved/resolved` 양성 대조 `10/10`은 게시를 유지했다. canonical contract는 차단 뒤 title state를 `unresolved_matchable`로 정규화하고 두 blocker를 ledger까지 동일하게 미러링한다.

집중 계약 `101 PASS`, publication/retrieval 인접 회귀 `108 PASS`, 독립 최신 diff 재검토 `143 PASS`다. 상시 회귀 `29`건 중 `5 ERROR / 1 SKIP`은 이번 patch assertion이 아니라 로컬 Codex executable SHA와 pinned trust anchor 불일치로 발생했다.

fresh targeted run `20260714_204406_840036`은 requested/effective `16/6`, dashboard ON, VLM/OCR required, Slang DB attempt-local로 `6/6/0/0`, runtime gate `GO`, `large_run_complete=true`, exit `0`으로 끝났다.

| post_id | fresh public 결과 | 판정 |
| --- | --- | --- |
| `11716475` | `지력 99 고능아인 척하기`, resolved/resolved, publish | 과거 wrong-work `일편독심` 교정 |
| `11718099` | public null, unresolved/unresolved, candidate-only | OCR 표지 충돌 차단 |
| `11716480` | public null, unresolved/multi_work, candidate-only | multi-work/OCR 경쟁 차단 |
| `11716448` | public null, `아카데미 생존 갤러리` 후보 보존 | `아생갤`을 현실 갤러리명으로 폐기하지 않고 HOLD |
| `11718077` | `즉사기 들고 무림에 떨어지다`, resolved/resolved, publish | positive 유지 |
| `11714907` | `아카데미 생존 갤러리`, resolved/resolved, publish | positive 유지 |

publication convergence는 `GO / violation 0`이지만, 이 호출은 durable receipt sidecar를 별도 공급하지 않아 exact-once를 `NOT_PROVABLE`로 남겼다. Slang work DB에는 중앙 대비 신규 term이 `0`이고, 기존 검증 alias `즉사무림`, `아생갤`만 관측됐다. 일반어 `고능아`는 `store=false`라 DB mutation이 없었다.

다만 runtime summary는 검색 요청 `80`, 실제 검색 `73`, 총 `680.8초`였다. `11716480` 단일 행이 `queries=26`, degraded `25`, unrecovered `15`로 다수의 무관 official URL을 직렬 검증했다. P0 public leak는 막았지만 비용·검색 thrash는 별도 P1 blocker다. dashboard forwarder도 timeout 3회 뒤 drop/retry 모드로 전환했으나 종료 전 `/`, `/api/health`, `/api/status`는 다시 HTTP `200`이었다. targeted 통과만으로 200행 canary나 전체 승인을 자동 개방하지 않는다.

### P0 — Slang DB 일반명사·비별칭 오염

18:30 KST work artifact 감사에서 중앙 대비 신규 term `14`개 중 명확한 오염이 `8`개(`57.1%`)였다. `지력 → 옥수수`는 clean `slang`, `네이버`, `보내`, `세상`, `있었`, `연참`, `쿠크루`, `비처녀노`는 `pending`으로 들어갔다. 18:58 KST에는 `나누는게 → 한달마다 바뀌는 아내`, `전쟁 → 로판을 망친 매국노가 되었다`가 추가돼 work delta가 `17`개로 늘었다. 원인은 `primary_work/title_candidate`의 High/Medium confidence를 alias relation 근거로 오인한 쓰기 경계와 `store=false` 우회 가능성이다.

첫 보강 뒤에도 구조 점수만으로 `페이트 → 페이 포인트`, `로판이나`, `니생`, `부분부분`, `유니콘들`이 observation 후보가 되는 잔여 경로가 확인됐다. 최종 경계는 구조 점수를 쓰기/seed 자격에서 제거하고 strict `slang_insight`, verified `confirmed_alias`, 실제 registry mapping까지 재검증한 exact pair 중 하나만 허용한다. reference 역할은 CandidateLedger에만 보존하고 Slang DB mutation으로 번역하지 않는다. 고정 checkpoint prefix `419`행 actual-manager replay는 `36 observation / slang 32 / pending 4 / error 0`, 중앙 대비 신규 term `6`이며 확인된 오염 표면은 `0`이다. 중앙 slang `87`개는 삭제 없이 `45 허용 / 42 재검증 격리`다. 현재 프로세스는 패치 전 코드이므로 work artifact는 계속 `NO-GO / QUARANTINE`, 중앙 승격은 `BLOCKED`다.

상세: [2026-07-14 Slang DB 오염 감사와 fail-close 보강](SLANG_DB_POLLUTION_AUDIT_KO_20260714.md)

### P1 — RetrievalState live wiring 부재

정적 `RetrievalState` fail-close 계약은 있지만 `expert_main.py`/`agentic_pipeline.py` live row 경로가 이를 구성하지 않는다. 현재 `search_health`는 직렬화되지만 degraded retrieval이 typed publication gate를 자동으로 닫지는 않는다.

### P1 — BatchContextMemory 선행 학습 보강

기존에는 worker가 final audit/WAL commit 전에 BatchContextMemory를 학습해, 후단 HOLD/REJECT alias가 병렬 후속 행에 전파될 수 있었다. `expert_main`은 이제 pipeline inline 학습을 끄고, 신규 canonical WAL `PUBLISH`이면서 `publish_allowed=true`인 행만 학습한다. `HOLD`, `ERROR_HOLD`, candidate-only, 같은 런의 중복 commit은 학습하지 않는다. 재시작 replay와 신규 commit은 input index 연속 buffer를 함께 사용하므로 최종 학습 적용 순서도 동일하다.

decoder alias·검증 작가·확인 캐릭터는 `batch_context_learning_envelope_v1`의 제한된 allowlist로 WAL에 남겨 replay recall을 보존한다. raw prompt/snippet/fetched page/namu 본문은 저장하지 않고, envelope의 개수·문자 길이와 assignment를 재검증한다. 기본 `AgenticPipeline` inline 학습도 명시적 opt-in으로 바꿔 publication 전 mutation escape를 닫았다. manifest에는 next index, pending count/index, ordered-drain 여부와 same-wave nondeterminism을 기록해 partial shutdown의 보류 학습도 숨기지 않는다. 다만 같은 `--parallel 16` wave에서 이미 실행 중인 worker가 어느 시점의 shared context를 관측하는지는 완전한 deterministic batch epoch가 아니며, namu raw cache replay도 의도적으로 제외했다. 따라서 이 P1은 `POST_COMMIT_ORDERED_PASS / PARALLEL_OBSERVATION_P2_REMAINS`이고 200행 의미 승인을 열지 않는다.

### P1 — model/cap 계보 불일치

실제 model은 `bg-digitalservices/Gemma-4-26B-A4B-it-NVFP4`지만 `model_parallel_cap_model`은 `bg-digitalservices/Gemma-4-E4B-it-NVFP4`로 기록된다. 현재 `--parallel 16`은 cap 36 아래라 worker 수는 바뀌지 않았지만 config hash와 audit lineage가 오염된다.

### P1 — dashboard validation fail-open

현재 run의 dashboard는 정상이다. 다만 code path는 dashboard 시작 실패를 잡고 `dashboard_mode=unavailable`로 계속 처리할 수 있어 repository의 validation dashboard 필수 계약과 다르다.

### P1 — 비용·처리량

17:39 KST 결과 prefix `163`행의 `DecisionCostTrace` 기준 평균 token은 약 `106.6k/row`, median `102.8k`, p95 `188.8k`였다. dashboard 17:50 누적값도 `22.8M token/209 completions` 규모다. 현 상태로 104,502행을 계속하면 검증 목표 대비 비용과 시간이 비현실적이다.

### P2 — VLM/OCR·multi-work·아생갤

- `11718099`: OCR `불어먹을 환생`과 final `빌어먹을 환생` 충돌 — `REPROCESS`
- `11716480`: image multi-work ambiguity와 degraded search — `REPROCESS`
- `11716448`: `아생갤`을 실제 DC 갤러리명으로만 닫지 않고 작품 약어 가능성과 경쟁 작품 근거를 함께 보존 — `HOLD/REPROCESS`
- positive controls: `11718077`, `11714907`은 direct/official evidence가 강하지만 전체 gate 승인을 의미하지 않음

### Slang DB 경계

work artifact는 중앙 DB보다 신규 title/term을 더 보유하지만 manifest는 `work_artifact_complete=false`, `promotion_ready=false`, `writeback_complete=false`다. `11716449`의 `케문제`는 extracted/work-artifact 상태와 central persistence가 다르므로 `SLANG_DB_REVIEW` 대상이다. 이번 work artifact 전체는 일반명사 오염 때문에 `NO-GO / QUARANTINE`이며, 패치 후에도 사람이 승인한 별도 proposal 전에는 central promotion을 열지 않는다. extraction, work persistence, central promotion, dashboard display를 같은 상태로 취급하지 않는다.

## Bounded convergence 판정

현재 목표는 `BLOCKED_HANDOFF`나 `COMPLETE_SAFE_TERMINAL`이 아니다. repository 내부 generalizable fix가 남아 있으므로 `CONTINUE_WITH_BOUNDED_REPAIR`다. 104,502행 full run은 이미 partial 종료됐고, 구계약 산출물과 새 계약을 혼합하지 않도록 해당 attempt는 보존·격리한다.

권고 실행 예산은 다음으로 제한한다.

1. 종료된 full run의 checkpoint/result/pending/journal과 work Slang DB를 불변 증거로 보존하고 중앙 승격·혼합 resume를 금지한다.
2. 완료한 Slang DB write/seed fail-close와 resolution-state publication fail-close를 fresh process에서 검증한다. BatchContext는 post-commit PUBLISH-only·input-order replay까지 보강했고, same-wave 관측 결정성은 P2로 남긴다. model/cap binding, RetrievalState live wiring, search-thrash, dashboard validation fail-close는 별도 bounded code pass다.
3. known-bad `11716475`, `11718099`, `11716480`, `11716448`과 positive control `11718077`, `11714907`의 fresh targeted run `20260714_204406_840036`을 판독한다.
4. `--parallel 16`, dashboard ON, `--vlm on --ocr on --require-vlm-ocr-for-images`를 사용한다.
5. current paired-validation 계약에는 Slang DB를 OFF 또는 read-only snapshot으로 고정한다.
6. targeted 통과 뒤에만 200행 canary를 실행한다.
7. 그 뒤 random baseline `1,000+`와 P0/P1 high-risk expansion을 별도 산출물·별도 오류율로 검토한다.
8. 모든 gate 통과 뒤 별도 새 run으로 대형 검증을 검토한다. 기존 checkpoint는 계약 의미가 달라졌으므로 동일 attempt resume의 의미 품질 근거로 사용하지 않고, 104,502행을 처음부터 자동 재실행하지도 않는다.

## 검증

- browser dashboard snapshot: title/worker/result rows 확인, page console의 Tailwind CDN production warning 외 치명 console error 없음
- `tools.audit_expert_run_health.build_audit(...)`: `IN_PROGRESS`, ordered flush 정합, search gate `REVIEW`
- static compile: `expert_main.py`, batch context, Slang DB, candidate audit, promotion gate PASS
- focused tests:
  - `tests.test_slang_db`: `31 PASS`
  - `tests.test_arbiter_curated_alias_guard`: `30 PASS`
  - `tests.test_expert_main_input_loader`: `58 PASS`
  - `tests.test_completed_source_candidate_audit`: `4 PASS`
  - `tests.test_retrieval_state_fail_close`: `10 PASS`
  - `tests.test_publication_contract_convergence_audit`: `43 PASS`
- resolution-state publication 보강:
  - `tests.test_promotion_gate_contract`: `101 PASS`
  - publication/retrieval 인접 5개 모듈: `108 PASS`
  - frozen checkpoint projection: contradictory publish `5/5` 차단, resolved positive `10/10` 유지
  - 독립 최신 diff 재검토: gate+convergence `143/143 PASS`, code slice `GO`
- always-on regression: `29`건 중 `5 ERROR / 1 SKIP`; 다섯 오류는 native Codex executable SHA가 pinned trust anchor와 달라 발생했으며 이번 publication patch의 기능 실패로 합산하지 않는다.
- BatchContext post-commit 보강:
  - `tests.test_batch_context tests.test_publication_decision_commit tests.test_expert_main_input_loader`: `111 PASS`
  - publication/retrieval 인접 3개 모듈(`PYTHONPATH=src`): `54 PASS`
  - `py_compile`: `expert_main.py`, `batch_context.py`, `models.py`, `agentic_pipeline.py` PASS
  - frozen publication exact-once harness `5 ERROR`는 수정 전 `promotion_gate` SHA를 고정한 parent RunSpec mismatch이며 기능 PASS에 포함하지 않는다.
- Data Analytics MCP report: `validate_artifact ok=true`, report render `ok=true`
- Slang DB exact-pair replay: 고정 checkpoint prefix `419`행, strict observation `36`, 중앙 대비 신규 term `6`; 중앙 seed `87`개 중 `45` 허용·`42` 격리

## 증거 경로

- `out/expert_result_20260714_160355_054970_manifest.json`
- `out/expert_result_20260714_160355_054970_checkpoint.jsonl`
- `out/expert_result_20260714_160355_054970.json`
- `out/expert_result_20260714_160355_054970_pending_snapshot.json`
- `out/expert_result_20260714_160355_054970_attempt_claim.json`
- `out/expert_result_20260714_160355_054970_slang_db_work.json`
- `out/publication_commit_journals/ff66a3fdfb3788dac91a53d5eb51412fd8c04379efc95acc025aaf64a3ca065e.jsonl`
- `logs/expert_run_20260714_160355_054970.log`
- `logs/expert_run_20260714_160355_054970_W0.log` … `W15.log`

이 보고서는 종료된 partial full-run snapshot과 후속 보강 상태를 함께 기록한다. fresh targeted/canary 결과가 추가돼도 `NO-GO / REVIEW-LOCKED / full_scan_approval=false`는 각 gate가 통과하기 전까지 유지한다.
