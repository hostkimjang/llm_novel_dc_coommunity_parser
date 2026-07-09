# loop630_true_triage64_after_prior_compatible_action_queue

## 요약

- source_review_id: `loop630_true_triage64_source_native_combined_review`
- gate: `REVIEW-LOCKED`
- source_rows: `64`
- residual_action_queue_rows: `59`
- label_counts: `{'HOLD': 6, 'INFO_MISSING': 35, 'REPROCESS': 18}`
- closed_post_ids_excluded: `[]`
- excluded_residual_action_queue_rows: `0`
- source_excluded_residual_action_queue_rows: `0`
- unreviewed_excluded_regression_rows: `0`
- unreviewed_regression_rows_added: `0`
- action_group_count: `12`
- validation_issue_count: `0`
- approval: `false`
- semantic_quality: `REVIEW-LOCKED`

## 승인 경계

- 이 큐 분해는 residual action queue를 실행 가능하게 만든 산출물이며 approval이 아니다.
- search recovery가 `unrecovered_degraded=0`으로 닫히기 전까지 `promotion_blocked`는 `search-blind conditional`이다.
- `REPROCESS`는 코드/계약/runtime replay 후보이고, `HOLD`는 native image/web/source 또는 policy review 후보다.

## 실행 그룹

### P1 canonical_title_cleanup_required

- row_count: `2`
- owner_mode: `RUNTIME_REPLAY_OR_REVIEW`
- label_counts: `{'REPROCESS': 2}`
- bucket_counts: `{'wrong_work_title_flip': 2}`
- sample_post_ids: `11716464, 11669907`

### P2 image_native_review_required

- row_count: `6`
- owner_mode: `POLICY_OR_NATIVE_REVIEW`
- label_counts: `{'HOLD': 6}`
- bucket_counts: `{'safe_loss_resolved_to_null': 5, 'wrong_work_title_flip': 1}`
- sample_post_ids: `11682791, 11666725, 11681152, 11682775, 11706844, 11716480`

### P1 native_web_review_required

- row_count: `7`
- owner_mode: `POLICY_OR_NATIVE_REVIEW`
- label_counts: `{'HOLD': 6, 'REPROCESS': 1}`
- bucket_counts: `{'safe_loss_resolved_to_null': 5, 'wrong_work_title_flip': 2}`
- sample_post_ids: `11682791, 11666725, 11681152, 11682775, 11706844, 11716480, 11663514`

### P0 p0_safe_loss_resolved_to_null_review_required

- row_count: `11`
- owner_mode: `SOURCE_NATIVE_OR_BLIND_REVIEW`
- label_counts: `{'INFO_MISSING': 11}`
- bucket_counts: `{'safe_loss_resolved_to_null': 11}`
- sample_post_ids: `11669926, 11682767, 11695599, 11708432, 11708443, 11663511, 11660268, 11660241, 11669924, 11676321, 11682761`

### P0 p0_unsafe_promotion_from_hold_review_required

- row_count: `9`
- owner_mode: `SOURCE_NATIVE_OR_BLIND_REVIEW`
- label_counts: `{'INFO_MISSING': 9}`
- bucket_counts: `{'unsafe_promotion_from_hold': 9}`
- sample_post_ids: `11705257, 11710045, 11660238, 11702060, 11657038, 11657044, 11681180, 11682768, 11685995`

### P0 p0_wrong_work_title_flip_review_required

- row_count: `15`
- owner_mode: `SOURCE_NATIVE_OR_BLIND_REVIEW`
- label_counts: `{'INFO_MISSING': 15}`
- bucket_counts: `{'wrong_work_title_flip': 15}`
- sample_post_ids: `11663554, 11714903, 11665110, 11702094, 11705269, 11660257, 11666713, 11669933, 11673102, 11674731, 11676309, 11692426`

### P0 repair_after_wrong_work

- row_count: `4`
- owner_mode: `CODE_OR_RUNTIME_REPAIR`
- label_counts: `{'REPROCESS': 4}`
- bucket_counts: `{'wrong_work_title_flip': 4}`
- sample_post_ids: `11679547, 11698865, 11716464, 11663514`

### P0 repair_safe_loss_restore_supported_title

- row_count: `13`
- owner_mode: `CODE_OR_RUNTIME_REPAIR`
- label_counts: `{'REPROCESS': 13}`
- bucket_counts: `{'safe_loss_resolved_to_null': 13}`
- sample_post_ids: `11660271, 11660273, 11663557, 11668325, 11677926, 11698910, 11706871, 11710049, 11714887, 11666741, 11679537, 11665121`

### P1 shared_promotion_gate_wiring_required

- row_count: `13`
- owner_mode: `RUNTIME_REPLAY_OR_REVIEW`
- label_counts: `{'REPROCESS': 13}`
- bucket_counts: `{'safe_loss_resolved_to_null': 13}`
- sample_post_ids: `11660271, 11660273, 11663557, 11668325, 11677926, 11698910, 11706871, 11710049, 11714887, 11666741, 11679537, 11665121`

### P1 source_main_work_title_needed

- row_count: `1`
- owner_mode: `RUNTIME_REPLAY_OR_REVIEW`
- label_counts: `{'REPROCESS': 1}`
- bucket_counts: `{'wrong_work_title_flip': 1}`
- sample_post_ids: `11698865`

### P1 source_native_or_blind_review_required

- row_count: `35`
- owner_mode: `SOURCE_NATIVE_OR_BLIND_REVIEW`
- label_counts: `{'INFO_MISSING': 35}`
- bucket_counts: `{'safe_loss_resolved_to_null': 11, 'unsafe_promotion_from_hold': 9, 'wrong_work_title_flip': 15}`
- sample_post_ids: `11663554, 11714903, 11705257, 11710045, 11669926, 11682767, 11695599, 11708432, 11708443, 11660238, 11663511, 11665110`

### P1 title_url_or_variant_trace_repair

- row_count: `1`
- owner_mode: `RUNTIME_REPLAY_OR_REVIEW`
- label_counts: `{'REPROCESS': 1}`
- bucket_counts: `{'wrong_work_title_flip': 1}`
- sample_post_ids: `11669907`
