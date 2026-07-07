# loop553_ordinary_residual64_dispatch

Loop553은 Loop552에서 남은 ordinary residual을 단건이 아니라 배치 lane으로 재분해한 회차다. 새 runtime replay, bounded run, full375 대형 런은 실행하지 않았다.

## 요약

- source_accounting_id: `loop552_residual78_after_contract_reviews_accounting`
- source_queue_id: `loop546_current_full375_after_loop545_runtime_residual78_action_queue`
- ordinary_residual_rows: `64`
- contract_processed_rows_held: `14`
- lane_counts: `{'candidate_set_rebuild_review': 15, 'canonical_policy_cleanup_review': 1, 'native_web_image_evidence_review': 20, 'no_publish_multiwork_guard_review': 6, 'shared_gate_restore_contract_review': 17, 'source_native_or_blind_review': 5}`
- label_counts: `{'HOLD': 21, 'INFO_MISSING': 5, 'REPROCESS': 38}`
- bucket_counts: `{'safe_loss_resolved_to_null': 41, 'unsafe_promotion_from_hold': 8, 'wrong_work_title_flip': 15}`
- validation_issue_count: `0`
- publish_allowed_rows: `0`
- runtime_replay_allowed_rows: `0`
- approval: `false`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`

## 승인 경계

- 이 dispatch는 residual64 처리 순서를 정한 산출물이며 approval이 아니다.
- 모든 lane은 review/contract/full375 재확인 전까지 `publish_allowed=false`, `runtime_replay_allowed=false`다.
- Dashboard는 다음 runtime 진행 관측 도구일 뿐 semantic/full_scan approval 근거가 아니다.
- 완료 기준은 계속 `full375 collateral GO + full_scan 경로 정의`다.

## Lanes

### candidate_set_rebuild_review

- 의미: 현재 후보셋이 정답 후보를 빠뜨렸거나 wrong-work 후보를 보존했으므로 candidate ledger를 재구성한다.
- lane_gate: `BLOCKED_UNTIL_CANDIDATE_SET_REBUILT_AND_CONTRACT_TESTED`
- row_count: `15`
- label_counts: `{'HOLD': 1, 'REPROCESS': 14}`
- bucket_counts: `{'safe_loss_resolved_to_null': 6, 'unsafe_promotion_from_hold': 1, 'wrong_work_title_flip': 8}`
- sample_post_ids: `11682749, 11694035, 11698865, 11703658, 11705231, 11710036, 11710044, 11660241, 11663514, 11671512, 11671514, 11674694, 11694041, 11698870`

### canonical_policy_cleanup_review

- 의미: canonical title, URL, variant, alias relation 정책을 정리한다.
- lane_gate: `BLOCKED_UNTIL_CANONICAL_POLICY_CLEANUP`
- row_count: `1`
- label_counts: `{'REPROCESS': 1}`
- bucket_counts: `{'wrong_work_title_flip': 1}`
- sample_post_ids: `11669907`

### native_web_image_evidence_review

- 의미: native web, 이미지, OCR, 플랫폼 evidence를 직접 확인해야 한다.
- lane_gate: `BLOCKED_UNTIL_NATIVE_WEB_OR_IMAGE_EVIDENCE_REVIEW`
- row_count: `20`
- label_counts: `{'HOLD': 19, 'REPROCESS': 1}`
- bucket_counts: `{'safe_loss_resolved_to_null': 17, 'unsafe_promotion_from_hold': 2, 'wrong_work_title_flip': 1}`
- sample_post_ids: `11661856, 11661863, 11665110, 11666725, 11677924, 11681178, 11685994, 11687661, 11698871, 11706844, 11706867, 11710047, 11711632, 11714885`

### no_publish_multiwork_guard_review

- 의미: unsafe promotion, intent guard, multi-work guard를 먼저 닫고 publish hard-hold를 유지한다.
- lane_gate: `HARD_HOLD_UNTIL_NO_PUBLISH_GUARD_REVIEW`
- row_count: `6`
- label_counts: `{'HOLD': 1, 'REPROCESS': 5}`
- bucket_counts: `{'safe_loss_resolved_to_null': 1, 'unsafe_promotion_from_hold': 5}`
- sample_post_ids: `11708453, 11657047, 11658621, 11668324, 11690855, 11718105`

### shared_gate_restore_contract_review

- 의미: source-native supported title을 shared promotion gate contract로 복원 후보화한다.
- lane_gate: `BLOCKED_UNTIL_SHARED_GATE_CONTRACT_APPLICATION_AND_FULL375_RECHECK`
- row_count: `17`
- label_counts: `{'REPROCESS': 17}`
- bucket_counts: `{'safe_loss_resolved_to_null': 17}`
- sample_post_ids: `11660273, 11663511, 11663535, 11668300, 11673077, 11673102, 11677915, 11681172, 11689292, 11694019, 11694063, 11694068, 11702094, 11705230`

### source_native_or_blind_review

- 의미: prior-compatible verdict가 없거나 INFO_MISSING이라 source-native/blind 판정을 먼저 닫는다.
- lane_gate: `BLOCKED_UNTIL_SOURCE_NATIVE_OR_BLIND_VERDICT`
- row_count: `5`
- label_counts: `{'INFO_MISSING': 5}`
- bucket_counts: `{'wrong_work_title_flip': 5}`
- sample_post_ids: `11660232, 11663554, 11682792, 11703674, 11714903`
