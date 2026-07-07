# loop562_conflict_safe_full375_info_missing5_source_native_batch

## 요약

- source_queue_id: `loop561_conflict_safe_full375_residual87_action_queue`
- gate: `REVIEW-LOCKED`
- selected_rows: `5`
- runtime_input_candidate_rows: `0`
- source_native_review_rows: `5`
- search_replay_required_rows: `0`
- label_counts: `{'INFO_MISSING': 5}`
- priority_counts: `{'P1': 5}`
- dispatch_lane_counts: `{'source_native_or_blind_review': 5}`
- audit_status_counts: `{'None': 5}`
- validation_issue_count: `0`
- approval: `false`
- semantic_quality: `REVIEW-LOCKED`

## 테스트런 실행 계약

- policy: `TEST_RUNS_USE_PARALLEL_16_AND_WEB_DASHBOARD`
- row_count: `5`
- requested_parallel: `16`
- expected_effective_parallel: `5`
- required_flags: `['--parallel 16']`
- forbidden_flags: `['--no-dashboard']`
- dashboard_policy: `WEB_DASHBOARD_REQUIRED_FOR_TEST_RUNS`
- dashboard_url: `http://127.0.0.1:8080`
- dashboard_gate: `GO_PROGRESS_VIEW_NOT_APPROVAL`
- Dashboard는 진행 확인 도구이며 semantic/full_scan approval 근거가 아니다.

## 승인 경계

- 이 batch는 실행 순서를 정한 산출물이며 approval이 아니다.
- `runtime_input_candidate_rows`는 입력 생성 후보일 뿐 runtime replay 결과가 아니다.
- `HOLD`/`INFO_MISSING` 행은 source-native/blind review 전까지 hard-hold 완화 대상이 아니다.
- 완료 기준은 계속 `full375 collateral GO + full_scan 경로 정의`다.

## Lanes

### source_native_or_blind_review

- row_count: `5`
- label_counts: `{'INFO_MISSING': 5}`
- priority_counts: `{'P1': 5}`
- dispatch_lane_counts: `{'source_native_or_blind_review': 5}`
- sample_post_ids: `11660232, 11663554, 11682792, 11703674, 11714903`
