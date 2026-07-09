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
- changed posts: `206`
- raw collateral_regression_count: `137`
- historical_raw_collateral_regression_count: `137`
- adjusted_drift_count: `null`
- review exclusion candidates: `0`
- review adjustment applied: `False`
- review scope: `full_regression_post_id_overlap`
- source-native decision rows: `null`
- info missing rows: `null`
- unreviewed or info-missing rows: `null`
- unreviewed regression rows: `0`
- reviewed raw regression rows: `137`
- reviewed non-regression rows: `0`
- review_adjusted_regression_count: `137`
- gate_metric: `collateral_regression_count`
- gate_regression_count: `137`
- runtime_complete: `True`

## Contract 회계 조정

- provided: `false`

## 차단 항목

- `collateral:collateral_review_validation_issues_nonzero`
- `collateral:collateral_review_counts_missing`
- `collateral:collateral_regression_count_nonzero`
