# loop573_official_detail_url_canonical_projection_contract source-native 수리 projection

- 결과 파일: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop573_official_detail_url_canonical_projection_result.json`
- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- projection 행 수: `375`
- eligible safe-loss 행 수: `13`
- publish 적용 행 수: `2`
- post-sync hold 행 수: `2`
- skip 행 수: `9`

## 결과 집계

- `applied_shared_gate_publish`: `2`
- `post_sync_held`: `2`
- `skipped_by_shared_gate`: `1`
- `skipped_missing_official_detail_url`: `8`

## Gate 해석

이 적용은 source-native verdict를 shared promotion seed helper와 final publication ledger sync에 통과시킨 projection-only 수렴이다. runtime replay, semantic approval, full_scan approval이 아니다.

## 행 요약

- `11718114` `skipped_by_shared_gate` `None` -> `None` (promotion_blocked -> promotion_blocked)
- `11697242` `applied_shared_gate_publish` `None` -> `유희왕` (output_consistency_lint -> safe_resolved)
- `11710021` `skipped_missing_official_detail_url` `None` -> `None` (output_consistency_lint -> None)
- `11665124` `skipped_missing_official_detail_url` `None` -> `None` (promotion_blocked -> None)
- `11698859` `skipped_missing_official_detail_url` `None` -> `None` (promotion_blocked -> None)
- `11708447` `applied_shared_gate_publish` `None` -> `잠룡회귀` (promotion_blocked -> safe_resolved)
- `11700500` `skipped_missing_official_detail_url` `None` -> `None` (promotion_blocked -> None)
- `11718099` `post_sync_held` `None` -> `None` (promotion_blocked -> promotion_blocked)
- `11668300` `post_sync_held` `None` -> `None` (promotion_blocked -> promotion_blocked)
- `11682775` `skipped_missing_official_detail_url` `None` -> `None` (promotion_blocked -> None)
- `11700483` `skipped_missing_official_detail_url` `None` -> `None` (promotion_blocked -> None)
- `11710049` `skipped_missing_official_detail_url` `None` -> `None` (promotion_blocked -> None)
- `11669921` `skipped_missing_official_detail_url` `None` -> `None` (promotion_blocked -> None)
