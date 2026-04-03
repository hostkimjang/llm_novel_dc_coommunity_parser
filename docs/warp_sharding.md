# WARP Sharding Layout

`expert_main.py --parallel 4` 같이 여러 워커를 돌릴 때는, `searchxng`와 `crawl4ai`를 같은 WARP 번들에 묶고 `MCPClient`가 shard별 `mcp-bridge`를 고르게 하는 구성이 가장 단순하다.

현재는 `expert_main.py`가 로컬 자동 생성 shard(`localhost:3333+`)를 감지하면 `tools/warp_shards.py up --count N`을 먼저 실행해서 필요한 컨테이너를 자동 기동한다. 수동으로 `MCP_ENDPOINTS` / `MCP_ENDPOINT` 를 지정한 경우에는 기존 구성을 존중하고 자동 기동하지 않는다.

또한 `expert_main.py` 시작 시 shard별 `warp-cli status` 와 Cloudflare trace(`ip`, `warp`, `loc`, `colo`)를 확인해서 `logs/warp_shards_status_*.json` 에 메모로 남긴다.

핵심:

- shard 1: `warp-1 + searchxng-1 + crawl4ai-1 + mcp-bridge-1`
- shard 2: `warp-2 + searchxng-2 + crawl4ai-2 + mcp-bridge-2`
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
    volumes:
      - ./docker/warp/state/warp-1:/etc/warp

  searchxng-1:
    image: searxng/searxng:latest
    restart: unless-stopped
    network_mode: "service:warp-1"
    volumes:
      - ./docker/searchxng/settings.yml:/etc/searxng/settings.yml:ro
      - ./docker/searchxng/startpage_patched.py:/usr/local/searxng/searx/engines/startpage.py:ro
    environment:
      - SEARXNG_BASE_URL=http://warp-1:8080/
      - SEARXNG_SECRET=change-me-please-change

  crawl4ai-1:
    image: unclecode/crawl4ai:latest
    restart: unless-stopped
    network_mode: "service:warp-1"
    shm_size: "2g"
    environment:
      - CRAWL4AI_API_TOKEN=${CRAWL4AI_API_TOKEN:-}

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
      - MCP_PORT=3333
    depends_on:
      - warp-1
      - searchxng-1
      - crawl4ai-1

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
      - ./docker/searchxng/startpage_patched.py:/usr/local/searxng/searx/engines/startpage.py:ro
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
      - ./docker/searchxng/startpage_patched.py:/usr/local/searxng/searx/engines/startpage.py:ro
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
      - ./docker/searchxng/startpage_patched.py:/usr/local/searxng/searx/engines/startpage.py:ro
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
- 로컬 `WARP/SearchXNG/Crawl4AI/MCP` 4 shard 자동 `docker compose up -d --build`
- `MCP_SHARD_BASE_PORT=4000` -> `4000,4001,4002,...`
- `MCP_SHARD_HOST=10.0.0.5` -> `http://10.0.0.5:3333,...`
- `MCP_SHARD_COUNT=6` -> `--parallel` 과 별개로 6개 shard 생성

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

- `searchxng`와 `crawl4ai`가 같은 `warp-N` 네트워크 namespace를 공유한다.
- `mcp-bridge-N`는 그 shard의 내부 주소만 보게 된다.
- 워커 단위로 MCP shard가 고정되므로, 한 게시글 처리 중 search/fetch가 섞여도 같은 WARP 번들을 쓴다.
- host에는 `mcp-bridge-*` 포트만 열면 되고, `searchxng`/`crawl4ai`는 외부에 직접 노출할 필요가 없다.
