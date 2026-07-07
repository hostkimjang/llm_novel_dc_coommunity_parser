# loop591_residual46_candidate_set_accounting

`loop581_candidate_set_full375_prior_compatible_residual_action_queue`에 `loop591_residual46_combined_contract_plan` contract 결과를 결합한 회계 산출물이다. 이 산출물은 새 runtime replay나 full375 GO가 아니며, contract 처리 상태와 아직 남은 ordinary residual을 분리한다.

## 요약

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- source_residual_rows: `46`
- contract_plan_overlap_rows: `19`
- contract_processed_rows: `19`
- source_native_processed_rows: `4`
- processed_or_excluded_rows: `23`
- ordinary_residual_unprocessed_rows: `23`
- validation_issue_count: `0`
- release_candidate_not_approval_rows: `8`
- no_publish_or_hold_contract_rows: `11`
- official_support_missing_restore_followup_rows: `0`
- native_web_disambiguation_hold_rows: `1`
- non_webnovel_ebook_policy_hold_rows: `1`
- candidate_set_rebuild_hold_rows: `9`
- no_publish_intent_guard_rows: `0`
- source_native_exclusion_candidate_rows: `4`
- publish_allowed_rows: `0`
- runtime_replay_allowed_rows: `0`
- full375 collateral: `NO-GO`

## Contract 회계 상태

- `contract_processed_candidate_set_rebuild_hold_no_publish`: `9`
- `contract_processed_expected_restore_projection_applied`: `8`
- `contract_processed_native_web_disambiguation_hold_no_publish`: `1`
- `contract_processed_non_webnovel_ebook_policy_hold_no_publish`: `1`
- `ordinary_residual_unprocessed`: `23`
- `source_native_reviewed_exclusion_candidate`: `4`

## Gate 해석

Contract-processed `19`건은 최신 shared gate 산출물로 처리 상태가 됐다. source-native exclusion 후보 `4`건은 regression count 제외 후보로 분리됐지만 approval은 아니다. 하지만 release candidate `8`건은 approval이 아니고, no-publish/hold `11`건은 public publish를 열지 않는다. native-web disambiguation hold `1`건과 비웹소설 eBook/classic policy hold `1`건은 닫힌 계약 행이지만 approval은 아니다. 공식 detail URL 보강 follow-up `0`건은 닫힌 행이 아니라 ordinary residual로 유지한다. ordinary residual `23`건과 full375 collateral 재확인이 남아 있으므로 goal은 `ACTIVE / NOT_COMPLETE`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`다.
