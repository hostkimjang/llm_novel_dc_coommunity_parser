# Loop640 full375 running health snapshot

생성 시각: `2026-07-10T01:07:06`

## 요약

- Run ID: `20260710_005902_590310`
- Gate: `IN_PROGRESS / NOT_APPROVAL_RUNNING`
- Runtime counts: completed/flushed/pending/failed `3/1/2/0`
- Result rows: `1`
- Checkpoint rows: `3`
- Flush integrity: `IN_PROGRESS / ordered_flush_gap_in_progress`
- Search evidence: `GO`, manifest `mcp_health_include_search=true`, `mcp_health_light_mode=false`, `mcp_health_ok_count=16`
- Publication contract: partial 기준 `GO / violation 0 / row 1`
- Reason errors: `0`

## Frontier

- next_save_idx: `2`
- post_id: `11676314`
- title: `마도줍 완결이 빠를까`
- worker trace: `in_progress_in_worker_log`
- last observed event: W1 `Synthesizer 증거 기반 재해석 시작`
- observed elapsed: `462.254s`

이 ordered flush gap은 2번 행이 아직 완료되지 않아 3번/13번 완료분이 result JSON으로 flush되지 못한 상태다. 현재 감사 기준으로는 진행 중 상태이며 approval 또는 full375 completion이 아니다.

## Gate

완료 gate는 여전히 raw가 아니라 adjusted 기준이다. `375/375/0/0`, manifest search non-light, publication contract `GO`, adjusted drift `0`, full_scan path 검증 전까지 `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`를 유지한다.
