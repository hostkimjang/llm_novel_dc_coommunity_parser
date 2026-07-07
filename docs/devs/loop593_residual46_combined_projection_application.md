# loop593_residual46_combined_projection_application

Post-verdict publish-class contract를 current projection row에 적용한 projection-only 산출물이다. 새 runtime replay가 아니며, release candidate가 생겨도 full375 collateral GO 전에는 approval 근거가 아니다.

## 요약

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- projection_rows: `375`
- applied_publish_contract_rows: `9`
- applied_restore_rows: `8`
- applied_expected_audit_update_rows: `0`
- applied_canonical_cleanup_rows: `1`
- validation_issue_count: `0`
- runtime_replay_allowed_rows: `0`
- full375 collateral: `NO-GO`

## 적용 행

- `11660273` action=`expected_title_restore_contract_case` target=`마도서를 줍다 마법사가 되다` superseded=`그리즐리 그랑`
- `11665124` action=`expected_title_restore_contract_case` target=`화산귀환` superseded=`None`
- `11682775` action=`expected_title_restore_contract_case` target=`여자가 되어서라도 복수한다` superseded=`None`
- `11682792` action=`expected_title_restore_contract_case` target=`이 무림의 미친년은 나야` superseded=`[무친년]이 무림의 미친놈`
- `11700483` action=`expected_title_restore_contract_case` target=`니들 생각 다 들린다` superseded=`None`
- `11700500` action=`expected_title_restore_contract_case` target=`전지적 1인칭 시점` superseded=`None`
- `11710049` action=`expected_title_restore_contract_case` target=`[림월드]변방계에서 회귀자로 살아남기` superseded=`None`
- `11718114` action=`expected_title_restore_contract_case` target=`설정값 딸깍으로 판타지 시스템 정상화` superseded=`None`
- `11669907` action=`canonical_cleanup_or_url_correction_contract_case` target=`마법 좋아좋아좋아` superseded=`약스포) 마법 좋아좋아좋아`

## Gate 해석

publish-class contract 적용 행 `9`건은 shared PromotionDecision을 projection identity, publish_contract_trace, publish_ledger에 동기화했다. 이 결과는 release gate contract를 닫는 projection 증거이며 runtime replay 또는 full_scan approval이 아니다.
