# loop545_current_full375_residual97_shared_gate_runtime_block_repair_queue

## 요약

- source_queue_id: `loop545_current_full375_residual97_runtime_failure_action_queue`
- gate: `REVIEW-LOCKED`
- repair_rows: `22`
- runtime_replay_allowed_rows: `0`
- primary_repair_lane_counts: `{'candidate_preservation_or_scrub_repair': 7, 'image_or_alias_anchor_contract_repair': 2, 'scope_or_nonwork_monotonicity_repair': 10, 'title_url_or_variant_trace_repair': 3}`
- repair_facet_counts: `{'candidate_preservation_or_scrub': 22, 'current_projection_candidate_alignment_review': 14, 'image_or_alias_anchor_contract': 4, 'official_support_reconciliation': 8, 'public_identity_serialization_trace': 22, 'scope_or_nonwork_monotonicity': 12, 'search_blind_or_missing_preflight': 22, 'title_url_or_variant_trace': 3}`
- search_gate_counts: `{'SEARCH_BLIND_BLOCKER': 12, 'SEARCH_EVIDENCE_MISSING': 4, 'SEARCH_RECOVERED_CONDITIONAL': 6}`
- projection_runtime_scope_conflict_counts: `{'no_conflict': 22}`
- projection_runtime_scope_conflict_kind_counts: `{'none': 22}`
- current_projection_candidate_alignment_counts: `{'different_title_candidate_review': 7, 'related_title_surface_review': 7, 'same_title_surface': 8}`
- current_projection_candidate_review_rows: `14`
- candidate_support_state_counts: `{'candidate_preservation_only_no_official_detail': 1, 'image_ocr_preservation_pending_official_url': 1, 'non_official_candidate_preservation_only': 6, 'official_url_candidate_support': 14}`
- repair_readiness_counts: `{'candidate_alignment_review_required': 14, 'same_title_search_preflight_required': 7, 'same_title_search_recovered_contract_candidate': 1}`
- repair_batch_lane_counts: `{'B1_different_candidate_alignment_review': 7, 'B1_related_candidate_alignment_review': 7, 'B2_same_title_search_blind_preflight': 6, 'B2_same_title_search_missing_preflight': 1, 'B4_same_title_recovered_support_contract': 1}`
- runtime_release_gate_counts: `{'BLOCKED_UNTIL_CANONICAL_CANDIDATE_RECHECK': 14, 'BLOCKED_UNTIL_CONTRACT_TESTS_PASS': 1, 'BLOCKED_UNTIL_SEARCH_PREFLIGHT_GO': 7}`
- validation_issue_count: `0`
- approval: `false`
- semantic_quality: `REVIEW-LOCKED`

## 승인 경계

- 이 repair queue는 runtime replay 입력이 아니다.
- 수리 전 동일 packet 반복 실행을 금지한다.
- search degraded 또는 missing 행은 `search-blind 조건부`를 보존한다.
- 완료 기준은 계속 `full375 collateral GO + full_scan 경로 정의`다.

## Next repair batches

### B1_different_candidate_alignment_review

- row_count: `7`
- runtime_release_gate: `BLOCKED_UNTIL_CANONICAL_CANDIDATE_RECHECK`
- runtime_replay_allowed_rows: `0`
- primary_repair_lane_counts: `{'candidate_preservation_or_scrub_repair': 4, 'scope_or_nonwork_monotonicity_repair': 3}`
- search_gate_counts: `{'SEARCH_BLIND_BLOCKER': 3, 'SEARCH_EVIDENCE_MISSING': 1, 'SEARCH_RECOVERED_CONDITIONAL': 3}`
- current_projection_candidate_alignment_counts: `{'different_title_candidate_review': 7}`
- candidate_support_state_counts: `{'non_official_candidate_preservation_only': 2, 'official_url_candidate_support': 5}`
- post_ids: `11665124, 11668325, 11690841, 11697242, 11710049, 11692436, 11710046`

### B1_related_candidate_alignment_review

- row_count: `7`
- runtime_release_gate: `BLOCKED_UNTIL_CANONICAL_CANDIDATE_RECHECK`
- runtime_replay_allowed_rows: `0`
- primary_repair_lane_counts: `{'candidate_preservation_or_scrub_repair': 2, 'image_or_alias_anchor_contract_repair': 1, 'scope_or_nonwork_monotonicity_repair': 4}`
- search_gate_counts: `{'SEARCH_BLIND_BLOCKER': 3, 'SEARCH_EVIDENCE_MISSING': 2, 'SEARCH_RECOVERED_CONDITIONAL': 2}`
- current_projection_candidate_alignment_counts: `{'related_title_surface_review': 7}`
- candidate_support_state_counts: `{'image_ocr_preservation_pending_official_url': 1, 'non_official_candidate_preservation_only': 3, 'official_url_candidate_support': 3}`
- post_ids: `11697256, 11710021, 11714887, 11718099, 11718114, 11682767, 11698859`

### B2_same_title_search_blind_preflight

- row_count: `6`
- runtime_release_gate: `BLOCKED_UNTIL_SEARCH_PREFLIGHT_GO`
- runtime_replay_allowed_rows: `0`
- primary_repair_lane_counts: `{'candidate_preservation_or_scrub_repair': 1, 'scope_or_nonwork_monotonicity_repair': 2, 'title_url_or_variant_trace_repair': 3}`
- search_gate_counts: `{'SEARCH_BLIND_BLOCKER': 6}`
- current_projection_candidate_alignment_counts: `{'same_title_surface': 6}`
- candidate_support_state_counts: `{'candidate_preservation_only_no_official_detail': 1, 'non_official_candidate_preservation_only': 1, 'official_url_candidate_support': 4}`
- post_ids: `11663535, 11677915, 11718110, 11673077, 11663511, 11705251`

### B2_same_title_search_missing_preflight

- row_count: `1`
- runtime_release_gate: `BLOCKED_UNTIL_SEARCH_PREFLIGHT_GO`
- runtime_replay_allowed_rows: `0`
- primary_repair_lane_counts: `{'image_or_alias_anchor_contract_repair': 1}`
- search_gate_counts: `{'SEARCH_EVIDENCE_MISSING': 1}`
- current_projection_candidate_alignment_counts: `{'same_title_surface': 1}`
- candidate_support_state_counts: `{'official_url_candidate_support': 1}`
- post_ids: `11681172`

### B4_same_title_recovered_support_contract

- row_count: `1`
- runtime_release_gate: `BLOCKED_UNTIL_CONTRACT_TESTS_PASS`
- runtime_replay_allowed_rows: `0`
- primary_repair_lane_counts: `{'scope_or_nonwork_monotonicity_repair': 1}`
- search_gate_counts: `{'SEARCH_RECOVERED_CONDITIONAL': 1}`
- current_projection_candidate_alignment_counts: `{'same_title_surface': 1}`
- candidate_support_state_counts: `{'official_url_candidate_support': 1}`
- post_ids: `11705230`

## Repair lanes

### candidate_preservation_or_scrub_repair

- row_count: `7`
- search_gate_counts: `{'SEARCH_BLIND_BLOCKER': 3, 'SEARCH_EVIDENCE_MISSING': 1, 'SEARCH_RECOVERED_CONDITIONAL': 3}`
- facet_counts: `{'candidate_preservation_or_scrub': 7, 'current_projection_candidate_alignment_review': 6, 'public_identity_serialization_trace': 7, 'search_blind_or_missing_preflight': 7}`
- projection_runtime_scope_conflict_rows: `0`
- projection_runtime_scope_conflict_kind_counts: `{'none': 7}`
- current_projection_candidate_alignment_counts: `{'different_title_candidate_review': 4, 'related_title_surface_review': 2, 'same_title_surface': 1}`
- current_projection_candidate_review_rows: `6`
- candidate_support_state_counts: `{'non_official_candidate_preservation_only': 2, 'official_url_candidate_support': 5}`
- repair_readiness_counts: `{'candidate_alignment_review_required': 6, 'same_title_search_preflight_required': 1}`
- repair_batch_lane_counts: `{'B1_different_candidate_alignment_review': 4, 'B1_related_candidate_alignment_review': 2, 'B2_same_title_search_blind_preflight': 1}`
- runtime_release_gate_counts: `{'BLOCKED_UNTIL_CANONICAL_CANDIDATE_RECHECK': 6, 'BLOCKED_UNTIL_SEARCH_PREFLIGHT_GO': 1}`
- sample_post_ids: `11665124, 11677915, 11690841, 11697242, 11697256, 11710049, 11718099`

### image_or_alias_anchor_contract_repair

- row_count: `2`
- search_gate_counts: `{'SEARCH_BLIND_BLOCKER': 1, 'SEARCH_EVIDENCE_MISSING': 1}`
- facet_counts: `{'candidate_preservation_or_scrub': 2, 'current_projection_candidate_alignment_review': 1, 'image_or_alias_anchor_contract': 2, 'official_support_reconciliation': 2, 'public_identity_serialization_trace': 2, 'search_blind_or_missing_preflight': 2}`
- projection_runtime_scope_conflict_rows: `0`
- projection_runtime_scope_conflict_kind_counts: `{'none': 2}`
- current_projection_candidate_alignment_counts: `{'related_title_surface_review': 1, 'same_title_surface': 1}`
- current_projection_candidate_review_rows: `1`
- candidate_support_state_counts: `{'official_url_candidate_support': 2}`
- repair_readiness_counts: `{'candidate_alignment_review_required': 1, 'same_title_search_preflight_required': 1}`
- repair_batch_lane_counts: `{'B1_related_candidate_alignment_review': 1, 'B2_same_title_search_missing_preflight': 1}`
- runtime_release_gate_counts: `{'BLOCKED_UNTIL_CANONICAL_CANDIDATE_RECHECK': 1, 'BLOCKED_UNTIL_SEARCH_PREFLIGHT_GO': 1}`
- sample_post_ids: `11681172, 11682767`

### scope_or_nonwork_monotonicity_repair

- row_count: `10`
- search_gate_counts: `{'SEARCH_BLIND_BLOCKER': 5, 'SEARCH_EVIDENCE_MISSING': 2, 'SEARCH_RECOVERED_CONDITIONAL': 3}`
- facet_counts: `{'candidate_preservation_or_scrub': 10, 'current_projection_candidate_alignment_review': 7, 'official_support_reconciliation': 3, 'public_identity_serialization_trace': 10, 'scope_or_nonwork_monotonicity': 10, 'search_blind_or_missing_preflight': 10}`
- projection_runtime_scope_conflict_rows: `0`
- projection_runtime_scope_conflict_kind_counts: `{'none': 10}`
- current_projection_candidate_alignment_counts: `{'different_title_candidate_review': 3, 'related_title_surface_review': 4, 'same_title_surface': 3}`
- current_projection_candidate_review_rows: `7`
- candidate_support_state_counts: `{'image_ocr_preservation_pending_official_url': 1, 'non_official_candidate_preservation_only': 4, 'official_url_candidate_support': 5}`
- repair_readiness_counts: `{'candidate_alignment_review_required': 7, 'same_title_search_preflight_required': 2, 'same_title_search_recovered_contract_candidate': 1}`
- repair_batch_lane_counts: `{'B1_different_candidate_alignment_review': 3, 'B1_related_candidate_alignment_review': 4, 'B2_same_title_search_blind_preflight': 2, 'B4_same_title_recovered_support_contract': 1}`
- runtime_release_gate_counts: `{'BLOCKED_UNTIL_CANONICAL_CANDIDATE_RECHECK': 7, 'BLOCKED_UNTIL_CONTRACT_TESTS_PASS': 1, 'BLOCKED_UNTIL_SEARCH_PREFLIGHT_GO': 2}`
- sample_post_ids: `11663535, 11668325, 11710021, 11714887, 11718114, 11663511, 11692436, 11698859, 11705230, 11710046`

### title_url_or_variant_trace_repair

- row_count: `3`
- search_gate_counts: `{'SEARCH_BLIND_BLOCKER': 3}`
- facet_counts: `{'candidate_preservation_or_scrub': 3, 'image_or_alias_anchor_contract': 2, 'official_support_reconciliation': 3, 'public_identity_serialization_trace': 3, 'scope_or_nonwork_monotonicity': 2, 'search_blind_or_missing_preflight': 3, 'title_url_or_variant_trace': 3}`
- projection_runtime_scope_conflict_rows: `0`
- projection_runtime_scope_conflict_kind_counts: `{'none': 3}`
- current_projection_candidate_alignment_counts: `{'same_title_surface': 3}`
- current_projection_candidate_review_rows: `0`
- candidate_support_state_counts: `{'candidate_preservation_only_no_official_detail': 1, 'official_url_candidate_support': 2}`
- repair_readiness_counts: `{'same_title_search_preflight_required': 3}`
- repair_batch_lane_counts: `{'B2_same_title_search_blind_preflight': 3}`
- runtime_release_gate_counts: `{'BLOCKED_UNTIL_SEARCH_PREFLIGHT_GO': 3}`
- sample_post_ids: `11718110, 11673077, 11705251`

## 다음 조건

- contract repair 뒤에만 runtime replay 후보로 되돌린다.
- replay 뒤에는 full375 collateral을 다시 확인한다.
