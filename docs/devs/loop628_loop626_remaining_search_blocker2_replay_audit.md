# loop628_loop626_remaining_search_blocker2_replay 검색 복구 재실행 감사

## 요약

- gate: `GO`
- expected_replay_rows: `2`
- completed_rows: `2`
- status_counts: `{'SEARCH_DEGRADED_RECOVERED': 1, 'ok': 1}`
- total_degraded: `9`
- total_degraded_zero: `0`
- total_degraded_recovered: `9`
- total_unrecovered_degraded: `0`
- hard_blocker_row_count: `0`
- recovered_observation_row_count: `1`
- missing_search_health_row_count: `0`
- hard_missing_search_health_row_count: `0`
- search_not_required_observation_row_count: `0`
- blockers: `[]`
- recovered_subset: run_id `None`, integrity `None`, large_run_complete `None`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`

## 해석

- 동일 deferred replay가 모두 완료됐고 hard search blocker가 남지 않았다.
- `SEARCH_DEGRADED_RECOVERED` 또는 `status=ok`의 recovered-only degraded 카운터는 별도 관측으로 남기되 hard blocker로 세지 않는다.
- 이 감사 범위에서는 검색 복구 gate를 통과했으므로 full375 재실행 선행 차단을 해제할 수 있다.
- 다만 이 산출물은 full375 collateral GO나 full_scan approval이 아니다.

## 행 목록

- `11660258` status=`ok` degraded=`0` recovered=`0` unrecovered=`0` blocker=`None` missing_observation=`None` recovered_observation=`None` title=`괴담 호텔 탈출기`
- `11694026` status=`SEARCH_DEGRADED_RECOVERED` degraded=`9` recovered=`9` unrecovered=`0` blocker=`None` missing_observation=`None` recovered_observation=`search_degraded_recovered` title=`None`
