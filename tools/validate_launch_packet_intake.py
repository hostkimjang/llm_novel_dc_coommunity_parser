"""Validate an operator-owned launch-packet intake without starting runtime.

The intake is deliberately separate from the launch manifest.  It records the
operator's source/policy attestation and the frozen paired-run command plan,
then delegates artifact integrity to the existing manifest reader.  It never
writes a receipt, launches a model, or changes public results.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shlex
import sys
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_launch_readiness_manifest import read_packet


SCHEMA = "pipeline_launch_packet_intake_v1"
PENDING = "WAITING_EXTERNAL_INPUT"
READY = "READY_FOR_NO_WRITE_PREFLIGHT"


def _text(value: Any, field: str) -> str:
    result = str(value or "").strip()
    if not result:
        raise ValueError(f"{field} must be non-empty")
    return result


def _tokens(command: Any, field: str) -> list[str]:
    text = _text(command, field)
    try:
        values = [item.strip("\"'") for item in shlex.split(text, posix=False)]
    except ValueError as exc:
        raise ValueError(f"{field} must be a parseable command") from exc
    if not values:
        raise ValueError(f"{field} must be non-empty")
    return values


def _option(tokens: list[str], name: str, field: str) -> str:
    indexes = [index for index, value in enumerate(tokens) if value == name]
    if len(indexes) != 1 or indexes[0] + 1 >= len(tokens):
        raise ValueError(f"{field} must contain exactly one {name}")
    return tokens[indexes[0] + 1]


def _validate_arm(command: Any, field: str) -> tuple[str, str]:
    tokens = _tokens(command, field)
    if not any(value.replace("\\", "/").endswith("expert_main.py") for value in tokens):
        raise ValueError(f"{field} must execute expert_main.py")
    if "--no-dashboard" in tokens:
        raise ValueError(f"{field} must preserve dashboard ON")
    if _option(tokens, "--parallel", field) != "16":
        raise ValueError(f"{field} must preserve exact --parallel 16")
    if _option(tokens, "--slang-db", field).lower() != "off":
        raise ValueError(f"{field} must keep slang DB OFF")
    if _option(tokens, "--vlm", field).lower() != "on" or _option(tokens, "--ocr", field).lower() != "on":
        raise ValueError(f"{field} must keep VLM/OCR ON")
    for flag in ("--reuse-shards-only", "--require-vlm-ocr-for-images"):
        if flag not in tokens:
            raise ValueError(f"{field} must contain {flag}")
    return _option(tokens, "--input", field), _option(tokens, "--output", field)


def _validate_plan(value: Any) -> dict[str, Any]:
    required = {
        "before_environment", "after_environment", "before_command", "after_command", "recovery_command"
    }
    if not isinstance(value, Mapping) or set(value) != required:
        raise ValueError("paired_command_plan schema mismatch")
    before_environment = value.get("before_environment")
    after_environment = value.get("after_environment")
    if before_environment != {"PIPELINE_MEASUREMENT_EARLY_ROUTE_MODE": "OFF"}:
        raise ValueError("before_environment must bind early-route mode OFF")
    if after_environment != {"PIPELINE_MEASUREMENT_EARLY_ROUTE_MODE": "SOURCE_ONLY_V1"}:
        raise ValueError("after_environment must bind early-route mode SOURCE_ONLY_V1")
    before_command = _text(value.get("before_command"), "paired_command_plan.before_command")
    after_command = _text(value.get("after_command"), "paired_command_plan.after_command")
    recovery_command = _text(value.get("recovery_command"), "paired_command_plan.recovery_command")
    before_input, before_output = _validate_arm(before_command, "paired_command_plan.before_command")
    after_input, after_output = _validate_arm(after_command, "paired_command_plan.after_command")
    if before_input != after_input:
        raise ValueError("paired BEFORE/AFTER commands must use the same frozen input")
    if before_output == after_output:
        raise ValueError("paired BEFORE/AFTER commands must use distinct outputs")
    recovery_tokens = _tokens(recovery_command, "paired_command_plan.recovery_command")
    if not any(value.replace("\\", "/").endswith("tools/recover_expert_run_from_checkpoint.py") for value in recovery_tokens):
        raise ValueError("recovery_command must execute recover_expert_run_from_checkpoint.py")
    _option(recovery_tokens, "--manifest", "paired_command_plan.recovery_command")
    return {
        "before_environment": dict(before_environment),
        "after_environment": dict(after_environment),
        "before_command": before_command,
        "after_command": after_command,
        "recovery_command": recovery_command,
        "frozen_input_path": before_input,
        "before_output_path": before_output,
        "after_output_path": after_output,
    }


def validate_intake(value: Any) -> dict[str, Any]:
    required = {
        "schema_version", "operator_id", "policy_owner_state", "source_backed_attestation",
        "manifest_path", "artifact_root", "requested_parallel", "dashboard_required",
        "slang_access_mode", "paired_command_plan",
    }
    if not isinstance(value, Mapping) or set(value) != required or value.get("schema_version") != SCHEMA:
        raise ValueError("launch packet intake schema mismatch")
    _text(value.get("operator_id"), "operator_id")
    if value.get("policy_owner_state") not in {"PENDING_OWNER_DECISION", "OWNER_APPROVED_POLICY_V3"}:
        raise ValueError("unsupported policy_owner_state")
    if value.get("source_backed_attestation") not in {"PENDING_EXTERNAL", "SOURCE_BACKED_CONFIRMED"}:
        raise ValueError("unsupported source_backed_attestation")
    if value.get("requested_parallel") != 16 or value.get("dashboard_required") is not True or value.get("slang_access_mode") != "OFF":
        raise ValueError("intake requires parallel 16, dashboard ON, and slang OFF")
    plan = _validate_plan(value.get("paired_command_plan"))

    pending_reasons: list[str] = []
    if value["policy_owner_state"] != "OWNER_APPROVED_POLICY_V3":
        pending_reasons.append("POLICY_OWNER_DECISION_PENDING")
    if value["source_backed_attestation"] != "SOURCE_BACKED_CONFIRMED":
        pending_reasons.append("SOURCE_BACKED_PACKET_PENDING")
    manifest_path = value.get("manifest_path")
    artifact_root = value.get("artifact_root")
    manifest_status: str | None = None
    if manifest_path is None or artifact_root is None:
        pending_reasons.append("MANIFEST_OR_ARTIFACT_ROOT_PENDING")
    else:
        manifest = Path(_text(manifest_path, "manifest_path"))
        root = Path(_text(artifact_root, "artifact_root"))
        if not manifest.is_file() or not root.is_dir():
            pending_reasons.append("MANIFEST_OR_ARTIFACT_ROOT_UNAVAILABLE")
        else:
            manifest = manifest.resolve(strict=True)
            root = root.resolve(strict=True)
            try:
                manifest.relative_to(root)
            except ValueError as exc:
                raise ValueError("manifest must remain under artifact_root") from exc
            loaded = json.loads(manifest.read_text(encoding="utf-8"))
            read_packet(loaded)
            for group_name in ("required_artifacts", "replay_artifacts"):
                for ref in loaded[group_name].values():
                    try:
                        Path(ref["path"]).resolve(strict=True).relative_to(root)
                    except (OSError, ValueError) as exc:
                        raise ValueError("all manifest artifacts must remain under artifact_root") from exc
            manifest_status = str(loaded["status"])
            if manifest_status != READY:
                pending_reasons.append("MANIFEST_NOT_READY")
            elif Path(plan["frozen_input_path"]).resolve(strict=True) != Path(
                loaded["required_artifacts"]["expected_universe"]["path"]
            ).resolve(strict=True):
                raise ValueError("paired commands must use the manifest-bound frozen expected universe")

    status = READY if not pending_reasons else PENDING
    return {
        "schema_version": SCHEMA,
        "status": status,
        "pending_reasons": sorted(set(pending_reasons)),
        "manifest_status": manifest_status,
        "paired_command_plan": plan,
        "runtime_started": False,
        "writes_performed": False,
        "actual_metrics": None,
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="No-write launch-packet intake validator")
    parser.add_argument("--intake", type=Path, required=True)
    args = parser.parse_args()
    try:
        value = json.loads(args.intake.read_text(encoding="utf-8"))
        print(json.dumps(validate_intake(value), ensure_ascii=False, sort_keys=True))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "NO_GO_LAUNCH_PACKET_INTAKE", "error": str(exc), "runtime_started": False, "writes_performed": False}, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
