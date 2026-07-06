# loop489_current_residual98_action_queue

## 요약

- source_review_id: `loop488_p0_full_source_native_review`
- gate: `REVIEW-LOCKED`
- source_rows: `136`
- residual_action_queue_rows: `98`
- label_counts: `{'HOLD': 34, 'INFO_MISSING': 1, 'REPROCESS': 63}`
- closed_post_ids_excluded: `[]`
- excluded_residual_action_queue_rows: `0`
- unreviewed_regression_rows_added: `1`
- action_group_count: `24`
- validation_issue_count: `0`
- approval: `false`
- semantic_quality: `REVIEW-LOCKED`

## 승인 경계

- 이 큐 분해는 residual action queue를 실행 가능하게 만든 산출물이며 approval이 아니다.
- search recovery가 `unrecovered_degraded=0`으로 닫히기 전까지 `promotion_blocked`는 `search-blind conditional`이다.
- `REPROCESS`는 코드/계약/runtime replay 후보이고, `HOLD`는 native image/web/source 또는 policy review 후보다.

## Action groups

### P2 alias_relation_review_required

- row_count: `3`
- owner_mode: `POLICY_OR_NATIVE_REVIEW`
- label_counts: `{'HOLD': 3}`
- bucket_counts: `{'safe_loss_resolved_to_null': 2, 'unsafe_promotion_from_hold': 1}`
- sample_post_ids: `11694067, 11665110, 11703631`

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
- bucket_counts: `{'safe_loss_resolved_to_null': 1, 'unsafe_promotion_from_hold': 1, 'wrong_work_title_flip': 2}`
- sample_post_ids: `11671514, 11710036, 11697249, 11690874`

### P1 canonical_title_cleanup_required

- row_count: `5`
- owner_mode: `RUNTIME_REPLAY_OR_REVIEW`
- label_counts: `{'REPROCESS': 5}`
- bucket_counts: `{'unsafe_promotion_from_hold': 1, 'wrong_work_title_flip': 4}`
- sample_post_ids: `11716464, 11674694, 11682767, 11708443, 11695637`

### P2 canonical_title_review_required

- row_count: `2`
- owner_mode: `POLICY_OR_NATIVE_REVIEW`
- label_counts: `{'HOLD': 2}`
- bucket_counts: `{'safe_loss_resolved_to_null': 1, 'wrong_work_title_flip': 1}`
- sample_post_ids: `11695599, 11660268`

### P2 character_bridge_review_required

- row_count: `1`
- owner_mode: `POLICY_OR_NATIVE_REVIEW`
- label_counts: `{'HOLD': 1}`
- bucket_counts: `{'unsafe_promotion_from_hold': 1}`
- sample_post_ids: `11671538`

### P1 comment_answer_bridge_review

- row_count: `1`
- owner_mode: `RUNTIME_REPLAY_OR_REVIEW`
- label_counts: `{'REPROCESS': 1}`
- bucket_counts: `{'wrong_work_title_flip': 1}`
- sample_post_ids: `11708478`

### P2 image_native_review_required

- row_count: `23`
- owner_mode: `POLICY_OR_NATIVE_REVIEW`
- label_counts: `{'HOLD': 23}`
- bucket_counts: `{'safe_loss_resolved_to_null': 16, 'unsafe_promotion_from_hold': 1, 'wrong_work_title_flip': 6}`
- sample_post_ids: `11660254, 11682791, 11685985, 11661856, 11666725, 11671512, 11677924, 11681152, 11681178, 11682775, 11685994, 11687661`

### P1 intent_guard_review

- row_count: `2`
- owner_mode: `RUNTIME_REPLAY_OR_REVIEW`
- label_counts: `{'REPROCESS': 2}`
- bucket_counts: `{'unsafe_promotion_from_hold': 2}`
- sample_post_ids: `11657046, 11657047`

### P2 multi_work_policy_review

- row_count: `2`
- owner_mode: `POLICY_OR_NATIVE_REVIEW`
- label_counts: `{'HOLD': 2}`
- bucket_counts: `{'safe_loss_resolved_to_null': 1, 'unsafe_promotion_from_hold': 1}`
- sample_post_ids: `11674712, 11703640`

### P1 native_web_review_required

- row_count: `34`
- owner_mode: `POLICY_OR_NATIVE_REVIEW`
- label_counts: `{'HOLD': 32, 'REPROCESS': 2}`
- bucket_counts: `{'safe_loss_resolved_to_null': 22, 'unsafe_promotion_from_hold': 7, 'wrong_work_title_flip': 5}`
- sample_post_ids: `11660254, 11682791, 11671538, 11685985, 11694067, 11697234, 11703645, 11661856, 11665110, 11666725, 11671512, 11677924`

### P1 official_url_recall_required

- row_count: `1`
- owner_mode: `RUNTIME_REPLAY_OR_REVIEW`
- label_counts: `{'REPROCESS': 1}`
- bucket_counts: `{'safe_loss_resolved_to_null': 1}`
- sample_post_ids: `11718120`

### P1 p1_new_resolution_promotion_review_required

- row_count: `1`
- owner_mode: `SOURCE_NATIVE_OR_BLIND_REVIEW`
- label_counts: `{'INFO_MISSING': 1}`
- bucket_counts: `{'new_resolution_promotion': 1}`
- sample_post_ids: `11682800`

### P2 policy_or_canonical_title_review_required

- row_count: `1`
- owner_mode: `POLICY_OR_NATIVE_REVIEW`
- label_counts: `{'HOLD': 1}`
- bucket_counts: `{'safe_loss_resolved_to_null': 1}`
- sample_post_ids: `11698871`

### P2 preserve_candidates

- row_count: `1`
- owner_mode: `POLICY_OR_NATIVE_REVIEW`
- label_counts: `{'HOLD': 1}`
- bucket_counts: `{'wrong_work_title_flip': 1}`
- sample_post_ids: `11661863`

### P2 preserve_secondary_candidates

- row_count: `2`
- owner_mode: `POLICY_OR_NATIVE_REVIEW`
- label_counts: `{'HOLD': 2}`
- bucket_counts: `{'safe_loss_resolved_to_null': 1, 'unsafe_promotion_from_hold': 1}`
- sample_post_ids: `11674712, 11703640`

### P0 repair_after_wrong_work

- row_count: `12`
- owner_mode: `CODE_OR_RUNTIME_REPAIR`
- label_counts: `{'REPROCESS': 12}`
- bucket_counts: `{'wrong_work_title_flip': 12}`
- sample_post_ids: `11671514, 11679547, 11698865, 11716464, 11663514, 11674694, 11682767, 11685987, 11697249, 11698859, 11708443, 11708478`

### P0 repair_safe_loss_restore_supported_title

- row_count: `46`
- owner_mode: `CODE_OR_RUNTIME_REPAIR`
- label_counts: `{'REPROCESS': 46}`
- bucket_counts: `{'safe_loss_resolved_to_null': 46}`
- sample_post_ids: `11660271, 11660273, 11663521, 11663535, 11663557, 11665124, 11668325, 11669913, 11669933, 11673096, 11673102, 11677915`

### P0 repair_unsafe_promotion

- row_count: `3`
- owner_mode: `CODE_OR_RUNTIME_REPAIR`
- label_counts: `{'REPROCESS': 3}`
- bucket_counts: `{'unsafe_promotion_from_hold': 3}`
- sample_post_ids: `11657046, 11657047, 11690874`

### P1 shared_promotion_gate_wiring_required

- row_count: `47`
- owner_mode: `RUNTIME_REPLAY_OR_REVIEW`
- label_counts: `{'REPROCESS': 47}`
- bucket_counts: `{'safe_loss_resolved_to_null': 47}`
- sample_post_ids: `11660271, 11660273, 11663521, 11663535, 11663557, 11665124, 11668325, 11669913, 11669933, 11673096, 11673102, 11677915`

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

### P1 stable_alias_collision_guard_required

- row_count: `1`
- owner_mode: `RUNTIME_REPLAY_OR_REVIEW`
- label_counts: `{'REPROCESS': 1}`
- bucket_counts: `{'wrong_work_title_flip': 1}`
- sample_post_ids: `11685987`

### P2 title_surface_specificity_review_required

- row_count: `2`
- owner_mode: `POLICY_OR_NATIVE_REVIEW`
- label_counts: `{'HOLD': 2}`
- bucket_counts: `{'safe_loss_resolved_to_null': 1, 'unsafe_promotion_from_hold': 1}`
- sample_post_ids: `11703645, 11718057`
