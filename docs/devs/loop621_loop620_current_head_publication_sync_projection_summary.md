# Loop621 Loop620 publication sync projection

- 성격: runtime replay가 아니라 current HEAD final publication sync projection이다.
- source result: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop620_full375_stream_guard_after_loop619_abort_result.json`
- projection result: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop621_loop620_current_head_publication_sync_projection_result.json`
- rows: `375`
- changed rows: `232`
- changed post_ids 전체 목록은 `docs/devs/loop621_loop620_current_head_publication_sync_projection_summary.json`에 보존했다.

## 11677957 결과

- public official title/url: `null / null`
- candidate preservation: `페도부`
- candidate_ledger_status: `promotion_blocked`
- promotion_decision: `candidate_only`, `publish_allowed=false`, `candidate_preserved=true`
- pre_gate_candidate: `페도부`, URL `null`, source `decoder_exact_post_title_surface_resolved`
- publish_ledger.candidate_preservation: `페도부`, URL `null`

## Gate

- publication contract projected audit: `GO / violation 0`
- runtime replay: `NOT_RUN`
- full375 collateral approval: `NO-GO` 유지
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
