# Verification Results

감사 명령, 핵심 지표, 판정, 후속 액션을 누적한다.

## 2026-05-01 - VLM degenerate image crash investigation and guard

- 판정: RUNTIME-GO for unit/rework / SERVER CANARY REQUIRED
- 관련 run:
  - current: `20260501_010427_282685`
  - cross-run confirmation: `20260423_170321_250907`
- 결론:
  - "4000번째쯤"이라는 위치 증상은 loaded index `4049`의 동일 post `11589463` 재현이었다.
  - 최초 실패는 텍스트 gatekeeper가 아니라 VLM multimodal image request에서 발생했다.
  - 해당 이미지 URL은 `application/octet-stream`으로 응답하지만 JPEG signature를 갖고, 실제 dimensions가 `389x1`인 degenerate image였다.
- 핵심 로그:
  - current W9: `VLM chunk request: post_id=11589463 chunk=1/1, images=1, bytes=448` -> `500 Internal Server Error` -> `502 Bad Gateway`
  - old W4: `VLM chunk request: post_id=11589463 chunk=1/1, images=1, bytes=448` -> `500 Internal Server Error` -> `502 Bad Gateway`
- 실제 이미지 확인:

```text
status= 200
content_type= application/octet-stream
bytes= 448
sniffed_mime= image/jpeg
dimensions= (389, 1)
first16= ffd8ffe000104a464946000101000001
```

- 패치 후 실제 URL fetch guard 확인:

```text
{'error': 'image_geometry_too_small:389x1:min=8x8', ...}
```

- 구현:
  - `src/llm_batch/agentic_pipeline.py`
  - JPEG/PNG/GIF/WebP/BMP dimension sniffing 추가.
  - VLM fetch 단계에서 `image_geometry_invalid`, `image_geometry_too_small`, `image_aspect_ratio_extreme` limitation 처리.
  - dimension unknown은 기존 호환성을 위해 fail-open.
- 신규/관련 테스트:
  - `tests.test_agentic_pipeline_rework.CommentTitleRecoveryTest.test_vlm_detects_progressive_jpeg_dimensions`
  - `tests.test_agentic_pipeline_rework.CommentTitleRecoveryTest.test_vlm_fetch_skips_degenerate_image_geometry_without_vlm_call`
  - 기존 VLM fetch 회귀 3건 재확인.
- 문법 검증:

```powershell
.\.venv312\Scripts\python.exe -m py_compile src\llm_batch\agentic_pipeline.py tests\test_agentic_pipeline_rework.py
```

- 결과: 통과.
- targeted 검증:

```powershell
.\.venv312\Scripts\python.exe -m unittest tests.test_agentic_pipeline_rework.CommentTitleRecoveryTest.test_vlm_detects_progressive_jpeg_dimensions tests.test_agentic_pipeline_rework.CommentTitleRecoveryTest.test_vlm_fetch_skips_degenerate_image_geometry_without_vlm_call -v
```

- 결과: `Ran 2 tests`, `OK`.
- 전체 rework 회귀:

```powershell
.\.venv312\Scripts\python.exe -m unittest tests.test_agentic_pipeline_rework -v
```

- 결과: `Ran 161 tests`, `OK`.
- run audit:

```powershell
.\.venv312\Scripts\python.exe tools\audit_expert_run_health.py --run-id 20260501_010427_282685
```

- 결과:
  - audit JSON: `out/run_audit_20260501_010427_282685.json`
  - `checkpoint_rows=4014`
  - `status_counts={'completed': 4014}`
  - `reason_errors=0`
  - `slang old/new/blocked=114/111/3`
  - `slang_db_bad_remaining=0`
  - `fatal_or_trace_line=4`
- 후속:
  - vLLM 서버 재기동 후 post `11589463` 포함 소량 canary 실행.
  - 기대 결과: `image_fetch_success=0`, limitation에 `image_geometry_too_small:389x1`, VLM chunk request 없음, 서버 500/502 없음.

### 2026-05-01 server canary after vLLM restart

- 판정: RUNTIME-GO / QUALITY-HOLD
- 입력: `out/sampling/targeted_vlm_degenerate_11589463_20260501.jsonl`
- 출력: `out/sampling/targeted_vlm_degenerate_11589463_20260501_result.json`
- run id: `20260501_160410_623323`
- 명령:

```powershell
.\.venv312\Scripts\python.exe expert_main.py --input out\sampling\targeted_vlm_degenerate_11589463_20260501.jsonl --output out\sampling\targeted_vlm_degenerate_11589463_20260501_result.json --parallel 1 --no-dashboard --server-type vllm --vlm on --ocr on --llm-suspend-on-anomaly off --slang-db off --no-auto-up-shards
```

- 런타임 결과:
  - `completed_count=1`, `failed_count=0`, `pending_count=0`
  - 로그: `logs/expert_run_20260501_160410_623323.log`
  - `VLM chunk request` 없음
  - `HTTPStatusError`, `500 Internal Server Error`, `502 Bad Gateway` 없음
  - 완료 로그의 VLM 요약: `vlm: used=False, fetch=0/1, chunks=0, bytes=0`
  - 결론: 재기동한 vLLM에서 동일 post를 실제 full pipeline으로 처리해도 문제 이미지는 VLM payload로 들어가지 않았고 serving crash는 재현되지 않음.
- 품질 HOLD:
  - 같은 run에서 별도 품질 문제가 드러남.
  - 검색 결과 `오러(판타지 용어)`가 character parenthetical bridge로 등록되어 `판타지 용어`가 resolved title처럼 승격됨.
  - 내부 reasoning은 반복적으로 `장르/트로프 일반론`, `특정 소설 아님`, `is_relevant=false`를 주장했지만 최종 output은 `is_relevant=true`, `official_title=판타지 용어`, `discussion_type=character_talk`로 뒤집힘.
  - 후속 개선: parenthetical bridge에서 `용어`, `개념`, `설정`, `장르`, `목록`, `대문` 등 비작품 범주 parenthetical을 작품명으로 승격하지 않는 guard와 단위 테스트 추가.

## 2026-04-28 - adjacent relevance and budget regression verification

- 판정: REGRESSION-GO / CANARY REQUIRED
- 추출한 실패 유형:
  - `adjacent_relevant`가 legacy `is_relevant=true`로 남아 주변 담론을 핵심 작품 토론처럼 카운트하는 문제.
  - `adjacent_meta_cheap` 검색 budget이 작가/플랫폼 주변담론과 장르 토론을 같은 `max_q`로 처리하는 문제.
- 조치:
  - 최종 `is_relevant`는 `topicality == core_relevant`일 때만 true로 계산.
  - `adjacent_relevant`는 `topicality`/`relevance_scope`로 보존하되 official title은 기본 null로 유도.
  - `adjacent_meta_cheap`은 작가/플랫폼/meta는 `max_q=2`, 장르 토론은 공식 근거 1칸을 남기기 위해 `max_q=3`.
- 테스트 케이스 추출:
  - `tests.test_agentic_pipeline_rework`에서 adjacent author/meta, recommendation, comment title recovery, budget profile 실패 계열 7건 추출.
  - budget positive/negative 이웃으로 `genre_discussion max_q=3`, `meta_platform/author_meta max_q=2`를 별도 확인.
- targeted 검증:

```powershell
.\venv\Scripts\python.exe -m unittest tests.test_agentic_pipeline_rework.AgenticPipelineReworkTest.test_adjacent_author_meta_clears_official_title tests.test_agentic_pipeline_rework.AgenticPipelineReworkTest.test_author_benchmark_post_stays_adjacent_author_meta tests.test_agentic_pipeline_rework.AgenticPipelineReworkTest.test_recommendation_request_without_title_stays_adjacent tests.test_agentic_pipeline_rework.CommentTitleRecoveryTest.test_author_criticism_context_forces_adjacent_author_meta tests.test_agentic_pipeline_rework.CommentTitleRecoveryTest.test_genre_discussion_comment_recommendation_does_not_trigger_canonical_recovery tests.test_agentic_pipeline_rework.OrchestratorBudgetProfileTest.test_adjacent_meta_profile tests.test_agentic_pipeline_rework.OrchestratorBudgetProfileTest.test_author_meta_budget_context_uses_adjacent_meta_profile -v
```

- 결과: `Ran 7 tests`, `OK`.
- budget 이웃 검증:

```powershell
.\venv\Scripts\python.exe -m unittest tests.test_agentic_pipeline_rework.AgenticPipelineReworkTest.test_adjacent_meta_cheap_budget_keeps_one_official_probe_slot tests.test_agentic_pipeline_rework.OrchestratorBudgetProfileTest.test_adjacent_meta_profile tests.test_agentic_pipeline_rework.OrchestratorBudgetProfileTest.test_author_meta_budget_context_uses_adjacent_meta_profile -v
```

- 결과: `Ran 3 tests`, `OK`.
- 전체 회귀:

```powershell
.\venv\Scripts\python.exe -m unittest tests.test_agentic_pipeline_rework -v
.\venv\Scripts\python.exe -m unittest tests.test_agentic_pipeline_alias_contract -v
```

- 결과:
  - `tests.test_agentic_pipeline_rework`: `Ran 145 tests`, `OK`
  - `tests.test_agentic_pipeline_alias_contract`: `Ran 30 tests`, `OK`
- 문법 검증:

```powershell
.\venv\Scripts\python.exe -m py_compile src\llm_batch\agentic_pipeline.py src\llm_batch\experts\orchestrator.py src\llm_batch\experts\arbiter.py src\llm_batch\prompts\prompt_router.py
```

- 결과: 통과.
- 후속:
  - 200건 canary에서 adjacent 판정이 `is_relevant` 카운트/official title/slang DB 저장으로 새지 않는지 집계.
  - 1,000건 risk discovery에서 장르 토론 `max_q=3`이 false positive를 늘리지 않는지 확인.

## 2026-04-28 - ambiguous title stem guard targeted verification

- 판정: REVIEW-GO for targeted fix / CANARY REQUIRED
- 관련 사례: `11684407`
- 관련 파일:
  - `src/llm_batch/agentic_pipeline.py`
  - `src/llm_batch/prompts/expert_prompts.py`
  - `src/llm_batch/prompts/prompt_router.py`
  - `tests/test_agentic_pipeline_alias_contract.py`
- 단위 검증:

```powershell
.\venv\Scripts\python.exe -m unittest tests.test_agentic_pipeline_alias_contract -v
```

- 결과:
  - `Ran 30 tests`
  - `OK`
  - 추가된 positive/negative 이웃 테스트:
    - 공통 stem 검색 이웃은 locked primary rescue를 막지 않음.
    - 직접 언급된 다른 공식 제목은 여전히 rescue blocker로 유지.
    - 검색 이웃은 comparison/recommendation/secondary reference에서 제거.
- 문법 검증:

```powershell
.\venv\Scripts\python.exe -m py_compile src\llm_batch\agentic_pipeline.py src\llm_batch\prompts\expert_prompts.py src\llm_batch\prompts\prompt_router.py tests\test_agentic_pipeline_alias_contract.py
```

- 결과: 통과.
- 단건 실제 재처리:

```powershell
.\venv\Scripts\python.exe expert_main.py --input tests\inputs\_tmp_11684407_single.jsonl --output out\sampling\targeted_ambiguous_title_stem_11684407_afterfix13_20260428_result.json --parallel 1 --no-dashboard --vlm off --ocr off --slang-db off --no-auto-up-shards
```

- 단건 결과:
  - `Total Posts=1`
  - `Relevant=1`
  - `Identified=1`
  - `official_title=마법소녀ㄴ은 은퇴하고 싶다`
  - `work_resolution=resolved`
  - `comparison_target=null`
  - `mentioned_works=null`
  - `secondary_reference_works=[]`
- 주변 테스트:

```powershell
.\venv\Scripts\python.exe -m unittest tests.test_agentic_pipeline_rework -v
```

- 결과:
  - `Ran 145 tests`
  - `FAILED (failures=7)`
  - 실패 계열: author/recommendation adjacent relevance 기대값 5건, adjacent meta budget profile 기대값 2건.
  - 해석: 이번 공통 title stem guard의 직접 경로는 아니지만, afterfix13 canary 전 별도 리워크 정리가 필요.

## 2026-04-26 - 20k run audit

- 판정: REVIEW
- 관련 run id: `20260423_170321_250907`
- 명령:

```powershell
.venv312\Scripts\python.exe tools\audit_expert_run_health.py --run-id 20260423_170321_250907
```

- 결과:
  - `checkpoint_rows=20532`
  - `status_counts={'completed': 20531, 'failed': 1}`
  - `reason_error_count=1`
  - `search_upstream_zero=45449`
  - `search_degraded_detected=13263`
  - `search_bridge_after_filter_zero=2166`
  - `search_timeout=102`
  - `llm_connection_refused=321`
  - `headless_naver_playwright=1057`
  - `headless_google_cloak=186`
- 해석:
  - 처리는 대부분 완료됐지만 shard 장애가 섞인 run이므로 검색 품질 승인은 보류.
- 후속:
  - 안정화 후 같은 입력의 소량 샘플 재처리.
  - 검색 저하율 비교.

## 2026-04-26 - shard audit before recreate

- 판정: NO-GO
- 명령:

```powershell
.venv312\Scripts\python.exe tools\audit_search_shards.py --count 36 --timeout 1.5
```

- 결과:
  - `ok=27/36`
  - bad shards: `[1, 10, 13, 15, 26, 27, 29, 33, 34]`
- 해석:
  - bad shard가 존재하므로 대량 런 품질 게이트 실패.

## 2026-04-26 - shard recreate

- 판정: implemented
- 명령:

```powershell
.venv312\Scripts\python.exe tools\warp_shards.py recreate --shards 1,10,13,15,26,27,29,33,34
```

- 결과:
  - 문제 shard bundle recreate 완료.

## 2026-04-26 - shard audit after recreate

- 판정: GO
- 명령:

```powershell
.venv312\Scripts\python.exe tools\audit_search_shards.py --count 36 --timeout 1.5
```

- 결과:
  - `ok=36/36`
  - `bad=[]`
- 해석:
  - shard reliability gate는 정상화.

## 2026-04-26 - syntax check

- 판정: GO
- 명령:

```powershell
.venv312\Scripts\python.exe -m py_compile src\llm_batch\search\client.py expert_main.py tools\audit_expert_run_health.py tools\audit_search_shards.py
```

- 결과:
  - 통과.

## 2026-04-26 - pytest availability

- 판정: REVIEW
- 명령:

```powershell
.venv312\Scripts\python.exe -m pytest tests -q
```

- 결과:
  - 실패: `.venv312`에 `pytest` 모듈 없음.
- 후속:
  - 테스트 실행 환경 정리 또는 의존성 문서화.

## 2026-04-26 - qualitative review packet smoke test

- 판정: GO
- 관련 run id: `20260423_170321_250907`
- 명령:

```powershell
.venv312\Scripts\python.exe tools\build_llm_judgment_review_packet.py --run-id 20260423_170321_250907 --limit 30 --per-bucket 8
```

- 결과:
  - JSONL: `out/llm_judgment_reviews/llm_judgment_review_20260423_170321_250907_20260426_201232.jsonl`
  - Markdown: `out/llm_judgment_reviews/llm_judgment_review_20260423_170321_250907_20260426_201232.md`
  - `selected=30 from rows=20532`
  - 주요 risk tags: `search_degraded_majority=27`, `search_degraded=29`, `slang_insight=22`, `slang_not_stored=15`, `resolved_low_anchor=12`, `status_failed=1`
- 해석:
  - 정성 리뷰 패킷 생성 경로 정상.
  - 20k run은 여전히 REVIEW baseline이므로 실제 품질 승인은 전문가 판정 이후 가능.

## 2026-04-26 - qualitative expert review batch

- 판정: REVIEW
- 관련 run id: `20260423_170321_250907`
- 리뷰 패킷:
  - `out/llm_judgment_reviews/llm_judgment_review_20260423_170321_250907_20260426_201809.jsonl`
  - `out/llm_judgment_reviews/llm_judgment_review_20260423_170321_250907_20260426_201809.md`
- 상세 문서:
  - `docs/devs/QUALITATIVE_REVIEW_20260426.md`
- 전문가 A 검색/근거 표본 81건:
  - `ACCEPT=48`, `HOLD=14`, `RESEARCH=5`, `REPROCESS=9`, `REJECT=5`
- 전문가 B slang/DB 대상 105건:
  - `confirmed_alias≈52`, `pending_alias≈19`, `secondary_reference≈6`, `comparison_only≈1`, `noise≈27`
- 전문가 C relevance/work resolution 표본 95건:
  - `ACCEPT=32`, `HOLD=8`, `RESEARCH=25`, `REPROCESS=25`, `REJECT=5`
- 통합 해석:
  - 위험군 집중 표본에서 자동 승인하기 어려운 케이스가 충분히 많아 전체 판정은 `REVIEW`.
  - 검색 장애 baseline 결과는 정성 리뷰 없이 품질 승인하면 안 됨.
- 한계:
  - 300건 위험군 샘플은 오류 유형 발견용이며 20k 전체 품질 승인용 표본으로는 부족.
  - 후속으로 계층 샘플 확대와 같은 post id 재처리 비교가 필요.

## 2026-04-26 - stratified 1000 review packet

- 판정: PACKET-GENERATED
- 관련 run id: `20260423_170321_250907`
- 명령:

```powershell
.venv312\Scripts\python.exe tools\build_llm_judgment_review_packet.py --run-id 20260423_170321_250907 --limit 1000 --per-bucket 80 --strategy stratified --control-count 120
```

- 출력:
  - `out/llm_judgment_reviews/llm_judgment_review_20260423_170321_250907_20260426_234227.jsonl`
  - `out/llm_judgment_reviews/llm_judgment_review_20260423_170321_250907_20260426_234227.md`
- 결과:
  - `selected=1000 from rows=20532`
  - `routine_sample=120`
  - 주요 risk tags: `search_degraded=782`, `search_degraded_majority=750`, `relevant_without_official_title=340`, `slang_insight=258`, `slang_not_stored=184`, `unresolved_or_ambiguous_work=174`, `possible_false_negative_anchor=161`, `possible_false_negative_novel_cue=113`
- 해석:
  - 300건 리뷰의 후속으로 쓸 수 있는 확대 패킷 생성 완료.
  - 아직 전문가 adjudication은 미완료이므로 20k run 최종 판정은 계속 `REVIEW`.

## 2026-04-26 - search query expansion probe

- 판정: PARTIAL
- 관련 파일:
  - `tools/run_search_query_expansion_probe.py`
- 수동 프로브:

```powershell
.venv312\Scripts\python.exe tools\run_search_query_expansion_probe.py --manual-query "괴담텔" --manual-query "괴담텔 웹소설" --manual-query "괴담텔 장르소설" --manual-query "괴담텔 노벨피아" --manual-query "즉사무림" --manual-query "즉사무림 웹소설" --manual-query "즉사무림 장르소설" --manual-query "즉사무림 문피아" --max-queries-per-item 8 --timeout 4 --num-results 5
```

- 수동 프로브 결과:
  - 출력: `out/search_query_experiments/search_query_expansion_20260426_234412.md`
  - `queries=8`, `ok=8`, `errors=0`
  - `base_detail_hits=1`, `expanded_detail_hits=4`
- 패킷 기반 소량 프로브:
  - 출력: `out/search_query_experiments/search_query_expansion_20260426_234524.md`
  - `queries=25`, `ok=11`, `errors=14`
  - `base_detail_hits=1`, `expanded_detail_hits=4`
- 해석:
  - 작품/약칭이 정확한 경우 플랫폼명 조합은 공식 상세 hit를 늘리는 경향이 있음.
  - `장르소설`/`웹소설` suffix는 회수율을 올릴 수 있지만 일반 제목/잡담에는 timeout, 검색 잡음, false positive 위험도 같이 증가.
  - 쿼리 확장은 alias/title confidence gate와 함께 적용해야 함.

## 2026-04-26 - confident query expansion gate

- 판정: IMPLEMENTED / REVIEW
- 관련 파일:
  - `src/llm_batch/experts/orchestrator.py`
  - `docs/devs/SAMPLING_AND_PARALLEL_TEST_GUIDE.md`
- 조치:
  - 확정 약칭은 alias-only 예외로 허용하고, 일반 표면어는 `novel_literature` 도메인일 때만 `웹소설/장르소설/플랫폼` 확장을 붙이도록 gate 추가.
  - 일반 제목/잡담/비소설 도메인은 confident title expansion에서 제외.
- 문법 확인:

```powershell
.venv312\Scripts\python.exe -m py_compile src\llm_batch\experts\orchestrator.py tools\build_balanced_regression_input.py tools\run_search_query_expansion_probe.py tools\build_llm_judgment_review_packet.py
```

- 단위 경로 확인:
  - `즉사무림` + `novel_literature` -> `즉사무림 웹소설`, `즉사무림 장르소설`, 플랫폼 확장 4건 추가
  - `ect` + `other` -> 확장 없음
  - `모도쿠가오소우` + `other` -> 확장 없음
- 병렬 smoke:
  - 입력: `out/sampling/query_gate_parallel_smoke_20260426.jsonl`
  - 출력: `out/sampling/query_gate_parallel_smoke_20260426_result.json`
  - 로그: `logs/expert_run_20260426_235548_804188.log`
  - 결과: 4건 완료, 1건 resolved, 3건 경계/비관련
  - 판정: `SMOKE ONLY`
- smoke에서 발견한 위험:
  - 초기 gate는 `모도쿠가오소우` 같은 비소설 제목에도 platform suffix를 붙였음.
  - 이후 gate를 더 좁혀 비소설/other 도메인의 title surface expansion을 차단함.
- 남은 작업:
  - 200건 canary와 1,000/10,000건 표본 재처리로 false positive/false negative 변화 확인.

## 2026-04-26 - sampling artifacts for large validation

- 판정: SAMPLE-GENERATED
- 생성 명령:

```powershell
.venv312\Scripts\python.exe tools\build_balanced_regression_input.py --checkpoint out\expert_result_20260423_170321_250907_checkpoint.jsonl --output out\sampling\query_gate_canary_200_20260426.jsonl --max-posts 200 --per-bucket 20 --must-post-ids 11718077,11718070,11718071,11718074
.venv312\Scripts\python.exe tools\build_balanced_regression_input.py --checkpoint out\expert_result_20260423_170321_250907_checkpoint.jsonl --output out\sampling\query_gate_risk_discovery_1000_20260426.jsonl --max-posts 1000 --per-bucket 80 --must-post-ids 11718077,11718070,11718071,11718074
.venv312\Scripts\python.exe tools\build_balanced_regression_input.py --checkpoint out\expert_result_20260423_170321_250907_checkpoint.jsonl --output out\sampling\query_gate_validation_10000_20260426.jsonl --max-posts 10000 --per-bucket 800 --must-post-ids 11718077,11718070,11718071,11718074
```

- 산출물:
  - `out/sampling/query_gate_canary_200_20260426.jsonl`, `post_count=200`
  - `out/sampling/query_gate_risk_discovery_1000_20260426.jsonl`, `post_count=1000`
  - `out/sampling/query_gate_validation_10000_20260426.jsonl`, `post_count=10000`
- 해석:
  - 4건 smoke는 품질 승인 불가.
  - 200건은 병렬 canary, 1,000건은 위험 유형 발견, 10,000건은 개선 전후 비교용.

## 2026-04-27 - search shard state after smoke

- 판정: SMOKE-ENV-GO / PRODUCTION-COUNT-REVIEW
- 명령:

```powershell
.venv312\Scripts\python.exe tools\audit_search_shards.py --count 2 --timeout 1.0
```

- 출력: `out/search_shard_audit_20260427_000659.json`
- 결과:
  - `ok=2/2`
  - `bad=[]`
- 해석:
  - 병렬 smoke 실행 과정에서 테스트용 shard 2개가 자동 구성됨.
  - 대형 검증/운영 run 전에는 목표 shard 수를 명시하고 다시 감사해야 함.

## 2026-04-27 - query gate 200 canary and stuck-case repro

- 판정: REVIEW / NO-GO
- 관련 입력:
  - `out/sampling/query_gate_canary_200_20260426.jsonl`
  - `out/sampling/query_gate_stuck_11478694_20260427.jsonl`
- 관련 산출물:
  - `out/sampling/query_gate_canary_200_20260427_result_checkpoint.jsonl`
  - `out/sampling/query_gate_canary_200_20260427_run_summary.json`
  - `out/sampling/query_gate_canary_200_20260427_stuck_cases.json`
  - `out/sampling/query_gate_canary_200_20260427_result_recovered_from_checkpoint.json`
  - `out/sampling/query_gate_stuck_11478694_20260427_result.json`
  - `out/sampling/query_gate_stuck_11478694_20260427_result_manifest.json`
- shard 감사:
  - 전: `out/search_shard_audit_20260427_002659.json`, `ok=36/36`
  - 후: `out/search_shard_audit_20260427_025329.json`, `ok=36/36`
  - 패치 후 재확인: `out/search_shard_audit_20260427_032109.json`, `ok=36/36`
- 200건 canary 결과:
  - run id: `20260427_002737_046977`
  - checkpoint rows: `199/200`
  - status: `completed=94`, `failed=105`
  - 실패 사유: `105건 모두 [Errno 22] Invalid argument`
  - 미기록/stuck: `global_idx=100`, `post_id=11478694`, `슬레이어즈 원형은 원래 sf소설이었다던데`
  - manifest: `completed_count=199`, `flushed_count=99`, `pending_count=100`, `next_save_idx=100`
- 확인된 원인:
  - `_cli_progress()`가 shell timeout 이후 닫힌 stderr pipe에 쓰면서 완료 post도 failed checkpoint로 오염.
  - snippet analyzer가 `category=anime`로 본 뒤에도 indirect title/alias/fetch 보강이 이어짐.
  - MCP client failover가 검색 1건에서 전체 36 endpoint를 순차로 훑을 수 있어 long-tail latency가 커짐.
- 적용 조치:
  - `expert_main.py`: CLI progress 출력 오류를 checkpoint 실패로 전파하지 않도록 방어.
  - `src/llm_batch/experts/orchestrator.py`: 비소설 매체 hard guard로 indirect title/alias/fetch 보강 차단.
  - `src/llm_batch/search/client.py`: `MCP_CLIENT_SEARCH_TIMEOUT_SEC`, `MCP_CLIENT_MAX_ENDPOINTS_PER_SEARCH` 추가.
- 문법 확인:

```powershell
.venv312\Scripts\python.exe -m py_compile expert_main.py src\llm_batch\experts\orchestrator.py src\llm_batch\search\client.py
```

- 단일 stuck 재현:
  - run id: `20260427_030848_374214`
  - manifest: `completed_count=1`, `failed_count=0`, `pending_count=0`
  - 처리 시간: `485.4s`
  - 로그상 `비소설 매체 간접 보강 차단` 확인.
  - 기존 약 20분 정체 구간은 약 100초 수준으로 감소.
- 전문가 리뷰 패킷:
  - `out/llm_judgment_reviews/llm_judgment_review_20260427_002737_046977_20260427_032233.jsonl`
  - `out/llm_judgment_reviews/llm_judgment_review_20260427_002737_046977_20260427_032233.md`
  - `selected=80 from rows=199`
  - 주요 bucket: `status_failed=45`, `search_degraded_majority=28`, `routine_sample=5`
- 남은 위험:
  - 단일 재현은 완료됐지만 485초는 여전히 canary에서 long-tail 위험.
  - 최종 판정은 `슬레이어즈`를 resolved 작품으로 잡아 LLM/전문가 정성 리뷰 대상.
  - 200건 canary는 통과하지 않았으므로 1,000/10,000건 validation으로 넘어가면 안 됨.
- 다음 작업:
  - `MCP_CLIENT_MAX_ENDPOINTS_PER_SEARCH=4`, `MCP_CLIENT_SEARCH_TIMEOUT_SEC=12`, `MCP_CLIENT_SEARCH_MAX_RETRIES=1` 기준으로 200건 canary 재실행.
  - 통과 기준: checkpoint rows `200/200`, stuck `0`, false failed `0`, long-tail post 별도 목록화.
  - 품질 판단은 전문가 review packet으로 `11478694` 같은 off-domain/light-novel 경계 케이스를 직접 판정.

## 2026-04-27 - expert_main startup shard probe

- 판정: STARTUP-GO
- 목적:
  - `expert_main.py` 실행 시작 시 로컬 shard 자동 기동/정리 경로를 그대로 사용해 canary를 실행해도 되는지 확인.
- 방식:
  - `MCP_ENDPOINTS`, `MCP_ENDPOINT`를 비우고 `MCP_SHARD_COUNT=36`만 지정.
  - `--no-auto-up-shards`는 사용하지 않음.
  - `expert_main.py`가 `MCP_ENDPOINTS`를 autogen하고 `warp_shards.py up`, WARP 상태 확인, `/readyz` 기반 health check를 수행하는지 확인.
- 확인 입력:
  - `out/sampling/expert_main_startup_shard_probe_one_nobom_20260427.jsonl`
- 산출물:
  - `out/sampling/expert_main_startup_shard_probe_one_nobom_20260427_result.json`
  - `out/sampling/expert_main_startup_shard_probe_one_nobom_20260427_result_checkpoint.jsonl`
  - `out/sampling/expert_main_startup_shard_probe_one_nobom_20260427_result_manifest.json`
  - `out/sampling/expert_main_startup_shard_probe_one_nobom_20260427_console.log`
  - `logs/warp_shards_status_20260427_114248_616808.json`
- 결과:
  - run id: `20260427_114248_616808`
  - 입력 로드: `1개 포스트`
  - startup: `로컬 MCP/WARP shard 36개 자동 기동 완료`
  - WARP 상태: `running=36/36`, `warp_on=36/36`
  - health check: `ok=36/36`
  - manifest: `completed_count=1`, `failed_count=0`, `pending_count=0`
- 해석:
  - 200건 canary 재실행은 별도 `warp_shards.py up`만 선행하기보다 `expert_main.py` startup auto-manage 경로를 사용해 실행하는 편이 맞음.
  - 단, 테스트 입력 JSONL은 BOM 없이 저장해야 함. BOM이 붙은 임시 probe 파일은 첫 줄 `JSONDecodeError`로 0건 로드될 수 있음.
- 권장 canary 실행 조건:
  - `MCP_SHARD_COUNT=36`
  - `MCP_AUTO_SHARD_LIMIT=36`
  - `MCP_CLIENT_MAX_ENDPOINTS_PER_SEARCH=4`
  - `MCP_CLIENT_SEARCH_TIMEOUT_SEC=12`
  - `MCP_CLIENT_SEARCH_MAX_RETRIES=1`
  - `--no-auto-up-shards` 미사용

## 2026-04-27 - query gate 200 canary auto rerun

- 판정: GO-CANARY-STABILITY / QUALITY-REVIEW
- 목적:
  - `expert_main.py` startup auto-manage 경로로 36개 shard를 재정리한 뒤 200건 canary를 다시 실행해, 1차 canary의 false failed/stuck 재발 여부를 확인.
- 관련 입력:
  - `out/sampling/query_gate_canary_200_20260426.jsonl`
- 관련 산출물:
  - `out/sampling/query_gate_canary_200_20260427_auto_result.json`
  - `out/sampling/query_gate_canary_200_20260427_auto_result_checkpoint.jsonl`
  - `out/sampling/query_gate_canary_200_20260427_auto_result_manifest.json`
  - `out/sampling/query_gate_canary_200_20260427_auto_run_summary.json`
  - `out/sampling/query_gate_canary_200_20260427_auto_stdout.log`
  - `out/sampling/query_gate_canary_200_20260427_auto_stderr.log`
- 실행 조건:
  - `MCP_SHARD_COUNT=36`, `MCP_AUTO_SHARD_LIMIT=36`
  - `MCP_HEALTH_USE_READYZ=1`
  - `MCP_CLIENT_ENDPOINT_FAILOVER=1`
  - `MCP_CLIENT_MAX_ENDPOINTS_PER_SEARCH=4`
  - `MCP_CLIENT_SEARCH_TIMEOUT_SEC=12`
  - `MCP_CLIENT_SEARCH_MAX_RETRIES=1`
  - `PIPELINE_SEARCH_CONCURRENCY=8`
  - `LLM_ENABLE_CONFIDENT_QUERY_EXPANSION=1`
  - `LLM_ENABLE_GENRE_NOVEL_QUERY_EXPANSION=1`
  - `--no-auto-up-shards` 미사용
- startup 확인:
  - run id: `20260427_121338_563339`
  - 입력 로드: `200개 포스트`
  - startup: `로컬 MCP/WARP shard 36개 자동 기동 완료`
  - WARP 상태: `running=36/36`, `warp_on=36/36`
  - health check: `ok=36/36`
- 결과:
  - checkpoint rows: `200/200`
  - status: `completed=200`, `failed=0`
  - missing global_idx: `0`
  - manifest: `completed_count=200`, `flushed_count=200`, `pending_count=0`, `failed_count=0`
  - 1차 stuck 케이스 `global_idx=100`, `post_id=11478694` 완료.
  - `11478694` 처리 시간: `703.9s`, `4 iterations`
- 사후 shard 감사:
  - `out/search_shard_audit_20260427_134858.json`
  - `ok_count=36/36`, `bad_count=0`
- 로그 요약:
  - `400 Bad Request`: `12`
  - `검색 오류`: `81`
  - `timed out`: `82`
  - `alias bridge 검색 추가`: `82`
  - `비소설 매체 간접 보강 차단`: `22`
  - `무결과-인프라 구간 감지`: `220`
  - 상위 long-tail: `11457804=886.4s`, `11478694=703.9s`, `11456200=586.5s`, `11676309=513.6s`, `11523367=497.9s`
- 전문가/LLM 리뷰 패킷:
  - `out/llm_judgment_reviews/llm_judgment_review_20260427_121338_563339_20260427_135409.jsonl`
  - `out/llm_judgment_reviews/llm_judgment_review_20260427_121338_563339_20260427_135409.md`
  - `selected=80 from rows=200`
  - 주요 bucket: `search_degraded_majority=64`, `routine_sample=10`, `possible_false_negative_novel_cue=3`, `search_degraded=3`
  - 주요 risk tag: `search_degraded=67`, `slang_insight=43`, `slang_not_stored=23`, `relevant_without_official_title=15`, `consistency_flag_review=18`
- 해석:
  - 1차 canary의 `[Errno 22] Invalid argument` false failed와 `11478694` stuck은 재발하지 않음.
  - 200건 canary 안정성 기준은 통과했으므로 1,000건 risk discovery로 진행 가능.
  - 다만 검색 timeout/infra no-result 로그와 long-tail이 아직 크므로 10,000건 validation 또는 운영 품질 GO 전에는 80건 리뷰 패킷 adjudication과 long-tail 원인 분리가 필요.
- 다음 작업:
  - 1,000건 risk discovery를 같은 startup auto-manage/env 조건으로 실행.
  - `11457804`, `11478694`, `11456200` 같은 long-tail 상위 post의 검색/LLM 단계별 병목 분석.
  - 이번 80건 review packet을 전문가가 직접 읽고 `ACCEPT/HOLD/REPROCESS/REJECT` 집계.

## 2026-04-27 - late search budget guard verification

- 판정: UNIT-GO / CANARY-REQUIRED
- 관련 변경:
  - `src/llm_batch/experts/orchestrator.py`
  - `tests/test_agentic_pipeline_rework.py`
- 목적:
  - 검색 배치 내부 cap이 아니라 post 단위 반복 verification/recall 검색 누적을 제한.
  - 초기 title/alias 탐색 recall은 유지.
- 검증 명령:
  - `.venv312\Scripts\python.exe -m py_compile src\llm_batch\experts\orchestrator.py`
  - `.venv312\Scripts\python.exe -m unittest tests.test_agentic_pipeline_rework.AgenticPipelineReworkTest.test_late_total_search_budget_is_not_applied_to_early_iterations tests.test_agentic_pipeline_rework.AgenticPipelineReworkTest.test_late_total_search_budget_applies_to_verification_batch tests.test_agentic_pipeline_rework.AgenticPipelineReworkTest.test_execute_searches_caps_late_total_budget`
- 결과:
  - `py_compile`: pass
  - targeted unit tests: `3/3 OK`
- 참고 smoke:
  - run id: `20260427_140716_814536`
  - 입력: `out/sampling/query_gate_stuck_11478694_20260427.jsonl`
  - 출력: `out/sampling/query_gate_stuck_11478694_late_budget_20260427_result.json`
  - manifest: `completed_count=1`, `failed_count=0`, `pending_count=0`
  - 처리: `291.8s`, `3 iterations`, 검색 실행 `13건`
  - 제한: `MCP_SHARD_COUNT`를 명시하지 않아 startup shard가 `1/1`로 구성됐고, 최종 late-purpose refinement 직전에 시작된 smoke라 품질 승인 근거로 쓰지 않음.
- 다음 확인:
  - `MCP_SHARD_COUNT=36`, `MCP_AUTO_SHARD_LIMIT=36` 조건으로 200건 canary 재실행.
  - `late_budget_capped_total`, `late_budget_exhausted_total`, top latency, post별 executed search count 변화 기록.

## 2026-04-27 - late search budget 200 canary comparison

- 판정: CANARY-STABILITY-GO / QUALITY-REVIEW
- baseline run: `20260427_121338_563339`
- improved run: `20260427_143145_922090`
- 입력:
  - `out/sampling/query_gate_canary_200_20260426.jsonl`
- 산출물:
  - `out/sampling/query_gate_canary_200_late_budget_20260427_result.json`
  - `out/sampling/query_gate_canary_200_late_budget_20260427_result_checkpoint.jsonl`
  - `out/sampling/query_gate_canary_200_late_budget_20260427_result_manifest.json`
  - `out/sampling/query_gate_canary_200_late_budget_20260427_run_summary.json`
  - `out/comparisons/query_gate_canary_200_20260427_baseline_vs_late_budget.json`
  - `out/comparisons/query_gate_canary_200_20260427_baseline_vs_late_budget.md`
- 실행 조건:
  - `MCP_SHARD_COUNT=36`, `MCP_AUTO_SHARD_LIMIT=36`
  - `MCP_HEALTH_USE_READYZ=1`
  - `MCP_CLIENT_ENDPOINT_FAILOVER=1`
  - `MCP_CLIENT_MAX_ENDPOINTS_PER_SEARCH=4`
  - `MCP_CLIENT_SEARCH_TIMEOUT_SEC=12`
  - `MCP_CLIENT_SEARCH_MAX_RETRIES=1`
  - `PIPELINE_SEARCH_CONCURRENCY=8`
  - `LLM_ENABLE_CONFIDENT_QUERY_EXPANSION=1`
  - `LLM_ENABLE_GENRE_NOVEL_QUERY_EXPANSION=1`
  - `LLM_ENABLE_LATE_TOTAL_SEARCH_BUDGET=1`
  - `LLM_ENABLE_LATE_SEARCH_BUDGET=1`
  - `LLM_LATE_TOTAL_SEARCH_MIN_ITERATION=3`
- 결과:
  - checkpoint rows: `200/200`
  - status: `completed=200`, `failed=0`
  - missing global_idx: `0`
  - manifest: `completed_count=200`, `flushed_count=200`, `pending_count=0`, `failed_count=0`
  - 사후 shard audit: `out/search_shard_audit_20260427_late_budget_postrun.json`, `ok=36/36`, `bad=[]`
- baseline 대비 요약:
  - relevant: `148 -> 153` (`+5`)
  - identified with title: `72 -> 76` (`+4`)
  - total time: `5452.3s -> 5453.8s` (`+1.5s`, 사실상 flat)
  - 검색 오류: `81 -> 75` (`-6`)
  - timed out: `82 -> 75` (`-7`)
  - alias bridge 검색 추가: `82 -> 76` (`-6`)
  - infra no-result: `220 -> 244` (`+24`)
  - late search budget cap/exhausted: `22 / 14`
- 핵심 long-tail:
  - `11478694`: `703.9s/4iter -> 361.7s/2iter`
  - `11456200`: `586.5s/4iter -> 267.4s/3iter`
  - `11457804`: `886.4s/3iter -> 911.5s/4iter`, 여전히 병목
  - `11718077`: `151.8s/3iter -> 496.2s/3iter`, 회귀 샘플로 리뷰 필요
- 전문가/LLM 리뷰 패킷:
  - `out/llm_judgment_reviews/llm_judgment_review_20260427_143145_922090_20260427_160810.jsonl`
  - `out/llm_judgment_reviews/llm_judgment_review_20260427_143145_922090_20260427_160810.md`
  - `selected=100 from rows=200`
  - 주요 bucket: `search_degraded_majority=79`, `routine_sample=13`
- 해석:
  - run 안정성은 GO. 200건 완주, 실패 0, 사후 shard audit 정상.
  - late search budget guard는 실제 canary에서 발동함.
  - 검색 오류와 timeout은 소폭 감소했지만 사라지지 않았고, infra no-result는 증가했다.
  - long-tail 전체 개선은 혼재됨. `11478694`, `11456200`은 개선됐지만 `11457804`, `11718077`은 추가 분석 필요.
  - relevance/title 수가 늘어 품질 개선 가능성은 있으나, 같은 post id 결과 변화가 있어 전문가 정성 리뷰 전에는 품질 GO로 승인하지 않음.
- 다음 작업:
  - 100건 리뷰 패킷을 전문가가 직접 읽고 `ACCEPT/HOLD/REPROCESS/REJECT` 집계.
  - `11457804`, `11718077` 로그를 단계별로 분해해 late budget 외 병목을 확인.
  - 같은 비교 루틴으로 1,000건 risk discovery 실행.

## 2026-04-27 - generic/character targeted regression

- 판정: UNIT-GO / TARGETED-REVIEW
- 목적:
  - `11631298` 일반 무협 세력명 과확정 차단.
  - `11663540` 캐릭터 parenthetical 작품명 회수 및 `전차` 같은 일반 설정어 오승격 차단.
  - `11549038` 과거 `[Errno 22] Invalid argument` row가 최신 rerun에서 재발하는지 확인.
- 관련 변경:
  - `src/llm_batch/experts/verifier.py`
  - `src/llm_batch/experts/orchestrator.py`
  - `src/llm_batch/experts/arbiter.py`
  - `src/llm_batch/agentic_pipeline.py`
  - `src/llm_batch/prompts/expert_prompts.py`
  - `tests/test_agentic_pipeline_rework.py`
- 단위 검증:
  - `py_compile`: pass
  - targeted unittest `7/7 OK`
  - 커버: generic martial faction guard, character parenthetical registration, event parenthetical rejection, `전차/줄다리기` generic topic guard.
- 실제 targeted run:
  - 입력: `out/sampling/targeted_generic_character_3_20260427.jsonl`
  - 최신 출력: `out/sampling/targeted_generic_character_3_20260427_afterfix3_result.json`
  - 로그: `logs/expert_run_20260427_174602_508561.log`
  - startup: 로컬 MCP/WARP shard 3개 자동 기동/헬스체크 정상.
- 최신 결과 요약:
  - `11549038`: error 재발 없음. `adjacent_relevant / trope_discussion`, official title 없음.
  - `11631298`: `무림맹주 막내제자` official title 확정은 차단. 단, `unresolved_title`과 `title_candidates`에는 후보가 남아 추가 정리 필요.
  - `11663540`: `전차` official title 오승격은 차단. 단, `전 버튜버가 하고 싶은데요` 최종 확정은 아직 실패하고 `character_talk / unresolved_title`로 남음.
- 해석:
  - 치명 FP(`무림맹주 막내제자` 확정, `전차` 확정)는 줄었지만, 캐릭터 parenthetical 회수는 최종 consistency/deliberation 단계에서 아직 안정적으로 닫히지 않음.
  - targeted 3건은 회귀 탐지용이며 품질 GO 근거가 아님. 같은 유형을 포함한 200/1,000건 분산 샘플 재검증 필요.
- 다음 작업:
  - `generic_relation_only` 후보를 `title_candidates`에서 제거하거나 secondary reference로만 보존.
  - `character_parenthetical_wiki + official platform hit + jury strong` 조합을 final consistency에서 유지하도록 좁은 조건 재설계.
  - 이 변경 후 동일 3건 + 분산 200건 canary 재실행.

## 2026-04-27 - generic/character targeted afterfix8

- 판정: TARGETED-GO / CANARY-REQUIRED
- 목적:
  - `11631298`의 search-only 작품 후보 누수 제거.
  - `11663540`의 `주서연(전 버튜버가 하고 싶은데요)` parenthetical 검색 증거를 최종 작품명으로 연결.
  - `confidence="High"` 문자열이 숫자 비교에서 worker를 죽이는 오류 제거.
- 관련 변경:
  - `src/llm_batch/agentic_pipeline.py`
  - `src/llm_batch/experts/orchestrator.py`
  - `src/llm_batch/experts/arbiter.py`
  - `tests/test_agentic_pipeline_rework.py`
- 단위 검증:

```powershell
.venv312\Scripts\python.exe -m py_compile src\llm_batch\agentic_pipeline.py src\llm_batch\experts\orchestrator.py src\llm_batch\experts\arbiter.py tests\test_agentic_pipeline_rework.py
.venv312\Scripts\python.exe -m unittest tests.test_agentic_pipeline_rework.AgenticPipelineReworkTest.test_generic_relation_only_drops_decoder_title_candidates tests.test_agentic_pipeline_rework.AgenticPipelineReworkTest.test_generic_relation_only_consistency_demotes_short_genre_reaction tests.test_agentic_pipeline_rework.AgenticPipelineReworkTest.test_character_parenthetical_bridge_resolves_final_title tests.test_agentic_pipeline_rework.AgenticPipelineReworkTest.test_search_parenthetical_bridge_resolves_without_registered_link tests.test_agentic_pipeline_rework.OrchestratorBudgetProfileTest.test_community_parenthetical_profile_registers_character_bridge tests.test_agentic_pipeline_rework.OrchestratorBudgetProfileTest.test_character_parenthetical_wiki_hint_registers_work_bridge tests.test_agentic_pipeline_rework.OrchestratorBudgetProfileTest.test_event_parenthetical_wiki_hint_does_not_register_character_bridge tests.test_agentic_pipeline_rework.OrchestratorBudgetProfileTest.test_merge_snippet_hints_rescans_search_results_for_character_parenthetical
```

- 결과:
  - `py_compile`: pass
  - targeted unittest: `8/8 OK`
  - Arbiter confidence label unittest: `OK`
- 3건 startup-shard targeted:
  - 명령: `expert_main.py out\sampling\targeted_generic_character_3_20260427.jsonl --output out\sampling\targeted_generic_character_3_20260427_afterfix6_result.json --parallel 3 --no-dashboard --server-type vllm --vlm off --ocr off`
  - startup: 로컬 MCP/WARP shard 3개 재기동, WARP `3/3`, health `3/3`.
  - `11631298`: `is_relevant=false`, `work_resolution=none`, `title_candidates=null`, `secondary_reference_works=[]`, `generic_relation_only_demoted`.
  - `11549038`: 처리 오류 재발 없음.
  - `11663540`: 추가 `confidence` 문자열 비교 오류가 발견되어 별도 수정.
- 단독 targeted:
  - 입력: `out/sampling/targeted_character_11663540_20260427_nobom.jsonl`
  - 출력: `out/sampling/targeted_character_11663540_20260427_afterfix8_result.json`
  - 로그: `logs/expert_run_20260427_183618_158484.log`
  - 결과: `is_relevant=true`, `official_title=전 버튜버가 하고 싶은데요`, `confidence=High`, `discussion_type=character_talk`, `character_parenthetical_title_resolved`.
- 해석:
  - 캐릭터 중심 팬덤 토론은 predicate(`전차`, `줄다리기`)가 공식 설정으로 직접 연결되지 않아도, 중심 캐릭터가 단일 작품으로 안정 연결되면 작품 토론으로 accept한다.
  - 일반 무협 세력명은 공식 작품 검색 결과가 있더라도 post 내부 고유 앵커가 없으면 결과 필드에 작품 후보를 노출하지 않는다.
  - 단독 targeted에서 발견된 Arbiter `confidence` 문자열 비교 오류는 코드 수정 및 단위 검증 완료. afterfix8 결과에는 이전 오류 플래그가 남아 있으므로 다음 전체 canary에서 재발 여부를 확인한다.
- 다음 작업:
  - 동일 3건을 한 번 더 3-shard로 재실행해 `11663540`의 `verifier_technical_failure` 플래그가 사라지는지 확인.
  - 그 뒤 200건 분산 canary에서 false positive/false negative 변화와 confidence type error 재발 여부를 확인.

## 2026-04-27 - generic/character targeted afterfix11

- 판정: TARGETED-GO / 200-CANARY-REQUIRED
- 목적:
  - afterfix10에서 확인된 `11663540` 최종 미확정 회귀를 재현 형태 그대로 수정.
  - `comparison_target=주서연`처럼 실제 작품 비교가 아닌 약한 캐릭터 표면 후보가 parenthetical 작품 확정을 막지 않게 함.
  - confidence 문자열 비교/산술 오류 재발 여부 확인.
- 관련 변경:
  - `src/llm_batch/agentic_pipeline.py`
  - `tests/test_agentic_pipeline_rework.py`
- 단위 검증:

```powershell
.venv312\Scripts\python.exe -m py_compile src\llm_batch\agentic_pipeline.py tests\test_agentic_pipeline_rework.py
.venv312\Scripts\python.exe -m unittest tests.test_agentic_pipeline_rework.AgenticPipelineReworkTest.test_search_parenthetical_bridge_resolves_without_registered_link tests.test_agentic_pipeline_rework.AgenticPipelineReworkTest.test_character_parenthetical_bridge_resolves_final_title tests.test_agentic_pipeline_rework.AgenticPipelineReworkTest.test_generic_relation_only_consistency_demotes_short_genre_reaction tests.test_agentic_pipeline_rework.AgenticPipelineReworkTest.test_arbiter_confidence_to_unit_handles_string_labels tests.test_agentic_pipeline_rework.AgenticPipelineReworkTest.test_verifier_confidence_to_unit_handles_string_labels
```

- 단위 결과:
  - `py_compile`: pass
  - targeted unittest: `5/5 OK`
- 3건 3-shard targeted:
  - 입력: `out/sampling/targeted_generic_character_3_20260427.jsonl`
  - 출력: `out/sampling/targeted_generic_character_3_20260427_afterfix11_result.json`
  - 로그: `logs/expert_run_20260427_190157_041612.log`
  - 명령: `expert_main.py out\sampling\targeted_generic_character_3_20260427.jsonl --output out\sampling\targeted_generic_character_3_20260427_afterfix11_result.json --parallel 3 --no-dashboard --server-type vllm --vlm off --ocr off --no-auto-up-shards`
  - shard health: `3/3 OK`
  - 처리: `3/3`, failed 없음, total time `337.8s`, avg `112.6s/post`
- 결과:
  - `11549038`: `is_relevant=true`, `discussion_type=trope_discussion`, `work_resolution=none`, 오류 재발 없음.
  - `11631298`: `is_relevant=false`, `topicality=unrelated`, `work_resolution=none`, `title_candidates=[]`, `secondary_reference_works=[]`, `generic_relation_only_demoted`.
  - `11663540`: `is_relevant=true`, `official_title=전 버튜버가 하고 싶은데요`, `discussion_type=character_talk`, `work_resolution=resolved`, `identity_state=resolved_title`, `system_state=clean`.
- 로그 확인:
  - `processing error`, `Invalid argument`, `not supported between`, `unsupported operand`, `Traceback`, `verifier_technical_failure` 검색 결과 없음.
- 해석:
  - 일반 세력명 FP 차단과 캐릭터 parenthetical 회수가 같은 3-shard targeted run에서 동시에 통과.
  - 이 targeted는 코드 경로 확인용이므로 품질 승인은 아님.
- 다음 작업:
  - 동일 sampling policy로 200건 canary를 실행해 동명이인 캐릭터 parenthetical FP, confidence type error, generic relation only 누수 재발을 집계.
  - canary 이후 `build_llm_judgment_review_packet.py`로 LLM 정성 리뷰 패킷 생성.

## 2026-04-27 - afterfix11 200건 canary

- 판정: CANARY-GO / RISK-DISCOVERY-REQUIRED
- 입력: `out/sampling/query_gate_canary_200_20260426.jsonl`
- 출력: `out/sampling/query_gate_canary_200_afterfix11_20260427_result.json`
- checkpoint: `out/sampling/query_gate_canary_200_afterfix11_20260427_result_checkpoint.jsonl`
- run summary: `out/sampling/query_gate_canary_200_afterfix11_20260427_run_summary.json`
- audit: `out/sampling/query_gate_canary_200_afterfix11_20260427_audit.json`
- 로그: `logs/expert_run_20260427_191203_030136.log`
- 실행 방식:
  - `expert_main.py` startup shard auto-manage 사용.
  - `MCP_SHARD_COUNT=36`
  - `MCP_CLIENT_MAX_ENDPOINTS_PER_SEARCH=4`
  - `MCP_CLIENT_SEARCH_TIMEOUT_SEC=12`
  - `MCP_CLIENT_SEARCH_MAX_RETRIES=1`
  - `--parallel 8 --no-dashboard --server-type vllm --vlm off --ocr off`
- startup 확인:
  - WARP `36/36`
  - MCP bridge health `36/36`
- 결과:
  - `completed=200/200`, `failed=0`, `pending=0`
  - `Relevant=151`
  - `Identified=75`
  - `Total Time=5508.2s`, `Avg Time/Post=27.5s`
  - `reason_error_count=0`
  - `[Errno 22] Invalid argument=0`
  - `verifier_technical_failure=0`
  - `generic_relation_only_demoted=3`
  - `character_parenthetical_title_resolved=5`
- 감사 요약:
  - `search_timeout=11`
  - `search_upstream_zero=103`
  - `search_degraded_detected=11`
  - `slang old/new/blocked=24/24/0`
  - `slang_db_bad_remaining=0`
- known bad 변화:
  - `11549038`: 오류 없음. afterfix11은 `adjacent_relevant / trope_discussion / work_resolution=none`.
  - `11631298`: late-budget는 `무림맹주 막내제자` resolved였으나 afterfix11은 `is_relevant=false`, title 없음, `generic_relation_only_demoted`.
  - `11663540`: late-budget는 unresolved였으나 afterfix11은 `전 버튜버가 하고 싶은데요` resolved, `character_talk`.
- 비교 산출물:
  - `out/comparisons/query_gate_canary_200_late_budget_vs_afterfix11.md`
  - `out/comparisons/query_gate_canary_200_late_budget_vs_afterfix11.json`
  - late-budget 대비 afterfix11: relevant `153 -> 151`, identified `76 -> 75`, changed posts `91/200`.
- LLM/전문가 정성 리뷰 패킷:
  - `out/llm_judgment_reviews/llm_judgment_review_20260427_191203_030136_afterfix11.md`
  - `out/llm_judgment_reviews/llm_judgment_review_20260427_191203_030136_afterfix11.jsonl`
  - selected `120/200`
- 해석:
  - targeted에서 확인한 두 핵심 회귀는 200건 canary에서도 유지됐다.
  - 다만 `changed=91/200`이고 검색 저하 bucket이 많아 품질 승인은 아직 아님.
- 다음 작업:
  - 리뷰 패킷 120건을 LLM/전문가가 직접 읽고 `ACCEPT/HOLD/RESEARCH/REPROCESS/REJECT`를 채운다.
  - 1,000건 risk discovery에서 `character_parenthetical_title_resolved`의 동명이인 FP와 `generic_relation_only_demoted`의 과차단 여부를 본다.

## 2026-04-27 - afterfix11 120건 정성 adjudication

- 판정: QUALITY-REVIEW / RISK-DISCOVERY-IN-PROGRESS
- 원본 패킷:
  - `out/llm_judgment_reviews/llm_judgment_review_20260427_191203_030136_afterfix11.jsonl`
  - `out/llm_judgment_reviews/llm_judgment_review_20260427_191203_030136_afterfix11.md`
- 판독 산출물:
  - `out/llm_judgment_reviews/llm_judgment_review_20260427_191203_030136_afterfix11_adjudicated.jsonl`
  - `out/llm_judgment_reviews/llm_judgment_review_20260427_191203_030136_afterfix11_adjudicated.md`
  - `out/llm_judgment_reviews/llm_judgment_review_20260427_191203_030136_afterfix11_adjudication_summary.json`
- 판독 집계:
  - `ACCEPT=63`
  - `HOLD=24`
  - `RESEARCH=11`
  - `REPROCESS=15`
  - `REJECT=7`
  - severity: `critical=7`, `major=26`, `minor=24`, `none=63`
- 주요 REJECT:
  - `11718070`: 의학 일반글을 `Depressive disorder` 작품으로 오인.
  - `11689276`: 인물/직업 검색 결과를 작품으로 오인.
  - `11620037`: 나생문/라쇼몽 일반 언급을 잘못된 공식 제목으로 확정.
  - `11512300`: 청부업자 일반론을 `마피아42`로 오인.
  - `11141333`: 포스타입/2D 권리 논의를 `r602 판`으로 오인.
  - `11381533`: 무협 장르사에서 `개파조사` 비유를 특정 작품으로 오인.
  - `11545782`: `최종보스` 일반명사를 작품명으로 확정.
- 해석:
  - `11663540`처럼 캐릭터 parenthetical bridge가 필요한 케이스는 회수됐다.
  - 다만 common term/person/media parenthetical이 작품명으로 승격되는 critical FP가 남아 bridge gate를 더 보수적으로 조정해야 한다.
  - `11631298` generic relation only 차단은 맞지만, `서울마탑`, `망교성`, `폴랩`, `아생갤` 같은 확인된 별칭이 같이 과차단되는 케이스가 있어 alias rescue가 필요하다.
  - multi-work/comparison post는 단일 작품으로 과수렴하거나 noise로 버려지는 경향이 남았다.
- 1,000건 risk discovery 시작:
  - run id: `20260427_212634_728016`
  - 입력: `out/sampling/query_gate_risk_discovery_1000_20260426.jsonl`
  - 출력 예정: `out/sampling/query_gate_risk_discovery_1000_afterfix11_20260427_result.json`
  - 로그: `logs/expert_run_20260427_212634_728016.log`
  - 실행 방식: `expert_main.py` startup shard auto-manage, `MCP_SHARD_COUNT=36`, `parallel=8`, `--server-type vllm --vlm off --ocr off`.
- 다음 작업:
  - 1,000건 완료 후 run audit, known bad/post bucket별 집계, 120건 adjudication에서 나온 REJECT/REPROCESS 유형 재발률 확인.
  - 완료 run에서 새 LLM/전문가 리뷰 패킷을 생성해 `ACCEPT/HOLD/RESEARCH/REPROCESS/REJECT` 분포를 비교.

## 2026-04-27 - afterfix11 1,000건 risk discovery 완료

- 판정: RUN-STABILITY-GO / QUALITY-REVIEW-REQUIRED
- run id: `20260427_212634_728016`
- 입력: `out/sampling/query_gate_risk_discovery_1000_20260426.jsonl`
- 출력: `out/sampling/query_gate_risk_discovery_1000_afterfix11_20260427_result.json`
- checkpoint: `out/sampling/query_gate_risk_discovery_1000_afterfix11_20260427_result_checkpoint.jsonl`
- manifest: `out/sampling/query_gate_risk_discovery_1000_afterfix11_20260427_result_manifest.json`
- audit: `out/sampling/query_gate_risk_discovery_1000_afterfix11_20260427_audit.json`
- 품질 리뷰 요약: `out/comparisons/query_gate_risk_discovery_1000_afterfix11_quality_review.md`
- 전체 리뷰 패킷:
  - `out/llm_judgment_reviews/llm_judgment_review_20260427_212634_728016_risk1000_afterfix11.jsonl`
  - `out/llm_judgment_reviews/llm_judgment_review_20260427_212634_728016_risk1000_afterfix11.md`
  - selected `1000/1000`
- 실행 방식:
  - `expert_main.py` startup shard auto-manage 사용.
  - WARP `36/36`, MCP bridge health `36/36`.
  - `MCP_SHARD_COUNT=36`, `parallel=8`, `--server-type vllm --vlm off --ocr off`.
- 결과:
  - `completed=1000/1000`, `failed=0`, `pending=0`
  - `Relevant=746`
  - `Identified=351`
  - `Total Time=30852.1s`, `Avg Time/Post=30.9s`
  - worker 분배: `120~129`건 범위로 균등
- 감사 요약:
  - `reason_error_count=0`
  - `resolved_title=351`, `adjacent_relevant=302`, `non_relevant=254`, `unresolved_title=93`
  - `work_resolution`: `none=556`, `resolved=351`, `unresolved=63`, `multi_work=30`
  - `avg_executed_queries=6.69`, `p95_executed_queries=13`, `max_executed_queries=19`
  - `search_upstream_zero=539`, `search_degraded_detected=130`, `search_timeout=29`
  - slang old/new/blocked `136/133/3`, `slang_db_bad_remaining=0`
- 위험 신호:
  - `character_parenthetical_title_resolved=37`
  - `generic_relation_only_demoted=8`
  - malformed/generic official title 후보 `14`
  - relevant without official title `395`
- 120건 adjudication overlap:
  - overlap `120/120`
  - 120건 REJECT 중 4건이 1,000건에서도 resolved title로 재현:
    - `11718070 -> Depressive disorder`
    - `11689276 -> 뮤지컬 배우`
    - `11620037 -> 또는 라쇼몽, 아쿠타가와 류노스케`
    - `11512300 -> 마피아42`
  - 120건 REPROCESS 중 10건이 여전히 unresolved/non-relevant/adjacent로 재현:
    - `11702067`, `11679545`, `11626446`, `11615196`, `11576520`, `11562020`, `11540912`, `11383118`, `11327341`, `11185574`
- 해석:
  - 실행 안정성은 통과했다. 1,000건 전체가 실패 없이 flush 됐고 reason/technical error도 없다.
  - 품질은 아직 승인 불가다. character parenthetical bridge가 좋은 회수(`11663540`)와 critical FP를 동시에 만들고 있다.
  - `generic_relation_only_demoted`는 `11631298`에는 맞지만 `서울마탑`, `화귀`, `언니약혼` 같은 strong alias 후보를 과차단한다.
  - 짧은 일반명사/영문 단어/비정상 문자열(`Depressive disorder`, `Sword Master`, `BLACKPINK`, `Truth`, `Cecil`, `rNN 판`, `主人公,2153`, `성장판`)이 official title로 들어가는 validator가 필요하다.
- 다음 작업:
  - character parenthetical bridge를 post/comment 캐릭터 앵커, 도메인 타입, 공식/위키 근거, 비소설/person/common term negative evidence로 재게이트.
  - malformed/generic official title validator 추가.
  - generic guard 이후 confirmed/strong alias rescue 계층 추가.
  - 1,000건 리뷰 패킷에서 `character_parenthetical_title_resolved`, `bad_or_malformed`, `relevant_without_title`, `generic_relation_only_demoted` bucket을 우선 adjudication.

## 2026-04-28 - afterfix12 P0 targeted verification

- 변경 범위:
  - `src/llm_batch/agentic_pipeline.py`
  - `tests/test_agentic_pipeline_rework.py`
- 검증 명령:

```powershell
.venv312\Scripts\python.exe -m py_compile src\llm_batch\agentic_pipeline.py tests\test_agentic_pipeline_rework.py
.venv312\Scripts\python.exe -m unittest tests.test_agentic_pipeline_rework.AgenticPipelineReworkTest.test_generic_relation_only_drops_decoder_title_candidates tests.test_agentic_pipeline_rework.AgenticPipelineReworkTest.test_generic_relation_only_consistency_demotes_short_genre_reaction tests.test_agentic_pipeline_rework.AgenticPipelineReworkTest.test_generic_relation_only_rescues_strong_alias_title tests.test_agentic_pipeline_rework.AgenticPipelineReworkTest.test_final_title_guard_rejects_malformed_revision_title tests.test_agentic_pipeline_rework.AgenticPipelineReworkTest.test_final_title_guard_rejects_nonwork_character_parenthetical_title tests.test_agentic_pipeline_rework.AgenticPipelineReworkTest.test_final_title_guard_rejects_source_metadata_phrase_title tests.test_agentic_pipeline_rework.AgenticPipelineReworkTest.test_character_parenthetical_bridge_rejects_ascii_common_term tests.test_agentic_pipeline_rework.AgenticPipelineReworkTest.test_character_parenthetical_bridge_resolves_final_title tests.test_agentic_pipeline_rework.AgenticPipelineReworkTest.test_search_parenthetical_bridge_resolves_without_registered_link tests.test_agentic_pipeline_rework.OrchestratorBudgetProfileTest.test_community_parenthetical_profile_registers_character_bridge tests.test_agentic_pipeline_rework.OrchestratorBudgetProfileTest.test_character_parenthetical_wiki_hint_registers_work_bridge tests.test_agentic_pipeline_rework.OrchestratorBudgetProfileTest.test_event_parenthetical_wiki_hint_does_not_register_character_bridge tests.test_agentic_pipeline_rework.OrchestratorBudgetProfileTest.test_merge_snippet_hints_rescans_search_results_for_character_parenthetical
```

- 결과:
  - `py_compile`: pass
  - targeted unittest: `13/13 OK`
- 실제 targeted run 1:
  - 입력: `out/sampling/targeted_p0_afterfix12_core4_20260428.jsonl`
  - 출력: `out/sampling/targeted_p0_afterfix12_core4_20260428_result.json`
  - run id: `20260428_123539_845850`
  - `completed=4/4`, `failed=0`, `pending=0`
  - 요약:
    - `11689276`: `뮤지컬 배우` title 제거, `adjacent_relevant/none`.
    - `11631298`: non-relevant/title 없음, `generic_relation_only_demoted`.
    - `11562020`: `서울에 마탑 세웠더니 돈이 미쳤다` resolved, `generic_relation_alias_rescued`.
    - `11620037`: core4 시점에는 `또는 라쇼몽...` source metadata title이 재발해 추가 조임.
- 실제 targeted run 2:
  - 입력: `out/sampling/targeted_p0_afterfix12_rashomon_20260428.jsonl`
  - 출력: `out/sampling/targeted_p0_afterfix12_rashomon_20260428_result.json`
  - run id: `20260428_124339_828427`
  - `11620037`: non-relevant/title 없음으로 수정 확인.
- 판정:
  - P0 targeted gate: `GO`
  - 200/1,000건 확대 gate: `REVIEW`
- 다음 확인:
  - 200건 canary에서 `character_parenthetical_title_resolved` critical FP 재발률 확인.
  - 1,000건 risk discovery에서 `generic_relation_alias_rescued`, `generic_relation_only_demoted`, malformed title 후보를 재집계.

### 2026-04-28 addendum - `11718070` ECT medical false positive

- 문제:
  - afterfix11: `11718070 -> Depressive disorder` resolved title FP.
  - afterfix12 1차: title은 제거됐지만 `adjacent_relevant=True`로 남음.
- 추가 변경:
  - 작품 앵커 없는 ECT/우울증 치료/기억력 문제 등 의학 일반글을 `medical_common_topic_demoted`로 non-relevant 처리.
- 검증:

```powershell
.venv312\Scripts\python.exe -m unittest tests.test_agentic_pipeline_rework.AgenticPipelineReworkTest.test_character_parenthetical_bridge_rejects_ascii_common_term ...
.venv312\Scripts\python.exe expert_main.py --input out\sampling\targeted_p0_afterfix12_ect_20260428.jsonl --output out\sampling\targeted_p0_afterfix12_ect_20260428_result.json --parallel 1 --no-dashboard --vlm off --ocr off --no-auto-up-shards
```

- 결과:
  - targeted unittest 전체 묶음: `13/13 OK`
  - 실제 run id `20260428_132300_821816`
  - `11718070`: `is_relevant=false`, `official_title=null`, `discussion_type=noise`, `topicality=unrelated`, `work_resolution=none`, flag `medical_common_topic_demoted`.

### 2026-04-28 addendum - 하드코딩 방지/일반화 가이드 적용

- 변경:
  - 프롬프트 공통 프레임워크에 "예시는 암기 대상이 아니라 rubric 설명용" 원칙 추가.
  - `CHECKLIST.md`, `OPERATION_QUALITY_CHECKLIST.md`, `FEATURE_IMPROVEMENT_TODO.md`, `DEV_TODO.md`에 일반화/하드코딩 방지 게이트 추가.
  - 최종 title guard의 사례별 bad-title 목록을 줄이고, source metadata/generic surface/real-world health처럼 범주형 규칙으로 정리.
- 검증:

```powershell
.venv312\Scripts\python.exe -m py_compile src\llm_batch\agentic_pipeline.py src\llm_batch\prompts\expert_prompts.py tests\test_agentic_pipeline_rework.py
.venv312\Scripts\python.exe -m unittest tests.test_agentic_pipeline_rework.AgenticPipelineReworkTest.test_generic_relation_only_consistency_demotes_short_genre_reaction tests.test_agentic_pipeline_rework.AgenticPipelineReworkTest.test_generic_relation_only_rescues_strong_alias_title tests.test_agentic_pipeline_rework.AgenticPipelineReworkTest.test_final_title_guard_rejects_malformed_revision_title tests.test_agentic_pipeline_rework.AgenticPipelineReworkTest.test_final_title_guard_rejects_nonwork_character_parenthetical_title tests.test_agentic_pipeline_rework.AgenticPipelineReworkTest.test_final_title_guard_rejects_source_metadata_phrase_title tests.test_agentic_pipeline_rework.AgenticPipelineReworkTest.test_character_parenthetical_bridge_rejects_ascii_common_term tests.test_agentic_pipeline_rework.AgenticPipelineReworkTest.test_character_parenthetical_bridge_resolves_final_title
```

- 결과:
  - `py_compile`: pass
  - targeted unittest: `7/7 OK`
- 판정:
  - 일반화/하드코딩 방지 문서 게이트: `GO`
  - 200/1,000건 확대 재확인: `REVIEW`

## 2026-04-28 - afterfix12 36병렬 canary

- 판정: RUN-STABILITY-GO / QUALITY-REVIEW
- 관련 run id: `20260428_142042_238055`
- 입력: `out/sampling/query_gate_canary_200_20260426.jsonl`
- 출력:
  - result: `out/sampling/query_gate_canary_200_afterfix12_parallel36_retry_20260428_result.json`
  - checkpoint: `out/sampling/query_gate_canary_200_afterfix12_parallel36_retry_20260428_result_checkpoint.jsonl`
  - manifest: `out/sampling/query_gate_canary_200_afterfix12_parallel36_retry_20260428_result_manifest.json`
  - audit: `out/sampling/query_gate_canary_200_afterfix12_parallel36_retry_20260428_audit.json`
- 사전 shard audit:

```powershell
.venv312\Scripts\python.exe tools\audit_search_shards.py --count 36 --timeout 1.5 --output out\search_shard_audit_20260428_before_afterfix12_parallel36.json
```

- 사전 결과:
  - `ok=4/36`
  - bad shards: `[5..36]`
  - 해석: 수동 shard 상태는 불안정했지만, 이번 테스트는 사용자가 제안한 대로 `expert_main.py` startup shard 재정리 경로로 진행.
- startup/status 보정:
  - `tools/warp_shards.py`의 Docker exec trace/status 호출에 subprocess timeout 추가.
  - 검증: `WARP_SHARDS_STATUS_EXEC_TIMEOUT_SEC=5` 상태에서 `warp_shards.py status --json` 정상 반환, `running=36`, `warp_on=36`.
- 실행 명령 요지:

```powershell
$env:MCP_SHARD_COUNT='36'
$env:MCP_AUTO_SHARD_LIMIT='36'
$env:MCP_CLIENT_ENDPOINT_FAILOVER='1'
$env:MCP_CLIENT_MAX_ENDPOINTS_PER_SEARCH='4'
$env:MCP_CLIENT_SEARCH_TIMEOUT_SEC='12'
$env:MCP_CLIENT_SEARCH_MAX_RETRIES='1'
$env:PIPELINE_SEARCH_CONCURRENCY='8'
$env:WARP_SHARDS_STATUS_EXEC_TIMEOUT_SEC='8'
.venv312\Scripts\python.exe expert_main.py --input out\sampling\query_gate_canary_200_20260426.jsonl --output out\sampling\query_gate_canary_200_afterfix12_parallel36_retry_20260428_result.json --parallel 36 --no-dashboard --server-type vllm --vlm off --ocr off
```

- run 결과:
  - startup WARP `36/36`, MCP bridge health `36/36`
  - `completed=200/200`, `failed=0`, `pending=0`
  - `Relevant=146`
  - `Identified=67`
  - `Total Time=2473.3s`, `Avg Time/Post=12.4s`
  - search cache: requests `1138`, real searches `1136`, cache entries `1017`
- 감사 결과:
  - `checkpoint_rows=200`
  - `reason_errors=0`
  - `slang old/new/blocked=26/25/1`
  - `slang_db_bad_remaining=0`
  - log counts: `search_upstream_zero=105`, `search_degraded_detected=12`, `search_timeout=8`
  - headless: `headless_naver_playwright=45`, `headless_google_cloak=3`
- 사후 shard audit:

```powershell
.venv312\Scripts\python.exe tools\audit_search_shards.py --count 36 --timeout 1.5 --output out\search_shard_audit_20260428_after_afterfix12_parallel36_retry.json
```

- 사후 결과:
  - `ok=36/36`
  - `bad=[]`
- 일반화/이웃 케이스 결과:
  - `11718070`: `Depressive disorder` FP 제거, `is_relevant=false`, title 없음, `medical_common_topic_demoted`.
  - `11631298`: 일반 무협 세력어 케이스 non-relevant/title 없음 유지.
  - `11663540`: `전 버튜버가 하고 싶은데요` resolved 유지.
  - `11620037`: source metadata title 제거, non-relevant/title 없음.
  - `11562020`: `서울에 마탑 세웠더니 돈이 미쳤다` resolved로 alias rescue 확인.
  - `11702067`, `11576520`: relevant 유지지만 title 미확정. strong alias long-tail 후보.
- 비교 산출물:
  - `out/comparisons/query_gate_canary_200_afterfix11_vs_afterfix12_parallel36_20260428.md`
  - afterfix11 -> afterfix12 parallel36: relevant `151 -> 146`, identified `75 -> 67`, resolved_title `75 -> 67`
  - 해석: 약한 common/topic title hallucination을 내리면서 identified가 감소했고, 남은 alias FN은 별도 개선 대상.
- LLM/전문가 리뷰 패킷:
  - `out/llm_judgment_reviews/llm_judgment_review_20260428_142042_238055_afterfix12_parallel36.md`
  - `out/llm_judgment_reviews/llm_judgment_review_20260428_142042_238055_afterfix12_parallel36.jsonl`
  - `selected=120/200`
  - 주요 risk tags: `search_degraded_majority=101`, `slang_insight=48`, `relevant_without_official_title=34`, `unresolved_or_ambiguous_work=18`
- 판정:
  - 실행 안정성: `GO`
  - shard 안정성: `GO`
  - 일반화 매트릭스: `PARTIAL-GO`
  - 품질 승인: `REVIEW`
- 다음 확인:
  - 120건 리뷰 패킷 실제 판독.
  - afterfix12 1,000건 risk discovery.
  - audit 도구가 sampling output 경로를 직접 받도록 개선.

## 2026-04-28 - afterfix14 Namu medical/common concept title guard

- 상태: targeted-verified / canary-required
- 발견 사례:
  - 대형 run 중 `11718111`이 `조현병`으로 resolved 됨.
  - 이전 결과 `out/expert_result_20260428_223800_568267_checkpoint.jsonl`에서는 `official_title=조현병`, `heretic_url=namu.wiki/w/조현병`, flags `character_parenthetical_title_resolved`, `weak_llm_only_title_replaced_by_url_backed_candidate`.
- 원인:
  - `조현병(정신분열병)` 같은 나무위키 일반 의학 항목이 `캐릭터명(작품명)` 패턴으로 해석됨.
  - 본문에 `웹소설` 단어가 있다는 이유로 일반 개념어 가드가 약해짐.
  - 마지막 URL-backed replacement가 나무위키 일반 개념 URL을 약한 LLM title보다 강한 근거로 승격.
- 조치:
  - post id/제목 직접 차단이 아니라 `medical_common_topic_title` 범주 가드를 추가.
  - 작품 고유 앵커, 공식 플랫폼 detail URL, 안정 alias, verified character-work bridge가 없으면 의학/현실 개념어 title 후보를 hard reject.
  - character-parenthetical link 추출과 URL-backed replacement 양쪽에서 같은 rejection profile을 재사용.
  - 나무위키 URL은 작품형 후보일 때만 fallback 근거로 두고, 의학/일반 개념 표면어는 승격하지 않음.
- 자동 테스트:
  - targeted 5건: `OK`
  - `tests.test_agentic_pipeline_rework`: `147 OK`
  - `tests.test_agentic_pipeline_alias_contract`: `30 OK`
  - `py_compile`: pass
- 실제 targeted run:
  - 입력: `out/sampling/targeted_medical_common_11718111_afterfix14_20260428.jsonl`
  - 출력: `out/sampling/targeted_medical_common_11718111_afterfix14_20260428_result.json`
  - run id: `20260428_230857_637381`
  - 결과: `11718111`은 `is_relevant=false`, official title 없음, `discussion_type=noise`, `topicality=unrelated`, `work_resolution=none`, flag `medical_common_topic_demoted`.
- 판정:
  - targeted gate: `GO`
  - 200/1,000건 품질 gate: `REVIEW`
- 다음 확인:
  - afterfix14 200건 canary에서 Namu common concept title 재발률 확인.
  - 1,000건 risk discovery에서 `medical_common_topic_demoted` 과차단과 실제 의료 소재 웹소설 positive 이웃을 함께 리뷰.

## 2026-04-29 - afterfix14 200건 canary 및 1,001건 risk discovery

- 판정: RUN-STABILITY-GO / QUALITY-REVIEW
- 실행 정책:
  - 품질 개선 후 200건 canary를 먼저 실행.
  - canary가 `completed=200/200`, `failed=0`, `pending=0`이라 1,000건 risk discovery를 이어서 실행.
  - `11718111` 조현병/정신질환 타깃을 risk discovery 입력 끝에 추가하여 총 1,001건으로 검증.
- 200건 canary:
  - run id: `20260428_233059_378617`
  - 입력: `out/sampling/query_gate_canary_200_20260426.jsonl`
  - 출력: `out/sampling/query_gate_canary_200_afterfix14_20260428_result.json`
  - audit: `out/sampling/query_gate_canary_200_afterfix14_20260428_audit.json`
  - 결과: `completed=200/200`, `failed=0`, `pending=0`, `Relevant=70`, `Identified=61`
  - audit 핵심: `reason_errors=0`, `slang_db_bad_remaining=0`, `search_timeout=9`, `search_degraded_detected=23`
- 1,001건 risk discovery:
  - run id: `20260429_002511_375830`
  - 입력: `out/sampling/query_gate_risk_discovery_1000_plus11718111_afterfix14_20260429.jsonl`
  - 출력: `out/sampling/query_gate_risk_discovery_1000_plus11718111_afterfix14_20260429_result.json`
  - audit: `out/sampling/query_gate_risk_discovery_1000_plus11718111_afterfix14_20260429_audit.json`
  - 사전 shard audit: `out/search_shard_audit_20260429_before_afterfix14_risk1000.json`
  - 사후 shard audit: `out/search_shard_audit_20260429_after_afterfix14_risk1000.json`
  - 리뷰 패킷: `out/llm_judgment_reviews/llm_judgment_review_20260429_002511_375830_risk1000_afterfix14.md`
  - 비교/리뷰 요약: `out/comparisons/query_gate_afterfix14_validation_review_20260429.md`
  - 결과: `completed=1001/1001`, `failed=0`, `pending=0`, `Relevant=381`, `Identified=297`
  - runtime: `Total Time=13487.3s`, `Avg Time/Post=13.5s`
  - search cache: requests `6057`, real searches `5996`, cache entries `5091`
  - audit 핵심: `reason_errors=0`, `slang old/new/blocked=88/85/3`, `slang_db_bad_remaining=0`, `search_timeout=4`, `search_degraded_detected=173`
  - shard audit: 사전/사후 모두 `ok=36/36`, `bad=[]`
- 확인된 개선:
  - `11718070` ECT 의학 일반글: `is_relevant=false`, official title 없음, `discussion_type=noise`, `topicality=unrelated`.
  - `11631298` 무림맹/마교/혈교 일반 세력어: `is_relevant=false`, official title 없음.
  - `11456200` 마법소녀ㄴ/폼체인지 검색 이웃: canary의 `포켓몬스터` 오탐에서 risk discovery는 `is_relevant=false`, official title 없음.
  - `11616838`, `11198715`: `마법소녀ㄴ은 은퇴하고 싶다` positive stem 사례 resolved 유지.
  - `11663540`: `전 버튜버가 하고 싶은데요` resolved 유지.
  - `11066247`: 00년대 애니/캐릭터 다중 언급은 `adjacent_relevant`, official title 없음.
- 잔존 위험:
  - `11718111`은 targeted run에서는 차단됐지만, risk discovery에서는 `official_title=정신과 의사`로 재발. `조현병` 직접 title만이 아니라 현실 의학/직업 명사와 플랫폼 URL-backed title 승격 전반으로 guard를 확장해야 함.
  - `11684415`은 `기계공주` 글에서 일반어 `소수`가 `小數, decimal number`로 승격. reason 내부에는 `official_title_evidence=false`, `evidence_bucket=post_spans=0, search_snippets=0, official_urls=0`가 기록되어 있어 후처리 스코어가 반론을 이긴 사례.
  - `11505857`은 `세실` 인명/캐릭터 표면이 `Cecil` title로 승격. 본문은 `ㄹㅇ`뿐이라 character/person/title 구분이 더 필요.
  - 약한 근거 official title 후보 35건을 별도 리뷰 대상으로 추출.
- 판정:
  - 실행 안정성: `GO`
  - shard 안정성: `GO`
  - 기존 ECT/무림맹/마법소녀ㄴ 일부 회귀: `PARTIAL-GO`
  - 품질 승인: `REVIEW`
- 다음 작업:
  - weak-evidence official title 승격 제한을 별도 개선 항목으로 분리.
  - `official_title_evidence=false` 또는 `post_spans=0/search_snippets=0/official_urls=0`인데 resolved되는 케이스를 HOLD/REPROCESS 큐로 보냄.
  - `정신과 의사`, `小數`, `Cecil`, `추리 소설`, `챌린지` 같은 직업/일반어/인명/장르명 positive/negative 이웃 테스트 추가.

## 2026-04-29 - afterfix15~17 weak evidence / broad alias guard 검증

- 판정: 200-CANARY-GO / 1000-RISK-HOLD
- 구현 요약:
  - `weak_evidence_literal_topic_title`, `dictionary_or_gloss_title` 범주 가드 추가.
  - 현실 의학/일상 키워드가 검색어와만 겹치는 unresolved core 사례를 `unresolved_nonwork_overlap_demoted`로 정리.
  - locked official detail 후보라도 넓은 alias/장르 stem이며 캐릭터명이 후보 작품과 직접 연결되지 않으면 `locked_official_candidate_broad_alias_hold`로 resolved 승격 보류.
- 단위 검증:
  - `python -m compileall -q src\llm_batch\agentic_pipeline.py tests\test_agentic_pipeline_rework.py`: pass.
  - `tests.test_agentic_pipeline_rework`: `153 OK`.
- targeted 검증:
  - `11718111` 조현병/의학 일반글: `out/sampling/targeted_medical_common_11718111_afterfix16_20260429_result.json`, `Relevant=0`, `Identified=0`.
  - `11198715` 마법소녀ㄴ broad alias 단건: `out/sampling/targeted_magicgirl_11198715_afterfix17_20260429_result.json`, 잘못된 `마법소녀물 신전사가 되었다` resolved는 사라졌으나 현재는 `Relevant=0`으로 과보수 판정됨.
- 200건 canary:
  - run id: `20260429_175638_261091`
  - 입력: `out/sampling/query_gate_canary_200_20260426.jsonl`
  - 출력: `out/sampling/query_gate_canary_200_afterfix16_20260429_result.json`
  - audit: `out/sampling/query_gate_canary_200_afterfix16_20260429_audit.json`
  - 결과: `completed=200/200`, `failed=0`, `pending=0`, `Relevant=77`, `Identified=64`, runtime `2959.6s`, avg `14.8s/post`.
  - audit 핵심: `reason_errors=0`, `slang_db_bad_remaining=0`, `search_degraded_detected=17`, `search_upstream_zero=60`, `search_bridge_after_filter_zero=47`.
- 사례 확인:
  - `11718070` ECT: non-relevant/title 없음 유지.
  - `11663540` 주서연: `전 버튜버가 하고 싶은데요` resolved 유지.
  - `11631298` 무림맹 일반 세력어: non-relevant/title 없음 유지.
  - `11549038` 이전 `[Errno 22] Invalid argument`: canary에서 정상 처리, non-relevant/title 없음.
  - `11198715` 마법소녀ㄴ: afterfix16 canary에서는 잘못된 `마법소녀물 신전사가 되었다` resolved가 재발했고, afterfix17 targeted에서는 title 오매칭은 제거됐지만 관련성까지 false로 내려감.
- 잔존 위험:
  - `11198715`류는 비관련으로 버릴 사례가 아니라, 캐릭터/설정 단서가 강한 경우 `관련-미확정` 또는 정확한 후보 재검색으로 보내야 함.
  - `마법소녀ㄴ`처럼 작가가 의도적으로 오타/자모를 제목에 포함한 작품군은 일반 장르어와 official detail 후보가 충돌하므로, alias stem + body predicate bridge를 별도 positive 이웃으로 관리해야 함.
- 다음 작업:
  - 1,000건 risk discovery는 afterfix17 broad-alias 과보수 문제를 `관련-미확정 HOLD`로 안정화한 뒤 실행.
  - `세린/세진/계약/은퇴` 같은 본문 고유 단서가 있을 때는 generic trope demotion보다 unresolved work hold가 우선되도록 테스트 추가.

## 2026-04-29 - afterfix18~19 internal work signal unresolved HOLD

- 판정: TARGETED-GO / 200-CANARY-REQUIRED / 1000-RISK-HOLD
- 구현 요약:
  - `internal_work_signal_unresolved_recovered` consistency guard 추가.
  - Gatekeeper/Discourse가 작품 토론으로 보고, 본문에 복수 캐릭터 + 설정/전개 단서가 있지만 broad alias stem 때문에 단일 공식 제목이 위험한 경우 `core_relevant + unresolved_work`로 유지.
  - 같은 HOLD 신호가 있으면 뒤쪽 `locked_official_candidate_rescue`도 title 확정 대신 보류.
  - 단일 캐릭터/장르 클리셰만 있는 이웃은 rescue하지 않도록 negative 조건 유지.
- 단위 검증:
  - `.venv312\Scripts\python.exe -m py_compile src\llm_batch\agentic_pipeline.py tests\test_agentic_pipeline_rework.py`: pass.
  - `.venv312\Scripts\python.exe -m unittest tests.test_agentic_pipeline_rework -v`: `155 OK`.
- targeted 검증:
  - afterfix18 단건 `out/sampling/targeted_magicgirl_11198715_afterfix18_20260429_result.json`: `Relevant=1`, `Identified=1`으로 비관련은 복구됐지만 locked official rescue가 `마법소녀ㄴ은 은퇴하고 싶다`를 다시 resolved하여 목표 불충족.
  - afterfix19 단건 `out/sampling/targeted_magicgirl_11198715_afterfix19_20260429_result.json`: `Relevant=1`, `Identified=0`, `official_title=null`, `discussion_type=character_talk`, flags에 `internal_work_signal_unresolved_recovered`.
- 사례 판정:
  - `11198715`: 오답 resolved 없이 관련-미확정으로 유지.
  - `11456200` negative 이웃: 단위 테스트에서 단일 캐릭터/폼체인지 클리셰만으로는 rescue하지 않음.
- 다음 작업:
  - afterfix19 기준 200건 canary 실행.
  - canary가 `completed=200/200`, `failed=0`, `pending=0`이면 1,000건 risk discovery로 확대.
  - canary에서 `11198715`, `11456200`, `11718070`, `11718111`, `11631298`, `11663540` known bad/positive 이웃을 별도 점검.

## 2026-04-30 - afterfix19 canary/risk 및 afterfix20 locked candidate metadata guard

- 판정: afterfix19 200-CANARY-GO / afterfix19 1000-RISK-REVIEW / afterfix20 200-CANARY-GO / afterfix20 1000-RISK-REVIEW
- afterfix19 200건 canary:
  - run id: `20260429_204443_104695`
  - 입력: `out/sampling/query_gate_canary_200_20260426.jsonl`
  - 출력: `out/sampling/query_gate_canary_200_afterfix19_20260429_result.json`
  - audit: `out/sampling/query_gate_canary_200_afterfix19_20260429_audit.json`
  - 결과: `completed=200/200`, `failed=0`, `Relevant=73`, `Identified=54`, runtime `2849.2s`, avg `14.2s/post`.
  - audit 핵심: `reason_errors=0`, `slang old/new/blocked=17/16/1`, `slang_db_bad_remaining=0`, `search_degraded_detected=20`, `search_upstream_zero=61`, `search_bridge_after_filter_zero=43`.
- afterfix19 1,001건 risk discovery:
  - run id: `20260429_213837_418990`
  - 입력: `out/sampling/query_gate_risk_discovery_1000_plus11718111_afterfix14_20260429.jsonl`
  - 출력: `out/sampling/query_gate_risk_discovery_1000_plus11718111_afterfix19_20260429_result.json`
  - audit: `out/sampling/query_gate_risk_discovery_1000_plus11718111_afterfix19_20260429_audit.json`
  - 결과: `completed=1001/1001`, `failed=0`, `Relevant=401`, `Identified=284`, runtime `15068.3s`.
  - audit 핵심: `reason_errors=0`, `slang old/new/blocked=95/91/4`, `slang_db_bad_remaining=0`, `search_degraded_detected=160`, `search_upstream_zero=387`, `search_bridge_after_filter_zero=402`.
- afterfix19 개선 확인:
  - `11718070` ECT: `is_relevant=false`, official title 없음, flag `medical_common_topic_demoted`.
  - `11718111` 조현병: `is_relevant=false`, official title 없음, flags `generic_relation_only_demoted`, `medical_common_topic_demoted`.
  - `11198715`: `is_relevant=true`, official title 없음, `work_resolution=unresolved`, flag `internal_work_signal_unresolved_recovered`.
  - `11456200`: official title 없음, negative 이웃 유지.
  - `11549038`, `11505857`, `11205227`: title 없음.
- afterfix19에서 새로 확인한 위험:
  - `11631298`가 risk discovery에서 `무림맹주 막내제자`로 재승격. 원인은 locked official candidate가 `page_type=community_post`, `content_status=deleted`, `negative_evidence=url_is_community_post/url_deleted_or_unavailable`인데도 rescue된 것.
  - `11663540`은 검색/판정 변동에 따라 `전 버튜버가 하고 싶은데요` resolved와 unresolved/non-relevant가 흔들림. 캐릭터 괄호형 bridge가 검색 결과에 없을 때 recall 손실이 생긴다.
- afterfix20 조치:
  - locked official candidate rescue에서 `community_post`, `deleted/unavailable`, `url_deleted_or_unavailable`, `url_is_community_post`, `listing_only`, `title_url_mismatch` 음성 메타가 있는 후보를 제외.
  - 단어별 차단이 아니라 page/content/evidence metadata invariant로 일반화.
- afterfix20 단위/targeted 검증:
  - `.venv312\Scripts\python.exe -m py_compile src\llm_batch\agentic_pipeline.py tests\test_agentic_pipeline_rework.py`: pass.
  - `.venv312\Scripts\python.exe -m unittest tests.test_agentic_pipeline_rework -v`: `157 OK`.
  - targeted run id: `20260430_015935_598854`
  - 입력: `out/sampling/targeted_weak_official_title_afterfix15_20260429.jsonl`
  - 출력: `out/sampling/targeted_weak_official_title_afterfix20_20260430_result.json`
  - 결과: `completed=5/5`, `Relevant=2`, `Identified=2`.
  - `11631298`: `is_relevant=false`, official title 없음, flags `generic_relation_only_demoted`, `primary_work_cleared_non_core`.
  - `11684415`: `헌터갤러리의 국가권력급 기계공주` resolved 유지.
  - `11456200`: adjacent/trope, official title 없음.
  - `11663540`: targeted afterfix20에서는 non-relevant로 흔들림. 다음 개선 후보.
  - `11616838`: `마법소녀ㄴ은 은퇴하고 싶다` resolved. `11198715` unresolved 정책과 함께 positive/negative 경계를 risk 표본에서 계속 점검.
- afterfix20 200건 canary:
  - run id: `20260430_021001_693350`
  - 출력: `out/sampling/query_gate_canary_200_afterfix20_20260430_result.json`
  - audit: `out/sampling/query_gate_canary_200_afterfix20_20260430_audit.json`
  - 결과: `completed=200/200`, `failed=0`, `Relevant=73`, `Identified=57`, runtime `2674.2s`.
  - audit 핵심: `reason_errors=0`, `slang old/new/blocked=15/14/1`, `slang_db_bad_remaining=0`, `search_degraded_detected=22`, `search_upstream_zero=66`, `search_bridge_after_filter_zero=32`.
  - known-case: `11718070` title 없음, `11631298` title 없음, `11663540 -> 전 버튜버가 하고 싶은데요`, `11456200` title 없음, `11198715` 관련-미확정.
- afterfix20 1,001건 risk discovery:
  - run id: `20260430_025849_885589`
  - 출력: `out/sampling/query_gate_risk_discovery_1000_plus11718111_afterfix20_20260430_result.json`
  - audit: `out/sampling/query_gate_risk_discovery_1000_plus11718111_afterfix20_20260430_audit.json`
  - 결과: `completed=1001/1001`, `failed=0`, `Relevant=382`, `Identified=277`, runtime `14816.5s`.
  - audit 핵심: `reason_errors=0`, `slang old/new/blocked=93/90/3`, `slang_db_bad_remaining=0`, `search_degraded_detected=174`, `search_upstream_zero=400`, `search_bridge_after_filter_zero=530`, worker log start/complete `1001/1001`.
  - known-case 개선 유지: `11718070` title 없음, `11718111` title 없음, `11631298` title 없음, `11663540 -> 전 버튜버가 하고 싶은데요`, `11616838` 관련-미확정, `11198715` 관련-미확정, `11205227` title 없음.
  - 새/잔존 위험: `11505857 -> Cecil` 재발, `11456200`이 title은 없지만 `is_relevant=true + unresolved`로 과복구.
- 다음 작업:
  - `Cecil`류 짧은 인명/캐릭터 표면이 영문 title로 승격하는 character-parenthetical false bridge를 next P1로 분리.
  - `11456200`류 단일 캐릭터 + 장르/트로프 일반론이 internal work signal로 과복구되는 조건을 축소.
  - afterfix20은 실행 안정성 `GO`, 품질 승인은 residual FP 때문에 `REVIEW`.

## 2026-04-30 - afterfix21 short person bridge / trope-only recovery guard

- 판정: 200-CANARY-GO / 1000-RISK-REVIEW
- 구현 요약:
  - character-parenthetical bridge에서 짧은 영어 인명형 title은 게시글 본문에 작품/회차/설정/캐릭터 등 post-side work anchor가 없으면 resolved title로 승격하지 않음.
  - `Cecil` 문자열을 직접 금지하지 않고 `short ascii personlike title + weak post work anchor` 구조 조건으로 일반화.
  - internal work signal에서 `폼체인지/변신/의상/추가파츠/마법소녀` 같은 trope-only 표면은 강한 plot term이 없으면 전문가 내부 신호가 있어도 `core_relevant + unresolved`로 과복구하지 않음.
  - `승급`을 강한 plot term에 추가해 `11616838` 같은 positive 이웃은 보존.
- 단위 검증:
  - `.venv312\Scripts\python.exe -m py_compile src\llm_batch\agentic_pipeline.py tests\test_agentic_pipeline_rework.py`: pass.
  - `.venv312\Scripts\python.exe -m unittest tests.test_agentic_pipeline_rework -v`: `159 OK`.
- targeted 검증:
  - run id: `20260430_120419_466550`
  - 입력: `out/sampling/targeted_short_person_trope_afterfix21_20260430.jsonl`
  - 출력: `out/sampling/targeted_short_person_trope_afterfix21_20260430_result.json`
  - 결과: `completed=5/5`, `Relevant=3`, `Identified=2`.
  - `11505857`: `is_relevant=false`, official title 없음.
  - `11456200`: `is_relevant=false`, official title 없음.
  - `11663540`: `전 버튜버가 하고 싶은데요` resolved 유지.
  - `11616838`: 관련-미확정 유지.
  - 참고: targeted 단건에서는 `11198715`이 검색 강도에 따라 `마법소녀ㄴ은 은퇴하고 싶다`로 resolved된 변동이 있었으나, canary/risk에서는 관련-미확정으로 닫힘.
- afterfix21 200건 canary:
  - run id: `20260430_121717_430655`
  - 출력: `out/sampling/query_gate_canary_200_afterfix21_20260430_result.json`
  - audit: `out/sampling/query_gate_canary_200_afterfix21_20260430_audit.json`
  - 결과: `completed=200/200`, `failed=0`, `pending=0`, `Relevant=82`, `Identified=65`, runtime `3241.9s`, avg `16.2s/post`.
  - audit 핵심: `reason_errors=0`, `slang old/new/blocked=19/18/1`, `slang_db_bad_remaining=0`, `search_degraded_detected=25`, `search_upstream_zero=68`, `search_bridge_after_filter_zero=70`.
  - known-case: `11456200` title 없음, `11549038` 처리 오류 없음, `11663540 -> 전 버튜버가 하고 싶은데요`, `11198715` 관련-미확정.
- afterfix21 1,001건 risk discovery:
  - run id: `20260430_131615_234022`
  - 출력: `out/sampling/query_gate_risk_discovery_1000_plus11718111_afterfix21_20260430_result.json`
  - audit: `out/sampling/query_gate_risk_discovery_1000_plus11718111_afterfix21_20260430_audit.json`
  - 결과: `completed=1001/1001`, `failed=0`, `pending=0`, `Relevant=396`, `Identified=308`.
  - audit 핵심: `reason_errors=0`, `slang old/new/blocked=120/118/2`, `slang_db_bad_remaining=0`, `search_degraded_detected=163`, `search_upstream_zero=436`, `search_bridge_after_filter_zero=434`.
  - known-case 개선 유지: `11505857` title 없음, `11456200` title 없음, `11718070` title 없음, `11718111` title 없음, `11631298` title 없음, `11663540 -> 전 버튜버가 하고 싶은데요`, `11198715` 관련-미확정, `11616838` 관련-미확정.
- 잔존 위험:
  - afterfix20 대비 risk `Identified`가 `277 -> 308`, `Relevant`가 `382 -> 396`으로 증가했으므로 recall 개선인지 false positive 증가인지 정성 리뷰가 필요.
  - 검색 bridge filter zero는 `530 -> 434`로 개선됐지만 upstream zero는 `400 -> 436`으로 증가.
  - 다음 라운드는 afterfix21 risk에서 새 resolved 저근거 상위 표본을 뽑아 `ACCEPT/HOLD/REPROCESS/REJECT`로 판독.
