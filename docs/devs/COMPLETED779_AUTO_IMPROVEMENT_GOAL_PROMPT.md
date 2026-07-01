# completed779 자동 개선 연구·검증·재개선 Goal Prompt

이 문서는 다음 Codex goal/thread에 그대로 붙여 넣어 실행할 수 있는 운영 프롬프트다. 목적은 completed779 native-web judge에서 나온 `266`개 non-ACCEPT와 balanced P0 seed `65`건을 기반으로, 자동 개선 연구 → 코드/프롬프트/오케스트레이션 수정 → `expert_main.py` canary → compare → 재개선 큐 생성을 반복하는 것이다.

사용자가 새 goal을 시작할 때는 아래 `Copy-Paste Prompt` 코드블록 전체를 그대로 붙여 넣는다. 실행 중 확인된 최신 운영 메모는 이 파일 하단 `Operator Notes`와 active contract `goal.md`를 함께 본다.

## Copy-Paste Prompt

```text
Objective:
completed779 native-web verdict 기반 issue index와 balanced P0 seed를 사용해 `expert_main.py`의 작품 식별 파이프라인을 자동 개선 연구, 구현, 검증, 재개선한다. 단순 보고서 작성이 아니라 실제 일반화 가능한 코드/프롬프트/오케스트레이션 개선을 적용하고, targeted canary와 compare로 효과를 증명한 뒤 docs를 갱신한다.

Authoritative Evidence:
- Active contract: goal.md
- Prior archived goal: llm_judge_goal.md
- Baseline result: out/expert_result_20260620_165159_711176_completed_subset.json
- Native-web judge root: out/codex_native_web_judge_20260620_165159_711176_completed779/
- Improvement root: out/completed779_improvement_goal_20260622/
- Issue index: out/completed779_improvement_goal_20260622/native_web_issue_index.json
- Korean issue report: out/completed779_improvement_goal_20260622/native_web_issue_index_ko.md
- Action queue: out/completed779_improvement_goal_20260622/action_queue_by_post_id.json
- Seed packet: out/completed779_improvement_goal_20260622/balanced_p0_seed.jsonl
- Text/url/comment canary input: out/completed779_improvement_goal_20260622/inputs/balanced_p0_text_url_comment.jsonl
- Image/OCR canary input: out/completed779_improvement_goal_20260622/inputs/balanced_p0_image_ocr.jsonl

Non-Negotiable Gates:
- Do not mix deterministic full_post_judge_report aggregate with native-web aggregate.
- Use native-web verdict aggregate for improvement priority: total 779, non-ACCEPT 266, missing 0, duplicate after dedupe 0.
- Keep semantic_quality=REVIEW-LOCKED.
- Keep full_scan_approval=false.
- Do not hardcode post_id/title-specific fixes.
- Do not write back to production slang_db. Use `--slang-db off`; if slang checks are needed, use a temporary DB path only.
- Treat native-web judge as a strong external baseline, not gold truth.
- Separate runtime integrity, targeted canary status, semantic quality, and full-scan approval in every report.

Known Baseline:
- Resolution labels: ACCEPT=513, REPROCESS=208, HOLD=49, INFO_MISSING=7, REJECT=2.
- Top issue axes: under_resolved=68, under_resolved_false_negative=64, wrong_relevance=62, heretic_url_null=13, wrong_work=9, candidate_preservation_missing=6, garbage_title=6, reason_evidence_mismatch=6, conflicting_or_multi_candidate=5, comment_explicit_title_missed=4.
- Macro buckets: recall/under-resolution=142, relevance boundary=73, primary-selection/identity precision=30, source/url hygiene=23, manual/info gap=8.
- Balanced P0 seed total=65: precision/identity 15, candidate/comment/multi-candidate 15, recall/relevance 25, source/url hygiene 10.
- Sentinel `11694064` must be included. It should not resolve to `무협 게임에 빙의했다. 문제는 나는 스토리를 보지 않는 스킵충이다`; correct target is `판초우의의 마법사` or a conservative HOLD/candidate-conflict state.
- `wrong_work=9` entire set must be included in verification, not only `11694064`.

Required Subagent Fan-Out:
Use at least four Codex subagents if the tool is available. Their outputs are input to the main Codex, not approval evidence.

1. taxonomy/source expert:
   - Re-read native_web_issue_index.json and action_queue_by_post_id.json.
   - Verify the 266 non-ACCEPT issue taxonomy and the 65 seed composition.
   - Identify the smallest generalizable P0 patterns; do not propose post_id hardcoding.

2. code-hook expert:
   - Map each issue axis to concrete code hooks:
     - src/llm_batch/candidate_audit.py
     - src/llm_batch/agentic_pipeline.py
     - src/llm_batch/experts/orchestrator.py
     - src/llm_batch/prompts/prompt_router.py
     - expert_main.py
   - Propose exact tests to cover each hook.

3. prompt/orchestration expert:
   - Improve search intent and prompt wording for comments, OCR, short aliases, character/setting clusters, author/new-work context, and multi-candidate preservation.
   - Ensure recommendation lists and comment-sourced candidates are preserved instead of forced into a single title.

4. verification/docs expert:
   - Define canary commands, compare commands, expected movement statuses, docs/checklist updates, and NO-GO conditions.
   - Keep `semantic_quality=REVIEW-LOCKED` and `full_scan_approval=false`.

Main Codex Workflow:
1. Preflight:
   - Rebuild or validate the issue index:
     `.venv312\Scripts\python.exe tools\build_completed779_issue_index.py --result out\expert_result_20260620_165159_711176_completed_subset.json --judge-root out\codex_native_web_judge_20260620_165159_711176_completed779 --out-dir out\completed779_improvement_goal_20260622`
   - Confirm total 779, non-ACCEPT 266, missing 0, duplicate after dedupe 0, seed total 65, bucket counts 15/15/25/10, `11694064` included, `wrong_work=9` all seeded.

2. Research and design:
   - Read `balanced_p0_seed.jsonl` and `action_queue_by_post_id.json`.
   - Group fixes into these workstreams:
     - Recall/under-resolution.
     - Relevance boundary.
     - Primary-selection precision.
     - Source/url hygiene.
     - Candidate ledger/multi-candidate.
     - Prompt/orchestration/comment/OCR.
   - Pick the smallest set of generalizable changes that should improve multiple seeds, not isolated one-off cases.

3. Implement:
   - Edit the relevant code and prompt files.
   - Preserve candidate ledger evidence, blocked/held states, and postprocess audit fields.
   - Prefer HOLD/candidate-conflict over unsafe title promotion when evidence is multi-candidate, comment-attributed, OCR-only, or source-local conflict.

4. Static and focused tests:
   - Run:
     `.venv312\Scripts\python.exe -m py_compile expert_main.py src\llm_batch\candidate_audit.py src\llm_batch\agentic_pipeline.py src\llm_batch\experts\orchestrator.py src\llm_batch\prompts\prompt_router.py tools\build_completed779_issue_index.py tools\compare_completed779_improvement.py`
   - Run:
     `.venv312\Scripts\python.exe -m unittest tests.test_candidate_audit tests.test_judge_seed_registry tests.test_title_lead_search_inferred_guard tests.test_agentic_pipeline_alias_contract tests.test_final_semantic_reread_gate tests.test_expert_main_comment_metadata tests.test_expert_main_input_loader tests.test_completed779_issue_index -v`
   - Add or update focused tests for the actual change. Do not rely only on pre-existing green tests.

5. Text/url/comment canary:
   - Run:
     `.venv312\Scripts\python.exe expert_main.py out\completed779_improvement_goal_20260622\inputs\balanced_p0_text_url_comment.jsonl --server-type vllm --llm-endpoint http://10.20.0.101:8000 --llm-model bg-digitalservices/Gemma-4-26B-A4B-it-NVFP4 --reuse-shards-only --no-dashboard --slang-db off --parallel 19`
   - If the vLLM endpoint or shard health blocks execution, write a preflight failure record with the exact resume command. Do not claim semantic improvement.
   - If you explicitly continue after search shard failure, label the run `degraded_no_search`. It may prove runtime/candidate-audit movement, but it is not search-enabled semantic approval.

6. Image/OCR canary:
   - Run:
     `.venv312\Scripts\python.exe expert_main.py out\completed779_improvement_goal_20260622\inputs\balanced_p0_image_ocr.jsonl --server-type vllm --llm-endpoint http://10.20.0.101:8000 --llm-model bg-digitalservices/Gemma-4-26B-A4B-it-NVFP4 --reuse-shards-only --no-dashboard --slang-db off --parallel 36 --vlm on --ocr on --require-vlm-ocr-for-images`
   - If image/OCR canary cannot run, record it separately from text canary. Do not use text canary to approve image/OCR behavior.
   - If you explicitly continue after search shard failure, label the run `degraded_no_search` while still recording VLM/OCR gate readiness separately.

7. Compare:
   - For each canary output result JSON, run:
     `.venv312\Scripts\python.exe tools\compare_completed779_improvement.py --seed out\completed779_improvement_goal_20260622\balanced_p0_seed.jsonl --before out\expert_result_20260620_165159_711176_completed_subset.json --after <CANARY_RESULT_JSON> --out-json out\completed779_improvement_goal_20260622\compare\<RUN_ID>_compare.json --out-md out\completed779_improvement_goal_20260622\compare\<RUN_ID>_compare.md --out-queue out\completed779_improvement_goal_20260622\compare\<RUN_ID>_reimprovement_queue.json --canary-kind <text_url_comment|image_ocr|combined> --only-after-posts`
   - If text and image/OCR are separate outputs, create one compare per output and a combined Korean summary.
   - For a combined 65-row output, omit `--only-after-posts` only when the after file actually contains all 65 seed rows.

8. Semantic acceptance audit:
   - `11694064`: must no longer finalize as `무협 게임에 빙의했다...스킵충이다`.
   - `wrong_work=9`: each must become resolved-correct, HOLD, or candidate conflict. Any still-bad wrong-work is NO-GO.
   - Recall/relevance seeds: should move from null/noise into candidate preserved, unresolved_matchable, resolved, or explicit human_review. Unsafe over-promotion is NO-GO.
   - Source/url hygiene seeds: should gain official detail URL or retain URL mismatch lint/HOLD.
   - Multi-candidate/comment/OCR seeds: candidate preservation beats forced single-title promotion.
   - Controls: if a new over-promotion appears, record semantic NO-GO and create a re-improvement queue.

9. Re-improvement queue:
   - If any semantic NO-GO remains, create:
     - `out/completed779_improvement_goal_20260622/reimprovement_queue.json`
     - `out/completed779_improvement_goal_20260622/reimprovement_queue_ko.md`
   - Queue rows must include post_id, seed bucket, before title/url, after title/url, expected movement, observed problem, suspected code hook, proposed next fix, and required test.

10. Docs and checklist sync:
   - Update:
     - goal.md
     - docs/devs/TODO.md
     - docs/devs/CHECKLIST.md
     - docs/devs/HISTORY.md
     - docs/devs/IMPROVEMENT_REGISTER.md
     - docs/devs/VERIFICATION_RESULTS.md
   - Optional runbook update if the procedure changed:
     - docs/devs/FULL_POST_JUDGE_RUNBOOK.md
   - Keep runtime integrity, targeted canary status, semantic quality, and full-scan approval separate.

Completion Criteria:
- Issue index still proves 779/779, missing 0, non-ACCEPT 266, duplicate after dedupe 0.
- Code/prompt/orchestration changes are implemented and covered by focused tests.
- Text/url/comment canary completed all 19 rows with failed=0 and pending=0, or a preflight failure with exact resume command is recorded.
- Image/OCR canary completed all 46 rows with failed=0 and pending=0, or a separate preflight failure with exact resume command is recorded.
- Compare artifacts exist for every completed canary.
- `11694064` and `wrong_work=9` acceptance audit is explicitly written.
- Re-improvement queue exists if any seed remains bad or ambiguous.
- Docs/checklists/history/register/verification results are updated.
- `git diff --check` passes.
- semantic_quality remains REVIEW-LOCKED.
- full_scan_approval remains false.

Do not mark the goal complete until every completed canary has compare evidence and every required doc/checklist has been updated. If canaries cannot run, keep the goal active unless the same blocker has repeated for the required blocked-audit threshold.
```

## Operator Notes

- `out/` artifacts are ignored by git; keep them as local evidence unless the user explicitly asks to package them.
- `tools/*` and `tests/*` may also be ignored by this repository's current `.gitignore`; use forced add only if the user asks for a commit.
- If a canary result filename is unclear, inspect the new manifest/result files under `out/` immediately after running `expert_main.py` and use the concrete result path in compare commands.
- Do not use a narrow static test pass as semantic proof. The improvement loop is only meaningful after canary and compare.
- Before running vLLM canaries, verify `http://10.20.0.101:8000/v1/models`. On 2026-06-22 the live model was `bg-digitalservices/Gemma-4-26B-A4B-it-NVFP4`; the older planned `bg-digitalservices/Gemma-4-E4B-it-NVFP4` returned 404.
- If Docker/SearXNG shards are down, `src/llm_batch/mcp_bridge/server.py` has a direct Naver/Bing fallback (`MCP_DIRECT_SEARCH_FALLBACK=1`) that can recover search evidence. Treat this as degraded-provider search evidence, not normal shard approval.
- Direct fallback can introduce snippet/breadcrumb title pollution. `candidate_audit` must demote snippet-like or breadcrumb-like `official_title` to `blocked_official_title`; compare should classify these as `garbage_title_after` and keep them in the re-improvement queue.
- Latest direct-search evidence roots from 2026-06-22:
  - text result: `out/expert_result_20260622_165552_032705.json`
  - image/OCR result: `out/expert_result_20260622_171928_162115.json`
  - combined compare: `out/completed779_improvement_goal_20260622/compare/combined_direct_search_compare.json`
  - post-fix polluted-title mini canary:
    - text 2 rows: `out/expert_result_20260622_183047_118075.json`
    - image/OCR 1 row: `out/expert_result_20260622_183544_060718.json`
    - combined compare: `out/completed779_improvement_goal_20260622/compare/garbage_title_postfix_combined_compare.json`
  - latest adjusted compare: `out/completed779_improvement_goal_20260622/compare/combined_direct_search_postfix_adjusted_compare.json`
  - root reimprovement queue: `out/completed779_improvement_goal_20260622/reimprovement_queue.json` and `reimprovement_queue_ko.md`, active rows `25`.
  - adjusted movement: `blocked_or_candidate_preserved=15`, `candidate_or_human_review_preserved=22`, `resolved_expected_title=2`, `resolved_expected_title_and_url=1`, `still_under_resolved_or_noise=16`, `title_or_url_still_mismatched=9`; `garbage_title_after=0`.
  - `11716482` is no longer a public-title pollution row, but remains active as comment multi-candidate preservation/under-resolution follow-up.
