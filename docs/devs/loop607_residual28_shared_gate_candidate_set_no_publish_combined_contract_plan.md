# loop607_residual28_shared_gate_candidate_set_no_publish_combined_contract_plan

기존 contract plan에 추가 shared-gate contract plan을 병합한 projection-only 산출물이다.

## 요약

- contract_plan_rows: `14`
- contract_action_counts: `{'candidate_scrub_no_publish_contract_case': 1, 'candidate_set_rebuild_required_before_publish': 8, 'expected_title_restore_contract_case': 3, 'no_publish_intent_guard_contract_case': 2}`
- promotion_decision_status_counts: `{'candidate_only': 3, 'publish': 3, 'reject': 8}`
- addition_plan_id: `loop607_residual15_no_publish_guard_contract_plan`
- addition_plan_rows: `2`
- addition_publish_release_candidate_rows: `0`
- addition_candidate_only_no_publish_rows: `2`
- runtime_replay_allowed_rows: `0`
- full375 collateral: `NO-GO`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`

## 추가 행

- `11698870` action=`no_publish_intent_guard_contract_case` decision=`candidate_only` target=`인간실격`
- `11711632` action=`no_publish_intent_guard_contract_case` decision=`candidate_only` target=`너의 이름은.`

## Gate 해석

추가 publish 행은 release candidate이며 approval이 아니다. candidate-only 행은 no-publish contract로 보존한다. 완료 기준은 계속 `full375 collateral GO + full_scan path`다.
