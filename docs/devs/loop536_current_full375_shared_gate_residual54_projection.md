# loop536_current_full375_shared_gate_residual54_projection

## 요약

- source_queue_id: `loop536_current_full375_review_adjusted_residual100_action_queue`
- source_review_id: `loop536_current_full375_p0_review_adjusted_summary`
- gate: `REVIEW-LOCKED`
- action_filter: `shared_promotion_gate_wiring_required`
- projected_rows: `54`
- projected_status_counts: `{'safe_resolved': 54}`
- publish_allowed_rows: `54`
- matches_source_native_title_rows: `54`
- validation_issue_count: `0`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`

## 경계

- 이 projection은 source-native residual queue를 shared `can_publish_title` 계약으로 투영한 산출물이다.
- Runtime replay, full375 collateral GO, full_scan approval을 대체하지 않는다.
- `safe_resolved` projection 행은 후속 runtime replay 후보이며, replay 후 publication contract와 collateral gate를 다시 봐야 한다.

## 샘플

- `11660273` `safe_resolved` `마도서를 줍다 마법사가 되다` -> `마도서를 줍다 마법사가 되다`
- `11663535` `safe_resolved` `퇴마록` -> `퇴마록`
- `11663557` `safe_resolved` `퇴마록` -> `퇴마록`
- `11665124` `safe_resolved` `화산파(화산귀환)` -> `화산파(화산귀환)`
- `11668325` `safe_resolved` `Fate/stay night` -> `Fate/stay night`
- `11669913` `safe_resolved` `하룬` -> `하룬`
- `11673102` `safe_resolved` `갤질하는 천재 의사` -> `갤질하는 천재 의사`
- `11677915` `safe_resolved` `전지적 독자 시점` -> `전지적 독자 시점`
- `11677926` `safe_resolved` `재앙급 막내 공자의 회귀` -> `재앙급 막내 공자의 회귀`
- `11681172` `safe_resolved` `헌터갤러리의 국가권력급 기계공주` -> `헌터갤러리의 국가권력급 기계공주`
- `11690841` `safe_resolved` `블루 아카이브` -> `블루 아카이브`
- `11694019` `safe_resolved` `혼후 순결` -> `혼후 순결`
