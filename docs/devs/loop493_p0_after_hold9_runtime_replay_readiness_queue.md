# loop493_p0_after_hold9_runtime_replay_readiness_queue

## 요약

- source_batch: `loop491_p0_runtime_failure_batch`
- source_verdict: `loop492_p0_hold9_source_native_verdicts`
- Loop491 runtime REPROCESS rows: `14`
- Loop492 verdict rows: `9`
- ready_for_runtime_replay rows: `0`
- blocked_before_runtime_replay rows: `23`
- runtime lanes: `{'publish_contract_trace_repair_before_replay': 5, 'search_blind_or_recovered_preflight_before_replay': 9}`
- verdict lanes: `{'canonical_repair_before_runtime_replay': 3, 'hard_hold_policy_or_native_review': 2, 'variant_policy_before_regression_exclusion': 4}`
- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`

## Runtime replay gate

- status: `BLOCKED_BEFORE_REPAIR`
- reason: Loop491 warned that REPROCESS 14 would be a repeat unless shared-gate repair or search-blind tagging happens first.
- prepared input: `out/regression_safe_grounding_20260626_000008_928006_loop01/inputs/loop491_p0_reprocess14_runtime_replay_input.jsonl`
- stop condition: actionable queue 감소 + 동일 packet safe_resolved 단조 비감소

## Lanes

- `publish_contract_trace_repair_before_replay`: `5` rows / post_ids `[11677915, 11684372, 11694019, 11718099, 11682780]`
- `search_blind_or_recovered_preflight_before_replay`: `9` rows / post_ids `[11663521, 11665124, 11677926, 11698910, 11708447, 11710049, 11716475, 11718110, 11710020]`
- `canonical_repair_before_runtime_replay`: `3` rows / post_ids `[11663535, 11714887, 11718098]`
- `hard_hold_policy_or_native_review`: `2` rows / post_ids `[11692436, 11673077]`
- `variant_policy_before_regression_exclusion`: `4` rows / post_ids `[11673102, 11698870, 11705230, 11694068]`

## Approval boundary

- 이 readiness queue는 replay 승인이나 full375 GO가 아니다.
- `ready_for_runtime_replay_rows=0`이므로 prepared 14건 입력을 즉시 실행하지 않는다.
- 완료 기준은 계속 `full375 collateral GO + full_scan 경로 정의`다.
