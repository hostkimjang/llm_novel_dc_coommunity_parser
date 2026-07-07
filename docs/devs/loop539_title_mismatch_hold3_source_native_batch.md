# loop539_title_mismatch_hold3_source_native_batch

## 요약

- source_queue_id: `loop538_shared_gate_seeded_runtime_failure_action_queue`
- gate: `REVIEW-LOCKED`
- selected_rows: `3`
- runtime_input_candidate_rows: `0`
- source_native_review_rows: `3`
- search_replay_required_rows: `3`
- label_counts: `{'HOLD': 3}`
- priority_counts: `{'P0': 3}`
- dispatch_lane_counts: `{'source_native_or_blind_review': 3}`
- audit_status_counts: `{'FAIL_SAFE_RESOLVED_TITLE_MISMATCH': 3}`
- validation_issue_count: `0`
- approval: `false`
- semantic_quality: `REVIEW-LOCKED`

## 승인 경계

- 이 batch는 실행 순서를 정한 산출물이며 approval이 아니다.
- `runtime_input_candidate_rows`는 입력 생성 후보일 뿐 runtime replay 결과가 아니다.
- `HOLD`/`INFO_MISSING` 행은 source-native/blind review 전까지 hard-hold 완화 대상이 아니다.
- 완료 기준은 계속 `full375 collateral GO + full_scan 경로 정의`다.

## Lanes

### search_replay_required

- row_count: `3`
- label_counts: `{'HOLD': 3}`
- priority_counts: `{'P0': 3}`
- dispatch_lane_counts: `{'source_native_or_blind_review': 3}`
- sample_post_ids: `11660277, 11694063, 11718098`

### source_native_or_blind_canonical_review

- row_count: `3`
- label_counts: `{'HOLD': 3}`
- priority_counts: `{'P0': 3}`
- dispatch_lane_counts: `{'source_native_or_blind_review': 3}`
- sample_post_ids: `11660277, 11694063, 11718098`
