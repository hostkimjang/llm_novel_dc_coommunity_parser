# loop535_post_verdict_expected_restore_release_gate_audit

Loop532 promotion-gate contract plan을 current projection 결과에 대조한 release gate 감사다. 이 감사는 새 runtime replay가 아니며, release candidate가 있더라도 full375 collateral GO 전에는 approval이나 full_scan 경로로 보지 않는다.

## 요약

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- contract_plan_rows: `22`
- projection_rows: `57`
- validation_issue_count: `0`
- violation_row_count: `0`
- pending_contract_rows: `0`
- satisfied_no_release_rows: `19`
- release_candidate_after_contract_rows: `3`
- runtime_replay_allowed_rows: `0`
- full375 collateral: `NO-GO`

## Release gate states

- `expected_restore_contract_satisfied_release_candidate`: `3`
- `scrub_contract_satisfied_no_release`: `6`
- `stronger_evidence_hold_preserved_no_release`: `6`
- `variant_policy_hold_satisfied_no_release`: `7`

## Satisfied no-release rows

- `11660273` action=`candidate_scrub_no_publish_contract_case` state=`scrub_contract_satisfied_no_release`
- `11665124` action=`candidate_scrub_no_publish_contract_case` state=`scrub_contract_satisfied_no_release`
- `11669913` action=`candidate_scrub_no_publish_contract_case` state=`scrub_contract_satisfied_no_release`
- `11677926` action=`candidate_scrub_no_publish_contract_case` state=`scrub_contract_satisfied_no_release`
- `11681172` action=`stronger_evidence_hard_hold_contract_case` state=`stronger_evidence_hold_preserved_no_release`
- `11690841` action=`candidate_scrub_no_publish_contract_case` state=`scrub_contract_satisfied_no_release`
- `11697242` action=`candidate_scrub_no_publish_contract_case` state=`scrub_contract_satisfied_no_release`
- `11697256` action=`canonical_variant_policy_hold_contract_case` state=`variant_policy_hold_satisfied_no_release`
- `11710021` action=`canonical_variant_policy_hold_contract_case` state=`variant_policy_hold_satisfied_no_release`
- `11714887` action=`canonical_variant_policy_hold_contract_case` state=`variant_policy_hold_satisfied_no_release`
- `11718110` action=`stronger_evidence_hard_hold_contract_case` state=`stronger_evidence_hold_preserved_no_release`
- `11718114` action=`stronger_evidence_hard_hold_contract_case` state=`stronger_evidence_hold_preserved_no_release`
- `11666741` action=`canonical_variant_policy_hold_contract_case` state=`variant_policy_hold_satisfied_no_release`
- `11694068` action=`canonical_variant_policy_hold_contract_case` state=`variant_policy_hold_satisfied_no_release`
- `11668300` action=`stronger_evidence_hard_hold_contract_case` state=`stronger_evidence_hold_preserved_no_release`
- `11669926` action=`stronger_evidence_hard_hold_contract_case` state=`stronger_evidence_hold_preserved_no_release`
- `11673080` action=`stronger_evidence_hard_hold_contract_case` state=`stronger_evidence_hold_preserved_no_release`
- `11682767` action=`canonical_variant_policy_hold_contract_case` state=`variant_policy_hold_satisfied_no_release`
- `11698859` action=`canonical_variant_policy_hold_contract_case` state=`variant_policy_hold_satisfied_no_release`

## Release candidates

- `11660271` action=`expected_title_restore_contract_case` title=`월야의 여인들`
- `11706871` action=`expected_title_restore_contract_case` title=`파우스트`
- `11679547` action=`expected_title_restore_contract_case` title=`도굴왕`

## Gate 해석

현재 projection 기준 pending contract는 `0`건이며 release candidate는 `3`건이다. no-release 유지 행은 `19`건이며, runtime replay allowed는 `0`건이다. full375 collateral은 `NO-GO`, goal은 `ACTIVE / NOT_COMPLETE`다.
