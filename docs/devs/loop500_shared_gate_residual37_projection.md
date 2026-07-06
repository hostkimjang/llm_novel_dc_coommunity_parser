# loop500_shared_gate_residual37_projection

## 요약

- source_queue_id: `loop498_current_full375_review_adjusted_residual105_action_queue`
- source_review_id: `loop498_current_full375_p0_review_summary`
- gate: `REVIEW-LOCKED`
- action_filter: `shared_promotion_gate_wiring_required`
- projected_rows: `37`
- projected_status_counts: `{'safe_resolved': 37}`
- publish_allowed_rows: `37`
- matches_source_native_title_rows: `37`
- validation_issue_count: `0`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`

## 경계

- 이 projection은 source-native residual queue를 shared `can_publish_title` 계약으로 투영한 산출물이다.
- Runtime replay, full375 collateral GO, full_scan approval을 대체하지 않는다.
- `safe_resolved` projection 행은 후속 runtime replay 후보이며, replay 후 publication contract와 collateral gate를 다시 봐야 한다.

## 샘플

- `11660271` `safe_resolved` `월야의 여인들` -> `월야의 여인들`
- `11660273` `safe_resolved` `마도서를 줍다 마법사가 되다` -> `마도서를 줍다 마법사가 되다`
- `11663521` `safe_resolved` `초전자포] 시스터즈가 되었다` -> `초전자포] 시스터즈가 되었다`
- `11663535` `safe_resolved` `퇴마록` -> `퇴마록`
- `11663557` `safe_resolved` `퇴마록` -> `퇴마록`
- `11665124` `safe_resolved` `화산파(화산귀환)` -> `화산파(화산귀환)`
- `11668325` `safe_resolved` `Fate/stay night` -> `Fate/stay night`
- `11669913` `safe_resolved` `하룬` -> `하룬`
- `11673096` `safe_resolved` `삼국지` -> `삼국지`
- `11673102` `safe_resolved` `갤질하는 천재 의사` -> `갤질하는 천재 의사`
- `11677915` `safe_resolved` `전지적 독자 시점` -> `전지적 독자 시점`
- `11677926` `safe_resolved` `재앙급 막내 공자의 회귀` -> `재앙급 막내 공자의 회귀`
