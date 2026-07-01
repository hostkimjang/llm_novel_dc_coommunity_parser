# Loop254 Preflight Report - platform-meta image hard-hold

## 요약

- 상태: goal `ACTIVE / NOT_COMPLETE`.
- 목적: Loop253에서 `11658668`이 semantic no-work 상태인데도 `batch_memory_exact_alias_rescued` 경로로 다시 publish된 우회를 next canary 전에 코드 계약으로 막는다.
- 동일 38-row parent packet은 재실행하지 않았다.

## 근거

- Loop253 run id: `20260702_041616_811347`
- 결과: `out\regression_safe_grounding_20260626_000008_928006_loop01\canary\loop253_p0_representative_7_after_platform_meta_hold_result.json`
- Manifest: `out\regression_safe_grounding_20260626_000008_928006_loop01\canary\loop253_p0_representative_7_after_platform_meta_hold_result_manifest.json`
- Runtime: completed/flushed/pending/failed `7/7/0/0`, VLM/OCR `READY`
- 실패 의미: runtime은 끝났지만 `11658668` public title `전 버튜버가 하고 싶은데요`가 `promotion_gate_state.source=batch_memory_exact_alias_rescued`, `title_resolution_state=context_only`, `work_resolution=unresolved` 상태에서 publish됐다.

## 변경

- `src\llm_batch\rules.py`: platform-meta feature term에 `수정`, `삭제`, `내리`, `내려`를 추가했다.
- `src\llm_batch\agentic_pipeline.py`: `_platform_meta_image_title_requires_hold(...)`를 추가했다.
- shared `_post_discusses_work_as_work(...)`와 no-work direct-anchor rescue가 non-promotable platform-meta image title을 current-work로 승격하지 못하게 했다.
- semantic no-work gate에는 `platform_meta_image_title_hard_hold`와 `scope_context_only` evidence를 남긴다.

## 검증

- py_compile: PASS
- `tests.test_title_lead_search_inferred_guard`: `179` tests OK
- `tests.test_expert_main_comment_metadata`: `34` tests OK
- `git diff --check`: PASS

## 게이트

- Preflight checkpoint only.
- Next step: 커밋 뒤 same 7-row packet canary를 실행한다.
- `semantic_quality=REVIEW-LOCKED`
- `full_scan_approval=false`
- full375 previous `NO-GO`
