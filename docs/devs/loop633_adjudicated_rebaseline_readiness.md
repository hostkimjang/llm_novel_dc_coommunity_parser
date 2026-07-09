# Loop633 adjudicated re-baseline readiness

Loop633은 source-native 미판정 35건을 전수 판결했지만, remaining residual follow-up 30건이 남아 re-baseline을 적용하지 않는다. 완료 게이트는 raw가 아니라 adjusted 기준이다.

## 요약
- gate: `NO-GO`
- rebaseline_status: `NOT_APPLIED`
- source_native_reviewed_rows: `35`
- source_native_info_missing_rows: `0`
- adjusted_exclusion_candidate_rows: `11`
- ordinary_residual_followup_rows: `30`
- dispatch_lane_counts: `{'candidate_set_rebuild_review': 6, 'canonical_policy_cleanup_review': 2, 'native_web_image_evidence_review': 12, 'no_publish_multiwork_guard_review': 4, 'shared_gate_restore_contract_review': 6}`
- completion_gate: `adjusted full375 collateral GO + full_scan path`

## 경계
- 2026-06-26 raw baseline diff는 진단용 historical compare일 뿐 완료 기준이 아니다.
- adjudicated 결과를 새 baseline으로 재동결하려면 remaining residual follow-up이 닫히고 adjusted full375 collateral GO와 full_scan 경로가 확인되어야 한다.
- `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`를 유지한다.
