# loop631_loop630_shared_gate_expected_restore_projection_application

Post-verdict publish-class contract를 current projection row에 적용한 projection-only 산출물이다. 새 runtime replay가 아니며, release candidate가 생겨도 full375 collateral GO 전에는 approval 근거가 아니다.

## 요약

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- projection_rows: `375`
- applied_publish_contract_rows: `13`
- applied_restore_rows: `13`
- applied_expected_audit_update_rows: `0`
- applied_canonical_cleanup_rows: `0`
- validation_issue_count: `0`
- runtime_replay_allowed_rows: `0`
- full375 collateral: `NO-GO`

## 적용 행

- `11660271` action=`expected_title_restore_contract_case` target=`월야의 여인들` superseded=`None`
- `11660273` action=`expected_title_restore_contract_case` target=`마도서를 줍다 마법사가 되다` superseded=`None`
- `11663557` action=`expected_title_restore_contract_case` target=`퇴마록` superseded=`None`
- `11668325` action=`expected_title_restore_contract_case` target=`Fate/stay night` superseded=`None`
- `11677926` action=`expected_title_restore_contract_case` target=`재앙급 막내 공자의 회귀` superseded=`None`
- `11698910` action=`expected_title_restore_contract_case` target=`판초우의의 마법사` superseded=`None`
- `11706871` action=`expected_title_restore_contract_case` target=`파우스트` superseded=`None`
- `11710049` action=`expected_title_restore_contract_case` target=`[림월드]변방계에서 회귀자로 살아남기` superseded=`None`
- `11714887` action=`expected_title_restore_contract_case` target=`도굴왕 1 |` superseded=`None`
- `11666741` action=`expected_title_restore_contract_case` target=`별을 품은 소드마스터` superseded=`None`
- `11679537` action=`expected_title_restore_contract_case` target=`죽었다 깨어도 수선` superseded=`None`
- `11665121` action=`expected_title_restore_contract_case` target=`후회 안 하는 프로듀서` superseded=`None`
- `11673077` action=`expected_title_restore_contract_case` target=`판초우의의 마법사` superseded=`None`

## Gate 해석

publish-class contract 적용 행 `13`건은 shared PromotionDecision을 projection identity, publish_contract_trace, publish_ledger에 동기화했다. 이 결과는 release gate contract를 닫는 projection 증거이며 runtime replay 또는 full_scan approval이 아니다.
