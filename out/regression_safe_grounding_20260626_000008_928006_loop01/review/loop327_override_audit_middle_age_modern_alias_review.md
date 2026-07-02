# Loop327 OVERRIDE AUDIT blind judge repair

## 결론

`11668283 / 게임 마인드의 중세 현대인 좋았다...`는 최신 104k light run에서 `off_topic / context_only / official_title=null`로 떨어졌지만, source-native로 보면 작품 감상 행이다. 이 행은 `OVERRIDE AUDIT(LLM=False->final=True)` 확장 중 발견한 false negative로 보고, `중세 현대인` 계열 alias와 긍정 감상 cue를 shared curated alias gate에 추가했다.

## 근거

- 입력: 제목 `게임 마인드의 중세 현대인 좋았다...`, 본문 `오라 각성자의 참담한 희생을 기도하라`.
- 최신 light 결과: `out/expert_result_20260702_065632_479765_checkpoint.jsonl`, run `20260702_065642_030743`.
  - `is_relevant=false`, `discussion_type=off_topic`, `work_resolution=none`, `title_resolution_state=context_only`.
  - flags: `batch_memory_alias_rescue_blocked_nonwork_context`, `batch_memory_alias_rescue_blocked_semantic_seed`, `llm_only_sentence_candidate_pruned`.
  - health: `mcp_health_include_search=false`, `mcp_health_light_mode=true`, row search `SEARCH_DEGRADED`.
- 과거 독립 결과: `out/expert_result_20260423_170321_250907_checkpoint.jsonl`.
  - `official_title=게임 마인드의 중세 현대인`, URL `https://page.kakao.com/content/63760170?tab_type=about`, `work_resolution=resolved`.
- partial current canary: `logs/expert_run_20260703_014314_718737.log`.
  - startup health는 `include_search=true`, `light_mode=false`, `1/1 OK`.
  - Gatekeeper는 `work_discussion`, Discourse는 `novel_literature / review / title_body_consistency=true`.
  - semantic seed guard가 `중세 현대인`을 일반어로 drop했고, search 결과는 게임 사이트 노이즈로 degraded했다.
  - 이 canary는 패치 전 프로세스였고 결과 JSON 전 중단했으므로 approval 증거로 쓰지 않는다.

## 변경

- `src/llm_batch/experts/utils.py`
  - `중세현대인`, `중세 현대인`, `게임마인드중세`, `게임마인드 중세 현대인` -> `게임 마인드의 중세 현대인`.
- `src/llm_batch/agentic_pipeline.py`
  - curated alias gate의 작품 소비 cue에 `좋았/좋네/좋다/좋음/좋구나/좋아` 계열을 추가했다.
- `tests/test_known_title_abbreviation_safe_loss_contract.py`
  - positive: `게임 마인드의 중세 현대인 좋았다...` + 작품 장면 문구가 release된다.
  - negative: `중세 현대인` 단어만 있고 작품 소비 cue가 없으면 release되지 않는다.

## 검증

- `py_compile`: PASS
- `tests.test_known_title_abbreviation_safe_loss_contract -v`: PASS, 9 tests
- `tests.test_known_title_abbreviation_support tests.test_arbiter_curated_alias_guard tests.test_regression_safe_work_bridge_contract tests.test_known_title_abbreviation_safe_loss_contract -v`: PASS, 62 tests

## 게이트

- row contract: `GO_UNIT_REPAIR`
- current patch runtime replay: `NOT_RUN_AFTER_PATCH`
- Loop326 background: `IN_PROGRESS / NOT_APPROVAL`
- search recovery: `P0 / OPEN`
- promotion_blocked 해석: `search-blind conditional`
- semantic quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- overall goal: `ACTIVE / NOT_COMPLETE`
