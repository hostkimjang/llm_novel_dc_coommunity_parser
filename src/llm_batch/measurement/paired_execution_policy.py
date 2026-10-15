"""Low-load policy and START/END binding; no providers or policy application.

Supplied observations prove byte/field consistency, not trusted OS provenance,
remote model immutability, continuous resource limits, price, or quality.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import time
from typing import Any, Mapping
from urllib.parse import urlsplit

POLICY_SCHEMA = "paired_measurement_low_load_policy_v1"
PROJECTION_SCHEMA = "paired_execution_config_projection_v1"
PARALLEL12_POLICY_SCHEMA = "paired_measurement_parallel12_policy_v1"
PARALLEL12_PROJECTION_SCHEMA = "paired_execution_config_projection_v2"
OBSERVATION_SCHEMA = "paired_execution_observation_v1"
MAX_POLICY_BYTES = 64 * 1024
MAX_OBSERVATION_BYTES = 128 * 1024
NUMERIC_THREAD_KEYS = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                       "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS")
RUNTIME_FIELDS = (
    "llm_model", "llm_endpoint", "generation_config_sha256", "prompt_sha256",
    "publication_config_sha256", "publication_decision_environment_sha256",
    "mcp_endpoint_pool_sha256", "mcp_health_workers", "mcp_health_probe_batch_size",
    "mcp_health_required_ok_count", "mcp_health_include_search", "mcp_health_light_mode",
    "mcp_reuse_shards_only", "mcp_auto_up_shards", "mcp_auto_recreate_shards",
    "mcp_auto_scale_up_missing_shards", "mutable_context_mode", "batch_context_enabled",
    "central_slang_db_write_allowed", "slang_mode", "slang_snapshot_sha256",
    "candidate_retrieval_mode", "community_knowledge_mode", "candidate_reranker_mode",
)
_SETTINGS = {"vlm", "ocr", "ledger_mode", "context_diagnostics", "requested_parallel"}
_PROJECTION = {"schema_version", "profile", "settings", "requested_parallel", "effective_parallel",
               "dashboard_enabled", "compression_status", "image_review_ready", "source", "runtime"}
_POLICY = {"schema_version", "policy_id", "config_projection", "config_projection_sha256", "resources",
           "health", "observation_scope", "policy_sha256"}
_BINDING = {"pair_id", "arm", "run_id", "attempt_id", "input_sha256", "publication_scope_id"}
_OBSERVATION = {"schema_version", "phase", "binding", "policy_sha256", "config_projection",
                "config_projection_sha256", "observed_at", "monotonic_ns", "resources", "health",
                "start_observation_sha256", "observation_sha256"}
_SHA = re.compile(r"[0-9a-f]{64}\Z")


class PairedExecutionPolicyError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise PairedExecutionPolicyError(code)


def _bytes(value: Any) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                          allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise PairedExecutionPolicyError("JSON_VALUE_INVALID") from exc


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(_bytes(value)).hexdigest()


def _copy(value: Any, maximum: int) -> Any:
    raw = _bytes(value)
    _require(len(raw) <= maximum, "JSON_BYTE_LIMIT")
    return json.loads(raw)


def _object(value: Any, keys: set, code: str) -> dict:
    _require(type(value) is dict and set(value) == keys, code)
    return value


def _sha(value: Any) -> str:
    _require(isinstance(value, str) and _SHA.fullmatch(value) is not None, "SHA256_INVALID")
    return value


def _text(value: Any, maximum=256) -> str:
    _require(isinstance(value, str) and bool(value.strip()) and len(value) <= maximum and
             not any(ord(char) < 32 for char in value), "TEXT_INVALID")
    return value


def _integer(value: Any, minimum: int, maximum: int, code: str) -> int:
    _require(type(value) is int and minimum <= value <= maximum, code)
    return value


def _url(value: Any) -> str:
    _text(value, 2048)
    try:
        parts = urlsplit(value)
        _require(parts.scheme in {"http", "https"} and bool(parts.hostname) and
                 parts.username is None and parts.password is None and not parts.query and not parts.fragment and
                 not any(char.isspace() for char in value),
                 "ENDPOINT_INVALID_OR_CONTAINS_CREDENTIALS")
        parts.port
    except ValueError as exc:
        if isinstance(exc, PairedExecutionPolicyError):
            raise
        raise PairedExecutionPolicyError("ENDPOINT_INVALID_OR_CONTAINS_CREDENTIALS") from exc
    return value


def endpoint_pool_fingerprint(endpoints: list[str]) -> str:
    _require(type(endpoints) is list and 1 <= len(endpoints) <= 256, "ENDPOINT_POOL_INVALID")
    for endpoint in endpoints:
        _url(endpoint)
    _require(len(endpoints) == len(set(endpoints)), "ENDPOINT_POOL_DUPLICATE")
    return canonical_sha256(endpoints)


def _resources_policy() -> dict:
    return {"platform": "WINDOWS", "priority_class": 16384, "affinity_mask": 2,
            "logical_cpu_count": 1, "numeric_threads": {name: "1" for name in NUMERIC_THREAD_KEYS}}


def _validate_projection(value: Any) -> dict:
    raw = _copy(value, MAX_POLICY_BYTES)
    parallel12 = isinstance(raw, dict) and raw.get("schema_version") == PARALLEL12_PROJECTION_SCHEMA
    p = _object(raw, _PROJECTION | {"input_post_count"} if parallel12 else _PROJECTION,
                "PROJECTION_SCHEMA_INVALID")
    _require(p["schema_version"] in (PROJECTION_SCHEMA, PARALLEL12_PROJECTION_SCHEMA)
             and p["profile"] == "low-load-validation", "LOW_LOAD_PROFILE_REQUIRED")
    settings = _object(p["settings"], _SETTINGS, "SETTINGS_SCHEMA_INVALID")
    for field in ("vlm", "ocr", "context_diagnostics"):
        _require(type(settings[field]) is bool, "SETTING_BOOLEAN_REQUIRED")
    _require(settings["ledger_mode"] == "REQUIRED", "LEDGER_REQUIRED")
    if parallel12:
        count = _integer(p["input_post_count"], 1, 2**31 - 1, "INPUT_POST_COUNT_INVALID")
        for value in (settings["requested_parallel"], p["requested_parallel"]):
            _integer(value, 12, 12, "PARALLEL_TWELVE_REQUIRED")
        _integer(p["effective_parallel"], min(count, 12), min(count, 12), "BOUNDED_PARALLEL_MISMATCH")
    else:
        for value in (settings["requested_parallel"], p["requested_parallel"], p["effective_parallel"]):
            _integer(value, 1, 1, "PARALLEL_ONE_REQUIRED")
    _require(p["dashboard_enabled"] is True, "DASHBOARD_REQUIRED")
    _require(p["compression_status"] == "OFF_NOT_REQUESTED", "COMPRESSION_OFF_REQUIRED")
    _require(p["image_review_ready"] is True, "IMAGE_REVIEW_READY_REQUIRED")
    source = _object(p["source"], {"entry_sha256", "runtime_source_sha256", "source_scope"}, "SOURCE_SCHEMA_INVALID")
    _sha(source["entry_sha256"])
    _sha(source["runtime_source_sha256"])
    _require(source["source_scope"] == "SELECTED_RUNTIME_FILES", "SOURCE_SCOPE_INVALID")
    runtime = _object(p["runtime"], set(RUNTIME_FIELDS), "RUNTIME_FIELDS_INVALID")
    _text(runtime["llm_model"])
    _url(runtime["llm_endpoint"])
    for field in ("generation_config_sha256", "prompt_sha256", "publication_config_sha256",
                  "publication_decision_environment_sha256", "mcp_endpoint_pool_sha256"):
        _sha(runtime[field])
    for field in ("mcp_health_workers", "mcp_health_probe_batch_size", "mcp_health_required_ok_count"):
        _integer(runtime[field], 1, 1, "HEALTH_SINGLE_PROBE_REQUIRED")
    for field in ("mcp_health_include_search", "mcp_reuse_shards_only"):
        _require(runtime[field] is True, "SEARCH_REUSE_REQUIRED")
    for field in ("mcp_health_light_mode", "mcp_auto_up_shards", "mcp_auto_recreate_shards",
                  "mcp_auto_scale_up_missing_shards", "batch_context_enabled", "central_slang_db_write_allowed"):
        _require(runtime[field] is False, "MUTABLE_OR_AUTOMATIC_ACTIVITY_FORBIDDEN")
    _require(runtime["mutable_context_mode"] == "FROZEN_OFF", "FROZEN_CONTEXT_REQUIRED")
    _require(runtime["slang_mode"] in ("OFF", "READ_ONLY"), "SLANG_MODE_INVALID")
    if runtime["slang_mode"] == "OFF":
        _require(runtime["slang_snapshot_sha256"] is None, "SLANG_OFF_SNAPSHOT_MUST_BE_NULL")
    else:
        _sha(runtime["slang_snapshot_sha256"])
    for field in ("candidate_retrieval_mode", "community_knowledge_mode", "candidate_reranker_mode"):
        _require(runtime[field] == "OFF", "RESEARCH_OBSERVERS_OFF_REQUIRED")
    return p


def execution_config_projection(execution_config: Any, *, runtime_fields: Mapping,
                                projection_schema: str = PROJECTION_SCHEMA,
                                input_post_count: int | None = None) -> dict:
    try:
        c = execution_config
        _require(type(c) is dict and c.get("schema_version") == "expert_execution_config_v1",
                 "EXECUTION_CONFIG_SCHEMA_INVALID")
        _require(isinstance(runtime_fields, Mapping), "RUNTIME_FIELDS_INVALID")
        settings = {key: c["settings"][key]["value"] for key in _SETTINGS}
        _require(projection_schema in (PROJECTION_SCHEMA, PARALLEL12_PROJECTION_SCHEMA), "PROJECTION_VERSION_UNSUPPORTED")
        _require(projection_schema == PARALLEL12_PROJECTION_SCHEMA or input_post_count is None,
                 "LEGACY_INPUT_COUNT_FORBIDDEN")
        result = {"schema_version": projection_schema, "profile": c["profile"], "settings": settings,
                  "requested_parallel": c["requested_parallel"], "effective_parallel": c["effective_parallel"],
                  "dashboard_enabled": c["dashboard"]["enabled"], "compression_status": c["compression"]["status"],
                  "image_review_ready": c["image_review"]["ready"],
                  "source": {key: c["source"][key] for key in ("entry_sha256", "runtime_source_sha256", "source_scope")},
                  "runtime": {key: runtime_fields[key] for key in RUNTIME_FIELDS}}
    except (KeyError, TypeError) as exc:
        raise PairedExecutionPolicyError("EXECUTION_CONFIG_FIELD_MISSING_OR_INVALID") from exc
    if projection_schema == PARALLEL12_PROJECTION_SCHEMA:
        result["input_post_count"] = input_post_count
    return _validate_projection(result)


def build_low_load_policy(*, policy_id: str, config_projection: dict, health_max_age_seconds: int = 300) -> dict:
    projection = _validate_projection(config_projection)
    schema = PARALLEL12_POLICY_SCHEMA if projection["schema_version"] == PARALLEL12_PROJECTION_SCHEMA else POLICY_SCHEMA
    policy = {"schema_version": schema, "policy_id": policy_id,
              "config_projection": projection, "config_projection_sha256": canonical_sha256(projection),
              "resources": _resources_policy(), "health": {"max_age_seconds": health_max_age_seconds,
              "future_tolerance_seconds": 0}, "observation_scope": "START_END_OBSERVED"}
    policy["policy_sha256"] = canonical_sha256(policy)
    return validate_low_load_policy(policy)


def validate_low_load_policy(policy: Any) -> dict:
    p = _object(_copy(policy, MAX_POLICY_BYTES), _POLICY, "POLICY_SCHEMA_INVALID")
    _require(p["schema_version"] in (POLICY_SCHEMA, PARALLEL12_POLICY_SCHEMA), "POLICY_VERSION_UNSUPPORTED")
    _text(p["policy_id"], 128)
    _sha(p["policy_sha256"])
    _require(p["policy_sha256"] == canonical_sha256({k: v for k, v in p.items() if k != "policy_sha256"}),
             "POLICY_SELF_SHA_MISMATCH")
    projection = _validate_projection(p["config_projection"])
    expected_projection = PARALLEL12_PROJECTION_SCHEMA if p["schema_version"] == PARALLEL12_POLICY_SCHEMA else PROJECTION_SCHEMA
    _require(projection["schema_version"] == expected_projection, "POLICY_PROJECTION_VERSION_MISMATCH")
    _require(_sha(p["config_projection_sha256"]) == canonical_sha256(projection), "CONFIG_PROJECTION_SHA_MISMATCH")
    # Canonical equality also distinguishes booleans/floats from required integers.
    _require(_bytes(p["resources"]) == _bytes(_resources_policy()), "RESOURCE_POLICY_INVALID")
    health = _object(p["health"], {"max_age_seconds", "future_tolerance_seconds"}, "HEALTH_POLICY_INVALID")
    _integer(health["max_age_seconds"], 1, 3600, "HEALTH_FRESHNESS_INVALID")
    _integer(health["future_tolerance_seconds"], 0, 0, "HEALTH_FUTURE_FORBIDDEN")
    _require(p["observation_scope"] == "START_END_OBSERVED", "OBSERVATION_SCOPE_INVALID")
    return p


def policy_summary(policy: Any) -> dict:
    p = validate_low_load_policy(policy)
    return {"schema_version": "paired_execution_policy_summary_v1", "status": "VALIDATED_POLICY",
            "policy_id": p["policy_id"], "policy_sha256": p["policy_sha256"],
            "config_projection_sha256": p["config_projection_sha256"], "resources": p["resources"],
            "health": p["health"], "observation_scope": p["observation_scope"],
            "publication_authority": False, "model_immutability_proven": False,
            "formal_kpi_status": "NOT_ESTIMABLE_POLICY_ONLY", "price_quality_evaluated": False}


def _binding(value: Any) -> dict:
    b = _object(_copy(value, 4096), _BINDING, "OBSERVATION_BINDING_SCHEMA_INVALID")
    for name in ("pair_id", "run_id", "attempt_id"):
        _text(b[name], 128)
    _require(b["arm"] in ("BEFORE", "AFTER"), "ARM_INVALID")
    _sha(b["input_sha256"])
    _sha(b["publication_scope_id"])
    return b


def _utc(value: Any) -> datetime:
    _text(value, 64)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        _require(parsed.tzinfo is not None and parsed.utcoffset().total_seconds() == 0,
                 "UTC_TIMESTAMP_REQUIRED")
        return parsed
    except (ValueError, OverflowError) as exc:
        if isinstance(exc, PairedExecutionPolicyError):
            raise
        raise PairedExecutionPolicyError("UTC_TIMESTAMP_REQUIRED") from exc


def seal_execution_observation(payload: Any) -> dict:
    result = _copy(payload, MAX_OBSERVATION_BYTES)
    _require(type(result) is dict, "OBSERVATION_SCHEMA_INVALID")
    result.pop("observation_sha256", None)
    _object(result, _OBSERVATION - {"observation_sha256"}, "OBSERVATION_SCHEMA_INVALID")
    result["observation_sha256"] = canonical_sha256(result)
    _require(len(_bytes(result)) <= MAX_OBSERVATION_BYTES, "JSON_BYTE_LIMIT")
    return result


def validate_execution_observation(policy: Any, observation: Any, *, binding: dict, phase: str) -> dict:
    p = validate_low_load_policy(policy)
    expected = _binding(binding)
    _require(phase in ("START", "END"), "PHASE_INVALID")
    o = _object(_copy(observation, MAX_OBSERVATION_BYTES), _OBSERVATION, "OBSERVATION_SCHEMA_INVALID")
    _require(o["schema_version"] == OBSERVATION_SCHEMA, "OBSERVATION_VERSION_UNSUPPORTED")
    _require(o["phase"] == phase, "OBSERVATION_PHASE_MISMATCH")
    _require(_binding(o["binding"]) == expected, "OBSERVATION_BINDING_MISMATCH")
    _require(_sha(o["policy_sha256"]) == p["policy_sha256"], "OBSERVATION_POLICY_MISMATCH")
    _require(_sha(o["observation_sha256"]) == canonical_sha256({k: v for k, v in o.items() if k != "observation_sha256"}),
             "OBSERVATION_SELF_SHA_MISMATCH")
    projection = _validate_projection(o["config_projection"])
    _require(_sha(o["config_projection_sha256"]) == canonical_sha256(projection) == p["config_projection_sha256"] and
             projection == p["config_projection"], "OBSERVATION_CONFIG_MISMATCH")
    instant = _utc(o["observed_at"])
    _integer(o["monotonic_ns"], 1, 2**63 - 1, "MONOTONIC_INVALID")
    resources = _object(o["resources"], set(_resources_policy()) | {"pid", "status"}, "RESOURCE_OBSERVATION_INVALID")
    _integer(resources["pid"], 1, 2**32 - 1, "RESOURCE_PID_INVALID")
    _require(resources["status"] in ("OBSERVED", "LOW_LOAD_VERIFIED"), "RESOURCE_API_UNAVAILABLE")
    _require(_bytes({k: v for k, v in resources.items() if k not in {"pid", "status"}}) == _bytes(p["resources"]),
             "RESOURCE_OBSERVATION_MISMATCH")
    h = _object(o["health"], {"observed_at", "endpoint_pool_sha256", "ok_count", "failure_count", "checked_count"},
                "HEALTH_OBSERVATION_INVALID")
    _require(_sha(h["endpoint_pool_sha256"]) == projection["runtime"]["mcp_endpoint_pool_sha256"], "HEALTH_POOL_MISMATCH")
    _integer(h["ok_count"], 1, 256, "HEALTH_SUCCESS_REQUIRED")
    _integer(h["failure_count"], 0, 0, "HEALTH_FAILURE_FORBIDDEN")
    _integer(h["checked_count"], 1, 256, "HEALTH_CHECKED_INVALID")
    _require(h["checked_count"] == h["ok_count"], "HEALTH_COUNTS_MISMATCH")
    age = (instant - _utc(h["observed_at"])).total_seconds()
    _require(0 <= age <= p["health"]["max_age_seconds"], "HEALTH_STALE_OR_FUTURE")
    if phase == "START":
        _require(o["start_observation_sha256"] is None, "START_PREDECESSOR_MUST_BE_NULL")
    else:
        _sha(o["start_observation_sha256"])
    return o


def validate_execution_observation_pair(policy: Any, start: Any, end: Any, *, binding: dict) -> dict:
    a = validate_execution_observation(policy, start, binding=binding, phase="START")
    b = validate_execution_observation(policy, end, binding=binding, phase="END")
    _require(b["start_observation_sha256"] == a["observation_sha256"], "START_END_SHA_MISMATCH")
    _require(b["resources"]["pid"] == a["resources"]["pid"], "START_END_PID_MISMATCH")
    _require(b["monotonic_ns"] > a["monotonic_ns"] and _utc(b["observed_at"]) >= _utc(a["observed_at"]),
             "START_END_CLOCK_NOT_INCREASING")
    return {"schema_version": "paired_execution_observation_pair_validation_v1", "status": "PASS",
            "policy_sha256": a["policy_sha256"], "config_projection_sha256": a["config_projection_sha256"],
            "binding": a["binding"], "start_observation_sha256": a["observation_sha256"],
            "end_observation_sha256": b["observation_sha256"], "observation_scope": "START_END_OBSERVED",
            "observed_elapsed_ns": b["monotonic_ns"] - a["monotonic_ns"],
            "comparison_eligibility": "NOT_DECIDED_POLICY_OBSERVATIONS_ONLY", "publication_authority": False,
            "model_immutability_proven": False, "price_quality_evaluated": False}


def capture_execution_observation(policy: Any, execution_config: Any, *, runtime_fields: Mapping,
                                  binding: dict, phase: str, health: dict, start_observation=None) -> dict:
    p = validate_low_load_policy(policy)
    expected = _binding(binding)
    _require(phase in ("START", "END"), "PHASE_INVALID")
    _require(os.name == "nt", "WINDOWS_RESOURCE_OBSERVATION_REQUIRED")
    projection = execution_config_projection(execution_config, runtime_fields=runtime_fields,
        projection_schema=p["config_projection"]["schema_version"],
        input_post_count=p["config_projection"].get("input_post_count"))
    from ..runtime.execution_config import observe_process_resources
    try:
        resources = observe_process_resources(os.environ)
    except Exception as exc:
        raise PairedExecutionPolicyError("RESOURCE_OBSERVATION_FAILED") from exc
    _require(type(resources) is dict, "RESOURCE_OBSERVATION_INVALID")
    resources = {**resources, "platform": "WINDOWS"}
    _require(resources.get("pid") == os.getpid(), "RESOURCE_PID_MISMATCH")
    prior = None
    if phase == "END":
        prior = validate_execution_observation(p, start_observation, binding=expected, phase="START")
    else:
        _require(start_observation is None, "START_PREDECESSOR_MUST_BE_NULL")
    receipt = seal_execution_observation({"schema_version": OBSERVATION_SCHEMA, "phase": phase,
        "binding": expected, "policy_sha256": p["policy_sha256"], "config_projection": projection,
        "config_projection_sha256": canonical_sha256(projection),
        "observed_at": datetime.now(timezone.utc).isoformat(), "monotonic_ns": time.perf_counter_ns(),
        "resources": resources, "health": deepcopy(health),
        "start_observation_sha256": prior["observation_sha256"] if prior else None})
    receipt = validate_execution_observation(p, receipt, binding=expected, phase=phase)
    if prior is not None:
        validate_execution_observation_pair(p, prior, receipt, binding=expected)
    return receipt


def _local_path(path: str | Path) -> Path:
    text = str(path)
    _require(not text.startswith(("\\\\", "//")) and "://" not in text, "LOCAL_POLICY_PATH_REQUIRED")
    try:
        resolved = Path(path).resolve()
        _require(not str(resolved).startswith(("\\\\", "//")), "LOCAL_POLICY_PATH_REQUIRED")
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.GetDriveTypeW.argtypes = [wintypes.LPCWSTR]
            kernel.GetDriveTypeW.restype = wintypes.UINT
            _require(kernel.GetDriveTypeW(resolved.anchor) in (2, 3, 5, 6), "LOCAL_POLICY_PATH_REQUIRED")
        return resolved
    except (OSError, ValueError, RuntimeError) as exc:
        if isinstance(exc, PairedExecutionPolicyError):
            raise
        raise PairedExecutionPolicyError("POLICY_PATH_INVALID") from exc


def _strict_json(raw: bytes) -> Any:
    def pairs(items):
        result = {}
        for key, value in items:
            _require(key not in result, "DUPLICATE_JSON_KEY")
            result[key] = value
        return result
    def constant(_):
        raise PairedExecutionPolicyError("JSON_VALUE_INVALID")
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise PairedExecutionPolicyError("POLICY_JSON_INVALID") from exc


def read_execution_policy(path: str | Path, *, expected_sha256: str, expected_policy_sha256=None) -> dict:
    _sha(expected_sha256)
    if expected_policy_sha256 is not None:
        _sha(expected_policy_sha256)
    target = _local_path(path)
    try:
        with target.open("rb") as stream:
            raw = stream.read(MAX_POLICY_BYTES + 1)
    except OSError as exc:
        raise PairedExecutionPolicyError("POLICY_FILE_UNAVAILABLE") from exc
    _require(len(raw) <= MAX_POLICY_BYTES, "POLICY_FILE_BYTE_LIMIT")
    digest = hashlib.sha256(raw).hexdigest()
    _require(digest == expected_sha256, "POLICY_FILE_SHA_MISMATCH")
    policy = validate_low_load_policy(_strict_json(raw))
    _require(expected_policy_sha256 is None or policy["policy_sha256"] == expected_policy_sha256,
             "POLICY_EXPECTED_SELF_SHA_MISMATCH")
    return {"policy": policy, "policy_sha256": policy["policy_sha256"], "file_sha256": digest,
            "bytes": len(raw), "path": str(target)}


def write_execution_policy(policy: Any, path: str | Path) -> dict:
    p = validate_low_load_policy(policy)
    raw = _bytes(p) + b"\n"
    _require(len(raw) <= MAX_POLICY_BYTES, "POLICY_FILE_BYTE_LIMIT")
    target = _local_path(path)
    try:
        with target.open("xb") as stream:
            stream.write(raw)
    except FileExistsError as exc:
        raise PairedExecutionPolicyError("POLICY_OUTPUT_EXISTS") from exc
    except OSError as exc:
        raise PairedExecutionPolicyError("POLICY_WRITE_FAILED") from exc
    return read_execution_policy(target, expected_sha256=hashlib.sha256(raw).hexdigest(),
                                 expected_policy_sha256=p["policy_sha256"])
