# P3 실제 정확도 정책 숫자 결정안

상태: `DECISION_REQUIRED / POLICY_NOT_REGISTERED / NO_GO_ACTUAL_DATASET_NOT_READY`

## 먼저 결론

실제 결과를 보기 전에 정확도·위험·비열화 한계를 고정해야 한다. 현재 저장소에는 그 숫자를 확정할 실제 baseline이나 사업 허용오류가 없으므로 실행 가능한 `FROZEN_ACTUAL_PRE_REGISTERED` JSON은 아직 만들지 않는다. 합성 fixture의 느슨한 값(`top=-1`, `risk=1`, `log_loss=100` 등)은 계산식 시험용이며 actual 정책으로 복사하지 않는다.

권고는 **A. 안전 우선 비열화 금지**다. 아래 숫자는 소유자 승인 전 제안값이며 측정 결과가 아니다.

## 바꿀 수 없는 계약

| 항목 | 고정 규칙 |
| --- | --- |
| 정답 사건 | `Y ∈ {candidate_id, NIL}`; `ABSTAIN`은 행동 |
| 후보 재현율 분모 | producer `COMPLETE` + immutable candidate ID + 결속된 정답 행만 사용 |
| 검색·후보 누락 | 하나라도 있으면 headline 전부 `null`, `NO-GO` |
| paired 방향 | top-label accuracy는 AFTER−BEFORE CI 하한, Brier/log-loss/ECE/selective-risk/AURC는 CI 상한 |
| 정책 출처 | `policy_scope=FROZEN_ACTUAL_PRE_REGISTERED`, `policy_origin=PRE_REGISTERED_DEV_CALIBRATION` |
| bootstrap | 같은 frozen 행·그룹, 그룹 최소 2개, 반복 최소 100; 권고 2,000 |
| 운영 경계 | actual shadow GO여도 `REVIEW-LOCKED`, `full_scan_approval=false` |

## 숫자 선택안

| 필드 | A. 안전 우선 비열화 금지 (권고) | B. 제한적 비열화 허용 | 뜻 |
| --- | ---: | ---: | --- |
| `selector_max_error_probability` | 0.10 | 0.15 | 선택한 행동의 추정 오류가 이 값을 넘으면 보류 |
| `nil_min_probability` | 0.90 | 0.85 | NIL 자동 선택 최소 확률 |
| `alpha` | 0.05 | 0.05 | 95% 신뢰수준 |
| `target_coverage` | 0.10 | 0.20 | 최소 자동 처리 범위 |
| `max_selective_risk_upper_bound` | 0.05 | 0.10 | 자동 선택 오답률 신뢰상한 |
| `min_candidate_recall_lower_bound` | 0.95 | 0.90 | 후보 목록 재현율의 one-sided 하한 |
| `min_nil_precision_lower_bound` | 0.90 | 0.85 | NIL 정밀도 신뢰하한 |
| `min_nil_recall_lower_bound` | 0.90 | 0.85 | NIL 재현율 신뢰하한 |
| `min_nil_prediction_count` | 36 | 30 | NIL 품질 평가 최소 예측 수 |
| paired top accuracy 하한 | 0.00 | -0.01 | A는 정확도 비열화 금지, B는 최대 1%p 허용 |
| paired Brier 상한 | 0.00 | 0.01 | AFTER−BEFORE 허용 악화 |
| paired log-loss 상한 | 0.00 | 0.02 | AFTER−BEFORE 허용 악화 |
| paired ECE 상한 | 0.00 | 0.01 | 보정 오차 허용 악화 |
| paired selective-risk 상한 | 0.00 | 0.02 | `baseline_noninferiority_margin`과 같은 값 |
| paired AURC 상한 | 0.00 | 0.01 | risk-coverage 곡선 허용 악화 |

A는 비용 개선이 있어도 정확도·확률 품질·선택 위험이 악화되는 경우 채택하지 않는다. B는 표본 노이즈와 비용 이득을 위해 작은 악화를 허용하므로 별도 운영 승인이 필요하다.

## 표본 제안

| 필드 | A 권고 | B 제안 |
| --- | ---: | ---: |
| DEV 전체 / truth class별 | 120 / 40 | 80 / 25 |
| CALIBRATION 전체 / truth class별 | 120 / 40 | 80 / 25 |
| FROZEN 전체 / truth class별 | 200 / 60 | 150 / 40 |
| 고정 ECE bin | `[0,.2,.4,.6,.8,1]` | 동일 |
| occupied bin 최소 행 | 20 | 15 |
| bootstrap seed / 반복 | `20260712 / 2000` | 동일 |

표본 근거 예시: alpha 0.05에서 관측이 전부 성공해도 candidate recall one-sided 하한 0.90/0.95를 보장하려면 독립 binomial 기준 최소 약 29/59건이 필요하다. NIL precision·recall의 two-sided 하한 0.90에는 약 36건이 필요하다. 실제 그룹 bootstrap·실패 사례·빈 ECE bin을 고려하면 더 많은 행이 필요하므로 A는 frozen class별 60행을 권고한다. 이는 목표값의 정당화가 아니라 최소 표본 산식이다.

## 미판정 3행

`11663521`, `11685994`, `11700470`은 모두 특정 작품 사건이지만 정확한 단일 작품 ID가 확정되지 않았다. NIL로 바꾸면 오라벨이고 후보 하나를 고르면 근거 없는 과확정이다. 따라서 새 source-backed 판결 전까지 `UNJUDGED / ABSTAIN`을 유지하며 actual split에서 제외한다.

## 확정 후 실행

1. 소유자가 `A` 또는 `B`를 확정하거나 필드별 숫자를 수정한다.
2. 확정값으로만 canonical policy SHA가 있는 JSON을 만든다.
3. readiness를 새 버전으로 재생해 정책 blocker가 제거됐는지 확인한다.
4. producer COMPLETE·행별 provenance·split/source/replay가 모두 준비된 뒤 `actual-preflight → actual-readback → actual-evaluate`를 실행한다.
5. P3 통과 뒤에만 동일 RunSpec의 fresh BEFORE/AFTER 비용 pair를 실행한다.

확정 입력 예시: `정책 A로 확정` 또는 `A에서 target_coverage=0.20만 변경`.
