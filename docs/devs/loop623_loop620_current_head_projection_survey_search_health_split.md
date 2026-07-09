# loop623_loop620_current_head_projection_survey_search_health_split raw regression survey/search-health 3분

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- raw regression rows: `141`

## 3분 결과

- expected_fp_removal 회계 면제: `47`
- intended recovery blind-judge 대상: `25` (recall_miss `17`, wrong_work `8`)
- search degraded/recovered overlay 보류: `11`
- ok-search & non-FP 후보: `81` (blind-judge 의도 복구 제외 후 진짜 triage `57`)
- search health missing: `4`

## 검색 선결

- `loop623_loop620_current_head_projection_collateral_compare` health audit는 degraded query `62`, unrecovered degraded `1`를 기록했다.
- `SEARCH_DEGRADED` 또는 `SEARCH_DEGRADED_RECOVERED` 행의 collateral 변화는 회귀 판정 근거로 쓰지 않는다.
- full375 재실행 전 검색 인프라 복구와 degraded/recovered 행 재실행이 선행이다.

## Post IDs

- expected_fp_removal: 11660254, 11660262, 11665124, 11666699, 11668278, 11668300, 11668305, 11668307, 11669908, 11669913, 11673096, 11673102, 11677915, 11679553, 11681172, 11681178, 11682749, 11685994, 11687661, 11692436, 11694035, 11694041, 11694044, 11695609, 11697239, 11697242, 11697249, 11697256, 11698859, 11698865, 11698871, 11698904, 11703640, 11703658, 11706867, 11708453, 11710020, 11710021, 11710047, 11711632, 11714885, 11714892, 11716475, 11716505, 11718057, 11718110, 11718114
- intended_recovery_blind_judge: 11658637, 11666700, 11668324, 11669928, 11671501, 11671514, 11671538, 11673086, 11676317, 11681177, 11694063, 11694067, 11695611, 11697234, 11700475, 11702084, 11703645, 11703674, 11706842, 11706852, 11708466, 11708478, 11710036, 11710044, 11718097
- true_triage_ok_search_nonfp: 11660229, 11660264, 11660268, 11660271, 11661857, 11661863, 11663514, 11663521, 11663535, 11663554, 11663557, 11665099, 11665110, 11666725, 11666741, 11668325, 11669907, 11669926, 11669929, 11671512, 11673077, 11673080, 11676314, 11677924, 11677926, 11679537, 11679547, 11681152, 11682767, 11682768, 11682775, 11682780, 11682791, 11682800, 11684370, 11687618, 11687627, 11689248, 11690855, 11694047, 11694049, 11694068, 11695599, 11697231, 11698880, 11702060, 11702090, 11702094, 11703622, 11705269, 11706871, 11708443, 11710045, 11710052, 11714887, 11714903, 11718099

## Gate 해석

`loop623_loop620_current_head_projection_collateral_compare` raw regression은 일괄 P0 triage 대상이 아니다. 먼저 survey FP 제거는 정당 제거로 회계 면제하고, 의도 복구 row는 제목 정답성 blind judge만 통과시키며, search health가 정상인 non-FP 잔여만 실제 triage 대상으로 다룬다.
