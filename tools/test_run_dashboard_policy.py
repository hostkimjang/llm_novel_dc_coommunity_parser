from __future__ import annotations

from pathlib import Path
from typing import Iterable


DEFAULT_TEST_RUN_REQUESTED_PARALLEL = 16
DEFAULT_DASHBOARD_URL = "http://127.0.0.1:8080"


def requested_parallel_for_test_run(row_count: int) -> int:
    """Return the user-locked requested parallel for non-empty test runs."""
    return DEFAULT_TEST_RUN_REQUESTED_PARALLEL if int(row_count or 0) > 0 else 0


def expected_effective_parallel(row_count: int) -> int:
    count = max(0, int(row_count or 0))
    if count == 0:
        return 0
    return min(DEFAULT_TEST_RUN_REQUESTED_PARALLEL, count)


def strip_no_dashboard(args: Iterable[str]) -> list[str]:
    return [str(arg) for arg in args if str(arg).strip() != "--no-dashboard"]


def start_dashboard_command(*, python_executable: str = "python") -> str:
    return f"{python_executable} tools/dashboard_server.py --host 127.0.0.1 --port 8080"


def attach_dashboard_command(
    manifest_path: str | Path,
    *,
    python_executable: str = "python",
    dashboard_url: str = DEFAULT_DASHBOARD_URL,
) -> str:
    return (
        f"{python_executable} tools/attach_manifest_dashboard.py "
        f"--manifest {Path(manifest_path).as_posix()} --dashboard-url {dashboard_url}"
    )


def dashboard_contract(
    *,
    manifest_path: str | Path | None = None,
    python_executable: str = "python",
    dashboard_url: str = DEFAULT_DASHBOARD_URL,
) -> dict[str, object]:
    contract: dict[str, object] = {
        "dashboard_policy": "WEB_DASHBOARD_REQUIRED_FOR_TEST_RUNS",
        "dashboard_url": dashboard_url,
        "start_dashboard_command": start_dashboard_command(python_executable=python_executable),
        "forbidden_flags": ["--no-dashboard"],
        "runner_cli_guard": (
            "tools/run_independent_plan.py ignores --no-dashboard unless "
            "ALLOW_TEST_RUN_NO_DASHBOARD=1 is explicitly set as a breakglass override."
        ),
        "live_forwarding_contract": (
            "Start tools/dashboard_server.py first; expert_main detects the standalone "
            "dashboard and forwards monitor events to it."
        ),
        "fallback_attach_contract": (
            "If a run was already started without live forwarding, attach its manifest "
            "with tools/attach_manifest_dashboard.py."
        ),
    }
    if manifest_path is not None:
        contract["attach_manifest_command"] = attach_dashboard_command(
            manifest_path,
            python_executable=python_executable,
            dashboard_url=dashboard_url,
        )
    return contract


def test_run_execution_contract(
    row_count: int,
    *,
    manifest_path: str | Path | None = None,
    python_executable: str = "python",
    dashboard_url: str = DEFAULT_DASHBOARD_URL,
) -> dict[str, object]:
    count = max(0, int(row_count or 0))
    return {
        "policy": "TEST_RUNS_USE_PARALLEL_16_AND_WEB_DASHBOARD",
        "row_count": count,
        "requested_parallel": requested_parallel_for_test_run(count),
        "expected_effective_parallel": expected_effective_parallel(count),
        "required_flags": ["--parallel 16"] if count > 0 else [],
        "forbidden_flags": ["--no-dashboard"],
        "dashboard_gate": "GO_PROGRESS_VIEW_NOT_APPROVAL",
        "dashboard_contract": dashboard_contract(
            manifest_path=manifest_path,
            python_executable=python_executable,
            dashboard_url=dashboard_url,
        ),
        "approval_boundary": (
            "Dashboard progress visibility and runtime completion are not semantic/full_scan approval."
        ),
    }
