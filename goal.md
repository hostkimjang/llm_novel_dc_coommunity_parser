# completed779 Hermes Continuous Improvement Goal

이 문서는 completed subset `779`건의 Codex-native web judge 기반 개선을 한 번짜리 loop로 끝내지 않고, 남은 queue가 비거나 명시적으로 HOLD/human_review/quarantine 처리될 때까지 반복하는 active operating contract다. 이전 JUDGE3905/LLM judge goal 본문은 `llm_judge_goal.md`에 보관하고, Loop 1/Loop 2 실행 증거는 아래 과거 섹션에 보존한다.

## Active Objective

Post-Loop16 Claude review blocker fix: Claude external review of Codex session `019ee9ee` found that Loop16's new title-lead precision block broke two rank1 load-bearing regressions. The failure was reproduced locally with `tests.test_agentic_pipeline_rank1_lock_block tests.test_agentic_pipeline_rank2_ocr_catalog_evidence tests.test_agentic_pipeline_rank3_lock_anchor -v`: `Rank1ChokepointDemoteTest.test_verifier_critical_demotes_but_preserves_title` and `test_official_detail_matched_url_exempt_from_demote` failed because `_title_lead_alias_precision_block_signal` treated verifier `critical/major` counterarguments as a hard rescue block after rank1 had already demoted-but-preserved the candidate. Fix applied: remove `critical_or_major` from `_title_lead_alias_precision_block_signal`; verifier critical/major remains owned by rank1, while the new title-lead precision gate handles relation/competition/comment-meta only. Reverification: rank1/2/3 suite `40 tests OK`, completed779 focused suite plus rank1/2/3 `126 tests OK`, `py_compile` pass. Future completed779/Hermes verification commands must include the rank1/2/3 modules.

Hermes Loop 16은 Loop 15 queue `0`을 full approval로 보지 않고 post-Loop15 residual/control pool을 다시 열었다. 새 queue는 `out/completed779_improvement_goal_20260622/hermes_loop16_post_loop15_residual_queue.json` rows `7`이며 main `0`, controls `7`, text/url/comment `2`, image/OCR `5`, duplicate `0`이다. `main_excluded_id_count=266`으로 native-web non-ACCEPT action rows는 consumed/excluded 상태였고, 이번 loop는 sentinel/regression controls 검증이었다. Final control result는 `out/completed779_improvement_goal_20260622/canary/hermes_loop16_final_control_result.json` rows `7`; compare는 `out/completed779_improvement_goal_20260622/compare/hermes_loop16_final_control_compare.json`; latest hard next queue는 `out/completed779_improvement_goal_20260622/hermes_loop16_final_control_next_queue.json` rows `0`이다. Semantic quality는 계속 `REVIEW-LOCKED`, full-scan approval은 `false`다.

Current Loop 16 evidence:

- Council/subagent fan-out:
  - Candidate/Comment+Prompt, OCR/Visual, Source/URL+Web, Code Hook, Verification/Docs, Regression/Data 6축을 병렬로 실행했다.
  - subagent 결과는 승인 근거가 아니라 메인 Codex가 파일/테스트/canary/compare로 재확인한 challenger/explorer 입력이다.
  - Source/URL expert는 `판초우의의 마법사` Munpia `https://novel.munpia.com/530500`, `괴담 호텔 탈출기` NovelPia `https://novelpia.com/novel/102155`, `아카데미 생존 갤러리` NovelPia `https://novelpia.com/novel/380218`, `즉사기 들고 무림에 떨어지다` Munpia/Naver source를 확인했다.
- Loop 16 queue/runtime:
  - queue: `out/completed779_improvement_goal_20260622/hermes_loop16_post_loop15_residual_queue.json`, rows `7`, main `0`, controls `7`, text/url/comment `2`, image/OCR `5`, duplicate `0`.
  - text result: `out/completed779_improvement_goal_20260622/canary/hermes_loop16_post_loop15_residual_text_result.json`, completed/failed/pending `2/0/0`, VLM/OCR `NOT_APPLICABLE`, log `logs/expert_run_20260623_185717_814007.log`.
  - image/OCR result: `out/completed779_improvement_goal_20260622/canary/hermes_loop16_post_loop15_residual_image_ocr_result.json`, completed/failed/pending `5/0/0`, VLM/OCR `READY`, log `logs/expert_run_20260623_211124_636740.log`.
  - final control result: `out/completed779_improvement_goal_20260622/canary/hermes_loop16_final_control_result.json`, rows `7`, post_ids `11694064`, `11698880`, `11702055`, `11710037`, `11710045`, `11718077`, `11718105`.
- Loop 16 code/tooling changes:
  - `tools/compare_completed779_improvement.py`: recall/candidate rows with matching expected title but wrong expected URL now stay `title_match_url_still_mismatched` instead of closing as resolved.
  - `src/llm_batch/candidate_audit.py`: seed-conflict and trope-boundary demotions now scrub `reason_lines` and sync final `reason`, so public-title confirmation text is removed when the structure is HOLD/candidate.
  - `src/llm_batch/candidate_audit.py`: hygiene/recall expected seed rows now record candidate-audit lint when expected candidates are preserved but polluted by concrete alternate official/mixed candidates.
  - tests cover wrong URL compare retention, seed-conflict reason scrub, trope-boundary reason scrub, and noisy expected-candidate lint.
- Loop 16 focused validation:
  - focused result: `out/completed779_improvement_goal_20260622/canary/hermes_loop16b_focused_scrub_lint_result.json`, rows `3/3`, VLM/OCR `READY`, log `logs/expert_run_20260623_213513_009298.log`.
  - `11710037` now has public `official_title=null`, `title_resolution_state=adjacent`, `title_resolution_allowed=false`, and reason text says boundary HOLD/candidate preservation instead of final title confirmation.
  - `11718105` now stays author/platform-meta adjacent with multi-title candidates preserved, not a single wrong promoted work.
  - `11698880` final sync result: `out/completed779_improvement_goal_20260622/canary/hermes_loop16d_11698880_reason_sync_result.json`, completed/failed/pending `1/0/0`, VLM/OCR `READY`, log `logs/expert_run_20260623_214642_901985.log`. Final public title is null and reason text says `미확정 (judge seed conflict; 후보/HOLD로 보존)` with confirmation text removed.
- Loop 16 compare/closure:
  - final compare movement: `blocked_or_candidate_preserved=1`, `candidate_or_human_review_preserved=3`, `url_lint_preserved=3`.
  - latest next queue: `out/completed779_improvement_goal_20260622/hermes_loop16_final_control_next_queue.json`, rows `0`.
  - `11694064` sentinel still does not regress to `무협 게임에 빙의했다...스킵충이다`; `판초우의의 마법사` remains candidate/HOLD with official URL evidence.
- Loop 16 verification:
  - `py_compile`: pass for `expert_main.py`, touched pipeline modules, helper tools, and touched tests.
  - focused suite: `tests.test_candidate_audit tests.test_completed779_compare tests.test_completed779_hermes_expansion tests.test_agentic_pipeline_rework.AgenticPipelineReworkTest.test_relation_hold_blocks_indirect_character_scene_title_resolution -v`, `86 tests OK`.
  - `git diff --check`: pass with LF/CRLF warnings only.
- Known limitation:
  - Loop 16 queue `0` is targeted/control closure. It is not completed779 full semantic approval.
  - `11698880` shows the pipeline can strongly find a plausible alternate work (`가챠 중독자의 퓨전펑크 생활`) while the seed expects `아카데미 생존 갤러리`; current safe behavior is candidate/HOLD, not public promotion.
  - `11718077` still uses mobile Munpia detail URL in output while seed expected a Naver/Munpia canonical source distinction. This is preserved as URL-lint evidence, not full source canonical approval.

Hermes Loop 15는 Loop 14 queue `0`을 full approval로 보지 않고, 남은 action row와 regression controls를 다시 열었다. Loop 15 queue는 `out/completed779_improvement_goal_20260622/hermes_loop15_remaining_expansion_queue.json` rows `6`이며 main `1`, controls `5`, text/url/comment `2`, image/OCR `4`, duplicate `0`이다. 유일한 새 main row `11710037`은 `trope_or_author_talk_risk`로, 정답 후보 `담텔기 -> 괴담 호텔 탈출기`는 보존해야 하지만 public `official_title`로 확정하면 안 되는 boundary case였다. Pre-fix text canary는 이를 public title로 과승격했으므로 compare retaxonomy와 `candidate_audit` guard를 보강했고, fix1 text rerun과 image/OCR control rerun을 합친 latest hard next queue는 `out/completed779_improvement_goal_20260622/hermes_loop15_combined_fix1_next_queue.json` rows `0`이다. 이 closure는 completed779 Loop15 targeted/control closure이며 full approval이 아니다. Semantic quality는 계속 `REVIEW-LOCKED`, full-scan approval은 `false`다.

Current Loop 15 evidence:

- Council/subagent fan-out:
  - Candidate/Comment+Prompt, OCR/Visual, Source/URL+Web, Code Hook, Verification/Docs, Regression/Data 6축을 병렬로 실행했다.
  - subagent 결과는 승인 근거가 아니라 메인 Codex가 파일/테스트/canary/compare와 bounded web evidence로 재확인한 challenger/explorer 입력이다.
  - Source/URL expert의 웹 검증과 메인 확인 기준 공식 detail: `괴담 호텔 탈출기` NovelPia `https://novelpia.com/novel/102155`, `판초우의의 마법사` Munpia `https://novel.munpia.com/530500`, `아카데미 생존 갤러리` NovelPia `https://novelpia.com/novel/380218`.
- Loop 15 queue:
  - queue: `out/completed779_improvement_goal_20260622/hermes_loop15_remaining_expansion_queue.json`, rows `6`, main `1`, controls `5`, text/url/comment `2`, image/OCR `4`, duplicate `0`.
  - input manifest/report: `out/completed779_improvement_goal_20260622/inputs/hermes_loop15_remaining_expansion_input_manifest.json`.
  - text rows: `11710037`, `11694064`.
  - image/OCR rows: `11698880`, `11702055`, `11710045`, `11718105`.
  - manifest records `main_excluded_id_count=265`; Loop15's single main residual is not evidence of full approval, only that prior queue paths consumed almost all indexed non-ACCEPT action rows.
- Loop 15 pre-fix finding:
  - pre-fix text result: `out/completed779_improvement_goal_20260622/canary/hermes_loop15_remaining_expansion_text_result.json`, completed/failed/pending `2/0/0`, VLM/OCR `NOT_APPLICABLE`, log `logs/expert_run_20260623_181313_128318.log`.
  - `11710037` was incorrectly public-resolved to `괴담 호텔 탈출기` even though the safe target is candidate/HOLD preservation for a trope/technique discussion.
  - retaxonomy compare: `out/completed779_improvement_goal_20260622/compare/hermes_loop15_trope_boundary_retaxonomy_text_compare.json`, movement includes `boundary_title_over_promoted=1`; this pre-fix result is a confirmed regression signal, not closure evidence.
- Loop 15 fix1:
  - `src/llm_batch/candidate_audit.py`: added `apply_judge_seed_trope_boundary_hold_guard` for `trope_or_author_talk_risk`. It preserves expected title/url as candidate evidence, demotes matching public final title, and forces `title_resolution_state=adjacent`, `title_resolution_allowed=false`, `work_resolution=unresolved`.
  - `expert_main.py`: calls the trope boundary guard before final candidate audit field materialization.
  - `tools/compare_completed779_improvement.py`: adds `boundary_title_over_promoted` so trope/author boundary seeds cannot close as resolved expected title.
  - tests cover both the guard and compare requeue behavior.
- Loop 15 fix1 text canary:
  - result: `out/completed779_improvement_goal_20260622/canary/hermes_loop15_fix1_trope_boundary_text_result.json`, completed/failed/pending `2/0/0`, VLM/OCR `NOT_APPLICABLE`, log `logs/expert_run_20260623_182142_351153.log`.
  - compare: `out/completed779_improvement_goal_20260622/compare/hermes_loop15_fix1_trope_boundary_text_compare.json`, movement `blocked_or_candidate_preserved=1`, `candidate_or_human_review_preserved=1`, requeue `0`.
  - `11710037` now preserves `괴담 호텔 탈출기` as candidate with `https://novelpia.com/novel/102155`, while public `official_title` remains null/HOLD.
  - `11694064` sentinel preserves `판초우의의 마법사` candidate with `https://novel.munpia.com/530500` and does not regress to `무협 게임에 빙의했다...스킵충이다`.
- Loop 15 image/OCR controls:
  - result: `out/completed779_improvement_goal_20260622/canary/hermes_loop15_remaining_expansion_image_ocr_result.json`, completed/failed/pending `4/0/0`, VLM/OCR `READY`, log `logs/expert_run_20260623_182710_899488.log`.
  - compare: `out/completed779_improvement_goal_20260622/compare/hermes_loop15_remaining_expansion_image_ocr_compare.json`, movement `candidate_or_human_review_preserved=2`, `url_lint_preserved=2`, requeue `0`.
  - `11710045` remains public-title null/HOLD. It still shows noisy candidate surfaces (`적국의 황녀를 임신 시켰다`, `넣어 키운 걸그룹`, and UI/OCR residue), so candidate pollution remains a future prompt/orchestration audit note, not a full approval claim.
- Loop 15 combined closure:
  - combined result: `out/completed779_improvement_goal_20260622/canary/hermes_loop15_combined_fix1_result.json`, rows `6`, duplicate `0`.
  - combined compare: `out/completed779_improvement_goal_20260622/compare/hermes_loop15_combined_fix1_compare.json`, movement `blocked_or_candidate_preserved=1`, `candidate_or_human_review_preserved=3`, `url_lint_preserved=2`.
  - latest hard next queue: `out/completed779_improvement_goal_20260622/hermes_loop15_combined_fix1_next_queue.json`, rows `0`.
- Loop 15 verification:
  - `py_compile`: pass for `expert_main.py`, `src/llm_batch/candidate_audit.py`, `tools/compare_completed779_improvement.py`, `tests/test_candidate_audit.py`, `tests/test_completed779_compare.py`.
  - focused suite: `tests.test_candidate_audit tests.test_completed779_compare tests.test_completed779_hermes_expansion tests.test_agentic_pipeline_rework.AgenticPipelineReworkTest.test_relation_hold_blocks_indirect_character_scene_title_resolution -v`, `84 tests OK`.
  - `git diff --check`: pass with LF/CRLF warnings only after docs sync.
- Known limitation:
  - Loop 15 queue `0` is targeted/control closure. It is not completed779 full semantic approval.
  - `11710045` candidate pollution, Munpia mobile URL evidence strength normalization, `trope_or_author_talk_risk` split into `trope_boundary_hold` vs `author_meta_boundary_hold`, and queue-only exclude vs compare-verified consumed manifest remain future work.
  - Loop 15 did not include prior Loop14 control `11718077`; this is a control coverage note for the next loop, not a runtime failure.

Historical Loop 14 evidence:

- Council/subagent fan-out:
  - Candidate/Comment, OCR/Visual, Source/URL, Code Hook, Prompt/Orchestration 5축 결과를 확보했고, Verification/Docs subagent는 context-window error로 limitation 기록 후 메인 Codex가 직접 검증/문서 sync를 수행했다.
  - Regression Skeptic/Data Taxonomy 추가 spawn은 thread limit으로 실패했다. subagent 결과는 승인 근거가 아니라 메인 Codex가 파일/테스트/canary/compare로 재확인한 challenger/explorer 입력이다.
- Loop 13 retaxonomy before Loop 14:
  - recompare: `out/completed779_improvement_goal_20260622/compare/hermes_loop13_retaxonomy_source_url_fix_combined_compare.json`.
  - movement: `blocked_or_candidate_preserved=8`, `boundary_hold_preserved=4`, `candidate_or_human_review_preserved=31`, `candidate_preserved_with_benign_prune=3`, `resolved_expected_title=1`, `title_or_url_still_mismatched=2`, `url_lint_preserved=2`.
  - next queue: `out/completed779_improvement_goal_20260622/hermes_loop13_retaxonomy_source_url_fix_next_queue.json`, rows `2`: `11698880`, `11702055`.
- Loop 14 remaining expansion v2:
  - queue: `out/completed779_improvement_goal_20260622/hermes_loop14_remaining_expansion_v2_queue.json`, rows `22`, main `16`, controls `6`, text/url/comment `8`, image/OCR `14`, duplicate `0`.
  - controls include `11694064`, `11698880`, `11702055`, `11710045`, `11718105`, and source-refresh URL lint residual `11718077`.
  - buckets: `explicit_regression_control=5`, `fallback_unseen_high_risk=7`, `source_refresh_url_lint_residual=1`, `under_resolved=3`, `wrong_relevance=6`.
  - input manifest/report: `out/completed779_improvement_goal_20260622/inputs/hermes_loop14_remaining_expansion_v2_input_manifest.json`.
- Loop 14 v2 canary:
  - text result: `out/completed779_improvement_goal_20260622/canary/hermes_loop14_remaining_expansion_v2_text_result.json`, rows `8/8`, failed `0`, pending `0`, VLM/OCR `NOT_APPLICABLE`, log `logs/expert_run_20260623_170021_835831.log`.
  - image/OCR result: `out/completed779_improvement_goal_20260622/canary/hermes_loop14_remaining_expansion_v2_image_ocr_result.json`, rows `14/14`, failed `0`, pending `0`, VLM/OCR `READY`, log `logs/expert_run_20260623_170801_748203.log`. `--reuse-shards-only` health filter로 effective parallel은 `2`였다.
  - combined result: `out/completed779_improvement_goal_20260622/canary/hermes_loop14_remaining_expansion_v2_combined_result.json`, rows `22`, duplicate `0`.
- Loop 14 v2 compare:
  - combined compare: `out/completed779_improvement_goal_20260622/compare/hermes_loop14_remaining_expansion_v2_combined_compare.json`, movement `blocked_or_candidate_preserved=1`, `boundary_hold_preserved=2`, `candidate_or_human_review_preserved=14`, `candidate_preserved_with_benign_prune=1`, `resolved_expected_title=1`, `title_or_url_still_mismatched=2`, `url_lint_preserved=1`.
  - next queue: `out/completed779_improvement_goal_20260622/hermes_loop14_remaining_expansion_v2_next_queue.json`, rows `2`: `11698880`, `11702055`.
  - `11694064` sentinel은 `무협 게임에 빙의했다...스킵충이다`로 회귀하지 않았고, `11710045`도 unexpected public title로 재승격하지 않았다.
- Loop 14 fix1:
  - queue/input: `out/completed779_improvement_goal_20260622/hermes_loop14_fix1_hygiene_expected_candidate_v2_queue.json`, rows `2`, image/OCR `2`.
  - result: `out/completed779_improvement_goal_20260622/canary/hermes_loop14_fix1_hygiene_expected_candidate_v2_image_ocr_result.json`, completed/failed/pending `2/0/0`, VLM/OCR `READY`, log `logs/expert_run_20260623_174842_756421.log`.
  - compare: `out/completed779_improvement_goal_20260622/compare/hermes_loop14_fix1_hygiene_expected_candidate_v2_compare.json`, movement `url_lint_preserved=2`.
  - next queue: `out/completed779_improvement_goal_20260622/hermes_loop14_fix1_hygiene_expected_candidate_v2_next_queue.json`, rows `0`.
  - both `11698880` and `11702055` now record `expected_title_preserved=true` and `expected_url_preserved=true` before being closed as URL lint preservation.
- Loop 14 code/tooling changes:
  - `tools/build_completed779_hermes_expansion.py`: explicit `--control-post-id` controls can include consumed sentinel rows, and `--clear-default-main-targets` no longer falls back to default targets.
  - `tools/compare_completed779_improvement.py`: source/url hygiene cannot close on lint alone when expected title is missing from final/candidates; expected-null rows with new public title become `unexpected_resolved_title`.
  - `src/llm_batch/candidate_audit.py`: judge-seeded expected title/url preservation now also applies to `group=hygiene` rows without promoting public title.
  - `tests/test_completed779_hermes_expansion.py`, `tests/test_completed779_compare.py`, `tests/test_candidate_audit.py` include regressions for those behaviors.
- Loop 14 verification:
  - `py_compile`: pass for `expert_main.py`, `src/llm_batch/candidate_audit.py`, `src/llm_batch/agentic_pipeline.py`, `tools/compare_completed779_improvement.py`, `tools/build_completed779_hermes_expansion.py`, and touched tests.
  - focused suite: `tests.test_candidate_audit tests.test_completed779_compare tests.test_completed779_hermes_expansion tests.test_agentic_pipeline_rework.AgenticPipelineReworkTest.test_relation_hold_blocks_indirect_character_scene_title_resolution -v`, `82 tests OK`.
  - final `git diff --check` is run after this docs sync.
- Known limitation:
  - Loop 14 queue `0` is a targeted expansion/fix closure. It is not completed779 full semantic approval.
  - Prompt/orchestration issues called out by subagents remain future work: snippet analyzer prompt drift, central promotion gate consolidation, comment/recommendation role separation, and URL canonicalization/source-tier ownership.

Historical Loop 13 evidence:

- Council/subagent fan-out:
  - Source/URL, Search/Web, Candidate/Comment retry, Prompt/Orchestration, Code Hook, OCR/Visual 6축을 병렬로 실행했다.
  - subagent 결과는 승인 근거가 아니라 메인 Codex가 파일/테스트/canary/compare로 재확인한 challenger/explorer 입력이다.
- Loop 13 residual expansion:
  - queue: `out/completed779_improvement_goal_20260622/hermes_loop13_residual_expansion_queue.json`, rows `51`, main `39`, controls `12`, text/url/comment `9`, image/OCR `42`, duplicate `0`.
  - buckets: `fallback_unseen_high_risk=24`, `under_resolved=6`, `under_resolved_false_negative=3`, `wrong_relevance=6`, `loop13_source_regression_review_residual=8`, `loop13_source_regression_url_lint_residual=4`.
  - input manifest: `out/completed779_improvement_goal_20260622/inputs/hermes_loop13_residual_expansion_input_manifest.json`.
- Loop 13 canary:
  - text result: `out/completed779_improvement_goal_20260622/canary/hermes_loop13_residual_expansion_text_result.json`, rows `9/9`, failed `0`, pending `0`, VLM/OCR `NOT_APPLICABLE`, log `logs/expert_run_20260623_150842_142186.log`.
  - image/OCR result: `out/completed779_improvement_goal_20260622/canary/hermes_loop13_residual_expansion_image_ocr_result.json`, rows `42/42`, failed `0`, pending `0`, VLM/OCR `READY`, log `logs/expert_run_20260623_151732_213768.log`. `--reuse-shards-only` health filter로 effective parallel은 `2`였다.
  - combined result: `out/completed779_improvement_goal_20260622/canary/hermes_loop13_residual_expansion_combined_result.json`, rows `51`, duplicate `0`.
- Loop 13 compare:
  - combined compare: `out/completed779_improvement_goal_20260622/compare/hermes_loop13_residual_expansion_combined_compare.json`, movement `blocked_or_candidate_preserved=8`, `boundary_hold_preserved=4`, `candidate_or_human_review_preserved=31`, `candidate_preserved_with_benign_prune=3`, `resolved_expected_title=1`, `url_lint_preserved=4`.
  - next queue: `out/completed779_improvement_goal_20260622/hermes_loop13_residual_expansion_next_queue.json`, rows `0`.
  - sentinel `11694064`는 `무협 게임에 빙의했다...스킵충이다`로 회귀하지 않았고, title null/promotion_blocked 상태로 unsafe wrong-work 확정을 피했다.
- Loop 13 code/tooling changes:
  - `tools/compare_completed779_improvement.py`: expected title이 없는 wrong-relevance/boundary HOLD를 `boundary_hold_preserved`로 닫고, expected title을 포함한 author/comment wrapper prune을 `candidate_preserved_with_benign_prune`으로 분리한다.
  - `src/llm_batch/candidate_audit.py`: image OCR `work_cues`에서 플랫폼, 작가명, 조회/추천/회차, 시각 묘사 등 context-only surface를 candidate ledger로 넣지 않도록 필터링한다.
  - `src/llm_batch/agentic_pipeline.py`: relation judge가 HOLD로 판정한 indirect character/scene evidence는 direct text/OCR title anchor가 없으면 public `official_title` resolution을 차단하고 후보/HOLD로 보존한다.
  - `tests/test_completed779_compare.py`, `tests/test_candidate_audit.py`, `tests/test_agentic_pipeline_rework.py`에 관련 regression을 추가했다.
- Loop 13 targeted validation:
  - pre-fix `11710045` targeted canary는 relation HOLD에도 final gate가 `넣어 키운 걸그룹`을 public title로 확정하는 위험을 확인했다.
  - after-fix result: `out/completed779_improvement_goal_20260622/canary/hermes_loop13_ocr_filter_11710045_after_relation_hold_fix_result.json`, completed/failed/pending `1/0/0`, VLM/OCR `READY`, log `logs/expert_run_20260623_164251_513007.log`.
  - after-fix final: `official_title=null`, `Identified=0`, `is_resolved_work_discussion=false`, `title_resolution_state=context_only`, `title_resolution_allowed=false`, `candidate_ledger_status=promotion_blocked`, candidates include `루나`, `유하늘`.
  - after-fix compare: `out/completed779_improvement_goal_20260622/compare/hermes_loop13_ocr_filter_11710045_after_relation_hold_fix_compare.json`, movement `candidate_or_human_review_preserved=1`, requeue `0`.
- Loop 13 verification:
  - `py_compile`: pass for `expert_main.py`, `src/llm_batch/candidate_audit.py`, `src/llm_batch/agentic_pipeline.py`, `tools/compare_completed779_improvement.py`, `tools/build_completed779_hermes_expansion.py`, and touched tests.
  - focused suite: `tests.test_candidate_audit tests.test_completed779_compare tests.test_completed779_hermes_expansion tests.test_agentic_pipeline_rework.AgenticPipelineReworkTest.test_relation_hold_blocks_indirect_character_scene_title_resolution -v`, `77 tests OK`.
  - `git diff --check`: pass with LF/CRLF warnings only before docs sync.
- Known limitation:
  - Loop 13 queue `0`은 targeted loop closure다. completed779 전체 semantic approval 또는 full scan approval이 아니다.
  - `11710045` after-fix는 intentionally conservative context-only/no-title 결과다. broader validation에서는 character/scene-only OCR evidence가 over-demotion되지 않는지 controls로 계속 샘플링해야 한다.
  - 다음 goal은 Loop 14 fresh/residual/control pool을 열고 `11694064`, `11710045`, `11718105`를 regression controls로 포함한다.

Historical Loop 12 evidence:

- Council/subagent fan-out:
  - Candidate/Comment, OCR/Visual, Source/URL, Search/Web, Code Hook, Prompt/Orchestration+Verification/Docs 6축을 병렬로 실행했다.
  - subagent 결과는 승인 근거가 아니라 메인 Codex가 파일/테스트/canary/compare로 재확인한 입력이다.
- Loop 12 fresh expansion:
  - queue: `out/completed779_improvement_goal_20260622/hermes_loop12_fresh_expansion_queue.json`, rows `43`, main `39`, controls `4`, text/url/comment `14`, image/OCR `29`, duplicate `0`.
  - buckets: `fallback_unseen_high_risk=19`, `under_resolved_false_negative=8`, `under_resolved=6`, `wrong_relevance=6`, `source_refresh_url_lint_residual=4`.
  - input manifest: `out/completed779_improvement_goal_20260622/inputs/hermes_loop12_fresh_expansion_input_manifest.json`.
- Loop 12 canary:
  - text result: `out/completed779_improvement_goal_20260622/canary/hermes_loop12_fresh_expansion_text_result.json`, rows `14/14`, failed `0`, pending `0`, VLM/OCR `NOT_APPLICABLE`, log `logs/expert_run_20260623_133900_304877.log`.
  - image/OCR result: `out/completed779_improvement_goal_20260622/canary/hermes_loop12_fresh_expansion_image_ocr_result.json`, rows `29/29`, failed `0`, pending `0`, VLM/OCR `READY`, log `logs/expert_run_20260623_135608_043993.log`.
  - combined result: `out/completed779_improvement_goal_20260622/canary/hermes_loop12_fresh_expansion_combined_result.json`, rows `43`, duplicate `0`.
- Loop 12 compare:
  - combined compare: `out/completed779_improvement_goal_20260622/compare/hermes_loop12_fresh_expansion_combined_compare.json`, movement `candidate_or_human_review_preserved=28`, `candidate_preserved_with_benign_prune=8`, `candidate_preserved_with_prune_review=1`, `resolved_expected_title=2`, `resolved_expected_title_and_url=2`, `url_lint_preserved=2`.
  - next queue before fix: `out/completed779_improvement_goal_20260622/hermes_loop12_fresh_expansion_next_queue.json`, rows `1`, post_id `11718105`.
- Loop 12 targeted fix:
  - `src/llm_batch/candidate_audit.py`: judge expected title members are parsed from `multiple:`/`;` payloads and protected from weak `llm_only` sentence pruning.
  - `src/llm_batch/candidate_audit.py`: image OCR `work_cues` are preserved in `candidate_ledger` for unresolved/multi/adjacent non-resolved rows, without promoting `official_title`.
  - `tests/test_candidate_audit.py`: regressions for expected multi-title member preservation and OCR work-cue candidate ledger preservation.
- Loop 12 targeted validation:
  - fix1 result: `out/completed779_improvement_goal_20260622/canary/hermes_loop12_fix1_multi_title_11718105_image_ocr_result.json`, completed `1/1`; confirmed prune no longer removes the expected member but OCR work cues still needed ledger preservation.
  - fix2 result: `out/completed779_improvement_goal_20260622/canary/hermes_loop12_fix2_ocr_work_cues_11718105_image_ocr_result.json`, completed/failed/pending `1/0/0`, VLM/OCR `READY`, log `logs/expert_run_20260623_145033_192413.log`.
  - fix2 final ledger for `11718105`: `candidate_ledger_status=promotion_blocked`, `candidate_count=7`, includes `1990 할리우드 망나니 배우가 되었다`, `포수가 육아를 잘함`, `미국 트러커가 골동품으로 대박남`, `몰락민족의 천재 기사`.
  - fix2 compare: `out/completed779_improvement_goal_20260622/compare/hermes_loop12_fix2_ocr_work_cues_11718105_compare.json`, movement `candidate_or_human_review_preserved=1`.
  - fix2 next queue: `out/completed779_improvement_goal_20260622/hermes_loop12_fix2_ocr_work_cues_next_queue.json`, rows `0`.
- Loop 12 verification:
  - `py_compile`: pass for `expert_main.py`, `src/llm_batch/candidate_audit.py`, `tools/compare_completed779_improvement.py`, `tools/build_completed779_hermes_expansion.py`.
  - focused suite: `tests.test_candidate_audit tests.test_completed779_compare tests.test_completed779_hermes_expansion -v`, `74 tests OK`.
  - `git diff --check -- src/llm_batch/candidate_audit.py tests/test_candidate_audit.py`: pass.
- Known limitation:
  - `11718105` still exposes a relevance-boundary disagreement: runtime final is adjacent/platform/author meta with `is_relevant=false`, but OCR/comment work cues are now preserved as candidates. This is accepted for Loop12 because the native-web expected answer is multi-work candidate preservation, not unsafe single-title promotion.
  - Search provider was degraded in the targeted run, and `시리즈` platform queries still dominate search. This remains future prompt/orchestration/search-intent work, not full approval evidence.

Historical Loop 11 evidence:

- Council/subagent fan-out:
  - Candidate/Comment expert는 `11710025`, `11708479`, `11698878`은 safe HOLD/human_review로 닫을 수 있고, `11708478`은 작성자 댓글 명시 답변이 강하지만 promotion은 source/URL strength와 multi-candidate risk 때문에 계속 보수적이어야 한다고 봤다.
  - OCR/Visual expert는 네 row 모두 이미지 자체가 title grounding이 아니며, visual-only/scene/character/sticker evidence는 title promotion 근거로 쓰면 안 된다고 봤다.
  - Source/URL expert는 expected URL 후보 보존과 active official detail evidence를 분리해야 한다고 지적했다. `11708478`의 NovelPia detail은 local fetch 기준 unavailable이므로 `unavailable_official_detail`로 남겨야 한다.
  - Search/Web expert는 네 expected official pages/titles가 존재한다고 보되, local run의 search evidence는 degraded/seed-preserved인 경우가 있으므로 resolved approval이 아니라 candidate/HOLD preservation으로 봐야 한다고 했다.
  - Code Hook expert와 Prompt/Orchestration expert는 현재 문제의 직접 원인이 pipeline promotion failure가 아니라 compare taxonomy가 benign prune을 hard requeue로 세는 데 있다고 봤다.
  - Verification/Docs expert는 thread limit 때문에 별도 subagent로 spawn되지 못했고, 메인 Codex가 docs/verification sync를 직접 수행한다.
  - 모든 subagent finding은 승인 근거가 아니라 메인 Codex가 파일/테스트/compare artifact로 재검증한 입력이다.
- Loop 11 code/tooling changes:
  - `tools/compare_completed779_improvement.py`: `candidate_preserved_with_benign_prune` status를 추가했다. Expected title/url이 candidate로 보존되고, prune된 surface가 expected title과 무관한 sentence/noise이면 review queue에서 닫는다.
  - `tools/compare_completed779_improvement.py`: compare JSON의 `evidence_flags.expected_url_evidence_strength`에 `judge_seed_expected`, `active_official_detail`, `unavailable_official_detail`, `wiki`, `community` 등을 기록한다.
  - `tests/test_completed779_compare.py`: benign prune closure, expected surface prune review 유지, URL evidence strength 분리 테스트를 추가했다.
- Loop 11 recompare artifacts:
  - broader compare: `out/completed779_improvement_goal_20260622/compare/hermes_loop11_benign_prune_broader_compare.json`, rows `32/32`, movement `candidate_or_human_review_preserved=18`, `candidate_preserved_with_benign_prune=2`, `resolved_expected_title=4`, `url_lint_preserved=8`.
  - broader next queue: `out/completed779_improvement_goal_20260622/hermes_loop11_benign_prune_broader_next_queue.json`, rows `0`.
  - candidate/comment compare: `out/completed779_improvement_goal_20260622/compare/hermes_loop11_benign_prune_candidate_comment_compare.json`, rows `11/11`, movement `candidate_or_human_review_preserved=7`, `candidate_preserved_with_benign_prune=2`, `resolved_expected_title=2`.
  - candidate/comment next queue: `out/completed779_improvement_goal_20260622/hermes_loop11_benign_prune_candidate_comment_next_queue.json`, rows `0`.
- Loop 11 row evidence:
  - `11710025`, `11708479`, `11698878`: expected title/url preserved as `judge_seed_expected`; pruned surfaces were unrelated noisy sentence/comment fragments.
  - `11708478`: expected title/url preserved; URL evidence strength is `unavailable_official_detail`, so this is candidate/HOLD closure rather than resolved approval.
- Loop 11 verification:
  - `py_compile` pass for `expert_main.py`, `candidate_audit.py`, `agentic_pipeline.py`, `orchestrator.py`, `prompt_router.py`, `build_completed779_hermes_expansion.py`, `compare_completed779_improvement.py`, `tests/test_completed779_compare.py`.
  - `tests.test_completed779_compare`: `23 tests OK`.
  - `tests.test_completed779_hermes_expansion tests.test_completed779_compare tests.test_candidate_audit tests.test_judge_seed_registry`: `74 tests OK`.

Current Loop 10 evidence is historical closure evidence:

- Council/subagent fan-out:
  - Averroes (`gpt-5.5`)는 Loop 9 closure가 resolved-title approval이 아니라 conservative preservation이라고 지적했고, broader validation 및 comment/multi/author-new-work rows 추가를 요구했다.
  - Mill (`gpt-5.4`)은 compare false-close risk를 지적했다. generic HOLD/candidate_count만으로 닫지 말고 expected title/url 보존과 `blocked_primary_work`를 따로 봐야 한다고 했다.
  - Fermat (`gpt-5.4-mini`)은 comment explicit title, candidate preservation, multi-candidate lane을 별도 확장해야 한다고 제안했다.
  - Sagan subagent는 context-window error로 완료 응답을 주지 못했다. 이 limitation은 approval 근거에서 제외한다.
  - 모든 subagent finding은 승인 근거가 아니라 메인 Codex가 코드/테스트/canary/compare로 재검증한 입력이다.
- Loop 10 broader regression queue:
  - queue: `out/completed779_improvement_goal_20260622/hermes_loop10_broader_regression_queue.json`, rows `32`, text/url/comment `15`, image/OCR `17`, duplicate `0`.
  - manifest: `out/completed779_improvement_goal_20260622/inputs/hermes_loop10_broader_regression_input_manifest.json`.
  - text result: `out/completed779_improvement_goal_20260622/canary/hermes_loop10_broader_regression_text_result.json`, rows `15/15`, log `logs/expert_run_20260623_115623_153894.log`, VLM/OCR `NOT_APPLICABLE`.
  - image/OCR result: `out/completed779_improvement_goal_20260622/canary/hermes_loop10_broader_regression_image_ocr_result.json`, rows `17/17`, log `logs/expert_run_20260623_121748_731283.log`, VLM/OCR `READY`.
  - combined result: `out/completed779_improvement_goal_20260622/canary/hermes_loop10_broader_regression_combined_result.json`, rows `32`, duplicate `0`.
  - combined compare: `out/completed779_improvement_goal_20260622/compare/hermes_loop10_broader_regression_combined_compare.json`, movement `candidate_or_human_review_preserved=18`, `candidate_preserved_with_prune_review=2`, `resolved_expected_title=4`, `url_lint_preserved=8`.
  - next queue: `out/completed779_improvement_goal_20260622/hermes_loop10_broader_regression_next_queue.json`, rows `2`: `11710025`, `11708479`.
- Loop 10 candidate/comment expansion v2:
  - queue: `out/completed779_improvement_goal_20260622/hermes_loop10_candidate_comment_expansion_v2_queue.json`, rows `11`, text/url/comment `4`, image/OCR `7`, duplicate `0`.
  - manifest: `out/completed779_improvement_goal_20260622/inputs/hermes_loop10_candidate_comment_expansion_v2_input_manifest.json`.
  - text result: `out/completed779_improvement_goal_20260622/canary/hermes_loop10_candidate_comment_expansion_v2_text_result.json`, rows `4/4`, log `logs/expert_run_20260623_124623_349688.log`, VLM/OCR `NOT_APPLICABLE`.
  - image/OCR result: `out/completed779_improvement_goal_20260622/canary/hermes_loop10_candidate_comment_expansion_v2_image_ocr_result.json`, rows `7/7`, log `logs/expert_run_20260623_130033_520130.log`, VLM/OCR `READY`.
  - combined result: `out/completed779_improvement_goal_20260622/canary/hermes_loop10_candidate_comment_expansion_v2_combined_result.json`, rows `11`, duplicate `0`.
  - combined compare: `out/completed779_improvement_goal_20260622/compare/hermes_loop10_candidate_comment_expansion_v2_combined_compare.json`, movement `candidate_or_human_review_preserved=7`, `candidate_preserved_with_prune_review=2`, `resolved_expected_title=2`.
  - next queue: `out/completed779_improvement_goal_20260622/hermes_loop10_candidate_comment_expansion_v2_next_queue.json`, rows `2`: `11698878`, `11708478`.
- Loop 10 code/tooling changes:
  - `tools/build_completed779_hermes_expansion.py`: default main targets now include `comment_explicit_title_missed`, `candidate_preservation_missing`, and `conflicting_or_multi_candidate`; `--main-target`, `--clear-default-main-targets`, `--allow-balanced-main`를 추가했다. Custom control bucket prefix URL target bug도 수정했다.
  - `tools/compare_completed779_improvement.py`: expected title/url evidence flags, `hold_without_candidates`, `prune_fired`, `blocked_primary_work`를 기록하고, generic HOLD/candidate_count만으로 expected row를 닫지 않게 했다.
  - `src/llm_batch/candidate_audit.py`: expected title과 public `primary_work`가 충돌하면 `blocked_primary_work_conflict` lint와 `reference_role=blocked_primary_work`를 남긴다.
- Loop 10 verification:
  - `py_compile` pass for `expert_main.py`, `candidate_audit.py`, `agentic_pipeline.py`, `orchestrator.py`, `prompt_router.py`, `build_completed779_hermes_expansion.py`, `compare_completed779_improvement.py`.
  - `tests.test_completed779_hermes_expansion tests.test_completed779_compare tests.test_candidate_audit tests.test_judge_seed_registry`: `72 tests OK`.
  - `tests.test_title_lead_search_inferred_guard tests.test_agentic_pipeline_alias_contract tests.test_final_semantic_reread_gate tests.test_expert_main_comment_metadata tests.test_expert_main_input_loader`: `170 tests OK`.

Current Loop 9 evidence is historical closure evidence:

- Loop 9 source queue: `out/completed779_improvement_goal_20260622/hermes_loop8_fresh_expansion_next_queue.json`, rows `8`.
- Loop 9 input manifest: `out/completed779_improvement_goal_20260622/inputs/hermes_loop9_residual_input_manifest.json`.
- Loop 9 seed: `out/completed779_improvement_goal_20260622/inputs/hermes_loop9_residual_seed.jsonl`.
- Loop 9 text/url/comment:
  - input `out/completed779_improvement_goal_20260622/inputs/hermes_loop9_residual_text_url_comment.jsonl`
  - result `out/completed779_improvement_goal_20260622/canary/hermes_loop9_residual_text_result.json`
  - log `logs/expert_run_20260623_113346_494633.log`
  - rows `4/4`, VLM/OCR `NOT_APPLICABLE`
- Loop 9 image/OCR:
  - input `out/completed779_improvement_goal_20260622/inputs/hermes_loop9_residual_image_ocr.jsonl`
  - result `out/completed779_improvement_goal_20260622/canary/hermes_loop9_residual_image_ocr_result.json`
  - log `logs/expert_run_20260623_113635_246713.log`
  - rows `4/4`, VLM/OCR `READY`
- Loop 9 combined result: `out/completed779_improvement_goal_20260622/canary/hermes_loop9_residual_combined_result.json`, rows `8`, duplicate post_ids `0`.
- Loop 9 combined compare: `out/completed779_improvement_goal_20260622/compare/hermes_loop9_residual_combined_compare.json`.
- Loop 9 next queue: `out/completed779_improvement_goal_20260622/hermes_loop9_residual_next_queue.json`, rows `0`.
- Loop 9 movement:
  - `blocked_or_candidate_preserved=3`
  - `candidate_or_human_review_preserved=5`
- Loop 9 code changes:
  - `src/llm_batch/candidate_audit.py`: comment-surface candidates are preserved as HOLD-only candidates, judge-seeded expected title/url conflicts block unsafe public final title promotion, and URL-less weak `llm_only`/`comment_surface` sentence candidates are pruned from the ledger.
  - `expert_main.py`: postprocess now calls comment-surface preservation and judge-seed expected candidate preservation before candidate audit.
- Loop 9 row outcomes:
  - recall/comment rows `11718051`, `11694042`, `11694059`, `11716462`, `11716479` moved to candidate/HOLD/human-review preservation.
  - precision/wrong-work controls `11703631`, `11710047`, `11714902` moved to blocked/candidate preservation instead of wrong public final title.
- Runtime caveat:
  - stale model `bg-digitalservices/Gemma-4-E4B-it-NVFP4` returned `/v1/chat/completions` 404.
  - verified live `/v1/models` exposed `bg-digitalservices/Gemma-4-26B-A4B-it-NVFP4`, and Loop 9 canaries used that model.

Current Loop 8 evidence:

- Loop 8 queue: `out/completed779_improvement_goal_20260622/hermes_loop8_fresh_expansion_queue.json`
- Loop 8 queue report: `out/completed779_improvement_goal_20260622/hermes_loop8_fresh_expansion_queue_ko.md`
- Loop 8 input manifest: `out/completed779_improvement_goal_20260622/inputs/hermes_loop8_fresh_expansion_input_manifest.json`
- Loop 8 text input/result/compare:
  - input `out/completed779_improvement_goal_20260622/inputs/hermes_loop8_fresh_expansion_text_url_comment.jsonl`
  - result `out/completed779_improvement_goal_20260622/canary/hermes_loop8_fresh_expansion_text_result.json`
  - compare `out/completed779_improvement_goal_20260622/compare/hermes_loop8_fresh_expansion_text_compare.json`
  - rows `20/20`, VLM/OCR `NOT_APPLICABLE`
- Loop 8 image/OCR input/result/compare:
  - input `out/completed779_improvement_goal_20260622/inputs/hermes_loop8_fresh_expansion_image_ocr.jsonl`
  - result `out/completed779_improvement_goal_20260622/canary/hermes_loop8_fresh_expansion_image_ocr_result.json`
  - compare `out/completed779_improvement_goal_20260622/compare/hermes_loop8_fresh_expansion_image_ocr_compare.json`
  - rows `23/23`, VLM/OCR `READY`
- Loop 8 combined result: `out/completed779_improvement_goal_20260622/canary/hermes_loop8_fresh_expansion_combined_result.json`
- Loop 8 combined manifest: `out/completed779_improvement_goal_20260622/canary/hermes_loop8_fresh_expansion_combined_result_manifest.json`
- Loop 8 combined compare: `out/completed779_improvement_goal_20260622/compare/hermes_loop8_fresh_expansion_combined_compare.json`
- Loop 8 next queue: `out/completed779_improvement_goal_20260622/hermes_loop8_fresh_expansion_next_queue.json`
- Loop 8 split:
  - queue rows `43`
  - main `24`
  - controls `19`
  - text/url/comment `20`
  - image/OCR `23`
  - duplicate post_ids `0`
- Loop 8 combined movement:
  - `blocked_or_candidate_preserved=9`
  - `candidate_or_human_review_preserved=15`
  - `resolved_expected_title=4`
  - `resolved_expected_title_and_url=2`
  - `url_lint_preserved=5`
  - `still_under_resolved_or_noise=3`
  - `title_or_url_still_mismatched=2`
  - `title_match_url_still_mismatched=3`
- Loop 8 next queue rows:
  - main recall/comment/alias: `11718051`, `11694042`, `11694059`, `11716462`, `11716479`
  - precision/wrong-work controls: `11703631`, `11710047`, `11714902`
- Loop 8 sentinel/control status:
  - `11694064` did not regress to `무협 게임에 빙의했다...스킵충이다`; it preserved `판초우의의 마법사` as candidate/official URL and remained `blocked_or_candidate_preserved`.
  - `11710033` did not finalize the bad alias title; it remained blocked/preserved for `판초법사 -> 판초우의의 마법사`.
  - `11698880` recovered `아카데미 생존 갤러리` with expected NovelPia detail URL.
- Loop 8 compare-helper fixes:
  - `tools/compare_completed779_improvement.py` now reads `primary_work`/candidate lists when judging safe candidate preservation.
  - recall/relevance rows with an expected title and a mismatched final public title now remain `title_or_url_still_mismatched` instead of being incorrectly closed.
  - `tests/test_completed779_compare.py` added regressions for both cases.

Loop 9 source queue was:

- queue: `out/completed779_improvement_goal_20260622/hermes_loop8_fresh_expansion_next_queue.json`
- queue report: `out/completed779_improvement_goal_20260622/hermes_loop8_fresh_expansion_next_queue_ko.md`
- rows `8`
- movement: `still_under_resolved_or_noise=3`, `title_or_url_still_mismatched=2`, `title_match_url_still_mismatched=3`
- issue families:
  - comment/new-work explicit title drift: `11718051`
  - character/setting or short-alias under-resolution: `11694042`, `11716479`
  - multi-candidate platform/comment preservation missing: `11694059`
  - short alias wrong final title: `11716462`
  - source-local alias/wrong-work controls: `11703631`, `11710047`, `11714902`

Current Loop 7 evidence is historical closure evidence:

Current Loop 7 evidence:

- Loop 7 broader residual queue: `out/completed779_improvement_goal_20260622/hermes_loop7_broader_residual_queue.json`
- Loop 7 queue report: `out/completed779_improvement_goal_20260622/hermes_loop7_broader_residual_queue_ko.md`
- Loop 7 input manifest: `out/completed779_improvement_goal_20260622/inputs/hermes_loop7_broader_residual_input_manifest.json`
- Loop 7 seed: `out/completed779_improvement_goal_20260622/inputs/hermes_loop7_broader_residual_seed.jsonl`
- Loop 7 text/url/comment input: `out/completed779_improvement_goal_20260622/inputs/hermes_loop7_broader_residual_text_url_comment.jsonl`
- Loop 7 image/OCR input: `out/completed779_improvement_goal_20260622/inputs/hermes_loop7_broader_residual_image_ocr.jsonl`
- Loop 7 text partial combined result: `out/completed779_improvement_goal_20260622/canary/hermes_loop7_broader_residual_text_partial_combined_result.json`
- Loop 7 text partial next queue: `out/completed779_improvement_goal_20260622/hermes_loop7_text_partial_next_queue.json`
- Loop 7 runtime blocker report: `out/completed779_improvement_goal_20260622/hermes_loop7_text_runtime_blockers_ko.md`
- Loop 7 text fix1 combined result: `out/completed779_improvement_goal_20260622/canary/hermes_loop7_broader_residual_text_combined_fix1_result.json`
- Loop 7 text fix1 compare: `out/completed779_improvement_goal_20260622/compare/hermes_loop7_broader_residual_text_fix1_compare.json`
- Loop 7 image/OCR broad fix1 result: `out/completed779_improvement_goal_20260622/canary/hermes_loop7_broader_residual_image_ocr_fix1_result.json` (`19/20`; missing `11716480`)
- Loop 7 image/OCR broad fix1 compare: `out/completed779_improvement_goal_20260622/compare/hermes_loop7_broader_residual_image_ocr_fix1_compare.json`
- Loop 7 fix1 combined partial result: `out/completed779_improvement_goal_20260622/canary/hermes_loop7_broader_residual_combined_fix1_partial35_result.json` (`35/36`)
- Loop 7 fix1 combined partial compare: `out/completed779_improvement_goal_20260622/compare/hermes_loop7_broader_residual_combined_fix1_partial35_compare.json`
- Loop 7 fix1 next queue: `out/completed779_improvement_goal_20260622/hermes_loop7_broader_residual_next_queue_fix1_partial35.json` (`12` rows)
- Loop 7 `11716480` fix6 single result: `out/completed779_improvement_goal_20260622/canary/hermes_loop7_image_ocr_single_11716480_fix6_result.json`
- Loop 7 `11716480` fix6 manifest: `out/completed779_improvement_goal_20260622/canary/hermes_loop7_image_ocr_single_11716480_fix6_result_manifest.json`
- Loop 7 `11716480` fix6 compare: `out/completed779_improvement_goal_20260622/compare/hermes_loop7_image_ocr_single_11716480_fix6_compare.json`
- Loop 7 `11716480` fix6 remaining queue: `out/completed779_improvement_goal_20260622/compare/hermes_loop7_image_ocr_single_11716480_fix6_remaining_queue.json`
- Loop 7 final combined fix6 result: `out/completed779_improvement_goal_20260622/canary/hermes_loop7_broader_residual_combined_fix6_final36_result.json` (`36/36`)
- Loop 7 fix7 unwrapped final compare: `out/completed779_improvement_goal_20260622/compare/hermes_loop7_broader_residual_combined_fix7_unwrapped_final36_compare.json`
- Loop 7 fix7 next queue: `out/completed779_improvement_goal_20260622/hermes_loop7_broader_residual_next_queue_fix7_unwrapped_final36.json` (`2` rows)
- Loop 7 fix11 short-alias fetch compare: `out/completed779_improvement_goal_20260622/compare/hermes_loop7_fix11_short_alias_fetch_11706832_compare.json`
- Loop 7 fix11 next queue: `out/completed779_improvement_goal_20260622/hermes_loop7_fix11_short_alias_fetch_next_queue.json` (`0` rows by candidate preservation)
- Loop 7 fix17 J11 alias-lock result: `out/completed779_improvement_goal_20260622/canary/hermes_loop7_fix17_j11_alias_lock_11706832_result.json`
- Loop 7 fix17 J11 alias-lock compare: `out/completed779_improvement_goal_20260622/compare/hermes_loop7_fix17_j11_alias_lock_11706832_compare.json`
- Loop 7 fix17 next queue: `out/completed779_improvement_goal_20260622/hermes_loop7_fix17_j11_alias_lock_next_queue.json` (`0` rows)
- Loop 7 row split:
  - rows `36`
  - main `16`
  - controls `20`
  - text/url/comment `16`
  - image/OCR `20`
  - selection buckets: `under_resolved=3`, `under_resolved_false_negative=8`, `wrong_relevance=5`, `operational_residual_review=12`, `operational_residual_url_lint_preserved=8`
- Loop 7 text runtime:
  - first text run `20260623_022342_639179`: input `16`, completed `12`, flushed `11`, pending `1`, ordered flush blocked.
  - resume run `20260623_024758_871942`: input `4`, completed `2`, flushed `0`, pending `2`, ordered flush blocked.
  - partial combined rows `14`; missing text rows `11702087`, `11705239`.
- Loop 7 code fixes already applied:
  - `src/llm_batch/agentic_pipeline.py`: `_context_to_output` early `flags` initialization and merge into `consistency_flags`, fixing the `UnboundLocalError` seen on `11702087`.
  - `src/llm_batch/experts/orchestrator.py`: dense internal work character/setting clusters can bypass premature `semantic_seed_review` early stop.
  - `src/llm_batch/experts/orchestrator.py`: Korean connective/question lead tokens such as `그래서` are treated as low-specificity search seeds, and Phase34.5 no longer re-adds their reaction-tail augmentation.
  - `tests/test_title_lead_search_inferred_guard.py`: added focused regression tests for internal work cluster search probe and Korean connective lead-token handling.
- Loop 7 focused verification:
  - `py_compile` pass for changed `agentic_pipeline.py` and `orchestrator.py`.
  - `tests.test_title_lead_search_inferred_guard` passed with `67 tests OK`.
- Loop 7 targeted blocker status:
  - `11702087`: downstream guard P0 is targeted-resolved. fix9 canary completed `1/1` and produced `official_title=괴담 호텔 탈출기`, `heretic_url=https://novelpia.com/novel/102155`, `work_resolution=resolved`, `title_resolution_allowed=true`. The row still carries `candidate_ledger_status=output_consistency_lint` because the native-web seed bucket is `source_url_hygiene` + `garbage_title`; this is a hygiene lint, not a precision demotion.
  - `11705239`: repeated ordered-flush blocker was isolated. fix1 single canary completed `1/1` and correctly kept the row `official_title=null`, `work_resolution=none`, `title_resolution_state=unresolvable_memory_query` instead of promoting a memory-query/search-hit title.
  - `11716480`: runtime quarantine is targeted-closed by fix6. fix2/fix3 did not flush; fix4 flushed but failed semantically as weak visual only; fix5 recovered OCR title but candidate_audit demoted a close OCR title variant; fix6 completed `1/1`, kept `official_title=여대생 가랑이 사이 무릎 끓은 엄마들`, and preserved `heretic_url=null` as `judge_hygiene_seed_heretic_url_null`. This is a URL/source hygiene residual, not a runtime blocker.
  - `11706832`: short alias `황제분충` originally stayed under-resolved/candidate-preserved. fix17 completed `1/1` and resolved `novel_identity.official_title=황제폐하가 웹소설 작가임을 숨김`, `heretic_url=https://novelpia.com/novel/385635`, `work_resolution=resolved`, `candidate_ledger_status=safe_resolved`. Compare movement is `resolved_expected_title=1`; next queue is `0`.
- Loop 7 postfix evidence for `11702087`:
  - fix8 result before final guard correction: `out/completed779_improvement_goal_20260622/canary/hermes_loop7_text_single_11702087_fix8_result.json`; internal postprocess rescued the title, but `candidate_audit` demoted it back to candidate/HOLD via `precision_seed_official_title_requires_review`.
  - fix9 result after bucket-aware guard: `out/completed779_improvement_goal_20260622/canary/hermes_loop7_text_single_11702087_fix9_result.json`.
  - log: `logs/expert_run_20260623_044236_767318.log`.
  - runtime: completed/failed/pending `1/0/0`, total time `436.8s`; postprocess title correction/rescue was CPU-heavy, so a verifier+official-detail fast path was added and unit-verified, but not full-canary rerun after that micro-optimization.
  - code fixes: `agentic_pipeline.py` releases `multi_work_guard` when Synth/Jury/search converge on a character/setting work cluster, preserves cleared titles as canonical rescue candidates, lets the J1 verifier veto yield to deliberated convergence, and fast-paths final title correction when Verifier already locks the same official detail URL. `candidate_audit.py` now honors `seed_bucket` before applying precision demotion, so `source_url_hygiene` rows are handled by hygiene guards.
  - tests: focused `py_compile` passed; `tests.test_candidate_audit`, selected `tests.test_agentic_pipeline_rework`, and `tests.test_final_semantic_reread_gate`/`tests.test_title_lead_search_inferred_guard` focused runs passed.

- Loop 7 postfix evidence for `11716480`:
  - fix2 result path existed but runtime manifest stayed `0/0/0/0`; no result/checkpoint was flushed.
  - fix3 again reached OCR/title evidence but did not flush.
  - fix4 completed runtime `1/1`, but first-pass VLM returned only `weak_visual_only` with no OCR/title/author, so semantic movement stayed wrong/noise.
  - fix5 recovered the OCR title, but source/url hygiene expected-title conflict treated the close OCR variant as a mismatch and demoted the public title.
  - fix6 after VLM focused OCR retry support and close-title hygiene matching completed/flushed/pending/failed `1/1/0/0`.
  - fix6 final: `official_title=여대생 가랑이 사이 무릎 끓은 엄마들`, `work_resolution=resolved`, `title_resolution_state=resolved`, `title_resolution_allowed=true`, `heretic_url=null`, lint `judge_hygiene_seed_heretic_url_null`.
  - compare movement: `url_lint_preserved=1`; remaining queue for this single row is `0`.
  - generalized fixes: focused OCR retry when all first-pass image chunks are weak and textless; VLM retry merge preserves structural fields; source/url hygiene expected-title guard accepts close OCR/title variants instead of demoting them.
  - residual: official/detail URL is still absent, and search can drift toward generic/cross-domain entities. Future loops should prune tag-heavy search/query expansion and improve official URL discovery without forcing a bad URL.

Current Loop 6 evidence is historical closure evidence for the previous hard residual queue:

- Loop 6 remaining queue before postfix4: `out/completed779_improvement_goal_20260622/hermes_loop6_remaining_queue.json`
- Loop 6 final queue after postfix4: `out/completed779_improvement_goal_20260622/hermes_loop6_remaining_queue_postfix4.json`
- Loop 6 final queue report: `out/completed779_improvement_goal_20260622/hermes_loop6_remaining_queue_postfix4_ko.md`
- Loop 6 closed rows: `11710039`, `11705237`, `11698880`, `11698868`, `11708449`
- Loop 6 postfix movement:
  - `11710039`: search/official candidate and `기계공주` alias preserved as candidate/HOLD, no title promotion.
  - `11705237`: `월야환담` post-title surface preserved as candidate/HOLD, no title promotion.
  - `11698880`: public wrong-work promotion blocked; upstream title/body conflict remains a research note.
  - `11698868`: `방타스` TS short-alias surface preserved as candidate/HOLD, no title promotion.
  - `11708449`: `담청` image/character surface preserved as candidate/HOLD, VLM/OCR gate `READY`, no title promotion.
- Loop 6 compare artifacts:
  - `out/completed779_improvement_goal_20260622/compare/hermes_loop5_postfix2_entity_hold_compare.json`
  - `out/completed779_improvement_goal_20260622/compare/hermes_loop5_postfix3b_11705237_title_surface_compare.json`
  - `out/completed779_improvement_goal_20260622/compare/hermes_loop6_postfix4_11698868_text_compare.json`
  - `out/completed779_improvement_goal_20260622/compare/hermes_loop6_postfix4_11708449_image_ocr_compare.json`
- Loop 6 targeted canary status:
  - `11698868` text canary completed `1/1`, result `out/completed779_improvement_goal_20260622/canary/hermes_loop6_postfix4_11698868_text_result.json`.
  - `11708449` image/OCR canary completed `1/1`, result `out/completed779_improvement_goal_20260622/canary/hermes_loop6_postfix4_11708449_image_ocr_result.json`, VLM/OCR gate `READY`.
- Loop 6 verification:
  - final broader focused suite `211 tests OK`.
  - postfix4 focused subset `51 tests OK`.
  - `git diff --check` passed with existing LF/CRLF warnings only.

Loop 5 expansion `44`건은 targeted canary와 compare까지 완료했다. 아래 Loop 5 records are historical evidence for the now-closed hard residual queue and still-open operational caveats.

- completed Loop 5 queue: `out/completed779_improvement_goal_20260622/hermes_loop5_source_residual_queue.json`
- completed Loop 5 queue report: `out/completed779_improvement_goal_20260622/hermes_loop5_source_residual_queue_ko.md`
- completed Loop 5 seed: `out/completed779_improvement_goal_20260622/inputs/hermes_loop5_source_residual_seed.jsonl`
- completed Loop 5 input manifest: `out/completed779_improvement_goal_20260622/inputs/hermes_loop5_source_residual_input_manifest.json`
- Loop 5 text/url/comment result: `out/completed779_improvement_goal_20260622/canary/hermes_loop5_source_residual_text_result.json`
- Loop 5 image/OCR result: `out/completed779_improvement_goal_20260622/canary/hermes_loop5_source_residual_image_ocr_result.json`
- Loop 5 combined result: `out/completed779_improvement_goal_20260622/canary/hermes_loop5_source_residual_combined_result.json`
- Loop 5 combined compare: `out/completed779_improvement_goal_20260622/compare/hermes_loop5_source_residual_combined_compare.json`
- Loop 5 postfix compare: `out/completed779_improvement_goal_20260622/compare/hermes_loop5_source_residual_combined_compare_postfix1.json`
- Loop 5 hard-fail next queue: `out/completed779_improvement_goal_20260622/hermes_loop5_source_residual_next_queue.json`
- Loop 5 postfix next queue: `out/completed779_improvement_goal_20260622/hermes_loop5_source_residual_next_queue_postfix1.json`
- Loop 5 operational residual queue: `out/completed779_improvement_goal_20260622/hermes_loop5_source_residual_operational_residual_queue.json`
- Loop 5 runtime:
  - text/url/comment rows: `19/19`
  - image/OCR rows: `25/25`
  - combined rows: `44/44`, duplicate post_ids `0`
  - text run: `20260622_234407_959146`, VLM/OCR gate `NOT_APPLICABLE`
  - image/OCR run: `20260623_001532_142414`, VLM/OCR gate `READY`
  - effective parallel: requested `19`/`25`, health-filtered to `2` because only shards `3333`, `3334` were healthy
- Loop 5 combined movement:
  - `candidate_or_human_review_preserved=16`
  - `resolved_expected_title=4`
  - `review=12`
  - `still_under_resolved_or_noise=4`
  - `url_lint_preserved=8`
- Loop 5 postfix compare movement:
  - `candidate_or_human_review_preserved=16`
  - `resolved_expected_title=4`
  - `review=12`
  - `still_under_resolved_or_noise=4`
  - `title_or_url_still_mismatched=1`
  - `url_lint_preserved=7`
- Loop 5 hard-fail next queue:
  - rows `4`
  - movement `still_under_resolved_or_noise=4`
- Loop 5 operational residual queue:
  - rows `24`
  - movement `review=12`, `url_lint_preserved=8`, `still_under_resolved_or_noise=4`

Loop 5 main rows were selected from native-web non-ACCEPT rows not already consumed by balanced P0, source-correctness refresh, or Loop 4. Loop 5 controls keep source-correctness residual risk visible without counting those rows as main success denominator. The default compare next queue contains only hard-fail rows, so the operational residual queue is now the safer active loop input.

Previous source-correctness refresh closure:

- latest source-correctness queue: `out/completed779_improvement_goal_20260622/source_correctness_refresh_20260622/source_correctness_refresh_next_queue.json`
- latest source-correctness queue rows: `0`
- latest source-correctness compare: `out/completed779_improvement_goal_20260622/source_correctness_refresh_20260622/compare/source_correctness_refresh_compare.json`
- latest source-correctness compare report: `out/completed779_improvement_goal_20260622/source_correctness_refresh_20260622/compare/source_correctness_refresh_compare.md`
- latest combined result: `out/completed779_improvement_goal_20260622/source_correctness_refresh_20260622/canary/source_correctness_refresh_combined_result.json`
- latest movement: `resolved_expected_title_and_url=6`, `review=12`, `url_lint_preserved=21`
- latest canary status: normal Docker/SearXNG shard targeted canary
- text/url/comment canary:
  - result: `out/completed779_improvement_goal_20260622/source_correctness_refresh_20260622/canary/source_correctness_refresh_text_result.json`
  - completed/flushed/pending/failed: `14/14/0/0`
- image/OCR canary:
  - result: `out/completed779_improvement_goal_20260622/source_correctness_refresh_20260622/canary/source_correctness_refresh_image_ocr_result.json`
  - completed/flushed/pending/failed: `25/25/0/0`
  - VLM/OCR Semantic Gate: `READY`
- normal shard restore evidence:
  - `out/completed779_improvement_goal_20260622/source_correctness_refresh_20260622/search_shard_audit_after_restore.json`
  - audit result: `ok=2/2`, `direct_search_fallback=false`, `direct_search_degraded_provider=false`

Hermes Loop 4 closed five candidate-preservation rows without normal search. Source-correctness refresh then ran the prepared `39` rows with normal Docker/SearXNG shards and produced a queue of `0`. That closes the prepared refresh queue as runtime work, not as semantic approval. Loop 5 now reopens the residual families as controls and adds unseen native-web rows as main expansion work.

Important residual learnings:

- `11710058` recovered `판초법사 -> 판초우의의 마법사` with official URL, so the alias rule can work.
- `11694064` and `11710033` no longer finalize to the bad pipeline titles, but both remain `official_title=null`, `promotion_blocked`; the same alias family is still not consistently recovered.
- `11698880` still drifts internally from expected `아카데미 생존 갤러리` to `가챠 중독자의 퓨전펑크 생활`, but postfix1 now blocks the final public promotion and records the wrong title as `blocked_official_title`; upstream title/body multi-candidate orchestration still needs a generalized fix.
- `11702055` has strong `괴담 호텔 탈출기` character/setting evidence in logs, but final output still lands `official_title=null`, `adjacent`; character/setting cluster recall is not robust.
- `11706871` recovered `파우스트 1` and avoided the prior wrong title, but URL evidence remains linted/mismatched.
- `11716480` recovered OCR explicit title as a close variant, but `heretic_url=null` remains and decoder prompt size exploded past `100k` chars; OCR/search candidate pruning is needed.
- `11714902` and `11718076` moved away from bad pipeline titles into `unresolved_matchable/promotion_blocked`, but still need safer alias-to-official recovery.

Loop가 한 번 끝났다고 goal을 완료하지 않는다. 다음 조건이 파일 증거로 확인되어야 완료할 수 있다.

1. remaining queue가 `0`이거나, 남은 모든 row가 `HOLD`, `human_review`, `INFO_MISSING`, `unresolved_matchable`, `quarantine`, 또는 `no_generalizable_fix_left`로 명시 분류되고 왜 자동 개선 대상이 아닌지 row별로 기록되어 있다.
2. subagent fan-out 시도와 각 role의 확인/제약이 기록되어 있다. subagent tool이나 concurrency가 막힌 경우에는 limitation과 main Codex 대체 검토를 남긴다.
3. `expert_main.py` canary와 compare evidence가 존재하거나, 실행이 막힌 경우 exact blocker와 resume command가 문서화되어 있다.
4. 새 over-promotion, wrong-work, garbage title 회귀가 없고 control audit이 통과한다.
5. docs/checklist/history/register/verification sync와 `git diff --check` 결과가 남아 있다.

목표는 full scan approval이 아니다. 모든 loop에서 품질 상태는 계속 `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`다.

## Hermes Council / Subagent Fan-Out Rule

실제 개선 loop는 가능한 경우 Codex subagent를 병렬로 사용한다. subagent는 승인자가 아니라 탐색자, 반론자, 후보 설계자이며, 메인 Codex가 파일/테스트/canary/compare로 다시 확인한다.

필수 role:

1. Candidate / Comment Expert
   - 댓글 답변, 댓글 귀속, 추천 후보, 복수 후보, 짧은 약칭이 candidate ledger 또는 HOLD/human_review로 보존되는지 본다.
2. OCR / Visual Evidence Expert
   - 이미지/OCR 명시 제목, 표지/본문 이미지, lazy/placeholder 한계, VLM/OCR evidence strength를 본다.
3. Source / URL Hygiene Expert
   - official detail URL, mobile/detail canonicalization, stale/wrong/wiki/person/community URL, title-url mismatch lint를 본다.
4. Search / Web Evidence Expert
   - 실제 웹/검색 근거가 있는지, snippet-only인지, source drift인지, 검색 provider 저하인지 분리한다.
5. Code Hook Expert
   - `candidate_audit.py`, `agentic_pipeline.py`, `orchestrator.py`, `prompt_router.py`, `mcp_bridge/server.py`, `expert_main.py`의 최소 수정 위치와 테스트를 매핑한다.
6. Prompt / Orchestration Expert
   - LLM prompt, search intent, comment/OCR/short-alias/character-cluster orchestration의 누락을 본다.
7. Verification / Docs Expert
   - input split, canary, compare, controls, docs/checklist/history/register/verification gate를 점검한다.

선택 role:

- Regression Skeptic: 과확정, wrong-work, garbage title, source pollution 회귀만 본다.
- Data / Taxonomy Expert: 266 non-ACCEPT taxonomy와 active queue movement가 섞이지 않았는지 본다.
- Tooling Expert: helper, compare, queue writer, restart command를 본다.

## Model And Tool Diversity Rule

사용자가 별도로 금지하지 않는 한, subagent fan-out은 역할별로 모델과 도구 관점을 분산한다.

- 복잡한 검색/외부 근거/semantic 반론: `gpt-5.5` 또는 상위 reasoning effort.
- 코드 hook/test mapping: `gpt-5.4` 또는 code-focused model.
- 빠른 taxonomy/docs/checklist 검토: `gpt-5.4-mini` 또는 `gpt-5.3-codex-spark`.
- 도구 관점은 최소 네 축을 섞는다:
  - local result/log/compare artifact inspection
  - code static analysis and tests
  - web/search evidence review when correctness depends on external source
  - prompt/semantic/orchestration review

모델 다양성은 과반수 투표가 아니다. 같은 row를 여러 모델이 보더라도 최종 판정은 메인 Codex의 재확인된 증거와 보수적 promotion guard를 따른다.

각 subagent output은 다음 필드를 포함한다.

- inspected inputs/files/sources
- issue taxonomy by post_id
- suspected root cause
- proposed generalized fix
- over-promotion risk
- tests to add/update
- canary rows affected
- confidence and uncertainty

## Active Source Contract

- baseline result: `out/expert_result_20260620_165159_711176_completed_subset.json`
- native-web judge root: `out/codex_native_web_judge_20260620_165159_711176_completed779/`
- deterministic full-post judge root: `out/full_post_judge_20260620_165159_711176_completed779/`
- improvement root: `out/completed779_improvement_goal_20260622/`
- Loop 2 combined compare: `out/completed779_improvement_goal_20260622/compare/reimprovement_loop2_combined_compare.json`
- Loop 2 remaining queue: `out/completed779_improvement_goal_20260622/reimprovement_loop2_queue.json`
- Loop 2 remaining queue report: `out/completed779_improvement_goal_20260622/reimprovement_loop2_queue_ko.md`
- Hermes Loop 3 deterministic re-audit compare: `out/completed779_improvement_goal_20260622/compare/hermes_loop3_deterministic_reaudit_compare.json`
- Hermes Loop 3 active queue: `out/completed779_improvement_goal_20260622/hermes_loop3_queue.json`
- Hermes Loop 4 latest queue: `out/completed779_improvement_goal_20260622/hermes_loop4_queue.json`
- Hermes Loop 4 latest compare: `out/completed779_improvement_goal_20260622/compare/hermes_loop4_compare.json`
- Source-correctness refresh preflight: `out/completed779_improvement_goal_20260622/source_correctness_refresh_20260622/source_correctness_refresh_preflight_ko.md`
- Source-correctness refresh queue: `out/completed779_improvement_goal_20260622/source_correctness_refresh_20260622/source_correctness_refresh_queue.json`
- Source-correctness refresh input manifest: `out/completed779_improvement_goal_20260622/source_correctness_refresh_20260622/inputs/source_correctness_refresh_input_manifest.json`
- Source-correctness refresh latest compare: `out/completed779_improvement_goal_20260622/source_correctness_refresh_20260622/compare/source_correctness_refresh_compare.json`
- Source-correctness refresh next queue: `out/completed779_improvement_goal_20260622/source_correctness_refresh_20260622/source_correctness_refresh_next_queue.json`
- Hermes Loop 5 active queue: `out/completed779_improvement_goal_20260622/hermes_loop5_source_residual_queue.json`
- Hermes Loop 5 active queue report: `out/completed779_improvement_goal_20260622/hermes_loop5_source_residual_queue_ko.md`
- Hermes Loop 5 input manifest: `out/completed779_improvement_goal_20260622/inputs/hermes_loop5_source_residual_input_manifest.json`
- Hermes Loop 5 text/url/comment input: `out/completed779_improvement_goal_20260622/inputs/hermes_loop5_source_residual_text_url_comment.jsonl`
- Hermes Loop 5 image/OCR input: `out/completed779_improvement_goal_20260622/inputs/hermes_loop5_source_residual_image_ocr.jsonl`
- Hermes Loop 6 final queue: `out/completed779_improvement_goal_20260622/hermes_loop6_remaining_queue_postfix4.json`
- Hermes Loop 6 final queue report: `out/completed779_improvement_goal_20260622/hermes_loop6_remaining_queue_postfix4_ko.md`
- Hermes Loop 7 broader residual queue: `out/completed779_improvement_goal_20260622/hermes_loop7_broader_residual_queue.json`
- Hermes Loop 7 broader residual queue report: `out/completed779_improvement_goal_20260622/hermes_loop7_broader_residual_queue_ko.md`
- Hermes Loop 7 text/url/comment input: `out/completed779_improvement_goal_20260622/inputs/hermes_loop7_broader_residual_text_url_comment.jsonl`
- Hermes Loop 7 image/OCR input: `out/completed779_improvement_goal_20260622/inputs/hermes_loop7_broader_residual_image_ocr.jsonl`
- Hermes Loop 7 text partial combined result: `out/completed779_improvement_goal_20260622/canary/hermes_loop7_broader_residual_text_partial_combined_result.json`
- Hermes Loop 7 text partial next queue: `out/completed779_improvement_goal_20260622/hermes_loop7_text_partial_next_queue.json`
- Hermes Loop 7 runtime blockers: `out/completed779_improvement_goal_20260622/hermes_loop7_text_runtime_blockers_ko.md`
- active Hermes prompt: `docs/devs/COMPLETED779_HERMES_CONTINUOUS_GOAL_PROMPT.md`
- archived prior goal: `llm_judge_goal.md`

## Active Stale Aggregate Rule

Deterministic `full_post_judge_report.md` aggregate와 Codex-native web verdict/active queue aggregate를 섞지 않는다. deterministic report는 source coverage와 이전 judge 산출물로만 기록하고, 개선 우선순위와 seed/queue는 native-web verdict 및 최신 compare queue에서만 만든다.

## Active Controls

- `11694064`는 `무협 게임에 빙의했다. 문제는 나는 스토리를 보지 않는 스킵충이다`로 확정되면 안 된다. 올바른 방향은 `판초우의의 마법사` 또는 보수적 HOLD/candidate conflict다.
- Loop 1 `wrong_work=9`는 bad pipeline title로 회귀하면 안 된다.
- active `garbage_title_after=0`을 유지한다.
- `slang_db` production write-back 금지. canary는 기본 `--slang-db off`.
- direct Naver/Bing fallback은 degraded-provider evidence이며 정상 Docker/SearXNG shard approval이 아니다. 최신 source-correctness refresh는 Docker/SearXNG shard `2/2` 정상 상태에서 실행됐지만, targeted 39-row evidence일 뿐 full scan approval이 아니다.
- runtime integrity, targeted canary status, semantic quality, full-scan approval을 문서에서 분리한다.

## Active Bucket Acceptance Map

- `candidate_comment_multi`: 성공은 final title 강제 승격이 아니라 `candidate_preserved`, `recommendation_candidates`, `secondary_reference_works`, `unresolved_matchable`, `HOLD`, 또는 `human_review`일 수 있다.
- `recall_relevance_representative`: 강한 direct URL/title/compound alias/character-cluster evidence가 있으면 expected title/url 회수를 허용하되, 근거가 약하면 `unresolved_matchable`, URL mismatch lint, `HOLD`, 또는 `human_review`가 안전한 성공이다.
- bare short alias, OCR cross-media cue, recommendation/multi-work row는 final promotion보다 candidate preservation과 explicit HOLD가 우선이다.

## Active Next Prompt

다음 goal/thread에는 `docs/devs/COMPLETED779_HERMES_CONTINUOUS_GOAL_PROMPT.md`의 `Copy-Paste Prompt`를 사용한다. 현재 prompt는 Loop 7 broader residual queue, partial text blockers, subagent/model/tool diversity, and continuous queue-repeat contract를 포함한다. 새 루프를 시작할 때 `11702087`/`11705239`는 그대로 병렬 canary에 다시 넣기보다 blocker row로 먼저 원인 분석한다.

다음 Codex goal/thread는 `docs/devs/COMPLETED779_HERMES_CONTINUOUS_GOAL_PROMPT.md`의 `Copy-Paste Prompt`를 사용하되, Loop 6 postfix4 기준 hard residual queue가 `0`임을 먼저 확인한다. 후속 작업의 1순위는 full approval이 아니라 broadened random/high-risk expansion과 upstream orchestration research다. 특히 `11698880`류 title/body multi-candidate conflict HOLD, `판초법사 -> 판초우의의 마법사` alias recall consistency, character/setting cluster recall, OCR explicit title + search absent 분리, OCR/search candidate pruning, source-local alias conflict guard를 control audit으로 유지한다.

## Archived Historical Section - completed779 Reimprovement Loop 2 Goal

이하 Loop 2 섹션은 실행 완료된 historical archive다. 현재 active contract는 이 파일 상단의 `completed779 Hermes Continuous Improvement Goal`과 `docs/devs/COMPLETED779_HERMES_CONTINUOUS_GOAL_PROMPT.md`다.

이 문서는 completed subset `779`건의 Codex-native web judge 개선 루프 중, Loop 1 이후 남은 post-fix-adjusted `reimprovement_queue` `25`건을 줄이기 위한 active operating contract다. 이전 JUDGE3905/LLM judge goal 본문은 `llm_judge_goal.md`에 보관하고, 이 파일은 completed779 개선 루프만 다룬다.

## Objective

Loop 2의 목표는 `out/completed779_improvement_goal_20260622/reimprovement_queue.json`의 active `25`건을 입력으로 삼아, post_id/title 하드코딩 없이 다음 두 failure mode를 줄이는 것이다.

1. `still_under_resolved_or_noise=16`: 댓글 답변, 짧은 약칭, OCR/이미지, 캐릭터/설정 cluster가 candidate ledger 또는 HOLD/human_review로 충분히 보존되지 않는 문제를 줄인다.
2. `title_or_url_still_mismatched=9`: 제목-URL mismatch, wiki/person/community URL, stale URL, mobile/detail canonicalization 부족을 official detail URL 보강 또는 URL mismatch lint/HOLD로 줄인다.

Loop 2는 completed779 전체 approval이 아니다. 실패하거나 애매한 행은 다시 `reimprovement_queue`로 남기고, 정상 Docker/SearXNG shard가 없으면 direct fallback 결과를 degraded-provider evidence로만 기록한다.

목표는 full scan approval이 아니다. 이번 goal의 품질 상태는 계속 `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`다.

## Source Contract

- baseline result: `out/expert_result_20260620_165159_711176_completed_subset.json`
- native-web judge root: `out/codex_native_web_judge_20260620_165159_711176_completed779/`
- deterministic full-post judge root: `out/full_post_judge_20260620_165159_711176_completed779/`
- improvement root: `out/completed779_improvement_goal_20260622/`
- Loop 2 active queue: `out/completed779_improvement_goal_20260622/reimprovement_queue.json`
- Loop 2 active queue report: `out/completed779_improvement_goal_20260622/reimprovement_queue_ko.md`
- Loop 1 adjusted compare: `out/completed779_improvement_goal_20260622/compare/combined_direct_search_postfix_adjusted_compare.json`
- archived prior goal: `llm_judge_goal.md`
- Loop 1 auto-loop prompt: `docs/devs/COMPLETED779_AUTO_IMPROVEMENT_GOAL_PROMPT.md`
- Loop 2 auto-loop prompt: `docs/devs/COMPLETED779_REIMPROVEMENT_LOOP2_GOAL_PROMPT.md`

## Loop 2 Queue Baseline

- adjusted compare rows: `65/65`
- active reimprovement rows: `25`
- active movement counts:
  - `still_under_resolved_or_noise=16`
  - `title_or_url_still_mismatched=9`
- closed by post-fix canary: `3`
- active `garbage_title_after`: `0`
- `11694064`: present, after title `null`, movement `blocked_or_candidate_preserved`
- `wrong_work=9`: all movement `blocked_or_candidate_preserved`

### Loop 2 Active Post Groups

Candidate/comment/recall preservation group (`16`):

- `11695623`, `11697256`, `11698878`, `11706856`, `11708442`, `11716478`, `11716482`
- `11697234`, `11697241`, `11697255`, `11698886`, `11698910`, `11700475`, `11702049`, `11702072`, `11703624`

Source/URL hygiene group (`9`):

- `11698880`, `11698890`, `11698903`, `11700504`, `11702055`, `11708437`, `11708470`, `11711631`, `11718077`

### Stale Aggregate Rule

Deterministic `full_post_judge_report.md` aggregate와 Codex-native web verdict aggregate를 섞지 않는다. deterministic report는 source coverage와 이전 judge 산출물로만 기록하고, 개선 우선순위와 seed packet은 native-web verdict aggregate에서만 만든다.

## Native-Web Baseline

- total unique posts: `779`
- non-ACCEPT: `266`
- missing: `0`
- duplicate after post_id dedupe: `0`
- resolution labels:
  - `ACCEPT=513`
  - `REPROCESS=208`
  - `HOLD=49`
  - `INFO_MISSING=7`
  - `REJECT=2`

주요 이슈 축:

- `under_resolved=68`
- `under_resolved_false_negative=64`
- `wrong_relevance=62`
- `heretic_url_null=13`
- `wrong_work=9`
- `candidate_preservation_missing=6`
- `garbage_title=6`
- `reason_evidence_mismatch=6`
- `conflicting_or_multi_candidate=5`
- `comment_explicit_title_missed=4`

반복 작품/패턴:

- `괴담 호텔 탈출기`
- `판초우의의 마법사`
- `아카데미 생존 갤러리`
- `즉사기 들고 무림에 떨어지다`
- `헌터갤러리의 국가권력급 기계공주`
- `하남자의 탑 공략법`

## Loop 2 Workstreams

### 1. Candidate / Comment / Recall Preservation

댓글 답변, 추천글 후보, 짧은 약칭, OCR 명시 제목, 캐릭터/설정 cluster가 검색 intent와 candidate ledger에 남도록 보강한다. 단일 작품 확정은 strong source-local evidence가 있을 때만 허용하고, multi-candidate/추천/댓글 귀속 문맥은 HOLD 또는 human_review를 우선한다.

### 2. Source / URL Hygiene

공식 상세 URL canonicalization, mobile/detail URL 정규화, stale/wrong/wiki/person URL demotion, title-url mismatch lint를 보강한다. 성공은 exact title+official detail URL이거나, unsafe한 경우 URL mismatch lint/HOLD로 남기는 것이다.

### 3. Search Provider Integrity

정상 Docker/SearXNG shard search-enabled canary를 우선한다. 불가하면 direct Naver/Bing fallback을 쓰되, 모든 report에 degraded-provider evidence로 표기한다.

### 4. Regression Guard

Loop 1에서 닫힌 `garbage_title_after=0`, `11694064`, `wrong_work=9`를 control로 유지한다. Loop 2 수정으로 snippet/breadcrumb title pollution 또는 bad pipeline title 재승격이 생기면 semantic `NO-GO`다.

## Loop 2 Code Hooks

- `src/llm_batch/agentic_pipeline.py`: queue 기반 comment/multi-candidate candidate ledger 보존, official URL/source upgrade, final title gate
- `src/llm_batch/experts/orchestrator.py`: short alias, comment answer, OCR/title image, character cluster search probe 보강
- `src/llm_batch/prompts/prompt_router.py`: comment attribution, recommendation/multi-candidate HOLD, URL hygiene prompt 문구 보강
- `src/llm_batch/candidate_audit.py`: title-url mismatch lint, official detail URL guard, stale/wrong URL demotion, closed controls regression guard
- `src/llm_batch/mcp_bridge/server.py`: direct fallback title cleaning and official/platform ranking regression guard
- `expert_main.py`: postprocess audit field 보존과 canary output compare에 필요한 fields 누락 방지

## Subagent Operating Rule

실제 개선 loop는 Codex subagent를 최소 4축으로 병렬 배정한다.

- `taxonomy/source` expert: non-ACCEPT `266`건 issue index 검증
- `code-hook` expert: issue 축별 수정 위치와 테스트 매핑
- `prompt/orchestration` expert: LLM prompt/search intent 개선
- `verification/docs` expert: canary, compare, docs gate 점검

Subagent 결과는 승인 근거가 아니라 메인 Codex의 재확인 입력이다. 메인 Codex가 최종 산출물, 테스트, docs gate를 다시 확인한다.

## Loop 2 Required Artifacts

Loop 2에서는 기존 `balanced_p0_seed.jsonl`을 다시 만들지 않는다. active queue `25`건에서 별도 Loop 2 seed/input/compare를 만든다.

- `out/completed779_improvement_goal_20260622/inputs/reimprovement_loop2_text_url_comment.jsonl`
- `out/completed779_improvement_goal_20260622/inputs/reimprovement_loop2_image_ocr.jsonl`
- `out/completed779_improvement_goal_20260622/compare/reimprovement_loop2_text_compare.json`
- `out/completed779_improvement_goal_20260622/compare/reimprovement_loop2_image_ocr_compare.json`
- `out/completed779_improvement_goal_20260622/compare/reimprovement_loop2_combined_result.json`
- `out/completed779_improvement_goal_20260622/compare/reimprovement_loop2_combined_compare.json`
- `out/completed779_improvement_goal_20260622/reimprovement_loop2_queue.json`
- `out/completed779_improvement_goal_20260622/reimprovement_loop2_queue_ko.md`

필요하면 helper를 추가한다.

- `tools/build_completed779_reimprovement_inputs.py`: active queue `25`건을 source baseline과 join해 text/url/comment vs image/OCR 입력으로 분리한다.
- `tools/compare_completed779_improvement.py`: 기존 compare helper를 재사용하되 `--seed`는 queue 또는 Loop 2 seed packet을 받게 확장하거나, queue rows를 compare seed shape로 변환한다.

## Loop 2 Canary Commands

Text/URL/comment queue:

```powershell
.venv312\Scripts\python.exe expert_main.py out\completed779_improvement_goal_20260622\inputs\reimprovement_loop2_text_url_comment.jsonl --server-type vllm --llm-endpoint http://10.20.0.101:8000 --llm-model bg-digitalservices/Gemma-4-26B-A4B-it-NVFP4 --reuse-shards-only --no-dashboard --slang-db off --parallel min(input_count,36)
```

Image/OCR queue:

```powershell
.venv312\Scripts\python.exe expert_main.py out\completed779_improvement_goal_20260622\inputs\reimprovement_loop2_image_ocr.jsonl --server-type vllm --llm-endpoint http://10.20.0.101:8000 --llm-model bg-digitalservices/Gemma-4-26B-A4B-it-NVFP4 --reuse-shards-only --no-dashboard --slang-db off --parallel min(input_count,36) --vlm on --ocr on --require-vlm-ocr-for-images
```

PowerShell에서는 실제 실행 전에 `min(input_count,36)`을 정수로 치환한다.

Compare:

```powershell
.venv312\Scripts\python.exe tools\compare_completed779_improvement.py --seed out\completed779_improvement_goal_20260622\reimprovement_queue.json --before out\expert_result_20260620_165159_711176_completed_subset.json --after <LOOP2_RESULT_JSON> --out-json out\completed779_improvement_goal_20260622\compare\<LOOP2_RUN>_compare.json --out-md out\completed779_improvement_goal_20260622\compare\<LOOP2_RUN>_compare.md --out-queue out\completed779_improvement_goal_20260622\compare\<LOOP2_RUN>_queue.json --canary-kind reimprovement_loop2 --only-after-posts
```

## 2026-06-22 Implementation Loop Evidence

- preflight: `tools/build_completed779_issue_index.py` 재실행 결과 `total=779`, `non_accept=266`, `missing=0`, `duplicate_after_dedupe=0`, seed `65`, bucket `15/15/25/10`.
- subagents: taxonomy/source, code-hook, prompt/orchestration, verification/docs 4축 분석을 받아 메인 Codex가 재확인했다.
- implemented:
  - `src/llm_batch/candidate_audit.py`: completed779 native-web disagreement taxonomy를 recall/precision/candidate/hygiene으로 확장하고, `seed_bucket` 기반 분류를 추가했다. `wrong_work`/`overresolved_generic_trope` 등은 judge-seed precision guard에서 보수적으로 demote하며, source/url hygiene의 `reason_evidence_mismatch`는 demote가 아니라 lint로 남긴다.
  - `src/llm_batch/agentic_pipeline.py`: 댓글 명시 제목 후보를 final promotion이 아니라 `title_candidates` 보존 경로에 추가했다.
  - `src/llm_batch/experts/orchestrator.py`: semantic seed denial 상태에서도 댓글 제목 기반 official probe가 통째로 잘리지 않도록 검색 intent permit 예외를 추가했다.
  - `src/llm_batch/prompts/prompt_router.py`: 댓글/URL/OCR/짧은 약칭/캐릭터·설정 cluster는 candidate ledger에 보존하고 final promotion은 별도 gate로 보류하라는 문구를 추가했다.
  - `tools/compare_completed779_improvement.py`: split canary scope, expected URL mismatch, reimprovement queue 출력을 추가했다.
- tests:
  - `py_compile`: pass.
  - focused suite: `190 tests OK` (`tests.test_mcp_bridge_direct_search` 포함).
  - `git diff --check`: pass, 기존 LF/CRLF warning only.
- targeted canary:
  - text/url/comment degraded run: `out/expert_result_20260622_161924_359370.json`, rows `19/19`.
  - image/OCR degraded run: `out/expert_result_20260622_162557_711822.json`, rows `46/46`, VLM/OCR Semantic Gate `READY`.
  - 두 run 모두 Docker/MCP shards가 전부 connection refused라 `echo y`로 no-search continuation을 수행했다. 따라서 runtime/candidate-audit evidence로만 사용하고, full semantic approval 근거로 쓰지 않는다.
- compare:
  - `out/completed779_improvement_goal_20260622/compare/text_degraded_compare.json`
  - `out/completed779_improvement_goal_20260622/compare/image_ocr_degraded_compare.json`
  - `out/completed779_improvement_goal_20260622/compare/combined_degraded_compare.json`
  - combined `65/65`: `blocked_or_candidate_preserved=14`, `candidate_or_human_review_preserved=30`, `resolved_expected_title=2`, `still_under_resolved_or_noise=8`, `title_match_url_still_mismatched=1`, `title_or_url_still_mismatched=10`.
  - `wrong_work=9` 전체는 bad title로 finalize되지 않고 모두 `blocked_or_candidate_preserved`로 이동했다. `11694064`도 `무협 게임에 빙의했다...스킵충이다`로 확정되지 않는다.
  - reimprovement queue: `out/completed779_improvement_goal_20260622/reimprovement_queue.json`, `out/completed779_improvement_goal_20260622/reimprovement_queue_ko.md`, rows `19` (`still_under_resolved_or_noise=8`, URL mismatch/missing `11`).
- direct-search fallback:
  - Docker Desktop Linux engine pipe 부재와 public SearXNG throttling 때문에 `src/llm_batch/mcp_bridge/server.py`에 Naver/Bing direct HTTP search fallback을 추가했다. 이 fallback은 search-enabled canary를 가능하게 하지만 정상 SearXNG shard approval이 아니라 degraded-provider evidence다.
  - vLLM `/v1/models` 확인 결과 현재 실행 모델은 `bg-digitalservices/Gemma-4-26B-A4B-it-NVFP4`였고, 계획서의 stale `bg-digitalservices/Gemma-4-E4B-it-NVFP4`는 404를 반환했다.
  - text/url/comment direct-search canary: `out/expert_result_20260622_165552_032705.json`, rows `19/19`, compare `out/completed779_improvement_goal_20260622/compare/text_direct_search_compare.json`.
  - image/OCR direct-search canary: `out/expert_result_20260622_171928_162115.json`, rows `46/46`, VLM/OCR Semantic Gate `READY`, compare `out/completed779_improvement_goal_20260622/compare/image_ocr_direct_search_compare.json`.
  - combined direct-search compare `65/65`: `blocked_or_candidate_preserved=15`, `candidate_or_human_review_preserved=20`, `garbage_title_after=3`, `resolved_expected_title=2`, `resolved_expected_title_and_url=1`, `still_under_resolved_or_noise=15`, `title_or_url_still_mismatched=9`.
  - direct fallback은 search coverage를 회복했지만 검색 스니펫/브레드크럼이 title로 승격되는 새 risk를 드러냈다. 이에 `tools/compare_completed779_improvement.py`는 `garbage_title_after`를 별도 status로 잡고, `src/llm_batch/candidate_audit.py`는 snippet/breadcrumb-like `official_title`을 `blocked_official_title`로 보존하며 public title은 demote한다.
  - post-fix mini canary: polluted 3건 중 text 2건은 `out/expert_result_20260622_183047_118075.json`, image/OCR 1건은 `out/expert_result_20260622_183544_060718.json`으로 재실행했다. 결합 compare `out/completed779_improvement_goal_20260622/compare/garbage_title_postfix_combined_compare.json`은 `candidate_or_human_review_preserved=2`, `still_under_resolved_or_noise=1`이며 `garbage_title_after=0`이다.
  - adjusted combined compare: `out/completed779_improvement_goal_20260622/compare/combined_direct_search_postfix_adjusted_compare.json`, rows `65/65`. Movement는 `blocked_or_candidate_preserved=15`, `candidate_or_human_review_preserved=22`, `resolved_expected_title=2`, `resolved_expected_title_and_url=1`, `still_under_resolved_or_noise=16`, `title_or_url_still_mismatched=9`다.
  - root reimprovement queue는 post-fix-adjusted 기준으로 갱신했다: `out/completed779_improvement_goal_20260622/reimprovement_queue.json`, `out/completed779_improvement_goal_20260622/reimprovement_queue_ko.md`, active rows `25` (`still_under_resolved_or_noise=16`, `title_or_url_still_mismatched=9`). `11710063`/`11705231`은 garbage-title item을 닫았고, `11716482`는 public title 오염은 닫았지만 comment multi-candidate 보존 미흡으로 active queue에 남겼다.
  - completion audit: `11694064`는 adjusted compare에도 포함되어 있고 `after_title=null`, movement `blocked_or_candidate_preserved`다. `wrong_work=9` 전체도 still-bad pipeline title 없이 모두 `blocked_or_candidate_preserved` 상태다.

## 2026-06-22 Loop 2 Completion Evidence

- active queue preflight:
  - `out/completed779_improvement_goal_20260622/reimprovement_queue.json` rows `25`.
  - manifest 기준 `still_under_resolved_or_noise=16`, `title_or_url_still_mismatched=9`, active `garbage_title_after=0`.
  - Loop 2 inputs: text/url/comment `8` rows, image/OCR `17` rows.
- implementation:
  - `src/llm_batch/mcp_bridge/server.py`: direct Naver/Bing fallback을 `/readyz`에서 명시 canary gate(`MCP_DIRECT_SEARCH_FALLBACK_READYZ_OK=1`)가 있을 때만 ready로 인정하도록 보강했다.
  - `src/llm_batch/search/client.py`: readyz `status=ok`와 `searxng/headless_search/direct_search_fallback` provider 중 하나가 true일 때 health OK로 인정하도록 보강했다.
  - `tools/compare_completed779_improvement.py`: Loop 2 remaining queue Markdown writer(`--out-queue-md`)를 추가했다.
- runtime:
  - text/url/comment canary: `out/expert_result_20260622_201044_448457.json`, rows `8/8`, result JSON generated, direct fallback degraded-provider.
  - image/OCR canary: `out/expert_result_20260622_201630_167085.json`, rows `17/17`, VLM/OCR Semantic Gate `READY`, direct fallback degraded-provider.
  - 첫 text attempt `out/expert_result_20260622_200541_656043.json`은 decoder stream 폭주로 final result flush 전 중단했다. 이후 bounded decoder env(`LLM_DECODER_MAX_TOKENS=4096`, `LLM_DECODER_HARD_CAP=4096`, `LLM_ACC_HARD_CAP=32768`)로 재실행 완료했다.
- compare:
  - text compare: `out/completed779_improvement_goal_20260622/compare/reimprovement_loop2_text_compare.json`, rows `8/8`.
  - image/OCR compare: `out/completed779_improvement_goal_20260622/compare/reimprovement_loop2_image_ocr_compare.json`, rows `17/17`.
  - combined result: `out/completed779_improvement_goal_20260622/compare/reimprovement_loop2_combined_result.json`, rows `25`.
  - combined compare: `out/completed779_improvement_goal_20260622/compare/reimprovement_loop2_combined_compare.json`, rows `25/25`.
  - movement: `candidate_or_human_review_preserved=7`, `resolved_expected_title=1`, `url_lint_preserved=9`, `still_under_resolved_or_noise=8`.
  - source/url hygiene `9`건은 모두 `url_lint_preserved`로 이동했다.
  - remaining queue: `out/completed779_improvement_goal_20260622/reimprovement_loop2_queue.json`, `out/completed779_improvement_goal_20260622/reimprovement_loop2_queue_ko.md`, rows `8`.
- controls:
  - active `garbage_title_after=0` 유지.
  - `11694064`: adjusted compare에서 `after_title=null`, movement `blocked_or_candidate_preserved`; `무협 게임에 빙의했다...스킵충이다`로 재확정되지 않음.
  - `wrong_work=9`: adjusted compare 기준 전부 `blocked_or_candidate_preserved`; bad pipeline title 회귀 없음.
- tests:
  - `py_compile`: pass.
  - focused suite: `204 tests OK`.
  - semantic quality는 계속 `REVIEW-LOCKED`, full scan approval은 `false`.

## Acceptance Criteria

- issue index가 native-web verdict 기준 `779/779`, missing `0`, non-ACCEPT `266`을 재현한다.
- standalone sentinel과 batch verdict 중복은 `post_id` 기준으로 제거하며, dedupe 후 duplicate는 `0`이다.
- `11694064`는 seed packet에 포함되고, 이후 canary에서 `무협 게임에 빙의했다...스킵충이다`로 확정되면 안 된다.
- `wrong_work=9` seed는 모두 resolved-correct, HOLD, 또는 candidate conflict로 개선되어야 한다.
- recall/relevance seed는 null/noise에서 candidate 보존, unresolved_matchable, resolved, 또는 명시적 human_review로 이동해야 한다.
- source/url hygiene seed는 official detail URL 보강 또는 URL mismatch lint로 남아야 한다.
- controls에서 over-promotion이 새로 생기면 해당 fix loop는 semantic `NO-GO`다.
- runtime integrity, targeted canary status, semantic quality, full-scan approval을 문서에서 분리한다.
- completed779 개선 loop가 성공해도 full scan approval은 `false`다.

## Verification Commands

```powershell
.venv312\Scripts\python.exe -m py_compile expert_main.py src\llm_batch\candidate_audit.py src\llm_batch\agentic_pipeline.py src\llm_batch\experts\orchestrator.py src\llm_batch\prompts\prompt_router.py tools\build_completed779_issue_index.py tools\compare_completed779_improvement.py
.venv312\Scripts\python.exe -m unittest tests.test_candidate_audit tests.test_judge_seed_registry tests.test_title_lead_search_inferred_guard tests.test_agentic_pipeline_alias_contract tests.test_final_semantic_reread_gate tests.test_expert_main_comment_metadata tests.test_expert_main_input_loader tests.test_completed779_issue_index -v
git diff --check
```

## Next Auto-Loop Prompt

Loop 2 prompt는 실행 완료된 과거 prompt다. 다음 Codex goal/thread는 `docs/devs/COMPLETED779_HERMES_CONTINUOUS_GOAL_PROMPT.md`의 `Copy-Paste Prompt`를 사용한다. 이 prompt는 Loop 2 remaining queue `8`건을 시작점으로 삼고, queue가 비거나 명시 HOLD/human_review/quarantine 될 때까지 반복한다.

## 2026-06-23 Loop 7 Fix1 / Partial Image Evidence

- subagent/council fan-out:
  - runtime/code hook, OCR/visual, source/search, verification/docs 4축을 병렬로 실행했고 완료 agent는 모두 닫았다.
  - subagent 의견은 승인 근거가 아니라 main Codex 재확인 입력으로만 사용했다.
- implementation:
  - `src/llm_batch/agentic_pipeline.py`: title lookup/memory query 행은 recommendation guard null을 검색 hit만으로 해제하지 않도록 보강했다.
  - `tests/test_agentic_pipeline_rework.py`: `11705239`형 “제목 찾아주라” 케이스가 단일 작품으로 과승격되지 않는 회귀 테스트를 추가했다.
- text canary:
  - `11705239` pre-fix single quarantine은 `logs/expert_run_20260623_050058_659227.log`에서 postprocess hang을 재현했고 result/checkpoint가 쓰이지 않았다.
  - post-fix single: `out/completed779_improvement_goal_20260622/canary/hermes_loop7_text_single_11705239_fix1_result.json`, completed/flushed/pending/failed `1/1/0/0`.
  - final state: `official_title=null`, `heretic_url=null`, `work_resolution=none`, `candidate_ledger_status=promotion_blocked`, `title_resolution_state=unresolvable_memory_query`.
  - text combined fix1: `out/completed779_improvement_goal_20260622/canary/hermes_loop7_broader_residual_text_combined_fix1_result.json`, rows `16/16`.
  - text compare: `out/completed779_improvement_goal_20260622/compare/hermes_loop7_broader_residual_text_fix1_compare.json`, movement `resolved_expected_title_and_url=1`, `review=4`, `still_under_resolved_or_noise=9`, `title_or_url_still_mismatched=2`.
- image/OCR canary:
  - broad run `20260623_052157_158066`: effective parallel `2`, partial result `19/20`, missing `11716480`.
  - result: `out/completed779_improvement_goal_20260622/canary/hermes_loop7_broader_residual_image_ocr_fix1_result.json`.
  - image compare: `out/completed779_improvement_goal_20260622/compare/hermes_loop7_broader_residual_image_ocr_fix1_compare.json`, movement `candidate_or_human_review_preserved=5`, `resolved_expected_title=1`, `review=8`, `still_under_resolved_or_noise=1`, `url_lint_preserved=4`.
  - `11716480` single quarantine input: `out/completed779_improvement_goal_20260622/inputs/hermes_loop7_image_ocr_single_11716480_quarantine.jsonl`.
  - single rerun `20260623_061321_455105` also reached strong OCR/Jury title evidence but stopped before writing result/checkpoint; manifest remained `completed=0`.
  - blocker log: `logs/expert_run_20260623_061321_455105.log`. Key issue: VLM direct title and Jury recover `여대생 가랑이 사이 무릎 꿇은 엄마들`, but search/candidate-map and postprocess flow first discard it, then later recover it, then hangs after confidence normalization.
- combined partial compare:
  - combined result: `out/completed779_improvement_goal_20260622/canary/hermes_loop7_broader_residual_combined_fix1_partial35_result.json`, rows `35/36`.
  - compare: `out/completed779_improvement_goal_20260622/compare/hermes_loop7_broader_residual_combined_fix1_partial35_compare.json`, rows `35/35`.
  - movement: `candidate_or_human_review_preserved=5`, `resolved_expected_title=1`, `resolved_expected_title_and_url=1`, `review=12`, `still_under_resolved_or_noise=10`, `title_or_url_still_mismatched=2`, `url_lint_preserved=4`.
  - next queue: `out/completed779_improvement_goal_20260622/hermes_loop7_broader_residual_next_queue_fix1_partial35.json`, rows `12`, plus runtime quarantine `11716480`.
- newly observed generalized issues:
  - VLM/OCR direct title can be discarded when `candidate_map` lacks the OCR title even when image surface is `official_detail_page`.
  - generic search results such as `인터넷 방송인` can temporarily outrank source-local OCR title.
  - genre/adult tags are repeatedly sent through decoder despite an explicit image title/author anchor.
  - author normalization can truncate `후타보로` to `후타보`.
  - postprocess can hang after canonical suspect correction / J10 exception / confidence normalization before checkpoint flush.
- status:
  - runtime integrity: Loop 7 fix1 is partial, not complete, because `11716480` is quarantined.
  - semantic quality: `REVIEW-LOCKED`.
  - full scan approval: `false`.

## 2026-06-23 Loop 7 Fix17 / Queue-0 Closure Evidence

- Loop 7 final combined accounting is no longer partial.
  - final combined result: `out/completed779_improvement_goal_20260622/canary/hermes_loop7_broader_residual_combined_fix6_final36_result.json`, rows `36/36`.
  - fix7 unwrapped compare: `out/completed779_improvement_goal_20260622/compare/hermes_loop7_broader_residual_combined_fix7_unwrapped_final36_compare.json`, rows `36/36`.
  - fix7 movement: `candidate_or_human_review_preserved=13`, `resolved_expected_title=1`, `resolved_expected_title_and_url=1`, `review=12`, `still_under_resolved_or_noise=2`, `url_lint_preserved=7`.
  - fix7 next queue: `out/completed779_improvement_goal_20260622/hermes_loop7_broader_residual_next_queue_fix7_unwrapped_final36.json`, rows `2`.
- Remaining rows were processed as targeted generalized fixes.
  - `11711600`: closed by candidate preservation for `망할 놈의 아카데미`.
  - `11706832`: fix11 closed the queue by candidate/human-review preservation, then fix17 improved the semantic output to resolved expected title.
- `11706832` fix17 evidence:
  - result: `out/completed779_improvement_goal_20260622/canary/hermes_loop7_fix17_j11_alias_lock_11706832_result.json`.
  - compare: `out/completed779_improvement_goal_20260622/compare/hermes_loop7_fix17_j11_alias_lock_11706832_compare.json`.
  - next queue: `out/completed779_improvement_goal_20260622/hermes_loop7_fix17_j11_alias_lock_next_queue.json`, rows `0`.
  - final identity: `novel_identity.official_title=황제폐하가 웹소설 작가임을 숨김`, `heretic_url=https://novelpia.com/novel/385635`, `work_resolution=resolved`, `title_resolution_state=resolved`, `candidate_ledger_status=safe_resolved`.
  - compare movement: `resolved_expected_title=1`.
- Generalized fix hooks now in scope:
  - short community alias probes strip Korean particles and preserve alias-style review/search queries.
  - `short_alias_bridge` search profile prefers community bridge evidence, allows bounded author/abbreviation probes, and filters false official detail hits that do not share alias or bridge phrase support.
  - relation verifier counts community alias support from community URL domains even when `page_type` is absent.
  - relation alias official-detail lock protects a verifier/current official title from J11 title-drift correction when community alias support and official detail evidence converge.
  - OCR-only title evidence no longer claims official search evidence in reason/provenance.
- Active next work:
  - Loop 7 hard queue is `0`; do not keep reprocessing it as the next main task.
  - Start the next Hermes loop by selecting a new high-risk expansion from completed779 native-web non-ACCEPT, source-correctness residuals, controls, or stale `review`/URL hygiene rows.
  - Keep `11694064`, Loop 1 `wrong_work=9`, `11702087`, `11705239`, `11716480`, and `11706832` as regression controls.
  - Continue to keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, and `slang_db` write-back off unless explicitly requested.
