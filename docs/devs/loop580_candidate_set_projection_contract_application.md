# loop580_candidate_set_projection_contract_application

Loop578 candidate-set 계약 계획을 Loop577 full375 projection에 적용한 projection-only 산출물이다. 새 runtime replay가 아니며, release 후보가 생겨도 full375 collateral GO 전에는 approval 근거가 아니다.

## 요약

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- projection_rows: `375`
- candidate_set_contract_rows: `10`
- applied_restore_rows: `4`
- applied_hold_rows: `6`
- scrubbed_public_identity_rows: `2`
- already_blocked_hold_rows: `4`
- validation_issue_count: `0`
- runtime_replay_allowed_rows: `0`
- 다음 runtime/test run 실행 계약: `--parallel 16`, web dashboard `http://127.0.0.1:8080`, `--no-dashboard` 금지
- full375 collateral: `NO-GO`
- 완료 기준: `full375 collateral GO + full_scan path`

## 적용 행

- `11660241` restore target=`이세계 TRPG 게임마스터` superseded=`[ 이티알 ] 이 세계 TRPG 마스터`
- `11663514` restore target=`마탄 속의 제국` superseded=`올바른 슬라임 사용법`
- `11671514` hold action=`candidate_set_rebuild_required_before_publish` preserved=`악신의 총애를 받는 성직자가 되었다` status=`scrubbed_public_identity`
- `11674694` restore target=`21세기 무림세가` superseded=`21세기 무림 인`
- `11682749` hold action=`candidate_set_rebuild_required_before_publish` preserved=`묵향` status=`preserved_no_release`
- `11698870` hold action=`no_publish_intent_guard_contract_case` preserved=`인간실격 히로인들을 수집해버렸다` status=`scrubbed_public_identity`
- `11703658` hold action=`candidate_set_rebuild_required_before_publish` preserved=`novel.munpia.com›neSrl` status=`preserved_no_release`
- `11705231` hold action=`candidate_set_rebuild_required_before_publish` preserved=`탐식의 재림` status=`preserved_no_release`
- `11710036` hold action=`candidate_set_rebuild_required_before_publish` preserved=`[림월드]변방계에서 회귀자로 살아남기` status=`preserved_no_release`
- `11716464` restore target=`슈라라펜란트` superseded=`슈라라펜란트 - 판타지 웹소설`

## Gate 해석

복구 `4`건은 shared PromotionDecision을 public identity, trace, ledger에 동기화했다. hold `6`건은 serialized public identity를 지우고 후보를 ledger/trace에 보존했다. 이 산출물은 full375 collateral 재평가의 입력일 뿐, runtime 완료나 full_scan approval이 아니다.
