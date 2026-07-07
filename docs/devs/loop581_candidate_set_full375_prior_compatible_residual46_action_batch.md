# loop581_candidate_set_full375_prior_compatible_residual46_action_batch

## 요약

- source_queue_id: `loop581_candidate_set_full375_prior_compatible_residual_action_queue`
- gate: `REVIEW-LOCKED`
- selected_rows: `46`
- runtime_input_candidate_rows: `0`
- source_native_review_rows: `33`
- search_replay_required_rows: `0`
- label_counts: `{'HOLD': 21, 'INFO_MISSING': 7, 'REPROCESS': 18}`
- priority_counts: `{'P0': 19, 'P1': 6, 'P2': 21}`
- dispatch_lane_counts: `{'candidate_set_rebuild_review': 9, 'canonical_variant_policy_review': 7, 'native_web_image_evidence_review': 1, 'no_publish_guard_review': 1, 'shared_gate_restore_contract_review': 6, 'source_native_or_blind_canonical_review': 1, 'source_native_or_blind_review': 21}`
- audit_status_counts: `{'None': 46}`
- validation_issue_count: `0`
- approval: `false`
- semantic_quality: `REVIEW-LOCKED`

## 테스트런 실행 계약

- policy: `TEST_RUNS_USE_PARALLEL_16_AND_WEB_DASHBOARD`
- row_count: `46`
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

- row_count: `11`
- label_counts: `{'HOLD': 2, 'REPROCESS': 9}`
- priority_counts: `{'P0': 4, 'P1': 5, 'P2': 2}`
- dispatch_lane_counts: `{'candidate_set_rebuild_review': 9, 'canonical_variant_policy_review': 1, 'source_native_or_blind_review': 1}`
- sample_post_ids: `11671512, 11694041, 11668324, 11718105, 11661863, 11682749, 11694035, 11698865, 11703658, 11705231, 11710036`

### canonical_variant_policy_review

- row_count: `9`
- label_counts: `{'HOLD': 7, 'REPROCESS': 2}`
- priority_counts: `{'P1': 2, 'P2': 7}`
- dispatch_lane_counts: `{'candidate_set_rebuild_review': 1, 'canonical_variant_policy_review': 7, 'source_native_or_blind_canonical_review': 1}`
- sample_post_ids: `11671538, 11694067, 11665110, 11698871, 11718057, 11669907, 11694041, 11698865, 11708453`

### native_web_image_evidence_review

- row_count: `25`
- label_counts: `{'HOLD': 20, 'REPROCESS': 5}`
- priority_counts: `{'P0': 2, 'P1': 3, 'P2': 20}`
- dispatch_lane_counts: `{'candidate_set_rebuild_review': 4, 'canonical_variant_policy_review': 6, 'native_web_image_evidence_review': 1, 'source_native_or_blind_review': 14}`
- sample_post_ids: `11682791, 11671538, 11694067, 11661856, 11665110, 11666725, 11681178, 11685994, 11687661, 11698871, 11706844, 11710047`

### no_publish_guard_review

- row_count: `5`
- label_counts: `{'HOLD': 1, 'REPROCESS': 4}`
- priority_counts: `{'P0': 1, 'P1': 3, 'P2': 1}`
- dispatch_lane_counts: `{'candidate_set_rebuild_review': 3, 'canonical_variant_policy_review': 1, 'no_publish_guard_review': 1}`
- sample_post_ids: `11668324, 11718105, 11694035, 11700483, 11708453`

### shared_gate_restore_contract_review

- row_count: `8`
- label_counts: `{'REPROCESS': 8}`
- priority_counts: `{'P0': 8}`
- dispatch_lane_counts: `{'native_web_image_evidence_review': 1, 'no_publish_guard_review': 1, 'shared_gate_restore_contract_review': 6}`
- sample_post_ids: `11665124, 11710049, 11718114, 11682775, 11698859, 11700483, 11700500, 11698870`

### source_native_or_blind_canonical_review

- row_count: `9`
- label_counts: `{'HOLD': 7, 'REPROCESS': 2}`
- priority_counts: `{'P1': 2, 'P2': 7}`
- dispatch_lane_counts: `{'candidate_set_rebuild_review': 1, 'canonical_variant_policy_review': 7, 'source_native_or_blind_canonical_review': 1}`
- sample_post_ids: `11671538, 11694067, 11665110, 11698871, 11718057, 11669907, 11694041, 11698865, 11708453`

### source_native_or_blind_review

- row_count: `7`
- label_counts: `{'INFO_MISSING': 7}`
- priority_counts: `{'P0': 7}`
- dispatch_lane_counts: `{'source_native_or_blind_review': 7}`
- sample_post_ids: `11660232, 11663554, 11682792, 11703674, 11714903, 11660273, 11671514`
