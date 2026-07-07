# loop596_residual46_combined_projection_application

기존 projection application에 추가 shared-gate publish-class 적용 행을 병합한 projection-only 산출물이다.

## 요약

- applied_publish_contract_rows: `11`
- addition_projection_id: `loop596_remaining15_shared_gate_projection_application`
- addition_applied_rows: `2`
- applied_restore_rows: `10`
- applied_canonical_cleanup_rows: `1`
- skipped_contract_action_counts: `{'candidate_set_rebuild_required_before_publish': 13, 'native_web_disambiguation_hold_contract_case': 1, 'non_webnovel_ebook_policy_hold_contract_case': 1, 'candidate_scrub_no_publish_contract_case': 1}`
- runtime_replay_allowed_rows: `0`
- full375 collateral: `NO-GO`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`

## 추가 적용 행

- `11698871` action=`expected_title_restore_contract_case` target=`Re : 제로부터 시작하는 이세계 생활` url=`https://page.kakao.com/content/48677416`
- `11706844` action=`expected_title_restore_contract_case` target=`호랑이 사냥꾼` url=`https://m.munpia.com/novel/detail/522066`

## Gate 해석

적용 행은 shared `PromotionDecision`/`publish_contract_trace`/`publish_ledger` 동기화 증거다. 새 runtime replay나 full_scan approval이 아니다.
