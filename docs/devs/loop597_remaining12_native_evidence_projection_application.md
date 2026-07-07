# loop597_remaining12_native_evidence_projection_application

Post-verdict publish-class contract를 current projection row에 적용한 projection-only 산출물이다. 새 runtime replay가 아니며, release candidate가 생겨도 full375 collateral GO 전에는 approval 근거가 아니다.

## 요약

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- projection_rows: `375`
- applied_publish_contract_rows: `6`
- applied_restore_rows: `6`
- applied_expected_audit_update_rows: `0`
- applied_canonical_cleanup_rows: `0`
- validation_issue_count: `0`
- runtime_replay_allowed_rows: `0`
- full375 collateral: `NO-GO`

## 적용 행

- `11661856` action=`expected_title_restore_contract_case` target=`너랑은 절! 대! 안 사갈거니까!` superseded=`None`
- `11665110` action=`expected_title_restore_contract_case` target=`사이키델리아` superseded=`None`
- `11666725` action=`expected_title_restore_contract_case` target=`학대받던 11살 고마가 각성한 이유` superseded=`None`
- `11685994` action=`expected_title_restore_contract_case` target=`교황님 아하세요 마왕 들어 가요` superseded=`None`
- `11694067` action=`expected_title_restore_contract_case` target=`괴담에 휘말렸다` superseded=`None`
- `11682791` action=`expected_title_restore_contract_case` target=`시간을 달리는 소설가` superseded=`None`

## Gate 해석

publish-class contract 적용 행 `6`건은 shared PromotionDecision을 projection identity, publish_contract_trace, publish_ledger에 동기화했다. 이 결과는 release gate contract를 닫는 projection 증거이며 runtime replay 또는 full_scan approval이 아니다.
