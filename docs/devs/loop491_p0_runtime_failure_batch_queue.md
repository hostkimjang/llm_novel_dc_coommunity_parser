# loop491_p0_runtime_failure_batch

## 요약

- source_queue_id: `loop490_projected_safe46_runtime_failure_action_queue`
- gate: `REVIEW-LOCKED`
- selected_rows: `23`
- runtime_input_candidate_rows: `14`
- source_native_review_rows: `9`
- search_replay_required_rows: `13`
- label_counts: `{'HOLD': 9, 'REPROCESS': 14}`
- priority_counts: `{'P0': 23}`
- dispatch_lane_counts: `{'canonical_variant_policy_review': 1, 'runtime_repair_with_search_replay': 9, 'runtime_repair_without_search_replay': 5, 'source_native_or_blind_review': 8}`
- audit_status_counts: `{'FAIL_RUNTIME_PROMOTION_BLOCKED': 17, 'FAIL_SAFE_RESOLVED_TITLE_MISMATCH': 5, 'FAIL_VARIANT_COMPACT_MATCH_ONLY': 1}`
- validation_issue_count: `0`
- approval: `false`
- semantic_quality: `REVIEW-LOCKED`

## 승인 경계

- 이 batch는 실행 순서를 정한 산출물이며 approval이 아니다.
- `runtime_input_candidate_rows`는 입력 생성 후보일 뿐 runtime replay 결과가 아니다.
- `HOLD` 행은 source-native/blind review 전까지 hard-hold 완화 대상이 아니다.
- 완료 기준은 계속 `full375 collateral GO + full_scan 경로 정의`다.

## Lanes

### canonical_variant_policy_review

- row_count: `1`
- label_counts: `{'HOLD': 1}`
- priority_counts: `{'P0': 1}`
- dispatch_lane_counts: `{'canonical_variant_policy_review': 1}`
- sample_post_ids: `11698870`

### runtime_repair_replay

- row_count: `14`
- label_counts: `{'REPROCESS': 14}`
- priority_counts: `{'P0': 14}`
- dispatch_lane_counts: `{'runtime_repair_with_search_replay': 9, 'runtime_repair_without_search_replay': 5}`
- sample_post_ids: `11663521, 11665124, 11677915, 11677926, 11684372, 11694019, 11698910, 11708447, 11710049, 11716475, 11718099, 11718110`

### search_replay_required

- row_count: `13`
- label_counts: `{'HOLD': 4, 'REPROCESS': 9}`
- priority_counts: `{'P0': 13}`
- dispatch_lane_counts: `{'canonical_variant_policy_review': 1, 'runtime_repair_with_search_replay': 9, 'source_native_or_blind_review': 3}`
- sample_post_ids: `11663521, 11663535, 11665124, 11673102, 11677926, 11698870, 11698910, 11705230, 11708447, 11710049, 11716475, 11718110`

### source_native_or_blind_canonical_review

- row_count: `8`
- label_counts: `{'HOLD': 8}`
- priority_counts: `{'P0': 8}`
- dispatch_lane_counts: `{'source_native_or_blind_review': 8}`
- sample_post_ids: `11663535, 11673102, 11692436, 11705230, 11714887, 11718098, 11673077, 11694068`
