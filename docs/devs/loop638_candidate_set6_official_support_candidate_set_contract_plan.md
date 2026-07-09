# loop638_candidate_set6_official_support_candidate_set_contract_plan

`loop638_candidate_set6_official_support_enrichment_review_enriched_restore_dispatch`의 `candidate_set_rebuild_review` 행을 shared promotion gate 계약 계획으로 분리한 산출물이다. 이 문서는 runtime replay 허가나 full_scan approval이 아니다.

## 요약

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- candidate_set_contract_plan_rows: `6`
- validation_issue_count: `0`
- contract_action_counts: `{'candidate_set_expected_restore_contract_case': 6}`
- promotion_decision_status_counts: `{'publish': 6}`
- release_candidate_not_approval_rows: `6`
- candidate_set_rebuild_hold_rows: `0`
- intent_guard_hold_rows: `0`
- runtime_replay_allowed_rows: `0`
- full375 collateral: `NO-GO`

## 실행 계약

- 이 산출물만으로 runtime replay를 시작하지 않는다.
- 다음 test/runtime run은 `--parallel 16`을 사용한다.
- 웹 대시보드: `http://127.0.0.1:8080`
- `--no-dashboard`는 금지한다.
- 이미 dashboard 없이 시작한 런만 manifest 사후 부착 명령을 사용한다.

## 행별 계획

- `11660257` action=`candidate_set_expected_restore_contract_case` decision=`publish` target=`암흑가 보스요? 제가요?` official_refs=`2` release_candidate_not_approval=`true`
- `11694065` action=`candidate_set_expected_restore_contract_case` decision=`publish` target=`아카데미에서 살아남기` official_refs=`1` release_candidate_not_approval=`true`
- `11698877` action=`candidate_set_expected_restore_contract_case` decision=`publish` target=`괴담 호텔 탈출기` official_refs=`2` release_candidate_not_approval=`true`
- `11703631` action=`candidate_set_expected_restore_contract_case` decision=`publish` target=`나의 악당들` official_refs=`1` release_candidate_not_approval=`true`
- `11673102` action=`candidate_set_expected_restore_contract_case` decision=`publish` target=`댓글 보는 천재 의사` official_refs=`1` release_candidate_not_approval=`true`
- `11676309` action=`candidate_set_expected_restore_contract_case` decision=`publish` target=`댓글 보는 천재 의사` official_refs=`1` release_candidate_not_approval=`true`

## Gate 해석

- `candidate_set_expected_restore_contract_case`는 source-native 근거와 공식 detail URL을 갖춘 contract case다. 이는 release 후보 표시일 뿐 승인 완료가 아니다.
- `candidate_set_rebuild_required_before_publish`는 현재 후보셋이 source-supported title을 담지 못하므로 publish 금지 상태로 둔다.
- `no_publish_intent_guard_contract_case`는 고전/비작품 intent guard로 같은 표면 웹소설 promotion을 막는다.
- 완료 기준은 계속 `adjusted full375 collateral GO + full_scan 경로 정의`다.
