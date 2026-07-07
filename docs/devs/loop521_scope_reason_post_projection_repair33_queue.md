# loop521_scope_reason_post_projection_repair33_queue

## 요약

- source_queue_id: `loop521_loop520_projected_safe57_expected_failure_queue`
- gate: `REVIEW-LOCKED`
- repair_rows: `33`
- runtime_replay_allowed_rows: `0`
- primary_repair_lane_counts: `{'candidate_preservation_or_scrub_repair': 9, 'image_or_alias_anchor_contract_repair': 6, 'scope_or_nonwork_monotonicity_repair': 10, 'title_url_or_variant_trace_repair': 8}`
- repair_facet_counts: `{'candidate_preservation_or_scrub': 33, 'image_or_alias_anchor_contract': 7, 'official_support_reconciliation': 17, 'public_identity_serialization_trace': 33, 'scope_or_nonwork_monotonicity': 13, 'search_blind_or_missing_preflight': 32, 'title_url_or_variant_trace': 8}`
- search_gate_counts: `{'SEARCH_BLIND_BLOCKER': 15, 'SEARCH_EVIDENCE_MISSING': 8, 'SEARCH_OK': 1, 'SEARCH_RECOVERED_CONDITIONAL': 9}`
- projection_runtime_scope_conflict_counts: `{'no_conflict': 33}`
- projection_runtime_scope_conflict_kind_counts: `{'none': 33}`
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
- search_gate_counts: `{'SEARCH_BLIND_BLOCKER': 3, 'SEARCH_EVIDENCE_MISSING': 3, 'SEARCH_RECOVERED_CONDITIONAL': 3}`
- facet_counts: `{'candidate_preservation_or_scrub': 9, 'public_identity_serialization_trace': 9, 'search_blind_or_missing_preflight': 9}`
- projection_runtime_scope_conflict_rows: `0`
- projection_runtime_scope_conflict_kind_counts: `{'none': 9}`
- sample_post_ids: `11665124, 11677926, 11690841, 11697242, 11706871, 11666741, 11694068, 11669926, 11682775`

### image_or_alias_anchor_contract_repair

- row_count: `6`
- search_gate_counts: `{'SEARCH_BLIND_BLOCKER': 2, 'SEARCH_EVIDENCE_MISSING': 2, 'SEARCH_RECOVERED_CONDITIONAL': 2}`
- facet_counts: `{'candidate_preservation_or_scrub': 6, 'image_or_alias_anchor_contract': 6, 'official_support_reconciliation': 6, 'public_identity_serialization_trace': 6, 'scope_or_nonwork_monotonicity': 2, 'search_blind_or_missing_preflight': 6}`
- projection_runtime_scope_conflict_rows: `0`
- projection_runtime_scope_conflict_kind_counts: `{'none': 6}`
- sample_post_ids: `11681172, 11702094, 11710049, 11679547, 11682767, 11700483`

### scope_or_nonwork_monotonicity_repair

- row_count: `10`
- search_gate_counts: `{'SEARCH_BLIND_BLOCKER': 3, 'SEARCH_EVIDENCE_MISSING': 3, 'SEARCH_OK': 1, 'SEARCH_RECOVERED_CONDITIONAL': 3}`
- facet_counts: `{'candidate_preservation_or_scrub': 10, 'official_support_reconciliation': 3, 'public_identity_serialization_trace': 10, 'scope_or_nonwork_monotonicity': 10, 'search_blind_or_missing_preflight': 9}`
- projection_runtime_scope_conflict_rows: `0`
- projection_runtime_scope_conflict_kind_counts: `{'none': 10}`
- sample_post_ids: `11660271, 11660273, 11669913, 11697256, 11710021, 11714887, 11718114, 11668300, 11698859, 11708470`

### title_url_or_variant_trace_repair

- row_count: `8`
- search_gate_counts: `{'SEARCH_BLIND_BLOCKER': 7, 'SEARCH_RECOVERED_CONDITIONAL': 1}`
- facet_counts: `{'candidate_preservation_or_scrub': 8, 'image_or_alias_anchor_contract': 1, 'official_support_reconciliation': 8, 'public_identity_serialization_trace': 8, 'scope_or_nonwork_monotonicity': 1, 'search_blind_or_missing_preflight': 8, 'title_url_or_variant_trace': 8}`
- projection_runtime_scope_conflict_rows: `0`
- projection_runtime_scope_conflict_kind_counts: `{'none': 8}`
- sample_post_ids: `11663535, 11663557, 11708447, 11718099, 11718110, 11673080, 11705230, 11708478`

## 다음 조건

- contract repair 뒤에만 runtime replay 후보로 되돌린다.
- replay 뒤에는 full375 collateral을 다시 확인한다.
