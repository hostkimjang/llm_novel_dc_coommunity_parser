# loop608_residual28_all_contracts_combined_projection_application

기존 projection application에 추가 shared-gate publish-class 적용 행을 병합한 projection-only 산출물이다.

## 요약

- applied_publish_contract_rows: `3`
- addition_projection_id: `loop608_residual13_remaining_native_hold_projection_application`
- addition_applied_rows: `13`
- applied_restore_rows: `3`
- applied_canonical_cleanup_rows: `0`
- skipped_contract_action_counts: `{'candidate_scrub_no_publish_contract_case': 1}`
- runtime_replay_allowed_rows: `0`
- full375 collateral: `NO-GO`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`

## 추가 적용 행

- `11681178` action=`native_web_disambiguation_hold_contract_case` target=`None` url=`None`
- `11687635` action=`native_web_disambiguation_hold_contract_case` target=`None` url=`None`
- `11714913` action=`native_web_disambiguation_hold_contract_case` target=`None` url=`None`
- `11718057` action=`native_web_disambiguation_hold_contract_case` target=`None` url=`None`
- `11685994` action=`native_web_disambiguation_hold_contract_case` target=`None` url=`None`
- `11687661` action=`native_web_disambiguation_hold_contract_case` target=`None` url=`None`
- `11694067` action=`native_web_disambiguation_hold_contract_case` target=`None` url=`None`
- `11677957` action=`native_web_disambiguation_hold_contract_case` target=`None` url=`None`
- `11661856` action=`native_web_disambiguation_hold_contract_case` target=`None` url=`None`
- `11661863` action=`native_web_disambiguation_hold_contract_case` target=`None` url=`None`
- `11671512` action=`native_web_disambiguation_hold_contract_case` target=`None` url=`None`
- `11682791` action=`native_web_disambiguation_hold_contract_case` target=`None` url=`None`
- `11716480` action=`native_web_disambiguation_hold_contract_case` target=`None` url=`None`

## Gate 해석

적용 행은 shared `PromotionDecision`/`publish_contract_trace`/`publish_ledger` 동기화 증거다. 새 runtime replay나 full_scan approval이 아니다.
