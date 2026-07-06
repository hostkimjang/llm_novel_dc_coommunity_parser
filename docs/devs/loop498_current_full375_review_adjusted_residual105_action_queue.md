# loop498_current_full375_review_adjusted_residual105_action_queue

## 요약

- source_review_id: `loop498_current_full375_p0_review_summary`
- gate: `REVIEW-LOCKED`
- source_rows: `137`
- residual_action_queue_rows: `105`
- label_counts: `{'HOLD': 24, 'INFO_MISSING': 36, 'REPROCESS': 45}`
- closed_post_ids_excluded: `[]`
- excluded_residual_action_queue_rows: `0`
- unreviewed_regression_rows_added: `0`
- action_group_count: `18`
- validation_issue_count: `0`
- approval: `false`
- semantic_quality: `REVIEW-LOCKED`

## 승인 경계

- 이 큐 분해는 residual action queue를 실행 가능하게 만든 산출물이며 approval이 아니다.
- search recovery가 `unrecovered_degraded=0`으로 닫히기 전까지 `promotion_blocked`는 `search-blind conditional`이다.
- `REPROCESS`는 코드/계약/runtime replay 후보이고, `HOLD`는 native image/web/source 또는 policy review 후보다.

## Action groups

### P2 alias_relation_review_required

- row_count: `2`
- owner_mode: `POLICY_OR_NATIVE_REVIEW`
- label_counts: `{'HOLD': 2}`
- bucket_counts: `{'safe_loss_resolved_to_null': 1, 'unsafe_promotion_from_hold': 1}`
- sample_post_ids: `11694067, 11665110`

### P2 author_new_work_context_review_required

- row_count: `1`
- owner_mode: `POLICY_OR_NATIVE_REVIEW`
- label_counts: `{'HOLD': 1}`
- bucket_counts: `{'unsafe_promotion_from_hold': 1}`
- sample_post_ids: `11697234`

### P1 candidate_set_rebuild_required

- row_count: `2`
- owner_mode: `RUNTIME_REPLAY_OR_REVIEW`
- label_counts: `{'REPROCESS': 2}`
- bucket_counts: `{'wrong_work_title_flip': 2}`
- sample_post_ids: `11671514, 11710036`

### P1 canonical_title_cleanup_required

- row_count: `3`
- owner_mode: `RUNTIME_REPLAY_OR_REVIEW`
- label_counts: `{'REPROCESS': 3}`
- bucket_counts: `{'wrong_work_title_flip': 3}`
- sample_post_ids: `11716464, 11674694, 11705230`

### P1 character_bridge_review_required

- row_count: `2`
- owner_mode: `POLICY_OR_NATIVE_REVIEW`
- label_counts: `{'HOLD': 1, 'REPROCESS': 1}`
- bucket_counts: `{'unsafe_promotion_from_hold': 1, 'wrong_work_title_flip': 1}`
- sample_post_ids: `11671538, 11692436`

### P2 image_native_review_required

- row_count: `17`
- owner_mode: `POLICY_OR_NATIVE_REVIEW`
- label_counts: `{'HOLD': 17}`
- bucket_counts: `{'safe_loss_resolved_to_null': 14, 'wrong_work_title_flip': 3}`
- sample_post_ids: `11682791, 11661856, 11666725, 11671512, 11681152, 11681178, 11685994, 11687661, 11706844, 11710047, 11711632, 11714885`

### P1 intent_guard_review

- row_count: `1`
- owner_mode: `RUNTIME_REPLAY_OR_REVIEW`
- label_counts: `{'REPROCESS': 1}`
- bucket_counts: `{'unsafe_promotion_from_hold': 1}`
- sample_post_ids: `11657047`

### P1 native_web_review_required

- row_count: `24`
- owner_mode: `POLICY_OR_NATIVE_REVIEW`
- label_counts: `{'HOLD': 23, 'REPROCESS': 1}`
- bucket_counts: `{'safe_loss_resolved_to_null': 17, 'unsafe_promotion_from_hold': 3, 'wrong_work_title_flip': 4}`
- sample_post_ids: `11682791, 11671538, 11694067, 11697234, 11661856, 11665110, 11666725, 11671512, 11681152, 11681178, 11685994, 11687661`

### P1 p0_safe_loss_resolved_to_null_review_required

- row_count: `25`
- owner_mode: `SOURCE_NATIVE_OR_BLIND_REVIEW`
- label_counts: `{'INFO_MISSING': 25}`
- bucket_counts: `{'safe_loss_resolved_to_null': 25}`
- sample_post_ids: `11660254, 11660277, 11663540, 11666699, 11666731, 11668288, 11668300, 11669907, 11669926, 11682767, 11685987, 11694035`

### P1 p0_unsafe_promotion_from_hold_review_required

- row_count: `11`
- owner_mode: `SOURCE_NATIVE_OR_BLIND_REVIEW`
- label_counts: `{'INFO_MISSING': 11}`
- bucket_counts: `{'unsafe_promotion_from_hold': 11}`
- sample_post_ids: `11658621, 11668324, 11669911, 11684370, 11690855, 11702081, 11703657, 11705257, 11708466, 11710043, 11710045`

### P2 policy_or_canonical_title_review_required

- row_count: `2`
- owner_mode: `POLICY_OR_NATIVE_REVIEW`
- label_counts: `{'HOLD': 2}`
- bucket_counts: `{'safe_loss_resolved_to_null': 1, 'wrong_work_title_flip': 1}`
- sample_post_ids: `11698871, 11714903`

### P2 preserve_candidates

- row_count: `1`
- owner_mode: `POLICY_OR_NATIVE_REVIEW`
- label_counts: `{'HOLD': 1}`
- bucket_counts: `{'wrong_work_title_flip': 1}`
- sample_post_ids: `11661863`

### P0 repair_after_wrong_work

- row_count: `7`
- owner_mode: `CODE_OR_RUNTIME_REPAIR`
- label_counts: `{'REPROCESS': 7}`
- bucket_counts: `{'wrong_work_title_flip': 7}`
- sample_post_ids: `11671514, 11679547, 11716464, 11663514, 11674694, 11692436, 11705230`

### P0 repair_safe_loss_restore_supported_title

- row_count: `36`
- owner_mode: `CODE_OR_RUNTIME_REPAIR`
- label_counts: `{'REPROCESS': 36}`
- bucket_counts: `{'safe_loss_resolved_to_null': 36}`
- sample_post_ids: `11660271, 11660273, 11663521, 11663535, 11663557, 11665124, 11668325, 11669913, 11673096, 11673102, 11677915, 11677926`

### P0 repair_unsafe_promotion

- row_count: `1`
- owner_mode: `CODE_OR_RUNTIME_REPAIR`
- label_counts: `{'REPROCESS': 1}`
- bucket_counts: `{'unsafe_promotion_from_hold': 1}`
- sample_post_ids: `11657047`

### P1 shared_promotion_gate_wiring_required

- row_count: `37`
- owner_mode: `RUNTIME_REPLAY_OR_REVIEW`
- label_counts: `{'REPROCESS': 37}`
- bucket_counts: `{'safe_loss_resolved_to_null': 36, 'wrong_work_title_flip': 1}`
- sample_post_ids: `11660271, 11660273, 11663521, 11663535, 11663557, 11665124, 11668325, 11669913, 11673096, 11673102, 11677915, 11677926`

### P1 source_native_or_blind_review_required

- row_count: `36`
- owner_mode: `SOURCE_NATIVE_OR_BLIND_REVIEW`
- label_counts: `{'INFO_MISSING': 36}`
- bucket_counts: `{'safe_loss_resolved_to_null': 25, 'unsafe_promotion_from_hold': 11}`
- sample_post_ids: `11658621, 11668324, 11669911, 11684370, 11690855, 11702081, 11703657, 11705257, 11708466, 11710043, 11710045, 11660254`

### P2 title_surface_specificity_review_required

- row_count: `1`
- owner_mode: `POLICY_OR_NATIVE_REVIEW`
- label_counts: `{'HOLD': 1}`
- bucket_counts: `{'safe_loss_resolved_to_null': 1}`
- sample_post_ids: `11718057`
