# loop638_after_candidate_set6_official_support_ordinary_residual0_dispatch

이 회차는 남은 ordinary residual을 단건이 아니라 배치 lane으로 재분해한 산출물이다. 새 runtime replay, bounded run, full375 대형 런은 실행하지 않았다.

## 요약

- source_accounting_id: `loop638_after_candidate_set6_official_support_residual6_accounting`
- source_queue_id: `loop637_after_native12_hold_plus_canonical1_ordinary_residual6_dispatch`
- ordinary_residual_rows: `0`
- contract_processed_rows_held: `6`
- lane_counts: `{}`
- label_counts: `{}`
- bucket_counts: `{}`
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
