# full375 P0 이전 호환 source-native verdict 상태

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- current batch rows: `86`
- compatible rows: `84`
- unreviewed current batch rows: `2`
- compatible verdicts: `docs/devs/loop581_candidate_set_full375_prior_compatible_source_native_verdicts.json`

## 제외 사유 집계

- duplicate_compatible_post_id: `453`
- post_id_not_in_current_batch: `321`
- triage_bucket_changed: `37`

## 잔여 배치

- gate: `REVIEW-LOCKED`
- unreviewed rows: `2`
- image rows: `2`
- text-only rows: `0`
- json: `out\regression_safe_grounding_20260626_000008_928006_loop01\review\loop581_candidate_set_full375_prior_incompatible_review_batch.json`
- jsonl: `out\regression_safe_grounding_20260626_000008_928006_loop01\review\loop581_candidate_set_full375_prior_incompatible_review_batch.jsonl`
- markdown: `out\regression_safe_grounding_20260626_000008_928006_loop01\review\loop581_candidate_set_full375_prior_incompatible_review_batch.md`

## 미검토 placeholder verdict

- gate: `REVIEW-LOCKED`
- placeholder rows: `2`
- json: `docs\devs\loop581_candidate_set_full375_unreviewed_placeholder_verdicts.json`

## 해석

이 산출물은 과거 source-native verdict를 현재 P0 배치에 그대로 승인한 것이 아니다.
동일 post_id, 동일 triage_bucket, 현재 후보의 title/url 일치를 만족한 행만 재사용 후보로 분리했다.
남은 행은 신규 blind/source-native 검토가 필요하며 full375 collateral gate는 계속 NO-GO다.
