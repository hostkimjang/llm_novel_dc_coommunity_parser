# full375 P0 이전 호환 source-native verdict 상태

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- current batch rows: `117`
- compatible rows: `102`
- unreviewed current batch rows: `15`
- compatible verdicts: `docs/devs/loop570_full375_after_loop569_prior_compatible_source_native_verdicts.json`

## 제외 사유 집계

- post_id_not_in_current_batch: `14`
- triage_bucket_changed: `2`

## 잔여 배치

- gate: `REVIEW-LOCKED`
- unreviewed rows: `15`
- image rows: `12`
- text-only rows: `3`
- json: `docs\devs\loop570_full375_after_loop569_prior_incompatible_review_batch.json`
- jsonl: `docs\devs\loop570_full375_after_loop569_prior_incompatible_review_batch.jsonl`
- markdown: `docs\devs\loop570_full375_after_loop569_prior_incompatible_review_batch.md`

## 미검토 placeholder verdict

- gate: `REVIEW-LOCKED`
- placeholder rows: `15`
- json: `docs\devs\loop570_full375_after_loop569_info_missing_placeholder_verdicts.json`

## 해석

이 산출물은 과거 source-native verdict를 현재 P0 배치에 그대로 승인한 것이 아니다.
동일 post_id, 동일 triage_bucket, 현재 후보의 title/url 일치를 만족한 행만 재사용 후보로 분리했다.
남은 행은 신규 blind/source-native 검토가 필요하며 full375 collateral gate는 계속 NO-GO다.
