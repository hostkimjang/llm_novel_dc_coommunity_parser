# loop542_b1_missing_candidate_expected_restore_projection_contract

Post-verdict expected-restore publish contract를 current projection row에 적용한 projection-only 산출물이다. 새 runtime replay가 아니며, release candidate가 생겨도 full375 collateral GO 전에는 approval 근거가 아니다.

## 요약

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- projection_rows: `375`
- applied_restore_rows: `1`
- validation_issue_count: `0`
- runtime_replay_allowed_rows: `0`
- full375 collateral: `NO-GO`

## 적용 행

- `11669933` target=`회귀수선전` superseded=`None`

## Gate 해석

expected restore 적용 행 `1`건은 shared PromotionDecision을 projection identity, publish_contract_trace, publish_ledger에 동기화했다. 이 결과는 release gate contract를 닫는 projection 증거이며 runtime replay 또는 full_scan approval이 아니다.
