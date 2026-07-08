# loop612_loop609_raw139_survey_search_health_split raw139 survey/search-health 3분

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- raw regression rows: `139`

## 3분 결과

- expected_fp_removal 회계 면제: `42`
- intended recovery blind-judge 대상: `24` (recall_miss `15`, wrong_work `9`)
- search degraded/recovered overlay 보류: `109`
- ok-search & non-FP 후보: `15` (blind-judge 의도 복구 제외 후 진짜 triage `10`)
- search health missing: `9`

## 검색 선결

- Loop609 health audit는 degraded query `1801`, unrecovered degraded `234`를 기록했다.
- `SEARCH_DEGRADED` 또는 `SEARCH_DEGRADED_RECOVERED` 행의 collateral 변화는 회귀 판정 근거로 쓰지 않는다.
- full375 재실행 전 검색 인프라 복구와 degraded/recovered 행 재실행이 선행이다.

## Post IDs

- expected_fp_removal: 11660277, 11663521, 11665110, 11665124, 11666699, 11668278, 11668300, 11668305, 11669908, 11669913, 11673102, 11681172, 11681178, 11685994, 11687661, 11692436, 11694019, 11694035, 11694041, 11694063, 11695609, 11697239, 11697242, 11697249, 11697256, 11698859, 11698865, 11698871, 11698904, 11702094, 11703658, 11706867, 11710020, 11710021, 11710047, 11711632, 11714885, 11714892, 11714903, 11716505, 11718110, 11718114
- intended_recovery_blind_judge: 11658637, 11660262, 11666700, 11668324, 11669928, 11671501, 11671514, 11671538, 11676317, 11677957, 11681177, 11682749, 11694044, 11694067, 11695639, 11697234, 11703645, 11703674, 11705256, 11706842, 11706852, 11710036, 11710037, 11718097
- true_triage_ok_search_nonfp: 11658626, 11660264, 11665099, 11671512, 11677926, 11681152, 11682761, 11682791, 11685987, 11694068

## Gate 해석

Loop609 raw139는 일괄 P0 triage 대상이 아니다. 먼저 survey FP 제거는 정당 제거로 회계 면제하고, 의도 복구 row는 제목 정답성 blind judge만 통과시키며, search health가 정상인 non-FP 잔여만 실제 triage 대상으로 다룬다.
