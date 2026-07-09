# loop638_candidate_set6_official_support_enrichment_review

`loop636_candidate_set6_contract_plan`의 official-support missing hold 행을 공식 detail URL 근거로 재분류한 리뷰다. 이 산출물은 새 runtime replay가 아니며, enriched dispatch도 해당 lane의 contract plan을 다시 통과해야 한다.

## 요약

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- source_official_missing_hold_rows: `6`
- reviewed_rows: `6`
- validation_issue_count: `0`
- state_counts: `{'official_detail_exact_title_found': 4, 'official_detail_found_target_title_mismatch': 2}`
- review_action_counts: `{'append_official_ref_to_restore_dispatch': 4, 'rewrite_target_to_official_restore_dispatch': 2}`
- enriched_restore_dispatch_rows: `6`
- exact_official_enriched_dispatch_rows: `4`
- canonical_rewrite_dispatch_rows: `2`
- hold_rows: `0`
- runtime_replay_allowed_rows: `0`
- full375 collateral: `NO-GO`

## Rows

- `11660257` state=`official_detail_exact_title_found` action=`append_official_ref_to_restore_dispatch` target=`암흑가 보스요? 제가요?` official=`암흑가 보스요? 제가요?` url=`https://novelpia.com/novel/384111` dispatch=`True`
- `11673102` state=`official_detail_found_target_title_mismatch` action=`rewrite_target_to_official_restore_dispatch` target=`갤질하는 천재 의사` official=`댓글 보는 천재 의사` url=`https://novelpia.com/novel/372180` dispatch=`True`
- `11676309` state=`official_detail_found_target_title_mismatch` action=`rewrite_target_to_official_restore_dispatch` target=`갤질하는 천재 의사` official=`댓글 보는 천재 의사` url=`https://novelpia.com/novel/372180` dispatch=`True`
- `11694065` state=`official_detail_exact_title_found` action=`append_official_ref_to_restore_dispatch` target=`아카데미에서 살아남기` official=`아카데미에서 살아남기` url=`https://series.naver.com/novel/detail.series?productNo=6484753` dispatch=`True`
- `11698877` state=`official_detail_exact_title_found` action=`append_official_ref_to_restore_dispatch` target=`괴담 호텔 탈출기` official=`괴담 호텔 탈출기` url=`https://novelpia.com/novel/102155` dispatch=`True`
- `11703631` state=`official_detail_exact_title_found` action=`append_official_ref_to_restore_dispatch` target=`나의 악당들` official=`나의 악당들` url=`https://page.kakao.com/content/55826557?tab_type=comment` dispatch=`True`

## Gate 해석

정확 공식 detail URL 또는 명시적 canonical rewrite 계약이 확인된 `6`건만 enriched dispatch로 넘긴다. 나머지 `0`건은 canonical rewrite 또는 eBook/classic 정책 검토가 필요하므로 publish 후보로 세지 않는다. 다음 단계는 enriched dispatch를 해당 lane의 contract plan에 다시 통과시키고 projection-only full375 collateral을 재확인하는 것이다.
