# loop632_after_residual41_dispatch

이 회차는 남은 ordinary residual을 단건이 아니라 배치 lane으로 재분해한 산출물이다. 새 runtime replay, bounded run, full375 대형 런은 실행하지 않았다.

## 요약

- source_accounting_id: `loop632_after_shared_gate13_plus_ordinary_residual5_accounting`
- source_queue_id: `loop630_true_triage64_after_prior_compatible_action_queue`
- ordinary_residual_rows: `41`
- contract_processed_rows_held: `18`
- lane_counts: `{'native_web_image_evidence_review': 6, 'source_native_or_blind_review': 35}`
- label_counts: `{'HOLD': 6, 'INFO_MISSING': 35}`
- bucket_counts: `{'safe_loss_resolved_to_null': 16, 'unsafe_promotion_from_hold': 9, 'wrong_work_title_flip': 16}`
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

### native_web_image_evidence_review

- 의미: native web, 이미지, OCR, 플랫폼 evidence를 직접 확인해야 한다.
- lane_gate: `BLOCKED_UNTIL_NATIVE_WEB_OR_IMAGE_EVIDENCE_REVIEW`
- row_count: `6`
- label_counts: `{'HOLD': 6}`
- bucket_counts: `{'safe_loss_resolved_to_null': 5, 'wrong_work_title_flip': 1}`
- sample_post_ids: `11666725, 11681152, 11682775, 11706844, 11716480, 11682791`

### source_native_or_blind_review

- 의미: prior-compatible verdict가 없거나 INFO_MISSING이라 source-native/blind 판정을 먼저 닫는다.
- lane_gate: `BLOCKED_UNTIL_SOURCE_NATIVE_OR_BLIND_VERDICT`
- row_count: `35`
- label_counts: `{'INFO_MISSING': 35}`
- bucket_counts: `{'safe_loss_resolved_to_null': 11, 'unsafe_promotion_from_hold': 9, 'wrong_work_title_flip': 15}`
- sample_post_ids: `11660241, 11660268, 11663511, 11669924, 11669926, 11676321, 11682761, 11682767, 11695599, 11708432, 11708443, 11657038, 11657044, 11660238`
