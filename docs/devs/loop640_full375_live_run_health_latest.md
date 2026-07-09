# Loop640 full375 live run health latest

이 문서는 Loop640 background full375 run `20260710_005902_590310`의 최신 live health snapshot이다. 완료 보고서가 아니라 진행 중 감사 기록이다.

## 요약

- generated_at: `2026-07-10T01:41:36`
- run_integrity_gate: `IN_PROGRESS`
- flush classification: `ordered_flush_gap_in_progress`
- manifest counts: completed/flushed/pending/failed `33/24/9/0`
- input_post_count: `375`
- result rows: `24`
- checkpoint completed rows: `33`
- pending snapshot rows: `9`
- next_save_idx: `25`
- frontier status: `in_flight_or_missing`
- frontier reason: `frontier_missing_from_checkpoint_and_pending`
- frontier post: `11663514 / 슬라임의 올바른 사용법`
- frontier worker trace: `in_progress_in_worker_log / W8 / observed_elapsed_seconds=680.689`
- cleared frontier: previous `11714892` completed enough to move ordered flushed prefix `19 -> 24`
- search evidence: `GO`
- row search health: ok `32`, degraded `0`, unrecovered degraded `0`
- publication contract: `GO / row 24 / violation 0`
- reason errors: `0`
- slang_db bad remaining: `0`
- baseline mode: `adjudicated_rebaseline`
- completion metric: `adjusted_drift_count`
- raw vs 2026-06-26: historical diagnostic only

## 해석

현재 artifact 정합성은 깨진 상태가 아니라 ordered flush가 앞선 idx `25`를 기다리는 진행 중 상태다. checkpoint는 `33`행까지 완료를 확인했지만, result JSON은 ordered flushed prefix `24`행만 담고 있다. checkpoint와 pending snapshot은 manifest count와 일치한다. 따라서 이 snapshot은 completed source가 아니며 full375 collateral approval 근거로 쓰지 않는다.

이전 frontier `11714892`는 해소되어 ordered flushed prefix가 `19 -> 24`로 이동했다. 새 frontier `11663514`는 checkpoint와 pending snapshot 양쪽에는 아직 없지만, W8 worker log에서 VLM, verifier, synthesizer, arbiter start까지 관측됐다. 현재 증거는 worker death가 아니라 새 long-tail postprocess 진행이다. 단 ordered flush가 이 row를 기다리는 동안 뒤쪽 completed/pending row를 completed source approval 근거로 쓰지 않는다.

Search evidence와 publication contract는 현재 관측된 completed/flushed subset 기준으로는 `GO`다. 그러나 full375 완료 gate는 completed/flushed/pending/failed `375/375/0/0`, manifest search non-light, publication contract `GO`, adjusted drift `0`, full_scan path가 모두 닫힌 뒤에만 열린다.

Loop638 이후 re-baseline은 이미 `APPLIED`다. 따라서 Loop640 이후 collateral은 `loop638_adjudicated_rebaseline_result.json` 대비 `adjusted_drift_count`로 판단하고, 2026-06-26 bootstrap raw `105`는 historical diagnostic으로만 둔다. Raw가 0이 되지 않는다는 이유로 매 run raw row를 다시 재소송하지 않는다.

`semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 산출물

- live audit JSON: `docs/devs/loop640_full375_live_run_health_latest.json`
- run manifest: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop640_full375_after_loop639_runtime_contract_fix_result_manifest.json`
- result JSON: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop640_full375_after_loop639_runtime_contract_fix_result.json`
- checkpoint JSONL: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop640_full375_after_loop639_runtime_contract_fix_result_checkpoint.jsonl`
- pending snapshot: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop640_full375_after_loop639_runtime_contract_fix_result_pending_snapshot.json`
- dashboard: `http://127.0.0.1:8080`
