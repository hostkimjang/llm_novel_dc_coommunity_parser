# Loop599 Loop595+unreviewed40 병합 source-native/full375 재회계

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- source summaries: `2`
- batch review rows: `65`
- reviewed rows: `65`
- source-native decision rows: `56`
- info missing rows: `9`
- validation issues: `0`

## Source Summaries

- `loop595_residual46_native_web_judge_source_native_review` rows=`25` exclude=`7` residual=`18` path=`docs\devs\loop595_residual46_native_web_judge_source_native_review.json`
- `loop599_full375_unreviewed40_source_native_verdicts` rows=`40` exclude=`37` residual=`3` path=`docs\devs\loop599_full375_unreviewed40_source_native_review.json`

## Action queue 전환

- 원 P0 행: `65`
- source-native 검토 완료: `65`
- source-native decision rows: `56`
- info missing rows: `9`
- gate wiring 뒤 regression count 제외 후보: `44`
- REPROCESS 수리 큐: `6`
- HOLD 정책/native 추가 검토 큐: `6`
- 잔여 action queue: `21`
- full collateral approval open: `false`

## 라벨 집계

- `ACCEPT`: `44`
- `HOLD`: `5`
- `INFO_MISSING`: `9`
- `REJECT`: `1`
- `REPROCESS`: `6`

## 버킷 집계

- `safe_loss_resolved_to_null`: `25`
- `unsafe_promotion_from_hold`: `22`
- `wrong_work_title_flip`: `18`

## Gate 해석

이 병합 요약은 full375 collateral regression을 source-native 검토로 재회계하기 위한 입력이다. 검토 제외 후보가 있어도 raw/full375 gate가 조용해지기 전까지 승인으로 보지 않는다.
