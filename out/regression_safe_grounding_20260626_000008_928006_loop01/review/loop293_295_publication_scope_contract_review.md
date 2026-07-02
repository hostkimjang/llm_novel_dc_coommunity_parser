# Loop293-295 publication scope 계약 점검

## 요약

- Loop293 targeted replay는 2/2 완료됐지만 두 행 모두 `SEARCH_DEGRADED`라 approval 근거가 아니다.
- `11698890`은 `댓글창의 천재 마법사`로 targeted resolved 됐으나 `search-blind conditional`이다.
- `11716448`은 `아카데미 생존 갤러리` 후보와 URL을 보존했지만, pre-patch runtime에서는 `context_only`가 먼저 잡혀 `scope_not_current_work`로 남았다.
- Loop294 safe-loss flip probe는 중복 post_id가 3개로 collapse되어 `N>=5` 증거가 아니므로 무효 중단했다.
- Loop295 post-patch smoke는 search degraded와 장시간 fallback/LLM 경로로 `completed=0`에서 중단했다. runtime verdict는 없다.
- 코드 계약은 `current_work` scope를 `context_only` 이미지 보류보다 먼저 평가하도록 고쳤고, noise/off-topic hard negative는 유지했다.

## 근거 경로

- Loop293 manifest: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop293_known_alias_guard_2_result_manifest.json`
- Loop293 checkpoint: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop293_known_alias_guard_2_result_checkpoint.jsonl`
- Loop294 invalid manifest: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop294_safe_loss_flip_probe_n5_current_head_result_manifest.json`
- Loop295 aborted manifest: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop295_known_alias_guard_2_after_scope_order_result_manifest.json`
- Data Analytics summary: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop293_295_publication_scope_data_analytics_artifact.json`

## 정량 표

| 항목 | input | completed | flushed | gate | 의미 |
| --- | ---: | ---: | ---: | --- | --- |
| Loop293 known-alias targeted | 2 | 2 | 2 | `REVIEW_LOCKED` | 완료됐지만 search degraded라 승인 아님 |
| Loop294 flip probe | 3 | 0 | 0 | `INVALID_ABORTED` | N>=5 반복이 post_id de-dupe로 3행 collapse |
| Loop295 scope-order smoke | 2 | 0 | 0 | `ABORTED_INCOMPLETE` | search degraded와 긴 fallback 경로로 runtime verdict 없음 |
| Loop288 full375 background | 375 | 45 | 36 | `BACKGROUND_RUNNING` | `large_run_complete=false` |
| Loop288 bounded1200 background | 1200 | 73 | 40 | `BACKGROUND_RUNNING` | `large_run_complete=false` |
| Loop288 golden18 background | 18 | 13 | 12 | `BACKGROUND_RUNNING` | `large_run_complete=false`, small-run light mode |

## 코드 계약

- `expert_main.py`에서 blocked candidate scope 추론 순서를 바꿨다.
- 공식 search evidence와 title/body/comments/search context가 있는 경우 `current_work`를 먼저 평가한다.
- `discussion_type in {noise, other}` 또는 `topicality in {unrelated, off_topic}`이면 `current_work` scope를 만들지 않는다.
- `tests/test_expert_main_comment_metadata.py`에 `11716448`형 회귀 테스트를 추가했다.

## 검증

- `py_compile expert_main.py`: PASS
- `tests.test_expert_main_comment_metadata`: 37 tests PASS
- `tests.test_title_lead_search_inferred_guard`: 180 tests PASS
- `git diff --check`: PASS, LF/CRLF 경고만 있음
- Data Analytics `validate_artifact`: PASS
- Data Analytics `render_artifact`: PASS

## 게이트

- run integrity: `TARGETED_LOOP293_COMPLETE / LOOP294_INVALID / LOOP295_ABORTED / BACKGROUND_RUNNING`
- targeted canary status: `REVIEW_LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- 이번 회차 판정: `REVIEW`

## 다음 작업

- 진짜 `N>=5` flip probe는 독립 프로세스 반복 또는 probe-only de-dupe 해제 wrapper가 필요하다.
- full375, bounded1200, golden18은 `large_run_complete=true` 전까지 approval 근거로 쓰지 않는다.
- `11716448` runtime smoke는 search degraded 복구 뒤 재실행해야 한다.
