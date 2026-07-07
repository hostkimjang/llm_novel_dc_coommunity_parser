# loop565_title_mismatch_hold2_source_native_batch

## 요약

- source_queue_id: `loop564_conflict_safe_p0_shared_gate_runtime_expected_failures`
- gate: `REVIEW-LOCKED`
- selected_rows: `2`
- runtime_input_candidate_rows: `0`
- source_native_review_rows: `2`
- search_replay_required_rows: `1`
- label_counts: `{'HOLD': 2}`
- priority_counts: `{'P0': 2}`
- dispatch_lane_counts: `{'source_native_or_blind_review': 2}`
- audit_status_counts: `{'FAIL_SAFE_RESOLVED_TITLE_MISMATCH': 2}`
- validation_issue_count: `0`
- approval: `false`
- semantic_quality: `REVIEW-LOCKED`

## 테스트런 실행 계약

- policy: `TEST_RUNS_USE_PARALLEL_16_AND_WEB_DASHBOARD`
- row_count: `2`
- requested_parallel: `16`
- expected_effective_parallel: `2`
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

### search_replay_required

- row_count: `1`
- label_counts: `{'HOLD': 1}`
- priority_counts: `{'P0': 1}`
- dispatch_lane_counts: `{'source_native_or_blind_review': 1}`
- sample_post_ids: `11673080`

### source_native_or_blind_canonical_review

- row_count: `2`
- label_counts: `{'HOLD': 2}`
- priority_counts: `{'P0': 2}`
- dispatch_lane_counts: `{'source_native_or_blind_review': 2}`
- sample_post_ids: `11665121, 11673080`
