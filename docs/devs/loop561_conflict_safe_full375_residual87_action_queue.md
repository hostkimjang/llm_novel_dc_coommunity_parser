# loop561_conflict_safe_full375_residual87_action_queue

## 요약

- source_review_id: `loop560_conflict_safe_full375_prior_compatible_source_native_review`
- gate: `REVIEW-LOCKED`
- source_rows: `126`
- residual_action_queue_rows: `87`
- label_counts: `{'HOLD': 21, 'INFO_MISSING': 5, 'REPROCESS': 61}`
- closed_post_ids_excluded: `[]`
- excluded_residual_action_queue_rows: `0`
- unreviewed_regression_rows_added: `0`
- action_group_count: `27`
- validation_issue_count: `0`
- approval: `false`
- semantic_quality: `REVIEW-LOCKED`

## 승인 경계

- 이 큐 분해는 residual action queue를 실행 가능하게 만든 산출물이며 approval이 아니다.
- search recovery가 `unrecovered_degraded=0`으로 닫히기 전까지 `promotion_blocked`는 `search-blind conditional`이다.
- `REPROCESS`는 코드/계약/runtime replay 후보이고, `HOLD`는 native image/web/source 또는 policy review 후보다.

## Action groups

### P1 alias_collision_guard_required

- row_count: `1`
- owner_mode: `RUNTIME_REPLAY_OR_REVIEW`
- label_counts: `{'REPROCESS': 1}`
- bucket_counts: `{'unsafe_promotion_from_hold': 1}`
- sample_post_ids: `11710044`

### P2 alias_relation_review_required

- row_count: `2`
- owner_mode: `POLICY_OR_NATIVE_REVIEW`
- label_counts: `{'HOLD': 2}`
- bucket_counts: `{'safe_loss_resolved_to_null': 1, 'unsafe_promotion_from_hold': 1}`
- sample_post_ids: `11694067, 11665110`

### P1 candidate_set_rebuild_required

- row_count: `10`
- owner_mode: `POLICY_OR_NATIVE_REVIEW`
- label_counts: `{'HOLD': 1, 'REPROCESS': 9}`
- bucket_counts: `{'safe_loss_resolved_to_null': 6, 'unsafe_promotion_from_hold': 1, 'wrong_work_title_flip': 3}`
- sample_post_ids: `11671514, 11671512, 11694041, 11710044, 11682749, 11694035, 11698865, 11703658, 11705231, 11710036`

### P1 canonical_alias_competition_guard_required

- row_count: `1`
- owner_mode: `RUNTIME_REPLAY_OR_REVIEW`
- label_counts: `{'REPROCESS': 1}`
- bucket_counts: `{'wrong_work_title_flip': 1}`
- sample_post_ids: `11660241`

### P1 canonical_title_cleanup_required

- row_count: `4`
- owner_mode: `RUNTIME_REPLAY_OR_REVIEW`
- label_counts: `{'REPROCESS': 4}`
- bucket_counts: `{'wrong_work_title_flip': 4}`
- sample_post_ids: `11716464, 11674694, 11669907, 11694041`

### P1 character_bridge_review_required

- row_count: `2`
- owner_mode: `POLICY_OR_NATIVE_REVIEW`
- label_counts: `{'HOLD': 1, 'REPROCESS': 1}`
- bucket_counts: `{'safe_loss_resolved_to_null': 1, 'unsafe_promotion_from_hold': 1}`
- sample_post_ids: `11671538, 11692436`

### P1 image_listing_multi_work_guard_required

- row_count: `2`
- owner_mode: `POLICY_OR_NATIVE_REVIEW`
- label_counts: `{'HOLD': 1, 'REPROCESS': 1}`
- bucket_counts: `{'safe_loss_resolved_to_null': 1, 'unsafe_promotion_from_hold': 1}`
- sample_post_ids: `11718105, 11661863`

### P1 image_multi_panel_review_required

- row_count: `1`
- owner_mode: `RUNTIME_REPLAY_OR_REVIEW`
- label_counts: `{'REPROCESS': 1}`
- bucket_counts: `{'safe_loss_resolved_to_null': 1}`
- sample_post_ids: `11677924`

### P1 image_native_review_required

- row_count: `14`
- owner_mode: `POLICY_OR_NATIVE_REVIEW`
- label_counts: `{'HOLD': 13, 'REPROCESS': 1}`
- bucket_counts: `{'safe_loss_resolved_to_null': 12, 'wrong_work_title_flip': 2}`
- sample_post_ids: `11682791, 11661856, 11666725, 11681178, 11685994, 11687661, 11706844, 11710047, 11711632, 11714885, 11716480, 11716505`

### P1 image_platform_url_preference

- row_count: `1`
- owner_mode: `RUNTIME_REPLAY_OR_REVIEW`
- label_counts: `{'REPROCESS': 1}`
- bucket_counts: `{'safe_loss_resolved_to_null': 1}`
- sample_post_ids: `11703658`

### P1 intent_guard_review

- row_count: `3`
- owner_mode: `RUNTIME_REPLAY_OR_REVIEW`
- label_counts: `{'REPROCESS': 3}`
- bucket_counts: `{'unsafe_promotion_from_hold': 2, 'wrong_work_title_flip': 1}`
- sample_post_ids: `11657047, 11698870, 11690855`

### P1 merchandise_or_emoticon_work_context_guard

- row_count: `1`
- owner_mode: `RUNTIME_REPLAY_OR_REVIEW`
- label_counts: `{'REPROCESS': 1}`
- bucket_counts: `{'safe_loss_resolved_to_null': 1}`
- sample_post_ids: `11700483`

### P1 multi_work_guard_required

- row_count: `4`
- owner_mode: `POLICY_OR_NATIVE_REVIEW`
- label_counts: `{'HOLD': 1, 'REPROCESS': 3}`
- bucket_counts: `{'safe_loss_resolved_to_null': 2, 'unsafe_promotion_from_hold': 2}`
- sample_post_ids: `11668324, 11718105, 11694035, 11708453`

### P1 native_web_review_required

- row_count: `24`
- owner_mode: `POLICY_OR_NATIVE_REVIEW`
- label_counts: `{'HOLD': 20, 'REPROCESS': 4}`
- bucket_counts: `{'safe_loss_resolved_to_null': 18, 'unsafe_promotion_from_hold': 2, 'wrong_work_title_flip': 4}`
- sample_post_ids: `11682791, 11671538, 11694067, 11661856, 11665110, 11666725, 11681178, 11685994, 11687661, 11698871, 11706844, 11710047`

### P1 nonwork_game_context_publish_block_required

- row_count: `1`
- owner_mode: `RUNTIME_REPLAY_OR_REVIEW`
- label_counts: `{'REPROCESS': 1}`
- bucket_counts: `{'unsafe_promotion_from_hold': 1}`
- sample_post_ids: `11690855`

### P1 ocr_title_variant_cleanup_required

- row_count: `1`
- owner_mode: `RUNTIME_REPLAY_OR_REVIEW`
- label_counts: `{'REPROCESS': 1}`
- bucket_counts: `{'safe_loss_resolved_to_null': 1}`
- sample_post_ids: `11669926`

### P1 p0_wrong_work_title_flip_review_required

- row_count: `5`
- owner_mode: `SOURCE_NATIVE_OR_BLIND_REVIEW`
- label_counts: `{'INFO_MISSING': 5}`
- bucket_counts: `{'wrong_work_title_flip': 5}`
- sample_post_ids: `11660232, 11663554, 11682792, 11703674, 11714903`

### P2 policy_or_canonical_title_review_required

- row_count: `3`
- owner_mode: `POLICY_OR_NATIVE_REVIEW`
- label_counts: `{'HOLD': 3}`
- bucket_counts: `{'safe_loss_resolved_to_null': 3}`
- sample_post_ids: `11698871, 11698865, 11708453`

### P1 preserve_secondary_candidates

- row_count: `7`
- owner_mode: `POLICY_OR_NATIVE_REVIEW`
- label_counts: `{'HOLD': 1, 'REPROCESS': 6}`
- bucket_counts: `{'safe_loss_resolved_to_null': 5, 'unsafe_promotion_from_hold': 2}`
- sample_post_ids: `11668324, 11718105, 11661863, 11682749, 11694035, 11705231, 11710036`

### P0 repair_after_wrong_work

- row_count: `10`
- owner_mode: `CODE_OR_RUNTIME_REPAIR`
- label_counts: `{'REPROCESS': 10}`
- bucket_counts: `{'safe_loss_resolved_to_null': 4, 'wrong_work_title_flip': 6}`
- sample_post_ids: `11671514, 11716464, 11663514, 11674694, 11660241, 11698870, 11682749, 11703658, 11705231, 11710036`

### P0 repair_safe_loss_restore_supported_title

- row_count: `41`
- owner_mode: `CODE_OR_RUNTIME_REPAIR`
- label_counts: `{'REPROCESS': 41}`
- bucket_counts: `{'safe_loss_resolved_to_null': 41}`
- sample_post_ids: `11660273, 11663557, 11665124, 11668325, 11669913, 11673102, 11677926, 11690841, 11694019, 11697242, 11697256, 11702094`

### P0 repair_unsafe_promotion

- row_count: `4`
- owner_mode: `CODE_OR_RUNTIME_REPAIR`
- label_counts: `{'REPROCESS': 4}`
- bucket_counts: `{'unsafe_promotion_from_hold': 4}`
- sample_post_ids: `11657047, 11658621, 11690855, 11710044`

### P1 search_title_similarity_hard_hold_required

- row_count: `1`
- owner_mode: `RUNTIME_REPLAY_OR_REVIEW`
- label_counts: `{'REPROCESS': 1}`
- bucket_counts: `{'unsafe_promotion_from_hold': 1}`
- sample_post_ids: `11658621`

### P1 shared_promotion_gate_wiring_required

- row_count: `41`
- owner_mode: `RUNTIME_REPLAY_OR_REVIEW`
- label_counts: `{'REPROCESS': 41}`
- bucket_counts: `{'safe_loss_resolved_to_null': 41}`
- sample_post_ids: `11660273, 11663557, 11665124, 11668325, 11669913, 11673102, 11677926, 11690841, 11694019, 11697242, 11697256, 11702094`

### P1 source_native_or_blind_review_required

- row_count: `5`
- owner_mode: `SOURCE_NATIVE_OR_BLIND_REVIEW`
- label_counts: `{'INFO_MISSING': 5}`
- bucket_counts: `{'wrong_work_title_flip': 5}`
- sample_post_ids: `11660232, 11663554, 11682792, 11703674, 11714903`

### P2 title_surface_specificity_review_required

- row_count: `1`
- owner_mode: `POLICY_OR_NATIVE_REVIEW`
- label_counts: `{'HOLD': 1}`
- bucket_counts: `{'safe_loss_resolved_to_null': 1}`
- sample_post_ids: `11718057`

### P1 title_url_or_variant_trace_repair

- row_count: `1`
- owner_mode: `RUNTIME_REPLAY_OR_REVIEW`
- label_counts: `{'REPROCESS': 1}`
- bucket_counts: `{'wrong_work_title_flip': 1}`
- sample_post_ids: `11669907`
