# loop589_p0_info_missing_candidate_set_projection_application

Candidate-set 계약 계획을 지정된 full375 projection에 적용한 projection-only 산출물이다. 새 runtime replay가 아니며, release 후보가 생겨도 full375 collateral GO 전에는 approval 근거가 아니다.

## 요약

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- projection_rows: `375`
- candidate_set_contract_rows: `1`
- applied_restore_rows: `0`
- applied_hold_rows: `1`
- scrubbed_public_identity_rows: `0`
- already_blocked_hold_rows: `1`
- validation_issue_count: `0`
- runtime_replay_allowed_rows: `0`
- 다음 runtime/test run 실행 계약: `--parallel 16`, web dashboard `http://127.0.0.1:8080`, `--no-dashboard` 금지
- full375 collateral: `NO-GO`
- 완료 기준: `full375 collateral GO + full_scan path`

## 적용 행

- `11671514` hold action=`candidate_set_rebuild_required_before_publish` preserved=`악신의 총애를 받는 성직자가 되었다` status=`preserved_no_release`

## Gate 해석

복구 `0`건은 shared PromotionDecision을 public identity, trace, ledger에 동기화했다. hold `1`건은 serialized public identity를 지우고 후보를 ledger/trace에 보존했다. 이 산출물은 full375 collateral 재평가의 입력일 뿐, runtime 완료나 full_scan approval이 아니다.
