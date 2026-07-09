# loop637_11682768_canonical_cleanup_contract_plan

Title mismatch source-native verdict를 shared `can_publish_title` gate 입력으로 변환한 계약 계획이다. `ACCEPT`도 expected audit update/exclusion 계약일 뿐 runtime approval이 아니다.

## 요약

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- contract_plan_rows: `1`
- validation_issue_count: `0`
- review_label_counts: `{'REPROCESS': 1}`
- contract_action_counts: `{'canonical_cleanup_or_url_correction_contract_case': 1}`
- promotion_decision_status_counts: `{'candidate_only': 1}`
- runtime_replay_allowed_rows: `0`
- full375 collateral: `NO-GO`

## 행별 계획

- `11682768` label=`REPROCESS` lane=`T3_canonical_cleanup_or_url_correction_contract` action=`canonical_cleanup_or_url_correction_contract_case` decision=`candidate_only` target=`마법소녀ㄴ은 은퇴하고 싶다` block=`canonical_cleanup_required`

## Gate 해석

`ACCEPT`는 expected baseline/update 계약으로만 쓰고, `HOLD`는 native-web disambiguation 전까지 hard hold다. `REPROCESS`는 canonical cleanup 또는 URL correction 계약이 닫히기 전까지 runtime replay를 열지 않는다. 따라서 full375 collateral은 계속 `NO-GO`이고 goal은 `ACTIVE / NOT_COMPLETE`다.
