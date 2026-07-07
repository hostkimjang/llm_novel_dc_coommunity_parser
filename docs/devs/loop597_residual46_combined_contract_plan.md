# loop597_residual46_combined_contract_plan

기존 contract plan에 추가 shared-gate contract plan을 병합한 projection-only 산출물이다.

## 요약

- contract_plan_rows: `35`
- contract_action_counts: `{'candidate_scrub_no_publish_contract_case': 3, 'candidate_set_rebuild_required_before_publish': 13, 'canonical_cleanup_or_url_correction_contract_case': 1, 'expected_title_restore_contract_case': 16, 'native_web_disambiguation_hold_contract_case': 1, 'non_webnovel_ebook_policy_hold_contract_case': 1}`
- promotion_decision_status_counts: `{'candidate_only': 2, 'hold': 2, 'publish': 16, 'reject': 15}`
- addition_plan_id: `loop597_remaining12_native_evidence_contract_plan`
- addition_plan_rows: `8`
- addition_publish_release_candidate_rows: `6`
- addition_candidate_only_no_publish_rows: `2`
- runtime_replay_allowed_rows: `0`
- full375 collateral: `NO-GO`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`

## 추가 행

- `11661856` action=`expected_title_restore_contract_case` decision=`publish` target=`너랑은 절! 대! 안 사갈거니까!`
- `11665110` action=`expected_title_restore_contract_case` decision=`publish` target=`사이키델리아`
- `11666725` action=`expected_title_restore_contract_case` decision=`publish` target=`학대받던 11살 고마가 각성한 이유`
- `11681178` action=`candidate_scrub_no_publish_contract_case` decision=`reject` target=`None`
- `11685994` action=`expected_title_restore_contract_case` decision=`publish` target=`교황님 아하세요 마왕 들어 가요`
- `11711632` action=`candidate_scrub_no_publish_contract_case` decision=`reject` target=`None`
- `11694067` action=`expected_title_restore_contract_case` decision=`publish` target=`괴담에 휘말렸다`
- `11682791` action=`expected_title_restore_contract_case` decision=`publish` target=`시간을 달리는 소설가`

## Gate 해석

추가 publish 행은 release candidate이며 approval이 아니다. candidate-only 행은 no-publish contract로 보존한다. 완료 기준은 계속 `full375 collateral GO + full_scan path`다.
