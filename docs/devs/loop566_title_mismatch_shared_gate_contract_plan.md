# loop566_title_mismatch_shared_gate_contract_plan

Title mismatch source-native verdict를 shared `can_publish_title` gate 입력으로 변환한 계약 계획이다. `ACCEPT`도 expected audit update/exclusion 계약일 뿐 runtime approval이 아니다.

## 요약

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- contract_plan_rows: `2`
- validation_issue_count: `0`
- review_label_counts: `{'ACCEPT': 1, 'REPROCESS': 1}`
- contract_action_counts: `{'expected_audit_update_exclusion_contract_case': 1, 'canonical_cleanup_or_url_correction_contract_case': 1}`
- promotion_decision_status_counts: `{'publish': 1, 'candidate_only': 1}`
- runtime_replay_allowed_rows: `0`
- full375 collateral: `NO-GO`

## 행별 계획

- `11665121` label=`ACCEPT` lane=`T1_expected_audit_update_or_blind_acceptance_contract` action=`expected_audit_update_exclusion_contract_case` decision=`publish` target=`후회 안 하는 프로듀서 [독점]` block=`None`
- `11673080` label=`REPROCESS` lane=`T3_canonical_cleanup_or_url_correction_contract` action=`canonical_cleanup_or_url_correction_contract_case` decision=`candidate_only` target=`갤질하는 천재 의사` block=`canonical_cleanup_required`

## Gate 해석

`ACCEPT`는 expected baseline/update 계약으로만 쓰고, `HOLD`는 native-web disambiguation 전까지 hard hold다. `REPROCESS`는 canonical cleanup 또는 URL correction 계약이 닫히기 전까지 runtime replay를 열지 않는다. 따라서 full375 collateral은 계속 `NO-GO`이고 goal은 `ACTIVE / NOT_COMPLETE`다.
