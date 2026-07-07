# loop598_residual46_combined_projection_application

기존 projection application에 추가 shared-gate publish-class 적용 행을 병합한 projection-only 산출물이다.

## 요약

- applied_publish_contract_rows: `17`
- addition_projection_id: `loop598_remaining4_native_hold_projection_application`
- addition_applied_rows: `4`
- applied_restore_rows: `16`
- applied_canonical_cleanup_rows: `1`
- skipped_contract_action_counts: `{'candidate_set_rebuild_required_before_publish': 13, 'native_web_disambiguation_hold_contract_case': 1, 'non_webnovel_ebook_policy_hold_contract_case': 1, 'candidate_scrub_no_publish_contract_case': 3}`
- runtime_replay_allowed_rows: `0`
- full375 collateral: `NO-GO`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`

## 추가 적용 행

- `11671538` action=`native_web_disambiguation_hold_contract_case` target=`None` url=`None`
- `11718057` action=`native_web_disambiguation_hold_contract_case` target=`None` url=`None`
- `11687661` action=`native_web_disambiguation_hold_contract_case` target=`None` url=`None`
- `11716480` action=`native_web_disambiguation_hold_contract_case` target=`None` url=`None`

## Gate 해석

적용 행은 shared `PromotionDecision`/`publish_contract_trace`/`publish_ledger` 동기화 증거다. 새 runtime replay나 full_scan approval이 아니다.
