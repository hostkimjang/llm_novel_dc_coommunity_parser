# loop608_residual28_all_contracts_combined_contract_plan

기존 contract plan에 추가 shared-gate contract plan을 병합한 projection-only 산출물이다.

## 요약

- contract_plan_rows: `27`
- contract_action_counts: `{'candidate_scrub_no_publish_contract_case': 1, 'candidate_set_rebuild_required_before_publish': 8, 'expected_title_restore_contract_case': 3, 'native_web_disambiguation_hold_contract_case': 13, 'no_publish_intent_guard_contract_case': 2}`
- promotion_decision_status_counts: `{'candidate_only': 16, 'publish': 3, 'reject': 8}`
- addition_plan_id: `loop608_residual13_remaining_native_hold_contract_plan`
- addition_plan_rows: `13`
- addition_publish_release_candidate_rows: `0`
- addition_candidate_only_no_publish_rows: `0`
- runtime_replay_allowed_rows: `0`
- full375 collateral: `NO-GO`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`

## 추가 행

- `11677957` action=`native_web_disambiguation_hold_contract_case` decision=`candidate_only` target=`None`
- `11714913` action=`native_web_disambiguation_hold_contract_case` decision=`candidate_only` target=`None`
- `11661856` action=`native_web_disambiguation_hold_contract_case` decision=`candidate_only` target=`None`
- `11661863` action=`native_web_disambiguation_hold_contract_case` decision=`candidate_only` target=`None`
- `11671512` action=`native_web_disambiguation_hold_contract_case` decision=`candidate_only` target=`None`
- `11681178` action=`native_web_disambiguation_hold_contract_case` decision=`candidate_only` target=`None`
- `11685994` action=`native_web_disambiguation_hold_contract_case` decision=`candidate_only` target=`None`
- `11687661` action=`native_web_disambiguation_hold_contract_case` decision=`candidate_only` target=`None`
- `11716480` action=`native_web_disambiguation_hold_contract_case` decision=`candidate_only` target=`None`
- `11718057` action=`native_web_disambiguation_hold_contract_case` decision=`candidate_only` target=`None`
- `11687635` action=`native_web_disambiguation_hold_contract_case` decision=`candidate_only` target=`None`
- `11694067` action=`native_web_disambiguation_hold_contract_case` decision=`candidate_only` target=`None`
- `11682791` action=`native_web_disambiguation_hold_contract_case` decision=`candidate_only` target=`None`

## Gate 해석

추가 publish 행은 release candidate이며 approval이 아니다. candidate-only 행은 no-publish contract로 보존한다. 완료 기준은 계속 `full375 collateral GO + full_scan path`다.
