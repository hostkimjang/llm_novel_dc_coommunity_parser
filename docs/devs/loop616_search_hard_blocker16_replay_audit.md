# loop616_search_hard_blocker16_replay_audit 검색 복구 재실행 감사

## 요약

- gate: `NO-GO`
- expected_replay_rows: `16`
- completed_rows: `16`
- status_counts: `{'MISSING': 3, 'SEARCH_DEGRADED_RECOVERED': 4, 'ok': 9}`
- total_degraded: `12`
- total_degraded_zero: `0`
- total_degraded_recovered: `8`
- total_unrecovered_degraded: `0`
- hard_blocker_row_count: `3`
- recovered_observation_row_count: `4`
- missing_search_health_row_count: `3`
- blockers: `['row_search_hard_blocker_observed', 'search_health_missing_observed']`
- recovered_subset: run_id `20260708_223012_369319`, integrity `clean_completed_run`, large_run_complete `True`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`

## 해석

- 이 산출물은 검색 복구 증명이 아니다.
- 완료 범위, missing search_health, 또는 unrecovered degraded hard blocker가 남아 있으므로 full375 재실행 차단은 유지한다.
- 검색 인프라 복구 후 blocker 행 또는 동일 deferred 행을 다시 실행해야 한다.

## 행 목록

- `11657045` status=`ok` degraded=`0` recovered=`0` unrecovered=`0` blocker=`None` recovered_observation=`None` title=`None`
- `11658637` status=`ok` degraded=`0` recovered=`0` unrecovered=`0` blocker=`None` recovered_observation=`None` title=`재벌집 막내아들`
- `11660241` status=`ok` degraded=`0` recovered=`0` unrecovered=`0` blocker=`None` recovered_observation=`None` title=`이세계 TRPG 게임마스터`
- `11660257` status=`SEARCH_DEGRADED_RECOVERED` degraded=`6` recovered=`4` unrecovered=`0` blocker=`None` recovered_observation=`search_degraded_recovered` title=`암흑가 보스요? 제가요?`
- `11660268` status=`ok` degraded=`0` recovered=`0` unrecovered=`0` blocker=`None` recovered_observation=`None` title=`None`
- `11660273` status=`SEARCH_DEGRADED_RECOVERED` degraded=`2` recovered=`1` unrecovered=`0` blocker=`None` recovered_observation=`search_degraded_recovered` title=`None`
- `11661856` status=`ok` degraded=`0` recovered=`0` unrecovered=`0` blocker=`None` recovered_observation=`None` title=`None`
- `11661863` status=`SEARCH_DEGRADED_RECOVERED` degraded=`3` recovered=`2` unrecovered=`0` blocker=`None` recovered_observation=`search_degraded_recovered` title=`용의 신부로 바쳐지고 말았다`
- `11661881` status=`ok` degraded=`0` recovered=`0` unrecovered=`0` blocker=`None` recovered_observation=`None` title=`여신이 나만 애호함`
- `11663511` status=`ok` degraded=`0` recovered=`0` unrecovered=`0` blocker=`None` recovered_observation=`None` title=`None`
- `11666713` status=`MISSING` degraded=`0` recovered=`0` unrecovered=`0` blocker=`search_health_missing` recovered_observation=`None` title=`None`
- `11677957` status=`ok` degraded=`0` recovered=`0` unrecovered=`0` blocker=`None` recovered_observation=`None` title=`None`
- `11694019` status=`ok` degraded=`0` recovered=`0` unrecovered=`0` blocker=`None` recovered_observation=`None` title=`이세계에서 사이비로 살아남기`
- `11697231` status=`SEARCH_DEGRADED_RECOVERED` degraded=`1` recovered=`1` unrecovered=`0` blocker=`None` recovered_observation=`search_degraded_recovered` title=`아카데미 생존 갤러리`
- `11698904` status=`MISSING` degraded=`0` recovered=`0` unrecovered=`0` blocker=`search_health_missing` recovered_observation=`None` title=`None`
- `11700483` status=`MISSING` degraded=`0` recovered=`0` unrecovered=`0` blocker=`search_health_missing` recovered_observation=`None` title=`None`
