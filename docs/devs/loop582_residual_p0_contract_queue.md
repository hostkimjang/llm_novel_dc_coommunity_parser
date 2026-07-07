# loop582_residual_p0_contract_queue

Loop581 P0 residual 19건을 새 runtime 없이 계약/검토 lane으로 재분해한 산출물이다. 이 문서는 residual 실행 허가나 full_scan approval이 아니다.

## 요약

- source_batch_id: `loop581_candidate_set_full375_prior_compatible_residual_p0_action_batch`
- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- contract_queue_rows: `19`
- runtime_replay_allowed_rows: `0`
- shared_gate_restore_clean_lane_rows: `6`
- shared_gate_restore_ready_with_official_url_rows: `1`
- shared_gate_restore_official_url_enrichment_rows: `5`
- shared_gate_restore_precondition_review_rows: `2`
- candidate_set_rebuild_required_rows: `4`
- source_native_or_blind_info_missing_rows: `7`
- validation_issue_count: `0`
- contract_bucket_counts: `{'candidate_set_rebuild_required_before_publish': 4, 'shared_gate_restore_contract_ready_with_official_url': 1, 'shared_gate_restore_requires_native_web_review': 1, 'shared_gate_restore_requires_no_publish_guard': 1, 'shared_gate_restore_requires_official_url_enrichment': 5, 'source_native_or_blind_info_missing_review': 7}`

## 테스트런 실행 계약

- policy: `TEST_RUNS_USE_PARALLEL_16_AND_WEB_DASHBOARD`
- requested_parallel: `16`
- expected_effective_parallel: `16`
- forbidden_flags: `['--no-dashboard']`
- dashboard_policy: `WEB_DASHBOARD_REQUIRED_FOR_TEST_RUNS`
- dashboard_url: `http://127.0.0.1:8080`
- dashboard_gate: `GO_PROGRESS_VIEW_NOT_APPROVAL`
- Dashboard는 진행 확인 도구이며 semantic/full_scan approval 근거가 아니다.

## 처리 bucket

### candidate_set_rebuild_required_before_publish

- row_count: `4`
- post_ids: `11682749, 11703658, 11705231, 11710036`
- dispatch_lane_counts: `{'candidate_set_rebuild_review': 4}`
- official_support_ref_rows: `1`
- runtime_replay_allowed_rows: `0`
- next_action: 현재 후보셋이 source-supported title을 담지 못하므로 후보셋 재구성 전 publish와 runtime replay를 금지한다.

### shared_gate_restore_contract_ready_with_official_url

- row_count: `1`
- post_ids: `11718114`
- dispatch_lane_counts: `{'shared_gate_restore_contract_review': 1}`
- official_support_ref_rows: `1`
- runtime_replay_allowed_rows: `0`
- next_action: shared promotion gate contract plan에 통과시킨 뒤 projection과 full375 collateral로 재검증한다.

### shared_gate_restore_requires_native_web_review

- row_count: `1`
- post_ids: `11698859`
- dispatch_lane_counts: `{'native_web_image_evidence_review': 1}`
- official_support_ref_rows: `0`
- runtime_replay_allowed_rows: `0`
- next_action: native web/image 근거를 먼저 확인하고, 이미지/플랫폼 URL 선호가 정리되기 전 publish를 금지한다.

### shared_gate_restore_requires_no_publish_guard

- row_count: `1`
- post_ids: `11700483`
- dispatch_lane_counts: `{'no_publish_guard_review': 1}`
- official_support_ref_rows: `0`
- runtime_replay_allowed_rows: `0`
- next_action: merchandise/emoticon 또는 no-publish guard를 먼저 판정하고, guard가 풀리기 전 publish를 금지한다.

### shared_gate_restore_requires_official_url_enrichment

- row_count: `5`
- post_ids: `11665124, 11710049, 11682775, 11700500, 11698870`
- dispatch_lane_counts: `{'shared_gate_restore_contract_review': 5}`
- official_support_ref_rows: `0`
- runtime_replay_allowed_rows: `0`
- next_action: 공식 detail URL을 후보 ledger에 보존한 뒤에만 shared gate restore contract 후보로 승격한다.

### source_native_or_blind_info_missing_review

- row_count: `7`
- post_ids: `11660232, 11663554, 11682792, 11703674, 11714903, 11660273, 11671514`
- dispatch_lane_counts: `{'source_native_or_blind_review': 7}`
- official_support_ref_rows: `0`
- runtime_replay_allowed_rows: `0`
- next_action: source-native 또는 blind judge로 정답성을 확정하기 전 hard-hold 완화와 safe-loss 해소 선언을 금지한다.

## 승인 경계

- 공식 detail URL이 없는 shared-gate restore 행은 publish contract 후보가 아니라 URL 보존/보강 대상이다.
- native web/image 또는 no-publish guard가 붙은 행은 해당 사전 검토가 끝나기 전 shared-gate restore로 승격하지 않는다.
- INFO_MISSING 행은 source-native/blind judge 판정 전 hard-hold 완화 대상이 아니다.
- 완료 기준은 계속 `full375 collateral GO + full_scan 경로 정의`다.
