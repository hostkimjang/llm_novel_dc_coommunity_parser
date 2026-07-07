# loop535_current_full375_canonical_post_verdict_projection_contract_audit

이 감사는 Loop530 post-verdict contract queue를 current projection 결과에 대조한다. 위반이 없어도 contract test나 stronger evidence가 닫힌 것은 아니므로 runtime replay는 계속 금지한다.

## 요약

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- contract_queue_rows: `22`
- violation_row_count: `0`
- pending_contract_rows: `14`
- satisfied_contract_rows: `8`
- runtime_replay_allowed_rows: `0`
- full375 collateral: `NO-GO`

## Outcome counts

- `candidate_scrub_satisfied_expected_restore_pending`: `5`
- `expected_contract_pending_unknown_projection_state`: `1`
- `expected_title_restored`: `3`
- `hard_hold_pending_unknown_projection_state`: `1`
- `hard_hold_preserved`: `5`
- `variant_policy_pending_no_publish`: `6`
- `variant_policy_pending_unknown_projection_state`: `1`

## Pending

- `11660273` `C1_expected_restore_or_candidate_scrub_contract` outcome=`candidate_scrub_satisfied_expected_restore_pending`
- `11665124` `C1_expected_restore_or_candidate_scrub_contract` outcome=`candidate_scrub_satisfied_expected_restore_pending`
- `11669913` `C1_expected_restore_or_candidate_scrub_contract` outcome=`candidate_scrub_satisfied_expected_restore_pending`
- `11677926` `C1_expected_restore_or_candidate_scrub_contract` outcome=`candidate_scrub_satisfied_expected_restore_pending`
- `11681172` `C3_stronger_evidence_or_native_web_hold` outcome=`hard_hold_pending_unknown_projection_state`
- `11690841` `C1_expected_restore_or_candidate_scrub_contract` outcome=`candidate_scrub_satisfied_expected_restore_pending`
- `11697242` `C1_expected_restore_or_candidate_scrub_contract` outcome=`expected_contract_pending_unknown_projection_state`
- `11697256` `C2_canonical_variant_policy_contract` outcome=`variant_policy_pending_no_publish`
- `11710021` `C2_canonical_variant_policy_contract` outcome=`variant_policy_pending_unknown_projection_state`
- `11714887` `C2_canonical_variant_policy_contract` outcome=`variant_policy_pending_no_publish`
- `11666741` `C2_canonical_variant_policy_contract` outcome=`variant_policy_pending_no_publish`
- `11694068` `C2_canonical_variant_policy_contract` outcome=`variant_policy_pending_no_publish`
- `11682767` `C2_canonical_variant_policy_contract` outcome=`variant_policy_pending_no_publish`
- `11698859` `C2_canonical_variant_policy_contract` outcome=`variant_policy_pending_no_publish`

## Gate 해석

현재 projection은 current candidate 누출과 C3 hard-hold release 위반은 보이지 않지만, C1 expected restore와 C2 variant policy는 별도 contract test 전까지 pending이다. 따라서 full375 collateral은 `NO-GO`, goal은 `ACTIVE / NOT_COMPLETE`다.
