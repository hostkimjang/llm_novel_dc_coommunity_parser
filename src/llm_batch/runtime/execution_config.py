"""실행 프로필을 해석하고 비밀값 없이 실제 유효 설정을 기록한다."""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit, urlunsplit

PROFILES = ("general", "low-load-validation", "paired-measurement")
NUMERIC_THREAD_KEYS = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                       "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS")
PROFILE_DEFAULTS = {
    "general": {},
    "low-load-validation": {"vlm": True, "ocr": True, "ledger_mode": "SHADOW",
                            "context_diagnostics": True, "requested_parallel": 1},
    "paired-measurement": {"ledger_mode": "REQUIRED", "context_diagnostics": True},
}
SETTING_CONTRACT = {
    "vlm": ("vlm", "LLM_VLM", False),
    "ocr": ("ocr", "LLM_OCR", True),
    "ledger_mode": ("decision_call_ledger", "PIPELINE_DECISION_CALL_LEDGER_MODE", "OFF"),
    "context_diagnostics": ("context_diagnostics", "EXPERT_CONTEXT_DIAGNOSTICS", False),
}


def _toggle(value: Any, default: bool) -> bool:
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def resolve_execution_settings(args: argparse.Namespace, environment: Mapping[str, str]) -> dict:
    """CLI > 환경변수 > 프로필 > 기존 기본값. 이 함수는 환경을 바꾸지 않는다."""
    cli_profile = getattr(args, "execution_profile", None)
    env_profile = environment.get("EXPERT_EXECUTION_PROFILE", "").strip()
    profile = cli_profile or env_profile or "general"
    if profile not in PROFILES:
        raise ValueError("알 수 없는 실행 프로필: " + str(profile))
    defaults = PROFILE_DEFAULTS[profile]
    settings, updates = {}, {}
    for key, (attribute, env_key, legacy_default) in SETTING_CONTRACT.items():
        cli = getattr(args, attribute, None)
        if cli is not None:
            value, source = cli, "CLI"
        elif env_key in environment:
            value, source = environment[env_key], "ENVIRONMENT"
        elif key in defaults:
            value, source = defaults[key], "PROFILE"
        else:
            value, source = legacy_default, "DEFAULT"
        if key == "ledger_mode":
            value = str(value or "OFF").strip().upper()
            if value not in {"OFF", "SHADOW", "REQUIRED"}:
                raise ValueError("호출 장부 모드는 OFF, SHADOW, REQUIRED 중 하나여야 합니다")
            updates[env_key] = value
        else:
            value = _toggle(value, legacy_default)
            updates[env_key] = "1" if value else "0"
        settings[key] = {"value": value, "source": source}
    explicit_parallel = bool(getattr(args, "parallel_explicit", False))
    parallel = max(1, int(getattr(args, "parallel", 1) or 1)) if explicit_parallel else defaults.get("requested_parallel", 1)
    settings["requested_parallel"] = {
        "value": parallel,
        "source": "CLI" if explicit_parallel else "PROFILE" if "requested_parallel" in defaults else "DEFAULT",
    }
    return {
        "profile": profile,
        "profile_source": "CLI" if cli_profile else "ENVIRONMENT" if env_profile else "DEFAULT",
        "settings": settings, "environment_updates": updates,
    }


def _windows_api():
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.argtypes = []
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.GetPriorityClass.argtypes = [wintypes.HANDLE]
    kernel.GetPriorityClass.restype = wintypes.DWORD
    kernel.SetPriorityClass.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.SetPriorityClass.restype = wintypes.BOOL
    pointer = ctypes.POINTER(ctypes.c_size_t)
    kernel.GetProcessAffinityMask.argtypes = [wintypes.HANDLE, pointer, pointer]
    kernel.GetProcessAffinityMask.restype = wintypes.BOOL
    kernel.SetProcessAffinityMask.argtypes = [wintypes.HANDLE, ctypes.c_size_t]
    kernel.SetProcessAffinityMask.restype = wintypes.BOOL
    return kernel


def observe_process_resources(environment: Mapping[str, str]) -> dict:
    result = {"pid": os.getpid(), "status": "OBSERVED", "priority_class": None,
              "affinity_mask": None, "logical_cpu_count": None,
              "numeric_threads": {key: environment.get(key) for key in NUMERIC_THREAD_KEYS}}
    if os.name == "nt":
        kernel = _windows_api()
        process = kernel.GetCurrentProcess()
        priority = kernel.GetPriorityClass(process)
        current, system = ctypes.c_size_t(), ctypes.c_size_t()
        if not priority or not kernel.GetProcessAffinityMask(process, ctypes.byref(current), ctypes.byref(system)):
            raise OSError(ctypes.get_last_error(), "현재 Python 프로세스 자원 설정을 확인하지 못했습니다")
        result.update(priority_class=priority, affinity_mask=current.value,
                      logical_cpu_count=current.value.bit_count())
    elif hasattr(os, "sched_getaffinity"):
        cpus = os.sched_getaffinity(0)
        result.update(affinity_mask=sum(1 << cpu for cpu in cpus), logical_cpu_count=len(cpus),
                      priority_class=os.getpriority(os.PRIO_PROCESS, 0) if hasattr(os, "getpriority") else None)
    else:
        result["status"] = "RESOURCE_API_UNAVAILABLE"
    return result


def apply_profile_resources(profile: str, environment: dict | os._Environ) -> dict:
    """저부하 프로필은 실제 실행 중인 CPython PID에 적용하고 반환값·관측을 검사한다."""
    if profile == "low-load-validation":
        for key in NUMERIC_THREAD_KEYS:
            environment[key] = "1"
        if os.name == "nt":
            kernel = _windows_api()
            process = kernel.GetCurrentProcess()
            current, system = ctypes.c_size_t(), ctypes.c_size_t()
            if not kernel.GetProcessAffinityMask(process, ctypes.byref(current), ctypes.byref(system)):
                raise OSError(ctypes.get_last_error(), "CPU affinity 조회 실패")
            mask = 2 if current.value & 2 else current.value & -current.value
            if not mask or not kernel.SetPriorityClass(process, 0x4000):
                raise OSError(ctypes.get_last_error(), "BelowNormal 적용 실패")
            if not kernel.SetProcessAffinityMask(process, mask):
                raise OSError(ctypes.get_last_error(), "단일 CPU affinity 적용 실패")
        elif hasattr(os, "sched_getaffinity") and hasattr(os, "sched_setaffinity"):
            cpus = os.sched_getaffinity(0)
            os.sched_setaffinity(0, {min(cpus)})
            if hasattr(os, "getpriority") and hasattr(os, "setpriority"):
                os.setpriority(os.PRIO_PROCESS, 0, max(5, os.getpriority(os.PRIO_PROCESS, 0)))
        else:
            raise RuntimeError("이 플랫폼에서는 저부하 프로필의 CPU 정책을 적용할 수 없습니다")
    observed = observe_process_resources(environment)
    if profile == "low-load-validation":
        valid = observed["logical_cpu_count"] == 1 and all(value == "1" for value in observed["numeric_threads"].values())
        if os.name == "nt":
            valid = valid and observed["priority_class"] == 0x4000
        if not valid:
            raise RuntimeError("저부하 프로필 자원 설정의 실제 관측이 요청과 다릅니다")
        observed["status"] = "LOW_LOAD_VERIFIED"
    return observed


def sanitized_url(value: str) -> str:
    """대시보드 주소에서 인증 정보·query·fragment를 제거한다."""
    try:
        parts = urlsplit(value)
        if parts.scheme not in {"http", "https"} or not parts.hostname:
            return ""
        host = "[" + parts.hostname + "]" if ":" in parts.hostname else parts.hostname
        if parts.port is not None:
            host += ":" + str(parts.port)
        return urlunsplit((parts.scheme, host, parts.path, "", ""))
    except ValueError:
        return ""


def source_snapshot(entry_point: Path) -> dict:
    entry = entry_point.resolve()
    root = entry.parent
    relative_files = ("expert_main.py", "src/llm_batch/agentic_pipeline.py",
        "src/llm_batch/grounding/context_projection_contract.py",
        "src/llm_batch/grounding/source_context_explanation.py",
        "src/llm_batch/grounding/source_speech_structure.py",
        "src/llm_batch/grounding/source_context_diagnostics.py",
        "src/llm_batch/grounding/candidate_retrieval_shadow.py",
        "src/llm_batch/runtime/candidate_retrieval.py",
        "src/llm_batch/grounding/candidate_reranker_shadow.py",
        "src/llm_batch/runtime/candidate_reranker.py",
        "src/llm_batch/grounding/candidate_reranker_capture.py",
        "src/llm_batch/runtime/candidate_capture.py",
        "src/llm_batch/runtime/candidate_calibration.py",
        "src/llm_batch/runtime/candidate_inference.py",
        "src/llm_batch/grounding/candidate_reranker_inference_graph.py",
        "src/llm_batch/grounding/candidate_reranker_calibration_inference.py",
        "tools/build_candidate_inference_bundle.py",
        "src/llm_batch/grounding/candidate_reranker_calibration.py",
        "src/llm_batch/grounding/candidate_reranker_calibration_data.py",
        "src/llm_batch/grounding/candidate_reranker_event_bridge.py",
        "src/llm_batch/grounding/candidate_set_calibration_shadow.py",
        "src/llm_batch/grounding/candidate_set_shadow.py",
        "src/llm_batch/grounding/candidate_reranker_roles.py",
        "src/llm_batch/grounding/candidate_reranker_semantics.py",
        "src/llm_batch/grounding/candidate_reranker_semantic_input.py",
        "src/llm_batch/grounding/claim_scope_contract.py",
        "src/llm_batch/grounding/candidate_reranker_alias_evidence.py",
        "src/llm_batch/runtime/candidate_semantics.py",
        "src/llm_batch/grounding/candidate_reranker_learned.py",
        "src/llm_batch/grounding/candidate_reranker_nil_learned.py",
        "src/llm_batch/grounding/reranker_training_split.py",
        "tools/run_candidate_reranker_training.py",
        "tools/run_candidate_reranker_calibration.py",
        "src/llm_batch/runtime/paired_execution.py",
        "src/llm_batch/measurement/paired_execution_policy.py",
        "src/llm_batch/measurement/paired_measurement_readback.py",
        "src/llm_batch/llm/client.py",
        "src/llm_batch/prompts/expert_prompts.py",
        "src/llm_batch/grounding/community_knowledge.py",
        "src/llm_batch/runtime/community_knowledge.py",
        "src/llm_batch/experts/orchestrator.py",
        "src/llm_batch/experts/decoder.py",
        "src/llm_batch/measurement/recovery_provider_contract.py",
        "src/llm_batch/measurement/recovery_input_projection.py",
        "src/llm_batch/measurement/recovery_provider_readback.py",
        "src/llm_batch/ledger/recovery_provider_journal.py",
        "src/llm_batch/runtime/recovery_provider_transport.py",
        "src/llm_batch/measurement/recovery_native_source.py",
        "src/llm_batch/runtime/recovery_native_context.py",
        "src/llm_batch/runtime/recovery_native_io.py",
        "src/llm_batch/runtime/recovery_native_workflow.py",
        "src/llm_batch/ledger/recovery_native_journal.py",
        "src/llm_batch/experts/verifier.py",
        "src/llm_batch/experts/synthesizer.py",
        "src/llm_batch/experts/arbiter.py",
        "src/llm_batch/runtime/recovery_transport.py",
        "src/llm_batch/monitor/recovery_provider_view.py",
        "src/llm_batch/monitor/recovery_native_view.py",
        "src/llm_batch/runtime/recovery_native_batch.py",
        "tools/run_recovery_provider.py",
        "src/llm_batch/runtime/execution_config.py")
    hashes = {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
              for name in relative_files if (root / name).is_file()}
    return {"entry_point": str(entry), "entry_sha256": hashlib.sha256(entry.read_bytes()).hexdigest(),
            "runtime_source_sha256": hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest(),
            "runtime_source_files": hashes, "source_scope": "SELECTED_RUNTIME_FILES"}


def build_execution_config(resolved: Mapping[str, Any], *, source: Mapping[str, Any], resources: Mapping[str, Any],
                           requested_parallel: int, effective_parallel: int, dashboard_enabled: bool,
                           dashboard_mode: str, dashboard_url: str, output_file: str, image_post_count: int,
                           image_review_ready: bool, image_skip_reasons: list, measurement_mode: str) -> dict:
    return {"schema_version": "expert_execution_config_v1", "profile": resolved["profile"],
        "profile_source": resolved["profile_source"], "settings": dict(resolved["settings"]),
        "source": dict(source), "resources": dict(resources), "requested_parallel": requested_parallel,
        "effective_parallel": effective_parallel,
        "dashboard": {"enabled": dashboard_enabled, "mode": dashboard_mode, "url": sanitized_url(dashboard_url)},
        "output_file": output_file,
        "image_review": {"image_post_count": image_post_count, "ready": image_review_ready,
                         "skip_reason_codes": list(image_skip_reasons)},
        "compression": {"status": "OFF_NOT_REQUESTED", "scope": "artifact_generation"},
        "measurement": {"execution_mode": measurement_mode, "formal_kpi_status": "NOT_ESTIMABLE"}}
