# completed779 Reimprovement Loop 2 Goal Prompt

이 문서는 completed779 Loop 1 이후 남은 post-fix-adjusted `reimprovement_queue` `25`건을 다음 Codex goal/thread에서 그대로 실행하기 위한 운영 프롬프트다. 목적은 전체 completed779를 다시 흔드는 것이 아니라, active queue의 두 잔여 축을 줄이는 것이다.

> 2026-06-22 note: 이 prompt는 실행 완료된 Loop 2 기록이다. 다음 completed779 개선 goal은 `docs/devs/COMPLETED779_HERMES_CONTINUOUS_GOAL_PROMPT.md`를 사용한다. 현재 active queue는 Hermes Loop 3 deterministic re-audit 이후 남은 `5`건이며, queue가 비거나 명시 HOLD/human_review/quarantine 될 때까지 Hermes Council/subagent fan-out 방식으로 반복한다.

## Copy-Paste Prompt

```text
Objective:
completed779 Loop 1 이후 남은 active `reimprovement_queue` 25건을 대상으로, `expert_main.py`의 작품 식별 파이프라인을 한 단계 더 개선한다. 목표는 post_id/title 하드코딩 없이 일반화 가능한 comment/candidate preservation과 source/url hygiene 개선을 구현하고, targeted canary와 compare로 증명한 뒤 남은 실패를 Loop 2 queue로 다시 남기는 것이다.

Authoritative Evidence:
- Active contract: goal.md
- Loop 1 prompt: docs/devs/COMPLETED779_AUTO_IMPROVEMENT_GOAL_PROMPT.md
- Loop 2 prompt: docs/devs/COMPLETED779_REIMPROVEMENT_LOOP2_GOAL_PROMPT.md
- Baseline completed subset: out/expert_result_20260620_165159_711176_completed_subset.json
- Native-web judge root: out/codex_native_web_judge_20260620_165159_711176_completed779/
- Improvement root: out/completed779_improvement_goal_20260622/
- Loop 1 adjusted compare: out/completed779_improvement_goal_20260622/compare/combined_direct_search_postfix_adjusted_compare.json
- Active queue: out/completed779_improvement_goal_20260622/reimprovement_queue.json
- Active queue report: out/completed779_improvement_goal_20260622/reimprovement_queue_ko.md

Non-Negotiable Gates:
- Do not mix deterministic full_post_judge aggregate with native-web/Loop 2 queue aggregate.
- Keep semantic_quality=REVIEW-LOCKED.
- Keep full_scan_approval=false.
- Do not hardcode post_id/title-specific fixes.
- Do not write back to production slang_db. Use `--slang-db off`; if slang checks are needed, use a temporary DB path only.
- Treat direct Naver/Bing fallback as degraded-provider evidence, not normal Docker/SearXNG shard approval.
- Separate runtime integrity, targeted canary status, semantic quality, and full-scan approval in every report.
- Loop 1 controls must not regress: `garbage_title_after=0`, `11694064` must not resolve to the bad pipeline title, and `wrong_work=9` must stay off bad pipeline titles.

Loop 2 Queue Baseline:
- active rows: 25
- `still_under_resolved_or_noise=16`
- `title_or_url_still_mismatched=9`
- active `garbage_title_after=0`
- closed by post-fix canary: 3
- `11694064`: after title null, movement `blocked_or_candidate_preserved`
- `wrong_work=9`: all movement `blocked_or_candidate_preserved`

Active Post Groups:
- Candidate/comment/recall preservation group, 16 rows:
  `11695623`, `11697256`, `11698878`, `11706856`, `11708442`, `11716478`, `11716482`,
  `11697234`, `11697241`, `11697255`, `11698886`, `11698910`, `11700475`, `11702049`, `11702072`, `11703624`.
- Source/url hygiene group, 9 rows:
  `11698880`, `11698890`, `11698903`, `11700504`, `11702055`, `11708437`, `11708470`, `11711631`, `11718077`.

Required Subagent Fan-Out:
Use at least four Codex subagents if available. Their outputs are input to main Codex, not approval evidence.

1. candidate/comment expert:
   - Inspect the 16 `still_under_resolved_or_noise` rows.
   - Identify how comment answers, short aliases, OCR/title image evidence, recommendation candidates, and character/setting clusters are being lost.
   - Propose candidate ledger/HOLD fixes without unsafe promotion.

2. source/url hygiene expert:
   - Inspect the 9 `title_or_url_still_mismatched` rows.
   - Map each to official detail URL canonicalization, stale/wrong URL demotion, mobile/detail URL normalization, or title-url mismatch lint.
   - Propose tests for exact title+official URL and unsafe HOLD/lint outcomes.

3. code-hook expert:
   - Map fixes to:
     - src/llm_batch/agentic_pipeline.py
     - src/llm_batch/experts/orchestrator.py
     - src/llm_batch/prompts/prompt_router.py
     - src/llm_batch/candidate_audit.py
     - src/llm_batch/mcp_bridge/server.py
     - expert_main.py
   - Avoid post_id/title hardcoding.

4. verification/docs expert:
   - Define input split, canary commands, compare commands, NO-GO controls, and docs sync.
   - Keep REVIEW-LOCKED and full_scan_approval=false.

Main Codex Workflow:
1. Preflight:
   - Read `out/completed779_improvement_goal_20260622/reimprovement_queue.json`.
   - Confirm active rows `25`, movement counts `still_under_resolved_or_noise=16`, `title_or_url_still_mismatched=9`, active `garbage_title_after=0`.
   - Confirm `11694064` and `wrong_work=9` are control rows from Loop 1 adjusted compare, not active failures.
   - Verify the current vLLM model with `http://10.20.0.101:8000/v1/models`; use the live model name in commands.

2. Build Loop 2 inputs:
   - Add helper if useful: `tools/build_completed779_reimprovement_inputs.py`.
   - Join the active queue with `out/expert_result_20260620_165159_711176_completed_subset.json`.
   - Output:
     - `out/completed779_improvement_goal_20260622/inputs/reimprovement_loop2_text_url_comment.jsonl`
     - `out/completed779_improvement_goal_20260622/inputs/reimprovement_loop2_image_ocr.jsonl`
   - Record counts and post IDs. Text and image/OCR must be reported separately.

3. Implement generalized fixes:
   - Candidate/comment/recall:
     - Preserve comment answer candidates and recommendation candidates in candidate ledger even when final title promotion is blocked.
     - Add short alias/comment/OCR/character cluster search probes where current search intent drops them.
     - Multi-candidate and recommendation contexts should become HOLD/human_review or candidate-preserved, not a forced single title.
   - Source/url hygiene:
     - Prefer official detail URL canonicalization over wiki/person/community URLs.
     - Normalize mobile/detail platform URLs when safe.
     - If title and URL disagree, keep title/url mismatch lint or HOLD instead of pretending success.
   - Controls:
     - Prevent snippet/breadcrumb title pollution.
     - Keep `11694064` and `wrong_work=9` off bad pipeline titles.

4. Static and focused tests:
   - Run:
     `.venv312\Scripts\python.exe -m py_compile expert_main.py src\llm_batch\candidate_audit.py src\llm_batch\agentic_pipeline.py src\llm_batch\experts\orchestrator.py src\llm_batch\prompts\prompt_router.py src\llm_batch\mcp_bridge\server.py tools\build_completed779_issue_index.py tools\compare_completed779_improvement.py`
   - Run focused suite:
     `.venv312\Scripts\python.exe -m unittest tests.test_candidate_audit tests.test_judge_seed_registry tests.test_title_lead_search_inferred_guard tests.test_agentic_pipeline_alias_contract tests.test_final_semantic_reread_gate tests.test_expert_main_comment_metadata tests.test_expert_main_input_loader tests.test_completed779_issue_index tests.test_completed779_compare tests.test_mcp_bridge_direct_search -v`
   - Add focused tests for any new helper or new guard.

5. Text/url/comment canary:
   - Run:
     `.venv312\Scripts\python.exe expert_main.py out\completed779_improvement_goal_20260622\inputs\reimprovement_loop2_text_url_comment.jsonl --server-type vllm --llm-endpoint http://10.20.0.101:8000 --llm-model <LIVE_MODEL> --reuse-shards-only --no-dashboard --slang-db off --parallel <TEXT_COUNT_OR_36_CAP>`
   - If normal search shards are down and direct fallback is used, label the run degraded-provider.

6. Image/OCR canary:
   - Run:
     `.venv312\Scripts\python.exe expert_main.py out\completed779_improvement_goal_20260622\inputs\reimprovement_loop2_image_ocr.jsonl --server-type vllm --llm-endpoint http://10.20.0.101:8000 --llm-model <LIVE_MODEL> --reuse-shards-only --no-dashboard --slang-db off --parallel <IMAGE_COUNT_OR_36_CAP> --vlm on --ocr on --require-vlm-ocr-for-images`
   - Record VLM/OCR Semantic Gate separately from semantic approval.

7. Compare:
   - For each canary result:
     `.venv312\Scripts\python.exe tools\compare_completed779_improvement.py --seed out\completed779_improvement_goal_20260622\reimprovement_queue.json --before out\expert_result_20260620_165159_711176_completed_subset.json --after <LOOP2_RESULT_JSON> --out-json out\completed779_improvement_goal_20260622\compare\<LOOP2_RUN>_compare.json --out-md out\completed779_improvement_goal_20260622\compare\<LOOP2_RUN>_compare.md --out-queue out\completed779_improvement_goal_20260622\compare\<LOOP2_RUN>_queue.json --canary-kind reimprovement_loop2 --only-after-posts`
   - Create combined result and combined compare for all 25 rows when both canaries finish.
   - If compare helper does not yet accept queue-shaped seed rows, extend it or convert queue rows to seed shape with a helper.

8. Acceptance audit:
   - `still_under_resolved_or_noise` rows should move to candidate preserved, unresolved_matchable, HOLD/human_review, or resolved expected title when source evidence is strong.
   - `title_or_url_still_mismatched` rows should move to exact title+official detail URL, URL changed/upgraded, URL mismatch lint, or HOLD.
   - Active `garbage_title_after` must remain `0`.
   - `11694064` must not finalize as `무협 게임에 빙의했다...스킵충이다`.
   - `wrong_work=9` must not regress into still-bad pipeline titles.
   - Any unsafe over-promotion is semantic NO-GO.

9. Re-improvement queue:
   - Write:
     - `out/completed779_improvement_goal_20260622/reimprovement_loop2_queue.json`
     - `out/completed779_improvement_goal_20260622/reimprovement_loop2_queue_ko.md`
   - Include post_id, bucket, issue, before title/url, after title/url, expected movement, observed problem, suspected hook, proposed next fix, and required test.

10. Docs and checklist sync:
   - Update:
     - goal.md
     - docs/devs/TODO.md
     - docs/devs/CHECKLIST.md
     - docs/devs/HISTORY.md
     - docs/devs/IMPROVEMENT_REGISTER.md
     - docs/devs/VERIFICATION_RESULTS.md
   - Keep runtime integrity, targeted canary status, semantic quality, and full-scan approval separate.
   - Run `git diff --check`.

Completion Criteria:
- Active queue preflight proves rows `25`, split `16/9`, active `garbage_title_after=0`.
- Loop 2 input files exist and counts match active queue.
- Generalized fixes are implemented without post_id/title hardcoding.
- Text/url/comment and image/OCR canaries complete their input rows, or preflight failure and exact resume commands are recorded.
- Compare artifacts exist for every completed canary and a combined 25-row view if both canaries complete.
- `11694064`, `wrong_work=9`, and `garbage_title_after=0` controls are explicitly audited.
- Remaining bad/ambiguous rows are written to Loop 2 reimprovement queue.
- Docs/checklists/history/register/verification results are updated.
- `git diff --check` passes.
- semantic_quality remains REVIEW-LOCKED.
- full_scan_approval remains false.
```

## Operator Notes

- Loop 2 starts from active queue `25`, not the original balanced P0 `65` as the primary failure list.
- Original `65` adjusted compare remains the control baseline for regression checks.
- Normal Docker/SearXNG shard search is preferred; direct fallback is acceptable only when labeled degraded-provider.
- The expected success for many rows is not necessarily public `official_title` promotion. Candidate preservation, HOLD, human_review, or URL mismatch lint can be the correct safer movement.

## 2026-06-22 Execution Result

- This prompt was executed as completed779 Reimprovement Loop 2.
- Runtime:
  - text/url/comment canary: `out/expert_result_20260622_201044_448457.json`, `8/8`.
  - image/OCR canary: `out/expert_result_20260622_201630_167085.json`, `17/17`, VLM/OCR Semantic Gate `READY`.
  - provider status: direct Naver/Bing fallback, degraded-provider evidence only.
- Compare:
  - combined result: `out/completed779_improvement_goal_20260622/compare/reimprovement_loop2_combined_result.json`, rows `25`.
  - combined compare: `out/completed779_improvement_goal_20260622/compare/reimprovement_loop2_combined_compare.json`, rows `25/25`.
  - movement: `candidate_or_human_review_preserved=7`, `resolved_expected_title=1`, `url_lint_preserved=9`, `still_under_resolved_or_noise=8`.
- Remaining queue:
  - `out/completed779_improvement_goal_20260622/reimprovement_loop2_queue.json`
  - `out/completed779_improvement_goal_20260622/reimprovement_loop2_queue_ko.md`
  - rows `8`, all `still_under_resolved_or_noise`.
- Controls:
  - active `garbage_title_after=0`.
  - `11694064` did not resolve to the bad pipeline title.
  - `wrong_work=9` did not regress to bad pipeline titles.
- Gates:
  - `semantic_quality=REVIEW-LOCKED`
  - `full_scan_approval=false`
