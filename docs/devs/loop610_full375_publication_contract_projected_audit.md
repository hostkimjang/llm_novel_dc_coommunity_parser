# Loop610 full375 publication contract projected audit

Loop610은 current code `_sync_final_publication_ledger_contract`를 Loop609 full375 rows에 in-memory 적용해 publication contract blocker가 닫히는지 확인한 projection audit이다. 새 runtime replay나 full375 approval이 아니다.

## Publication contract

- source result: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop609_full375_after_loop608_search_nonlight_result.json`
- before gate: `NO-GO`, violation `1`
- after gate: `GO`, violation `0`
- fixed post: `11660277`

## Collateral after projection

- shared posts: `375/375`
- changed rows: `196`
- raw collateral regression: `139`
- status counts: `null_to_resolved 24 / same_title_url_changed 45 / resolved_to_null 89 / resolved_to_different_title 38`
- regression status counts: `null_to_resolved 24 / resolved_to_null 82 / resolved_to_different_title 33`

## 11660277

- before: `아카메디 아카데미 본 사람?` / `https://novelpia.com/novel/22299`
- after: `아카메디 아카데미` / `null`
- collateral status after projection: `same_title_url_changed`
- regression after projection: `false`

## Gate

- publication contract projected gate: `GO`
- runtime replay: `NOT_RUN`
- full375 collateral: `NO-GO / raw 139`
- `semantic_quality=REVIEW-LOCKED`
- `full_scan_approval=false`
