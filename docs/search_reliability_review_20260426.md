# Search Reliability Review - 2026-04-26

대상 런: `20260423_170321_250907`

이 문서는 20k 규모 expert run에서 검색 성능 저하가 확인된 뒤, 로그/결과/slang DB/shard 상태를 함께 검토한 운영 히스토리다.

개발 TODO/품질 게이트/검증 결과 색인은 `docs/devs/README.md`, `docs/devs/OPERATION_QUALITY_CHECKLIST.md`, `docs/devs/VERIFICATION_RESULTS.md`에서 관리한다.

## 확인 결과

- checkpoint 기준 `20,532` rows 중 `completed=20,531`, `failed=1`.
- manifest 기준 `completed_count=20,532`, `flushed_count=20,501`, `pending_count=31`.
- 로그 집계:
  - `search_upstream_zero=45,449`
  - `search_degraded_detected=13,263`
  - `search_bridge_after_filter_zero=2,166`
  - `search_timeout=102`
  - `headless_lines=1,243` (`headless_naver_playwright=1,057`, `headless_google_cloak=186`)
  - `llm_connection_refused=321`
- 현재 shard probe 기준 `36`개 중 `27`개 정상, 문제 shard는 `[1, 10, 13, 15, 26, 27, 29, 33, 34]`.
- Docker 상태에서 `mcp-bridge-1`은 `Exited (137)`, 여러 `searchxng-*`는 `Exited (1/137)`.
- 문제 shard recreate 후 재감사 기준 `36/36` 정상화.
- 컨테이너 로그/inspect에서 반복 확인된 핵심 원인:
  - `RuntimeError: can't start new thread`
  - `Resource temporarily unavailable`
  - `pthread_create failed`
  - Docker DNAT/iptables fork 실패

해석: 검색 품질 저하는 단순 검색엔진 랭킹 문제가 아니라, 대량 병렬 처리 중 일부 MCP/SearchXNG shard가 죽고도 endpoint pool에 남아 검색 호출이 빈 결과/저하/타임아웃으로 흘러간 영향이 크다.

## Slang DB 점검

- `slang_insight_count=1,817`
- 기존 저장 판단 `old_store_true=546`
- 현재 보정 기준 저장 판단 `new_store_true=532`
- 보정으로 차단된 후보 `14`, 모두 `unclear_canonical_alias`
- 현재 `slang_db/slang_db.json`:
  - `titles=340`
  - `family_aliases=1`
  - 문장형 term 또는 title과 완전 동일 alias 잔존 `0`

현 상태의 DB는 심각한 오염은 보이지 않는다. 다만 `빌환`, `무마`, `악엔`, `림조`, `드유`처럼 실제 약칭으로 보이는 후보 일부가 `unclear_canonical_alias`로 차단된 표본이 있어, 검색 안정화 후 회수율 관점에서 재검토가 필요하다.

## 이번 반영

- [x] `MCPClient`가 워커 기본 shard 실패 시 `MCP_ENDPOINTS` pool의 다른 endpoint로 failover하도록 보강.
- [x] `MCPClient.health_check(include_search=False)`에서도 `/readyz`를 확인해 bridge만 살아 있고 SearchXNG가 죽은 shard를 실패로 판정.
- [x] `expert_main.py` 시작 헬스체크 중 로컬 shard readiness 실패가 있으면 해당 shard bundle을 recreate 후 재확인.
- [x] `tools/audit_expert_run_health.py` 로그 읽기를 streaming 방식으로 바꾸고 worker별 검색 저하 top 지표 추가.
- [x] `tools/audit_search_shards.py` 추가. MCP `/healthz`, `/readyz`, SearchXNG UI, Docker state를 한 번에 기록.

## 운영 체크리스트

- [x] 20k 런 감사 실행: `tools/audit_expert_run_health.py`
- [x] 현재 shard 상태 감사 실행: `tools/audit_search_shards.py`
- [x] `slang_db` 적재/오염 지표 확인
- [x] 문제 shard recreate 후 `tools/audit_search_shards.py --count 36` 재실행 (`ok=36/36`)
- [ ] 같은 입력의 소량 재처리에서 `search_upstream_zero`, `search_degraded_detected` 비율 비교
- [ ] host thread/process 압박이 반복되면 `MCP_AUTO_SHARD_LIMIT`, `WARP_SHARDS_BATCH_SIZE`, `MCP_HEALTH_WORKERS` 하향 조정
- [ ] `unclear_canonical_alias`로 차단된 실제 약칭 표본을 active learning/review queue로 분리

## 재현/감사 명령

```powershell
.venv312\Scripts\python.exe tools\audit_expert_run_health.py --run-id 20260423_170321_250907
.venv312\Scripts\python.exe tools\audit_search_shards.py --count 36
.venv312\Scripts\python.exe tools\warp_shards.py recreate --shards 1,10,13,15,26,27,29,33,34
```

## 다음 개선 후보

- dead shard를 감지하면 현재 worker가 같은 post 안에서 즉시 다른 MCP endpoint로 재검색하는 failover가 우선이다.
- 시작 시 readiness 실패 shard는 유저 입력 대기 전에 자동 recreate를 먼저 시도해야 한다.
- 장시간 런에서는 N분마다 shard readiness snapshot을 남기고, 죽은 shard가 있으면 새 post 배정 전에 pool에서 제외하는 장치가 필요하다.
- 검색 실패가 많은 post는 결과 JSON에 `search_health_flags`를 명시해 후처리/재처리 대상으로 분리해야 한다.
