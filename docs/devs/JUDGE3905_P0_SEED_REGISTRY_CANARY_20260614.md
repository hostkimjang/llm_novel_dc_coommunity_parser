# JUDGE3905 P0 seed registry / expert_main canary

## 요약

- GPT Pro judge 결과 `out/_judge3905_gpt_pro_v2/post_reviews.jsonl`를 P0 seed registry로 재포장했다.
- registry seed는 `1505`건이며 source 매칭 누락은 `0`건이다.
- group별 seed는 `recall=644`, `precision=123`, `hygiene=738`이다.
- shadow label은 `candidate_generation_miss=164`, `hold_unresolved=480`, `identity_consistency_lint=94`, `output_consistency_lint=738`, `review_only=29`이다.
- 24건 canary를 `expert_main.py`로 실제 실행했고 run integrity는 `GO`다.
- semantic quality는 계속 `REVIEW-LOCKED`다. 이 결과는 head-slice 진단 seed이며 full scan approval이 아니다.

## 산출물

- seed registry: `out/judge3905_p0_seed_registry/judge3905_p0_seed_registry.json`
- candidate ledger shadow: `out/judge3905_p0_seed_registry/judge3905_p0_candidate_ledger_shadow.jsonl`
- canary input: `out/judge3905_p0_seed_registry/judge3905_p0_expert_main_canary_input.jsonl`
- build manifest: `out/judge3905_p0_seed_registry/judge3905_p0_manifest.json`
- canary result: `out/judge3905_p0_seed_registry/judge3905_p0_expert_main_canary_result.json`
- canary manifest: `out/judge3905_p0_seed_registry/judge3905_p0_expert_main_canary_result_manifest.json`
- canary compare: `out/judge3905_p0_seed_registry/judge3905_p0_expert_main_canary_compare.json`
- canary compare summary: `out/judge3905_p0_seed_registry/judge3905_p0_expert_main_canary_compare_ko.md`

## expert_main canary

실행 명령:

```powershell
.\.venv312\Scripts\python.exe expert_main.py --input out\judge3905_p0_seed_registry\judge3905_p0_expert_main_canary_input.jsonl --output out\judge3905_p0_seed_registry\judge3905_p0_expert_main_canary_result.json --server-type vllm --parallel 24 --reuse-shards-only --no-dashboard --slang-db on --vlm on --ocr on --require-vlm-ocr-for-images --llm-endpoint http://10.20.0.101:8000 --llm-model bg-digitalservices/Gemma-4-E4B-it-NVFP4
```

결과:

- run id: `20260614_230245_886140`
- input/completed/flushed/pending/failed: `24/24/24/0/0`
- requested/effective parallel: `24/24`
- MCP health: `8/8`
- small targeted run: `true`
- shard lifecycle auto up/recreate: blocked by small-run policy
- VLM/OCR flags: on/on
- image post count: `0`
- VLM/OCR semantic review skip reason: `no_image_blocks`

## Compare 결과

- compare scope: `manifest_canary_post_ids`
- expected/result/compared: `24/24/24`
- missing result: `0`
- registry seed missing: `0`
- extra result: `0`
- official title changed: `15`
- official title lint after: `0`
- identity consistency lint after: `10`
- after shadow labels:
  - `safe_resolved=3`
  - `promotion_blocked=3`
  - `hold_unresolved=2`
  - `review_only=6`
  - `output_consistency_lint=8`
  - `identity_consistency_lint=2`

Gate:

- run integrity: `GO`
- semantic quality: `REVIEW-LOCKED`
- reason: targeted seed evidence only; random/high-risk expansion is still required.

## 2026-06-16 continuous loop follow-up

이 문서의 canary/registry는 계속 JUDGE3905 head-slice seed evidence로만 사용한다. 2026-06-16 continuous loop에서는 remaining output-lint target과 controls를 다시 묶어 runtime bug와 OCR/title hold guard를 검증했다.

### Targeted 9건 run

```powershell
.\.venv312\Scripts\python.exe expert_main.py --input out\judge3905_p0_seed_registry\judge3905_p0_continuous_loop_targeted_input.jsonl --output out\judge3905_p0_seed_registry\judge3905_p0_continuous_loop_targeted_result.json --server-type vllm --parallel 9 --reuse-shards-only --no-dashboard --slang-db on --vlm on --ocr on --require-vlm-ocr-for-images --llm-endpoint http://10.20.0.101:8000 --llm-model bg-digitalservices/Gemma-4-E4B-it-NVFP4
```

- run id: `20260615_231925_533889`
- input/completed/flushed/pending/failed: `9/9/9/0/0`
- image post count: `9`
- VLM/OCR semantic gate: `READY`
- compare expected/result/compared: `9/9/9`, missing `0`
- compare after labels: `hold_unresolved=3`, `output_consistency_lint=2`, `safe_resolved=3`, `promotion_blocked=1`
- runtime audit: `NO-GO`, because the log contains `Deliberation 오류`, `NameError`, `Traceback` on `11639284`.

### Fix reruns

- Deliberation `disc` NameError fix:
  - run id `20260615_234526_746998`
  - post_id `11639284`
  - input/completed/flushed/pending/failed `1/1/1/0/0`
  - runtime audit `GO`
  - compare label `promotion_blocked`
- OCR/title mismatch hold guard:
  - run id `20260616_000415_830530`
  - post_id `11650591`
  - input/completed/flushed/pending/failed `1/1/1/0/0`
  - runtime audit `GO`
  - compare label `hold_unresolved`

### Pipeline changes

- `src/llm_batch/experts/deliberation.py`: Jury prompt rebuild에서 discourse output을 복원해 `disc` NameError를 제거했다.
- `tools/audit_goal_test_run_contract.py`: generic traceback/NameError/Deliberation error log hits를 `runtime_log_exception`으로 잡아 `NO-GO` 처리한다.
- `src/llm_batch/candidate_audit.py`: `title_noisy_ocr` seed에서 direct image work title과 final public title이 충돌하면 official URL이 있어도 public `official_title`을 hold하고 candidate ledger에 보존한다.

### Current gate

- `11602367`: wrong_relevance semantic/manual review remains.
- `11632915`: public title overpromotion is held; semantic accept is not granted.
- `11650591`: public title overpromotion is held after focused rerun; semantic accept is not granted.
- semantic quality remains `REVIEW-LOCKED`.
- full scan approval remains `false`.

## 한계

- judge batch source에는 `img_count`와 `image_ocr`가 있어도 원본 image URL이 빠진 row가 많다.
- 이번 canary 24건 중 image seed without URL은 `18`건이다.
- 따라서 이번 canary는 judge-context 재실행 검증이지 full VLM/browser evidence 검증이 아니다.
- 다음 단계에서는 원본 image URL을 보존한 source-enriched canary를 만들어 `image_post_count > 0` 상태에서 VLM/OCR/browser gate를 다시 확인해야 한다.

## 2026-06-15 source-enriched VLM/OCR canary

기존 24건 canary의 image URL 누락을 원본 `out/expert_result_20260612_174715_296791_checkpoint.jsonl`에서 복원했다.

### Source enrichment

실행 명령:

```powershell
.\.venv312\Scripts\python.exe tools\build_judge3905_source_enriched_canary.py --canary-input out\judge3905_p0_seed_registry\judge3905_p0_expert_main_canary_input.jsonl --source out\expert_result_20260612_174715_296791_checkpoint.jsonl --source out\expert_result_20260612_174715_296791_completed_subset.json --source out\expert_result_20260612_174715_296791.json --out-dir out\judge3905_p0_seed_registry --prefix judge3905_p0
```

결과:

- input count: `24`
- image seed count: `18`
- missing image URL count: `18`
- restored count: `18`
- unrecovered count: `0`
- source-enriched input: `out/judge3905_p0_seed_registry/judge3905_p0_source_enriched_canary_input.jsonl`
- restore report: `out/judge3905_p0_seed_registry/judge3905_p0_source_enriched_canary_restore_report.json`

### Pipeline instrumentation

- `src/llm_batch/candidate_audit.py`를 추가해 candidate ledger와 promotion/lint status를 생성한다.
- `expert_main.py`는 `_judge_seed`를 `PostInput.judge_seed`로 보존하고, result row의 `analysis_result.identity`에 audit fields를 붙인다.
- `models.py`는 공개 schema에 `candidate_ledger`, `candidate_ledger_status`, `candidate_generation_miss`, `promotion_blocked`, `hold_unresolved`, `safe_resolved`, `official_title_lint`, `identity_consistency_lint`, `output_consistency_lint`를 추가했다.
- `prompt_router.py`에는 후보 보존과 official title promotion guard 문구를 보강했다.

### expert_main source-enriched canary

실행 명령:

```powershell
.\.venv312\Scripts\python.exe expert_main.py --input out\judge3905_p0_seed_registry\judge3905_p0_source_enriched_canary_input.jsonl --output out\judge3905_p0_seed_registry\judge3905_p0_source_enriched_canary_result.json --server-type vllm --parallel 24 --reuse-shards-only --no-dashboard --slang-db on --vlm on --ocr on --require-vlm-ocr-for-images --llm-endpoint http://10.20.0.101:8000 --llm-model bg-digitalservices/Gemma-4-E4B-it-NVFP4
```

결과:

- run id: `20260615_001642_376095`
- input/completed/flushed/pending/failed: `24/24/24/0/0`
- requested/effective parallel: `24/24`
- MCP health: `8/8`
- image post count: `18`
- VLM/OCR semantic gate: `READY`
- image evidence catalog / VLM enrichment / image fetch counters: `18/18`
- runtime contract audit: `GO`

### Compare

실행 명령:

```powershell
.\.venv312\Scripts\python.exe tools\build_judge_seed_registry.py compare --registry out\judge3905_p0_seed_registry\judge3905_p0_seed_registry.json --canary-result out\judge3905_p0_seed_registry\judge3905_p0_source_enriched_canary_result.json --manifest out\judge3905_p0_seed_registry\judge3905_p0_source_enriched_canary_manifest.json --output-json out\judge3905_p0_seed_registry\judge3905_p0_source_enriched_canary_compare.json --output-md out\judge3905_p0_seed_registry\judge3905_p0_source_enriched_canary_compare_ko.md
```

Compare 결과:

- expected/result/compared: `24/24/24`
- missing result: `0`
- registry seed missing: `0`
- extra result: `0`
- candidate ledger present: `24/24`
- official title changed: `16`
- official title lint after: `0`
- identity consistency lint after: `10`
- after shadow labels:
  - `safe_resolved=3`
  - `promotion_blocked=7`
  - `hold_unresolved=4`
  - `output_consistency_lint=8`
  - `identity_consistency_lint=2`

Gate:

- run integrity: `GO`
- source/VLM coverage for this canary: `GO`
- semantic quality: `REVIEW-LOCKED`
- reason: targeted 24-post head-slice seed evidence only; remaining lint rows and random/high-risk expansion are still required.

## 2026-06-15 high-risk expansion and slang DB guard

source-enriched 24건 canary 뒤에, 기존 canary와 겹치지 않는 high-risk source-backed 36건을 추가 실행했다.

### Expansion input

실행 명령:

```powershell
.\.venv312\Scripts\python.exe tools\build_judge3905_expansion_inputs.py --registry out\judge3905_p0_seed_registry\judge3905_p0_seed_registry.json --source out\expert_result_20260612_174715_296791_checkpoint.jsonl --source out\expert_result_20260612_174715_296791_completed_subset.json --source out\expert_result_20260612_174715_296791.json --exclude out\judge3905_p0_seed_registry\judge3905_p0_source_enriched_canary_manifest.json --exclude out\judge3905_p0_seed_registry\judge3905_p0_manifest.json --out-dir out\judge3905_p0_seed_registry --prefix judge3905_p0 --total 36 --quota recall=12 --quota precision=16 --quota hygiene=8
```

결과:

- selected count: `36`
- excluded previous canary post count: `24`
- missing source count: `0`
- group count: `recall=12`, `precision=16`, `hygiene=8`
- disagreement type count: `under_resolved_false_negative=12`, `cross_media_or_famous_mismatch=16`, `wrong_relevance=1`, `title_noisy_ocr=7`
- image post count: `36`
- restored source rows: `36`
- input: `out/judge3905_p0_seed_registry/judge3905_p0_highrisk_expansion_input.jsonl`

### expert_main high-risk expansion

실행 명령:

```powershell
.\.venv312\Scripts\python.exe expert_main.py --input out\judge3905_p0_seed_registry\judge3905_p0_highrisk_expansion_input.jsonl --output out\judge3905_p0_seed_registry\judge3905_p0_highrisk_expansion_result.json --server-type vllm --parallel 36 --reuse-shards-only --no-dashboard --slang-db on --vlm on --ocr on --require-vlm-ocr-for-images --llm-endpoint http://10.20.0.101:8000 --llm-model bg-digitalservices/Gemma-4-E4B-it-NVFP4
```

결과:

- run id: `20260615_012056_067394`
- input/completed/flushed/pending/failed: `36/36/36/0/0`
- effective parallel: `36`
- MCP health: `8/8`
- image post count: `36`
- VLM/OCR semantic gate: `READY`
- runtime contract audit: `GO`

### High-risk compare

실행 명령:

```powershell
.\.venv312\Scripts\python.exe tools\build_judge_seed_registry.py compare --registry out\judge3905_p0_seed_registry\judge3905_p0_seed_registry.json --canary-result out\judge3905_p0_seed_registry\judge3905_p0_highrisk_expansion_result.json --manifest out\judge3905_p0_seed_registry\judge3905_p0_highrisk_expansion_manifest.json --output-json out\judge3905_p0_seed_registry\judge3905_p0_highrisk_expansion_compare.json --output-md out\judge3905_p0_seed_registry\judge3905_p0_highrisk_expansion_compare_ko.md
```

Compare 결과:

- expected/result/compared: `36/36/36`
- missing result: `0`
- candidate ledger present: `36/36`
- official title changed: `23`
- official title lint after: `1`
- identity consistency lint after: `14`
- after shadow labels:
  - `safe_resolved=7`
  - `promotion_blocked=12`
  - `hold_unresolved=3`
  - `output_consistency_lint=8`
  - `identity_consistency_lint=5`
  - `official_title_lint=1`

Gate:

- run integrity: `GO`
- semantic quality: `REVIEW-LOCKED`
- reason: targeted high-risk seed evidence only; random baseline and remaining lint review are still required.

### Slang DB low-information alias guard

high-risk run에서 `novel`, `dc`, `그리고` 같은 저정보 표면이 slang DB observation으로 flush되는 새 문제가 발견됐다.

관측 로그:

- `novel -> novel.munpia.com (slang)`
- `dc -> 내가 주인공인 줄 알았다 (slang)`
- `그리고 -> 괴담에 휘말린 피해자가 되었다 (slang)`

조치:

- `src/llm_batch/slang_db.py`의 generic/low-information alias guard에 URL/domain/platform token과 Korean connective surface를 추가했다.
- domain/URL label은 `_looks_domain_or_url_label()`로 generic term/title label 처리한다.
- `tests/test_slang_db_low_information_alias.py`를 추가했다.

post-patch focused canary:

```powershell
.\.venv312\Scripts\python.exe expert_main.py --input out\judge3905_p0_seed_registry\judge3905_p0_slang_guard_focus_input.jsonl --output out\judge3905_p0_seed_registry\judge3905_p0_slang_guard_focus_result.json --server-type vllm --parallel 3 --reuse-shards-only --no-dashboard --slang-db on --vlm on --ocr on --require-vlm-ocr-for-images --llm-endpoint http://10.20.0.101:8000 --llm-model bg-digitalservices/Gemma-4-E4B-it-NVFP4
```

결과:

- run id: `20260615_021205_542965`
- input/completed/flushed/pending/failed: `3/3/3/0/0`
- image post count: `3`
- VLM/OCR semantic gate: `READY`
- slang DB finalize flush: `buffered_observations=0`, titles `0`, previews `[-]`
- runtime contract audit: `GO`
- focused compare: expected/result/compared `3/3/3`, after labels `promotion_blocked=1`, `identity_consistency_lint=1`, `official_title_lint=1`

### Remaining blockers before domain-guard follow-up

- `11663514`는 focused canary에서도 `official_title=novel.munpia.com`으로 남아 `official_title_lint`가 유지됐다.
- 따라서 slang DB 오염은 막았지만, URL/domain official title promotion guard는 아직 후속 과제다.
- random baseline은 아직 실행하지 않았다.
- 전체 gate는 계속 semantic quality `REVIEW-LOCKED`다.

## 2026-06-15 URL/domain official title promotion guard and random50 p32 baseline

section 위의 remaining blocker를 후속 패치와 재실행으로 닫았다.

### Pipeline patch

- `src/llm_batch/candidate_audit.py`에 URL/domain/platform/generic label demotion guard를 추가했다.
- blocked title은 `blocked_official_title`, `blocked_official_title_url`, `promotion_blocked_reasons`에 남기고, 실제 작품 후보는 `candidate_ledger`에 보존한다.
- `expert_main.py`는 candidate audit field 생성 전에 promotion guard를 적용한다.
- 회귀 테스트는 `tests/test_candidate_audit.py`에 추가했다.

### Domain/lint focused canary

실행 명령:

```powershell
.\.venv312\Scripts\python.exe expert_main.py --input out\judge3905_p0_seed_registry\judge3905_p0_domain_guard_lint_focus_input.jsonl --output out\judge3905_p0_seed_registry\judge3905_p0_domain_guard_lint_focus_result.json --server-type vllm --parallel 15 --reuse-shards-only --no-dashboard --slang-db on --vlm on --ocr on --require-vlm-ocr-for-images --llm-endpoint http://10.20.0.101:8000 --llm-model bg-digitalservices/Gemma-4-E4B-it-NVFP4
```

결과:

- run id: `20260615_105502_850042`
- input/completed/flushed/pending/failed: `15/15/15/0/0`
- `image_post_count=15`
- VLM/OCR semantic gate: `READY`
- runtime contract audit: `GO`

Compare:

- expected/result/compared: `15/15/15`
- missing result: `0`
- after labels: `output_consistency_lint=8`, `promotion_blocked=4`, `identity_consistency_lint=3`
- official title lint after: `0`
- `11663514`: after `official_title=null`, `promotion_blocked`, candidate titles preserve `전생했더니 슬라임이었던 건에 대하여`.

Remaining focused rows:

- `identity_consistency_lint`: `11634549`, `11657028`, `11673108`
- `output_consistency_lint`: `11602334`, `11602367`, `11605540`, `11628058`, `11629688`, `11632915`, `11636134`, `11650591`

### Random50 p32 baseline

첫 random50 실행은 completed `50/50`이었지만 `--parallel 36` 요청 대비 healthy endpoint filter가 `32/36`이라 runtime audit이 `NO-GO`였다. 같은 input을 `--parallel 32`로 재실행했다.

실행 명령:

```powershell
.\.venv312\Scripts\python.exe expert_main.py --input out\judge3905_p0_seed_registry\judge3905_p0_random50_baseline_input.jsonl --output out\judge3905_p0_seed_registry\judge3905_p0_random50_baseline_p32_result.json --server-type vllm --parallel 32 --reuse-shards-only --no-dashboard --slang-db on --vlm on --ocr on --require-vlm-ocr-for-images --llm-endpoint http://10.20.0.101:8000 --llm-model bg-digitalservices/Gemma-4-E4B-it-NVFP4
```

결과:

- run id: `20260615_120734_501402`
- input/completed/flushed/pending/failed: `50/50/50/0/0`
- requested/effective parallel: `32/32`
- MCP health: `32/32`
- `image_post_count=30`
- VLM/OCR semantic gate: `READY`
- runtime contract audit: `GO`
- quality summary: `out/judge3905_p0_seed_registry/judge3905_p0_random50_baseline_p32_quality_summary.json`
- candidate ledger status: `safe_resolved=10`, `review_only=2`, `hold_unresolved=31`, `promotion_blocked=7`
- official/identity/output lint counts: `{}`
- domain/URL official title rows: `[]`

Gate:

- focused canary run integrity: `GO`
- random50 p32 run integrity: `GO`
- semantic quality: `REVIEW-LOCKED`
- reason: remaining focused lint rows and small random baseline limits; no full scan approval.

## 2026-06-15 remaining-lint focused closure

domain/lint focused compare의 remaining target 11건을 별도 input으로 묶어 재검토했다.

### Patch

- judge precision seed에서 official title이 남으면 URL/platform 근거가 있더라도 `promotion_blocked`로 내린다. 이는 `_judge_seed`가 있는 focused regression run에만 적용되는 보수 guard다.
- `title_noisy_ocr` safe 판정은 official search title match가 있어야 한다. `primary_work`의 self-claimed title/url만으로는 safe 처리하지 않는다.

### expert_main remaining-lint focused run

실행 명령:

```powershell
.\.venv312\Scripts\python.exe expert_main.py --input out\judge3905_p0_seed_registry\judge3905_p0_remaining_lint_focus_input.jsonl --output out\judge3905_p0_seed_registry\judge3905_p0_remaining_lint_focus_result.json --server-type vllm --parallel 15 --reuse-shards-only --no-dashboard --slang-db on --vlm on --ocr on --require-vlm-ocr-for-images --llm-endpoint http://10.20.0.101:8000 --llm-model bg-digitalservices/Gemma-4-E4B-it-NVFP4
```

결과:

- run id: `20260615_165906_220298`
- input/completed/flushed/pending/failed: `15/14/8/6/0`
- image post count: `15`
- VLM/OCR semantic gate: `READY`
- runtime contract audit: `NO-GO`
- incomplete row: control `11639284`
- target 11 rows: all present in checkpoint/recovered subset

### Recovery / compare

- recovery summary: `out/judge3905_p0_seed_registry/judge3905_p0_remaining_lint_focus_recovery_summary.json`
- final postprocessed result: `out/judge3905_p0_seed_registry/judge3905_p0_remaining_lint_focus_result_recovered_14_postprocessed.json`
- compare: `out/judge3905_p0_seed_registry/judge3905_p0_remaining_lint_focus_compare.json`
- quality summary: `out/judge3905_p0_seed_registry/judge3905_p0_remaining_lint_focus_quality_summary.json`

Target 11 status:

- `promotion_blocked`: `11634549`, `11657028`, `11673108`
- `safe_resolved`: `11605540`, `11628058`, `11629688`
- `hold_unresolved`: `11602334`
- `output_consistency_lint`: `11602367`, `11632915`, `11636134`, `11650591`

Gate:

- original run integrity: `NO-GO`
- recovered subset: usable for target semantic comparison only
- semantic quality: `REVIEW-LOCKED`
- full scan approval: `false`

## 2026-06-15 remaining output-lint closure and control-only cleanup

remaining-lint focused closure에서 남은 output lint 4건과 미완료 control 1건을 다시 좁혀 처리했다.

### Patch

- `src/llm_batch/candidate_audit.py`에 `apply_judge_seed_title_hygiene_guard()`를 추가했다.
- guard 조건은 `title_noisy_ocr` seed + current official title URL 존재 + image explicit work title + official/platform search title이 같은 URL에서 일치하는 경우로 제한한다.
- `expert_main.py`는 precision guard 뒤, audit field 생성 전에 이 guard를 실행한다.
- `tests/test_candidate_audit.py`는 `11636134`형 image/search same-URL title correction 회귀를 추가했다.

### Control-only expert_main rerun

실행 명령:

```powershell
.\.venv312\Scripts\python.exe expert_main.py --input out\judge3905_p0_seed_registry\judge3905_p0_remaining_control_11639284_input.jsonl --output out\judge3905_p0_seed_registry\judge3905_p0_remaining_control_11639284_result.json --server-type vllm --parallel 1 --reuse-shards-only --no-dashboard --slang-db on --vlm on --ocr on --require-vlm-ocr-for-images --llm-endpoint http://10.20.0.101:8000 --llm-model bg-digitalservices/Gemma-4-E4B-it-NVFP4
```

결과:

- run id: `20260615_194903_574111`
- input/completed/flushed/pending/failed: `1/1/1/0/0`
- effective parallel: `1`
- image post count: `1`
- VLM/OCR semantic gate: `READY`
- runtime contract audit: `GO`

### Combined15 compare

- combined postprocessed result: `out/judge3905_p0_seed_registry/judge3905_p0_remaining_lint_focus_result_combined15_postprocessed.json`
- compare: `out/judge3905_p0_seed_registry/judge3905_p0_remaining_output_lint_closure_compare.json`
- summary: `out/judge3905_p0_seed_registry/judge3905_p0_remaining_output_lint_closure_summary.json`
- manual evidence packets: `out/judge3905_p0_seed_registry/judge3905_p0_remaining_output_lint_manual_evidence_packets.json`
- expected/result/compared: `15/15/15`
- missing result: `0`
- after labels: `safe_resolved=4`, `promotion_blocked=7`, `hold_unresolved=1`, `output_consistency_lint=3`

Target closure:

- `11636134`: `safe_resolved`, title corrected to `불패의 명장으로 착각당했다`.
- `11639284`: `promotion_blocked`, control runtime gap closed.
- `11602367`, `11632915`, `11650591`: `output_consistency_lint`, manual semantic/OCR evidence review remains.

Gate:

- control-only runtime: `GO`
- combined evidence completeness: `GO`
- original 15-row run integrity: `NO-GO`
- semantic quality: `REVIEW-LOCKED`
- full scan approval: `false`
