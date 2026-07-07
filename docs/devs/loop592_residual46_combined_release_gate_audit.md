# loop592_residual46_combined_release_gate_audit

Post-verdict promotion-gate contract plan을 current projection 결과에 대조한 release gate 감사다. 이 감사는 새 runtime replay가 아니며, release candidate가 있더라도 full375 collateral GO 전에는 approval이나 full_scan 경로로 보지 않는다.

## 요약

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- contract_plan_rows: `23`
- projection_rows: `375`
- validation_issue_count: `0`
- violation_row_count: `0`
- pending_contract_rows: `0`
- satisfied_no_release_rows: `15`
- release_candidate_after_contract_rows: `8`
- runtime_replay_allowed_rows: `0`
- full375 collateral: `NO-GO`

## Release gate states

- `candidate_set_rebuild_preserved_no_release`: `13`
- `expected_restore_contract_satisfied_release_candidate`: `8`
- `native_web_disambiguation_hold_preserved_no_release`: `1`
- `non_webnovel_ebook_policy_hold_preserved_no_release`: `1`

## Satisfied no-release rows

- `11661863` action=`candidate_set_rebuild_required_before_publish` state=`candidate_set_rebuild_preserved_no_release`
- `11668324` action=`candidate_set_rebuild_required_before_publish` state=`candidate_set_rebuild_preserved_no_release`
- `11671512` action=`candidate_set_rebuild_required_before_publish` state=`candidate_set_rebuild_preserved_no_release`
- `11671514` action=`candidate_set_rebuild_required_before_publish` state=`candidate_set_rebuild_preserved_no_release`
- `11682749` action=`candidate_set_rebuild_required_before_publish` state=`candidate_set_rebuild_preserved_no_release`
- `11694035` action=`candidate_set_rebuild_required_before_publish` state=`candidate_set_rebuild_preserved_no_release`
- `11694041` action=`candidate_set_rebuild_required_before_publish` state=`candidate_set_rebuild_preserved_no_release`
- `11698859` action=`native_web_disambiguation_hold_contract_case` state=`native_web_disambiguation_hold_preserved_no_release`
- `11698865` action=`candidate_set_rebuild_required_before_publish` state=`candidate_set_rebuild_preserved_no_release`
- `11698870` action=`non_webnovel_ebook_policy_hold_contract_case` state=`non_webnovel_ebook_policy_hold_preserved_no_release`
- `11703658` action=`candidate_set_rebuild_required_before_publish` state=`candidate_set_rebuild_preserved_no_release`
- `11705231` action=`candidate_set_rebuild_required_before_publish` state=`candidate_set_rebuild_preserved_no_release`
- `11708453` action=`candidate_set_rebuild_required_before_publish` state=`candidate_set_rebuild_preserved_no_release`
- `11710036` action=`candidate_set_rebuild_required_before_publish` state=`candidate_set_rebuild_preserved_no_release`
- `11718105` action=`candidate_set_rebuild_required_before_publish` state=`candidate_set_rebuild_preserved_no_release`

## Release candidates

- `11660273` action=`expected_title_restore_contract_case` title=`마도서를 줍다 마법사가 되다`
- `11665124` action=`expected_title_restore_contract_case` title=`화산귀환`
- `11682775` action=`expected_title_restore_contract_case` title=`여자가 되어서라도 복수한다`
- `11682792` action=`expected_title_restore_contract_case` title=`이 무림의 미친년은 나야`
- `11700483` action=`expected_title_restore_contract_case` title=`니들 생각 다 들린다`
- `11700500` action=`expected_title_restore_contract_case` title=`전지적 1인칭 시점`
- `11710049` action=`expected_title_restore_contract_case` title=`[림월드]변방계에서 회귀자로 살아남기`
- `11718114` action=`expected_title_restore_contract_case` title=`설정값 딸깍으로 판타지 시스템 정상화`

## Gate 해석

현재 projection 기준 pending contract는 `0`건이며 release candidate는 `8`건이다. no-release 유지 행은 `15`건이며, runtime replay allowed는 `0`건이다. full375 collateral은 `NO-GO`, goal은 `ACTIVE / NOT_COMPLETE`다.
