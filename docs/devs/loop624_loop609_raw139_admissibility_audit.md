# loop624_loop609_raw139_admissibility_audit collateral 판정 적격성 감사

## 결론

- gate: `NO-GO`
- collateral regression evidence: `NOT_ADMISSIBLE`
- full375 rerun gate: `BLOCKED_UNTIL_SEARCH_RECOVERY_FOR_HELD_ROWS`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`

## 3분 회계

- raw regression rows: `139`
- expected_fp_removal 회계 면제: `42`
- intended recovery blind judge: `24` (recall_miss `15`, wrong_work `9`)
- search degraded/recovered 판정 보류: `109`
- search health missing: `9`
- ok-search & non-FP 후보: `15` (의도 복구 제외 후 실제 triage `10`)

## 검색 선결

- degraded query `1801`, unrecovered degraded `234`.
- search health가 ok가 아닌 run의 collateral은 회귀 판정 근거로 쓰지 않는다.
- search degraded/recovered 행은 검색 복구 후 해당 행만 재실행해 재판정한다.
- full375 재실행은 검색 인프라 복구와 보류 행 재실행 뒤에만 연다.

## 실제 triage post_id

- true_triage_ok_search_nonfp: 11658626, 11660264, 11665099, 11671512, 11677926, 11681152, 11682761, 11682791, 11685987, 11694068

## 검증

- issue_count: `0`

## 차단 사유

- blocker_count: `1`
- `search_health_not_admissible` gate=`REVIEW` degraded_query=`1801` unrecovered=`234` overlay=`109` missing=`9`
