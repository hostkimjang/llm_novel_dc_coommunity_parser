# loop638_candidate_set6_official_support_release_gate_audit

Post-verdict promotion-gate contract plan을 current projection 결과에 대조한 release gate 감사다. 이 감사는 새 runtime replay가 아니며, release candidate가 있더라도 full375 collateral GO 전에는 approval이나 full_scan 경로로 보지 않는다.

## 요약

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- contract_plan_rows: `6`
- projection_rows: `375`
- validation_issue_count: `0`
- violation_row_count: `0`
- pending_contract_rows: `0`
- satisfied_no_release_rows: `0`
- release_candidate_after_contract_rows: `6`
- runtime_replay_allowed_rows: `0`
- full375 collateral: `NO-GO`

## Release gate states

- `candidate_set_expected_restore_contract_satisfied_release_candidate`: `6`

## Release candidates

- `11660257` action=`candidate_set_expected_restore_contract_case` title=`암흑가 보스요? 제가요?`
- `11694065` action=`candidate_set_expected_restore_contract_case` title=`아카데미에서 살아남기`
- `11698877` action=`candidate_set_expected_restore_contract_case` title=`괴담 호텔 탈출기`
- `11703631` action=`candidate_set_expected_restore_contract_case` title=`나의 악당들`
- `11673102` action=`candidate_set_expected_restore_contract_case` title=`댓글 보는 천재 의사`
- `11676309` action=`candidate_set_expected_restore_contract_case` title=`댓글 보는 천재 의사`

## Gate 해석

현재 projection 기준 pending contract는 `0`건이며 release candidate는 `6`건이다. no-release 유지 행은 `0`건이며, runtime replay allowed는 `0`건이다. full375 collateral은 `NO-GO`, goal은 `ACTIVE / NOT_COMPLETE`다.
