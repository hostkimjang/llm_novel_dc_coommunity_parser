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

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tools.test_run_dashboard_policy import DEFAULT_DASHBOARD_URL, strip_no_dashboard


MANIFEST_ATTACH_WAIT_SECONDS = 120.0


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


def _env_mapping(raw: Any, *, field_name: str) -> dict[str, str]:
    if raw in (None, ""):
        return {}
    if not isinstance(raw, dict):
        raise ValueError(f"{field_name} must be an object")
    out: dict[str, str] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not key.strip():
            raise ValueError(f"{field_name} has an empty/non-string key")
        out[key.strip()] = str(value)
    return out


def _plan_env_overrides(plan: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    out.update(_env_mapping(plan.get("required_env"), field_name="required_env"))
    out.update(_env_mapping(plan.get("env_overrides"), field_name="env_overrides"))
    runtime_contract = plan.get("runtime_contract")
    if isinstance(runtime_contract, dict):
        out.update(
            _env_mapping(
                runtime_contract.get("required_env"),
                field_name="runtime_contract.required_env",
            )
        )
    return out


def _run_env_overrides(run: dict[str, Any], *, index: int) -> dict[str, str]:
    out: dict[str, str] = {}
    out.update(_env_mapping(run.get("required_env"), field_name=f"planned_runs[{index}].required_env"))
    out.update(_env_mapping(run.get("env_overrides"), field_name=f"planned_runs[{index}].env_overrides"))
    return out


def _env_truthy(name: str, *, env: dict[str, str] | None = None) -> bool:
    values = os.environ if env is None else env
    raw = str(values.get(name, "")).strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _dashboard_enabled_from_cli(
    no_dashboard_requested: bool,
    *,
    env: dict[str, str] | None = None,
) -> tuple[bool, str]:
    if not no_dashboard_requested:
        return True, "default_on"
    if _env_truthy("ALLOW_TEST_RUN_NO_DASHBOARD", env=env):
        return False, "breakglass_disabled"
    return True, "forced_on_no_dashboard_forbidden"


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


def _manifest_path_for_run(run: dict[str, Any], output_path: Path | None) -> Path | None:
    raw_manifest = str(run.get("manifest_json") or "").strip()
    if raw_manifest:
        return Path(raw_manifest)
    if output_path is None:
        return None
    return output_path.with_name(output_path.stem + "_manifest.json")


def _start_manifest_attach(
    *,
    manifest_path: Path,
    dashboard_url: str,
    log_path: Path,
    python_executable: str,
    wait_sec: float = MANIFEST_ATTACH_WAIT_SECONDS,
) -> tuple[subprocess.Popen[Any], dict[str, Any]]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    argv = [
        python_executable,
        "tools/attach_manifest_dashboard.py",
        "--manifest",
        str(manifest_path),
        "--dashboard-url",
        dashboard_url,
        "--wait-for-manifest-sec",
        str(max(0.0, wait_sec)),
    ]
    token = os.environ.get("DASHBOARD_INGEST_TOKEN", "").strip()
    if token:
        argv.extend(["--token", token])
    with log_path.open("a", encoding="utf-8", errors="replace", newline="\n") as log_file:
        log_file.write(
            f"START_ATTACH {datetime.now().isoformat()} COMMAND {subprocess.list2cmdline(argv)}\n"
        )
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
    return proc, {
        "pid": proc.pid,
        "manifest": str(manifest_path),
        "log": str(log_path),
        "command": subprocess.list2cmdline(argv),
    }


def _finish_manifest_attach(
    proc: subprocess.Popen[Any],
    *,
    run_returncode: int,
    timeout_sec: float = 10.0,
) -> int | str | None:
    try:
        return proc.wait(timeout=timeout_sec)
    except subprocess.TimeoutExpired:
        if run_returncode == 0:
            proc.terminate()
        else:
            proc.kill()
        try:
            return proc.wait(timeout=3.0)
        except subprocess.TimeoutExpired:
            proc.kill()
            return "killed_after_timeout"


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
    plan_env_updates = _plan_env_overrides(plan)
    env = os.environ.copy()
    env.update(plan_env_updates)
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
    dashboard_attach_started = 0
    dashboard_attach_records: list[dict[str, Any]] = []
    run_env_override_records: list[dict[str, Any]] = []
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
        manifest_path = _manifest_path_for_run(run, output_path)
        run_env_updates = _run_env_overrides(run, index=index)
        if run_env_updates:
            run_env_override_records.append({"index": index, "keys": sorted(run_env_updates)})
        run_env = env.copy()
        run_env.update(run_env_updates)

        if skip_existing and output_path is not None and output_path.exists():
            skipped += 1
            _write_line(marker, f"SKIP {datetime.now().isoformat()} index={index} output={output_path}")
            continue

        attach_proc: subprocess.Popen[Any] | None = None
        attach_record: dict[str, Any] | None = None
        if dashboard and manifest_path is not None:
            attach_proc, attach_record = _start_manifest_attach(
                manifest_path=manifest_path,
                dashboard_url=dashboard_url,
                log_path=log_dir / f"{stem}.dashboard_attach.log",
                python_executable=dashboard_python or sys.executable,
            )
            dashboard_attach_started += 1
            dashboard_attach_records.append({"index": index, **attach_record})

        _write_line(
            marker,
            (
                f"START {datetime.now().isoformat()} index={index} "
                f"post_id={run.get('post_id')} repeat={run.get('repeat_index')} output={output_json} "
                f"dashboard={dashboard_state.get('status')} "
                f"dashboard_attach_pid={(attach_record or {}).get('pid', '')} "
                f"manifest={manifest_path or ''} "
                f"env_override_keys={','.join(sorted(run_env_updates))}"
            ),
        )
        with combined.open("a", encoding="utf-8", errors="replace", newline="\n") as log_file:
            log_file.write(f"COMMAND {subprocess.list2cmdline(argv)}\n")
            log_file.flush()
            proc = subprocess.Popen(
                argv,
                cwd=Path.cwd(),
                env=run_env,
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
        attach_exit: int | str | None = None
        if attach_proc is not None:
            attach_exit = _finish_manifest_attach(attach_proc, run_returncode=rc)
            if attach_record is not None:
                attach_record["exit"] = attach_exit
        exists = bool(output_path and output_path.exists())
        _write_line(
            marker,
            f"END {datetime.now().isoformat()} exit={rc} exists={exists} dashboard_attach_exit={attach_exit}",
        )
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
                "plan_env_overrides": sorted(plan_env_updates),
                "run_env_overrides": run_env_override_records,
                "dashboard": dashboard_state,
                "stripped_no_dashboard_flags": stripped_no_dashboard,
                "dashboard_attach_started_runs": dashboard_attach_started,
                "dashboard_attach_processes": dashboard_attach_records,
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
        help=(
            "Legacy breakglass only: ignored unless ALLOW_TEST_RUN_NO_DASHBOARD=1. "
            "Test/runtime plans default to standalone dashboard forwarding."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    dashboard_enabled, dashboard_policy_status = _dashboard_enabled_from_cli(bool(args.no_dashboard))
    if args.no_dashboard:
        print(
            json.dumps(
                {
                    "event": "dashboard_policy",
                    "requested_no_dashboard": True,
                    "dashboard_enabled": dashboard_enabled,
                    "dashboard_policy_status": dashboard_policy_status,
                    "breakglass_env": "ALLOW_TEST_RUN_NO_DASHBOARD=1",
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
            flush=True,
        )
    return run_plan(
        plan_path=args.plan,
        log_dir=args.log_dir,
        env_updates=_env_overrides(list(args.set_env or [])),
        skip_existing=bool(args.skip_existing),
        limit=args.limit,
        dashboard=dashboard_enabled,
        dashboard_url=str(args.dashboard_url),
        dashboard_python=str(args.dashboard_python),
    )


if __name__ == "__main__":
    raise SystemExit(main())
