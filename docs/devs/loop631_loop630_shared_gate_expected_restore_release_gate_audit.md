# loop631_loop630_shared_gate_expected_restore_release_gate_audit

Post-verdict promotion-gate contract plan을 current projection 결과에 대조한 release gate 감사다. 이 감사는 새 runtime replay가 아니며, release candidate가 있더라도 full375 collateral GO 전에는 approval이나 full_scan 경로로 보지 않는다.

## 요약

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- contract_plan_rows: `13`
- projection_rows: `375`
- validation_issue_count: `0`
- violation_row_count: `0`
- pending_contract_rows: `0`
- satisfied_no_release_rows: `0`
- release_candidate_after_contract_rows: `13`
- runtime_replay_allowed_rows: `0`
- full375 collateral: `NO-GO`

## Release gate states

- `expected_restore_contract_satisfied_release_candidate`: `13`

## Release candidates

- `11660271` action=`expected_title_restore_contract_case` title=`월야의 여인들`
- `11660273` action=`expected_title_restore_contract_case` title=`마도서를 줍다 마법사가 되다`
- `11663557` action=`expected_title_restore_contract_case` title=`퇴마록`
- `11668325` action=`expected_title_restore_contract_case` title=`Fate/stay night`
- `11677926` action=`expected_title_restore_contract_case` title=`재앙급 막내 공자의 회귀`
- `11698910` action=`expected_title_restore_contract_case` title=`판초우의의 마법사`
- `11706871` action=`expected_title_restore_contract_case` title=`파우스트`
- `11710049` action=`expected_title_restore_contract_case` title=`[림월드]변방계에서 회귀자로 살아남기`
- `11714887` action=`expected_title_restore_contract_case` title=`도굴왕 1 |`
- `11666741` action=`expected_title_restore_contract_case` title=`별을 품은 소드마스터`
- `11679537` action=`expected_title_restore_contract_case` title=`죽었다 깨어도 수선`
- `11665121` action=`expected_title_restore_contract_case` title=`후회 안 하는 프로듀서`
- `11673077` action=`expected_title_restore_contract_case` title=`판초우의의 마법사`

## Gate 해석

현재 projection 기준 pending contract는 `0`건이며 release candidate는 `13`건이다. no-release 유지 행은 `0`건이며, runtime replay allowed는 `0`건이다. full375 collateral은 `NO-GO`, goal은 `ACTIVE / NOT_COMPLETE`다.
