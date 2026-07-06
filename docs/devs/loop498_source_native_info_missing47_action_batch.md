# loop498_source_native_info_missing47_action_batch

## 요약

- source_queue_id: `loop497_current_full375_review_adjusted_residual111_action_queue`
- gate: `REVIEW-LOCKED`
- selected_rows: `47`
- runtime_input_candidate_rows: `0`
- source_native_review_rows: `47`
- search_replay_required_rows: `0`
- label_counts: `{'INFO_MISSING': 47}`
- priority_counts: `{'None': 47}`
- dispatch_lane_counts: `{'source_native_or_blind_review': 47}`
- audit_status_counts: `{'None': 47}`
- validation_issue_count: `0`
- approval: `false`
- semantic_quality: `REVIEW-LOCKED`

## 승인 경계

- 이 batch는 실행 순서를 정한 산출물이며 approval이 아니다.
- `runtime_input_candidate_rows`는 입력 생성 후보일 뿐 runtime replay 결과가 아니다.
- `HOLD`/`INFO_MISSING` 행은 source-native/blind review 전까지 hard-hold 완화 대상이 아니다.
- 완료 기준은 계속 `full375 collateral GO + full_scan 경로 정의`다.

## Lanes

### source_native_or_blind_review

- row_count: `47`
- label_counts: `{'INFO_MISSING': 47}`
- priority_counts: `{'None': 47}`
- dispatch_lane_counts: `{'source_native_or_blind_review': 47}`
- sample_post_ids: `11660262, 11663554, 11677924, 11682749, 11689292, 11692436, 11694044, 11703658, 11705230, 11710036, 11714903, 11658621`
