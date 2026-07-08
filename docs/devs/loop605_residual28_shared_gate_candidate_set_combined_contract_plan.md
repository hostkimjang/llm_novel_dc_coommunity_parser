# loop605_residual28_shared_gate_candidate_set_combined_contract_plan

기존 contract plan에 추가 shared-gate contract plan을 병합한 projection-only 산출물이다.

## 요약

- contract_plan_rows: `12`
- contract_action_counts: `{'candidate_scrub_no_publish_contract_case': 1, 'candidate_set_rebuild_required_before_publish': 8, 'expected_title_restore_contract_case': 3}`
- promotion_decision_status_counts: `{'candidate_only': 1, 'publish': 3, 'reject': 8}`
- addition_plan_id: `loop605_residual24_candidate_set_contract_plan`
- addition_plan_rows: `8`
- addition_publish_release_candidate_rows: `0`
- addition_candidate_only_no_publish_rows: `None`
- runtime_replay_allowed_rows: `0`
- full375 collateral: `NO-GO`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`

## 추가 행

- `11671514` action=`candidate_set_rebuild_required_before_publish` decision=`reject` target=`None`
- `11682749` action=`candidate_set_rebuild_required_before_publish` decision=`reject` target=`None`
- `11694035` action=`candidate_set_rebuild_required_before_publish` decision=`reject` target=`None`
- `11698865` action=`candidate_set_rebuild_required_before_publish` decision=`reject` target=`None`
- `11703658` action=`candidate_set_rebuild_required_before_publish` decision=`reject` target=`None`
- `11705231` action=`candidate_set_rebuild_required_before_publish` decision=`reject` target=`None`
- `11708453` action=`candidate_set_rebuild_required_before_publish` decision=`reject` target=`None`
- `11710036` action=`candidate_set_rebuild_required_before_publish` decision=`reject` target=`None`

## Gate 해석

추가 publish 행은 release candidate이며 approval이 아니다. candidate-only 행은 no-publish contract로 보존한다. 완료 기준은 계속 `full375 collateral GO + full_scan path`다.
