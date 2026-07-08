# loop617_search_health_missing3_replay_audit 검색 복구 재실행 감사

## 요약

- gate: `GO`
- expected_replay_rows: `3`
- completed_rows: `3`
- status_counts: `{'SEARCH_DEGRADED_RECOVERED': 1, 'ok': 2}`
- total_degraded: `3`
- total_degraded_zero: `0`
- total_degraded_recovered: `2`
- total_unrecovered_degraded: `0`
- hard_blocker_row_count: `0`
- recovered_observation_row_count: `1`
- missing_search_health_row_count: `0`
- blockers: `[]`
- recovered_subset: run_id `20260708_231154_843681`, integrity `clean_completed_run`, large_run_complete `True`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`

## 해석

- 동일 deferred replay가 모두 완료됐고 hard search blocker가 남지 않았다.
- `SEARCH_DEGRADED_RECOVERED` 또는 `status=ok`의 recovered-only degraded 카운터는 별도 관측으로 남기되 hard blocker로 세지 않는다.
- 이 감사 범위에서는 검색 복구 gate를 통과했으므로 full375 재실행 선행 차단을 해제할 수 있다.
- 다만 이 산출물은 full375 collateral GO나 full_scan approval이 아니다.

## 행 목록

- `11666713` status=`SEARCH_DEGRADED_RECOVERED` degraded=`3` recovered=`2` unrecovered=`0` blocker=`None` recovered_observation=`search_degraded_recovered` title=`21세기 무림세가 - 웹소설`
- `11698904` status=`ok` degraded=`0` recovered=`0` unrecovered=`0` blocker=`None` recovered_observation=`None` title=`None`
- `11700483` status=`ok` degraded=`0` recovered=`0` unrecovered=`0` blocker=`None` recovered_observation=`None` title=`None`
