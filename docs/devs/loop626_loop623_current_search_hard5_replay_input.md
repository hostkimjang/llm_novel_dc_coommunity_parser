# loop626_loop623_current_search_hard5_replay search recovery replay input

## 요약

- gate: `GO`
- runtime_input_rows: `5`
- missing_post_ids: `[]`
- skipped_rows: `0`
- deferred_search_status_counts: `{'MISSING': 4, 'SEARCH_DEGRADED': 1}`
- deferred_primary_action_counts: `{'expected_fp_removal_exempt': 2, 'hold_for_search_health_missing': 2, 'hold_for_search_recovery_rerun': 1}`
- survey_failure_class_counts: `{'None': 3, 'wrong_work_among_aliases': 2}`
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

11660258, 11690841, 11694026, 11708453, 11710021
