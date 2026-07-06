# Loop488 P0 이전 호환 source-native verdict 상태

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- current batch rows: `136`
- compatible rows: `84`
- unreviewed current batch rows: `52`
- compatible verdicts: `docs/devs/loop488_p0_prior_compatible_source_native_verdicts.json`

## 제외 사유 집계

- ambiguous_current_option_match: `2`
- post_id_not_in_current_batch: `34`
- triage_bucket_changed: `18`

## 해석

이 산출물은 과거 source-native verdict를 현재 P0 배치에 그대로 승인한 것이 아니다.
동일 post_id, 동일 triage_bucket, 현재 후보의 title/url 일치를 만족한 행만 재사용 후보로 분리했다.
남은 행은 신규 blind/source-native 검토가 필요하며 full375 collateral gate는 계속 NO-GO다.
