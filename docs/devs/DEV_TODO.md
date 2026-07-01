# Development TODO

코드, 인프라, 테스트, 도구처럼 개발 작업 자체에 가까운 항목을 관리한다.

## P0

- [x] MCP client endpoint failover 구현
  - 상태: verified
  - 관련 파일: `src/llm_batch/search/client.py`
  - 완료 기준: 워커 기본 shard 실패/저하 시 `MCP_ENDPOINTS`의 다른 endpoint 후보를 시도
  - 검증: failover 호출 확인, `py_compile` 통과
- [x] MCP client 검색 failover budget 구현
  - 상태: verified_canary / long_tail_review
  - 관련 파일: `src/llm_batch/search/client.py`
  - 완료 기준: 검색 1건당 client timeout과 failover endpoint 최대 수를 env로 제한
  - 검증: `py_compile` 통과, `11478694` 단일 재현 완료, 2차 200건 canary `20260427_121338_563339` checkpoint `200/200`
- [x] post별 late search 누적 예산 가드 구현
  - 상태: implemented_unit_verified / canary_required
  - 관련 파일: `src/llm_batch/experts/orchestrator.py`
  - 완료 기준: 반복 verification/recall 검색이 post 단위 예산을 초과하면 `_execute_searches` 중앙 관문에서 cap 또는 skip
  - 검증: `py_compile` 통과, late budget 단위 테스트 3건 통과
- [x] 병렬 progress 출력 실패 방어
  - 상태: verified_canary
  - 관련 파일: `expert_main.py`
  - 문제: timeout wrapper 이후 stderr pipe가 닫히면 완료 post도 `[Errno 22] Invalid argument` failed checkpoint로 기록될 수 있음
  - 검증: `py_compile` 통과, 2차 200건 canary `failed=0`
- [x] 시작 health check에서 `/readyz` 확인
  - 상태: verified
  - 관련 파일: `src/llm_batch/search/client.py`, `expert_main.py`
  - 완료 기준: bridge liveness만 정상이고 SearchXNG가 죽은 shard를 실패로 판정
- [x] readiness 실패 shard 자동 recreate
  - 상태: verified
  - 관련 파일: `expert_main.py`
  - 완료 기준: 로컬 자동 shard에서 실패 endpoint를 shard index로 변환해 `warp_shards.py recreate` 수행
- [x] shard 감사 도구 추가
  - 상태: verified
  - 관련 파일: `tools/audit_search_shards.py`
  - 완료 기준: MCP `/healthz`, `/readyz`, SearchXNG UI, Docker state를 JSON으로 기록
- [x] WARP shard status/trace subprocess timeout 추가
  - 상태: verified_parallel36
  - 관련 파일: `tools/warp_shards.py`
  - 문제: 36병렬 startup 중 `docker compose exec ... curl --max-time 10` 자체가 반환하지 않아 `warp_shards.py status --json`가 멈출 수 있음.
  - 조치: `warp-cli status`와 trace curl 호출에 subprocess timeout을 적용하고, `warp-cli`가 connected인 경우 trace timeout fallback을 기록.
  - 검증: `WARP_SHARDS_STATUS_EXEC_TIMEOUT_SEC=5` 상태 조회 정상 반환, afterfix12 36병렬 canary startup WARP/MCP health `36/36`.
- [x] LLM/전문가 정성 리뷰 패킷 생성 도구 추가
  - 상태: implemented
  - 관련 파일: `tools/build_llm_judgment_review_packet.py`
  - 완료 기준: checkpoint JSONL, run audit JSON, slang DB를 입력으로 사람이 읽을 Markdown과 JSONL 패킷 생성
- [x] 균형 회귀 입력 샘플 생성 도구 추가
  - 상태: implemented
  - 관련 파일: `tools/build_balanced_regression_input.py`
  - 완료 기준: must id, resolved/unresolved/slang/non-relevant/search-degraded bucket을 섞은 JSONL 입력과 manifest 생성
- [x] VLM 이미지 geometry guard 추가
  - 상태: implemented_unit_verified / server_canary_deferred
  - 관련 파일: `src/llm_batch/agentic_pipeline.py`, `tests/test_agentic_pipeline_rework.py`
  - 문제: `post_id=11589463`의 dcimg 이미지가 `application/octet-stream`으로 내려오지만 JPEG signature를 갖고 실제 크기는 `389x1`, 448 bytes였고, vLLM VLM 요청 직후 `500 Internal Server Error`와 후속 `502 Bad Gateway`가 반복됨.
  - 일반화: 특정 post id 차단이 아니라 JPEG/PNG/GIF/WebP/BMP dimension을 sniff하고, 0px/최소 크기 미만/극단 aspect ratio 이미지를 VLM 전송 전에 limitation으로 격리.
  - env: `LLM_VLM_MIN_IMAGE_WIDTH` 기본 `8`, `LLM_VLM_MIN_IMAGE_HEIGHT` 기본 `8`, `LLM_VLM_MAX_ASPECT_RATIO` 기본 `64`
  - 검증: `py_compile` 통과, `tests.test_agentic_pipeline_rework` 161건 OK
  - 남은 확인: vLLM 서버 재기동 후 post `11589463` 포함 소량 canary에서 `image_geometry_too_small:389x1` limitation과 서버 생존 확인

## P1

- [ ] LLM/후처리 규칙 일반화 감사 도구화
  - 상태: proposed
  - 문제: 품질 오답을 고칠 때 특정 post id, 특정 제목, 특정 검색 문자열을 직접 막는 방식으로 누적되면 대량 런에서 새 false positive/false negative를 만든다.
  - 원칙: 실패 사례는 `일반 의학/현실 주제`, `장르 일반어`, `검색 메타데이터 꼬리`, `타매체/인물명`, `댓글 보조 참조` 같은 실패 유형과 증거 조건으로 해결한다.
  - 관련 파일 후보: `src/llm_batch/agentic_pipeline.py`, `src/llm_batch/prompts/expert_prompts.py`, `tests/test_agentic_pipeline_rework.py`
  - 완료 기준: 새 품질 패치마다 exact 문자열 blacklist 여부, 범주형 lexicon 주석, positive/negative 이웃 테스트 존재 여부를 자동 또는 수동 체크리스트로 검증
- [ ] 개선 전후 자동 테스트/비교 리포트 도구화
  - 상태: mandatory_policy_added / proposed_tooling
  - 관련 파일 후보: `tools/compare_improvement_runs.py`, `tools/audit_expert_run_health.py`, `tools/build_llm_judgment_review_packet.py`
  - 완료 기준: baseline run과 improved run을 입력하면 동일 입력 여부, 200건 canary, 1,000건 risk discovery, manifest/checkpoint, timeout/degraded, top latency, known bad post 변화, slang/store 지표를 Markdown/JSON으로 생성
  - 검증 방법: 200건 canary와 1,000건 risk discovery baseline/improved 결과로 `out/comparisons/<baseline>_vs_<improved>.md` 생성 확인
- [ ] 품질 개선 후 200/1,000 자동 실행 wrapper
  - 상태: proposed
  - 관련 파일 후보: `tools/run_quality_improvement_validation.py`, `expert_main.py`, `tools/audit_expert_run_health.py`, `tools/build_llm_judgment_review_packet.py`
  - 완료 기준: 개선 라벨과 baseline run/input을 받으면 targeted 이후 200건 canary를 실행하고, canary 통과 시 1,000건 risk discovery와 리뷰 패킷 생성까지 진행
  - 실패 정책: canary가 `completed=200/200`, `failed=0`, `pending=0`을 만족하지 못하면 risk discovery를 중단하고 failure summary를 생성
  - 수동 검증 참고: afterfix14에서 정책을 수동 수행하여 canary `20260428_233059_378617`과 risk discovery `20260429_002511_375830` 완료, audit/review packet 생성까지 확인
  - 검증 방법: afterfix 계열 200건/1,000건 샘플에서 dry-run 또는 실제 run 한 세트를 wrapper로 완료
- [x] `audit_expert_run_health.py` sampling output 경로 옵션 추가
  - 상태: implemented_loop272 / approval blocked
  - 문제: sampling output은 `out/sampling/<name>_checkpoint.jsonl`에 있는데 audit 도구는 기본 `out/expert_result_<run_id>_checkpoint.jsonl`만 찾아 수동 복사가 필요함.
  - 2026-07-02 Loop266 조치: `expert_result_*_manifest.json`의 `manifest.run_id` lookup으로 internal run id와 output prefix가 다른 진행 중 대형 run은 감사 가능해졌다. 단, 임의 sampling 경로를 `--checkpoint` 등으로 직접 지정하는 기능은 아직 남아 있다.
  - 2026-07-02 Loop267 조치: `--artifact-prefix`, `--manifest`, `--checkpoint`, `--pending-snapshot`, `--log-glob`를 추가해 custom/sampling artifact 경로를 직접 감사할 수 있게 했다.
  - 2026-07-02 Loop268 조치: `--result-json`과 `result_rows` 감사를 추가해 manifest/checkpoint/result/pending 정합성을 한 audit JSON에서 비교할 수 있게 했다.
  - 2026-07-02 Loop269 조치: `flush_integrity` classifier를 추가해 clean completion, ordered flush gap, artifact count mismatch를 `GO/IN_PROGRESS/NO-GO`로 분리한다.
  - 2026-07-02 Loop270 조치: `flush_integrity.frontier`를 추가해 `next_save_idx`가 checkpoint/pending에 있는지 또는 in-flight/missing인지 기록한다.
  - 2026-07-02 Loop271 조치: `--input-jsonl`과 `flush_integrity.frontier.source_post`를 추가해 frontier `global_idx`의 원본 post_id/title/url/source_line을 기록한다.
  - 2026-07-02 Loop272 조치: `search_evidence` gate를 추가해 manifest direct search-health, row-level `search_health`, worker log 검색 저하 신호를 `GO/REVIEW/SEPARATE_AUDIT_REQUIRED/NO-GO`로 분리한다.
  - 완료 기준: `--checkpoint`, `--result-json`, `--manifest`, `--pending-snapshot` 또는 output prefix 옵션으로 sampling 결과를 직접 감사.
  - 검증: `tests.test_audit_expert_run_health` `12` tests OK, Loop264 진행 중 run search evidence audit `out\regression_safe_grounding_20260626_000008_928006_loop01\review\loop272_search_evidence_health_audit.json`.
- [ ] 장시간 런 중 shard readiness 주기 snapshot
  - 상태: proposed
  - 관련 파일 후보: `expert_main.py`, `src/llm_batch/monitor/*`
  - 완료 기준: N분 단위 shard 상태가 run id와 함께 저장되고 bad shard가 새 post 배정 전에 감지됨
  - 검증 방법: 장시간 샘플 런에서 snapshot 파일 또는 monitor event 생성 확인
- [ ] post별 search health flag 저장
  - 상태: proposed
  - 관련 파일 후보: `src/llm_batch/agentic_pipeline.py`, `src/llm_batch/models.py`
  - 완료 기준: 검색 빈 결과/저하/timeout이 결과 JSON에서 후처리 대상으로 식별됨
- [ ] 대형 병렬 validation 실행 스크립트 정리
  - 상태: proposed
  - 관련 파일 후보: `expert_main.py`, `tools/build_balanced_regression_input.py`
  - 완료 기준: 200/1,000/10,000건 표본을 같은 env/shard/worker 설정으로 재현 실행할 수 있음
- [ ] `pytest` 실행 환경 정리
  - 상태: proposed
  - 문제: 로컬 `venv`/`.venv312` 환경에 `pytest`가 없으면 전체 테스트 실행 불가
  - 최신 관측: 2026-04-29 afterfix14 검증 중 `.\venv\Scripts\python.exe -m pytest tests\test_agentic_pipeline_rework.py -q`가 `No module named pytest`로 실패
  - 완료 기준: 테스트 실행 방법이 문서화되거나 dev dependency로 정리됨

## P2

- [ ] README에서 `docs/devs` 링크 추가
  - 상태: proposed
  - 완료 기준: 운영/개발 문서 허브를 README에서 바로 찾을 수 있음
- [ ] 문서 갱신 루틴 자동 점검
  - 상태: proposed
  - 완료 기준: 기능 변경 시 관련 docs/devs 항목 확인이 체크리스트에 남음
