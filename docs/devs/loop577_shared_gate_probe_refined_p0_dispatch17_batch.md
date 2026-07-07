# loop577_shared_gate_probe_refined_p0_dispatch17_batch

## 요약

- source_queue_id: `loop576_source_native_hold_residual64_action_queue`
- gate: `REVIEW-LOCKED`
- selected_rows: `17`
- runtime_input_candidate_rows: `0`
- source_native_review_rows: `3`
- search_replay_required_rows: `0`
- label_counts: `{'REPROCESS': 17}`
- priority_counts: `{'P0': 17}`
- dispatch_lane_counts: `{'candidate_set_rebuild_review': 10, 'native_web_image_evidence_review': 1, 'no_publish_guard_review': 1, 'shared_gate_restore_contract_review': 5}`
- audit_status_counts: `{'None': 17}`
- validation_issue_count: `0`
- approval: `false`
- semantic_quality: `REVIEW-LOCKED`

## 테스트런 실행 계약

- policy: `TEST_RUNS_USE_PARALLEL_16_AND_WEB_DASHBOARD`
- row_count: `17`
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

- row_count: `10`
- label_counts: `{'REPROCESS': 10}`
- priority_counts: `{'P0': 10}`
- dispatch_lane_counts: `{'candidate_set_rebuild_review': 10}`
- sample_post_ids: `11660241, 11663514, 11671514, 11674694, 11682749, 11698870, 11703658, 11705231, 11710036, 11716464`

### canonical_variant_policy_review

- row_count: `3`
- label_counts: `{'REPROCESS': 3}`
- priority_counts: `{'P0': 3}`
- dispatch_lane_counts: `{'candidate_set_rebuild_review': 3}`
- sample_post_ids: `11660241, 11674694, 11716464`

### native_web_image_evidence_review

- row_count: `3`
- label_counts: `{'REPROCESS': 3}`
- priority_counts: `{'P0': 3}`
- dispatch_lane_counts: `{'candidate_set_rebuild_review': 2, 'native_web_image_evidence_review': 1}`
- sample_post_ids: `11663514, 11698859, 11703658`

### no_publish_guard_review

- row_count: `2`
- label_counts: `{'REPROCESS': 2}`
- priority_counts: `{'P0': 2}`
- dispatch_lane_counts: `{'candidate_set_rebuild_review': 1, 'no_publish_guard_review': 1}`
- sample_post_ids: `11698870, 11700483`

### shared_gate_restore_contract_review

- row_count: `7`
- label_counts: `{'REPROCESS': 7}`
- priority_counts: `{'P0': 7}`
- dispatch_lane_counts: `{'native_web_image_evidence_review': 1, 'no_publish_guard_review': 1, 'shared_gate_restore_contract_review': 5}`
- sample_post_ids: `11665124, 11682775, 11698859, 11700483, 11700500, 11710049, 11718114`

### source_native_or_blind_canonical_review

- row_count: `3`
- label_counts: `{'REPROCESS': 3}`
- priority_counts: `{'P0': 3}`
- dispatch_lane_counts: `{'candidate_set_rebuild_review': 3}`
- sample_post_ids: `11660241, 11674694, 11716464`
