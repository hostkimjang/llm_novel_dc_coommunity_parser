# loop544_current_full375_residual97_shared_gate_followup_queue

## 요약

- source_projection_id: `loop544_current_full375_residual97_shared_gate_projection`
- gate: `REVIEW-LOCKED`
- followup_action_queue_rows: `51`
- label_counts: `{'HOLD': 20, 'REPROCESS': 31}`
- priority_counts: `{'P0': 11, 'P1': 40}`
- projected_status_counts: `{'safe_resolved': 51}`
- exact_match_counts: `{'match': 51}`
- prior_runtime_audit_status_counts: `{'FAIL_RUNTIME_PROMOTION_BLOCKED': 10, 'FAIL_SAFE_RESOLVED_TITLE_MISMATCH': 1, 'NO_PRIOR_AUDIT': 19, 'PASS_EXACT_SAFE_RESOLVED': 21}`
- runtime_replay_candidate_rows: `40`
- runtime_seed_replay_candidate_rows: `9`
- variant_review_rows: `1`
- lint_followup_rows: `0`
- still_blocked_rows: `0`
- validation_issue_count: `0`
- approval: `false`
- semantic_quality: `REVIEW-LOCKED`

## 승인 경계

- 이 큐는 source projection의 후속 실행 단위이며 approval이 아니다.
- `safe_resolved` projection도 runtime replay와 publication contract audit 전에는 해소 처리하지 않는다.
- prior runtime expected-audit 실패 행은 같은 입력 반복 실행 전에 repair/source-native review lane으로 보낸다.
- source-native exact title mismatch는 canonical variant 또는 wrong-work review 전까지 publish 근거가 아니다.
- 완료 기준은 여전히 `full375 collateral GO + full_scan 경로 정의`다.

## Action groups

### full375_collateral_recheck_after_repair

- row_count: `1`
- priority_counts: `{'P0': 1}`
- label_counts: `{'REPROCESS': 1}`
- projected_status_counts: `{'safe_resolved': 1}`
- owner_modes: `{'CODE_OR_RUNTIME_CONTRACT_REPAIR': 1}`
- sample_post_ids: `11677924`

### full375_collateral_recheck_after_runtime

- row_count: `49`
- priority_counts: `{'P0': 9, 'P1': 40}`
- label_counts: `{'HOLD': 19, 'REPROCESS': 30}`
- projected_status_counts: `{'safe_resolved': 49}`
- owner_modes: `{'RUNTIME_AUDIT_GAP_REVIEW': 19, 'RUNTIME_REPLAY': 21, 'RUNTIME_REPLAY_WITH_SHARED_GATE_SEED': 9}`
- sample_post_ids: `11660273, 11663535, 11663557, 11665124, 11668325, 11669913, 11673102, 11677915, 11677926, 11681172, 11690841, 11694019`

### prior_runtime_expected_audit_missing_review_required

- row_count: `19`
- priority_counts: `{'P1': 19}`
- label_counts: `{'HOLD': 19}`
- projected_status_counts: `{'safe_resolved': 19}`
- owner_modes: `{'RUNTIME_AUDIT_GAP_REVIEW': 19}`
- sample_post_ids: `11663557, 11665124, 11668325, 11673102, 11677915, 11681172, 11694019, 11710021, 11710049, 11673077, 11666713, 11669921`

### prior_runtime_promotion_block_repair_required

- row_count: `1`
- priority_counts: `{'P0': 1}`
- label_counts: `{'REPROCESS': 1}`
- projected_status_counts: `{'safe_resolved': 1}`
- owner_modes: `{'CODE_OR_RUNTIME_CONTRACT_REPAIR': 1}`
- sample_post_ids: `11677924`

### prior_runtime_title_mismatch_review_required

- row_count: `1`
- priority_counts: `{'P0': 1}`
- label_counts: `{'HOLD': 1}`
- projected_status_counts: `{'safe_resolved': 1}`
- owner_modes: `{'SOURCE_NATIVE_OR_CANONICAL_REVIEW': 1}`
- sample_post_ids: `11694063`

### projection_followup_official_url_repair_required

- row_count: `1`
- priority_counts: `{'P0': 1}`
- label_counts: `{'REPROCESS': 1}`
- projected_status_counts: `{'safe_resolved': 1}`
- owner_modes: `{'CODE_OR_RUNTIME_CONTRACT_REPAIR': 1}`
- sample_post_ids: `11677924`

### runtime_replay_after_variant_review

- row_count: `1`
- priority_counts: `{'P0': 1}`
- label_counts: `{'HOLD': 1}`
- projected_status_counts: `{'safe_resolved': 1}`
- owner_modes: `{'SOURCE_NATIVE_OR_CANONICAL_REVIEW': 1}`
- sample_post_ids: `11694063`

### runtime_replay_projected_safe_resolved_exact_required

- row_count: `40`
- priority_counts: `{'P1': 40}`
- label_counts: `{'HOLD': 19, 'REPROCESS': 21}`
- projected_status_counts: `{'safe_resolved': 40}`
- owner_modes: `{'RUNTIME_AUDIT_GAP_REVIEW': 19, 'RUNTIME_REPLAY': 21}`
- sample_post_ids: `11660273, 11663535, 11663557, 11665124, 11668325, 11673102, 11677915, 11677926, 11681172, 11690841, 11694019, 11702094`

### runtime_replay_with_projection_followup_seed_required

- row_count: `9`
- priority_counts: `{'P0': 9}`
- label_counts: `{'REPROCESS': 9}`
- projected_status_counts: `{'safe_resolved': 9}`
- owner_modes: `{'RUNTIME_REPLAY_WITH_SHARED_GATE_SEED': 9}`
- sample_post_ids: `11669913, 11697242, 11697256, 11718114, 11666741, 11694068, 11663511, 11669926, 11706831`

### shared_gate_runtime_block_repair_required

- row_count: `1`
- priority_counts: `{'P0': 1}`
- label_counts: `{'REPROCESS': 1}`
- projected_status_counts: `{'safe_resolved': 1}`
- owner_modes: `{'CODE_OR_RUNTIME_CONTRACT_REPAIR': 1}`
- sample_post_ids: `11677924`

### source_native_canonical_variant_review_required

- row_count: `1`
- priority_counts: `{'P0': 1}`
- label_counts: `{'HOLD': 1}`
- projected_status_counts: `{'safe_resolved': 1}`
- owner_modes: `{'SOURCE_NATIVE_OR_CANONICAL_REVIEW': 1}`
- sample_post_ids: `11694063`
