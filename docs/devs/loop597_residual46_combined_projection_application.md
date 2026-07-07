# loop597_residual46_combined_projection_application

기존 projection application에 추가 shared-gate publish-class 적용 행을 병합한 projection-only 산출물이다.

## 요약

- applied_publish_contract_rows: `17`
- addition_projection_id: `loop597_remaining12_native_evidence_projection_application`
- addition_applied_rows: `6`
- applied_restore_rows: `16`
- applied_canonical_cleanup_rows: `1`
- skipped_contract_action_counts: `{'candidate_set_rebuild_required_before_publish': 13, 'native_web_disambiguation_hold_contract_case': 1, 'non_webnovel_ebook_policy_hold_contract_case': 1, 'candidate_scrub_no_publish_contract_case': 3}`
- runtime_replay_allowed_rows: `0`
- full375 collateral: `NO-GO`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`

## 추가 적용 행

- `11661856` action=`expected_title_restore_contract_case` target=`너랑은 절! 대! 안 사갈거니까!` url=`None`
- `11665110` action=`expected_title_restore_contract_case` target=`사이키델리아` url=`https://ridibooks.com/books/297056360`
- `11666725` action=`expected_title_restore_contract_case` target=`학대받던 11살 고마가 각성한 이유` url=`None`
- `11685994` action=`expected_title_restore_contract_case` target=`교황님 아하세요 마왕 들어 가요` url=`None`
- `11694067` action=`expected_title_restore_contract_case` target=`괴담에 휘말렸다` url=`https://novelpia.com/novel/363195`
- `11682791` action=`expected_title_restore_contract_case` target=`시간을 달리는 소설가` url=`https://novel.munpia.com/357213`

## Gate 해석

적용 행은 shared `PromotionDecision`/`publish_contract_trace`/`publish_ledger` 동기화 증거다. 새 runtime replay나 full_scan approval이 아니다.
