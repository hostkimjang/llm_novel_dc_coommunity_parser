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
- changed posts: `196`
- raw collateral_regression_count: `139`
- review exclusion candidates: `37`
- review adjustment applied: `True`
- review scope: `p0_scoped`
- source-native decision rows: `69`
- info missing rows: `9`
- unreviewed or info-missing rows: `9`
- unreviewed regression rows: `74`
- reviewed raw regression rows: `65`
- reviewed non-regression rows: `13`
- review_adjusted_regression_count: `78`
- runtime_complete: `False`

## Contract 회계 조정

- applied: `True`
- accounting_id: `loop608_after_remaining_native_hold_residual28_accounting`
- processed_or_excluded_rows: `28`
- ordinary_residual_unprocessed_rows: `0`
- contract_accounted_raw_regression_rows: `24`
- contract_accounted_additional_rows: `24`
- validation_issue_count: `0`

## 차단 항목

- `collateral:collateral_review_adjusted_regression_count_nonzero`
- `collateral:collateral_review_unreviewed_regression_rows_nonzero`
- `collateral:collateral_runtime_counts_missing`
