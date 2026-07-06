# loop502_shared_gate_runtime_block_repair28_queue

## 요약

- source_queue_id: `loop500_shared_gate_residual37_prior_runtime_followup_queue`
- gate: `REVIEW-LOCKED`
- repair_rows: `28`
- runtime_replay_allowed_rows: `0`
- primary_repair_lane_counts: `{'candidate_preservation_or_scrub_repair': 9, 'image_or_alias_anchor_contract_repair': 1, 'scope_or_nonwork_monotonicity_repair': 9, 'title_url_or_variant_trace_repair': 9}`
- repair_facet_counts: `{'candidate_preservation_or_scrub': 28, 'image_or_alias_anchor_contract': 5, 'official_support_reconciliation': 11, 'public_identity_serialization_trace': 28, 'scope_or_nonwork_monotonicity': 15, 'search_blind_or_missing_preflight': 26, 'title_url_or_variant_trace': 9}`
- search_gate_counts: `{'SEARCH_BLIND_BLOCKER': 9, 'SEARCH_EVIDENCE_MISSING': 3, 'SEARCH_OK': 2, 'SEARCH_RECOVERED_CONDITIONAL': 14}`
- validation_issue_count: `0`
- approval: `false`
- semantic_quality: `REVIEW-LOCKED`

## 승인 경계

- 이 repair queue는 runtime replay 입력이 아니다.
- 수리 전 동일 packet 반복 실행을 금지한다.
- search degraded 또는 missing 행은 `search-blind 조건부`를 보존한다.
- 완료 기준은 계속 `full375 collateral GO + full_scan 경로 정의`다.

## Repair lanes

### candidate_preservation_or_scrub_repair

- row_count: `9`
- search_gate_counts: `{'SEARCH_BLIND_BLOCKER': 3, 'SEARCH_EVIDENCE_MISSING': 2, 'SEARCH_OK': 1, 'SEARCH_RECOVERED_CONDITIONAL': 3}`
- facet_counts: `{'candidate_preservation_or_scrub': 9, 'public_identity_serialization_trace': 9, 'search_blind_or_missing_preflight': 8}`
- sample_post_ids: `11660271, 11665124, 11677926, 11681172, 11690841, 11697242, 11697256, 11710049, 11666741`

### image_or_alias_anchor_contract_repair

- row_count: `1`
- search_gate_counts: `{'SEARCH_RECOVERED_CONDITIONAL': 1}`
- facet_counts: `{'candidate_preservation_or_scrub': 1, 'image_or_alias_anchor_contract': 1, 'official_support_reconciliation': 1, 'public_identity_serialization_trace': 1, 'search_blind_or_missing_preflight': 1}`
- sample_post_ids: `11684372`

### scope_or_nonwork_monotonicity_repair

- row_count: `9`
- search_gate_counts: `{'SEARCH_BLIND_BLOCKER': 4, 'SEARCH_EVIDENCE_MISSING': 1, 'SEARCH_RECOVERED_CONDITIONAL': 4}`
- facet_counts: `{'candidate_preservation_or_scrub': 9, 'official_support_reconciliation': 2, 'public_identity_serialization_trace': 9, 'scope_or_nonwork_monotonicity': 9, 'search_blind_or_missing_preflight': 9}`
- sample_post_ids: `11663521, 11668325, 11669913, 11698910, 11706871, 11710021, 11718110, 11718114, 11710020`

### title_url_or_variant_trace_repair

- row_count: `9`
- search_gate_counts: `{'SEARCH_BLIND_BLOCKER': 2, 'SEARCH_OK': 1, 'SEARCH_RECOVERED_CONDITIONAL': 6}`
- facet_counts: `{'candidate_preservation_or_scrub': 9, 'image_or_alias_anchor_contract': 4, 'official_support_reconciliation': 8, 'public_identity_serialization_trace': 9, 'scope_or_nonwork_monotonicity': 6, 'search_blind_or_missing_preflight': 8, 'title_url_or_variant_trace': 9}`
- sample_post_ids: `11663535, 11663557, 11677915, 11694019, 11702094, 11708447, 11714887, 11718099, 11673077`

## 다음 조건

- contract repair 뒤에만 runtime replay 후보로 되돌린다.
- replay 뒤에는 full375 collateral을 다시 확인한다.
