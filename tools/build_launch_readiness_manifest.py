from __future__ import annotations

"""Build a no-runtime launch packet for the P3/P4 actual workflow."""

import argparse, hashlib, json
from pathlib import Path
from typing import Any


SCHEMA = "pipeline_launch_readiness_manifest_v2"
REQUIRED = ("p1_run_spec", "p1_comparison", "label_ledger", "policy", "split_manifest", "source_manifest", "expected_universe", "producer", "after_prediction", "before_prediction")
REPLAY_REQUIRED = ("after_base_shadows", "after_score_vectors", "after_calibration_artifact", "baseline_base_shadows", "baseline_score_vectors", "baseline_calibration_artifact")


def _ref(path: Path) -> dict[str, Any]:
    raw = path.read_bytes(); return {"path": str(path.resolve()), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def _sha(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def read_packet(value: dict[str, Any]) -> dict[str, Any]:
    required = {"schema_version", "status", "runtime_started", "writes_to_production", "source_backed_required", "requested_parallel", "dashboard_required", "slang_access_mode", "seed", "replicates", "required_artifacts", "replay_artifacts", "missing_required", "missing_replay_artifacts", "path_collisions", "commands", "gate", "full_scan_approval", "manifest_sha256"}
    if not isinstance(value, dict) or set(value) != required or value.get("schema_version") != SCHEMA:
        raise ValueError("launch manifest schema mismatch")
    material = {key: value[key] for key in required if key != "manifest_sha256"}
    if value.get("manifest_sha256") != _sha(material): raise ValueError("launch manifest self-hash mismatch")
    if not isinstance(value["required_artifacts"], dict) or not isinstance(value["replay_artifacts"], dict) or not isinstance(value["missing_required"], list) or not isinstance(value["missing_replay_artifacts"], list) or not isinstance(value["path_collisions"], list): raise ValueError("launch manifest readiness mismatch")
    if value["runtime_started"] is not False or value["writes_to_production"] is not False or value["source_backed_required"] is not True or value["requested_parallel"] != 16 or value["dashboard_required"] is not True or value["slang_access_mode"] != "OFF" or value["gate"] != "REVIEW-LOCKED" or value["full_scan_approval"] is not False:
        raise ValueError("launch manifest safety boundary mismatch")
    for group, expected in ((value["required_artifacts"], REQUIRED), (value["replay_artifacts"], REPLAY_REQUIRED)):
        if set(group) - set(expected): raise ValueError("launch manifest artifact name mismatch")
        for ref in group.values():
            if not isinstance(ref, dict) or set(ref) != {"path", "bytes", "sha256"} or _ref(Path(ref["path"])) != ref:
                raise ValueError("launch manifest artifact bytes mismatch")
    expected_missing = sorted(set(REQUIRED) - set(value["required_artifacts"]))
    expected_replay_missing = sorted(set(REPLAY_REQUIRED) - set(value["replay_artifacts"]))
    all_paths = [ref["path"] for ref in value["required_artifacts"].values()] + [ref["path"] for ref in value["replay_artifacts"].values()]
    expected_collisions = sorted({path for path in all_paths if all_paths.count(path) > 1})
    if value["missing_required"] != expected_missing or value["missing_replay_artifacts"] != expected_replay_missing or value["path_collisions"] != expected_collisions: raise ValueError("launch manifest readiness mismatch")
    ready = not expected_missing and not expected_replay_missing and not expected_collisions
    if value["status"] != ("READY_FOR_NO_WRITE_PREFLIGHT" if ready else "NOT_READY"): raise ValueError("launch manifest readiness mismatch")
    return {"schema_version": SCHEMA, "status": value["status"], "source_backed_required": True, "runtime_started": False, "writes_to_production": False, "independent_readback": "GO_LAUNCH_MANIFEST_BOUND"}


def build_packet(*, output: Path, paths: dict[str, Path], artifacts: dict[str, Path], seed: int, replicates: int) -> dict[str, Any]:
    if set(paths) - set(REQUIRED) or set(artifacts) - set(REPLAY_REQUIRED): raise ValueError("launch packet only accepts canonical artifact names")
    missing = sorted(name for name in REQUIRED if name not in paths or not paths[name].is_file())
    bad_artifacts = sorted(name for name in REPLAY_REQUIRED if name not in artifacts or not artifacts[name].is_file())
    refs = {name: _ref(path) for name, path in paths.items() if path.is_file()}
    artifact_refs = {name: _ref(path) for name, path in artifacts.items() if path.is_file()}
    all_paths = [ref["path"] for ref in refs.values()] + [ref["path"] for ref in artifact_refs.values()]
    collisions = sorted({path for path in all_paths if all_paths.count(path) > 1})
    status = "READY_FOR_NO_WRITE_PREFLIGHT" if not missing and not bad_artifacts and not collisions else "NOT_READY"
    payload = {"schema_version": SCHEMA, "status": status, "runtime_started": False, "writes_to_production": False, "source_backed_required": True, "requested_parallel": 16, "dashboard_required": True, "slang_access_mode": "OFF", "seed": seed, "replicates": replicates, "required_artifacts": refs, "replay_artifacts": artifact_refs, "missing_required": missing, "missing_replay_artifacts": bad_artifacts, "path_collisions": collisions, "commands": {"preflight": "tools/run_candidate_set_calibration_shadow_harness.py actual-preflight", "pair_freeze": "tools/run_paired_measurement_readback.py --freeze-run-spec", "recovery": "tools/recover_expert_run_from_checkpoint.py"}, "gate": "REVIEW-LOCKED", "full_scan_approval": False}
    payload["manifest_sha256"] = _sha(payload)
    output.parent.mkdir(parents=True, exist_ok=True); output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="P3/P4 launch packet readiness manifest (no runtime)")
    parser.add_argument("--output", required=True, type=Path); parser.add_argument("--seed", type=int, default=20260712); parser.add_argument("--replicates", type=int, default=2000)
    for name in REQUIRED: parser.add_argument("--" + name.replace("_", "-"), dest=name, type=Path)
    parser.add_argument("--artifact", action="append", default=[])
    args = parser.parse_args(); artifacts = {}
    for item in args.artifact:
        name, sep, path = item.partition("=")
        if not sep or not name or not path: parser.error("--artifact must be name=path")
        artifacts[name] = Path(path)
    packet = build_packet(output=args.output, paths={name: getattr(args, name) for name in REQUIRED if getattr(args, name) is not None}, artifacts=artifacts, seed=args.seed, replicates=args.replicates)
    print(json.dumps(packet, ensure_ascii=False)); return 0 if packet["status"] == "READY_FOR_NO_WRITE_PREFLIGHT" else 2


if __name__ == "__main__": raise SystemExit(main())
