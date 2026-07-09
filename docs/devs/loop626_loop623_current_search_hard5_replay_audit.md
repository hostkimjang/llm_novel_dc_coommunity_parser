# loop626_loop623_current_search_hard5_replay_audit 검색 복구 재실행 감사

## 요약

- gate: `NO-GO`
- expected_replay_rows: `5`
- completed_rows: `5`
- status_counts: `{'MISSING': 1, 'SEARCH_DEGRADED': 2, 'SEARCH_DEGRADED_RECOVERED': 1, 'ok': 1}`
- total_degraded: `26`
- total_degraded_zero: `2`
- total_degraded_recovered: `22`
- total_unrecovered_degraded: `2`
- hard_blocker_row_count: `3`
- recovered_observation_row_count: `2`
- missing_search_health_row_count: `1`
- blockers: `['row_search_hard_blocker_observed', 'search_health_missing_observed', 'unrecovered_degraded_queries_observed']`
- recovered_subset: run_id `20260709_111842_982379`, integrity `clean_completed_source`, large_run_complete `True`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`

## 해석

- 이 산출물은 검색 복구 증명이 아니다.
- 완료 범위, missing search_health, 또는 unrecovered degraded hard blocker가 남아 있으므로 full375 재실행 차단은 유지한다.
- 검색 인프라 복구 후 blocker 행 또는 동일 deferred 행을 다시 실행해야 한다.

## 행 목록

- `11660258` status=`SEARCH_DEGRADED` degraded=`4` recovered=`3` unrecovered=`1` blocker=`search_degraded` recovered_observation=`None` title=`괴담 호텔 탈출기`
- `11690841` status=`ok` degraded=`1` recovered=`0` unrecovered=`0` blocker=`None` recovered_observation=`ok_with_recovered_degradation_counter` title=`None`
- `11694026` status=`SEARCH_DEGRADED` degraded=`18` recovered=`16` unrecovered=`1` blocker=`search_degraded` recovered_observation=`None` title=`None`
- `11708453` status=`SEARCH_DEGRADED_RECOVERED` degraded=`3` recovered=`3` unrecovered=`0` blocker=`None` recovered_observation=`search_degraded_recovered` title=`감옥학원에서 나만 힐링할거다`
- `11710021` status=`MISSING` degraded=`0` recovered=`0` unrecovered=`0` blocker=`search_health_missing` recovered_observation=`None` title=`None`
