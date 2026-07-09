# 상시 회귀 게이트

- gate: `NO-GO`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- completion_gate: `adjusted full375 collateral GO + full_scan path`
- completion_gate_metric: `adjusted_drift_count`
- current_collateral_gate_metric: `adjusted_drift_count`
- rebaseline_status: `APPLIED`
- raw_20260626_baseline_is_completion_gate: `false`
- 정책: golden-18과 full 375 collateral diff를 항상 함께 요구한다.

## Golden 게이트

- gate: `GO`
- rows: `18/18`
- passed: `18`
- failed: `0`
- runtime_complete: `True`

## Collateral 게이트

- gate: `NO-GO`
- shared posts: `375/375`
- baseline_mode: `adjudicated_rebaseline`
- collateral_measure: `adjusted_drift`
- changed posts: `0`
- raw collateral_regression_count: `0`
- historical_raw_collateral_regression_count: `null`
- adjusted_drift_count: `0`
- review exclusion candidates: `0`
- review adjustment applied: `False`
- review scope: `None`
- source-native decision rows: `null`
- info missing rows: `null`
- unreviewed or info-missing rows: `null`
- unreviewed regression rows: `None`
- reviewed raw regression rows: `null`
- reviewed non-regression rows: `null`
- review_adjusted_regression_count: `0`
- gate_metric: `adjusted_drift_count`
- gate_regression_count: `0`
- runtime_complete: `False`

## 완료 Gate 해석

판결 baseline이 적용된 상태이므로 완료 gate는 `adjusted_drift_count`를 본다. 2026-06-26 raw diff는 historical compare로만 남긴다.

## Contract 회계 조정

- provided: `false`

## 차단 항목

- `collateral:collateral_runtime_counts_missing`
