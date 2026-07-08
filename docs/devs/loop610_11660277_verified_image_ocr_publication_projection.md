# Loop610 11660277 verified image/OCR publication projection

Loop610은 Loop609 publication contract violation `11660277`의 exact row에 current code sync를 적용한 targeted projection이다. 새 runtime replay나 full375 approval이 아니다.

## 결과

- source result: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop609_full375_after_loop608_search_nonlight_result.json`
- before gate: `NO-GO`, violation `1`, code `verified_image_ocr_work_title_blocked_by_precision_review`
- after gate: `GO`, violation `0`
- public title: `아카메디 아카데미`
- public url: `null`
- candidate ledger status: `safe_resolved`
- decision: `publish`, publish_allowed `true`
- reason codes: `official_title_exists`, `row_discusses_work_as_work`, `scope_current_work`, `direct_image_work_surface_bridge`, `ocr_catalog_official_title`, `verified_image_ocr_work_title_publication`, `serialized_public_identity_shared_gate_restored`, `serialized_public_identity_published`

## 근거

- image evidence: `promotion_eligible=true`, `title_role=work_title`, `explicit_work_title=아카메디 아카데미`
- preserved official detail candidate: `https://novelpia.com/novel/22299`
- source context: title, body, comments, search, image
- 공식 detail URL 후보는 ledger 후보 보존 근거로 남기고, public identity는 verified image/OCR 표면 제목으로 title-only publish한다.

## Gate

- targeted publication contract projection: `GO`
- runtime replay: `NOT_RUN`
- full375 collateral: `NO-GO / inherited Loop609 raw 139 / adjusted 78 / unreviewed 74`
- `semantic_quality=REVIEW-LOCKED`
- `full_scan_approval=false`
