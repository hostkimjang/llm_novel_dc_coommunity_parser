# loop538_shared_gate_seeded_runtime_failure_action_queue

## 요약

- gate: `REVIEW-LOCKED`
- expected_rows: `35`
- passed_rows_excluded: `21`
- failed_rows: `14`
- projection_still_blocked_rows: `0`
- action_queue_rows: `14`
- source_audit_status_counts: `{'FAIL_RUNTIME_PROMOTION_BLOCKED': 11, 'FAIL_SAFE_RESOLVED_TITLE_MISMATCH': 3, 'PASS_EXACT_SAFE_RESOLVED': 21}`
- label_counts: `{'HOLD': 3, 'REPROCESS': 11}`
- priority_counts: `{'P0': 3, 'P1': 11}`
- owner_mode_counts: `{'CODE_OR_RUNTIME_PROMOTION_GATE_REPAIR': 11, 'SOURCE_NATIVE_OR_BLIND_CANONICAL_REVIEW': 3}`
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

- row_count: `3`
- priority_counts: `{'P0': 3}`
- label_counts: `{'HOLD': 3}`
- audit_status_counts: `{'FAIL_SAFE_RESOLVED_TITLE_MISMATCH': 3}`
- owner_modes: `{'SOURCE_NATIVE_OR_BLIND_CANONICAL_REVIEW': 3}`
- sample_post_ids: `11660277, 11694063, 11718098`

### search_degraded_or_timeout_replay_required

- row_count: `7`
- priority_counts: `{'P0': 3, 'P1': 4}`
- label_counts: `{'HOLD': 3, 'REPROCESS': 4}`
- audit_status_counts: `{'FAIL_RUNTIME_PROMOTION_BLOCKED': 4, 'FAIL_SAFE_RESOLVED_TITLE_MISMATCH': 3}`
- owner_modes: `{'CODE_OR_RUNTIME_PROMOTION_GATE_REPAIR': 4, 'SOURCE_NATIVE_OR_BLIND_CANONICAL_REVIEW': 3}`
- sample_post_ids: `11697256, 11694068, 11660277, 11663511, 11694063, 11706831, 11718098`

### search_evidence_missing_review_required

- row_count: `1`
- priority_counts: `{'P1': 1}`
- label_counts: `{'REPROCESS': 1}`
- audit_status_counts: `{'FAIL_RUNTIME_PROMOTION_BLOCKED': 1}`
- owner_modes: `{'CODE_OR_RUNTIME_PROMOTION_GATE_REPAIR': 1}`
- sample_post_ids: `11666741`

### shared_gate_runtime_block_repair_required

- row_count: `11`
- priority_counts: `{'P1': 11}`
- label_counts: `{'REPROCESS': 11}`
- audit_status_counts: `{'FAIL_RUNTIME_PROMOTION_BLOCKED': 11}`
- owner_modes: `{'CODE_OR_RUNTIME_PROMOTION_GATE_REPAIR': 11}`
- sample_post_ids: `11669913, 11697242, 11697256, 11718114, 11666741, 11694068, 11663511, 11669926, 11669933, 11677924, 11706831`
