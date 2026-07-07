# loop566_b1_post_verdict_promotion_gate_contract_plan

Post-verdict contract queue를 shared `can_publish_title` gate 입력으로 변환한 계약 계획이다. 이 산출물은 runtime replay 허가가 아니며, C1/C2 contract test와 C3 stronger evidence 확인 전에는 release를 열지 않는다.

## 요약

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- contract_plan_rows: `15`
- validation_issue_count: `0`
- contract_action_counts: `{'expected_title_restore_contract_case': 6, 'candidate_scrub_no_publish_contract_case': 6, 'stronger_evidence_hard_hold_contract_case': 3}`
- promotion_decision_status_counts: `{'publish': 6, 'candidate_only': 9}`
- runtime_replay_allowed_rows: `0`
- full375 collateral: `NO-GO`

## 계약 액션

- `candidate_scrub_no_publish_contract_case`: `6`
- `expected_title_restore_contract_case`: `6`
- `stronger_evidence_hard_hold_contract_case`: `3`

## 행별 계획

- `11663557` lane=`C1_expected_restore_or_candidate_scrub_contract` action=`expected_title_restore_contract_case` decision=`publish` target=`퇴마록` block=`None`
- `11666713` lane=`C1_expected_restore_or_candidate_scrub_contract` action=`candidate_scrub_no_publish_contract_case` decision=`candidate_only` target=`21세기 무림세가` block=`search_evidence_missing`
- `11666741` lane=`C1_expected_restore_or_candidate_scrub_contract` action=`candidate_scrub_no_publish_contract_case` decision=`candidate_only` target=`별을 품은 소드마스터` block=`search_evidence_missing`
- `11668325` lane=`C1_expected_restore_or_candidate_scrub_contract` action=`expected_title_restore_contract_case` decision=`publish` target=`Fate/stay night` block=`None`
- `11669913` lane=`C1_expected_restore_or_candidate_scrub_contract` action=`expected_title_restore_contract_case` decision=`publish` target=`하룬` block=`None`
- `11669926` lane=`C1_expected_restore_or_candidate_scrub_contract` action=`candidate_scrub_no_publish_contract_case` decision=`candidate_only` target=`싸울아비 룬` block=`search_blind_condition`
- `11677924` lane=`C1_expected_restore_or_candidate_scrub_contract` action=`expected_title_restore_contract_case` decision=`publish` target=`고결에 오만이 깃들 때` block=`None`
- `11681159` lane=`C1_expected_restore_or_candidate_scrub_contract` action=`expected_title_restore_contract_case` decision=`publish` target=`괴담에 휘말렸다` block=`None`
- `11692436` lane=`C3_stronger_evidence_or_native_web_hold` action=`stronger_evidence_hard_hold_contract_case` decision=`candidate_only` target=`퍼펙트 메이지` block=`stronger_evidence_required`
- `11697242` lane=`C3_stronger_evidence_or_native_web_hold` action=`stronger_evidence_hard_hold_contract_case` decision=`candidate_only` target=`유희왕` block=`stronger_evidence_required`
- `11697256` lane=`C1_expected_restore_or_candidate_scrub_contract` action=`candidate_scrub_no_publish_contract_case` decision=`candidate_only` target=`황제의 딸로 환생했다` block=`search_blind_condition`
- `11700483` lane=`C1_expected_restore_or_candidate_scrub_contract` action=`candidate_scrub_no_publish_contract_case` decision=`candidate_only` target=`니들 생각 다 들린다` block=`search_evidence_missing`
- `11706831` lane=`C1_expected_restore_or_candidate_scrub_contract` action=`candidate_scrub_no_publish_contract_case` decision=`candidate_only` target=`소설 속 빌런은 아카데미 차석으로 살아간다` block=`search_blind_condition`
- `11714887` lane=`C1_expected_restore_or_candidate_scrub_contract` action=`expected_title_restore_contract_case` decision=`publish` target=`도굴왕 1 |` block=`None`
- `11718114` lane=`C3_stronger_evidence_or_native_web_hold` action=`stronger_evidence_hard_hold_contract_case` decision=`candidate_only` target=`설정값 딸깍으로 판타지 시스템 정상화` block=`stronger_evidence_required`

## Gate 해석

Post-verdict C1 일부는 expected title restore contract case로 정리되지만 이는 contract test 입력일 뿐이다. C2는 canonical variant policy가 닫히기 전까지 candidate-only로 유지하고, C3는 stronger evidence/native-web 확인 전까지 hard hold로 둔다. 따라서 goal은 `ACTIVE / NOT_COMPLETE`이고 완료 기준은 계속 `full375 collateral GO + full_scan 경로 정의`다.
