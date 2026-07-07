# loop588_native_policy_preflight_review

Loop582/587의 native-web/image 및 no-publish guard 사전 검토 행을 공식/native 근거로 재분류한 리뷰다. 이 산출물은 새 runtime replay가 아니며, restore dispatch도 shared promotion gate를 다시 통과해야 한다.

## 요약

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- source_preflight_rows: `2`
- reviewed_rows: `2`
- validation_issue_count: `0`
- lane_counts: `{'native_web_image_evidence_review': 1, 'no_publish_guard_review': 1}`
- state_counts: `{'native_web_exact_title_not_found_context_only': 1, 'official_detail_and_store_context_confirmed': 1}`
- review_action_counts: `{'native_web_context_only_hold': 1, 'native_policy_restore_dispatch': 1}`
- restore_dispatch_rows: `1`
- hold_rows: `1`
- runtime_replay_allowed_rows: `0`
- full375 collateral: `NO-GO`

## Rows

- `11698859` state=`native_web_exact_title_not_found_context_only` action=`native_web_context_only_hold` target=`귤부인 대롱대롱` official=`친아들이 내게 집착한다` url=`https://novelpia.com/novel/197558` dispatch=`False`
- `11700483` state=`official_detail_and_store_context_confirmed` action=`native_policy_restore_dispatch` target=`니들 생각 다 들린다` official=`니들 생각 다 들린다` url=`https://novelpia.com/novel/384318` dispatch=`True`

## Gate 해석

공식 detail과 작품별 상품/이모티콘 맥락이 함께 확인된 `1`건만 restore dispatch로 넘긴다. 나머지 `1`건은 exact official title 또는 native-web disambiguation이 부족하므로 publish 후보로 세지 않는다. 다음 단계는 dispatch를 shared restore contract plan에 통과시키고 projection-only full375 collateral을 재확인하는 것이다.
