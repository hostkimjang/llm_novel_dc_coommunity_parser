# P3 정확도 퍼센트 계약 기반 구현 보고서

> 2026-07-12 최신 정본은 P2 v8에 결속한 P3 v18이다. readiness v2, 무쓰기 actual preflight, 정책·P1·라벨·동결 split·source payload·네 JSONL·replay 6종 bound readback, 여섯 paired CI 정책 판정까지 구현했다. replay는 실제 parser와 frozen coverage·split/policy 결속을 통과해야 한다. 다만 실제 DEV/CAL/FROZEN 자료와 실행 출력이 없으므로 정확도 퍼센트는 계속 `null / NOT_ESTIMABLE`이다. RunSpec self hash는 `ca26d8d39485171e5d8a0673fabbf6353aca91389413a834eea4d4827f48e64b`다.

## 한눈에 보는 결론

- 후보 작품들과 `작품 없음(NIL)`에 확률을 나누는 **정확도 퍼센트 그림자 기록의 계약 기반**을 구현했다.
- Golden18은 후보 생산 완료 영수증과 분리된 개발·보정·동결 자료가 없으므로 모든 실제 확률·정확도 지표를 `null`로 유지했다.
- 준비도는 전체 `18`, 작품 정답 `9`, NIL `6`, 미판정 `3`, producer COMPLETE `0`, 실제 분할 준비 `0`이다. 게이트는 `NO_GO_ACTUAL_DATASET_NOT_READY`다.
- readiness v2는 blocker와 hash만 다시 만든 거짓 READY뿐 아니라 다른 actual 정책 파일도 P1 comparison·P1-bound label ledger·policy raw-byte source replay에서 거부한다.
- actual bound runner는 수동 SHA를 받지 않고 동결 split의 정답·candidate ID·content/source/label provenance와 source manifest raw SHA를 producer·AFTER·baseline에 결속한다. 행별 source payload도 최상위 아티팩트로 올려 평가 전후에 다시 읽고 내부 행 신원을 대조한다.
- `actual-preflight`는 필수 입력 10종·replay 6종·readiness·strict bound build 가능 여부를 파일 쓰기와 모델 실행 없이 보여준다. GO여도 실제 readback이 다시 검증한다.
- replay 6종은 base shadow·score vector·calibration artifact·prediction parser와 frozen coverage·post identity·split/policy 검증을 통과해야 하므로 이름만 맞춘 빈 JSON은 거부된다.
- 정확도·Brier·log loss·ECE·선택 위험·AURC의 paired CI를 사전 정책과 대조하며, 계산 가능하다는 사실만으로 GO를 만들지 않는다.
- 기존 구조에서 출처 없이 “보정됨”이라고 주장할 수 있던 합성 숫자 경로는 `1→0`으로 닫았다.
- 합성 공격은 `20/20`, 거짓 통과는 `0`이다. 실제 판독 `12`, 준비도 `7`, 계약 `16`, 하네스 `19`, 합계 `54/54` 집중 시험을 통과했다.
- 판정은 `GO_P3_CONTRACT_FOUNDATION_ONLY`다. 실제 모델 정확도 향상, 실제 runtime, 의미 품질, 전체 스캔 승인을 뜻하지 않는다.
- 현재 경계는 `runtime_validation=NOT_RUN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, 목표 `ACTIVE_NOT_COMPLETE`다.

## 이 기능은 무엇을 하는가

한 게시글의 정답 사건을 다음 중 정확히 하나로 둔다.

`Y = 후보 작품 A 또는 후보 작품 B 또는 ... 또는 NIL`

후보별 확률과 `p(NIL)`의 합은 정확히 100%다. 여기서 100%는 선택지에 확률을 모두 배분했다는 뜻이며, 시스템이 100% 맞는다는 뜻이 아니다. `ABSTAIN`은 정답 종류가 아니라 검색 실패나 높은 오류 위험 때문에 답을 보류하는 행동이다.

| 기능 | 쉬운 설명 | 이번 구현 |
| --- | --- | --- |
| 후보 목록 재현율 선행 | 정답 작품이 후보 목록에 없으면 높은 확률도 의미가 없다. | 정답 후보 누락·애매 결합은 지표 계산 전에 중단한다. |
| 개발·보정·동결 분리 | 같은 자료로 규칙을 만들고 시험하면 퍼센트가 과적합된다. | 게시글 그룹·본문·출처·후보 묶음·작품 지문이 분할을 건너지 못한다. |
| 보정기 학습 영수증 | 어떤 자료와 점수 생성기로 확률을 맞췄는지 증명한다. | 보정 자료 수, 작품/NIL 수, 미해결 라벨 0, 온도값, 분할·정책 지문을 결속한다. |
| 원본 재생 검증 | 저장된 확률 기록만 바꿔 지표를 조작하지 못하게 한다. | 기본 후보 기록·원점수·보정기·분할·행을 다시 재생해 저장본과 정확히 비교한다. |
| 확률 질량 고정 | 부동소수 반올림이나 사건 추가로 합을 속이지 못하게 한다. | 후보 ID들과 NIL의 정수 질량 합을 정확히 `1,000,000`으로 고정한다. |
| 검색 실패 무수치 | 필수 검색이 실패한 행을 보류 처리한 뒤 성능 분모에 섞지 않는다. | 검색 차단 행이 하나라도 있으면 headline 지표를 전부 `null`로 둔다. |
| 실제 자료 표기 차단 | 해시 문자열만 만들어 실제 동결 평가라고 주장하지 못하게 한다. | 파일 바이트·생산 행 coverage·예측 payload 재검증 전에는 `FROZEN_ACTUAL` 수치를 전부 차단한다. |
| 준비도 원본 재생 | 준비도 JSON을 스스로 다시 해시한 위조를 막는다. | P1 RunSpec에서 비교표를 재생하고 P1이 결속한 라벨 원장으로 모든 행을 다시 계산한다. |
| paired CI 정책 판정 | 같은 행의 전후 차이가 우연인지 정책 한계 안인지 본다. | 정확도는 CI 하한, Brier·log loss·ECE·선택 위험·AURC는 CI 상한을 대조한다. |
| 공개 결과 비간섭 | 시험 퍼센트가 기존 결과를 바로 바꾸지 않는다. | 별도 그림자 기록이며 `action_applied=false`, `NONE_SHADOW_ONLY`다. |

## 개선 전·후

| 항목 | 개선 전 | 개선 후 |
| --- | --- | --- |
| 숫자 출처 | 합계가 1인 숫자와 상태 문자열만으로 보정 주장 가능 | 분할·보정 학습 영수증·점수 생성기·정책·후보 묶음·입력 지문 필수 |
| 행 결합 | 저장된 결과를 신뢰 | 기본 후보 기록·점수·보정기를 재생해 정확히 같은지 확인 |
| 행이 중간에 바뀌는 입력 | 검증 뒤 다른 값으로 바꿔 지표 세탁 가능 | 평가 시작 시 한 번 복제한 고정 snapshot만 사용 |
| 검색 미복구 | 보류와 숫자 지표가 공존할 수 있음 | `NOT_EVALUABLE_RETRIEVAL_BLOCKED`, headline 전부 `null` |
| 보고서 승인값 | 임의 `full_scan_approval=true` 직렬화 가능 | 저장 전 구조·RunSpec·정책·공격 요약·승인 경계를 재검증하고 거부 |
| 실제 자료 표기 | 호출자가 `FROZEN_ACTUAL` 문자열을 줄 수 있음 | 실제 파일 바이트·생산 행 coverage·예측 payload·원본 SHA를 독립 재판독하고 모두 결속해야만 계산 허용 |
| 원문 행 바꿔치기·TOCTOU | source manifest 해시만 맞추거나 평가 중 원문 파일을 바꿀 수 있음 | 행별 source payload를 최상위 `ArtifactRef`로 재판독하고 내부 `schema_version/source_run_id/example_id/post_id`를 exact-match |
| 신뢰구간 | 계산만 되면 값이 정책 한계를 넘어도 GO가 될 수 있음 | 고정 seed 그룹 bootstrap의 여섯 paired CI를 사전 정책에 모두 대조하고 하나라도 실패하면 NO-GO |

## 지표의 뜻

| 지표 | 무엇을 재나 | 좋은 방향 |
| --- | --- | --- |
| 후보 목록 재현율 | 실제 정답 작품이 후보 묶음에 포함됐는지 | 높을수록 좋음 |
| 최고 후보 정확도 | 가장 큰 확률을 준 후보가 정답인지 | 높을수록 좋음 |
| Brier 점수 | 모든 후보와 NIL에 준 확률이 정답에서 벗어난 평균 정도 | 낮을수록 좋음 |
| 자연로그 손실 | 정답에 지나치게 낮은 확률을 준 예측의 벌점 | 낮을수록 좋음 |
| 예측 비율 오차(ECE) | 80%라고 한 묶음이 실제로 약 80% 맞는지 | 낮을수록 좋음 |
| NIL 정밀도·재현율 | 작품 없음 선택의 과잉과 누락 | 둘 다 높을수록 좋음 |
| 자동 처리 범위·선택 위험 | 보류하지 않은 비율과 그중 오답 비율 | 함께 비교해야 함 |
| AURC | 낮은 위험 예측부터 처리 범위를 넓힐 때 누적 오류 곡선의 평균 | 낮을수록 좋음 |

NIL 예측이 0건이면 정밀도를 100%로 만들지 않고 `null`로 둔다. 표본이 사전 최소치보다 작거나 ECE 구간이 너무 작아도 0% 또는 100%를 만들지 않고 `NOT_ESTIMABLE`로 중단한다. 비율 신뢰구간은 작은 표본에도 맞는 Clopper–Pearson 방식을 사용한다.

## 저장본과 합성 결과를 분리한 판정

### Golden18 저장본

- 행 수: `18`
- 후보 생성 상태: `UNKNOWN`
- 후보 목록 재현율: `NOT_EVALUABLE`
- 실제 headline 지표: 전부 `null`
- 기존 공개 결과 불변: `18/18`
- 실제 정확도 퍼센트 공개: 금지

### 합성 4행 계산식 시험

| 지표 | 개선 전 합성 | 개선 후 합성 |
| --- | ---: | ---: |
| 최고 후보 정확도 | 0.500000 | 1.000000 |
| Brier 점수 | 0.606777 | 0.004498 |
| 자연로그 손실 | 0.813262 | 0.048587 |
| ECE | 0.231059 | 0.047426 |

이 표는 수식이 올바른 방향으로 움직이는지 확인하기 위해 만든 인위적 4행이다. 실제 모델 성능이나 정확도 개선률로 인용하면 안 된다. 합성 결과도 `conversion_allowed=false`다.

## 공격·회귀 검증

- 합성 계약 공격: `20/20`, 거짓 통과 `0`
- 계약·하네스 테스트: `35/35`
- 실제 파일 재판독·준비도 테스트: `19/19`
- 이번 P3 집중 합계: `54/54`
- P1 검색·후보·공개 영향 범위: `532/532`
- P2 publication/recovery/input 핵심: `126/126`
- 변경 파일 문법 검사: `py_compile PASS`
- Sol 울트라 재공격 3건:
  - 평가 도중 값이 바뀌는 `Mapping` 지표 세탁 차단
  - 검색 차단 행을 검증 뒤 정상 행으로 바꾸는 세탁 차단
  - 보고서에 `full_scan_approval=true`를 직접 쓰는 위조 차단

이번 오케스트레이션의 Fable·Opus는 모델 선택은 적용됐지만 재전송에도 작업 본문별 결과 대신 일반 안내를 반환해 최신 근거에서 제외했다. Sol·Terra·Luna 결과도 본 에이전트가 로컬 테스트로 재검증한 내용만 반영했다.

Active production은 읽기 전용으로만 확인했다. `2026-07-12 14:20:20 KST` 이동 스냅샷은 input/completed/flushed/pending/failed `104502/2665/2650/15/0`, next save `2651`, parallel `16/16`, dashboard health HTTP 200, `partial_flush_gap=true`, `ordered_flush_blocked=true`, `large_run_complete=false`다. 이 수치는 P3 runtime·정확도·승인 근거가 아니다.

이 정본 생성 뒤 한때 반복 외부 blocker 임계치에 따라 `BLOCKED_HANDOFF / NOT_COMPLETE`로 전환했지만, 사용자의 `goal 재개` 지시로 현재 전체 Goal은 `ACTIVE / NOT_COMPLETE`다. comparison 내부의 `ACTIVE_NOT_COMPLETE`는 정본 생성 시점 artifact gate이고 실제 runtime·운영 승인을 뜻하지 않는다.

## 정본 산출물

- 최신 RunSpec: `out/candidate_set_calibration_shadow_harness_20260711/v18/run_spec.json`
  - self hash: `ca26d8d39485171e5d8a0673fabbf6353aca91389413a834eea4d4827f48e64b`
  - file SHA-256: `6328b5c10e5a94ffa042583cf397e7a9f6ed84037df2c26f5dc76e7f95fb1606`
- 최신 비교 JSON: `out/candidate_set_calibration_shadow_harness_20260711/v18/comparison.json`
  - file SHA-256: `92b4d8d6ac221543a9b75e9c632434ac661c7fdea6696d8a06b47ec59c86df93`
- 사람이 읽는 최신 비교: `out/candidate_set_calibration_shadow_harness_20260711/v18/comparison.md`
  - file SHA-256: `3cf2e26eae409ef2d9aed245c5c4de1561377673bc038e235c69abc2311bc9b7`
- readiness v2: `out/candidate_set_calibration_dataset_readiness_20260712/v2/readiness.json`
  - manifest self hash: `540472ba9c93b8c066a18520835c7b50570a7be19259e68cf3b32548bb4da61f`

## 현재 게이트

| 게이트 | 상태 | 뜻 |
| --- | --- | --- |
| P3 계약 기반 | `GO_P3_CONTRACT_FOUNDATION_ONLY` | 무근거 숫자·분할 누수·저장본 위조를 막는 기반만 통과 |
| Golden18 확률 | `NOT_AVAILABLE_UNCALIBRATED` | 실제 수치 없음 |
| 실제 보정 자료 | `NO_GO_ACTUAL_DATASET_NOT_READY` | producer COMPLETE `0/18`, 미판정 `3`, 준비 행 `0/18` |
| 실제 증거 사전점검 | `IMPLEMENTED_READ_ONLY_NO_ACTUAL_PACKET` | 무쓰기/무런타임 preflight는 구현됐고 actual packet은 없음 |
| 실제 산출물 재검증 | `IMPLEMENTED_V2_BOUND_RUNNER_NO_ACTUAL_ARTIFACT` | 정책·split·source·producer·AFTER·baseline bound runner는 구현됐고 actual 파일은 없음 |
| 전체 신뢰구간 | `IMPLEMENTED_POLICY_BOUND_NO_ACTUAL_OUTPUT` | 여섯 paired CI 정책 게이트는 구현됐고 실제 출력 구간은 아직 없음 |
| 실제 runtime | `NOT_RUN` | active production 비간섭 |
| 의미 품질 | `REVIEW-LOCKED` | 사람·공식 근거 기반 전체 품질 미승인 |
| 전체 스캔 승인 | `full_scan_approval=false` | 운영 전환 금지 |
| 목표 | `ACTIVE_NOT_COMPLETE` | P3 실제 자료·runtime과 후속 단계가 남음 |

## 다음 완료 증거

1. Golden18 NO-GO 점검과 분리된 actual runner에서 policy JSON·외부 expected universe·COMPLETE producer·P1-bound 라벨 원장을 결속한다.
2. 구현된 독립 reader로 생산 계획·영수증·예측 파일·행 coverage를 실제 파일 바이트에서 다시 읽어 하나의 증거 영수증으로 결속한다.
3. 보정 자료에서만 온도값과 행동 기준을 정하고 동결 자료는 기준 변경 없이 한 번 평가한다.
4. 구현된 그룹 bootstrap으로 ECE·Brier·자연로그 손실·AURC와 동일 행 baseline 차이의 실제 신뢰구간을 산출한다.
5. active production 종료 뒤 별도 경로, `--parallel 16`, dashboard ON, slang DB off 또는 읽기 전용으로 실제 P2/P3 runtime을 검증한다.
