# WARP Sharding Layout

`expert_main.py --parallel 4` 같이 여러 워커를 돌릴 때는, `searchxng`, `crawl4ai`, `browser-search`를 같은 WARP 번들에 묶고 `MCPClient`가 shard별 `mcp-bridge`를 고르게 하는 구성이 가장 단순하다.

운영 품질 게이트와 검증 결과는 `docs/devs/OPERATION_QUALITY_CHECKLIST.md`, `docs/devs/VERIFICATION_RESULTS.md`에 기록한다.

현재 goal/test regression에서는 `expert_main.py`가 로컬 자동 생성 shard(`localhost:3333+`)를 감지해도 Docker Compose lifecycle을 기본으로 열지 않는다. 소규모 run은 살아 있는 endpoint를 재사용/필터링하고, `--parallel`은 worker 최대치로만 해석한다. shard 복구 자체가 검증 대상일 때만 `--allow-goal-shard-lifecycle`과 `--auto-up-shards` 또는 `--auto-recreate-shards`를 함께 명시해 `tools/warp_shards.py up/recreate`를 실행한다. 수동으로 `MCP_ENDPOINTS` / `MCP_ENDPOINT` 를 지정한 경우에는 기존 구성을 존중하고, goal/test에서는 health filter 이후 사용 가능한 endpoint만 쓰는 계약을 우선한다.

또한 shard 상태감사 작업에서는 `expert_main.py` 시작 시 shard별 `warp-cli status` 와 Cloudflare trace(`ip`, `warp`, `loc`, `colo`)를 확인해서 `logs/warp_shards_status_*.json` 에 메모로 남길 수 있다. 일반 goal/test semantic regression에서는 Compose status/exec 기반 감사도 기본 경로가 아니며, 필요할 때만 `MCP_LOCAL_SHARD_STATUS_AUDIT=1`과 `MCP_ALLOW_GOAL_SHARD_STATUS_AUDIT=1`을 함께 명시한다.

핵심:

- shard 1: `warp-1 + searchxng-1 + crawl4ai-1 + browser-search-1 + mcp-bridge-1`
- shard 2: `warp-2 + searchxng-2 + crawl4ai-2 + browser-search-2 + mcp-bridge-2`
- ...
- host의 `expert_main.py`는 `MCP_ENDPOINTS=http://localhost:3333,http://localhost:3334,...` 로 shard를 라운드로빈 선택

이 저장소의 `MCPClient`는 `MCP_ENDPOINTS`를 읽고 클라이언트 생성 시 하나의 shard를 고정 선택한다. 따라서 한 워커 안의 `search()` / `fetch()`는 같은 `mcp-bridge`를 거쳐 같은 WARP 번들로 나간다.

## Compose Skeleton

아래 예시는 구조를 보여주는 샘플이다. `warp-*` 서비스는 질문에서 언급한 `cloudflare-warp-docker` 계열 이미지를 사용하거나, 별도 로컬 이미지로 교체해서 쓰면 된다.

```yaml
services:
  warp-1:
    image: your-warp-image:latest
    privileged: true
    restart: unless-stopped
    ports:
      - "19001:8080"  # SearchXNG UI는 같은 network namespace의 warp 서비스에서 노출한다.
    volumes:
      - ./docker/warp/state/warp-1:/etc/warp

  searchxng-1:
    image: searxng/searxng:latest
    restart: unless-stopped
    network_mode: "service:warp-1"
    volumes:
      - ./docker/searchxng/settings.yml:/etc/searxng/settings.yml:ro
    environment:
      - SEARXNG_BASE_URL=http://localhost:19001/
      - SEARXNG_SECRET=change-me-please-change

  crawl4ai-1:
    image: unclecode/crawl4ai:latest
    restart: unless-stopped
    network_mode: "service:warp-1"
    shm_size: "2g"
    environment:
      - CRAWL4AI_API_TOKEN=${CRAWL4AI_API_TOKEN:-}

  browser-search-1:
    image: llm-batch-browser-search:latest
    build:
      context: .
      dockerfile: docker/browser-search/Dockerfile
    restart: unless-stopped
    network_mode: "service:warp-1"
    shm_size: "2g"
    environment:
      - BROWSER_SEARCH_PROVIDER_ORDER=cloak
      - BROWSER_SEARCH_WAIT_MS=3000
      - BROWSER_SEARCH_GOOGLE_MIN_INTERVAL_SEC=45
      - BROWSER_SEARCH_GOOGLE_JITTER_SEC=15
      - BROWSER_SEARCH_BLOCK_COOLDOWN_SEC=7200

  mcp-bridge-1:
    build:
      context: .
      dockerfile: docker/mcp-bridge/Dockerfile
    restart: unless-stopped
    ports:
      - "3333:3333"
    environment:
      - SEARCHXNG_URL=http://warp-1:8080
      - CRAWL4AI_URL=http://warp-1:11235
      - HEADLESS_SEARCH_URL=http://warp-1:8765/search
      - MCP_PORT=3333
    depends_on:
      - warp-1
      - searchxng-1
      - crawl4ai-1
      - browser-search-1

  warp-2:
    image: your-warp-image:latest
    privileged: true
    restart: unless-stopped
    volumes:
      - ./docker/warp/state/warp-2:/etc/warp

  searchxng-2:
    image: searxng/searxng:latest
    restart: unless-stopped
    network_mode: "service:warp-2"
    volumes:
      - ./docker/searchxng/settings.yml:/etc/searxng/settings.yml:ro
    environment:
      - SEARXNG_BASE_URL=http://warp-2:8080/
      - SEARXNG_SECRET=change-me-please-change

  crawl4ai-2:
    image: unclecode/crawl4ai:latest
    restart: unless-stopped
    network_mode: "service:warp-2"
    shm_size: "2g"
    environment:
      - CRAWL4AI_API_TOKEN=${CRAWL4AI_API_TOKEN:-}

  mcp-bridge-2:
    build:
      context: .
      dockerfile: docker/mcp-bridge/Dockerfile
    restart: unless-stopped
    ports:
      - "3334:3333"
    environment:
      - SEARCHXNG_URL=http://warp-2:8080
      - CRAWL4AI_URL=http://warp-2:11235
      - MCP_PORT=3333
    depends_on:
      - warp-2
      - searchxng-2
      - crawl4ai-2

  warp-3:
    image: your-warp-image:latest
    privileged: true
    restart: unless-stopped
    volumes:
      - ./docker/warp/state/warp-3:/etc/warp

  searchxng-3:
    image: searxng/searxng:latest
    restart: unless-stopped
    network_mode: "service:warp-3"
    volumes:
      - ./docker/searchxng/settings.yml:/etc/searxng/settings.yml:ro
    environment:
      - SEARXNG_BASE_URL=http://warp-3:8080/
      - SEARXNG_SECRET=change-me-please-change

  crawl4ai-3:
    image: unclecode/crawl4ai:latest
    restart: unless-stopped
    network_mode: "service:warp-3"
    shm_size: "2g"
    environment:
      - CRAWL4AI_API_TOKEN=${CRAWL4AI_API_TOKEN:-}

  mcp-bridge-3:
    build:
      context: .
      dockerfile: docker/mcp-bridge/Dockerfile
    restart: unless-stopped
    ports:
      - "3335:3333"
    environment:
      - SEARCHXNG_URL=http://warp-3:8080
      - CRAWL4AI_URL=http://warp-3:11235
      - MCP_PORT=3333
    depends_on:
      - warp-3
      - searchxng-3
      - crawl4ai-3

  warp-4:
    image: your-warp-image:latest
    privileged: true
    restart: unless-stopped
    volumes:
      - ./docker/warp/state/warp-4:/etc/warp

  searchxng-4:
    image: searxng/searxng:latest
    restart: unless-stopped
    network_mode: "service:warp-4"
    volumes:
      - ./docker/searchxng/settings.yml:/etc/searxng/settings.yml:ro
    environment:
      - SEARXNG_BASE_URL=http://warp-4:8080/
      - SEARXNG_SECRET=change-me-please-change

  crawl4ai-4:
    image: unclecode/crawl4ai:latest
    restart: unless-stopped
    network_mode: "service:warp-4"
    shm_size: "2g"
    environment:
      - CRAWL4AI_API_TOKEN=${CRAWL4AI_API_TOKEN:-}

  mcp-bridge-4:
    build:
      context: .
      dockerfile: docker/mcp-bridge/Dockerfile
    restart: unless-stopped
    ports:
      - "3336:3333"
    environment:
      - SEARCHXNG_URL=http://warp-4:8080
      - CRAWL4AI_URL=http://warp-4:11235
      - MCP_PORT=3333
    depends_on:
      - warp-4
      - searchxng-4
      - crawl4ai-4
```

## Host-side env

host에서 일반 개발 샘플을 돌릴 때는 아래처럼 실행할 수 있다.

```bash
python expert_main.py tests/inputs/sample.jsonl --parallel 4
```

대형 shard bootstrap 또는 shard 복구 검증 모드에서는 아래 자동 관리 기능을 사용할 수 있다. 다만 goal/test regression의 기본 실행 계약은 reuse/filter이며, 아래 Docker lifecycle은 `--allow-goal-shard-lifecycle` opt-in 없이 열지 않는다.

- `--parallel 4` -> `3333,3334,3335,3336`
- 로컬 `WARP/SearchXNG/Crawl4AI/CloakBrowser browser-search/MCP` 4 shard 자동 `docker compose up -d --build`는 shard lifecycle opt-in이 있을 때만 수행
- 자동 생성 shard 수는 기본적으로 `--parallel` 값을 그대로 따른다. 필요하면 `MCP_SHARD_COUNT=6` 같이 별도 지정 가능
- `MCP_SHARD_BASE_PORT=4000` -> `4000,4001,4002,...`
- `MCP_SHARD_HOST=10.0.0.5` -> `http://10.0.0.5:3333,...`
- `MCP_SHARD_COUNT=6` -> `--parallel` 과 별개로 6개 shard 생성
- `WARP_SHARDS_SEARCH_UI_BASE_PORT=19001` -> SearchXNG UI를 `http://localhost:19001`, `19002`, ... 로 노출. `0`이면 UI 포트 노출 비활성화
- 대량 shard에서는 `warp_shards.py`가 shard 묶음을 배치 단위로 `docker compose up ... mcp-bridge-N` 해서 점진적으로 수렴시킨다
- shard 복구 모드의 `expert_main.py`는 auto-managed shard에서 `warp=off` 또는 미기동 shard가 보이면 해당 shard 번들을 다시 올리고, 모두 `warp=on` 이 될 때까지 기다린다
- `WARP_SHARDS_COMPOSE_PARALLEL=4` -> `docker compose` 엔진 호출 병렬도 제한
- `WARP_SHARDS_BATCH_SIZE=6` -> 한 번에 올릴 shard 배치 크기
- `WARP_SHARDS_WAIT_TIMEOUT=240` -> 배치별 `docker compose up --wait` 타임아웃(초)
- `WARP_SHARDS_BATCH_PAUSE_SEC=2` -> 배치 사이 쉬는 시간(초)
- `WARP_SHARDS_ENSURE_PAUSE_SEC=5` -> `warp=off` shard 재기동 뒤 다음 상태 확인까지 기다릴 시간(초)
- `WARP_SHARDS_ENSURE_MAX_ATTEMPTS=0` -> `warp=on` 보장 루프 최대 시도 횟수. `0`이면 제한 없이 계속 재시도
- `MCP_AUTO_SHARD_LIMIT=24` -> 정말 필요할 때만 자동 생성 shard 수 상한 지정 (기본은 제한 없음)
- `BROWSER_SEARCH_PROVIDER_ORDER=cloak` -> 기본값. 비용 없는 CloakBrowser 단일 fallback만 사용
- `BROWSER_SEARCH_PROVIDER_ORDER=playwright,ucd` 처럼 Google 직접 provider를 여러 개 이어붙이면 CAPTCHA 시 연쇄 재시도가 늘 수 있으므로 기본값을 권장
- `BROWSER_SEARCH_GOOGLE_MIN_INTERVAL_SEC=45` / `BROWSER_SEARCH_GOOGLE_JITTER_SEC=15` -> shard별 Google 직접 브라우저 검색 간격
- `BROWSER_SEARCH_BLOCK_COOLDOWN_SEC=7200` -> CAPTCHA/차단 징후 감지 시 해당 shard의 Google 직접 브라우저 검색 중단 시간
- `MCP_HEALTH_USE_READYZ=1` -> 시작 헬스체크에서 bridge liveness뿐 아니라 `/readyz` 기반 SearchXNG readiness도 확인
- `MCP_AUTO_SCALE_UP_MISSING_SHARDS=1` (기본) -> 대형 검증 런에서 autogen 로컬 shard 일부가 헬스체크에 **연결 거부(컨테이너 부재)** 로 빠지면(예: 16개만 기동된 상태에서 32개 필요) 부족 shard만 `warp_shards.py up --shards 17-32` + `--no-recreate`로 자동 증분 기동 후 실패 endpoint만 재검사. 기존 healthy 컨테이너는 compose up 대상 자체에서 제외된다. 소규모 goal/test 런(기존 2-key 허가+액션 opt-in 필요)·Codex 런(현재 커맨드 opt-in 필요)·`--reuse-shards-only`·`--no-auto-up-shards`에서는 동작하지 않음. `0`으로 비활성화
- `MCP_SCALE_UP_REPROBE_ATTEMPTS=12` / `MCP_SCALE_UP_REPROBE_PAUSE_SEC=10` -> 증분 기동 후 실패 endpoint 재검사 횟수/간격 (신규 shard WARP 등록 워밍업 시간 흡수용; 전부 회복되면 조기 종료)
- `warp_shards.py up --shards 17,19,20-32` -> compose 렌더는 `--count` 전체로 유지하되 지정 shard 서비스만 up. 단일 shard 영구 실패는 수집-계속(collect-and-continue)되어 나머지 shard 기동을 막지 않고 exit code 2로 보고
- `WARP_SHARDS_REMOVE_ORPHANS=0` -> `warp_shards.py up` 시 `--remove-orphans` 생략 (현재 풀 크기를 초과해 떠 있는 기존 컨테이너 보호용; expert_main 자동 증분 기동은 항상 `0`으로 호출)
- `WARP_SHARDS_NO_RECREATE=1` -> `warp_shards.py up` 시 `--no-recreate` 추가 — 정의/이미지 drift가 있어도 기존 컨테이너를 재생성하지 않고 없는 컨테이너만 생성 (expert_main 자동 증분 기동은 항상 `1`로 호출)
- `MCP_CLIENT_ENDPOINT_FAILOVER=1` -> 런 중 워커 기본 MCP shard가 실패하면 `MCP_ENDPOINTS` pool의 다른 endpoint로 우회
- `MCP_CLIENT_ENDPOINT_BACKOFF_SEC=90` -> 실패 endpoint를 클라이언트 쪽에서 잠시 제외하는 시간

shard 복구 모드에서 자동 기동을 명시적으로 끄려면:

```bash
python expert_main.py tests/inputs/sample.jsonl --parallel 4 --no-auto-up-shards
```

goal/test regression에서는 위 옵션을 붙이지 않아도 Docker lifecycle이 기본으로 열리지 않는다. 운영 실수를 줄이고 싶으면 `--reuse-shards-only`를 함께 사용한다.

WARP 연결 상태와 egress IP 확인:

```bash
python tools/warp_shards.py status
```

이 명령은 shard별로 아래를 출력한다.

- `warp-cli --accept-tos status`
- `curl https://www.cloudflare.com/cdn-cgi/trace`

`trace` 출력의 `ip=` 와 `warp=` 값을 보면 실제 WARP 경유 여부를 바로 확인할 수 있다.

특정 shard만 강제 재기동:

```bash
python tools/warp_shards.py recreate --shards 33,35-38
```

현재 shard readiness 감사:

```bash
python tools/audit_search_shards.py --count 36
```

이 명령은 MCP `/healthz`, MCP `/readyz`, SearchXNG UI 포트, Docker state를 `out/search_shard_audit_*.json`에 저장한다.

직접 지정:

```bash
export MCP_ENDPOINTS="http://localhost:3333,http://localhost:3334,http://localhost:3335,http://localhost:3336"
export MCP_ENDPOINT_STRATEGY="round_robin"
python expert_main.py tests/inputs/sample.jsonl --parallel 4
```

선택 전략:

- `round_robin`: 새 `MCPClient` 인스턴스가 생성될 때 shard를 순환 선택
- `random`: 무작위 shard 선택
- `first`: 첫 번째 shard 고정

## Why This Layout

- `searchxng`, `crawl4ai`, `browser-search-N`가 같은 `warp-N` 네트워크 namespace를 공유한다.
- `mcp-bridge-N`는 그 shard의 내부 주소만 보게 된다.
- 워커 단위로 MCP shard가 고정되므로, 한 게시글 처리 중 search/fetch가 섞여도 같은 WARP 번들을 쓴다.
- host에는 `mcp-bridge-*` 포트와 디버깅용 SearchXNG UI 포트(`19001+`)만 연다. `searchxng`가 `warp-N`의 네트워크 namespace를 공유하므로 UI 포트 publish도 `searchxng-N`가 아니라 `warp-N` 서비스에 둔다.

## 2026-04-26 운영 메모

`20260423_170321_250907` 20k 런 리뷰에서 일부 shard가 `Exited (1/137)` 상태로 남아 있었고, 브라우저에서 SearchXNG UI가 `ERR_EMPTY_RESPONSE`를 보였다. 대표 증상은 `19013`이었지만 실제 감사에서는 `1,10,13,15,26,27,29,33,34` shard가 문제로 잡혔다. 해당 shard bundle만 recreate한 뒤 재감사에서는 `36/36` 정상화됐다.

컨테이너 로그에서는 `can't start new thread`, `Resource temporarily unavailable`, `pthread_create failed`, Docker DNAT/iptables fork 실패가 확인됐다. 따라서 대량 병렬 처리에서는 WARP on 여부만으로 충분하지 않고, `mcp-bridge /readyz`와 SearchXNG UI 응답까지 readiness로 봐야 한다.

운영 순서:

1. `python tools/audit_search_shards.py --count N`으로 문제 shard를 확인한다.
2. `python tools/warp_shards.py recreate --shards <문제 shard 목록>`으로 해당 bundle만 재생성한다.
3. 재감사에서 `ok=N/N`이 될 때까지 반복한다.
4. 같은 현상이 반복되면 shard 수나 batch 기동 크기를 줄인다.
