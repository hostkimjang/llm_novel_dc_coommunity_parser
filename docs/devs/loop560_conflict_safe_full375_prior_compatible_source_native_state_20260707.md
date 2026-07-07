# full375 P0 이전 호환 source-native verdict 상태

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- current batch rows: `126`
- compatible rows: `126`
- unreviewed current batch rows: `0`
- compatible verdicts: `docs/devs/loop560_conflict_safe_full375_prior_compatible_source_native_verdicts.json`

## 제외 사유 집계

- duplicate_compatible_post_id: `333`
- post_id_not_in_current_batch: `94`
- triage_bucket_changed: `23`

## 잔여 배치

- gate: `REVIEW-LOCKED`
- unreviewed rows: `0`
- image rows: `0`
- text-only rows: `0`
- json: `docs\devs\loop560_conflict_safe_full375_unreviewed_batch.json`
- jsonl: `docs\devs\loop560_conflict_safe_full375_unreviewed_batch.jsonl`
- markdown: `docs\devs\loop560_conflict_safe_full375_unreviewed_batch.md`

## 미검토 placeholder verdict

- gate: `REVIEW-LOCKED`
- placeholder rows: `0`
- json: `docs\devs\loop560_conflict_safe_full375_unreviewed_placeholder_verdicts.json`

## 해석

이 산출물은 과거 source-native verdict를 현재 P0 배치에 그대로 승인한 것이 아니다.
동일 post_id, 동일 triage_bucket, 현재 후보의 title/url 일치를 만족한 행만 재사용 후보로 분리했다.
남은 행은 신규 blind/source-native 검토가 필요하며 full375 collateral gate는 계속 NO-GO다.
