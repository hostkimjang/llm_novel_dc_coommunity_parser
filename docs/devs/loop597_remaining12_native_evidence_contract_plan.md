# loop597_remaining12_native_evidence_contract_plan

Remaining native-web/image evidence를 shared promotion gate contract plan으로 변환한 산출물이다. 새 runtime replay가 아니며 full375 approval도 아니다.

## 요약

- source_dispatch_id: `loop596_residual46_remaining12_dispatch`
- source_dispatch_rows: `12`
- contract_plan_rows: `8`
- release_candidate_not_approval_rows: `6`
- no_publish_contract_rows: `2`
- hold_rows: `4`
- contract_action_counts: `{'expected_title_restore_contract_case': 6, 'candidate_scrub_no_publish_contract_case': 2}`
- promotion_decision_status_counts: `{'publish': 6, 'reject': 2}`
- validation_issue_count: `0`
- runtime_replay_allowed_rows: `0`
- full375 collateral: `NO-GO`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`

## 계약 행

- `11661856` action=`expected_title_restore_contract_case` decision=`publish` target=`너랑은 절! 대! 안 사갈거니까!` url=`None` lane=`NE_direct_image_work_title_publish_candidate`
- `11665110` action=`expected_title_restore_contract_case` decision=`publish` target=`사이키델리아` url=`https://ridibooks.com/books/297056360` lane=`NE_official_detail_alias_publish_candidate`
- `11666725` action=`expected_title_restore_contract_case` decision=`publish` target=`학대받던 11살 고마가 각성한 이유` url=`None` lane=`NE_direct_image_work_title_publish_candidate`
- `11681178` action=`candidate_scrub_no_publish_contract_case` decision=`reject` target=`None` url=`None` lane=`NE_current_result_no_publish_contract`
- `11685994` action=`expected_title_restore_contract_case` decision=`publish` target=`교황님 아하세요 마왕 들어 가요` url=`None` lane=`NE_direct_image_work_title_publish_candidate`
- `11711632` action=`candidate_scrub_no_publish_contract_case` decision=`reject` target=`None` url=`None` lane=`NE_current_result_no_publish_contract`
- `11694067` action=`expected_title_restore_contract_case` decision=`publish` target=`괴담에 휘말렸다` url=`https://novelpia.com/novel/363195` lane=`NE_official_detail_alias_publish_candidate`
- `11682791` action=`expected_title_restore_contract_case` decision=`publish` target=`시간을 달리는 소설가` url=`https://novel.munpia.com/357213` lane=`NE_direct_image_work_title_publish_candidate`

## Hold 행

- `11687661` state=`ocr_explicit_title_unresolved` type=`meme` reason=`image_or_context_required_for_safe_title`
- `11716480` state=`ocr_explicit_title_unresolved` type=`review` reason=`image_or_context_required_for_safe_title`
- `11718057` state=`resolved` type=`character_talk` reason=`generic_or_author_like_surface_needs_native_confirmation`
- `11671538` state=`unresolved_matchable` type=`character_talk` reason=`character_or_deity_bridge_not_enough_without_verified_work_link`

## Gate 해석

publish 행은 release candidate일 뿐이고 no-publish 행도 full_scan approval이 아니다. 남은 hold 행은 native-web/image evidence review가 필요하다. 완료 기준은 계속 `full375 collateral GO + full_scan path`다.
