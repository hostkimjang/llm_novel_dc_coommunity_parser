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
- changed posts: `171`
- raw collateral_regression_count: `117`
- review exclusion candidates: `39`
- review adjustment applied: `True`
- review scope: `full_regression`
- source-native decision rows: `97`
- info missing rows: `20`
- unreviewed or info-missing rows: `20`
- unreviewed regression rows: `0`
- review_adjusted_regression_count: `78`
- runtime_complete: `True`

## 차단 항목

- `collateral:collateral_review_adjusted_regression_count_nonzero`
