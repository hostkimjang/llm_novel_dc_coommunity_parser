# loop593_residual46_remaining18_dispatch

이 회차는 남은 ordinary residual을 단건이 아니라 배치 lane으로 재분해한 산출물이다. 새 runtime replay, bounded run, full375 대형 런은 실행하지 않았다.

## 요약

- source_accounting_id: `loop593_residual46_canonical_cleanup_accounting`
- source_queue_id: `loop581_candidate_set_full375_prior_compatible_residual_action_queue`
- ordinary_residual_rows: `18`
- contract_processed_rows_held: `24`
- lane_counts: `{'native_web_image_evidence_review': 18}`
- label_counts: `{'HOLD': 18}`
- bucket_counts: `{'safe_loss_resolved_to_null': 15, 'unsafe_promotion_from_hold': 2, 'wrong_work_title_flip': 1}`
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
- row_count: `18`
- label_counts: `{'HOLD': 18}`
- bucket_counts: `{'safe_loss_resolved_to_null': 15, 'unsafe_promotion_from_hold': 2, 'wrong_work_title_flip': 1}`
- sample_post_ids: `11661856, 11665110, 11666725, 11681178, 11685994, 11687661, 11698871, 11706844, 11706867, 11710047, 11711632, 11714885, 11716480, 11716505`
