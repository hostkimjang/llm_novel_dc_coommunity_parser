# loop522_context_preserving_safe57_expected_failure_queue

## 요약

- gate: `REVIEW-LOCKED`
- expected_rows: `57`
- passed_rows_excluded: `15`
- failed_rows: `42`
- projection_still_blocked_rows: `0`
- action_queue_rows: `42`
- source_audit_status_counts: `{'FAIL_RUNTIME_PROMOTION_BLOCKED': 32, 'FAIL_SAFE_RESOLVED_TITLE_MISMATCH': 10, 'PASS_EXACT_SAFE_RESOLVED': 15}`
- label_counts: `{'HOLD': 10, 'REPROCESS': 32}`
- priority_counts: `{'P0': 10, 'P1': 32}`
- owner_mode_counts: `{'CODE_OR_RUNTIME_PROMOTION_GATE_REPAIR': 32, 'SOURCE_NATIVE_OR_BLIND_CANONICAL_REVIEW': 10}`
- search_unrecovered_degraded_rows/total: `0/0`
- validation_issue_count: `0`
- approval: `false`
- semantic_quality: `REVIEW-LOCKED`

## 승인 경계

- 이 큐는 Loop489 runtime expected-audit 실패를 다음 작업 단위로 나눈 산출물이며 approval이 아니다.
- Runtime completion, publication contract `GO`, expected-audit queue 정리는 full375 collateral 승인이 아니다.
- 완료 기준은 계속 `full375 collateral GO + full_scan 경로 정의`다.

## Action groups

### canonical_variant_or_wrong_work_review_required

- row_count: `10`
- priority_counts: `{'P0': 10}`
- label_counts: `{'HOLD': 10}`
- audit_status_counts: `{'FAIL_SAFE_RESOLVED_TITLE_MISMATCH': 10}`
- owner_modes: `{'SOURCE_NATIVE_OR_BLIND_CANONICAL_REVIEW': 10}`
- sample_post_ids: `11668325, 11673102, 11694019, 11673077, 11666713, 11669921, 11689292, 11692436, 11694065, 11706842`

### search_degraded_or_timeout_replay_required

- row_count: `20`
- priority_counts: `{'P0': 6, 'P1': 14}`
- label_counts: `{'HOLD': 6, 'REPROCESS': 14}`
- audit_status_counts: `{'FAIL_RUNTIME_PROMOTION_BLOCKED': 14, 'FAIL_SAFE_RESOLVED_TITLE_MISMATCH': 6}`
- owner_modes: `{'CODE_OR_RUNTIME_PROMOTION_GATE_REPAIR': 14, 'SOURCE_NATIVE_OR_BLIND_CANONICAL_REVIEW': 6}`
- sample_post_ids: `11660273, 11663535, 11665124, 11669913, 11677926, 11694019, 11708447, 11710049, 11718099, 11718110, 11673077, 11666713`

### search_evidence_missing_review_required

- row_count: `8`
- priority_counts: `{'P1': 8}`
- label_counts: `{'REPROCESS': 8}`
- audit_status_counts: `{'FAIL_RUNTIME_PROMOTION_BLOCKED': 8}`
- owner_modes: `{'CODE_OR_RUNTIME_PROMOTION_GATE_REPAIR': 8}`
- sample_post_ids: `11681172, 11690841, 11697242, 11697256, 11710021, 11666741, 11700483, 11708470`

### shared_gate_runtime_block_repair_required

- row_count: `32`
- priority_counts: `{'P1': 32}`
- label_counts: `{'REPROCESS': 32}`
- audit_status_counts: `{'FAIL_RUNTIME_PROMOTION_BLOCKED': 32}`
- owner_modes: `{'CODE_OR_RUNTIME_PROMOTION_GATE_REPAIR': 32}`
- sample_post_ids: `11660271, 11660273, 11663535, 11663557, 11665124, 11669913, 11677926, 11681172, 11690841, 11697242, 11697256, 11702094`
