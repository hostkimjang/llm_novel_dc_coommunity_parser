# loop555_ordinary_restore_post_apply_release_gate_audit

Post-verdict promotion-gate contract plan을 current projection 결과에 대조한 release gate 감사다. 이 감사는 새 runtime replay가 아니며, release candidate가 있더라도 full375 collateral GO 전에는 approval이나 full_scan 경로로 보지 않는다.

## 요약

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- contract_plan_rows: `17`
- projection_rows: `375`
- validation_issue_count: `0`
- violation_row_count: `0`
- pending_contract_rows: `0`
- satisfied_no_release_rows: `0`
- release_candidate_after_contract_rows: `17`
- runtime_replay_allowed_rows: `0`
- full375 collateral: `NO-GO`

## Release gate states

- `expected_restore_contract_satisfied_release_candidate`: `17`

## Release candidates

- `11660273` action=`expected_title_restore_contract_case` title=`마도서를 줍다 마법사가 되다`
- `11663511` action=`expected_title_restore_contract_case` title=`부캐 키우는 황태자님`
- `11663535` action=`expected_title_restore_contract_case` title=`퇴마록`
- `11668300` action=`expected_title_restore_contract_case` title=`즉사기 들고 게임 속 으로`
- `11673077` action=`expected_title_restore_contract_case` title=`판초우의의 마법사`
- `11673102` action=`expected_title_restore_contract_case` title=`갤질하는 천재 의사`
- `11677915` action=`expected_title_restore_contract_case` title=`전지적 독자 시점`
- `11681172` action=`expected_title_restore_contract_case` title=`헌터갤러리의 국가권력급 기계공주`
- `11689292` action=`expected_title_restore_contract_case` title=`최악의 파트너`
- `11694019` action=`expected_title_restore_contract_case` title=`혼후 순결`
- `11694063` action=`expected_title_restore_contract_case` title=`빙의한 신의 아이, 엘리시아`
- `11694068` action=`expected_title_restore_contract_case` title=`트와일라잇`
- `11702094` action=`expected_title_restore_contract_case` title=`#더블오`
- `11705230` action=`expected_title_restore_contract_case` title=`월야환담`
- `11705251` action=`expected_title_restore_contract_case` title=`월야환담 창월야`
- `11706842` action=`expected_title_restore_contract_case` title=`삼국지 마대 가 되었다`
- `11718110` action=`expected_title_restore_contract_case` title=`지구온라인에서 쌀먹합니다`

## Gate 해석

현재 projection 기준 pending contract는 `0`건이며 release candidate는 `17`건이다. no-release 유지 행은 `0`건이며, runtime replay allowed는 `0`건이다. full375 collateral은 `NO-GO`, goal은 `ACTIVE / NOT_COMPLETE`다.
