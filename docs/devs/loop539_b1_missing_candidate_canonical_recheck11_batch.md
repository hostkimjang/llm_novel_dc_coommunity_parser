# loop539_b1_missing_candidate_canonical_recheck11_batch

## 요약

- source_queue_id: `loop539_shared_gate_runtime_block_repair11_queue`
- gate: `REVIEW-LOCKED`
- selected_rows: `11`
- verdict_required_rows: `11`
- runtime_replay_allowed_rows: `0`
- review_lane_counts: `{'B1_missing_candidate_alignment_review': 11}`
- alignment_state_counts: `{'missing_current_projection_candidate': 11}`
- candidate_support_state_counts: `{'missing_current_projection_candidate_support': 11}`
- search_gate_counts: `{'SEARCH_BLIND_BLOCKER': 4, 'SEARCH_EVIDENCE_MISSING': 1, 'SEARCH_OK': 1, 'SEARCH_RECOVERED_CONDITIONAL': 5}`
- primary_repair_lane_counts: `{'candidate_preservation_or_scrub_repair': 4, 'scope_or_nonwork_monotonicity_repair': 4, 'title_url_or_variant_trace_repair': 3}`
- validation_issue_count: `0`
- approval: `false`
- semantic_quality: `REVIEW-LOCKED`

## 승인 경계

- 이 batch는 canonical verdict가 아니라 판정 입력이다.
- B1 row는 source-native 또는 blind canonical review 전까지 runtime replay로 넘기지 않는다.
- 판정 뒤에도 contract test와 full375 collateral 확인 전에는 full_scan approval을 열지 않는다.
- 완료 기준은 계속 `full375 collateral GO + full_scan 경로 정의`다.

## Review groups

### B1_missing_candidate_alignment_review

- row_count: `11`
- candidate_support_state_counts: `{'missing_current_projection_candidate_support': 11}`
- search_gate_counts: `{'SEARCH_BLIND_BLOCKER': 4, 'SEARCH_EVIDENCE_MISSING': 1, 'SEARCH_OK': 1, 'SEARCH_RECOVERED_CONDITIONAL': 5}`
- primary_repair_lane_counts: `{'candidate_preservation_or_scrub_repair': 4, 'scope_or_nonwork_monotonicity_repair': 4, 'title_url_or_variant_trace_repair': 3}`
- post_ids: `11669913, 11697242, 11697256, 11718114, 11666741, 11694068, 11663511, 11669926, 11669933, 11677924, 11706831`

## 판정 옵션

- `EXPECTED_SOURCE_NATIVE_TITLE_CONFIRMED`: expected/source-native title이 맞다. current projection 후보를 scrub/restore 계약으로 정리해야 한다.
- `CURRENT_PROJECTION_CANDIDATE_CONFIRMED`: current projection 후보가 맞다. expected/source-native 기준 자체를 blind 근거로 갱신해야 한다.
- `RELATED_CANONICAL_VARIANT_CONFIRMED`: 같은 작품의 canonical variant다. variant policy 계약 테스트가 필요하다.
- `WRONG_OR_UNRELATED_CANDIDATE`: current projection 후보가 wrong-work 또는 무관 후보다. candidate scrub 계약 테스트가 필요하다.
- `INSUFFICIENT_EVIDENCE_HOLD`: 증거가 부족하다. hard-hold 또는 native-web review로 남긴다.
