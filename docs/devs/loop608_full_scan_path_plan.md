# Loop608 full_scan 실행 경로 계획

Loop608 기준 residual 회계는 ordinary residual `0`까지 내려왔지만, full375 runtime count가 아직 없어서 goal은 완료가 아니다. 이 문서는 다음 full_scan 성격의 runtime 검증을 어떤 조건에서 실행하고, 어떤 게이트로 판정할지 고정한다.

## 현재 상태

- residual accounting: processed/excluded `28`, ordinary residual `0`, validation issue `0`
- publication contract: `GO`, rows `375`, violation `0`
- release audit: contract rows `27`, pending `0`, release candidate `3`, no-release/hold `24`, runtime allowed `0`
- golden gate: `GO`, `18/18`
- full375 static collateral: shared `375/375`, raw regression `67`
- always-on gate: review+contract adjusted regression `0`, but `NO-GO`
- 남은 blocker: `collateral_runtime_counts_missing`
- `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`

## Dashboard 실행 계약

- 다음 test/runtime run은 반드시 `--parallel 16`으로 실행한다.
- 진행상황 확인을 위해 web dashboard를 붙인다: `http://127.0.0.1:8080`
- 현재 health: `ok=true`, `standalone=true`, `pid=9320`
- 최신 status는 이전 Loop564 runtime replay `30/30`, `parallel_count=16`, `batch_running=false`다.
- `--no-dashboard`는 사용하지 않는다.
- `tools/run_independent_plan.py` 경유 planned run은 dashboard forwarding과 manifest attach fallback을 사용한다.
- 이미 dashboard 없이 뜬 런은 증거로 쓰기 전에 `tools/attach_manifest_dashboard.py --manifest <manifest>`로 사후 부착한다.
- Dashboard는 진행상황 관측 도구이며 semantic/full_scan approval 근거가 아니다.

## 실행 명령 초안

```powershell
.\.venv312\Scripts\python.exe expert_main.py `
  out\regression_safe_grounding_20260626_000008_928006_loop01\panel\regression_panel_input.jsonl `
  --output out\regression_safe_grounding_20260626_000008_928006_loop01\canary\loop609_full375_after_loop608_search_nonlight_result.json `
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

이 명령에는 `--no-dashboard`를 넣지 않는다. planned run으로 감싸는 경우에도 runner가 dashboard를 기본 확인/시작하고 child run에 `DASHBOARD_URL`, `DASHBOARD_PORT`, `EXPERT_DASHBOARD_FORWARD=1`을 전달해야 한다.

## Preflight

- dashboard health `ok=true`
- requested parallel `16`
- search 포함, non-light 조건 확인
- MCP/search shard health 확인
- VLM/OCR ready 확인
- `slang_db`는 off 또는 read-only 유지
- full375 입력 row `375` 확인

## Post-run gate

- run health `GO`
- completed/flushed/pending/failed `375/375/0/0`
- dashboard manifest progress attached
- publication contract `GO / violation 0`
- full375 collateral compare 재실행
- always-on golden18 + full375 gate 재실행
- runtime counts complete
- 위 조건이 모두 충족되기 전에는 `full_scan_approval=false`를 유지한다.

## 산출물

- residual accounting: `docs/devs/loop608_after_remaining_native_hold_residual28_accounting.json`
- ordinary residual dispatch: `docs/devs/loop608_after_remaining_native_hold_ordinary_residual0_dispatch.json`
- publication audit: `docs/devs/loop608_remaining_native_hold_publication_contract_audit.json`
- collateral compare: `docs/devs/loop608_remaining_native_hold_full375_collateral_compare.json`
- always-on gate: `docs/devs/loop608_always_on_golden18_full375_remaining_native_hold_gate.json`
