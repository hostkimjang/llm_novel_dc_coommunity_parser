# loop589_p0_info_missing_source_native_restore_projection_application source-native 수리 projection

- 결과 파일: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop589_p0_info_missing_source_native_restore_projection_result.json`
- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- projection 행 수: `375`
- eligible restore 행 수: `2`
- eligible safe-loss 행 수: `0`
- eligible wrong-work 수리 행 수: `2`
- publish 적용 행 수: `2`
- post-sync hold 행 수: `0`
- skip 행 수: `0`

## 결과 집계

- `applied_shared_gate_publish`: `2`

## Eligible action 집계

- `repair_after_wrong_work`: `2`

## Gate 해석

이 적용은 source-native verdict를 shared promotion seed helper와 final publication ledger sync에 통과시킨 projection-only 수렴이다. runtime replay, semantic approval, full_scan approval이 아니다.

## 행 요약

- `11682792` `applied_shared_gate_publish` `[무친년]이 무림의 미친놈` -> `이 무림의 미친년은 나야` (safe_resolved -> safe_resolved)
- `11660273` `applied_shared_gate_publish` `그리즐리 그랑` -> `마도서를 줍다 마법사가 되다` (safe_resolved -> safe_resolved)
