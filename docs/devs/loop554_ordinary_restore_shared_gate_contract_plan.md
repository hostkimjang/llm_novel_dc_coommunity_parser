# loop554_ordinary_restore_shared_gate_contract_plan

Loop554는 Loop553 shared-gate restore lane을 shared `can_publish_title` gate로 통과시킨 계약 계획이다. 이 산출물은 runtime replay 허가나 full_scan approval이 아니다.

## 요약

- source_dispatch: `loop553_ordinary_residual64_dispatch`
- gate: `REVIEW-LOCKED`
- restore_contract_plan_rows: `17`
- validation_issue_count: `0`
- contract_action_counts: `{'expected_title_restore_contract_case': 17}`
- promotion_decision_status_counts: `{'publish': 17}`
- evidence_grade_counts: `{'Medium': 3, 'Strong': 14}`
- search_condition_counts: `{'runtime_expected_audit_missing': 1, 'search_degraded_condition': 10, 'search_recovered_condition': 5, 'search_status_missing': 1}`
- official_support_ref_missing_rows: `1`
- search_review_required_before_approval_rows: `12`
- release_candidate_not_approval_rows: `17`
- publish_allowed_rows: `0`
- runtime_replay_allowed_rows: `0`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`

## 승인 경계

- `promotion_decision=publish`는 contract case일 뿐 approval이 아니다.
- Projection 적용, lane별 검증, full375 collateral 재확인 전 runtime replay를 열지 않는다.
- Search degraded/status missing 조건은 full_scan approval 전에 별도 확인해야 한다.
- 완료 기준은 계속 `full375 collateral GO + full_scan 경로 정의`다.

## Rows

- `11660273` action=`expected_title_restore_contract_case` decision=`publish` target=`마도서를 줍다 마법사가 되다` runtime_audit=`FAIL_SAFE_RESOLVED_TITLE_MISMATCH` search=`search_degraded_condition` official_refs=`1`
- `11663511` action=`expected_title_restore_contract_case` decision=`publish` target=`부캐 키우는 황태자님` runtime_audit=`FAIL_RUNTIME_PROMOTION_BLOCKED` search=`search_degraded_condition` official_refs=`1`
- `11663535` action=`expected_title_restore_contract_case` decision=`publish` target=`퇴마록` runtime_audit=`FAIL_RUNTIME_PROMOTION_BLOCKED` search=`search_degraded_condition` official_refs=`1`
- `11668300` action=`expected_title_restore_contract_case` decision=`publish` target=`즉사기 들고 게임 속 으로` runtime_audit=`FAIL_SAFE_RESOLVED_TITLE_MISMATCH` search=`search_recovered_condition` official_refs=`1`
- `11673077` action=`expected_title_restore_contract_case` decision=`publish` target=`판초우의의 마법사` runtime_audit=`FAIL_RUNTIME_PROMOTION_BLOCKED` search=`search_degraded_condition` official_refs=`1`
- `11673102` action=`expected_title_restore_contract_case` decision=`publish` target=`갤질하는 천재 의사` runtime_audit=`FAIL_SAFE_RESOLVED_TITLE_MISMATCH` search=`search_recovered_condition` official_refs=`1`
- `11677915` action=`expected_title_restore_contract_case` decision=`publish` target=`전지적 독자 시점` runtime_audit=`FAIL_RUNTIME_PROMOTION_BLOCKED` search=`search_degraded_condition` official_refs=`1`
- `11681172` action=`expected_title_restore_contract_case` decision=`publish` target=`헌터갤러리의 국가권력급 기계공주` runtime_audit=`FAIL_RUNTIME_PROMOTION_BLOCKED` search=`search_status_missing` official_refs=`0`
- `11689292` action=`expected_title_restore_contract_case` decision=`publish` target=`최악의 파트너` runtime_audit=`FAIL_SAFE_RESOLVED_TITLE_MISMATCH` search=`search_recovered_condition` official_refs=`1`
- `11694019` action=`expected_title_restore_contract_case` decision=`publish` target=`혼후 순결` runtime_audit=`FAIL_SAFE_RESOLVED_TITLE_MISMATCH` search=`search_degraded_condition` official_refs=`1`
- `11694063` action=`expected_title_restore_contract_case` decision=`publish` target=`빙의한 신의 아이, 엘리시아` runtime_audit=`None` search=`runtime_expected_audit_missing` official_refs=`1`
- `11694068` action=`expected_title_restore_contract_case` decision=`publish` target=`트와일라잇` runtime_audit=`FAIL_RUNTIME_PROMOTION_BLOCKED` search=`search_degraded_condition` official_refs=`1`
- `11702094` action=`expected_title_restore_contract_case` decision=`publish` target=`#더블오` runtime_audit=`FAIL_SAFE_RESOLVED_TITLE_MISMATCH` search=`search_recovered_condition` official_refs=`1`
- `11705230` action=`expected_title_restore_contract_case` decision=`publish` target=`월야환담` runtime_audit=`FAIL_RUNTIME_PROMOTION_BLOCKED` search=`search_recovered_condition` official_refs=`1`
- `11705251` action=`expected_title_restore_contract_case` decision=`publish` target=`월야환담 창월야` runtime_audit=`FAIL_RUNTIME_PROMOTION_BLOCKED` search=`search_degraded_condition` official_refs=`1`
- `11706842` action=`expected_title_restore_contract_case` decision=`publish` target=`삼국지 마대 가 되었다` runtime_audit=`FAIL_SAFE_RESOLVED_TITLE_MISMATCH` search=`search_degraded_condition` official_refs=`1`
- `11718110` action=`expected_title_restore_contract_case` decision=`publish` target=`지구온라인에서 쌀먹합니다` runtime_audit=`FAIL_RUNTIME_PROMOTION_BLOCKED` search=`search_degraded_condition` official_refs=`1`
