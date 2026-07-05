# loop485_shared_gate_projection_followup_action_queue

## 요약

- source_projection_id: `loop484_shared_gate_counterevidence_projection`
- gate: `REVIEW-LOCKED`
- followup_action_queue_rows: `59`
- label_counts: `{'HOLD': 35, 'REPROCESS': 24}`
- priority_counts: `{'P0': 12, 'P1': 17, 'P2': 30}`
- projected_status_counts: `{'output_consistency_lint': 3, 'promotion_blocked': 42, 'safe_resolved': 14}`
- exact_match_counts: `{'match': 9, 'mismatch': 50}`
- runtime_replay_candidate_rows: `9`
- variant_review_rows: `5`
- lint_followup_rows: `3`
- still_blocked_rows: `42`
- validation_issue_count: `0`
- approval: `false`
- semantic_quality: `REVIEW-LOCKED`

## 승인 경계

- 이 큐는 Loop484 projection의 후속 실행 단위이며 approval이 아니다.
- `safe_resolved` projection도 runtime replay와 publication contract audit 전에는 해소 처리하지 않는다.
- source-native exact title mismatch는 canonical variant 또는 wrong-work review 전까지 publish 근거가 아니다.
- 완료 기준은 여전히 `full375 collateral GO + full_scan 경로 정의`다.

## Action groups

### blocked_projection_manual_review_required

- row_count: `7`
- priority_counts: `{'P2': 7}`
- label_counts: `{'HOLD': 7}`
- projected_status_counts: `{'promotion_blocked': 7}`
- owner_modes: `{'MANUAL_REVIEW': 7}`
- sample_post_ids: `11663535, 11669933, 11677915, 11690841, 11698870, 11716475, 11718099`

### full375_collateral_recheck_after_runtime

- row_count: `9`
- priority_counts: `{'P0': 9}`
- label_counts: `{'REPROCESS': 9}`
- projected_status_counts: `{'safe_resolved': 9}`
- owner_modes: `{'RUNTIME_REPLAY': 9}`
- sample_post_ids: `11658620, 11660265, 11661881, 11676314, 11685987, 11692444, 11694035, 11713220, 11716498`

### output_consistency_lint_contract_followup_required

- row_count: `3`
- priority_counts: `{'P0': 3}`
- label_counts: `{'REPROCESS': 3}`
- projected_status_counts: `{'output_consistency_lint': 3}`
- owner_modes: `{'CODE_CONTRACT_OR_LINT_REVIEW': 3}`
- sample_post_ids: `11681172, 11697242, 11710021`

### publication_trace_lint_review_required

- row_count: `3`
- priority_counts: `{'P0': 3}`
- label_counts: `{'REPROCESS': 3}`
- projected_status_counts: `{'output_consistency_lint': 3}`
- owner_modes: `{'CODE_CONTRACT_OR_LINT_REVIEW': 3}`
- sample_post_ids: `11681172, 11697242, 11710021`

### runtime_replay_after_variant_review

- row_count: `5`
- priority_counts: `{'P1': 5}`
- label_counts: `{'HOLD': 5}`
- projected_status_counts: `{'safe_resolved': 5}`
- owner_modes: `{'SOURCE_NATIVE_OR_CANONICAL_REVIEW': 5}`
- sample_post_ids: `11668300, 11674694, 11694049, 11705230, 11708447`

### runtime_replay_projected_safe_resolved_exact_required

- row_count: `9`
- priority_counts: `{'P0': 9}`
- label_counts: `{'REPROCESS': 9}`
- projected_status_counts: `{'safe_resolved': 9}`
- owner_modes: `{'RUNTIME_REPLAY': 9}`
- sample_post_ids: `11658620, 11660265, 11661881, 11676314, 11685987, 11692444, 11694035, 11713220, 11716498`

### scope_or_nonwork_hard_hold_review_required

- row_count: `23`
- priority_counts: `{'P2': 23}`
- label_counts: `{'HOLD': 23}`
- projected_status_counts: `{'promotion_blocked': 23}`
- owner_modes: `{'POLICY_OR_SOURCE_NATIVE_REVIEW': 23}`
- sample_post_ids: `11660257, 11663514, 11663521, 11663540, 11663557, 11666731, 11668288, 11668325, 11669913, 11671507, 11673096, 11692436`

### shared_gate_support_gap_repair_required

- row_count: `12`
- priority_counts: `{'P1': 12}`
- label_counts: `{'REPROCESS': 12}`
- projected_status_counts: `{'promotion_blocked': 12}`
- owner_modes: `{'CODE_OR_CANDIDATE_REPAIR': 12}`
- sample_post_ids: `11660271, 11660273, 11660277, 11665124, 11673102, 11677926, 11682767, 11684372, 11694019, 11697256, 11702094, 11708432`

### source_native_canonical_variant_review_required

- row_count: `5`
- priority_counts: `{'P1': 5}`
- label_counts: `{'HOLD': 5}`
- projected_status_counts: `{'safe_resolved': 5}`
- owner_modes: `{'SOURCE_NATIVE_OR_CANONICAL_REVIEW': 5}`
- sample_post_ids: `11668300, 11674694, 11694049, 11705230, 11708447`
