# loop605_residual24_candidate_set_projection_application

Candidate-set 계약 계획을 지정된 full375 projection에 적용한 projection-only 산출물이다. 새 runtime replay가 아니며, release 후보가 생겨도 full375 collateral GO 전에는 approval 근거가 아니다.

## 요약

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- projection_rows: `375`
- candidate_set_contract_rows: `8`
- applied_restore_rows: `0`
- applied_hold_rows: `8`
- scrubbed_public_identity_rows: `0`
- already_blocked_hold_rows: `8`
- validation_issue_count: `0`
- runtime_replay_allowed_rows: `0`
- 다음 runtime/test run 실행 계약: `--parallel 16`, web dashboard `http://127.0.0.1:8080`, `--no-dashboard` 금지
- full375 collateral: `NO-GO`
- 완료 기준: `full375 collateral GO + full_scan path`

## 적용 행

- `11671514` hold action=`candidate_set_rebuild_required_before_publish` preserved=`악신의 총애를 받는 성직자가 되었다` status=`preserved_no_release`
- `11682749` hold action=`candidate_set_rebuild_required_before_publish` preserved=`묵향` status=`preserved_no_release`
- `11694035` hold action=`candidate_set_rebuild_required_before_publish` preserved=`아카데미 생존 갤러리` status=`preserved_no_release`
- `11698865` hold action=`candidate_set_rebuild_required_before_publish` preserved=`리제로x자살헌터] 헌터 나츠키` status=`preserved_no_release`
- `11703658` hold action=`candidate_set_rebuild_required_before_publish` preserved=`novel.munpia.com›neSrl` status=`preserved_no_release`
- `11705231` hold action=`candidate_set_rebuild_required_before_publish` preserved=`탐식의 재림` status=`preserved_no_release`
- `11708453` hold action=`candidate_set_rebuild_required_before_publish` preserved=`이세계 검은 머리 외국인` status=`preserved_no_release`
- `11710036` hold action=`candidate_set_rebuild_required_before_publish` preserved=`[림월드]변방계에서 회귀자로 살아남기` status=`preserved_no_release`

## Gate 해석

복구 `0`건은 shared PromotionDecision을 public identity, trace, ledger에 동기화했다. hold `8`건은 serialized public identity를 지우고 후보를 ledger/trace에 보존했다. 이 산출물은 full375 collateral 재평가의 입력일 뿐, runtime 완료나 full_scan approval이 아니다.
