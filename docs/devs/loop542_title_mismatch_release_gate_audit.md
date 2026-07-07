# loop542_title_mismatch_release_gate_audit

Post-verdict promotion-gate contract plan을 current projection 결과에 대조한 release gate 감사다. 이 감사는 새 runtime replay가 아니며, release candidate가 있더라도 full375 collateral GO 전에는 approval이나 full_scan 경로로 보지 않는다.

## 요약

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- contract_plan_rows: `3`
- projection_rows: `375`
- validation_issue_count: `0`
- violation_row_count: `0`
- pending_contract_rows: `2`
- satisfied_no_release_rows: `1`
- release_candidate_after_contract_rows: `0`
- runtime_replay_allowed_rows: `0`
- full375 collateral: `NO-GO`

## Release gate states

- `canonical_cleanup_contract_pending_projection_not_restored`: `1`
- `expected_audit_update_contract_pending_projection_not_restored`: `1`
- `native_web_disambiguation_hold_preserved_no_release`: `1`

## Pending contract rows

- `11660277` action=`expected_audit_update_exclusion_contract_case` state=`expected_audit_update_contract_pending_projection_not_restored` target=`아카메디 아카데미`
- `11718098` action=`canonical_cleanup_or_url_correction_contract_case` state=`canonical_cleanup_contract_pending_projection_not_restored` target=`마법 좋아좋아좋아`

## Satisfied no-release rows

- `11694063` action=`native_web_disambiguation_hold_contract_case` state=`native_web_disambiguation_hold_preserved_no_release`

## Gate 해석

현재 projection 기준 pending contract는 `2`건이고 release candidate는 `0`건이다. no-release 유지 행은 `1`건이며, runtime replay allowed는 `0`건이다. full375 collateral은 `NO-GO`, goal은 `ACTIVE / NOT_COMPLETE`다.
