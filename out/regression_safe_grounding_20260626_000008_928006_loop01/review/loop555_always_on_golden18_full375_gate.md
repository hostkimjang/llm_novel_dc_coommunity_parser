# 상시 회귀 게이트

- gate: `NO-GO`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- 정책: golden-18과 full 375 collateral diff를 항상 함께 요구한다.

## Golden 게이트

- gate: `NO-GO`
- rows: `18/18`
- passed: `17`
- failed: `1`
- runtime_complete: `True`

## Collateral 게이트

- gate: `NO-GO`
- shared posts: `375/375`
- changed posts: `181`
- raw collateral_regression_count: `119`
- review exclusion candidates: `0`
- review adjustment applied: `False`
- review scope: `None`
- unreviewed regression rows: `None`
- review_adjusted_regression_count: `119`
- runtime_complete: `True`

## 차단 항목

- `golden:golden_expected_answer_failures`
- `golden:golden_semantic_gate_not_pass`
- `collateral:collateral_regression_count_nonzero`
