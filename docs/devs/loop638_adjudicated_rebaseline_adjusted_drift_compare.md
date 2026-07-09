# loop638_adjudicated_rebaseline_adjusted_drift_compare

projection 결과를 판결 baseline full375와 비교한 정적 adjusted_drift collateral diff다. runtime 375 완주가 아니므로 drift가 0이어도 full_scan approval은 열리지 않는다.

## 요약

- gate: `REVIEW-LOCKED`
- projection_static_collateral_gate: `GO`
- runtime_collateral_gate: `NO-GO`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- baseline_mode: `adjudicated_rebaseline`
- collateral_measure: `adjusted_drift`
- shared posts: `375/375`
- changed rows: `0`
- raw collateral_regression_count: `0`
- adjusted_drift_count: `0`
- historical_raw_collateral_regression_count: `None`
- status_counts: `{}`
- regression_status_counts: `{}`
- runtime counts: `missing`

## 차단 항목

- `collateral_runtime_counts_missing`

## Gate 해석

판결 baseline 대비 adjusted_drift는 0건이다. 단 이 산출물만으로 full_scan approval을 열지 않고 always-on gate와 full_scan 경로 조건을 함께 확인한다.
