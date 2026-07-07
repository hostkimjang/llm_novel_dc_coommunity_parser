# loop515_residual100_shared_gate_followup_queue

## 요약

- source_projection_id: `loop515_residual100_shared_gate_projection`
- gate: `REVIEW-LOCKED`
- followup_action_queue_rows: `57`
- label_counts: `{'REPROCESS': 57}`
- priority_counts: `{'P0': 57}`
- projected_status_counts: `{'safe_resolved': 57}`
- exact_match_counts: `{'match': 57}`
- prior_runtime_audit_status_counts: `{}`
- runtime_replay_candidate_rows: `57`
- variant_review_rows: `0`
- lint_followup_rows: `0`
- still_blocked_rows: `0`
- validation_issue_count: `0`
- approval: `false`
- semantic_quality: `REVIEW-LOCKED`

## 승인 경계

- 이 큐는 source projection의 후속 실행 단위이며 approval이 아니다.
- `safe_resolved` projection도 runtime replay와 publication contract audit 전에는 해소 처리하지 않는다.
- prior runtime expected-audit 실패 행은 같은 입력 반복 실행 전에 repair/source-native review lane으로 보낸다.
- source-native exact title mismatch는 canonical variant 또는 wrong-work review 전까지 publish 근거가 아니다.
- 완료 기준은 여전히 `full375 collateral GO + full_scan 경로 정의`다.

## Action groups

### full375_collateral_recheck_after_runtime

- row_count: `57`
- priority_counts: `{'P0': 57}`
- label_counts: `{'REPROCESS': 57}`
- projected_status_counts: `{'safe_resolved': 57}`
- owner_modes: `{'RUNTIME_REPLAY': 57}`
- sample_post_ids: `11660271, 11660273, 11663535, 11663557, 11665124, 11668325, 11669913, 11673102, 11677915, 11677926, 11681172, 11690841`

### runtime_replay_projected_safe_resolved_exact_required

- row_count: `57`
- priority_counts: `{'P0': 57}`
- label_counts: `{'REPROCESS': 57}`
- projected_status_counts: `{'safe_resolved': 57}`
- owner_modes: `{'RUNTIME_REPLAY': 57}`
- sample_post_ids: `11660271, 11660273, 11663535, 11663557, 11665124, 11668325, 11669913, 11673102, 11677915, 11677926, 11681172, 11690841`
