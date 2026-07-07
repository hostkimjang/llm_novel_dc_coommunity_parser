# Loop566 title mismatch 2건 source-native verdict

Loop566은 Loop565 title mismatch `2`건을 동일 runtime packet 재실행 없이 source-native/blind 기준으로 판정했다. 이 verdict는 approval이 아니라 shared promotion gate contract 입력이다.

## 요약

- source batch: `docs/devs/loop565_title_mismatch_hold2_source_native_batch.json`
- source packet: `docs/devs/loop565_title_mismatch_hold2_source_native_review_packet.json`
- source runtime result: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop564_conflict_safe_p0_shared_gate_runtime_replay_result.json`
- review rows: `2`
- label counts: `ACCEPT 1 / REPROCESS 1`
- runtime replay after review: `NOT_RUN_AFTER_REVIEW`
- full375 collateral: `NO-GO`
- `semantic_quality=REVIEW-LOCKED`
- `full_scan_approval=false`

## 판정

- `11665121`: `ACCEPT`. actual `후회 안 하는 프로듀서 [독점]`은 네이버 시리즈 공식 상세의 bracketed canonical title이고, expected `후회 안 하는 프로듀서`는 compact title이다. expected audit update/exclusion contract로 보낸다.
- `11673080`: `REPROCESS`. source projection follow-up의 의사물/OCR 근거는 `갤질하는 천재 의사`를 지지하지만 runtime actual은 `흔적을 보는 천재 무사`로 wrong-work publish다. canonical cleanup/URL correction contract로 보낸다.

## Gate

- Title mismatch verdict: `REVIEW-LOCKED / 2`
- Runtime replay: `BLOCKED / allowed 0`
- Full375 collateral: `NO-GO / adjusted residual 87`
- Overall goal: `ACTIVE / NOT_COMPLETE`

완료 기준은 계속 `full375 collateral GO + full_scan 경로 정의`다.
