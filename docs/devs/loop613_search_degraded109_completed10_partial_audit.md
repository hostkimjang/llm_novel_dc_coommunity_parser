# loop613_search_degraded109_completed10_partial_audit search recovery replay audit

## 요약

- gate: `NO-GO`
- expected_replay_rows: `109`
- completed_rows: `10`
- status_counts: `{'SEARCH_DEGRADED': 8, 'SEARCH_DEGRADED_RECOVERED': 2}`
- total_degraded: `104`
- total_unrecovered_degraded: `13`
- non_ok_row_count: `10`
- blockers: `['partial_replay_not_all_deferred_rows_completed', 'row_search_health_not_ok', 'unrecovered_degraded_queries_observed', 'recovered_subset_not_large_run_complete']`
- recovered_subset: run_id `20260708_181931_964377`, integrity `recoverable_pending_flush_gap`, large_run_complete `False`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`

## 해석

- 이 산출물은 검색 복구 증명이 아니다.
- 완료된 subset에서도 row-level search health가 `ok`가 아니므로 full375 재실행 차단은 유지한다.
- 검색 인프라 복구 후 동일 109행을 다시 실행해야 한다.

## Rows

- `11657047` status=`SEARCH_DEGRADED` degraded=`10` unrecovered=`1` title=`베지테리언 블러드`
- `11658637` status=`SEARCH_DEGRADED` degraded=`21` unrecovered=`3` title=`재벌집 막내아들`
- `11660241` status=`SEARCH_DEGRADED` degraded=`13` unrecovered=`1` title=`이세계 TRPG 게임마스터`
- `11660257` status=`SEARCH_DEGRADED` degraded=`10` unrecovered=`2` title=`None`
- `11660262` status=`SEARCH_DEGRADED_RECOVERED` degraded=`5` unrecovered=`0` title=`로판에 도파민을 풀었다`
- `11660268` status=`SEARCH_DEGRADED` degraded=`10` unrecovered=`1` title=`□□을 위한 세계는 없다`
- `11660271` status=`SEARCH_DEGRADED_RECOVERED` degraded=`8` unrecovered=`0` title=`None`
- `11660273` status=`SEARCH_DEGRADED` degraded=`5` unrecovered=`2` title=`None`
- `11661881` status=`SEARCH_DEGRADED` degraded=`14` unrecovered=`2` title=`여신이 나만 애호함`
- `11663511` status=`SEARCH_DEGRADED` degraded=`8` unrecovered=`1` title=`부캐 키우는 황태자 님`
