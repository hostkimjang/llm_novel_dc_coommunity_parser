# loop541_b1_missing_candidate_post_verdict_contract_queue

이 큐는 canonical verdict 적용 뒤의 contract 작업 배치다. 아직 runtime replay 허가가 아니며, contract test와 필요한 native-web/강한 근거 확인 전에는 full_scan approval을 열지 않는다.

## 요약

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- source_application_rows: `11`
- contract_queue_rows: `11`
- validation issues: `0`
- runtime_replay_allowed_rows: `0`
- contract_test_required_rows: `11`
- full375 collateral: `NO-GO`
- completion gate: `full375 collateral GO + full_scan path`

## Contract batch lanes

- `C1_expected_restore_or_candidate_scrub_contract`: `6`
- `C3_stronger_evidence_or_native_web_hold`: `5`

## Next batches

- `C1_expected_restore_or_candidate_scrub_contract` rows=`6` runtime_replay_allowed=`0`
  - post_ids: `11697256`, `11666741`, `11694068`, `11663511`, `11669933`, `11706831`
- `C3_stronger_evidence_or_native_web_hold` rows=`5` runtime_replay_allowed=`0`
  - post_ids: `11669913`, `11697242`, `11718114`, `11669926`, `11677924`

## Gate 해석

Canonical verdict는 `11/11` 적용됐지만 이 큐는 replay release가 아니다. C1/C2는 contract test가 먼저 필요하고, C3는 stronger evidence 또는 native-web 검증 전까지 hard hold다.
