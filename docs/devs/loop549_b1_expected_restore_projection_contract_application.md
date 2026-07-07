# loop549_b1_expected_restore_projection_contract

Post-verdict publish-class contract를 current projection row에 적용한 projection-only 산출물이다. 새 runtime replay가 아니며, release candidate가 생겨도 full375 collateral GO 전에는 approval 근거가 아니다.

## 요약

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- projection_rows: `49`
- applied_publish_contract_rows: `3`
- applied_restore_rows: `3`
- applied_expected_audit_update_rows: `0`
- applied_canonical_cleanup_rows: `0`
- validation_issue_count: `0`
- runtime_replay_allowed_rows: `0`
- full375 collateral: `NO-GO`

## 적용 행

- `11668325` action=`expected_title_restore_contract_case` target=`Fate/stay night` superseded=`마파두부를 너무나도 좋아하는 신부님의 키보토스 생활`
- `11710049` action=`expected_title_restore_contract_case` target=`[림월드]변방계에서 회귀자로 살아남기` superseded=`변방계 행성 하렘 생존기`
- `11718099` action=`expected_title_restore_contract_case` target=`빌어먹을 환생` superseded=`불을 먹을 환생`

## Gate 해석

publish-class contract 적용 행 `3`건은 shared PromotionDecision을 projection identity, publish_contract_trace, publish_ledger에 동기화했다. 이 결과는 release gate contract를 닫는 projection 증거이며 runtime replay 또는 full_scan approval이 아니다.
