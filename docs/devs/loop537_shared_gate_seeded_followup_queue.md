# loop537_shared_gate_seeded_followup_action_queue

## 요약

- source_projection_id: `loop536_current_full375_shared_gate_residual54_projection`
- gate: `REVIEW-LOCKED`
- followup_action_queue_rows: `54`
- label_counts: `{'HOLD': 10, 'REPROCESS': 44}`
- priority_counts: `{'P0': 39, 'P1': 15}`
- projected_status_counts: `{'safe_resolved': 54}`
- exact_match_counts: `{'match': 54}`
- prior_runtime_audit_status_counts: `{'FAIL_RUNTIME_PROMOTION_BLOCKED': 29, 'FAIL_SAFE_RESOLVED_TITLE_MISMATCH': 10, 'PASS_EXACT_SAFE_RESOLVED': 15}`
- runtime_replay_candidate_rows: `15`
- runtime_seed_replay_candidate_rows: `20`
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

- row_count: `9`
- priority_counts: `{'P0': 9}`
- label_counts: `{'REPROCESS': 9}`
- projected_status_counts: `{'safe_resolved': 9}`
- owner_modes: `{'CODE_OR_RUNTIME_CONTRACT_REPAIR': 9}`
- sample_post_ids: `11663557, 11665124, 11681172, 11710021, 11710049, 11682767, 11682775, 11698859, 11700483`

### full375_collateral_recheck_after_runtime

- row_count: `35`
- priority_counts: `{'P0': 20, 'P1': 15}`
- label_counts: `{'REPROCESS': 35}`
- projected_status_counts: `{'safe_resolved': 35}`
- owner_modes: `{'RUNTIME_REPLAY': 15, 'RUNTIME_REPLAY_WITH_SHARED_GATE_SEED': 20}`
- sample_post_ids: `11660273, 11663535, 11669913, 11677926, 11690841, 11697242, 11697256, 11702094, 11708447, 11714887, 11718099, 11718110`

### prior_runtime_promotion_block_repair_required

- row_count: `9`
- priority_counts: `{'P0': 9}`
- label_counts: `{'REPROCESS': 9}`
- projected_status_counts: `{'safe_resolved': 9}`
- owner_modes: `{'CODE_OR_RUNTIME_CONTRACT_REPAIR': 9}`
- sample_post_ids: `11663557, 11665124, 11681172, 11710021, 11710049, 11682767, 11682775, 11698859, 11700483`

### prior_runtime_title_mismatch_review_required

- row_count: `10`
- priority_counts: `{'P0': 10}`
- label_counts: `{'HOLD': 10}`
- projected_status_counts: `{'safe_resolved': 10}`
- owner_modes: `{'SOURCE_NATIVE_OR_CANONICAL_REVIEW': 10}`
- sample_post_ids: `11668325, 11673102, 11677915, 11694019, 11673077, 11666713, 11669921, 11689292, 11692436, 11706842`

### projection_followup_official_url_repair_required

- row_count: `9`
- priority_counts: `{'P0': 9}`
- label_counts: `{'REPROCESS': 9}`
- projected_status_counts: `{'safe_resolved': 9}`
- owner_modes: `{'CODE_OR_RUNTIME_CONTRACT_REPAIR': 9}`
- sample_post_ids: `11663557, 11665124, 11681172, 11710021, 11710049, 11682767, 11682775, 11698859, 11700483`

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

### runtime_replay_with_projection_followup_seed_required

- row_count: `20`
- priority_counts: `{'P0': 20}`
- label_counts: `{'REPROCESS': 20}`
- projected_status_counts: `{'safe_resolved': 20}`
- owner_modes: `{'RUNTIME_REPLAY_WITH_SHARED_GATE_SEED': 20}`
- sample_post_ids: `11660273, 11663535, 11669913, 11677926, 11690841, 11697242, 11697256, 11702094, 11708447, 11714887, 11718099, 11718110`

### shared_gate_runtime_block_repair_required

- row_count: `9`
- priority_counts: `{'P0': 9}`
- label_counts: `{'REPROCESS': 9}`
- projected_status_counts: `{'safe_resolved': 9}`
- owner_modes: `{'CODE_OR_RUNTIME_CONTRACT_REPAIR': 9}`
- sample_post_ids: `11663557, 11665124, 11681172, 11710021, 11710049, 11682767, 11682775, 11698859, 11700483`

### source_native_canonical_variant_review_required

- row_count: `10`
- priority_counts: `{'P0': 10}`
- label_counts: `{'HOLD': 10}`
- projected_status_counts: `{'safe_resolved': 10}`
- owner_modes: `{'SOURCE_NATIVE_OR_CANONICAL_REVIEW': 10}`
- sample_post_ids: `11668325, 11673102, 11677915, 11694019, 11673077, 11666713, 11669921, 11689292, 11692436, 11706842`
