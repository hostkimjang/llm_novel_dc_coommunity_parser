# loop635_after_no_publish_guard4_ordinary_residual20_dispatch

이 회차는 남은 ordinary residual을 단건이 아니라 배치 lane으로 재분해한 산출물이다. 새 runtime replay, bounded run, full375 대형 런은 실행하지 않았다.

## 요약

- source_accounting_id: `loop635_after_no_publish_guard4_residual24_accounting`
- source_queue_id: `loop634_after_shared_gate6_ordinary_residual24_dispatch`
- ordinary_residual_rows: `20`
- contract_processed_rows_held: `4`
- lane_counts: `{'candidate_set_rebuild_review': 6, 'canonical_policy_cleanup_review': 2, 'native_web_image_evidence_review': 12}`
- label_counts: `{'HOLD': 12, 'REPROCESS': 8}`
- bucket_counts: `{'safe_loss_resolved_to_null': 9, 'unsafe_promotion_from_hold': 1, 'wrong_work_title_flip': 10}`
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
- 완료 기준은 계속 `adjusted full375 collateral GO + full_scan 경로 정의`다.

## Lanes

### candidate_set_rebuild_review

- 의미: 현재 후보셋이 정답 후보를 빠뜨렸거나 wrong-work 후보를 보존했으므로 candidate ledger를 재구성한다.
- lane_gate: `BLOCKED_UNTIL_CANDIDATE_SET_REBUILT_AND_CONTRACT_TESTED`
- row_count: `6`
- label_counts: `{'REPROCESS': 6}`
- bucket_counts: `{'wrong_work_title_flip': 6}`
- sample_post_ids: `11660257, 11673102, 11676309, 11694065, 11698877, 11703631`

### canonical_policy_cleanup_review

- 의미: canonical title, URL, variant, alias relation 정책을 정리한다.
- lane_gate: `BLOCKED_UNTIL_CANONICAL_POLICY_CLEANUP`
- row_count: `2`
- label_counts: `{'REPROCESS': 2}`
- bucket_counts: `{'unsafe_promotion_from_hold': 1, 'wrong_work_title_flip': 1}`
- sample_post_ids: `11682768, 11674731`

### native_web_image_evidence_review

- 의미: native web, 이미지, OCR, 플랫폼 evidence를 직접 확인해야 한다.
- lane_gate: `BLOCKED_UNTIL_NATIVE_WEB_OR_IMAGE_EVIDENCE_REVIEW`
- row_count: `12`
- label_counts: `{'HOLD': 12}`
- bucket_counts: `{'safe_loss_resolved_to_null': 9, 'wrong_work_title_flip': 3}`
- sample_post_ids: `11666725, 11669924, 11669926, 11681152, 11682761, 11682775, 11695599, 11706844, 11716480, 11666713, 11682791, 11705269`
