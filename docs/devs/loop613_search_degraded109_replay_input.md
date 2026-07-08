# loop613_search_degraded109_replay search recovery replay input

## 요약

- gate: `GO`
- runtime_input_rows: `109`
- missing_post_ids: `[]`
- skipped_rows: `0`
- loop609_search_status_counts: `{'SEARCH_DEGRADED': 53, 'SEARCH_DEGRADED_RECOVERED': 56}`
- primary_action_counts: `{'blind_judge_title_correctness': 19, 'expected_fp_removal_exempt': 31, 'hold_for_search_recovery_rerun': 59}`
- survey_failure_class_counts: `{'None': 51, 'batch_context_bleed': 1, 'generic_phrase_substring': 8, 'homonym_cross_domain': 2, 'image_anchor_spurious': 8, 'other': 2, 'over_resolved_nonwork': 9, 'recall_miss': 13, 'wrong_work_among_aliases': 15}`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`

## 실행 계약

- requested_parallel: `16`
- dashboard_required: `True`
- forbidden_flags: `['--no-dashboard']`
- required_env: `{'MCP_HEALTH_INCLUDE_SEARCH': '1', 'MCP_HEALTH_LIGHT_MODE': '0', 'DASHBOARD_URL': 'http://127.0.0.1:8080', 'DASHBOARD_PORT': '8080', 'EXPERT_DASHBOARD_FORWARD': '1'}`
- 이 입력 생성은 approval이 아니다. 재실행 후 row-level search health가 `ok`인지 별도 감사해야 한다.
- full375 재실행은 이 보류 행 재실행과 검색 복구 판정 이후에만 연다.

## Post IDs

11657045, 11657047, 11658637, 11660241, 11660257, 11660262, 11660268, 11660271, 11660273, 11660277, 11661856, 11661863, 11661881, 11663511, 11663514, 11663521, 11663554, 11663557, 11665110, 11665121, 11665124, 11666699, 11666700, 11666713, 11666725, 11668278, 11668300, 11668324, 11668325, 11669907, 11669908, 11669913, 11669924, 11669926, 11669928, 11669929, 11669933, 11671500, 11671514, 11671538, 11673077, 11673096, 11676314, 11676317, 11677919, 11677957, 11679547, 11681177, 11681180, 11682749, 11682767, 11682768, 11685994, 11685995, 11687618, 11687661, 11692436, 11694019, 11694035, 11694041, 11694044, 11694049, 11694063, 11694065, 11695599, 11695639, 11697231, 11697239, 11697242, 11697249, 11698865, 11698870, 11698880, 11698904, 11698910, 11700483, 11702050, 11702081, 11702094, 11703631, 11703645, 11703658, 11703674, 11705230, 11705231, 11705251, 11705252, 11706844, 11706852, 11706867, 11706871, 11708432, 11708443, 11710020, 11710036, 11710037, 11710047, 11710049, 11714887, 11714892, 11714903, 11716464, 11716480, 11716505, 11718097, 11718098, 11718099, 11718110, 11718114
