# loop617_search_health_missing3_replay 검색 blocker 재실행 입력

## 요약

- gate: `GO`
- source_input_rows: `16`
- audit_blocker_rows: `3`
- runtime_input_rows: `3`
- missing_post_ids: `[]`
- blocker_reason_counts: `{'search_health_missing': 3}`
- loop615_search_status_counts: `{'MISSING': 3}`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`

## 실행 계약

- requested_parallel: `16`
- dashboard_required: `True`
- forbidden_flags: `['--no-dashboard']`
- required_env: `{'MCP_HEALTH_INCLUDE_SEARCH': '1', 'MCP_HEALTH_LIGHT_MODE': '0', 'DASHBOARD_URL': 'http://127.0.0.1:8080', 'DASHBOARD_PORT': '8080', 'EXPERT_DASHBOARD_FORWARD': '1'}`
- 이 입력 생성은 approval이 아니다. 재실행 후 row-level hard search blocker가 `0`인지 다시 감사한다.
- full375 재실행은 이 blocker replay가 조용해진 뒤에만 연다.

## Post ID 목록

11666713, 11698904, 11700483
