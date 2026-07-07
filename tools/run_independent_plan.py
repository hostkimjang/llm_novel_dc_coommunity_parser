from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import urlopen

from tools.test_run_dashboard_policy import DEFAULT_DASHBOARD_URL, strip_no_dashboard


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"plan must be a JSON object: {path}")
    return payload


def _env_overrides(values: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in values:
        if "=" not in raw:
            raise ValueError(f"--set-env expects KEY=VALUE, got: {raw}")
        key, value = raw.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"empty environment key in: {raw}")
        out[key] = value
    return out


def _safe_stem(path: str, fallback: str) -> str:
    stem = Path(path).stem
    if stem:
        return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in stem)
    return fallback


def _write_line(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(text + "\n")


def _dashboard_health(dashboard_url: str, *, timeout: float = 2.0) -> dict[str, Any]:
    health_url = f"{dashboard_url.rstrip('/')}/api/health"
    try:
        with urlopen(health_url, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="replace") or "{}")
        if not isinstance(payload, dict):
            payload = {}
        return {
            "ok": bool(payload.get("ok")),
            "standalone": bool(payload.get("standalone")),
            "service": payload.get("service") or "",
            "url": dashboard_url.rstrip("/"),
        }
    except (OSError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {
            "ok": False,
            "standalone": False,
            "service": "",
            "url": dashboard_url.rstrip("/"),
            "error": repr(exc),
        }


def _dashboard_host_port(dashboard_url: str) -> tuple[str, int]:
    parsed = urlparse(dashboard_url)
    host = parsed.hostname or "127.0.0.1"
    port = int(parsed.port or (443 if parsed.scheme == "https" else 80))
    return host, port


def _ensure_dashboard(
    *,
    dashboard_url: str,
    log_dir: Path,
    python_executable: str,
    wait_sec: float = 5.0,
) -> dict[str, Any]:
    dashboard_url = dashboard_url.rstrip("/") or DEFAULT_DASHBOARD_URL
    before = _dashboard_health(dashboard_url)
    if before.get("ok") and before.get("standalone"):
        return {"status": "already_running", **before}

    host, port = _dashboard_host_port(dashboard_url)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "dashboard_server.log"
    argv = [
        python_executable,
        "tools/dashboard_server.py",
        "--host",
        host,
        "--port",
        str(port),
    ]
    with log_path.open("a", encoding="utf-8", errors="replace", newline="\n") as log_file:
        log_file.write(f"START_DASHBOARD {datetime.now().isoformat()} COMMAND {subprocess.list2cmdline(argv)}\n")
        log_file.flush()
        proc = subprocess.Popen(
            argv,
            cwd=Path.cwd(),
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

    deadline = time.time() + max(0.5, wait_sec)
    last = before
    while time.time() < deadline:
        time.sleep(0.25)
        last = _dashboard_health(dashboard_url)
        if last.get("ok") and last.get("standalone"):
            return {"status": "started", "pid": proc.pid, "log": str(log_path), **last}
        if proc.poll() is not None:
            break
    return {
        "status": "unavailable",
        "pid": proc.pid,
        "exit_code": proc.poll(),
        "log": str(log_path),
        **last,
    }


def run_plan(
    *,
    plan_path: Path,
    log_dir: Path,
    env_updates: dict[str, str],
    skip_existing: bool,
    limit: int | None,
    dashboard: bool = True,
    dashboard_url: str = DEFAULT_DASHBOARD_URL,
    dashboard_python: str | None = None,
) -> int:
    plan = _load_json(plan_path)
    runs = plan.get("planned_runs")
    if not isinstance(runs, list):
        raise ValueError(f"plan has no planned_runs list: {plan_path}")

    selected = runs[: max(0, limit)] if limit is not None else runs
    log_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(env_updates)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("LLM_SUSPEND_ON_SERVER_ANOMALY", "0")
    env.setdefault("LLM_SUSPEND_FAILURE_THRESHOLD", "0")
    env.setdefault("LLM_STREAM_FIRST_TOKEN_TIMEOUT_SECONDS", "45")
    env.setdefault("LLM_STREAM_IDLE_TIMEOUT_SECONDS", "45")
    dashboard_state: dict[str, Any] = {"status": "disabled"}
    if dashboard:
        dashboard_url = dashboard_url.rstrip("/") or DEFAULT_DASHBOARD_URL
        host, port = _dashboard_host_port(dashboard_url)
        env.setdefault("DASHBOARD_URL", dashboard_url)
        env.setdefault("DASHBOARD_PORT", str(port))
        env.setdefault("EXPERT_DASHBOARD_FORWARD", "1")
        dashboard_state = _ensure_dashboard(
            dashboard_url=dashboard_url,
            log_dir=log_dir,
            python_executable=dashboard_python or sys.executable,
        )
        print(
            json.dumps(
                {
                    "event": "dashboard_ready",
                    "dashboard_url": dashboard_url,
                    "dashboard_status": dashboard_state.get("status"),
                    "dashboard_ok": dashboard_state.get("ok"),
                    "dashboard_standalone": dashboard_state.get("standalone"),
                    "dashboard_log": dashboard_state.get("log", ""),
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
        _write_line(
            log_dir / "dashboard.marker.log",
            (
                f"DASHBOARD {datetime.now().isoformat()} status={dashboard_state.get('status')} "
                f"url={dashboard_url} host={host} port={port} log={dashboard_state.get('log', '')}"
            ),
        )

    completed = 0
    skipped = 0
    stripped_no_dashboard = 0
    for index, run in enumerate(selected, start=1):
        if not isinstance(run, dict):
            raise ValueError(f"planned_runs[{index}] is not an object")
        argv = run.get("command_argv")
        if not isinstance(argv, list) or not all(isinstance(item, str) for item in argv):
            raise ValueError(f"planned_runs[{index}] has invalid command_argv")
        if dashboard:
            before_len = len(argv)
            argv = strip_no_dashboard(argv)
            stripped_no_dashboard += before_len - len(argv)
        output_json = str(run.get("output_json") or "")
        output_path = Path(output_json) if output_json else None
        stem = _safe_stem(output_json, f"run_{index:03d}")
        marker = log_dir / f"{stem}.marker.log"
        combined = log_dir / f"{stem}.combined.log"

        if skip_existing and output_path is not None and output_path.exists():
            skipped += 1
            _write_line(marker, f"SKIP {datetime.now().isoformat()} index={index} output={output_path}")
            continue

        _write_line(
            marker,
            (
                f"START {datetime.now().isoformat()} index={index} "
                f"post_id={run.get('post_id')} repeat={run.get('repeat_index')} output={output_json} "
                f"dashboard={dashboard_state.get('status')}"
            ),
        )
        with combined.open("a", encoding="utf-8", errors="replace", newline="\n") as log_file:
            log_file.write(f"COMMAND {subprocess.list2cmdline(argv)}\n")
            log_file.flush()
            proc = subprocess.Popen(
                argv,
                cwd=Path.cwd(),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            assert proc.stdout is not None
            try:
                for line in proc.stdout:
                    log_file.write(line)
                    log_file.flush()
                rc = proc.wait()
            finally:
                proc.stdout.close()
        exists = bool(output_path and output_path.exists())
        _write_line(marker, f"END {datetime.now().isoformat()} exit={rc} exists={exists}")
        if rc != 0:
            return rc
        completed += 1

    print(
        json.dumps(
            {
                "plan": str(plan_path),
                "log_dir": str(log_dir),
                "selected_runs": len(selected),
                "completed_runs": completed,
                "skipped_runs": skipped,
                "env_overrides": sorted(env_updates),
                "dashboard": dashboard_state,
                "stripped_no_dashboard_flags": stripped_no_dashboard,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run an independent JSON run-plan sequentially with logs.")
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--log-dir", required=True, type=Path)
    parser.add_argument("--set-env", action="append", default=[], help="Environment override as KEY=VALUE.")
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--dashboard-url",
        default=DEFAULT_DASHBOARD_URL,
        help="Standalone dashboard URL to start/use for test-run progress.",
    )
    parser.add_argument(
        "--dashboard-python",
        default=sys.executable,
        help="Python executable used to start tools/dashboard_server.py.",
    )
    parser.add_argument(
        "--no-dashboard",
        action="store_true",
        help="Disable default standalone dashboard startup/forwarding for this plan.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return run_plan(
        plan_path=args.plan,
        log_dir=args.log_dir,
        env_updates=_env_overrides(list(args.set_env or [])),
        skip_existing=bool(args.skip_existing),
        limit=args.limit,
        dashboard=not bool(args.no_dashboard),
        dashboard_url=str(args.dashboard_url),
        dashboard_python=str(args.dashboard_python),
    )


if __name__ == "__main__":
    raise SystemExit(main())
