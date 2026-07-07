# loop598_residual46_combined_contract_plan

기존 contract plan에 추가 shared-gate contract plan을 병합한 projection-only 산출물이다.

## 요약

- contract_plan_rows: `39`
- contract_action_counts: `{'candidate_scrub_no_publish_contract_case': 3, 'candidate_set_rebuild_required_before_publish': 13, 'canonical_cleanup_or_url_correction_contract_case': 1, 'expected_title_restore_contract_case': 16, 'native_web_disambiguation_hold_contract_case': 5, 'non_webnovel_ebook_policy_hold_contract_case': 1}`
- promotion_decision_status_counts: `{'candidate_only': 6, 'hold': 2, 'publish': 16, 'reject': 15}`
- addition_plan_id: `loop598_remaining4_native_hold_contract_plan`
- addition_plan_rows: `4`
- addition_publish_release_candidate_rows: `0`
- addition_candidate_only_no_publish_rows: `0`
- runtime_replay_allowed_rows: `0`
- full375 collateral: `NO-GO`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`

## 추가 행

- `11687661` action=`native_web_disambiguation_hold_contract_case` decision=`candidate_only` target=`None`
- `11716480` action=`native_web_disambiguation_hold_contract_case` decision=`candidate_only` target=`None`
- `11718057` action=`native_web_disambiguation_hold_contract_case` decision=`candidate_only` target=`None`
- `11671538` action=`native_web_disambiguation_hold_contract_case` decision=`candidate_only` target=`None`

## Gate 해석

추가 publish 행은 release candidate이며 approval이 아니다. candidate-only 행은 no-publish contract로 보존한다. 완료 기준은 계속 `full375 collateral GO + full_scan path`다.
