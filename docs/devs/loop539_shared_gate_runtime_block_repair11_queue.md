# loop539_shared_gate_runtime_block_repair11_queue

## 요약

- source_queue_id: `loop538_shared_gate_seeded_runtime_failure_action_queue`
- gate: `REVIEW-LOCKED`
- repair_rows: `11`
- runtime_replay_allowed_rows: `0`
- primary_repair_lane_counts: `{'candidate_preservation_or_scrub_repair': 4, 'scope_or_nonwork_monotonicity_repair': 4, 'title_url_or_variant_trace_repair': 3}`
- repair_facet_counts: `{'candidate_preservation_or_scrub': 11, 'current_projection_candidate_alignment_review': 11, 'official_support_reconciliation': 4, 'public_identity_serialization_trace': 11, 'scope_or_nonwork_monotonicity': 4, 'search_blind_or_missing_preflight': 10, 'title_url_or_variant_trace': 3}`
- search_gate_counts: `{'SEARCH_BLIND_BLOCKER': 4, 'SEARCH_EVIDENCE_MISSING': 1, 'SEARCH_OK': 1, 'SEARCH_RECOVERED_CONDITIONAL': 5}`
- projection_runtime_scope_conflict_counts: `{'no_conflict': 11}`
- projection_runtime_scope_conflict_kind_counts: `{'none': 11}`
- current_projection_candidate_alignment_counts: `{'missing_current_projection_candidate': 11}`
- current_projection_candidate_review_rows: `11`
- candidate_support_state_counts: `{'missing_current_projection_candidate_support': 11}`
- repair_readiness_counts: `{'candidate_alignment_review_required': 11}`
- repair_batch_lane_counts: `{'B1_missing_candidate_alignment_review': 11}`
- runtime_release_gate_counts: `{'BLOCKED_UNTIL_CANONICAL_CANDIDATE_RECHECK': 11}`
- validation_issue_count: `0`
- approval: `false`
- semantic_quality: `REVIEW-LOCKED`

## 승인 경계

- 이 repair queue는 runtime replay 입력이 아니다.
- 수리 전 동일 packet 반복 실행을 금지한다.
- search degraded 또는 missing 행은 `search-blind 조건부`를 보존한다.
- 완료 기준은 계속 `full375 collateral GO + full_scan 경로 정의`다.

## Next repair batches

### B1_missing_candidate_alignment_review

- row_count: `11`
- runtime_release_gate: `BLOCKED_UNTIL_CANONICAL_CANDIDATE_RECHECK`
- runtime_replay_allowed_rows: `0`
- primary_repair_lane_counts: `{'candidate_preservation_or_scrub_repair': 4, 'scope_or_nonwork_monotonicity_repair': 4, 'title_url_or_variant_trace_repair': 3}`
- search_gate_counts: `{'SEARCH_BLIND_BLOCKER': 4, 'SEARCH_EVIDENCE_MISSING': 1, 'SEARCH_OK': 1, 'SEARCH_RECOVERED_CONDITIONAL': 5}`
- current_projection_candidate_alignment_counts: `{'missing_current_projection_candidate': 11}`
- candidate_support_state_counts: `{'missing_current_projection_candidate_support': 11}`
- post_ids: `11669913, 11697242, 11697256, 11718114, 11666741, 11694068, 11663511, 11669926, 11669933, 11677924, 11706831`

## Repair lanes

### candidate_preservation_or_scrub_repair

- row_count: `4`
- search_gate_counts: `{'SEARCH_BLIND_BLOCKER': 2, 'SEARCH_EVIDENCE_MISSING': 1, 'SEARCH_RECOVERED_CONDITIONAL': 1}`
- facet_counts: `{'candidate_preservation_or_scrub': 4, 'current_projection_candidate_alignment_review': 4, 'public_identity_serialization_trace': 4, 'search_blind_or_missing_preflight': 4}`
- projection_runtime_scope_conflict_rows: `0`
- projection_runtime_scope_conflict_kind_counts: `{'none': 4}`
- current_projection_candidate_alignment_counts: `{'missing_current_projection_candidate': 4}`
- current_projection_candidate_review_rows: `4`
- candidate_support_state_counts: `{'missing_current_projection_candidate_support': 4}`
- repair_readiness_counts: `{'candidate_alignment_review_required': 4}`
- repair_batch_lane_counts: `{'B1_missing_candidate_alignment_review': 4}`
- runtime_release_gate_counts: `{'BLOCKED_UNTIL_CANONICAL_CANDIDATE_RECHECK': 4}`
- sample_post_ids: `11697256, 11666741, 11694068, 11669926`

### scope_or_nonwork_monotonicity_repair

- row_count: `4`
- search_gate_counts: `{'SEARCH_BLIND_BLOCKER': 1, 'SEARCH_OK': 1, 'SEARCH_RECOVERED_CONDITIONAL': 2}`
- facet_counts: `{'candidate_preservation_or_scrub': 4, 'current_projection_candidate_alignment_review': 4, 'official_support_reconciliation': 1, 'public_identity_serialization_trace': 4, 'scope_or_nonwork_monotonicity': 4, 'search_blind_or_missing_preflight': 3}`
- projection_runtime_scope_conflict_rows: `0`
- projection_runtime_scope_conflict_kind_counts: `{'none': 4}`
- current_projection_candidate_alignment_counts: `{'missing_current_projection_candidate': 4}`
- current_projection_candidate_review_rows: `4`
- candidate_support_state_counts: `{'missing_current_projection_candidate_support': 4}`
- repair_readiness_counts: `{'candidate_alignment_review_required': 4}`
- repair_batch_lane_counts: `{'B1_missing_candidate_alignment_review': 4}`
- runtime_release_gate_counts: `{'BLOCKED_UNTIL_CANONICAL_CANDIDATE_RECHECK': 4}`
- sample_post_ids: `11669913, 11697242, 11718114, 11706831`

### title_url_or_variant_trace_repair

- row_count: `3`
- search_gate_counts: `{'SEARCH_BLIND_BLOCKER': 1, 'SEARCH_RECOVERED_CONDITIONAL': 2}`
- facet_counts: `{'candidate_preservation_or_scrub': 3, 'current_projection_candidate_alignment_review': 3, 'official_support_reconciliation': 3, 'public_identity_serialization_trace': 3, 'search_blind_or_missing_preflight': 3, 'title_url_or_variant_trace': 3}`
- projection_runtime_scope_conflict_rows: `0`
- projection_runtime_scope_conflict_kind_counts: `{'none': 3}`
- current_projection_candidate_alignment_counts: `{'missing_current_projection_candidate': 3}`
- current_projection_candidate_review_rows: `3`
- candidate_support_state_counts: `{'missing_current_projection_candidate_support': 3}`
- repair_readiness_counts: `{'candidate_alignment_review_required': 3}`
- repair_batch_lane_counts: `{'B1_missing_candidate_alignment_review': 3}`
- runtime_release_gate_counts: `{'BLOCKED_UNTIL_CANONICAL_CANDIDATE_RECHECK': 3}`
- sample_post_ids: `11663511, 11669933, 11677924`

## 다음 조건

- contract repair 뒤에만 runtime replay 후보로 되돌린다.
- replay 뒤에는 full375 collateral을 다시 확인한다.
