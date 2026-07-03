from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


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


def run_plan(
    *,
    plan_path: Path,
    log_dir: Path,
    env_updates: dict[str, str],
    skip_existing: bool,
    limit: int | None,
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

    completed = 0
    skipped = 0
    for index, run in enumerate(selected, start=1):
        if not isinstance(run, dict):
            raise ValueError(f"planned_runs[{index}] is not an object")
        argv = run.get("command_argv")
        if not isinstance(argv, list) or not all(isinstance(item, str) for item in argv):
            raise ValueError(f"planned_runs[{index}] has invalid command_argv")
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
                f"post_id={run.get('post_id')} repeat={run.get('repeat_index')} output={output_json}"
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
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return run_plan(
        plan_path=args.plan,
        log_dir=args.log_dir,
        env_updates=_env_overrides(list(args.set_env or [])),
        skip_existing=bool(args.skip_existing),
        limit=args.limit,
    )


if __name__ == "__main__":
    raise SystemExit(main())
