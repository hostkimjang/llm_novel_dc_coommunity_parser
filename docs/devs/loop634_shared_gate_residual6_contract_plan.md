# loop634_shared_gate_residual6_contract_plan

Post-verdict contract queue를 shared `can_publish_title` gate 입력으로 변환한 계약 계획이다. SG projection과 C1/C2는 contract test 입력이고, C3는 stronger evidence 확인 전까지 release를 열지 않는다. 이 산출물은 runtime replay 허가가 아니다.

## 요약

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- contract_plan_rows: `6`
- validation_issue_count: `0`
- contract_action_counts: `{'expected_title_restore_contract_case': 6}`
- promotion_decision_status_counts: `{'publish': 6}`
- runtime_replay_allowed_rows: `0`
- full375 collateral: `NO-GO`

## 계약 액션

- `expected_title_restore_contract_case`: `6`

## 행별 계획

- `11660241` lane=`SG_shared_gate_publish_release_candidate` action=`expected_title_restore_contract_case` decision=`publish` target=`이세계 TRPG 게임마스터` block=`None`
- `11660268` lane=`SG_shared_gate_publish_release_candidate` action=`expected_title_restore_contract_case` decision=`publish` target=`■■을 위한 세계는 없다` block=`None`
- `11663511` lane=`SG_shared_gate_publish_release_candidate` action=`expected_title_restore_contract_case` decision=`publish` target=`부캐 키우는 황태자님` block=`None`
- `11676321` lane=`SG_shared_gate_publish_release_candidate` action=`expected_title_restore_contract_case` decision=`publish` target=`마도서를 줍다 마법사가 되다` block=`None`
- `11682767` lane=`SG_shared_gate_publish_release_candidate` action=`expected_title_restore_contract_case` decision=`publish` target=`묵향` block=`None`
- `11708443` lane=`SG_shared_gate_publish_release_candidate` action=`expected_title_restore_contract_case` decision=`publish` target=`괴담에 떨어져도 출근을 해야 하는구나` block=`None`

## Gate 해석

Post-verdict C1 또는 SG shared-gate projection 일부는 expected title restore contract case로 정리되지만 이는 contract test 입력일 뿐이다. C2는 canonical variant policy가 닫히기 전까지 candidate-only로 유지하고, C3는 stronger evidence/native-web 확인 전까지 hard hold로 둔다. 따라서 goal은 `ACTIVE / NOT_COMPLETE`이고 완료 기준은 계속 `adjusted full375 collateral GO + full_scan 경로 정의`다.
