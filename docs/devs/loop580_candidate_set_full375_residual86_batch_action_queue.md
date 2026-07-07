# loop580_candidate_set_full375_residual86_batch_action_queue

## 요약

- source_review_id: `loop580_candidate_set_full375_residual86_batch_action_queue_triage_only_source`
- gate: `REVIEW-LOCKED`
- source_rows: `0`
- residual_action_queue_rows: `86`
- label_counts: `{'INFO_MISSING': 86}`
- closed_post_ids_excluded: `[]`
- excluded_residual_action_queue_rows: `0`
- unreviewed_regression_rows_added: `86`
- action_group_count: `4`
- validation_issue_count: `0`
- approval: `false`
- semantic_quality: `REVIEW-LOCKED`

## 승인 경계

- 이 큐 분해는 residual action queue를 실행 가능하게 만든 산출물이며 approval이 아니다.
- search recovery가 `unrecovered_degraded=0`으로 닫히기 전까지 `promotion_blocked`는 `search-blind conditional`이다.
- `REPROCESS`는 코드/계약/runtime replay 후보이고, `HOLD`는 native image/web/source 또는 policy review 후보다.

## 실행 그룹

### P0 p0_safe_loss_resolved_to_null_review_required

- row_count: `41`
- owner_mode: `SOURCE_NATIVE_OR_BLIND_REVIEW`
- label_counts: `{'INFO_MISSING': 41}`
- bucket_counts: `{'safe_loss_resolved_to_null': 41}`
- sample_post_ids: `11660254, 11661856, 11661863, 11665110, 11665124, 11666725, 11668278, 11668305, 11671514, 11681178, 11682749, 11682775`

### P0 p0_unsafe_promotion_from_hold_review_required

- row_count: `24`
- owner_mode: `SOURCE_NATIVE_OR_BLIND_REVIEW`
- label_counts: `{'INFO_MISSING': 24}`
- bucket_counts: `{'unsafe_promotion_from_hold': 24}`
- sample_post_ids: `11658637, 11660238, 11668324, 11669928, 11671501, 11671538, 11673086, 11674703, 11676317, 11677957, 11681177, 11682768`

### P0 p0_wrong_work_title_flip_review_required

- row_count: `21`
- owner_mode: `SOURCE_NATIVE_OR_BLIND_REVIEW`
- label_counts: `{'INFO_MISSING': 21}`
- bucket_counts: `{'wrong_work_title_flip': 21}`
- sample_post_ids: `11660232, 11660262, 11660273, 11663554, 11665099, 11666700, 11669907, 11669929, 11671500, 11671512, 11676314, 11681152`

### P1 source_native_or_blind_review_required

- row_count: `86`
- owner_mode: `SOURCE_NATIVE_OR_BLIND_REVIEW`
- label_counts: `{'INFO_MISSING': 86}`
- bucket_counts: `{'safe_loss_resolved_to_null': 41, 'unsafe_promotion_from_hold': 24, 'wrong_work_title_flip': 21}`
- sample_post_ids: `11658637, 11660232, 11660238, 11660254, 11660262, 11660273, 11661856, 11661863, 11663554, 11665099, 11665110, 11665124`
