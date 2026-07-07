# loop580_candidate_set_release_contract_audit

Post-verdict promotion-gate contract plan을 current projection 결과에 대조한 release gate 감사다. 이 감사는 새 runtime replay가 아니며, release candidate가 있더라도 full375 collateral GO 전에는 approval이나 full_scan 경로로 보지 않는다.

## 요약

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- contract_plan_rows: `10`
- projection_rows: `375`
- validation_issue_count: `0`
- violation_row_count: `0`
- pending_contract_rows: `0`
- satisfied_no_release_rows: `6`
- release_candidate_after_contract_rows: `4`
- runtime_replay_allowed_rows: `0`
- full375 collateral: `NO-GO`

## Release gate states

- `candidate_set_expected_restore_contract_satisfied_release_candidate`: `4`
- `candidate_set_rebuild_preserved_no_release`: `5`
- `no_publish_intent_guard_preserved_no_release`: `1`

## Satisfied no-release rows

- `11671514` action=`candidate_set_rebuild_required_before_publish` state=`candidate_set_rebuild_preserved_no_release`
- `11682749` action=`candidate_set_rebuild_required_before_publish` state=`candidate_set_rebuild_preserved_no_release`
- `11698870` action=`no_publish_intent_guard_contract_case` state=`no_publish_intent_guard_preserved_no_release`
- `11703658` action=`candidate_set_rebuild_required_before_publish` state=`candidate_set_rebuild_preserved_no_release`
- `11705231` action=`candidate_set_rebuild_required_before_publish` state=`candidate_set_rebuild_preserved_no_release`
- `11710036` action=`candidate_set_rebuild_required_before_publish` state=`candidate_set_rebuild_preserved_no_release`

## Release candidates

- `11660241` action=`candidate_set_expected_restore_contract_case` title=`이세계 TRPG 게임마스터`
- `11663514` action=`candidate_set_expected_restore_contract_case` title=`마탄 속의 제국`
- `11674694` action=`candidate_set_expected_restore_contract_case` title=`21세기 무림세가`
- `11716464` action=`candidate_set_expected_restore_contract_case` title=`슈라라펜란트`

## Gate 해석

현재 projection 기준 pending contract는 `0`건이며 release candidate는 `4`건이다. no-release 유지 행은 `6`건이며, runtime replay allowed는 `0`건이다. full375 collateral은 `NO-GO`, goal은 `ACTIVE / NOT_COMPLETE`다.
