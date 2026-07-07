# loop599_full375_unreviewed40_action_queue

## 요약

- source_review_id: `loop595_residual46_native_web_judge_source_native_review`
- gate: `REVIEW-LOCKED`
- source_rows: `25`
- residual_action_queue_rows: `40`
- label_counts: `{'INFO_MISSING': 40}`
- closed_post_ids_excluded: `[11660232, 11660273, 11661856, 11661863, 11663554, 11665110, 11665124, 11666725, 11668324, 11669907, 11671512, 11671514, 11671538, 11681178, 11682749, 11682775, 11682791, 11682792, 11685994, 11687661, 11694035, 11694041, 11694067, 11698859, 11698865, 11698870, 11698871, 11700483, 11700500, 11703658, 11703674, 11705231, 11706844, 11706867, 11708453, 11710036, 11710047, 11710049, 11711632, 11714885, 11714903, 11716480, 11716505, 11718057, 11718105, 11718114]`
- excluded_residual_action_queue_rows: `51`
- source_excluded_residual_action_queue_rows: `18`
- unreviewed_excluded_regression_rows: `33`
- unreviewed_regression_rows_added: `40`
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

- row_count: `9`
- owner_mode: `SOURCE_NATIVE_OR_BLIND_REVIEW`
- label_counts: `{'INFO_MISSING': 9}`
- bucket_counts: `{'safe_loss_resolved_to_null': 9}`
- sample_post_ids: `11660254, 11668278, 11668305, 11695609, 11697239, 11697249, 11698904, 11703640, 11714892`

### P0 p0_unsafe_promotion_from_hold_review_required

- row_count: `20`
- owner_mode: `SOURCE_NATIVE_OR_BLIND_REVIEW`
- label_counts: `{'INFO_MISSING': 20}`
- bucket_counts: `{'unsafe_promotion_from_hold': 20}`
- sample_post_ids: `11658637, 11660238, 11669928, 11671501, 11673086, 11674703, 11676317, 11677957, 11681177, 11682768, 11687618, 11687635`

### P0 p0_wrong_work_title_flip_review_required

- row_count: `11`
- owner_mode: `SOURCE_NATIVE_OR_BLIND_REVIEW`
- label_counts: `{'INFO_MISSING': 11}`
- bucket_counts: `{'wrong_work_title_flip': 11}`
- sample_post_ids: `11660262, 11665099, 11666700, 11669929, 11671500, 11676314, 11681152, 11694044, 11703631, 11706842, 11718097`

### P1 source_native_or_blind_review_required

- row_count: `40`
- owner_mode: `SOURCE_NATIVE_OR_BLIND_REVIEW`
- label_counts: `{'INFO_MISSING': 40}`
- bucket_counts: `{'safe_loss_resolved_to_null': 9, 'unsafe_promotion_from_hold': 20, 'wrong_work_title_flip': 11}`
- sample_post_ids: `11658637, 11660238, 11660254, 11660262, 11665099, 11666700, 11668278, 11668305, 11669928, 11669929, 11671500, 11671501`
