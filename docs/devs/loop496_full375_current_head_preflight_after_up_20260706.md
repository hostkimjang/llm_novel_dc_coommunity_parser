# expert_main 재런 runtime preflight

- generated_at: `2026-07-06T15:08:50`
- input: `out/regression_safe_grounding_20260626_000008_928006_loop01/panel/regression_panel_input.jsonl`
- manifest: ``

## Summary

- input_count: `375`
- raw_input_row_count: `375`
- unique_post_count: `375`
- input_count_source: `jsonl.unique_post_id_count`
- requested_parallel_max: `36`
- effective_parallel_expected: `36`
- expected_shards: `16`
- require_all_shards: `False`
- endpoint_count_expected: `16`
- endpoint_caps: `none`
- required_open_for_run: `16`
- LLM endpoint readiness: `GO`
- MCP effective shard readiness: `GO`
- MCP full shard readiness: `GO`
- rerun execution: `GO`
- reasons: `none`
- warnings: `none`

## LLM

- url: `http://10.20.0.101:8000/v1/models`
- ok: `True`
- expected_model: `bg-digitalservices/Gemma-4-26B-A4B-it-NVFP4`
- expected_model_found: `True`
- models: `bg-digitalservices/Gemma-4-26B-A4B-it-NVFP4`

## MCP TCP

- host: `127.0.0.1`
- base_port: `3333`
- expected_count: `16`
- open_count: `16`
- closed_count: `0`
- open_ports: `3333, 3334, 3335, 3336, 3337, 3338, 3339, 3340, 3341, 3342, 3343, 3344, 3345, 3346, 3347, 3348`

## Gate

이 preflight는 read-only 확인이다. Docker compose up/recreate/status audit을 실행하지 않는다.
기본 정책은 `--parallel 36`을 최대치로 보고, 입력 수 기준 effective worker에 필요한 shard가 열려 있으면 소규모 재런을 허용한다.
`expert_main.py`의 goal/targeted run 보호 cap도 반영하므로, 기본 조건에서는 입력 24건이어도 endpoint 풀은 `MCP_GOAL_RUN_AUTO_SHARD_LIMIT=8`까지 줄 수 있다.
전체 36-shard 준비 여부는 `mcp_full_shard_readiness`로 별도 기록한다.
`--require-all-shards`를 주면 36개 전체가 열려야만 `rerun_execution=GO`가 된다.
