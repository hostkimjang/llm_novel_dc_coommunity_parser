# loop566_title_mismatch_post_apply_release_gate_audit

Post-verdict promotion-gate contract plan을 current projection 결과에 대조한 release gate 감사다. 이 감사는 새 runtime replay가 아니며, release candidate가 있더라도 full375 collateral GO 전에는 approval이나 full_scan 경로로 보지 않는다.

## 요약

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- contract_plan_rows: `2`
- projection_rows: `30`
- validation_issue_count: `0`
- violation_row_count: `0`
- pending_contract_rows: `0`
- satisfied_no_release_rows: `0`
- release_candidate_after_contract_rows: `2`
- runtime_replay_allowed_rows: `0`
- full375 collateral: `NO-GO`

## Release gate states

- `canonical_cleanup_contract_satisfied_release_candidate`: `1`
- `expected_audit_update_contract_satisfied_release_candidate`: `1`

## Release candidates

- `11665121` action=`expected_audit_update_exclusion_contract_case` title=`후회 안 하는 프로듀서 [독점]`
- `11673080` action=`canonical_cleanup_or_url_correction_contract_case` title=`갤질하는 천재 의사`

## Gate 해석

현재 projection 기준 pending contract는 `0`건이며 release candidate는 `2`건이다. no-release 유지 행은 `0`건이며, runtime replay allowed는 `0`건이다. full375 collateral은 `NO-GO`, goal은 `ACTIVE / NOT_COMPLETE`다.
