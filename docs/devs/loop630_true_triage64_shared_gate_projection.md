# loop630_true_triage64_shared_gate_projection

## 요약

- source_queue_id: `loop630_true_triage64_after_prior_compatible_action_queue`
- source_review_id: `loop630_true_triage64_source_native_combined_review`
- gate: `REVIEW-LOCKED`
- action_filter: `shared_promotion_gate_wiring_required`
- projected_rows: `13`
- projected_status_counts: `{'safe_resolved': 13}`
- publish_allowed_rows: `13`
- matches_source_native_title_rows: `13`
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
- `11663557` `safe_resolved` `퇴마록` -> `퇴마록`
- `11668325` `safe_resolved` `Fate/stay night` -> `Fate/stay night`
- `11677926` `safe_resolved` `재앙급 막내 공자의 회귀` -> `재앙급 막내 공자의 회귀`
- `11698910` `safe_resolved` `판초우의의 마법사` -> `판초우의의 마법사`
- `11706871` `safe_resolved` `파우스트` -> `파우스트`
- `11710049` `safe_resolved` `[림월드]변방계에서 회귀자로 살아남기` -> `[림월드]변방계에서 회귀자로 살아남기`
- `11714887` `safe_resolved` `도굴왕 1 |` -> `도굴왕 1 |`
- `11666741` `safe_resolved` `별을 품은 소드마스터` -> `별을 품은 소드마스터`
- `11679537` `safe_resolved` `죽었다 깨어도 수선` -> `죽었다 깨어도 수선`
- `11665121` `safe_resolved` `후회 안 하는 프로듀서` -> `후회 안 하는 프로듀서`
