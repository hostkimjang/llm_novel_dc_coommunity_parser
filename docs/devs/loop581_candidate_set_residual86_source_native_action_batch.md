# loop581_candidate_set_residual86_source_native_action_batch

## 요약

- source_queue_id: `loop580_candidate_set_full375_residual86_batch_action_queue`
- gate: `REVIEW-LOCKED`
- selected_rows: `86`
- runtime_input_candidate_rows: `0`
- source_native_review_rows: `86`
- search_replay_required_rows: `0`
- label_counts: `{'INFO_MISSING': 86}`
- priority_counts: `{'P0': 86}`
- dispatch_lane_counts: `{'source_native_or_blind_review': 86}`
- audit_status_counts: `{'None': 86}`
- validation_issue_count: `0`
- approval: `false`
- semantic_quality: `REVIEW-LOCKED`

## 테스트런 실행 계약

- policy: `TEST_RUNS_USE_PARALLEL_16_AND_WEB_DASHBOARD`
- row_count: `86`
- requested_parallel: `16`
- expected_effective_parallel: `16`
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

## 처리 lane

### source_native_or_blind_review

- row_count: `86`
- label_counts: `{'INFO_MISSING': 86}`
- priority_counts: `{'P0': 86}`
- dispatch_lane_counts: `{'source_native_or_blind_review': 86}`
- sample_post_ids: `11658637, 11660232, 11660238, 11660254, 11660262, 11660273, 11661856, 11661863, 11663554, 11665099, 11665110, 11665124`
