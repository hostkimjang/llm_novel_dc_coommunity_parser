# loop605_residual28_shared_gate_candidate_set_combined_projection_application

기존 projection application에 추가 shared-gate publish-class 적용 행을 병합한 projection-only 산출물이다.

## 요약

- applied_publish_contract_rows: `3`
- addition_projection_id: `loop605_residual24_candidate_set_projection_application`
- addition_applied_rows: `8`
- applied_restore_rows: `3`
- applied_canonical_cleanup_rows: `0`
- skipped_contract_action_counts: `{'candidate_scrub_no_publish_contract_case': 1}`
- runtime_replay_allowed_rows: `0`
- full375 collateral: `NO-GO`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`

## 추가 적용 행

- `11671514` action=`candidate_set_rebuild_required_before_publish` target=`None` url=`None`
- `11682749` action=`candidate_set_rebuild_required_before_publish` target=`None` url=`None`
- `11694035` action=`candidate_set_rebuild_required_before_publish` target=`None` url=`None`
- `11698865` action=`candidate_set_rebuild_required_before_publish` target=`None` url=`None`
- `11703658` action=`candidate_set_rebuild_required_before_publish` target=`None` url=`None`
- `11705231` action=`candidate_set_rebuild_required_before_publish` target=`None` url=`None`
- `11708453` action=`candidate_set_rebuild_required_before_publish` target=`None` url=`None`
- `11710036` action=`candidate_set_rebuild_required_before_publish` target=`None` url=`None`

## Gate 해석

적용 행은 shared `PromotionDecision`/`publish_contract_trace`/`publish_ledger` 동기화 증거다. 새 runtime replay나 full_scan approval이 아니다.
