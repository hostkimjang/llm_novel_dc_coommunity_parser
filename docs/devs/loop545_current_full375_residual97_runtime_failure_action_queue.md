# loop545_current_full375_residual97_runtime_failure_action_queue

## 요약

- gate: `REVIEW-LOCKED`
- expected_rows: `49`
- passed_rows_excluded: `19`
- failed_rows: `30`
- projection_still_blocked_rows: `0`
- action_queue_rows: `30`
- source_audit_status_counts: `{'FAIL_RUNTIME_PROMOTION_BLOCKED': 23, 'FAIL_SAFE_RESOLVED_TITLE_MISMATCH': 7, 'PASS_EXACT_SAFE_RESOLVED': 19}`
- label_counts: `{'HOLD': 8, 'REPROCESS': 22}`
- priority_counts: `{'P0': 9, 'P1': 21}`
- owner_mode_counts: `{'CODE_OR_RUNTIME_PROMOTION_GATE_REPAIR': 22, 'SOURCE_NATIVE_OR_BLIND_CANONICAL_REVIEW': 8}`
- search_unrecovered_degraded_rows/total: `0/0`
- validation_issue_count: `0`
- approval: `false`
- semantic_quality: `REVIEW-LOCKED`

## 승인 경계

- 이 큐는 Loop489 runtime expected-audit 실패를 다음 작업 단위로 나눈 산출물이며 approval이 아니다.
- Runtime completion, publication contract `GO`, expected-audit queue 정리는 full375 collateral 승인이 아니다.
- 완료 기준은 계속 `full375 collateral GO + full_scan 경로 정의`다.

## Action groups

### blocked_expected_title_trace_review_required

- row_count: `1`
- priority_counts: `{'P0': 1}`
- label_counts: `{'REPROCESS': 1}`
- audit_status_counts: `{'FAIL_RUNTIME_PROMOTION_BLOCKED': 1}`
- owner_modes: `{'CODE_OR_RUNTIME_PROMOTION_GATE_REPAIR': 1}`
- sample_post_ids: `11663535`

### blocked_title_mismatch_source_native_review_required

- row_count: `1`
- priority_counts: `{'P0': 1}`
- label_counts: `{'HOLD': 1}`
- audit_status_counts: `{'FAIL_RUNTIME_PROMOTION_BLOCKED': 1}`
- owner_modes: `{'SOURCE_NATIVE_OR_BLIND_CANONICAL_REVIEW': 1}`
- sample_post_ids: `11694068`

### canonical_variant_or_wrong_work_review_required

- row_count: `8`
- priority_counts: `{'P0': 8}`
- label_counts: `{'HOLD': 8}`
- audit_status_counts: `{'FAIL_RUNTIME_PROMOTION_BLOCKED': 1, 'FAIL_SAFE_RESOLVED_TITLE_MISMATCH': 7}`
- owner_modes: `{'SOURCE_NATIVE_OR_BLIND_CANONICAL_REVIEW': 8}`
- sample_post_ids: `11660273, 11673102, 11694019, 11702094, 11694068, 11668300, 11689292, 11706842`

### search_degraded_or_timeout_replay_required

- row_count: `16`
- priority_counts: `{'P0': 5, 'P1': 11}`
- label_counts: `{'HOLD': 4, 'REPROCESS': 12}`
- audit_status_counts: `{'FAIL_RUNTIME_PROMOTION_BLOCKED': 13, 'FAIL_SAFE_RESOLVED_TITLE_MISMATCH': 3}`
- owner_modes: `{'CODE_OR_RUNTIME_PROMOTION_GATE_REPAIR': 12, 'SOURCE_NATIVE_OR_BLIND_CANONICAL_REVIEW': 4}`
- sample_post_ids: `11660273, 11663535, 11665124, 11677915, 11694019, 11697256, 11718110, 11673077, 11694068, 11663511, 11682767, 11692436`

### search_evidence_missing_review_required

- row_count: `4`
- priority_counts: `{'P1': 4}`
- label_counts: `{'REPROCESS': 4}`
- audit_status_counts: `{'FAIL_RUNTIME_PROMOTION_BLOCKED': 4}`
- owner_modes: `{'CODE_OR_RUNTIME_PROMOTION_GATE_REPAIR': 4}`
- sample_post_ids: `11681172, 11690841, 11710021, 11718114`

### shared_gate_runtime_block_repair_required

- row_count: `22`
- priority_counts: `{'P0': 1, 'P1': 21}`
- label_counts: `{'REPROCESS': 22}`
- audit_status_counts: `{'FAIL_RUNTIME_PROMOTION_BLOCKED': 22}`
- owner_modes: `{'CODE_OR_RUNTIME_PROMOTION_GATE_REPAIR': 22}`
- sample_post_ids: `11663535, 11665124, 11668325, 11677915, 11681172, 11690841, 11697242, 11697256, 11710021, 11710049, 11714887, 11718099`
