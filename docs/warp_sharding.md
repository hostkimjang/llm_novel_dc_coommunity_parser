# 검색·WARP shard 운영 안내

`expert_main.py`는 검색과 fetch를 MCP bridge로 보낸다. 여러 worker를 돌릴 때는 `searchxng`, `crawl4ai`, `browser-search`를 같은 WARP 번들(shard)에 묶고, `MCPClient`가 shard별 `mcp-bridge`를 고르게 하는 구성이 가장 단순하다.

운영 품질 게이트와 검증 결과는 `docs/devs/OPERATION_QUALITY_CHECKLIST.md`, `docs/devs/VERIFICATION_RESULTS.md`에 기록한다.

## 검증 실행 예시

테스트런·검증런은 대시보드를 켠 상태(`--no-dashboard` 없음)에서 요청 병렬도 12로 실행한다. 기존 shard만 쓰고 Docker 기동·재생성을 하지 않으려면 `--reuse-shards-only`를 붙인다.

```bash
python expert_main.py tests/inputs/sample.jsonl --parallel 12 --reuse-shards-only
```

## 병렬도와 endpoint 구성

**worker 수.** `--parallel`은 worker 수의 상한이다. 실제 병렬도(effective parallel)는 요청값과 입력 게시글 수 중 작은 값이다. 시작할 때 health filter가 endpoint pool을 줄였다면 살아 있는 endpoint 수로도 제한된다. manifest의 requested/effective parallel과 병렬도 정책 문구를 함께 확인한다.

**endpoint 출처.** 다음 순서로 정해진다.

1. `MCP_ENDPOINTS`를 지정하면 중복을 제거해 그대로 쓴다.
2. `MCP_ENDPOINT` 하나만 지정하면 그 주소를 쓴다.
3. 둘 다 없으면 `MCP_SHARD_SCHEME`(기본 `http`), `MCP_SHARD_HOST`(기본 `127.0.0.1`), `MCP_SHARD_BASE_PORT`(기본 `3333`)로 endpoint를 자동 생성한다.

**자동 생성 수.** `MCP_SHARD_COUNT`가 있으면 그 값을 쓰고, 없으면 effective parallel에서 출발해 아래 상한을 차례로 적용한다.

| 상한 | 적용 조건 | 기본값 |
| --- | --- | --- |
| `MCP_AUTO_SHARD_LIMIT` | 값이 0보다 크고 `MCP_SHARD_COUNT`가 없을 때 | `0`(상한 없음) |
| 낮은 병렬도 상한 `MCP_SMALL_RUN_AUTO_SHARD_LIMIT` | effective parallel이 `MCP_SMALL_RUN_SHARD_THRESHOLD` 미만이고, `MCP_SHARD_COUNT`가 없고, 환경에 `MCP_AUTO_SHARD_LIMIT` 자체가 없을 때 | 기준 `10` 미만이면 `2`개 |
| goal 실행 상한 `MCP_GOAL_RUN_AUTO_SHARD_LIMIT` | 입력 수 기준 소규모 실행(아래)이면서 shard lifecycle이 막혀 있을 때. `MCP_SHARD_COUNT`를 지정해도 적용된다. | `8`개 |

`MCP_AUTO_SHARD_LIMIT`는 환경에 있기만 해도(값이 `0`이어도) 낮은 병렬도 상한 2개를 끈다.

**소규모 실행과 lifecycle.** 입력 게시글 수가 `MCP_GOAL_RUN_SHARD_LIFECYCLE_THRESHOLD`(기본 `36`) 이하이면 소규모(goal/test) 실행으로 본다. 이때 Docker Compose shard lifecycle(기동·재생성)은 기본으로 막혀 있다. 현재 명령에 `--allow-goal-shard-lifecycle`과 `--auto-up-shards` 또는 `--auto-recreate-shards`를 함께 줘야 `tools/warp_shards.py up/recreate`를 실행한다. `--reuse-shards-only`는 이 허가보다 우선해 lifecycle을 막는다. 이전 셸에서 남은 `MCP_AUTO_*` 환경 변수만으로는 소규모 실행의 shard를 기동·재생성하지 않는다. Codex에서 시작한 실행도 현재 명령의 opt-in이 필요하다.

**health filter.** 시작할 때 health check에 응답하지 않는 endpoint를 pool에서 뺄 수 있는 경우는 두 가지다.

- `--reuse-shards-only`: `MCP_REUSE_ONLY_FILTER_HEALTHY_AUTOGEN`(자동 생성) 또는 `MCP_REUSE_ONLY_FILTER_HEALTHY_ENDPOINTS`(직접 지정)가 켜져 있으면(기본 ON) 살아 있는 endpoint만 쓴다.
- 소규모 실행에서 lifecycle이 막힌 경우: `MCP_GOAL_RUN_FILTER_HEALTHY_AUTOGEN` 또는 `MCP_GOAL_RUN_FILTER_HEALTHY_ENDPOINTS`(기본 ON)에 따라 살아 있는 endpoint만 쓴다.

그 밖의 대형 검증에서 직접 지정한 endpoint가 실패하면 감추지 않고 실패로 드러낸다.

**누락 shard 증분 기동.** `MCP_AUTO_SCALE_UP_MISSING_SHARDS`(기본 `1`)는 자동 생성한 로컬 shard 일부가 health check에서 연결 거부(컨테이너 없음)로 빠졌을 때 부족한 shard만 띄우는 경로 하나를 제어한다. 예를 들어 shard가 16개만 떠 있는데 32개가 필요하면 `warp_shards.py up --shards 17-32`에 `--no-recreate`를 붙여 부족한 shard만 띄우고, 실패했던 endpoint만 다시 확인한다. 이미 정상인 컨테이너는 compose up 대상에서 빠진다. `0`은 이 증분 기동 경로만 끄며, `--auto-up-shards`·`--auto-recreate-shards` 같은 다른 lifecycle 동작은 각자의 조건을 따른다. 이 경로는 `--reuse-shards-only`, `--no-auto-up-shards`, lifecycle이 막힌 소규모 실행, 현재 명령 opt-in이 없는 Codex 실행, 직접 지정 endpoint, 로컬이 아닌 `MCP_SHARD_HOST`에서는 동작하지 않는다.

**shard 상태 감사.** 시작할 때 shard별 `warp-cli status`와 Cloudflare trace(`ip`, `warp`, `loc`, `colo`)를 `logs/warp_shards_status_*.json`에 남길 수 있다. 소규모 실행에서는 이 Compose status/exec 기반 감사도 기본 경로가 아니며, 필요할 때만 `MCP_LOCAL_SHARD_STATUS_AUDIT=1`과 `MCP_ALLOW_GOAL_SHARD_STATUS_AUDIT=1`을 함께 지정한다.

## shard 구성

shard N 하나는 다음 서비스로 이루어진다.

- `warp-N`: Cloudflare WARP 연결. 같은 shard의 다른 서비스가 이 컨테이너의 네트워크 namespace를 함께 쓴다.
- `searchxng-N`, `crawl4ai-N`, `browser-search-N`: 메타 검색, 페이지 fetch, 헤드리스 브라우저 검색
- `mcp-bridge-N`: 호스트 포트 `3333 + N - 1`로 열리는 MCP bridge

호스트의 `expert_main.py`는 `MCP_ENDPOINTS=http://localhost:3333,http://localhost:3334,...`의 endpoint 중에서 shard를 고른다. `MCPClient`는 클라이언트를 만들 때 shard 하나를 정해 쓰므로, 한 worker 안의 `search()`·`fetch()`는 같은 `mcp-bridge`를 거쳐 같은 WARP 번들로 나간다. 기본 shard가 실패하면 `MCP_CLIENT_ENDPOINT_FAILOVER`에 따라 pool의 다른 endpoint로 우회할 수 있다.

## Compose 파일 만들기

실제 shard 구성은 `tools/warp_shards.py`가 만든다. `render`는 `docker-compose.warp-shards.generated.yml`을 쓰고, `up`은 같은 구성으로 컨테이너를 띄운다.

```bash
python tools/warp_shards.py render --count 12
python tools/warp_shards.py up --count 12
```

생성 파일의 shard 1은 다음과 같다. 환경 변수 일부는 생략했다. shard 2부터는 서비스 이름의 번호와 호스트 포트만 1씩 늘어난다.

```yaml
services:
  warp-1:
    build:
      context: .
      dockerfile: docker/warp/Dockerfile
    privileged: true
    restart: unless-stopped
    environment:
      - WARP_LICENSE_KEY=${WARP_LICENSE_KEY:-}
      - WARP_MODE=${WARP_MODE:-warp+doh}
      - WARP_TUNNEL_PROTOCOL=${WARP_TUNNEL_PROTOCOL:-}
    ports:
      - "19001:8080"  # SearchXNG UI. searchxng가 warp의 network namespace를 쓰므로 warp 서비스에서 연다.
    volumes:
      - ./docker/warp/state/warp-1/var-lib:/var/lib/cloudflare-warp
      - ./docker/warp/state/warp-1/etc:/etc/warp

  searchxng-1:
    image: searxng/searxng:latest
    restart: unless-stopped
    network_mode: "service:warp-1"
    depends_on:
      - warp-1
    volumes:
      - ./docker/searchxng/settings.yml:/etc/searxng/settings.yml:ro
    environment:
      - SEARXNG_BASE_URL=http://localhost:19001/
      - SEARXNG_SECRET=${SEARXNG_SECRET:-change-me-please-change}

  crawl4ai-1:
    image: unclecode/crawl4ai:latest
    restart: unless-stopped
    network_mode: "service:warp-1"
    shm_size: "2g"
    depends_on:
      - warp-1
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
    depends_on:
      - warp-1
    environment:
      - BROWSER_SEARCH_PROVIDER_ORDER=${BROWSER_SEARCH_PROVIDER_ORDER:-cloak,naver}
      - BROWSER_SEARCH_GOOGLE_MIN_INTERVAL_SEC=${BROWSER_SEARCH_GOOGLE_MIN_INTERVAL_SEC:-45}
      - BROWSER_SEARCH_GOOGLE_JITTER_SEC=${BROWSER_SEARCH_GOOGLE_JITTER_SEC:-15}
      - BROWSER_SEARCH_BLOCK_COOLDOWN_SEC=${BROWSER_SEARCH_BLOCK_COOLDOWN_SEC:-7200}

  mcp-bridge-1:
    build:
      context: .
      dockerfile: docker/mcp-bridge/Dockerfile
    restart: unless-stopped
    ports:
      - "3333:3333"
    depends_on:
      - warp-1
      - searchxng-1
      - crawl4ai-1
      - browser-search-1
    environment:
      - SEARCHXNG_URL=http://warp-1:8080
      - SEARCHXNG_URLS=http://warp-1:8080
      - CRAWL4AI_URL=http://warp-1:11235
      - HEADLESS_SEARCH_URL=http://warp-1:8765/search
      - HEADLESS_SEARCH_ENABLED=${HEADLESS_SEARCH_ENABLED:-1}
      - MCP_PORT=3333
```

## 호스트에서 실행하기

일반 개발 샘플은 다음처럼 실행한다.

```bash
python expert_main.py tests/inputs/sample.jsonl --parallel 12
```

대형 shard bootstrap이나 shard 복구 검증에서는 아래 자동 관리 기능을 쓸 수 있다. 소규모 실행의 기본은 기존 shard 재사용과 health filter이며, Docker lifecycle은 앞에서 설명한 lifecycle 조건을 충족할 때만 열린다.

- effective parallel이 12이고 상한이 적용되지 않으면 `3333`부터 `3344`까지 endpoint 12개를 만든다.
- 로컬 WARP·SearchXNG·Crawl4AI·CloakBrowser browser-search·MCP shard의 자동 `docker compose up -d --build`는 shard lifecycle이 열려 있을 때만 실행한다.
- shard가 많으면 `warp_shards.py`가 shard를 배치로 나눠 `docker compose up ... mcp-bridge-N`을 실행하며 차례로 띄운다.
- shard 복구 모드의 `expert_main.py`는 자동 관리 shard 중 `warp=off`이거나 떠 있지 않은 shard를 발견하면 그 shard 번들을 다시 올리고, 모두 `warp=on`이 될 때까지 기다린다.
- `warp_shards.py up --shards 17,19,20-32`는 compose 파일은 `--count` 전체로 렌더하고 지정한 shard 서비스만 띄운다. shard 하나가 계속 실패해도 나머지 shard 기동은 이어 가고, 끝에 exit code 2로 알린다.

### endpoint·클라이언트 설정

| 환경 변수 | 기본값 | 의미 |
| --- | --- | --- |
| `MCP_SHARD_BASE_PORT` | `3333` | 자동 생성 endpoint의 시작 포트. `4000`이면 `4000,4001,4002,...` |
| `MCP_SHARD_HOST` | `127.0.0.1` | 자동 생성 endpoint의 호스트. `10.0.0.5`면 `http://10.0.0.5:3333,...` |
| `MCP_SHARD_COUNT` | 없음 | `--parallel`과 별개로 만들 shard 수. lifecycle이 막힌 소규모 실행에는 goal 실행 상한(기본 8)이 적용된다. |
| `MCP_AUTO_SHARD_LIMIT` | `0`(상한 없음) | 자동 생성 shard 수 상한. 이 변수가 환경에 있으면 낮은 병렬도 상한 2개는 적용되지 않는다. |
| `WARP_SHARDS_SEARCH_UI_BASE_PORT` | `19001` | SearchXNG UI를 `http://localhost:19001`, `19002`, ... 로 연다. `0`이면 UI 포트를 열지 않는다. |
| `MCP_HEALTH_USE_READYZ` | `1` | 시작 health check에서 bridge liveness와 함께 `/readyz`로 SearchXNG 준비 상태도 확인한다. |
| `MCP_CLIENT_ENDPOINT_FAILOVER` | `1` | 실행 중 worker의 기본 MCP shard가 실패하면 `MCP_ENDPOINTS` pool의 다른 endpoint로 우회한다. |
| `MCP_CLIENT_ENDPOINT_BACKOFF_SEC` | `90` | 실패한 endpoint를 클라이언트에서 잠시 빼 두는 시간(초) |

### Docker 기동·복구 설정

| 환경 변수 | 기본값 | 의미 |
| --- | --- | --- |
| `WARP_SHARDS_COMPOSE_PARALLEL` | `8` | `docker compose` 엔진 호출 병렬도. `COMPOSE_PARALLEL_LIMIT`가 있으면 그 값을 쓴다. |
| `WARP_SHARDS_BATCH_SIZE` | compose 병렬도와 같음 | 한 번에 올릴 shard 배치 크기 |
| `WARP_SHARDS_WAIT_TIMEOUT` | `180` | 배치별 `docker compose up --wait` 제한 시간(초) |
| `WARP_SHARDS_BATCH_PAUSE_SEC` | `1` | 배치 사이 대기 시간(초) |
| `WARP_SHARDS_ENSURE_PAUSE_SEC` | `5` | `warp=off` shard를 다시 띄운 뒤 다음 상태 확인까지 기다리는 시간(초) |
| `WARP_SHARDS_ENSURE_MAX_ATTEMPTS` | `0` | `warp=on` 확인 반복의 최대 횟수. `0`이면 제한 없이 다시 시도한다. |
| `WARP_SHARDS_REMOVE_ORPHANS` | `1` | `warp_shards.py up`에 `--remove-orphans`를 붙인다. `0`이면 생략해 현재 풀 크기를 넘는 기존 컨테이너를 보호한다. `expert_main`의 자동 증분 기동은 항상 `0`으로 호출한다. |
| `WARP_SHARDS_NO_RECREATE` | `0` | `1`이면 `warp_shards.py up`에 `--no-recreate`를 붙여, 정의나 이미지가 바뀌어도 기존 컨테이너는 다시 만들지 않고 없는 컨테이너만 만든다. `expert_main`의 자동 증분 기동은 항상 `1`로 호출한다. |
| `MCP_AUTO_SCALE_UP_MISSING_SHARDS` | `1` | 누락 shard 증분 기동 경로. 앞의 [병렬도와 endpoint 구성](#병렬도와-endpoint-구성) 참고 |
| `MCP_SCALE_UP_REPROBE_ATTEMPTS` / `MCP_SCALE_UP_REPROBE_PAUSE_SEC` | `12` / `10` | 증분 기동 뒤 실패한 endpoint를 다시 확인하는 횟수와 간격(초). 새 shard가 WARP에 등록되는 시간을 기다리기 위한 값이며, 모두 회복되면 일찍 끝난다. |

### 브라우저 검색 설정

| 환경 변수 | 기본값 | 의미 |
| --- | --- | --- |
| `BROWSER_SEARCH_PROVIDER_ORDER` | `cloak,naver` | 헤드리스 브라우저 검색 제공자 순서. 기본은 CloakBrowser를 먼저 쓰고 다음에 Naver 검색을 쓴다. `playwright`, `ucd` 같은 Google 직접 제공자를 여러 개 이어 붙이면 CAPTCHA가 날 때 연쇄 재시도가 늘 수 있으므로 기본값을 권장한다. |
| `BROWSER_SEARCH_GOOGLE_MIN_INTERVAL_SEC` / `BROWSER_SEARCH_GOOGLE_JITTER_SEC` | `45` / `15` | shard별 Google 직접 브라우저 검색의 최소 간격과 무작위 추가 지연(초) |
| `BROWSER_SEARCH_BLOCK_COOLDOWN_SEC` | `7200` | CAPTCHA나 차단 징후가 보이면 그 shard에서 Google 직접 브라우저 검색을 멈추는 시간(초) |

## 운영 명령

shard 복구 모드에서 자동 기동을 명시적으로 끄려면 다음처럼 실행한다. 소규모 실행에서는 이 옵션이 없어도 Docker lifecycle이 기본으로 열리지 않는다. 운영 실수를 줄이려면 `--reuse-shards-only`를 함께 쓴다.

```bash
python expert_main.py tests/inputs/sample.jsonl --parallel 12 --no-auto-up-shards
```

| 목적 | 명령 | 확인할 내용 |
| --- | --- | --- |
| WARP 연결 상태와 egress IP | `python tools/warp_shards.py status` | shard별 `warp-cli --accept-tos status`와 `curl https://www.cloudflare.com/cdn-cgi/trace` 출력. `trace`의 `ip=`, `warp=` 값으로 실제 WARP 경유 여부를 본다. |
| 특정 shard만 다시 만들기 | `python tools/warp_shards.py recreate --shards 33,35-38` | 지정한 shard 번들만 재생성한다. |
| shard 준비 상태 감사 | `python tools/audit_search_shards.py --count 36` | MCP `/healthz`·`/readyz`, SearchXNG UI 포트, Docker 상태를 `out/search_shard_audit_*.json`에 저장한다. |

endpoint를 직접 지정할 때는 다음처럼 실행한다.

```bash
export MCP_ENDPOINTS="http://localhost:3333,http://localhost:3334,http://localhost:3335,http://localhost:3336"
export MCP_ENDPOINT_STRATEGY="round_robin"
python expert_main.py tests/inputs/sample.jsonl --parallel 12
```

`MCP_ENDPOINT_STRATEGY`(기본 `round_robin`)는 새 `MCPClient`가 shard를 고르는 방식이다.

- `round_robin`: 새 `MCPClient`를 만들 때마다 shard를 차례로 돌아가며 고른다.
- `random`: 무작위로 고른다.
- `first`: 첫 번째 shard만 쓴다.

## 이 구성을 쓰는 이유

- `searchxng-N`, `crawl4ai-N`, `browser-search-N`이 같은 `warp-N` 네트워크 namespace를 공유한다.
- `mcp-bridge-N`은 그 shard의 내부 주소만 본다.
- worker마다 MCP shard가 정해지므로, 게시글 하나를 처리하는 동안 search와 fetch가 섞여도 같은 WARP 번들을 쓴다.
- 호스트에는 `mcp-bridge-*` 포트와 디버깅용 SearchXNG UI 포트(`19001`부터)만 연다. `searchxng-N`이 `warp-N`의 네트워크 namespace를 공유하므로 UI 포트도 `searchxng-N`이 아니라 `warp-N` 서비스에서 연다.

## 과거 운영 기록

아래는 당시의 기록이며 현재 동작을 보장하는 설명이 아니다.

### 2026-07-06 Loop496: shard 1 UI 복구 중 orphan 제거

shard 1의 SearchXNG 호스트 UI 연결이 끊겨 `warp_shards.py render --count 16` 뒤 `up --count 16 --shards 1`로 복구했다. 이때 compose가 현재 count 밖의 shard `17-44`를 orphan으로 보고 제거했다. 당시 full375 실행은 shard `1-16`만 써서 문제가 없었지만, 16개를 넘게 쓰는 후속 실행은 먼저 필요한 shard를 다시 `up`해야 한다. 더 큰 풀을 보존해야 하는 복구 작업에서는 `WARP_SHARDS_REMOVE_ORPHANS=0`을 쓰거나 전체 count로 렌더한다.

### 2026-04-26: 20k 실행의 shard 장애

`20260423_170321_250907` 20k 실행을 검토할 때 일부 shard가 `Exited (1/137)` 상태로 남아 있었고, 브라우저에서 SearchXNG UI가 `ERR_EMPTY_RESPONSE`를 보였다. 대표 증상은 `19013`이었지만 실제 감사에서는 `1,10,13,15,26,27,29,33,34` shard가 문제였다. 해당 shard 번들만 recreate한 뒤 재감사에서는 `36/36`이 정상으로 돌아왔다.

컨테이너 로그에서는 `can't start new thread`, `Resource temporarily unavailable`, `pthread_create failed`, Docker DNAT/iptables fork 실패가 확인됐다. 그래서 대량 병렬 처리에서는 WARP on 여부만 보지 말고 `mcp-bridge /readyz`와 SearchXNG UI 응답까지 준비 상태로 확인해야 한다.

당시 정한 대응 순서는 다음과 같다.

1. `python tools/audit_search_shards.py --count N`으로 문제 shard를 확인한다.
2. `python tools/warp_shards.py recreate --shards <문제 shard 목록>`으로 해당 번들만 재생성한다.
3. 재감사에서 `ok=N/N`이 될 때까지 반복한다.
4. 같은 현상이 반복되면 shard 수나 배치 기동 크기를 줄인다.
