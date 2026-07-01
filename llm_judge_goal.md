# JUDGE3905 Continuous Improvement Goal

이 문서는 다음 Codex goal/agent가 종료 보고에서 멈추지 않고, JUDGE3905 head-slice 기반 개선 연구, evidence-first review, targeted test-run, compare, docs 갱신 루프를 계속 진행하게 하기 위한 목표 문서다.

## Objective

JUDGE3905 P0/head-slice와 지금까지의 source-enriched, high-risk, focused, random50, remaining output-lint closure 결과를 기반으로 남은 품질 이슈를 계속 줄인다.

목표는 full 10만 scan approval이 아니다. 남은 이슈를 post_id/evidence 단위로 검토하고, 일반화 가능한 pipeline 개선만 구현한 뒤, targeted `expert_main.py` canary/test-run, compare, runtime/quality summary, docs 갱신까지 반복한다.

## Current State

- Seed registry: `out/judge3905_p0_seed_registry/judge3905_p0_seed_registry.json`
- Remaining closure summary: `out/judge3905_p0_seed_registry/judge3905_p0_remaining_output_lint_closure_summary.json`
- Manual evidence packets: `out/judge3905_p0_seed_registry/judge3905_p0_remaining_output_lint_manual_evidence_packets.json`
- Closure compare: `out/judge3905_p0_seed_registry/judge3905_p0_remaining_output_lint_closure_compare.json`
- Latest combined15 evidence: expected/result/compared `15/15/15`, missing `0`
- Latest after labels: `safe_resolved=4`, `promotion_blocked=7`, `hold_unresolved=1`, `output_consistency_lint=3`
- `11639284`: control-only rerun id `20260615_194903_574111`, runtime `GO`, precision control `promotion_blocked`
- `11636134`: title hygiene guard로 `불패의 명장으로 착각당했다`에 재정렬, `safe_resolved`
- Still open manual/output-lint post_ids:
  - `11602367`
  - `11632915`
  - `11650591`
- Semantic quality remains `REVIEW-LOCKED`.
- Full scan approval remains `false`.

## Required Reading

Before editing or running:

- `docs/devs/SCAN_RESULT_REVIEW_GUIDE.md`
- `docs/devs/SAMPLING_AND_PARALLEL_TEST_GUIDE.md`
- `docs/devs/OPERATION_QUALITY_CHECKLIST.md`
- `docs/devs/TODO.md`
- `docs/devs/CHECKLIST.md`
- `docs/devs/HISTORY.md`
- `docs/devs/IMPROVEMENT_REGISTER.md`
- `docs/devs/VERIFICATION_RESULTS.md`
- `docs/devs/JUDGE3905_REPORT.md`
- `docs/devs/JUDGE3905_P0_SEED_REGISTRY_CANARY_20260614.md`
- `expert_main.py`
- `src/llm_batch/candidate_audit.py`
- `src/llm_batch/models.py`
- `src/llm_batch/batch_context.py`
- `src/llm_batch/slang_db.py`
- `src/llm_batch/prompts/prompt_router.py`
- `tests/test_candidate_audit.py`

## Operating Rules

- Separate run integrity from semantic quality in every report.
- Do not promote targeted canary, high-risk, focused, or random50 evidence to full scan approval.
- Keep semantic quality `REVIEW-LOCKED` until expanded random/high-risk review and remaining manual evidence are genuinely closed.
- Work from actual files, manifests, checkpoints, logs, compare output, evidence packets, and result rows.
- For every `post_id`, inspect source text, recovered/current result, image evidence, search evidence, judge note, candidate ledger, and final lint before changing behavior.
- Do not hardcode post_id-specific fixes.
- Do not broaden `official_title` promotion casually.
- Preserve candidates in `candidate_ledger`; separate candidate preservation, promotion guard, hold/lint, and final safe resolution.
- For image/OCR cases, distinguish image loading, OCR text, explicit title evidence, official/platform confirmation, and final semantic correctness.
- For small targeted runs, use `--parallel min(input_count,36)` or a lower stable parallel. Do not confuse Codex review subagents with `expert_main.py --parallel`.
- Keep docs/checklists current during the run.

## Next Improvement Loop

### 1. Re-review open post_ids

Review these first:

- `11602367`
- `11632915`
- `11650591`

For each post_id, build or update an evidence packet with:

- original source row and URL
- content/body/comment context
- recovered or latest result row
- `image_evidence_catalog`
- `search_evidence_catalog`
- judge seed note and disagreement type
- `candidate_ledger`
- `official_title`, `heretic_url`, `work_resolution`, `discussion_type`
- current `candidate_ledger_status`
- `official_title_lint`, `identity_consistency_lint`, `output_consistency_lint`
- final recommendation: `no_action`, `re_search`, `re_judge`, `re_run`, `human_review`, `slang_db_review`, or `docs_issue`

Classify each row as:

- pipeline bug
- evidence 부족
- OCR/title hygiene problem
- promotion guard correctly blocked
- judge seed ambiguous/wrong
- manual adjudication needed

If a case should not be automated, document why.

### 2. Implement only generalizable fixes

Patch only if the rule is general and evidence-backed.

Preferred directions:

- `wrong_relevance` / false negative: preserve novel-related candidate signals in `candidate_ledger` or `hold_unresolved`; do not force `official_title`.
- `title_noisy_ocr`: image OCR alone is not enough for correction; require official/platform/source evidence.
- Partial, ellipsis, malformed, or noisy titles: block promotion or keep hygiene lint unless official evidence is strong.
- Cross-media/famous title mismatch: keep `promotion_blocked` and candidate preservation before public `official_title`.
- Slang/alias behavior: separate extracted, saved, blocked, pending, family alias, and display state.
- Prompt/router/schema changes must stay compact and follow existing `models.py`, `batch_context.py`, `slang_db.py`, `prompt_router.py`, and `candidate_audit.py` patterns.

### 3. Build a targeted canary

Create a source-backed targeted input containing:

- the open 3 post_ids
- positive/control regression seeds from the previous closure
- optionally 10-30 similar registry seeds from `title_noisy_ocr`, `wrong_relevance`, partial-title, OCR-title, or precision mismatch buckets

Keep `content_blocks`, `image_urls`, comments, and `_judge_seed` metadata where available.

### 4. Run `expert_main.py`

Use `.venv312\Scripts\python.exe`.

Preferred endpoint/model:

```powershell
--llm-endpoint http://10.20.0.101:8000
--llm-model bg-digitalservices/Gemma-4-E4B-it-NVFP4
```

Use:

```powershell
--server-type vllm --reuse-shards-only --no-dashboard --slang-db on --vlm on --ocr on --require-vlm-ocr-for-images
```

Record:

- command
- input path
- result path
- checkpoint path
- manifest path
- log path
- run id
- input/completed/flushed/pending/failed
- effective parallel
- image post count
- VLM/OCR readiness
- runtime contract

If execution is impossible, write the preflight failure and an exact resume command.

### 5. Compare and analyze

Compare:

- previous combined15 closure
- new targeted canary result
- registry seed expectation
- source-enriched/high-risk/focused/random50 context

Check:

- missing/extra post_ids
- candidate ledger presence
- `safe_resolved`, `promotion_blocked`, `hold_unresolved`, `output_consistency_lint` movement
- `official_title` over-promotion or over-demotion
- OCR/title hygiene changes
- slang DB pollution or blocking
- schema/validation/prompt/checkpoint/timeout/runtime problems

Produce compare and quality summary artifacts.

### 6. Validate

Run at minimum:

```powershell
.venv312\Scripts\python.exe -m py_compile src\llm_batch\candidate_audit.py expert_main.py tests\test_candidate_audit.py tools\build_judge_seed_registry.py tools\audit_goal_test_run_contract.py
.venv312\Scripts\python.exe -m unittest tests.test_candidate_audit tests.test_judge_seed_registry tests.test_goal_test_run_contract_audit -v
git diff --check
```

Add or run more tests when touching `models.py`, `batch_context.py`, `slang_db.py`, `prompt_router.py`, input builders, or runtime audit tools.

### 7. Update docs

Update the smallest sufficient set, but do not leave durable findings only in chat.

Must consider:

- `docs/devs/TODO.md`
- `docs/devs/CHECKLIST.md`
- `docs/devs/HISTORY.md`
- `docs/devs/IMPROVEMENT_REGISTER.md`
- `docs/devs/VERIFICATION_RESULTS.md`
- `docs/devs/JUDGE3905_REPORT.md`
- `docs/devs/JUDGE3905_P0_SEED_REGISTRY_CANARY_20260614.md`

Every docs update must keep these separate:

- runtime integrity
- targeted canary status
- semantic quality
- full scan approval status

## Completion Criteria

This goal is complete only for the current loop when all are true:

- Open post_ids have updated evidence packets or clear missing-evidence notes.
- Any implemented fix is generalizable and tested.
- Cases not automated have documented reasons.
- A targeted `expert_main.py` run or explicit preflight failure exists.
- Compare/runtime/quality summary artifacts exist.
- Required validation commands have been run.
- Docs/checklists/history/registers are updated.
- Semantic quality remains `REVIEW-LOCKED` unless a separate, properly scoped approval goal proves otherwise.
- Full scan approval is not claimed.

If any item is incomplete, keep working the loop rather than treating the current slice as final approval.
