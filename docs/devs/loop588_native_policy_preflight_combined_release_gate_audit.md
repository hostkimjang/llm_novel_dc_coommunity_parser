# loop588_native_policy_preflight_combined_release_gate_audit

Post-verdict promotion-gate contract plan을 current projection 결과에 대조한 release gate 감사다. 이 감사는 새 runtime replay가 아니며, release candidate가 있더라도 full375 collateral GO 전에는 approval이나 full_scan 경로로 보지 않는다.

## 요약

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- contract_plan_rows: `11`
- projection_rows: `375`
- validation_issue_count: `0`
- violation_row_count: `0`
- pending_contract_rows: `0`
- satisfied_no_release_rows: `5`
- release_candidate_after_contract_rows: `6`
- runtime_replay_allowed_rows: `0`
- full375 collateral: `NO-GO`

## Release gate states

- `candidate_set_rebuild_preserved_no_release`: `4`
- `expected_restore_contract_satisfied_release_candidate`: `6`
- `official_support_missing_restore_hold_preserved_no_release`: `1`

## Satisfied no-release rows

- `11698870` action=`official_support_missing_restore_hold_contract_case` state=`official_support_missing_restore_hold_preserved_no_release`
- `11682749` action=`candidate_set_rebuild_required_before_publish` state=`candidate_set_rebuild_preserved_no_release`
- `11703658` action=`candidate_set_rebuild_required_before_publish` state=`candidate_set_rebuild_preserved_no_release`
- `11705231` action=`candidate_set_rebuild_required_before_publish` state=`candidate_set_rebuild_preserved_no_release`
- `11710036` action=`candidate_set_rebuild_required_before_publish` state=`candidate_set_rebuild_preserved_no_release`

## Release candidates

- `11665124` action=`expected_title_restore_contract_case` title=`화산귀환`
- `11710049` action=`expected_title_restore_contract_case` title=`[림월드]변방계에서 회귀자로 살아남기`
- `11718114` action=`expected_title_restore_contract_case` title=`설정값 딸깍으로 판타지 시스템 정상화`
- `11682775` action=`expected_title_restore_contract_case` title=`여자가 되어서라도 복수한다`
- `11700500` action=`expected_title_restore_contract_case` title=`전지적 1인칭 시점`
- `11700483` action=`expected_title_restore_contract_case` title=`니들 생각 다 들린다`

## Gate 해석

현재 projection 기준 pending contract는 `0`건이며 release candidate는 `6`건이다. no-release 유지 행은 `5`건이며, runtime replay allowed는 `0`건이다. full375 collateral은 `NO-GO`, goal은 `ACTIVE / NOT_COMPLETE`다.
