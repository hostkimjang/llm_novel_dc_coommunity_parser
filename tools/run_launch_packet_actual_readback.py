from __future__ import annotations

"""Write an actual-readback bundle only from a verified launch/preflight pair."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.run_candidate_set_calibration_shadow_harness import build_bound_actual_readback_from_files, write_actual_readback_bundle
from tools.run_launch_packet_preflight import LaunchPacketPreflightError, _require_artifact_root, load_verified_with_ref, read_preflight_receipt


class LaunchPacketActualReadbackError(ValueError):
    pass


def _load_go_receipt(path: Path, *, manifest_ref: dict, artifact_root: Path) -> None:
    receipt = json.loads(path.read_text(encoding="utf-8"))
    result = read_preflight_receipt(receipt)
    if result["gate"] != "GO_ACTUAL_BOUND_READBACK_ATTEMPT_ALLOWED":
        raise LaunchPacketActualReadbackError("preflight receipt is not GO")
    if receipt.get("launch_manifest") != manifest_ref or Path(str(receipt.get("artifact_root") or "")).resolve() != artifact_root:
        raise LaunchPacketActualReadbackError("preflight receipt packet binding mismatch")


def run(*, manifest_path: Path, preflight_receipt_path: Path, artifact_root: Path, output_dir: Path) -> dict:
    packet, manifest_ref = load_verified_with_ref(manifest_path)
    root, paths, _ = _require_artifact_root(packet, manifest_path, artifact_root, expected_manifest_ref=manifest_ref)
    _load_go_receipt(preflight_receipt_path, manifest_ref=manifest_ref, artifact_root=root)
    try:
        output = output_dir.resolve()
        output.relative_to(root)
        if output.parent.resolve() != root:
            raise ValueError("output must be a direct child directory")
    except ValueError as exc:
        raise LaunchPacketActualReadbackError("actual readback output must remain inside artifact-root") from exc
    _, spec, readiness, manifest = build_bound_actual_readback_from_files(
        artifact_root=root,
        p1_run_spec_json=paths["p1_run_spec"], p1_comparison_json=paths["p1_comparison"], label_ledger_json=paths["label_ledger"],
        actual_evaluation_policy_json=paths["policy"], split_manifest_json=paths["split_manifest"], source_manifest_json=paths["source_manifest"],
        expected_universe_jsonl=paths["expected_universe"], producer_jsonl=paths["producer"], prediction_jsonl=paths["after_prediction"], baseline_prediction_jsonl=paths["before_prediction"],
        additional_artifacts=[(name, paths[name]) for name in sorted(packet["replay_artifacts"])], seed=packet["seed"], replicates=packet["replicates"],
    )
    _require_artifact_root(packet, manifest_path, root, expected_manifest_ref=manifest_ref)
    written = write_actual_readback_bundle(artifact_root=root, output_dir=output, run_spec=spec, readiness=readiness, manifest=manifest)
    return {"gate": "GO_ACTUAL_READBACK_FOUNDATION_ONLY", "output_dir": str(written), "runtime_started": False, "writes_to_production": False, "semantic_quality": "REVIEW-LOCKED", "full_scan_approval": False}


def main() -> int:
    parser = argparse.ArgumentParser(description="Write actual-readback only from a verified launch/preflight pair")
    parser.add_argument("--manifest", required=True, type=Path); parser.add_argument("--preflight-receipt", required=True, type=Path)
    parser.add_argument("--artifact-root", required=True, type=Path); parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    try: result = run(manifest_path=args.manifest, preflight_receipt_path=args.preflight_receipt, artifact_root=args.artifact_root, output_dir=args.output_dir)
    except (LaunchPacketPreflightError, LaunchPacketActualReadbackError, OSError, ValueError) as exc:
        print(json.dumps({"gate": "NO_GO_LAUNCH_PACKET_ACTUAL_READBACK", "runtime_started": False, "writes_to_production": False, "reason": str(exc)}, ensure_ascii=False)); return 2
    print(json.dumps(result, ensure_ascii=False)); return 0


if __name__ == "__main__": raise SystemExit(main())
