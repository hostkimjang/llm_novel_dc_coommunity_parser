# Loop640 Loop639 runtime 계약 수정 후 full375 재시도 계획

Loop638에서 판결 baseline 재동결은 이미 `APPLIED`다. 따라서 완료 gate는 2026-06-26 raw가 아니라 판결 baseline 대비 `adjusted_drift_count`다. Raw `105`는 historical diagnostic으로만 남긴다.

## Loop639 부분 실행 판정

- Run ID: `20260709_235040_236898`
- Manifest: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop639_full375_after_adjudicated_rebaseline_result_manifest.json`
- Partial health: `docs/devs/loop639_full375_after_adjudicated_rebaseline_partial_run_health.json`
- Counts: completed/flushed/pending/failed `40/24/16/0`
- Frontier: global idx `25`, post_id `11663514`, title `슬라임의 올바른 사용법`
- Flush integrity: `IN_PROGRESS / ordered_flush_gap_in_progress`
- Partial publication contract: `GO / violation 0 / row 24`
- Search contract: `NO-GO`, manifest `mcp_health_include_search=false`, `mcp_health_light_mode=true`

이 부분 실행은 full375 collateral 승인 근거가 아니다. 외부 query-level audit은 pre/post 모두 shard `16/16`, query probe `16/16`, degraded `0`이었지만 child manifest가 search 포함 non-light health를 남기지 않았으므로 collateral 회귀 판정에 쓰지 않는다.

## 수정한 실행 계약

- Runner 직접 실행 import 보강: `tools/run_independent_plan.py`가 script path invocation에서도 repo root를 `sys.path`에 넣는다.
- Plan/run env forwarding 보강: JSON의 `required_env` 또는 `env_overrides`를 child process에 주입한다.
- 필수 env:
  - `MCP_HEALTH_INCLUDE_SEARCH=1`
  - `MCP_HEALTH_LIGHT_MODE=0`
  - `MCP_HEALTH_REQUIRED_OK=16`
  - `MCP_HEALTH_PROBE_BATCH_SIZE=16`
- Runtime: `--parallel 16`, web dashboard ON, `--reuse-shards-only`, `--slang-db off`, VLM/OCR ON.

## 실행 명령

```powershell
.\.venv312\Scripts\python.exe tools\run_independent_plan.py `
  --plan docs\devs\loop640_full375_after_loop639_runtime_contract_fix_runtime_plan.json `
  --log-dir out\regression_safe_grounding_20260626_000008_928006_loop01\logs\loop640_full375_after_loop639_runtime_contract_fix `
  --dashboard-url http://127.0.0.1:8080
```

Plan 자체에 필수 env가 있으므로 별도 `--set-env` 없이도 child manifest에 `mcp_health_include_search=true`, `mcp_health_light_mode=false`가 남아야 한다. 임시 override가 필요하면 같은 값을 `--set-env`로 중복 지정해도 된다.

## Post-run gate

- Runtime counts: completed/flushed/pending/failed `375/375/0/0`
- Manifest search health: `mcp_health_include_search=true`, `mcp_health_light_mode=false`
- Query/search: pre/post shard audit `GO`, row-level hard blocker `0`
- Publication contract convergence: `GO / violation 0`
- Collateral compare: `--baseline-mode adjudicated_rebaseline`, `adjusted_drift_count=0`
- Always-on: golden18 + adjusted full375 runtime collateral `GO`
- Full_scan path: 정의와 검증 완료 전까지 `full_scan_approval=false`

## Gate

현재 gate는 `READY_RETRY_AFTER_CONTRACT_FIX`다. Loop639 partial은 `PARTIAL_NOT_APPROVAL_EVIDENCE`이고, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`를 유지한다.
