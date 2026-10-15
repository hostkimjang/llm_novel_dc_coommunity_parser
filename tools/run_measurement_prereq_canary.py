from __future__ import annotations

"""Run a one-row measurement prerequisite canary.

The canary copies exactly one row from a source JSONL into an isolated output
root, runs one normal publication owner, then one AFTER fresh semantic
observation.  It never enables recovery activation and never accepts
``--no-dashboard``; the source owner WAL is the sole authority for the
observation comparison.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.llm_batch.ledger.publication_commit import (  # noqa: E402
    validate_publication_result_commit,
)
from src.llm_batch.measurement.publication_shadow_observation import (  # noqa: E402
    validate_publication_shadow_observation,
)
from tools.run_recovery_sidecar_grouped_ab import (  # noqa: E402
    DEFAULT_ACTIVE_MANIFEST,
    DEFAULT_ENDPOINTS,
    _active_endpoint_protection,
    _base_env,
    _dashboard_health,
    _load_json,
    _manifest_path,
)


DEFAULT_INPUT = ROOT / (
    "out/regression_safe_2712_improvement_20260716/"
    "frozen_bundles_cap32/bundles/cross_family.jsonl"
)
DEFAULT_ROOT = ROOT / "out/measurement_prereq_canary"


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_sha256(value: Mapping[str, Any]) -> str:
    return _sha256_bytes(
        json.dumps(
            dict(value),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )


def _atomic_bytes(path: Path, payload: bytes) -> None:
    """Create an immutable artifact atomically, accepting an exact replay."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            if path.read_bytes() != payload:
                raise RuntimeError(f"existing immutable artifact differs: {path}")
        directory = os.open(str(path.parent), os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    _atomic_bytes(
        path,
        (json.dumps(dict(payload), ensure_ascii=False, indent=2) + "\n").encode(
            "utf-8"
        ),
    )


def _post_id_key(value: Any) -> str:
    if value is None or isinstance(value, bool):
        raise ValueError("post_id must be non-empty")
    key = str(value).strip()
    if not key:
        raise ValueError("post_id must be non-empty")
    return key


def _select_input_row(source_path: Path, post_id: str) -> tuple[dict[str, Any], bytes, str]:
    """Select exactly one source row and return its bytes for the canary input."""

    target = _post_id_key(post_id)
    matches: list[tuple[dict[str, Any], bytes, int]] = []
    raw = source_path.read_bytes()
    for line_number, raw_line in enumerate(raw.splitlines(keepends=True), 1):
        if not raw_line.strip():
            continue
        try:
            value = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid source JSONL row {line_number}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"source row {line_number} must be an object")
        if _post_id_key(value.get("post_id")) == target:
            matches.append((value, raw_line, line_number))
    if len(matches) != 1:
        raise ValueError(
            f"--post-id must select exactly one row: post_id={target!r}, matches={len(matches)}"
        )
    row, row_bytes, _ = matches[0]
    if not row_bytes.endswith((b"\n", b"\r")):
        row_bytes += b"\n"
    return row, row_bytes, _sha256_bytes(row_bytes)


def _write_selected_input(source_path: Path, output_root: Path, post_id: str) -> tuple[dict[str, Any], Path, str]:
    row, row_bytes, input_sha256 = _select_input_row(source_path, post_id)
    input_path = output_root / "input.jsonl"
    _atomic_bytes(input_path, row_bytes)
    return row, input_path, input_sha256


def _validate_source_manifest(
    manifest_path: Path,
    *,
    input_sha256: str,
    row_count: int,
    health_required_ok: int,
) -> dict[str, Any]:
    manifest = _load_json(manifest_path)
    required = {
        "input_post_count": row_count,
        "completed_count": row_count,
        "flushed_count": row_count,
        "pending_count": 0,
        "failed_count": 0,
        "requested_parallel": 16,
        "effective_parallel": min(row_count, 16),
        "dashboard_enabled": True,
        "terminal_artifacts_finalized": True,
        "publication_commit_count": row_count,
        "publication_execution_mode": "NORMAL_PUBLICATION_OWNER",
        "recovery_activation_requested_mode": "OFF",
        "large_run_complete": True,
    }
    mismatches = {
        key: {"expected": expected, "actual": manifest.get(key)}
        for key, expected in required.items()
        if manifest.get(key) != expected
    }
    if mismatches:
        raise RuntimeError(f"source manifest contract mismatch: {mismatches}")
    if manifest.get("publication_input_snapshot_sha256") != input_sha256:
        raise RuntimeError("source manifest input SHA mismatch")
    if manifest.get("mcp_health_include_search") is not True:
        raise RuntimeError("source manifest search health was not enabled")
    if manifest.get("mcp_health_light_mode") is not False:
        raise RuntimeError("source manifest used light health mode")
    if int(manifest.get("mcp_health_ok_count") or 0) < health_required_ok:
        raise RuntimeError("source manifest has too few healthy endpoints")
    if int(manifest.get("mcp_health_failure_count") or 0) != 0:
        raise RuntimeError("source manifest has endpoint health failures")
    if (manifest.get("runtime_completion_gate") or {}).get("status") != "GO":
        raise RuntimeError("source runtime completion gate is not GO")
    return manifest


def _validate_observation_manifest(
    manifest_path: Path,
    *,
    source: Mapping[str, Any],
    input_sha256: str,
    pair_id: str,
    run_spec_sha256: str,
    row_count: int,
) -> dict[str, Any]:
    manifest = _load_json(manifest_path)
    measurement = manifest.get("decision_call_measurement") or {}
    required = {
        "input_post_count": row_count,
        "completed_count": row_count,
        "flushed_count": row_count,
        "pending_count": 0,
        "failed_count": 0,
        "requested_parallel": 16,
        "effective_parallel": min(row_count, 16),
        "dashboard_enabled": True,
        "terminal_artifacts_finalized": True,
        "publication_commit_count": row_count,
        "publication_execution_mode": "FRESH_SHADOW_OBSERVATION_NO_PUBLIC_WRITE",
        "recovery_activation_requested_mode": "OFF",
        "recovery_activation_status": "SKIPPED_FRESH_MEASUREMENT",
    }
    mismatches = {
        key: {"expected": expected, "actual": manifest.get(key)}
        for key, expected in required.items()
        if manifest.get(key) != expected
    }
    if mismatches:
        raise RuntimeError(f"observation manifest contract mismatch: {mismatches}")
    if manifest.get("publication_input_snapshot_sha256") != input_sha256:
        raise RuntimeError("observation input SHA mismatch")
    for field in (
        "publication_scope_id",
        "publication_config_sha256",
        "publication_decision_environment_sha256",
        "publication_release_fingerprint",
    ):
        if manifest.get(field) != source.get(field):
            raise RuntimeError(f"observation source binding mismatch: {field}")
    expected_measurement = {
        "mode": "REQUIRED",
        "pair_id": pair_id,
        "arm": "AFTER",
        "run_spec_sha256": run_spec_sha256,
        "execution_mode": "FRESH_SEMANTIC_OBSERVATION_REQUIRED",
        "fresh_execution_required": True,
        "semantic_drift_observation": True,
        "publication_decision_equivalence_required": False,
        "mutable_context_mode": "FROZEN_OFF",
        "early_route_mode": "OFF",
    }
    for key, expected in expected_measurement.items():
        if measurement.get(key) != expected:
            raise RuntimeError(
                f"observation measurement mismatch {key}: "
                f"expected={expected!r} actual={measurement.get(key)!r}"
            )
    if (manifest.get("runtime_completion_gate") or {}).get("status") != "GO":
        raise RuntimeError("observation runtime completion gate is not GO")
    measurement_status = (manifest.get("measurement_gate") or {}).get("status")
    if measurement_status not in {"GO", "NO_GO"}:
        raise RuntimeError("observation measurement gate is not terminal")
    if manifest.get("large_run_complete") is not (measurement_status == "GO"):
        raise RuntimeError("large_run_complete does not reflect measurement gate")
    observation = manifest.get("publication_shadow_observation") or {}
    if observation.get("status") != "GO" or observation.get(
        "observed_observation_count"
    ) != row_count:
        raise RuntimeError("observation receipt coverage is not GO")
    noninterference = manifest.get("publication_noninterference_gate") or {}
    if noninterference.get("status") != "GO":
        raise RuntimeError("publication noninterference gate is not GO")
    if noninterference.get("public_write_allowed") is not False:
        raise RuntimeError("observation public writes were not forbidden")
    if noninterference.get("start_wal_sha256") != noninterference.get(
        "current_wal_sha256"
    ):
        raise RuntimeError("observation changed the publication WAL")
    if noninterference.get("start_wal_event_count") != noninterference.get(
        "current_wal_event_count"
    ):
        raise RuntimeError("observation changed the publication WAL event count")
    return manifest


def _validate_observation_checkpoint(
    checkpoint_path: Path,
    *,
    source: Mapping[str, Any],
    post_id: str,
) -> dict[str, Any]:
    rows = [
        json.loads(line)
        for line in checkpoint_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if len(rows) != 1:
        raise RuntimeError(f"observation checkpoint must contain one row: {len(rows)}")
    row = rows[0]
    coordinate = (int(row["global_idx"]), _post_id_key(row["post_id"]))
    if coordinate != (1, post_id):
        raise RuntimeError(f"observation checkpoint coordinate mismatch: {coordinate}")
    source_wal = Path(str(source["publication_commit_journal"]))
    authority: dict[str, Any] | None = None
    for line in source_wal.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        frame = json.loads(line)
        receipt = frame.get("receipt") if isinstance(frame, dict) else None
        if isinstance(receipt, dict) and int(receipt.get("input_index")) == 1 and _post_id_key(receipt.get("post_id")) == post_id:
            authority = receipt
    if authority is None:
        raise RuntimeError("authoritative WAL row is missing")
    observed = validate_publication_result_commit(
        row["result"], row["publication_commit"], expected_input_index=1, expected_post_id=row["post_id"]
    )
    run_meta = row["result"].get("run_meta") or {}
    observation = validate_publication_shadow_observation(
        run_meta.get("publication_shadow_observation")
    )
    attempt = run_meta.get("decision_call_attempt_receipt") or {}
    if observed.decision_id != observation["observed_decision"]["decision_id"]:
        raise RuntimeError("checkpoint decision differs from observation")
    if attempt.get("publication_decision_id_preview") != observed.decision_id:
        raise RuntimeError("attempt preview differs from observation")
    if observation["authoritative_decision"]["decision_id"] != authority["decision_id"]:
        raise RuntimeError("observation authority differs from public WAL")
    link_status = str(attempt.get("publication_link_status") or "")
    if link_status == "LINKED_EXTERNAL_LEDGER":
        if attempt.get("publication_link_decision_id") != authority["decision_id"]:
            raise RuntimeError("linked attempt differs from public WAL authority")
        linked, unlinked = 1, 0
    elif link_status == "NOT_LINKABLE_WRITER_INCOMPLETE":
        if attempt.get("publication_link_decision_id") is not None:
            raise RuntimeError("incomplete writer unexpectedly carries a link ID")
        linked, unlinked = 0, 1
    else:
        raise RuntimeError(f"unexpected terminal link status: {link_status}")
    comparison = observation["comparison"]
    return {
        "schema_version": "publication_shadow_checkpoint_validation_v1",
        "status": "GO",
        "expected_row_count": 1,
        "validated_row_count": 1,
        "linked_call_measurement_count": linked,
        "unlinked_call_measurement_count": unlinked,
        "call_measurement_status": "GO" if unlinked == 0 else "NO_GO",
        "public_projection_drift_count": int(comparison["public_projection_equal"] is False),
        "outcome_drift_count": int(comparison["outcome_equal"] is False),
    }


def _command(*, python: Path, input_path: Path, output_path: Path, llm_endpoint: str, llm_model: str) -> list[str]:
    return [
        str(python), str(ROOT / "expert_main.py"), str(input_path), "--output", str(output_path),
        "--parallel", "16", "--server-type", "vllm", "--llm-endpoint", llm_endpoint,
        "--llm-model", llm_model, "--vlm", "on", "--ocr", "on",
        "--require-vlm-ocr-for-images", "--slang-db", "off", "--reuse-shards-only",
        "--no-auto-up-shards", "--no-auto-recreate-shards", "--llm-suspend-on-anomaly", "off",
    ]


def _run_once(command: list[str], *, env: Mapping[str, str], output_path: Path) -> None:
    manifest_path = _manifest_path(output_path)
    if output_path.exists() or manifest_path.exists():
        if output_path.is_file() and manifest_path.is_file():
            return
        raise RuntimeError(f"partial existing attempt artifacts: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(command, cwd=ROOT, env=dict(env), check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"expert_main failed with exit={completed.returncode}: {output_path}")


def _parse_endpoints(value: str | None) -> tuple[str, ...]:
    if not value:
        return DEFAULT_ENDPOINTS
    endpoints = tuple(item.strip().rstrip("/") for item in value.split(",") if item.strip())
    if not endpoints or len(set(endpoints)) != len(endpoints):
        raise ValueError("endpoints must be a non-empty unique comma-separated list")
    return endpoints


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="one-row measurement prerequisite canary")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--post-id", required=True)
    parser.add_argument("--output-root", default=str(DEFAULT_ROOT))
    parser.add_argument("--active-manifest", default=str(DEFAULT_ACTIVE_MANIFEST))
    parser.add_argument("--dashboard-url", default="http://127.0.0.1:8093")
    parser.add_argument("--dashboard-port", type=int, default=8093)
    parser.add_argument("--endpoints", default=None)
    parser.add_argument("--llm-endpoint", default="http://10.20.0.101:8000/")
    parser.add_argument("--llm-model", default="nvidia/Gemma-4-26B-A4B-NVFP4")
    parser.add_argument("--python", default=str(ROOT / "venv/bin/python"))
    return parser


def main() -> None:
    args = _parser().parse_args()
    input_path = Path(args.input).resolve()
    output_root = Path(args.output_root).resolve()
    active_manifest = Path(args.active_manifest).resolve()
    python = Path(os.path.abspath(args.python))
    endpoints = _parse_endpoints(args.endpoints)
    row, canary_input, input_sha256 = _write_selected_input(input_path, output_root, args.post_id)
    post_id = _post_id_key(row.get("post_id"))
    _active_endpoint_protection(active_manifest, endpoints)
    dashboard_health = _dashboard_health(args.dashboard_url)
    base_env = _base_env(
        endpoints=endpoints,
        dashboard_url=args.dashboard_url,
        dashboard_port=args.dashboard_port,
        llm_endpoint=args.llm_endpoint,
        llm_model=args.llm_model,
    )
    source_output = output_root / "source_owner.json"
    source_env = dict(base_env)
    source_env["RECOVERY_ACTIVATION_MODE"] = "OFF"
    source_command = _command(
        python=python, input_path=canary_input, output_path=source_output,
        llm_endpoint=args.llm_endpoint, llm_model=args.llm_model,
    )
    _run_once(source_command, env=source_env, output_path=source_output)
    source_manifest_path = _manifest_path(source_output)
    source = _validate_source_manifest(
        source_manifest_path, input_sha256=input_sha256, row_count=1,
        health_required_ok=min(16, len(endpoints)),
    )

    pair_id = f"measurement-prereq-{post_id}"
    pair_material = {
        "schema_version": "measurement_prereq_canary_pair_v1",
        "pair_id": pair_id,
        "input_sha256": input_sha256,
        "post_id": row["post_id"],
        "publication_scope_id": source["publication_scope_id"],
        "publication_release_fingerprint": source["publication_release_fingerprint"],
        "publication_config_sha256": source["publication_config_sha256"],
        "decision_environment_sha256": source["publication_decision_environment_sha256"],
        "execution_mode": "FRESH_SEMANTIC_OBSERVATION_REQUIRED",
        "mutable_context_mode": "FROZEN_OFF",
        "early_route_mode": "OFF",
        "requested_parallel": 16,
        "effective_parallel": 1,
    }
    pair_spec = {**pair_material, "run_spec_sha256": _canonical_sha256(pair_material)}
    _atomic_json(output_root / "run_spec.json", pair_spec)

    observed_output = output_root / "observed_after.json"
    observed_env = dict(base_env)
    observed_env.update(
        {
            "PIPELINE_DECISION_CALL_LEDGER_MODE": "REQUIRED",
            "PIPELINE_MEASUREMENT_RUN_SPEC_SHA256": pair_spec["run_spec_sha256"],
            "PIPELINE_MEASUREMENT_PAIR_ID": pair_id,
            "PIPELINE_MEASUREMENT_ARM": "AFTER",
            "PIPELINE_MEASUREMENT_EXECUTION_MODE": "FRESH_SEMANTIC_OBSERVATION_REQUIRED",
            "PIPELINE_MEASUREMENT_MUTABLE_CONTEXT_MODE": "FROZEN_OFF",
            "PIPELINE_MEASUREMENT_EARLY_ROUTE_MODE": "OFF",
            "RECOVERY_ACTIVATION_MODE": "OFF",
        }
    )
    observed_command = _command(
        python=python, input_path=canary_input, output_path=observed_output,
        llm_endpoint=args.llm_endpoint, llm_model=args.llm_model,
    )
    _run_once(observed_command, env=observed_env, output_path=observed_output)
    observed_manifest_path = _manifest_path(observed_output)
    observed = _validate_observation_manifest(
        observed_manifest_path, source=source, input_sha256=input_sha256,
        pair_id=pair_id, run_spec_sha256=pair_spec["run_spec_sha256"], row_count=1,
    )
    checkpoint = _validate_observation_checkpoint(
        observed_output.with_name(f"{observed_output.stem}_checkpoint.jsonl"),
        source=source, post_id=post_id,
    )
    measurement_gate = observed.get("measurement_gate") or {}
    ledger_summary = observed.get("decision_call_ledger_summary") or {}
    measurement = observed.get("decision_call_measurement") or {}
    reasons = sorted({
        str(reason)
        for source_value in (measurement_gate.get("reason_codes", []), ledger_summary.get("reason_codes", []))
        if isinstance(source_value, list)
        for reason in source_value
    })
    release = {
        "source": source.get("publication_release_fingerprint"),
        "observed": observed.get("publication_release_fingerprint"),
        "match": source.get("publication_release_fingerprint") == observed.get("publication_release_fingerprint"),
    }
    noninterference = observed.get("publication_noninterference_gate") or {}
    measurement_ok = (
        measurement_gate.get("status") == "GO"
        and checkpoint.get("call_measurement_status") == "GO"
    )
    summary = {
        "schema_version": "measurement_prereq_canary_summary_v1",
        "status": "GO" if measurement_ok else "NO_GO",
        "input": {"source": str(input_path), "canary": str(canary_input), "post_id": row["post_id"], "row_count": 1, "sha256": input_sha256},
        "source_manifest": str(source_manifest_path),
        "observed_manifest": str(observed_manifest_path),
        "source_execution_mode": source.get("publication_execution_mode"),
        "source_recovery_activation_mode": source.get("recovery_activation_requested_mode"),
        "observed_execution_mode": observed.get("publication_execution_mode"),
        "observed_recovery_activation_mode": observed.get("recovery_activation_requested_mode"),
        "observed_measurement": {
            key: measurement.get(key)
            for key in (
                "mode", "arm", "execution_mode", "mutable_context_mode",
                "early_route_mode", "fresh_execution_required",
            )
        },
        "source_runtime_gate": (source.get("runtime_completion_gate") or {}).get("status"),
        "observed_runtime_gate": (observed.get("runtime_completion_gate") or {}).get("status"),
        "measurement_gate": measurement_gate.get("status"),
        "measurement_reason_codes": reasons,
        "linked_call_measurement_count": checkpoint["linked_call_measurement_count"],
        "unlinked_call_measurement_count": checkpoint["unlinked_call_measurement_count"],
        "ledger_summary": {"ledger_status": ledger_summary.get("ledger_status"), "actual_kpi_status": ledger_summary.get("actual_kpi_status"), "linked": checkpoint["linked_call_measurement_count"], "unlinked": checkpoint["unlinked_call_measurement_count"], "row_attempt_count": ledger_summary.get("row_attempt_count"), "sealed_row_attempt_count": ledger_summary.get("sealed_row_attempt_count"), "linked_row_attempt_count": ledger_summary.get("linked_row_attempt_count")},
        "checkpoint_validation": checkpoint,
        "release_fingerprint": release,
        "dashboard": {"url": args.dashboard_url.rstrip("/"), "enabled": observed.get("dashboard_enabled") is True, "health": dashboard_health},
        "publication_noninterference_gate": noninterference.get("status"),
        "public_wal_unchanged": bool(
            noninterference.get("status") == "GO"
            and noninterference.get("public_write_allowed") is False
            and noninterference.get("start_wal_sha256") == noninterference.get("current_wal_sha256")
            and noninterference.get("start_wal_event_count") == noninterference.get("current_wal_event_count")
        ),
        "public_apply": False,
        "production_enable_allowed": False,
        "full_scan_approval": False,
    }
    _atomic_json(output_root / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
