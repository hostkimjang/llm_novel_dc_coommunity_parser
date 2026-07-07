# loop586_canonical_title_rewrite_restore_contract_plan

`loop586_canonical_title_rewrite_review_enriched_restore_dispatch` shared-gate restore lane을 shared `can_publish_title` gate로 통과시킨 계약 계획이다. 이 산출물은 runtime replay 허가나 full_scan approval이 아니다.

## 요약

- source_dispatch: `loop586_canonical_title_rewrite_review_enriched_restore_dispatch`
- gate: `REVIEW-LOCKED`
- restore_contract_plan_rows: `1`
- validation_issue_count: `0`
- contract_action_counts: `{'expected_title_restore_contract_case': 1}`
- promotion_decision_status_counts: `{'publish': 1}`
- evidence_grade_counts: `{'Strong': 1}`
- search_condition_counts: `{'runtime_expected_audit_missing': 1}`
- official_support_ref_missing_rows: `0`
- official_support_missing_hold_rows: `0`
- search_review_required_before_approval_rows: `1`
- release_candidate_not_approval_rows: `1`
- publish_allowed_rows: `0`
- runtime_replay_allowed_rows: `0`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`

## 테스트런 실행 계약

- policy: `TEST_RUNS_USE_PARALLEL_16_AND_WEB_DASHBOARD`
- requested_parallel: `16`
- expected_effective_parallel: `1`
- forbidden_flags: `['--no-dashboard']`
- dashboard_policy: `WEB_DASHBOARD_REQUIRED_FOR_TEST_RUNS`
- dashboard_url: `http://127.0.0.1:8080`
- dashboard_gate: `GO_PROGRESS_VIEW_NOT_APPROVAL`
- Dashboard는 진행 확인 도구이며 semantic/full_scan approval 근거가 아니다.

## 승인 경계

- `promotion_decision=publish`는 contract case일 뿐 approval이 아니다.
- 공식 detail URL이 없는 restore 후보는 `official_support_missing_restore_hold_contract_case`로 보존하고 publish하지 않는다.
- Projection 적용, lane별 검증, full375 collateral 재확인 전 runtime replay를 열지 않는다.
- Search degraded/status missing 조건은 full_scan approval 전에 별도 확인해야 한다.
- 완료 기준은 계속 `full375 collateral GO + full_scan 경로 정의`다.

## Rows

- `11665124` action=`expected_title_restore_contract_case` decision=`publish` target=`화산귀환` runtime_audit=`None` search=`runtime_expected_audit_missing` official_refs=`1`
