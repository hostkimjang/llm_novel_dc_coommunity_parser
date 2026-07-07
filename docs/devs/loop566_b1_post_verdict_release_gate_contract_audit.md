# loop566_b1_post_verdict_release_gate_contract_audit

Post-verdict promotion-gate contract plan을 current projection 결과에 대조한 release gate 감사다. 이 감사는 새 runtime replay가 아니며, release candidate가 있더라도 full375 collateral GO 전에는 approval이나 full_scan 경로로 보지 않는다.

## 요약

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- contract_plan_rows: `15`
- projection_rows: `30`
- validation_issue_count: `0`
- violation_row_count: `0`
- pending_contract_rows: `6`
- satisfied_no_release_rows: `9`
- release_candidate_after_contract_rows: `0`
- runtime_replay_allowed_rows: `0`
- full375 collateral: `NO-GO`

## Release gate states

- `expected_restore_contract_pending_projection_not_restored`: `6`
- `scrub_contract_satisfied_no_release`: `6`
- `stronger_evidence_hold_preserved_no_release`: `3`

## Pending contract rows

- `11663557` action=`expected_title_restore_contract_case` state=`expected_restore_contract_pending_projection_not_restored` target=`퇴마록`
- `11668325` action=`expected_title_restore_contract_case` state=`expected_restore_contract_pending_projection_not_restored` target=`Fate/stay night`
- `11669913` action=`expected_title_restore_contract_case` state=`expected_restore_contract_pending_projection_not_restored` target=`하룬`
- `11677924` action=`expected_title_restore_contract_case` state=`expected_restore_contract_pending_projection_not_restored` target=`고결에 오만이 깃들 때`
- `11681159` action=`expected_title_restore_contract_case` state=`expected_restore_contract_pending_projection_not_restored` target=`괴담에 휘말렸다`
- `11714887` action=`expected_title_restore_contract_case` state=`expected_restore_contract_pending_projection_not_restored` target=`도굴왕 1 |`

## Satisfied no-release rows

- `11666713` action=`candidate_scrub_no_publish_contract_case` state=`scrub_contract_satisfied_no_release`
- `11666741` action=`candidate_scrub_no_publish_contract_case` state=`scrub_contract_satisfied_no_release`
- `11669926` action=`candidate_scrub_no_publish_contract_case` state=`scrub_contract_satisfied_no_release`
- `11692436` action=`stronger_evidence_hard_hold_contract_case` state=`stronger_evidence_hold_preserved_no_release`
- `11697242` action=`stronger_evidence_hard_hold_contract_case` state=`stronger_evidence_hold_preserved_no_release`
- `11697256` action=`candidate_scrub_no_publish_contract_case` state=`scrub_contract_satisfied_no_release`
- `11700483` action=`candidate_scrub_no_publish_contract_case` state=`scrub_contract_satisfied_no_release`
- `11706831` action=`candidate_scrub_no_publish_contract_case` state=`scrub_contract_satisfied_no_release`
- `11718114` action=`stronger_evidence_hard_hold_contract_case` state=`stronger_evidence_hold_preserved_no_release`

## Gate 해석

현재 projection 기준 pending contract는 `6`건이고 release candidate는 `0`건이다. no-release 유지 행은 `9`건이며, runtime replay allowed는 `0`건이다. full375 collateral은 `NO-GO`, goal은 `ACTIVE / NOT_COMPLETE`다.
