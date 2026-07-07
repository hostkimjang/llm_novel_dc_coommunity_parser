# loop555_ordinary_restore_projection_contract

Post-verdict publish-class contract를 current projection row에 적용한 projection-only 산출물이다. 새 runtime replay가 아니며, release candidate가 생겨도 full375 collateral GO 전에는 approval 근거가 아니다.

## 요약

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- projection_rows: `375`
- applied_publish_contract_rows: `17`
- applied_restore_rows: `17`
- applied_expected_audit_update_rows: `0`
- applied_canonical_cleanup_rows: `0`
- validation_issue_count: `0`
- runtime_replay_allowed_rows: `0`
- full375 collateral: `NO-GO`

## 적용 행

- `11660273` action=`expected_title_restore_contract_case` target=`마도서를 줍다 마법사가 되다` superseded=`그리즐리 그랑`
- `11663511` action=`expected_title_restore_contract_case` target=`부캐 키우는 황태자님` superseded=`None`
- `11663535` action=`expected_title_restore_contract_case` target=`퇴마록` superseded=`퇴마록`
- `11668300` action=`expected_title_restore_contract_case` target=`즉사기 들고 게임 속 으로` superseded=`즉사기 인 줄 알았는데 지옥이었다`
- `11673077` action=`expected_title_restore_contract_case` target=`판초우의의 마법사` superseded=`None`
- `11673102` action=`expected_title_restore_contract_case` target=`갤질하는 천재 의사` superseded=`댓글 보는 천재 의사`
- `11677915` action=`expected_title_restore_contract_case` target=`전지적 독자 시점` superseded=`None`
- `11681172` action=`expected_title_restore_contract_case` target=`헌터갤러리의 국가권력급 기계공주` superseded=`None`
- `11689292` action=`expected_title_restore_contract_case` target=`최악의 파트너` superseded=`[원신] 최악의 파트너`
- `11694019` action=`expected_title_restore_contract_case` target=`혼후 순결` superseded=`이세계에서 사이비로 살아남기`
- `11694063` action=`expected_title_restore_contract_case` target=`빙의한 신의 아이, 엘리시아` superseded=`None`
- `11694068` action=`expected_title_restore_contract_case` target=`트와일라잇` superseded=`트와일라잇 시리즈`
- `11702094` action=`expected_title_restore_contract_case` target=`#더블오` superseded=`댓글창이 내 흑막 연기를 너무 좋아한다`
- `11705230` action=`expected_title_restore_contract_case` target=`월야환담` superseded=`None`
- `11705251` action=`expected_title_restore_contract_case` target=`월야환담 창월야` superseded=`None`
- `11706842` action=`expected_title_restore_contract_case` target=`삼국지 마대 가 되었다` superseded=`대마법사였던것은 다시 대마법사를 꿈꾼다`
- `11718110` action=`expected_title_restore_contract_case` target=`지구온라인에서 쌀먹합니다` superseded=`None`

## Gate 해석

publish-class contract 적용 행 `17`건은 shared PromotionDecision을 projection identity, publish_contract_trace, publish_ledger에 동기화했다. 이 결과는 release gate contract를 닫는 projection 증거이며 runtime replay 또는 full_scan approval이 아니다.
