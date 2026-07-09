# Loop639 adjudicated re-baseline 이후 full375 runtime 계획

Loop638에서 `true triage`와 intended recovery 계열 판결이 전 행 닫혔고, 59행 adjudication ledger를 바탕으로 `loop638_adjudicated_rebaseline_result.json`을 새 baseline으로 재동결했다. 따라서 다음 collateral은 2026-06-26 bootstrap raw 변화가 아니라 판결 baseline 대비 `adjusted_drift_count`를 잰다.

## 현재 상태

- Gate: `READY_NOT_RUN`
- Re-baseline: `APPLIED`
- Baseline rows: `375`
- Adjudication ledger rows: `59`
- Adjusted drift at static compare: `0`
- Historical raw vs 2026-06-26: `105`, diagnostic only
- Always-on: `NO-GO / collateral_runtime_counts_missing`
- `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`

## Preflight 확인

- Full375 input: `out/regression_safe_grounding_20260626_000008_928006_loop01/panel/regression_panel_input.jsonl`, rows `375`
- Golden set: `out/regression_safe_grounding_20260626_000008_928006_loop01/golden/golden_set.jsonl`, rows `18`
- Adjudicated baseline: `out/regression_safe_grounding_20260626_000008_928006_loop01/baseline/loop638_adjudicated_rebaseline_result.json`, rows `375`
- Dashboard: `http://127.0.0.1:8080/api/health`, `ok=true`, `standalone=true`, pid `9320`
- LLM endpoint: `http://10.20.0.101:8000`, model `bg-digitalservices/Gemma-4-26B-A4B-it-NVFP4`, max model len `128000`

## 실행 명령

직접 실행:

```powershell
.\.venv312\Scripts\python.exe expert_main.py `
  out\regression_safe_grounding_20260626_000008_928006_loop01\panel\regression_panel_input.jsonl `
  --output out\regression_safe_grounding_20260626_000008_928006_loop01\canary\loop639_full375_after_adjudicated_rebaseline_result.json `
  --server-type vllm `
  --llm-endpoint http://10.20.0.101:8000 `
  --llm-model bg-digitalservices/Gemma-4-26B-A4B-it-NVFP4 `
  --reuse-shards-only `
  --slang-db off `
  --parallel 16 `
  --vlm on `
  --ocr on `
  --require-vlm-ocr-for-images
```

Dashboard attach를 보장하는 planned runner:

```powershell
.\.venv312\Scripts\python.exe tools\run_independent_plan.py `
  --plan docs\devs\loop639_full375_after_adjudicated_rebaseline_runtime_plan.json `
  --log-dir out\regression_safe_grounding_20260626_000008_928006_loop01\logs\loop639_full375_after_adjudicated_rebaseline `
  --dashboard-url http://127.0.0.1:8080
```

`--no-dashboard`는 넣지 않는다. 모든 test/runtime run은 `--parallel 16`, search 포함 non-light, VLM/OCR ON, `slang_db off`, `--reuse-shards-only`로 실행한다.

## 예상 소요

Loop629 full375 완료 기준 실제 소요는 `31080.8s`, 약 `8.6h`, 평균 `82.9s/post`였다. 그래서 이 회차에서는 장시간 foreground dispatch를 시작하지 않고 실행 계약과 post-run gate를 먼저 고정한다.

## Post-run gate

- Runtime counts: completed/flushed/pending/failed `375/375/0/0`
- Dashboard: manifest progress attached. 단 dashboard는 진행 관측 도구이지 approval 근거가 아니다.
- Query/search: pre/post shard audit `GO`, row-level search hard blocker `0`
- Row search degraded/recovered가 남으면 collateral 회귀 판정 보류 후 해당 행만 재실행한다.
- Publication contract convergence: `GO / violation 0`
- Collateral compare: `--baseline-mode adjudicated_rebaseline`, `adjusted_drift_count=0`
- Always-on: golden18 + adjusted full375 runtime collateral `GO`
- Full_scan path: 정의와 검증 완료 전까지 `full_scan_approval=false`

## 산출물

- Plan JSON: `docs/devs/loop639_full375_after_adjudicated_rebaseline_runtime_plan.json`
- Expected result: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop639_full375_after_adjudicated_rebaseline_result.json`
- Expected manifest: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop639_full375_after_adjudicated_rebaseline_result_manifest.json`
- Run health: `docs/devs/loop639_full375_after_adjudicated_rebaseline_run_health.json/.md`
- Adjusted drift compare: `docs/devs/loop639_full375_after_adjudicated_rebaseline_adjusted_drift_compare.json/.md`
- Always-on: `docs/devs/loop639_always_on_after_full375_runtime.json/.md`
- Report: `docs/devs/loop_reports/LOOP_639_REPORT_20260709.md`

## 결론

재동결은 적용됐다. 이제 raw `105`는 6/26 대비 역사적 이동량 설명값이고, 완료/드리프트 게이트가 아니다. 다음 실행이 조용하면 `adjusted full375 collateral GO + full_scan path`를 완료 경로로 열고, 시끄러우면 raw 재소송이 아니라 판결 baseline 대비 drift 행만 triage한다.
