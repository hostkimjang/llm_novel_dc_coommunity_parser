# Loop486 goal/test 런 계약 감사

## 요약

- runtime_contract: `REVIEW`
- semantic_approval: `not_evaluated_by_runtime_contract_audit`
- manifest: `out\regression_safe_grounding_20260626_000008_928006_loop01\canary\loop486_shared_gate_exact9_runtime_replay_result_manifest.json`
- log_evidence_present: `True`

## 관측값

- run_id: `20260706_035613_577781`
- input/completed/flushed/pending/failed: `9/9/9/0/0`
- effective_parallel: `9`
- VLM/OCR ready: `vlm=True`, `ocr=True`, `ready=True`
- health: `include_search=True`, `light_mode=False`, `ok/failure=2/0`
- shard lifecycle blocked: `True`

## 이슈

- `REVIEW` `small_run_health_include_search_true`: 소규모 goal/test 기본 계약은 Bridge readiness 중심이지만, 이번 실행은 search 포함 non-light 실증 목적이라 REVIEW로 남긴다.
- `REVIEW` `small_run_health_light_mode_false`: 소규모 기본 계약은 light health를 기대하지만, 이번 실행은 search degraded 복구 관찰을 위해 non-light로 실행했다.

## 판정

이 도구는 `expert_main.py` 소규모 goal/test 런타임 계약만 감사한다. 이번 Loop486은 사용자가 요구한 search 포함 non-light 조건을 따랐기 때문에 runtime contract는 `REVIEW`로 남긴다. 이는 expected-title 실패나 full375 collateral `NO-GO`를 덮지 않는다.
