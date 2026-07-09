# loop634_shared_gate_residual6_release_gate_audit

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

- `expected_restore_contract_satisfied_release_candidate`: `6`

## Release candidates

- `11660241` action=`expected_title_restore_contract_case` title=`이세계 TRPG 게임마스터`
- `11660268` action=`expected_title_restore_contract_case` title=`■■을 위한 세계는 없다`
- `11663511` action=`expected_title_restore_contract_case` title=`부캐 키우는 황태자님`
- `11676321` action=`expected_title_restore_contract_case` title=`마도서를 줍다 마법사가 되다`
- `11682767` action=`expected_title_restore_contract_case` title=`묵향`
- `11708443` action=`expected_title_restore_contract_case` title=`괴담에 떨어져도 출근을 해야 하는구나`

## Gate 해석

현재 projection 기준 pending contract는 `0`건이며 release candidate는 `6`건이다. no-release 유지 행은 `0`건이며, runtime replay allowed는 `0`건이다. full375 collateral은 `NO-GO`, goal은 `ACTIVE / NOT_COMPLETE`다.
