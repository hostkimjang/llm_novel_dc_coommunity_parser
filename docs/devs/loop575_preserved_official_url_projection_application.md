# loop575_preserved_official_url_projection_contract source-native 수리 projection

- 결과 파일: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop575_preserved_official_url_projection_result.json`
- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- projection 행 수: `375`
- eligible safe-loss 행 수: `9`
- publish 적용 행 수: `2`
- post-sync hold 행 수: `0`
- skip 행 수: `7`

## 결과 집계

- `applied_shared_gate_publish`: `2`
- `skipped_by_shared_gate`: `1`
- `skipped_missing_official_detail_url`: `6`

## Gate 해석

이 적용은 source-native verdict를 shared promotion seed helper와 final publication ledger sync에 통과시킨 projection-only 수렴이다. runtime replay, semantic approval, full_scan approval이 아니다.

## 행 요약

- `11718114` `skipped_by_shared_gate` `None` -> `None` (promotion_blocked -> promotion_blocked)
- `11710021` `applied_shared_gate_publish` `None` -> `무한의 마법사` (output_consistency_lint -> safe_resolved)
- `11665124` `skipped_missing_official_detail_url` `None` -> `None` (promotion_blocked -> None)
- `11698859` `skipped_missing_official_detail_url` `None` -> `None` (promotion_blocked -> None)
- `11700500` `skipped_missing_official_detail_url` `None` -> `None` (promotion_blocked -> None)
- `11682775` `skipped_missing_official_detail_url` `None` -> `None` (promotion_blocked -> None)
- `11700483` `skipped_missing_official_detail_url` `None` -> `None` (promotion_blocked -> None)
- `11710049` `skipped_missing_official_detail_url` `None` -> `None` (promotion_blocked -> None)
- `11669921` `applied_shared_gate_publish` `None` -> `악당은 살고 싶다` (promotion_blocked -> safe_resolved)
