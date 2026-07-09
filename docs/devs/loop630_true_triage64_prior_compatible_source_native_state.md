# full375 P0 이전 호환 source-native verdict 상태

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- current batch rows: `64`
- compatible rows: `45`
- unreviewed current batch rows: `19`
- compatible verdicts: `docs/devs/loop630_true_triage64_prior_compatible_source_native_verdicts.json`

## 제외 사유 집계

- duplicate_compatible_post_id: `305`
- missing_source_triage_bucket_for_auto_bucket: `116`
- post_id_not_in_current_batch: `1395`
- selected_title_or_url_not_in_current_options: `20`
- triage_bucket_changed: `84`

## 잔여 배치

- gate: `REVIEW-LOCKED`
- unreviewed rows: `19`
- image rows: `13`
- text-only rows: `6`
- json: `docs\devs\loop630_true_triage64_unreviewed_source_native_review_batch.json`
- jsonl: `docs\devs\loop630_true_triage64_unreviewed_source_native_review_batch.jsonl`
- markdown: `docs\devs\loop630_true_triage64_unreviewed_source_native_review_batch.md`

## 미검토 placeholder verdict

- gate: `REVIEW-LOCKED`
- placeholder rows: `19`
- json: `docs\devs\loop630_true_triage64_unreviewed_placeholder_verdicts.json`

## 해석

이 산출물은 과거 source-native verdict를 현재 P0 배치에 그대로 승인한 것이 아니다.
동일 post_id, 동일 triage_bucket, 현재 후보의 title/url 일치를 만족한 행만 재사용 후보로 분리했다.
남은 행은 신규 blind/source-native 검토가 필요하며 full375 collateral gate는 계속 NO-GO다.
