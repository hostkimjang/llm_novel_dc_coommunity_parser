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
- changed posts: `154`
- raw collateral_regression_count: `75`
- review exclusion candidates: `7`
- review adjustment applied: `True`
- review scope: `p0_scoped`
- source-native decision rows: `16`
- info missing rows: `9`
- unreviewed or info-missing rows: `9`
- unreviewed regression rows: `50`
- review_adjusted_regression_count: `68`
- runtime_complete: `False`

## 차단 항목

- `collateral:collateral_review_adjusted_regression_count_nonzero`
- `collateral:collateral_review_unreviewed_regression_rows_nonzero`
- `collateral:collateral_runtime_counts_missing`
