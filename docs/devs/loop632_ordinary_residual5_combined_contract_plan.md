# loop632_ordinary_residual5_combined_contract_plan

기존 contract plan에 추가 shared-gate contract plan을 병합한 projection-only 산출물이다.

## 요약

- contract_plan_rows: `5`
- contract_action_counts: `{'candidate_set_expected_restore_contract_case': 3, 'candidate_set_rebuild_required_before_publish': 1, 'canonical_cleanup_or_url_correction_contract_case': 1}`
- promotion_decision_status_counts: `{'candidate_only': 1, 'publish': 3, 'reject': 1}`
- addition_plan_id: `loop632_11669907_canonical_cleanup_contract_plan`
- addition_plan_rows: `1`
- addition_publish_release_candidate_rows: `None`
- addition_candidate_only_no_publish_rows: `None`
- runtime_replay_allowed_rows: `0`
- full375 collateral: `NO-GO`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`

## 추가 행

- `11669907` action=`canonical_cleanup_or_url_correction_contract_case` decision=`candidate_only` target=`마법 좋아좋아좋아`

## Gate 해석

추가 publish 행은 release candidate이며 approval이 아니다. candidate-only 행은 no-publish contract로 보존한다. 완료 기준은 계속 `full375 collateral GO + full_scan path`다.
