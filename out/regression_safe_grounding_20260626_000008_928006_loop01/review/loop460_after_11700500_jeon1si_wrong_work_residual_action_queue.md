# loop460_after_11700500_jeon1si_wrong_work_residual_action_queue

## 요약

- source_review_id: `loop457_11716448_asaenggal_wrong_work_runtime`
- gate: `REVIEW-LOCKED`
- source_rows: `96`
- residual_action_queue_rows: `95`
- label_counts: `{'HOLD': 28, 'REPROCESS': 67}`
- closed_post_ids_excluded: `[11698890, 11700500, 11702090, 11705252, 11716448]`
- excluded_residual_action_queue_rows: `1`
- action_group_count: `22`
- validation_issue_count: `0`
- approval: `false`
- semantic_quality: `REVIEW-LOCKED`

## 승인 경계

- 이 큐 분해는 residual action queue를 실행 가능하게 만든 산출물이며 approval이 아니다.
- search recovery가 `unrecovered_degraded=0`으로 닫히기 전까지 `promotion_blocked`는 `search-blind conditional`이다.
- `REPROCESS`는 코드/계약/runtime replay 후보이고, `HOLD`는 native image/web/source 또는 policy review 후보다.

## Action groups

### P2 canonical_title_variant_policy_required

- row_count: `1`
- owner_mode: `POLICY_OR_NATIVE_REVIEW`
- label_counts: `{'HOLD': 1}`
- bucket_counts: `{'safe_loss_resolved_to_null': 1}`
- sample_post_ids: `11665124`

### P1 comment_title_or_image_review_required

- row_count: `1`
- owner_mode: `RUNTIME_REPLAY_OR_REVIEW`
- label_counts: `{'REPROCESS': 1}`
- bucket_counts: `{'safe_loss_resolved_to_null': 1}`
- sample_post_ids: `11708478`

### P1 comparison_context_policy_required

- row_count: `1`
- owner_mode: `RUNTIME_REPLAY_OR_REVIEW`
- label_counts: `{'REPROCESS': 1}`
- bucket_counts: `{'safe_loss_resolved_to_null': 1}`
- sample_post_ids: `11716475`

### P2 multi_candidate_recommendation_review_required

- row_count: `1`
- owner_mode: `POLICY_OR_NATIVE_REVIEW`
- label_counts: `{'HOLD': 1}`
- bucket_counts: `{'safe_loss_resolved_to_null': 1}`
- sample_post_ids: `11697256`

### P1 multi_work_or_benchmark_context_policy_required

- row_count: `1`
- owner_mode: `RUNTIME_REPLAY_OR_REVIEW`
- label_counts: `{'REPROCESS': 1}`
- bucket_counts: `{'safe_loss_resolved_to_null': 1}`
- sample_post_ids: `11708432`

### P2 native_image_or_canonical_review_required

- row_count: `2`
- owner_mode: `POLICY_OR_NATIVE_REVIEW`
- label_counts: `{'HOLD': 2}`
- bucket_counts: `{'safe_loss_resolved_to_null': 2}`
- sample_post_ids: `11706844, 11716480`

### P2 native_image_or_character_bridge_review_required

- row_count: `2`
- owner_mode: `POLICY_OR_NATIVE_REVIEW`
- label_counts: `{'HOLD': 2}`
- bucket_counts: `{'safe_loss_resolved_to_null': 2}`
- sample_post_ids: `11663554, 11692436`

### P2 native_image_or_media_boundary_review_required

- row_count: `1`
- owner_mode: `POLICY_OR_NATIVE_REVIEW`
- label_counts: `{'HOLD': 1}`
- bucket_counts: `{'safe_loss_resolved_to_null': 1}`
- sample_post_ids: `11668325`

### P1 native_image_or_ocr_title_review_required

- row_count: `1`
- owner_mode: `RUNTIME_REPLAY_OR_REVIEW`
- label_counts: `{'REPROCESS': 1}`
- bucket_counts: `{'safe_loss_resolved_to_null': 1}`
- sample_post_ids: `11718099`

### P2 native_image_or_scope_review_required

- row_count: `1`
- owner_mode: `POLICY_OR_NATIVE_REVIEW`
- label_counts: `{'HOLD': 1}`
- bucket_counts: `{'safe_loss_resolved_to_null': 1}`
- sample_post_ids: `11711632`

### P2 native_image_or_source_review_required

- row_count: `14`
- owner_mode: `POLICY_OR_NATIVE_REVIEW`
- label_counts: `{'HOLD': 14}`
- bucket_counts: `{'safe_loss_resolved_to_null': 14}`
- sample_post_ids: `11658615, 11660254, 11661856, 11661863, 11665099, 11666725, 11669908, 11669924, 11671512, 11673080, 11677924, 11695599`

### P1 native_image_or_url_review_required

- row_count: `1`
- owner_mode: `RUNTIME_REPLAY_OR_REVIEW`
- label_counts: `{'REPROCESS': 1}`
- bucket_counts: `{'safe_loss_resolved_to_null': 1}`
- sample_post_ids: `11702086`

### P2 native_web_or_alternative_title_review_required

- row_count: `1`
- owner_mode: `POLICY_OR_NATIVE_REVIEW`
- label_counts: `{'HOLD': 1}`
- bucket_counts: `{'safe_loss_resolved_to_null': 1}`
- sample_post_ids: `11702094`

### P2 native_web_or_scope_review_required

- row_count: `1`
- owner_mode: `POLICY_OR_NATIVE_REVIEW`
- label_counts: `{'HOLD': 1}`
- bucket_counts: `{'safe_loss_resolved_to_null': 1}`
- sample_post_ids: `11698870`

### P2 native_web_or_source_review_required

- row_count: `3`
- owner_mode: `POLICY_OR_NATIVE_REVIEW`
- label_counts: `{'HOLD': 3}`
- bucket_counts: `{'safe_loss_resolved_to_null': 3}`
- sample_post_ids: `11660262, 11665110, 11685994`

### P1 native_web_or_url_review_required

- row_count: `3`
- owner_mode: `RUNTIME_REPLAY_OR_REVIEW`
- label_counts: `{'REPROCESS': 3}`
- bucket_counts: `{'safe_loss_resolved_to_null': 3}`
- sample_post_ids: `11697267, 11698895, 11700483`

### P2 preserve_hold_boundary

- row_count: `1`
- owner_mode: `POLICY_OR_NATIVE_REVIEW`
- label_counts: `{'HOLD': 1}`
- bucket_counts: `{'safe_loss_resolved_to_null': 1}`
- sample_post_ids: `11663521`

### P0 repair_after_wrong_work

- row_count: `1`
- owner_mode: `CODE_OR_RUNTIME_REPAIR`
- label_counts: `{'REPROCESS': 1}`
- bucket_counts: `{'wrong_work_title_flip': 1}`
- sample_post_ids: `11666713`

### P0 repair_safe_loss

- row_count: `66`
- owner_mode: `CODE_OR_RUNTIME_REPAIR`
- label_counts: `{'REPROCESS': 66}`
- bucket_counts: `{'safe_loss_resolved_to_null': 66}`
- sample_post_ids: `11660237, 11660257, 11660258, 11660259, 11660265, 11661876, 11666731, 11669943, 11671500, 11671517, 11676310, 11684372`

### P1 title_field_split_contract_required

- row_count: `1`
- owner_mode: `RUNTIME_REPLAY_OR_REVIEW`
- label_counts: `{'REPROCESS': 1}`
- bucket_counts: `{'safe_loss_resolved_to_null': 1}`
- sample_post_ids: `11705231`

### P1 title_variant_canonicalization_required

- row_count: `5`
- owner_mode: `RUNTIME_REPLAY_OR_REVIEW`
- label_counts: `{'REPROCESS': 5}`
- bucket_counts: `{'safe_loss_resolved_to_null': 5}`
- sample_post_ids: `11660277, 11663544, 11669929, 11705269, 11714887`

### P1 url_canonicalization_review_required

- row_count: `4`
- owner_mode: `RUNTIME_REPLAY_OR_REVIEW`
- label_counts: `{'REPROCESS': 4}`
- bucket_counts: `{'safe_loss_resolved_to_null': 4}`
- sample_post_ids: `11702085, 11710020, 11710021, 11710052`
