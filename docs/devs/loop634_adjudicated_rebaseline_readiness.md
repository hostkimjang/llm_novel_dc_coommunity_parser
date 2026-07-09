# Loop634 adjudicated re-baseline readiness

Loop634는 Loop633 이후 남은 shared-gate residual 6건을 계약 계획, projection 적용, release audit, publication convergence까지 닫았다. 그러나 ordinary residual 24건과 adjusted full375 collateral GO가 아직 남아 있으므로 re-baseline은 적용하지 않는다.

## 요약
- gate: `NO-GO`
- rebaseline_status: `NOT_APPLIED`
- shared_gate_contract_rows: `6`
- release_candidate_not_approval_rows: `6`
- publication_contract_gate: `GO`
- publication_contract_violation_rows: `0`
- ordinary_residual_followup_rows: `24`
- dispatch_lane_counts: `{'candidate_set_rebuild_review': 6, 'canonical_policy_cleanup_review': 2, 'native_web_image_evidence_review': 12, 'no_publish_multiwork_guard_review': 4}`
- golden18_gate: `GO`
- full375_collateral_gate: `NO-GO`
- historical_raw_collateral_regression_count: `114`
- adjusted_drift_count: `None`
- completion_gate: `adjusted full375 collateral GO + full_scan path`

## 경계
- shared-gate 6건은 release candidate 상태지만 approval이 아니다. full375 adjusted collateral과 full_scan 경로가 열리기 전까지 publish/full_scan 승인은 닫힌다.
- 2026-06-26 raw baseline diff는 historical compare다. 판결 완료 뒤 새 baseline으로 재동결하면 완료 게이트는 raw가 아니라 adjusted drift 기준으로 평가한다.
- 다음 residual 처리는 단건 반복이 아니라 dispatch lane batch로 진행한다.
- `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`를 유지한다.
