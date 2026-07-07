# loop596_native_web_judge_shared_gate_projection

## 요약

- source_queue_id: `None`
- source_review_id: `loop589_p0_info_missing_source_native_verdicts`
- gate: `REVIEW-LOCKED`
- action_filter: `shared_promotion_gate_wiring_required`
- projected_rows: `5`
- projected_status_counts: `{'promotion_blocked': 3, 'safe_resolved': 2}`
- publish_allowed_rows: `2`
- matches_source_native_title_rows: `2`
- validation_issue_count: `0`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`

## 경계

- 이 projection은 source-native residual queue를 shared `can_publish_title` 계약으로 투영한 산출물이다.
- Runtime replay, full375 collateral GO, full_scan approval을 대체하지 않는다.
- `safe_resolved` projection 행은 후속 runtime replay 후보이며, replay 후 publication contract와 collateral gate를 다시 봐야 한다.

## 샘플

- `11682792` `promotion_blocked` `이 무림의 미친년은 나야` -> `None`
- `11660273` `promotion_blocked` `마도서를 줍다 마법사가 되다` -> `None`
- `11698871` `safe_resolved` `Re : 제로부터 시작하는 이세계 생활` -> `Re : 제로부터 시작하는 이세계 생활`
- `11706844` `safe_resolved` `호랑이 사냥꾼` -> `호랑이 사냥꾼`
- `11710047` `promotion_blocked` `아카데미 속 미움받는 악역이 되었다` -> `None`
