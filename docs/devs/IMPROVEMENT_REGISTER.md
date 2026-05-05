# Improvement Register

개선안은 문제, 조치, 확인 결과를 한 묶음으로 관리한다. 완료된 항목도 지우지 않고 상태를 `verified`로 바꾼다.

## IMP-20260501-001 - VLM/OCR degenerate image geometry guard

- 상태: runtime_verified / quality_hold
- 우선순위: P0
- 관련 run id: `20260501_010427_282685`, `20260423_170321_250907`
- 관련 문서: `docs/devs/VERIFICATION_RESULTS.md`, `docs/devs/HISTORY.md`
- 문제:
  - 장시간 병렬 run이 loaded index `4049`, post `11589463` 부근에서 반복적으로 vLLM serving `500 -> 502` 상태로 전파됨.
  - 로그상 최초 실패는 W9/W4의 `VLM chunk request: post_id=11589463, images=1, bytes=448` 직후 발생했고, 다른 worker의 502는 서버 엔진 사망 이후의 후폭풍으로 확인됨.
  - 실제 이미지 응답은 `application/octet-stream`이지만 JPEG signature이며 dimensions가 `389x1`인 degenerate progressive JPEG.
- 조치:
  - 이미지 fetch 단계에서 signature MIME sniffing 이후 JPEG/PNG/GIF/WebP/BMP dimension 파싱 추가.
  - `LLM_VLM_MIN_IMAGE_WIDTH`, `LLM_VLM_MIN_IMAGE_HEIGHT`, `LLM_VLM_MAX_ASPECT_RATIO` 기준으로 VLM 전송 전 geometry limitation 처리.
  - dimension을 알 수 없는 이미지는 기존 호환성을 위해 fail-open으로 유지.
- 확인:
  - 실제 dcimg fetch: status `200`, content-type `application/octet-stream`, bytes `448`, sniffed MIME `image/jpeg`, dimensions `(389, 1)`.
  - `tests.test_agentic_pipeline_rework.CommentTitleRecoveryTest.test_vlm_detects_progressive_jpeg_dimensions`
  - `tests.test_agentic_pipeline_rework.CommentTitleRecoveryTest.test_vlm_fetch_skips_degenerate_image_geometry_without_vlm_call`
  - `tests.test_agentic_pipeline_rework`: `Ran 161 tests`, `OK`
  - vLLM 재기동 후 단건 canary `20260501_160410_623323`: completed `1/1`, failed `0`, VLM chunk request 없음, 500/502 없음.
- 남은 위험:
  - full output/result에는 geometry limitation 문자열이 노출되지 않아 운영자가 `fetch=0/1`만 보고 원인을 역추적해야 함.
  - AVIF 등 dimension을 파싱하지 못하는 포맷은 fail-open이므로, 동일 증상이 다른 포맷에서 재현되면 파서 확장 필요.
  - 동일 post에서 `오러(판타지 용어)` parenthetical bridge가 `판타지 용어`를 작품명처럼 승격하는 별도 품질 HOLD가 확인됨.
- 다음 작업:
  - `image_geometry_too_small`/`image_aspect_ratio_extreme` limitation 카운트를 run audit 또는 dashboard에 노출 검토.
  - generic concept parenthetical bridge guard 추가.

## IMP-20260426-001 - MCP/SearchXNG shard readiness와 failover

- 상태: verified
- 우선순위: P0
- 관련 run id: `20260423_170321_250907`
- 관련 문서: `docs/search_reliability_review_20260426.md`, `docs/warp_sharding.md`
- 문제: 일부 shard가 `Exited (1/137)`로 죽었는데 endpoint pool에 남아 검색 빈 결과/저하/timeout을 유발.
- 조치:
  - `MCPClient` endpoint failover 추가
  - health check에서 `/readyz` 확인
  - 시작 헬스체크 실패 shard 자동 recreate
  - `tools/audit_search_shards.py` 추가
- 확인:
  - 최초 shard 감사 `ok=27/36`
  - 문제 shard recreate 후 `ok=36/36`
  - `py_compile` 통과
- 남은 위험:
  - 장시간 런 도중 shard가 죽으면 새 snapshot/worker pool 제외가 아직 부족함
- 다음 작업:
  - run 중 주기 readiness snapshot
  - post별 search health flag 저장

### 2026-04-28 status/trace timeout update

- 상태: verified_parallel36
- 배경:
  - afterfix12 36병렬 startup 중 `warp_shards.py status --json`가 Docker exec trace 호출에서 반환하지 않아 run 시작이 멈출 수 있음을 확인.
- 조치:
  - `tools/warp_shards.py`의 `warp-cli status`와 trace curl 호출에 subprocess timeout 적용.
  - trace timeout이지만 `warp-cli`가 connected이면 fallback trace 상태를 남기고 expert_main startup이 계속 진행되도록 조정.
- 확인:
  - `WARP_SHARDS_STATUS_EXEC_TIMEOUT_SEC=5` 상태 조회 정상 반환.
  - afterfix12 36병렬 run `20260428_142042_238055`에서 startup WARP/MCP health `36/36`, 사후 shard audit `ok=36/36`.

## IMP-20260426-002 - Slang DB audit와 후보 회수율 관리

- 상태: implemented
- 우선순위: P1
- 관련 run id: `20260423_170321_250907`
- 관련 문서: `docs/slang_db_improvement_todo.md`, `docs/search_reliability_review_20260426.md`
- 문제: slang DB가 실제 약칭, 보류 관측, family alias를 함께 담아 대시보드/운영에서 저장 여부가 헷갈릴 수 있음.
- 조치:
  - 20k 런 기준 slang audit
  - 오염성 alias 잔존 여부 확인
  - blocked 후보 사유 집계
- 확인:
  - `slang_insight=1817`
  - 보정 후 저장 후보 `532`
  - 문장형/작품명 동일 alias 오염 `0`
- 남은 위험:
  - `unclear_canonical_alias`로 차단된 후보 중 실제 약칭 가능성이 있음
- 다음 작업:
  - review queue 분리
  - 검색 안정화 후 같은 샘플 재감사

## IMP-20260426-003 - Developer docs process

- 상태: verified
- 우선순위: P2
- 관련 run id: 없음
- 관련 문서: `docs/devs/*`
- 문제: 개발 TODO, 기능 개선, 체크리스트, 히스토리가 흩어지면 대량 런 이후 개선 결과가 누락될 수 있음.
- 조치:
  - `docs/devs` 허브 생성
  - DEV_TODO/FEATURE_IMPROVEMENT_TODO/CHECKLIST/OPERATION_QUALITY_CHECKLIST/REGISTER/VERIFICATION_RESULTS/HISTORY 문서 규격화
  - 전문가 리뷰 기반으로 GO/REVIEW/NO-GO 품질 판정 도입
- 확인:
  - 문서 파일 생성
  - 기존 검색 reliability/slang DB 문서와 연결
  - 2026-04-26 검증 결과와 TODO를 새 문서 체계에 반영
- 남은 위험:
  - 실제 개발 루틴에서 체크리스트를 계속 갱신하지 않으면 다시 문서가 낡을 수 있음
- 다음 작업:
  - 변경 완료 전 `CHECKLIST.md` 확인을 습관화
  - 대량 런 승인 전 `OPERATION_QUALITY_CHECKLIST.md` 판정을 남김

## IMP-20260426-004 - LLM/전문가 정성 리뷰 패킷

- 상태: implemented
- 우선순위: P1
- 관련 run id: `20260423_170321_250907`
- 관련 문서: `docs/devs/LLM_JUDGMENT_REVIEW.md`, `docs/devs/VERIFICATION_RESULTS.md`
- 문제: 검색 shard 장애가 섞인 run은 숫자 감사만으로 실제 오판/은어 회수율 손실을 확정하기 어렵다.
- 조치:
  - `tools/build_llm_judgment_review_packet.py` 추가
  - 위험군 샘플링, risk score, sample bucket, run audit 맥락, slang DB 맥락, 전문가 adjudication 필드 포함
- 확인:
  - 30건 smoke test 패킷 생성
  - JSONL/Markdown 산출물 생성
- 남은 위험:
  - 현재 checkpoint에는 raw search snippet, used evidence URL, query별 상태가 제한적임
- 다음 작업:
  - 300건 규모 전문가 리뷰 진행
  - 다음 run checkpoint에 `search_health_flags`, `used_evidence_urls`, `raw/filtered search preview` 저장

## IMP-20260426-005 - 20k Run Qualitative Review Findings

- 상태: verified
- 우선순위: P1
- 관련 run id: `20260423_170321_250907`
- 관련 문서: `docs/devs/QUALITATIVE_REVIEW_20260426.md`
- 문제: 통계 감사만으로는 검색 장애가 실제 판정/은어 DB 품질에 미친 영향을 확정하기 어려움.
- 조치:
  - 300건 위험군 패킷 생성
  - 검색/근거, slang/DB, relevance/work resolution 전문가 리뷰 수행
- 확인:
  - 검색/근거: 표본 81건 중 약 40%가 HOLD/RESEARCH/REPROCESS/REJECT
  - slang/DB: 105건 중 confirmed alias 약 52건, noise 약 27건
  - relevance/work: 표본 95건 중 RESEARCH/REPROCESS 50건
- 남은 위험:
  - 이번 패킷은 위험군 집중 샘플이므로 전체 정확도 추정에는 부적합
  - 그러나 자동 승인 위험과 개선 우선순위는 충분히 확인됨
- 다음 작업:
  - `search_snippets=0 AND official_urls=0` resolved 제한
  - 댓글 URL evidence 역할 분리
  - off-domain media gate
  - alias span 추출
  - reason/field 불일치 validator

## IMP-20260426-006 - Stratified Review And Query Expansion Probe

- 상태: partial
- 우선순위: P1
- 관련 run id: `20260423_170321_250907`
- 관련 문서: `docs/devs/VERIFICATION_RESULTS.md`, `docs/devs/LLM_JUDGMENT_REVIEW.md`
- 문제:
  - 300건 위험군 샘플만으로 20k 전체 품질 승인을 하면 표본 부족 위험이 큼.
  - 검색 쿼리 확장은 회수율을 높일 수 있지만 잡담/장르 일반론을 작품으로 과잉 확정할 위험도 있음.
- 조치:
  - 1,000건 계층 리뷰 패킷 생성
  - 정상 대조군 120건 포함
  - 검색 쿼리 확장 후보를 리뷰 패킷에 포함
  - `tools/run_search_query_expansion_probe.py` 추가
- 확인:
  - `selected=1000 from rows=20532`
  - `괴담텔/즉사무림` 수동 프로브에서 확장 쿼리가 platform detail hit를 늘림
  - 패킷 기반 소량 프로브에서 일반 제목/잡담 쿼리는 timeout/false positive 위험을 보임
- 남은 위험:
  - 아직 1,000건 전문가 adjudication은 미완료
  - 확장 쿼리를 무조건 적용하면 장르/잡담 글이 특정 작품으로 오염될 수 있음
- 다음 작업:
  - alias/title confidence gate 설계
  - 같은 post id 재처리 비교
  - 쿼리 확장 전후 false positive/false negative 정성 리뷰

## IMP-20260426-007 - Confident Query Expansion Gate And Large Sampling

- 상태: implemented
- 우선순위: P1
- 관련 run id: `20260423_170321_250907`
- 관련 문서: `docs/devs/SAMPLING_AND_PARALLEL_TEST_GUIDE.md`, `docs/devs/VERIFICATION_RESULTS.md`
- 문제:
  - `작품명 장르소설/웹소설/플랫폼` 검색은 약칭 회수율을 올릴 수 있지만, 일반 제목/잡담에도 적용되면 false positive와 timeout을 늘릴 수 있음.
  - 4건 병렬 smoke는 수백만 건 운영 품질 승인 근거로 너무 작음.
- 조치:
  - confident query expansion gate 추가
  - 확정 약칭은 alias-only로 허용하고, 일반 표면어는 `novel_literature` 도메인일 때만 확장
  - 비소설/other 도메인 title surface expansion 차단
  - 200/1,000/10,000건 검증 샘플 생성
- 확인:
  - `py_compile` 통과
  - 단위 경로에서 `즉사무림`은 확장, `ect`/`모도쿠가오소우`는 확장 차단
  - 4건 병렬 smoke 완료, over-expansion 위험 발견 후 gate 재조정
- 남은 위험:
  - 아직 200건 canary와 10,000건 validation 재처리는 미완료
  - 검색 shard 수가 smoke 중 2개로 구성된 상태라 대형 run 전 목표 shard 수 재감사가 필요
- 다음 작업:
  - canary 200건 병렬 실행
  - risk discovery 1,000건 정성 샘플 리뷰
  - validation 10,000건 개선 전후 비교

## IMP-20260427-008 - Canary 200 Failure Triage And Search Long-Tail Guard

- 상태: verified_canary / quality_review
- 우선순위: P0
- 관련 run id:
  - `20260427_002737_046977`
  - `20260427_030848_374214`
- 관련 문서:
  - `docs/devs/VERIFICATION_RESULTS.md`
  - `docs/devs/SAMPLING_AND_PARALLEL_TEST_GUIDE.md`
- 문제:
  - 36개 shard가 모두 정상이어도 200건 canary가 `199/200`에서 막힘.
  - `[Errno 22] Invalid argument`가 105건 failed checkpoint를 만들어 실제 판정을 오염.
  - `anime`로 감지된 post가 alias bridge 검색으로 이어져 비소설/타매체 long-tail과 false positive 위험을 만듦.
  - MCP client failover가 검색 1건에서 최대 36 endpoint를 순회할 수 있어 단일 검색 latency tail이 커짐.
- 조치:
  - `expert_main.py`: progress stderr write 실패를 무시하도록 방어.
  - `src/llm_batch/experts/orchestrator.py`: `hard_non_novel_media` guard 추가.
  - `src/llm_batch/search/client.py`: `MCP_CLIENT_SEARCH_TIMEOUT_SEC`, `MCP_CLIENT_MAX_ENDPOINTS_PER_SEARCH` 추가.
  - canary summary/recovered/stuck artifact 재생성.
- 확인:
  - `py_compile` 통과.
  - canary 전후 shard audit `ok=36/36`.
  - stuck 단일 재현 `11478694` 완료, manifest `completed_count=1`, `failed_count=0`.
  - 단일 재현 로그에서 `비소설 매체 간접 보강 차단` 확인.
  - 2차 200건 canary `20260427_121338_563339` 완료: checkpoint `200/200`, `failed=0`, missing `0`.
  - 2차 manifest: `completed_count=200`, `flushed_count=200`, `pending_count=0`, `failed_count=0`.
  - 2차 canary에서 1차 stuck `11478694` 완료: `703.9s`, `4 iterations`.
  - 사후 shard audit `out/search_shard_audit_20260427_134858.json`: `ok_count=36/36`, `bad_count=0`.
  - 2차 canary 리뷰 패킷 생성: `out/llm_judgment_reviews/llm_judgment_review_20260427_121338_563339_20260427_135409.md`, `selected=80`.
- 남은 위험:
  - 2차 canary 안정성은 통과했지만 long-tail 상위 `11457804=886.4s`, `11478694=703.9s`, `11456200=586.5s`는 운영 비용 위험.
  - 검색 오류 `81`, timeout `82`, infra no-result `220`이 남아 검색 품질 영향은 전문가 정성 리뷰 필요.
  - `슬레이어즈` 같은 라이트노벨/애니/원작 경계 케이스는 자동 품질 GO로 승인하지 않음.
- 다음 작업:
  - 같은 env/startup auto-manage 조건으로 1,000건 risk discovery 실행.
  - 80건 review packet adjudication으로 `ACCEPT/HOLD/REPROCESS/REJECT` 집계.
  - 10,000건 validation 전 long-tail 상위 post의 검색/LLM 단계별 병목 분석.

## IMP-20260427-009 - Post-Level Late Search Budget Guard

- 상태: verified_canary / quality_review
- 우선순위: P0
- 관련 run id:
  - reference smoke: `20260427_140716_814536`
  - 200 canary: `20260427_143145_922090`
- 관련 문서:
  - `docs/devs/FEATURE_IMPROVEMENT_TODO.md`
  - `docs/devs/VERIFICATION_RESULTS.md`
  - `docs/devs/SAMPLING_AND_PARALLEL_TEST_GUIDE.md`
- 문제:
  - 검색 batch 내부 cap은 존재하지만 verification/search/recall batch가 반복되면 post 단위 검색 수와 처리 시간이 계속 증가.
  - 2차 200건 canary에서 안정성은 통과했으나 long-tail 상위 post가 운영 비용 위험으로 남음.
- 조치:
  - `_execute_searches` 중앙 관문에서 `ctx.executed_queries` 기준 post 누적 late budget 적용.
  - early title/alias 탐색은 보존.
  - late iteration 또는 `abbreviation_verification`, `title_character_verification`, `decoder_recall_verification`, `auto_*`, `unresolved_term_*`, `refinement` batch는 iteration이 낮아도 예산 적용.
  - profile별 cap을 env로 조정 가능하게 추가.
- 기본값:
  - `LLM_ENABLE_LATE_TOTAL_SEARCH_BUDGET=1`
  - `LLM_LATE_TOTAL_SEARCH_MIN_ITERATION=3`
  - `core_fast_resolve=14`, `uncertain_core=16`, `adjacent_meta=10`, `adjacent_meta_cheap=6`, `quarantine_candidate=3`, `deep_research=24`, default `18`
- 확인:
  - `py_compile` 통과.
  - late budget targeted unit tests `3/3 OK`.
  - `11478694` 참고 smoke 완료: `completed_count=1`, `failed_count=0`, `291.8s`, `3 iterations`, 검색 실행 `13건`.
  - 36 shard 200건 canary 완료: checkpoint `200/200`, failed `0`, missing `0`.
  - 사후 shard audit `out/search_shard_audit_20260427_late_budget_postrun.json`: `ok=36/36`.
  - baseline `20260427_121338_563339` 대비 비교 문서 생성: `out/comparisons/query_gate_canary_200_20260427_baseline_vs_late_budget.md`.
  - late budget cap/exhausted 로그 `22/14` 확인.
  - 검색 오류 `81 -> 75`, timeout `82 -> 75`.
  - `11478694` `703.9s -> 361.7s`, `11456200` `586.5s -> 267.4s`.
- 남은 위험:
  - `11457804`는 `886.4s -> 911.5s`로 여전히 병목.
  - `11718077`은 `151.8s -> 496.2s`로 회귀.
  - relevant/title 증가분과 post별 판정 변화는 100건 전문가 리뷰 전 품질 GO로 승인하지 않음.
- 다음 작업:
  - `out/llm_judgment_reviews/llm_judgment_review_20260427_143145_922090_20260427_160810.md` 100건 adjudication.
  - `11457804`, `11718077` 단계별 병목 분석.
  - 1,000건 risk discovery 전후 결과 비교.

## IMP-20260427-010 - Improvement Test And Comparison Automation

- 상태: first_report_done / tool_required
- 우선순위: P1
- 관련 문서:
  - `docs/devs/CHECKLIST.md`
  - `docs/devs/SAMPLING_AND_PARALLEL_TEST_GUIDE.md`
  - `docs/devs/OPERATION_QUALITY_CHECKLIST.md`
- 문제:
  - 개선 구현 후 테스트 런, run audit, 개선 전후 비교, 리뷰 패킷 생성이 사람 기억에 의존하면 누락될 수 있음.
  - 수백만 건 운영에서는 작은 smoke 통과만으로 품질 개선을 승인하는 위험이 큼.
- 결정:
  - 기능/품질 개선은 `구현 -> 자동 테스트 런 -> run audit -> baseline/improved 비교 문서 -> LLM 리뷰 패킷`을 기본 루틴으로 둔다.
  - 자동화 도구가 없을 때도 수동 비교 문서를 남기며, 누락 사유를 히스토리에 기록한다.
- 완료 기준:
  - baseline run id와 improved run id를 입력해 비교 Markdown/JSON을 생성하는 도구 추가.
  - `VERIFICATION_RESULTS.md`에 비교 결과 경로와 gate 판정이 자동 또는 반자동으로 기록됨.
- 첫 적용:
  - late search budget 개선에서 수동/반자동 비교 리포트 생성 완료.
  - `out/comparisons/query_gate_canary_200_20260427_baseline_vs_late_budget.md`
  - `out/comparisons/query_gate_canary_200_20260427_baseline_vs_late_budget.json`
- 다음 작업:
  - `tools/compare_improvement_runs.py` 또는 기존 audit 도구 확장 설계.
  - 현재 비교 리포트 형식을 입력으로 재사용해 자동화 스크립트화.

## IMP-20260427-011 - Generic Relation And Character Parenthetical Guards

- 상태: targeted_verified / canary_required
- 우선순위: P1
- 관련 사례:
  - `11631298`: 무협 일반 세력명(`무림맹`, `마교`, `혈교`)만으로 `무림맹주 막내제자`가 후보/보조 참조에 남는 문제.
  - `11663540`: `주서연(전 버튜버가 하고 싶은데요)` 검색 증거가 있음에도 최종 official title로 닫히지 않는 문제.
- 관련 문서:
  - `docs/devs/FEATURE_IMPROVEMENT_TODO.md`
  - `docs/devs/VERIFICATION_RESULTS.md`
  - `docs/devs/HISTORY.md`
- 조치:
  - generic relation only demote 후 결과 필드의 후보/secondary reference를 비우고 interpretation을 재계산.
  - final consistency에서 search result parenthetical `캐릭터명(작품명)`을 직접 재구성하는 fallback 추가.
  - 캐릭터 anchor는 post/comment에 등장해야 하며, `전차`, `줄다리기`, 사건/게임/일반명사 parenthetical은 제외.
  - `confidence="High"` 문자열이 숫자 비교에서 오류를 내지 않도록 Orchestrator/Arbiter 경로 보정.
- 확인:
  - `py_compile` 통과.
  - targeted unittest `8/8 OK`.
  - `11631298`: afterfix6에서 비관련, title 후보 없음, secondary reference 없음.
  - `11663540`: afterfix8 단독 targeted에서 `전 버튜버가 하고 싶은데요`로 resolved.
- 남은 위험:
  - afterfix8 단독 결과에는 수정 전 Arbiter confidence 오류로 `verifier_technical_failure` 플래그가 남아 있음. 코드 수정 후 전체 canary에서 재발 여부 확인 필요.
  - 동명이인 캐릭터 parenthetical false positive는 200/1,000건에서 정성 리뷰가 필요.
- 다음 작업:
  - 동일 3건 3-shard rerun으로 confidence technical failure 소거 확인.
  - 200건 분산 canary에서 `generic_relation_only_demoted`, `character_parenthetical_title_resolved`, confidence type error를 집계.

### 2026-04-27 afterfix11 update

- 상태: targeted_verified / 200_canary_required
- 추가 조치:
  - `comparison_target`이 실제 작품 비교가 아니라 `주서연` 같은 약한 캐릭터 표면 후보일 때 parenthetical 작품 확정을 막지 않도록 final consistency 가드 추가.
  - 캐릭터 표면 후보를 `mentioned_works`/secondary reference에서 제거하는 정리 추가.
  - 회귀 테스트를 afterfix10 실패 형태로 강화.
- 확인:
  - `py_compile` pass.
  - targeted unittest `5/5 OK`.
  - `out/sampling/targeted_generic_character_3_20260427_afterfix11_result.json`:
    - `11631298`: non-relevant, title 후보/secondary 없음.
    - `11663540`: `전 버튜버가 하고 싶은데요` resolved, `character_talk`, `system_state=clean`.
    - `11549038`: `[Errno 22] Invalid argument` 재발 없음.
  - 로그에서 confidence type error와 `verifier_technical_failure` 재발 없음.
- 남은 위험:
  - targeted 3건은 품질 승인 근거가 아니므로 200건 canary와 1,000건 risk discovery에서 동명이인 캐릭터 parenthetical FP를 검토해야 함.

### 2026-04-27 afterfix11 200-canary update

- 상태: canary_verified / risk_discovery_required
- 실행:
  - `out/sampling/query_gate_canary_200_20260426.jsonl`를 `expert_main.py` startup shard auto-manage 방식으로 재처리.
  - WARP `36/36`, MCP health `36/36`, `parallel=8`.
- 확인:
  - `out/sampling/query_gate_canary_200_afterfix11_20260427_result.json`: `completed=200/200`, `failed=0`.
  - `Relevant=151`, `Identified=75`, `Total Time=5508.2s`.
  - audit `reason_error_count=0`, `verifier_technical_failure=0`, `Invalid argument=0`.
  - `11631298`: non-relevant/title 없음.
  - `11663540`: `전 버튜버가 하고 싶은데요` resolved.
  - `generic_relation_only_demoted=3`, `character_parenthetical_title_resolved=5`.
- 비교/리뷰 산출물:
  - `out/comparisons/query_gate_canary_200_late_budget_vs_afterfix11.md`
  - `out/comparisons/query_gate_canary_200_late_budget_vs_afterfix11.json`
  - `out/llm_judgment_reviews/llm_judgment_review_20260427_191203_030136_afterfix11.md`
  - `out/llm_judgment_reviews/llm_judgment_review_20260427_191203_030136_afterfix11.jsonl`
- 남은 위험:
  - late-budget 대비 changed `91/200`이라 LLM 정성 리뷰가 필요.
  - `search_upstream_zero=103`, `search_timeout=11`, `search_degraded_detected=11`은 검색 품질 별도 개선 항목으로 추적.

### 2026-04-27 afterfix11 qualitative adjudication update

- 상태: qualitative_review_done / risk_discovery_running
- 판독 산출물:
  - `out/llm_judgment_reviews/llm_judgment_review_20260427_191203_030136_afterfix11_adjudicated.jsonl`
  - `out/llm_judgment_reviews/llm_judgment_review_20260427_191203_030136_afterfix11_adjudicated.md`
  - `out/llm_judgment_reviews/llm_judgment_review_20260427_191203_030136_afterfix11_adjudication_summary.json`
- 판독 집계:
  - `ACCEPT=63`, `HOLD=24`, `RESEARCH=11`, `REPROCESS=15`, `REJECT=7`.
- 확인된 개선:
  - `11631298` generic relation only demote는 정성 리뷰에서도 ACCEPT.
  - `11663540` character parenthetical title rescue는 정성 리뷰에서도 ACCEPT.
- 추가 개선 필요:
  - common term/person/media parenthetical은 critical false positive가 남아 더 강한 domain/evidence gate가 필요.
  - 확인된 alias가 generic guard와 충돌하는 `서울마탑`, `망교성`, `폴랩`, `아생갤`은 alias rescue/whitelist 또는 stronger evidence path 필요.
  - multi-work/comparison post는 단일 title 과수렴 또는 noise false negative를 줄이는 별도 규칙이 필요.
- 확대 검증:
  - 1,000건 risk discovery run `20260427_212634_728016` 시작.
  - 입력 `out/sampling/query_gate_risk_discovery_1000_20260426.jsonl`.
  - 출력 예정 `out/sampling/query_gate_risk_discovery_1000_afterfix11_20260427_result.json`.

### 2026-04-27 afterfix11 1,000-risk-discovery update

- 상태: run_stability_go / quality_fix_required
- 실행 결과:
  - `out/sampling/query_gate_risk_discovery_1000_afterfix11_20260427_result.json`: `completed=1000/1000`, `failed=0`, `pending=0`.
  - `Relevant=746`, `Identified=351`, `Total Time=30852.1s`, `Avg Time/Post=30.9s`.
  - WARP `36/36`, MCP bridge health `36/36`.
- 감사/리뷰 산출물:
  - `out/sampling/query_gate_risk_discovery_1000_afterfix11_20260427_audit.json`
  - `out/sampling/query_gate_risk_discovery_1000_afterfix11_20260427_quality_summary.json`
  - `out/comparisons/query_gate_risk_discovery_1000_afterfix11_quality_review.md`
  - `out/llm_judgment_reviews/llm_judgment_review_20260427_212634_728016_risk1000_afterfix11.md`
- 감사:
  - `reason_error_count=0`
  - `search_timeout=29`
  - `search_upstream_zero=539`
  - `search_degraded_detected=130`
  - slang old/new/blocked `136/133/3`, bad remaining `0`
- 품질 위험:
  - `character_parenthetical_title_resolved=37`, 이 중 120건 REJECT의 4건이 그대로 재현.
  - malformed/generic official title 후보 `14`.
  - `generic_relation_only_demoted=8`, strong alias 과차단 포함.
  - relevant without title `395`.
- 개선 우선순위:
  - P0: character parenthetical bridge evidence/domain gate 강화.
  - P0: malformed/generic/영문 단독 official title validator 추가.
  - P0: generic guard 이후 confirmed/strong alias rescue 추가.
  - P1: multi-work/comparison post 보존.

### 2026-04-28 afterfix12 P0 title/alias gate update

- 상태: targeted_verified / canary_required
- 변경 요약:
  - final official title rejection profile 추가.
  - character parenthetical bridge가 nonwork/common/source metadata title을 승격하지 않도록 사전 차단.
  - generic relation only 이후 strong alias rescue 추가.
  - 단, `무림맹`, `마교`, `혈교` 등 세계관 일반 세력명은 rescue alias에서 제외.
- 테스트:
  - `py_compile`: pass.
  - targeted unittest `13/13 OK`.
- 실제 run:
  - `out/sampling/targeted_p0_afterfix12_core4_20260428_result.json`
    - `11689276`: `뮤지컬 배우` title 제거.
    - `11631298`: non-relevant/title 없음.
    - `11562020`: `서울에 마탑 세웠더니 돈이 미쳤다` resolved.
  - `out/sampling/targeted_p0_afterfix12_rashomon_20260428_result.json`
    - `11620037`: non-relevant/title 없음.
- 남은 위험:
  - core4 첫 실행에서 source metadata phrase가 freeze 단계에서 재발했으므로, 단건 재수정은 확인됐지만 200/1,000건 확대 검증 전 품질 GO는 불가.
  - `화귀`, `언니약혼`, `폴랩`, `망교성`은 아직 targeted 실제 run 미확인.

### 2026-04-28 afterfix12 36병렬 canary update

- 상태: parallel36_canary_verified / quality_review_required
- 실행:
  - run id `20260428_142042_238055`.
  - 입력 `out/sampling/query_gate_canary_200_20260426.jsonl`.
  - 출력 `out/sampling/query_gate_canary_200_afterfix12_parallel36_retry_20260428_result.json`.
  - `parallel=36`, startup WARP/MCP health `36/36`.
- 확인:
  - `completed=200/200`, `failed=0`, `Relevant=146`, `Identified=67`.
  - `11718070`: `Depressive disorder` FP 제거, non-relevant/title 없음.
  - `11631298`: non-relevant/title 없음 유지.
  - `11663540`: `전 버튜버가 하고 싶은데요` resolved 유지.
  - `11620037`: source metadata title 제거, non-relevant/title 없음.
  - `11562020`: strong alias rescue로 `서울에 마탑 세웠더니 돈이 미쳤다` resolved.
- 비교/리뷰:
  - `out/comparisons/query_gate_canary_200_afterfix11_vs_afterfix12_parallel36_20260428.md`
  - `out/llm_judgment_reviews/llm_judgment_review_20260428_142042_238055_afterfix12_parallel36.md`
- 남은 위험:
  - `11689276`은 title FP는 제거됐지만 adjacent 판정이 남음.
  - `11702067`, `11576520` 등 strong alias long-tail은 official title 미확정.
  - 1,000건 risk discovery 전 품질 GO는 불가.

## IMP-20260428-013 - Ambiguous Title Stem Search Neighbor Guard

- 상태: targeted_verified / canary_required
- 우선순위: P1
- 관련 run id:
  - source observation: `20260428_155230_844180`
  - targeted verification: `20260428_202817_029607`
- 관련 사례:
  - `11684407` (`마법소녀ㄴ 신아 집에서는 머리 풀고다니는건가`)
- 문제:
  - `마법소녀ㄴ`처럼 의도적 자모 오타형 표면이 복수 공식 제목의 공통 stem으로 존재하면, 검색 이웃 후보가 실제 비교/추천/은어 후보처럼 출력과 slang DB pending에 섞임.
  - 기존 결과에서 `불꽃의 마법소녀ㄴ`이 `comparison_target`, `recommendation_candidate`, `secondary_reference`로 남아 `마법소녀ㄴ -> 불꽃의 마법소녀ㄴ` pending 관측을 만들었음.
- 조치:
  - title stem 비교용 정규화는 `ㄱ-ㅎ/ㅏ-ㅣ` 자모를 보존.
  - locked official detail 후보가 decisive support를 가지면 공통 stem 검색 이웃은 locked rescue blocker에서 제외.
  - 공통 stem 검색 이웃을 outward reference roles에서 제거.
  - verifier/router prompt에 `ambiguous_title_stem` 규칙 추가.
- 확인:
  - `tests.test_agentic_pipeline_alias_contract`: `30 OK`.
  - 단건 실제 rerun `out/sampling/targeted_ambiguous_title_stem_11684407_afterfix13_20260428_result.json`.
  - 결과: `official_title=마법소녀ㄴ은 은퇴하고 싶다`, `work_resolution=resolved`, `comparison_target=null`, `secondary_reference_works=[]`.
- 남은 위험:
  - 같은 stem을 공유하는 다른 공식 제목이 실제 비교 대상으로 직접 언급되는 경우는 negative 테스트로 막았지만, 대형 표본에서 과차단 여부 재확인 필요.
  - 기존 slang DB pending 관측은 최신 재처리 결과 기준으로 stale cleanup/audit 필요.
- 다음 작업:
  - afterfix13 200건 canary.
  - 1,000건 risk discovery에서 common stem collision bucket 추가 집계.

## IMP-20260428-014 - Adjacent Relevance Legacy Flag And Budget Profile Cleanup

- 상태: regression_verified / canary_required
- 우선순위: P1
- 관련 문서:
  - `docs/devs/FEATURE_IMPROVEMENT_TODO.md`
  - `docs/devs/VERIFICATION_RESULTS.md`
  - `docs/devs/HISTORY.md`
- 문제:
  - `adjacent_relevant`는 작가/플랫폼/추천/장르 주변담론으로 보존해야 하지만 legacy `is_relevant=true`가 되면 핵심 작품 토론과 식별 성공으로 카운트됨.
  - 이 경로는 official title 확정, `Relevant/Identified` 지표, slang DB 저장 근거를 오염시킬 수 있음.
  - 검색 budget에서 작가/플랫폼 주변담론과 장르 토론을 같은 `adjacent_meta_cheap` 한도로 처리해 한쪽은 과검색, 한쪽은 공식 근거 확인 부족이 생길 수 있음.
- 조치:
  - final relevance 계산을 `topicality == core_relevant`로 제한.
  - prompt/router/arbiter에 adjacent는 legacy `is_relevant=false`, official title null 기본값이라고 명시.
  - `adjacent_meta_cheap`은 author/platform/meta 계열 `max_q=2`, genre/trope discussion 계열 `max_q=3`으로 분리.
- 확인:
  - targeted adjacent 실패 계열 7건 통과.
  - budget positive/negative 이웃 3건 통과.
  - `tests.test_agentic_pipeline_rework`: `145 OK`.
  - `tests.test_agentic_pipeline_alias_contract`: `30 OK`.
  - 변경 파일 `py_compile` 통과.
- 남은 위험:
  - 장르 토론의 3쿼리 budget은 회수 슬롯을 보존하지만, 200/1,000건 표본에서 false positive 증가 여부를 확인해야 함.
  - adjacent가 `topicality`로는 남아도 downstream exporter/slang DB가 legacy flag 대신 scope를 잘 참조하는지 canary에서 확인 필요.
- 다음 작업:
  - afterfix 계열 200건 canary에서 adjacent 누수율 집계.
  - 1,000건 risk discovery에서 `adjacent_relevant + official_title`, `adjacent_relevant + slang 저장 후보`를 별도 bucket으로 audit.

## IMP-20260428-015 - Namu Medical/Common Concept Title Guard

- 상태: risk_discovery_done / residual_fp_found
- 우선순위: P1
- 관련 run id:
  - source observation: `20260428_223800_568267`
  - targeted verification: `20260428_230857_637381`
- 관련 사례:
  - `11718111` (`나도 조현병으로 오해받은 적 있음`)
- 문제:
  - `조현병(정신분열병)` 같은 나무위키 일반 의학 항목이 `캐릭터명(작품명)` 패턴으로 오인됨.
  - 본문에 `웹소설`이라는 약한 매체 단어가 있어 기존 general concept guard가 완화됨.
  - URL-backed replacement가 나무위키 일반 개념 URL을 근거로 `official_title=조현병`을 되살림.
- 조치:
  - `medical_common_topic_title` final rejection profile 추가.
  - 의학/건강/현실 개념어는 작품 고유 앵커, 공식 플랫폼 detail URL, 안정 alias, verified character-work bridge가 없으면 hard reject.
  - character-parenthetical extraction과 URL-backed replacement가 final rejection profile을 공유.
  - title reject 시 관련 candidate/reference 필드를 같이 비워 residual title 누수를 차단.
- 확인:
  - targeted 5건 OK.
  - `tests.test_agentic_pipeline_rework`: `147 OK`.
  - `tests.test_agentic_pipeline_alias_contract`: `30 OK`.
  - `py_compile` 통과.
  - 단건 실제 rerun `out/sampling/targeted_medical_common_11718111_afterfix14_20260428_result.json`: `is_relevant=false`, title 없음, `medical_common_topic_demoted`.
- 확대 확인:
  - 200건 canary run id `20260428_233059_378617`: `completed=200/200`, `failed=0`, `pending=0`.
  - 1,001건 risk discovery run id `20260429_002511_375830`: `completed=1001/1001`, `failed=0`, `pending=0`.
  - 사전/사후 shard audit 모두 `ok=36/36`.
  - `11718070` ECT, `11631298` 무림맹, `11456200` 마법소녀ㄴ/폼체인지 검색 이웃은 title 없음.
  - `11616838`, `11198715` 마법소녀ㄴ positive stem은 `마법소녀ㄴ은 은퇴하고 싶다`로 resolved 유지.
- 남은 위험:
  - 실제 의료/질병 소재를 제목이나 핵심 설정으로 쓰는 웹소설 positive 이웃이 과차단될 수 있음.
  - 나무위키가 유일한 공식성 높은 work evidence인 장기표본에서 Namu fallback이 과하게 줄었는지 확인 필요.
  - `11718111`은 risk discovery에서 `정신과 의사`로 재발. 의학 일반어 guard만으로는 직업/현실 개념 title 승격을 충분히 막지 못함.
- 다음 작업:
  - weak evidence official title promotion guard로 확장.
  - `official_title_evidence=false` 또는 `post_spans/search_snippets/official_urls=0` 조합이 resolved를 이기지 못하도록 후처리 스코어 조정.

## IMP-20260429-016 - Weak Evidence Official Title Promotion Guard

- 상태: afterfix16_canary_go / afterfix17_risk_hold
- 우선순위: P1
- 관련 run id:
  - discovery: `20260429_002511_375830`
- 관련 사례:
  - `11718111 -> 정신과 의사`
  - `11684415 -> 小數, decimal number`
  - `11505857 -> Cecil`
  - `11713208 -> 코믹 메이플스토리`
  - `11684401 -> 추리 소설`
  - `11205227 -> 챌린지`
- 문제:
  - reason 내부에는 weak evidence 반론이 존재하지만 final title scoring이 플랫폼 URL, title_in_post, generic search bootstrap 점수로 resolved title을 확정한다.
  - `official_title_evidence=false`, `evidence_bucket=post_spans=0/search_snippets=0/official_urls=0`, `grounding_anchor=search_only`, `relation_judge:thematic_overlap_only`가 함께 있으면 title 확정이 아니라 HOLD/REPROCESS가 맞다.
  - 이 유형은 의학 일반어뿐 아니라 직업명, 인명, 장르명, 일반명사, 다른 매체명으로 확장된다.
- 해결 방향:
  - exact title blacklist 대신 evidence invariant 기반 guard를 추가.
  - weak evidence 조건에서는 `heretic_url_platform` 또는 URL-backed replacement 가산점만으로 official title 확정을 허용하지 않음.
  - 직접 앵커가 있는 positive 이웃은 유지: `나혼렙`, `마법소녀ㄴ은 은퇴하고 싶다`, `전 버튜버가 하고 싶은데요`, `서울에 마탑 세웠더니 돈이 미쳤다`.
- 완료 기준:
  - negative 이웃: `정신과 의사`, `小數`, `Cecil`, `추리 소설`, `챌린지` 계열은 title 없음 또는 unresolved/HOLD.
  - positive 이웃: 안정 약칭/작품 앵커/공식 플랫폼 detail URL이 닫힌 케이스는 resolved 유지.
  - targeted/unit 통과 후 200건 canary와 1,000건 risk discovery 자동 실행.
  - afterfix14에서 추출한 약한 근거 후보 35건의 resolved 재발률을 비교 문서에 기록.
- 진행:
  - afterfix15~16에서 weak literal/dictionary/medical unresolved demotion을 구현.
  - `tests.test_agentic_pipeline_rework`: `153 OK`.
  - `11718111` targeted afterfix16: `Relevant=0`, title 없음.
  - 200건 canary run id `20260429_175638_261091`: `completed=200/200`, `failed=0`, `Relevant=77`, `Identified=64`, audit `reason_errors=0`.
- 새 위험:
  - `11198715`는 afterfix16 canary에서 `마법소녀물 신전사가 되었다`로 오매칭 resolved.
  - afterfix17 broad alias hold 추가 후 단건에서는 오답 title은 제거됐지만 `Relevant=0`으로 과보수.
  - 따라서 1,000건 risk discovery는 보류하고, IMP-20260429-017에서 의도적 오타/자모 title alias 정책을 먼저 보강한다.

## IMP-20260429-017 - Intentional Typo/Jamo Title Alias Hold Policy

- 상태: afterfix19_risk_review / afterfix20_related_guard_running
- 우선순위: P1
- 관련 사례:
  - `11198715` (`마법소녀ㄴ 생각해보니 공백의 2년 어떻게 한거지`)
  - negative 이웃: `11456200` (`마법소녀ㄴ 생각해보니 이거 완전 폼체인지`)
- 문제:
  - `마법소녀ㄴ`처럼 장르어와 의도적 제목 표기가 겹치면 검색 결과가 복수 official detail 후보로 갈라진다.
  - 단일 official title로 잠그면 `마법소녀물 신전사가 되었다` 같은 오매칭이 생긴다.
  - 반대로 모든 broad alias를 비관련 처리하면 `세린/세진/계약/은퇴` 같은 작품 내부 단서가 있는 글까지 손실된다.
- 해결 방향:
  - broad alias stem은 단일 resolved title로 잠그지 않는다.
  - 본문에 캐릭터명/설정/전개/기간 단서가 있으면 `core_relevant + unresolved_work`로 유지한다.
  - candidate title의 stem과 body predicate가 함께 맞는 경우는 RESEARCH/HOLD 큐로 보내고, 캐릭터명 공식 연결이 없으면 slang DB 확정 저장은 금지한다.
- 완료 기준:
  - `11198715`는 오답 title 없이 관련-미확정 또는 정확한 후보로 처리.
  - `11456200`은 non-relevant/title 없음 유지.
  - `불꽃의 마법소녀ㄴ`, `마법소녀ㄴ은 은퇴하고 싶다` 공식 detail 이웃을 함께 단위 테스트와 canary 사례 점검에 포함.
- 진행:
  - `internal_work_signal_unresolved_recovered` guard 추가.
  - 실제 Gatekeeper 구조인 `detected_entities.possible_characters/titles`를 반영.
  - 내부 앵커 HOLD가 발생하면 locked official detail rescue도 title 확정 대신 보류.
  - `tests.test_agentic_pipeline_rework`: `155 OK`.
  - afterfix19 targeted `out/sampling/targeted_magicgirl_11198715_afterfix19_20260429_result.json`: `Relevant=1`, `Identified=0`, `official_title=null`, flag `internal_work_signal_unresolved_recovered`.
- 확대 확인:
  - afterfix19 200건 canary `20260429_204443_104695`: `completed=200/200`, `Relevant=73`, `Identified=54`.
  - afterfix19 1,001건 risk discovery `20260429_213837_418990`: `completed=1001/1001`, `Relevant=401`, `Identified=284`.
  - `11198715`은 관련-미확정 유지, `11456200`은 title 없음.
- 남은 위험:
  - `11616838`은 afterfix20 targeted에서 `마법소녀ㄴ은 은퇴하고 싶다`로 resolved. 실제 positive일 수 있으나 `11198715`과의 경계 기준을 계속 리뷰해야 함.
  - `11631298`는 broad alias 문제가 아니라 locked candidate bad metadata 문제로 재승격되어 IMP-20260430-018로 분리.
- 다음:
  - afterfix20 canary/risk에서 magicgirl stem 이웃을 계속 known-case 추출.

## IMP-20260430-018 - Locked Official Candidate Bad Metadata Guard

- 상태: afterfix20_guard_go / overall_quality_review
- 우선순위: P1
- 관련 run id:
  - discovery: `20260429_213837_418990`
  - targeted verification: `20260430_015935_598854`
  - canary verification: `20260430_021001_693350`
  - risk verification: `20260430_025849_885589`
- 관련 사례:
  - `11631298` (`무림맹에 시발 마교 혈교 대가리가 다 있네...`)
- 문제:
  - locked official candidate rescue가 `page_type=community_post`, `content_status=deleted`, `negative_evidence=url_is_community_post/url_deleted_or_unavailable`인 후보를 다시 resolved로 승격.
  - 본문은 `ㅋㅋㅋㅋ`뿐이고 제목의 `무림맹/마교/혈교`는 다수 무협 작품에 공통인 세력명이라, 검색 후보 하나가 있더라도 단일 작품 확정 근거가 부족함.
- 해결 방향:
  - exact title blacklist 대신 candidate metadata invariant를 사용.
  - bad page/content metadata가 있는 locked candidate는 single locked official rescue 후보에서 제외.
  - active official detail positive 이웃은 유지.
- 조치:
  - `_select_single_locked_official_candidate`에서 `community_post`, `deleted/unavailable`, `url_deleted_or_unavailable`, `url_is_community_post`, `url_is_listing`, `listing_only`, `title_url_mismatch`를 제외.
  - 단위 테스트 `test_locked_official_candidate_skips_deleted_community_page_signal`, `test_deleted_locked_candidate_does_not_resolve_generic_faction_reaction` 추가.
- 확인:
  - `py_compile` pass.
  - `tests.test_agentic_pipeline_rework`: `157 OK`.
  - targeted run `20260430_015935_598854`: `11631298`은 `is_relevant=false`, official title 없음.
  - canary run `20260430_021001_693350`: `completed=200/200`, `Relevant=73`, `Identified=57`, `reason_errors=0`, `11631298` title 없음.
  - risk run `20260430_025849_885589`: `completed=1001/1001`, `Relevant=382`, `Identified=277`, `reason_errors=0`, `11631298` title 없음.
- 남은 위험:
  - locked bad metadata guard 자체는 통과.
  - 전체 risk 품질은 `11505857 -> Cecil`, `11456200` 과복구 때문에 REVIEW.
- 다음:
  - IMP-20260430-019, IMP-20260430-020으로 잔존 FP를 분리.

## IMP-20260430-019 - Short Person/Character Surface False Title Bridge

- 상태: afterfix21_verified_risk
- 우선순위: P1
- 관련 run id:
  - discovery: `20260430_025849_885589`
  - targeted verification: `20260430_120419_466550`
  - canary verification: `20260430_121717_430655`
  - risk verification: `20260430_131615_234022`
- 관련 사례:
  - `11505857` (`암흑고라니는 사죄의 의미로 세실 야스편 하나 들고 오도록`) -> `Cecil`
- 문제:
  - 짧은 인명/캐릭터 표면이 검색 결과의 영문 title로 연결되어 resolved됨.
  - 본문은 `ㄹㅇ` 수준이라 작품 고유 설정/회차/공식 URL/캐릭터-작품 설명 근거가 부족함.
- 해결 방향:
  - character-parenthetical bridge는 본문 캐릭터 anchor와 검색 title/snippet의 `캐릭터명(작품명)` 또는 명확한 작품 설명을 함께 요구.
  - 짧은 인명 단독 표면은 title resolved가 아니라 RESEARCH/HOLD로 보냄.
  - exact `Cecil` blacklist가 아니라 short-person-surface + weak-work-evidence invariant로 처리.
- 조치:
  - `_pick_character_parenthetical_confirmed_title`에서 짧은 영어 인명형 title은 post-side work anchor가 없으면 resolved하지 않도록 제한.
  - 단위 테스트 `test_character_parenthetical_bridge_rejects_short_person_title_without_post_work_anchor` 추가.
- positive 보존:
  - `11663540 -> 전 버튜버가 하고 싶은데요`처럼 `주서연(작품명)` bridge가 명확한 경우.
- 확인:
  - `tests.test_agentic_pipeline_rework`: `159 OK`.
  - targeted/canary/risk에서 `11505857`은 `is_relevant=false`, official title 없음.
  - canary/risk에서 `11663540 -> 전 버튜버가 하고 싶은데요` 유지.
- 완료 기준:
  - 충족. afterfix21 risk 기준 `11505857` title 없음, positive 이웃 유지.

## IMP-20260430-020 - Internal Work Signal Trope-Only Over-Recovery

- 상태: afterfix21_verified_risk
- 우선순위: P1
- 관련 run id:
  - discovery: `20260430_025849_885589`
  - targeted verification: `20260430_120419_466550`
  - canary verification: `20260430_121717_430655`
  - risk verification: `20260430_131615_234022`
- 관련 사례:
  - `11456200` (`마법소녀ㄴ 생각해보니 이거 완전 폼체인지`)
- 문제:
  - official title은 막았지만 `internal_work_signal_unresolved_recovered`가 단일 캐릭터/폼체인지 트로프 일반론을 `core_relevant + unresolved`로 과복구.
- 해결 방향:
  - internal work signal은 복수 캐릭터 또는 캐릭터+작품 고유 설정/전개/회차/사건 밀도를 요구.
  - `폼체인지`, `변신`, 장르 일반 클리셰만으로는 rescue하지 않음.
- 조치:
  - trope-only 표면(`폼체인지`, `변신`, `의상`, `추가파츠`, `마법소녀`)은 strong plot hit 없이 internal work signal rescue 불가.
  - `승급`을 strong plot term에 추가해 `11616838`류 positive 이웃을 보존.
  - 단위 테스트 `test_internal_work_signal_does_not_rescue_multi_character_trope_only_form_change` 추가.
- positive 보존:
  - `11198715`, `11616838`처럼 구체 캐릭터와 설정/전개 단서가 같이 있는 글.
- 확인:
  - targeted/canary/risk에서 `11456200`은 non-relevant/title 없음.
  - risk에서 `11198715`, `11616838`은 관련-미확정 유지.
- 완료 기준:
  - 충족. afterfix21 risk 기준 negative/positive 이웃 모두 통과.

## IMP-20260430-021 - Afterfix21 Resolved Increase Review

- 상태: discovered_afterfix21_risk
- 우선순위: P1
- 관련 run id:
  - canary verification: `20260430_121717_430655`
  - risk verification: `20260430_131615_234022`
- 관련 지표:
  - afterfix20 risk: `Relevant=382`, `Identified=277`, `search_degraded_detected=174`, `search_upstream_zero=400`, `search_bridge_after_filter_zero=530`.
  - afterfix21 risk: `Relevant=396`, `Identified=308`, `search_degraded_detected=163`, `search_upstream_zero=436`, `search_bridge_after_filter_zero=434`.
- 문제:
  - known bad는 개선됐지만 resolved 수가 크게 늘어 false positive 증가 가능성을 배제할 수 없음.
  - 검색 bridge filter zero는 개선됐으나 upstream zero가 증가해 검색 상태 차이도 함께 분리해야 함.
- 해결 방향:
  - afterfix21 risk에서 새 resolved/저근거/title bridge 관련 표본을 추출해 전문가 판독 패킷 생성.
  - `ACCEPT/HOLD/REPROCESS/REJECT`로 분류해 recall 개선과 FP 증가를 분리.
- 완료 기준:
  - afterfix21 risk resolved 증가분 정성 리뷰 완료.
  - 다음 개선 항목이 실제 false positive 유형별로 분리됨.
