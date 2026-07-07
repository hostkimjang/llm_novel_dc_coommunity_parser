# loop596_remaining15_shared_gate_projection_application

Post-verdict publish-class contract를 current projection row에 적용한 projection-only 산출물이다. 새 runtime replay가 아니며, release candidate가 생겨도 full375 collateral GO 전에는 approval 근거가 아니다.

## 요약

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- projection_rows: `375`
- applied_publish_contract_rows: `2`
- applied_restore_rows: `2`
- applied_expected_audit_update_rows: `0`
- applied_canonical_cleanup_rows: `0`
- validation_issue_count: `0`
- runtime_replay_allowed_rows: `0`
- full375 collateral: `NO-GO`

## 적용 행

- `11698871` action=`expected_title_restore_contract_case` target=`Re : 제로부터 시작하는 이세계 생활` superseded=`Re : 제로부터 시작하는 이세계 생활`
- `11706844` action=`expected_title_restore_contract_case` target=`호랑이 사냥꾼` superseded=`호랑이 사냥꾼`

## Gate 해석

publish-class contract 적용 행 `2`건은 shared PromotionDecision을 projection identity, publish_contract_trace, publish_ledger에 동기화했다. 이 결과는 release gate contract를 닫는 projection 증거이며 runtime replay 또는 full_scan approval이 아니다.
