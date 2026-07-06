# loop490_projected_safe46_runtime_failure_action_queue

## 요약

- gate: `REVIEW-LOCKED`
- expected_rows: `46`
- passed_rows_excluded: `10`
- failed_rows: `36`
- projection_still_blocked_rows: `1`
- action_queue_rows: `37`
- source_audit_status_counts: `{'FAIL_RUNTIME_PROMOTION_BLOCKED': 30, 'FAIL_SAFE_RESOLVED_TITLE_MISMATCH': 5, 'FAIL_VARIANT_COMPACT_MATCH_ONLY': 1, 'PASS_EXACT_SAFE_RESOLVED': 10}`
- label_counts: `{'HOLD': 10, 'REPROCESS': 27}`
- priority_counts: `{'P0': 23, 'P1': 13, 'P2': 1}`
- owner_mode_counts: `{'CANDIDATE_SET_REBUILD_OR_SOURCE_NATIVE_REVIEW': 1, 'CANONICAL_VARIANT_POLICY_REVIEW': 1, 'CODE_OR_RUNTIME_PROMOTION_GATE_REPAIR': 27, 'SOURCE_NATIVE_OR_BLIND_CANONICAL_REVIEW': 8}`
- search_unrecovered_degraded_rows/total: `13/25`
- validation_issue_count: `0`
- approval: `false`
- semantic_quality: `REVIEW-LOCKED`

## 승인 경계

- 이 큐는 Loop489 runtime expected-audit 실패를 다음 작업 단위로 나눈 산출물이며 approval이 아니다.
- Runtime completion, publication contract `GO`, expected-audit queue 정리는 full375 collateral 승인이 아니다.
- 완료 기준은 계속 `full375 collateral GO + full_scan 경로 정의`다.

## Action groups

### blocked_expected_title_trace_review_required

- row_count: `6`
- priority_counts: `{'P0': 6}`
- label_counts: `{'REPROCESS': 6}`
- audit_status_counts: `{'FAIL_RUNTIME_PROMOTION_BLOCKED': 6}`
- owner_modes: `{'CODE_OR_RUNTIME_PROMOTION_GATE_REPAIR': 6}`
- sample_post_ids: `11677915, 11684372, 11694019, 11698910, 11718099, 11682780`

### blocked_title_mismatch_source_native_review_required

- row_count: `3`
- priority_counts: `{'P0': 3}`
- label_counts: `{'HOLD': 3}`
- audit_status_counts: `{'FAIL_RUNTIME_PROMOTION_BLOCKED': 3}`
- owner_modes: `{'SOURCE_NATIVE_OR_BLIND_CANONICAL_REVIEW': 3}`
- sample_post_ids: `11663535, 11714887, 11673077`

### candidate_set_rebuild_required

- row_count: `1`
- priority_counts: `{'P2': 1}`
- label_counts: `{'HOLD': 1}`
- audit_status_counts: `{'PROJECTION_STILL_BLOCKED': 1}`
- owner_modes: `{'CANDIDATE_SET_REBUILD_OR_SOURCE_NATIVE_REVIEW': 1}`
- sample_post_ids: `11710036`

### canonical_variant_or_wrong_work_review_required

- row_count: `8`
- priority_counts: `{'P0': 8}`
- label_counts: `{'HOLD': 8}`
- audit_status_counts: `{'FAIL_RUNTIME_PROMOTION_BLOCKED': 3, 'FAIL_SAFE_RESOLVED_TITLE_MISMATCH': 5}`
- owner_modes: `{'SOURCE_NATIVE_OR_BLIND_CANONICAL_REVIEW': 8}`
- sample_post_ids: `11663535, 11673102, 11692436, 11705230, 11714887, 11718098, 11673077, 11694068`

### search_degraded_or_timeout_replay_required

- row_count: `13`
- priority_counts: `{'P0': 13}`
- label_counts: `{'HOLD': 4, 'REPROCESS': 9}`
- audit_status_counts: `{'FAIL_RUNTIME_PROMOTION_BLOCKED': 10, 'FAIL_SAFE_RESOLVED_TITLE_MISMATCH': 2, 'FAIL_VARIANT_COMPACT_MATCH_ONLY': 1}`
- owner_modes: `{'CANONICAL_VARIANT_POLICY_REVIEW': 1, 'CODE_OR_RUNTIME_PROMOTION_GATE_REPAIR': 9, 'SOURCE_NATIVE_OR_BLIND_CANONICAL_REVIEW': 3}`
- sample_post_ids: `11663521, 11663535, 11665124, 11673102, 11677926, 11698870, 11698910, 11705230, 11708447, 11710049, 11716475, 11718110`

### search_evidence_missing_review_required

- row_count: `3`
- priority_counts: `{'P1': 3}`
- label_counts: `{'REPROCESS': 3}`
- audit_status_counts: `{'FAIL_RUNTIME_PROMOTION_BLOCKED': 3}`
- owner_modes: `{'CODE_OR_RUNTIME_PROMOTION_GATE_REPAIR': 3}`
- sample_post_ids: `11690841, 11710021, 11666741`

### shared_gate_runtime_block_repair_required

- row_count: `27`
- priority_counts: `{'P0': 14, 'P1': 13}`
- label_counts: `{'REPROCESS': 27}`
- audit_status_counts: `{'FAIL_RUNTIME_PROMOTION_BLOCKED': 27}`
- owner_modes: `{'CODE_OR_RUNTIME_PROMOTION_GATE_REPAIR': 27}`
- sample_post_ids: `11660271, 11663521, 11663557, 11665124, 11668325, 11669913, 11677915, 11677926, 11681172, 11684372, 11690841, 11694019`

### shared_promotion_gate_wiring_required

- row_count: `1`
- priority_counts: `{'P2': 1}`
- label_counts: `{'HOLD': 1}`
- audit_status_counts: `{'PROJECTION_STILL_BLOCKED': 1}`
- owner_modes: `{'CANDIDATE_SET_REBUILD_OR_SOURCE_NATIVE_REVIEW': 1}`
- sample_post_ids: `11710036`

### source_native_scope_or_nonwork_hold_review_required

- row_count: `1`
- priority_counts: `{'P2': 1}`
- label_counts: `{'HOLD': 1}`
- audit_status_counts: `{'PROJECTION_STILL_BLOCKED': 1}`
- owner_modes: `{'CANDIDATE_SET_REBUILD_OR_SOURCE_NATIVE_REVIEW': 1}`
- sample_post_ids: `11710036`

### spacing_or_canonical_variant_policy_review_required

- row_count: `1`
- priority_counts: `{'P0': 1}`
- label_counts: `{'HOLD': 1}`
- audit_status_counts: `{'FAIL_VARIANT_COMPACT_MATCH_ONLY': 1}`
- owner_modes: `{'CANONICAL_VARIANT_POLICY_REVIEW': 1}`
- sample_post_ids: `11698870`
