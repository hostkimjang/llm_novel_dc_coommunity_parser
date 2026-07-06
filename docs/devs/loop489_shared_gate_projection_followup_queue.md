# loop489_shared_gate_projection_followup_queue

## 요약

- source_projection_id: `loop489_shared_gate_residual47_projection`
- gate: `REVIEW-LOCKED`
- followup_action_queue_rows: `47`
- label_counts: `{'HOLD': 1, 'REPROCESS': 46}`
- priority_counts: `{'P0': 46, 'P2': 1}`
- projected_status_counts: `{'promotion_blocked': 1, 'safe_resolved': 46}`
- exact_match_counts: `{'match': 46, 'mismatch': 1}`
- runtime_replay_candidate_rows: `46`
- variant_review_rows: `0`
- lint_followup_rows: `0`
- still_blocked_rows: `1`
- validation_issue_count: `0`
- approval: `false`
- semantic_quality: `REVIEW-LOCKED`

## 승인 경계

- 이 큐는 Loop484 projection의 후속 실행 단위이며 approval이 아니다.
- `safe_resolved` projection도 runtime replay와 publication contract audit 전에는 해소 처리하지 않는다.
- source-native exact title mismatch는 canonical variant 또는 wrong-work review 전까지 publish 근거가 아니다.
- 완료 기준은 여전히 `full375 collateral GO + full_scan 경로 정의`다.

## Action groups

### full375_collateral_recheck_after_runtime

- row_count: `46`
- priority_counts: `{'P0': 46}`
- label_counts: `{'REPROCESS': 46}`
- projected_status_counts: `{'safe_resolved': 46}`
- owner_modes: `{'RUNTIME_REPLAY': 46}`
- sample_post_ids: `11660271, 11660273, 11663521, 11663535, 11663557, 11665124, 11668325, 11669913, 11669933, 11673096, 11673102, 11677915`

### runtime_replay_projected_safe_resolved_exact_required

- row_count: `46`
- priority_counts: `{'P0': 46}`
- label_counts: `{'REPROCESS': 46}`
- projected_status_counts: `{'safe_resolved': 46}`
- owner_modes: `{'RUNTIME_REPLAY': 46}`
- sample_post_ids: `11660271, 11660273, 11663521, 11663535, 11663557, 11665124, 11668325, 11669913, 11669933, 11673096, 11673102, 11677915`

### scope_or_nonwork_hard_hold_review_required

- row_count: `1`
- priority_counts: `{'P2': 1}`
- label_counts: `{'HOLD': 1}`
- projected_status_counts: `{'promotion_blocked': 1}`
- owner_modes: `{'POLICY_OR_SOURCE_NATIVE_REVIEW': 1}`
- sample_post_ids: `11710036`
