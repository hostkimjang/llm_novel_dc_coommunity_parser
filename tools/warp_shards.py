from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _compose_path() -> Path:
    return _repo_root() / "docker-compose.warp-shards.generated.yml"


def _compose_env() -> dict[str, str]:
    env = os.environ.copy()
    raw_parallel = env.get("COMPOSE_PARALLEL_LIMIT", "").strip() or env.get("WARP_SHARDS_COMPOSE_PARALLEL", "").strip()
    try:
        parallel = max(1, int(raw_parallel)) if raw_parallel else 8
    except Exception:
        parallel = 8
    env["COMPOSE_PARALLEL_LIMIT"] = str(parallel)
    return env


def _compose_progress_mode() -> str:
    mode = os.getenv("WARP_SHARDS_COMPOSE_PROGRESS", "plain").strip().lower()
    if mode in {"auto", "tty", "plain", "json", "quiet"}:
        return mode
    return "plain"


def _compose_cmd(project_name: str, compose_path: Path, *args: str) -> list[str]:
    return [
        "docker",
        "compose",
        "--ansi",
        "never",
        "--progress",
        _compose_progress_mode(),
        "-p",
        project_name,
        "-f",
        str(compose_path),
        *args,
    ]


def _get_batch_size(total_count: int) -> int:
    raw = os.getenv("WARP_SHARDS_BATCH_SIZE", "").strip()
    if raw:
        try:
            return max(1, min(total_count, int(raw)))
        except Exception:
            pass
    try:
        compose_parallel = int(_compose_env().get("COMPOSE_PARALLEL_LIMIT", "8"))
    except Exception:
        compose_parallel = 8
    return max(1, min(total_count, compose_parallel))


def _get_wait_timeout() -> int:
    raw = os.getenv("WARP_SHARDS_WAIT_TIMEOUT", "").strip()
    if raw:
        try:
            return max(0, int(raw))
        except Exception:
            pass
    return 180


def _get_search_ui_base_port() -> int:
    raw = os.getenv("WARP_SHARDS_SEARCH_UI_BASE_PORT", "19001").strip()
    try:
        return max(0, int(raw))
    except Exception:
        return 19001


def _get_batch_pause_seconds() -> float:
    raw = os.getenv("WARP_SHARDS_BATCH_PAUSE_SEC", "").strip()
    if raw:
        try:
            return max(0.0, float(raw))
        except Exception:
            pass
    return 1.0


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name, "1" if default else "0").strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    return default


def _mcp_bridge_services(indices: list[int]) -> list[str]:
    return [f"mcp-bridge-{idx}" for idx in indices]


def _bundle_services(indices: list[int]) -> list[str]:
    services: list[str] = []
    for idx in indices:
        services.extend(
            [
                f"warp-{idx}",
                f"searchxng-{idx}",
                f"crawl4ai-{idx}",
                f"browser-search-{idx}",
                f"mcp-bridge-{idx}",
            ]
        )
    return services


def _format_shard_span(indices: list[int]) -> str:
    if not indices:
        return "-"
    if len(indices) == 1:
        return str(indices[0])
    return f"{indices[0]}-{indices[-1]}"


def _extract_shard_index(service_name: str) -> int | None:
    match = re.fullmatch(r"warp-(\d+)", service_name.strip())
    if not match:
        return None
    try:
        return int(match.group(1))
    except Exception:
        return None


def _parse_shard_spec(raw: str) -> list[int]:
    seen: list[int] = []
    for chunk in (raw or "").split(","):
        token = chunk.strip()
        if not token:
            continue
        if "-" in token:
            left, right = token.split("-", 1)
            start = int(left.strip())
            end = int(right.strip())
            if end < start:
                start, end = end, start
            for idx in range(start, end + 1):
                if idx not in seen:
                    seen.append(idx)
            continue
        idx = int(token)
        if idx not in seen:
            seen.append(idx)
    return seen


def _validate_port_ranges(count: int, mcp_base_port: int, search_ui_base_port: int) -> None:
    if count < 1:
        raise ValueError("count must be >= 1")

    ranges: list[tuple[str, int, int]] = [("mcp", mcp_base_port, mcp_base_port + count - 1)]
    if search_ui_base_port > 0:
        ranges.append(("search-ui", search_ui_base_port, search_ui_base_port + count - 1))

    for name, start, end in ranges:
        if start < 1 or end > 65535:
            raise ValueError(f"{name} port range out of bounds: {start}-{end}")

    if search_ui_base_port <= 0:
        return

    mcp_start, mcp_end = mcp_base_port, mcp_base_port + count - 1
    ui_start, ui_end = search_ui_base_port, search_ui_base_port + count - 1
    if max(mcp_start, ui_start) <= min(mcp_end, ui_end):
        raise ValueError(f"mcp/search-ui port ranges overlap: {mcp_start}-{mcp_end} vs {ui_start}-{ui_end}")


def _render_service_block(index: int, mcp_port: int, search_ui_port: int) -> str:
    warp_name = f"warp-{index}"
    search_name = f"searchxng-{index}"
    crawl_name = f"crawl4ai-{index}"
    browser_name = f"browser-search-{index}"
    mcp_name = f"mcp-bridge-{index}"
    search_ui_ports = ""
    searchxng_base_url = f"http://{warp_name}:8080/"
    if search_ui_port > 0:
        search_ui_ports = f"""    ports:
      - "{search_ui_port}:8080"
"""
        searchxng_base_url = f"http://localhost:{search_ui_port}/"

    return f"""
  {warp_name}:
    build:
      context: .
      dockerfile: docker/warp/Dockerfile
    privileged: true
    restart: unless-stopped
    environment:
      - WARP_LICENSE_KEY=${{WARP_LICENSE_KEY:-}}
      - WARP_MODE=${{WARP_MODE:-warp+doh}}
      - WARP_TUNNEL_PROTOCOL=${{WARP_TUNNEL_PROTOCOL:-}}
{search_ui_ports.rstrip()}
    volumes:
      - ./docker/warp/state/{warp_name}/var-lib:/var/lib/cloudflare-warp
      - ./docker/warp/state/{warp_name}/etc:/etc/warp

  {search_name}:
    image: searxng/searxng:latest
    restart: unless-stopped
    network_mode: "service:{warp_name}"
    depends_on:
      - {warp_name}
    volumes:
      - ./docker/searchxng/settings.yml:/etc/searxng/settings.yml:ro
    environment:
      - SEARXNG_BASE_URL={searchxng_base_url}
      - SEARXNG_SECRET=${{SEARXNG_SECRET:-change-me-please-change}}

  {crawl_name}:
    image: unclecode/crawl4ai:latest
    restart: unless-stopped
    network_mode: "service:{warp_name}"
    shm_size: "2g"
    depends_on:
      - {warp_name}
    environment:
      - CRAWL4AI_API_TOKEN=${{CRAWL4AI_API_TOKEN:-}}

  {browser_name}:
    image: llm-batch-browser-search:latest
    build:
      context: .
      dockerfile: docker/browser-search/Dockerfile
    restart: unless-stopped
    network_mode: "service:{warp_name}"
    shm_size: "2g"
    depends_on:
      - {warp_name}
    environment:
      - BROWSER_SEARCH_PROVIDER_ORDER=${{BROWSER_SEARCH_PROVIDER_ORDER:-cloak,naver}}
      - BROWSER_SEARCH_HEADLESS=${{BROWSER_SEARCH_HEADLESS:-1}}
      - BROWSER_SEARCH_HUMANIZE=${{BROWSER_SEARCH_HUMANIZE:-1}}
      - BROWSER_SEARCH_HUMAN_PRESET=${{BROWSER_SEARCH_HUMAN_PRESET:-default}}
      - BROWSER_SEARCH_WAIT_MS=${{BROWSER_SEARCH_WAIT_MS:-3000}}
      - BROWSER_SEARCH_GOOGLE_MIN_INTERVAL_SEC=${{BROWSER_SEARCH_GOOGLE_MIN_INTERVAL_SEC:-45}}
      - BROWSER_SEARCH_GOOGLE_JITTER_SEC=${{BROWSER_SEARCH_GOOGLE_JITTER_SEC:-15}}
      - BROWSER_SEARCH_BLOCK_COOLDOWN_SEC=${{BROWSER_SEARCH_BLOCK_COOLDOWN_SEC:-7200}}
      - CLOAKBROWSER_AUTO_UPDATE=${{CLOAKBROWSER_AUTO_UPDATE:-false}}

  {mcp_name}:
    build:
      context: .
      dockerfile: docker/mcp-bridge/Dockerfile
    restart: unless-stopped
    ports:
      - "{mcp_port}:3333"
    depends_on:
      - {warp_name}
      - {search_name}
      - {crawl_name}
      - {browser_name}
    environment:
      - SEARCHXNG_URL=http://{warp_name}:8080
      - SEARCHXNG_URLS=http://{warp_name}:8080
      - CRAWL4AI_URL=http://{warp_name}:11235
      - HEADLESS_SEARCH_URL=http://{warp_name}:8765/search
      - HEADLESS_SEARCH_ENABLED=${{HEADLESS_SEARCH_ENABLED:-1}}
      - MCP_DISCOVER_PUBLIC_INSTANCES=0
      - MCP_DISCOVERY_SOURCE_URL=https://searx.space/data/instances.json
      - MCP_DISCOVERY_MAX_URLS=5
      - MCP_DISCOVERY_MIN_SEARCH_SUCCESS=80
      - MCP_DISCOVERY_CACHE_SEC=1800
      - MCP_PORT=3333
      - LLM_ENDPOINT=${{LLM_ENDPOINT:-http://host.docker.internal:11434}}
      - MCP_SEARCH_ENGINES=${{MCP_SEARCH_ENGINES:-google,bing,webcrawler,naver}}
      - MCP_SEARCH_FALLBACK_ENGINES=${{MCP_SEARCH_FALLBACK_ENGINES:-webcrawler,google,bing,naver}}
      - MCP_SEARCH_LANGUAGE=${{MCP_SEARCH_LANGUAGE:-ko-KR}}
      - MCP_SEARCH_MAX_RETRIES=${{MCP_SEARCH_MAX_RETRIES:-1}}
      - MCP_SEARCH_MAX_PAGES=${{MCP_SEARCH_MAX_PAGES:-2}}
      - MCP_SEARCH_RETRY_BACKOFF_MS=${{MCP_SEARCH_RETRY_BACKOFF_MS:-400}}
      - MCP_SEARCH_RETRY_ON_EMPTY=${{MCP_SEARCH_RETRY_ON_EMPTY:-1}}
      - MCP_SEARCH_SOFT_FAIL=${{MCP_SEARCH_SOFT_FAIL:-1}}
"""


def render_compose(count: int, mcp_base_port: int, search_ui_base_port: int) -> str:
    _validate_port_ranges(count, mcp_base_port, search_ui_base_port)
    services = ["services:"]
    for idx in range(1, count + 1):
        search_ui_port = search_ui_base_port + idx - 1 if search_ui_base_port > 0 else 0
        services.append(_render_service_block(idx, mcp_base_port + idx - 1, search_ui_port).rstrip())
    return "\n".join(services) + "\n"


def write_compose(count: int, mcp_base_port: int, search_ui_base_port: int) -> Path:
    repo_root = _repo_root()
    for idx in range(1, count + 1):
        (repo_root / "docker" / "warp" / "state" / f"warp-{idx}" / "var-lib").mkdir(parents=True, exist_ok=True)
        (repo_root / "docker" / "warp" / "state" / f"warp-{idx}" / "etc").mkdir(parents=True, exist_ok=True)

    compose_path = _compose_path()
    compose_path.write_text(render_compose(count, mcp_base_port, search_ui_base_port), encoding="utf-8")
    return compose_path


def run_compose(args: list[str]) -> None:
    subprocess.run(args, cwd=_repo_root(), check=True, env=_compose_env())


def run_compose_capture(args: list[str], *, timeout: float | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=_repo_root(),
        check=True,
        text=True,
        capture_output=True,
        env=_compose_env(),
        timeout=timeout,
    )


def _discover_warp_services() -> list[str]:
    compose_path = _compose_path()
    if not compose_path.exists():
        return []
    text = compose_path.read_text(encoding="utf-8")
    seen: list[str] = []
    for match in re.finditer(r"^\s{2}(warp-\d+):\s*$", text, flags=re.MULTILINE):
        name = match.group(1)
        if name not in seen:
            seen.append(name)
    return seen


def _status_exec_timeout() -> float:
    raw = os.getenv("WARP_SHARDS_STATUS_EXEC_TIMEOUT_SEC", "20").strip()
    try:
        return max(1.0, float(raw))
    except Exception:
        return 20.0


def _compose_exec(project_name: str, service: str, shell_cmd: str, *, timeout: float | None = None) -> str:
    proc = run_compose_capture(
        _compose_cmd(
            project_name,
            _compose_path(),
            "exec",
            "-T",
            service,
            "bash",
            "-lc",
            shell_cmd,
        ),
        timeout=timeout,
    )
    return proc.stdout.strip()


def _parse_trace(trace: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for line in (trace or "").splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        parsed[key.strip()] = value.strip()
    return parsed


def collect_status(project_name: str) -> list[dict[str, object]]:
    compose_path = _compose_path()
    if not compose_path.exists():
        raise FileNotFoundError("generated compose file not found")

    services = _discover_warp_services()
    if not services:
        raise RuntimeError("no warp services found")

    ps_proc = run_compose_capture(
        _compose_cmd(
            project_name,
            compose_path,
            "ps",
            "--status",
            "running",
            "--services",
        ),
        timeout=_status_exec_timeout(),
    )
    running = {line.strip() for line in ps_proc.stdout.splitlines() if line.strip()}

    items: list[dict[str, object]] = []
    for service in services:
        shard_index = _extract_shard_index(service)
        item: dict[str, object] = {
            "shard_index": shard_index,
            "service": service,
            "running": service in running,
            "warp_status_raw": "",
            "trace_raw": "",
            "trace": {},
        }
        if service not in running:
            items.append(item)
            continue

        try:
            warp_status = _compose_exec(
                project_name,
                service,
                "warp-cli --accept-tos status || true",
                timeout=_status_exec_timeout(),
            )
            item["warp_status_raw"] = warp_status
        except subprocess.TimeoutExpired as exc:
            item["error"] = f"warp_status_timeout:{_status_exec_timeout():.1f}s"
            item["timeout_cmd"] = str(exc.cmd)
            items.append(item)
            continue
        except subprocess.CalledProcessError as exc:
            item["error"] = exc.stderr.strip() or exc.stdout.strip() or str(exc)
            items.append(item)
            continue

        try:
            trace = _compose_exec(
                project_name,
                service,
                "curl -fsS --max-time 10 https://www.cloudflare.com/cdn-cgi/trace || true",
                timeout=_status_exec_timeout(),
            )
            item["trace_raw"] = trace
            item["trace"] = _parse_trace(trace)
        except subprocess.TimeoutExpired as exc:
            item["trace_error"] = f"trace_timeout:{_status_exec_timeout():.1f}s"
            item["timeout_cmd"] = str(exc.cmd)
            if "connected" in str(item.get("warp_status_raw") or "").lower():
                item["trace"] = {
                    "warp": "on",
                    "trace_fallback": "warp_cli_connected_after_trace_timeout",
                }
        except subprocess.CalledProcessError as exc:
            item["trace_error"] = exc.stderr.strip() or exc.stdout.strip() or str(exc)

        items.append(item)

    return items


def cmd_render(count: int, mcp_base_port: int, search_ui_base_port: int) -> int:
    compose_path = write_compose(count, mcp_base_port, search_ui_base_port)
    print(compose_path)
    return 0


def _run_up_batch(project_name: str, compose_path: Path, shard_indices: list[int], wait_timeout: int) -> None:
    services = _mcp_bridge_services(shard_indices)
    cmd = _compose_cmd(
        project_name,
        compose_path,
        "up",
        "-d",
        "--build",
    )
    # 증분 scale-up 경로에서는 현재 compose count보다 큰 index의 기존 컨테이너를
    # orphan으로 제거하면 안 되므로 env로 끌 수 있게 한다.
    if _env_bool("WARP_SHARDS_REMOVE_ORPHANS", True):
        cmd.append("--remove-orphans")
    # --no-recreate: 정의/이미지 drift가 있어도 기존 컨테이너를 절대 재생성하지
    # 않고 없는 컨테이너만 생성한다. 증분 scale-up 경로에서 healthy 컨테이너
    # 보호용 (기본 off — 기존 up 경로 동작 불변).
    if _env_bool("WARP_SHARDS_NO_RECREATE", False):
        cmd.append("--no-recreate")
    if wait_timeout > 0:
        cmd.extend(["--wait", "--wait-timeout", str(wait_timeout)])
    cmd.extend(services)
    run_compose(cmd)


def _run_recreate_batch(project_name: str, compose_path: Path, shard_indices: list[int], wait_timeout: int) -> None:
    services = _bundle_services(shard_indices)
    cmd = _compose_cmd(
        project_name,
        compose_path,
        "up",
        "-d",
        "--force-recreate",
        "--no-build",
        "--remove-orphans",
    )
    if wait_timeout > 0:
        cmd.extend(["--wait", "--wait-timeout", str(wait_timeout)])
    cmd.extend(services)
    run_compose(cmd)


def _run_up_batch_recursive(project_name: str, compose_path: Path, shard_indices: list[int], wait_timeout: int) -> list[int]:
    """배치 up을 시도하고 끝내 기동 실패한 shard index 목록을 반환한다.

    단일 shard가 영구 실패해도 raise하지 않고 수집-계속(collect-and-continue)
    하므로, 한 shard의 포트 충돌 등이 나머지 shard 기동을 막지 않는다.
    """
    if not shard_indices:
        return []
    try:
        _run_up_batch(project_name, compose_path, shard_indices, wait_timeout)
        print(
            f"[warp_shards] batch ready: shards={_format_shard_span(shard_indices)} count={len(shard_indices)}",
            file=sys.stderr,
            flush=True,
        )
        return []
    except subprocess.CalledProcessError as exc:
        if len(shard_indices) == 1:
            print(
                f"[warp_shards] shard {shard_indices[0]} 기동 실패 (returncode={exc.returncode})",
                file=sys.stderr,
                flush=True,
            )
            return list(shard_indices)
        mid = len(shard_indices) // 2
        left = shard_indices[:mid]
        right = shard_indices[mid:]
        print(
            "[warp_shards] batch 실패: shards={span} count={count} returncode={code}; "
            "더 작은 배치로 재시도합니다 ({left_span}, {right_span})".format(
                span=_format_shard_span(shard_indices),
                count=len(shard_indices),
                code=exc.returncode,
                left_span=_format_shard_span(left),
                right_span=_format_shard_span(right),
            ),
            file=sys.stderr,
            flush=True,
        )
        failed: list[int] = []
        failed.extend(_run_up_batch_recursive(project_name, compose_path, left, wait_timeout))
        failed.extend(_run_up_batch_recursive(project_name, compose_path, right, wait_timeout))
        return failed


def _run_recreate_batch_recursive(project_name: str, compose_path: Path, shard_indices: list[int], wait_timeout: int) -> None:
    if not shard_indices:
        return
    try:
        _run_recreate_batch(project_name, compose_path, shard_indices, wait_timeout)
        print(
            f"[warp_shards] batch recreated: shards={_format_shard_span(shard_indices)} count={len(shard_indices)}",
            file=sys.stderr,
            flush=True,
        )
        return
    except subprocess.CalledProcessError as exc:
        if len(shard_indices) == 1:
            print(
                f"[warp_shards] shard {shard_indices[0]} 재기동 실패 (returncode={exc.returncode})",
                file=sys.stderr,
                flush=True,
            )
            raise
        mid = len(shard_indices) // 2
        left = shard_indices[:mid]
        right = shard_indices[mid:]
        print(
            "[warp_shards] recreate batch 실패: shards={span} count={count} returncode={code}; "
            "더 작은 배치로 재시도합니다 ({left_span}, {right_span})".format(
                span=_format_shard_span(shard_indices),
                count=len(shard_indices),
                code=exc.returncode,
                left_span=_format_shard_span(left),
                right_span=_format_shard_span(right),
            ),
            file=sys.stderr,
            flush=True,
        )
        _run_recreate_batch_recursive(project_name, compose_path, left, wait_timeout)
        _run_recreate_batch_recursive(project_name, compose_path, right, wait_timeout)


def cmd_up(
    count: int,
    mcp_base_port: int,
    search_ui_base_port: int,
    project_name: str,
    shards: list[int] | None = None,
) -> int:
    compose_path = write_compose(count, mcp_base_port, search_ui_base_port)
    compose_parallel = _compose_env().get("COMPOSE_PARALLEL_LIMIT", "8")
    batch_size = _get_batch_size(count)
    wait_timeout = _get_wait_timeout()
    batch_pause_sec = _get_batch_pause_seconds()
    # --shards 지정 시 compose 렌더는 전체 count로 유지하되(포트 매핑/state 보존),
    # up 대상 서비스는 지정 shard로만 제한한다. 증분 scale-up에서 healthy shard를
    # compose 명령 대상 자체에서 제외해 재생성 가능성을 구조적으로 차단한다.
    if shards:
        shard_indices = sorted({idx for idx in shards if 1 <= idx <= count})
        if not shard_indices:
            print(
                f"[warp_shards] up --shards: 1..{count} 범위 내 유효 shard 없음",
                file=sys.stderr,
                flush=True,
            )
            return 1
    else:
        shard_indices = list(range(1, count + 1))
    print(
        "[warp_shards] compose up: project={project}, shards={span} (count={count}), compose_parallel={parallel}, "
        "batch_size={batch}, wait_timeout={wait}, progress={progress}, search_ui_base_port={ui_port}".format(
            project=project_name,
            span=_format_shard_span(shard_indices),
            count=len(shard_indices),
            parallel=compose_parallel,
            batch=batch_size,
            wait=wait_timeout,
            progress=_compose_progress_mode(),
            ui_port=search_ui_base_port or "disabled",
        ),
        file=sys.stderr,
        flush=True,
    )
    failed_shards: list[int] = []
    total_batches = (len(shard_indices) + batch_size - 1) // batch_size
    for batch_idx in range(total_batches):
        start = batch_idx * batch_size
        batch = shard_indices[start : start + batch_size]
        print(
            "[warp_shards] batch {current}/{total}: shards={span} count={count}".format(
                current=batch_idx + 1,
                total=total_batches,
                span=_format_shard_span(batch),
                count=len(batch),
            ),
            file=sys.stderr,
            flush=True,
        )
        failed_shards.extend(_run_up_batch_recursive(project_name, compose_path, batch, wait_timeout))
        if batch_pause_sec > 0 and batch_idx + 1 < total_batches:
            time.sleep(batch_pause_sec)
    if failed_shards:
        print(
            f"[warp_shards] failed shards: {_format_shard_span(sorted(failed_shards))} "
            f"(count={len(failed_shards)})",
            file=sys.stderr,
            flush=True,
        )
    if _env_bool("WARP_SHARDS_PRINT_ENDPOINTS", True):
        for idx in range(count):
            print(f"http://localhost:{mcp_base_port + idx}")
    else:
        print(
            "[warp_shards] endpoints ready: {first}..{last} (count={count})".format(
                first=f"http://localhost:{mcp_base_port}",
                last=f"http://localhost:{mcp_base_port + count - 1}",
                count=count,
            ),
            file=sys.stderr,
            flush=True,
        )
    if search_ui_base_port > 0:
        print(
            "[warp_shards] SearchXNG UI ports: {first}..{last} (count={count})".format(
                first=f"http://localhost:{search_ui_base_port}",
                last=f"http://localhost:{search_ui_base_port + count - 1}",
                count=count,
            ),
            file=sys.stderr,
            flush=True,
        )
    return 2 if failed_shards else 0


def cmd_recreate(shards: list[int], project_name: str) -> int:
    compose_path = _compose_path()
    if not compose_path.exists():
        raise FileNotFoundError("generated compose file not found")
    if not shards:
        return 0
    wait_timeout = _get_wait_timeout()
    print(
        "[warp_shards] recreate: project={project}, shards={span}, count={count}, wait_timeout={wait}".format(
            project=project_name,
            span=_format_shard_span(shards),
            count=len(shards),
            wait=wait_timeout,
        ),
        file=sys.stderr,
        flush=True,
    )
    _run_recreate_batch_recursive(project_name, compose_path, shards, wait_timeout)
    return 0


def cmd_down(project_name: str) -> int:
    compose_path = _compose_path()
    if not compose_path.exists():
        return 0
    run_compose(_compose_cmd(project_name, compose_path, "down", "--remove-orphans"))
    return 0


def cmd_status(project_name: str) -> int:
    return cmd_status_format(project_name, as_json=False)


def cmd_status_format(project_name: str, as_json: bool) -> int:
    try:
        items = collect_status(project_name)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if as_json:
        print(json.dumps(items, ensure_ascii=False, indent=2))
        return 0

    for item in items:
        service = str(item.get("service") or "?")
        print(f"[{service}]")
        if not bool(item.get("running")):
            print("running=no")
            print()
            continue
        if item.get("error"):
            print("running=yes")
            print(f"status_error={item['error']}")
            print()
            continue
        print("running=yes")
        print("-- warp-cli status --")
        print(str(item.get("warp_status_raw") or "(empty)"))
        print("-- cloudflare trace --")
        print(str(item.get("trace_raw") or item.get("trace_error") or "(empty)"))
        print()
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manage local WARP shard stack")
    sub = parser.add_subparsers(dest="command", required=True)

    p_render = sub.add_parser("render")
    p_render.add_argument("--count", type=int, required=True)
    p_render.add_argument("--mcp-base-port", type=int, default=3333)
    p_render.add_argument(
        "--search-ui-base-port",
        type=int,
        default=_get_search_ui_base_port(),
        help="SearchXNG UI host port base. 0 disables UI port publishing.",
    )

    p_up = sub.add_parser("up")
    p_up.add_argument("--count", type=int, required=True)
    p_up.add_argument("--mcp-base-port", type=int, default=3333)
    p_up.add_argument(
        "--search-ui-base-port",
        type=int,
        default=_get_search_ui_base_port(),
        help="SearchXNG UI host port base. 0 disables UI port publishing.",
    )
    p_up.add_argument("--project-name", default="warp-shards")
    p_up.add_argument(
        "--shards",
        default="",
        help="지정 시 해당 shard 서비스만 up (쉼표/범위 형식, 예: 17,19,20-32). compose 렌더는 --count 전체로 유지",
    )

    p_recreate = sub.add_parser("recreate")
    p_recreate.add_argument("--shards", required=True, help="쉼표/범위 형식 shard 목록 (예: 1,3,5-8)")
    p_recreate.add_argument("--project-name", default="warp-shards")

    p_down = sub.add_parser("down")
    p_down.add_argument("--project-name", default="warp-shards")

    p_status = sub.add_parser("status")
    p_status.add_argument("--project-name", default="warp-shards")
    p_status.add_argument("--json", action="store_true")

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "render":
        return cmd_render(args.count, args.mcp_base_port, args.search_ui_base_port)
    if args.command == "up":
        up_shards = _parse_shard_spec(args.shards) if str(args.shards or "").strip() else None
        return cmd_up(
            args.count,
            args.mcp_base_port,
            args.search_ui_base_port,
            args.project_name,
            shards=up_shards,
        )
    if args.command == "recreate":
        return cmd_recreate(_parse_shard_spec(args.shards), args.project_name)
    if args.command == "down":
        return cmd_down(args.project_name)
    if args.command == "status":
        return cmd_status_format(args.project_name, as_json=bool(args.json))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
