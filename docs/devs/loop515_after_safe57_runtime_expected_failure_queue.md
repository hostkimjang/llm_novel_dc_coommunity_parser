# loop515_after_safe57_runtime_expected_failure_queue

## 요약

- source_projection_id: `loop515_residual100_shared_gate_projection`
- gate: `REVIEW-LOCKED`
- followup_action_queue_rows: `57`
- label_counts: `{'HOLD': 10, 'REPROCESS': 47}`
- priority_counts: `{'P0': 42, 'P1': 15}`
- projected_status_counts: `{'safe_resolved': 57}`
- exact_match_counts: `{'match': 57}`
- prior_runtime_audit_status_counts: `{'FAIL_RUNTIME_PROMOTION_BLOCKED': 32, 'FAIL_SAFE_RESOLVED_TITLE_MISMATCH': 10, 'PASS_EXACT_SAFE_RESOLVED': 15}`
- runtime_replay_candidate_rows: `15`
- variant_review_rows: `10`
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

- row_count: `32`
- priority_counts: `{'P0': 32}`
- label_counts: `{'REPROCESS': 32}`
- projected_status_counts: `{'safe_resolved': 32}`
- owner_modes: `{'CODE_OR_RUNTIME_CONTRACT_REPAIR': 32}`
- sample_post_ids: `11660271, 11660273, 11663535, 11663557, 11665124, 11669913, 11677926, 11681172, 11690841, 11697242, 11697256, 11702094`

### full375_collateral_recheck_after_runtime

- row_count: `15`
- priority_counts: `{'P1': 15}`
- label_counts: `{'REPROCESS': 15}`
- projected_status_counts: `{'safe_resolved': 15}`
- owner_modes: `{'RUNTIME_REPLAY': 15}`
- sample_post_ids: `11665121, 11660277, 11663511, 11669933, 11677924, 11681159, 11692444, 11694063, 11694065, 11700500, 11705251, 11706831`

### prior_runtime_promotion_block_repair_required

- row_count: `32`
- priority_counts: `{'P0': 32}`
- label_counts: `{'REPROCESS': 32}`
- projected_status_counts: `{'safe_resolved': 32}`
- owner_modes: `{'CODE_OR_RUNTIME_CONTRACT_REPAIR': 32}`
- sample_post_ids: `11660271, 11660273, 11663535, 11663557, 11665124, 11669913, 11677926, 11681172, 11690841, 11697242, 11697256, 11702094`

### prior_runtime_title_mismatch_review_required

- row_count: `10`
- priority_counts: `{'P0': 10}`
- label_counts: `{'HOLD': 10}`
- projected_status_counts: `{'safe_resolved': 10}`
- owner_modes: `{'SOURCE_NATIVE_OR_CANONICAL_REVIEW': 10}`
- sample_post_ids: `11668325, 11673102, 11677915, 11694019, 11673077, 11666713, 11669921, 11689292, 11692436, 11706842`

### runtime_replay_after_variant_review

- row_count: `10`
- priority_counts: `{'P0': 10}`
- label_counts: `{'HOLD': 10}`
- projected_status_counts: `{'safe_resolved': 10}`
- owner_modes: `{'SOURCE_NATIVE_OR_CANONICAL_REVIEW': 10}`
- sample_post_ids: `11668325, 11673102, 11677915, 11694019, 11673077, 11666713, 11669921, 11689292, 11692436, 11706842`

### runtime_replay_projected_safe_resolved_exact_required

- row_count: `15`
- priority_counts: `{'P1': 15}`
- label_counts: `{'REPROCESS': 15}`
- projected_status_counts: `{'safe_resolved': 15}`
- owner_modes: `{'RUNTIME_REPLAY': 15}`
- sample_post_ids: `11665121, 11660277, 11663511, 11669933, 11677924, 11681159, 11692444, 11694063, 11694065, 11700500, 11705251, 11706831`

### shared_gate_runtime_block_repair_required

- row_count: `32`
- priority_counts: `{'P0': 32}`
- label_counts: `{'REPROCESS': 32}`
- projected_status_counts: `{'safe_resolved': 32}`
- owner_modes: `{'CODE_OR_RUNTIME_CONTRACT_REPAIR': 32}`
- sample_post_ids: `11660271, 11660273, 11663535, 11663557, 11665124, 11669913, 11677926, 11681172, 11690841, 11697242, 11697256, 11702094`

### source_native_canonical_variant_review_required

- row_count: `10`
- priority_counts: `{'P0': 10}`
- label_counts: `{'HOLD': 10}`
- projected_status_counts: `{'safe_resolved': 10}`
- owner_modes: `{'SOURCE_NATIVE_OR_CANONICAL_REVIEW': 10}`
- sample_post_ids: `11668325, 11673102, 11677915, 11694019, 11673077, 11666713, 11669921, 11689292, 11692436, 11706842`
