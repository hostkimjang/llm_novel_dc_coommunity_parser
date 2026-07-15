# Loop640 full375 live run health latest

> Continuation override: 이 문서는 `2026-07-10T02:49:59`의 historical live snapshot이다. 이후 manifest는 `75/68/7/0`, checkpoint completed `75`, result `68`, pending `7`, `large_run_complete=false`까지 전진했고 현재 관련 process/dashboard는 종료 상태다. 기존 Loop640 output 재실행은 금지하며, 별도 checkpoint 복구와 새 residual output을 사용한다. 실행 prompt는 `docs/devs/LOOP640_RECOVERY_GPT56_CONTINUOUS_GOAL_PROMPT.md`다.

이 문서는 Loop640 background full375 run `20260710_005902_590310`의 당시 live health snapshot이다. 완료 보고서가 아니라 진행 중 감사 기록이다.

## 요약

- generated_at: `2026-07-10T02:49:59`
- run_integrity_gate: `IN_PROGRESS`
- flush classification: `incomplete_run_in_progress`
- manifest counts: completed/flushed/pending/failed `66/66/0/0`
- input_post_count: `375`
- result rows: `66`
- checkpoint completed rows: `66`
- pending snapshot rows: `0`
- next_save_idx: `67`
- frontier status: `in_flight_or_missing`
- frontier reason: `frontier_missing_from_checkpoint_and_pending`
- frontier post: `11714885 / 자식들로 몸 갈아타는 부모 ㅁㅊ`
- frontier worker trace: `in_progress_in_worker_log / W12 / event_count=8 / observed_elapsed_seconds=702.444`
- cleared frontier: previous `11706828` completed enough to move ordered flushed prefix `62 -> 66`
- dashboard liveness: `batch_running=true`, done `66/375`, progress `17.6%`, current post `11694019`, current expert `verifier`, current expert status `running`, parallel `16`, `llm_suspended=false`
- search evidence: `GO`
- row search health: ok `62`, `SEARCH_DEGRADED_RECOVERED 3`, unrecovered degraded `0`
- publication contract: `GO / row 66 / violation 0`
- worker log progress: post start `82`, post complete `66`, title anchor probes `85`, headless meta lines `116`
- reason errors: `0`
- slang_db bad remaining: `0`
- baseline mode: `adjudicated_rebaseline`
- completion metric: `adjusted_drift_count`
- raw vs 2026-06-26: historical diagnostic only

## 해석

현재 artifact 정합성은 깨진 상태가 아니라 full375 입력 `375` 중 앞선 `66`행만 완료된 진행 중 상태다. checkpoint, result JSON, pending snapshot은 manifest count와 일치하고 ordered flush gap은 이 snapshot에서는 해소됐다. 그러나 전체 입력이 아직 `375/375/0/0`이 아니므로 이 snapshot은 completed source가 아니며 full375 collateral approval 근거로 쓰지 않는다.

이전 frontier `11706828`은 해소되어 ordered flushed prefix가 `62 -> 66`으로 이동했다. 새 frontier `11714885`는 아직 completed source가 아니지만, W12 worker log에서 진행 중 trace가 관측된다. Dashboard/main log도 살아 있어 worker death가 아니라 live long-tail postprocess 진행으로 본다. 현재 prefix가 `66`까지 깨끗해도 전체 `375`행 완료 전에는 completed source approval 근거로 쓰지 않는다.

프로세스 점검에서는 `.venv312` runner가 `C:\Python312` child runner를 띄우고 그 자식이 attach/expert process를 띄운 wrapper chain으로 확인됐다. 같은 output path에 대한 별도 독립 duplicate dispatch 증거는 없으므로 현재 조치는 신규 dispatch가 아니라 background 감시다.

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
