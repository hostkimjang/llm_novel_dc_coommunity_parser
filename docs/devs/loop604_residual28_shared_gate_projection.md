# loop604_residual28_shared_gate_projection

## 요약

- source_queue_id: `loop602_after_unreviewed13_source_native_residual_action_queue`
- source_review_id: `['loop595_residual46_native_web_judge_source_native_review', 'loop602_corrected_full375_unreviewed13_source_native_verdicts']`
- gate: `REVIEW-LOCKED`
- action_filter: `shared_promotion_gate_wiring_required`
- projected_rows: `4`
- projected_status_counts: `{'promotion_blocked': 1, 'safe_resolved': 3}`
- publish_allowed_rows: `3`
- matches_source_native_title_rows: `3`
- validation_issue_count: `0`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`

## 경계

- 이 projection은 source-native residual queue를 shared `can_publish_title` 계약으로 투영한 산출물이다.
- Runtime replay, full375 collateral GO, full_scan approval을 대체하지 않는다.
- `safe_resolved` projection 행은 후속 runtime replay 후보이며, replay 후 publication contract와 collateral gate를 다시 봐야 한다.

## 샘플

- `11694041` `safe_resolved` `격투 소설 엑스트라가 타격 천재임` -> `격투 소설 엑스트라가 타격 천재임`
- `11698859` `safe_resolved` `귤부인 대롱대롱` -> `귤부인 대롱대롱`
- `11706844` `safe_resolved` `호랑이 사냥꾼` -> `호랑이 사냥꾼`
- `11710047` `promotion_blocked` `아카데미 속 미움받는 악역이 되었다` -> `None`
