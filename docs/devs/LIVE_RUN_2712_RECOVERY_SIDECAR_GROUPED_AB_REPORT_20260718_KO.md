# 동결 2,712행 Recovery Sidecar 실제 묶음 BEFORE/AFTER 보고서

## 결론

기존 공개 결과를 흔들지 않는 `freeze → shadow/review-only → append-only activation ledger` 구조는 실제 묶음 실행에서도 안전하게 작동했다. 그러나 direct OCR 후보의 **자동 공개 승격은 승인하지 않는다**.

- 공개 결과 보존·WAL 비간섭: `GO`
- 2,712 persisted replay exact parity: `GO`
- review-only provenance·멱등성: `GO`
- 32행 × BEFORE/AFTER × 각 3회 runtime: `6/6 GO`
- fresh 의미 자동 승격: `NO-GO`
- 호출·token 승인 KPI: `NO-GO / NOT_ESTIMABLE`
- search health: `NO-GO`
- semantic review router: `NO-GO / NOT_ESTIMABLE`
- P1/P2 자동 activation: `NO-GO`
- 전체 스캔 승인: `full_scan_approval=false`

이번 개선이 실제로 해결한 것은 “기존 정답을 바꾸지 않고 direct OCR 복구 후보를 검증 가능한 review event로 포착하는 구조”다. 실제 공개 정답률 개선은 아직 입증되지 않았다.

## 한눈에 보는 게이트

| 축 | 결과 | 근거 |
| --- | --- | --- |
| 입력·조건 동등성 | `GO` | 동일 32 `post_id`, input SHA, model, publication scope, WAL |
| 요청/실효 병렬도 | `16/16` | 6개 arm 모두 동일 |
| dashboard | `ON` | standalone forward, 6개 arm 모두 동일 |
| VLM/OCR | `READY` | 이미지 19행, 6개 arm 모두 semantic gate READY |
| runtime completion | `6/6 GO` | 각 arm `32/32`, pending/failed `0/0`, terminal finalized |
| receipt coverage | `192/192 GO` | 32행 × 6 arm validated shadow receipt |
| 공개 WAL 비간섭 | `6/6 GO` | event `32→32`, SHA `fb336f…c84d` 불변 |
| sidecar 공개 적용 | `0` | `public_apply=false`, fresh에서는 sidecar append 자체를 건너뜀 |
| semantic auto activation | `NO-GO` | source 정답 대비 반복 회귀 2행, search/router·measurement 미통과 |
| call measurement | `NO-GO` | 모든 arm ledger partial·actual KPI `NOT_ESTIMABLE` |
| full scan | `REVIEW-LOCKED` | targeted 32행 결과를 104,502행 전체 승인으로 확대하지 않음 |

정본 RunSpec의 AFTER는 `AUDIT_ONLY`로 요청됐지만 fresh measurement에서는 `SKIPPED_FRESH_MEASUREMENT`다. 따라서 아래 BEFORE/AFTER 차이는 sidecar의 인과 효과가 아니라 동일 release의 stochastic 분포 차이다.

## 개선 전후 묶음 지표

각 arm은 동일 32행을 3회 실행했다. `any-run`은 한 번이라도 발생한 post 수, `exact runs`는 96개 행-회차 중 해당 조건 횟수, `majority`는 같은 post에서 2/3 이상 반복된 수다.

| 지표 | BEFORE/OFF | AFTER/AUDIT_ONLY 요청 | 해석 |
| --- | ---: | ---: | --- |
| source 정답→반복 비정상 | `2` | `2` | 양 arm 동일 2행, 자동 승격 차단 |
| 신규 unsafe publish majority | `1` | `0` | AFTER 우세처럼 보이나 sidecar 미실행이라 인과 주장 금지 |
| 신규 wrong-title majority | `1` | `0` | 같은 이유로 기술적 관측만 보존 |
| unsafe publish any-run / exact runs / majority | `1 / 2 / 1` | `1 / 1 / 0` | `11716480`의 title 변형·HOLD 흔들림 |
| FN correct recovery any-run / exact runs / majority | `1 / 1 / 0` | `1 / 1 / 0` | `11718097`, 양 arm 모두 1/3뿐 |
| PASS retention any-run / exact runs / majority | `1 / 1 / 0` | `1 / 2 / 1` | `11718120`, stochastic 개선 보류 |
| FP publish | `0 / 0 / 0` | `0 / 0 / 0` | 묶음의 FP 3행 전 회차 HOLD |
| HOLD integrity exact runs / majority posts | `15 / 5` | `15 / 5` | HOLD 정본 5행 전 회차 보존 |
| WRONG_WORK 미회복 exact runs / majority posts | `9 / 3` | `9 / 3` | CORRECT 필요 3행은 전 회차 HOLD |
| 동결 정본 majority compliant | `16/32` | `17/32` | 절대 품질도 activation 기준 미달 |
| source projection drift 횟수 | `6` | `7` | arm별 stochastic drift, 공개 WAL 변경 아님 |
| unanimous / variable posts | `29 / 3` | `29 / 3` | distinct-projection excess만 `4 / 3` |

`cross_arm descriptive normal→abnormal`은 `0`이지만 승인 근거가 되지 않는다. source owner에서 정답이던 두 행이 양 arm 모두 반복 비정상이었기 때문이다.

## 행별로 무엇이 좋아지고 나빠졌나

| post_id | 동결 정답 | BEFORE 3회 | AFTER 3회 | 판정 |
| --- | --- | --- | --- | --- |
| `11718120` | `괴담 호텔 탈출기` KEEP/PASS | HOLD / 정답 / HOLD | 정답 / 정답 / HOLD | `1/3→2/3`이나 sidecar 미실행. stochastic 개선으로만 기록 |
| `11718097` | `망겜의 힐러` CORRECT/FN | 정답 / HOLD / HOLD | HOLD / 정답 / HOLD | 양 arm `1/3`; source 정답 대비 반복 회귀 |
| `11716480` | `여대생 가랑이 사이 무릎 꿇은 엄마들` CORRECT/FN | `무릎 끓은` / `여대학생…` / HOLD | HOLD / `무릎 끓은` / HOLD | 정확한 회복 `0/3→0/3`; wrong-title와 HOLD가 반복 |

### 안정적으로 보존된 정상·위험 대조군

- `FP_NONNOVEL` 3행은 BEFORE/AFTER 전 18회 HOLD다.
- `MULTIWORK_HOLD_CORRECT` 2행은 전 12회 HOLD다.
- `WRONG_WORK + HOLD` 2행은 전 12회 HOLD다.
- action `HOLD`인 5행은 전 30회 HOLD다.

### 아직 회복하지 못한 위험군

- CORRECT가 필요한 `WRONG_WORK` 3행은 양 arm 전 18회 HOLD다.
- 묶음의 FN 11행 중 majority 정답 회복은 양 arm 모두 `0`이다.
- `11718117`, `11718082`, `11718058`은 offline sidecar가 정확한 direct OCR review 후보로 포착했지만, fresh 공개 결과는 양 arm 전 회차 HOLD였다. 이것이 review-only 포착과 자동 공개 회복을 분리해야 하는 이유다.

## 2,712행 전체에서 review-only가 한 일

동결 2,712 persisted checkpoint를 공개 결과 변경 없이 재조정한 결과는 다음과 같다.

| 항목 | 결과 |
| --- | ---: |
| checkpoint exact coverage | `2,712/2,712` |
| base PUBLISH / HOLD | `263 / 2,449` |
| review proposal events / 고유 post | `68 / 67` |
| `FN_TITLE_MISSING` event | `48/339` |
| PASS 추가 review | `0/230` |
| provenance coverage | `68/68`, `100%` |
| 동일 입력 재실행 신규 event | `0` (`replayed 68`) |
| checkpoint/public WAL 변경 | `0` |
| `public_apply=true` | `0` |

정상 `NOT_APPLICABLE` action에도 12 events가 있었고 `WRONG_WORK 3`, `FP_NONNOVEL 1`, conflict/multiwork에도 proposal이 섞였다. 따라서 68 events를 68건 정답 회복으로 해석하면 안 된다. review queue recall은 생겼지만 false-review 비용과 의미 선별이 남아 있다.

## Search·router·비용

| 항목 | BEFORE 96관측 | AFTER 96관측 | 승인 상태 |
| --- | ---: | ---: | --- |
| search status | degraded `61`, ok `19`, unknown `16` | degraded `61`, ok `19`, unknown `16` | `NO-GO` |
| search queries | `566` | `618` | 관측치 |
| unrecovered degraded | `225` | `246` | `NO-GO` |
| router known / unknown | `0 / 96` | `0 / 96` | `NOT_ESTIMABLE` |
| high-risk router recall | 분모 없음 | 분모 없음 | `NOT_ESTIMABLE` |
| normal false-review rate | 분모 없음 | 분모 없음 | `NOT_ESTIMABLE` |
| run wall time | `3,519.2s` | `4,513.6s` | 관측치, 인과 해석 금지 |

구조 관측치는 BEFORE/AFTER 순서로 expert calls `897/912`, search calls `566/618`, prompt tokens `7,483,613/8,173,940`, completion tokens `351,079/427,077`, total tokens `7,834,692/8,601,017`이다. 6개 arm 합계는 calls `1,809`, total tokens `16,435,709`다. 그러나 전 arm에서 actual KPI gate가 닫혔으므로 모두 승인 가능한 exact cost가 아니라 `observational_partial`이다.

계측 `NO-GO` 원인은 의미 결과와 분리된다.

1. manifest gate가 JSON roundtrip 뒤 `int` row key를 `str`로 바꾸고 다시 `int`로 조회해 모든 행을 `ROW_MEASUREMENT_MISSING`으로 오판한다.
2. `comment_answer_judge` tag가 stage allowlist에 없어 매 arm `11718115` row attempt가 abort되고 open call 1개가 남는다.
3. 일부 provider usage가 `ESTIMATED`여서 exact token KPI로 승격할 수 없다.

공개 projection은 위 계측 실패와 무관하게 모든 행에서 별도 receipt로 검증됐다.

## 지금 구조의 한계와 더 안전한 다음 개선

현재 구조의 핵심 한계는 candidate 포착과 candidate 공개 선정을 의도적으로 분리했다는 점이다. recall 후보는 얻지만, 공식 상세·primary relation·검색 정상성 없이 title을 자동 부활시키지 않는다. 기존 정답을 최대한 안 흔들려면 이 제약을 유지하는 편이 맞다.

다음 순서는 아래 rollback boundary를 지킨다.

1. **계측 복구만 별도 release**: row-key 보존, `comment_answer_judge` stage mapping, estimated usage와 structural linkability 분리. 공개 판정 로직은 바꾸지 않는다.
2. **direct OCR review precision gate**: 정본과 일치한 proposal만 대상으로 official-detail URL, canonical work ID, primary/current relation, single-work, non-media 조건을 모두 요구한다.
3. **shadow selector**: public writer와 분리된 append-only selection event에서만 후보를 고르고, 기존 public projection은 계속 immutable로 둔다.
4. **family별 canary**: FN direct OCR, WRONG_WORK, media/non-novel, multiwork, PASS/NOT_APPLICABLE를 섞되 각 family를 별도 rollback한다.
5. **자동 공개는 마지막**: repeated source regression `0`, 신규 unsafe/wrong-title `0`, provenance `100%`, search/router/measurement green일 때만 capability token으로 제한 활성화한다.
6. **P2 early route**: 위 모든 게이트 통과 뒤 초저위험 188건 canary부터 시작한다.

현재는 2번 이후로 진행하지 않는다. 양 arm에서 반복 source regression 2행이 있고, FN majority recovery가 `0/11`, PASS majority retention이 `1/2`, CORRECT가 필요한 WRONG_WORK 미회복이 `3/3`이며 search/router/measurement도 모두 green이 아니기 때문이다.

## GO/NO-GO와 rollback boundary

| Phase | 상태 | rollback boundary |
| --- | --- | --- |
| P0a 공개 safety seal | `GO` | 현재 production 공개 경로 유지 |
| append-only recovery ledger/capability | `GO` | sidecar OFF로 즉시 격리 가능 |
| direct OCR review-only | `GO` | `public_apply=false` 유지 |
| 2,712 exact replay | `GO` | projection/fingerprint/reason regression 0 |
| fresh grouped runtime/noninterference | `GO` | 6/6 runtime·WAL gate |
| fresh semantic auto activation | `NO-GO` | source 반복 회귀 2행 |
| measurement | `NO-GO` | 계측 전용 release 전 비용 승인 금지 |
| search/router | `NO-GO` | selector/auto publish 금지 |
| P1/P2 | `NOT_STARTED / NO-GO` | family별 shadow 재검증 필요 |
| full scan | `REVIEW-LOCKED` | `full_scan_approval=false` |

## 정본 산출물

- 실제 6-arm runner summary: [`run_summary.json`](../../out/regression_safe_2712_improvement_20260717/fresh_cross_family_recovery_sidecar_ab_v2/run_summary.json)
- post_id exact 분석 summary: [`report.json`](../../out/regression_safe_2712_improvement_20260717/fresh_cross_family_recovery_sidecar_ab_v2/grouped_analysis/report.json)
- 행별 반복 transition: [`transitions.jsonl`](../../out/regression_safe_2712_improvement_20260717/fresh_cross_family_recovery_sidecar_ab_v2/grouped_analysis/transitions.jsonl)
- 2,712 review-only reconciliation: [`recovery_activation_reconciliation_summary.json`](../../out/regression_safe_2712_improvement_20260717/recovery_sidecar_v2_frozen2712_atomic_key_final/recovery_activation_reconciliation_summary.json)
- 2,712 publish replay: [`publish_contract_replay_summary.json`](../../out/regression_safe_2712_improvement_20260717/recovery_sidecar_shadow_observation_v2_frozen2712_replay/publish_contract_replay_summary.json)
- 분석 도구: [`analyze_recovery_sidecar_grouped_ab.py`](../../tools/analyze_recovery_sidecar_grouped_ab.py)
- 분석 계약 테스트: [`test_analyze_recovery_sidecar_grouped_ab.py`](../../tests/test_analyze_recovery_sidecar_grouped_ab.py)
