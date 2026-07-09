# loop630_true_triage64_shared_gate_contract_plan

Post-verdict contract queue를 shared `can_publish_title` gate 입력으로 변환한 계약 계획이다. SG projection과 C1/C2는 contract test 입력이고, C3는 stronger evidence 확인 전까지 release를 열지 않는다. 이 산출물은 runtime replay 허가가 아니다.

## 요약

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- contract_plan_rows: `13`
- validation_issue_count: `0`
- contract_action_counts: `{'expected_title_restore_contract_case': 13}`
- promotion_decision_status_counts: `{'publish': 13}`
- runtime_replay_allowed_rows: `0`
- full375 collateral: `NO-GO`

## 계약 액션

- `expected_title_restore_contract_case`: `13`

## 행별 계획

- `11660271` lane=`SG_shared_gate_publish_release_candidate` action=`expected_title_restore_contract_case` decision=`publish` target=`월야의 여인들` block=`None`
- `11660273` lane=`SG_shared_gate_publish_release_candidate` action=`expected_title_restore_contract_case` decision=`publish` target=`마도서를 줍다 마법사가 되다` block=`None`
- `11663557` lane=`SG_shared_gate_publish_release_candidate` action=`expected_title_restore_contract_case` decision=`publish` target=`퇴마록` block=`None`
- `11668325` lane=`SG_shared_gate_publish_release_candidate` action=`expected_title_restore_contract_case` decision=`publish` target=`Fate/stay night` block=`None`
- `11677926` lane=`SG_shared_gate_publish_release_candidate` action=`expected_title_restore_contract_case` decision=`publish` target=`재앙급 막내 공자의 회귀` block=`None`
- `11698910` lane=`SG_shared_gate_publish_release_candidate` action=`expected_title_restore_contract_case` decision=`publish` target=`판초우의의 마법사` block=`None`
- `11706871` lane=`SG_shared_gate_publish_release_candidate` action=`expected_title_restore_contract_case` decision=`publish` target=`파우스트` block=`None`
- `11710049` lane=`SG_shared_gate_publish_release_candidate` action=`expected_title_restore_contract_case` decision=`publish` target=`[림월드]변방계에서 회귀자로 살아남기` block=`None`
- `11714887` lane=`SG_shared_gate_publish_release_candidate` action=`expected_title_restore_contract_case` decision=`publish` target=`도굴왕 1 |` block=`None`
- `11666741` lane=`SG_shared_gate_publish_release_candidate` action=`expected_title_restore_contract_case` decision=`publish` target=`별을 품은 소드마스터` block=`None`
- `11679537` lane=`SG_shared_gate_publish_release_candidate` action=`expected_title_restore_contract_case` decision=`publish` target=`죽었다 깨어도 수선` block=`None`
- `11665121` lane=`SG_shared_gate_publish_release_candidate` action=`expected_title_restore_contract_case` decision=`publish` target=`후회 안 하는 프로듀서` block=`None`
- `11673077` lane=`SG_shared_gate_publish_release_candidate` action=`expected_title_restore_contract_case` decision=`publish` target=`판초우의의 마법사` block=`None`

## Gate 해석

Post-verdict C1 또는 SG shared-gate projection 일부는 expected title restore contract case로 정리되지만 이는 contract test 입력일 뿐이다. C2는 canonical variant policy가 닫히기 전까지 candidate-only로 유지하고, C3는 stronger evidence/native-web 확인 전까지 hard hold로 둔다. 따라서 goal은 `ACTIVE / NOT_COMPLETE`이고 완료 기준은 계속 `full375 collateral GO + full_scan 경로 정의`다.
