from __future__ import annotations

"""Run a frozen grouped semantic-observation series without public WAL writes.

The script performs one normal owner run to establish an immutable public
reference, then three BEFORE/OFF and three AFTER/AUDIT_ONLY fresh observations.
Observation runs require the existing WAL, call the provider again, tolerate
semantic variance, and prove that the reference WAL bytes did not change.
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
DEFAULT_INPUT = ROOT / (
    "out/regression_safe_2712_improvement_20260716/"
    "frozen_bundles_cap32/bundles/cross_family.jsonl"
)
DEFAULT_ROOT = ROOT / (
    "out/regression_safe_2712_improvement_20260717/"
    "fresh_cross_family_recovery_sidecar_ab_v2"
)
DEFAULT_ACTIVE_MANIFEST = ROOT / "out/expert_result_20260715_143806_848671_manifest.json"
DEFAULT_ENDPOINTS = tuple(f"http://127.0.0.1:{port}" for port in range(3349, 3365))


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


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(dict(payload), handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory = os.open(str(path.parent), os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temporary.unlink(missing_ok=True)


def _exclusive_or_exact_json(path: Path, payload: Mapping[str, Any]) -> None:
    encoded = (json.dumps(dict(payload), ensure_ascii=False, indent=2) + "\n").encode(
        "utf-8"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError:
        if path.read_bytes() != encoded:
            raise RuntimeError(f"existing immutable spec differs: {path}")
        return
    try:
        remaining = memoryview(encoded)
        while remaining:
            written = os.write(descriptor, remaining)
            if written <= 0:
                raise OSError("exclusive spec write made no progress")
            remaining = remaining[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _read_input(path: Path) -> tuple[list[Any], str]:
    raw = path.read_bytes()
    post_ids: list[Any] = []
    for line_number, raw_line in enumerate(raw.splitlines(), 1):
        if not raw_line.strip():
            continue
        value = json.loads(raw_line)
        if not isinstance(value, dict) or value.get("post_id") is None:
            raise ValueError(f"invalid input row {line_number}")
        post_ids.append(value["post_id"])
    if len(post_ids) != 32 or len({str(value) for value in post_ids}) != 32:
        raise ValueError("grouped input must contain exactly 32 unique post_id rows")
    return post_ids, _sha256_bytes(raw)


def _manifest_path(output_path: Path) -> Path:
    return output_path.with_name(f"{output_path.stem}_manifest.json")


def _active_endpoint_protection(active_manifest: Path, selected: tuple[str, ...]) -> None:
    manifest = _load_json(active_manifest)
    protected = {
        value.strip()
        for value in str(manifest.get("mcp_endpoints") or "").split(",")
        if value.strip()
    }
    overlap = sorted(protected.intersection(selected))
    if overlap:
        raise RuntimeError(f"selected endpoints overlap protected active run: {overlap}")
    if str(manifest.get("run_id") or "") != "20260715_143806_848671":
        raise RuntimeError("protected manifest run_id changed")


def _dashboard_health(url: str) -> dict[str, Any]:
    with urlopen(f"{url.rstrip('/')}/api/health", timeout=3.0) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict) or payload.get("standalone") is not True:
        raise RuntimeError("standalone dashboard is not healthy")
    return payload


def _validate_source_manifest(
    manifest_path: Path,
    *,
    input_sha256: str,
    post_ids: list[Any],
) -> dict[str, Any]:
    manifest = _load_json(manifest_path)
    required = {
        "input_post_count": len(post_ids),
        "completed_count": len(post_ids),
        "flushed_count": len(post_ids),
        "pending_count": 0,
        "failed_count": 0,
        "requested_parallel": 16,
        "effective_parallel": min(len(post_ids), 16),
        "dashboard_enabled": True,
        "terminal_artifacts_finalized": True,
        "publication_commit_count": len(post_ids),
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
    if int(manifest.get("mcp_health_ok_count") or 0) < 16:
        raise RuntimeError("source manifest has fewer than 16 healthy endpoints")
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
    requested_mode: str,
    pair_id: str,
    run_spec_sha256: str,
    arm: str,
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
        "recovery_activation_requested_mode": requested_mode,
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
        "arm": arm,
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
        raise RuntimeError(
            "large_run_complete does not reflect the terminal measurement gate"
        )
    observation = manifest.get("publication_shadow_observation") or {}
    if observation.get("status") != "GO" or observation.get(
        "observed_observation_count"
    ) != row_count:
        raise RuntimeError("observation receipt coverage is not GO")
    if (manifest.get("publication_noninterference_gate") or {}).get("status") != "GO":
        raise RuntimeError("publication noninterference gate is not GO")
    return manifest


def _validate_observation_checkpoint(
    checkpoint_path: Path,
    *,
    source: Mapping[str, Any],
    ordered_post_ids: list[Any],
) -> dict[str, Any]:
    rows = [
        json.loads(line)
        for line in checkpoint_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    expected = {
        (index, str(post_id))
        for index, post_id in enumerate(ordered_post_ids, 1)
    }
    observed: set[tuple[int, str]] = set()
    linked = 0
    unlinked = 0
    public_projection_drift = 0
    outcome_drift = 0
    authority_by_coordinate: dict[tuple[int, str], str] = {}
    wal_path = Path(str(source["publication_commit_journal"]))
    for line in wal_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        frame = json.loads(line)
        receipt = frame.get("receipt") if isinstance(frame, dict) else None
        if not isinstance(receipt, dict):
            raise RuntimeError("authoritative WAL frame is invalid")
        coordinate = (int(receipt["input_index"]), str(receipt["post_id"]))
        authority_by_coordinate[coordinate] = str(receipt["decision_id"])
    if set(authority_by_coordinate) != expected:
        raise RuntimeError("authoritative WAL coordinates differ from frozen input")

    for row in rows:
        coordinate = (int(row["global_idx"]), str(row["post_id"]))
        if coordinate in observed:
            raise RuntimeError(f"duplicate checkpoint coordinate: {coordinate}")
        observed.add(coordinate)
        receipt = validate_publication_result_commit(
            row["result"], row["publication_commit"]
        )
        run_meta = row["result"].get("run_meta") or {}
        observation = validate_publication_shadow_observation(
            run_meta.get("publication_shadow_observation")
        )
        attempt = run_meta.get("decision_call_attempt_receipt") or {}
        if observation["input_index"] != coordinate[0] or str(
            observation["post_id"]
        ) != coordinate[1]:
            raise RuntimeError("observation checkpoint coordinate mismatch")
        if receipt.decision_id != observation["observed_decision"]["decision_id"]:
            raise RuntimeError("checkpoint decision differs from observed decision")
        if (
            attempt.get("publication_decision_id_preview")
            != observation["observed_decision"]["decision_id"]
        ):
            raise RuntimeError("attempt preview differs from observed decision")
        authority_id = authority_by_coordinate[coordinate]
        if observation["authoritative_decision"]["decision_id"] != authority_id:
            raise RuntimeError("observation authority differs from public WAL")
        link_status = str(attempt.get("publication_link_status") or "")
        if link_status == "LINKED_EXTERNAL_LEDGER":
            if attempt.get("publication_link_decision_id") != authority_id:
                raise RuntimeError("linked attempt differs from public WAL authority")
            linked += 1
        elif link_status == "NOT_LINKABLE_WRITER_INCOMPLETE":
            if attempt.get("publication_link_decision_id") is not None:
                raise RuntimeError("incomplete writer unexpectedly carries a link ID")
            unlinked += 1
        else:
            raise RuntimeError(f"unexpected terminal link status: {link_status}")
        comparison = observation["comparison"]
        public_projection_drift += int(
            comparison["public_projection_equal"] is False
        )
        outcome_drift += int(comparison["outcome_equal"] is False)
    if observed != expected:
        raise RuntimeError("checkpoint observation coverage differs from frozen input")
    return {
        "schema_version": "publication_shadow_checkpoint_validation_v1",
        "status": "GO",
        "expected_row_count": len(expected),
        "validated_row_count": len(observed),
        "linked_call_measurement_count": linked,
        "unlinked_call_measurement_count": unlinked,
        "call_measurement_status": "GO" if unlinked == 0 else "NO_GO",
        "public_projection_drift_count": public_projection_drift,
        "outcome_drift_count": outcome_drift,
    }


def _base_env(
    *,
    endpoints: tuple[str, ...],
    dashboard_url: str,
    dashboard_port: int,
    llm_endpoint: str,
    llm_model: str,
) -> dict[str, str]:
    env = dict(os.environ)
    env.update(
        {
            "MCP_ENDPOINTS": ",".join(endpoints),
            "MCP_ENDPOINTS_AUTOGEN": "0",
            "MCP_AUTO_SCALE_UP_MISSING_SHARDS": "0",
            "MCP_CLIENT_ENDPOINT_FAILOVER": "0",
            "MCP_HEALTH_INCLUDE_SEARCH": "1",
            "MCP_HEALTH_LIGHT_MODE": "0",
            "MCP_HEALTH_REQUIRED_OK": "16",
            "MCP_HEALTH_PROBE_BATCH_SIZE": "16",
            "MCP_HEALTH_WORKERS": "16",
            "MCP_HEALTH_SEARCH_QUERY": "웹소설",
            "MCP_HEALTH_SEARCH_MIN_RESULTS": "1",
            "MCP_HEALTH_SEARCH_MAX_LATENCY_MS": "8000",
            "DASHBOARD_URL": dashboard_url.rstrip("/"),
            "DASHBOARD_PORT": str(dashboard_port),
            "EXPERT_DASHBOARD_FORWARD": "1",
            "LLM_ENDPOINT": llm_endpoint,
            "LLM_MODEL": llm_model,
            "PIPELINE_SLANG_DB": "0",
            "PIPELINE_MEASUREMENT_EARLY_ROUTE_MODE": "OFF",
        }
    )
    for key in (
        "PIPELINE_DECISION_CALL_LEDGER_MODE",
        "PIPELINE_MEASUREMENT_RUN_SPEC_SHA256",
        "PIPELINE_MEASUREMENT_PAIR_ID",
        "PIPELINE_MEASUREMENT_ARM",
        "PIPELINE_MEASUREMENT_EXECUTION_MODE",
        "PIPELINE_MEASUREMENT_MUTABLE_CONTEXT_MODE",
        "RECOVERY_ACTIVATION_MODE",
    ):
        env.pop(key, None)
    return env


def _command(
    *,
    python: Path,
    input_path: Path,
    output_path: Path,
    llm_endpoint: str,
    llm_model: str,
) -> list[str]:
    return [
        str(python),
        str(ROOT / "expert_main.py"),
        str(input_path),
        "--output",
        str(output_path),
        "--parallel",
        "16",
        "--server-type",
        "vllm",
        "--llm-endpoint",
        llm_endpoint,
        "--llm-model",
        llm_model,
        "--vlm",
        "on",
        "--ocr",
        "on",
        "--require-vlm-ocr-for-images",
        "--slang-db",
        "off",
        "--reuse-shards-only",
        "--no-auto-up-shards",
        "--no-auto-recreate-shards",
        "--llm-suspend-on-anomaly",
        "off",
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
        raise RuntimeError(
            f"expert_main failed with exit={completed.returncode}: {output_path}"
        )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="32행 recovery sidecar BEFORE/OFF↔AFTER/AUDIT_ONLY 반복 관측"
    )
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output-root", default=str(DEFAULT_ROOT))
    parser.add_argument("--active-manifest", default=str(DEFAULT_ACTIVE_MANIFEST))
    parser.add_argument("--repeat-count", type=int, default=3)
    parser.add_argument("--dashboard-url", default="http://127.0.0.1:8093")
    parser.add_argument("--dashboard-port", type=int, default=8093)
    parser.add_argument("--llm-endpoint", default="http://10.20.0.101:8000/")
    parser.add_argument(
        "--llm-model", default="unsloth/gemma-4-26B-A4B-it-NVFP4"
    )
    parser.add_argument("--python", default=str(ROOT / "venv/bin/python"))
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.repeat_count != 3:
        raise SystemExit("repeat-count must be exactly 3 for this frozen series")
    input_path = Path(args.input).resolve()
    output_root = Path(args.output_root).resolve()
    active_manifest = Path(args.active_manifest).resolve()
    # Keep the virtualenv launcher path itself. ``Path.resolve()`` follows the
    # symlink to the base interpreter and drops the venv site-packages context.
    python = Path(os.path.abspath(args.python))
    post_ids, input_sha256 = _read_input(input_path)
    endpoints = DEFAULT_ENDPOINTS
    _active_endpoint_protection(active_manifest, endpoints)
    dashboard_health = _dashboard_health(args.dashboard_url)
    base_env = _base_env(
        endpoints=endpoints,
        dashboard_url=args.dashboard_url,
        dashboard_port=args.dashboard_port,
        llm_endpoint=args.llm_endpoint,
        llm_model=args.llm_model,
    )
    common_command = _command(
        python=python,
        input_path=input_path,
        output_path=output_root / "source_owner.json",
        llm_endpoint=args.llm_endpoint,
        llm_model=args.llm_model,
    )
    source_output = output_root / "source_owner.json"
    source_env = dict(base_env)
    source_env["RECOVERY_ACTIVATION_MODE"] = "OFF"
    _run_once(common_command, env=source_env, output_path=source_output)
    source_manifest_path = _manifest_path(source_output)
    source = _validate_source_manifest(
        source_manifest_path,
        input_sha256=input_sha256,
        post_ids=post_ids,
    )

    series_material = {
        "schema_version": "recovery_sidecar_semantic_observation_series_v1",
        "series_id": "cross-family-recovery-sidecar-ab-v1",
        "repeat_count": 3,
        "input_path": str(input_path),
        "input_sha256": input_sha256,
        "ordered_post_ids": post_ids,
        "source_manifest": str(source_manifest_path),
        "source_publication_scope_id": source["publication_scope_id"],
        "source_publication_release_fingerprint": source[
            "publication_release_fingerprint"
        ],
        "source_publication_config_sha256": source["publication_config_sha256"],
        "source_decision_environment_sha256": source[
            "publication_decision_environment_sha256"
        ],
        "requested_parallel": 16,
        "effective_parallel": 16,
        "dashboard_url": args.dashboard_url.rstrip("/"),
        "dashboard_standalone": dashboard_health.get("standalone"),
        "mcp_endpoints": list(endpoints),
        "mcp_endpoints_sha256": _sha256_bytes(",".join(endpoints).encode("utf-8")),
        "search_health_policy": {
            "include_search": True,
            "light_mode": False,
            "required_ok": 16,
            "query": "웹소설",
            "min_results": 1,
            "max_latency_ms": 8000,
        },
        "measurement_execution_mode": "FRESH_SEMANTIC_OBSERVATION_REQUIRED",
        "arms": {
            "BEFORE": {"recovery_activation_mode": "OFF"},
            "AFTER": {"recovery_activation_mode": "AUDIT_ONLY"},
        },
        "approval_boundary": {
            "public_apply": False,
            "production_enable_allowed": False,
            "full_scan_approval": False,
            "semantic_approval": "REVIEW_LOCKED",
        },
    }
    series_spec = {
        **series_material,
        "series_spec_sha256": _canonical_sha256(series_material),
    }
    _exclusive_or_exact_json(output_root / "series_spec.json", series_spec)

    attempts: list[dict[str, Any]] = []
    for repeat_index in range(1, 4):
        pair_id = f"cross-family-sidecar-r{repeat_index}"
        pair_material = {
            "schema_version": "recovery_sidecar_semantic_observation_pair_v1",
            "series_spec_sha256": series_spec["series_spec_sha256"],
            "pair_id": pair_id,
            "repeat_index": repeat_index,
            "repeat_count": 3,
            "input_sha256": input_sha256,
            "publication_scope_id": source["publication_scope_id"],
            "publication_release_fingerprint": source[
                "publication_release_fingerprint"
            ],
            "publication_config_sha256": source["publication_config_sha256"],
            "decision_environment_sha256": source[
                "publication_decision_environment_sha256"
            ],
            "execution_mode": "FRESH_SEMANTIC_OBSERVATION_REQUIRED",
            "mutable_context_mode": "FROZEN_OFF",
            "early_route_mode": "OFF",
        }
        pair_spec = {
            **pair_material,
            "run_spec_sha256": _canonical_sha256(pair_material),
        }
        pair_dir = output_root / f"repeat_{repeat_index}"
        pair_spec_path = pair_dir / "run_spec.json"
        _exclusive_or_exact_json(pair_spec_path, pair_spec)
        for arm, recovery_mode in (("BEFORE", "OFF"), ("AFTER", "AUDIT_ONLY")):
            output_path = pair_dir / f"{arm.lower()}.json"
            env = dict(base_env)
            env.update(
                {
                    "PIPELINE_DECISION_CALL_LEDGER_MODE": "REQUIRED",
                    "PIPELINE_MEASUREMENT_RUN_SPEC_SHA256": pair_spec[
                        "run_spec_sha256"
                    ],
                    "PIPELINE_MEASUREMENT_PAIR_ID": pair_id,
                    "PIPELINE_MEASUREMENT_ARM": arm,
                    "PIPELINE_MEASUREMENT_EXECUTION_MODE": (
                        "FRESH_SEMANTIC_OBSERVATION_REQUIRED"
                    ),
                    "PIPELINE_MEASUREMENT_MUTABLE_CONTEXT_MODE": "FROZEN_OFF",
                    "PIPELINE_MEASUREMENT_EARLY_ROUTE_MODE": "OFF",
                    "RECOVERY_ACTIVATION_MODE": recovery_mode,
                }
            )
            command = _command(
                python=python,
                input_path=input_path,
                output_path=output_path,
                llm_endpoint=args.llm_endpoint,
                llm_model=args.llm_model,
            )
            _run_once(command, env=env, output_path=output_path)
            manifest_path = _manifest_path(output_path)
            manifest = _validate_observation_manifest(
                manifest_path,
                source=source,
                input_sha256=input_sha256,
                requested_mode=recovery_mode,
                pair_id=pair_id,
                run_spec_sha256=pair_spec["run_spec_sha256"],
                arm=arm,
                row_count=len(post_ids),
            )
            checkpoint_validation = _validate_observation_checkpoint(
                output_path.with_name(f"{output_path.stem}_checkpoint.jsonl"),
                source=source,
                ordered_post_ids=post_ids,
            )
            attempts.append(
                {
                    "repeat_index": repeat_index,
                    "arm": arm,
                    "output": str(output_path),
                    "manifest": str(manifest_path),
                    "run_id": manifest.get("run_id"),
                    "runtime_gate": manifest["runtime_completion_gate"]["status"],
                    "measurement_gate": manifest["measurement_gate"]["status"],
                    "measurement_reason_codes": manifest["measurement_gate"][
                        "reason_codes"
                    ],
                    "noninterference_gate": manifest[
                        "publication_noninterference_gate"
                    ]["status"],
                    "checkpoint_validation": checkpoint_validation,
                    "decision_drift_count": manifest[
                        "publication_shadow_observation"
                    ]["drift_counts"]["decision_id"],
                }
            )
            _atomic_json(
                output_root / "series_progress.json",
                {
                    "schema_version": "recovery_sidecar_series_progress_v1",
                    "series_spec_sha256": series_spec["series_spec_sha256"],
                    "source_manifest": str(source_manifest_path),
                    "completed_attempts": attempts,
                    "status": "RUNNING",
                },
            )

    measurement_all_go = all(
        attempt["measurement_gate"] == "GO" for attempt in attempts
    )
    summary = {
        "schema_version": "recovery_sidecar_grouped_ab_run_summary_v1",
        "status": (
            "GO_RUNTIME_OBSERVATION_COMPLETE"
            if measurement_all_go
            else "NO_GO_CALL_MEASUREMENT_OBSERVATION_COMPLETE"
        ),
        "series_spec_sha256": series_spec["series_spec_sha256"],
        "input_count": len(post_ids),
        "repeat_count_per_arm": 3,
        "source_manifest": str(source_manifest_path),
        "attempts": attempts,
        "call_measurement_gate": "GO" if measurement_all_go else "NO_GO",
        "public_apply": False,
        "production_enable_allowed": False,
        "full_scan_approval": False,
    }
    _atomic_json(output_root / "run_summary.json", summary)
    _atomic_json(
        output_root / "series_progress.json",
        {
            "schema_version": "recovery_sidecar_series_progress_v1",
            "series_spec_sha256": series_spec["series_spec_sha256"],
            "source_manifest": str(source_manifest_path),
            "completed_attempts": attempts,
            "status": "COMPLETE",
        },
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
