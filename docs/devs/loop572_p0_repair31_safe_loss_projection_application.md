# loop572_p0_repair31_safe_loss_projection_contract source-native 수리 projection

- 결과 파일: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop572_p0_repair31_safe_loss_projection_result.json`
- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- projection 행 수: `375`
- eligible safe-loss 행 수: `17`
- publish 적용 행 수: `4`
- post-sync hold 행 수: `2`
- skip 행 수: `11`

## 결과 집계

- `applied_shared_gate_publish`: `4`
- `post_sync_held`: `2`
- `skipped_by_shared_gate`: `1`
- `skipped_missing_official_detail_url`: `10`

## Gate 해석

이 적용은 source-native verdict를 shared promotion seed helper와 final publication ledger sync에 통과시킨 projection-only 수렴이다. runtime replay, semantic approval, full_scan approval이 아니다.

## 행 요약

- `11718114` `skipped_by_shared_gate` `None` -> `None` (promotion_blocked -> promotion_blocked)
- `11697242` `skipped_missing_official_detail_url` `None` -> `None` (output_consistency_lint -> None)
- `11710021` `skipped_missing_official_detail_url` `None` -> `None` (output_consistency_lint -> None)
- `11665124` `skipped_missing_official_detail_url` `None` -> `None` (promotion_blocked -> None)
- `11666741` `applied_shared_gate_publish` `None` -> `별을 품은 소드마스터` (promotion_blocked -> safe_resolved)
- `11694065` `applied_shared_gate_publish` `None` -> `아카데미에서 살아남기` (promotion_blocked -> safe_resolved)
- `11698859` `skipped_missing_official_detail_url` `None` -> `None` (promotion_blocked -> None)
- `11708447` `skipped_missing_official_detail_url` `None` -> `None` (promotion_blocked -> None)
- `11700500` `skipped_missing_official_detail_url` `None` -> `None` (promotion_blocked -> None)
- `11718099` `post_sync_held` `None` -> `None` (promotion_blocked -> promotion_blocked)
- `11668300` `post_sync_held` `None` -> `None` (promotion_blocked -> promotion_blocked)
- `11697256` `applied_shared_gate_publish` `None` -> `황제의 딸로 환생했다` (promotion_blocked -> safe_resolved)
- `11708478` `applied_shared_gate_publish` `None` -> `사연 있는 악역으로 착각 당한다` (promotion_blocked -> safe_resolved)
- `11682775` `skipped_missing_official_detail_url` `None` -> `None` (promotion_blocked -> None)
- `11700483` `skipped_missing_official_detail_url` `None` -> `None` (promotion_blocked -> None)
- `11710049` `skipped_missing_official_detail_url` `None` -> `None` (promotion_blocked -> None)
- `11669921` `skipped_missing_official_detail_url` `None` -> `None` (promotion_blocked -> None)
