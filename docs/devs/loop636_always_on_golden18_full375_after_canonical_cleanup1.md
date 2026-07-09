# 상시 회귀 게이트

- gate: `NO-GO`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- completion_gate: `adjusted full375 collateral GO + full_scan path`
- completion_gate_metric: `not_open_until_adjudicated_rebaseline`
- current_collateral_gate_metric: `collateral_regression_count`
- rebaseline_status: `NOT_APPLIED`
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
- baseline_mode: `bootstrap_20260626`
- collateral_measure: `historical_raw_vs_20260626`
- changed posts: `182`
- raw collateral_regression_count: `109`
- historical_raw_collateral_regression_count: `109`
- adjusted_drift_count: `null`
- review exclusion candidates: `0`
- review adjustment applied: `False`
- review scope: `None`
- source-native decision rows: `null`
- info missing rows: `null`
- unreviewed or info-missing rows: `null`
- unreviewed regression rows: `None`
- reviewed raw regression rows: `null`
- reviewed non-regression rows: `null`
- review_adjusted_regression_count: `109`
- gate_metric: `collateral_regression_count`
- gate_regression_count: `109`
- runtime_complete: `False`

## 완료 Gate 해석

아직 adjudicated re-baseline이 적용되지 않았으므로 completion gate는 열리지 않는다. 현재 bootstrap raw diff는 진단용이며, 완료 기준은 전 행 판결 후 adjusted full375 collateral GO와 full_scan path다.

## Contract 회계 조정

- provided: `false`

## 차단 항목

- `collateral:collateral_regression_count_nonzero`
- `collateral:collateral_runtime_counts_missing`
