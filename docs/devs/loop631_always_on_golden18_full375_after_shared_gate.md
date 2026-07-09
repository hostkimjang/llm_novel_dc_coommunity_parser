# 상시 회귀 게이트

- gate: `NO-GO`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
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
- changed posts: `193`
- raw collateral_regression_count: `124`
- historical_raw_collateral_regression_count: `124`
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
- review_adjusted_regression_count: `124`
- gate_metric: `collateral_regression_count`
- gate_regression_count: `124`
- runtime_complete: `False`

## Contract 회계 조정

- provided: `false`

## 차단 항목

- `collateral:collateral_regression_count_nonzero`
- `collateral:collateral_runtime_counts_missing`
