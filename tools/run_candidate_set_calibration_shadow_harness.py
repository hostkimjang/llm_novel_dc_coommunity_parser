from __future__ import annotations

"""P3 정확도 퍼센트 sidecar의 저장본 준비도·합성 계약 하네스.

새 LLM 실행이나 공개 결과 변경을 만들지 않는다. Golden18은 확률을
계산할 수 없는 이유를 fail-close로 확인하고, 합성 COMPLETE 후보셋은
분할·보정 산출물·정책·점수 벡터 결속과 지표 산술만 검증한다.
"""

import argparse
import copy
from dataclasses import replace
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import secrets
import stat
import sys
from typing import Any, Callable, Mapping, Optional, Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.llm_batch.grounding.candidate_set_calibration_shadow import (  # noqa: E402
    CALIBRATION_SHADOW_SCHEMA,
    CALIBRATION_UNAVAILABLE_SCHEMA,
    CalibrationArtifact,
    CalibrationEvaluationPolicy,
    CalibrationFitReceipt,
    CalibrationSplitAssignment,
    CalibrationSplitManifest,
    EventScoreVector,
    FrozenActualEvidenceReceipt,
    build_calibration_shadow,
    calibration_shadow_from_dict,
    evaluate_frozen_holdout,
)
from src.llm_batch.grounding.candidate_set_shadow import (  # noqa: E402
    CALIBRATED_SHADOW_STATUS,
    NIL_LABEL,
    PROBABILITY_STATUS,
    build_uncalibrated_selective_shadow,
    selective_shadow_from_dict,
)
from src.llm_batch.grounding.calibration_actual_readback import (  # noqa: E402
    ArtifactRef,
    build_readback_manifest,
    expected_universe_readback,
    prediction_payload_readback,
    producer_coverage_receipt,
    snapshot_artifact,
    snapshot_json_object,
    snapshot_jsonl_rows,
    validate_actual_readback_artifacts,
)
from src.llm_batch.promotion_gate import (  # noqa: E402
    EvidenceRecord,
    GroundingState,
    RetrievalState,
    can_publish_title,
)


RUN_SPEC_SCHEMA = "candidate-set-calibration-shadow-runspec-v1"
REPORT_SCHEMA = "candidate-set-calibration-shadow-comparison-v1"
ACTUAL_EVIDENCE_RUN_SPEC_SCHEMA = "candidate-set-calibration-actual-evidence-runspec-v1"
ACTUAL_SOURCE_MANIFEST_SCHEMA = "candidate-set-calibration-actual-source-manifest-v1"
ACTUAL_SOURCE_PAYLOAD_SCHEMA = "candidate-set-calibration-actual-source-payload-v1"
ACTUAL_PREFLIGHT_SCHEMA = "candidate-set-calibration-actual-preflight-v1"
ACTUAL_EVALUATION_RESULT_SCHEMA = "candidate-set-calibration-actual-evaluation-result-v1"
ACTUAL_REPLAY_ARTIFACT_NAMES = frozenset(
    {
        "after_base_shadows",
        "after_score_vectors",
        "after_calibration_artifact",
        "baseline_base_shadows",
        "baseline_score_vectors",
        "baseline_calibration_artifact",
    }
)
MODE = "SAVED_GOLDEN_READINESS_AND_SYNTHETIC_METRIC_CONTRACT_NO_RUNTIME"
OUTPUT_ROOT = ROOT / "out" / "candidate_set_calibration_shadow_harness_20260711"
DEFAULT_DATASET_READINESS = (
    ROOT
    / "out/candidate_set_calibration_dataset_readiness_20260712/v2/readiness.json"
)
SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64
SHA_D = "d" * 64
SHA_E = "e" * 64
SHA_F = "f" * 64
SHA_BASELINE = "9" * 64


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _resolve_path(value: str | Path) -> Path:
    path = Path(value)
    return (path if path.is_absolute() else ROOT / path).resolve()


def _stored_path(value: str | Path) -> str:
    path = _resolve_path(value)
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _canonical_hash(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact_ref(value: str | Path) -> dict[str, Any]:
    path = _resolve_path(value)
    if not path.is_file():
        raise ValueError(f"artifact missing: {path}")
    return {
        "path": _stored_path(path),
        "sha256": _sha256_file(path),
        "bytes": path.stat().st_size,
    }


def _validate_artifact_ref(value: Any, label: str) -> Path:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} artifact reference missing")
    path = _resolve_path(str(value.get("path") or ""))
    if _artifact_ref(path) != dict(value):
        raise ValueError(f"{label} artifact reference mismatch")
    return path


def _read_json(value: str | Path) -> Any:
    return json.loads(_resolve_path(value).read_text(encoding="utf-8-sig"))


def _run_spec_self_hash(spec: Mapping[str, Any]) -> str:
    return _canonical_hash(
        {
            key: value
            for key, value in spec.items()
            if key not in {"generated_at", "run_spec_sha256"}
        }
    )


def _comparison_semantic_payload(value: Mapping[str, Any]) -> dict[str, Any]:
    snapshot = json.loads(json.dumps(dict(value), ensure_ascii=False))
    snapshot.pop("generated_at", None)
    return snapshot


def _validate_parent_comparison_semantics(
    *,
    stage: str,
    run_spec_path: str | Path,
    comparison_path: str | Path,
) -> dict[str, Any]:
    run_path = _resolve_path(run_spec_path)
    comparison_path = _resolve_path(comparison_path)
    run_ref_before = _artifact_ref(run_path)
    comparison_ref_before = _artifact_ref(comparison_path)
    stored = _read_json(comparison_path)
    run_spec = _read_json(run_path)
    if not isinstance(stored, dict) or not isinstance(run_spec, Mapping):
        raise ValueError(f"{stage} parent comparison or RunSpec shape mismatch")
    if stage == "P1":
        from tools.run_candidate_set_nil_shadow_harness import (
            build_saved_artifact_comparison,
        )

        rebuilt = build_saved_artifact_comparison(
            run_path,
            verify_implementation=False,
        )
    elif stage == "P2":
        from tools.run_publication_exact_once_harness import build_comparison

        rebuilt = build_comparison(run_path, verify_implementation=False)
    else:
        raise ValueError(f"unsupported P3 parent stage: {stage}")
    if _comparison_semantic_payload(stored) != _comparison_semantic_payload(rebuilt):
        raise ValueError(f"{stage} parent comparison semantic replay mismatch")
    run_ref = stored.get("run_spec")
    if not isinstance(run_ref, Mapping):
        raise ValueError(f"{stage} parent comparison RunSpec reference missing")
    if _resolve_path(str(run_ref.get("path") or "")) != run_path:
        raise ValueError(f"{stage} parent comparison points to another RunSpec")
    file_sha256 = run_ref.get("sha256") or run_ref.get("file_sha256")
    if file_sha256 != run_ref_before["sha256"]:
        raise ValueError(f"{stage} parent comparison RunSpec file digest mismatch")
    if run_ref.get("self_hash") != run_spec.get("run_spec_sha256"):
        raise ValueError(f"{stage} parent comparison RunSpec self-hash mismatch")
    if (
        _artifact_ref(run_path) != run_ref_before
        or _artifact_ref(comparison_path) != comparison_ref_before
    ):
        raise ValueError(f"{stage} parent artifacts changed during semantic replay")
    return stored


def _implementation_contract() -> dict[str, Any]:
    refs = {
        "harness_tool": _artifact_ref(Path(__file__)),
        "calibration_contract": _artifact_ref(
            ROOT / "src/llm_batch/grounding/candidate_set_calibration_shadow.py"
        ),
        "learned_calibration_solver": _artifact_ref(
            ROOT / "src/llm_batch/grounding/candidate_reranker_calibration.py"
        ),
        "learned_calibration_events": _artifact_ref(
            ROOT / "src/llm_batch/grounding/candidate_reranker_calibration_data.py"
        ),
        "candidate_set_shadow": _artifact_ref(ROOT / "src/llm_batch/grounding/candidate_set_shadow.py"),
        "actual_artifact_readback": _artifact_ref(
            ROOT / "src/llm_batch/grounding/calibration_actual_readback.py"
        ),
        "dataset_readiness_contract": _artifact_ref(
            ROOT / "src/llm_batch/grounding/calibration_dataset_readiness.py"
        ),
        "dataset_readiness_tool": _artifact_ref(
            ROOT / "tools/run_calibration_dataset_readiness.py"
        ),
        "contract_tests": _artifact_ref(
            ROOT / "tests/test_candidate_set_calibration_shadow_contract.py"
        ),
        "actual_artifact_readback_tests": _artifact_ref(
            ROOT / "tests/test_calibration_actual_readback.py"
        ),
        "dataset_readiness_tests": _artifact_ref(
            ROOT / "tests/test_calibration_dataset_readiness.py"
        ),
        "harness_tests": _artifact_ref(
            ROOT / "tests/test_candidate_set_calibration_shadow_harness.py"
        ),
    }
    return {
        "artifacts": refs,
        "sha256": _canonical_hash(
            {name: ref["sha256"] for name, ref in sorted(refs.items())}
        ),
    }


def _synthetic_metric_protocol() -> dict[str, Any]:
    payload = {
        "evidence_scope": "SYNTHETIC_CONTRACT_ONLY",
        "policy": _policy().to_dict(),
        "truth_event": "Y_IN_CANDIDATE_ID_OR_NIL",
        "headline_metrics": [
            "candidate_set_recall",
            "top_label_accuracy",
            "multiclass_brier",
            "log_loss",
            "top_label_ece",
            "nil_precision",
            "nil_recall",
            "coverage",
            "selective_risk",
            "aurc",
        ],
        "implemented_intervals": {
            "candidate_set_recall": "CLOPPER_PEARSON_ONE_SIDED_LOWER",
            "nil_precision": "CLOPPER_PEARSON_TWO_SIDED",
            "nil_recall": "CLOPPER_PEARSON_TWO_SIDED",
            "selective_risk": "CLOPPER_PEARSON_ONE_SIDED_UPPER",
            "top_label_accuracy": "CLUSTER_BOOTSTRAP_PERCENTILE_POLICY_GATED",
            "brier": "CLUSTER_BOOTSTRAP_PERCENTILE_POLICY_GATED",
            "log_loss": "CLUSTER_BOOTSTRAP_PERCENTILE_POLICY_GATED",
            "ece": "CLUSTER_BOOTSTRAP_PERCENTILE_POLICY_GATED",
            "aurc": "CLUSTER_BOOTSTRAP_PERCENTILE_POLICY_GATED",
            "paired_baseline_deltas": "CLUSTER_BOOTSTRAP_PERCENTILE_POLICY_GATED",
        },
        "deployment_interval_protocol": "IMPLEMENTED_PRE_REGISTERED_PAIRED_CI_GATES_NO_ACTUAL_OUTPUT",
        "missing_for_actual_conversion": [
            "actual DEV/CALIBRATION/FROZEN_HOLDOUT artifact set",
            "actual producer and prediction payloads",
            "pre-registered actual metric protocol and completed readback run",
        ],
    }
    return {**payload, "protocol_sha256": _canonical_hash(payload)}


def _p3_contract() -> dict[str, Any]:
    return {
        "truth_event": "Y_IN_CANDIDATE_ID_OR_NIL",
        "abstain_is_action_not_truth": True,
        "probability_mass_scale": 1_000_000,
        "candidate_set_recall_precondition": True,
        "split_roles": ["DEV", "CALIBRATION", "FROZEN_HOLDOUT"],
        "frozen_tuning_forbidden": True,
        "actual_readback_schema": "calibration-actual-readback-v2",
        "actual_evidence_run_spec_schema": ACTUAL_EVIDENCE_RUN_SPEC_SCHEMA,
        "actual_preflight_schema": ACTUAL_PREFLIGHT_SCHEMA,
        "actual_preflight_mode": "READ_ONLY_NO_WRITE_NO_RUNTIME",
        "actual_binding_source": "STABLE_POLICY_P1_LEDGER_AND_JSONL_FILES_NO_RAW_SHA_CLI",
        "actual_evidence_receipt_schema": "candidate_set_frozen_actual_evidence_receipt_v2",
        "dataset_readiness_schema": "candidate_set_calibration_dataset_readiness_v2",
        "calibration_policy_schema": "candidate_set_calibration_policy_v2",
        "paired_delta_ci_gate_metrics": [
            "top_label_accuracy",
            "brier",
            "log_loss",
            "ece",
            "selective_risk",
            "aurc",
        ],
        "public_effect": "NONE_SHADOW_ONLY",
    }


def create_run_spec(
    *,
    parent_p1_run_spec_path: str | Path,
    parent_p1_comparison_path: str | Path,
    parent_p2_run_spec_path: str | Path,
    parent_p2_comparison_path: str | Path,
    label_ledger_path: str | Path,
    dataset_readiness_path: str | Path = DEFAULT_DATASET_READINESS,
) -> dict[str, Any]:
    from tools.run_candidate_set_nil_shadow_harness import validate_run_spec as validate_p1
    from tools.run_publication_exact_once_harness import validate_run_spec as validate_p2

    p1_spec, p1_rows, _ = validate_p1(parent_p1_run_spec_path, verify_implementation=False)
    p2_spec, p2_rows = validate_p2(parent_p2_run_spec_path, verify_implementation=False)
    if len(p1_rows) != 18 or len(p2_rows) != 18:
        raise ValueError("P1/P2 parent row count must be Golden18")
    p1_comparison = _validate_parent_comparison_semantics(
        stage="P1",
        run_spec_path=parent_p1_run_spec_path,
        comparison_path=parent_p1_comparison_path,
    )
    p2_comparison = _validate_parent_comparison_semantics(
        stage="P2",
        run_spec_path=parent_p2_run_spec_path,
        comparison_path=parent_p2_comparison_path,
    )
    ledger = _read_json(label_ledger_path)
    readiness = _read_json(dataset_readiness_path)
    if not isinstance(ledger, dict) or ledger.get("schema_version") != "candidate-set-nil-label-ledger-v1":
        raise ValueError("label ledger schema mismatch")
    artifacts = {
        "parent_p1_run_spec": _artifact_ref(parent_p1_run_spec_path),
        "parent_p1_comparison": _artifact_ref(parent_p1_comparison_path),
        "parent_p2_run_spec": _artifact_ref(parent_p2_run_spec_path),
        "parent_p2_comparison": _artifact_ref(parent_p2_comparison_path),
        "label_ledger": _artifact_ref(label_ledger_path),
        "dataset_readiness": _artifact_ref(dataset_readiness_path),
    }
    p1_label_ref = p1_spec.get("artifacts", {}).get("label_ledger")
    if not isinstance(p1_label_ref, Mapping) or dict(p1_label_ref) != artifacts["label_ledger"]:
        raise ValueError("P3 label ledger is not the exact P1-bound artifact")
    from src.llm_batch.grounding.calibration_dataset_readiness import (
        validate_dataset_readiness_against_sources,
    )

    validate_dataset_readiness_against_sources(
        readiness,
        p1_comparison=p1_comparison,
        label_ledger=ledger,
    )
    readiness_sources = readiness["sources"]
    if (
        readiness_sources.get("p1_run_spec") != artifacts["parent_p1_run_spec"]
        or readiness_sources.get("p1_comparison") != artifacts["parent_p1_comparison"]
        or readiness_sources.get("label_ledger") != artifacts["label_ledger"]
    ):
        raise ValueError("dataset readiness sources do not match P3 parents")
    spec: dict[str, Any] = {
        "schema_version": RUN_SPEC_SCHEMA,
        "generated_at": _now(),
        "mode": MODE,
        "artifacts": artifacts,
        "parent_contract": {
            "p1_run_spec_self_hash": p1_spec.get("run_spec_sha256"),
            "p2_run_spec_self_hash": p2_spec.get("run_spec_sha256"),
            "p1_row_count": len(p1_rows),
            "p2_row_count": len(p2_rows),
            "p1_probability": p1_comparison.get("gates", {}).get("probability"),
            "p1_candidate_set_recall": p1_comparison.get("gates", {}).get(
                "candidate_set_recall"
            ),
            "p2_runtime": p2_comparison.get("gates", {}).get("production_runtime"),
        },
        "p3_contract": _p3_contract(),
        "dataset_readiness": {
            "gate": readiness["gate"],
            "manifest_sha256": readiness["manifest_sha256"],
            "ready_for_split_manifest": readiness["ready_for_split_manifest"],
            "counts": readiness["counts"],
        },
        "metric_protocol": _synthetic_metric_protocol(),
        "implementation_contract": _implementation_contract(),
        "runtime_validation": "NOT_RUN",
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
    }
    spec["run_spec_sha256"] = _run_spec_self_hash(spec)
    return spec


def write_run_spec(spec: Mapping[str, Any], output: str | Path) -> Path:
    path = _resolve_path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(dict(spec), ensure_ascii=False, indent=2) + "\n")
    if _read_json(path) != dict(spec):
        raise ValueError("stored P3 RunSpec readback mismatch")
    return path


def _validate_frozen_implementation_contract(implementation: Any) -> None:
    if not isinstance(implementation, Mapping) or not isinstance(implementation.get("artifacts"), Mapping):
        raise ValueError("P3 implementation contract missing")
    hashes: dict[str, str] = {}
    for name, ref in implementation["artifacts"].items():
        if not isinstance(name, str) or not isinstance(ref, Mapping):
            raise ValueError("P3 frozen implementation artifact invalid")
        path, digest, size = ref.get("path"), ref.get("sha256"), ref.get("bytes")
        if not isinstance(path, str) or Path(path).is_absolute() or not path:
            raise ValueError(f"P3 frozen implementation path invalid: {name}")
        if not isinstance(digest, str) or len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise ValueError(f"P3 frozen implementation sha256 invalid: {name}")
        if not isinstance(size, int) or size <= 0:
            raise ValueError(f"P3 frozen implementation bytes invalid: {name}")
        hashes[name] = digest
    if not hashes or implementation.get("sha256") != _canonical_hash(dict(sorted(hashes.items()))):
        raise ValueError("P3 frozen implementation contract fingerprint mismatch")


def validate_run_spec(
    path: str | Path,
    *,
    verify_implementation: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    from tools.run_candidate_set_nil_shadow_harness import validate_run_spec as validate_p1
    from tools.run_publication_exact_once_harness import validate_run_spec as validate_p2

    spec = _read_json(path)
    if not isinstance(spec, dict) or spec.get("schema_version") != RUN_SPEC_SCHEMA:
        raise ValueError("unsupported P3 run spec schema")
    if spec.get("mode") != MODE:
        raise ValueError("P3 run spec mode mismatch")
    if spec.get("run_spec_sha256") != _run_spec_self_hash(spec):
        raise ValueError("P3 run spec self hash mismatch")
    if spec.get("runtime_validation") != "NOT_RUN":
        raise ValueError("P3 run spec runtime boundary mismatch")
    if spec.get("semantic_quality") != "REVIEW-LOCKED" or spec.get("full_scan_approval") is not False:
        raise ValueError("P3 run spec approval boundary mismatch")
    if spec.get("p3_contract") != _p3_contract():
        raise ValueError("P3 calibration contract mismatch")
    if spec.get("metric_protocol") != _synthetic_metric_protocol():
        raise ValueError("P3 metric protocol or policy binding mismatch")
    artifacts = spec.get("artifacts")
    if not isinstance(artifacts, Mapping):
        raise ValueError("P3 run spec artifacts missing")
    paths = {
        name: _validate_artifact_ref(artifacts.get(name), name)
        for name in (
            "parent_p1_run_spec",
            "parent_p1_comparison",
            "parent_p2_run_spec",
            "parent_p2_comparison",
            "label_ledger",
            "dataset_readiness",
        )
    }
    p1_spec, p1_rows, _ = validate_p1(paths["parent_p1_run_spec"], verify_implementation=False)
    p2_spec, p2_rows = validate_p2(paths["parent_p2_run_spec"], verify_implementation=False)
    p1_label_ref = p1_spec.get("artifacts", {}).get("label_ledger")
    if not isinstance(p1_label_ref, Mapping) or dict(p1_label_ref) != dict(
        artifacts["label_ledger"]
    ):
        raise ValueError("P3 label ledger is not the exact P1-bound artifact")
    parent = spec.get("parent_contract")
    if not isinstance(parent, Mapping):
        raise ValueError("P3 parent contract missing")
    if parent.get("p1_run_spec_self_hash") != p1_spec.get("run_spec_sha256"):
        raise ValueError("P1 parent self hash mismatch")
    if parent.get("p2_run_spec_self_hash") != p2_spec.get("run_spec_sha256"):
        raise ValueError("P2 parent self hash mismatch")
    if parent.get("p1_row_count") != len(p1_rows) or parent.get("p2_row_count") != len(p2_rows):
        raise ValueError("P1/P2 parent row count mismatch")
    p1_comparison = _validate_parent_comparison_semantics(
        stage="P1",
        run_spec_path=paths["parent_p1_run_spec"],
        comparison_path=paths["parent_p1_comparison"],
    )
    p2_comparison = _validate_parent_comparison_semantics(
        stage="P2",
        run_spec_path=paths["parent_p2_run_spec"],
        comparison_path=paths["parent_p2_comparison"],
    )
    ledger = _read_json(paths["label_ledger"])
    readiness = _read_json(paths["dataset_readiness"])
    from src.llm_batch.grounding.calibration_dataset_readiness import (
        validate_dataset_readiness_against_sources,
    )

    validate_dataset_readiness_against_sources(
        readiness,
        p1_comparison=p1_comparison,
        label_ledger=ledger,
    )
    if (
        readiness["sources"].get("p1_run_spec") != artifacts["parent_p1_run_spec"]
        or readiness["sources"].get("p1_comparison") != artifacts["parent_p1_comparison"]
        or readiness["sources"].get("label_ledger") != artifacts["label_ledger"]
    ):
        raise ValueError("P3 dataset readiness source binding mismatch")
    expected_readiness = {
        "gate": readiness["gate"],
        "manifest_sha256": readiness["manifest_sha256"],
        "ready_for_split_manifest": readiness["ready_for_split_manifest"],
        "counts": readiness["counts"],
    }
    if spec.get("dataset_readiness") != expected_readiness:
        raise ValueError("P3 dataset readiness contract mismatch")
    if parent.get("p1_probability") != p1_comparison.get("gates", {}).get("probability"):
        raise ValueError("P1 probability gate binding mismatch")
    if parent.get("p1_candidate_set_recall") != p1_comparison.get("gates", {}).get(
        "candidate_set_recall"
    ):
        raise ValueError("P1 recall gate binding mismatch")
    if parent.get("p2_runtime") != p2_comparison.get("gates", {}).get("production_runtime"):
        raise ValueError("P2 runtime gate binding mismatch")
    implementation = spec.get("implementation_contract")
    if verify_implementation:
        if not isinstance(implementation, Mapping) or not isinstance(implementation.get("artifacts"), Mapping):
            raise ValueError("P3 implementation contract missing")
        hashes = {
            str(name): _sha256_file(_validate_artifact_ref(ref, f"implementation {name}"))
            for name, ref in implementation["artifacts"].items()
        }
        if implementation.get("sha256") != _canonical_hash(dict(sorted(hashes.items()))):
            raise ValueError("P3 implementation contract fingerprint mismatch")
    _validate_frozen_implementation_contract(implementation)
    return spec, {
        "p1_comparison": p1_comparison,
        "p2_comparison": p2_comparison,
        "label_ledger": ledger,
        "dataset_readiness": readiness,
    }


def _base_shadow(*, generation_status: str = "COMPLETE", retrieval_blocked: bool = False):
    state = GroundingState(
        post_id=101,
        candidate_title="작품 A",
        candidate_url="https://example.test/a",
        retrieval=(
            RetrievalState(required=True, attempted=True, recovered=False)
            if retrieval_blocked
            else None
        ),
    )
    evidence = [
        EvidenceRecord(
            kind="candidate_preservation",
            candidate_title="작품 A",
            candidate_url="https://example.test/a",
            supports_publish=True,
        )
    ]
    decision = can_publish_title(state, evidence)
    return build_uncalibrated_selective_shadow(
        state,
        evidence,
        decision,
        generation_status=generation_status,
    )


def _policy(**overrides: Any) -> CalibrationEvaluationPolicy:
    values: dict[str, Any] = {
        "fixed_bin_edges": (0.0, 0.5, 1.0),
        "selector_max_error_probability": 0.49,
        "nil_min_probability": 0.60,
        "alpha": 0.05,
        "min_dev_rows": 2,
        "min_dev_per_truth_class": 1,
        "min_calibration_rows": 2,
        "min_calibration_per_truth_class": 1,
        "min_frozen_rows": 4,
        "min_per_truth_class": 2,
        "min_occupied_bin_rows": 1,
        "target_coverage": 0.50,
        "max_selective_risk_upper_bound": 1.0,
        "baseline_noninferiority_margin": 1.0,
        "min_candidate_recall_lower_bound": 0.0,
        "min_nil_prediction_count": 1,
        "min_nil_precision_lower_bound": 0.0,
        "min_nil_recall_lower_bound": 0.0,
        "paired_delta_ci_bounds": {
            "top_label_accuracy": -1.0,
            "brier": 2.0,
            "log_loss": 100.0,
            "ece": 1.0,
            "selective_risk": 1.0,
            "aurc": 1.0,
        },
        "policy_scope": "SYNTHETIC_CONTRACT_ONLY",
        "policy_origin": "PRE_REGISTERED_DEV_CALIBRATION",
    }
    values.update(overrides)
    return CalibrationEvaluationPolicy.create(**values)


def _assignment(
    *,
    example_id: str,
    post_id: str,
    split: str,
    truth_kind: str,
    truth_label: str,
    candidate_set_fingerprint: str,
    nonce: int,
) -> CalibrationSplitAssignment:
    hex_value = format(nonce % 16, "x") * 64
    source_value = format((nonce + 7) % 16, "x") * 64
    return CalibrationSplitAssignment(
        example_id=example_id,
        post_id=post_id,
        split_group_id=f"group-{example_id}",
        content_fingerprint=hex_value,
        source_group_fingerprint=source_value,
        split=split,
        truth_kind=truth_kind,
        truth_label=truth_label,
        label_provenance_sha256=SHA_A if split == "DEV" else SHA_B if split == "CALIBRATION" else SHA_C,
        candidate_set_fingerprint=candidate_set_fingerprint,
        gold_work_fingerprint=(
            _canonical_hash({"gold_work": truth_label})
            if truth_kind == "CANDIDATE"
            else None
        ),
        binding_status="UNIQUE" if truth_kind == "CANDIDATE" else "NOT_APPLICABLE",
        matched_candidate_ids=(truth_label,) if truth_kind == "CANDIDATE" else (),
    )


def _synthetic_manifest(base_shadow) -> CalibrationSplitManifest:
    candidate = base_shadow.event_probabilities[0].label
    candidate_set_fingerprint = base_shadow.candidate_set.candidate_set_fingerprint
    rows = (
        _assignment(example_id="dev-candidate", post_id="1", split="DEV", truth_kind="CANDIDATE", truth_label="cand_dev", candidate_set_fingerprint=SHA_D, nonce=1),
        _assignment(example_id="dev-nil", post_id="2", split="DEV", truth_kind="NIL", truth_label=NIL_LABEL, candidate_set_fingerprint=SHA_D, nonce=2),
        _assignment(example_id="cal-candidate", post_id="3", split="CALIBRATION", truth_kind="CANDIDATE", truth_label="cand_calibration", candidate_set_fingerprint=SHA_E, nonce=3),
        _assignment(example_id="cal-nil", post_id="4", split="CALIBRATION", truth_kind="NIL", truth_label=NIL_LABEL, candidate_set_fingerprint=SHA_E, nonce=4),
        _assignment(example_id="frozen-candidate-1", post_id="5", split="FROZEN_HOLDOUT", truth_kind="CANDIDATE", truth_label=candidate, candidate_set_fingerprint=candidate_set_fingerprint, nonce=5),
        _assignment(example_id="frozen-candidate-2", post_id="6", split="FROZEN_HOLDOUT", truth_kind="CANDIDATE", truth_label=candidate, candidate_set_fingerprint=candidate_set_fingerprint, nonce=6),
        _assignment(example_id="frozen-nil-1", post_id="7", split="FROZEN_HOLDOUT", truth_kind="NIL", truth_label=NIL_LABEL, candidate_set_fingerprint=candidate_set_fingerprint, nonce=7),
        _assignment(example_id="frozen-nil-2", post_id="8", split="FROZEN_HOLDOUT", truth_kind="NIL", truth_label=NIL_LABEL, candidate_set_fingerprint=candidate_set_fingerprint, nonce=8),
    )
    return CalibrationSplitManifest.create(
        assignments=rows,
        source_label_ledger_sha256=SHA_D,
        assignment_seed_sha256=SHA_E,
    )


def _artifact(
    manifest: CalibrationSplitManifest,
    policy: CalibrationEvaluationPolicy,
    *,
    scorer_fingerprint: str = SHA_F,
    temperature: float = 1.0,
) -> CalibrationArtifact:
    calibration_rows = [
        item for item in manifest.assignments if item.split == "CALIBRATION"
    ]
    fit_receipt = CalibrationFitReceipt.create(
        split_manifest_sha256=manifest.manifest_sha256,
        calibration_split_fingerprint=manifest.split_fingerprints["CALIBRATION"],
        scorer_fingerprint=scorer_fingerprint,
        fit_row_count=len(calibration_rows),
        candidate_truth_count=sum(item.truth_kind == "CANDIDATE" for item in calibration_rows),
        resolved_candidate_count=sum(
            item.truth_kind == "CANDIDATE" and item.binding_status == "UNIQUE"
            for item in calibration_rows
        ),
        unresolved_candidate_count=sum(
            item.truth_kind == "CANDIDATE" and item.binding_status != "UNIQUE"
            for item in calibration_rows
        ),
        nil_truth_count=sum(item.truth_kind == "NIL" for item in calibration_rows),
        unjudged_count=sum(item.truth_kind == "UNJUDGED" for item in calibration_rows),
        method="TEMPERATURE_SCALING",
        temperature=temperature,
    )
    return CalibrationArtifact.create(
        split_manifest_sha256=manifest.manifest_sha256,
        calibration_split_fingerprint=manifest.split_fingerprints["CALIBRATION"],
        frozen_holdout_fingerprint=manifest.split_fingerprints["FROZEN_HOLDOUT"],
        scorer_fingerprint=scorer_fingerprint,
        policy_sha256=policy.policy_sha256,
        fit_receipt=fit_receipt,
        method="TEMPERATURE_SCALING",
        temperature=temperature,
    )


def _score(
    base_shadow,
    artifact: CalibrationArtifact,
    *,
    example_id: str,
    post_id: str,
    raw_scores: Sequence[float],
) -> EventScoreVector:
    return EventScoreVector.create(
        example_id=example_id,
        post_id=post_id,
        split="FROZEN_HOLDOUT",
        base_shadow=base_shadow,
        raw_scores=raw_scores,
        scorer_fingerprint=artifact.scorer_fingerprint,
        split_manifest_sha256=artifact.split_manifest_sha256,
        generation_proof_fingerprint=SHA_A,
        retrieval_state_fingerprint=SHA_B,
        feature_schema_version="candidate_probability_features_v1",
        feature_fingerprint=SHA_C,
    )


def _build_bound(
    base_shadow,
    score: EventScoreVector,
    artifact: CalibrationArtifact,
    policy: CalibrationEvaluationPolicy,
    manifest: CalibrationSplitManifest,
):
    assignment = next(
        item for item in manifest.assignments if item.example_id == score.example_id
    )
    return build_calibration_shadow(
        base_shadow,
        score,
        artifact,
        policy,
        split_manifest=manifest,
        assignment=assignment,
    )


def _build_synthetic_bundle(
    policy: Optional[CalibrationEvaluationPolicy] = None,
) -> dict[str, Any]:
    base = _base_shadow()
    policy = policy or _policy()
    manifest = _synthetic_manifest(base)
    artifact = _artifact(manifest, policy)
    baseline_artifact = _artifact(
        manifest,
        policy,
        scorer_fingerprint=SHA_BASELINE,
    )
    before_raw_scores = {
        "frozen-candidate-1": (1.0, 0.0),
        "frozen-candidate-2": (0.0, 1.0),
        "frozen-nil-1": (0.0, 1.0),
        "frozen-nil-2": (1.0, 0.0),
    }
    after_raw_scores = {
        "frozen-candidate-1": (3.0, 0.0),
        "frozen-candidate-2": (3.0, 0.0),
        "frozen-nil-1": (0.0, 3.0),
        "frozen-nil-2": (0.0, 3.0),
    }
    post_ids = {
        "frozen-candidate-1": "5",
        "frozen-candidate-2": "6",
        "frozen-nil-1": "7",
        "frozen-nil-2": "8",
    }
    before_scores = {
        example_id: _score(
            base,
            baseline_artifact,
            example_id=example_id,
            post_id=post_ids[example_id],
            raw_scores=raw_scores,
        )
        for example_id, raw_scores in before_raw_scores.items()
    }
    after_scores = {
        example_id: _score(
            base,
            artifact,
            example_id=example_id,
            post_id=post_ids[example_id],
            raw_scores=raw_scores,
        )
        for example_id, raw_scores in after_raw_scores.items()
    }
    before = {
        example_id: _build_bound(
            base,
            score,
            baseline_artifact,
            policy,
            manifest,
        )
        for example_id, score in before_scores.items()
    }
    after = {
        example_id: _build_bound(
            base,
            score,
            artifact,
            policy,
            manifest,
        )
        for example_id, score in after_scores.items()
    }
    base_shadows = {example_id: base for example_id in after_scores}
    report = evaluate_frozen_holdout(
        split_manifest=manifest,
        shadows=after,
        baseline_shadows=before,
        policy=policy,
        evidence_mode="SYNTHETIC_CONTRACT_ONLY",
        base_shadows=base_shadows,
        score_vectors=after_scores,
        calibration_artifact=artifact,
        baseline_base_shadows=base_shadows,
        baseline_score_vectors=before_scores,
        baseline_calibration_artifact=baseline_artifact,
    )
    return {
        "base": base,
        "policy": policy,
        "manifest": manifest,
        "artifact": artifact,
        "baseline_artifact": baseline_artifact,
        "base_shadows": base_shadows,
        "before_scores": before_scores,
        "after_scores": after_scores,
        "before": before,
        "after": after,
        "report": report,
    }


def _legacy_unbound_numeric_claim(base_shadow) -> bool:
    payload = copy.deepcopy(base_shadow.to_dict())
    labels = [item["label"] for item in payload["event_probabilities"]]
    payload["event_probabilities"] = [
        {"label": label, "probability": 0.1 if index == 0 else 0.9}
        for index, label in enumerate(labels)
    ]
    payload["probability_status"] = CALIBRATED_SHADOW_STATUS
    payload["selected_label"] = labels[0]
    payload["action"] = "RESOLVE"
    fingerprint_payload = {
        key: value for key, value in payload.items() if key != "shadow_fingerprint"
    }
    payload["shadow_fingerprint"] = _canonical_hash(fingerprint_payload)
    parsed = selective_shadow_from_dict(payload)
    return parsed.probability_status == CALIBRATED_SHADOW_STATUS


def _case(name: str, callback: Callable[[], bool], expected_ko: str) -> dict[str, Any]:
    try:
        passed = callback() is True
        observed = "PASS" if passed else "FALSE_GO_OR_WRONG_STATUS"
    except Exception as error:  # expected rejection is expressed by callback itself
        passed = False
        observed = f"UNEXPECTED_EXCEPTION: {error}"
    return {"case": name, "passed": passed, "expected_ko": expected_ko, "observed": observed}


def _raises(callback: Callable[[], Any], pattern: str) -> bool:
    try:
        callback()
    except Exception as error:
        return pattern in str(error)
    return False


def _adversarial_cases(bundle: Mapping[str, Any]) -> list[dict[str, Any]]:
    base = bundle["base"]
    policy = bundle["policy"]
    manifest = bundle["manifest"]
    artifact = bundle["artifact"]
    baseline_artifact = bundle["baseline_artifact"]
    assignments = {item.example_id: item for item in manifest.assignments}
    first_after = bundle["after"]["frozen-candidate-1"]
    valid_score = _score(base, artifact, example_id="frozen-candidate-1", post_id="5", raw_scores=(3.0, 0.0))

    def _evaluate(
        shadows,
        *,
        baseline_shadows=None,
        baseline_score_vectors=None,
        evidence_mode="SYNTHETIC_CONTRACT_ONLY",
    ):
        return evaluate_frozen_holdout(
            split_manifest=manifest,
            shadows=shadows,
            policy=policy,
            evidence_mode=evidence_mode,
            base_shadows=bundle["base_shadows"],
            score_vectors=bundle["after_scores"],
            calibration_artifact=artifact,
            baseline_shadows=baseline_shadows,
            baseline_base_shadows=(
                bundle["base_shadows"] if baseline_shadows is not None else None
            ),
            baseline_score_vectors=baseline_score_vectors,
            baseline_calibration_artifact=(
                baseline_artifact if baseline_shadows is not None else None
            ),
        )

    cases: list[dict[str, Any]] = []
    cases.append(_case("missing_artifact_all_null", lambda: build_calibration_shadow(base, None, None, policy).schema_version == CALIBRATION_UNAVAILABLE_SCHEMA, "보정 산출물이 없으면 확률 null"))
    cases.append(_case("unknown_generation_all_null", lambda: build_calibration_shadow(_base_shadow(generation_status="UNKNOWN"), None, None, policy).probability_status == PROBABILITY_STATUS, "후보 완전성 UNKNOWN이면 숫자 금지"))
    cases.append(_case("missing_split_assignment_all_null", lambda: build_calibration_shadow(base, valid_score, artifact, policy).schema_version == CALIBRATION_UNAVAILABLE_SCHEMA, "split/행 결속이 없으면 확률 null"))
    blocked_base = _base_shadow(retrieval_blocked=True)
    blocked_score = _score(blocked_base, artifact, example_id="frozen-candidate-1", post_id="5", raw_scores=(9.0, 0.0))
    cases.append(_case("retrieval_block_forces_abstain", lambda: build_calibration_shadow(blocked_base, blocked_score, artifact, policy, split_manifest=manifest, assignment=assignments["frozen-candidate-1"]).action == "ABSTAIN", "검색 blocker가 있으면 고확률이어도 보류"))
    rows = list(manifest.assignments)
    rows[4] = replace(rows[4], split_group_id=rows[0].split_group_id)
    cases.append(_case("split_group_leakage_rejected", lambda: _raises(lambda: CalibrationSplitManifest.create(assignments=rows, source_label_ledger_sha256=SHA_D, assignment_seed_sha256=SHA_E), "split-group leakage"), "같은 그룹의 split 교차 금지"))
    rows = list(manifest.assignments)
    rows[4] = replace(rows[4], content_fingerprint=rows[0].content_fingerprint)
    cases.append(_case("content_leakage_rejected", lambda: _raises(lambda: CalibrationSplitManifest.create(assignments=rows, source_label_ledger_sha256=SHA_D, assignment_seed_sha256=SHA_E), "content leakage"), "같은 본문의 split 교차 금지"))
    cases.append(_case("score_label_order_rejected", lambda: _raises(lambda: build_calibration_shadow(base, replace(valid_score, labels=tuple(reversed(valid_score.labels))), artifact, policy, split_manifest=manifest, assignment=assignments["frozen-candidate-1"]), "labels"), "후보/NIL 순서 변조 거부"))
    cases.append(_case("candidate_set_fingerprint_rejected", lambda: _raises(lambda: build_calibration_shadow(base, replace(valid_score, candidate_set_fingerprint=SHA_A), artifact, policy, split_manifest=manifest, assignment=assignments["frozen-candidate-1"]), "candidate-set fingerprint"), "다른 CandidateSet 점수 재사용 거부"))
    cases.append(_case("policy_binding_rejected", lambda: _raises(lambda: build_calibration_shadow(base, valid_score, replace(artifact, policy_sha256=SHA_A), policy, split_manifest=manifest, assignment=assignments["frozen-candidate-1"]), "policy"), "사전 정책 SHA 불일치 거부"))
    cases.append(_case("split_manifest_binding_rejected", lambda: _raises(lambda: build_calibration_shadow(base, replace(valid_score, split_manifest_sha256=SHA_A), artifact, policy, split_manifest=manifest, assignment=assignments["frozen-candidate-1"]), "split manifest"), "split manifest SHA 불일치 거부"))
    cases.append(_case("assignment_exact_binding_required", lambda: _raises(lambda: build_calibration_shadow(base, valid_score, artifact, policy, split_manifest=manifest, assignment=replace(assignments["frozen-candidate-1"], post_id="999")), "exactly bound"), "manifest에 없는 변조 행 거부"))
    cases.append(_case("synthetic_never_conversion", lambda: bundle["report"]["conversion_allowed"] is False, "합성 지표는 배포 승인 금지"))
    cases.append(_case("frozen_actual_rejects_synthetic_policy", lambda: _evaluate(bundle["after"], baseline_shadows=bundle["before"], baseline_score_vectors=bundle["before_scores"], evidence_mode="FROZEN_ACTUAL")["status"] == "NO_GO_POLICY_SCOPE_MISMATCH", "합성 전용 정책으로 실제 FROZEN을 주장할 수 없음"))
    actual_policy = _policy(
        policy_scope="FROZEN_ACTUAL_PRE_REGISTERED",
        min_candidate_recall_lower_bound=0.01,
        min_nil_precision_lower_bound=0.01,
        min_nil_recall_lower_bound=0.01,
    )
    actual_bundle = _build_synthetic_bundle(actual_policy)
    cases.append(
        _case(
            "frozen_actual_requires_evidence_receipt",
            lambda: evaluate_frozen_holdout(
                split_manifest=actual_bundle["manifest"],
                shadows=actual_bundle["after"],
                baseline_shadows=actual_bundle["before"],
                policy=actual_policy,
                evidence_mode="FROZEN_ACTUAL",
                base_shadows=actual_bundle["base_shadows"],
                score_vectors=actual_bundle["after_scores"],
                calibration_artifact=actual_bundle["artifact"],
                baseline_base_shadows=actual_bundle["base_shadows"],
                baseline_score_vectors=actual_bundle["before_scores"],
                baseline_calibration_artifact=actual_bundle["baseline_artifact"],
            )["status"]
            == "NOT_ESTIMABLE_ACTUAL_EVIDENCE_MISSING",
            "실제 FROZEN 표기는 불변 증거 영수증 없이는 NO-GO",
        )
    )
    swapped_baseline = dict(bundle["before"])
    swapped_baseline["frozen-candidate-1"] = bundle["before"]["frozen-nil-1"]
    swapped_baseline["frozen-nil-1"] = bundle["before"]["frozen-candidate-1"]
    cases.append(_case("baseline_exact_row_binding_required", lambda: _evaluate(bundle["after"], baseline_shadows=swapped_baseline, baseline_score_vectors=bundle["before_scores"])["status"] == "NO_GO_BASELINE_INVALID_BINDING", "baseline은 같은 frozen 행·정책에 결속"))
    post_ids = {
        "frozen-candidate-1": "5",
        "frozen-candidate-2": "6",
        "frozen-nil-1": "7",
        "frozen-nil-2": "8",
    }
    no_nil_scores = {
        example_id: _score(
            base,
            artifact,
            example_id=example_id,
            post_id=post_id,
            raw_scores=(3.0, 0.0),
        )
        for example_id, post_id in post_ids.items()
    }
    no_nil = {
        example_id: _build_bound(base, score, artifact, policy, manifest)
        for example_id, score in no_nil_scores.items()
    }
    no_nil_report = evaluate_frozen_holdout(
        split_manifest=manifest,
        shadows=no_nil,
        policy=policy,
        evidence_mode="SYNTHETIC_CONTRACT_ONLY",
        base_shadows=bundle["base_shadows"],
        score_vectors=no_nil_scores,
        calibration_artifact=artifact,
    )
    cases.append(_case("nil_zero_prediction_is_not_perfect", lambda: no_nil_report["metrics"]["nil_precision"] is None and no_nil_report["conversion_allowed"] is False, "NIL 예측 0건은 precision 100%가 아니라 null이며 승인 금지"))
    bad_rows = list(manifest.assignments)
    bad_rows[4] = replace(
        bad_rows[4],
        truth_label=None,
        binding_status="MISSING",
        matched_candidate_ids=(),
    )
    bad_manifest = CalibrationSplitManifest.create(assignments=bad_rows, source_label_ledger_sha256=SHA_D, assignment_seed_sha256=SHA_E)
    bad_artifact = _artifact(bad_manifest, policy)
    bad_scores = {
        example_id: _score(
            base,
            bad_artifact,
            example_id=example_id,
            post_id=post_id,
            raw_scores=(3.0, 0.0) if "candidate" in example_id else (0.0, 3.0),
        )
        for example_id, post_id in post_ids.items()
    }
    bad_shadows = {
        example_id: _build_bound(base, score, bad_artifact, policy, bad_manifest)
        for example_id, score in bad_scores.items()
    }
    cases.append(_case("candidate_miss_not_relabelled_nil", lambda: evaluate_frozen_holdout(split_manifest=bad_manifest, shadows=bad_shadows, policy=policy, evidence_mode="SYNTHETIC_CONTRACT_ONLY", base_shadows=bundle["base_shadows"], score_vectors=bad_scores, calibration_artifact=bad_artifact)["status"] == "NOT_EVALUABLE_CANDIDATE_SET_INCOMPLETE", "정답 후보 누락은 NIL/제외로 세탁 금지"))
    strict = _policy(min_frozen_rows=5)
    strict_bundle = _build_synthetic_bundle(strict)
    cases.append(_case("small_sample_no_number", lambda: strict_bundle["report"]["status"] == "NOT_ESTIMABLE_SMALL_SAMPLE" and all(value is None for value in strict_bundle["report"]["metrics"].values()), "소표본은 0/100 대신 null"))
    cases.append(_case("frozen_tuned_policy_rejected", lambda: _raises(lambda: _policy(policy_origin="TUNED_ON_FROZEN_HOLDOUT"), "policy_origin"), "FROZEN 기준 정책 튜닝 금지"))
    tampered = first_after.to_dict()
    tampered["event_probabilities"][0]["probability_mass"] += 1
    cases.append(_case("probability_mass_tamper_rejected", lambda: _raises(lambda: calibration_shadow_from_dict(tampered), "probability"), "확률 질량 합·지문 변조 거부"))
    return cases


def build_comparison(
    run_spec_path: str | Path,
    *,
    verify_implementation: bool = True,
) -> dict[str, Any]:
    spec, context = validate_run_spec(
        run_spec_path,
        verify_implementation=verify_implementation,
    )
    p1 = context["p1_comparison"]
    p2 = context["p2_comparison"]
    ledger = context["label_ledger"]
    readiness = context["dataset_readiness"]
    summary = p1.get("summary", {})
    p1_gates = p1.get("gates", {})
    golden_metrics = {
        "candidate_set_recall": None,
        "top_label_accuracy": None,
        "multiclass_brier": None,
        "log_loss": None,
        "top_label_ece": None,
        "nil_precision": None,
        "nil_recall": None,
        "coverage": None,
        "selective_risk": None,
        "aurc": None,
    }
    bundle = _build_synthetic_bundle()
    legacy_accepted = int(_legacy_unbound_numeric_claim(bundle["base"]))
    after_missing = build_calibration_shadow(bundle["base"], None, None, bundle["policy"])
    attacks = _adversarial_cases(bundle)
    passed = sum(item["passed"] is True for item in attacks)
    false_go = len(attacks) - passed
    report = {
        "schema_version": REPORT_SCHEMA,
        "generated_at": _now(),
        "mode": MODE,
        "run_spec": {
            "path": _stored_path(run_spec_path),
            "file_sha256": _sha256_file(_resolve_path(run_spec_path)),
            "self_hash": spec["run_spec_sha256"],
        },
        "golden18_readiness": {
            "row_count": summary.get("candidate_nil_event_rows"),
            "truth_counts": ledger.get("counts"),
            "generation_status": summary.get("generation_status"),
            "candidate_set_recall": p1_gates.get("candidate_set_recall"),
            "all_probability_null": summary.get("all_probability_null"),
            "public_contract_unchanged_rows": summary.get("public_contract_unchanged_rows"),
            "dataset_readiness_gate": readiness["gate"],
            "dataset_readiness_manifest_sha256": readiness["manifest_sha256"],
            "dataset_readiness_counts": readiness["counts"],
            "headline_metrics": golden_metrics,
            "status": "NO_GO_ACTUAL_DATASET_NOT_READY",
            "reason_ko": "Golden18 준비도 점검은 producer COMPLETE 0/18, 미판정 3건, split·candidate-ID·actual 정책 provenance 누락을 확인했으므로 정확도 퍼센트를 계산하지 않는다.",
            "conversion_allowed": False,
        },
        "before_after": {
            "before": {
                "meaning_ko": "기존 P1 구조형은 숫자 벡터의 합만 맞으면 보정 산출물·split 증명 없이 CALIBRATED_SHADOW 문자열을 받을 수 있었다.",
                "unbound_numeric_claim_accepted": legacy_accepted,
            },
            "after": {
                "meaning_ko": "P3 권위 sidecar는 보정 산출물·fit receipt·split·scorer·정책·CandidateSet 지문이 모두 결속되지 않으면 숫자를 만들지 않는다.",
                "unbound_numeric_claim_accepted": 0,
                "missing_artifact_schema": after_missing.schema_version,
                "missing_artifact_status": after_missing.probability_status,
                "probabilities_all_null": all(item.probability is None for item in after_missing.event_probabilities),
            },
        },
        "synthetic_metric_contract": {
            "evidence_scope": "SYNTHETIC_CONTRACT_ONLY",
            "status": bundle["report"]["status"],
            "candidate_set_recall": bundle["report"]["candidate_set_recall"],
            "before_metrics": bundle["report"]["baseline_metrics"],
            "after_metrics": bundle["report"]["metrics"],
            "intervals": bundle["report"]["intervals"],
            "ece_bins": bundle["report"]["ece_bins"],
            "conversion_allowed": bundle["report"]["conversion_allowed"],
            "conversion_reason": bundle["report"]["conversion_reason"],
        },
        "metric_protocol": spec["metric_protocol"],
        "adversarial_contract": {
            "case_count": len(attacks),
            "passed_count": passed,
            "false_go_count": false_go,
            "cases": attacks,
        },
        "parent_evidence": {
            "p1_probability": p1_gates.get("probability"),
            "p1_candidate_set_recall": p1_gates.get("candidate_set_recall"),
            "p2_saved_gate": p2.get("gates", {}).get("saved_artifact_and_synthetic"),
            "p2_runtime": p2.get("gates", {}).get("production_runtime"),
        },
        "gates": {
            "artifact_integrity": "GO",
            "golden18_probability": "NOT_AVAILABLE_UNCALIBRATED",
            "golden18_candidate_set_recall": "NOT_EVALUABLE",
            "artifact_bound_sidecar_contract": "GO_SYNTHETIC_ONLY" if false_go == 0 else "NO-GO",
            "metric_math": "GO_SYNTHETIC_ONLY" if false_go == 0 else "NO-GO",
            "actual_calibration_dataset": readiness["gate"],
            "actual_preflight": "IMPLEMENTED_READ_ONLY_NO_ACTUAL_PACKET",
            "actual_artifact_readback": "IMPLEMENTED_V2_BOUND_RUNNER_NO_ACTUAL_ARTIFACT",
            "full_interval_protocol": "IMPLEMENTED_POLICY_BOUND_NO_ACTUAL_OUTPUT",
            "runtime_validation": "NOT_RUN",
            "semantic_quality": "REVIEW-LOCKED",
            "full_scan_approval": False,
            "overall": "GO_P3_CONTRACT_FOUNDATION_ONLY" if false_go == 0 else "NO-GO",
            "goal": "ACTIVE_NOT_COMPLETE",
        },
        "limits": [
            "Golden18은 generation UNKNOWN이며 실제 확률 지표의 분모가 아니다.",
            "합성 전후 수치는 계산식과 fail-close 계약 시험일 뿐 모델 품질 증거가 아니다.",
            "dataset readiness v2는 producer COMPLETE 0/18, 미판정 3건과 split·candidate-ID·actual 정책 provenance 누락을 NO-GO로 고정했다.",
            "actual-preflight는 필수 파일·replay 6종·readiness·bound readback 가능 여부를 무쓰기/무런타임으로 점검하지만 실제 증거를 생성하거나 성능 GO를 만들지 않는다.",
            "FROZEN_ACTUAL readback v2 bound runner는 정책·P1·라벨 원장·외부 expected universe·producer·after·baseline을 파일에서 재판독해 SHA를 유도한다. 현재 실제 자료가 없으므로 수치는 전부 null이다.",
            "정확도·Brier·log loss·ECE·선택 위험·AURC의 paired CI 정책 게이트는 구현됐지만 실제 출력 구간은 아직 없다.",
            "P3 sidecar는 공개 결과를 바꾸지 않으며 full_scan 승인을 만들지 않는다.",
        ],
    }
    return report


def _validate_comparison_report(
    report: Mapping[str, Any],
    *,
    verify_implementation: bool = True,
) -> dict[str, Any]:
    try:
        report = copy.deepcopy(dict(report))
    except (TypeError, ValueError) as error:
        raise ValueError(f"P3 comparison report snapshot failed: {error}") from error
    expected_keys = {
        "schema_version",
        "generated_at",
        "mode",
        "run_spec",
        "golden18_readiness",
        "before_after",
        "synthetic_metric_contract",
        "metric_protocol",
        "adversarial_contract",
        "parent_evidence",
        "gates",
        "limits",
    }
    if not isinstance(report, Mapping) or set(report) != expected_keys:
        raise ValueError("P3 comparison report shape mismatch")
    if report.get("schema_version") != REPORT_SCHEMA or report.get("mode") != MODE:
        raise ValueError("P3 comparison report schema/mode mismatch")
    run_spec_ref = report.get("run_spec")
    if not isinstance(run_spec_ref, Mapping):
        raise ValueError("P3 comparison run spec reference missing")
    run_spec_path = _resolve_path(str(run_spec_ref.get("path") or ""))
    if not run_spec_path.is_file():
        raise ValueError("P3 comparison run spec file missing")
    if _sha256_file(run_spec_path) != run_spec_ref.get("file_sha256"):
        raise ValueError("P3 comparison run spec file binding mismatch")
    run_spec, _ = validate_run_spec(
        run_spec_path,
        verify_implementation=verify_implementation,
    )
    if run_spec_ref.get("self_hash") != run_spec.get("run_spec_sha256"):
        raise ValueError("P3 comparison run spec self-hash mismatch")
    if report.get("metric_protocol") != run_spec.get("metric_protocol"):
        raise ValueError("P3 comparison metric protocol mismatch")

    golden = report.get("golden18_readiness")
    if not isinstance(golden, Mapping):
        raise ValueError("P3 Golden18 readiness block missing")
    headline = golden.get("headline_metrics")
    if (
        golden.get("status") != "NO_GO_ACTUAL_DATASET_NOT_READY"
        or golden.get("dataset_readiness_gate") != "NO_GO_ACTUAL_DATASET_NOT_READY"
        or golden.get("dataset_readiness_counts", {}).get("ready_rows") != 0
        or golden.get("conversion_allowed") is not False
        or not isinstance(headline, Mapping)
        or any(value is not None for value in headline.values())
    ):
        raise ValueError("P3 Golden18 no-number boundary mismatch")

    comparison = report.get("before_after")
    if not isinstance(comparison, Mapping):
        raise ValueError("P3 before/after block missing")
    after = comparison.get("after")
    if (
        not isinstance(after, Mapping)
        or after.get("unbound_numeric_claim_accepted") != 0
        or after.get("probabilities_all_null") is not True
    ):
        raise ValueError("P3 authoritative sidecar boundary mismatch")

    synthetic = report.get("synthetic_metric_contract")
    if (
        not isinstance(synthetic, Mapping)
        or synthetic.get("evidence_scope") != "SYNTHETIC_CONTRACT_ONLY"
        or synthetic.get("status") != "GO_SYNTHETIC_METRIC_CONTRACT_ONLY"
        or synthetic.get("conversion_allowed") is not False
        or synthetic.get("conversion_reason") != "SYNTHETIC_EVIDENCE_NEVER_DEPLOYMENT"
    ):
        raise ValueError("P3 synthetic evidence boundary mismatch")

    attacks = report.get("adversarial_contract")
    if not isinstance(attacks, Mapping) or not isinstance(attacks.get("cases"), list):
        raise ValueError("P3 adversarial contract missing")
    cases = attacks["cases"]
    passed = sum(item.get("passed") is True for item in cases if isinstance(item, Mapping))
    if (
        attacks.get("case_count") != len(cases)
        or attacks.get("passed_count") != passed
        or attacks.get("false_go_count") != len(cases) - passed
    ):
        raise ValueError("P3 adversarial summary mismatch")

    gates = report.get("gates")
    expected_gate_keys = {
        "artifact_integrity",
        "golden18_probability",
        "golden18_candidate_set_recall",
        "artifact_bound_sidecar_contract",
        "metric_math",
        "actual_calibration_dataset",
        "actual_preflight",
        "actual_artifact_readback",
        "full_interval_protocol",
        "runtime_validation",
        "semantic_quality",
        "full_scan_approval",
        "overall",
        "goal",
    }
    expected_overall = (
        "GO_P3_CONTRACT_FOUNDATION_ONLY"
        if attacks.get("false_go_count") == 0
        else "NO-GO"
    )
    expected_scoped_gate = (
        "GO_SYNTHETIC_ONLY" if attacks.get("false_go_count") == 0 else "NO-GO"
    )
    if (
        not isinstance(gates, Mapping)
        or set(gates) != expected_gate_keys
        or gates.get("artifact_integrity") != "GO"
        or gates.get("golden18_probability") != "NOT_AVAILABLE_UNCALIBRATED"
        or gates.get("golden18_candidate_set_recall") != "NOT_EVALUABLE"
        or gates.get("artifact_bound_sidecar_contract") != expected_scoped_gate
        or gates.get("metric_math") != expected_scoped_gate
        or gates.get("actual_calibration_dataset") != "NO_GO_ACTUAL_DATASET_NOT_READY"
        or gates.get("actual_preflight") != "IMPLEMENTED_READ_ONLY_NO_ACTUAL_PACKET"
        or gates.get("actual_artifact_readback")
        != "IMPLEMENTED_V2_BOUND_RUNNER_NO_ACTUAL_ARTIFACT"
        or gates.get("full_interval_protocol")
        != "IMPLEMENTED_POLICY_BOUND_NO_ACTUAL_OUTPUT"
        or gates.get("runtime_validation") != "NOT_RUN"
        or gates.get("semantic_quality") != "REVIEW-LOCKED"
        or gates.get("full_scan_approval") is not False
        or gates.get("overall") != expected_overall
        or gates.get("goal") != "ACTIVE_NOT_COMPLETE"
    ):
        raise ValueError("P3 comparison approval boundary mismatch")
    return report


def render_markdown(report: Mapping[str, Any]) -> str:
    report = _validate_comparison_report(report)
    golden = report["golden18_readiness"]
    comparison = report["before_after"]
    synthetic = report["synthetic_metric_contract"]
    attacks = report["adversarial_contract"]
    gates = report["gates"]
    before = synthetic["before_metrics"]
    after = synthetic["after_metrics"]
    lines = [
        "# P3 정확도 퍼센트: 숫자를 만들기 전 계약 검증",
        "",
        "## 한눈에 보는 결론",
        "",
        f"- **Golden18에는 정확도 퍼센트를 만들지 않았다.** 후보 생성 상태가 `{golden['generation_status']}`이고 후보 재현율은 `{golden['candidate_set_recall']}`이므로 모든 지표는 `null`이다.",
        f"- **실제 데이터 준비도는 `{golden['dataset_readiness_gate']}`다.** 준비된 행은 `{golden['dataset_readiness_counts']['ready_rows']}/{golden['dataset_readiness_counts']['source_rows']}`이며, 미판정 `{golden['dataset_readiness_counts']['unjudged']}`건과 생산 완료 증거·분할·후보 ID·실제 정책 출처가 남아 있다.",
        f"- **보정됐다는 위조 경로를 분리했다.** 기존 구조형의 무결속 숫자 claim `{comparison['before']['unbound_numeric_claim_accepted']}`건을 P3 권위 sidecar에서는 `{comparison['after']['unbound_numeric_claim_accepted']}`건으로 막았다.",
        f"- **합성 공격 {attacks['case_count']}개를 모두 막았다.** 통과 `{attacks['passed_count']}/{attacks['case_count']}`, 거짓 통과 `{attacks['false_go_count']}`이다.",
        "- **합성 지표가 좋아져도 운영 승인이 아니다.** 계산식 검증용 전후 수치는 실제 모델·실제 정답셋 성능이 아니며 `conversion_allowed=false`다.",
        f"- 실제 runtime은 `{gates['runtime_validation']}`, 의미 품질은 `{gates['semantic_quality']}`, `full_scan_approval={str(gates['full_scan_approval']).lower()}`다.",
        "",
        "## 무엇이 달라졌나",
        "",
        "| 구분 | 개선 전 | 개선 후 |",
        "| --- | --- | --- |",
        f"| 보정 출처 | 합계가 1인 숫자와 `CALIBRATED_SHADOW` 문자열만으로 구조형 생성 가능 | 보정기 학습 영수증·개발/보정/동결 분할·점수 생성기·정책·후보 묶음·입력 특징 지문이 모두 필요 |",
        f"| 보정 산출물 없음 | 무결속 claim `{comparison['before']['unbound_numeric_claim_accepted']}` | 확률 전부 `null`, 상태 `{comparison['after']['missing_artifact_status']}` |",
        "| 확률 합 | 부동소수 합 허용 | 후보 ID+NIL의 정수 질량 합을 `1,000,000`으로 정확히 고정 |",
        "| 검색·후보 blocker | 숫자형 구조와 RESOLVE가 공존 가능 | 검색 미복구·후보 UNKNOWN/TRUNCATED·무결성 실패는 ABSTAIN 또는 숫자 없음 |",
        "| 실제 파일 판독 | producer가 자기 자신을 예상 행 집합으로 삼고 baseline은 파일 해시만 보관할 수 있음 | 외부 예상 행 집합과 producer·개선 후·baseline을 각각 다시 읽어 행 의미 영수증을 만들고, bootstrap seed·반복 횟수까지 평가 계획 해시에 결속 |",
        "| 신뢰구간 판정 | 신뢰구간을 계산해도 값이 정책 한계를 넘는지 GO 판정에 쓰지 않음 | 실제 자동처리 범위·위험 상한과 paired 정확도/Brier/log loss/ECE/선택 위험/AURC CI를 사전 정책 한계에 모두 대조 |",
        "| 실제 결과 영향 | 해석에 따라 오용 가능 | 별도 그림자 기록(sidecar)이며 `action_applied=false`, `NONE_SHADOW_ONLY` |",
        "",
        "## Golden18에서 왜 숫자가 없는가",
        "",
        f"Golden18 {golden['row_count']}행의 공개 결과는 `{golden['public_contract_unchanged_rows']}/18` 불변이지만, 사전 고정 생산 작업의 완료 영수증과 서로 겹치지 않는 세 데이터 분할이 없다. 따라서 후보 재현율·예측 비율 오차(ECE)·확률 벌점(Brier/자연로그 손실)·작품 없음 정밀도/재현율·자동 처리 범위별 위험·AURC를 계산하면 안 된다.",
        "",
        "| 준비도 항목 | 현재 값 | 의미 |",
        "| --- | ---: | --- |",
        f"| 전체 행 | {golden['dataset_readiness_counts']['source_rows']} | 준비도 점검 대상 |",
        f"| 작품 정답 / NIL 정답 / 미판정 | {golden['dataset_readiness_counts']['candidate_truth']} / {golden['dataset_readiness_counts']['nil_truth']} / {golden['dataset_readiness_counts']['unjudged']} | 미판정은 NIL로 바꾸지 않음 |",
        f"| 생산 완료 증거 | {golden['dataset_readiness_counts']['generation_complete']} | `COMPLETE` 영수증이 없으면 실제 평가 분모에서 제외 |",
        f"| 실제 분할 가능 행 | {golden['dataset_readiness_counts']['ready_rows']} | 0이므로 DEV/CALIBRATION/FROZEN manifest를 만들지 않음 |",
        "",
        "`actual-preflight`는 실제 파일을 쓰거나 모델을 실행하지 않고 필수 입력 10종, replay 6종, 정책·readiness, strict bound readback 시도 가능 여부를 한 번에 보여준다. 이 결과가 GO여도 이어지는 `actual-readback`이 모든 파일을 다시 읽으므로 사전점검 자체는 성능 증거가 아니다.",
        "",
        "`actual-readback v2 bound runner`는 나중에 실제 파일이 생겼을 때 누락 행을 producer 스스로 숨기지 못하게 한다. 정책·P1 RunSpec·비교표·P1 결속 라벨 원장과 외부 예상 행 목록, producer 결과, 개선 후 예측, baseline 예측을 독립적으로 다시 읽고 SHA를 파일에서 유도한다. 수동 SHA 인자는 받지 않는다. 현재는 실제 파일이 없으므로 구현 완료가 곧 성능 검증 완료를 뜻하지 않는다.",
        "",
        "## 합성 계산식 전후 확인",
        "",
        "| 지표 | 개선 전 합성 | 개선 후 합성 | 의미 |",
        "| --- | ---: | ---: | --- |",
        f"| 최고 확률 후보 적중률 | {before['top_label_accuracy']:.3f} | {after['top_label_accuracy']:.3f} | 계산식 방향 확인용 |",
        f"| 다중 클래스 Brier | {before['multiclass_brier']:.6f} | {after['multiclass_brier']:.6f} | 낮을수록 좋음 |",
        f"| 자연로그 손실 | {before['log_loss']:.6f} | {after['log_loss']:.6f} | 낮을수록 좋음 |",
        f"| ECE | {before['top_label_ece']:.6f} | {after['top_label_ece']:.6f} | 고정 bin 산술 확인 |",
        "",
        "이 표는 인위적으로 만든 4행을 대상으로 수식이 개선 방향을 반영하는지만 본다. 실제 정확도 향상 수치로 인용하면 안 된다.",
        "",
        "### 각 수치가 하는 일",
        "",
        "| 수치 | 쉬운 뜻 | 주의할 점 |",
        "| --- | --- | --- |",
        "| 후보 목록 재현율 | 실제 정답 작품이 비교 대상 후보 안에 들어온 비율 | 후보 생성이 `COMPLETE`이고 정답 원장이 결속된 행만 분모로 사용 |",
        "| 최고 후보 정확도 | 가장 큰 확률을 준 후보가 실제 정답인 비율 | 확률이 얼마나 정직한지는 별도 문제 |",
        "| Brier 점수 | 모든 후보와 NIL에 준 확률이 정답에서 얼마나 벗어났는지 재는 평균 벌점 | 낮을수록 좋음 |",
        "| 자연로그 손실 | 정답에 너무 낮은 확률을 준 예측을 크게 벌점 | 낮을수록 좋고 0% 정답 확률은 허용하지 않음 |",
        "| ECE | 예를 들어 80%라고 한 묶음이 실제로 약 80% 맞는지 보는 간격 | 고정 구간과 충분한 표본이 필요 |",
        "| NIL 정밀도·재현율 | 작품 없음이라고 한 것이 맞는 비율 / 실제 작품 없음 사례를 찾은 비율 | 예측 또는 실제 NIL이 0건이면 100%가 아니라 `null` |",
        "| 자동 처리 범위·선택 위험 | 보류하지 않은 비율 / 그중 틀린 비율 | 둘을 함께 봐야 보류를 늘린 착시를 막음 |",
        "| AURC | 낮은 위험 예측부터 자동 처리 범위를 넓힐 때 누적 오류 곡선의 평균 | 그룹 bootstrap 계산 기반은 구현됐지만 actual output은 없음 |",
        "",
        "paired CI는 같은 행의 개선 후 값에서 baseline 값을 뺀 차이의 신뢰구간이다. 정확도는 하한이 정책보다 낮으면 실패하고, 오류·손실·위험 계열은 상한이 정책보다 높으면 실패한다. 계산 가능하다는 사실만으로 GO가 되지 않는다.",
        "",
        "## 공격 검증",
        "",
        "| 공격 | 결과 | 막으려는 문제 |",
        "| --- | --- | --- |",
    ]
    for item in attacks["cases"]:
        lines.append(
            f"| `{item['case']}` | {'통과' if item['passed'] else '실패'} | {item['expected_ko']} |"
        )
    lines.extend(
        [
            "",
            "## 게이트",
            "",
            "| 게이트 | 상태 |",
            "| --- | --- |",
            f"| Golden18 확률 | `{gates['golden18_probability']}` |",
            f"| Golden18 후보 재현율 | `{gates['golden18_candidate_set_recall']}` |",
            f"| P3 sidecar 계약 | `{gates['artifact_bound_sidecar_contract']}` |",
            f"| 실제 보정 데이터 | `{gates['actual_calibration_dataset']}` |",
            f"| 실제 증거 무쓰기 사전점검 | `{gates['actual_preflight']}` |",
            f"| 실제 산출물 바이트 재검증 | `{gates['actual_artifact_readback']}` |",
            f"| 전체 신뢰구간 규약 | `{gates['full_interval_protocol']}` |",
            f"| 실제 runtime | `{gates['runtime_validation']}` |",
            f"| 의미 품질 | `{gates['semantic_quality']}` |",
            f"| 전체 승인 | `{str(gates['full_scan_approval']).lower()}` |",
            f"| 전체 목표 | `{gates['goal']}` |",
            "",
            "## 다음 완료 증거",
            "",
            "1. 실제 DEV/CALIBRATION/FROZEN_HOLDOUT을 중복 그룹 단위로 분리하고 manifest SHA를 고정한다.",
            "2. 실제 COMPLETE producer receipt가 있는 행만 후보 재현율 분모에 포함하되 누락·제외 사유를 전수 회계한다.",
            "3. CALIBRATION split에서만 보정기와 선택 임계를 정하고 FROZEN은 한 번만 평가한다.",
            "4. 동일 행·동일 coverage baseline과 신뢰구간 비열화 검사를 통과해도 shadow GO만 허용한다.",
            "5. 실제 공개 전환과 full-scan 승인은 별도 목표·별도 게이트로 유지한다.",
            "",
        ]
    )
    return "\n".join(lines)


def write_comparison(
    report: Mapping[str, Any],
    *,
    output_json: str | Path,
    output_md: str | Path,
) -> tuple[Path, Path]:
    report = _validate_comparison_report(report)
    json_path = _resolve_path(output_json)
    markdown_path = _resolve_path(output_md)
    if json_path == markdown_path or json_path.exists() or markdown_path.exists():
        raise ValueError("P3 comparison outputs must be distinct new files")
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    rendered = render_markdown(report)
    created: list[Path] = []
    try:
        with json_path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        created.append(json_path)
        with markdown_path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(rendered)
        created.append(markdown_path)
    except Exception:
        for created_path in reversed(created):
            created_path.unlink(missing_ok=True)
        raise
    if _read_json(json_path) != dict(report) or markdown_path.read_text(encoding="utf-8") != rendered:
        raise ValueError("stored P3 comparison readback mismatch")
    return json_path, markdown_path


def _build_actual_readback_manifest_from_files(
    *,
    artifact_root: str | Path,
    expected_universe_jsonl: str,
    producer_jsonl: str,
    prediction_jsonl: str,
    baseline_prediction_jsonl: str,
    additional_artifacts: Sequence[tuple[str, str]] = (),
    run_spec_sha256: str,
    source_digest_sha256: str,
    metric_protocol_sha256: str,
    seed: int,
    replicates: int,
) -> tuple[Path, dict[str, Any]]:
    """Private low-level receipt builder used only by bounded contract tests."""

    root = _resolve_path(artifact_root)
    expected_ref, expected_rows = snapshot_jsonl_rows(
        root,
        "expected_universe",
        expected_universe_jsonl,
    )
    producer_ref, producer_rows = snapshot_jsonl_rows(root, "producer", producer_jsonl)
    prediction_ref, prediction_rows = snapshot_jsonl_rows(root, "prediction", prediction_jsonl)
    baseline_ref, baseline_rows = snapshot_jsonl_rows(
        root,
        "baseline_prediction",
        baseline_prediction_jsonl,
    )
    refs = {
        "expected_universe": expected_ref,
        "producer": producer_ref,
        "prediction": prediction_ref,
        "baseline_prediction": baseline_ref,
    }
    for name, path in additional_artifacts:
        if not name or not path or name in refs:
            raise ValueError("additional artifact names must be non-empty and unique")
        refs[name] = snapshot_artifact(
            root,
            name,
            path,
            jsonl=Path(path).suffix.lower() == ".jsonl",
        )
    universe = expected_universe_readback(expected_rows)
    coverage = producer_coverage_receipt(expected_rows, producer_rows)
    prediction = prediction_payload_readback(expected_rows, prediction_rows)
    baseline_prediction = prediction_payload_readback(expected_rows, baseline_rows)
    manifest = build_readback_manifest(
        run_spec_sha256=run_spec_sha256,
        artifacts=refs,
        expected_universe=universe,
        producer_coverage=coverage,
        prediction=prediction,
        baseline_prediction=baseline_prediction,
        source_digest_sha256=source_digest_sha256,
        metric_protocol_sha256=metric_protocol_sha256,
        bootstrap_seed=seed,
        bootstrap_replicates=replicates,
    )
    validate_actual_readback_artifacts(root, manifest)
    return root, manifest


def build_actual_readback_manifest_from_files(**_: Any) -> tuple[Path, dict[str, Any]]:
    """Reject the former raw-SHA API; callers must use the bound runner."""

    raise ValueError(
        "raw SHA assertions are forbidden; use build_bound_actual_readback_from_files"
    )


def _actual_run_spec_self_hash(spec: Mapping[str, Any]) -> str:
    return _canonical_hash(
        {key: value for key, value in spec.items() if key != "run_spec_sha256"}
    )


def _split_manifest_from_dict(value: Mapping[str, Any]) -> CalibrationSplitManifest:
    required = {
        "schema_version",
        "assignments",
        "source_label_ledger_sha256",
        "assignment_seed_sha256",
        "split_fingerprints",
        "manifest_sha256",
    }
    if not isinstance(value, Mapping) or set(value) != required:
        raise ValueError("invalid actual split manifest shape")
    rows = value.get("assignments")
    if not isinstance(rows, list):
        raise ValueError("actual split manifest assignments missing")
    assignment_keys = {
        "example_id",
        "post_id",
        "split_group_id",
        "content_fingerprint",
        "source_group_fingerprint",
        "split",
        "truth_kind",
        "truth_label",
        "label_provenance_sha256",
        "candidate_set_fingerprint",
        "gold_work_fingerprint",
        "binding_status",
        "matched_candidate_ids",
    }
    assignments: list[CalibrationSplitAssignment] = []
    for row in rows:
        if not isinstance(row, Mapping) or set(row) != assignment_keys:
            raise ValueError("invalid actual split assignment shape")
        payload = dict(row)
        matched = payload.pop("matched_candidate_ids")
        if not isinstance(matched, list):
            raise ValueError("actual split matched_candidate_ids must be a list")
        assignments.append(
            CalibrationSplitAssignment(
                **payload,
                matched_candidate_ids=tuple(matched),
            )
        )
    return CalibrationSplitManifest(
        assignments=tuple(assignments),
        source_label_ledger_sha256=value.get("source_label_ledger_sha256"),
        assignment_seed_sha256=value.get("assignment_seed_sha256"),
        split_fingerprints=value.get("split_fingerprints"),
        manifest_sha256=value.get("manifest_sha256"),
        schema_version=value.get("schema_version"),
    )


def _validate_split_against_readiness(
    split_manifest: CalibrationSplitManifest,
    readiness: Mapping[str, Any],
    policy: CalibrationEvaluationPolicy,
) -> list[CalibrationSplitAssignment]:
    ready_rows = readiness.get("rows")
    if not isinstance(ready_rows, list):
        raise ValueError("actual readiness rows missing")
    readiness_by_post = {str(row.get("post_id") or ""): row for row in ready_rows}
    if (
        len(readiness_by_post) != len(ready_rows)
        or {item.post_id for item in split_manifest.assignments} != set(readiness_by_post)
    ):
        raise ValueError("actual split/readiness post universe mismatch")
    for assignment in split_manifest.assignments:
        row = readiness_by_post[assignment.post_id]
        expected_truth_label = (
            row.get("truth_candidate_id")
            if row.get("truth_kind") == "CANDIDATE"
            else NIL_LABEL
        )
        expected_matched = (
            (str(expected_truth_label),)
            if row.get("truth_kind") == "CANDIDATE"
            else ()
        )
        checks = {
            "truth_kind": assignment.truth_kind == row.get("truth_kind"),
            "truth_label": assignment.truth_label == expected_truth_label,
            "candidate_set_fingerprint": assignment.candidate_set_fingerprint
            == row.get("candidate_set_fingerprint"),
            "split_group_id": assignment.split_group_id == row.get("split_group_id"),
            "content_fingerprint": assignment.content_fingerprint
            == row.get("content_fingerprint"),
            "source_group_fingerprint": assignment.source_group_fingerprint
            == row.get("source_group_fingerprint"),
            "label_provenance_sha256": assignment.label_provenance_sha256
            == row.get("label_provenance_sha256"),
            "gold_work_fingerprint": assignment.gold_work_fingerprint
            == row.get("gold_work_fingerprint"),
            "binding_status": assignment.binding_status == row.get("binding_status"),
            "matched_candidate_ids": assignment.matched_candidate_ids == expected_matched,
        }
        if not all(checks.values()):
            failed = ",".join(key for key, passed in checks.items() if not passed)
            raise ValueError(f"actual split/readiness row mismatch: {assignment.post_id}: {failed}")
        if assignment.truth_kind not in {"CANDIDATE", "NIL"}:
            raise ValueError("actual split contains UNJUDGED rows")
    limits = {
        "DEV": (policy.min_dev_rows, policy.min_dev_per_truth_class),
        "CALIBRATION": (
            policy.min_calibration_rows,
            policy.min_calibration_per_truth_class,
        ),
        "FROZEN_HOLDOUT": (policy.min_frozen_rows, policy.min_per_truth_class),
    }
    for split, (minimum_rows, minimum_per_class) in limits.items():
        rows = [item for item in split_manifest.assignments if item.split == split]
        if len(rows) < minimum_rows or any(
            sum(item.truth_kind == truth_kind for item in rows) < minimum_per_class
            for truth_kind in ("CANDIDATE", "NIL")
        ):
            raise ValueError(f"actual split does not satisfy pre-registered minimums: {split}")
    return [
        item
        for item in split_manifest.assignments
        if item.split == "FROZEN_HOLDOUT"
    ]


def _validate_actual_source_manifest(
    value: Mapping[str, Any],
    frozen: Sequence[CalibrationSplitAssignment],
    *,
    artifact_root: Path | None = None,
) -> dict[str, ArtifactRef]:
    if not isinstance(value, Mapping) or set(value) != {
        "schema_version",
        "source_run_id",
        "rows",
        "manifest_sha256",
    }:
        raise ValueError("invalid actual source manifest shape")
    if value.get("schema_version") != ACTUAL_SOURCE_MANIFEST_SCHEMA:
        raise ValueError("unsupported actual source manifest schema")
    if not isinstance(value.get("source_run_id"), str) or not value["source_run_id"].strip():
        raise ValueError("actual source manifest run id missing")
    source_run_id = value["source_run_id"]
    rows = value.get("rows")
    if not isinstance(rows, list) or len(rows) != len(frozen):
        raise ValueError("actual source manifest row coverage mismatch")
    expected_order = [(item.example_id, item.post_id) for item in frozen]
    observed_order: list[tuple[str, str]] = []
    artifact_paths: set[str] = set()
    payload_refs: dict[str, ArtifactRef] = {}
    for row in rows:
        if not isinstance(row, Mapping) or set(row) != {
            "example_id",
            "post_id",
            "source_artifact",
        }:
            raise ValueError("invalid actual source manifest row")
        example_id = str(row.get("example_id") or "")
        post_id = str(row.get("post_id") or "")
        source_ref = row.get("source_artifact")
        logical_name = f"source_payload::{example_id}"
        if not isinstance(source_ref, Mapping) or set(source_ref) != {
            "logical_name",
            "relative_path",
            "bytes",
            "sha256",
            "canonical_payload_sha256",
            "row_count",
        }:
            raise ValueError("invalid actual source artifact ref")
        relative_path = source_ref.get("relative_path")
        if (
            source_ref.get("logical_name") != logical_name
            or not isinstance(relative_path, str)
            or not relative_path
            or relative_path in artifact_paths
        ):
            raise ValueError("actual source artifact identity/path mismatch")
        artifact_paths.add(relative_path)
        for field in ("sha256", "canonical_payload_sha256"):
            digest = source_ref.get(field)
            if (
                not isinstance(digest, str)
                or len(digest) != 64
                or any(character not in "0123456789abcdef" for character in digest)
            ):
                raise ValueError("invalid actual source artifact digest")
        if (
            isinstance(source_ref.get("bytes"), bool)
            or not isinstance(source_ref.get("bytes"), int)
            or source_ref["bytes"] < 0
            or source_ref.get("row_count") is not None
            and (
                isinstance(source_ref.get("row_count"), bool)
                or not isinstance(source_ref.get("row_count"), int)
                or source_ref["row_count"] < 0
            )
        ):
            raise ValueError("invalid actual source artifact size/count")
        if artifact_root is not None:
            suffix = Path(relative_path).suffix.lower()
            if suffix not in {".json", ".jsonl"}:
                raise ValueError("actual source payload must be JSON or JSONL")
            if suffix == ".json":
                current, payload = snapshot_json_object(
                    artifact_root,
                    logical_name,
                    relative_path,
                )
                payload_rows = [payload]
            else:
                current, payload_rows = snapshot_jsonl_rows(
                    artifact_root,
                    logical_name,
                    relative_path,
                )
                if not payload_rows:
                    raise ValueError("actual source payload rows missing")
            if current.to_dict() != dict(source_ref):
                raise ValueError("actual source payload snapshot mismatch")
            for payload_row in payload_rows:
                if (
                    payload_row.get("schema_version") != ACTUAL_SOURCE_PAYLOAD_SCHEMA
                    or payload_row.get("source_run_id") != source_run_id
                    or str(payload_row.get("example_id") or "") != example_id
                    or str(payload_row.get("post_id") or "") != post_id
                ):
                    raise ValueError("actual source payload identity mismatch")
            payload_refs[logical_name] = current
        observed_order.append((example_id, post_id))
    if observed_order != expected_order:
        raise ValueError("actual source manifest frozen order mismatch")
    if value.get("manifest_sha256") != _canonical_hash(
        {key: item for key, item in value.items() if key != "manifest_sha256"}
    ):
        raise ValueError("actual source manifest self hash mismatch")
    return payload_refs


def _artifact_source_matches(
    source: Mapping[str, Any],
    ref: Mapping[str, Any],
    label: str,
) -> None:
    if source.get("sha256") != ref.get("sha256") or source.get("bytes") != ref.get("bytes"):
        raise ValueError(f"{label} source snapshot mismatch")


def _actual_preflight_path(
    root: Path,
    logical_name: str,
    relative_path: str,
    expected_suffix: str | None,
) -> tuple[Path | None, dict[str, Any]]:
    status: dict[str, Any] = {
        "relative_path": relative_path,
        "expected_suffix": expected_suffix,
        "exists": False,
        "bytes": None,
        "error": None,
    }
    if not isinstance(relative_path, str) or not relative_path.strip():
        status["error"] = "EMPTY_RELATIVE_PATH"
        return None, status
    candidate = Path(relative_path)
    if candidate.is_absolute():
        status["error"] = "ABSOLUTE_PATH_FORBIDDEN"
        return None, status
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        status["error"] = "ARTIFACT_ROOT_ESCAPE"
        return None, status
    if expected_suffix is not None and resolved.suffix.lower() != expected_suffix:
        status["error"] = "UNEXPECTED_FILE_SUFFIX"
        return resolved, status
    if not resolved.is_file():
        status["error"] = "MISSING_FILE"
        return resolved, status
    status["exists"] = True
    status["bytes"] = resolved.stat().st_size
    return resolved, status


def build_actual_preflight_report(
    *,
    artifact_root: str | Path,
    p1_run_spec_json: str,
    p1_comparison_json: str,
    label_ledger_json: str,
    actual_evaluation_policy_json: str,
    split_manifest_json: str,
    source_manifest_json: str,
    expected_universe_jsonl: str,
    producer_jsonl: str,
    prediction_jsonl: str,
    baseline_prediction_jsonl: str,
    additional_artifacts: Sequence[tuple[str, str]] = (),
    seed: int,
    replicates: int,
) -> dict[str, Any]:
    """Read-only inventory/readiness check before the strict bound readback."""

    from tools.run_calibration_dataset_readiness import build_current_readiness

    root = _resolve_path(artifact_root)
    paths: dict[str, tuple[str, str | None]] = {
        "p1_run_spec": (p1_run_spec_json, ".json"),
        "p1_comparison": (p1_comparison_json, ".json"),
        "label_ledger": (label_ledger_json, ".json"),
        "actual_evaluation_policy": (actual_evaluation_policy_json, ".json"),
        "split_manifest": (split_manifest_json, ".json"),
        "source_manifest": (source_manifest_json, ".json"),
        "expected_universe": (expected_universe_jsonl, ".jsonl"),
        "producer": (producer_jsonl, ".jsonl"),
        "prediction": (prediction_jsonl, ".jsonl"),
        "baseline_prediction": (baseline_prediction_jsonl, ".jsonl"),
    }
    blockers: list[str] = []
    additional_names: set[str] = set()
    for name, relative_path in additional_artifacts:
        if not name or not relative_path or name in paths or name in additional_names:
            blockers.append(f"INVALID_ADDITIONAL_ARTIFACT::{name or '<empty>'}")
            continue
        additional_names.add(name)
        suffix = Path(relative_path).suffix.lower()
        paths[name] = (relative_path, suffix if suffix in {".json", ".jsonl"} else None)
        if suffix not in {".json", ".jsonl"}:
            blockers.append(f"INVALID_ARTIFACT_SUFFIX::{name}")
    for name in sorted(ACTUAL_REPLAY_ARTIFACT_NAMES - additional_names):
        blockers.append(f"MISSING_REPLAY_ARTIFACT::{name}")
    if (
        isinstance(seed, bool)
        or not isinstance(seed, int)
        or seed < 0
        or isinstance(replicates, bool)
        or not isinstance(replicates, int)
        or replicates <= 0
    ):
        blockers.append("INVALID_BOOTSTRAP_PLAN")

    statuses: dict[str, dict[str, Any]] = {}
    resolved_paths: dict[str, Path] = {}
    for name, (relative_path, expected_suffix) in sorted(paths.items()):
        resolved, status = _actual_preflight_path(
            root,
            name,
            relative_path,
            expected_suffix,
        )
        statuses[name] = status
        if status["error"] is not None:
            blockers.append(f"{status['error']}::{name}")
        elif resolved is not None:
            resolved_paths[name] = resolved

    readiness_summary: dict[str, Any] = {
        "evaluated": False,
        "ready_for_split_manifest": False,
        "gate": "NOT_EVALUATED",
        "counts": None,
        "manifest_sha256": None,
        "error": None,
    }
    readiness_names = {
        "p1_run_spec",
        "p1_comparison",
        "label_ledger",
        "actual_evaluation_policy",
    }
    if readiness_names.issubset(resolved_paths):
        try:
            readiness = build_current_readiness(
                p1_run_spec_path=resolved_paths["p1_run_spec"],
                p1_comparison_path=resolved_paths["p1_comparison"],
                label_ledger_path=resolved_paths["label_ledger"],
                actual_evaluation_policy_path=resolved_paths["actual_evaluation_policy"],
            )
            readiness_summary = {
                "evaluated": True,
                "ready_for_split_manifest": readiness.get("ready_for_split_manifest") is True,
                "gate": readiness.get("gate"),
                "counts": readiness.get("counts"),
                "manifest_sha256": readiness.get("manifest_sha256"),
                "error": None,
            }
            if readiness.get("ready_for_split_manifest") is not True:
                blockers.append("NO_GO_ACTUAL_DATASET_NOT_READY")
        except Exception as exc:
            readiness_summary["error"] = str(exc)
            blockers.append("READINESS_REPLAY_FAILED")

    bound_readback: dict[str, Any] = {
        "attempted": False,
        "eligible": False,
        "error": None,
        "actual_run_spec_sha256": None,
        "readback_manifest_sha256": None,
        "discovered_source_payloads": [],
    }
    if not blockers:
        bound_readback["attempted"] = True
        try:
            _, actual_run_spec, _, manifest = build_bound_actual_readback_from_files(
                artifact_root=root,
                p1_run_spec_json=p1_run_spec_json,
                p1_comparison_json=p1_comparison_json,
                label_ledger_json=label_ledger_json,
                actual_evaluation_policy_json=actual_evaluation_policy_json,
                split_manifest_json=split_manifest_json,
                source_manifest_json=source_manifest_json,
                expected_universe_jsonl=expected_universe_jsonl,
                producer_jsonl=producer_jsonl,
                prediction_jsonl=prediction_jsonl,
                baseline_prediction_jsonl=baseline_prediction_jsonl,
                additional_artifacts=additional_artifacts,
                seed=seed,
                replicates=replicates,
            )
            bound_readback.update(
                {
                    "eligible": True,
                    "actual_run_spec_sha256": actual_run_spec["run_spec_sha256"],
                    "readback_manifest_sha256": manifest["manifest_sha256"],
                    "discovered_source_payloads": [
                        {
                            "logical_name": name,
                            "relative_path": ref["relative_path"],
                            "bytes": ref["bytes"],
                            "sha256": ref["sha256"],
                        }
                        for name, ref in sorted(actual_run_spec["artifacts"].items())
                        if name.startswith("source_payload::")
                    ],
                }
            )
        except Exception as exc:
            bound_readback["error"] = str(exc)
            blockers.append("BOUND_READBACK_VALIDATION_FAILED")

    unique_blockers = sorted(set(blockers))
    report: dict[str, Any] = {
        "schema_version": ACTUAL_PREFLIGHT_SCHEMA,
        "mode": "READ_ONLY_NO_WRITE_NO_RUNTIME",
        "artifact_root": str(root),
        "artifacts": statuses,
        "readiness": readiness_summary,
        "bound_readback": bound_readback,
        "blockers": unique_blockers,
        "gate": (
            "GO_ACTUAL_BOUND_READBACK_ATTEMPT_ALLOWED"
            if bound_readback["eligible"]
            else "NO_GO_ACTUAL_PREFLIGHT"
        ),
        "writes_performed": False,
        "runtime_started": False,
        "actual_metrics": None,
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
    }
    report["report_sha256"] = _canonical_hash(report)
    return report


def validate_actual_evidence_run_spec(spec: Mapping[str, Any]) -> None:
    required = {
        "schema_version",
        "mode",
        "artifacts",
        "p1_run_spec_sha256",
        "dataset_readiness_manifest_sha256",
        "actual_evaluation_policy_sha256",
        "split_manifest_sha256",
        "source_label_ledger_sha256",
        "source_digest_sha256",
        "metric_protocol_sha256",
        "bootstrap_seed",
        "bootstrap_replicates",
        "runtime_validation",
        "semantic_quality",
        "full_scan_approval",
        "actual_metrics",
        "run_spec_sha256",
    }
    if not isinstance(spec, Mapping) or set(spec) != required:
        raise ValueError("invalid actual evidence RunSpec shape")
    if spec.get("schema_version") != ACTUAL_EVIDENCE_RUN_SPEC_SCHEMA:
        raise ValueError("unsupported actual evidence RunSpec schema")
    if spec.get("mode") != "FROZEN_ACTUAL_READBACK_FOUNDATION_NO_MODEL_RUNTIME":
        raise ValueError("actual evidence RunSpec mode mismatch")
    artifacts = spec.get("artifacts")
    expected_artifacts = {
        "p1_run_spec",
        "p1_comparison",
        "label_ledger",
        "actual_evaluation_policy",
        "split_manifest",
        "source_manifest",
        "expected_universe",
        "producer",
        "prediction",
        "baseline_prediction",
    }
    if not isinstance(artifacts, Mapping) or not expected_artifacts.issubset(artifacts):
        raise ValueError("actual evidence RunSpec artifacts missing")
    paths: set[str] = set()
    for name, ref in artifacts.items():
        if not isinstance(ref, Mapping) or set(ref) != {
            "logical_name",
            "relative_path",
            "bytes",
            "sha256",
            "canonical_payload_sha256",
            "row_count",
        }:
            raise ValueError(f"invalid actual evidence artifact ref: {name}")
        if ref.get("logical_name") != name or ref.get("relative_path") in paths:
            raise ValueError("actual evidence artifact name/path mismatch")
        paths.add(ref["relative_path"])
        for field in ("sha256", "canonical_payload_sha256"):
            value = ref.get(field)
            if (
                not isinstance(value, str)
                or len(value) != 64
                or any(character not in "0123456789abcdef" for character in value)
            ):
                raise ValueError(f"invalid actual evidence artifact digest: {name}")
    for field in (
        "p1_run_spec_sha256",
        "dataset_readiness_manifest_sha256",
        "actual_evaluation_policy_sha256",
        "split_manifest_sha256",
        "source_label_ledger_sha256",
        "source_digest_sha256",
        "metric_protocol_sha256",
    ):
        value = spec.get(field)
        if (
            not isinstance(value, str)
            or len(value) != 64
            or any(character not in "0123456789abcdef" for character in value)
        ):
            raise ValueError(f"invalid actual evidence binding: {field}")
    if spec.get("metric_protocol_sha256") != spec.get("actual_evaluation_policy_sha256"):
        raise ValueError("actual metric protocol must be the validated policy")
    if (
        isinstance(spec.get("bootstrap_seed"), bool)
        or not isinstance(spec.get("bootstrap_seed"), int)
        or spec["bootstrap_seed"] < 0
        or isinstance(spec.get("bootstrap_replicates"), bool)
        or not isinstance(spec.get("bootstrap_replicates"), int)
        or spec["bootstrap_replicates"] <= 0
    ):
        raise ValueError("invalid actual bootstrap plan")
    if (
        spec.get("runtime_validation") != "NOT_RUN"
        or spec.get("semantic_quality") != "REVIEW-LOCKED"
        or spec.get("full_scan_approval") is not False
        or spec.get("actual_metrics") is not None
    ):
        raise ValueError("actual evidence approval boundary mismatch")
    if spec.get("run_spec_sha256") != _actual_run_spec_self_hash(spec):
        raise ValueError("actual evidence RunSpec self hash mismatch")


def build_bound_actual_readback_from_files(
    *,
    artifact_root: str | Path,
    p1_run_spec_json: str,
    p1_comparison_json: str,
    label_ledger_json: str,
    actual_evaluation_policy_json: str,
    split_manifest_json: str,
    source_manifest_json: str,
    expected_universe_jsonl: str,
    producer_jsonl: str,
    prediction_jsonl: str,
    baseline_prediction_jsonl: str,
    additional_artifacts: Sequence[tuple[str, str]] = (),
    seed: int,
    replicates: int,
) -> tuple[Path, dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Derive, freeze and revalidate all readback bindings from source files."""

    from tools.run_calibration_dataset_readiness import build_current_readiness

    root = _resolve_path(artifact_root)
    object_inputs = {
        "p1_run_spec": p1_run_spec_json,
        "p1_comparison": p1_comparison_json,
        "label_ledger": label_ledger_json,
        "actual_evaluation_policy": actual_evaluation_policy_json,
    }
    refs: dict[str, Any] = {}
    objects: dict[str, dict[str, Any]] = {}
    for name, relative_path in object_inputs.items():
        ref, value = snapshot_json_object(root, name, relative_path)
        refs[name] = ref
        objects[name] = value
    try:
        policy = CalibrationEvaluationPolicy(**objects["actual_evaluation_policy"])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid actual evaluation policy: {exc}") from exc
    if policy.policy_scope != "FROZEN_ACTUAL_PRE_REGISTERED":
        raise ValueError("actual readback requires FROZEN_ACTUAL_PRE_REGISTERED policy")
    readiness = build_current_readiness(
        p1_run_spec_path=root / p1_run_spec_json,
        p1_comparison_path=root / p1_comparison_json,
        label_ledger_path=root / label_ledger_json,
        actual_evaluation_policy_path=root / actual_evaluation_policy_json,
    )
    for name in ("p1_run_spec", "p1_comparison", "label_ledger"):
        _artifact_source_matches(readiness["sources"][name], refs[name].to_dict(), name)
    if readiness.get("actual_evaluation_policy_sha256") != policy.policy_sha256:
        raise ValueError("readiness policy binding mismatch")
    _artifact_source_matches(
        readiness.get("actual_evaluation_policy") or {},
        refs["actual_evaluation_policy"].to_dict(),
        "actual_evaluation_policy",
    )
    if readiness.get("ready_for_split_manifest") is not True:
        counts = readiness.get("counts", {})
        raise ValueError(
            "NO_GO_ACTUAL_DATASET_NOT_READY: "
            f"ready_rows={counts.get('ready_rows')}/{counts.get('source_rows')}"
        )

    split_ref, split_payload = snapshot_json_object(
        root, "split_manifest", split_manifest_json
    )
    split_manifest = _split_manifest_from_dict(split_payload)
    if split_manifest.source_label_ledger_sha256 != refs["label_ledger"].sha256:
        raise ValueError("actual split manifest label-ledger binding mismatch")
    frozen = _validate_split_against_readiness(split_manifest, readiness, policy)
    source_ref, source_payload = snapshot_json_object(
        root, "source_manifest", source_manifest_json
    )
    source_payload_refs = _validate_actual_source_manifest(
        source_payload,
        frozen,
        artifact_root=root,
    )
    refs["split_manifest"] = split_ref
    refs["source_manifest"] = source_ref
    refs.update(source_payload_refs)
    expected_ref, expected_rows = snapshot_jsonl_rows(
        root, "expected_universe", expected_universe_jsonl
    )
    producer_ref, producer_rows = snapshot_jsonl_rows(root, "producer", producer_jsonl)
    prediction_ref, prediction_rows = snapshot_jsonl_rows(
        root, "prediction", prediction_jsonl
    )
    baseline_ref, baseline_rows = snapshot_jsonl_rows(
        root, "baseline_prediction", baseline_prediction_jsonl
    )
    refs.update(
        {
            "expected_universe": expected_ref,
            "producer": producer_ref,
            "prediction": prediction_ref,
            "baseline_prediction": baseline_ref,
        }
    )
    expected_frozen_rows = [item.to_dict() for item in frozen]
    if expected_rows != expected_frozen_rows:
        raise ValueError("expected universe does not exactly match frozen split rows")
    readiness_by_post = {str(row["post_id"]): row for row in readiness["rows"]}
    for producer_row in producer_rows:
        ready_row = readiness_by_post.get(str(producer_row.get("post_id") or ""))
        if (
            ready_row is None
            or producer_row.get("candidate_set_fingerprint")
            != ready_row.get("candidate_set_fingerprint")
        ):
            raise ValueError("producer/readiness candidate-set binding mismatch")
    source_digest_sha256 = source_ref.sha256
    if any(
        row.get("source_digest_sha256") != source_digest_sha256
        for row in producer_rows
    ):
        raise ValueError("producer rows do not bind the snapshotted source manifest")
    for name, path in additional_artifacts:
        if not name or not path or name in refs:
            raise ValueError("additional artifact names must be non-empty and unique")
        refs[name] = snapshot_artifact(
            root,
            name,
            path,
            jsonl=Path(path).suffix.lower() == ".jsonl",
        )
    _validate_actual_replay_bundle(
        root=root,
        refs=refs,
        frozen=frozen,
        split_manifest=split_manifest,
        policy=policy,
        prediction_rows=prediction_rows,
        baseline_rows=baseline_rows,
    )

    actual_run_spec: dict[str, Any] = {
        "schema_version": ACTUAL_EVIDENCE_RUN_SPEC_SCHEMA,
        "mode": "FROZEN_ACTUAL_READBACK_FOUNDATION_NO_MODEL_RUNTIME",
        "artifacts": {
            name: ref.to_dict() for name, ref in sorted(refs.items())
        },
        "p1_run_spec_sha256": objects["p1_run_spec"].get("run_spec_sha256"),
        "dataset_readiness_manifest_sha256": readiness["manifest_sha256"],
        "actual_evaluation_policy_sha256": policy.policy_sha256,
        "split_manifest_sha256": split_manifest.manifest_sha256,
        "source_label_ledger_sha256": split_manifest.source_label_ledger_sha256,
        "source_digest_sha256": source_digest_sha256,
        "metric_protocol_sha256": policy.policy_sha256,
        "bootstrap_seed": seed,
        "bootstrap_replicates": replicates,
        "runtime_validation": "NOT_RUN",
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "actual_metrics": None,
    }
    actual_run_spec["run_spec_sha256"] = _actual_run_spec_self_hash(actual_run_spec)
    validate_actual_evidence_run_spec(actual_run_spec)
    universe = expected_universe_readback(expected_rows)
    coverage = producer_coverage_receipt(expected_rows, producer_rows)
    prediction = prediction_payload_readback(expected_rows, prediction_rows)
    baseline_prediction = prediction_payload_readback(expected_rows, baseline_rows)
    manifest = build_readback_manifest(
        run_spec_sha256=actual_run_spec["run_spec_sha256"],
        artifacts=refs,
        expected_universe=universe,
        producer_coverage=coverage,
        prediction=prediction,
        baseline_prediction=baseline_prediction,
        source_digest_sha256=source_digest_sha256,
        metric_protocol_sha256=policy.policy_sha256,
        bootstrap_seed=seed,
        bootstrap_replicates=replicates,
    )
    validate_actual_readback_artifacts(root, manifest)
    return root, actual_run_spec, readiness, manifest


def render_actual_readback_markdown(
    run_spec: Mapping[str, Any],
    readiness: Mapping[str, Any],
    manifest: Mapping[str, Any],
) -> str:
    validate_actual_evidence_run_spec(run_spec)
    if manifest.get("run_spec_sha256") != run_spec.get("run_spec_sha256"):
        raise ValueError("actual report RunSpec/readback mismatch")
    counts = readiness["counts"]
    return "\n".join(
        [
            "# P3 실제 자료 독립 재판독 결과",
            "",
            "## 결론",
            "",
            "- 게이트: `GO_ACTUAL_READBACK_FOUNDATION_ONLY`",
            f"- 준비도: `{readiness['gate']}` ({counts['ready_rows']}/{counts['source_rows']})",
            f"- 예상/producer/AFTER/baseline 행: `{manifest['expected_universe']['row_count']}`",
            "- 실제 정확도·신뢰구간: `null`",
            "- runtime: `NOT_RUN`",
            "- 의미 품질: `REVIEW-LOCKED`",
            "- 전체 스캔 승인: `false`",
            "",
            "정책·P1 RunSpec·비교표·P1 결속 라벨 원장·네 JSONL을 파일에서 다시 읽어 결속했다. 이 단계는 실제 평가 입력을 동결한 것이며 보정 모델 평가나 운영 승인이 아니다.",
            "",
            f"actual RunSpec SHA-256: `{run_spec['run_spec_sha256']}`",
            f"readback manifest SHA-256: `{manifest['manifest_sha256']}`",
            "",
        ]
    )


def write_actual_readback_bundle(
    *,
    artifact_root: str | Path,
    output_dir: str | Path,
    run_spec: Mapping[str, Any],
    readiness: Mapping[str, Any],
    manifest: Mapping[str, Any],
) -> Path:
    validate_actual_evidence_run_spec(run_spec)
    root = _resolve_path(artifact_root)
    directory = _resolve_path(output_dir)
    if not root.is_dir():
        raise ValueError("actual readback artifact root must be an existing directory")
    if directory.parent != root:
        raise ValueError("actual readback output must be a direct child of artifact root")
    if directory.exists() or _is_reparse_point(directory):
        raise ValueError("actual readback output directory must be new and non-reparse")
    staging = _new_readback_staging_directory(root)
    staging_identity = _path_identity(staging)
    paths = {
        "run_spec.json": dict(run_spec),
        "readiness.json": dict(readiness),
        "readback.json": dict(manifest),
    }
    try:
        for name, payload in paths.items():
            _require_staging_identity(staging, staging_identity)
            with (staging / name).open("x", encoding="utf-8", newline="\n") as handle:
                handle.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        _require_staging_identity(staging, staging_identity)
        with (staging / "report.md").open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(render_actual_readback_markdown(run_spec, readiness, manifest))
        for name, payload in paths.items():
            _require_staging_identity(staging, staging_identity)
            if _read_json(staging / name) != payload:
                raise ValueError(f"stored actual readback bundle mismatch: {name}")
        validate_actual_readback_artifacts(artifact_root, manifest)
        _require_staging_identity(staging, staging_identity)
        if directory.exists() or _is_reparse_point(directory):
            raise ValueError("actual readback output directory appeared during staging")
        os.rename(staging, directory)
    except Exception:
        _cleanup_readback_staging(staging, staging_identity, (*paths, "report.md"))
        raise
    return directory


def _is_reparse_point(path: Path) -> bool:
    try:
        attributes = os.lstat(path).st_file_attributes
    except (AttributeError, FileNotFoundError, OSError):
        return path.is_symlink()
    return bool(attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def _path_identity(path: Path) -> tuple[int, int]:
    if _is_reparse_point(path):
        raise ValueError("actual readback staging directory must not be a reparse point")
    status = os.stat(path, follow_symlinks=False)
    if not stat.S_ISDIR(status.st_mode):
        raise ValueError("actual readback staging path must be a directory")
    return status.st_dev, status.st_ino


def _require_staging_identity(path: Path, expected: tuple[int, int]) -> None:
    if _path_identity(path) != expected:
        raise ValueError("actual readback staging directory changed during write")


def _new_readback_staging_directory(root: Path) -> Path:
    for _ in range(16):
        staging = root / f".actual-readback-staging-{secrets.token_hex(16)}"
        try:
            staging.mkdir()
        except FileExistsError:
            continue
        return staging
    raise ValueError("could not allocate actual readback staging directory")


def _cleanup_readback_staging(
    staging: Path,
    identity: tuple[int, int],
    known_names: Sequence[str],
) -> None:
    """Best-effort cleanup that never traverses a swapped staging directory."""
    try:
        _require_staging_identity(staging, identity)
    except (OSError, ValueError):
        return
    for name in known_names:
        path = staging / name
        try:
            status = os.lstat(path)
            if not _is_reparse_point(path) and stat.S_ISREG(status.st_mode):
                path.unlink()
        except FileNotFoundError:
            continue
        except OSError:
            return
    try:
        staging.rmdir()
    except OSError:
        return


def _bound_json_object(
    root: Path,
    readback: Mapping[str, Any],
    logical_name: str,
) -> dict[str, Any]:
    stored = readback.get("artifacts", {}).get(logical_name)
    if not isinstance(stored, Mapping):
        raise ValueError(f"bound actual object missing: {logical_name}")
    ref, payload = snapshot_json_object(root, logical_name, stored["relative_path"])
    if ref.to_dict() != dict(stored):
        raise ValueError(f"bound actual object snapshot mismatch: {logical_name}")
    return payload


def _bound_jsonl_rows(
    root: Path,
    readback: Mapping[str, Any],
    logical_name: str,
) -> list[dict[str, Any]]:
    stored = readback.get("artifacts", {}).get(logical_name)
    if not isinstance(stored, Mapping):
        raise ValueError(f"bound actual JSONL missing: {logical_name}")
    ref, rows = snapshot_jsonl_rows(root, logical_name, stored["relative_path"])
    if ref.to_dict() != dict(stored):
        raise ValueError(f"bound actual JSONL snapshot mismatch: {logical_name}")
    return rows


def _calibration_artifact_from_dict(value: Mapping[str, Any]) -> CalibrationArtifact:
    from src.llm_batch.grounding.candidate_set_calibration_shadow import calibration_artifact_from_dict
    return calibration_artifact_from_dict(value)


def _score_vector_from_dict(value: Mapping[str, Any]) -> EventScoreVector:
    if not isinstance(value, Mapping):
        raise ValueError("score vector must be an object")
    payload = dict(value)
    labels = payload.pop("labels", None)
    raw_scores = payload.pop("raw_scores", None)
    if not isinstance(labels, list) or not isinstance(raw_scores, list):
        raise ValueError("score vector labels/raw_scores must be lists")
    try:
        return EventScoreVector(
            **payload,
            labels=tuple(labels),
            raw_scores=tuple(raw_scores),
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid score vector: {exc}") from exc


def _base_shadow_map(
    rows: Sequence[Mapping[str, Any]],
    *,
    expected_posts: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for row in rows:
        if not isinstance(row, Mapping) or set(row) != {"example_id", "post_id", "shadow"}:
            raise ValueError("invalid bound base-shadow row")
        example_id = str(row.get("example_id") or "")
        post_id = str(row.get("post_id") or "")
        if not example_id or example_id in result or not post_id:
            raise ValueError("duplicate or blank bound base-shadow identity")
        if expected_posts is not None and expected_posts.get(example_id) != post_id:
            raise ValueError("bound base-shadow post identity mismatch")
        shadow = selective_shadow_from_dict(row.get("shadow"))
        result[example_id] = shadow
    return result


def _score_vector_map(rows: Sequence[Mapping[str, Any]]) -> dict[str, EventScoreVector]:
    result: dict[str, EventScoreVector] = {}
    for row in rows:
        score = _score_vector_from_dict(row)
        if score.example_id in result:
            raise ValueError("duplicate bound score-vector identity")
        result[score.example_id] = score
    return result


def _calibration_shadow_map(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for row in rows:
        payload = row.get("calibration_shadow") if isinstance(row, Mapping) else None
        if not isinstance(payload, Mapping):
            raise ValueError("actual prediction row lacks calibration_shadow")
        shadow = calibration_shadow_from_dict(payload)
        if shadow.example_id in result:
            raise ValueError("duplicate actual calibration-shadow identity")
        if (
            row.get("example_id") != shadow.example_id
            or row.get("post_id") != shadow.post_id
            or row.get("shadow_fingerprint") != shadow.shadow_fingerprint
            or row.get("score_vector_sha256") != shadow.score_vector_sha256
            or row.get("candidate_set_fingerprint") != shadow.candidate_set_fingerprint
            or row.get("generation_proof_fingerprint")
            != shadow.generation_proof_fingerprint
            or row.get("probabilities")
            != {
                item.label: item.probability_mass
                for item in shadow.event_probabilities
            }
        ):
            raise ValueError("actual prediction/calibration-shadow binding mismatch")
        result[shadow.example_id] = shadow
    return result


def _validate_actual_replay_bundle(
    *,
    root: Path,
    refs: Mapping[str, ArtifactRef],
    frozen: Sequence[CalibrationSplitAssignment],
    split_manifest: CalibrationSplitManifest,
    policy: CalibrationEvaluationPolicy,
    prediction_rows: Sequence[Mapping[str, Any]],
    baseline_rows: Sequence[Mapping[str, Any]],
) -> None:
    if ACTUAL_REPLAY_ARTIFACT_NAMES - set(refs):
        raise ValueError("actual readback replay artifacts are incomplete")
    jsonl_names = {
        "after_base_shadows",
        "after_score_vectors",
        "baseline_base_shadows",
        "baseline_score_vectors",
    }
    json_names = ACTUAL_REPLAY_ARTIFACT_NAMES - jsonl_names
    for name in jsonl_names:
        if Path(refs[name].relative_path).suffix.lower() != ".jsonl":
            raise ValueError(f"actual replay artifact suffix mismatch: {name}")
    for name in json_names:
        if Path(refs[name].relative_path).suffix.lower() != ".json":
            raise ValueError(f"actual replay artifact suffix mismatch: {name}")

    def bound_rows(name: str) -> list[dict[str, Any]]:
        current, rows = snapshot_jsonl_rows(root, name, refs[name].relative_path)
        if current.to_dict() != refs[name].to_dict():
            raise ValueError(f"actual replay artifact snapshot mismatch: {name}")
        return rows

    def bound_object(name: str) -> dict[str, Any]:
        current, payload = snapshot_json_object(root, name, refs[name].relative_path)
        if current.to_dict() != refs[name].to_dict():
            raise ValueError(f"actual replay artifact snapshot mismatch: {name}")
        return payload

    expected_posts = {item.example_id: item.post_id for item in frozen}
    expected_ids = set(expected_posts)
    after_bases = _base_shadow_map(
        bound_rows("after_base_shadows"),
        expected_posts=expected_posts,
    )
    baseline_bases = _base_shadow_map(
        bound_rows("baseline_base_shadows"),
        expected_posts=expected_posts,
    )
    after_scores = _score_vector_map(bound_rows("after_score_vectors"))
    baseline_scores = _score_vector_map(bound_rows("baseline_score_vectors"))
    after_artifact = _calibration_artifact_from_dict(
        bound_object("after_calibration_artifact")
    )
    baseline_artifact = _calibration_artifact_from_dict(
        bound_object("baseline_calibration_artifact")
    )
    after_artifact.validate_against(split_manifest, policy)
    baseline_artifact.validate_against(split_manifest, policy)
    after_shadows = _calibration_shadow_map(prediction_rows)
    baseline_shadows = _calibration_shadow_map(baseline_rows)
    mappings = (
        after_bases,
        baseline_bases,
        after_scores,
        baseline_scores,
        after_shadows,
        baseline_shadows,
    )
    if any(set(mapping) != expected_ids for mapping in mappings):
        raise ValueError("actual replay artifact coverage mismatch")
    if any(
        value.post_id != expected_posts[example_id]
        for mapping in (
            after_scores,
            baseline_scores,
            after_shadows,
            baseline_shadows,
        )
        for example_id, value in mapping.items()
    ):
        raise ValueError("actual replay artifact post identity mismatch")


def evaluate_bound_actual_readback_bundle(
    *,
    artifact_root: str | Path,
    readback_bundle_dir: str,
) -> tuple[Path, dict[str, Any], FrozenActualEvidenceReceipt, dict[str, Any]]:
    """Replay a bound readback bundle into the existing FROZEN_ACTUAL evaluator."""

    from src.llm_batch.grounding.calibration_dataset_readiness import (
        validate_dataset_readiness_manifest,
    )
    from tools.run_calibration_dataset_readiness import build_current_readiness

    root = _resolve_path(artifact_root)
    bundle_base = Path(readback_bundle_dir)
    _, run_spec = snapshot_json_object(
        root, "bundle_run_spec", (bundle_base / "run_spec.json").as_posix()
    )
    _, readiness = snapshot_json_object(
        root, "bundle_readiness", (bundle_base / "readiness.json").as_posix()
    )
    _, readback = snapshot_json_object(
        root, "bundle_readback", (bundle_base / "readback.json").as_posix()
    )
    validate_actual_evidence_run_spec(run_spec)
    validate_dataset_readiness_manifest(readiness)
    validate_actual_readback_artifacts(root, readback)
    if (
        run_spec["dataset_readiness_manifest_sha256"] != readiness["manifest_sha256"]
        or readback.get("run_spec_sha256") != run_spec["run_spec_sha256"]
        or readback.get("metric_protocol_sha256")
        != run_spec["actual_evaluation_policy_sha256"]
        or readback.get("source_digest_sha256") != run_spec["source_digest_sha256"]
        or readback.get("artifacts") != run_spec.get("artifacts")
    ):
        raise ValueError("actual bundle cross-binding mismatch")
    refs = run_spec["artifacts"]
    p1_payload = _bound_json_object(root, readback, "p1_run_spec")
    if p1_payload.get("run_spec_sha256") != run_spec["p1_run_spec_sha256"]:
        raise ValueError("actual bundle P1 self-hash binding mismatch")
    rebuilt_readiness = build_current_readiness(
        p1_run_spec_path=root / refs["p1_run_spec"]["relative_path"],
        p1_comparison_path=root / refs["p1_comparison"]["relative_path"],
        label_ledger_path=root / refs["label_ledger"]["relative_path"],
        actual_evaluation_policy_path=root
        / refs["actual_evaluation_policy"]["relative_path"],
    )
    if rebuilt_readiness != readiness:
        raise ValueError("actual bundle readiness source replay mismatch")

    policy_payload = _bound_json_object(root, readback, "actual_evaluation_policy")
    try:
        policy = CalibrationEvaluationPolicy(**policy_payload)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid bound actual policy: {exc}") from exc
    split_manifest = _split_manifest_from_dict(
        _bound_json_object(root, readback, "split_manifest")
    )
    if (
        split_manifest.manifest_sha256 != run_spec["split_manifest_sha256"]
        or split_manifest.source_label_ledger_sha256
        != run_spec["source_label_ledger_sha256"]
    ):
        raise ValueError("actual bundle split binding mismatch")
    frozen = _validate_split_against_readiness(split_manifest, readiness, policy)
    source_payload_refs = _validate_actual_source_manifest(
        _bound_json_object(root, readback, "source_manifest"),
        frozen,
        artifact_root=root,
    )
    if any(
        refs.get(name) != ref.to_dict()
        for name, ref in source_payload_refs.items()
    ):
        raise ValueError("actual bundle source payload binding mismatch")
    expected_rows = _bound_jsonl_rows(root, readback, "expected_universe")
    if expected_rows != [item.to_dict() for item in frozen]:
        raise ValueError("actual evaluation universe/split mismatch")

    if ACTUAL_REPLAY_ARTIFACT_NAMES - set(readback["artifacts"]):
        raise ValueError("actual evaluation replay artifacts are incomplete")
    expected_posts = {item.example_id: item.post_id for item in frozen}
    after_bases = _base_shadow_map(
        _bound_jsonl_rows(root, readback, "after_base_shadows"),
        expected_posts=expected_posts,
    )
    baseline_bases = _base_shadow_map(
        _bound_jsonl_rows(root, readback, "baseline_base_shadows"),
        expected_posts=expected_posts,
    )
    after_scores = _score_vector_map(
        _bound_jsonl_rows(root, readback, "after_score_vectors")
    )
    baseline_scores = _score_vector_map(
        _bound_jsonl_rows(root, readback, "baseline_score_vectors")
    )
    after_artifact = _calibration_artifact_from_dict(
        _bound_json_object(root, readback, "after_calibration_artifact")
    )
    baseline_artifact = _calibration_artifact_from_dict(
        _bound_json_object(root, readback, "baseline_calibration_artifact")
    )
    after_rows = _bound_jsonl_rows(root, readback, "prediction")
    baseline_rows = _bound_jsonl_rows(root, readback, "baseline_prediction")
    after_shadows = _calibration_shadow_map(after_rows)
    baseline_shadows = _calibration_shadow_map(baseline_rows)
    expected_ids = {item.example_id for item in frozen}
    if any(
        set(mapping) != expected_ids
        for mapping in (
            after_bases,
            baseline_bases,
            after_scores,
            baseline_scores,
            after_shadows,
            baseline_shadows,
        )
    ):
        raise ValueError("actual evaluation replay object coverage mismatch")
    generation_proof_set_sha256 = _canonical_hash(
        sorted(score.generation_proof_fingerprint for score in after_scores.values())
    )
    receipt = FrozenActualEvidenceReceipt.create(
        run_spec_sha256=run_spec["run_spec_sha256"],
        split_manifest_sha256=split_manifest.manifest_sha256,
        source_label_ledger_sha256=split_manifest.source_label_ledger_sha256,
        expected_universe_artifact_sha256=readback["artifacts"]["expected_universe"]["sha256"],
        prediction_artifact_sha256=readback["artifacts"]["prediction"]["sha256"],
        baseline_prediction_artifact_sha256=readback["artifacts"]["baseline_prediction"]["sha256"],
        producer_receipt_artifact_sha256=readback["artifacts"]["producer"]["sha256"],
        readback_manifest_sha256=readback["manifest_sha256"],
        evaluation_plan_sha256=readback["evaluation_plan_sha256"],
        calibrator_fit_receipt_sha256=after_artifact.calibrator_fit_receipt_sha256,
        baseline_calibrator_fit_receipt_sha256=baseline_artifact.calibrator_fit_receipt_sha256,
        generation_proof_set_sha256=generation_proof_set_sha256,
        metric_protocol_sha256=policy.policy_sha256,
    )
    evaluation = evaluate_frozen_holdout(
        split_manifest=split_manifest,
        shadows=after_shadows,
        policy=policy,
        evidence_mode="FROZEN_ACTUAL",
        base_shadows=after_bases,
        score_vectors=after_scores,
        calibration_artifact=after_artifact,
        baseline_shadows=baseline_shadows,
        baseline_base_shadows=baseline_bases,
        baseline_score_vectors=baseline_scores,
        baseline_calibration_artifact=baseline_artifact,
        actual_evidence_receipt=receipt,
        prediction_artifact_sha256=readback["artifacts"]["prediction"]["sha256"],
        baseline_prediction_artifact_sha256=readback["artifacts"]["baseline_prediction"]["sha256"],
        run_spec_sha256=run_spec["run_spec_sha256"],
        producer_receipt_artifact_sha256=readback["artifacts"]["producer"]["sha256"],
        actual_readback_manifest=readback,
        actual_bootstrap_seed=run_spec["bootstrap_seed"],
        actual_bootstrap_replicates=run_spec["bootstrap_replicates"],
        actual_readback_root=str(root),
    )
    if evaluation.get("conversion_allowed") is not False:
        raise ValueError("actual evaluation must remain shadow-only")
    result: dict[str, Any] = {
        "schema_version": ACTUAL_EVALUATION_RESULT_SCHEMA,
        "run_spec_sha256": run_spec["run_spec_sha256"],
        "readback_manifest_sha256": readback["manifest_sha256"],
        "evidence_receipt_sha256": receipt.receipt_sha256,
        "evaluation": evaluation,
        "runtime_validation": "OFFLINE_ARTIFACT_REPLAY_ONLY",
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "conversion_allowed": False,
    }
    result["result_sha256"] = _canonical_hash(result)
    validate_actual_readback_artifacts(root, readback)
    return root, result, receipt, readback


def render_actual_evaluation_markdown(result: Mapping[str, Any]) -> str:
    evaluation = result.get("evaluation")
    if not isinstance(evaluation, Mapping):
        raise ValueError("actual evaluation result missing")
    metrics = evaluation.get("metrics") if isinstance(evaluation.get("metrics"), Mapping) else {}
    return "\n".join(
        [
            "# P3 실제 보정 평가 결과",
            "",
            "## 결론",
            "",
            f"- 평가 상태: `{evaluation.get('status')}`",
            f"- 동결 평가 행: `{evaluation.get('frozen_count')}`",
            f"- 최고 후보 정확도: `{metrics.get('top_label_accuracy')}`",
            f"- 자동 처리 범위: `{metrics.get('coverage')}`",
            f"- 선택 위험: `{metrics.get('selective_risk')}`",
            "- 운영 전환: `false`",
            "- 의미 품질: `REVIEW-LOCKED`",
            "- 전체 스캔 승인: `false`",
            "",
            "`GO_FROZEN_ACTUAL_SHADOW_ONLY`가 나오더라도 실제 동결 자료의 그림자 평가 게이트만 통과한 것이다. fresh 비용 pair·hard regression·public 비간섭·사람 검토 전에는 운영 적용하지 않는다.",
            "",
            f"result SHA-256: `{result.get('result_sha256')}`",
            "",
        ]
    )


def write_actual_evaluation_bundle(
    *,
    artifact_root: str | Path,
    readback_manifest: Mapping[str, Any],
    output_dir: str | Path,
    result: Mapping[str, Any],
    receipt: FrozenActualEvidenceReceipt,
) -> Path:
    directory = _resolve_path(output_dir)
    if directory.exists():
        raise ValueError("actual evaluation output directory must be new")
    directory.mkdir(parents=True, exist_ok=False)
    payloads = {
        "evaluation.json": dict(result),
        "evidence_receipt.json": receipt.to_dict(),
    }
    try:
        for name, payload in payloads.items():
            with (directory / name).open("x", encoding="utf-8", newline="\n") as handle:
                handle.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        with (directory / "report.md").open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(render_actual_evaluation_markdown(result))
        for name, payload in payloads.items():
            if _read_json(directory / name) != payload:
                raise ValueError(f"stored actual evaluation bundle mismatch: {name}")
        validate_actual_readback_artifacts(artifact_root, readback_manifest)
    except Exception:
        for path in directory.iterdir():
            path.unlink(missing_ok=True)
        directory.rmdir()
        raise
    return directory


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="P3 calibration shadow saved/synthetic harness")
    commands = parser.add_subparsers(dest="command", required=True)
    freeze = commands.add_parser("freeze")
    freeze.add_argument("--parent-p1-run-spec", required=True)
    freeze.add_argument("--parent-p1-comparison", required=True)
    freeze.add_argument("--parent-p2-run-spec", required=True)
    freeze.add_argument("--parent-p2-comparison", required=True)
    freeze.add_argument("--label-ledger", required=True)
    freeze.add_argument(
        "--dataset-readiness",
        default=str(DEFAULT_DATASET_READINESS),
    )
    freeze.add_argument("--output", required=True)
    status = commands.add_parser("status")
    status.add_argument("--run-spec", required=True)
    compare = commands.add_parser("compare")
    compare.add_argument("--run-spec", required=True)
    compare.add_argument("--output-json", required=True)
    compare.add_argument("--output-md", required=True)
    preflight = commands.add_parser("actual-preflight")
    preflight.add_argument("--artifact-root", required=True)
    preflight.add_argument("--p1-run-spec-json", required=True)
    preflight.add_argument("--p1-comparison-json", required=True)
    preflight.add_argument("--label-ledger-json", required=True)
    preflight.add_argument("--actual-evaluation-policy-json", required=True)
    preflight.add_argument("--split-manifest-json", required=True)
    preflight.add_argument("--source-manifest-json", required=True)
    preflight.add_argument("--expected-universe-jsonl", required=True)
    preflight.add_argument("--producer-jsonl", required=True)
    preflight.add_argument("--prediction-jsonl", required=True)
    preflight.add_argument("--baseline-prediction-jsonl", required=True)
    preflight.add_argument("--artifact", action="append", default=[], help="logical_name=relative_path")
    preflight.add_argument("--seed", type=int, required=True)
    preflight.add_argument("--replicates", type=int, required=True)
    actual = commands.add_parser("actual-readback")
    actual.add_argument("--artifact-root", required=True)
    actual.add_argument("--p1-run-spec-json", required=True)
    actual.add_argument("--p1-comparison-json", required=True)
    actual.add_argument("--label-ledger-json", required=True)
    actual.add_argument("--actual-evaluation-policy-json", required=True)
    actual.add_argument("--split-manifest-json", required=True)
    actual.add_argument("--source-manifest-json", required=True)
    actual.add_argument("--expected-universe-jsonl", required=True)
    actual.add_argument("--producer-jsonl", required=True)
    actual.add_argument("--prediction-jsonl", required=True)
    actual.add_argument("--baseline-prediction-jsonl", required=True)
    actual.add_argument("--artifact", action="append", default=[], help="logical_name=relative_path")
    actual.add_argument("--seed", type=int, required=True)
    actual.add_argument("--replicates", type=int, required=True)
    actual.add_argument("--output-dir", required=True)
    evaluate_actual = commands.add_parser("actual-evaluate")
    evaluate_actual.add_argument("--artifact-root", required=True)
    evaluate_actual.add_argument("--readback-bundle-dir", required=True)
    evaluate_actual.add_argument("--output-dir", required=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.command == "freeze":
        spec = create_run_spec(
            parent_p1_run_spec_path=args.parent_p1_run_spec,
            parent_p1_comparison_path=args.parent_p1_comparison,
            parent_p2_run_spec_path=args.parent_p2_run_spec,
            parent_p2_comparison_path=args.parent_p2_comparison,
            label_ledger_path=args.label_ledger,
            dataset_readiness_path=args.dataset_readiness,
        )
        output = write_run_spec(spec, args.output)
        print(json.dumps({"gate": "GO_P3_CONTRACT_FOUNDATION_ONLY", "output": _stored_path(output), "run_spec_sha256": spec["run_spec_sha256"], "runtime_validation": "NOT_RUN", "semantic_quality": "REVIEW-LOCKED", "full_scan_approval": False}, ensure_ascii=False))
        return 0
    if args.command == "status":
        spec, context = validate_run_spec(args.run_spec)
        print(json.dumps({"gate": "GO_P3_CONTRACT_FOUNDATION_ONLY", "mode": spec["mode"], "golden_rows": context["p1_comparison"].get("summary", {}).get("candidate_nil_event_rows"), "runtime_validation": "NOT_RUN", "semantic_quality": "REVIEW-LOCKED", "full_scan_approval": False}, ensure_ascii=False))
        return 0
    if args.command == "actual-preflight":
        additional_artifacts: list[tuple[str, str]] = []
        for item in args.artifact:
            name, sep, path = item.partition("=")
            if not sep:
                name = ""
                path = item
            additional_artifacts.append((name, path))
        report = build_actual_preflight_report(
            artifact_root=args.artifact_root,
            p1_run_spec_json=args.p1_run_spec_json,
            p1_comparison_json=args.p1_comparison_json,
            label_ledger_json=args.label_ledger_json,
            actual_evaluation_policy_json=args.actual_evaluation_policy_json,
            split_manifest_json=args.split_manifest_json,
            source_manifest_json=args.source_manifest_json,
            expected_universe_jsonl=args.expected_universe_jsonl,
            producer_jsonl=args.producer_jsonl,
            prediction_jsonl=args.prediction_jsonl,
            baseline_prediction_jsonl=args.baseline_prediction_jsonl,
            additional_artifacts=additional_artifacts,
            seed=args.seed,
            replicates=args.replicates,
        )
        print(json.dumps(report, ensure_ascii=False))
        return 0 if report["gate"] == "GO_ACTUAL_BOUND_READBACK_ATTEMPT_ALLOWED" else 2
    if args.command == "actual-readback":
        additional_artifacts: list[tuple[str, str]] = []
        for item in args.artifact:
            name, sep, path = item.partition("=")
            if not sep or not name or not path:
                raise ValueError("--artifact must be unique logical_name=relative_path")
            additional_artifacts.append((name, path))
        root, actual_run_spec, readiness, manifest = build_bound_actual_readback_from_files(
            artifact_root=args.artifact_root,
            p1_run_spec_json=args.p1_run_spec_json,
            p1_comparison_json=args.p1_comparison_json,
            label_ledger_json=args.label_ledger_json,
            actual_evaluation_policy_json=args.actual_evaluation_policy_json,
            split_manifest_json=args.split_manifest_json,
            source_manifest_json=args.source_manifest_json,
            expected_universe_jsonl=args.expected_universe_jsonl,
            producer_jsonl=args.producer_jsonl,
            prediction_jsonl=args.prediction_jsonl,
            baseline_prediction_jsonl=args.baseline_prediction_jsonl,
            additional_artifacts=additional_artifacts,
            seed=args.seed,
            replicates=args.replicates,
        )
        output_path = write_actual_readback_bundle(
            artifact_root=root,
            output_dir=args.output_dir,
            run_spec=actual_run_spec,
            readiness=readiness,
            manifest=manifest,
        )
        print(
            json.dumps(
                {
                    "gate": "GO_ACTUAL_READBACK_FOUNDATION_ONLY",
                    "actual_readback_root": str(root),
                    "actual_run_spec_sha256": actual_run_spec["run_spec_sha256"],
                    "evaluation_plan_sha256": manifest["evaluation_plan_sha256"],
                    "readback_manifest_sha256": manifest["manifest_sha256"],
                    "output_dir": _stored_path(output_path),
                    "readback_manifest": manifest,
                    "semantic_quality": "REVIEW-LOCKED",
                    "full_scan_approval": False,
                },
                ensure_ascii=False,
            )
        )
        return 0
    if args.command == "actual-evaluate":
        root, result, receipt, readback = evaluate_bound_actual_readback_bundle(
            artifact_root=args.artifact_root,
            readback_bundle_dir=args.readback_bundle_dir,
        )
        output_path = write_actual_evaluation_bundle(
            artifact_root=root,
            readback_manifest=readback,
            output_dir=args.output_dir,
            result=result,
            receipt=receipt,
        )
        print(
            json.dumps(
                {
                    "gate": result["evaluation"].get("status"),
                    "artifact_root": str(root),
                    "result_sha256": result["result_sha256"],
                    "output_dir": _stored_path(output_path),
                    "semantic_quality": "REVIEW-LOCKED",
                    "full_scan_approval": False,
                    "conversion_allowed": False,
                },
                ensure_ascii=False,
            )
        )
        return 0
    report = build_comparison(args.run_spec)
    json_path, markdown_path = write_comparison(report, output_json=args.output_json, output_md=args.output_md)
    print(json.dumps({"gate": report["gates"]["overall"], "output_json": _stored_path(json_path), "output_md": _stored_path(markdown_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
