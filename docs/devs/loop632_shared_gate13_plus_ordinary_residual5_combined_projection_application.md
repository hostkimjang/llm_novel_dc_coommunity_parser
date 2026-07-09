# loop632_shared_gate13_plus_ordinary_residual5_combined_projection_application

기존 projection application에 추가 shared-gate publish-class 적용 행을 병합한 projection-only 산출물이다.

## 요약

- applied_publish_contract_rows: `17`
- addition_projection_id: `loop632_ordinary_residual5_combined_projection_application`
- addition_applied_rows: `5`
- applied_restore_rows: `13`
- applied_canonical_cleanup_rows: `1`
- skipped_contract_action_counts: `{}`
- runtime_replay_allowed_rows: `0`
- full375 collateral: `NO-GO`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`

## 추가 적용 행

- `11663514` action=`candidate_set_expected_restore_contract_case` target=`마탄 속의 제국` url=`https://novel.munpia.com/486006`
- `11679547` action=`candidate_set_expected_restore_contract_case` target=`도굴왕` url=`https://page.kakao.com/content/65130395`
- `11698865` action=`candidate_set_rebuild_required_before_publish` target=`None` url=`None`
- `11716464` action=`candidate_set_expected_restore_contract_case` target=`슈라라펜란트` url=`https://ridibooks.com/books/875100425`
- `11669907` action=`canonical_cleanup_or_url_correction_contract_case` target=`마법 좋아좋아좋아` url=`https://novelpia.com/novel/326040`

## Gate 해석

적용 행은 shared `PromotionDecision`/`publish_contract_trace`/`publish_ledger` 동기화 증거다. 새 runtime replay나 full_scan approval이 아니다.
