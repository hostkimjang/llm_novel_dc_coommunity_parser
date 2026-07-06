# loop500_shared_gate_residual37_prior_runtime_followup_queue

## 요약

- source_projection_id: `loop500_shared_gate_residual37_projection`
- gate: `REVIEW-LOCKED`
- followup_action_queue_rows: `37`
- label_counts: `{'HOLD': 4, 'REPROCESS': 33}`
- priority_counts: `{'P0': 31, 'P1': 6}`
- projected_status_counts: `{'safe_resolved': 37}`
- exact_match_counts: `{'match': 37}`
- prior_runtime_audit_status_counts: `{'FAIL_RUNTIME_PROMOTION_BLOCKED': 28, 'FAIL_SAFE_RESOLVED_TITLE_MISMATCH': 2, 'FAIL_VARIANT_COMPACT_MATCH_ONLY': 1, 'NO_PRIOR_AUDIT': 1, 'PASS_EXACT_SAFE_RESOLVED': 5}`
- runtime_replay_candidate_rows: `6`
- variant_review_rows: `3`
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

- row_count: `28`
- priority_counts: `{'P0': 28}`
- label_counts: `{'REPROCESS': 28}`
- projected_status_counts: `{'safe_resolved': 28}`
- owner_modes: `{'CODE_OR_RUNTIME_CONTRACT_REPAIR': 28}`
- sample_post_ids: `11660271, 11663521, 11663535, 11663557, 11665124, 11668325, 11669913, 11677915, 11677926, 11681172, 11684372, 11690841`

### full375_collateral_recheck_after_runtime

- row_count: `6`
- priority_counts: `{'P1': 6}`
- label_counts: `{'HOLD': 1, 'REPROCESS': 5}`
- projected_status_counts: `{'safe_resolved': 6}`
- owner_modes: `{'RUNTIME_AUDIT_GAP_REVIEW': 1, 'RUNTIME_REPLAY': 5}`
- sample_post_ids: `11660273, 11673096, 11679537, 11665121, 11679553, 11710036`

### prior_runtime_expected_audit_missing_review_required

- row_count: `1`
- priority_counts: `{'P1': 1}`
- label_counts: `{'HOLD': 1}`
- projected_status_counts: `{'safe_resolved': 1}`
- owner_modes: `{'RUNTIME_AUDIT_GAP_REVIEW': 1}`
- sample_post_ids: `11710036`

### prior_runtime_promotion_block_repair_required

- row_count: `28`
- priority_counts: `{'P0': 28}`
- label_counts: `{'REPROCESS': 28}`
- projected_status_counts: `{'safe_resolved': 28}`
- owner_modes: `{'CODE_OR_RUNTIME_CONTRACT_REPAIR': 28}`
- sample_post_ids: `11660271, 11663521, 11663535, 11663557, 11665124, 11668325, 11669913, 11677915, 11677926, 11681172, 11684372, 11690841`

### prior_runtime_title_mismatch_review_required

- row_count: `3`
- priority_counts: `{'P0': 3}`
- label_counts: `{'HOLD': 3}`
- projected_status_counts: `{'safe_resolved': 3}`
- owner_modes: `{'SOURCE_NATIVE_OR_CANONICAL_REVIEW': 3}`
- sample_post_ids: `11673102, 11698870, 11694068`

### runtime_replay_after_variant_review

- row_count: `3`
- priority_counts: `{'P0': 3}`
- label_counts: `{'HOLD': 3}`
- projected_status_counts: `{'safe_resolved': 3}`
- owner_modes: `{'SOURCE_NATIVE_OR_CANONICAL_REVIEW': 3}`
- sample_post_ids: `11673102, 11698870, 11694068`

### runtime_replay_projected_safe_resolved_exact_required

- row_count: `6`
- priority_counts: `{'P1': 6}`
- label_counts: `{'HOLD': 1, 'REPROCESS': 5}`
- projected_status_counts: `{'safe_resolved': 6}`
- owner_modes: `{'RUNTIME_AUDIT_GAP_REVIEW': 1, 'RUNTIME_REPLAY': 5}`
- sample_post_ids: `11660273, 11673096, 11679537, 11665121, 11679553, 11710036`

### shared_gate_runtime_block_repair_required

- row_count: `28`
- priority_counts: `{'P0': 28}`
- label_counts: `{'REPROCESS': 28}`
- projected_status_counts: `{'safe_resolved': 28}`
- owner_modes: `{'CODE_OR_RUNTIME_CONTRACT_REPAIR': 28}`
- sample_post_ids: `11660271, 11663521, 11663535, 11663557, 11665124, 11668325, 11669913, 11677915, 11677926, 11681172, 11684372, 11690841`

### source_native_canonical_variant_review_required

- row_count: `3`
- priority_counts: `{'P0': 3}`
- label_counts: `{'HOLD': 3}`
- projected_status_counts: `{'safe_resolved': 3}`
- owner_modes: `{'SOURCE_NATIVE_OR_CANONICAL_REVIEW': 3}`
- sample_post_ids: `11673102, 11698870, 11694068`
