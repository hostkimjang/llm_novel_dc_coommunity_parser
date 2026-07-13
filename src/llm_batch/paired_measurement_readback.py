"""Independent, source-bound BEFORE/AFTER physical-call readback.

The reader never launches providers and never writes publication artifacts.  It
accepts only fresh, terminal arms bound to one self-hashed paired RunSpec.  The
output rows, immutable call ledgers, and authoritative publication WAL are read
back independently before any cost number is emitted.

An AFTER cheap row is an authoritative-WAL reference copy.  Its zero calls are
therefore a counterfactual cost observation, not evidence of production
inference savings.  Such rows are reported as ``REFERENCE_COPY_COST_ONLY`` and
are excluded from the production-comparable KPI.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import random
from typing import Any, Mapping

from .decision_call_readback import (
    read_decision_call_ledger,
    verify_readback_report_sha256,
)
from .early_route_measurement import (
    ACCURACY_NOT_ESTIMABLE,
    ARM_AFTER,
    LANE_CHEAP_NIL,
    LANE_FULL,
    EarlyRouteComparisonReceipt,
    EarlyRouteDecision,
)
from .selective_compute_shadow import decision_cost_trace_from_dict
from .publication_commit import (
    PUBLICATION_COMMIT_EVENT_SCHEMA,
    PublicationDecisionCommit,
    compute_publication_decision_commit,
    validate_publication_result_commit,
    validate_publication_result_decision,
)


SCHEMA_VERSION = "paired-pipeline-measurement-readback-v2"
RUN_SPEC_SCHEMA_VERSION = "paired-pipeline-measurement-runspec-v1"
RECOVERY_WITNESS_SCHEMA_VERSION = "paired_measurement_recovery_witness_v1"
EXECUTION_ENVELOPE_SCHEMA_VERSION = "paired_measurement_execution_envelope_v1"
EXECUTION_ENVELOPE_POLICY_SCHEMA_VERSION = "paired_measurement_execution_envelope_policy_v1"
REFERENCE_COPY_COST_ONLY = "REFERENCE_COPY_COST_ONLY"
_PRODUCTION_COMPARABLE = "EXACT_PRODUCTION_INFERENCE_COMPARABLE_ROWS_ONLY"
_HEX = frozenset("0123456789abcdef")
_METRIC_NAMES = (
    "expert_calls",
    "text_calls",
    "vlm_calls",
    "retry_count",
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "physical_call_wall_ms_sum",
)
_RUN_SPEC_KEYS = {
    "schema_version",
    "pair_id",
    "publication_scope_id",
    "publication_input_snapshot_sha256",
    "input_post_count",
    "ordered_post_ids",
    "frozen_conditions",
    "recovery_policy",
    "approval_boundary",
    "run_spec_sha256",
}
_FROZEN_CONDITION_KEYS = {
    "runtime_manifest_fields",
    "shared_measurement_fields",
    "arm_measurement_fields",
}
_REQUIRED_RUNTIME_FIELDS = {
    "llm_model",
    "llm_endpoint",
    "requested_parallel",
    "effective_parallel",
    "parallel_policy",
    "vlm_enabled",
    "ocr_enabled",
    "vlm_ocr_semantic_review_ready",
    "dashboard_enabled",
    "mcp_health_include_search",
    "mcp_health_light_mode",
    "mcp_health_ok_count",
    "mcp_health_failure_count",
    "mcp_healthy_endpoint_filter_reason",
    "publication_config_sha256",
    "publication_decision_environment_sha256",
    "publication_slang_db_input_sha256",
    "publication_release_fingerprint",
}
_REQUIRED_SHARED_MEASUREMENT = {
    "mode": "REQUIRED",
    "execution_mode": "FRESH_EXECUTION_REQUIRED",
    "binding_status": "BOUND",
    "fresh_execution_required": True,
    "actual_kpi_eligible": True,
    "early_route_mode": "SOURCE_ONLY_V1",
    "mutable_context_mode": "FROZEN_OFF",
    "mutable_context_frozen": True,
    "central_slang_db_write_allowed": False,
}
_RESERVED_MEASUREMENT_FIELDS = {"run_spec_sha256", "pair_id", "arm"}
_RECOVERY_MARKERS = {
    "fresh_measurement_recovery",
    "recovered_from",
    "recovered_output_path",
    "recovery_source",
    "recovery_summary",
    "recovery_witness",
}
_REQUIRED_RECOVERY_MARKERS = frozenset(_RECOVERY_MARKERS)
_RECOVERY_WITNESS_KEYS = {
    "schema_version",
    "arm",
    "run_spec_sha256",
    "pair_id",
    "publication_scope_id",
    "attempt_run_id",
    "recovery_source",
    "status",
    "measurement_eligible",
    "actual_kpi_status",
    "recovery_action",
    "reason_codes",
    "input_post_count",
    "ordered_post_ids_sha256",
    "source_manifest",
    "source_result",
    "source_checkpoint",
    "source_pending_snapshot",
    "recovery_summary",
    "recovered_output",
    "output_attempt_claim",
    "publication_wal",
    "decision_call_ledger",
    "fresh_measurement_recovery",
    "witness_sha256",
}
_EXECUTION_ENVELOPE_POLICY_KEYS = {
    "schema_version",
    "bootstrap_seed",
    "bootstrap_replicates",
    "alpha",
    "min_comparable_rows",
}


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256(value: Any) -> str:
    return _sha256_bytes(_canonical_bytes(value))


def _require_sha256(value: Any, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in _HEX for character in value)
    ):
        raise ValueError(f"{field} must be a lowercase sha256")
    return value


def _require_nonnegative_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field} must be a nonnegative integer")
    return value


def _require_positive_int(value: Any, field: str) -> int:
    parsed = _require_nonnegative_int(value, field)
    if parsed == 0:
        raise ValueError(f"{field} must be positive")
    return parsed


def _require_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _require_mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be an object")
    return value


def _stable_bytes(path: Path) -> bytes:
    if not path.is_file():
        raise ValueError(f"artifact missing: {path}")
    before = path.stat()
    first = path.read_bytes()
    middle = path.stat()
    second = path.read_bytes()
    after = path.stat()
    snapshot = lambda value: (
        value.st_size,
        value.st_mtime_ns,
        getattr(value, "st_ino", 0),
    )
    if (
        snapshot(before) != snapshot(middle)
        or snapshot(middle) != snapshot(after)
        or first != second
    ):
        raise ValueError(f"artifact changed during independent readback: {path}")
    return first


def _load_json_value_snapshot(path: Path) -> tuple[Any, dict[str, Any]]:
    raw = _stable_bytes(path)
    try:
        value = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid JSON artifact: {path}: {error}") from error
    return value, {
        "path": str(path.resolve()),
        "bytes": len(raw),
        "sha256": _sha256_bytes(raw),
    }


def _load_json_snapshot(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    value, reference = _load_json_value_snapshot(path)
    if not isinstance(value, dict):
        raise ValueError(f"JSON artifact must be an object: {path}")
    return value, reference


def _artifact_path(value: Any, owner_path: Path, field: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} path is missing")
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = owner_path.parent / candidate
    return candidate.resolve()


def _post_id(value: Any, field: str) -> int | str:
    if isinstance(value, bool):
        raise ValueError(f"{field} is invalid")
    if isinstance(value, int):
        if value < 0:
            raise ValueError(f"{field} is invalid")
        return value
    if isinstance(value, str) and value.strip():
        return value.strip()
    raise ValueError(f"{field} is invalid")


def _assert_snapshot_unchanged(reference: Mapping[str, Any], label: str) -> None:
    path = Path(_require_text(reference.get("path"), f"{label} path"))
    raw = _stable_bytes(path)
    if len(raw) != reference.get("bytes") or _sha256_bytes(raw) != reference.get("sha256"):
        raise ValueError(f"{label} changed during paired readback")


def _validate_artifact_reference(value: Any, label: str) -> dict[str, Any]:
    reference = dict(_require_mapping(value, f"{label} reference"))
    if set(reference) != {"path", "bytes", "sha256"}:
        raise ValueError(f"{label} artifact reference shape mismatch")
    path = Path(_require_text(reference.get("path"), f"{label} path")).resolve()
    size = _require_nonnegative_int(reference.get("bytes"), f"{label} bytes")
    digest = _require_sha256(reference.get("sha256"), f"{label} sha256")
    raw = _stable_bytes(path)
    if len(raw) != size or _sha256_bytes(raw) != digest:
        raise ValueError(f"{label} artifact bytes mismatch")
    return {"path": str(path), "bytes": size, "sha256": digest}


def _artifact_reference_for_path(path: str | Path) -> dict[str, Any]:
    resolved = Path(path).resolve()
    raw = _stable_bytes(resolved)
    return {
        "path": str(resolved),
        "bytes": len(raw),
        "sha256": _sha256_bytes(raw),
    }


@dataclass(frozen=True)
class _RunSpecReadback:
    value: dict[str, Any]
    reference: dict[str, Any]
    path: Path
    runtime_fields: dict[str, Any]
    shared_measurement_fields: dict[str, Any]
    arm_measurement_fields: dict[str, dict[str, Any]]
    ordered_post_ids: tuple[int | str, ...]


@dataclass(frozen=True)
class _RecoveryWitnessReadback:
    value: dict[str, Any]
    path: Path
    reference: dict[str, Any]


def _read_run_spec(path: str | Path) -> _RunSpecReadback:
    run_spec_path = Path(path).resolve()
    spec, reference = _load_json_snapshot(run_spec_path)
    if set(spec) != _RUN_SPEC_KEYS:
        raise ValueError("paired RunSpec shape mismatch")
    if spec.get("schema_version") != RUN_SPEC_SCHEMA_VERSION:
        raise ValueError("unsupported paired RunSpec schema")
    supplied_hash = _require_sha256(spec.get("run_spec_sha256"), "RunSpec self hash")
    expected_hash = _sha256(
        {key: value for key, value in spec.items() if key != "run_spec_sha256"}
    )
    if supplied_hash != expected_hash:
        raise ValueError("paired RunSpec self hash mismatch")

    pair_id = _require_text(spec.get("pair_id"), "RunSpec pair_id")
    _require_sha256(spec.get("publication_scope_id"), "RunSpec publication_scope_id")
    _require_sha256(
        spec.get("publication_input_snapshot_sha256"),
        "RunSpec publication_input_snapshot_sha256",
    )
    input_count = _require_positive_int(spec.get("input_post_count"), "RunSpec input_post_count")
    raw_post_ids = spec.get("ordered_post_ids")
    if not isinstance(raw_post_ids, list) or len(raw_post_ids) != input_count:
        raise ValueError("RunSpec ordered_post_ids coverage mismatch")
    ordered_post_ids = tuple(
        _post_id(value, f"RunSpec ordered_post_ids[{index}]")
        for index, value in enumerate(raw_post_ids)
    )
    if len({_canonical_bytes(value) for value in ordered_post_ids}) != input_count:
        raise ValueError("RunSpec ordered_post_ids contains duplicates")

    conditions = _require_mapping(spec.get("frozen_conditions"), "RunSpec frozen_conditions")
    if set(conditions) != _FROZEN_CONDITION_KEYS:
        raise ValueError("RunSpec frozen_conditions shape mismatch")
    runtime_fields = dict(
        _require_mapping(
            conditions.get("runtime_manifest_fields"),
            "RunSpec runtime_manifest_fields",
        )
    )
    missing_runtime = _REQUIRED_RUNTIME_FIELDS - set(runtime_fields)
    if missing_runtime:
        raise ValueError(f"RunSpec runtime fields missing: {sorted(missing_runtime)}")
    _require_text(runtime_fields.get("llm_model"), "RunSpec llm_model")
    _require_text(runtime_fields.get("llm_endpoint"), "RunSpec llm_endpoint")
    requested_parallel = _require_positive_int(
        runtime_fields.get("requested_parallel"), "RunSpec requested_parallel"
    )
    if requested_parallel != 16:
        raise ValueError("paired RunSpec requires requested_parallel=16")
    effective_parallel = _require_positive_int(
        runtime_fields.get("effective_parallel"), "RunSpec effective_parallel"
    )
    if effective_parallel != min(requested_parallel, input_count):
        raise ValueError("RunSpec effective_parallel does not match bounded input coverage")
    _require_text(runtime_fields.get("parallel_policy"), "RunSpec parallel_policy")
    for field in (
        "vlm_enabled",
        "ocr_enabled",
        "vlm_ocr_semantic_review_ready",
        "dashboard_enabled",
        "mcp_health_include_search",
        "mcp_health_light_mode",
    ):
        if not isinstance(runtime_fields.get(field), bool):
            raise ValueError(f"RunSpec {field} must be boolean")
    if runtime_fields["dashboard_enabled"] is not True:
        raise ValueError("paired RunSpec requires dashboard_enabled=true")
    if runtime_fields["vlm_ocr_semantic_review_ready"] is not True:
        raise ValueError("paired RunSpec requires VLM/OCR semantic readiness")
    if (
        runtime_fields["mcp_health_include_search"] is not True
        or runtime_fields["mcp_health_light_mode"] is not False
    ):
        raise ValueError("paired RunSpec requires non-light search health verification")
    health_ok = _require_nonnegative_int(
        runtime_fields.get("mcp_health_ok_count"), "RunSpec mcp_health_ok_count"
    )
    health_failures = _require_nonnegative_int(
        runtime_fields.get("mcp_health_failure_count"),
        "RunSpec mcp_health_failure_count",
    )
    if health_ok < requested_parallel or health_failures != 0:
        raise ValueError("paired RunSpec requires at least 16 healthy search shards and zero failures")
    if runtime_fields.get("mcp_healthy_endpoint_filter_reason") != "reuse_shards_only":
        raise ValueError("paired RunSpec requires --reuse-shards-only provenance")
    for field in (
        "publication_config_sha256",
        "publication_decision_environment_sha256",
        "publication_slang_db_input_sha256",
        "publication_release_fingerprint",
    ):
        _require_sha256(runtime_fields.get(field), f"RunSpec {field}")

    shared = dict(
        _require_mapping(
            conditions.get("shared_measurement_fields"),
            "RunSpec shared_measurement_fields",
        )
    )
    if _RESERVED_MEASUREMENT_FIELDS & set(shared):
        raise ValueError("RunSpec shared measurement fields contain arm bindings")
    for field, expected in _REQUIRED_SHARED_MEASUREMENT.items():
        if shared.get(field) != expected:
            raise ValueError(f"RunSpec shared measurement {field} mismatch")
    slang_mode = shared.get("slang_access_mode")
    if slang_mode not in {"OFF", "READ_ONLY"}:
        raise ValueError("RunSpec slang_access_mode must be OFF or READ_ONLY")
    mutable_binding = _require_mapping(
        shared.get("mutable_context_binding"),
        "RunSpec mutable_context_binding",
    )
    expected_mutable_binding = {
        "schema_version": "paired_measurement_mutable_context_binding_v1",
        "mutable_context_mode": "FROZEN_OFF",
        "batch_context_enabled": False,
        "slang_access_mode": slang_mode,
        "central_slang_db_write_allowed": False,
    }
    if dict(mutable_binding) != expected_mutable_binding:
        raise ValueError("RunSpec mutable_context_binding mismatch")
    if shared.get("mutable_context_binding_sha256") != _sha256(expected_mutable_binding):
        raise ValueError("RunSpec mutable_context_binding self hash mismatch")

    raw_arms = _require_mapping(
        conditions.get("arm_measurement_fields"),
        "RunSpec arm_measurement_fields",
    )
    if set(raw_arms) != {"BEFORE", "AFTER"}:
        raise ValueError("RunSpec arm measurement coverage mismatch")
    arm_fields: dict[str, dict[str, Any]] = {}
    expected_arm_values = {
        "BEFORE": {
            "early_route_enabled": False,
            "early_route_enable_status": "DISABLED_CONDITIONS_NOT_MET",
        },
        "AFTER": {
            "early_route_enabled": True,
            "early_route_enable_status": "ENABLED_AFTER_REQUIRED_FRESH_SOURCE_ONLY_V1",
        },
    }
    for arm in ("BEFORE", "AFTER"):
        arm_value = dict(_require_mapping(raw_arms.get(arm), f"RunSpec {arm} fields"))
        if _RESERVED_MEASUREMENT_FIELDS & set(arm_value):
            raise ValueError(f"RunSpec {arm} fields contain reserved bindings")
        if arm_value != expected_arm_values[arm]:
            raise ValueError(f"RunSpec {arm} early-route contract mismatch")
        arm_fields[arm] = arm_value

    if (
        spec.get("recovery_policy")
        != "ALLOW_RECOVERED_ARMS_EXACT_BOUND_WITNESS_ONLY"
    ):
        raise ValueError("RunSpec recovery policy must require an exact bound witness")
    if spec.get("approval_boundary") != {
        "semantic_quality": "REVIEW-LOCKED",
        "production_enable_allowed": False,
        "full_scan_approval": False,
    }:
        raise ValueError("RunSpec approval boundary mismatch")
    reference["self_hash"] = supplied_hash
    reference["pair_id"] = pair_id
    return _RunSpecReadback(
        value=spec,
        reference=reference,
        path=run_spec_path,
        runtime_fields=runtime_fields,
        shared_measurement_fields=shared,
        arm_measurement_fields=arm_fields,
        ordered_post_ids=ordered_post_ids,
    )


def _load_recovery_witness(
    manifest: Mapping[str, Any],
    manifest_path: Path,
    arm: str,
    run_spec: _RunSpecReadback,
) -> _RecoveryWitnessReadback | None:
    markers = {field for field in _RECOVERY_MARKERS if field in manifest}
    if not markers:
        return None
    if markers != _REQUIRED_RECOVERY_MARKERS:
        raise ValueError(
            f"{arm} recovered arm rejected: no independently bound recovery witness; "
            f"markers={sorted(markers)}"
        )

    witness_path = _artifact_path(
        manifest.get("recovery_witness"), manifest_path, f"{arm} recovery witness"
    )
    witness, reference = _load_json_snapshot(witness_path)
    if set(witness) != _RECOVERY_WITNESS_KEYS:
        raise ValueError(f"{arm} recovery witness shape mismatch")
    if witness.get("schema_version") != RECOVERY_WITNESS_SCHEMA_VERSION:
        raise ValueError(f"{arm} recovery witness schema mismatch")
    supplied_hash = _require_sha256(
        witness.get("witness_sha256"), f"{arm} recovery witness self hash"
    )
    if supplied_hash != _sha256(
        {key: value for key, value in witness.items() if key != "witness_sha256"}
    ):
        raise ValueError(f"{arm} recovery witness self hash mismatch")

    expected_bindings = {
        "arm": arm,
        "run_spec_sha256": run_spec.value["run_spec_sha256"],
        "pair_id": run_spec.value["pair_id"],
        "publication_scope_id": run_spec.value["publication_scope_id"],
        "attempt_run_id": manifest.get("run_id"),
        "recovery_source": "publication_commit_wal_current",
        "status": "GO",
        "measurement_eligible": True,
        "actual_kpi_status": "INDEPENDENTLY_VERIFIED_EXACT",
        "recovery_action": "NONE",
        "reason_codes": [],
        "input_post_count": run_spec.value["input_post_count"],
        "ordered_post_ids_sha256": _sha256(list(run_spec.ordered_post_ids)),
    }
    if any(witness.get(key) != value for key, value in expected_bindings.items()):
        raise ValueError(f"{arm} recovery witness binding mismatch")
    if manifest.get("recovery_source") != witness["recovery_source"]:
        raise ValueError(f"{arm} recovery source differs from witness")
    fresh_gate = manifest.get("fresh_measurement_recovery")
    if not isinstance(fresh_gate, Mapping) or dict(fresh_gate) != witness.get(
        "fresh_measurement_recovery"
    ):
        raise ValueError(f"{arm} fresh recovery gate differs from witness")
    if (
        fresh_gate.get("status") != "GO"
        or fresh_gate.get("measurement_eligible") is not True
        or fresh_gate.get("actual_kpi_status") != "INDEPENDENTLY_VERIFIED_EXACT"
        or fresh_gate.get("recovery_action") != "NONE"
        or fresh_gate.get("reason_codes") != []
        or fresh_gate.get("publication_wal_unchanged") is not True
    ):
        raise ValueError(f"{arm} recovery witness does not contain an exact GO gate")
    return _RecoveryWitnessReadback(
        value=witness,
        path=witness_path,
        reference=reference,
    )


def _reject_recovered_arm(manifest: Mapping[str, Any], arm: str) -> None:
    markers = sorted(field for field in _RECOVERY_MARKERS if field in manifest)
    if markers:
        raise ValueError(
            f"{arm} recovered arm rejected: no independently bound recovery witness; "
            f"markers={markers}"
        )


def _measurement_config(
    manifest: Mapping[str, Any],
    expected_arm: str,
    run_spec: _RunSpecReadback,
) -> dict[str, Any]:
    value = manifest.get("decision_call_measurement")
    if not isinstance(value, Mapping):
        raise ValueError(f"{expected_arm} decision_call_measurement is missing")
    config = dict(value)
    expected = {
        **run_spec.shared_measurement_fields,
        **run_spec.arm_measurement_fields[expected_arm],
        "run_spec_sha256": run_spec.value["run_spec_sha256"],
        "pair_id": run_spec.value["pair_id"],
        "arm": expected_arm,
    }
    for field, expected_value in expected.items():
        if config.get(field) != expected_value:
            raise ValueError(f"{expected_arm} measurement {field} differs from RunSpec")
    _require_sha256(config.get("run_spec_sha256"), f"{expected_arm} run_spec_sha256")
    return config


def _validate_runtime_terminal(
    manifest: Mapping[str, Any],
    arm: str,
    run_spec: _RunSpecReadback,
    recovery_witness: _RecoveryWitnessReadback | None,
) -> int:
    if recovery_witness is None:
        _reject_recovered_arm(manifest, arm)
    input_count = _require_nonnegative_int(manifest.get("input_post_count"), f"{arm} input_post_count")
    if input_count != run_spec.value["input_post_count"]:
        raise ValueError(f"{arm} input_post_count differs from RunSpec")
    for field, expected in (
        ("completed_count", input_count),
        ("flushed_count", input_count),
        ("pending_count", 0),
        ("failed_count", 0),
    ):
        if _require_nonnegative_int(manifest.get(field), f"{arm} {field}") != expected:
            raise ValueError(f"{arm} terminal count mismatch: {field}")
    if manifest.get("terminal_artifacts_finalized") is not True:
        raise ValueError(f"{arm} terminal artifacts are not finalized")
    runtime_gate = manifest.get("runtime_completion_gate")
    measurement_gate = manifest.get("measurement_gate")
    if not isinstance(runtime_gate, Mapping) or runtime_gate.get("status") != "GO":
        raise ValueError(f"{arm} runtime completion gate is not GO")
    if not isinstance(measurement_gate, Mapping) or measurement_gate.get("status") != "GO":
        raise ValueError(f"{arm} writer measurement gate is not GO")
    if manifest.get("large_run_complete") is not True:
        raise ValueError(f"{arm} large_run_complete is not true")
    if manifest.get("publication_execution_mode") != "FRESH_EXECUTION_NO_PUBLIC_WRITE":
        raise ValueError(f"{arm} is not a no-public-write fresh execution")
    if manifest.get("publication_scope_id") != run_spec.value["publication_scope_id"]:
        raise ValueError(f"{arm} publication scope differs from RunSpec")
    if (
        manifest.get("publication_input_snapshot_sha256")
        != run_spec.value["publication_input_snapshot_sha256"]
    ):
        raise ValueError(f"{arm} input snapshot differs from RunSpec")
    for field, expected in run_spec.runtime_fields.items():
        if manifest.get(field) != expected:
            raise ValueError(f"{arm} runtime field {field} differs from RunSpec")
    return input_count


@dataclass(frozen=True)
class _WalRow:
    receipt: PublicationDecisionCommit
    result: dict[str, Any]


def _read_publication_wal(
    path: Path,
    *,
    publication_scope_id: str,
) -> tuple[dict[tuple[int, int | str], _WalRow], dict[str, Any]]:
    raw = _stable_bytes(path)
    if raw and not raw.endswith(b"\n"):
        raise ValueError("authoritative publication WAL has an uncommitted tail")
    rows: dict[tuple[int, int | str], _WalRow] = {}
    for line_number, line in enumerate(raw.splitlines(), 1):
        if not line.strip():
            raise ValueError(f"blank publication WAL line: {line_number}")
        try:
            event = json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError(f"invalid publication WAL line {line_number}: {error}") from error
        if not isinstance(event, Mapping) or set(event) != {"schema_version", "receipt", "result"}:
            raise ValueError(f"publication WAL event shape mismatch: {line_number}")
        if event.get("schema_version") != PUBLICATION_COMMIT_EVENT_SCHEMA:
            raise ValueError(f"publication WAL event schema mismatch: {line_number}")
        receipt = PublicationDecisionCommit.from_dict(event.get("receipt"))
        receipt.validate()
        if receipt.publication_scope_id != publication_scope_id:
            raise ValueError("publication WAL scope differs from RunSpec")
        result = event.get("result")
        if not isinstance(result, Mapping):
            raise ValueError("publication WAL result is not an object")
        validate_publication_result_commit(
            result,
            receipt,
            expected_scope_id=publication_scope_id,
            expected_input_index=receipt.input_index,
            expected_post_id=receipt.post_id,
        )
        coordinate = (receipt.input_index, receipt.post_id)
        if coordinate in rows:
            raise ValueError(f"duplicate authoritative WAL coordinate: {coordinate}")
        rows[coordinate] = _WalRow(receipt=receipt, result=dict(result))
    return rows, {
        "path": str(path.resolve()),
        "bytes": len(raw),
        "sha256": _sha256_bytes(raw),
        "event_count": len(rows),
    }


def _read_attempt_claim(
    manifest: Mapping[str, Any],
    manifest_path: Path,
    *,
    arm: str,
    output_path: Path,
    ledger_path: Path,
    run_id: str,
    measurement: Mapping[str, Any],
    run_spec: _RunSpecReadback,
    recovery_witness: _RecoveryWitnessReadback | None,
) -> tuple[Path, dict[str, Any], Path, dict[str, Any]]:
    claim_path = _artifact_path(
        manifest.get("output_attempt_claim"), manifest_path, f"{arm} output attempt claim"
    )
    claim, reference = _load_json_snapshot(claim_path)
    declared_sha = _require_sha256(
        manifest.get("output_attempt_claim_sha256"),
        f"{arm} output_attempt_claim_sha256",
    )
    if reference["sha256"] != declared_sha:
        raise ValueError(f"{arm} output attempt claim bytes mismatch")
    if claim.get("schema_version") != "expert_output_attempt_claim_v1":
        raise ValueError(f"{arm} output attempt claim schema mismatch")
    if claim.get("run_id") != run_id:
        raise ValueError(f"{arm} output attempt claim run_id mismatch")
    claimed_output = _artifact_path(claim.get("output_file"), claim_path, f"{arm} claimed output")
    if claimed_output != output_path:
        if recovery_witness is None:
            raise ValueError(
                f"{arm} recovered/rewritten output rejected: no independent recovery witness "
                "binds the output attempt claim"
            )
        source_result = _validate_artifact_reference(
            recovery_witness.value.get("source_result"), f"{arm} recovery source result"
        )
        if claimed_output != Path(source_result["path"]):
            raise ValueError(f"{arm} recovered output claim/source witness mismatch")
    claimed_ledger = _artifact_path(
        claim.get("decision_call_ledger_path"),
        claim_path,
        f"{arm} claimed decision-call ledger",
    )
    if claimed_ledger != ledger_path:
        raise ValueError(f"{arm} output attempt claim ledger mismatch")
    if claim.get("decision_call_ledger_mode") != "REQUIRED":
        raise ValueError(f"{arm} output attempt claim measurement mode mismatch")
    if claim.get("decision_call_measurement") != dict(measurement):
        raise ValueError(f"{arm} output attempt claim measurement binding mismatch")
    input_path = _artifact_path(
        claim.get("input_file"), claim_path, f"{arm} claimed input"
    )
    input_reference = _read_input_snapshot(
        input_path,
        arm=arm,
        run_spec=run_spec,
    )
    return claim_path, reference, input_path, input_reference


def _recorded_path(value: Any, owner_path: Path, label: str) -> Path:
    return _artifact_path(value, owner_path, label)


def _load_jsonl_rows_from_reference(
    reference: Mapping[str, Any], label: str
) -> list[dict[str, Any]]:
    checked = _validate_artifact_reference(reference, label)
    path = Path(checked["path"])
    raw = _stable_bytes(path)
    rows: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(raw.decode("utf-8-sig").splitlines(), 1):
        if not raw_line.strip():
            continue
        try:
            row = json.loads(raw_line)
        except json.JSONDecodeError as error:
            raise ValueError(f"{label} invalid JSONL line {line_number}: {error}") from error
        if not isinstance(row, dict):
            raise ValueError(f"{label} row {line_number} is not an object")
        rows.append(row)
    return rows


def _load_json_list_from_reference(
    reference: Mapping[str, Any], label: str
) -> list[Any]:
    checked = _validate_artifact_reference(reference, label)
    value, snapshot = _load_json_value_snapshot(Path(checked["path"]))
    if snapshot != checked or not isinstance(value, list):
        raise ValueError(f"{label} must be a bound JSON list")
    return value


def _replay_recovery_checkpoint(
    *,
    arm: str,
    source_manifest: Mapping[str, Any],
    measurement: Mapping[str, Any],
    checkpoint_rows: list[dict[str, Any]],
    recovered_output_rows: Mapping[tuple[int, int | str], Mapping[str, Any]],
    ledger_report: Mapping[str, Any],
    wal_rows: Mapping[tuple[int, int | str], _WalRow],
    run_spec: _RunSpecReadback,
) -> dict[str, Any]:
    expected_coordinates = {
        (index, post_id)
        for index, post_id in enumerate(run_spec.ordered_post_ids, 1)
    }
    checkpoint_by_coordinate: dict[
        tuple[int, int | str], Mapping[str, Any]
    ] = {}
    for row in checkpoint_rows:
        index = _require_positive_int(row.get("global_idx"), "recovery global_idx")
        post_id = _post_id(row.get("post_id"), "recovery checkpoint post_id")
        coordinate = (index, post_id)
        if coordinate in checkpoint_by_coordinate:
            raise ValueError("recovery checkpoint contains duplicate coordinates")
        if row.get("status") != "completed":
            raise ValueError("recovery checkpoint contains a non-completed row")
        checkpoint_by_coordinate[coordinate] = row
    if set(checkpoint_by_coordinate) != expected_coordinates:
        raise ValueError("recovery checkpoint coverage differs from RunSpec")
    if set(recovered_output_rows) != expected_coordinates:
        raise ValueError("recovered output coverage differs from RunSpec")
    if set(wal_rows) != expected_coordinates:
        raise ValueError("recovery WAL coverage differs from RunSpec")
    ledger_rows = _ledger_row_map(ledger_report)
    if set(ledger_rows) != expected_coordinates:
        raise ValueError("recovery ledger coverage differs from RunSpec")

    run_id = _require_text(source_manifest.get("run_id"), "recovery source run_id")
    ledger_coverage = dict(
        _require_mapping(ledger_report.get("coverage"), "recovery ledger coverage")
    )
    if (
        ledger_coverage.get("attempt_run_ids") != [run_id]
        or ledger_coverage.get("attempt_run_count") != 1
        or ledger_coverage.get("observed_row_count") != len(expected_coordinates)
    ):
        raise ValueError("recovery ledger is not one exact fresh attempt")
    scope_id = _require_sha256(
        source_manifest.get("publication_scope_id"),
        "recovery source publication_scope_id",
    )
    row_bindings: list[dict[str, Any]] = []
    for coordinate in sorted(expected_coordinates, key=lambda item: item[0]):
        index, post_id = coordinate
        checkpoint = checkpoint_by_coordinate[coordinate]
        result = checkpoint.get("result")
        if not isinstance(result, Mapping):
            raise ValueError("recovery checkpoint result is not an object")
        recovered_result = recovered_output_rows[coordinate]
        if dict(result) != dict(recovered_result):
            raise ValueError("recovery checkpoint/result source replay mismatch")
        wal_row = wal_rows[coordinate]
        try:
            attempt_receipt = validate_publication_result_commit(
                result,
                checkpoint.get("publication_commit"),
                expected_scope_id=scope_id,
                expected_input_index=index,
                expected_post_id=post_id,
            )
        except Exception as error:
            raise ValueError(
                f"recovery checkpoint publication receipt is invalid: {coordinate}"
            ) from error
        if (
            attempt_receipt.attempt_run_id != run_id
            or attempt_receipt.decision_id != wal_row.receipt.decision_id
            or attempt_receipt.public_projection_sha256
            != wal_row.receipt.public_projection_sha256
        ):
            raise ValueError("recovery checkpoint/WAL decision binding mismatch")
        run_meta = result.get("run_meta")
        if (
            not isinstance(run_meta, Mapping)
            or run_meta.get("run_id") != run_id
            or run_meta.get("measurement_execution_source")
            != "FRESH_EXECUTION_NO_PUBLIC_WRITE"
            or run_meta.get("decision_call_measurement") != dict(measurement)
        ):
            raise ValueError("recovery checkpoint measurement binding mismatch")
        ledger_row = ledger_rows[coordinate]
        if (
            ledger_row.get("attempt_run_id") != run_id
            or ledger_row.get("seal_status") != "SEALED"
            or ledger_row.get("link_status") != "LINKED"
            or ledger_row.get("publication_decision_id")
            != wal_row.receipt.decision_id
        ):
            raise ValueError("recovery checkpoint/ledger linkage mismatch")
        if arm == "AFTER":
            route = _validate_after_route_row(
                result,
                run_meta,
                ledger_row,
                wal_row,
                coordinate=coordinate,
                run_id=run_id,
                measurement=measurement,
                publication_scope_id=scope_id,
            )
            route_sha = route["execution_receipt_sha256"]
        else:
            if "early_route_measurement" in run_meta:
                raise ValueError("BEFORE recovery checkpoint contains an early route")
            route_sha = None
        row_bindings.append(
            {
                "input_index": index,
                "post_id": post_id,
                "publication_decision_id": wal_row.receipt.decision_id,
                "ledger_event_root_sha256": ledger_row.get("event_root_sha256"),
                "execution_receipt_sha256": route_sha,
            }
        )
    return {
        "status": "GO",
        "measurement_eligible": True,
        "actual_kpi_status": "INDEPENDENTLY_VERIFIED_EXACT",
        "recovery_action": "NONE",
        "reason_codes": [],
        "row_count": len(row_bindings),
        "row_bindings_sha256": _sha256(row_bindings),
    }


def _validate_recovery_witness_sources(
    *,
    manifest: Mapping[str, Any],
    manifest_path: Path,
    arm: str,
    run_spec: _RunSpecReadback,
    witness: _RecoveryWitnessReadback,
    measurement: Mapping[str, Any],
    ledger_path: Path,
    ledger_report: Mapping[str, Any],
    publication_wal_path: Path,
    publication_wal_ref: Mapping[str, Any],
    wal_rows: Mapping[tuple[int, int | str], _WalRow],
    output_path: Path,
    output_ref: Mapping[str, Any],
    output_rows: Mapping[tuple[int, int | str], Mapping[str, Any]],
    attempt_claim_path: Path,
    attempt_claim_ref: Mapping[str, Any],
) -> tuple[dict[str, Any], ...]:
    value = witness.value
    source_manifest_ref = _validate_artifact_reference(
        value.get("source_manifest"), f"{arm} recovery source manifest"
    )
    source_result_ref = _validate_artifact_reference(
        value.get("source_result"), f"{arm} recovery source result"
    )
    source_checkpoint_ref = _validate_artifact_reference(
        value.get("source_checkpoint"), f"{arm} recovery source checkpoint"
    )
    source_pending_ref = _validate_artifact_reference(
        value.get("source_pending_snapshot"),
        f"{arm} recovery source pending snapshot",
    )
    recovery_summary_ref = _validate_artifact_reference(
        value.get("recovery_summary"), f"{arm} recovery summary"
    )
    recovered_output_ref = _validate_artifact_reference(
        value.get("recovered_output"), f"{arm} recovered output"
    )
    claim_ref = _validate_artifact_reference(
        value.get("output_attempt_claim"), f"{arm} recovery output attempt claim"
    )
    wal_ref = _validate_artifact_reference(
        value.get("publication_wal"), f"{arm} recovery publication WAL"
    )

    source_manifest_path = Path(source_manifest_ref["path"])
    if source_manifest_path == manifest_path:
        raise ValueError(f"{arm} recovery witness cannot self-bind the recovered manifest")
    source_manifest, source_manifest_snapshot = _load_json_snapshot(source_manifest_path)
    if source_manifest_snapshot != source_manifest_ref:
        raise ValueError(f"{arm} recovery source manifest reference mismatch")
    if any(field in source_manifest for field in _RECOVERY_MARKERS):
        raise ValueError(f"{arm} chained recovery source manifests are not supported")

    expected_marker_paths = {
        "recovered_from": source_manifest_path,
        "recovered_output_path": output_path,
        "recovery_summary": Path(recovery_summary_ref["path"]),
    }
    for field, expected_path in expected_marker_paths.items():
        if _recorded_path(manifest.get(field), manifest_path, f"{arm} {field}") != expected_path:
            raise ValueError(f"{arm} recovery marker path differs from witness: {field}")

    if recovered_output_ref != dict(output_ref):
        raise ValueError(f"{arm} recovered output reference mismatch")
    if claim_ref != dict(attempt_claim_ref) or Path(claim_ref["path"]) != attempt_claim_path:
        raise ValueError(f"{arm} output attempt claim reference mismatch")
    observed_wal_ref = {
        key: publication_wal_ref.get(key) for key in ("path", "bytes", "sha256")
    }
    if wal_ref != observed_wal_ref or Path(wal_ref["path"]) != publication_wal_path:
        raise ValueError(f"{arm} publication WAL reference mismatch")

    ledger_binding = dict(
        _require_mapping(value.get("decision_call_ledger"), f"{arm} recovery ledger")
    )
    if set(ledger_binding) != {
        "path",
        "scope_sha256",
        "frame_set_sha256",
        "report_sha256",
    }:
        raise ValueError(f"{arm} recovery ledger binding shape mismatch")
    expected_ledger_binding = {
        "path": str(ledger_path.resolve()),
        "scope_sha256": manifest.get("decision_call_ledger_scope_sha256"),
        "frame_set_sha256": ledger_report.get("frame_set_sha256"),
        "report_sha256": ledger_report.get("report_sha256"),
    }
    if ledger_binding != expected_ledger_binding:
        raise ValueError(f"{arm} recovery ledger binding mismatch")
    for field in ("scope_sha256", "frame_set_sha256", "report_sha256"):
        _require_sha256(ledger_binding.get(field), f"{arm} recovery ledger {field}")

    if (
        source_manifest.get("run_id") != manifest.get("run_id")
        or source_manifest.get("publication_scope_id")
        != run_spec.value["publication_scope_id"]
        or source_manifest.get("publication_input_snapshot_sha256")
        != run_spec.value["publication_input_snapshot_sha256"]
        or source_manifest.get("decision_call_measurement") != dict(measurement)
    ):
        raise ValueError(f"{arm} recovery source manifest binding mismatch")
    source_paths = {
        "output_file": source_result_ref,
        "checkpoint_jsonl": source_checkpoint_ref,
        "pending_snapshot": source_pending_ref,
        "output_attempt_claim": claim_ref,
        "publication_commit_journal": wal_ref,
    }
    for field, reference in source_paths.items():
        observed = _recorded_path(
            source_manifest.get(field), source_manifest_path, f"{arm} source {field}"
        )
        if observed != Path(reference["path"]):
            raise ValueError(f"{arm} recovery source path mismatch: {field}")
    if _recorded_path(
        source_manifest.get("decision_call_ledger_path"),
        source_manifest_path,
        f"{arm} source decision-call ledger",
    ) != ledger_path:
        raise ValueError(f"{arm} recovery source ledger path mismatch")

    recovery_summary_path = Path(recovery_summary_ref["path"])
    recovery_summary, summary_snapshot = _load_json_snapshot(recovery_summary_path)
    if summary_snapshot != recovery_summary_ref:
        raise ValueError(f"{arm} recovery summary reference mismatch")
    summary_path_fields = {
        "source_result_path": source_result_ref,
        "source_checkpoint_path": source_checkpoint_ref,
        "source_pending_snapshot_path": source_pending_ref,
        "recovered_output_path": recovered_output_ref,
    }
    for field, reference in summary_path_fields.items():
        if _recorded_path(
            recovery_summary.get(field), recovery_summary_path, f"{arm} summary {field}"
        ) != Path(reference["path"]):
            raise ValueError(f"{arm} recovery summary source mismatch: {field}")
    fresh_gate = dict(
        _require_mapping(
            manifest.get("fresh_measurement_recovery"),
            f"{arm} fresh recovery gate",
        )
    )
    if (
        recovery_summary.get("run_id") != manifest.get("run_id")
        or recovery_summary.get("recovery_source") != "publication_commit_wal_current"
        or recovery_summary.get("fresh_measurement_recovery") != fresh_gate
        or recovery_summary.get("recovery_safe_to_use_as_completed_subset") is not True
        or recovery_summary.get("large_run_complete") is not True
        or recovery_summary.get("semantic_quality") != "REVIEW-LOCKED"
        or recovery_summary.get("full_scan_approval") is not False
    ):
        raise ValueError(f"{arm} recovery summary is not an exact safe terminal witness")

    independent = dict(
        _require_mapping(
            fresh_gate.get("independent_readback"),
            f"{arm} recovery independent readback",
        )
    )
    if independent != {
        "gate_status": "GO",
        "report_sha256": ledger_report.get("report_sha256"),
        "reason_codes": [],
    }:
        raise ValueError(f"{arm} recovery independent readback mismatch")
    wal_event_count = publication_wal_ref.get("event_count")
    if (
        _recorded_path(
            fresh_gate.get("ledger_path"), recovery_summary_path, f"{arm} recovery ledger"
        )
        != ledger_path
        or fresh_gate.get("publication_wal_sha256_before") != wal_ref["sha256"]
        or fresh_gate.get("publication_wal_sha256_after") != wal_ref["sha256"]
        or fresh_gate.get("publication_wal_event_count_before") != wal_event_count
        or fresh_gate.get("publication_wal_event_count_after") != wal_event_count
    ):
        raise ValueError(f"{arm} recovery WAL/ledger replay mismatch")

    checkpoint_rows = _load_jsonl_rows_from_reference(
        source_checkpoint_ref, f"{arm} recovery source checkpoint"
    )
    pending_rows = _load_json_list_from_reference(
        source_pending_ref, f"{arm} recovery source pending snapshot"
    )
    completed_checkpoint_rows = sum(
        row.get("status") == "completed" for row in checkpoint_rows
    )
    failed_checkpoint_rows = sum(
        row.get("status") == "failed" for row in checkpoint_rows
    )
    expected_summary_counts = {
        "checkpoint_rows": len(checkpoint_rows),
        "checkpoint_completed_rows": completed_checkpoint_rows,
        "checkpoint_failed_rows": failed_checkpoint_rows,
        "pending_snapshot_rows": len(pending_rows),
        "recovered_rows": len(output_rows),
    }
    if any(
        recovery_summary.get(key) != count
        for key, count in expected_summary_counts.items()
    ):
        raise ValueError(f"{arm} recovery summary source counts mismatch")
    replayed_gate = _replay_recovery_checkpoint(
        arm=arm,
        source_manifest=source_manifest,
        measurement=measurement,
        checkpoint_rows=checkpoint_rows,
        recovered_output_rows=output_rows,
        ledger_report=ledger_report,
        wal_rows=wal_rows,
        run_spec=run_spec,
    )
    for key in (
        "status",
        "measurement_eligible",
        "actual_kpi_status",
        "recovery_action",
        "reason_codes",
    ):
        if fresh_gate.get(key) != replayed_gate[key]:
            raise ValueError(f"{arm} recovery GO witness differs from source replay: {key}")

    return (
        witness.reference,
        source_manifest_ref,
        source_result_ref,
        source_checkpoint_ref,
        source_pending_ref,
        recovery_summary_ref,
        recovered_output_ref,
        claim_ref,
        wal_ref,
    )


def _normalized_input_post_id(value: Any, field: str) -> int | str:
    parsed = _post_id(value, field)
    if isinstance(parsed, str):
        try:
            return int(parsed)
        except ValueError:
            return parsed
    return parsed


def _input_post_ids(entries: Any, *, arm: str, input_format: str) -> tuple[int | str, ...]:
    if not isinstance(entries, list):
        raise ValueError(f"{arm} {input_format} input must contain a list of rows")
    post_ids: list[int | str] = []
    for row_number, entry in enumerate(entries, 1):
        if not isinstance(entry, Mapping):
            raise ValueError(f"{arm} input row is not an object: {row_number}")
        if "comment_id" in entry:
            continue
        if "post_id" not in entry:
            raise ValueError(f"{arm} input row has no post_id: {row_number}")
        post_ids.append(
            _normalized_input_post_id(
                entry.get("post_id"), f"{arm} input post_id[{row_number}]"
            )
        )
    if len({_canonical_bytes(value) for value in post_ids}) != len(post_ids):
        raise ValueError(f"{arm} input contains duplicate post_id rows")
    return tuple(post_ids)


def _read_input_snapshot(
    path: Path,
    *,
    arm: str,
    run_spec: _RunSpecReadback,
) -> dict[str, Any]:
    observed_post_ids, snapshot = _read_unbound_input_snapshot(path, label=arm)
    expected_post_ids = run_spec.ordered_post_ids
    if observed_post_ids != expected_post_ids:
        raise ValueError(
            f"{arm} input ordered post_id coverage differs from RunSpec: "
            f"observed={list(observed_post_ids)}, expected={list(expected_post_ids)}"
        )
    if snapshot["sha256"] != run_spec.value["publication_input_snapshot_sha256"]:
        raise ValueError(f"{arm} input bytes SHA differs from RunSpec")
    return snapshot


def _read_unbound_input_snapshot(
    path: Path,
    *,
    label: str,
) -> tuple[tuple[int | str, ...], dict[str, Any]]:
    """Read input bytes/order before a paired RunSpec exists or while replaying it."""

    raw = _stable_bytes(path)
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError(f"{label} input is not valid UTF-8: {path}") from error
    try:
        decoded = json.loads(text)
    except json.JSONDecodeError:
        entries: list[Any] = []
        for line_number, line in enumerate(text.splitlines(), 1):
            if not line.strip():
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"{label} invalid JSONL input line {line_number}: {error}"
                ) from error
        input_format = "JSONL"
    else:
        if isinstance(decoded, list):
            entries = decoded
            input_format = "JSON_ARRAY"
        elif isinstance(decoded, Mapping) and isinstance(decoded.get("posts"), list):
            entries = list(decoded["posts"])
            input_format = "JSON_OBJECT_POSTS"
        elif isinstance(decoded, Mapping):
            entries = [decoded]
            input_format = "JSON_OBJECT"
        else:
            raise ValueError(f"{label} JSON input root is not rows or an object")
    observed_post_ids = _input_post_ids(
        entries,
        arm=label,
        input_format=input_format,
    )
    raw_sha256 = _sha256_bytes(raw)
    return observed_post_ids, {
        "path": str(path.resolve()),
        "bytes": len(raw),
        "sha256": raw_sha256,
        "format": input_format,
        "post_count": len(observed_post_ids),
        "ordered_post_ids_sha256": _sha256(list(observed_post_ids)),
    }


def build_recovery_witness(
    *,
    run_spec_path: str | Path,
    source_manifest_path: str | Path,
    source_checkpoint_path: str | Path,
    source_pending_snapshot_path: str | Path,
    recovery_summary_path: str | Path,
    recovered_output_path: str | Path,
) -> dict[str, Any]:
    """Build a source-replayed recovery witness without writing any artifact."""

    run_spec = _read_run_spec(run_spec_path)
    source_path = Path(source_manifest_path).resolve()
    source_manifest, source_manifest_ref = _load_json_snapshot(source_path)
    if any(field in source_manifest for field in _RECOVERY_MARKERS):
        raise ValueError("recovery witness source manifest must be an original arm")
    measurement_value = source_manifest.get("decision_call_measurement")
    if not isinstance(measurement_value, Mapping):
        raise ValueError("recovery source measurement is missing")
    arm = measurement_value.get("arm")
    if arm not in {"BEFORE", "AFTER"}:
        raise ValueError("recovery source arm is invalid")
    measurement = _measurement_config(source_manifest, arm, run_spec)
    run_id = _require_text(source_manifest.get("run_id"), "recovery source run_id")
    scope_id = _require_sha256(
        source_manifest.get("publication_scope_id"),
        "recovery source publication_scope_id",
    )

    source_result_path = _artifact_path(
        source_manifest.get("output_file"), source_path, "recovery source result"
    )
    source_checkpoint = Path(source_checkpoint_path).resolve()
    source_pending = Path(source_pending_snapshot_path).resolve()
    for field, supplied_path in (
        ("checkpoint_jsonl", source_checkpoint),
        ("pending_snapshot", source_pending),
    ):
        recorded = _artifact_path(
            source_manifest.get(field), source_path, f"recovery source {field}"
        )
        if recorded != supplied_path:
            raise ValueError(f"recovery source {field} path mismatch")
    summary_path = Path(recovery_summary_path).resolve()
    summary, summary_ref = _load_json_snapshot(summary_path)
    recovered_output = Path(recovered_output_path).resolve()
    if _recorded_path(
        summary.get("recovered_output_path"), summary_path, "summary recovered output"
    ) != recovered_output:
        raise ValueError("recovery summary recovered output path mismatch")
    summary_sources = {
        "source_result_path": source_result_path,
        "source_checkpoint_path": source_checkpoint,
        "source_pending_snapshot_path": source_pending,
    }
    for field, expected in summary_sources.items():
        if _recorded_path(summary.get(field), summary_path, f"summary {field}") != expected:
            raise ValueError(f"recovery summary {field} mismatch")
    fresh_gate = dict(
        _require_mapping(
            summary.get("fresh_measurement_recovery"),
            "recovery summary fresh measurement gate",
        )
    )
    if (
        summary.get("run_id") != run_id
        or summary.get("recovery_source") != "publication_commit_wal_current"
        or summary.get("recovery_safe_to_use_as_completed_subset") is not True
        or summary.get("large_run_complete") is not True
        or summary.get("semantic_quality") != "REVIEW-LOCKED"
        or summary.get("full_scan_approval") is not False
    ):
        raise ValueError("recovery summary is not safe for a measurement witness")

    ledger_path = _artifact_path(
        source_manifest.get("decision_call_ledger_path"),
        source_path,
        "recovery decision-call ledger",
    )
    ledger_report = read_decision_call_ledger(ledger_path)
    if (
        ledger_report.get("gate_status") != "GO"
        or not verify_readback_report_sha256(ledger_report)
    ):
        raise ValueError("recovery decision-call ledger readback is not GO")
    wal_path = _artifact_path(
        source_manifest.get("publication_commit_journal"),
        source_path,
        "recovery publication WAL",
    )
    wal_rows, wal_readback_ref = _read_publication_wal(
        wal_path, publication_scope_id=scope_id
    )
    recovered_value, _ = _load_json_value_snapshot(recovered_output)
    if (
        not isinstance(recovered_value, list)
        or len(recovered_value) != run_spec.value["input_post_count"]
    ):
        raise ValueError("recovered output row coverage mismatch")
    recovered_rows: dict[tuple[int, int | str], Mapping[str, Any]] = {}
    for index, row in enumerate(recovered_value, 1):
        if not isinstance(row, Mapping):
            raise ValueError("recovered output row is not an object")
        post_id = _post_id(row.get("post_id"), "recovered output post_id")
        coordinate = (index, post_id)
        if coordinate in recovered_rows:
            raise ValueError("recovered output contains duplicate coordinates")
        recovered_rows[coordinate] = row
    checkpoint_ref = _artifact_reference_for_path(source_checkpoint)
    checkpoint_rows = _load_jsonl_rows_from_reference(
        checkpoint_ref, "recovery source checkpoint"
    )
    pending_ref = _artifact_reference_for_path(source_pending)
    pending_rows = _load_json_list_from_reference(
        pending_ref, "recovery source pending snapshot"
    )
    expected_summary_counts = {
        "checkpoint_rows": len(checkpoint_rows),
        "checkpoint_completed_rows": sum(
            row.get("status") == "completed" for row in checkpoint_rows
        ),
        "checkpoint_failed_rows": sum(
            row.get("status") == "failed" for row in checkpoint_rows
        ),
        "pending_snapshot_rows": len(pending_rows),
        "recovered_rows": len(recovered_rows),
    }
    if any(summary.get(key) != count for key, count in expected_summary_counts.items()):
        raise ValueError("recovery summary source counts mismatch")
    replayed_gate = _replay_recovery_checkpoint(
        arm=arm,
        source_manifest=source_manifest,
        measurement=measurement,
        checkpoint_rows=checkpoint_rows,
        recovered_output_rows=recovered_rows,
        ledger_report=ledger_report,
        wal_rows=wal_rows,
        run_spec=run_spec,
    )
    for key in (
        "status",
        "measurement_eligible",
        "actual_kpi_status",
        "recovery_action",
        "reason_codes",
    ):
        if fresh_gate.get(key) != replayed_gate[key]:
            raise ValueError(f"recovery summary differs from source replay: {key}")
    wal_ref = {
        key: wal_readback_ref[key] for key in ("path", "bytes", "sha256")
    }
    wal_event_count = wal_readback_ref["event_count"]
    if (
        fresh_gate.get("publication_wal_unchanged") is not True
        or fresh_gate.get("publication_wal_sha256_before") != wal_ref["sha256"]
        or fresh_gate.get("publication_wal_sha256_after") != wal_ref["sha256"]
        or fresh_gate.get("publication_wal_event_count_before") != wal_event_count
        or fresh_gate.get("publication_wal_event_count_after") != wal_event_count
    ):
        raise ValueError("recovery summary WAL snapshot differs from source replay")

    claim_path = _artifact_path(
        source_manifest.get("output_attempt_claim"),
        source_path,
        "recovery output attempt claim",
    )
    payload: dict[str, Any] = {
        "schema_version": RECOVERY_WITNESS_SCHEMA_VERSION,
        "arm": arm,
        "run_spec_sha256": run_spec.value["run_spec_sha256"],
        "pair_id": run_spec.value["pair_id"],
        "publication_scope_id": scope_id,
        "attempt_run_id": run_id,
        "recovery_source": "publication_commit_wal_current",
        "status": "GO",
        "measurement_eligible": True,
        "actual_kpi_status": "INDEPENDENTLY_VERIFIED_EXACT",
        "recovery_action": "NONE",
        "reason_codes": [],
        "input_post_count": run_spec.value["input_post_count"],
        "ordered_post_ids_sha256": _sha256(list(run_spec.ordered_post_ids)),
        "source_manifest": source_manifest_ref,
        "source_result": _artifact_reference_for_path(source_result_path),
        "source_checkpoint": checkpoint_ref,
        "source_pending_snapshot": pending_ref,
        "recovery_summary": summary_ref,
        "recovered_output": _artifact_reference_for_path(recovered_output),
        "output_attempt_claim": _artifact_reference_for_path(claim_path),
        "publication_wal": wal_ref,
        "decision_call_ledger": {
            "path": str(ledger_path),
            "scope_sha256": source_manifest.get(
                "decision_call_ledger_scope_sha256"
            ),
            "frame_set_sha256": ledger_report.get("frame_set_sha256"),
            "report_sha256": ledger_report.get("report_sha256"),
        },
        "fresh_measurement_recovery": fresh_gate,
    }
    return {**payload, "witness_sha256": _sha256(payload)}


def build_paired_measurement_run_spec(
    *,
    input_path: str | Path,
    source_manifest_path: str | Path,
    pair_id: str,
    slang_access_mode: str = "OFF",
) -> dict[str, Any]:
    """Freeze the exact input, publication scope, and runtime for two fresh arms.

    The source manifest must already own a complete authoritative publication
    WAL for the exact input bytes.  This function launches no provider and
    writes nothing; the CLI performs exclusive validated persistence.
    """

    source_path = Path(source_manifest_path).resolve()
    manifest, _ = _load_json_snapshot(source_path)
    input_post_ids, input_reference = _read_unbound_input_snapshot(
        Path(input_path).resolve(),
        label="RUN_SPEC",
    )
    input_count = len(input_post_ids)
    if input_count == 0:
        raise ValueError("paired RunSpec input must contain at least one post")
    if manifest.get("terminal_artifacts_finalized") is not True:
        raise ValueError("source manifest terminal artifacts are not finalized")
    if manifest.get("large_run_complete") is not True:
        raise ValueError("source manifest is not large_run_complete")
    if _require_nonnegative_int(
        manifest.get("input_post_count"), "source input_post_count"
    ) != input_count:
        raise ValueError("source manifest input count differs from frozen input")
    if (
        manifest.get("publication_input_snapshot_sha256")
        != input_reference["sha256"]
    ):
        raise ValueError("source manifest input bytes SHA differs from frozen input")
    scope_id = _require_sha256(
        manifest.get("publication_scope_id"), "source publication_scope_id"
    )
    wal_path = _artifact_path(
        manifest.get("publication_commit_journal"),
        source_path,
        "source publication WAL",
    )
    wal_rows, _ = _read_publication_wal(
        wal_path,
        publication_scope_id=scope_id,
    )
    expected_coordinates = {
        (index, post_id) for index, post_id in enumerate(input_post_ids, 1)
    }
    if set(wal_rows) != expected_coordinates:
        raise ValueError("source publication WAL coverage differs from frozen input")
    if _require_nonnegative_int(
        manifest.get("publication_commit_count"), "source publication_commit_count"
    ) != input_count:
        raise ValueError("source publication commit count differs from frozen input")

    runtime_fields = {
        field: manifest.get(field) for field in sorted(_REQUIRED_RUNTIME_FIELDS)
    }
    missing_runtime = sorted(
        field for field, value in runtime_fields.items() if value is None
    )
    if missing_runtime:
        raise ValueError(f"source runtime fields missing: {missing_runtime}")
    requested_parallel = _require_positive_int(
        runtime_fields["requested_parallel"], "source requested_parallel"
    )
    effective_parallel = _require_positive_int(
        runtime_fields["effective_parallel"], "source effective_parallel"
    )
    if requested_parallel != 16 or effective_parallel != min(16, input_count):
        raise ValueError("source runtime does not use parallel 16 bounded by input count")
    if (
        runtime_fields["dashboard_enabled"] is not True
        or runtime_fields["mcp_health_include_search"] is not True
        or runtime_fields["mcp_health_light_mode"] is not False
        or runtime_fields["vlm_ocr_semantic_review_ready"] is not True
    ):
        raise ValueError("source runtime readiness does not satisfy paired policy")
    if (
        _require_nonnegative_int(
            runtime_fields["mcp_health_ok_count"], "source mcp_health_ok_count"
        )
        < 16
        or _require_nonnegative_int(
            runtime_fields["mcp_health_failure_count"],
            "source mcp_health_failure_count",
        )
        != 0
        or runtime_fields["mcp_healthy_endpoint_filter_reason"]
        != "reuse_shards_only"
    ):
        raise ValueError("source runtime search/reuse-shards-only policy mismatch")
    for field in (
        "publication_config_sha256",
        "publication_decision_environment_sha256",
        "publication_slang_db_input_sha256",
        "publication_release_fingerprint",
    ):
        _require_sha256(runtime_fields[field], f"source {field}")

    normalized_slang = str(slang_access_mode or "").strip().upper()
    if normalized_slang not in {"OFF", "READ_ONLY"}:
        raise ValueError("slang_access_mode must be OFF or READ_ONLY")
    mutable_binding = {
        "schema_version": "paired_measurement_mutable_context_binding_v1",
        "mutable_context_mode": "FROZEN_OFF",
        "batch_context_enabled": False,
        "slang_access_mode": normalized_slang,
        "central_slang_db_write_allowed": False,
    }
    shared_measurement = {
        **_REQUIRED_SHARED_MEASUREMENT,
        "slang_access_mode": normalized_slang,
        "mutable_context_binding": mutable_binding,
        "mutable_context_binding_sha256": _sha256(mutable_binding),
        "execution_envelope_policy": {
            "schema_version": EXECUTION_ENVELOPE_POLICY_SCHEMA_VERSION,
            "bootstrap_seed": 20260712,
            "bootstrap_replicates": 2000,
            "alpha": 0.05,
            "min_comparable_rows": 2,
        },
    }
    payload: dict[str, Any] = {
        "schema_version": RUN_SPEC_SCHEMA_VERSION,
        "pair_id": _require_text(pair_id, "pair_id"),
        "publication_scope_id": scope_id,
        "publication_input_snapshot_sha256": input_reference["sha256"],
        "input_post_count": input_count,
        "ordered_post_ids": list(input_post_ids),
        "frozen_conditions": {
            "runtime_manifest_fields": runtime_fields,
            "shared_measurement_fields": shared_measurement,
            "arm_measurement_fields": {
                "BEFORE": {
                    "early_route_enabled": False,
                    "early_route_enable_status": "DISABLED_CONDITIONS_NOT_MET",
                },
                "AFTER": {
                    "early_route_enabled": True,
                    "early_route_enable_status": (
                        "ENABLED_AFTER_REQUIRED_FRESH_SOURCE_ONLY_V1"
                    ),
                },
            },
        },
        "recovery_policy": "ALLOW_RECOVERED_ARMS_EXACT_BOUND_WITNESS_ONLY",
        "approval_boundary": {
            "semantic_quality": "REVIEW-LOCKED",
            "production_enable_allowed": False,
            "full_scan_approval": False,
        },
    }
    return {**payload, "run_spec_sha256": _sha256(payload)}


def _reference_payload(result: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in result.items() if key != "run_meta"}


def _validate_after_route_row(
    output_row: Mapping[str, Any],
    run_meta: Mapping[str, Any],
    ledger_row: Mapping[str, Any],
    wal_row: _WalRow,
    *,
    coordinate: tuple[int, int | str],
    run_id: str,
    measurement: Mapping[str, Any],
    publication_scope_id: str,
) -> dict[str, Any]:
    route = run_meta.get("early_route_measurement")
    if not isinstance(route, Mapping) or set(route) != {"execution_receipt", "comparison_receipt"}:
        raise ValueError(f"AFTER output early_route receipt coverage mismatch: {coordinate}")
    execution = route.get("execution_receipt")
    comparison = route.get("comparison_receipt")
    if not isinstance(execution, Mapping) or not isinstance(comparison, Mapping):
        raise ValueError(f"AFTER output early_route receipts are incomplete: {coordinate}")
    expected_execution_keys = {
        "schema_version",
        "mode",
        "route_decision",
        "execution_status",
        "compute_skip_applied",
        "public_action_applied",
        "production_enable_allowed",
        "accuracy_status",
        "receipt_sha256",
    }
    if set(execution) != expected_execution_keys:
        raise ValueError(f"AFTER execution receipt shape mismatch: {coordinate}")
    expected_execution_hash = _sha256(
        {key: value for key, value in execution.items() if key != "receipt_sha256"}
    )
    if execution.get("receipt_sha256") != expected_execution_hash:
        raise ValueError(f"AFTER execution receipt self hash mismatch: {coordinate}")
    decision = EarlyRouteDecision.from_dict(execution.get("route_decision"))
    if (
        decision.publication_scope_id != publication_scope_id
        or decision.pair_id != measurement.get("pair_id")
        or decision.arm != ARM_AFTER
        or decision.input_index != coordinate[0]
        or decision.post_id != str(coordinate[1])
    ):
        raise ValueError(f"AFTER route decision binding mismatch: {coordinate}")
    if (
        execution.get("schema_version") != "early_route_execution_receipt_v1"
        or execution.get("mode") != "SOURCE_ONLY_V1"
        or execution.get("public_action_applied") is not False
        or execution.get("production_enable_allowed") is not False
        or execution.get("accuracy_status") != ACCURACY_NOT_ESTIMABLE
    ):
        raise ValueError(f"AFTER execution receipt safety boundary mismatch: {coordinate}")

    typed_comparison = EarlyRouteComparisonReceipt.from_dict(comparison)
    current_receipt = compute_publication_decision_commit(
        output_row,
        publication_scope_id=publication_scope_id,
        attempt_run_id=run_id,
        input_index=coordinate[0],
        post_id=coordinate[1],
    )
    if (
        typed_comparison.publication_scope_id != publication_scope_id
        or typed_comparison.pair_id != measurement.get("pair_id")
        or typed_comparison.input_index != coordinate[0]
        or typed_comparison.post_id != str(coordinate[1])
        or typed_comparison.route_decision_sha256 != decision.decision_sha256
        or typed_comparison.selected_lane != decision.selected_lane
        or typed_comparison.authoritative_wal_receipt_sha256
        != wal_row.receipt.commit_sha256
        or typed_comparison.authoritative_wal_outcome != wal_row.receipt.outcome
        or typed_comparison.public_projection_before_sha256
        != wal_row.receipt.public_projection_sha256
        or typed_comparison.public_projection_after_sha256
        != current_receipt.public_projection_sha256
        or typed_comparison.public_noninterference_status != "GO"
    ):
        raise ValueError(f"AFTER comparison receipt/WAL binding mismatch: {coordinate}")
    validate_publication_result_decision(
        output_row,
        wal_row.receipt,
        expected_scope_id=publication_scope_id,
        expected_input_index=coordinate[0],
        expected_post_id=coordinate[1],
    )

    zero_calls = ledger_row.get("expert_calls") == 0
    if decision.selected_lane == LANE_CHEAP_NIL:
        if (
            execution.get("execution_status")
            != "CHEAP_ZERO_CALL_AUTHORITATIVE_REFERENCE_COPY"
            or execution.get("compute_skip_applied") is not True
            or not zero_calls
            or any(ledger_row.get(metric) != 0 for metric in _METRIC_NAMES)
            or typed_comparison.baseline_equivalence_status != "BASELINE_EQUIVALENT"
            or _reference_payload(output_row) != _reference_payload(wal_row.result)
        ):
            raise ValueError(f"AFTER authoritative reference-copy proof mismatch: {coordinate}")
        execution_class = REFERENCE_COPY_COST_ONLY
        production_eligible = False
    elif decision.selected_lane == LANE_FULL:
        if (
            execution.get("execution_status") != "FULL_EXPERT_EXECUTED"
            or execution.get("compute_skip_applied") is not False
        ):
            raise ValueError(f"AFTER full-expert execution receipt mismatch: {coordinate}")
        if zero_calls:
            raise ValueError(f"AFTER unexplained zero physical calls: {coordinate}")
        execution_class = "PRODUCTION_INFERENCE_OBSERVED"
        production_eligible = True
    else:
        raise ValueError(f"AFTER unsupported early-route lane: {coordinate}")
    return {
        "execution_class": execution_class,
        "production_savings_kpi_eligible": production_eligible,
        "route_decision_sha256": decision.decision_sha256,
        "execution_receipt_sha256": execution["receipt_sha256"],
        "comparison_receipt_sha256": typed_comparison.receipt_sha256,
        "selected_lane": decision.selected_lane,
    }


@dataclass(frozen=True)
class _ArmReadback:
    arm: str
    manifest_path: Path
    manifest: dict[str, Any]
    manifest_ref: dict[str, Any]
    measurement: dict[str, Any]
    ledger_report: dict[str, Any]
    ledger_path: Path
    publication_wal_path: Path
    publication_wal_ref: dict[str, Any]
    wal_rows: dict[tuple[int, int | str], _WalRow]
    output_path: Path
    output_ref: dict[str, Any]
    output_rows: dict[tuple[int, int | str], Mapping[str, Any]]
    route_rows: dict[tuple[int, int | str], dict[str, Any]]
    attempt_claim_path: Path
    attempt_claim_ref: dict[str, Any]
    input_path: Path
    input_ref: dict[str, Any]
    input_count: int
    run_id: str
    recovery_witness: _RecoveryWitnessReadback | None
    recovery_source_refs: tuple[dict[str, Any], ...]


def _read_arm(path: str | Path, arm: str, run_spec: _RunSpecReadback) -> _ArmReadback:
    manifest_path = Path(path).resolve()
    manifest, manifest_ref = _load_json_snapshot(manifest_path)
    recovery_witness = _load_recovery_witness(
        manifest, manifest_path, arm, run_spec
    )
    input_count = _validate_runtime_terminal(
        manifest, arm, run_spec, recovery_witness
    )
    measurement = _measurement_config(manifest, arm, run_spec)
    scope_id = _require_sha256(manifest.get("publication_scope_id"), f"{arm} publication_scope_id")
    run_id = _require_text(manifest.get("run_id"), f"{arm} run_id")

    ledger_path = _artifact_path(
        manifest.get("decision_call_ledger_path"), manifest_path, f"{arm} ledger"
    )
    if not ledger_path.is_dir():
        raise ValueError(f"{arm} decision-call ledger directory is missing")
    ledger_report = read_decision_call_ledger(ledger_path)
    if ledger_report.get("gate_status") != "GO" or not verify_readback_report_sha256(ledger_report):
        raise ValueError(f"{arm} independent decision-call readback is not GO")
    declared_scope_sha = _require_sha256(
        manifest.get("decision_call_ledger_scope_sha256"),
        f"{arm} decision_call_ledger_scope_sha256",
    )
    ledger_scope = _require_mapping(ledger_report.get("scope"), f"{arm} ledger scope")
    if ledger_scope.get("scope_sha256") != declared_scope_sha:
        raise ValueError(f"{arm} ledger scope SHA mismatch")
    if ledger_scope.get("publication_scope_id") != scope_id:
        raise ValueError(f"{arm} ledger publication scope mismatch")
    expected_bindings = {
        "run_spec_sha256": run_spec.value["run_spec_sha256"],
        "pair_id": run_spec.value["pair_id"],
        "arm": arm,
        "fresh_execution_mode": True,
    }
    if ledger_scope.get("measurement_bindings") != expected_bindings:
        raise ValueError(f"{arm} ledger measurement bindings mismatch")
    coverage = _require_mapping(ledger_report.get("coverage"), f"{arm} ledger coverage")
    if coverage.get("observed_row_count") != input_count:
        raise ValueError(f"{arm} ledger row coverage mismatch")
    if coverage.get("attempt_run_ids") != [run_id] or coverage.get("attempt_run_count") != 1:
        raise ValueError(f"{arm} ledger attempt run binding mismatch")
    rows = ledger_report.get("rows")
    if not isinstance(rows, list) or len(rows) != input_count:
        raise ValueError(f"{arm} independent row receipts are incomplete")
    ledger_by_coordinate: dict[tuple[int, int | str], Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError(f"{arm} independent row receipt is invalid")
        index = _require_positive_int(row.get("input_index"), f"{arm} ledger input_index")
        post_id = _post_id(row.get("post_id"), f"{arm} ledger post_id")
        coordinate = (index, post_id)
        if coordinate in ledger_by_coordinate:
            raise ValueError(f"{arm} duplicate ledger coordinate: {coordinate}")
        if row.get("attempt_run_id") != run_id:
            raise ValueError(f"{arm} ledger row run_id mismatch: {coordinate}")
        for metric in _METRIC_NAMES:
            _require_nonnegative_int(row.get(metric), f"{arm} row {metric}")
        ledger_by_coordinate[coordinate] = row

    expected_coordinates = {
        (index, post_id) for index, post_id in enumerate(run_spec.ordered_post_ids, 1)
    }
    if set(ledger_by_coordinate) != expected_coordinates:
        raise ValueError(f"{arm} ledger coordinates differ from RunSpec")

    wal_path = _artifact_path(
        manifest.get("publication_commit_journal"), manifest_path, f"{arm} publication WAL"
    )
    wal_rows, wal_ref = _read_publication_wal(wal_path, publication_scope_id=scope_id)
    if set(wal_rows) != expected_coordinates:
        raise ValueError(f"{arm} authoritative WAL coverage differs from RunSpec")
    if (
        _require_nonnegative_int(
            manifest.get("publication_commit_count"), f"{arm} publication_commit_count"
        )
        != input_count
    ):
        raise ValueError(f"{arm} publication commit count mismatch")
    for coordinate, row in ledger_by_coordinate.items():
        if row.get("publication_decision_id") != wal_rows[coordinate].receipt.decision_id:
            raise ValueError(f"{arm} ledger row is not linked to authoritative WAL")

    output_path = _artifact_path(manifest.get("output_file"), manifest_path, f"{arm} output")
    output_value, output_ref = _load_json_value_snapshot(output_path)
    if not isinstance(output_value, list) or len(output_value) != input_count:
        raise ValueError(f"{arm} output row coverage mismatch")
    observed_post_ids = []
    output_rows: dict[tuple[int, int | str], Mapping[str, Any]] = {}
    route_rows: dict[tuple[int, int | str], dict[str, Any]] = {}
    for index, raw_row in enumerate(output_value, 1):
        if not isinstance(raw_row, Mapping):
            raise ValueError(f"{arm} output row is not an object: {index}")
        post_id = _post_id(raw_row.get("post_id"), f"{arm} output post_id")
        observed_post_ids.append(post_id)
        coordinate = (index, post_id)
        if coordinate not in expected_coordinates:
            raise ValueError(f"{arm} output coordinate differs from RunSpec: {coordinate}")
        run_meta = _require_mapping(raw_row.get("run_meta"), f"{arm} output run_meta")
        if run_meta.get("run_id") != run_id:
            raise ValueError(f"{arm} output run_id mismatch: {coordinate}")
        if run_meta.get("model") != run_spec.runtime_fields["llm_model"]:
            raise ValueError(f"{arm} output model differs from RunSpec: {coordinate}")
        if run_meta.get("effective_parallel") != run_spec.runtime_fields["effective_parallel"]:
            raise ValueError(f"{arm} output effective_parallel differs from RunSpec: {coordinate}")
        if run_meta.get("decision_call_measurement") != measurement:
            raise ValueError(f"{arm} output measurement binding mismatch: {coordinate}")
        if run_meta.get("measurement_execution_source") != "FRESH_EXECUTION_NO_PUBLIC_WRITE":
            raise ValueError(f"{arm} output is not from fresh measurement execution: {coordinate}")
        ledger_row = ledger_by_coordinate[coordinate]
        wal_row = wal_rows[coordinate]
        validate_publication_result_decision(
            raw_row,
            wal_row.receipt,
            expected_scope_id=scope_id,
            expected_input_index=index,
            expected_post_id=post_id,
        )
        if arm == "BEFORE":
            if "early_route_measurement" in run_meta:
                raise ValueError(f"BEFORE output unexpectedly contains early-route receipt: {coordinate}")
            if ledger_row.get("expert_calls") == 0:
                raise ValueError(f"BEFORE unexplained zero physical calls: {coordinate}")
        else:
            route_rows[coordinate] = _validate_after_route_row(
                raw_row,
                run_meta,
                ledger_row,
                wal_row,
                coordinate=coordinate,
                run_id=run_id,
                measurement=measurement,
                publication_scope_id=scope_id,
            )
        output_rows[coordinate] = raw_row
    if tuple(observed_post_ids) != run_spec.ordered_post_ids:
        raise ValueError(f"{arm} output ordered post_id coverage differs from RunSpec")

    early_gate = _require_mapping(
        manifest.get("early_route_execution_gate"), f"{arm} early_route_execution_gate"
    )
    if arm == "AFTER":
        cheap_count = sum(
            row["execution_class"] == REFERENCE_COPY_COST_ONLY for row in route_rows.values()
        )
        expected_gate = {
            "required": True,
            "status": "GO",
            "expected_input_count": input_count,
            "observed_route_count": input_count,
            "observed_comparison_count": input_count,
            "cheap_count": cheap_count,
            "cheap_zero_call_writer_verified_count": cheap_count,
            "reason_codes": [],
        }
    else:
        expected_gate = {
            "required": False,
            "status": "NOT_REQUIRED",
            "expected_input_count": input_count,
            "observed_route_count": 0,
            "observed_comparison_count": 0,
            "cheap_count": 0,
            "cheap_zero_call_writer_verified_count": 0,
            "reason_codes": [],
        }
    for field, expected in expected_gate.items():
        if early_gate.get(field) != expected:
            raise ValueError(f"{arm} early-route writer gate {field} mismatch")

    claim_path, claim_ref, input_path, input_ref = _read_attempt_claim(
        manifest,
        manifest_path,
        arm=arm,
        output_path=output_path,
        ledger_path=ledger_path,
        run_id=run_id,
        measurement=measurement,
        run_spec=run_spec,
        recovery_witness=recovery_witness,
    )
    recovery_source_refs: tuple[dict[str, Any], ...] = ()
    if recovery_witness is not None:
        recovery_source_refs = _validate_recovery_witness_sources(
            manifest=manifest,
            manifest_path=manifest_path,
            arm=arm,
            run_spec=run_spec,
            witness=recovery_witness,
            measurement=measurement,
            ledger_path=ledger_path,
            ledger_report=ledger_report,
            publication_wal_path=wal_path,
            publication_wal_ref=wal_ref,
            wal_rows=wal_rows,
            output_path=output_path,
            output_ref=output_ref,
            output_rows=output_rows,
            attempt_claim_path=claim_path,
            attempt_claim_ref=claim_ref,
        )
    return _ArmReadback(
        arm=arm,
        manifest_path=manifest_path,
        manifest=manifest,
        manifest_ref=manifest_ref,
        measurement=measurement,
        ledger_report=ledger_report,
        ledger_path=ledger_path,
        publication_wal_path=wal_path,
        publication_wal_ref=wal_ref,
        wal_rows=wal_rows,
        output_path=output_path,
        output_ref=output_ref,
        output_rows=output_rows,
        route_rows=route_rows,
        attempt_claim_path=claim_path,
        attempt_claim_ref=claim_ref,
        input_path=input_path,
        input_ref=input_ref,
        input_count=input_count,
        run_id=run_id,
        recovery_witness=recovery_witness,
        recovery_source_refs=recovery_source_refs,
    )


def _metric_receipt(
    name: str,
    before: int,
    after: int,
    *,
    status: str,
) -> dict[str, Any]:
    before_value = _require_nonnegative_int(before, f"before {name}")
    after_value = _require_nonnegative_int(after, f"after {name}")
    reduction = before_value - after_value
    if before_value == 0:
        percent = None
    else:
        percent = 100.0 * reduction / before_value
        if not math.isfinite(percent):
            raise ValueError(f"non-finite metric reduction: {name}")
    return {
        "metric": name,
        "before": before_value,
        "after": after_value,
        "absolute_reduction": reduction,
        "reduction_percent": percent,
        "status": status,
    }


def _sum_metrics(
    rows: Mapping[tuple[int, int | str], Mapping[str, Any]],
    coordinates: set[tuple[int, int | str]],
) -> dict[str, int]:
    return {
        name: sum(_require_nonnegative_int(rows[coordinate].get(name), name) for coordinate in coordinates)
        for name in _METRIC_NAMES
    }


def _read_execution_envelope_policy(
    shared_measurement_fields: Mapping[str, Any],
) -> dict[str, Any] | None:
    """Read a pre-bound latency policy without inventing one for legacy specs."""

    value = shared_measurement_fields.get("execution_envelope_policy")
    if value is None:
        return None
    policy = dict(_require_mapping(value, "execution_envelope_policy"))
    if set(policy) != _EXECUTION_ENVELOPE_POLICY_KEYS:
        raise ValueError("execution_envelope_policy shape mismatch")
    if policy.get("schema_version") != EXECUTION_ENVELOPE_POLICY_SCHEMA_VERSION:
        raise ValueError("unsupported execution_envelope_policy schema")
    seed = _require_nonnegative_int(
        policy.get("bootstrap_seed"), "execution_envelope_policy bootstrap_seed"
    )
    replicates = _require_positive_int(
        policy.get("bootstrap_replicates"),
        "execution_envelope_policy bootstrap_replicates",
    )
    alpha = policy.get("alpha")
    if (
        isinstance(alpha, bool)
        or not isinstance(alpha, (int, float))
        or not math.isfinite(float(alpha))
        or not 0.0 < float(alpha) < 0.5
    ):
        raise ValueError("execution_envelope_policy alpha is invalid")
    min_rows = _require_positive_int(
        policy.get("min_comparable_rows"),
        "execution_envelope_policy min_comparable_rows",
    )
    if replicates < 100:
        raise ValueError("execution_envelope_policy requires at least 100 replicates")
    return {
        "schema_version": EXECUTION_ENVELOPE_POLICY_SCHEMA_VERSION,
        "bootstrap_seed": seed,
        "bootstrap_replicates": replicates,
        "alpha": float(alpha),
        "min_comparable_rows": min_rows,
    }


def _execution_envelope_for_arm(
    arm: _ArmReadback,
    run_spec: _RunSpecReadback,
) -> dict[str, Any]:
    """Reconstruct an E2E envelope from immutable output-row cost traces.

    The trace is intentionally separate from the physical-call ledger: it
    measures one row's wall time, whereas the ledger is the only source for
    provider call/token totals.  This reader never turns a reference-copy row
    into a production latency claim.
    """

    rows: list[dict[str, Any]] = []
    starts: list[datetime] = []
    finishes: list[datetime] = []
    for coordinate in sorted(arm.output_rows, key=lambda item: (item[0], str(item[1]))):
        output_row = arm.output_rows[coordinate]
        run_meta = _require_mapping(output_row.get("run_meta"), f"{arm.arm} output run_meta")
        trace = decision_cost_trace_from_dict(run_meta.get("decision_cost_trace"))
        if (
            trace.publication_scope_id != run_spec.value["publication_scope_id"]
            or trace.run_id != arm.run_id
            or trace.input_index != coordinate[0]
            or trace.post_id != str(coordinate[1])
        ):
            raise ValueError(f"{arm.arm} execution envelope trace binding mismatch: {coordinate}")
        started = datetime.fromisoformat(trace.processing_started_at)
        finished = datetime.fromisoformat(trace.processing_finished_at)
        starts.append(started)
        finishes.append(finished)
        rows.append(
            {
                "input_index": coordinate[0],
                "post_id": coordinate[1],
                "trace_sha256": trace.trace_sha256,
                "processing_started_at": trace.processing_started_at,
                "processing_finished_at": trace.processing_finished_at,
                "wall_ms": trace.wall_ms,
            }
        )
    if len(rows) != arm.input_count:
        raise ValueError(f"{arm.arm} execution envelope row coverage mismatch")
    payload = {
        "schema_version": EXECUTION_ENVELOPE_SCHEMA_VERSION,
        "run_spec_sha256": run_spec.value["run_spec_sha256"],
        "pair_id": run_spec.value["pair_id"],
        "arm": arm.arm,
        "attempt_run_id": arm.run_id,
        "input_post_count": arm.input_count,
        "batch_started_at": min(starts).isoformat(timespec="milliseconds"),
        "batch_finished_at": max(finishes).isoformat(timespec="milliseconds"),
        "batch_wall_ms": max(0, round((max(finishes) - min(starts)).total_seconds() * 1000)),
        "rows": rows,
    }
    return {**payload, "envelope_sha256": _sha256(payload)}


def _percentile(values: list[int], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(ordered[lower])
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _paired_execution_latency(
    *,
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    coordinates: set[tuple[int, int | str]],
    policy: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if policy is None:
        return {"value": None, "status": "NOT_ESTIMABLE_NO_EXECUTION_ENVELOPE_POLICY"}
    before_rows = {(row["input_index"], row["post_id"]): row for row in before["rows"]}
    after_rows = {(row["input_index"], row["post_id"]): row for row in after["rows"]}
    if set(before_rows) != set(after_rows):
        raise ValueError("BEFORE/AFTER execution envelope coverage mismatch")
    if not coordinates:
        return {"value": None, "status": "NOT_ESTIMABLE_NO_PRODUCTION_INFERENCE_COMPARABLE_ROWS"}
    if not coordinates <= set(before_rows):
        raise ValueError("execution envelope production coordinate mismatch")
    pairs = [
        (int(before_rows[coordinate]["wall_ms"]), int(after_rows[coordinate]["wall_ms"]))
        for coordinate in sorted(coordinates, key=lambda item: (item[0], str(item[1])))
    ]
    if len(pairs) < policy["min_comparable_rows"]:
        return {
            "value": None,
            "status": "NOT_ESTIMABLE_INSUFFICIENT_COMPARABLE_EXECUTION_ROWS",
            "comparable_row_count": len(pairs),
        }
    rng = random.Random(policy["bootstrap_seed"])
    p50_deltas: list[float] = []
    p95_deltas: list[float] = []
    for _ in range(policy["bootstrap_replicates"]):
        sample = [pairs[rng.randrange(len(pairs))] for _ in pairs]
        before_values = [item[0] for item in sample]
        after_values = [item[1] for item in sample]
        p50_deltas.append(_percentile(after_values, 0.50) - _percentile(before_values, 0.50))
        p95_deltas.append(_percentile(after_values, 0.95) - _percentile(before_values, 0.95))
    qlo = int((policy["alpha"] / 2) * (len(p50_deltas) - 1))
    qhi = int((1 - policy["alpha"] / 2) * (len(p50_deltas) - 1))
    p50_deltas.sort()
    p95_deltas.sort()
    before_values = [item[0] for item in pairs]
    after_values = [item[1] for item in pairs]
    before_p50 = _percentile(before_values, 0.50)
    after_p50 = _percentile(after_values, 0.50)
    before_p95 = _percentile(before_values, 0.95)
    after_p95 = _percentile(after_values, 0.95)
    return {
        "value": after_p50 - before_p50,
        "status": _PRODUCTION_COMPARABLE,
        "unit": "milliseconds_per_post",
        "comparable_row_count": len(pairs),
        "policy": dict(policy),
        "p50": {
            "before": before_p50,
            "after": after_p50,
            "delta": after_p50 - before_p50,
            "paired_ci_lower": p50_deltas[qlo],
            "paired_ci_upper": p50_deltas[qhi],
        },
        "p95": {
            "before": before_p95,
            "after": after_p95,
            "delta": after_p95 - before_p95,
            "paired_ci_lower": p95_deltas[qlo],
            "paired_ci_upper": p95_deltas[qhi],
        },
        "before_batch_wall_ms": before["batch_wall_ms"],
        "after_batch_wall_ms": after["batch_wall_ms"],
    }


def _ledger_row_map(report: Mapping[str, Any]) -> dict[tuple[int, int | str], Mapping[str, Any]]:
    rows = report.get("rows")
    if not isinstance(rows, list):
        raise ValueError("independent readback rows are missing")
    result: dict[tuple[int, int | str], Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("independent readback row is invalid")
        coordinate = (row.get("input_index"), row.get("post_id"))
        if coordinate in result:
            raise ValueError("duplicate paired row coordinate")
        result[coordinate] = row
    return result


def _assert_ledger_replay_unchanged(arm: _ArmReadback) -> None:
    replay = read_decision_call_ledger(arm.ledger_path)
    if replay.get("gate_status") != "GO" or not verify_readback_report_sha256(replay):
        raise ValueError(f"{arm.arm} decision-call ledger changed before final replay")
    if (
        replay.get("frame_set_sha256") != arm.ledger_report.get("frame_set_sha256")
        or replay.get("report_sha256") != arm.ledger_report.get("report_sha256")
    ):
        raise ValueError(f"{arm.arm} decision-call ledger final replay mismatch")


def build_paired_measurement_readback(
    *,
    run_spec_path: str | Path,
    before_manifest_path: str | Path,
    after_manifest_path: str | Path,
) -> dict[str, Any]:
    """Build one deterministic, source-reconstructable paired cost report."""

    run_spec = _read_run_spec(run_spec_path)
    before = _read_arm(before_manifest_path, "BEFORE", run_spec)
    after = _read_arm(after_manifest_path, "AFTER", run_spec)
    if before.run_id == after.run_id:
        raise ValueError("BEFORE/AFTER must have separate fresh run IDs")
    if (
        before.input_ref["sha256"] != after.input_ref["sha256"]
        or before.input_ref["bytes"] != after.input_ref["bytes"]
        or before.input_ref["ordered_post_ids_sha256"]
        != after.input_ref["ordered_post_ids_sha256"]
    ):
        raise ValueError("BEFORE/AFTER input bytes or ordered post_id coverage mismatch")
    if before.publication_wal_ref != after.publication_wal_ref:
        raise ValueError("BEFORE/AFTER authoritative publication WAL mismatch")
    if before.wal_rows != after.wal_rows:
        raise ValueError("BEFORE/AFTER authoritative decision set mismatch")
    if before.ledger_path == after.ledger_path:
        raise ValueError("BEFORE/AFTER must use separate decision-call ledgers")
    if before.output_path == after.output_path:
        raise ValueError("BEFORE/AFTER must use separate output artifacts")

    before_rows = _ledger_row_map(before.ledger_report)
    after_rows = _ledger_row_map(after.ledger_report)
    if set(before_rows) != set(after_rows):
        raise ValueError("BEFORE/AFTER row coverage mismatch")
    all_coordinates = set(before_rows)
    reference_coordinates = {
        coordinate
        for coordinate, route in after.route_rows.items()
        if route["execution_class"] == REFERENCE_COPY_COST_ONLY
    }
    production_coordinates = all_coordinates - reference_coordinates
    if any(after_rows[coordinate]["expert_calls"] == 0 for coordinate in production_coordinates):
        raise ValueError("unexplained AFTER zero physical calls remain after route validation")

    production_before = _sum_metrics(before_rows, production_coordinates)
    production_after = _sum_metrics(after_rows, production_coordinates)
    reference_before = _sum_metrics(before_rows, reference_coordinates)
    reference_after = _sum_metrics(after_rows, reference_coordinates)
    production_status = (
        _PRODUCTION_COMPARABLE
        if production_coordinates
        else "NOT_ESTIMABLE_NO_PRODUCTION_INFERENCE_COMPARABLE_ROWS"
    )
    execution_policy = _read_execution_envelope_policy(
        run_spec.shared_measurement_fields
    )
    if execution_policy is None:
        before_execution_envelope = None
        after_execution_envelope = None
        execution_latency = {
            "value": None,
            "status": "NOT_ESTIMABLE_NO_EXECUTION_ENVELOPE_POLICY",
        }
    else:
        before_execution_envelope = _execution_envelope_for_arm(before, run_spec)
        after_execution_envelope = _execution_envelope_for_arm(after, run_spec)
        execution_latency = _paired_execution_latency(
            before=before_execution_envelope,
            after=after_execution_envelope,
            coordinates=production_coordinates,
            policy=execution_policy,
        )
    actual_metrics = {
        name: _metric_receipt(
            name,
            production_before[name],
            production_after[name],
            status=production_status,
        )
        for name in _METRIC_NAMES
    }
    reference_metrics = {
        name: _metric_receipt(
            name,
            reference_before[name],
            reference_after[name],
            status=REFERENCE_COPY_COST_ONLY,
        )
        for name in _METRIC_NAMES
    }

    row_receipts: list[dict[str, Any]] = []
    for coordinate in sorted(before_rows, key=lambda item: (item[0], str(item[1]))):
        before_row = before_rows[coordinate]
        after_row = after_rows[coordinate]
        if before_row.get("publication_decision_id") != after_row.get("publication_decision_id"):
            raise ValueError("BEFORE/AFTER publication decision link mismatch")
        route = after.route_rows[coordinate]
        metric_status = (
            REFERENCE_COPY_COST_ONLY
            if coordinate in reference_coordinates
            else _PRODUCTION_COMPARABLE
        )
        row_receipts.append(
            {
                "input_index": coordinate[0],
                "post_id": coordinate[1],
                "publication_decision_id": before_row["publication_decision_id"],
                "before_seal_frame_sha256": before_row["seal_frame_sha256"],
                "after_seal_frame_sha256": after_row["seal_frame_sha256"],
                "after_execution_class": route["execution_class"],
                "production_savings_kpi_eligible": route[
                    "production_savings_kpi_eligible"
                ],
                "selected_lane": route["selected_lane"],
                "route_decision_sha256": route["route_decision_sha256"],
                "execution_receipt_sha256": route["execution_receipt_sha256"],
                "comparison_receipt_sha256": route["comparison_receipt_sha256"],
                "metrics": {
                    name: _metric_receipt(
                        name,
                        before_row[name],
                        after_row[name],
                        status=metric_status,
                    )
                    for name in _METRIC_NAMES
                },
                "after_zero_physical_calls": after_row["expert_calls"] == 0,
            }
        )

    reference_count = len(reference_coordinates)
    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "status": "GO_COST_READBACK_ONLY_ACCURACY_NOT_ESTIMABLE",
        "run_spec_sha256": run_spec.value["run_spec_sha256"],
        "pair_id": run_spec.value["pair_id"],
        "publication_scope_id": run_spec.value["publication_scope_id"],
        "input_post_count": before.input_count,
        "sources": {
            "run_spec": run_spec.reference,
            "before_manifest": before.manifest_ref,
            "after_manifest": after.manifest_ref,
            "before_output": before.output_ref,
            "after_output": after.output_ref,
            "before_input": before.input_ref,
            "after_input": after.input_ref,
            "before_output_attempt_claim": before.attempt_claim_ref,
            "after_output_attempt_claim": after.attempt_claim_ref,
            "authoritative_publication_wal": before.publication_wal_ref,
            "before_ledger": {
                "path": str(before.ledger_path),
                "frame_set_sha256": before.ledger_report["frame_set_sha256"],
                "report_sha256": before.ledger_report["report_sha256"],
            },
            "after_ledger": {
                "path": str(after.ledger_path),
                "frame_set_sha256": after.ledger_report["frame_set_sha256"],
                "report_sha256": after.ledger_report["report_sha256"],
            },
            "before_recovery_witness": (
                None
                if before.recovery_witness is None
                else before.recovery_witness.reference
            ),
            "after_recovery_witness": (
                None
                if after.recovery_witness is None
                else after.recovery_witness.reference
            ),
            "before_recovery_sources": list(before.recovery_source_refs),
            "after_recovery_sources": list(after.recovery_source_refs),
            "before_execution_envelope": before_execution_envelope,
            "after_execution_envelope": after_execution_envelope,
        },
        "gates": {
            "run_spec_bytes_and_self_hash_bound": "GO",
            "input_bytes_and_order_bound": "GO",
            "fresh_before_independent_readback": "GO",
            "fresh_after_independent_readback": "GO",
            "same_runspec_pair_scope": "GO",
            "output_route_ledger_wal_binding": "GO",
            "ledger_final_replay_unchanged": "GO",
            "reference_copy_excluded_from_production_savings": "GO",
            "unexplained_zero_physical_calls": 0,
            "authoritative_publication_wal_unchanged": "GO",
            "public_decision_link_equivalence": "GO",
            "recovery_measurement_support": (
                "GO_EXACT_BOUND_WITNESS_REPLAY"
                if before.recovery_witness is not None
                or after.recovery_witness is not None
                else "AVAILABLE_EXACT_BOUND_WITNESS_REQUIRED"
            ),
            "frozen_actual_accuracy": "NOT_ESTIMABLE_NOT_BOUND_IN_THIS_REPORT",
            "end_to_end_latency": execution_latency["status"],
            "money_cost": "NOT_ESTIMABLE_NO_PRICE_SNAPSHOT",
            "semantic_quality": "REVIEW-LOCKED",
            "production_enable_allowed": False,
            "full_scan_approval": False,
        },
        "production_inference_comparable_row_count": len(production_coordinates),
        "actual_cost_metrics": actual_metrics,
        "non_cost_metrics": {
            "frozen_actual_accuracy": {
                "value": None,
                "status": "NOT_ESTIMABLE_NOT_BOUND_IN_THIS_REPORT",
            },
            "end_to_end_latency": {
                "value": execution_latency["value"],
                "status": execution_latency["status"],
                "execution_envelope": execution_latency,
            },
            "money_cost": {
                "value": None,
                "status": "NOT_ESTIMABLE_NO_PRICE_SNAPSHOT",
            },
        },
        "counterfactual_reference_copy_cost": {
            "classification": REFERENCE_COPY_COST_ONLY,
            "row_count": reference_count,
            "production_savings_kpi_eligible": False,
            "cost_metrics": reference_metrics,
            "meaning": (
                "authoritative WAL 결과를 복사해 provider 호출을 생략한 반사실 비용이며 "
                "실제 production inference 절감 KPI가 아니다."
            ),
        },
        "zero_physical_call_coverage": {
            "numerator": reference_count,
            "denominator": before.input_count,
            "value": reference_count / before.input_count,
            "percent": 100.0 * reference_count / before.input_count,
            "authorized_reference_copy_zero_call_count": reference_count,
            "unexplained_zero_call_count": 0,
            "classification": REFERENCE_COPY_COST_ONLY,
            "production_savings_kpi_eligible": False,
            "meaning": (
                "AFTER 0-call 행은 모두 authoritative reference copy로 검증됐으며 "
                "production inference 절감률에서 제외됐다."
            ),
        },
        "row_receipts": row_receipts,
        "limitations": [
            "REFERENCE_COPY_COST_ONLY 행은 counterfactual/reference-copy 비용이며 production 절감 KPI가 아니다.",
            "physical_call_wall_ms_sum은 모델 호출 누적 시간이며 배치 전체 지연이 아니다.",
            "E2E p50/p95는 실행 봉투에 결속된 full-expert 동일 행만 paired bootstrap으로 비교하며 reference-copy 행을 production 개선 수치에 섞지 않는다.",
            "FROZEN_ACTUAL 정확도와 그룹 신뢰구간은 이 비용 보고서에 아직 결속되지 않았다.",
            "가격표 출처, 시점, 통화가 없으므로 금액 비용은 계산하지 않는다.",
            "recovered arm은 self-hash와 모든 원천 바이트를 재생한 exact GO witness가 있을 때만 허용한다.",
            "비용 GO만으로 실제 라우팅이나 production 승인을 열지 않는다.",
        ],
    }
    report["report_sha256"] = _sha256(report)

    # Broaden the terminal stable recheck beyond the WAL.  A report is never
    # returned if any root source changed after it was first parsed.
    for reference, label in (
        (run_spec.reference, "paired RunSpec"),
        (before.manifest_ref, "BEFORE manifest"),
        (after.manifest_ref, "AFTER manifest"),
        (before.output_ref, "BEFORE output"),
        (after.output_ref, "AFTER output"),
        (before.input_ref, "BEFORE input"),
        (after.input_ref, "AFTER input"),
        (before.attempt_claim_ref, "BEFORE output attempt claim"),
        (after.attempt_claim_ref, "AFTER output attempt claim"),
        (before.publication_wal_ref, "authoritative publication WAL"),
    ):
        _assert_snapshot_unchanged(reference, label)
    for arm_name, arm_readback in (("BEFORE", before), ("AFTER", after)):
        for index, reference in enumerate(arm_readback.recovery_source_refs, 1):
            _assert_snapshot_unchanged(
                reference,
                f"{arm_name} recovery source {index}",
            )
    _assert_ledger_replay_unchanged(before)
    _assert_ledger_replay_unchanged(after)
    return report


def verify_paired_report_sha256(report: Mapping[str, Any]) -> bool:
    if not isinstance(report, Mapping):
        return False
    supplied = report.get("report_sha256")
    if not isinstance(supplied, str):
        return False
    return supplied == _sha256(
        {key: value for key, value in report.items() if key != "report_sha256"}
    )


def validate_paired_measurement_run_spec(path: str | Path) -> dict[str, Any]:
    """Validate persisted RunSpec bytes and return a detached JSON value."""

    return json.loads(json.dumps(_read_run_spec(path).value, ensure_ascii=False))


def validate_paired_measurement_readback(
    report: Mapping[str, Any],
    *,
    run_spec_path: str | Path,
    before_manifest_path: str | Path,
    after_manifest_path: str | Path,
) -> None:
    """Reject plain or self-rehashed forgery by replaying every source root."""

    if not verify_paired_report_sha256(report):
        raise ValueError("paired report self hash mismatch")
    try:
        rebuilt = build_paired_measurement_readback(
            run_spec_path=run_spec_path,
            before_manifest_path=before_manifest_path,
            after_manifest_path=after_manifest_path,
        )
    except (OSError, TypeError, ValueError) as error:
        raise ValueError(f"paired report source replay failed: {error}") from error
    if dict(report) != rebuilt:
        raise ValueError("paired report differs from independent source replay")


__all__ = [
    "RECOVERY_WITNESS_SCHEMA_VERSION",
    "REFERENCE_COPY_COST_ONLY",
    "RUN_SPEC_SCHEMA_VERSION",
    "SCHEMA_VERSION",
    "build_recovery_witness",
    "build_paired_measurement_run_spec",
    "build_paired_measurement_readback",
    "validate_paired_measurement_run_spec",
    "validate_paired_measurement_readback",
    "verify_paired_report_sha256",
]
