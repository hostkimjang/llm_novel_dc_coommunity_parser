# loop586_canonical_title_rewrite_review

Loop582/583의 `official_support_missing_restore_hold_contract_case` 보류 행을 공식 detail URL 근거로 재분류한 리뷰다. 이 산출물은 새 runtime replay가 아니며, enriched dispatch도 기존 shared restore plan을 다시 통과해야 한다.

## 요약

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- source_official_missing_hold_rows: `2`
- reviewed_rows: `2`
- validation_issue_count: `0`
- state_counts: `{'official_detail_found_target_title_mismatch': 1, 'ebook_or_classic_policy_review_required': 1}`
- review_action_counts: `{'rewrite_target_to_official_restore_dispatch': 1, 'non_webnovel_ebook_policy_hold': 1}`
- enriched_restore_dispatch_rows: `1`
- exact_official_enriched_dispatch_rows: `0`
- canonical_rewrite_dispatch_rows: `1`
- hold_rows: `1`
- runtime_replay_allowed_rows: `0`
- full375 collateral: `NO-GO`

## Rows

- `11665124` state=`official_detail_found_target_title_mismatch` action=`rewrite_target_to_official_restore_dispatch` target=`화산파(화산귀환)` official=`화산귀환` url=`https://series.naver.com/novel/detail.series?productNo=4130558` dispatch=`True`
- `11698870` state=`ebook_or_classic_policy_review_required` action=`non_webnovel_ebook_policy_hold` target=`인간실격` official=`인간실격` url=`https://series.naver.com/ebook/detail.series?productNo=8927664` dispatch=`False`

## Gate 해석

정확 공식 detail URL 또는 명시적 canonical rewrite 계약이 확인된 `1`건만 enriched dispatch로 넘긴다. 나머지 `1`건은 canonical rewrite 또는 eBook/classic 정책 검토가 필요하므로 publish 후보로 세지 않는다. 다음 단계는 enriched dispatch를 shared restore contract plan에 다시 통과시키고 projection-only full375 collateral을 재확인하는 것이다.
