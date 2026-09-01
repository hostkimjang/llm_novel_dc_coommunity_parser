# 동결 2,712행 Recovery Sidecar 개선 구현·검증 보고서

## 결론

기존 공개 정답을 바꾸지 않는 범위의 개선은 구현·검증됐다. 공개 결과를 직접 고치는 대신, 검증된 publication WAL 뒤에 별도 append-only `AUDIT_ONLY/public_apply=false` sidecar를 붙여 direct OCR 기반 제목 후보를 review 대상으로만 회수한다.

- 기존 공개 결과 보존: `GO`
- sidecar 구조·provenance·멱등성: `GO`
- 동결 2,712행 review 후보 reconciliation: `GO`
- 실제 fresh 반복 의미 품질: `RUN / SEMANTIC NO-GO`
- search health: `NO-GO` (`68/68 SEARCH_DEGRADED`)
- 자동 title publish activation: `NO-GO`
- 전체 런 승인: `full_scan_approval=false`

즉, 이번 단계에서 해결된 것은 “정답을 흔들지 않고 개선 후보를 안전하게 포착·감사하는 구조”다. 공개 title 정답률이 개선됐다고 결론 내릴 단계는 아니다.

## 개선 전과 현재 비교

| 항목 | 개선 전 | 현재 | 판정 |
| --- | ---: | ---: | --- |
| 공개 결과와 분리된 recovery 원장 | 없음 | append-only sidecar 1개 | 해결 |
| direct OCR review 후보 event | 별도 provenance 없음 | `68` events / `67` post | review 포착 개선 |
| `FN_TITLE_MISSING` 후보 포착 | 자동 비교 불가 | `48/339` events, `14.16%` | shadow 개선 |
| PASS 정상군 추가 review | 기준 없음 | `0/230` | 비침범 확인 |
| 공개 projection 불일치 | 변경 금지 기준 | `0/2,712` | hard gate 통과 |
| 정상→비정상 계약 회귀 | 변경 금지 기준 | `0/2,712` | hard gate 통과 |
| fingerprint/reason mismatch | 변경 금지 기준 | `0/0` | hard gate 통과 |
| proposal provenance coverage | 없음 | `68/68`, `100%` | 해결 |
| 동일 입력 재실행 신규 event | 중복 방지 계약 없음 | `created 0 / replayed 68` | 해결 |
| review event의 공개 적용 | 허용하지 않음 | `public_apply=true 0` | 보존 |
| 검색 정상성 | 저하 관측 | `68/68 SEARCH_DEGRADED` | 미해결 |
| 정답 title 자동 회복 | 미승인 | 미승인 | 미해결 |

### 해석 주의

동결 persisted replay의 adjudicated unsafe publish는 저장·재계산 모두 `33`으로 동일하다. 이것은 이번 sidecar가 기존 잘못된 공개 결과 33건을 고쳤다는 뜻이 아니라, 공개 projection을 바꾸지 않았다는 뜻이다. 사전 감사의 “최종 개입 필요 35건”과 replay의 “adjudicated unsafe 33건”은 분모·판정 정의가 다른 지표이므로 합치지 않는다.

## 어떤 문제군을 포착했나

sidecar event 분모는 `68`, 고유 post 분모는 `67`이다. 한 post에서 서로 다른 OCR 제목 두 개가 보존돼 event가 1개 더 많다.

| 동결 verdict | 전체 행 | sidecar event | event/전체 | 의미 |
| --- | ---: | ---: | ---: | --- |
| `FN_TITLE_MISSING` | 339 | 48 | 14.16% | 주 목표군에 가장 많이 집중 |
| `DASHBOARD_TITLE_MISMATCH` | 7 | 1 | 14.29% | 작은 분모, 자동 판단 금지 |
| `WRONG_WORK` | 36 | 3 | 8.33% | 잘못된 작품 위험이므로 review 유지 |
| `EVIDENCE_CONFLICT` | 25 | 1 | 4.00% | conflict 보존 |
| `FP_NONNOVEL` | 72 | 1 | 1.39% | false-review 위험 |
| `MULTIWORK_HOLD_CORRECT` | 91 | 1 | 1.10% | multi-title 자동 승격 금지 |
| `CONTEXT_ONLY_CORRECT` | 719 | 6 | 0.83% | 정상군 추가 review |
| `NOISE_CORRECT` | 891 | 6 | 0.67% | 정상군 추가 review |
| `EVIDENCE_INSUFFICIENT` | 302 | 1 | 0.33% | 근거 부족 상태 유지 |
| `PASS` | 230 | 0 | 0.00% | 기존 정상 공개 정답 비침범 |

dashboard action 기준 event는 `CORRECT 51`, `HOLD 3`, `NOT_APPLICABLE 12`, `REMOVE 2`, `KEEP 0`이다. `NOT_APPLICABLE` 12 events는 11개 고유 post이며 false-review 비용이 남아 있음을 보여준다. 따라서 현재 결과를 “68건 회복 성공”으로 부르면 안 된다.

## 구현한 구조

### 1. 공개 결과 밖의 append-only recovery 원장

[`src/llm_batch/ledger/recovery_activation.py`](../../src/llm_batch/ledger/recovery_activation.py)는 final publication receipt/result를 다시 검증한 뒤 review proposal만 별도 journal에 기록한다.

- result JSON, `PickvelIdentity`, `candidate_ledger`, `publish_ledger`, checkpoint, base publication WAL을 수정하지 않는다.
- proposal은 public writer field를 가질 수 없다.
- event는 `AUDIT_ONLY`, `public_apply=false`로 고정한다.
- publication scope, input index, post ID, decision/commit/result/stable-result/public-projection/fingerprint를 exact 결속한다.
- raw capability와 HMAC key는 result·WAL·checkpoint·journal·manifest에 저장하지 않는다.

### 2. 동시성·손상 fail-close

- scope-local key는 lock 아래 `0600` temp에 전부 쓰고 `fsync → atomic replace → directory fsync`한다.
- 16개 동시 creator/registry에서도 key 1개, proposal event 1개만 남는다.
- newline 없는 최종 torn frame만 completed prefix 검증 뒤 복구한다.
- newline이 끝난 invalid frame과 middle corruption은 자동 수리하지 않고 실패한다.
- sidecar I/O 실패는 공개 base WAL을 되돌리거나 변조하지 않고 sidecar 상태만 `NO_GO`로 만든다.

### 3. authoritative path 배선

[`expert_main.py`](../../expert_main.py)의 hook은 `commit_publication_result`와 base receipt 재검증 뒤, batch learning 전에 실행된다. fresh measurement에서는 HMAC key와 registry를 만들지 않고 WAL replay sidecar append도 건너뛴다.

[`tools/reconcile_recovery_activation_checkpoint.py`](../../tools/reconcile_recovery_activation_checkpoint.py)는 기존 checkpoint를 읽기 전용으로 exact 검증해 sidecar를 재구성한다. 서로 다른 publication scope가 섞이면 consensus를 `NO-GO`로 처리한다.

## 결정적 검증 결과

| 검증 | 결과 | 핵심 확인 |
| --- | --- | --- |
| Python 3.11 focused sidecar | `22 PASS` | key/tail/capability/base/WAL/CAS |
| Python 3.12 focused sidecar | `22 PASS` | 동일 계약 교차 버전 |
| 인접 계약 묶음 | `187 PASS` | publication/semantic/promotion/replay |
| Python 3.11/3.12 compile | `PASS` | import/compile blocker 없음 |
| 동결 2,712 publish replay | `GO` | exact `2,712/2,712`, mismatch/regression `0` |
| 동결 2,712 sidecar reconciliation | `GO` | proposal/event `68/68`, provenance `100%` |
| 동일 출력 두 번째 reconciliation | `GO` | `created 0 / replayed 68` |
| 독립 배선 검토 | `GO` | 새 P0/P1 없음 |
| 독립 지표 검산 | `GO` | ledger·summary·비율 일치 |
| Data Analytics artifact | `validate ok / render ok` | title·KPI·verdict chart·caveat 포함 |

동결 publish replay의 exact 결과는 다음과 같다.

- ledger/replay/estimable: `2,712/2,712/2,712`
- ledger missing/duplicate: `0/0`
- public projection mismatch: `0`
- fingerprint mismatch: `0`
- reason-code mismatch: `0`
- normal→abnormal contract regression: `0`
- stored/recomputed unsafe publish: `33/33`
- stored compliant→recomputed noncompliant semantic regression: `0`

동결 sidecar reconciliation 결과는 다음과 같다.

- source rows/unique post: `2,712/2,712`
- base outcome: `PUBLISH 263 / HOLD 2,449`
- proposal/event: `68/68`
- unique proposal post: `67`
- checkpoint SHA before/after: 동일
- provenance coverage: `100%`
- `public_apply=true`: `0`
- 첫 실행/동일 재실행: `created 68` 뒤 `created 0 / replayed 68`
- HMAC key mode: `0600`

## 왜 지금 구조가 기존 정답을 덜 흔드는가

기존 경로 안에서 title을 즉시 부활시키면 serializer late override, legacy fallback, canonical rewrite, 검색 변동이 한 번에 공개 결과에 영향을 줄 수 있다. 현재 구조는 세 단계를 분리한다.

1. 기존 publication WAL과 공개 projection을 immutable baseline으로 고정한다.
2. 새 근거는 public writer가 아닌 review proposal로만 append한다.
3. 동일 scope의 반복 검증과 별도 activation 승인이 끝난 뒤에만 제한된 공개 적용을 검토한다.

이 방식은 신규 recall을 바로 얻는 대신 자동 공개까지 시간이 더 걸린다. 그러나 기존 정상 정답을 보존하는 것이 최우선인 현재 상황에서는 가장 안전한 rollback boundary다.

## 남은 개선 작업

2026-07-18에 독립 shard 3349~3364로 32행 BEFORE/OFF·AFTER/AUDIT_ONLY 요청을 각 3회 실행했다. runtime·공개 비간섭은 6/6 `GO`였으나 source 반복 회귀 2행, search/router/measurement 미통과로 자동 activation은 `NO-GO`다. 상세 수치와 사례는 [`LIVE_RUN_2712_RECOVERY_SIDECAR_GROUPED_AB_REPORT_20260718_KO.md`](LIVE_RUN_2712_RECOVERY_SIDECAR_GROUPED_AB_REPORT_20260718_KO.md)를 정본으로 사용한다.

### 현재 바로 열지 않는 것

- direct OCR 후보의 자동 공개
- non-novel/media, primary/previous/mentioned/comparison 관계의 전면 activation
- semantic review router 자동 처리
- canonical work ID→official title 자동 렌더링
- targeted HOLD 자동 recovery
- 초저위험 188건 early route

### 다음 실행 순서

1. call measurement row-key·stage normalization을 공개 판정과 분리된 release에서 복구
2. search/router를 measurable·green 상태로 만든 뒤 동일 RunSpec을 재실행
3. official-detail·canonical work ID·primary/current·single-work·non-media를 모두 만족하는 review selector만 shadow로 추가
4. 위험 family와 정상 family를 별도 rollback boundary로 각 3회 반복
5. deterministic gate는 1회 실패도 hard failure, semantic wobble은 반복 합의·집중도로 판정
6. search/router/measurement green, provenance 100%, repeated regression·신규 unsafe/wrong-title 0일 때만 제한 activation 검토

현재 104,502-input run은 계속 읽기 전용으로 보존했다. 새 canary는 그 런의 endpoint와 겹치지 않는 3349~3364 shard와 별도 dashboard를 사용해 자원·검색 범위를 분리했다.

## GO/NO-GO와 rollback boundary

| Phase | 상태 | rollback boundary |
| --- | --- | --- |
| P0a 공개 safety seal | `GO` | 기존 production 경로 유지 |
| recovery ledger/capability 기반 | `GO` | 별도 sidecar 삭제·비활성화 가능 |
| direct OCR review-only | `GO` | 공개 결과와 독립 |
| search health | `NO-GO` | activation 금지 |
| fresh grouped semantic repeat | `RUNTIME GO / SEMANTIC NO-GO` | 6 arm 192 receipt, source 반복 회귀 2행 |
| automatic recovery publish | `NO-GO` | `public_apply=false` 유지 |
| P1/P2 확대 | `NOT_STARTED` | 각 family 별도 shadow boundary |
| full scan | `REVIEW-LOCKED` | `full_scan_approval=false` |

## 정본 산출물

- 결정적 publish replay: [`publish_contract_replay_summary.json`](../../out/regression_safe_2712_improvement_20260717/recovery_sidecar_s0_replay_atomic_key_final/publish_contract_replay_summary.json)
- review-only sidecar reconciliation: [`recovery_activation_reconciliation_summary.json`](../../out/regression_safe_2712_improvement_20260717/recovery_sidecar_v2_frozen2712_atomic_key_final/recovery_activation_reconciliation_summary.json)
- append-only sidecar journal: [`expert_result_20260715_143806_848671_checkpoint.recovery_activation.jsonl`](../../out/regression_safe_2712_improvement_20260717/recovery_sidecar_v2_frozen2712_atomic_key_final/expert_result_20260715_143806_848671_checkpoint.recovery_activation.jsonl)
- Data Analytics artifact: [`LIVE_RUN_2712_RECOVERY_SIDECAR_DATA_ANALYTICS_ARTIFACT_20260717.json`](LIVE_RUN_2712_RECOVERY_SIDECAR_DATA_ANALYTICS_ARTIFACT_20260717.json)
- 계약 테스트: [`tests/test_recovery_activation_ledger.py`](../../tests/test_recovery_activation_ledger.py)
- 개발 체크리스트: [`CHECKLIST.md`](CHECKLIST.md)

Data Analytics MCP artifact `동결 2,712행 Recovery Sidecar 개선 검증`도 동일 두 summary를 source로 `validate ok / render ok`까지 확인했다.
