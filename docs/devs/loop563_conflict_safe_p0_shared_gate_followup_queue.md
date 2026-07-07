# loop563_conflict_safe_p0_shared_gate_followup_queue

## 요약

- source_projection_id: `loop563_conflict_safe_p0_shared_gate_projection`
- gate: `REVIEW-LOCKED`
- followup_action_queue_rows: `41`
- label_counts: `{'HOLD': 8, 'REPROCESS': 33}`
- priority_counts: `{'P0': 21, 'P1': 20}`
- projected_status_counts: `{'safe_resolved': 41}`
- exact_match_counts: `{'match': 41}`
- prior_runtime_audit_status_counts: `{'FAIL_RUNTIME_PROMOTION_BLOCKED': 14, 'FAIL_SAFE_RESOLVED_TITLE_MISMATCH': 7, 'NO_PRIOR_AUDIT': 1, 'PASS_EXACT_SAFE_RESOLVED': 19}`
- runtime_replay_candidate_rows: `20`
- runtime_seed_replay_candidate_rows: `10`
- variant_review_rows: `7`
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

- row_count: `4`
- priority_counts: `{'P0': 4}`
- label_counts: `{'REPROCESS': 4}`
- projected_status_counts: `{'safe_resolved': 4}`
- owner_modes: `{'CODE_OR_RUNTIME_CONTRACT_REPAIR': 4}`
- sample_post_ids: `11665124, 11710021, 11710049, 11698859`

### full375_collateral_recheck_after_runtime

- row_count: `30`
- priority_counts: `{'P0': 10, 'P1': 20}`
- label_counts: `{'HOLD': 1, 'REPROCESS': 29}`
- projected_status_counts: `{'safe_resolved': 30}`
- owner_modes: `{'RUNTIME_AUDIT_GAP_REVIEW': 1, 'RUNTIME_REPLAY': 19, 'RUNTIME_REPLAY_WITH_SHARED_GATE_SEED': 10}`
- sample_post_ids: `11663557, 11668325, 11669913, 11677926, 11690841, 11697242, 11697256, 11708447, 11714887, 11718099, 11718114, 11666741`

### prior_runtime_expected_audit_missing_review_required

- row_count: `1`
- priority_counts: `{'P1': 1}`
- label_counts: `{'HOLD': 1}`
- projected_status_counts: `{'safe_resolved': 1}`
- owner_modes: `{'RUNTIME_AUDIT_GAP_REVIEW': 1}`
- sample_post_ids: `11677924`

### prior_runtime_promotion_block_repair_required

- row_count: `4`
- priority_counts: `{'P0': 4}`
- label_counts: `{'REPROCESS': 4}`
- projected_status_counts: `{'safe_resolved': 4}`
- owner_modes: `{'CODE_OR_RUNTIME_CONTRACT_REPAIR': 4}`
- sample_post_ids: `11665124, 11710021, 11710049, 11698859`

### prior_runtime_title_mismatch_review_required

- row_count: `7`
- priority_counts: `{'P0': 7}`
- label_counts: `{'HOLD': 7}`
- projected_status_counts: `{'safe_resolved': 7}`
- owner_modes: `{'SOURCE_NATIVE_OR_CANONICAL_REVIEW': 7}`
- sample_post_ids: `11660273, 11673102, 11694019, 11702094, 11668300, 11689292, 11706842`

### projection_followup_official_url_repair_required

- row_count: `4`
- priority_counts: `{'P0': 4}`
- label_counts: `{'REPROCESS': 4}`
- projected_status_counts: `{'safe_resolved': 4}`
- owner_modes: `{'CODE_OR_RUNTIME_CONTRACT_REPAIR': 4}`
- sample_post_ids: `11665124, 11710021, 11710049, 11698859`

### runtime_replay_after_variant_review

- row_count: `7`
- priority_counts: `{'P0': 7}`
- label_counts: `{'HOLD': 7}`
- projected_status_counts: `{'safe_resolved': 7}`
- owner_modes: `{'SOURCE_NATIVE_OR_CANONICAL_REVIEW': 7}`
- sample_post_ids: `11660273, 11673102, 11694019, 11702094, 11668300, 11689292, 11706842`

### runtime_replay_projected_safe_resolved_exact_required

- row_count: `20`
- priority_counts: `{'P1': 20}`
- label_counts: `{'HOLD': 1, 'REPROCESS': 19}`
- projected_status_counts: `{'safe_resolved': 20}`
- owner_modes: `{'RUNTIME_AUDIT_GAP_REVIEW': 1, 'RUNTIME_REPLAY': 19}`
- sample_post_ids: `11663557, 11669913, 11677926, 11708447, 11666741, 11665121, 11666713, 11669921, 11669926, 11673080, 11677924, 11681159`

### runtime_replay_with_projection_followup_seed_required

- row_count: `10`
- priority_counts: `{'P0': 10}`
- label_counts: `{'REPROCESS': 10}`
- projected_status_counts: `{'safe_resolved': 10}`
- owner_modes: `{'RUNTIME_REPLAY_WITH_SHARED_GATE_SEED': 10}`
- sample_post_ids: `11668325, 11690841, 11697242, 11697256, 11714887, 11718099, 11718114, 11682767, 11692436, 11710046`

### shared_gate_runtime_block_repair_required

- row_count: `4`
- priority_counts: `{'P0': 4}`
- label_counts: `{'REPROCESS': 4}`
- projected_status_counts: `{'safe_resolved': 4}`
- owner_modes: `{'CODE_OR_RUNTIME_CONTRACT_REPAIR': 4}`
- sample_post_ids: `11665124, 11710021, 11710049, 11698859`

### source_native_canonical_variant_review_required

- row_count: `7`
- priority_counts: `{'P0': 7}`
- label_counts: `{'HOLD': 7}`
- projected_status_counts: `{'safe_resolved': 7}`
- owner_modes: `{'SOURCE_NATIVE_OR_CANONICAL_REVIEW': 7}`
- sample_post_ids: `11660273, 11673102, 11694019, 11702094, 11668300, 11689292, 11706842`
