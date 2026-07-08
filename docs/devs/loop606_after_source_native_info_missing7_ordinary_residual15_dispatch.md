# loop606_after_source_native_info_missing7_ordinary_residual15_dispatch

이 회차는 남은 ordinary residual을 단건이 아니라 배치 lane으로 재분해한 산출물이다. 새 runtime replay, bounded run, full375 대형 런은 실행하지 않았다.

## 요약

- source_accounting_id: `loop606_after_source_native_info_missing7_residual28_accounting`
- source_queue_id: `loop602_after_unreviewed13_source_native_residual_action_queue`
- ordinary_residual_rows: `15`
- contract_processed_rows_held: `12`
- lane_counts: `{'canonical_policy_cleanup_review': 2, 'native_web_image_evidence_review': 11, 'no_publish_multiwork_guard_review': 2}`
- label_counts: `{'HOLD': 14, 'REJECT': 1}`
- bucket_counts: `{'safe_loss_resolved_to_null': 10, 'unsafe_promotion_from_hold': 4, 'wrong_work_title_flip': 1}`
- validation_issue_count: `0`
- publish_allowed_rows: `0`
- runtime_replay_allowed_rows: `0`
- approval: `false`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`

## 승인 경계

- 이 dispatch는 residual 처리 순서를 정한 산출물이며 approval이 아니다.
- 모든 lane은 review/contract/full375 재확인 전까지 `publish_allowed=false`, `runtime_replay_allowed=false`다.
- Dashboard는 다음 runtime 진행 관측 도구일 뿐 semantic/full_scan approval 근거가 아니다.
- 완료 기준은 계속 `full375 collateral GO + full_scan 경로 정의`다.

## Lanes

### canonical_policy_cleanup_review

- 의미: canonical title, URL, variant, alias relation 정책을 정리한다.
- lane_gate: `BLOCKED_UNTIL_CANONICAL_POLICY_CLEANUP`
- row_count: `2`
- label_counts: `{'HOLD': 2}`
- bucket_counts: `{'unsafe_promotion_from_hold': 2}`
- sample_post_ids: `11677957, 11714913`

### native_web_image_evidence_review

- 의미: native web, 이미지, OCR, 플랫폼 evidence를 직접 확인해야 한다.
- lane_gate: `BLOCKED_UNTIL_NATIVE_WEB_OR_IMAGE_EVIDENCE_REVIEW`
- row_count: `11`
- label_counts: `{'HOLD': 11}`
- bucket_counts: `{'safe_loss_resolved_to_null': 8, 'unsafe_promotion_from_hold': 2, 'wrong_work_title_flip': 1}`
- sample_post_ids: `11661856, 11661863, 11671512, 11681178, 11685994, 11687661, 11716480, 11718057, 11687635, 11694067, 11682791`

### no_publish_multiwork_guard_review

- 의미: unsafe promotion, intent guard, multi-work guard를 먼저 닫고 publish hard-hold를 유지한다.
- lane_gate: `HARD_HOLD_UNTIL_NO_PUBLISH_GUARD_REVIEW`
- row_count: `2`
- label_counts: `{'HOLD': 1, 'REJECT': 1}`
- bucket_counts: `{'safe_loss_resolved_to_null': 2}`
- sample_post_ids: `11698870, 11711632`
