from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _compose_path() -> Path:
    return _repo_root() / "docker-compose.warp-shards.generated.yml"


def _render_service_block(index: int, mcp_port: int) -> str:
    warp_name = f"warp-{index}"
    search_name = f"searchxng-{index}"
    crawl_name = f"crawl4ai-{index}"
    mcp_name = f"mcp-bridge-{index}"

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
      - ./docker/searchxng/startpage_patched.py:/usr/local/searxng/searx/engines/startpage.py:ro
    environment:
      - SEARXNG_BASE_URL=http://{warp_name}:8080/
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
    environment:
      - SEARCHXNG_URL=http://{warp_name}:8080
      - SEARCHXNG_URLS=http://{warp_name}:8080
      - CRAWL4AI_URL=http://{warp_name}:11235
      - MCP_DISCOVER_PUBLIC_INSTANCES=0
      - MCP_DISCOVERY_SOURCE_URL=https://searx.space/data/instances.json
      - MCP_DISCOVERY_MAX_URLS=5
      - MCP_DISCOVERY_MIN_SEARCH_SUCCESS=80
      - MCP_DISCOVERY_CACHE_SEC=1800
      - MCP_PORT=3333
      - LLM_ENDPOINT=${{LLM_ENDPOINT:-http://host.docker.internal:11434}}
      - MCP_SEARCH_ENGINES=google,bing,presearch,webcrawler,naver
      - MCP_SEARCH_FALLBACK_ENGINES=webcrawler,google,bing,presearch,naver
      - MCP_SEARCH_LANGUAGE=${{MCP_SEARCH_LANGUAGE:-ko-KR}}
      - MCP_SEARCH_MAX_RETRIES=${{MCP_SEARCH_MAX_RETRIES:-4}}
      - MCP_SEARCH_MAX_PAGES=${{MCP_SEARCH_MAX_PAGES:-3}}
      - MCP_SEARCH_RETRY_BACKOFF_MS=${{MCP_SEARCH_RETRY_BACKOFF_MS:-400}}
      - MCP_SEARCH_RETRY_ON_EMPTY=${{MCP_SEARCH_RETRY_ON_EMPTY:-1}}
      - MCP_SEARCH_SOFT_FAIL=${{MCP_SEARCH_SOFT_FAIL:-1}}
"""


def render_compose(count: int, mcp_base_port: int) -> str:
    services = ["services:"]
    for idx in range(1, count + 1):
        services.append(_render_service_block(idx, mcp_base_port + idx - 1).rstrip())
    return "\n".join(services) + "\n"


def write_compose(count: int, mcp_base_port: int) -> Path:
    repo_root = _repo_root()
    for idx in range(1, count + 1):
        (repo_root / "docker" / "warp" / "state" / f"warp-{idx}" / "var-lib").mkdir(parents=True, exist_ok=True)
        (repo_root / "docker" / "warp" / "state" / f"warp-{idx}" / "etc").mkdir(parents=True, exist_ok=True)

    compose_path = _compose_path()
    compose_path.write_text(render_compose(count, mcp_base_port), encoding="utf-8")
    return compose_path


def run_compose(args: list[str]) -> None:
    subprocess.run(args, cwd=_repo_root(), check=True)


def run_compose_capture(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=_repo_root(),
        check=True,
        text=True,
        capture_output=True,
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


def _compose_exec(project_name: str, service: str, shell_cmd: str) -> str:
    proc = run_compose_capture(
        [
            "docker",
            "compose",
            "-p",
            project_name,
            "-f",
            str(_compose_path()),
            "exec",
            "-T",
            service,
            "bash",
            "-lc",
            shell_cmd,
        ]
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
        [
            "docker",
            "compose",
            "-p",
            project_name,
            "-f",
            str(compose_path),
            "ps",
            "--status",
            "running",
            "--services",
        ]
    )
    running = {line.strip() for line in ps_proc.stdout.splitlines() if line.strip()}

    items: list[dict[str, object]] = []
    for service in services:
        item: dict[str, object] = {
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
            warp_status = _compose_exec(project_name, service, "warp-cli --accept-tos status || true")
            item["warp_status_raw"] = warp_status
        except subprocess.CalledProcessError as exc:
            item["error"] = exc.stderr.strip() or exc.stdout.strip() or str(exc)
            items.append(item)
            continue

        try:
            trace = _compose_exec(
                project_name,
                service,
                "curl -fsS --max-time 10 https://www.cloudflare.com/cdn-cgi/trace || true",
            )
            item["trace_raw"] = trace
            item["trace"] = _parse_trace(trace)
        except subprocess.CalledProcessError as exc:
            item["trace_error"] = exc.stderr.strip() or exc.stdout.strip() or str(exc)

        items.append(item)

    return items


def cmd_render(count: int, mcp_base_port: int) -> int:
    compose_path = write_compose(count, mcp_base_port)
    print(compose_path)
    return 0


def cmd_up(count: int, mcp_base_port: int, project_name: str) -> int:
    compose_path = write_compose(count, mcp_base_port)
    run_compose(
        [
            "docker",
            "compose",
            "-p",
            project_name,
            "-f",
            str(compose_path),
            "up",
            "-d",
            "--build",
            "--remove-orphans",
        ]
    )
    for idx in range(count):
        print(f"http://localhost:{mcp_base_port + idx}")
    return 0


def cmd_down(project_name: str) -> int:
    compose_path = _compose_path()
    if not compose_path.exists():
        return 0
    run_compose(
        [
            "docker",
            "compose",
            "-p",
            project_name,
            "-f",
            str(compose_path),
            "down",
            "--remove-orphans",
        ]
    )
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

    p_up = sub.add_parser("up")
    p_up.add_argument("--count", type=int, required=True)
    p_up.add_argument("--mcp-base-port", type=int, default=3333)
    p_up.add_argument("--project-name", default="warp-shards")

    p_down = sub.add_parser("down")
    p_down.add_argument("--project-name", default="warp-shards")

    p_status = sub.add_parser("status")
    p_status.add_argument("--project-name", default="warp-shards")
    p_status.add_argument("--json", action="store_true")

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "render":
        return cmd_render(args.count, args.mcp_base_port)
    if args.command == "up":
        return cmd_up(args.count, args.mcp_base_port, args.project_name)
    if args.command == "down":
        return cmd_down(args.project_name)
    if args.command == "status":
        return cmd_status_format(args.project_name, as_json=bool(args.json))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
