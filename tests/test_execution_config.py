"""프로필 우선순위, 실제 자식 PID 저부하 적용과 공개 설정 경계를 검증한다."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import Mock, patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from llm_batch.runtime.execution_config import (
    apply_profile_resources, build_execution_config, resolve_execution_settings, sanitized_url,
)


def arguments(**values):
    return argparse.Namespace(parallel=1, parallel_explicit=False, **values)


def test_default_profile_preserves_existing_defaults_and_does_not_change_environment():
    env = {"API_KEY": "never-display"}
    resolved = resolve_execution_settings(arguments(), env)
    assert resolved["profile"] == "general"
    assert {key: row["value"] for key, row in resolved["settings"].items()} == {
        "vlm": False, "ocr": True, "ledger_mode": "OFF", "context_diagnostics": False, "requested_parallel": 1,
    }
    assert env == {"API_KEY": "never-display"}


def test_cli_then_environment_then_profile_precedence_with_provenance():
    args = arguments(execution_profile="low-load-validation", vlm="off", context_diagnostics="off")
    resolved = resolve_execution_settings(args, {"LLM_VLM": "1", "LLM_OCR": "0", "PIPELINE_DECISION_CALL_LEDGER_MODE": "OFF"})
    assert resolved["settings"]["vlm"] == {"value": False, "source": "CLI"}
    assert resolved["settings"]["ocr"] == {"value": False, "source": "ENVIRONMENT"}
    assert resolved["settings"]["ledger_mode"] == {"value": "OFF", "source": "ENVIRONMENT"}
    assert resolved["settings"]["requested_parallel"] == {"value": 1, "source": "PROFILE"}
    assert resolved["settings"]["context_diagnostics"]["value"] is False


def test_profile_defaults_and_explicit_parallel_remain_distinct():
    args = arguments(execution_profile="low-load-validation")
    args.parallel, args.parallel_explicit = 3, True
    resolved = resolve_execution_settings(args, {})
    assert resolved["settings"]["ledger_mode"] == {"value": "SHADOW", "source": "PROFILE"}
    assert resolved["settings"]["context_diagnostics"]["value"] is True
    assert resolved["settings"]["requested_parallel"] == {"value": 3, "source": "CLI"}
    assert resolve_execution_settings(arguments(), {"EXPERT_EXECUTION_PROFILE": "paired-measurement"})["settings"]["ledger_mode"]["value"] == "REQUIRED"


def test_unknown_profile_or_ledger_fails_before_execution():
    with pytest.raises(ValueError):
        resolve_execution_settings(arguments(), {"EXPERT_EXECUTION_PROFILE": "typo"})
    with pytest.raises(ValueError):
        resolve_execution_settings(arguments(), {"PIPELINE_DECISION_CALL_LEDGER_MODE": "typo"})


def test_execution_snapshot_is_bounded_to_allowlisted_settings_and_redacts_url():
    resolved = resolve_execution_settings(arguments(), {"SECRET_TOKEN": "never-display"})
    snapshot = build_execution_config(resolved, source={"entry_point": "/source/expert_main.py"}, resources={"pid": 1},
        requested_parallel=16, effective_parallel=2, dashboard_enabled=True, dashboard_mode="standalone_forward",
        dashboard_url="https://user:password@example.test:8080/dashboard?token=secret#fragment", output_file="out/result.json",
        image_post_count=1, image_review_ready=False, image_skip_reasons=["VLM_DISABLED"], measurement_mode="NORMAL")
    assert snapshot["dashboard"]["url"] == "https://example.test:8080/dashboard"
    assert snapshot["measurement"]["formal_kpi_status"] == "NOT_ESTIMABLE"
    assert snapshot["compression"]["status"] == "OFF_NOT_REQUESTED"
    assert snapshot["effective_parallel"] == 2
    assert "secret" not in json.dumps(snapshot).lower()
    assert "environment_updates" not in snapshot
    assert sanitized_url("http://[::1]:8080/?key=a") == "http://[::1]:8080/"


@pytest.mark.skipif(os.name != "nt", reason="Windows 실제 프로세스 자원 검사")
def test_low_load_policy_is_verified_on_real_cpython_child_pid():
    program = """
import json, os
from pathlib import Path
from llm_batch.runtime.execution_config import apply_profile_resources
import llm_batch.runtime.execution_config as config
assert Path(config.__file__).resolve().is_relative_to(Path.cwd().resolve())
observed = apply_profile_resources('low-load-validation', os.environ)
assert observed['pid'] == os.getpid()
print(json.dumps(observed))
"""
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src") + os.pathsep + str(ROOT), PYTHONDONTWRITEBYTECODE="1")
    result = subprocess.run([sys.executable, "-B", "-c", program], cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    observed = json.loads(result.stdout)
    assert observed["status"] == "LOW_LOAD_VERIFIED"
    assert observed["priority_class"] == 0x4000
    assert observed["logical_cpu_count"] == 1
    assert observed["affinity_mask"].bit_count() == 1
    assert set(observed["numeric_threads"].values()) == {"1"}


@pytest.mark.skipif(os.name != "nt", reason="Windows API 실패 검사")
def test_failed_windows_api_is_not_reported_as_applied():
    kernel = Mock()
    kernel.GetProcessAffinityMask.return_value = 0
    with patch("llm_batch.runtime.execution_config._windows_api", return_value=kernel):
        with pytest.raises(OSError):
            apply_profile_resources("low-load-validation", {})


def test_main_cli_profile_parser_does_not_consume_importers_options():
    import expert_main
    args = expert_main._parse_args(["--execution-profile", "low-load-validation", "--parallel=2", "--context-diagnostics", "off"])
    assert args.parallel_explicit and args.parallel == 2
    assert args.execution_profile == "low-load-validation"
    assert not expert_main._parse_args([]).parallel_explicit
    for argv in (["--par", "3"], ["-p3"]):
        parsed = expert_main._parse_args(argv)
        assert parsed.parallel == 3 and parsed.parallel_explicit
    assert expert_main._publication_decision_environment({"EXPERT_CONTEXT_DIAGNOSTICS": "1"}) == {}
    with pytest.raises(ValueError, match="needs complete RunSpec"):
        expert_main._decision_call_measurement_config({"PIPELINE_DECISION_CALL_LEDGER_MODE": "REQUIRED"})
