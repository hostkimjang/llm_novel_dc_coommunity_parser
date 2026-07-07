# loop581_candidate_set_full375_prior_compatible_residual_p0_action_batch

## 요약

- source_queue_id: `loop581_candidate_set_full375_prior_compatible_residual_action_queue`
- gate: `REVIEW-LOCKED`
- selected_rows: `19`
- runtime_input_candidate_rows: `0`
- source_native_review_rows: `9`
- search_replay_required_rows: `0`
- label_counts: `{'INFO_MISSING': 7, 'REPROCESS': 12}`
- priority_counts: `{'P0': 19}`
- dispatch_lane_counts: `{'candidate_set_rebuild_review': 4, 'native_web_image_evidence_review': 1, 'no_publish_guard_review': 1, 'shared_gate_restore_contract_review': 6, 'source_native_or_blind_review': 7}`
- audit_status_counts: `{'None': 19}`
- validation_issue_count: `0`
- approval: `false`
- semantic_quality: `REVIEW-LOCKED`

## 테스트런 실행 계약

- policy: `TEST_RUNS_USE_PARALLEL_16_AND_WEB_DASHBOARD`
- row_count: `19`
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

### candidate_set_rebuild_review

- row_count: `4`
- label_counts: `{'REPROCESS': 4}`
- priority_counts: `{'P0': 4}`
- dispatch_lane_counts: `{'candidate_set_rebuild_review': 4}`
- sample_post_ids: `11682749, 11703658, 11705231, 11710036`

### native_web_image_evidence_review

- row_count: `2`
- label_counts: `{'REPROCESS': 2}`
- priority_counts: `{'P0': 2}`
- dispatch_lane_counts: `{'candidate_set_rebuild_review': 1, 'native_web_image_evidence_review': 1}`
- sample_post_ids: `11698859, 11703658`

### no_publish_guard_review

- row_count: `1`
- label_counts: `{'REPROCESS': 1}`
- priority_counts: `{'P0': 1}`
- dispatch_lane_counts: `{'no_publish_guard_review': 1}`
- sample_post_ids: `11700483`

### shared_gate_restore_contract_review

- row_count: `8`
- label_counts: `{'REPROCESS': 8}`
- priority_counts: `{'P0': 8}`
- dispatch_lane_counts: `{'native_web_image_evidence_review': 1, 'no_publish_guard_review': 1, 'shared_gate_restore_contract_review': 6}`
- sample_post_ids: `11665124, 11710049, 11718114, 11682775, 11698859, 11700483, 11700500, 11698870`

### source_native_or_blind_review

- row_count: `7`
- label_counts: `{'INFO_MISSING': 7}`
- priority_counts: `{'P0': 7}`
- dispatch_lane_counts: `{'source_native_or_blind_review': 7}`
- sample_post_ids: `11660232, 11663554, 11682792, 11703674, 11714903, 11660273, 11671514`
