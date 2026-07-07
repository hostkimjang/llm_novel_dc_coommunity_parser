# loop585_official_support_enrichment_review

Loop582/583의 `official_support_missing_restore_hold_contract_case` 보류 행을 공식 detail URL 근거로 재분류한 리뷰다. 이 산출물은 새 runtime replay가 아니며, enriched dispatch도 기존 shared restore plan을 다시 통과해야 한다.

## 요약

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- source_official_missing_hold_rows: `5`
- reviewed_rows: `5`
- validation_issue_count: `0`
- state_counts: `{'official_detail_found_target_title_mismatch': 1, 'official_detail_exact_title_found': 3, 'ebook_or_classic_policy_review_required': 1}`
- review_action_counts: `{'canonical_title_rewrite_review_required': 1, 'append_official_ref_to_restore_dispatch': 3, 'non_webnovel_ebook_policy_hold': 1}`
- enriched_restore_dispatch_rows: `3`
- hold_rows: `2`
- runtime_replay_allowed_rows: `0`
- full375 collateral: `NO-GO`

## Rows

- `11665124` state=`official_detail_found_target_title_mismatch` action=`canonical_title_rewrite_review_required` target=`화산파(화산귀환)` official=`화산귀환` url=`https://series.naver.com/novel/detail.series?productNo=4130558` dispatch=`False`
- `11710049` state=`official_detail_exact_title_found` action=`append_official_ref_to_restore_dispatch` target=`[림월드]변방계에서 회귀자로 살아남기` official=`[림월드]변방계에서 회귀자로 살아남기` url=`https://novelpia.com/novel/382324` dispatch=`True`
- `11682775` state=`official_detail_exact_title_found` action=`append_official_ref_to_restore_dispatch` target=`여자가 되어서라도 복수한다` official=`여자가 되어서라도 복수한다` url=`https://novelpia.com/novel/403405` dispatch=`True`
- `11700500` state=`official_detail_exact_title_found` action=`append_official_ref_to_restore_dispatch` target=`전지적 1인칭 시점` official=`전지적 1인칭 시점` url=`https://novelpia.com/novel/49942` dispatch=`True`
- `11698870` state=`ebook_or_classic_policy_review_required` action=`non_webnovel_ebook_policy_hold` target=`인간실격` official=`인간실격` url=`https://series.naver.com/ebook/detail.series?productNo=8927664` dispatch=`False`

## Gate 해석

정확 공식 detail URL이 확인된 `3`건만 enriched dispatch로 넘긴다. 나머지 `2`건은 canonical rewrite 또는 eBook/classic 정책 검토가 필요하므로 publish 후보로 세지 않는다. 다음 단계는 enriched dispatch를 shared restore contract plan에 다시 통과시키고 projection-only full375 collateral을 재확인하는 것이다.
