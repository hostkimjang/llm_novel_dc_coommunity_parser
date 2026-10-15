from __future__ import annotations

"""연구 전용 벤치마크의 실행부터 검증까지 묶는 안전한 workflow.

이 wrapper는 기존 benchmark runner의 score semantics를 재구현하지 않는다.
standalone dashboard를 준비하고 baseline/challenge runner를 순차 실행한 뒤,
각 terminal manifest와 focused test를 검증하고 한국어 요약을 남긴다.
모든 생성물은 하나의 새 ``out/research/`` 하위 디렉터리에만 기록한다.
"""

import argparse
import json
import os
import platform
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
RESEARCH_ROOT = (ROOT / "out/research").resolve()
RUNNER = ROOT / "tools/run_research_local_benchmark.py"
DASHBOARD_SERVER = ROOT / "tools/dashboard_server.py"
WORKFLOW_SCHEMA_VERSION = "research-local-grounding-workflow-v1"
REQUESTED_PARALLEL = 16
PARTITIONS = (
    ("baseline", "tests/fixtures/research_local_benchmark_v1.jsonl"),
    ("challenge", "tests/fixtures/research_local_benchmark_challenge_v1.jsonl"),
)

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.llm_batch.grounding.research_local_benchmark import (  # noqa: E402
    sha256_file,
    sha256_value,
    validate_local_endpoint,
    validate_terminal_manifest,
)


class WorkflowError(RuntimeError):
    """Workflow contract or child-process failure."""


def _write_text(path: Path, value: str) -> None:
    path.write_text(value, encoding="utf-8", newline="\n")


def _write_json(path: Path, value: Any) -> None:
    temporary = path.with_name(path.name + ".tmp")
    _write_text(temporary, json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    os.replace(temporary, path)


def _git_state() -> dict[str, Any]:
    def run(*args: str) -> str:
        completed = subprocess.run(
            ["git", *args],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        return completed.stdout.strip()

    return {"commit": run("rev-parse", "HEAD"), "dirty": bool(run("status", "--porcelain"))}


def parse_dashboard_url(url: str) -> tuple[str, int]:
    """Return a loopback host/port and reject network-exposed dashboards."""

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise WorkflowError("dashboard URL must be HTTP(S)")
    if parsed.hostname not in {"127.0.0.1", "localhost"}:
        raise WorkflowError("workflow dashboard must use a loopback host")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise WorkflowError("dashboard URL must not include a path, query, or fragment")
    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError as exc:
        raise WorkflowError("dashboard URL port is invalid") from exc
    if not 1 <= port <= 65535:
        raise WorkflowError("dashboard URL port is out of range")
    return parsed.hostname, port


def _dashboard_health(base_url: str) -> dict[str, Any] | None:
    request = urllib.request.Request(f"{base_url.rstrip('/')}/api/health", method="GET")
    try:
        with urllib.request.urlopen(request, timeout=2.0) as response:
            payload = json.loads(response.read().decode("utf-8") or "{}")
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _is_standalone_health(payload: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(payload, dict)
        and payload.get("ok") is True
        and payload.get("standalone") is True
    )


def _dashboard_receipt(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": payload.get("ok"),
        "standalone": payload.get("standalone"),
        "service": payload.get("service"),
        "pid": payload.get("pid"),
    }


@dataclass
class DashboardHandle:
    url: str
    process: subprocess.Popen[Any] | None = None
    log_handle: Any = None

    @property
    def owned_process(self) -> bool:
        return self.process is not None

    def close(self) -> None:
        if self.process is None:
            return
        try:
            if self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=5)
        finally:
            if self.log_handle is not None:
                self.log_handle.close()


def ensure_dashboard(base_url: str, output_root: Path, *, timeout_sec: float = 20.0) -> tuple[DashboardHandle, dict[str, Any]]:
    """Reuse a healthy standalone server or start one owned by this workflow."""

    parse_dashboard_url(base_url)
    current = _dashboard_health(base_url)
    if _is_standalone_health(current):
        return DashboardHandle(base_url), current

    host, port = parse_dashboard_url(base_url)
    log_handle = (output_root / "dashboard_server.log").open("w", encoding="utf-8", newline="\n")
    process = subprocess.Popen(
        [sys.executable, str(DASHBOARD_SERVER), "--host", host, "--port", str(port)],
        cwd=ROOT,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        text=True,
    )
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        if process.poll() is not None:
            log_handle.flush()
            message = (output_root / "dashboard_server.log").read_text(encoding="utf-8", errors="replace")
            log_handle.close()
            raise WorkflowError(f"dashboard server exited before health check: {message[-1000:]}")
        health = _dashboard_health(base_url)
        if _is_standalone_health(health):
            return DashboardHandle(base_url, process, log_handle), health
        time.sleep(0.25)

    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)
    log_handle.close()
    raise WorkflowError(f"dashboard health timeout: {base_url}")


def build_runner_command(
    *,
    input_path: Path,
    output_dir: Path,
    dashboard_url: str,
    requested_parallel: int = REQUESTED_PARALLEL,
    local_llm_endpoint: str | None = None,
    local_llm_model: str | None = None,
    local_llm_fingerprint: str | None = None,
    allow_configured_remote_vllm: bool = False,
) -> list[str]:
    if requested_parallel != REQUESTED_PARALLEL:
        raise WorkflowError("research workflow requires requested --parallel 16")
    local_values = [local_llm_endpoint, local_llm_model, local_llm_fingerprint]
    provided_local_values = sum(value is not None for value in local_values)
    if provided_local_values not in {0, 3}:
        raise WorkflowError("local LLM endpoint, model, fingerprint must be provided together")
    if allow_configured_remote_vllm and provided_local_values == 0:
        raise WorkflowError("configured remote vLLM opt-in requires endpoint, model, and fingerprint")
    command = [
        sys.executable,
        str(RUNNER),
        "--input",
        str(input_path),
        "--output-dir",
        str(output_dir),
        "--parallel",
        str(requested_parallel),
        "--dashboard-url",
        dashboard_url,
    ]
    if provided_local_values == 3:
        command.extend(
            [
                "--local-llm-endpoint",
                local_llm_endpoint,
                "--local-llm-model",
                local_llm_model,
                "--local-llm-fingerprint",
                local_llm_fingerprint,
            ]
        )
        if allow_configured_remote_vllm:
            command.append("--allow-configured-remote-vllm")
    return command


def _run_logged(command: Sequence[str], *, stdout_path: Path, stderr_path: Path) -> int:
    environment = os.environ.copy()
    environment.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    completed = subprocess.run(
        list(command),
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
        check=False,
    )
    _write_text(stdout_path, completed.stdout or "")
    _write_text(stderr_path, completed.stderr or "")
    return int(completed.returncode)


def _resolve_input(value: str) -> Path:
    path = Path(value)
    resolved = (ROOT / path).resolve() if not path.is_absolute() else path.resolve()
    if not resolved.is_file():
        raise WorkflowError(f"input fixture does not exist: {resolved}")
    return resolved


def _default_output_root() -> Path:
    return RESEARCH_ROOT / datetime.now().astimezone().strftime("research_workflow_%Y%m%d_%H%M%S")


def _partition_summary(
    *,
    name: str,
    input_path: Path,
    output_dir: Path,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    metrics_path = Path(str(manifest["artifacts"]["metrics"]["path"]))
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    return {
        "partition": name,
        "input_file": str(input_path),
        "input_sha256": sha256_file(input_path),
        "output_dir": str(output_dir),
        "manifest_file": str(output_dir / "manifest.json"),
        "manifest_sha256": manifest.get("manifest_sha256"),
        "benchmark_input_count": manifest.get("benchmark_input_count"),
        "requested_parallel": manifest.get("requested_parallel"),
        "effective_parallel": manifest.get("effective_parallel"),
        "completed_count": manifest.get("completed_count"),
        "terminal_status_counts": manifest.get("terminal_status_counts"),
        "dashboard_status": manifest.get("dashboard", {}).get("status"),
        "local_llm": manifest.get("models", {}).get("local_llm"),
        "arms": {
            arm: {
                "denominator": values.get("denominator"),
                "correct": values.get("correct"),
                "accuracy": values.get("accuracy"),
                "terminal_status_counts": values.get("terminal_status_counts"),
                "diagnostics": {
                    "case_type_counts": values.get("case_type_counts"),
                    "expected_action_counts": values.get("expected_action_counts"),
                    "failure_stage_counts": values.get("failure_stage_counts"),
                    "candidate_recall": values.get("candidate_recall"),
                    "conditional_selection": values.get("conditional_selection"),
                },
            }
            for arm, values in metrics.get("arms", {}).items()
        },
    }


def seal_workflow_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    sealed = dict(manifest)
    sealed.pop("workflow_manifest_sha256", None)
    sealed["workflow_manifest_sha256"] = sha256_value(sealed)
    return sealed


def _format_count_map(value: Any) -> str:
    if not isinstance(value, dict):
        return "NOT_RECORDED"
    nonzero = [(str(key), item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0])) if item]
    return ", ".join(f"{key}={item}" for key, item in nonzero) if nonzero else "none"


def _format_ratio(value: Any) -> str:
    if not isinstance(value, dict):
        return "NOT_RECORDED"
    return f"{value.get('numerator', 'NA')}/{value.get('denominator', 'NA')}"


def render_workflow_report(manifest: dict[str, Any]) -> str:
    lines = [
        "# 연구 전용 로컬 grounding benchmark workflow 결과",
        "",
        f"- 판정: `{manifest['claim_level']}`",
        f"- workflow schema: `{manifest['schema_version']}`",
        f"- output root: `{manifest['output_root']}`",
        f"- dashboard: `{manifest['dashboard']['status']}` / `{manifest['dashboard']['url']}`",
        f"- requested parallel: `{manifest['requested_parallel']}`",
        "- 중앙 Slang DB·production·publication 쓰기: `0`",
        "",
        "| partition | 입력 | requested/effective | validator | terminal 상태 |",
        "|---|---:|---:|---|---|",
    ]
    for name in ("baseline", "challenge"):
        item = manifest["partitions"][name]
        counts = ", ".join(
            f"{key}={value}"
            for key, value in item["terminal_status_counts"].items()
            if value
        )
        lines.append(
            f"| {name} | {item['benchmark_input_count']} | "
            f"{item['requested_parallel']}/{item['effective_parallel']} | PASS | {counts} |"
        )
    lines.extend(["", "## 진단 보존"])
    for name in ("baseline", "challenge"):
        item = manifest["partitions"][name]
        for arm_name, arm in sorted((item.get("arms") or {}).items()):
            diagnostics = arm.get("diagnostics") or {}
            if not diagnostics:
                continue
            recall = diagnostics.get("candidate_recall") or {}
            lines.append(
                f"- {name}/{arm_name}: failure stage `{_format_count_map(diagnostics.get('failure_stage_counts'))}`; "
                f"Recall@5 `{_format_ratio(recall.get('recall_at_5'))}`; "
                f"조건부 selection `{_format_ratio(diagnostics.get('conditional_selection'))}`."
            )
    test = manifest["tests"]["focused_unittest"]
    lines.extend(
        [
            "",
            "## 게이트",
            f"- focused unittest: `{test['status']}`",
            "- baseline/challenge terminal manifest validator: `PASS`",
            "- 각 child runner는 dashboard pre/post health와 전체 terminal 분모를 기록했다.",
            "- `ERROR`, `UNAVAILABLE`, `ABSTAIN`, `NIL`은 전체 입력 분모에서 제거하지 않았다.",
            "- 이 workflow는 synthetic fixture 연구 증거이며 P0·production·publication·full-scan 승인 근거가 아니다.",
            "",
        ]
    )
    return "\n".join(lines)


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="연구 benchmark 실행·검증 workflow")
    parser.add_argument("--output-root", help="새 out/research 하위 output root")
    parser.add_argument("--dashboard-url", default="http://127.0.0.1:8765")
    parser.add_argument("--parallel", type=int, default=REQUESTED_PARALLEL)
    parser.add_argument("--baseline-input", default=PARTITIONS[0][1])
    parser.add_argument("--challenge-input", default=PARTITIONS[1][1])
    parser.add_argument(
        "--local-llm-endpoint",
        help="OpenAI-compatible endpoint; endpoint, model, fingerprint는 함께 제공해야 함",
    )
    parser.add_argument(
        "--local-llm-model",
        help="모델 ID; endpoint, model, fingerprint는 함께 제공해야 함",
    )
    parser.add_argument(
        "--local-llm-fingerprint",
        help="모델 weights 또는 endpoint/model metadata SHA256; endpoint, model과 함께 제공해야 함",
    )
    parser.add_argument(
        "--allow-configured-remote-vllm",
        action="store_true",
        help="expert_main에 설정된 vLLM endpoint를 명시적으로 사용",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    dashboard: DashboardHandle | None = None
    output_root: Path | None = None
    started = time.time()
    try:
        if args.parallel != REQUESTED_PARALLEL:
            raise WorkflowError("workflow requested parallel must be exactly 16")
        local_values = [args.local_llm_endpoint, args.local_llm_model, args.local_llm_fingerprint]
        if sum(value is not None for value in local_values) not in {0, 3}:
            raise WorkflowError("local LLM endpoint, model, fingerprint must be provided together")
        if args.local_llm_endpoint:
            validate_local_endpoint(
                args.local_llm_endpoint,
                allow_configured_remote=args.allow_configured_remote_vllm,
            )

        output_root = (
            (ROOT / args.output_root).resolve()
            if args.output_root and not Path(args.output_root).is_absolute()
            else Path(args.output_root).resolve()
            if args.output_root
            else _default_output_root()
        )
        output_root = output_root.resolve()
        from src.llm_batch.grounding.research_local_benchmark import ensure_research_output_dir

        ensure_research_output_dir(output_root, RESEARCH_ROOT)
        output_root.mkdir(parents=True)
        dashboard, preflight = ensure_dashboard(args.dashboard_url, output_root)

        partitions: dict[str, dict[str, Any]] = {}
        for name, input_value in PARTITIONS:
            input_path = _resolve_input(
                args.baseline_input if name == "baseline" else args.challenge_input
            )
            child_output = output_root / name
            command = build_runner_command(
                input_path=input_path,
                output_dir=child_output,
                dashboard_url=args.dashboard_url,
                requested_parallel=args.parallel,
                local_llm_endpoint=args.local_llm_endpoint,
                local_llm_model=args.local_llm_model,
                local_llm_fingerprint=args.local_llm_fingerprint,
                allow_configured_remote_vllm=args.allow_configured_remote_vllm,
            )
            stdout_path = output_root / f"{name}_runner.stdout.log"
            stderr_path = output_root / f"{name}_runner.stderr.log"
            return_code = _run_logged(command, stdout_path=stdout_path, stderr_path=stderr_path)
            if return_code != 0:
                detail = stderr_path.read_text(encoding="utf-8", errors="replace")
                raise WorkflowError(f"{name} runner failed with exit code {return_code}: {detail[-1000:]}")
            manifest_path = child_output / "manifest.json"
            manifest = validate_terminal_manifest(manifest_path, research_root=RESEARCH_ROOT)
            partitions[name] = _partition_summary(
                name=name,
                input_path=input_path,
                output_dir=child_output,
                manifest=manifest,
            )

        test_stdout = output_root / "focused_tests.stdout.log"
        test_stderr = output_root / "focused_tests.stderr.log"
        test_command = [
            sys.executable,
            "-m",
            "unittest",
            "-q",
            "tests.test_research_local_benchmark",
            "tests.test_research_local_benchmark_workflow",
        ]
        test_return_code = _run_logged(test_command, stdout_path=test_stdout, stderr_path=test_stderr)
        if test_return_code != 0:
            detail = test_stderr.read_text(encoding="utf-8", errors="replace")
            raise WorkflowError(f"focused tests failed with exit code {test_return_code}: {detail[-1000:]}")

        postflight = _dashboard_health(args.dashboard_url)
        if not _is_standalone_health(postflight):
            raise WorkflowError("dashboard postflight health failed")

        manifest = seal_workflow_manifest(
            {
                "schema_version": WORKFLOW_SCHEMA_VERSION,
                "workflow": "research_local_benchmark",
                "claim_level": "RESEARCH_EVIDENCE_ONLY",
                "publication_mode": "OFFLINE_SHADOW",
                "p0_authority_claimed": False,
                "production_authority_claimed": False,
                "full_scan_approval": False,
                "central_slang_db_write": False,
                "central_slang_db_writes": 0,
                "output_root": str(output_root),
                "requested_parallel": args.parallel,
                "effective_parallel": {
                    name: partitions[name]["effective_parallel"] for name in ("baseline", "challenge")
                },
                "partitions": partitions,
                "dashboard": {
                    "url": args.dashboard_url,
                    "status": "CONNECTED",
                    "owned_process": dashboard.owned_process,
                    "preflight_receipt": _dashboard_receipt(preflight),
                    "postflight_receipt": _dashboard_receipt(postflight),
                },
                "tests": {
                    "focused_unittest": {
                        "status": "PASS",
                        "return_code": test_return_code,
                        "command": test_command,
                        "stdout": str(test_stdout),
                        "stderr": str(test_stderr),
                    }
                },
                "local_llm": {
                    "status": args.local_llm_model or "UNAVAILABLE_MODEL_IDENTITY",
                    "endpoint_configured": bool(args.local_llm_endpoint),
                    "endpoint_scope": (
                        "CONFIGURED_REMOTE_VLLM" if args.allow_configured_remote_vllm else "LOOPBACK_ONLY"
                    ),
                },
                "git": _git_state(),
                "runtime": {"python": sys.version, "platform": platform.platform()},
                "started_at": datetime.fromtimestamp(started).astimezone().isoformat(timespec="seconds"),
                "ended_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                "duration_sec": round(time.time() - started, 6),
            }
        )
        workflow_manifest_path = output_root / "workflow_manifest.json"
        report_path = output_root / "report_ko.md"
        _write_json(workflow_manifest_path, manifest)
        _write_text(report_path, render_workflow_report(manifest))
        print(
            json.dumps(
                {
                    "workflow_manifest": str(workflow_manifest_path),
                    "report": str(report_path),
                    "partitions": {
                        name: {
                            "input": item["benchmark_input_count"],
                            "requested_parallel": item["requested_parallel"],
                            "effective_parallel": item["effective_parallel"],
                            "terminal_status_counts": item["terminal_status_counts"],
                        }
                        for name, item in partitions.items()
                    },
                    "focused_tests": "PASS",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    except (WorkflowError, ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"research workflow failed: {exc}", file=sys.stderr)
        return 1
    finally:
        if dashboard is not None:
            dashboard.close()


if __name__ == "__main__":
    raise SystemExit(main())
