# loop578_candidate_set_contract_plan

Loop577 refined P0 dispatch의 `candidate_set_rebuild_review` 10건을 shared promotion gate 계약 계획으로 분리한 산출물이다. 이 문서는 runtime replay 허가나 full_scan approval이 아니다.

## 요약

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- candidate_set_contract_plan_rows: `10`
- validation_issue_count: `0`
- contract_action_counts: `{'candidate_set_expected_restore_contract_case': 4, 'candidate_set_rebuild_required_before_publish': 5, 'no_publish_intent_guard_contract_case': 1}`
- promotion_decision_status_counts: `{'candidate_only': 1, 'publish': 4, 'reject': 5}`
- release_candidate_not_approval_rows: `4`
- candidate_set_rebuild_hold_rows: `5`
- intent_guard_hold_rows: `1`
- runtime_replay_allowed_rows: `0`
- full375 collateral: `NO-GO`

## 실행 계약

- 이 산출물만으로 runtime replay를 시작하지 않는다.
- 다음 test/runtime run은 `--parallel 16`을 사용한다.
- 웹 대시보드: `http://127.0.0.1:8080`
- `--no-dashboard`는 금지한다.
- 이미 dashboard 없이 시작한 런만 manifest 사후 부착 명령을 사용한다.

## 행별 계획

- `11660241` action=`candidate_set_expected_restore_contract_case` decision=`publish` target=`이세계 TRPG 게임마스터` official_refs=`1` release_candidate_not_approval=`true`
- `11663514` action=`candidate_set_expected_restore_contract_case` decision=`publish` target=`마탄 속의 제국` official_refs=`1` release_candidate_not_approval=`true`
- `11671514` action=`candidate_set_rebuild_required_before_publish` decision=`reject` target=`-` official_refs=`0` release_candidate_not_approval=`false`
- `11674694` action=`candidate_set_expected_restore_contract_case` decision=`publish` target=`21세기 무림세가` official_refs=`1` release_candidate_not_approval=`true`
- `11682749` action=`candidate_set_rebuild_required_before_publish` decision=`reject` target=`-` official_refs=`0` release_candidate_not_approval=`false`
- `11698870` action=`no_publish_intent_guard_contract_case` decision=`candidate_only` target=`인간실격` official_refs=`0` release_candidate_not_approval=`false`
- `11703658` action=`candidate_set_rebuild_required_before_publish` decision=`reject` target=`-` official_refs=`0` release_candidate_not_approval=`false`
- `11705231` action=`candidate_set_rebuild_required_before_publish` decision=`reject` target=`-` official_refs=`0` release_candidate_not_approval=`false`
- `11710036` action=`candidate_set_rebuild_required_before_publish` decision=`reject` target=`-` official_refs=`1` release_candidate_not_approval=`false`
- `11716464` action=`candidate_set_expected_restore_contract_case` decision=`publish` target=`슈라라펜란트` official_refs=`1` release_candidate_not_approval=`true`

## Gate 해석

- `candidate_set_expected_restore_contract_case` 4건은 source-native 근거와 공식 detail URL을 갖춘 contract case다. 이는 release 후보 표시일 뿐 승인 완료가 아니다.
- `candidate_set_rebuild_required_before_publish` 5건은 현재 후보셋이 source-supported title을 담지 못하므로 publish 금지 상태로 둔다.
- `no_publish_intent_guard_contract_case` 1건은 고전 작품 intent guard로 같은 표면 웹소설 promotion을 막는다.
- 완료 기준은 계속 `full375 collateral GO + full_scan 경로 정의`다.
