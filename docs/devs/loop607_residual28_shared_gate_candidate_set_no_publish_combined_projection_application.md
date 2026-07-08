# loop607_residual28_shared_gate_candidate_set_no_publish_combined_projection_application

기존 projection application에 추가 shared-gate publish-class 적용 행을 병합한 projection-only 산출물이다.

## 요약

- applied_publish_contract_rows: `3`
- addition_projection_id: `loop607_residual15_no_publish_guard_projection_application`
- addition_applied_rows: `2`
- applied_restore_rows: `3`
- applied_canonical_cleanup_rows: `0`
- skipped_contract_action_counts: `{'candidate_scrub_no_publish_contract_case': 1}`
- runtime_replay_allowed_rows: `0`
- full375 collateral: `NO-GO`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`

## 추가 적용 행

- `11698870` action=`no_publish_intent_guard_contract_case` target=`None` url=`None`
- `11711632` action=`no_publish_intent_guard_contract_case` target=`None` url=`None`

## Gate 해석

적용 행은 shared `PromotionDecision`/`publish_contract_trace`/`publish_ledger` 동기화 증거다. 새 runtime replay나 full_scan approval이 아니다.
