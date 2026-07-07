# loop586_residual46_canonical_title_rewrite_accounting

`residual_queue`에 `loop586_canonical_title_rewrite_combined_restore_contract_plan` contract 결과를 결합한 회계 산출물이다. 이 산출물은 새 runtime replay나 full375 GO가 아니며, contract 처리 상태와 아직 남은 ordinary residual을 분리한다.

## 요약

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- source_residual_rows: `46`
- contract_plan_overlap_rows: `6`
- contract_processed_rows: `5`
- ordinary_residual_unprocessed_rows: `41`
- validation_issue_count: `0`
- release_candidate_not_approval_rows: `5`
- no_publish_or_hold_contract_rows: `0`
- official_support_missing_restore_followup_rows: `1`
- publish_allowed_rows: `0`
- runtime_replay_allowed_rows: `0`
- full375 collateral: `NO-GO`

## Contract 회계 상태

- `contract_processed_expected_restore_projection_applied`: `5`
- `ordinary_residual_unprocessed`: `41`

## Gate 해석

Contract-processed `5`건은 최신 shared gate 산출물로 처리 상태가 됐다. 하지만 release candidate `5`건은 approval이 아니고, no-publish/hold `0`건은 public publish를 열지 않는다. 공식 detail URL 보강 follow-up `1`건은 닫힌 행이 아니라 ordinary residual로 유지한다. ordinary residual `41`건과 full375 collateral 재확인이 남아 있으므로 goal은 `ACTIVE / NOT_COMPLETE`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`다.
