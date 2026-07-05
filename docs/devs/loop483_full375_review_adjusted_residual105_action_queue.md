# loop483_full375_review_adjusted_residual105_action_queue

## 요약

- source_review_id: `loop481_combined_full375_p0_source_native_review`
- gate: `REVIEW-LOCKED`
- source_rows: `138`
- residual_action_queue_rows: `105`
- label_counts: `{'HOLD': 41, 'INFO_MISSING': 1, 'REPROCESS': 63}`
- closed_post_ids_excluded: `[]`
- excluded_residual_action_queue_rows: `0`
- unreviewed_regression_rows_added: `1`
- action_group_count: `21`
- validation_issue_count: `0`
- approval: `false`
- semantic_quality: `REVIEW-LOCKED`

## 승인 경계

- 이 큐 분해는 residual action queue를 실행 가능하게 만든 산출물이며 approval이 아니다.
- search recovery가 `unrecovered_degraded=0`으로 닫히기 전까지 `promotion_blocked`는 `search-blind conditional`이다.
- `REPROCESS`는 코드/계약/runtime replay 후보이고, `HOLD`는 native image/web/source 또는 policy review 후보다.

## Action groups

### P2 alias_relation_review_required

- row_count: `4`
- owner_mode: `POLICY_OR_NATIVE_REVIEW`
- label_counts: `{'HOLD': 4}`
- bucket_counts: `{'safe_loss_resolved_to_null': 2, 'unsafe_promotion_from_hold': 2}`
- sample_post_ids: `11681180, 11694067, 11665110, 11695609`

### P2 author_new_work_context_review_required

- row_count: `1`
- owner_mode: `POLICY_OR_NATIVE_REVIEW`
- label_counts: `{'HOLD': 1}`
- bucket_counts: `{'unsafe_promotion_from_hold': 1}`
- sample_post_ids: `11697234`

### P1 candidate_set_rebuild_required

- row_count: `4`
- owner_mode: `RUNTIME_REPLAY_OR_REVIEW`
- label_counts: `{'REPROCESS': 4}`
- bucket_counts: `{'safe_loss_resolved_to_null': 3, 'wrong_work_title_flip': 1}`
- sample_post_ids: `11671514, 11676314, 11694035, 11710036`

### P2 canonical_title_policy_review

- row_count: `2`
- owner_mode: `POLICY_OR_NATIVE_REVIEW`
- label_counts: `{'HOLD': 2}`
- bucket_counts: `{'wrong_work_title_flip': 2}`
- sample_post_ids: `11692426, 11694068`

### P2 character_bridge_review_required

- row_count: `2`
- owner_mode: `POLICY_OR_NATIVE_REVIEW`
- label_counts: `{'HOLD': 2}`
- bucket_counts: `{'unsafe_promotion_from_hold': 2}`
- sample_post_ids: `11671538, 11684370`

### P2 image_native_review_required

- row_count: `23`
- owner_mode: `POLICY_OR_NATIVE_REVIEW`
- label_counts: `{'HOLD': 23}`
- bucket_counts: `{'safe_loss_resolved_to_null': 18, 'unsafe_promotion_from_hold': 2, 'wrong_work_title_flip': 3}`
- sample_post_ids: `11660254, 11682791, 11706867, 11685985, 11687635, 11661856, 11666725, 11669907, 11669926, 11671512, 11677924, 11681152`

### P1 intent_permit_guard_required

- row_count: `1`
- owner_mode: `RUNTIME_REPLAY_OR_REVIEW`
- label_counts: `{'REPROCESS': 1}`
- bucket_counts: `{'unsafe_promotion_from_hold': 1}`
- sample_post_ids: `11690855`

### P2 multi_work_policy_review

- row_count: `5`
- owner_mode: `POLICY_OR_NATIVE_REVIEW`
- label_counts: `{'HOLD': 5}`
- bucket_counts: `{'safe_loss_resolved_to_null': 3, 'unsafe_promotion_from_hold': 1, 'wrong_work_title_flip': 1}`
- sample_post_ids: `11673077, 11668324, 11660232, 11666700, 11703674`

### P2 native_web_review_required

- row_count: `33`
- owner_mode: `POLICY_OR_NATIVE_REVIEW`
- label_counts: `{'HOLD': 33}`
- bucket_counts: `{'safe_loss_resolved_to_null': 22, 'unsafe_promotion_from_hold': 8, 'wrong_work_title_flip': 3}`
- sample_post_ids: `11660254, 11682791, 11706867, 11658621, 11671538, 11681180, 11684370, 11685985, 11694067, 11697234, 11703645, 11661856`

### P1 p1_new_resolution_promotion_review_required

- row_count: `1`
- owner_mode: `SOURCE_NATIVE_OR_BLIND_REVIEW`
- label_counts: `{'INFO_MISSING': 1}`
- bucket_counts: `{'new_resolution_promotion': 1}`
- sample_post_ids: `11682800`

### P2 policy_or_canonical_title_review_required

- row_count: `2`
- owner_mode: `POLICY_OR_NATIVE_REVIEW`
- label_counts: `{'HOLD': 2}`
- bucket_counts: `{'safe_loss_resolved_to_null': 2}`
- sample_post_ids: `11698871, 11714903`

### P2 preserve_secondary_candidates

- row_count: `5`
- owner_mode: `POLICY_OR_NATIVE_REVIEW`
- label_counts: `{'HOLD': 5}`
- bucket_counts: `{'safe_loss_resolved_to_null': 3, 'unsafe_promotion_from_hold': 1, 'wrong_work_title_flip': 1}`
- sample_post_ids: `11673077, 11668324, 11660232, 11666700, 11703674`

### P2 promotion_guard_review

- row_count: `1`
- owner_mode: `POLICY_OR_NATIVE_REVIEW`
- label_counts: `{'HOLD': 1}`
- bucket_counts: `{'unsafe_promotion_from_hold': 1}`
- sample_post_ids: `11658621`

### P2 recommendation_context_review_required

- row_count: `1`
- owner_mode: `POLICY_OR_NATIVE_REVIEW`
- label_counts: `{'HOLD': 1}`
- bucket_counts: `{'unsafe_promotion_from_hold': 1}`
- sample_post_ids: `11687635`

### P0 repair_after_unsafe_promotion

- row_count: `1`
- owner_mode: `CODE_OR_RUNTIME_REPAIR`
- label_counts: `{'REPROCESS': 1}`
- bucket_counts: `{'unsafe_promotion_from_hold': 1}`
- sample_post_ids: `11690855`

### P0 repair_after_wrong_work

- row_count: `3`
- owner_mode: `CODE_OR_RUNTIME_REPAIR`
- label_counts: `{'REPROCESS': 3}`
- bucket_counts: `{'wrong_work_title_flip': 3}`
- sample_post_ids: `11671514, 11679547, 11698865`

### P0 repair_safe_loss_restore_supported_title

- row_count: `56`
- owner_mode: `CODE_OR_RUNTIME_REPAIR`
- label_counts: `{'REPROCESS': 56}`
- bucket_counts: `{'safe_loss_resolved_to_null': 56}`
- sample_post_ids: `11658620, 11660257, 11660265, 11660271, 11660273, 11660277, 11661881, 11663514, 11663521, 11663535, 11663540, 11663557`

### P1 shared_promotion_gate_wiring_required

- row_count: `59`
- owner_mode: `RUNTIME_REPLAY_OR_REVIEW`
- label_counts: `{'REPROCESS': 59}`
- bucket_counts: `{'safe_loss_resolved_to_null': 59}`
- sample_post_ids: `11658620, 11660257, 11660265, 11660271, 11660273, 11660277, 11661881, 11663514, 11663521, 11663535, 11663540, 11663557`

### P1 source_main_work_title_needed

- row_count: `1`
- owner_mode: `RUNTIME_REPLAY_OR_REVIEW`
- label_counts: `{'REPROCESS': 1}`
- bucket_counts: `{'wrong_work_title_flip': 1}`
- sample_post_ids: `11698865`

### P1 source_native_or_blind_review_required

- row_count: `1`
- owner_mode: `SOURCE_NATIVE_OR_BLIND_REVIEW`
- label_counts: `{'INFO_MISSING': 1}`
- bucket_counts: `{'new_resolution_promotion': 1}`
- sample_post_ids: `11682800`

### P2 title_surface_specificity_review_required

- row_count: `1`
- owner_mode: `POLICY_OR_NATIVE_REVIEW`
- label_counts: `{'HOLD': 1}`
- bucket_counts: `{'unsafe_promotion_from_hold': 1}`
- sample_post_ids: `11703645`
