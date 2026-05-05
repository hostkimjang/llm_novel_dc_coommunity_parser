# WARP Sharding Layout

`expert_main.py --parallel 4` 같이 여러 워커를 돌릴 때는, `searchxng`, `crawl4ai`, `browser-search`를 같은 WARP 번들에 묶고 `MCPClient`가 shard별 `mcp-bridge`를 고르게 하는 구성이 가장 단순하다.

운영 품질 게이트와 검증 결과는 `docs/devs/OPERATION_QUALITY_CHECKLIST.md`, `docs/devs/VERIFICATION_RESULTS.md`에 기록한다.

현재는 `expert_main.py`가 로컬 자동 생성 shard(`localhost:3333+`)를 감지하면 `tools/warp_shards.py up --count N`을 먼저 실행해서 필요한 컨테이너를 자동 기동한다. 수동으로 `MCP_ENDPOINTS` / `MCP_ENDPOINT` 를 지정한 경우에는 기존 구성을 존중하고 자동 기동하지 않는다.

또한 `expert_main.py` 시작 시 shard별 `warp-cli status` 와 Cloudflare trace(`ip`, `warp`, `loc`, `colo`)를 확인해서 `logs/warp_shards_status_*.json` 에 메모로 남긴다. 자동 생성 shard에서 `warp=off` 가 감지되면 해당 shard 번들을 강제 재기동하고, 전부 `warp=on` 이 될 때까지 대기한 뒤 본 처리로 넘어간다.

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

host에서 `expert_main.py`를 돌릴 때는 기본적으로 그냥 아래처럼 실행하면 된다.

```bash
python expert_main.py tests/inputs/sample.jsonl --parallel 4
```

위처럼 실행하면 기본값으로 아래가 자동 처리된다.

- `--parallel 4` -> `3333,3334,3335,3336`
- 로컬 `WARP/SearchXNG/Crawl4AI/CloakBrowser browser-search/MCP` 4 shard 자동 `docker compose up -d --build`
- 자동 생성 shard 수는 기본적으로 `--parallel` 값을 그대로 따른다. 필요하면 `MCP_SHARD_COUNT=6` 같이 별도 지정 가능
- `MCP_SHARD_BASE_PORT=4000` -> `4000,4001,4002,...`
- `MCP_SHARD_HOST=10.0.0.5` -> `http://10.0.0.5:3333,...`
- `MCP_SHARD_COUNT=6` -> `--parallel` 과 별개로 6개 shard 생성
- `WARP_SHARDS_SEARCH_UI_BASE_PORT=19001` -> SearchXNG UI를 `http://localhost:19001`, `19002`, ... 로 노출. `0`이면 UI 포트 노출 비활성화
- 대량 shard에서는 `warp_shards.py`가 shard 묶음을 배치 단위로 `docker compose up ... mcp-bridge-N` 해서 점진적으로 수렴시킨다
- `expert_main.py`는 auto-managed shard에서 `warp=off` 또는 미기동 shard가 보이면 해당 shard 번들을 다시 올리고, 모두 `warp=on` 이 될 때까지 기다린다
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
- `MCP_CLIENT_ENDPOINT_FAILOVER=1` -> 런 중 워커 기본 MCP shard가 실패하면 `MCP_ENDPOINTS` pool의 다른 endpoint로 우회
- `MCP_CLIENT_ENDPOINT_BACKOFF_SEC=90` -> 실패 endpoint를 클라이언트 쪽에서 잠시 제외하는 시간

자동 기동을 끄려면:

```bash
python expert_main.py tests/inputs/sample.jsonl --parallel 4 --no-auto-up-shards
```

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
