# loop608_residual28_all_contracts_release_gate_audit

Post-verdict promotion-gate contract plan을 current projection 결과에 대조한 release gate 감사다. 이 감사는 새 runtime replay가 아니며, release candidate가 있더라도 full375 collateral GO 전에는 approval이나 full_scan 경로로 보지 않는다.

## 요약

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- contract_plan_rows: `27`
- projection_rows: `375`
- validation_issue_count: `0`
- violation_row_count: `0`
- pending_contract_rows: `0`
- satisfied_no_release_rows: `24`
- release_candidate_after_contract_rows: `3`
- runtime_replay_allowed_rows: `0`
- full375 collateral: `NO-GO`

## Release gate states

- `candidate_set_rebuild_preserved_no_release`: `8`
- `expected_restore_contract_satisfied_release_candidate`: `3`
- `native_web_disambiguation_hold_preserved_no_release`: `13`
- `no_publish_intent_guard_preserved_no_release`: `2`
- `scrub_contract_satisfied_no_release`: `1`

## Satisfied no-release rows

- `11710047` action=`candidate_scrub_no_publish_contract_case` state=`scrub_contract_satisfied_no_release`
- `11671514` action=`candidate_set_rebuild_required_before_publish` state=`candidate_set_rebuild_preserved_no_release`
- `11682749` action=`candidate_set_rebuild_required_before_publish` state=`candidate_set_rebuild_preserved_no_release`
- `11694035` action=`candidate_set_rebuild_required_before_publish` state=`candidate_set_rebuild_preserved_no_release`
- `11698865` action=`candidate_set_rebuild_required_before_publish` state=`candidate_set_rebuild_preserved_no_release`
- `11703658` action=`candidate_set_rebuild_required_before_publish` state=`candidate_set_rebuild_preserved_no_release`
- `11705231` action=`candidate_set_rebuild_required_before_publish` state=`candidate_set_rebuild_preserved_no_release`
- `11708453` action=`candidate_set_rebuild_required_before_publish` state=`candidate_set_rebuild_preserved_no_release`
- `11710036` action=`candidate_set_rebuild_required_before_publish` state=`candidate_set_rebuild_preserved_no_release`
- `11698870` action=`no_publish_intent_guard_contract_case` state=`no_publish_intent_guard_preserved_no_release`
- `11711632` action=`no_publish_intent_guard_contract_case` state=`no_publish_intent_guard_preserved_no_release`
- `11677957` action=`native_web_disambiguation_hold_contract_case` state=`native_web_disambiguation_hold_preserved_no_release`
- `11714913` action=`native_web_disambiguation_hold_contract_case` state=`native_web_disambiguation_hold_preserved_no_release`
- `11661856` action=`native_web_disambiguation_hold_contract_case` state=`native_web_disambiguation_hold_preserved_no_release`
- `11661863` action=`native_web_disambiguation_hold_contract_case` state=`native_web_disambiguation_hold_preserved_no_release`
- `11671512` action=`native_web_disambiguation_hold_contract_case` state=`native_web_disambiguation_hold_preserved_no_release`
- `11681178` action=`native_web_disambiguation_hold_contract_case` state=`native_web_disambiguation_hold_preserved_no_release`
- `11685994` action=`native_web_disambiguation_hold_contract_case` state=`native_web_disambiguation_hold_preserved_no_release`
- `11687661` action=`native_web_disambiguation_hold_contract_case` state=`native_web_disambiguation_hold_preserved_no_release`
- `11716480` action=`native_web_disambiguation_hold_contract_case` state=`native_web_disambiguation_hold_preserved_no_release`
- `11718057` action=`native_web_disambiguation_hold_contract_case` state=`native_web_disambiguation_hold_preserved_no_release`
- `11687635` action=`native_web_disambiguation_hold_contract_case` state=`native_web_disambiguation_hold_preserved_no_release`
- `11694067` action=`native_web_disambiguation_hold_contract_case` state=`native_web_disambiguation_hold_preserved_no_release`
- `11682791` action=`native_web_disambiguation_hold_contract_case` state=`native_web_disambiguation_hold_preserved_no_release`

## Release candidates

- `11694041` action=`expected_title_restore_contract_case` title=`격투 소설 엑스트라가 타격 천재임`
- `11698859` action=`expected_title_restore_contract_case` title=`귤부인 대롱대롱`
- `11706844` action=`expected_title_restore_contract_case` title=`호랑이 사냥꾼`

## Gate 해석

현재 projection 기준 pending contract는 `0`건이며 release candidate는 `3`건이다. no-release 유지 행은 `24`건이며, runtime replay allowed는 `0`건이다. full375 collateral은 `NO-GO`, goal은 `ACTIVE / NOT_COMPLETE`다.
