# 상시 회귀 게이트

- gate: `NO-GO`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- 정책: golden-18과 full 375 collateral diff를 항상 함께 요구한다.

## Golden 게이트

- gate: `NO-GO`
- rows: `18/18`
- passed: `null`
- failed: `null`
- runtime_complete: `False`

## Collateral 게이트

- gate: `NO-GO`
- shared posts: `375/375`
- changed posts: `223`
- raw collateral_regression_count: `183`
- review exclusion candidates: `57`
- review adjustment applied: `True`
- review_adjusted_regression_count: `126`
- runtime_complete: `True`

## 차단 항목

- `golden:golden_expected_answer_failures`
- `golden:golden_semantic_gate_not_pass`
- `golden:golden_runtime_not_complete`
- `collateral:collateral_review_adjusted_regression_count_nonzero`
