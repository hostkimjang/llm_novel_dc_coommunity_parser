# completed779 Hermes Continuous Goal Prompt

이 문서는 completed779 개선을 한 번짜리 loop로 끝내지 않고, 남은 queue가 비거나 명시적으로 HOLD/human_review/quarantine 처리될 때까지 계속 돌리기 위한 copy-paste prompt다. 사용자가 새 Codex goal/thread를 열 때 아래 코드블록 전체를 붙여 넣는다.

## Copy-Paste Prompt

```text
Objective:
completed779 native-web judge 기반 개선을 Hermes Council 방식으로 계속 진행한다. Hermes Loop 17은 Loop 16 queue `0`을 full approval로 보지 않고, fresh/residual/control pool `28`건을 다시 열었다. Loop 17 queue는 `out/completed779_improvement_goal_20260622/hermes_loop17_fresh_residual_control_queue.json` rows `28`, text/url/comment `7`, image/OCR `21`, duplicate `0`이다. Text/image canary 후 decoder NameError `11706871`와 source/url residual `11703669`을 targeted fix/canary/compare로 닫았고, latest compare `out/completed779_improvement_goal_20260622/compare/hermes_loop17_fix2b_author_context_flag_compare.json`은 movement `blocked_or_candidate_preserved=6`, `candidate_or_human_review_preserved=9`, `candidate_preserved_with_benign_prune=4`, `resolved_expected_title=1`, `resolved_expected_title_author_supported_alt_url=1`, `url_lint_preserved=7`, latest hard next queue `out/completed779_improvement_goal_20260622/hermes_loop17_fix2b_author_context_flag_next_queue.json` rows `0`을 기록한다. 다음 목표는 이 closure를 full approval로 오독하지 않고, 새 Loop 18 fresh/residual/control pool 또는 명시적 limitation queue를 열어 같은 loop를 계속하는 것이다.

Current override:
- Treat Loop 17 as the active latest state. Earlier Loop 16 and Loop 15 queue `0` states are historical targeted/control closure evidence, not current approval.
- Preserve the post-review blocker fix from Claude review of Codex session `019ee9ee`: Loop16's `_title_lead_alias_precision_block_signal` originally broke rank1 demote-but-preserve behavior by treating verifier `critical/major` as a hard rescue block. This was reproduced and fixed by removing `critical_or_major` from that gate. Future completed779/Hermes verification commands must include `tests.test_agentic_pipeline_rank1_lock_block tests.test_agentic_pipeline_rank2_ocr_catalog_evidence tests.test_agentic_pipeline_rank3_lock_anchor`.
- Latest post-review verification: rank1/2/3 suite `40 tests OK`; completed779 focused suite plus rank1/2/3 `126 tests OK`; py_compile pass.
- Loop 17 verification: py_compile pass; focused suite with rank1/2/3 `131 tests OK`; surrounding suite `172 tests OK`.
- Loop 17 text result: `out/completed779_improvement_goal_20260622/canary/hermes_loop17_fresh_residual_control_text_result.json`, completed/failed/pending `7/0/0`.
- Loop 17 image/OCR result: `out/completed779_improvement_goal_20260622/canary/hermes_loop17_fresh_residual_control_image_ocr_result.json`, completed/failed/pending `21/0/0`, VLM/OCR `READY`.
- Loop 17 decoder fix result: `out/completed779_improvement_goal_20260622/canary/hermes_loop17_fix1_decoder_genre_pattern_11706871_image_ocr_result.json`, completed/failed/pending `1/0/0`, NameError/Traceback absent.
- Loop 17 URL/source fix result: `out/completed779_improvement_goal_20260622/canary/hermes_loop17_fix2b_author_context_flag_11703669_text_result.json`, completed/failed/pending `1/0/0`.
- Loop 17 final compare: `out/completed779_improvement_goal_20260622/compare/hermes_loop17_fix2b_author_context_flag_compare.json`, movement `blocked_or_candidate_preserved=6`, `candidate_or_human_review_preserved=9`, `candidate_preserved_with_benign_prune=4`, `resolved_expected_title=1`, `resolved_expected_title_author_supported_alt_url=1`, `url_lint_preserved=7`.
- Loop 17 final next queue: `out/completed779_improvement_goal_20260622/hermes_loop17_fix2b_author_context_flag_next_queue.json`, rows `0`.
- `11694064` sentinel did not regress to `무협 게임에 빙의했다...스킵충이다`; it preserved `판초우의의 마법사` candidate with `https://novel.munpia.com/530500`.
- `11703669` resolved `세상에 나쁜 영애는 없다`; primary URL `https://novel.munpia.com/405699` is same-title official detail and expected Naver seed URL `https://series.naver.com/novel/detail.series?productNo=11651797` is preserved as candidate evidence.
- Loop 17 queue `0` is targeted/fresh-residual-control closure, not completed779 full semantic approval. Keep `semantic_quality=REVIEW-LOCKED` and `full_scan_approval=false`.
- Historical Loop 16 state:
- Loop 16 queue: `out/completed779_improvement_goal_20260622/hermes_loop16_post_loop15_residual_queue.json`, rows `7`, main `0`, controls `7`, text/url/comment `2`, image/OCR `5`, duplicate `0`.
- Loop 16 controls: `11694064`, `11698880`, `11702055`, `11710037`, `11710045`, `11718077`, `11718105`.
- Loop 16 text result: `out/completed779_improvement_goal_20260622/canary/hermes_loop16_post_loop15_residual_text_result.json`, completed/failed/pending `2/0/0`, VLM/OCR `NOT_APPLICABLE`, log `logs/expert_run_20260623_185717_814007.log`.
- Loop 16 image/OCR result: `out/completed779_improvement_goal_20260622/canary/hermes_loop16_post_loop15_residual_image_ocr_result.json`, completed/failed/pending `5/0/0`, VLM/OCR `READY`, log `logs/expert_run_20260623_211124_636740.log`.
- Loop 16 focused scrub/lint result: `out/completed779_improvement_goal_20260622/canary/hermes_loop16b_focused_scrub_lint_result.json`, completed/failed/pending `3/0/0`, VLM/OCR `READY`, log `logs/expert_run_20260623_213513_009298.log`.
- Loop 16 `11698880` reason sync result: `out/completed779_improvement_goal_20260622/canary/hermes_loop16d_11698880_reason_sync_result.json`, completed/failed/pending `1/0/0`, VLM/OCR `READY`, log `logs/expert_run_20260623_214642_901985.log`.
- Loop 16 final result: `out/completed779_improvement_goal_20260622/canary/hermes_loop16_final_control_result.json`, rows `7`, duplicate `0`.
- Loop 16 final compare: `out/completed779_improvement_goal_20260622/compare/hermes_loop16_final_control_compare.json`, movement `blocked_or_candidate_preserved=1`, `candidate_or_human_review_preserved=3`, `url_lint_preserved=3`.
- Loop 16 final next queue: `out/completed779_improvement_goal_20260622/hermes_loop16_final_control_next_queue.json`, rows `0`.
- Loop 16 code changes: `candidate_audit.py` reason scrub/final reason sync/noisy expected seed candidate lint; `compare_completed779_improvement.py` expected-title match with wrong expected URL retaxonomy; related tests were added.
- Loop 16 verification: py_compile pass; focused suite `86 tests OK`; `git diff --check` pass with LF/CRLF warnings only.
- `11694064` sentinel did not regress to `무협 게임에 빙의했다...스킵충이다`; it preserved `판초우의의 마법사` candidate with `https://novel.munpia.com/530500`.
- Loop 16 queue `0` is targeted/control closure, not completed779 full semantic approval. Keep `semantic_quality=REVIEW-LOCKED` and `full_scan_approval=false`.
- Historical Loop 15 evidence: Earlier Loop 14 queue `0` was historical targeted closure evidence; Loop 15 hard next queue was `out/completed779_improvement_goal_20260622/hermes_loop15_combined_fix1_next_queue.json` rows `0`.
- Loop 15 queue: `out/completed779_improvement_goal_20260622/hermes_loop15_remaining_expansion_queue.json`, rows `6`, main `1`, controls `5`, text/url/comment `2`, image/OCR `4`, duplicate `0`.
- Loop 15 manifest: `out/completed779_improvement_goal_20260622/inputs/hermes_loop15_remaining_expansion_input_manifest.json`; it records `main_excluded_id_count=265`, so Loop15 closure is targeted/control closure, not completed779 approval.
- Loop 15 controls: `11694064`, `11698880`, `11702055`, `11710045`, `11718105`. Prior Loop14 control `11718077` was not included and should be considered for future control coverage if relevant.
- Loop 15 pre-fix text result: `out/completed779_improvement_goal_20260622/canary/hermes_loop15_remaining_expansion_text_result.json`, completed/failed/pending `2/0/0`, VLM/OCR `NOT_APPLICABLE`, log `logs/expert_run_20260623_181313_128318.log`.
- Loop 15 pre-fix retaxonomy compare: `out/completed779_improvement_goal_20260622/compare/hermes_loop15_trope_boundary_retaxonomy_text_compare.json`, movement included `boundary_title_over_promoted=1` for `11710037`.
- Loop 15 code changes: `candidate_audit.py` adds `apply_judge_seed_trope_boundary_hold_guard`; `expert_main.py` calls it before final audit fields; `compare_completed779_improvement.py` adds `boundary_title_over_promoted`; related tests were added.
- Loop 15 fix1 text result: `out/completed779_improvement_goal_20260622/canary/hermes_loop15_fix1_trope_boundary_text_result.json`, completed/failed/pending `2/0/0`, VLM/OCR `NOT_APPLICABLE`, log `logs/expert_run_20260623_182142_351153.log`.
- Loop 15 fix1 text compare: `out/completed779_improvement_goal_20260622/compare/hermes_loop15_fix1_trope_boundary_text_compare.json`, movement `blocked_or_candidate_preserved=1`, `candidate_or_human_review_preserved=1`, requeue `0`.
- Loop 15 image/OCR result: `out/completed779_improvement_goal_20260622/canary/hermes_loop15_remaining_expansion_image_ocr_result.json`, completed/failed/pending `4/0/0`, VLM/OCR `READY`, log `logs/expert_run_20260623_182710_899488.log`.
- Loop 15 image/OCR compare: `out/completed779_improvement_goal_20260622/compare/hermes_loop15_remaining_expansion_image_ocr_compare.json`, movement `candidate_or_human_review_preserved=2`, `url_lint_preserved=2`, requeue `0`.
- Loop 15 combined result: `out/completed779_improvement_goal_20260622/canary/hermes_loop15_combined_fix1_result.json`, rows `6`, duplicate `0`.
- Loop 15 combined compare: `out/completed779_improvement_goal_20260622/compare/hermes_loop15_combined_fix1_compare.json`, movement `blocked_or_candidate_preserved=1`, `candidate_or_human_review_preserved=3`, `url_lint_preserved=2`.
- Loop 15 combined next queue: `out/completed779_improvement_goal_20260622/hermes_loop15_combined_fix1_next_queue.json`, rows `0`.
- `11710037` must not resolve publicly to `괴담 호텔 탈출기`; it should preserve the `담텔기 -> 괴담 호텔 탈출기` candidate/HOLD with `https://novelpia.com/novel/102155`.
- `11694064` sentinel did not regress to `무협 게임에 빙의했다...스킵충이다`; it preserved `판초우의의 마법사` candidate with `https://novel.munpia.com/530500`.
- `11710045` remains public-title null/HOLD. Its noisy candidate surfaces are a future candidate-pollution/prompt-orchestration limitation, not approval evidence.
- Loop 15 verification: py_compile pass; `tests.test_candidate_audit tests.test_completed779_compare tests.test_completed779_hermes_expansion tests.test_agentic_pipeline_rework.AgenticPipelineReworkTest.test_relation_hold_blocks_indirect_character_scene_title_resolution` `84 tests OK`; `git diff --check` pass with LF/CRLF warnings only after docs sync.
- Historical Loop 14 evidence:
- Loop 13 retaxonomy compare: `out/completed779_improvement_goal_20260622/compare/hermes_loop13_retaxonomy_source_url_fix_combined_compare.json`, movement `blocked_or_candidate_preserved=8`, `boundary_hold_preserved=4`, `candidate_or_human_review_preserved=31`, `candidate_preserved_with_benign_prune=3`, `resolved_expected_title=1`, `title_or_url_still_mismatched=2`, `url_lint_preserved=2`.
- Loop 13 retaxonomy next queue: `out/completed779_improvement_goal_20260622/hermes_loop13_retaxonomy_source_url_fix_next_queue.json`, rows `2`: `11698880`, `11702055`.
- Loop 14 v2 queue: `out/completed779_improvement_goal_20260622/hermes_loop14_remaining_expansion_v2_queue.json`, rows `22`, main `16`, controls `6`, text/url/comment `8`, image/OCR `14`, duplicate `0`.
- Loop 14 v2 controls: `11694064`, `11698880`, `11702055`, `11710045`, `11718105`, `11718077`.
- Loop 14 v2 text result: `out/completed779_improvement_goal_20260622/canary/hermes_loop14_remaining_expansion_v2_text_result.json`, rows `8/8`, failed `0`, pending `0`, VLM/OCR `NOT_APPLICABLE`, log `logs/expert_run_20260623_170021_835831.log`.
- Loop 14 v2 image/OCR result: `out/completed779_improvement_goal_20260622/canary/hermes_loop14_remaining_expansion_v2_image_ocr_result.json`, rows `14/14`, failed `0`, pending `0`, VLM/OCR `READY`, log `logs/expert_run_20260623_170801_748203.log`, effective parallel `2` due reuse-shards-only health filtering.
- Loop 14 v2 combined result: `out/completed779_improvement_goal_20260622/canary/hermes_loop14_remaining_expansion_v2_combined_result.json`, rows `22`, duplicate `0`.
- Loop 14 v2 combined compare: `out/completed779_improvement_goal_20260622/compare/hermes_loop14_remaining_expansion_v2_combined_compare.json`, movement `blocked_or_candidate_preserved=1`, `boundary_hold_preserved=2`, `candidate_or_human_review_preserved=14`, `candidate_preserved_with_benign_prune=1`, `resolved_expected_title=1`, `title_or_url_still_mismatched=2`, `url_lint_preserved=1`.
- Loop 14 v2 next queue: `out/completed779_improvement_goal_20260622/hermes_loop14_remaining_expansion_v2_next_queue.json`, rows `2`: `11698880`, `11702055`.
- Loop 14 fix1 queue: `out/completed779_improvement_goal_20260622/hermes_loop14_fix1_hygiene_expected_candidate_v2_queue.json`, rows `2`, image/OCR `2`.
- Loop 14 fix1 result: `out/completed779_improvement_goal_20260622/canary/hermes_loop14_fix1_hygiene_expected_candidate_v2_image_ocr_result.json`, completed/failed/pending `2/0/0`, VLM/OCR `READY`, log `logs/expert_run_20260623_174842_756421.log`.
- Loop 14 fix1 compare: `out/completed779_improvement_goal_20260622/compare/hermes_loop14_fix1_hygiene_expected_candidate_v2_compare.json`, movement `url_lint_preserved=2`; both rows have `expected_title_preserved=true` and `expected_url_preserved=true`.
- Loop 14 fix1 next queue: `out/completed779_improvement_goal_20260622/hermes_loop14_fix1_hygiene_expected_candidate_v2_next_queue.json`, rows `0`.
- Loop 14 code changes: `build_completed779_hermes_expansion.py` explicit `--control-post-id` and empty-main-target fix; `compare_completed779_improvement.py` stricter source/url hygiene and `unexpected_resolved_title`; `candidate_audit.py` hygiene expected candidate preservation.
- Loop 14 verification: py_compile pass; `tests.test_candidate_audit tests.test_completed779_compare tests.test_completed779_hermes_expansion tests.test_agentic_pipeline_rework.AgenticPipelineReworkTest.test_relation_hold_blocks_indirect_character_scene_title_resolution` `82 tests OK`; `git diff --check` pass with LF/CRLF warnings only.
- `11694064` sentinel did not regress to `무협 게임에 빙의했다...스킵충이다`; `11710045` did not regain an unexpected public title.
- Loop 15 later opened a fresh/residual/control pool and kept `11694064`, `11710045`, `11718105`, `11698880`, `11702055` as regression controls.
- Historical Loop 13 evidence:
- Loop 13 residual expansion queue: `out/completed779_improvement_goal_20260622/hermes_loop13_residual_expansion_queue.json`, rows `51`, main `39`, controls `12`, text/url/comment `9`, image/OCR `42`, duplicate `0`.
- Loop 13 buckets: `fallback_unseen_high_risk=24`, `under_resolved=6`, `under_resolved_false_negative=3`, `wrong_relevance=6`, `loop13_source_regression_review_residual=8`, `loop13_source_regression_url_lint_residual=4`.
- Loop 13 input manifest: `out/completed779_improvement_goal_20260622/inputs/hermes_loop13_residual_expansion_input_manifest.json`.
- Loop 13 text result: `out/completed779_improvement_goal_20260622/canary/hermes_loop13_residual_expansion_text_result.json`, rows `9/9`, failed `0`, pending `0`, VLM/OCR `NOT_APPLICABLE`, log `logs/expert_run_20260623_150842_142186.log`.
- Loop 13 image/OCR result: `out/completed779_improvement_goal_20260622/canary/hermes_loop13_residual_expansion_image_ocr_result.json`, rows `42/42`, failed `0`, pending `0`, VLM/OCR `READY`, log `logs/expert_run_20260623_151732_213768.log`, effective parallel `2` due reuse-shards-only health filtering.
- Loop 13 combined compare: `out/completed779_improvement_goal_20260622/compare/hermes_loop13_residual_expansion_combined_compare.json`, movement `blocked_or_candidate_preserved=8`, `boundary_hold_preserved=4`, `candidate_or_human_review_preserved=31`, `candidate_preserved_with_benign_prune=3`, `resolved_expected_title=1`, `url_lint_preserved=4`.
- Loop 13 next queue: `out/completed779_improvement_goal_20260622/hermes_loop13_residual_expansion_next_queue.json`, rows `0`.
- Loop 13 targeted `11710045` after-fix result: `out/completed779_improvement_goal_20260622/canary/hermes_loop13_ocr_filter_11710045_after_relation_hold_fix_result.json`, completed/failed/pending `1/0/0`, VLM/OCR `READY`, log `logs/expert_run_20260623_164251_513007.log`.
- Loop 13 targeted `11710045` after-fix compare: `out/completed779_improvement_goal_20260622/compare/hermes_loop13_ocr_filter_11710045_after_relation_hold_fix_compare.json`, movement `candidate_or_human_review_preserved=1`, requeue `0`.
- Loop 13 code changes: `compare_completed779_improvement.py` adds boundary-HOLD and benign-wrapper accounting; `candidate_audit.py` filters context-only OCR work cues; `agentic_pipeline.py` blocks public title resolution for relation-HOLD indirect character/scene evidence without direct title anchors.
- Loop 13 verification: py_compile pass; `tests.test_candidate_audit tests.test_completed779_compare tests.test_completed779_hermes_expansion tests.test_agentic_pipeline_rework.AgenticPipelineReworkTest.test_relation_hold_blocks_indirect_character_scene_title_resolution` `77 tests OK`; `git diff --check` pass with LF/CRLF warnings only before docs sync.
- `11694064` sentinel did not regress to `무협 게임에 빙의했다...스킵충이다`.
- `11710045` after-fix intentionally remains conservative: `official_title=null`, `Identified=0`, `title_resolution_state=context_only`, `title_resolution_allowed=false`, candidate ledger preserves `루나`, `유하늘`.
- Next Loop 14 should open a fresh/residual/control pool and include `11694064`, `11710045`, and `11718105` as regression controls.
- Loop 10 broader regression queue: `out/completed779_improvement_goal_20260622/hermes_loop10_broader_regression_queue.json`, rows `32`, text/url/comment `15`, image/OCR `17`, duplicate `0`.
- Loop 10 broader input manifest: `out/completed779_improvement_goal_20260622/inputs/hermes_loop10_broader_regression_input_manifest.json`.
- Loop 10 broader text result: `out/completed779_improvement_goal_20260622/canary/hermes_loop10_broader_regression_text_result.json`, rows `15/15`, VLM/OCR `NOT_APPLICABLE`, log `logs/expert_run_20260623_115623_153894.log`.
- Loop 10 broader image/OCR result: `out/completed779_improvement_goal_20260622/canary/hermes_loop10_broader_regression_image_ocr_result.json`, rows `17/17`, VLM/OCR `READY`, log `logs/expert_run_20260623_121748_731283.log`.
- Loop 10 broader combined result: `out/completed779_improvement_goal_20260622/canary/hermes_loop10_broader_regression_combined_result.json`, rows `32`, duplicate `0`.
- Loop 10 broader combined compare: `out/completed779_improvement_goal_20260622/compare/hermes_loop10_broader_regression_combined_compare.json`, movement `candidate_or_human_review_preserved=18`, `candidate_preserved_with_prune_review=2`, `resolved_expected_title=4`, `url_lint_preserved=8`.
- Loop 10 broader next queue: `out/completed779_improvement_goal_20260622/hermes_loop10_broader_regression_next_queue.json`, rows `2`, post_ids `11710025`, `11708479`.
- Loop 10 candidate/comment v2 queue: `out/completed779_improvement_goal_20260622/hermes_loop10_candidate_comment_expansion_v2_queue.json`, rows `11`, text/url/comment `4`, image/OCR `7`, duplicate `0`.
- Loop 10 candidate/comment v2 input manifest: `out/completed779_improvement_goal_20260622/inputs/hermes_loop10_candidate_comment_expansion_v2_input_manifest.json`.
- Loop 10 candidate/comment v2 text result: `out/completed779_improvement_goal_20260622/canary/hermes_loop10_candidate_comment_expansion_v2_text_result.json`, rows `4/4`, VLM/OCR `NOT_APPLICABLE`, log `logs/expert_run_20260623_124623_349688.log`.
- Loop 10 candidate/comment v2 image/OCR result: `out/completed779_improvement_goal_20260622/canary/hermes_loop10_candidate_comment_expansion_v2_image_ocr_result.json`, rows `7/7`, VLM/OCR `READY`, log `logs/expert_run_20260623_130033_520130.log`.
- Loop 10 candidate/comment v2 combined result: `out/completed779_improvement_goal_20260622/canary/hermes_loop10_candidate_comment_expansion_v2_combined_result.json`, rows `11`, duplicate `0`.
- Loop 10 candidate/comment v2 combined compare: `out/completed779_improvement_goal_20260622/compare/hermes_loop10_candidate_comment_expansion_v2_combined_compare.json`, movement `candidate_or_human_review_preserved=7`, `candidate_preserved_with_prune_review=2`, `resolved_expected_title=2`.
- Loop 10 candidate/comment v2 next queue: `out/completed779_improvement_goal_20260622/hermes_loop10_candidate_comment_expansion_v2_next_queue.json`, rows `2`, post_ids `11698878`, `11708478`.
- Loop 10 subagents: Averroes (`gpt-5.5`) source/url/regression skeptic, Mill (`gpt-5.4`) code-hook/compare skeptic, Fermat (`gpt-5.4-mini`) candidate/prompt expert. Sagan context-window error is a recorded limitation, not approval evidence.
- Loop 10 code/tooling changes: `build_completed779_hermes_expansion.py` custom main targets and candidate/comment/multi default lanes; `compare_completed779_improvement.py` strict expected evidence flags and `candidate_preserved_with_prune_review`; `candidate_audit.py` `blocked_primary_work_conflict` marking.
- Loop 10 verification: py_compile pass; `tests.test_completed779_hermes_expansion tests.test_completed779_compare tests.test_candidate_audit tests.test_judge_seed_registry` `72 tests OK`; broader focused suite `170 tests OK`.
- Treat earlier references to Loop 7 hard queue, Loop 5 operational residual, and source-correctness refresh as historical unless explicitly used as controls.
- Loop 9 source queue: `out/completed779_improvement_goal_20260622/hermes_loop8_fresh_expansion_next_queue.json`, rows `8`.
- Loop 9 input manifest: `out/completed779_improvement_goal_20260622/inputs/hermes_loop9_residual_input_manifest.json`, text/url/comment `4`, image/OCR `4`, missing `0`, duplicate `0`.
- Loop 9 text result: `out/completed779_improvement_goal_20260622/canary/hermes_loop9_residual_text_result.json`, rows `4/4`, VLM/OCR `NOT_APPLICABLE`, log `logs/expert_run_20260623_113346_494633.log`.
- Loop 9 image/OCR result: `out/completed779_improvement_goal_20260622/canary/hermes_loop9_residual_image_ocr_result.json`, rows `4/4`, VLM/OCR `READY`, log `logs/expert_run_20260623_113635_246713.log`.
- Loop 9 combined result: `out/completed779_improvement_goal_20260622/canary/hermes_loop9_residual_combined_result.json`, rows `8`, duplicate post_ids `0`.
- Loop 9 combined compare: `out/completed779_improvement_goal_20260622/compare/hermes_loop9_residual_combined_compare.json`.
- Loop 9 movement: `blocked_or_candidate_preserved=3`, `candidate_or_human_review_preserved=5`.
- Loop 9 next queue: `out/completed779_improvement_goal_20260622/hermes_loop9_residual_next_queue.json`, rows `0`.
- Loop 9 code changes: `candidate_audit.py` comment-surface HOLD candidate preservation, judge expected candidate preservation/conflict guard, weak `llm_only`/`comment_surface` sentence candidate pruning; `expert_main.py` calls these before candidate audit fields.
- Stale model `bg-digitalservices/Gemma-4-E4B-it-NVFP4` returned 404. Use live model `bg-digitalservices/Gemma-4-26B-A4B-it-NVFP4` unless `/v1/models` says otherwise.
- Loop 8 queue: `out/completed779_improvement_goal_20260622/hermes_loop8_fresh_expansion_queue.json`, rows `43`, main `24`, controls `19`, text/url/comment `20`, image/OCR `23`, duplicate post_ids `0`.
- Loop 8 text result: `out/completed779_improvement_goal_20260622/canary/hermes_loop8_fresh_expansion_text_result.json`, rows `20/20`, VLM/OCR `NOT_APPLICABLE`.
- Loop 8 image/OCR result: `out/completed779_improvement_goal_20260622/canary/hermes_loop8_fresh_expansion_image_ocr_result.json`, rows `23/23`, VLM/OCR `READY`.
- Loop 8 combined result: `out/completed779_improvement_goal_20260622/canary/hermes_loop8_fresh_expansion_combined_result.json`, rows `43`, duplicate post_ids `0`.
- Loop 8 combined compare: `out/completed779_improvement_goal_20260622/compare/hermes_loop8_fresh_expansion_combined_compare.json`.
- Loop 8 combined movement: `blocked_or_candidate_preserved=9`, `candidate_or_human_review_preserved=15`, `resolved_expected_title=4`, `resolved_expected_title_and_url=2`, `url_lint_preserved=5`, `still_under_resolved_or_noise=3`, `title_or_url_still_mismatched=2`, `title_match_url_still_mismatched=3`.
- Loop 9 source queue report: `out/completed779_improvement_goal_20260622/hermes_loop8_fresh_expansion_next_queue_ko.md`.
- Loop 9 source rows were: `11718051`, `11694042`, `11694059`, `11716462`, `11716479`, `11703631`, `11710047`, `11714902`.
- `11694064` sentinel did not regress to `무협 게임에 빙의했다...스킵충이다`; it preserved `판초우의의 마법사` candidate/official URL and was classified `blocked_or_candidate_preserved`.
- `11698880` recovered `아카데미 생존 갤러리` with expected URL `https://novelpia.com/novel/380218`.
- `tools/compare_completed779_improvement.py` was fixed to count expected candidate preservation and to keep recall/relevance rows with a mismatched final public title in requeue.
- Treat earlier references to Loop 7 text `14/16`, `11702087` blocker, and `11705239` blocker as historical. They are no longer the active blockers.
- `11702087` fix9: completed `1/1`, `official_title=괴담 호텔 탈출기`, `heretic_url=https://novelpia.com/novel/102155`.
- `11705239` fix1: completed `1/1`, safely held as `official_title=null`, `work_resolution=none`, `title_resolution_state=unresolvable_memory_query`.
- `11716480` fix6: completed/flushed/pending/failed `1/1/0/0`, final close OCR title `여대생 가랑이 사이 무릎 끓은 엄마들`, `heretic_url=null`, movement `url_lint_preserved`.
- `11716480` runtime hang is targeted-closed, but official/detail URL discovery and tag/query pruning remain open residuals.
- Loop 7 fix7: final combined compare rows `36/36`; movement `candidate_or_human_review_preserved=13`, `resolved_expected_title=1`, `resolved_expected_title_and_url=1`, `review=12`, `still_under_resolved_or_noise=2`, `url_lint_preserved=7`; next queue rows `2`.
- `11711600` is closed by candidate preservation for `망할 놈의 아카데미`.
- `11706832` fix17: completed `1/1`, resolved `황제폐하가 웹소설 작가임을 숨김` with `https://novelpia.com/novel/385635`; compare movement `resolved_expected_title=1`; next queue rows `0`.
- Keep semantic_quality=REVIEW-LOCKED and full_scan_approval=false.

This is a continuous loop goal:
- Do not stop after one implementation loop if a non-empty queue remains.
- Continue with the next queue until the queue is empty, or every remaining row is explicitly HOLD/human_review/INFO_MISSING/quarantine/no_generalizable_fix_left with row-level rationale.
- Subagents are explorers and challengers, not approval authorities. Main Codex must reverify every claim with files, tests, canary, compare, or bounded web/search evidence.
- Use subagents when useful, and diversify role/model/tooling when available: taxonomy/source expert, search/web expert, candidate/comment expert, OCR/visual expert, code-hook expert, prompt/orchestration expert, verification/docs expert. Prefer different reasoning profiles or model choices where the runtime exposes them, but never treat model identity as proof.
- If a subagent or tool fails because of capacity, context, search, or thread limits, record the limitation and continue with main Codex verification instead of silently dropping that lane.

Authoritative Evidence:
- Active contract: goal.md
- Archived prior goal: llm_judge_goal.md
- Baseline completed subset: out/expert_result_20260620_165159_711176_completed_subset.json
- Native-web judge root: out/codex_native_web_judge_20260620_165159_711176_completed779/
- Deterministic full-post judge root: out/full_post_judge_20260620_165159_711176_completed779/
- Improvement root: out/completed779_improvement_goal_20260622/
- Loop 2 combined compare: out/completed779_improvement_goal_20260622/compare/reimprovement_loop2_combined_compare.json
- Hermes Loop 3 precompare: out/completed779_improvement_goal_20260622/compare/hermes_loop3_precompare.json
- Hermes Loop 3 deterministic re-audit compare: out/completed779_improvement_goal_20260622/compare/hermes_loop3_deterministic_reaudit_compare.json
- Hermes Loop 4 combined result: out/completed779_improvement_goal_20260622/canary/hermes_loop4_combined_result.json
- Hermes Loop 4 compare: out/completed779_improvement_goal_20260622/compare/hermes_loop4_compare.json
- Completed Loop 5 queue: out/completed779_improvement_goal_20260622/hermes_loop5_source_residual_queue.json
- Completed Loop 5 queue report: out/completed779_improvement_goal_20260622/hermes_loop5_source_residual_queue_ko.md
- Completed Loop 5 input manifest: out/completed779_improvement_goal_20260622/inputs/hermes_loop5_source_residual_input_manifest.json
- Loop 5 text/url/comment result: out/completed779_improvement_goal_20260622/canary/hermes_loop5_source_residual_text_result.json
- Loop 5 image/OCR result: out/completed779_improvement_goal_20260622/canary/hermes_loop5_source_residual_image_ocr_result.json
- Loop 5 combined result: out/completed779_improvement_goal_20260622/canary/hermes_loop5_source_residual_combined_result.json
- Loop 5 combined compare: out/completed779_improvement_goal_20260622/compare/hermes_loop5_source_residual_combined_compare.json
- Loop 5 hard-fail next queue: out/completed779_improvement_goal_20260622/hermes_loop5_source_residual_next_queue.json
- Loop 5 operational residual queue: out/completed779_improvement_goal_20260622/hermes_loop5_source_residual_operational_residual_queue.json
- Loop 6 remaining queue: out/completed779_improvement_goal_20260622/hermes_loop6_remaining_queue.json
- Loop 6 final queue after postfix4: out/completed779_improvement_goal_20260622/hermes_loop6_remaining_queue_postfix4.json
- Loop 6 final queue report: out/completed779_improvement_goal_20260622/hermes_loop6_remaining_queue_postfix4_ko.md
- Loop 6 postfix4 11698868 text result: out/completed779_improvement_goal_20260622/canary/hermes_loop6_postfix4_11698868_text_result.json
- Loop 6 postfix4 11708449 image/OCR result: out/completed779_improvement_goal_20260622/canary/hermes_loop6_postfix4_11708449_image_ocr_result.json
- Loop 6 postfix4 compares:
  - out/completed779_improvement_goal_20260622/compare/hermes_loop6_postfix4_11698868_text_compare.json
  - out/completed779_improvement_goal_20260622/compare/hermes_loop6_postfix4_11708449_image_ocr_compare.json
- Loop 7 broader residual queue: out/completed779_improvement_goal_20260622/hermes_loop7_broader_residual_queue.json
- Loop 7 broader residual queue report: out/completed779_improvement_goal_20260622/hermes_loop7_broader_residual_queue_ko.md
- Loop 7 input manifest: out/completed779_improvement_goal_20260622/inputs/hermes_loop7_broader_residual_input_manifest.json
- Loop 7 text/url/comment input: out/completed779_improvement_goal_20260622/inputs/hermes_loop7_broader_residual_text_url_comment.jsonl
- Loop 7 image/OCR input: out/completed779_improvement_goal_20260622/inputs/hermes_loop7_broader_residual_image_ocr.jsonl
- Loop 7 text partial combined result: out/completed779_improvement_goal_20260622/canary/hermes_loop7_broader_residual_text_partial_combined_result.json
- Loop 7 text fix1 combined result: out/completed779_improvement_goal_20260622/canary/hermes_loop7_broader_residual_text_combined_fix1_result.json
- Loop 7 text fix1 compare: out/completed779_improvement_goal_20260622/compare/hermes_loop7_broader_residual_text_fix1_compare.json
- Loop 7 runtime blocker report: out/completed779_improvement_goal_20260622/hermes_loop7_text_runtime_blockers_ko.md
- Loop 7 image/OCR broad fix1 result: out/completed779_improvement_goal_20260622/canary/hermes_loop7_broader_residual_image_ocr_fix1_result.json
- Loop 7 image/OCR broad fix1 compare: out/completed779_improvement_goal_20260622/compare/hermes_loop7_broader_residual_image_ocr_fix1_compare.json
- Loop 7 combined partial fix1 result: out/completed779_improvement_goal_20260622/canary/hermes_loop7_broader_residual_combined_fix1_partial35_result.json
- Loop 7 combined partial fix1 compare: out/completed779_improvement_goal_20260622/compare/hermes_loop7_broader_residual_combined_fix1_partial35_compare.json
- Loop 7 fix1 next queue: out/completed779_improvement_goal_20260622/hermes_loop7_broader_residual_next_queue_fix1_partial35.json
- Loop 7 11716480 fix6 result: out/completed779_improvement_goal_20260622/canary/hermes_loop7_image_ocr_single_11716480_fix6_result.json
- Loop 7 11716480 fix6 manifest: out/completed779_improvement_goal_20260622/canary/hermes_loop7_image_ocr_single_11716480_fix6_result_manifest.json
- Loop 7 11716480 fix6 compare: out/completed779_improvement_goal_20260622/compare/hermes_loop7_image_ocr_single_11716480_fix6_compare.json
- Loop 7 11716480 fix6 remaining queue: out/completed779_improvement_goal_20260622/compare/hermes_loop7_image_ocr_single_11716480_fix6_remaining_queue.json
- Loop 7 final combined fix6 result: out/completed779_improvement_goal_20260622/canary/hermes_loop7_broader_residual_combined_fix6_final36_result.json
- Loop 7 fix7 unwrapped final compare: out/completed779_improvement_goal_20260622/compare/hermes_loop7_broader_residual_combined_fix7_unwrapped_final36_compare.json
- Loop 7 fix7 next queue: out/completed779_improvement_goal_20260622/hermes_loop7_broader_residual_next_queue_fix7_unwrapped_final36.json
- Loop 7 fix11 short-alias fetch compare: out/completed779_improvement_goal_20260622/compare/hermes_loop7_fix11_short_alias_fetch_11706832_compare.json
- Loop 7 fix11 next queue: out/completed779_improvement_goal_20260622/hermes_loop7_fix11_short_alias_fetch_next_queue.json
- Loop 7 fix17 J11 alias-lock result: out/completed779_improvement_goal_20260622/canary/hermes_loop7_fix17_j11_alias_lock_11706832_result.json
- Loop 7 fix17 J11 alias-lock compare: out/completed779_improvement_goal_20260622/compare/hermes_loop7_fix17_j11_alias_lock_11706832_compare.json
- Loop 7 fix17 next queue: out/completed779_improvement_goal_20260622/hermes_loop7_fix17_j11_alias_lock_next_queue.json
- Loop 8 queue: out/completed779_improvement_goal_20260622/hermes_loop8_fresh_expansion_queue.json
- Loop 8 queue report: out/completed779_improvement_goal_20260622/hermes_loop8_fresh_expansion_queue_ko.md
- Loop 8 input manifest: out/completed779_improvement_goal_20260622/inputs/hermes_loop8_fresh_expansion_input_manifest.json
- Loop 8 text result: out/completed779_improvement_goal_20260622/canary/hermes_loop8_fresh_expansion_text_result.json
- Loop 8 image/OCR result: out/completed779_improvement_goal_20260622/canary/hermes_loop8_fresh_expansion_image_ocr_result.json
- Loop 8 combined result: out/completed779_improvement_goal_20260622/canary/hermes_loop8_fresh_expansion_combined_result.json
- Loop 8 combined compare: out/completed779_improvement_goal_20260622/compare/hermes_loop8_fresh_expansion_combined_compare.json
- Loop 9 active queue: out/completed779_improvement_goal_20260622/hermes_loop8_fresh_expansion_next_queue.json
- Loop 9 active queue report: out/completed779_improvement_goal_20260622/hermes_loop8_fresh_expansion_next_queue_ko.md
- Source-correctness refresh preflight: out/completed779_improvement_goal_20260622/source_correctness_refresh_20260622/source_correctness_refresh_preflight_ko.md
- Source-correctness refresh queue: out/completed779_improvement_goal_20260622/source_correctness_refresh_20260622/source_correctness_refresh_queue.json
- Source-correctness refresh input manifest: out/completed779_improvement_goal_20260622/source_correctness_refresh_20260622/inputs/source_correctness_refresh_input_manifest.json
- Source-correctness refresh combined result: out/completed779_improvement_goal_20260622/source_correctness_refresh_20260622/canary/source_correctness_refresh_combined_result.json
- Source-correctness refresh compare: out/completed779_improvement_goal_20260622/source_correctness_refresh_20260622/compare/source_correctness_refresh_compare.json
- Source-correctness refresh next queue: out/completed779_improvement_goal_20260622/source_correctness_refresh_20260622/source_correctness_refresh_next_queue.json
- Previous queue report: out/completed779_improvement_goal_20260622/hermes_loop3_queue_ko.md
- Prior Loop 2 prompt/result: docs/devs/COMPLETED779_REIMPROVEMENT_LOOP2_GOAL_PROMPT.md

Current Status And Next Queue:
- Latest override: Loop 17 fix2b closed the fresh/residual/control pool after the decoder NameError residual (`11706871`) and same-title official URL residual (`11703669`) were fixed, rerun, and compare-verified.
  - `out/completed779_improvement_goal_20260622/hermes_loop17_fix2b_author_context_flag_next_queue.json`, rows `0`.
  - `out/completed779_improvement_goal_20260622/compare/hermes_loop17_fix2b_author_context_flag_compare.json`, movement `blocked_or_candidate_preserved=6`, `candidate_or_human_review_preserved=9`, `candidate_preserved_with_benign_prune=4`, `resolved_expected_title=1`, `resolved_expected_title_author_supported_alt_url=1`, `url_lint_preserved=7`.
- Next work should not reprocess the closed Loop 13/14/15/16/17 queues. If continuing completed779 improvement, open Loop 18 from a fresh expansion, compare-verified residual pool, explicit regression control pool, or documented limitation queue. Semantic quality remains `REVIEW-LOCKED`; full scan approval remains `false`.
- Loop 10 hard queues are historical closure evidence and must not be treated as current completion beyond their targeted scope.
- Loop 8/9 hard queues are historical closure evidence and must not be treated as current completion.
- Loop 7 broader residual queue rows: 36
- Loop 7 split: main 16, control 20, text/url/comment 16, image/OCR 20
- Loop 7 selection buckets:
  - under_resolved=3
  - under_resolved_false_negative=8
  - wrong_relevance=5
  - operational_residual_review=12
  - operational_residual_url_lint_preserved=8
- Loop 7 current status:
  - text/url/comment is now combined `16/16` via fix1.
  - image/OCR broad fix1 is `19/20`; missing row `11716480` was handled by single-row fix6.
  - final combined result is `36/36`.
  - fix7 next queue was `2`; fix11/fix17 targeted work leaves active Loop 7 hard queue `0`.
  - next loop must select a fresh expansion/residual source instead of reprocessing the closed Loop 7 queue.
  - combined partial fix1 result remains `35/36`; final combined `36/36` should be regenerated before the next broad queue decision.
- Loop 7 targeted blockers:
  - `11702087`: fix9 targeted-resolved with `괴담 호텔 탈출기` and NovelPia detail URL.
  - `11705239`: fix1 targeted-held with title null / unresolvable memory query, which is the safer movement.
  - `11716480`: fix6 targeted-resolved as a close OCR title variant with URL lint preserved; URL discovery remains open.
- Loop 7 code fixes already applied:
  - `src/llm_batch/agentic_pipeline.py`: early flags initialization/merge fixes `_context_to_output` `UnboundLocalError`.
  - `src/llm_batch/experts/orchestrator.py`: dense internal work character/setting clusters can bypass premature semantic seed early stop.
  - `src/llm_batch/experts/orchestrator.py`: Korean connective/question lead tokens such as `그래서` are low-specificity seeds and are not re-added by Phase34.5 reaction-tail augmentation.
  - `tests/test_title_lead_search_inferred_guard.py`: regression tests cover both behaviors.
- Loop 7 focused verification:
  - `py_compile` pass for changed agentic/orchestrator files.
  - `tests.test_title_lead_search_inferred_guard`: `67 tests OK`.
- Loop 6 hard residual rows: 0; Loop 6 is historical closure evidence, not the current queue.
- Loop 6 final queue path: out/completed779_improvement_goal_20260622/hermes_loop6_remaining_queue_postfix4.json
- Loop 6 closure:
  - 11698868: `방타스` preserved as a `post_title_surface` candidate without unsafe title/URL promotion.
  - 11708449: `담청` preserved as a `post_title_surface` candidate in an image/OCR case without unsafe title/URL promotion.
  - 11705237: `월야환담` preserved as a media-adaptation title-surface candidate.
  - 11710039: official/context candidate preservation closed the entity-hold row.
  - 11698880: public output wrong-work finalization is guarded, but upstream title/body multi-candidate orchestration remains a research note.
- Next active queue should not be the old Loop 5 hard-fail `4` rows. Start from:
  - Loop 5 operational residual queue `24` rows when doing residual diagnostics.
  - completed779 native-web non-ACCEPT issue index when broadening taxonomy coverage.
  - a new bounded random/high-risk expansion when validating that candidate-surface preservation did not create over-hold or over-promotion.
- Historical Loop 5 snapshot:
- Loop 5 completed rows: 44/44
- Loop 5 text/url/comment result rows: 19/19
- Loop 5 image/OCR result rows: 25/25
- Loop 5 duplicate post_ids: 0
- Loop 5 combined movement:
  - candidate_or_human_review_preserved=16
  - resolved_expected_title=4
  - review=12
  - still_under_resolved_or_noise=4
  - url_lint_preserved=8
- historical hard-fail next queue:
  - path: out/completed779_improvement_goal_20260622/hermes_loop5_source_residual_next_queue.json
  - rows: 4
  - movement: still_under_resolved_or_noise=4
- operational residual queue:
  - path: out/completed779_improvement_goal_20260622/hermes_loop5_source_residual_operational_residual_queue.json
  - rows: 24
  - movement: review=12, url_lint_preserved=8, still_under_resolved_or_noise=4
- source-refresh movement feeding Loop 5 controls: resolved_expected_title_and_url=6, review=12, url_lint_preserved=21
- source-correctness refresh rows: 39/39 matched
- latest source-correctness text/url/comment canary:
  - result: out/completed779_improvement_goal_20260622/source_correctness_refresh_20260622/canary/source_correctness_refresh_text_result.json
  - log: logs/expert_run_20260622_220605_069293.log
  - completed/flushed/pending/failed: 14/14/0/0
- latest source-correctness image/OCR canary:
  - result: out/completed779_improvement_goal_20260622/source_correctness_refresh_20260622/canary/source_correctness_refresh_image_ocr_result.json
  - log: logs/expert_run_20260622_222635_313729.log
  - completed/flushed/pending/failed: 25/25/0/0
  - VLM/OCR Semantic Gate: READY
- latest combined result:
  - out/completed779_improvement_goal_20260622/source_correctness_refresh_20260622/canary/source_correctness_refresh_combined_result.json
- latest compare:
  - out/completed779_improvement_goal_20260622/source_correctness_refresh_20260622/compare/source_correctness_refresh_compare.json
  - after rows matched: 39/39
  - next queue: out/completed779_improvement_goal_20260622/source_correctness_refresh_20260622/source_correctness_refresh_next_queue.json, rows 0
- latest normal shard audit:
  - out/completed779_improvement_goal_20260622/source_correctness_refresh_20260622/search_shard_audit_after_restore.json
  - ok=2/2, direct_search_fallback=false, direct_search_degraded_provider=false
- important residuals after Loop 5:
  - 11710058: 판초법사 -> 판초우의의 마법사 recovered with official URL, proving the alias rule can work.
  - 11694064 and 11710033: bad titles did not return, but 판초법사 -> 판초우의의 마법사 is still not consistently recovered; both remain promotion_blocked/title null.
  - 11698880: expected 아카데미 생존 갤러리, after title 가챠 중독자의 퓨전펑크 생활; title/body multi-candidate conflict still needs HOLD instead of primary finalization.
  - 11702055: 괴담 호텔 탈출기 character/setting evidence appears in logs, but final output remains title null/adjacent.
  - 11706871: 파우스트 1 recovered and prior wrong-title risk improved, but URL evidence remains linted/mismatched.
  - 11716480: OCR explicit title recovered as a close variant, but URL null remains and decoder prompt exceeded 100k chars.
  - 11714902 and 11718076: moved away from bad pipeline titles into unresolved_matchable/promotion_blocked, but safe alias-to-official recovery is still open.
- prior Hermes Loop 4 text canary:
  - result: out/completed779_improvement_goal_20260622/canary/hermes_loop4_text_result.json
  - log: logs/expert_run_20260622_214057_698080.log
  - completed: 4/4
- prior Hermes Loop 4 image/OCR canary:
  - result: out/completed779_improvement_goal_20260622/canary/hermes_loop4_image_ocr_result.json
  - log: logs/expert_run_20260622_214139_955485.log
  - completed: 1/1
- prior Hermes Loop 4 compare:
  - out/completed779_improvement_goal_20260622/compare/hermes_loop4_compare.json
  - after rows matched: 5/5
  - next queue: out/completed779_improvement_goal_20260622/hermes_loop4_queue.json, rows 0
- caveat:
  - Source-correctness refresh targeted queue is consumed and next queue is 0, but this is not semantic approval.
  - `review=12` and `url_lint_preserved=21` are residual evidence, not a full fix.
  - Do not rerun the closed 5 Loop 4 rows or the consumed 39 refresh rows as main work. Loop 5 has already consumed its 44-row expansion; use Loop 5 residual queues for the next loop.

Consumed Source-Correctness Refresh:
- original queue rows: 39
- queue: out/completed779_improvement_goal_20260622/source_correctness_refresh_20260622/source_correctness_refresh_queue.json
- text/url/comment input rows: 14
- image/OCR input rows: 25
- closed Loop 4 rows were excluded from the main seed.
- normal Docker/SearXNG shards were restored before running: ok=2/2.
- first next action: preflight Loop 5 residual queues, then design the next generalized fix/canary loop.

Active Queue Planning Fields:
- The active queue rows must include non-empty `suspected_code_hook`, `proposed_next_fix`, and `required_test`.
- If these fields are missing, fill them before code edits so the loop does not become another manual reinterpretation pass.
- Use the queue row fields as the first execution plan, then revise them only with explicit evidence.

Non-Negotiable Gates:
- Do not mix deterministic full_post_judge_report aggregate with native-web or active queue aggregate.
- Keep semantic_quality=REVIEW-LOCKED.
- Keep full_scan_approval=false.
- Do not hardcode post_id/title-specific fixes.
- Do not write back to production slang_db. Use --slang-db off. If slang checks are needed, use a temporary DB path only.
- Direct Naver/Bing fallback is degraded-provider evidence, not normal Docker/SearXNG shard approval.
- Latest source-correctness refresh used normal Docker/SearXNG shards, but it is only a targeted 39-row evidence refresh.
- Separate runtime integrity, targeted canary status, semantic quality, and full-scan approval in every report.
- Runtime completion is not semantic approval.
- Candidate preservation, HOLD, human_review, unresolved_matchable, or URL mismatch lint can be correct safer movement; do not force final official_title promotion.

Controls:
- 11694064 must not finalize as 무협 게임에 빙의했다. 문제는 나는 스토리를 보지 않는 스킵충이다. Correct direction is 판초우의의 마법사 or conservative HOLD/candidate conflict.
- Loop 1 wrong_work=9 must not regress into bad pipeline titles.
- active garbage_title_after must stay 0.
- Snippet/breadcrumb/platform/person/wiki/community page titles must not become final official_title.

Required Hermes Council Fan-Out:
Use Codex subagents aggressively when available. Prefer parallel fan-out for independent questions. If the subagent tool is unavailable or concurrency is full, record that and emulate the role in main Codex until a slot opens.

Required roles:
1. Candidate / Comment Expert
   - If a non-empty queue exists, inspect those queue rows. If the queue is 0, propose the next high-risk expansion or source-correctness refresh scope.
   - Identify comment answer attribution, comment-sourced title, recommendation candidate, multi-candidate, and short alias loss.
   - Propose candidate ledger/HOLD/human_review fixes without unsafe promotion.

2. OCR / Visual Evidence Expert
   - Identify whether OCR/title image evidence is needed or was dropped.
   - Separate direct image title evidence from visual-only/scene/character evidence.
   - Define VLM/OCR canary and placeholder/lazy image limitations.

3. Source / URL Hygiene Expert
   - Check official detail URL support, stale/wrong URL risk, mobile/detail canonicalization, and title-url mismatch lint.
   - This role is still required even when the active queue is not URL-hygiene dominated, because fixes can accidentally regress URL behavior.

4. Search / Web Evidence Expert
   - Use bounded web/search evidence when title correctness depends on external source.
   - Distinguish strong source evidence, snippet-only evidence, source drift, search degradation, and inaccessible pages.

5. Code Hook Expert
   - Map fixes to:
     - src/llm_batch/candidate_audit.py
     - src/llm_batch/agentic_pipeline.py
     - src/llm_batch/experts/orchestrator.py
     - src/llm_batch/prompts/prompt_router.py
     - src/llm_batch/mcp_bridge/server.py
     - src/llm_batch/search/client.py
     - expert_main.py
   - Propose focused tests. Avoid post_id/title hardcoding.

6. Prompt / Orchestration Expert
   - Improve LLM prompt/search intent for comments, OCR, short aliases, character/setting clusters, author/new-work context, and recommendation/multi-candidate preservation.
   - Ensure prompt wording separates final title promotion from candidate preservation.

7. Verification / Docs Expert
   - Define input split, canary commands, compare commands, controls, NO-GO conditions, and docs sync.
   - Keep REVIEW-LOCKED and full_scan_approval=false.

Optional challenge roles:
- Regression Skeptic: look only for over-promotion, wrong-work, garbage title, URL pollution, and controls regression.
- Data / Taxonomy Expert: check that stale deterministic aggregate is not mixed with native-web/current queue data.
- Tooling Expert: check helper/restart/compare/queue writer robustness.

Model And Tool Diversity:
- Use diverse models when useful and available, because the goal is variance reduction, not one-model consensus.
- Suggested split:
  - search/web/semantic challenge: gpt-5.5, high or xhigh reasoning
  - code hook/test mapping: gpt-5.4, high reasoning
  - prompt/docs/taxonomy fast review: gpt-5.4-mini or gpt-5.3-codex-spark
- If a requested model/provider/tool is unavailable in the active Codex session, record the limitation and continue with the strongest available local Codex/subagent path. Do not invent external-provider evidence.
- If a subagent can call web/search/browser or another approved tool independently, let it do so for bounded evidence gathering, then require the main Codex to verify the exact files, links, logs, or command outputs before changing code.
- Use diverse evidence paths:
  - local result/log/compare artifact inspection
  - code static analysis and unit tests
  - bounded web/search verification where needed
  - prompt/semantic/orchestration review
- Subagent output must include:
  - inspected inputs/files/sources
  - issue taxonomy by post_id
  - suspected root cause
  - proposed generalized fix
  - over-promotion risk
  - tests to add/update
  - canary rows affected
  - confidence and uncertainty

Main Codex Workflow:
1. Preflight:
    - Read active queue and report.
   - Treat Loop 12 fix2 next queue rows `0` as the latest active closure. Do not re-run Loop 12 as the main task unless using it as a regression control.
   - If continuing the goal, build Loop 13 from completed779 native-web non-ACCEPT residual coverage, source-correctness refresh, stale review rows, URL hygiene rows, or a new balanced high-risk expansion.
   - Treat `11718105` as a regression control for multi-title OCR work-cue preservation: do not force single-title promotion, but do preserve OCR work cues in `candidate_ledger`.
   - Treat `11705239`, `11702087`, `11716480`, and `11706832` as historical targeted controls unless new evidence shows a regression.
   - Read source-correctness refresh, Loop 5-12 compares, and deterministic full-post judge only as historical/control evidence before code changes.
   - Do not re-run closed Loop 4-12 queues as the main task unless they are explicitly selected as regression controls.
   - Verify any new source does not mix deterministic full-post aggregate with native-web/current queue data.
    - Verify current live vLLM model via http://10.20.0.101:8000/v1/models if a canary will run.
    - Check current git status and do not revert unrelated user changes.

2. Hermes Council fan-out:
   - Spawn at least the available independent subagents in parallel.
   - Use different models/tools where practical.
   - Prefer diverse expert roles and model/tool mixes when available:
     - search/web/semantic challenge: gpt-5.5 or strongest web-capable reasoning path
     - code hook/test mapping: code-focused model
     - taxonomy/docs/verification: faster lightweight model
     - tool paths: local artifact/log inspection, static code/test review, bounded web/search verification, prompt/orchestration critique
   - Continue non-overlapping local work while agents run.
   - When each agent returns, verify the claim against files/tests/canary evidence before adopting it.

3. Row-level diagnosis:
   - For each active row in the current or newly generated queue, produce a row diagnosis with:
     - observed signal in title/body/comment/OCR/search
     - why previous run stayed null/noise/unresolved
     - expected safe movement
     - generalized hook
     - over-promotion risk
     - test/canary requirement
   - Unknown-title rows may correctly become HOLD/human_review instead of resolved.
   - Before implementation, ensure each active queue row has non-empty `suspected_code_hook`, `proposed_next_fix`, and `required_test`.

Bucket Acceptance Map:
- candidate_comment_multi:
  - accepted movement: candidate_preserved, recommendation_candidates, secondary_reference_works, unresolved_matchable, HOLD, or human_review.
  - unsafe movement: forced single official_title from recommendation, comment-only ambiguity, joke/pronoun answer, or multi-work comparison.
- recall_relevance_representative:
  - accepted movement: resolved expected title+url when evidence is strong, candidate_preserved, unresolved_matchable, URL mismatch lint, HOLD, or human_review.
  - unsafe movement: bare short alias promotion, snippet/breadcrumb title promotion, or cross-media/OCR cue promotion without official/detail evidence.

4. Implement generalized fixes:
   - Candidate/comment preservation:
     - Preserve comment answer candidates and recommendation/multi-candidate candidates in candidate ledger.
     - Do not force a single title when evidence is comment-only, ambiguous, recommendation list, or multi-work comparison.
   - Recall/relevance recovery:
     - Recover direct title, strong alias, OCR explicit title, comment URL/title, and character/setting clusters when evidence is source-local and strong.
   - Search/prompt orchestration:
     - Add search intent probes for short aliases, comment answers, OCR text, and character/setting clusters that were previously suppressed.
   - Primary-selection precision:
     - If source-local alias/candidate conflicts with pipeline primary, prefer candidate conflict/HOLD over wrong_work finalization.
   - Source/URL safety:
     - Keep official detail URL guard and URL mismatch lint behavior. Do not regress Loop 2 source/url hygiene closure.

5. Tests:
   - Run py_compile for changed files and helpers.
   - Run focused tests relevant to changed hooks, including:
     .venv312\Scripts\python.exe -m unittest tests.test_candidate_audit tests.test_judge_seed_registry tests.test_title_lead_search_inferred_guard tests.test_agentic_pipeline_alias_contract tests.test_final_semantic_reread_gate tests.test_expert_main_comment_metadata tests.test_expert_main_input_loader tests.test_completed779_issue_index tests.test_completed779_compare tests.test_mcp_bridge_direct_search tests.test_search_client_health -v
   - Add/update tests for any new helper or guard.

6. Build next canary input:
   - For Loop 13, start from a fresh/random/high-risk expansion or a documented residual/control pool, because Loop 12 fix2 next queue is `0`.
   - Include regression controls for recently fixed rows: `11694064`, Loop 1 `wrong_work=9`, `11702087`, `11705239`, `11716480`, `11706832`, and `11718105`.
   - Use older Loop 5-12 queues only as residual diagnostic/control seeds, not as proof of full quality.
   - Create the next active seed from the native-web non-ACCEPT issue index, source-correctness residuals, stale review rows, URL hygiene rows, or a balanced high-risk expansion.
   - Split text/url/comment vs image/OCR if needed.
   - Use a new loop prefix for future loops and do not overwrite Loop 2-12, source-correctness refresh, or targeted fix artifacts.

7. Run expert_main canary:
   - Text/url/comment:
     .venv312\Scripts\python.exe expert_main.py <HERMES_TEXT_INPUT> --server-type vllm --llm-endpoint http://10.20.0.101:8000 --llm-model <LIVE_MODEL> --reuse-shards-only --no-dashboard --slang-db off --parallel <min(input_count,36)>
   - Image/OCR:
     .venv312\Scripts\python.exe expert_main.py <HERMES_IMAGE_INPUT> --server-type vllm --llm-endpoint http://10.20.0.101:8000 --llm-model <LIVE_MODEL> --reuse-shards-only --no-dashboard --slang-db off --parallel <min(input_count,36)> --vlm on --ocr on --require-vlm-ocr-for-images
   - If direct fallback is used, label the run degraded-provider.
   - If preflight blocks execution, write exact failure and resume command.

8. Compare and requeue:
   - Compare before/after against the active queue.
   - Write loop-specific combined result and compare artifacts.
   - Write the next queue with row-level rationale.
   - If the next queue is non-empty, repeat the loop unless every row is explicitly HOLD/human_review/INFO_MISSING/quarantine/no_generalizable_fix_left.

9. Acceptance audit:
   - active queue rows should move to candidate preserved, unresolved_matchable, HOLD/human_review, resolved expected title when evidence is strong, or explicit no_generalizable_fix_left.
   - active garbage_title_after remains 0.
   - 11694064 bad title does not return.
   - wrong_work=9 does not regress.
   - Any unsafe over-promotion is semantic NO-GO for that fix loop.
   - For `11702087`, regression means returning to no-search/noise or demoting the already supported `괴담 호텔 탈출기` + NovelPia URL path without stronger contrary evidence.
   - For `11705239`, regression means promoting a memory-query/search-hit title despite recommendation/memory-query ambiguity.
   - For `11716480`, acceptable movement is close OCR title preserved with URL lint, official detail URL found and verified, or explicit HOLD. Regression means weak_visual_only/noise, generic `인터넷 방송인`/cross-domain title promotion, or a mismatched URL.

10. Docs/checklist sync:
   - Update:
     - goal.md
     - docs/devs/COMPLETED779_HERMES_CONTINUOUS_GOAL_PROMPT.md if the operating contract changes
     - docs/devs/TODO.md
     - docs/devs/CHECKLIST.md
     - docs/devs/HISTORY.md
     - docs/devs/IMPROVEMENT_REGISTER.md
     - docs/devs/VERIFICATION_RESULTS.md
   - Keep runtime integrity, targeted canary status, semantic quality, and full-scan approval separate.
   - Run git diff --check.

Completion Criteria:
- Queue is empty, or all remaining rows are explicitly HOLD/human_review/INFO_MISSING/unresolved_matchable/quarantine/no_generalizable_fix_left with row-level rationale.
- Subagent fan-out was attempted and recorded; if unavailable, the limitation is documented.
- Generalized fixes avoid post_id/title hardcoding.
- Canary and compare evidence exists, or exact preflight blocker and resume commands exist.
- Controls are audited.
- Docs/checklists/history/register/verification are updated.
- semantic_quality remains REVIEW-LOCKED.
- full_scan_approval remains false.
```

## Operator Notes

- This prompt supersedes the one-shot Loop 2 prompt for future completed779 improvement work.
- Loop 2 through Loop 12 and source-correctness refresh evidence remain valid historical evidence.
- Loop 12 is now the latest active closure. Its fix2 next queue rows `0`, so the next main work should open Loop 13 from a fresh expansion/residual/control pool.
- The Loop 5 operational residual queue `24` rows remains useful as a diagnostic/control source, but it is not the current hard-fail queue.
- Loop 7 text `14/16` was the historical pre-fix1 state. Current text combined status is `16/16`.
- Model diversity is useful for variance reduction, but it is not voting. Main Codex must verify with artifacts and conservative gates.
- If subagent concurrency is limited, start with the highest-value independent roles, close completed agents, then fan out the remaining roles.
- Loop 5 postfix1 / Loop 6 note: `11698880` is now protected by final source/url hygiene expected-title conflict guard, but upstream title/body multi-candidate orchestration remains open. Future loops should treat it as an upstream design/control case, not as an already-approved semantic fix.
- Loop 7 `11702087` note: downstream guard suppression is targeted-closed by fix9. Use it as a regression control, not the next P0 target.

## Loop 7 Fix1 Update 2026-06-23

- Loop 7 text is no longer `14/16` partial:
  - `11702087` is recovered by fix9.
  - `11705239` is quarantined, fixed, and rerun as `out/completed779_improvement_goal_20260622/canary/hermes_loop7_text_single_11705239_fix1_result.json`.
  - text combined result is `out/completed779_improvement_goal_20260622/canary/hermes_loop7_broader_residual_text_combined_fix1_result.json`, rows `16/16`.
- Loop 7 image/OCR is now partial:
  - broad image/OCR run `20260623_052157_158066` produced `19/20` rows.
  - missing/quarantined row is `11716480`.
  - `11716480` single rerun `20260623_061321_455105` also failed to flush a result after reaching strong OCR/Jury evidence.
- Active runtime blocker:
  - Historical fix1/fix2 target was `quarantine/runtime_postprocess_hang`.
  - This is superseded by fix6, where the single-row run completed `1/1`; keep the old command only as lineage, not as the next command.
  - Historical resume/debug command:
    `.venv312\Scripts\python.exe expert_main.py out\completed779_improvement_goal_20260622\inputs\hermes_loop7_image_ocr_single_11716480_quarantine.jsonl --output out\completed779_improvement_goal_20260622\canary\hermes_loop7_image_ocr_single_11716480_fix2_result.json --server-type vllm --llm-endpoint http://10.20.0.101:8000 --llm-model bg-digitalservices/Gemma-4-26B-A4B-it-NVFP4 --reuse-shards-only --no-dashboard --slang-db off --parallel 1 --vlm on --ocr on --require-vlm-ocr-for-images`
- New P0 fix hooks from Loop 7 fix1:
  - Preserve VLM/OCR `official_detail_page` direct title in the candidate ledger even when search `candidate_map` lacks the exact OCR title.
  - Block generic parenthetical search titles such as `인터넷 방송인` from outranking image-local direct title evidence.
  - Limit repeated decoder recall over genre/adult tags when VLM already provides explicit title, author, episode, and UI metadata.
  - Fix author normalization that truncates `후타보로` to `후타보`.
  - Add a postprocess watchdog/checkpoint-safe path around canonical suspect correction, J10 exception, and confidence normalization.
- Current compares:
  - text compare: `out/completed779_improvement_goal_20260622/compare/hermes_loop7_broader_residual_text_fix1_compare.json`.
  - image partial compare: `out/completed779_improvement_goal_20260622/compare/hermes_loop7_broader_residual_image_ocr_fix1_compare.json`.
  - combined partial compare: `out/completed779_improvement_goal_20260622/compare/hermes_loop7_broader_residual_combined_fix1_partial35_compare.json`, rows `35/35`.
  - active semantic queue: `out/completed779_improvement_goal_20260622/hermes_loop7_broader_residual_next_queue_fix1_partial35.json`, rows `12`, plus runtime quarantine `11716480`.
- Continue to keep:
  - semantic_quality: `REVIEW-LOCKED`
  - full_scan_approval: `false`
  - `slang_db` write-back: off unless explicitly requested

## Loop 7 Fix6 Update 2026-06-23

- `11716480` runtime quarantine is targeted-closed:
  - fix2/fix3: no flushed result/checkpoint.
  - fix4: runtime completed `1/1`, but semantic failed because first-pass VLM stayed `weak_visual_only` with no OCR/title/author.
  - fix5: OCR title recovered, but close OCR variant was demoted by expected-title hygiene mismatch.
  - fix6: completed/flushed/pending/failed `1/1/0/0`.
- fix6 evidence:
  - result: `out/completed779_improvement_goal_20260622/canary/hermes_loop7_image_ocr_single_11716480_fix6_result.json`
  - manifest: `out/completed779_improvement_goal_20260622/canary/hermes_loop7_image_ocr_single_11716480_fix6_result_manifest.json`
  - compare: `out/completed779_improvement_goal_20260622/compare/hermes_loop7_image_ocr_single_11716480_fix6_compare.json`
  - remaining queue: `out/completed779_improvement_goal_20260622/compare/hermes_loop7_image_ocr_single_11716480_fix6_remaining_queue.json`, rows `0`
- fix6 final state:
  - `official_title=여대생 가랑이 사이 무릎 끓은 엄마들`
  - `work_resolution=resolved`
  - `title_resolution_state=resolved`
  - `title_resolution_allowed=true`
  - `heretic_url=null`
  - lint: `judge_hygiene_seed_heretic_url_null`
  - compare movement: `url_lint_preserved=1`
- Generalized fix hooks now in scope:
  - focused OCR retry when first-pass VLM chunks are all weak visual and textless.
  - VLM retry merge preserves stronger structural fields.
  - source/url hygiene expected-title guard accepts close OCR/title variants instead of demoting them.
- Active next work:
  - regenerate Loop 7 final combined `36/36` accounting if needed.
  - continue the `12` row semantic next queue from `hermes_loop7_broader_residual_next_queue_fix1_partial35.json`.
  - keep `11716480` as URL/source hygiene residual, not runtime quarantine.
  - keep search/query pruning and official URL discovery as future loops.

## Loop 7 Fix17 Update 2026-06-23

- Loop 7 final combined accounting is closed:
  - final combined result: `out/completed779_improvement_goal_20260622/canary/hermes_loop7_broader_residual_combined_fix6_final36_result.json`, rows `36/36`.
  - fix7 compare: `out/completed779_improvement_goal_20260622/compare/hermes_loop7_broader_residual_combined_fix7_unwrapped_final36_compare.json`, rows `36/36`.
  - fix7 next queue: `out/completed779_improvement_goal_20260622/hermes_loop7_broader_residual_next_queue_fix7_unwrapped_final36.json`, rows `2`.
- Targeted residual closure:
  - `11711600` closed by candidate preservation for `망할 놈의 아카데미`.
  - `11706832` fix17 resolved `황제폐하가 웹소설 작가임을 숨김` with `https://novelpia.com/novel/385635`.
  - fix17 compare: `out/completed779_improvement_goal_20260622/compare/hermes_loop7_fix17_j11_alias_lock_11706832_compare.json`, movement `resolved_expected_title=1`.
  - fix17 next queue: `out/completed779_improvement_goal_20260622/hermes_loop7_fix17_j11_alias_lock_next_queue.json`, rows `0`.
- Current start point for the next pasted goal:
  - Do not rerun Loop 7 as the main task unless using it as regression control.
  - Build the next queue from completed779 native-web non-ACCEPT residual coverage, source-correctness refresh, stale review rows, URL hygiene rows, or a new balanced high-risk expansion.
  - Keep regression controls: `11694064`, Loop 1 `wrong_work=9`, `11702087`, `11705239`, `11716480`, `11706832`.
  - Keep `semantic_quality=REVIEW-LOCKED` and `full_scan_approval=false`.

## Loop 12 Fix2 Update 2026-06-23

- Loop 12 reopened fresh completed779 coverage after Loop 11 queue `0`.
  - fresh queue: `out/completed779_improvement_goal_20260622/hermes_loop12_fresh_expansion_queue.json`, rows `43`, text/url/comment `14`, image/OCR `29`, duplicate `0`.
  - text result: `out/completed779_improvement_goal_20260622/canary/hermes_loop12_fresh_expansion_text_result.json`, rows `14/14`.
  - image/OCR result: `out/completed779_improvement_goal_20260622/canary/hermes_loop12_fresh_expansion_image_ocr_result.json`, rows `29/29`, VLM/OCR `READY`.
  - combined compare: `out/completed779_improvement_goal_20260622/compare/hermes_loop12_fresh_expansion_combined_compare.json`.
  - combined movement: `candidate_or_human_review_preserved=28`, `candidate_preserved_with_benign_prune=8`, `candidate_preserved_with_prune_review=1`, `resolved_expected_title=2`, `resolved_expected_title_and_url=2`, `url_lint_preserved=2`.
  - pre-fix next queue: `out/completed779_improvement_goal_20260622/hermes_loop12_fresh_expansion_next_queue.json`, rows `1`, post_id `11718105`.
- Targeted generalized fixes:
  - `candidate_audit.py` protects judge expected `multiple:` members from weak `llm_only` sentence pruning.
  - `candidate_audit.py` preserves image OCR `work_cues` in the candidate ledger for unresolved/multi/adjacent non-resolved rows without promoting `official_title`.
  - `tests/test_candidate_audit.py` covers both behaviors.
- `11718105` fix2 evidence:
  - result: `out/completed779_improvement_goal_20260622/canary/hermes_loop12_fix2_ocr_work_cues_11718105_image_ocr_result.json`.
  - compare: `out/completed779_improvement_goal_20260622/compare/hermes_loop12_fix2_ocr_work_cues_11718105_compare.json`, movement `candidate_or_human_review_preserved=1`.
  - next queue: `out/completed779_improvement_goal_20260622/hermes_loop12_fix2_ocr_work_cues_next_queue.json`, rows `0`.
  - candidate ledger includes OCR work cues for `1990 할리우드 망나니 배우가 되었다`, `포수가 육아를 잘함`, `미국 트러커가 골동품으로 대박남`, `몰락민족의 천재 기사`.
- Current start point for the next pasted goal:
  - Do not rerun Loop 12 as the main task unless using it as regression control.
  - Open Loop 13 from completed779 native-web non-ACCEPT residual coverage, source-correctness refresh, stale review rows, URL hygiene rows, or a new balanced high-risk expansion.
  - Keep regression controls: `11694064`, Loop 1 `wrong_work=9`, `11702087`, `11705239`, `11716480`, `11706832`, `11718105`.
  - Keep `semantic_quality=REVIEW-LOCKED` and `full_scan_approval=false`.
