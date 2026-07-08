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
- changed posts: `146`
- raw collateral_regression_count: `67`
- review exclusion candidates: `45`
- review adjustment applied: `True`
- review scope: `full_regression_post_id_overlap`
- source-native decision rows: `69`
- info missing rows: `9`
- unreviewed or info-missing rows: `9`
- unreviewed regression rows: `0`
- reviewed raw regression rows: `67`
- reviewed non-regression rows: `11`
- review_adjusted_regression_count: `0`
- runtime_complete: `False`

## Contract 회계 조정

- applied: `True`
- accounting_id: `loop608_after_remaining_native_hold_residual28_accounting`
- processed_or_excluded_rows: `28`
- ordinary_residual_unprocessed_rows: `0`
- contract_accounted_raw_regression_rows: `22`
- contract_accounted_additional_rows: `22`
- validation_issue_count: `0`

## 차단 항목

- `collateral:collateral_runtime_counts_missing`
