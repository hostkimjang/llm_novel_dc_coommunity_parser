# loop546_current_full375_after_loop545_runtime_residual78_action_queue

## 요약

- source_residual_rows: `97`
- runtime_replay_rows: `49`
- runtime_verified_exact_safe_resolved_rows: `19`
- runtime_expected_title_failure_rows: `30`
- projection_followup_non_runtime_remaining_rows: `2`
- outside_shared_gate_projection_remaining_rows: `46`
- residual_action_queue_rows: `78`
- label_counts: `{'REPROCESS': 52, 'HOLD': 21, 'INFO_MISSING': 5}`
- bucket_counts: `{'wrong_work_title_flip': 15, 'unsafe_promotion_from_hold': 8, 'safe_loss_resolved_to_null': 55}`
- transition_counts: `{'outside_shared_gate_projection_remaining': 46, 'runtime_expected_title_failure_remaining': 30, 'projection_followup_non_runtime_remaining': 2}`
- runtime_failure_status_counts: `{'FAIL_SAFE_RESOLVED_TITLE_MISMATCH': 7, 'FAIL_RUNTIME_PROMOTION_BLOCKED': 23}`
- action_counts: `{'alias_collision_guard_required': 1, 'alias_relation_review_required': 2, 'candidate_set_rebuild_required': 10, 'canonical_alias_competition_guard_required': 1, 'canonical_title_cleanup_required': 4, 'character_bridge_review_required': 2, 'image_listing_multi_work_guard_required': 2, 'image_multi_panel_review_required': 1, 'image_native_review_required': 14, 'image_platform_url_preference': 1, 'intent_guard_review': 3, 'multi_work_guard_required': 4, 'native_web_review_required': 24, 'nonwork_game_context_publish_block_required': 1, 'p0_wrong_work_title_flip_review_required': 5, 'policy_or_canonical_title_review_required': 3, 'preserve_secondary_candidates': 7, 'repair_after_wrong_work': 10, 'repair_safe_loss_restore_supported_title': 32, 'repair_unsafe_promotion': 4, 'search_title_similarity_hard_hold_required': 1, 'shared_promotion_gate_wiring_required': 32, 'source_native_or_blind_review_required': 5, 'title_surface_specificity_review_required': 1, 'title_url_or_variant_trace_repair': 1}`
- validation_issue_count: `0`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- approval: `false`

## 승인 경계

- runtime_verified_exact_safe_resolved는 해당 19행의 runtime 재현 통과일 뿐 full375 collateral GO가 아니다.
- residual_action_queue_rows가 78로 감소했지만 completion gate는 여전히 full375 collateral GO + full_scan 경로 정의다.
- 동일 packet 재실행 전 code/contract repair 또는 source-native/blind review를 먼저 수행한다.

## Transition groups

### outside_shared_gate_projection_remaining

- row_count: `46`
- sample_post_ids: `11671514, 11682791, 11671538, 11694067, 11661856, 11665110, 11666725, 11681178, 11685994, 11687661, 11698871, 11706844, 11710047, 11711632, 11714885, 11716480, 11716505, 11716464, 11718057, 11663514`

### projection_followup_non_runtime_remaining

- row_count: `2`
- sample_post_ids: `11677924, 11694063`

### runtime_expected_title_failure_remaining

- row_count: `30`
- sample_post_ids: `11660273, 11663535, 11665124, 11668325, 11673102, 11677915, 11681172, 11690841, 11694019, 11697242, 11697256, 11702094, 11710021, 11710049, 11714887, 11718099, 11718110, 11718114, 11673077, 11694068`

## Runtime verified excluded

- row_count: `19`
- post_ids: `11663557, 11669913, 11677926, 11708447, 11666741, 11665121, 11666713, 11669921, 11669926, 11673080, 11681159, 11682775, 11692444, 11694065, 11700483, 11700500, 11706831, 11708470, 11708478`

## 다음 조건

- 30건 runtime expected-title failure는 `docs/devs/loop545_current_full375_residual97_runtime_failure_action_queue.json` 레인으로 처리한다.
- 22건 promotion-block repair는 `docs/devs/loop545_current_full375_residual97_shared_gate_runtime_block_repair_queue.json` 계약 수리 큐로 처리한다.
- 수리 뒤 동일 49건을 그대로 반복하지 말고, 줄어든 배치와 full375 collateral 재확인을 연결한다.
