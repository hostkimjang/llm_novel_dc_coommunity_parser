# Operation Quality Checklist

대량 런과 품질 승인에 쓰는 운영 게이트다. 최종 판정은 `GO`, `REVIEW`, `NO-GO` 중 하나로 남긴다.

## 1. 검색 Shard / MCP Reliability

- [ ] `tools/audit_search_shards.py --count <N>` 실행
- [ ] `ok_count == count`
- [ ] `bad_count == 0`
- [ ] 모든 shard의 `/healthz` 정상
- [ ] 모든 shard의 `/readyz.payload.searxng == true`
- [ ] SearchXNG UI 포트 정상
- [ ] Docker state에서 `Running=true`, `OOMKilled=false`, `Dead=false`
- [ ] `mcp-bridge`, `searchxng`, `browser-search`, `warp`가 exited/restarting/dead 상태가 아님
- [ ] WARP snapshot에서 `warp=on`
- [ ] `MCP_HEALTH_USE_READYZ=1`
- [ ] `MCP_CLIENT_ENDPOINT_FAILOVER=1`
- [ ] `MCP_CLIENT_ENDPOINT_BACKOFF_SEC` 설정 확인

게이트:

- `GO`: `ok_count == count`, `bad_count == 0`
- `NO-GO`: bad shard 1개 이상, `/readyz` 실패, SearchXNG UI 실패
- `REVIEW`: 정상화됐지만 `Exited (137)`, `can't start new thread`, `Resource temporarily unavailable`, `pthread_create failed`, DNAT/iptables fork 실패 흔적이 있음

## 2. Run Audit

- [ ] `tools/audit_expert_run_health.py --run-id <RUN_ID>` 실행
- [ ] `checkpoint_rows == manifest.completed_count`
- [ ] `pending_count_actual == manifest.pending_count`
- [ ] `status_counts.failed == 0` 또는 실패 post id/원인 문서화
- [ ] `reason_error_count == 0` 또는 known issue 문서화
- [ ] `fatal_or_trace_line == 0` 권장
- [ ] `llm_connection_refused` 반복 여부 확인
- [ ] `search_upstream_zero` 확인
- [ ] `search_degraded_detected` 확인
- [ ] `search_bridge_after_filter_zero` 확인
- [ ] `search_timeout` 확인
- [ ] `headless_engine_counts` 확인
- [ ] worker별 degradation top 확인

게이트:

- `GO`: checkpoint/manifest 정합성 통과, fatal trace 0, shard 장애 없음
- `REVIEW`: run은 완료됐지만 검색 저하율 상승, failed/reason error 소수 존재, pending/flush 차이 존재
- `NO-GO`: 정합성 실패, fatal trace 증가, shard 장애 동반 결과를 품질 승인하려는 경우

## 2-1. VLM/OCR Image Payload Reliability

- [ ] VLM enabled run에서 `VLM chunk request` 직후 `500 -> 502` fanout이 있는지 확인
- [ ] `image_geometry_invalid`, `image_geometry_too_small`, `image_aspect_ratio_extreme` limitation 카운트 확인
- [ ] dcimg `application/octet-stream` 응답이 signature sniffing으로 image 처리되는 경우 dimension guard가 적용되는지 확인
- [ ] 새 degenerate 이미지가 발견되면 post id가 아니라 width/height/aspect ratio 같은 일반화 기준으로 차단
- [ ] 서버 재기동 후 known incident post `11589463` 포함 소량 canary에서 VLM request 미발생과 서버 생존 확인

게이트:

- `GO`: degenerate image는 limitation으로 격리되고, VLM request 직후 500/502 fanout이 없음
- `REVIEW`: limitation은 기록되지만 dashboard/audit 집계가 부족하거나, unknown-dimension 포맷이 섞여 추가 파서 검토 필요
- `NO-GO`: 동일 이미지/동일 geometry 계열이 VLM payload로 들어가 serving crash를 재현

## 3. Slang DB Audit

- [ ] `slang_insight_count` 확인
- [ ] `old_store_true_count` 확인
- [ ] `new_store_true_after_patch_count` 확인
- [ ] `old_store_true_blocked_by_patch_count` 확인
- [ ] `blocked_reason_counts` 확인
- [ ] `blocked_samples` 수동 검토
- [ ] `slang_db/slang_db.json` title count 확인
- [ ] slang term count 확인
- [ ] family aliases count 확인
- [ ] sentence-like term 오염 수 확인
- [ ] title과 완전 동일 alias 오염 수 확인

게이트:

- `GO`: 문장형 term 오염 0, title 동일 alias 오염 0, review 후보 처리됨
- `REVIEW`: 오염은 0이지만 `unclear_canonical_alias` 실제 약칭 후보가 남음
- `NO-GO`: `sentence_or_exact_bad_remaining > 0`

## 4. Sampling / Parallel Regression

- [ ] `docs/devs/SAMPLING_AND_PARALLEL_TEST_GUIDE.md` 기준으로 표본 단계 기록
- [ ] 4~20건 스모크를 품질 승인 근거로 쓰지 않음
- [ ] canary 입력 100~500건 이상 생성
- [ ] risk discovery 입력 1,000~3,000건 이상 생성
- [ ] validation 입력 10,000건 이상 생성 또는 전체 run 100% 자동 감사와 결합
- [ ] 검색 저하, unresolved, slang 후보, non-relevant 경계, 정상 대조군 포함
- [ ] 같은 post id를 개선 전후 재처리해 false positive/false negative 변화를 비교
- [ ] 병렬 실행 시 shard 수, worker 수, env override를 문서에 기록
- [ ] 기능/품질 개선 후 자동 테스트 런을 실행하고 baseline 대비 비교 문서를 생성
- [ ] 품질 개선 targeted/unit 통과 후 200건 canary를 기본 후속 작업으로 실행
- [ ] 200건 canary가 `completed=200/200`, `failed=0`, `pending=0`이면 1,000건 risk discovery를 이어서 실행
- [ ] 200건 canary 실패 시 1,000건으로 진행하지 않고 failure summary, stuck/failed post, shard/search 상태를 기록
- [ ] 즉시 실행하지 못한 경우 defer 사유와 재개 명령을 `HISTORY.md`/`TODO.md`에 기록
- [ ] 비교 문서에 baseline run id, improved run id, 입력 JSONL, 명령, env, 주요 지표 delta를 포함
- [ ] top latency, timeout/degraded, failed/pending, known bad post id 변화가 누락되지 않음

게이트:

- `GO`: 100% 자동 감사와 대형 validation/정성 리뷰가 함께 완료됨
- `REVIEW`: 200건 canary와 1,000건 risk discovery는 완료됐지만 정성 리뷰/validation이 남음
- `NO-GO`: 수백만 건 운영 변경을 4~20건 스모크나 targeted만으로 승인하거나, canary 통과 없이 risk discovery/validation으로 넘어가려는 경우

## 5. 대시보드 / 문서 갱신

- [ ] run audit 요약 문서 또는 대시보드 갱신
- [ ] shard audit 요약 문서 또는 대시보드 갱신
- [ ] slang DB 품질 지표 문서 또는 대시보드 갱신
- [ ] 개선 전후 비교 요약 문서 갱신
- [ ] audit JSON 경로 기록
- [ ] 실행 명령 기록
- [ ] 남은 TODO 기록

게이트:

- `GO`: 운영자가 문서/대시보드만 보고 현재 상태를 판단할 수 있음
- `REVIEW`: 코드 개선은 됐지만 대시보드 반영이 남음
- `NO-GO`: 새 reliability/slang/품질 변경이 있는데 검증 문서 또는 개선 전후 비교 문서가 없음

## 6. 일반화 / 하드코딩 방지 게이트

- [ ] 실패 사례가 특정 post id/제목 문자열이 아니라 재사용 가능한 실패 유형으로 기록됨
- [ ] LLM 프롬프트 변경은 "예시 암기"가 아니라 판단 rubric/증거 조건을 강화함
- [ ] 코드 변경에 exact bad-title blacklist가 추가됐다면 범주형 lexicon으로 대체 가능한지 검토함
- [ ] 범주형 lexicon은 `의학/건강`, `장르 일반어`, `검색 메타데이터`, `타매체`처럼 이름과 목적이 명확함
- [ ] positive rescue 케이스와 negative veto 케이스를 같은 테스트 묶음에서 검증함
- [ ] known bad 사례의 통과만으로 승인하지 않고, 200/1,000건 표본에서 새 FP/FN을 재확인함

게이트:

- `GO`: 실패 유형 정의, 범주형 규칙/프롬프트, 이웃 케이스 회귀 테스트, 표본 재확인이 모두 남음
- `REVIEW`: 단일 사례는 고쳤지만 일반화 근거 또는 이웃 케이스 검증이 부족함
- `NO-GO`: 특정 post id/제목/검색 문자열을 직접 하드코딩해 대량 런에 투입하려는 경우

## 7. LLM / 전문가 정성 리뷰

- [ ] `tools/build_llm_judgment_review_packet.py --run-id <RUN_ID>` 실행
- [ ] 검색 저하 + slang 후보 위험군 포함
- [ ] resolved title 저근거/고신뢰 케이스 포함
- [ ] unresolved/multi_work 경계 케이스 포함
- [ ] non-relevant 오분류 가능 케이스 포함
- [ ] `unclear_canonical_alias` 후보 포함
- [ ] 정상군 대조 샘플 포함
- [ ] 2인 독립 리뷰 또는 최종 조정자 판정 기록
- [ ] `ACCEPT/HOLD/RESEARCH/REPROCESS/REJECT` 집계 기록

게이트:

- `GO`: 필수 위험군 정성 리뷰 완료, DB 반영 후보 확정, 재처리 대상 분리
- `REVIEW`: 패킷은 생성됐지만 리뷰가 미완료이거나 `RESEARCH/REPROCESS` 대상이 남음
- `NO-GO`: 정성 리뷰가 필요한 run을 리뷰 없이 품질 승인하려는 경우

## 2026-04-26 판정

- 관련 run id: `20260423_170321_250907`
- 최초 shard 상태: `ok=27/36`, bad `[1,10,13,15,26,27,29,33,34]` -> `NO-GO`
- recreate 후 shard 상태: `ok=36/36` -> shard gate `GO`
- 이후 병렬 smoke 실행으로 테스트용 shard 2개가 자동 구성됨: `out/search_shard_audit_20260427_000659.json`, `ok=2/2`
- slang DB: 오염 0, `unclear_canonical_alias` 후보 14 -> `REVIEW`
- 정성 리뷰: 패킷 생성/전문가 판정 필요 -> `REVIEW`
- 전체 판정: `REVIEW`
- 이유: 검색 인프라는 정상화됐지만 shard 장애가 섞인 20k run 결과는 검색 안정화 후 대형 샘플 재처리가 필요함. 4건 smoke는 승인 근거가 아님.

## 2026-04-27 판정 - query gate 200 canary auto rerun

- 관련 run id: `20260427_121338_563339`
- 입력: `out/sampling/query_gate_canary_200_20260426.jsonl`
- 실행 경로: `expert_main.py` startup auto-manage, `--no-auto-up-shards` 미사용
- shard 상태:
  - startup health: `ok=36/36`
  - 사후 audit: `out/search_shard_audit_20260427_134858.json`, `ok_count=36`, `bad_count=0`
  - shard reliability gate: `GO`
- run 상태:
  - checkpoint `200/200`
  - manifest `completed_count=200`, `flushed_count=200`, `pending_count=0`, `failed_count=0`
  - 1차 stuck `post_id=11478694` 완료, `703.9s`
  - run stability gate: `GO`
- sampling/regression 상태:
  - canary 200건 완료.
  - 1,000건 risk discovery와 10,000건 validation은 아직 미완료.
  - sampling gate: `REVIEW`
- LLM/전문가 정성 리뷰:
  - 패킷: `out/llm_judgment_reviews/llm_judgment_review_20260427_121338_563339_20260427_135409.md`
  - `selected=80`, 검색 저하/은어/공식 제목 미확정/경계 케이스 포함.
  - adjudication 미완료.
  - qualitative gate: `REVIEW`
- 전체 판정: `REVIEW`
- 이유:
  - canary 안정성은 통과했지만 검색 오류 `81`, timeout `82`, infra no-result `220`, long-tail 상위 post가 남음.
  - 수백만 건 운영 승인 또는 10,000건 validation GO 전에는 80건 정성 리뷰와 1,000건 risk discovery가 필요함.

## 2026-04-27 판정 - late search budget guard

- 관련 변경: `src/llm_batch/experts/orchestrator.py`
- 자동 테스트:
  - `py_compile`: pass
  - targeted unit tests: `3/3 OK`
- 참고 실행:
  - `20260427_140716_814536`, `11478694`, `completed_count=1`, `failed_count=0`
  - shard `1/1` 및 최종 late-purpose refinement 전 시작된 smoke라 품질 gate로 사용하지 않음
- 현재 gate:
  - implementation gate: `GO`
  - canary/regression gate: `REVIEW`
  - qualitative gate: `REVIEW`
- 다음 gate 조건:
  - 36 shard / 200건 canary에서 `failed=0`, missing `0`
  - `late_budget_capped_total` 또는 `late_budget_exhausted_total` 발생 케이스가 false negative를 늘리지 않는지 전문가 리뷰
  - top latency 상위 post의 처리 시간과 검색 실행 수 감소 확인

## 2026-04-27 판정 - late search budget 200 canary comparison

- 관련 run id:
  - baseline: `20260427_121338_563339`
  - improved: `20260427_143145_922090`
- 비교 문서:
  - `out/comparisons/query_gate_canary_200_20260427_baseline_vs_late_budget.md`
  - `out/comparisons/query_gate_canary_200_20260427_baseline_vs_late_budget.json`
- run 상태:
  - checkpoint `200/200`
  - manifest `completed_count=200`, `flushed_count=200`, `pending_count=0`, `failed_count=0`
  - 사후 shard audit `out/search_shard_audit_20260427_late_budget_postrun.json`: `ok=36/36`
  - run stability gate: `GO`
- 비교 상태:
  - 검색 오류 `81 -> 75`
  - timeout `82 -> 75`
  - identified title `72 -> 76`
  - relevant `148 -> 153`
  - late budget cap/exhausted `22/14`
  - total time `5452.3s -> 5453.8s`
  - comparison gate: `REVIEW`
- LLM/전문가 정성 리뷰:
  - 패킷: `out/llm_judgment_reviews/llm_judgment_review_20260427_143145_922090_20260427_160810.md`
  - `selected=100 from rows=200`
  - qualitative gate: `REVIEW`
- 전체 판정: `REVIEW`
- 이유:
  - 안정성은 통과했고 late budget guard도 실제 발동했지만, 결과 품질은 사람이 읽어야 한다.
  - `11478694`, `11456200` tail은 개선됐으나 `11457804`, `11718077`은 회귀/잔류 병목이다.
  - infra no-result `220 -> 244`와 output 판정 변화가 있어 1,000건 risk discovery 전 전문가 adjudication이 필요하다.

## 2026-04-27 판정 - afterfix11 qualitative adjudication

- 관련 run id: `20260427_191203_030136`
- canary 상태:
  - checkpoint `200/200`
  - failed `0`, pending `0`
  - WARP/MCP startup health `36/36`
  - run stability gate: `GO`
- 정성 리뷰:
  - 원본 패킷: `out/llm_judgment_reviews/llm_judgment_review_20260427_191203_030136_afterfix11.md`
  - 판독 산출물: `out/llm_judgment_reviews/llm_judgment_review_20260427_191203_030136_afterfix11_adjudicated.md`
  - 집계: `ACCEPT=63`, `HOLD=24`, `RESEARCH=11`, `REPROCESS=15`, `REJECT=7`
  - qualitative gate: `REVIEW`
- 확대 검증:
  - 1,000건 risk discovery 완료: run id `20260427_212634_728016`
  - 입력: `out/sampling/query_gate_risk_discovery_1000_20260426.jsonl`
  - 출력: `out/sampling/query_gate_risk_discovery_1000_afterfix11_20260427_result.json`
  - 결과: `completed=1000/1000`, `failed=0`, `pending=0`, `Relevant=746`, `Identified=351`
  - audit: `out/sampling/query_gate_risk_discovery_1000_afterfix11_20260427_audit.json`
- 전체 판정: `REVIEW`
- 이유:
  - `11631298`, `11663540` known bad는 정성 리뷰에서도 개선 인정.
  - 그러나 1,000건에서 parenthetical bridge critical FP 4건이 재현됐고, malformed/generic official title 후보 14건, strong alias 과차단이 확인되어 후속 rule 개선이 필요하다.

## 2026-04-28 판정 - afterfix12 P0 targeted gate

- 관련 변경:
  - final official title validator
  - character parenthetical false positive gate
  - generic relation strong alias rescue
- 자동 테스트:
  - `py_compile`: pass
  - targeted unittest: `13/13 OK`
- 실제 targeted run:
  - core4 run id `20260428_123539_845850`, `completed=4/4`, `failed=0`
  - `11689276`: title 없음, adjacent.
  - `11631298`: non-relevant/title 없음.
  - `11562020`: title resolved.
  - `11620037`: core4 첫 실행에서 source metadata title 재발.
  - rashomon 단건 rerun id `20260428_124339_828427`: `11620037` non-relevant/title 없음.
- gate:
  - implementation/targeted gate: `GO`
  - 200/1,000 canary gate: `REVIEW`
  - qualitative gate: `REVIEW`
- 다음 gate 조건:
  - 200건 canary에서 known critical FP 재발 없음.
  - 1,000건 risk discovery에서 malformed/generic title 후보 감소.
  - strong alias rescue가 `서울마탑` 외 long-tail(`화귀`, `언니약혼`, `폴랩`, `망교성`)에서 false positive 없이 작동하는지 리뷰.

### 2026-04-28 addendum - ECT medical chatter gate

- 관련 post: `11718070`
- 실제 run id: `20260428_132300_821816`
- 결과:
  - `is_relevant=false`
  - official title 없음
  - `topicality=unrelated`
  - `work_resolution=none`
  - `consistency_flags=medical_common_topic_demoted`
- gate 영향:
  - targeted ECT gate: `GO`
  - broader medical/nonwork generalization gate: `REVIEW`

### 2026-04-28 addendum - Namu medical/common concept title gate

- 관련 post: `11718111`
- 실제 run id: `20260428_230857_637381`
- 결과:
  - `is_relevant=false`
  - official title 없음
  - `discussion_type=noise`
  - `topicality=unrelated`
  - `work_resolution=none`
  - `consistency_flags=medical_common_topic_demoted`
- regression:
  - `tests.test_agentic_pipeline_rework`: `147 OK`
  - `tests.test_agentic_pipeline_alias_contract`: `30 OK`
  - `py_compile`: pass
- gate 영향:
  - targeted Namu medical concept gate: `GO`
  - broader Namu fallback/medical positive-neighbor gate: `REVIEW`

## 2026-04-28 판정 - afterfix12 36병렬 canary

- 관련 run id: `20260428_142042_238055`
- 입력: `out/sampling/query_gate_canary_200_20260426.jsonl`
- 출력: `out/sampling/query_gate_canary_200_afterfix12_parallel36_retry_20260428_result.json`
- 실행 조건:
  - `expert_main.py` startup auto shard 관리 경로.
  - `MCP_SHARD_COUNT=36`, `MCP_AUTO_SHARD_LIMIT=36`, `--parallel 36`.
  - startup WARP `36/36`, MCP bridge health `36/36`.
- run 상태:
  - checkpoint `200/200`
  - manifest `completed_count=200`, `failed_count=0`, `pending_count=0`
  - `Relevant=146`, `Identified=67`
  - `Total Time=2473.3s`, `Avg Time/Post=12.4s`
  - run stability gate: `GO`
- shard 상태:
  - 사전 수동 audit은 `ok=4/36`이라 startup auto 재정리 경로를 사용.
  - `tools/warp_shards.py` status/trace timeout 보정 후 startup 확인 통과.
  - 사후 audit `out/search_shard_audit_20260428_after_afterfix12_parallel36_retry.json`: `ok=36/36`, `bad=[]`
  - shard reliability gate: `GO`
- 일반화/이웃 케이스:
  - `11718070`: medical/common-topic FP 제거.
  - `11631298`: generic faction/worldbuilding FP 차단 유지.
  - `11663540`: character parenthetical positive 회수 유지.
  - `11620037`: source metadata title 오염 제거.
  - `11562020`: strong alias positive rescue 확인.
  - `11702067`, `11576520`: relevant지만 title 미확정으로 alias long-tail review 필요.
  - generalization gate: `PARTIAL-GO`
- 정성 리뷰:
  - 패킷: `out/llm_judgment_reviews/llm_judgment_review_20260428_142042_238055_afterfix12_parallel36.md`
  - selected `120/200`
  - adjudication 미완료.
  - qualitative gate: `REVIEW`
- 전체 판정: `REVIEW`
- 이유:
  - 실행/검색 shard 안정성은 통과했고, afterfix11 critical FP 일부는 제거됐다.
  - 하지만 adjacent/relevant 경계와 strong alias long-tail이 남아 1,000건 risk discovery 및 120건 리뷰 판독 전 품질 승인은 보류.

## 2026-04-29 판정 - afterfix14 canary/risk discovery

- 관련 run id:
  - canary: `20260428_233059_378617`
  - risk discovery: `20260429_002511_375830`
- 입력:
  - canary: `out/sampling/query_gate_canary_200_20260426.jsonl`
  - risk discovery: `out/sampling/query_gate_risk_discovery_1000_plus11718111_afterfix14_20260429.jsonl`
- 출력:
  - canary result: `out/sampling/query_gate_canary_200_afterfix14_20260428_result.json`
  - risk result: `out/sampling/query_gate_risk_discovery_1000_plus11718111_afterfix14_20260429_result.json`
  - risk audit: `out/sampling/query_gate_risk_discovery_1000_plus11718111_afterfix14_20260429_audit.json`
  - risk review packet: `out/llm_judgment_reviews/llm_judgment_review_20260429_002511_375830_risk1000_afterfix14.md`
- run 상태:
  - canary `completed=200/200`, `failed=0`, `pending=0`, `Relevant=70`, `Identified=61`.
  - risk discovery `completed=1001/1001`, `failed=0`, `pending=0`, `Relevant=381`, `Identified=297`.
  - risk runtime `13487.3s`, 평균 `13.5s/post`.
- shard 상태:
  - 사전 audit: `out/search_shard_audit_20260429_before_afterfix14_risk1000.json`, `ok=36/36`.
  - 사후 audit: `out/search_shard_audit_20260429_after_afterfix14_risk1000.json`, `ok=36/36`.
  - shard reliability gate: `GO`.
- audit:
  - `reason_errors=0`
  - `slang_db_bad_remaining=0`
  - `search_timeout=4`
  - `search_degraded_detected=173`
  - `headless_naver_playwright=184`, `headless_google_cloak=18`
- 품질 확인:
  - `11718070`: ECT/우울증 치료 일반글은 non-relevant/title 없음.
  - `11631298`: 무림맹 일반 세력어는 non-relevant/title 없음.
  - `11456200`: 마법소녀ㄴ/폼체인지 검색 이웃은 non-relevant/title 없음.
  - `11616838`, `11198715`: 마법소녀ㄴ positive stem resolved 유지.
  - `11066247`: 다중 애니 캐릭터/트로프 글은 adjacent/title 없음.
- 실패/리뷰:
  - `11718111`: `정신과 의사`로 resolved 재발. targeted 통과만으로는 대형 표본 품질 승인이 불가함을 확인.
  - `11684415`: `小數, decimal number`로 resolved. reason 내부는 `official_title_evidence=false`, `post_spans=0`, `search_snippets=0`, `official_urls=0`.
  - `11505857`: `Cecil`로 resolved. 본문이 `ㄹㅇ`뿐인 인명/캐릭터 표면이라 title 확정 근거가 약함.
  - weak-evidence official title 후보 35건을 후속 개선 대상으로 분리.
- gate 영향:
  - run stability: `GO`
  - shard reliability: `GO`
  - known-case regression: `PARTIAL-GO`
  - production quality: `REVIEW`
- 다음 gate 조건:
  - weak-evidence official title guard targeted positive/negative 이웃 통과.
  - 개선 후 같은 정책으로 200건 canary와 1,000건 risk discovery 자동 재실행.
  - `11718111`, `11684415`, `11505857`이 title 없음/HOLD/REPROCESS로 이동하고, `나혼렙`, `마법소녀ㄴ`, `전 버튜버`, `서울마탑` positive가 유지되는지 확인.

## 2026-04-30 판정 - afterfix21 canary/risk discovery

- 관련 run id:
  - targeted: `20260430_120419_466550`
  - canary: `20260430_121717_430655`
  - risk discovery: `20260430_131615_234022`
- run 상태:
  - targeted `completed=5/5`, `Relevant=3`, `Identified=2`.
  - canary `completed=200/200`, `failed=0`, `pending=0`, `Relevant=82`, `Identified=65`.
  - risk `completed=1001/1001`, `failed=0`, `pending=0`, `Relevant=396`, `Identified=308`.
- audit:
  - canary `reason_errors=0`, `slang_db_bad_remaining=0`, `search_degraded_detected=25`.
  - risk `reason_errors=0`, `slang_db_bad_remaining=0`, `search_degraded_detected=163`, `search_upstream_zero=436`, `search_bridge_after_filter_zero=434`.
- 품질 확인:
  - `11505857`: short person/character surface false bridge 차단, title 없음.
  - `11456200`: trope-only internal work signal 과복구 차단, non-relevant/title 없음.
  - `11718070`, `11718111`, `11631298`: title 없음 유지.
  - `11663540`: `전 버튜버가 하고 싶은데요` resolved 유지.
  - `11198715`, `11616838`: risk에서 관련-미확정 유지.
- gate 영향:
  - run stability: `GO`.
  - known-case regression: `GO`.
  - production quality: `REVIEW`.
- REVIEW 사유:
  - afterfix20 risk 대비 afterfix21 risk `Identified=277 -> 308`, `Relevant=382 -> 396`으로 증가.
  - 증가분이 검색 회수율 개선인지 false positive 증가인지 정성 리뷰 전에는 production GO로 승인하지 않음.
- 다음 gate 조건:
  - afterfix21 risk resolved 증가분 리뷰 패킷 생성.
  - 고위험 resolved 표본을 `ACCEPT/HOLD/REPROCESS/REJECT`로 판독.
