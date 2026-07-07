# loop542_b1_missing_candidate_pre_apply_release_gate_audit

Post-verdict promotion-gate contract plan을 current projection 결과에 대조한 release gate 감사다. 이 감사는 새 runtime replay가 아니며, release candidate가 있더라도 full375 collateral GO 전에는 approval이나 full_scan 경로로 보지 않는다.

## 요약

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- contract_plan_rows: `11`
- projection_rows: `375`
- validation_issue_count: `0`
- violation_row_count: `0`
- pending_contract_rows: `1`
- satisfied_no_release_rows: `10`
- release_candidate_after_contract_rows: `0`
- runtime_replay_allowed_rows: `0`
- full375 collateral: `NO-GO`

## Release gate states

- `expected_restore_contract_pending_projection_not_restored`: `1`
- `scrub_contract_satisfied_no_release`: `5`
- `stronger_evidence_hold_preserved_no_release`: `5`

## Pending contract rows

- `11669933` action=`expected_title_restore_contract_case` state=`expected_restore_contract_pending_projection_not_restored` target=`회귀수선전`

## Satisfied no-release rows

- `11669913` action=`stronger_evidence_hard_hold_contract_case` state=`stronger_evidence_hold_preserved_no_release`
- `11697242` action=`stronger_evidence_hard_hold_contract_case` state=`stronger_evidence_hold_preserved_no_release`
- `11697256` action=`candidate_scrub_no_publish_contract_case` state=`scrub_contract_satisfied_no_release`
- `11718114` action=`stronger_evidence_hard_hold_contract_case` state=`stronger_evidence_hold_preserved_no_release`
- `11666741` action=`candidate_scrub_no_publish_contract_case` state=`scrub_contract_satisfied_no_release`
- `11694068` action=`candidate_scrub_no_publish_contract_case` state=`scrub_contract_satisfied_no_release`
- `11663511` action=`candidate_scrub_no_publish_contract_case` state=`scrub_contract_satisfied_no_release`
- `11669926` action=`stronger_evidence_hard_hold_contract_case` state=`stronger_evidence_hold_preserved_no_release`
- `11677924` action=`stronger_evidence_hard_hold_contract_case` state=`stronger_evidence_hold_preserved_no_release`
- `11706831` action=`candidate_scrub_no_publish_contract_case` state=`scrub_contract_satisfied_no_release`

## Gate 해석

현재 projection 기준 pending contract는 `1`건이고 release candidate는 `0`건이다. no-release 유지 행은 `10`건이며, runtime replay allowed는 `0`건이다. full375 collateral은 `NO-GO`, goal은 `ACTIVE / NOT_COMPLETE`다.
