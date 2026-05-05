# Development History

날짜별 개발/운영 변경과 확인 결과를 기록한다. 상세 분석은 관련 문서에 두고, 여기에는 핵심 지표와 후속 작업을 남긴다.

## 2026-05-01 - vLLM VLM degenerate JPEG crash guard

- 상태: runtime_verified / quality_hold
- 배경:
  - 대량 병렬 run이 약 4,000번째 이후 같은 지점에서 반복적으로 vLLM serving `500 -> 502` 상태로 무너지는 증상을 조사.
  - 현재 run `20260501_010427_282685`와 과거 run `20260423_170321_250907` 모두 loaded index `4049`, post `11589463`의 VLM 이미지 처리 직후 최초 `500 Internal Server Error`가 발생.
- 원인 증거:
  - `logs/expert_run_20260501_010427_282685_W9.log`: `[14:59:31] VLM chunk request: post_id=11589463, images=1, bytes=448` 직후 `[14:59:38] 500`, 이후 502 fanout.
  - `logs/expert_run_20260423_170321_250907_W4.log`: `[05:35:51] VLM chunk request: post_id=11589463, images=1, bytes=448` 직후 `[05:35:52] 500`, 이후 502.
  - 실제 dcimg 응답: status `200`, content-type `application/octet-stream`, sniffed MIME `image/jpeg`, dimensions `(389, 1)`.
- 조치:
  - `AgenticPipeline` 이미지 fetch 단계에 image dimension sniffing 추가.
  - JPEG/PNG/GIF/WebP/BMP 크기를 파싱하고, 0px/최소 크기 미만/극단 aspect ratio 이미지는 VLM payload에서 제외.
  - 새 env: `LLM_VLM_MIN_IMAGE_WIDTH=8`, `LLM_VLM_MIN_IMAGE_HEIGHT=8`, `LLM_VLM_MAX_ASPECT_RATIO=64`.
- 확인:
  - `py_compile src\llm_batch\agentic_pipeline.py tests\test_agentic_pipeline_rework.py` 통과.
  - `tests.test_agentic_pipeline_rework`: `Ran 161 tests`, `OK`.
  - run audit 재실행: checkpoint `4014`, failed `0`, reason_errors `0`, fatal_or_trace_line `4`.
- 추가 확인:
  - vLLM 재기동 후 단건 canary `20260501_160410_623323` 실행.
  - `completed_count=1`, `failed_count=0`, `pending_count=0`.
  - `VLM chunk request`, `HTTPStatusError`, `500`, `502` 없음.
  - 완료 로그의 VLM 요약: `vlm: used=False, fetch=0/1, chunks=0, bytes=0`.
- 남은 작업:
  - full output/result에는 `image_geometry_too_small:389x1` limitation 문자열이 노출되지 않아 observability 보강 필요.
  - 같은 run에서 `오러(판타지 용어)` parenthetical이 `판타지 용어` title로 승격되는 별도 품질 문제가 확인되어 QUALITY-HOLD로 분리.
  - 장기적으로 VLM image limitation 카운트를 run audit/dashboard에 노출.

## 2026-04-28 - 품질 개선 후 200/1,000 자동 확대 지침 격상

- 상태: guideline_added / tooling_required
- 배경:
  - `11718111` Namu 의학 일반 개념 오탐처럼 targeted 단건은 바로 고칠 수 있지만, 대량 run에서는 같은 유형의 이웃 케이스와 과차단 리스크가 뒤늦게 드러난다.
  - 앞으로 품질 개선마다 "다음에 canary/risk discovery를 돌리자"로 남기지 않고, 기본 후속 작업으로 자동 진행하도록 운영 기준을 고정한다.
- 지침:
  - 검색 품질, title/alias 판정, relevance gate, slang DB 저장 기준 변경은 targeted/unit 통과 후 200건 canary를 실행한다.
  - 200건 canary가 `completed=200/200`, `failed=0`, `pending=0`이면 같은 조건으로 1,000건 risk discovery를 이어서 실행한다.
  - canary 실패 시 1,000건으로 진행하지 않고 실패 원인, stuck/failed post, shard/search 상태를 먼저 기록한다.
  - 즉시 실행이 불가능하면 defer 사유와 재개 명령을 `HISTORY.md`/`TODO.md`에 남긴다.
- 문서 반영:
  - `docs/devs/CHECKLIST.md`
  - `docs/devs/SAMPLING_AND_PARALLEL_TEST_GUIDE.md`
  - `docs/devs/FEATURE_IMPROVEMENT_TODO.md`
  - `docs/devs/DEV_TODO.md`
  - `docs/devs/TODO.md`
- 남은 작업:
  - 위 루틴을 한 번에 실행하는 wrapper 도구 구현.
  - afterfix14 기준 200건 canary와 1,000건 risk discovery 실행.

## 2026-04-28 - adjacent relevance legacy flag 및 검색 budget 정리

- 상태: regression_verified / canary_needed
- 배경:
  - 공통 제목 stem 수정 후 전체 rework 회귀에서 7건 실패를 추출.
  - 실패는 stem guard 자체가 아니라 adjacent author/meta/recommendation 계열이 legacy `is_relevant=true`로 남는 문제와 `adjacent_meta_cheap` budget 기대값 불일치로 분리됨.
- 일반 실패 유형:
  - 주변 담론(`adjacent_relevant`)은 운영상 보존해야 하지만, 핵심 작품 토론/식별 성공/은어 DB 확정 근거로 카운트되면 false positive 지표가 부풀어짐.
  - 작가/플랫폼/meta 주변담론은 2쿼리로 충분하지만, 장르 토론은 표면 제목 후보가 있으면 공식 근거 확인 슬롯 1개를 남겨야 함.
- 조치:
  - final relevance 계산을 `topicality == core_relevant` 기준으로 정리.
  - prompt/router/arbiter 지시에서 `adjacent_relevant`의 legacy `is_relevant=false`, official title null 기본값을 명시.
  - `adjacent_meta_cheap` budget을 genre-probe `max_q=3`, author/platform/meta `max_q=2`로 분기.
- 확인:
  - targeted adjacent 7건 통과.
  - budget positive/negative 이웃 3건 통과.
  - `tests.test_agentic_pipeline_rework`: 145건 통과.
  - `tests.test_agentic_pipeline_alias_contract`: 30건 통과.
  - 변경 파일 `py_compile` 통과.
- 다음 작업:
  - afterfix 계열 200건 canary에서 adjacent가 `Relevant/Identified/slang DB`로 새는 비율 집계.
  - 1,000건 risk discovery에서 장르 토론 budget 3쿼리의 false positive 증가 여부 확인.

## 2026-04-28 - 공통 제목 stem 충돌 검색 이웃 분리

- 상태: targeted_verified / canary_needed
- 관련 사례:
  - `11684407` (`마법소녀ㄴ 신아 집에서는 머리 풀고다니는건가`)
  - afterfix12 36병렬 run `20260428_142042_238055` 및 대형 run `20260428_155230_844180`에서 `불꽃의 마법소녀ㄴ`이 comparison/recommendation/secondary reference로 새는 현상 확인
- 문제:
  - `마법소녀ㄴ`처럼 의도적 자모 오타형 제목 stem이 여러 공식 제목에 공통으로 포함될 때, 검색 이웃 후보가 실제 비교/추천/은어 후보처럼 저장될 수 있음.
- 조치:
  - 자모 표기(`ㄴ`)를 보존하는 title stem 비교 추가.
  - locked 공식 후보가 본문 앵커와 닫히면 공통 stem 검색 이웃이 단일 후보 rescue를 막지 않도록 조정.
  - 검색 이웃 후보를 `comparison_target`, `recommendation_candidates`, `secondary_reference_works`에서 제거.
  - verifier/router prompt에 `ambiguous_title_stem` 일반 규칙 추가.
- 확인:
  - `python -m unittest tests.test_agentic_pipeline_alias_contract -v`: 30건 통과.
  - 단건 실제 실행: `out/sampling/targeted_ambiguous_title_stem_11684407_afterfix13_20260428_result.json`
  - 결과: `official_title=마법소녀ㄴ은 은퇴하고 싶다`, `work_resolution=resolved`, `comparison_target=null`, `secondary_reference_works=[]`.
- 한계:
  - `python -m unittest tests.test_agentic_pipeline_rework -v`는 145건 중 7건 실패. 실패는 author/recommendation adjacent 기대값과 budget profile 기대값 계열로, 이번 stem 가드 경로와 별개인 기존 리워크 리스크로 분리 기록.
- 다음 작업:
  - afterfix13 200건 canary와 1,000건 risk discovery에서 공통 stem 계열 과차단/과확정 재집계.
  - slang DB 기존 pending `불꽃의 마법소녀ㄴ <- 마법소녀ㄴ` 관측은 최신 run 재처리 후 stale 여부 audit.

## 2026-04-26 - 20k run 검색 reliability 리뷰

- 상태: verified
- 관련 run id: `20260423_170321_250907`
- 관련 문서:
  - `docs/search_reliability_review_20260426.md`
  - `docs/warp_sharding.md`
  - `docs/slang_db_improvement_todo.md`
- 문제:
  - 최근 20k run에서 검색 품질 저하와 MCP/SearchXNG shard 중간 사망 의심.
  - 브라우저에서 SearchXNG UI `19013`이 `ERR_EMPTY_RESPONSE`.
- 확인:
  - `checkpoint_rows=20532`
  - `search_upstream_zero=45449`
  - `search_degraded_detected=13263`
  - `search_timeout=102`
  - 최초 shard 감사 `ok=27/36`, 문제 `[1,10,13,15,26,27,29,33,34]`
  - 컨테이너 로그에서 `can't start new thread`, `Resource temporarily unavailable`, `pthread_create failed` 확인
- 조치:
  - MCP client failover 추가
  - health check `/readyz` 확인 추가
  - 시작 시 readiness 실패 shard recreate 추가
  - shard 감사 도구 추가
  - 문제 shard recreate
- 재확인:
  - `tools/audit_search_shards.py --count 36` 결과 `ok=36/36`
  - `py_compile` 통과
- 남은 작업:
  - 장시간 런 중 주기 shard snapshot
  - post별 search health flag 저장
  - 같은 입력 소량 재처리로 검색 저하율 비교

## 2026-04-26 - Slang DB audit

- 상태: implemented
- 관련 run id: `20260423_170321_250907`
- 관련 문서:
  - `docs/slang_db_improvement_todo.md`
  - `docs/search_reliability_review_20260426.md`
- 확인:
  - `slang_insight=1817`
  - 기존 저장 후보 `546`
  - 보정 후 저장 후보 `532`
  - 차단 후보 `14`, 사유 `unclear_canonical_alias`
  - `slang_db/slang_db.json` 기준 `titles=340`, `family_aliases=1`, 오염성 alias `0`
- 남은 작업:
  - 차단된 실제 약칭 후보 review queue 분리
  - 검색 안정화 후 slang 회수율 재감사

## 2026-04-26 - docs/devs 운영 문서 허브 생성

- 상태: verified
- 관련 run id: 없음
- 관련 문서:
  - `docs/devs/README.md`
  - `docs/devs/TODO.md`
  - `docs/devs/DEV_TODO.md`
  - `docs/devs/FEATURE_IMPROVEMENT_TODO.md`
  - `docs/devs/CHECKLIST.md`
  - `docs/devs/OPERATION_QUALITY_CHECKLIST.md`
  - `docs/devs/IMPROVEMENT_REGISTER.md`
  - `docs/devs/VERIFICATION_RESULTS.md`
- 조치:
  - 개발 TODO, 기능 개선 TODO, 체크리스트, 히스토리, 개선 레지스터를 분리해 규격화
  - 기존 상세 문서를 새 허브에서 참조
  - 전문가 리뷰를 반영해 개발 TODO와 기능개선 TODO, 검증 결과, 운영 품질 게이트를 분리
- 확인:
  - `docs/devs` 표준 문서 세트 생성
  - 2026-04-26 검색 reliability/slang DB 감사 결과를 새 문서 체계에 반영
- 다음 작업:
  - 이후 기능 변경 시 `CHECKLIST.md`와 `TODO.md`를 같이 갱신
  - 대량 런 품질 승인은 `OPERATION_QUALITY_CHECKLIST.md` 기준으로 판정

## 2026-04-26 - LLM/전문가 정성 리뷰 프로토콜 추가

- 상태: implemented
- 관련 run id: `20260423_170321_250907`
- 관련 문서:
  - `docs/devs/LLM_JUDGMENT_REVIEW.md`
  - `docs/devs/OPERATION_QUALITY_CHECKLIST.md`
  - `docs/devs/VERIFICATION_RESULTS.md`
- 조치:
  - 통계/코드 검토로 판단하기 어려운 케이스를 전문가가 직접 읽는 프로토콜 추가
  - `tools/build_llm_judgment_review_packet.py` 추가
  - checkpoint, run audit, slang DB를 묶어 Markdown/JSONL 리뷰 패킷 생성
- 확인:
  - `--limit 30 --per-bucket 8` smoke test 완료
  - `selected=30 from rows=20532`
- 남은 작업:
  - 300건 규모 1차 전문가 리뷰 배치 수행
  - 리뷰 결과 adjudication sheet 누적
  - 다음 run부터 search evidence 필드를 checkpoint에 더 자세히 저장

## 2026-04-26 - 20k run 300건 전문가 정성 리뷰

- 상태: verified
- 관련 run id: `20260423_170321_250907`
- 관련 문서:
  - `docs/devs/QUALITATIVE_REVIEW_20260426.md`
  - `docs/devs/VERIFICATION_RESULTS.md`
- 리뷰 패킷:
  - `out/llm_judgment_reviews/llm_judgment_review_20260423_170321_250907_20260426_201809.jsonl`
- 결과:
  - 검색/근거 리뷰: 표본 81건 중 `ACCEPT=48`, `HOLD/RESEARCH/REPROCESS/REJECT=33`
  - slang 리뷰: 105건 중 `confirmed_alias≈52`, `noise≈27`, 나머지 보류/참조/비교
  - relevance/work 리뷰: 표본 95건 중 `ACCEPT=32`, `RESEARCH/REPROCESS=50`
- 통합 판정: `REVIEW`
- 핵심 발견:
  - 검색 근거 0 상태 resolved_title 확정
  - 댓글 URL 과잉 primary 승격
  - off-domain media 수용
  - alias span 과대 추출
  - false negative와 reason/field 불일치

## 2026-04-26 - 1,000건 계층 리뷰 패킷과 쿼리 확장 프로브

- 상태: partial
- 관련 run id: `20260423_170321_250907`
- 조치:
  - `tools/build_llm_judgment_review_packet.py`에 `--strategy stratified`, `--control-count` 추가
  - 1,000건 계층 리뷰 패킷 생성
  - 리뷰 패킷에 검색 쿼리 확장 후보 포함
  - `tools/run_search_query_expansion_probe.py` 추가
- 확인:
  - `selected=1000 from rows=20532`
  - 정상 대조군 `routine_sample=120` 포함
  - `괴담텔/즉사무림` 수동 프로브에서 플랫폼명 조합이 platform detail hit를 늘림
- 남은 작업:
  - 1,000건 패킷 전문가 adjudication
  - 일반 제목/잡담에 suffix를 붙였을 때의 false positive와 timeout 위험 제어
  - alias/title confidence gate 이후 쿼리 확장 적용

## 2026-04-26 - 쿼리 확장 gate와 대형 샘플 기준 정리

- 상태: implemented / review
- 관련 파일:
  - `src/llm_batch/experts/orchestrator.py`
  - `docs/devs/SAMPLING_AND_PARALLEL_TEST_GUIDE.md`
  - `docs/devs/VERIFICATION_RESULTS.md`
- 조치:
  - confident query expansion을 확정 약칭 alias-only 또는 `novel_literature` 도메인 표면어로 제한
  - 일반 제목/잡담/비소설 도메인에는 platform suffix를 붙이지 않도록 조정
  - 4건 smoke를 품질 승인 근거로 쓰지 않도록 문서화
  - 200건 canary, 1,000건 risk discovery, 10,000건 validation 입력 샘플 생성
- 확인:
  - `py_compile` 통과
  - 단위 경로 확인: `즉사무림`은 확장, `ect`/`모도쿠가오소우`는 확장 차단
  - 병렬 smoke 4건 완료, 단 품질 판정은 `SMOKE ONLY`
- 남은 작업:
  - 200건 canary 병렬 실행
  - 1,000/10,000건 표본에서 개선 전후 결과 비교
  - 전문가 adjudication으로 false positive/false negative 변화 확인

## 2026-04-27 - 200건 canary 결과와 검색 long-tail 보정

- 상태: review / no-go
- 관련 run id:
  - canary: `20260427_002737_046977`
  - stuck single repro: `20260427_030848_374214`
- 관련 문서:
  - `docs/devs/VERIFICATION_RESULTS.md`
  - `docs/devs/FEATURE_IMPROVEMENT_TODO.md`
  - `docs/devs/SAMPLING_AND_PARALLEL_TEST_GUIDE.md`
- 확인:
  - 36개 shard는 canary 전후 모두 `ok=36/36`.
  - 200건 canary checkpoint는 `199/200`까지만 기록.
  - `105`건이 `[Errno 22] Invalid argument`로 failed 처리됐으나, 원인은 결과 판정이 아니라 CLI progress stderr pipe 오류.
  - 실제 stuck은 `global_idx=100`, `post_id=11478694` 한 건.
  - `11478694`는 `anime` category 감지 이후에도 alias bridge 검색이 이어져 정체 위험이 있었음.
- 조치:
  - `expert_main.py`에서 CLI progress 출력 실패가 처리 결과를 실패로 만들지 않도록 방어.
  - `orchestrator.py`에서 비소설 매체 hard guard가 indirect title/alias/fetch 보강을 차단.
  - `search/client.py`에서 검색 1건당 failover endpoint 수와 client timeout을 env로 제한 가능하게 추가.
- 검증:
  - `py_compile` 통과.
  - `11478694` 단일 재현은 `completed_count=1`, `failed_count=0`.
  - 단일 재현 시간은 `485.4s`로 완료됐지만 아직 long-tail 위험.
  - canary checkpoint 199건에서 전문가 리뷰 패킷 80건 생성.
- 다음 작업:
  - 200건 canary 재실행.
  - 통과 후에만 1,000건 risk discovery, 10,000건 validation으로 진행.
  - `슬레이어즈`처럼 라이트노벨/애니/원작 경계 케이스는 LLM/전문가 리뷰에 포함.

## 2026-04-27 - expert_main startup auto-manage 200건 canary 통과

- 상태: verified / quality-review
- 관련 run id: `20260427_121338_563339`
- 관련 문서:
  - `docs/devs/VERIFICATION_RESULTS.md`
  - `docs/devs/FEATURE_IMPROVEMENT_TODO.md`
  - `docs/devs/IMPROVEMENT_REGISTER.md`
- 조치:
  - `expert_main.py`의 startup shard auto-manage 경로로 36개 shard를 정리한 뒤 200건 canary 재실행.
  - `MCP_CLIENT_MAX_ENDPOINTS_PER_SEARCH=4`, `MCP_CLIENT_SEARCH_TIMEOUT_SEC=12`, `MCP_CLIENT_SEARCH_MAX_RETRIES=1` 조건 적용.
  - 완료 후 사후 shard audit과 80건 LLM/전문가 리뷰 패킷 생성.
- 확인:
  - checkpoint `200/200`, `completed=200`, `failed=0`, missing `0`.
  - manifest `completed_count=200`, `flushed_count=200`, `pending_count=0`.
  - 1차 stuck 케이스 `11478694` 완료, 처리 시간 `703.9s`.
  - 사후 shard audit `out/search_shard_audit_20260427_134858.json`: `ok_count=36/36`, `bad_count=0`.
  - 리뷰 패킷 `out/llm_judgment_reviews/llm_judgment_review_20260427_121338_563339_20260427_135409.md`, `selected=80`.
- 판정:
  - canary 안정성은 GO.
  - 검색 timeout, infra no-result, long-tail과 작품/은어 판단 품질은 REVIEW.
- 다음 작업:
  - 같은 실행 조건으로 1,000건 risk discovery 진행.
  - long-tail 상위 post와 80건 리뷰 패킷을 전문가가 직접 검토.
  - 10,000건 validation 또는 운영 승인 전 `ACCEPT/HOLD/REPROCESS/REJECT` 집계 필요.

## 2026-04-27 - post별 late search 누적 예산 가드

- 상태: implemented_unit_verified / canary-required
- 관련 파일:
  - `src/llm_batch/experts/orchestrator.py`
  - `tests/test_agentic_pipeline_rework.py`
  - `docs/devs/FEATURE_IMPROVEMENT_TODO.md`
  - `docs/devs/SAMPLING_AND_PARALLEL_TEST_GUIDE.md`
- 배경:
  - 2차 200건 canary는 안정성은 통과했지만 `11457804=886.4s`, `11478694=703.9s`, `11456200=586.5s` long-tail이 남음.
  - 원인 일부는 개별 `_execute_searches` 배치 cap이 아니라 verification/search/recall batch가 post 안에서 반복되며 누적되는 구조.
- 조치:
  - `_execute_searches` 중앙 관문에서 `ctx.executed_queries` 기준 post 누적 예산을 적용.
  - 초기 title/alias 탐색은 보존하고, late iteration 또는 verification/recall/unresolved late-purpose batch에 cap/skip 적용.
  - profile별 기본 cap을 env로 조정 가능하게 추가.
- 확인:
  - `py_compile` 통과.
  - late budget 단위 테스트 3건 통과.
  - `11478694` 1 shard 참고 실행 `20260427_140716_814536`: `completed_count=1`, `failed_count=0`, `291.8s`, `3 iterations`, 검색 실행 `13건`.
- 주의:
  - `11478694` 참고 실행은 최종 late-purpose refinement 직전에 시작된 smoke라 품질 gate로 쓰지 않음.
  - 운영 판단은 36 shard / 200건 canary 재확인 후 진행.

## 2026-04-27 - 개선 전후 자동 테스트/비교 지침 추가

- 상태: proposed / guideline-added
- 관련 문서:
  - `docs/devs/CHECKLIST.md`
  - `docs/devs/OPERATION_QUALITY_CHECKLIST.md`
  - `docs/devs/SAMPLING_AND_PARALLEL_TEST_GUIDE.md`
  - `docs/devs/DEV_TODO.md`
  - `docs/devs/FEATURE_IMPROVEMENT_TODO.md`
  - `docs/devs/IMPROVEMENT_REGISTER.md`
- 조치:
  - 개선 작업의 완료 기준에 자동 테스트 런, run audit, baseline/improved 비교 문서, 필요 시 LLM 리뷰 패킷 생성을 추가.
  - 자동화 도구가 없으면 수동 비교로 대체하되 누락 사유를 기록하도록 명시.
  - 전용 비교 도구는 P1 TODO로 등록.
- 다음 작업:
  - late search budget 200건 canary 재실행 때 baseline `20260427_121338_563339` 대비 첫 비교 문서 형식 확정.

## 2026-04-27 - late search budget 200건 canary 비교 완료

- 상태: verified-canary / quality-review
- 관련 run id:
  - baseline: `20260427_121338_563339`
  - improved: `20260427_143145_922090`
- 조치:
  - late search budget guard 적용 후 같은 200건 canary를 36 shard/startup auto-manage 경로로 재실행.
  - 사후 shard audit과 baseline/improved 비교 문서, 100건 전문가 리뷰 패킷 생성.
- 산출물:
  - `out/sampling/query_gate_canary_200_late_budget_20260427_run_summary.json`
  - `out/comparisons/query_gate_canary_200_20260427_baseline_vs_late_budget.md`
  - `out/comparisons/query_gate_canary_200_20260427_baseline_vs_late_budget.json`
  - `out/search_shard_audit_20260427_late_budget_postrun.json`
  - `out/llm_judgment_reviews/llm_judgment_review_20260427_143145_922090_20260427_160810.md`
- 확인:
  - checkpoint `200/200`, failed `0`, missing `0`.
  - 사후 shard audit `ok=36/36`.
  - 검색 오류 `81 -> 75`, timeout `82 -> 75`.
  - late budget cap/exhausted `22/14`로 실제 canary에서 가드 발동 확인.
  - identified title `72 -> 76`, relevant `148 -> 153`.
  - total wall time은 `5452.3s -> 5453.8s`로 거의 동일.
- 판정:
  - 안정성은 GO.
  - 품질은 REVIEW. post id별 판정 변화와 title 증가분은 사람이 읽어야 함.
- 남은 위험:
  - `11478694`, `11456200` tail은 개선됐지만 `11457804`는 `886.4s -> 911.5s`로 여전히 병목.
  - `11718077`은 `151.8s -> 496.2s`로 회귀해 단계별 로그 리뷰 필요.

## 2026-04-27 - canary 정성 검토 중 발견한 추가 개선점

- 상태: discovered / partially-implemented
- 발견 사례:
  - `11663540`: `주서연` character page의 `주서연(전 버튜버가 하고 싶은데요)` parenthetical title을 회수하지 못해 정식 제목 미확정.
  - `11631298`: `무림맹`, `마교`, `혈교` 같은 무협 일반 세력명만으로 `무림맹주 막내제자`를 과확정.
  - `11549038`: 1차 partial result에는 `[Errno 22] Invalid argument` 실패 row가 남아 있으나, 이후 rerun에서는 정상 처리됨.
- 조치:
  - `tools/build_balanced_regression_input.py`에 `--order distributed|random|post_id_desc|post_id_asc` 추가.
  - 기본값을 `distributed`로 두어 post id 정렬순 canary가 되지 않게 변경.
  - `SAMPLING_AND_PARALLEL_TEST_GUIDE.md`에 분산 출력 순서 지침 추가.
- 추가 개선 후보:
  - 무협/판타지 일반 세력명은 공유 토큰에서 장르 일반어를 제거한 뒤 고유 토큰이 없으면 resolved 승격 금지.
  - character page parenthetical title은 별도 중간 증거로 회수하되, 동명이인/타매체 false positive 방지를 위해 post 반복 언급과 장르 맥락을 요구.
  - 오래된 partial result의 실패 row가 최신 rerun에서 회수됐는지 표시하는 audit 리포트 필요.
  - infra no-result는 `220 -> 244`로 증가했으므로 검색 무결과를 오류 감소와 별도로 해석해야 함.

## 2026-04-27 - generic/character targeted 개선 실험

- 상태: implemented-unit / targeted-review
- 조치:
  - Verifier relation judge에 `generic_relation_only`를 추가해 무협 일반 세력/역할어만 겹치는 후보의 resolved 승격을 차단.
  - `캐릭터명(작품명)` wiki/search result를 character parenthetical bridge로 등록하는 경로 추가.
  - `줄다리기(오징어 게임)` 같은 사건/게임 parenthetical은 캐릭터 브리지에서 제외.
  - `전차`, `줄다리기` 등 설정/대결 표면어를 generic topic title로 취급해 canonical 보정 오승격을 차단.
  - 최종 consistency에서 deliberation rescue가 마지막 청소 단계에 의해 제거되는 문제를 좁은 조건으로 보호하는 실험 추가.
- 확인:
  - `py_compile` 통과.
  - targeted unittest 7건 통과.
  - `expert_main.py` startup auto-manage 경로로 targeted 3건을 반복 실행.
- 결과:
  - `11549038`: 과거 `[Errno 22] Invalid argument` 재발 없음.
  - `11631298`: official title 확정은 차단됐지만 `unresolved_title`/candidate 잔류가 있어 추가 보정 필요.
  - `11663540`: `전차` 오승격은 차단됐지만 `전 버튜버가 하고 싶은데요` 최종 확정은 아직 미완.
- 산출물:
  - `out/sampling/targeted_generic_character_3_20260427.jsonl`
  - `out/sampling/targeted_generic_character_3_20260427_afterfix3_result.json`
  - `logs/expert_run_20260427_174602_508561.log`
- 남은 작업:
  - generic relation only 후보가 최종 `title_candidates`에 남는 문제 정리.
  - character parenthetical + official platform hit + jury strong의 최종 title 유지 조건을 더 보수적으로 재설계.
  - 동일 3건 통과 후 분산 200건 canary로 회귀 확인.

## 2026-04-27 - generic/character targeted 후속 수정

- 상태: targeted-verified / canary-required
- 조치:
  - `agentic_pipeline.py`에서 generic relation only demote 후 `primary/mentioned/title_candidates`를 비우고 최종 interpretation을 재계산해 `secondary_reference_works` 누수를 제거.
  - `ctx.verified_character_work_links`가 비어 있어도 `ctx.search_results`의 `캐릭터명(작품명)` parenthetical을 final consistency에서 재구성하도록 보강.
  - `orchestrator.py`, `arbiter.py`에서 `confidence="High"` 같은 문자열 label이 숫자 비교에서 오류를 내지 않도록 정규화.
  - `tests/test_agentic_pipeline_rework.py`에 검색 결과 fallback parenthetical, secondary reference suppress, confidence label 테스트 추가.
- 확인:
  - `py_compile` 통과.
  - targeted unittest 8건 통과 및 confidence label unittest 통과.
  - 3-shard targeted run `out/sampling/targeted_generic_character_3_20260427_afterfix6_result.json`에서 `11631298`은 `is_relevant=false`, `work_resolution=none`, 후보/secondary reference 없음.
  - 단독 no-BOM targeted run `out/sampling/targeted_character_11663540_20260427_afterfix8_result.json`에서 `11663540`은 `전 버튜버가 하고 싶은데요`로 resolved.
- 주의:
  - afterfix8 결과에는 Arbiter confidence 오류 수정 전 발생한 `verifier_technical_failure` 플래그가 남아 있음. 코드는 수정했지만, 다음 3-shard/200건 canary에서 재발 여부를 다시 봐야 함.
  - targeted 1~3건은 코드 경로 확인용이며 품질 승인 근거가 아님.
- 다음 작업:
  - 동일 3건을 다시 3-shard로 재실행해 technical failure 플래그 소거 확인.
  - 200건 분산 canary에서 `generic_relation_only_demoted`, `character_parenthetical_title_resolved`, confidence type error 재발 여부를 집계.

## 2026-04-27 - generic/character afterfix11 3-shard 확인

- 상태: targeted-go / canary-required
- 추가 발견:
  - afterfix10 3-shard에서는 `11663540`이 캐릭터 parenthetical 증거를 찾았지만, `comparison_target=주서연`이 실제 작품 비교처럼 남아 최종 `unresolved`로 되돌아갔다.
  - 이는 `주서연`이 작품명이 아니라 캐릭터 표면인데도 comparison slot에 들어간 케이스다.
- 조치:
  - `agentic_pipeline.py`에 약한 캐릭터/비작품 comparison target은 캐릭터 parenthetical 확정을 막지 않는 좁은 가드를 추가.
  - 해당 캐릭터 표면 후보가 `mentioned_works`/secondary reference로 새지 않도록 정리.
  - 회귀 테스트 `test_search_parenthetical_bridge_resolves_without_registered_link`를 afterfix10 실패 형태로 강화.
- 확인:
  - `py_compile`: pass.
  - targeted unittest 5건: OK.
  - 3-shard targeted run `out/sampling/targeted_generic_character_3_20260427_afterfix11_result.json` 완료.
  - `11631298`: 비관련, 후보/secondary 누수 없음.
  - `11663540`: `전 버튜버가 하고 싶은데요` resolved, `character_talk`, `system_state=clean`.
  - 로그에서 `Invalid argument`, confidence type error, `Traceback`, `verifier_technical_failure` 재발 없음.
- 다음 작업:
  - 200건 분산 canary를 실행하고, known bad 변화와 동명이인 캐릭터 parenthetical false positive를 정성 리뷰한다.

## 2026-04-27 - afterfix11 200건 canary 완료

- 상태: canary-go / risk-discovery-required
- 실행:
  - `expert_main.py` startup auto shard 관리 경로 사용.
  - WARP `36/36`, MCP health `36/36`.
  - 입력 `out/sampling/query_gate_canary_200_20260426.jsonl`.
  - 출력 `out/sampling/query_gate_canary_200_afterfix11_20260427_result.json`.
  - 로그 `logs/expert_run_20260427_191203_030136.log`.
- 결과:
  - `completed=200/200`, `failed=0`, `pending=0`.
  - `Relevant=151`, `Identified=75`, `Total Time=5508.2s`.
  - 감사 결과 `reason_error_count=0`, `verifier_technical_failure=0`, `[Errno 22] Invalid argument=0`.
  - `generic_relation_only_demoted=3`, `character_parenthetical_title_resolved=5`.
- known bad:
  - `11631298`은 `무림맹주 막내제자` resolved에서 non-relevant/title 없음으로 수정 유지.
  - `11663540`은 unresolved에서 `전 버튜버가 하고 싶은데요` resolved로 수정 유지.
  - `11549038`은 처리 오류 없이 `adjacent_relevant / trope_discussion`.
- 산출물:
  - 감사: `out/sampling/query_gate_canary_200_afterfix11_20260427_audit.json`.
  - 비교: `out/comparisons/query_gate_canary_200_late_budget_vs_afterfix11.md`.
  - LLM 리뷰 패킷: `out/llm_judgment_reviews/llm_judgment_review_20260427_191203_030136_afterfix11.md`.
- 다음 작업:
  - 120건 리뷰 패킷을 실제로 판독해 false positive/false negative와 slang DB 저장 위험을 표기.
  - 1,000건 risk discovery로 확대.

## 2026-04-27 - afterfix11 120건 리뷰 판독 및 1,000건 risk discovery 시작

- 상태: qualitative-review-done / risk-discovery-running
- 판독 산출물:
  - `out/llm_judgment_reviews/llm_judgment_review_20260427_191203_030136_afterfix11_adjudicated.jsonl`
  - `out/llm_judgment_reviews/llm_judgment_review_20260427_191203_030136_afterfix11_adjudicated.md`
  - `out/llm_judgment_reviews/llm_judgment_review_20260427_191203_030136_afterfix11_adjudication_summary.json`
- 판독 결과:
  - `ACCEPT=63`, `HOLD=24`, `RESEARCH=11`, `REPROCESS=15`, `REJECT=7`.
  - critical reject는 common term/person/media parenthetical 과확정, generic phrase 작품명 오인, off-domain title 승격이 중심.
  - REPROCESS는 확인된 별칭 누락(`폴랩`, `망교성`, `서울마탑`, `아생갤`)과 multi-work/comparison 처리 약화가 중심.
- 후속 실행:
  - `out/sampling/query_gate_risk_discovery_1000_20260426.jsonl`을 afterfix11 코드로 재처리 시작.
  - run id `20260427_212634_728016`, 출력 예정 `out/sampling/query_gate_risk_discovery_1000_afterfix11_20260427_result.json`.
  - startup auto shard 관리 경로, `MCP_SHARD_COUNT=36`, `parallel=8`.
- 다음 작업:
  - 1,000건 완료 후 audit/summary/comparison을 생성하고, 120건 adjudication의 critical/reprocess 유형이 risk discovery에서 얼마나 재발하는지 집계.

## 2026-04-27 - afterfix11 1,000건 risk discovery 완료

- 상태: run-stability-go / quality-review-required
- 실행:
  - run id `20260427_212634_728016`.
  - 입력 `out/sampling/query_gate_risk_discovery_1000_20260426.jsonl`.
  - 출력 `out/sampling/query_gate_risk_discovery_1000_afterfix11_20260427_result.json`.
  - startup auto shard 관리 경로 사용, WARP `36/36`, MCP bridge health `36/36`, `parallel=8`.
- 결과:
  - `completed=1000/1000`, `failed=0`, `pending=0`.
  - `Relevant=746`, `Identified=351`.
  - `Total Time=30852.1s`, `Avg Time/Post=30.9s`.
  - audit `reason_error_count=0`, `search_timeout=29`, `search_upstream_zero=539`, `search_degraded_detected=130`.
  - slang old/new/blocked `136/133/3`, bad remaining `0`.
- 산출물:
  - audit `out/sampling/query_gate_risk_discovery_1000_afterfix11_20260427_audit.json`.
  - 품질 요약 `out/comparisons/query_gate_risk_discovery_1000_afterfix11_quality_review.md`.
  - 리뷰 패킷 `out/llm_judgment_reviews/llm_judgment_review_20260427_212634_728016_risk1000_afterfix11.md`, selected `1000/1000`.
- 발견:
  - 120건 REJECT 중 4건이 1,000건에서도 resolved title FP로 재현.
  - 120건 REPROCESS 중 10건이 여전히 false negative/미확정/과차단 형태로 재현.
  - `character_parenthetical_title_resolved=37` 중 `Depressive disorder`, `뮤지컬 배우`, `Sword Master`, `마피아42`, `BLACKPINK`, `Ubuya` 같은 critical FP가 섞임.
  - `generic_relation_only_demoted=8` 중 `11631298`은 맞지만 `서울마탑`, `화귀`, `언니약혼` 등 strong alias 후보 과차단이 섞임.
- 다음 작업:
  - parenthetical bridge gate, malformed/generic official title validator, generic guard 이후 alias rescue를 우선 개선.

## 2026-04-28 - afterfix12 P0 품질 가드 1차 적용

- 상태: targeted-verified / broader-risk-discovery-required
- 변경:
  - `src/llm_batch/agentic_pipeline.py`
    - 최종 official title validator 추가: malformed wiki revision/source metadata phrase/영문 일반어/person-media/common title 후보 차단.
    - character parenthetical bridge가 `Depressive disorder`, `뮤지컬 배우`, `또는 라쇼몽...` 같은 비작품 괄호 표제를 title로 승격하지 않도록 재게이트.
    - `generic_relation_only` demote 전에 strong alias rescue를 추가하되, `무림맹`, `마교`, `혈교` 같은 세계관 일반 세력명은 rescue alias로 인정하지 않음.
  - `tests/test_agentic_pipeline_rework.py`
    - `서울마탑` rescue, `무림맹` 과구제 방지, malformed/source metadata/person title reject 회귀 테스트 추가.
- 자동 확인:
  - `.venv312\Scripts\python.exe -m py_compile src\llm_batch\agentic_pipeline.py tests\test_agentic_pipeline_rework.py`
  - targeted unittest `13/13 OK`
- 실제 targeted run:
  - core4 입력: `out/sampling/targeted_p0_afterfix12_core4_20260428.jsonl`
  - core4 출력: `out/sampling/targeted_p0_afterfix12_core4_20260428_result.json`
  - run id `20260428_123539_845850`, `completed=4/4`, `failed=0`
  - 확인:
    - `11689276`: `뮤지컬 배우` title 제거, `adjacent_relevant/none`.
    - `11631298`: `generic_relation_only_demoted`, non-relevant/title 없음.
    - `11562020`: `서울에 마탑 세웠더니 돈이 미쳤다` resolved, `generic_relation_alias_rescued`.
    - `11620037`: core4에서는 source metadata title이 재발해 추가 조임 필요 확인.
  - 추가 라쇼몽 단건 재확인:
    - 입력 `out/sampling/targeted_p0_afterfix12_rashomon_20260428.jsonl`
    - 출력 `out/sampling/targeted_p0_afterfix12_rashomon_20260428_result.json`
    - run id `20260428_124339_828427`
    - `11620037`: non-relevant/title 없음으로 수정 확인.
- 남은 작업:
  - 같은 P0 묶음을 200건 canary와 1,000건 risk discovery에 재적용해 false positive 감소와 alias rescue 회귀를 확인.
  - `화귀`, `언니약혼`, `폴랩`, `망교성` 등 strong alias long-tail은 추가 targeted/adjudication 필요.

## 2026-04-28 - afterfix12 ECT 의학 일반글 추가 보정

- 상태: targeted-verified
- 배경:
  - `11718070`은 afterfix11에서 `Depressive disorder` resolved title FP였고, afterfix12 1차에서는 title은 제거됐지만 `adjacent_relevant=True`가 남았다.
  - 실제로는 ECT/우울증 치료/기억력 문제를 말하는 의학 일반글이므로 장르소설 adjacent도 아니어야 한다.
- 변경:
  - 작품 앵커 없이 의학 주제만 확인되는 경우 `medical_common_topic_demoted`로 `unrelated/noise/work_resolution=none` 처리.
  - 안전하지 않은 verified character-work link(`ECT -> Depressive disorder`)는 medical demotion을 막지 못하도록 조정.
- 확인:
  - targeted unittest `13/13 OK`.
  - 실제 단건 run:
    - 입력 `out/sampling/targeted_p0_afterfix12_ect_20260428.jsonl`
    - 출력 `out/sampling/targeted_p0_afterfix12_ect_20260428_result.json`
    - run id `20260428_132300_821816`
    - `11718070`: `is_relevant=false`, official title 없음, `topicality=unrelated`, flag `medical_common_topic_demoted`.

## 2026-04-28 - 하드코딩 방지 / 일반화 원칙 문서화

- 상태: guideline-added / regression-running
- 배경:
  - 특정 실패 사례를 고칠 때 post id, 오답 title, 검색 문자열을 직접 막는 식으로 누적하면 대량 런에서 새 오탐/누락을 만든다.
  - `11718070`도 `Depressive disorder`만 막는 방식이 아니라 "작품 앵커 없는 실제 의학/건강 주제"라는 실패 유형으로 다뤄야 한다.
- 변경:
  - `docs/devs/CHECKLIST.md`에 일반화/하드코딩 금지 체크리스트 추가.
  - `docs/devs/OPERATION_QUALITY_CHECKLIST.md`에 일반화/하드코딩 방지 운영 게이트 추가.
  - `docs/devs/FEATURE_IMPROVEMENT_TODO.md`, `docs/devs/DEV_TODO.md`에 LLM/후처리 규칙 일반화 작업 항목 추가.
  - `src/llm_batch/prompts/expert_prompts.py` 공통 프레임워크에 "예시는 암기 대상이 아니라 rubric 설명용" 원칙 추가.
  - `src/llm_batch/agentic_pipeline.py`의 최종 title guard에서 사례별 bad-title 목록을 줄이고, 검색 메타데이터/일반 표면어/의학 도메인처럼 범주형 규칙으로 주석화.
- 완료 기준:
  - 새 품질 패치마다 실패 유형, 증거 불변식, positive/negative 이웃 테스트, 200/1,000건 재확인을 함께 남긴다.

## 2026-04-28 - afterfix12 36병렬 canary와 일반화 매트릭스 확인

- 상태: run-stability-go / quality-review-required
- 관련 run id: `20260428_142042_238055`
- 입력: `out/sampling/query_gate_canary_200_20260426.jsonl`
- 출력: `out/sampling/query_gate_canary_200_afterfix12_parallel36_retry_20260428_result.json`
- 실행:
  - `expert_main.py` startup auto shard 관리 경로 사용.
  - `MCP_SHARD_COUNT=36`, `MCP_AUTO_SHARD_LIMIT=36`, `--parallel 36`.
  - startup WARP `36/36`, MCP bridge health `36/36`.
- 운영 발견:
  - 최초 36병렬 시 `warp_shards.py status --json`가 Docker exec trace 단계에서 멈출 수 있음을 확인.
  - `tools/warp_shards.py`에 `WARP_SHARDS_STATUS_EXEC_TIMEOUT_SEC` 기반 subprocess timeout과 `warp_cli_connected_after_trace_timeout` fallback을 추가.
  - 수정 후 `warp_shards.py status --json`와 expert_main startup shard 확인이 정상 진행됨.
- 결과:
  - `completed=200/200`, `failed=0`, `pending=0`.
  - `Relevant=146`, `Identified=67`.
  - `Total Time=2473.3s`, `Avg Time/Post=12.4s`.
  - audit `reason_errors=0`, `search_timeout=8`, `search_upstream_zero=105`, `search_degraded_detected=12`.
  - 사후 shard audit `ok=36/36`, `bad=[]`.
- 일반화 매트릭스 확인:
  - `11718070`: afterfix11의 `Depressive disorder` FP에서 afterfix12는 non-relevant/title 없음, `medical_common_topic_demoted`.
  - `11631298`: 무림맹/마교/혈교 일반 세력어는 non-relevant/title 없음 유지.
  - `11663540`: `전 버튜버가 하고 싶은데요` resolved 유지, Novelpia 공식 detail URL 회수.
  - `11620037`: 라쇼몽/source metadata 오염 title 제거, non-relevant/title 없음.
  - `11562020`: `서울에 마탑 세웠더니 돈이 미쳤다` resolved, `generic_relation_alias_rescued`.
- 남은 위험:
  - `11689276`은 오답 title은 제거됐지만 adjacent_relevant로 남아 정성 검토 필요.
  - `11702067`, `11576520`은 relevant지만 official title 미확정으로 strong alias long-tail 개선 필요.
  - `11383118`, `11327341`은 risk discovery 이웃 케이스로 재판독 필요.
- 산출물:
  - audit: `out/sampling/query_gate_canary_200_afterfix12_parallel36_retry_20260428_audit.json`
  - case matrix: `out/sampling/query_gate_canary_200_afterfix12_parallel36_retry_20260428_case_matrix.md`
  - 비교: `out/comparisons/query_gate_canary_200_afterfix11_vs_afterfix12_parallel36_20260428.md`
  - 리뷰 패킷: `out/llm_judgment_reviews/llm_judgment_review_20260428_142042_238055_afterfix12_parallel36.md`
- 다음 작업:
  - 생성된 120건 리뷰 패킷을 `ACCEPT/HOLD/RESEARCH/REPROCESS/REJECT`로 실제 판독.
  - afterfix12 1,000건 risk discovery로 확대해 malformed/common title FP 감소와 alias FN 잔존률 확인.
  - sampling output을 기본 `out/expert_result_<run_id>` 경로로 복사하지 않아도 audit 가능한 도구 옵션 추가.

## 2026-04-28 - afterfix14 Namu 의학/일반 개념 official title 승격 차단

- 상태: targeted_verified / canary_required
- 배경:
  - `11718111` (`나도 조현병으로 오해받은 적 있음`)이 `조현병`이라는 나무위키 일반 의학 항목으로 resolved 되는 오탐을 확인.
  - reason 내부에는 "현실 의학/사회 개념이며 작품 고유 근거가 부족하다"는 반론이 있었지만, 후처리 단계가 이를 되살렸다.
- 원인:
  - `조현병(정신분열병)` 나무위키 결과가 character-parenthetical bridge로 등록됨.
  - `웹소설`이라는 약한 매체 단어 때문에 나무위키 일반 개념어 가드가 완화됨.
  - URL-backed weak-title replacement가 나무위키 일반 개념 URL을 official title 근거로 사용.
- 변경:
  - 의학/건강/현실 개념어 surface를 범주형 lexicon으로 묶고 `medical_common_topic_title` hard reject profile을 추가.
  - 최종 title reject 시 title candidates, primary/mentioned/recommendation/comparison 후보를 함께 비워 residual title 누수를 막음.
  - character-parenthetical search hint와 URL-backed replacement가 같은 final title rejection profile을 확인하도록 정리.
  - `웹소설/소설/작품` 같은 약한 단어만으로는 medical common demotion을 막지 못하고, 작가/회차/캐릭터명/공식 플랫폼 detail 등 강한 앵커가 필요하도록 변경.
- 검증:
  - targeted 회귀 5건 OK.
  - `tests.test_agentic_pipeline_rework`: 147건 OK.
  - `tests.test_agentic_pipeline_alias_contract`: 30건 OK.
  - `py_compile` 통과.
  - 실제 단건 run `20260428_230857_637381`: `11718111`은 `is_relevant=false`, title 없음, `medical_common_topic_demoted`.
- 남은 작업:
  - afterfix14 200건 canary와 1,000건 risk discovery에서 나무위키 일반 개념어 FP와 의료 소재 웹소설 positive 이웃을 같이 집계.

## 2026-04-29 - afterfix14 200 canary 및 1,001 risk discovery 완료

- 상태: run-stability-go / quality-review
- 실행:
  - 200건 canary run id `20260428_233059_378617`.
  - 1,001건 risk discovery run id `20260429_002511_375830`.
  - `11718111`을 risk discovery 입력에 추가해 targeted 통과 사례의 대형 표본 재발 여부를 확인.
- 결과:
  - canary: `completed=200/200`, `failed=0`, `pending=0`, `Relevant=70`, `Identified=61`.
  - risk discovery: `completed=1001/1001`, `failed=0`, `pending=0`, `Relevant=381`, `Identified=297`.
  - risk runtime: `13487.3s`, 평균 `13.5s/post`.
  - 사전/사후 shard audit 모두 `ok=36/36`.
  - risk audit: `reason_errors=0`, `slang_db_bad_remaining=0`, `search_timeout=4`, `search_degraded_detected=173`.
- 확인:
  - `11718070` ECT, `11631298` 무림맹, `11456200` 마법소녀ㄴ/폼체인지 오탐은 최신 risk discovery에서 title 없음.
  - `11616838`, `11198715` 마법소녀ㄴ positive stem은 `마법소녀ㄴ은 은퇴하고 싶다`로 유지.
  - `11066247`처럼 다중 애니 캐릭터/트로프 글은 adjacent/title 없음으로 마감.
- 새로 드러난 위험:
  - `11718111`은 targeted에서는 차단됐지만 risk discovery에서는 `정신과 의사`로 resolved. 의학 일반어만이 아니라 직업/현실 개념 title 승격 guard가 필요.
  - `11684415 -> 小數, decimal number`, `11505857 -> Cecil`처럼 일반어/인명 표면이 플랫폼 URL 또는 search bootstrap으로 official title이 됨.
  - weak-evidence official title 후보 35건을 별도 리뷰 대상으로 추출.
- 산출물:
  - `out/sampling/query_gate_canary_200_afterfix14_20260428_audit.json`
  - `out/sampling/query_gate_risk_discovery_1000_plus11718111_afterfix14_20260429_audit.json`
  - `out/search_shard_audit_20260429_after_afterfix14_risk1000.json`
  - `out/llm_judgment_reviews/llm_judgment_review_20260429_002511_375830_risk1000_afterfix14.md`
- 다음 작업:
  - weak evidence official title promotion guard를 P1 개선으로 분리.
  - `official_title_evidence=false`, `search_snippets=0`, `official_urls=0`, `post_spans=0` 조합이 resolved를 이기지 못하게 스코어/후처리 기준 보강.

## 2026-04-29 - afterfix15~17 weak evidence / broad alias 개선

- 상태: canary-go / risk-hold
- 변경:
  - 약한 evidence literal topic title, dictionary/gloss title이 official title로 확정되지 않도록 최종 title rejection profile을 확장.
  - `11718111`처럼 의료/일상 개념과 검색 키워드만 겹치는 unresolved core 잔류를 demotion하는 consistency guard 추가.
  - locked official candidate rescue가 넓은 alias stem과 캐릭터 미연결 반론을 무시하지 않도록 broad alias hold guard 추가.
- 검증:
  - `tests.test_agentic_pipeline_rework`: 153건 OK.
  - `11718111` targeted afterfix16: `Relevant=0`, title 없음.
  - afterfix16 200 canary `20260429_175638_261091`: `completed=200/200`, `failed=0`, `Relevant=77`, `Identified=64`, audit `reason_errors=0`, `slang_db_bad_remaining=0`.
- 관찰:
  - ECT/조현병/무림맹/주서연 기본 회귀는 통과.
  - `11198715`는 afterfix16 canary에서 `마법소녀물 신전사가 되었다`로 잘못 resolved되는 새 오류를 발견.
  - afterfix17 targeted에서는 오답 title lock은 제거됐지만 `Relevant=0`까지 내려가 과보수. 이 케이스는 `관련-미확정`으로 유지하는 후속 개선 필요.
- 결정:
  - afterfix17 상태에서 1,000건 risk discovery는 보류.
  - 다음 개선은 `마법소녀ㄴ`류 의도적 제목 오타/자모 alias의 positive/negative 이웃을 먼저 고정한 뒤 200 canary를 재실행한다.

## 2026-04-29 - afterfix18~19 internal work signal HOLD

- 상태: targeted-go / canary-required
- 배경:
  - `11198715`는 afterfix17에서 오답 title resolved는 제거됐지만 `Relevant=0`으로 과보수 처리됨.
  - 본문에는 `세린이`, `세진이`, `계약`, `은퇴`, `공백의 2년`처럼 작품 내부 토론 단서가 있으므로 비관련 삭제가 아니라 관련-미확정 HOLD가 맞음.
- 변경:
  - `internal_work_signal_unresolved_recovered` guard를 추가해 복수 캐릭터 + 설정/전개 단서가 있으면 `core_relevant + unresolved_work`로 복구.
  - 실제 Gatekeeper 구조인 `detected_entities.possible_characters/titles`도 읽도록 보강.
  - 내부 앵커 HOLD가 발생한 경우 locked official detail 후보가 다시 title resolved로 승격하지 않도록 차단.
- 검증:
  - `tests.test_agentic_pipeline_rework`: 155건 OK.
  - afterfix18 targeted는 관련 복구는 됐지만 locked official rescue가 `마법소녀ㄴ은 은퇴하고 싶다`로 resolved하여 추가 차단 필요를 확인.
  - afterfix19 targeted `out/sampling/targeted_magicgirl_11198715_afterfix19_20260429_result.json`: `Relevant=1`, `Identified=0`, `official_title=null`, flag `internal_work_signal_unresolved_recovered`.
- 다음:
  - afterfix19 200건 canary를 실행하고, 통과 시 1,000건 risk discovery로 확대.

## 2026-04-30 - afterfix19 risk review 및 afterfix20 locked metadata guard

- 상태: afterfix19 canary-go / risk-review / afterfix20 canary-go / risk-review
- 실행:
  - afterfix19 200건 canary run id `20260429_204443_104695`: `completed=200/200`, `Relevant=73`, `Identified=54`.
  - afterfix19 1,001건 risk discovery run id `20260429_213837_418990`: `completed=1001/1001`, `Relevant=401`, `Identified=284`.
  - risk audit: `reason_errors=0`, `slang_db_bad_remaining=0`, `search_degraded_detected=160`.
- 확인:
  - ECT/조현병 현실 의학어는 title 없음으로 안정화.
  - `11198715`은 관련-미확정으로 유지.
  - `11456200`, `11505857`, `11205227`은 title 없음.
- 새 위험:
  - `11631298`가 risk discovery에서 `무림맹주 막내제자`로 재승격.
  - 문제 candidate는 locked 상태였지만 `page_type=community_post`, `content_status=deleted`, `negative_evidence=url_is_community_post/url_deleted_or_unavailable`를 갖고 있었음.
  - `11663540`은 검색 결과에 캐릭터 괄호형 bridge가 잡히지 않을 때 resolved/unresolved/non-relevant가 흔들림.
- 변경:
  - afterfix20에서 locked official candidate rescue가 bad page/content metadata를 가진 후보를 제외하도록 보강.
  - 특정 작품명/세력명 blacklist가 아니라 `community_post`, `deleted/unavailable`, `negative_evidence` 구조 신호를 기준으로 일반화.
- 검증:
  - `tests.test_agentic_pipeline_rework`: `157 OK`.
  - afterfix20 targeted run `20260430_015935_598854`: `11631298` title 없음, `11684415` resolved 유지, `11456200` title 없음.
- afterfix20 canary:
  - run id `20260430_021001_693350`.
  - `completed=200/200`, `Relevant=73`, `Identified=57`, `reason_errors=0`, `slang_db_bad_remaining=0`.
  - known-case: `11631298` title 없음, `11663540 -> 전 버튜버가 하고 싶은데요`, `11198715` 관련-미확정.
- afterfix20 risk:
  - run id `20260430_025849_885589`.
  - `completed=1001/1001`, `Relevant=382`, `Identified=277`, `reason_errors=0`, `slang_db_bad_remaining=0`.
  - `11631298` locked bad metadata 재승격은 차단됨.
  - `11663540`은 `전 버튜버가 하고 싶은데요` resolved.
  - `11616838`, `11198715`은 관련-미확정.
  - `11718070`, `11718111`, `11205227`은 title 없음.
- 잔존 위험:
  - `11505857 -> Cecil` 재발. 짧은 인명/캐릭터 표면이 character-parenthetical/영문 title로 승격하는 유형.
  - `11456200`은 title 없음이지만 관련-미확정으로 과복구. 단일 캐릭터 + 트로프 일반론의 internal work signal 조건을 줄여야 함.
- 다음:
  - `Cecil`류 false bridge guard 추가.
  - `11456200`류 trope-only 과복구 조건 축소.

## 2026-04-30 - afterfix21 short person bridge / trope-only guard

- 상태: canary-go / risk-review
- 변경:
  - 짧은 영어 인명형 character-parenthetical title은 게시글 본문에 작품성 anchor가 없으면 resolved로 승격하지 않도록 제한.
  - `Cecil` blacklist가 아니라 `short ascii personlike title + weak post-side work anchor` invariant로 처리.
  - `폼체인지/변신/의상/추가파츠/마법소녀` trope-only 표면은 강한 plot term 없이 `internal_work_signal_unresolved_recovered`를 만들지 않도록 축소.
  - `승급`은 strong plot term으로 추가해 positive 이웃 보존.
- 검증:
  - `tests.test_agentic_pipeline_rework`: `159 OK`.
  - targeted run `20260430_120419_466550`: `11505857`, `11456200`은 title 없음, `11663540` resolved 유지, `11616838` 관련-미확정.
  - 200 canary run `20260430_121717_430655`: `completed=200/200`, `Relevant=82`, `Identified=65`, `reason_errors=0`, `slang_db_bad_remaining=0`.
  - 1,001 risk run `20260430_131615_234022`: `completed=1001/1001`, `Relevant=396`, `Identified=308`, `reason_errors=0`, `slang_db_bad_remaining=0`.
- 확인:
  - `11505857 -> Cecil` 재발 차단.
  - `11456200` trope-only 과복구 차단.
  - `11718070`, `11718111`, `11631298` title 없음 유지.
  - `11663540`은 `전 버튜버가 하고 싶은데요` resolved 유지.
  - `11198715`, `11616838`은 risk에서 관련-미확정 유지.
- 다음:
  - afterfix21 risk에서 증가한 `Relevant/Identified`를 정성 리뷰해 recall 개선인지 false positive 증가인지 분리.
  - 새 resolved 저근거 상위 표본을 리뷰 패킷으로 추출.
