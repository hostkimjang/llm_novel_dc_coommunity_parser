# loop548_b1_post_verdict_promotion_gate_contract_plan

Post-verdict contract queue를 shared `can_publish_title` gate 입력으로 변환한 계약 계획이다. 이 산출물은 runtime replay 허가가 아니며, C1/C2 contract test와 C3 stronger evidence 확인 전에는 release를 열지 않는다.

## 요약

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- contract_plan_rows: `14`
- validation_issue_count: `0`
- contract_action_counts: `{'candidate_scrub_no_publish_contract_case': 3, 'expected_title_restore_contract_case': 3, 'stronger_evidence_hard_hold_contract_case': 3, 'canonical_variant_policy_hold_contract_case': 5}`
- promotion_decision_status_counts: `{'candidate_only': 11, 'publish': 3}`
- runtime_replay_allowed_rows: `0`
- full375 collateral: `NO-GO`

## 계약 액션

- `candidate_scrub_no_publish_contract_case`: `3`
- `canonical_variant_policy_hold_contract_case`: `5`
- `expected_title_restore_contract_case`: `3`
- `stronger_evidence_hard_hold_contract_case`: `3`

## 행별 계획

- `11665124` lane=`C1_expected_restore_or_candidate_scrub_contract` action=`candidate_scrub_no_publish_contract_case` decision=`candidate_only` target=`화산파(화산귀환)` block=`search_blind_condition`
- `11668325` lane=`C1_expected_restore_or_candidate_scrub_contract` action=`expected_title_restore_contract_case` decision=`publish` target=`Fate/stay night` block=`None`
- `11690841` lane=`C1_expected_restore_or_candidate_scrub_contract` action=`candidate_scrub_no_publish_contract_case` decision=`candidate_only` target=`블루 아카이브` block=`search_evidence_missing`
- `11697242` lane=`C3_stronger_evidence_or_native_web_hold` action=`stronger_evidence_hard_hold_contract_case` decision=`candidate_only` target=`유희왕` block=`stronger_evidence_required`
- `11697256` lane=`C2_canonical_variant_policy_contract` action=`canonical_variant_policy_hold_contract_case` decision=`candidate_only` target=`황제의 딸로 환생했습니다` block=`canonical_variant_policy_pending`
- `11710021` lane=`C2_canonical_variant_policy_contract` action=`canonical_variant_policy_hold_contract_case` decision=`candidate_only` target=`무한의 마법사` block=`canonical_variant_policy_pending`
- `11710049` lane=`C1_expected_restore_or_candidate_scrub_contract` action=`expected_title_restore_contract_case` decision=`publish` target=`[림월드]변방계에서 회귀자로 살아남기` block=`None`
- `11714887` lane=`C2_canonical_variant_policy_contract` action=`canonical_variant_policy_hold_contract_case` decision=`candidate_only` target=`도굴왕` block=`canonical_variant_policy_pending`
- `11718099` lane=`C1_expected_restore_or_candidate_scrub_contract` action=`expected_title_restore_contract_case` decision=`publish` target=`빌어먹을 환생` block=`None`
- `11718114` lane=`C3_stronger_evidence_or_native_web_hold` action=`stronger_evidence_hard_hold_contract_case` decision=`candidate_only` target=`설정값 딸깍으로 판타지 시스템 정상화` block=`stronger_evidence_required`
- `11682767` lane=`C2_canonical_variant_policy_contract` action=`canonical_variant_policy_hold_contract_case` decision=`candidate_only` target=`묵향` block=`canonical_variant_policy_pending`
- `11692436` lane=`C3_stronger_evidence_or_native_web_hold` action=`stronger_evidence_hard_hold_contract_case` decision=`candidate_only` target=`퍼펙트 메이지` block=`stronger_evidence_required`
- `11698859` lane=`C2_canonical_variant_policy_contract` action=`canonical_variant_policy_hold_contract_case` decision=`candidate_only` target=`귤부인 대롱대롱` block=`canonical_variant_policy_pending`
- `11710046` lane=`C1_expected_restore_or_candidate_scrub_contract` action=`candidate_scrub_no_publish_contract_case` decision=`candidate_only` target=`샷건 치는 병약 천사님` block=`search_blind_condition`

## Gate 해석

Post-verdict C1 일부는 expected title restore contract case로 정리되지만 이는 contract test 입력일 뿐이다. C2는 canonical variant policy가 닫히기 전까지 candidate-only로 유지하고, C3는 stronger evidence/native-web 확인 전까지 hard hold로 둔다. 따라서 goal은 `ACTIVE / NOT_COMPLETE`이고 완료 기준은 계속 `full375 collateral GO + full_scan 경로 정의`다.
