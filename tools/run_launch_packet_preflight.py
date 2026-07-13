from __future__ import annotations

"""Run the P3 no-write preflight only from an independently verified packet."""

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_launch_readiness_manifest import read_packet
from tools.run_candidate_set_calibration_shadow_harness import build_actual_preflight_report


class LaunchPacketPreflightError(ValueError):
    pass


SCHEMA = "pipeline_launch_packet_preflight_receipt_v1"


def _sha(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _ref(path: Path) -> dict:
    raw = path.read_bytes()
    return {"path": str(path.resolve()), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def _load_verified(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    read_packet(value)
    if value["status"] != "READY_FOR_NO_WRITE_PREFLIGHT":
        raise LaunchPacketPreflightError("launch manifest is NOT_READY; source-backed artifacts are required")
    return value


def load_verified_with_ref(path: Path) -> tuple[dict, dict]:
    resolved = path.resolve(strict=True)
    raw = resolved.read_bytes()
    value = json.loads(raw.decode("utf-8"))
    read_packet(value)
    if value["status"] != "READY_FOR_NO_WRITE_PREFLIGHT":
        raise LaunchPacketPreflightError("launch manifest is NOT_READY; source-backed artifacts are required")
    return value, {"path": str(resolved), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def _require_artifact_root(packet: dict, manifest_path: Path, artifact_root: Path, *, expected_manifest_ref: dict | None = None) -> tuple[Path, dict[str, str], dict]:
    try:
        root = artifact_root.resolve(strict=True)
        if not root.is_dir():
            raise ValueError("artifact root is not a directory")
        manifest_ref = _ref(manifest_path.resolve(strict=True))
        if expected_manifest_ref is not None and manifest_ref != expected_manifest_ref:
            raise ValueError("launch manifest bytes changed during preflight")
        Path(manifest_ref["path"]).relative_to(root)
        relative_paths: dict[str, str] = {}
        for group_name in ("required_artifacts", "replay_artifacts"):
            for name, ref in packet[group_name].items():
                path = Path(ref["path"]).resolve(strict=True)
                if _ref(path) != ref:
                    raise ValueError("artifact bytes changed after manifest validation")
                relative_paths[name] = path.relative_to(root).as_posix()
    except (OSError, ValueError) as exc:
        raise LaunchPacketPreflightError("all verified packet artifacts must remain under artifact-root") from exc
    return root, relative_paths, manifest_ref


def _receipt(*, manifest_ref: dict, artifact_root: Path, report: dict) -> dict:
    material = {
        "schema_version": SCHEMA,
        "launch_manifest": manifest_ref,
        "artifact_root": str(artifact_root),
        "preflight_report": report,
        "gate": report["gate"],
        "runtime_started": False,
        "writes_to_production": False,
        "actual_metrics": None,
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
    }
    return {**material, "receipt_sha256": _sha(material)}


def _recompute_report(packet: dict, root: Path, paths: dict[str, str]) -> dict:
    return build_actual_preflight_report(
        artifact_root=root,
        p1_run_spec_json=paths["p1_run_spec"], p1_comparison_json=paths["p1_comparison"], label_ledger_json=paths["label_ledger"],
        actual_evaluation_policy_json=paths["policy"], split_manifest_json=paths["split_manifest"], source_manifest_json=paths["source_manifest"],
        expected_universe_jsonl=paths["expected_universe"], producer_jsonl=paths["producer"], prediction_jsonl=paths["after_prediction"], baseline_prediction_jsonl=paths["before_prediction"],
        additional_artifacts=[(name, paths[name]) for name in sorted(packet["replay_artifacts"])], seed=packet["seed"], replicates=packet["replicates"],
    )


def read_preflight_receipt(value: dict, *, verify_artifacts: bool = True) -> dict:
    """Re-verify a captured no-write preflight receipt before later launch steps consume it."""
    required = {"schema_version", "launch_manifest", "artifact_root", "preflight_report", "gate", "runtime_started", "writes_to_production", "actual_metrics", "semantic_quality", "full_scan_approval", "receipt_sha256"}
    if not isinstance(value, dict) or set(value) != required or value.get("schema_version") != SCHEMA:
        raise LaunchPacketPreflightError("preflight receipt schema mismatch")
    material = {key: item for key, item in value.items() if key != "receipt_sha256"}
    if value.get("receipt_sha256") != _sha(material):
        raise LaunchPacketPreflightError("preflight receipt self-hash mismatch")
    report = value.get("preflight_report")
    if not isinstance(report, dict) or value.get("gate") != report.get("gate"):
        raise LaunchPacketPreflightError("preflight receipt gate mismatch")
    if value.get("runtime_started") is not False or value.get("writes_to_production") is not False or value.get("actual_metrics") is not None or value.get("semantic_quality") != "REVIEW-LOCKED" or value.get("full_scan_approval") is not False:
        raise LaunchPacketPreflightError("preflight receipt safety boundary mismatch")
    if report.get("writes_performed") is not False or report.get("runtime_started") is not False or report.get("actual_metrics") is not None or report.get("semantic_quality") != "REVIEW-LOCKED" or report.get("full_scan_approval") is not False or report.get("mode") != "READ_ONLY_NO_WRITE_NO_RUNTIME":
        raise LaunchPacketPreflightError("preflight report safety boundary mismatch")
    if verify_artifacts:
        manifest_ref = value.get("launch_manifest")
        if not isinstance(manifest_ref, dict) or set(manifest_ref) != {"path", "bytes", "sha256"}:
            raise LaunchPacketPreflightError("preflight receipt manifest reference mismatch")
        manifest_path = Path(manifest_ref["path"])
        if _ref(manifest_path) != manifest_ref:
            raise LaunchPacketPreflightError("preflight receipt manifest bytes mismatch")
        packet = _load_verified(manifest_path)
        root, paths, _ = _require_artifact_root(packet, manifest_path, Path(value["artifact_root"]), expected_manifest_ref=manifest_ref)
        if _recompute_report(packet, root, paths) != report:
            raise LaunchPacketPreflightError("preflight receipt provenance mismatch")
    return {"schema_version": SCHEMA, "gate": value["gate"], "runtime_started": False, "writes_to_production": False, "independent_readback": "GO_LAUNCH_PACKET_PREFLIGHT_RECEIPT_BOUND"}


def preflight(*, manifest_path: Path, artifact_root: Path) -> dict:
    """Reuse only verified manifest refs; this never starts a model or writes output."""
    packet, manifest_ref = load_verified_with_ref(manifest_path)
    artifact_root, relative_paths, _ = _require_artifact_root(packet, manifest_path, artifact_root, expected_manifest_ref=manifest_ref)
    report = _recompute_report(packet, artifact_root, relative_paths)
    if report.get("writes_performed") is not False or report.get("runtime_started") is not False or report.get("actual_metrics") is not None or report.get("semantic_quality") != "REVIEW-LOCKED" or report.get("full_scan_approval") is not False or report.get("mode") != "READ_ONLY_NO_WRITE_NO_RUNTIME":
        raise LaunchPacketPreflightError("preflight safety boundary mismatch")
    _require_artifact_root(packet, manifest_path, artifact_root, expected_manifest_ref=manifest_ref)
    return _receipt(manifest_ref=manifest_ref, artifact_root=artifact_root, report=report)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run P3 no-write preflight from a verified launch packet")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--artifact-root", required=True, type=Path)
    args = parser.parse_args()
    try:
        report = preflight(manifest_path=args.manifest, artifact_root=args.artifact_root)
    except (LaunchPacketPreflightError, OSError, ValueError) as exc:
        print(json.dumps({"gate": "NO_GO_LAUNCH_PACKET_PREFLIGHT", "runtime_started": False, "writes_to_production": False, "reason": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["gate"] == "GO_ACTUAL_BOUND_READBACK_ATTEMPT_ALLOWED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
