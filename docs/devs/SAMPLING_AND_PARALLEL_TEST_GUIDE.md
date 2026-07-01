# Sampling And Parallel Test Guide

## 2026-05-31 v408 goal/test runtime and semantic permit refresh

- 이 문서의 `parallel`, `worker`, `shard`는 `expert_main.py` 런타임 병렬도만 뜻한다. Codex goal 수행 중 `spawn_agent` subagent 병렬 운영은 `docs/devs/SCAN_RESULT_REVIEW_GUIDE.md`의 Codex goal 전문 subagent 병렬 운영 항목을 따른다.
- 사용자가 goal 작업에서 "여러 전문가", "subagent", "병렬 검토"를 말한 경우 이 문서의 worker/parallel 값을 조정하는 것으로 대응하지 않는다. 먼저 Codex `spawn_agent` 전문가 축을 선언하고 실제 subagent를 배정한다.
- subagent 검토가 부족한 문제는 Codex `spawn_agent` 분해 축을 보강해서 풀고, 처리 속도/샤드 포화/endpoint health 문제는 `expert_main.py` runtime 병렬도와 manifest/log로 따로 판단한다.
- 10만 건/대량 품질검토에서는 Codex goal의 메인 에이전트가 통합/결정권을 갖고, `runtime/shard`, `VLM/OCR/browser`, `semantic/prompt`, `docs/checklist/gate`처럼 다른 전문 subagent를 병렬로 배정하는 방식을 권장한다.
- subagent 결과는 실행 결과가 아니라 검토 입력이다. 메인 에이전트가 파일 경로, line, `post_id`, `run_id`, manifest/checkpoint/review packet 근거를 재확인한 뒤에만 random baseline과 high-risk oversample gate에 반영한다.
- random baseline과 high-risk oversample은 표본 수, 오류율, HOLD/REPROCESS/REJECT 집계를 계속 분리 보고한다.
- 브라우저/VLM 사례는 이미지 로딩 상태와 직접 시각 증거를 별도 gate로 보고, OCR/text match만으로 semantic approval을 열지 않는다.
- `expert_main.py --parallel 36`은 Gemma 4 4B 운영 기준의 최대치로 쓴다. 10건 미만/소량 입력에서 worker 36개를 강제로 맞추려고 재실행하지 않는다.
- Gemma 4 E4B/4B 계열 manifest/run_meta는 `requested_parallel_raw`, cap 이후 `requested_parallel`, `model_parallel_max=36`, `model_parallel_cap_applied`, `effective_parallel`을 분리해서 남긴다.
- cap 계약을 검증해야 할 때는 v454처럼 의도적으로 `--parallel 64`를 넣은 focused canary를 한 번 실행할 수 있다. 기대값은 `requested_parallel_raw=64`, `requested_parallel=36`, small input이면 `effective_parallel=input_count`다.
- v454 확인 산출물: `qualitative_review\20260528_141006_620986\v454_post11718080_11718082_model_cap_reason_contract_result_manifest.json`, audit `v454_goal_test_run_contract_audit.json`, run id `20260601_042151_464777`.
- cap canary 예시는 runtime 계약 검증용이다. v454/v458처럼 runtime `GO`가 나와도 Browser visual 캡처를 새로 수행하지 않았다면 이미지 row semantic approval은 여전히 `REVIEW-LOCKED`다.
- small input에서는 manifest/run_meta의 `effective_parallel`이 입력 수 또는 healthy endpoint 수에 맞게 낮아지는 것이 정상이다.
- 잔여 action 입력 패키지나 실행 템플릿은 현재 입력 수 기준 권장 `--parallel min(input_count,36)`를 표시한다. `MCP_SHARD_COUNT=36`은 소규모 reuse-only goal/test의 필수 env가 아니며, large run 또는 명시 shard audit에서만 별도로 둔다.
- 이미 `--parallel 36`으로 완료된 소규모 run은 manifest의 `effective_parallel`, lifecycle flags, health/audit contract가 맞으면 worker 수를 맞추려고 재실행하지 않는다. 재실행은 semantic bug, evidence gap, manifest contract gap처럼 명확한 검증 목적이 있을 때만 한다.
- goal/test run에서 Docker Compose/shard lifecycle은 기본 금지다. shard 복구 자체가 검증 대상일 때만 `--allow-goal-shard-lifecycle --auto-up-shards` 또는 `--allow-goal-shard-lifecycle --auto-recreate-shards`를 명시한다.
- v491 이후 소규모 goal/test run 감사는 `mcp_health_include_search=false`, `mcp_health_light_mode=true`, `mcp_health_checked_endpoint_count`, `mcp_health_required_ok_count`, `mcp_health_probe_batch_size`, `mcp_health_workers`, `mcp_health_attempts`, `mcp_health_timeout_sec`를 함께 확인한다. 이 필드가 manifest에 없으면 runtime `REVIEW`, `mcp_health_include_search=true`도 runtime `REVIEW`, health count 모순은 `NO-GO`다.
- semantic regression은 VLM/OCR on 기준이다. 이미지 row가 있으면 `--vlm on --ocr on`을 명시하고, 빠졌다면 결과를 자연어 품질 승인 근거로 쓰지 않는다.
- 11718080류 한탄/잡담/친구 얘기 글은 검색 seed가 만들어져도 바로 작품 resolved로 승격하지 않는다. 검색 전 `intent_permit_for_title_search` 또는 동등한 intent permit이 필요하다.
- `search_only` evidence는 weak로 남긴다. `community_banter`, `trope_discussion`, `author_talk`, `recommendation` intent에서는 직접 작품 앵커 없이 `resolved_title`을 확정하지 않는다.
- comment author/IP/context는 대화 흐름 힌트다. 독립 작품 evidence로 승격하지 않는다.

## 2026-05-31 v391 goal/test audit auto log discovery

- `tools\audit_goal_test_run_contract.py`는 `--log`를 생략하면 manifest의 `run_id`로 `logs\expert_run_<run_id>.log`와 worker log를 자동 탐색한다.
- 자동 탐색으로도 로그가 없으면 `runtime_contract=REVIEW`와 `log_evidence_missing`을 남긴다. 이 경우 Docker/shard lifecycle log hit가 없었다고 증명할 수 없으므로 완료 보고에서 로그를 보강한다.
- 명시 로그를 쓰려면 기존처럼 `--log <expert_run.log>`를 붙인다. worker log를 제외하려면 `--skip-worker-logs`를 사용한다.
- v391 확인: v381 manifest만 넘긴 감사에서 `auto_discovered_logs=true`, `log_evidence_present=true`, `runtime_contract=GO`가 나왔다.

## 2026-05-31 v390 post-run goal/test contract audit

- 소규모 goal/test regression을 실행한 뒤에는 manifest와 log를 `tools\audit_goal_test_run_contract.py`로 감사한다.
- 기본 명령:
  `.\venv\Scripts\python.exe tools\audit_goal_test_run_contract.py --manifest <result_manifest.json> --log <expert_run.log> --output-json <audit.json> --output-md <audit_ko.md> --fail-on-no-go`
- 이 감사는 `requested_parallel=36`이 max로만 쓰였는지, `effective_parallel`이 `input_post_count` 또는 healthy endpoint 수로 낮아졌는지, Docker Compose/shard lifecycle log hit가 없는지, health check가 light mode인지, 이미지 row에서 VLM/OCR ready가 맞는지 확인한다.
- `runtime_contract=GO`는 런타임 계약만 통과했다는 뜻이다. 자연어 판정 품질 승인이나 10만 semantic approval로 쓰지 않는다.
- v390 확인: `v381_post11718096_current_clean_canary_result_manifest.json` + `expert_run_20260531_142901_117227.log` 감사에서 `requested_parallel=36`, `effective_parallel=1`, lifecycle flags false, VLM/OCR ready true, forbidden log hit 0, `runtime_contract=GO`였다.

## 2026-05-31 v372 targeted run log mode

- Gemma 4 4B 기준 최대 worker cap은 `36`이지만, 소규모 goal/test regression 명령 템플릿은 실제 입력 수 기준 `--parallel min(input_count, 36)` 값을 적는다. 본체도 `effective_parallel`을 입력 수/healthy endpoint 수로 낮추지만, 10건 미만 재테스트를 36 worker로 맞추려고 재실행하지 않는다.
- 예: 입력 1건이면 `--parallel 1`, 입력 4건이면 `--parallel 4`, 대형/배치 검증이면 `--parallel 36`을 사용한다. 공통 옵션은 `--reuse-shards-only --no-dashboard --slang-db on --vlm on --ocr on`이다.
- `--parallel 36`은 최대치이며, 단건 입력에서는 `effective_parallel=1`이 정상이다.
- targeted run 로그에서 Slang DB seed preload가 너무 길면 기본 `PIPELINE_BATCHMEM_SEED_LOG_MODE=summary`를 유지한다.
- per-alias seed preload 로그가 꼭 필요할 때만 `PIPELINE_BATCHMEM_SEED_LOG_MODE=full`을 임시로 사용한다.
- `BatchMem seed preload summary`가 보였더라도 semantic 품질 승인은 별도 reason/evidence scan과 정성 리뷰를 통과해야 한다.

## 2026-05-30 v269 goal/test preflight와 endpoint cap

- `--parallel 36`은 worker 최대치다. 입력 24건이면 1차 `effective_parallel=24`가 정상이다.
- 36건 이하 goal/test run에서 Docker lifecycle opt-in이 없고 `--reuse-shards-only`를 쓰면 endpoint pool은 기본 `MCP_GOAL_RUN_AUTO_SHARD_LIMIT=8`까지 줄 수 있다.
- 따라서 preflight는 `mcp_full_shard_readiness=36/36`과 `required_open_for_run`을 분리한다. 대형 검증은 full readiness를 요구하고, 소규모 targeted rerun은 endpoint cap 이후 필요한 open count를 본다.
- v269 24건 재런은 preflight 기준 `open=32/36`, `endpoint_count_expected=8`, `required_open_for_run=8`, 실제 manifest 기준 endpoint health `8/8`, worker `24`였다.
- shard를 36개로 맞추는 작업 자체가 목표일 때만 `--require-all-shards` preflight와 `--allow-goal-shard-lifecycle --auto-up-shards` 실행을 별도 runtime 작업으로 분리한다.

## 2026-05-29 v186 large rerun VLM/OCR-on 고정

- 10만 건급 semantic 재검증 source를 새로 만들 때도 `--vlm on --ocr on`은 필수 옵션이다.
- 대형 재런 기본 템플릿은 `.\venv\Scripts\python.exe expert_main.py --input <FULL_INPUT_JSONL> --output out\expert_result_<NEW_TIMESTAMP>.json --server-type vllm --parallel 36 --reuse-shards-only --no-dashboard --slang-db on --vlm on --ocr on`이다.
- 기존 `out\expert_result_20260528_141006_620986*` partial artifacts는 덮어쓰지 않는다.
- 전체 입력 JSONL 경로가 확정되기 전에는 10만 건 재런을 시작하지 않는다.
- 36-shard Docker lifecycle 자체가 검증 대상이면 `--allow-goal-shard-lifecycle --auto-up-shards`를 명시하고, 일반 semantic 재검증과 분리 보고한다.
- 실행 후 manifest에서 `vlm_enabled=true`, `ocr_enabled=true`, `image_post_count>0`일 때 `vlm_ocr_semantic_review_ready=true`를 확인하기 전에는 이미지 포함 row를 semantic approval 근거로 쓰지 않는다.
- readiness artifact: `qualitative_review\20260528_141006_620986\v186_large_rerun_vlm_ocr_on_readiness_ko_20260529.md`.

## 2026-05-29 semantic/VLM 테스트 기준

- 자연어 판정 품질을 확인하는 goal/test regression은 기본적으로 `--vlm on --ocr on` 기준으로 실행한다.
- VLM 서버가 열려 있는 현재 기준에서는 semantic regression 명령에 `--vlm on --ocr on`을 명시한다. 옵션이 빠진 run은 기본 승인 증거가 아니라 설정 누락 여부부터 확인한다.
- `--vlm off --ocr off` 실행은 text-only guard나 VLM crash 회피를 따로 검증할 때만 쓰며, 이미지가 있는 post의 semantic approval 근거로 사용하지 않는다.
- 이미지 block이 있는 입력에서 VLM/OCR이 완전히 켜지지 않으면 manifest의 `vlm_ocr_semantic_review_ready=false`와 `vlm_ocr_semantic_review_warning=image_posts_present_but_vlm_ocr_not_fully_enabled`를 확인하고, 해당 run은 `INFO_MISSING` 또는 `REPROCESS` 증거로만 취급한다.
- `11718082`처럼 이미지 안에 작품명/회차/OCR 텍스트가 있는 경우, 텍스트 본문만 읽은 판정은 자연어 품질 승인 대상이 아니다.
- 소규모 goal/test 명령 예시는 `.\venv\Scripts\python.exe expert_main.py --input <input.jsonl> --output <result.json> --server-type vllm --parallel <min(input_count,36)> --reuse-shards-only --no-dashboard --slang-db on --vlm on --ocr on`이다. `--parallel 36`이 들어와도 본체는 effective parallel을 낮춰야 하지만, 새 명령 템플릿은 작은 입력에서 불필요한 오해를 줄이기 위해 권장값을 입력 수 기준으로 표기한다.

## 2026-05-29 v180 goal/reuse-only explicit endpoint 필터 기준

- goal/test run에서 Docker Compose `up/recreate`를 자동으로 돌리는 것은 계속 금지한다. shard 복구 자체가 검증 대상일 때만 `--allow-goal-shard-lifecycle`과 `--auto-up-shards` 또는 `--auto-recreate-shards`를 함께 명시한다.
- `MCP_ENDPOINTS`가 예전 24/36개 shard 목록으로 명시되어 있어도, 36건 이하 goal/test 또는 `--reuse-shards-only` 실행에서는 health check 후 살아있는 endpoint만 남긴다.
- autogen endpoint뿐 아니라 명시 endpoint도 `MCP_GOAL_RUN_FILTER_HEALTHY_ENDPOINTS=1` 기본값으로 축소된다. 끄려면 같은 env를 `0`으로 둔다.
- 이 필터는 goal/test 편의 장치이며 large validation에서는 기본 적용하지 않는다. 100건 이상 large/validation 명시 endpoint 실패는 그대로 드러나야 한다.
- startup failure 안내도 goal/reuse-only에서는 `warp_shards.py up`을 기본 해결책처럼 안내하지 않고, Docker lifecycle이 차단된 상태와 복구 opt-in 조건을 먼저 보고한다.
- 확인할 manifest/run_meta 필드: `mcp_healthy_endpoint_filter`, `mcp_healthy_endpoint_filter_autogen`, `mcp_goal_run_health_filtered`, `mcp_endpoint_count_after_health_filter`, `mcp_parallel_after_health_filter`.

## 2026-05-29 v178 title-lead alias goal 테스트런 기준

- title-leading alias 글이 correct title인데 느린 경우 먼저 Docker Compose가 아니라 expert loop를 의심한다.
- `Decoder=None but Verifier=relevant`만 충돌하고, 제목 첫 alias가 검색 결과 `title` 필드에서 동일 작품명으로 직접 닫히면 full Jury/Debate 대신 `evidence_scorer_only`로 종료한다.
- score가 `2.0`처럼 낮아도 위 강한 title-field bridge가 있으면 스킵 가능하지만, 일반 snippet-only bridge는 score `3.0` 이상일 때만 허용한다.
- memory-query, original Gatekeeper noise, recommendation, author/trope/genre target, critical counterargument가 있으면 이 fast-path를 쓰지 않는다.
- v178 known-bad 4건 live 기준 `requested_parallel=36`, `effective_parallel=4`, `mcp_auto_up_shards=false`, `mcp_auto_recreate_shards=false`, `mcp_local_shard_management_enabled=false`, `mcp_local_shard_status_audit=false`였다.
- v178 로그 기준 `11718097`과 `11718099`는 `title-lead alias search bridge resolved`로 스킵됐고, `full_deliberation_ABC`/debate/jury 및 Docker/Compose/shard lifecycle 실행 흔적은 `0`건이었다.

## 2026-05-29 v176 goal/test run: Compose status audit도 기본 차단

- goal/test regression의 기본 경로는 Docker Compose `up/recreate`뿐 아니라 `warp_shards.py status` 기반 Compose status/exec 조회도 피한다.
- `MCP_LOCAL_SHARD_STATUS_AUDIT=1`은 shard 상태감사 작업용이지 일반 semantic regression 기본값이 아니다.
- small goal/test run에서 status audit이 정말 필요하면 `MCP_LOCAL_SHARD_STATUS_AUDIT=1`과 `MCP_ALLOW_GOAL_SHARD_STATUS_AUDIT=1`을 함께 명시한다.
- 일반 goal/test 명령은 기본값 또는 `--reuse-shards-only`를 사용하고, manifest에서 `mcp_auto_up_shards=false`, `mcp_auto_recreate_shards=false`, `mcp_local_shard_management_enabled=false`, `mcp_local_shard_status_audit_allowed=false`를 확인한다.
- `--parallel 36`은 계속 최대치다. 입력이 10건 미만이면 실제 worker는 입력 수 또는 healthy endpoint 수로 낮아져야 하며, worker 수를 맞추려고 compose를 건드리지 않는다.
- 단건/소량 run이 느린 경우 우선 search retry, page analyzer, Decoder/Verifier prompt, expert iteration 병목으로 분리한다.

## 2026-05-29 v175 memory-query weak-title forced-upgrade guard

- 기억 회수/소설 찾기 글에서 title candidate가 있어도 direct proof가 없고 relation judge가 hold/downgrade하면 작품 확정으로 승격하지 않는다.
- direct title, official URL, quote source, character-title link, closed/explicit bridge가 있으면 일반 검증 경로로 보낸다.
- `post_direct_grounding=false`, explicit bridge 부재, weak/thematic relation, major downgrade/nullify counter가 같이 보이면 추가 collaboration/full deliberation을 줄인다.
- Arbiter가 suspected title을 다시 살리는 forced-upgrade도 같은 조건에서 막는다.
- v175 known-bad 4건 canary는 semantic regression 증거지만 10만 건 approval 근거는 아니다. large semantic gate는 random baseline과 high-risk expansion을 별도로 통과해야 한다.

## 2026-05-29 v173 memory-query/null-title goal 테스트런 기준

- `11718083` 같은 memory-query/null-title 케이스는 "작품 매칭 실패"가 아니라 "소설 관련 기억 회수 글이지만 공개 근거만으로 작품 특정 불가"로 본다.
- Verifier 공개 출력이 실제로 존재하기 전에는 memory-query settled fast-path를 열지 않는다. Decoder/Verifier를 건너뛰는 v172식 조기 skip은 승인 경로가 아니다.
- Verifier가 no-title/weak bridge/hold-nullify 방향으로 정리하고 direct proof가 없으면, 추가 collaboration과 Synthesizer를 열지 않는다.
- 이 조건의 Deliberation은 full Jury/Debate 대신 `evidence_scorer_only`로 종료한다.
- direct quote/source, official URL, character/title link, direct title anchor가 있으면 fast-path를 열지 않고 일반 검증 경로로 보낸다.
- v173 live goal run `20260529_132113_820839` 기준 `--parallel 36 --reuse-shards-only` 단건 입력은 `effective_parallel=1`로 낮아졌고, Docker Compose lifecycle 실행 흔적은 `0`건이었다.
- v173 result는 `11718083`을 `is_relevant=false`, `novel_identity=null`, `work_resolution=none`, `title_resolution_state=unresolvable_memory_query`로 유지했다.
- v171 `365.3s`/`102,794` tokens에서 v173 `155.5s`/`62,730` tokens까지 줄었지만, search/deep-search/page analyzer와 대형 Decoder/Verifier prompt는 별도 병목으로 남는다.
- 단건 canary 통과는 goal/test regression 증거일 뿐이며, 10만 건 semantic approval은 random baseline과 high-risk expansion이 별도로 통과해야 한다.

## 2026-05-29 v171 goal/test run Docker lifecycle hard opt-in 강화

- goal/test regression에서 `MCP_AUTO_UP_SHARDS=1` 또는 `MCP_AUTO_RECREATE_SHARDS=1` 환경변수만으로 Docker Compose `up/recreate`를 열지 않는다.
- env 기반 lifecycle이 정말 필요한 경우에는 `MCP_ALLOW_ENV_SHARD_LIFECYCLE=1` 또는 legacy `MCP_CODEX_ALLOW_ENV_SHARD_LIFECYCLE=1` ack를 둔다.
- Codex 또는 36건 이하 small goal/test run에서는 env ack가 있어도 현재 명령에 `--allow-goal-shard-lifecycle`이 없으면 lifecycle은 계속 차단된다.
- shard lifecycle 자체를 검증할 때만 현재 명령에 `--allow-goal-shard-lifecycle --auto-up-shards` 또는 `--allow-goal-shard-lifecycle --auto-recreate-shards`를 함께 붙인다.
- 일반 semantic regression 명령은 기본값 또는 `--reuse-shards-only`로 실행한다. `--parallel 36`은 최대치이고, 실제 실행은 `effective_parallel=min(requested_parallel,input_post_count,healthy_mcp_endpoint_count)`로 낮아질 수 있다.
- manifest에서 `mcp_env_shard_lifecycle_requested`, `mcp_env_shard_lifecycle_global_opt_in`, `mcp_env_shard_lifecycle_allowed`, `mcp_auto_up_shards`, `mcp_auto_recreate_shards`, `mcp_local_shard_management_enabled`를 함께 확인한다.
- lifecycle이 꺼진 상태에서 단건이 여전히 느리면 Compose 문제가 아니라 검색 retry, 대형 decoder/verifier prompt, expert iteration 병목으로 분리해서 본다.
- v171 live goal run `20260529_125908_474586` 재확인: `--parallel 36 --reuse-shards-only` 단건 입력은 `effective_parallel=1`로 낮아졌고, manifest의 `mcp_auto_up_shards=false`, `mcp_auto_recreate_shards=false`, `mcp_local_shard_management_enabled=false` 및 log grep `docker/compose/force-recreate/warp_shards.py=0`으로 Compose lifecycle 미진입을 확인했다.

## 2026-05-29 v169 goal 단건 테스트런 확인

- v169 `11718083` 단건 canary는 `--parallel 36 --reuse-shards-only`로 실행했고, manifest 기준 `requested_parallel=36`, `effective_parallel=1`, `completed/flushed/pending/failed=1/1/0/0`이었다.
- 이 결과는 `--parallel 36`이 최대치이며, 단건 입력에서 worker/shard 수를 맞추기 위해 Docker Compose를 재시작하지 않는다는 운영 규칙을 다시 확인한다.
- manifest 기준 `mcp_auto_up_shards=false`, `mcp_auto_recreate_shards=false`, `mcp_local_shard_management_enabled=false`, `mcp_small_run_shard_lifecycle_blocked=true`였다.
- log 기준 `docker compose`, `force-recreate`, `warp_shards.py`, `compose up` 실행 흔적은 없었다.
- semantic canary는 통과했다: `11718083`은 `official_title=null`, `work_resolution=none`, `title_resolution_state=unresolvable_memory_query`로 유지됐다.
- 단, 단건 `441.6s`와 `176,274` tokens는 별도 성능 병목이므로, goal loop 속도 문제를 Compose lifecycle 문제와 혼동하지 않는다.

## 2026-05-29 v167 goal/test run compose 재시작 방지와 partial 보존

- goal/targeted 테스트런에서 Docker Compose stop/start/recreate를 피하려면 기본값 또는 `--reuse-shards-only`를 사용한다.
- 과거/기존 완료 run에 `--parallel 36`이 들어가 있어도 그것은 최대 worker 상한이다. 입력이 10건 미만인 새 명령 템플릿은 `--parallel min(input_count,36)`를 권장하지만, 이미 완료된 p36 run은 manifest의 `effective_parallel`이 입력 수 또는 healthy endpoint 수로 낮아졌고 lifecycle/evidence 계약이 맞으면 병렬도 표기만 고치려고 재실행하지 않는다.
- Docker lifecycle은 `--allow-goal-shard-lifecycle`과 `--auto-up-shards` 또는 `--auto-recreate-shards`를 함께 명시한 경우에만 검증 대상으로 연다.
- partial/중단 run에서 ordered flush gap이 남으면 primary result JSON은 ordered flushed prefix로 유지하고, `_completed_subset.json`과 `_completed_subset_manifest.json`을 별도 recovery artifact로 남긴다.
- manifest에서 `partial_flush_gap`, `ordered_flush_blocked`, `completed_subset_written`, `completed_subset_count`, `large_run_complete`를 확인한다.
- completed subset은 triage/recovery artifact이며, clean completion 또는 10만 건 semantic approval 근거가 아니다.

## 2026-05-29 v166 large rerun readiness

- 현재 `20260528_141006_620986` source는 partial/recovered라 large-scale approval에 부족하다.
- 새 completed source를 만들 때는 기존 `out\expert_result_20260528_141006_620986*`를 덮어쓰지 않고 새 timestamp output을 사용한다.
- reuse-only safe mode는 `--reuse-shards-only --parallel 36`으로 실행한다. Docker lifecycle을 건드리지 않으며 healthy shard 수에 따라 `effective_parallel`이 낮아질 수 있다.
- explicit 36-shard validation mode는 shard `36/36` 자체가 필요한 경우에만 사용한다. 실행 전후 shard audit을 남기고, Docker lifecycle 의도를 명시한다.
- 현재 관측 기준 Docker shard group은 `1..5`만 떠 있으므로, `--parallel 36`만으로 36 shard 처리량을 기대하지 않는다.
- large rerun 후에는 manifest clean completion, `audit_expert_run_health.py`, `preflight_qualitative_large_scale_review.py`, random baseline `1000+`, P0/P1 high-risk expansion 순으로 검증한다.

## 2026-05-29 v161 goal/test run 확인

- v161 known-bad 5건 regression은 `--parallel 36 --reuse-shards-only`로 실행했고 manifest 기준 `requested_parallel=36`, `effective_parallel=5`, `completed/failed/pending=5/0/0`이었다.
- Docker Compose lifecycle은 열리지 않았다. manifest 기준 `mcp_auto_up_shards=false`, `mcp_auto_recreate_shards=false`, `mcp_local_shard_management_enabled=false`, `mcp_small_run_shard_lifecycle_blocked=true`였고, 통합/워커 로그에서 `docker compose`, `force-recreate`, `warp_shards.py`, `compose up/down` match는 0건이었다.
- 이 런은 소량 goal/test regression의 정상 운영 예시다. 입력이 5건이면 36 worker를 모두 맞추려고 shard를 재시작하지 않고 `effective_parallel=5`로 낮춰 처리한다.
- v161은 known-bad 회귀 검증이며 10만 건 semantic approval 근거가 아니다.

## 2026-05-29 small goal/test run: Docker lifecycle hard opt-in v2

- `--parallel 36`은 최대 worker 상한이다. 입력이 36건 이하인 goal/test regression에서는 shard 수를 맞추려고 Docker Compose를 중지/재시작하지 않는다.
- 36건 이하에서는 Codex 여부와 무관하게 `--auto-up-shards`/`--auto-recreate-shards`만으로 `up/recreate/local shard management`가 열리지 않는다.
- shard 복구 자동화 자체를 테스트할 때만 `--allow-goal-shard-lifecycle --auto-up-shards` 또는 `--allow-goal-shard-lifecycle --auto-recreate-shards`를 함께 붙인다.
- 일반 판단 회귀 run은 기본값 또는 `--reuse-shards-only`로 실행한다. manifest에서 `mcp_small_run_shard_lifecycle_blocked=true`, `mcp_auto_up_shards=false`, `mcp_auto_recreate_shards=false`, `mcp_local_shard_management_enabled=false`를 확인한다.

## 2026-05-29 Codex goal/test run: stale env lifecycle 차단

- Codex에서 `expert_main.py`를 실행할 때는 `CODEX_SHELL` 또는 `CODEX_THREAD_ID`가 감지된다.
- 이 환경에서는 stale `MCP_AUTO_UP_SHARDS=1`/`MCP_AUTO_RECREATE_SHARDS=1`만으로 Docker Compose `up/recreate`를 켜지 않는다.
- 이 차단은 36건 이하 small/goal run뿐 아니라 37건 이상 goal/test 입력에도 적용한다.
- shard 복구 자동화 자체가 검증 대상이면 Codex goal/test 명령에 `--allow-goal-shard-lifecycle`과 `--auto-up-shards` 또는 `--auto-recreate-shards`를 함께 붙인다.
- 자동화 스크립트에서 env 기반 opt-in이 꼭 필요해도 `MCP_CODEX_ALLOW_ENV_SHARD_LIFECYCLE=1`만으로는 부족하다. 현재 명령에 `--allow-goal-shard-lifecycle`을 함께 붙인 경우에만 env lifecycle opt-in을 인정한다.
- manifest/run config에서 `mcp_interactive_codex_run`, `mcp_env_shard_lifecycle_allowed`, `mcp_env_shard_lifecycle_blocked_by_context`, `mcp_allow_goal_shard_lifecycle`, `mcp_command_shard_lifecycle_allowed`, `mcp_auto_up_shards`, `mcp_auto_recreate_shards`를 확인한다.
- v152 live run `20260529_072232_140417` 기준으로 위 메타가 기록됐고, `mcp_auto_up_shards=false`, `mcp_auto_recreate_shards=false`, `mcp_local_shard_management_enabled=false` 상태에서 compose/recreate 로그 흔적은 없었다.

## 2026-05-29 goal/test run: healthy shard 기본 필터

- `--parallel 36`은 계속 최대치다. 입력이 24건이면 1차 effective parallel은 24가 맞다.
- 다만 36건 이하 goal/test run에서 lifecycle opt-in이 없으면 autogen endpoint를 기본 `MCP_GOAL_RUN_AUTO_SHARD_LIMIT=8`로 제한한다.
- health check 뒤 healthy endpoint만 남기고 effective parallel을 healthy endpoint 수 이하로 낮춘다.
- 이 기본 필터는 `MCP_GOAL_RUN_FILTER_HEALTHY_AUTOGEN=1`로 켜져 있다. 끄려면 `MCP_GOAL_RUN_FILTER_HEALTHY_AUTOGEN=0`을 명시한다.
- 36건 이하에서 shard 수를 실제로 늘리는 복구 검증이면 `--allow-goal-shard-lifecycle`과 `--auto-up-shards`/`--auto-recreate-shards`를 함께 명시한다. Codex env 기반 자동화도 `--allow-goal-shard-lifecycle` 없는 env 단독 opt-in은 무시한다.
- goal/test 회귀에서 failed shard 때문에 재실행하는 것은 기본적으로 피한다. healthy shard가 하나 이상 있으면 그 shard만 써서 판단 변화 확인을 먼저 진행한다.

## 2026-05-29 goal/test run: local shard management는 명시 opt-in

- 일반 goal/targeted 테스트런에서 `--parallel 36`은 최대치이며, 입력 수와 healthy endpoint 수에 따라 effective parallel이 낮아질 수 있다.
- 기본 실행은 `docker compose up`, shard `force-recreate`, `warp_shards.py status/ensure` 관리 경로를 모두 생략한다.
- startup에서 확인하는 것은 endpoint health다. Docker Compose를 만져 shard를 맞추는 것은 별도 검증 대상일 때만 한다.
- 36건 이하 goal/test regression은 입력 post 수 기준으로 lifecycle 차단 대상이다. 이 구간에서는 stale `MCP_AUTO_UP_SHARDS=1`/`MCP_AUTO_RECREATE_SHARDS=1` 환경변수가 남아 있어도 up/recreate를 켜지 않는다.
- lifecycle 차단 기준은 `MCP_GOAL_RUN_SHARD_LIFECYCLE_THRESHOLD` 기본 `36`이다. endpoint 자동 생성 제한 기준인 `MCP_SMALL_RUN_SHARD_THRESHOLD`와 혼동하지 않는다.
- shard 복구 자동화 검증이면 36건 이하 goal/test 명령에는 `--allow-goal-shard-lifecycle`과 `--auto-up-shards`/`--auto-recreate-shards`를 함께 명시한다.
- status 감사만 필요하면 `MCP_LOCAL_SHARD_STATUS_AUDIT=1`과 `MCP_ALLOW_GOAL_SHARD_STATUS_AUDIT=1`을 함께 사용한다.

## 2026-05-29 v148 운영 규칙: reuse-only는 healthy shard 수로 낮춰 진행한다

- `--parallel 36`은 최대치다. 입력이 24건이면 1차 effective parallel은 24가 된다.
- `--reuse-shards-only`에서는 Docker Compose를 켜거나 재생성하지 않는다.
- 자동 생성 endpoint가 실제 healthy shard보다 많으면, health check 후 healthy endpoint만 남기고 parallel을 그 수로 낮춘다.
- v148 기준 endpoint `24 -> 5`, parallel `24 -> 5`로 낮춰 24건을 완료했다.
- 이 정책은 goal/targeted 검증 시간을 줄이기 위한 runtime 정책이다. semantic 품질 승인과는 분리한다.
- large validation에서 실제 shard 수를 늘리는 것이 목적이면 `--auto-up-shards`를 명시해야 한다.

수백만 건 단위 처리를 검증할 때 4건, 30건, 300건 같은 작은 표본을 품질 승인 근거로 쓰면 안 된다. 작은 표본은 코드 경로 확인과 오류 유형 발견에만 쓴다.

## 2026-05-29 goal 테스트런 운영 메모

- `--parallel 36`은 고정 워커 수가 아니라 최대치다. 입력이 5건이면 `effective_parallel=5`가 정상이다.
- known-bad/goal 테스트런에서 compose stop/start 비용을 피하려면 기본 정책으로도 자동 lifecycle은 꺼져 있지만, 운영 실수를 줄이려면 `--reuse-shards-only`를 붙인다.
- shard 복구 자동화 자체가 검증 대상일 때만 `--allow-goal-shard-lifecycle`과 `--auto-up-shards`/`--auto-recreate-shards`, 또는 대응 env를 명시한다.
- v147 run id `20260529_040313_425572` 기준 `requested_parallel=36`, `effective_parallel=5`, `mcp_auto_up_shards=false`, `mcp_auto_recreate_shards=false`, `mcp_small_run_shard_lifecycle_blocked=true`였고 compose 실행 흔적은 없었다.
- v147 같은 5건 targeted regression은 코드 경로와 known-bad 회귀 증거다. 10만 건 semantic approval에는 random baseline과 high-risk expansion이 별도로 필요하다.

## 2026-05-24 Gemma 4 4B 36워커 재확인 기록

- 대상: `qualitative_review/20260505_214349_324347`
- 모델: `bg-digitalservices/Gemma-4-E4B-it-NVFP4`
- 실행 기준:
  - `expert_main.py --parallel 36`
  - `MCP_SHARD_COUNT=36`
  - shard audit `36/36`
- 결과:
  - `round3_exit_re_search_re_run_p36_result_manifest.json`: completed `155/155`, failed `0`
  - `round3_exit_re_search_re_run_p36_after_labels.jsonl`: `REPROCESS=94`, `HOLD=57`, `ACCEPT=4`
  - strict closure 후 `round3_exit_action_current_combined_manifest.json`: `ACCEPT=52`, approval excluded `532/584`
- 주의:
  - 후속 재처리 라벨의 자동 `ACCEPT`는 VLM/OCR browser gate와 weak-evidence guard를 통과해야 한다.
  - 이번 실행에서 VLM/OCR 전체 `100`건은 browser visual evidence가 모두 `Weak`였으므로 품질 승인 근거로 쓰지 않는다.

## 샘플 단계

| 단계 | 크기 | 목적 | 품질 승인 가능 여부 |
| --- | ---: | --- | --- |
| unit/smoke | 4~20건 | 새 코드 경로가 터지지 않는지 확인 | 불가 |
| canary | 100~500건 | 병렬 실행, 로그, 검색 timeout/degraded, 결과 스키마 확인 | 불가 |
| risk discovery | 1,000~3,000건 | 위험 bucket별 오류 유형 발견 | 불가 |
| validation | 10,000건 이상 | 개선 전후 품질 비교, 주요 오류율 추정 | 제한적 가능 |
| production audit | 전체 run 100% 자동 감사 + 대형 샘플 정성 리뷰 | 운영 승인 | 가능 |

## 대형 run 기본 원칙

- 전체 결과는 자동 감사로 100% 본다.
  - checkpoint/manifest 정합성
  - failed/reason_error
  - search_degraded/search_timeout
  - slang DB store/block/conflict
  - worker/shard별 이상치
- 정성 리뷰는 표본으로 보되, 위험군을 과표집한다.
- 정상 대조군도 반드시 넣는다.
- 작은 smoke test는 문서에 `품질 승인용 아님`이라고 적는다.
- 같은 post id를 개선 전후로 재처리해 결과 변화를 비교한다.
- 개선 작업은 가능한 한 자동으로 `테스트 런 -> 감사 -> 전후 비교 문서 생성 -> 리뷰 패킷 생성`까지 이어지게 한다.
- 자동화가 아직 없는 단계는 수동으로 실행하되, 누락한 단계와 이유를 `VERIFICATION_RESULTS.md`와 `HISTORY.md`에 남긴다.

## 최소 샘플 권장치

수백만 건 run의 기본 검증 표본:

- 병렬 canary: 최소 200건
- risk discovery: 최소 1,000건
- validation: 최소 10,000건
- 정상 대조군: validation 표본의 15~25%
- 각 주요 bucket 최소치:
  - 검색 저하: 500건 이상
  - 검색 정상 대조군: 1,000건 이상
  - slang 후보: 500건 이상
  - slang 미저장/차단 후보: 300건 이상
  - resolved 저근거: 300건 이상
  - unresolved/multi_work: 300건 이상
  - 역할/호칭성 alias rescue 차단 bucket: 200건 이상
  - 제목 첫 토큰 + 조사 clean alias bucket: 200건 이상
  - non-relevant false negative 의심군: 300건 이상

치명 오류율을 1%p 안팎으로 보고 싶으면 랜덤 표본은 대략 10,000건 이상이 필요하다. 희귀 오류는 랜덤 표본만으로 잘 잡히지 않으므로 risk bucket 표본을 별도로 둔다.

## 병렬 테스트 기준

병렬 테스트는 최소 2단계로 나눈다.

1. 병렬 smoke
   - 4~20건
   - 목적: 코드 경로, worker 로그, shard routing, schema 깨짐 확인
   - 판정: `SMOKE ONLY`
2. 병렬 canary
   - 200~500건
   - 목적: 실제 병렬 구동에서 timeout/degraded/LLM 오류율 확인
   - 판정: `REVIEW`
3. 병렬 validation
   - 1,000건 이상
   - 목적: 개선 전후 오류율과 검색 품질 비교
   - 판정: `GO | REVIEW | NO-GO`

Targeted regression은 별도 단계로 둔다. known bad post 1~20건만 골라 고친 코드 경로가 실제로 바뀌는지 확인하는 용도이며, 품질 승인 근거는 아니다. targeted에서 통과한 케이스는 이후 200건 canary와 1,000건 risk discovery의 `must-post-ids` 또는 별도 고정 샘플에 포함한다.

## 병렬 실행 기록 규칙

병렬 테스트 결과를 남길 때는 아래 값을 반드시 함께 기록한다.

- 입력 파일 경로와 manifest 경로
- 출력 JSON 경로
- run log 경로
- `--parallel` 값
- search shard 목표 수와 실제 감사 결과
- 주요 env override
- 총 처리 시간, post당 평균 시간
- `search_upstream_zero`, `search_degraded_detected`, `search_timeout`
- known bad sample의 개선 전후 판정 변화

작은 targeted 입력을 수동으로 만들 때는 JSONL을 UTF-8 BOM 없이 저장한다. BOM이 있으면 첫 post line이 `json.loads`에서 제외되고 댓글만 남아 `0개 포스트`로 로드될 수 있다.

Gemma 4 4B급 vLLM(`bg-digitalservices/Gemma-4-E4B-it-NVFP4`)으로 `expert_main.py`를 호출할 때 `36`은 고정 워커 수가 아니라 기본 상한이다. 대형 canary/validation의 기본 검증은 `MCP_SHARD_COUNT=36`과 shard audit `36/36`을 맞춘 뒤 실행하되, 36건 이하 goal/test regression은 `MCP_GOAL_RUN_AUTO_SHARD_LIMIT`와 healthy shard filter가 우선한다. 현재 `expert_main.py`가 실제 워커 수를 `effective_parallel=min(requested_parallel,input_post_count,healthy_endpoint_count_if_filtered)`로 자동 조정한다.

- 1~9건 소규모 targeted run: `--parallel 36`을 넘겨도 실제 워커는 입력 건수로 낮아진다.
- 10~35건 targeted run: `--parallel 36`을 넘겨도 실제 워커는 입력 건수로 낮아진다.
- 36건 이상 canary/rerun/validation: `--parallel 36`을 상한으로 사용한다.
- 예: `--parallel 36`으로 7건 입력을 실행하면 manifest에는 `requested_parallel=36`, `effective_parallel=7`이 남아야 한다. 25건 입력이면 `effective_parallel=25`, 199건 입력이면 `effective_parallel=36`이다.
- 운영자가 매번 명령을 `--parallel <input_count>`로 다시 만들 필요는 없다. 사람이 명령을 줄여도 되지만, 필수 검증 기준은 명령 문자열이 아니라 manifest/run_meta의 `effective_parallel`이다.
- 이미 완료된 소규모 run은 병렬도 명령값만 과했다는 이유로 재실행하지 않는다. result/checkpoint/log/manifest가 정상이고 자연어 품질 이슈가 따로 없으면 해당 run은 그대로 증거로 유지한다.
- 결과 manifest와 row별 `run_meta`에서 `requested_parallel`, `effective_parallel`, `parallel_policy`, `input_post_count`를 확인해 실제 실행 병렬도를 검증한다.
- 10건 미만 소규모 targeted run은 자동 endpoint 생성 shard를 기본 2개로 제한한다.
- 36건 이하 goal/test regression은 stale `MCP_SHARD_COUNT=36`/`MCP_AUTO_SHARD_LIMIT=36`이 남아 있어도 lifecycle opt-in이 없으면 `MCP_GOAL_RUN_AUTO_SHARD_LIMIT` 기본 8개로 제한한다.
- 필요한 로컬 shard가 이미 healthy이면 `warp_shards.py up`을 생략한다. 이 재사용 경로는 `MCP_AUTO_UP_REUSE_HEALTHY=0`으로 끌 수 있다.
- 2026-05-29 이후 `expert_main.py`의 docker lifecycle은 goal/test regression에서 기본 재사용 우선이다. 36건 이하 입력은 `MCP_GOAL_RUN_SHARD_LIFECYCLE_THRESHOLD` 기준으로 stale env lifecycle을 차단한다.
- `MCP_SMALL_RUN_SHARD_THRESHOLD`는 소규모 endpoint 자동 생성 제한 기준이다. compose 재시작 허용 기준으로 쓰지 않는다.
- `MCP_GOAL_RUN_SHARD_LIFECYCLE_THRESHOLD` 이하 goal/targeted run은 stale `MCP_AUTO_UP_SHARDS=1` 또는 `MCP_AUTO_RECREATE_SHARDS=1` 환경변수가 남아 있어도 compose lifecycle과 compose 기반 shard ensure를 켜지 않는다. 이때 manifest/run config에는 `mcp_small_run_shard_lifecycle_blocked=true`, `mcp_shard_lifecycle_block_threshold`, `mcp_run_post_count_for_lifecycle`가 남아야 한다.
- 소규모 Codex goal/test run에서 shard 복구 자동화까지 검증해야 하는 경우에는 stale env에 기대지 말고 `--allow-goal-shard-lifecycle`과 `--auto-up-shards`/`--auto-recreate-shards`를 함께 붙인다. 자동화/스크립트의 env opt-in도 현재 명령의 `--allow-goal-shard-lifecycle` 없이는 무시한다.
- v138 live 확인: 5건 targeted run에서 `requested_parallel=36`, `effective_parallel=5`, endpoint `2`, WARP/health attempt `1/1`로 종료됐고 `docker compose`/`force-recreate`는 실행되지 않았다.
- v139 live 확인: 5건 targeted run manifest에서 `mcp_auto_up_shards=false`, `mcp_auto_recreate_shards=false`, `mcp_small_targeted_run=true`를 확인했다.
- v145 live 확인: 5건 known-bad goal run을 `--reuse-shards-only --parallel 36`으로 실행했을 때 `requested_parallel=36`, `effective_parallel=5`, `completed/failed/pending=5/0/0`, startup config `auto_up=False`, `auto_recreate=False`, `small_run_lifecycle_blocked=True`였고 `docker compose`/`force-recreate`/`warp_shards.py recreate` 실행 흔적은 없었다.
- Codex goal/test에서 shard 자동 기동을 강제로 켜야 하면 `--allow-goal-shard-lifecycle --auto-up-shards`를 명시한다. 실패 shard 자동 재생성을 허용하려면 `--allow-goal-shard-lifecycle --auto-recreate-shards`를 명시한다.
- 명령 단위로 완전 재사용 모드를 강제하려면 `--reuse-shards-only`를 붙인다. 이는 CLI/env의 auto-up/recreate opt-in보다 우선한다.
- canary/validation처럼 shard 상태 자체가 검증 대상이면 `MCP_SHARD_COUNT`, `MCP_AUTO_SHARD_LIMIT`, 필요 시 `--auto-up-shards`, `--auto-recreate-shards`를 명시한다.
- 소규모 shard 제한은 `MCP_SMALL_RUN_SHARD_THRESHOLD`와 `MCP_SMALL_RUN_AUTO_SHARD_LIMIT`로 조정한다. 예: `MCP_SMALL_RUN_AUTO_SHARD_LIMIT=1`이면 1~9건 targeted run은 기본 1 shard만 자동 생성한다.
- canary/validation처럼 shard 수 자체가 검증 대상이면 `MCP_SHARD_COUNT`를 명시해 소규모 제한을 우회한다.

의도적으로 더 적은 live search shard를 36 worker가 순환 사용하게 할 때는 실제 live shard 수, `MCP_SHARD_COUNT`/`MCP_ENDPOINTS`, shard audit 결과, 품질 gate 제한 사유를 문서에 남긴다.

리뷰, 분석, 검토, 피드백 Markdown은 한국어로 작성한다. JSON key, enum, action id, bucket id, 명령어, 로그 원문은 원문을 유지하되, 사람이 읽는 결론/근거/판정/후속 작업 설명은 한국어로 남긴다.

4건 smoke가 통과해도 다음 단계는 200건 canary다. 200건 canary가 통과해도 품질 승인이 아니라 validation 준비 상태로만 본다.

## 개선 전후 자동화 루틴

기능 개선, 검색 품질 개선, slang DB 규칙 변경은 아래 루틴을 기본값으로 둔다.

1. baseline 고정
   - baseline run id, checkpoint, output JSON, run summary, shard audit 경로를 기록한다.
   - 같은 입력 JSONL을 재사용할 수 없으면 비교 불가 사유를 먼저 남긴다.
2. 개선 후 테스트 런
   - unit/smoke로 코드 경로를 확인한다.
   - canary 이상은 동일 입력, 동일 `--parallel`, 동일 shard 목표 수, 동일 주요 env로 재실행한다.
3. 자동 감사
   - baseline과 improved run 모두 `tools/audit_expert_run_health.py` 또는 동등한 감사 결과를 남긴다.
   - shard 상태는 `tools/audit_search_shards.py --count <N>`로 전후 기록한다.
4. 전후 비교 문서
   - checkpoint/manifest 정합성, failed/pending, 처리 시간, top latency, search timeout/degraded, slang store/block, known bad 판정 변화를 표로 기록한다.
   - 비교 Markdown/JSON은 `out/comparisons/` 또는 `out/sampling/`에 두고 `VERIFICATION_RESULTS.md`에서 링크한다.
5. 정성 리뷰
   - LLM 판단이 필요한 개선은 `tools/build_llm_judgment_review_packet.py`로 improved run 리뷰 패킷을 생성한다.
   - `ACCEPT/HOLD/REPROCESS/REJECT` 집계가 없으면 품질 gate는 `REVIEW`로 남긴다.

## 샘플 생성 예시

```powershell
.venv312\Scripts\python.exe tools\build_balanced_regression_input.py --checkpoint out\expert_result_20260423_170321_250907_checkpoint.jsonl --output out\sampling\query_gate_canary_200.jsonl --max-posts 200 --per-bucket 20 --order distributed
```

기본 샘플 출력 순서는 `distributed`이다. bucket round-robin으로 출력해 post id/시간대가 한쪽에 몰리지 않게 한다.

- `--order distributed`: canary/risk discovery 기본값. 위험 bucket과 정상군을 섞음.
- `--order random`: 완전 랜덤 순서.
- `--order post_id_desc` 또는 `--order post_id_asc`: 과거 정렬순 결과 재현이 필요할 때만 사용.

post id 정렬순 테스트는 특정 시간대/게시 흐름이 초반 또는 후반 worker에 몰려 late budget, cache, shard 상태, 검색 rate-limit 평가를 왜곡할 수 있다. 운영 대상이 수백만 건이면 테스트도 시간/버킷/위험 유형이 섞여야 한다.

```powershell
.venv312\Scripts\python.exe tools\build_llm_judgment_review_packet.py --run-id 20260423_170321_250907 --limit 1000 --per-bucket 80 --strategy stratified --control-count 120
```

## 병렬 실행 예시

Smoke는 코드 경로 확인용이다.

```powershell
$env:PIPELINE_SEARCH_CONCURRENCY="2"
$env:LLM_ENABLE_CONFIDENT_QUERY_EXPANSION="1"
$env:LLM_ENABLE_GENRE_NOVEL_QUERY_EXPANSION="1"
.venv312\Scripts\python.exe expert_main.py --input out\sampling\query_gate_parallel_smoke_20260426.jsonl --output out\sampling\query_gate_parallel_smoke_20260426_result.json --parallel 2 --no-dashboard --vlm off --ocr off
```

Canary 이상은 shard 수를 먼저 명시하고 감사한 뒤 실행한다.

```powershell
.venv312\Scripts\python.exe tools\audit_search_shards.py --count 36 --timeout 1.5
$env:MCP_SHARD_COUNT="36"
$env:MCP_CLIENT_ENDPOINT_FAILOVER="1"
$env:MCP_CLIENT_MAX_ENDPOINTS_PER_SEARCH="4"
$env:MCP_CLIENT_SEARCH_TIMEOUT_SEC="12"
$env:MCP_CLIENT_SEARCH_MAX_RETRIES="1"
$env:PIPELINE_SEARCH_CONCURRENCY="8"
$env:LLM_ENABLE_CONFIDENT_QUERY_EXPANSION="1"
$env:LLM_ENABLE_GENRE_NOVEL_QUERY_EXPANSION="1"
$env:LLM_ENABLE_LATE_TOTAL_SEARCH_BUDGET="1"
$env:LLM_LATE_TOTAL_SEARCH_MIN_ITERATION="3"
.venv312\Scripts\python.exe expert_main.py --input out\sampling\query_gate_canary_200_20260426.jsonl --output out\sampling\query_gate_canary_200_20260426_result.json --parallel 8 --no-dashboard --vlm off --ocr off
```

실행 시간이 길면 200건 canary를 먼저 완료하고, 1,000건/10,000건은 같은 env와 shard 구성으로 이어서 돌린다.

Canary가 timeout wrapper 안에서 실행될 때는 CLI progress 출력 오류가 결과 실패로 기록되지 않아야 한다. 또한 검색 client failover가 전체 shard를 순차 순회하면 단일 검색이 수십 분까지 늘 수 있으므로 canary 이상에서는 `MCP_CLIENT_MAX_ENDPOINTS_PER_SEARCH`와 `MCP_CLIENT_SEARCH_TIMEOUT_SEC`를 명시한다.

`expert_main.py`의 startup shard discovery 경로를 쓰려면 `MCP_ENDPOINTS`/`MCP_ENDPOINT`를 직접 지정하지 않는다. 대형 run 또는 명시 shard audit에서 `MCP_SHARD_COUNT=36`을 지정하면 endpoint pool이 자동 생성되고, 시작 시 WARP 상태 확인과 `/readyz` health check를 수행한다. 단, `warp_shards.py up` 또는 실패 shard recreate 같은 docker lifecycle 동작은 기본 실행하지 않는다. 해당 복구 동작까지 검증해야 하는 canary에서만 `--allow-goal-shard-lifecycle --auto-up-shards` 또는 `--allow-goal-shard-lifecycle --auto-recreate-shards`를 함께 명시한다.

## 품질 판정

- `GO`: 전체 자동 감사 통과, validation 샘플 정성 리뷰 완료, 치명 오염 0, 재처리 대상 분리 완료
- `REVIEW`: smoke/canary만 수행했거나 risk discovery 단계만 완료
- `NO-GO`: shard 장애/검색 저하가 큰 run을 대형 샘플 없이 승인하려는 경우

## 2026-04-26 샘플 아티팩트

이번 쿼리 확장 gate 검증을 위해 다음 입력 샘플을 생성했다.

| 단계 | 파일 | 건수 | 용도 |
| --- | --- | ---: | --- |
| smoke | `out/sampling/query_gate_parallel_smoke_20260426.jsonl` | 4 | 파이프라인/worker 로그 확인만 가능 |
| canary | `out/sampling/query_gate_canary_200_20260426.jsonl` | 200 | 병렬 실행 안정성, timeout/degraded 관찰 |
| risk discovery | `out/sampling/query_gate_risk_discovery_1000_20260426.jsonl` | 1,000 | 위험 bucket 오류 유형 발견 |
| validation | `out/sampling/query_gate_validation_10000_20260426.jsonl` | 10,000 | 개선 전후 품질 비교용 대형 표본 |

4건 smoke 결과는 `SMOKE ONLY`이며 품질 승인 근거로 사용하지 않는다.

## 품질 개선 후 기본 자동 루틴

검색 품질, title/alias 판정, relevance gate, slang DB 저장 기준을 바꾸는 모든 개선은 다음 확대 순서를 기본값으로 실행한다.

1. targeted/unit 검증
2. 같은 입력 정책의 200건 canary
3. canary 통과 시 1,000건 risk discovery
4. risk discovery 리뷰 패킷 생성

운영 원칙:

- 200건 canary는 `completed=200/200`, `failed=0`, `pending=0`을 만족해야 1,000건으로 넘어간다.
- canary 이상은 `expert_main.py` startup shard discovery/health 경로를 우선 사용한다. docker lifecycle 복구가 검증 대상일 때만 `--auto-up-shards`, `--auto-recreate-shards`를 명시하고, 직접 shard를 올렸다면 전후 shard audit을 남긴다.
- `out/sampling/query_gate_canary_200_20260426.jsonl`과 `out/sampling/query_gate_risk_discovery_1000_20260426.jsonl`을 기본 회귀 입력으로 사용한다. 개선 유형에 맞는 must-id나 이웃 케이스가 필요하면 새 balanced input을 만들고 manifest를 남긴다.
- 각 run은 result/checkpoint/manifest/audit을 남기고, `VERIFICATION_RESULTS.md`에 명령, run id, 판정, 다음 작업을 기록한다.
- risk discovery는 안정성 승인이 아니라 오류 유형 발견 단계다. 결과가 완주해도 품질 판정은 정성 리뷰 전까지 `REVIEW`로 둔다.
- 시간/비용/인프라 문제로 자동 확대를 즉시 수행하지 못하면 defer 사유, 재개 명령, 예상 산출물 경로를 `HISTORY.md`와 `TODO.md`에 남긴다.

## 2026-04-27 canary 교훈

- `20260427_002737_046977` 200건 canary는 `REVIEW / NO-GO`.
- shard 감사는 전후 모두 `ok=36/36`이었으므로, shard 정상만으로 품질/처리 완료를 보장하지 못한다.
- checkpoint 기준 `199/200`, false failed `105`, stuck `1`이 발생했다.
- stuck post `11478694`는 비소설 매체/라이트노벨/애니 경계 케이스이며, 전문가 정성 리뷰 샘플에 고정 포함한다.
- 후속 canary 통과 기준:
  - checkpoint rows `200/200`
  - false failed `0`
  - stuck `0`
  - top latency post 목록 기록
  - off-domain media가 alias bridge로 재확장되지 않음

## 2026-04-27 canary 재실행 결과

- `20260427_121338_563339` 200건 canary는 안정성 기준 `GO`, 품질 기준 `REVIEW`.
- 실행 방식:
  - 당시 기준 `expert_main.py` startup auto-manage 사용. 2026-05-29 이후에는 startup shard discovery/health가 기본이며 docker lifecycle 복구는 명시 opt-in이다.
  - `MCP_SHARD_COUNT=36`, `MCP_AUTO_SHARD_LIMIT=36`.
  - `MCP_CLIENT_MAX_ENDPOINTS_PER_SEARCH=4`, `MCP_CLIENT_SEARCH_TIMEOUT_SEC=12`, `MCP_CLIENT_SEARCH_MAX_RETRIES=1`.
  - 현재 동일 조건에서 docker lifecycle 복구까지 검증하려면 `--auto-up-shards`, `--auto-recreate-shards`를 명시한다.
- 결과:
  - checkpoint rows `200/200`.
  - failed `0`, missing `0`, pending `0`.
  - 사후 shard audit `ok_count=36/36`, `bad_count=0`.
  - stuck 재현 케이스 `11478694` 완료, `703.9s`.
- 남은 검토:
  - top latency post: `11457804=886.4s`, `11478694=703.9s`, `11456200=586.5s`.
  - 검색 오류/timeout/infra no-result가 남아 1,000건 risk discovery와 정성 리뷰 필요.
  - 80건 리뷰 패킷: `out/llm_judgment_reviews/llm_judgment_review_20260427_121338_563339_20260427_135409.md`.
- 다음 단계:
  - late search budget 적용 후 같은 env와 startup shard discovery/health 조건으로 200건 canary 재확인. shard 복구 자체가 검증 대상이면 `--auto-up-shards`, `--auto-recreate-shards`를 별도로 명시한다.
  - canary에서 `late_budget_capped_total`, `late_budget_exhausted_total`, top latency, 검색 실행 수 변화를 기록.
  - 이후 1,000건 risk discovery 실행.
  - 10,000건 validation은 1,000건 결과와 리뷰 adjudication 이후 진행.

## 2026-04-27 late search budget 추가 검증 지침

- 목적: 초기 title/alias 탐색 recall은 유지하되, verification/recall/unresolved 검색이 반복되며 long-tail을 만드는지 제어한다.
- 기본 env:
  - `LLM_ENABLE_LATE_TOTAL_SEARCH_BUDGET=1`
  - `LLM_ENABLE_LATE_SEARCH_BUDGET=1`
  - `LLM_LATE_TOTAL_SEARCH_MIN_ITERATION=3`
  - profile별 기본 cap: `core_fast_resolve=14`, `uncertain_core=16`, `adjacent_meta=10`, `adjacent_meta_cheap=6`, `quarantine_candidate=3`, `deep_research=24`.
- 확인 로그:
  - `late search budget cap`
  - `late search budget exhausted`
- 비교 지표:
  - post별 `executed_queries`
  - `search_query_stats.late_budget_capped_total`
  - `search_query_stats.late_budget_exhausted_total`
  - top latency post와 `search_degraded`/`timed out` 로그 수

## 2026-04-27 afterfix11 risk discovery 결과

- run id `20260427_212634_728016`
- 입력 `out/sampling/query_gate_risk_discovery_1000_20260426.jsonl`
- 출력 `out/sampling/query_gate_risk_discovery_1000_afterfix11_20260427_result.json`
- 결과:
  - `completed=1000/1000`, `failed=0`, `pending=0`
  - `Relevant=746`, `Identified=351`
  - `search_timeout=29`, `search_upstream_zero=539`, `search_degraded_detected=130`
  - `reason_error_count=0`
- 리뷰 패킷:
  - `out/llm_judgment_reviews/llm_judgment_review_20260427_212634_728016_risk1000_afterfix11.md`
  - selected `1000/1000`
- 교훈:
  - risk discovery는 안정성 확인이 아니라 오류 유형 발견 단계다. 이번 run은 안정성은 `GO`였지만 품질은 `REVIEW`.
  - `character_parenthetical_title_resolved`, `generic_relation_only_demoted`, malformed/generic official title, relevant_without_title bucket을 다음 리뷰 우선순위로 둔다.

## 2026-04-28 afterfix12 36병렬 일반화 canary 결과

- run id `20260428_142042_238055`
- 입력 `out/sampling/query_gate_canary_200_20260426.jsonl`
- 출력 `out/sampling/query_gate_canary_200_afterfix12_parallel36_retry_20260428_result.json`
- 실행:
  - `MCP_SHARD_COUNT=36`
  - `MCP_AUTO_SHARD_LIMIT=36`
  - `--parallel 36`
  - 당시 기준 `expert_main.py` startup auto-manage 사용. 2026-05-29 이후 같은 목적이면 startup shard discovery/health를 기본으로 쓰고, docker lifecycle 복구 검증 시에만 `--auto-up-shards`, `--auto-recreate-shards`를 추가한다.
- 결과:
  - `completed=200/200`, `failed=0`, `pending=0`
  - `Relevant=146`, `Identified=67`
  - `Total Time=2473.3s`, `Avg Time/Post=12.4s`
  - 사후 shard audit `ok=36/36`
- 일반화 매트릭스:
  - 실패 유형을 먼저 정의하고 negative/positive 이웃 케이스를 함께 확인했다.
  - `11718070` ECT 의학 일반글은 non-relevant.
  - `11631298` 일반 무협 세력어는 non-relevant.
  - `11663540` 캐릭터 parenthetical positive는 resolved 유지.
  - `11620037` source metadata title 오염은 제거.
  - `11562020` strong alias positive는 resolved.
- 산출물:
  - `docs/devs/GENERALIZATION_CASE_MATRIX.md`
  - `out/sampling/query_gate_canary_200_afterfix12_parallel36_retry_20260428_case_matrix.md`
  - `out/comparisons/query_gate_canary_200_afterfix11_vs_afterfix12_parallel36_20260428.md`
  - `out/llm_judgment_reviews/llm_judgment_review_20260428_142042_238055_afterfix12_parallel36.md`
- 교훈:
  - 36병렬 자체는 안정성 `GO`였지만, `11689276` adjacent 경계와 `11702067/11576520` alias long-tail이 남아 품질은 `REVIEW`.
  - 이후 1,000건 risk discovery도 같은 matrix를 유지하며 positive/negative 이웃 케이스를 포함해야 한다.
