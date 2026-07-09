# Loop640 full375 live run health latest

이 문서는 Loop640 background full375 run `20260710_005902_590310`의 최신 live health snapshot이다. 완료 보고서가 아니라 진행 중 감사 기록이다.

## 요약

- generated_at: `2026-07-10T01:21:19`
- run_integrity_gate: `IN_PROGRESS`
- flush classification: `ordered_flush_gap_in_progress`
- manifest counts: completed/flushed/pending/failed `19/17/2/0`
- input_post_count: `375`
- result rows: `17`
- checkpoint completed rows: `19`
- pending snapshot rows: `2`
- next_save_idx: `18`
- frontier status: `in_flight_or_missing`
- frontier reason: `frontier_missing_from_checkpoint_and_pending`
- search evidence: `GO`
- row search health: ok `19`, degraded `0`, unrecovered degraded `0`
- publication contract: `GO / row 17 / violation 0`
- reason errors: `0`
- slang_db bad remaining: `0`

## 해석

현재 artifact 정합성은 깨진 상태가 아니라 ordered flush가 앞선 idx `18`을 기다리는 진행 중 상태다. 이전 frontier `4`는 완료되어 result JSON이 `3`행에서 `17`행까지 flush됐지만, 아직 input `375` 중 일부 초반 index가 처리 중이다. checkpoint와 pending snapshot은 manifest count와 일치하지만, result JSON은 ordered flushed prefix `17`행만 담고 있다. 따라서 이 snapshot은 completed source가 아니며 full375 collateral approval 근거로 쓰지 않는다.

Search evidence와 publication contract는 현재 관측된 completed/flushed subset 기준으로는 `GO`다. 그러나 full375 완료 gate는 completed/flushed/pending/failed `375/375/0/0`, manifest search non-light, publication contract `GO`, adjusted drift `0`, full_scan path가 모두 닫힌 뒤에만 열린다.

`semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 산출물

- live audit JSON: `docs/devs/loop640_full375_live_run_health_latest.json`
- run manifest: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop640_full375_after_loop639_runtime_contract_fix_result_manifest.json`
- result JSON: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop640_full375_after_loop639_runtime_contract_fix_result.json`
- checkpoint JSONL: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop640_full375_after_loop639_runtime_contract_fix_result_checkpoint.jsonl`
- pending snapshot: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop640_full375_after_loop639_runtime_contract_fix_result_pending_snapshot.json`
- dashboard: `http://127.0.0.1:8080`
