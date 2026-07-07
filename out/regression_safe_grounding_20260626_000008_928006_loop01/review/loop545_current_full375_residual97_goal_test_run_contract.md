# Goal/Test 런 계약 감사

## 요약

- runtime_contract: `GO`
- semantic_approval: `not_evaluated_by_runtime_contract_audit`
- manifest: `out\regression_safe_grounding_20260626_000008_928006_loop01\canary\loop545_current_full375_residual97_runtime_replay_result_manifest.json`
- logs: `logs\expert_run_20260707_185644_707690.log`
- auto_discovered_logs: `False`
- log_evidence_present: `True`

## 관측값

- run_id: `20260707_185644_707690`
- llm_model: `bg-digitalservices/Gemma-4-26B-A4B-it-NVFP4`
- llm_endpoint: `http://10.20.0.101:8000/`
- input_post_count: `49`
- requested_parallel_raw: `16`
- requested_parallel: `16`
- effective_parallel: `16`
- parallel_policy: `effective_parallel=min(min(requested_parallel_raw,model_parallel_max),input_post_count)`
- model_parallel_max: `36`
- model_parallel_cap_applied: `False`
- completed/flushed/pending/failed: `49/49/0/0`
- image_post_count: `32`
- VLM/OCR ready: `vlm=True`, `ocr=True`, `ready=True`
- shard lifecycle: `auto_up=False`, `auto_recreate=False`, `local_management=False`, `status_audit=False`
- small_run_lifecycle_blocked: `False`
- healthy_endpoint_filter: `False`, after_filter=`16`
- health: `include_search=False`, `light_mode=True`, `required_ok=16`, `checked=16`, `ok=16`, `failure=0`, `batch=12`, `stopped_after_required=False`

## 로그 금지 패턴

- counts: `{}`

## 이슈

- 없음


## 판정

이 도구는 `expert_main.py` 소규모 goal/test run의 런타임 계약만 감사한다. `GO`가 나와도 자연어 판정 품질 승인으로 쓰지 않는다.
이미지 row가 있으면 VLM/OCR ready 또는 Browser visual evidence가 별도 semantic review에 필요하다.
